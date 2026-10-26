# -*- coding: utf-8 -*-
"""Đội Ads ghi Facebook Ads: dựng camp TẮT trước GATE, bật đúng camp đó sau GATE (26.10.248).

    python tests/run.py doi_ads_ghi      (KHÔNG mạng, MCP Meta giả)

Lời hứa với chủ (plans/doi-ads-ghi/PLAN.md):
1. Mọi lệnh ghi vào MCP Meta Ads chính chủ, từ bất kỳ engine nào, bị soi theo TRỊ SỐ: tài khoản
   phải trong danh sách cho phép, ngân sách không vượt trần (700.000đ/camp/ngày), dưới full không
   bật / không đặt ACTIVE / không sửa thứ đang chạy.
2. Bước dựng camp tạo camp TẮT/NHÁP đúng mẫu của chủ và lưu mã vào job; GATE hiện các mã đó.
3. Bước bật camp chỉ bật ĐÚNG các mã đã lưu; lệnh bật thô nhắm mã khác bị chặn kể cả ở full.
4. Bước job (cả sau GATE) chỉ dùng MCP qua hub: strict + tắt connector claude.ai.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-doiads-"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import meta_ads_luat as L  # noqa: E402
import mcp_client          # noqa: E402
import mcp_hub             # noqa: E402
import once_ledger         # noqa: E402
import tasks               # noqa: E402
from tasks import TasksDeps, TasksFeature  # noqa: E402

FAILS = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        FAILS.append(name)


TK = "1372588536646337"
S = {"quyen": {"meta_ads": {"tai_khoan": [TK], "tran_ngay_vnd": 700000}}}

# ---------------------------------------------------------------- 1. luật
check("mặc định: tài khoản ĐẠT 3, trần 700.000đ",
      L.doc_luat({}) == {"tai_khoan": [TK], "tran_ngay_vnd": 700000})
check("danh sách rỗng chủ đặt = không tài khoản nào", L.doc_luat(
    {"quyen": {"meta_ads": {"tai_khoan": [], "tran_ngay_vnd": 500000}}})["tai_khoan"] == [])
check("chuẩn hoá act_", L.chuan_tk(" act_123 ") == "123" and L.chuan_tk("abc") == "")
ok_camp = {"ad_account_id": TK, "campaign_name": "x", "objective": "OUTCOME_SALES",
           "buying_type": "AUCTION", "campaign_daily_budget": 300000}
check("tạo camp TẮT trong trần ở mức auto: cho qua", L.kiem_lenh("ads_create_campaign", ok_camp, "auto", S) == "")
check("tên có tiền tố connector vẫn nhận ra", L.kiem_lenh("meta__ads_create_campaign",
      {**ok_camp, "ad_account_id": "999"}, "full", S) != "")
check("tài khoản ngoài danh sách bị chặn kể cả full",
      "KHÔNG nằm trong" in L.kiem_lenh("ads_create_campaign", {**ok_camp, "ad_account_id": "act_999"}, "full", S))
check("thiếu ad_account_id bị chặn", L.kiem_lenh("ads_create_ad", {"ad_name": "a"}, "full", S) != "")
check("ngân sách 700.001đ bị chặn kể cả full",
      "vượt trần" in L.kiem_lenh("ads_create_campaign", {**ok_camp, "campaign_daily_budget": 700001}, "full", S))
check("đúng trần 700.000đ cho qua",
      L.kiem_lenh("ads_create_campaign", {**ok_camp, "campaign_daily_budget": 700000}, "auto", S) == "")
check("ngân sách nằm trong JSON fields của update bị soi",
      "vượt trần" in L.kiem_lenh("ads_update_entity", {"ad_account_id": TK, "entity_id": "1",
                                 "fields": json.dumps({"daily_budget": 5000000})}, "full", S))
check("trọn đời > trần x 30 bị chặn",
      L.kiem_lenh("ads_create_campaign", {**ok_camp, "campaign_daily_budget": None,
                  "campaign_lifetime_budget": 700000 * 31}, "full", S) != "")
check("auto: ads_activate_entity bị chặn",
      "Toàn quyền" in L.kiem_lenh("ads_activate_entity", {"ad_account_id": TK, "entity_id": "1"}, "auto", S))
check("auto: ads_update_entity bị chặn (đổi được camp đang chạy)",
      L.kiem_lenh("ads_update_entity", {"ad_account_id": TK, "entity_id": "1", "fields": "{\"name\":\"a\"}"}, "auto", S) != "")
check("auto: status ACTIVE trong lệnh tạo bị chặn",
      "ACTIVE" in L.kiem_lenh("ads_create_ad_set", {"ad_account_id": TK, "status": "ACTIVE"}, "auto", S))
check("auto: publish_as_active bị chặn", L.kiem_lenh("ads_create_ad",
      {"ad_account_id": TK, "publish_as_active": True}, "safe", S) != "")
check("tool đọc không bị soi", L.kiem_lenh("ads_get_ad_entities", {"ad_account_id": "999"}, "suggest", S) == "")
check("full: bật đúng mã đã lưu cho qua", L.kiem_lenh("ads_activate_entity",
      {"ad_account_id": TK, "entity_id": "120001", "object_ids": ["120001", "120002", "120003"]}, "full", S,
      ids_cho_phep=["120001", "120002", "120003"]) == "")
check("full: bật mã khác mã đã lưu bị chặn", "khác" in L.kiem_lenh("ads_activate_entity",
      {"ad_account_id": TK, "entity_id": "120009"}, "full", S, ids_cho_phep=["120001", "120002", "120003"]))
check("full: object_ids lẫn một mã lạ bị chặn", L.kiem_lenh("ads_activate_entity",
      {"ad_account_id": TK, "entity_id": "120001", "object_ids": ["120001", "999"]}, "full", S, ids_cho_phep=["120001"]) != "")
check("bước job chưa lưu mã nào: không bật gì", L.kiem_lenh("ads_activate_entity",
      {"ad_account_id": TK, "entity_id": "120001"}, "full", S, ids_cho_phep=[]) != "")
check("nhận ra MCP Meta Ads chính chủ theo địa chỉ",
      L.la_ket_noi_meta_ads("https://mcp.facebook.com/ads", "custom")
      and not L.la_ket_noi_meta_ads("https://graph.facebook.com/v26.0", "custom")
      and not L.la_ket_noi_meta_ads("https://evil.com/mcp.facebook.com/ads", "custom"))
luat, loi = L.kiem_luat_moi({"tai_khoan": "act_1, 2", "tran_ngay_vnd": "700.000"})
check("ô Giới hạn: nhận chuỗi nhiều tài khoản + số có dấu chấm", luat == {"tai_khoan": ["1", "2"], "tran_ngay_vnd": 700000}, (luat, loi))
check("ô Giới hạn: trần quá thấp bị từ chối", L.kiem_luat_moi({"tai_khoan": [], "tran_ngay_vnd": 1000})[0] is None)
check("ô Giới hạn: mã chữ bị từ chối", L.kiem_luat_moi({"tai_khoan": ["abc"], "tran_ngay_vnd": 700000})[0] is None)

# Soát độc lập (26.10.248) tìm ra các lỗ sau, canh từng cái:
check("tool ghi lạ (thử nghiệm A/B) bị coi là ghi: chặn dưới full",
      L.kiem_lenh("ads_experiment_abtest_create_test", {"ad_account_id": TK}, "auto", S) != "")
check("tool đọc lạ vẫn đọc được", L.kiem_lenh("ads_experiment_check_eligibility", {}, "suggest", S) == ""
      and L.kiem_lenh("ads_catalog_list_products", {}, "suggest", S) == "")
check("sao chép từ camp có sẵn bị chặn (ngân sách ẩn)",
      "sao" in L.kiem_lenh("ads_create_campaign", {**ok_camp, "source_campaign_id": "123"}, "full", S))
check("ngân sách trọn đời bị chặn hẳn", L.kiem_lenh("ads_create_campaign",
      {**ok_camp, "campaign_daily_budget": None, "campaign_lifetime_budget": 100000}, "full", S) != "")
check("lịch ngân sách bị chặn", L.kiem_lenh("ads_create_campaign",
      {**ok_camp, "budget_schedule_specs": json.dumps([{"budget_value": 100}])}, "full", S) != "")
check("ngân sách dạng '1.500.000' vẫn bị bắt", "vượt trần" in L.kiem_lenh("ads_create_campaign",
      {**ok_camp, "campaign_daily_budget": "1.500.000"}, "full", S))
check("ngân sách không đọc được thì chặn", L.kiem_lenh("ads_create_campaign",
      {**ok_camp, "campaign_daily_budget": "bảy trăm"}, "full", S) != "")
check("nhóm quảng cáo có ngân sách riêng bị chặn (10 nhóm x trần)", "CBO" in L.kiem_lenh("ads_create_ad_set",
      {"ad_account_id": TK, "campaign_id": "1", "daily_budget": 500000}, "full", S))
check("account_id khác ad_account_id bị chặn", L.kiem_lenh("ads_create_ad",
      {"ad_account_id": TK, "account_id": "act_999"}, "full", S) != "")
check("đủ trần nút soát: lệnh khổng lồ bị chặn chứ không lọt",
      L.kiem_lenh("ads_create_ad", {"ad_account_id": TK, "x": [[i] for i in range(5000)]}, "full", S) != "")
JOB = {"ids": ["120001", "120002", "120003"], "nhap": True}
check("trong bước job: tạo thô bị chặn (phải dùng công cụ hẹp)",
      L.kiem_lenh("ads_create_ad", {"ad_account_id": TK, "ad_set_id": "120002"}, "full", S, job=JOB) != "")
check("trong bước job: bật chiến dịch NHÁP không kèm object_ids bị chặn (đăng lậu con)",
      "object_ids" in L.kiem_lenh("ads_activate_entity", {"ad_account_id": TK, "entity_id": "120001",
                                  "entity_type": "campaign"}, "full", S, job=JOB))
check("trong bước job: camp TẮT (không nháp) bật chiến dịch không object_ids được",
      L.kiem_lenh("ads_activate_entity", {"ad_account_id": TK, "entity_id": "120001", "entity_type": "campaign"},
                  "full", S, job={**JOB, "nhap": False}) == "")
check("nhận ra MCP Meta ở đường con /ads/mcp", L.la_ket_noi_meta_ads("https://mcp.facebook.com/ads/mcp"))

# ---------------------------------------------------------------- 2. hub
import config  # noqa: E402
_goc_read = config.read_settings
config.read_settings = lambda: dict(S)
goi_that = []


async def _fake_call_tool(spec, tool, args):
    goi_that.append((tool, args))
    return json.dumps({"ok": True})

_goc_pool = mcp_client.pool.call_tool
mcp_client.pool.call_tool = _fake_call_tool


def _ent(url="https://mcp.facebook.com/ads", tool="ads_create_campaign"):
    return {"spec": {"key": "120001", "url": url, "headers": {}}, "tool": tool,
            "conn": {"id": "120001", "connector_id": "custom", "perm": "full", "label": "Meta"}}


async def _hub(ent, mode, args):
    return await mcp_hub._guard(ent, "x", mode)(args)

r = asyncio.run(_hub(_ent(tool="ads_activate_entity"), "auto", {"ad_account_id": TK, "entity_id": "1"}))
check("hub auto: lệnh bật camp thô bị chặn", r.startswith("ERROR") and not goi_that, r[:120])
r = asyncio.run(_hub(_ent(), "full", {**ok_camp, "ad_account_id": "555"}))
check("hub full: tài khoản lạ bị chặn, không gọi Meta", r.startswith("ERROR") and not goi_that, r[:120])
r = asyncio.run(_hub(_ent(), "full", {**ok_camp, "campaign_daily_budget": 2000000}))
check("hub full: vượt trần bị chặn", "vượt trần" in r and not goi_that, r[:120])
r = asyncio.run(_hub(_ent(), "auto", ok_camp))
check("hub auto: tạo camp hợp lệ đi qua", len(goi_that) == 1 and not r.startswith("ERROR"), r[:120])
goi_that.clear()
r = asyncio.run(_hub(_ent(url="https://khac.vn/mcp"), "full", {**ok_camp, "ad_account_id": "555"}))
check("hub: kết nối không phải Meta Ads không bị luật Đội Ads đụng", len(goi_that) == 1, r[:120])
goi_that.clear()


# ---------------------------------------------------------------- 3. job lưu mã camp
def _atomic(path, text):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


async def _wf(*_a, **_k):
    if False:
        yield {}


def _feature():
    tmp = Path(tempfile.mkdtemp(prefix="javis-doiads-t-"))
    brain = tmp / "Brain"
    brain.mkdir()

    async def report(*a, **k):
        return True
    deps = TasksDeps(brain_root=lambda v: str(brain), atomic_write_text=_atomic, execute_workflow=_wf,
                     workflows_dir=lambda b: brain / "workflows", build_system_prompt=lambda b: "s",
                     aux_model=lambda: None, safe_tools=["Read", "Write"], state_dir=tmp / "state",
                     scheduler_brains=lambda: [str(brain)], report=report)
    deps.notify_gate = lambda v, g: None
    return TasksFeature(deps), str(brain)


def _run(f, tid, result="xong"):
    async def execute(task):
        return result, "", False, {"provider": "test"}
    f._execute = execute
    c = f.store.claim(tid, "w")
    if c:
        asyncio.run(f._run_worker(c, "w"))


f, brain = _feature()
tasks._FEATURE = f
f.store.set_orchestration(brain, "auto")
_mau, steps = f.steps_from_template("ads-len-camp", "Váy lụa P720 page HALIMI 07")
check("mẫu Đội Ads gọi meta_ads_dung_camp ở bước dựng", "meta_ads_dung_camp" in steps[2]["intent"])
check("mẫu Đội Ads chỉ dùng meta_ads_bat_camp ở bước bật", "meta_ads_bat_camp" in steps[4]["intent"]
      and "KHÔNG dùng ads_activate_entity" in steps[4]["intent"])
jid = f.create_job(brain, "Lên camp", "ads", steps)
b = f._cac_buoc(jid)
dung, gate, bat = b[2]["id"], b[3]["id"], b[4]["id"]
ADS = {"tai_khoan": TK, "campaign_id": "120001", "adset_ids": ["120002"], "ad_ids": ["120003"],
       "ten": "CÔNG TY TNHH MTV HALIMI - HALIMI 07 - P720", "ngan_sach_ngay_vnd": 300000, "trang_thai": "NHAP"}
check("bước không đứng ngay trước GATE không lưu được mã", f.job_ads_luu(b[0]["id"], ADS) is False)
check("bước dựng (trước GATE) lưu mã được", f.job_ads_luu(dung, ADS) is True)
check("đọc lại mã từ bất kỳ bước nào của job", (f.job_ads_doc(bat) or {}).get("campaign_id") == "120001")
check("không lưu từ GATE", f.job_ads_luu(gate, ADS) is False)
check("không lưu thiếu campaign_id", f.job_ads_luu(dung, {**ADS, "campaign_id": ""}) is False)
check("bước sau GATE không thay được mã", f.job_ads_luu(bat, {**ADS, "campaign_id": "120009"}) is False
      and f.job_ads_doc(bat)["campaign_id"] == "120001")

# ids_job_hien_tai qua mã việc của lượt
tok = once_ledger.bind_job(f"kanban:{bat}")
check("lượt của bước job: ids = mã đã lưu", L.ids_job_hien_tai() == ["120001", "120002", "120003"], L.ids_job_hien_tai())
r = asyncio.run(_hub(_ent(tool="ads_activate_entity"), "full",
                     {"ad_account_id": TK, "entity_id": "120077", "entity_type": "campaign"}))
check("hub full trong bước job: bật mã lạ bị chặn", r.startswith("ERROR") and not goi_that, r[:120])
r = asyncio.run(_hub(_ent(tool="ads_activate_entity"), "full",
                     {"ad_account_id": TK, "entity_id": "120001", "entity_type": "campaign", "object_ids": ["120001", "120002", "120003"]}))
check("hub full trong bước job: bật đúng mã đi qua", len(goi_that) == 1, r[:120])
goi_that.clear()
once_ledger.reset_job(tok)
check("ngoài job: ids None (chat của chủ không bị ràng mã)", L.ids_job_hien_tai() is None)

for _ in range(3):
    _run(f, b[0]["id"])
    _run(f, b[1]["id"])
    _run(f, dung, "Đã dựng camp 120001")
    f._housekeep(brain)
v = next(j for j in f.jobs_view(brain)["jobs"] if j["id"] == jid)
g = v.get("gate_cho") or {}
check("GATE hiện thông tin camp sẽ bật", (g.get("ads") or {}).get("campaign_id") == "120001"
      and g["ads"]["ngan_sach_ngay_vnd"] == 300000 and g["ads"]["tai_khoan"] == TK, g)
f.gate_action(brain, jid, "duyet")
check("duyệt xong: bước dựng không lưu đè được nữa", f.job_ads_luu(dung, {**ADS, "campaign_id": "120005"}) is False)

# ---------------------------------------------------------------- 4. siết bước job ở full
class _Cli:
    mcp_config = "/tmp/x.json"
    mcp_strict = False
    env_them = None

c = _Cli()
TasksFeature._siet_buoc_job_full(c)
check("bước job full: strict MCP", c.mcp_strict is True)
check("bước job full: tắt connector claude.ai", (c.env_them or {}).get("ENABLE_CLAUDEAI_MCP_SERVERS") == "false")
c2 = _Cli()
TasksFeature._siet_buoc_job(c2)
check("bước job dưới full cũng tắt connector claude.ai", (c2.env_them or {}).get("ENABLE_CLAUDEAI_MCP_SERVERS") == "false")
src = (Path(SERVER) / "tasks.py").read_text(encoding="utf-8")
check("_base_cli gọi siết full cho bước job", "elif task.get(\"job_id\"):\n            self._siet_buoc_job_full(cli)" in src)
from claude_sdk_engine import ClaudeSDK  # noqa: E402
eng = ClaudeSDK(cwd=tempfile.mkdtemp(), tag="t")
eng.env_them = {"ENABLE_CLAUDEAI_MCP_SERVERS": "false"}
try:
    opts = eng._options()
    check("engine đưa env_them xuống tiến trình claude",
          (getattr(opts, "env", None) or {}).get("ENABLE_CLAUDEAI_MCP_SERVERS") == "false")
except Exception as e:  # SDK không có trên máy test
    print("bỏ qua kiểm env SDK:", type(e).__name__, e)

c3 = _Cli()
c3.mcp_config = None
TasksFeature._siet_buoc_job_full(c3)
check("bước job full thiếu cấu hình hub: khoá về 0 MCP + strict", bool(c3.mcp_config) and c3.mcp_strict is True)
import aux_engine  # noqa: E402


class _CliJob:
    javis_job = "kanban:t_1"
check("engine phụ nhận header mã việc", aux_engine._hub_job(_CliJob()) == {"X-Javis-Job": "kanban:t_1"}
      and aux_engine._hub_job(object()) == {})
ec = mcp_hub.dat_codex_job(["a=1"], "kanban:t_1")
check("Codex nhận header mã việc qua -c", any("X-Javis-Job" in x and "kanban:t_1" in x for x in ec)
      and mcp_hub.dat_codex_job(ec, "") == ["a=1"])
src_aux = (Path(SERVER) / "aux_engine.py").read_text(encoding="utf-8")
check("mọi engine CLI phụ gắn header mã việc", src_aux.count("**_hub_job(claude_cli_obj)") == 6)
import claude_sdk_engine  # noqa: E402
check("chặn connector Facebook Ads native của claude.ai", "mcp__claude_ai_Facebook_Ads" in claude_sdk_engine.cam_meta_native())
try:
    opts2 = ClaudeSDK(cwd=tempfile.mkdtemp(), tag="t")._options()
    check("mọi phiên Claude chặn connector Facebook Ads native",
          "mcp__claude_ai_Facebook_Ads" in list(getattr(opts2, "disallowed_tools", []) or []))
except Exception as e:
    print("bỏ qua kiểm disallowed SDK:", type(e).__name__, e)

# ---------------------------------------------------------------- 5. plugin
spec = importlib.util.spec_from_file_location("meta_ads_camp_plugin",
                                              Path(ROOT) / "system/plugins/meta-ads-camp/plugin.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


class _Ctx:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, desc, handler, schema=None, min_mode="readonly", check_fn=None, **k):
        self.tools[name] = {"handler": handler, "min_mode": min_mode, "check_fn": check_fn}

ctx = _Ctx()
P.register(ctx)
check("dựng camp min_mode safe, bật camp min_mode full",
      ctx.tools["meta_ads_dung_camp"]["min_mode"] == "safe" and ctx.tools["meta_ads_bat_camp"]["min_mode"] == "full")

P._ket_noi = lambda: None
check("chưa nối MCP Meta: check_fn nói rõ", "mcp.facebook.com/ads" in (P._check() or ""))

CONN = {"id": "m1", "url": "https://mcp.facebook.com/ads", "connector_id": "custom", "label": "Meta"}
P._ket_noi = lambda: CONN


async def _no_oauth(conn):
    return {"Authorization": "Bearer x"}
mcp_client._oauth_headers = _no_oauth
lenh = []
TRA = {"ads_create_campaign": {"campaign_id": "120001", "status": "DRAFT", "client_conversation_id": "A" * 20},
       "ads_create_ad_set": {"ad_set_id": "120002", "status": "DRAFT"},
       "ads_create_ad": {"ad_id": "120003", "status": "DRAFT"},
       "ads_activate_entity": {"status": "PUBLISHING"}}
TRANG_THAI = {}


async def _meta(spec, tool, args):
    lenh.append((tool, dict(args)))
    if tool == "ads_get_ad_entities":
        ids = args.get("object_ids") or []
        return json.dumps({"ad_entities": [{"id": i, "status": TRANG_THAI.get(i, "PAUSED"),
                                            "effective_status": TRANG_THAI.get(i, "PAUSED")} for i in ids]})
    if tool == "ads_activate_entity":
        for i in [args.get("entity_id")] + list(args.get("object_ids") or []):
            TRANG_THAI[i] = "ACTIVE" if (i == args.get("entity_id") or args.get("object_ids") is None) else "PAUSED"
    return json.dumps(TRA.get(tool, {}))
mcp_client.pool.call_tool = _meta

f2, brain2 = _feature()
tasks._FEATURE = f2
jid2 = f2.create_job(brain2, "Lên camp 2", "ads", steps)
b2 = f2._cac_buoc(jid2)
tok = once_ledger.bind_job(f"kanban:{b2[2]['id']}")
kq = asyncio.run(P._dung_camp({"page_id": "111", "page_ten": "Halimi 07", "ma_sp": "p720",
                               "bai_viet_id": "222"}, None))
once_ledger.reset_job(tok)
d = json.loads(kq) if kq.startswith("{") else {}
check("dựng camp bài viết: trả mã + đã lưu vào job", d.get("campaign_id") == "120001" and d.get("da_luu_vao_job"), kq[:200])
camp = next(a for t, a in lenh if t == "ads_create_campaign")
check("tên camp đúng mẫu HALIMI", camp["campaign_name"] == "CÔNG TY TNHH MTV HALIMI - HALIMI 07 - P720", camp["campaign_name"])
check("ngân sách mặc định 300.000đ, CBO", camp["campaign_daily_budget"] == 300000)
check("tài khoản mặc định ĐẠT 3, không act_", camp["ad_account_id"] == TK)
check("bắt đầu 23:59 giờ VN", camp["campaign_start_time"].endswith("T23:59:00+07:00"))
check("client_conversation_id 20 ký tự", len(camp["client_conversation_id"]) == 20)
nhom = next(a for t, a in lenh if t == "ads_create_ad_set")
tg = json.loads(nhom["targeting"])
check("đối tượng nữ 23-54 Việt Nam", tg["genders"] == [2] and tg["age_min"] == 23 and tg["age_max"] == 54
      and tg["geo_locations"]["countries"] == ["VN"])
check("nhóm dùng lại client_conversation_id Meta trả", nhom["client_conversation_id"] == "A" * 20)
check("không lệnh nào mang ACTIVE ở bước dựng", not any("ACTIVE" in json.dumps(a) for t, a in lenh))
qc = next(a for t, a in lenh if t == "ads_create_ad")
check("quảng cáo dùng bài viết có sẵn page_post", json.loads(qc["creative"]) == {"object_story_id": "111_222"})
check("job đã có mã camp", (f2.job_ads_doc(b2[4]["id"]) or {}).get("ad_ids") == ["120003"])

lenh.clear()
kq = asyncio.run(P._dung_camp({"page_id": "111", "page_ten": "X", "ma_sp": "P1", "bai_viet_id": "2",
                               "ngan_sach_ngay_vnd": 800000}, None))
check("dựng vượt trần: dừng trước khi gọi Meta", kq.startswith("ERROR") and not lenh, kq[:120])
kq = asyncio.run(P._dung_camp({"page_id": "111", "page_ten": "X", "ma_sp": "P1"}, None))
check("không landing không bài viết: dừng", kq.startswith("ERROR") and not lenh)


async def _landing_hong(url):
    return "landing page trả mã lỗi HTTP 404"
_goc_landing = P._landing_song
P._landing_song = _landing_hong
kq = asyncio.run(P._dung_camp({"page_id": "111", "page_ten": "X", "ma_sp": "P1", "bai_viet_id": "2",
                               "landing_page": "https://halimi.ladi.vn/a", "pixel_id": "9"}, None))
check("landing lỗi: DỪNG, không tự đổi sang camp bài viết", "DỪNG" in kq and not lenh, kq[:160])
P._landing_song = _goc_landing
kq = asyncio.run(P._dung_camp({"page_id": "111", "page_ten": "X", "ma_sp": "P1", "bai_viet_id": "2",
                               "tai_khoan": "act_999"}, None))
check("tài khoản lạ: plugin chặn trước khi gọi Meta", "CHẶN" in kq and not lenh, kq[:160])

# bật camp
kq = asyncio.run(P._bat_camp({}, None))
check("bật camp ngoài job: từ chối", kq.startswith("ERROR"))
tok = once_ledger.bind_job(f"kanban:{b2[4]['id']}")
lenh.clear()
kq = asyncio.run(P._bat_camp({}, None))
once_ledger.reset_job(tok)
d = json.loads(kq) if kq.startswith("{") else {}
bat = [a for t, a in lenh if t == "ads_activate_entity"]
check("bật: đăng nháp đúng 3 mã đã lưu, publish_as_active", bat and bat[0]["object_ids"] == ["120001", "120002", "120003"]
      and bat[0]["publish_as_active"] is True and bat[0]["entity_id"] == "120001", bat[:1])
check("bật: nhóm và quảng cáo còn TẮT thì bật từng cái", {a["entity_id"] for a in bat[1:]} == {"120002", "120003"})
check("bật: chỉ báo ok khi đọc lại đủ ACTIVE", d.get("ok") is True and "ACTIVE" in d.get("ket_luan", ""), kq[:300])
check("bật: không lệnh nào nhắm mã ngoài job",
      all(set([a.get("entity_id")] + list(a.get("object_ids") or [])) <= {"120001", "120002", "120003"} for a in bat))

# Meta chưa xác nhận -> không báo đang chạy
TRANG_THAI.clear()


async def _meta_cham(spec, tool, args):
    lenh.append((tool, dict(args)))
    if tool == "ads_get_ad_entities":
        return json.dumps({"ad_entities": [{"id": i, "status": "ACTIVE", "effective_status": "IN_PROCESS"}
                                           for i in args.get("object_ids") or []]})
    return json.dumps({"status": "PUBLISHING"})
mcp_client.pool.call_tool = _meta_cham
tok = once_ledger.bind_job(f"kanban:{b2[4]['id']}")
kq = asyncio.run(P._bat_camp({}, None))
once_ledger.reset_job(tok)
d = json.loads(kq) if kq.startswith("{") else {}
check("Meta còn IN_PROCESS: không báo là đang chạy", d.get("ok") is False and "chưa" in d.get("ket_luan", ""), kq[:300])

# Đọc lại ngân sách trước khi bật: lỗi đọc thì không bật; nhóm có ngân sách riêng thì không bật.
async def _meta_doc_loi(spec, tool, args):
    lenh.append((tool, dict(args)))
    if tool == "ads_get_ad_entities":
        return "ERROR: field không hợp lệ"
    return json.dumps({"status": "PUBLISHING"})
mcp_client.pool.call_tool = _meta_doc_loi
lenh.clear()
tok = once_ledger.bind_job(f"kanban:{b2[4]['id']}")
kq = asyncio.run(P._bat_camp({}, None))
check("không đọc lại được ngân sách: KHÔNG bật", kq.startswith("ERROR") and not any(t == "ads_activate_entity" for t, _ in lenh), kq[:160])


async def _meta_nhom_tien(spec, tool, args):
    lenh.append((tool, dict(args)))
    if tool == "ads_get_ad_entities":
        return json.dumps({"ad_entities": [{"id": i, "status": "PAUSED", "effective_status": "PAUSED",
                                            "daily_budget": "900000" if args.get("level") == "adset" else "300000"}
                                           for i in args.get("object_ids") or []]})
    return json.dumps({"status": "PUBLISHING"})
mcp_client.pool.call_tool = _meta_nhom_tien
lenh.clear()
kq = asyncio.run(P._bat_camp({}, None))
once_ledger.reset_job(tok)
check("có người sửa ngân sách sau lúc dựng: KHÔNG bật", "CHẶN" in kq and not any(t == "ads_activate_entity" for t, _ in lenh), kq[:160])
check("mã chỉ lấy theo khoá đã khai, phải là số",
      P._ma({"id": "5", "creative": {"id": "77777"}}, ("ad_id",)) == ""
      and P._ma({"result": {"ad_id": "120003"}}, ("ad_id",)) == "120003")

# ---------------------------------------------------------------- 6. route ô Giới hạn
import main  # noqa: E402
config.read_settings = _goc_read


class _Req:
    def __init__(self, body):
        self._b = body

    async def json(self):
        return self._b

r = asyncio.run(main.meta_ads_luat_luu(_Req({"tai_khoan": ["act_1372588536646337", "42"], "tran_ngay_vnd": 650000})))
check("POST /meta-ads/luat lưu được", isinstance(r, dict) and r.get("tai_khoan") == [TK, "42"] and r.get("tran_ngay_vnd") == 650000, r)
r = asyncio.run(main.meta_ads_luat_doc())
check("GET /meta-ads/luat đọc lại đúng", r.get("tran_ngay_vnd") == 650000)
r = asyncio.run(main.meta_ads_luat_luu(_Req({"tai_khoan": ["abc"], "tran_ngay_vnd": 650000})))
check("POST mã sai trả 400", getattr(r, "status_code", 200) == 400)

mcp_client.pool.call_tool = _goc_pool
if FAILS:
    raise SystemExit(f"\nFAIL - test_doi_ads_ghi: {len(FAILS)} lỗi")
print("\nOK - test_doi_ads_ghi: tất cả pass")
