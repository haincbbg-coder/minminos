"""Bộ não GitHub Copilot CLI (binary `copilot`, gói npm `@github/copilot`), chạy bằng GÓI Copilot.

Khuôn giống `grok_cli.py`: MinMin không giữ token của ai, nó gọi đúng binary `copilot` của máy và
mượn phiên đăng nhập mà chính CLI giữ. Một gói Copilot (Free / Pro / Pro+ / Business) mở được
model của NHIỀU HÃNG (Claude, GPT, Gemini, Grok...) qua cùng một binary - đó là lý do thẻ này
đáng có dù MinMin đã có thẻ riêng cho từng hãng.

**ĐÃ ĐO TRÊN BINARY THẬT (`@github/copilot` 1.0.103, 2026-10-24), đừng đoán lại:**

- `copilot --help`: `-p/--prompt <text>` chạy không tương tác, `--output-format json` in JSONL
  (một sự kiện mỗi dòng), `--model <id>` (nhận cả `auto`), `--reasoning-effort` với đúng bảy giá
  trị `none|minimal|low|medium|high|xhigh|max` (gửi giá trị lạ là thoát ngay "invalid value"),
  `--session-id <uuid>` vừa mở phiên mới mang id đó vừa nối lại phiên cũ, `--allow-all-tools`
  (BẮT BUỘC cho chế độ không tương tác), `--deny-tool=<mẫu>` thắng cả `--allow-all-tools`,
  `--allow-all-paths`, `--allow-all-urls`, `--no-ask-user`, `--no-auto-update`, `--no-color`,
  `--disable-builtin-mcps`, `--additional-mcp-config @<file>`. Cả bộ cờ MinMin truyền đã chạy
  thử trên binary thật và được nhận (dừng ở bước "chưa đăng nhập", tức đã qua bước đọc cờ).
- Prompt qua ống stdin (không có `-p`) cũng là chế độ prompt - đo được: CLI trả "No
  authentication" chứ không mở giao diện tương tác. Dùng cho prompt quá dài so với trần argv.
- Chưa đăng nhập: thoát mã 1, stdout RỖNG, stderr `Error: No authentication information found.`
  PAT cổ điển trong biến môi trường: `Error: Classic Personal Access Tokens (ghp_) are not
  supported by Copilot.`
- `copilot login --device-code` (dựng máy chủ OAuth giả trên localhost bằng `--host` để đo) in
  NGUYÊN VĂN, không có menu nào:
      To authenticate, visit https://github.com/login/device and enter code ABCD-1234
      Waiting for authorization...
  rồi đứng hỏi máy chủ. Xong thì, trên máy KHÔNG có keychain (container Docker, VPS), nó HỎI:
      System keychain unavailable. Store token in plaintext config file? (y/N)
  Chạy không có tty thì nó không hỏi được, in "Login succeeded, but the token was not saved" và
  thoát mã 1 - đăng nhập xong mà vẫn như chưa. Nên PHẢI chạy trong pty và trả lời "y". Trả lời
  xong nó in `Signed in successfully as <login> (<host>).` và ghi `~/.copilot/config.json`:
  `authTokens` (token), `loggedInUsers`, `lastLoggedInUser`. File đó có DÒNG CHÚ THÍCH `//` ở
  đầu (JSONC), `json.loads` thẳng là hỏng.
- Trong pty nó còn in chuỗi OSC 52 (chép mã vào clipboard, base64 của mã) - phải lọc.
- Không có lệnh `logout`/`status` ngoài giao diện tương tác (`copilot logout` -> "Invalid command
  format"). Ngắt = gỡ ba khoá đăng nhập khỏi `config.json`, xem `logout()`.
- Model: `copilot help config` liệt kê danh mục model của BẢN CLI đó, không cần mạng.
- MCP: `copilot mcp add --transport http ... --header` ghi `~/.copilot/mcp-config.json` dạng
  `{"mcpServers": {"<ten>": {"type": "http", "url": ..., "headers": {...}, "tools": ["*"]}}}`.
- Sơ đồ sự kiện JSONL: đọc từ `schemas/session-events.schema.json` ĐI KÈM gói (nguồn cấp 1,
  không phải tài liệu): `assistant.message` (`content`), `assistant.message_delta`
  (`deltaContent`), `tool.execution_start` (`toolName`, `mcpServerName`, `mcpToolName`,
  `arguments`), `tool.execution_complete` (`success`, `result.content`), `assistant.usage`
  (`inputTokens`, `outputTokens`, `cacheReadTokens`), `session.error` (`message`),
  `session.warning`, `session.mcp_server_status_changed` (`serverName`, `status`).

**CHƯA ĐO** (sandbox chặn `api.githubcopilot.com`, không có tài khoản Copilot): một lượt chat THẬT
từ đầu tới cuối - thứ tự sự kiện, có phát `message_delta` ở chế độ json hay không, câu lỗi hết
hạn mức thật. Lưới an toàn: dòng không phải JSON giữ làm chữ, loại sự kiện lạ thì vớt chữ, và
không ra chữ nào thì báo nguyên văn những gì CLI in chứ không trả bong bóng rỗng.

Lưu ý đo được thêm: CLI có CHÍNH SÁCH MCP bên thứ ba theo tổ chức. Trên máy chủ OAuth giả nó
báo "Third-party MCP servers are disabled by your organization's Copilot policy" và chặn server
`javis`. Gói cá nhân thật chưa đo được; nút "Kiểm tra lại" đọc đúng cảnh báo đó và nói ra.
"""
from __future__ import annotations

import asyncio
import errno
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import AsyncIterator, Optional

from claude_cli import _home_dir, _no_window, tim_binary

# Dự phòng khi không đọc được `copilot help config`. Cố ý ngắn: danh mục thật lấy từ CLI.
MODELS_DU_PHONG = ["auto", "claude-sonnet-5", "gpt-5.4", "gemini-3.8-flash"]

# Cài qua npm vào ~/.local, KHÔNG cài vào image Docker. Vì sao chọn khuôn nút Cài đặt (như
# Grok/agy) chứ không khuôn Codex (nằm sẵn trong Dockerfile):
# - Gói nặng: bản Linux x64 tải về ~200 MB binary, lần chạy đầu bung thêm ~240 MB vào
#   ~/.cache/copilot. Nhét vào image là mọi người cài MinMin đều gánh, kể cả ai không có gói
#   Copilot. Codex khác: đăng nhập ChatGPT do chính MinMin lo nên thẻ đó cần binary sẵn.
# - Container chạy user `javis`, không ghi được /usr/local nên `npm install -g` trần hỏng quyền.
#   `--prefix ~/.local` thả binary vào ~/.local/bin, mà ~/.local đã được entrypoint link sang
#   volume /data - cài một lần là sống qua mọi lần cập nhật image.
# - Bản cài từ npm không tự cập nhật (help: "Installations run from npm only report that a
#   newer version is available") nên không có tiến trình nào tự ghi đè binary giữa lượt chat.
GOI_NPM = "@github/copilot"
LENH_CAI = "npm install -g --prefix ~/.local @github/copilot"
LENH_CAI_WIN = "npm install -g @github/copilot"

# Mức quyền MinMin -> luật chặn của Copilot. `--deny-tool` thắng `--allow-all-tools` (help
# permissions). Viết dạng `--deny-tool=<mẫu>` có dấu bằng vì cờ này nhận NHIỀU giá trị: viết
# tách hai token thì một giá trị theo sau có thể bị nuốt làm mẫu chặn.
# `shell` không kèm đối số = mọi lệnh máy; `write` không kèm đường dẫn = mọi tool ghi file.
_LUAT_CHAN = {
    "suggest": ("shell", "write"),
    "auto": ("shell",),
    "full": (),
}

