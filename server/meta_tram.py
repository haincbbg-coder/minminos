"""meta_tram.py - TRẠM ĐĂNG NHẬP META của MinMin (26.10.114).

Vấn đề: muốn đọc quảng cáo hay đăng bài Facebook, người dùng phải tự tạo một Facebook App,
dán App ID + App Secret, khai Redirect URI đúng từng ký tự. Người thường làm không nổi.

Cách giải: nhà phát hành MinMin giữ MỘT Facebook App đã được Meta duyệt. Người dùng chỉ bấm
"Đăng nhập bằng Facebook". Vướng ở chỗ MinMin tự host: mỗi máy một tên miền, còn App Secret thì
không bao giờ được phát cho từng máy. Nên cần một TRẠM đứng giữa, chạy trên máy chủ của nhà phát
hành (vd minmin.elaria.cloud), là nơi duy nhất giữ App Secret.

File này có HAI nửa:

  BÊN TRẠM (chỉ bật khi máy có JAVIS_META_TRAM_APP_ID + JAVIS_META_TRAM_APP_SECRET):
    POST /mt/bat-dau        máy MinMin xin mở một phiên đăng nhập (yêu cầu có KÝ SỐ)
    GET  /mt/xac-nhan/{id}  trang trung gian: "bạn đang nối Facebook với máy <host>, đúng không?"
    GET  /mt/ve             Facebook trả code về đây; trạm đổi code lấy token dài hạn
    POST /mt/nhan           máy MinMin nhận token (đã MÃ HOÁ riêng cho nó), nhận một lần rồi xoá
    POST /mt/gia-han        gia hạn token ~60 ngày (cần App Secret nên phải qua trạm)
    GET  /mt/thong-tin      trạm có bật không, xin được những quyền nào
    GET  /mt/chinh-sach, /mt/dieu-khoan, /mt/xoa-du-lieu   ba trang Meta bắt buộc khi duyệt app

  BÊN MÁY NGƯỜI DÙNG: bat_dau(), nhan(), gia_han() - oauth_mcp gọi khi connector provider=meta
  mà người dùng chọn "Đăng nhập nhanh qua MinMin" thay vì tự tạo app.

Bảo mật, từng lớp:
  1. Mọi yêu cầu từ máy MinMin KÝ bằng khoá danh tính Ed25519 của máy (danh_tinh). Chỉ đúng máy
     mở phiên mới nhận được token của phiên đó.
  2. Token MÃ HOÁ cho riêng máy nhận (X25519 + HKDF + AES-GCM, khoá tạm sinh mỗi lần). Kể cả lộ
     mã phiên qua lịch sử trình duyệt, kẻ khác cũng không đọc được.
  3. Trạm KHÔNG LƯU token: chỉ giữ bản đã mã hoá tối đa 5 phút trong RAM cho tới lúc máy nhận lấy.
  4. Trang trung gian + cookie: kẻ xấu không thể gửi thẳng link Facebook cho nạn nhân để token
     của nạn nhân chảy về máy kẻ xấu. Trình duyệt phải đi qua trang xác nhận (hiện rõ địa chỉ máy
     sẽ nhận token) và mang cookie do trang đó đặt, thiếu là trạm từ chối.
  5. Địa chỉ quay về chỉ nhận https công khai hoặc http://localhost, và đường dẫn phải đúng
     /connect/oauth/callback: trạm không thành công cụ chuyển hướng tuỳ ý.

Giới hạn phải nói thật: token ĐI QUA RAM của trạm trong lúc đổi code. Ai vận hành trạm về lý
thuyết thấy được nó. Trang Chính sách nói rõ điều này; ai không muốn thì vẫn dùng đường tự tạo app.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
from typing import Optional

import httpx

import danh_tinh

GRAPH_VER = "v26.0"
DIALOG = f"https://www.facebook.com/{GRAPH_VER}/dialog/oauth"
TOKEN_URL = f"https://graph.facebook.com/{GRAPH_VER}/oauth/access_token"
GRAPH = f"https://graph.facebook.com/{GRAPH_VER}"
TRAM_MAC_DINH = "https://minmin.elaria.cloud"
LECH_GIAY = 600            # chữ ký cũ hơn 10 phút là hết hiệu lực
PHIEN_TTL = 900            # từ lúc mở phiên tới lúc Facebook trả về: 15 phút
HOP_TTL = 300              # bản mã hoá chờ máy nhận: 5 phút
TOI_DA_PHIEN = 2000
QUYEN_MAC_DINH = ("ads_read", "ads_management", "business_management", "pages_show_list",
                  "pages_read_engagement", "pages_manage_posts", "pages_manage_engagement",
                  "read_insights")
TEN_QUYEN = {
    "ads_read": "Đọc số liệu quảng cáo",
    "ads_management": "Quản lý quảng cáo (tạo, sửa, tạm dừng)",
    "business_management": "Đọc danh sách tài sản trong Business Manager",
    "pages_show_list": "Xem danh sách Trang",
    "pages_read_engagement": "Đọc bài viết và tương tác của Trang",
    "pages_manage_posts": "Đăng và sửa bài trên Trang",
    "pages_manage_engagement": "Trả lời, ẩn bình luận trên Trang",
    "read_insights": "Đọc số liệu Trang",
}
COOKIE = "mt_xn"

_LOCK = threading.Lock()
_phien: dict = {}          # id -> {khoa, kx, ve, st, quyen, goc, xn, ts}
_hop: dict = {}            # id -> {khoa, goi (dict mã hoá), ts}
_dem: dict = {}            # ip -> [ts...] (chặn spam)


# ───────────────────────────── mã hoá chung ─────────────────────────────

def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _unb64(s: str) -> bytes:
    return base64.b64decode(str(s or ""), validate=True)


def khoa_tam():
    """(khoá riêng X25519 dạng bytes, khoá công khai base64) - sinh mới mỗi lần đăng nhập."""
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    k = X25519PrivateKey.generate()
    rieng = k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                            serialization.NoEncryption())
    cong = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return rieng, _b64(cong)


def _khoa_aes(chung: bytes, e_pub: bytes, nhan_pub: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=b"minmin-meta-tram|" + e_pub + nhan_pub).derive(chung)


def niem_phong(du_lieu: dict, nhan_pub_b64: str) -> dict:
    """Mã hoá một dict cho riêng chủ khoá X25519 `nhan_pub_b64`."""
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import serialization
    nhan_pub = _unb64(nhan_pub_b64)
    e = X25519PrivateKey.generate()
    e_pub = e.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    khoa = _khoa_aes(e.exchange(X25519PublicKey.from_public_bytes(nhan_pub)), e_pub, nhan_pub)
    n = secrets.token_bytes(12)
    c = AESGCM(khoa).encrypt(n, json.dumps(du_lieu).encode(), b"minmin-meta-tram")
    return {"e": _b64(e_pub), "n": _b64(n), "c": _b64(c)}


def mo_niem_phong(goi: dict, rieng: bytes) -> Optional[dict]:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import serialization
    try:
        k = X25519PrivateKey.from_private_bytes(rieng)
        nhan_pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        e_pub = _unb64(goi["e"])
        khoa = _khoa_aes(k.exchange(X25519PublicKey.from_public_bytes(e_pub)), e_pub, nhan_pub)
        raw = AESGCM(khoa).decrypt(_unb64(goi["n"]), _unb64(goi["c"]), b"minmin-meta-tram")
        d = json.loads(raw.decode())
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def thong_diep(duong: str, than: dict, luc: str) -> bytes:
    """Thứ được ký: đường dẫn + thời điểm + băm của thân (bỏ trường ky)."""
    goc = {k: v for k, v in (than or {}).items() if k != "ky"}
    bam = hashlib.sha256(json.dumps(goc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f"minmin-mt|{duong}|{luc}|{bam}".encode()


def ky_than(duong: str, than: dict) -> dict:
    """Thêm khoa/luc/ky của máy này vào thân yêu cầu gửi trạm."""
    t = dict(than, khoa=danh_tinh.cong_khai(), luc=str(int(time.time())))
    t["ky"] = danh_tinh.ky(thong_diep(duong, t, t["luc"]))
    return t


def kiem_than(duong: str, than: dict) -> str:
    """'' khi chữ ký hợp lệ, ngược lại là lý do."""
    try:
        if abs(time.time() - int(than.get("luc"))) > LECH_GIAY:
            return "sai_gio"
    except (TypeError, ValueError):
        return "sai_gio"
    if not danh_tinh.xac_minh(str(than.get("khoa") or ""), thong_diep(duong, than, str(than["luc"])),
                              str(than.get("ky") or "")):
        return "sai_chu_ky"
    return ""


# ───────────────────────────── BÊN TRẠM ─────────────────────────────

def cau_hinh() -> dict:
    app_id = (os.environ.get("JAVIS_META_TRAM_APP_ID") or "").strip()
    sec = (os.environ.get("JAVIS_META_TRAM_APP_SECRET") or "").strip()
    q = [x.strip() for x in (os.environ.get("JAVIS_META_TRAM_SCOPES") or "").split(",") if x.strip()]
    return {"bat": bool(app_id and sec), "app_id": app_id, "secret": sec,
            "quyen": q or list(QUYEN_MAC_DINH),
            "goc": (os.environ.get("JAVIS_META_TRAM_GOC") or "").strip().rstrip("/"),
            # Facebook Login for Business: quyền khai trong một "cấu hình" ở trang app, gửi
            # config_id thay cho scope. Bỏ trống = Facebook Login thường (gửi scope).
            "config_id": (os.environ.get("JAVIS_META_TRAM_CONFIG_ID") or "").strip(),
            "chu": (os.environ.get("JAVIS_META_TRAM_CHU") or "MinMin OS").strip(),
            "lien_he": (os.environ.get("JAVIS_META_TRAM_LIEN_HE") or "").strip()}


_VE_RE = re.compile(r"^(https://[a-z0-9.-]+(:\d{2,5})?|http://(localhost|127\.0\.0\.1)(:\d{2,5})?)"
                    r"/connect/oauth/callback$", re.I)


def ve_hop_le(ve: str) -> bool:
    """Chỉ cho quay về đúng đường /connect/oauth/callback của một máy MinMin."""
    if not _VE_RE.match(ve or ""):
        return False
    host = urllib.parse.urlsplit(ve).hostname or ""
    if ve.lower().startswith("https://"):
        # https trỏ vào IP nội bộ hay tên không có dấu chấm thì không phải máy công khai
        if "." not in host or re.match(r"^(10|127|192\.168|172\.(1[6-9]|2\d|3[01]))\.", host):
            return False
    return True


def _don():
    now = time.time()
    for k in [k for k, v in _phien.items() if now - v["ts"] > PHIEN_TTL]:
        _phien.pop(k, None)
    for k in [k for k, v in _hop.items() if now - v["ts"] > HOP_TTL]:
        _hop.pop(k, None)


def gioi_han(ip: str, toi_da: int = 30, cua_so: int = 600) -> bool:
    """True = còn được phép. Đơn giản, trong RAM, đủ chặn một máy spam mở phiên."""
    now = time.time()
    with _LOCK:
        ds = [t for t in _dem.get(ip, []) if now - t < cua_so]
        if len(ds) >= toi_da:
            _dem[ip] = ds
            return False
        ds.append(now)
        _dem[ip] = ds
        if len(_dem) > 5000:
            _dem.clear()
    return True


def mo_phien(than: dict, goc: str) -> dict:
    """Xử lý POST /mt/bat-dau. Trả {ok, url} hoặc {ok:False, loi, ma}."""
    ch = cau_hinh()
    if not ch["bat"]:
        return {"ok": False, "ma": 503, "loi": "Trạm đăng nhập Meta chưa bật trên máy chủ này."}
    ly_do = kiem_than("/mt/bat-dau", than)
    if ly_do:
        return {"ok": False, "ma": 401, "loi": f"Yêu cầu không hợp lệ ({ly_do})."}
    ve = str(than.get("ve") or "")
    if not ve_hop_le(ve):
        return {"ok": False, "ma": 400, "loi": "Địa chỉ quay về không hợp lệ."}
    try:
        if len(_unb64(than.get("kx"))) != 32:
            raise ValueError
    except Exception:
        return {"ok": False, "ma": 400, "loi": "Thiếu khoá nhận."}
    st = str(than.get("st") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", st):
        return {"ok": False, "ma": 400, "loi": "Thiếu mã phiên của máy."}
    xin = [q for q in (than.get("quyen") or []) if isinstance(q, str)]
    quyen = [q for q in xin if q in ch["quyen"]] or [q for q in ("ads_read",) if q in ch["quyen"]]
    goc = (ch["goc"] or goc).rstrip("/")
    pid = secrets.token_urlsafe(24)
    with _LOCK:
        _don()
        if len(_phien) >= TOI_DA_PHIEN:
            return {"ok": False, "ma": 429, "loi": "Trạm đang bận, thử lại sau ít phút."}
        _phien[pid] = {"khoa": than["khoa"], "kx": than["kx"], "ve": ve, "st": st, "quyen": quyen,
                       "goc": goc, "xn": secrets.token_urlsafe(18), "ts": time.time()}
    return {"ok": True, "url": f"{goc}/mt/xac-nhan/{pid}", "quyen": quyen}


def trang_xac_nhan(pid: str):
    """(html, cookie_value | None) cho GET /mt/xac-nhan/{pid}."""
    ch = cau_hinh()
    with _LOCK:
        _don()
        p = _phien.get(pid)
    if not p or not ch["bat"]:
        return _trang("Phiên đã hết hạn", "<p>Quay lại MinMin và bấm Đăng nhập Facebook lần nữa.</p>"), None
    host = urllib.parse.urlsplit(p["ve"]).netloc
    q = {"client_id": ch["app_id"], "redirect_uri": p["goc"] + "/mt/ve", "state": pid,
         "response_type": "code", "scope": ",".join(p["quyen"]), "auth_type": "rerequest"}
    if ch["config_id"]:
        q.pop("scope", None)
        q["config_id"] = ch["config_id"]
    di = DIALOG + "?" + urllib.parse.urlencode(q)
    ds = "".join(f"<li>{html.escape(TEN_QUYEN.get(x, x))}</li>" for x in p["quyen"])
    than = (f"<p>Bạn đang nối Facebook với máy MinMin tại</p><p class='host'>{html.escape(host)}</p>"
            f"<p class='nho'>Vân tay máy: {html.escape(danh_tinh.van_tay(p['khoa']))}</p>"
            f"<p>Máy đó sẽ được phép:</p><ul>{ds}</ul>"
            "<p class='canh'>Chỉ tiếp tục nếu đây là máy MinMin của chính bạn. Nếu ai đó gửi link này "
            "cho bạn, hãy đóng trang.</p>"
            f"<a class='nut' href='{html.escape(di)}'>Tiếp tục với Facebook</a>")
    return _trang("Xác nhận kết nối Facebook", than), p["xn"]


async def _doi_code(code: str, ve: str, ch: dict) -> dict:
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(TOKEN_URL, params={"client_id": ch["app_id"], "client_secret": ch["secret"],
                                           "redirect_uri": ve, "code": code})
        tk = r.json()
        if not (isinstance(tk, dict) and tk.get("access_token")):
            raise ValueError(((tk or {}).get("error") or {}).get("message") or "Facebook từ chối mã")
        r2 = await c.get(TOKEN_URL, params={"grant_type": "fb_exchange_token", "client_id": ch["app_id"],
                                            "client_secret": ch["secret"], "fb_exchange_token": tk["access_token"]})
        ll = r2.json()
        if isinstance(ll, dict) and ll.get("access_token"):
            tk = ll
        ra = {"access_token": tk["access_token"], "expires_in": int(tk.get("expires_in") or 5184000)}
        try:     # quyền THẬT được cấp, để máy phát hiện "đăng nhập xanh nhưng thiếu quyền"
            r3 = await c.get(GRAPH + "/me/permissions", params={"access_token": ra["access_token"]})
            ds = [x.get("permission") for x in (r3.json() or {}).get("data", []) if x.get("status") == "granted"]
            ra["scope"] = ",".join(x for x in ds if x)
        except Exception:
            pass
        return ra


async def nhan_ve(pid: str, code: str, loi: str, cookie: str):
    """Xử lý GET /mt/ve. Trả ('redirect', url) hoặc ('html', trang)."""
    ch = cau_hinh()
    with _LOCK:
        _don()
        p = _phien.get(pid or "")
        # Kiểm cookie TRƯỚC khi xoá phiên: không thì ai gọi bừa vào /mt/ve cũng huỷ được phiên
        # đang chờ của người khác.
        hop_le = bool(p and cookie and secrets.compare_digest(str(cookie), p["xn"]))
        if hop_le:
            _phien.pop(pid, None)
    if not p:
        return "html", _trang("Phiên đã hết hạn", "<p>Quay lại MinMin và thử lại từ đầu.</p>")
    if not hop_le:
        return "html", _trang("Không xác nhận được", "<p>Trình duyệt này chưa đi qua trang xác nhận "
                              "của MinMin. Vì an toàn, trạm không nhận. Hãy bắt đầu lại từ MinMin của bạn.</p>")
    if loi or not code:
        return "html", _trang("Chưa kết nối", "<p>Bạn đã huỷ hoặc Facebook không cấp quyền. "
                              "Quay lại MinMin để thử lại.</p>")
    try:
        tk = await _doi_code(code, p["goc"] + "/mt/ve", ch)
    except Exception as e:
        return "html", _trang("Facebook từ chối", f"<p>{html.escape(str(e))[:300]}</p>")
    with _LOCK:
        _hop[pid] = {"khoa": p["khoa"], "goi": niem_phong(tk, p["kx"]), "ts": time.time()}
    del tk
    return "redirect", p["ve"] + "?" + urllib.parse.urlencode({"state": p["st"], "tram": pid})


def giao_hop(than: dict) -> dict:
    """POST /mt/nhan: trả gói mã hoá một lần, đúng máy đã mở phiên."""
    ly_do = kiem_than("/mt/nhan", than)
    if ly_do:
        return {"ok": False, "ma": 401, "loi": ly_do}
    with _LOCK:
        _don()
        h = _hop.get(str(than.get("phien") or ""))
        if not h or h["khoa"] != than.get("khoa"):
            return {"ok": False, "ma": 404, "loi": "Không có hoặc đã nhận rồi."}
        _hop.pop(str(than["phien"]), None)
    return {"ok": True, "goi": h["goi"]}


async def gia_han_tram(than: dict) -> dict:
    """POST /mt/gia-han: đổi token còn hạn lấy token mới ~60 ngày, trả về đã mã hoá."""
    ch = cau_hinh()
    if not ch["bat"]:
        return {"ok": False, "ma": 503, "loi": "Trạm chưa bật."}
    ly_do = kiem_than("/mt/gia-han", than)
    if ly_do:
        return {"ok": False, "ma": 401, "loi": ly_do}
    tok = str(than.get("token") or "")
    if not tok:
        return {"ok": False, "ma": 400, "loi": "Thiếu token."}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(TOKEN_URL, params={"grant_type": "fb_exchange_token", "client_id": ch["app_id"],
                                               "client_secret": ch["secret"], "fb_exchange_token": tok})
            ll = r.json()
    except Exception as e:
        return {"ok": False, "ma": 502, "loi": f"Không gọi được Facebook: {type(e).__name__}"}
    if not (isinstance(ll, dict) and ll.get("access_token")):
        return {"ok": False, "ma": 400, "loi": "Token đã hết hạn hoặc bị thu hồi, cần đăng nhập lại."}
    try:
        goi = niem_phong({"access_token": ll["access_token"],
                          "expires_in": int(ll.get("expires_in") or 5184000)}, str(than.get("kx") or ""))
    except Exception:
        return {"ok": False, "ma": 400, "loi": "Thiếu khoá nhận."}
    return {"ok": True, "goi": goi}


def thong_tin() -> dict:
    ch = cau_hinh()
    return {"bat": ch["bat"], "quyen": ch["quyen"] if ch["bat"] else [], "chu": ch["chu"]}


# ── ba trang Meta bắt buộc (song ngữ: người duyệt của Meta đọc tiếng Anh) ──

_CSS = ("body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#0f1115;color:#e8e8ea;"
        "margin:0;padding:24px 16px;line-height:1.6}main{max-width:640px;margin:0 auto}"
        "h1{font-size:22px}h2{font-size:17px;margin-top:28px}a{color:#7cb4ff}"
        ".host{font-size:20px;font-weight:600;word-break:break-all}.nho{color:#9aa0a6;font-size:13px}"
        ".canh{background:#3a2a10;border:1px solid #8a6420;border-radius:8px;padding:10px 12px}"
        ".nut{display:inline-block;margin-top:12px;background:#1877f2;color:#fff;text-decoration:none;"
        "padding:12px 20px;border-radius:8px;font-weight:600}")


def csp() -> str:
    return "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; base-uri 'none'; form-action 'none'"


def _trang(tieu_de: str, than: str) -> str:
    return (f"<!doctype html><html lang='vi'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>{html.escape(tieu_de)}</title>"
            f"<style>{_CSS}</style></head><body><main><h1>{html.escape(tieu_de)}</h1>{than}</main></body></html>")


def trang_chinh_sach() -> str:
    ch = cau_hinh()
    lh = html.escape(ch["lien_he"] or "(chưa khai)")
    chu = html.escape(ch["chu"])
    return _trang(f"Chính sách quyền riêng tư - {ch['chu']}", f"""
