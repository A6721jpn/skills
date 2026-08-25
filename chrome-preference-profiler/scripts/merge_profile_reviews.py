#!/usr/bin/env python3
"""Strictly merge typed aggregate-only reviewer judgments into a v2 draft."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from validate_profile import validate_profile


ROOT_KEYS = {"schema_version", "profile_id", "baseline_sha256", "reviewer_id", "reviewer_role", "judgments"}
REVIEWER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
BASELINE_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
JUDGMENT_KEYS = {
    "topic_id",
    "recommendation",
    "weight_delta",
    "confidence_delta",
    "intent",
    "time_horizon",
    "reason_codes",
}
ROLES = {"temporal", "intent", "news-utility", "calibration", "skeptic"}
RECOMMENDATIONS = {"keep", "deprioritize", "exclude", "uncertain"}
INTENTS = {"personal", "professional", "mixed", "unknown"}
HORIZONS = {"durable", "emerging", "transient", "uncertain"}
REASON_CODES = {
    "cross-day-support",
    "cross-domain-support",
    "stable-recurrence",
    "single-window-burst",
    "work-utility-risk",
    "high-attention-coverage",
    "low-attention-coverage",
    "coverage-short",
    "taxonomy-ambiguity",
    "news-utility-high",
    "news-utility-low",
    "insufficient-evidence",
}
RECOMMENDATION_DELTA = {"keep": 0.0, "uncertain": -0.02, "deprioritize": -0.08, "exclude": -0.15}


def reject_constant(_: str) -> None:
    raise ValueError("non-finite JSON number")


def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_json_strict(path: Path) -> Any:
    return json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicate_pairs,
    )


def read_json_with_sha256(path: Path) -> tuple[Any, str]:
    """Read and hash the exact UTF-8 baseline bytes as one consistent snapshot."""
    payload = path.read_bytes()
    data = json.loads(
        payload.decode("utf-8"),
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicate_pairs,
    )
    return data, hashlib.sha256(payload).hexdigest()


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(path)


def number_in_delta_range(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and -0.15 <= value <= 0.15


def validate_review(
    data: Any,
    *,
    profile_id: str,
    baseline_sha256: str,
    topic_ids: set[str],
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict) or set(data) != ROOT_KEYS:
        return ["review root does not match the strict schema"]
    if data.get("schema_version") != "profile-review/v1":
        errors.append("review schema version is unsupported")
    if data.get("profile_id") != profile_id:
        errors.append("review profile identifier does not match")
    review_baseline_sha256 = data.get("baseline_sha256")
    if not isinstance(review_baseline_sha256, str) or not BASELINE_SHA256_RE.fullmatch(review_baseline_sha256):
        errors.append("baseline_sha256 must be 64 lowercase hexadecimal characters")
    elif review_baseline_sha256 != baseline_sha256:
        errors.append("review baseline SHA-256 does not match the baseline profile")
    reviewer_id = data.get("reviewer_id")
    if not isinstance(reviewer_id, str) or not REVIEWER_ID_RE.fullmatch(reviewer_id):
        errors.append("reviewer_id must be a unique safe identifier")
    if data.get("reviewer_role") not in ROLES:
        errors.append("reviewer role is unsupported")
    judgments = data.get("judgments")
    if not isinstance(judgments, list) or not 1 <= len(judgments) <= 64:
        errors.append("judgments must contain between 1 and 64 items")
        return errors
    seen: set[str] = set()
    for judgment in judgments:
        if not isinstance(judgment, dict) or set(judgment) != JUDGMENT_KEYS:
            errors.append("a judgment does not match the strict schema")
            continue
        topic_id = judgment.get("topic_id")
        if topic_id not in topic_ids:
            errors.append("a judgment references an unknown topic")
        elif topic_id in seen:
            errors.append("a review repeats a topic judgment")
        else:
            seen.add(topic_id)
        if judgment.get("recommendation") not in RECOMMENDATIONS:
            errors.append("a recommendation is unsupported")
        if not number_in_delta_range(judgment.get("weight_delta")):
            errors.append("a weight delta is outside the allowed range")
        if not number_in_delta_range(judgment.get("confidence_delta")):
            errors.append("a confidence delta is outside the allowed range")
        if judgment.get("intent") not in INTENTS:
            errors.append("an intent judgment is unsupported")
        if judgment.get("time_horizon") not in HORIZONS:
            errors.append("a horizon judgment is unsupported")
        reason_codes = judgment.get("reason_codes")
        if (
            not isinstance(reason_codes, list)
            or len(reason_codes) > 12
            or len(set(reason_codes)) != len(reason_codes)
            or any(code not in REASON_CODES for code in reason_codes)
        ):
            errors.append("reason codes are invalid")
    return errors


def review_digest(data: dict[str, Any]) -> str:
    """Hash review content without identity fields to catch copied/relabelled reviews."""
    canonical_judgments = []
    for judgment in data["judgments"]:
        canonical = dict(judgment)
        canonical["reason_codes"] = sorted(canonical["reason_codes"])
        canonical_judgments.append(canonical)
    canonical_judgments.sort(key=lambda item: str(item["topic_id"]))
    payload = {
        "schema_version": data["schema_version"],
        "profile_id": data["profile_id"],
        "judgments": canonical_judgments,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def mode_or_default(values: list[str], default: str) -> str:
    if not values:
        return default
    counts = Counter(values)
    most_common = counts.most_common()
    if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
        return default
    return most_common[0][0]


def summarize_role(
    judgments: list[dict[str, Any]],
    *,
    default_intent: str,
    default_horizon: str,
) -> dict[str, Any]:
    return {
        "recommendation": mode_or_default(
            [str(item["recommendation"]) for item in judgments],
            "uncertain",
        ),
        "weight_delta": statistics.median(float(item["weight_delta"]) for item in judgments),
        "confidence_delta": statistics.median(float(item["confidence_delta"]) for item in judgments),
        "intent": mode_or_default([str(item["intent"]) for item in judgments], default_intent),
        "time_horizon": mode_or_default(
            [str(item["time_horizon"]) for item in judgments],
            default_horizon,
        ),
    }


def disagreement(judgments: list[dict[str, Any]]) -> float:
    if len(judgments) < 2:
        return 1.0
    weight_values = [float(item["weight_delta"]) for item in judgments]
    confidence_values = [float(item["confidence_delta"]) for item in judgments]
    numeric = max((max(weight_values) - min(weight_values)) / 0.3, (max(confidence_values) - min(confidence_values)) / 0.3)
    categorical = 0.0
    for key in ("recommendation", "intent", "time_horizon"):
        counts = Counter(str(item[key]) for item in judgments)
        categorical = max(categorical, 1 - max(counts.values()) / len(judgments))
    return bounded(max(numeric, categorical))


def has_keep_exclude_split(judgments: list[dict[str, Any]]) -> bool:
    counts = Counter(str(item["recommendation"]) for item in judgments)
    if not counts["keep"] or not counts["exclude"]:
        return False
    return min(counts["keep"], counts["exclude"]) / len(judgments) > 0.3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-reviews", type=int, default=5)
    parser.add_argument("--min-topic-judgments", type=int, default=3)
    args = parser.parse_args()

    try:
        if args.min_reviews < 3 or args.min_topic_judgments < 3:
            raise ValueError("review quorum must be at least three")
        if len(args.reviews) > 35:
            raise ValueError("review input exceeds the 35-review stopping limit")
        if args.profile.stat().st_size > 2_000_000:
            raise ValueError("profile exceeds the 2 MB safety limit")
        if any(path.stat().st_size > 262_144 for path in args.reviews):
            raise ValueError("a review exceeds the 256 KB safety limit")
        profile, baseline_sha256 = read_json_with_sha256(args.profile)
        profile_errors = validate_profile(profile)
        if profile_errors:
            raise ValueError("baseline profile is invalid")
        if profile.get("schema_version") != "interest-profile/v2":
            raise ValueError("aggregate review requires interest-profile/v2")
        if profile.get("approval", {}).get("status") != "draft":
            raise ValueError("aggregate review requires a draft baseline")
        topic_ids = {topic["id"] for topic in profile["topics"]}

        resolved_output = args.output.resolve()
        resolved_inputs = [args.profile.resolve(), *(path.resolve() for path in args.reviews)]
        if any(resolved_output == input_path for input_path in resolved_inputs):
            raise ValueError("merge output must not alias the baseline or a review input")
        for input_path in resolved_inputs:
            try:
                if args.output.exists() and args.output.samefile(input_path):
                    raise ValueError("merge output must not alias the baseline or a review input")
            except OSError:
                pass

        reviews: list[dict[str, Any]] = []
        reviewer_ids: set[str] = set()
        review_digests: set[str] = set()
        for path in args.reviews:
            review = read_json_strict(path)
            review_errors = validate_review(
                review,
                profile_id=profile["profile_id"],
                baseline_sha256=baseline_sha256,
                topic_ids=topic_ids,
            )
            if review_errors:
                raise ValueError("a review failed the strict aggregate-only contract: " + "; ".join(review_errors))
            reviewer_id = review["reviewer_id"]
            if reviewer_id in reviewer_ids:
                raise ValueError("reviewer_id values must be unique")
            digest = review_digest(review)
            if digest in review_digests:
                raise ValueError("review content digests must be unique")
            reviewer_ids.add(reviewer_id)
            review_digests.add(digest)
            reviews.append(review)
        if len(reviews) < args.min_reviews:
            raise ValueError("valid review quorum was not reached")
        roles = {review["reviewer_role"] for review in reviews}
        if len(roles) < 3:
            raise ValueError("at least three distinct review roles are required")
        role_review_counts = Counter(review["reviewer_role"] for review in reviews)
        if any(count > 7 for count in role_review_counts.values()):
            raise ValueError("a reviewer role exceeds the seven-review stopping limit")

        by_topic: defaultdict[str, defaultdict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        for review in reviews:
            for judgment in review["judgments"]:
                by_topic[judgment["topic_id"]][review["reviewer_role"]].append(judgment)

        max_disagreement = 0.0
        any_contested = False
        confidence_cap = float(profile["inference"]["calibration"]["confidence_cap"])
        for topic in profile["topics"]:
            role_groups = by_topic.get(topic["id"], {})
            judgments = [
                summarize_role(
                    role_groups[role],
                    default_intent=topic["intent"],
                    default_horizon=topic["time_horizon"],
                )
                for role in sorted(role_groups)
            ]
            topic_disagreement = disagreement(judgments)
            max_disagreement = max(max_disagreement, topic_disagreement)
            contested = (
                len(judgments) < args.min_topic_judgments
                or topic_disagreement > 0.25
                or has_keep_exclude_split(judgments)
            )
            any_contested = any_contested or contested
            if topic.get("user_confirmed") is not None:
                continue
            if contested:
                topic["confidence"] = round(bounded(float(topic["confidence"]) - 0.05), 2)
                continue
            recommendation_adjustments = [RECOMMENDATION_DELTA[item["recommendation"]] for item in judgments]
            weight_delta = statistics.median(float(item["weight_delta"]) for item in judgments)
            confidence_delta = statistics.median(float(item["confidence_delta"]) for item in judgments)
            recommendation_delta = statistics.median(recommendation_adjustments)
            topic["weight"] = round(bounded(float(topic["weight"]) + weight_delta + recommendation_delta), 2)
            topic["confidence"] = round(
                min(
                    confidence_cap,
                    bounded(float(topic["confidence"]) + confidence_delta - 0.1 * topic_disagreement),
                ),
                2,
            )
            topic["intent"] = mode_or_default([str(item["intent"]) for item in judgments], topic["intent"])
            topic["time_horizon"] = mode_or_default(
                [str(item["time_horizon"]) for item in judgments],
                topic["time_horizon"],
            )

        profile["topics"].sort(key=lambda topic: (-float(topic["weight"]), -float(topic["confidence"]), topic["id"]))
        profile["inference"]["ensemble"] = {
            "status": "contested" if any_contested else "converged",
            "review_count": len(reviews),
            "role_count": len(roles),
            "max_disagreement": round(max_disagreement, 2),
        }
        profile["approval"] = {"status": "draft", "approved_at": None}
        merged_errors = validate_profile(profile)
        if merged_errors:
            raise ValueError("merged profile failed validation")
        write_json_atomic(args.output, profile)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"MERGED: {len(reviews)} aggregate reviews -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