TIEN_TO_TOKEN = ("gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "ghp_")


def _copilot_home() -> Path:
    """Thư mục cấu hình của `copilot`. COPILOT_HOME thắng, đúng như CLI xử lý (help environment)."""
    env = (os.environ.get("COPILOT_HOME") or "").strip()
    if env:
        return Path(env).expanduser()
    return _home_dir() / ".copilot"


def _doc_jsonc(p: Path) -> tuple:
    """(đọc_được, dict) cho file JSON có dòng chú thích `//` (đo: config.json mở bằng hai dòng
    `// User settings belong in settings.json.`). Không có file -> (True, {}); hỏng -> (False, {}).

    Phân biệt "không có" với "hỏng" vì `logout()` GHI lại file này: gộp hai ca là mỗi lần gặp
    file lạ MinMin xoá sạch cấu hình Copilot của người dùng."""
    try:
        if not p.exists():
            return True, {}
        raw = p.read_text(encoding="utf-8")
    except Exception:
        return False, {}
    dong = [x for x in raw.splitlines() if not x.lstrip().startswith("//")]
    try:
        d = json.loads("\n".join(dong) or "{}")
        return True, (d if isinstance(d, dict) else {})
    except Exception:
        return False, {}


def find_copilot_cli() -> Optional[str]:
    """Tìm binary `copilot`. Cửa thoát JAVIS_COPILOT_BIN cho máy cài chỗ lạ."""
    envp = (os.environ.get("JAVIS_COPILOT_BIN") or "").strip()
    if envp:
        try:
            if Path(envp).exists():
                return envp
        except Exception:
            pass
    home = _home_dir()
    # ~/.local/bin TRƯỚC PATH: đó là chỗ nút Cài đặt thả binary, và PATH của tiến trình server
    # trong container không có ~/.local/bin.
    cho = [home / ".local" / "bin" / "copilot"]
    if os.environ.get("APPDATA"):
        cho.append(Path(os.environ["APPDATA"]) / "npm" / "copilot.cmd")
    for p in cho:
        try:
            if p.exists():
                return str(p)
        except Exception:
            pass
    return tim_binary("copilot")


def lenh_cai() -> str:
    return LENH_CAI_WIN if os.name == "nt" else LENH_CAI


def _moi_truong() -> dict:
    """Môi trường cho mọi tiến trình `copilot`.

    - COPILOT_AUTO_UPDATE=false + NO_COLOR: không tải bản mới giữa lượt, không mã màu lẫn vào JSONL.
    - GỠ GH_TOKEN / GITHUB_TOKEN: CLI xét chúng TRƯỚC phiên đã đăng nhập (help environment). Một
      máy chủ hay có sẵn GITHUB_TOKEN cho việc khác (CI, git, `gh`) - thường là PAT cổ điển `ghp_`
      mà Copilot từ chối - và thế là đăng nhập trên thẻ vô nghĩa, lượt nào cũng đỏ. Ai muốn dùng
      token qua biến môi trường thì đặt COPILOT_GITHUB_TOKEN (tên riêng của Copilot, được giữ),
      hoặc JAVIS_COPILOT_GIU_GH_TOKEN=1 để giữ nguyên hai biến kia.
    """
    env = dict(os.environ)
    env["COPILOT_AUTO_UPDATE"] = "false"
    env.setdefault("NO_COLOR", "1")
    if (env.get("JAVIS_COPILOT_GIU_GH_TOKEN") or "").strip() != "1":
        env.pop("GH_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
    return env


# ---------------------------------------------------------------------------
# Dò cờ: hỏi `--help` trước (khuôn grok_cli.co_co). Bản CLI này ra bản mới gần như mỗi ngày.
# ---------------------------------------------------------------------------
_HELP_CACHE: dict = {"path": None, "text": "", "ts": 0.0}
_HELP_TTL = 300.0
_HELP_TTL_LOI = 120.0


def _chay_help(cli: str, args: list, timeout: float = 30) -> str:
    try:
        r = subprocess.run([cli] + args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, creationflags=_no_window(),
                           env=_moi_truong(), stdin=subprocess.DEVNULL)
        return (r.stdout or "") + "\n" + (r.stderr or "")
    except Exception:
        return ""


def _help_text() -> str:
    cli = find_copilot_cli()
    if not cli:
        return ""
    now = time.time()
    if _HELP_CACHE["path"] == cli and now - _HELP_CACHE["ts"] < (
            _HELP_TTL if _HELP_CACHE["text"] else _HELP_TTL_LOI):
        return _HELP_CACHE["text"]
    txt = _chay_help(cli, ["--help"])
    _HELP_CACHE.update(path=cli, text=txt, ts=now)
    return txt


def co_co(*ten_co: str) -> bool:
    """Binary trên máy CÓ khai cờ này không. Fail-closed: không đọc được help thì coi như không."""
    txt = _help_text()
    return bool(txt) and any(c in txt for c in ten_co)


def co_effort(muc: Optional[str]) -> list:
    """['--reasoning-effort', muc] khi help khai cả cờ lẫn giá trị, không thì [].

    Đo: giá trị lạ (vd `ultra`) làm CLI thoát ngay "invalid value", hỏng trọn lượt. Nên phải thấy
    giá trị trong CHÍNH dòng `[possible values: ...]` của cờ, không chỉ ở đâu đó trong help."""
    if not muc:
        return []
    txt = _help_text()
    m = re.search(r"--reasoning-effort[^\[]*\[possible values:([^\]]*)\]", txt or "", re.S)
    if not m:
        return []
    gia_tri = [x.strip() for x in m.group(1).split(",")]
    return ["--reasoning-effort", str(muc)] if str(muc) in gia_tri else []


def phien_moi() -> str:
    return str(uuid.uuid4())


def permission_cho_mode(mode: Optional[str]) -> list:
    """Mức quyền MinMin -> cờ quyền của Copilot. Mode lạ về nấc CHẶT NHẤT (fail-closed).

    Hàng rào thật vẫn là header `X-Javis-Mode` ở MCP hub (chặn cả tool của MCP đã đấu); cờ ở đây
    là lớp thứ hai, chặn tool NATIVE của Copilot (shell, ghi file) mà hub không nhìn thấy.
    `--allow-all-tools` luôn có: thiếu nó thì chế độ không tương tác dừng lại hỏi duyệt và treo.
    """
    m = str(mode or "").strip().lower()
    luat = _LUAT_CHAN.get(m)
    if luat is None:
        luat, m = _LUAT_CHAN["suggest"], "suggest"
    args = ["--allow-all-tools"]
    # Đọc web là thao tác ĐỌC, mọi mức đều được; không cho thì CLI hỏi duyệt URL rồi treo.
    if co_co("--allow-all-urls"):
        args.append("--allow-all-urls")
    # Mức full: bỏ rào đường dẫn (mặc định Copilot chỉ cho đụng thư mục làm việc), ngang quyền
    # Claude Code ở mức full.
    if m == "full" and co_co("--allow-all-paths"):
        args.append("--allow-all-paths")
    if co_co("--deny-tool"):
        args += [f"--deny-tool={r}" for r in luat]
    elif luat:
        # Bản CLI không có cờ chặn thì KHÔNG chạy mức thấp bằng toàn quyền: bỏ hẳn allow-all
        # để CLI tự từ chối tool cần duyệt (chế độ không tương tác không ai duyệt được).
        args.remove("--allow-all-tools")
    return args


# ---------------------------------------------------------------------------
# MCP: hub MinMin -> `<brain>/.copilot/mcp-config.json`, truyền bằng --additional-mcp-config
# ---------------------------------------------------------------------------
# Vì sao KHÔNG ghi vào `~/.copilot/mcp-config.json` như `copilot mcp add`: file HOME dùng chung
# cho mọi brain, brain sau đè header X-Javis-Vault của brain trước khi hai lượt chạy cùng lúc.
# `--additional-mcp-config @<file>` (đo: có trong help, cờ được nhận) cộng thêm server CHO RIÊNG
# lượt đó, nên mỗi brain một file, không giẫm lên cấu hình cá nhân. File nằm trong brain để
# "Kiểm tra lại" đọc lại được; nó chứa hub token nên đã chặn khỏi bản sao lưu git
# (`git_brain._BACKUP_SKIP_SUBSTR` có `/.copilot/`).
TEN_MCP = "javis"


def hub_entry(url: str, headers: Optional[dict] = None) -> dict:
    """Hình dạng entry MCP HTTP của Copilot, chép đúng thứ `copilot mcp add --transport http`
    ghi ra (đo trên binary). Giữ trong module engine chứ không viết tay ở main.py: mỗi CLI một
    khoá (`url` / `serverUrl` / `httpUrl`), chép nhầm là bộ não chạy không có tool nào."""
    e: dict = {"type": "http", "url": url, "tools": ["*"]}
    if headers:
        e["headers"] = dict(headers)
    return e


def mcp_config_path(vault_root) -> Path:
    return Path(vault_root).expanduser() / ".copilot" / "mcp-config.json"


def ghi_mcp_settings(vault_root, hub: Optional[dict]) -> Optional[str]:
    """Ghi file MCP của brain. `hub=None` (hub tắt) -> gỡ entry javis, giữ phần còn lại."""
    try:
        p = mcp_config_path(vault_root)
        ok, cu = _doc_jsonc(p)
        if not ok:
            print(f"[copilot mcp] `{p}` không đọc được, KHÔNG ghi đè", file=sys.stderr)
            return None
        servers = cu.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
        if hub:
            servers[TEN_MCP] = hub
        else:
            servers.pop(TEN_MCP, None)
        cu["mcpServers"] = servers
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cu, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(p, 0o600)   # chứa hub token
        except Exception:
            pass
        return str(p)
    except Exception as e:
        print(f"[copilot mcp] {e}", file=sys.stderr)
        return None


def trang_thai_mcp(vault_root) -> dict:
    """ĐỌC LẠI file vừa ghi: "đã ghi" không phải bằng chứng, đọc lại mới là (bài học `agy`)."""
    p = mcp_config_path(vault_root)
    ra = {"file": str(p), "ton_tai": False, "co_javis": False, "url": "", "so_header": 0}
    try:
        ra["ton_tai"] = p.exists()
    except Exception:
        return ra
    if not ra["ton_tai"]:
        return ra
    _ok, d = _doc_jsonc(p)
    e = (d.get("mcpServers") or {}).get(TEN_MCP) if isinstance(d.get("mcpServers"), dict) else None
    if isinstance(e, dict) and e.get("url"):
        ra["co_javis"] = True
        ra["url"] = str(e.get("url") or "")
        h = e.get("headers")
        ra["so_header"] = len(h) if isinstance(h, dict) else 0
    return ra


def _co_mcp_args(mcp_file: Optional[str]) -> list:
    if mcp_file and co_co("--additional-mcp-config"):
        try:
            if Path(mcp_file).exists():
                return ["--additional-mcp-config", "@" + str(mcp_file)]
        except Exception:
            pass
    return []


# ---------------------------------------------------------------------------
# Trạng thái đăng nhập: ĐỌC FILE, không đẻ tiến trình (trang Models gọi liên tục)
# ---------------------------------------------------------------------------
def _thong_tin_dang_nhap() -> dict:
    """Đọc ~/.copilot/config.json. Chỉ trả TÊN tài khoản/host và việc có token hay không,
    không bao giờ trả giá trị token."""
    ok, d = _doc_jsonc(_copilot_home() / "config.json")
    users = d.get("loggedInUsers") if isinstance(d.get("loggedInUsers"), list) else []
    cuoi = d.get("lastLoggedInUser") if isinstance(d.get("lastLoggedInUser"), dict) else {}
    tokens = d.get("authTokens") if isinstance(d.get("authTokens"), dict) else {}
    co_token = any(isinstance(v, dict) and len(str(v.get("token") or "").strip()) >= 8
                   for v in tokens.values())
    acc = str(cuoi.get("login") or "")
    host = str(cuoi.get("host") or "")
    if not acc and users and isinstance(users[0], dict):
        acc = str(users[0].get("login") or "")
        host = host or str(users[0].get("host") or "")
    return {"doc_duoc": ok, "co_user": bool(users or cuoi), "co_token": co_token,
            "account": acc, "host": host, "khoa": sorted(str(k) for k in d.keys())[:30]}


def auth_status() -> dict:
    """{connected, method, account, plan, error}.

    `loggedInUsers` có mặt = đã đăng nhập: đo được rằng khi token KHÔNG lưu được (không có
    keychain, không trả lời câu hỏi lưu plaintext) thì CLI không ghi gì vào file này cả. Token có
    thể nằm trong keychain hệ điều hành (máy desktop) thay vì `authTokens` - vẫn là đã đăng nhập.
    """
    cli = find_copilot_cli()
    if not cli:
        return {"connected": False, "method": "", "account": "", "plan": "",
                "error": "Chưa cài GitHub Copilot CLI. Bấm \"Cài đặt\" trên thẻ này."}
    tt = _thong_tin_dang_nhap()
    if tt["co_user"]:
        return {"connected": True, "method": "oauth" if tt["co_token"] else "keychain",
                "account": tt["account"], "plan": "", "host": tt["host"], "error": ""}
    tok = (os.environ.get("COPILOT_GITHUB_TOKEN") or "").strip()
    if tok:
        if tok.startswith("ghp_"):
            return {"connected": False, "method": "", "account": "", "plan": "",
                    "error": ("Biến COPILOT_GITHUB_TOKEN đang là PAT cổ điển (ghp_), Copilot không "
                              "nhận loại này. Dùng nút Đăng nhập GitHub hoặc PAT fine-grained có "
                              "quyền \"Copilot Requests\".")}
        return {"connected": True, "method": "env-token", "account": "", "plan": "", "error": ""}
    if not tt["doc_duoc"]:
        return {"connected": False, "method": "", "account": "", "plan": "",
                "error": f"Không đọc được {_copilot_home() / 'config.json'}. Bấm \"Kiểm tra lại\"."}
    return {"connected": False, "method": "", "account": "", "plan": "",
            "error": "Đã cài Copilot CLI nhưng chưa đăng nhập. Bấm \"Đăng nhập GitHub\" trên thẻ này."}


def chan_doan() -> dict:
    """Chẩn đoán KHÔNG lộ token: đường binary, thư mục cấu hình, tên file, tên khoá cấp cao."""
    home = _copilot_home()
    ra = {"cli_path": find_copilot_cli() or "", "home": str(home), "home_ton_tai": False,
          "files": [], "khoa_cap_cao": [], "co_token": False, "nhat_ky": nhat_ky_dang_nhap(),
          "co_gh_token_env": bool((os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
                                   or "").strip())}
    try:
        ra["home_ton_tai"] = home.is_dir()
        for f in sorted(home.iterdir())[:40]:
            ra["files"].append({"ten": f.name, "bytes": f.stat().st_size if f.is_file() else -1})
    except Exception:
        pass
    tt = _thong_tin_dang_nhap()
    ra["khoa_cap_cao"] = tt["khoa"]
    ra["co_token"] = tt["co_token"] or tt["co_user"]
    return ra


def login_huong_dan() -> dict:
    return {"cai": lenh_cai(), "dang_nhap": "copilot login --device-code",
            "ghi_chu": ("Cách khác: đặt biến COPILOT_GITHUB_TOKEN bằng PAT fine-grained có quyền "
                        "\"Copilot Requests\" (PAT cổ điển ghp_ không dùng được).")}


# ---------------------------------------------------------------------------
# Đăng nhập device code trong pty, điều khiển từ trang Models
# ---------------------------------------------------------------------------
# Bốn bài học của `agy` áp nguyên ở đây: (1) CLI có thể HỎI rồi im chờ phím - ở Copilot là câu
# "Store token in plaintext config file? (y/N)", MinMin trả lời "y" (không thì đăng nhập xong mà
# token không được lưu, đo được); (2) đọc pty có hạn chờ (select); (3) pty rộng 1000 cột để link
# không bị bẻ dòng; (4) luồng đọc TỰ đóng fd của nó.
_LOGIN: dict = {"proc": None, "fd": None, "url": "", "code": "", "log": None, "ma_thoat": None,
                "bat_dau": 0.0, "da_tra_loi": False}
_CAI: dict = {"dang_chay": False, "ok": None, "log": None, "bat_dau": 0.0}
_NHAT_KY_TOI_DA = 60
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_MA_RE = re.compile(r"\b[A-Z0-9]{4,}(?:-[A-Z0-9]{4,})+\b")
# CSI, OSC (kết thúc bằng BEL hoặc ESC \\ - đo: OSC 52 mang mã dạng base64), và mấy mã đơn.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
                      r"|\x1b[()][A-Z0-9]|\x1b[=>78]")
_BIMAT_RE = re.compile(r"\b(?:gh[oupsr]_|github_pat_)[A-Za-z0-9_]{8,}|\b[A-Za-z0-9_\-]{36,}\b")
_HOI_LUU_RE = re.compile(r"plaintext\s+config\s+file\?\s*\(y/N\)", re.I)


def _lam_sach(s: str) -> str:
    return _ANSI_RE.sub("", s or "")


def _che(s: str) -> str:
    """Che chuỗi giống token. Nhật ký này hiện ra màn hình và vào ảnh chụp người dùng gửi đi."""
    s = re.sub(r"((?:code|token|access_token)=)[^&\s]+", r"\1[đã che]", s)
    return _BIMAT_RE.sub("[đã che]", s)


def _ghi(store: dict, dong: str) -> None:
    if store.get("log") is None:
        return
    d = _che(_lam_sach(dong).strip())
    if d:
        store["log"].append(d)


def _nhat_ky(store: dict) -> list:
    log = store.get("log")
    return list(log) if log else []


def nhat_ky_dang_nhap() -> list:
    return _nhat_ky(_LOGIN)


def _env_dang_nhap() -> dict:
    e = _moi_truong()
    e["TERM"] = "xterm-256color"
    e.setdefault("LANG", "C.UTF-8")
    e["COLUMNS"] = "1000"
    e["LINES"] = "50"
    # Ép đúng một kiểu: không có trình duyệt nào trên máy chủ để mở cả.
    e.setdefault("BROWSER", "echo")
    return e


def _mo_pty(args: list):
    """Chạy trong pseudo-terminal (POSIX). Không có pty (Windows) -> ống thường: vẫn bóc được link
    + mã, chỉ mất bước trả lời câu hỏi lưu token (Windows có Credential Manager nên không hỏi)."""
    try:
        import pty
        master, slave = pty.openpty()
        try:
            import fcntl, struct, termios
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 1000, 0, 0))
        except Exception:
            pass
        proc = subprocess.Popen(args, stdin=slave, stdout=slave, stderr=slave,
                                env=_env_dang_nhap(), start_new_session=True, close_fds=True,
                                cwd=str(_home_dir()), creationflags=_no_window())
        os.close(slave)
        return proc, master
    except Exception:
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, creationflags=_no_window(),
                                env=_env_dang_nhap(), cwd=str(_home_dir()))
        return proc, None


