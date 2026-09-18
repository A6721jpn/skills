# Rams quality gates

Use this reference for an explicit design review, a substantial UI task's final acceptance, or a formal reduction pass. Scale evidence to the task and risk: a small local fix needs only the applicable checks, while a new flow or high-consequence interface warrants the full gate.

## Hard fails

Resolve every applicable hard fail introduced by or within the accepted task scope before declaring that scope complete. Report pre-existing or out-of-scope hard fails separately rather than expanding the assignment without authorization:

- The primary task or current object is not immediately identifiable.
- A required action is available only through hover, color, drag, right-click, or an unlabeled icon.
- Keyboard operation is incomplete or focus is invisible/lost.
- A destructive or costly action has ambiguous scope or consequence.
- Loading, error, empty, offline, stale, permission, or recovery behavior is missing where the system can enter that state.
- Status or selection depends on color alone.
- Text/control contrast fails applicable requirements.
- The design hides latency, uncertainty, data age, limits, pricing, permission, or AI provenance that affects a decision.
- The interface uses a decorative motif or effect with no functional rationale.
- Multiple primary accents or competing focal points make hierarchy unclear.
- Every group is placed in a card despite no independent object/action semantics.
- The implementation introduces a new component system where the existing one could satisfy the task.

## Ten-principle check

After the hard fails are clear, name the weakest one or two of Rams's ten principles (see `rams-principles.md`) for this result and state the concrete evidence. Do not produce a numeric score; it is not evidence and does not replace the product's own acceptance criteria for critical or regulated workflows.

## Reduction pass

After the feature works, look for containers, labels, icons, colors, type sizes, animations, confirmations, options, and dependencies that can go without degrading comprehension, accessibility, safety, efficiency, or useful character. Remove what qualifies, restore anything whose removal makes the task worse, and if nothing can go, say so in the handoff.

## Functional-rationale ledger

For a material exception to the visual boundaries, record a concise rationale when the decision is not already explained by the user brief, platform convention, or product requirement:

| Decision | Functional reason | Alternative rejected | Verification |
|---|---|---|---|
| gradient, shadow, large radius, animation, extra accent, custom widget, or retro motif | what information or operation it improves | why a simpler pattern fails | screenshot, test, usability observation, or product requirement |

If a decision has no defensible functional reason, remove it.

## Audit output format

For a review request, report findings in this order:

1. **Hard fails**, with file/component/state and concrete consequence.
2. **High-value corrections**, ordered by user impact.
3. **Weakest principles**, with one sentence of evidence each.
4. **Reduction candidates**, each with expected benefit and risk.
5. **Verification gaps**, including unrendered states or untested inputs.

Avoid vague feedback such as “make it cleaner.” Name the exact hierarchy, component, token, state, or behavior to change.

## Heuristic script

Run:

```bash
python "<skill-dir>/scripts/rams_ui_audit.py" <file-or-directory> [more paths]
```

Useful options:

```bash
python "<skill-dir>/scripts/rams_ui_audit.py" src --format json
python "<skill-dir>/scripts/rams_ui_audit.py" src --strict
python "<skill-dir>/scripts/rams_ui_audit.py" src --max-files 2000
```

The script flags patterns such as backdrop blur, decorative gradients, large or pill radii, transition-all, infinite animation, removed focus outlines, excessive raw colors, and some non-semantic clickable elements. Review context before changing code; exceptions may be valid.
