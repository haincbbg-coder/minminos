"""Facebook nhiều tài khoản - soi quyền (26.10.252): gom Trang / tài khoản quảng cáo của mọi tài khoản
Facebook đã nối, chỉ ra cái gì Facebook chưa giao cho MinMin và vì sao, hỏi Facebook về một Trang.
Không mạng: giả kết nối, token và Graph.

    python tests/run.py meta_tai_san
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import sys
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-metats-"))
sys.path.insert(0, str(SERVER))
import meta_tai_san as mts  # noqa: E402

_fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        _fails.append(n)


CONNS = [{"id": "c_tk", "connector_id": "facebook-pages", "label": "Trung - Tố Khuyên", "is_default": True},
         {"id": "c_tk_ads", "connector_id": "meta-ads-graph", "label": "Trung ads", "is_default": False},
         {"id": "c_hb", "connector_id": "facebook-pages", "label": "Khang - HB Vũ", "is_default": False},
         {"id": "c_chet", "connector_id": "facebook-pages", "label": "Nick chết", "is_default": False}]
TOK = {"c_tk": "U_TK", "c_tk_ads": "U_TK2", "c_hb": "U_HB", "c_chet": "U_DEAD"}
ME = {"U_TK": {"id": "100", "name": "Trung"}, "U_TK2": {"id": "100", "name": "Trung"},
      "U_HB": {"id": "200", "name": "Khang"}}
PERMS = {"U_TK": ["pages_show_list", "pages_manage_posts", "pages_read_engagement", "business_management"],
         "U_TK2": ["ads_read", "business_management"],
         "U_HB": ["pages_show_list", "pages_manage_posts", "pages_read_engagement", "pages_manage_engagement",
                  "ads_read", "ads_management", "business_management"]}
# Trang qua me/accounts. P1 cả hai cầm; P2 chỉ Trung (biên tập, cá nhân); P3 chỉ Khang, thuộc BM;
# P4 Trung chỉ là phân tích viên (không đăng được).
ACC = {"U_TK": [{"id": "P1", "name": "Melya Lady", "tasks": ["MANAGE", "CREATE_CONTENT"]},
                {"id": "P2", "name": "Melya Avenue", "tasks": ["CREATE_CONTENT", "MODERATE"]},
                {"id": "P4", "name": "Phân tích thôi", "tasks": ["ANALYZE"]}],
       "U_HB": [{"id": "P1", "name": "Melya Lady", "tasks": ["CREATE_CONTENT"]},
                {"id": "P3", "name": "Nguyễn Phạm", "tasks": ["MANAGE"]}]}
ADS = {"U_TK2": [{"account_id": "111", "name": "HALIMI 07", "business": {"name": "BM Halimi"}, "user_tasks": ["MANAGE"]}],
       "U_HB": [{"account_id": "222", "name": "HALIMI 12", "business": {"name": "BM Halimi"}, "user_tasks": ["ADVERTISE"]},
                {"account_id": "333", "name": "Cá nhân Khang", "user_tasks": ["ANALYZE"]}]}
BIZ = {"U_TK": [{"id": "B1", "name": "BM Halimi"}], "U_TK2": [{"id": "B1", "name": "BM Halimi"}],
       "U_HB": [{"id": "B1", "name": "BM Halimi"}]}
BM_PAGES = {"B1/owned_pages": [{"id": "P1", "name": "Melya Lady"}, {"id": "P3", "name": "Nguyễn Phạm"},
                               {"id": "P9", "name": "Hoa Trà Boutique"}],
            "B1/owned_ad_accounts": [{"account_id": "111", "name": "HALIMI 07"}, {"account_id": "222", "name": "HALIMI 12"},
                                     {"account_id": "999", "name": "HALIMI 99"}]}
# Trang lẻ hỏi theo ID
DIRECT = {"P2": {"id": "P2", "name": "Melya Avenue", "access_token": "PT2", "tasks": ["CREATE_CONTENT"]},
          "P4": {"id": "P4", "name": "Phân tích thôi", "access_token": "PT4", "tasks": ["ANALYZE"]},
          "P9": {"id": "P9", "name": "Hoa Trà Boutique"},
          "77777777": {"id": "77777777", "name": "Liora Belle"},
          "hoatra": {"id": "P9", "name": "Hoa Trà Boutique"}}
calls = []


async def fhttp(path, params, token):
    calls.append((path, token))
    if token == "U_DEAD":
        return {"error": {"message": "Error validating access token", "code": 190}}
    if str(path).startswith("http"):            # trang kế
        return {"data": [{"id": "P5", "name": "Trang lật trang", "tasks": ["MANAGE"]}]}
    if path == "me":
        return ME[token]
    if path == "debug_token":
        return {"data": {"application": "MinMin app", "expires_at": int(time.time()) + 52 * 86400, "is_valid": True}}
    if path == "me/permissions":
        return {"data": [{"permission": p, "status": "granted"} for p in PERMS.get(token, [])]
                + [{"permission": "ads_management", "status": "declined"}]}
    if path == "me/accounts":
        d = {"data": list(ACC.get(token, []))}
        if token == "U_TK":
            d["paging"] = {"next": "https://graph.facebook.com/next-page"}
        return d
    if path == "me/adaccounts":
        if token not in ADS:
            return {"error": {"message": "(#200) Requires ads_read", "code": 200}}
        return {"data": ADS[token]}
    if path == "me/businesses":
        return {"data": BIZ.get(token, [])}
    if path in BM_PAGES:
        return {"data": BM_PAGES[path]}
    if path.startswith("B1/"):
        return {"data": []}
    if path in DIRECT:
        return DIRECT[path]
    if path == "404404404":
        return {"error": {"message": "Unsupported get request.", "code": 100}}
    return {"error": {"message": "Unknown path " + path, "code": 100}}


async def ftoken(cid):
    return TOK.get(cid)


async def chay():
    mts.dat_ket_noi(lambda: list(CONNS))
    mts.dat_token(ftoken)
    mts.dat_http(fhttp)
    mts.xoa_dem()
    r = await mts.tai_san(lam_moi=True)
    s = json.dumps(r, ensure_ascii=False)
    check("không lộ token người dùng hay token Trang", "U_TK" not in s and "PT2" not in s and "access_token" not in s)
    tks = {t["fb_id"]: t for t in r["tai_khoan"]}
    check("gộp hai kết nối cùng một người (Trung Trang + Trung ads) thành MỘT tài khoản",
          "100" in tks and len(tks["100"]["ket_noi"]) == 2, list(tks))
    check("có 3 tài khoản: Trung, Khang, nick chết", len(tks) == 3, list(tks))
    chet = [t for t in r["tai_khoan"] if t["fb_id"].startswith("conn:")]
    check("nick token chết: trạng thái loi, không làm hỏng tài khoản khác",
          chet and chet[0]["token"]["trang_thai"] in ("loi", "het_han"), chet)
    check("token còn 52 ngày -> tot", tks["100"]["token"]["trang_thai"] == "tot" and tks["100"]["token"]["con_ngay"] in (51, 52))
    check("Trung thiếu quản lý quảng cáo -> báo trong thieu_quyen",
          any(q["ma"] == "ads_management" for q in tks["100"]["thieu_quyen"]))
    check("Khang đủ quyền", tks["200"]["thieu_quyen"] == [], tks["200"]["thieu_quyen"])

    pg = {p["id"]: p for p in r["trang"]}
    check("lật trang me/accounts: thấy Trang ở trang thứ hai", "P5" in pg)
    check("P1 hai người cầm: một dòng, hai nguồn", set(pg["P1"]["nguon"]) == {"100", "200"})
    check("P1 của Trung: quản trị viên qua BM Halimi",
          pg["P1"]["nguon"]["100"] == {"vai_tro": "quan_tri", "qua": "bm", "bm_ten": "BM Halimi", "giao": True})
    check("P2 Trung biên tập viên cá nhân", pg["P2"]["nguon"]["100"]["vai_tro"] == "bien_tap"
          and pg["P2"]["nguon"]["100"]["qua"] == "ca_nhan")
    check("P1 đăng bằng tài khoản mặc định (Trung)", pg["P1"]["dang_bang"] == "100")
    check("P3 đăng bằng Khang", pg["P3"]["dang_bang"] == "200")
    check("P4 phân tích viên: không đăng được, có vấn đề", pg["P4"]["dang_bang"] == "" and pg["P4"]["van_de"] == "chua_giao")
    check("P9 thấy qua BM nhưng chưa giao -> chua_giao, giao=False",
          pg["P9"]["van_de"] == "chua_giao" and pg["P9"]["nguon"]["100"]["giao"] is False)
    check("Trang có vấn đề xếp đầu bảng", r["trang"][0]["van_de"] != "")

    ad = {a["id"]: a for a in r["tkqc"]}
    check("111 (Trung, thiếu ads_management) -> thieu_quyen_ghi", ad["111"]["van_de"] == "thieu_quyen_ghi")
    check("222 Khang ADVERTISE + đủ quyền -> dùng Khang, không vấn đề", ad["222"]["dung"] == "200" and ad["222"]["van_de"] == "")
    check("333 Khang chỉ ANALYZE -> thiếu quyền ghi", ad["333"]["van_de"] == "thieu_quyen_ghi")
    check("333 cá nhân", ad["333"]["nguon"]["200"]["qua"] == "ca_nhan")
    check("999 thấy trong BM, chưa giao", ad["999"]["van_de"] == "chua_giao")

    n0 = len(calls)
    await mts.tai_san()
    check("đệm 120 giây: gọi lại không hỏi Facebook", len(calls) == n0)

    s = await mts.soi_quyen("100")
    check("soi quyền: ok + tên app", s["ok"] and s["ung_dung"] == "MinMin app")
    q = {x["ma"]: x for x in s["quyen"]}
    check("soi quyền: ads_management co=False kèm 'bật tắt camp'",
          q["ads_management"]["co"] is False and "bật tắt camp" in q["ads_management"]["de_lam"])
    ma = {(x["loai"], x["id"]): x for x in s["chua_giao"]}
    check("soi quyền: P9 chưa giao qua BM, nút đăng nhập lại", ma[("trang", "P9")]["ly_do_ma"] == "chua_giao_bm"
          and ma[("trang", "P9")]["nut"] == "dang_nhap_lai")
    check("soi quyền: P4 vai trò không đăng được", ma[("trang", "P4")]["ly_do_ma"] == "khong_dang")
    check("soi quyền: TKQC 111 thiếu quyền, nút cấp quyền", ma[("tkqc", "111")]["nut"] == "cap_quyen")
    check("soi quyền: đếm Trang chưa giao (P3 Trung không cầm + P9)", s["trang_chua_giao"] == 2, s["trang_chua_giao"])
    bad = await mts.soi_quyen("khong-co")
    check("soi quyền fb_id lạ -> ok False", bad["ok"] is False)

    h = await mts.hoi_trang("100", "Melya Avenue")
    check("hỏi theo tên đã biết -> giao", h["ket_qua"] == "giao" and h["id"] == "P2", h)
    h = await mts.hoi_trang("100", "https://www.facebook.com/hoatra")
    check("hỏi theo link slug, Trang trong BM chưa giao -> chua_giao_bm", h["ket_qua"] == "chua_giao_bm", h)
    h = await mts.hoi_trang("100", "77777777")
    check("hỏi theo ID, Facebook thấy Trang nhưng không giao -> khong_thay_quyen + tên Trang",
          h["ket_qua"] == "khong_thay_quyen" and h["ten"] == "Liora Belle", h)
    h = await mts.hoi_trang("100", "Liora Belle")
    check("hỏi theo tên MinMin chưa từng thấy -> can_id (không đoán)", h["ket_qua"] == "can_id", h)
    h = await mts.hoi_trang("100", "Melya")
    check("tên khớp nhiều Trang -> can_id", h["ket_qua"] == "can_id", h)
    h = await mts.hoi_trang("100", "404404404")
    check("ID sai -> khong_tim_thay + nguyên văn có mã lỗi", h["ket_qua"] == "khong_tim_thay" and "(100)" in h["nguyen_van"], h)
    h = await mts.hoi_trang("100", "P4")
    check("vai trò phân tích -> giao_khong_dang", h["ket_qua"] == "giao_khong_dang", h)
    h = await mts.hoi_trang("100", "https://facebook.com/profile.php?id=77777777")
    check("link profile.php?id= -> lấy đúng ID", h["id"] == "77777777", h)
    h = await mts.hoi_trang("100", "")
    check("ô trống -> can_id", h["ket_qua"] == "can_id")
    check("hỏi Trang không lộ token", "PT2" not in json.dumps(await mts.hoi_trang("100", "Melya Avenue")))

    check("tach_q: số", mts.tach_q("123456789") == ("id", "123456789"))
    check("tach_q: link pages/<tên>/<id>", mts.tach_q("facebook.com/pages/Abc/1234567") == ("id", "1234567"))
    check("tach_q: tên", mts.tach_q("Melya Lady") == ("ten", "Melya Lady"))


asyncio.run(chay())
print("\n" + ("TẤT CẢ OK" if not _fails else f"{len(_fails)} LỖI: {_fails}"))
sys.exit(1 if _fails else 0)
