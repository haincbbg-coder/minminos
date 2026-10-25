# -*- coding: utf-8 -*-
"""Năm bộ não mới dùng được cho giọng nói (26.10.224).

    python tests/run.py voice_nao_moi     (KHÔNG mạng, không chạy CLI thật)

Khoá:
  - Copilot, Kimi, Kiro, Cursor, Mistral Vibe có trong BRAIN_PROVIDERS, chạy trên gói (không key),
    id trùng id engine ở trang Models;
  - máy tự chọn xét chúng SAU năm bộ não cũ (thứ tự cũ không đổi), và chỉ khi ĐÃ ĐĂNG NHẬP;
  - _make dựng CliVoiceBrain; lượt đầu mồi lịch sử, lượt sau nối mạch; lỗi CLI thành RuntimeError
    (để run_voice_turn rơi về bộ não chính và nói ra lỗi);
  - lớp giọng chạy CLI ở mức Chỉ đọc, một lượt;
  - /voice/options liệt kê đủ, đường lưu nhận id mới.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
import types

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-voice-moi-"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import voice_brain as vb  # noqa: E402

_fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  [{extra}]" if (extra and not cond) else ""))
    if not cond:
        _fails.append(name)


MOI = ("copilot-cli", "kimi-cli", "kiro-cli", "cursor-cli", "vibe-cli")

# 1. Bảng bộ não
for k in MOI:
    p = vb.BRAIN_PROVIDERS.get(k) or {}
    check(f"{k}: có trong BRAIN_PROVIDERS, chạy trên gói", p and p["key_field"] == "" and k not in vb.PROVIDERS)
    check(f"{k}: có khuôn chạy CLI", k in vb.CLI_VOICE)
check("thứ tự cũ giữ nguyên ở đầu PLAN_BRAINS",
      vb.PLAN_BRAINS[:5] == ("antigravity", "codex", "claude", "grok", "muse"), vb.PLAN_BRAINS)
check("năm bộ não mới nằm sau", vb.PLAN_BRAINS[5:] == MOI, vb.PLAN_BRAINS)

# 2. Mỗi module thật có đúng tên lớp/hàm mà CLI_VOICE khai (bắt lỗi gõ sai tên)
import importlib  # noqa: E402
for k, (mod_ten, lop, tim, _ten) in vb.CLI_VOICE.items():
    mod = importlib.import_module(mod_ten)
    check(f"{k}: module {mod_ten} có {lop} và {tim} và auth_status",
          hasattr(mod, lop) and callable(getattr(mod, tim, None)) and callable(getattr(mod, "auth_status", None)))

# 3. Sẵn = đã đăng nhập, không chỉ có binary
_that = {}
for k, (mod_ten, *_r) in vb.CLI_VOICE.items():
    mod = importlib.import_module(mod_ten)
    _that[mod_ten] = mod.auth_status
mod_kimi = importlib.import_module("kimi_cli")
mod_kimi.auth_status = lambda *a, **k: {"connected": True}
check("kimi đã đăng nhập -> sẵn", vb.plan_brain_available("kimi-cli", {}))
mod_kimi.auth_status = lambda *a, **k: {"connected": False, "error": "chưa đăng nhập"}
check("kimi cài mà chưa đăng nhập -> không sẵn", not vb.plan_brain_available("kimi-cli", {}))
mod_kimi.auth_status = lambda *a, **k: (_ for _ in ()).throw(OSError("hỏng"))
check("auth_status lỗi -> không sẵn, không nổ", not vb.plan_brain_available("kimi-cli", {}))
mod_kimi.auth_status = _that["kimi_cli"]

# 4. Máy tự chọn: bộ não cũ vẫn thắng; chỉ có bộ não mới thì chọn nó
_goc = vb.plan_brain_available
_san = set()
vb.plan_brain_available = lambda pid, cfg: pid in _san


def moi(*ids):
    _san.clear()
    _san.update(ids)
    vb._AUTO_CACHE.update(at=0.0, key=None, value="")


moi("cursor-cli", "grok")
check("tự chọn: grok (cũ) đứng trước cursor", vb.auto_brain({}) == "grok")
moi("vibe-cli", "copilot-cli")
check("tự chọn: copilot đứng trước vibe", vb.auto_brain({}) == "copilot-cli")
moi()
check("không có gì sẵn -> bộ não chính", vb.auto_brain({}) == "")
moi("kiro-cli")
conf = vb.config_from_settings({"voice": {"mode": "fast"}})
check("làn nhanh chưa chọn tay -> dùng kiro đã đăng nhập", conf["provider"] == "kiro-cli", conf)
vb.plan_brain_available = _goc
moi()

# 5. Dựng và chạy (CLI giả)


class CliGia:
    def __init__(self, su_kien, sid_sau="phien-1"):
        self.su_kien = su_kien
        self.sid_sau = sid_sau
        self.session_id = None
        self.nhan = []

    async def query(self, prompt):
        self.nhan.append(prompt)
        for ev in self.su_kien:
            yield ev
        self.session_id = self.sid_sau


async def chay():
    for k in MOI:
        b = vb._make({"provider": k, "model": "m-x"})
        check(f"{k}: _make dựng CliVoiceBrain đúng provider/model",
              isinstance(b, vb.CliVoiceBrain) and b.provider == k and b.model == "m-x")

    cli = CliGia([{"type": "text", "content": "Chào "}, {"type": "text", "content": "bố"},
                  {"type": "final", "content": "Chào bố"}])
    b = vb.CliVoiceBrain("kimi-cli", cli_factory=lambda: cli)
    lich_su = [{"role": "user", "content": "câu cũ"}, {"role": "assistant", "content": "đáp cũ"}]
    out = [x async for x in b.stream("mấy giờ rồi", lich_su)]
    check("stream: lấy chữ từng mảnh, không lặp lại final", "".join(out) == "Chào bố", out)
    check("lượt đầu: mồi lịch sử cũ", "câu cũ" in cli.nhan[0] and "mấy giờ rồi" in cli.nhan[0], cli.nhan[0][:200])
    _ = [x async for x in b.stream("câu hai", lich_su)]
    check("lượt sau: nối mạch, chỉ gửi câu mới", cli.nhan[1] == "câu hai", cli.nhan[1][:100])

    cli2 = CliGia([{"type": "final", "content": "Một cục"}])
    b2 = vb.CliVoiceBrain("cursor-cli", cli_factory=lambda: cli2)
    out = [x async for x in b2.stream("hỏi", [])]
    check("CLI chỉ trả final -> vẫn có câu trả lời", out == ["Một cục"], out)

    cli3 = CliGia([{"type": "error", "content": "Hết quota gói"}])
    b3 = vb.CliVoiceBrain("vibe-cli", cli_factory=lambda: cli3)
    loi = ""
    try:
        _ = [x async for x in b3.stream("hỏi", [])]
    except RuntimeError as e:
        loi = str(e)
    check("lỗi CLI -> RuntimeError mang đúng lời báo", "Hết quota gói" in loi, loi)

    # Dựng CLI thật bằng module giả: mức Chỉ đọc, một lượt, cwd là thư mục tạm
    gia = types.ModuleType("nao_gia_voice")

    class LopGia:
        def __init__(self, cwd=None, tag="", model=None, instructions=None):
            self.cwd, self.tag, self.model, self.instructions = cwd, tag, model, instructions
            self.mode, self.max_turns, self.timeout, self.session_id = "full", 0, 900, None

    gia.LopGia = LopGia
    gia.tim_gia = lambda: "/bin/gia"
    sys.modules["nao_gia_voice"] = gia
    vb.CLI_VOICE["nao-gia"] = ("nao_gia_voice", "LopGia", "tim_gia", "Não giả")
    try:
        bg = vb.CliVoiceBrain("nao-gia", model="m1")
        bg._ensure()
        c = bg.cli
        check("CLI giọng: mức Chỉ đọc, một lượt, tag voice",
              c.mode == "suggest" and c.max_turns == 1 and c.tag == "voice" and c.model == "m1")
        check("CLI giọng: có lời dặn giọng nói, cwd thư mục tạm",
              c.instructions == vb.SYSTEM_PROMPT and c.cwd == tempfile.gettempdir())
        gia.tim_gia = lambda: None
        bh = vb.CliVoiceBrain("nao-gia")
        loi = ""
        try:
            bh._ensure()
        except RuntimeError as e:
            loi = str(e)
        check("chưa cài -> lỗi nhắc trang Models", "Chưa cài Não giả" in loi and "Models" in loi, loi)
    finally:
        vb.CLI_VOICE.pop("nao-gia", None)
        sys.modules.pop("nao_gia_voice", None)
    await vb.close_all()


asyncio.run(chay())

# 6. Trang Cài đặt và đường lưu
import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app, base_url="http://127.0.0.1")
r = client.get("/voice/options?brains=0").json()
ids = {b["id"] for b in r.get("brain_choices", [])}
check("/voice/options: brain_choices có đủ năm bộ não mới", set(MOI) <= ids, ids)
r = client.get("/voice/options?brains=1").json()
mot = {b["id"]: b for b in r.get("brain_providers", [])}
check("/voice/options đủ: có năm bộ não mới, kèm gợi ý",
      all(k in mot and mot[k].get("hint") for k in MOI), list(mot))
r = client.get("/voice/brain-models?provider=kimi-cli").json()
check("/voice/brain-models nhận id mới", r.get("ok") is True and r.get("provider") == "kimi-cli", r)

if _fails:
    print(f"\n{len(_fails)} FAIL")
    sys.exit(1)
print("\nTất cả OK")
