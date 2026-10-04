"""Đăng video lên nền tảng. Giai đoạn 1: YouTube (video thường và Shorts) và Facebook Reels.

TikTok, Instagram, X, Threads, Zalo chưa có ở đây và nói THẲNG là chưa hỗ trợ, thay vì giả vờ
đăng được: mỗi nơi cần một đường khác hẳn (TikTok bắt app qua kiểm duyệt mới đăng công khai,
Instagram Reels cần video nằm ở một URL công khai, X tính phí API, Zalo cá nhân không có API
đăng bài). Xem `HO_TRO`.

Đăng bài là hành động THẬT và không rút lại được qua API này, nên mọi lỗi mạng giữa chừng được
báo rõ "chưa rõ đã đăng hay chưa" thay vì tự thử lại mù quáng (tự thử lại có thể đăng trùng).
"""
from __future__ import annotations

import asyncio
import urllib.parse
from pathlib import Path
from typing import Dict, Optional

import httpx

from . import khoa, kho

HO_TRO = {"youtube": True, "youtube_short": True, "facebook_reel": True,
          "tiktok": True, "zalo": False, "instagram": False, "x": False, "threads": False}
LY_DO_CHUA = {
    "instagram": "Instagram Reels cần video nằm ở một đường link công khai. Chưa làm ở bản này.",
    "x": "X tính phí API đăng video. Chưa làm ở bản này.",
    "threads": "Threads chưa làm ở bản này.",
    "zalo": "Zalo cá nhân không có API đăng bài lên nhật ký. Chưa làm ở bản này.",
}
GRAPH = "https://graph.facebook.com/v25.0"
RUPLOAD = "https://rupload.facebook.com/video-upload/v25.0"
TT_API = "https://open.tiktokapis.com/v2"
TT_AUTH = "https://www.tiktok.com/v2/auth/authorize/"
TT_CHUNK = 10 * 1024 * 1024          # TikTok: mỗi mảnh 5-64MB, mảnh cuối được dôi tới 128MB
TT_MIN = 5 * 1024 * 1024
TT_RIENG_TU = ("SELF_ONLY", "FOLLOWER_OF_CREATOR", "MUTUAL_FOLLOW_FRIENDS", "PUBLIC_TO_EVERYONE")
TT_HAN_CHO = 240.0
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


async def _ngu(giay: float) -> None:       # tách ra để test không phải chờ thật
    await asyncio.sleep(giay)


# ============================================================ TikTok
def tiktok_auth_url(redirect_uri: str, state: str) -> str:
    v = khoa.lay("tiktok")
    if not v.get("client_key") or not v.get("client_secret"):
        raise LoiDang("Nhập Client key và Client secret của ứng dụng TikTok (developers.tiktok.com) trước khi kết nối.")
    q = {"client_key": v["client_key"], "scope": "video.publish", "response_type": "code",
         "redirect_uri": redirect_uri, "state": state}
    return TT_AUTH + "?" + urllib.parse.urlencode(q)


def _tt_loi(r: httpx.Response) -> LoiDang:
    code = msg = ""
    try:
        e = (r.json() or {}).get("error") or {}
        code, msg = str(e.get("code") or ""), str(e.get("message") or "")
    except Exception:
        msg = (r.text or "")[:200]
    huong = {
        "unaudited_client_can_only_post_to_private_accounts":
            "ứng dụng TikTok chưa qua kiểm duyệt (audit) nên chỉ đăng được lên tài khoản đặt chế độ riêng tư",
        "privacy_level_option_mismatch": "chế độ hiển thị không khớp với lựa chọn tài khoản cho phép",
        "spam_risk_too_many_posts": "đã chạm giới hạn số bài mỗi ngày của TikTok",
        "reached_active_user_cap": "đã hết hạn mức người dùng trong ngày của ứng dụng",
        "access_token_invalid": "token hết hạn hoặc sai, hãy kết nối lại TikTok",
        "scope_not_authorized": "chưa cấp quyền video.publish, hãy kết nối lại TikTok",
        "rate_limit_exceeded": "gọi quá nhanh, thử lại sau ít phút",
    }.get(code, "")
    return LoiDang(f"TikTok trả lỗi {r.status_code}" + (f" ({huong})" if huong else "") + (f": {msg}" if msg and not huong else ""))


async def tiktok_doi_code(code: str, redirect_uri: str) -> None:
    v = khoa.lay("tiktok")
    async with _client() as c:
        r = await c.post(TT_API + "/oauth/token/", data={
            "client_key": v.get("client_key", ""), "client_secret": v.get("client_secret", ""), "code": code,
            "grant_type": "authorization_code", "redirect_uri": redirect_uri},
            headers={"Content-Type": "application/x-www-form-urlencoded"})
    d = r.json() if r.status_code < 500 else {}
    if r.status_code >= 400 or not (d or {}).get("refresh_token"):
        raise LoiDang("TikTok không cấp token: " + str((d or {}).get("error_description") or (d or {}).get("error") or r.status_code)[:200])
    khoa.dat("tiktok", {"refresh_token": d["refresh_token"]})


