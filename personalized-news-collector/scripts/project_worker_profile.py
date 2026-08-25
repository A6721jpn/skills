#!/usr/bin/env python3
"""Create the narrow, public profile projection that workers may receive.

The input profile is validated locally and must be approved.  This module is
deliberately the only place where a full profile is converted to worker input;
the projection omits coverage, privacy, inference evidence, attention data,
raw history, approval metadata, and local paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any

from run_limits import copy_run_budgets
from validate_profile import validate_profile


MAX_PROFILE_BYTES = 2_000_000
MAX_PROJECTION_BYTES = 2_000_000
PROJECTION_SCHEMA = "worker-profile/v1"
PROMPT_INJECTION_RE = re.compile(
    r"(?:ignore\s+(?:all\s+)?(?:the\s+)?previous\s+instructions?|"
    r"disregard\s+(?:all\s+)?(?:the\s+)?instructions?|"
    r"system\s+message|developer\s+message|assistant\s+message|tool\s+call|"
    r"<\s*/?\s*(?:system|developer|assistant|tool)\b|"
    r"\b(?:BEGIN|END)\s+(?:SYSTEM|DEVELOPER|ASSISTANT|TOOL)\b)",
    re.IGNORECASE,
)
WINDOWS_REPARSE_POINT = 0x400


def _absolute_without_following_links(path: Path) -> Path:
    """Return an absolute path while rejecting symlink/reparse components."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    current = absolute
    components: list[Path] = []
    while True:
        components.append(current)
        if current.parent == current:
            break
        current = current.parent
    for component in reversed(components):
        try:
            info = os.lstat(component)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & WINDOWS_REPARSE_POINT:
            raise ValueError(f"reparse-point paths are not allowed: {component}")
    return absolute


