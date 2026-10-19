"""Bộ não thứ 15: Meta Muse Code CLI (binary `muse`), chạy bằng GÓI THUÊ BAO Muse Code.

Chép khuôn `grok_cli.py` (bộ não thứ 11) vì hai engine giống nhau ở chỗ quan trọng nhất: Javis
KHÔNG giữ token của ai cả, nó gọi đúng binary `muse` của máy và mượn phiên đăng nhập mà chính
CLI đó giữ trong `~/.config/muse/auth.json`. Gói Everyday / High / Power / Maximum của Meta CHỈ
đăng nhập được bằng trình duyệt; `META_API_KEY` thì trả theo lượng dùng và THẮNG phiên đăng
nhập nếu có trong môi trường (đúng "auth precedence" trong tài liệu dev.meta.ai/docs/muse-code).

Ba chỗ khác `grok`, đều ghi lại để không ai đoán lại:

- **Headless là `muse exec "<prompt>"` với `--json`** (JSONL trên stdout), KHÔNG phải `-p`. Sơ đồ
  sự kiện JSONL CHƯA được Meta tài liệu hoá (ngày 19/10/2026). Giao thức MSP của họ có
  `item/started`, `item/delta`, `item/updated`, `item/completed`, `turn/completed`,
  `approval/requested`; nhưng dòng `--json` có đúng hình đó không thì chưa ai đo trên máy thật.
  Nên `_doi_su_kien` đọc theo HÌNH DẠNG, nhận ba kiểu (MSP, kiểu Claude Code, kiểu chung), và
  mọi dòng thô đi qua vòng đệm `_SU_KIEN_THO` để `chan_doan()` đưa lên thẻ Models - chủ repo dán
  lại là sửa được bảng dịch mà không phải đoán.
- **MCP cấu hình ở `~/.config/muse/settings.json`** (JSON, `schema_version: 1`), tức cấu hình CÁ
  NHÂN chứ không theo thư mục làm việc như `<brain>/.grok/config.toml`. Nên `ghi_mcp_settings`
  GỘP vào file đó (giữ nguyên server khác của người dùng, sao lưu trước khi ghi), và entry
  `javis` mang header X-Javis-Vault của brain vừa chạy - hai brain chạy xen kẽ thì entry đổi
  theo lượt, `trang_thai_mcp` nói rõ entry đang trỏ brain nào.
- **Không có lệnh đăng nhập headless.** `muse` tương tác hỏi "Sign in with your browser" rồi in
  link + mã (báo cáo bên thứ ba nói là device code, chạy được qua SSH). `login_start` mở `muse`
  trong pseudo-terminal, bóc link + mã như `grok login --device-auth`; bóc hụt thì trả đuôi
  output thô và câu hướng dẫn tự gõ.

Cờ của `muse exec` lấy từ tài liệu chính chủ: `--prompt-file`, `--json`, `--max-model-steps`,
`--disable-reminders`, `--disable-request-user-input`, `--disable-write`, `--disable-shell`,
`--session-id`, `--allow-workspace-switch`, `--workspace`, `--model`, `--reasoning-effort`
(none|minimal|low|medium|high|xhigh|max|ultra, `none` bị từ chối), `--approval-mode`
(on-request|untrusted|never), `--disable-approval`, `--disable-sandbox`, `--yolo`,
`--trust-workspace`, `--preset`. Mã thoát: 0 ok, 1 lỗi/huỷ, 2 sai cú pháp, 130/143 tín hiệu.
"""
from __future__ import annotations

import asyncio
import errno
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import AsyncIterator, Optional

from claude_cli import _home_dir, _no_window, tim_binary

# Meta không có lệnh liệt kê model; bảng tĩnh theo tài liệu. Hai bản "contributor" xếp CUỐI và
# thẻ Models phải nói rõ: chọn chúng là cho Meta huấn luyện trên dữ liệu gửi lên.
MODELS = ["muse-spark-1.3", "muse-spark-1.2", "muse-wonder-1.0",
          "muse-spark-1.3-contributor", "muse-spark-1.2-contributor"]
MODEL_MAC_DINH = "muse-spark-1.3"

LENH_CAI = "curl -fsSL https://dev.meta.ai/install.sh | sh"
LENH_CAI_WIN = "irm https://dev.meta.ai/install.ps1 | iex"

# Mức quyền Javis -> cờ của `muse exec`. Xem `permission_cho_mode`.
#
# HÀNG RÀO THẬT vẫn là header `X-Javis-Mode` mà MCP hub áp cho mọi tool đi qua nó. Cờ ở đây là
# lớp thứ hai, chặn tool NATIVE của chính Muse (ghi file / chạy lệnh), thứ hub không nhìn thấy.
# `--approval-mode never` + `--disable-request-user-input`: headless mà CLI dừng lại hỏi là
# treo tới hết giờ, nên bảo thẳng là không có ai để hỏi.
_LUAT_CHAN = {
    # suggest: CHỈ ĐỌC. Chặn cả ghi file lẫn lệnh máy.
    "suggest": ("--disable-write", "--disable-shell", "--approval-mode", "never"),
    # auto: ghi file nháp được, KHÔNG chạy lệnh máy.
    "auto": ("--disable-shell", "--approval-mode", "never", "--disable-approval"),
    # full: tắt duyệt lẫn sandbox. `--disable-sandbox` vì Docker của Javis không có bubblewrap,
    # để sandbox bật là mọi lệnh máy thoát lỗi ngay.
    "full": ("--yolo", "--disable-sandbox"),
}

# Cờ truyền cho MỌI lượt headless, bất kể mức quyền.
_CO_CHUNG = ("--disable-request-user-input", "--disable-reminders", "--json",
             "--trust-workspace")
MAX_MODEL_STEPS = 60

# Thang nghĩ của Javis -> giá trị `--reasoning-effort`. `off` thành `minimal` chứ KHÔNG BAO GIỜ
# `none`: tài liệu nói `none` bị từ chối, truyền vào là hỏng cả lượt chat vì một tuỳ chọn phụ.
_EFFORT_MAP = {"off": "minimal", "minimal": "minimal", "low": "low", "medium": "medium",
               "high": "high", "xhigh": "xhigh", "max": "max", "ultra": "ultra"}


def _muse_home() -> Path:
    """Thư mục cấu hình của `muse`: `~/.config/muse` (tôn trọng XDG_CONFIG_HOME và cửa thoát
    JAVIS_MUSE_HOME cho máy cài chỗ lạ)."""
    env = (os.environ.get("JAVIS_MUSE_HOME") or "").strip()
    if env:
        return Path(env).expanduser()
    xdg = (os.environ.get("XDG_CONFIG_HOME") or "").strip()
    if xdg:
        return Path(xdg).expanduser() / "muse"
    return _home_dir() / ".config" / "muse"


def _doc_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def find_muse_cli() -> Optional[str]:
    """Tìm binary `muse`. Cửa thoát JAVIS_MUSE_BIN cho máy cài chỗ lạ."""
    envp = (os.environ.get("JAVIS_MUSE_BIN") or "").strip()
    if envp:
        try:
            if Path(envp).exists():
                return envp
        except Exception:
            pass
    cli = tim_binary("muse")
    if cli:
        return cli
    home = _home_dir()
    # Installer chính chủ thả binary vào ~/.local/bin (Unix) hoặc %LOCALAPPDATA% (Windows).
    for p in (home / ".local" / "bin" / "muse",
              home / ".muse" / "bin" / "muse",
              Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "muse" / "muse.exe"):
        try:
            if p.exists():
                return str(p)
        except Exception:
            pass
    return None


def lenh_cai() -> str:
    return LENH_CAI_WIN if os.name == "nt" else LENH_CAI


def _moi_truong() -> dict:
    """Môi trường cho một lượt `muse`: kế thừa của server. Không ép tắt màu/tự cập nhật bằng
    biến môi trường nào vì Meta chưa khai biến như vậy; `NO_COLOR` thì mọi CLI tử tế đều hiểu."""
    env = dict(os.environ)
    env.setdefault("NO_COLOR", "1")
    return env


# ---------------------------------------------------------------------------
# Dò cờ: hỏi `--help` trước, đừng đoán
# ---------------------------------------------------------------------------
_HELP_CACHE: dict = {"path": None, "text": "", "ts": 0.0}
_HELP_TTL = 300.0
_HELP_TTL_LOI = 120.0

