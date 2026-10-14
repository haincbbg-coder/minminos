"""hanh_dong.py - SỔ HÀNH ĐỘNG RA NGOÀI ĐỜI + QUYỀN THEO LOẠI VIỆC (Trụ 4, 26.10.139).

Vì sao cần: MinMin được phép tự làm việc thật qua connector (gửi tin Zalo, tạo đơn Pancake, đổi
ngân sách ads, xoá dữ liệu). Hub đã có nhật ký kỹ thuật theo từng kết nối (mcp_audit.jsonl),
nhưng người chủ cần một SỔ riêng chỉ ghi những việc đã CHẠM RA NGOÀI, trả lời bốn câu: ai làm,
lúc nào, làm gì (tham số nào), và có hoàn tác được không. Và quyền không còn là một công tắc
"full" chung: từng LOẠI việc (nhắn tin, đăng bài, đơn hàng, tiền, xoá) được cho phép hay chặn
riêng, cứng ở hub, không phụ thuộc prompt.

Thuần stdlib (đường dẫn sổ truyền vào hoặc đặt qua `dat_duong`). Hook ở mcp_hub._guard.

Loại việc (xếp theo độ nặng, xét từ nặng xuống nhẹ):
  xoa       xoá/huỷ không lấy lại được
  tien      tiền: thanh toán, ngân sách/giá thầu ads, hoàn tiền, chuyển khoản
  don_hang  đơn hàng, vận đơn, tồn kho, hoá đơn
  nhan_tin  gửi tin nhắn/email/thông báo cho người khác
  dang_bai  đăng/sửa bài, bình luận, tải nội dung lên
  khac      thao tác ghi khác
"""
from __future__ import annotations

import contextvars
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

LOAI = ("xoa", "tien", "don_hang", "nhan_tin", "dang_bai", "khac")
NHAN = {"xoa": "Xoá / huỷ", "tien": "Tiền & quảng cáo", "don_hang": "Đơn hàng & kho",
        "nhan_tin": "Nhắn tin & email", "dang_bai": "Đăng bài", "khac": "Ghi khác",
        # Không nằm trong LOAI (không có chính sách chặn): chỉ là dòng CẢNH BÁO dữ liệu vào
        # chứa câu nhắm vào AI (26.10.164). Nhãn để trang Kết nối hiện tên người đọc được.
        "tiem_lenh": "Cảnh báo tiêm lệnh"}
CHINH_SACH_HOP_LE = ("cho_phep", "chan", "hoi_truoc")

# Từ khoá trong TÊN TOOL (chữ thường). Xét theo thứ tự LOAI: xoá trước (nặng nhất).
_TU = {
    "xoa": ("delete", "remove", "destroy", "purge", "xoa", "huy_", "_huy", "cancel", "trash",
            "archive", "unpublish", "revoke"),
    "tien": ("pay", "payment", "charge", "refund", "budget", "bid", "spend", "transfer",
             "withdraw", "topup", "deposit", "campaign", "adset", "ad_set", "ads_", "_ads",
             "chuyen_khoan", "thanh_toan", "ngan_sach", "subscription", "billing"),
    "don_hang": ("order", "don_hang", "invoice", "hoa_don", "shipment", "van_don", "inventory",
                 "ton_kho", "stock", "product", "san_pham", "cart", "checkout", "fulfill"),
    "nhan_tin": ("send", "reply", "message", "sms", "mail", "email", "notify", "gui_", "_gui",
                 "nhan_tin", "tin_nhan", "broadcast", "dm_", "chat_"),
    "dang_bai": ("post", "publish", "upload", "comment", "tweet", "dang_bai", "bai_viet",
                 "story", "reel", "video", "media", "caption", "pin_"),
}
# Gợi ý theo CONNECTOR khi tên tool chung chung (create/update/write...).
_NHA = {
    "tien": ("ads", "meta", "facebook_ads", "google_ads", "tiktok_ads", "payment", "momo",
             "vnpay", "stripe", "paypal", "bank"),
    "don_hang": ("pancake", "pos", "sapo", "kiotviet", "haravan", "shopify", "woocommerce",
                 "lazada", "shopee", "tiktok_shop", "ghn", "ghtk", "viettelpost"),
    "nhan_tin": ("zalo", "telegram", "gmail", "mail", "slack", "discord", "messenger", "whatsapp",
                 "sms"),
    "dang_bai": ("facebook_page", "fanpage", "instagram", "tiktok", "youtube", "threads",
                 "linkedin", "x_", "twitter", "wordpress", "webcake"),
}
_HOAN_TAC = {
    "xoa": "KHÔNG hoàn tác được. Dữ liệu đã xoá chỉ lấy lại được nếu dịch vụ có thùng rác.",
    "tien": "Kiểm tra ngay trong trình quản lý quảng cáo/thanh toán; tiền đã chi có thể không hoàn được.",
    "don_hang": "Huỷ hoặc sửa lại đơn/vận đơn trong POS. Đơn đã giao cho vận chuyển thì phải gọi hãng.",
    "nhan_tin": "Không rút lại được tin đã gửi. Chỉ có thể gửi tin đính chính.",
    "dang_bai": "Gỡ bài bằng tool xoá/ẩn bài tương ứng của nền tảng.",
    "khac": "",
}
_KHOA_NHAY_CAM = ("token", "key", "secret", "password", "pass", "auth", "cookie", "otp", "pin")

