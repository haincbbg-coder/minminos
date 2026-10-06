"""Bộ phát sự kiện cho VĂN PHÒNG AI 3D (khoang não): ai đang làm việc gì, đang đi gặp ai.

Mỗi lần workflow chạy (web, Kanban, nhắc hẹn, loop đều đi qua `_ghi_lich_su`) bắn vài sự kiện
nhẹ vào một vòng đệm trong RAM. Trình duyệt hỏi `GET /office/events?since=<seq>` mỗi giây rưỡi
và điều khiển các robot đi lại theo đúng việc thật. Không ghi đĩa, không giữ gì sau khi khởi
động lại (văn phòng chỉ cần hiện tại). Mất sự kiện cũng không hỏng gì: robot chỉ đứng yên.

Loại sự kiện (trường `k`):
- run_start  {run, name}                  một lần chạy bắt đầu
- step       {run, agent, prev, task}     `agent` nhận bước mới; `prev` là người làm bước trước
                                          (nếu có) để robot đi lấy dữ liệu tận bàn người đó
- tool       {run, agent, tool}           agent gọi công cụ (đi tới trạm dữ liệu của công cụ)
- verify     {run, agent, target}         người kiểm chứng đi tới bàn người vừa làm
- step_done  {run, agent, out}            bước xong; `out` là đoạn đầu của đầu ra bước (để robot đứng dậy trình bày)
- run_end    {run, ok}                    lần chạy kết thúc (ok False = lỗi)
"""
import threading
import time
from collections import deque

_BUF = deque(maxlen=500)
_LOCK = threading.Lock()
_SEQ = 0


def emit(k: str, brain: str = "", **kw) -> int:
    """Thêm một sự kiện, trả về số thứ tự. Không bao giờ ném lỗi ra ngoài."""
    global _SEQ
    try:
        with _LOCK:
            _SEQ += 1
            ev = {"seq": _SEQ, "t": round(time.time(), 2), "k": k, "brain": brain}
            for key, v in kw.items():
                ev[key] = (v[:(400 if key == "out" else 160)] if isinstance(v, str) else v)
            _BUF.append(ev)
            return _SEQ
    except Exception:
        return 0


def since(n: int = 0, brain: str = "") -> dict:
    """Mọi sự kiện có seq > n (của brain đó nếu truyền). `seq` trả về là mốc mới nhất.

    Nếu client giữ mốc cũ hơn vòng đệm (hoặc server vừa khởi động lại, mốc nhỏ hơn) thì chỉ
    trả phần còn lại, và `reset` = True khi mốc client lớn hơn mốc server để nó đồng bộ lại.
    """
    with _LOCK:
        cur = _SEQ
        evs = [e for e in _BUF if e["seq"] > n and (not brain or not e["brain"] or e["brain"] == brain)]
    return {"seq": cur, "reset": n > cur, "events": evs[-120:]}


def _reset_for_tests() -> None:
    global _SEQ
    with _LOCK:
        _BUF.clear()
        _SEQ = 0
