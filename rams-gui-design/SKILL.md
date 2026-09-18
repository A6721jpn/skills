---
name: rams-gui-design
description: >-
  Rams/Braun-informed functionalist GUI design, implementation, or audit.
  Use only when the user or repository asks for a Rams-style (ラムス風・機能主義)
  UI direction; not for general GUI work.
license: "Apache-2.0; see LICENSE.txt"
metadata:
  version: "1.2.0"
---

# Rams-informed GUI design

Treat this as a functional design discipline, not a retro skin: a precise, calm instrument whose form follows the user's work. Do not imitate Braun products literally. Scale the effort to the task; a local styling fix needs none of the references below.

## Precedence

1. Required behavior, data integrity, safety, platform conventions.
2. Accessibility, localization, responsiveness, performance.
3. The repository's existing components and tokens.
4. The Rams-informed rules in this skill.
5. Remaining aesthetic preference.

An explicit user brief overrides the default visual language. Discipline a product's brand; do not erase it.

## Design contract

- Start from use: primary user, primary job, critical information, highest-risk action.
- Let grouping, hierarchy, and control-to-result mapping explain the interface.
- Use the fewest sufficient elements; neutral surfaces, one functional accent, little permanent elevation.
- Show actual state, latency, limits, permissions, and uncertainty. Never imply capability the system lacks.
- Derive spacing, size, radius, color, type, and motion from tokens, not scattered values.
- Resolve every state the product can enter, including recovery.
- Choose components for interaction semantics, never because they look characteristic.
- Ask only when a missing answer would change behavior, safety, information architecture, or platform choice; use this skill's defaults for reversible visual choices and proceed.

## References

Read only the row that changes the current decision.

| When you need to | Read |
|---|---|
| Interpret the philosophy or judge a Rams-specific exception | [references/rams-principles.md](references/rams-principles.md) |
| Choose or change information architecture, layout, or a workflow | [references/feature-archetypes.md](references/feature-archetypes.md) |
| Choose or refine controls, data displays, feedback, or component states | [references/component-patterns.md](references/component-patterns.md) |
| Establish or change tokens, type, color, geometry, elevation, icons, charts, motion | [references/visual-language.md](references/visual-language.md) |
| Implement or verify accessibility, responsiveness, rendering, performance | [references/accessibility-and-verification.md](references/accessibility-and-verification.md) |
| Run an explicit audit or a formal reduction pass | [references/quality-gates.md](references/quality-gates.md) |

When no design system exists, adapt [assets/rams-ui-tokens.json](assets/rams-ui-tokens.json); [assets/rams-ui-foundation.css](assets/rams-ui-foundation.css) is a web starting point, not a required stylesheet.

## Audit script

For a heuristic source pass, run from the project root:

```bash
python "<this skill's directory>/scripts/rams_ui_audit.py" <changed-ui-paths>
```

Every result is a warning to judge in context, not proof of quality or accessibility.

## Done means

For a substantial UI task: the primary job is immediately legible; component choice matches the interaction; relevant states and recovery paths exist; existing tokens and conventions are respected; no applicable hard fail from `quality-gates.md` remains; a reduction pass was run; and the handoff separates what was verified from what was not. Do not claim visual completion for rendering you did not inspect.

## Provenance

Derived from Anthropic's `frontend-design` skill (Apache-2.0). See `NOTICE.md`.
