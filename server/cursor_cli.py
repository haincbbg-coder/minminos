"""Bộ não Cursor CLI (binary `agent`, tên cũ `cursor-agent`), chạy bằng gói Cursor sẵn có.

**CHƯA ĐO TRÊN BINARY THẬT.** Lệnh cài chính chủ `curl https://cursor.com/install -fsS | bash`
tải từ cursor.com - domain bị chặn trong máy dựng bản này. Gói npm `cursor-agent` 1.0.3 KHÔNG
phải của Anysphere (người đăng `zalab-inc`, mô tả "Task sequence creator", repo
github.com/zalab-inc/cursor_agent) nên KHÔNG dùng để cài và không đo trên nó.

Mọi thứ dưới đây đọc từ tài liệu chính chủ cursor.com/docs/cli (đọc 24/10/2026):
- Cờ toàn cục: `-p/--print`, `--output-format text|json|stream-json`, `--stream-partial-output`,
  `--resume [chatId]`, `--model`, `--mode` (agent|plan|ask), `-f/--force` (cho phép sửa file
  khi chạy headless), `--approve-mcps`, `--trust`, `--workspace`, `--api-key`, `--list-models`.
- Lệnh con: `login` (mở trình duyệt; `NO_OPEN_BROWSER=1` thì chỉ in link), `logout`,
  `status`/`whoami`, `models`, `mcp list|login|enable|disable`.
- stream-json: `system/init` (session_id, model), `user`, `assistant` (message.content[].text),
  `tool_call` started/completed (tool_call.readToolCall / writeToolCall / function), và
  `result` cuối (`result` = toàn văn câu trả lời, `session_id`, `is_error`).
- MCP: `.cursor/mcp.json` của project (thư mục làm việc) hoặc `~/.cursor/mcp.json`; entry HTTP
  là `{"url": ..., "headers": {...}}`, không có khoá `type`.
- `CURSOR_API_KEY` cho chạy tự động (khoá tạo ở Cursor Dashboard, tính vào gói Cursor).

Đăng nhập trên VPS: tài liệu chỉ nói `NO_OPEN_BROWSER=1` in link. Diễn đàn Cursor có người mở
link đó ở máy khác "có vẻ thành công" rồi chỉ hỏng ở bước cất token vào Keychain macOS - tức
CLI tự hỏi máy chủ chứ không đợi cổng localhost. CHƯA ĐO trên Linux, nên nút Đăng nhập là ĐƯỜNG
THỬ; đường chắc chắn là dán `CURSOR_API_KEY`. Cửa thoát: JAVIS_CURSOR_BIN, JAVIS_CURSOR_TIMEOUT.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

import cli_nao_chung as chung
from claude_cli import _home_dir

ID = "cursor-cli"
TEN = "Cursor CLI"
KHOA_ENV = "CURSOR_API_KEY"
MODELS_DU_PHONG = ["auto"]
LENH_CAI = "curl https://cursor.com/install -fsS | bash"
LENH_CAI_WIN = "irm 'https://cursor.com/install?win32=true' | iex"
# Prompt dài hơn ngần này byte thì không nhét vào argv (Linux cắt MỘT tham số ở 128 KiB).
_TRAN_ARGV = 100_000
HELP = chung.HelpCache()


def _la_cursor(p: str) -> bool:
    """`agent` là tên quá chung: chỉ nhận khi đường thật trỏ vào bản cài của Cursor."""
    try:
        if Path(p).name.startswith("cursor-agent"):
            return True
        return "cursor" in str(Path(p).resolve()).lower()
    except Exception:
        return False


def find_cursor_cli() -> Optional[str]:
    return chung.tim("JAVIS_CURSOR_BIN", ("cursor-agent", "agent"), (), loc=_la_cursor)


find_cli = find_cursor_cli   # tên chung cho main.py / aux_engine


def lenh_cai() -> str:
    return LENH_CAI_WIN if os.name == "nt" else LENH_CAI


def _file_khoa() -> Path:
    # Nằm trong ~/.cursor - thư mục được docker/entrypoint.sh đưa lên volume /data.
    return _home_dir() / ".cursor" / "minmin-api-key.env"


def _khoa() -> str:
    return ((os.environ.get(KHOA_ENV) or "").strip()
            or chung.doc_env(_file_khoa()).get(KHOA_ENV, ""))


def _moi_truong() -> dict:
    e = dict(os.environ)
    k = _khoa()
    if k:
        e[KHOA_ENV] = k      # qua biến môi trường, KHÔNG qua `--api-key` (lộ trong `ps`)
    e.setdefault("NO_OPEN_BROWSER", "1")
    return e


def _co(*c) -> bool:
    return HELP.co(find_cursor_cli(), (), *c, env=_moi_truong())


# ---------------------------------------------------------------------------
# Đăng nhập
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _hoi_status() -> dict:
    cli = find_cursor_cli()
    if not cli:
        return {"connected": False, "error": "Chưa cài Cursor CLI."}
    ma, out, err = chung.chay([cli, "status"], timeout=25, env=_moi_truong())
    txt = chung.lam_sach(out + "\n" + err)
    l = txt.lower()
    if "not logged in" in l or "not authenticated" in l or "logged out" in l:
        return {"connected": False, "error": "Đã cài Cursor CLI nhưng chưa đăng nhập."}
    if ma == 0 and ("logged in" in l or "authenticated" in l or _EMAIL_RE.search(txt)):
        m = _EMAIL_RE.search(txt)
        return {"connected": True, "method": "login", "account": m.group(0) if m else "",
                "error": ""}
    # Không hiểu câu trả lời: nói ra nguyên văn (đã che), đừng đoán là xanh.
    return {"connected": False,
            "error": "Cursor CLI chưa xác nhận đăng nhập: " + chung.che(txt.strip())[:200]}


_AUTH = chung.CacheNen(_hoi_status, ttl=120.0)


def _file_phien() -> Optional[Path]:
    """File phiên của bản Linux (CHƯA ĐO: ~/.config/cursor/auth.json theo các bản cài thấy được).
    Chỉ dùng làm đường TẮT cho trang Models; nút Kiểm tra lại mới là bằng chứng."""
    for p in (_home_dir() / ".config/cursor/auth.json", _home_dir() / ".cursor/auth.json"):
        try:
            if p.is_file() and p.stat().st_size < 2_000_000:
                d = json.loads(p.read_text(encoding="utf-8") or "{}")
                if isinstance(d, dict) and any(isinstance(v, str) and len(v) > 20
                                               for k, v in d.items() if "token" in k.lower()):
                    return p
        except Exception:
            continue
    return None


def auth_status(cho: bool = False) -> dict:
    cli = find_cursor_cli()
    if not cli:
        return {"connected": False, "method": "", "account": "", "plan": "",
                "error": "Chưa cài Cursor CLI. Bấm \"Cài đặt\" trên thẻ này."}
    k = _khoa()
    if k:
        return {"connected": True, "method": "api-key", "account": "", "plan": "",
                "error": "", "duoi_khoa": chung.duoi_khoa(k)}
    if _file_phien() is not None and not cho:
        return {"connected": True, "method": "login", "account": "", "plan": "", "error": ""}
    d = _AUTH.lay(cho=cho)
    d.setdefault("method", "")
    d.setdefault("account", "")
    d.setdefault("plan", "")
    if d.get("dang_kiem"):
        d["error"] = "Đang hỏi Cursor CLI trạng thái đăng nhập..."
    return d


def dat_api_key(khoa: str) -> dict:
    khoa = (khoa or "").strip()
    if len(khoa) < 16 or any(c.isspace() for c in khoa):
        return {"ok": False, "error": "Khoá không hợp lệ (quá ngắn hoặc có khoảng trắng)."}
    if not chung.ghi_env(_file_khoa(), KHOA_ENV, khoa):
        return {"ok": False, "error": "Không ghi được file khoá."}
    _AUTH.xoa()
    return {"ok": True}


_PHIEN = chung.PhienPty(
    "agent login",
    loc_link=lambda u: ("cursor" in u.lower()) and not re.match(r"https?://(localhost|127\.)", u),
    menu_re=r"press enter|continue\?|\(y/n\)|select")


def login_start(cho_giay: float = 40.0) -> dict:
    cli = find_cursor_cli()
    if not cli:
        return {"ok": False, "can_cai": True, "error": "Chưa cài Cursor CLI. Bấm Cài đặt trước."}
    _AUTH.xoa()
    _PHIEN.start([cli, "login"], env=chung.env_dang_nhap({"NO_OPEN_BROWSER": "1"}))
    _PHIEN.cho_link(cho_giay)
    if _PHIEN.url:
        return {"ok": True, "xong": False, "url": _PHIEN.url, "code": _PHIEN.code,
                "nhat_ky": _PHIEN.log.ds()}
    if auth_status(cho=True).get("connected"):
        _PHIEN.huy()
        return {"ok": True, "xong": True, "url": ""}
    duoi = [x for x in _PHIEN.log.ds() if not x.startswith("[")][-6:]
    _PHIEN.huy()
    return {"ok": False,
            "error": (f"Cursor CLI không in ra link đăng nhập trong {int(cho_giay)} giây. Dùng "
                      "đường chắc chắn: tạo API key ở Cursor Dashboard rồi dán vào thẻ."
                      + (" CLI vừa in: " + " | ".join(x[:140] for x in duoi) if duoi else "")),
            "nhat_ky": _PHIEN.log.ds()}


def login_trang_thai() -> dict:
    dang = _PHIEN.dang_chay()
    if dang:
        # Còn đang chờ người dùng: chỉ hỏi file (rẻ), không đẻ `agent status` mỗi 2 giây.
        d = {"connected": _file_phien() is not None}
    else:
        d = auth_status(cho=True)
    loi = ""
    if not d.get("connected") and not dang:
        cuoi = [x for x in _PHIEN.log.ds() if not x.startswith("[")]
        loi = d.get("error") or "Đăng nhập chưa xong."
        if _PHIEN.ma_thoat not in (None, 0):
            loi = f"`agent login` thoát với mã {_PHIEN.ma_thoat}. " + loi
        if cuoi:
            loi += " CLI nói: " + cuoi[-1][:200]
    return {"connected": bool(d.get("connected")), "dang_cho": dang, "url": _PHIEN.url,
            "code": _PHIEN.code, "nhat_ky": _PHIEN.log.ds(), "error": loi}


def huy_dang_nhap() -> None:
    _PHIEN.huy()


def logout() -> dict:
    _PHIEN.huy()
    chung.ghi_env(_file_khoa(), KHOA_ENV, None)
    _AUTH.xoa()
    cli = find_cursor_cli()
    if not cli:
        return {"ok": False, "error": "Chưa cài Cursor CLI."}
    ma, out, err = chung.chay([cli, "logout"], timeout=30, env=dict(os.environ))
    if (os.environ.get(KHOA_ENV) or "").strip():
        return {"ok": False, "error": ("Khoá còn nằm ở biến môi trường CURSOR_API_KEY của máy chủ - "
                                       "MinMin không gỡ được chỗ đó.")}
    if ma != 0:
        return {"ok": False, "error": (err or out or f"Thoát mã {ma}").strip()[:300]}
    return {"ok": True}


def login_huong_dan() -> dict:
    return {"cai": lenh_cai(), "dang_nhap": "NO_OPEN_BROWSER=1 agent login",
            "ghi_chu": "Đường chắc chắn trên VPS: tạo API key ở Cursor Dashboard rồi dán vào thẻ."}


_CAI = chung.TrinhCai("cursor", find_cursor_cli)


def cai_dat_start() -> dict:
    if os.name == "nt":
        return _CAI.start([["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                            LENH_CAI_WIN]])
    return _CAI.start([["bash", "-c", "set -o pipefail; " + LENH_CAI]])


def cai_dat_trang_thai() -> dict:
    return _CAI.trang_thai()


# ---------------------------------------------------------------------------
# MCP: `<brain>/.cursor/mcp.json`
# ---------------------------------------------------------------------------
def hub_entry(url: str, headers: Optional[dict] = None) -> dict:
    e: dict = {"url": url}
    if headers:
        e["headers"] = dict(headers)
    return e


def mcp_config_path(vault_root) -> Path:
    return Path(vault_root).expanduser() / ".cursor" / "mcp.json"


def ghi_mcp_settings(vault_root, hub: Optional[dict]) -> Optional[str]:
    return chung.ghi_mcp_json(mcp_config_path(vault_root), hub)


def trang_thai_mcp(vault_root) -> dict:
    return chung.trang_thai_mcp_json(mcp_config_path(vault_root))


# ---------------------------------------------------------------------------
_MODEL_RE = re.compile(r"^[a-z0-9][\w.\-:/]*$", re.I)
_TU_KHONG_PHAI_MODEL = {"available", "models", "model", "current", "default", "id", "name"}


def list_models() -> Optional[list]:
    """`agent models` (CHƯA ĐO định dạng): lấy từ đầu của mỗi dòng trông như id model."""
    cli = find_cursor_cli()
    if not cli:
        return None
    ids: list = []
    if _co("models"):
        ma, out, _ = chung.chay([cli, "models"], timeout=30, env=_moi_truong())
        if ma == 0:
            for dong in chung.lam_sach(out).splitlines():
                tok = dong.strip().lstrip("-*•>✓ ").split(" ")[0].strip(",:")
                if tok and _MODEL_RE.match(tok) and tok.lower() not in _TU_KHONG_PHAI_MODEL \
                        and tok not in ids:
                    ids.append(tok)
    for m in MODELS_DU_PHONG:
        if m not in ids:
            ids.insert(0, m)
    return ids[:80]


def co_effort(muc) -> list:
    return []      # Cursor chọn mức nghĩ qua tên model, không có cờ riêng trong tài liệu


def chan_doan() -> dict:
    return {"cli_path": find_cursor_cli() or "", "home": str(_home_dir() / ".cursor"),
            "home_ton_tai": (_home_dir() / ".cursor").is_dir(),
            "file_phien": str(_file_phien() or ""), "co_token": bool(_file_phien() or _khoa()),
            "api_key": bool(_khoa()), "nhat_ky": _PHIEN.log.ds()}


# ---------------------------------------------------------------------------
class CursorCLI(chung.NaoCLIGoc):
    ID = ID
    TEN = TEN
    ENV_TIMEOUT = "JAVIS_CURSOR_TIMEOUT"

    @staticmethod
    def tim_cli():
        return find_cursor_cli()

    @staticmethod
    def lenh_cai():
        return lenh_cai()

    def _chuan_bi(self, full: str) -> tuple:
        args = [self.cli_path, "-p"]
        if _co("--output-format"):
            args += ["--output-format", "stream-json"]
        if _co("--trust"):
            args.append("--trust")            # headless không có ai bấm "tin thư mục này"
        if _co("--approve-mcps"):
            args.append("--approve-mcps")     # để hub MCP của MinMin nạp được
        m = str(self.mode or "").strip().lower()
        if m == "full":
            if _co("--force"):
                args.append("--force")
        elif m == "auto":
            pass                              # không --force: CLI đề xuất, không tự ghi
        else:                                 # suggest hoặc lạ -> nấc chặt nhất
            if _co("--mode"):
                args += ["--mode", "ask"]
        if self.model and self.model != "auto" and _co("--model"):
            args += ["--model", self.model]
        if self.session_id and _co("--resume"):
            args += [f"--resume={self.session_id}"]
        if _co("--workspace"):
            args += ["--workspace", str(self.cwd)]
        args += list(self.extra_args)
        if len(full.encode("utf-8")) <= _TRAN_ARGV:
            return args + [full], None, _moi_truong(), []
        # Quá trần argv: đưa qua stdin (CHƯA ĐO - tài liệu không nói rõ `-p` đọc stdin).
        return args, full, _moi_truong(), []

    def _doi_su_kien(self, ev: dict, gom: dict) -> list:
        sid = str(ev.get("session_id") or ev.get("sessionId") or ev.get("chatId") or "").strip()
        if sid:
            self.session_id = sid
        t = str(ev.get("type") or "")
        st = str(ev.get("subtype") or "")
        if t == "assistant":
            msg = ev.get("message") or {}
            chu = "".join(str(c.get("text") or "") for c in (msg.get("content") or [])
                          if isinstance(c, dict) and c.get("type") == "text")
            if chu:
                gom["manh"].append(chu if not gom["manh"] else "\n\n" + chu)
            return []
        if t == "tool_call":
            tc = ev.get("tool_call") or {}
            ten = ""
            if isinstance(tc, dict):
                if isinstance(tc.get("function"), dict):
                    ten = str(tc["function"].get("name") or "")
                else:
                    k = next(iter(tc.keys()), "")
                    ten = re.sub(r"ToolCall$", "", str(k))
            cid = str(ev.get("call_id") or "")
            if st == "started":
                inp = {}
                if isinstance(tc, dict) and tc:
                    v = next(iter(tc.values()))
                    if isinstance(v, dict):
                        inp = v.get("args") or v.get("arguments") or {}
                return [{"type": "tool_call", "name": ten or "tool", "id": cid, "input": inp}]
            if st == "completed":
                return [{"type": "tool_result", "id": cid, "status": "completed", "content": ""}]
            return []
        if t == "result":
            ra = []
            if isinstance(ev.get("usage"), dict):
                ra.append(chung.doc_usage(ev["usage"]))
            if ev.get("is_error") or (st and st != "success"):
                ra.append({"type": "error", "content": "Cursor CLI: " + str(
                    chung.lay(ev, "result", "error", "message") or st or "lỗi")[:1500]})
            elif isinstance(ev.get("result"), str) and ev["result"].strip():
                gom["final"] = ev["result"]
            return ra
        if t == "error":
            return [{"type": "error", "content": "Cursor CLI: " + str(
                chung.lay(ev, "message", "error") or "lỗi")[:1500]}]
        if t in ("system", "user", "thinking"):
            return []
        gom["vot"] += chung.vot_chu(ev)
        return []

    def _cau_chua_dang_nhap(self, loi: str) -> str:
        l = (loi or "").lower()
        if ("not logged in" in l or "not authenticated" in l or "agent login" in l
                or "authentication required" in l or "please log in" in l):
            return ("Cursor CLI chưa đăng nhập. Mở trang Models, ở thẻ Cursor bấm \"Đăng nhập\" "
                    "hoặc dán API key tạo ở Cursor Dashboard.")
        if "invalid api key" in l or ("api key" in l and ("invalid" in l or "unauthorized" in l)):
            return "API key Cursor không hợp lệ hoặc đã bị thu hồi. Dán khoá mới ở thẻ Cursor."
        return ""


def kiem_tra_nhanh(timeout: float = 90.0) -> dict:
    if not find_cursor_cli():
        return {"ok": False, "error": f"Chưa cài Cursor CLI ({lenh_cai()})."}
    _AUTH.xoa()
    return chung.kiem_tra_bang_luot(CursorCLI, timeout)
