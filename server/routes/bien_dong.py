"""Biến động số dư: Casso đẩy giao dịch ngân hàng vào đây, MinMin báo chủ và nhân viên.

Đường đi: Techcombank -> Casso Flow -> Webhook V2 -> POST /bien-dong/casso/<token> ở đây
-> lưu (server/bien_dong.py) -> báo chuông + thông báo đẩy + Telegram chủ, rồi các nơi nhận thêm.

- `POST /bien-dong/casso/{token}` CÔNG KHAI với hàng rào đăng nhập (Casso không có cookie).
  Miễn hẹp nhất có thể: đúng POST, đúng một đoạn mã 20-80 ký tự (xem `LOI_VAO_CONG_KHAI` và
  `_auth_guard` trong main.py). Bảo vệ ba lớp: mã trong đường (so thời gian hằng, sai thì 404
  và tính vào giới hạn sai theo IP), trần thân 64KB, và chữ ký HMAC-SHA512 của Casso BẮT BUỘC.
  Trả {"success": true} ngay, báo tin chạy nền: Casso đòi trả lời trong 5 giây.
- Cần đăng nhập: `GET /bien-dong` (trang), `GET /bien-dong/giao-dich`, `GET|POST
  /bien-dong/cai-dat`, `POST /bien-dong/doi-token`, `POST /bien-dong/thu`.
"""
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse

import bien_dong

# (mẫu đường, phương thức) được miễn cổng đăng nhập. main._auth_guard đọc hằng này.
LOI_VAO_CONG_KHAI = (r"/bien-dong/casso/[A-Za-z0-9_-]{20,80}", "POST")
THAN_TOI_DA = 64 * 1024
_SAI = {}                        # ip -> [mốc các lần sai mã] (chống dò mã)
_SAI_TOI_DA = 20
_SAI_CUA_SO = 600


@dataclass
class BienDongDeps:
    dashboard_dir: Path
    # Báo chủ (hòm thư + thông báo đẩy + Telegram). main.py nối vào _notify_owner.
    bao_chu: Optional[Callable[[str], Awaitable]] = None
    # Gửi tới MỘT nơi nhận thêm (chat id Telegram hoặc "zalo:<id>"). main.py nối vào _gui_qua_kenh.
    gui_kenh: Optional[Callable[[str, str], Awaitable]] = None
    # Danh sách chat id Telegram được phép (whitelist của bot), để kiểm nơi nhận thêm.
    ds_telegram: Optional[Callable[[], list]] = None
    # Danh sách chat id được phép của bot Zalo (rỗng = bot nhận mọi id).
    ds_zalo: Optional[Callable[[], list]] = None


_DEPS: Optional[BienDongDeps] = None
_VIEC_BAO = set()   # giữ tham chiếu task báo tin cho tới khi xong


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _bi_chan(ip: str) -> bool:
    now = time.time()
    ds = [t for t in _SAI.get(ip, []) if now - t < _SAI_CUA_SO]
    _SAI[ip] = ds
    if len(_SAI) > 5000:
        _SAI.clear()
    return len(ds) >= _SAI_TOI_DA


