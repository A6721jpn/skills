# Bottom-to-Datum operation contract

## Contents

- Pinned executor and mailbox lifecycle
- Accepted Bottom-to-Datum sequence and gates
- Failure, retry, and portability limits

## Executor contract

The executor is an external Fusion Python script that reads
`fusion_inspector_action.json` from its task root. The host CLI pins its source
and policy hashes. A compatible copy must expose only these actions and result
paths to this controller:

| Action | Result |
|---|---|
| `import_trial` | `fusion_inspector_action_result.json` |
| `snapshot_active` | `fusion_parametric_inspection.json` |
| `bottom_z_extrude_correction` | `fusion_bottom_z_projection_result.json` |
| `verify_corrected_exports` | `fusion_bottom_z_export_verification.json` |

The exact historical executor imports `annular_thickness_policy.py` when its
module starts, before it dispatches any action. The profile therefore pins that
file as a boot dependency. This controller exposes no annular action, result,
selection data, or validator. Eliminating the boot dependency requires a new
Bottom-only executor revision and a fresh Fusion qualification.

The CLI never calls Autodesk APIs. `stage` atomically replaces the mailbox only
after backing it up into the run directory. It requires an active task lock
whose task ID, thread ID, and protected root match the explicit command
arguments. Fusion must be invoked separately.

## Commands

The examples assume the installed skill root is stored in `$skillRoot`.

```powershell
python "$skillRoot\scripts\fusion_bottom_datum.py" doctor `
  --executor-root "C:\path\to\compatible-task"

python "$skillRoot\scripts\fusion_bottom_datum.py" init-run `
  --archive "C:\path\to\input.f3d" `
  --run-dir "C:\path\to\fresh-run"

python "$skillRoot\scripts\fusion_bottom_datum.py" next `
  --run-dir "C:\path\to\fresh-run"

python "$skillRoot\scripts\fusion_bottom_datum.py" stage `
  --run-dir "C:\path\to\fresh-run" `
  --executor-root "C:\path\to\compatible-task" `
  --task-id "current-task-id" `
  --thread-id "current-codex-thread-id" `
  --replace-mailbox

python "$skillRoot\scripts\fusion_bottom_datum.py" record `
  --run-dir "C:\path\to\fresh-run" `
  --step import-trial `
  --result "C:\path\to\compatible-task\fusion_inspector_action_result.json"
```

The CLI has no recipe selector. The profile must contain exactly
`bottom-datum-add`; any additional recipe is rejected.

For `apply-bottom-datum`, `stage` requires
`--ack-fresh-unsaved-trial`. The flag is an assertion, not a check; confirm the
active Fusion document directly before supplying it.

Use a new run directory for every attempt. `record` accepts only the exact
result path registered by `stage`, and requires both its `generated_at` value
and file modification time to postdate staging. Passed or failed evidence is
immutable; `--replace-result` is only for recovering a partially written
record while the ledger still says `staged`.

`init-run` copies the accepted F3D to `inputs/source.f3d`, verifies its hash and
size, and embeds that collected absolute path in the import action. Every later
command rechecks the copy. At `record`, the mailbox, executor hashes, and all
live prior-result hashes must still match. `status` re-audits each action,
state transition, result, check, and collected artifact.

## Validated operation

Evidence level: historical local round-trip; **not release-ready**. Open
release blockers:

- `historical_compute_all_false`
- `f3d_roundtrip_full_preexisting_health_not_rechecked`

Validated sequence:

1. Import the pinned pretrial F3D into a fresh unsaved document.
2. Confirm the main-body and `DatumSurfaces/UpperFrameBottom` fingerprints and
   the absence of `BottomBoundary_` features.
3. For four uniquely diagnosed source faces, project every boundary edge to the
   global XY plane.
4. Select the historically matched closed profile for each face.
5. Create a New Body extrusion from the Datum face to the original Bottom face.
6. Join each of the four additions to the main body.
7. Require four healthy Extrudes, four healthy Joins, one visible main solid,
   an unchanged hidden root solid, the exact known unhealthy-feature baseline,
   increased volume, and at least 0.99 Datum coverage.
8. Export F3D and STEP, reopen both, and apply the profile gates.

At step 7 the controller copies the fresh F3D and STEP into the run and records
their SHA-256 values. Step 8 must reopen the same original paths while both the
originals and collected copies still match those hashes.

This is not a generic follow-surface algorithm. Only material addition was
proved. Candidate count, input hash, target identity, body fingerprint, profile
topology, and output gates are part of the recipe.

## Failure and retry

- Never automatically retry the mutating step or use `--restage` for it.
- Do not stage a later step until every earlier result is recorded and passed.
- The first successful stage binds later stages to the same executor root,
  task ID, and thread ID.
- Treat a staged mutating action with no result as ambiguous; inspect Fusion and
  the executor result path before doing anything else.
- Do not clean up by deleting arbitrary features. The reliable rollback
  boundary is a separately imported, unsaved trial document.
- Publishing or cloud Save As is outside this operation.

## Portability

The orchestration, hashing, ordering, validation, and evidence ledger are
reusable. The geometry runner is not bundled. This profile is not portable to
another model or executor revision. Either change requires a new source hash,
executor hash set, body fingerprint, Fusion smoke run, and reopen evidence.
