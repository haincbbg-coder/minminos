"""Bộ não thứ 16: Kimi Code CLI của Moonshot AI (binary `kimi`), chạy bằng GÓI HỘI VIÊN Kimi.

MinMin không giữ token của ai: nó gọi đúng binary `kimi` trên máy và mượn phiên đăng nhập mà
chính CLI giữ trong `~/.kimi-code/credentials/`. Không cần API key; quota lập trình đi theo gói
hội viên (bản kimi.com: ¥99 / ¥199 / ¥699 có quota lập trình, gói ¥49 KHÔNG có; bản kimi.ai quốc
tế có bảng giá riêng). Quota tính theo khung 5 giờ cuốn chiếu cộng trần tháng, mọi thiết bị đăng
nhập cùng tài khoản dùng chung một quota (trang Kimi Code benefits, đọc 24/10/2026).

**Bản nào là bản chính chủ hiện hành.** Có HAI gói cùng hãng cùng tên binary `kimi`:
- npm `@moonshot-ai/kimi-code` (2.3.1, cần Node >= 22.19) - bản HIỆN HÀNH, cũng là thứ lệnh cài
  `curl -fsSL https://code.kimi.com/kimi-code/install.sh | bash` đặt lên máy (bản đóng gói sẵn).
- PyPI `kimi-cli` (1.52.0) - bản CŨ. ĐÃ ĐO: `kimi --help` của nó chỉ in đúng một câu "kimi-cli is
  no longer maintained. Please use the new Kimi Code CLI", và `kimi --version` ra
  "kimi, version 1.52.0". Bản mới còn có lệnh `kimi migrate` để chuyển dữ liệu từ bản cũ.
  Nên `find_kimi_cli()` LOẠI binary nào là bản cũ (xem `_la_ban_cu`), kể cả khi nó đứng trước
  trong PATH.

**ĐÃ ĐO trên binary thật 2.3.1 (24/10/2026)**, cài bằng npm vào thư mục nháp. Mạng tới
auth.kimi.com/api.kimi.com bị chặn trong máy dựng bản, nên phần đăng nhập và một lượt chat được
đo bằng cách trỏ CLI vào máy chủ GIẢ trên 127.0.0.1 qua hai biến chính chủ `KIMI_CODE_OAUTH_HOST`
và `KIMI_CODE_BASE_URL` (CLI tự khai hai biến này để đổi đầu mối). Tức là đo THẬT cách binary in
ra, ghi file, gửi request; chỉ nội dung máy chủ trả là giả.

- Không tương tác: `kimi -p "<prompt>" --output-format stream-json`. Ở chế độ này CLI tự đặt
  quyền "auto" (Never Ask) - không bao giờ dừng lại hỏi duyệt nên không treo. Mỗi dòng stdout là
  MỘT tin nhắn kiểu OpenAI, KHÔNG phải từng mẩu chữ:
      {"role":"meta","type":"system.version","version":"2.3.1"}
      {"role":"assistant","tool_calls":[{"type":"function","id":"call_1",
                       "function":{"name":"Bash","arguments":"{\"command\":\"echo hi\"}"}}]}
      {"role":"tool","tool_call_id":"call_1","content":"hi\n"}
      {"role":"assistant","content":"Xin chào bố"}
      {"role":"meta","type":"session.resume_hint","session_id":"session_94285efb-...", ...}
  Lỗi đi ra stderr dạng `error: failed to run prompt: <lý do>`, mã thoát 1. Lệnh con Bash của
  chính Kimi có thể in lọt ra stdout (đo được dòng `hi` trần giữa các dòng JSON) - dòng không
  phải JSON KHÔNG được gộp vào câu trả lời, chỉ giữ làm lưới cuối khi không có chữ nào khác.
- Không có số token trong stream-json. Số token nằm ở `~/.kimi-code/sessions/<ws>/<sid>/agents/
  main/wire.jsonl`, dòng `{"type":"usage.record","usage":{"inputOther","output","inputCacheRead",
  "inputCacheCreation"}}` - `_doc_usage` đọc phần mới ghi thêm của lượt này.
- Chọn model: `-m <alias>`; alias lấy từ `[models."kimi-code/<id>"]` mà `kimi login` ghi vào
  `~/.kimi-code/config.toml` sau khi hỏi `/models` của Kimi (gói nào thấy model nấy). Không có
  lệnh liệt kê riêng ngoài `kimi provider list --json`; đọc thẳng file là đủ và không đẻ tiến trình.
- Nối phiên: `-S <session_id>`. System prompt: `--agent-file <file.md>` (frontmatter `name`,
  `description`, `disallowedTools`; THÂN file THAY HẲN system prompt của Kimi - đo: request gửi
  đi có message system đúng bằng thân file, và danh sách tool mất đúng các tool bị cấm).
  `--agent-file` KHÔNG đi chung được với `-S` (CLI khai thế), nhưng phiên giữ nguyên agent đã
  chọn lúc tạo (đo: lượt `-S` sau vẫn mang system prompt và danh sách tool của lượt đầu, kể cả
  khi file agent đã bị xoá).
- Đăng nhập: CÓ lệnh riêng `kimi login [--region global|mainland-cn]`, không tương tác, in ra
  stderr: "Opening browser for Kimi device login: <url>" rồi "If the browser did not open, paste
  the URL above and enter code: <mã>", tự hỏi máy chủ tới khi xong, in "Logged in to
  managed:kimi-code." và thoát 0. Phiên ghi ở `~/.kimi-code/credentials/kimi-code*.json`
  (access_token/refresh_token, quyền 0600) cộng mục `[providers."managed:kimi-code"]` trong
  config.toml. Không có lệnh `kimi logout` (chỉ có `/logout` trong giao diện tương tác).
  Menu chọn nền tảng ("Select a platform": Kimi Code (kimi.com/code) / Kimi Code (kimi.ai/code)
  / API key...) chỉ có trong `/login` của giao diện tương tác; `login_start` vẫn tự chọn đúng
  mục nếu gặp nó (bản sau đổi `kimi login` thành menu, hoặc bản thiếu lệnh `login`).
- MCP: `~/.kimi-code/mcp.json` (cấp user) hoặc `<cwd>/.kimi-code/mcp.json` (cấp dự án), khoá
  `{"mcpServers": {"<ten>": {"transport": "http", "url": ..., "headers": {...}}}}`. Cấp dự án bị
  BỎ QUA nếu thư mục chưa "trust" (đo: CLI in cảnh báo "this folder is not trusted; skipped 1
  project-level MCP server"), trừ khi đặt `KIMI_CODE_TRUST_WORKSPACE=1` - MinMin đặt biến này
  (đo: có biến thì CLI gửi `initialize` tới hub kèm đúng header Authorization + X-Javis-Mode).
- Tự cập nhật / hỏi bản mới: tắt bằng `KIMI_CODE_NO_AUTO_UPDATE=1` (biến chính chủ).

**CHƯA ĐO (không có tài khoản Kimi thật):** dạng thật của `user_code` (máy chủ giả trả
"ABCD-1234"), câu lỗi THẬT khi hết quota hoặc gói không có quota lập trình (máy chủ giả trả 429
"You exceeded your current quota" và CLI in nguyên văn `provider.api_error: 429 ...`), vị trí binary
mà install.sh chính chủ đặt (code.kimi.com bị chặn ở máy dựng bản). Cửa thoát: `JAVIS_KIMI_BIN`
(đường dẫn binary), `JAVIS_KIMI_REGION` (global|mainland-cn), `JAVIS_KIMI_TIMEOUT` (giây/lượt).

Điều khoản: trang hội viên Kimi Code (24/10/2026) không nói gì về chạy nền 24/7, chạy trên VPS
hay dùng tự động - CHƯA RÕ, không phải "được phép". Điều duy nhất ghi rõ: sửa nhận dạng client
(User-Agent) là vi phạm, có thể bị treo quyền lợi hội viên. MinMin chạy đúng binary chính chủ nên
không đụng tới nhận dạng đó.
"""
from __future__ import annotations

import asyncio
import errno
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import AsyncIterator, Optional

from claude_cli import _home_dir, _no_window, tim_binary

