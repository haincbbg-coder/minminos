"""Phần DÙNG CHUNG của ba bộ não CLI gói thuê bao thêm ở 26.10.215: Kiro, Cursor, Mistral Vibe.

Vì sao có file này thay vì chép khuôn `grok_cli.py` ba lần: cả ba cần đúng mấy món giống nhau -
tìm binary, hỏi `--help` có nhớ, cài nền bằng lệnh chính chủ, mở phiên đăng nhập trong pty để
bóc link + mã, đọc NDJSON của một lượt chạy headless có trần giờ, ghi cấu hình MCP trỏ về hub.
Chép ba lần là ba bản lệch nhau dần, đúng bài học đã trả giá giữa `grok` và `agy`.

KHÔNG đụng grok/muse/antigravity: ba module đó đang chạy thật trên máy chủ, giữ nguyên hành vi.
File này chỉ phục vụ ba bộ não mới. Nơi khác trong app gọi chúng qua `NAO` + `mo_dun(pid)`, để
thêm một bộ não CLI nữa là thêm một dòng ở đây chứ không rải thêm nhánh `elif` khắp main.py.

Bài học cũ được giữ nguyên ở đây (xem đầu `antigravity_cli.py`):
1. CLI thật hay hiện MENU rồi im lặng chờ phím -> phiên pty biết tự bấm Enter.
2. Đọc pty phải có hạn chờ (`select`), không thì treo.
3. Link dài bị bẻ dòng theo bề rộng pty -> pty rộng 1000 cột, COLUMNS=1000.
4. Luồng đọc pty TỰ đóng fd của nó; luồng khác chỉ giết tiến trình.
"""
from __future__ import annotations

import asyncio
import errno
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from claude_cli import _home_dir, _no_window, tim_binary

# id provider -> tên module. Thứ tự là thứ tự thẻ trên trang Models.
NAO = {"kiro-cli": "kiro_cli", "cursor-cli": "cursor_cli", "vibe-cli": "vibe_cli"}


def mo_dun(pid: str):
    """Module của bộ não `pid`, hoặc None nếu không phải ba bộ não này."""
    ten = NAO.get(str(pid or ""))
    if not ten:
        return None
    try:
        return importlib.import_module(ten)
    except Exception as e:   # module hỏng không được kéo sập trang Models
        print(f"[nao cli] không nạp được {ten}: {e}", file=sys.stderr)
        return None


def la_nao(pid: str) -> bool:
    return str(pid or "") in NAO


# ---------------------------------------------------------------------------
# Tìm binary, chạy lệnh ngắn, nhớ `--help`
# ---------------------------------------------------------------------------
def tim(env_var: str, ten: tuple, them: tuple = (), loc: Optional[Callable] = None) -> Optional[str]:
    """Tìm binary: biến môi trường (cửa thoát) > PATH > các chỗ installer chính chủ hay thả.

    `loc(path) -> bool` loại những binary trùng tên mà không phải của hãng (vd `agent` của
    Cursor là một cái tên quá chung, PATH có thể có một `agent` khác hẳn).
    """
    envp = (os.environ.get(env_var) or "").strip()
    if envp:
        try:
            if Path(envp).exists():
                return envp
        except Exception:
            pass
    home = _home_dir()
    for t in ten:
        p = tim_binary(t)
        if p and (loc is None or loc(p)):
            return p
    for rel in tuple(f".local/bin/{t}" for t in ten) + tuple(them):
        p = home / rel
        try:
            if p.exists() and (loc is None or loc(str(p))):
                return str(p)
        except Exception:
            pass
    return None


def chay(args: list, timeout: float = 20.0, env: Optional[dict] = None, cwd=None,
         dau_vao: Optional[str] = None) -> tuple:
    """(mã thoát, stdout, stderr). Không bao giờ ném; lỗi chạy -> (-1, "", câu lỗi).

    stdin luôn có giá trị (DEVNULL hoặc chuỗi): CLI nào rơi vào màn hỏi tương tác cũng thoát
    ngay thay vì ngồi chờ bàn phím vô hình ăn trọn timeout (bài học của `agy`, 2026-08-30).
    """
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, creationflags=_no_window(),
                           env=env, cwd=cwd,
                           input=dau_vao if dau_vao is not None else None,
                           stdin=None if dau_vao is not None else subprocess.DEVNULL)
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"quá {int(timeout)} giây không trả lời"
    except Exception as e:
        return -1, "", f"{type(e).__name__}: {e}"


