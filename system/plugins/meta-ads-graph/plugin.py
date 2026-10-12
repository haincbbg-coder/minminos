"""Plugin bundled: đọc số liệu Meta Ads (Facebook/Instagram) qua Graph API - CHỈ ĐỌC.

Không đi qua MCP beta bị khoá của Meta (mcp.facebook.com/ads); gọi THẲNG graph.facebook.com
Marketing API bằng user access token của kết nối "meta-ads-graph" (connector BYO app - user tự
tạo Facebook App, OAuth do oauth_mcp lo, token tự gia hạn ~60 ngày). Đây là cách Composio/byadsco
làm. Mọi tool đều readonly (chỉ GET) - không tạo/sửa chiến dịch, không tiêu tiền.
"""
from __future__ import annotations

import json

GRAPH = "https://graph.facebook.com/v26.0"
CONNECTOR_ID = "meta-ads-graph"
_INSIGHT_FIELDS = "spend,impressions,clicks,ctr,cpc,cpm,reach,frequency,actions,action_values"
_CAMPAIGN_FIELDS = "name,status,effective_status,objective,daily_budget,lifetime_budget,start_time,stop_time"


def _conns():
    """MỌI kết nối meta-ads-graph ĐÃ đăng nhập: [{id, label, is_default}], tài khoản mặc định lên đầu.
    Import lười để load không phụ thuộc."""
    try:
        import mcp_store
        import oauth_mcp
    except Exception:
        return []
    out = []
    for c in mcp_store.list_connections():
        if c.get("connector_id") == CONNECTOR_ID and oauth_mcp.status(c["id"]).get("connected"):
            out.append({"id": c["id"], "label": c.get("label") or c.get("name") or c["id"],
                        "is_default": bool(c.get("is_default"))})
    out.sort(key=lambda x: not x["is_default"])
    return out


def _connected_id():
    """id kết nối meta-ads-graph ĐÃ đăng nhập (ưu tiên tài khoản mặc định; None nếu chưa)."""
    cs = _conns()
    return cs[0]["id"] if cs else None


def _check():
    if not _connected_id():
        return ("Chưa kết nối Facebook. Vào trang Kết nối, chọn 'Meta Ads (tự tạo app - Graph API)', "
                "làm theo hướng dẫn tạo Facebook App rồi đăng nhập. Sau đó gọi lại tool này.")
    return None


async def _token_of(cid):
    import oauth_mcp
    hdr = await oauth_mcp.auth_headers(cid)      # tự refresh token ~60 ngày khi sắp hết hạn
    return (hdr.get("Authorization", "") or "").replace("Bearer ", "").strip() or None


async def _token():
    """Token của tài khoản mặc định (dùng để kiểm 'đã kết nối chưa')."""
    cid = _connected_id()
    return await _token_of(cid) if cid else None


async def _acct_tokens(tai_khoan=""):
    """[(nhãn tài khoản, token)] theo thứ tự ưu tiên (mặc định trước); `tai_khoan` thu hẹp về một
    tài khoản. Trả (list, err)."""
    cs = _conns()
    if not cs:                                    # chưa có danh sách kết nối: đường 1 token cũ
        t = await _token()
        return ([("", t)] if t else []), None
    ref = str(tai_khoan or "").strip().lower()
    if ref:
        sel = [c for c in cs if ref in (c["id"].lower(), c["label"].lower())] or \
              [c for c in cs if ref in c["label"].lower()]
        if not sel:
            return [], ("ERROR: Không có tài khoản Facebook '" + str(tai_khoan) + "'. Đang nối: " +
                        ", ".join(c["label"] for c in cs))
        cs = sel
    out = []
    for c in cs:
        t = await _token_of(c["id"])
        if t:
            out.append((c["label"], t))
    return out, None


async def _get(path, params, token):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{GRAPH}/{str(path).lstrip('/')}",
                            params={**(params or {}), "access_token": token})
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}"}}
    except Exception as e:
        return {"error": {"message": f"{type(e).__name__}: {e}"}}


def _fmt(d):
    if isinstance(d, dict) and d.get("error"):
        e = d["error"]
        return "ERROR: Facebook API: " + (e.get("message") if isinstance(e, dict) else str(e))
    return json.dumps(d, ensure_ascii=False, default=str)


