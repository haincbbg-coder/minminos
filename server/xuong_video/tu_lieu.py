"""Dựng tư liệu thật trong MinMin; không gửi ảnh sản phẩm sang model tạo ảnh/video.

Thiết kế tham khảo workflow MoneyPrinterTurbo; implementation dùng FFmpeg sẵn có.
Đường dẫn đầu vào chỉ lấy từ manifest tài liệu của chính dự án, không nhận URL.
"""
from __future__ import annotations

import asyncio
import math
import re
import uuid

from . import ghep, kho, ncc, khoa

GIONG = ("vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural", "en-US-JennyNeural", "en-US-GuyNeural")
_sem = None


def so(v, mac_dinh, thap, cao):
    try:
        n = float(v)
        return max(thap, min(cao, n)) if math.isfinite(n) else mac_dinh
    except (TypeError, ValueError):
        return mac_dinh


def chuan_hoa(p: dict, data: dict, *, nhap=False) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Bản dựng không hợp lệ.")
    tep = {x["rel"]: x for x in p.get("tai_lieu", [])}
    canh = data.get("canh")
    if not isinstance(canh, list) or not (0 if nhap else 1) <= len(canh) <= 30:
        raise ValueError("Chọn từ 1 đến 30 ảnh hoặc clip cho bản dựng.")
    ra = []
    for c in canh:
        if not isinstance(c, dict) or c.get("rel") not in tep or tep[c["rel"]]["loai"] not in ("anh", "video"):
            raise ValueError("Cảnh phải dùng ảnh/clip đã tải vào dự án này.")
        ra.append({"rel": c["rel"], "giay": so(c.get("giay"), 5, 1, 30),
                   "chu": str(c.get("chu") or "").strip()[:600]})
    if sum(c["giay"] for c in ra) > 180:
        raise ValueError("Tổng thời lượng cảnh không quá 180 giây.")
    for key in ("nhac", "loi_doc"):
        rel = data.get(key) or ""
        if rel and (rel not in tep or tep[rel]["loai"] != "audio"):
            raise ValueError("Nhạc và lời đọc phải là âm thanh của dự án này.")
    mau = str(data.get("mau") or "#FFFFFF")
    return {"canh": ra, "nhac": data.get("nhac") or "", "loi_doc": data.get("loi_doc") or "",
            "giong": data.get("giong") if data.get("giong") in ("khong", "edge", "elevenlabs", "tep") else "khong",
            "voice": data.get("voice") if data.get("voice") in GIONG else GIONG[0],
            "toc_do": so(data.get("toc_do"), 1, .75, 1.25),
            "am_nhac": so(data.get("am_nhac"), .15, 0, 1),
            "am_giong": so(data.get("am_giong"), 1, 0, 2),
            "phu_de": data.get("phu_de", True) is True,
            "co_chu": int(so(data.get("co_chu"), 18, 10, 32)),
            "mau": mau if re.fullmatch(r"#[0-9a-fA-F]{6}", mau) else "#FFFFFF",
            "vi_tri": "tren" if data.get("vi_tri") == "tren" else "duoi",
            "khung": "crop" if data.get("khung") == "crop" else "fit"}


async def _ff(args):
    safe = []
    for arg in args:
        if arg == "-i":
            safe.extend(["-protocol_whitelist", "file,pipe"])
        safe.append(arg)
    return await ghep._chay(safe)


async def _edge(chu, voice, rate, dich):
    import edge_tts
    moc = []
    with dich.open("wb") as f:
        async for item in edge_tts.Communicate(chu, voice, rate=f"{round((rate-1)*100):+d}%").stream():
            if item["type"] == "audio":
                f.write(item["data"])
            elif item["type"] in ("WordBoundary", "SentenceBoundary"):
                moc.append((item["offset"] / 10_000_000, item["duration"] / 10_000_000, item["text"]))
    if not dich.stat().st_size:
        raise ValueError("Dịch vụ giọng đọc không trả âm thanh. Chọn audio riêng hoặc thử lại.")
    return moc


def _srt(doan):
    # Không cho dấu HTML/ASS từ lời thoại trở thành lệnh định dạng.
    return "\n".join(f"{i}\n{ghep._thoi_gian_srt(t)} --> {ghep._thoi_gian_srt(t+d)}\n"
                     f"{re.sub(r'[<>｛｝{}]', '', chu).replace(chr(10), ' ')}\n"
                     for i, (t, d, chu) in enumerate(doan, 1) if chu.strip() and d > 0)


async def dung(pid: str):
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(1)
    async with _sem:
        return await _dung(pid)