class HelpCache:
    """Nhớ nội dung `--help` theo (binary, lệnh con). Fail-closed: không đọc được = không có cờ.

    Cùng tinh thần `grok_cli.co_co`: CLI mới đổi cờ liên tục, truyền một cờ nó chưa có là nó
    thoát ngay với "unknown flag" và hỏng cả lượt chat chỉ vì một tuỳ chọn phụ.
    """
    TTL = 300.0
    TTL_LOI = 120.0

    def __init__(self):
        self._d: dict = {}

    def text(self, cli: Optional[str], *lenh_con: str, env: Optional[dict] = None) -> str:
        if not cli:
            return ""
        k = (cli,) + tuple(lenh_con)
        now = time.time()
        cu = self._d.get(k)
        if cu and now - cu[1] < (self.TTL if cu[0] else self.TTL_LOI):
            return cu[0]
        ma, out, err = chay([cli, *lenh_con, "--help"], timeout=20, env=env)
        txt = (out + "\n" + err) if (out or err) and ma != -1 else ""
        self._d[k] = (txt, now)
        return txt

    def co(self, cli, lenh_con: tuple, *ten_co: str, env: Optional[dict] = None) -> bool:
        txt = self.text(cli, *lenh_con, env=env)
        return bool(txt) and any(c in txt for c in ten_co)

    def xoa(self):
        self._d.clear()


# ---------------------------------------------------------------------------
# Che bí mật, nhật ký
# ---------------------------------------------------------------------------
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07|\x1b[()][A-Z0-9]|\x1b[=>]")
_BIMAT_RE = re.compile(r"\b(?![A-Z0-9]{4,}-)[A-Za-z0-9_\-]{32,}\b")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")
_MA_RE = re.compile(r"\b[A-Z0-9]{4,}(?:-[A-Z0-9]{4,})+\b")
NHAT_KY_TOI_DA = 60


def lam_sach(s: str) -> str:
    return _ANSI_RE.sub("", s or "")


def che(s: str) -> str:
    """Che chuỗi giống bí mật. Nhật ký này HIỆN RA MÀN HÌNH và đi vào ảnh chụp người dùng gửi.

    Link đăng nhập giữ nguyên (người dùng cần bấm), nhưng tham số code/token trong URL thì che.
    Chuỗi `sk-...`, `key_...` dài cũng che dù có gạch nối.
    """
    s = re.sub(r"((?:code|token|access_token|refresh_token|api_key|key)=)[^&\s]+",
               r"\1[đã che]", s)
    if "://" in s:
        return s
    s = re.sub(r"\b(sk|key|crsr|ksk)[-_][A-Za-z0-9_\-]{12,}", "[đã che]", s)
    return _BIMAT_RE.sub("[đã che]", s)


class NhatKy:
    def __init__(self, toi_da: int = NHAT_KY_TOI_DA):
        self.d = deque(maxlen=toi_da)

    def ghi(self, dong: str) -> None:
        x = che(lam_sach(str(dong)).strip())
        if x:
            self.d.append(x)

    def ds(self) -> list:
        return list(self.d)


# ---------------------------------------------------------------------------
# Cài nền bằng lệnh chính chủ
# ---------------------------------------------------------------------------
class TrinhCai:
    """Chạy lệnh cài ở NỀN, nhật ký đọc dần. Binary vào ~/.local/bin - trong Docker thư mục đó
    đã được `docker/entrypoint.sh` link sang volume /data nên cài một lần là sống qua cập nhật."""

    def __init__(self, ten: str, tim_cli: Callable[[], Optional[str]]):
        self.ten = ten
        self.tim_cli = tim_cli
        self.dang_chay = False
        self.ok: Optional[bool] = None
        self.log = NhatKy()

    def start(self, cac_lenh: list) -> dict:
        """`cac_lenh`: danh sách argv chạy LẦN LƯỢT, dừng ở lệnh đầu tiên làm ra binary."""
        if self.tim_cli():
            return {"ok": True, "da_co": True}
        if self.dang_chay:
            return {"ok": True, "dang_chay": True}
        self.dang_chay, self.ok, self.log = True, None, NhatKy()

        def _chay():
            try:
                for args in cac_lenh:
                    self.log.ghi("[MinMin chạy] " + " ".join(str(a) for a in args)[:300])
                    try:
                        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             stdin=subprocess.DEVNULL, creationflags=_no_window(),
                                             cwd=str(_home_dir()))
                        for dong in iter(p.stdout.readline, b""):
                            self.log.ghi(dong.decode("utf-8", "replace"))
                        ma = p.wait(timeout=900)
                        self.log.ghi(f"[lệnh cài kết thúc, mã thoát {ma}]")
                    except Exception as e:
                        self.log.ghi(f"[lỗi cài] {type(e).__name__}: {e}")
                    if self.tim_cli():
                        break
                self.ok = bool(self.tim_cli())
            finally:
                self.dang_chay = False

        threading.Thread(target=_chay, name=f"minmin-cai-{self.ten}", daemon=True).start()
        return {"ok": True, "dang_chay": True}

    def trang_thai(self) -> dict:
        co = self.tim_cli()
        d = {"dang_chay": self.dang_chay, "ok": True if co else self.ok,
             "cli_path": co or "", "nhat_ky": self.log.ds()}
        if self.ok is False and not co:
            d["error"] = "Cài không thành công. Xem nhật ký bên dưới."
        return d