NGUOI_LAM: contextvars.ContextVar[str] = contextvars.ContextVar("hanh_dong_nguoi_lam", default="")
_DUONG: Optional[Path] = None
_MAX_BYTES = 5_000_000


def dat_duong(p) -> None:
    global _DUONG
    _DUONG = Path(p)


def dat_nguoi_lam(ai: str):
    """Đặt 'ai đang làm' cho task hiện tại (web:<sid>, telegram:<chat>, loop:<slug>...). Trả token
    để reset nếu cần; ContextVar tự theo task con của asyncio."""
    return NGUOI_LAM.set(str(ai or ""))


def nguoi_lam() -> str:
    return NGUOI_LAM.get() or ""


# ─────────────────────────── phân loại việc ───────────────────────────

def loai_viec(connector_id: str, tool: str, args=None) -> str:
    """Loại việc của MỘT lời gọi tool GHI (cls != read). Tên tool quyết định trước, connector
    bổ sung khi tên tool chung chung. Không nhận ra -> 'khac'."""
    t = str(tool or "").lower()
    c = str(connector_id or "").lower()
    for loai in LOAI[:-1]:
        if any(k in t for k in _TU[loai]):
            return loai
    for loai in ("tien", "don_hang", "nhan_tin", "dang_bai"):
        if any(k in c for k in _NHA[loai]):
            return loai
    return "khac"


def hoan_tac(loai: str) -> str:
    return _HOAN_TAC.get(loai, "")


def cho_phep(chinh_sach: dict, loai: str) -> tuple:
    """(ok, lý do chặn). chinh_sach = {loai: 'cho_phep'|'chan'}; thiếu = cho phép (giữ hành vi cũ)."""
    gia_tri = str((chinh_sach or {}).get(loai) or "cho_phep").strip().lower()
    if gia_tri == "chan":
        return False, (f"Việc loại \"{NHAN.get(loai, loai)}\" đang bị CHẶN theo chính sách quyền "
                       f"của chủ (trang Kết nối, mục Quyền theo loại việc). MinMin không tự làm "
                       f"việc này; hãy nói lại cho người dùng để họ mở quyền hoặc tự làm tay.")
    return True, ""


def can_hoi(chinh_sach: dict, loai: str) -> bool:
    """Loại việc này đang ở mức HỎI TRƯỚC? (26.10.165: MinMin dừng lại, hỏi chủ, chủ gật thì làm)."""
    return str((chinh_sach or {}).get(loai) or "").strip().lower() == "hoi_truoc"


# ─────────────────────────── cổng hỏi trước (26.10.165) ───────────────────────────
# Mượn cách approval gate của Hermes: hành động ra ngoài thuộc loại chủ đặt "hỏi trước" thì
# tool KHÔNG chạy ngay; MinMin tạo một yêu cầu, báo chủ (khung chat, chuông, Telegram), và chờ
# chủ bấm Đồng ý/Từ chối trong vài phút. Gật thì chạy thật và ghi sổ "đã duyệt bởi ai"; lắc
# hay hết giờ thì tool trả lỗi nói rõ CHƯA LÀM, để model nói lại với chủ thay vì tự lách.

import asyncio
import secrets

_CHO: dict = {}          # id -> yêu cầu (có "event": asyncio.Event)
_THONG_BAO = None        # async fn(yeu_cau) do main đặt: đẩy ra khung chat / Telegram / chuông
HOI_TRUOC_GIAY_MAC_DINH = 180


def dat_thong_bao(fn) -> None:
    global _THONG_BAO
    _THONG_BAO = fn


def tao_yeu_cau(*, ai: str, tool: str, connector: str, label: str, loai: str, args) -> dict:
    yc = {"id": secrets.token_hex(4), "ts": datetime.now().isoformat(timespec="seconds"),
          "ai": ai or "?", "tool": tool, "connector": connector or "", "label": label or "",
          "loai": loai, "nhan_loai": NHAN.get(loai, loai), "args": tom_tat_args(args),
          "trang_thai": "cho", "nguoi_quyet": "", "event": asyncio.Event()}
    _CHO[yc["id"]] = yc
    # dọn yêu cầu cũ đã quyết quá 1 giờ
    for k in [k for k, v in _CHO.items() if v["trang_thai"] != "cho"
              and (datetime.now() - datetime.fromisoformat(v["ts"])).total_seconds() > 3600]:
        _CHO.pop(k, None)
    return yc


def _gon(yc: dict) -> dict:
    return {k: v for k, v in yc.items() if k != "event"}


