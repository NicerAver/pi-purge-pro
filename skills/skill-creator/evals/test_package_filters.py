import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "package_skill.py"
SPEC = importlib.util.spec_from_file_location("package_skill", SCRIPT_PATH)
PACKAGE_SKILL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE_SKILL)


class PackageFilterTests(unittest.TestCase):
    def test_local_and_generated_artifacts_are_excluded(self):
        excluded = (
            "skill/.git/config",
            "skill/.CACHE/item",
            "skill/cache/item",
            "skill/logs/run.txt",
            "skill/run.LOG",
            "skill/.env",
            "skill/.env.local",
            "skill/config.local.json",
            "skill/local.config.json",
            "skill/results.json",
            "skill/archive.ZIP",
            "skill/js_reverse_cache/a.js",
            "skill/evals/evals.json",
            "skill/cases/_private_mapping.json",
        )
        for path in excluded:
            with self.subTest(path=path):
                self.assertTrue(PACKAGE_SKILL.should_exclude(Path(path)))

    def test_skill_resources_are_included(self):
        included = (
            "skill/SKILL.md",
            "skill/references/x.md",
            "skill/scripts/x.py",
            "skill/fixtures/x.json",
            "skill/assets/x.png",
        )
        for path in included:
            with self.subTest(path=path):
                self.assertFalse(PACKAGE_SKILL.should_exclude(Path(path)))


if __name__ == "__main__":
    unittest.main()
