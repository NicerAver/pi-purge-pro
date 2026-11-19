import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_output_contract_eval.py"
SPEC = importlib.util.spec_from_file_location("run_output_contract_eval", SCRIPT_PATH)
RUN_OUTPUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN_OUTPUT)


class OutputContractEvalTests(unittest.TestCase):
    def test_parse_events_collects_skills_and_text(self):
        output = "\n".join(
            (
                '{"type":"tool_use","part":{"tool":"skill","state":{"input":{"name":"trace"}}}}',
                '{"type":"text","part":{"text":"MODE: live-target"}}',
                '{"type":"text","part":{"text":"OWNER: trace"}}',
            )
        )

        skills, text = RUN_OUTPUT.parse_events(output)

        self.assertEqual(skills, ["trace"])
        self.assertIn("MODE: live-target", text)
        self.assertIn("OWNER: trace", text)

    def test_score_case_checks_required_and_forbidden_terms(self):
        case = {
            "id": "x",
            "query": "q",
            "expected_skill": "trace",
            "must_include": ["MODE", "trace"],
            "must_not_include": ["browser automation final"],
        }
        outcome = {"loaded_skills": ["trace"], "text": "MODE: live-target\nOWNER: trace", "error": None}

        scored = RUN_OUTPUT.score_case(case, outcome)

        self.assertTrue(scored["pass"])

    def test_score_case_supports_none(self):
        case = {"id": "none", "query": "q", "expected_skill": "none", "must_include": ["OWNER"]}
        outcome = {"loaded_skills": [], "text": "OWNER: none", "error": None}

        scored = RUN_OUTPUT.score_case(case, outcome)

        self.assertTrue(scored["pass"])

    def test_score_case_accepts_owner_text_without_skill_tool(self):
        case = {"id": "trace", "query": "q", "expected_skill": "trace", "must_include": ["OWNER"]}
        outcome = {"loaded_skills": [], "text": "OWNER: trace", "error": None}

        scored = RUN_OUTPUT.score_case(case, outcome)

        self.assertTrue(scored["pass"])


if __name__ == "__main__":
    unittest.main()
