#!/usr/bin/env python3
# NOTE: this file is vendored identically in chrome-preference-profiler and
# personalized-news-collector. Edit both copies; a test checks they match.
"""Validate the privacy-minimized interest-profile/v1 contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
ABSOLUTE_PATH_RE = re.compile(r"(?:\b[A-Za-z]:\\|(?:^|\s)/(?:Users|home|var|tmp)/)")
FORBIDDEN_SCHEMES_RE = re.compile(r"(?:https?://|file://|chrome://)", re.I)
FORBIDDEN_KEYS = {
    "history_entries",
    "raw_history",
    "raw_urls",
    "raw_titles",
    "search_queries",
    "visit_timestamps",
    "visited_at",
    "page_url",
    "page_title",
    "per_page_attention",
    "per_page_dwell",
    "attention_events",
    "review_notes",
}
PRIVATE_DOMAIN_SUFFIXES = (".internal", ".local", ".lan", ".corp", ".home", ".localhost", ".invalid", ".test", ".example")
PRIVATE_DOMAIN_LABELS = {"intranet", "internal", "private", "corpnet", "vpn", "admin", "auth", "login", "accounts", "mail", "docs", "drive"}
SENSITIVE_QUERY_RE = re.compile(
    r"(?:\b(?:confidential|internal|intranet|secret|customer|client|project|codename|nda|private)\b|"
    r"機密|社内|顧客|案件|プロジェクト|未公開|秘密|個人名)",
    re.I,
)
ISO_TIMESTAMP_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}[Tt ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?\b")
TITLE_LIKE_RE = re.compile(r"\b[A-Z][A-Za-z0-9_-]{2,}\s+[A-Z][A-Za-z0-9_-]{2,}\b")
CONTROL_TEXT_RE = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029\u200b\u200c\u200d\u2060\ufeff]")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]\r\n]{1,200}\]\s*(?:\([^\)\r\n]{0,500}\)|\[[^\]\r\n]{1,200}\])")
HTML_TAG_RE = re.compile(r"<!--|-->|</?[A-Za-z][^>\r\n]{0,256}>|<\s*[!?][^>\r\n]{0,256}>", re.I)
BARE_HOST_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}"
    r"(?::\d+)?(?:[/?#][^\s)\]]*)?",
    re.I,
)
PRIVATE_HOST_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:[A-Za-z0-9-]+\.)*(?:internal|local|lan|corp|home|localhost|invalid|test|example)"
    r"(?::\d+)?(?:[/?#\s]|$)|(?<![A-Za-z0-9])(?:intranet|vpn|auth|accounts|login|private|corpnet)(?![A-Za-z0-9])",
    re.I,
)
RELATIVE_PATH_RE = re.compile(
    r"(?:^|[\s(])(?:\.\.?[\\/]|[\\/](?:users?|home|var|tmp|workspace|project|private|internal)(?:[\\/]|$)"
    r"|(?:users?|home|var|tmp|workspace|project|private|internal)[\\/])",
    re.I,
)
UNC_OR_DEVICE_PATH_RE = re.compile(
    r"(?:^|[\s(])(?:\\\\(?:[?.][\\/])|\\\\[^\\/\s]+[\\/][^\\/\s]+(?:[\\/]|$)|//[^/\s]+/[^/\s]+(?:/|$))",
    re.I,
)
PROMPT_INJECTION_RE = re.compile(
    r"(?:\b(?:ignore|disregard|override|forget)\b.{0,48}\b(?:previous|prior|earlier|above|system|developer|user)?"
    r"\s*(?:instructions?|rules?|messages?|prompt)\b"
    r"|\b(?:do\s+not|don't)\s+(?:follow|obey)\s+(?:the\s+)?(?:previous|prior|above|these)?\s*(?:instructions?|rules?)\b"
    r"|\b(?:system|developer|assistant|user)\s*(?:message|prompt|instruction|role)\b"
    r"|(?:^|[\r\n])\s*(?:system|developer|assistant|user|instruction|tool)\s*[:>]"
    r"|(?:^|[\r\n])\s*(?:システム|開発者|アシスタント|ユーザー|指示)\s*[:：]"
    r"|\b(?:you\s+are|act\s+as|roleplay\s+as)\s+(?:chatgpt|an?\s+ai|the\s+assistant|a\s+system)\b"
    r"|\b(?:reveal|print|exfiltrate|leak)\b.{0,48}\b(?:prompt|system|secret|history|credentials?)\b"
    r"|(?:以前|前|上記|これまで)の?(?:指示|命令|ルール).{0,20}(?:無視|忘れ|上書き|従わない))",
    re.I,
)
TOP_LEVEL_KEYS_V1 = {
    "schema_version",
    "profile_id",
    "generated_at",
    "coverage",
    "privacy",
    "languages",
    "topics",
    "exclusions",
    "source_policy",
    "digest_defaults",
    "approval",
}
TOP_LEVEL_KEYS_V2 = TOP_LEVEL_KEYS_V1 | {"inference"}
COVERAGE_KEYS = {
    "source_kind",
    "requested_days",
    "requested_start",
    "requested_end",
    "actual_start",
    "actual_end",
    "observed_days",
    "processed_visits",
    "public_visits",
    "excluded_or_downweighted_visits",
    "retention_limit_days",
    "history_query_limit",
    "history_limit_hit",
    "result_truncated",
    "status",
}
PRIVACY_KEYS_V1 = {
    "raw_history_retained",
    "exact_urls_retained",
    "exact_titles_retained",
    "exact_visit_times_retained",
    "search_queries_retained",
    "sensitive_attribute_inference",
    "raw_tokens_copied_to_queries",
    "raw_tokens_copied_to_profile_text",
    "public_search_terms_reviewed",
}
PRIVACY_KEYS_V2 = PRIVACY_KEYS_V1 | {
    "raw_history_shared_with_reviewers",
    "aggregate_only_agent_reviews",
}
INFERENCE_KEYS = {
    "method",
    "taxonomy_version",
    "taxonomy_coverage_ratio",
    "unmapped_public_visits",
    "short_window_days",
    "long_window_days",
    "attention",
    "calibration",
    "ensemble",
}
INFERENCE_ATTENTION_KEYS = {
    "estimator",
    "status",
    "observable_visits",
    "coverage_ratio",
    "per_visit_cap_minutes",
    "session_gap_minutes",
}
CALIBRATION_KEYS = {"method", "status", "confidence_cap"}
ENSEMBLE_KEYS = {"status", "review_count", "role_count", "max_disagreement"}
TOPIC_KEYS_V1 = {
    "id",
    "label",
    "weight",
    "confidence",
    "user_confirmed",
    "news_eligible",
    "news_query_terms",
    "preferred_primary_domains",
    "rationale",
    "evidence",
}
TOPIC_KEYS_V2 = TOPIC_KEYS_V1 | {
    "parent_id",
    "intent",
    "time_horizon",
    "attention",
    "horizon",
    "intent_scores",
}
EVIDENCE_KEYS = {"capped_visits", "distinct_days", "domain_diversity", "recency_band"}
TOPIC_ATTENTION_KEYS = {
    "score",
    "band",
    "estimated_minutes_capped",
    "observable_visits",
    "coverage_ratio",
    "engaged_days",
}
HORIZON_KEYS = {"short_score", "long_score", "trend", "stability", "burstiness"}
INTENT_SCORE_KEYS = {"durable", "transient", "work_like"}
DIGEST_KEYS = {"lookback_hours", "max_items", "max_per_domain", "language_order"}
EXCLUSION_KEYS = {"topic_ids", "terms", "domains"}
APPROVAL_KEYS = {"status", "approved_at"}
RATIO_TOLERANCE = 0.011
APPROVAL_CHRONOLOGY_TOLERANCE = timedelta(minutes=5)
REQUIRED_TOP_LEVEL_KEYS_V1 = TOP_LEVEL_KEYS_V1 - {"source_policy"}
REQUIRED_TOP_LEVEL_KEYS_V2 = TOP_LEVEL_KEYS_V2 - {"source_policy"}
SAFE_DIAGNOSTIC_KEYS = (
    TOP_LEVEL_KEYS_V2
    | COVERAGE_KEYS
    | PRIVACY_KEYS_V2
    | INFERENCE_KEYS
    | INFERENCE_ATTENTION_KEYS
    | CALIBRATION_KEYS
    | ENSEMBLE_KEYS
    | TOPIC_KEYS_V2
    | EVIDENCE_KEYS
    | TOPIC_ATTENTION_KEYS
    | HORIZON_KEYS
    | INTENT_SCORE_KEYS
    | DIGEST_KEYS
    | EXCLUSION_KEYS
    | APPROVAL_KEYS
    | {"prefer", "deprioritize"}
    | FORBIDDEN_KEYS
)


def _reject_constant(_: str) -> None:
    raise ValueError("non-finite JSON number")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def loads_json_strict(payload: str) -> Any:
    return json.loads(
        payload,
        parse_constant=_reject_constant,
        object_pairs_hook=_reject_duplicate_pairs,
    )


def load_json_strict(path: Path) -> Any:
    return loads_json_strict(path.read_text(encoding="utf-8"))


def parse_iso(value: Any, label: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str):
        errors.append(f"{label} must be an ISO-8601 string")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} is not valid ISO-8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{label} must include a timezone offset")
        return None
    return parsed


def parse_date(value: Any, label: str, errors: list[str]) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        errors.append(f"{label} must be YYYY-MM-DD")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{label} is not a valid calendar date")
        return None


def in_unit_interval(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def public_domain_error(value: Any, *, allow_utility: bool = False) -> str | None:
    if not isinstance(value, str) or not DOMAIN_RE.fullmatch(value):
        return "must be a bare domain"
    lowered = value.casefold().rstrip(".")
    if lowered.endswith(PRIVATE_DOMAIN_SUFFIXES):
        return "uses a reserved or private suffix"
    first_label = lowered.split(".", 1)[0]
    if not allow_utility and first_label in PRIVATE_DOMAIN_LABELS:
        return "looks like an authentication or private-workspace host"
    return None


def public_query_error(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "must be non-empty"
    normalized = value.strip()
    if len(normalized) < 2 or len(normalized) > 80 or "\n" in normalized or "\r" in normalized:
        return "must be 2-80 characters on one line"
    if len(normalized.split()) > 8:
        return "must contain at most 8 whitespace-separated words"
    if issue := public_text_safety_error(normalized):
        return issue
    if SENSITIVE_QUERY_RE.search(normalized):
        return "looks private, confidential, customer-specific, or project-specific"
    if ISO_TIMESTAMP_RE.search(normalized):
        return "contains an exact timestamp"
    return None


def public_profile_text_error(value: Any) -> str | None:
    if not isinstance(value, str):
        return "must be text"
    if issue := public_text_safety_error(value):
        return issue
    if ISO_TIMESTAMP_RE.search(value):
        return "contains an exact timestamp"
    if TITLE_LIKE_RE.search(value):
        return "looks like an exact page title or private named item"
    return None


def public_text_safety_error(value: str) -> str | None:
    """Reject text that could carry private routing or executable instructions."""
    if CONTROL_TEXT_RE.search(value):
        return "contains control or invisible formatting characters"
    if MARKDOWN_LINK_RE.search(value):
        return "contains a Markdown link"
    if HTML_TAG_RE.search(value):
        return "contains HTML markup"
    if FORBIDDEN_SCHEMES_RE.search(value):
        return "contains a URL or forbidden scheme"
    if EMAIL_RE.search(value):
        return "contains an email address"
    if ABSOLUTE_PATH_RE.search(value) or RELATIVE_PATH_RE.search(value) or UNC_OR_DEVICE_PATH_RE.search(value):
        return "contains a local or workspace path"
    if PRIVATE_HOST_RE.search(value):
        return "contains an internal or private host token"
    if BARE_HOST_RE.search(value):
        return "contains a host or link; use a separate public-domain field"
    if PROMPT_INJECTION_RE.search(value):
        return "contains prompt-injection wording"
    return None


def reject_unknown_keys(value: Any, allowed: set[str], path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        return
    unknown_count = sum(1 for key in value if key not in allowed)
    if unknown_count:
        errors.append(f"{path} contains {unknown_count} field(s) outside the privacy-minimized schema")


def require_keys(value: Any, required: set[str], path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        return
    for key in sorted(required - set(value)):
        errors.append(f"{path}.{key} is required")


def walk(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_KEYS:
                errors.append(f"{path} contains a forbidden raw-history field")
            diagnostic_key = str(key) if key in SAFE_DIAGNOSTIC_KEYS else "<unknown>"
            walk(child, f"{path}.{diagnostic_key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk(child, f"{path}[{index}]", errors)
    elif isinstance(value, str):
        if CONTROL_TEXT_RE.search(value):
            errors.append(f"{path} contains control or invisible formatting characters")
        if MARKDOWN_LINK_RE.search(value) or HTML_TAG_RE.search(value):
            errors.append(f"{path} contains Markdown or HTML markup")
        if FORBIDDEN_SCHEMES_RE.search(value):
            errors.append(f"{path} contains a URL or forbidden scheme")
        if EMAIL_RE.search(value):
            errors.append(f"{path} contains an email address")
        if ABSOLUTE_PATH_RE.search(value) or RELATIVE_PATH_RE.search(value) or UNC_OR_DEVICE_PATH_RE.search(value):
            errors.append(f"{path} contains a local or workspace path")
        if PROMPT_INJECTION_RE.search(value):
            errors.append(f"{path} contains prompt-injection wording")


def validate_profile(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["profile root must be an object"]
    schema_version = data.get("schema_version")
    is_v2 = schema_version == "interest-profile/v2"
    if schema_version not in {"interest-profile/v1", "interest-profile/v2"}:
        errors.append("schema_version must be interest-profile/v1 or interest-profile/v2")
    allowed_top_level = TOP_LEVEL_KEYS_V2 if is_v2 else TOP_LEVEL_KEYS_V1
    required_top_level = REQUIRED_TOP_LEVEL_KEYS_V2 if is_v2 else REQUIRED_TOP_LEVEL_KEYS_V1
    reject_unknown_keys(data, allowed_top_level, "$", errors)
    require_keys(data, required_top_level, "$", errors)

    profile_id = data.get("profile_id")
    if not isinstance(profile_id, str) or not SLUG_RE.fullmatch(profile_id) or len(profile_id) > 96:
        errors.append("profile_id must be a lowercase slug of at most 96 characters")

    generated_at = parse_iso(data.get("generated_at"), "generated_at", errors)

    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        reject_unknown_keys(coverage, COVERAGE_KEYS, "coverage", errors)
        require_keys(coverage, COVERAGE_KEYS, "coverage", errors)
        for key in (
            "requested_days",
            "observed_days",
            "processed_visits",
            "public_visits",
            "excluded_or_downweighted_visits",
            "retention_limit_days",
            "history_query_limit",
        ):
            value = coverage.get(key)
            if not is_integer(value) or value < 0:
                errors.append(f"coverage.{key} must be a non-negative integer")
        if is_integer(coverage.get("requested_days")) and coverage["requested_days"] <= 0:
            errors.append("coverage.requested_days must be positive")
        if is_integer(coverage.get("retention_limit_days")) and coverage["retention_limit_days"] <= 0:
            errors.append("coverage.retention_limit_days must be positive")
        if is_integer(coverage.get("history_query_limit")) and coverage["history_query_limit"] <= 0:
            errors.append("coverage.history_query_limit must be positive")
        dates = {
            key: parse_date(coverage.get(key), f"coverage.{key}", errors)
            for key in ("requested_start", "requested_end", "actual_start", "actual_end")
        }
        if all(dates.values()):
            requested_start = dates["requested_start"]
            requested_end = dates["requested_end"]
            actual_start = dates["actual_start"]
            actual_end = dates["actual_end"]
            assert requested_start and requested_end and actual_start and actual_end
            if requested_start > requested_end:
                errors.append("coverage.requested_start must not be after requested_end")
            elif coverage.get("requested_days") != (requested_end - requested_start).days:
                errors.append("coverage.requested_days must equal requested_end minus requested_start")
            if actual_start > actual_end:
                errors.append("coverage.actual_start must not be after actual_end")
            if actual_start < requested_start or actual_end > requested_end:
                errors.append("coverage actual range must be inside the requested range")
            inclusive_span = (actual_end - actual_start).days + 1
            if coverage.get("observed_days") != inclusive_span:
                errors.append("coverage.observed_days must equal the inclusive actual date span")
        if coverage.get("source_kind") != "chrome-history-api":
            errors.append("coverage.source_kind must be chrome-history-api")
        for key in ("history_limit_hit", "result_truncated"):
            if not isinstance(coverage.get(key), bool):
                errors.append(f"coverage.{key} must be boolean")
        processed = coverage.get("processed_visits")
        public = coverage.get("public_visits")
        excluded = coverage.get("excluded_or_downweighted_visits")
        query_limit = coverage.get("history_query_limit")
        if all(is_integer(x) for x in (processed, public, excluded)):
            if processed != public + excluded:
                errors.append("coverage.processed_visits must equal public_visits plus excluded_or_downweighted_visits")
        if is_integer(processed) and is_integer(query_limit) and processed > query_limit:
            errors.append("coverage.processed_visits must not exceed history_query_limit")
        if is_integer(processed) and is_integer(query_limit) and query_limit > 0:
            expected_hit = processed == query_limit
            if coverage.get("history_limit_hit") is not expected_hit:
                errors.append("coverage.history_limit_hit must state whether processed_visits reached history_query_limit")
        if coverage.get("result_truncated") is not coverage.get("history_limit_hit"):
            errors.append("coverage.result_truncated must match the conservative history_limit_hit flag")
        if is_integer(coverage.get("retention_limit_days")) and coverage["retention_limit_days"] > 90:
            errors.append("coverage.retention_limit_days must not exceed Chrome's documented 90-day History window")
        if is_integer(coverage.get("observed_days")) and is_integer(coverage.get("retention_limit_days")):
            if coverage["observed_days"] > coverage["retention_limit_days"]:
                errors.append("coverage.observed_days must not exceed retention_limit_days")
        if coverage.get("status") not in {"insufficient", "provisional", "usable"}:
            errors.append("coverage.status must be insufficient, provisional, or usable")
        observed = coverage.get("observed_days")
        if is_integer(observed):
            if observed <= 0:
                errors.append("coverage.observed_days must be positive; do not create a profile for zero history")
            expected_status = "insufficient" if observed < 14 else "provisional" if observed <= 45 else "usable"
            if coverage.get("status") != expected_status:
                errors.append(f"coverage.status must be {expected_status} for {observed} observed days")
        if is_integer(processed) and processed <= 0:
            errors.append("coverage.processed_visits must be positive; do not create a profile for zero history")

    privacy = data.get("privacy")
    required_privacy_false = (
        "raw_history_retained",
        "exact_urls_retained",
        "exact_titles_retained",
        "exact_visit_times_retained",
        "search_queries_retained",
        "sensitive_attribute_inference",
        "raw_tokens_copied_to_queries",
        "raw_tokens_copied_to_profile_text",
    )
    required_privacy_true = ("public_search_terms_reviewed",)
    if not isinstance(privacy, dict):
        errors.append("privacy must be an object")
    else:
        privacy_keys = PRIVACY_KEYS_V2 if is_v2 else PRIVACY_KEYS_V1
        reject_unknown_keys(privacy, privacy_keys, "privacy", errors)
        require_keys(privacy, privacy_keys, "privacy", errors)
        privacy_false = required_privacy_false + (("raw_history_shared_with_reviewers",) if is_v2 else ())
        privacy_true = required_privacy_true + (("aggregate_only_agent_reviews",) if is_v2 else ())
        for key in privacy_false:
            if privacy.get(key) is not False:
                errors.append(f"privacy.{key} must be false")
        for key in privacy_true:
            if privacy.get(key) is not True:
                errors.append(f"privacy.{key} must be true")

    inference = data.get("inference")
    if is_v2:
        if not isinstance(inference, dict):
            errors.append("inference must be an object for interest-profile/v2")
        else:
            reject_unknown_keys(inference, INFERENCE_KEYS, "inference", errors)
            require_keys(inference, INFERENCE_KEYS, "inference", errors)
            if inference.get("method") != "privacy-safe-history-signals/v2":
                errors.append("inference.method is unsupported")
            if inference.get("taxonomy_version") != "public-news-taxonomy/v2":
                errors.append("inference.taxonomy_version is unsupported")
            if not in_unit_interval(inference.get("taxonomy_coverage_ratio")):
                errors.append("inference.taxonomy_coverage_ratio must be between 0 and 1")
            unmapped = inference.get("unmapped_public_visits")
            if not is_integer(unmapped) or unmapped < 0:
                errors.append("inference.unmapped_public_visits must be a non-negative integer")
            for key in ("short_window_days", "long_window_days"):
                value = inference.get(key)
                if not is_integer(value) or value <= 0 or value > 90:
                    errors.append(f"inference.{key} must be an integer from 1 to 90")
            if is_integer(inference.get("short_window_days")) and is_integer(inference.get("long_window_days")):
                if inference["short_window_days"] > inference["long_window_days"]:
                    errors.append("inference.short_window_days must not exceed long_window_days")
            if isinstance(coverage, dict) and is_integer(inference.get("long_window_days")) and is_integer(coverage.get("retention_limit_days")):
                if inference["long_window_days"] > coverage["retention_limit_days"]:
                    errors.append("inference.long_window_days must not exceed retention_limit_days")
            if isinstance(coverage, dict) and is_integer(unmapped) and is_integer(coverage.get("public_visits")):
                public_visits = coverage["public_visits"]
                if unmapped > public_visits:
                    errors.append("inference.unmapped_public_visits must not exceed coverage.public_visits")
                elif public_visits > 0 and in_unit_interval(inference.get("taxonomy_coverage_ratio")):
                    expected_ratio = (public_visits - unmapped) / public_visits
                    if abs(inference["taxonomy_coverage_ratio"] - expected_ratio) > RATIO_TOLERANCE:
                        errors.append("inference taxonomy coverage ratio does not reconcile with public visits")

            attention_meta = inference.get("attention")
            if not isinstance(attention_meta, dict):
                errors.append("inference.attention must be an object")
            else:
                reject_unknown_keys(attention_meta, INFERENCE_ATTENTION_KEYS, "inference.attention", errors)
                require_keys(attention_meta, INFERENCE_ATTENTION_KEYS, "inference.attention", errors)
                if attention_meta.get("estimator") != "adjacent-gap-proxy/v1":
                    errors.append("inference.attention.estimator is unsupported")
                if attention_meta.get("status") not in {"usable", "limited", "unavailable"}:
                    errors.append("inference.attention.status is unsupported")
                if not is_integer(attention_meta.get("observable_visits")) or attention_meta.get("observable_visits", -1) < 0:
                    errors.append("inference.attention.observable_visits must be a non-negative integer")
                if not in_unit_interval(attention_meta.get("coverage_ratio")):
                    errors.append("inference.attention.coverage_ratio must be between 0 and 1")
                for key in ("per_visit_cap_minutes", "session_gap_minutes"):
                    value = attention_meta.get(key)
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0 or value > 60:
                        errors.append(f"inference.attention.{key} must be a number from 0 to 60")
                attention_observable = attention_meta.get("observable_visits")
                attention_ratio = attention_meta.get("coverage_ratio")
                public_visits = coverage.get("public_visits") if isinstance(coverage, dict) else None
                matched_public_visits = None
                if is_integer(public_visits) and is_integer(unmapped) and 0 <= unmapped <= public_visits:
                    matched_public_visits = public_visits - unmapped
                    if is_integer(attention_observable) and attention_observable > matched_public_visits:
                        errors.append("inference.attention.observable_visits must not exceed matched public visits")
                    if is_integer(attention_observable) and in_unit_interval(attention_ratio):
                        expected_attention_ratio = (
                            attention_observable / matched_public_visits if matched_public_visits else 0.0
                        )
                        if abs(attention_ratio - expected_attention_ratio) > RATIO_TOLERANCE:
                            errors.append("inference attention coverage ratio does not reconcile with matched public visits")
                if is_integer(attention_observable) and in_unit_interval(attention_ratio):
                    if attention_observable == 0:
                        if attention_meta.get("status") != "unavailable" or attention_ratio != 0:
                            errors.append("zero-observable attention must be unavailable with zero coverage")
                    elif attention_meta.get("status") == "unavailable":
                        errors.append("unavailable attention must have zero observable visits and zero coverage")
                    if attention_meta.get("status") == "usable" and attention_ratio < 0.5:
                        errors.append("usable attention requires at least 0.5 coverage")

            calibration = inference.get("calibration")
            if not isinstance(calibration, dict):
                errors.append("inference.calibration must be an object")
            else:
                reject_unknown_keys(calibration, CALIBRATION_KEYS, "inference.calibration", errors)
                require_keys(calibration, CALIBRATION_KEYS, "inference.calibration", errors)
                if calibration.get("method") != "prior-only/v1" or calibration.get("status") != "uncalibrated":
                    errors.append("inference.calibration must disclose the prior-only uncalibrated method")
                if not in_unit_interval(calibration.get("confidence_cap")) or calibration.get("confidence_cap", 1) > 0.75:
                    errors.append("inference.calibration.confidence_cap must be between 0 and 0.75")

            ensemble = inference.get("ensemble")
            if not isinstance(ensemble, dict):
                errors.append("inference.ensemble must be an object")
            else:
                reject_unknown_keys(ensemble, ENSEMBLE_KEYS, "inference.ensemble", errors)
                require_keys(ensemble, ENSEMBLE_KEYS, "inference.ensemble", errors)
                if ensemble.get("status") not in {"not-run", "converged", "contested"}:
                    errors.append("inference.ensemble.status is unsupported")
                for key in ("review_count", "role_count"):
                    if not is_integer(ensemble.get(key)) or ensemble.get(key, -1) < 0:
                        errors.append(f"inference.ensemble.{key} must be a non-negative integer")
                if is_integer(ensemble.get("review_count")) and ensemble["review_count"] > 35:
                    errors.append("inference.ensemble.review_count must not exceed 35")
                if is_integer(ensemble.get("role_count")) and ensemble["role_count"] > 5:
                    errors.append("inference.ensemble.role_count must not exceed five")
                if is_integer(ensemble.get("review_count")) and is_integer(ensemble.get("role_count")):
                    if ensemble["role_count"] > ensemble["review_count"]:
                        errors.append("inference.ensemble.role_count must not exceed review_count")
                if not in_unit_interval(ensemble.get("max_disagreement")):
                    errors.append("inference.ensemble.max_disagreement must be between 0 and 1")
                if ensemble.get("status") == "not-run" and any(ensemble.get(key) != 0 for key in ("review_count", "role_count", "max_disagreement")):
                    errors.append("not-run ensemble metrics must be zero")
                if ensemble.get("status") in {"converged", "contested"}:
                    if ensemble.get("review_count", 0) < 5 or ensemble.get("role_count", 0) < 3:
                        errors.append("completed ensemble review requires five reviews and three roles")

    languages = data.get("languages")
    if (
        not isinstance(languages, list)
        or not 1 <= len(languages) <= 8
        or not all(isinstance(x, str) and x for x in languages)
        or len(set(languages)) != len(languages)
    ):
        errors.append("languages must be a non-empty string array")

    topics = data.get("topics")
    seen_ids: set[str] = set()
    global_attention = inference.get("attention") if is_v2 and isinstance(inference, dict) else None
    global_observable = global_attention.get("observable_visits") if isinstance(global_attention, dict) else None
    attention_cap_minutes = global_attention.get("per_visit_cap_minutes") if isinstance(global_attention, dict) else None
    observed_days = coverage.get("observed_days") if isinstance(coverage, dict) else None
    if not isinstance(topics, list) or not 1 <= len(topics) <= 64:
        errors.append("topics must contain between 1 and 64 items")
    else:
        for index, topic in enumerate(topics):
            prefix = f"topics[{index}]"
            if not isinstance(topic, dict):
                errors.append(f"{prefix} must be an object")
                continue
            topic_keys = TOPIC_KEYS_V2 if is_v2 else TOPIC_KEYS_V1
            reject_unknown_keys(topic, topic_keys, prefix, errors)
            require_keys(topic, topic_keys, prefix, errors)
            topic_id = topic.get("id")
            if not isinstance(topic_id, str) or not SLUG_RE.fullmatch(topic_id):
                errors.append(f"{prefix}.id must be a lowercase slug")
            elif topic_id in seen_ids:
                errors.append(f"{prefix}.id is duplicated")
            else:
                seen_ids.add(topic_id)
            if is_v2:
                parent_id = topic.get("parent_id")
                if not isinstance(parent_id, str) or not SLUG_RE.fullmatch(parent_id):
                    errors.append(f"{prefix}.parent_id must be a lowercase slug")
                elif parent_id == topic_id:
                    errors.append(f"{prefix}.parent_id must differ from the topic id")
            if not isinstance(topic.get("label"), str) or not topic["label"].strip():
                errors.append(f"{prefix}.label must be non-empty")
            elif SENSITIVE_QUERY_RE.search(topic["label"]):
                errors.append(f"{prefix}.label looks private or project-specific")
            elif issue := public_profile_text_error(topic["label"]):
                errors.append(f"{prefix}.label {issue}")
            rationale = topic.get("rationale")
            if not isinstance(rationale, str) or not 10 <= len(rationale.strip()) <= 240 or "\n" in rationale:
                errors.append(f"{prefix}.rationale must be a 10-240 character single-line summary")
            elif SENSITIVE_QUERY_RE.search(rationale):
                errors.append(f"{prefix}.rationale looks private, confidential, customer-specific, or project-specific")
            elif issue := public_profile_text_error(rationale):
                errors.append(f"{prefix}.rationale {issue}")
            for key in ("weight", "confidence"):
                if not in_unit_interval(topic.get(key)):
                    errors.append(f"{prefix}.{key} must be between 0 and 1")
            if "user_confirmed" in topic and topic.get("user_confirmed") not in {None, True, False}:
                errors.append(f"{prefix}.user_confirmed must be null or boolean")
            if is_v2 and topic.get("user_confirmed") is None and isinstance(inference, dict):
                calibration_value = inference.get("calibration")
                if isinstance(calibration_value, dict) and in_unit_interval(calibration_value.get("confidence_cap")):
                    confidence_value = topic.get("confidence")
                    if in_unit_interval(confidence_value) and confidence_value > calibration_value["confidence_cap"]:
                        errors.append(f"{prefix}.confidence exceeds the disclosed uncalibrated cap")
            if not isinstance(topic.get("news_eligible"), bool):
                errors.append(f"{prefix}.news_eligible must be boolean")
            if is_v2:
                if topic.get("intent") not in {"personal", "professional", "mixed", "unknown"}:
                    errors.append(f"{prefix}.intent is unsupported")
                if topic.get("time_horizon") not in {"durable", "emerging", "transient", "uncertain"}:
                    errors.append(f"{prefix}.time_horizon is unsupported")
            terms = topic.get("news_query_terms")
            if not isinstance(terms, list) or not terms or not all(isinstance(x, str) and x.strip() for x in terms):
                errors.append(f"{prefix}.news_query_terms must be a non-empty string array")
            elif len(terms) > 12 or len(set(terms)) != len(terms):
                errors.append(f"{prefix}.news_query_terms must contain at most 12 unique terms")
            else:
                for term_index, term in enumerate(terms):
                    issue = public_query_error(term)
                    if issue:
                        errors.append(f"{prefix}.news_query_terms[{term_index}] {issue}")
            domains = topic.get("preferred_primary_domains")
            if (
                not isinstance(domains, list)
                or len(domains) > 16
                or not all(isinstance(domain, str) for domain in domains)
                or len(set(domains)) != len(domains)
            ):
                errors.append(f"{prefix}.preferred_primary_domains must contain bare public domains")
            else:
                for domain_index, domain in enumerate(domains):
                    issue = public_domain_error(domain)
                    if issue:
                        errors.append(f"{prefix}.preferred_primary_domains[{domain_index}] {issue}")
            evidence = topic.get("evidence")
            if not isinstance(evidence, dict):
                errors.append(f"{prefix}.evidence must be an object")
            else:
                reject_unknown_keys(evidence, EVIDENCE_KEYS, f"{prefix}.evidence", errors)
                require_keys(evidence, EVIDENCE_KEYS, f"{prefix}.evidence", errors)
                for key in ("capped_visits", "distinct_days", "domain_diversity"):
                    value = evidence.get(key)
                    if not is_integer(value) or value < 0:
                        errors.append(f"{prefix}.evidence.{key} must be a non-negative integer")
                if evidence.get("recency_band") not in {"recent", "mixed", "older"}:
                    errors.append(f"{prefix}.evidence.recency_band must be recent, mixed, or older")

            if is_v2:
                topic_attention = topic.get("attention")
                if not isinstance(topic_attention, dict):
                    errors.append(f"{prefix}.attention must be an object")
                else:
                    reject_unknown_keys(topic_attention, TOPIC_ATTENTION_KEYS, f"{prefix}.attention", errors)
                    require_keys(topic_attention, TOPIC_ATTENTION_KEYS, f"{prefix}.attention", errors)
                    if not in_unit_interval(topic_attention.get("score")):
                        errors.append(f"{prefix}.attention.score must be between 0 and 1")
                    if topic_attention.get("band") not in {"low", "medium", "high"}:
                        errors.append(f"{prefix}.attention.band is unsupported")
                    minutes = topic_attention.get("estimated_minutes_capped")
                    if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or minutes < 0:
                        errors.append(f"{prefix}.attention.estimated_minutes_capped must be non-negative")
                    for key in ("observable_visits", "engaged_days"):
                        value = topic_attention.get(key)
                        if not is_integer(value) or value < 0:
                            errors.append(f"{prefix}.attention.{key} must be a non-negative integer")
                    if not in_unit_interval(topic_attention.get("coverage_ratio")):
                        errors.append(f"{prefix}.attention.coverage_ratio must be between 0 and 1")
                    topic_observable = topic_attention.get("observable_visits")
                    topic_ratio = topic_attention.get("coverage_ratio")
                    topic_score = topic_attention.get("score")
                    topic_minutes = topic_attention.get("estimated_minutes_capped")
                    engaged_days = topic_attention.get("engaged_days")
                    if is_integer(topic_observable) and is_integer(global_observable):
                        if topic_observable > global_observable:
                            errors.append(f"{prefix}.attention.observable_visits must not exceed global observable visits")
                    if (
                        isinstance(topic_minutes, (int, float))
                        and not isinstance(topic_minutes, bool)
                        and is_integer(topic_observable)
                        and isinstance(attention_cap_minutes, (int, float))
                        and not isinstance(attention_cap_minutes, bool)
                        and topic_minutes > topic_observable * attention_cap_minutes
                    ):
                        errors.append(f"{prefix}.attention.estimated_minutes_capped exceeds its visit cap")
                    if is_integer(topic_observable) and topic_observable == 0:
                        if topic_minutes != 0 or topic_ratio != 0 or topic_score != 0:
                            errors.append(f"{prefix}.attention zero-observable fields must all be zero")
                    if is_integer(engaged_days) and is_integer(observed_days) and engaged_days > observed_days:
                        errors.append(f"{prefix}.attention.engaged_days must not exceed coverage.observed_days")

                horizon = topic.get("horizon")
                if not isinstance(horizon, dict):
                    errors.append(f"{prefix}.horizon must be an object")
                else:
                    reject_unknown_keys(horizon, HORIZON_KEYS, f"{prefix}.horizon", errors)
                    require_keys(horizon, HORIZON_KEYS, f"{prefix}.horizon", errors)
                    for key in ("short_score", "long_score", "stability", "burstiness"):
                        if not in_unit_interval(horizon.get(key)):
                            errors.append(f"{prefix}.horizon.{key} must be between 0 and 1")
                    if horizon.get("trend") not in {"rising", "steady", "fading", "unknown"}:
                        errors.append(f"{prefix}.horizon.trend is unsupported")

                intent_scores = topic.get("intent_scores")
                if not isinstance(intent_scores, dict):
                    errors.append(f"{prefix}.intent_scores must be an object")
                else:
                    reject_unknown_keys(intent_scores, INTENT_SCORE_KEYS, f"{prefix}.intent_scores", errors)
                    require_keys(intent_scores, INTENT_SCORE_KEYS, f"{prefix}.intent_scores", errors)
                    for key in INTENT_SCORE_KEYS:
                        if not in_unit_interval(intent_scores.get(key)):
                            errors.append(f"{prefix}.intent_scores.{key} must be between 0 and 1")

    defaults = data.get("digest_defaults")
    if not isinstance(defaults, dict):
        errors.append("digest_defaults must be an object")
    else:
        reject_unknown_keys(defaults, DIGEST_KEYS, "digest_defaults", errors)
        require_keys(defaults, DIGEST_KEYS, "digest_defaults", errors)
        for key in ("lookback_hours", "max_items", "max_per_domain"):
            value = defaults.get(key)
            if not is_integer(value) or value <= 0:
                errors.append(f"digest_defaults.{key} must be a positive integer")
        language_order = defaults.get("language_order")
        if not isinstance(language_order, list) or not language_order or not all(
            isinstance(x, str) and x for x in language_order
        ):
            errors.append("digest_defaults.language_order must be a non-empty string array")
        elif len(language_order) > 8 or len(set(language_order)) != len(language_order):
            errors.append("digest_defaults.language_order must contain at most eight unique languages")
        elif isinstance(languages, list) and any(language not in languages for language in language_order):
            errors.append("digest_defaults.language_order must be drawn from languages")

    exclusions = data.get("exclusions")
    if not isinstance(exclusions, dict):
        errors.append("exclusions must be an object")
    else:
        reject_unknown_keys(exclusions, EXCLUSION_KEYS, "exclusions", errors)
        require_keys(exclusions, EXCLUSION_KEYS, "exclusions", errors)
        for key in ("topic_ids", "terms", "domains"):
            value = exclusions.get(key)
            if (
                not isinstance(value, list)
                or len(value) > 64
                or not all(isinstance(x, str) and x.strip() for x in value)
                or len(set(value)) != len(value)
            ):
                errors.append(f"exclusions.{key} must be a string array")
        topic_exclusions = exclusions.get("topic_ids", [])
        if isinstance(topic_exclusions, list) and all(isinstance(value, str) for value in topic_exclusions):
            if any(topic_id not in seen_ids for topic_id in topic_exclusions):
                errors.append("exclusions.topic_ids contains an unknown topic id")
        terms = exclusions.get("terms", [])
        if isinstance(terms, list):
            for term_index, term in enumerate(terms):
                issue = public_query_error(term)
                if issue:
                    errors.append(f"exclusions.terms[{term_index}] {issue}")
        domains = exclusions.get("domains", [])
        if isinstance(domains, list):
            for domain_index, domain in enumerate(domains):
                issue = public_domain_error(domain, allow_utility=True)
                if issue:
                    errors.append(f"exclusions.domains[{domain_index}] {issue}")

    source_policy = data.get("source_policy")
    if source_policy is not None:
        if not isinstance(source_policy, dict):
            errors.append("source_policy must be an object when present")
        else:
            reject_unknown_keys(source_policy, {"prefer", "deprioritize"}, "source_policy", errors)
            require_keys(source_policy, {"prefer", "deprioritize"}, "source_policy", errors)
            for key in ("prefer", "deprioritize"):
                values = source_policy.get(key)
                if not isinstance(values, list) or not values or not all(
                    isinstance(x, str) and 2 <= len(x.strip()) <= 120 and "\n" not in x for x in values
                ):
                    errors.append(f"source_policy.{key} must be a non-empty array of short public descriptions")
                elif any(SENSITIVE_QUERY_RE.search(x) for x in values):
                    errors.append(f"source_policy.{key} contains private or project-specific wording")
                elif any(public_profile_text_error(x) for x in values):
                    errors.append(f"source_policy.{key} contains an exact timestamp or title-like wording")

    approval = data.get("approval")
    if not isinstance(approval, dict):
        errors.append("approval must be an object")
    else:
        reject_unknown_keys(approval, APPROVAL_KEYS, "approval", errors)
        require_keys(approval, APPROVAL_KEYS, "approval", errors)
        status = approval.get("status")
        if status not in {"draft", "approved"}:
            errors.append("approval.status must be draft or approved")
        approved_at = approval.get("approved_at")
        if status == "approved":
            approved_at_parsed = parse_iso(approved_at, "approval.approved_at", errors)
            if generated_at is not None and approved_at_parsed is not None:
                if approved_at_parsed < generated_at - APPROVAL_CHRONOLOGY_TOLERANCE:
                    errors.append(
                        "approval.approved_at must not precede generated_at by more than five minutes"
                    )
            if isinstance(topics, list) and topics:
                if any(isinstance(topic, dict) and topic.get("user_confirmed") is None for topic in topics):
                    errors.append("approved profiles require every topic to have an explicit user_confirmed boolean")
                if not any(
                    isinstance(topic, dict)
                    and topic.get("user_confirmed") is True
                    and topic.get("news_eligible") is True
                    for topic in topics
                ):
                    errors.append("approved profiles require at least one user-confirmed news-eligible topic")
        elif approved_at is not None:
            errors.append("approval.approved_at must be null while status is draft")

    walk(data, "$", errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    try:
        if args.profile.stat().st_size > 2_000_000:
            raise ValueError("profile exceeds the 2 MB safety limit")
        data = load_json_strict(args.profile)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    errors = validate_profile(data)
    if errors:
        for error in errors:
            print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print(f"VALID: {args.profile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
