import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_suite_routing_eval.py"
SPEC = importlib.util.spec_from_file_location("run_suite_routing_eval", SCRIPT_PATH)
RUN_SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN_SUITE)


class SuiteRoutingEvalTests(unittest.TestCase):
    def test_parse_loaded_skills_collects_unique_skill_calls(self):
        output = "\n".join(
            (
                '{"type":"text","part":{"text":"start"}}',
                '{"type":"tool_use","part":{"tool":"skill","state":{"input":{"name":"trace"}}}}',
                '{"type":"tool_use","part":{"tool":"skill","state":{"input":{"name":"trace"}}}}',
                '{"type":"tool_use","part":{"tool":"skill","state":{"input":{"name":"captcha-reverse"}}}}',
            )
        )

        self.assertEqual(RUN_SUITE.parse_loaded_skills(output), ["trace", "captcha-reverse"])

    def test_parse_loaded_skills_rejects_malformed_lines(self):
        with self.assertRaises(ValueError):
            RUN_SUITE.parse_loaded_skills('not-json\n{"type":"text"}')

    def test_score_case_passes_when_expected_skill_loaded(self):
        case = {"query": "q", "expected_skill": "trace", "reason": "r"}
        scored = RUN_SUITE.score_case(
            case,
            [{"loaded_skills": ["trace"], "error": None}],
            match_threshold=0.5,
        )

        self.assertTrue(scored["pass"])
        self.assertEqual(scored["match_rate"], 1.0)

    def test_score_case_fails_when_forbidden_skill_is_loaded(self):
        case = {
            "query": "q",
            "expected_skill": "trace",
            "not_expected_skills": ["iv8-web-reverse"],
        }
        scored = RUN_SUITE.score_case(
            case,
            [{"loaded_skills": ["trace", "iv8-web-reverse"], "error": None}],
            match_threshold=0.5,
        )

        self.assertFalse(scored["pass"])
        self.assertEqual(scored["forbidden_owner_hits"], 1)
        self.assertEqual(scored["match_rate"], 0.0)

    def test_score_case_fails_on_infra_error(self):
        case = {"query": "q", "expected_skill": "trace"}
        scored = RUN_SUITE.score_case(
            case,
            [{"loaded_skills": None, "error": "timeout"}],
            match_threshold=0.5,
        )

        self.assertFalse(scored["pass"])
        self.assertEqual(scored["infra_failures"], 1)

    def test_score_case_supports_expected_none(self):
        case = {"query": "q", "expected_skill": "none"}
        scored = RUN_SUITE.score_case(
            case,
            [{"loaded_skills": [], "error": None}],
            match_threshold=0.5,
        )

        self.assertTrue(scored["pass"])
        self.assertEqual(scored["match_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
