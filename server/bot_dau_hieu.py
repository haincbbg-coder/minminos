"""Hai dấu hiệu Agent của bot được viết trong câu trả lời, và cách MinMin đọc chúng (26.10.306).

Cả hai học ý từ Javis 0.280 và 0.282, viết lại cho MinMin:

1. `[BAO_CHU]`: tin nhắn RIÊNG khó quá (giá riêng, khiếu nại, hoàn tiền, việc phải để chủ quyết),
   bot không đoán mà im với khách và báo chủ ở chuông, kèm khách nhắn gì và vì sao bot không tự
   trả lời. Chỉ dạy ở chat riêng khi bot để chế độ "Tự phán đoán" (`reply_when == "judge"`); nhưng
   dấu hiệu này bị BẮT ở mọi lượt, vì để lọt chữ `[BAO_CHU]` tới khách là kết cục tệ nhất.

2. `[TACH_TIN]`: bot tự quyết nhắn vài tin ngắn thay vì một khối dài. Chỉ Zalo cá nhân gửi từng
   phần thành tin riêng (`KENH_TACH`); mọi nơi khác (kênh khác, Hộp thư, nhật ký bot, bản nháp
   cho chủ) nhận bản gộp, dấu hiệu thành một dòng trống. MinMin không tự cắt câu theo dòng trống:
   dòng trống trong một tin là cách viết bình thường.
"""
from __future__ import annotations

import re
import sys
import time
from typing import Any, Dict, List, Optional

IM_LANG = "[IM_LANG]"
BAO_CHU = "[BAO_CHU]"
GHI_CHU_TOI_DA = 300
CHUONG_CACH = 600          # giây: một cuộc chat báo chuông nhiều nhất một lần mỗi 10 phút
_DA_BAO: Dict[tuple, float] = {}

TACH_TIN = "[TACH_TIN]"
TOI_DA_TIN = 4             # quá số này đọc như spam: phần thừa gộp vào tin cuối
KENH_TACH = ("zalo_personal",)
_TACH_RE = re.compile(r"\s*\[\s*tach_tin\s*\]\s*", re.I)

CAU_BAO_CHU = f"""
## Tin nhắn RIÊNG: câu khó thì im và báo chủ

Chủ để bot này ở chế độ Tự phán đoán. Với tin nhắn riêng này bạn có ba cách xử lý:

- Trả lời bình thường khi tin đúng là việc vai của bạn phụ trách và hướng dẫn vai hoặc tài liệu
  cho bạn đủ căn cứ để trả lời chắc chắn.
- Viết đúng một dòng `{IM_LANG}` khi tin không cần ai hồi đáp (chỉ "ok", cảm ơn khi việc đã xong)
  hoặc không thuộc việc của vai.
- Viết `{BAO_CHU}` rồi MỘT câu ngắn cho chủ (người nhắn cần gì, vì sao bạn không tự trả lời) khi tin
  là việc thật cần hồi đáp nhưng bạn KHÔNG trả lời chắc chắn được: hướng dẫn vai và tài liệu không
  có thông tin đó, hoặc việc phải để chủ tự quyết (giá riêng, giảm giá, khiếu nại, hoàn tiền, hẹn
  lịch, cam kết thay chủ). Đừng đoán, đừng hứa. Người nhắn không nhận được chữ nào; MinMin báo chủ
  để chủ trả lời tay.

Hướng dẫn vai của chủ LUÔN thắng đoạn này: hướng dẫn vai đã nói cách xử lý một loại tin thì làm
đúng như vậy.
"""

CAU_TACH_TIN = f"""
## Nhắn nhiều tin ngắn

Khách đọc trên điện thoại. Khi câu trả lời có từ hai ý trở lên (ví dụ báo giá rồi gợi ý thêm), bạn
được tách thành nhiều tin ngắn như người thật nhắn: đặt một dòng chỉ có `{TACH_TIN}` giữa các tin,
tối đa {TOI_DA_TIN} tin. Mỗi tin một ý, vài câu. Câu trả lời chỉ có một ý thì gửi một tin.
"""


