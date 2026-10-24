"""che_do_thu.py - CHẠY THỬ AN TOÀN (shadow) cho Trụ 2 "tự học có đối chứng" (26.10.217).

Vì sao có module này: Harness² (Google Research) cải tiến một agent bằng cách CHẠY THẬT nhiều
biến thể của nó trên cùng một việc rồi so trajectory. Bài báo chạy trong container nên chạy bao
nhiêu lần cũng không chạm ra đời thật. MinMin thì khác: một trợ lý ở mức full tạo đơn, chạy ads,
gửi Zalo, đăng Fanpage bằng tool thật. Chạy thử 12 lượt nghĩa là có thể gửi 12 tin nhắn thật.

Nên mọi lượt chạy thử mang một CỜ (mã lượt "h2-..."), và lớp quyền cứng của hub đọc cờ đó:
  - tool MCP loại ghi/nguy hiểm: KHÔNG gọi, chỉ ghi lại Ý ĐỊNH (tên tool + tham số đã che bí
    mật) rồi trả câu "GIẢ LẬP" để agent làm tiếp như thật;
  - plugin min_mode safe/full (javis_task, zalo_send_image, fb_page_post...): giả lập y vậy;
  - javis_write_file: chỉ ghi được khi brain là thư mục tạm của lượt thử (trong STATE_DIR/harness);
  - hub không được tự suy ra "brain đang mở" khi lượt thử thiếu/sai header brain (suy ra là rơi
    về brain THẬT của chủ).

Hai đường mang cờ, như mã việc nền của once_ledger:
  - engine API chạy trong tiến trình server: ContextVar `CO` (tool gọi trong cùng task asyncio);
  - engine CLI (Claude Code) gọi hub qua HTTP từ tiến trình con: header `X-Javis-Shadow` ghi vào
    file cấu hình MCP RIÊNG của lượt; hub đọc header rồi gắn ContextVar cho lượt gọi đó.

Cờ chỉ có thể SIẾT, không bao giờ nới: ai có hub token mà gửi header này thì chỉ tự làm mình mất
quyền ghi. Nên không cần bí mật hoá mã lượt.

Module THUẦN (chỉ stdlib + secret_redact), không import main/hub, để test đứng một mình được.
Không dùng ký tự gạch dài.
"""
from __future__ import annotations

import contextvars
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

HEADER = "X-Javis-Shadow"
# Mã lượt: "h2-" + chữ/số/gạch. Mã lạ bị bỏ (coi như không có cờ) - một header rác không được
# biến thành cờ "bật" với khoá lạ làm sổ ý định phình vô hạn.
_MA_RE = re.compile(r"^h2-[A-Za-z0-9_\-]{1,80}$")

CO: contextvars.ContextVar[str] = contextvars.ContextVar("che_do_thu_co", default="")

# Gốc DUY NHẤT nơi brain tạm của lượt thử được phép nằm. main/harness2_noi đặt bằng `dat_goc`
# lúc khởi động (STATE_DIR/harness). Chưa đặt thì javis_write_file ở chế độ thử luôn bị giả lập.
_GOC: Dict[str, Optional[Path]] = {"tam": None}

# Sổ ý định theo mã lượt. Hub chạy CÙNG tiến trình với bộ chạy thử (CLI gọi ngược về chính
# server này), nên giữ trong RAM là đủ; có trần để một lượt chạy loạn không ăn hết bộ nhớ.
_SO: Dict[str, List[dict]] = {}
_KHOA = threading.Lock()
_TRAN_MOI_LUOT = 400

_KHOA_NHAY_CAM = ("token", "key", "secret", "password", "pass", "auth", "cookie", "otp", "pin",
                  "credential", "session")


def ma_hop_le(ma: str) -> bool:
    return bool(_MA_RE.match(str(ma or "")))


def bat(ma: str):
    """Gắn cờ chạy thử cho ngữ cảnh hiện tại. Trả token để `tat`. Mã sai = không gắn gì."""
    return CO.set(ma if ma_hop_le(ma) else "")


def tat(token) -> None:
    try:
        CO.reset(token)
    except Exception:
        pass


def hien_tai() -> str:
    """Mã lượt thử đang chạy, "" nếu đây là lượt thật."""
    return CO.get() or ""