# Cờ mà TÀI LIỆU chính chủ khai cho `muse exec`. Khác `grok_cli.co_co` (fail-closed tuyệt đối):
# `--help` của `muse` là của lệnh gốc, cờ của `exec` có thể không nằm trong đó, mà fail-closed
# ở đây là rụng luôn `--json` và không đọc được một sự kiện nào. Nên cờ CÓ TÀI LIỆU thì tin tài
# liệu khi help không nhắc; cờ ngoài bảng vẫn fail-closed như cũ.
_CO_TAI_LIEU = frozenset((
    "--prompt-file", "--json", "--max-model-steps", "--disable-reminders",
    "--disable-request-user-input", "--disable-write", "--disable-shell", "--session-id",
    "--allow-workspace-switch", "--workspace", "--model", "--reasoning-effort",
    "--approval-mode", "--disable-approval", "--disable-sandbox", "--yolo", "--trust-workspace",
    "--preset",
))


def _help_text() -> str:
    """`muse exec --help` + `muse --help`, nhớ trong RAM. Rỗng nếu không chạy được."""
    cli = find_muse_cli()
    if not cli:
        return ""
    now = time.time()
    if _HELP_CACHE["path"] == cli and now - _HELP_CACHE["ts"] < (
            _HELP_TTL if _HELP_CACHE["text"] else _HELP_TTL_LOI):
        return _HELP_CACHE["text"]
    txt = ""
    for args in ([cli, "exec", "--help"], [cli, "--help"]):
        try:
            r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=20, creationflags=_no_window(),
                               env=_moi_truong(), stdin=subprocess.DEVNULL)
            txt += (r.stdout or "") + "\n" + (r.stderr or "") + "\n"
        except Exception:
            pass
    _HELP_CACHE.update(path=cli, text=txt.strip(), ts=now)
    return _HELP_CACHE["text"]


def co_co(*ten_co: str) -> bool:
    """Binary trên máy CÓ cờ này không.

    `--help` nhắc tới -> có. `--help` không nhắc nhưng cờ nằm trong bảng tài liệu chính chủ ->
    vẫn có (xem `_CO_TAI_LIEU`). Cờ lạ ngoài bảng mà help không nhắc -> không.
    """
    txt = _help_text()
    if txt and any(c in txt for c in ten_co):
        return True
    return any(c in _CO_TAI_LIEU for c in ten_co)


def co_effort(muc: Optional[str]) -> list:
    """['--reasoning-effort', '<giá trị>'] theo thang Javis; [] nếu mức lạ hoặc CLI không khai cờ."""
    if not muc:
        return []
    gia = _EFFORT_MAP.get(str(muc).strip().lower())
    if not gia or gia == "none":
        return []
    if not co_co("--reasoning-effort"):
        return []
    return ["--reasoning-effort", gia]


def phien_moi() -> str:
    return str(uuid.uuid4())


def permission_cho_mode(mode: Optional[str]) -> list:
    """Mức quyền của Javis -> cờ của `muse exec`. Giá trị lạ về nấc CHẶT NHẤT (fail-closed)."""
    m = str(mode or "").strip().lower()
    luat = _LUAT_CHAN.get(m)
    if luat is None:
        luat = _LUAT_CHAN["suggest"]
    args: list = []
    i = 0
    while i < len(luat):
        co = luat[i]
        gia = luat[i + 1] if i + 1 < len(luat) and not luat[i + 1].startswith("-") else None
        if co_co(co):
            args.append(co)
            if gia is not None:
                args.append(gia)
        i += 2 if gia is not None else 1
    return args


def co_chung() -> list:
    """Cờ đi với MỌI lượt headless."""
    args: list = []
    for co in _CO_CHUNG:
        if co_co(co):
            args.append(co)
    if co_co("--max-model-steps"):
        args += ["--max-model-steps", str(MAX_MODEL_STEPS)]
    return args


# ---------------------------------------------------------------------------
# MCP: gộp hub của Javis vào `~/.config/muse/settings.json`
# ---------------------------------------------------------------------------
def hub_entry(url: str, headers: Optional[dict] = None) -> dict:
    """Hình dạng entry MCP HTTP của Muse Code (tài liệu: `transport: streamable_http`).

    Để hình dạng entry TRONG module engine chứ không viết tay ở `main.py` - bài học `agy` đọc
    `serverUrl`, Grok đọc `url`, Gemini đọc `httpUrl`; chép nhầm khoá là bộ não chạy mấy bản mà
    không có lấy một tool nào của Javis.
    """
    e: dict = {"transport": "streamable_http", "url": url, "enabled": True, "mode": "optional"}
    if headers:
        e["headers"] = dict(headers)
    return e


def mcp_config_path(vault_root=None) -> Path:
    """`vault_root` nhận cho ĐỐI XỨNG với grok_cli; Muse đọc cấu hình cá nhân chứ không theo
    thư mục làm việc, nên đường dẫn không phụ thuộc brain."""
    return _muse_home() / "settings.json"


def _doc_json_ky(p: Path) -> tuple:
    """(đọc_được, dict). File chưa có -> (True, {}); file hỏng -> (False, {}) và KHÔNG ghi đè.

    Cùng lý do với `grok_cli._doc_toml_ky`: gộp "file hỏng" vào "chưa có" rồi ghi tiếp là xoá
    sạch cấu hình cá nhân của người dùng không một câu lỗi.
    """
    try:
        if not p.exists():
            return True, {}
    except Exception:
        return False, {}
    d = _doc_json(p)
    if isinstance(d, dict):
        return True, d
    print(f"[muse mcp settings] `{p}` không đọc được, KHÔNG ghi đè.", file=sys.stderr)
    return False, {}


