"""Cầu nối TikTok Business API (Marketing API) v1.3 (transport "internal").

Mỗi kết nối = MỘT lần ủy quyền TikTok Business (token của một Business Center / một người dùng).
Một lần ủy quyền quản lý được NHIỀU tài khoản quảng cáo (advertiser), nên mọi tool nhận
`advertiser_id`. Bỏ trống thì:
  - dùng ô advertiser_id mặc định của kết nối nếu có;
  - không thì nếu lần ủy quyền chỉ có ĐÚNG MỘT tài khoản quảng cáo, dùng luôn tài khoản đó;
  - còn lại báo lỗi kèm danh sách mã để model hỏi lại người dùng.
Nhiều Business Center khác nhau = nhiều kết nối.

Xác thực: header `Access-Token: <token>`. Kết quả dạng {code, message, request_id, data};
code khác 0 là lỗi. Token dài hạn của advertiser KHÔNG hết hạn, nên không có làm mới.

Ủy quyền: người dùng dán auth_code (lấy từ link ủy quyền của app trên business-api.tiktok.com)
hoặc dán thẳng access_token. Có auth_code mới thì lần gọi đầu MinMin đổi lấy token qua
POST /oauth2/access_token/ rồi lưu, đánh dấu code đã dùng (code chỉ dùng được một lần).

Tham số GET kiểu danh sách / đối tượng phải gửi dạng chuỗi JSON (quy định của TikTok).

Tool ghi (mức Toàn quyền): bật/tắt chiến dịch và đổi ngân sách chiến dịch. Không có xoá.
"""
import json
import re
from datetime import datetime, timedelta

import ket_noi_api as k

HOST = "https://business-api.tiktok.com/open_api/v1.3"
TEN = "TikTok Ads"
# Giấu MỌI ô kết nối, trừ vài mã công khai (không phải bí mật, lại hay được nhắc trong câu trả
# lời). Liệt kê cái được HIỆN thay vì cái phải giấu: ô bí mật thêm sau tự được giấu luôn.
CONG_KHAI = ("app_id", "advertiser_id", "advertiser_ids", "token_het_han")
CAP_DO = {"AUCTION_ADVERTISER": "advertiser_id", "AUCTION_CAMPAIGN": "campaign_id",
          "AUCTION_ADGROUP": "adgroup_id", "AUCTION_AD": "ad_id"}
CHI_SO_MAC_DINH = ["spend", "impressions", "clicks", "ctr", "cpc", "cpm", "conversion",
                   "cost_per_conversion", "complete_payment", "complete_payment_roas"]
THAO_TAC = ("ENABLE", "DISABLE")
NGAN_SACH_TOI_DA = 1_000_000_000
_TEN_TRUONG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

_ADV = {"advertiser_id": {"type": "string",
                          "description": "mã tài khoản quảng cáo (dãy số). Bỏ trống nếu kết nối chỉ có "
                                         "một tài khoản hoặc đã đặt tài khoản mặc định"}}
_TRANG = {"page": {"type": "integer", "description": "trang, bắt đầu từ 1"},
          "page_size": {"type": "integer", "description": "số dòng mỗi trang, tối đa 1000"}}