# ---------------------------------------------------------------------------
# Phiên đăng nhập chạy trong pty: bóc link + mã, tự bấm qua menu
# ---------------------------------------------------------------------------
def env_dang_nhap(them: Optional[dict] = None) -> dict:
    """Môi trường cho tiến trình đăng nhập: luôn ép luồng 'máy từ xa' (in link, không mở
    trình duyệt). Trang Models luôn được mở từ một trình duyệt KHÁC tiến trình CLI."""
    e = dict(os.environ)
    e["TERM"] = "xterm-256color"
    e.setdefault("LANG", "C.UTF-8")
    e.setdefault("NO_BROWSER", "1")
    e.setdefault("NO_OPEN_BROWSER", "1")
    e.setdefault("BROWSER", "echo")
    e["COLUMNS"] = "1000"
    e["LINES"] = "50"
    if not e.get("SSH_CONNECTION"):
        e["SSH_CONNECTION"] = "127.0.0.1 0 127.0.0.1 22"
        e.setdefault("SSH_CLIENT", "127.0.0.1 0 22")
    if them:
        e.update(them)
    return e


class PhienPty:
    """Một tiến trình đăng nhập chạy trong pseudo-terminal (POSIX), ống thường nếu không có pty.

    `loc_link(url) -> bool` chọn đúng link cần mở (loại địa chỉ localhost/telemetry).
    `menu_re`: thấy chữ này trong output mà CHƯA có link thì bấm Enter (mục mặc định), tối đa
    ba lần đổi kiểu phím - bài học 26.10.205 của `agy`: menu in xong rồi im chờ phím.
    """

    def __init__(self, ten: str, loc_link: Optional[Callable[[str], bool]] = None,
                 menu_re: Optional[str] = None):
        self.ten = ten
        self.loc_link = loc_link or (lambda u: True)
        self.menu_re = re.compile(menu_re, re.I) if menu_re else None
        self.proc = None
        self.fd = None
        self.url = ""
        self.code = ""
        self.ma_thoat = None
        self.log = NhatKy()
        self.bat_dau = 0.0

    # -- vòng đời --
    def start(self, args: list, env: Optional[dict] = None, cwd=None) -> None:
        self.huy()
        self.url, self.code, self.ma_thoat, self.log = "", "", None, NhatKy()
        self.bat_dau = time.time()
        e = env or env_dang_nhap()
        cwd = str(cwd or _home_dir())
        try:
            import pty
            master, slave = pty.openpty()
            try:
                import fcntl, struct, termios
                fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 1000, 0, 0))
            except Exception:
                pass
            self.proc = subprocess.Popen(args, stdin=slave, stdout=slave, stderr=slave, env=e,
                                         start_new_session=True, close_fds=True, cwd=cwd,
                                         creationflags=_no_window())
            os.close(slave)
            self.fd = master
        except Exception:
            self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, env=e, cwd=cwd,
                                         creationflags=_no_window())
            self.fd = None
        self.log.ghi("[MinMin chạy] " + " ".join(str(a) for a in args[1:])[:200])
        threading.Thread(target=self._doc_luong, args=(self.proc, self.fd),
                         name=f"minmin-login-{self.ten}", daemon=True).start()

    def dang_chay(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def huy(self) -> None:
        """Giết tiến trình. KHÔNG đóng fd ở đây: luồng đọc tự đóng khi nó thoát (bài học 4)."""
        p = self.proc
        if p and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass
        self.proc, self.fd = None, None

    def gui(self, chu: str) -> bool:
        b = chu.encode("utf-8")
        try:
            if self.fd is not None:
                os.write(self.fd, b)
                return True
            if self.proc and self.proc.stdin:
                self.proc.stdin.write(b)
                self.proc.stdin.flush()
                return True
        except Exception:
            pass
        return False

    def cho_link(self, cho_giay: float) -> None:
        han = time.time() + cho_giay
        while time.time() < han and not self.url and self.dang_chay():
            time.sleep(0.2)
        # CLI in link rồi in mã ở dòng sau: chờ thêm một nhịp cho mã kịp tới.
        if self.url and not self.code:
            han2 = time.time() + 1.5
            while time.time() < han2 and not self.code and self.dang_chay():
                time.sleep(0.1)

    # -- đọc --
    def _bat(self, s: str) -> None:
        sach = lam_sach(s)
        if not self.url:
            for m in _URL_RE.finditer(sach):
                u = m.group(0).rstrip(".,);]")
                if self.loc_link(u):
                    self.url = u
                    break
        if not self.code:
            for tok in _MA_RE.findall(sach):
                self.code = tok
                break

    def _doc_luong(self, proc, fd) -> None:
        buf, gan_day = "", ""
        lan_bam, luc_bam = 0, 0.0

        def _doc():
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

        def _co_le_bam():
            nonlocal lan_bam, luc_bam, gan_day
            if self.menu_re is None or self.url or lan_bam >= 3:
                return
            now = time.time()
            if now - self.bat_dau < 2 or (lan_bam and now - luc_bam < 5):
                return
            if not self.menu_re.search(lam_sach(gan_day)):
                return
            self.gui(("\r", "\n", "1\r")[lan_bam])
            lan_bam += 1
            luc_bam = now
            gan_day = ""
            self.log.ghi(f"[MinMin chọn mục mặc định ở menu đăng nhập, lần {lan_bam}]")

        try:
            while True:
                ch = _doc()
                if not ch:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
                    _co_le_bam()
                    continue
                gan_day = (gan_day + ch)[-3000:]
                for c in ch:
                    if c in "\r\n":
                        if buf.strip():
                            self._bat(buf)
                            self.log.ghi(buf)
                        buf = ""
                    else:
                        buf += c
                        if len(buf) > 4000:
                            self._bat(buf)
                            self.log.ghi(buf)
                            buf = ""
                _co_le_bam()
        except Exception as e:
            self.log.ghi(f"[MinMin đọc output lỗi] {type(e).__name__}: {e}")
        if buf.strip():
            self._bat(buf)
            self.log.ghi(buf)
        try:
            self.ma_thoat = proc.wait(timeout=5)
            self.log.ghi(f"[{self.ten} kết thúc, mã thoát {self.ma_thoat}]")
        except Exception:
            pass
        if fd is not None:
            if self.fd == fd:
                self.fd = None
            try:
                os.close(fd)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Trạng thái đăng nhập phải hỏi CLI: nhớ + làm mới ở nền
# ---------------------------------------------------------------------------
class CacheNen:
    """Giá trị đắt (đẻ tiến trình) cho luồng async: trả cache NGAY, làm mới ở thread nền.

    Cùng lý do `antigravity_cli.auth_status_nen`: `_providers_view` chạy trong handler async của
    GET /settings, một CLI treo trong đó từng làm CẢ dashboard đứng hình (2026-08-30).
    """

    def __init__(self, fn: Callable[[], dict], ttl: float = 60.0, mac_dinh: Optional[dict] = None):
        self.fn = fn
        self.ttl = ttl
        self.val: Optional[dict] = None
        self.ts = 0.0
        self.dang = False
        self.mac_dinh = mac_dinh or {"connected": False, "dang_kiem": True, "error": ""}

    def lay(self, cho: bool = False) -> dict:
        if cho:
            return self._lam_moi()
        if self.val is None or time.time() - self.ts > self.ttl:
            if not self.dang:
                self.dang = True
                threading.Thread(target=self._lam_moi, daemon=True,
                                 name="minmin-nao-auth").start()
        return dict(self.val) if self.val is not None else dict(self.mac_dinh)

    def _lam_moi(self) -> dict:
        try:
            v = self.fn()
        except Exception as e:
            v = {"connected": False, "error": f"{type(e).__name__}: {e}"}
        finally:
            self.dang = False
        self.val, self.ts = v, time.time()
        return dict(v)

    def xoa(self):
        self.val, self.ts = None, 0.0


# ---------------------------------------------------------------------------
# File .env (khoá dán từ thẻ Models) - quyền 0600, không bao giờ trả giá trị ra giao diện
# ---------------------------------------------------------------------------
def doc_env(p: Path) -> dict:
    ra = {}
    try:
        for dong in p.read_text(encoding="utf-8").splitlines():
            dong = dong.strip()
            if not dong or dong.startswith("#") or "=" not in dong:
                continue
            k, v = dong.split("=", 1)
            k = k.strip()
            if k.startswith("export "):
                k = k[7:].strip()
            ra[k] = v.strip().strip("'").strip('"')
    except Exception:
        pass
    return ra


def ghi_env(p: Path, khoa: str, gia_tri: Optional[str]) -> bool:
    """Đặt (hoặc gỡ khi `gia_tri` rỗng) MỘT dòng `KHOA=...`, giữ mọi dòng khác của file."""
    try:
        dong_cu = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    except Exception:
        dong_cu = []
    moi = [d for d in dong_cu
           if not re.match(r"^\s*(export\s+)?" + re.escape(khoa) + r"\s*=", d)]
    if gia_tri:
        moi.append(f"{khoa}={gia_tri}")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(moi) + ("\n" if moi else ""), encoding="utf-8")
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[nao cli env] {p}: {e}", file=sys.stderr)
        return False


