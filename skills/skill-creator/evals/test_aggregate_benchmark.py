import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "aggregate_benchmark.py"
SPEC = importlib.util.spec_from_file_location("aggregate_benchmark", SCRIPT_PATH)
AGGREGATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AGGREGATE)


def write_metadata(root, eval_id, mode=None):
    eval_dir = root / f"eval-{eval_id}"
    eval_dir.mkdir(parents=True, exist_ok=True)
    payload = {"eval_id": eval_id, "prompt": f"eval {eval_id}"}
    if mode is not None:
        payload["evaluation_mode"] = mode
    (eval_dir / "eval_metadata.json").write_text(json.dumps(payload), encoding="utf-8")


def write_run(root, eval_id, config, pass_rate, mode=None, run_number=None):
    run_dir = root / f"eval-{eval_id}" / config
    if run_number is not None:
        run_dir /= f"run-{run_number}"
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "pass_rate": pass_rate,
            "passed": int(pass_rate == 1.0),
            "failed": int(pass_rate != 1.0),
            "total": 1,
        },
        "expectations": [],
    }
    if mode is not None:
        payload["evaluation_mode"] = mode
    (run_dir / "grading.json").write_text(json.dumps(payload), encoding="utf-8")


class AggregateBenchmarkTests(unittest.TestCase):
    def test_full_test_pair_is_claimable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_metadata(root, 1, "full_test")
            write_run(root, 1, "with_skill", 1.0, "full_test")
            write_run(root, 1, "without_skill", 0.0, "full_test")

            benchmark = AGGREGATE.generate_benchmark(root, "example")

            self.assertEqual(benchmark["metadata"]["evidence_modes"], ["full_test"])
            self.assertEqual(benchmark["metadata"]["claim_status"], "measured")
            self.assertEqual(benchmark["metadata"]["runs_per_configuration"], 1)
            self.assertTrue(benchmark["run_summary"]["delta"]["claimable"])
            self.assertTrue(all(run["evaluation_mode"] == "full_test" for run in benchmark["runs"]))

    def test_mixed_modes_are_unproven(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for eval_id, mode in ((1, "full_test"), (2, "dry_run")):
                write_metadata(root, eval_id, mode)
                write_run(root, eval_id, "with_skill", 1.0, mode)
                write_run(root, eval_id, "without_skill", 0.0, mode)

            benchmark = AGGREGATE.generate_benchmark(root, "example")

            self.assertEqual(benchmark["metadata"]["evidence_modes"], ["dry_run", "full_test"])
            self.assertEqual(benchmark["metadata"]["claim_status"], "unproven")
            self.assertFalse(benchmark["run_summary"]["delta"]["claimable"])
            self.assertEqual(benchmark["run_summary"]["with_skill"]["evidence_modes"], ["dry_run", "full_test"])
            self.assertIn("Unproven delta", AGGREGATE.generate_markdown(benchmark))

    def test_missing_mode_stays_unlabeled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_metadata(root, 1)
            write_run(root, 1, "with_skill", 1.0)
            write_run(root, 1, "without_skill", 0.0)

            benchmark = AGGREGATE.generate_benchmark(root, "example")

            self.assertEqual(benchmark["metadata"]["evidence_modes"], ["unlabeled"])
            self.assertEqual(benchmark["metadata"]["claim_status"], "unproven")

    def test_invalid_or_conflicting_modes_fail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_metadata(root, 1, "invalid")
            write_run(root, 1, "with_skill", 1.0)
            with self.assertRaises(ValueError):
                AGGREGATE.generate_benchmark(root, "example")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_metadata(root, 1, "full_test")
            write_run(root, 1, "with_skill", 1.0, "dry_run")
            with self.assertRaises(ValueError):
                AGGREGATE.generate_benchmark(root, "example")

    def test_unpaired_eval_ids_are_unproven(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_metadata(root, 1, "full_test")
            write_metadata(root, 2, "full_test")
            write_run(root, 1, "with_skill", 1.0, "full_test")
            write_run(root, 2, "without_skill", 0.0, "full_test")

            benchmark = AGGREGATE.generate_benchmark(root, "example")

            self.assertEqual(benchmark["metadata"]["claim_status"], "unproven")
            self.assertFalse(benchmark["run_summary"]["delta"]["claimable"])
            self.assertIn("same eval IDs", benchmark["run_summary"]["delta"]["claim_reason"])

    def test_unbalanced_repeat_counts_are_unproven(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_metadata(root, 1, "full_test")
            write_run(root, 1, "with_skill", 1.0, "full_test", run_number=1)
            write_run(root, 1, "with_skill", 1.0, "full_test", run_number=2)
            write_run(root, 1, "without_skill", 0.0, "full_test", run_number=1)

            benchmark = AGGREGATE.generate_benchmark(root, "example")

            self.assertEqual(benchmark["metadata"]["runs_per_configuration"], "varied")
            self.assertEqual(benchmark["metadata"]["claim_status"], "unproven")
            self.assertFalse(benchmark["run_summary"]["delta"]["claimable"])
            self.assertIn("repeat counts", benchmark["run_summary"]["delta"]["claim_reason"])


if __name__ == "__main__":
    unittest.main()
