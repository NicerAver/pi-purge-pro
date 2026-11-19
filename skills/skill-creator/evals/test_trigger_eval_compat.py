import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_eval.py"
SPEC = importlib.util.spec_from_file_location("run_eval", SCRIPT_PATH)
RUN_EVAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN_EVAL)

LOOP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_loop.py"
LOOP_SPEC = importlib.util.spec_from_file_location("run_loop_compat", LOOP_PATH)
RUN_LOOP = importlib.util.module_from_spec(LOOP_SPEC)
LOOP_SPEC.loader.exec_module(RUN_LOOP)


class ImmediateFuture:
    def result(self):
        return {"triggered": True, "error": None}


class FailedFuture:
    def result(self):
        raise RuntimeError("executor unavailable")


class FakeExecutor:
    def __init__(self, **_kwargs):
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def submit(self, _fn, query, *_args):
        self.queries.append(query)
        return ImmediateFuture()


class FailingExecutor(FakeExecutor):
    def submit(self, _fn, query, *_args):
        self.queries.append(query)
        return FailedFuture()


class TriggerEvalCompatibilityTests(unittest.TestCase):
    @patch.object(RUN_EVAL, "as_completed", side_effect=lambda futures: list(futures))
    @patch.object(RUN_EVAL, "ProcessPoolExecutor", FakeExecutor)
    def test_legacy_prompt_is_normalized(self, _as_completed):
        result = RUN_EVAL.run_eval(
            [{"prompt": "legacy query", "should_trigger": True}],
            "example-skill",
            "description",
            1,
            1,
            Path.cwd(),
        )
        self.assertEqual(result["summary"]["passed"], 1)

    def test_missing_query_is_rejected(self):
        with self.assertRaises(ValueError):
            RUN_EVAL.run_eval(
                [{"should_trigger": True}],
                "example-skill",
                "description",
                1,
                1,
                Path.cwd(),
            )

    @patch.object(RUN_EVAL, "as_completed", side_effect=lambda futures: list(futures))
    @patch.object(RUN_EVAL, "ProcessPoolExecutor", FailingExecutor)
    def test_infrastructure_failure_cannot_pass_negative_case(self, _as_completed):
        result = RUN_EVAL.run_eval(
            [{"query": "negative query", "should_trigger": False}],
            "example-skill",
            "description",
            1,
            1,
            Path.cwd(),
        )
        self.assertEqual(result["summary"]["infra_failures"], 1)
        self.assertFalse(result["results"][0]["pass"])

    def test_timeout_is_an_infrastructure_error(self):
        with patch.object(
            RUN_EVAL.subprocess,
            "run",
            side_effect=RUN_EVAL.subprocess.TimeoutExpired(["opencode"], 1),
        ):
            outcome = RUN_EVAL.run_single_query("query", "skill", "description", 1, str(Path.cwd()))
        self.assertIsNone(outcome["triggered"])
        self.assertIn("timeout", outcome["error"])

    def test_nonzero_exit_is_an_infrastructure_error(self):
        with patch.object(
            RUN_EVAL.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=3, stderr="provider unavailable", stdout=""),
        ):
            outcome = RUN_EVAL.run_single_query("query", "skill", "description", 1, str(Path.cwd()))
        self.assertIsNone(outcome["triggered"])
        self.assertIn("exited 3", outcome["error"])

    def test_empty_success_output_is_an_infrastructure_error(self):
        with patch.object(
            RUN_EVAL.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stderr="", stdout=""),
        ):
            outcome = RUN_EVAL.run_single_query("query", "skill", "description", 1, str(Path.cwd()))
        self.assertIsNone(outcome["triggered"])
        self.assertIn("no valid JSON event stream", outcome["error"])

    def test_valid_non_trigger_event_is_a_real_negative(self):
        stdout = '{"type":"text","part":{"text":"done"}}\n'
        with patch.object(
            RUN_EVAL.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stderr="", stdout=stdout),
        ):
            outcome = RUN_EVAL.run_single_query("query", "skill", "description", 1, str(Path.cwd()))
        self.assertEqual(outcome, {"triggered": False, "error": None})

    def test_malformed_line_cannot_be_hidden_by_a_valid_event(self):
        stdout = 'not-json\n{"type":"text","part":{"text":"done"}}\n'
        with patch.object(
            RUN_EVAL.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stderr="", stdout=stdout),
        ):
            outcome = RUN_EVAL.run_single_query("query", "skill", "description", 1, str(Path.cwd()))
        self.assertIsNone(outcome["triggered"])
        self.assertIn("malformed JSON", outcome["error"])

    def test_legacy_prompt_survives_full_loop(self):
        def fake_run_eval(eval_set, **_kwargs):
            results = [
                {
                    "query": item["query"],
                    "should_trigger": item["should_trigger"],
                    "triggers": 1,
                    "runs": 1,
                    "pass": True,
                }
                for item in eval_set
            ]
            return {"results": results, "summary": {"passed": len(results), "failed": 0, "total": len(results)}}

        with (
            patch.object(RUN_LOOP, "run_eval", side_effect=fake_run_eval),
            patch.object(RUN_LOOP, "parse_skill_md", return_value=("example-skill", "description", "body")),
        ):
            result = RUN_LOOP.run_loop(
                eval_set=[{"prompt": "legacy loop query", "should_trigger": True}],
                skill_path=Path.cwd(),
                description_override=None,
                num_workers=1,
                timeout=1,
                max_iterations=1,
                runs_per_query=1,
                trigger_threshold=0.5,
                holdout=0,
                model="test-model",
                verbose=False,
            )
        self.assertEqual(result["best_score"], "1/1")


if __name__ == "__main__":
    unittest.main()
