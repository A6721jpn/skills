# Rams-informed visual language

Use this reference when choosing or reviewing color, type, layout, geometry, elevation, icons, motion, density, dark mode, and data visualization.

## 1. Visual profile

Aim for six simultaneous qualities:

1. **Instrumental:** values, units, state, and control mappings are explicit.
2. **Calm:** the interface has few competing focal points.
3. **Exact:** alignment, spacing, dimensions, and component states are deliberate.
4. **Flat but tactile:** boundaries and active states are perceptible without decorative depth.
5. **Neutral with signal:** most of the screen is neutral; color is concentrated where it carries meaning.
6. **Dense where work happens, spacious around it:** professional efficiency without visual crowding.

## 2. Token policy

- Reuse the product's existing semantic tokens first.
- Remap values at the token layer rather than inserting one-off styling.
- Separate semantic roles from raw values: `surface`, `text`, `border`, `accent`, `danger`, not `gray-3` in component code.
- Keep the number of surface levels, radii, shadows, and type sizes small.
- When no usable system exists, adapt `assets/rams-ui-tokens.json` or `assets/rams-ui-foundation.css`.
- Do not copy the fallback palette unchanged when a product has established brand colors. Preserve brand recognition while retaining neutral dominance and functional color allocation.

## 3. Color

### Default allocation

- Use neutral canvas and surfaces for most area.
- Use one accent family for primary action, active selection, focus, or a small signature signal.
- Use semantic colors for success, warning, danger, and information only where the state must be distinguished.
- Keep large colored surfaces rare. Prefer a small signal, rule, label, or selected control.
- Never encode meaning by color alone; pair it with text, iconography, shape, position, or pattern.

### Avoid

- decorative gradients;
- neon-on-black styling;
- multiple unrelated accents;
- low-contrast gray-on-gray minimalism;
- broad brand-color flooding that competes with data;
- translucent glass layers used as generic containers.

## 4. Typography

- Use the established UI typeface or a neutral grotesk/system sans.
- Use one family for most UI. Add a monospaced or technical face only for code, measurements, identifiers, or aligned data.
- Prefer regular and medium weights. Reserve bold for strong hierarchy or critical values.
- Use sentence case. Avoid all-caps except short technical labels, units, or established acronyms.
- Use a compact, limited type scale. Differentiate hierarchy with size, weight, spacing, and placement before color.
- Use tabular numerals for tables, measurements, timers, financial values, and changing readouts.
- Keep units visually attached to values and do not rely on placeholder text as a label.
- Avoid a characterful display face merely to create personality. Let product structure and content provide identity.

## 5. Grid and spacing

- Use a consistent 4 px base with an 8 px dominant rhythm, or preserve the project's established equivalent.
- Align labels, controls, values, units, and table columns to visible axes.
- Use whitespace as structure, not as luxury. Separate unrelated groups; tighten related control-value pairs.
- Prefer fewer, stronger regions over many floating cards.
- Use hairline dividers only where spacing alone does not communicate the boundary.
- Keep page margins stable and allow task-dense areas to use compact spacing without becoming cramped.
- In workbench UIs, keep canvas, navigation/tree, inspector, and status regions geometrically stable.

## 6. Geometry

- Default to rectilinear shapes with small radii.
- Use square or 2–4 px radii for controls and panels; use 6–8 px only when touch comfort or platform convention benefits.
- Use pills only when the semantics are pill-like: status, tag, compact filter, segmented selection, or rounded switch track.
- Use circular geometry for radial or continuous mapping, icon controls, avatars, or signals—not as generic decoration.
- Keep border thickness generally to 1 px. Use 2 px for focus, selected emphasis, or physical-control-like active feedback.
- Use the hairline `border` token only for dividers inside an already-perceivable region. A control's sole boundary (input, checkbox, segmented control) must use `borderStrong` or another value meeting 3:1 against its background.
- Avoid nested rounded rectangles and mixed radius systems.

## 7. Surface and elevation

- Keep permanent layout regions flat or separated by tone, border, and spacing.
- Reserve elevation for temporary overlays such as menus, popovers, dialogs, and dragged objects.
- Use one subtle overlay shadow recipe. Do not build multiple decorative elevation tiers.
- Avoid inner glows, blurred colored shadows, backdrop blur, frosted glass, and glossy highlights.
- An active control may use a small tonal shift, border change, or 1 px inset effect if it improves state perception.

## 8. Icons and imagery

- Use a consistent, simple icon set with restrained stroke or filled geometry.
- Prefer familiar symbols. Pair ambiguous icons with text.
- Do not use icons as decoration beside every label.
- Keep icon size subordinate to the label unless the control is a repeated tool button.
- Use product imagery, diagrams, or illustrations only when they explain, identify, compare, or instruct.
- Avoid generic hero illustrations and stock imagery inside task-oriented software.

## 9. Motion

- Animate cause and effect: opening, closing, selection, reordering, progress, spatial change, and confirmation.
- Keep common feedback around 90–180 ms and larger spatial transitions around 160–240 ms.
- Avoid `transition: all`; animate only required properties.
- Do not use ambient loops, floating objects, parallax, shimmer everywhere, or scroll spectacle in productivity UI.
- Use skeletons only when they improve perceived structure; prefer honest progress or preserved layout.
- Respect reduced-motion settings and provide non-motion state cues.

## 10. Density and control size

- Match density to frequency and platform.
- For pointer-heavy professional tools, controls may be visually compact while maintaining adequate hit areas and keyboard access.
- For touch, target approximately 44 px where practical; never violate applicable accessibility minimums.
- Keep dense tables and inspectors readable through alignment, row rhythm, grouping, and hover/focus indication rather than large card spacing.
- Provide a user-selectable compact mode only when the product genuinely serves both occasional and expert users.

## 11. Responsive behavior

- Preserve task priority, not desktop proportions.
- Reflow into a single primary column before shrinking text and controls excessively.
- Collapse secondary panes into drawers, sheets, or sequential views; keep current context visible.
- Keep primary action reachable and stable.
- Replace hover-only affordances with explicit touch controls.
- Preserve data meaning when tables become narrow: prioritize columns, offer detail views, or allow deliberate horizontal scrolling.

## 12. Dark mode

- Treat dark mode as a material inversion, not a neon theme.
- Use dark neutral canvas and slightly lighter surfaces; keep boundaries visible without glowing outlines.
- Use a lighter accent variant with dark foreground when needed for contrast.
- Re-test every semantic color and focus treatment.
- Avoid pure black over large areas unless the product domain requires it.

## 13. Data visualization

- Lead with the question the chart answers, not the chart type.
- Use direct labels and explicit units; reduce legends where series can be labeled in place.
- Use neutral series plus one emphasized series when comparison permits.
- Add semantic colors only for meaningful categories or thresholds.
- Keep gridlines sparse and low prominence.
- Avoid 3D charts, decorative gradients, excessive smoothing, dual axes without strong justification, and rainbow palettes.
- Provide tables or accessible summaries for exact values and non-visual access.
- Use calibrated scales, thresholds, reference lines, and uncertainty bands where they carry analytical meaning.

## 14. Functional signature

A Rams-informed product may have one recurring, functional signature across screens. Examples:

- a narrow status rail that consistently shows state, progress, and alerts;
- a calibrated value-control pattern with label, number, unit, and direct adjustment;
- a modular channel or parameter matrix for repeated technical entities;
- a precise split between work surface and inspector;
- a single signal accent used for active state and primary action.

The signature must improve orientation, manipulation, or comprehension. It must not become a decorative motif detached from function.
