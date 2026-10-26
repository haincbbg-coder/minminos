"""Hộp tin VIỆC HÀNG NGÀY (26.10.259).

Vấn đề (chủ repo báo 2026-10-26): kết quả của Bảng việc và Lịch tự chạy (loop, nhắc hẹn,
theo dõi trang web) đổ thẳng vào hội thoại đang dùng, tức là hội thoại đã tạo ra việc đó. Một
loop chạy 30 phút một lần là cứ nửa tiếng lại một thẻ chen giữa cuộc trò chuyện đang dở.

Cách làm: mọi tin việc nền đáng lẽ vào một khung chat web thì nay vào MỘT trong hai hội thoại
cố định, cả hai nằm trong mục (project) "Việc Hàng Ngày":
  - "Bảng Việc"     - việc Kanban, câu hỏi của việc nền, GATE của đội AI.
  - "Lịch Tự Chạy"  - loop, nhắc hẹn, theo dõi trang web.
Hội thoại đầy (TRAN_TIN tin hoặc TRAN_CHU ký tự) thì mở "phần 2", "phần 3"... vẫn trong mục đó.

Luật giữ nguyên ý người dùng:
  - Mục tìm theo TÊN đã bỏ dấu ("viec hang ngay"), nên mục chủ repo tự tạo được dùng luôn. Chưa
    có thì tạo. Bị xoá thì lần sau tạo lại.
  - Hội thoại bị lưu trữ, bị xoá, hoặc bị người dùng kéo ra khỏi mục: coi như đã nghỉ, mở cái
    mới. Không kéo ngược nó về, vì đó là một thao tác người dùng cố ý làm.
  - Chỉ đổi đích của tin đang đi vào KHUNG CHAT WEB ("web:<mã phiên>"). Tin đi Telegram/Zalo
    giữ nguyên, vì người dùng giao việc từ điện thoại muốn nhận về điện thoại.

Mã phiên đang dùng lưu ở <STATE_DIR>/viec-hang-ngay.json, theo từng bộ não. Ghi chú: không
dùng ký tự em dash ở bất kỳ đâu.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import unicodedata
from pathlib import Path
from typing import Any, Callable, Optional

TEN_MUC = "Việc Hàng Ngày"
ICON_MUC = "calendar-check"
TEN_HOP = {"bang": "Bảng Việc", "lich": "Lịch Tự Chạy"}
# Loại việc nền -> hộp. Loại "job" (việc chạy nền giao ngay trong một lượt chat) KHÔNG có ở
# đây: đó là câu trả lời cho chính lượt chat ấy, phải về đúng khung đã hỏi.
KIND_HOP = {"task": "bang", "gate": "bang", "loop": "lich", "reminder": "lich", "watch": "lich"}
# "Đầy dung lượng": loop 30 phút cộng vài nhắc hẹn là khoảng 70 tin một ngày, nên 1000 tin là
# hơn hai tuần. Trần ký tự để một hội thoại toàn báo cáo dài không thành khối nặng khi mở.
TRAN_TIN = 1000
TRAN_CHU = 3_000_000
WEB = "web:"


def chuan_ten(s: Any) -> str:
    """Tên đã bỏ dấu, chữ thường, gom khoảng trắng: "Việc  Hàng Ngày" -> "viec hang ngay"."""
    t = unicodedata.normalize("NFD", str(s or "")).replace("đ", "d").replace("Đ", "D")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def hop_cua(viec: Any) -> str:
    """Hộp ("bang" | "lich") của một khối việc, "" khi tin này không thuộc hộp nào."""
    if not isinstance(viec, dict):
        return ""
    return KIND_HOP.get(str(viec.get("kind") or ""), "")


class HopViec:
    """Tìm/tạo mục Việc Hàng Ngày và hai hội thoại của nó. An toàn đa luồng."""

    def __init__(self, store_getter: Callable[[], Any], state_path: Path,
                 bat: Optional[Callable[[], bool]] = None,
                 brain_keys: Optional[Callable[[str], list]] = None):
        self._store = store_getter
        # Mọi cách viết cùng trỏ về một bộ não ("brain", "/brains/Brain Default"...). 26.10.260:
        # mục chủ repo tạo mang khoá "brain" còn hội thoại mang khoá đường dẫn, so đúng một
        # chuỗi là không thấy mục và đẻ ra mục thứ hai mà danh sách không hiện.
        self._keys = brain_keys or (lambda b: [b])
        self._path = Path(state_path)
        self._bat = bat or (lambda: True)
        self._lock = threading.Lock()

    # ── trạng thái ──
    def _doc(self) -> dict:
        try:
            d = json.loads(self._path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}

    def _ghi(self, d: dict) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tam = self._path.with_suffix(".tmp")
            tam.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            tam.replace(self._path)
        except Exception as e:
            print(f"[viec-hang-ngay] ghi trạng thái lỗi: {type(e).__name__}: {e}", file=sys.stderr)

    # ── mục ──
    def muc(self, brain: str) -> str:
        """id của mục Việc Hàng Ngày trong bộ não này, tạo nếu chưa có."""
        st = self._store()
        dich = chuan_ten(TEN_MUC)
        keys = self._cac_khoa(brain)
        thay = [p for k in keys for p in (st.list_projects(k) or [])
                if chuan_ten(p.get("name")) == dich]
        if thay:
            # Nhiều mục trùng tên: lấy mục CŨ nhất, tức mục người dùng tự tạo trước.
            thay.sort(key=lambda p: float(p.get("created_at") or 0))
            return str(thay[0]["id"])
        # Tạo bằng khoá ngắn "brain" khi có: đó là khoá danh sách hội thoại đang đọc.
        return st.create_project(TEN_MUC, icon=ICON_MUC,
                                 brain="brain" if "brain" in keys else keys[0])

    def _cac_khoa(self, brain: str) -> list:
        try:
            keys = [str(k) for k in (self._keys(brain) or []) if k]
        except Exception:
            keys = []
        return keys or [brain]

    def _day(self, sid: str, sess: dict) -> bool:
        if int(sess.get("msg_count") or 0) >= TRAN_TIN:
            return True
        try:
            rows = self._store()._read(
                "SELECT COALESCE(SUM(LENGTH(content)), 0) AS n FROM messages WHERE session_id = ?",
                (sid,))
            return int(rows[0]["n"]) >= TRAN_CHU if rows else False
        except Exception:
            return False

    def phien(self, brain: str, hop: str) -> str:
        """Mã hội thoại đang nhận tin của hộp `hop` trong bộ não `brain`. Đầy/mất thì mở mới."""
        if hop not in TEN_HOP:
            return ""
        brain = str(brain or "brain")
        with self._lock:
            st = self._store()
            pid = self.muc(brain)
            data = self._doc()
            cua_nao = data.setdefault(brain, {})
            cu = cua_nao.get(hop) if isinstance(cua_nao.get(hop), dict) else {}
            sid = str(cu.get("sid") or "")
            phan = max(1, int(cu.get("phan") or 1))
            sess = st.get_session(sid) if sid else None
            if (sess and str(sess.get("brain") or "") in self._cac_khoa(brain)
                    and not int(sess.get("archived") or 0)
                    and str(sess.get("project_id") or "") == pid):
                if not self._day(sid, sess):
                    return sid
                phan += 1
            ten = TEN_HOP[hop] if phan == 1 else f"{TEN_HOP[hop]} · phần {phan}"
            sid = st.create_session(brain=brain, title=ten, channel="web")
            st.set_project(sid, pid)
            cua_nao[hop] = {"sid": sid, "phan": phan, "project_id": pid}
            self._ghi(data)
            return sid

    def doi_dich(self, owner_chat: Any, viec: Any = None, hop: str = "") -> str:
        """owner_chat mới cho một tin việc nền. Không thuộc diện thì trả nguyên owner_chat.

        Chỉ đổi khi tin đang đi vào khung chat web. Lỗi bất kỳ cũng trả nguyên đích cũ: thà
        tin rơi vào hội thoại cũ còn hơn mất tin."""
        cid = str(owner_chat or "").strip()
        hop = hop or hop_cua(viec)
        if not hop or not cid.startswith(WEB):
            return cid
        try:
            if not self._bat():
                return cid
            goc = cid[len(WEB):]
            sess = self._store().get_session(goc) if goc else None
            if not sess:
                return cid
            # Tin của chính hội thoại trong mục (ví dụ người dùng giao việc ngay trong "Bảng
            # Việc") vẫn đi qua phien() để đúng hộp và đúng luật đầy.
            moi = self.phien(str(sess.get("brain") or "brain"), hop)
            return (WEB + moi) if moi else cid
        except Exception as e:
            print(f"[viec-hang-ngay] đổi đích lỗi, giữ hội thoại cũ: {type(e).__name__}: {e}",
                  file=sys.stderr)
            return cid
