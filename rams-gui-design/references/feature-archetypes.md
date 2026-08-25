# Feature archetypes and interaction-job mapping

Use this reference to turn any feature request into a stable information architecture and a small set of suitable components.

## General method for an unfamiliar feature

1. List the user's nouns: objects, records, files, parameters, people, jobs, results.
2. List the user's verbs: find, inspect, create, edit, compare, run, approve, recover.
3. Identify the system states: idle, busy, partial, stale, failed, offline, unauthorized.
4. Identify risk: reversible, costly, destructive, regulated, or safety-related.
5. Rank frequency: continuous, frequent, occasional, rare.
6. Choose the archetype below that best matches the dominant verb.
7. Compose secondary jobs with adjacent patterns instead of merging everything into one overloaded component.

## 1. Orientation and navigation

Use for multi-page products, deep hierarchies, projects, folders, assemblies, and settings categories.

Recommended structure:

- stable product-level navigation;
- page title and current object context;
- breadcrumb or tree for real hierarchy;
- tabs only for peer views of the same object;
- local actions adjacent to the title or selected object.

Rams treatment:

- keep navigation quieter than content;
- show selection with one clear signal, not multiple simultaneous cues;
- avoid large decorative headers;
- use location names that match user concepts.

Failure modes:

- using tabs for sequential steps;
- hiding important destinations in an icon-only rail;
- duplicating the same navigation in sidebar, tabs, and cards.

## 2. Inspect and monitor

Use for dashboards, system status, test results, simulations, devices, production lines, and operational overviews.

Recommended structure:

- concise status summary;
- prioritized exceptions or deviations;
- trends and thresholds;
- detailed table or log;
- clear time range, update time, data source, and stale state.

Rams treatment:

- make normal state quiet and exceptions salient;
- prefer direct values, units, and thresholds over decorative KPI cards;
- use color locally and pair it with text/symbols;
- show latency and data freshness honestly.

Failure modes:

- a grid of equally weighted cards;
- oversized numbers without context;
- auto-refresh that moves content without preserving focus.

## 3. Search, filter, and narrow

Use for large collections, catalogs, files, records, logs, parts, users, or commands.

Recommended structure:

- prominent search when text lookup is primary;
- filters ordered by decision value;
- visible active-filter summary;
- sort and view controls separated from filtering;
- result count and clear-empty action;
- saved views only for repeated expert workflows.

Rams treatment:

- keep filter controls compact and explicit;
- use chips only to represent active filters, not as generic buttons;
- preserve query and filters through navigation when expected.

Failure modes:

- hidden filter state;
- placeholder-only labels;
- filter drawers that obscure results without necessity.

## 4. Compare and decide

Use for variants, revisions, products, configurations, measurements, before/after states, or design alternatives.

Recommended structure:

- aligned comparison axes;
- explicit baseline/reference;
- highlighted differences, not entire colored panels;
- synchronized scroll or shared scale where needed;
- decision action and rationale/history.

Rams treatment:

- use tables, split views, diffs, and calibrated charts;
- maintain identical units and precision;
- keep the reference visually stable.

Failure modes:

- cards with inconsistent content order;
- hiding unfavorable differences;
- using color without textual or structural indication.

## 5. Create and edit

Use for forms, records, documents, models, configurations, and content authoring.

Recommended structure:

- logical field groups in task order;
- persistent object identity and save state;
- inline validation at the field and summary at submission when needed;
- explicit primary action and reversible cancellation;
- autosave only with visible status and reliable recovery.

Rams treatment:

- use labels above or beside fields; keep help close and concise;
- avoid carding every form group;
- use units, valid ranges, and examples where precision matters;
- reveal advanced settings progressively.

Failure modes:

- ambiguous “Submit” buttons;
- validation only after full submission;
- uncontrolled autosave with no history or status.

## 6. Configure and tune

Use for settings, preferences, system parameters, device controls, and engineering inputs.

Recommended structure:

- categories based on user goals;
- current value, default, allowed range, unit, and effect;
- immediate preview for reversible changes;
- explicit apply/restart requirement for delayed changes;
- restore-defaults at an appropriate scope.

Rams treatment:

- pair control, value, unit, and status tightly;
- use switches only for true immediate binary state;
- use sliders only when continuous comparison matters, with numeric entry for precision;
- separate dangerous or system-wide settings.

Failure modes:

- every option as a switch;
- unexplained disabled controls;
- settings categories based on backend modules.

## 7. Execute a command

Use for run, build, export, analyze, convert, send, publish, or machine actions.

Recommended structure:

- action-specific label;
- prerequisites and scope visible before execution;
- progress, cancellation, and logs proportional to duration;
- outcome, next step, and retry/recovery;
- confirmation only when consequence or scope warrants it.

Rams treatment:

- keep the command visually strong but not theatrical;
- show exact target and parameters;
- distinguish queued, running, paused, canceled, failed, and complete states.

Failure modes:

- spinner with no scope or progress;
- success toast that disappears before the user can act;
- confirmation dialogs for harmless reversible actions.

## 8. Multi-step workflow

Use for onboarding, checkout, setup, calibration, release, approval, or guided procedures.

Recommended structure:

- visible current step and remaining work;
- one primary decision per step;
- preserved data and back navigation;
- validation before advancing;
- summary and final consequence before commitment.

Rams treatment:

- use a quiet step indicator; do not turn steps into decorative cards;
- show sequence only when order is real;
- keep the user's object/context visible across steps.

Failure modes:

- hiding the total process;
- forcing a wizard for a short form;
- losing work when moving backward.

## 9. Collection and file management

Use for documents, assets, parts, datasets, projects, media, or versions.

