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
    """Gửi một tin từ Hộp thư. Markdown (thường do A.I. soạn) thành định dạng Zalo ở chat riêng, chữ trơn ở nhóm
    (26.10.314); không có dấu nào thì đi thẳng MCP như cũ."""
    import zalo_dinh_dang
    tron, kieu = zalo_dinh_dang.sang_zalo(str(text or ""))
    if tron != str(text or "") or kieu:
        if kieu and str(chat_type or "") != "group":
            kq = await gui_dinh_dang(str(tk.get("id") or tk.get("external_id") or ""), str(chat_id), tron, kieu)
            if kq is not None:
                return kq
        text = tron
    return await _gui_mcp(tk, chat_id, text, chat_type)


async def _gui_mcp(tk: dict, chat_id: str, text: str, chat_type: str = "private"):
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
    # 26.10.306 (học Javis 0.282): Zalo báo "thành công" mà không có id tin nghĩa là tin không đi
    # (phiên vừa bị nơi khác giành). Báo hỏng để Hộp thư không hiện như đã gửi trong khi khách
    # không thấy gì. Chỉ xét khi MCP CÓ trả khoá messageId (bản cũ không trả thì giữ như trước).
    if isinstance(d, dict) and d.get("success") is True and "messageId" in d and not d.get("messageId"):
        return False, "Zalo không xác nhận tin đã gửi (có thể nick đang mở ở nơi khác giành kết nối)"
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


async def gui_dinh_dang(conn_id: str, thread: str, cau: str, styles: list):
    """Gửi MỘT tin chat riêng KÈM định dạng Zalo (đậm, nghiêng, màu...) bằng lệnh `msg send --style` của
    chính zalo-agent-cli (tool MCP `zalo_send_message` chỉ nhận chữ trơn). 26.10.314.

    Trả `(ok, lỗi)` khi đã có kết cục, hoặc None khi CHƯA gửi gì và người gọi nên gửi chữ trơn qua MCP.
    Hết giờ là kết cục KHÔNG RÕ (CLI có thể đã gửi xong mới bị giết): không gửi lại, kẻo khách nhận hai tin."""
    import zalo_dinh_dang
    import zalo_personal_channel as zc
    them = zalo_dinh_dang.tham_so_style(styles)
    if not them or time.time() < float(_CLI_NGHI.get(conn_id) or 0):
        return None
    try:
        conn = zc.ket_noi_theo_id(conn_id)
        argv = lenh_cli(conn, "msg", "send", str(thread), str(cau), "-t", "0", *them)
        if not argv:
            return None
        import os
        env = dict(os.environ)
        env.update({k: str(v) for k, v in (conn.get("env") or {}).items()})
        import winproc
        proc = await asyncio.create_subprocess_exec(
            *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
            **winproc.kwargs_no_window())
    except Exception as e:
        print(f"[zalo-personal] không chạy được lệnh gửi có định dạng, gửi chữ thường: {e}", file=sys.stderr)
        return None
    try:
        await asyncio.wait_for(proc.communicate(), timeout=25)
    except asyncio.TimeoutError:
        proc.kill()
        return False, "không rõ tin có định dạng đã tới khách chưa (lệnh gửi quá 25 giây)"
    if proc.returncode != 0:
        # Lỗi thật (phiên bản CLI, đăng nhập): nghỉ đường này một lúc, tin vẫn đi bằng chữ thường.
        _CLI_NGHI[conn_id] = time.time() + CLI_NGHI_GIAY
        print(f"[zalo-personal] gửi có định dạng thoát mã {proc.returncode}, gửi chữ thường", file=sys.stderr)
        return None
    return True, ""


CLI_NGHI_GIAY = 600         # gửi có định dạng hỏng thì nghỉ đường CLI chừng này giây
_CLI_NGHI: dict = {}        # conn_id -> giờ được thử lại đường CLI

# "Đang soạn tin" trong lúc bot viết câu trả lời chat riêng (26.10.314, theo Javis 0.413). Cần tool MCP
# `zalo_send_typing`; zalo-agent-cli 1.6.2 (bản mới nhất đang có) CHƯA có tool này, nên lần thử đầu báo lỗi và
# kết nối đó nghỉ GO_NGHI giây. Câu trả lời không bao giờ phải chờ dòng này.
GO_TOOL = "zalo_send_typing"
GO_TRE = 1.5                # giây: lượt xong nhanh (im lặng, chủ tiếp quản) thì không hiện gì
GO_NHIP = 4.0               # Zalo tự tắt dòng "đang soạn tin" sau vài giây
GO_NGHI = 3600
_GO_NGHI: dict = {}         # conn_id -> giờ được thử lại


