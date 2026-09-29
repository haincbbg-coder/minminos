"""Kênh Zalo CÁ NHÂN: tài khoản đã quét QR ở trang Kết nối (MCP `zalo-agent-cli`). Đọc tin bằng
vòng cursor ở `zalo_personal_channel`, gửi tin bằng tool `zalo_send_message` của chính MCP đó.

Gửi từ kênh này là gửi DƯỚI DANH TÍNH CHỦ (không phải bot), nên Hộp thư nói rõ điều đó ở ô
soạn tin; ngoài ra nó là một kênh như mọi kênh khác, không có mục riêng nào trên giao diện.

Từ 0.64.80 kênh này gắn được Bot chuyên trách (lớp `Transport` cuối file). Bot tự trả lời và tự
quyết có nên trả lời không; các rào nằm ở `Transport.xu_ly`.
"""
from __future__ import annotations

import asyncio
import sys
import time

from channels import KenhSpec

SPEC = KenhSpec(
    id="zalo_personal", nhan="Zalo cá nhân", kind="account", logo="zalo", mau="#0068FF",
    tom_tat="Tài khoản Zalo của chính bạn. Bot trực thì tự trả lời chat riêng dưới tên bạn.",
    nang_luc={"nhom": True, "gui_chu": True, "gui_file": False},
)


def tai_khoan():
    import zalo_personal_channel
    return zalo_personal_channel.tai_khoan()


def bat(account_id: str, on: bool) -> dict:
    import zalo_personal_channel
    return zalo_personal_channel.bat(account_id, on)


def trang_thai() -> dict:
    import zalo_personal_channel
    return zalo_personal_channel.trang_thai()


async def gui(tk: dict, chat_id: str, text: str, chat_type: str = "private"):
    """Gửi qua MCP: tham số theo mcp-guide của zalo-agent-cli (threadId, text, type 0|1)."""
    import zalo_personal_channel
    conn = zalo_personal_channel.ket_noi_theo_id(str(tk.get("id") or tk.get("external_id") or ""))
    if not conn:
        return False, "tài khoản Zalo này không còn ở trang Kết nối (hoặc đang tắt)"
    try:
        d = await zalo_personal_channel._goi(conn, "zalo_send_message", {
            "threadId": str(chat_id), "text": str(text or ""),
            "type": 1 if str(chat_type or "") == "group" else 0,
        })
    except Exception as e:
        return False, str(e)[:300]
    if isinstance(d, dict) and d.get("success") is False:
        return False, str(d.get("error") or d.get("message") or "Zalo từ chối")[:300]
    return True, ""


