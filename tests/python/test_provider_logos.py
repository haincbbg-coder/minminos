"""Bundled provider images must work in an offline installation."""
from _paths import ROOT
import hashlib
import json
import unittest
import xml.etree.ElementTree as ET


class ProviderLogoTests(unittest.TestCase):
    def test_catalog_logos_are_bundled(self):
        catalog = json.loads((ROOT / "system/mcp-catalog.json").read_text(encoding="utf-8"))
        for con in catalog["connectors"]:
            with self.subTest(provider=con["id"]):
                icon = con["icon"]
                self.assertTrue(icon.startswith("/static/logos/"), icon)
                filename = icon.removeprefix("/static/logos/")
                self.assertNotIn("/", filename)
                self.assertTrue((ROOT / "dashboard/logos" / filename).is_file())

    def test_new_assets_match_provenance(self):
        sources = json.loads((ROOT / "dashboard/logos/provider-sources.json").read_text(encoding="utf-8"))
        for provider, entry in sources["providers"].items():
            with self.subTest(provider=provider):
                path = ROOT / "dashboard/logos" / entry["file"]
                raw = path.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"])
                self.assertTrue(entry["url"].startswith("https://"))
                if path.suffix == ".svg":
                    root = ET.fromstring(raw)
                    self.assertTrue(root.tag.endswith("svg"))
                    for node in root.iter():
                        self.assertFalse(node.tag.lower().endswith("script"))
                        for key, value in node.attrib.items():
                            self.assertFalse(key.lower().startswith("on"))
                            if key.endswith("href"):
                                self.assertTrue(value.startswith("#"), value)


if __name__ == "__main__":
    unittest.main()

