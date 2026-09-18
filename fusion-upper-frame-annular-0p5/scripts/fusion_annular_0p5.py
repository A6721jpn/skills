#!/usr/bin/env python3
"""Fail-closed host orchestration for the pinned annular 0.5 mm Fusion action.

This module never imports ``adsk`` and never starts Fusion.  It creates pinned
action JSON, stages one action at a time into a compatible executor mailbox,
and records immutable result evidence after applying pure validation gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = SKILL_ROOT / "assets" / "upper-frame-v1-annular-0p5-profile.json"
RECIPE_NAME = "annular-0p5"
RECIPE_ID = "fusion.annular-local-normal-thickness/v1"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_PRECONDITION = 3
EXIT_VALIDATION = 5


class CliFailure(RuntimeError):
    def __init__(self, message: str, exit_code: int = EXIT_PRECONDITION):
        super().__init__(message)
        self.exit_code = exit_code


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def file_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "path": str(path.resolve())}
    stat = path.stat()
    return {
        "exists": True,
        "path": str(path.resolve()),
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(path),
    }


def _same_resolved_path(one: Path, two: Path) -> bool:
    return os.path.normcase(str(one.resolve())) == os.path.normcase(str(two.resolve()))


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CliFailure(f"{label} is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CliFailure(f"{label} is not ISO-8601: {value}") from error
    if parsed.tzinfo is None:
        raise CliFailure(f"{label} has no timezone: {value}")
    return parsed.astimezone(timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CliFailure(f"JSON file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise CliFailure(f"Invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise CliFailure(f"Expected a JSON object in {path}")
    return value


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    # Keep the temporary name short: Windows fails on paths over 260 characters
    # and run directories are already deep.
    handle, temporary_name = tempfile.mkstemp(dir=str(path.parent), prefix=".", suffix=".tmp")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(dir=str(destination.parent), prefix=".", suffix=".tmp")
    temporary = Path(temporary_name)
    try:
        with source.open("rb") as input_stream, os.fdopen(handle, "wb") as output:
            shutil.copyfileobj(input_stream, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def load_profile(path: Path) -> tuple[Path, dict[str, Any]]:
    resolved = path.resolve()
    profile = load_json(resolved)
    if profile.get("schema_version") != 1:
        raise CliFailure("Unsupported profile schema_version")
    if not profile.get("profile_id"):
        raise CliFailure("Profile has no profile_id")
    recipes = profile.get("recipes")
    if not isinstance(recipes, dict) or set(recipes) != {RECIPE_NAME}:
        raise CliFailure(
            f"Profile must contain exactly the {RECIPE_NAME!r} recipe"
        )
    if recipes[RECIPE_NAME].get("recipe_id") != RECIPE_ID:
        raise CliFailure("Profile annular recipe_id mismatch")
    return resolved, profile


def get_recipe(profile: dict[str, Any]) -> dict[str, Any]:
    recipe = (profile.get("recipes") or {}).get(RECIPE_NAME)
    if not isinstance(recipe, dict) or recipe.get("recipe_id") != RECIPE_ID:
        raise CliFailure("Profile does not contain the pinned annular recipe")
    return recipe


def get_step(recipe: dict[str, Any], step_id: str) -> tuple[int, dict[str, Any]]:
    for index, step in enumerate(recipe.get("steps") or []):
        if step.get("id") == step_id:
            return index, step
    raise CliFailure(f"Recipe has no step {step_id!r}", EXIT_USAGE)


def doctor_check(
    profile: dict[str, Any], executor_root: Path
) -> dict[str, Any]:
    root = executor_root.resolve()
    issues: list[str] = []
    observations: dict[str, Any] = {"executor_root": str(root), "files": []}
    executor = profile["executor"]
    for entry in executor.get("required_files") or []:
        relative = Path(entry["path"])
        path = root / relative
        record: dict[str, Any] = {
            "path": str(path),
            "expected_sha256": str(entry["sha256"]).upper(),
            "exists": path.is_file(),
        }
        if path.is_file():
            actual = sha256_file(path)
            record["actual_sha256"] = actual
            if actual != record["expected_sha256"]:
                issues.append(f"Executor hash drift: {relative}")
        else:
            issues.append(f"Missing executor file: {relative}")
        observations["files"].append(record)

    source_path = root / "fusion_inspector" / "fusion_inspector.py"
    if source_path.is_file():
        source = source_path.read_text(encoding="utf-8")
        missing_markers = [
            marker
            for marker in executor.get("required_source_markers") or []
            if marker not in source
        ]
        observations["missing_source_markers"] = missing_markers
        issues.extend(f"Missing executor action marker: {item}" for item in missing_markers)

    action_mailbox = root / executor["action_mailbox"]
    observations["action_mailbox"] = str(action_mailbox)
    return {
        "success": not issues,
        "issues": issues,
        "warnings": [],
        "observations": observations,
    }


def _template_value(value: Any, replacements: dict[str, Any]) -> Any:
    if isinstance(value, str) and value in replacements:
        return replacements[value]
    if isinstance(value, list):
        return [_template_value(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _template_value(item, replacements) for key, item in value.items()}
    return value


def _selection_tokens(profile_path: Path, recipe: dict[str, Any]) -> list[str]:
    selection_name = recipe.get("selection_asset")
    if not selection_name:
        return []
    selection_path = profile_path.parent / str(selection_name)
    expected_hash = str(recipe.get("selection_asset_sha256") or "").upper()
    if not expected_hash:
        raise CliFailure("Selection asset has no pinned SHA-256")
    if not selection_path.is_file():
        raise CliFailure(f"Selection asset does not exist: {selection_path}")
    actual_hash = sha256_file(selection_path)
    if actual_hash != expected_hash:
        raise CliFailure(
            "Selection asset hash drift: "
            f"expected {expected_hash}, got {actual_hash}"
        )
    selection = load_json(selection_path)
    records = selection.get("records") or []
    tokens = [record.get("face_token") for record in records]
    if len(tokens) != 15 or any(not isinstance(token, str) or not token for token in tokens):
        raise CliFailure("Selection asset must contain exactly 15 non-empty face tokens")
    if len(set(tokens)) != len(tokens):
        raise CliFailure("Selection asset contains duplicate face tokens")
    return tokens


def _accepted_archive(recipe: dict[str, Any], archive: Path) -> dict[str, Any]:
    if archive.suffix.lower() != ".f3d":
        raise CliFailure("Input archive must have an .f3d suffix")
    if not archive.is_file():
        raise CliFailure(f"Input archive does not exist: {archive}")
    digest = sha256_file(archive)
    size = archive.stat().st_size
    for accepted in recipe.get("accepted_inputs") or []:
        if (
            str(accepted.get("sha256") or "").upper() == digest
            and int(accepted.get("size_bytes", -1)) == size
        ):
            return {"path": str(archive), "sha256": digest, "size_bytes": size}
    raise CliFailure(
        "Input F3D hash/size is not accepted by this pinned recipe. "
        "Qualify a new profile instead of bypassing the gate."
    )


def create_run(
    profile_path: Path,
    profile: dict[str, Any],
    archive_path: Path,
    run_dir: Path,
) -> dict[str, Any]:
    recipe = get_recipe(profile)
    archive = archive_path.resolve()
    accepted_archive = _accepted_archive(recipe, archive)
    resolved_run = run_dir.resolve()
    if resolved_run.exists():
        raise CliFailure(f"Run directory already exists: {resolved_run}")
    (resolved_run / "actions").mkdir(parents=True)
    (resolved_run / "results").mkdir()
    (resolved_run / "checks").mkdir()
    (resolved_run / "staged").mkdir()
    (resolved_run / "inputs").mkdir()

    collected_archive = resolved_run / "inputs" / "source.f3d"
    atomic_copy(archive, collected_archive)
    if (
        sha256_file(collected_archive) != accepted_archive["sha256"]
        or collected_archive.stat().st_size != accepted_archive["size_bytes"]
    ):
        raise CliFailure("Collected run input does not match the accepted F3D")

    selection_tokens = _selection_tokens(profile_path, recipe)
    replacements = {
        "{archive_path}": str(collected_archive),
        "{selection_face_tokens}": selection_tokens,
    }
    manifest_steps: list[dict[str, Any]] = []
    ledger_steps: dict[str, dict[str, Any]] = {}
    for ordinal, step in enumerate(recipe.get("steps") or [], start=1):
        step_id = str(step["id"])
        action = _template_value(step["action"], replacements)
        action_path = resolved_run / "actions" / f"{ordinal:02d}-{step_id}.json"
        atomic_write_json(action_path, action)
        manifest_steps.append(
            {
                "ordinal": ordinal,
                "id": step_id,
                "action_file": str(action_path.relative_to(resolved_run)),
                "action_sha256": sha256_file(action_path),
                "result_kind": step["result_kind"],
                "result_path": step["result_path"],
                "mutates_geometry": bool(step.get("mutates_geometry")),
            }
        )
        ledger_steps[step_id] = {"state": "pending"}

    manifest = {
        "schema_version": 1,
        "profile_id": profile["profile_id"],
        "profile_path": str(profile_path),
        "profile_sha256": sha256_file(profile_path),
        "recipe": RECIPE_NAME,
        "recipe_id": recipe["recipe_id"],
        "completion_class": recipe["completion_class"],
        "release_blockers": recipe.get("release_blockers") or [],
        "input_archive": {
            "source_path": accepted_archive["path"],
            "collected_file": str(collected_archive.relative_to(resolved_run)),
            "sha256": accepted_archive["sha256"],
            "size_bytes": accepted_archive["size_bytes"],
        },
        "executor_contract": profile["executor"]["contract_id"],
        "steps": manifest_steps,
    }
    manifest_path = resolved_run / "run-manifest.json"
    atomic_write_json(manifest_path, manifest)
    ledger = {
        "schema_version": 1,
        "run_manifest_sha256": sha256_file(manifest_path),
        "steps": ledger_steps,
    }
    atomic_write_json(resolved_run / "ledger.json", ledger)
    return {
        "success": True,
        "run_dir": str(resolved_run),
        "recipe": RECIPE_NAME,
        "input_sha256": accepted_archive["sha256"],
        "step_count": len(manifest_steps),
        "next_step": manifest_steps[0]["id"] if manifest_steps else None,
        "release_blockers": manifest["release_blockers"],
    }


def _run_relative_path(root: Path, value: Any, label: str) -> Path:
    relative = Path(str(value or ""))
    if not str(value or "") or relative.is_absolute():
        raise CliFailure(f"{label} must be a non-empty run-relative path")
    resolved = (root / relative).resolve()
    try:
        common = os.path.commonpath([str(root.resolve()), str(resolved)])
    except ValueError as error:
        raise CliFailure(f"{label} escapes the run directory") from error
    if os.path.normcase(common) != os.path.normcase(str(root.resolve())):
        raise CliFailure(f"{label} escapes the run directory")
    return resolved



def _verify_ledger_integrity(
    root: Path,
    manifest: dict[str, Any],
    ledger: dict[str, Any],
) -> None:
    if ledger.get("schema_version") != 1:
        raise CliFailure("Unsupported ledger schema_version")
    manifest_steps = manifest.get("steps") or []
    expected_ids = [str(step.get("id")) for step in manifest_steps]
    ledger_steps = ledger.get("steps")
    if not isinstance(ledger_steps, dict) or set(ledger_steps) != set(expected_ids):
        raise CliFailure("Ledger step set differs from the run manifest")

    encountered_terminal = False
    any_started = False
    for manifest_step in manifest_steps:
        step_id = manifest_step["id"]
        ordinal = int(manifest_step["ordinal"])
        action_file = _run_relative_path(
            root, manifest_step.get("action_file"), f"Action file for {step_id}"
        )
        if (
            not action_file.is_file()
            or sha256_file(action_file) != manifest_step.get("action_sha256")
        ):
            raise CliFailure(f"Action evidence changed: {step_id}")

        record = ledger_steps[step_id]
        if not isinstance(record, dict):
            raise CliFailure(f"Ledger step record is not an object: {step_id}")
        state = record.get("state")
        if state not in {"pending", "staged", "passed", "failed"}:
            raise CliFailure(f"Invalid ledger state for {step_id}: {state}")
        if encountered_terminal and state != "pending":
            raise CliFailure("Ledger states are not a valid passed-prefix transition")
        if state == "pending":
            encountered_terminal = True
            continue
        any_started = True
        if state == "staged":
            encountered_terminal = True
            staged_path = root / "staged" / f"{step_id}.json"
            if (
                record.get("action_sha256") != manifest_step.get("action_sha256")
                or not staged_path.is_file()
                or sha256_file(staged_path) != record.get("staged_sha256")
            ):
                raise CliFailure(f"Staged evidence changed or is incomplete: {step_id}")
            staged = load_json(staged_path)
            if (
                staged.get("step") != step_id
                or staged.get("action_sha256") != manifest_step.get("action_sha256")
            ):
                raise CliFailure(f"Staged evidence identity mismatch: {step_id}")
            staged_mailbox = Path(str(staged.get("mailbox") or ""))
            if (
                not staged_mailbox.is_file()
                or sha256_file(staged_mailbox) != manifest_step.get("action_sha256")
            ):
                raise CliFailure(f"Live staged mailbox changed: {step_id}")
            continue

        expected_result = root / "results" / f"{ordinal:02d}-{step_id}.json"
        expected_check = root / "checks" / f"{ordinal:02d}-{step_id}.json"
        result_file = _run_relative_path(
            root, record.get("result_file"), f"Result file for {step_id}"
        )
        check_file = _run_relative_path(
            root, record.get("check_file"), f"Check file for {step_id}"
        )
        if not _same_resolved_path(result_file, expected_result):
            raise CliFailure(f"Ledger result path is not canonical: {step_id}")
        if not _same_resolved_path(check_file, expected_check):
            raise CliFailure(f"Ledger check path is not canonical: {step_id}")
        if (
            not result_file.is_file()
            or sha256_file(result_file) != record.get("result_sha256")
        ):
            raise CliFailure(f"Recorded result evidence changed: {step_id}")
        if (
            not check_file.is_file()
            or sha256_file(check_file) != record.get("check_sha256")
        ):
            raise CliFailure(f"Recorded check evidence changed: {step_id}")
        check = load_json(check_file)
        expected_success = state == "passed"
        if check.get("success") is not expected_success:
            raise CliFailure(f"Check success does not match ledger state: {step_id}")
        if expected_success and check.get("issues") != []:
            raise CliFailure(f"Passed check contains issues: {step_id}")
        if not expected_success and not check.get("issues"):
            raise CliFailure(f"Failed check does not preserve its issues: {step_id}")
        if (
            check.get("run_manifest_sha256") != ledger.get("run_manifest_sha256")
            or check.get("profile_id") != manifest.get("profile_id")
            or check.get("recipe") != manifest.get("recipe")
            or check.get("recipe_id") != manifest.get("recipe_id")
            or check.get("step") != step_id
            or check.get("result_sha256") != record.get("result_sha256")
            or not _same_resolved_path(
                Path(str(check.get("result_path") or "")), result_file
            )
            or check.get("release_blockers") != manifest.get("release_blockers")
        ):
            raise CliFailure(f"Check identity/provenance mismatch: {step_id}")
        if state == "failed":
            encountered_terminal = True

    binding = ledger.get("executor_binding")
    if any_started and (
        not isinstance(binding, dict)
        or not binding.get("executor_root")
        or not binding.get("task_id")
        or not binding.get("thread_id")
    ):
        raise CliFailure("Started run has no complete executor binding")


def load_run(
    run_dir: Path,
) -> tuple[Path, dict[str, Any], dict[str, Any], Path, dict[str, Any], dict[str, Any]]:
    root = run_dir.resolve()
    manifest_path = root / "run-manifest.json"
    ledger_path = root / "ledger.json"
    manifest = load_json(manifest_path)
    ledger = load_json(ledger_path)
    if ledger.get("run_manifest_sha256") != sha256_file(manifest_path):
        raise CliFailure("Run manifest hash no longer matches the ledger")
    profile_path = Path(str(manifest.get("profile_path") or "")).resolve()
    if sha256_file(profile_path) != manifest.get("profile_sha256"):
        raise CliFailure("Pinned profile hash changed after the run was created")
    _, profile = load_profile(profile_path)
    if profile.get("profile_id") != manifest.get("profile_id"):
        raise CliFailure("Pinned profile ID changed after the run was created")
    input_record = manifest.get("input_archive") or {}
    input_path = root / str(input_record.get("collected_file") or "")
    if not input_path.is_file():
        raise CliFailure("Collected run input is missing")
    if (
        sha256_file(input_path) != input_record.get("sha256")
        or input_path.stat().st_size != int(input_record.get("size_bytes") or -1)
    ):
        raise CliFailure("Collected run input hash/size changed")
    if manifest.get("recipe") != RECIPE_NAME or manifest.get("recipe_id") != RECIPE_ID:
        raise CliFailure("Run manifest is not the pinned annular recipe")
    recipe = get_recipe(profile)
    _verify_ledger_integrity(root, manifest, ledger)
    return root, manifest, ledger, profile_path, profile, recipe


def _run_status(
    manifest: dict[str, Any], ledger: dict[str, Any]
) -> dict[str, Any]:
    steps = []
    failed = False
    complete = True
    next_step = None
    for step in manifest.get("steps") or []:
        step_id = step["id"]
        state_record = (ledger.get("steps") or {}).get(step_id) or {"state": "missing"}
        state = state_record.get("state")
        steps.append({"id": step_id, **state_record})
        if state == "failed":
            failed = True
        if state != "passed":
            complete = False
            if next_step is None:
                next_step = step_id
    blockers = manifest.get("release_blockers") or []
    return {
        "success": not failed,
        "recipe": manifest.get("recipe"),
        "complete": complete,
        "release_ready": bool(complete and not blockers),
        "release_blockers": blockers,
        "next_step": next_step,
        "steps": steps,
    }


def _next_state(manifest: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    status = _run_status(manifest, ledger)
    if any(step.get("state") == "failed" for step in status["steps"]):
        status["instruction"] = "Stop. Preserve evidence and start a fresh run."
        return status
    if status["complete"]:
        status["instruction"] = "All executable recipe steps passed."
        return status
    next_record = next(step for step in status["steps"] if step["id"] == status["next_step"])
    if next_record.get("state") == "staged":
        status["instruction"] = "Run Fusion once, then record the expected result."
    else:
        status["instruction"] = "Stage this step after checking its preconditions."
    return status


def verify_task_lock(
    profile: dict[str, Any],
    executor_root: Path,
    expected_task_id: str,
    expected_thread_id: str,
) -> dict[str, Any]:
    root = executor_root.resolve()
    lock_name = str(profile["executor"].get("task_lock_file") or "")
    if not lock_name:
        raise CliFailure("Profile does not define an executor task lock")
    lock_path = root / lock_name
    lock = load_json(lock_path)
    issues: list[str] = []
    if lock.get("state") != "active":
        issues.append("Task lock is not active")
    if lock.get("task_id") != expected_task_id:
        issues.append("Task lock task_id does not match --task-id")
    if lock.get("thread_id") != expected_thread_id:
        issues.append("Task lock thread_id does not match --thread-id")
    protected = []
    for value in lock.get("protected_paths") or []:
        try:
            protected.append(Path(str(value)).resolve())
        except (OSError, RuntimeError):
            continue
    if not any(_same_resolved_path(root, item) for item in protected):
        issues.append("Task lock protected_paths does not include executor root")
    if issues:
        raise CliFailure("Executor task lock rejected: " + "; ".join(issues))
    return {
        "path": str(lock_path.resolve()),
        "sha256": sha256_file(lock_path),
        "task_id": expected_task_id,
        "thread_id": expected_thread_id,
        "state": "active",
    }


def _assert_bound_executor(
    ledger: dict[str, Any],
    executor_root: Path,
    task_id: str,
    thread_id: str,
) -> None:
    binding = ledger.get("executor_binding")
    if not binding:
        return
    expected_root = Path(str(binding.get("executor_root") or ""))
    if not _same_resolved_path(executor_root, expected_root):
        raise CliFailure("Run is already bound to a different executor root")
    if binding.get("task_id") != task_id or binding.get("thread_id") != thread_id:
        raise CliFailure("Run is already bound to a different task/thread lock")


def _assert_prior_result_chain(
    root: Path,
    manifest: dict[str, Any],
    ledger: dict[str, Any],
    profile: dict[str, Any],
    recipe: dict[str, Any],
    step_index: int,
    executor_root: Path,
) -> None:
    for earlier in manifest["steps"][:step_index]:
        step_id = earlier["id"]
        record = ledger["steps"][step_id]
        if record.get("state") != "passed":
            raise CliFailure(f"Earlier step has not passed: {step_id}")
        result_hash = str(record.get("result_sha256") or "")
        check_hash = str(record.get("check_sha256") or "")
        result_file = root / str(record.get("result_file") or "")
        check_file = root / str(record.get("check_file") or "")
        if not result_hash or not result_file.is_file():
            raise CliFailure(f"Recorded result evidence is incomplete: {step_id}")
        if sha256_file(result_file) != result_hash:
            raise CliFailure(f"Recorded result evidence changed: {step_id}")
        if not check_hash or not check_file.is_file() or sha256_file(check_file) != check_hash:
            raise CliFailure(f"Recorded check evidence changed: {step_id}")
        _earlier_index, recipe_step = get_step(recipe, step_id)
        live_result = (
            executor_root.resolve()
            / profile["executor"]["result_paths"][recipe_step["result_path"]]
        )
        if not live_result.is_file() or sha256_file(live_result) != result_hash:
            raise CliFailure(
                f"Executor result no longer matches recorded evidence: {step_id}"
            )


def stage_action(
    run_dir: Path,
    executor_root: Path,
    task_id: str,
    thread_id: str,
    requested_step: str | None,
    replace_mailbox: bool,
    restage: bool,
    ack_fresh_unsaved_trial: bool,
) -> dict[str, Any]:
    root, manifest, ledger, _profile_path, profile, recipe = load_run(run_dir)
    resolved_executor = executor_root.resolve()
    lock_record = verify_task_lock(
        profile, resolved_executor, task_id, thread_id
    )
    _assert_bound_executor(ledger, resolved_executor, task_id, thread_id)
    check = doctor_check(profile, executor_root)
    if not check["success"]:
        raise CliFailure("Executor doctor failed: " + "; ".join(check["issues"]))

    status = _run_status(manifest, ledger)
    if any(item.get("state") == "failed" for item in status["steps"]):
        raise CliFailure("The run already contains a failed step; do not continue")
    step_id = requested_step or status.get("next_step")
    if not step_id:
        raise CliFailure("The run has no remaining step")
    step_index, recipe_step = get_step(recipe, step_id)
    manifest_step = manifest["steps"][step_index]

    for earlier in manifest["steps"][:step_index]:
        if ledger["steps"][earlier["id"]].get("state") != "passed":
            raise CliFailure(f"Earlier step has not passed: {earlier['id']}")
    current_state = ledger["steps"][step_id].get("state")
    if current_state == "passed":
        raise CliFailure(f"Step already passed: {step_id}")
    if current_state == "failed":
        raise CliFailure(f"Step already failed: {step_id}")
    if (
        current_state == "staged"
        and restage
        and recipe_step.get("mutates_geometry")
    ):
        raise CliFailure(
            "A mutating step can never be restaged; preserve evidence and start a fresh run"
        )
    if current_state == "staged" and not restage:
        raise CliFailure(
            f"Step is already staged: {step_id}. Inspect/collect its result; "
            "use --restage only if Fusion definitely did not execute it."
        )
    if recipe_step.get("mutates_geometry") and not ack_fresh_unsaved_trial:
        raise CliFailure(
            "Mutating step requires --ack-fresh-unsaved-trial after direct confirmation"
        )

    _assert_prior_result_chain(
        root,
        manifest,
        ledger,
        profile,
        recipe,
        step_index,
        resolved_executor,
    )

    action_path = root / manifest_step["action_file"]
    if sha256_file(action_path) != manifest_step["action_sha256"]:
        raise CliFailure(f"Action file hash changed: {action_path}")
    mailbox = resolved_executor / profile["executor"]["action_mailbox"]
    expected_result = (
        resolved_executor
        / profile["executor"]["result_paths"][recipe_step["result_path"]]
    )
    result_pre_stage = file_state(expected_result)
    if mailbox.exists() and not replace_mailbox:
        raise CliFailure(
            f"Executor mailbox already exists: {mailbox}. "
            "Use --replace-mailbox to back it up and replace it atomically."
        )
    backup = None
    if mailbox.exists():
        old_hash = sha256_file(mailbox)
        backup = root / "mailbox-backups" / f"{step_id}-{old_hash[:16]}.json"
        if not backup.exists():
            atomic_copy(mailbox, backup)
    staged_at_epoch_ns = time.time_ns()
    staged_at_utc = datetime.now(timezone.utc).isoformat()
    atomic_copy(action_path, mailbox)
    if sha256_file(mailbox) != manifest_step["action_sha256"]:
        raise CliFailure("Staged mailbox hash does not match the pinned action")

    staged_record = {
        "step": step_id,
        "action_sha256": manifest_step["action_sha256"],
        "executor_root": str(resolved_executor),
        "task_lock": lock_record,
        "mailbox": str(mailbox),
        "mailbox_backup": str(backup) if backup else None,
        "expected_result": str(expected_result),
        "result_pre_stage": result_pre_stage,
        "staged_at_epoch_ns": staged_at_epoch_ns,
        "staged_at_utc": staged_at_utc,
    }
    staged_path = root / "staged" / f"{step_id}.json"
    atomic_write_json(staged_path, staged_record)
    ledger["steps"][step_id] = {
        "state": "staged",
        "action_sha256": manifest_step["action_sha256"],
        "staged_sha256": sha256_file(staged_path),
    }
    ledger["executor_binding"] = {
        "executor_root": str(resolved_executor),
        "task_id": task_id,
        "thread_id": thread_id,
    }
    atomic_write_json(root / "ledger.json", ledger)
    return {"success": True, **staged_record}


def _issue(condition: bool, message: str, issues: list[str]) -> None:
    if not condition:
        issues.append(message)


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _close(value: Any, expected: Any, tolerance: float) -> bool:
    actual_number = _number(value)
    expected_number = _number(expected)
    return bool(
        actual_number is not None
        and expected_number is not None
        and abs(actual_number - expected_number) <= tolerance + 1e-15
    )


def _bbox_close(actual: Any, expected: Any, tolerance: float) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    for key in ("minimum_cm", "maximum_cm"):
        one = actual.get(key)
        two = expected.get(key)
        if not isinstance(one, list) or not isinstance(two, list) or len(one) != len(two):
            return False
        if not all(_close(a, b, tolerance) for a, b in zip(one, two)):
            return False
    return True


def _healthy_feature(feature: Any) -> bool:
    if not isinstance(feature, dict):
        return False
    timeline = feature.get("timeline") or {}
    return bool(
        feature.get("health_state") == 0
        and feature.get("error_or_warning") == ""
        and feature.get("is_suppressed") is False
        and timeline.get("is_suppressed") is False
        and timeline.get("name") == feature.get("name")
    )


def _nonnegative_at_most(value: Any, maximum: float) -> bool:
    number = _number(value)
    return bool(number is not None and 0.0 <= number <= maximum + 1e-15)


def _deep_close(actual: Any, expected: Any, tolerance: float) -> bool:
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        return actual == expected
    if isinstance(expected, (int, float)):
        return _close(actual, expected, tolerance)
    if isinstance(expected, list):
        return bool(
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                _deep_close(one, two, tolerance)
                for one, two in zip(actual, expected)
            )
        )
    if isinstance(expected, dict):
        return bool(
            isinstance(actual, dict)
            and set(actual) == set(expected)
            and all(
                _deep_close(actual[key], expected[key], tolerance)
                for key in expected
            )
        )
    return actual == expected


def _canonical_unhealthy_features(records: Any) -> list[dict[str, Any]]:
    result = []
    for item in records or []:
        if not isinstance(item, dict) or item.get("health_state") == 0:
            continue
        timeline = item.get("timeline") or {}
        error_text = str(item.get("error_or_warning") or "")
        result.append(
            {
                "index": item.get("index"),
                "name": item.get("name"),
                "object_type": item.get("object_type"),
                "health_state": item.get("health_state"),
                "error_or_warning_sha256": hashlib.sha256(
                    error_text.encode("utf-8")
                ).hexdigest().upper(),
                "is_suppressed": item.get("is_suppressed"),
                "timeline_index": timeline.get("index"),
                "timeline_is_suppressed": timeline.get("is_suppressed"),
                "timeline_name": timeline.get("name"),
            }
        )
    return sorted(
        result,
        key=lambda item: (
            -1 if item["index"] is None else int(item["index"]),
            str(item["name"]),
            str(item["object_type"]),
        ),
    )


def _expected_unhealthy_features(profile: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        profile.get("known_root_unhealthy_features") or [],
        key=lambda item: (
            -1 if item.get("index") is None else int(item["index"]),
            str(item.get("name")),
            str(item.get("object_type")),
        ),
    )


def _body_matches(
    actual: Any,
    expected: dict[str, Any],
    volume_tolerance: float = 0.000001,
    area_tolerance: float = 0.00001,
    bbox_tolerance: float = 0.000001,
) -> bool:
    if not isinstance(actual, dict):
        return False
    for key in ("name", "is_solid", "is_visible", "face_count", "edge_count"):
        if key in expected and actual.get(key) != expected.get(key):
            return False
    if "volume_cm3" in expected and not _close(
        actual.get("volume_cm3"), expected.get("volume_cm3"), volume_tolerance
    ):
        return False
    if "area_cm2" in expected and not _close(
        actual.get("area_cm2"), expected.get("area_cm2"), area_tolerance
    ):
        return False
    if "bounding_box" in expected and not _bbox_close(
        actual.get("bounding_box"), expected.get("bounding_box"), bbox_tolerance
    ):
        return False
    return True


def _snapshot_bodies(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for component in ((snapshot.get("design") or {}).get("components") or []):
        for body in component.get("bodies") or []:
            if isinstance(body, dict):
                result.append({"component_name": component.get("name"), **body})
    return result


def _snapshot_feature_names(snapshot: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    design = snapshot.get("design") or {}
    for component in design.get("components") or []:
        for feature in component.get("features") or []:
            name = feature.get("name")
            if isinstance(name, str):
                names.add(name)
    for item in design.get("timeline") or []:
        name = item.get("name")
        if isinstance(name, str):
            names.add(name)
    return names


def _axis_group_count(records: Iterable[dict[str, Any]]) -> int:
    groups: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for record in records:
        cylinder = record.get("inner_cylinder") or {}
        origin_values = cylinder.get("axis_origin_mm") or []
        direction_values = cylinder.get("axis_direction") or []
        if len(origin_values) != 3 or len(direction_values) != 3:
            raise ValueError("Cylinder axis must have three coordinates")
        origin = tuple(float(item) for item in origin_values)
        direction = tuple(float(item) for item in direction_values)
        magnitude = math.sqrt(sum(item * item for item in direction))
        if magnitude == 0 or not all(math.isfinite(item) for item in origin + direction):
            raise ValueError("Cylinder axis must be finite and non-zero")
        direction = tuple(item / magnitude for item in direction)
        matched = False
        for other_origin, other_direction in groups:
            dot = max(-1.0, min(1.0, abs(sum(a * b for a, b in zip(direction, other_direction)))))
            angle = math.degrees(math.acos(dot))
            delta = tuple(a - b for a, b in zip(origin, other_origin))
            cross = (
                delta[1] * other_direction[2] - delta[2] * other_direction[1],
                delta[2] * other_direction[0] - delta[0] * other_direction[2],
                delta[0] * other_direction[1] - delta[1] * other_direction[0],
            )
            distance = math.sqrt(sum(item * item for item in cross))
            if angle <= 0.001 + 1e-12 and distance <= 0.001 + 1e-12:
                matched = True
                break
        if not matched:
            groups.append((origin, direction))
    return len(groups)


def _validate_import(data: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    _issue(data.get("action") == "import_trial", "Unexpected action", issues)
    _issue(data.get("success") is True, "Trial import did not succeed", issues)
    _issue(data.get("is_saved") is False, "Imported document is not unsaved", issues)
    return {"issues": issues, "warnings": [], "observations": {}}


def _validate_snapshot(
    data: dict[str, Any], recipe: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    issues: list[str] = []
    observations: dict[str, Any] = {}
    fingerprint = recipe["source_fingerprint"]
    _issue(data.get("is_saved") is False, "Snapshot document is not unsaved", issues)
    bodies = _snapshot_bodies(data)
    visible_solids = [
        body for body in bodies if body.get("is_solid") is True and body.get("is_visible") is True
    ]
    _issue(len(visible_solids) == 1, "Expected exactly one visible solid body", issues)
    expected_body = fingerprint["main_body"]
    matches = [
        body
        for body in bodies
        if body.get("name") == expected_body["name"]
        and body.get("is_solid") is True
        and body.get("is_visible") is True
    ]
    _issue(len(matches) == 1, "Main body fingerprint did not resolve uniquely", issues)
    if len(matches) == 1:
        body = matches[0]
        tolerance = fingerprint["tolerance"]
        _issue(
            _close(body.get("volume_cm3"), expected_body["volume_cm3"], tolerance["volume_cm3"]),
            "Main body volume fingerprint mismatch",
            issues,
        )
        _issue(
            _close(body.get("area_cm2"), expected_body["area_cm2"], tolerance["area_cm2"]),
            "Main body area fingerprint mismatch",
            issues,
        )
        _issue(body.get("face_count") == expected_body["face_count"], "Main body face count mismatch", issues)
        _issue(body.get("edge_count") == expected_body["edge_count"], "Main body edge count mismatch", issues)
        _issue(
            _bbox_close(body.get("bounding_box"), expected_body["bounding_box"], tolerance["bounding_box_cm"]),
            "Main body bounding box mismatch",
            issues,
        )
        observations["main_body"] = {
            key: body.get(key)
            for key in ("name", "volume_cm3", "area_cm2", "face_count", "edge_count")
        }

    design = data.get("design") or {}
    root_name = design.get("root_component_name")
    root_components = [
        component
        for component in design.get("components") or []
        if component.get("name") == root_name
    ]
    _issue(len(root_components) == 1, "Snapshot root component did not resolve uniquely", issues)
    if len(root_components) == 1:
        root_component = root_components[0]
        root_solids = [
            body
            for body in root_component.get("bodies") or []
            if body.get("is_solid") is True
        ]
        expected_other = fingerprint.get("other_root_solids") or []
        _issue(
            len(root_solids) == 1 + len(expected_other),
            "Snapshot root solid count mismatch",
            issues,
        )
        for expected_hidden in expected_other:
            hidden_matches = [
                body
                for body in root_solids
                if body.get("name") == expected_hidden["name"]
            ]
            _issue(
                len(hidden_matches) == 1
                and _body_matches(hidden_matches[0], expected_hidden),
                f"Snapshot non-target root solid changed: {expected_hidden['name']}",
                issues,
            )
        actual_unhealthy = _canonical_unhealthy_features(
            root_component.get("features") or []
        )
        expected_unhealthy = _expected_unhealthy_features(profile)
        _issue(
            actual_unhealthy == expected_unhealthy,
            "Snapshot root unhealthy-feature baseline mismatch",
            issues,
        )
        observations["root_unhealthy_feature_count"] = len(actual_unhealthy)

    feature_names = _snapshot_feature_names(data)
    for name in fingerprint.get("required_feature_names") or []:
        _issue(name in feature_names, f"Required feature is missing: {name}", issues)
    for prefix in fingerprint.get("forbidden_feature_prefixes") or []:
        conflicting = sorted(name for name in feature_names if name.startswith(prefix))
        _issue(not conflicting, f"Recipe appears already/partially applied: {conflicting}", issues)
    observations["feature_name_count"] = len(feature_names)
    return {"issues": issues, "warnings": [], "observations": observations}



def _expected_selection_tokens(profile_path: Path, recipe: dict[str, Any]) -> set[str]:
    return set(_selection_tokens(profile_path, recipe))


def _validate_annular_selection(
    data: dict[str, Any], profile_path: Path, recipe: dict[str, Any]
) -> dict[str, Any]:
    gates = recipe["gates"]
    issues: list[str] = []
    _issue(data.get("action") == "capture_annular_selection", "Unexpected action", issues)
    _issue(data.get("success") is True, "Annular selection capture failed", issues)
    records = data.get("records") or []
    _issue(data.get("selected_face_count") == gates["expected_selected_face_count"], "Annular selected-face count mismatch", issues)
    _issue(len(records) == gates["expected_selected_face_count"], "Annular record count mismatch", issues)
    tokens = [record.get("face_token") for record in records]
    _issue(len(tokens) == len(set(tokens)), "Annular face tokens are not unique", issues)
    _issue(set(tokens) == _expected_selection_tokens(profile_path, recipe), "Annular face-token set differs from the pinned manifest", issues)
    expected_capture = load_json(
        profile_path.parent / str(recipe["selection_asset"])
    )
    expected_records = {
        record.get("face_token"): record
        for record in expected_capture.get("records") or []
        if isinstance(record, dict)
    }
    actual_records = {
        record.get("face_token"): record
        for record in records
        if isinstance(record, dict)
    }
    signature_tolerance = float(gates["selection_signature_tolerance"])
    for token, expected_record in expected_records.items():
        _issue(
            token in actual_records
            and _deep_close(actual_records[token], expected_record, signature_tolerance),
            f"Annular geometric signature differs for face token: {token}",
            issues,
        )
    top_tokens = {record.get("top_face_token") for record in records}
    _issue(len(top_tokens) == 1 and None not in top_tokens, "Expected one common annular top face", issues)
    try:
        group_count = _axis_group_count(records)
    except (TypeError, ValueError) as error:
        issues.append(f"Invalid annular cylinder axes: {error}")
        group_count = None
    _issue(group_count == gates["expected_hole_group_count"], "Annular hole-axis group count mismatch", issues)
    return {
        "issues": issues,
        "warnings": [],
        "observations": {"hole_group_count": group_count},
    }


def _validate_annular_apply(
    data: dict[str, Any], recipe: dict[str, Any]
) -> dict[str, Any]:
    gates = recipe["gates"]
    issues: list[str] = []
    _issue(data.get("action") == "annular_thickness_trial", "Unexpected action", issues)
    _issue(data.get("success") is True, "Annular thickness operation failed", issues)
    _issue((data.get("document") or {}).get("is_saved") is False, "Annular operation did not run in an unsaved document", issues)
    parameter = data.get("parameter") or {}
    _issue(parameter.get("name") == "annularWallThickness", "Annular parameter name mismatch", issues)
    _issue(_close(parameter.get("value_internal_cm"), gates["thickness_mm"] / 10.0, 1e-12), "Annular parameter value mismatch", issues)
    _issue(data.get("selected_face_count") == gates["expected_selected_face_count"], "Annular selected-face count mismatch", issues)
    _issue(data.get("resolved_face_count") == gates["expected_selected_face_count"], "Annular resolved-face count mismatch", issues)
    _issue(data.get("hole_group_count") == gates["expected_hole_group_count"], "Annular hole-group count mismatch", issues)
    _issue(data.get("replace_face_count") == gates["expected_replace_face_count"], "Annular Replace Face count mismatch", issues)
    _issue(data.get("boundary_fill_count") == gates["expected_boundary_fill_count"], "Annular fallback was used", issues)
    _issue(
        _close(
            data.get("inward_offset_sign"),
            gates["expected_inward_offset_sign"],
            1e-12,
        ),
        "Annular inward offset direction changed",
        issues,
    )
    _issue(
        data.get("offset_expression") == gates["expected_offset_expression"],
        "Annular offset expression changed",
        issues,
    )
    direction_samples = (data.get("direction_probe") or {}).get("samples") or []
    inside = [
        item
        for item in direction_samples
        if item.get("containment") == "inside"
    ]
    outside = [
        item
        for item in direction_samples
        if item.get("containment") == "outside"
    ]
    _issue(
        len(inside) == 1
        and len(outside) == 1
        and _close(
            inside[0].get("sign"), gates["expected_inward_offset_sign"], 1e-12
        )
        and _close(
            outside[0].get("sign"), -gates["expected_inward_offset_sign"], 1e-12
        ),
        "Annular direction probe does not prove one inside and one outside side",
        issues,
    )
    _issue(data.get("offset_feature_body_count") == gates["expected_offset_feature_body_count"], "Annular offset body count mismatch", issues)
    _issue(data.get("offset_surface_body_count") == gates["expected_offset_surface_body_count"], "Annular offset surface count mismatch", issues)
    _issue(len(data.get("target_boundary_records") or []) == gates["expected_hole_group_count"], "Annular target-boundary count mismatch", issues)
    _issue(data.get("group_methods") == [], "Annular fallback group method was used", issues)
    features = data.get("features") or []
    expected_feature_count = 2 + gates["expected_replace_face_count"]
    _issue(len(features) == expected_feature_count, "Annular feature count mismatch", issues)
    _issue(all(_healthy_feature(item) for item in features), "An annular feature is unhealthy", issues)
    names = {item.get("name") for item in features}
    _issue("AnnularThickness_OffsetTop_0p5mm" in names, "Annular Offset feature is missing", issues)
    _issue("AnnularThickness_ExtendTop_0p5mm" in names, "Annular Extend feature is missing", issues)
    for index in range(gates["expected_replace_face_count"]):
        _issue(f"AnnularThickness_ReplaceFace_{index:02d}" in names, f"Annular Replace Face {index:02d} is missing", issues)
    expected_types = {
        "AnnularThickness_OffsetTop_0p5mm": "adsk::fusion::OffsetFeature",
        "AnnularThickness_ExtendTop_0p5mm": "adsk::fusion::ExtendFeature",
        **{
            f"AnnularThickness_ReplaceFace_{index:02d}": "adsk::fusion::ReplaceFaceFeature"
            for index in range(gates["expected_replace_face_count"])
        },
    }
    _issue(
        all(expected_types.get(item.get("name")) == item.get("object_type") for item in features),
        "Annular feature type mismatch",
        issues,
    )
    body = data.get("body_after") or {}
    expected_body = gates["expected_apply_body"]
    _issue(body.get("name") == expected_body["name"], "Annular output body name mismatch", issues)
    _issue(body.get("is_solid") is expected_body["is_solid"], "Annular output is not a solid", issues)
    for key in ("face_count", "edge_count"):
        _issue(body.get(key) == expected_body[key], f"Annular output {key} mismatch", issues)
    _issue(_close(body.get("volume_cm3"), expected_body["volume_cm3"], 0.000001), "Annular output volume mismatch", issues)
    _issue(_close(body.get("area_cm2"), expected_body["area_cm2"], 0.00001), "Annular output area mismatch", issues)
    _issue(_bbox_close(body.get("bounding_box"), expected_body["bounding_box"], 0.000001), "Annular output bounding box mismatch", issues)
    return {
        "issues": issues,
        "warnings": [],
        "observations": {"feature_count": len(features)},
    }


def _validate_annular_validation(
    data: dict[str, Any], recipe: dict[str, Any], profile: dict[str, Any]
) -> dict[str, Any]:
    gates = recipe["gates"]
    issues: list[str] = []
    warnings: list[str] = []
    _issue(data.get("action") == "validate_annular_thickness", "Unexpected action", issues)
    _issue(data.get("success") is True, "Annular validation failed", issues)
    _issue(data.get("all_validation_gates_passed") is True, "Annular aggregate gate failed", issues)
    _issue(data.get("solid_valid") is True, "Annular output is not a valid solid", issues)
    _issue(data.get("new_features_healthy") is True, "Annular feature health gate failed", issues)
    _issue(
        _canonical_unhealthy_features(
            data.get("preexisting_unhealthy_features") or []
        )
        == _expected_unhealthy_features(profile),
        "Annular preexisting unhealthy-feature baseline changed",
        issues,
    )
    _issue(data.get("valid_sample_coverage") is True, "Annular sample coverage gate failed", issues)
    _issue(data.get("resolved_face_count") == gates["expected_selected_face_count"], "Annular resolved-face count mismatch", issues)
    thickness = data.get("thickness") or {}
    _issue(_close(thickness.get("nominal_mm"), gates["thickness_mm"], 1e-12), "Annular nominal thickness mismatch", issues)
    maximum_error = _number(thickness.get("maximum_absolute_error_mm"))
    _issue(maximum_error is not None and 0.0 <= maximum_error <= gates["maximum_thickness_error_mm"], "Annular thickness error exceeds the gate", issues)
    sample_count = int(thickness.get("sample_count") or 0)
    samples = data.get("thickness_samples_mm") or []
    _issue(sample_count == gates["expected_valid_sample_count"], "Annular valid sample count differs from the pinned replay", issues)
    _issue(len(samples) == sample_count, "Annular thickness sample list is incomplete", issues)
    _issue(_close(data.get("maximum_absolute_error_mm"), maximum_error, 1e-12), "Annular aggregate maximum thickness error mismatch", issues)
    deltas = data.get("cylinder_deltas") or []
    _issue(len(deltas) == gates["expected_cylinder_delta_count"], "Annular cylinder-delta evidence is incomplete", issues)
    delta_pairs = {(item.get("group_index"), item.get("kind")) for item in deltas}
    _issue(
        delta_pairs
        == {
            (group_index, kind)
            for group_index in range(gates["expected_hole_group_count"])
            for kind in ("hole", "counterbore")
        },
        "Annular cylinder-delta group/kind set mismatch",
        issues,
    )
    for index, delta in enumerate(deltas):
        _issue(_nonnegative_at_most(delta.get("diameter_delta_mm"), gates["maximum_diameter_delta_mm"]), f"Cylinder {index} diameter changed", issues)
        _issue(_nonnegative_at_most(delta.get("axis_position_delta_mm"), gates["maximum_axis_position_delta_mm"]), f"Cylinder {index} axis position changed", issues)
        _issue(_nonnegative_at_most(delta.get("axis_angle_degrees"), gates["maximum_axis_angle_degrees"]), f"Cylinder {index} axis angle changed", issues)
    groups = data.get("groups") or []
    _issue(len(groups) == gates["expected_hole_group_count"], "Annular validation group evidence is incomplete", issues)
    _issue({group.get("group_index") for group in groups} == set(range(gates["expected_hole_group_count"])), "Annular validation group indices mismatch", issues)
    _issue(sum(int(group.get("face_count") or 0) for group in groups) == gates["expected_selected_face_count"], "Annular validation group face coverage mismatch", issues)
    _issue(sum(int((group.get("thickness") or {}).get("sample_count") or 0) for group in groups) == sample_count, "Annular group sample counts do not cover the aggregate", issues)
    _issue(all((group.get("thickness") or {}).get("success") is True for group in groups), "An annular group thickness gate failed", issues)
    new_features = data.get("new_features") or []
    expected_feature_names = {
        "AnnularThickness_OffsetTop_0p5mm",
        "AnnularThickness_ExtendTop_0p5mm",
        *{
            f"AnnularThickness_ReplaceFace_{index:02d}"
            for index in range(gates["expected_replace_face_count"])
        },
    }
    _issue(len(new_features) == len(expected_feature_names), "Annular new-feature evidence is incomplete", issues)
    _issue({item.get("name") for item in new_features} == expected_feature_names, "Annular new-feature set mismatch", issues)
    _issue(all(_healthy_feature(item) for item in new_features), "Annular new-feature evidence contains an unhealthy feature", issues)
    validation_expected_types = {
        "AnnularThickness_OffsetTop_0p5mm": "adsk::fusion::OffsetFeature",
        "AnnularThickness_ExtendTop_0p5mm": "adsk::fusion::ExtendFeature",
        **{
            f"AnnularThickness_ReplaceFace_{index:02d}": "adsk::fusion::ReplaceFaceFeature"
            for index in range(gates["expected_replace_face_count"])
        },
    }
    _issue(
        all(validation_expected_types.get(item.get("name")) == item.get("object_type") for item in new_features),
        "Annular validation feature type mismatch",
        issues,
    )
    _issue(len(data.get("feature_face_records") or []) == gates["expected_feature_face_record_count"], "Annular feature-face evidence is incomplete", issues)
    gate = data.get("gate") or {}
    for key in (
        "thickness_ok",
        "diameter_ok",
        "axis_position_ok",
        "axis_angle_ok",
        "topology_ok",
        "new_features_healthy",
        "success",
        "valid_sample_coverage",
    ):
        _issue(gate.get(key) is True, f"Annular nested gate failed: {key}", issues)
    outside = data.get("outside_region_unchanged")
    if outside is False:
        issues.append("Annular outside-region comparison failed")
    elif outside is not True:
        warnings.append("Annular outside-region geometry was not independently compared")
    warnings.append("Dedicated annular F3D/STEP reopen is not part of this historical executor contract")
    return {
        "issues": issues,
        "warnings": warnings,
        "observations": {
            "maximum_thickness_error_mm": maximum_error,
            "valid_sample_count": thickness.get("sample_count"),
        },
    }


def validate_result(
    profile_path: Path,
    profile: dict[str, Any],
    step_id: str,
    result_path: Path,
) -> dict[str, Any]:
    recipe = get_recipe(profile)
    _index, step = get_step(recipe, step_id)
    data = load_json(result_path)
    kind = step["result_kind"]
    if kind == "import_trial":
        check = _validate_import(data)
    elif kind == "snapshot":
        check = _validate_snapshot(data, recipe, profile)
    elif kind == "annular_selection":
        check = _validate_annular_selection(data, profile_path, recipe)
    elif kind == "annular_apply":
        check = _validate_annular_apply(data, recipe)
    elif kind == "annular_validation":
        check = _validate_annular_validation(data, recipe, profile)
    else:
        raise CliFailure(f"Unsupported result_kind: {kind}")
    return {
        "success": not check["issues"],
        "profile_id": profile["profile_id"],
        "recipe": RECIPE_NAME,
        "recipe_id": recipe["recipe_id"],
        "step": step_id,
        "result_path": str(result_path.resolve()),
        "result_sha256": sha256_file(result_path),
        "issues": check["issues"],
        "warnings": check["warnings"],
        "observations": check["observations"],
        "release_blockers": recipe.get("release_blockers") or [],
    }


def _assert_fresh_staged_result(
    root: Path,
    manifest: dict[str, Any],
    manifest_step: dict[str, Any],
    ledger: dict[str, Any],
    profile: dict[str, Any],
    source: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    step_id = manifest_step["id"]
    staged_path = root / "staged" / f"{step_id}.json"
    staged = load_json(staged_path)
    if sha256_file(staged_path) != (ledger.get("steps") or {}).get(step_id, {}).get(
        "staged_sha256"
    ):
        raise CliFailure(f"Staged evidence changed after mailbox write: {step_id}")
    if staged.get("action_sha256") != manifest_step["action_sha256"]:
        raise CliFailure(f"Staged action evidence does not match the manifest: {step_id}")
    mailbox = Path(str(staged.get("mailbox") or ""))
    if not mailbox.is_file() or sha256_file(mailbox) != manifest_step["action_sha256"]:
        raise CliFailure(f"Executor mailbox changed after staging: {step_id}")
    expected_result = Path(str(staged.get("expected_result") or ""))
    if not _same_resolved_path(source, expected_result):
        raise CliFailure(
            "Result must be collected from the exact executor result path staged for this step"
        )
    binding = ledger.get("executor_binding") or {}
    executor_root = Path(str(staged.get("executor_root") or ""))
    _assert_bound_executor(
        ledger,
        executor_root,
        str(binding.get("task_id") or ""),
        str(binding.get("thread_id") or ""),
    )
    task_lock = staged.get("task_lock") or {}
    verify_task_lock(
        profile,
        executor_root,
        str(task_lock.get("task_id") or ""),
        str(task_lock.get("thread_id") or ""),
    )
    current = file_state(source)
    previous = staged.get("result_pre_stage") or {"exists": False}
    if previous.get("exists"):
        unchanged = all(
            current.get(key) == previous.get(key)
            for key in ("size_bytes", "mtime_ns", "sha256")
        )
        if unchanged:
            raise CliFailure(f"Executor result is stale and predates staging: {step_id}")
    data = load_json(source)
    generated_at = _parse_utc(data.get("generated_at"), "Result generated_at")
    staged_at = _parse_utc(staged.get("staged_at_utc"), "Stage timestamp")
    if generated_at <= staged_at:
        raise CliFailure(f"Executor result generated_at predates staging: {step_id}")
    staged_epoch_ns = int(staged.get("staged_at_epoch_ns") or 0)
    if int(current.get("mtime_ns") or 0) <= staged_epoch_ns:
        raise CliFailure(f"Executor result file mtime predates staging: {step_id}")
    return staged, data



def _verify_annular_body_chain(
    root: Path,
    ledger: dict[str, Any],
    data: dict[str, Any],
) -> list[str]:
    apply_record = (ledger.get("steps") or {}).get("apply-annular-thickness") or {}
    apply_result = root / str(apply_record.get("result_file") or "")
    if not apply_result.is_file():
        return ["Annular apply result is missing from the run"]
    before = (load_json(apply_result).get("body_after") or {})
    after = data.get("body") or {}
    issues: list[str] = []
    for key in ("name", "is_solid", "face_count", "edge_count"):
        if after.get(key) != before.get(key):
            issues.append(f"Annular validation body changed after apply: {key}")
    for key, tolerance in (("volume_cm3", 0.000001), ("area_cm2", 0.00001)):
        if not _close(after.get(key), before.get(key), tolerance):
            issues.append(f"Annular validation body changed after apply: {key}")
    if not _bbox_close(after.get("bounding_box"), before.get("bounding_box"), 0.000001):
        issues.append("Annular validation body bounding box changed after apply")
    return issues


def record_result(
    run_dir: Path,
    step_id: str,
    result_path: Path,
    replace_result: bool,
) -> tuple[dict[str, Any], int]:
    root, manifest, ledger, profile_path, profile, recipe = load_run(run_dir)
    step_index, _recipe_step = get_step(recipe, step_id)
    manifest_step = manifest["steps"][step_index]
    state = ledger["steps"][step_id].get("state")
    if state not in {"staged", "passed", "failed"}:
        raise CliFailure(f"Step must be staged before recording a result: {step_id}")
    source = result_path.resolve()
    if not source.is_file():
        raise CliFailure(f"Result file does not exist: {source}")
    stored = root / "results" / f"{manifest_step['ordinal']:02d}-{step_id}.json"
    check_path = root / "checks" / f"{manifest_step['ordinal']:02d}-{step_id}.json"
    if state in {"passed", "failed"}:
        if (
            stored.is_file()
            and check_path.is_file()
            and sha256_file(stored) == sha256_file(source)
        ):
            existing_check = load_json(check_path)
            return existing_check, EXIT_OK if existing_check.get("success") else EXIT_VALIDATION
        raise CliFailure(
            f"Recorded {state} evidence is immutable; start a fresh run: {step_id}"
        )

    binding = ledger.get("executor_binding") or {}
    bound_executor = Path(str(binding.get("executor_root") or ""))
    executor_check = doctor_check(profile, bound_executor)
    if not executor_check["success"]:
        raise CliFailure(
            "Executor doctor failed at result collection: "
            + "; ".join(executor_check["issues"])
        )
    _assert_prior_result_chain(
        root,
        manifest,
        ledger,
        profile,
        recipe,
        step_index,
        bound_executor,
    )

    staged, staged_data = _assert_fresh_staged_result(
        root, manifest, manifest_step, ledger, profile, source
    )
    if stored.exists():
        if sha256_file(stored) != sha256_file(source) and not replace_result:
            raise CliFailure(
                f"A different result is already recorded for {step_id}; "
                "use --replace-result only to recover an interrupted staged record"
            )
        if sha256_file(stored) != sha256_file(source):
            previous_hash = sha256_file(stored)
            suffix = f"{manifest_step['ordinal']:02d}-{step_id}-{previous_hash[:16]}.json"
            previous_result = root / "replaced-results" / suffix
            if not previous_result.exists():
                atomic_copy(stored, previous_result)
            if check_path.is_file():
                previous_check = root / "replaced-checks" / suffix
                if not previous_check.exists():
                    atomic_copy(check_path, previous_check)
    atomic_copy(source, stored)
    check = validate_result(profile_path, profile, step_id, stored)
    check["run_manifest_sha256"] = ledger["run_manifest_sha256"]
    kind = manifest_step["result_kind"]
    if kind == "import_trial":
        expected_input = root / str(manifest["input_archive"]["collected_file"])
        actual_input = Path(str(staged_data.get("archive_path") or ""))
        if not _same_resolved_path(expected_input, actual_input):
            check["issues"].append(
                "Import result archive_path differs from the collected run input"
            )
    elif kind == "annular_validation" and check["success"]:
        check["issues"].extend(_verify_annular_body_chain(root, ledger, staged_data))
    check["success"] = not check["issues"]
    atomic_write_json(check_path, check)
    ledger["steps"][step_id] = {
        "state": "passed" if check["success"] else "failed",
        "result_sha256": check["result_sha256"],
        "result_file": str(stored.relative_to(root)),
        "check_file": str(check_path.relative_to(root)),
        "check_sha256": sha256_file(check_path),
    }
    atomic_write_json(root / "ledger.json", ledger)
    return check, EXIT_OK if check["success"] else EXIT_VALIDATION


def audit_history(
    profile_path: Path,
    profile: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    recipe = get_recipe(profile)
    reports = []
    overall = True
    for step_id, evidence in (recipe.get("historical_evidence") or {}).items():
        path = Path(str(evidence["path"])).resolve()
        expected_hash = str(evidence["sha256"]).upper()
        if not path.is_file():
            report = {
                "success": False,
                "recipe": RECIPE_NAME,
                "step": step_id,
                "issues": [f"Historical evidence is missing: {path}"],
                "warnings": [],
            }
        elif sha256_file(path) != expected_hash:
            report = {
                "success": False,
                "recipe": RECIPE_NAME,
                "step": step_id,
                "issues": ["Historical evidence hash mismatch"],
                "warnings": [],
                "actual_sha256": sha256_file(path),
                "expected_sha256": expected_hash,
            }
        else:
            report = validate_result(profile_path, profile, step_id, path)
            report["historical_sha256_match"] = True
        overall = overall and bool(report["success"])
        reports.append(report)
    result = {
        "success": overall,
        "profile_id": profile["profile_id"],
        "reports": reports,
    }
    return result, EXIT_OK if overall else EXIT_VALIDATION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Verify a compatible executor copy")
    doctor.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    doctor.add_argument("--executor-root", type=Path, required=True)

    init_run = subparsers.add_parser("init-run", help="Create an immutable action plan")
    init_run.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    init_run.add_argument("--archive", type=Path, required=True)
    init_run.add_argument("--run-dir", type=Path, required=True)

    next_parser = subparsers.add_parser("next", help="Show the next safe state transition")
    next_parser.add_argument("--run-dir", type=Path, required=True)

    status_parser = subparsers.add_parser("status", help="Show run state and release blockers")
    status_parser.add_argument("--run-dir", type=Path, required=True)

    stage = subparsers.add_parser("stage", help="Atomically stage one action JSON")
    stage.add_argument("--run-dir", type=Path, required=True)
    stage.add_argument("--executor-root", type=Path, required=True)
    stage.add_argument("--task-id", required=True)
    stage.add_argument("--thread-id", required=True)
    stage.add_argument("--step")
    stage.add_argument("--replace-mailbox", action="store_true")
    stage.add_argument("--restage", action="store_true")
    stage.add_argument("--ack-fresh-unsaved-trial", action="store_true")

    record = subparsers.add_parser("record", help="Record and validate a staged result")
    record.add_argument("--run-dir", type=Path, required=True)
    record.add_argument("--step", required=True)
    record.add_argument("--result", type=Path, required=True)
    record.add_argument("--replace-result", action="store_true")

    check = subparsers.add_parser("check-result", help="Validate one result without a run")
    check.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    check.add_argument("--step", required=True)
    check.add_argument("--result", type=Path, required=True)

    audit = subparsers.add_parser("audit-history", help="Recheck preserved successful evidence")
    audit.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            _profile_path, profile = load_profile(args.profile)
            result = doctor_check(profile, args.executor_root)
            print_json(result)
            return EXIT_OK if result["success"] else EXIT_PRECONDITION
        if args.command == "init-run":
            profile_path, profile = load_profile(args.profile)
            print_json(create_run(profile_path, profile, args.archive, args.run_dir))
            return EXIT_OK
        if args.command in {"next", "status"}:
            _root, manifest, ledger, _profile_path, _profile, _recipe = load_run(args.run_dir)
            result = _next_state(manifest, ledger) if args.command == "next" else _run_status(manifest, ledger)
            print_json(result)
            return EXIT_OK if result["success"] else EXIT_VALIDATION
        if args.command == "stage":
            print_json(
                stage_action(
                    args.run_dir,
                    args.executor_root,
                    args.task_id,
                    args.thread_id,
                    args.step,
                    args.replace_mailbox,
                    args.restage,
                    args.ack_fresh_unsaved_trial,
                )
            )
            return EXIT_OK
        if args.command == "record":
            result, exit_code = record_result(
                args.run_dir, args.step, args.result, args.replace_result
            )
            print_json(result)
            return exit_code
        if args.command == "check-result":
            profile_path, profile = load_profile(args.profile)
            result = validate_result(
                profile_path, profile, args.step, args.result.resolve()
            )
            print_json(result)
            return EXIT_OK if result["success"] else EXIT_VALIDATION
        if args.command == "audit-history":
            profile_path, profile = load_profile(args.profile)
            result, exit_code = audit_history(profile_path, profile)
            print_json(result)
            return exit_code
    except CliFailure as error:
        print_json({"success": False, "error": str(error), "exit_code": error.exit_code})
        return error.exit_code
    parser.error("Unsupported command")
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