def dang_bat() -> bool:
    return bool(CO.get())


def dat_goc(p) -> None:
    """Đặt gốc chứa brain tạm (STATE_DIR/harness). Gọi một lần lúc khởi động."""
    try:
        _GOC["tam"] = Path(p).expanduser().resolve()
    except Exception:
        _GOC["tam"] = None


def goc_tam() -> Optional[Path]:
    return _GOC["tam"]


def la_brain_tam(vault_root) -> bool:
    """vault_root có nằm TRONG gốc brain tạm không. Chỉ khi đó javis_write_file mới ghi thật."""
    goc = _GOC["tam"]
    if not goc or not vault_root:
        return False
    try:
        p = Path(vault_root).expanduser().resolve()
    except Exception:
        return False
    return p != goc and goc in p.parents


# ─────────────────────────── che bí mật ───────────────────────────

def _che_chuoi(s: str) -> str:
    try:
        import secret_redact
        return secret_redact.redact_secrets(s)
    except Exception:
        return s


def che(v: Any, _sau: int = 0) -> Any:
    """Bản sao tham số đã che: khoá nhạy cảm -> "***", chuỗi qua bộ che secret, cắt dài."""
    if _sau > 6:
        return "..."
    if isinstance(v, dict):
        ra = {}
        for k, x in list(v.items())[:40]:
            ks = str(k)
            if any(n in ks.lower() for n in _KHOA_NHAY_CAM):
                ra[ks] = "***"
            else:
                ra[ks] = che(x, _sau + 1)
        return ra
    if isinstance(v, (list, tuple)):
        return [che(x, _sau + 1) for x in list(v)[:40]]
    if isinstance(v, str):
        s = _che_chuoi(v)
        return s if len(s) <= 2000 else s[:2000] + f"...(+{len(s) - 2000} ký tự)"
    return v


# ─────────────────────────── sổ ý định ───────────────────────────

def ghi_y_dinh(tool: str, args: Any, *, nguon: str, loai: str = "", ly_do: str = "") -> dict:
    """Ghi một hành động BỊ GIẢ LẬP vào sổ của lượt thử đang chạy. Trả bản ghi."""
    ma = hien_tai()
    rec = {"ts": round(time.time(), 3), "tool": str(tool or ""), "nguon": nguon,
           "loai": loai or "", "args": che(args if isinstance(args, dict) else {"_": args}),
           "ly_do": ly_do or ""}
    if not ma:
        return rec
    with _KHOA:
        ds = _SO.setdefault(ma, [])
        if len(ds) < _TRAN_MOI_LUOT:
            ds.append(rec)
    return rec


def lay_y_dinh(ma: str, xoa: bool = True) -> List[dict]:
    """Các ý định đã ghi của một lượt thử (mặc định lấy xong thì xoá khỏi RAM)."""
    with _KHOA:
        ds = list(_SO.get(ma) or [])
        if xoa:
            _SO.pop(ma, None)
    return ds


def cau_gia_lap(tool: str, loai: str = "") -> str:
    """Câu trả về cho model thay cho kết quả thật.

    KHÔNG bắt đầu bằng "ERROR:" có chủ ý: lượt thử phải đi tiếp như lượt thật thì trajectory mới
    so được với nhau. Một câu lỗi làm agent rẽ sang nhánh xử lý lỗi, và cả lượt thử thành bằng
    chứng về một tình huống không bao giờ xảy ra ngoài đời."""
    them = f" (loại việc: {loai})" if loai else ""
    return (f"GIẢ LẬP (chạy thử): đã không thực hiện {tool}{them}. Đây là lượt chạy thử của "
            f"MinMin để so sánh cách làm, hành động ra ngoài được ghi lại thay vì làm thật. Coi "
            f"như lời gọi đã được nhận và làm tiếp phần còn lại như bình thường.")


def tom_tat(ds: List[dict]) -> str:
    """Một dòng mỗi ý định, cho người đọc màn so sánh."""
    out = []
    for r in ds or []:
        a = json.dumps(r.get("args") or {}, ensure_ascii=False)
        if len(a) > 160:
            a = a[:157] + "..."
        out.append(f"{r.get('tool')} {a}")
    return "\n".join(out)
