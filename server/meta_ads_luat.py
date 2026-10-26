"""Luật cứng cho mọi lệnh GHI Facebook Ads của MinMin (26.10.248).

Đội Ads chạy trọn tới bước bật camp qua MCP Meta Ads chính chủ (`https://mcp.facebook.com/ads`).
Lệnh ở đó chi tiền thật, nên ngoài mức quyền chung (mcp_catalog.allowed) còn một lớp chặn theo
TRỊ SỐ của lệnh, do chủ đặt ở ô "Giới hạn Đội Ads":

- Tài khoản quảng cáo phải nằm trong danh sách cho phép, ở MỌI mức quyền (kể cả full). Danh sách
  rỗng = không tài khoản nào được ghi.
- Ngân sách ngày không vượt trần (VND), ở MỌI mức quyền. Ngân sách trọn đời không vượt trần x 30.
- Dưới full: không kích hoạt, không đặt ACTIVE, không publish_as_active, không sửa đối tượng đang
  chạy (`ads_update_entity` có thể đổi ngân sách hay trạng thái của camp đang tiêu tiền), không xoá.
- Bước bật camp của một job Đội AI chỉ được bật ĐÚNG các mã mà bước dựng camp đã lưu vào job.

Một chỗ dùng chung cho hub (lệnh thô từ mọi engine) và plugin `meta-ads-camp` (lệnh plugin gọi
thẳng pool MCP, không qua hub), để hai đường không lệch luật nhau.

Đơn vị ngân sách của MCP Meta là đơn vị nhỏ nhất của tiền tài khoản; VND không có đơn vị lẻ nên
1 = 1 đồng. Trần tính theo đồng nên danh sách cho phép chỉ nên chứa tài khoản đặt tiền VND; ô
Giới hạn Đội Ads nói rõ điều này với chủ.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

TAI_KHOAN_MAC_DINH = ["1372588536646337"]      # CÔNG TY HALIMI - ĐẠT 3, chủ chốt 2026-10-26
TRAN_NGAY_MAC_DINH = 700_000                    # đồng / camp / ngày, chủ chốt 2026-10-26
TRAN_MIN, TRAN_MAX = 50_000, 50_000_000
# Tool GHI được làm ở mức dưới full: chỉ tạo đối tượng TẮT/NHÁP và tải ảnh. Mọi tool ghi khác
# (bật, sửa, xoá, boost, thử nghiệm A/B, catalog, pixel, tệp đối tượng...) chỉ ở mức full.
TOOL_TAO_NHAP = frozenset((
    "ads_create_campaign", "ads_create_ad_set", "ads_create_ad", "ads_create_creative",
    "ads_creative_upload_media", "ads_creative_upload_local_image",
    "ads_finalize_local_ad_image_upload",
))
# Từ trong tên cho biết tool chỉ ĐỌC. Tên không có từ nào trong đây coi là GHI (fail-closed): lỗ
# cũ là danh sách tool ghi liệt kê tay, tool ghi mới của Meta (thử nghiệm A/B...) lọt qua.
TU_DOC = frozenset(("get", "list", "read", "search", "check", "insights", "library", "help",
                    "field", "log", "preview", "eligibility", "diagnostics", "benchmark",
                    "benchmarks", "trend", "signal", "context", "score", "status"))
TRUONG_NGAN_SACH_NGAY = ("campaign_daily_budget", "daily_budget", "daily_spend_cap",
                         "ad_set_daily_budget", "daily_min_spend_target", "budget_value")
# Cấm hẳn, mọi mức: ngân sách trọn đời (trọn đời 21 triệu với ngày kết thúc mai là tiêu 21 triệu
# trong một ngày, trần ngày không bắt được), lịch ngân sách, và sao chép từ đối tượng có sẵn (bản
# sao mang ngân sách của bản gốc mà lệnh không hề ghi ra).
TRUONG_CAM = ("campaign_lifetime_budget", "lifetime_budget", "ad_set_lifetime_budget",
              "budget_schedule_specs", "source_campaign_id", "source_adset_id", "source_ad_id",
              "lifetime_min_spend_target")
TRUONG_TRANG_THAI = ("status", "campaign_status", "ad_set_status", "ad_status",
                     "configured_status")
TRUONG_TAI_KHOAN = ("ad_account_id", "account_id")
_TRAN_QUET = 3000


def chuan_tk(x: Any) -> str:
    """'act_123 ' -> '123'. Không phải số thì trả rỗng."""
    s = re.sub(r"\s+", "", str(x or "")).lower()
    if s.startswith("act_"):
        s = s[4:]
    return s if s.isdigit() else ""


def _settings(settings: Optional[dict]) -> dict:
    if settings is not None:
        return settings
    try:
        import config
        return config.read_settings() or {}
    except Exception:
        return {}


def doc_luat(settings: Optional[dict] = None) -> dict:
    """{"tai_khoan": [số tài khoản], "tran_ngay_vnd": int}. Chưa đặt thì dùng mặc định chủ chốt."""
    q = (_settings(settings).get("quyen") or {})
    raw = q.get("meta_ads") if isinstance(q, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    if "tai_khoan" in raw and isinstance(raw.get("tai_khoan"), list):
        tk = [t for t in (chuan_tk(x) for x in raw["tai_khoan"]) if t]
    else:
        tk = list(TAI_KHOAN_MAC_DINH)
    try:
        tran = int(raw.get("tran_ngay_vnd") or TRAN_NGAY_MAC_DINH)
    except Exception:
        tran = TRAN_NGAY_MAC_DINH
    tran = min(max(tran, TRAN_MIN), TRAN_MAX)
    return {"tai_khoan": list(dict.fromkeys(tk)), "tran_ngay_vnd": tran}


def kiem_luat_moi(data: Any) -> tuple[Optional[dict], str]:
    """Kiểm dữ liệu chủ gửi lên ô Giới hạn Đội Ads. (luật đã chuẩn hoá, "") hoặc (None, lý do)."""
    if not isinstance(data, dict):
        return None, "Dữ liệu không hợp lệ"
    tk_raw = data.get("tai_khoan")
    if isinstance(tk_raw, str):
        tk_raw = re.split(r"[\s,;]+", tk_raw)
    if not isinstance(tk_raw, list):
        return None, "Danh sách tài khoản phải là một danh sách"
    tk = []
    for x in tk_raw:
        if not str(x or "").strip():
            continue
        c = chuan_tk(x)
        if not c:
            return None, f"Mã tài khoản '{x}' không hợp lệ: chỉ gồm số, có thể kèm act_ ở đầu"
        tk.append(c)
    try:
        tran = int(str(data.get("tran_ngay_vnd") or "").replace(".", "").replace(",", "").strip())
    except Exception:
        return None, "Trần ngân sách phải là số đồng"
    if tran < TRAN_MIN or tran > TRAN_MAX:
        return None, f"Trần ngân sách phải từ {TRAN_MIN:,} đến {TRAN_MAX:,} đồng".replace(",", ".")
    return {"tai_khoan": list(dict.fromkeys(tk)), "tran_ngay_vnd": tran}, ""


def la_ket_noi_meta_ads(url: Any = "", connector_id: Any = "") -> bool:
    """Kết nối có phải MCP Meta Ads chính chủ không (nối bằng địa chỉ tự nhập)."""
    try:
        u = urlparse(str(url or ""))
    except Exception:
        return False
    host = (u.hostname or "").lower()
    if host == "mcp.facebook.com":
        return True
    return (host == "facebook.com" or host.endswith(".facebook.com")) and "/ads" in (u.path or "")


def ten_goc(tool: Any) -> str:
    """Bỏ tiền tố connector: `meta__ads_create_ad` / `mcp__fb__ads_create_ad` -> `ads_create_ad`."""
    t = str(tool or "").strip().lower()
    m = re.search(r"(ads_[a-z0-9_]+)$", t)
    return m.group(1) if m else t


def la_tool_doc(goc: str) -> bool:
    tu = goc.split("_")
    return goc.startswith("ads_") and any(w in TU_DOC for w in tu[1:])


def _json(v: Any) -> Any:
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in ("{", "["):
            try:
                return json.loads(s)
            except Exception:
                return v
    return v


_SO_CO_DAU = re.compile(r"^\d{1,3}([.,]\d{3})+$")


def _so(v: Any) -> Optional[int]:
    """Số đồng từ int/float/chuỗi ("700000", "700.000", "1,500,000"). Không đọc được -> None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v or "").strip().replace(" ", "")
    if not s:
        return None
    if _SO_CO_DAU.match(s):
        s = s.replace(".", "").replace(",", "")
    try:
        return int(float(s))
    except Exception:
        return None