try:                       # Python 3.11+ có sẵn; đọc TOML, KHÔNG ghi được.
    import tomllib
except ModuleNotFoundError:   # pragma: no cover
    tomllib = None            # type: ignore[assignment]

PROVIDER_ID = "kimi-cli"
GOI_NPM = "@moonshot-ai/kimi-code"
NODE_TOI_THIEU = (22, 19, 0)

# Lệnh cài chính chủ (trang kimi.ai/resources/kimi-code-introduction). Chọn script làm đường
# CHÍNH thay vì npm: VPS của chủ chạy Docker, mà npm global nằm trong /usr/local của image - mỗi
# lần cập nhật Docker là mất. Script đặt bản đóng gói sẵn vào thư mục nhà (đã link sang /data
# trong entrypoint) và không đòi Node. npm là đường LÙI khi script hỏng (mạng chặn code.kimi.com)
# mà máy có Node đủ mới; khi đó cài với `--prefix ~/.local` để binary vào ~/.local/bin, cũng
# sống qua lần cập nhật Docker.
LENH_CAI = "curl -fsSL https://code.kimi.com/kimi-code/install.sh | bash"
LENH_CAI_WIN = "irm https://code.kimi.com/kimi-code/install.ps1 | iex"
LENH_CAI_NPM = "npm install -g --prefix ~/.local " + GOI_NPM

# Model dự phòng khi config.toml chưa có danh sách (chưa đăng nhập). `kimi-for-coding` là model
# mà mọi gói có quota lập trình đều thấy (trang membership-guide); alias theo đúng dạng CLI ghi.
MODEL_DU_PHONG = "kimi-code/kimi-for-coding"

# Tool NATIVE của Kimi bị cấm theo mức quyền MinMin. Tên ĐÃ ĐO từ danh sách tool trong request
# thật của 2.3.1: Agent, AgentSwarm, AskUserQuestion, Bash, CreateGoal, CronCreate, CronDelete,
# CronList, Edit, EnterPlanMode, ExitPlanMode, FetchURL, GetGoal, Glob, Grep, Read, SetGoalBudget,
# Skill, TaskList, TaskOutput, TaskStop, TodoList, UpdateGoal, WaitFor, WebSearch, Write.
# Hàng rào THẬT vẫn là header X-Javis-Mode ở hub MCP; đây là lớp thứ hai cho tool của chính Kimi.
# AskUserQuestion luôn cấm: chạy headless không có ai trả lời. Agent/AgentSwarm/Cron* cấm ở mức
# thấp vì sub-agent và lịch của Kimi là đường vòng ra khỏi luật cấm của agent chính.
_TOOL_CAM = {
    "suggest": ("AskUserQuestion", "Bash", "Write", "Edit", "Agent", "AgentSwarm",
                "CronCreate", "CronDelete"),
    "auto": ("AskUserQuestion", "Bash", "Agent", "AgentSwarm", "CronCreate", "CronDelete"),
    "full": ("AskUserQuestion",),
}
_THU_TU_MUC = {"suggest": 0, "auto": 1, "full": 2}


def _kimi_home() -> Path:
    """Thư mục dữ liệu của `kimi`. KIMI_CODE_HOME thắng, đúng như CLI xử lý."""
    env = (os.environ.get("KIMI_CODE_HOME") or "").strip()
    if env:
        return Path(env).expanduser()
    return _home_dir() / ".kimi-code"


def lenh_cai() -> str:
    return LENH_CAI_WIN if os.name == "nt" else LENH_CAI


def vung_mac_dinh() -> str:
    """Vùng tài khoản: `global` (kimi.ai) hay `mainland-cn` (kimi.com). Hai vùng là hai hệ tài
    khoản khác nhau. Mặc định global vì chủ MinMin ở Việt Nam; đổi được ngay trên thẻ."""
    v = (os.environ.get("JAVIS_KIMI_REGION") or "").strip().lower()
    return v if v in ("global", "mainland-cn") else "global"


def _moi_truong() -> dict:
    env = dict(os.environ)
    # Tắt bộ tự cập nhật: nó có thể tải bản mới giữa lượt, ghi vào chỗ chỉ đọc, hoặc in chữ lạ.
    env.setdefault("KIMI_CODE_NO_AUTO_UPDATE", "1")
    env.setdefault("KIMI_CLI_NO_AUTO_UPDATE", "1")
    # Cho CLI đọc `<brain>/.kimi-code/mcp.json` (hub MinMin) mà không đòi bấm "Trust this
    # folder" trong giao diện tương tác - thứ không ai bấm được trên VPS.
    env.setdefault("KIMI_CODE_TRUST_WORKSPACE", "1")
    env.setdefault("NO_COLOR", "1")
    # VPS không có trình duyệt: `kimi login` vẫn gọi mở trình duyệt; trỏ BROWSER vào lệnh vô hại
    # để nó không in lỗi xdg-open lẫn vào nhật ký đăng nhập.
    if os.name != "nt":
        env.setdefault("BROWSER", "true")
    return env


# ---------------------------------------------------------------------------
# Tìm binary, loại bản cũ
# ---------------------------------------------------------------------------
_BAN_CU_CACHE: dict = {}


