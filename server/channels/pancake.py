"""Kênh Pancake (26.10.315): mỗi Fanpage trong Pancake là một tài khoản của Hộp thư. Đọc và gửi ở `pancake_inbox`.

Kind "account": tài khoản là Page của kết nối Thống kê Pancake ở trang Kết nối (không có token riêng ở đây). Công tắc
Ghi hội thoại bật/tắt từng Page. Gắn được Bot chuyên trách: bot SOẠN NHÁP chờ chủ duyệt, chỉ tự gửi khi chủ bật
"A.I. tự trả lời" riêng cho Page đó.
"""
from __future__ import annotations

import asyncio
import sys

from channels import KenhSpec

SPEC = KenhSpec(
    id="pancake", nhan="Pancake", kind="account", logo="pancake", mau="#F26B21",
    tom_tat=("Fanpage đã có trong Pancake. Nhân viên vẫn trả lời trong Pancake; A.I. mặc định chỉ soạn nháp chờ duyệt."),
    nang_luc={"nhom": False, "gui_chu": True, "gui_file": False},
)


def tai_khoan():
    import pancake_inbox
    return pancake_inbox.tai_khoan()


def bat(account_id: str, on: bool) -> dict:
    import pancake_inbox
    return pancake_inbox.bat(account_id, on)


def trang_thai() -> dict:
    import pancake_inbox
    return pancake_inbox.trang_thai()


def cho_che_do(account_id: str, mode: str) -> tuple:
    """Hook cho route đổi chế độ: "A.I. tự trả lời" chỉ được khi Page đã bật riêng."""
    import pancake_inbox
    return pancake_inbox.cho_che_do(account_id, mode)


def dat_tu_tra_loi(account_id: str, on: bool, xac_nhan: bool = False) -> dict:
    import pancake_inbox
    return pancake_inbox.dat_tu_tra_loi(account_id, on, xac_nhan)


def tu_tra_loi(account_id: str) -> bool:
    import pancake_inbox
    return pancake_inbox.tu_tra_loi(account_id)


async def gui(tk: dict, chat_id: str, text: str, chat_type: str = "private"):
    import pancake_inbox
    return await pancake_inbox.gui(str(tk.get("id") or ""), str(chat_id), str(text or ""))


GOM_GIAY = 6   # khách nhắn một ý thành mấy tin: đợi chừng này giây rồi soạn một lần