async def bao_dang_soan(conn_id: str, thread: str) -> bool:
    """Hiện "đang soạn tin" ở một chat riêng. True khi Zalo nhận. Không bao giờ ném lỗi."""
    import zalo_personal_channel as zc
    cid = str(conn_id or "")
    if time.time() < float(_GO_NGHI.get(cid) or 0):
        return False
    conn = zc.ket_noi_theo_id(cid)
    if not conn:
        return False
    try:
        d = await zc._goi(conn, GO_TOOL, {"threadId": str(thread), "threadType": 0, "type": 0})
    except Exception as e:      # bản cũ: "Tool zalo_send_typing not found"
        _GO_NGHI[cid] = time.time() + GO_NGHI
        print(f"[zalo-personal] chưa bật được \"đang soạn tin\" ({str(e)[:120]}), thử lại sau "
              f"{GO_NGHI // 60} phút", file=sys.stderr)
        return False
    if isinstance(d, dict) and d.get("success") is False:
        _GO_NGHI[cid] = time.time() + GO_NGHI
        return False
    return True


async def giu_dang_soan(conn_id: str, thread: str) -> None:
    """Chạy suốt lúc bot viết; người gọi huỷ khi xong. Dừng hẳn ngay lần đầu Zalo không nhận."""
    await asyncio.sleep(GO_TRE)
    while await bao_dang_soan(conn_id, thread):
        await asyncio.sleep(GO_NHIP)


GIOI_HAN_TIN = 1800   # ký tự mỗi tin: Zalo từ chối tin quá dài, khách chẳng nhận được gì


def chia_tin(cau: str, gioi_han: int = GIOI_HAN_TIN) -> list:
    """Cắt câu dài thành nhiều tin, ưu tiên cắt ở hết đoạn, rồi hết câu, rồi dấu cách. Giữ nguyên
    thứ tự, không làm rơi chữ nào (trừ khoảng trắng đầu/cuối mỗi mảnh)."""
    cau = str(cau or "").strip()
    if len(cau) <= gioi_han:
        return [cau] if cau else []
    mang = []
    while len(cau) > gioi_han:
        cat = -1
        for dau in ("\n\n", "\n", ". ", "? ", "! ", " "):
            i = cau.rfind(dau, 0, gioi_han)
            if i >= gioi_han // 3:
                cat = i + (len(dau) if dau.strip() == "" else len(dau) - 1)
                break
        if cat <= 0:
            cat = gioi_han
        mang.append(cau[:cat].strip())
        cau = cau[cat:].strip()
    if cau:
        mang.append(cau)
    return [m for m in mang if m]