def _la_ban_cu(path: str) -> bool:
    """Binary này có phải `kimi-cli` cũ của PyPI không (đã ngừng phát triển, khác hẳn cờ)."""
    try:
        st = os.stat(path)
        khoa = (path, int(st.st_mtime), st.st_size)
    except OSError:
        return False
    if khoa in _BAN_CU_CACHE:
        return _BAN_CU_CACHE[khoa]
    cu = False
    try:
        r = subprocess.run([path, "--version"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20, creationflags=_no_window(),
                           env=_moi_truong(), stdin=subprocess.DEVNULL)
        txt = (r.stdout or "") + (r.stderr or "")
        cu = ("no longer maintained" in txt) or bool(re.search(r"kimi, version 1\.", txt))
    except Exception:
        cu = False     # không chạy được --version thì không kết luận là bản cũ
    _BAN_CU_CACHE[khoa] = cu
    return cu


def _ung_vien() -> list:
    home = _home_dir()
    ds = []
    envp = (os.environ.get("JAVIS_KIMI_BIN") or "").strip()
    if envp:
        ds.append(envp)
    # CHƯA ĐO chỗ install.sh đặt binary: thử các chỗ quen của installer cùng loại, rồi PATH.
    ds += [str(home / ".local" / "bin" / "kimi"),
           str(home / ".kimi-code" / "bin" / "kimi"),
           str(home / ".kimi" / "bin" / "kimi")]
    if os.name == "nt":
        la = os.environ.get("LOCALAPPDATA", "")
        ds += [str(Path(la) / "Programs" / "kimi-code" / "kimi.exe"),
               str(home / ".kimi-code" / "bin" / "kimi.exe")]
    p = tim_binary("kimi")
    if p:
        ds.append(p)
    return ds


def find_kimi_cli() -> Optional[str]:
    """Binary `kimi` bản HIỆN HÀNH (Kimi Code), hoặc None. Bỏ qua bản `kimi-cli` cũ."""
    da = set()
    for p in _ung_vien():
        if not p or p in da:
            continue
        da.add(p)
        try:
            if not Path(p).is_file():
                continue
        except Exception:
            continue
        if _la_ban_cu(p):
            continue
        return p
    return None


def co_ban_cu() -> str:
    """Đường dẫn bản `kimi-cli` cũ nếu máy CHỈ có bản đó - để thẻ nói rõ chứ không báo 'chưa cài'."""
    for p in _ung_vien():
        try:
            if p and Path(p).is_file() and _la_ban_cu(p):
                return p
        except Exception:
            pass
    return ""


# ---------------------------------------------------------------------------
# Dò cờ: hỏi `--help` trước, đừng đoán (khuôn grok_cli)
# ---------------------------------------------------------------------------
_HELP_CACHE: dict = {"path": None, "text": "", "ts": 0.0}
_HELP_TTL = 300.0
_HELP_TTL_LOI = 120.0


def _help_text() -> str:
    cli = find_kimi_cli()
    if not cli:
        return ""
    now = time.time()
    if _HELP_CACHE["path"] == cli and now - _HELP_CACHE["ts"] < (
            _HELP_TTL if _HELP_CACHE["text"] else _HELP_TTL_LOI):
        return _HELP_CACHE["text"]
    try:
        r = subprocess.run([cli, "--help"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=20, creationflags=_no_window(),
                           env=_moi_truong(), stdin=subprocess.DEVNULL)
        txt = (r.stdout or "") + "\n" + (r.stderr or "")
    except Exception:
        txt = ""
    _HELP_CACHE.update(path=cli, text=txt, ts=now)
    return txt


def co_co(*ten_co: str) -> bool:
    """Fail-closed: không đọc được `--help` thì coi như KHÔNG có cờ."""
    txt = _help_text()
    return bool(txt) and any(c in txt for c in ten_co)


def co_effort(muc: Optional[str]) -> list:
    """Kimi Code 2.3.1 KHÔNG có cờ mức nghĩ (đo `--help`): mức nghĩ nằm trong config.toml
    (`[thinking]`). Trả [] để `_cli_do_sau_khac` rơi về câu nhắc trong prompt. Giữ hàm cho
    bản sau khai `--effort` thì tự chạy, cùng luật chặt của grok_cli: thấy cả cờ lẫn giá trị."""
    if not muc:
        return []
    txt = _help_text()
    if not txt or not re.search(r"\b" + re.escape(str(muc)) + r"\b", txt):
        return []
    for co in ("--effort", "--reasoning-effort", "--thinking-effort"):
        if co in txt:
            return [co, str(muc)]
    return []


def _muc(mode: Optional[str]) -> str:
    m = str(mode or "").strip().lower()
    return m if m in _TOOL_CAM else "suggest"    # mode lạ -> nấc chặt nhất


def tool_cam(mode: Optional[str]) -> list:
    return list(_TOOL_CAM[_muc(mode)])


def file_agent(mode: Optional[str], instructions: Optional[str]) -> str:
    """Nội dung file `--agent-file`: frontmatter cấm tool theo mức + thân là system prompt."""
    m = _muc(mode)
    than = (instructions or "").strip() or (
        "Bạn là MinMin, trợ lý AI cá nhân. Trả lời ngắn gọn, đúng trọng tâm, bằng ngôn ngữ "
        "người dùng đang viết.")
    return ("---\n"
            f"name: minmin-{m}\n"
            "description: MinMin chạy Kimi Code ở chế độ không tương tác\n"
            f"disallowedTools: {', '.join(_TOOL_CAM[m])}\n"
            "---\n" + than + "\n")


# ---------------------------------------------------------------------------
# TOML/JSON
# ---------------------------------------------------------------------------
def _doc_toml(p: Path) -> dict:
    if tomllib is None:
        return {}
    try:
        with open(p, "rb") as f:
            d = tomllib.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _doc_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# MCP: ghi hub MinMin vào `<brain>/.kimi-code/mcp.json`
# ---------------------------------------------------------------------------
def hub_entry(url: str, headers: Optional[dict] = None) -> dict:
    """Entry MCP HTTP đúng schema Kimi Code (đọc từ mã nguồn 2.3.1: `transport` + `url` +
    `headers`; thiếu `transport` mà có `url` thì CLI tự hiểu là http, nhưng ghi rõ cho chắc)."""
    e: dict = {"transport": "http", "url": url}
    if headers:
        e["headers"] = dict(headers)
    return e


def mcp_config_path(vault_root) -> Path:
    return Path(vault_root).expanduser() / ".kimi-code" / "mcp.json"


def ghi_mcp_settings(vault_root, hub: Optional[dict]) -> Optional[str]:
    """Gộp entry `javis` vào `<brain>/.kimi-code/mcp.json`, giữ server khác.

    Cấp DỰ ÁN chứ không cấp user (`~/.kimi-code/mcp.json`): MinMin chạy `kimi` với cwd = gốc
    brain, nên mỗi brain một hub với header X-Javis-Vault riêng, không brain nọ giẫm brain kia.
    File hỏng thì KHÔNG ghi đè (thà thiếu tool còn hơn xoá cấu hình người dùng).
    """
    try:
        p = mcp_config_path(vault_root)
        cu: dict = {}
        if p.exists():
            d = _doc_json(p)
            if not isinstance(d, dict):
                print(f"[kimi mcp] `{p}` không đọc được, KHÔNG ghi đè", file=sys.stderr)
                return None
            cu = d
        servers = cu.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
        if hub:
            servers["javis"] = hub
        else:
            servers.pop("javis", None)
        cu["mcpServers"] = servers
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cu, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(p, 0o600)   # chứa hub token
        except Exception:
            pass
        return str(p)
    except Exception as e:
        print(f"[kimi mcp] {e}", file=sys.stderr)
        return None


def trang_thai_mcp(vault_root) -> dict:
    """Đọc LẠI file vừa ghi: "đã ghi" không phải bằng chứng, đọc lại mới là (bài học `agy`)."""
    p = mcp_config_path(vault_root)
    ra = {"file": str(p), "ton_tai": False, "co_javis": False, "url": "", "so_header": 0}
    try:
        ra["ton_tai"] = p.exists()
    except Exception:
        return ra
    if not ra["ton_tai"]:
        return ra
    d = _doc_json(p)
    e = ((d or {}).get("mcpServers") or {}).get("javis") if isinstance(d, dict) else None
    if isinstance(e, dict) and e.get("url"):
        ra["co_javis"] = True
        ra["url"] = str(e.get("url") or "")
        h = e.get("headers")
        ra["so_header"] = len(h) if isinstance(h, dict) else 0
    return ra


# ---------------------------------------------------------------------------
# Trạng thái đăng nhập: đọc FILE, không đẻ tiến trình
# ---------------------------------------------------------------------------
def _file_phien() -> list:
    try:
        return sorted((_kimi_home() / "credentials").glob("kimi-code*.json"))[:10]
    except Exception:
        return []


def _vung_da_dang_nhap(cfg: dict) -> str:
    prov = ((cfg.get("providers") or {}).get("managed:kimi-code") or {})
    host = str(((prov.get("oauth") or {}).get("oauth_host")) or "")
    if "kimi.ai" in host:
        return "global"
    if prov:
        return "mainland-cn"
    return ""


def auth_status() -> dict:
    """{connected, method, account, plan, region, error}. Đọc file, rẻ, gọi được trong /settings."""
    cli = find_kimi_cli()
    if not cli:
        cu = co_ban_cu()
        loi = (f"Máy đang có bản kimi-cli CŨ đã ngừng phát triển ({cu}). Bấm \"Cài đặt\" để cài "
               "Kimi Code bản mới." if cu else "Chưa cài Kimi Code CLI. Bấm \"Cài đặt\" trên thẻ này.")
        return {"connected": False, "method": "", "account": "", "plan": "", "region": "",
                "error": loi}
    cfg = _doc_toml(_kimi_home() / "config.toml")
    vung = _vung_da_dang_nhap(cfg)
    co_token = False
    co_file = False
    for f in _file_phien():
        d = _doc_json(f)
        if not isinstance(d, dict):
            continue
        co_file = True
        # Đo: refresh token bị thu hồi thì CLI ghi đè token thành chuỗi RỖNG chứ không xoá file.
        if str(d.get("refresh_token") or "").strip() or str(d.get("access_token") or "").strip():
            co_token = True
            break
    if co_token:
        return {"connected": True, "method": "oauth", "account": "",
                "plan": "kimi.ai" if vung == "global" else ("kimi.com" if vung else ""),
                "region": vung, "error": ""}
    if co_file:
        return {"connected": False, "method": "", "account": "", "plan": "", "region": vung,
                "error": "Phiên đăng nhập Kimi đã hết hạn hoặc bị thu hồi. Bấm \"Đăng nhập Kimi\" lại."}
    return {"connected": False, "method": "", "account": "", "plan": "", "region": "",
            "error": "Đã cài Kimi Code nhưng chưa đăng nhập. Bấm \"Đăng nhập Kimi\" trên thẻ này."}


def _liet_ke_home() -> list:
    ra = []
    try:
        for f in sorted(_kimi_home().iterdir())[:40]:
            try:
                ra.append({"ten": f.name, "bytes": f.stat().st_size if f.is_file() else -1})
            except Exception:
                ra.append({"ten": f.name, "bytes": -1})
    except Exception:
        pass
    return ra


def chan_doan() -> dict:
    """Chẩn đoán KHÔNG lộ token: chỉ tên file, tên khoá, có/không có token."""
    home = _kimi_home()
    cfg = _doc_toml(home / "config.toml")
    ra = {"cli_path": find_kimi_cli() or "", "ban_cu": co_ban_cu(), "home": str(home),
          "home_ton_tai": home.is_dir(), "files": _liet_ke_home(),
          "file_phien": [f.name for f in _file_phien()], "co_token": False,
          "khoa_cap_cao": [], "vung": _vung_da_dang_nhap(cfg),
          "so_model": len(list_models_tu_config(cfg)), "nhat_ky": nhat_ky_dang_nhap()}
    for f in _file_phien():
        d = _doc_json(f)
        if isinstance(d, dict):
            ra["khoa_cap_cao"] += [f.name + ":" + str(k) for k in list(d.keys())[:12]]
            if str(d.get("refresh_token") or "").strip():
                ra["co_token"] = True
    return ra


def login_huong_dan() -> dict:
    return {"cai": lenh_cai(), "cai_npm": LENH_CAI_NPM,
            "dang_nhap": "kimi login --region " + vung_mac_dinh(),
            "ghi_chu": ("Đăng nhập bằng mã thiết bị: mở link trên điện thoại hoặc máy tính của "
                        "bạn, đăng nhập tài khoản Kimi, nhập mã. Không cần trình duyệt trên máy chủ.")}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
def list_models_tu_config(cfg: dict) -> list:
    models = cfg.get("models") or {}
    ids = []
    for alias, m in models.items():
        if isinstance(m, dict) and str(m.get("provider") or "") == "managed:kimi-code":
            ids.append(str(alias))
    mac = str(cfg.get("default_model") or "").strip()
    if mac in ids:
        ids.remove(mac)
        ids.insert(0, mac)
    return ids


def list_models() -> Optional[list]:
    """Alias model đăng nhập đã ghi vào config.toml (danh sách THẬT theo gói). Rẻ: đọc file."""
    if not find_kimi_cli():
        return None
    ids = list_models_tu_config(_doc_toml(_kimi_home() / "config.toml"))
    return ids or [MODEL_DU_PHONG]


# ---------------------------------------------------------------------------
# Dịch lỗi của CLI ra câu tiếng Việt làm theo được
# ---------------------------------------------------------------------------
_LOI_CHUA_DANG_NHAP = ("no model configured", "no credential configured", "use /login",
                       "not logged in", "login required", "unauthorized", "invalid_grant",
                       "refresh token", "invalid authentication", "401", "oauth_login_required",
                       "token refresh")
_LOI_QUOTA = ("429", "quota", "rate limit", "rate_limit", "usage limit", "exceeded", "insufficient",
              "membership", "subscription", "billing", "too many requests", "frozen")


def dich_loi(tho: str) -> str:
    """Câu lỗi CLI (tiếng Anh, có tiền tố `error: failed to run prompt:`) -> tiếng Việt.

    Giữ nguyên văn ở cuối trong ngoặc: `_limit_frame` của main đọc chữ này để nhận ra hết lượt,
    và người dùng gửi ảnh chụp thì còn thấy CLI nói gì.
    """
    t = (tho or "").strip()
    goc = re.sub(r"^error:\s*failed to run prompt:\s*", "", t.splitlines()[0] if t else "",
                 flags=re.I).strip()
    goc = re.sub(r"\s*See log:.*$", "", goc)
    l = t.lower()
    if any(k in l for k in _LOI_QUOTA):
        return ("Gói hội viên Kimi đã hết quota lập trình (khung 5 giờ hoặc trần tháng), hoặc gói "
                "đang dùng không có quota lập trình (gói ¥49 của kimi.com không có). Chờ quota hồi "
                "hoặc nâng gói ở kimi.com/code. (Kimi báo: " + goc[:300] + ")")
    if any(k in l for k in _LOI_CHUA_DANG_NHAP):
        return ("Kimi Code chưa đăng nhập hoặc phiên đã hết hạn. Mở trang Models, bấm \"Đăng nhập "
                "Kimi\" trên thẻ Kimi Code. (Kimi báo: " + goc[:200] + ")")
    if "different directory" in l or ("session" in l and "not found" in l):
        return "Mạch hội thoại cũ của Kimi không còn trên máy, MinMin sẽ mở mạch mới ở lượt sau. (" + goc[:200] + ")"
    return ("Kimi Code lỗi: " + goc[:800]) if goc else "Kimi Code thoát lỗi mà không nói lý do."


# ---------------------------------------------------------------------------
# Đăng nhập bằng device code, điều khiển từ trang Models
# ---------------------------------------------------------------------------
_LOGIN: dict = {"proc": None, "fd": None, "url": "", "code": "", "bat_dau": 0.0, "log": None,
                "ma_thoat": None, "vung": "", "da_chon_menu": 0, "khoa": threading.Lock(),
                "fd_dong": True}
NHAT_KY_TOI_DA = 60
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07|\x1b[=>]")
_BIMAT_RE = re.compile(r"\b(?![A-Z0-9]{4,}-)[A-Za-z0-9_\-\.]{32,}\b")
# Nhãn menu nền tảng của `/login` (đo trong mã nguồn 2.3.1: "Select a platform").
_NHAN_MENU = {"global": ("kimi.ai/code",), "mainland-cn": ("kimi.com/code",)}
_DAU_CHON = ("❯", "›", ">", "●", "➜", "▶", "*")


def _lam_sach(s: str) -> str:
    return _ANSI_RE.sub("", s or "")


def _che_bi_mat(dong: str) -> str:
    """Che chuỗi dài trông như token. Link đăng nhập giữ nguyên (người dùng cần bấm)."""
    if "://" in dong:
        return dong
    return _BIMAT_RE.sub("[đã che]", dong)


def _ghi(dong: str) -> None:
    log = _LOGIN.get("log")
    if log is None:
        return
    d = _che_bi_mat(_lam_sach(dong).strip())
    if d:
        log.append(d[:600])


def nhat_ky_dang_nhap() -> list:
    log = _LOGIN.get("log")
    return list(log) if log else []


def _bat_url_code(dong: str) -> None:
    sach = _lam_sach(dong)
    if not _LOGIN["url"]:
        m = _URL_RE.search(sach)
        if m:
            u = m.group(0).rstrip(".,);]")
            h = u.lower()
            # Bỏ link localhost (không phải link đăng nhập).
            if "://localhost" not in h and "://127.0.0.1" not in h:
                _LOGIN["url"] = u
    if not _LOGIN["code"]:
        m = re.search(r"code[:\s]+([A-Za-z0-9][A-Za-z0-9\-]{3,})", sach, re.I)
        if m and "://" not in m.group(1):
            _LOGIN["code"] = m.group(1)
        else:
            for tok in re.findall(r"\b[A-Z0-9]{4,}(?:-[A-Z0-9]{4,})+\b", sach):
                _LOGIN["code"] = tok
                break
    if not _LOGIN["code"] and _LOGIN["url"]:
        m = re.search(r"[?&]user_code=([A-Za-z0-9\-]+)", _LOGIN["url"])
        if m:
            _LOGIN["code"] = m.group(1)


def _gui(chu: str) -> bool:
    """Gửi phím vào CLI. Chỉ GHI vào fd khi luồng đọc chưa đóng nó (luồng đọc tự đóng fd của
    mình; ghi vào số fd đã đóng có thể trúng một file khác vừa được cấp lại số đó)."""
    with _LOGIN["khoa"]:
        fd = _LOGIN.get("fd")
        if fd is not None and not _LOGIN.get("fd_dong"):
            try:
                os.write(fd, chu.encode("utf-8"))
                return True
            except OSError:
                return False
    proc = _LOGIN.get("proc")
    try:
        if proc and proc.stdin:
            proc.stdin.write(chu.encode("utf-8"))
            proc.stdin.flush()
            return True
    except Exception:
        pass
    return False


def _xu_ly_menu(gan_day: str) -> bool:
    """Gặp menu chọn nền tảng thì tự chọn đúng mục Kimi Code (OAuth) của vùng đã chọn.

    Tìm các dòng mục theo thứ tự hiện ra, dòng nào có dấu chọn (❯ / > ...) là mục đang trỏ;
    bấm mũi tên xuống/lên đúng số bước tới mục cần rồi Enter. Trả True nếu đã bấm.
    """
    if _LOGIN["url"] or _LOGIN["da_chon_menu"] >= 2:
        return False
    sach = _lam_sach(gan_day)
    if not re.search(r"select a platform|kimi code \(kimi\.(ai|com)/code\)", sach, re.I):
        return False
    dong = [x.rstrip() for x in sach.splitlines() if x.strip()]
    muc = [x for x in dong if re.search(r"kimi code \(kimi\.|api key|platform\.|moonshot|"
                                        r"\(.*\.(ai|com|cn)\)", x, re.I)
           and "select a platform" not in x.lower()]
    if not muc:
        return False
    # Lấy lần vẽ CUỐI của menu (TUI vẽ lại nhiều lần): từ lần cuối thấy mục đầu tiên.
    dau = muc[0].strip(" " + "".join(_DAU_CHON))
    vt = [i for i, x in enumerate(muc) if x.strip(" " + "".join(_DAU_CHON)) == dau]
    muc = muc[vt[-1]:] if vt else muc
    nhan = _NHAN_MENU.get(_LOGIN.get("vung") or "global", ("kimi.ai/code",))
    dich = next((i for i, x in enumerate(muc) if any(n in x.lower() for n in nhan)), None)
    if dich is None:
        return False
    dang = next((i for i, x in enumerate(muc) if x.lstrip().startswith(_DAU_CHON)), 0)
    buoc = dich - dang
    phim = ("\x1b[B" * buoc) if buoc > 0 else ("\x1b[A" * (-buoc))
    _gui(phim + "\r")
    _LOGIN["da_chon_menu"] += 1
    _ghi(f"[MinMin chọn mục \"{muc[dich].strip(' ' + ''.join(_DAU_CHON))[:60]}\" ở menu đăng nhập]")
    return True


def _doc_luong(proc, fd) -> None:
    """Đọc output của tiến trình đăng nhập. Đọc pty có HẠN CHỜ (select) để vòng lặp còn quay
    lại xử lý menu khi CLI in xong rồi im lặng chờ phím. Luồng này TỰ đóng fd của nó."""
    buf = ""
    gan_day = ""
    luc_co_chu = time.time()
    try:
        while True:
            chu = ""
            if fd is not None:
                try:
                    import select
                    r, _, _ = select.select([fd], [], [], 0.5)
                    if r:
                        chu = os.read(fd, 4096).decode("utf-8", "replace")
                        if not chu:
                            break
                except (OSError, ValueError):
                    break
            else:
                try:
                    b = proc.stdout.read(1)
                except Exception:
                    b = b""
                if not b:
                    break
                chu = b.decode("utf-8", "replace") if isinstance(b, bytes) else b
            if chu:
                luc_co_chu = time.time()
                gan_day = (gan_day + chu)[-4000:]
                for c in chu:
                    if c in "\r\n":
                        if buf.strip():
                            _bat_url_code(buf)
                            _ghi(buf)
                        buf = ""
                    else:
                        buf += c
                        if len(buf) > 8000:
                            _bat_url_code(buf)
                            _ghi(buf)
                            buf = ""
            # Chỉ bấm khi menu đã vẽ XONG và CLI đứng im chờ phím (0,6 giây không in gì): TUI
            # thường chuyển bàn phím sang chế độ raw quanh lúc vẽ, và đổi chế độ kiểu TCSAFLUSH
            # là vứt mọi phím gửi tới trước đó.
            if not chu and time.time() - luc_co_chu >= 0.6 and _xu_ly_menu(gan_day):
                gan_day = ""
            if fd is not None and not chu and proc.poll() is not None:
                break
    finally:
        if buf.strip():
            _bat_url_code(buf)
            _ghi(buf)
        if fd is not None:
            with _LOGIN["khoa"]:
                if _LOGIN.get("fd") == fd:
                    _LOGIN["fd_dong"] = True
                try:
                    os.close(fd)
                except OSError:
                    pass
        try:
            _LOGIN["ma_thoat"] = proc.wait(timeout=10)
            _ghi(f"[kimi login kết thúc, mã thoát {_LOGIN['ma_thoat']}]")
        except Exception:
            pass


def _mo_tien_trinh(args: list):
    """POSIX: chạy trong pty RỘNG 1000 cột (link dài không bị bẻ dòng). Windows: ống thường -
    `kimi login` không tương tác nên không cần pty."""
    env = _moi_truong()
    env["COLUMNS"] = "1000"
    if os.name != "nt":
        try:
            import pty
            master, slave = pty.openpty()
            try:
                import fcntl, struct, termios
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 1000, 0, 0))
            except Exception:
                pass
            proc = subprocess.Popen(args, stdin=slave, stdout=slave, stderr=slave, env=env,
                                    start_new_session=True, close_fds=True,
                                    cwd=str(_home_dir()), creationflags=_no_window())
            os.close(slave)
            return proc, master
        except Exception:
            pass
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env, creationflags=_no_window(),
                            cwd=str(_home_dir()))
    return proc, None