def _quet(args: Any) -> tuple[list, bool]:
    """Mọi cặp (khoá, giá trị) trong args, kể cả JSON lồng trong chuỗi (fields, creative...).
    Trả (danh sách, đủ). `đủ`=False khi vượt trần nút: người gọi phải CHẶN, không được cho qua."""
    out = []
    stack = [_json(args)]
    seen = 0
    while stack:
        cur = stack.pop()
        seen += 1
        if seen > _TRAN_QUET:
            return out, False
        if isinstance(cur, dict):
            for k, v in cur.items():
                v2 = _json(v)
                out.append((str(k).lower(), v2))
                if isinstance(v2, (dict, list)):
                    stack.append(v2)
        elif isinstance(cur, list):
            for v in cur:
                v2 = _json(v)
                if isinstance(v2, (dict, list)):
                    stack.append(v2)
    return out, True


def _dong(n: int) -> str:
    return f"{n:,}".replace(",", ".") + "đ"


def kiem_lenh(tool: Any, args: Any, mode: str, settings: Optional[dict] = None,
              ids_cho_phep: Optional[list] = None, job: Optional[dict] = None) -> str:
    """"" = cho qua; khác rỗng = câu lý do chặn (tiếng Việt, nói được với chủ).

    `job`: {"ids": [...], "nhap": bool} khi lệnh chạy trong một bước job Đội AI (xem
    `ngu_canh_job`). `ids_cho_phep` là dạng ngắn của nó (coi như camp còn nháp). Trong bước job,
    lệnh ghi thô duy nhất được phép là bật ĐÚNG các mã bước dựng camp đã lưu."""
    goc = ten_goc(tool)
    if not goc.startswith("ads_") or la_tool_doc(goc):
        return ""
    if job is None and ids_cho_phep is not None:
        job = {"ids": list(ids_cho_phep), "nhap": True}
    luat = doc_luat(settings)
    mode = str(mode or "full").strip().lower()
    a = args if isinstance(args, dict) else {}

    tks = [str(a.get(k) or "") for k in TRUONG_TAI_KHOAN if str(a.get(k) or "").strip()]
    if not tks:
        return (f"Lệnh {goc} thiếu ad_account_id: MinMin chỉ ghi vào tài khoản quảng cáo có trong "
                f"danh sách chủ cho phép, nên lệnh phải nêu rõ tài khoản.")
    ds = ", ".join("act_" + x for x in luat["tai_khoan"]) or "(trống)"
    for raw in tks:
        tk = chuan_tk(raw)
        if not tk or tk not in luat["tai_khoan"]:
            return (f"Tài khoản {raw} KHÔNG nằm trong danh sách chủ cho phép Đội Ads ghi ({ds}). "
                    f"Không làm. Chủ thêm tài khoản ở ô Giới hạn Đội Ads trên trang Bảng việc nếu muốn.")

    cap, du = _quet(a)
    if not du:
        return f"Lệnh {goc} quá lớn để soát hết. Không làm."
    tran = luat["tran_ngay_vnd"]
    for k, v in cap:
        if k in TRUONG_CAM and v not in (None, "", [], {}, 0, "0", "[]"):
            return (f"Lệnh {goc} có {k}: MinMin không dùng ngân sách trọn đời, lịch ngân sách hay sao "
                    f"chép từ đối tượng có sẵn (ngân sách thật không nằm trong lệnh để soát). Không làm.")
        if k in TRUONG_NGAN_SACH_NGAY and v not in (None, ""):
            if isinstance(v, (dict, list)):
                return f"Lệnh {goc}: {k} không phải một con số. Không làm."
            n = _so(v)
            if n is None:
                return f"Lệnh {goc}: không đọc được {k}={v!r} thành số đồng. Không làm."
            if n > tran:
                return (f"Ngân sách ngày {_dong(n)} ({k}) vượt trần {_dong(tran)} chủ đặt cho mỗi camp. "
                        f"Không làm. Hạ ngân sách, hoặc chủ nâng trần ở ô Giới hạn Đội Ads.")
    if goc == "ads_create_ad_set" and any(k == "daily_budget" and v not in (None, "", 0) for k, v in cap):
        return ("Nhóm quảng cáo không được có ngân sách riêng: MinMin đặt ngân sách ở chiến dịch (CBO) để "
                "trần tính đúng cho cả camp. Bỏ daily_budget ở nhóm.")

    if mode != "full":
        if goc not in TOOL_TAO_NHAP:
            return (f"Lệnh {goc} bật, sửa, xoá hoặc chạy thứ có thể tiêu tiền trên tài khoản quảng cáo: "
                    f"chỉ được làm ở mức Toàn quyền (bước sau GATE chủ đã duyệt). Lượt này đang ở mức {mode}.")
        for k, v in cap:
            if k in TRUONG_TRANG_THAI and str(v).strip().upper() == "ACTIVE":
                return (f"Lệnh {goc} đặt {k}=ACTIVE: camp dựng ở mức {mode} phải để TẮT/NHÁP, "
                        f"chỉ bước sau GATE chủ đã duyệt mới được bật.")
            if k == "publish_as_active" and str(v).strip().lower() in ("true", "1", "yes"):
                return f"Lệnh {goc} có publish_as_active=true: chỉ bước sau GATE chủ đã duyệt mới được bật."

    if job is not None:
        cho = {str(x) for x in (job.get("ids") or []) if str(x or "").strip()}
        if goc != "ads_activate_entity":
            return (f"Trong bước job Đội Ads, lệnh {goc} thô không được dùng: dựng camp bằng "
                    f"meta_ads_dung_camp, bật camp bằng meta_ads_bat_camp.")
        if not cho:
            return ("Bước này thuộc một job Đội AI nhưng bước dựng camp chưa lưu mã camp nào vào job, "
                    "nên không có gì được phép bật. Dừng và báo chủ.")
        dich = str(a.get("entity_id") or "").strip()
        oi = _json(a.get("object_ids"))
        if isinstance(oi, list):
            ds_oi = [str(x).strip() for x in oi if str(x).strip()]
        elif oi:
            ds_oi = [x for x in re.split(r"[\s,]+", str(oi)) if x]
        else:
            ds_oi = []
        muc = ([dich] if dich else []) + ds_oi
        if not dich or any(m not in cho for m in muc):
            return ("Lệnh nhắm vào mã khác với các mã bước dựng camp đã lưu trong job "
                    f"({', '.join(sorted(cho))}). Chỉ được bật đúng camp chủ đã duyệt ở GATE.")
        loai = str(a.get("entity_type") or "").strip().lower()
        if job.get("nhap", True) and loai in ("campaign", "") and not ds_oi:
            return ("Bật chiến dịch NHÁP mà không liệt kê object_ids sẽ đăng luôn mọi thứ đang nháp dưới "
                    "nó, kể cả thứ chủ chưa duyệt. Phải liệt kê đúng các mã đã lưu trong object_ids.")
    return ""


