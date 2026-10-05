"""MCP 26.10.68: kết nối cũ tự lên lệnh catalog mới (lệnh sửa tay giữ nguyên) và quyền Apps Script.

- Trước đây mỗi kết nối chép lệnh lúc tạo nên bản sửa trong app (@latest, đổi gói) không tới máy cũ.
- Google Workspace: công cụ chạy hàm Apps Script phải là nguy hiểm, công cụ nhập tệp là ghi.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import mcp_catalog


def test_catalog_ghim_latest_va_ads_pypi():
    gw = mcp_catalog.get("google-workspace")
    assert gw["args"][0] == "workspace-mcp@latest"
    ads = mcp_catalog.get("google-ads")
    assert ads["args"] == ["google-ads-mcp@latest"]
    assert "git+" not in " ".join(ads["args"])
    keys = [f["key"] for f in ads["auth"]["fields"]]
    assert "project_id" not in keys
    assert mcp_catalog.get("google-search-console")["args"][-1] == "mcp-server-gsc@latest"


def test_nang_lenh_ket_noi_cu_chua_sua():
    c = {"connector_id": "google-ads", "command": "uvx",
         "args": ["--from", "git+https://github.com/googleads/google-ads-mcp.git", "google-ads-mcp"]}
    assert mcp_catalog.nang_lenh(c) is True
    assert c["args"] == ["google-ads-mcp@latest"]
    assert c["lenh_catalog"]["args"] == ["google-ads-mcp@latest"]
    assert mcp_catalog.nang_lenh(c) is False        # idempotent


def test_lenh_sua_tay_giu_nguyen():
    tay = {"connector_id": "google-workspace", "command": "uvx",
           "args": ["workspace-mcp==1.2.3", "--tool-tier", "core"]}
    assert mcp_catalog.nang_lenh(tay) is False
    assert tay["args"][0] == "workspace-mcp==1.2.3"


def test_snapshot_phan_biet_sua_tay():
    # có snapshot: lệnh khác snapshot là sửa tay, bằng snapshot là chưa sửa
    cu = {"connector_id": "google-keep", "command": "uvx", "args": ["--from", "keep-mcp", "python", "-m", "server"],
          "lenh_catalog": {"command": "uvx", "args": ["--from", "keep-mcp", "python", "-m", "server"]}}
    assert mcp_catalog.nang_lenh(cu) is True
    assert cu["args"][1] == "keep-mcp@latest"
    sua = {"connector_id": "google-keep", "command": "uvx", "args": ["--from", "keep-mcp==9", "python", "-m", "server"],
           "lenh_catalog": {"command": "uvx", "args": ["--from", "keep-mcp", "python", "-m", "server"]}}
    assert mcp_catalog.nang_lenh(sua) is False


def test_connector_http_va_custom_khong_dung_toi():
    assert mcp_catalog.nang_lenh({"connector_id": "custom", "command": "x", "args": []}) is False
    assert mcp_catalog.nang_lenh({"connector_id": "khong-ton-tai"}) is False


def test_apps_script_la_nguy_hiem_nhap_tep_la_ghi():
    gw = mcp_catalog.get("google-workspace")
    assert mcp_catalog.classify(gw, "run_script_function") == "danger"
    assert mcp_catalog.classify(gw, "import_to_google_doc") == "write"
    assert mcp_catalog.classify(gw, "send_gmail_message") == "danger"
    assert mcp_catalog.allowed(gw, "safe", "full", "run_script_function")[0] is False
    assert mcp_catalog.allowed(gw, "safe", "full", "import_to_google_doc")[0] is True
    assert mcp_catalog.allowed(gw, "full", "full", "run_script_function")[0] is True


def test_tool_cong_xet_theo_tung_lenh_ben_trong():
    cp = mcp_catalog.get("composio")
    doc = {"tools": [{"tool_slug": "GMAIL_FETCH_EMAILS"}]}
    gui = {"tools": [{"tool_slug": "GMAIL_FETCH_EMAILS"}, {"tool_slug": "GMAIL_SEND_EMAIL"}]}
    la = {"tools": [{"tool_slug": "XYZ_LAMTHUKHAC"}]}
    assert mcp_catalog.allowed(cp, "readonly", "full", "COMPOSIO_MULTI_EXECUTE_TOOL", doc)[0] is True
    assert mcp_catalog.allowed(cp, "readonly", "full", "COMPOSIO_MULTI_EXECUTE_TOOL", gui)[0] is False
    assert mcp_catalog.allowed(cp, "readonly", "full", "COMPOSIO_MULTI_EXECUTE_TOOL", la)[0] is False


def test_mcp_store_load_nang_lenh_cu(tmp_path, monkeypatch):
    import json
    import mcp_store
    f = tmp_path / "mcp_servers.json"
    f.write_text(json.dumps({"version": 2, "connections": [
        {"id": "a1", "connector_id": "google-keep", "label": "k", "slug": "k", "transport": "stdio",
         "command": "uvx", "args": ["--from", "keep-mcp", "python", "-m", "server"], "enabled": True},
        {"id": "a2", "connector_id": "google-keep", "label": "k2", "slug": "k2", "transport": "stdio",
         "command": "uvx", "args": ["--from", "keep-mcp==1", "python", "-m", "server"], "enabled": True},
    ]}), encoding="utf-8")
    monkeypatch.setattr(mcp_store, "STORE", f)
    d = mcp_store._load()
    by = {c["id"]: c for c in d["connections"]}
    assert by["a1"]["args"][1] == "keep-mcp@latest"
    assert by["a2"]["args"][1] == "keep-mcp==1"
