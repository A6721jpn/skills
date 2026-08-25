#!/usr/bin/env python3
"""Deterministically rank, deduplicate, and optionally mark news candidates seen."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from validate_profile import load_json_strict, public_text_safety_error, validate_profile


QUALITY = {"primary": 1.0, "specialist": 0.88, "reputable": 0.82, "other": 0.5}
ALLOWED_CANDIDATE_FIELDS = {
    "title",
    "url",
    "source",
    "published_at",
    "event_at",
    "interest_ids",
    "source_quality",
    "summary",
}
PRIVATE_HOST_SUFFIXES = (".internal", ".local", ".lan", ".corp", ".home", ".localhost", ".invalid", ".test", ".example")
DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)
LEGACY_IP_LABEL_RE = re.compile(r"^(?:\d+|0x[0-9a-f]+)$", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
ABSOLUTE_PATH_RE = re.compile(r"(?:\b[A-Za-z]:[\\/]|\\\\[^\\\s]+\\[^\\\s]+|(?:^|\s)/(?:Users|home|var|tmp)/)")
BIDI_CONTROL_RE = re.compile(r"[\u200b\u200e\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]")
FORBIDDEN_CANDIDATE_TEXT_RE = re.compile(
    r"(?:https?://|file://|chrome://|\blocalhost\b|(?:\.internal|\.local|\.lan|\.corp|\.home|\.localhost)\b)",
    re.I,
)
MULTI_LABEL_PUBLIC_SUFFIXES = {
    "ac.jp",
    "co.jp",
    "go.jp",
    "ne.jp",
    "or.jp",
    "co.uk",
    "org.uk",
    "com.au",
    "net.au",
    "com.br",
    "com.cn",
    "com.sg",
}


def read_json(path: Path) -> Any:
    return load_json_strict(path)


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(path)


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def canonicalize_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    try:
        host_value = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() != "https" or not host_value or parts.username is not None or parts.password is not None:
        return None
    if "%" in host_value or any(character.isspace() for character in host_value):
        return None
    try:
        host = host_value.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError:
        return None
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if (
        len(host) > 253
        or len(labels) < 2
        or not re.search(r"[a-z]", labels[-1], re.I)
        or any(not DNS_LABEL_RE.fullmatch(label) for label in labels)
    ):
        return None
    if all(LEGACY_IP_LABEL_RE.fullmatch(label) for label in labels):
        return None
    if host == "localhost" or host.endswith(PRIVATE_HOST_SUFFIXES):
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None
    if port not in {None, 443}:
        return None
    netloc = host
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    if path == "/" or parts.query:
        return None
    return urlunsplit(("https", netloc, path, "", ""))


def hostname(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def domain_bucket(host: str) -> str:
    """Approximate registrable domain for source-diversity accounting."""
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    labels = [label for label in host.split(".") if label]
    if len(labels) <= 2:
        return host
    suffix = ".".join(labels[-2:])
    if suffix in MULTI_LABEL_PUBLIC_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return suffix


def title_key(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(ch for ch in normalized if ch.isalnum())


def public_candidate_text(value: Any, *, maximum: int) -> bool:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        return False
    if any(ord(character) < 32 for character in value) or BIDI_CONTROL_RE.search(value):
        return False
    if EMAIL_RE.search(value) or ABSOLUTE_PATH_RE.search(value) or FORBIDDEN_CANDIDATE_TEXT_RE.search(value):
        return False
    shared_issue = public_text_safety_error(value)
    if shared_issue:
        return False
    return True


def reject_path_collisions(paths: dict[str, Path | None]) -> None:
    """Fail before writes when two logical artifacts alias the same path/file."""

    present = [(name, path) for name, path in paths.items() if path is not None]
    normalized: dict[str, str] = {}
    for name, path in present:
        assert path is not None
        normalized[name] = os.path.normcase(str(path.resolve(strict=False)))
    for index, (left_name, left_path) in enumerate(present):
        assert left_path is not None
        for right_name, right_path in present[index + 1 :]:
            assert right_path is not None
            aliased = normalized[left_name] == normalized[right_name]
            if not aliased and left_path.exists() and right_path.exists():
                try:
                    aliased = os.path.samefile(left_path, right_path)
                except OSError:
                    aliased = False
            if aliased:
                raise ValueError(f"{left_name} and {right_name} paths must be distinct")


def domain_blocked(host: str, excluded: set[str]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in excluded)


def load_seen(path: Path | None) -> tuple[set[str], set[str], list[dict[str, Any]]]:
    if path is None or not path.exists():
        return set(), set(), []
    raw = read_json(path)
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "updated_at", "items"}:
        raise ValueError("seen state must match news-seen/v1")
    if raw.get("schema_version") != "news-seen/v1":
        raise ValueError("seen state metadata is invalid")
    items = raw.get("items")
    if not isinstance(items, list) or len(items) > 2000:
        raise ValueError("seen state must contain at most 2000 items")
    if not (raw.get("updated_at") is None and not items) and parse_timestamp(raw.get("updated_at")) is None:
        raise ValueError("seen state metadata is invalid")
    urls: set[str] = set()
    titles: set[str] = set()
    valid_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"url", "title_key", "first_seen_at"}:
            raise ValueError("seen state contains an invalid item")
        url = canonicalize_url(item.get("url"))
        key = item.get("title_key") if isinstance(item.get("title_key"), str) else ""
        if parse_timestamp(item.get("first_seen_at")) is None or (not url and not key):
            raise ValueError("seen state contains invalid item values")
        if url:
            urls.add(url)
        if key:
            titles.add(key)
        valid_items.append({"url": url, "title_key": key, "first_seen_at": item.get("first_seen_at")})
    return urls, titles, valid_items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--seen", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--now", help="ISO-8601 timestamp; required for reproducible runs")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--lookback-hours", type=int)
    parser.add_argument("--max-per-domain", type=int)
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--update-seen", action="store_true")
    args = parser.parse_args()

    try:
        reject_path_collisions(
            {
                "profile": args.profile,
                "candidates": args.candidates,
                "seen": args.seen,
                "output": args.output,
            }
        )
        if args.update_seen and args.seen is None:
            raise ValueError("--update-seen requires --seen")
        if args.profile.stat().st_size > 2_000_000:
            raise ValueError("profile exceeds the 2 MB safety limit")
        if args.candidates.stat().st_size > 5_000_000:
            raise ValueError("candidate input exceeds the 5 MB safety limit")
        if args.seen is not None and args.seen.exists() and args.seen.stat().st_size > 5_000_000:
            raise ValueError("seen state exceeds the 5 MB safety limit")
        profile = read_json(args.profile)
        profile_errors = validate_profile(profile)
        if profile_errors:
            raise ValueError("invalid profile: " + "; ".join(profile_errors))
        approval = profile["approval"]["status"]
        if approval != "approved" and not args.allow_draft:
            raise ValueError("draft profile requires --allow-draft and must not update seen state")
        if approval != "approved" and args.update_seen:
            raise ValueError("cannot update seen state from a draft profile")

        raw_candidates = read_json(args.candidates)
        if isinstance(raw_candidates, dict) and set(raw_candidates) != {"items"}:
            raise ValueError("candidate wrapper must contain only items")
        candidates = raw_candidates.get("items", []) if isinstance(raw_candidates, dict) else raw_candidates
        if not isinstance(candidates, list):
            raise ValueError("candidates must be a JSON array or an object with items")
        if len(candidates) > 500:
            raise ValueError("candidate input exceeds the 500-item safety limit")

        defaults = profile["digest_defaults"]
        limit = args.limit if args.limit is not None else defaults["max_items"]
        lookback_hours = args.lookback_hours if args.lookback_hours is not None else defaults["lookback_hours"]
        max_per_domain = args.max_per_domain if args.max_per_domain is not None else defaults["max_per_domain"]
        if min(limit, lookback_hours, max_per_domain) <= 0:
            raise ValueError("limit, lookback-hours, and max-per-domain must be positive")

        now = parse_timestamp(args.now) if args.now else datetime.now(timezone.utc)
        if now is None:
            raise ValueError("--now must be timezone-aware ISO-8601")
        profile_generated = parse_timestamp(profile.get("generated_at"))
        if profile_generated is None:
            raise ValueError("profile generated_at is invalid")
        profile_age_seconds = (now - profile_generated).total_seconds()
        if profile_age_seconds < -300:
            raise ValueError("profile generated_at is materially in the future")
        profile_stale = profile_age_seconds > 90 * 24 * 3600
        if approval == "approved":
            approved_at = parse_timestamp(profile.get("approval", {}).get("approved_at"))
            if approved_at is None or (now - approved_at).total_seconds() < -300:
                raise ValueError("profile approval timestamp is invalid for this run")

        topic_map = {
            topic["id"]: topic
            for topic in profile["topics"]
            if topic.get("news_eligible") is True and topic.get("user_confirmed") is not False
        }
        exclusions = profile.get("exclusions", {})
        excluded_topic_ids = set(exclusions.get("topic_ids", []))
        excluded_domains = {str(x).casefold().removeprefix("www.") for x in exclusions.get("domains", [])}
        excluded_terms = [str(x).casefold() for x in exclusions.get("terms", []) if str(x).strip()]
        seen_urls, seen_titles, previous_seen_items = load_seen(args.seen)

        rejection_counts: Counter[str] = Counter()
        sanitization_counts: Counter[str] = Counter()
        scored: list[dict[str, Any]] = []
        for item in candidates:
            if not isinstance(item, dict):
                rejection_counts["invalid_candidate"] += 1
                continue
            if any(key not in ALLOWED_CANDIDATE_FIELDS for key in item):
                sanitization_counts["candidates_with_extra_fields_stripped"] += 1
            raw_url = item.get("url")
            url = canonicalize_url(raw_url)
            key = title_key(item.get("title"))
            published = parse_timestamp(item.get("published_at"))
            event_at = parse_timestamp(item.get("event_at")) if "event_at" in item else None
            interest_ids = item.get("interest_ids")
            if (
                not url
                or len(key) < 8
                or published is None
                or ("event_at" in item and event_at is None)
                or not isinstance(interest_ids, list)
                or len(interest_ids) > 16
                or not public_candidate_text(item.get("title"), maximum=500)
                or not public_candidate_text(item.get("source"), maximum=200)
                or not public_candidate_text(item.get("summary"), maximum=2000)
            ):
                rejection_counts["invalid_candidate"] += 1
                continue
            host = hostname(url)
            if domain_blocked(host, excluded_domains):
                rejection_counts["excluded_domain"] += 1
                continue
            searchable = f"{item.get('title', '')} {item.get('summary', '')}".casefold()
            if any(term in searchable for term in excluded_terms):
                rejection_counts["excluded_term"] += 1
                continue
            valid_topic_ids = sorted(set(
                topic_id
                for topic_id in interest_ids
                if isinstance(topic_id, str)
                and topic_id in topic_map
                and topic_id not in excluded_topic_ids
            ))
            if not valid_topic_ids:
                rejection_counts["no_valid_topic"] += 1
                continue
            age_hours = (now - published).total_seconds() / 3600
            if age_hours < 0:
                rejection_counts["future_dated"] += 1
                continue
            if age_hours > lookback_hours:
                rejection_counts["stale"] += 1
                continue
            if event_at is not None:
                event_offset_days = (event_at - published).total_seconds() / 86_400
                if abs(event_offset_days) > 366 or (event_at - now).total_seconds() > 366 * 86_400:
                    rejection_counts["implausible_event_date"] += 1
                    continue
            if url in seen_urls or key in seen_titles:
                rejection_counts["seen"] += 1
                continue
            quality_name = item.get("source_quality")
            if quality_name not in QUALITY:
                rejection_counts["invalid_source_quality"] += 1
                continue

            topics = [topic_map[topic_id] for topic_id in valid_topic_ids]
            if profile["schema_version"] == "interest-profile/v2":
                topic_scores = []
                for topic in topics:
                    horizon = topic["horizon"]
                    intent_scores = topic["intent_scores"]
                    base = (
                        0.45 * float(topic["weight"])
                        + 0.25 * float(topic["confidence"])
                        + 0.20 * float(horizon["long_score"])
                        + 0.10 * float(horizon["short_score"])
                    )
                    gate = 1.0 if topic.get("user_confirmed") is True else max(
                        0.35,
                        min(1.0, 1 - 0.35 * float(intent_scores["work_like"]) - 0.40 * float(intent_scores["transient"])),
                    )
                    topic_scores.append(base * gate)
                interest_score = max(topic_scores)
            else:
                max_weight = max(float(topic["weight"]) for topic in topics)
                mean_confidence = sum(float(topic["confidence"]) for topic in topics) / len(topics)
                interest_score = 0.7 * max_weight + 0.3 * mean_confidence
            freshness_score = max(0.0, min(1.0, 1.0 - max(age_hours, 0.0) / lookback_hours))
            quality_score = QUALITY[quality_name]
            total_score = 0.58 * interest_score + 0.24 * freshness_score + 0.18 * quality_score
            enriched = {
                "title": item["title"],
                "url": url,
                "source": item["source"],
                "published_at": item["published_at"],
                "interest_ids": valid_topic_ids,
                "source_quality": quality_name,
                "summary": item["summary"],
            }
            if "event_at" in item:
                enriched["event_at"] = item["event_at"]
            candidate_tie = json.dumps(
                enriched,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            enriched.update(
                {
                    "canonical_url": url,
                    "title_key": key,
                    "age_hours": round(max(age_hours, 0.0), 2),
                    "scores": {
                        "interest": round(interest_score, 4),
                        "freshness": round(freshness_score, 4),
                        "source_quality": round(quality_score, 4),
                        "total": round(total_score, 4),
                    },
                    "_candidate_tie": candidate_tie,
                    "_host": host,
                    "_domain_bucket": domain_bucket(host),
                    "_source_key": title_key(item["source"]),
                    "_published_epoch": published.timestamp(),
                }
            )
            scored.append(enriched)

        scored.sort(
            key=lambda x: (
                -x["scores"]["total"],
                -x["_published_epoch"],
                x["canonical_url"],
                x["_candidate_tie"],
            )
        )

        deduplicated: list[dict[str, Any]] = []
        for item in scored:
            duplicate = False
            for accepted in deduplicated:
                if item["canonical_url"] == accepted["canonical_url"]:
                    duplicate = True
                    break
                if SequenceMatcher(None, item["title_key"], accepted["title_key"]).ratio() >= 0.92:
                    duplicate = True
                    break
            if duplicate:
                rejection_counts["duplicate_story"] += 1
            else:
                deduplicated.append(item)

        selected: list[dict[str, Any]] = []
        domain_counts: defaultdict[str, int] = defaultdict(int)
        source_counts: defaultdict[str, int] = defaultdict(int)
        topic_counts: defaultdict[str, int] = defaultdict(int)
        remaining = list(deduplicated)
        while remaining and len(selected) < limit:
            eligible_for_slot: list[dict[str, Any]] = []
            survivors: list[dict[str, Any]] = []
            for item in remaining:
                if (
                    domain_counts[item["_domain_bucket"]] >= max_per_domain
                    or source_counts[item["_source_key"]] >= max_per_domain
                ):
                    rejection_counts["domain_diversity_limit"] += 1
                    continue
                unseen_topic = any(topic_counts[topic_id] == 0 for topic_id in item["interest_ids"])
                saturation = max((topic_counts[topic_id] for topic_id in item["interest_ids"]), default=0)
                item["_selection_score"] = item["scores"]["total"] + (0.04 if unseen_topic else 0) - 0.02 * saturation
                eligible_for_slot.append(item)
                survivors.append(item)
            if not eligible_for_slot:
                break
            eligible_for_slot.sort(
                key=lambda x: (
                    -x["_selection_score"],
                    -x["scores"]["total"],
                    -x["_published_epoch"],
                    x["canonical_url"],
                    x["_candidate_tie"],
                )
            )
            chosen = eligible_for_slot[0]
            chosen["scores"]["selection"] = round(chosen["_selection_score"], 4)
            domain_counts[chosen["_domain_bucket"]] += 1
            source_counts[chosen["_source_key"]] += 1
            for topic_id in chosen["interest_ids"]:
                topic_counts[topic_id] += 1
            selected.append(chosen)
            remaining = [item for item in survivors if item is not chosen]

        for item in selected:
            item.pop("_candidate_tie", None)
            item.pop("_host", None)
            item.pop("_domain_bucket", None)
            item.pop("_source_key", None)
            item.pop("_published_epoch", None)
            item.pop("_selection_score", None)

        result = {
            "schema_version": "ranked-news/v1",
            "generated_at": now.isoformat(),
            "profile_id": profile["profile_id"],
            "profile_approval": approval,
            "profile_stale": profile_stale,
            "lookback_hours": lookback_hours,
            "input_candidates": len(candidates),
            "eligible_candidates": len(deduplicated),
            "selected_count": len(selected),
            "rejection_counts": dict(sorted(rejection_counts.items())),
            "sanitization_counts": dict(sorted(sanitization_counts.items())),
            "items": selected,
        }
        write_json_atomic(args.output, result)

        if args.update_seen:
            new_seen = list(previous_seen_items)
            stamp = now.isoformat()
            for item in selected:
                new_seen.append(
                    {
                        "url": item["canonical_url"],
                        "title_key": item["title_key"],
                        "first_seen_at": stamp,
                    }
                )
            unique: dict[tuple[str | None, str], dict[str, Any]] = {}
            for item in new_seen:
                unique[(item.get("url"), item.get("title_key", ""))] = item
            trimmed = list(unique.values())[-2000:]
            write_json_atomic(
                args.seen,
                {"schema_version": "news-seen/v1", "updated_at": stamp, "items": trimmed},
            )

    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"RANKED: {len(selected)} items -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