def _gui(proc, fd, chu: str) -> bool:
    b = chu.encode("utf-8")
    try:
        if fd is not None:
            os.write(fd, b)
            return True
        if proc and proc.stdin:
            proc.stdin.write(b)
            proc.stdin.flush()
            return True
    except Exception:
        pass
    return False


def _bat_url_code(sach: str) -> None:
    if not _LOGIN["url"]:
        for m in _URL_RE.finditer(sach):
            u = m.group(0).rstrip(".,);]")
            if "github" in u.lower() or "/login/device" in u:
                _LOGIN["url"] = u
                break
    if not _LOGIN["code"]:
        m = _MA_RE.search(sach)
        if m:
            _LOGIN["code"] = m.group(0)


def _doc_luong(proc, fd) -> None:
    """Đọc output `copilot login`, cắt dòng theo cả `\\n` lẫn `\\r`, trả lời câu hỏi lưu token."""
    buf = ""
    gan_day = ""

    def _doc() -> str:
        if fd is not None:
            try:
                import select
                r, _, _ = select.select([fd], [], [], 0.5)
                if not r:
                    return ""
                return os.read(fd, 4096).decode("utf-8", "replace")
            except (OSError, ValueError):
                return ""
        try:
            return proc.stdout.read(1).decode("utf-8", "replace")
        except Exception:
            return ""

    def _tra_loi_neu_hoi():
        nonlocal gan_day
        if _LOGIN["da_tra_loi"] or not _HOI_LUU_RE.search(_lam_sach(gan_day)):
            return
        _LOGIN["da_tra_loi"] = True
        gan_day = ""
        _gui(proc, fd, "y\r")
        _ghi(_LOGIN, "[MinMin trả lời y: máy chủ không có keychain, token lưu ở "
                     "~/.copilot/config.json quyền 0600 - không lưu thì đăng nhập xong vẫn như chưa]")

    try:
        while True:
            ch = _doc()
            if not ch:
                if proc.poll() is not None:
                    break
                _tra_loi_neu_hoi()
                time.sleep(0.05)
                continue
            gan_day = (gan_day + ch)[-3000:]
            for c in ch:
                if c in "\r\n":
                    if buf.strip():
                        _bat_url_code(_lam_sach(buf))
                        _ghi(_LOGIN, buf)
                    buf = ""
                else:
                    buf += c
                    if len(buf) > 4000:
                        _bat_url_code(_lam_sach(buf))
                        _ghi(_LOGIN, buf)
                        buf = ""
            _bat_url_code(_lam_sach(buf))
            _tra_loi_neu_hoi()
    except Exception as e:
        _ghi(_LOGIN, f"[MinMin đọc output lỗi] {type(e).__name__}: {e}")
    if buf.strip():
        _bat_url_code(_lam_sach(buf))
        _ghi(_LOGIN, buf)
    try:
        _LOGIN["ma_thoat"] = proc.wait(timeout=5)
        _ghi(_LOGIN, f"[copilot login kết thúc, mã thoát {_LOGIN['ma_thoat']}]")
    except Exception:
        pass
    if fd is not None:
        if _LOGIN.get("fd") == fd:
            _LOGIN["fd"] = None
        try:
            os.close(fd)
        except Exception:
            pass


