---
name: fusion-upper-frame-bottom-datum-add
description: Prepare, stage, and verify the pinned Upper Frame add-only Bottom-to-Datum correction, including F3D/STEP round-trip evidence. Use for replaying or auditing that exact operation; do not use for annular thickness or generic surface repair.
---

# Fusion Upper Frame Bottom to Datum

Use the deterministic host CLI in `scripts/fusion_bottom_datum.py`. It prepares
and checks JSON actions; Fusion geometry still executes inside the compatible
external `fusion_inspector` script.

This is a pinned replay controller, not a self-contained Fusion add-in. The
geometry implementation remains in the exact executor revision accepted by
`doctor`. Extracting a standalone Bottom-only executor requires a separate
Fusion qualification and reopen run.

## Boundaries

- Use only the F3D accepted by `assets/upper-frame-bottom-datum-v1-profile.json`:
  SHA-256 `95656EB4C373CE1E5A1C16F6F7B23725570304F8EA1D268484160E01B3097CF4`,
  size `12206579` bytes. A different input is a new qualification task, not a
  replay.
- Never edit the protected historical task merely to run this skill. Point the
  CLI at an executor task that passes `doctor`. Its active
  `.codex-task-lock.json` must belong to the current task/thread and protect the
  executor root.
- Import the F3D into a fresh unsaved document. Never retry the mutating action
  in the same document. On failure, preserve the run evidence.
- Do not save, publish, overwrite, close, or discard a Fusion document merely
  because this skill was invoked. Those are separate mutations.
- This operation is add-only: four Extrudes followed by four Joins. Do not use
  it for cutting, crossing, Boundary Fill, thickness, or other surface edits.

The historical executor imports `annular_thickness_policy.py` at process boot
even when it runs only this Bottom operation. Its hash therefore remains an
executor boot prerequisite in the profile; it is not an operation exposed by
this skill.

## Workflow

1. Read [references/operation-contract.md](references/operation-contract.md)
   before the first execution or whenever the executor/profile changes.
2. Run `doctor` against the intended executor root. Hash drift is a hard stop.
3. Run `init-run` with the accepted input archive and a fresh run directory.
   It copies the F3D into the run and makes the import action refer to that
   hash-verified copy.
4. Use `next`, then `stage`. `stage` writes only the action mailbox and never
   starts Fusion. For `apply-bottom-datum`, supply
   `--ack-fresh-unsaved-trial` only after directly confirming that condition.
5. Run the registered Fusion script once. Immediately use `record` to copy and
   validate the exact freshly generated executor result before staging the
   next action.
6. Use `status`. A failed check stops the run; begin again from a fresh import.

Never restage the mutating step. Passed and failed records are immutable. The
apply step copies and hashes its F3D/STEP exports into the run; the reopen step
must refer to those same bytes.

The recipe can reach historical local round-trip completion, but it is not
release-ready. `historical_compute_all_false` and
`f3d_roundtrip_full_preexisting_health_not_rechecked` remain open. A completed
ledger means only that all historical replay gates passed.

## Historical audit

Use `audit-history` to recheck the two preserved result JSON files and the
Bottom F3D/STEP hashes without opening Fusion. This confirms the extracted
historical evidence, not a newly staged run.