def login_start(vung: Optional[str] = None, cho_giay: float = 30.0) -> dict:
    """Mở `kimi login --region <vùng>` (device code), trả {ok, url, code} cho giao diện.

    Tiến trình chạy tiếp sau khi hàm trả về: nó tự hỏi máy chủ Kimi tới khi người dùng nhập mã
    xong trên web. Giao diện hỏi lặp `login_trang_thai()`.
    """
    cli = find_kimi_cli()
    if not cli:
        return {"ok": False, "error": "Chưa cài Kimi Code CLI. Bấm \"Cài đặt\" trên thẻ trước."}
    v = (vung or "").strip().lower()
    v = v if v in ("global", "mainland-cn") else vung_mac_dinh()
    huy_dang_nhap()
    co_login = co_co(" login ") or co_co("login [options]")
    args = [cli, "login"] + (["--region", v] if co_co("--region") or co_login else [])
    if not co_login:
        args = [cli]          # bản không có lệnh `login`: vào giao diện tương tác rồi gõ /login
    try:
        proc, fd = _mo_tien_trinh(args)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    _LOGIN.update(proc=proc, fd=fd, fd_dong=(fd is None), url="", code="", bat_dau=time.time(),
                  log=deque(maxlen=NHAT_KY_TOI_DA), ma_thoat=None, vung=v, da_chon_menu=0)
    _ghi("[MinMin chạy] " + " ".join(args[1:]))
    threading.Thread(target=_doc_luong, args=(proc, fd), name="minmin-kimi-login",
                     daemon=True).start()
    if not co_login:
        time.sleep(2.0)
        _gui("/login\r")
        _ghi("[MinMin gõ /login]")
    han = time.time() + cho_giay
    while time.time() < han:
        if _LOGIN["url"] and (_LOGIN["code"] or time.time() > han - cho_giay + 3):
            break
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    if not _LOGIN["url"]:
        if proc.poll() is not None and auth_status().get("connected"):
            return {"ok": True, "xong": True, "url": "", "code": ""}
        duoi = [x for x in nhat_ky_dang_nhap() if not x.startswith("[")][-4:]
        loi = (f"Kimi Code không in ra link đăng nhập trong {int(cho_giay)} giây."
               + (" CLI vừa in: " + " | ".join(x[:160] for x in duoi) if duoi else ""))
        if any("fetch failed" in x.lower() or "econn" in x.lower() for x in duoi):
            loi += " (Máy chủ không ra được mạng tới auth.kimi.ai / auth.kimi.com.)"
        huy_dang_nhap()
        return {"ok": False, "error": loi, "nhat_ky": nhat_ky_dang_nhap()}
    return {"ok": True, "xong": False, "url": _LOGIN["url"], "code": _LOGIN["code"], "vung": v,
            "nhat_ky": nhat_ky_dang_nhap()}


