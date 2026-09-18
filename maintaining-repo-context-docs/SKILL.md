---
name: maintaining-repo-context-docs
description: Audit and refresh a repository's existing agent-facing docs (reading guide, architecture overview, ADRs, milestones, ownership maps, runbook) after development has moved on. Use when such docs exist but are stale or conflicting; to create them from scratch use repo-context-docs.
---

# Maintaining Repo Context Docs

## Overview

Refresh an existing repository documentation spine after code and tests have moved. Preserve the spine; do not rewrite it from scratch unless the structure itself is the problem.

## Core Loop

1. **Snapshot what changed.** Inspect `git status`, recent files, docs, tests, and source ownership changes. Note untracked/generated docs separately from tracked current-state docs.
2. **Run a no-context read test.** A fresh reader should start with the repo entry docs and answer: current state, invariants, owners, implemented/deferred work, ADRs to read, and first files for one likely change. Record files read, rough word count, scores, guesses, and stale/conflicting statements.
3. **Compare docs to repo reality.** Check these drift points:
   - README status vs milestone docs.
   - agent guide read order vs actual docs/source/tests.
   - architecture overview vs implemented modules.
   - ADRs vs new design constraints.
   - milestone table vs test directories and feature docs.
   - runbook commands vs the project's build/config manifest.
   - generated/review/planning artifacts vs current-state labels.
   - forward-looking contract tests that now pass vs docs still calling the work planned.
4. **Patch the smallest responsible doc.** Fix the doc closest to the drift:
   - read order or ownership -> agent guide
   - architecture boundary -> architecture overview
   - rationale or accepted tradeoff -> ADR
   - not-yet-decided risk -> ADR backlog
   - status/timeline -> milestones
   - commands/env/ops -> runbook
   - security invariant -> security model
   - entry routing -> README
5. **Re-test.** Run the same no-context questions. The reader should use fewer files, guess less, and land on the right source/test files.

## Maintenance Rules

| Symptom | Fix |
| --- | --- |
| README becomes a second design doc | Move detail to runbook, milestones, or architecture overview |
| New test directory is unexplained | Update test ownership map and milestone status |
| Feature is implemented but listed as deferred | Update milestone and architecture status |
| Future contract tests look like completed work | Label as active/contract/planned |
| Passing source/tests show a feature is now baseline | Promote the milestone/status docs, then update guide and overview |
| Reconnect or persistence language is ambiguous | Separate memory-only runtime restoration from persistent storage |
| New operational rule lacks rationale | Add ADR or ADR backlog item |
| Agent reads generated files for orientation | Add generated README or update guide exclusions |
| Agent reads many milestone docs for one task | Add task-specific read path or source ownership row |
| Review/planning artifact looks authoritative | Label it as supporting context |

## Scores To Track

Use the shared rubric in `repo-context-docs/references/evaluation-rubric.md` (or the repo's own). Record before/after scores and the initial-entry word count; a score drop, more guessing, or a larger initial read set is a regression.

## Relationship To Initial Creation

If the repo has no agent guide, current architecture overview, ADR area, milestone table, or evaluation rubric, use `repo-context-docs` first. Use this skill only after a documentation spine already exists.

## Stop Conditions

Stop after the smallest coherent refresh. Do not opportunistically rewrite all docs, normalize prose style everywhere, or update historical notes unless they actively mislead current readers. Keep the audit narrow: identify drift symptoms first, then open only the responsible docs and the minimum source/tests needed to verify reality.

