---
name: personalized-news-collector
description: Collect and summarize current news from an existing validated interest profile with live web verification, direct sources, event deduplication, and diversity. Use for personalized news digests; never read Chrome history, regenerate preferences, or schedule or send anything unless separately requested.
---

# Personalized News Collector

Use a privacy-minimized interest profile to produce a fresh, source-linked Japanese news digest. This skill consumes aggregate topics only and must never access Chrome history.

## Preflight

1. Resolve `profile.json` from the user-provided path or the default personal-news data root used by `$chrome-preference-profiler`.
2. Read [Profile consumer contract](references/profile-consumer-contract.md).
3. Validate before any web request:

   `python scripts/validate_profile.py <path-to-profile.json>`

4. Accept `interest-profile/v1` or `interest-profile/v2`. Require `approval.status: approved` for normal, recurring, or unattended collection. A draft is allowed only for a clearly labeled, explicitly requested one-off preview and must never update seen state.
5. Reject invalid schema, missing profile, privacy failure, or unsupported approval state before search. Never read Chrome or run the profiler to repair a missing profile.

## Collection workflow

1. Read [News workflow](references/news-workflow.md). For multi-agent or scheduled operation, also read [Multi-agent scheduled collection](references/multi-agent-scheduled-collection.md).
2. Use live web search on every run. Search only approved broad `news_query_terms` plus explicit run terms. Never search profile evidence or browser-derived strings.
3. Build the worker input from the validated approved profile before any worker call:

   `python scripts/project_worker_profile.py --profile <path-to-profile.json> --output <coordinator-owned>/worker-profile.json --output-root <coordinator-owned> --expected-profile-sha256 <snapshot-sha256>`

   The projection is an atomic, public-field whitelist. It contains no coverage, privacy, attention, evidence, raw history, intent probabilities, local paths, or approval metadata. Use independent discovery, primary-source, context, verification, adversarial, and clustering lanes when subagents are available. Workers receive only the projection and have no writable state.
4. Open promising direct pages. Verify headline, publisher, publication date, event date, and every summarized claim. Prefer primary sources for product, software, standards, research, regulatory, and company claims; add independent context when it materially improves confidence.
5. Build a temporary candidate JSON file using the exact schema in the workflow reference. Target roughly three times the requested item count when possible. Keep worker metadata and verification votes in a separate temporary ledger, never in candidate JSON.
6. Consolidate same-event reports before ranking. Use deterministic URL/title blocking first and agent judgments only for ambiguous pairs. Merge supporting links into the temporary verification ledger rather than spending multiple digest slots on one event.
7. Rank and deduplicate:

   `python scripts/rank_news.py --profile <profile.json> --candidates <candidates.json> --seen <seen.json> --output <ranked.json> --now <ISO-8601>`

   For an explicitly requested draft preview only, add `--allow-draft`; never add `--update-seen`.
8. Reopen and independently check every selected story. Correct or remove unsupported summaries. Do not pad the digest with stale, weak, duplicative, or unresolved items.
9. Write a Japanese Markdown digest with direct links and near-claim citations. Explain relevance using approved topic labels only, never browsing-history language.
10. For an approved unscheduled run, save under `digests/YYYY-MM-DD.md`, then update seen only after the digest succeeds. A scheduled run must use `scheduled_run_guard.py commit` (or its two-phase equivalent), never `rank_news.py --update-seen`; failed and preview runs never mark items seen.

## Output contract

State collection timestamp, timezone, lookback, profile version/approval, stopping reason, and any allowed window expansion. Each story includes headline, publisher, publication date, event date when different, a concise verified summary, matching approved topics, direct sources, and material uncertainty.

Group reports about the same event. Enforce `max_per_domain`, avoid single-topic saturation when equally strong alternatives exist, and reserve at most a small exploration share for adjacent stories grounded in approved topics. Return fewer items when the evidence pool is weak.

## Side effects and scheduled runs

- Never modify profile topics, weights, confidence, intent, approval, or exclusions from news behavior.
- Do not create a schedule, background service, Slack post, email, subscription, or notification unless separately requested.
- A scheduled run is `scripts/scheduled_run_guard.py start` (validate, snapshot, lock) -> collection -> `scheduled_run_guard.py commit` (or `mark-digest` then `commit-seen`). Write the digest with `scheduled_run_guard.atomic_write_text`. Never use `rank_news.py --update-seen` in a scheduled run; failed and preview runs never mark items seen. The guard's budgets, journaling, and recovery rules are in [Multi-agent scheduled collection](references/multi-agent-scheduled-collection.md).
- The coordinator alone writes the digest and seen state; workers receive only the projection.
- When model selection is exposed and the user requests the quality-first route, use the strongest reasoning model available for independent workers. Stop at evidence convergence and hard safety limits; do not create unbounded duplicate work.
