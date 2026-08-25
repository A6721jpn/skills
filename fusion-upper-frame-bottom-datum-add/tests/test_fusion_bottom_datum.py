from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = SKILL_ROOT / "scripts" / "fusion_bottom_datum.py"
SPEC = importlib.util.spec_from_file_location("fusion_bottom_datum_under_test", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


PROFILE_PATH, PROFILE = MODULE.load_profile(
    SKILL_ROOT / "assets" / "upper-frame-bottom-datum-v1-profile.json"
)
HISTORICAL_ROOT = Path(
    "C:/dev/MeltMouse_ME_Dev/01_Fusion_Mechanical_Design/01_Active/"
    "upper-frame-fusion-development"
)
TEST_TASK_ID = "fusion-recipe-test"
TEST_THREAD_ID = "00000000-0000-0000-0000-000000000001"


class FusionBottomDatumTests(unittest.TestCase):
    def setUp(self):
        test_temp_root = SKILL_ROOT / ".test-work"
        test_temp_root.mkdir(exist_ok=True)
        self.temp = test_temp_root / self._testMethodName
        if self.temp.exists():
            shutil.rmtree(self.temp)
        self.temp.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp)

    def _write_json(self, name: str, value: dict) -> Path:
        path = self.temp / name
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def _historical(self, name: str) -> dict:
        return json.loads((HISTORICAL_ROOT / name).read_text(encoding="utf-8"))

    def _copy_executor(self, name: str = "executor", with_lock: bool = True) -> Path:
        executor_copy = self.temp / name
        for entry in PROFILE["executor"]["required_files"]:
            source = HISTORICAL_ROOT / entry["path"]
            destination = executor_copy / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        if with_lock:
            MODULE.atomic_write_json(
                executor_copy / ".codex-task-lock.json",
                {
                    "version": 1,
                    "task_id": TEST_TASK_ID,
                    "thread_id": TEST_THREAD_ID,
                    "state": "active",
                    "protected_paths": [str(executor_copy.resolve())],
                },
            )
        return executor_copy

    def _fresh_import_result(self, executor: Path, success: bool = True) -> Path:
        path = executor / "fusion_inspector_action_result.json"
        action = MODULE.load_json(executor / "fusion_inspector_action.json")
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

    def _advance_bottom_to_snapshot_passed(self, run: Path, executor: Path) -> None:
        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "import-trial",
            False,
            False,
            False,
        )
        import_result = self._fresh_import_result(executor)
        check, exit_code = MODULE.record_result(
            run, "import-trial", import_result, False
        )
        self.assertTrue(check["success"])
        self.assertEqual(MODULE.EXIT_OK, exit_code)

        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "snapshot-source",
            True,
            False,
            False,
        )
        recipe = PROFILE["recipes"]["bottom-datum-add"]
        expected = copy.deepcopy(recipe["source_fingerprint"]["main_body"])
        other_solids = copy.deepcopy(
            recipe["source_fingerprint"]["other_root_solids"]
        )
        baseline_features = copy.deepcopy(
            self._historical("fusion_bottom_z_projection_result.json")["correction"][
                "preexisting_unhealthy_features"
            ]
        )
        target = recipe["source_fingerprint"]["target"]
        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "is_saved": False,
            "design": {
                "root_component_name": "Untitled",
                "components": [
                    {
                        "name": "DatumSurfaces",
                        "bodies": [
                            {
                                "name": target["body"],
                                "is_solid": False,
                                "is_visible": True,
                                "area_cm2": target["area_cm2"],
                                "face_count": target["face_count"],
                            }
                        ],
                        "features": [],
                    },
                    {
                        "name": "Untitled",
                        "bodies": [expected, *other_solids],
                        "features": baseline_features,
                    },
                ],
                "timeline": [],
            },
        }
        snapshot_path = executor / "fusion_parametric_inspection.json"
        MODULE.atomic_write_json(snapshot_path, snapshot)
        check, exit_code = MODULE.record_result(
            run, "snapshot-source", snapshot_path, False
        )
        self.assertTrue(check["success"], check)
        self.assertEqual(MODULE.EXIT_OK, exit_code)

    def test_doctor_accepts_only_the_pinned_executor(self):
        report = MODULE.doctor_check(PROFILE, HISTORICAL_ROOT)
        self.assertTrue(report["success"], report)

        executor_copy = self._copy_executor()
        source_file = executor_copy / "fusion_inspector" / "fusion_inspector.py"
        source_file.write_text(
            source_file.read_text(encoding="utf-8") + "\n# drift\n",
            encoding="utf-8",
        )
        report = MODULE.doctor_check(PROFILE, executor_copy)
        self.assertFalse(report["success"])
        self.assertTrue(any("hash drift" in item.lower() for item in report["issues"]))

    def test_historical_evidence_hashes_and_gates_pass(self):
        report, exit_code = MODULE.audit_history(PROFILE)
        self.assertEqual(MODULE.EXIT_OK, exit_code)
        self.assertTrue(report["success"])
        self.assertEqual(4, len(report["reports"]))
        result_reports = [
            item for item in report["reports"] if "historical_sha256_match" in item
        ]
        self.assertEqual(2, len(result_reports))
        self.assertTrue(all(item["historical_sha256_match"] for item in result_reports))
        artifact_reports = [
            item
            for item in report["reports"]
            if str(item["step"]).startswith("historical-artifact:")
        ]
        self.assertEqual({"historical-artifact:f3d", "historical-artifact:step"}, {item["step"] for item in artifact_reports})
        self.assertTrue(all(item["success"] for item in artifact_reports))

    def test_profile_and_public_cli_are_single_recipe(self):
        self.assertEqual({MODULE.RECIPE_NAME}, set(PROFILE["recipes"]))
        controller_source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "_validate_annular",
            "_expected_selection",
            "_axis_group_count",
            "_verify_annular",
            '"capture_annular_selection"',
            '"annular_thickness_trial"',
            '"validate_annular_thickness"',
            '"annular_result"',
            '"annular_validation"',
        ):
            self.assertNotIn(forbidden, controller_source)
        parser = MODULE.build_parser()
        command_action = next(
            action for action in parser._actions if action.dest == "command"
        )
        for command in ("init-run", "check-result", "audit-history"):
            destinations = {
                action.dest for action in command_action.choices[command]._actions
            }
            self.assertNotIn("recipe", destinations)

        extra_profile = copy.deepcopy(PROFILE)
        extra_profile["recipes"]["unexpected-recipe"] = {}
        extra_path = self._write_json("extra-recipe-profile.json", extra_profile)
        with self.assertRaisesRegex(MODULE.CliFailure, "exactly"):
            MODULE.load_profile(extra_path)

        wrong_id_profile = copy.deepcopy(PROFILE)
        wrong_id_profile["recipes"][MODULE.RECIPE_NAME]["recipe_id"] = "wrong"
        wrong_id_path = self._write_json("wrong-recipe-id-profile.json", wrong_id_profile)
        with self.assertRaisesRegex(MODULE.CliFailure, "recipe_id"):
            MODULE.load_profile(wrong_id_path)

        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        foreign_run = self.temp / "foreign-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, foreign_run)
        manifest_path = foreign_run / "run-manifest.json"
        ledger_path = foreign_run / "ledger.json"
        manifest = MODULE.load_json(manifest_path)
        manifest["recipe_id"] = "foreign.recipe/v1"
        MODULE.atomic_write_json(manifest_path, manifest)
        ledger = MODULE.load_json(ledger_path)
        ledger["run_manifest_sha256"] = MODULE.sha256_file(manifest_path)
        MODULE.atomic_write_json(ledger_path, ledger)
        with self.assertRaisesRegex(MODULE.CliFailure, "recipe"):
            MODULE.load_run(foreign_run)

    def test_init_bottom_run_generates_a_pinned_action_sequence(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "bottom-run"
        report = MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        self.assertTrue(report["success"])
        manifest = MODULE.load_json(run / "run-manifest.json")
        self.assertEqual(
            [
                "import-trial",
                "snapshot-source",
                "apply-bottom-datum",
                "verify-exports",
            ],
            [step["id"] for step in manifest["steps"]],
        )
        import_action = MODULE.load_json(run / manifest["steps"][0]["action_file"])
        self.assertEqual("import_trial", import_action["action"])
        collected = run / manifest["input_archive"]["collected_file"]
        self.assertEqual(str(collected.resolve()), import_action["archive_path"])
        self.assertEqual(MODULE.sha256_file(archive), MODULE.sha256_file(collected))

    def test_mutating_stage_requires_explicit_fresh_unsaved_ack(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "bottom-stage-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        executor_copy = self._copy_executor()
        self._advance_bottom_to_snapshot_passed(run, executor_copy)

        with self.assertRaisesRegex(MODULE.CliFailure, "fresh-unsaved-trial"):
            MODULE.stage_action(
                run,
                executor_copy,
                TEST_TASK_ID,
                TEST_THREAD_ID,
                "apply-bottom-datum",
                False,
                False,
                False,
            )
        MODULE.stage_action(
            run,
            executor_copy,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "apply-bottom-datum",
            True,
            False,
            True,
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "never be restaged"):
            MODULE.stage_action(
                run,
                executor_copy,
                TEST_TASK_ID,
                TEST_THREAD_ID,
                "apply-bottom-datum",
                False,
                True,
                True,
            )

    def test_stage_rejects_a_missing_task_lock(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "no-lock-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        executor = self._copy_executor(with_lock=False)
        with self.assertRaisesRegex(MODULE.CliFailure, "task-lock|does not exist"):
            MODULE.stage_action(
                run,
                executor,
                TEST_TASK_ID,
                TEST_THREAD_ID,
                "import-trial",
                False,
                False,
                False,
            )

    def test_record_rejects_a_preexisting_stale_result(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "stale-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        executor = self._copy_executor()
        result = executor / "fusion_inspector_action_result.json"
        MODULE.atomic_write_json(
            result,
            {
                "action": "import_trial",
                "success": True,
                "is_saved": False,
                "generated_at": "2026-01-01T00:00:00+00:00",
            },
        )
        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "import-trial",
            False,
            False,
            False,
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "stale"):
            MODULE.record_result(run, "import-trial", result, False)

    def test_record_rejects_mailbox_tamper_and_wrong_import_path(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "mailbox-tamper-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        executor = self._copy_executor()
        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "import-trial",
            False,
            False,
            False,
        )
        mailbox = executor / "fusion_inspector_action.json"
        wrong_archive = self.temp / "wrong.f3d"
        wrong_archive.write_bytes(b"wrong archive")
        MODULE.atomic_write_json(
            mailbox,
            {"action": "import_trial", "archive_path": str(wrong_archive)},
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
        action_path = run / manifest["steps"][0]["action_file"]
        MODULE.atomic_copy(action_path, mailbox)
        check, exit_code = MODULE.record_result(run, "import-trial", result, False)
        self.assertEqual(MODULE.EXIT_VALIDATION, exit_code)
        self.assertFalse(check["success"])
        self.assertTrue(any("archive_path" in item for item in check["issues"]))

    def test_record_rechecks_executor_source_hashes(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "executor-drift-at-record-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        executor = self._copy_executor()
        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "import-trial",
            False,
            False,
            False,
        )
        result = self._fresh_import_result(executor)
        policy = executor / "fusion_inspector" / "bottom_z_policy.py"
        policy.write_text(
            policy.read_text(encoding="utf-8") + "\n# drift after stage\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "doctor failed at result"):
            MODULE.record_result(run, "import-trial", result, False)

    def test_record_rechecks_live_prior_result_chain(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "prior-result-drift-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        executor = self._copy_executor()
        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "import-trial",
            False,
            False,
            False,
        )
        import_result = self._fresh_import_result(executor)
        check, exit_code = MODULE.record_result(
            run, "import-trial", import_result, False
        )
        self.assertTrue(check["success"])
        self.assertEqual(MODULE.EXIT_OK, exit_code)
        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "snapshot-source",
            True,
            False,
            False,
        )
        import_data = MODULE.load_json(import_result)
        import_data["drift_after_snapshot_stage"] = True
        MODULE.atomic_write_json(import_result, import_data)
        snapshot_result = executor / "fusion_parametric_inspection.json"
        MODULE.atomic_write_json(
            snapshot_result,
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "is_saved": False,
                "design": {"components": [], "timeline": []},
            },
        )
        with self.assertRaisesRegex(MODULE.CliFailure, "no longer matches"):
            MODULE.record_result(
                run, "snapshot-source", snapshot_result, False
            )

    def test_run_rejects_collected_input_hash_drift(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "input-drift-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        manifest = MODULE.load_json(run / "run-manifest.json")
        collected = run / manifest["input_archive"]["collected_file"]
        collected.write_bytes(b"tampered collected input")
        with self.assertRaisesRegex(MODULE.CliFailure, "input hash/size changed"):
            MODULE.load_run(run)

    def test_status_rejects_a_forged_all_passed_ledger(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "forged-ledger-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        ledger = MODULE.load_json(run / "ledger.json")
        for step_id in ledger["steps"]:
            ledger["steps"][step_id] = {"state": "passed"}
        ledger["executor_binding"] = {
            "executor_root": str(self.temp / "fake-executor"),
            "task_id": TEST_TASK_ID,
            "thread_id": TEST_THREAD_ID,
        }
        MODULE.atomic_write_json(run / "ledger.json", ledger)
        with self.assertRaisesRegex(MODULE.CliFailure, "Result file|result evidence"):
            MODULE.load_run(run)

    def test_status_rejects_deleted_recorded_evidence(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "deleted-evidence-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        executor = self._copy_executor()
        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "import-trial",
            False,
            False,
            False,
        )
        result = self._fresh_import_result(executor)
        check, exit_code = MODULE.record_result(run, "import-trial", result, False)
        self.assertTrue(check["success"])
        self.assertEqual(MODULE.EXIT_OK, exit_code)
        (run / "results" / "01-import-trial.json").unlink()
        with self.assertRaisesRegex(MODULE.CliFailure, "result evidence changed"):
            MODULE.load_run(run)

    def test_run_rejects_switching_executor_roots(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "bound-executor-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        first = self._copy_executor("executor-one")
        MODULE.stage_action(
            run,
            first,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "import-trial",
            False,
            False,
            False,
        )
        result = self._fresh_import_result(first)
        check, exit_code = MODULE.record_result(run, "import-trial", result, False)
        self.assertTrue(check["success"])
        self.assertEqual(MODULE.EXIT_OK, exit_code)
        second = self._copy_executor("executor-two")
        with self.assertRaisesRegex(MODULE.CliFailure, "different executor"):
            MODULE.stage_action(
                run,
                second,
                TEST_TASK_ID,
                TEST_THREAD_ID,
                "snapshot-source",
                False,
                False,
                False,
            )

    def test_failed_result_cannot_be_replaced_to_resurrect_a_run(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "failed-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        executor = self._copy_executor()
        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "import-trial",
            False,
            False,
            False,
        )
        result = self._fresh_import_result(executor, success=False)
        _check, exit_code = MODULE.record_result(run, "import-trial", result, False)
        self.assertEqual(MODULE.EXIT_VALIDATION, exit_code)
        self._fresh_import_result(executor, success=True)
        with self.assertRaisesRegex(MODULE.CliFailure, "immutable"):
            MODULE.record_result(run, "import-trial", result, True)

    def test_init_rejects_an_unqualified_f3d(self):
        fake = self.temp / "unqualified.f3d"
        fake.write_bytes(b"not the pinned Fusion archive")
        with self.assertRaises(MODULE.CliFailure):
            MODULE.create_run(
                PROFILE_PATH,
                PROFILE,
                fake,
                self.temp / "rejected-run",
            )

    def test_bottom_gate_rejects_sub_099_datum_coverage(self):
        data = self._historical("fusion_bottom_z_projection_result.json")
        data["correction"]["target_coverage_ratio"] = 0.989999
        path = self._write_json("bad-bottom.json", data)
        check = MODULE.validate_result(
            PROFILE,
            "apply-bottom-datum",
            path,
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("coverage" in item.lower() for item in check["issues"]))

    def test_bottom_gate_rejects_duplicate_or_warning_join_features(self):
        data = self._historical("fusion_bottom_z_projection_result.json")
        joins = data["correction"]["combine_features"]
        for item in joins:
            item["name"] = "BottomBoundary_Join_0"
            item["timeline"]["name"] = "BottomBoundary_Join_0"
            item["error_or_warning"] = "warning"
        path = self._write_json("bad-bottom-joins.json", data)
        check = MODULE.validate_result(
            PROFILE,
            "apply-bottom-datum",
            path,
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("join" in item.lower() for item in check["issues"]))

    def test_bottom_gate_rejects_unknown_preexisting_unhealthy_feature(self):
        data = self._historical("fusion_bottom_z_projection_result.json")
        extra = copy.deepcopy(
            data["correction"]["preexisting_unhealthy_features"][-1]
        )
        extra["index"] = 999
        extra["name"] = "UnexpectedFailure"
        extra["timeline"]["index"] = 999
        extra["timeline"]["name"] = "UnexpectedFailure"
        data["correction"]["preexisting_unhealthy_features"].append(extra)
        path = self._write_json("bottom-extra-unhealthy.json", data)
        check = MODULE.validate_result(
            PROFILE,
            "apply-bottom-datum",
            path,
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("unhealthy-feature baseline" in item for item in check["issues"]))

    def test_bottom_gate_rejects_hidden_root_solid_drift(self):
        data = self._historical("fusion_bottom_z_projection_result.json")
        hidden = next(
            item
            for item in data["correction"]["root_solids"]
            if item["name"] == "ボディ1"
        )
        hidden["volume_cm3"] += 0.01
        path = self._write_json("bottom-hidden-drift.json", data)
        check = MODULE.validate_result(
            PROFILE,
            "apply-bottom-datum",
            path,
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("root solid changed" in item.lower() for item in check["issues"]))

    def test_bottom_roundtrip_rejects_an_extra_step_solid(self):
        data = self._historical("fusion_bottom_z_export_verification.json")
        step = next(item for item in data["artifacts"] if item["type"] == "step")
        step["solid_bodies"].append(copy.deepcopy(step["solid_bodies"][0]))
        path = self._write_json("bad-step.json", data)
        check = MODULE.validate_result(
            PROFILE,
            "verify-exports",
            path,
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("exactly one solid" in item.lower() for item in check["issues"]))

    def test_bottom_roundtrip_rejects_missing_feature_health_evidence(self):
        data = self._historical("fusion_bottom_z_export_verification.json")
        f3d = next(item for item in data["artifacts"] if item["type"] == "f3d")
        f3d["new_feature_health"] = []
        path = self._write_json("missing-f3d-features.json", data)
        check = MODULE.validate_result(
            PROFILE,
            "verify-exports",
            path,
        )
        self.assertFalse(check["success"])
        self.assertTrue(any("feature" in item.lower() for item in check["issues"]))

    def test_snapshot_rejects_partial_reapplication_marker(self):
        recipe = PROFILE["recipes"]["bottom-datum-add"]
        expected = recipe["source_fingerprint"]["main_body"]
        target = recipe["source_fingerprint"]["target"]
        snapshot = {
            "is_saved": False,
            "design": {
                "components": [
                    {
                        "name": "DatumSurfaces",
                        "bodies": [
                            {
                                "name": target["body"],
                                "is_solid": False,
                                "is_visible": True,
                                "area_cm2": target["area_cm2"],
                                "face_count": target["face_count"],
                            }
                        ],
                        "features": [],
                    },
                    {
                        "name": "Untitled",
                        "bodies": [copy.deepcopy(expected)],
                        "features": [{"name": "BottomBoundary_Join_0"}],
                    },
                ],
                "timeline": [],
            },
        }
        result = MODULE._validate_snapshot(snapshot, recipe, PROFILE)
        self.assertTrue(any("already/partially" in item for item in result["issues"]))

    def test_replaced_result_and_check_are_preserved(self):
        archive = HISTORICAL_ROOT / "artifacts" / "01_Upper_Frame_v1.0_pretrial_20260731_190616.f3d"
        run = self.temp / "replace-result-run"
        MODULE.create_run(PROFILE_PATH, PROFILE, archive, run)
        executor = self._copy_executor()
        MODULE.stage_action(
            run,
            executor,
            TEST_TASK_ID,
            TEST_THREAD_ID,
            "import-trial",
            False,
            False,
            False,
        )
        stored = run / "results" / "01-import-trial.json"
        old_result = {
            "action": "import_trial",
            "success": False,
            "is_saved": False,
            "generated_at": "2026-01-01T00:00:00+00:00",
        }
        MODULE.atomic_write_json(stored, old_result)
        old_check_path = run / "checks" / "01-import-trial.json"
        MODULE.atomic_write_json(old_check_path, {"success": False, "old": True})
        first_hash = MODULE.sha256_file(stored)
        result = self._fresh_import_result(executor)
        second_check, second_exit = MODULE.record_result(
            run, "import-trial", result, True
        )
        self.assertEqual(MODULE.EXIT_OK, second_exit)
        self.assertTrue(second_check["success"])
        suffix = f"01-import-trial-{first_hash[:16]}.json"
        self.assertEqual(
            first_hash,
            MODULE.sha256_file(run / "replaced-results" / suffix),
        )
        self.assertTrue((run / "replaced-checks" / suffix).is_file())

    def test_bottom_exports_are_collected_and_roundtrip_hash_bound(self):
        run = self.temp / "artifact-run"
        run.mkdir()
        executor = self.temp / "artifact-executor"
        artifact_dir = executor / "artifacts"
        artifact_dir.mkdir(parents=True)
        f3d = artifact_dir / "result.f3d"
        step = artifact_dir / "result.step"
        f3d.write_bytes(b"fresh-f3d")
        step.write_bytes(b"fresh-step")
        data = {
            "exports": [
                {"type": "f3d", "path": str(f3d), "size_bytes": f3d.stat().st_size},
                {"type": "step", "path": str(step), "size_bytes": step.stat().st_size},
            ]
        }
        manifest_step = {"ordinal": 3, "id": "apply-bottom-datum"}
        collected, issues = MODULE._collect_bottom_exports(
            run,
            manifest_step,
            executor,
            {"staged_at_epoch_ns": 0},
            data,
        )
        self.assertEqual([], issues)
        self.assertEqual({"f3d", "step"}, {item["type"] for item in collected})

        check_path = run / "checks" / "03-apply-bottom-datum.json"
        MODULE.atomic_write_json(check_path, {"collected_artifacts": collected})
        ledger = {
            "steps": {
                "apply-bottom-datum": {"check_file": str(check_path.relative_to(run))}
            }
        }
        reopen = {
            "artifacts": [
                {"type": "f3d", "path": str(f3d)},
                {"type": "step", "path": str(step)},
            ]
        }
        chain, chain_issues = MODULE._verify_bottom_artifact_chain(run, ledger, reopen)
        self.assertEqual([], chain_issues)
        self.assertEqual(2, len(chain))
        f3d.write_bytes(b"tampered-f3d")
        _chain, tamper_issues = MODULE._verify_bottom_artifact_chain(run, ledger, reopen)
        self.assertTrue(any("changed" in item.lower() for item in tamper_issues))
        MODULE._verify_collected_artifact_records(
            run, collected, "Bottom apply test"
        )
        collected_f3d = run / next(
            item["collected_path"] for item in collected if item["type"] == "f3d"
        )
        collected_f3d.write_bytes(b"tampered-collected-f3d")
        with self.assertRaisesRegex(MODULE.CliFailure, "collected artifact changed"):
            MODULE._verify_collected_artifact_records(
                run, collected, "Bottom apply test"
            )


if __name__ == "__main__":
    unittest.main()
