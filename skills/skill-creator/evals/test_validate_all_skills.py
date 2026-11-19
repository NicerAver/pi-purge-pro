import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_all_skills.py"
SPEC = importlib.util.spec_from_file_location("validate_all_skills_under_test", SCRIPT_PATH)
VALIDATE_ALL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATE_ALL
SPEC.loader.exec_module(VALIDATE_ALL)


class ValidateAllSkillsTests(unittest.TestCase):
    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(ValueError):
            VALIDATE_ALL._reject_duplicate_json_keys([("reason", "first"), ("reason", "second")])

    def test_unique_json_keys_are_preserved(self):
        self.assertEqual(
            VALIDATE_ALL._reject_duplicate_json_keys([("name", "skill"), ("version", 1)]),
            {"name": "skill", "version": 1},
        )


if __name__ == "__main__":
    unittest.main()
