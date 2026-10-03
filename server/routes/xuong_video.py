"""Xưởng video (26.10.63): app của mục Kết nối ngoài, sản xuất video hàng loạt rồi đăng lên mạng.

Giao diện tĩnh ở `/apps/xuong-video/`, API ở `/apps/xuong-video/api/...`. Mọi thứ khoá sau mã
kích hoạt (`giay_phep`) và điều khoản chung, y như `routes/hoa_don.py`. Việc nặng nằm ở package
`xuong_video` (kho, nhà cung cấp, kịch bản, ghép, đăng, chạy); file này chỉ là lớp HTTP mỏng.
"""
from __future__ import annotations

import asyncio
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

import giay_phep
import routes.ket_noi_ngoai as knn
from xuong_video import chay, dang, ghep, kho, khoa

APP_ID = "xuong_video"
GOC = "/apps/xuong-video"
WEB_DIR = Path(__file__).resolve().parents[2] / "apps" / "xuong-video" / "web"
WEB_FILES = {"index.html", "app.js", "styles.css"}
TOI_DA_LO = 30
TRUONG_SUA = ("ten", "y_tuong", "nen_tang", "ti_le", "thoi_luong_giay", "phong_cach", "ngon_ngu",
              "che_do_dang", "dang_luc")

_viec: set = set()
_state_oauth: dict = {}
_dung = asyncio.Event()


def ly_do_chan() -> Optional[str]:
    if not giay_phep.da_mo(APP_ID):
        return "Xưởng video chưa được mở khoá. Vào Kết nối & Khách > Kết nối ngoài để nhập mã kích hoạt."
    if not knn.da_dong_y("chung"):
        return "Cần đồng ý Điều khoản sử dụng MinMin trước (trang Kết nối ngoài)."
    return None


def _chan() -> Optional[JSONResponse]:
    ly = ly_do_chan()
    return JSONResponse({"ok": False, "error": ly}, status_code=403) if ly else None


def _loi(msg, ma: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": str(msg)}, status_code=ma)


def _trang_khoa(ly: str) -> HTMLResponse:
    import html
    return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                        f"<body style='font-family:system-ui;max-width:560px;margin:15vh auto;padding:0 20px'>"
                        f"<h2>Xưởng video</h2><p>{html.escape(ly)}</p></body>", status_code=403)


def _giu(coro) -> None:
    t = asyncio.ensure_future(coro)
    _viec.add(t)
    t.add_done_callback(_viec.discard)


def _thong_bao(tieu_de: str, noi_dung: str = "") -> None:
    try:
        import inbox
        inbox.add(noi_dung or tieu_de, kind="system", title=tieu_de, source="xuong_video", label="Xưởng video")
    except Exception:
        pass


def _redirect(request: Request) -> str:
    return str(request.base_url).rstrip("/") + GOC + "/api/youtube/callback"


