import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_pi_suite_routing_eval.py"
SPEC = importlib.util.spec_from_file_location("run_pi_suite_routing_eval", SCRIPT_PATH)
RUN_PI_SUITE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN_PI_SUITE)


class PiSuiteRoutingEvalTests(unittest.TestCase):
    def test_extract_markdown_section_stops_at_next_h2(self):
        text = """
# Title

## Routing Precedence

first rule

- second rule

## Other Section

ignored
""".lstrip()

        self.assertEqual(
            RUN_PI_SUITE.extract_markdown_section(text, "Routing Precedence"),
            "first rule\n\n- second rule",
        )

    def test_extract_markdown_section_errors_when_missing(self):
        with self.assertRaises(ValueError):
            RUN_PI_SUITE.extract_markdown_section("## Different\nbody", "Routing Precedence")

    def test_build_routing_instruction_defaults_to_legacy_prompt(self):
        self.assertEqual(
            RUN_PI_SUITE.build_routing_instruction(None),
            RUN_PI_SUITE.ROUTING_INSTRUCTION,
        )

    def test_build_routing_instruction_injects_gate_before_user_request(self):
        prompt = RUN_PI_SUITE.build_routing_instruction("Requested artifact beats marker words.")

        self.assertIn("Apply this routing gate before selecting OWNER", prompt)
        self.assertIn("Requested artifact beats marker words.", prompt)
        self.assertTrue(prompt.endswith("User request: "))

    def test_load_routing_gate_reads_routing_precedence_section(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workflow.md"
            path.write_text(
                "## Routing Precedence\n\nObservation owns observation.\n\n## Stage Gates\n\nignored\n",
                encoding="utf-8",
            )

            self.assertEqual(
                RUN_PI_SUITE.load_routing_gate(path),
                "Observation owns observation.",
            )

    def test_parse_owner_accepts_all_active_runtime_owners(self):
        self.assertEqual(
            RUN_PI_SUITE.parse_owner('{"OWNER":"wechat-miniapp-reverse"}'),
            "wechat-miniapp-reverse",
        )
        self.assertEqual(
            RUN_PI_SUITE.parse_owner('{"OWNER":"nv8-node-runtime"}'),
            "nv8-node-runtime",
        )

    def test_parse_owner_tolerates_bare_owner_line(self):
        self.assertEqual(
            RUN_PI_SUITE.parse_owner("OWNER: captcha-reverse"),
            "captcha-reverse",
        )
        self.assertEqual(
            RUN_PI_SUITE.parse_owner('prefix\nOWNER = "trace"\nsuffix'),
            "trace",
        )

    def test_summarize_counts_forbidden_owner_hits(self):
        results = [
            {
                "case_index": 0,
                "mode": "baseline",
                "correct": False,
                "error": None,
                "elapsed_ms": 10,
                "output_chars": 20,
                "forbidden_owner_hit": True,
            },
            {
                "case_index": 0,
                "mode": "with_skill",
                "correct": True,
                "error": None,
                "elapsed_ms": 15,
                "output_chars": 25,
                "forbidden_owner_hit": False,
            },
            {
                "case_index": 1,
                "mode": "baseline",
                "correct": True,
                "error": None,
                "elapsed_ms": 20,
                "output_chars": 30,
                "forbidden_owner_hit": False,
            },
            {
                "case_index": 1,
                "mode": "with_skill",
                "correct": False,
                "error": None,
                "elapsed_ms": 25,
                "output_chars": 35,
                "forbidden_owner_hit": True,
            },
        ]

        summary = RUN_PI_SUITE.summarize(results, total_cases=2)

        self.assertEqual(summary["baseline"]["forbidden_owner_hits"], 1)
        self.assertEqual(summary["with_skill"]["forbidden_owner_hits"], 1)
        self.assertEqual(summary["paired_forbidden_owner_hits"], 2)


if __name__ == "__main__":
    unittest.main()
