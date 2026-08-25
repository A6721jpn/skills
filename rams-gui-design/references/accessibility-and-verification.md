# Accessibility, implementation, and verification

Accessibility is part of making a product understandable, useful, honest, and thorough. Minimal appearance is never a reason to remove labels, focus, contrast, target size, status, or recovery.

Apply HTML, WCAG, and ARIA instructions directly to web interfaces. For native desktop or mobile work, use the platform's equivalent accessibility semantics, input conventions, inspectors, and assistive-technology APIs; do not add web-specific ARIA outside the web platform.

## 1. Semantic implementation

- Use native HTML controls and landmarks where possible.
- Use links for navigation and buttons for actions.
- Associate every form control with a persistent accessible name.
- Use headings in a logical hierarchy.
- Use semantic tables for read-only tabular data; use ARIA grid only when interaction genuinely requires composite keyboard behavior.
- Use ARIA roles, states, and properties only when native semantics are insufficient.
- Follow the WAI-ARIA Authoring Practices interaction model for custom widgets such as dialogs, tabs, comboboxes, menus, trees, toolbars, and grids.

Primary references:

- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/WAI/ARIA/apg/patterns/

## 2. Keyboard and focus

- Make every action available by keyboard on platforms and devices that support keyboard input; provide an equivalent accessible path for gesture or pointer actions.
- Preserve logical tab order; do not use positive `tabindex` to patch visual order.
- Provide visible `:focus-visible` treatment with sufficient contrast and separation.
- For composite widgets, implement expected arrow, Home/End, Enter/Space, and Escape behavior.
- Return focus to the invoking control when a dialog, popover, or temporary surface closes.
- Keep focus stable when content updates, filters apply, or rows are removed.
- Provide a non-drag alternative for all drag interactions unless the movement itself is essential.

## 3. Pointer and touch

- Meet WCAG 2.2 target-size requirements and spacing exceptions.
- Aim for approximately 44 px touch targets when the platform and density allow; compact visual controls may use larger invisible hit areas.
- Do not depend on hover for essential information or action.
- Make resize handles, splitters, and canvas manipulators perceivable and operable.
- Avoid accidental destructive activation near frequent controls.

## 4. Contrast and non-color cues

- Meet the applicable WCAG contrast requirements for text, controls, focus, and meaningful graphics.
- Test every state, not only rest state.
- Pair semantic color with text, icon, shape, pattern, or position.
- Ensure disabled state remains legible enough to identify the control and understand context; use explanation for non-obvious unavailability.
- Test in dark mode and forced-colors/high-contrast mode where supported.

## 5. Motion and animation

- Respect `prefers-reduced-motion` or the platform equivalent.
- Keep state understandable without motion.
- Avoid flashing, continuous ambient animation, auto-moving content, and parallax in task-oriented software.
- Pause or stop nonessential motion.
- Do not use motion as the only indication of selection, progress, or error.

## 6. Content, copy, and localization

- Use plain, specific labels that describe user-recognized objects and outcomes.
- Keep action vocabulary consistent from control through confirmation and result.
- Avoid placeholder-only labels.
- Support text expansion, long translations, mixed scripts, right-to-left layout where required, and localized numbers/dates/units.
- Do not bake text into images.
- State units, precision, timezone, and rounding rules where they affect decisions.

## 7. Responsive and zoom behavior

- Verify at 200% zoom and narrow reflow where applicable.
- Preserve reading and focus order when panes collapse.
- Avoid horizontal scrolling for ordinary content; allow deliberate scrolling for wide data tables, timelines, canvases, and diagrams when meaning requires it.
- Provide compact alternatives for secondary panes while preserving the primary task.
- Ensure sticky headers, toolbars, and status bars do not consume the usable viewport.

## 8. State and failure verification

Select and exercise representative cases that the product can enter, in proportion to the change and its risk:

- first use and empty data;
- normal content and realistic maximum content;
- slow response and long-running work;
- partial success and retry;
- validation errors;
- network loss and stale data;
- permission denial and expired authentication;
- destructive confirmation and undo/recovery;
- concurrent change or conflict;
- canceled operations;
- reduced motion, keyboard-only, touch, and screen-reader use where feasible.

Do not use only lorem ipsum or idealized data. Long names, large values, negative values, missing fields, and mixed statuses expose hierarchy defects.

## 9. Visual verification loop

When tools permit:

1. Capture the baseline before changes.
2. Render the changed UI at representative wide, medium, and compact viewports.
3. Capture key component states, not only the happy path.
4. Inspect alignment, overflow, wrapping, density, focus, selected state, error state, and dark mode.
5. Compare the result with the feature contract and visual-language rules.
6. Perform the reduction pass and capture again if the change is material.

For a substantial responsive web change, a useful starting viewport set is:

- approximately 1440 × 900 for wide desktop;
- approximately 1024 × 768 for compact desktop/tablet landscape;
- approximately 390 × 844 for touch/mobile.

Adapt the set to the actual supported devices and embedded window sizes. A local change need not exercise unrelated viewports, but it must cover any viewport behavior it can affect.

## 10. Automated and manual checks

Use the repository's established tools first. Depending on stack, verify with:

- unit/component tests for state and event behavior;
- keyboard interaction tests;
- accessibility checks such as axe or platform inspectors;
- visual regression or screenshots;
- lint/type/build tests;
- performance profiling for large lists, canvases, charts, and animations.

Run `scripts/rams_ui_audit.py` for a heuristic check of common visual and semantic anti-patterns. Review every warning; do not treat a clean report as certification.

## 11. Performance and resource restraint

- Prefer CSS and native platform behavior over JavaScript effects.
- Avoid adding a component library or animation framework for one control.
- Lazy-load heavy editors, charts, or media only when the user needs them.
- Virtualize large collections without breaking semantics, focus, or findability.
- Keep layout stable during loading.
- Compress and size images appropriately; avoid decorative media in productivity flows.
- Measure rather than assume when performance is material.

## 12. Handoff honesty

At completion, state:

- what was implemented;
- which states and viewports were verified;
- which automated checks ran and their results;
- whether visual rendering was inspected;
- any unverified platform, assistive-technology, or data condition.

Do not say the UI is accessible, responsive, or visually complete without evidence matching that claim.