def register(app: FastAPI, ask: Callable[[str, str, List[str]], Awaitable[str]],
             chep: Callable[[str, List[Path]], List[str]]) -> None:
    """`ask` và `chep` do main.py đưa vào (engine của MinMin, chép file vào brain)."""
    A = GOC + "/api"

    @app.get(GOC)
    def xv_goc():
        return RedirectResponse(GOC + "/", status_code=307)

    @app.get(GOC + "/")
    def xv_trang():
        ly = ly_do_chan()
        if ly:
            return _trang_khoa(ly)
        return FileResponse(str(WEB_DIR / "index.html"), headers={"Cache-Control": "no-cache"})

    @app.get(GOC + "/{ten}")
    def xv_tinh(ten: str):
        if ten not in WEB_FILES or ten == "index.html":
            return _loi("Không có tệp này.", 404)
        if ly_do_chan():
            return _loi(ly_do_chan(), 403)
        return FileResponse(str(WEB_DIR / ten), headers={"Cache-Control": "no-cache"})

    # ---------------- trạng thái, khoá, cài đặt
    @app.get(A + "/trang-thai")
    def xv_trang_thai():
        if (c := _chan()):
            return c
        return {"ok": True, "ffmpeg": bool(shutil.which("ffmpeg")), "khoa": khoa.tinh_trang(),
                "cai_dat": khoa.cai_dat(), "hom_nay": chay.da_dung_hom_nay(), "ho_tro": dang.HO_TRO,
                "ly_do_chua": dang.LY_DO_CHUA}

    @app.post(A + "/khoa/{dv}")
    async def xv_khoa(dv: str, request: Request):
        if (c := _chan()):
            return c
        if dv not in khoa.DICH_VU:
            return _loi("Dịch vụ không hợp lệ.")
        try:
            body = await request.json()
        except Exception:
            return _loi("Dữ liệu không đúng.")
        khoa.dat(dv, {k: str(v) for k, v in (body or {}).items() if k in khoa.DICH_VU[dv]["truong"] and str(v).strip()})
        return {"ok": True, "khoa": khoa.tinh_trang()}

    @app.delete(A + "/khoa/{dv}")
    def xv_khoa_xoa(dv: str):
        if (c := _chan()):
            return c
        if dv not in khoa.DICH_VU:
            return _loi("Dịch vụ không hợp lệ.")
        khoa.xoa(dv)
        return {"ok": True, "khoa": khoa.tinh_trang()}

    @app.post(A + "/cai-dat")
    async def xv_cai_dat(request: Request):
        if (c := _chan()):
            return c
        try:
            return {"ok": True, "cai_dat": khoa.luu_cai_dat(await request.json())}
        except Exception:
            return _loi("Dữ liệu không đúng.")

    # ---------------- YouTube OAuth
    @app.get(A + "/youtube/ket-noi")
    def xv_yt_ket_noi(request: Request):
        if (c := _chan()):
            return c
        st = secrets.token_urlsafe(16)
        _state_oauth[st] = time.time()
        for k in [k for k, t in _state_oauth.items() if time.time() - t > 900]:
            _state_oauth.pop(k, None)
        try:
            return {"ok": True, "url": dang.youtube_auth_url(_redirect(request), st), "redirect_uri": _redirect(request)}
        except dang.LoiDang as e:
            return _loi(e)

    @app.get(A + "/youtube/callback")
    async def xv_yt_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        if (c := _chan()):
            return c
        if error or state not in _state_oauth:
            return HTMLResponse("<meta charset=utf-8><p>Kết nối YouTube không thành công hoặc đã quá hạn. Đóng tab và thử lại.</p>", 400)
        _state_oauth.pop(state, None)
        try:
            await dang.youtube_doi_code(code, _redirect(request))
        except dang.LoiDang as e:
            import html
            return HTMLResponse(f"<meta charset=utf-8><p>{html.escape(str(e))}</p>", 400)
        return HTMLResponse("<meta charset=utf-8><p>Đã kết nối YouTube. Đóng tab này và quay lại Xưởng video.</p>")

    # ---------------- dự án
    @app.get(A + "/du-an")
    def xv_ds():
        if (c := _chan()):
            return c
        return {"ok": True, "du_an": kho.liet_ke(), "dang_chay": [t["id"] for t in kho.liet_ke() if chay.dang_chay(t["id"])]}

    def _tao(d: dict) -> str:
        return kho.tao(d)

    @app.post(A + "/du-an")
    async def xv_tao(request: Request):
        if (c := _chan()):
            return c
        try:
            body = await request.json()
        except Exception:
            return _loi("Dữ liệu không đúng.")
        if not str(body.get("y_tuong") or "").strip():
            return _loi("Cần nhập ý tưởng.")
        return {"ok": True, "id": _tao(body)}

    @app.get(A + "/du-an/{pid}")
    def xv_xem(pid: str):
        if (c := _chan()):
            return c
        p = kho.doc(pid)
        if not p:
            return _loi("Không có dự án này.", 404)
        p["dang_chay"] = chay.dang_chay(p["id"])
        return {"ok": True, "du_an": p}

    @app.delete(A + "/du-an/{pid}")
    def xv_xoa(pid: str):
        if (c := _chan()):
            return c
        if chay.dang_chay(pid):
            return _loi("Dự án đang chạy, chờ xong rồi xoá.", 409)
        return {"ok": kho.xoa(pid)}

    @app.patch(A + "/du-an/{pid}")
    async def xv_sua(pid: str, request: Request):
        if (c := _chan()):
            return c
        p = kho.doc(pid)
        if not p:
            return _loi("Không có dự án này.", 404)
        try:
            body = await request.json()
        except Exception:
            return _loi("Dữ liệu không đúng.")
        kw = {}
        for k in TRUONG_SUA:
            if k in body:
                kw[k] = body[k]
        if "nen_tang" in kw:
            kw["nen_tang"] = [x for x in (kw["nen_tang"] or []) if x in kho.NEN_TANG]
        if "ti_le" in kw and kw["ti_le"] not in kho.TI_LE:
            kw.pop("ti_le")
        if "che_do_dang" in kw:
            kw["che_do_dang"] = "tu_dong" if kw["che_do_dang"] == "tu_dong" else "duyet"
        if "dang_luc" in kw:
            try:
                kw["dang_luc"] = float(kw["dang_luc"] or 0)
            except (TypeError, ValueError):
                kw.pop("dang_luc")
        for k in ("ten", "y_tuong", "phong_cach", "ngon_ngu"):
            if k in kw:
                kw[k] = str(kw[k] or "").strip()[:8000 if k == "y_tuong" else 400]
        if "thoi_luong_giay" in kw:
            try:
                kw["thoi_luong_giay"] = max(8, min(int(kw["thoi_luong_giay"]), 180))
            except (TypeError, ValueError):
                kw.pop("thoi_luong_giay")
        for c_ in body.get("canh") or []:
            try:
                stt = int(c_.get("stt"))
            except (TypeError, ValueError):
                continue
            sua = {k: str(c_[k])[:900] for k in ("loi_thoai", "mo_ta_hinh", "chuyen_dong") if k in c_}
            if c_.get("tao_lai"):
                sua.update(anh="", video="", giong="", trang_thai="cho", loi="")
            if sua:
                kho.cap_nhat_canh(pid, stt, **sua)
        if kw:
            kho.cap_nhat(pid, **kw)
        return {"ok": True}

    @app.post(A + "/du-an/{pid}/tai-lieu")
    async def xv_tai_lieu(pid: str, request: Request, ten: str = "tep"):
        """Nhận THÔ (body là bytes của tệp, tên ở query) để khỏi phụ thuộc multipart."""
        if (c := _chan()):
            return c
        data = await request.body()
        rel, loi = kho.them_tai_lieu(pid, ten, data)
        return _loi(loi) if loi else {"ok": True, "rel": rel}

    @app.get(A + "/du-an/{pid}/tep")
    def xv_tep(pid: str, rel: str):
        if (c := _chan()):
            return c
        f = kho.duong_dan_file(pid, rel)
        if not f:
            return _loi("Không thấy tệp.", 404)
        return FileResponse(str(f))

    def _bat_dau(pid: str):
        _giu(chay.san_xuat(pid, ask, chep, _thong_bao))

    @app.post(A + "/du-an/{pid}/chay")
    def xv_chay(pid: str):
        if (c := _chan()):
            return c
        if not kho.doc(pid):
            return _loi("Không có dự án này.", 404)
        if chay.dang_chay(pid):
            return _loi("Dự án đang chạy rồi.", 409)
        if not shutil.which("ffmpeg"):
            return _loi("Máy chủ chưa cài ffmpeg nên không ghép được video.", 400)
        _bat_dau(pid)
        return {"ok": True}

    @app.post(A + "/du-an/{pid}/duyet")
    async def xv_duyet(pid: str, request: Request):
        """Duyệt: đồng ý đăng. Mặc định đăng ngay; có `dang_luc` thì đăng đúng giờ đó."""
        if (c := _chan()):
            return c
        p = kho.doc(pid)
        if not p or p.get("trang_thai") not in ("san_sang", "da_dang"):
            return _loi("Dự án chưa có video sẵn sàng để đăng.", 400)
        try:
            body = await request.json()
        except Exception:
            body = {}
        try:
            luc = float(body.get("dang_luc") or 0) or time.time()
        except (TypeError, ValueError):
            luc = time.time()
        if not p.get("nen_tang"):
            return _loi("Chưa chọn nền tảng nào để đăng.")
        kho.cap_nhat(pid, che_do_dang="tu_dong", dang_luc=luc)
        return {"ok": True, "dang_luc": luc}

    @app.post(A + "/du-an/{pid}/dang-ngay")
    async def xv_dang_ngay(pid: str):
        """Bấm tay: đăng các nền tảng còn thiếu NGAY, bỏ qua lịch và bỏ qua giới hạn thử lại."""
        if (c := _chan()):
            return c
        if chay.dang_chay(pid):
            return _loi("Dự án đang chạy rồi.", 409)
        p = kho.doc(pid)
        if not p or not (p.get("ket_qua") or {}).get("video"):
            return _loi("Dự án chưa có video.")
        chay._dang_chay.add(pid)

        async def _lam():
            try:
                await chay.dang_du_an(pid, _thong_bao, ep=True)
            finally:
                chay._dang_chay.discard(pid)
        _giu(_lam())
        return {"ok": True}

    # ---------------- lô
    @app.post(A + "/lo")
    async def xv_lo(request: Request):
        """Tạo nhiều dự án một lượt: mỗi ý tưởng một video, giãn giờ đăng đều nhau."""
        if (c := _chan()):
            return c
        try:
            body = await request.json()
        except Exception:
            return _loi("Dữ liệu không đúng.")
        y = body.get("y_tuong") or []
        if isinstance(y, str):
            y = [x for x in re.split(r"\n\s*\n|\n-{3,}\n", y)]
        y = [str(x).strip() for x in y if str(x).strip()][:TOI_DA_LO]
        if not y:
            return _loi("Cần ít nhất một ý tưởng.")
        chung = body.get("chung") or {}
        try:
            gian = max(0, min(int(body.get("cach_nhau_phut") or 0), 24 * 60))
        except (TypeError, ValueError):
            gian = 0
        lo_id = secrets.token_hex(5)
        bat_dau = time.time() + 60
        ids = []
        for i, y1 in enumerate(y):
            d = dict(chung, y_tuong=y1, lo_id=lo_id, ten=(chung.get("ten") or "Lô") + f" {i + 1}")
            if gian:
                d["dang_luc"] = bat_dau + i * gian * 60
            ids.append(_tao(d))
        if not shutil.which("ffmpeg"):
            return _loi("Máy chủ chưa cài ffmpeg nên không ghép được video.")

        async def _chay_lo():
            for pid in ids:        # lần lượt từng dự án: tiền và hạn mức được dùng có kiểm soát
                await chay.san_xuat(pid, ask, chep, _thong_bao)
        _giu(_chay_lo())
        return {"ok": True, "lo_id": lo_id, "ids": ids}

    # ---------------- vòng đời
    @app.on_event("startup")
    async def _xv_khoi_dong():
        # Dự án đang dở lúc server tắt thì không còn tác vụ nào chạy nó nữa: đánh dấu lỗi rõ ràng.
        try:
            for t in kho.liet_ke():
                if str(t.get("trang_thai", "")).startswith("dang_") and t["id"] not in chay._dang_chay:
                    if t.get("trang_thai") == "dang_dang":
                        kho.dat_trang_thai(t["id"], "loi", "MinMin khởi động lại đúng lúc đang đăng. Hãy kiểm tra kênh xem bài đã lên chưa trước khi đăng lại.")
                    else:
                        kho.dat_trang_thai(t["id"], "loi", "MinMin khởi động lại giữa chừng. Bấm Chạy tiếp để làm nốt chỗ dở.")
        except Exception:
            pass
        _dung.clear()
        _giu(chay.vong_lich(_thong_bao, _dung))

    @app.on_event("shutdown")
    async def _xv_tat():
        _dung.set()
