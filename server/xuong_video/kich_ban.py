"""Từ ý tưởng + tài liệu (ảnh, video) thành kịch bản và storyboard dạng JSON.

Việc nghĩ do engine AI mà chủ đã chọn ở MinMin làm (Claude Code, Codex, API...). Ở đây chỉ làm ba
việc quanh nó: (1) trích khung hình từ video tham khảo để engine "nhìn" được, (2) dựng yêu cầu
đòi đúng một khối JSON, (3) đọc và làm sạch JSON đó, chặn đầu ra bậy (cảnh trùng số, thời lượng
ngoài khoảng, câu thoại quá dài so với thời lượng cảnh).

"Modding" một video có sẵn thành bản mới: engine được dặn rõ là phải đổi nhân vật, bối cảnh,
lời thoại và cách kể, KHÔNG dựng lại từng khung hình của bản gốc. Cố ý: bản sao y chang một
video của người khác lên kênh của chủ là rủi ro vi phạm bản quyền, nên thiết kế đi theo hướng
"lấy ý, kể lại bằng hình và lời mới".
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

import winproc
from . import kho

MAX_KHUNG = 6
GIAY_TOI_DA_MOT_CANH = 8.0
GIAY_TOI_THIEU_MOT_CANH = 3.0
TU_MOI_GIAY = 2.6          # tốc độ đọc tiếng Việt thoải mái, từ trên giây (để cắt thoại quá dài)


async def trich_khung(video: Path, dich: Path, so: int = MAX_KHUNG) -> List[Path]:
    """Trích `so` khung hình rải đều từ video. Rỗng nếu thiếu ffmpeg hoặc video hỏng."""
    ff = shutil.which("ffmpeg")
    if not ff or not video.is_file():
        return []
    dich.mkdir(parents=True, exist_ok=True)
    try:
        pr = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, **winproc.kwargs_no_window())
        o, _ = await asyncio.wait_for(pr.communicate(), 30)
        dai = float((o or b"0").decode().strip() or 0)
    except Exception:
        dai = 0.0
    if dai <= 0:
        return []
    out = []
    for i in range(so):
        t = dai * (i + 0.5) / so
        f = dich / f"{video.stem}-{i + 1}.jpg"
        try:
            pr = await asyncio.create_subprocess_exec(
                ff, "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=720:-2", str(f),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL, **winproc.kwargs_no_window())
            await asyncio.wait_for(pr.wait(), 60)
        except Exception:
            continue
        if f.is_file() and f.stat().st_size > 0:
            out.append(f)
    return out


def dung_yeu_cau(p: dict, anh_rel: List[str], khung_rel: List[str]) -> str:
    gs = int(p.get("thoi_luong_giay") or 30)
    so_canh = max(3, min(round(gs / 6), 20))
    ti_le = p.get("ti_le") or "9:16"
    ngon = {"vi": "tiếng Việt", "en": "English"}.get(p.get("ngon_ngu"), p.get("ngon_ngu") or "tiếng Việt")
    nt = ", ".join(p.get("nen_tang") or []) or "YouTube"
    dong = [
        "Bạn là đạo diễn kiêm biên kịch video ngắn. Hãy lập KỊCH BẢN và STORYBOARD cho một video.",
        "",
        f"Ý TƯỞNG CỦA CHỦ:\n{p.get('y_tuong') or '(không có chữ, dựa vào ảnh/video tham khảo)'}",
        "",
        f"Tổng thời lượng mục tiêu: {gs} giây, khoảng {so_canh} cảnh, mỗi cảnh {int(GIAY_TOI_THIEU_MOT_CANH)}-{int(GIAY_TOI_DA_MOT_CANH)} giây.",
        f"Tỉ lệ khung hình: {ti_le}. Ngôn ngữ lời thoại/lời dẫn: {ngon}. Nền tảng đăng: {nt}.",
    ]
    if p.get("phong_cach"):
        dong.append(f"Phong cách hình ảnh chủ muốn: {p['phong_cach']}")
    if anh_rel:
        dong += ["", "ẢNH THAM KHẢO của chủ (hãy MỞ ĐỌC từng file ảnh để nhìn):"] + [f"- {x}" for x in anh_rel]
    if khung_rel:
        dong += ["", "KHUNG HÌNH trích từ VIDEO THAM KHẢO (mở đọc để hiểu cách kể, nhịp, bối cảnh):"] + [f"- {x}" for x in khung_rel]
        dong += ["", "Video tham khảo chỉ để LẤY Ý. Bản mới phải khác: đổi nhân vật, bối cảnh, chi tiết và lời thoại, "
                     "kể lại bằng hình và lời mới. Không dựng lại từng khung hình, không giữ nguyên nhân vật hay logo của bản gốc."]
    dong += [
        "",
        "TRẢ VỀ DUY NHẤT một khối JSON (không giải thích, không markdown), đúng khuôn:",
        '{"tieu_de": "...", "mo_ta": "mô tả đăng kèm, 1-3 câu", "hashtags": ["..."],',
        ' "phong_cach": "một câu mô tả thống nhất màu sắc, ánh sáng, chất liệu",',
        ' "nhan_vat": [{"ten": "...", "mo_ta": "ngoại hình CỤ THỂ (tuổi, tóc, trang phục, màu) để vẽ nhất quán"}],',
        ' "canh": [{"stt": 1, "loi_thoai": "câu đọc của cảnh này (rỗng nếu không có)",',
        '           "mo_ta_hinh": "tả khung hình bằng tiếng Anh cho AI vẽ ảnh: bối cảnh, nhân vật, góc máy, ánh sáng",',
        '           "chuyen_dong": "tả chuyển động máy và hành động bằng tiếng Anh cho AI làm video",',
        '           "nhan_vat": ["tên nhân vật có trong cảnh"], "giay": 6}]}',
        "",
        "Quy tắc: cảnh đầu phải có móc câu giữ người xem trong 3 giây đầu. Lời thoại ngắn, đọc kịp trong thời lượng "
        f"cảnh (khoảng {TU_MOI_GIAY} từ/giây). Mô tả hình luôn nhắc lại ngoại hình nhân vật để các cảnh nhất quán. "
        "Không đưa chữ hay logo vào hình.",
    ]
    return "\n".join(dong)


def doc_json(text: str) -> dict:
    s = str(text or "")
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s.strip(), flags=re.M)
    a, b = s.find("{"), s.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("Engine không trả về JSON kịch bản.")
    try:
        return json.loads(s[a:b + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON kịch bản hỏng: {e}")


def lam_sach(d: dict, p: dict) -> dict:
    """Chuẩn hoá kịch bản: số cảnh liên tục, thời lượng trong khoảng, thoại không dài quá cảnh."""
    canh_tho = [c for c in (d.get("canh") or []) if isinstance(c, dict)]
    if not canh_tho:
        raise ValueError("Kịch bản không có cảnh nào.")
    canh = []
    for i, c in enumerate(canh_tho[:24], 1):
        try:
            g = float(c.get("giay") or 6)
        except (TypeError, ValueError):
            g = 6.0
        g = max(GIAY_TOI_THIEU_MOT_CANH, min(g, GIAY_TOI_DA_MOT_CANH))
        thoai = re.sub(r"\s+", " ", str(c.get("loi_thoai") or "")).strip()
        tu = thoai.split()
        toi_da = int(g * TU_MOI_GIAY)
        if len(tu) > toi_da:
            thoai = " ".join(tu[:toi_da]).rstrip(",;:") + "..."
        mo_ta = str(c.get("mo_ta_hinh") or "").strip()[:900]
        if not mo_ta:
            raise ValueError(f"Cảnh {i} thiếu mô tả hình.")
        canh.append({"stt": i, "loi_thoai": thoai, "mo_ta_hinh": mo_ta,
                     "chuyen_dong": str(c.get("chuyen_dong") or "").strip()[:600],
                     "nhan_vat": [str(x)[:60] for x in (c.get("nhan_vat") or []) if x][:4],
                     "giay": g, "anh": "", "video": "", "giong": "", "trang_thai": "cho", "loi": ""})
    tags = [re.sub(r"[^\w]", "", str(h).lstrip("#")) for h in (d.get("hashtags") or [])]
    return {
        "kich_ban": {"tieu_de": str(d.get("tieu_de") or p.get("ten") or "")[:100],
                     "mo_ta": str(d.get("mo_ta") or "")[:800],
                     "hashtags": [t for t in tags if t][:12],
                     "phong_cach": str(d.get("phong_cach") or p.get("phong_cach") or "")[:400]},
        "nhan_vat": [{"ten": str(n.get("ten") or "")[:60], "mo_ta": str(n.get("mo_ta") or "")[:500], "anh": ""}
                     for n in (d.get("nhan_vat") or []) if isinstance(n, dict) and n.get("ten")][:4],
        "canh": canh,
    }


AskFn = Callable[[str, str, List[str]], Awaitable[str]]


async def lap(pid: str, ask: AskFn, chep_vao_brain: Callable[[str, List[Path]], List[str]]) -> dict:
    """Lập kịch bản cho dự án, ghi vào kho. `ask(yeu_cau, brain, [])` trả chữ của engine;
    `chep_vao_brain(brain, files)` đặt file tham khảo vào brain và trả đường dẫn tương đối."""
    p = kho.doc(pid)
    if not p:
        raise ValueError("Không có dự án này.")
    kho.dat_trang_thai(pid, "dang_lap_kich_ban")
    base = kho.thu_muc(pid)
    anh = [base / t["rel"] for t in p.get("tai_lieu") or [] if t.get("loai") == "anh"][:6]
    khung: List[Path] = []
    for t in [t for t in p.get("tai_lieu") or [] if t.get("loai") == "video"][:2]:
        khung += await trich_khung(base / t["rel"], base / "tai-lieu" / "khung")
    rel_anh = chep_vao_brain(p.get("brain") or "brain", anh) if anh else []
    rel_khung = chep_vao_brain(p.get("brain") or "brain", khung[:MAX_KHUNG]) if khung else []
    yc = dung_yeu_cau(p, rel_anh, rel_khung)
    try:
        tra = await ask(yc, p.get("brain") or "brain", rel_anh + rel_khung)
        kq = lam_sach(doc_json(tra), p)
    except ValueError as e:
        # Một lần thử lại có kèm lý do: engine hay quên khuôn JSON ở lần đầu.
        kho.nhat_ky(pid, f"Kịch bản lần 1 chưa đạt ({e}), thử lại.", "warn")
        tra = await ask(yc + f"\n\nLẦN TRƯỚC LỖI: {e}. Chỉ trả đúng khối JSON theo khuôn.", p.get("brain") or "brain", rel_anh + rel_khung)
        kq = lam_sach(doc_json(tra), p)
    kho.cap_nhat(pid, **kq)
    kho.dat_trang_thai(pid, "kich_ban_xong")
    kho.nhat_ky(pid, f"Đã lập kịch bản: {len(kq['canh'])} cảnh.")
    return kq
