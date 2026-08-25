"""Fixed safety budgets shared by worker projection and scheduled-run guard.

These values are intentionally constants rather than profile-controlled fields.
The coordinator may stop earlier, but it may not raise a limit supplied by a
profile, worker, or model.
"""

from __future__ import annotations

from typing import Final


RUN_BUDGETS: Final[dict[str, int]] = {
    "max_waves": 4,
    "max_pages": 128,
    "max_retries": 16,
    "max_retries_per_job": 2,
    "max_workers": 32,
    "max_topic_shards": 12,
    "max_candidates": 500,
    "deadline_seconds": 1800,
}

REQUIRED_BUDGET_KEYS: Final[frozenset[str]] = frozenset(RUN_BUDGETS)


def copy_run_budgets() -> dict[str, int]:
    """Return a detached budget object suitable for JSON serialization."""

    return dict(RUN_BUDGETS)


def validate_run_budgets(value: object) -> dict[str, int]:
    """Validate an untrusted budget object against the fixed safety limits.

    The returned object is always the fixed budget set.  A caller cannot use
    this helper to raise a limit; the optional value is accepted only when it
    exactly matches the constants.
    """

    if value is None:
        return copy_run_budgets()
    if not isinstance(value, dict) or set(value) != REQUIRED_BUDGET_KEYS:
        raise ValueError("budgets must contain exactly the fixed safety keys")
    for key, maximum in RUN_BUDGETS.items():
        candidate = value.get(key)
        if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate != maximum:
            raise ValueError(f"budget {key} must equal the fixed limit {maximum}")
    return copy_run_budgets()