def ghi_mcp_settings(vault_root, hub: Optional[dict]) -> Optional[str]:
    """Gộp đúng MỘT entry `mcp_servers.javis` vào `~/.config/muse/settings.json`.

    Giữ nguyên mọi server khác người dùng đã khai, giữ `schema_version` nếu có (đặt 1 nếu chưa),
    và SAO LƯU bản trước ra `settings.json.bak` trước khi ghi - đây là file cá nhân của người
    dùng, không phải file Javis dựng trong brain.

    `hub=None` (chưa bật hub) -> GỠ entry javis nếu có. Trả đường dẫn đã ghi, None nếu không.
    """
    try:
        p = mcp_config_path(vault_root)
        doc_duoc, cu = _doc_json_ky(p)
        if not doc_duoc:
            return None
        servers = cu.get("mcp_servers")
        if not isinstance(servers, dict):
            servers = {}
        moi = dict(servers)
        if hub:
            moi["javis"] = hub
        else:
            moi.pop("javis", None)
        if moi == servers and p.exists():
            return str(p)          # không đổi gì thì không ghi, không sao lưu thừa
        if moi:
            cu["mcp_servers"] = moi
        else:
            cu.pop("mcp_servers", None)
        cu.setdefault("schema_version", 1)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            if p.exists():
                (p.parent / (p.name + ".bak")).write_text(p.read_text(encoding="utf-8"),
                                                          encoding="utf-8")
        except Exception:
            pass
        p.write_text(json.dumps(cu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(p, 0o600)   # chứa hub token
        except Exception:
            pass
        return str(p)
    except Exception as e:
        print(f"[muse mcp settings] {e}", file=sys.stderr)
        return None


def trang_thai_mcp(vault_root=None) -> dict:
    """ĐỌC LẠI chính file vừa ghi để trang Models nói được sự thật ("đã ghi xong" không phải
    bằng chứng). Kèm `vault` mà entry đang trỏ, vì file là cấu hình cá nhân dùng chung."""
    p = mcp_config_path(vault_root)
    ra = {"file": str(p), "ton_tai": False, "co_javis": False, "url": "", "so_header": 0,
          "vault": "", "vault_khop": False}
    try:
        ra["ton_tai"] = p.exists()
    except Exception:
        return ra
    if not ra["ton_tai"]:
        return ra
    d = _doc_json(p)
    e = ((d or {}).get("mcp_servers") or {}).get("javis") if isinstance(d, dict) else None
    if isinstance(e, dict):
        ra["co_javis"] = True
        ra["url"] = str(e.get("url") or "")
        h = e.get("headers")
        ra["so_header"] = len(h) if isinstance(h, dict) else 0
        ra["vault"] = str((h or {}).get("X-Javis-Vault") or "") if isinstance(h, dict) else ""
        if vault_root and ra["vault"]:
            try:
                ra["vault_khop"] = (Path(ra["vault"]).resolve()
                                    == Path(vault_root).expanduser().resolve())
            except Exception:
                ra["vault_khop"] = str(vault_root) == ra["vault"]
    return ra


# ---------------------------------------------------------------------------
# Đăng nhập
# ---------------------------------------------------------------------------
_KHOA_TOKEN = ("access_token", "accesstoken", "refresh_token", "refreshtoken", "id_token",
               "idtoken", "session_token", "sessiontoken", "token", "api_key", "apikey",
               "credential", "credentials", "bearer", "jwt")
_TOKEN_DAI_TOI_THIEU = 8
_FILE_PHIEN = ("auth.json", "credentials.json", "session.json", "tokens.json", "oauth.json")


def _tim_token(o, sau: int = 0):
    """Trong cây JSON này có token nào không. Trả TÊN khoá, không bao giờ trả giá trị."""
    if sau > 6:
        return ""
    if isinstance(o, dict):
        for k, v in o.items():
            kl = str(k).lower().replace("-", "_")
            if (kl in _KHOA_TOKEN and isinstance(v, str)
                    and len(v.strip()) >= _TOKEN_DAI_TOI_THIEU):
                return str(k)
            trong = _tim_token(v, sau + 1)
            if trong:
                return trong
    elif isinstance(o, list):
        for v in o[:20]:
            trong = _tim_token(v, sau + 1)
            if trong:
                return trong
    return ""


def _tim_chuoi(o, ten, sau: int = 0) -> str:
    """Giá trị chuỗi đầu tiên của một trong các khoá `ten` (so không phân biệt hoa thường), tìm
    ở mọi tầng. "" nếu không có."""
    if sau > 6:
        return ""
    ten = tuple(str(x).lower() for x in ten)
    if isinstance(o, dict):
        for k, v in o.items():
            if str(k).lower() in ten and isinstance(v, str) and v.strip():
                return v.strip()
        for v in o.values():
            trong = _tim_chuoi(v, ten, sau + 1)
            if trong:
                return trong
    elif isinstance(o, list):
        for v in o[:20]:
            trong = _tim_chuoi(v, ten, sau + 1)
            if trong:
                return trong
    return ""


def _tim_dict(o, ten, sau: int = 0) -> Optional[dict]:
    """Dict đầu tiên nằm dưới một trong các khoá `ten`, tìm ở mọi tầng."""
    if sau > 6:
        return None
    ten = tuple(str(x).lower() for x in ten)
    if isinstance(o, dict):
        for k, v in o.items():
            if str(k).lower() in ten and isinstance(v, dict):
                return v
        for v in o.values():
            trong = _tim_dict(v, ten, sau + 1)
            if trong is not None:
                return trong
    elif isinstance(o, list):
        for v in o[:20]:
            trong = _tim_dict(v, ten, sau + 1)
            if trong is not None:
                return trong
    return None


def _doc_phien() -> tuple:
    """Tìm file phiên đăng nhập trong `~/.config/muse`. Trả (path|None, dict|None)."""
    home = _muse_home()
    ten_da_thu = set()
    ds = []
    for ten in _FILE_PHIEN:
        ten_da_thu.add(ten)
        ds.append(home / ten)
    try:
        for f in sorted(home.glob("*.json"))[:20]:
            if f.name not in ten_da_thu and f.name != "settings.json":
                ds.append(f)
    except Exception:
        pass
    for f in ds:
        try:
            if not f.is_file() or f.stat().st_size > 4_000_000:
                continue
        except Exception:
            continue
        d = _doc_json(f)
        if isinstance(d, (dict, list)) and _tim_token(d):
            return f, d
    return None, None


def auth_status() -> dict:
    """Đã đăng nhập chưa: {connected, method, account, plan, error}. ĐỌC FILE, không gọi CLI.

    `META_API_KEY` xét TRƯỚC phiên đăng nhập, đúng thứ tự ưu tiên trong tài liệu của Meta: có
    biến đó là CLI trả theo lượng dùng chứ không chạy gói, và thẻ Models phải nói đúng điều đó.
    """
    cli = find_muse_cli()
    if not cli:
        return {"connected": False, "method": "", "account": "", "plan": "",
                "error": f"Chưa cài Muse Code CLI ({lenh_cai()})."}
    if (os.environ.get("META_API_KEY") or "").strip():
        return {"connected": True, "method": "meta-api-key", "account": "", "plan": "",
                "error": ""}
    f, auth = _doc_phien()
    if auth is not None:
        acc = _tim_chuoi(auth, ("email", "account", "username", "handle", "user", "name"))
        plan = _tim_chuoi(auth, ("plan", "subscription", "tier"))
        pt = _tim_chuoi(auth, ("issuer", "method", "provider", "auth_type")) or "oauth"
        return {"connected": True, "method": pt, "account": acc, "plan": plan,
                "error": "", "file": str(f)}
    co_file = [x["ten"] for x in _liet_ke_home() if x["ten"] != "settings.json"]
    if co_file:
        return {"connected": False, "method": "", "account": "", "plan": "",
                "error": ("Thư mục " + str(_muse_home()) + " đã có file (" + ", ".join(co_file[:6])
                          + ") nhưng Javis không nhận ra token đăng nhập trong đó. "
                            "Bấm \"Kiểm tra lại\" để xem chi tiết.")}
    return {"connected": False, "method": "", "account": "", "plan": "",
            "error": "Đã cài Muse Code CLI nhưng chưa đăng nhập. Bấm \"Đăng nhập\" ngay trên thẻ này."}


def _liet_ke_home() -> list:
    ra = []
    try:
        for f in sorted(_muse_home().iterdir())[:40]:
            try:
                ra.append({"ten": f.name, "bytes": f.stat().st_size if f.is_file() else -1})
            except Exception:
                ra.append({"ten": f.name, "bytes": -1})
    except Exception:
        pass
    return ra


# Vòng đệm dòng JSONL THÔ của lượt `muse exec` gần nhất (mọi lượt trong tiến trình này ghi vào
# đây). Chỉ để chẩn đoán: sơ đồ sự kiện chưa có tài liệu, chủ repo dán 30 dòng này lại là sửa
# được bảng dịch. Mỗi dòng cắt 600 ký tự; prompt KHÔNG nằm trong stdout nên không lộ nội dung.
_SU_KIEN_THO_TOI_DA = 30
_SU_KIEN_THO: deque = deque(maxlen=_SU_KIEN_THO_TOI_DA)
_SU_KIEN_THO_LOCK = threading.Lock()


def _ghi_su_kien_tho(dong: str) -> None:
    with _SU_KIEN_THO_LOCK:
        _SU_KIEN_THO.append(dong[:600])


def su_kien_tho() -> list:
    with _SU_KIEN_THO_LOCK:
        return list(_SU_KIEN_THO)


def chan_doan() -> dict:
    """Mọi thứ để trả lời "vì sao thẻ Muse vẫn báo chưa đăng nhập / vì sao chat ra ô trống",
    KHÔNG lộ token: đường binary, thư mục cấu hình, TÊN file, TÊN khoá cấp cao, nhật ký đăng
    nhập, và 30 dòng JSONL thô của lượt gần nhất (`su_kien_tho`)."""
    home = _muse_home()
    ra = {"cli_path": find_muse_cli() or "", "home": str(home), "home_ton_tai": False,
          "files": [], "file_phien": "", "khoa_cap_cao": [], "co_token": False,
          "khoa_token": "", "meta_api_key": bool((os.environ.get("META_API_KEY") or "").strip()),
          "nhat_ky": nhat_ky_dang_nhap(), "su_kien_tho": su_kien_tho()}
    try:
        ra["home_ton_tai"] = home.is_dir()
    except Exception:
        pass
    ra["files"] = _liet_ke_home()
    f, d = _doc_phien()
    if f is not None:
        ra["file_phien"] = str(f)
        ra["co_token"] = True
        ra["khoa_token"] = _tim_token(d)
        if isinstance(d, dict):
            ra["khoa_cap_cao"] = [str(k) for k in list(d.keys())[:40]]
        return ra
    for x in ra["files"]:
        if not x["ten"].endswith(".json"):
            continue
        d2 = _doc_json(home / x["ten"])
        if isinstance(d2, dict):
            ra["khoa_cap_cao"] += [x["ten"] + ":" + str(k) for k in list(d2.keys())[:20]]
    return ra


def login_huong_dan() -> dict:
    return {
        "cai": lenh_cai(),
        "dang_nhap": "muse",
        "ghi_chu": ("Cách khác: chạy `muse` trong terminal của máy chạy MinMin rồi chọn "
                    "\"Sign in with your browser\"; nó in ra một link (và mã) để mở trên máy "
                    "bạn. Gói Everyday/High/Power/Maximum chỉ đăng nhập được kiểu này; "
                    "`META_API_KEY` thì trả theo lượng dùng. `muse logout` để ngắt."),
    }


# ---------------------------------------------------------------------------
# Đăng nhập qua pseudo-terminal, điều khiển từ dashboard
# ---------------------------------------------------------------------------
_LOGIN: dict = {"proc": None, "url": "", "code": "", "loi": "", "bat_dau": 0.0,
                "log": None, "ma_thoat": None, "fd": None}
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_CODE_RE = re.compile(r"\b[A-Z0-9]{4,}(?:-[A-Z0-9]{4,})+\b")
_BIMAT_RE = re.compile(r"\b(?![A-Z0-9]{4,}-)[A-Za-z0-9_\-]{32,}\b")
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()][A-Z0-9]")
NHAT_KY_TOI_DA = 60


def _lam_sach(dong: str) -> str:
    return _ANSI_RE.sub("", dong)


def _che_bi_mat(dong: str) -> str:
    if "://" in dong:
        return dong
    return _BIMAT_RE.sub("[đã che]", dong)


def _ghi_nhat_ky(dong: str) -> None:
    if _LOGIN.get("log") is None:
        return
    d = _che_bi_mat(_lam_sach(dong).strip())
    if d:
        _LOGIN["log"].append(d)


def nhat_ky_dang_nhap() -> list:
    log = _LOGIN.get("log")
    return list(log) if log else []


def _bat_url_code(dong: str) -> None:
    dong = _lam_sach(dong)
    if not _LOGIN["url"]:
        m = _URL_RE.search(dong)
        if m:
            _LOGIN["url"] = m.group(0).rstrip(".,);")
    if not _LOGIN["code"]:
        for tok in _CODE_RE.findall(dong):
            _LOGIN["code"] = tok
            break


def _mo_pty(args: list):
    """Mở `muse` trong pseudo-terminal (POSIX). Trả (proc, fd đọc). Không có pty -> pipe thường."""
    try:
        import pty
        master, slave = pty.openpty()
        proc = subprocess.Popen(args, stdin=slave, stdout=slave, stderr=slave,
                                env=_moi_truong(), start_new_session=True, close_fds=True,
                                creationflags=_no_window())
        os.close(slave)
        return proc, master
    except Exception:
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, creationflags=_no_window(),
                                env=_moi_truong(), start_new_session=(os.name != "nt"))
        return proc, None


