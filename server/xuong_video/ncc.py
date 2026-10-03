"""Nhà cung cấp tạo ảnh, video, giọng. Gọi thẳng API chính thức, không qua trình duyệt.

  ảnh   : Gemini (Nano Banana, `generateContent`), OpenAI (`/v1/images/*`)
  video : fal.ai (một khoá, nhiều model: Kling, Seedance, Veo...) qua hàng đợi `queue.fal.run`
  giọng : ElevenLabs

Mã model là CÀI ĐẶT chứ không đóng cứng: nhà cung cấp đổi tên model mỗi vài tháng, chủ sửa ở
trang Cài đặt mà không cần chờ bản MinMin mới. Các mặc định trong `khoa.MAC_DINH_CAI_DAT` lấy
từ tài liệu chính thức lúc viết (10/2026).

Mọi hàm HTTP đi qua `_client()` để test thay bằng transport giả. KHÔNG có khoá thật trong CI,
nên các adapter này được kiểm bằng phản hồi mô phỏng đúng cấu trúc tài liệu, chưa được chạy với
nhà cung cấp thật trong môi trường phát triển.
"""
from __future__ import annotations

import asyncio
import base64
import mimetypes
import time
from pathlib import Path
from typing import List, Optional

import httpx

from . import khoa

FAL_QUEUE = "https://queue.fal.run"
GEMINI = "https://generativelanguage.googleapis.com/v1beta"
OPENAI = "https://api.openai.com/v1"
ELEVEN = "https://api.elevenlabs.io/v1"
HAN_CHO_VIDEO = 20 * 60          # giây tối đa chờ một clip
NHIP_HOI = 5.0                   # giây giữa hai lần hỏi trạng thái
TIMEOUT = httpx.Timeout(120.0, connect=20.0)


class LoiNcc(Exception):
    """Lỗi của nhà cung cấp, thông điệp đã dịch ra tiếng Việt để hiện cho chủ."""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT)


async def _ngu(giay: float) -> None:      # tách ra để test không phải chờ thật
    await asyncio.sleep(giay)


def _loi_http(ten: str, r: httpx.Response) -> LoiNcc:
    mo_ta = ""
    try:
        d = r.json()
        mo_ta = str((d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else
                    d.get("detail") or d.get("error") or d.get("message") or "")[:200]
    except Exception:
        mo_ta = (r.text or "")[:200]
    huong = {401: "khoá API sai hoặc hết hạn", 403: "khoá chưa có quyền dùng model này",
             402: "hết số dư tài khoản", 429: "bị giới hạn tốc độ hoặc hết hạn mức"}.get(r.status_code, "")
    return LoiNcc(f"{ten} trả lỗi {r.status_code}" + (f" ({huong})" if huong else "") + (f": {mo_ta}" if mo_ta else ""))


def _can_khoa(dv: str, truong: str = "api_key") -> str:
    v = khoa.lay(dv).get(truong, "")
    if not v:
        raise LoiNcc(f"Chưa nhập khoá {dv} ở trang Kết nối của Xưởng video.")
    return v


def _b64_tep(p: Path) -> tuple:
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    return mime, base64.b64encode(p.read_bytes()).decode("ascii")


# ============================================================ ẢNH
async def tao_anh(prompt: str, ti_le: str = "9:16", tham_chieu: Optional[List[Path]] = None,
                  cfg: Optional[dict] = None) -> bytes:
    cfg = cfg or khoa.cai_dat()["anh"]
    ncc = cfg.get("ncc") or "gemini"
    model = cfg.get("model") or ""
    tc = [Path(p) for p in (tham_chieu or []) if Path(p).is_file()][:4]
    if ncc == "gemini":
        return await _anh_gemini(prompt, ti_le, tc, model or "gemini-2.5-flash-image")
    if ncc == "openai":
        return await _anh_openai(prompt, ti_le, tc, model)
    raise LoiNcc(f"Nhà cung cấp ảnh '{ncc}' chưa được hỗ trợ.")


def _huong_ti_le(ti_le: str) -> str:
    return {"9:16": "vertical 9:16 portrait composition", "16:9": "horizontal 16:9 landscape composition",
            "1:1": "square 1:1 composition"}.get(ti_le, "")


async def _anh_gemini(prompt, ti_le, tc, model) -> bytes:
    key = _can_khoa("gemini")
    parts = [{"text": f"{prompt}\n\n{_huong_ti_le(ti_le)}. No text, no watermark, no captions in the image."}]
    for p in tc:
        mime, b64 = _b64_tep(p)
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})
    body = {"contents": [{"parts": parts}], "generationConfig": {"responseModalities": ["IMAGE"]}}
    async with _client() as c:
        r = await c.post(f"{GEMINI}/models/{model}:generateContent", json=body,
                         headers={"x-goog-api-key": key, "Content-Type": "application/json"})
    if r.status_code >= 400:
        raise _loi_http("Gemini", r)
    try:
        for cand in r.json().get("candidates") or []:
            for part in (cand.get("content") or {}).get("parts") or []:
                d = part.get("inlineData") or part.get("inline_data")
                if d and d.get("data"):
                    return base64.b64decode(d["data"])
    except Exception:
        pass
    raise LoiNcc("Gemini không trả về ảnh (có thể nội dung bị chặn an toàn). Thử sửa mô tả cảnh.")