async def _all_adaccounts(token, fields="account_id,name,currency,account_status,amount_spent,balance"):
    """Mọi tài khoản quảng cáo một user thấy (theo trang, tối đa ~4000). Trả (list, err)."""
    rows, after = [], ""
    for _ in range(20):
        params = {"fields": fields, "limit": 200}
        if after:
            params["after"] = after
        d = await _get("me/adaccounts", params, token)
        if isinstance(d, dict) and d.get("error"):
            return None, _fmt(d)
        rows += (d or {}).get("data") or []
        pg = (d or {}).get("paging") or {}
        after = ((pg.get("cursors") or {}).get("after") or "") if pg.get("next") else ""
        if not after:
            break
    return rows, None


async def _resolve_act(args, token):
    """Chuẩn hoá account_id thành 'act_<id>' và CHỌN ĐÚNG TOKEN. Trả (act, err, token_dùng).
    - có account_id: tìm trong các tài khoản Facebook đã nối xem ai quản lý nó (mặc định trước), dùng
      token của người đó; không ai liệt kê được thì dùng token mặc định như trước;
    - bỏ trống: tài khoản quảng cáo đầu tiên của tài khoản mặc định."""
    args = args or {}
    accts, err = await _acct_tokens(args.get("tai_khoan"))
    if err:
        return None, err, token
    aid = str(args.get("account_id") or "").strip()
    if aid:
        n = aid.replace("act_", "")
        for _label, tok in accts:
            rows, e = await _all_adaccounts(tok, "account_id")
            if not e and any(str(r.get("account_id")) == n for r in rows or []):
                return "act_" + n, None, tok
        return "act_" + n, None, (accts[0][1] if accts else token)
    tok = accts[0][1] if accts else token
    d = await _get("me/adaccounts", {"fields": "account_id", "limit": 1}, tok)
    if isinstance(d, dict) and d.get("error"):
        return None, _fmt(d), tok
    data = (d or {}).get("data") or []
    if not data:
        return None, ("ERROR: Không thấy tài khoản quảng cáo nào. Kiểm tra bạn có quyền ads_read "
                      "và là admin của ad account."), tok
    return "act_" + (data[0].get("account_id") or "").replace("act_", ""), None, tok


async def _accounts(args, ctx):
    """Tài khoản quảng cáo của MỌI tài khoản Facebook đã nối, kèm ai đang quản lý (cùng BM nên một
    tài khoản quảng cáo có thể hiện ở nhiều người, gộp lại một dòng)."""
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    accts, err = await _acct_tokens((args or {}).get("tai_khoan"))
    if err:
        return err
    by_id, order, loi = {}, [], []
    for label, tok in accts:
        rows, e = await _all_adaccounts(tok)
        if e:
            loi.append(f"{label or 'tài khoản'}: {e}")
            continue
        for r in rows or []:
            k = str(r.get("account_id"))
            if k not in by_id:
                by_id[k] = dict(r)
                by_id[k]["tai_khoan"] = []
                order.append(k)
            if label and label not in by_id[k]["tai_khoan"]:
                by_id[k]["tai_khoan"].append(label)
    if not order and loi:
        return loi[0]
    data = [by_id[k] if by_id[k]["tai_khoan"] else {x: y for x, y in by_id[k].items() if x != "tai_khoan"}
            for k in order]
    out = {"data": data}
    if loi:
        out["loi_tai_khoan"] = loi
    return _fmt(out)