async def _tt_access_token() -> str:
    v = khoa.lay("tiktok")
    if not v.get("refresh_token"):
        raise LoiDang("Chưa kết nối TikTok.")
    async with _client() as c:
        r = await c.post(TT_API + "/oauth/token/", data={
            "client_key": v.get("client_key", ""), "client_secret": v.get("client_secret", ""),
            "grant_type": "refresh_token", "refresh_token": v["refresh_token"]},
            headers={"Content-Type": "application/x-www-form-urlencoded"})
    d = r.json() if r.status_code < 500 else {}
    if r.status_code >= 400 or not (d or {}).get("access_token"):
        raise LoiDang("TikTok từ chối làm mới token, hãy kết nối lại: " + str((d or {}).get("error_description") or r.status_code)[:150])
    if d.get("refresh_token") and d["refresh_token"] != v["refresh_token"]:
        khoa.dat("tiktok", {"refresh_token": d["refresh_token"]})     # TikTok có thể đổi refresh token
    return d["access_token"]


def tt_chia_manh(size: int) -> tuple:
    """(chunk_size, total_chunk_count) theo luật TikTok: <5MB một mảnh; còn lại mảnh 10MB, mảnh cuối gom phần dư."""
    if size < TT_MIN or size < TT_CHUNK:
        return size, 1
    return TT_CHUNK, size // TT_CHUNK


async def dang_tiktok(p: dict, video: Path) -> dict:
    tok = await _tt_access_token()
    v = khoa.lay("tiktok")
    rieng = v.get("rieng_tu") if v.get("rieng_tu") in TT_RIENG_TU else "SELF_ONLY"
    tieu, mo = tieu_de_va_mo_ta(p)
    tags = " ".join("#" + t for t in ((p.get("kich_ban") or {}).get("hashtags") or [])[:8])
    title = (tieu + (" " + tags if tags else ""))[:2200]
    size = video.stat().st_size
    if size > 4 * 1024 ** 3:
        raise LoiDang("Video quá 4GB, TikTok không nhận.")
    cs, n = tt_chia_manh(size)
    body = {"post_info": {"title": title, "privacy_level": rieng, "disable_duet": False, "disable_stitch": False,
                          "disable_comment": False, "brand_content_toggle": False, "is_aigc": True},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": cs, "total_chunk_count": n}}
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8"}
    async with _client() as c:
        r = await c.post(TT_API + "/post/publish/video/init/", json=body, headers=h)
        if r.status_code >= 400:
            raise _tt_loi(r)
        d = (r.json() or {}).get("data") or {}
        pid, up = d.get("publish_id"), d.get("upload_url")
        if not pid or not up:
            raise LoiDang("TikTok không trả publish_id hoặc địa chỉ tải lên.")
        data = video.read_bytes()
        for i in range(n):
            a = i * cs
            b = size if i == n - 1 else a + cs          # mảnh cuối gom phần dư
            try:
                u = await c.put(up, content=data[a:b], headers={
                    "Content-Type": "video/mp4", "Content-Length": str(b - a),
                    "Content-Range": f"bytes {a}-{b - 1}/{size}"})
            except httpx.HTTPError as e:
                # Mảnh cuối đã gửi đi mà mất mạng: TikTok có thể đã nhận đủ và đăng.
                raise LoiDang(f"Mất kết nối khi tải video lên TikTok ({type(e).__name__}).",
                              chua_ro=(i == n - 1))
            if u.status_code not in (200, 201, 206):
                raise LoiDang(f"TikTok từ chối mảnh video {i + 1}/{n} (mã {u.status_code}).")
        han = asyncio.get_event_loop().time() + TT_HAN_CHO
        while True:
            try:
                s = await c.post(TT_API + "/post/publish/status/fetch/", json={"publish_id": pid}, headers=h)
            except httpx.HTTPError:
                s = None
            if s is not None and s.status_code < 400:
                sd = (s.json() or {}).get("data") or {}
                st = sd.get("status")
                if st == "PUBLISH_COMPLETE":
                    ids = sd.get("publicaly_available_post_id") or []
                    vid = str(ids[0]) if ids else ""
                    ten = (v.get("ten_kenh") or "").lstrip("@")
                    url = f"https://www.tiktok.com/@{ten}/video/{vid}" if (vid and ten) else (f"https://www.tiktok.com/video/{vid}" if vid else "")
                    return {"id": vid or pid, "url": url, "rieng_tu": rieng}
                if st == "FAILED":
                    raise LoiDang("TikTok báo đăng thất bại: " + str(sd.get("fail_reason") or "không rõ lý do"))
            if asyncio.get_event_loop().time() > han:
                raise LoiDang("Đã tải video lên nhưng TikTok chưa xác nhận đăng xong. Hãy kiểm tra trên TikTok trước khi đăng lại.", chua_ro=True)
            await _ngu(5.0)


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
    if nen_tang == "tiktok":
        return await dang_tiktok(p, video)
    raise LoiDang("Nền tảng chưa hỗ trợ.")
