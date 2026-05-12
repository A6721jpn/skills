# Agent Patterns

Use specialist roles for deep, broad, or multimedia-heavy research. If actual subagent tools are unavailable or not allowed by the active environment, run these roles sequentially in the main agent.

## Recommended roles

- `Research lead`: scope, plan, integration, final report.
- `Source scout`: official, primary, regulatory, academic, and company sources.
- `Broad web scout`: news, trade publications, explainers, criticism, counterpoints.
- `Media scout`: YouTube, podcasts, webinars, interviews, transcripts, show notes.
- `Data analyst`: tables, numeric extraction, Python chart inputs, chart outputs.
- `Imagegen specialist`: explanatory diagrams from verified visual brief only.
- `Skeptic/checker`: contradiction checks, outdated information, missing evidence, overclaims.

## Delegation rules

- Split by source type or specialty, not by duplicate query.
- Give each role a bounded output schema.
- Ask for source URLs, dates, confidence, and caveats.
- Do not let specialist conclusions flow directly into the report; the Research lead must verify and integrate.

## Output schema for research roles

```text
claim:
evidence:
source_url:
source_title:
published_or_updated:
source_type:
confidence:
caveat:
```

## Imagegen isolation

Never give the Imagegen specialist:

- raw web pages
- hidden or pasted website text
- unverified notes
- full research logs
- source lists with irrelevant details
- private data or local files

Give only:

- purpose
- audience
- diagram type
- verified points, maximum 5
- allowed labels, maximum 8
- visual constraints
- explicit exclusions
- output size/aspect ratio