TOOLS = [
    k.tool("tiktokads_tai_khoan",
           "Danh sách tài khoản quảng cáo (advertiser) mà lần ủy quyền này quản lý, kèm tên, tiền tệ, "
           "múi giờ, trạng thái, số dư.",
           {"chi_tiet": {"type": "boolean", "description": "lấy thêm tiền tệ, trạng thái, số dư "
                                                           "(mặc định có)"}}),
    k.tool("tiktokads_chien_dich",
           "Danh sách chiến dịch của một tài khoản quảng cáo: tên, mục tiêu, ngân sách, trạng thái.",
           {**_ADV, **_TRANG,
            "filtering": {"type": "object",
                          "description": "lọc theo chuẩn TikTok, ví dụ {\"campaign_ids\": [\"123\"]} hoặc "
                                         "{\"primary_status\": \"STATUS_DELIVERY_OK\"}"}}),
    k.tool("tiktokads_nhom_quang_cao",
           "Danh sách nhóm quảng cáo (ad group): ngân sách, giá thầu, lịch chạy, trạng thái.",
           {**_ADV, **_TRANG,
            "campaign_ids": {"type": "string", "description": "chỉ lấy nhóm thuộc các chiến dịch này, "
                                                              "cách nhau dấu phẩy"},
            "filtering": {"type": "object", "description": "lọc thêm theo chuẩn TikTok"}}),
    k.tool("tiktokads_bao_cao",
           "Báo cáo hiệu quả (chi tiêu, hiển thị, click, CTR, CPC, CPM, chuyển đổi, ROAS) theo tài khoản, "
           "chiến dịch, nhóm hoặc quảng cáo. Tối đa 30 ngày mỗi lần, mặc định 7 ngày gần nhất.",
           {**_ADV, **_TRANG,
            "data_level": {"type": "string", "enum": list(CAP_DO),
                           "description": "cấp báo cáo, mặc định AUCTION_CAMPAIGN"},
            "dimensions": {"type": "array", "items": {"type": "string"},
                           "description": "chiều gom, ví dụ [\"campaign_id\", \"stat_time_day\"]; mặc định "
                                          "đúng mã của cấp báo cáo"},
            "theo_ngay": {"type": "boolean", "description": "tách theo từng ngày (thêm stat_time_day)"},
            "metrics": {"type": "array", "items": {"type": "string"},
                        "description": "chỉ số, mặc định " + ", ".join(CHI_SO_MAC_DINH)},
            "start_date": {"type": "string", "description": "từ ngày YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "đến ngày YYYY-MM-DD, mặc định hôm nay"}}),
    k.tool("tiktokads_bat_tat_chien_dich",
           "BẬT hoặc TẮT tối đa 20 chiến dịch. Tác động thật tới việc tiêu tiền quảng cáo. Không xoá được.",
           {**_ADV,
            "campaign_ids": {"type": "string", "description": "các mã chiến dịch (dãy số), cách nhau dấu "
                                                              "phẩy, tối đa 20"},
            "operation_status": {"type": "string", "enum": list(THAO_TAC),
                                 "description": "ENABLE để bật, DISABLE để tắt"}},
           ["campaign_ids", "operation_status"]),
    k.tool("tiktokads_doi_ngan_sach_chien_dich",
           "Đổi ngân sách của MỘT chiến dịch (đơn vị tiền tệ của tài khoản, ví dụ VND). Tác động thật "
           "tới số tiền quảng cáo được tiêu.",
           {**_ADV,
            "campaign_id": {"type": "string", "description": "mã chiến dịch (dãy số)"},
            "budget": {"type": "number", "description": "ngân sách mới, lớn hơn 0"}},
           ["campaign_id", "budget"]),
]


async def list_tools(spec):
    return TOOLS


def _an(sec):
    return {kk: v for kk, v in sec.items() if v and kk not in CONG_KHAI}


def _json_tham_so(v):
    """Danh sách / đối tượng -> chuỗi JSON (TikTok đòi vậy trên query GET)."""
    return json.dumps(v, ensure_ascii=False, separators=(",", ":")) if isinstance(v, (list, dict)) else v


def _doc_doi_tuong(v):
    """Nhận dict hoặc chuỗi JSON dict. Trả (dict|None, lỗi|None)."""
    if v in (None, "", {}):
        return None, None
    if isinstance(v, str):
        try:
            v = json.loads(v)
        except ValueError:
            return None, "ERROR: filtering phải là đối tượng JSON"
    if not isinstance(v, dict):
        return None, "ERROR: filtering phải là đối tượng JSON"
    return v, None


async def dam_bao_token(spec):
    """Trả None khi đã có access token, hoặc câu lỗi. Đổi auth_code mới (một lần) nếu có."""
    async with k.khoa(spec):
        sec = k.bi_mat(spec)
        code = str(sec.get("auth_code") or "").strip()
        if code and code != str(sec.get("auth_code_da_dung") or ""):
            ok, d = await k.goi(TEN, "POST", f"{HOST}/oauth2/access_token/", secrets=_an(sec),
                                json_body={"app_id": str(sec["app_id"]).strip(),
                                           "secret": str(sec["secret"]).strip(), "auth_code": code})
            if not ok:
                return d
            data = d.get("data") if isinstance(d, dict) else None
            if not isinstance(d, dict) or d.get("code") != 0 or not isinstance(data, dict) \
                    or not data.get("access_token"):
                ma = d.get("code", "") if isinstance(d, dict) else ""
                msg = d.get("message", "") if isinstance(d, dict) else str(d)[:300]
                return k.giau(f"ERROR: TikTok từ chối cấp token: {ma} {msg}. Mã ủy quyền chỉ dùng được một "
                              "lần và hết hạn nhanh, hãy ủy quyền lại rồi dán mã mới.", _an(sec))
            ids = [str(x) for x in (data.get("advertiser_ids") or []) if str(x).isdigit()]
            k.luu_bi_mat(spec, {"access_token": data["access_token"],
                                "advertiser_ids": ",".join(ids), "auth_code_da_dung": code})
            return None
        if str(sec.get("access_token") or "").strip():
            return None
        return ("ERROR: kết nối TikTok Ads chưa có access_token. Ủy quyền app trên business-api.tiktok.com "
                "rồi dán auth_code (hoặc access_token) vào kết nối ở trang Kết nối.")


async def _goi(spec, method, path, params=None, body=None):
    loi = await dam_bao_token(spec)
    if loi:
        return False, loi
    sec = k.bi_mat(spec)
    q = {kk: _json_tham_so(v) for kk, v in (params or {}).items() if v is not None} if params else None
    ok, d = await k.goi(TEN, method, f"{HOST}{path}", secrets=_an(sec), params=q, json_body=body,
                        headers={"Access-Token": str(sec["access_token"]).strip()})
    if not ok:
        return False, d
    if not isinstance(d, dict):
        return False, k.giau(f"ERROR: TikTok trả về không đúng dạng: {str(d)[:300]}", _an(sec))
    if d.get("code") != 0:
        return False, k.giau(f"ERROR: TikTok {d.get('code')}: {d.get('message', '')} "
                             f"(request_id {d.get('request_id', '')})", _an(sec))
    return True, d.get("data", {})


async def _ds_advertiser(spec):
    """(True, [ {advertiser_id, advertiser_name} ]) hoặc (False, lỗi)."""
    sec = k.bi_mat(spec)
    ok, d = await _goi(spec, "GET", "/oauth2/advertiser/get/",
                       {"app_id": str(sec["app_id"]).strip(), "secret": str(sec["secret"]).strip()})
    if not ok:
        return False, d
    ds = d.get("list") if isinstance(d, dict) else None
    return True, [x for x in (ds or []) if isinstance(x, dict)]


async def chon_advertiser(spec, a):
    """(advertiser_id, None) hoặc (None, lỗi)."""
    adv = str((a or {}).get("advertiser_id") or "").strip()
    if adv:
        return (adv, None) if adv.isdigit() else (None, "ERROR: advertiser_id phải là dãy số")
    sec = k.bi_mat(spec)
    mac_dinh = str(sec.get("advertiser_id") or "").strip()
    if mac_dinh:
        return (mac_dinh, None) if mac_dinh.isdigit() else (None, "ERROR: advertiser_id mặc định của kết nối "
                                                                  "phải là dãy số")
    loi = await dam_bao_token(spec)
    if loi:
        return None, loi
    ids = k.ds(k.bi_mat(spec).get("advertiser_ids"))
    if not ids:
        ok, ds = await _ds_advertiser(spec)
        if not ok:
            return None, ds
        ids = [str(x.get("advertiser_id")) for x in ds if str(x.get("advertiser_id") or "").isdigit()]
    if len(ids) == 1:
        return ids[0], None
    if not ids:
        return None, "ERROR: lần ủy quyền này không có tài khoản quảng cáo nào"
    return None, ("ERROR: kết nối quản lý " + str(len(ids)) + " tài khoản quảng cáo, cần chỉ rõ advertiser_id. "
                  "Các mã: " + ", ".join(ids[:50]) + ". Xem tên bằng tiktokads_tai_khoan.")


def _ngay(v):
    try:
        return datetime.strptime(str(v).strip(), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def khoang_ngay(a, hom_nay=None):
    """(start, end) dạng YYYY-MM-DD. Mặc định 7 ngày gần nhất, tối đa 30 ngày (tính cả hai đầu)."""
    hom_nay = hom_nay or datetime.now(k.mui_gio()).date()
    den = _ngay(a.get("end_date")) or hom_nay
    tu = _ngay(a.get("start_date")) or (den - timedelta(days=6))
    if tu > den:
        tu, den = den, tu
    if (den - tu).days > 29:
        tu = den - timedelta(days=29)
    return tu.isoformat(), den.isoformat()


def _ten_truong(v, toi_da):
    """Danh sách tên trường hợp lệ (chữ thường, số, _). Trả (list|None, lỗi|None)."""
    if v in (None, "", []):
        return None, None
    if isinstance(v, str):
        try:
            v = json.loads(v) if v.strip().startswith("[") else k.ds(v)
        except ValueError:
            return None, "ERROR: dimensions/metrics phải là danh sách tên trường"
    if not isinstance(v, list) or not v or len(v) > toi_da:
        return None, f"ERROR: dimensions/metrics phải là danh sách 1..{toi_da} tên trường"
    v = [str(x).strip() for x in v]
    if not all(_TEN_TRUONG.match(x) for x in v):
        return None, "ERROR: tên trường chỉ gồm chữ thường, số và dấu _"
    return v, None


def _trang(a):
    return k.so(a.get("page"), 1, 1, 100000), k.so(a.get("page_size"), 100, 1, 1000)


def _so_tien(v):
    if isinstance(v, bool):
        return None
    try:
        x = float(str(v).strip())
    except (TypeError, ValueError):
        return None
    return x if x == x and x not in (float("inf"), float("-inf")) else None


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "app_id", "secret")
    if t:
        return "ERROR: kết nối TikTok Ads thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    if not str(sec.get("access_token") or "").strip() and not str(sec.get("auth_code") or "").strip():
        return ("ERROR: kết nối TikTok Ads cần auth_code (mã ủy quyền) hoặc access_token - sửa lại ở trang "
                "Kết nối")
    a = arguments or {}
    ra = await _xu_ly(tool, a, spec)
    return k.giau(ra, _an(k.bi_mat(spec)))


async def _xu_ly(tool, a, spec):
    if tool == "tiktokads_tai_khoan":
        ok, ds = await _ds_advertiser(spec)
        if not ok:
            return ds
        if a.get("chi_tiet", True) is not False and ds:
            ids = [str(x.get("advertiser_id")) for x in ds if str(x.get("advertiser_id") or "").isdigit()][:100]
            ok2, info = await _goi(spec, "GET", "/advertiser/info/", {
                "advertiser_ids": ids,
                "fields": ["advertiser_id", "name", "currency", "timezone", "status", "balance", "company"]})
            if ok2:
                return k.json_ra({"tai_khoan": ds, "chi_tiet": (info or {}).get("list", info)})
            return k.json_ra({"tai_khoan": ds, "chi_tiet_loi": info})
        return k.json_ra({"tai_khoan": ds})

    if tool == "tiktokads_bat_tat_chien_dich":
        thao_tac = str(a.get("operation_status") or "").strip().upper()
        if thao_tac not in THAO_TAC:
            return "ERROR: operation_status chỉ nhận ENABLE hoặc DISABLE (không cho xoá chiến dịch)"
        ids = k.ds(a.get("campaign_ids"))
        if not ids:
            return "ERROR: thiếu campaign_ids"
        if len(ids) > 20:
            return "ERROR: tối đa 20 chiến dịch mỗi lần"
        if not all(x.isdigit() for x in ids):
            return "ERROR: campaign_ids phải là dãy số"
        adv, loi = await chon_advertiser(spec, a)
        if loi:
            return loi
        ok, d = await _goi(spec, "POST", "/campaign/status/update/", body={
            "advertiser_id": adv, "campaign_ids": ids, "operation_status": thao_tac})
        return k.json_ra(d) if ok else d

    if tool == "tiktokads_doi_ngan_sach_chien_dich":
        ma = str(a.get("campaign_id") or "").strip()
        if not ma.isdigit():
            return "ERROR: thiếu campaign_id (dãy số)"
        tien = _so_tien(a.get("budget"))
        if tien is None or tien <= 0:
            return "ERROR: budget phải là số lớn hơn 0"
        if tien > NGAN_SACH_TOI_DA:
            return f"ERROR: budget vượt mức cho phép ({NGAN_SACH_TOI_DA:,}), kiểm tra lại số"
        adv, loi = await chon_advertiser(spec, a)
        if loi:
            return loi
        ok, d = await _goi(spec, "POST", "/campaign/update/", body={
            "advertiser_id": adv, "campaign_id": ma, "budget": tien})
        return k.json_ra(d) if ok else d

    if tool not in ("tiktokads_chien_dich", "tiktokads_nhom_quang_cao", "tiktokads_bao_cao"):
        return f"ERROR: tool '{tool}' không có trong cầu nối TikTok Ads"

    page, page_size = _trang(a)
    if tool == "tiktokads_bao_cao":
        cap = str(a.get("data_level") or "AUCTION_CAMPAIGN").strip().upper()
        if cap not in CAP_DO:
            return "ERROR: data_level chỉ nhận " + ", ".join(CAP_DO)
        dims, loi = _ten_truong(a.get("dimensions"), 4)
        if loi:
            return loi
        dims = dims or [CAP_DO[cap]]
        if a.get("theo_ngay") is True and "stat_time_day" not in dims:
            dims.append("stat_time_day")
        mets, loi = _ten_truong(a.get("metrics"), 50)
        if loi:
            return loi
        tu, den = khoang_ngay(a)
        adv, loi = await chon_advertiser(spec, a)
        if loi:
            return loi
        ok, d = await _goi(spec, "GET", "/report/integrated/get/", {
            "advertiser_id": adv, "report_type": "BASIC", "data_level": cap, "dimensions": dims,
            "metrics": mets or CHI_SO_MAC_DINH, "start_date": tu, "end_date": den,
            "page": page, "page_size": page_size})
        return k.json_ra(d) if ok else d

    loc, loi = _doc_doi_tuong(a.get("filtering"))
    if loi:
        return loi
    if tool == "tiktokads_nhom_quang_cao" and a.get("campaign_ids"):
        ids = k.ds(a.get("campaign_ids"))
        if not all(x.isdigit() for x in ids):
            return "ERROR: campaign_ids phải là dãy số"
        loc = {**(loc or {}), "campaign_ids": ids[:100]}
    adv, loi = await chon_advertiser(spec, a)
    if loi:
        return loi
    path = "/campaign/get/" if tool == "tiktokads_chien_dich" else "/adgroup/get/"
    ok, d = await _goi(spec, "GET", path, {"advertiser_id": adv, "page": page, "page_size": page_size,
                                           "filtering": loc})
    return k.json_ra(d) if ok else d
