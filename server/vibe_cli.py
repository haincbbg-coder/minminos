"""Bộ não Mistral Vibe CLI (binary `vibe`, gói PyPI `mistral-vibe`), chạy bằng gói Le Chat Pro /
Team của Mistral hoặc API key Mistral riêng.

**ĐÃ ĐO TRÊN BINARY THẬT (mistral-vibe 3.0.2, 24/10/2026)** - cài bằng pip vào venv nháp, chạy
headless với một máy chủ OpenAI-compat GIẢ (khai qua `[[providers]]` trong config.toml) và một
MCP server giả (FastMCP streamable-http). Không có tài khoản Mistral nên phần nói chuyện với
máy chủ Mistral thật là phần duy nhất chưa đo.

- `vibe` là vỏ Python exec sang binary Rust `vibe-rs` (bundled trong wheel, ~160MB).
- Headless: `vibe -p TEXT` hoặc `--prompt-file PATH`; `--output text|json|streaming`.
  `streaming` = NDJSON, MỖI DÒNG LÀ MỘT MỤC HOÀN CHỈNH (không phải từng mảnh chữ):
      {"type":"message","role":"user",...,"sessionId":"..."}
      {"type":"effect","title":"file_system.bash","detail":{"toolName":"file_system.bash",
       "input":{"command":"..."}},"state":{"status":"completed"|"failed",...}}
      {"type":"message","role":"assistant","content":[{"type":"text","text":"..."}],
       "outcome":{"type":"committed"}}
  Có cả loại `callback` (hỏi duyệt) - không phải câu trả lời.
- Mã thoát: 0 xong; 1 lỗi cấu hình/đăng nhập ("Error: Missing MISTRAL_API_KEY environment
  variable for mistral provider", "Error: Invalid API key (from env var ...)"); 2 lỗi hạ tầng
  (máy chủ model); 3 dừng vì giới hạn. Lỗi in ra stderr, dạng "Error: ...".
- `--output-dir DIR` ghi `DIR/export.json`: outcome, session_id, usage {input_tokens,
  output_tokens, cached_input_tokens, total_tokens}, cost_usd. Đây là chỗ DUY NHẤT có token.
- Model: KHÔNG có cờ `--model`. Đổi bằng biến `VIBE_ACTIVE_MODEL=<alias>` (đo: đổi alias là
  request đi sang đúng model khác). Alias dựng sẵn: `mistral-medium-3.5`.
- Quyền (đo bằng một lệnh `touch` thật): mặc định `accept-edits` và `--agent ask` đều TỪ CHỐI
  lệnh máy ở headless ("Tool execution denied by approval callback"); `--auto-approve` chạy hết.
  `--disabled-tools bash` thì KHÔNG chặn được (bash vẫn chạy ở bản 3.0.2) - nên không dùng.
- MCP: `[[mcp_servers]]` trong `<brain>/.vibe/config.toml` (tầng project, chỉ nạp khi thư mục
  được tin - truyền `--trust`), `transport = "streamable-http"`, `url`, `headers = {...}`.
  Đo: header `Authorization` + `X-Javis-Mode` tới đúng hub; tool hub hiện thành nhóm
  `mcp_javis`, model gọi qua `search_tool_functions` + `run_typescript` (gọi thẳng tên
  `javis_xxx` bị từ chối "unsupported top-level tool").
- Đăng nhập: khoá cất ở biến `MISTRAL_API_KEY`, file `~/.vibe/.env` (VIBE_HOME), hoặc keyring.
  "Đăng nhập bằng trình duyệt" của Mistral thực chất TẠO một API key trong tài khoản rồi cất
  vào đó. Luồng chạy được trên VPS là `vibe-acp` (Agent Client Protocol qua stdio) với cách
  `browser-auth-delegated`: `authenticate` start trả `signInUrl` (KHÔNG mở trình duyệt), rồi
  `authenticate` complete tự hỏi máy chủ tới khi người dùng đăng nhập xong. Đo trọn vòng với
  cổng đăng nhập giả (POST /api/vibe/sign-in, GET poll, POST .../exchange): khoá vào
  `~/.vibe/.env` (ép keyring hỏng bằng PYTHON_KEYRING_BACKEND để chắc chắn vào file).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

import cli_nao_chung as chung
from claude_cli import _home_dir, _no_window

try:
    import tomllib
except ModuleNotFoundError:   # pragma: no cover
    tomllib = None            # type: ignore[assignment]

ID = "vibe-cli"
TEN = "Mistral Vibe CLI"
KHOA_ENV = "MISTRAL_API_KEY"
MODELS_DU_PHONG = ["mistral-medium-3.5"]
LENH_CAI = "uv tool install mistral-vibe"
LENH_CAI_CURL = "curl -LsSf https://mistral.ai/vibe/install.sh | bash"

_LUAT_QUYEN = {
    "suggest": ["--agent", "ask"],          # hỏi duyệt mọi thứ -> headless từ chối hết
    "auto": ["--agent", "accept-edits"],    # sửa file được, lệnh máy bị từ chối
    "full": ["--auto-approve"],
}


def vibe_home() -> Path:
    env = (os.environ.get("VIBE_HOME") or "").strip()
    return Path(env).expanduser() if env else _home_dir() / ".vibe"


def _file_env() -> Path:
    return vibe_home() / ".env"


def _co_acp_canh(p: str) -> bool:
    """Chỉ nhận `vibe` có `vibe-acp` nằm cạnh: tên `vibe` quá chung để tin PATH mù."""
    try:
        d = Path(p).resolve().parent
        return any((d / n).exists() for n in ("vibe-acp", "vibe-acp.exe")) or \
            any((Path(p).parent / n).exists() for n in ("vibe-acp", "vibe-acp.exe"))
    except Exception:
        return False


def find_vibe_cli() -> Optional[str]:
    return chung.tim("JAVIS_VIBE_BIN", ("vibe",),
                     (".local/share/uv/tools/mistral-vibe/bin/vibe",
                      ".local/share/minmin-vibe/venv/bin/vibe"),
                     loc=_co_acp_canh)


def find_vibe_acp() -> Optional[str]:
    v = find_vibe_cli()
    if not v:
        return None
    for n in ("vibe-acp", "vibe-acp.exe"):
        for d in (Path(v).parent, Path(v).resolve().parent):
            if (d / n).exists():
                return str(d / n)
    return shutil.which("vibe-acp")


find_cli = find_vibe_cli   # tên chung cho main.py / aux_engine


def lenh_cai() -> str:
    return LENH_CAI


def _moi_truong(model: Optional[str] = None) -> dict:
    e = dict(os.environ)
    # Đặt qua tiền tố VIBE_ (tài liệu dựng sẵn trong gói: mọi khoá config ghi đè được bằng
    # VIBE_<TÊN>). Kiểm tra cập nhật hằng ngày sẽ HỎI người dùng lúc khởi động - headless trên
    # VPS không có ai trả lời.
    e.setdefault("VIBE_ENABLE_UPDATE_CHECKS", "false")
    if model:
        e["VIBE_ACTIVE_MODEL"] = str(model)   # ĐO: đây là cách duy nhất đổi model headless
    return e


# ---------------------------------------------------------------------------
# Đăng nhập: đọc file, không đẻ tiến trình
# ---------------------------------------------------------------------------
def auth_status() -> dict:
    cli = find_vibe_cli()
    if not cli:
        return {"connected": False, "method": "", "account": "", "plan": "",
                "error": "Chưa cài Mistral Vibe CLI. Bấm \"Cài đặt\" trên thẻ này."}
    if (os.environ.get(KHOA_ENV) or "").strip():
        return {"connected": True, "method": "env", "account": "", "plan": "",
                "error": "", "duoi_khoa": chung.duoi_khoa(os.environ.get(KHOA_ENV, ""))}
    v = chung.doc_env(_file_env()).get(KHOA_ENV, "")
    if v:
        return {"connected": True, "method": "vibe_home_env_file", "account": "", "plan": "",
                "error": "", "duoi_khoa": chung.duoi_khoa(v)}
    return {"connected": False, "method": "", "account": "", "plan": "",
            "error": ("Đã cài Mistral Vibe nhưng chưa có khoá. Bấm \"Đăng nhập\" (tài khoản Mistral) "
                      "hoặc dán API key Mistral ngay trên thẻ này.")}


def dat_api_key(khoa: str) -> dict:
    """Ghi khoá vào `~/.vibe/.env` - đúng chỗ và đúng dạng chính `vibe` ghi khi đăng nhập
    (đo: `persist_api_key` rơi về file này khi không có keyring). MinMin không giữ bản nào."""
    khoa = (khoa or "").strip()
    if len(khoa) < 16 or any(c.isspace() for c in khoa):
        return {"ok": False, "error": "Khoá không hợp lệ (quá ngắn hoặc có khoảng trắng)."}
    if not chung.ghi_env(_file_env(), KHOA_ENV, khoa):
        return {"ok": False, "error": f"Không ghi được {_file_env()}."}
    return {"ok": True}


def logout() -> dict:
    """Gỡ khoá khỏi `~/.vibe/.env` - đúng việc `_auth/signOut` của vibe-acp làm (đã đo)."""
    huy_dang_nhap()
    if not find_vibe_cli():
        return {"ok": False, "error": "Chưa cài Mistral Vibe CLI."}
    chung.ghi_env(_file_env(), KHOA_ENV, None)
    if (os.environ.get(KHOA_ENV) or "").strip():
        return {"ok": False, "error": ("Khoá còn nằm ở biến môi trường MISTRAL_API_KEY của máy chủ "
                                       "(docker-compose / .env) - MinMin không gỡ được chỗ đó.")}
    return {"ok": True}


def login_huong_dan() -> dict:
    return {"cai": lenh_cai(), "dang_nhap": "vibe --setup",
            "ghi_chu": ("Đăng nhập Mistral tạo một API key trong tài khoản của bạn rồi cất vào "
                        "~/.vibe/.env. Có sẵn API key thì dán thẳng vào thẻ cũng được.")}


# ---------------------------------------------------------------------------
# Đăng nhập trình duyệt qua vibe-acp (browser-auth-delegated) - chạy được trên VPS
# ---------------------------------------------------------------------------
class _PhienAcp:
    def __init__(self):
        self.proc = None
        self.tra: dict = {}
        self.cho: dict = {}
        self.url = ""
        self.attempt = ""
        self.het_han = 0.0
        self.loi = ""
        self.xong = False
        self.log = chung.NhatKy()

    def start(self, acp: str) -> None:
        env = dict(_moi_truong())
        # Ép keyring hỏng: khoá rơi vào ~/.vibe/.env (đã đo) - file mà MinMin đọc được trạng
        # thái, và nằm trên volume /data nên sống qua cập nhật Docker. Keyring của một
        # container không có phiên đăng nhập hệ điều hành thì hoặc không có, hoặc mất khi
        # dựng lại container.
        env["PYTHON_KEYRING_BACKEND"] = "keyring.backends.fail.Keyring"
        self.proc = subprocess.Popen([acp], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                     errors="replace", bufsize=1, env=env,
                                     cwd=str(_home_dir()), creationflags=_no_window(),
                                     start_new_session=(os.name != "nt"))
        threading.Thread(target=self._doc, daemon=True, name="minmin-vibe-acp").start()

    def _doc(self):
        try:
            for l in iter(self.proc.stdout.readline, ""):
                try:
                    d = json.loads(l)
                except Exception:
                    continue
                i = d.get("id")
                if i in self.cho:
                    self.tra[i] = d
                    self.cho[i].set()
        except Exception:
            pass

    def goi(self, i: int, method: str, params: dict, timeout: float) -> dict:
        ev = threading.Event()
        self.cho[i] = ev
        try:
            self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": i, "method": method,
                                              "params": params}) + "\n")
            self.proc.stdin.flush()
        except Exception as e:
            return {"error": {"message": f"{type(e).__name__}: {e}"}}
        if not ev.wait(timeout):
            return {"error": {"message": f"vibe-acp không trả lời {method} trong {int(timeout)}s"}}
        return self.tra.get(i) or {}

    def dang_chay(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def huy(self):
        p = self.proc
        if p and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass


_PHIEN: dict = {"p": None}


def huy_dang_nhap() -> None:
    p = _PHIEN.get("p")
    if p:
        p.huy()
    _PHIEN["p"] = None


def _meta(d: dict) -> dict:
    return (((d or {}).get("result") or {}).get("_meta") or {}).get("browser-auth-delegated") or {}


def login_start(cho_giay: float = 40.0) -> dict:
    """Mở vibe-acp, xin link đăng nhập Mistral (KHÔNG mở trình duyệt trên máy chủ)."""
    acp = find_vibe_acp()
    if not acp:
        return {"ok": False, "can_cai": True,
                "error": "Chưa cài Mistral Vibe CLI (thiếu `vibe-acp`). Bấm Cài đặt trước."}
    if auth_status().get("connected"):
        return {"ok": True, "xong": True, "url": ""}
    huy_dang_nhap()
    p = _PhienAcp()
    try:
        p.start(acp)
    except Exception as e:
        return {"ok": False, "error": f"Không chạy được vibe-acp: {type(e).__name__}: {e}"}
    _PHIEN["p"] = p
    p.log.ghi("[MinMin chạy] vibe-acp (đăng nhập trình duyệt, kiểu delegated)")
    r = p.goi(1, "initialize", {"protocolVersion": 1, "clientInfo": {"name": "minmin", "version": "1"},
                                "clientCapabilities": {"_meta": {"browser-auth-delegated": True}}},
              cho_giay)
    if r.get("error"):
        p.huy()
        return {"ok": False, "error": "vibe-acp lỗi khi khởi động: "
                + str(r["error"].get("message") or r["error"])[:300], "nhat_ky": p.log.ds()}
    cach = [m.get("id") for m in ((r.get("result") or {}).get("authMethods") or [])]
    if "browser-auth-delegated" not in cach:
        p.huy()
        return {"ok": False, "error": ("Bản Mistral Vibe trên máy chưa có đăng nhập trình duyệt từ xa. "
                                       "Dán API key Mistral vào thẻ này thay thế."),
                "nhat_ky": p.log.ds()}
    r = p.goi(2, "authenticate", {"methodId": "browser-auth-delegated",
                                  "_meta": {"action": "start"}}, cho_giay)
    m = _meta(r)
    if r.get("error") or not m.get("signInUrl"):
        p.huy()
        loi = str(((r.get("error") or {}).get("message")) or "không nhận được link")
        return {"ok": False, "error": "Mistral không mở được phiên đăng nhập: " + loi[:300],
                "nhat_ky": p.log.ds()}
    p.url, p.attempt = str(m["signInUrl"]), str(m.get("attemptId") or "")
    p.log.ghi("Link đăng nhập: " + p.url)
    try:
        from datetime import datetime
        p.het_han = datetime.fromisoformat(str(m.get("expiresAt")).replace("Z", "+00:00")).timestamp()
    except Exception:
        p.het_han = time.time() + 600

    def _hoan_tat():
        cho = max(30.0, p.het_han - time.time() + 30)
        d = p.goi(3, "authenticate", {"methodId": "browser-auth-delegated",
                                      "_meta": {"action": "complete", "attemptId": p.attempt}}, cho)
        if d.get("error"):
            p.loi = str(d["error"].get("message") or d["error"])[:300]
            p.log.ghi("[Mistral] " + p.loi)
        else:
            p.xong = str(_meta(d).get("status") or "") == "completed"
            p.log.ghi("[Mistral] đăng nhập xong, khoá đã cất vào ~/.vibe/.env" if p.xong
                      else "[Mistral] phản hồi lạ: " + json.dumps(d)[:200])
        p.huy()

    threading.Thread(target=_hoan_tat, daemon=True, name="minmin-vibe-login").start()
    return {"ok": True, "xong": False, "url": p.url, "code": "", "nhat_ky": p.log.ds()}


def login_trang_thai() -> dict:
    p = _PHIEN.get("p")
    d = auth_status()
    dang = bool(p and p.dang_chay() and not p.xong and not p.loi)
    loi = ""
    if not d.get("connected") and not dang:
        loi = (p.loi if p and p.loi else d.get("error") or "Đăng nhập chưa xong.")
    return {"connected": bool(d.get("connected")), "dang_cho": dang,
            "url": p.url if p else "", "code": "", "nhat_ky": p.log.ds() if p else [],
            "error": loi}


# ---------------------------------------------------------------------------
# Cài đặt
# ---------------------------------------------------------------------------
_CAI = chung.TrinhCai("vibe", find_vibe_cli)


def cai_dat_start() -> dict:
    """uv có sẵn -> `uv tool install mistral-vibe` (lệnh chính chủ). Không có uv (ảnh Docker
    python-slim) -> venv riêng + pip, đúng gói PyPI chính chủ - đường này ĐÃ ĐO cài được."""
    home = _home_dir()
    uv = shutil.which("uv") or (str(home / ".local/bin/uv") if (home / ".local/bin/uv").exists() else None)
    if uv:
        return _CAI.start([[uv, "tool", "install", "--upgrade", "mistral-vibe"]])
    venv = home / ".local/share/minmin-vibe/venv"
    py = sys.executable or "python3"
    if os.name == "nt":
        return _CAI.start([[py, "-m", "pip", "install", "--user", "--upgrade", "mistral-vibe"]])
    bin_ = home / ".local/bin"
    return _CAI.start([
        [py, "-m", "venv", str(venv)],
        [str(venv / "bin/python"), "-m", "pip", "install", "--upgrade", "mistral-vibe"],
        ["sh", "-c", f'mkdir -p "{bin_}" && ln -sf "{venv}/bin/vibe" "{bin_}/vibe" '
                     f'&& ln -sf "{venv}/bin/vibe-acp" "{bin_}/vibe-acp"'],
    ])


def cai_dat_trang_thai() -> dict:
    return _CAI.trang_thai()


# ---------------------------------------------------------------------------
# MCP: `[[mcp_servers]]` trong `<brain>/.vibe/config.toml`
# ---------------------------------------------------------------------------
def hub_entry(url: str, headers: Optional[dict] = None) -> dict:
    e = {"name": "javis", "transport": "streamable-http", "url": url}
    if headers:
        e["headers"] = dict(headers)
    return e


def mcp_config_path(vault_root) -> Path:
    return Path(vault_root).expanduser() / ".vibe" / "config.toml"


def _tv(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return json.dumps(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_tv(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{_tk(k)} = {_tv(x)}" for k, x in v.items()) + " }"
    return json.dumps(str(v), ensure_ascii=False)


def _tk(k) -> str:
    k = str(k)
    if k and all(c.isascii() and (c.isalnum() or c in "_-") for c in k):
        return k
    return json.dumps(k, ensure_ascii=False)


def _toml_dump(d: dict) -> str:
    """TOML đủ cho config của Vibe: khoá phẳng, bảng một tầng, mảng bảng `[[...]]`. Giá trị lồng
    sâu hơn viết thành inline table. Mất chú thích trong file - chấp nhận được vì file nằm trong
    `<brain>/.vibe/`, thư mục MinMin dựng (giống `<brain>/.grok/` của Grok)."""
    dong, bang, mang = [], [], []
    for k, v in d.items():
        if isinstance(v, dict):
            bang.append((k, v))
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            mang.append((k, v))
        else:
            dong.append(f"{_tk(k)} = {_tv(v)}")
    ra = "\n".join(dong) + ("\n" if dong else "")
    for k, v in bang:
        ra += f"\n[{_tk(k)}]\n" + "".join(f"{_tk(a)} = {_tv(b)}\n" for a, b in v.items())
    for k, ds in mang:
        for x in ds:
            ra += f"\n[[{_tk(k)}]]\n" + "".join(f"{_tk(a)} = {_tv(b)}\n" for a, b in x.items())
    return ra.lstrip("\n")


def _doc_toml_ky(p: Path) -> tuple:
    try:
        if not p.exists():
            return True, {}
        if tomllib is None:
            return False, {}
        with open(p, "rb") as f:
            d = tomllib.load(f)
        return True, (d if isinstance(d, dict) else {})
    except Exception as e:
        print(f"[vibe mcp] `{p}` không đọc được, KHÔNG ghi đè: {e}", file=sys.stderr)
        return False, {}


def ghi_mcp_settings(vault_root, hub: Optional[dict]) -> Optional[str]:
    try:
        p = mcp_config_path(vault_root)
        ok, cu = _doc_toml_ky(p)
        if not ok:
            return None
        ds = [x for x in (cu.get("mcp_servers") or []) if isinstance(x, dict)
              and x.get("name") != "javis"]
        if hub:
            ds.append(dict(hub))
        if ds:
            cu["mcp_servers"] = ds
        else:
            cu.pop("mcp_servers", None)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_toml_dump(cu), encoding="utf-8")
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass
        return str(p)
    except Exception as e:
        print(f"[vibe mcp] {e}", file=sys.stderr)
        return None


def trang_thai_mcp(vault_root) -> dict:
    p = mcp_config_path(vault_root)
    ra = {"file": str(p), "ton_tai": p.exists(), "co_javis": False, "url": "", "so_header": 0}
    if not ra["ton_tai"]:
        return ra
    ok, d = _doc_toml_ky(p)
    for x in (d.get("mcp_servers") or []) if ok else []:
        if isinstance(x, dict) and x.get("name") == "javis":
            ra["co_javis"] = True
            ra["url"] = str(x.get("url") or "")
            h = x.get("headers")
            ra["so_header"] = len(h) if isinstance(h, dict) else 0
    return ra


# ---------------------------------------------------------------------------
def list_models() -> Optional[list]:
    """Alias dựng sẵn + alias người dùng khai `[[models]]` trong ~/.vibe/config.toml."""
    if not find_vibe_cli():
        return None
    ids = list(MODELS_DU_PHONG)
    ok, d = _doc_toml_ky(vibe_home() / "config.toml")
    for m in (d.get("models") or []) if ok else []:
        a = str((m or {}).get("alias") or (m or {}).get("name") or "").strip()
        if a and a not in ids:
            ids.append(a)
    act = str((d.get("active_model") or "") if ok else "").strip()
    if act and act not in ids:
        ids.insert(0, act)
    return ids


def co_effort(muc) -> list:
    return []      # Vibe đặt mức nghĩ theo model trong config.toml, không có cờ dòng lệnh


def chan_doan() -> dict:
    h = vibe_home()
    files = []
    try:
        files = [{"ten": f.name, "bytes": f.stat().st_size if f.is_file() else -1}
                 for f in sorted(h.iterdir())[:40]]
    except Exception:
        pass
    p = _PHIEN.get("p")
    return {"cli_path": find_vibe_cli() or "", "acp_path": find_vibe_acp() or "",
            "home": str(h), "home_ton_tai": h.is_dir(), "files": files,
            "co_token": bool(chung.doc_env(_file_env()).get(KHOA_ENV)),
            "env_bien": bool((os.environ.get(KHOA_ENV) or "").strip()),
            "nhat_ky": p.log.ds() if p else []}


# ---------------------------------------------------------------------------
class VibeCLI(chung.NaoCLIGoc):
    ID = ID
    TEN = TEN
    ENV_TIMEOUT = "JAVIS_VIBE_TIMEOUT"
    STDERR_ON = r"^Reading API keys from the system keyring"   # đo: bản 3.0.2 lượt nào cũng in
    HELP = chung.HelpCache()

    @staticmethod
    def tim_cli():
        return find_vibe_cli()

    @staticmethod
    def lenh_cai():
        return LENH_CAI

    def _co(self, *c) -> bool:
        return self.HELP.co(self.cli_path, (), *c, env=_moi_truong())

    def _chuan_bi(self, full: str) -> tuple:
        args = [self.cli_path]
        tep = chung.tep_tam(full, "minmin-vibe-")
        if tep and self._co("--prompt-file"):
            args += ["--prompt-file", tep]
        else:
            args += ["-p", full]
        args += ["--output", "streaming"] if self._co("--output") else []
        if self._co("--trust"):
            args.append("--trust")       # cần để Vibe nạp `<brain>/.vibe/config.toml` (hub MCP)
        m = str(self.mode or "").strip().lower()
        args += _LUAT_QUYEN.get(m, _LUAT_QUYEN["suggest"])   # mode lạ -> nấc chặt nhất
        if self.max_turns and self._co("--max-turns"):
            args += ["--max-turns", str(int(self.max_turns))]
        if self.session_id and self._co("--resume"):
            args += ["--resume", self.session_id]
        self._out_dir = None
        if self._co("--output-dir"):
            self._out_dir = tempfile.mkdtemp(prefix="minmin-vibe-out-")
            args += ["--output-dir", self._out_dir]
        args += list(self.extra_args)
        return args, None, _moi_truong(self.model), [tep] if tep else []

    def _doi_su_kien(self, ev: dict, gom: dict) -> list:
        sid = str(ev.get("sessionId") or ev.get("session_id") or "").strip()
        if sid:
            self.session_id = sid
        t = str(ev.get("type") or "")
        if t == "message":
            if str(ev.get("role") or "") != "assistant":
                return []
            chu = "".join(str(c.get("text") or "") for c in (ev.get("content") or [])
                          if isinstance(c, dict) and c.get("type") == "text").strip()
            if chu:
                # Mỗi dòng là MỘT tin hoàn chỉnh; tin trợ lý CUỐI là câu trả lời (tin trước đó
                # là lời dẫn trước khi gọi tool). Vẫn giữ các tin trước ở `vot` làm lưới.
                if gom.get("final"):
                    gom["vot"].append(gom["final"])
                gom["final"] = chu
            return []
        if t == "effect":
            d = ev.get("detail") or {}
            ten = str(d.get("toolName") or ev.get("title") or "tool")
            eid = str(ev.get("id") or "")
            da = gom.setdefault("da_bao_tool", set())
            if eid and eid in da:
                return []
            da.add(eid)
            st = ev.get("state") or {}
            ra = [{"type": "tool_call", "name": ten, "id": eid, "input": d.get("input") or {}}]
            if str(st.get("status") or "") in ("completed", "failed"):
                ra.append({"type": "tool_result", "id": eid, "status": st.get("status"),
                           "content": str(st.get("outputText") or "")[:2000]})
            return ra
        if t in ("error",):
            return [{"type": "error", "content": "Mistral Vibe: " + str(
                chung.lay(ev, "message", "error", "content") or "lỗi không rõ")[:1500]}]
        return []

    def _sau_luot(self, gom: dict) -> list:
        d = getattr(self, "_out_dir", None)
        if not d:
            return []
        ra = []
        try:
            p = Path(d) / "export.json"
            if p.exists():
                x = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(x.get("usage"), dict):
                    ra.append(chung.doc_usage(x["usage"]))
                if x.get("session_id"):
                    self.session_id = str(x["session_id"])
                oc = str(x.get("outcome") or "")
                if oc in ("turn_limit", "token_limit", "price_limit", "deadline", "length") \
                        and not gom.get("final"):
                    ra.append({"type": "error",
                               "content": f"Mistral Vibe dừng giữa chừng vì chạm giới hạn ({oc})."})
        except Exception as e:
            print(f"[vibe export] {e}", file=sys.stderr)
        finally:
            shutil.rmtree(d, ignore_errors=True)
            self._out_dir = None
        return ra

    def _cau_chua_dang_nhap(self, loi: str) -> str:
        l = (loi or "").lower()
        if "missing mistral_api_key" in l or ("missing" in l and "api_key" in l and "environment" in l):
            return ("Mistral Vibe chưa đăng nhập. Mở trang Models, bấm \"Đăng nhập\" ở thẻ Mistral "
                    "Vibe (hoặc dán API key Mistral).")
        if "invalid api key" in l or "401" in l and "unauthorized" in l:
            return ("Khoá Mistral không còn hợp lệ (đã bị thu hồi hoặc hết hạn). Đăng nhập lại ở thẻ "
                    "Mistral Vibe trên trang Models.")
        return ""


def kiem_tra_nhanh(timeout: float = 90.0) -> dict:
    if not find_vibe_cli():
        return {"ok": False, "error": "Chưa cài Mistral Vibe CLI."}
    return chung.kiem_tra_bang_luot(VibeCLI, timeout)
