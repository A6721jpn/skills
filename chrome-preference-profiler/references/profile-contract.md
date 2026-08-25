# Interest profile contract

`profile.json` is the source of truth. `profile.md` is its deterministic human-readable rendering. Both contain aggregate, public-news-safe terms only.

The profiler writes `interest-profile/v2`. The paired collector and validator also accept legacy `interest-profile/v1` files so an already approved profile keeps working until the user refreshes it.

## v2 shape

```json
{
  "schema_version": "interest-profile/v2",
  "profile_id": "personal-news-20260824-draft-01",
  "generated_at": "2026-08-24T18:30:00+09:00",
  "coverage": {
    "source_kind": "chrome-history-api",
    "requested_days": 365,
    "requested_start": "2025-08-24",
    "requested_end": "2026-08-24",
    "actual_start": "2026-07-15",
    "actual_end": "2026-08-24",
    "observed_days": 41,
    "processed_visits": 3669,
    "public_visits": 1448,
    "excluded_or_downweighted_visits": 2221,
    "retention_limit_days": 90,
    "history_query_limit": 50000,
    "history_limit_hit": false,
    "result_truncated": false,
    "status": "provisional"
  },
  "privacy": {
    "raw_history_retained": false,
    "exact_urls_retained": false,
    "exact_titles_retained": false,
    "exact_visit_times_retained": false,
    "search_queries_retained": false,
    "sensitive_attribute_inference": false,
    "raw_tokens_copied_to_queries": false,
    "raw_tokens_copied_to_profile_text": false,
    "raw_history_shared_with_reviewers": false,
    "aggregate_only_agent_reviews": true,
    "public_search_terms_reviewed": true
  },
  "inference": {
    "method": "privacy-safe-history-signals/v2",
    "taxonomy_version": "public-news-taxonomy/v2",
    "taxonomy_coverage_ratio": 0.54,
    "unmapped_public_visits": 666,
    "short_window_days": 7,
    "long_window_days": 90,
    "attention": {
      "estimator": "adjacent-gap-proxy/v1",
      "status": "limited",
      "observable_visits": 721,
      "coverage_ratio": 0.92,
      "per_visit_cap_minutes": 10,
      "session_gap_minutes": 30
    },
    "calibration": {
      "method": "prior-only/v1",
      "status": "uncalibrated",
      "confidence_cap": 0.75
    },
    "ensemble": {
      "status": "not-run",
      "review_count": 0,
      "role_count": 0,
      "max_disagreement": 0.0
    }
  },
  "languages": ["ja", "en"],
  "topics": [
    {
      "id": "cad-cae-manufacturing",
      "parent_id": "engineering-design",
      "label": "機械CAD・CAE・製造技術",
      "weight": 0.9,
      "confidence": 0.72,
      "user_confirmed": null,
      "news_eligible": true,
      "intent": "mixed",
      "time_horizon": "durable",
      "news_query_terms": ["mechanical CAD CAE", "STEP B-Rep Open CASCADE"],
      "preferred_primary_domains": ["autodesk.com", "solidworks.com"],
      "rationale": "複数日・複数公開ソースにまたがる継続的な技術調査。",
      "attention": {
        "score": 0.62,
        "band": "medium",
        "estimated_minutes_capped": 182.5,
        "observable_visits": 94,
        "coverage_ratio": 0.71,
        "engaged_days": 8
      },
      "horizon": {
        "short_score": 0.64,
        "long_score": 0.78,
        "trend": "steady",
        "stability": 0.71,
        "burstiness": 0.18
      },
      "intent_scores": {
        "durable": 0.72,
        "transient": 0.16,
        "work_like": 0.12
      },
      "evidence": {
        "capped_visits": 100,
        "distinct_days": 20,
        "domain_diversity": 12,
        "recency_band": "recent"
      }
    }
  ],
  "exclusions": {
    "topic_ids": [],
    "terms": [],
    "domains": []
  },
  "digest_defaults": {
    "lookback_hours": 72,
    "max_items": 8,
    "max_per_domain": 2,
    "language_order": ["ja", "en"]
  },
  "approval": {
    "status": "draft",
    "approved_at": null
  }
}
```

