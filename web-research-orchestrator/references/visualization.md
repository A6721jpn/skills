# Visualization

Use visuals only when they clarify the research. Avoid decorative images.

## Use Python for exact data

Use Python or Code Interpreter for:

- bar charts
- line charts
- scatter plots
- distributions
- tables from CSV/JSON
- charts with units, axes, legends, dates, or exact labels

Keep:

- raw data
- processed data
- chart generation code when practical
- generated chart image
- source notes

## Use Imagegen for explanatory diagrams

Use Imagegen for:

- concept maps
- process diagrams
- stakeholder maps
- comparison diagrams
- simplified report summary visuals

Do not use Imagegen for:

- exact numeric graphs
- dense labels
- small text
- source-heavy visuals
- reproducing specific logos or copyrighted layouts unless the user has provided rights/permission

## Imagegen specialist prompt template

```text
Purpose: Explain [what] inside a sourced HTML research report.
Audience: [general / expert / decision-maker].
Diagram type: [concept map / process flow / comparison map / stakeholder map].
Verified points:
1.
2.
3.
4.
5.
Allowed labels: [max 8 short labels].
Avoid: unverified numbers, dense text, brand logos, unsupported claims.
Style: clear, editorial, report-friendly, high contrast, minimal labels.
Output: one image. Source notes will be outside the image in HTML.
```

## Review generated images

Before embedding an Imagegen output:

- Check that it does not add unsupported claims.
- Check that labels match verified text.
- Check that it is readable at report size.
- Add HTML `alt` text and a concise caption.
