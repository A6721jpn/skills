# Component patterns in the Rams-informed language

Choose components by interaction semantics first. Apply restrained visual treatment second.

## Action controls

### Primary button

Use for the single most important action in a task region.

- Use a specific verb-object label: `Save changes`, `Run analysis`, `Export STEP`.
- Use the accent family or strong neutral treatment.
- Keep geometry rectangular with a small radius.
- Show busy state without changing width; prevent duplicate submission when necessary.
- Preserve focus and announce completion or failure.
- Do not create multiple equal primary buttons in one region.

### Secondary and quiet buttons

Use for supporting or reversible actions.

- Prefer border or text treatment over filled color.
- Keep hierarchy lower than the primary action but maintain contrast and target size.
- Use a quiet button for low-frequency or contextual actions.

### Destructive button

- Use explicit labels such as `Delete 12 files`, not `Confirm`.
- Use danger color sparingly and show scope.
- Require confirmation only when action is difficult to reverse or high consequence.
- Prefer undo for routine reversible deletion.

### Icon button

- Use for conventional or repeated compact actions.
- Always provide a programmatic accessible name. A tooltip may supplement it for pointer and keyboard users, but never replaces the accessible name or a visible label when the action remains ambiguous, especially in touch contexts.
- Keep selected/active state distinct from hover.
- Avoid a toolbar of visually similar mystery icons without labels, grouping, or discoverability.

### Split button and menu button

- Use a split button only when one action is clearly the default and adjacent alternatives are closely related.
- Use a menu button for a compact set of actions, not for persistent selection.
- Keep destructive actions separated and labeled.

### Toolbar and command palette

- Group commands by task and frequency.
- Show current mode and selected tool clearly.
- Support keyboard shortcuts and display them consistently.
- Command palettes supplement, not replace, visible primary paths.

## Input and choice

### Text field and text area

- Use persistent visible labels.
- Place unit, format, range, or example near the field.
- Keep help text concise and error text specific.
- Preserve entered data on validation failure.
- Use monospace only when character alignment or code semantics matter.

### Numeric input and spinbutton

- Show unit and valid range.
- Use locale-aware parsing and formatting.
- Support keyboard increments and direct entry.
- For engineering or financial values, define precision, rounding, and invalid intermediate states.

### Checkbox

Use for independent binary choices or multi-selection.

- Label the resulting condition, not an action command.
- Support indeterminate state only when representing a real mixed selection.
- Keep related checkboxes in a labeled group.

### Radio group

Use for a small mutually exclusive set where options benefit from being visible together.

- Show all options when there are roughly two to five meaningful choices.
- Provide group label and keyboard arrow behavior.
- Avoid using radio cards unless the extra descriptive content is necessary.

### Switch

Use only for an immediate, persistent on/off state.

- Label the controlled state; show current state through position plus text when ambiguity is possible.
- Do not use a switch for an action, form submission, or choice that requires `Save` before taking effect.

### Select, listbox, and combobox

- Use native select for straightforward compact choice when platform behavior is sufficient.
- Use a combobox when typing/filtering aids a larger option set.
- Use a listbox when multiple options must remain visible.
- Keep current value legible when collapsed.
- Support Escape without accidental commitment when exploring options.

### Segmented control

Use for a small set of peer modes or views.

- Keep labels short.
- Do not use it for unrelated actions.
- Show one selected segment with a clear border/tone, not a decorative pill bar.

### Slider

Use when relative position and continuous adjustment matter.

- Pair with a numeric value and unit when precision matters.
- Show min/max or meaningful anchors.
- Provide keyboard and non-drag operation.
- Avoid sliders for values users normally know exactly.

### Date and time input

- Use platform-appropriate controls.
- Show timezone, locale, recurrence, or range semantics when relevant.
- Allow typed entry for expert workflows if reliable.
- Keep date constraints and invalid states explicit.

### File input and upload

