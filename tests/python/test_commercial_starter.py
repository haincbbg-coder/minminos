"""Offline tests for bundled commercial agents, skills and non-destructive upgrades."""
from pathlib import Path
import ast
import json
import re
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
import commercial_starter as starter


class CommercialStarterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.brain = self.base / "brain"
        self.source = self.base / "source"
        shutil.copytree(starter.BUNDLE_ROOT, self.source)

    def sync(self):
        return starter.sync_brain(self.brain, self.source)

    def test_fresh_install_and_idempotency(self):
        r = self.sync()
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(list((self.brain / "agents").glob("*.md"))), 4)
        self.assertEqual(len(list((self.brain / "skills").glob("*/SKILL.md"))), 12)
        self.assertEqual(len(r["installed"]), 19)
        self.assertFalse(self.sync()["installed"])
        self.assertFalse(self.sync()["updated"])

    def test_updates_preserve_edits_deletions_and_disabled_skill(self):
        self.sync()
        user = self.brain / "agents/hoa-don.md"
        user.write_text("CUSTOMER CONTENT", encoding="utf-8")
        deleted = self.brain / "agents/kinh-doanh-pos.md"
        deleted.unlink()
        profile = self.brain / "commercial/ho-so-doanh-nghiep.md"
        profile.write_text("MY BUSINESS", encoding="utf-8")
        skill = self.brain / "skills/pos-bao-cao"
        disabled = self.brain / "skills/.disabled/pos-bao-cao"
        disabled.parent.mkdir()
        skill.rename(disabled)
        source_skill = self.source / "skills/pos-bao-cao/SKILL.md"
        source_skill.write_text(source_skill.read_text(encoding="utf-8") + "\nNew template revision\n", encoding="utf-8")
        r = self.sync()
        self.assertTrue(r["ok"], r)
        self.assertEqual(user.read_text(encoding="utf-8"), "CUSTOMER CONTENT")
        self.assertEqual(profile.read_text(encoding="utf-8"), "MY BUSINESS")
        self.assertFalse(deleted.exists())
        self.assertFalse(skill.exists())
        self.assertIn("New template revision", (disabled / "SKILL.md").read_text(encoding="utf-8"))

    def test_existing_agent_directory_and_name_collision(self):
        old = self.brain / "Javis/agents"
        old.mkdir(parents=True)
        (old / "hoa-don.md").write_text("ORIGINAL", encoding="utf-8")
        self.sync()
        self.assertFalse((self.brain / "agents").exists())
        self.assertEqual((old / "hoa-don.md").read_text(encoding="utf-8"), "ORIGINAL")
        self.assertEqual(len(list(old.glob("*.md"))), 4)

    def test_independent_brains_and_corrupt_manifest(self):
        self.sync()
        other = self.base / "other"
        self.assertEqual(len(starter.sync_brain(other, self.source)["installed"]), 19)
        marker = self.brain / starter.MANIFEST
        marker.write_text("broken", encoding="utf-8")
        r = self.sync()
        self.assertFalse(r["ok"])
        self.assertEqual(marker.read_text(encoding="utf-8"), "broken")

    def test_symlink_escape_is_rejected(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.brain.mkdir()
        try:
            (self.brain / "skills").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink permission unavailable")
        r = self.sync()
        self.assertFalse(r["ok"])
        self.assertFalse(list(outside.iterdir()))

    def test_bundle_contract_and_business_neutrality(self):
        agents = list(self.source.glob("agents/*.md"))
        skills = {p.parent.name for p in self.source.glob("skills/*/SKILL.md")}
        for path in agents:
            raw = path.read_text(encoding="utf-8")
            front = raw.split("---", 2)[1]
            line = next(l for l in front.splitlines() if l.startswith("skills: "))
            refs = json.loads(line.split(": ", 1)[1])
            self.assertEqual(len(refs), 3)
            self.assertTrue(set(refs) <= skills)
            self.assertIn('model: ""', front)
        for path in self.source.rglob("*.md"):
            text = path.read_text(encoding="utf-8").lower()
            for private in ("halimi", "meimei", "act_1372588536646337", "chi vui", "hỏi bố", "bố cần"):
                self.assertIsNone(re.search(r"\\b" + re.escape(private) + r"\\b", text), str(path))
            self.assertNotIn("mm1.", text)
        for path in self.source.glob("skills/*/SKILL.md"):
            front = path.read_text(encoding="utf-8").split("---", 2)[1]
            desc = next(l for l in front.splitlines() if l.startswith("description: "))
            self.assertLessEqual(len(json.loads(desc.split(": ", 1)[1])), 150)

    def test_sync_is_in_real_brain_lifecycle_before_mirror(self):
        code = (ROOT / "server/system_sync.py").read_text(encoding="utf-8")
        fn = next(n for n in ast.parse(code).body if isinstance(n, ast.FunctionDef) and n.name == "sync_brain")
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
        install = next(n for n in calls if isinstance(n.func, ast.Attribute)
                       and isinstance(n.func.value, ast.Name)
                       and n.func.value.id == "commercial_starter" and n.func.attr == "sync_brain")
        mirror = next(n for n in calls if isinstance(n.func, ast.Name) and n.func.id == "mirror_skills")
        self.assertLess(install.lineno, mirror.lineno)


if __name__ == "__main__":
    unittest.main()