async def _dung(pid):
    p = kho.doc(pid)
    b = chuan_hoa(p, p.get("ban_dung") or {})
    if b["giong"] == "tep" and not b["loi_doc"]:
        raise ValueError("Chọn file lời đọc hoặc chuyển sang Không lời đọc.")
    # Mỗi lượt có đầu ra riêng: bản cũ vẫn mở được trong lúc dựng bản mới/lỗi.
    rel_dir = "ban-dung/" + uuid.uuid4().hex[:12]
    thu = kho.thu_muc(pid) / rel_dir
    thu.mkdir(parents=True)
    W, H = ghep.KICH_CO.get(p.get("ti_le"), ghep.KICH_CO["9:16"])
    segs, doan, tong = [], [], 0.0
    for i, c in enumerate(b["canh"]):
        kho.nhat_ky(pid, f"Đang dựng cảnh {i+1}/{len(b['canh'])}.")
        f = kho.duong_dan_file(pid, c["rel"])
        if not f:
            raise ValueError("Không thấy tư liệu của cảnh " + str(i+1))
        am, moc = None, []
        dai = c["giay"]
        if c["chu"] and b["giong"] in ("edge", "elevenlabs"):
            am = thu / f"voice-{i}.mp3"
            if b["giong"] == "edge":
                try:
                    moc = await asyncio.wait_for(_edge(c["chu"], b["voice"], b["toc_do"], am), 120)
                except Exception:
                    # Provider exceptions may embed signed URLs. Never expose those in project logs.
                    raise ValueError("Không kết nối được giọng Edge TTS. Thử lại sau hoặc chọn file lời đọc / ElevenLabs đã kết nối.") from None
            else:
                am.write_bytes(await ncc.tao_giong(c["chu"], khoa.cai_dat()["giong"]))
                if b["toc_do"] != 1:
                    adjusted = thu / f"voice-{i}-speed.mp3"
                    await _ff(["ffmpeg", "-y", "-i", str(am), "-af", f"atempo={b['toc_do']}", str(adjusted)])
                    am = adjusted
            ad = await ghep.do_dai(am)
            if ad <= 0:
                raise ValueError("Không đọc được âm thanh lời đọc.")
            dai = max(dai, ad + .2)
        if tong + dai > 300:
            raise ValueError("Lời đọc làm video dài quá 5 phút. Rút gọn lời thoại rồi dựng lại.")
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2"
              if b["khung"] == "fit" else f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}")
        vf += ",setsar=1,fps=30,format=yuv420p"
        args = ["ffmpeg", "-y", "-nostdin"]
        if f.suffix.lower() in kho.DUOI_ANH:
            args += ["-loop", "1", "-i", str(f)]
        else:
            args += ["-stream_loop", "-1", "-i", str(f)]
        args += ["-i", str(am)] if am else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
        out = thu / f"scene-{i}.mp4"
        args += ["-filter_complex", f"[0:v]{vf}[v];[1:a]aresample=44100,apad[a]",
                 "-map", "[v]", "-map", "[a]", "-t", f"{dai:.3f}", "-c:v", "libx264",
                 "-threads", "2", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-ac", "2", str(out)]
        await _ff(args)
        segs.append(out)
        if moc:
            for t, d, chu in moc:
                if t < dai:
                    doan.append((tong+t, min(max(d, .1), dai-t), chu))
        elif c["chu"]:
            doan.append((tong, dai, c["chu"]))
        tong += dai
    ds = thu / "concat.txt"
    ds.write_text("".join(f"file '{x.name}'\n" for x in segs), encoding="utf-8")
    raw = thu / "raw.mp4"
    await _ff(["ffmpeg", "-y", "-f", "concat", "-safe", "1", "-i", str(ds), "-c", "copy", str(raw)])
    args = ["ffmpeg", "-y", "-nostdin", "-i", str(raw)]
    audio_index = 0
    if b["giong"] == "tep":
        f = kho.duong_dan_file(pid, b["loi_doc"])
        if not f or await ghep.do_dai(f) <= 0:
            raise ValueError("File lời đọc không hợp lệ.")
        args += ["-i", str(f)]
        audio_index = 1
    filters = [f"[{audio_index}:a]volume={b['am_giong']},apad[a]"]
    if b["nhac"]:
        f = kho.duong_dan_file(pid, b["nhac"])
        if not f or await ghep.do_dai(f) <= 0:
            raise ValueError("File nhạc nền không hợp lệ.")
        args += ["-stream_loop", "-1", "-i", str(f)]
        filters += [f"[{audio_index+1}:a]volume={b['am_nhac']}[bg]",
                    "[a][bg]amix=inputs=2:duration=first:normalize=0[mix]"]
    args += ["-filter_complex", ";".join(filters), "-map", "0:v",
             "-map", "[mix]" if b["nhac"] else "[a]"]
    srt = thu / "subtitles.srt"
    if b["phu_de"] and doan:
        srt.write_text(_srt(doan), encoding="utf-8")
        color = b["mau"][1:]
        ass = "&H00" + color[4:6] + color[2:4] + color[:2]
        path = str(srt).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        args += ["-vf", f"subtitles='{path}':force_style='FontName=DejaVu Sans,FontSize={b['co_chu']},"
                 f"PrimaryColour={ass},Outline=2,MarginV=60,Alignment={8 if b['vi_tri']=='tren' else 2}'",
                 "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "23"]
    else:
        args += ["-c:v", "copy"]
    final = thu / "final.mp4"
    args += ["-t", f"{tong:.3f}", "-c:a", "aac", "-movflags", "+faststart", str(final)]
    await _ff(args)
    result = {"video": rel_dir + "/final.mp4", "srt": rel_dir + "/subtitles.srt" if srt.exists() else "",
              "giay": round(tong, 1), "kich_co": f"{W}x{H}", "phu_de": srt.exists()}
    kho.cap_nhat(pid, ket_qua=result)
    return result
