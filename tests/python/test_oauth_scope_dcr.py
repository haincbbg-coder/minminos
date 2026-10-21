"""OAuth tự đăng ký (DCR): chọn scope đúng chuẩn MCP, bỏ scope bị từ chối, và báo lỗi thật ở callback."""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import os
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-oauth-scope-")
import oauth_mcp  # noqa: E402

md = {"_www_scope": "", "_prm_scopes": [], "scopes_supported": ["openid", "email", "private_metadata"]}
assert oauth_mcp._chon_scopes(md, {}) == ["openid", "email", "private_metadata"]
assert oauth_mcp._chon_scopes(md, {"blocked_scopes": ["private_metadata"]}) == ["openid", "email"]
assert oauth_mcp._chon_scopes(md, {"scope_omit": True}) == []
assert oauth_mcp._chon_scopes(dict(md, _www_scope="mcp:read mcp:write"), {}) == ["mcp:read", "mcp:write"]
assert oauth_mcp._chon_scopes(dict(md, _prm_scopes=["a"]), {}) == ["a"]
assert oauth_mcp._scope_bi_tu_choi(
    "The OAuth 2.0 Client is not allowed to request scope 'private_metadata'.") == ["private_metadata"]


async def callback():
    # phiên không có / hết hạn
    r = await oauth_mcp.handle_callback("khong-co", "", "", "invalid_scope", "x")
    assert r["ok"] is False
    # lỗi ở bước xin quyền KHÔNG được đem mã rỗng đi đổi (không còn "Đổi code thất bại: invalid_grant")
    oauth_mcp._pending["s1"] = {"conn_id": "c1", "ts": 9e12, "discovery": False, "retry": 0,
                                "provider": "", "redirect_uri": "http://x/cb"}
    r = await oauth_mcp.handle_callback("s1", "", "", "access_denied", "user said no")
    assert r["ok"] is False and "access_denied" in r["error"] and "Đổi code" not in r["error"], r


asyncio.run(callback())
print("OK")
