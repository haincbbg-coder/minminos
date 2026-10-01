"""Lead ledger scoped to a brain. No network calls and no model-generated metrics.

Brain scoping is not SaaS tenant authorization: commercial installations must keep
separate state directories until the host has a tenant-aware identity layer.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SIGNALS = {"purchase_intent": 45, "product_fit": 25, "timing": 20}
STAGES = {"new", "qualified", "contacted", "won", "lost", "opted_out"}


def now():
    return datetime.now(timezone.utc).isoformat()


def text(value, name, limit=2000, required=True):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"{name}: cần chuỗi {'không rỗng, ' if required else ''}tối đa {limit} ký tự")
    return value.strip()


def timestamp(value):
    value = text(value, "timestamp", 50)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError()
        if dt > datetime.now(timezone.utc):
            raise ValueError()
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        raise ValueError("Thời điểm phải có múi giờ và không ở tương lai") from None


def money(value):
    if type(value) is not int or not 0 <= value <= 10**15:
        raise ValueError("amount_minor phải là số nguyên không âm theo đơn vị tiền nhỏ nhất")
    return value


class LeadStore:
    def __init__(self, data_dir, vault_root):
        if not vault_root or not Path(vault_root).is_dir():
            raise ValueError("Chưa xác định brain. Không tự chuyển sang brain mặc định.")
        self.root = Path(vault_root).resolve()
        key = hashlib.sha256(str(self.root).encode()).hexdigest()
        self.path = Path(data_dir).resolve() / key / "leads.sqlite3"

    @contextmanager
    def db(self, readonly=False):
        if not readonly:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        c = (sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=15) if readonly
             else sqlite3.connect(self.path, timeout=15))
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        if not readonly:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS leads (
              id TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
              name TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'new', updated TEXT NOT NULL,
              UNIQUE(source,external_id));
            CREATE TABLE IF NOT EXISTS messages (
              lead_id TEXT NOT NULL REFERENCES leads(id), id TEXT NOT NULL,
              role TEXT NOT NULL, body TEXT NOT NULL, at TEXT NOT NULL,
              PRIMARY KEY(lead_id,id));
            CREATE TABLE IF NOT EXISTS analyses (
              lead_id TEXT PRIMARY KEY REFERENCES leads(id), data TEXT NOT NULL, at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outcomes (
              source TEXT NOT NULL, external_id TEXT NOT NULL,
              lead_id TEXT NOT NULL REFERENCES leads(id), status TEXT NOT NULL,
              amount INTEGER NOT NULL, evidence TEXT NOT NULL, at TEXT NOT NULL,
              PRIMARY KEY(source,external_id));
            CREATE TABLE IF NOT EXISTS spend (
              source TEXT NOT NULL, campaign TEXT NOT NULL, day TEXT NOT NULL,
              amount INTEGER NOT NULL, evidence TEXT NOT NULL, at TEXT NOT NULL,
              PRIMARY KEY(source,campaign,day));
            CREATE TABLE IF NOT EXISTS drafts (
              id TEXT PRIMARY KEY, lead_id TEXT REFERENCES leads(id), kind TEXT NOT NULL,
              body TEXT NOT NULL, at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (
              seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, ref TEXT NOT NULL, at TEXT NOT NULL);
        """)
        try:
            c.execute("BEGIN" if readonly else "BEGIN IMMEDIATE")
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    @staticmethod
    def audit(c, kind, ref):
        c.execute("INSERT INTO audit(kind,ref,at) VALUES(?,?,?)", (kind, ref, now()))

    @staticmethod
    def require_profile(c):
        row = c.execute("SELECT data FROM profile WHERE id=1").fetchone()
        if not row:
            raise ValueError("Hãy lưu hồ sơ doanh nghiệp trước")
        return json.loads(row[0])

    @staticmethod
    def lead(c, lead_id):
        row = c.execute("SELECT * FROM leads WHERE id=?", (text(lead_id, "lead_id", 64),)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy lead trong brain này")
        return dict(row)

    def configure(self, args):
        p = {k: text(args.get(k, ""), k, n) for k, n in
             (("business_name", 160), ("offer", 2000), ("ideal_customer", 2000), ("currency", 3))}
        p["currency"] = p["currency"].upper()
        if not re.fullmatch(r"[A-Z]{3}", p["currency"]):
            raise ValueError("currency phải là mã tiền tệ 3 chữ cái")
        with self.db() as c:
            old = c.execute("SELECT data FROM profile WHERE id=1").fetchone()
            if old and json.loads(old[0])["currency"] != p["currency"]:
                if c.execute("SELECT 1 FROM outcomes UNION ALL SELECT 1 FROM spend LIMIT 1").fetchone():
                    raise ValueError("Đã có số tiền: không được đổi đơn vị tiền tệ của sổ")
            c.execute("INSERT OR REPLACE INTO profile VALUES(1,?)", (json.dumps(p, ensure_ascii=False),))
            self.audit(c, "profile", p["business_name"])
        return p

    def capture(self, args):
        source = text(args.get("source"), "source (kèm mã tài khoản)", 200)
        external_id = text(args.get("external_id"), "external_id", 300)
        name = text(args.get("name"), "name", 200)
        # Provider account + contact/thread ID, not display name or guessed phone normalization.
        lead_id = hashlib.sha256(json.dumps([source, external_id]).encode()).hexdigest()[:32]
        messages = args.get("messages", [])
        if not isinstance(messages, list) or len(messages) > 500:
            raise ValueError("Mỗi lần nhận tối đa 500 tin nhắn")
        clean = []
        for m in messages:
            if not isinstance(m, dict) or m.get("role") not in ("customer", "business"):
                raise ValueError("Tin nhắn cần role customer hoặc business")
            clean.append((lead_id, text(m.get("id"), "message.id", 300), m["role"],
                          text(m.get("text"), "message.text", 8000), timestamp(m.get("at"))))
        with self.db() as c:
            self.require_profile(c)
            c.execute("INSERT INTO leads(id,source,external_id,name,updated) VALUES(?,?,?,?,?) "
                      "ON CONFLICT(id) DO UPDATE SET name=excluded.name,updated=excluded.updated",
                      (lead_id, source, external_id, name, now()))
            added = False
            for row in clean:
                old = c.execute("SELECT role,body,at FROM messages WHERE lead_id=? AND id=?", row[:2]).fetchone()
                if old and tuple(old) != row[2:]:
                    raise ValueError("Mã tin nhắn đã có nội dung khác; cần đối soát nguồn")
                added = added or not old
                c.execute("INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?)", row)
            if added:
                c.execute("DELETE FROM analyses WHERE lead_id=?", (lead_id,))
            self.audit(c, "capture", lead_id)
        return {"lead_id": lead_id, "received_messages": len(clean)}

    def analyze(self, args):
        lead_id = args.get("lead_id")
        signals = args.get("signals")
        if not isinstance(signals, list) or len(signals) > len(SIGNALS):
            raise ValueError("signals phải là danh sách tối đa 3 tín hiệu có dẫn chứng")
        summary = text(args.get("summary"), "summary", 3000)
        result, seen, score = [], set(), 0
        with self.db() as c:
            self.lead(c, lead_id)
            for s in signals:
                if not isinstance(s, dict) or s.get("kind") not in SIGNALS or s["kind"] in seen:
                    raise ValueError("Tín hiệu không hợp lệ hoặc trùng loại")
                seen.add(s["kind"])
                quote = text(s.get("quote"), "quote", 2000)
                message_id = text(s.get("message_id"), "message_id", 300)
                m = c.execute("SELECT * FROM messages WHERE lead_id=? AND id=?", (lead_id, message_id)).fetchone()
                if not m or m["role"] != "customer" or quote not in m["body"]:
                    raise ValueError("Dẫn chứng phải nằm trong tin nhắn thật của khách thuộc lead này")
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(m["at"])).total_seconds() / 86400
                weight = SIGNALS[s["kind"]] if age <= 90 else 0
                score += weight
                result.append({"kind": s["kind"], "quote": quote, "message_id": message_id, "weight": weight})
            bought = c.execute("SELECT 1 FROM outcomes WHERE lead_id=? AND status='delivered' LIMIT 1", (lead_id,)).fetchone()
            score += 10 if bought else 0
            data = {"summary": summary, "signals": result, "score": score,
                    "tier": "HOT" if score >= 70 else "WARM" if score >= 40 else "COLD",
                    "score_method": "heuristic-v1", "is_purchase_probability": False,
                    "verified_purchase": bool(bought)}
            c.execute("INSERT OR REPLACE INTO analyses VALUES(?,?,?)", (lead_id, json.dumps(data, ensure_ascii=False), now()))
            self.audit(c, "analysis", lead_id)
        return data

    def stage(self, args):
        stage = args.get("stage")
        if stage not in STAGES:
            raise ValueError("Trạng thái lead không hợp lệ")
        with self.db() as c:
            lead = self.lead(c, args.get("lead_id"))
            if lead["stage"] == "opted_out" and stage != "opted_out":
                raise ValueError("Không tự khôi phục khách đã từ chối liên hệ")
            c.execute("UPDATE leads SET stage=?,updated=? WHERE id=?", (stage, now(), lead["id"]))
            self.audit(c, "stage:" + stage, lead["id"])
        return {"lead_id": lead["id"], "stage": stage}

    def outcome(self, args):
        source = text(args.get("source"), "source", 200)
        ext = text(args.get("external_id"), "external_id", 300)
        status = args.get("status")
        if status not in ("pending", "delivered", "cancelled", "refunded"):
            raise ValueError("status: pending, delivered, cancelled hoặc refunded")
        amount = money(args.get("amount_minor"))
        evidence = text(args.get("evidence_ref"), "evidence_ref", 1000)
        at = timestamp(args.get("observed_at"))
        with self.db() as c:
            p = self.require_profile(c)
            if args.get("currency") != p["currency"]:
                raise ValueError("Tiền tệ không khớp hồ sơ")
            lead = self.lead(c, args.get("lead_id"))
            old = c.execute("SELECT lead_id,at FROM outcomes WHERE source=? AND external_id=?", (source, ext)).fetchone()
            if old and (old["lead_id"] != lead["id"] or old["at"] > at):
                raise ValueError("Không được gán lại đơn cho lead khác hoặc ghi đè bằng dữ liệu cũ")
            c.execute("INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?,?,?,?)",
                      (source, ext, lead["id"], status, amount, evidence, at))
            c.execute("DELETE FROM analyses WHERE lead_id=?", (lead["id"],))
            self.audit(c, "outcome:" + status, ext)
        return {"external_id": ext, "status": status}

    def spend(self, args):
        source = text(args.get("source"), "source", 200)
        campaign = text(args.get("campaign_id"), "campaign_id", 300)
        day = text(args.get("day"), "day", 10)
        datetime.strptime(day, "%Y-%m-%d")
        at = timestamp(args.get("observed_at"))
        amount = money(args.get("amount_minor"))
        evidence = text(args.get("evidence_ref"), "evidence_ref", 1000)
        with self.db() as c:
            if args.get("currency") != self.require_profile(c)["currency"]:
                raise ValueError("Tiền tệ không khớp hồ sơ")
            old = c.execute("SELECT at FROM spend WHERE source=? AND campaign=? AND day=?", (source, campaign, day)).fetchone()
            if old and old[0] > at:
                raise ValueError("Số liệu chi phí cũ hơn bản đã lưu")
            c.execute("INSERT OR REPLACE INTO spend VALUES(?,?,?,?,?,?)", (source, campaign, day, amount, evidence, at))
            self.audit(c, "spend", campaign + ":" + day)
        return {"campaign_id": campaign, "day": day, "amount_minor": amount}

    def draft(self, args):
        kind = args.get("kind")
        if kind not in ("ad", "follow_up"):
            raise ValueError("kind phải là ad hoặc follow_up")
        body = text(args.get("body"), "body", 8000)
        key = text(args.get("idempotency_key"), "idempotency_key", 200)
        lead_id = args.get("lead_id") or None
        did = hashlib.sha256(key.encode()).hexdigest()[:32]
        with self.db() as c:
            self.require_profile(c)
            if kind == "follow_up" and not lead_id:
                raise ValueError("Tin chăm sóc cần lead_id")
            if lead_id and self.lead(c, lead_id)["stage"] == "opted_out":
                raise ValueError("Khách đã từ chối liên hệ")
            old = c.execute("SELECT lead_id,kind,body FROM drafts WHERE id=?", (did,)).fetchone()
            if old and tuple(old) != (lead_id, kind, body):
                raise ValueError("idempotency_key đã dùng cho nội dung khác")
            c.execute("INSERT OR IGNORE INTO drafts VALUES(?,?,?,?,?)", (did, lead_id, kind, body, now()))
            self.audit(c, "draft", did)
        return {"draft_id": did, "status": "draft", "sent": False}

    def detail(self, args):
        if not self.path.exists():
            raise ValueError("Chưa có lead trong brain này")
        with self.db(readonly=True) as c:
            result = self.lead(c, args.get("lead_id"))
            result["messages"] = [dict(r) for r in c.execute(
                "SELECT id,role,body,at FROM messages WHERE lead_id=? ORDER BY at DESC LIMIT 500", (result["id"],))]
            a = c.execute("SELECT data,at FROM analyses WHERE lead_id=?", (result["id"],)).fetchone()
            result["analysis"] = {**json.loads(a[0]), "at": a[1]} if a else None
            return result

    def report(self, args=None):
        if not self.path.exists():
            return {"profile": None, "generated_at": now(),
                    "metrics": {"leads": 0, "spend_minor": 0, "delivered_revenue_minor": 0, "delivered_orders": 0},
                    "stages": {}, "leads": [], "display_limit": 200, "drafts": [], "audit": [],
                    "coverage": "Chưa có dữ liệu. Hãy lưu hồ sơ doanh nghiệp và kết nối nguồn.",
                    "automation": {"campaign_execution": False, "outreach_sending": False}}
        with self.db(readonly=True) as c:
            p = c.execute("SELECT data FROM profile WHERE id=1").fetchone()
            leads = [dict(r) for r in c.execute("SELECT l.*,a.data AS analysis,a.at AS analyzed_at FROM leads l "
                     "LEFT JOIN analyses a ON a.lead_id=l.id ORDER BY l.updated DESC LIMIT 200")]
            for lead in leads:
                lead["analysis"] = json.loads(lead["analysis"]) if lead["analysis"] else None
            total = c.execute("SELECT count(*) FROM leads").fetchone()[0]
            spent = c.execute("SELECT coalesce(sum(amount),0) FROM spend").fetchone()[0]
            revenue, orders = c.execute("SELECT coalesce(sum(amount),0),count(*) FROM outcomes WHERE status='delivered'").fetchone()
            return {"profile": json.loads(p[0]) if p else None, "generated_at": now(),
                    "metrics": {"leads": total, "spend_minor": spent, "delivered_revenue_minor": revenue,
                                "delivered_orders": orders},
                    "stages": {r[0]: r[1] for r in c.execute("SELECT stage,count(*) FROM leads GROUP BY stage")},
                    "leads": leads, "display_limit": 200,
                    "drafts": [dict(r) for r in c.execute("SELECT * FROM drafts ORDER BY at DESC LIMIT 100")],
                    "audit": [dict(r) for r in c.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT 30")],
                    "coverage": "Dữ liệu đã nhập/đồng bộ vào sổ; chưa khẳng định đầy đủ dữ liệu nguồn.",
                    "automation": {"campaign_execution": False, "outreach_sending": False}}
