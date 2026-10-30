"""Kênh Zalo OA của Chatbot (26.10.314): bot chuyên trách trả lời hộp thư Zalo Official Account.

Đọc theo Javis 0.412 (zalo_oa_bot.py), viết lại theo cách của MinMin. Khác lớn nhất: MinMin ĐÃ CÓ cầu nối
Zalo OA ở trang Kết nối (`zalo_oa_mcp`, kho token trong `mcp_store`, khoá làm mới theo kết nối). Kênh này
KHÔNG dựng kho token thứ hai. Một OA = một kết nối `zalo-oa`; tài khoản kênh chỉ giữ `{"ket_noi": <id>}`,
và mọi lần làm mới token đi qua `zalo_oa_mcp.dam_bao_token` (một khoá, đọc lại kho trong khoá, lưu cặp
mới ngay khi Zalo trả). Vì sao quan trọng: refresh token Zalo DÙNG MỘT LẦN. Hai kho cùng giữ một refresh
token thì bên nào đổi trước, bên kia cầm token chết và OA phải ủy quyền lại.

Luồng:
  - Chủ dán "App ID, App secret key, OA secret key, Refresh token" ở form Thêm kênh. `lien_ket` tìm hoặc tạo
    kết nối `zalo-oa`, làm mới token một lần (cặp mới ghi xuống kho ngay), đọc tên và mã OA. Đã có kết nối
    cùng App ID mang refresh token sẵn thì chỉ cần ba thứ đầu, không phải lấy refresh token mới.
  - Zalo POST mọi tin khách vào `/zalo-oa/webhook` (routes/zalo_oa.py). Route kiểm chữ ký bằng OA secret
    key rồi gọi `nhan_webhook`, hàm này chuyển sự kiện cho bot đang trực đúng OA đó.
  - Bot trả lời bằng "tin tư vấn" (`/v3.0/oa/message/cs`), chữ trơn (Zalo OA không hiện Markdown), cắt
    theo trần 2000 ký tự. Zalo chỉ cho tin tư vấn trong một khung thời gian sau tin cuối của khách.
  - Zalo bắt xác thực tên miền webhook bằng file `zalo_verifier<mã>.html`; MinMin phục vụ đúng các mã chủ lưu.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import mimetypes
import re
import sys
import time
from collections import deque
from pathlib import Path

from bot_gateway import HangLuot, dong_vet, parse_chat_ids, ten_tool

CONNECTOR = "zalo-oa"
KENH = "zalo_oa"
OPENAPI = "https://openapi.zalo.me"
TIN_TOI_DA = 1900               # Zalo nhận 2000 ký tự một tin; chừa lề
NHO_TOI_DA = 4000               # số mã tin nhớ để chống trùng (Zalo gửi lại webhook khi chậm trả lời)
TAI_TOI_DA_MB = 20
ANH_TOI_DA_MB = 1               # upload/image của Zalo
TEP_TOI_DA_MB = 5               # upload/file: chỉ pdf, doc, docx
MA_XAC_THUC_TOI_DA = 10

# oa_id -> bot đang trực OA đó
_TRUC: dict = {}


# ---------------------------------------------------------------- thông tin đăng nhập
def _van_tay(s: str) -> str:
    return hashlib.sha256(str(s or "").encode("utf-8")).hexdigest()[:32]


def tach(raw) -> dict:
    """Chuỗi tài khoản -> dict. Hai dạng:

    - Dạng lưu: JSON `{"ket_noi": "<id kết nối>"}` (MinMin tự ghi sau khi liên kết).
    - Dạng chủ dán: "<App ID> <App secret key> <OA secret key> <Refresh token>", cách nhau bằng dấu cách, phẩy
      hoặc xuống dòng. Nhận diện theo hình: App ID toàn số, refresh token là chuỗi dài, hai khoá ngắn lấy THEO
      THỨ TỰ (App secret trước). Viết `oa_secret=...` / `app_secret=...` thì đọc theo tên.
    """
    s = str(raw or "").strip()
    if s.startswith("{"):
        try:
            d = json.loads(s)
        except Exception:
            d = {}
        return {"ket_noi": str((d or {}).get("ket_noi") or "")} if isinstance(d, dict) else {}
    out = {"app_id": "", "app_secret": "", "oa_secret": "", "refresh_token": ""}
    ngan = []
    for phan in re.split(r"[\s,;|]+", s):
        if not phan:
            continue
        if "=" in phan[:24]:
            k, _, v = phan.partition("=")
            k = k.strip().lower().replace("-", "_")
            k = {"secret_key": "app_secret", "app_secret_key": "app_secret", "oa_secret_key": "oa_secret",
                 "refresh": "refresh_token"}.get(k, k)
            if k in out:
                out[k] = v.strip()
            continue
        if re.fullmatch(r"\d{6,25}", phan) and not out["app_id"]:
            out["app_id"] = phan
        elif len(phan) >= 60:
            out["refresh_token"] = phan
        elif re.fullmatch(r"[A-Za-z0-9_\-]{8,59}", phan):
            ngan.append(phan)
    for k in ("app_secret", "oa_secret"):
        if not out[k] and ngan:
            out[k] = ngan.pop(0)
    return out


def chuoi_luu(cid: str) -> str:
    return json.dumps({"ket_noi": str(cid)}, ensure_ascii=False)


def _ket_noi_oa() -> list:
    """Mọi kết nối Zalo OA ở trang Kết nối, kèm bí mật đã giải mã. Chỉ cho mã nội bộ."""
    import mcp_store
    out = []
    for c in mcp_store.list_connections():
        if c.get("connector_id") != CONNECTOR:
            continue
        out.append({"id": c["id"], "label": c.get("label") or "", "enabled": bool(c.get("enabled")),
                    "sec": mcp_store.connection_secrets(c["id"])})
    return out


def _spec(cid: str) -> dict:
    import mcp_store
    return {"key": str(cid), "secrets": mcp_store.connection_secrets(str(cid))}


def cap_khoa_webhook() -> list:
    """[(App ID, OA secret key)] của mọi kết nối Zalo OA có OA secret key: để kiểm chữ ký webhook."""
    try:
        return [(str(c["sec"].get("app_id") or ""), str(c["sec"]["oa_secret"]))
                for c in _ket_noi_oa() if str(c["sec"].get("oa_secret") or "").strip()]
    except Exception as e:
        print(f"[zalo-oa] đọc khoá webhook lỗi: {type(e).__name__}: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------- lỗi Zalo nói thành lời
_LOI = {
    -216: "access token Zalo OA không hợp lệ. MinMin đã thử làm mới; vẫn lỗi thì lấy refresh token mới rồi dán lại",
    -124: "access token Zalo OA đã hết hạn",
    -213: "người này chưa quan tâm OA hoặc đã bỏ quan tâm",
    -230: ("khách đã lâu không nhắn cho OA nên Zalo không cho gửi tin tư vấn nữa. Khách nhắn lại là mở lại "
           "khung trả lời"),
    -224: "gói dịch vụ của OA chưa cho dùng tính năng này qua API. Kiểm tra gói OA ở oa.zalo.me",
    -14029: "app trên developers.zalo.me chưa được duyệt hoặc chưa được cấp quyền cho OA này",
    -201: "tham số sai, thường là mã khách không thuộc OA này",
    -32: "vượt hạn mức gọi API của Zalo, thử lại sau",
}


def giai_thich(loi: str) -> str:
    """Câu lỗi của `zalo_oa_mcp` ("ERROR: Zalo -230: ...") -> câu chủ đọc hiểu được."""
    s = str(loi or "").strip()
    m = re.search(r"Zalo (-?\d+)", s)
    if m:
        try:
            ma = int(m.group(1))
        except ValueError:
            ma = None
        if ma in _LOI:
            return f"{_LOI[ma]} ({ma})"
    return re.sub(r"^ERROR:\s*", "", s)


async def _goi(cid: str, method: str, path: str, params=None, body=None):
    """Một lời gọi OpenAPI qua cầu nối có sẵn (tự làm mới token, -216/-124 thì làm mới một lần rồi thử lại)."""
    import zalo_oa_mcp
    return await zalo_oa_mcp._api(_spec(cid), method, path, params, body)


async def doc_oa(cid: str) -> dict:
    """{"ok", "oa_id", "ten"} hoặc {"ok": False, "error"}."""
    import zalo_oa_mcp
    ok, d = await _goi(cid, "GET", "/v2.0/oa/getoa")
    if not ok:
        return {"ok": False, "error": giai_thich(d)}
    d = d if isinstance(d, dict) else {}
    oa_id = str(d.get("oa_id") or "")
    if not oa_id:
        return {"ok": False, "error": "Zalo không trả về OA nào cho token này"}
    _ = zalo_oa_mcp   # cùng cầu nối, nhắc người đọc
    return {"ok": True, "oa_id": oa_id, "ten": str(d.get("name") or "")}


async def lien_ket(raw: str) -> dict:
    """Từ chuỗi chủ dán ra một kết nối Zalo OA dùng được. {"ok", "ket_noi", "oa_id", "ten"} hoặc {"ok": False, "error"}.

    Làm mới token một lần (cách duy nhất để biết khoá đúng và OA nào); cặp token mới nằm ngay trong kết nối,
    nên MinMin có khởi động lại giữa lúc Kiểm tra và lúc Lưu thì cũng không mất."""
    import mcp_store
    import zalo_oa_mcp
    cr = tach(raw)
    if cr.get("ket_noi"):
        cid = cr["ket_noi"]
        if not mcp_store.get_connection(cid):
            return {"ok": False, "error": "Kết nối Zalo OA của tài khoản này không còn ở trang Kết nối. Dán lại bốn thứ."}
        info = await doc_oa(cid)
        return {**info, "ket_noi": cid} if info.get("ok") else info
    thieu = [n for n, k in (("App ID", "app_id"), ("App secret key", "app_secret"), ("OA secret key", "oa_secret"))
             if not cr.get(k)]
    if thieu:
        return {"ok": False, "error": "Còn thiếu: " + ", ".join(thieu) + ". Dán theo thứ tự: App ID, App secret key, "
                                      "OA secret key, Refresh token."}
    co = _ket_noi_oa()
    cung_app = [c for c in co if str(c["sec"].get("app_id") or "").strip() == cr["app_id"]]
    cid, moi = "", False
    if cr["refresh_token"]:
        vt = _van_tay(cr["refresh_token"])
        # Đã đổi refresh token này rồi (bấm Kiểm tra hai lần, hoặc Kiểm tra rồi Lưu): dùng lại kết nối đó, không
        # đem token đã chết đi đổi lần nữa.
        cid = next((c["id"] for c in cung_app if c["sec"].get("rt_dan") == vt), "")
        if not cid:
            cid, loi = mcp_store.add_connection(CONNECTOR, {"label": "Zalo OA", "fields": {
                "app_id": cr["app_id"], "app_secret": cr["app_secret"], "oa_secret": cr["oa_secret"],
                "refresh_token": cr["refresh_token"], "rt_dan": vt}})
            if loi:
                return {"ok": False, "error": loi}
            moi = True
    else:
        co_token = [c for c in cung_app if str(c["sec"].get("refresh_token") or "").strip()]
        if len(co_token) != 1:
            return {"ok": False, "error": ("Còn thiếu Refresh token." if not co_token else
                                           "Có nhiều OA cùng App ID này ở trang Kết nối. Dán thêm Refresh token để "
                                           "chọn đúng OA.")}
        cid = co_token[0]["id"]
    if not moi:
        mcp_store.update_connection(cid, {"fields": {"oa_secret": cr["oa_secret"], "app_secret": cr["app_secret"]}})
    loi = await zalo_oa_mcp.dam_bao_token(_spec(cid))
    if loi:
        if moi:
            mcp_store.delete_connection(cid)
        return {"ok": False, "error": ("Zalo không làm mới được token: " + giai_thich(loi) + ". Refresh token sai, đã "
                                       "dùng rồi hoặc quá 3 tháng, hoặc App ID và App secret key không khớp. Lấy refresh "
                                       "token mới ở API Explorer rồi dán lại.")}
    info = await doc_oa(cid)
    if not info.get("ok"):
        # Token đã xoay và nằm trong kết nối này: KHÔNG xoá, xoá là mất refresh token duy nhất còn sống.
        return info
    # Một OA một kho token: OA này đã có kết nối khác thì dồn cặp token mới về đó, bỏ kết nối vừa tạo.
    khac = next((c for c in co if c["id"] != cid and str(c["sec"].get("oa_id") or "") == info["oa_id"]), None)
    if khac and moi:
        import ket_noi_api
        async with ket_noi_api.khoa({"key": khac["id"]}):
            sec = mcp_store.connection_secrets(cid)
            mcp_store.update_connection(khac["id"], {"fields": {
                k: sec.get(k, "") for k in ("access_token", "refresh_token", "token_het_han", "oa_secret",
                                            "app_secret", "rt_dan") if sec.get(k)}})
        mcp_store.delete_connection(cid)
        cid = khac["id"]
    patch = {"fields": {"oa_id": info["oa_id"]}}
    if moi and not khac and info.get("ten"):
        patch["label"] = f"Zalo OA {info['ten']}"[:80]
    mcp_store.update_connection(cid, patch)
    return {**info, "ket_noi": cid}


def tim_ket_noi(raw: str, oa_id: str = "") -> str:
    """Id kết nối mà chuỗi chủ dán đã liên kết (sau `lien_ket`). Rỗng nếu chưa liên kết."""
    cr = tach(raw)
    if cr.get("ket_noi"):
        return cr["ket_noi"]
    co = [c for c in _ket_noi_oa() if str(c["sec"].get("app_id") or "").strip() == cr.get("app_id")]
    if cr.get("refresh_token"):
        vt = _van_tay(cr["refresh_token"])
        hit = next((c["id"] for c in co if c["sec"].get("rt_dan") == vt), "")
        if hit:
            return hit
    if oa_id:
        return next((c["id"] for c in co if str(c["sec"].get("oa_id") or "") == str(oa_id)), "")
    return ""


# ---------------------------------------------------------------- webhook
def hop_le_chu_ky(than: bytes, header: str, cap_khoa) -> bool:
    """Chữ ký `X-ZEvent-Signature: mac=<hex>` có khớp thân tin dưới OA secret key của một OA không.

    Công thức tài liệu Zalo: sha256(app_id + thân thô + timestamp + OA secret key), `app_id` và `timestamp`
    lấy trong chính thân JSON. Vài bản cài cộng đồng dùng HMAC-SHA256(OA secret key, thân); cả hai đều cần
    khoá bí mật nên nhận cả hai. Địa chỉ webhook công khai: đây là thứ duy nhất chặn tin giả mạo khách."""
    got = str(header or "").strip()
    if got.lower().startswith("mac="):
        got = got[4:].strip()
    got = got.lower()
    if not got or not than:
        return False
    try:
        chu = than.decode("utf-8")
        d = json.loads(chu)
    except Exception:
        return False
    if not isinstance(d, dict):
        return False
    app_id, ts = str(d.get("app_id") or ""), str(d.get("timestamp") or "")
    for aid, khoa in cap_khoa or []:
        khoa = str(khoa or "")
        if not khoa or (aid and app_id and str(aid) != app_id):
            continue
        a = hashlib.sha256((app_id + chu + ts + khoa).encode("utf-8")).hexdigest()
        b = hmac.new(khoa.encode("utf-8"), than, hashlib.sha256).hexdigest()
        if hmac.compare_digest(a, got) or hmac.compare_digest(b, got):
            return True
    return False


def dang_truc() -> dict:
    return dict(_TRUC)


async def nhan_webhook(su_kien: dict) -> int:
    """Giao một sự kiện ĐÃ kiểm chữ ký cho bot của OA nhận. Trả số sự kiện đã giao (0 hoặc 1).
    Tin OA tự gửi (`oa_send_*`) và sự kiện không phải tin khách thì bỏ qua."""
    ev = su_kien or {}
    ten = str(ev.get("event_name") or "")
    if not ten.startswith("user_send_") and ten != "user_submit_info":
        return 0
    oa = str((ev.get("recipient") or {}).get("id") or ev.get("oa_id") or "")
    bot = _TRUC.get(oa)
    if not bot:
        print(f"[zalo-oa] có tin cho OA {oa} nhưng chưa bot nào trực OA này", file=sys.stderr)
        return 0
    asyncio.get_running_loop().create_task(bot._an_toan(ev))
    return 1


# ---------------------------------------------------------------- xác thực tên miền
def doc_ma_xac_thuc(raw) -> str:
    """Mã xác thực tên miền từ thứ chủ dán: tên file `zalo_verifier<mã>.html`, thẻ meta, hoặc chính mã."""
    s = str(raw or "").strip()
    m = re.search(r"zalo_verifier([A-Za-z0-9_\-]{6,80})\.html", s)
    if m:
        return m.group(1)
    m = re.search(r"zalo-platform-site-verification[^>]*content\s*=\s*[\"']([A-Za-z0-9_\-]{6,80})[\"']", s)
    if m:
        return m.group(1)
    return s if re.fullmatch(r"[A-Za-z0-9_\-]{6,80}", s) else ""


def ma_xac_thuc() -> list:
    import config as cfgmod
    ds = (cfgmod.read_settings().get("zalo_oa") or {}).get("ma_xac_thuc") or []
    return [str(x) for x in ds if re.fullmatch(r"[A-Za-z0-9_\-]{6,80}", str(x or ""))]


def luu_ma_xac_thuc(ma: str, xoa: bool = False) -> list:
    import config as cfgmod
    cfg = cfgmod.read_settings()
    ds = [x for x in ma_xac_thuc() if x != ma]
    if not xoa:
        ds = ([ma] + ds)[:MA_XAC_THUC_TOI_DA]
    z = cfg.get("zalo_oa") if isinstance(cfg.get("zalo_oa"), dict) else {}
    z["ma_xac_thuc"] = ds
    cfg["zalo_oa"] = z
    cfgmod.write_settings(cfg)
    return ds


def html_xac_thuc(ma: str) -> str:
    return ("<!DOCTYPE html>\n<html><head>\n"
            f"<meta name=\"zalo-platform-site-verification\" content=\"{ma}\" />\n"
            "</head><body>There Is No Limit To What You Can Accomplish Using Zalo!</body></html>\n")


# ---------------------------------------------------------------- lớp vận chuyển
def _cat(text: str, tran: int = TIN_TOI_DA) -> list:
    """Cắt câu dài, ưu tiên hết đoạn, hết dòng, hết câu rồi mới tới dấu cách."""
    s = str(text or "").strip()
    out = []
    while len(s) > tran:
        cat = -1
        for dau in ("\n\n", "\n", ". ", " "):
            i = s.rfind(dau, 0, tran)
            if i >= tran // 3:
                cat = i + len(dau)
                break
        if cat <= 0:
            cat = tran
        out.append(s[:cat].strip())
        s = s[cat:].strip()
    if s:
        out.append(s)
    return [x for x in out if x]


class ZaloOABot(HangLuot):
    """Đúng khế ước của `TelegramBot` (start/stop/status/send_text/send_file) để `chatbot_runtime` không phải
    biết mình cầm kênh nào. Không giữ kết nối nào: Zalo đẩy tin vào webhook. `start()` kiểm token, đọc mã OA,
    đăng ký trực OA đó, rồi định kỳ làm mới token trước khi hết hạn (refresh token chỉ sống khoảng 3 tháng
    nếu không được dùng, nên OA vắng khách lâu cũng không bị rơi ủy quyền)."""

    def __init__(self, token, chat_id, answer_fn, command_fn=None, download_dir=None, commands=None,
                 precheck_fn=None, event_fn=None, giau_trang_thai=False, **_bo_qua):
        self.ket_noi = tach(token).get("ket_noi") or ""
        self.account_id = ""
        self.oa_id = ""
        self.giau_trang_thai = bool(giau_trang_thai)
        self.chat_ids = parse_chat_ids(chat_id)
        self.commands = list(commands or [])
        self.answer_fn = answer_fn
        self.command_fn = command_fn
        self.callback_fn = None
        self.precheck_fn = precheck_fn
        self.event_fn = event_fn
        self.download_dir = download_dir
        self._task = None
        self._current = {}
        self._cho = {}
        self._stop = False
        self.status = "off"
        self.last_error = ""
        self.bot_id = ""
        self.bot_username = ""
        self.loi_danh_tinh = ""
        self.doc_moi_tin_nhom = False
        self._da_thay = set()
        self._thu_tu = deque()
        self._ten: dict = {}

    # ---- gửi ----------------------------------------------------------------------------
    async def _gui_mot(self, chat, text):
        return await _goi(self.ket_noi, "POST", "/v3.0/oa/message/cs",
                          body={"recipient": {"user_id": str(chat)}, "message": {"text": text}})

    async def _send(self, client, chat, text, reply_markup=None):
        import zalo_dinh_dang
        if not str(text or "").strip() and self.giau_trang_thai:
            return
        for manh in _cat(zalo_dinh_dang.bo_dinh_dang(text or "(không có nội dung)")):
            ok, d = await self._gui_mot(chat, manh)
            if not ok:
                self.last_error = giai_thich(d)
                print(f"[zalo-oa gửi] {self.last_error}", file=sys.stderr)
                return

    async def send_text(self, chat, text):
        import zalo_dinh_dang
        chu = zalo_dinh_dang.bo_dinh_dang(str(text or "")).strip()
        if not chu:
            return False, "tin trống"
        for manh in _cat(chu):
            ok, d = await self._gui_mot(chat, manh)
            if not ok:
                return False, giai_thich(d)
        return True, ""

    async def send_file(self, path, caption="", chat=None):
        """Ảnh JPG/PNG/GIF (tối đa 1MB) gửi dạng mẫu media, PDF/DOC/DOCX (tối đa 5MB) gửi dạng tệp. (ok, lỗi)."""
        import httpx
        import zalo_oa_mcp
        chat = chat or (self.chat_ids[0] if self.chat_ids else "")
        if not chat:
            return False, "không có người nhận"
        p = Path(str(path))
        try:
            data = p.read_bytes()
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        la_anh = mime in ("image/jpeg", "image/png", "image/gif")
        if not la_anh and p.suffix.lower() not in (".pdf", ".doc", ".docx"):
            return False, "Zalo OA chỉ gửi được ảnh JPG, PNG, GIF và tệp PDF, DOC, DOCX"
        tran = ANH_TOI_DA_MB if la_anh else TEP_TOI_DA_MB
        if len(data) > tran * 1024 * 1024:
            return False, f"tệp lớn hơn {tran}MB, Zalo OA không nhận"
        spec = _spec(self.ket_noi)
        loi = await zalo_oa_mcp.dam_bao_token(spec)
        if loi:
            return False, giai_thich(loi)
        tok = str(spec["secrets"].get("access_token") or "")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as c:
                r = await c.post(OPENAPI + ("/v2.0/oa/upload/image" if la_anh else "/v2.0/oa/upload/file"),
                                 headers={"access_token": tok}, files={"file": (p.name, data, mime)})
                d = r.json() if r.content else {}
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
        if int((d or {}).get("error") or 0):
            return False, giai_thich(f"Zalo {d.get('error')}: {d.get('message', '')}")
        dd = (d or {}).get("data") or {}
        if la_anh:
            dinh = {"type": "template", "payload": {"template_type": "media", "elements": [
                {"media_type": "image", "attachment_id": str(dd.get("attachment_id") or "")}]}}
        else:
            dinh = {"type": "file", "payload": {"token": str(dd.get("token") or "")}}
        tin = {"attachment": dinh}
        if la_anh and str(caption or "").strip():
            import zalo_dinh_dang
            tin["text"] = zalo_dinh_dang.bo_dinh_dang(str(caption))[:TIN_TOI_DA]
            caption = ""
        ok, kq = await _goi(self.ket_noi, "POST", "/v3.0/oa/message/cs",
                            body={"recipient": {"user_id": str(chat)}, "message": tin})
        if not ok:
            return False, giai_thich(kq)
        if str(caption or "").strip():
            return await self.send_text(chat, caption)
        return True, ""

    # ---- nhận ---------------------------------------------------------------------------
    def _thay_roi(self, mid) -> bool:
        mid = str(mid or "")
        if not mid:
            return False
        if mid in self._da_thay:
            return True
        self._da_thay.add(mid)
        self._thu_tu.append(mid)
        while len(self._thu_tu) > NHO_TOI_DA:
            self._da_thay.discard(self._thu_tu.popleft())
        return False

    async def _ten_khach(self, uid) -> str:
        if uid in self._ten:
            return self._ten[uid]
        ok, d = await _goi(self.ket_noi, "GET", "/v3.0/oa/user/detail",
                           {"data": json.dumps({"user_id": str(uid)})})
        ten = str((d or {}).get("display_name") or "").strip() if ok and isinstance(d, dict) else ""
        if len(self._ten) > 2000:
            self._ten.clear()
        self._ten[uid] = ten
        return ten

    async def _tai(self, url):
        import httpx
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=True) as c:
            r = await c.get(url)
        r.raise_for_status()
        if len(r.content) > TAI_TOI_DA_MB * 1024 * 1024:
            raise RuntimeError(f"lớn hơn {TAI_TOI_DA_MB}MB")
        return r.content, str(r.headers.get("content-type") or "").split(";")[0].strip()

    async def _chu_dinh_kem(self, att, chat) -> str:
        loai = str(att.get("type") or "")
        pl = att.get("payload") or {}
        url = str(pl.get("url") or "")
        if loai == "location":
            co = pl.get("coordinates") or {}
            return f"[Khách gửi vị trí: {co.get('latitude')}, {co.get('longitude')}]"
        if loai == "sticker":
            return "[Khách gửi một nhãn dán]"
        if loai == "link":
            return str(pl.get("url") or pl.get("description") or "").strip()
        if not url:
            return ""
        if loai in ("audio", "voice"):
            return "[Khách gửi một tin thoại qua Zalo OA, bot chưa nghe được. Hãy nhờ khách nhắn bằng chữ]"
        if loai in ("video", "gif"):
            return f"[Khách gửi một video qua Zalo OA: {url}]"
        try:
            data, mime = await self._tai(url)
        except Exception as e:
            return f"[Khách gửi {loai} nhưng tải về lỗi: {type(e).__name__}]"
        thu_muc = self.download_dir(chat) if callable(self.download_dir) else self.download_dir
        d = Path(thu_muc) if thu_muc else Path("zalo-oa-inbox")
        d.mkdir(parents=True, exist_ok=True)
        duoi = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp",
                "application/pdf": ".pdf"}.get(mime, "")
        if not duoi:
            m = re.search(r"\.([A-Za-z0-9]{2,5})(?:\?|$)", str(pl.get("name") or url))
            duoi = "." + m.group(1).lower() if m else ""
        dich = d / f"zalo_oa_{int(time.time() * 1000)}{duoi}"
        dich.write_bytes(data)
        if loai == "image":
            return f"[Khách gửi ảnh qua Zalo OA, đã tải về: {dich}]"
        return f"[Khách gửi tệp qua Zalo OA, đã tải về: {dich}]"

    async def _chu_su_kien(self, ev, chat) -> str:
        if ev.get("event_name") == "user_submit_info":
            info = ev.get("info") or {}
            return "; ".join(f"{k}: {v}" for k, v in info.items() if v)
        tin = ev.get("message") or {}
        phan = []
        for att in tin.get("attachments") or []:
            t = await self._chu_dinh_kem(att, chat)
            if t:
                phan.append(t)
        chu = str(tin.get("text") or "").strip()
        if chu:
            phan.append(chu)
        return "\n".join(phan).strip()

    async def _an_toan(self, ev):
        try:
            await self._nhan(ev)
        except Exception as e:
            print(f"[zalo-oa sự kiện] {type(e).__name__}: {e}", file=sys.stderr)

    async def _nhan(self, ev):
        tin = ev.get("message") or {}
        mid = str(tin.get("msg_id") or "") or (
            f"{(ev.get('sender') or {}).get('id')}:{ev.get('timestamp')}:{ev.get('event_name')}")
        if self._stop or self._thay_roi(mid):
            return
        chat = str((ev.get("sender") or {}).get("id") or ev.get("user_id_by_app") or "")
        if not chat or chat == self.oa_id:
            return
        ten = await self._ten_khach(chat)
        meta = {"platform": KENH, "chat_id": chat, "chat_type": "private", "chat_title": "",
                "user_name": ten, "username": ten, "user_id": chat, "message_id": str(tin.get("msg_id") or ""),
                "bot_username": self.bot_username, "mentioned": False, "reply_to_bot": False}
        if self.chat_ids and chat not in self.chat_ids:
            return
        chu = await self._chu_su_kien(ev, chat)
        if chu:
            await self._dispatch(None, chat, chu, meta)

    async def _handle_turn(self, client, chat, text, meta=None):
        tep, cong_cu, t0 = [], [], time.monotonic()

        async def progress(txt):
            ten = ten_tool(txt)
            if ten and ten not in cong_cu:
                cong_cu.append(ten)

        try:
            dap = await self.answer_fn(text, meta, progress)
        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"[zalo-oa lượt hỏng] {type(e).__name__}: {e}", file=sys.stderr)
            from telegram_bot import CAU_LOI_NGUOI_THAT
            dap = CAU_LOI_NGUOI_THAT if self.giau_trang_thai else f"⚠ Lỗi: {type(e).__name__}: {e}"
        im = False
        if isinstance(dap, dict):
            tep = dap.get("files") or []
            im = bool(dap.get("im_lang"))
            dap = dap.get("text") or ""
        if im and not str(dap or "").strip() and not tep:
            return
        if not self.giau_trang_thai:
            vet = dong_vet(cong_cu, time.monotonic() - t0)
            dap = ((str(dap or "").rstrip() + "\n\n") if str(dap or "").strip() else "") + vet
        if str(dap or "").strip() or not tep:
            await self._send(client, chat, dap)
        for f in tep:
            duong, chu_thich = (f.get("path"), f.get("caption", "")) if isinstance(f, dict) else (f, "")
            ok, loi = await self.send_file(duong, chu_thich, chat=chat)
            if not ok:
                print(f"[zalo-oa gửi tệp] {duong}: {loi}", file=sys.stderr)

    # ---- vòng đời -----------------------------------------------------------------------
    async def _canh(self):
        import mcp_store
        import zalo_oa_mcp
        if not self.ket_noi or not mcp_store.get_connection(self.ket_noi):
            self.status, self.last_error = "error", ("Kết nối Zalo OA của tài khoản này không còn ở trang Kết nối. "
                                                     "Sửa kênh, dán lại bốn thứ.")
            return
        sec = mcp_store.connection_secrets(self.ket_noi)
        if not str(sec.get("oa_secret") or "").strip():
            # Thiếu khoá này thì mọi webhook bị từ chối chữ ký: bot trông như khoẻ mà không nghe gì. Báo thẳng.
            self.status, self.last_error = "error", "Thiếu OA secret key nên MinMin không kiểm được tin Zalo gửi tới. Sửa kênh, dán đủ bốn thứ."
            return
        info = await doc_oa(self.ket_noi)
        if not info.get("ok"):
            self.status = "error"
            self.last_error = self.loi_danh_tinh = info.get("error", "")
            return
        self.oa_id = self.bot_id = info["oa_id"]
        self.bot_username = info.get("ten", "")
        self.loi_danh_tinh = ""
        _TRUC[self.oa_id] = self
        self.status, self.last_error = "polling", ""
        try:
            while not self._stop:
                het = 0.0
                try:
                    het = float(mcp_store.connection_secrets(self.ket_noi).get("token_het_han") or 0)
                except (TypeError, ValueError):
                    het = 0.0
                await asyncio.sleep(max(60.0, min(het - time.time() - 240, 3600.0)))
                if self._stop:
                    break
                loi = await zalo_oa_mcp.dam_bao_token(_spec(self.ket_noi))
                if loi:
                    self.last_error = "Zalo không làm mới được token: " + giai_thich(loi)
                    print(f"[zalo-oa] OA {self.oa_id}: {self.last_error}", file=sys.stderr)
                    await asyncio.sleep(600)
                else:
                    self.last_error = ""
        finally:
            if _TRUC.get(self.oa_id) is self:
                _TRUC.pop(self.oa_id, None)

    def start(self):
        self._stop = False
        self.status = "starting"
        if not self._task or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._canh())

    def stop(self):
        self._stop = True
        self.status = "stopped"
        if _TRUC.get(self.oa_id) is self:
            _TRUC.pop(self.oa_id, None)
        for t in list(self._current.values()):
            if t and not t.done():
                t.cancel()
        self._current.clear()
        self._cho.clear()
        if self._task:
            self._task.cancel()
            self._task = None
