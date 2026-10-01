"""Zalo Forwarder chạy trên trình duyệt (26.10.4): app đầu tiên của mục Kết nối ngoài.

Phần lõi là mã Node của app desktop Zalo Forwarder (TrungKienHa, dùng zca-js), đặt ở
`apps/zalo-forwarder/`. MinMin chạy nó thành MỘT tiến trình con chỉ nghe 127.0.0.1 với token
ngẫu nhiên, rồi đứng trước làm cổng:

- `GET  /apps/zalo-forwarder/`                 giao diện (bản web của app desktop)
- `POST /apps/zalo-forwarder/api/rpc/{ham}`    gọi một hàm của app (danh sách hàm cố định)
- `GET  /apps/zalo-forwarder/api/events`       luồng sự kiện (QR, log, trạng thái chuyển tiếp)
- `POST /apps/zalo-forwarder/api/upload`       tải ảnh lên để đăng nhóm hàng loạt
- `GET  /apps/zalo-forwarder/api/trang-thai`   tiến trình nền có đang chạy không

Mọi đường đi qua `_auth_guard` (phải đăng nhập MinMin) VÀ phải qua cửa `_cho_phep`: đã nhập mã
kích hoạt mở app này, đã đồng ý Điều khoản chung và Phụ lục A (Zalo). Tiến trình nền chỉ được
bật sau khi qua cửa; MinMin khởi động lại thì nó tự bật lại nếu lúc trước đang chuyển tiếp.

Dữ liệu (phiên đăng nhập Zalo, cấu hình, ảnh tạm) ở `<STATE_DIR>/zalo-forwarder/`, không bao giờ
nằm trong thư mục mã nguồn.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import shutil
import sys
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

import giay_phep
import routes.ket_noi_ngoai as knn

APP_ID = "zalo_forwarder"
GOC = "/apps/zalo-forwarder"
APP_DIR = Path(__file__).resolve().parents[2] / "apps" / "zalo-forwarder"
WEB_DIR = APP_DIR / "web"
WEB_FILES = {"index.html", "renderer.js", "i18n.js", "styles.css", "web-api.js", "operations.js"}

# Đúng các hàm web-api.js gọi. Tên lạ bị chặn ở đây, không tới được tiến trình Node.
HAM = frozenset({
    "loadConfig", "saveConfig", "listAccounts", "loginQR", "connect", "deleteAccount", "setProxy",
    "listGroups", "listFriends", "getGroupLink", "sendTest",
    "startAll", "startAccount", "stopAccount", "pauseAccount", "resumeAccount", "stopAll", "forwardStatus",
    "aiTest", "aiCompose", "aiListModels", "aiChat", "previewRules", "broadcastSend",
})
# Đăng nhập QR chờ người quét; đăng nhóm hàng loạt nghỉ vài giây giữa mỗi nhóm.
HAM_LAU = {"loginQR": 600.0, "broadcastSend": 3 * 3600.0, "startAll": 300.0, "startAccount": 300.0}
GIOI_HAN_ANH = 20 * 1024 * 1024


def _thu_muc_du_lieu() -> Path:
    try:
        from config import STATE_DIR
    except Exception:  # pragma: no cover - chạy lẻ ngoài server
        STATE_DIR = Path(os.environ.get("JAVIS_STATE_DIR") or Path.home() / ".minmin")
    p = Path(STATE_DIR) / "zalo-forwarder"
    p.mkdir(parents=True, exist_ok=True)
    return p


def ly_do_chan() -> Optional[str]:
    """None = được dùng. Ngược lại là câu nói cho người dùng biết còn thiếu gì."""
    if not giay_phep.da_mo(APP_ID):
        return "Zalo Forwarder chưa được mở khoá. Vào Kết nối & Khách > Kết nối ngoài để nhập mã kích hoạt."
    if not knn.da_dong_y("chung"):
        return "Cần đồng ý Điều khoản sử dụng MinMin trước (trang Kết nối ngoài)."
    if not knn.da_dong_y("zalo"):
        return "Cần đồng ý Phụ lục A (tự động hoá Zalo) trước: bấm Mở ở thẻ Zalo Forwarder trong trang Kết nối ngoài."
    return None


class TienTrinh:
    """Một tiến trình Node duy nhất cho cả bản cài (mọi tài khoản Zalo chạy chung trong đó)."""

    def __init__(self) -> None:
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.port = 0
        self.token = ""
        self.loi_cuoi = ""
        self._khoa = asyncio.Lock()
        self._doc_log: Optional[asyncio.Task] = None

    def song(self) -> bool:
        return bool(self.proc and self.proc.returncode is None and self.port)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _hdr(self) -> dict:
        return {"x-zf-token": self.token}

    async def _cai_thu_vien(self) -> None:
        """Bản Docker đã cài sẵn lúc build. Bản cài thẳng trên máy thì cài lần đầu dùng."""
        if (APP_DIR / "node_modules" / "zca-js").is_dir():
            return
        npm = shutil.which("npm")
        if not npm:
            raise RuntimeError("Máy chưa có Node.js/npm nên chưa chạy được Zalo Forwarder.")
        if not os.access(APP_DIR, os.W_OK):
            raise RuntimeError("Thiếu thư viện của Zalo Forwarder và thư mục mã nguồn chỉ đọc. Hãy cập nhật MinMin lên bản mới.")
        p = await asyncio.create_subprocess_exec(
            npm, "ci", "--omit=dev", "--no-audit", "--no-fund", cwd=str(APP_DIR),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await asyncio.wait_for(p.communicate(), timeout=600)
        if p.returncode != 0:
            raise RuntimeError("Cài thư viện Zalo Forwarder lỗi: " + out.decode("utf-8", "replace")[-400:])

    async def dam_bao(self) -> None:
        if self.song():
            return
        async with self._khoa:
            if self.song():
                return
            node = shutil.which("node")
            if not node:
                raise RuntimeError("Máy chưa có Node.js nên chưa chạy được Zalo Forwarder.")
            await self._cai_thu_vien()
            data = _thu_muc_du_lieu()
            self.token = secrets.token_urlsafe(32)
            env = dict(os.environ, ZF_PORT="0", ZF_TOKEN=self.token, ZF_DATA=str(data))
            # stdin là ống: MinMin chết thì ống đóng, tiến trình Node tự tắt theo, không mồ côi.
            self.proc = await asyncio.create_subprocess_exec(
                node, "server.js", cwd=str(APP_DIR), env=env,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT, start_new_session=True)
            try:
                port = await asyncio.wait_for(self._doi_san_sang(), timeout=30)
            except Exception as e:
                await self.tat()
                self.loi_cuoi = f"Zalo Forwarder không khởi động được: {e}"
                raise RuntimeError(self.loi_cuoi)
            self.port = port
            self.loi_cuoi = ""
            self._doc_log = asyncio.create_task(self._ghi_log(data / "tien-trinh.log"))

    async def _doi_san_sang(self) -> int:
        assert self.proc and self.proc.stdout
        dong_cuoi = ""
        while True:
            raw = await self.proc.stdout.readline()
            if not raw:
                raise RuntimeError(dong_cuoi or "tiến trình thoát ngay")
            dong = raw.decode("utf-8", "replace").strip()
            m = re.match(r"^ZF_READY (\d+)$", dong)
            if m:
                return int(m.group(1))
            dong_cuoi = dong[-300:]

    async def _ghi_log(self, f: Path) -> None:
        """Đọc hết stdout để ống không đầy (đầy là Node treo). Giữ khoảng 1MB cuối."""
        try:
            while self.proc and self.proc.stdout:
                raw = await self.proc.stdout.readline()
                if not raw:
                    break
                try:
                    if f.exists() and f.stat().st_size > 1_000_000:
                        f.write_bytes(f.read_bytes()[-500_000:])
                    with f.open("ab") as h:
                        h.write(raw)
                except OSError:
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            self.port = 0

    async def tat(self) -> None:
        p, self.proc, self.port = self.proc, None, 0
        if self._doc_log:
            self._doc_log.cancel()
            self._doc_log = None
        if not p or p.returncode is not None:
            return
        try:
            p.terminate()
            await asyncio.wait_for(p.wait(), timeout=8)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

    async def rpc(self, ham: str, args: list) -> dict:
        await self.dam_bao()
        async with httpx.AsyncClient(timeout=httpx.Timeout(HAM_LAU.get(ham, 120.0), connect=5.0)) as c:
            r = await c.post(f"{self.base}/rpc/{ham}", headers=self._hdr(), json={"args": args})
        return r.json()


TT = TienTrinh()


def dang_chuyen_tiep_truoc_do() -> bool:
    try:
        d = json.loads((_thu_muc_du_lieu() / "dang-chay.json").read_text(encoding="utf-8"))
        return bool(d.get("running"))
    except Exception:
        return False


def _trang_khoa(ly_do: str) -> HTMLResponse:
    from html import escape
    return HTMLResponse(
        '<!doctype html><html lang="vi"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Zalo Forwarder</title>'
        '<style>body{font-family:system-ui,sans-serif;background:#0f1420;color:#e8ecf4;display:grid;'
        'place-items:center;min-height:100vh;margin:0;padding:16px}div{max-width:460px;background:#182033;'
        'border-radius:14px;padding:24px;line-height:1.55}a{color:#7cc4ff}</style></head><body><div>'
        f'<h2>Zalo Forwarder</h2><p>{escape(ly_do)}</p><p><a href="/">Về MinMin</a></p></div></body></html>',
        status_code=403)


def register(app: FastAPI) -> None:

    def _chan_json() -> Optional[JSONResponse]:
        ly_do = ly_do_chan()
        return JSONResponse({"ok": False, "error": ly_do}, status_code=403) if ly_do else None

    @app.get(GOC)
    def zf_goc():
        return RedirectResponse(GOC + "/", status_code=307)

    @app.get(GOC + "/")
    def zf_trang():
        ly_do = ly_do_chan()
        if ly_do:
            return _trang_khoa(ly_do)
        return FileResponse(str(WEB_DIR / "index.html"), headers={"Cache-Control": "no-cache"})

    @app.get(GOC + "/api/trang-thai")
    def zf_trang_thai():
        return {"ok": True, "cho_phep": ly_do_chan() is None, "ly_do": ly_do_chan(),
                "dang_chay": TT.song(), "loi": TT.loi_cuoi}

    @app.post(GOC + "/api/rpc/{ham}")
    async def zf_rpc(ham: str, request: Request):
        chan = _chan_json()
        if chan:
            return chan
        if ham not in HAM:
            return JSONResponse({"ok": False, "error": "Hàm không hợp lệ"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            body = {}
        args = body.get("args") if isinstance(body, dict) else None
        if not isinstance(args, list):
            args = []
        try:
            return await TT.rpc(ham, args)
        except httpx.TimeoutException:
            return JSONResponse({"ok": False, "error": "Zalo Forwarder phản hồi quá lâu"}, status_code=504)
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=502)

    @app.post(GOC + "/api/upload")
    async def zf_upload(request: Request, ten: str = ""):
        chan = _chan_json()
        if chan:
            return chan
        than = bytearray()
        async for khuc in request.stream():
            than.extend(khuc)
            if len(than) > GIOI_HAN_ANH:
                return JSONResponse({"ok": False, "error": "Ảnh quá lớn (tối đa 20MB)"}, status_code=413)
        try:
            await TT.dam_bao()
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(f"{TT.base}/upload", params={"ten": ten[:120]}, headers=TT._hdr(),
                                 content=bytes(than))
            return JSONResponse(r.json(), status_code=r.status_code)
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=502)

    @app.get(GOC + "/api/events")
    async def zf_events(request: Request):
        chan = _chan_json()
        if chan:
            return chan
        try:
            await TT.dam_bao()
        except Exception as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=502)
        base, hdr = TT.base, TT._hdr()

        async def chuyen():
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=5.0)) as c:
                    async with c.stream("GET", f"{base}/events", headers=hdr) as r:
                        async for khuc in r.aiter_raw():
                            if await request.is_disconnected():
                                break
                            yield khuc
            except (httpx.HTTPError, asyncio.CancelledError):
                return

        return StreamingResponse(chuyen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get(GOC + "/{ten}")
    def zf_tinh(ten: str):
        if ten not in WEB_FILES:
            return JSONResponse({"error": "not found"}, status_code=404)
        if ly_do_chan():
            return JSONResponse({"error": "locked"}, status_code=403)
        return FileResponse(str(WEB_DIR / ten), headers={"Cache-Control": "no-cache"})

    @app.on_event("startup")
    async def _zf_bat_lai():
        # Lúc trước đang chuyển tiếp (rồi MinMin cập nhật / khởi động lại) thì bật lại ngay,
        # không đợi ai mở trang. Chưa mở khoá thì thôi.
        if ly_do_chan() is None and dang_chuyen_tiep_truoc_do():
            async def _bat():
                try:
                    await TT.dam_bao()
                except Exception as e:
                    print(f"[zalo-forwarder] {e}", file=sys.stderr)
            asyncio.create_task(_bat())

    @app.on_event("shutdown")
    async def _zf_tat():
        await TT.tat()