class Transport:
    """Lớp vận chuyển cho bot trên một Page Pancake, đúng khế ước `chatbot_runtime.start_bot`.

    Không tự đọc: vòng đọc `pancake_inbox` là nguồn duy nhất và đưa tin khách mới qua `xu_ly`. `token` ở đây là
    page_id (tài khoản ảo, xem `channel_accounts.get_token`)."""

    def __init__(self, token, whitelist, answer_fn, command_fn=None, download_dir=None,
                 commands=None, precheck_fn=None, event_fn=None, giau_trang_thai=True, **_):
        self.page_id = str(token or "")
        self.account_id = self.page_id
        self.answer_fn = answer_fn
        self.precheck_fn = precheck_fn
        self.status = "off"
        self.last_error = ""
        self._task = None
        self._khoa = {}
        self._cho = {}

    def start(self):
        import pancake_inbox
        pancake_inbox.dang_ky_bot(self.page_id, self)
        self.status = "starting"
        self._task = asyncio.get_running_loop().create_task(self._giam_sat())

    def stop(self):
        import pancake_inbox
        pancake_inbox.huy_dang_ky_bot(self.page_id, self)
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        self.status = "off"

    async def _giam_sat(self):
        import pancake_inbox
        while True:
            try:
                tt = pancake_inbox._TT.get(self.page_id) or {}
                if not pancake_inbox.page(self.page_id):
                    self.status, self.last_error = "error", "Page này không còn trong kết nối Thống kê Pancake."
                elif tt.get("loi"):
                    self.status, self.last_error = "error", str(tt["loi"])
                elif tt.get("lan_cuoi"):
                    self.status, self.last_error = "polling", ""
                else:
                    self.status = "starting"
            except Exception:      # noqa: BLE001
                pass
            await asyncio.sleep(10)

    async def xu_ly(self, chat_id: str, evs: list):
        """Tin khách mới của một hội thoại: gom vài giây rồi soạn (hoặc tự trả lời nếu Page đã bật) một lần."""
        d = self._cho.setdefault(chat_id, {"evs": [], "task": None})
        d["evs"].extend(evs)
        if d["task"] and not d["task"].done():
            d["task"].cancel()
        d["task"] = asyncio.get_running_loop().create_task(self._doi(chat_id))

    async def _doi(self, chat_id: str):
        try:
            await asyncio.sleep(GOM_GIAY)
            d = self._cho.get(chat_id) or {}
            evs, d["evs"] = list(d.get("evs") or []), []
            if evs:
                await self.tra_loi(chat_id, evs)
        except asyncio.CancelledError:
            raise
        except Exception as e:      # noqa: BLE001
            self.last_error = f"{type(e).__name__}: {e}"[:300]
            print(f"[pancake bot {self.page_id}] {self.last_error}", file=sys.stderr)

    async def tra_loi(self, chat_id: str, evs: list):
        import conversations
        import pancake_inbox as pi
        pid = self.page_id
        dong, anh = [], ""
        for e in evs:
            t = str(e.get("text") or "").strip()
            if e.get("loai") == "image" and e.get("url"):
                anh = str(e["url"])
            dong.append(t)
        text = "\n".join(x for x in dong if x).strip()
        if not text:
            return
        cuoi = evs[-1]
        meta = {"chat_id": chat_id, "chat_type": "private", "chat_title": "",
                "user_id": str(cuoi.get("sender_id") or chat_id), "user_name": str(cuoi.get("sender_name") or ""),
                "username": "", "message_id": str(cuoi.get("id") or ""), "account_id": pid}
        if anh:
            meta.update(co_anh=True, image_url=anh)
        khoa = self._khoa.setdefault(chat_id, asyncio.Lock())
        async with khoa:
            mode = conversations.che_do(pi.KENH, pid, chat_id)
            if mode == "human":
                return
            if mode == "ai" and not pi.tu_tra_loi(pid):
                cid = conversations.conversation_id_of(pi.KENH, pid, chat_id)
                if cid:
                    conversations.dat_che_do(cid, "draft")
            if self.precheck_fn:
                r = self.precheck_fn(text, meta)
                if asyncio.iscoroutine(r):
                    r = await r
                if r is not None:
                    return        # bot chọn im (chat chưa cho phép...): Pancake không gửi câu cố định nào
            out = await self.answer_fn(text, meta, None)
            cau = str((out or {}).get("text") or "").strip() if isinstance(out, dict) else str(out or "").strip()
            if not cau or (isinstance(out, dict) and out.get("im_lang")):
                return
            # Chốt cuối: chỉ gửi khi Page đã bật tự trả lời VÀ cuộc chat vẫn ở "A.I. tự trả lời". Còn lại giữ làm nháp.
            cid = conversations.conversation_id_of(pi.KENH, pid, chat_id)
            if not pi.tu_tra_loi(pid) or conversations.che_do(pi.KENH, pid, chat_id) != "ai":
                if cid:
                    conversations.save_draft(cid, cau, conversations.last_customer_message_id(cid))
                return
            ok, loi = await pi.gui(pid, chat_id, cau)
            if not ok:
                self.last_error = f"Gửi Pancake lỗi: {loi}"[:300]
                # Không tự gửi lại. Cuộc chat vẫn hiện "khách chờ" ở Hộp thư để người trực xử lý.
                print(f"[pancake bot {pid}] {self.last_error}", file=sys.stderr)
            else:
                self.last_error = ""
                self.status = "polling"
