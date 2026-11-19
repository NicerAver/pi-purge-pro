import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "quick_validate.py"
SPEC = importlib.util.spec_from_file_location("quick_validate", SCRIPT_PATH)
QUICK_VALIDATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUICK_VALIDATE)


class QuickValidateTests(unittest.TestCase):
    def validate_frontmatter(self, frontmatter):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir)
            (skill_dir / "SKILL.md").write_text(
                f"---\n{frontmatter}\n---\n\n# Test\n",
                encoding="utf-8",
            )
            return QUICK_VALIDATE.validate_skill(skill_dir)

    def test_version_and_user_invocable_are_allowed(self):
        valid, message = self.validate_frontmatter(
            "name: test-skill\n"
            "description: Test skill description\n"
            "version: 1.2.3\n"
            "user-invocable: true"
        )
        self.assertTrue(valid, message)

    def test_fallback_parser_preserves_boolean_type(self):
        parsed = QUICK_VALIDATE.parse_simple_frontmatter("user-invocable: false")
        self.assertIs(parsed["user-invocable"], False)

    def test_user_invocable_requires_boolean(self):
        valid, _ = self.validate_frontmatter(
            "name: test-skill\n"
            "description: Test skill description\n"
            "user-invocable: yes-please"
        )
        self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main()