async def _insights(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    act, err, token = await _resolve_act(args, token)
    if err:
        return err
    args = args or {}
    params = {"fields": _INSIGHT_FIELDS, "level": (args.get("level") or "account")}
    since, until = str(args.get("since") or "").strip(), str(args.get("until") or "").strip()
    if since and until:
        params["time_range"] = json.dumps({"since": since, "until": until})
    else:
        params["date_preset"] = args.get("date_preset") or "last_7d"
    d = await _get(f"{act}/insights", params, token)
    return _fmt(d)


async def _campaigns(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    act, err, token = await _resolve_act(args, token)
    if err:
        return err
    args = args or {}
    try:
        limit = max(1, min(200, int(args.get("limit") or 50)))
    except (TypeError, ValueError):
        limit = 50
    d = await _get(f"{act}/campaigns", {"fields": _CAMPAIGN_FIELDS, "limit": limit}, token)
    return _fmt(d)


async def _raw_get(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    path = str(args.get("path") or "").strip().lstrip("/")
    if not path:
        return "ERROR: thiếu 'path' (vd 'me/adaccounts', 'act_123/insights')."
    params = args.get("params")
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception:
            params = {}
    if not isinstance(params, dict):
        params = {}
    accts, aerr = await _acct_tokens(args.get("tai_khoan"))
    if aerr:
        return aerr
    d = await _get(path, params, accts[0][1] if accts else token)
    return _fmt(d)


def register(ctx):
    ctx.register_tool(
        name="meta_ads_accounts", min_mode="readonly", check_fn=_check, handler=_accounts,
        description=("Liệt kê tài khoản quảng cáo của MỌI tài khoản Facebook đã nối, kèm tài khoản nào quản lý (id, tên, tiền tệ, "
                     "trạng thái, tổng đã tiêu). Dùng đầu tiên để lấy account_id cho các tool khác."),
        schema={"type": "object", "properties": {
            "tai_khoan": {"type": "string", "description": "Chỉ liệt kê của tài khoản Facebook này (bỏ trống = tất cả)"}}},
    )
    ctx.register_tool(
        name="meta_ads_insights", min_mode="readonly", check_fn=_check, handler=_insights,
        description=("Hiệu suất quảng cáo Facebook/Instagram: chi tiêu, hiển thị, click, CTR, CPC, CPM, "
                     "reach, hành động chuyển đổi. Bỏ trống account_id = tài khoản đầu tiên. Kỳ mặc định "
                     "7 ngày; đổi bằng date_preset (today/yesterday/last_7d/last_14d/last_30d/this_month/"
                     "last_month...) hoặc since+until (YYYY-MM-DD). level = account|campaign|ad."),
        schema={"type": "object", "properties": {
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = tài khoản mặc định, tự tìm ai quản lý account_id)"},
            "account_id": {"type": "string", "description": "act_<id> hoặc <id> (bỏ trống = tài khoản đầu tiên)"},
            "date_preset": {"type": "string", "description": "vd last_7d, last_30d, this_month"},
            "since": {"type": "string", "description": "Từ ngày YYYY-MM-DD (dùng kèm until)"},
            "until": {"type": "string", "description": "Đến ngày YYYY-MM-DD"},
            "level": {"type": "string", "description": "account | campaign | ad (mặc định account)"}}},
    )
    ctx.register_tool(
        name="meta_ads_campaigns", min_mode="readonly", check_fn=_check, handler=_campaigns,
        description=("Liệt kê chiến dịch quảng cáo của một tài khoản (tên, trạng thái, mục tiêu, ngân sách "
                     "ngày/trọn đời, thời gian chạy). Bỏ trống account_id = tài khoản đầu tiên."),
        schema={"type": "object", "properties": {
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = tài khoản mặc định, tự tìm ai quản lý account_id)"},
            "account_id": {"type": "string", "description": "act_<id> hoặc <id> (bỏ trống = tài khoản đầu tiên)"},
            "limit": {"type": "integer", "description": "Số chiến dịch tối đa (mặc định 50)"}}},
    )
    ctx.register_tool(
        name="meta_ads_get", min_mode="readonly", check_fn=_check, handler=_raw_get,
        description=("Gọi ĐỌC bất kỳ node/edge nào của Graph API Marketing (chỉ GET, không ghi). Dùng khi "
                     "3 tool trên chưa đủ. path = đường dẫn Graph (vd 'act_123/adsets', 'me/businesses'); "
                     "params = tham số truy vấn (object)."),
        schema={"type": "object", "properties": {
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = mặc định)"},
            "path": {"type": "string", "description": "Đường dẫn Graph API, vd 'act_123/adsets'"},
            "params": {"type": "object", "description": "Tham số query (vd {\"fields\":\"name,status\"})"}},
            "required": ["path"]},
    )