def ngu_canh_job() -> Optional[dict]:
    """{"ids": [...], "nhap": bool} của job Đội AI đang chạy lượt này. None = lượt không thuộc
    bước job nào (chat thường, loop, việc lẻ). ids [] = bước job nhưng chưa lưu mã nào."""
    try:
        import once_ledger
        mvc = once_ledger.current_job() or ""
    except Exception:
        return None
    if not mvc.startswith("kanban:"):
        return None
    try:
        import tasks
        feat = tasks.current()
        if feat is None or not hasattr(feat, "job_ads_doc"):
            return None
        tid = mvc.split(":", 1)[1]
        if not feat.la_buoc_job(tid):
            return None
        ads = feat.job_ads_doc(tid) or {}
    except Exception:
        return None
    if not ads.get("campaign_id"):
        return {"ids": [], "nhap": True}
    ids = ([str(ads.get("campaign_id"))] + [str(x) for x in (ads.get("adset_ids") or [])]
           + [str(x) for x in (ads.get("ad_ids") or [])])
    return {"ids": ids, "nhap": str(ads.get("trang_thai") or "NHAP") != "TAT"}


def ids_job_hien_tai() -> Optional[list]:
    """Dạng ngắn của `ngu_canh_job`: chỉ danh sách mã."""
    nc = ngu_canh_job()
    return None if nc is None else list(nc["ids"])