def _kich_co_openai(ti_le: str) -> str:
    return {"9:16": "1024x1536", "16:9": "1536x1024", "1:1": "1024x1024"}.get(ti_le, "1024x1024")


async def _anh_openai(prompt, ti_le, tc, model) -> bytes:
    key = _can_khoa("openai")
    model = model or "gpt-image-1"
    h = {"Authorization": f"Bearer {key}"}
    async with _client() as c:
        if tc:
            files = [("image[]", (p.name, p.read_bytes(), mimetypes.guess_type(str(p))[0] or "image/png")) for p in tc]
            r = await c.post(f"{OPENAI}/images/edits", headers=h, files=files,
                             data={"model": model, "prompt": prompt, "size": _kich_co_openai(ti_le)})
        else:
            r = await c.post(f"{OPENAI}/images/generations", headers=h,
                             json={"model": model, "prompt": prompt, "size": _kich_co_openai(ti_le), "n": 1})
    if r.status_code >= 400:
        raise _loi_http("OpenAI", r)
    try:
        d = (r.json().get("data") or [{}])[0]
        if d.get("b64_json"):
            return base64.b64decode(d["b64_json"])
        if d.get("url"):
            async with _client() as c2:
                rr = await c2.get(d["url"])
            if rr.status_code < 400:
                return rr.content
    except Exception:
        pass
    raise LoiNcc("OpenAI không trả về ảnh.")


# ============================================================ VIDEO (fal.ai)
def _giay_gan_nhat(model: str, giay: float) -> object:
    """Mỗi model chỉ nhận vài độ dài và mỗi họ ghi khác kiểu (Veo: "8s", Kling: "5"/"10",
    Seedance: số nguyên). Chọn độ dài gần nhất mà model nhận."""
    m = model.lower()
    if "veo" in m:
        v = min((4, 6, 8), key=lambda x: abs(x - giay))
        return f"{v}s"
    if "kling" in m:
        return str(min((5, 10), key=lambda x: abs(x - giay)))
    if "seedance" in m:
        return str(max(3, min(int(round(giay)), 12)))
    return str(int(round(giay)))


def dung_tai_trong(model: str, prompt: str, anh_uri: str, giay: float, ti_le: str) -> dict:
    """Thân yêu cầu cho model fal. Tham số chung (prompt, image_url, duration, aspect_ratio) có
    mặt ở mọi họ model; mỗi họ chỉ khác kiểu giá trị."""
    body = {"prompt": prompt}
    if anh_uri and "text-to-video" not in model:
        body["image_url"] = anh_uri
    body["duration"] = _giay_gan_nhat(model, giay)
    if ti_le in ("9:16", "16:9", "1:1"):
        body["aspect_ratio"] = ti_le
    if "veo" in model.lower():
        body["generate_audio"] = False         # giọng đọc do ElevenLabs lo, tránh hai lớp tiếng
        body["resolution"] = "720p"
    return body


