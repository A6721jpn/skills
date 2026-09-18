# Multi-agent scheduled collection

Read this reference for scheduled runs or when independent subagents are available. Multi-agent work improves source coverage and adversarial verification; it does not relax profile, privacy, citation, or mutation boundaries.

## Coordinator boundary

One coordinator owns all state. Start the run with
`python scripts/scheduled_run_guard.py start --profile <profile.json> --seen
<seen.json> --state-dir <coordinator-state> --run-id <slug>
--run-timestamp <ISO-8601> --timezone <IANA-name>`. The guard validates the
approved profile, snapshots the profile and `seen.json`, computes SHA-256
hashes, records the configuration, and acquires an atomic exclusive lock.
The journal is written in `starting` state before lock acquisition, so a crash
cannot leave an unaccounted-for lock; recovery also reclaims a lock-only
orphan only when its same-host PID is proven dead.
Workers are stateless and receive no writable paths, state directory, profile
path, seen path, or owner token.

Project the profile to the safe fields listed in the consumer contract. Never send attention evidence, history coverage details, raw browsing evidence, local paths, or seen-state contents to workers.

The fixed coordinator quality preset is deliberately not profile-controlled:
`max_waves=4`, `max_pages=128`, `max_retries=16` total with at most
`max_retries_per_job=2`, `max_workers=32`, `max_topic_shards=12`,
`max_candidates=500`, and a `deadline_seconds=1800` wall-clock limit. Record
cumulative usage with the guard's `progress` command; an over-budget or
overdue run is aborted and its lock is released.

## Deterministic query plan

Sort eligible topics by `0.7 × weight + 0.3 × confidence`, then topic ID. The
v2 profile producer has already applied conservative work/transient penalties
to stored weights. A draft preview may locally apply the horizon/intent gate
to `user_confirmed:null`; approved `user_confirmed:true` is authoritative.
Build stable shard IDs from canonical plan JSON, not completion order.

Create these bounded lanes:

1. `primary`: official releases, standards bodies, regulators, research publishers, and project blogs.
2. `specialist`: reputable specialist reporting for impact and context.
3. `discovery`: broad approved-term searches across languages in profile order.
4. `verification`: direct-page headline, publisher, date, event date, and claim entailment.
5. `adversarial`: attempt to falsify launch/status/date/attribution claims and find omitted qualifiers.
6. `cluster`: judge only ambiguous same-event pairs after deterministic blocking.

When the requested quality-first model controls are available, use `gpt-5.6-luna` with `max` reasoning. Two independent discovery workers per shard and three voters for ambiguous verification or clustering are sufficient starting points. Add workers only for unresolved high-ranked candidates.

## Typed worker output

Discovery workers return the exact public candidate schema from `news-workflow.md`. Verification, adversarial, and clustering results go to a separate ephemeral typed ledger with fixed enums and canonical public URLs. Reject unknown fields and free-form operational metadata. Do not put worker IDs, prompts, votes, or provenance internals into the candidate file or digest.

A candidate qualifies only when its direct page supports the summary and date. Consequential claims should have independent-domain corroboration when practical. A failed or tied verification is omitted or explicitly labeled uncertain; it never receives an invented fact.

## Event clustering and selection

First group exact canonical URLs and near-identical titles deterministically. For remaining candidates, block possible pairs by topic and event/publication date. Ask cluster voters only about those pairs, accept an edge with a fixed two-of-three quorum, and build connected components in sorted pair order.

Choose one representative per event: primary source, verification strength, newer publication time, then canonical URL. Keep alternate verified sources only as context links.

Rank the consolidated pool deterministically. Enforce publisher/domain caps, try to represent multiple eligible topics when evidence quality is comparable, and reserve no more than 15% of slots for adjacent exploration grounded in approved topics. Exploration may vary domains or approved query terms; it may not invent interests.

## Convergence and limits

After each wave, fingerprint cluster assignments, qualified representative URLs, selected URL order, and rejection counts. Stop when either:

- the verified pool reaches three times the requested item count and all high-ranked candidates are resolved; or
- the selected set and cluster fingerprint are unchanged for two consecutive waves with no higher-priority shard remaining.

Also enforce maximum waves, pages, retries, workers, and wall-clock deadline. Retry malformed or timed-out worker output at most twice. More workers do not compensate for weak evidence. If limits are reached, publish fewer qualified stories and report the stopping reason.

## Commit protocol

1. Recheck the profile and initial-seen hashes; abort if either changed.
2. Write the digest atomically with `scheduled_run_guard.atomic_write_text`.
3. Call `scheduled_run_guard.py commit` (or `mark-digest` followed by
   `commit-seen`). The guard records `digest-committed` before touching seen
   state.
   Do not use `rank_news.py --update-seen` in this scheduled path.
4. Prepare and atomically update seen state idempotently under the same owner
   lock, then record `seen-committed` and release that exact lock.
   The guard persists `seen-prepared`, then rechecks the profile, initial-seen
   boundary, digest bytes, and selected-source bytes immediately before the
   atomic seen replace.
5. Remove temporary candidate, ranked, review, and cluster files only after
   `seen-committed`.

An invalid/draft profile, total worker failure, digest-write failure, profile
change, or initial-seen change causes no seen-state mutation. A crash after
digest creation can resume only the idempotent seen commit for the same run ID:
first prove the recorded lock PID is dead, then use `recover --resume`. A
normal `recover` aborts and releases the stale lock without touching seen
state. Wrong owner tokens, live locks, reparse-point paths, and conflicting
post-prepare seen hashes fail closed.

## Guard behavior (moved from SKILL.md)

- A scheduled run uses `scripts/scheduled_run_guard.py start` to validate and snapshot the approved profile and initial seen state, compute immutable SHA-256 hashes, acquire an atomic exclusive lock, and fix the run timestamp and timezone. Workers receive only the projection; they never receive writable paths or the owner token.
- The guard enforces the fixed quality preset `max_waves=4`, `max_pages=128`, `max_retries=16` total (`max_retries_per_job=2`), `max_workers=32`, `max_topic_shards=12`, `max_candidates=500`, and `deadline_seconds=1800`. Record cumulative progress with `scheduled_run_guard.py progress`; exceeding a budget or deadline aborts the run and releases the lock.
- Write the digest with `scheduled_run_guard.atomic_write_text`, then call `scheduled_run_guard.py commit` (or `mark-digest` followed by `commit-seen`). The guard rechecks profile and initial-seen hashes before commit, journals `digest-committed` before touching seen state, updates seen idempotently, and releases the exact owner lock. Use `recover --resume` only after a crashed owner is proven dead; recovery without resume aborts with no seen mutation.
- For v2, the profile producer has already applied conservative work/transient penalties to stored weights. The runtime intent gate is a draft-preview aid for `user_confirmed: null`; approved `user_confirmed: true` is authoritative, so that gate is intentionally not reachable in approved scheduled runs.