def _doc_luong_login(proc, fd) -> None:
    """Đọc output của `muse` tương tác, cắt theo `\\n` lẫn `\\r`. Thấy menu đăng nhập mà chưa
    thấy link thì gửi Enter MỘT lần để chọn mục mặc định "Sign in with your browser"."""
    buf = ""
    da_enter = False
    bat_dau = time.time()

    def _doc():
        if fd is not None:
            try:
                return os.read(fd, 4096).decode("utf-8", "replace")
            except OSError:
                return ""
        try:
            return proc.stdout.read(1)
        except Exception:
            return ""

    def _gui_enter():
        try:
            if fd is not None:
                os.write(fd, b"\r")
            elif proc.stdin:
                proc.stdin.write(b"\r")
                proc.stdin.flush()
        except Exception:
            pass

    try:
        while True:
            ch = _doc()
            if not ch:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
                if (not da_enter and not _LOGIN["url"] and time.time() - bat_dau > 4
                        and re.search(r"sign in|browser|login", _lam_sach(buf), re.I)):
                    _gui_enter()
                    da_enter = True
                continue
            for c in ch:
                if c in "\r\n":
                    if buf.strip():
                        _bat_url_code(buf)
                        _ghi_nhat_ky(buf)
                    buf = ""
                else:
                    buf += c
                    if len(buf) > 4000:
                        _bat_url_code(buf)
                        _ghi_nhat_ky(buf)
                        buf = ""
            if (not da_enter and not _LOGIN["url"] and time.time() - bat_dau > 4
                    and re.search(r"sign in|browser|login", _lam_sach(buf), re.I)):
                _gui_enter()
                da_enter = True
    except Exception as e:
        _ghi_nhat_ky(f"[Javis đọc output lỗi] {type(e).__name__}: {e}")
    if buf.strip():
        _bat_url_code(buf)
        _ghi_nhat_ky(buf)
    try:
        _LOGIN["ma_thoat"] = proc.wait(timeout=5)
        _ghi_nhat_ky(f"[muse kết thúc, mã thoát {_LOGIN['ma_thoat']}]")
    except Exception:
        pass


def login_start(cho_giay: float = 30.0) -> dict:
    """Mở `muse` tương tác trong pty, bóc link + mã đăng nhập cho giao diện.

    Đã đăng nhập rồi thì trả `xong` ngay. Bóc hụt trong `cho_giay` giây thì trả lỗi kèm đuôi
    output thô và hướng dẫn tự gõ - KHÔNG đoán.
    """
    cli = find_muse_cli()
    if not cli:
        return {"ok": False, "error": f"Chưa cài Muse Code CLI ({lenh_cai()})."}
    if auth_status().get("connected"):
        return {"ok": True, "xong": True, "url": "", "code": ""}
    logout_huy_tien_trinh()
    args = [cli]
    try:
        proc, fd = _mo_pty(args)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    _LOGIN.update(proc=proc, url="", code="", loi="", bat_dau=time.time(),
                  log=deque(maxlen=NHAT_KY_TOI_DA), ma_thoat=None, fd=fd)
    _ghi_nhat_ky("[Javis chạy] muse (tương tác, qua pty)")
    threading.Thread(target=_doc_luong_login, args=(proc, fd), name="javis-muse-login",
                     daemon=True).start()
    han = time.time() + cho_giay
    while time.time() < han:
        if _LOGIN["url"]:
            break
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    if not _LOGIN["url"]:
        if proc.poll() is not None and auth_status().get("connected"):
            return {"ok": True, "xong": True, "url": "", "code": ""}
        duoi = [x for x in nhat_ky_dang_nhap() if not x.startswith("[")][-6:]
        return {"ok": False,
                "error": ("Muse Code CLI không in ra link đăng nhập trong " f"{int(cho_giay)}s. "
                          "Chạy `muse` trong terminal của MinMin rồi chọn \"Sign in with your "
                          "browser\"."
                          + (" CLI vừa in: " + " | ".join(x[:120] for x in duoi) if duoi else "")),
                "nhat_ky": nhat_ky_dang_nhap()}
    return {"ok": True, "xong": False, "url": _LOGIN["url"], "code": _LOGIN["code"],
            "nhat_ky": nhat_ky_dang_nhap()}


def login_trang_thai() -> dict:
    """Vòng đăng nhập đang tới đâu. Giao diện gọi lặp lại sau `login_start`."""
    proc = _LOGIN.get("proc")
    d = auth_status()
    dang_chay = bool(proc and proc.poll() is None)
    if d.get("connected") and dang_chay:
        # `muse` tương tác không tự thoát sau khi đăng nhập xong (nó vào màn chat). Có phiên
        # rồi thì tắt nó đi, kẻo một tiến trình chờ bàn phím vô hình nằm mãi trên máy chủ.
        logout_huy_tien_trinh()
        dang_chay = False
    elif not d.get("connected") and proc is not None and not dang_chay:
        time.sleep(0.6)
        d = auth_status()
    loi = ""
    if not d.get("connected") and not dang_chay:
        ma = _LOGIN.get("ma_thoat")
        cuoi = [x for x in nhat_ky_dang_nhap() if not x.startswith("[")]
        loi = (d.get("error") or "Đăng nhập chưa xong.")
        if ma not in (None, 0):
            loi = f"`muse` thoát với mã {ma}. " + loi
        if cuoi:
            loi += " CLI nói: " + cuoi[-1][:200]
    return {"connected": bool(d.get("connected")), "dang_cho": dang_chay,
            "url": _LOGIN.get("url", ""), "code": _LOGIN.get("code", ""),
            "account": d.get("account", ""), "plan": d.get("plan", ""),
            "ma_thoat": _LOGIN.get("ma_thoat"), "nhat_ky": nhat_ky_dang_nhap(),
            "error": loi}