def huy_dang_nhap() -> None:
    """Tắt tiến trình đăng nhập. KHÔNG đóng fd ở đây - luồng đọc tự đóng (bài học 26.10.206)."""
    proc = _LOGIN.get("proc")
    if proc and proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass
    _LOGIN.update(proc=None, fd=None, url="", code="", da_tra_loi=False)


def login_start(cho_giay: float = 30.0) -> dict:
    """Chạy `copilot login --device-code` trong pty, trả {ok, url, code} cho trang Models.

    Tiến trình được giữ chạy tiếp: nó tự hỏi GitHub tới khi người dùng nhập mã xong trên web.
    Giao diện theo dõi bằng `login_trang_thai()`.
    """
    cli = find_copilot_cli()
    if not cli:
        return {"ok": False, "can_cai": True,
                "error": "Chưa cài GitHub Copilot CLI. Bấm Cài đặt trước."}
    huy_dang_nhap()
    from collections import deque
    args = [cli, "login", "--device-code"]
    try:
        proc, fd = _mo_pty(args)
    except Exception as e:
        return {"ok": False, "error": f"Không chạy được copilot: {type(e).__name__}: {e}"}
    _LOGIN.update(proc=proc, fd=fd, url="", code="", ma_thoat=None, bat_dau=time.time(),
                  da_tra_loi=False, log=deque(maxlen=_NHAT_KY_TOI_DA))
    _ghi(_LOGIN, "[MinMin chạy] copilot login --device-code (qua pty)")
    threading.Thread(target=_doc_luong, args=(proc, fd), name="minmin-copilot-login",
                     daemon=True).start()
    han = time.time() + cho_giay
    while time.time() < han and not (_LOGIN["url"] and _LOGIN["code"]) and proc.poll() is None:
        time.sleep(0.2)
    if _LOGIN["url"]:
        return {"ok": True, "xong": False, "url": _LOGIN["url"], "code": _LOGIN["code"],
                "nhat_ky": nhat_ky_dang_nhap()}
    duoi = [x for x in nhat_ky_dang_nhap() if not x.startswith("[")][-6:]
    huy_dang_nhap()
    return {"ok": False,
            "error": (f"Copilot CLI không in ra link đăng nhập trong {int(cho_giay)} giây."
                      + (" CLI vừa in: " + " | ".join(x[:160] for x in duoi) if duoi else "")),
            "nhat_ky": nhat_ky_dang_nhap()}