# ============================================================
# [BAO_CHU]
# ============================================================
def duoc_bao_chu(cfg: dict, meta: dict) -> bool:
    """Lượt này có được dạy cách thứ ba (im và báo chủ) không: chat RIÊNG, bot để Tự phán đoán.
    So khớp đúng chữ "judge": giá trị lạ thì giữ hành vi cũ."""
    return (str((meta or {}).get("chat_type") or "private") == "private"
            and (cfg or {}).get("reply_when") == "judge")


def ghi_chu_bao_chu(dap: Any) -> Optional[str]:
    """Câu bot ghi cho chủ khi câu trả lời có `[BAO_CHU]`, không có thì None ("" = có dấu mà
    không ghi gì). Mọi câu mang dấu này đều là báo chủ, KHÔNG BAO GIỜ là chữ gửi khách."""
    t = str(dap or "")
    i = t.lower().find(BAO_CHU.lower())
    if i < 0:
        return None
    con = (t[:i] + " " + t[i + len(BAO_CHU):]).replace(IM_LANG, " ")
    return " ".join(con.split())[:GHI_CHU_TOI_DA]


def la_im(dap: Any) -> bool:
    """Agent chọn không gửi gì cho khách: `[IM_LANG]` hoặc `[BAO_CHU]`."""
    t = str(dap or "").lower()
    return IM_LANG.lower() in t or BAO_CHU.lower() in t


def bao_chuong(cfg: dict, meta: dict, text: str, ghi_chu: str, now: Optional[float] = None) -> bool:
    """Báo chuông MinMin cho một tin bot để chủ trả lời. Mỗi cuộc chat nhiều nhất một lần mỗi
    `CHUONG_CACH` giây; khách hỏi dồn năm câu khó thì chuông kêu một lần, nhật ký bot vẫn đủ."""
    meta = meta or {}
    khoa = (str((cfg or {}).get("id") or ""), str(meta.get("chat_id") or ""))
    now = time.time() if now is None else now
    if now - _DA_BAO.get(khoa, 0.0) < CHUONG_CACH:
        return False
    if len(_DA_BAO) > 2000:
        _DA_BAO.clear()
    ai = str(meta.get("user_name") or meta.get("chat_id") or "Một khách")
    hoi = " ".join(str(text or "").split())[:400]
    than = (f"Bot \"{(cfg or {}).get('name') or 'bot'}\" không tự trả lời tin này mà để bố trả lời.\n\n"
            f"Khách nhắn: \"{hoi}\"" + (f"\n\nBot ghi chú: {ghi_chu}" if ghi_chu else "")
            + "\n\nMở trang Khách, Hộp thư để trả lời.")
    try:
        import inbox
        inbox.add(than, kind="system", title=f"{ai} cần bố trả lời", source="chatbot",
                  channel=str(meta.get("channel") or ""))
    except Exception as e:      # noqa: BLE001 - chuông hỏng không được làm gãy lượt bot
        print(f"[bot báo chủ] chuông lỗi: {type(e).__name__}: {e}", file=sys.stderr)
        return False
    _DA_BAO[khoa] = now
    return True


# ============================================================
# [TACH_TIN]
# ============================================================
def co_tach(text: Any) -> bool:
    return bool(_TACH_RE.search(str(text or "")))


def cac_tin(text: Any, toi_da: int = TOI_DA_TIN) -> List[str]:
    """Các tin của một câu trả lời, bỏ phần rỗng, nhiều nhất `toi_da` (phần thừa gộp vào tin cuối)."""
    ds = [p.strip() for p in _TACH_RE.split(str(text or ""))]
    ds = [p for p in ds if p]
    if len(ds) > toi_da:
        ds = ds[:toi_da - 1] + ["\n\n".join(ds[toi_da - 1:])]
    return ds


def gop(text: Any) -> str:
    """Câu trả lời thành MỘT tin: mỗi dấu tách thành một dòng trống. Cho kênh và bản ghi không tách."""
    if not co_tach(text):
        return str(text or "")
    return "\n\n".join(cac_tin(text, toi_da=10 ** 6))