- Show accepted types, size limits, privacy, and destination before selection.
- Provide progress, cancel, retry, duplicate/conflict handling, and partial failure states.
- Keep drag-and-drop as an enhancement, never the only path.

## Navigation and orientation

### Link

- Use for navigation, not actions.
- Keep labels descriptive out of context.
- Distinguish visited state when it aids the task.

### Breadcrumb

- Use for real hierarchy.
- Keep the current item non-interactive or clearly indicated.
- Collapse middle levels carefully on compact screens.

### Tabs

- Use for peer views of the same object or context.
- Keep tab count limited and labels stable.
- Support expected keyboard behavior.
- Do not use tabs for a required sequence or unrelated destinations.

### Side navigation

- Use for stable product-level or category navigation.
- Keep selected state clear and quiet.
- Provide text labels unless the rail is a well-known compact mode with accessible expansion.
- Do not over-emphasize navigation relative to the work.

### Tree navigation

- Use for hierarchical objects, files, assemblies, layers, or settings.
- Distinguish focus, selection, expansion, and checked state.
- Preserve expansion and scroll position where expected.
- Provide context menu and keyboard access without making right-click mandatory.

### Pagination and infinite loading

- Use pagination when position, total scope, sharing, or return navigation matters.
- Use incremental/infinite loading for continuous feeds only when position loss is acceptable.
- Preserve focus and announce appended content.

## Containers and disclosure

### Section

Prefer a titled section with spacing and an optional rule before creating a card.

- Use clear heading hierarchy.
- Keep related controls and feedback in the same region.
- Do not wrap every section in a raised container.

### Panel and card

Use a panel for a stable functional region or a card for an independently actionable object.

- Use flat surfaces, small radius, and subtle border.
- Avoid nested cards.
- Do not use a card merely because content needs spacing.

### Accordion and disclosure

- Use for optional or advanced content, not to hide the primary path.
- Keep the trigger label descriptive and state perceivable.
- Preserve open state when it supports the workflow.

### Split pane and resizable region

- Use when simultaneous comparison or control of a central work surface is important.
- Provide sensible defaults, minimum sizes, keyboard alternative, and persistence.
- Keep resize handles perceivable without decorative thickness.

## Data display

### Description list and key-value readout

- Use for compact object metadata, measurements, and status.
- Align labels and values; keep units attached.
- Use tabular numerals for changing values.
- Highlight exceptions, not every value.

### List

- Use for scan-friendly homogeneous items.
- Keep row structure consistent.
- Place primary identity first, status and metadata second, actions last.
- Reveal row actions on hover only if they remain keyboard/touch accessible.

### Table and data grid

- Use a semantic table for read-only tabular data and a grid only when cell-level interaction requires it.
- Align numbers by decimal or right edge; keep units in header or value consistently.
- Use sticky headers/columns only when they improve orientation.
- Separate selection, focus, hover, edited, invalid, and changed states.
- Provide sorting, filtering, column visibility, density, and export only when the task needs them.
- On narrow screens, prioritize columns or open a detail view rather than turning every row into an unrelated card.

### Tree table

- Use for hierarchical objects with comparable columns.
- Keep indentation, expansion, selection, and status distinct.
- Avoid excessive connector lines and color coding.

### Badge, tag, and status indicator

- Use text-first compact status.
- Reserve pills for status/tag semantics.
- Use a signal dot only as a supplement.
- Avoid a rainbow of badges; map colors to stable semantic categories.

### Metric and KPI

- Pair value with label, unit, timeframe, source, and comparison basis.
- Use large type only when the metric is the actual decision focus.
- Avoid decorative arrows or percentage changes without baseline and direction meaning.

### Chart

- Use the simplest chart that answers the question.
- Add exact values through direct labels, table, or accessible description.
- Keep axis, unit, threshold, and time range explicit.
- Use neutral series plus one emphasis where possible.

### Timeline, log, and activity history

