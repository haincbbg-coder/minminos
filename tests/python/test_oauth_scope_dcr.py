"""OAuth tự đăng ký (DCR) không xin scope dành riêng cho ứng dụng cấp phép sẵn (Higgsfield/Clerk)."""
from _paths import ROOT, SERVER  # noqa: F401
import oauth_mcp

assert oauth_mcp.loc_scope_dcr(["openid", "profile", "email", "private_metadata", "offline_access"]) == [
    "openid", "profile", "email", "offline_access"]
assert oauth_mcp.loc_scope_dcr(None) == []
assert oauth_mcp.loc_scope_dcr(["Public_Metadata", "x"]) == ["x"]