<p><b>{chu}</b> vận hành dịch vụ "Đăng nhập Facebook cho MinMin". MinMin là phần mềm trợ lý kinh doanh mà
mỗi người dùng tự cài trên máy chủ của mình.</p>
<h2>Chúng tôi thu thập gì</h2>
<p>Khi bạn bấm Đăng nhập Facebook, trạm nhận mã cấp quyền từ Facebook, đổi lấy access token, mã hoá token
riêng cho máy MinMin của bạn và chuyển về máy đó. Trạm <b>không lưu</b> token, không lưu tên, email hay dữ
liệu quảng cáo, Trang của bạn. Bản đã mã hoá nằm trong bộ nhớ tạm tối đa 5 phút rồi bị xoá.</p>
<h2>Dữ liệu được dùng thế nào</h2>
<p>Token chỉ nằm trên máy MinMin của bạn, được mã hoá khi lưu. MinMin dùng nó để đọc số liệu quảng cáo,
đọc và đăng bài trên Trang theo yêu cầu của chính bạn. Dữ liệu không được bán hay chia sẻ cho bên thứ ba.</p>
<h2>Xoá dữ liệu</h2>
<p>Xem <a href="/mt/xoa-du-lieu">hướng dẫn xoá dữ liệu</a>.</p>
<h2>Liên hệ</h2><p>{lh}</p>
<h2>English summary</h2>
<p>{chu} operates a login relay for MinMin, a self-hosted business assistant. The relay exchanges the
Facebook authorization code for an access token, encrypts it for the user's own MinMin server and delivers it
there. The relay does not store tokens or any personal, advertising or Page data; the encrypted blob is held in
memory for at most 5 minutes. The token is used only by the user's own server, at the user's request, to read
ad insights and to read and publish Page content. Data is never sold or shared. Contact: {lh}.</p>""")


def trang_dieu_khoan() -> str:
    ch = cau_hinh()
    chu = html.escape(ch["chu"])
    lh = html.escape(ch["lien_he"] or "(chưa khai)")
    return _trang(f"Điều khoản sử dụng - {ch['chu']}", f"""