## Contract rules

- Accept only exact schema versions `interest-profile/v1` and `interest-profile/v2`. Reject unknown fields at every governed object. The profiler emits v2; v1 is compatibility-only.
- Topic IDs and optional parent IDs are lowercase slugs. `weight`, `confidence`, all scores, probabilities, ratios, stability, burstiness, and disagreement are in 0–1.
- `weight` means usefulness for news ranking. `confidence` means confidence that the inferred topic is a stable interest. Neither is measured preference probability.
- `intent` is `personal`, `professional`, `mixed`, or `unknown`. It describes likely context, never occupation, employer, or identity.
- `time_horizon` is `durable`, `emerging`, `transient`, or `uncertain`. Absence of activity must not create negative preference evidence.
- Attention is explicitly an adjacent-gap proxy. Only aggregate capped minutes, coverage, counts, score, and band may persist. No per-page durations or event arrays are permitted.
- Attention counts reconcile: global observable visits cannot exceed matched public visits (`public_visits - unmapped_public_visits`), and global coverage is the observable/matched ratio within two-decimal rounding. Zero observable visits require `unavailable` status and zero coverage; `usable` requires at least 0.5 coverage. Per-topic capped minutes cannot exceed observable visits times the global per-visit cap; a zero-observable topic has zero minutes, coverage, and score, cannot exceed global observable visits, and its engaged days cannot exceed observed days.
- `news_query_terms` contain fixed, broad public topics, never raw searches, private names, internal identifiers, personal attributes, or strings copied from history.
- Public query terms, topic labels, rationales, and source-policy text must remain public-news-safe: reject prompt-injection wording, internal/private host tokens, URLs or links, local/workspace paths (including UNC shares and Windows device prefixes), email addresses, control or invisible formatting characters, and HTML/Markdown markup. Legitimate Japanese and broad public-topic wording remains allowed.
- `preferred_primary_domains` contain bare public domains, not URLs. Coverage counts and date spans must reconcile.
- Privacy flags describing retention, sensitive inference, raw-token copying, or reviewer sharing remain false. `aggregate_only_agent_reviews` and `public_search_terms_reviewed` remain true.
- The file must not contain URL schemes, email addresses, absolute local paths, exact visit timestamps, raw evidence arrays, or forbidden raw-history keys.
- Markdown rendering escapes user-controlled text as inert Markdown/HTML content; validation and rendering are separate safeguards.
- `approval.status` is `draft` or `approved`. Only explicit user review changes a draft to approved. An approved profile has no `user_confirmed: null` topics and at least one confirmed news-eligible topic. Its `approved_at` must not precede `generated_at` by more than five minutes, preventing copied historical approval metadata from being attached to a newer profile. Draft profiles keep `approved_at: null`.
- Agent consensus cannot approve a profile, add topics, add query terms, or override explicit user decisions.

## Inference interpretation

- `taxonomy_coverage_ratio` is the fraction of filtered public visits explained by one or more fixed topics. A low value reduces overall confidence and should trigger an explicit-interest request, not raw-term discovery.
- Attention `status` is `usable`, `limited`, or `unavailable`. Low coverage or aggregate history rows must not be presented as measured reading time.
- Calibration remains `prior-only/v1` and `uncalibrated` until a held-out aggregate dataset with explicit user labels is actually evaluated. Uncalibrated inferred confidence is capped at 0.75.
- Ensemble status is `not-run`, `converged`, or `contested`. Only aggregate review counts and disagreement persist; individual review text does not.
- Review inputs require a 64-character lowercase `baseline_sha256` equal to the SHA-256 of the exact UTF-8 baseline profile file bytes, plus unique reviewer identities and unique canonical judgment content; a review from another file with the same `profile_id`, or a copied/relabelled review, does not count toward quorum. Merging always clamps confidence to the disclosed calibration cap.

## Markdown rendering

The companion Markdown includes coverage and shortfall, taxonomy and attention quality, topic weight/confidence/intent/horizon, aggregate rationales, exclusions, privacy guarantees, ensemble status, and approval instructions.

It must not include domains visited, raw titles, queries, private hostnames, per-page attention, individual reviewer output, or exact visit times.
