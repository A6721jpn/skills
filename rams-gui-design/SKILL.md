---
name: rams-gui-design
description: >-
  Design, implement, refactor, or audit interfaces with a Dieter-Rams-informed
  functionalist direction. Use when the user requests Rams/Braun-like,
  restrained, industrial, timeless, disciplined, or minimal GUI design,
  including ディーター・ラムス, ラムス風, ブラウン風, 機能主義, or ミニマルGUI,
  or when repository instructions declare this the default UI direction. Do not
  trigger merely because a task involves a GUI.
license: "Apache-2.0; see LICENSE.txt"
metadata:
  version: "1.1.0"
---

# Rams-informed GUI design

Treat this as a functional design discipline, not a retro skin. Make the interface feel like a precise, calm instrument whose form follows the user's work. Do not imitate Braun products literally unless a physical metaphor is genuinely useful.

Apply this workflow in proportion to the task. A local copy, styling, or component fix does not require an unrelated redesign, every reference, a full scorecard, or multi-viewport capture. A new flow, substantial implementation, or explicit audit warrants broader analysis and verification.

## Precedence

Apply constraints in this order:

1. Preserve required behavior, data integrity, safety, and platform conventions.
2. Meet accessibility, localization, responsiveness, and performance requirements.
3. Reuse the repository's established components and tokens unless they prevent the first two items.
4. Apply the Rams-informed rules in this skill.
5. Follow any remaining aesthetic preference.

An explicit user brief overrides the default visual language. Do not erase a product's brand identity; discipline it through the rules below.

## Core design contract

1. **Start from use.** Identify the primary user, primary job, critical information, and highest-risk action before styling.
2. **Make structure visible.** Let grouping, sequence, hierarchy, and control-to-result mapping explain the interface.
3. **Use the fewest sufficient elements.** Remove decoration, containers, labels, and controls only while understanding, safety, and speed remain intact.
4. **Keep the product honest.** Show actual state, latency, limits, permissions, consequences, and material uncertainty. Never imply capability the system does not have.
5. **Keep the interface quiet.** Use neutral surfaces, restrained typography, one dominant functional accent, and little or no permanent elevation.
6. **Make values deliberate.** Derive spacing, size, radius, color, type, and motion from existing or adapted tokens instead of scattering arbitrary values.
7. **Finish relevant behavior.** Use durable native or established components and resolve every state the product can actually enter, including recovery paths.
8. **Spend resources carefully.** Avoid decorative assets, excessive JavaScript, large animation libraries, and effects that add visual or computational pollution.
9. **Run a reduction pass.** Remove an element only when doing so improves clarity without reducing comprehension, accessibility, safety, efficiency, or useful character. If nothing can be removed safely, retain the design and record that conclusion.

## Reference routing

Load only the references that change the current decision. Do not load a reference merely because this skill was selected.

| Current task | Read |
|---|---|
| Interpret the philosophy or evaluate a Rams-specific exception | [references/rams-principles.md](references/rams-principles.md) |
| Choose or substantially change information architecture, layout, or a workflow | [references/feature-archetypes.md](references/feature-archetypes.md) |
| Choose or refine interactive controls, data displays, feedback, or component states | [references/component-patterns.md](references/component-patterns.md) |
| Establish or materially change tokens, typography, color, geometry, elevation, icons, charts, or motion | [references/visual-language.md](references/visual-language.md) |
| Implement or substantially verify accessibility, responsiveness, rendering, or performance | [references/accessibility-and-verification.md](references/accessibility-and-verification.md) |
| Perform an explicit audit, substantial final acceptance, or formal reduction pass | [references/quality-gates.md](references/quality-gates.md) |

A small, well-bounded change may need no supporting reference. When several rows apply, read only those rows.

## Workflow

### 1. Inspect before changing

- Detect the framework, platform, component library, routing model, styling system, and relevant test setup.
- Read the smallest set of design-system files, tokens, component stories, screenshots, and requirements that governs the task.
- Locate the files that own the feature; do not replace the product's system merely to impose a look.
- For an existing UI, inspect a rendered baseline and existing keyboard/accessibility behavior when tools and scope permit.

### 2. Establish the feature contract

Determine, internally or in the implementation plan:

- user, context, and single primary job;
- essential data, units, and current object;
- primary, secondary, and destructive actions;
- frequency of use and appropriate density;
- applicable latency, failure, offline, permission, empty, stale, and recovery conditions;
- device, input mode, localization, and accessibility constraints.

Ask a question only when a missing answer would change behavior, safety, information architecture, or platform choice. Use this skill's defaults for reversible visual choices and proceed.

### 3. Choose the interaction model

- Translate the request into user verbs such as orient, inspect, choose, enter, adjust, compare, search, execute, monitor, recover, or approve.
- Choose the simplest component and layout pattern that preserves clarity and efficiency.
- Keep control, label, current value, unit, and resulting status spatially close.
- Prefer progressive disclosure for secondary complexity, but never hide the primary path.
- When no archetype fits, compose the feature from its data objects, user verbs, system states, and risks instead of inventing an ornamental pattern.

Choose components for their interaction semantics, never because they look characteristic. Apply the Rams-informed visual language after the interaction model is correct.

### 4. Adapt the visual system and implement

- Preserve existing semantic tokens and accessible components when possible; remap token values before creating a parallel system.
- When no usable system exists, adapt [assets/rams-ui-tokens.json](assets/rams-ui-tokens.json). For web work, [assets/rams-ui-foundation.css](assets/rams-ui-foundation.css) is a starting point, not a mandatory stylesheet.
- Preserve public component APIs unless requirements demand a change.
- Use native semantics first and add ARIA only where native semantics are insufficient.
- Keep one clear primary action per task region, de-emphasize secondary actions, and isolate destructive actions.
- Use direct, consistent labels that name the user's action or object.
- Prefer sections, alignment, rules, whitespace, and tonal shifts over redundant cards, shadows, or decorative containers.
- Use an icon-only control only when its symbol is conventional or the control is repeated frequently. Always provide an accessible name; use a visible label when meaning would otherwise remain ambiguous.
- Keep motion brief and causal, respect reduced-motion preferences, and preserve task priority when layouts reflow.

### 5. Verify and reduce

Verify the behavior, states, viewports, and input modes relevant to the change and its risk. For substantial implementation or acceptance, use the routed verification and quality-gate references.

When browser or screenshot tools are available and the task changes appearance, inspect the rendered result rather than judging source alone. Do not claim visual completion when rendering was not verified; state the limitation in the handoff.

For a useful heuristic source-code pass, run:

```bash
python scripts/rams_ui_audit.py <changed-ui-paths>
```

Treat every result as a warning to inspect in context, not proof of design quality or accessibility. Run the reduction pass after behavior is correct and restore anything whose removal makes the task worse.

## Completion contract

A substantial UI task is complete only when:

- the primary job and current object are immediately legible;
- component choice matches the interaction job;
- every relevant state and recovery path is implemented;
- applicable keyboard, focus, touch, contrast, reflow, localization, and reduced-motion behavior is verified;
- tokens and existing component conventions are respected;
- rendering has been visually inspected when tools allow;
- the Rams quality gate has no applicable hard fail;
- the reduction pass was performed and either improved the result or documented why no safe removal remained;
- the handoff distinguishes verified results from unverified conditions.

## Provenance

This `SKILL.md` is a substantially modified derivative of Anthropic's `frontend-design` skill, distributed under Apache License 2.0. See `NOTICE.md` and `LICENSE.txt` for attribution and terms.