def login_trang_thai() -> dict:
    proc = _LOGIN.get("proc")
    d = auth_status()
    dang_chay = bool(proc and proc.poll() is None)
    if not d.get("connected") and proc is not None and not dang_chay:
        time.sleep(0.6)          # file phiên có thể đang ghi dở
        d = auth_status()
    loi = ""
    if not d.get("connected") and not dang_chay:
        ma = _LOGIN.get("ma_thoat")
        cuoi = [x for x in nhat_ky_dang_nhap() if not x.startswith("[")]
        loi = d.get("error") or "Đăng nhập chưa xong."
        if ma not in (None, 0):
            loi = f"`kimi login` thoát với mã {ma}. " + loi
        if cuoi:
            loi += " CLI nói: " + cuoi[-1][:200]
    if d.get("connected") and dang_chay:
        huy_dang_nhap()          # bản tương tác (/login) không tự thoát sau khi xong
    return {"connected": bool(d.get("connected")), "dang_cho": dang_chay and not d.get("connected"),
            "url": _LOGIN.get("url", ""), "code": _LOGIN.get("code", ""),
            "region": d.get("region", ""), "ma_thoat": _LOGIN.get("ma_thoat"),
            "nhat_ky": nhat_ky_dang_nhap(), "error": loi}


def huy_dang_nhap() -> None:
    proc = _LOGIN.get("proc")
    if proc and proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass
    # KHÔNG đóng fd ở đây: luồng đọc tự đóng fd của nó khi thấy tiến trình chết.
    _LOGIN.update(proc=None, url="", code="", bat_dau=0.0)


