# Report Output

The final deliverable should usually be a static HTML report. Markdown is useful as an intermediate artifact, but HTML is better for figures, charts, source tables, details sections, and multimedia notes.

## File layout

```text
report.html
report.md
sources.json or sources.csv
assets/
  overview.png
  chart.png
```

## Static HTML rules

- Make the report readable without JavaScript.
- Use embedded CSS or a single local stylesheet.
- Use a slightly larger body font than browser default: `17px` is the standard, with comfortable line height.
- Before writing final Japanese prose, invoke `human-writing-style` if available.
- Put conclusions at the top.
- Use clickable links for every cited source.
- Put source tables near claims or in a clear appendix.
- Use `details` for long logs, source lists, media notes, and caveats.
- Add `alt` text for images.
- For charts, include a nearby data table or at least the key values in text.
- Mention the research date and any freshness limitations.

## HTML section order

1. Title and research metadata
2. Scope and exclusions
3. Executive summary
4. Key findings
5. Visual overview
6. Evidence table
7. Media findings, if any
8. Caveats and open questions
9. Source appendix

## Minimal template

```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Research Report</title>
  <style>
    body { font-family: system-ui, sans-serif; font-size: 17px; line-height: 1.7; margin: 32px; max-width: 1080px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 8px; vertical-align: top; }
    figure { margin: 24px 0; }
    figcaption { color: #555; font-size: 0.92rem; }
    .summary { border-left: 4px solid #333; padding-left: 16px; }
  </style>
</head>
<body>
  <header>
    <h1>Research Report</h1>
    <p>Research date, target, timeframe, geography/language, exclusions.</p>
  </header>

  <section class="summary">
    <h2>Executive Summary</h2>
    <ul>
      <li>3-5 key conclusions.</li>
    </ul>
  </section>

  <section>
    <h2>Evidence</h2>
    <table>
      <thead>
        <tr><th>Claim</th><th>Evidence</th><th>Source</th><th>Date</th><th>Confidence</th></tr>
      </thead>
      <tbody>
        <tr><td></td><td></td><td><a href="">source</a></td><td></td><td></td></tr>
      </tbody>
    </table>
  </section>
</body>
</html>
```

## Final chat response

Keep the final chat short:

- Link the `report.html`.
- Mention major limitations.
- Mention whether sources and assets were produced.
- Apply `human-writing-style` to the final Japanese answer before sending it.
