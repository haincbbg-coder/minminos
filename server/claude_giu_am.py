"""Lượt chat Claude Code chạy trên tiến trình `claude` được giữ ấm giữa các tin (26.10.313).

`ClaudeSDK.query` mở một ClaudeSDKClient mới mỗi lượt rồi đóng ở cuối, nên lượt nào cũng trả giá
khởi động CLI và nối lại mọi MCP trước khi model bắt đầu. Module này cắm vào ĐÚNG vòng đọc đó qua
một đối tượng `Luot` gắn vào engine (`cli.giu_am`): engine vẫn tự dựng options, tự canh các trần
watchdog, tự phát đúng những sự kiện như cũ. `Luot` chỉ quyết ba chỗ:

- trước khi dựng client: cuộc chat có tiến trình ấm khớp vân tay không (giu_am.HO);
- có thì engine KHÔNG connect lại mà gửi luôn tin nhắn;
- cuối lượt: lượt sạch (kết quả tốt, không còn việc nền nào của CLI đang chạy) thì trả tiến trình
  về hồ thay vì đóng.

Vân tay KHÔNG gồm system prompt: Claude Code nối phiên bằng --resume vốn đã giữ system prompt của
lượt đầu phiên (xem main._gio_luot_noi_mach), nên tiến trình ấm không đổi thứ model nhìn thấy.
Vân tay cũng KHÔNG gồm file đăng nhập: Claude Code tự ghi lại file đó sau mỗi lần chạy, đưa vào là
không lượt nào dùng lại được (Javis vấp ở 0.382, sửa ở 0.387). Đăng nhập/đăng xuất qua MinMin thì
main gọi `giu_am.HO.bo_loai("claude")`.

`query(cli, prompt, khoa)` rơi về `cli.query(prompt)` y như cũ khi lượt không đủ điều kiện.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from typing import AsyncIterator, Optional

import giu_am


class AmHong(Exception):
    """Tiến trình ấm từ chối tin nhắn trước khi lượt bắt đầu: chạy lại lượt đó bằng tiến trình mới."""


class TayClaude(giu_am.Tay):
    loai = "claude"

    def __init__(self, client=None):
        self.client = client
        self.cli = None          # engine của lượt đang chạy (đích của stderr)
        self.phan = None         # các phần vân tay lúc trả về hồ (để log đúng phần đổi khi trượt)
        self.chet = False

    def con_song(self) -> bool:
        if self.chet or self.client is None:
            return False
        try:
            proc = self.client._transport._process
            if proc is None or proc.returncode is not None:
                return False
            q = self.client._query
            task = getattr(q, "_read_task", None)
            return not getattr(q, "_closed", False) and not (task is not None and task.done())
        except Exception:  # noqa: BLE001 - SDK không có các trường đó: tin cờ của mình
            return True

    def yen(self) -> bool:
        """Không còn gì sót từ lượt trước. Client chỉ có MỘT dòng tin: thứ CLI ghi ra sau kết quả
        cuối (tin của một việc nền, một lượt nó tự mở) sẽ bị đọc như của lượt mới. Chỉ bỏ qua ghi
        chú hệ thống cuối lượt; còn thứ gì khác là tiến trình không ở trạng thái biết trước."""
        try:
            import anyio
            dong = self.client._query._message_receive
        except Exception:  # noqa: BLE001
            return True
        while True:
            try:
                m = dong.receive_nowait()
            except anyio.WouldBlock:
                return True
            except Exception:  # noqa: BLE001 - đã đóng hoặc hỏng: không dùng lại
                return False
            sub = str((m or {}).get("subtype") or "") if isinstance(m, dict) else ""
            if not (isinstance(m, dict) and m.get("type") == "system" and not sub.startswith("task_")):
                return False

    async def dong(self) -> None:
        self.chet = True
        if self.client is None:
            return
        try:
            await self.client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    def on_stderr(self, line):
        cli = self.cli
        if cli is not None:
            cli._on_stderr(line)


def du_dieu_kien(cli) -> bool:
    """Chỉ engine chat của chủ trên dashboard: engine SDK, không rào allowlist (việc nền), không
    trần wall-clock, không server in-process bổ sung, không rào đường ghi."""
    if giu_am.ngan_sach_mb() <= 0:
        return False
    if type(cli).__name__ != "ClaudeSDK":
        return False
    if (cli.allowed_tools or cli.max_wall_s or getattr(cli, "sdk_servers", None)
            or getattr(cli, "duong_cam_ghi", None) or getattr(cli, "setting_sources", None) is not None):
        return False
    return str(cli.tag or "").startswith("chat:")


def _stat(p) -> str:
    try:
        st = os.stat(p)
        return f"{st.st_size}:{st.st_mtime_ns}"
    except OSError:
        return "-"


def _stat_skill(goc: str) -> str:
    """Mọi SKILL.md trong thư mục skill mirror: sửa một skill là đổi file, không đổi thư mục."""
    out = [_stat(goc)]
    try:
        for e in sorted(os.scandir(goc), key=lambda e: e.name):
            if e.is_dir():
                out.append(e.name + "=" + _stat(os.path.join(e.path, "SKILL.md")))
    except OSError:
        pass
    return hashlib.sha256("|".join(out).encode("utf-8")).hexdigest()


def _bam(phan: dict) -> str:
    return hashlib.sha256(json.dumps(phan, default=str, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def phan_doi(cu: dict, moi: dict) -> list:
    """Tên các phần vân tay khác nhau, cho đúng một dòng log khi trượt tiến trình ấm."""
    return sorted(k for k in set(cu) | set(moi) if cu.get(k) != moi.get(k))


def cac_phan_van_tay(cli, opts) -> dict:
    """Những gì quyết định tiến trình ấm còn hợp với lượt này. Mạch được nối (resume) cũng nằm trong."""
    may_chu = {}
    raw = getattr(opts, "mcp_servers", None)
    if isinstance(raw, dict):
        for ten, conf in raw.items():
            if isinstance(conf, dict) and conf.get("type") == "sdk":
                may_chu[ten] = "sdk"
            elif isinstance(conf, dict):
                may_chu[ten] = conf
            else:
                may_chu[ten] = str(conf)
    else:
        may_chu = str(raw)
    try:
        import plugins_host
        plugin = repr(plugins_host._signature(cli.javis_vault, scope_vault=False))
    except Exception:  # noqa: BLE001
        plugin = ""
    env = getattr(opts, "env", None) or {}
    auth = sorted((k, v) for k, v in env.items() if str(k).startswith(("ANTHROPIC_", "CLAUDE_")))
    cli_path = getattr(opts, "cli_path", None) or ""
    sp = getattr(opts, "system_prompt", None)
    cwd = str(getattr(opts, "cwd", "") or "")
    conf_dir = env.get("CLAUDE_CONFIG_DIR") or os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return {
        "cli": [str(cli_path), _stat(cli_path) if cli_path else ""], "cwd": cwd,
        "model": getattr(opts, "model", None), "effort": getattr(opts, "effort", None),
        "settings": str(getattr(opts, "settings", None)),
        "permission_mode": getattr(opts, "permission_mode", None),
        "setting_sources": list(getattr(opts, "setting_sources", None) or []),
        "disallowed_tools": list(getattr(opts, "disallowed_tools", None) or []),
        "co_stream": [bool(getattr(opts, "include_partial_messages", False)),
                      bool(getattr(opts, "include_hook_events", False))],
        "kieu_prompt": sp.get("type") if isinstance(sp, dict) else ("raw" if sp else ""),
        "mcp": may_chu, "strict_mcp": bool(getattr(opts, "strict_mcp_config", False)),
        "plugin": plugin, "auth_env": hashlib.sha256(json.dumps(auth).encode()).hexdigest(),
        "muc": cli.javis_mode, "brain": str(cli.javis_vault or ""),
        "resume": str(getattr(opts, "resume", None) or ""),
        # Claude Code chỉ đọc mấy thứ này lúc khởi động: thêm skill, sửa CLAUDE.md là cần tiến trình mới.
        "claude_md": _stat(os.path.join(cwd, "CLAUDE.md")),
        "skill": _stat_skill(os.path.join(cwd, ".claude", "skills")),
        "mcp_json": _stat(os.path.join(cwd, ".mcp.json")),
        "settings_du_an": [_stat(os.path.join(cwd, ".claude", "settings.json")),
                           _stat(os.path.join(cwd, ".claude", "settings.local.json"))],
        "settings_may": _stat(os.path.join(conf_dir, "settings.json")),
        "mcp_hub": _stat(may_chu) if isinstance(may_chu, str) and os.path.isfile(may_chu) else "",
    }


def _cong_thuc(cli, opts, sysprompt: Optional[str]):
    """Mở lại đúng tiến trình này sau (hâm nóng), nối vào mạch nó kết thúc. File system prompt của
    lượt đã bị dọn lúc đó, nên ghi lại cho lần khởi động rồi xoá ngay sau."""
    async def _mo_lai() -> TayClaude:
        from claude_agent_sdk import ClaudeSDKClient
        o = copy.copy(opts)
        tam = None
        extra = dict(getattr(o, "extra_args", None) or {})
        if "append-system-prompt-file" in extra and sysprompt is not None:
            tam = cli._write_sysprompt_file(sysprompt)
            cli._tmp_files = [p for p in cli._tmp_files if p != tam]   # tự xoá ở dưới
            extra["append-system-prompt-file"] = tam
            o.extra_args = extra
        tay = TayClaude()
        if getattr(o, "stderr", None) is not None:
            o.stderr = tay.on_stderr
        try:
            tay.client = ClaudeSDKClient(options=o)
            await tay.client.connect()
            return tay
        except BaseException:
            await tay.dong()
            raise
        finally:
            if tam:
                try:
                    os.unlink(tam)
                except OSError:
                    pass
    return _mo_lai


class Luot:
    """Một lượt chat, do `ClaudeSDK.query` gọi ở ba chỗ: `chuan_bi`, `client`, `xong`."""

    def __init__(self, khoa: str, cho_phep_am: bool = True):
        self.khoa = khoa
        self.cho_phep_am = cho_phep_am
        self.cho: Optional[giu_am.Cho] = None
        self.tay: Optional[TayClaude] = None
        self.opts = None
        self.sysprompt = None
        self.am = False            # lượt này chạy trên tiến trình ấm có sẵn

    def chuan_bi(self, cli, opts):
        """Engine vừa dựng options. Tìm tiến trình ấm khớp; đổi stderr sang tay để lượt sau vẫn
        ghi đúng engine. Trả options (có thể đã sửa)."""
        self.opts = opts
        self.sysprompt = cli.system_prompt if not cli.system_prompt_raw else None
        phan = cac_phan_van_tay(cli, opts)
        van_tay = _bam(phan)
        if cli.session_id and self.cho_phep_am:
            dang = giu_am.HO.nhin(self.khoa)
            if dang is not None and dang.van_tay != van_tay and getattr(dang.tay, "phan", None):
                print(f"[giữ ấm] {self.khoa[:12]}: cấu hình đổi ({', '.join(phan_doi(dang.tay.phan, phan))}),"
                      f" mở tiến trình mới", file=sys.stderr)
            cho = giu_am.HO.lay(self.khoa, "claude", van_tay)
            if cho is not None and not cho.tay.yen():
                giu_am.HO.tra(cho, giu=False)
                cho = None
            if cho is not None:
                self.cho = cho
                self.tay = cho.tay
                self.am = True
                cli._cleanup_tmp()   # file prompt của lượt này thừa: tiến trình đã chạy sẵn
        if self.tay is None:
            self.tay = TayClaude()
        self.tay.cli = cli
        if getattr(opts, "stderr", None) is not None:
            opts.stderr = self.tay.on_stderr
        return opts

    def client(self, options):
        """Client ấm có sẵn, hoặc None để engine tự dựng client mới như cũ."""
        return self.tay.client if self.am else None

    def ghi_client(self, client) -> None:
        if not self.am and self.tay is not None:
            self.tay.client = client

    def xong(self, cli, client, sach: bool) -> bool:
        """Hết lượt. True = Luot đã lo client (giữ lại hoặc hẹn đóng), engine KHÔNG disconnect nữa."""
        tay = self.tay
        if tay is None:
            return False
        tay.cli = None
        try:
            if not sach:
                if self.cho is not None:
                    giu_am.HO.tra(self.cho, giu=False)
                    return True
                return False
            self.opts.resume = cli.session_id
            phan = cac_phan_van_tay(cli, self.opts)
            van_tay = _bam(phan)
            tay.phan = phan
            ct = _cong_thuc(cli, self.opts, self.sysprompt)
            if self.cho is not None:
                self.cho.cong_thuc = ct     # lần hâm nóng sau nối vào mạch này
                giu_am.HO.tra(self.cho, van_tay=van_tay)
                return True
            moi = giu_am.HO.nhan(self.khoa, "claude", van_tay, tay, cong_thuc=ct)
            if moi is None:
                return False
            giu_am.HO.tra(moi)
            return True
        except Exception as e:  # noqa: BLE001 - lỗi ở đây chỉ được làm mất phần giữ ấm
            print(f"[giữ ấm] trả tiến trình lỗi {type(e).__name__}: {e}", file=sys.stderr)
            if self.cho is not None:
                giu_am.HO.tra(self.cho, giu=False)
                return True
            return False


async def query(cli, prompt, khoa: str) -> AsyncIterator[dict]:
    """Một lượt chat trên tiến trình ấm của cuộc chat nếu có cái khớp, không thì lạnh, rồi giữ tiến
    trình lại khi hồ còn chỗ. Cùng sự kiện như `ClaudeSDK.query`."""
    if not khoa or not du_dieu_kien(cli):
        async for ev in cli.query(prompt):
            yield ev
        return
    cli.giu_am = Luot(khoa)
    try:
        async for ev in cli.query(prompt):
            yield ev
    except AmHong as e:
        print(f"[giữ ấm] tiến trình ấm hỏng trước khi bắt đầu lượt ({e}), chạy lạnh", file=sys.stderr)
        cli.giu_am = Luot(khoa, cho_phep_am=False)
        async for ev in cli.query(prompt):
            yield ev
    finally:
        cli.giu_am = None
