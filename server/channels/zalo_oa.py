"""Kênh Zalo OA (Official Account, API chính thức OA Open API v3), 26.10.314. Lớp vận chuyển và webhook ở
`zalo_oa_kenh`; token dùng chung kho với cầu nối Zalo OA ở trang Kết nối (một OA một kho, xem đầu file đó).

Khác kênh `zalo` (Zalo Bot, bot tạo trong "Zalo Bot Manager") và `zalo_personal` (nick Zalo của chủ): OA là
trang doanh nghiệp khách bấm Quan tâm. Tài khoản kiểu "bot" (lưu ở kho tài khoản kênh) nhưng tin vào bằng
webhook, nên khai thêm `WEBHOOK_PATH` để form Thêm kênh hiện địa chỉ cần dán sang Zalo."""
from __future__ import annotations

from channels import KenhSpec

SPEC = KenhSpec(
    id="zalo_oa", nhan="Zalo OA", kind="bot", logo="zalo", mau="#0068FF",
    lay_token=("Cần MinMin mở bằng tên miền HTTPS. Ở developers.zalo.me tạo app, liên kết OA, xác thực tên miền "
               "(dán mã vào ô bên dưới), đặt webhook bằng địa chỉ bên dưới và bật các sự kiện user_send_*. Rồi dán "
               "bốn thứ cách nhau dấu cách: App ID, App secret key, OA secret key, Refresh token."),
    tom_tat=("Hộp thư Zalo Official Account của shop. Chỉ chat riêng; khách lâu không nhắn thì Zalo không cho OA "
             "trả lời tự do nữa."),
    nang_luc={"nhom": False, "gui_chu": True, "gui_file": True},
)

WEBHOOK_PATH = "/zalo-oa/webhook"


def _Transport():
    from zalo_oa_kenh import ZaloOABot
    return ZaloOABot


class _Lazy:
    def __call__(self, *a, **kw):
        return _Transport()(*a, **kw)


Transport = _Lazy()


async def verify_token(token: str) -> dict:
    import zalo_oa_kenh
    r = await zalo_oa_kenh.lien_ket(token)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error") or "Không liên kết được Zalo OA"}
    return {"ok": True, "username": r["oa_id"], "bot_name": r.get("ten") or "", "vao_duoc_nhom": False,
            "account_type": "oa"}


def token_luu(token: str, external_id: str = "") -> str:
    """Chuỗi lưu vào kho tài khoản kênh: chỉ id kết nối, không bao giờ là bí mật. Rỗng = chưa liên kết."""
    import zalo_oa_kenh
    cid = zalo_oa_kenh.tim_ket_noi(token, external_id)
    return zalo_oa_kenh.chuoi_luu(cid) if cid else ""


async def gui(tk: dict, chat_id: str, text: str, chat_type: str = "private"):
    tok = str(tk.get("token") or "").strip()
    if not tok:
        return False, "tài khoản Zalo OA này chưa liên kết"
    bot = _Transport()(tok, "", None, giau_trang_thai=True)
    return await bot.send_text(chat_id, text)
