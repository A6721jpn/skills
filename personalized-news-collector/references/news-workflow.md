# News workflow

## Query planning

Plan a small set of broad queries across the highest-weight topics. Combine a topic with freshness or announcement terms only when useful. Prefer official domains listed in `preferred_primary_domains`, official project blogs, standards bodies, regulators, research publishers, and reputable specialist reporting.

For a draft-preview v2 topic with `user_confirmed: null`, compute a local planning score:

```text
base = 0.45 × weight + 0.25 × confidence + 0.20 × long_score + 0.10 × short_score
intent_gate = clamp(1 - 0.35 × work_like - 0.40 × transient, 0.35, 1)
planning_score = base × intent_gate
```

The v2 profile producer already bakes conservative work/transient penalties into
stored weights. For `user_confirmed: true`, do not apply the runtime intent
gate; the explicit decision is authoritative. Approved scheduled profiles use
that path intentionally. Use the score only to allocate search effort. It
does not change the stored profile.

Do not send profile evidence counts, private names, internal domains, raw searches, or browser-derived phrases to the web.

## Candidate JSON

Create a UTF-8 JSON array with at most 500 candidates. Each object has exactly:

```json
{
  "title": "Direct article headline",
  "url": "https://publisher.example.com/article",
  "source": "Publisher",
  "published_at": "2026-08-24T08:00:00+09:00",
  "event_at": "2026-08-24T00:00:00+09:00",
  "interest_ids": ["cad-cae-manufacturing"],
  "source_quality": "primary",
  "summary": "A source-grounded candidate summary."
}
```

`source_quality` is `primary`, `specialist`, `reputable`, or `other`. `event_at` is optional. Publication time is required; if only a date is known, use a local-noon timestamp and disclose date-only precision in the final digest. When supplied, `event_at` must be within plus or minus 366 days of `published_at` and no more than 366 days after the fixed run timestamp; reject implausible event dates.

Use only these fields. Supply a direct public HTTPS article URL whose DNS hostname and path identify the story. The ranker requires a query-free URL and rejects IP-literal, private, loopback, local, reserved, credential-bearing, query-bearing, and non-HTTPS URLs; it discards fragments before persistence. It also copies an explicit field whitelist and strips every unknown candidate field without recording its name or value, so accidentally attached private metadata cannot propagate to ranked output.

Deduplicate `interest_ids` before writing. Keep verification votes, worker metadata, alternate sources, and event-cluster judgments in a separate ephemeral ledger; they are not candidate fields.

Candidate files contain public news data, not Chrome history. Delete temporary candidate and ranked files after a successful run unless the user asks to keep them.

## Date and source verification

- Open the direct page; do not cite search-result pages.
- Verify publication date from the page or publisher metadata.
- Treat a materially updated old article as old unless the update contains the new event being summarized.
- For breaking or consequential claims, use a second independent source when practical and label unresolved disagreement.
- Prefer an official release for what changed and an independent source for impact or context.
- Do not quote more than needed; summarize in original wording.

## Ranking and diversity

The ranker combines topic weight/confidence, recency, and source quality. It rejects query-bearing story URLs, removes previously seen URLs, exact or near-duplicate titles, future-dated items, stale items, excluded domains, and excess items from one publisher name or registrable publisher domain, including its subdomains.

Consolidate same-event reports before ranking when multiple workers found them. After ranking, prefer topic breadth when similarly scored candidates exist, while never admitting a weaker or unverifiable story merely to fill a category. Exploration is capped at 15% and must remain grounded in approved topic terms.

If too few items qualify, first return fewer. Expand the lookback window only when the user allows it or the profile explicitly sets a larger window, and disclose the expansion.

## Digest format

Start with one compact line giving collection time, lookback, item count, and profile state. Then list stories in rank order. Each story should have:

1. linked headline and publisher;
2. publication date;
3. two or three Japanese sentences summarizing verified facts;
4. `おすすめ理由:` followed by approved topic labels;
5. a second source only when it adds verification or important context.

End with a short `見送り` note only when candidates were excluded for staleness, duplication, weak sourcing, or insufficient relevance. Do not reveal private browsing evidence.

## Seen state

Default to `seen.json` in the personal-news data root. It stores only canonical public article URLs, title fingerprints, and first-seen timestamps. Update it only after an approved digest has been saved successfully.
