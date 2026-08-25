# Rams principles translated into GUI decisions

This is an original digital-interface interpretation of Dieter Rams's ten principles of good design. It is not an official Rams, Braun, or Vitsœ style guide.

## Philosophy before appearance

A Rams-informed GUI is not created by copying an off-white casing, an orange switch, a circular dial, or a perforated grille. Those cues are useful only when they express structure or operation. The durable character comes from usefulness, explicit mapping, restraint, precision, and reduction.

## Ten-principle translation

| Principle | GUI translation | Verification questions |
|---|---|---|
| Innovative | Use technology to remove friction, reveal information, or improve control. Do not add novelty as spectacle. | Does the new behavior materially improve the task? Could a simpler established pattern do it better? |
| Useful | Optimize the primary user job, including speed, accuracy, recoverability, and confidence. | Is the primary task obvious? Are high-frequency actions efficient? Are important values and units visible? |
| Aesthetic | Treat coherence, proportion, typography, spacing, and detail as part of usability. | Is the screen calm and well resolved at both overview and detail levels? Are visual decisions consistent? |
| Understandable | Make hierarchy, control mapping, state, cause, and consequence self-evident. | Can a first-time user predict what each control does and see what happened? Are labels and feedback adjacent to their object? |
| Unobtrusive | Let the user's data and work dominate. Keep chrome quiet and avoid competing focal points. | Does the interface recede during use? Is anything asking for attention without a task reason? |
| Honest | Represent capability, latency, limits, permissions, uncertainty, pricing, and destructive effects accurately. | Does the UI overpromise? Are disabled states explained? Are AI-generated or estimated values identified? |
| Long-lasting | Prefer semantic tokens, platform conventions, stable patterns, and maintainable components over short-lived visual trends. | Will the hierarchy still work after a brand refresh? Is the implementation tied to a fashionable effect? |
| Thorough | Resolve microcopy, alignment, units, edge cases, input modes, localization, and every relevant component state. | Are loading, empty, error, offline, permission, focus, and touch states intentional? Are arbitrary values eliminated? |
| Resource-conscious | Minimize visual pollution, data transfer, computation, DOM complexity, dependencies, and motion. | Does an effect justify its runtime and cognitive cost? Can an asset, library, or layer be removed? |
| As little design as possible | Retain only what supports comprehension, action, safety, identity, or useful delight. | What can be removed without degrading the task? After removal, is the interface clearer? |

## Physical-to-digital translation

Use these correspondences when they are functionally appropriate:

- **Clearly separated physical controls →** clear action groups, local labels, and predictable state changes.
- **Calibrated dials and scales →** direct numeric values, units, ranges, tick marks, and reversible adjustment.
- **Modular product architecture →** consistent grids, repeatable components, and stable information regions.
- **Signal colors →** localized active, warning, or destructive status rather than broad decorative color fields.
- **Neutral housings →** quiet canvas and surfaces that frame the user's content.
- **Visible material joints →** honest section boundaries, separators, and hierarchy rather than fake depth.
- **Compact control clusters within generous housing →** dense task areas surrounded by sufficient framing space.
- **Precise printed labeling →** concise sentence-case labels, tabular numerals, explicit units, and consistent terminology.

## Anti-cosplay rule

Do not add a dial, grille, numbered scale, orange switch, or vintage type treatment merely to signal Rams. Require a semantic justification:

- A dial is appropriate for a continuous or cyclic value with direct manipulation.
- A scale is appropriate for magnitude, threshold, range, or calibration.
- A modular matrix is appropriate for repeated channels, states, tools, or samples.
- A signal color is appropriate for active state, warning, destructive action, or a single primary action.
- A perforation or repeated-dot motif is appropriate only when it represents data, density, drag affordance, or a real system structure.

If the motif would remain unchanged when the underlying data or behavior changes, it is probably decoration. Remove it.

## Source basis

The ten principle names are attributed to Dieter Rams. The primary source used for this adaptation is Vitsœ's “Good design” page:

https://www.vitsoe.com/us/about/good-design
