"""Đăng video lên nền tảng. Giai đoạn 1: YouTube (video thường và Shorts) và Facebook Reels.

TikTok, Instagram, X, Threads, Zalo chưa có ở đây và nói THẲNG là chưa hỗ trợ, thay vì giả vờ
đăng được: mỗi nơi cần một đường khác hẳn (TikTok bắt app qua kiểm duyệt mới đăng công khai,
Instagram Reels cần video nằm ở một URL công khai, X tính phí API, Zalo cá nhân không có API
đăng bài). Xem `HO_TRO`.

Đăng bài là hành động THẬT và không rút lại được qua API này, nên mọi lỗi mạng giữa chừng được
báo rõ "chưa rõ đã đăng hay chưa" thay vì tự thử lại mù quáng (tự thử lại có thể đăng trùng).
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Dict, Optional

import httpx

from . import khoa, kho

HO_TRO = {"youtube": True, "youtube_short": True, "facebook_reel": True,
          "tiktok": False, "zalo": False, "instagram": False, "x": False, "threads": False}
LY_DO_CHUA = {
    "tiktok": "TikTok chỉ cho đăng công khai qua API sau khi ứng dụng được TikTok duyệt. Chưa làm ở bản này.",
    "instagram": "Instagram Reels cần video nằm ở một đường link công khai. Chưa làm ở bản này.",
    "x": "X tính phí API đăng video. Chưa làm ở bản này.",
    "threads": "Threads chưa làm ở bản này.",
    "zalo": "Zalo cá nhân không có API đăng bài lên nhật ký. Chưa làm ở bản này.",
}
GRAPH = "https://graph.facebook.com/v25.0"
RUPLOAD = "https://rupload.facebook.com/video-upload/v25.0"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
YT_UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
YT_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
TIMEOUT = httpx.Timeout(600.0, connect=30.0)


class LoiDang(Exception):
    def __init__(self, msg: str, chua_ro: bool = False):
        super().__init__(msg)
        self.chua_ro = chua_ro      # True: lỗi xảy ra SAU khi gửi, chưa biết bài đã lên hay chưa


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT)


def _loi(ten: str, r: httpx.Response) -> LoiDang:
    mo_ta = ""
    try:
        d = r.json()
        e = d.get("error")
        mo_ta = str((e.get("message") if isinstance(e, dict) else e) or d.get("error_description") or "")[:200]
    except Exception:
        mo_ta = (r.text or "")[:200]
    return LoiDang(f"{ten} trả lỗi {r.status_code}" + (f": {mo_ta}" if mo_ta else ""))


def tieu_de_va_mo_ta(p: dict, short: bool = False) -> tuple:
    kb = p.get("kich_ban") or {}
    tieu = (kb.get("tieu_de") or p.get("ten") or "Video")[:90]
    tags = " ".join("#" + t for t in (kb.get("hashtags") or [])[:10])
    if short:
        tags = (tags + " #Shorts").strip()
    mo = ((kb.get("mo_ta") or "") + ("\n\n" + tags if tags else "")).strip()
    return tieu[:100], mo[:4500]


# ============================================================ YouTube
def youtube_auth_url(redirect_uri: str, state: str) -> str:
    v = khoa.lay("youtube")
    if not v.get("client_id") or not v.get("client_secret"):
        raise LoiDang("Nhập Client ID và Client Secret của Google Cloud trước khi kết nối YouTube.")
    q = {"client_id": v["client_id"], "redirect_uri": redirect_uri, "response_type": "code",
         "scope": YT_SCOPE + " https://www.googleapis.com/auth/youtube.readonly", "access_type": "offline",
         "prompt": "consent", "state": state}
    return GOOGLE_AUTH + "?" + urllib.parse.urlencode(q)


async def youtube_doi_code(code: str, redirect_uri: str) -> None:
    v = khoa.lay("youtube")
    async with _client() as c:
        r = await c.post(GOOGLE_TOKEN, data={"code": code, "client_id": v.get("client_id", ""),
                                             "client_secret": v.get("client_secret", ""),
                                             "redirect_uri": redirect_uri, "grant_type": "authorization_code"})
    if r.status_code >= 400:
        raise _loi("Google", r)
    rt = r.json().get("refresh_token")
    if not rt:
        raise LoiDang("Google không cấp refresh token. Thu hồi quyền của ứng dụng ở tài khoản Google rồi kết nối lại.")
    khoa.dat("youtube", {"refresh_token": rt})


async def _yt_access_token() -> str:
    v = khoa.lay("youtube")
    if not v.get("refresh_token"):
        raise LoiDang("Chưa kết nối YouTube.")
    async with _client() as c:
        r = await c.post(GOOGLE_TOKEN, data={"client_id": v.get("client_id", ""), "client_secret": v.get("client_secret", ""),
                                             "refresh_token": v["refresh_token"], "grant_type": "refresh_token"})
    if r.status_code >= 400:
        raise _loi("Google", r)
    return r.json()["access_token"]


async def dang_youtube(p: dict, video: Path, short: bool = False) -> dict:
    tok = await _yt_access_token()
    tieu, mo = tieu_de_va_mo_ta(p, short)
    size = video.stat().st_size
    body = {"snippet": {"title": tieu, "description": mo, "categoryId": "22",
                        "tags": [t for t in ((p.get("kich_ban") or {}).get("hashtags") or [])][:15]},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    async with _client() as c:
        r = await c.post(YT_UPLOAD, params={"uploadType": "resumable", "part": "snippet,status"}, json=body,
                         headers={"Authorization": f"Bearer {tok}", "X-Upload-Content-Length": str(size),
                                  "X-Upload-Content-Type": "video/mp4"})
        if r.status_code >= 400:
            raise _loi("YouTube", r)
        url = r.headers.get("location")
        if not url:
            raise LoiDang("YouTube không trả địa chỉ tải lên.")
        try:
            up = await c.put(url, content=video.read_bytes(), headers={"Content-Type": "video/mp4",
                                                                       "Content-Length": str(size)})
        except httpx.HTTPError as e:
            raise LoiDang(f"Mất kết nối khi tải video lên YouTube ({type(e).__name__}). Chưa rõ video đã lên hay chưa, "
                          "hãy kiểm tra trong YouTube Studio trước khi thử lại.", chua_ro=True)
    if up.status_code >= 400:
        raise _loi("YouTube", up)
    vid = (up.json() or {}).get("id")
    if not vid:
        raise LoiDang("YouTube nhận file nhưng không trả id video.", chua_ro=True)
    return {"id": vid, "url": (f"https://www.youtube.com/shorts/{vid}" if short else f"https://www.youtube.com/watch?v={vid}")}


# ============================================================ Facebook Reels
async def dang_facebook_reel(p: dict, video: Path) -> dict:
    v = khoa.lay("facebook")
    page, tok = v.get("page_id", ""), v.get("page_token", "")
    if not page or not tok:
        raise LoiDang("Chưa nhập Page ID và Page Access Token của Facebook.")
    tieu, mo = tieu_de_va_mo_ta(p)
    size = video.stat().st_size
    async with _client() as c:
        r = await c.post(f"{GRAPH}/{page}/video_reels", data={"upload_phase": "start", "access_token": tok})
        if r.status_code >= 400:
            raise _loi("Facebook", r)
        vid = str((r.json() or {}).get("video_id") or "")
        if not vid:
            raise LoiDang("Facebook không trả video_id.")
        up_url = (r.json() or {}).get("upload_url") or f"{RUPLOAD}/{vid}"
        try:
            u = await c.post(up_url, content=video.read_bytes(),
                             headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size),
                                      "Content-Type": "application/octet-stream"})
        except httpx.HTTPError as e:
            raise LoiDang(f"Mất kết nối khi tải video lên Facebook ({type(e).__name__}).")
        if u.status_code >= 400 or not (u.json() or {}).get("success", True):
            raise _loi("Facebook (tải lên)", u)
        try:
            f = await c.post(f"{GRAPH}/{page}/video_reels", data={
                "upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                "description": mo, "title": tieu, "access_token": tok})
        except httpx.HTTPError as e:
            raise LoiDang(f"Mất kết nối ở bước chốt đăng Reel ({type(e).__name__}). Chưa rõ Reel đã lên hay chưa, "
                          "hãy kiểm tra trên Trang trước khi thử lại.", chua_ro=True)
    if f.status_code >= 400:
        raise _loi("Facebook (chốt đăng)", f)
    return {"id": vid, "url": f"https://www.facebook.com/reel/{vid}"}


async def dang(nen_tang: str, p: dict, video: Path) -> dict:
    """Đăng một nền tảng. Ném LoiDang khi hỏng. Trả {id, url}."""
    if not video.is_file():
        raise LoiDang("Chưa có file video để đăng.")
    if not HO_TRO.get(nen_tang):
        raise LoiDang(LY_DO_CHUA.get(nen_tang) or f"Nền tảng '{nen_tang}' chưa hỗ trợ.")
    if nen_tang == "youtube":
        return await dang_youtube(p, video, False)
    if nen_tang == "youtube_short":
        if p.get("ti_le") != "9:16":
            raise LoiDang("YouTube Shorts cần video dọc 9:16.")
        return await dang_youtube(p, video, True)
    if nen_tang == "facebook_reel":
        if p.get("ti_le") != "9:16":
            raise LoiDang("Facebook Reels cần video dọc 9:16.")
        return await dang_facebook_reel(p, video)
    raise LoiDang("Nền tảng chưa hỗ trợ.")
