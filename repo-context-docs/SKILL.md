---
name: repo-context-docs
description: Create the initial agent-facing documentation spine (reading guide, architecture overview, ADRs, milestones, runbook) for a repository that has none. Use when asked to make a repo readable for coding agents; to refresh existing agent docs use maintaining-repo-context-docs.
---

# Repo Context Docs

## Overview

Create a small documentation spine that lets a fresh coding agent form the right mental model before reading source. Optimize for current truth, decision traceability, and task-specific reading paths rather than chronological history.

## Workflow

1. **Baseline with no-context readers.** Ask one or more fresh agents, or if none are available read as a first-time reader yourself, to read only the existing entry docs and answer: product goal, invariants, source ownership, implemented/deferred work, decision rationale, and first files for a focused change. Record files read, word count, scores, and guesses.
2. **Build the spine.** Add or update:
   - `README.md`: product status and links to current entry points.
   - `docs/agent-reading-guide.md`: start-here guide, task-based read order, source/test ownership, context budget.
   - `docs/architecture/overview.md`: current architecture only, not milestone archaeology.
   - `docs/adr/`: accepted decisions, one decision per file.
   - `docs/milestones.md`: current/historical/planned status table.
   - `docs/security-model.md` or domain-specific invariant doc when safety rules are central.
   - `docs/runbook.md`: commands, environment, operational caveats.
   - `docs/llm-doc-evaluation.md`: repeatable rubric.
3. **Label document roles.** Mark current-state docs, decision records, historical milestone notes, generated files, review artifacts, and stale/planned docs. Tell agents what not to read for orientation.
4. **Evaluate again.** Run fresh no-context agents (or the same first-time read) against the new spine. They should start with README + instructions + agent guide, then open only task-specific docs.
5. **Patch from failures.** If agents read too much, guessed rationale, missed source files, or found contradictions, update the smallest responsible doc.

## Document Rules

| Need | Good doc | Avoid |
| --- | --- | --- |
| Orientation | Short start-here guide with read order | Huge design spec as the only entry point |
| Current architecture | Compact overview with boundaries and ownership | Reconstructing current state from milestones |
| Rationale | ADRs with context, decision, alternatives, consequences | Hiding reasons in chat transcripts or plans |
| Implementation entry | Source and test ownership maps | Forcing broad `rg` before every change |
| History | Milestone table with status labels | Chronological docs competing as source of truth |
| Generated artifacts | README saying when to use them | Letting generated schema/code pollute doc search |

## ADR Format

Use this shape unless the repo already has a standard:

```markdown
# ADR 0001: Title

## Status
Accepted | Proposed | Superseded

## Context
The constraints that forced a decision.

## Decision
The chosen rule.

## Alternatives Considered
Real options and why they were rejected.

## Consequences
What this enables, forbids, or defers.
```

Put unresolved major choices in `docs/adr/backlog.md` instead of pretending they are decided.

## Evaluation Rubric

Score the spine with [references/evaluation-rubric.md](references/evaluation-rubric.md), shared with `maintaining-repo-context-docs`.

## Common Failures

- README says "current design" but links to an old broad spec.
- Agents must read every milestone to understand current state.
- Source ownership exists but test ownership is missing.
- Security or privacy invariants appear only in review prose.
- Generated protocol files live under `docs/` without a warning.
- Future contract tests exist while milestones say the feature is only planned.
- Known future choices are listed as deferred but not centralized in a decision backlog.
