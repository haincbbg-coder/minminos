"""Kênh Zalo OA của Chatbot (26.10.314, server/zalo_oa_kenh.py + channels/zalo_oa.py + routes/zalo_oa.py). Không mạng.

    python tests/run.py zalo_oa_kenh

Phủ: tách bốn thứ chủ dán; liên kết tạo MỘT kết nối zalo-oa ở trang Kết nối (không kho token thứ hai), lưu cặp
token mới ngay và chuỗi lưu ở tài khoản kênh không chứa bí mật; Kiểm tra lần hai không đổi lại refresh token đã
chết; refresh hỏng thì xoá kết nối vừa tạo; cùng OA thì dồn về kết nối cũ; spec cũ của công cụ MCP đọc lại kho
trong khoá; kho mcp_store ghi nguyên tử; chữ ký webhook (cả hai công thức, sai khoá, sai app); giao sự kiện cho
bot đúng OA; gửi tin tư vấn chữ trơn và cắt tin dài; mã lỗi -230 nói thành lời; mã xác thực tên miền; route
webhook công khai còn route khác vẫn phải đăng nhập.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import hashlib
import hmac
import json
import os
import tempfile
import time

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-zalo-oa-kenh-"))

from _gia_http import GiaHttp, KiemTra  # noqa: E402
import mcp_store  # noqa: E402
import zalo_oa_kenh as zk  # noqa: E402
import zalo_oa_mcp  # noqa: E402
import channels  # noqa: E402

check = KiemTra()
OAUTH = "oauth.zaloapp.com/v4/oa/access_token"
RT = "R" * 80
DAN = f"4455667788 appsecretABC123 oasecretXYZ789 {RT}"


def chay(c):
    return asyncio.run(c)


def oa_ket_noi():
    return [c for c in mcp_store.list_connections() if c["connector_id"] == "zalo-oa"]


# ---- 1. tách chuỗi chủ dán ----
cr = zk.tach(DAN)
check("tách bốn thứ theo hình và thứ tự", cr == {"app_id": "4455667788", "app_secret": "appsecretABC123",
                                                 "oa_secret": "oasecretXYZ789", "refresh_token": RT}, cr)
cr2 = zk.tach(f"oa_secret=oasecretXYZ789, 4455667788\napp_secret=appsecretABC123 {RT}")
check("ghi tên thì đọc theo tên, nhận phẩy và xuống dòng", cr2 == cr, cr2)
check("dạng lưu chỉ có id kết nối", zk.tach(zk.chuoi_luu("abc")) == {"ket_noi": "abc"})

# ---- 2. liên kết: một kết nối zalo-oa, cặp token mới lưu ngay ----
gia = GiaHttp().lap()
gia.tra(OAUTH, {"access_token": "AT-MOI-1111111", "refresh_token": "RT-MOI-1111111", "expires_in": "90000"})
gia.tra("/v2.0/oa/getoa", {"error": 0, "data": {"oa_id": "777", "name": "HALIMI"}})
r = chay(channels.module("zalo_oa").verify_token(DAN))
check("Kiểm tra trả mã OA và tên", r.get("ok") and r["username"] == "777" and r["bot_name"] == "HALIMI", r)
ds = oa_ket_noi()
check("tạo đúng một kết nối Zalo OA ở trang Kết nối", len(ds) == 1, ds)
cid = ds[0]["id"]
sec = mcp_store.connection_secrets(cid)
check("cặp token mới đã nằm trong kết nối", sec.get("access_token") == "AT-MOI-1111111"
      and sec.get("refresh_token") == "RT-MOI-1111111" and float(sec.get("token_het_han")) > time.time())
check("OA secret key và mã OA lưu ở kết nối", sec.get("oa_secret") == "oasecretXYZ789" and sec.get("oa_id") == "777")
check("kết nối mới mặc định Chỉ đọc (công cụ gửi tin không tự mở)", ds[0]["perm"] == "readonly", ds[0]["perm"])
check("tên kết nối theo tên OA", ds[0]["label"] == "Zalo OA HALIMI", ds[0]["label"])
luu = channels.module("zalo_oa").token_luu(DAN, "777")
check("tài khoản kênh chỉ lưu id kết nối, không bí mật",
      json.loads(luu) == {"ket_noi": cid} and "secret" not in luu and RT not in luu, luu)

n_doi = len([g for g in gia.goi if OAUTH in g["url"]])
r2 = chay(zk.lien_ket(DAN))
check("Kiểm tra lần hai dùng lại kết nối, không đổi refresh token đã chết",
      r2.get("ok") and r2["ket_noi"] == cid and len([g for g in gia.goi if OAUTH in g["url"]]) == n_doi, r2)
check("vẫn một kết nối", len(oa_ket_noi()) == 1)

# ---- 3. chỉ ba thứ: dùng refresh token của kết nối có sẵn cùng App ID ----
r3 = chay(zk.lien_ket("4455667788 appsecretABC123 oasecretXYZ789"))
check("thiếu refresh token mà đã có kết nối cùng App ID thì dùng nó", r3.get("ok") and r3["ket_noi"] == cid, r3)
check("thiếu OA secret key thì báo rõ", "OA secret key" in chay(zk.lien_ket("4455667788 appsecretABC123")).get("error", ""))

# ---- 4. refresh hỏng: không để lại kết nối rác ----
gia2 = GiaHttp().lap()
gia2.tra(OAUTH, {"error": -14014, "error_description": "Invalid refresh token"})
r4 = chay(zk.lien_ket(f"5556667778 appsecretDEF456 oasecretUVW123 {'Q' * 80}"))
check("refresh hỏng báo lời rõ", not r4.get("ok") and "refresh token" in r4.get("error", "").lower(), r4)
check("refresh hỏng xoá kết nối vừa tạo", len(oa_ket_noi()) == 1)

# ---- 5. cùng OA, refresh token mới: dồn về kết nối cũ ----
gia3 = GiaHttp().lap()
gia3.tra(OAUTH, {"access_token": "AT-MOI-2222222", "refresh_token": "RT-MOI-2222222", "expires_in": "90000"})
gia3.tra("/v2.0/oa/getoa", {"error": 0, "data": {"oa_id": "777", "name": "HALIMI"}})
r5 = chay(zk.lien_ket(f"4455667788 appsecretABC123 oasecretXYZ789 {'S' * 80}"))
check("OA đã có kết nối: dồn cặp mới về kết nối cũ", r5.get("ok") and r5["ket_noi"] == cid and len(oa_ket_noi()) == 1, r5)
check("kết nối cũ mang refresh token mới nhất", mcp_store.connection_secrets(cid).get("refresh_token") == "RT-MOI-2222222")

# ---- 6. spec cũ của công cụ MCP đọc lại kho trong khoá ----
cu = {"key": cid, "secrets": {**mcp_store.connection_secrets(cid), "refresh_token": "RT-DA-CHET", "token_het_han": "1"}}
gia4 = GiaHttp().lap()
gia4.tra(OAUTH, {"access_token": "AT-MOI-3333333", "refresh_token": "RT-MOI-3333333", "expires_in": "90000"})
mcp_store.update_connection(cid, {"fields": {"token_het_han": "1"}})
loi = chay(zalo_oa_mcp.dam_bao_token(cu))
gui_rt = [g["data"].get("refresh_token") for g in gia4.goi if OAUTH in g["url"]]
check("làm mới bằng refresh token MỚI NHẤT trong kho, không phải bản chụp cũ", loi is None and gui_rt == ["RT-MOI-2222222"],
      (loi, gui_rt))
check("mcp_store ghi nguyên tử, không để file tạm", not (mcp_store.STORE.with_name(mcp_store.STORE.name + ".tmp")).exists())

# ---- 7. chữ ký webhook ----
than = json.dumps({"app_id": "4455667788", "timestamp": "1730000000", "event_name": "user_send_text",
                   "sender": {"id": "u1"}, "recipient": {"id": "777"}, "message": {"msg_id": "m1", "text": "hi"}}).encode()
ky = hashlib.sha256(("4455667788" + than.decode() + "1730000000" + "oasecretXYZ789").encode()).hexdigest()
cap = zk.cap_khoa_webhook()
check("khoá webhook lấy từ kết nối", ("4455667788", "oasecretXYZ789") in cap, cap)
check("chữ ký theo tài liệu Zalo khớp", zk.hop_le_chu_ky(than, "mac=" + ky, cap))
check("chữ ký HMAC thân tin cũng nhận", zk.hop_le_chu_ky(than, hmac.new(b"oasecretXYZ789", than, hashlib.sha256).hexdigest(), cap))
check("sai khoá bị từ chối", not zk.hop_le_chu_ky(than, "mac=" + ky, [("4455667788", "khac")]))
check("app khác bị từ chối", not zk.hop_le_chu_ky(than, "mac=" + ky, [("999", "oasecretXYZ789")]))
check("thiếu chữ ký bị từ chối", not zk.hop_le_chu_ky(than, "", cap))
check("thân sửa một chữ bị từ chối", not zk.hop_le_chu_ky(than.replace(b"hi", b"ho"), "mac=" + ky, cap))

# ---- 8. bot trực OA: nhận sự kiện, trả lời chữ trơn ----
gia5 = GiaHttp().lap()
gia5.tra("/v2.0/oa/getoa", {"error": 0, "data": {"oa_id": "777", "name": "HALIMI"}})
gia5.tra("/v3.0/oa/user/detail", {"error": 0, "data": {"display_name": "Chị Lan"}})
gia5.tra("/v3.0/oa/message/cs", {"error": 0, "data": {"message_id": "x"}})
mcp_store.update_connection(cid, {"fields": {"token_het_han": str(time.time() + 99999)}})
nhan = []


async def tra_loi(text, meta=None, progress=None):
    nhan.append((text, meta))
    return "Dạ **85.000đ** ạ\n- ship nhanh"


async def chay_bot():
    bot = channels.module("zalo_oa").Transport(zk.chuoi_luu(cid), "", tra_loi, giau_trang_thai=True)
    bot.start()
    for _ in range(50):
        await asyncio.sleep(0.01)
        if bot.status == "polling":
            break
    n = await zk.nhan_webhook(json.loads(than))
    n_lap = await zk.nhan_webhook(json.loads(than))     # Zalo gửi lại cùng tin
    n_oa_khac = await zk.nhan_webhook({**json.loads(than), "recipient": {"id": "888"}})
    n_oa_gui = await zk.nhan_webhook({**json.loads(than), "event_name": "oa_send_text"})
    for _ in range(100):
        await asyncio.sleep(0.01)
        if any("/message/cs" in g["url"] for g in gia5.goi):
            break
    trang_thai = (bot.status, dict(zk.dang_truc()))
    bot.stop()
    return n, n_lap, n_oa_khac, n_oa_gui, trang_thai, dict(zk.dang_truc())


n, n_lap, n_khac, n_gui, tt, sau = chay(chay_bot())
check("bot trực đúng OA", tt[0] == "polling" and "777" in tt[1], tt)
check("giao sự kiện cho bot của OA", n == 1 and n_khac == 0 and n_gui == 0, (n, n_khac, n_gui))
check("tin trùng chỉ trả lời một lần", len(nhan) == 1, nhan)
check("meta mang tên khách và chat riêng", nhan and nhan[0][1]["user_name"] == "Chị Lan"
      and nhan[0][1]["chat_type"] == "private" and nhan[0][0] == "hi")
cs = [g for g in gia5.goi if "/message/cs" in g["url"]]
check("trả lời bằng tin tư vấn, chữ trơn không dấu Markdown",
      cs and cs[0]["json"] == {"recipient": {"user_id": "u1"}, "message": {"text": "Dạ 85.000đ ạ\n• ship nhanh"}},
      cs and cs[0]["json"])
check("tắt bot thì rời sổ trực", "777" not in sau)
check("cắt tin dài theo trần Zalo", all(len(x) <= zk.TIN_TOI_DA for x in zk._cat("a " * 3000)) and len(zk._cat("a " * 3000)) > 2)

# ---- 9. lỗi -230 nói thành lời, gửi từ Hộp thư ----
gia6 = GiaHttp().lap()
gia6.tra("/v3.0/oa/message/cs", {"error": -230, "message": "User has not interacted"})
ok, loi = chay(channels.module("zalo_oa").gui({"token": zk.chuoi_luu(cid)}, "u1", "chào"))
check("ngoài khung tư vấn: báo lời dễ hiểu", not ok and "lâu không nhắn" in loi and "-230" in loi, loi)
check("tài khoản chưa liên kết thì báo", chay(channels.module("zalo_oa").gui({}, "u1", "x"))[0] is False)

# ---- 10. mã xác thực tên miền ----
check("đọc mã từ tên file", zk.doc_ma_xac_thuc("zalo_verifierAbC123xyz.html") == "AbC123xyz")
check("đọc mã từ thẻ meta", zk.doc_ma_xac_thuc('<meta name="zalo-platform-site-verification" content="QWE123456" />') == "QWE123456")
check("chuỗi lạ không thành mã", zk.doc_ma_xac_thuc("<script>") == "")
zk.luu_ma_xac_thuc("AbC123xyz")
check("mã đã lưu", zk.ma_xac_thuc() == ["AbC123xyz"])
check("file xác thực mang đúng mã", 'content="AbC123xyz"' in zk.html_xac_thuc("AbC123xyz"))

# ---- 11. route: webhook công khai, phần khác vẫn phải đăng nhập ----
import main  # noqa: E402
import routes.zalo_oa as zr  # noqa: E402
paths = {(r.path, tuple(sorted(getattr(r, "methods", []) or []))) for r in zr.router.routes}
check("có route webhook, thông tin webhook, lưu mã, file xác thực",
      {("/zalo-oa/webhook", ("POST",)), ("/zalo-oa/webhook-info", ("GET",)), ("/zalo-oa/xac-thuc", ("POST",))} <= paths
      and any(p == "/zalo_verifier{ma}.html" for p, _ in paths))
check("chỉ POST webhook được miễn đăng nhập", main._ZALO_OA_CONG_KHAI == (("/zalo-oa/webhook", "POST"),))
check("đường file xác thực khớp chặt", main._ZALO_OA_XAC_THUC_RE.fullmatch("/zalo_verifierAbC123xyz.html")
      and not main._ZALO_OA_XAC_THUC_RE.fullmatch("/zalo_verifier../x.html")
      and not main._ZALO_OA_XAC_THUC_RE.fullmatch("/zalo_verifierAbC123xyz.html/x"))

check.ket_thuc()