def _require_under(path: Path, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("worker projection output must stay under --output-root") from exc


def _check_public_text(value: Any, field: str) -> None:
    if isinstance(value, str) and PROMPT_INJECTION_RE.search(value):
        raise ValueError(f"{field} contains instruction-like text not safe for workers")


def _file_signature(info: os.stat_result) -> tuple[int, int, int, int]:
    # Windows reports ctime differently for a handle and a path; keep the
    # cross-API identity/size/mtime fields only.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _read_stable_profile(path: Path) -> tuple[dict[str, Any], str]:
    """Read, hash, and decode one stable profile byte snapshot."""

    last_error: OSError | None = None
    for _ in range(3):
        try:
            _absolute_without_following_links(path)
            with path.open("rb") as handle:
                before = os.fstat(handle.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError("regular profile file required")
                payload = handle.read(MAX_PROFILE_BYTES + 1)
                after = os.fstat(handle.fileno())
            current = path.stat()
            _absolute_without_following_links(path)
        except OSError as exc:
            last_error = exc
            continue
        if len(payload) > MAX_PROFILE_BYTES:
            raise ValueError("profile exceeds the 2 MB safety limit")
        if _file_signature(before) != _file_signature(after) or _file_signature(after) != _file_signature(current):
            continue
        try:
            from validate_profile import loads_json_strict

            value = loads_json_strict(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("profile is not strict UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("profile root must be an object")
        return value, hashlib.sha256(payload).hexdigest()
    if last_error is not None:
        raise ValueError("profile could not be read stably") from last_error
    raise ValueError("profile changed while it was being read")


def _atomic_write_json(path: Path, value: Any) -> None:
    """Write JSON in the destination directory, then atomically replace it."""

    path = _absolute_without_following_links(path)
    _absolute_without_following_links(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if len(payload.encode("utf-8")) > MAX_PROJECTION_BYTES:
        raise ValueError("worker projection exceeds the 2 MB safety limit")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        temporary.replace(path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _safe_topic(topic: dict[str, Any], schema_version: str) -> dict[str, Any]:
    """Copy only public fields from one already-validated eligible topic."""

    _check_public_text(topic["label"], "topic label")
    for index, term in enumerate(topic["news_query_terms"]):
        _check_public_text(term, f"topic news_query_terms[{index}]")
    for index, domain in enumerate(topic["preferred_primary_domains"]):
        _check_public_text(domain, f"topic preferred_primary_domains[{index}]")
    projected: dict[str, Any] = {
        "id": topic["id"],
        "label": topic["label"],
        "weight": topic["weight"],
        "confidence": topic["confidence"],
        "news_query_terms": list(topic["news_query_terms"]),
        "preferred_primary_domains": list(topic["preferred_primary_domains"]),
    }
    if schema_version == "interest-profile/v2":
        horizon = topic["horizon"]
        projected.update(
            {
                "intent": topic["intent"],
                "time_horizon": topic["time_horizon"],
                # Keep only aggregate horizon scores.  Raw intent probabilities
                # and attention evidence are intentionally not worker fields.
                "horizon": {
                    "short_score": horizon["short_score"],
                    "long_score": horizon["long_score"],
                },
            }
        )
    return projected


def project_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic safe projection of an approved profile.

    ``profile`` must already be a decoded object.  Validation is repeated here
    so callers cannot accidentally bypass the approval/privacy contract.
    """

    errors = validate_profile(profile)
    if errors:
        raise ValueError("invalid profile: " + "; ".join(errors))
    if profile["approval"]["status"] != "approved":
        raise ValueError("worker projection requires an approved profile")

    schema_version = profile["schema_version"]
    eligible_topics = [
        topic
        for topic in profile["topics"]
        if topic.get("news_eligible") is True and topic.get("user_confirmed") is not False
    ]
    if not eligible_topics:
        raise ValueError("approved profile has no eligible public topics")
    budgets = copy_run_budgets()
    if len(eligible_topics) > budgets["max_topic_shards"]:
        raise ValueError(
            f"eligible topic shards exceed the fixed limit of {budgets['max_topic_shards']}"
        )

    # The ranking score is deliberately based only on public projected values.
    # The profile producer has already applied the conservative v2 sanitizer;
    # user-confirmed topics remain authoritative at runtime.
    eligible_topics.sort(
        key=lambda topic: (
            -(0.7 * float(topic["weight"]) + 0.3 * float(topic["confidence"])),
            topic["id"],
        )
    )

    projection: dict[str, Any] = {
        "schema_version": PROJECTION_SCHEMA,
        "profile_schema_version": schema_version,
        "profile_id": profile["profile_id"],
        "topics": [_safe_topic(topic, schema_version) for topic in eligible_topics],
        "exclusions": {
            "topic_ids": list(profile["exclusions"]["topic_ids"]),
            "terms": list(profile["exclusions"]["terms"]),
            "domains": list(profile["exclusions"]["domains"]),
        },
        "digest_defaults": dict(profile["digest_defaults"]),
        "budgets": budgets,
    }
    for key in ("topic_ids", "terms", "domains"):
        for index, value in enumerate(profile["exclusions"][key]):
            _check_public_text(value, f"exclusions.{key}[{index}]")
    for index, value in enumerate(profile["digest_defaults"]["language_order"]):
        _check_public_text(value, f"digest_defaults.language_order[{index}]")
    if "source_policy" in profile:
        for key in ("prefer", "deprioritize"):
            for index, value in enumerate(profile["source_policy"][key]):
                _check_public_text(value, f"source_policy.{key}[{index}]")
        projection["source_policy"] = {
            "prefer": list(profile["source_policy"]["prefer"]),
            "deprioritize": list(profile["source_policy"]["deprioritize"]),
        }
    return projection


def project_profile_file(
    profile_path: Path,
    output_path: Path,
    *,
    output_root: Path | None = None,
    expected_profile_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate and atomically write a worker projection."""

    profile_path = _absolute_without_following_links(profile_path)
    output_path = _absolute_without_following_links(output_path)
    if output_root is None:
        raise ValueError("coordinator-owned output_root is required")
    output_root = _absolute_without_following_links(output_root)
    _require_under(output_path, output_root)
    if profile_path == output_path:
        raise ValueError("profile and worker projection paths must differ")
    if profile_path.stat().st_size > MAX_PROFILE_BYTES:
        raise ValueError("profile exceeds the 2 MB safety limit")
    profile, profile_sha256 = _read_stable_profile(profile_path)
    if expected_profile_sha256 is not None and profile_sha256 != expected_profile_sha256:
        raise ValueError("profile does not match the coordinator snapshot hash")
    projection = project_profile(profile)
    _atomic_write_json(output_path, projection)
    return projection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="coordinator-owned directory; output cannot escape it",
    )
    parser.add_argument("--expected-profile-sha256")
    args = parser.parse_args()
    try:
        projection = project_profile_file(
            args.profile,
            args.output,
            output_root=args.output_root,
            expected_profile_sha256=args.expected_profile_sha256,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=os.sys.stderr)
        return 1
    print(f"PROJECTED: {len(projection['topics'])} topics -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