def duoi_khoa(v: str) -> str:
    v = (v or "").strip()
    return v[-4:] if len(v) >= 8 else ""


# ---------------------------------------------------------------------------
# MCP: JSON `{"mcpServers": {"javis": {...}}}` (Kiro, Cursor)
# ---------------------------------------------------------------------------
def _doc_json_ky(p: Path) -> tuple:
    """(đọc_được, dict). File có mà hỏng thì KHÔNG được ghi đè - xem `grok_cli._doc_toml_ky`."""
    try:
        if not p.exists():
            return True, {}
        d = json.loads(p.read_text(encoding="utf-8") or "{}")
        return True, (d if isinstance(d, dict) else {})
    except Exception as e:
        print(f"[nao cli mcp] `{p}` không đọc được, KHÔNG ghi đè: {e}", file=sys.stderr)
        return False, {}


def ghi_mcp_json(p: Path, hub: Optional[dict], ten: str = "javis") -> Optional[str]:
    """Gộp entry `javis` vào `mcpServers` của file, giữ server khác. hub=None -> gỡ entry."""
    try:
        ok, cu = _doc_json_ky(p)
        if not ok:
            return None
        sv = cu.get("mcpServers")
        if not isinstance(sv, dict):
            sv = {}
        if hub:
            sv[ten] = hub
        else:
            sv.pop(ten, None)
        cu["mcpServers"] = sv
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(p, 0o600)   # chứa hub token
        except Exception:
            pass
        return str(p)
    except Exception as e:
        print(f"[nao cli mcp] {e}", file=sys.stderr)
        return None


