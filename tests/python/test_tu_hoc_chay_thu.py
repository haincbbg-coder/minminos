"""Trụ 6 (26.10.217): CHẠY THỬ AN TOÀN - không một hành động thật nào lọt ra ngoài.

    python3 tests/python/test_tu_hoc_chay_thu.py      (KHÔNG mạng, KHÔNG model)

Bộ cải tiến có đối chứng (Harness² viết lại cho MinMin) chạy MỘT trợ lý nhiều lần trên việc thật
của nó để so cách làm. Trợ lý ở mức full có tool tạo đơn, đăng Fanpage, gửi Zalo, giao việc nền.
File này chứng minh, bằng đúng các lớp quyền cứng mà lượt thật đi qua:

  1. ở chế độ thử: tool MCP ghi/nguy hiểm KHÔNG được gọi (chỉ ghi ý định, che bí mật);
  2. ở chế độ thử: plugin safe/full THẬT của app (fb_page_post, zalo_send_image, javis_task,
     javis_app_close) không chạy một dòng mã nào, kể cả check_fn;
  3. ở chế độ thử: javis_write_file chỉ ghi được vào brain TẠM, hub không tự rơi về brain thật;
  4. cờ đi được qua HTTP (header X-Javis-Shadow) cho Claude Code;
  5. NGOÀI chế độ thử mọi thứ chạy y như cũ (full vẫn là full).
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-chaythu-")
os.environ["JAVIS_STATE_DIR"] = _STATE
os.environ.setdefault("BRAINS_DIR", tempfile.mkdtemp(prefix="javis-chaythu-brains-"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import che_do_thu  # noqa: E402
import hanh_dong  # noqa: E402
import mcp_catalog  # noqa: E402
import mcp_client  # noqa: E402
import mcp_hub  # noqa: E402
import plugins_host  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


def chay(coro):
    return asyncio.run(coro)


async def trong_thu(ma, coro_fn):
    tok = che_do_thu.bat(ma)
    try:
        return await coro_fn()
    finally:
        che_do_thu.tat(tok)


GOC_TAM = Path(_STATE) / "harness"
GOC_TAM.mkdir(parents=True, exist_ok=True)
che_do_thu.dat_goc(GOC_TAM)
NAO_TAM = GOC_TAM / "h2-r1" / "lan" / "nao"
NAO_TAM.mkdir(parents=True, exist_ok=True)
NAO_THAT = Path(os.environ["BRAINS_DIR"]) / "brain-that"
NAO_THAT.mkdir(parents=True, exist_ok=True)
MA = "h2-r1-a"

# ============================================================ 0. cờ
check("ngoài chạy thử: không có cờ", che_do_thu.hien_tai() == "" and not che_do_thu.dang_bat())
for xau in ("", "abc", "h2-", "h2-a b", "h2-../x", "kanban:t_1", "h2-" + "x" * 90):
    tok = che_do_thu.bat(xau)
    check(f"mã lạ không bật cờ: {xau[:16]!r}", not che_do_thu.dang_bat())
    che_do_thu.tat(tok)
tok = che_do_thu.bat(MA)
check("mã hợp lệ bật cờ", che_do_thu.hien_tai() == MA)
che_do_thu.tat(tok)
check("tắt cờ trả về lượt thật", not che_do_thu.dang_bat())
check("brain tạm nằm trong gốc harness", che_do_thu.la_brain_tam(NAO_TAM))
check("brain thật KHÔNG phải brain tạm", not che_do_thu.la_brain_tam(NAO_THAT))
check("chính gốc harness không phải brain tạm", not che_do_thu.la_brain_tam(GOC_TAM))
check("đường dẫn leo ra ngoài bằng .. không lọt", not che_do_thu.la_brain_tam(str(GOC_TAM / ".." / "x")))

# ============================================================ 1. MCP qua _guard
_cu = {"call_route": mcp_client.call_route, "get": mcp_catalog.get, "classify": mcp_catalog.classify,
       "allowed": mcp_catalog.allowed, "audit": mcp_hub._audit_append, "ghi": hanh_dong.ghi,
       "tao_yc": hanh_dong.tao_yeu_cau, "cs": mcp_hub._chinh_sach_loai_viec}
goi_mcp = []
so_hd = []
yeu_cau = []
loai_tool = {"create_order": "write", "send_message": "danger", "get_orders": "read"}


async def _call_route(route, fn, args):
    # Route của lớp quyền (có "call") thì đi qua lớp đó y như mcp_client thật; route thô mà
    # _guard gọi xuống (chỉ có spec + tool) là "dịch vụ ngoài": tới được đây là đã làm thật.
    ent = (route or {}).get(fn) or {}
    if ent.get("call"):
        return await ent["call"](args or {})
    goi_mcp.append((fn, dict(args or {})))
    return "THẬT: đã làm"

mcp_client.call_route = _call_route
# Connector giả KHAI get_orders là đọc: ở chế độ thử chỉ tool khai đọc rõ ràng mới chạy thật (classify_ro).
mcp_catalog.get = lambda cid: {"tool_meta": {"read": ["get_orders"]}}
mcp_catalog.classify = lambda c, t, a: loai_tool.get(t, "write")
mcp_catalog.allowed = lambda *a, **k: (True, "")
mcp_hub._audit_append = lambda rec: None
hanh_dong.ghi = lambda rec: so_hd.append(rec)
hanh_dong.tao_yeu_cau = lambda **k: yeu_cau.append(k) or {"id": "x"}
try:
    def _g(tool):
        ent = {"conn": {"id": "c1", "connector_id": "pancake", "label": "Shop", "perm": "full"},
               "tool": tool, "spec": {}}
        return mcp_hub._guard(ent, f"shop__{tool}", "full")

    tao_don, gui_tin, doc_don = _g("create_order"), _g("send_message"), _g("get_orders")

    async def _thu():
        a = await tao_don({"sku": "A1", "access_token": "EAAB-bi-mat-123456789"})
        b = await gui_tin({"threadId": "9", "message": "Chào chị"})
        c = await doc_don({"ngay": "hom-nay"})
        return a, b, c

    a, b, c = chay(trong_thu(MA, _thu))
    ten_goi = [x[0] for x in goi_mcp]
    check("thử: tool MCP ghi (tạo đơn) KHÔNG được gọi", "shop__create_order" not in ten_goi, ten_goi)
    check("thử: tool MCP nguy hiểm (gửi tin) KHÔNG được gọi", "shop__send_message" not in ten_goi, ten_goi)
    check("thử: tool ĐỌC vẫn gọi thật để có số thật", ten_goi == ["shop__get_orders"], ten_goi)
    check("thử: câu trả về là GIẢ LẬP, không phải lỗi", a.startswith("GIẢ LẬP") and b.startswith("GIẢ LẬP"), a)
    check("thử: không ghi sổ hành động thật", so_hd == [], so_hd)
    yd = che_do_thu.lay_y_dinh(MA)
    check("thử: ghi đủ 2 ý định", [r["tool"] for r in yd] == ["create_order", "send_message"], yd)
    check("thử: bí mật trong tham số bị che", yd and yd[0]["args"].get("access_token") == "***", yd[:1])
    check("thử: ý định mang nguồn mcp", yd and yd[0]["nguon"] == "mcp:pancake", yd[:1])

    # Chính sách "hỏi trước": lượt thử KHÔNG được tạo yêu cầu duyệt làm phiền chủ.
    mcp_hub._chinh_sach_loai_viec = lambda: {"don_hang": "hoi_truoc", "nhan_tin": "hoi_truoc"}
    chay(trong_thu(MA, lambda: tao_don({"sku": "B"})))
    check("thử: mức 'hỏi trước' không sinh yêu cầu duyệt", yeu_cau == [], yeu_cau)
    che_do_thu.lay_y_dinh(MA)
    # Chính sách CHẶN vẫn thắng: lượt thử nhận đúng lỗi như lượt thật, không phải câu giả lập.
    mcp_hub._chinh_sach_loai_viec = lambda: {"don_hang": "chan"}
    kq = chay(trong_thu(MA, lambda: tao_don({"sku": "C"})))
    check("thử: việc bị chủ CHẶN vẫn trả lỗi chặn", kq.startswith("ERROR:"), kq)
    check("thử: việc bị chặn cũng không gọi thật", "shop__create_order" not in [x[0] for x in goi_mcp])
    che_do_thu.lay_y_dinh(MA)
    mcp_hub._chinh_sach_loai_viec = lambda: {}

    # Ngoài chạy thử: y như cũ.
    goi_mcp.clear()
    kq = chay(tao_don({"sku": "THAT"}))
    check("thật: tool ghi vẫn gọi thật ở mức full", [x[0] for x in goi_mcp] == ["shop__create_order"], goi_mcp)
    check("thật: kết quả thật trả về", kq.startswith("THẬT"), kq)
    check("thật: ghi sổ hành động như cũ", any(r.get("tool") == "create_order" for r in so_hd), so_hd)
    check("thật: không có ý định giả lập nào", che_do_thu.lay_y_dinh("") == [])

    # ============================================================ 4. qua HTTP (Claude Code)
    goi_mcp.clear()
    route = {"shop__create_order": {"call": tao_don}}

    async def _discover(*a, **k):
        return [], route
    _cu["discover"] = mcp_hub.discover_all
    mcp_hub.discover_all = _discover

    class _Req:
        def __init__(self, headers, body):
            self.headers = {k.lower(): v for k, v in headers.items()}
            self._b = body

        async def json(self):
            return self._b

    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "shop__create_order", "arguments": {"sku": "HTTP"}}}
    tok_hub = mcp_hub.hub_token()
    r1 = chay(mcp_hub.handle_http(_Req({"Authorization": f"Bearer {tok_hub}", "X-Javis-Mode": "full",
                                        "X-Javis-Shadow": "h2-http", "X-Javis-Vault": str(NAO_TAM)}, body)))
    txt1 = json.loads(r1.body)["result"]["content"][0]["text"]
    check("HTTP có header thử: không gọi thật", goi_mcp == [], goi_mcp)
    check("HTTP có header thử: trả GIẢ LẬP", txt1.startswith("GIẢ LẬP"), txt1)
    check("HTTP: ý định nằm đúng sổ của mã lượt", [r["tool"] for r in che_do_thu.lay_y_dinh("h2-http")] == ["create_order"])
    check("HTTP: cờ không rò sang lượt sau", not che_do_thu.dang_bat())
    chay(mcp_hub.handle_http(_Req({"Authorization": f"Bearer {tok_hub}", "X-Javis-Mode": "full"}, body)))
    check("HTTP không header: lượt thật gọi thật", [x[0] for x in goi_mcp] == ["shop__create_order"], goi_mcp)
    mcp_hub.discover_all = _cu["discover"]
finally:
    mcp_client.call_route = _cu["call_route"]
    mcp_catalog.get = _cu["get"]
    mcp_catalog.classify = _cu["classify"]
    mcp_catalog.allowed = _cu["allowed"]
    mcp_hub._audit_append = _cu["audit"]
    hanh_dong.ghi = _cu["ghi"]
    hanh_dong.tao_yeu_cau = _cu["tao_yc"]
    mcp_hub._chinh_sach_loai_viec = _cu["cs"]

# ============================================================ 2. plugin THẬT của app
ent = plugins_host._load_all(str(NAO_TAM))   # CÙNG khoá cache với plugin_tools bên dưới
muc_tieu = {"fb_page_post": "full", "zalo_send_image": "full", "javis_task": "safe",
            "javis_app_close": "full"}
da_chay = []
goc_handler = {}
for lp in ent["plugins"]:
    for t in lp.tools:
        if t["name"] in muc_tieu:
            goc_handler[t["name"]] = (t, t["handler"], t.get("check_fn"))

            def _spy(args, ctx, _n=t["name"]):
                da_chay.append(_n)
                return "THẬT: plugin đã chạy"

            def _spy_check(_n=t["name"]):
                da_chay.append(_n + ":check")
                return ""
            t["handler"] = _spy
            if t.get("check_fn"):
                t["check_fn"] = _spy_check
try:
    check("tìm thấy đủ plugin hệ thống cần thử", set(goc_handler) == set(muc_tieu), sorted(goc_handler))
    for ten, muc in muc_tieu.items():
        if ten in goc_handler:
            check(f"{ten} khai min_mode {muc}", goc_handler[ten][0]["min_mode"] == muc, goc_handler[ten][0]["min_mode"])
    _tools, p_route = plugins_host.plugin_tools("full", str(NAO_TAM))

    async def _thu_plugin():
        ra = {}
        for ten in muc_tieu:
            if ten in p_route:
                ra[ten] = await p_route[ten]["call"]({"page_id": "1", "message": "bài", "threadId": "2"})
        return ra

    kq = chay(trong_thu(MA, _thu_plugin))
    check("thử: KHÔNG plugin ghi/ra-ngoài nào chạy (kể cả check_fn)", da_chay == [], da_chay)
    check("thử: mọi plugin trả GIẢ LẬP", kq and all(str(v).startswith("GIẢ LẬP") for v in kq.values()), kq)
    yd = che_do_thu.lay_y_dinh(MA)
    check("thử: ghi ý định cho từng plugin", sorted(r["tool"] for r in yd) == sorted(kq), yd)
    check("thử: ý định mang nguồn plugin", all(r["nguon"].startswith("plugin:") for r in yd), yd)

    # Ngoài chạy thử: plugin full vẫn chạy như cũ ở mức full.
    kq2 = chay(p_route["fb_page_post"]["call"]({"page_id": "1", "message": "bài"}))
    check("thật: fb_page_post vẫn chạy ở mức full", "fb_page_post" in da_chay, da_chay)
    check("thật: trả kết quả của plugin", "THẬT" in str(kq2), kq2)
    # Và mức thấp vẫn bị chặn như cũ (cờ thử không nới quyền).
    _t2, r_suggest = plugins_host.plugin_tools("suggest", str(NAO_TAM))
    kq3 = chay(trong_thu(MA, lambda: r_suggest["javis_task"]["call"]({"op": "list"})))
    check("thử ở mức suggest: vẫn là lỗi quyền như cũ, không phải giả lập", str(kq3).startswith("ERROR:"), kq3)
finally:
    for ten, (t, h, cf) in goc_handler.items():
        t["handler"] = h
        if cf is not None:
            t["check_fn"] = cf

# ============================================================ 3. javis_write_file + brain
(NAO_THAT / "a.md").write_text("gốc", encoding="utf-8")
b_tools, b_route = mcp_hub._builtin_tools("full", str(NAO_THAT))
kq = chay(trong_thu(MA, lambda: b_route["javis_write_file"]["call"]({"path": "a.md", "content": "BẨN"})))
check("thử: javis_write_file KHÔNG ghi vào brain thật", (NAO_THAT / "a.md").read_text(encoding="utf-8") == "gốc")
check("thử: ghi brain thật trả GIẢ LẬP", str(kq).startswith("GIẢ LẬP"), kq)
che_do_thu.lay_y_dinh(MA)
_t, r_tam = mcp_hub._builtin_tools("full", str(NAO_TAM))
chay(trong_thu(MA, lambda: r_tam["javis_write_file"]["call"]({"path": "nhap.md", "content": "nháp"})))
check("thử: javis_write_file ghi được vào brain TẠM", (NAO_TAM / "nhap.md").read_text(encoding="utf-8") == "nháp")
chay(b_route["javis_write_file"]["call"]({"path": "a.md", "content": "chủ sửa"}))
check("thật: javis_write_file vẫn ghi như cũ", (NAO_THAT / "a.md").read_text(encoding="utf-8") == "chủ sửa")

# Hub không được suy ra brain đang mở trong lượt thử. Máy chỉ có MỘT brain là ca mà lượt thật
# chắc chắn suy ra nó; lượt thử thì phải trả None.
mcp_hub.quen_brain_dang_mo()
v_that = mcp_hub.resolve_vault("")[0]
check("thật: không header thì suy ra brain duy nhất (hành vi cũ)",
      v_that and Path(v_that).resolve() == NAO_THAT.resolve(), v_that)


def _rv(raw):
    tok = che_do_thu.bat(MA)
    try:
        return mcp_hub.resolve_vault(raw)
    finally:
        che_do_thu.tat(tok)


check("thử: không header -> KHÔNG có brain (không rơi về brain thật)", _rv("")[0] is None, _rv(""))
check("thử: header trỏ brain thật -> từ chối", _rv(str(NAO_THAT))[0] is None, _rv(str(NAO_THAT)))
check("thử: header trỏ brain tạm -> nhận", _rv(str(NAO_TAM))[0] == str(NAO_TAM.resolve()), _rv(str(NAO_TAM)))
mat = GOC_TAM / "h2-r1" / "mat" / "nao"
check("thử: brain tạm đã biến mất -> không có brain, không rơi về brain thật", _rv(str(mat))[0] is None)

# ============================================================ 5. mã nguồn: chốt chặn nằm đúng chỗ
src_hub = (SERVER / "mcp_hub.py").read_text(encoding="utf-8")
than_guard = src_hub.split("def _guard(")[1].split("def _ambient_enabled")[0]
i_thu = than_guard.find("che_do_thu.dang_bat()")
check("guard: chốt thử nằm TRƯỚC hỏi-trước, sổ làm-một-lần và đếm tần suất",
      0 < i_thu < than_guard.find("hanh_dong.can_hoi") and i_thu < than_guard.find("once_ledger.run")
      and i_thu < than_guard.find("_rate_ok("))
src_ph = (SERVER / "plugins_host.py").read_text(encoding="utf-8")
than_call = src_ph.split("def _make_call(")[1].split("def unload(")[0]
check("plugin: chốt thử nằm TRƯỚC check_fn và handler",
      0 < than_call.find("che_do_thu.dang_bat()") < than_call.find("if check_fn:"))
for f in ("che_do_thu.py",):
    check(f"{f} không có gạch dài", "—" not in (SERVER / f).read_text(encoding="utf-8"))

shutil.rmtree(_STATE, ignore_errors=True)
print()
print("FAIL: " + ", ".join(fails) if fails else "ALL OK")
raise SystemExit(1 if fails else 0)
