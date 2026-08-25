# Aggregate ensemble review

Use this reference only after `scripts/sanitize_history_aggregate.mjs` has produced and locally validated an `interest-profile/v2` draft.

## Non-negotiable boundary

Reviewers receive only the complete validated aggregate draft. They receive no Chrome handle, browser tool, raw rows, URLs, titles, hostnames, search strings, exact visit times, logs, or temporary evidence. They may judge only existing topic IDs and fixed enums. They may not invent topic labels, search terms, domains, or evidence.

## Quality-first map/reduce

Use five independent roles:

1. `temporal`: challenge trend, horizon, burstiness, and stability.
2. `intent`: challenge work-like versus durable relevance without inferring occupation or identity.
3. `news-utility`: judge whether the existing topic is useful for a recurring news digest.
4. `calibration`: challenge confidence against coverage, day spread, domain spread, and attention quality.
5. `skeptic`: search for false-positive explanations and correlated evidence.

When model selection is available for the user-requested quality-first route, use `gpt-5.6-luna` with `max` reasoning. Start with three independent reviewers per role. Run them in waves when concurrency is limited.

Do not spend reviewers uniformly forever. After merging the first wave, add two fresh reviewers only for contested topics/roles. Stop when all topics converge, or after seven judgments per contested topic/role. Retry a malformed or failed review at most twice; a failed review does not count toward quorum.

Convergence requires:

- at least five valid review files overall;
- at least three distinct roles overall;
- at least three distinct reviewer roles for each changed topic;
- no keep-versus-exclude split above 30%;
- maximum normalized disagreement no greater than 0.25.

More agents do not replace missing evidence. If the maximum is reached without convergence, keep the deterministic baseline for contested fields, reduce confidence, set `inference.ensemble.status` to `contested`, and require human review.

## Review JSON contract

Each reviewer writes one UTF-8 JSON object:

```json
{
  "schema_version": "profile-review/v1",
  "profile_id": "personal-news-20260824-draft-01",
  "baseline_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "reviewer_id": "temporal-reviewer-01",
  "reviewer_role": "temporal",
  "judgments": [
    {
      "topic_id": "cad-cae-manufacturing",
      "recommendation": "keep",
      "weight_delta": 0.03,
      "confidence_delta": -0.02,
      "intent": "mixed",
      "time_horizon": "durable",
      "reason_codes": ["cross-day-support", "cross-domain-support"]
    }
  ]
}
```

`baseline_sha256` is the lowercase SHA-256 of the exact UTF-8 bytes of the complete baseline profile file supplied to the reviewer. The reducer recomputes that file hash from one read snapshot and rejects any missing, malformed, or mismatched digest, even when a stale review has the same `profile_id`.

`reviewer_id` is a stable safe identifier and must be unique within one merge. The reducer also hashes canonical judgment content without identity or role fields; duplicate content is rejected so copying and relabelling a review cannot satisfy quorum.

Allowed recommendations are `keep`, `deprioritize`, `exclude`, and `uncertain`. Deltas must be between -0.15 and +0.15. Allowed intent values are `personal`, `professional`, `mixed`, and `unknown`. Allowed horizons are `durable`, `emerging`, `transient`, and `uncertain`.

Allowed reason codes:

- `cross-day-support`
- `cross-domain-support`
- `stable-recurrence`
- `single-window-burst`
- `work-utility-risk`
- `high-attention-coverage`
- `low-attention-coverage`
- `coverage-short`
- `taxonomy-ambiguity`
- `news-utility-high`
- `news-utility-low`
- `insufficient-evidence`

No free-text field is allowed. A reviewer should include every topic it can assess and use `uncertain` with zero deltas when evidence is insufficient.

## Deterministic reduction

Write reviews to a temporary directory, then run:

```text
python scripts/merge_profile_reviews.py --profile <baseline-v2.json> --reviews <review-1.json> <review-2.json> ... --output <reviewed-v2.json>
```

The reducer validates every key and enum, rejects unknown topic IDs, first takes a median within each role and then across roles, preserves explicit user decisions, penalizes disagreement, and always returns a draft. Replicating one role therefore cannot drown out the other roles. It never adds topics or public query terms. Delete individual review files after successful reduction unless the user asks to retain the safe aggregate audit material.
