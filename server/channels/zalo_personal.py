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
            # zalo-agent-cli 1.6.2 đặt tên tham số là `threadType`; `type` giữ lại cho bản cũ.
            # Chỉ gửi `type` thì zod gạt nó đi, loại tin rơi về 0 và tin NHÓM đi như tin riêng.
            "threadType": 1 if str(chat_type or "") == "group" else 0,
            "type": 1 if str(chat_type or "") == "group" else 0,
        })
    except Exception as e:
        return False, str(e)[:300]
    if isinstance(d, dict) and d.get("success") is False:
        return False, str(d.get("error") or d.get("message") or "Zalo từ chối")[:300]
    return True, ""


def lenh_cli(conn: dict, *dong_lenh: str):
    """Dựng argv chạy zalo-agent-cli bằng ĐÚNG gói đã ghim ở kết nối (cùng phiên bản với MCP,
    cùng thư mục đăng nhập). None nếu kết nối không phải dạng `npx ... mcp start`."""
    args = list((conn or {}).get("args") or [])
    if not conn or conn.get("command") != "npx" or args[-2:] != ["mcp", "start"]:
        return None
    return ["npx", *args[:-2], *[str(x) for x in dong_lenh]]


async def gui_co_tag(conn_id: str, thread: str, cau: str, specs: list):
    """Gửi vào NHÓM kèm tag thật (người được tag nhận thông báo). Tool MCP `zalo_send_message`
    không có tham số tag, nên đi bằng lệnh `msg send --mention` của chính zalo-agent-cli, dùng
    đúng thư mục đăng nhập của kết nối này. Hỏng bất cứ chỗ nào thì rơi về gửi chữ thường qua
    MCP: câu vẫn tới nhóm, chỉ mất hiệu ứng thông báo."""
    import zalo_personal_channel as zc
    if not specs:
        return await gui({"id": conn_id}, thread, cau, "group")
    try:
        conn = zc.ket_noi_theo_id(conn_id)
        argv = lenh_cli(conn, "msg", "send", str(thread), str(cau), "-t", "1",
                        "--mention", *[str(x) for x in specs])
        if not argv:
            raise RuntimeError("không dựng được lệnh CLI")
        import os
        env = dict(os.environ)
        env.update({k: str(v) for k, v in (conn.get("env") or {}).items()})
        import winproc
        proc = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
            **winproc.kwargs_no_window())
        try:
            await asyncio.wait_for(proc.communicate(), timeout=25)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("CLI quá hạn")
        if proc.returncode != 0:
            raise RuntimeError(f"CLI thoát mã {proc.returncode}")
        return True, ""
    except Exception as e:
        print(f"[zalo-personal] gửi có tag lỗi, gửi chữ thường: {e}", file=sys.stderr)
        return await gui({"id": conn_id}, thread, cau, "group")