def login_trang_thai() -> dict:
    proc = _LOGIN.get("proc")
    dang_chay = bool(proc and proc.poll() is None)
    d = auth_status()
    if not d.get("connected") and proc is not None and not dang_chay:
        time.sleep(0.6)      # file vừa ghi xong ngay lúc tiến trình thoát
        d = auth_status()
    loi = ""
    if not d.get("connected") and not dang_chay:
        ma = _LOGIN.get("ma_thoat")
        cuoi = [x for x in nhat_ky_dang_nhap() if not x.startswith("[")]
        loi = d.get("error") or "Đăng nhập chưa xong."
        if ma not in (None, 0):
            loi = f"`copilot login` thoát với mã {ma}. " + loi
        if cuoi:
            loi += " CLI nói: " + cuoi[-1][:200]
    return {"connected": bool(d.get("connected")), "dang_cho": dang_chay,
            "url": _LOGIN.get("url", ""), "code": _LOGIN.get("code", ""),
            "account": d.get("account", ""), "ma_thoat": _LOGIN.get("ma_thoat"),
            "nhat_ky": nhat_ky_dang_nhap(), "error": loi}


def logout() -> dict:
    """Ngắt: gỡ `authTokens`, `loggedInUsers`, `lastLoggedInUser` khỏi ~/.copilot/config.json.

    Vì sao tự sửa file: CLI không có lệnh đăng xuất ngoài giao diện tương tác (`/logout`), đo được
    `copilot logout` trả "Invalid command format". Ba khoá đó đúng là thứ `copilot login` thêm
    vào (đo trước/sau). Giữ nguyên mọi khoá khác và hai dòng chú thích đầu file. File hỏng thì
    KHÔNG ghi. Token trong keychain hệ điều hành (máy desktop) thì MinMin không gỡ được - nói ra.
    """
    huy_dang_nhap()
    p = _copilot_home() / "config.json"
    ok, d = _doc_jsonc(p)
    if not ok:
        return {"ok": False, "error": f"Không đọc được {p}, không dám sửa."}
    co_token = bool(d.get("authTokens"))
    if not any(k in d for k in ("authTokens", "loggedInUsers", "lastLoggedInUser")):
        return {"ok": True, "ghi_chu": "Máy này chưa đăng nhập Copilot."}
    for k in ("authTokens", "loggedInUsers", "lastLoggedInUser"):
        d.pop(k, None)
    try:
        dau = [x for x in p.read_text(encoding="utf-8").splitlines() if x.lstrip().startswith("//")]
        p.write_text("\n".join(dau + [json.dumps(d, ensure_ascii=False, indent=2)]) + "\n",
                     encoding="utf-8")
        os.chmod(p, 0o600)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    ra = {"ok": True}
    if not co_token:
        ra["ghi_chu"] = ("Token nằm trong keychain của hệ điều hành; MinMin đã gỡ tài khoản khỏi "
                         "danh sách đăng nhập nhưng không xoá được token trong keychain.")
    if (os.environ.get("COPILOT_GITHUB_TOKEN") or "").strip():
        ra["ghi_chu"] = "Máy đang đặt biến COPILOT_GITHUB_TOKEN; Copilot vẫn dùng biến đó."
    return ra


def cai_dat_start() -> dict:
    """`npm install -g --prefix ~/.local @github/copilot` chạy nền (lý do chọn khuôn: xem LENH_CAI)."""
    if find_copilot_cli():
        return {"ok": True, "da_co": True}
    if _CAI["dang_chay"]:
        return {"ok": True, "dang_chay": True}
    npm = tim_binary("npm")
    if not npm:
        return {"ok": False, "error": "Máy chủ không có npm (Node.js). Cài Node.js 22 trở lên trước."}
    from collections import deque
    _CAI.update(dang_chay=True, ok=None, log=deque(maxlen=_NHAT_KY_TOI_DA), bat_dau=time.time())
    if os.name == "nt":
        args = [npm, "install", "-g", GOI_NPM]
    else:
        args = [npm, "install", "-g", "--prefix", str(_home_dir() / ".local"), GOI_NPM]

    def _chay():
        try:
            _ghi(_CAI, "[MinMin chạy] " + " ".join(["npm"] + args[1:]))
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, creationflags=_no_window(),
                                 cwd=str(_home_dir()))
            for dong in iter(p.stdout.readline, b""):
                _ghi(_CAI, dong.decode("utf-8", "replace"))
            ma = p.wait(timeout=900)
            _ghi(_CAI, f"[lệnh cài kết thúc, mã thoát {ma}]")
            _CAI["ok"] = bool(find_copilot_cli())
        except Exception as e:
            _ghi(_CAI, f"[lỗi cài] {type(e).__name__}: {e}")
            _CAI["ok"] = False
        finally:
            _CAI["dang_chay"] = False
            _HELP_CACHE.update(path=None, text="", ts=0.0)

    threading.Thread(target=_chay, name="minmin-copilot-install", daemon=True).start()
    return {"ok": True, "dang_chay": True}


