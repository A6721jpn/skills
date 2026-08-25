---
name: chrome-preference-profiler
description: Create or refresh a reviewable, privacy-minimized news-interest profile from the user's explicitly authorized Chrome browsing history. Use when the user asks to infer or document preferences from Chrome history; do not use for current-news collection, raw-history export, deletion, cookies, passwords, sessions, or general browser control.
---

# Chrome Preference Profiler

Create two synchronized artifacts from the connected Chrome profile:

- `profile.json`: the machine-readable source of truth for downstream news collection.
- `profile.md`: a concise review document explaining inferred topics, attention-proxy quality, time horizon, intent uncertainty, confidence, coverage, and approval state.

## Authorization and privacy boundary

- Read history only when the user explicitly authorizes Chrome-history analysis. Recurring history refresh requires separate, explicit authorization for repeated reads.
- Use the installed Chrome-control skill and only the selected Chrome handle, conventionally `chrome.user.history()`. Never inspect Chrome profile folders or SQLite databases directly.
- Never inspect cookies, passwords, autofill, sessions, downloads, bookmarks, extensions, local storage, or account data, and never modify browsing data.
- Keep raw history inside one function-local sanitizer call. Never write, print, return, log, prompt with, or send to an agent any raw URL, query, title, hostname, exact visit time, private name, or search term.
- Do not infer sensitive personal traits. Treat frequency and the estimated attention proxy as evidence of relevance, not proof of liking.
- Only fixed, reviewed public topic IDs and search terms may exit the sanitizer. A high unmapped ratio means taxonomy coverage is weak; it is not permission to expose raw text for open-ended topic discovery.

## Workflow

1. Read [Chrome history analysis](references/chrome-history-analysis.md) before accessing Chrome.
2. Resolve the data root. Use `$CODEX_HOME/user-data/personal-news` when `CODEX_HOME` is set; otherwise use the platform's `.codex/user-data/personal-news` directory under the user's profile. Honor an explicit alternative path.
3. Default to a requested 365-day window, make one bounded history call, and record the actual returned range. Do not promise that Chrome will return the full period.
4. Run `scripts/sanitize_history_aggregate.mjs` inside the browser-control runtime. It produces an `interest-profile/v2` draft containing only aggregate signals. The adjacent-visit gap is an attention proxy, never measured dwell time.
5. If independent subagents are available, read [Aggregate ensemble review](references/ensemble-review.md). Send only the validated aggregate draft to reviewers, merge their typed reviews with `scripts/merge_profile_reviews.py`, and stop at statistical convergence. Never give a reviewer Chrome/history/browser access.
6. If no subagent mechanism is available, keep the deterministic baseline, leave `inference.ensemble.status` as `not-run`, and lower no confidence merely because orchestration is unavailable.
7. Preserve explicit user decisions over inference: confirmed topics, exclusions, intent corrections, horizon corrections, and user-set weights remain authoritative. A refresh that changes inferred content returns to `draft` unless the user explicitly approves it.
8. Read [Profile contract](references/profile-contract.md), validate, render, and check exact synchronization:

   `python scripts/validate_profile.py <path-to-profile.json>`

   `python scripts/render_profile.py <path-to-profile.json> <path-to-profile.md>`

   `python scripts/render_profile.py --check <path-to-profile.json> <path-to-profile.md>`

9. Report requested versus actual coverage, attention-proxy coverage/status, taxonomy coverage, and ensemble convergence. Release safe bindings and reset the browser runtime when practical.

## Approval and scheduled refresh

- A draft profile is usable only for an explicitly requested one-off preview. Normal, recurring, or unattended news collection requires an approved profile.
- A scheduled history refresh must write a dated draft candidate beside the current profile; it must not overwrite the last approved `profile.json`. News collection continues using that approved file until the user reviews the candidate.
- When the user corrects a draft, preserve those corrections but keep it draft until separate explicit approval. On approval, every topic must have `user_confirmed: true` or `false`, and at least one confirmed topic must be news-eligible.
- Never learn silently from missing clicks or passive behavior. Explicit feedback such as boost, mute, work-only, temporary, or long-term may update the next draft.
- When model selection is exposed and the user requests the quality-first multi-agent route, prefer `gpt-5.6-luna` reviewers with `max` reasoning. Availability and concurrency are runtime capabilities, not assumptions the skill may claim as guarantees.

## Longer coverage and handoff

If the connected history surface returns less than requested, explain the shortfall. A user-supplied Chrome or Google activity export requires a separate authorized step; never navigate to My Activity or request Takeout automatically.

The paired `$personalized-news-collector` consumes validated v1 or v2 profiles and must never receive raw history.