async def gui_tep(conn_id: str, thread: str, path: str, loai_chat: str = "private", loai_tep: str = "tep"):
    """Gửi MỘT ảnh/video/tài liệu. Tool MCP chỉ có chữ, nên đi bằng lệnh `msg send-image` /
    `msg send-file` của chính zalo-agent-cli (cùng gói đã ghim, cùng thư mục đăng nhập)."""
    import zalo_personal_channel as zc
    try:
        conn = zc.ket_noi_theo_id(conn_id)
        sub = "send-image" if loai_tep == "anh" else "send-file"
        argv = lenh_cli(conn, "--json", "msg", sub, str(thread), str(path),
                        "-t", "1" if str(loai_chat) == "group" else "0")
        if not argv:
            return False, "không dựng được lệnh CLI"
        import os
        env = dict(os.environ)
        env.update({k: str(v) for k, v in (conn.get("env") or {}).items()})
        import winproc
        proc = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
            **winproc.kwargs_no_window())
        try:
            _o, e = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill()
            return False, "gửi file quá 3 phút chưa xong"
        if proc.returncode != 0:
            return False, (e or b"").decode("utf-8", "replace").strip()[-200:] or f"CLI thoát mã {proc.returncode}"
        return True, ""
    except Exception as ex:
        return False, f"{type(ex).__name__}: {ex}"[:200]


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
          - chat riêng nhận chữ và ảnh có chú thích; nhóm dùng các luật riêng;
          - tin cũ quá `TUOI_TOI_DA` bỏ qua (bộ đệm MCP lúc mới bật);
          - chủ vừa TỰ TAY nhắn cuộc chat này thì nhường;
          - rồi tới các luật chung của bot (Tiếp quản, giới hạn tần suất) trong `answer_fn`;
          - cuối cùng chính bot tự quyết: Agent viết `[IM_LANG]` nghĩa là không gửi gì.
        """
        import zalo_personal_channel as zc
        import zalo_nhom
        nhom = ev.get("chat_type") == "group"
        loai = str(ev.get("message_type") or "text")
        text = str(ev.get("text") or "").strip()
        thread = str(ev.get("external_chat_id") or "")
        # Chat riêng: chữ hoặc ảnh có chú thích. Nhóm: tin chữ, và ảnh/file CÓ CAPTION (chữ đi kèm ảnh tính
        # như một tin: "@Bot giá cái này?" gửi kèm ảnh thì bot phải trả lời).
        if not nhom and (ev.get("chat_type") != "private" or loai not in ("text", "image")):
            return
        if (nhom or loai == "image") and not zalo_nhom.la_chu_thich(loai, text):
            return
        if not text or not thread:
            return
        if time.time() - float(ev.get("created_at") or 0) > zc.TUOI_TOI_DA:
            return
        if zc.chu_vua_nhan_tay(self.conn_id, thread):
            return
        meta = {
            "chat_id": thread, "chat_type": "group" if nhom else "private",
            "chat_title": str(ev.get("chat_title") or "") if nhom else "",
            "user_id": str(ev.get("sender_id") or thread),
            "user_name": str(ev.get("sender_name") or ""), "username": "",
            "message_id": str(ev.get("external_message_id") or ""),
            "account_id": self.conn_id,
        }
        if loai == "image":
            meta["co_anh"] = True
            # 0.74.1: the photo's link, so the bot can actually look at it (see `chatbot_runtime.anh_cho_bot`).
            meta["image_url"] = str((ev.get("metadata") or {}).get("image_url") or "")
        if nhom:
            md = ev.get("metadata") or {}
            meta["mentioned"] = zalo_nhom.co_goi_ten(text, md.get("mentions"), self._ten_goi())
            meta["reply_to_bot"] = zc.la_tra_loi_bot(self.conn_id, thread, md.get("replyTo"))
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
                    # CHỈ file trong thư viện chủ duyệt (cờ `thu_vien`): file engine tự sinh trong
                    # brain không tự bay ra Zalo của người lạ.
                    tep = [f for f in (out.get("files") or []) if isinstance(f, dict) and f.get("thu_vien")]
                else:
                    cau = str(out or "").strip()
                    tep = []
                if cau:
                    await self._gui(thread, cau, meta if nhom else None)
                for f in tep[:4]:
                    zc.ghi_tep_da_gui(self.conn_id, thread)
                    ok, loi = await gui_tep(self.conn_id, thread, f["path"],
                                            "group" if nhom else "private", str(f.get("loai") or "tep"))
                    if not ok:
                        self.last_error = f"Gửi file Zalo lỗi: {loi}"[:300]
                        print(f"[zalo-personal bot {self.conn_id}] {self.last_error}", file=sys.stderr)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"[:300]
                print(f"[zalo-personal bot {self.conn_id}] lượt hỏng: {self.last_error}",
                      file=sys.stderr)

    def _ten_goi(self) -> list:
        """Các tên mà khách có thể gọi con bot này: tên bot gắn với tài khoản và tên tài khoản."""
        import zalo_personal_channel as zc
        ten = []
        try:
            c = zc.ket_noi_theo_id(self.conn_id)
            if c and c.get("label"):
                ten.append(str(c["label"]))
            import chatbot_store
            for b in chatbot_store.list_bots():
                ids = [str((a or {}).get("id") if isinstance(a, dict) else a) for a in (b.get("accounts") or [])]
                if self.conn_id in ids and b.get("name"):
                    ten.append(str(b["name"]))
        except Exception:
            pass
        return ten

    async def _gui(self, thread: str, cau: str, meta=None):
        import zalo_personal_channel as zc
        import zalo_nhom, conversations
        specs = []
        if meta and meta.get("chat_type") == "group":
            # Tag người vừa hỏi, và đổi "@Tên" khác thành tag thật khi khớp đúng một thành viên.
            try:
                tv = zalo_nhom.thanh_vien(conversations.tin_gan_day("zalo_personal", self.conn_id, thread, 60))
            except Exception:
                tv = {}
            cau, specs = zalo_nhom.gan_tag(cau, str(meta.get("user_id") or ""),
                                           str(meta.get("user_name") or ""), tv)
        # Nhớ TRƯỚC khi gửi: tiếng vọng có thể về vòng đọc ngay trong nhịp kế tiếp.
        zc.ghi_da_gui(self.conn_id, thread, cau)
        if meta and meta.get("chat_type") == "group":
            ok, loi = await gui_co_tag(self.conn_id, thread, cau, specs)
        else:
            ok, loi = await gui({"id": self.conn_id}, thread, cau, "private")
        if not ok:
            self.last_error = f"Gửi Zalo lỗi: {loi}"[:300]
            print(f"[zalo-personal bot {self.conn_id}] {self.last_error}", file=sys.stderr)