def cai_dat_trang_thai() -> dict:
    co = find_copilot_cli()
    d = {"dang_chay": _CAI["dang_chay"], "ok": _CAI["ok"] if not co else True,
         "cli_path": co or "", "nhat_ky": _nhat_ky(_CAI)}
    if _CAI["ok"] is False and not co:
        d["error"] = "Cài không thành công. Xem nhật ký bên dưới."
    return d


# ---------------------------------------------------------------------------
# Model: danh mục của CHÍNH bản CLI (`copilot help config`, đo: không cần mạng)
# ---------------------------------------------------------------------------
_MODEL_CACHE: dict = {"path": None, "ids": None, "ts": 0.0}


def _tach_model(txt: str) -> list:
    """Bóc khối `model`: trong `copilot help config`:

          `model`: AI model to use for Copilot CLI; ...
            - "claude-sonnet-5.5"
            - "gpt-5.4"
          `contextTier`: ...
    """
    ids: list = []
    trong = False
    for dong in (txt or "").splitlines():
        s = dong.strip()
        if s.startswith("`model`:"):
            trong = True
            continue
        if trong:
            m = re.match(r'^-\s*"([^"]+)"\s*$', s)
            if m:
                if m.group(1) not in ids:
                    ids.append(m.group(1))
                continue
            if s.startswith("`") or (ids and s):
                break
    return ids


def list_models() -> Optional[list]:
    """`auto` + danh mục model của bản CLI đang cài.

    Đây là danh mục mà BẢN CLI biết, không phải danh sách gói của người dùng được dùng: gói Free
    ít model hơn Pro/Pro+, chọn model ngoài gói thì lượt chat báo lỗi của GitHub. `auto` đứng đầu
    vì đó là lựa chọn luôn hợp lệ với mọi gói.
    """
    cli = find_copilot_cli()
    if not cli:
        return None
    now = time.time()
    if _MODEL_CACHE["path"] == cli and _MODEL_CACHE["ids"] and now - _MODEL_CACHE["ts"] < 600:
        return list(_MODEL_CACHE["ids"])
    ids = _tach_model(_chay_help(cli, ["help", "config"]))
    if ids:
        ids = ["auto"] + [x for x in ids if x != "auto"]
        _MODEL_CACHE.update(path=cli, ids=ids, ts=now)
    else:
        ids = list(MODELS_DU_PHONG)
    _ok, st = _doc_jsonc(_copilot_home() / "settings.json")
    ten = str(st.get("model") or "").strip()
    if ten and ten not in ids:
        ids.insert(1, ten)
    return list(ids)


# ---------------------------------------------------------------------------
# Câu lỗi
# ---------------------------------------------------------------------------
def dich_loi(loi: str) -> str:
    """Câu lỗi của CLI -> tiếng Việt khi nhận ra. Câu hết hạn mức GIỮ NGUYÊN tiếng Anh ở cuối để
    `limit_learner` còn nhận dạng được (nó soi đúng chữ của nhà cung cấp)."""
    l = (loi or "").lower()
    if "no authentication information" in l or "not authenticated" in l or "please log in" in l:
        return ("Copilot CLI chưa đăng nhập. Mở trang Models, thẻ GitHub Copilot, bấm "
                "\"Đăng nhập GitHub\".")
    if "classic personal access token" in l:
        return ("Token GitHub trong biến môi trường là PAT cổ điển (ghp_), Copilot không nhận. "
                "Gỡ biến đó hoặc thay bằng PAT fine-grained có quyền \"Copilot Requests\".")
    if "not have access to copilot" in l or "no copilot" in l or "copilot is not enabled" in l \
            or "access denied by copilot policy" in l:
        return ("Tài khoản GitHub này chưa có gói Copilot (hoặc tổ chức đã tắt Copilot CLI). "
                "Bật gói Copilot ở github.com/settings/copilot. Chi tiết: " + loi[:300])
    if "rate limit" in l or ("weekly" in l and "limit" in l):
        return "Gói Copilot đã chạm hạn mức. " + loi[:400]
    return loi


# ---------------------------------------------------------------------------
_CO_MANG_PROMPT = ("-p", "--prompt")
_CHAN_DAU_TOI_DA = 20
_CHAN_DUOI_TOI_DA = 20
_CHAN_LOAI_TOI_DA = 40
# Linux cấm MỘT đối số dài quá 128 KiB (MAX_ARG_STRLEN); Windows trần cả dòng lệnh 32767 ký tự.
# Vượt ngưỡng thì đưa prompt qua stdin (đo: ống stdin là chế độ prompt của Copilot).
_TRAN_ARGV = 24000 if os.name == "nt" else 100_000


def _cat_args(args: list) -> list:
    """Cờ đã truyền để hiện khi hỏng, KHÔNG kèm prompt và KHÔNG kèm đường file MCP."""
    ra, truoc = [], ""
    for a in [str(x) for x in args[1:]]:
        if a.startswith("-"):
            ra.append(a)
            truoc = a
            continue
        if truoc in _CO_MANG_PROMPT:
            ra.append("<prompt>")
        elif truoc and len(a) <= 40 and not a.startswith(("/", "\\", "@")):
            ra.append(a)
        truoc = ""
    return ra[:24]


def _chan_moi() -> dict:
    from collections import deque
    return {"raw": [], "duoi": deque(maxlen=_CHAN_DUOI_TOI_DA), "loai": set(), "vot": [],
            "ma_thoat": None, "stderr": "", "args": [], "so_dong": 0, "canh_bao": [],
            "mcp": {}, "loi_phien": ""}


_KHOA_CHU = ("content", "text", "deltaContent", "message", "summary")


def _vot(ev) -> list:
    ra = []

    def di(o, sau=0):
        if sau > 5 or len(ra) >= 10:
            return
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and v.strip() and k in _KHOA_CHU:
                    ra.append(v)
                elif isinstance(v, (dict, list)):
                    di(v, sau + 1)
        elif isinstance(o, list):
            for v in o[:20]:
                di(v, sau + 1)

    di((ev or {}).get("data"))
    return ra