- Show time, actor/source, action, object, and outcome.
- Use chronological order consistently.
- Distinguish user actions, system events, warnings, and errors structurally, not only by color.
- Make filtering and retention limits honest.

## Feedback and system state

### Inline validation

- Place feedback adjacent to the field or control.
- State what is wrong and how to fix it.
- Do not remove the user's input.
- Use summary focus for long forms when submission fails.

### Status line and live region

- Use for ongoing state, selection count, coordinates, save state, or connection state.
- Keep it stable and low prominence until action is required.
- Announce material changes without excessive interruption.

### Progress

- Use determinate progress when measurable; show completed/total or time estimate only when trustworthy.
- Use indeterminate progress when scope is unknown, with descriptive text.
- Provide cancellation when meaningful and safe.
- Distinguish queued, running, paused, failed, canceled, and complete.

### Empty state

- Explain what the region represents and the next useful action.
- Do not fill the space with decorative illustration by default.
- Preserve filters/search context and explain when they caused the empty result.

### Error state

- State what happened, what is affected, whether data is safe, and what to do next.
- Keep technical details behind disclosure.
- Preserve context and input.

### Toast

- Use for low-risk confirmation that does not require a decision.
- Keep duration adequate and pause on hover/focus when applicable.
- Do not place critical errors, destructive consequences, or sole recovery actions only in a toast.

### Banner and alert

- Use for persistent page/system conditions that affect the task.
- Keep severity and scope explicit.
- Provide one clear action if action is available.

### Tooltip

- Use for supplementary explanation, not essential instructions.
- Support hover and keyboard focus.
- Keep content concise and dismissible according to platform expectations.

## Overlays

### Popover

- Use for local supplemental controls or details.
- Keep it anchored and dismissible.
- Manage focus when it contains interactive content.
- Avoid popover chains.

### Dialog

- Use for a focused decision or task that must interrupt the underlying workflow.
- Give it a descriptive title, concise scope, explicit actions, correct initial focus, Escape/cancel behavior, and focus return.
- Do not use a modal for information that can remain inline.

### Alert dialog

- Reserve for urgent high-consequence confirmation or acknowledgement.
- State the irreversible effect and object count.
- Avoid generic `OK`/`Cancel` when specific labels are possible.

### Drawer or sheet

- Use for secondary detail, filters, or compact-screen pane substitution.
- Keep current context visible or named.
- Do not use it to hide the only route to a primary task.

## Complex and direct-manipulation components

### Drag and drop

- Provide a non-drag alternative.
- Make source, destination, valid targets, and result clear.
- Support cancel/undo and announce the move.
- Avoid gratuitous movement animation.

### Canvas handles and manipulators

- Show selected object, active mode, constraints, snapping, coordinates, and units.
- Provide numeric entry and keyboard adjustment for precision.
- Keep handles visible at required zoom levels and input modes.
- Support Escape/cancel and undo.

### Inspector

- Organize by object semantics and frequency.
- Keep label, value, unit, reset/default, and validation close.
- Use progressive disclosure for advanced parameters.
- Preserve selection context and distinguish multi-selection mixed values.

### Command line, code, or formula editor

- Use monospace, clear line/column status, errors linked to location, and explicit run/evaluate state.
- Do not over-style syntax at the expense of contrast.
- Preserve history and make destructive execution scope explicit.

## State matrix

For each component, select and implement every relevant state:

| Category | States |
|---|---|
| Interaction | rest, hover, focus-visible, active/pressed, selected/checked, expanded, dragged |
| Availability | enabled, disabled with reason when useful, read-only, permission-denied |
| Data | loading, partial, stale, empty, offline, conflict |
| Validation | valid, warning, invalid, submitting, success, failure |
| Responsiveness | pointer, keyboard, touch, compact, wide, zoomed/reflowed |
| Preferences | reduced motion, high contrast/forced colors, dark mode |

Do not create a visual variant unless its state meaning is distinguishable and documented.