class Transport:
    """Lớp vận chuyển cho bot trên Zalo cá nhân, đúng khế ước của `chatbot_runtime.start_bot`.

    KHÔNG tự đọc tin: vòng đọc của `zalo_personal_channel` là nguồn duy nhất (một cursor, hai
    người đọc là mất tin của nhau). Lớp này đăng ký ở đó, được đưa từng tin khách mới, và gửi
    câu trả lời bằng `gui`. `token` ở đây là id kết nối Zalo (xem `channel_accounts.get_token`).
    """

    def __init__(self, token, whitelist, answer_fn, command_fn=None, download_dir=None,
                 commands=None, precheck_fn=None, event_fn=None, giau_trang_thai=True, **_):
        self.conn_id = str(token or "")
        self.answer_fn = answer_fn
        self.precheck_fn = precheck_fn
        self.account_id = self.conn_id
        self.status = "off"
        self.last_error = ""
        self._task = None
        self._khoa = {}         # thread -> Lock: một cuộc chat một lượt, khỏi trả lời chồng nhau

    # ---- vòng đời ------------------------------------------------------------------
    def start(self):
        import zalo_personal_channel as zc
        zc.dang_ky_bot(self.conn_id, self)
        self.status = "starting"
        self._task = asyncio.get_running_loop().create_task(self._giam_sat())

    def stop(self):
        import zalo_personal_channel as zc
        zc.huy_dang_ky_bot(self.conn_id, self)
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        self.status = "off"

    async def _giam_sat(self):
        """Đo sức khoẻ để thẻ bot nói thật: chấm xanh chỉ khi vòng đọc đang đọc được."""
        import zalo_personal_channel as zc
        while True:
            try:
                tt = zc._TT.get(self.conn_id) or {}
                if not zc.ket_noi_theo_id(self.conn_id):
                    self.status = "error"
                    self.last_error = ("Kết nối Zalo này không còn (hoặc đang tắt) ở trang Kết nối, "
                                       "bot không nhận được tin.")
                elif tt.get("loi"):
                    self.status = "error"
                    self.last_error = str(tt["loi"])
                elif tt.get("lan_cuoi"):
                    self.status = "polling"
                    self.last_error = ""
                else:
                    self.status = "starting"
            except Exception:
                pass
            await asyncio.sleep(10)

    # ---- một tin khách ---------------------------------------------------------------
    async def xu_ly(self, ev: dict):
        """Quyết định có trả lời một tin khách không, và trả lời nếu có.

        Các rào, theo thứ tự rẻ tới đắt (cái nào chặn thì KHÔNG tốn một lượt model):
          - chỉ chat RIÊNG dạng CHỮ (nhóm và ảnh/tiếng/file bỏ qua: chủ chưa giao việc đó);
          - tin cũ quá `TUOI_TOI_DA` bỏ qua (bộ đệm MCP lúc mới bật);
          - chủ vừa TỰ TAY nhắn cuộc chat này thì nhường;
          - rồi tới các luật chung của bot (Tiếp quản, giới hạn tần suất) trong `answer_fn`;
          - cuối cùng chính bot tự quyết: Agent viết `[IM_LANG]` nghĩa là không gửi gì.
        """
        import zalo_personal_channel as zc
        if ev.get("chat_type") != "private" or ev.get("message_type") != "text":
            return
        text = str(ev.get("text") or "").strip()
        thread = str(ev.get("external_chat_id") or "")
        if not text or not thread:
            return
        if time.time() - float(ev.get("created_at") or 0) > zc.TUOI_TOI_DA:
            return
        if zc.chu_vua_nhan_tay(self.conn_id, thread):
            return
        meta = {
            "chat_id": thread, "chat_type": "private", "chat_title": "",
            "user_id": str(ev.get("sender_id") or thread),
            "user_name": str(ev.get("sender_name") or ""), "username": "",
            "message_id": str(ev.get("external_message_id") or ""),
            "account_id": self.conn_id,
        }
        khoa = self._khoa.setdefault(thread, asyncio.Lock())
        async with khoa:
            try:
                if self.precheck_fn:
                    r = self.precheck_fn(text, meta)
                    if asyncio.iscoroutine(r):
                        r = await r
                    if r is not None:           # {} = im, {"reply": ...} = một câu cố định
                        cau = str((r or {}).get("reply") or "").strip()
                        if cau:
                            await self._gui(thread, cau)
                        return
                out = await self.answer_fn(text, meta, None)
                if isinstance(out, dict):
                    if out.get("im_lang"):
                        return
                    cau = str(out.get("text") or "").strip()
                else:
                    cau = str(out or "").strip()
                if cau:
                    await self._gui(thread, cau)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"[:300]
                print(f"[zalo-personal bot {self.conn_id}] lượt hỏng: {self.last_error}",
                      file=sys.stderr)

    async def _gui(self, thread: str, cau: str):
        import zalo_personal_channel as zc
        # Nhớ TRƯỚC khi gửi: tiếng vọng có thể về vòng đọc ngay trong nhịp kế tiếp.
        zc.ghi_da_gui(self.conn_id, thread, cau)
        ok, loi = await gui({"id": self.conn_id}, thread, cau, "private")
        if not ok:
            self.last_error = f"Gửi Zalo lỗi: {loi}"[:300]
            print(f"[zalo-personal bot {self.conn_id}] {self.last_error}", file=sys.stderr)