GOM_GIAY = 5   # chat riêng: đợi khách im ngần này giây rồi mới trả lời một lần


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
        self._dem = {}          # thread -> {evs, task}: tin chat riêng đang chờ gom

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
        # Chat riêng: chữ, ảnh (có hay không có chú thích) và file. Nhóm: tin chữ, và ảnh/file CÓ
        # CAPTION (chữ đi kèm ảnh tính như một tin: "@Bot giá cái này?" gửi kèm ảnh thì bot phải trả lời).
        if not nhom and (ev.get("chat_type") != "private" or loai not in ("text", "image", "file")):
            return
        if nhom and not zalo_nhom.la_chu_thich(loai, text):
            if loai == "file":
                zc.xu_ly_tep_nhom(self.conn_id, ev)
            return
        if not thread or (not text and (nhom or loai == "text")):
            return
        if time.time() - float(ev.get("created_at") or 0) > zc.TUOI_TOI_DA:
            return
        if nhom:
            if zc.chu_vua_nhan_tay(self.conn_id, thread):
                return
            meta = self._meta(ev, thread, True)
            md = ev.get("metadata") or {}
            meta["mentioned"] = zalo_nhom.co_goi_ten(text, md.get("mentions"), self._ten_goi())
            meta["reply_to_bot"] = zc.la_tra_loi_bot(self.conn_id, thread, md.get("replyTo"))
            # File trong nhóm (26.10.306): file kèm lời gọi bot thì đọc luôn; người vừa gửi file
            # trơn (xem `xu_ly_tep_nhom`) rồi gọi bot thì bot nhận lại đúng file đó.
            tep = zc.tep_cua_tin(ev)
            if meta["mentioned"] or meta["reply_to_bot"]:
                tep = tep or (zc.lay_tep_tron(self.conn_id, thread, str(ev.get("sender_id") or "")) or [None])[-1]
                if tep:
                    meta["tep_url"], meta["tep_ten"] = tep["url"], tep["ten"]
            await self._tra_loi(thread, text, meta, True)
            return
        # Chat riêng: gom các tin khách nhắn liền nhau rồi trả lời MỘT lần (xem _gom).
        self._gom(thread, ev)

    def _meta(self, ev: dict, thread: str, nhom: bool) -> dict:
        import zalo_personal_channel as zc
        return {
            "chat_id": thread, "chat_type": "group" if nhom else "private",
            "chat_title": str(ev.get("chat_title") or "") if nhom else "",
            "user_id": str(ev.get("sender_id") or thread),
            "user_name": str(ev.get("sender_name") or ""), "username": "",
            "message_id": str(ev.get("external_message_id") or ""),
            "account_id": self.conn_id,
            # Tag Zalo chủ gắn cho cuộc chat này (Gia đình, Khách...), 26.10.306. Đọc bộ nhớ đệm,
            # không chờ mạng: chưa có thì để trống, lượt không bị giữ lại vì nó.
            "zalo_labels": zc.nhan_cua_chat(self.conn_id, thread),
        }

    # ---- gom tin chat riêng ----------------------------------------------------------
    def _gom(self, thread: str, ev: dict):
        """Khách nhắn một ý thành mấy tin liền: đợi họ im GOM_GIAY giây rồi đáp một lần đủ ý.
        Chủ vừa tự nhắn cuộc chat này thì GIỮ tin lại thay vì bỏ: chủ trả lời trong TAY_IM giây
        thì bỏ phần giữ (khách đã được phục vụ), hết hạn mà chủ chưa trả lời thì bot đáp một lần."""
        d = self._dem.setdefault(thread, {"evs": [], "task": None})
        d["evs"].append(ev)
        if d["task"] and not d["task"].done():
            d["task"].cancel()
        d["task"] = asyncio.get_running_loop().create_task(self._doi_roi_tra_loi(thread))

    async def _doi_roi_tra_loi(self, thread: str):
        import zalo_personal_channel as zc
        try:
            await asyncio.sleep(GOM_GIAY)
            while True:
                d = self._dem.get(thread) or {}
                evs = list(d.get("evs") or [])
                if not evs or zc._BOTS.get(self.conn_id) is not self:
                    return           # bot đã tắt: không gửi gì
                cuoi = max(float(e.get("created_at") or 0) for e in evs) or time.time()
                tay = float(zc._TAY.get((self.conn_id, thread)) or 0)
                if tay and tay >= cuoi:
                    d["evs"] = []    # chủ đã tự trả lời sau tin khách: bỏ phần giữ
                    return
                if tay and cuoi - tay < zc.TAY_IM:
                    # Chủ đang nói chuyện ở đây từ trước khi khách nhắn: chờ tới khi đủ TAY_IM
                    # kể từ tin khách mà chủ vẫn im.
                    cho = cuoi + zc.TAY_IM - time.time()
                    if cho > 0:
                        await asyncio.sleep(min(cho, 60))
                        continue
                break
            d["evs"] = []
            await self._tra_loi_gom(thread, evs)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"[:300]
            print(f"[zalo-personal bot {self.conn_id}] gom tin hỏng: {self.last_error}", file=sys.stderr)

    async def _tra_loi_gom(self, thread: str, evs: list):
        import zalo_personal_channel as zc
        dong = []
        anh = ""
        tep = None
        for e in evs:
            loai = str(e.get("message_type") or "text")
            t = str(e.get("text") or "").strip()
            if loai == "image":
                anh = str((e.get("metadata") or {}).get("image_url") or anh)
                dong.append(t or "[Khách gửi một ảnh]")
            elif loai == "file":
                # 26.10.306: file có link tải thì bot đọc được (PDF, Word, Excel, chữ trơn), xem
                # `chatbot_runtime.tep_cho_bot`. Không có link thì nói thật là chưa mở được.
                tep = zc.tep_cua_tin(e) or tep
                ten = (tep or {}).get("ten") or str((e.get("metadata") or {}).get("fileName") or "")
                nhan = f"[Khách gửi file{': ' + ten if ten else ''}]" if tep else \
                    f"[Khách gửi file{': ' + ten if ten else ''}. Bot chưa mở được file, hãy nói rõ và hỏi khách cần gì]"
                dong.append(nhan if not t or t.startswith("[") else t + " " + nhan)
            else:
                dong.append(t)
        text = "\n".join(x for x in dong if x).strip()
        if not text:
            return
        meta = self._meta(evs[-1], thread, False)
        if anh:
            meta["co_anh"] = True
            # 0.74.1: the photo's link, so the bot can actually look at it (see `chatbot_runtime.anh_cho_bot`).
            meta["image_url"] = anh
        if tep:
            meta["tep_url"], meta["tep_ten"] = tep["url"], tep["ten"]
        await self._tra_loi(thread, text, meta, False)

    async def _tra_loi(self, thread: str, text: str, meta: dict, nhom: bool):
        import zalo_personal_channel as zc
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
                # "Đang soạn tin" chỉ ở chat riêng: trong nhóm phần lớn lượt kết thúc bằng im lặng, hiện dòng đó
                # rồi không nói gì trông như người đổi ý.
                go = None if nhom else asyncio.get_running_loop().create_task(giu_dang_soan(self.conn_id, thread))
                try:
                    out = await self.answer_fn(text, meta, None)
                finally:
                    if go is not None:
                        go.cancel()
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
        import zalo_dinh_dang
        specs = []
        nhom = bool(meta and meta.get("chat_type") == "group")
        if nhom:
            # Tin nhóm đi bằng tag thật, vị trí tag tính trên chữ trơn: bỏ dấu Markdown TRƯỚC khi gắn tag.
            cau = zalo_dinh_dang.bo_dinh_dang(cau)
            # Tag người vừa hỏi, và đổi "@Tên" khác thành tag thật khi khớp đúng một thành viên.
            try:
                tv = zalo_nhom.thanh_vien(conversations.tin_gan_day("zalo_personal", self.conn_id, thread, 60))
            except Exception:
                tv = {}
            cau, specs = zalo_nhom.gan_tag(cau, str(meta.get("user_id") or ""),
                                           str(meta.get("user_name") or ""), tv)
        # Bot tự tách câu thành vài tin ngắn bằng [TACH_TIN] (26.10.306); phần nào còn dài quá thì
        # vẫn cắt tiếp. Trong nhóm chỉ tin đầu mới kèm tag.
        import bot_dau_hieu
        manh = [x for p in (bot_dau_hieu.cac_tin(cau) or [cau]) for x in (chia_tin(p) or [p])] or [cau]
        for i, m in enumerate(manh):
            if nhom:
                # Nhớ TRƯỚC khi gửi: tiếng vọng có thể về vòng đọc ngay trong nhịp kế tiếp.
                zc.ghi_da_gui(self.conn_id, thread, m)
                ok, loi = await gui_co_tag(self.conn_id, thread, m, specs if i == 0 else [])
            else:
                # Chat riêng: Markdown thành chữ đậm/màu của Zalo; tiếng vọng về là chữ trơn nên nhớ bản trơn.
                tron, kieu = zalo_dinh_dang.sang_zalo(m)
                zc.ghi_da_gui(self.conn_id, thread, tron)
                kq = await gui_dinh_dang(self.conn_id, thread, tron, kieu) if kieu else None
                ok, loi = kq if kq is not None else await gui({"id": self.conn_id}, thread, tron, "private")
            if not ok:
                self.last_error = f"Gửi Zalo lỗi: {loi}"[:300]
                print(f"[zalo-personal bot {self.conn_id}] {self.last_error}", file=sys.stderr)
                zc.bao_gui_hong(self.conn_id, thread, m, loi,
                                "group" if meta and meta.get("chat_type") == "group" else "private")
                return
            if i + 1 < len(manh):
                await asyncio.sleep(0.8)