def trang_thai_mcp_json(p: Path, ten: str = "javis", khoa_url: str = "url") -> dict:
    """ĐỌC LẠI file vừa ghi: 'đã ghi xong' không phải bằng chứng (bài học `agy` 0.43.0)."""
    ra = {"file": str(p), "ton_tai": False, "co_javis": False, "url": "", "so_header": 0}
    try:
        ra["ton_tai"] = p.exists()
    except Exception:
        return ra
    if not ra["ton_tai"]:
        return ra
    ok, d = _doc_json_ky(p)
    e = ((d.get("mcpServers") or {}) if ok else {}).get(ten)
    if isinstance(e, dict):
        ra["co_javis"] = True
        ra["url"] = str(e.get(khoa_url) or "")
        h = e.get("headers")
        ra["so_header"] = len(h) if isinstance(h, dict) else 0
    return ra


# ---------------------------------------------------------------------------
# Vớt chữ từ một sự kiện JSON sơ đồ chưa biết
# ---------------------------------------------------------------------------
KHOA_CHU = ("text", "result", "content", "data", "delta", "response", "output", "answer",
            "message", "reply", "completion")
LOAI_KHONG_PHAI_TRA_LOI = ("thought", "thinking", "reasoning", "usage", "tool_call",
                           "tool_use", "tool_result", "effect", "callback", "user", "system",
                           "init", "ping", "heartbeat", "available_commands")


def vot_chu(ev, sau: int = 0) -> list:
    """Mọi mẩu chữ người đọc được trong một sự kiện, bất kể sơ đồ. Bám HÌNH DẠNG chứ không
    bám tên loại - đúng bài học Grok 29/08 (khoá `data` chứ không phải `text`)."""
    ra: list = []

    def di(o, s=0):
        if s > 6 or len(ra) >= 20:
            return
        if isinstance(o, dict):
            if str(o.get("type") or "").lower() in LOAI_KHONG_PHAI_TRA_LOI:
                return
            if str(o.get("role") or "").lower() in ("user", "system", "tool"):
                return
            for k, v in o.items():
                if isinstance(v, str) and v.strip() and str(k).lower() in KHOA_CHU:
                    ra.append(v)
                else:
                    di(v, s + 1)
        elif isinstance(o, list):
            for v in o[:30]:
                di(v, s + 1)

    di(ev, sau)
    return ra


