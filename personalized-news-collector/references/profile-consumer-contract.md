# Profile consumer contract

The collector accepts validated `interest-profile/v1` and `interest-profile/v2` JSON produced by the paired profiler or an equivalent source.

## Safe projection

Validate locally before any web request. Workers and search planning may receive only:

- eligible topic IDs and labels;
- weight and confidence;
- for v2, intent, time horizon, and aggregate horizon scores needed for ranking;
- broad `news_query_terms`;
- reviewed public preferred domains;
- exclusions, source policy, language order, and digest defaults.

Generate the projection with `scripts/project_worker_profile.py` and pass the
`profile_sha256` recorded by the scheduled guard as
`--expected-profile-sha256`. Its
`worker-profile/v1` output contains only eligible topic records and the public
exclusions/source/digest fields above, plus the fixed run budgets. It omits
coverage, privacy, evidence, attention, raw history, approval metadata, local
paths, and v2 intent probabilities. The output is written atomically beneath a
coordinator-owned `--output-root`; reject instruction-like text and reparse
points rather than forwarding them to workers.

Never expose coverage evidence, attention counts/minutes, intent probabilities, Chrome history, private source data, local paths, or internal domains to web search or collection workers. The coordinator may use v2 aggregate scores locally but does not reveal them in the digest.

## Required behavior

- Reject unknown fields and unknown schema versions before search.
- Use only topics where `news_eligible` is true and `user_confirmed` is not false.
- Send only validated broad query terms and explicit user terms to public search.
- Use `weight` and `confidence` for v1 ranking. The v2 profile producer already
  bakes conservative work/transient penalties into stored weights; use the
  projected long/short horizon scores for planning. A draft preview may apply
  the runtime gate to `user_confirmed: null`; approved `user_confirmed: true`
  is authoritative and intentionally bypasses that gate.
- Respect all topic, term, and domain exclusions.
- Never mutate the profile from clicks, skips, article content, or agent suggestions.

## Approval and freshness

- `approved`: usable for direct, scheduled, or unattended runs.
- `draft`: usable only for an explicitly requested one-off preview; label it and never update `seen.json`.

An old profile is not automatically invalid. Warn when it is more than 90 days old, but never refresh it by reading Chrome unless the user separately asks and has authorized that read.

For scheduled runs, hash the profile snapshot before search and again before committing seen state. A change aborts the commit so one run never mixes two preference versions.
