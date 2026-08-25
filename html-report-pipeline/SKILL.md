---
name: html-report-pipeline
description: Create or revise a source-grounded standalone HTML report by chaining evidence-based writing, concise visual explanation, stale-idea guarding, purposeful diagrams, semantic HTML, artifact sanitization, and structural/browser QA. Use for technical reports, design reviews, research summaries, decision memos, and other reports that should be delivered as one self-contained HTML file.
---

# Html Report Pipeline

Use this as the orchestration layer for a report request. The output is a
standalone HTML deliverable; the intermediate production context must not leak
into the deliverable.

## Invocation and scope

- Apply automatically when the user asks for an HTML report, a report with
  charts/diagrams, a technical explanation intended for delivery, or a revision
  of an existing report.
- The user can explicitly invoke it with `/html-report-pipeline <topic>`.
- Respect an existing output path and existing files. If no path is given,
  choose a task-owned report path such as `reports/<slug>.html` and do not
  overwrite an existing file without explicit approval.
- Default to Japanese when the request is Japanese; preserve the requested
  language otherwise. Use reasonable labeled assumptions unless a missing
  decision, audience, or scope choice would change the result; then ask one
  concise question before drafting.

## Skill routing

Run the stages in this order, keeping the same report brief, evidence ledger,
and artifact path across stages:

1. **Brief and evidence** — Apply the `technical-report-authoring` workflow.
   Define purpose, audience, decision, scope, conditions, exclusions, known and
   missing inputs, and output format. Research current or source-sensitive
   claims from authoritative primary sources. Classify every material statement
   as `Published`, `Assumption`, `Calculation`, or `Inference`; show equations,
   units, criteria, and applicability for derived values.
2. **Show-me visual explanation** — Apply the `show-me` skill to choose the
   smallest visual view that makes the report's key relationship understandable.
   Keep prose brief and place the view beside the claim it explains. Select
   pseudocode for logic, a call tree for runtime flow, a shallow file tree for
   responsibility, a diff for change shape, Mermaid for component/data flow,
   or a focused standalone HTML artifact only when the relationship is too
   dense for a compact diagram. Use real labels and evidence; a visual is an
   explanation aid, not a substitute for citations, equations, limitations, or
   verification criteria. Do not turn every report into a decorative infographic.
3. **Pink Elephant Guard (conditional)** — Apply `pink-elephant-guard` when
   the conversation contains a rejected, deleted, corrected, or forbidden idea
   and the output is a reader-facing report. Separate the current approved
   state from rejected history and required visible exceptions before drafting.
   Generate from the current state, then scan headings, prose, tables, captions,
   alt/ARIA text, inline SVG labels, IDs, and interactive states for literal,
   semantic, rationale, attention, and visual leakage. Do not hide required
   safety, legal, regulatory, audit, comparison, or accessibility information.
   If a scan fails, regenerate from the clean brief instead of deleting a few
   leaked words from the contaminated draft.
4. **Narrative and final diagram plan** — Draft only the content needed to
   support the decision. Treat `show-me` as the representation selector and
   `visualize` as the composition and presentation guide: the former chooses
   the smallest useful view, while the latter helps make a chart or diagram
   readable, responsive, accessible, and theme-aware. Add a diagram only when
   it makes a relationship, sequence, hierarchy, comparison, geometry, or
   trend easier to understand. For a standalone report, embed the final
   diagram as inline SVG or semantic HTML inside the report; do not return an
   in-conversation visualization reference as the report itself. Never invent
   data or use color as the only encoding.
5. **HTML assembly** — Apply the `html` skill for semantic, accessible,
   minimal markup: correct landmarks and heading hierarchy, native controls,
   explicit labels, meaningful image handling, and no unnecessary wrapper
   elements. Then use the installed
   `technical-report-authoring/assets/technical-report-template.html` as the
   starting point. Preserve `data-report-section`, `data-evidence-type`,
   responsive tables, equation blocks, focus-visible styles, print styles,
   UTF-8, viewport metadata, unique IDs, and heading hierarchy. Replace every
   template token. Keep the report self-contained: inline CSS/SVG/JavaScript
   only when required, with no network dependency for the delivered report.
6. **Sanitize** — Apply `sanitize-artifacts` to the complete HTML. Remove
   prompts, conversation residue, internal reasoning, tool/process notes,
   implementation constraints, and corrective feedback from user-facing
   content. Preserve necessary limitations, assumptions, citations, and
   verification requirements as audience-facing report content.
7. **QA gate** — Run the report validator from the technical-report skill:
   `python scripts/validate_report.py <report.html>`. Fix all errors and rerun
   until it reports `OK`. Then inspect the rendered report at desktop, narrow,
   and print widths. Use the available browser-control capability or an allowed
   local HTTP route when possible; a static validator pass is not a browser
   pass. Record browser inspection as `verified` or `unverified` rather than
   inferring it from file existence or a successful script exit.

## Required report contract

Every complete report should contain these semantic sections, with visible
headings adapted to the requested language:

1. Executive summary
2. Context and decision
3. Scope, conditions, and assumptions
4. Method and source quality
5. Published data
6. Calculation method
7. Results and interpretation
8. Recommendations
9. Verification plan
10. Limitations and unresolved items
11. References

Use the report template's semantic attributes even when a short report merges
visible sections. Put citations beside supported claims and repeat complete
source details in the references section. Keep screening values visibly
separate from confirmed product, material, regulatory, or test data.

## Diagram rules

- Prefer one or two high-information diagrams over decorative graphics.
- Select the smallest useful visual: flow for causal steps, timeline for
  sequence, tree for hierarchy, table for exact mappings, chart for measured
  quantities, and annotated SVG for geometry or mechanism.
- Give every diagram a concise title/description, readable labels, units where
  applicable, and a non-color alternative such as text, shape, line style, or
  direct labels.
- Make SVGs responsive and keyboard/print friendly. Avoid clipped labels,
  fixed-width canvases, unexplained legends, and external image/font/runtime
  dependencies.

If the user asks for a very simple explanation, let the selected `show-me`
view carry the first explanation with short adjacent prose, while retaining
the evidence types, limitations, and source traceability required for the
report.

## Delivery boundary

Before replying, confirm the final HTML path, validator result, and browser/print
inspection status. If a gate could not be run, say exactly which one is
unverified and why. Do not claim engineering, scientific, regulatory, or
physical validation merely because the HTML is attractive or structurally
valid. Keep process commentary outside the delivered HTML.
