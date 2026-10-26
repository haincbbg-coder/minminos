"""Bật/tắt chiến dịch Facebook có bước duyệt (26.10.252). Không mạng: giả kết nối, token, Graph.

Phủ: đề xuất KHÔNG đổi gì; chọn đúng tài khoản Facebook cho từng tài khoản quảng cáo; thẻ không lộ token;
duyệt chạy đúng một lần (kể cả bấm hai lần cùng lúc); đọc lại trạng thái; lỗi quyền gợi ý Soi quyền;
từ chối / hết hạn không chạy; hoàn tác; chặn khi chính sách "tiền" = chặn; nút Telegram; plugin trả thẻ.

    python tests/run.py meta_ads_duyet
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-adsduyet-"))
sys.path.insert(0, str(SERVER))
import meta_tai_san as mts  # noqa: E402
import meta_ads_duyet as mad  # noqa: E402

_fails = []


def check(n, c, extra=None):
    print(("ok   " if c else "FAIL ") + n + ("" if c or extra is None else f"  [{extra}]"))
    if not c:
        _fails.append(n)


CONNS = [{"id": "c_tk", "connector_id": "meta-ads-graph", "label": "Trung - Tố Khuyên", "is_default": True},
         {"id": "c_hb", "connector_id": "meta-ads-graph", "label": "Khang - HB Vũ", "is_default": False}]
TOK = {"c_tk": "U_TK", "c_hb": "U_HB"}
# Chiến dịch C1 thuộc TKQC 111 (chỉ Trung thấy); C2 thuộc 222 (cả hai thấy, chỉ Khang có quyền ghi).
OBJ = {"1201": {"id": "1201", "name": "Melya Lady - Đầm lụa", "status": "ACTIVE", "effective_status": "ACTIVE",
              "account_id": "111", "metadata": {"type": "campaign"}, "daily_budget": "300000"},
       "1202": {"id": "1202", "name": "Nguyễn Phạm - Bộ đồ ngủ", "status": "PAUSED", "effective_status": "PAUSED",
              "account_id": "222", "metadata": {"type": "campaign"}, "daily_budget": "800000"},
       "1203": {"id": "1203", "name": "Đã tắt sẵn", "status": "PAUSED", "effective_status": "PAUSED",
              "account_id": "111", "metadata": {"type": "campaign"}}}
THAY = {"U_TK": {"1201", "1203", "1202"}, "U_HB": {"1202"}}
posts = []
TU_CHOI_GHI = set()


async def fhttp(path, params, token):
    if path == "me":
        return {"id": {"U_TK": "100", "U_HB": "200"}[token], "name": token}
    if path == "debug_token":
        return {"data": {"application": "app", "expires_at": 0, "is_valid": True}}
    if path == "me/permissions":
        perms = ["ads_read", "business_management"] + (["ads_management"] if token == "U_HB" else [])
        return {"data": [{"permission": p, "status": "granted"} for p in perms]}
    if path == "me/accounts" or path == "me/businesses":
        return {"data": []}
    if path == "me/adaccounts":
        rows = {"U_TK": [{"account_id": "111", "name": "HALIMI 07"}, {"account_id": "222", "name": "HALIMI 12"}],
                "U_HB": [{"account_id": "222", "name": "HALIMI 12", "user_tasks": ["ADVERTISE"]}]}[token]
        return {"data": rows}
    if path.endswith("/insights"):
        return {"data": [{"spend": "1250000"}]}
    if path.startswith("act_"):
        return {"name": "TKQC " + path}
    oid = path
    if oid in OBJ:
        if oid not in THAY.get(token, set()):
            return {"error": {"message": "Unsupported get request.", "code": 100}}
        return dict(OBJ[oid])
    return {"error": {"message": "nope", "code": 100}}


async def fpost(path, data, token):
    posts.append((path, data.get("status"), token))
    await asyncio.sleep(0.01)
    if (path, token) in TU_CHOI_GHI:
        return {"error": {"message": "(#200) Ad account owner has NOT grant ads_management", "code": 200}}
    OBJ[path]["status"] = data["status"]
    OBJ[path]["effective_status"] = data["status"]
    return {"success": True}


async def ftoken(cid):
    return TOK.get(cid)


async def chay():
    mts.dat_ket_noi(lambda: list(CONNS))
    mts.dat_token(ftoken)
    mts.dat_http(fhttp)
    mts.xoa_dem()
    mad.dat_duong(os.path.join(os.environ["JAVIS_STATE_DIR"], "duyet.json"))
    mad.dat_post(fpost)
    mad.dat_chinh_sach(lambda: {})
    tg = []

    async def ftg(chat, text, rm):
        tg.append((chat, text, rm))
        return True
    mad.dat_gui_telegram(ftg)

    v = await mad.tao([{"id": "1201", "trang_thai": "tat"}, {"id": "1202", "trang_thai": "bat"}], chat="web:abc")
    check("tạo đề xuất ok, trạng thái cho", v["ok"] and v["trang_thai"] == "cho", v)
    check("đề xuất KHÔNG đổi gì trên Facebook", posts == [])
    m = {x["id"]: x for x in v["muc"]}
    check("C1 (TKQC 111) dùng Trung", m["1201"]["fb_id"] == "100" and m["1201"]["fb_ten"] == "Trung - Tố Khuyên", m["1201"])
    check("C2 (TKQC 222) dùng Khang, người có quyền ghi, dù Trung là mặc định",
          m["1202"]["fb_id"] == "200", m["1202"])
    check("đọc chi hôm nay + ngân sách ngày", m["1201"]["chi_hom_nay"] == 1250000 and m["1201"]["ngan_sach_ngay"] == 300000)
    check("trước -> sau đúng", m["1201"]["tu"] == "ACTIVE" and m["1201"]["sang"] == "PAUSED" and m["1202"]["sang"] == "ACTIVE")
    check("thẻ không lộ token / conn_id", "U_TK" not in json.dumps(v) and "conn_id" not in json.dumps(v))
    check("chat web: không gửi Telegram", tg == [] and v["da_gui_telegram"] is False)

    a, b = await asyncio.gather(mad.quyet(v["id"], "duyet", ai="chủ"), mad.quyet(v["id"], "duyet", ai="chủ"))
    check("bấm Duyệt hai lần cùng lúc: chỉ chạy MỘT lần", len(posts) == 2, posts)
    check("C1 tắt bằng token Trung, C2 bật bằng token Khang",
          ("1201", "PAUSED", "U_TK") in posts and ("1202", "ACTIVE", "U_HB") in posts, posts)
    x = mad.xem(v["id"])
    check("sau duyệt: xong, đổi 2/2", x["trang_thai"] == "xong" and x["thong_bao"] == "Đã đổi 2/2.", x)
    check("có thể hoàn tác", x["co_the_hoan_tac"] is True)
    again = await mad.quyet(v["id"], "duyet")
    check("duyệt lại đề xuất đã xong: không chạy nữa", len(posts) == 2 and "xử lý rồi" in again["thong_bao"])

    ht = await mad.quyet(v["id"], "hoan_tac", ai="chủ")
    check("hoàn tác: đưa C1 về ACTIVE, C2 về PAUSED",
          posts[-2:] in ([("1201", "ACTIVE", "U_TK"), ("1202", "PAUSED", "U_HB")],
                         [("1202", "PAUSED", "U_HB"), ("1201", "ACTIVE", "U_TK")]) and ht["da_hoan_tac"], posts[-2:])
    check("hoàn tác lần hai: không được", (await mad.quyet(v["id"], "hoan_tac"))["thong_bao"].startswith("Không hoàn tác"))

    v2 = await mad.tao([{"id": "1201", "trang_thai": "tat"}])
    n = len(posts)
    r = await mad.quyet(v2["id"], "tu_choi")
    check("từ chối: không đổi gì", len(posts) == n and r["trang_thai"] == "tu_choi")
    r = await mad.quyet(v2["id"], "duyet")
    check("duyệt sau khi đã từ chối: không chạy", len(posts) == n and "từ chối" in r["thong_bao"])

    v3 = await mad.tao([{"id": "1201", "trang_thai": "tat"}])
    kho = mad._doc_kho()
    kho[v3["id"]]["het_han_ts"] = time.time() - 1
    mad._ghi_kho(kho)
    r = await mad.quyet(v3["id"], "duyet")
    check("đề xuất quá 30 phút: hết hạn, không chạy", len(posts) == n and r["trang_thai"] == "het_han", r)

    v4 = await mad.tao([{"id": "1203", "trang_thai": "tat"}])
    check("đối tượng đã đúng trạng thái: đánh dấu không đổi", v4["muc"][0]["khong_doi"] is True)
    await mad.quyet(v4["id"], "duyet")
    check("duyệt mục không đổi: không gọi Facebook", len(posts) == n)

    mad.dat_chinh_sach(lambda: {"tien": "chan"})
    v5 = await mad.tao([{"id": "1201", "trang_thai": "tat"}])
    r = await mad.quyet(v5["id"], "duyet")
    check("chính sách tiền = chặn: không chạy, báo lý do", len(posts) == n and r["thong_bao"].startswith("Không chạy"), r)
    mad.dat_chinh_sach(lambda: {})

    TU_CHOI_GHI.add(("1201", "U_TK"))
    v6 = await mad.tao([{"id": "1201", "trang_thai": "tat"}])
    r = await mad.quyet(v6["id"], "duyet")
    check("Facebook từ chối vì thiếu quyền: trạng thái loi, gợi ý Soi quyền",
          r["trang_thai"] == "loi" and "Soi quyền" in r["ket_qua"][0]["loi"], r)
    TU_CHOI_GHI.clear()

    v7 = await mad.tao([{"id": "1201", "trang_thai": "tat"}], chat="123456789")
    check("chat Telegram: gửi tin có nút fa:<id>:d / fa:<id>:t",
          tg and tg[-1][0] == "123456789" and tg[-1][2]["inline_keyboard"][0][0]["callback_data"] == f"fa:{v7['id']}:d", tg[-1:])
    check("tin Telegram ghi rõ tên, tài khoản Facebook, 'Chưa đổi gì'",
          "Melya Lady" in tg[-1][1] and "Trung - Tố Khuyên" in tg[-1][1] and "Chưa đổi gì" in tg[-1][1])
    n = len(posts)
    r = await mad.tg_callback(f"fa:{v7['id']}:d", ai="tg:123")
    check("bấm Duyệt trên Telegram: đổi thật, nguồn telegram", len(posts) == n + 1 and "Đã đổi 1/1" in r["text"]
          and mad.xem(v7["id"])["nguon_quyet"] == "telegram", r)
    check("callback lạ -> None", await mad.tg_callback("gv:abc:d") is None)

    r = await mad.tao([{"id": "1999", "trang_thai": "tat"}])
    check("mã không ai đọc được: ok False", r["ok"] is False)
    r = await mad.tao([{"id": "1201", "trang_thai": "chay"}])
    check("trang_thai sai: ok False", r["ok"] is False)
    r = await mad.quyet("khongco", "duyet")
    check("đề xuất không tồn tại: ok False", r["ok"] is False)

    # ---- plugin ----
    spec = importlib.util.spec_from_file_location("t_ads_duyet_plugin", str(ROOT / "system" / "plugins" / "meta-ads-graph" / "plugin.py"))
    pl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pl)

    class Ctx:
        def __init__(self):
            self.t = {}

        def register_tool(self, name, description, handler, schema=None, min_mode="readonly", check_fn=None, **k):
            self.t[name] = {"min_mode": min_mode, "handler": handler}
    ctx = Ctx()
    pl.register(ctx)
    check("plugin: meta_ads_tim readonly, meta_ads_de_xuat_trang_thai safe",
          ctx.t["meta_ads_tim"]["min_mode"] == "readonly" and ctx.t["meta_ads_de_xuat_trang_thai"]["min_mode"] == "safe")
    n = len(posts)
    out = json.loads(await pl._de_xuat({"muc": [{"id": "1202", "trang_thai": "tat"}]}, None))
    check("plugin đề xuất: trả dòng thẻ JAVIS_CARD duyet_ads, không đổi gì",
          out["THE_DUYET"].startswith("<!-- JAVIS_CARD:") and '"duyet_ads"' in out["THE_DUYET"] and len(posts) == n, out)
    out = await pl._de_xuat({"muc": "không phải json"}, None)
    check("plugin đề xuất: tham số hỏng -> ERROR", out.startswith("ERROR"))

    pl._conns = lambda: [{"id": c["id"], "label": c["label"], "is_default": c["is_default"]} for c in CONNS]
    pl._token_of = ftoken
    seen = []

    async def pget(path, params, token):
        seen.append((path, params, token))
        if path == "me/adaccounts":
            return {"data": [{"account_id": "111", "name": "HALIMI 07"}, {"account_id": "222", "name": "HALIMI 12"}]
                    if token == "U_TK" else [{"account_id": "222", "name": "HALIMI 12"}]}
        if path.endswith("/campaigns"):
            f = json.loads(params.get("filtering") or "[]")
            q = f[0]["value"].lower() if f else ""
            aid = path.split("/")[0].replace("act_", "")
            return {"data": [{"id": o["id"], "name": o["name"], "status": o["status"], "effective_status": o["effective_status"]}
                             for o in OBJ.values() if o["account_id"] == aid and q in o["name"].lower()]}
        return {"data": []}
    pl._get = pget
    r = json.loads(await pl._tim({"q": "melya"}, None))
    check("meta_ads_tim: tìm trên mọi TKQC, mỗi TKQC quét một lần", r["so"] == 1 and r["data"][0]["id"] == "1201"
          and r["da_quet_tkqc"] == 2, r)
    check("meta_ads_tim: lọc ngay ở Facebook bằng CONTAIN",
          any('"CONTAIN"' in str(p[1].get("filtering", "")) for p in seen))


asyncio.run(chay())
print("\n" + ("TẤT CẢ OK" if not _fails else f"{len(_fails)} LỖI: {_fails}"))
sys.exit(1 if _fails else 0)
