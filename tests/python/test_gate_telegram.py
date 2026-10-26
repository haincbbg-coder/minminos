"""Đội AI - GATE trên Telegram: tin báo có nút Duyệt / Từ chối / Xem chi tiết (Phase 02).

    python tests/run.py gate_telegram      (KHÔNG mạng)

Hợp đồng ở plans/doi-ai-gate/PLAN.md mục "Telegram / thông báo". Hàng đợi (Phase 01) gọi
`deps.notify_gate(job_view, gate_task)`; nút bấm quay về `_tg_callback` nhánh "gv:" và gọi
`tasks.current().gate_action(brain, job_id, action, source="telegram")`. Ở đây giả lập cả
job_view lẫn gate_action, không chạm tasks.py.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-gate-tg-"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import config as cfgmod  # noqa: E402
import main  # noqa: E402
import inbox  # noqa: E402
import webpush  # noqa: E402
from _gia_http import GiaHttp  # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(name)


_LOOP = asyncio.new_event_loop()


def chay(coro):
    return _LOOP.run_until_complete(coro)


async def _khong_push(*a, **k):
    return 0


webpush.gui_het = _khong_push

s = cfgmod.read_settings()
s["telegram"] = {"enabled": True, "token": "123:abc", "chat_id": "111,222"}
s.setdefault("domain", {})["custom"] = ""
cfgmod.write_settings(s)

BRAIN = "/tmp/brain-gia"


def _job(jid="job_ab12", chat="", doi="social"):
    return {
        "id": jid, "title": "Đăng bài ra mắt váy lụa", "doi": doi, "status": "cho_duyet",
        "created_at": "2026-10-26T09:00:00", "chat_id": chat, "brain": BRAIN,
        "buoc": [
            {"task_id": "t1", "title": "Nghiên cứu xu hướng", "loai": "buoc", "status": "done",
             "ket_qua_ngan": "3 xu hướng", "block_reason": ""},
            {"task_id": "t2", "title": "Viết content", "loai": "buoc", "status": "done",
             "ket_qua_ngan": "2 bản nháp", "block_reason": ""},
            {"task_id": "t3", "title": "Duyệt đăng", "loai": "gate", "status": "blocked",
             "ket_qua_ngan": "", "block_reason": "chờ duyệt"},
            {"task_id": "t4", "title": "Đăng lên fanpage", "loai": "buoc", "status": "todo",
             "ket_qua_ngan": "", "block_reason": ""},
        ],
        "gate_cho": {"task_id": "t3", "mo_ta": "Cho phép đăng 2 bài lên fanpage HALIMI",
                     "xem_truoc": "Bài 1: Lụa mềm như gió thu\nBài 2: Giảm 10% hôm nay\nBài 3: thừa",
                     "mo_khoa": ["t4"]},
    }


class _FakeFeature:
    def __init__(self, jobs, co_gate=True, kq=None):
        self.jobs = jobs
        self.goi = []
        self.kq = kq or {"ok": True, "status": "dang_chay"}
        if co_gate:
            self.gate_action = self._gate_action

    def jobs_view(self, brain):
        return {"jobs": self.jobs if brain == BRAIN else []}

    def _gate_action(self, brain, job_id, action, note="", source="dashboard"):
        self.goi.append((brain, job_id, action, note, source))
        return self.kq


def _tg_goi(gia):
    return [g for g in gia.goi if "api.telegram.org" in g["url"]]


# ---- 1. Soạn tin ---------------------------------------------------------------
tin = main._gate_soan_tin(_job())
dong = tin.splitlines()
check("dòng 1 có tên đội Social", dong[0] == "GATE · Đội Social chờ bạn duyệt", dong[0])
check("đội ads -> Ads, khac -> AI",
      "Đội Ads" in main._gate_soan_tin(_job(doi="ads"))
      and "Đội AI" in main._gate_soan_tin(_job(doi="khac")))
check("dòng 2 có tên job và các bước đã xong",
      "Đăng bài ra mắt váy lụa" in dong[1] and "Nghiên cứu xu hướng" in dong[1]
      and "Viết content" in dong[1] and "Đăng lên fanpage" not in dong[1], dong[1])
check("dòng 3 là mô tả GATE", dong[2] == "Cho phép đăng 2 bài lên fanpage HALIMI", dong[2])
check("xem trước tối đa 2 dòng", "Bài 1" in tin and "Bài 2" in tin and "thừa" not in tin, tin)
check("xưng bạn, không bố/anh", "bạn" in tin and "bố" not in tin.lower()
      and " anh " not in f" {tin.lower()} ".replace("\n", " "), tin)
check("không có em dash", "—" not in tin)
check("job_view hỏng không ném lỗi", isinstance(main._gate_soan_tin(None), str))

# ---- 2. notify_gate gửi Telegram có nút ----------------------------------------
gia = GiaHttp().tra("api.telegram.org", {"ok": True, "result": {}}).lap()
n_hom = len(inbox.danh_sach(500))
ok, err = chay(main._notify_gate(_job(), {"id": "t3", "title": "Duyệt đăng"}))
check("notify_gate trả ok", ok, err)
tg = _tg_goi(gia)
check("gửi đúng 1 tin Telegram", len(tg) == 1, len(tg))
p = (tg[0]["json"] if tg else {}) or {}
check("người nhận rỗng -> ID đầu tiên trong whitelist", p.get("chat_id") == "111", p.get("chat_id"))
kb = (p.get("reply_markup") or {}).get("inline_keyboard") or []
cbs = [b.get("callback_data") for h in kb for b in h if b.get("callback_data")]
check("có nút gv:...:d và gv:...:t", "gv:job_ab12:d" in cbs and "gv:job_ab12:t" in cbs, cbs)
check("không có địa chỉ công khai -> nút Xem chi tiết là callback gv:...:x", "gv:job_ab12:x" in cbs, cbs)
check("mọi callback_data <= 64 byte", all(len(c.encode()) <= 64 for c in cbs))
check("nút đúng nhãn", [b["text"] for b in kb[0]] == ["Duyệt", "Từ chối"] and kb[1][0]["text"] == "Xem chi tiết")
moi = inbox.danh_sach(500)
check("luôn ghi hòm thư, chưa đọc", len(moi) == n_hom + 1 and not moi[0]["read"]
      and moi[0]["source"] == "gate", moi[0] if moi else None)
gia.go()

# chat_id Telegram trong whitelist -> đúng người đó
gia = GiaHttp().tra("api.telegram.org", {"ok": True}).lap()
chay(main._notify_gate(_job(chat="222")))
check("chat_id 222 trong whitelist -> gửi 222", (_tg_goi(gia)[0]["json"] or {}).get("chat_id") == "222")
gia.go()

# job_id dài -> mã rút gọn vẫn <= 64 byte, bấm vẫn về đúng job
dai = "job_" + "x" * 80
gia = GiaHttp().tra("api.telegram.org", {"ok": True}).lap()
chay(main._notify_gate(_job(jid=dai)))
kb = ((_tg_goi(gia)[0]["json"] or {}).get("reply_markup") or {}).get("inline_keyboard") or []
cbs_dai = [b.get("callback_data") for h in kb for b in h if b.get("callback_data")]
check("job_id dài -> callback rút gọn <= 64 byte", cbs_dai and all(len(c.encode()) <= 64 for c in cbs_dai), cbs_dai)
gia.go()

# có tên miền -> nút URL
s = cfgmod.read_settings(); s["domain"]["custom"] = "minmin.example.com"; s["domain"]["ssl_enabled"] = True
cfgmod.write_settings(s)
kb = main._gate_ban_phim("job_ab12")["inline_keyboard"]
check("có tên miền -> Xem chi tiết là nút URL https",
      kb[1][0].get("url") == "https://minmin.example.com/#kanban" and "callback_data" not in kb[1][0], kb[1])
s = cfgmod.read_settings(); s["domain"]["custom"] = ""; cfgmod.write_settings(s)

# ---- 3. web: / zalo: đi đúng kênh, không nút -----------------------------------
_web = []
_zalo = []


async def _push(sid, text, viec=None):
    _web.append((sid, text))
    return True


async def _zalo_send(cid, text):
    _zalo.append((cid, text))
    return True, ""


_goc_push, _goc_zalo = main.push_to_chat, main._zalo_send_to
main.push_to_chat, main._zalo_send_to = _push, _zalo_send
gia = GiaHttp().tra("api.telegram.org", {"ok": True}).lap()
n_hom = len(inbox.danh_sach(500))
chay(main._notify_gate(_job(chat="web:sid123")))
chay(main._notify_gate(_job(chat="zalo:z9")))
check("web:<sid> -> khung chat web đúng phiên", _web and _web[0][0] == "sid123" and "GATE" in _web[0][1])
check("zalo:<id> -> Zalo dạng chữ", _zalo and _zalo[0][0] == "z9" and "GATE" in _zalo[0][1])
check("web/zalo không đi Telegram", not _tg_goi(gia))
check("web/zalo vẫn ghi hòm thư", len(inbox.danh_sach(500)) == n_hom + 2)
gia.go()
main.push_to_chat, main._zalo_send_to = _goc_push, _goc_zalo

# ---- 4. _gui_qua_kenh gọi cũ không đổi hành vi ----------------------------------
gia = GiaHttp().tra("api.telegram.org", {"ok": True}).lap()
ok, _ = chay(main._gui_qua_kenh("", "chào"))
p = _tg_goi(gia)[0]["json"]
check("gọi cũ: payload đúng 2 khoá chat_id/text, không reply_markup",
      ok and set(p) == {"chat_id", "text"} and p["text"] == "chào", p)
ok, _ = chay(main._gui_qua_kenh("", "có nút", reply_markup={"inline_keyboard": []}))
check("có reply_markup thì gắn vào payload", "reply_markup" in _tg_goi(gia)[1]["json"])
gia.go()

# ---- 5. _tg_callback nhánh gv: --------------------------------------------------
ff = _FakeFeature([_job()])
_goc_feat = main._gate_feature
main._gate_feature = lambda: ff
r = chay(main._tg_callback("gv:job_ab12:d", chat="111"))
check("gv:<id>:d gọi gate_action(brain, id, 'duyet', source='telegram')",
      ff.goi == [(BRAIN, "job_ab12", "duyet", "", "telegram")], ff.goi)
check("d: sửa tin thêm 'Đã duyệt lúc HH:MM', không trả nút",
      r and "Đã duyệt lúc " in r.get("text", "") and "reply_markup" not in r
      and str(r.get("them_vao_goc", "")).startswith("Đã duyệt lúc "), r)
ff.goi.clear()
r = chay(main._tg_callback("gv:job_ab12:t", chat="111"))
check("gv:<id>:t -> tu_choi", ff.goi and ff.goi[0][2] == "tu_choi" and ff.goi[0][4] == "telegram", ff.goi)
check("t: dòng 'Đã từ chối lúc'", "Đã từ chối lúc " in (r or {}).get("text", ""), r)

ff.goi.clear()
_gui = []


async def _gui_gia(chat, text, **k):
    _gui.append((chat, text, k))
    return True, ""


_goc_gui = main._gui_qua_kenh
main._gui_qua_kenh = _gui_gia
r = chay(main._tg_callback("gv:job_ab12:x", chat="111"))
main._gui_qua_kenh = _goc_gui
check("gv:<id>:x không gọi gate_action", not ff.goi)
check("x: gửi tin tóm tắt các bước + trạng thái về người bấm",
      _gui and _gui[0][0] == "111" and "Trạng thái: chờ bạn duyệt" in _gui[0][1]
      and "GATE Duyệt đăng" in _gui[0][1] and "text" not in (r or {}), (_gui, r))

# job id dài: callback rút gọn về đúng job
ff_dai = _FakeFeature([_job(jid=dai)])
main._gate_feature = lambda: ff_dai
chay(main._tg_callback(cbs_dai[0], chat="111"))
check("callback rút gọn -> gate_action đúng job_id dài", ff_dai.goi and ff_dai.goi[0][1] == dai, ff_dai.goi)
main._gate_feature = lambda: ff

# lỗi: dữ liệu hỏng, job không còn, gate_action báo không ok, gate_action ném, chưa có gate_action
for bad in ("gv:", "gv:abc", "gv::d", "gv:job_ab12:z", "gv:~deadbeef0000:d"):
    try:
        r = chay(main._tg_callback(bad, chat="111"))
        check(f"dữ liệu hỏng {bad!r} -> alert, không ném", isinstance(r, dict) and r.get("alert") and "text" not in r, r)
    except Exception as e:
        check(f"dữ liệu hỏng {bad!r} -> alert, không ném", False, e)
ff.kq = {"ok": False, "status": "xong", "loi": "GATE đã xử lý"}
r = chay(main._tg_callback("gv:job_ab12:d", chat="111"))
check("đã xử lý rồi -> báo ngắn, không sửa tin", "text" not in r and "đã xử lý" in r.get("alert", ""), r)


def _nem(*a, **k):
    raise RuntimeError("job không còn")


ff.gate_action = _nem
r = chay(main._tg_callback("gv:job_ab12:d", chat="111"))
check("gate_action ném -> báo ngắn, không ném", "text" not in r and "job không còn" in r.get("alert", ""), r)
main._gate_feature = lambda: _FakeFeature([_job()], co_gate=False)
r = chay(main._tg_callback("gv:job_ab12:d", chat="111"))
check("Phase 01 chưa có gate_action -> báo ngắn", "text" not in r and "Bảng việc" in r.get("alert", ""), r)
main._gate_feature = lambda: None
r = chay(main._tg_callback("gv:job_ab12:d", chat="111"))
check("chưa có hàng đợi -> báo ngắn", "text" not in r and r.get("alert"), r)
main._gate_feature = _goc_feat

# ---- 6. telegram_bot giữ chữ tin gốc + nối dòng, gỡ nút; whitelist có sẵn --------
from telegram_bot import TelegramBot  # noqa: E402


class _Client:
    def __init__(self):
        self.goi = []

    async def post(self, url, json=None):
        self.goi.append((url.rsplit("/", 1)[-1], json))


async def _cb(data, chat):
    return {"text": "dựng lại", "them_vao_goc": "Đã duyệt lúc 09:12", "alert": "Đã duyệt"}


bot = TelegramBot("1:x", "111", None, None, _cb)
cl = _Client()
chay(bot._handle_callback(cl, {"id": "q1", "data": "gv:job_ab12:d",
                               "message": {"chat": {"id": 111}, "message_id": 5, "text": "GATE · Đội Social chờ bạn duyệt"}}))
ed = [j for m, j in cl.goi if m == "editMessageText"]
check("sửa tin = chữ gốc + dòng Đã duyệt, không kèm nút",
      ed and ed[0]["text"] == "GATE · Đội Social chờ bạn duyệt\n\nĐã duyệt lúc 09:12" and "reply_markup" not in ed[0], ed)
cl = _Client()
chay(bot._handle_callback(cl, {"id": "q2", "data": "gv:job_ab12:d",
                               "message": {"chat": {"id": 999}, "message_id": 6, "text": "x"}}))
check("người ngoài whitelist bấm -> chỉ 'Không có quyền'",
      [m for m, _ in cl.goi] == ["answerCallbackQuery"] and cl.goi[0][1]["text"] == "Không có quyền", cl.goi)

# ---- 7. Ràng buộc kiến trúc ---------------------------------------------------
_src = (SERVER / "main.py").read_text(encoding="utf-8")
check("deps.notify_gate được nối vào hàng đợi", "tasks_feature.deps.notify_gate = _notify_gate" in _src)
check("hàng đợi đang chạy mang notify_gate", getattr(main.tasks_feature.deps, "notify_gate", None) is main._notify_gate)
_cb_src = _src.split("async def _tg_callback(", 1)[1].split("\nasync def _tg_command(", 1)[0]
check("_tg_callback có nhánh gv:", 'data.startswith("gv:")' in _cb_src)
_gate_src = _src.split("# ĐỘI AI - GATE", 1)[1].split("def _loop_mcp_allow", 1)[0]
check("không có em dash trong code GATE", "—" not in _gate_src)

print()
if _fails:
    print(f"ĐỎ {len(_fails)} mục: " + "; ".join(_fails))
    raise SystemExit(1)
print("Tất cả xanh.")
