"""Repo riêng tư: /version đọc được bản mới từ thẻ ảnh GHCR khi có token read:packages."""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import os

import httpx

import ghcr_version as g

# Chọn đúng thẻ semver lớn nhất, bỏ latest và mã commit
assert g.ban_moi_nhat(["latest", "0.64.9", "0.64.81", "9f8c730", "0.64.80"]) == "0.64.81"
assert g.ban_moi_nhat(["latest"]) is None

# Cấu hình suy từ repo, token rỗng thì tắt
for k in ("GHCR_TOKEN", "JAVIS_GHCR_TOKEN", "GHCR_USER", "JAVIS_IMAGE"):
    os.environ.pop(k, None)
assert g.cau_hinh("haincbbg-coder/minminos") == ("haincbbg-coder/minminos", "haincbbg-coder", "")
assert asyncio.run(g.latest_from_ghcr("haincbbg-coder/minminos")) == (None, None)

os.environ["JAVIS_IMAGE"] = "ghcr.io/Haincbbg-Coder/MinMinOS:latest"
assert g.cau_hinh("x/y")[0] == "haincbbg-coder/minminos"
os.environ.pop("JAVIS_IMAGE")

# Luồng thật với GHCR giả: đổi token, phân trang qua Link
os.environ["GHCR_TOKEN"] = "tok"
seen = []


def handler(req: httpx.Request):
    seen.append(str(req.url))
    if req.url.path == "/token":
        assert req.headers["authorization"].startswith("Basic ")
        return httpx.Response(200, json={"token": "bearer-x"})
    assert req.headers["authorization"] == "Bearer bearer-x"
    if "last=" not in str(req.url):
        return httpx.Response(200, json={"tags": ["0.64.80", "latest"]},
                              headers={"link": '</v2/haincbbg-coder/minminos/tags/list?n=1000&last=latest>; rel="next"'})
    return httpx.Response(200, json={"tags": ["0.64.82", "abc1234"]})


_goc = httpx.AsyncClient


class _Gia(_goc):
    def __init__(self, *a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        super().__init__(*a, **kw)


httpx.AsyncClient = _Gia
try:
    assert asyncio.run(g.latest_from_ghcr("haincbbg-coder/minminos")) == ("0.64.82", None)
    assert len(seen) == 3

    # Token sai: báo rõ cần quyền gì
    def tu_choi(req):
        return httpx.Response(401, json={})
    _Gia.__init__ = lambda self, *a, **kw: _goc.__init__(self, *a, transport=httpx.MockTransport(tu_choi), **{k: v for k, v in kw.items() if k != "transport"})
    v, err = asyncio.run(g.latest_from_ghcr("haincbbg-coder/minminos"))
    assert v is None and "read:packages" in err
finally:
    httpx.AsyncClient = _goc
    os.environ.pop("GHCR_TOKEN", None)

print("ok")
