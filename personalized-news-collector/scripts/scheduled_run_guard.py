#!/usr/bin/env python3
"""Guard the stateful part of an approved scheduled news run.

The guard is intentionally small and file-backed.  A coordinator starts a
run, passes only the projection produced by ``project_worker_profile.py`` to
workers, records bounded progress, marks an already atomically-written digest,
and then commits seen state.  Workers never receive the state directory,
profile path, seen path, or owner token.

The owner token is a bearer capability for one coordinator process.  Every
mutating command requires it, while ``recover`` is an explicit administrator
operation that can reclaim a lock only after proving its recorded process is
dead.  Profile and initial-seen hashes are checked before both commit phases.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import secrets
import stat
import socket
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from run_limits import RUN_BUDGETS, copy_run_budgets, validate_run_budgets
from validate_profile import loads_json_strict, validate_profile


JOURNAL_SCHEMA = "news-run/v1"
LOCK_SCHEMA = "news-run-lock/v1"
RUN_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)
PRIVATE_HOST_SUFFIXES = (".internal", ".local", ".lan", ".corp", ".home", ".localhost", ".invalid", ".test", ".example")
RESERVED_HOSTS = {"localhost", "example.com", "example.org", "example.net"}
MAX_PROFILE_BYTES = 2_000_000
MAX_SEEN_BYTES = 5_000_000
MAX_DIGEST_BYTES = 10_000_000
MAX_JOURNAL_BYTES = 10_000_000
TERMINAL_STATES = frozenset({"seen-committed", "aborted"})
USAGE_KEYS = frozenset(
    {"waves", "pages", "retries", "retries_per_job", "workers", "topic_shards", "candidates"}
)
WINDOWS_REPARSE_POINT = 0x400
JOURNAL_KEYS = frozenset(
    {
        "schema_version", "run_id", "state", "created_at", "updated_at", "started_at",
        "run_timestamp", "timezone", "profile_path", "seen_path", "profile_sha256",
        "initial_seen_exists", "initial_seen_sha256", "budgets", "budget_usage", "config",
        "config_sha256", "owner_token_sha256", "digest_path", "digest_sha256",
        "seen_source_path", "seen_source_sha256", "prepared_seen", "expected_seen_sha256", "events",
    }
)
LOCK_KEYS = frozenset({"schema_version", "run_id", "owner_token", "pid", "host", "created_at"})
STATES = frozenset({"starting", "started", "collecting", "digest-committed", "seen-prepared", "seen-committed", "aborted"})


class GuardError(ValueError):
    """A fail-closed guard error suitable for a CLI diagnostic."""


def _absolute_without_following_links(path: Path) -> Path:
    """Return an absolute path while rejecting symlink/reparse components."""

    # Normalize ``..`` before containment checks and before persisting paths in
    # the journal.  ``Path.relative_to`` is lexical; checking it against an
    # unnormalised path can otherwise make ``root/../outside`` look contained.
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
            raise GuardError(f"reparse-point paths are not allowed: {component}")
    return absolute


def _now_iso(value: str | None = None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    parsed = _parse_timestamp(value)
    return parsed.isoformat()


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise GuardError("timestamp must be a timezone-aware ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GuardError("timestamp must be a timezone-aware ISO-8601 string") from exc
    if parsed.tzinfo is None:
        raise GuardError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _safe_run_id(value: str) -> str:
    if not isinstance(value, str) or not RUN_ID_RE.fullmatch(value):
        raise GuardError("run_id must be a lowercase slug of at most 64 characters")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_signature(info: os.stat_result) -> tuple[int, int, int, int]:
    # Do not include ctime: Windows exposes different creation/change-time
    # values through fstat(handle) and stat(path).  Handle identity plus size
    # and mtime still detects replacement and in-read mutation portably.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _read_stable_bytes(path: Path, *, maximum: int) -> tuple[bytes, str]:
    """Read one stable regular-file snapshot and hash those exact bytes."""

    path = _absolute_without_following_links(path)
    last_error: OSError | None = None
    for _ in range(3):
        try:
            _absolute_without_following_links(path)
            with path.open("rb") as handle:
                before = os.fstat(handle.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise GuardError(f"regular file required: {path}")
                payload = handle.read(maximum + 1)
                after = os.fstat(handle.fileno())
            current = path.stat()
            _absolute_without_following_links(path)
        except GuardError:
            raise
        except OSError as exc:
            last_error = exc
            continue
        if len(payload) > maximum:
            raise GuardError(f"file exceeds safety limit: {path}")
        if _file_signature(before) == _file_signature(after) == _file_signature(current):
            return payload, _sha256_bytes(payload)
    if last_error is not None:
        raise GuardError(f"file could not be read stably: {path}") from last_error
    raise GuardError(f"file changed while it was being read: {path}")


def _sha256_file(path: Path, *, maximum: int | None = None) -> str:
    path = _absolute_without_following_links(path)
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise GuardError(f"regular non-symlink file required: {path}")
    _, digest = _read_stable_bytes(path, maximum=maximum or MAX_JOURNAL_BYTES)
    return digest


def _atomic_write_json(path: Path, value: Any, *, maximum: int = MAX_JOURNAL_BYTES) -> None:
    path = _absolute_without_following_links(path)
    _absolute_without_following_links(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    encoded = payload.encode("utf-8")
    if len(encoded) > maximum:
        raise GuardError(f"JSON artifact exceeds safety limit: {path}")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, delete=False
        ) as handle:
            handle.write(encoded)
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


def atomic_write_text(path: Path, text: str, *, maximum: int = MAX_DIGEST_BYTES) -> None:
    """Atomically write a digest before it can be marked committed."""

    if not isinstance(text, str) or not text.strip():
        raise GuardError("digest text must be non-empty")
    if not text.lstrip().startswith("#"):
        raise GuardError("digest must contain a non-empty Markdown heading")
    if any(
        (ord(character) < 0x20 and character not in {"\n", "\r", "\t"})
        or ord(character) == 0x7F
        for character in text
    ):
        raise GuardError("digest contains NUL or other control characters")
    encoded = text.encode("utf-8")
    if len(encoded) > maximum:
        raise GuardError("digest exceeds the 10 MB safety limit")
    path = _absolute_without_following_links(path)
    if path.suffix.casefold() != ".md":
        raise GuardError("digest output must be a Markdown .md file")
    _absolute_without_following_links(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", dir=path.parent, delete=False
        ) as handle:
            handle.write(encoded)
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


def _journal_dir(state_dir: Path) -> Path:
    return state_dir / "journal"


def _journal_path(state_dir: Path, run_id: str) -> Path:
    state_dir = _absolute_without_following_links(state_dir)
    return _journal_dir(state_dir) / f"{_safe_run_id(run_id)}.json"


def _lock_path(state_dir: Path) -> Path:
    return _absolute_without_following_links(state_dir) / "run.lock"


def _read_json(path: Path, *, maximum: int) -> Any:
    path = _absolute_without_following_links(path)
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise GuardError(f"regular non-symlink JSON file required: {path}")
    try:
        payload, _ = _read_stable_bytes(path, maximum=maximum)
        return loads_json_strict(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GuardError(f"invalid JSON artifact: {path}") from exc


def _read_journal(state_dir: Path, run_id: str) -> dict[str, Any]:
    path = _journal_path(state_dir, run_id)
    value = _read_json(path, maximum=MAX_JOURNAL_BYTES)
    if not isinstance(value, dict) or set(value) != JOURNAL_KEYS:
        raise GuardError("run journal must contain exactly the journal schema fields")
    if not isinstance(value.get("schema_version"), str) or value["schema_version"] != JOURNAL_SCHEMA:
        raise GuardError("run journal schema is invalid")
    if not isinstance(value.get("run_id"), str) or value["run_id"] != run_id:
        raise GuardError("run journal run_id does not match")
    if not isinstance(value.get("state"), str) or value["state"] not in STATES:
        raise GuardError("run journal state is invalid")
    for key in ("created_at", "updated_at", "started_at", "run_timestamp"):
        _parse_timestamp(value.get(key))
    for key in ("profile_path", "seen_path", "timezone"):
        if (
            not isinstance(value.get(key), str)
            or not value[key]
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value[key])
        ):
            raise GuardError(f"run journal {key} is invalid")
    for key in ("profile_path", "seen_path"):
        if str(_absolute_without_following_links(Path(value[key]))) != value[key]:
            raise GuardError(f"run journal {key} is not a normalized safe path")
    for key in ("profile_sha256", "config_sha256", "owner_token_sha256"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", value[key]):
            raise GuardError(f"run journal {key} is invalid")
    for key in ("initial_seen_sha256", "digest_sha256", "seen_source_sha256", "expected_seen_sha256"):
        candidate = value.get(key)
        if candidate is not None and (not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{64}", candidate)):
            raise GuardError(f"run journal {key} is invalid")
    if not isinstance(value.get("initial_seen_exists"), bool):
        raise GuardError("run journal initial_seen_exists is invalid")
    if value["initial_seen_exists"] != (value["initial_seen_sha256"] is not None):
        raise GuardError("run journal initial seen existence/hash fields disagree")
    for key in ("digest_path", "seen_source_path"):
        candidate = value.get(key)
        if candidate is not None and (
            not isinstance(candidate, str)
            or not candidate
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in candidate)
        ):
            raise GuardError(f"run journal {key} is invalid")
        if candidate is not None and str(_absolute_without_following_links(Path(candidate))) != candidate:
            raise GuardError(f"run journal {key} is not a normalized safe path")
    for path_key, hash_key in (("digest_path", "digest_sha256"), ("seen_source_path", "seen_source_sha256")):
        if (value[path_key] is None) != (value[hash_key] is None):
            raise GuardError(f"run journal {path_key}/{hash_key} fields disagree")
    if (value["prepared_seen"] is None) != (value["expected_seen_sha256"] is None):
        raise GuardError("run journal prepared_seen/expected_seen_sha256 fields disagree")
    if not isinstance(value.get("config"), dict):
        raise GuardError("run journal config is invalid")
    config = value["config"]
    if set(config) != {"profile_path", "seen_path", "state_dir", "run_timestamp", "timezone", "budgets"}:
        raise GuardError("run journal config fields are invalid")
    for key in ("profile_path", "seen_path", "state_dir", "run_timestamp", "timezone"):
        if (
            not isinstance(config.get(key), str)
            or not config[key]
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in config[key])
        ):
            raise GuardError(f"run journal config {key} is invalid")
    for key in ("profile_path", "seen_path", "state_dir"):
        if str(_absolute_without_following_links(Path(config[key]))) != config[key]:
            raise GuardError(f"run journal config {key} is not a normalized safe path")
    if config["state_dir"] != str(_absolute_without_following_links(state_dir)):
        raise GuardError("run journal config state_dir does not match its journal location")
    _parse_timestamp(config["run_timestamp"])
    if config["profile_path"] != value["profile_path"] or config["seen_path"] != value["seen_path"]:
        raise GuardError("run journal config paths do not match snapshots")
    if config["run_timestamp"] != value["run_timestamp"] or config["timezone"] != value["timezone"]:
        raise GuardError("run journal config timestamps do not match snapshots")
    validate_run_budgets(config.get("budgets"))
    if config["budgets"] != value["budgets"]:
        raise GuardError("run journal config budgets do not match snapshots")
    expected_config_hash = _sha256_bytes(json.dumps(config, sort_keys=True).encode("utf-8"))
    if value["config_sha256"] != expected_config_hash:
        raise GuardError("run journal configuration hash is invalid")
    usage = value.get("budget_usage")
    if not isinstance(usage, dict) or set(usage) != USAGE_KEYS:
        raise GuardError("run journal budget usage fields are invalid")
    for key, candidate in usage.items():
        if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate < 0:
            raise GuardError(f"run journal budget usage {key} is invalid")
        limit_key = {
            "waves": "max_waves", "pages": "max_pages", "retries": "max_retries",
            "retries_per_job": "max_retries_per_job", "workers": "max_workers",
            "topic_shards": "max_topic_shards", "candidates": "max_candidates",
        }[key]
        if candidate > RUN_BUDGETS[limit_key]:
            raise GuardError(f"run journal budget usage {key} exceeds its fixed limit")
    events = value["events"]
    if not isinstance(events, list) or not events:
        raise GuardError("run journal events are invalid")
    for event in events:
        if not isinstance(event, dict) or set(event) - {"state", "at", "detail"} or set(event) < {"state", "at"}:
            raise GuardError("run journal event schema is invalid")
        if not isinstance(event["state"], str) or event["state"] not in STATES:
            raise GuardError("run journal event state is invalid")
        _parse_timestamp(event["at"])
        if "detail" in event and (
            not isinstance(event["detail"], str)
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in event["detail"])
        ):
            raise GuardError("run journal event detail is invalid")
    allowed_transitions = {
        "starting": {"started", "aborted"},
        "started": {"collecting", "digest-committed", "aborted"},
        "collecting": {"collecting", "digest-committed", "aborted"},
        "digest-committed": {"seen-prepared", "seen-committed", "aborted"},
        "seen-prepared": {"seen-committed", "aborted"},
        "seen-committed": set(),
        "aborted": set(),
    }
    previous_state: str | None = None
    previous_at: datetime | None = None
    for event in events:
        event_at = _parse_timestamp(event["at"])
        if previous_state is None:
            if event["state"] != "starting":
                raise GuardError("run journal event history must start at starting")
        elif event["state"] != previous_state and event["state"] not in allowed_transitions[previous_state]:
            raise GuardError("run journal event history contains an invalid transition")
        if previous_at is not None and event_at < previous_at:
            raise GuardError("run journal event timestamps must be monotonic")
        previous_state = event["state"]
        previous_at = event_at
    if events[-1]["state"] != value["state"]:
        raise GuardError("run journal state does not match its last event")
    if previous_at != _parse_timestamp(value["updated_at"]):
        raise GuardError("run journal updated_at does not match its last event")
    if value.get("prepared_seen") is not None and not isinstance(value["prepared_seen"], dict):
        raise GuardError("run journal prepared seen payload is invalid")
    if value.get("prepared_seen") is not None:
        _validate_seen_shape(value["prepared_seen"], allow_empty_timestamp=False)
    validate_run_budgets(value.get("budgets"))
    return value


def _write_journal(state_dir: Path, journal: dict[str, Any]) -> None:
    _atomic_write_json(_journal_path(state_dir, journal["run_id"]), journal)


def _read_lock(state_dir: Path) -> dict[str, Any]:
    lock_path = _lock_path(state_dir)
    value = _read_json(lock_path, maximum=64_000)
    if not isinstance(value, dict) or set(value) != LOCK_KEYS:
        raise GuardError("run lock schema is invalid")
    if value.get("schema_version") != LOCK_SCHEMA:
        raise GuardError("run lock schema is invalid")
    _safe_run_id(value.get("run_id"))
    if (
        not isinstance(value.get("owner_token"), str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", value["owner_token"])
    ):
        raise GuardError("run lock owner token is invalid")
    if not isinstance(value.get("pid"), int) or isinstance(value["pid"], bool) or value["pid"] <= 0:
        raise GuardError("run lock pid is invalid")
    if (
        not isinstance(value.get("host"), str)
        or not 1 <= len(value["host"]) <= 253
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value["host"])
    ):
        raise GuardError("run lock host is invalid")
    _parse_timestamp(value.get("created_at"))
    return value


def _acquire_lock(state_dir: Path, run_id: str, owner_token: str | None = None) -> str:
    state_dir = _absolute_without_following_links(state_dir)
    _absolute_without_following_links(state_dir.parent)
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path(state_dir)
    owner_token = owner_token or secrets.token_urlsafe(32)
    value = {
        "schema_version": LOCK_SCHEMA,
        "run_id": run_id,
        "owner_token": owner_token,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "created_at": _now_iso(),
    }
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    descriptor: int | None = None
    try:
        descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("run lock write made no progress")
            offset += written
        os.fsync(descriptor)
    except FileExistsError as exc:
        raise GuardError(f"another scheduled run already owns {lock_path}") from exc
    except OSError as exc:
        raise GuardError(f"could not acquire run lock: {lock_path}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return owner_token


def _release_lock(state_dir: Path, run_id: str, owner_token: str) -> None:
    lock_path = _lock_path(state_dir)
    lock = _read_lock(state_dir)
    if lock.get("run_id") != run_id or lock.get("owner_token") != owner_token:
        raise GuardError("run lock is not owned by this coordinator")
    try:
        lock_path.unlink()
    except FileNotFoundError as exc:
        raise GuardError("run lock disappeared before release") from exc


def _assert_owner(state_dir: Path, journal: dict[str, Any], owner_token: str) -> None:
    if not isinstance(owner_token, str) or len(owner_token) < 32:
        raise GuardError("owner token is required")
    lock = _read_lock(state_dir)
    if lock.get("run_id") != journal["run_id"] or lock.get("owner_token") != owner_token:
        raise GuardError("run lock is not owned by this coordinator")
    expected_hash = journal.get("owner_token_sha256")
    if expected_hash != _sha256_bytes(owner_token.encode("utf-8")):
        raise GuardError("owner token does not match the run journal")


def _event(journal: dict[str, Any], state: str, at: str, detail: str | None = None) -> None:
    event: dict[str, Any] = {"state": state, "at": at}
    if detail:
        event["detail"] = detail
    journal["events"].append(event)
    journal["state"] = state
    journal["updated_at"] = at


def _transition(journal: dict[str, Any], state: str, at: str, detail: str | None = None) -> None:
    current = journal["state"]
    allowed = {
        "starting": {"started", "aborted"},
        "started": {"collecting", "digest-committed", "aborted"},
        "collecting": {"collecting", "digest-committed", "aborted"},
        "digest-committed": {"seen-prepared", "seen-committed", "aborted"},
        "seen-prepared": {"seen-committed", "aborted"},
        "seen-committed": set(),
        "aborted": set(),
    }
    if state not in allowed.get(current, set()):
        raise GuardError(f"invalid run state transition: {current} -> {state}")
    _event(journal, state, at, detail)


def _validate_seen_shape(value: Any, *, allow_empty_timestamp: bool = True) -> None:
    if not isinstance(value, dict) or set(value) != {"schema_version", "updated_at", "items"}:
        raise GuardError("seen state must match news-seen/v1")
    if value.get("schema_version") != "news-seen/v1":
        raise GuardError("seen state schema is invalid")
    items = value.get("items")
    if not isinstance(items, list) or len(items) > 2_000:
        raise GuardError("seen state must contain at most 2000 items")
    updated_at = value.get("updated_at")
    if updated_at is None and allow_empty_timestamp and not items:
        return
    _parse_timestamp(updated_at)
    for item in items:
        if not isinstance(item, dict) or set(item) != {"url", "title_key", "first_seen_at"}:
            raise GuardError("seen state contains an invalid item")
        _public_seen_url(item.get("url"))
        title_key = item.get("title_key")
        if not isinstance(title_key, str) or not 1 <= len(title_key) <= 512:
            raise GuardError("seen state contains an invalid bounded title key")
        if any(ord(character) < 0x20 or ord(character) == 0x7F for character in title_key):
            raise GuardError("seen state contains control characters in title_key")
        _parse_timestamp(item.get("first_seen_at"))


def _snapshot_seen(path: Path) -> tuple[bool, str | None]:
    path = _absolute_without_following_links(path)
    if not path.exists():
        return False, None
    payload, digest = _read_stable_bytes(path, maximum=MAX_SEEN_BYTES)
    try:
        value = loads_json_strict(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GuardError(f"invalid JSON artifact: {path}") from exc
    _validate_seen_shape(value)
    return True, digest


def _snapshot_profile(path: Path) -> tuple[dict[str, Any], str]:
    path = _absolute_without_following_links(path)
    if not path.exists() or not path.is_file() or path.is_symlink():
        raise GuardError(f"regular non-symlink profile required: {path}")
    payload, digest = _read_stable_bytes(path, maximum=MAX_PROFILE_BYTES)
    try:
        value = loads_json_strict(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GuardError(f"invalid profile JSON: {path}") from exc
    if not isinstance(value, dict):
        raise GuardError("profile root must be an object")
    return value, digest


def _check_snapshots(journal: dict[str, Any], *, include_seen: bool = True) -> None:
    _check_profile_snapshot(journal)
    if include_seen:
        _check_seen_snapshot(journal)


def _check_profile_snapshot(journal: dict[str, Any]) -> None:
    profile_path = Path(journal["profile_path"])
    profile, current_profile = _snapshot_profile(profile_path)
    if current_profile != journal["profile_sha256"]:
        raise GuardError("profile changed after the run snapshot")
    errors = validate_profile(profile)
    if errors:
        raise GuardError("profile changed to an invalid profile: " + "; ".join(errors))


def _check_seen_snapshot(journal: dict[str, Any]) -> None:
    seen_path = Path(journal["seen_path"])
    exists, current_seen = _snapshot_seen(seen_path)
    if exists != journal["initial_seen_exists"] or current_seen != journal["initial_seen_sha256"]:
        raise GuardError("seen state changed after the run snapshot")


def _check_deadline(journal: dict[str, Any], now: str) -> None:
    elapsed = (_parse_timestamp(now) - _parse_timestamp(journal["started_at"])).total_seconds()
    if elapsed < 0:
        raise GuardError("scheduled run timestamp precedes its start timestamp")
    if elapsed >= RUN_BUDGETS["deadline_seconds"]:
        raise GuardError("scheduled run exceeded its fixed wall-clock deadline")


def _abort_locked(
    state_dir: Path,
    journal: dict[str, Any],
    owner_token: str,
    reason: str,
    now: str | None = None,
) -> dict[str, Any]:
    _assert_owner(state_dir, journal, owner_token)
    try:
        if journal["state"] not in TERMINAL_STATES:
            _transition(journal, "aborted", _now_iso(now), reason)
            _write_journal(state_dir, journal)
    finally:
        # Even if the journal filesystem is unhealthy, never leave an owner
        # lock behind when this coordinator has explicitly aborted its run.
        _release_lock(state_dir, journal["run_id"], owner_token)
    return journal


def _load_approved_profile(profile_path: Path) -> tuple[dict[str, Any], str]:
    profile, profile_sha256 = _snapshot_profile(profile_path)
    errors = validate_profile(profile)
    if errors:
        raise GuardError("invalid profile: " + "; ".join(errors))
    if profile["approval"]["status"] != "approved":
        raise GuardError("scheduled runs require an approved profile")
    return profile, profile_sha256


def start_run(
    *,
    profile_path: Path,
    seen_path: Path,
    state_dir: Path,
    run_id: str,
    run_timestamp: str | None = None,
    timezone_name: str = "UTC",
) -> tuple[dict[str, Any], str]:
    """Snapshot inputs and acquire the one-run lock."""

    run_id = _safe_run_id(run_id)
    profile_path = _absolute_without_following_links(profile_path)
    seen_path = _absolute_without_following_links(seen_path)
    state_dir = _absolute_without_following_links(state_dir)
    if not timezone_name or "\n" in timezone_name:
        raise GuardError("timezone name must be a non-empty single line")
    timestamp = _now_iso(run_timestamp)
    _, profile_sha256 = _load_approved_profile(profile_path)
    initial_seen_exists, initial_seen_sha256 = _snapshot_seen(seen_path)
    journal_path = _journal_path(state_dir, run_id)
    if journal_path.exists():
        raise GuardError(f"run journal already exists: {journal_path}")

    state_dir.mkdir(parents=True, exist_ok=True)
    owner_token = secrets.token_urlsafe(32)
    config = {
        "profile_path": str(profile_path),
        "seen_path": str(seen_path),
        "state_dir": str(state_dir),
        "run_timestamp": timestamp,
        "timezone": timezone_name,
        "budgets": copy_run_budgets(),
    }
    journal: dict[str, Any] = {
        "schema_version": JOURNAL_SCHEMA,
        "run_id": run_id,
        "state": "starting",
        "created_at": timestamp,
        "updated_at": timestamp,
        "started_at": timestamp,
        "run_timestamp": timestamp,
        "timezone": timezone_name,
        "profile_path": str(profile_path),
        "seen_path": str(seen_path),
        "profile_sha256": profile_sha256,
        "initial_seen_exists": initial_seen_exists,
        "initial_seen_sha256": initial_seen_sha256,
        "budgets": copy_run_budgets(),
        "budget_usage": {key: 0 for key in USAGE_KEYS},
        "config": config,
        "config_sha256": _sha256_bytes(json.dumps(config, sort_keys=True).encode("utf-8")),
        "owner_token_sha256": _sha256_bytes(owner_token.encode("utf-8")),
        "digest_path": None,
        "digest_sha256": None,
        "seen_source_path": None,
        "seen_source_sha256": None,
        "prepared_seen": None,
        "expected_seen_sha256": None,
        "events": [{"state": "starting", "at": timestamp}],
    }
    _write_journal(state_dir, journal)
    try:
        _acquire_lock(state_dir, run_id, owner_token)
        _transition(journal, "started", timestamp, "exclusive lock acquired")
        _write_journal(state_dir, journal)
    except Exception:
        try:
            if _lock_path(state_dir).exists():
                lock = _read_lock(state_dir)
                if lock.get("run_id") == run_id and lock.get("owner_token") == owner_token:
                    _release_lock(state_dir, run_id, owner_token)
            if journal_path.exists() and journal["state"] == "starting":
                journal_path.unlink()
        finally:
            raise
    return journal, owner_token


def record_progress(
    *,
    state_dir: Path,
    run_id: str,
    owner_token: str,
    waves: int,
    pages: int,
    retries: int,
    workers: int,
    retries_per_job: int = 0,
    topic_shards: int = 0,
    candidates: int = 0,
    now: str | None = None,
) -> dict[str, Any]:
    journal = _read_journal(state_dir, _safe_run_id(run_id))
    _assert_owner(state_dir, journal, owner_token)
    if journal["state"] in TERMINAL_STATES:
        raise GuardError(f"run is already {journal['state']}")
    usage = {
        "waves": waves,
        "pages": pages,
        "retries": retries,
        "retries_per_job": retries_per_job,
        "workers": workers,
        "topic_shards": topic_shards,
        "candidates": candidates,
    }
    current = _now_iso(now)
    try:
        for key, value in usage.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise GuardError(f"budget usage {key} must be a non-negative integer")
            limit_key = {
                "waves": "max_waves",
                "pages": "max_pages",
                "retries": "max_retries",
                "retries_per_job": "max_retries_per_job",
                "workers": "max_workers",
                "topic_shards": "max_topic_shards",
                "candidates": "max_candidates",
            }[key]
            if value > RUN_BUDGETS[limit_key]:
                raise GuardError(f"budget usage exceeds fixed {key} limit")
            if value < journal["budget_usage"][key]:
                raise GuardError(f"budget usage {key} cannot move backwards")
        _check_deadline(journal, current)
    except GuardError as exc:
        _abort_locked(state_dir, journal, owner_token, str(exc), current)
        raise
    journal["budget_usage"] = usage
    _transition(journal, "collecting", current, "bounded worker progress")
    _write_journal(state_dir, journal)
    return journal


def _validate_digest(path: Path) -> str:
    """Validate and hash one coordinator-owned Markdown digest snapshot."""

    path = _absolute_without_following_links(path)
    if path.suffix.casefold() != ".md":
        raise GuardError("digest output must be a Markdown .md file")
    payload, digest = _read_stable_bytes(path, maximum=MAX_DIGEST_BYTES)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GuardError("digest must be valid UTF-8 Markdown") from exc
    if not text.strip() or not text.lstrip().startswith("#"):
        raise GuardError("digest must contain a non-empty Markdown heading")
    if any(
        (ord(character) < 0x20 and character not in {"\n", "\r", "\t"})
        or ord(character) == 0x7F
        for character in text
    ):
        raise GuardError("digest contains NUL or other control characters")
    return digest


def _reject_artifact_aliases(
    journal: dict[str, Any], *, state_dir: Path, digest_path: Path, seen_source_path: Path
) -> None:
    """Reject path and hard-link aliases across the commit boundary."""

    paths = [
        ("profile", Path(journal["profile_path"])),
        ("seen", Path(journal["seen_path"])),
        ("digest", digest_path),
        ("seen-source", seen_source_path),
        ("state-dir", state_dir),
        ("journal", _journal_path(state_dir, journal["run_id"])),
        ("lock", _lock_path(state_dir)),
    ]
    normalized = [(label, _absolute_without_following_links(path)) for label, path in paths]
    for index, (left_label, left) in enumerate(normalized):
        for right_label, right in normalized[index + 1 :]:
            if left == right:
                raise GuardError(f"{left_label} and {right_label} paths must be distinct")
            if not left.exists() or not right.exists():
                continue
            try:
                aliased = os.path.samefile(left, right)
            except OSError as exc:
                raise GuardError(f"could not establish distinct artifact identity: {left}") from exc
            if aliased:
                raise GuardError(f"{left_label} and {right_label} artifacts must not be hard-link aliases")


def mark_digest_committed(
    *,
    state_dir: Path,
    run_id: str,
    owner_token: str,
    digest_path: Path,
    seen_source_path: Path,
    now: str | None = None,
) -> dict[str, Any]:
    """Record an already atomically-written digest, but do not touch seen state."""

    journal = _read_journal(state_dir, _safe_run_id(run_id))
    _assert_owner(state_dir, journal, owner_token)
    if journal["state"] == "digest-committed":
        current = _now_iso(now)
        try:
            _check_deadline(journal, current)
            _check_snapshots(journal, include_seen=True)
            _recheck_commit_inputs(journal)
            if _absolute_without_following_links(digest_path) != _absolute_without_following_links(Path(journal["digest_path"])):
                raise GuardError("a different digest is already recorded for this run")
            return journal
        except GuardError as exc:
            _abort_locked(state_dir, journal, owner_token, str(exc), current)
            raise
    if journal["state"] not in {"started", "collecting"}:
        raise GuardError(f"cannot commit digest from state {journal['state']}")
    current = _now_iso(now)
    try:
        _check_deadline(journal, current)
        _check_snapshots(journal, include_seen=True)
        digest_path = _absolute_without_following_links(digest_path)
        seen_source_path = _absolute_without_following_links(seen_source_path)
        _reject_artifact_aliases(
            journal,
            state_dir=state_dir,
            digest_path=digest_path,
            seen_source_path=seen_source_path,
        )
        digest_sha256 = _validate_digest(digest_path)
        if not seen_source_path.exists() or not seen_source_path.is_file() or seen_source_path.is_symlink():
            raise GuardError("seen source must be a regular non-symlink JSON file")
        _, seen_source_sha256 = _load_seen_candidates_with_hash(seen_source_path, journal["run_timestamp"])
    except GuardError as exc:
        _abort_locked(state_dir, journal, owner_token, str(exc), current)
        raise
    journal["digest_path"] = str(digest_path)
    journal["digest_sha256"] = digest_sha256
    journal["seen_source_path"] = str(seen_source_path)
    journal["seen_source_sha256"] = seen_source_sha256
    _transition(journal, "digest-committed", current, "digest exists before seen commit")
    _write_journal(state_dir, journal)
    return journal


def _public_seen_url(value: Any) -> str:
    if not isinstance(value, str):
        raise GuardError("seen item URL must be a string")
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise GuardError("seen item URL is invalid") from exc
    try:
        port = parts.port
    except ValueError as exc:
        raise GuardError("seen item URL has an invalid port") from exc
    if parts.scheme.lower() != "https" or not parts.hostname or parts.username or parts.password:
        raise GuardError("seen item URL must be a public HTTPS URL")
    if port is not None:
        raise GuardError("seen item URL must not contain an explicit port")
    if parts.query or parts.fragment or parts.path in {"", "/"}:
        raise GuardError("seen item URL must be canonical and query-free")
    try:
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise GuardError("seen item URL hostname is invalid") from exc
    if host in RESERVED_HOSTS or host.endswith(PRIVATE_HOST_SUFFIXES):
        raise GuardError("seen item URL hostname is private or reserved")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise GuardError("seen item URL must not use an IP-literal host")
    labels = host.split(".")
    if len(labels) < 2 or len(host) > 253 or any(not DNS_LABEL_RE.fullmatch(label) for label in labels):
        raise GuardError("seen item URL hostname is not a public DNS name")
    return value


def _load_seen_candidates_with_hash(path: Path, run_timestamp: str) -> tuple[list[dict[str, str]], str]:
    path = _absolute_without_following_links(path)
    payload, source_sha256 = _read_stable_bytes(path, maximum=MAX_SEEN_BYTES)
    try:
        value = loads_json_strict(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GuardError(f"invalid JSON artifact: {path}") from exc
    if isinstance(value, dict) and set(value) == {"items"}:
        raw_items = value["items"]
    elif isinstance(value, list):
        raw_items = value
    else:
        raise GuardError("seen source must be an array or an object containing only items")
    if not isinstance(raw_items, list) or len(raw_items) > 500:
        raise GuardError("seen source must contain at most 500 selected items")
    projected: list[dict[str, str]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise GuardError("seen source contains a non-object item")
        url = raw.get("canonical_url", raw.get("url"))
        title_key = raw.get("title_key")
        if not isinstance(title_key, str) or not 1 <= len(title_key) <= 512:
            raise GuardError("seen source item requires a bounded title_key")
        if any(ord(character) < 0x20 or ord(character) == 0x7F for character in title_key):
            raise GuardError("seen source title_key contains control characters")
        projected.append({"url": _public_seen_url(url), "title_key": title_key, "first_seen_at": run_timestamp})
    return projected, source_sha256


def _load_seen_candidates(path: Path, run_timestamp: str) -> list[dict[str, str]]:
    projected, _ = _load_seen_candidates_with_hash(path, run_timestamp)
    return projected


def _prepare_seen(journal: dict[str, Any]) -> dict[str, Any]:
    seen_path = Path(journal["seen_path"])
    if seen_path.exists():
        existing = _read_json(seen_path, maximum=MAX_SEEN_BYTES)
        _validate_seen_shape(existing)
    else:
        existing = {"schema_version": "news-seen/v1", "updated_at": None, "items": []}
    source_path = journal.get("seen_source_path")
    if not isinstance(source_path, str):
        raise GuardError("journal has no seen source")
    additions, source_sha256 = _load_seen_candidates_with_hash(Path(source_path), journal["run_timestamp"])
    if source_sha256 != journal.get("seen_source_sha256"):
        raise GuardError("seen source changed after digest commit")
    combined = list(existing["items"]) + additions
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for item in combined:
        key = (item["url"], item["title_key"])
        unique[key] = item
    items = list(unique.values())[-2_000:]
    prepared = {"schema_version": "news-seen/v1", "updated_at": journal["run_timestamp"], "items": items}
    _validate_seen_shape(prepared, allow_empty_timestamp=False)
    return prepared


def _recheck_commit_inputs(journal: dict[str, Any]) -> None:
    """Re-hash the digest and selected-source bytes at the commit boundary."""

    digest_path = journal.get("digest_path")
    digest_sha256 = journal.get("digest_sha256")
    source_path = journal.get("seen_source_path")
    source_sha256 = journal.get("seen_source_sha256")
    if not all(isinstance(value, str) for value in (digest_path, digest_sha256, source_path, source_sha256)):
        raise GuardError("journal has incomplete commit inputs")
    state_dir = Path(journal["config"]["state_dir"])
    _reject_artifact_aliases(
        journal,
        state_dir=state_dir,
        digest_path=Path(digest_path),
        seen_source_path=Path(source_path),
    )
    if _validate_digest(Path(digest_path)) != digest_sha256:
        raise GuardError("digest changed or disappeared before seen commit")
    _, current_source_sha256 = _load_seen_candidates_with_hash(
        Path(source_path), journal["run_timestamp"]
    )
    if current_source_sha256 != source_sha256:
        raise GuardError("seen source changed after digest commit")


def _commit_prepared_seen(state_dir: Path, journal: dict[str, Any], owner_token: str, now: str) -> dict[str, Any]:
    _assert_owner(state_dir, journal, owner_token)
    _check_deadline(journal, now)
    # Recheck the approved profile immediately before either the first seen
    # preparation or a crash-recovery commit.  A seen-prepared journal may be
    # resumed after the profile changed, so checking only in the
    # digest-committed branch is insufficient.
    _check_profile_snapshot(journal)
    digest_path = journal.get("digest_path")
    digest_sha256 = journal.get("digest_sha256")
    if not isinstance(digest_path, str) or not isinstance(digest_sha256, str):
        raise GuardError("journal has no committed digest")
    if _validate_digest(Path(digest_path)) != digest_sha256:
        raise GuardError("digest changed or disappeared before seen commit")
    if journal["state"] == "digest-committed":
        _check_snapshots(journal, include_seen=True)
        prepared = _prepare_seen(journal)
        encoded = (json.dumps(prepared, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(encoded) > MAX_SEEN_BYTES:
            raise GuardError("prepared seen state exceeds the 5 MB safety limit")
        journal["prepared_seen"] = prepared
        journal["expected_seen_sha256"] = _sha256_bytes(encoded)
        _transition(journal, "seen-prepared", now, "seen payload prepared after digest commit")
        _write_journal(state_dir, journal)
    if journal["state"] != "seen-prepared":
        if journal["state"] == "seen-committed":
            return journal
        raise GuardError(f"cannot commit seen state from {journal['state']}")
    prepared = journal.get("prepared_seen")
    if not isinstance(prepared, dict):
        raise GuardError("journal has no prepared seen payload")
    # The source and digest are re-read after the journaled preparation and
    # immediately before the seen hash check/write.  This closes the gap where
    # either artifact could change after the first preflight hash.
    _recheck_commit_inputs(journal)
    # Repeat the profile check after the durable seen-prepared transition and
    # after the digest/source recheck.  The current seen hash below is the
    # immediate initial-seen (or exact prepared-payload) snapshot check.
    _check_profile_snapshot(journal)
    # A second coordinator must not overwrite a changed seen file.  The only
    # accepted pre-write hashes are the original snapshot or the exact
    # prepared payload (the latter makes a crash after replace idempotent).
    seen_path = Path(journal["seen_path"])
    current_seen = _sha256_file(seen_path, maximum=MAX_SEEN_BYTES) if seen_path.exists() else None
    expected = journal.get("expected_seen_sha256")
    if current_seen == expected:
        _transition(journal, "seen-committed", now, "seen state was already committed")
        _write_journal(state_dir, journal)
        _release_lock(state_dir, journal["run_id"], owner_token)
        return journal
    if current_seen != journal.get("initial_seen_sha256"):
        raise GuardError("seen state changed after the initial snapshot")
    _atomic_write_json(Path(journal["seen_path"]), prepared, maximum=MAX_SEEN_BYTES)
    actual = _sha256_file(Path(journal["seen_path"]), maximum=MAX_SEEN_BYTES)
    if actual != expected:
        raise GuardError("seen state hash after commit does not match the prepared payload")
    _transition(journal, "seen-committed", now, "seen state committed idempotently")
    _write_journal(state_dir, journal)
    _release_lock(state_dir, journal["run_id"], owner_token)
    return journal


def commit_seen_state(
    *, state_dir: Path, run_id: str, owner_token: str, now: str | None = None
) -> dict[str, Any]:
    journal = _read_journal(state_dir, _safe_run_id(run_id))
    try:
        return _commit_prepared_seen(state_dir, journal, owner_token, _now_iso(now))
    except GuardError as exc:
        if journal["state"] not in TERMINAL_STATES:
            try:
                _abort_locked(state_dir, journal, owner_token, str(exc), _now_iso(now))
            except GuardError:
                pass
        raise


def commit_run(
    *,
    state_dir: Path,
    run_id: str,
    owner_token: str,
    digest_path: Path,
    seen_source_path: Path,
    now: str | None = None,
) -> dict[str, Any]:
    """Transactional convenience path: digest marker, then seen commit.

    The two phases remain journaled separately so a process crash between them
    can be resumed by ``recover --resume`` without duplicating seen entries.
    """

    mark_digest_committed(
        state_dir=state_dir,
        run_id=run_id,
        owner_token=owner_token,
        digest_path=digest_path,
        seen_source_path=seen_source_path,
        now=now,
    )
    return commit_seen_state(
        state_dir=state_dir,
        run_id=run_id,
        owner_token=owner_token,
        now=now,
    )


def abort_run(
    *, state_dir: Path, run_id: str, owner_token: str, reason: str, now: str | None = None
) -> dict[str, Any]:
    journal = _read_journal(state_dir, _safe_run_id(run_id))
    if journal["state"] == "seen-committed":
        raise GuardError("a seen-committed run cannot be aborted")
    if journal["state"] == "aborted":
        if _lock_path(state_dir).exists():
            return _abort_locked(state_dir, journal, owner_token, "release stale aborted-run lock", now)
        return journal
    return _abort_locked(state_dir, journal, owner_token, reason, now)


def _pid_alive(pid: int) -> bool:
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except PermissionError:
        # Permission denied means the process may exist; recovery must prove
        # death rather than reclaim a lock optimistically.
        return True
    except (OSError, ProcessLookupError):
        return False
    return True


def recover_run(
    *, state_dir: Path, run_id: str, resume: bool = False, now: str | None = None
) -> dict[str, Any]:
    """Recover a crashed run after proving its previous owner is not alive."""

    run_id = _safe_run_id(run_id)
    journal_path = _journal_path(state_dir, run_id)
    try:
        journal = _read_journal(state_dir, run_id)
    except GuardError:
        # The coordinator writes the journal before acquiring the lock, but a
        # hard crash can still leave a lock-only orphan from an older runner or
        # from the tiny O_EXCL/write window.  Reclaim it only when its journal
        # is absent, its run id matches, its host is this host, and its PID is
        # provably dead.  A malformed journal or a live/remote lock remains a
        # fail-closed error.
        if journal_path.exists():
            raise
        lock_path = _lock_path(state_dir)
        if not lock_path.exists():
            raise
        lock = _read_lock(state_dir)
        if lock["run_id"] != run_id:
            raise GuardError("orphan run lock belongs to a different run")
        if lock["host"] != socket.gethostname():
            raise GuardError("cannot recover an orphan lock owned on another host")
        if _pid_alive(lock["pid"]):
            raise GuardError("cannot recover an orphan lock while its owner is alive")
        lock_path.unlink()
        return {"run_id": run_id, "state": "aborted", "orphan_lock_recovered": True}
    if journal["state"] == "seen-committed":
        lock_path = _lock_path(state_dir)
        if lock_path.exists():
            lock = _read_lock(state_dir)
            if lock["run_id"] != run_id:
                raise GuardError("run lock belongs to a different run")
            if lock["host"] != socket.gethostname():
                raise GuardError("cannot recover a lock owned on another host")
            if _pid_alive(lock["pid"]):
                raise GuardError("completed run still has a live lock owner")
            lock_path.unlink()
        return journal
    lock_path = _lock_path(state_dir)
    if lock_path.exists():
        lock = _read_lock(state_dir)
        if lock["run_id"] != run_id:
            raise GuardError("run lock belongs to a different run")
        if lock["host"] != socket.gethostname():
            raise GuardError("cannot recover a lock owned on another host")
        if _pid_alive(lock["pid"]):
            raise GuardError("cannot recover while the recorded lock owner is alive")
        lock_path.unlink()
    if not resume or journal["state"] not in {"digest-committed", "seen-prepared"}:
        if journal["state"] not in TERMINAL_STATES:
            _transition(journal, "aborted", _now_iso(now), "recovered without resuming; no seen mutation")
            _write_journal(state_dir, journal)
        return journal

    owner_token = _acquire_lock(state_dir, run_id)
    try:
        journal = _read_journal(state_dir, run_id)
        current = _now_iso(now)
        journal["owner_token_sha256"] = _sha256_bytes(owner_token.encode("utf-8"))
        _event(journal, journal["state"], current, "recovery owner claimed after stale lock")
        _write_journal(state_dir, journal)
        if journal["state"] == "seen-prepared":
            _check_deadline(journal, current)
            _recheck_commit_inputs(journal)
            _check_profile_snapshot(journal)
            current_hash = None
            if Path(journal["seen_path"]).exists():
                current_hash = _sha256_file(Path(journal["seen_path"]), maximum=MAX_SEEN_BYTES)
            if current_hash == journal.get("expected_seen_sha256"):
                _transition(journal, "seen-committed", current, "recovered completed seen commit")
                _write_journal(state_dir, journal)
                _release_lock(state_dir, run_id, owner_token)
                return journal
            if current_hash != journal.get("initial_seen_sha256"):
                raise GuardError("seen state conflicts with both initial and prepared hashes")
        return _commit_prepared_seen(state_dir, journal, owner_token, current)
    except GuardError as exc:
        try:
            journal = _read_journal(state_dir, run_id)
            if journal["state"] not in TERMINAL_STATES:
                _transition(journal, "aborted", _now_iso(now), str(exc))
                _write_journal(state_dir, journal)
        finally:
            try:
                _release_lock(state_dir, run_id, owner_token)
            except GuardError:
                pass
        raise
    except Exception:
        try:
            _release_lock(state_dir, run_id, owner_token)
        except GuardError:
            pass
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--profile", type=Path, required=True)
    start.add_argument("--seen", type=Path, required=True)
    start.add_argument("--state-dir", type=Path, required=True)
    start.add_argument("--run-id", default=f"run-{secrets.token_hex(8)}")
    start.add_argument("--run-timestamp")
    start.add_argument("--timezone", default="UTC")

    progress = sub.add_parser("progress")
    progress.add_argument("--state-dir", type=Path, required=True)
    progress.add_argument("--run-id", required=True)
    progress.add_argument("--owner-token", required=True)
    for key in ("waves", "pages", "retries", "workers"):
        progress.add_argument(f"--{key}", type=int, required=True)
    progress.add_argument("--retries-per-job", type=int, default=0)
    progress.add_argument("--topic-shards", type=int, default=0)
    progress.add_argument("--candidates", type=int, default=0)
    progress.add_argument("--now")

    mark = sub.add_parser("mark-digest")
    mark.add_argument("--state-dir", type=Path, required=True)
    mark.add_argument("--run-id", required=True)
    mark.add_argument("--owner-token", required=True)
    mark.add_argument("--digest", type=Path, required=True)
    mark.add_argument("--seen-source", type=Path, required=True)
    mark.add_argument("--now")

    commit = sub.add_parser("commit-seen")
    commit.add_argument("--state-dir", type=Path, required=True)
    commit.add_argument("--run-id", required=True)
    commit.add_argument("--owner-token", required=True)
    commit.add_argument("--now")

    transaction = sub.add_parser("commit")
    transaction.add_argument("--state-dir", type=Path, required=True)
    transaction.add_argument("--run-id", required=True)
    transaction.add_argument("--owner-token", required=True)
    transaction.add_argument("--digest", type=Path, required=True)
    transaction.add_argument("--seen-source", type=Path, required=True)
    transaction.add_argument("--now")

    abort = sub.add_parser("abort")
    abort.add_argument("--state-dir", type=Path, required=True)
    abort.add_argument("--run-id", required=True)
    abort.add_argument("--owner-token", required=True)
    abort.add_argument("--reason", required=True)
    abort.add_argument("--now")

    recover = sub.add_parser("recover")
    recover.add_argument("--state-dir", type=Path, required=True)
    recover.add_argument("--run-id", required=True)
    recover.add_argument("--resume", action="store_true")
    recover.add_argument("--now")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "start":
            journal, owner_token = start_run(
                profile_path=args.profile,
                seen_path=args.seen,
                state_dir=args.state_dir,
                run_id=args.run_id,
                run_timestamp=args.run_timestamp,
                timezone_name=args.timezone,
            )
            print(json.dumps({"run_id": journal["run_id"], "owner_token": owner_token, "state": journal["state"]}))
        elif args.command == "progress":
            journal = record_progress(
                state_dir=args.state_dir,
                run_id=args.run_id,
                owner_token=args.owner_token,
                waves=args.waves,
                pages=args.pages,
                retries=args.retries,
                workers=args.workers,
                retries_per_job=args.retries_per_job,
                topic_shards=args.topic_shards,
                candidates=args.candidates,
                now=args.now,
            )
            print(f"PROGRESS: {journal['run_id']} {journal['budget_usage']}")
        elif args.command == "mark-digest":
            journal = mark_digest_committed(
                state_dir=args.state_dir,
                run_id=args.run_id,
                owner_token=args.owner_token,
                digest_path=args.digest,
                seen_source_path=args.seen_source,
                now=args.now,
            )
            print(f"DIGEST-COMMITTED: {journal['run_id']}")
        elif args.command == "commit-seen":
            journal = commit_seen_state(
                state_dir=args.state_dir,
                run_id=args.run_id,
                owner_token=args.owner_token,
                now=args.now,
            )
            print(f"SEEN-COMMITTED: {journal['run_id']}")
        elif args.command == "commit":
            journal = commit_run(
                state_dir=args.state_dir,
                run_id=args.run_id,
                owner_token=args.owner_token,
                digest_path=args.digest,
                seen_source_path=args.seen_source,
                now=args.now,
            )
            print(f"SEEN-COMMITTED: {journal['run_id']}")
        elif args.command == "abort":
            journal = abort_run(
                state_dir=args.state_dir,
                run_id=args.run_id,
                owner_token=args.owner_token,
                reason=args.reason,
                now=args.now,
            )
            print(f"ABORTED: {journal['run_id']}")
        elif args.command == "recover":
            journal = recover_run(
                state_dir=args.state_dir,
                run_id=args.run_id,
                resume=args.resume,
                now=args.now,
            )
            print(f"RECOVERED: {journal['run_id']} {journal['state']}")
        else:  # pragma: no cover - argparse enforces this
            raise GuardError("unknown command")
    except (OSError, json.JSONDecodeError, GuardError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
