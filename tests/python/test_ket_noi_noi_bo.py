"""Cổng kiểm định CHUNG cho mọi cầu nối API tự bọc (transport "internal"). Không mạng.

    python tests/run.py ket_noi_noi_bo

Mỗi connector internal trong catalog phải qua đủ các phép dưới đây thì mới được vào MinMin.
Test riêng của từng nền tảng (test_shopee_mcp.py...) kiểm ĐÚNG API; file này kiểm cái mà
mọi cầu nối đều phải giữ, để một nền tảng thêm sau không lọt qua chỉ vì quên viết test:

1. Đăng ký đủ: module có trong mcp_client._INTERNAL, nạp được, có list_tools/call.
2. Phân loại đủ: tool module khai == tool catalog phân loại (read/write/danger), không tool nào
   rơi xuống heuristic đoán theo tên. Tên tool không trùng giữa các cầu nối.
3. Quyền đúng: kết nối mới mặc định Chỉ đọc; tool danger bị CHẶN ở mức Chỉ đọc và Ghi thường;
   loop chế độ suggest/auto không gọi được tool danger dù kết nối để Toàn quyền.
4. Thiếu ô đăng nhập: báo lỗi, KHÔNG chạm mạng.
5. Không lộ bí mật: gọi MỌI tool với server giả trả lỗi nhại lại toàn bộ bí mật, và với lỗi mạng
   chứa bí mật; kết quả không được chứa bí mật nào.
6. Đa tài khoản: hai kết nối cùng connector ra hai namespace khác nhau, mỗi bên giữ bí mật riêng.
7. Văn bản sạch: không em dash / en dash (giọng đọc TTS bị khựng).
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import importlib
import json
import os
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="minmin-ketnoi-")

import httpx  # noqa: E402
_GOC = httpx.AsyncClient

from _gia_http import KiemTra  # noqa: E402
import mcp_catalog  # noqa: E402
import mcp_client  # noqa: E402
import mcp_store  # noqa: E402

check = KiemTra()
mcp_store_update_goc = mcp_store.update_connection
mcp_store.update_connection = lambda cid, patch: True     # phần 1-5 không ghi đĩa

# Lứa đầu (26.10.115) phải luôn còn đủ. Từ đó về sau MỌI connector internal đều đi qua cổng
# nghiêm, trừ hai cái có test riêng từ trước, nên thêm nền tảng mới là tự bị kiểm, không cần
# nhớ sửa file này.
LUA_DAU = {"shopee", "tiktok-shop", "lazada", "ghn", "ghtk", "sepay", "casso", "payos", "tiktok-ads", "zalo-oa"}
MIEN = {"botcake", "substack"}
cat = dict(mcp_catalog.load())
_them_module = {}
# Tự kiểm trước khi vào catalog: KET_NOI_THEM=a.json:b.json nạp khuôn connector từ file rời
# (không sửa catalog thật), module mặc định là <internal>_mcp.
for _p in [x for x in os.environ.get("KET_NOI_THEM", "").split(os.pathsep) if x.strip()]:
    _c = json.loads(open(_p, encoding="utf-8").read())
    cat[_c["id"]] = _c
    _them_module[_c.get("internal") or ""] = (_c.get("internal") or "") + "_mcp"
noi_bo = {cid: c for cid, c in cat.items() if c.get("transport") == "internal"}
MOI = {cid for cid in noi_bo if cid not in MIEN}
check("lứa đầu 10 connector vẫn đủ trong catalog", LUA_DAU <= set(noi_bo), sorted(LUA_DAU - set(noi_bo)))


class _CamMang:
    """httpx giả: bất kỳ request nào cũng bị ghi lại. Dùng để chứng minh 'không chạm mạng'."""
    goi = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def request(self, method, url, **kw):
        _CamMang.goi.append(url)
        raise AssertionError("không được chạm mạng")

    async def get(self, url, **kw):
        return await self.request("GET", url, **kw)

    async def post(self, url, **kw):
        return await self.request("POST", url, **kw)


def _gia_tri(ten, schema):
    """Giá trị tham số trông hợp lệ để đi qua bước kiểm đầu vào và chạm tới tầng HTTP."""
    t = (schema or {}).get("type")
    if (schema or {}).get("enum"):
        return schema["enum"][0]
    if t == "integer" or t == "number":
        return 1000 if any(x in ten for x in ("amount", "tien", "budget", "ngan_sach", "weight", "can")) else 1
    if t == "array":
        return ["1234567"]
    if t == "object":
        return {}
    if t == "boolean":
        return False
    low = ten.lower()
    if "url" in low:
        return "https://minmin.vi.du/cb"
    if "phone" in low or "tel" in low or "sdt" in low:
        return "0912345678"
    if "ngay" in low or "date" in low:
        return "2026-10-01"
    if "path" in low:
        return "/api/v2/shop/get_shop_info"
    if "text" in low or "noi_dung" in low or "description" in low or "mo_ta" in low or "ten" in low or "name" in low:
        return "Hang mau"
    return "1234567"


def _args_mau(tool):
    sch = tool.get("inputSchema") or {}
    props = sch.get("properties") or {}
    return {k: _gia_tri(k, v) for k, v in props.items() if k in (sch.get("required") or [])}


ten_da_thay = {}
for cid, con in sorted(noi_bo.items()):
    ten_mod = mcp_client._INTERNAL.get(con.get("internal") or "") or _them_module.get(con.get("internal") or "")
    check(f"[{cid}] có trong mcp_client._INTERNAL", bool(ten_mod), con.get("internal"))
    if not ten_mod:
        continue
    try:
        mod = importlib.import_module(ten_mod)
    except Exception as e:
        check(f"[{cid}] nạp được module {ten_mod}", False, f"{type(e).__name__}: {e}")
        continue
    check(f"[{cid}] có list_tools và call", callable(getattr(mod, "list_tools", None))
          and callable(getattr(mod, "call", None)))
    if cid not in MOI:
        continue   # Botcake/Substack có test riêng từ trước; cổng nghiêm chỉ áp cho lứa mới

    tools = asyncio.run(mod.list_tools({"secrets": {}}))
    ten = [t["name"] for t in tools]
    tm = con.get("tool_meta") or {}
    khai = set(tm.get("read") or []) | set(tm.get("write") or []) | set(tm.get("danger") or [])
    check(f"[{cid}] mọi tool đều được catalog phân loại", set(ten) <= khai, sorted(set(ten) - khai))
    check(f"[{cid}] catalog không phân loại tool ma", khai <= set(ten), sorted(khai - set(ten)))
    check(f"[{cid}] tool không khai trùng ở read và danger",
          not (set(tm.get("read") or []) & set(tm.get("danger") or [])))
    check(f"[{cid}] mỗi tool có schema object", all((t.get("inputSchema") or {}).get("type") == "object"
                                                  for t in tools))
    for n in ten:
        if n in ten_da_thay:
            check(f"tên tool {n} không trùng giữa {ten_da_thay[n]} và {cid}", False)
        ten_da_thay[n] = cid
    check(f"[{cid}] mặc định Chỉ đọc", con.get("default_perm") == "readonly", con.get("default_perm"))
    check(f"[{cid}] có hướng dẫn và cảnh báo rủi ro", bool((con.get("auth") or {}).get("guide"))
          and bool(con.get("risk")))

    for n in ten:
        loai = mcp_catalog.classify(con, n, {})
        if loai == "danger":
            check(f"[{cid}] {n}: Chỉ đọc chặn tool danger", not mcp_catalog.allowed(con, "readonly", "full", n, {})[0])
            check(f"[{cid}] {n}: Ghi thường chặn tool danger", not mcp_catalog.allowed(con, "safe", "full", n, {})[0])
            check(f"[{cid}] {n}: loop auto chặn tool danger dù Toàn quyền",
                  not mcp_catalog.allowed(con, "full", "auto", n, {})[0])
            check(f"[{cid}] {n}: Toàn quyền + chat mới gọi được", mcp_catalog.allowed(con, "full", "full", n, {})[0])
        elif loai == "read":
            check(f"[{cid}] {n}: đọc được ở Chỉ đọc", mcp_catalog.allowed(con, "readonly", "suggest", n, {})[0])

    # 4. thiếu ô đăng nhập -> lỗi, không chạm mạng
    httpx.AsyncClient = _CamMang
    _CamMang.goi = []
    for t in tools:
        ra = asyncio.run(mod.call(t["name"], _args_mau(t), {"key": "k-" + cid, "secrets": {}}))
        if not str(ra).startswith("ERROR"):
            check(f"[{cid}] {t['name']}: thiếu ô đăng nhập -> ERROR", False, str(ra)[:120])
    check(f"[{cid}] thiếu ô đăng nhập thì không tool nào chạm mạng", not _CamMang.goi, _CamMang.goi[:3])
    check(f"[{cid}] tool lạ -> ERROR", str(asyncio.run(mod.call("khong_ton_tai", {}, {"secrets": {}}))).startswith("ERROR"))

    # 5. không lộ bí mật: mọi ô điền giá trị canh gác; server nhại lại tất cả trong câu lỗi
    canh = {}
    for f in (con.get("auth") or {}).get("fields") or []:
        key = f["key"]
        # Mã CÔNG KHAI (định danh app/shop, địa chỉ trả về) không phải bí mật: link ủy quyền
        # bắt buộc chứa client_id/app_key. Mọi ô còn lại coi là bí mật và phải được giấu.
        if key in ("partner_id", "shop_id", "advertiser_id", "app_id"):
            canh[key] = "1234567"
        elif key in ("app_key", "client_id", "ma_doi_tac"):
            canh[key] = "congkhai1234"
        elif key in ("redirect_url", "return_url", "cancel_url"):
            canh[key] = "https://minmin.vi.du/cb"
        else:
            canh[key] = f"BIMAT-{key}-9f8e7d6c"
    canh.update({"access_token": "BIMAT-access-77aa", "refresh_token": "BIMAT-refresh-88bb",
                 "token_het_han": "9999999999", "moi_truong": "live", "redirect_url": "https://minmin.vi.du/cb"})
    bi_mat_that = [v for v in canh.values() if str(v).startswith("BIMAT-")]
    # Ô `pages` (Thống kê Pancake): nhiều dòng "page_id | token | tên". Bí mật là token bên trong.
    if "pages" in canh:
        bi_mat_that.remove(canh["pages"])
        canh["pages"] = "598364820025920 | BIMAT-pagetok1-9f8e7d6c | Page A\n120769791116649 | BIMAT-pagetok2-9f8e7d6c | Page B"
        bi_mat_that += ["BIMAT-pagetok1-9f8e7d6c", "BIMAT-pagetok2-9f8e7d6c"]
    tieng_vong = " ".join(bi_mat_that)

    class _NhaiLai(_CamMang):
        async def request(self, method, url, **kw):
            _CamMang.goi.append(url)

            class R:
                status_code = 401
                text = json.dumps({"error": "invalid " + tieng_vong, "message": tieng_vong, "code": 401,
                                   "msg": tieng_vong, "desc": tieng_vong})

                def json(self):
                    return json.loads(self.text)
            return R()

    class _LoiMang(_CamMang):
        async def request(self, method, url, **kw):
            raise ConnectionError("không tới được, token=" + tieng_vong + " url=" + url)

    for lop, nhan in ((_NhaiLai, "lỗi API nhại bí mật"), (_LoiMang, "lỗi mạng chứa bí mật")):
        httpx.AsyncClient = lop
        _CamMang.goi = []
        lo = []
        for t in tools:
            ra = str(asyncio.run(mod.call(t["name"], _args_mau(t), {"key": "k-" + cid, "secrets": dict(canh)})))
            if any(b in ra for b in bi_mat_that):
                lo.append(t["name"])
        check(f"[{cid}] {nhan}: không tool nào lộ bí mật", not lo, lo)
        # Phép trên chỉ có nghĩa khi request THẬT SỰ đi tới tầng HTTP (không bị chặn hết ở bước
        # kiểm đầu vào). Đòi ít nhất một nửa số tool chạm tới mạng giả.
        if lop is _NhaiLai:
            check(f"[{cid}] phép không-lộ-bí-mật thật sự chạm tầng HTTP", len(_CamMang.goi) * 2 >= len(tools),
                  f"{len(_CamMang.goi)}/{len(tools)}")
    httpx.AsyncClient = _GOC

    for ten_file in (f"{ten_mod}.py",):
        raw = (SERVER / ten_file).read_text(encoding="utf-8")
        check(f"[{cid}] {ten_file} không có em/en dash", "—" not in raw and "–" not in raw)

raw = (SERVER / "ket_noi_api.py").read_text(encoding="utf-8")
check("ket_noi_api.py không có em/en dash", "—" not in raw and "–" not in raw)

# ---- 6. đa tài khoản: hai shop Shopee = hai kết nối, hai namespace, bí mật không lẫn ----
mcp_store.update_connection = mcp_store_update_goc
id1, e1 = mcp_store.add_connection("shopee", {"label": "HALIMI", "fields": {
    "partner_id": "2001", "partner_key": "KEY-CHUNG-123456", "shop_id": "111"}})
id2, e2 = mcp_store.add_connection("shopee", {"label": "MeiMei", "fields": {
    "partner_id": "2001", "partner_key": "KEY-CHUNG-123456", "shop_id": "222"}})
check("thêm được 2 shop Shopee", id1 and id2 and not e1 and not e2, (e1, e2))
ds = {c["id"]: c for c in mcp_store.resolved() if c["connector_id"] == "shopee"}
check("hai kết nối ra hai namespace khác nhau", len({c["namespace"] for c in ds.values()}) == 2,
      [c["namespace"] for c in ds.values()])
check("mỗi kết nối giữ shop_id riêng", ds[id1]["secrets"]["shop_id"] == "111" and ds[id2]["secrets"]["shop_id"] == "222")
check("kết nối mới mặc định Chỉ đọc", ds[id1]["perm"] == "readonly")
check("bí mật lưu ĐÃ MÃ HOÁ trên đĩa", mcp_store.STORE.exists()
      and "KEY-CHUNG-123456" not in mcp_store.STORE.read_text(encoding="utf-8"))

import ket_noi_api as k  # noqa: E402
spec = {"key": id1, "secrets": dict(ds[id1]["secrets"])}
k.luu_bi_mat(spec, {"access_token": "AT-SHOP-111", "refresh_token": "RT-SHOP-111"})
ds = {c["id"]: c for c in mcp_store.resolved() if c["connector_id"] == "shopee"}
check("token mới lưu đúng kết nối shop 1", ds[id1]["secrets"].get("access_token") == "AT-SHOP-111")
check("token shop 1 không lẫn sang shop 2", "access_token" not in ds[id2]["secrets"])
check("lưu token không làm mất ô cũ", ds[id1]["secrets"].get("partner_key") == "KEY-CHUNG-123456")

check.ket_thuc()
