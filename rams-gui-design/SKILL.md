---
name: rams-gui-design
description: >-
  Rams/Braun-informed functionalist GUI design, implementation, or audit.
  Use only when the user or repository asks for a Rams-style (ラムス風・機能主義)
  UI direction; not for general GUI work.
license: "Apache-2.0; see LICENSE.txt"
metadata:
  version: "2.1.2"
  optimized_for: "gpt-6-astra"
---

# Rams GUI Design

Create a precise, calm working instrument whose structure explains its use.
The user's brief and existing product commitments take precedence over these
design preferences, including accessibility and platform requirements.

## Design judgment

- **Derive form from work.** Organize the screen around the object being worked
  on, the decision being made, and the relationship between control and result.
  Let those relationships determine the composition before choosing a visual style.
- **Spend attention deliberately.** Give the current work and consequential
  exceptions priority. Let surrounding chrome recede. Express hierarchy through
  position, alignment, density, and typography; color and depth can reinforce it.
- **Make the instrument honest.** Keep values, units, editable boundaries, and
  decision-relevant state understandable. A precise-looking display must distinguish
  actual precision, uncertainty, and pending changes. Preserve context and recovery
  when an operation fails.
- **Reduce the user's burden.** Prefer the design that removes interpretation,
  navigation, or repeated effort while retaining useful context. Fewer visible
  elements are beneficial only when they improve the actual job.

Resolve visual and interaction tradeoffs from these criteria. Geometry, motion,
density, and component choice are design decisions for this product.
Rams character comes from functional coherence and restrained craftsmanship.

## Color set — A

Use this light-theme palette unless the user's brief or an established product
color system takes precedence. Keep orange as the primary accent for actions,
selection signals, and focus; give status colors their listed roles.

| Role | Color |
|---|---|
| Canvas | #EFEDE7 |
| Surface | #F9F8F3 |
| Main text | #1F211F |
| Secondary text | #62645E |
| Decorative divider | #C7C7BF |
| Control boundary | #83877E |
| Primary accent / focus | #AE4700 |
| Text on accent | #FFFFFF |
| Selection background | #F6E6D9 |
| Error | #A32958 |
| Error background | #FBE6EE |
| Warning signal | #E7BC26 |
| Warning background | #FFF5CC |
| Warning text | #5B4900 |
| Success | #2E6E4A |
| Information | #355F7C |

Pair the yellow warning signal with its dark text color. Pair status colors with
text or symbols so the meaning remains visible beyond color.

## Typography

Use IBM Plex Sans JP for Japanese and Latin GUI text unless the user's brief or
an established product type system takes precedence. Use Regular (400) for body
text and Bold (700) for emphasis; choose sizes, line height, and density for the
actual task. When implementing or changing typography, read
[typography.md](references/typography.md) for verified download sources, local
bundling, and font-load verification.

## Context to load when useful

| Current task | Supporting guidance |
|---|---|
| Establish a new interface or substantially new composition | [new-interface.md](references/new-interface.md) |
| Change or review an existing interface | [existing-interface.md](references/existing-interface.md) |
| Implement or change typography | [typography.md](references/typography.md) |

A bounded local correction can use the criteria above without loading a reference.
For mixed tasks, read the relevant section where its decision becomes necessary.

## Completion

For implementation, carry the authorized scope through a usable result, rendered
inspection where available, and correction of observed defects. Finish when the
requested job works and the affected requirements have sufficient evidence;
choose checks proportionate to the change. Report material evidence gaps.
For reviews, deliver findings supported by the affected interface and user task.

See [NOTICE.md](NOTICE.md) for attribution and instruction-design sources.
