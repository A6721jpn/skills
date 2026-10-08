# Notice

Rams GUI Design version 2.1.2 promotes the local `rams-design-v2` 2.1.2
under the existing `rams-gui-design` distribution name. The local 2.1.2 revision
added the user-selected IBM Plex Sans JP typeface
to version 2.1.1, which added light-theme color set A to version 2.1.0.
Version 2.1.0 revised the local `rams-design-v2` 2.0.0,
which was adapted from `rams-gui-design` 1.1.0. The earlier package was a
substantially modified derivative of Anthropic's `frontend-design` skill:

https://github.com/anthropics/skills/tree/main/skills/frontend-design

The Apache License 2.0 is retained in `LICENSE.txt`.

Version 2.1.0 replaced the earlier visual preset, component catalog, verification
reference, and optional principle score with outcome-oriented design judgment and
two context-specific references. The inherited token assets, foundation stylesheet,
and heuristic source audit were removed. Version 2.1.1 restores only explicit
color roles and values. Version 2.1.2 adds font sources and application guidance;
no executable tooling, font binaries, or fixed layout is bundled.
The original Rams-informed discipline
remains: usefulness, clarity, honesty, coherence, and economy.

## Instruction-design sources

Official OpenAI guidance reviewed on 2026-10-08:

- Rethinking skills and prompts for GPT-6 Astra:
  https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra
  Supports concise discovery descriptions, progressive disclosure, replacing
  elaborate recipes, and explicit completion appropriate to the task.
- Build skills:
  https://learn.chatgpt.com/docs/build-skills
  Supports focused, instruction-first skills and conditional supporting resources.

These sources guide how the skill is written. They do not prescribe Rams aesthetics,
require removal of CSS or audits, or establish this package's performance. Removing
those resources and reorganizing the design criteria are local authoring decisions.
The task-derived design grammar in the supporting references is also a local
interpretation rather than a quotation or OpenAI design standard.

The `optimized_for` metadata identifies the intended prompting target. This skill
does not select a model or change runtime settings. Version 2.1.0 was evaluated
in three Sol 6.1 / XHIGH GUI trials against saved version 1.1.0 and 2.0.0 results.
Versions 2.1.1 and 2.1.2 have not been benchmarked. Their color and font previews
verify displayed color pairs and actual font use, not full GUI quality or token
efficiency. No Astra benchmark has been performed.

The earlier package's Dieter Rams and Vitsœ attribution is retained:

https://www.vitsoe.com/us/about/good-design

“Dieter Rams,” “Braun,” and “Vitsœ” are descriptive references. This package is
not affiliated with, approved by, or endorsed by Dieter Rams, Braun, Vitsœ,
Anthropic, or OpenAI.