def logout() -> dict:
    """Ngắt tài khoản Kimi khỏi máy: xoá file phiên trong `~/.kimi-code/credentials/`.

    CLI không có `kimi logout` (chỉ có `/logout` trong giao diện tương tác, mà nó cũng chỉ xoá
    đúng file này rồi gỡ mục provider). Để lại mục provider trong config.toml là vô hại: lượt
    chat sau sẽ báo "no credential configured" và MinMin dịch thành "chưa đăng nhập".
    """
    huy_dang_nhap()
    da_xoa = []
    for f in _file_phien():
        try:
            f.unlink()
            da_xoa.append(f.name)
        except Exception as e:
            return {"ok": False, "error": f"Không xoá được {f.name}: {e}"}
    return {"ok": True, "da_xoa": da_xoa}


# ---------------------------------------------------------------------------
# Cài đặt từ trang Models
# ---------------------------------------------------------------------------
_CAI: dict = {"dang_chay": False, "ok": None, "log": None, "bat_dau": 0.0}


def _ghi_cai(dong: str) -> None:
    if _CAI.get("log") is not None:
        d = _lam_sach(dong).strip()
        if d:
            _CAI["log"].append(_che_bi_mat(d)[:400])


def _node_du_moi() -> bool:
    node = shutil.which("node")
    if not node or not shutil.which("npm"):
        return False
    try:
        r = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10,
                           creationflags=_no_window())
        so = tuple(int(x) for x in re.findall(r"\d+", r.stdout or "")[:3])
        return len(so) == 3 and so >= NODE_TOI_THIEU
    except Exception:
        return False


def _chay_lenh(args: list, timeout: float = 600) -> int:
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, creationflags=_no_window(),
                         cwd=str(_home_dir()), env=_moi_truong())
    for dong in iter(p.stdout.readline, b""):
        _ghi_cai(dong.decode("utf-8", "replace"))
    return p.wait(timeout=timeout)


def cai_dat_start() -> dict:
    """Cài Kimi Code ở nền: lệnh chính chủ trước, npm (`--prefix ~/.local`) nếu cần."""
    if find_kimi_cli():
        return {"ok": True, "da_co": True}
    if _CAI["dang_chay"]:
        return {"ok": True, "dang_chay": True}
    _CAI.update(dang_chay=True, ok=None, log=deque(maxlen=NHAT_KY_TOI_DA), bat_dau=time.time())

    def _chay():
        try:
            if os.name == "nt":
                a = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", LENH_CAI_WIN]
            else:
                a = ["bash", "-c", "set -o pipefail; " + LENH_CAI]
            _ghi_cai("[MinMin chạy lệnh cài chính chủ] " + lenh_cai())
            try:
                ma = _chay_lenh(a)
                _ghi_cai(f"[lệnh cài chính chủ kết thúc, mã thoát {ma}]")
            except Exception as e:
                _ghi_cai(f"[lệnh cài chính chủ lỗi] {type(e).__name__}: {e}")
            _BAN_CU_CACHE.clear()
            if not find_kimi_cli():
                if _node_du_moi():
                    pre = str(_home_dir() / ".local")
                    npm = shutil.which("npm") or "npm"
                    _ghi_cai("[MinMin thử đường npm] npm install -g --prefix " + pre + " " + GOI_NPM)
                    try:
                        ma = _chay_lenh([npm, "install", "-g", "--prefix", pre, GOI_NPM])
                        _ghi_cai(f"[npm kết thúc, mã thoát {ma}]")
                    except Exception as e:
                        _ghi_cai(f"[npm lỗi] {type(e).__name__}: {e}")
                    _BAN_CU_CACHE.clear()
                else:
                    _ghi_cai("[Không thử npm: máy không có Node >= 22.19 kèm npm]")
            _CAI["ok"] = bool(find_kimi_cli())
            _HELP_CACHE.update(path=None, text="", ts=0.0)
        except Exception as e:
            _ghi_cai(f"[lỗi cài] {type(e).__name__}: {e}")
            _CAI["ok"] = False
        finally:
            _CAI["dang_chay"] = False

    threading.Thread(target=_chay, name="minmin-kimi-install", daemon=True).start()
    return {"ok": True, "dang_chay": True}


def cai_dat_trang_thai() -> dict:
    co = find_kimi_cli()
    log = _CAI.get("log")
    d = {"dang_chay": _CAI["dang_chay"], "ok": True if co else _CAI["ok"],
         "cli_path": co or "", "nhat_ky": list(log) if log else []}
    if _CAI["ok"] is False and not co:
        d["error"] = "Cài không thành công. Xem nhật ký bên dưới."
    return d


# ---------------------------------------------------------------------------
# Số token: đọc wire.jsonl của phiên
# ---------------------------------------------------------------------------
def _file_wire(sid: str) -> Optional[Path]:
    if not sid or "/" in sid or "\\" in sid or ".." in sid:
        return None
    try:
        for p in (_kimi_home() / "sessions").glob(f"*/{sid}/agents/main/wire.jsonl"):
            return p
    except Exception:
        pass
    return None


def _co_file(p: Optional[Path]) -> int:
    try:
        return p.stat().st_size if p else 0
    except Exception:
        return 0


def _doc_usage(sid: str, tu_byte: int = 0) -> Optional[dict]:
    """Token của lượt vừa chạy: cộng `output` mọi bước, `input` lấy của bước CUỐI (đó mới là
    độ dài mạch hiện tại - thứ main dùng để biết khi nào xoay mạch)."""
    p = _file_wire(sid)
    if not p:
        return None
    try:
        with open(p, "rb") as f:
            f.seek(tu_byte)
            tho = f.read(8_000_000).decode("utf-8", "replace")
    except Exception:
        return None
    vao = ra = cache = 0
    co = False
    for dong in tho.splitlines():
        if '"usage.record"' not in dong:
            continue
        try:
            u = (json.loads(dong).get("usage") or {})
        except Exception:
            continue
        co = True
        vao = int(u.get("inputOther") or 0) + int(u.get("inputCacheRead") or 0) \
            + int(u.get("inputCacheCreation") or 0)
        cache = int(u.get("inputCacheRead") or 0)
        ra += int(u.get("output") or 0)
    if not co:
        return None
    return {"type": "usage", "input_tokens": vao, "output_tokens": ra,
            "total_tokens": vao + ra, "cached": cache}


# Mức quyền mà MỖI phiên được tạo ra (agent-file đóng băng danh sách tool cấm vào phiên).
# Lưu ra file để sống qua lần khởi động lại MinMin.
_MODE_PHIEN_FILE = "minmin-phien.json"
_MODE_PHIEN_KHOA = threading.Lock()


def _mode_phien_doc() -> dict:
    d = _doc_json(_kimi_home() / _MODE_PHIEN_FILE)
    return d if isinstance(d, dict) else {}


