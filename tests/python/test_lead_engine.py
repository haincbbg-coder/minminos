"""Business invariants: isolation, evidence, retries, revenue and private routes."""
from _paths import ROOT, SERVER
import asyncio
import importlib.util
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from lead_engine import LeadStore

spec = importlib.util.spec_from_file_location("lead_plugin_test", ROOT / "system/plugins/lead-engine/plugin.py")
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class LeadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.brain = self.root / "brain"
        self.brain.mkdir()
        self.store = LeadStore(self.root / "state", str(self.brain))
        self.at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        self.profile = dict(business_name="Example", offer="Service", ideal_customer="Homeowners", currency="VND")
        self.store.configure(self.profile)
        self.input = dict(source="pancake:shop-1", external_id="contact-1", name="Customer",
                          messages=[dict(id="m1", role="customer", text="Tôi muốn đặt. Cần vào thứ sáu.", at=self.at)])
        self.id = self.store.capture(self.input)["lead_id"]

    def test_retry_and_account_identity(self):
        self.assertEqual(self.store.capture(self.input)["lead_id"], self.id)
        self.assertEqual(self.store.report()["metrics"]["leads"], 1)
        self.assertEqual(len(self.store.detail({"lead_id": self.id})["messages"]), 1)
        other = self.store.capture({**self.input, "source": "pancake:shop-2"})
        self.assertNotEqual(other["lead_id"], self.id)

    def test_atomic_conflicting_message(self):
        with self.assertRaises(ValueError):
            self.store.capture({**self.input, "name": "Wrong", "messages": [
                {**self.input["messages"][0], "text": "Changed"}]})
        self.assertEqual(self.store.detail({"lead_id": self.id})["name"], "Customer")

    def analysis(self, **patch):
        args = dict(lead_id=self.id, summary="Wants to order", signals=[dict(kind="purchase_intent", message_id="m1", quote="Tôi muốn đặt")])
        return self.store.analyze({**args, **patch})

    def test_analysis_evidence_not_probability(self):
        result = self.analysis()
        self.assertEqual(result["score"], 45)
        self.assertFalse(result["is_purchase_probability"])
        self.store.capture(self.input)
        self.assertIsNotNone(self.store.detail({"lead_id": self.id})["analysis"])
        for signals in ([dict(kind="purchase_intent", message_id="m1", quote="made up")],
                        [dict(kind="purchase_intent", message_id="other", quote="Tôi muốn đặt")]):
            with self.assertRaises(ValueError):
                self.analysis(signals=signals)

    def test_business_message_not_customer_evidence(self):
        self.store.capture({**self.input, "messages": [dict(id="b1", role="business", text="Buy today", at=self.at)]})
        with self.assertRaises(ValueError):
            self.analysis(signals=[dict(kind="timing", message_id="b1", quote="today")])

    def test_stale_evidence(self):
        old = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
        self.store.capture({**self.input, "messages": [dict(id="old", role="customer", text="Order now", at=old)]})
        self.assertEqual(self.analysis(signals=[dict(kind="purchase_intent", message_id="old", quote="Order now")])["score"], 0)

    def test_invalid_date_and_negative_money(self):
        with self.assertRaises(ValueError):
            self.store.capture({**self.input, "messages": [dict(id="x", role="customer", text="x", at="2026-01-01")]})
        with self.assertRaises(ValueError):
            self.outcome(amount_minor=-1)
        with self.assertRaises(ValueError):
            self.outcome(amount_minor=True)

    def outcome(self, **patch):
        args = dict(lead_id=self.id, source="pos:shop-1", external_id="order-1", status="delivered",
                    amount_minor=500000, currency="VND", evidence_ref="pos:order-1", observed_at=self.at)
        return self.store.outcome({**args, **patch})

    def test_revenue_snapshot_and_refund(self):
        self.outcome(); self.outcome()
        report = self.store.report()["metrics"]
        self.assertEqual(report["delivered_revenue_minor"], 500000)
        self.assertEqual(report["delivered_orders"], 1)
        self.assertEqual(self.analysis()["score"], 55)
        self.outcome(status="refunded")
        self.assertEqual(self.store.report()["metrics"]["delivered_revenue_minor"], 0)
        self.assertIsNone(self.store.detail({"lead_id": self.id})["analysis"])
        with self.assertRaises(ValueError):
            self.outcome(observed_at="2020-01-01T00:00:00Z")

    def test_won_is_not_revenue(self):
        self.store.stage({"lead_id": self.id, "stage": "won"})
        self.assertEqual(self.store.report()["metrics"]["delivered_revenue_minor"], 0)

    def test_currency_and_spend_snapshot(self):
        args = dict(source="meta:act-1", campaign_id="c1", day=self.at[:10], amount_minor=100,
                    currency="VND", evidence_ref="meta:c1", observed_at=self.at)
        self.store.spend(args); self.store.spend(args)
        self.assertEqual(self.store.report()["metrics"]["spend_minor"], 100)
        with self.assertRaises(ValueError):
            self.store.configure({**self.profile, "currency": "USD"})
        with self.assertRaises(ValueError):
            self.outcome(currency="USD")

    def test_draft_retry_conflict_optout(self):
        args = dict(idempotency_key="follow-1", lead_id=self.id, kind="follow_up", body="Hello")
        self.assertFalse(self.store.draft(args)["sent"])
        self.store.draft(args)
        self.assertEqual(len(self.store.report()["drafts"]), 1)
        with self.assertRaises(ValueError):
            self.store.draft({**args, "body": "Different"})
        self.store.stage({"lead_id": self.id, "stage": "opted_out"})
        with self.assertRaises(ValueError):
            self.store.draft({**args, "idempotency_key": "follow-2"})
        with self.assertRaises(ValueError):
            self.store.stage({"lead_id": self.id, "stage": "new"})

    def test_brain_isolation_and_readonly(self):
        brain2 = self.root / "second"; brain2.mkdir()
        second = LeadStore(self.root / "state", str(brain2))
        self.assertEqual(second.report()["metrics"]["leads"], 0)
        self.assertFalse(second.path.exists())
        with self.assertRaises(ValueError):
            second.detail({"lead_id": self.id})
        with self.assertRaises(ValueError):
            LeadStore(self.root / "state", "")

    def test_concurrent_retries(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: self.store.capture(self.input), range(12)))
        self.assertEqual(self.store.report()["metrics"]["leads"], 1)

    def test_plugin_permissions_routes_and_setup(self):
        tools, routes = [], []
        ctx = SimpleNamespace(register_tool=lambda *a, **k: tools.append((a,k)),
                              register_http=lambda *a, **k: routes.append((a,k)))
        plugin.register(ctx)
        for args, kwargs in tools:
            self.assertEqual(kwargs["min_mode"], "readonly" if args[0] in ("lead_report", "lead_detail") else "safe")
        self.assertTrue(all(not k.get("public") and not k.get("no_cookie") for _,k in routes))
        self.assertTrue(plugin._setup_agent(self.store)["created"])
        path = self.brain / "agents/lead-engine.md"
        path.write_text("custom", encoding="utf-8")
        self.assertFalse(plugin._setup_agent(self.store)["created"])
        self.assertEqual(path.read_text(), "custom")


if __name__ == "__main__":
    unittest.main()
