"""Ghép các cảnh thành một video hoàn chỉnh bằng ffmpeg: chuẩn hoá khung hình, gắn giọng đọc,
kéo dài cảnh cho vừa lời thoại, ghép nối, đốt phụ đề, lấy ảnh bìa."""
from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import List, Optional

import winproc
from . import kho

KICH_CO = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
FPS = 30
CHAY_TOI_DA = 600


class LoiGhep(Exception):
    pass


async def _chay(argv: List[str], han: int = CHAY_TOI_DA) -> str:
    pr = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                              **winproc.kwargs_no_window())
    try:
        o, e = await asyncio.wait_for(pr.communicate(), han)
    except asyncio.TimeoutError:
        pr.kill()
        raise LoiGhep("ffmpeg chạy quá lâu.")
    if pr.returncode != 0:
        raise LoiGhep("ffmpeg lỗi: " + (e or b"").decode("utf-8", "replace").strip()[-400:])
    return (o or b"").decode("utf-8", "replace")


async def do_dai(p: Path) -> float:
    try:
        o = await _chay(["ffprobe", "-protocol_whitelist", "file,pipe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(p)], 60)
        return float(o.strip() or 0)
    except (LoiGhep, ValueError):
        return 0.0


def _thoi_gian_srt(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def dung_srt(cac_doan: List[tuple]) -> str:
    """cac_doan: [(bat_dau_giay, dai_giay, chu)]. Chia thoại dài thành 2 dòng cho vừa màn dọc."""
    ra = []
    for i, (bd, dai, chu) in enumerate([d for d in cac_doan if d[2].strip()], 1):
        tu = chu.split()
        if len(tu) > 7:
            nua = (len(tu) + 1) // 2
            chu = " ".join(tu[:nua]) + "\n" + " ".join(tu[nua:])
        ra.append(f"{i}\n{_thoi_gian_srt(bd)} --> {_thoi_gian_srt(bd + dai)}\n{chu}\n")
    return "\n".join(ra)


def _loc_srt(srt: Path) -> str:
    # đường dẫn trong bộ lọc ffmpeg cần thoát dấu ':' và '\' (Windows)
    s = str(srt).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    return f"subtitles='{s}':force_style='FontName=DejaVu Sans,FontSize=14,Bold=1,Outline=2,Shadow=0,MarginV=80,Alignment=2'"


async def ghep(pid: str, phu_de: bool = True) -> dict:
    """Ghép dự án. Trả {video, thumb, giay}. Cần mọi cảnh đã có video."""
    if not shutil.which("ffmpeg"):
        raise LoiGhep("Máy chủ chưa cài ffmpeg nên không ghép được video.")
    p = kho.doc(pid)
    if not p:
        raise LoiGhep("Không có dự án này.")
    canh = [c for c in p.get("canh") or []]
    thieu = [c["stt"] for c in canh if not c.get("video")]
    if not canh or thieu:
        raise LoiGhep("Còn cảnh chưa có video: " + ", ".join(map(str, thieu)) if thieu else "Dự án chưa có cảnh.")
    base = kho.thu_muc(pid)
    tmp = base / "ghep"
    tmp.mkdir(exist_ok=True)
    W, H = KICH_CO.get(p.get("ti_le"), KICH_CO["9:16"])
    segs, doan, t = [], [], 0.0
    for c in canh:
        clip = base / c["video"]
        giong = (base / c["giong"]) if c.get("giong") and (base / c["giong"]).is_file() else None
        dc = await do_dai(clip) or float(c.get("giay") or 6)
        dg = await do_dai(giong) if giong else 0.0
        tong = max(dc, dg + 0.25) if giong else dc
        them = max(0.0, tong - dc)
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1"
              + (f",tpad=stop_mode=clone:stop_duration={them:.3f}" if them > 0.05 else ""))
        seg = tmp / f"seg-{c['stt']:02d}.mp4"
        argv = ["ffmpeg", "-y", "-i", str(clip)]
        if giong:
            argv += ["-i", str(giong)]
            af = "aresample=44100,apad"
            amap = "[a]"
            fc = f"[0:v]{vf}[v];[1:a]{af}[a]"
        else:
            argv += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            fc = f"[0:v]{vf}[v];[1:a]anull[a]"
            amap = "[a]"
        argv += ["-filter_complex", fc, "-map", "[v]", "-map", amap, "-t", f"{tong:.3f}",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", str(seg)]
        await _chay(argv)
        segs.append(seg)
        doan.append((t + 0.15, max(0.5, (dg or tong) ), c.get("loi_thoai") or ""))
        t += tong
    ds = tmp / "ds.txt"
    ds.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), "utf-8")
    ghep_tho = tmp / "ghep.mp4"
    await _chay(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(ds), "-c", "copy", str(ghep_tho)])
    out_dir = base / "ket-qua"
    out_dir.mkdir(exist_ok=True)
    final = out_dir / "final.mp4"
    srt_txt = dung_srt(doan) if phu_de else ""
    da_dot = False
    if srt_txt:
        srt = tmp / "phu-de.srt"
        srt.write_text(srt_txt, "utf-8")
        try:
            await _chay(["ffmpeg", "-y", "-i", str(ghep_tho), "-vf", _loc_srt(srt), "-c:v", "libx264", "-preset",
                         "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
                         str(final)])
            da_dot = True
        except LoiGhep:
            da_dot = False      # thiếu libass/font: vẫn ra video, chỉ không có phụ đề cứng
    if not da_dot:
        await _chay(["ffmpeg", "-y", "-i", str(ghep_tho), "-c", "copy", "-movflags", "+faststart", str(final)])
    thumb = out_dir / "thumb.jpg"
    try:
        await _chay(["ffmpeg", "-y", "-ss", "1", "-i", str(final), "-frames:v", "1", "-q:v", "3", str(thumb)], 60)
    except LoiGhep:
        thumb = None
    kq = {"video": "ket-qua/final.mp4", "thumb": ("ket-qua/thumb.jpg" if thumb else ""),
          "giay": round(t, 1), "phu_de": da_dot, "kich_co": f"{W}x{H}"}
    kho.cap_nhat(pid, ket_qua=kq)
    return kq