async def bao_tin(text: str) -> None:
    """Báo chủ rồi từng nơi nhận thêm. Lỗi chỉ ghi log, một nơi hỏng không chặn nơi khác."""
    deps = _DEPS
    if not deps or not text:
        return
    if deps.bao_chu:
        try:
            await deps.bao_chu(text)
        except Exception as ex:
            print(f"[bien-dong] báo chủ lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)
    if deps.gui_kenh:
        for dich in bien_dong.noi_nhan_them():
            try:
                kq = await deps.gui_kenh(dich, text)
                if isinstance(kq, tuple) and kq and not kq[0]:
                    print(f"[bien-dong] gửi {dich} lỗi: {kq[1] if len(kq) > 1 else ''}", file=sys.stderr)
            except Exception as ex:
                print(f"[bien-dong] gửi {dich} lỗi: {type(ex).__name__}: {ex}", file=sys.stderr)


def _len_lich(text: str) -> None:
    # KHÔNG chờ: Casso đợi trả lời tối đa 5 giây, gửi Telegram/Zalo chậm cỡ nào cũng không
    # được giữ chân nó. Giao dịch đã lưu xong trước khi tới đây.
    t = asyncio.create_task(bao_tin(text))
    _VIEC_BAO.add(t)
    t.add_done_callback(_VIEC_BAO.discard)


async def _doc_than(request: Request) -> Optional[bytes]:
    """Đọc thân có trần. Vượt trần trả None (không đọc hết thân khổng lồ vào bộ nhớ)."""
    try:
        if int(request.headers.get("content-length") or 0) > THAN_TOI_DA:
            return None
    except ValueError:
        return None
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > THAN_TOI_DA:
            return None
    return bytes(buf)


def _ds(ten: str) -> list:
    ham = getattr(_DEPS, ten, None) if _DEPS else None
    try:
        return list(ham() if ham else [])
    except Exception:
        return []


def register(app: FastAPI, deps: BienDongDeps) -> None:
    global _DEPS
    _DEPS = deps
    index = deps.dashboard_dir / "bien-dong" / "index.html"

    @app.get("/bien-dong")
    def bien_dong_page():
        return FileResponse(str(index), media_type="text/html",
                            headers={"Cache-Control": "no-cache"})

    @app.post("/bien-dong/casso/{token}")
    async def bien_dong_casso(token: str, request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return JSONResponse({"success": False, "error": "sai quá nhiều lần, thử lại sau 10 phút"},
                                status_code=429)
        if not bien_dong.token_dung(token):
            _SAI.setdefault(ip, []).append(time.time())
            return JSONResponse({"success": False, "error": "not found"}, status_code=404)
        body = await _doc_than(request)
        if body is None:
            return JSONResponse({"success": False, "error": "thân yêu cầu quá lớn"}, status_code=413)
        try:
            raw = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            return JSONResponse({"success": False, "error": "JSON hỏng"}, status_code=400)
        khoa = bien_dong.lay_khoa()
        if not khoa:
            return JSONResponse({"success": False, "error": "MinMin chưa có Key bảo mật của Casso"},
                                status_code=401)
        chu_ky = str(request.headers.get("x-casso-signature") or "")
        if not (isinstance(raw, dict) and bien_dong.xac_thuc_chu_ky(chu_ky, raw, khoa)
                and bien_dong.chu_ky_con_han(chu_ky)):
            return JSONResponse({"success": False, "error": "chữ ký không hợp lệ"}, status_code=401)
        try:
            _trang_thai, cau = bien_dong.nhan(raw)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        if cau:
            _len_lich(cau)
        return {"success": True}

    @app.get("/bien-dong/giao-dich")
    def bien_dong_giao_dich(limit: int = Query(100), chi_vao: bool = Query(False),
                            tu_ngay: str = Query(None), den_ngay: str = Query(None),
                            tim: str = Query(None)):
        try:
            ds = bien_dong.danh_sach(limit=limit, chi_vao=chi_vao, tu_ngay=tu_ngay,
                                     den_ngay=den_ngay, tim=tim or "")
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return {"giao_dich": ds, "so": len(ds), "hom_nay": bien_dong.tong_hom_nay()}

    @app.get("/bien-dong/cai-dat")
    def bien_dong_cai_dat():
        return bien_dong.cai_dat_cong_khai()

    @app.post("/bien-dong/cai-dat")
    async def bien_dong_luu_cai_dat(request: Request):
        try:
            patch = await request.json()
        except Exception:
            return JSONResponse({"error": "JSON hỏng"}, status_code=400)
        try:
            return {"ok": True, **bien_dong.luu_cai_dat(patch, _ds("ds_telegram"), _ds("ds_zalo"))}
        except ValueError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

    @app.post("/bien-dong/doi-token")
    def bien_dong_doi_token():
        bien_dong.tao_token()
        return {"ok": True, "duong_dan": bien_dong.duong_dan(),
                "luu_y": "Địa chỉ cũ đã hết hiệu lực. Dán địa chỉ mới vào Casso."}

    @app.post("/bien-dong/thu")
    async def bien_dong_thu():
        # Cùng đường báo với giao dịch thật, nhưng không ghi vào danh sách giao dịch.
        gd = bien_dong.chuan_hoa(bien_dong.mau_thu()["data"])
        await bao_tin(bien_dong.cau_bao(gd))
        return {"ok": True, "noi_nhan_them": len(bien_dong.noi_nhan_them())}
