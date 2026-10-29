"""up_bai.py - Up bài tự động từ Google Sheet "UP BÀI" (26.10.186).

Chủ repo đang dùng một Sheet (cùng quy ước với Javis) để giao việc đăng bài cho Trang:
  tab CẤU HÌNH PAGE   Bật | Tên Page | Page ID | Loại content (GIÁ CAO/GIÁ THẤP) | Số bài/ngày | Giờ đăng | Trạng thái
  tab HÀNG ĐỢI UP BÀI A Ngày đăng | B Giờ đăng | C Tên Page | D Page ID | E Link video | F Chỉnh sửa video
                      | G Mã hàng | H Giá | I Chi tiết AI nhận diện | J Content hoàn chỉnh | K Duyệt
                      | L Trạng thái | M Video ID | N Link bài | O Lỗi | (P.. quảng cáo, chưa đụng tới)
  tab NHẬT KÝ         Thời gian | Job ID | Page ID | Tên Page | Mã hàng | Hành động | Kết quả | Post ID | Link bài | Chi tiết lỗi

Một dòng đi qua các trạng thái (cột L), mỗi bước ghi ngược vào Sheet nên chủ nhìn Sheet là biết:
  (trống) -> ĐANG XỬ LÝ -> CHỜ DUYỆT -> (Duyệt trên Telegram / gõ ĐÃ DUYỆT ở cột K) -> CHỜ ĐĂNG
          -> ĐANG ĐĂNG -> ĐÃ ĐĂNG | LỖI - ...
Bước xử lý: tải video bằng yt-dlp (TikTok, Facebook, Instagram, Douyin...), chuẩn hoá bằng ffmpeg
(H.264/AAC, faststart: Javis từng đẩy lên Meta một file hỏng và bài không bao giờ lên sóng), cắt 3
khung hình, AI xem khung hình để nhận diện đồ và viết content theo loại content + giá + mã + các
bài mẫu đã đăng của chính Trang đó. Bước đăng: Reels 3 pha qua Graph API bằng token của Trang (kết
nối Facebook Trang), rồi HẬU KIỂM: hỏi lại trạng thái video tới khi Meta báo đã đăng, mới ghi ĐÃ ĐĂNG.

Không tự đăng lại một dòng đã bắt đầu đăng (tránh trùng bài): lỗi sau khi đã đẩy video lên thì
ghi LỖI và để chủ quyết.

Mã máy (mạng, Sheet, AI, Telegram) được tiêm vào qua `Deps` để test thay bằng đồ giả.
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

import localefmt

VN = localefmt.tz()       # múi giờ của chủ (mặc định Việt Nam), lấy từ cài đặt chung
TAB_CAU_HINH = "CẤU HÌNH PAGE"
TAB_HANG_DOI = "HÀNG ĐỢI UP BÀI"
TAB_NHAT_KY = "NHẬT KÝ"
GRAPH = "https://graph.facebook.com/v26.0"

# Cột của HÀNG ĐỢI (chữ cái -> khoá). Đọc tên cột ở hàng tiêu đề để định vị, mặc định theo Sheet hiện tại.
COT_MAC_DINH = {"ngay": "A", "gio": "B", "page": "C", "page_id": "D", "link": "E", "sua": "F",
                "ma": "G", "gia": "H", "nhan_dien": "I", "content": "J", "duyet": "K", "trang_thai": "L",
                "video_id": "M", "link_bai": "N", "loi": "O"}
TEN_COT = {"ngày đăng": "ngay", "giờ đăng": "gio", "tên page": "page", "page id": "page_id",
           "link video": "link", "chỉnh sửa video": "sua", "mã hàng": "ma", "giá": "gia",
           "chi tiết ai nhận diện": "nhan_dien", "content hoàn chỉnh": "content", "duyệt": "duyet",
           "trạng thái": "trang_thai", "video id": "video_id", "link bài": "link_bai", "lỗi": "loi"}

TT_XU_LY, TT_CHO_DUYET, TT_CHO_DANG, TT_DANG_DANG, TT_DA_DANG = (
    "ĐANG XỬ LÝ", "CHỜ DUYỆT", "CHỜ ĐĂNG", "ĐANG ĐĂNG", "ĐÃ ĐĂNG")
DA_DUYET = "ĐÃ DUYỆT"
GIO_BAT_DAU, GIO_KET_THUC, CACH_PHUT, BAI_NGAY = 8, 22, 60, 3


def bay_gio() -> datetime:
    return localefmt.now()


def _bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").strip().lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def cot_chu(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def chu_cot(c: str) -> int:
    n = 0
    for ch in c.upper():
        n = n * 26 + (ord(ch) - 64)
    return n - 1


# ------------------------------------------------------------------ đọc cấu trúc Sheet (thuần)

def tim_tieu_de(rows: List[List[str]]):
    """(chỉ số hàng tiêu đề, {khoá: chữ cột}). Hàng tiêu đề là hàng có ô 'Link video'."""
    for i, r in enumerate(rows[:15]):
        ten = [_bo_dau(x) for x in r]
        if "link video" in ten:
            cot = dict(COT_MAC_DINH)
            for j, x in enumerate(r):
                k = TEN_COT.get(str(x).strip().lower())
                if k:
                    cot[k] = cot_chu(j)
            return i, cot
    return None, dict(COT_MAC_DINH)


def o(row: List[str], cot: Dict[str, str], k: str) -> str:
    j = chu_cot(cot[k])
    return str(row[j]).strip() if j < len(row) and row[j] is not None else ""


@dataclass
class CauHinhPage:
    ten: str
    page_id: str
    loai: str = "GIÁ CAO"
    bai_ngay: int = BAI_NGAY
    gio_dang: List[int] = field(default_factory=list)   # phút trong ngày được phép đăng
    bat: bool = True


def doc_lich(chu: str) -> List[int]:
    """'Bắt đầu đăng từ 08h sáng, và cứ cách 1 tiếng lại đăng bài' -> [480, 540, ...] tới 22h.
    '8h, 11h30, 20h' -> các mốc đó. Trống -> từ 8h cách 60 phút."""
    s = _bo_dau(chu)
    moc = []
    for h, m in re.findall(r"(\d{1,2})\s*(?:h|g|:)\s*(\d{2})?", s):
        if 0 <= int(h) <= 23:
            moc.append(int(h) * 60 + int(m or 0))
    cach = re.search(r"cach\s*(\d+)\s*(tieng|gio|h|phut)", s)
    if cach or (moc and ("tu" in s or "bat dau" in s) and len(moc) == 1):
        bd = moc[0] if moc else GIO_BAT_DAU * 60
        buoc = int(cach.group(1)) * (1 if cach and cach.group(2) == "phut" else 60) if cach else CACH_PHUT
        buoc = max(10, buoc)
        return list(range(bd, GIO_KET_THUC * 60 + 1, buoc))
    if moc:
        return sorted(set(moc))
    return list(range(GIO_BAT_DAU * 60, GIO_KET_THUC * 60 + 1, CACH_PHUT))


def doc_cau_hinh_page(rows: List[List[str]]) -> Dict[str, CauHinhPage]:
    out: Dict[str, CauHinhPage] = {}
    tieu = None
    for i, r in enumerate(rows[:10]):
        if any(_bo_dau(x) == "page id" for x in r):
            tieu = i
            break
    if tieu is None:
        return out
    ten_cot = {_bo_dau(x): j for j, x in enumerate(rows[tieu])}

    def lay(r, k, mac=""):
        j = ten_cot.get(k)
        return str(r[j]).strip() if j is not None and j < len(r) else mac
    for r in rows[tieu + 1:]:
        pid = re.sub(r"\D", "", lay(r, "page id"))
        if not pid:
            continue
        try:
            n = int(re.sub(r"\D", "", lay(r, "so bai/ngay")) or BAI_NGAY)
        except ValueError:
            n = BAI_NGAY
        out[pid] = CauHinhPage(ten=lay(r, "ten page"), page_id=pid, loai=lay(r, "loai content") or "GIÁ CAO",
                               bai_ngay=max(1, min(50, n)), gio_dang=doc_lich(lay(r, "gio dang")),
                               bat=lay(r, "bat", "TRUE").upper() not in ("FALSE", "0", "TẮT", "TAT", "OFF"))
    return out


def den_gio_dang(cfg: CauHinhPage, da_dang_hom_nay: List[datetime], luc: datetime) -> Optional[str]:
    """None nếu được đăng ngay lúc `luc`, không thì lý do chờ (để ghi nhật ký vòng chạy)."""
    if not cfg.bat:
        return "Trang đang tắt ở CẤU HÌNH PAGE"
    if len(da_dang_hom_nay) >= cfg.bai_ngay:
        return f"đã đủ {cfg.bai_ngay} bài hôm nay"
    phut = luc.hour * 60 + luc.minute
    moc_qua = [m for m in cfg.gio_dang if m <= phut]
    if not moc_qua:
        return "chưa tới giờ đăng đầu tiên"
    # Mỗi mốc giờ chỉ một bài: đếm số bài đã đăng từ mốc gần nhất trở đi.
    moc = moc_qua[-1]
    dau_moc = luc.replace(hour=moc // 60, minute=moc % 60, second=0, microsecond=0)
    if any(t >= dau_moc for t in da_dang_hom_nay):
        return "mốc giờ này đã có bài, chờ mốc sau"
    return None


def la_link_video(s: str) -> bool:
    return bool(re.match(r"https?://\S+", s or "")) and any(
        k in s.lower() for k in ("tiktok.com", "facebook.com", "fb.watch", "instagram.com", "douyin.com",
                                 "youtube.com", "youtu.be", "threads.net", "kuaishou", "xiaohongshu", ".mp4"))


def viec_can_lam(row: List[str], cot: Dict[str, str]) -> Optional[str]:
    """'xu_ly' | 'dang' | None cho một dòng hàng đợi."""
    link, tt, duyet = o(row, cot, "link"), _bo_dau(o(row, cot, "trang_thai")), _bo_dau(o(row, cot, "duyet"))
    if not la_link_video(link):
        return None
    if tt in ("", "cho", "up ngay"):
        return "xu_ly"
    if tt in (_bo_dau(TT_CHO_DUYET), _bo_dau(TT_CHO_DANG)) and duyet == _bo_dau(DA_DUYET) and o(row, cot, "content"):
        return "dang"
    return None


def kiem_tra_hang_doi(rows, cfg_rows):
    """Read-only deterministic Sheet evidence; no AI interpretation or publication."""
    cfgs = doc_cau_hinh_page(cfg_rows)
    header, columns = tim_tieu_de(rows)
    if header is None:
        raise ValueError("Không tìm thấy hàng tiêu đề Link video")
    ready, ignored = [], []
    for index, row in enumerate(rows[header+1:], header+2):
        if not any(str(x or '').strip() for x in row):
            continue
        pid = re.sub(r'\D', '', o(row, columns, 'page_id'))
        status = o(row, columns, 'trang_thai')
        entry = {'dong': index, 'page_id': pid, 'trang_thai': status, 'co_media': bool(o(row, columns, 'link'))}
        config = cfgs.get(pid)
        if not pid:
            reason = 'Thiếu Page ID'
        elif not config:
            reason = 'Page chưa có trong cấu hình'
        elif not config.bat:
            reason = 'Page đang tắt'
        elif not o(row, columns, 'link'):
            reason = 'Thiếu link media'
        else:
            action = viec_can_lam(row, columns)
            if action:
                ready.append({**entry, 'hanh_dong': action, 'uu_tien': _bo_dau(status) == 'up ngay'})
                continue
            reason = ('Có link media nhưng luồng video chưa nhận diện được nguồn; cần kiểm tra ảnh/tệp, không kết luận thiếu media'
                      if _bo_dau(status) in ('', 'cho', 'up ngay') else
                      'Chờ hậu kiểm, đã xử lý hoặc chưa đủ điều kiện duyệt; không đăng lại')
        ignored.append({**entry, 'ly_do': reason})
    ready.sort(key=lambda r: (not r['uu_tien'], -r['dong'] if r['uu_tien'] else r['dong']))
    return {'page_bat': [{'page_id': p.page_id, 'ten': p.ten} for p in cfgs.values() if p.bat],
            'du_dieu_kien': ready, 'bo_qua': ignored, 'chi_doc': True}


def prompt_content(cfg: Optional[CauHinhPage], ma: str, gia: str, mau: List[str], ghi_chu: str = "") -> str:
    loai = (cfg.loai if cfg else "GIÁ CAO").upper()
    gia_so = re.sub(r"\D", "", gia or "")
    gia_chu = f"{int(gia_so):,}".replace(",", ".") + "đ" if gia_so else ""
    giong = ("sang, chỉn chu, nhấn chất liệu và phom dáng, hợp khách nữ trung lưu trở lên"
             if "CAO" in loai else "giá tốt, rõ ràng, có kêu gọi chốt đơn, dễ hiểu, hợp khách bình dân")
    phan = [
        "Bạn là content creator phòng marketing của một thương hiệu thời trang nữ thiết kế Việt Nam.",
        "Các ảnh là khung hình cắt từ một video sản phẩm. Hãy:",
        "1) Nhận diện món đồ: loại đồ, chất liệu (đoán từ bề mặt vải), kiểu dáng/phom, màu, chi tiết nổi bật.",
        f"2) Viết MỘT content đăng Facebook Reels, giọng {giong}. Loại content của Trang: {loai}.",
        "   Mở đầu bằng một dòng tiêu đề viết HOA bắt mắt, sau đó 3-6 dòng ngắn, có emoji vừa phải.",
    ]
    if gia_chu:
        phan.append(f"   Có ghi giá: {gia_chu}.")
    else:
        phan.append("   Không bịa giá; chỉ mời inbox để báo giá.")
    if ma:
        phan.append(f"   Có ghi mã sản phẩm: {ma}.")
    phan.append("   Không bịa size/màu/chính sách không thấy trong video. Kết bằng lời mời inbox/để lại SĐT.")
    if ghi_chu:
        phan.append(f"   Ghi chú của chủ cho video này: {ghi_chu}")
    if mau:
        phan.append("Các content Trang này đã đăng (giữ đúng văn phong này):")
        phan += [f"--- mẫu {i + 1} ---\n{m[:700]}" for i, m in enumerate(mau[:3])]
    phan.append('Trả lời DUY NHẤT một JSON: {"nhan_dien": "...ngắn gọn 1 dòng...", "content": "...toàn bộ bài..."}')
    return "\n".join(phan)


def boc_json(text: str) -> Optional[dict]:
    s = str(text or "")
    a, b = s.find("{"), s.rfind("}")
    if 0 <= a < b:
        try:
            d = json.loads(s[a:b + 1])
            if isinstance(d, dict) and str(d.get("content") or "").strip():
                return d
        except Exception:
            pass
    return None


# ------------------------------------------------------------------ video (ffmpeg / yt-dlp)

def _chay(lenh: List[str], timeout: float = 600) -> subprocess.CompletedProcess:
    import winproc
    return subprocess.run(lenh, capture_output=True, text=True, timeout=timeout, errors="replace",
                          **winproc.kwargs_no_window())


def tai_video(link: str, dich: Path) -> Path:
    """Tải video về `dich` (thư mục). Trả đường dẫn file. Raise RuntimeError câu tiếng Việt."""
    dich.mkdir(parents=True, exist_ok=True)
    try:
        import yt_dlp
    except Exception as e:
        raise RuntimeError("máy chủ thiếu yt-dlp") from e
    opts = {"outtmpl": str(dich / "goc.%(ext)s"), "quiet": True, "no_warnings": True, "noplaylist": True,
            "format": "bv*[height<=1920][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
            "merge_output_format": "mp4", "socket_timeout": 30, "retries": 3,
            "max_filesize": 500 * 1024 * 1024}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(link, download=True)
            p = Path(ydl.prepare_filename(info))
    except Exception as e:
        raise RuntimeError(f"không tải được video ({str(e).splitlines()[0][:200]})") from e
    if not p.exists():
        cands = sorted(dich.glob("goc.*"), key=lambda x: x.stat().st_size, reverse=True)
        if not cands:
            raise RuntimeError("tải xong nhưng không thấy file video")
        p = cands[0]
    return p


def thong_tin_video(p: Path) -> dict:
    r = _chay(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(p)], 60)
    try:
        d = json.loads(r.stdout or "{}")
    except Exception:
        d = {}
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"rong": int(v.get("width") or 0), "cao": int(v.get("height") or 0),
            "giay": float((d.get("format") or {}).get("duration") or 0),
            "co_tieng": any(s.get("codec_type") == "audio" for s in d.get("streams", []))}


def chuan_hoa(goc: Path, ra: Path) -> dict:
    """Mã hoá lại H.264 + AAC, yuv420p, faststart; thêm tiếng câm nếu video không có tiếng (Reels
    cần luồng âm thanh). Kiểm lại bằng ffprobe trước khi trả: file hỏng thì raise, không đẩy lên Meta."""
    tt = thong_tin_video(goc)
    if not tt["rong"]:
        raise RuntimeError("file tải về không phải video đọc được")
    lenh = ["ffmpeg", "-y", "-v", "error", "-i", str(goc)]
    if not tt["co_tieng"]:
        lenh += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-shortest"]
    lenh += ["-map", "0:v:0", "-map", "0:a:0" if tt["co_tieng"] else "1:a:0",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
             "-vf", "scale='min(1080,iw)':-2", "-r", "30", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart", str(ra)]
    r = _chay(lenh, 900)
    if r.returncode != 0 or not ra.exists():
        raise RuntimeError(f"chuẩn hoá video lỗi: {(r.stderr or '')[-200:]}")
    tt2 = thong_tin_video(ra)
    if not tt2["rong"] or tt2["giay"] <= 0:
        raise RuntimeError("video sau chuẩn hoá không đọc được, không đăng để tránh bài hỏng")
    return tt2


def cat_khung(video: Path, thu_muc: Path, giay: float, so: int = 3) -> List[Path]:
    out = []
    for i in range(so):
        t = max(0.2, giay * (0.15 + 0.6 * i / max(1, so - 1))) if giay else 0.5 + i
        p = thu_muc / f"khung-{i + 1}.jpg"
        _chay(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
               "-vf", "scale='min(720,iw)':-2", "-q:v", "3", str(p)], 60)
        if p.exists() and p.stat().st_size > 0:
            out.append(p)
    return out


# ------------------------------------------------------------------ Graph API (Reels + hậu kiểm)

class LoiDang(RuntimeError):
    def __init__(self, msg: str, da_day_len: bool = False, video_id: str = ""):
        super().__init__(msg)
        self.da_day_len = da_day_len
        self.video_id = video_id


async def dang_reel(client, page_id: str, token: str, video: Path, mo_ta: str,
                    cho_toi_da: float = 900, nhip: float = 15) -> dict:
    """Đăng Reels 3 pha rồi hậu kiểm tới khi Meta báo đã đăng. Trả {video_id, link}."""
    r = await client.post(f"{GRAPH}/{page_id}/video_reels", data={"upload_phase": "start", "access_token": token})
    d = r.json()
    if d.get("error") or not d.get("video_id"):
        raise LoiDang(f"Meta từ chối bắt đầu tải Reels: {(d.get('error') or {}).get('message') or d}")
    vid = str(d["video_id"])
    up = d.get("upload_url") or f"https://rupload.facebook.com/video-upload/v26.0/{vid}"
    data = video.read_bytes()
    r = await client.post(up, content=data, headers={"Authorization": f"OAuth {token}", "offset": "0",
                                                      "file_size": str(len(data))}, timeout=900)
    try:
        ok = r.json().get("success")
    except Exception:
        ok = False
    if not ok:
        raise LoiDang(f"tải file video lên Meta không thành công (HTTP {r.status_code})", True, vid)
    r = await client.post(f"{GRAPH}/{page_id}/video_reels",
                          data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                "description": mo_ta, "access_token": token})
    d = r.json()
    if d.get("error") or not d.get("success", True):
        raise LoiDang(f"Meta không nhận lệnh đăng: {(d.get('error') or {}).get('message') or d}", True, vid)
    han = time.monotonic() + cho_toi_da
    cuoi = {}
    while time.monotonic() < han:
        r = await client.get(f"{GRAPH}/{vid}", params={"fields": "status,permalink_url", "access_token": token})
        cuoi = r.json()
        st = cuoi.get("status") or {}
        if st.get("video_status") == "error" or (st.get("processing_phase") or {}).get("status") == "error":
            raise LoiDang(f"Meta báo lỗi xử lý video: {json.dumps(st, ensure_ascii=False)[:300]}", True, vid)
        pub = (st.get("publishing_phase") or {}).get("status")
        if st.get("video_status") == "ready" and pub in ("complete", None):
            link = cuoi.get("permalink_url") or f"https://www.facebook.com/reel/{vid}"
            if link.startswith("/"):
                link = "https://www.facebook.com" + link
            return {"video_id": vid, "link": link}
        await asyncio.sleep(nhip)
    raise LoiDang(f"đã đẩy video nhưng sau {int(cho_toi_da / 60)} phút Meta vẫn chưa đăng xong "
                  f"(trạng thái {json.dumps(cuoi.get('status') or {}, ensure_ascii=False)[:200]}). "
                  "Kiểm tra trên Trang trước khi đăng lại.", True, vid)


# ------------------------------------------------------------------ vòng chạy

@dataclass
class Deps:
    doc_sheet: Callable[[str, str], Awaitable[List[List[str]]]]            # (sheet_id, tab) -> rows
    ghi_o: Callable[[str, str, Dict[str, List[List[Any]]]], Awaitable[None]]  # (sheet_id, tab, {A1: [[..]]})
    them_dong: Callable[[str, str, List[Any]], Awaitable[None]]            # (sheet_id, tab, row) nhật ký
    nhin_anh: Callable[[List[str], str], Awaitable[str]]                   # (ảnh trong brain, prompt) -> text
    token_page: Callable[[str], Awaitable[str]]                            # page_id -> page token
    bao: Callable[[dict, str], Awaitable[None]]                            # (thẻ, sự_kiện)
    http: Callable[[], Any]                                                # -> httpx.AsyncClient
    thu_muc: Path = Path(".")                                              # trong brain (để AI xem ảnh)
    goc_brain: str = ""


class UpBai:
    def __init__(self, deps: Deps, sheet_id: str = "", tu_duyet: bool = False):
        self.d = deps
        self.sheet_id = sheet_id
        self.tu_duyet = tu_duyet
        self._khoa = asyncio.Lock()
        self.lan_cuoi: dict = {}
        self.nhat_ky_vong: List[str] = []

    def _ghi(self, s: str) -> None:
        self.nhat_ky_vong.append(bay_gio().strftime("%H:%M ") + s)
        self.nhat_ky_vong = self.nhat_ky_vong[-60:]

    async def _ghi_dong(self, tab: str, so_dong: int, cot: Dict[str, str], gia_tri: Dict[str, Any]) -> None:
        await self.d.ghi_o(self.sheet_id, tab,
                           {f"{cot[k]}{so_dong}": [[v]] for k, v in gia_tri.items() if k in cot})

    async def chay_mot_vong(self, chi_dong: Optional[int] = None) -> dict:
        """Một lượt: xử lý tối đa 2 dòng mới và đăng tối đa 1 bài đến hạn. Trả tóm tắt."""
        if not self.sheet_id:
            return {"ok": False, "loi": "chưa đặt Google Sheet UP BÀI"}
        if self._khoa.locked():
            return {"ok": True, "bo_qua": "vòng trước còn chạy"}
        async with self._khoa:
            kq = {"ok": True, "xu_ly": 0, "dang": 0, "cho": []}
            rows = await self.d.doc_sheet(self.sheet_id, TAB_HANG_DOI)
            cfg_rows = await self.d.doc_sheet(self.sheet_id, TAB_CAU_HINH)
            cfgs = doc_cau_hinh_page(cfg_rows)
            tieu, cot = tim_tieu_de(rows)
            if tieu is None:
                return {"ok": False, "loi": f"tab '{TAB_HANG_DOI}' không có hàng tiêu đề 'Link video'"}
            hom_nay = bay_gio().strftime("%d/%m")
            da_dang: Dict[str, List[datetime]] = {}
            mau: Dict[str, List[str]] = {}
            for r in rows[tieu + 1:]:
                pid = re.sub(r"\D", "", o(r, cot, "page_id"))
                if _bo_dau(o(r, cot, "trang_thai")).startswith(_bo_dau(TT_DA_DANG)):
                    if o(r, cot, "content"):
                        mau.setdefault(pid, []).append(o(r, cot, "content"))
                    if o(r, cot, "ngay") == hom_nay:
                        try:
                            hh, mm = re.findall(r"\d+", o(r, cot, "gio"))[:2]
                            da_dang.setdefault(pid, []).append(
                                bay_gio().replace(hour=int(hh), minute=int(mm), second=0, microsecond=0))
                        except ValueError:
                            da_dang.setdefault(pid, []).append(bay_gio())
            xu_ly_con, dang_con = 2, 1
            plan = kiem_tra_hang_doi(rows, cfg_rows)
            for entry in plan['du_dieu_kien']:
                i = entry['dong']
                r = rows[i-1]
                if chi_dong and i != chi_dong:
                    continue
                viec = viec_can_lam(r, cot)
                if viec == "xu_ly" and xu_ly_con > 0:
                    xu_ly_con -= 1
                    await self._xu_ly(i, r, cot, cfgs, mau)
                    kq["xu_ly"] += 1
                elif viec == "dang" and dang_con > 0:
                    pid = re.sub(r"\D", "", o(r, cot, "page_id"))
                    cfg = cfgs.get(pid) or CauHinhPage(ten=o(r, cot, "page"), page_id=pid,
                                                       gio_dang=doc_lich(""))
                    ly = None if chi_dong else den_gio_dang(cfg, da_dang.get(pid, []), bay_gio())
                    if ly:
                        kq["cho"].append(f"dòng {i} ({cfg.ten or pid}): {ly}")
                        continue
                    dang_con -= 1
                    if await self._dang(i, r, cot):
                        da_dang.setdefault(pid, []).append(bay_gio())
                        kq["dang"] += 1
            self.lan_cuoi = {"luc": bay_gio().strftime("%d/%m %H:%M"), **kq}
            return kq

    async def kiem_tra(self, sheet_id=""):
        sid = sheet_id or self.sheet_id
        if not sid:
            raise ValueError("Chưa chọn Google Sheet UP BÀI")
        rows = await self.d.doc_sheet(sid, TAB_HANG_DOI)
        configs = await self.d.doc_sheet(sid, TAB_CAU_HINH)
        return kiem_tra_hang_doi(rows, configs)

    async def _xu_ly(self, so_dong: int, r: List[str], cot, cfgs, mau) -> None:
        link, pid = o(r, cot, "link"), re.sub(r"\D", "", o(r, cot, "page_id"))
        await self._ghi_dong(TAB_HANG_DOI, so_dong, cot, {"trang_thai": TT_XU_LY, "loi": ""})
        self._ghi(f"dòng {so_dong}: tải video {link[:60]}")
        thu = self.d.thu_muc / f"dong-{so_dong}-{int(time.time())}"
        try:
            goc = await asyncio.to_thread(tai_video, link, thu)
            sach = thu / "video.mp4"
            tt = await asyncio.to_thread(chuan_hoa, goc, sach)
            try:
                goc.unlink()
            except Exception:
                pass
            khung = await asyncio.to_thread(cat_khung, sach, thu, tt["giay"])
            if not khung:
                raise RuntimeError("không cắt được khung hình để AI xem")
            prompt = prompt_content(cfgs.get(pid), o(r, cot, "ma"), o(r, cot, "gia"), mau.get(pid, [])[-3:],
                                    o(r, cot, "sua"))
            tra = await self.d.nhin_anh([str(k) for k in khung], prompt)
            d = boc_json(tra)
            if not d:
                raise RuntimeError(f"AI không trả content đúng dạng: {str(tra)[:200]}")
        except Exception as e:
            shutil.rmtree(str(thu), ignore_errors=True)
            await self._ghi_dong(TAB_HANG_DOI, so_dong, cot, {
                "trang_thai": "LỖI - CHƯA ĐĂNG", "loi": f"{bay_gio():%d/%m %H:%M} - {e}"})
            self._ghi(f"dòng {so_dong}: lỗi xử lý - {e}")
            await self.d.bao({"dong": so_dong, "page": o(r, cot, "page"), "link": link, "loi": str(e)}, "loi")
            return
        da_duyet = self.tu_duyet or _bo_dau(o(r, cot, "duyet")) == _bo_dau(DA_DUYET)
        await self._ghi_dong(TAB_HANG_DOI, so_dong, cot, {
            "nhan_dien": str(d.get("nhan_dien") or "")[:500], "content": str(d["content"]).strip(),
            "trang_thai": TT_CHO_DANG if da_duyet else TT_CHO_DUYET,
            **({"duyet": DA_DUYET} if self.tu_duyet else {})})
        (thu / "the.json").write_text(json.dumps({"link": link, "page_id": pid}, ensure_ascii=False), "utf-8")
        self._ghi(f"dòng {so_dong}: đã viết content, {'chờ đăng' if da_duyet else 'chờ duyệt'}")
        await self.d.bao({"dong": so_dong, "page": o(r, cot, "page"), "page_id": pid, "link": link,
                          "ma": o(r, cot, "ma"), "gia": o(r, cot, "gia"), "nhan_dien": d.get("nhan_dien") or "",
                          "content": str(d["content"]).strip(), "anh": str(khung[0])},
                         "cho_dang" if da_duyet else "cho_duyet")

    def _tim_video(self, so_dong: int, link: str) -> Optional[Path]:
        for thu in sorted(self.d.thu_muc.glob(f"dong-{so_dong}-*"), reverse=True):
            try:
                the = json.loads((thu / "the.json").read_text("utf-8"))
            except Exception:
                continue
            if the.get("link") == link and (thu / "video.mp4").exists():
                return thu / "video.mp4"
        return None

    async def _dang(self, so_dong: int, r: List[str], cot) -> bool:
        link, pid, page = o(r, cot, "link"), re.sub(r"\D", "", o(r, cot, "page_id")), o(r, cot, "page")
        video = self._tim_video(so_dong, link)
        if not video:
            # Video đã dọn hoặc dòng do người khác điền content sẵn: tải lại (chưa đẩy gì lên Meta).
            thu = self.d.thu_muc / f"dong-{so_dong}-{int(time.time())}"
            try:
                goc = await asyncio.to_thread(tai_video, link, thu)
                video = thu / "video.mp4"
                await asyncio.to_thread(chuan_hoa, goc, video)
                (thu / "the.json").write_text(json.dumps({"link": link, "page_id": pid}), "utf-8")
            except Exception as e:
                await self._ghi_dong(TAB_HANG_DOI, so_dong, cot, {
                    "trang_thai": "LỖI - CHƯA ĐĂNG", "loi": f"{bay_gio():%d/%m %H:%M} - {e}"})
                return False
        await self._ghi_dong(TAB_HANG_DOI, so_dong, cot, {"trang_thai": TT_DANG_DANG, "loi": ""})
        self._ghi(f"dòng {so_dong}: đăng Reels lên {page or pid}")
        luc = bay_gio()
        job = f"{o(r, cot, 'ma') or 'BAI'}-{pid}-{luc:%Y%m%d-%H%M}"
        try:
            token = await self.d.token_page(pid)
            async with self.d.http() as c:
                kq = await dang_reel(c, pid, token, video, o(r, cot, "content"))
        except Exception as e:
            da_day = getattr(e, "da_day_len", False)
            vid = getattr(e, "video_id", "")
            await self._ghi_dong(TAB_HANG_DOI, so_dong, cot, {
                "trang_thai": "LỖI - CẦN KIỂM TRA TRANG" if da_day else "LỖI - CHƯA ĐĂNG",
                "video_id": f"{vid} (chỉ là ID video đã tải lên, chưa chắc đã đăng)" if vid else "",
                "loi": f"{luc:%d/%m %H:%M} - {e}"})
            await self.d.them_dong(self.sheet_id, TAB_NHAT_KY, [
                f"{luc:%d/%m/%Y %H:%M}", job, pid, page, o(r, cot, "ma"), "Đăng Reels", "LỖI", vid, "", str(e)[:500]])
            self._ghi(f"dòng {so_dong}: đăng lỗi - {e}")
            await self.d.bao({"dong": so_dong, "page": page, "link": link, "loi": str(e)}, "loi")
            return False
        await self._ghi_dong(TAB_HANG_DOI, so_dong, cot, {
            "ngay": f"{luc:%d/%m}", "gio": f"{luc:%H}h{luc:%M}", "trang_thai": TT_DA_DANG,
            "video_id": kq["video_id"], "link_bai": kq["link"], "loi": ""})
        await self.d.them_dong(self.sheet_id, TAB_NHAT_KY, [
            f"{luc:%d/%m/%Y %H:%M}", job, pid, page, o(r, cot, "ma"), "Đăng Reels",
            "THÀNH CÔNG - Meta báo đã đăng", kq["video_id"], kq["link"], ""])
        shutil.rmtree(str(video.parent), ignore_errors=True)
        self._ghi(f"dòng {so_dong}: ĐÃ ĐĂNG {kq['link']}")
        await self.d.bao({"dong": so_dong, "page": page, "link_bai": kq["link"], "ma": o(r, cot, "ma")}, "da_dang")
        return True

    async def duyet(self, so_dong: int, dong_y: bool) -> str:
        rows = await self.d.doc_sheet(self.sheet_id, TAB_HANG_DOI)
        tieu, cot = tim_tieu_de(rows)
        if tieu is None or so_dong - 1 >= len(rows):
            return "không thấy dòng này trong Sheet"
        r = rows[so_dong - 1]
        if _bo_dau(o(r, cot, "trang_thai")) != _bo_dau(TT_CHO_DUYET):
            return f"dòng {so_dong} đang ở trạng thái '{o(r, cot, 'trang_thai')}', không duyệt lại"
        if dong_y:
            await self._ghi_dong(TAB_HANG_DOI, so_dong, cot, {"duyet": DA_DUYET, "trang_thai": TT_CHO_DANG})
            return "Đã duyệt. MinMin đăng khi tới mốc giờ của Trang."
        await self._ghi_dong(TAB_HANG_DOI, so_dong, cot, {"duyet": "BỎ", "trang_thai": "ĐÃ BỎ"})
        for thu in self.d.thu_muc.glob(f"dong-{so_dong}-*"):
            shutil.rmtree(str(thu), ignore_errors=True)
        return "Đã bỏ bài này."


def id_sheet(link_hoac_id: str) -> str:
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]{20,})", link_hoac_id or "")
    if m:
        return m.group(1)
    s = str(link_hoac_id or "").strip()
    return s if re.fullmatch(r"[A-Za-z0-9_-]{20,}", s) else ""
