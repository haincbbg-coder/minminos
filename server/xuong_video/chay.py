"""Dây chuyền chạy của Xưởng video: kịch bản -> ảnh -> video -> giọng -> ghép -> đăng.

Mỗi bước bỏ qua phần đã có file, nên bấm chạy lại sau lỗi chỉ làm tiếp chỗ dở, không tốn tiền
tạo lại cảnh đã xong. Hai rào an toàn tiền/tài khoản:
  - hạn mức video và bài đăng mỗi ngày (cài đặt), vì mỗi cảnh video là một khoản tiền thật;
  - lỗi đăng "chưa rõ đã lên hay chưa" (LoiDang.chua_ro) KHÔNG BAO GIỜ tự thử lại, tránh đăng đúp.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

from . import dang as _dang
from . import ghep as _ghep
from . import kho, khoa, kich_ban, ncc

SONG_SONG_VIDEO = 2
TOI_DA_THU_LAI_DANG = 2
NHIP_LICH = 30          # giây giữa hai lần quét lịch đăng

_dang_chay: set = set()
_sem_video: Optional[asyncio.Semaphore] = None

NotifyFn = Callable[[str, str], None]          # (tiêu đề, nội dung)
AskFn = Callable[[str, str, List[str]], Awaitable[str]]
ChepFn = Callable[[str, List[Path]], List[str]]


# ------------------------------------------------------------------ hạn mức theo ngày
def _file_dem() -> Path:
    return kho.goc().parent / "dem-ngay.json"


def _dem() -> dict:
    try:
        d = json.loads(_file_dem().read_text("utf-8"))
    except Exception:
        d = {}
    hom_nay = date.today().isoformat()
    if d.get("ngay") != hom_nay:
        d = {"ngay": hom_nay, "video": 0, "dang": 0}
    return d


def da_dung_hom_nay() -> dict:
    d = _dem()
    return {"video": int(d.get("video", 0)), "dang": int(d.get("dang", 0))}


def _tang(loai: str) -> None:
    d = _dem()
    d[loai] = int(d.get(loai, 0)) + 1
    _file_dem().write_text(json.dumps(d), "utf-8")


def con_han_muc(loai: str) -> bool:
    khoa_cd = "toi_da_video_moi_ngay" if loai == "video" else "toi_da_bai_dang_moi_ngay"
    tran = int(khoa.cai_dat().get(khoa_cd, 0))
    return tran <= 0 or int(_dem().get(loai, 0)) < tran


def dang_chay(pid: str) -> bool:
    return pid in _dang_chay


# ------------------------------------------------------------------ sản xuất
class _Dung(Exception):
    pass


def _sem() -> asyncio.Semaphore:
    global _sem_video
    if _sem_video is None:
        _sem_video = asyncio.Semaphore(SONG_SONG_VIDEO)
    return _sem_video


def _lenh_anh(p: dict, c: dict) -> str:
    pc = (p.get("kich_ban") or {}).get("phong_cach") or p.get("phong_cach") or ""
    return (f"{c.get('mo_ta_hinh', '')}. Phong cách: {pc}. Không chữ, không logo, không hình mờ.").strip()


async def _anh_nhan_vat(pid: str, p: dict, cfg: dict) -> None:
    base = kho.thu_muc(pid)
    ref = [base / t["rel"] for t in p.get("tai_lieu") or [] if t.get("loai") == "anh"][:2]
    for i, nv in enumerate(p.get("nhan_vat") or []):
        if nv.get("anh") and (base / nv["anh"]).is_file():
            continue
        data = await ncc.tao_anh(f"Ảnh tham chiếu nhân vật, nền trơn, nhìn rõ mặt và trang phục: "
                                 f"{nv.get('ten')}. {nv.get('mo_ta')}. Phong cách: "
                                 f"{(p.get('kich_ban') or {}).get('phong_cach', '')}", "1:1", ref, cfg)
        rel = f"nhan-vat/nv-{i + 1}.png"
        (base / "nhan-vat").mkdir(exist_ok=True)
        (base / rel).write_bytes(data)
        kho.cap_nhat(pid, nhan_vat=lambda ds, i=i, rel=rel: [dict(x, anh=rel) if j == i else x
                                                             for j, x in enumerate(ds or [])])


async def _mot_canh(pid: str, stt: int, cfg_anh: dict, cfg_video: dict, cfg_giong: dict, co_giong: bool) -> None:
    p = kho.doc(pid)
    c = next(x for x in p["canh"] if int(x["stt"]) == stt)
    base = kho.thu_muc(pid)
    (base / "canh").mkdir(exist_ok=True)
    try:
        if not (c.get("anh") and (base / c["anh"]).is_file()):
            ref = [base / n["anh"] for n in p.get("nhan_vat") or []
                   if n.get("anh") and n.get("ten") in (c.get("nhan_vat") or [])]
            if not ref:
                ref = [base / t["rel"] for t in p.get("tai_lieu") or [] if t.get("loai") == "anh"][:1]
            data = await ncc.tao_anh(_lenh_anh(p, c), p["ti_le"], ref, cfg_anh)
            rel = f"canh/{stt:02d}.png"
            (base / rel).write_bytes(data)
            kho.cap_nhat_canh(pid, stt, anh=rel, trang_thai="co_anh", loi="")
            c["anh"] = rel
        if not (c.get("video") and (base / c["video"]).is_file()):
            if not con_han_muc("video"):
                raise _Dung("Đã chạm hạn mức video trong ngày. Sang ngày mới (hoặc tăng hạn mức ở Cài đặt) rồi bấm chạy tiếp.")
            async with _sem():
                data = await ncc.tao_video(f"{c.get('mo_ta_hinh', '')}. {c.get('chuyen_dong', '')}".strip(),
                                           base / c["anh"], c.get("giay") or 6, p["ti_le"], cfg_video)
            _tang("video")
            rel = f"canh/{stt:02d}.mp4"
            (base / rel).write_bytes(data)
            kho.cap_nhat_canh(pid, stt, video=rel, trang_thai="co_video", loi="")
            kho.cap_nhat(pid, so_video_da_tao=lambda n: int(n or 0) + 1)
        if co_giong and c.get("loi_thoai") and not (c.get("giong") and (base / c["giong"]).is_file()):
            data = await ncc.tao_giong(c["loi_thoai"], cfg_giong)
            rel = f"canh/{stt:02d}.mp3"
            (base / rel).write_bytes(data)
            kho.cap_nhat_canh(pid, stt, giong=rel)
    except _Dung:
        raise
    except Exception as e:
        kho.cap_nhat_canh(pid, stt, trang_thai="loi", loi=str(e)[:300])
        raise


async def san_xuat(pid: str, ask: AskFn, chep: ChepFn, thong_bao: Optional[NotifyFn] = None) -> None:
    """Chạy (hoặc chạy tiếp) từ kịch bản tới video hoàn chỉnh. Không ném lỗi: lỗi ghi vào dự án."""
    if pid in _dang_chay:
        return
    _dang_chay.add(pid)
    tb = thong_bao or (lambda t, n: None)
    try:
        p = kho.doc(pid)
        if not p:
            return
        cfg = khoa.cai_dat()
        kho.cap_nhat(pid, loi="")
        if not (p.get("canh") or []):
            await kich_ban.lap(pid, ask, chep)
            p = kho.doc(pid)
        kho.dat_trang_thai(pid, "dang_tao_anh")
        await _anh_nhan_vat(pid, p, cfg["anh"])
        p = kho.doc(pid)
        co_giong = bool(khoa.lay("elevenlabs").get("api_key"))
        if not co_giong:
            kho.nhat_ky(pid, "Chưa có khoá ElevenLabs: bỏ qua giọng đọc, video sẽ không có lời.", "warn")
        kho.dat_trang_thai(pid, "dang_tao_video")
        kq = await asyncio.gather(*[_mot_canh(pid, int(c["stt"]), cfg["anh"], cfg["video"], cfg["giong"], co_giong)
                                    for c in p["canh"]], return_exceptions=True)
        dung = [e for e in kq if isinstance(e, _Dung)]
        hong = [e for e in kq if isinstance(e, Exception) and not isinstance(e, _Dung)]
        if dung or hong:
            e = (dung or hong)[0]
            kho.dat_trang_thai(pid, "loi", str(e))
            kho.nhat_ky(pid, f"Dừng giữa chừng: {e}", "loi")
            tb(f"Xưởng video: '{p.get('ten')}' dừng giữa chừng", str(e))
            return
        kho.dat_trang_thai(pid, "dang_ghep")
        await _ghep.ghep(pid, bool(cfg.get("ghep_phu_de", True)))
        kho.dat_trang_thai(pid, "san_sang")
        kho.nhat_ky(pid, "Video đã ghép xong.")
        p = kho.doc(pid)
        if p.get("nen_tang") and p.get("che_do_dang") == "tu_dong":
            if not p.get("dang_luc"):
                kho.cap_nhat(pid, dang_luc=time.time())
            tb(f"Xưởng video: '{p.get('ten')}' đã xong, sẽ tự đăng theo lịch", "")
        else:
            tb(f"Xưởng video: '{p.get('ten')}' đã xong, chờ bố duyệt", "Mở Xưởng video để xem rồi bấm duyệt đăng.")
    except Exception as e:      # lập kịch bản hỏng, ghép hỏng...
        kho.dat_trang_thai(pid, "loi", str(e))
        kho.nhat_ky(pid, f"Lỗi: {e}", "loi")
        tb("Xưởng video: có dự án bị lỗi", f"{pid}: {str(e)[:200]}")
    finally:
        _dang_chay.discard(pid)


# ------------------------------------------------------------------ đăng
def _den_han(p: dict, nt: str, bay_gio: float) -> bool:
    d = (p.get("dang") or {}).get(nt) or {}
    if d.get("trang_thai") in ("da_dang", "chua_ro", "da_huy"):
        return False
    if d.get("trang_thai") == "loi":
        return int(d.get("lan", 0)) < TOI_DA_THU_LAI_DANG and bay_gio >= float(d.get("thu_lai_luc") or 0)
    return True


async def dang_du_an(pid: str, thong_bao: Optional[NotifyFn] = None, ep: bool = False) -> dict:
    """Đăng mọi nền tảng còn thiếu của một dự án. `ep=True`: người dùng bấm tay, bỏ qua lịch."""
    tb = thong_bao or (lambda t, n: None)
    p = kho.doc(pid)
    if not p or not (p.get("ket_qua") or {}).get("video"):
        return {"ok": False, "loi": "Dự án chưa có video."}
    video = kho.duong_dan_file(pid, p["ket_qua"]["video"])
    if not video:
        return {"ok": False, "loi": "Không thấy file video."}
    bay_gio = time.time()
    xong = []
    for nt in p.get("nen_tang") or []:
        tt = ((p.get("dang") or {}).get(nt) or {}).get("trang_thai")
        if ep:
            if tt in ("da_dang", "chua_ro"):
                continue
        elif not _den_han(p, nt, bay_gio):
            continue
        if not con_han_muc("dang"):
            kho.nhat_ky(pid, "Đã chạm hạn mức bài đăng trong ngày, để mai.", "warn")
            break
        kho.dat_trang_thai(pid, "dang_dang")
        lan = int(((p.get("dang") or {}).get(nt) or {}).get("lan", 0)) + 1
        try:
            kq = await _dang.dang(nt, p, video)
            _tang("dang")
            ghi = {"trang_thai": "da_dang", "id": kq.get("id", ""), "url": kq.get("url", ""), "luc": time.time(), "lan": lan}
            tb(f"Đã đăng '{p.get('ten')}' lên {nt}", kq.get("url", ""))
            kho.nhat_ky(pid, f"Đã đăng {nt}: {kq.get('url', '')}")
        except _dang.LoiDang as e:
            if e.chua_ro:
                ghi = {"trang_thai": "chua_ro", "loi": str(e)[:400], "luc": time.time(), "lan": lan}
                tb(f"Cần bố kiểm tra: '{p.get('ten')}' trên {nt}", str(e)[:300])
            else:
                ghi = {"trang_thai": "loi", "loi": str(e)[:400], "luc": time.time(), "lan": lan,
                       "thu_lai_luc": time.time() + 600 * lan}
                tb(f"Đăng {nt} lỗi: '{p.get('ten')}'", str(e)[:300])
            kho.nhat_ky(pid, f"Đăng {nt} lỗi: {e}", "loi")
        except Exception as e:
            ghi = {"trang_thai": "loi", "loi": f"{type(e).__name__}: {e}"[:400], "luc": time.time(), "lan": lan,
                   "thu_lai_luc": time.time() + 600 * lan}
        kho.cap_nhat(pid, dang=lambda d, nt=nt, ghi=ghi: dict(d or {}, **{nt: ghi}))
        xong.append(nt)
        p = kho.doc(pid)
    p = kho.doc(pid) or p
    het = all(((p.get("dang") or {}).get(nt) or {}).get("trang_thai") in ("da_dang", "chua_ro")
              for nt in p.get("nen_tang") or [])
    kho.dat_trang_thai(pid, "da_dang" if het and p.get("nen_tang") else "san_sang")
    return {"ok": True, "da_thu": xong}


async def vong_lich(thong_bao: Optional[NotifyFn] = None, dung: Optional[asyncio.Event] = None) -> None:
    """Quét lịch: dự án sẵn sàng + chế độ tự động + đã tới giờ thì đăng."""
    while not (dung and dung.is_set()):
        try:
            bay_gio = time.time()
            for t in kho.liet_ke():
                if t.get("trang_thai") != "san_sang" or t.get("che_do_dang") != "tu_dong" or not t.get("nen_tang"):
                    continue
                if float(t.get("dang_luc") or 0) > bay_gio or t["id"] in _dang_chay:
                    continue
                _dang_chay.add(t["id"])
                try:
                    await dang_du_an(t["id"], thong_bao)
                finally:
                    _dang_chay.discard(t["id"])
        except Exception:
            pass
        await asyncio.sleep(NHIP_LICH)
