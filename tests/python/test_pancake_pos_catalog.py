"""Bundled Pancake POS card, auth and permission regression tests (offline)."""
from _paths import ROOT
import json
import unittest
from unittest.mock import patch
import mcp_catalog as mc

class PancakePosCatalogTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / "system/mcp-catalog.json").read_text(encoding="utf-8"))
        self.con = next(c for c in self.data["connectors"] if c["id"] == "pancake-pos")

    def test_card_is_available_without_store_pack(self):
        with patch.object(mc, "_da_go", return_value=set()), patch.object(mc, "_lop_goi", return_value={}), patch.object(mc, "_sig_goi", return_value="test"):
            mc._cache["sig"] = None
            con = mc.load()["pancake-pos"]
            self.assertEqual(con["name"], "Pancake POS")
            self.assertEqual(con["default_perm"], "readonly")
            self.assertEqual(con["icon"], "/static/logos/pancake-pos.svg")
            self.assertTrue((ROOT / "dashboard/logos/pancake-pos.svg").is_file())
            cards = mc.public_catalog()
            if isinstance(cards, dict):
                cards = list(cards.values())
            self.assertTrue(any(c["id"] == "pancake-pos" for c in cards))

    def test_auth_and_validation_use_existing_catalog_contract(self):
        self.assertEqual(self.con["url"], "https://mcp-pos.pancake.biz/mcp")
        self.assertEqual(self.con["transport"], "http")
        field = self.con["auth"]["fields"][0]
        self.assertEqual(field["key"], "api_key")
        self.assertEqual(field["header"], "Authorization: Bearer {api_key}")
        self.assertEqual(self.con["validate"]["tool"], "pos_shop")
        self.assertEqual(self.con["validate"]["args"], {"action": "list"})
        self.assertIn("shops.0.name", self.con["validate"]["label_paths"])
        self.assertNotIn("secrets", self.con)

    def test_readonly_can_read_but_cannot_mutate_or_spend(self):
        for tool, args in [("pos_shop", {"action": "list"}), ("pos_order", {"action": "list"}),
                           ("pos_order", {"action": "get"}), ("pos_statistics", {})]:
            self.assertTrue(mc.allowed(self.con, "readonly", "full", tool, args)[0], (tool, args))
        for tool, args in [("pos_order", {"action": "create"}), ("pos_order", {"action": "update"}),
                           ("pos_transaction", {"action": "create"}), ("pos_ads_manager", {"action": "create"}),
                           ("pos_order", {}), ("pos_new_unknown", {})]:
            self.assertFalse(mc.allowed(self.con, "readonly", "full", tool, args)[0], (tool, args))
            self.assertFalse(mc.allowed(self.con, "safe", "auto", tool, args)[0], (tool, args))
        self.assertTrue(mc.allowed(self.con, "full", "full", "pos_order", {"action": "create"})[0])

    def test_builtin_wins_over_same_id_pack_without_duplicating_card(self):
        fake = dict(self.con, name="PACK VERSION", url="https://invalid.example")
        with patch.object(mc, "_da_go", return_value=set()), patch.object(mc, "_lop_goi", return_value={"pancake-pos": fake}), patch.object(mc, "_sig_goi", return_value="same-id"):
            mc._cache["sig"] = None
            self.assertEqual(mc.load()["pancake-pos"]["url"], self.con["url"])
            self.assertEqual(sum(c["id"] == "pancake-pos" for c in self.data["connectors"]), 1)

if __name__ == "__main__":
    unittest.main()
