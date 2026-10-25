"""Gợi ý mã hàng (26.10.220): HTTP cho tiện ích trình duyệt của nhân viên và trang quản lý.

1. `/goi-y-ma/may/...` - CHO TIỆN ÍCH, miễn cổng đăng nhập; tự xác thực bằng header `x-minmin-may`
   (token máy), riêng đường ghép dùng mã 6 số. Chống dò như Concat.
     POST /goi-y-ma/may/ghep      {ma, ten, phien_ban} -> {may_id, token}
     GET  /goi-y-ma/may/bang      ba bảng gọn (sku, ad, post, bi_danh) để nạp sẵn trên máy
     POST /goi-y-ma/may/tra       {text, ad_id, post_id} -> ứng viên
     POST /goi-y-ma/may/anh       {anh: base64, mime} -> ứng viên theo ảnh (ChatGPT, có cache)
     POST /goi-y-ma/may/xac-nhan  {ma, nguon, khoa}: nhân viên chốt mã (nguon=anh thì khoa là hash ảnh)
2. `/goi-y-ma/api/...` - cho dashboard, cần đăng nhập.
     POST /goi-y-ma/api/ma-ghep, GET /goi-y-ma/api/thong-ke, GET /goi-y-ma/api/may,
     DELETE /goi-y-ma/api/may/{id}
"""
from __future__ import annotations

import json
import time
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import goi_y_anh
import goi_y_ma

TIEN_TO_MAY = "/goi-y-ma/may/"
THAN_TOI_DA = 100_000
_SAI: dict = {}
_SAI_TOI_DA = 20
_SAI_CUA_SO = 600


def _loi(msg, ma: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": str(msg)}, status_code=ma)


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _bi_chan(ip: str) -> bool:
    now = time.time()
    ds = [t for t in _SAI.get(ip, []) if now - t < _SAI_CUA_SO]
    _SAI[ip] = ds
    if len(_SAI) > 5000:
        _SAI.clear()
    return len(ds) >= _SAI_TOI_DA


def _ghi_sai(ip: str) -> None:
    _SAI.setdefault(ip, []).append(time.time())


def register(app: FastAPI) -> None:
    async def _may(request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return None, JSONResponse({"error": "sai token quá nhiều lần, thử lại sau 10 phút"}, status_code=429)
        m = goi_y_ma.may_theo_token(str(request.headers.get("x-minmin-may") or ""))
        if not m:
            _ghi_sai(ip)
            return None, JSONResponse({"error": "unauthorized", "goi_y_ma": "token máy sai hoặc máy đã bị gỡ"},
                                      status_code=401)
        return m, None

    async def _json(request: Request, toi_da: int = THAN_TOI_DA) -> dict:
        body = await request.body()
        if len(body) > toi_da:
            raise ValueError("thân yêu cầu quá lớn")
        try:
            raw = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("thân yêu cầu không phải JSON hợp lệ")
        if not isinstance(raw, dict):
            raise ValueError("JSON phải là object")
        return raw

    @app.post(TIEN_TO_MAY + "ghep")
    async def gy_ghep(request: Request):
        ip = _ip(request)
        if _bi_chan(ip):
            return _loi("sai mã quá nhiều lần, thử lại sau 10 phút", 429)
        try:
            d = await _json(request)
            kq = goi_y_ma.ghep(d.get("ma"), d.get("ten"), d.get("phien_ban") or "")
        except ValueError as e:
            _ghi_sai(ip)
            return _loi(e)
        return {"ok": True, **kq}

    @app.get(TIEN_TO_MAY + "bang")
    async def gy_bang(request: Request):
        m, err = await _may(request)
        if err:
            return err
        return {"ok": True, **goi_y_ma.xuat_bang()}

    @app.post(TIEN_TO_MAY + "tra")
    async def gy_tra(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
        except ValueError as e:
            return _loi(e)
        return {"ok": True, **goi_y_ma.phan_giai(str(d.get("text") or "")[:2000], str(d.get("ad_id") or ""),
                                                  str(d.get("post_id") or ""))}

    @app.post(TIEN_TO_MAY + "anh")
    async def gy_anh(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request, 9_000_000)
            import base64
            raw = base64.b64decode(str(d.get("anh") or "").split(",")[-1], validate=False)
        except (ValueError, TypeError) as e:
            return _loi(e)
        mime = str(d.get("mime") or "image/jpeg")
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            return _loi("chỉ nhận ảnh jpeg, png hoặc webp")
        kq = await goi_y_anh.tra_anh(raw, mime)
        return kq if kq.get("ok") else JSONResponse(kq, status_code=422 if kq.get("hash") else 400)

    @app.post(TIEN_TO_MAY + "xac-nhan")
    async def gy_xac_nhan(request: Request):
        m, err = await _may(request)
        if err:
            return err
        try:
            d = await _json(request)
        except ValueError as e:
            return _loi(e)
        if not goi_y_ma.chuan_ma(d.get("ma")):
            return _loi("thiếu mã hàng")
        goi_y_ma.xac_nhan(d.get("ma"), str(d.get("nguon") or ""), str(d.get("khoa") or ""))
        hoc = goi_y_anh.hoc_tu_xac_nhan(d.get("ma"), str(d.get("khoa") or "")) if d.get("nguon") == "anh" else False
        return {"ok": True, "da_hoc_anh": hoc}

    A = "/goi-y-ma/api"

    @app.post(A + "/ma-ghep")
    async def gy_ma_ghep():
        return {"ok": True, "ma": goi_y_ma.tao_ma_ghep(), "het_han_sau_giay": goi_y_ma.MA_SONG}

    @app.get(A + "/thong-ke")
    async def gy_thong_ke():
        return {"ok": True, **goi_y_ma.thong_ke(), **goi_y_anh.thong_ke()}

    @app.get(A + "/may")
    async def gy_ds_may():
        return {"ok": True, "may": goi_y_ma.ds_may()}

    @app.delete(A + "/may/{may_id}")
    async def gy_go_may(may_id: str):
        return {"ok": goi_y_ma.go_may(may_id)}