def lay(d: dict, *ten, mac_dinh=""):
    for k in ten:
        v = d.get(k) if isinstance(d, dict) else None
        if v not in (None, ""):
            return v
    return mac_dinh


def doc_usage(u: dict) -> dict:
    u = u if isinstance(u, dict) else {}
    vao = int(u.get("input_tokens") or u.get("inputTokens") or u.get("prompt_tokens") or 0)
    ra = int(u.get("output_tokens") or u.get("outputTokens") or u.get("completion_tokens") or 0)
    cache = int(u.get("cached_input_tokens") or u.get("cache_read_input_tokens")
                or u.get("cacheReadTokens") or 0)
    return {"type": "usage", "input_tokens": vao, "output_tokens": ra,
            "total_tokens": int(u.get("total_tokens") or u.get("totalTokens") or (vao + ra)),
            "cached": cache}


# Cờ mà giá trị đi sau là NỘI DUNG NGƯỜI DÙNG - không bao giờ hiện trong câu lỗi.
_CO_MANG_PROMPT = ("-p", "--print", "--prompt", "--prompt-file", "--api-key")


def cat_args(args: list) -> list:
    """Danh sách cờ đã truyền, KHÔNG kèm prompt hay khoá (xem `grok_cli._cat_args`)."""
    ra, truoc = [], ""
    for a in [str(x) for x in args[1:]]:
        if a.startswith("-"):
            ra.append(a.split("=", 1)[0] if a.startswith("--api-key") else a)
            truoc = a
            continue
        if truoc in _CO_MANG_PROMPT:
            ra.append("<ẩn>")
        elif truoc and len(a) <= 40 and "\n" not in a and not a.startswith(("/", "\\")):
            ra.append(a)
        else:
            ra.append("<prompt>" if len(a) > 40 else "")
        truoc = ""
    return [x for x in ra if x][:20]


