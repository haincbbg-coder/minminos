"""Bộ não Kiro CLI (binary `kiro-cli`, Amazon - thay Amazon Q Developer CLI), chạy bằng gói Kiro.

**CHƯA ĐO TRÊN BINARY THẬT.** Lệnh cài chính chủ `curl -fsSL https://cli.kiro.dev/install | bash`
tải từ cli.kiro.dev - domain bị chặn trong máy dựng bản này, và Kiro không phát hành trên npm
hay PyPI. Mọi thứ dưới đây đọc từ tài liệu chính chủ kiro.dev/docs (đọc 24/10/2026); chỗ nào
tài liệu không nói thì ghi CHƯA ĐO và có cửa thoát biến môi trường.

Theo tài liệu:
- `kiro-cli login`: chọn Builder ID / Google / GitHub / tổ chức (IAM Identity Center). Cờ
  `--license free|pro`, `--social google|github`, `--identity-provider <URL>`, `--region`,
  `--use-device-flow` (ép device flow cho máy từ xa). Device flow "in URL + mã dùng một lần,
  mở ở trình duyệt bất kỳ, không cần mở cổng", dùng được cho Builder ID, Identity Center,
  Google, GitHub (IdP ngoài như Okta thì KHÔNG).
- `kiro-cli logout`, `kiro-cli whoami --format json`.
- Headless: `kiro-cli chat --no-interactive [prompt]` (prompt là tham số hoặc qua stdin),
  `--output-format stream-json` (JSON Lines - sơ đồ sự kiện KHÔNG có trong tài liệu),
  `--trust-all-tools`, `--trust-tools=<id,...>` (V3 khớp đúng id tool nội bộ, vd
  `read_file,grep_search`), `--model <id>`, `--effort low|medium|high|xhigh|max`,
  `--resume-id <ID>`, `--list-models --format json`, `--require-mcp-startup`.
- `KIRO_API_KEY`: chạy không tương tác, CHỈ cho gói Pro, Pro+, Pro Max, Power; tính vào credit
  của gói. Thứ tự: phiên `kiro-cli login` thắng, rồi tới `KIRO_API_KEY`.
- MCP: `.kiro/settings/mcp.json` (workspace) và `~/.kiro/settings/mcp.json` (user), khoá
  `mcpServers`, entry từ xa `{"url": ..., "headers": {...}}`; workspace thắng khi trùng tên.

CHƯA ĐO: chỗ CLI cất phiên đăng nhập (đoán ~/.local/share/kiro-cli, giống Amazon Q - thư mục đó
đã nằm trên volume), sơ đồ stream-json, câu lỗi khi chưa đăng nhập, định dạng whoami/list-models.
Phần dịch sự kiện vì thế bám HÌNH DẠNG (vớt chữ ở mọi tầng) chứ không bám tên loại, và dòng
không phải JSON được giữ làm chữ. Cửa thoát: JAVIS_KIRO_BIN, JAVIS_KIRO_TIMEOUT.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

import cli_nao_chung as chung
from claude_cli import _home_dir

ID = "kiro-cli"
TEN = "Kiro CLI"
KHOA_ENV = "KIRO_API_KEY"
MODELS_DU_PHONG = ["auto"]
LENH_CAI = "curl -fsSL https://cli.kiro.dev/install | bash"
# Id tool CHỈ ĐỌC lấy đúng từ ví dụ trong tài liệu headless (V3). Không chắc đủ, nhưng thiếu
# thì CLI từ chối tool đó - an toàn hơn đoán thêm id rồi vô tình cho phép ghi.
_TOOL_CHI_DOC = "read_file,grep_search"
CACH_DANG_NHAP = {
    "builder-id": ["--license", "free"],
    "google": ["--license", "free", "--social", "google"],
    "github": ["--license", "free", "--social", "github"],
    "identity-center": ["--license", "pro"],
}
HELP = chung.HelpCache()


def find_kiro_cli() -> Optional[str]:
    return chung.tim("JAVIS_KIRO_BIN", ("kiro-cli",), ())


find_cli = find_kiro_cli   # tên chung cho main.py / aux_engine


def lenh_cai() -> str:
    return LENH_CAI


def _file_khoa() -> Path:
    return _home_dir() / ".kiro" / "minmin-api-key.env"


def _khoa() -> str:
    return ((os.environ.get(KHOA_ENV) or "").strip()
            or chung.doc_env(_file_khoa()).get(KHOA_ENV, ""))


def _moi_truong() -> dict:
    e = dict(os.environ)
    k = _khoa()
    if k:
        e[KHOA_ENV] = k
    return e


def _co(lenh: tuple, *c) -> bool:
    return HELP.co(find_kiro_cli(), lenh, *c, env=_moi_truong())


# ---------------------------------------------------------------------------
# Đăng nhập
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _hoi_whoami() -> dict:
    cli = find_kiro_cli()
    if not cli:
        return {"connected": False, "error": "Chưa cài Kiro CLI."}
    ma, out, err = chung.chay([cli, "whoami", "--format", "json"], timeout=25, env=_moi_truong())
    txt = chung.lam_sach(out + "\n" + err)
    l = txt.lower()
    if ma != 0 or "not logged in" in l or "not authenticated" in l:
        return {"connected": False,
                "error": "Đã cài Kiro CLI nhưng chưa đăng nhập. Bấm \"Đăng nhập\" trên thẻ này."}
    acc, plan, cach = "", "", ""
    try:
        d = json.loads(out.strip() or "{}")
        if isinstance(d, dict):
            acc = str(chung.lay(d, "email", "username", "account", "userId", "user") or "")
            plan = str(chung.lay(d, "plan", "subscription", "license", "tier") or "")
            cach = str(chung.lay(d, "authType", "accountType", "method", "provider") or "")
    except Exception:
        m = _EMAIL_RE.search(txt)
        acc = m.group(0) if m else ""
    return {"connected": True, "method": cach or "login", "account": acc, "plan": plan,
            "error": ""}


_AUTH = chung.CacheNen(_hoi_whoami, ttl=120.0)


def auth_status(cho: bool = False) -> dict:
    cli = find_kiro_cli()
    if not cli:
        return {"connected": False, "method": "", "account": "", "plan": "",
                "error": "Chưa cài Kiro CLI. Bấm \"Cài đặt\" trên thẻ này."}
    d = _AUTH.lay(cho=cho)
    if not d.get("connected") and _khoa():
        # Phiên đăng nhập thắng khoá (tài liệu); không có phiên thì khoá là đường còn lại.
        return {"connected": True, "method": "api-key", "account": "", "plan": "",
                "error": "", "duoi_khoa": chung.duoi_khoa(_khoa())}
    d.setdefault("method", "")
    d.setdefault("account", "")
    d.setdefault("plan", "")
    if d.get("dang_kiem"):
        d["error"] = "Đang hỏi Kiro CLI trạng thái đăng nhập..."
    return d


def dat_api_key(khoa: str) -> dict:
    khoa = (khoa or "").strip()
    if len(khoa) < 16 or any(c.isspace() for c in khoa):
        return {"ok": False, "error": "Khoá không hợp lệ (quá ngắn hoặc có khoảng trắng)."}
    if not chung.ghi_env(_file_khoa(), KHOA_ENV, khoa):
        return {"ok": False, "error": "Không ghi được file khoá."}
    _AUTH.xoa()
    return {"ok": True}


def _la_link_dang_nhap(u: str) -> bool:
    if re.match(r"https?://(localhost|127\.|\[::1\])", u):
        return False
    l = u.lower()
    return any(x in l for x in ("aws", "amazon", "kiro", "google", "github", "device", "oauth",
                                "signin", "login"))


_PHIEN = chung.PhienPty(
    "kiro-cli login", loc_link=_la_link_dang_nhap,
    # CHƯA ĐO: cờ chọn cách đăng nhập có thể bị bỏ qua và CLI vẫn hiện menu. Khi đó bấm Enter
    # (mục mặc định) - bài học `agy` 26.10.205: menu in xong rồi im lặng chờ phím.
    menu_re=r"select|choose|sign in with|login method|builder id|use the arrow")


def login_start(cach: str = "builder-id", idc_url: str = "", idc_region: str = "",
                cho_giay: float = 45.0) -> dict:
    cli = find_kiro_cli()
    if not cli:
        return {"ok": False, "can_cai": True, "error": "Chưa cài Kiro CLI. Bấm Cài đặt trước."}
    _AUTH.xoa()
    if _hoi_whoami().get("connected"):
        return {"ok": True, "xong": True, "url": ""}
    args = [cli, "login"]
    co_cach = CACH_DANG_NHAP.get(cach) or CACH_DANG_NHAP["builder-id"]
    if _co(("login",), "--license"):
        args += co_cach
    if cach == "identity-center":
        if not (idc_url or "").strip().startswith("https://"):
            return {"ok": False, "error": ("Identity Center cần địa chỉ Start URL của tổ chức "
                                           "(dạng https://<tên>.awsapps.com/start).")}
        args += ["--identity-provider", idc_url.strip()]
        if (idc_region or "").strip():
            args += ["--region", idc_region.strip()]
    if _co(("login",), "--use-device-flow"):
        args.append("--use-device-flow")
    _PHIEN.start(args, env=chung.env_dang_nhap())
    _PHIEN.cho_link(cho_giay)
    if _PHIEN.url:
        return {"ok": True, "xong": False, "url": _PHIEN.url, "code": _PHIEN.code,
                "nhat_ky": _PHIEN.log.ds()}
    if _hoi_whoami().get("connected"):
        _PHIEN.huy()
        return {"ok": True, "xong": True, "url": ""}
    duoi = [x for x in _PHIEN.log.ds() if not x.startswith("[")][-6:]
    _PHIEN.huy()
    return {"ok": False,
            "error": (f"Kiro CLI không in ra link đăng nhập trong {int(cho_giay)} giây."
                      + (" CLI vừa in: " + " | ".join(x[:140] for x in duoi) if duoi else "")),
            "nhat_ky": _PHIEN.log.ds()}


def login_trang_thai() -> dict:
    dang = _PHIEN.dang_chay()
    d = {"connected": False}
    if not dang:
        _AUTH.xoa()
        d = auth_status(cho=True)
    loi = ""
    if not d.get("connected") and not dang:
        cuoi = [x for x in _PHIEN.log.ds() if not x.startswith("[")]
        loi = d.get("error") or "Đăng nhập chưa xong."
        if _PHIEN.ma_thoat not in (None, 0):
            loi = f"`kiro-cli login` thoát với mã {_PHIEN.ma_thoat}. " + loi
        if cuoi:
            loi += " CLI nói: " + cuoi[-1][:200]
    return {"connected": bool(d.get("connected")), "dang_cho": dang, "url": _PHIEN.url,
            "code": _PHIEN.code, "account": d.get("account", ""), "plan": d.get("plan", ""),
            "nhat_ky": _PHIEN.log.ds(), "error": loi}


def huy_dang_nhap() -> None:
    _PHIEN.huy()


def logout() -> dict:
    _PHIEN.huy()
    chung.ghi_env(_file_khoa(), KHOA_ENV, None)
    _AUTH.xoa()
    cli = find_kiro_cli()
    if not cli:
        return {"ok": False, "error": "Chưa cài Kiro CLI."}
    ma, out, err = chung.chay([cli, "logout"], timeout=30, env=dict(os.environ))
    if (os.environ.get(KHOA_ENV) or "").strip():
        return {"ok": False, "error": ("Khoá còn nằm ở biến môi trường KIRO_API_KEY của máy chủ - "
                                       "MinMin không gỡ được chỗ đó.")}
    if ma != 0:
        return {"ok": False, "error": (err or out or f"Thoát mã {ma}").strip()[:300]}
    return {"ok": True}


def login_huong_dan() -> dict:
    return {"cai": lenh_cai(), "dang_nhap": "kiro-cli login --use-device-flow",
            "ghi_chu": ("API key (KIRO_API_KEY) chỉ dùng được với gói Kiro Pro, Pro+, Pro Max, "
                        "Power - tạo ở app.kiro.dev, mục API Keys.")}


_CAI = chung.TrinhCai("kiro", find_kiro_cli)


def cai_dat_start() -> dict:
    if os.name == "nt":
        return {"ok": False, "error": ("Kiro chưa công bố lệnh cài CLI cho Windows trên trang tải về. "
                                       "Cài thủ công từ kiro.dev/downloads.")}
    return _CAI.start([["bash", "-c", "set -o pipefail; " + LENH_CAI]])


def cai_dat_trang_thai() -> dict:
    return _CAI.trang_thai()


# ---------------------------------------------------------------------------
# MCP: `<brain>/.kiro/settings/mcp.json` (tầng workspace)
# ---------------------------------------------------------------------------
def hub_entry(url: str, headers: Optional[dict] = None) -> dict:
    e: dict = {"url": url}
    if headers:
        e["headers"] = dict(headers)
    return e


def mcp_config_path(vault_root) -> Path:
    return Path(vault_root).expanduser() / ".kiro" / "settings" / "mcp.json"


def ghi_mcp_settings(vault_root, hub: Optional[dict]) -> Optional[str]:
    return chung.ghi_mcp_json(mcp_config_path(vault_root), hub)


def trang_thai_mcp(vault_root) -> dict:
    return chung.trang_thai_mcp_json(mcp_config_path(vault_root))


# ---------------------------------------------------------------------------
def list_models() -> Optional[list]:
    cli = find_kiro_cli()
    if not cli:
        return None
    ids: list = []
    ma, out, _ = chung.chay([cli, "chat", "--list-models", "--format", "json"], timeout=30,
                            env=_moi_truong())
    if ma == 0:
        try:
            d = json.loads(out.strip() or "[]")
            if isinstance(d, dict):
                d = d.get("models") or d.get("data") or []
            for m in d if isinstance(d, list) else []:
                mid = (chung.lay(m, "model_id", "modelId", "id", "name") if isinstance(m, dict)
                       else m)
                if isinstance(mid, str) and mid.strip() and mid.strip() not in ids:
                    ids.append(mid.strip())
        except Exception:
            pass
    for m in MODELS_DU_PHONG:
        if m not in ids:
            ids.insert(0, m)
    return ids[:80]


_DOI_EFFORT = {"ultra": "max"}


def co_effort(muc) -> list:
    """['--effort', '<mức>'] chỉ khi `kiro-cli chat --help` khai CẢ cờ lẫn giá trị."""
    if not muc:
        return []
    muc = _DOI_EFFORT.get(str(muc), str(muc))
    txt = HELP.text(find_kiro_cli(), "chat", env=_moi_truong())
    if txt and "--effort" in txt and re.search(r"\b" + re.escape(muc) + r"\b", txt):
        return ["--effort", muc]
    return []


def chan_doan() -> dict:
    h = _home_dir() / ".kiro"
    return {"cli_path": find_kiro_cli() or "", "home": str(h), "home_ton_tai": h.is_dir(),
            "co_token": bool(_khoa()), "api_key": bool(_khoa()), "nhat_ky": _PHIEN.log.ds()}


# ---------------------------------------------------------------------------
class KiroCLI(chung.NaoCLIGoc):
    ID = ID
    TEN = TEN
    ENV_TIMEOUT = "JAVIS_KIRO_TIMEOUT"

    @staticmethod
    def tim_cli():
        return find_kiro_cli()

    @staticmethod
    def lenh_cai():
        return LENH_CAI

    def _chuan_bi(self, full: str) -> tuple:
        args = [self.cli_path, "chat", "--no-interactive"]
        if _co(("chat",), "--output-format"):
            args += ["--output-format", "stream-json"]
        m = str(self.mode or "").strip().lower()
        if m == "full":
            if _co(("chat",), "--trust-all-tools"):
                args.append("--trust-all-tools")
        elif _co(("chat",), "--trust-tools"):
            # suggest/auto (và mode lạ): chỉ tin tool đọc. Headless không có ai bấm duyệt nên
            # tool khác bị từ chối - kể cả tool hub, CHƯA ĐO id của chúng để tin riêng.
            args.append("--trust-tools=" + _TOOL_CHI_DOC)
        if self.model and self.model != "auto" and _co(("chat",), "--model"):
            args += ["--model", self.model]
        if self.effort:
            args += ["--effort", str(self.effort)]
        if self.session_id and _co(("chat",), "--resume-id"):
            args += ["--resume-id", self.session_id]
        if _co(("chat",), "--wrap"):
            args += ["--wrap", "never"]
        args += list(self.extra_args)
        # Prompt qua STDIN (tài liệu: "positional argument or piped stdin"): không đụng trần
        # dòng lệnh dù system prompt + ngữ cảnh brain dài bao nhiêu.
        return args, full, _moi_truong(), []

    def _doi_su_kien(self, ev: dict, gom: dict) -> list:
        """Sơ đồ stream-json của Kiro CHƯA có tài liệu: dịch theo HÌNH DẠNG."""
        for k in ("session_id", "sessionId", "conversation_id", "conversationId"):
            v = ev.get(k)
            if isinstance(v, str) and v.strip():
                self.session_id = v.strip()
                break
        t = str(ev.get("type") or ev.get("event") or "").lower()
        ra: list = []
        u = ev.get("usage")
        if not isinstance(u, dict) and isinstance(ev.get("metadata"), dict):
            u = ev["metadata"].get("usage")
        if isinstance(u, dict):
            ra.append(chung.doc_usage(u))
        if "tool" in t:
            if any(x in t for x in ("result", "complete", "end", "output")):
                return ra
            ten = str(chung.lay(ev, "name", "tool_name", "toolName", "tool") or "tool")
            if isinstance(ev.get("tool"), dict):
                ten = str(chung.lay(ev["tool"], "name", "id") or ten)
            return ra + [{"type": "tool_call", "name": ten,
                          "id": str(chung.lay(ev, "id", "tool_use_id", "toolUseId", "call_id")),
                          "input": chung.lay(ev, "input", "args", "arguments", mac_dinh={})}]
        if t == "error" or (ev.get("is_error") and t == "result"):
            return ra + [{"type": "error", "content": "Kiro CLI: " + str(
                chung.lay(ev, "message", "error", "result", "content") or "lỗi")[:1500]}]
        if t in ("result", "final", "done", "end", "completion"):
            v = chung.lay(ev, "result", "text", "content", "message", "response")
            if isinstance(v, str) and v.strip():
                gom["final"] = v
            elif v:
                x = "\n".join(chung.vot_chu(v)).strip()
                if x:
                    gom["final"] = x
            return ra
        if "delta" in t or t in ("text", "chunk", "assistant_text", "content"):
            v = chung.lay(ev, "text", "delta", "content", "data")
            if isinstance(v, str):
                gom["manh"].append(v)
            elif isinstance(v, dict):
                gom["manh"].append("".join(chung.vot_chu(v)))
            return ra
        if t in ("assistant", "message", "assistant_message", "response"):
            gom["vot"] += chung.vot_chu(ev)
            return ra
        if t in ("user", "system", "init", "thinking", "reasoning", "metadata", "usage"):
            return ra
        gom["vot"] += chung.vot_chu(ev)
        return ra

    def _cau_chua_dang_nhap(self, loi: str) -> str:
        l = (loi or "").lower()
        if ("not logged in" in l or "kiro-cli login" in l or "not authenticated" in l
                or "please log in" in l or "authentication required" in l
                or "token has expired" in l or "sso session" in l):
            return ("Kiro CLI chưa đăng nhập (hoặc phiên đã hết hạn). Mở trang Models, ở thẻ Kiro "
                    "bấm \"Đăng nhập\", hoặc dán KIRO_API_KEY nếu bạn có gói Pro trở lên.")
        if "kiro_api_key" in l and ("invalid" in l or "unauthorized" in l or "not available" in l):
            return ("KIRO_API_KEY không dùng được. Khoá chỉ chạy với gói Pro, Pro+, Pro Max, Power "
                    "(gói do công ty quản lý thì quản trị viên phải bật).")
        return ""


def kiem_tra_nhanh(timeout: float = 90.0) -> dict:
    if not find_kiro_cli():
        return {"ok": False, "error": f"Chưa cài Kiro CLI ({lenh_cai()})."}
    _AUTH.xoa()
    return chung.kiem_tra_bang_luot(KiroCLI, timeout)
