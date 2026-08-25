# Annular 0.5 mm operation contract

## Controller and executor

The host CLI never imports Autodesk APIs and never starts Fusion. It verifies
the profile and external executor, creates an immutable action sequence, stages
one JSON action at a time to `fusion_inspector_action.json`, and records fresh
result evidence in a hash-bound ledger.

The historical executor is a monolithic Fusion script. It eagerly imports both
`annular_thickness_policy.py` and `bottom_z_policy.py` at boot, so `doctor` must
retain both file pins. The annular action does not call the Bottom policy, and
this Skill has no dependency on the separate Bottom Skill. Removing the boot
import requires a new executor revision, Fusion smoke run, and reopen evidence.

## Input contract

The accepted input is exactly the Bottom-corrected Upper Frame F3D:

- SHA-256: `EC3049F0E8059E593550D3DC89CD5AD86CFE379A6D434BACC03C2EBF8C725280`
- size: `12733310` bytes

`init-run` copies those bytes to `inputs/source.f3d` and all later commands
recheck the copy. The snapshot must also match the visible main body, hidden
root body, seven known unhealthy features, and these eight prerequisite feature
names:

- `BottomBoundary_FromDatum_ToOriginal_0` through `_3`
- `BottomBoundary_Join_0` through `_3`

These names describe the qualified input state. They are not permission to run
or modify the Bottom recipe. If the exact input is unavailable, stop; do not
invoke another Skill automatically.

## Commands

The Skill exposes one recipe only, so no command accepts `--recipe`.

```powershell
python "$skillRoot\scripts\fusion_annular_0p5.py" doctor `
  --executor-root "C:\path\to\compatible-task"

python "$skillRoot\scripts\fusion_annular_0p5.py" init-run `
  --archive "C:\path\to\bottom-corrected.f3d" `
  --run-dir "C:\path\to\fresh-run"

python "$skillRoot\scripts\fusion_annular_0p5.py" next `
  --run-dir "C:\path\to\fresh-run"

python "$skillRoot\scripts\fusion_annular_0p5.py" stage `
  --run-dir "C:\path\to\fresh-run" `
  --executor-root "C:\path\to\compatible-task" `
  --task-id "current-task-id" `
  --thread-id "current-codex-thread-id" `
  --replace-mailbox

python "$skillRoot\scripts\fusion_annular_0p5.py" record `
  --run-dir "C:\path\to\fresh-run" `
  --step import-trial `
  --result "C:\path\to\compatible-task\fusion_inspector_action_result.json"
```

For `apply-annular-thickness`, `stage` also requires
`--ack-fresh-unsaved-trial`. The flag is an assertion, not a live Fusion check.

`record` requires the registered result path, a post-stage `generated_at`, a
post-stage file mtime, unchanged mailbox bytes, an unchanged executor, and an
unchanged live chain of prior results. Import results must echo the collected
input path. Failed or passed evidence cannot be replaced; `--replace-result`
only recovers an interrupted record while the ledger remains `staged`.

## Geometry sequence and gates

1. Import the accepted F3D into a fresh unsaved document.
2. Verify the source fingerprint and absence of `AnnularThickness_` features.
3. Resolve the 15 hash-bound face records in
   `assets/upper-frame-v1-annular-selection.json` and compare full geometric
   signatures, not only tokens.
4. Require exactly 12 cylinder-axis groups sharing one freeform top face.
5. Offset the top face inward using `-annularWallThickness`, exactly 0.5 mm.
6. Naturally extend the sheet by 0.5 mm at the hole boundaries.
7. Create exactly 12 healthy Replace Face features and zero fallback features.
8. Require the pinned solid/body result, 88 valid samples, maximum thickness
   error at most 0.01 mm, 24 cylinder deltas, and diameter/axis changes within
   0.001 mm and 0.001 degree.
9. Require the validation body to match the apply body in the same run.

The selection manifest is byte-pinned at SHA-256
`4FA5EE0FAB5E1E791CF153CD5C34697659B9CAED985A3330EC1C5EBE8BC3C312`.

## Evidence boundary

Historical completion is `historical_geometry_replay`, not release evidence.
Outside-region geometry and the hidden non-target body were not independently
compared, and no dedicated annular F3D/STEP reopen was bound to the run. Keep
all three release blockers visible even when every executable gate passes.

The preserved apply JSON and preserved validation JSON also contain different
body volume, area, and edge-count snapshots. `audit-history` intentionally
checks those historical files independently; it does not claim they form one
same-run ledger. A newly recorded run is stricter and fails unless its
validation body matches its recorded apply body.

Never automatically retry the mutating action, delete arbitrary features, save
or publish the result, or convert a different model/hash into an accepted input.