def danh_sach_cho(ca_da_quyet: bool = False) -> list:
    ds = [_gon(v) for v in _CHO.values() if ca_da_quyet or v["trang_thai"] == "cho"]
    return sorted(ds, key=lambda x: x["ts"], reverse=True)


def quyet(ma: str, dong_y: bool, ai: str = "") -> tuple:
    """Chủ bấm nút. (ok, lý do). Chỉ yêu cầu đang chờ mới quyết được, một lần."""
    yc = _CHO.get(str(ma or ""))
    if not yc:
        return False, "không có yêu cầu này (có thể đã hết giờ chờ)"
    if yc["trang_thai"] != "cho":
        return False, f"yêu cầu đã được quyết: {yc['trang_thai']}"
    yc["trang_thai"] = "dong_y" if dong_y else "tu_choi"
    yc["nguoi_quyet"] = ai or "chủ"
    yc["event"].set()
    return True, ""


async def cho_quyet(yc: dict, timeout: float = HOI_TRUOC_GIAY_MAC_DINH) -> str:
    """Báo chủ rồi chờ. Trả 'dong_y' | 'tu_choi' | 'het_gio'."""
    if _THONG_BAO is not None:
        try:
            await _THONG_BAO(_gon(yc))
        except Exception:
            pass
    try:
        await asyncio.wait_for(yc["event"].wait(), timeout=max(5.0, float(timeout)))
    except asyncio.TimeoutError:
        if yc["trang_thai"] == "cho":
            yc["trang_thai"] = "het_gio"
    return yc["trang_thai"]


def chuan_hoa_chinh_sach(d) -> dict:
    """Chỉ giữ khoá hợp lệ + giá trị hợp lệ; còn lại bỏ. Dùng khi lưu từ UI."""
    ra = {}
    for k, v in (d or {}).items():
        if k in LOAI and str(v).strip().lower() in CHINH_SACH_HOP_LE:
            ra[k] = str(v).strip().lower()
    return ra


# ─────────────────────────── sổ hành động ───────────────────────────

def tom_tat_args(args, max_len: int = 160) -> str:
    """Tham số gọi tool, rút gọn cho người đọc, CHE giá trị nhạy cảm (token/key/password...)."""
    if not isinstance(args, dict) or not args:
        return ""
    phan = []
    for k, v in list(args.items())[:8]:
        ks = str(k)
        if any(x in ks.lower() for x in _KHOA_NHAY_CAM):
            phan.append(f"{ks}=***")
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        v = re.sub(r"\s+", " ", str(v))
        if len(v) > 40:
            v = v[:37] + "..."
        phan.append(f"{ks}={v}")
    s = ", ".join(phan)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def ghi(rec: dict) -> None:
    """Thêm một dòng vào sổ (JSONL, tự xoay khi quá 5MB). Không bao giờ ném lỗi ra ngoài."""
    if _DUONG is None:
        return
    try:
        if _DUONG.exists() and _DUONG.stat().st_size > _MAX_BYTES:
            _DUONG.replace(_DUONG.with_suffix(".jsonl.1"))
        _DUONG.parent.mkdir(parents=True, exist_ok=True)
        with _DUONG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def dong_so(*, ai: str, tool: str, connector: str, label: str, loai: str, cls: str, mode: str,
            ok: bool, ms: int, args, err: str = "", luc: Optional[str] = None) -> dict:
    return {"ts": luc or datetime.now().isoformat(timespec="seconds"), "ai": ai or "?",
            "tool": tool, "connector": connector or "", "label": label or "", "loai": loai,
            "cls": cls, "mode": mode or "full", "ok": bool(ok), "ms": int(ms or 0),
            "args": tom_tat_args(args), "err": str(err or "")[:200], "hoan_tac": hoan_tac(loai)}


def doc(limit: int = 100, loai: str = "", chi_loi: bool = False) -> list:
    """Dòng mới nhất trước. Lọc theo loại việc hoặc chỉ dòng lỗi/bị chặn."""
    if _DUONG is None or not _DUONG.exists():
        return []
    try:
        lines = _DUONG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    ra = []
    for line in reversed(lines):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if loai and r.get("loai") != loai:
            continue
        if chi_loi and r.get("ok"):
            continue
        ra.append(r)
        if len(ra) >= limit:
            break
    return ra


def thong_ke(limit: int = 2000) -> dict:
    """Đếm theo loại + số bị chặn, cho thẻ tóm tắt trên trang Kết nối."""
    ds = doc(limit)
    dem = {l: 0 for l in LOAI}
    chan = 0
    tiem = 0
    for r in ds:
        if r.get("loai") == "tiem_lenh":
            tiem += 1
            continue
        dem[r.get("loai") if r.get("loai") in dem else "khac"] += 1
        if not r.get("ok") and "CHẶN" in str(r.get("err") or ""):
            chan += 1
    return {"tong": len(ds), "theo_loai": dem, "bi_chan": chan, "tiem_lenh": tiem}