<p>Dịch vụ đăng nhập do <b>{chu}</b> cung cấp miễn phí, như hiện trạng, để kết nối máy MinMin của bạn với tài
khoản Facebook của chính bạn.</p>
<ul><li>Bạn chỉ kết nối tài khoản, Trang, tài khoản quảng cáo mà bạn có quyền quản lý.</li>
<li>Bạn chịu trách nhiệm về mọi thao tác máy MinMin của bạn thực hiện, kể cả thao tác tự động.</li>
<li>Không dùng dịch vụ để spam, tạo tài khoản giả, hay vi phạm Điều khoản nền tảng của Meta.</li>
<li>Chúng tôi có thể tạm dừng dịch vụ hoặc chặn một máy vi phạm.</li></ul>
<p>Liên hệ: {lh}</p>
<h2>English</h2><p>The login relay is provided free and as-is by {chu} to connect your own MinMin server with your
own Facebook account. Connect only accounts, Pages and ad accounts you are authorised to manage. You are
responsible for all actions your server performs. Spam, fake accounts and violations of Meta Platform Terms are
prohibited. We may suspend the service or block a server that violates these terms. Contact: {lh}.</p>""")


def trang_xoa_du_lieu() -> str:
    ch = cau_hinh()
    lh = html.escape(ch["lien_he"] or "(chưa khai)")
    return _trang("Hướng dẫn xoá dữ liệu", f"""