# ---------------------------------------------------------------------------
# Một lượt chạy headless: tiến trình + NDJSON + trần giờ
# ---------------------------------------------------------------------------
class NaoCLIGoc:
    """Khuôn chung cho một lượt chạy headless. Cùng hợp đồng sự kiện với GrokCLI/MuseCLI:
    query() sinh {"type": "tool_call"|"usage"|"error"|"final", ...}.

    Lớp con định nghĩa:
      ID, TEN, ENV_TIMEOUT, tim_cli(), lenh_cai()
      _chuan_bi(full_prompt) -> (args, stdin_text|None, env, [file cần dọn])
      _doi_su_kien(ev, gom) -> list   (gom: {"manh": [...], "final": "", "vot": [...]})
      _cau_chua_dang_nhap(loi) -> str ("" nếu không phải lỗi đăng nhập)
      _sau_luot(gom) (tuỳ chọn: đọc file phụ như export.json)
    """
    ID = "cli"
    TEN = "CLI"
    ENV_TIMEOUT = "JAVIS_NAO_CLI_TIMEOUT"
    STDERR_ON = ""          # regex các dòng stderr vô hại, không in ra nhật ký máy chủ

    def __init__(self, cwd: Optional[str] = None, tag: str = "chat", model: Optional[str] = None,
                 instructions: Optional[str] = None):
        self.cli_path = self.tim_cli()
        self.cwd = cwd or os.getcwd()
        self.tag = tag
        self.model = model
        self.instructions = instructions
        self.session_id: Optional[str] = None
        self.mode = "full"
        self.max_turns = 0
        self.effort: Optional[str] = None
        self.extra_args: list = []
        self.timeout = float(os.environ.get(self.ENV_TIMEOUT) or 900)
        self.chan: dict = {}

    # -- lớp con ghi đè --
    @staticmethod
    def tim_cli() -> Optional[str]:
        return None

    @staticmethod
    def lenh_cai() -> str:
        return ""

    def _chuan_bi(self, full: str) -> tuple:
        raise NotImplementedError

    def _doi_su_kien(self, ev: dict, gom: dict) -> list:
        return []

    def _cau_chua_dang_nhap(self, loi: str) -> str:
        return ""

    def _sau_luot(self, gom: dict) -> list:
        return []

    # -- chung --
    def is_available(self) -> bool:
        return self.cli_path is not None

    async def query(self, prompt: str) -> AsyncIterator[dict]:
        if not self.cli_path:
            yield {"type": "error",
                   "content": f"Chưa cài {self.TEN} trên máy này. Mở trang Models, bấm "
                              f"\"Cài đặt\" ở thẻ {self.TEN} rồi đăng nhập."}
            return
        full = (self.instructions.strip() + "\n\n" + prompt) if self.instructions else prompt
        try:
            args, dau_vao, env, don = self._chuan_bi(full)
        except Exception as e:
            yield {"type": "error", "content": f"{self.TEN}: không dựng được lệnh chạy ({e})."}
            return
        gom = {"manh": [], "final": "", "vot": [], "raw": [], "loai": set(), "so_dong": 0,
               "ma_thoat": None, "stderr": "", "args": cat_args(args), "loi": False}
        self.chan = gom
        loop = asyncio.get_running_loop()
        hang: asyncio.Queue = asyncio.Queue()
        HET = object()
        qua_gio = threading.Event()

        def doc_luong():
            proc, canh = None, None
            try:
                proc = subprocess.Popen(
                    args, stdin=subprocess.PIPE if dau_vao is not None else subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.cwd, text=True,
                    encoding="utf-8", errors="replace", bufsize=1, creationflags=_no_window(),
                    env=env, start_new_session=(os.name != "nt"))
                try:
                    import tien_trinh_nen
                    tien_trinh_nen.ghi_nhom(self.tag, proc.pid)
                except Exception:
                    pass
                if dau_vao is not None:
                    # Ghi stdin ở thread riêng: prompt dài hơn bộ đệm ống mà CLI chưa đọc thì
                    # ghi thẳng ở đây là kẹt cả hai bên (bài học `antigravity_cli._ghi_stdin`).
                    def _ghi():
                        try:
                            proc.stdin.write(dau_vao)
                            proc.stdin.close()
                        except Exception:
                            pass
                    threading.Thread(target=_ghi, daemon=True).start()

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
                err_buf: list = []

                def doc_err():
                    try:
                        for l in iter(proc.stderr.readline, ""):
                            if len(err_buf) < 400:
                                err_buf.append(l)
                    except Exception:
                        pass
                te = threading.Thread(target=doc_err, daemon=True)
                te.start()
                for line in iter(proc.stdout.readline, ""):
                    line = lam_sach(line).strip()
                    if not line:
                        continue
                    gom["so_dong"] += 1
                    if len(gom["raw"]) < 40:
                        gom["raw"].append(line[:1000])
                    try:
                        o = json.loads(line)
                        if not isinstance(o, dict):
                            o = {"_raw": line}
                    except json.JSONDecodeError:
                        o = {"_raw": line}
                    loop.call_soon_threadsafe(hang.put_nowait, o)
                ma = proc.wait()
                te.join(timeout=2)
                err = lam_sach("".join(err_buf)).strip()
                gom["ma_thoat"], gom["stderr"] = ma, err[-2000:]
                if qua_gio.is_set():
                    loop.call_soon_threadsafe(hang.put_nowait, {"_exit": -1, "_err": (
                        f"{self.TEN} chạy quá {int(self.timeout)} giây nên bị cắt. Việc thật sự "
                        f"dài thì nâng biến môi trường {self.ENV_TIMEOUT}.")})
                elif ma != 0:
                    loop.call_soon_threadsafe(hang.put_nowait, {"_exit": ma, "_err": err})
                elif err:
                    # Thoát 0 mà stderr có chữ: log/cảnh báo, không phải lỗi. Bỏ dòng ồn đã biết
                    # (vd Vibe luôn in "Reading API keys from the system keyring") cho nhật ký
                    # máy chủ khỏi đầy rác, giữ phần còn lại để còn lần ra khi cần.
                    con = "\n".join(x for x in err.splitlines()
                                    if not (self.STDERR_ON and re.search(self.STDERR_ON, x)))
                    if con.strip():
                        print(f"[{self.ID} stderr] {con[:1500]}", file=sys.stderr)
            except OSError as e:
                if getattr(e, "errno", None) in (errno.E2BIG, errno.ENAMETOOLONG):
                    t = (f"Hội thoại quá dài so với trần dòng lệnh của hệ điều hành. Mở một hội "
                         f"thoại mới, hoặc nâng cấp {self.TEN}.")
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
                for f in don or []:
                    try:
                        if os.path.isdir(f):
                            import shutil
                            shutil.rmtree(f, ignore_errors=True)
                        else:
                            os.unlink(f)
                    except Exception:
                        pass
                loop.call_soon_threadsafe(hang.put_nowait, HET)

        threading.Thread(target=doc_luong, name=f"minmin-{self.ID}-{self.tag}",
                         daemon=True).start()
        # File phụ cần đọc SAU lượt (vd export.json của Vibe) thì lớp con KHÔNG đưa vào `don`
        # mà tự đọc rồi tự dọn trong `_sau_luot` - `don` bị xoá ngay khi tiến trình thoát.
        while True:
            ev = await hang.get()
            if ev is HET:
                break
            if "_exit" in ev:
                gom["loi"] = True
                yield {"type": "error", "content": self._cau_loi(ev)}
                continue
            if "_raw" in ev:
                gom["manh_tho"] = gom.get("manh_tho", []) + [str(ev["_raw"])]
                continue
            t = str(ev.get("type") or "")
            if t and len(gom["loai"]) < 40:
                gom["loai"].add(t)
            for ra in self._doi_su_kien(ev, gom):
                if ra.get("type") == "error":
                    gom["loi"] = True
                yield ra
        for ra in self._sau_luot(gom):
            yield ra
        text = (gom.get("final") or "").strip() or "".join(gom["manh"]).strip()
        if not text:
            text = "\n".join(x for x in gom["vot"] if str(x).strip()).strip()
        if not text and gom.get("manh_tho"):
            # Không phải JSON: CLI in chữ thường (bản chưa có định dạng JSON). Giữ làm chữ,
            # KHÔNG trả bong bóng rỗng. Bỏ dòng cảnh báo hiển nhiên của CLI.
            text = "\n".join(x for x in gom["manh_tho"]
                             if not re.match(r"^(warning|warn|info|debug)\b[:\s]", x, re.I)).strip()
        if text:
            yield {"type": "final", "content": text}
        elif not gom["loi"]:
            yield {"type": "error", "content": self._loi_trong(gom)}

    def _cau_loi(self, ev: dict) -> str:
        loi = str(ev.get("_err") or "").strip()
        dn = self._cau_chua_dang_nhap(loi + "\n" + "\n".join(self.chan.get("raw") or []))
        if dn:
            return dn
        if not loi:
            loi = f"{self.TEN} thoát với mã {ev.get('_exit')}."
        return f"{self.TEN}: " + loi[-1500:]

    def _loi_trong(self, gom: dict) -> str:
        loai = sorted(x for x in gom.get("loai") or () if x)
        n = int(gom.get("so_dong") or 0)
        if not n:
            noi = (f"{self.TEN} chạy xong (mã thoát {gom.get('ma_thoat')}) nhưng không in ra gì "
                   "cả. Bấm \"Kiểm tra lại\" ở thẻ trên trang Models để xem chi tiết.")
        else:
            noi = (f"{self.TEN} in ra {n} dòng nhưng MinMin không nhận ra câu trả lời"
                   + (" (thấy: " + ", ".join(loai[:12]) + ")" if loai else "") + ".")
            raw = gom.get("raw") or []
            if raw:
                noi += "\nDòng cuối: " + raw[-1][:400]
        if gom.get("stderr"):
            noi += "\nCLI báo ở stderr: " + gom["stderr"][-300:]
        if gom.get("args"):
            noi += "\nCờ đã truyền: " + " ".join(gom["args"])
        return noi


