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
- The result was not rendered or otherwise visually inspected when tools were available.

## Ten-principle score

Score each dimension 0, 1, or 2.

- **0:** contradicted or materially incomplete;
- **1:** acceptable but with a clear weakness;
- **2:** strong and evidenced.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Innovation | novelty without task benefit | modest improvement | technology meaningfully reduces friction or improves control |
| Usefulness | primary job impaired or unclear | job works with friction | primary job is obvious, efficient, accurate, and recoverable |
| Aesthetic quality | inconsistent or unresolved | coherent | proportion, type, spacing, and detail reinforce use |
| Understandability | control/state mapping unclear | learnable | structure, labels, state, and consequence are self-evident |
| Unobtrusiveness | chrome competes with work | mostly calm | user content and task dominate |
| Honesty | hides limits or consequence | adequate disclosure | capability, state, uncertainty, and consequence are explicit |
| Longevity | trend-dependent or brittle | maintainable | semantic, conventional, and resilient to change |
| Thoroughness | relevant states/details missing | minor gaps | states, copy, units, inputs, and edge cases are resolved |
| Resource restraint | gratuitous effects/dependencies | reasonable | visual and computational cost is intentionally minimized |
| Minimality | redundant elements remain | mostly reduced | nothing nonessential remains and hierarchy is stronger |

Default diagnostic target for a substantial UI task:

- no hard fails;
- total score at least 17/20;
- no dimension scored 0.

Treat this score as a design heuristic, not proof of accessibility, safety, usability, or regulatory compliance. For critical or regulated workflows, use the product's approved acceptance criteria and evidence; do not substitute a higher Rams score for domain verification.

## Reduction pass

Perform the reduction pass after the feature works and has been visually inspected.

For each screen or major component, ask:

1. Can one container be replaced by spacing or a divider?
2. Can one label be removed because hierarchy already explains it?
3. Can one icon be removed or paired with clearer text?
4. Can one color be returned to neutral?
5. Can one type size or weight be merged into the scale?
6. Can one animation be removed or shortened?
7. Can one advanced option move behind deliberate disclosure?
8. Can one confirmation become undo, or one unnecessary confirmation disappear?
9. Can one status be localized closer to the affected object?
10. Can one dependency, asset, or DOM layer be removed?

Remove one candidate at a time and verify that comprehension, accessibility, safety, efficiency, and useful character do not degrade. Restore the element if the task becomes worse.

If no candidate can be removed safely, keep the current design and record that the reduction pass found no justified removal.

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
3. **Ten-principle score**, with one sentence of evidence per weak dimension.
4. **Reduction candidates**, each with expected benefit and risk.
5. **Verification gaps**, including unrendered states or untested inputs.

Avoid vague feedback such as “make it cleaner.” Name the exact hierarchy, component, token, state, or behavior to change.

## Heuristic script

Run:

```bash
python scripts/rams_ui_audit.py <file-or-directory> [more paths]
```

Useful options:

```bash
python scripts/rams_ui_audit.py src --format json
python scripts/rams_ui_audit.py src --strict
python scripts/rams_ui_audit.py src --max-files 2000
```

The script flags patterns such as backdrop blur, decorative gradients, large or pill radii, transition-all, infinite animation, removed focus outlines, excessive raw colors, and some non-semantic clickable elements. Review context before changing code; exceptions may be valid.