<p>Trạm đăng nhập không lưu dữ liệu nào của bạn, nên không có gì để xoá ở phía trạm.</p>
<h2>Xoá dữ liệu trên máy MinMin của bạn</h2>
<ol><li>Mở MinMin, vào trang <b>Kết nối</b>.</li><li>Ở thẻ Meta Ads hoặc Facebook Trang, bấm <b>Xoá kết nối</b>.
Token bị xoá khỏi máy ngay.</li></ol>
<h2>Thu hồi quyền ở phía Facebook</h2>
<ol><li>Vào Facebook &gt; Cài đặt &gt; Bảo mật &gt; <b>Ứng dụng và trang web</b>.</li><li>Chọn ứng dụng MinMin, bấm
<b>Gỡ</b>. Mọi token đã cấp hết hiệu lực.</li></ol>
<p>Cần hỗ trợ: {lh}</p>
<h2>English</h2><p>The login relay stores no user data, so there is nothing to delete on the relay. To delete data
on your MinMin server, open Connections and remove the Meta connection. To revoke access on Facebook, go to
Settings &gt; Security &gt; Apps and Websites, select MinMin and remove it. Contact: {lh}.</p>""")


# ───────────────────────────── BÊN MÁY NGƯỜI DÙNG ─────────────────────────────

def dia_chi_tram() -> str:
    v = (os.environ.get("JAVIS_META_TRAM") or TRAM_MAC_DINH).strip().rstrip("/")
    return "" if v.lower() in ("", "off", "0", "tat", "false") else v


async def _goi(duong: str, than: dict) -> dict:
    tram = dia_chi_tram()
    if not tram:
        return {"ok": False, "loi": "Máy này đã tắt trạm đăng nhập Meta (JAVIS_META_TRAM=off)."}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(tram + duong, json=ky_than(duong, than))
            d = r.json()
    except Exception as e:
        return {"ok": False, "loi": f"Không gọi được trạm đăng nhập ({type(e).__name__})."}
    return d if isinstance(d, dict) else {"ok": False, "loi": "Trạm trả lời lạ."}


_tt_cache: dict = {}


async def trang_thai_tram() -> dict:
    """Trạm có bật không (cache 5 phút) - để dashboard biết có hiện nút đăng nhập nhanh."""
    tram = dia_chi_tram()
    if not tram:
        return {"bat": False, "tram": ""}
    c = _tt_cache.get(tram)
    if c and time.time() - c[0] < 300:
        return c[1]
    try:
        async with httpx.AsyncClient(timeout=8) as cl:
            d = (await cl.get(tram + "/mt/thong-tin")).json()
        kq = {"bat": bool(d.get("bat")), "tram": tram, "quyen": d.get("quyen") or []}
    except Exception:
        kq = {"bat": False, "tram": tram}
    _tt_cache[tram] = (time.time(), kq)
    return kq


async def bat_dau(st: str, ve: str, quyen: list) -> dict:
    """Mở phiên ở trạm. Trả {ok, url, rieng(bytes)} - `rieng` giữ trong RAM để giải mã token."""
    rieng, kx = khoa_tam()
    d = await _goi("/mt/bat-dau", {"ve": ve, "st": st, "kx": kx, "quyen": list(quyen or [])})
    if not d.get("ok"):
        return {"ok": False, "loi": d.get("loi") or "Trạm từ chối."}
    return {"ok": True, "url": d["url"], "rieng": rieng}


async def nhan(phien: str, rieng: bytes) -> dict:
    d = await _goi("/mt/nhan", {"phien": phien})
    if not d.get("ok"):
        return {"ok": False, "loi": "Không nhận được token từ trạm (" + str(d.get("loi") or "") + ")."}
    tk = mo_niem_phong(d.get("goi") or {}, rieng)
    if not tk or not tk.get("access_token"):
        return {"ok": False, "loi": "Không giải mã được token từ trạm."}
    return {"ok": True, "token": tk}


async def gia_han(token: str) -> Optional[dict]:
    rieng, kx = khoa_tam()
    d = await _goi("/mt/gia-han", {"token": token, "kx": kx})
    if not d.get("ok"):
        return None
    return mo_niem_phong(d.get("goi") or {}, rieng)
