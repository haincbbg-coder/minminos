"""Concat MCP GIẢ cho test_concat.py: nói MCP qua stdio như `concat --mcp`.

Công cụ:
  concat_version  trả chữ
  media_import    trả lại tham số + kiểm mọi tệp trong `files` có thật trên đĩa
  preview_frame   trả một ảnh PNG nhỏ (base64) + chữ
  loi_thu         trả isError=true
"""
import base64
import json
import os
import sys

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\nGIA").decode()
TOOLS = [
    {"name": "concat_version", "description": "Phiên bản", "inputSchema": {"type": "object"}},
    {"name": "media_import", "description": "Nhập media", "inputSchema": {
        "type": "object", "properties": {"path": {"type": "string"}, "files": {"type": "array"}}}},
    {"name": "preview_frame", "description": "Xem khung", "inputSchema": {"type": "object"}},
    {"name": "loi_thu", "description": "Luôn lỗi", "inputSchema": {"type": "object"}},
]


def tra(mid, result=None, error=None):
    msg = {"jsonrpc": "2.0", "id": mid}
    if error:
        msg["error"] = {"code": -32000, "message": error}
    else:
        msg["result"] = result
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


for dong in sys.stdin:
    try:
        req = json.loads(dong)
    except Exception:
        continue
    m, mid, p = req.get("method"), req.get("id"), req.get("params") or {}
    if mid is None:
        continue
    if m == "initialize":
        tra(mid, {"protocolVersion": p.get("protocolVersion"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "concat", "version": "0.2.8-gia"}})
    elif m == "tools/list":
        tra(mid, {"tools": TOOLS})
    elif m == "tools/call":
        ten, a = p.get("name"), p.get("arguments") or {}
        if ten == "concat_version":
            tra(mid, {"content": [{"type": "text", "text": "Concat 0.2.8-gia, mcp.mode headless"}], "isError": False})
        elif ten == "media_import":
            co = all(os.path.isfile(f) for f in a.get("files") or [])
            tra(mid, {"content": [{"type": "text", "text": json.dumps({"nhan": a, "tep_co_that": co})}],
                      "isError": False})
        elif ten == "preview_frame":
            tra(mid, {"content": [{"type": "image", "data": PNG, "mimeType": "image/png"},
                                  {"type": "text", "text": "The frame at 1 s."}], "isError": False})
        elif ten == "loi_thu":
            tra(mid, {"content": [{"type": "text", "text": "hỏng (code: x)"}], "isError": True})
        else:
            tra(mid, error=f"unknown tool {ten}")
    else:
        tra(mid, error="method not found")
