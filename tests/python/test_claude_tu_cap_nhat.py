"""Claude Code phải tự lên bản mới, để model mới tự hiện trong Javis.

    python tests/run.py claude_tu_cap_nhat

Lỗi thật chủ repo báo 29/09/2026: "có sonnet 5.5 rồi mà trên javis chưa update, anh tưởng là
đã update tự động các mô hình rồi chứ?". Đường đọc danh mục model từ binary `claude` vẫn chạy
đúng; cái kẹt là chính binary. Claude Code chỉ tự cập nhật khi người ta mở nó gõ tay, còn Javis
gọi nó chạy ngầm, nên máy đứng ở 2.1.232 (14/08) suốt sáu tuần. Bản Docker kẹt theo kiểu khác:
cache gha giữ nguyên lớp `npm install -g @anthropic-ai/claude-code@latest` vì chuỗi lệnh
không đổi.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import subprocess
import sys
import tempfile
import time

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-claude-upd-")

import claude_cli  # noqa: E402
import claude_update as cu  # noqa: E402
import config as cfgmod  # noqa: E402
import deploy_info  # noqa: E402
import main  # noqa: E402

_fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if them and not cond else ""))
    if not cond:
        _fails.append(name)


class _R:
    def __init__(self, rc, out):
        self.returncode, self.stdout, self.stderr = rc, out, ""


def _gia_chay(ban_truoc, ban_sau, rc_update=0, ra_update="Successfully updated"):
    """Giả `claude --version` / `claude update`: sau lệnh update thì --version ra bản mới."""
    trang = {"da_update": False, "lenh": []}

    def _chay(cmd, timeout):
        trang["lenh"].append(cmd[1:])
        if cmd[1:] == ["update"]:
            trang["da_update"] = rc_update == 0
            return _R(rc_update, ra_update)
        return _R(0, f"{ban_sau if trang['da_update'] else ban_truoc} (Claude Code)\n")
    return _chay, trang


_goc = (cu._chay, claude_cli.find_claude_cli, deploy_info.deploy_mode)
try:
    claude_cli.find_claude_cli = lambda: "C:/gia/claude.exe"
    deploy_info.deploy_mode = lambda: "windows"

    # 1. Chạy được, phiên bản đổi -> báo đổi và nhớ lại
    cu._chay, _t = _gia_chay("2.1.232", "2.1.284")
    _kq = cu.cap_nhat("tu_dong")
    check("cập nhật thành công thì ok và báo phiên bản đổi",
          _kq.get("ok") and _kq.get("doi") and (_kq["truoc"], _kq["sau"]) == ("2.1.232", "2.1.284"), _kq)
    check("gọi đúng lệnh `claude update`", ["update"] in _t["lenh"], _t["lenh"])
    check("trạng thái được ghi để thẻ Models đọc", cu.doc_trang_thai().get("sau") == "2.1.284")
    check("vừa thử xong thì chưa tới hạn chạy lại", not cu.den_han())
    check("qua 24 giờ thì tới hạn", cu.den_han(time.time() + cu.CHU_KY + 1))

    # 2. Đã mới nhất
    cu._chay, _ = _gia_chay("2.1.284", "2.1.284")
    _kq = cu.cap_nhat()
    check("đã mới nhất thì ok nhưng không báo đổi", _kq.get("ok") and not _kq.get("doi"), _kq)

    # 3. Hỏng -> câu CLI tự nói, không ném lỗi
    cu._chay, _ = _gia_chay("2.1.284", "2.1.284", rc_update=1,
                            ra_update="Checking...\nClaude is managed by Homebrew. Run brew upgrade.")
    _kq = cu.cap_nhat()
    check("hỏng thì trả ok=False kèm dòng lỗi cuối của CLI",
          not _kq.get("ok") and "Homebrew" in (_kq.get("error") or ""), _kq)

    # 4. Docker: không đụng tới CLI
    deploy_info.deploy_mode = lambda: "docker"
    cu._chay, _t = _gia_chay("1", "2")
    _kq = cu.cap_nhat()
    check("Docker không chạy `claude update` (CLI của root, user javis không ghi được)",
          _kq.get("docker") and not _t["lenh"], _kq)
    deploy_info.deploy_mode = lambda: "windows"

    # 5. Chưa cài
    claude_cli.find_claude_cli = lambda: None
    check("chưa cài Claude Code thì báo rõ", "Chưa thấy" in (cu.cap_nhat().get("error") or ""))
finally:
    cu._chay, claude_cli.find_claude_cli, deploy_info.deploy_mode = _goc

# 6. App Claude Desktop đặt DISABLE_AUTOUPDATER=1: phải gỡ ra, không thì `claude update` từ chối
os.environ["DISABLE_AUTOUPDATER"] = "1"
_r = cu._chay([sys.executable, "-c", "import os;print(os.environ.get('DISABLE_AUTOUPDATER'))"], 30)
check("gỡ DISABLE_AUTOUPDATER khỏi môi trường của lệnh con", _r.stdout.strip() == "None", _r.stdout)
os.environ.pop("DISABLE_AUTOUPDATER", None)

# 7. Tắt được bằng biến môi trường
os.environ["JAVIS_CLAUDE_AUTO_UPDATE"] = "0"
check("JAVIS_CLAUDE_AUTO_UPDATE=0 tắt vòng hằng ngày", not cu.bat())
os.environ.pop("JAVIS_CLAUDE_AUTO_UPDATE")
check("mặc định bật", cu.bat())

# 8. Server: sau khi lên bản mới thì báo đúng model MỚI
_goc2 = (cu.cap_nhat, claude_cli.list_models, main.provider_models_index)
try:
    _ds = {"v": ["sonnet", "claude-sonnet-5"]}
    claude_cli.list_models = lambda: list(_ds["v"])

    def _cap_nhat_gia(ly_do):
        _ds["v"] = ["sonnet", "claude-sonnet-5-5", "claude-sonnet-5"]
        return {"ok": True, "doi": True, "truoc": "2.1.232", "sau": "2.1.284"}
    cu.cap_nhat = _cap_nhat_gia

    async def _pmi(provider, refresh=False):
        return {"models": claude_cli.list_models(), "live": True}
    main.provider_models_index = _pmi
    main._PROV_MODELS_CACHE["anthropic-cli"] = {"ids": ["cu"], "ts": time.time()}
    _kq = asyncio.run(main._cap_nhat_claude("tay"))
    check("CANARY: báo Sonnet 5.5 là model mới", _kq.get("model_moi") == ["claude-sonnet-5-5"], _kq)
    check("xoá cache danh sách model cũ", "anthropic-cli" not in main._PROV_MODELS_CACHE)
finally:
    cu.cap_nhat, claude_cli.list_models, main.provider_models_index = _goc2

check("có endpoint POST /claude/update",
      any(getattr(r, "path", "") == "/claude/update" and "POST" in getattr(r, "methods", set())
          for r in main.app.routes))

# 9. Lưới cuối và ảnh Docker
_def = {d["id"]: d for d in main.PROVIDER_DEFS}
for _p in ("anthropic-cli", "anthropic-api"):
    check(f"danh sách dự phòng {_p} có Sonnet 5.5 và Opus 5.5",
          {"claude-sonnet-5-5", "claude-opus-5-5"} <= set(_def[_p]["default_models"]))
check("catalog mặc định trong config có Sonnet 5.5",
      "claude-sonnet-5-5" in cfgmod._DEFAULT["model"]["catalog"]["claude"])
_wf = open(os.path.join(ROOT, ".github", "workflows", "docker-publish.yml"), encoding="utf-8").read()
check("CI truyền số phiên bản Claude Code thật vào build (phá cache lớp npm)",
      "CLAUDE_CLI_VERSION=${{ env.CLAUDE_CLI_VERSION }}" in _wf
      and "npm view @anthropic-ai/claude-code@latest version" in _wf)

print()
if _fails:
    print(f"{len(_fails)} FAIL")
    sys.exit(1)
print("ALL PASS")
