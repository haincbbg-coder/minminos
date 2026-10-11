"""Nhiều tài khoản Facebook (26.10.138): MinMin tự biết Trang / tài khoản quảng cáo nào do tài khoản
Facebook nào quản lý, và đăng / đọc bằng ĐÚNG token của tài khoản đó, ngồi máy nào hay đăng từ
điện thoại cũng vậy. Không mạng (giả _get/_post/_conns/_token_of).

    python tests/run.py meta_nhieu_tai_khoan
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import json
import os
import sys
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-metanhieu-"))
_fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        _fails.append(n)


def nap(ten):
    spec = importlib.util.spec_from_file_location("t_" + ten.replace("-", "_"),
                                                  str(ROOT / "system" / "plugins" / ten / "plugin.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# Hai tài khoản Facebook của cùng BM Halimi. HB Vũ là mặc định (ngôi sao).
CONNS = [{"id": "c_hb", "label": "Khang - HB Vũ", "is_default": True},
         {"id": "c_tk", "label": "Trung - Tố Khuyên", "is_default": False}]
UTOK = {"c_hb": "U_HB", "c_tk": "U_TK"}
# Trang: A cả hai cùng quản lý, B chỉ HB Vũ, C chỉ Tố Khuyên.
PAGES = {
    "U_HB": [{"id": "A", "name": "Halimi Official", "category": "Shop", "access_token": "PT_A_HB", "tasks": ["MANAGE"]},
             {"id": "B", "name": "MeiMei Design", "category": "Shop", "access_token": "PT_B", "tasks": ["MANAGE"]}],
    "U_TK": [{"id": "A", "name": "Halimi Official", "category": "Shop", "access_token": "PT_A_TK", "tasks": ["MANAGE"]},
             {"id": "C", "name": "Melya Avenue", "category": "Shop", "access_token": "PT_C", "tasks": ["MANAGE"]},
             {"id": "D", "name": "Melya Avenue 2", "category": "Shop", "access_token": "PT_D", "tasks": ["MANAGE"]}],
}
ADS = {"U_HB": [{"account_id": "111", "name": "BM Halimi 1"}, {"account_id": "222", "name": "BM Halimi 2"}],
       "U_TK": [{"account_id": "222", "name": "BM Halimi 2"}, {"account_id": "333", "name": "BM Halimi 3"}]}


async def chay():
    pg = nap("meta-pages-graph")
    pg._conns = lambda: list(CONNS)
    async def tok_of(cid): return UTOK[cid]
    pg._token_of = tok_of
    posts = []
    async def fget(path, params, token):
        if path == "me/accounts":
            return {"data": PAGES[token]}
        return {"data": []}
    async def fpost(path, data, token):
        posts.append((path, token))
        return {"id": path.split("/")[0] + "_999"}
    pg._get, pg._post = fget, fpost

    r = json.loads(await pg._list({}, None))
    ids = {p["id"]: p for p in r}
    check("fb_pages_list: gộp Trang của CẢ HAI tài khoản (A, B, C, D)", set(ids) == {"A", "B", "C", "D"}, list(ids))
    check("fb_pages_list: ghi rõ tài khoản nào quản lý Trang nào",
          ids["B"]["tai_khoan"] == ["Khang - HB Vũ"] and ids["C"]["tai_khoan"] == ["Trung - Tố Khuyên"])
    check("fb_pages_list: Trang cả hai cùng quản lý hiện MỘT lần với hai tài khoản",
          len(ids["A"]["tai_khoan"]) == 2)
    check("fb_pages_list: KHÔNG lộ token Trang", "PT_" not in json.dumps(r))
    r_tk = json.loads(await pg._list({"tai_khoan": "Tố Khuyên"}, None))
    check("fb_pages_list: lọc theo tài khoản", {p["id"] for p in r_tk} == {"A", "C", "D"})

    pid, ptok, _, err = await pg._resolve_page({"page": "MeiMei Design"}, None)
    check("Trang chỉ HB Vũ quản lý: dùng đúng token Trang của HB Vũ", pid == "B" and ptok == "PT_B" and not err)
    pid, ptok, _, err = await pg._resolve_page({"page": "Melya Avenue"}, None)
    check("tên chính xác thắng tên chứa chuỗi (Melya Avenue, không nhầm Melya Avenue 2)",
          pid == "C" and ptok == "PT_C" and not err, (pid, err))
    pid, ptok, _, err = await pg._resolve_page({"page": "Halimi Official"}, None)
    check("Trang cả hai quản lý: dùng tài khoản MẶC ĐỊNH (HB Vũ) trước", ptok == "PT_A_HB", ptok)
    pid, ptok, _, err = await pg._resolve_page({"page": "Halimi Official", "tai_khoan": "Tố Khuyên"}, None)
    check("chỉ định tai_khoan thì dùng đúng tài khoản đó", ptok == "PT_A_TK", ptok)
    _, _, _, err = await pg._resolve_page({"page": "Melya"}, None)
    check("tên mơ hồ (Melya khớp 2 Trang) → ERROR, KHÔNG đoán", err and err.startswith("ERROR") and "khớp nhiều" in err, err)
    _, _, _, err = await pg._resolve_page({"page": "Halimi Official", "tai_khoan": "Không có ai"}, None)
    check("tai_khoan không tồn tại → ERROR kèm danh sách tài khoản đang nối",
          err and "Khang - HB Vũ" in err, err)
    _, _, _, err = await pg._resolve_page({"page": "MeiMei Design", "tai_khoan": "Tố Khuyên"}, None)
    check("Trang không thuộc tài khoản được chỉ định → ERROR", err and err.startswith("ERROR"), err)

    out = json.loads(await pg._publish({"page": "MeiMei Design", "message": "xin chào"}, None))
    check("đăng bài từ Google Sheet: tự chọn đúng token Trang B và báo tài khoản đã dùng",
          posts[-1] == ("B/feed", "PT_B") and out["tai_khoan"] == "Khang - HB Vũ", (posts[-1], out))
    out = json.loads(await pg._publish({"page": "Melya Avenue", "message": "chào"}, None))
    check("đăng Trang C: đúng token Tố Khuyên", posts[-1] == ("C/feed", "PT_C") and out["tai_khoan"] == "Trung - Tố Khuyên")

    # Một tài khoản hết hạn token không được làm chết tài khoản kia
    async def tok_loi(cid):
        return None if cid == "c_tk" else UTOK[cid]
    pg._token_of = tok_loi
    r2 = json.loads(await pg._list({}, None))
    check("một tài khoản mất token: tài khoản còn lại vẫn liệt kê được", {p["id"] for p in r2} == {"A", "B"}, r2)
    pg._token_of = tok_of

    # ---------------- Meta Ads ----------------
    ad = nap("meta-ads-graph")
    ad._conns = lambda: list(CONNS)
    ad._token_of = tok_of
    seen = {}
    async def aget(path, params, token):
        seen["last"] = (path, token)
        if path == "me/adaccounts":
            return {"data": ADS[token]}
        if path.endswith("/insights"):
            return {"data": [{"spend": "1"}]}
        return {"data": []}
    ad._get = aget
    r = json.loads(await ad._accounts({}, None))["data"]
    byid = {a["account_id"]: a for a in r}
    check("meta_ads_accounts: gộp 111/222/333 của cả hai tài khoản", set(byid) == {"111", "222", "333"})
    check("meta_ads_accounts: tài khoản quảng cáo dùng chung BM hiện MỘT dòng, ghi cả hai người quản lý",
          len(byid["222"]["tai_khoan"]) == 2 and byid["333"]["tai_khoan"] == ["Trung - Tố Khuyên"])
    await ad._insights({"account_id": "333"}, None)
    check("insights act_333 (chỉ Tố Khuyên thấy) dùng token của Tố Khuyên", seen["last"] == ("act_333/insights", "U_TK"), seen["last"])
    await ad._insights({"account_id": "act_111"}, None)
    check("insights act_111 dùng token HB Vũ", seen["last"] == ("act_111/insights", "U_HB"), seen["last"])
    await ad._insights({"account_id": "222"}, None)
    check("act_222 cả hai thấy: dùng tài khoản mặc định", seen["last"][1] == "U_HB")
    await ad._insights({"account_id": "222", "tai_khoan": "Tố Khuyên"}, None)
    check("chỉ định tai_khoan cho act_222", seen["last"][1] == "U_TK")
    bad = await ad._insights({"account_id": "222", "tai_khoan": "Ai đó"}, None)
    check("tai_khoan lạ → ERROR", bad.startswith("ERROR"), bad)

    # Phân trang: 50+ tài khoản quảng cáo của BM
    big = [{"account_id": str(1000 + i), "name": f"TK {i}"} for i in range(330)]
    async def aget_big(path, params, token):
        if path == "me/adaccounts":
            start = int(params.get("after") or 0)
            chunk = big[start:start + 200]
            nxt = start + 200
            pgn = {"cursors": {"after": str(nxt)}, "next": "x"} if nxt < len(big) else {}
            return {"data": chunk, "paging": pgn}
        return {"data": []}
    ad._get = aget_big
    rows, e = await ad._all_adaccounts("U_HB")
    check("phân trang me/adaccounts: lấy đủ 330 tài khoản quảng cáo", len(rows) == 330 and not e, len(rows or []))

asyncio.run(chay())
if _fails:
    print(f"\nFAIL - {len(_fails)} test: {_fails}")
    sys.exit(1)
print("\nOK - test_meta_nhieu_tai_khoan: tất cả pass")