def logout_huy_tien_trinh() -> None:
    proc = _LOGIN.get("proc")
    if proc and proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass
    fd = _LOGIN.get("fd")
    if fd is not None:
        try:
            os.close(fd)
        except Exception:
            pass
    _LOGIN.update(proc=None, url="", code="", loi="", bat_dau=0.0, fd=None)


def logout() -> dict:
    """`muse logout` - xoá phiên CLI đang giữ."""
    logout_huy_tien_trinh()
    cli = find_muse_cli()
    if not cli:
        return {"ok": False, "error": "Chưa cài Muse Code CLI."}
    try:
        r = subprocess.run([cli, "logout"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, creationflags=_no_window(),
                           env=_moi_truong(), stdin=subprocess.DEVNULL)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    if r.returncode != 0:
        return {"ok": False, "error": ((r.stderr or r.stdout or "").strip()[:300]
                                       or f"Thoát mã {r.returncode}")}
    return {"ok": True}


def list_models() -> Optional[list]:
    """Danh sách model cho picker: bảng tĩnh (Meta không có lệnh liệt kê). None nếu chưa cài."""
    if not find_muse_cli():
        return None
    return list(MODELS)


# ---------------------------------------------------------------------------
# Chẩn đoán một lượt: giữ nửa đầu + nửa đuôi stdout, như grok_cli
# ---------------------------------------------------------------------------
_CHAN_DAU_TOI_DA = 20
_CHAN_DUOI_TOI_DA = 20
_CHAN_LOAI_TOI_DA = 40
_CHAN_VOT_TOI_DA = 60
_CO_MANG_PROMPT = ("--prompt-file", "exec")


def _cat_args(args: list) -> list:
    """Danh sách CỜ đã truyền, KHÔNG kèm nội dung prompt (prompt là nội dung riêng người dùng)."""
    ra = []
    truoc = ""
    for a in [str(x) for x in args[1:]]:
        if a.startswith("-"):
            ra.append(a)
            truoc = a
            continue
        if a == "exec":
            ra.append(a)
            truoc = ""
            continue
        if truoc in _CO_MANG_PROMPT:
            ra.append("<prompt>")
        elif truoc and len(a) <= 40 and "\n" not in a and not a.startswith(("/", "\\")):
            ra.append(a)
        elif not truoc:
            ra.append("<prompt>")     # prompt positional của `muse exec`
        truoc = ""
    return ra[:20]


def _chan_moi() -> dict:
    return {"raw": [], "duoi": deque(maxlen=_CHAN_DUOI_TOI_DA), "loai": set(),
            "vot": [], "ma_thoat": None, "stderr": "", "args": [],
            "qua_file": False, "lan_hai": False, "so_dong": 0, "delta_ids": set(),
            "session_tu_cap": False}


_KHOA_CHU = ("delta", "text", "content", "output_text", "data", "response", "output",
             "answer", "message", "reply", "result", "completion")
# Loại sự kiện / loại item KHÔNG BAO GIỜ là câu trả lời.
_LOAI_KHONG_PHAI_TRA_LOI = ("thought", "thinking", "reasoning", "usage", "available_commands",
                            "tool_call", "tool_use", "function_call", "ping", "heartbeat",
                            "init", "system", "status", "session/started", "turn/started")
_LOAI_SUY_NGHI = ("reasoning", "thinking", "thought")
_LOAI_TOOL_GOI = ("tool_call", "tool_use", "function_call", "command", "shell", "bash",
                  "command_execution", "file_write", "file_edit", "mcp_tool_call", "tool")
_LOAI_TOOL_KQ = ("tool_result", "function_call_output", "command_output", "tool_output",
                 "mcp_tool_result")


def _chu(o) -> str:
    """Chữ người đọc được của một khối: chuỗi, hoặc danh sách block {type:text,text}."""
    if isinstance(o, str):
        return o
    if isinstance(o, list):
        ra = []
        for b in o[:50]:
            if isinstance(b, str):
                ra.append(b)
            elif isinstance(b, dict):
                bt = str(b.get("type") or "")
                if bt in _LOAI_SUY_NGHI or bt in _LOAI_TOOL_GOI or bt in _LOAI_TOOL_KQ:
                    continue
                v = b.get("text") or b.get("delta") or b.get("content") or b.get("output_text")
                if isinstance(v, (str, list)):
                    ra.append(_chu(v))
        return "".join(x for x in ra if x)
    if isinstance(o, dict):
        for k in ("delta", "text", "output_text", "content", "data"):
            v = o.get(k)
            if isinstance(v, str) and v:
                return v
            if isinstance(v, list):
                t = _chu(v)
                if t:
                    return t
            if isinstance(v, dict):
                t = _chu(v)
                if t:
                    return t
    return ""


def _vot_tu_su_kien(ev) -> list:
    """Mọi mẩu chữ người đọc được trong MỘT sự kiện lạ, bất kể sơ đồ."""
    if str((ev or {}).get("type") or (ev or {}).get("method") or "") in _LOAI_KHONG_PHAI_TRA_LOI:
        return []
    ra = []

    def di(o, sau=0):
        if sau > 6 or len(ra) >= 20:
            return
        if isinstance(o, dict):
            if str(o.get("type") or "") in _LOAI_KHONG_PHAI_TRA_LOI:
                return
            for k, v in o.items():
                if isinstance(v, str) and v.strip() and str(k).lower() in _KHOA_CHU:
                    ra.append(v)
                else:
                    di(v, sau + 1)
        elif isinstance(o, list):
            for v in o[:20]:
                di(v, sau + 1)

    di(ev)
    return ra


def _chan_dong(chan: dict) -> list:
    dau = list(chan.get("raw") or [])
    duoi = list(chan.get("duoi") or [])
    bo = int(chan.get("so_dong") or 0) - len(dau) - len(duoi)
    if bo > 0:
        return dau + [f"... (lược {bo} dòng giữa) ..."] + duoi
    return dau + duoi


_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


# ---------------------------------------------------------------------------
class MuseCLI:
    """Một lượt chạy `muse exec` headless. Cùng hợp đồng sự kiện với ClaudeSDK/CodexCLI/GrokCLI.

    query() sinh dict {"type": "text"|"tool_call"|"tool_result"|"final"|"error"|"usage", ...}
    để mọi nơi gọi (chat dashboard, Telegram, việc nền) không phải biết đây là engine nào.
    """

    def __init__(self, cwd: Optional[str] = None, tag: str = "chat", model: Optional[str] = None,
                 instructions: Optional[str] = None, reasoning: Optional[str] = None,
                 mode: str = "full", session_id: Optional[str] = None):
        self.cli_path = find_muse_cli()
        self.cwd = cwd or os.getcwd()
        self.tag = tag
        self.model = model
        self.instructions = instructions
        self.reasoning = reasoning
        # Có giá trị -> `--session-id <id>` nối mạch cũ; None -> Javis tự cấp uuid4 cho lượt
        # đầu (tài liệu nói `--session-id` nối phiên; bị từ chối thì thử lại không cờ).
        self.session_id = session_id
        self.mode = mode or "full"
        self.max_turns = 0
        self.extra_args: list = []
        # Độ sâu suy nghĩ (`main._cli_do_sau_khac` đặt thẳng giá trị cờ). None = theo `reasoning`.
        self.effort = None
        self.timeout = float(os.environ.get("JAVIS_MUSE_TIMEOUT") or 900)

    def is_available(self) -> bool:
        return self.cli_path is not None

    def _build_args(self, prompt_file: Optional[str] = None,
                    prompt_argv: Optional[str] = None,
                    session_id: Optional[str] = None, noi_mach: bool = False) -> list:
        args = [self.cli_path, "exec"]
        args += co_chung()
        if self.model and co_co("--model"):
            args += ["--model", self.model]
        args += permission_cho_mode(self.mode)
        args += co_effort(self.effort or self.reasoning)
        if self.max_turns and co_co("--max-model-steps"):
            # Trần lượt tool của người gọi (bộ não giọng đặt 1) thay cho trần chung.
            i = args.index("--max-model-steps") if "--max-model-steps" in args else -1
            if i >= 0:
                args[i + 1] = str(int(self.max_turns))
        if session_id and co_co("--session-id"):
            args += ["--session-id", session_id]
            if noi_mach and co_co("--allow-workspace-switch"):
                # Nối mạch cũ mà cwd đã đổi (mở repo khác) thì CLI từ chối; cho phép đổi.
                args.append("--allow-workspace-switch")
        args += list(self.extra_args)
        # Prompt: ưu tiên FILE (system prompt + ngữ cảnh brain vượt trần dòng lệnh Windows).
        if prompt_file and co_co("--prompt-file"):
            args += ["--prompt-file", prompt_file]
        else:
            args.append(prompt_argv if prompt_argv is not None else "")
        return args

    async def query(self, prompt: str) -> AsyncIterator[dict]:
        if not self.cli_path:
            yield {"type": "error",
                   "content": f"Không tìm thấy Muse Code CLI. Cài bằng `{lenh_cai()}` rồi chạy "
                              "`muse` một lần để đăng nhập."}
            return
        # Không có `--system-prompt`: gộp vào đầu prompt. Chỉ ở lượt MỞ MẠCH - mạch cũ (có
        # session_id) đã mang system prompt từ lượt đầu, gửi lại mỗi lượt là phí token thuê bao.
        mach_cu = bool(self.session_id)
        full = ((self.instructions.strip() + "\n\n" + prompt)
                if (self.instructions and not mach_cu) else prompt)
        tep = None
        try:
            fd, tep = tempfile.mkstemp(prefix="javis-muse-", suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(full)
        except Exception:
            tep = None
        sid = self.session_id or phien_moi()
        chan = _chan_moi()
        chan["session_tu_cap"] = not mach_cu
        args = self._build_args(prompt_file=tep, prompt_argv=full, session_id=sid,
                                noi_mach=mach_cu)
        chan["qua_file"] = bool(tep and "--prompt-file" in args)
        cac_manh: list = []
        loi_ds: list = []
        async for ra in self._mot_lan(args, cac_manh, chan, xoa_tep=None):
            if ra.get("type") == "error":
                loi_ds.append(ra)
                continue          # giữ lại, quyết định sau khi biết có thử lại không
            yield ra
        text = "".join(cac_manh).strip()
        if not text:
            text = self._vot_chu(chan)

        # `--session-id <uuid mới>` bị từ chối (mã 2 hoặc lỗi nhắc "session"): thử lại ĐÚNG
        # MỘT lần không cờ. Mạch cũ từ kho mà hỏng thì KHÔNG thử ở đây - nơi gọi xoá id và mồi
        # lại từ transcript, như nhánh Grok.
        if (not text and chan["session_tu_cap"] and self._loi_session(chan, loi_ds)):
            chan2 = _chan_moi()
            chan2["lan_hai"] = True
            args2 = self._build_args(prompt_file=tep, prompt_argv=full, session_id=None)
            manh2: list = []
            loi_ds = []
            async for ra in self._mot_lan(args2, manh2, chan2, xoa_tep=None):
                if ra.get("type") == "error":
                    loi_ds.append(ra)
                    continue
                yield ra
            text = "".join(manh2).strip() or self._vot_chu(chan2)
            chan2["loai"] |= set(chan.get("loai") or ())
            chan = chan2
            sid = None
            print("[muse] `--session-id` bị từ chối, chạy lại không cờ thì được.", file=sys.stderr)
        if tep:
            try:
                os.unlink(tep)
            except Exception:
                pass
        # Id mạch: CLI phát trong dòng sự kiện thì đã gán ở `_doi_su_kien`; không thì giữ id
        # Javis cấp (chỉ khi lượt chạy đã thành công, kẻo lưu một id không tồn tại).
        if text and not self.session_id and sid:
            self.session_id = sid
        for ra in loi_ds:
            yield ra
        if text:
            yield {"type": "final", "content": text, "session_id": self.session_id,
                   "tokens_in": int(chan.get("tokens_in") or 0),
                   "tokens_out": int(chan.get("tokens_out") or 0)}
        elif not loi_ds:
            yield {"type": "error", "content": self._loi_trong(chan)}

    @staticmethod
    def _loi_session(chan: dict, loi_ds: list) -> bool:
        if chan.get("ma_thoat") == 2:
            return True
        tat = " ".join(str(x.get("content") or "") for x in loi_ds) + " " + str(chan.get("stderr") or "")
        return "session" in tat.lower()

    async def _mot_lan(self, args: list, cac_manh: list, chan: dict,
                       xoa_tep: Optional[str] = None) -> AsyncIterator[dict]:
        """Chạy MỘT tiến trình `muse exec` và sinh sự kiện theo hợp đồng chung."""
        tep = xoa_tep
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
                    args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, cwd=self.cwd, text=True, encoding="utf-8",
                    errors="replace", bufsize=1, creationflags=_no_window(),
                    env=_moi_truong(), start_new_session=(os.name != "nt"),
                )
                try:
                    import tien_trinh_nen
                    tien_trinh_nen.ghi_nhom(self.tag, proc.pid)
                except Exception:
                    pass

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
                    _ghi_su_kien_tho(line)
                    if len(chan["raw"]) < _CHAN_DAU_TOI_DA:
                        chan["raw"].append(line[:1000])
                    else:
                        chan["duoi"].append(line[:1000])
                    try:
                        loop.call_soon_threadsafe(hang.put_nowait, json.loads(line))
                    except json.JSONDecodeError:
                        loop.call_soon_threadsafe(hang.put_nowait, {"_raw": line})
                err = ""
                try:
                    err = (proc.stderr.read() or "").strip()
                except Exception:
                    pass
                ma = proc.wait()
                chan["ma_thoat"] = ma
                chan["stderr"] = err[:1000]
                if qua_gio.is_set():
                    loop.call_soon_threadsafe(
                        hang.put_nowait,
                        {"_exit": -1, "_err": f"Muse Code CLI chạy quá {int(self.timeout)}s nên "
                                              f"bị cắt. Nếu việc thật sự dài thì nâng biến môi "
                                              f"trường JAVIS_MUSE_TIMEOUT."})
                elif ma != 0:
                    loop.call_soon_threadsafe(hang.put_nowait, {"_exit": ma, "_err": err})
                elif err:
                    # Thoát 0 mà stderr có chữ KHÔNG phải lỗi (log). Nhưng có thể mang id phiên.
                    loop.call_soon_threadsafe(hang.put_nowait, {"_stderr": err})
                    print(f"[muse stderr] {err[:2000]}", file=sys.stderr)
            except OSError as e:
                if getattr(e, "errno", None) in (errno.E2BIG, errno.ENAMETOOLONG):
                    _t = ("Hội thoại đã quá dài so với trần dòng lệnh của hệ điều hành, mà bản "
                          "Muse Code CLI trên máy này chưa nhận `--prompt-file`. Nâng cấp CLI ("
                          + lenh_cai() + ") hoặc mở một hội thoại mới.")
                    loop.call_soon_threadsafe(hang.put_nowait, {"_exit": -1, "_err": _t})
                else:
                    loop.call_soon_threadsafe(
                        hang.put_nowait, {"_exit": -1, "_err": f"{type(e).__name__}: {e}"})
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
                if tep:
                    try:
                        os.unlink(tep)
                    except Exception:
                        pass
                loop.call_soon_threadsafe(hang.put_nowait, HET)

        threading.Thread(target=doc_luong, name=f"javis-muse-{self.tag}", daemon=True).start()

        while True:
            ev = await hang.get()
            if ev is HET:
                break
            for ra in self._doi_su_kien(ev, cac_manh, chan):
                yield ra

    @staticmethod
    def _vot_chu(chan: dict) -> str:
        san = [x for x in (chan.get("vot") or []) if str(x).strip()]
        if san:
            return "\n".join(san).strip()
        ra = []
        for dong in list(chan.get("raw") or []) + list(chan.get("duoi") or []):
            try:
                d = json.loads(dong)
            except Exception:
                continue
            ra += _vot_tu_su_kien(d)
        return "\n".join(ra).strip()

    @staticmethod
    def _loi_trong(chan: dict) -> str:
        loai = sorted(x for x in (chan.get("loai") or []) if x)
        dong = _chan_dong(chan)
        n = int(chan.get("so_dong") or 0) or len(dong)
        if not n:
            noi = ("Muse Code CLI chạy xong (mã thoát "
                   f"{chan.get('ma_thoat')}) nhưng KHÔNG in ra gì cả")
            if chan.get("lan_hai"):
                noi += ", kể cả khi thử lại không có --session-id"
            noi += (". Thử chạy tay trên máy chủ để xem nó nói gì:\n"
                    "`muse exec --json \"chào\"`")
        else:
            noi = (f"Muse Code CLI in ra {n} dòng nhưng Javis không nhận ra loại sự kiện nào là "
                   "câu trả lời")
            if loai:
                noi += " (thấy: " + ", ".join(loai[:12]) + ")"
            noi += ". Bấm \"Kiểm tra lại\" ở thẻ Muse trên trang Models để xem sự kiện thô."
            if dong:
                noi += "\nDòng đầu: " + dong[0][:250]
            if len(dong) > 1:
                noi += "\nDòng cuối: " + dong[-1][:400]
        if chan.get("stderr"):
            noi += "\nCLI báo ở stderr: " + chan["stderr"][:300]
        if chan.get("args"):
            noi += "\nCờ đã truyền: " + " ".join(chan["args"])
        return noi

    # -- dịch sự kiện -------------------------------------------------------
    @staticmethod
    def _lay(ev: dict, *ten, mac_dinh=""):
        for k in ten:
            v = ev.get(k)
            if v not in (None, ""):
                return v
        return mac_dinh

    def _nhat_sid(self, o) -> None:
        sid = _tim_chuoi(o, ("session_id", "sessionid", "session", "conversation_id", "thread_id"))
        if sid and _UUID_RE.search(sid):
            self.session_id = _UUID_RE.search(sid).group(0)
        elif sid and len(sid) >= 8 and " " not in sid:
            self.session_id = sid

    def _doi_su_kien(self, ev: dict, cac_manh: list, chan: Optional[dict] = None) -> list:
        """Một dòng JSONL của `muse exec --json` -> 0..n sự kiện theo hợp đồng của Javis.

        Ba hình dạng được nhận, xét theo thứ tự:
          (a) MSP: {"method": "item/delta", "params": {...}} hoặc {"type": "item/delta", ...}
          (b) kiểu Claude Code: {"type": "assistant"|"text"|"tool_use"|"tool_result"|"result"}
          (c) chung: dict có text/delta/content chuỗi -> chữ; có tool/name + input|arguments ->
              tool_call; `usage` dict ở đâu cũng được -> usage; session_id ở đâu cũng nhặt.
        Loại lạ thì KHÔNG đưa vào câu trả lời ở đường chính, chỉ để dành ở phần vớt.
        """
        if "_raw" in ev:
            cac_manh.append(str(ev["_raw"]))
            return []
        if "_stderr" in ev:
            # stderr của lượt thành công: có thể in "Session: <uuid>".
            m = re.search(r"session[^\n]{0,40}?(" + _UUID_RE.pattern + ")", str(ev["_stderr"]), re.I)
            if m and not self.session_id:
                self.session_id = m.group(1)
            return []
        if "_exit" in ev:
            loi = str(ev.get("_err") or "").strip()
            if ev.get("_exit") == 0 and not loi:
                return []
            l = loi.lower()
            if ("not authenticated" in l or "unauthorized" in l or "not logged in" in l
                    or "please log in" in l or "please sign in" in l or "meta_api_key" in l):
                return [{"type": "error",
                         "content": "Muse Code CLI chưa đăng nhập. Mở trang Models bấm \"Đăng nhập\", "
                                    "hoặc chạy `muse` trong terminal rồi chọn Sign in with your "
                                    "browser."}]
            if ev.get("_exit") == 2 and not loi:
                loi = "Muse Code CLI thoát mã 2 (sai cú pháp dòng lệnh)."
            if not loi:
                loi = f"Muse Code CLI thoát với mã {ev.get('_exit')}."
            return [{"type": "error", "content": loi[:1500]}]

        t = str(ev.get("type") or ev.get("method") or ev.get("event") or "")
        if chan is not None and t:
            loai = chan.setdefault("loai", set())
            if len(loai) < _CHAN_LOAI_TOI_DA:
                loai.add(t)
        self._nhat_sid(ev)
        ra: list = []
        u = _tim_dict(ev, ("usage", "token_usage", "tokens"))
        if isinstance(u, dict) and any(k in u for k in ("input_tokens", "prompt_tokens", "input",
                                                        "inputTokens", "output_tokens",
                                                        "completion_tokens", "output")):
            ra.append(self._usage(u, chan))

        params = ev.get("params") if isinstance(ev.get("params"), dict) else ev
        item = params.get("item") if isinstance(params.get("item"), dict) else params
        loai_item = str(item.get("type") or item.get("kind") or item.get("item_type")
                        or item.get("role") or "").lower()
        item_id = str(item.get("id") or item.get("item_id") or params.get("item_id") or "")
        tl = t.lower()

        # ---- (a) MSP ----
        if tl in ("item/delta", "delta", "message/delta", "content_block_delta", "text_delta",
                  "assistant_delta", "message_delta", "output_text.delta",
                  "response.output_text.delta"):
            if loai_item in _LOAI_SUY_NGHI:
                return ra
            chu = _chu(params.get("delta")) or _chu(params) or _chu(ev.get("delta"))
            if chu:
                cac_manh.append(chu)
                if chan is not None and item_id:
                    chan.setdefault("delta_ids", set()).add(item_id)
            return ra
        if tl in ("item/started", "item/updated", "item/completed", "item", "item.started",
                  "item.updated", "item.completed"):
            if loai_item in _LOAI_SUY_NGHI:
                return ra
            if loai_item in _LOAI_TOOL_GOI:
                if tl.endswith("started") or tl.endswith("completed") or tl in ("item",):
                    da = chan.setdefault("tool_ids", set()) if chan is not None else set()
                    if item_id and item_id in da and not tl.endswith("completed"):
                        return ra
                    if not (item_id and item_id in da):
                        if item_id:
                            da.add(item_id)
                        ra.append({"type": "tool_call",
                                   "name": str(self._lay(item, "name", "tool_name", "tool",
                                                         "command", "title")),
                                   "id": item_id,
                                   "input": self._lay(item, "input", "arguments", "parameters",
                                                      "args", mac_dinh={})})
                    if tl.endswith("completed"):
                        kq = self._lay(item, "output", "result", "stdout", "content")
                        if kq not in (None, "", {}):
                            ra.append({"type": "tool_result", "id": item_id,
                                       "status": str(self._lay(item, "status", "state")),
                                       "content": (kq if isinstance(kq, str)
                                                   else json.dumps(kq, ensure_ascii=False))[:2000]})
                return ra
            if loai_item in _LOAI_TOOL_KQ:
                if tl.endswith("completed") or tl in ("item",):
                    kq = self._lay(item, "output", "result", "content", "stdout")
                    ra.append({"type": "tool_result", "id": item_id,
                               "status": str(self._lay(item, "status", "state")),
                               "content": (kq if isinstance(kq, str)
                                           else json.dumps(kq, ensure_ascii=False))[:2000]})
                return ra
            # Item CHỮ (message / assistant / text / output_text). Chỉ lấy ở completed, và chỉ
            # khi item này chưa chảy qua delta - kẻo đếm chữ hai lần.
            if tl.endswith("completed") or tl in ("item",):
                if chan is not None and item_id and item_id in chan.get("delta_ids", set()):
                    return ra
                if loai_item and loai_item not in ("message", "assistant", "text", "output_text",
                                                   "agent_message", "assistant_message", "answer"):
                    if chan is not None and len(chan.setdefault("vot", [])) < _CHAN_VOT_TOI_DA:
                        chan["vot"] += _vot_tu_su_kien(item)
                    return ra
                if str(item.get("role") or "").lower() == "user":
                    return ra
                chu = _chu(item.get("content")) or _chu(item.get("text")) or _chu(item)
                da_co = "".join(cac_manh).strip()
                if chu and chu.strip() and chu.strip() != da_co and not da_co.endswith(chu.strip()):
                    cac_manh.append(chu)
            return ra
        if tl in ("turn/completed", "turn.completed", "turn_completed", "end", "done",
                  "response.completed", "complete"):
            if chan is not None and len(chan.setdefault("vot", [])) < _CHAN_VOT_TOI_DA:
                chan["vot"] += _vot_tu_su_kien(params)
            st = str(self._lay(params, "status", "stop_reason", "stopReason", "reason")).lower()
            if st in ("error", "failed", "max_steps", "max_turns"):
                tin = str(self._lay(params, "error", "message"))
                ra.append({"type": "error", "content": tin or f"Muse Code CLI kết thúc sớm ({st})."})
            return ra
        if tl in ("approval/requested", "approval_requested", "approval.requested"):
            ra.append({"type": "error",
                       "content": "Muse Code CLI dừng lại xin duyệt một hành động dù đang chạy "
                                  "headless. Nâng mức quyền của lượt lên Toàn quyền hoặc xem cờ "
                                  "--approval-mode của bản CLI này."})
            return ra

        # ---- (b) kiểu Claude Code ----
        if tl == "assistant":
            msg = ev.get("message") if isinstance(ev.get("message"), dict) else ev
            noi = msg.get("content")
            if isinstance(noi, list):
                for b in noi[:50]:
                    if not isinstance(b, dict):
                        continue
                    bt = str(b.get("type") or "")
                    if bt == "text" and isinstance(b.get("text"), str):
                        cac_manh.append(b["text"])
                    elif bt in ("tool_use", "tool_call"):
                        ra.append({"type": "tool_call", "name": str(b.get("name") or ""),
                                   "id": str(b.get("id") or ""),
                                   "input": b.get("input") or b.get("arguments") or {}})
            elif isinstance(noi, str):
                cac_manh.append(noi)
            return ra
        if tl == "text":
            chu = _chu(ev)
            if chu:
                cac_manh.append(chu)
            return ra
        if tl in ("tool_use", "tool_call", "function_call"):
            ra.append({"type": "tool_call",
                       "name": str(self._lay(ev, "name", "tool_name", "tool")),
                       "id": str(self._lay(ev, "id", "tool_call_id", "toolCallId")),
                       "input": self._lay(ev, "input", "parameters", "arguments", mac_dinh={})})
            return ra
        if tl in ("tool_result", "tool_call_update", "function_call_output"):
            tt = str(self._lay(ev, "status", "state"))
            if tl == "tool_call_update" and tt not in ("completed", "success", "failed", "error"):
                return ra
            kq = self._lay(ev, "output", "result", "content")
            ra.append({"type": "tool_result",
                       "id": str(self._lay(ev, "id", "tool_call_id", "toolCallId")),
                       "status": tt,
                       "content": (kq if isinstance(kq, str)
                                   else json.dumps(kq, ensure_ascii=False))[:2000]})
            return ra
        if tl == "result":
            if chan is not None and len(chan.setdefault("vot", [])) < _CHAN_VOT_TOI_DA:
                chan["vot"] += _vot_tu_su_kien(ev)
            if bool(ev.get("is_error")) or str(ev.get("subtype") or "").startswith("error"):
                tin = str(self._lay(ev, "error", "message", "result"))
                ra.append({"type": "error", "content": tin or "Muse Code CLI lỗi."})
            return ra
        if tl == "usage":
            return ra
        if tl == "error":
            tin = str(self._lay(ev, "message", "error", "content"))
            ra.append({"type": "error", "content": tin or "Muse Code CLI lỗi."})
            return ra
        if tl in _LOAI_SUY_NGHI or tl in _LOAI_KHONG_PHAI_TRA_LOI:
            return ra

        # ---- (c) chung ----
        if ("tool" in ev or "name" in ev) and ("input" in ev or "arguments" in ev):
            ra.append({"type": "tool_call",
                       "name": str(self._lay(ev, "tool", "name")),
                       "id": str(self._lay(ev, "id", "tool_call_id")),
                       "input": self._lay(ev, "input", "arguments", mac_dinh={})})
            return ra
        for k in ("delta", "text", "content"):
            v = ev.get(k)
            if isinstance(v, str) and v:
                cac_manh.append(v)
                return ra
        if chan is not None and len(chan.setdefault("vot", [])) < _CHAN_VOT_TOI_DA:
            chan["vot"] += _vot_tu_su_kien(ev)
        return ra

    @staticmethod
    def _usage(u: dict, chan: Optional[dict] = None) -> dict:
        vao = int(u.get("input_tokens") or u.get("prompt_tokens") or u.get("input")
                  or u.get("inputTokens") or 0)
        ra = int(u.get("output_tokens") or u.get("completion_tokens") or u.get("output")
                 or u.get("outputTokens") or 0)
        cache = int(u.get("cache_read_input_tokens") or u.get("cached_tokens")
                    or u.get("cache_read") or u.get("cacheRead") or u.get("cached") or 0)
        if chan is not None:
            chan["tokens_in"] = vao
            chan["tokens_out"] = ra
        return {"type": "usage", "input_tokens": vao, "output_tokens": ra,
                "total_tokens": int(u.get("total_tokens") or u.get("total") or (vao + ra)),
                "cached": cache}


# ---------------------------------------------------------------------------
def kiem_tra_nhanh(timeout: float = 45.0) -> dict:
    """Chạy thử MỘT lượt `muse exec --json` cực ngắn để biết CLI + đăng nhập có THẬT SỰ dùng
    được không, và trả kèm `su_kien_tho` để chủ repo dán lại khi sơ đồ sự kiện lệch."""
    cli = find_muse_cli()
    if not cli:
        return {"ok": False, "error": f"Chưa cài Muse Code CLI ({lenh_cai()})."}
    m = MuseCLI(cwd=str(Path.home()), tag="check", mode="suggest")
    m.timeout = timeout
    m.max_turns = 1
    args = m._build_args(prompt_argv="Trả lời đúng một chữ: ok", session_id=None)
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, creationflags=_no_window(),
                           env=_moi_truong(), cwd=str(Path.home()), stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Muse Code CLI không trả lời kịp."}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    tho = (r.stdout or "").strip()
    for dong in tho.splitlines()[-_SU_KIEN_THO_TOI_DA:]:
        if dong.strip():
            _ghi_su_kien_tho(dong.strip())
    if r.returncode != 0:
        loi = (r.stderr or r.stdout or "").strip()
        l = loi.lower()
        if ("not authenticated" in l or "unauthorized" in l or "not logged in" in l
                or "sign in" in l or "log in" in l):
            loi = ("Chưa đăng nhập. Bấm \"Đăng nhập\" trên thẻ này, hoặc chạy `muse` trong "
                   "terminal rồi chọn Sign in with your browser.")
        elif "subscription" in l or "not eligible" in l or "forbidden" in l or "plan" in l:
            loi = ("Tài khoản đăng nhập không có quyền dùng Muse Code. Nó đi kèm gói Everyday / "
                   "High / Power / Maximum của Meta, hoặc META_API_KEY trả theo lượng dùng.")
        return {"ok": False, "error": loi[:400] or f"Thoát mã {r.returncode}",
                "su_kien_tho": su_kien_tho()}
    chan = _chan_moi()
    manh: list = []
    for dong in tho.splitlines():
        dong = dong.strip()
        if not dong:
            continue
        chan["so_dong"] += 1
        chan["raw"].append(dong[:1000])
        try:
            ev = json.loads(dong)
        except json.JSONDecodeError:
            ev = {"_raw": dong}
        if isinstance(ev, dict):
            m._doi_su_kien(ev, manh, chan)
    tra = "".join(manh).strip() or MuseCLI._vot_chu(chan)
    if tra:
        return {"ok": True, "reply": tra[:200], "su_kien_tho": su_kien_tho()}
    if not tho:
        return {"ok": False, "su_kien_tho": su_kien_tho(),
                "error": ("Muse Code CLI thoát 0 nhưng không in ra gì cả. Thử chạy tay trên máy "
                          "chủ: `muse exec --json \"chào\"`")}
    return {"ok": False, "su_kien_tho": su_kien_tho(),
            "error": ("Muse Code CLI chạy xong nhưng Javis không đọc ra câu trả lời trong thứ "
                      "nó in ra (thấy: " + ", ".join(sorted(chan["loai"])[:10]) + "). Nguyên văn: "
                      + tho[:300])}