def _mode_phien_ghi(sid: str, mode: str) -> None:
    with _MODE_PHIEN_KHOA:
        try:
            d = _mode_phien_doc()
            d[sid] = mode
            if len(d) > 500:
                d = dict(list(d.items())[-400:])
            p = _kimi_home() / _MODE_PHIEN_FILE
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(d), encoding="utf-8")
        except Exception:
            pass


def noi_lai_duoc(sid: str, mode: str) -> bool:
    """Nối phiên `sid` ở mức `mode` có giữ đúng luật cấm tool không.

    Danh sách tool cấm đóng băng lúc tạo phiên. Nối một phiên tạo ở mức RỘNG hơn vào lượt mức
    hẹp hơn là lách luật, nên khi đó mở mạch mới (fail-closed). Phiên không rõ mức (tạo ngoài
    MinMin, hoặc file ghi chú bị xoá) chỉ được nối ở mức full.
    """
    cu = _mode_phien_doc().get(sid)
    m = _muc(mode)
    if cu is None:
        return m == "full"
    return _THU_TU_MUC.get(_muc(cu), 0) <= _THU_TU_MUC[m]


# ---------------------------------------------------------------------------
_CO_MANG_PROMPT = ("-p", "--prompt")


def _cat_args(args: list) -> list:
    """Cờ đã truyền để hiện khi lỗi. KHÔNG kèm nội dung prompt hay đường dẫn file agent."""
    ra, truoc = [], ""
    for a in [str(x) for x in args[1:]]:
        if a.startswith("-"):
            ra.append(a)
            truoc = a
            continue
        if truoc in _CO_MANG_PROMPT:
            ra.append("<prompt>")
        elif truoc == "--agent-file":
            ra.append("<file>")
        elif truoc and len(a) <= 60 and "\n" not in a:
            ra.append(a)
        truoc = ""
    return ra[:16]


def _tran_argv() -> int:
    """Trần độ dài prompt đưa qua argv. Linux chặn MỘT đối số ở 128 KiB (MAX_ARG_STRLEN),
    Windows chặn cả dòng lệnh ở 32767 ký tự. Để chừa chỗ cho cờ khác."""
    return 24_000 if os.name == "nt" else 100_000


