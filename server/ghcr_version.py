"""Số phiên bản mới nhất đọc từ ảnh Docker trên GHCR, cho repo RIÊNG TƯ (0.64.82).

Vì sao cần: `/version` hỏi raw.githubusercontent.com/<repo>/main/VERSION. Repo công khai thì
được; repo riêng tư (như MinMin) thì GitHub trả 404, app báo "chưa so được với GitHub" và
không bao giờ hiện nút Cập nhật, dù ảnh mới đã nằm sẵn trên GHCR. Chủ repo gặp đúng cảnh đó
ngày 30/09 và phải SSH vào VPS gõ `docker compose pull`.

Cách làm: mỗi lần phát hành, workflow docker-publish gắn thẻ ảnh bằng chính số VERSION
(`ghcr.io/<owner>/<repo>:0.64.82`). Có token đọc gói (`read:packages`) thì liệt kê thẻ của
ảnh rồi lấy số lớn nhất. Cùng token đó Watchtower dùng để kéo ảnh, nên người dùng chỉ phải
tạo MỘT token.

Chỉ đọc. Không có token thì trả (None, None) và `/version` giữ nguyên hành vi cũ.
"""
import os
import re

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def cau_hinh(github_repo: str):
    """(ảnh, user, token) từ biến môi trường; token rỗng nghĩa là tắt tính năng này."""
    token = (os.getenv("GHCR_TOKEN") or os.getenv("JAVIS_GHCR_TOKEN") or "").strip()
    anh = (os.getenv("JAVIS_IMAGE") or f"ghcr.io/{github_repo}").strip().lower()
    if anh.startswith("ghcr.io/"):
        anh = anh[len("ghcr.io/"):]
    anh = anh.split(":", 1)[0]
    user = (os.getenv("GHCR_USER") or anh.split("/", 1)[0]).strip()
    return anh, user, token


def _ver_tuple(v):
    return tuple(int(x) for x in v.split("."))


def ban_moi_nhat(tags):
    """Thẻ semver lớn nhất trong danh sách thẻ ảnh (bỏ qua latest, mã commit...)."""
    ban = [t for t in (tags or []) if isinstance(t, str) and _SEMVER.match(t)]
    return max(ban, key=_ver_tuple) if ban else None


async def latest_from_ghcr(github_repo: str, timeout: float = 8.0):
    """(phiên bản mới nhất | None, lỗi | None). (None, None) khi chưa cấu hình token."""
    anh, user, token = cau_hinh(github_repo)
    if not token:
        return None, None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get("https://ghcr.io/token",
                                 params={"scope": f"repository:{anh}:pull", "service": "ghcr.io"},
                                 auth=(user, token))
            if r.status_code != 200:
                return None, f"GHCR từ chối token (HTTP {r.status_code}). Token cần quyền read:packages."
            bearer = (r.json() or {}).get("token") or ""
            tags, url = [], f"https://ghcr.io/v2/{anh}/tags/list?n=1000"
            for _ in range(10):       # phân trang qua header Link, tối đa 10 trang
                r = await client.get(url, headers={"Authorization": f"Bearer {bearer}"})
                if r.status_code != 200:
                    return None, f"Không đọc được danh sách bản trên GHCR (HTTP {r.status_code})."
                tags += (r.json() or {}).get("tags") or []
                m = re.search(r'<([^>]+)>;\s*rel="next"', r.headers.get("link", ""))
                if not m:
                    break
                nxt = m.group(1)
                url = nxt if nxt.startswith("http") else "https://ghcr.io" + nxt
        latest = ban_moi_nhat(tags)
        return latest, (None if latest else "Ảnh trên GHCR chưa có thẻ phiên bản nào.")
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
