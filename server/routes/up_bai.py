"""Up bài tự động từ Google Sheet (26.10.186) - lớp HTTP + vòng chạy nền. Lõi ở `up_bai.py`.

Cấu hình sống ở STATE_DIR/up-bai/cau-hinh.json: {sheet_id, bat, tu_duyet}. Khi `bat`, cứ 5 phút
MinMin đọc Sheet một lượt (xử lý dòng mới, đăng bài đến hạn). Nằm chung app Đội Social (cùng mã
kích hoạt), giao diện là một thẻ trong trang Đội Social.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import up_bai
import routes.doi_social as rds

NHIP_GIAY = 300
_THE: dict = {"up": None, "goc": None, "task": None}


def _tep(goc: Path) -> Path:
    return goc / "up-bai" / "cau-hinh.json"


def doc_cau_hinh() -> dict:
    goc = _THE["goc"]
    try:
        d = json.loads(_tep(goc).read_text("utf-8"))
    except Exception:
        d = {}
    return {"sheet_id": d.get("sheet_id") or "", "bat": bool(d.get("bat")), "tu_duyet": bool(d.get("tu_duyet"))}


def ghi_cau_hinh(d: dict) -> dict:
    p = _tep(_THE["goc"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    up = _THE["up"]
    if up:
        up.sheet_id, up.tu_duyet = d["sheet_id"], d["tu_duyet"]
    return d


def may() -> Optional[up_bai.UpBai]:
    return _THE["up"]


async def _vong():
    await asyncio.sleep(30)
    while True:
        try:
            cfg = doc_cau_hinh()
            up = _THE["up"]
            if cfg["bat"] and cfg["sheet_id"] and up and not rds.ly_do_chan():
                await up.chay_mot_vong()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[up-bai] vòng chạy lỗi: {type(e).__name__}: {e}", file=sys.stderr)
            if _THE["up"]:
                _THE["up"]._ghi(f"lỗi vòng chạy: {e}")
        await asyncio.sleep(NHIP_GIAY)


def register(app: FastAPI, deps: up_bai.Deps, state_dir: Path) -> None:
    _THE["goc"] = Path(state_dir)
    cfg = doc_cau_hinh()
    _THE["up"] = up_bai.UpBai(deps, cfg["sheet_id"], cfg["tu_duyet"])

    @app.on_event("startup")
    async def _bat_dau():
        _THE["task"] = asyncio.get_running_loop().create_task(_vong())

    @app.on_event("shutdown")
    async def _dung():
        t = _THE.get("task")
        if t:
            t.cancel()

    def _chan():
        ly = rds.ly_do_chan()
        return JSONResponse({"ok": False, "error": ly}, status_code=403) if ly else None

    @app.get("/up-bai/trang-thai")
    def ub_trang_thai():
        c = _chan()
        if c:
            return c
        up = _THE["up"]
        return {"ok": True, "cau_hinh": doc_cau_hinh(), "lan_cuoi": up.lan_cuoi if up else {},
                "nhat_ky": list(reversed(up.nhat_ky_vong[-30:])) if up else []}

    @app.post("/up-bai/kiem-tra")
    async def ub_kiem_tra(request: Request):
        c = _chan()
        if c:
            return c
        try:
            data = await request.json()
            sid = up_bai.id_sheet(str(data.get('sheet') or doc_cau_hinh()['sheet_id']))
            if not may():
                raise ValueError('Up bài chưa khởi động')
            return {'ok': True, **await may().kiem_tra(sid)}
        except ValueError as exc:
            return JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)
        except Exception:
            return JSONResponse({'ok': False, 'error': 'Chưa đọc được Google Sheet; kiểm tra kết nối Google Sheets'}, status_code=502)

    @app.post("/up-bai/cau-hinh")
    async def ub_cau_hinh(request: Request):
        c = _chan()
        if c:
            return c
        d = await request.json()
        cu = doc_cau_hinh()
        sid = up_bai.id_sheet(d.get("sheet", cu["sheet_id"])) if "sheet" in d else cu["sheet_id"]
        if "sheet" in d and d.get("sheet") and not sid:
            return JSONResponse({"ok": False, "error": "link Google Sheet không đúng"}, status_code=400)
        moi = {"sheet_id": sid, "bat": bool(d.get("bat", cu["bat"])), "tu_duyet": bool(d.get("tu_duyet", cu["tu_duyet"]))}
        return {"ok": True, "cau_hinh": ghi_cau_hinh(moi)}

    @app.post("/up-bai/chay")
    async def ub_chay(request: Request):
        c = _chan()
        if c:
            return c
        try:
            d = await request.json()
        except Exception:
            d = {}
        up = _THE["up"]
        try:
            kq = await up.chay_mot_vong(chi_dong=int(d["dong"]) if d.get("dong") else None)
        except Exception as e:
            return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, status_code=500)
        return {"ok": True, "ket_qua": kq}
