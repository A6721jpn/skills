# Chrome history analysis

Read this reference only when an authorized history analysis is about to run.

## Supported access path

1. Read and follow the installed Chrome-control skill.
2. Select Chrome explicitly and name the browser session.
3. Load the executable sanitizer from its resolved absolute file URL into the existing browser-control Node runtime.
4. Call the selected Chrome handle, conventionally `chrome.user.history()`, once with bounded `from`, `to`, and a sufficiently high `limit`.
5. Record only the sanitized coverage summary: requested dates, actual oldest/newest dates, entry count, and whether the limit was reached.

Do not fall back to direct Chrome profile-file access. If the browser extension is unavailable, explain how to connect Chrome and stop.

## Function-local raw-response pattern

Keep raw rows inside an async function-local variable and expose only the sanitizer result:

```js
const { sanitizeChromeHistory } = await import(resolvedSanitizerFileUrl);
const safeProfile = await (async () => {
  const rawRows = await chrome.user.history({ from, to, limit: 50000 });
  return sanitizeChromeHistory(rawRows, {
    requestedStart,
    requestedEnd,
    requestedDays,
    historyQueryLimit: 50000,
    retentionLimitDays: 90,
    generatedAt,
    timeZone,
  });
})();
nodeRepl.write(safeProfile);
```

Never assign the raw array to a global binding, inspect or print an element, serialize it, include it in an exception, or send it to a subagent. Do not replace the sanitizer with an improvised dumper. After transferring the safe profile, clear the safe binding and reset the runtime when practical.

If the sanitizer reports zero usable timestamps, no stable public topic, or a privacy/schema failure, do not write a profile.

## Deterministic filtering

The sanitizer excludes or heavily downweights:

- `chrome://`, `file://`, localhost, loopback, invalid URLs, and extension pages;
- authentication, account, password-manager, checkout, cart, billing, and banking pages;
- email, private cloud documents, calendars, private workspaces, team chat, and internal hosts;
- search-engine navigation and raw query strings;
- redirect pages, generic home pages, and repeated refreshes;
- exact project, customer, person, restaurant, route, or document names.

Only fixed reviewed taxonomy IDs, labels, rationales, public query terms, primary domains, and aggregate numbers may leave the sanitizer. The original text must never appear in the profile, agent prompts, logs, diagnostics, or web searches.

## Attention proxy

History does not measure foreground reading time. The sanitizer estimates an adjacent-visit attention proxy:

- sort all usable visit timestamps in memory, including excluded pages that can end the prior interval;
- ignore negative gaps and session gaps over 30 minutes;
- cap each contribution at 10 minutes and each topic/day/domain at 30 minutes;
- heavily reduce gaps under 5 seconds, reloads, redirects, same-page transitions, and unknown device scope;
- treat the last event in a session as unobservable, not zero attention;
- mark aggregate URL-history rows or sparse sequences as `limited` rather than pretending they are visit-level telemetry.

Persist only total capped minutes, observable visit count, coverage ratio, engaged-day count, score, and band. Never persist a per-page estimate or timestamp sequence.

## Temporal and intent signals

For every taxonomy topic, aggregate:

- capped visits, distinct days, domain diversity, and recency;
- 7-day and available-history recency-decayed scores;
- stability, trend, and burstiness;
- conservative work-like, transient, and durable probabilities from fixed rule metadata and aggregate shape.

`work_like` describes browsing shape, never occupation, employer, or identity. Absence is not negative preference evidence. A recent two-day burst may enter the draft as `emerging`, but it must receive lower confidence than cross-day, cross-domain evidence.

## Coverage interpretation

- Under 14 observed days: `insufficient`.
- 14–45 days: `provisional`.
- More than 45 days: `usable` within the returned window.

Also report `taxonomy_coverage_ratio`. Low coverage means the fixed safe taxonomy cannot explain much of the public history; ask for explicit user-supplied interests instead of exposing raw terms for discovery.

Never claim full-year analysis unless the returned data actually spans it.