class KimiCLI:
    """Một lượt `kimi -p` headless. Hợp đồng sự kiện chung: tool_call / tool_result / final /
    usage / error, như GrokCLI/MuseCLI, để chat, Telegram, việc nền không cần biết engine nào."""

    def __init__(self, cwd: Optional[str] = None, tag: str = "chat", model: Optional[str] = None,
                 instructions: Optional[str] = None):
        self.cli_path = find_kimi_cli()
        self.cwd = cwd or os.getcwd()
        self.tag = tag
        self.model = model
        self.instructions = instructions
        self.session_id = None
        self.mode = "full"
        self.effort = None
        self.extra_args: list = []
        self.timeout = float(os.environ.get("JAVIS_KIMI_TIMEOUT") or 900)

    def is_available(self) -> bool:
        return self.cli_path is not None

    def _build_args(self, prompt: str, agent_file: Optional[str]) -> list:
        args = [self.cli_path, "-p", prompt, "--output-format", "stream-json"]
        if self.model:
            args += ["-m", self.model]
        if self.session_id:
            args += ["-S", self.session_id]
        elif agent_file:
            args += ["--agent-file", agent_file]
        args += co_effort(self.effort)
        args += list(self.extra_args)
        return args

    async def query(self, prompt: str) -> AsyncIterator[dict]:
        if not self.cli_path:
            yield {"type": "error",
                   "content": f"Không tìm thấy Kimi Code CLI. Cài bằng `{lenh_cai()}` (hoặc bấm "
                              "\"Cài đặt\" ở thẻ Kimi Code trên trang Models) rồi đăng nhập."}
            return
        mode = _muc(self.mode)
        if self.session_id and not noi_lai_duoc(self.session_id, mode):
            print(f"[kimi] không nối phiên {self.session_id} ở mức {mode}: mở mạch mới",
                  file=sys.stderr)
            self.session_id = None
        cac_tep: list = []
        agent_file = None
        than_he_thong = self.instructions
        if not self.session_id and len(prompt.encode("utf-8")) > _tran_argv():
            # Mạch MỚI với lịch sử mồi quá dài cho argv: đưa phần mồi vào system prompt (thân
            # file agent), argv chỉ còn câu ra lệnh ngắn.
            than_he_thong = ((self.instructions or "").strip() + "\n\n# Ngữ cảnh hội thoại và "
                             "yêu cầu hiện tại\n\n" + prompt).strip()
            prompt = "Làm theo yêu cầu cuối cùng trong phần \"Ngữ cảnh hội thoại\" ở trên."
        elif self.session_id and len(prompt.encode("utf-8")) > _tran_argv():
            # Mạch cũ (không đổi được system prompt): để nội dung dài trong file, Kimi đọc bằng Read
            # (Read được phép ở mọi mức quyền).
            try:
                fd, tep_dai = tempfile.mkstemp(prefix="minmin-kimi-msg-", suffix=".md")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(prompt)
                cac_tep.append(tep_dai)
                prompt = (f"Tin nhắn của người dùng dài nên nằm trong file `{tep_dai}`. Đọc toàn bộ "
                          "file đó bằng tool Read rồi làm theo đúng yêu cầu trong đó.")
            except Exception:
                pass
        if not self.session_id:
            try:
                fd, agent_file = tempfile.mkstemp(prefix="minmin-kimi-agent-", suffix=".md")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(file_agent(mode, than_he_thong))
                cac_tep.append(agent_file)
            except Exception:
                agent_file = None
        sid_truoc = self.session_id
        moc_wire = _co_file(_file_wire(sid_truoc)) if sid_truoc else 0
        args = self._build_args(prompt, agent_file)
        chan = {"raw": deque(maxlen=40), "khong_json": [], "tra_loi": [], "chu_khac": [],
                "stderr": "", "ma_thoat": None, "args": _cat_args(args), "so_dong": 0}
        da_loi = False
        async for ev in self._mot_lan(args, chan, cac_tep):
            if ev.get("type") == "error":
                da_loi = True
            yield ev
        if self.session_id:
            if self.session_id != sid_truoc:
                _mode_phien_ghi(self.session_id, mode)
            u = _doc_usage(self.session_id, moc_wire if self.session_id == sid_truoc else 0)
            if u:
                yield u
        text = "\n\n".join(x for x in chan["tra_loi"] if x.strip()).strip()
        if not text:
            text = "\n\n".join(x for x in chan["chu_khac"] if x.strip()).strip()
        if not text and not da_loi:
            # Lưới cuối: dòng không phải JSON (bản CLI in chữ trần) - giữ làm chữ, không trả ô rỗng.
            text = "\n".join(chan["khong_json"]).strip()
        if text:
            yield {"type": "final", "content": text}
        elif not da_loi:
            n = chan["so_dong"]
            noi = (f"Kimi Code chạy xong (mã thoát {chan['ma_thoat']}) nhưng không có câu trả lời"
                   f" ({n} dòng output).")
            if chan["raw"]:
                noi += "\nDòng cuối: " + list(chan["raw"])[-1][:400]
            if chan["stderr"]:
                noi += "\nCLI báo ở stderr: " + chan["stderr"][:300]
            noi += "\nCờ đã truyền: " + " ".join(chan["args"])
            yield {"type": "error", "content": noi}

    async def _mot_lan(self, args: list, chan: dict, cac_tep: list) -> AsyncIterator[dict]:
        loop = asyncio.get_running_loop()
        hang: asyncio.Queue = asyncio.Queue()
        HET = object()
        qua_gio = threading.Event()

        def doc_luong():
            proc = None
            canh = None
            try:
                proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, cwd=self.cwd, text=True,
                                        encoding="utf-8", errors="replace", bufsize=1,
                                        creationflags=_no_window(), env=_moi_truong(),
                                        start_new_session=(os.name != "nt"))
                try:
                    import tien_trinh_nen
                    tien_trinh_nen.ghi_nhom(self.tag, proc.pid)
                except Exception:
                    pass
                loi_ds: list = []

                def doc_err():
                    try:
                        for d in iter(proc.stderr.readline, ""):
                            if len(loi_ds) < 200:
                                loi_ds.append(d.rstrip())
                    except Exception:
                        pass
                te = threading.Thread(target=doc_err, daemon=True)
                te.start()

                def cat():
                    if proc.poll() is None:
                        qua_gio.set()
                        try:
                            proc.kill()
                        except Exception:
                            pass
                canh = threading.Timer(self.timeout, cat)
                canh.daemon = True
                canh.start()
                for line in iter(proc.stdout.readline, ""):
                    line = line.strip()
                    if not line:
                        continue
                    chan["so_dong"] += 1
                    chan["raw"].append(line[:1000])
                    try:
                        ev = json.loads(line)
                        if not isinstance(ev, dict):
                            raise ValueError
                    except (json.JSONDecodeError, ValueError):
                        ev = {"_raw": line}
                    loop.call_soon_threadsafe(hang.put_nowait, ev)
                ma = proc.wait()
                te.join(timeout=5)
                err = "\n".join(x for x in loi_ds if x.strip()).strip()
                # Cảnh báo "folder is not trusted" / "Warning:" không phải lỗi.
                chan["ma_thoat"] = ma
                chan["stderr"] = err[:1000]
                if qua_gio.is_set():
                    loop.call_soon_threadsafe(hang.put_nowait, {
                        "_exit": -1, "_err": f"Kimi Code chạy quá {int(self.timeout)} giây nên bị "
                                             "cắt. Việc thật sự dài thì nâng JAVIS_KIMI_TIMEOUT."})
                elif ma != 0:
                    loop.call_soon_threadsafe(hang.put_nowait, {"_exit": ma, "_err": err})
                elif err:
                    print(f"[kimi stderr] {err[:2000]}", file=sys.stderr)
            except OSError as e:
                if getattr(e, "errno", None) in (errno.E2BIG, errno.ENAMETOOLONG):
                    t = ("Tin nhắn quá dài so với trần dòng lệnh của hệ điều hành. Mở một hội "
                         "thoại mới hoặc rút ngắn tin nhắn.")
                else:
                    t = f"{type(e).__name__}: {e}"
                loop.call_soon_threadsafe(hang.put_nowait, {"_exit": -1, "_err": t, "_tho": True})
            except Exception as e:
                loop.call_soon_threadsafe(hang.put_nowait,
                                          {"_exit": -1, "_err": f"{type(e).__name__}: {e}", "_tho": True})
            finally:
                if canh:
                    canh.cancel()
                try:
                    if proc and proc.poll() is None:
                        proc.terminate()
                except Exception:
                    pass
                for t in cac_tep:
                    try:
                        os.unlink(t)
                    except Exception:
                        pass
                loop.call_soon_threadsafe(hang.put_nowait, HET)

        threading.Thread(target=doc_luong, name=f"minmin-kimi-{self.tag}", daemon=True).start()
        while True:
            ev = await hang.get()
            if ev is HET:
                break
            for ra in self._doi_su_kien(ev, chan):
                yield ra

    def _doi_su_kien(self, ev: dict, chan: dict) -> list:
        """Một dòng stream-json của Kimi -> 0..n sự kiện theo hợp đồng MinMin."""
        if "_raw" in ev:
            if len(chan["khong_json"]) < 200:
                chan["khong_json"].append(str(ev["_raw"]))
            return []
        if "_exit" in ev:
            loi = str(ev.get("_err") or "").strip()
            if ev.get("_tho") or ev.get("_exit") == -1 and loi.startswith("Kimi Code chạy quá"):
                return [{"type": "error", "content": loi[:1500]}]
            if not loi:
                loi = f"Kimi Code thoát với mã {ev.get('_exit')}."
                return [{"type": "error", "content": loi}]
            # Bỏ các dòng cảnh báo, lấy dòng lỗi thật.
            dong_loi = [x for x in loi.splitlines() if x.lower().startswith("error")] or \
                [x for x in loi.splitlines() if x.strip() and not x.lower().startswith(
                    ("warning", "  run `kimi`", "see log"))] or [loi]
            return [{"type": "error", "content": dich_loi("\n".join(dong_loi))}]
        role = str(ev.get("role") or "")
        if role == "meta":
            t = str(ev.get("type") or "")
            sid = str(ev.get("session_id") or "").strip()
            if sid:
                self.session_id = sid
            if t == "turn.step.retrying":
                # Kimi tự thử lại (vd 429/5xx). Không phải lỗi cuối; ghi nhận để chẩn đoán.
                print(f"[kimi retry] {ev.get('status_code')} {str(ev.get('error_message'))[:200]}",
                      file=sys.stderr)
            elif t in ("error", "turn.error"):
                tin = str(ev.get("content") or ev.get("message") or ev.get("error") or "")
                return [{"type": "error", "content": dich_loi(tin)}] if tin else []
            return []
        if role == "assistant":
            ra = []
            noi_dung = ev.get("content")
            if isinstance(noi_dung, list):
                noi_dung = "".join(str((x or {}).get("text") or "") for x in noi_dung
                                   if isinstance(x, dict))
            tcs = ev.get("tool_calls") or []
            if isinstance(noi_dung, str) and noi_dung.strip():
                # Tin có tool_calls là lời dẫn trước khi gọi tool; tin không có là câu trả lời.
                (chan["chu_khac"] if tcs else chan["tra_loi"]).append(noi_dung)
            for tc in tcs if isinstance(tcs, list) else []:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                a = fn.get("arguments")
                try:
                    inp = json.loads(a) if isinstance(a, str) and a.strip() else (a or {})
                except Exception:
                    inp = {"raw": str(a)[:2000]}
                ra.append({"type": "tool_call", "name": str(fn.get("name") or tc.get("name") or ""),
                           "id": str(tc.get("id") or ""), "input": inp})
            return ra
        if role == "tool":
            c = ev.get("content")
            if not isinstance(c, str):
                c = json.dumps(c, ensure_ascii=False)
            return [{"type": "tool_result", "id": str(ev.get("tool_call_id") or ""),
                     "status": "completed", "content": c[:2000]}]
        # Hình dạng lạ: vớt chữ để dành, không đưa thẳng vào câu trả lời.
        for k in ("content", "text", "message"):
            v = ev.get(k)
            if isinstance(v, str) and v.strip():
                chan["chu_khac"].append(v)
                break
        return []


# ---------------------------------------------------------------------------
def kiem_tra_nhanh(timeout: float = 60.0) -> dict:
    """Chạy thật MỘT lượt ngắn (mức suggest, cwd = thư mục nhà) để biết chat được chưa."""
    cli = find_kimi_cli()
    if not cli:
        return {"ok": False, "error": auth_status().get("error") or "Chưa cài Kimi Code CLI."}
    tep = None
    try:
        fd, tep = tempfile.mkstemp(prefix="minmin-kimi-agent-", suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(file_agent("suggest", "Trả lời thật ngắn."))
        args = [cli, "-p", "Trả lời đúng một chữ: ok", "--output-format", "stream-json",
                "--agent-file", tep]
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, creationflags=_no_window(),
                           env=_moi_truong(), cwd=str(_home_dir()), stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Kimi Code không trả lời trong {int(timeout)} giây."}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        if tep:
            try:
                os.unlink(tep)
            except Exception:
                pass
    tra, sid = "", ""
    for dong in (r.stdout or "").splitlines():
        try:
            d = json.loads(dong)
        except Exception:
            continue
        if isinstance(d, dict) and d.get("role") == "assistant" and isinstance(d.get("content"), str):
            tra = d["content"].strip() or tra
        if isinstance(d, dict) and d.get("session_id"):
            sid = str(d["session_id"])
    if r.returncode != 0:
        err = [x for x in (r.stderr or "").splitlines() if x.lower().startswith("error")]
        return {"ok": False, "error": dich_loi("\n".join(err) or (r.stderr or r.stdout or "")[:400])}
    if tra:
        return {"ok": True, "reply": tra[:200], "session_id": sid}
    return {"ok": False, "error": ("Kimi Code thoát 0 nhưng không có câu trả lời. Nguyên văn: "
                                   + (r.stdout or "")[:300])}
