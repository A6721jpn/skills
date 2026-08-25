---
name: fusion-upper-frame-annular-0p5
description: Prepare, stage, and verify the pinned Upper Frame Fusion recipe that repairs the captured annular region to exactly 0.5 mm local-normal thickness. Use only with the accepted Bottom-corrected Upper Frame F3D; do not use for Bottom-to-Datum correction, other thicknesses or models, or generic surface repair.
---

# Fusion Upper Frame Annular 0.5 mm

Use `scripts/fusion_annular_0p5.py` as the deterministic host controller. It
prepares and validates JSON actions; Fusion geometry still executes in the
external `fusion_inspector` revision accepted by `doctor`.

This Skill is independent of the Bottom-to-Datum Skill. Never import, invoke,
or read files from that Skill. Its only Bottom-related precondition is the
exact corrected F3D on which the annular selection was qualified:

- SHA-256 `EC3049F0E8059E593550D3DC89CD5AD86CFE379A6D434BACC03C2EBF8C725280`
- size `12733310` bytes

The caller may provide that F3D from any location. A different byte stream is a
new qualification task, not a replay.

## Boundaries

- This is a pinned replay controller, not a self-contained Fusion add-in.
- Work only in a freshly imported, unsaved trial document. Never retry the
  mutating step in the same document.
- Do not save, publish, overwrite, close, or discard a Fusion document merely
  because this Skill was invoked. Those are separate mutations.
- Thickness is exactly 0.5 mm. Planar and Boundary Fill fallbacks are forbidden.
- The active executor task lock must match the current task, thread, and root.
- `bottom_z_policy.py` remains hash-pinned only because the historical executor
  imports it at boot. This does not authorize or call a Bottom operation.

## Workflow

Read [references/operation-contract.md](references/operation-contract.md)
before first execution or whenever the input, profile, or executor changes.

1. Run `doctor` against the intended executor root. Hash drift is a hard stop.
2. Run `init-run` with the accepted F3D and a new run directory.
3. Use `next`, then `stage`. `stage` writes the mailbox but never starts Fusion.
4. For `apply-annular-thickness`, provide
   `--ack-fresh-unsaved-trial` only after directly confirming that condition.
5. Run the registered Fusion script once, then immediately use `record` on the
   exact freshly generated result path.
6. Stop on any failed check and start a new run from a fresh import.

Never restage a mutating step. Passed and failed evidence is immutable.

Completion proves only the historical geometry-replay gates. It is **not
release-ready** while these blockers remain:

- `outside_region_unchanged_not_measured`
- `non_target_hidden_body_unchanged_not_measured`
- `dedicated_annular_f3d_step_reopen_not_bound_to_run`

Use `audit-history` to hash-check and revalidate preserved historical evidence
without opening Fusion. It does not prove that a newly staged run succeeded.