class CopilotCLI:
    """Một lượt `copilot -p` không tương tác. Cùng hợp đồng sự kiện với GrokCLI:
    {"type": "tool_call"|"tool_result"|"final"|"error"|"usage", ...}."""

    def __init__(self, cwd: Optional[str] = None, tag: str = "chat", model: Optional[str] = None,
                 instructions: Optional[str] = None):
        self.cli_path = find_copilot_cli()
        self.cwd = cwd or os.getcwd()
        self.tag = tag
        self.model = model
        self.instructions = instructions
        # Có giá trị -> `--session-id <id>` nối lại mạch; None -> MinMin cấp uuid mới cho lượt
        # này (Copilot nhận uuid tự cấp, đo trên help: "or set the UUID for a new session").
        self.session_id = None
        self.mode = "full"
        self.effort = None
        self.mcp_file: Optional[str] = None     # `_apply_copilot_hub` đặt
        self.extra_args: list = []
        self.timeout = float(os.environ.get("JAVIS_COPILOT_TIMEOUT") or 900)

    def is_available(self) -> bool:
        return self.cli_path is not None

    def _build_args(self, prompt: Optional[str]) -> list:
        """`prompt=None` nghĩa là prompt đi qua stdin."""
        args = [self.cli_path]
        if self.model and co_co("--model"):
            args += ["--model", self.model]
        args += permission_cho_mode(self.mode)
        args += co_effort(self.effort)
        if co_co("--output-format"):
            args += ["--output-format", "json"]
        for co in ("--no-auto-update", "--no-ask-user", "--no-color"):
            if co_co(co):
                args.append(co)
        # Tắt MCP dựng sẵn của GitHub (github-mcp-server): chủ shop không cần tool GitHub, và
        # bảng khai báo tool của nó ăn token ngữ cảnh mỗi lượt. Tool của MinMin đi qua hub.
        if co_co("--disable-builtin-mcps") and os.environ.get("JAVIS_COPILOT_GITHUB_MCP") != "1":
            args.append("--disable-builtin-mcps")
        args += _co_mcp_args(self.mcp_file)
        if not self.session_id:
            self.session_id = phien_moi()
        if co_co("--session-id"):
            args += ["--session-id", self.session_id]
        args += list(self.extra_args)
        if prompt is not None:
            args += ["-p", prompt]
        return args

    async def query(self, prompt: str) -> AsyncIterator[dict]:
        if not self.cli_path:
            yield {"type": "error",
                   "content": "Chưa cài GitHub Copilot CLI. Bấm \"Cài đặt\" ở thẻ GitHub Copilot "
                              "trên trang Models."}
            return
        full = (self.instructions.strip() + "\n\n" + prompt) if self.instructions else prompt
        qua_stdin = len(full.encode("utf-8")) > _TRAN_ARGV or \
            os.environ.get("JAVIS_COPILOT_PROMPT_STDIN") == "1"
        args = self._build_args(None if qua_stdin else full)
        chan = _chan_moi()
        st = {"manh": [], "delta": {}, "da_loi": False}
        async for ra in self._mot_lan(args, chan, st, full if qua_stdin else None):
            if ra.get("type") == "error":
                st["da_loi"] = True
            yield ra
        text = self._chu_cuoi(st)
        if not text and not st["da_loi"]:
            text = "\n".join(chan["vot"]).strip()
        if text:
            yield {"type": "final", "content": text}
        elif not st["da_loi"]:
            yield {"type": "error", "content": self._loi_trong(chan)}

    @staticmethod
    def _chu_cuoi(st: dict) -> str:
        """Câu trả lời = `assistant.message` cuối cùng có chữ (phần trước tool call thường chỉ là
        "để em xem..."). Không có message trọn nào thì ghép các mẩu delta."""
        for t in reversed(st["manh"]):
            if t.strip():
                return t.strip()
        return "".join(st["delta"].values()).strip()

    async def _mot_lan(self, args: list, chan: dict, st: dict,
                       stdin_txt: Optional[str]) -> AsyncIterator[dict]:
        chan["args"] = _cat_args(args)
        loop = asyncio.get_running_loop()
        hang: asyncio.Queue = asyncio.Queue()
        HET = object()
        qua_gio = threading.Event()

        def doc_luong():
            proc = None
            canh = None
            try:
                proc = subprocess.Popen(
                    args, stdin=subprocess.PIPE if stdin_txt is not None else subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.cwd, text=True,
                    encoding="utf-8", errors="replace", bufsize=1, creationflags=_no_window(),
                    env=_moi_truong(), start_new_session=(os.name != "nt"))
                try:
                    import tien_trinh_nen
                    tien_trinh_nen.ghi_nhom(self.tag, proc.pid)
                except Exception:
                    pass
                if stdin_txt is not None:
                    # Ghi ở luồng riêng: prompt dài hơn bộ đệm ống mà ghi chặn ở đây thì không ai
                    # đọc stdout, CLI đứng chờ, hai bên khoá nhau.
                    def _ghi_vao():
                        try:
                            proc.stdin.write(stdin_txt)
                            proc.stdin.close()
                        except Exception:
                            pass
                    threading.Thread(target=_ghi_vao, daemon=True).start()

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
                    if len(chan["raw"]) < _CHAN_DAU_TOI_DA:
                        chan["raw"].append(line[:1000])
                    else:
                        chan["duoi"].append(line[:1000])
                    try:
                        ev = json.loads(line)
                        if not isinstance(ev, dict):
                            ev = {"_raw": line}
                    except json.JSONDecodeError:
                        ev = {"_raw": line}
                    loop.call_soon_threadsafe(hang.put_nowait, ev)
                err = ""
                try:
                    err = (proc.stderr.read() or "").strip()
                except Exception:
                    pass
                ma = proc.wait()
                chan["ma_thoat"] = ma
                chan["stderr"] = err[:1500]
                if qua_gio.is_set():
                    loop.call_soon_threadsafe(hang.put_nowait, {
                        "_exit": -1, "_err": f"Copilot CLI chạy quá {int(self.timeout)}s nên bị cắt. "
                                             "Việc thật sự dài thì nâng JAVIS_COPILOT_TIMEOUT."})
                elif ma != 0:
                    loop.call_soon_threadsafe(hang.put_nowait, {"_exit": ma, "_err": err})
                elif err:
                    print(f"[copilot stderr] {err[:2000]}", file=sys.stderr)
            except OSError as e:
                if getattr(e, "errno", None) in (errno.E2BIG, errno.ENAMETOOLONG):
                    t = ("Hội thoại quá dài so với trần dòng lệnh. Mở một hội thoại mới, hoặc đặt "
                         "JAVIS_COPILOT_PROMPT_STDIN=1 để đưa prompt qua stdin.")
                else:
                    t = f"{type(e).__name__}: {e}"
                loop.call_soon_threadsafe(hang.put_nowait, {"_exit": -1, "_err": t})
            except Exception as e:
                loop.call_soon_threadsafe(hang.put_nowait,
                                          {"_exit": -1, "_err": f"{type(e).__name__}: {e}"})
            finally:
                if canh:
                    canh.cancel()
                try:
                    if proc and proc.poll() is None:
                        proc.terminate()
                except Exception:
                    pass
                loop.call_soon_threadsafe(hang.put_nowait, HET)

        threading.Thread(target=doc_luong, name=f"minmin-copilot-{self.tag}", daemon=True).start()
        while True:
            ev = await hang.get()
            if ev is HET:
                break
            for ra in self._doi_su_kien(ev, st, chan):
                yield ra

    # -- dịch sự kiện (sơ đồ từ schemas/session-events.schema.json của gói) --------------------
    def _doi_su_kien(self, ev: dict, st: dict, chan: Optional[dict] = None) -> list:
        if chan is None:
            chan = _chan_moi()
        if "_raw" in ev:
            # Không phải JSON: bản CLI chưa có `--output-format json`, hoặc chữ lọt ra stdout.
            # Giữ làm chữ (không vứt im lặng), nhưng chỉ dùng khi không có message nào.
            chan["vot"].append(str(ev["_raw"]))
            return []
        if "_exit" in ev:
            loi = str(ev.get("_err") or "").strip()
            if not loi:
                # stderr rỗng: lấy dòng thô không phải JSON cuối cùng làm lời CLI.
                loi = "\n".join(chan["vot"][-3:]).strip() or chan.get("loi_phien") or \
                    f"Copilot CLI thoát với mã {ev.get('_exit')}."
            if st.get("da_loi") and chan.get("loi_phien"):
                return []        # đã báo lỗi từ sự kiện session.error, đừng báo đôi
            return [{"type": "error", "content": dich_loi(loi)[:1500]}]

        t = str(ev.get("type") or "")
        d = ev.get("data") if isinstance(ev.get("data"), dict) else {}
        if t and len(chan["loai"]) < _CHAN_LOAI_TOI_DA:
            chan["loai"].add(t)
        con = bool(d.get("parentToolCallId"))   # sự kiện của sub-agent, không phải câu trả lời

        if t == "session.start":
            sid = str(d.get("sessionId") or "").strip()
            if sid:
                self.session_id = sid
            return []
        if t == "assistant.message_delta":
            if not con:
                k = str(d.get("messageId") or "")
                st["delta"][k] = st["delta"].get(k, "") + str(d.get("deltaContent") or "")
            return []
        if t == "assistant.message":
            if not con:
                st["manh"].append(str(d.get("content") or ""))
            return []
        if t == "tool.execution_start":
            sv, tn = str(d.get("mcpServerName") or ""), str(d.get("mcpToolName") or "")
            ten = f"mcp__{sv}__{tn}" if sv and tn else str(d.get("toolName") or "tool")
            vao = d.get("arguments")
            return [{"type": "tool_call", "name": ten, "id": str(d.get("toolCallId") or ""),
                     "input": vao if isinstance(vao, dict) else {"arguments": vao}}]
        if t == "tool.execution_complete":
            kq = d.get("result") if isinstance(d.get("result"), dict) else {}
            er = d.get("error") if isinstance(d.get("error"), dict) else {}
            return [{"type": "tool_result", "id": str(d.get("toolCallId") or ""),
                     "status": "completed" if d.get("success") else "failed",
                     "content": str(kq.get("content") or er.get("message") or "")[:2000]}]
        if t == "assistant.usage":
            vao = int(d.get("inputTokens") or 0)
            ra = int(d.get("outputTokens") or 0)
            return [{"type": "usage", "input_tokens": vao, "output_tokens": ra,
                     "total_tokens": vao + ra, "cached": int(d.get("cacheReadTokens") or 0)}]
        if t == "session.error":
            tin = str(d.get("message") or d.get("errorType") or "Copilot CLI lỗi.")
            chan["loi_phien"] = tin
            return [{"type": "error", "content": dich_loi(tin)[:1500]}]
        if t == "session.warning":
            chan["canh_bao"].append(str(d.get("message") or "")[:300])
            return []
        if t == "session.mcp_server_status_changed":
            ten = str(d.get("serverName") or "")
            if ten:
                chan["mcp"][ten] = {"status": str(d.get("status") or ""),
                                    "error": str(d.get("error") or "")[:300]}
            return []
        if t.startswith(("session.", "assistant.", "tool.", "model.", "permission.", "hook.",
                         "subagent.", "skill.", "mcp.", "user.", "system.")):
            return []            # loại đã biết, không mang câu trả lời
        # Loại lạ: không đưa vào câu trả lời, nhưng vớt chữ để dùng khi cả lượt không ra chữ nào.
        if len(chan["vot"]) < 60:
            chan["vot"] += _vot(ev)
        return []

    @staticmethod
    def _loi_trong(chan: dict) -> str:
        """Lượt không ra chữ nào: kể ra đúng những gì MinMin thấy, không một câu chung chung."""
        loai = sorted(x for x in chan.get("loai") or [] if x)
        dong = list(chan.get("raw") or []) + list(chan.get("duoi") or [])
        n = int(chan.get("so_dong") or 0)
        if not n:
            noi = (f"Copilot CLI chạy xong (mã thoát {chan.get('ma_thoat')}) nhưng KHÔNG in ra gì.")
        else:
            noi = f"Copilot CLI in ra {n} dòng nhưng không có câu trả lời nào"
            if loai:
                noi += " (thấy: " + ", ".join(loai[:12]) + ")"
            noi += "."
            if dong:
                noi += "\nDòng cuối: " + dong[-1][:400]
        if chan.get("canh_bao"):
            noi += "\nCLI cảnh báo: " + " | ".join(chan["canh_bao"][:3])
        if chan.get("stderr"):
            noi += "\nCLI báo ở stderr: " + chan["stderr"][:300]
        if chan.get("args"):
            noi += "\nCờ đã truyền: " + " ".join(chan["args"])
        return noi