def tep_tam(noi_dung: str, tien_to: str) -> Optional[str]:
    try:
        fd, p = tempfile.mkstemp(prefix=tien_to, suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(noi_dung)
        return p
    except Exception:
        return None


def kiem_tra_bang_luot(cls, timeout: float = 90.0) -> dict:
    """Chạy thử MỘT lượt thật ở mức suggest để trả lời DỨT KHOÁT "chat được chưa".

    File phiên còn nằm đó không có nghĩa là còn dùng được (token hết hạn, gói hết hạn) - chỉ
    chat thật một lượt mới biết. Chạy trong vòng sự kiện riêng vì nơi gọi là thread worker.
    """
    async def _mot():
        g = cls(cwd=str(_home_dir()), tag="kiem-tra")
        g.mode = "suggest"
        g.timeout = timeout
        if not g.is_available():
            return {"ok": False, "error": f"Chưa cài {cls.TEN}."}
        loi, chu = [], ""
        async for ev in g.query("Trả lời đúng một chữ: ok"):
            if ev.get("type") == "final":
                chu = ev.get("content") or ""
            elif ev.get("type") == "error":
                loi.append(str(ev.get("content") or ""))
        if chu:
            return {"ok": True, "reply": chu[:200]}
        return {"ok": False, "error": (loi[0] if loi else f"{cls.TEN} không trả lời.")[:600]}

    try:
        return asyncio.run(_mot())
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
