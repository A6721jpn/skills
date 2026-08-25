from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_ROOT / "scripts" / "fusion_annular_0p5.py"
SPEC = importlib.util.spec_from_file_location("fusion_annular_0p5_under_test", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

PROFILE_PATH, PROFILE = MODULE.load_profile(
    SKILL_ROOT / "assets" / "upper-frame-v1-annular-0p5-profile.json"
)
RECIPE = PROFILE["recipes"]["annular-0p5"]
HISTORICAL_ROOT = Path(
    "C:/dev/MeltMouse_ME_Dev/01_Fusion_Mechanical_Design/01_Active/"
    "upper-frame-fusion-development"
)
ACCEPTED_ARCHIVE = (
    HISTORICAL_ROOT
    / "artifacts"
    / "01_Upper_Frame_v1.0_bottom_z_corrected_20260731_231212.f3d"
)
TEST_TASK_ID = "fusion-annular-test"
TEST_THREAD_ID = "00000000-0000-0000-0000-000000000001"


class FusionAnnularTests(unittest.TestCase):
    def setUp(self) -> None:
        test_root = SKILL_ROOT / ".test-work"
        test_root.mkdir(exist_ok=True)
        self.temp = test_root / self._testMethodName
        if self.temp.exists():
            shutil.rmtree(self.temp)
        self.temp.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp)

    def _write_json(self, name: str, value: dict) -> Path:
        path = self.temp / name
        MODULE.atomic_write_json(path, value)
        return path

    def _historical(self, name: str) -> dict:
        return json.loads((HISTORICAL_ROOT / name).read_text(encoding="utf-8"))

    def _new_run(self, name: str = "run") -> Path:
        run = self.temp / name
        MODULE.create_run(PROFILE_PATH, PROFILE, ACCEPTED_ARCHIVE, run)
        return run

    def _copy_executor(self, name: str = "executor", with_lock: bool = True) -> Path:
        root = self.temp / name
        for entry in PROFILE["executor"]["required_files"]:
            source = HISTORICAL_ROOT / entry["path"]
            destination = root / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        if with_lock:
            MODULE.atomic_write_json(
                root / ".codex-task-lock.json",
                {
                    "version": 1,
                    "task_id": TEST_TASK_ID,
                    "thread_id": TEST_THREAD_ID,
                    "state": "active",
                    "protected_paths": [str(root.resolve())],
                },
            )
        return root

    def _fresh_import_result(self, executor: Path, success: bool = True) -> Path:
        action = MODULE.load_json(executor / "fusion_inspector_action.json")
        path = executor / "fusion_inspector_action_result.json"
        MODULE.atomic_write_json(
            path,
            {
                "action": "import_trial",
                "success": success,
                "is_saved": False,
                "archive_path": action["archive_path"],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return path

    def _valid_snapshot(self) -> dict:
        fingerprint = RECIPE["source_fingerprint"]
        root_features = copy.deepcopy(
            self._historical("fusion_annular_thickness_validation.json")[
                "preexisting_unhealthy_features"
            ]
        )
        root_features.extend(
            {"name": name, "health_state": 0}
            for name in fingerprint["required_feature_names"]
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "is_saved": False,
            "design": {
                "root_component_name": "Untitled",
                "components": [
                    {
                        "name": "Untitled",
                        "bodies": [
                            copy.deepcopy(fingerprint["main_body"]),
                            *copy.deepcopy(fingerprint["other_root_solids"]),
                        ],
                        "features": root_features,
                    }
                ],
                "timeline": [],
            },
        }

    def _advance_to_snapshot(self, run: Path, executor: Path) -> None:
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "import-trial", False, False, False,
        )
        check, code = MODULE.record_result(
            run, "import-trial", self._fresh_import_result(executor), False
        )
        self.assertTrue(check["success"], check)
        self.assertEqual(MODULE.EXIT_OK, code)

        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "snapshot-source", True, False, False,
        )
        snapshot_path = executor / "fusion_parametric_inspection.json"
        MODULE.atomic_write_json(snapshot_path, self._valid_snapshot())
        check, code = MODULE.record_result(
            run, "snapshot-source", snapshot_path, False
        )
        self.assertTrue(check["success"], check)
        self.assertEqual(MODULE.EXIT_OK, code)

    def _advance_to_selection(self, run: Path, executor: Path) -> None:
        self._advance_to_snapshot(run, executor)
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "capture-annular-selection", True, False, False,
        )
        result = self._historical("fusion_annular_selection.json")
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        result_path = executor / "fusion_annular_selection.json"
        MODULE.atomic_write_json(result_path, result)
        check, code = MODULE.record_result(
            run, "capture-annular-selection", result_path, False
        )
        self.assertTrue(check["success"], check)
        self.assertEqual(MODULE.EXIT_OK, code)

    def _advance_to_apply(self, run: Path, executor: Path) -> None:
        self._advance_to_selection(run, executor)
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "apply-annular-thickness", True, False, True,
        )
        result = self._historical("fusion_annular_thickness_result.json")
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        result_path = executor / "fusion_annular_thickness_result.json"
        MODULE.atomic_write_json(result_path, result)
        check, code = MODULE.record_result(
            run, "apply-annular-thickness", result_path, False
        )
        self.assertTrue(check["success"], check)
        self.assertEqual(MODULE.EXIT_OK, code)

    def test_profile_is_annular_only_and_keeps_executor_boot_dependency(self):
        self.assertEqual({"annular-0p5"}, set(PROFILE["recipes"]))
        controller_source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "_validate_bottom",
            "_collect_bottom",
            "_verify_bottom",
            '"bottom_z_extrude_correction"',
            '"verify_corrected_exports"',
            '"bottom_result"',
            '"bottom_verify"',
            "Datum target",
        ):
            self.assertNotIn(forbidden, controller_source)
        markers = PROFILE["executor"]["required_source_markers"]
        self.assertFalse(any("bottom_z_extrude_correction" in item for item in markers))
        self.assertFalse(any("verify_corrected_exports" in item for item in markers))
        self.assertEqual(
            {
                "action_result",
                "snapshot",
                "annular_selection",
                "annular_result",
                "annular_validation",
            },
            set(PROFILE["executor"]["result_paths"]),
        )
        required = {item["path"] for item in PROFILE["executor"]["required_files"]}
        self.assertIn("fusion_inspector/bottom_z_policy.py", required)

    def test_load_profile_rejects_more_than_one_recipe(self):
        bad = copy.deepcopy(PROFILE)
        bad["recipes"]["unrelated"] = copy.deepcopy(RECIPE)
        path = self._write_json("bad-profile.json", bad)
        with self.assertRaisesRegex(MODULE.CliFailure, "exactly"):
            MODULE.load_profile(path)

        wrong_id = copy.deepcopy(PROFILE)
        wrong_id["recipes"][MODULE.RECIPE_NAME]["recipe_id"] = "wrong"
        wrong_id_path = self._write_json("wrong-recipe-id-profile.json", wrong_id)
        with self.assertRaisesRegex(MODULE.CliFailure, "recipe_id"):
            MODULE.load_profile(wrong_id_path)

    def test_cli_public_api_has_no_recipe_option(self):
        parser = MODULE.build_parser()
        choices = parser._subparsers._group_actions[0].choices
        for command in ("init-run", "check-result", "audit-history"):
            self.assertNotIn(
                "recipe",
                {action.dest for action in choices[command]._actions},
            )

    def test_doctor_accepts_only_the_pinned_executor(self):
        report = MODULE.doctor_check(PROFILE, HISTORICAL_ROOT)
        self.assertTrue(report["success"], report)
        self.assertEqual(5, len(report["observations"]["files"]))

        executor = self._copy_executor()
        policy = executor / "fusion_inspector" / "bottom_z_policy.py"
        policy.write_text(
            policy.read_text(encoding="utf-8") + "\n# boot dependency drift\n",
            encoding="utf-8",
        )
        report = MODULE.doctor_check(PROFILE, executor)
        self.assertFalse(report["success"])
        self.assertTrue(any("hash drift" in item.lower() for item in report["issues"]))

    def test_historical_annular_evidence_hashes_and_gates_pass(self):
        report, code = MODULE.audit_history(PROFILE_PATH, PROFILE)
        self.assertEqual(MODULE.EXIT_OK, code)
        self.assertTrue(report["success"], report)
        self.assertEqual(3, len(report["reports"]))
        self.assertTrue(
            all(item.get("historical_sha256_match") for item in report["reports"])
        )
        self.assertEqual(
            {
                "capture-annular-selection",
                "apply-annular-thickness",
                "validate-annular-thickness",
            },
            {item["step"] for item in report["reports"]},
        )

    def test_init_run_pins_input_tokens_actions_and_fallbacks(self):
        run = self._new_run()
        manifest = MODULE.load_json(run / "run-manifest.json")
        self.assertEqual("annular-0p5", manifest["recipe"])
        self.assertEqual(
            [
                "import-trial",
                "snapshot-source",
                "capture-annular-selection",
                "apply-annular-thickness",
                "validate-annular-thickness",
            ],
            [item["id"] for item in manifest["steps"]],
        )
        collected = run / manifest["input_archive"]["collected_file"]
        self.assertEqual(MODULE.sha256_file(ACCEPTED_ARCHIVE), MODULE.sha256_file(collected))
        capture = MODULE.load_json(run / manifest["steps"][2]["action_file"])
        apply_action = MODULE.load_json(run / manifest["steps"][3]["action_file"])
        self.assertEqual(15, len(capture["target_face_tokens"]))
        self.assertEqual(15, len(set(capture["target_face_tokens"])))
        self.assertEqual(0.5, apply_action["thickness_mm"])
        self.assertFalse(apply_action["allow_planar_fallback"])
        self.assertFalse(apply_action["allow_fallback"])

    def test_init_rejects_unqualified_f3d(self):
        archive = (
            HISTORICAL_ROOT / "artifacts"
            / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "not accepted"):
            MODULE.create_run(PROFILE_PATH, PROFILE, archive, self.temp / "bad-run")

    def test_init_rejects_selection_asset_hash_drift(self):
        profile_dir = self.temp / "profile"
        profile_dir.mkdir()
        profile_copy = profile_dir / PROFILE_PATH.name
        selection_copy = profile_dir / RECIPE["selection_asset"]
        shutil.copy2(PROFILE_PATH, profile_copy)
        shutil.copy2(PROFILE_PATH.parent / RECIPE["selection_asset"], selection_copy)
        selection_copy.write_text(
            selection_copy.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "Selection asset hash drift"):
            MODULE.create_run(
                profile_copy, PROFILE, ACCEPTED_ARCHIVE, self.temp / "drift-run"
            )

    def test_mutating_stage_requires_fresh_unsaved_ack_and_no_restage(self):
        run = self._new_run()
        executor = self._copy_executor()
        self._advance_to_selection(run, executor)
        with self.assertRaisesRegex(MODULE.CliFailure, "fresh-unsaved-trial"):
            MODULE.stage_action(
                run, executor, TEST_TASK_ID, TEST_THREAD_ID,
                "apply-annular-thickness", True, False, False,
            )
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "apply-annular-thickness", True, False, True,
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "never be restaged"):
            MODULE.stage_action(
                run, executor, TEST_TASK_ID, TEST_THREAD_ID,
                "apply-annular-thickness", True, True, True,
            )

    def test_stage_rejects_missing_task_lock(self):
        run = self._new_run()
        executor = self._copy_executor(with_lock=False)
        with self.assertRaisesRegex(MODULE.CliFailure, "does not exist"):
            MODULE.stage_action(
                run, executor, TEST_TASK_ID, TEST_THREAD_ID,
                "import-trial", False, False, False,
            )

    def test_record_rejects_preexisting_stale_result(self):
        run = self._new_run()
        executor = self._copy_executor()
        path = executor / "fusion_inspector_action_result.json"
        MODULE.atomic_write_json(
            path,
            {
                "action": "import_trial",
                "success": True,
                "is_saved": False,
                "generated_at": "2026-01-01T00:00:00+00:00",
            },
        )
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "import-trial", False, False, False,
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "stale"):
            MODULE.record_result(run, "import-trial", path, False)

    def test_record_rejects_mailbox_tamper_and_wrong_import_path(self):
        run = self._new_run()
        executor = self._copy_executor()
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "import-trial", False, False, False,
        )
        mailbox = executor / "fusion_inspector_action.json"
        wrong_archive = self.temp / "wrong.f3d"
        wrong_archive.write_bytes(b"wrong")
        MODULE.atomic_write_json(
            mailbox, {"action": "import_trial", "archive_path": str(wrong_archive)}
        )
        result = executor / "fusion_inspector_action_result.json"
        MODULE.atomic_write_json(
            result,
            {
                "action": "import_trial",
                "success": True,
                "is_saved": False,
                "archive_path": str(wrong_archive),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "mailbox changed"):
            MODULE.record_result(run, "import-trial", result, False)

        manifest = MODULE.load_json(run / "run-manifest.json")
        MODULE.atomic_copy(run / manifest["steps"][0]["action_file"], mailbox)
        check, code = MODULE.record_result(run, "import-trial", result, False)
        self.assertEqual(MODULE.EXIT_VALIDATION, code)
        self.assertTrue(any("archive_path" in item for item in check["issues"]))

    def test_record_rechecks_executor_hashes_at_collection(self):
        run = self._new_run()
        executor = self._copy_executor()
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "import-trial", False, False, False,
        )
        result = self._fresh_import_result(executor)
        policy = executor / "fusion_inspector" / "annular_thickness_policy.py"
        policy.write_text(
            policy.read_text(encoding="utf-8") + "\n# post-stage drift\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "doctor failed at result"):
            MODULE.record_result(run, "import-trial", result, False)

    def test_record_rechecks_live_prior_result_chain(self):
        run = self._new_run()
        executor = self._copy_executor()
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "import-trial", False, False, False,
        )
        import_path = self._fresh_import_result(executor)
        check, code = MODULE.record_result(run, "import-trial", import_path, False)
        self.assertTrue(check["success"])
        self.assertEqual(MODULE.EXIT_OK, code)
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "snapshot-source", True, False, False,
        )
        data = MODULE.load_json(import_path)
        data["drift"] = True
        MODULE.atomic_write_json(import_path, data)
        snapshot = executor / "fusion_parametric_inspection.json"
        MODULE.atomic_write_json(snapshot, self._valid_snapshot())
        with self.assertRaisesRegex(MODULE.CliFailure, "no longer matches"):
            MODULE.record_result(run, "snapshot-source", snapshot, False)

    def test_run_rejects_collected_input_hash_drift(self):
        run = self._new_run()
        manifest = MODULE.load_json(run / "run-manifest.json")
        collected = run / manifest["input_archive"]["collected_file"]
        collected.write_bytes(b"tampered")
        with self.assertRaisesRegex(MODULE.CliFailure, "input hash/size changed"):
            MODULE.load_run(run)

    def test_status_rejects_forged_all_passed_ledger(self):
        run = self._new_run()
        ledger = MODULE.load_json(run / "ledger.json")
        for step_id in ledger["steps"]:
            ledger["steps"][step_id] = {"state": "passed"}
        ledger["executor_binding"] = {
            "executor_root": str(self.temp / "fake"),
            "task_id": TEST_TASK_ID,
            "thread_id": TEST_THREAD_ID,
        }
        MODULE.atomic_write_json(run / "ledger.json", ledger)
        with self.assertRaisesRegex(MODULE.CliFailure, "Result file|result evidence"):
            MODULE.load_run(run)

    def test_status_rejects_deleted_recorded_evidence(self):
        run = self._new_run()
        executor = self._copy_executor()
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "import-trial", False, False, False,
        )
        result = self._fresh_import_result(executor)
        MODULE.record_result(run, "import-trial", result, False)
        (run / "checks" / "01-import-trial.json").unlink()
        with self.assertRaisesRegex(MODULE.CliFailure, "check evidence"):
            MODULE.load_run(run)

    def test_run_rejects_switching_executor_roots(self):
        run = self._new_run()
        first = self._copy_executor("executor-one")
        second = self._copy_executor("executor-two")
        MODULE.stage_action(
            run, first, TEST_TASK_ID, TEST_THREAD_ID,
            "import-trial", False, False, False,
        )
        MODULE.record_result(run, "import-trial", self._fresh_import_result(first), False)
        with self.assertRaisesRegex(MODULE.CliFailure, "different executor"):
            MODULE.stage_action(
                run, second, TEST_TASK_ID, TEST_THREAD_ID,
                "snapshot-source", False, False, False,
            )

    def test_failed_result_cannot_resurrect_run(self):
        run = self._new_run()
        executor = self._copy_executor()
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "import-trial", False, False, False,
        )
        failed = self._fresh_import_result(executor, success=False)
        check, code = MODULE.record_result(run, "import-trial", failed, False)
        self.assertFalse(check["success"])
        self.assertEqual(MODULE.EXIT_VALIDATION, code)
        passed = self._fresh_import_result(executor, success=True)
        with self.assertRaisesRegex(MODULE.CliFailure, "immutable"):
            MODULE.record_result(run, "import-trial", passed, True)

    def test_replaced_interrupted_result_and_check_are_preserved(self):
        run = self._new_run()
        executor = self._copy_executor()
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "import-trial", False, False, False,
        )
        stored = run / "results" / "01-import-trial.json"
        MODULE.atomic_write_json(
            stored,
            {
                "action": "import_trial",
                "success": False,
                "is_saved": False,
                "generated_at": "2026-01-01T00:00:00+00:00",
            },
        )
        old_check = run / "checks" / "01-import-trial.json"
        MODULE.atomic_write_json(old_check, {"success": False, "old": True})
        old_hash = MODULE.sha256_file(stored)
        result = self._fresh_import_result(executor)
        check, code = MODULE.record_result(run, "import-trial", result, True)
        self.assertTrue(check["success"])
        self.assertEqual(MODULE.EXIT_OK, code)
        suffix = f"01-import-trial-{old_hash[:16]}.json"
        self.assertEqual(
            old_hash, MODULE.sha256_file(run / "replaced-results" / suffix)
        )
        self.assertTrue((run / "replaced-checks" / suffix).is_file())

    def test_snapshot_rejects_partial_annular_reapplication_marker(self):
        snapshot = self._valid_snapshot()
        root = snapshot["design"]["components"][0]
        root["features"].append(
            {"name": "AnnularThickness_ReplaceFace_00", "health_state": 0}
        )
        result = MODULE._validate_snapshot(snapshot, RECIPE, PROFILE)
        self.assertTrue(any("already/partially" in item for item in result["issues"]))

    def test_annular_capture_rejects_geometry_drift_with_same_tokens(self):
        data = self._historical("fusion_annular_selection.json")
        data["records"][0]["centroid_cm"][0] += 0.01
        data["records"][0]["inner_cylinder"]["diameter_mm"] += 0.01
        path = self._write_json("drifted-selection.json", data)
        check = MODULE.validate_result(
            PROFILE_PATH, PROFILE, "capture-annular-selection", path
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("signature" in item.lower() for item in check["issues"]))

    def test_annular_apply_rejects_any_fallback(self):
        data = self._historical("fusion_annular_thickness_result.json")
        data["boundary_fill_count"] = 1
        path = self._write_json("fallback.json", data)
        check = MODULE.validate_result(
            PROFILE_PATH, PROFILE, "apply-annular-thickness", path
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("fallback" in item.lower() for item in check["issues"]))

    def test_annular_apply_rejects_reversed_offset_direction(self):
        data = self._historical("fusion_annular_thickness_result.json")
        data["inward_offset_sign"] = -1.0
        data["offset_expression"] = "annularWallThickness"
        for sample in data["direction_probe"]["samples"]:
            sample["sign"] *= -1.0
        path = self._write_json("reversed.json", data)
        check = MODULE.validate_result(
            PROFILE_PATH, PROFILE, "apply-annular-thickness", path
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("direction" in item.lower() for item in check["issues"]))

    def test_annular_validation_rejects_out_of_tolerance_thickness(self):
        data = self._historical("fusion_annular_thickness_validation.json")
        data["thickness"]["maximum_absolute_error_mm"] = 0.010001
        path = self._write_json("thickness.json", data)
        check = MODULE.validate_result(
            PROFILE_PATH, PROFILE, "validate-annular-thickness", path
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("thickness error" in item.lower() for item in check["issues"]))

    def test_annular_historical_pass_is_not_release_ready(self):
        path = HISTORICAL_ROOT / "fusion_annular_thickness_validation.json"
        check = MODULE.validate_result(
            PROFILE_PATH, PROFILE, "validate-annular-thickness", path
        )
        self.assertTrue(check["success"], check)
        self.assertEqual(3, len(check["release_blockers"]))
        self.assertTrue(any("outside-region" in item for item in check["warnings"]))

    def test_annular_validation_rejects_truncated_evidence(self):
        data = self._historical("fusion_annular_thickness_validation.json")
        data["groups"] = []
        data["cylinder_deltas"] = data["cylinder_deltas"][:1]
        path = self._write_json("truncated.json", data)
        check = MODULE.validate_result(
            PROFILE_PATH, PROFILE, "validate-annular-thickness", path
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("incomplete" in item.lower() for item in check["issues"]))

    def test_annular_validation_rejects_unhealthy_baseline_drift(self):
        data = self._historical("fusion_annular_thickness_validation.json")
        data["preexisting_unhealthy_features"][0]["health_state"] = 1
        path = self._write_json("baseline.json", data)
        check = MODULE.validate_result(
            PROFILE_PATH, PROFILE, "validate-annular-thickness", path
        )
        self.assertFalse(check["success"])
        self.assertTrue(
            any("unhealthy-feature baseline" in item for item in check["issues"])
        )

    def test_annular_apply_validation_body_chain_rejects_drift(self):
        run = self.temp / "chain-run"
        (run / "results").mkdir(parents=True)
        apply_path = run / "results" / "04-apply-annular-thickness.json"
        apply_data = self._historical("fusion_annular_thickness_result.json")
        MODULE.atomic_write_json(apply_path, apply_data)
        ledger = {
            "steps": {
                "apply-annular-thickness": {
                    "result_file": str(apply_path.relative_to(run))
                }
            }
        }
        validation = self._historical("fusion_annular_thickness_validation.json")
        validation["body"] = copy.deepcopy(apply_data["body_after"])
        self.assertEqual([], MODULE._verify_annular_body_chain(run, ledger, validation))
        validation["body"]["edge_count"] += 1
        issues = MODULE._verify_annular_body_chain(run, ledger, validation)
        self.assertTrue(any("edge_count" in item for item in issues))

    def test_full_annular_run_rejects_historical_apply_validation_body_drift(self):
        run = self._new_run()
        executor = self._copy_executor()
        self._advance_to_apply(run, executor)
        MODULE.stage_action(
            run, executor, TEST_TASK_ID, TEST_THREAD_ID,
            "validate-annular-thickness", True, False, False,
        )
        result = self._historical("fusion_annular_thickness_validation.json")
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
        result_path = executor / "fusion_annular_thickness_validation.json"
        MODULE.atomic_write_json(result_path, result)
        check, code = MODULE.record_result(
            run, "validate-annular-thickness", result_path, False
        )
        self.assertFalse(check["success"])
        self.assertEqual(MODULE.EXIT_VALIDATION, code)
        self.assertTrue(
            any("changed after apply" in item for item in check["issues"])
        )
        _root, manifest, ledger, *_rest = MODULE.load_run(run)
        status = MODULE._run_status(manifest, ledger)
        self.assertFalse(status["success"])
        self.assertFalse(status["complete"])
        self.assertFalse(status["release_ready"])
        self.assertEqual(3, len(status["release_blockers"]))


if __name__ == "__main__":
    unittest.main()