async def tao_video(prompt: str, anh: Optional[Path], giay: float, ti_le: str = "9:16",
                    cfg: Optional[dict] = None) -> bytes:
    cfg = cfg or khoa.cai_dat()["video"]
    if (cfg.get("ncc") or "fal") != "fal":
        raise LoiNcc(f"Nhà cung cấp video '{cfg.get('ncc')}' chưa được hỗ trợ (hiện dùng fal.ai).")
    model = (cfg.get("model") or "fal-ai/veo3.1/image-to-video").strip("/")
    key = _can_khoa("fal")
    uri = ""
    if anh and Path(anh).is_file():
        mime, b64 = _b64_tep(Path(anh))
        uri = f"data:{mime};base64,{b64}"
    if "text-to-video" not in model and not uri:
        raise LoiNcc("Model video này cần ảnh đầu vào nhưng cảnh chưa có ảnh.")
    h = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    body = dung_tai_trong(model, prompt, uri, giay, ti_le)
    async with _client() as c:
        r = await c.post(f"{FAL_QUEUE}/{model}", json=body, headers=h)
        if r.status_code >= 400:
            raise _loi_http("fal.ai", r)
        d = r.json()
        rid = d.get("request_id")
        st_url = d.get("status_url") or f"{FAL_QUEUE}/{model}/requests/{rid}/status"
        rs_url = d.get("response_url") or f"{FAL_QUEUE}/{model}/requests/{rid}"
        if not rid:
            raise LoiNcc("fal.ai không trả request_id.")
        han = time.monotonic() + HAN_CHO_VIDEO
        while True:
            if time.monotonic() > han:
                raise LoiNcc("fal.ai tạo video quá 20 phút chưa xong. Bấm thử lại cảnh này.")
            s = await c.get(st_url, headers=h)
            if s.status_code >= 400:
                raise _loi_http("fal.ai", s)
            if (s.json() or {}).get("status") == "COMPLETED":
                break
            await _ngu(NHIP_HOI)
        res = await c.get(rs_url, headers=h)
        if res.status_code >= 400:
            raise _loi_http("fal.ai", res)
        url = ((res.json() or {}).get("video") or {}).get("url")
        if not url:
            raise LoiNcc("fal.ai báo xong nhưng không có video (có thể bị bộ lọc an toàn chặn).")
        v = await c.get(url)
    if v.status_code >= 400 or not v.content:
        raise LoiNcc("Không tải được video đã tạo từ fal.ai.")
    return v.content


# ============================================================ GIỌNG
async def tao_giong(text: str, cfg: Optional[dict] = None) -> bytes:
    cfg = cfg or khoa.cai_dat()["giong"]
    if (cfg.get("ncc") or "elevenlabs") != "elevenlabs":
        raise LoiNcc(f"Nhà cung cấp giọng '{cfg.get('ncc')}' chưa được hỗ trợ.")
    key = _can_khoa("elevenlabs")
    voice = khoa.lay("elevenlabs").get("voice_id", "")
    if not voice:
        raise LoiNcc("Chưa nhập Voice ID của ElevenLabs.")
    async with _client() as c:
        r = await c.post(f"{ELEVEN}/text-to-speech/{voice}", params={"output_format": "mp3_44100_128"},
                         headers={"xi-api-key": key, "Content-Type": "application/json"},
                         json={"text": text, "model_id": cfg.get("model") or "eleven_multilingual_v2"})
    if r.status_code >= 400:
        raise _loi_http("ElevenLabs", r)
    if not r.content:
        raise LoiNcc("ElevenLabs trả file rỗng.")
    return r.content