# ---------------------------------------------------------------------------
def _mcp_bi_chan(chan: dict) -> str:
    """Câu tiếng Việt nếu CLI báo chặn server `javis` theo chính sách (đo được trên OAuth giả)."""
    for c in chan.get("canh_bao") or []:
        l = c.lower()
        if ("blocked by policy" in l and TEN_MCP in l) or "third-party mcp servers are disabled" in l:
            return ("Copilot báo chính sách của tổ chức/gói đang TẮT MCP bên thứ ba, nên tool của "
                    "MinMin (POS, Ads, Zalo, file brain) không vào được bộ não này. Gói Business/"
                    "Enterprise: nhờ quản trị bật \"MCP servers in Copilot\". CLI nói: " + c[:200])
    return ""


def kiem_tra_nhanh(timeout: float = 90.0, mcp_file: Optional[str] = None) -> dict:
    """Chạy THẬT một lượt ngắn: CLI + đăng nhập + gói có dùng được không, và (khi có `mcp_file`)
    hub MCP của MinMin có kết nối được trong chính lượt đó không.

    `config.json` còn nằm đó không chứng minh gói còn quyền dùng; chỉ chat thật mới chứng minh.
    """
    cli = find_copilot_cli()
    if not cli:
        return {"ok": False, "error": "Chưa cài GitHub Copilot CLI. Bấm \"Cài đặt\" trên thẻ."}
    g = CopilotCLI(cwd=str(_home_dir()), tag="kiem-tra")
    g.mode = "suggest"
    g.mcp_file = mcp_file
    args = g._build_args("Trả lời đúng một chữ: ok")
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, creationflags=_no_window(),
                           env=_moi_truong(), cwd=str(_home_dir()), stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Copilot CLI không trả lời trong {int(timeout)} giây."}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    chan = _chan_moi()
    st = {"manh": [], "delta": {}, "da_loi": False}
    loi = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        chan["so_dong"] += 1
        if len(chan["raw"]) < _CHAN_DAU_TOI_DA:
            chan["raw"].append(line[:1000])
        else:
            chan["duoi"].append(line[:1000])
        try:
            ev = json.loads(line)
            if not isinstance(ev, dict):
                ev = {"_raw": line}
        except json.JSONDecodeError:
            ev = {"_raw": line}
        for x in g._doi_su_kien(ev, st, chan):
            if x.get("type") == "error":
                loi.append(x["content"])
    ra: dict = {"canh_bao": chan["canh_bao"][:5]}
    if mcp_file:
        ra["mcp_lan_chay"] = chan["mcp"].get(TEN_MCP) or {}
        chan_mcp = _mcp_bi_chan(chan)
        if chan_mcp:
            ra["mcp_bi_chan"] = chan_mcp
    if r.returncode != 0 or loi:
        tho = (r.stderr or "").strip() or "\n".join(chan["vot"][-3:])
        ra.update(ok=False, error=(loi[0] if loi else dich_loi(tho)[:500])
                  or f"Copilot CLI thoát mã {r.returncode}.")
        return ra
    tra = CopilotCLI._chu_cuoi(st) or "\n".join(chan["vot"]).strip()
    if tra:
        ra.update(ok=True, reply=tra[:200])
        return ra
    ra.update(ok=False, error=CopilotCLI._loi_trong(chan))
    return ra