Recommended structure:

- list/table/tree according to hierarchy and metadata needs;
- selection model and bulk-action bar;
- rename, move, copy, delete, restore, and version/history behavior;
- upload/import progress and conflict handling;
- preview/detail pane for frequent inspection.

Rams treatment:

- favor stable columns and compact metadata;
- make selection and current location unambiguous;
- expose destructive scope and recovery.

Failure modes:

- card grid for metadata-heavy files;
- invisible multi-selection rules;
- destructive actions without object count or undo.

## 10. Planning, scheduling, and workflow management

Use for calendars, timelines, Gantt charts, kanban, queues, dependencies, and resource allocation.

Recommended structure:

- time scale and timezone;
- status/owner/priority filters;
- dependency and conflict indicators;
- direct manipulation plus keyboard/non-drag alternative;
- detail inspector and history.

Rams treatment:

- emphasize sequence, duration, dependency, and exception;
- use color sparingly for status or ownership;
- keep grid and labels precise.

Failure modes:

- drag-only operation;
- dense color coding without legend or text;
- hidden timezone and date assumptions.

## 11. Communication, review, and approval

Use for comments, annotations, design review, issue triage, and sign-off.

Recommended structure:

- object being discussed remains visible;
- thread, author, time, status, and resolution state;
- explicit approve/request-change/reject controls;
- mention and notification behavior;
- immutable decision history where required.

Rams treatment:

- distinguish commentary from system state;
- keep approval consequence and scope explicit;
- use restrained presence indicators.

Failure modes:

- burying unresolved decisions in chat;
- ambiguous emoji-only approvals;
- changing prior decisions without history.

## 12. Spatial, canvas, CAD, diagram, and technical workbench

Use for geometry, maps, node graphs, image editing, CAD/CAE, dashboards with manipulable plots, or any large central work surface.

Recommended structure:

- stable central canvas;
- tool selection near the canvas or pointer context;
- object tree/layers on one side when hierarchy matters;
- properties/inspector on the other side;
- status bar for coordinates, units, mode, selection count, and warnings;
- command history, undo/redo, and escape/cancel behavior;
- direct manipulation plus numeric precision controls.

Rams treatment:

- make mode and selection unmistakable;
- keep tool chrome compact and consistent;
- use calibrated readouts, exact units, and local constraints;
- reserve accent color for active tool, selection, or warning—not the entire canvas.

Failure modes:

- hidden mode changes;
- icon-only toolbars without discoverability;
- direct manipulation without numeric entry or undo;
- warning overlays that obstruct the object.

## 13. Data analysis and visualization

Use for charts, experiments, reports, comparisons, distributions, and measured results.

Recommended structure:

- question/title, scope, units, source, and time range;
- chart for pattern, table for exact values;
- filters and series controls;
- thresholds, reference, uncertainty, and annotations;
- export and reproducibility metadata when appropriate.

Rams treatment:

- use calibrated axes and direct labels;
- emphasize one analytical point at a time;
- keep annotation factual and concise.

Failure modes:

- decorative charts with no decision purpose;
- truncated axes without disclosure;
- excessive series color.

## 14. Account, authentication, permissions, and billing

Use for sign-in, account settings, roles, invitations, plans, and payment.

Recommended structure:

- clear identity and organization context;
- explicit permission scope and inherited roles;
- visible security consequence;
- billing amount, period, renewal, taxes, and cancellation effect;
- recovery and support paths.

Rams treatment:

- prioritize trust and plain language;
- avoid manipulative upgrade hierarchy or hidden cancellation;
- separate routine settings from high-risk security actions.

Failure modes:

- dark patterns;
- ambiguous role names;
- concealing irreversible or financial consequences.

## 15. AI-assisted feature

Use for generation, summarization, classification, recommendations, agents, and automated actions.

Recommended structure:

- clear user input and system output separation;
- source/provenance and freshness where available;
- confidence, assumptions, and limits when material;
- edit, retry, compare, and feedback controls;
- explicit approval before external side effects;
- progress and intermediate state for long-running work;
- safe recovery from partial completion.

Rams treatment:

- avoid magical or anthropomorphic decoration;
- show what the model used and what it will do;
- keep automation honest, inspectable, and interruptible.

Failure modes:

- presenting generated content as verified fact;
- hiding tool calls or side effects;
- streaming animation that overwhelms readability.

## 16. System state, error, and recovery

Use whenever the product can be unavailable, stale, partial, delayed, unauthorized, or failed.

Recommended structure:

- what happened;
- what is affected;
- whether data is safe;
- what the user can do now;
- retry, alternate path, contact/support, or incident status as appropriate;
- technical details behind disclosure, not in the primary message.

Rams treatment:

- factual, local, and actionable;
- no apologetic filler or vague “Something went wrong” messages;
- preserve user input and context.

Failure modes:

- error only in toast;
- destructive retry;
- hidden offline or stale status.

## Common layout compositions

### Single-purpose tool

Use one dominant work area, one compact control group, and one result/status region. Avoid dashboard framing.

### Master-detail

Use a stable list/tree and detail pane. Keep selection visible. On compact screens, preserve context with a clear back path and title.

### Dashboard

Use summary → exceptions → trends → details. Do not assign equal weight to every metric.

### Settings

Use category navigation, titled sections, local descriptions, and clear save/apply behavior. Avoid a wall of switches.

### Workbench

Use stable navigation/tree, central canvas, inspector, toolbar, and status line. Preserve spatial memory.

### Mobile task flow

Use one primary job per screen, reachable actions, explicit state, and progressive disclosure. Do not compress a desktop workbench into tiny panes.
