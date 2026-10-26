"""Plugin bundled: Đội Ads dựng camp TẮT trước GATE, bật camp sau GATE (26.10.248).

Vì sao là hai công cụ HẸP thay vì để model gọi thẳng các lệnh của MCP Meta Ads
============================================================================
MCP Meta Ads chính chủ (`https://mcp.facebook.com/ads`) có hàng chục lệnh, trong đó có lệnh tiêu
tiền thật (`ads_activate_entity`) và lệnh sửa camp đang chạy (`ads_update_entity`). Lớp chặn ở hub
(`meta_ads_luat.kiem_lenh`) giữ luật tài khoản / trần ngân sách / chỉ full mới bật cho mọi lệnh
thô, nhưng một lệnh thô vẫn để model tự chọn từng tham số. Hai công cụ ở đây cố định phần chủ đã
chốt, nên model chỉ còn đưa vào những thứ thay đổi theo từng camp:

- `meta_ads_dung_camp` (min_mode safe, chạy được ở bước trước GATE): tự đặt tên
  "CÔNG TY TNHH MTV HALIMI - TÊN PAGE - MÃ SP", ngân sách ngày (mặc định 300.000đ, không vượt
  trần), nữ 23-54 Việt Nam, bắt đầu 23:59 hôm nay, mọi thứ ở trạng thái TẮT/NHÁP. Hai loại camp
  theo luật của chủ: có landing page hợp lệ -> camp chuyển đổi website; không có -> camp mua hàng
  qua tin nhắn từ bài viết có sẵn; landing page lỗi -> DỪNG, không tự đổi loại.
  Dựng xong thì lưu mã camp/nhóm/quảng cáo vào job, để khung GATE hiện cho chủ xem.
- `meta_ads_bat_camp` (min_mode full, chỉ bước sau GATE chủ đã duyệt): KHÔNG nhận mã từ model.
  Đọc mã đã lưu trong job, kiểm luật lần nữa, bật đúng các mã đó, rồi đọc lại trạng thái thật.
  PUBLISHING không được báo là "đã chạy".

Plugin gọi thẳng pool MCP bằng kết nối OAuth của chủ (không qua hub), nên tự gọi
`meta_ads_luat.kiem_lenh` trước mỗi lệnh ghi.
"""
from __future__ import annotations

import json
import random
import re
import string
from datetime import datetime, timedelta

CHU_CTY = "CÔNG TY TNHH MTV HALIMI"
NGAN_SACH_MAC_DINH = 300_000
TARGETING_MAC_DINH = {
    "geo_locations": {"countries": ["VN"]},
    "age_min": 23, "age_max": 54, "genders": [2],
    # Chủ chốt đối tượng ban đầu nữ 23-54 (tuổi tối đa CỨNG dưới 65 là lý do hợp lệ để tắt
    # Advantage+ Audience theo chính mô tả của Meta).
    "targeting_automation": {"advantage_audience": 0},
}
JOB_META = "create_and_launch_new_ads"
CHUA_NOI = ("Chưa nối MCP Meta Ads chính chủ. Vào trang Kết nối, thêm kết nối tự nhập địa chỉ "
            "https://mcp.facebook.com/ads, chọn đăng nhập OAuth bằng tài khoản Facebook quản lý "
            "tài khoản quảng cáo, rồi gọi lại. MinMin KHÔNG dựng hay bật camp khi chưa có kết nối này.")


# ---------------------------------------------------------------------------
# Kết nối MCP Meta
# ---------------------------------------------------------------------------
def _ket_noi():
    try:
        import mcp_store
        import meta_ads_luat
    except Exception:
        return None
    try:
        for c in mcp_store.resolved(enabled_only=True):
            if meta_ads_luat.la_ket_noi_meta_ads(c.get("url"), c.get("connector_id")):
                return c
    except Exception:
        return None
    return None


def _check():
    return None if _ket_noi() else CHUA_NOI


def _ma_hoi_thoai() -> str:
    bang = string.ascii_letters + string.digits
    return "".join(random.choice(bang) for _ in range(20))


def _doc_json(text):
    if not isinstance(text, str):
        return text if isinstance(text, (dict, list)) else None
    s = text.strip()
    for thu in (s, s[s.find("{"):] if "{" in s else ""):
        if not thu:
            continue
        try:
            return json.loads(thu)
        except Exception:
            continue
    return None


def _tim(obj, khoa, sau=0):
    """Giá trị đầu tiên của một trong các khoá, tìm sâu trong dict/list."""
    if sau > 8:
        return None
    if isinstance(obj, dict):
        for k in khoa:
            v = obj.get(k)
            if v not in (None, "", [], {}):
                return v
        for v in obj.values():
            r = _tim(v, khoa, sau + 1)
            if r not in (None, "", [], {}):
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _tim(v, khoa, sau + 1)
            if r not in (None, "", [], {}):
                return r
    return None


_MA_HOP_LE = re.compile(r"^[0-9]{5,25}$")


def _ma(data, khoa):
    """Mã đối tượng Meta trả về, CHỈ theo khoá đã khai (campaign_id, ad_set_id, ad_id) ở cấp
    ngoài hoặc một cấp lồng, và phải là chuỗi số. Không lấy `id` chung chung: một `creative.id`
    hay mã tài khoản lồng bên trong từng có thể bị lưu nhầm thành mã quảng cáo."""
    tang = [data] if isinstance(data, dict) else []
    if isinstance(data, dict):
        tang += [v for v in data.values() if isinstance(v, dict)]
    for d in tang:
        for k in khoa:
            v = str(d.get(k) or "").strip()
            if _MA_HOP_LE.match(v):
                return v
    return ""


def _tim_het(obj, khoa, out=None, sau=0):
    out = [] if out is None else out
    if sau > 8:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in khoa and not isinstance(v, (dict, list)):
                out.append((k, v, obj))
            _tim_het(v, khoa, out, sau + 1)
    elif isinstance(obj, list):
        for v in obj:
            _tim_het(v, khoa, out, sau + 1)
    return out


class _Phien:
    """Một lượt làm việc với MCP Meta: giữ client_conversation_id xuyên các lệnh."""

    def __init__(self, conn, yeu_cau: str):
        self.conn = conn
        self.cid = _ma_hoi_thoai()
        self.yeu_cau = (yeu_cau or "lên camp")[:500]
        self.nhat_ky = []

    async def goi(self, tool: str, args: dict):
        import mcp_client
        spec = mcp_client._conn_spec(self.conn)
        spec["headers"].update(await mcp_client._oauth_headers(self.conn))
        a = {**args, "client_conversation_id": self.cid, "advertiser_job": JOB_META,
             "advertiser_request": self.yeu_cau}
        raw = await mcp_client.pool.call_tool(spec, tool, a)
        data = _doc_json(raw)
        moi = _tim(data, ("client_conversation_id",)) if data is not None else None
        if isinstance(moi, str) and re.fullmatch(r"[A-Za-z0-9]{20}", moi):
            self.cid = moi
        loi = ""
        if isinstance(raw, str) and raw.startswith("ERROR"):
            loi = raw[:600]
        elif isinstance(data, dict) and data.get("error"):
            loi = json.dumps(data.get("error"), ensure_ascii=False)[:600]
        self.nhat_ky.append({"tool": tool, "loi": loi[:200]})
        return data, (raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)), loi


def _viec_dang_chay() -> str:
    try:
        import once_ledger
        job = once_ledger.current_job() or ""
    except Exception:
        return ""
    return job.split(":", 1)[1] if job.startswith("kanban:") else ""


def _tasks():
    try:
        import tasks
        return tasks.current()
    except Exception:
        return None


def _bat_dau_2359() -> str:
    try:
        from zoneinfo import ZoneInfo
        bay_gio = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    except Exception:
        bay_gio = datetime.utcnow() + timedelta(hours=7)
    return bay_gio.strftime("%Y-%m-%dT23:59:00+07:00")


def _dong(n) -> str:
    return f"{int(n):,}".replace(",", ".") + "đ"


async def _landing_song(url: str) -> str:
    """"" nếu landing page trả trang được; khác rỗng = lý do lỗi."""
    if not re.match(r"^https?://", url or ""):
        return "địa chỉ landing page không hợp lệ"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0 MinMin"})
        if r.status_code >= 400:
            return f"landing page trả mã lỗi HTTP {r.status_code}"
        if len(r.text or "") < 200:
            return "landing page gần như trống"
    except Exception as e:
        return f"không mở được landing page ({type(e).__name__})"
    return ""


# ---------------------------------------------------------------------------
# Dựng camp TẮT
# ---------------------------------------------------------------------------
async def _dung_camp(args, ctx):
    import meta_ads_luat
    a = args or {}
    luat = meta_ads_luat.doc_luat()
    tk = meta_ads_luat.chuan_tk(a.get("tai_khoan") or (luat["tai_khoan"][0] if luat["tai_khoan"] else ""))
    page_id = re.sub(r"\D", "", str(a.get("page_id") or ""))
    page_ten = str(a.get("page_ten") or "").strip()
    ma_sp = str(a.get("ma_sp") or "").strip().upper()
    if not tk:
        return "ERROR: Chưa có tài khoản quảng cáo nào trong danh sách chủ cho phép (ô Giới hạn Đội Ads)."
    if not page_id or not page_ten or not ma_sp:
        return "ERROR: Cần đủ page_id, page_ten và ma_sp (mã sản phẩm thật, ví dụ P720)."
    try:
        ngan_sach = int(a.get("ngan_sach_ngay_vnd") or NGAN_SACH_MAC_DINH)
    except Exception:
        return "ERROR: ngan_sach_ngay_vnd phải là số đồng."
    if ngan_sach > luat["tran_ngay_vnd"]:
        return (f"ERROR: Ngân sách {_dong(ngan_sach)}/ngày vượt trần {_dong(luat['tran_ngay_vnd'])} "
                f"chủ đặt. Không dựng.")
    landing = str(a.get("landing_page") or "").strip()
    bai_viet = str(a.get("bai_viet_id") or "").strip()
    pixel = re.sub(r"\D", "", str(a.get("pixel_id") or ""))
    if bai_viet and "_" not in bai_viet:
        bai_viet = f"{page_id}_{bai_viet}"

    # Luật chọn loại camp của chủ.
    if landing:
        loi = await _landing_song(landing)
        if loi:
            return (f"ERROR: DỪNG - {loi} ({landing}). Theo luật của chủ, landing page lỗi thì "
                    f"không dựng camp và KHÔNG tự đổi sang camp bài viết. Báo chủ sửa landing page.")
        if not pixel:
            return ("ERROR: Camp chuyển đổi website cần pixel_id (Pixel/Dataset của tài khoản). "
                    "Đọc pixel bằng công cụ đọc dataset của Meta rồi gọi lại.")
        loai = "website"
        objective, goal, dest = "OUTCOME_SALES", "OFFSITE_CONVERSIONS", "WEBSITE"
        promoted = {"pixel_id": pixel, "custom_event_type": "PURCHASE"}
        if bai_viet:
            creative = {"object_story_id": bai_viet}
        else:
            msg = str(a.get("noi_dung") or "").strip()
            anh = str(a.get("image_hash") or "").strip()
            if not msg or not anh:
                return ("ERROR: Camp website không dùng bài có sẵn thì cần noi_dung và image_hash "
                        "(ảnh đã tải lên tài khoản quảng cáo).")
            creative = {"object_story_spec": {"page_id": page_id, "link_data": {
                "link": landing, "message": msg, "image_hash": anh,
                "call_to_action": {"type": "SHOP_NOW", "value": {"link": landing}}}}}
    else:
        if not bai_viet:
            return ("ERROR: Chưa có landing page thì luật của chủ là camp mua hàng từ BÀI VIẾT CÓ SẴN: "
                    "cần bai_viet_id (video/bài đăng hôm nay của page).")
        loai = "bai_viet"
        objective, goal, dest = "OUTCOME_ENGAGEMENT", "MESSAGING_PURCHASE_CONVERSION", "MESSENGER"
        promoted = {"page_id": page_id}
        creative = {"object_story_id": bai_viet}

    ten = f"{CHU_CTY} - {page_ten.upper()} - {ma_sp}"
    p = _Phien(_ket_noi(), a.get("yeu_cau") or "")
    if p.conn is None:
        return "ERROR: " + CHUA_NOI

    async def _ghi(tool, lenh):
        ly_do = meta_ads_luat.kiem_lenh(tool, lenh, "auto")
        if ly_do:
            return None, "", "CHẶN: " + ly_do
        return await p.goi(tool, lenh)

    lenh_camp = {"ad_account_id": tk, "campaign_name": ten, "objective": objective,
                 "buying_type": "AUCTION", "campaign_daily_budget": ngan_sach,
                 "special_ad_categories": "[]", "campaign_start_time": _bat_dau_2359()}
    d, raw, loi = await _ghi("ads_create_campaign", lenh_camp)
    if loi:
        return f"ERROR: Tạo chiến dịch không được: {loi}"
    camp_id = _ma(d, ("campaign_id",))
    if not camp_id:
        return f"ERROR: Meta không trả mã chiến dịch. Phản hồi: {raw[:400]}"
    nhap = str((d or {}).get("status") if isinstance(d, dict) else "").upper() == "DRAFT" or \
        str(_tim(d, ("status",)) or "").upper() == "DRAFT"

    lenh_nhom = {"ad_account_id": tk, "campaign_id": camp_id, "ad_set_name": ten,
                 "billing_event": "IMPRESSIONS", "optimization_goal": goal,
                 "destination_type": dest, "promoted_object": json.dumps(promoted),
                 "targeting": json.dumps(TARGETING_MAC_DINH), "start_time": _bat_dau_2359()}
    d, raw, loi = await _ghi("ads_create_ad_set", lenh_nhom)
    if loi and loai == "bai_viet" and "goal" in loi.lower():
        # Mục tiêu "mua qua tin nhắn" bị Meta khoá theo tài khoản: lùi về "cuộc trò chuyện".
        lenh_nhom["optimization_goal"] = goal = "CONVERSATIONS"
        d, raw, loi = await _ghi("ads_create_ad_set", lenh_nhom)
    ket = {"tai_khoan": tk, "campaign_id": camp_id, "adset_ids": [], "ad_ids": [], "ten": ten,
           "ngan_sach_ngay_vnd": ngan_sach, "trang_thai": "NHAP" if nhap else "TAT"}
    if loi:
        return (f"ERROR: Đã tạo chiến dịch {camp_id} (TẮT) nhưng tạo nhóm quảng cáo lỗi: {loi}. "
                f"Chiến dịch không chạy được khi thiếu nhóm; báo chủ, không bật.")
    adset_id = _ma(d, ("ad_set_id", "adset_id"))
    if not adset_id:
        return f"ERROR: Meta không trả mã nhóm quảng cáo. Phản hồi: {raw[:400]}"
    ket["adset_ids"] = [adset_id]

    lenh_qc = {"ad_account_id": tk, "ad_set_id": adset_id, "ad_name": ten,
               "creative": json.dumps(creative, ensure_ascii=False)}
    d, raw, loi = await _ghi("ads_create_ad", lenh_qc)
    if loi:
        return (f"ERROR: Đã tạo chiến dịch {camp_id} và nhóm {adset_id} (TẮT) nhưng tạo quảng cáo "
                f"lỗi: {loi}. Báo chủ, không bật.")
    ad_id = _ma(d, ("ad_id",))
    if not ad_id:
        return f"ERROR: Meta không trả mã quảng cáo. Phản hồi: {raw[:400]}"
    ket["ad_ids"] = [ad_id]
    loi_kiem = _tim(d, ("active_errors",))

    tid = _viec_dang_chay()
    da_luu = False
    f = _tasks()
    if tid and f is not None and hasattr(f, "job_ads_luu"):
        try:
            da_luu = bool(f.job_ads_luu(tid, ket))
        except Exception:
            da_luu = False
    ket.update({"ok": True, "loai_camp": loai, "muc_tieu_toi_uu": goal, "doi_tuong": "nữ 23-54, Việt Nam",
                "bat_dau": _bat_dau_2359(), "da_luu_vao_job": da_luu})
    if loi_kiem:
        ket["canh_bao_meta"] = loi_kiem
    ket["ghi_chu"] = ("Camp đang " + ("NHÁP trong Ads Manager" if nhap else "TẮT (PAUSED)")
                      + ", chưa chi đồng nào. Chỉ bước 'Bật camp' sau GATE chủ duyệt mới bật được.")
    return json.dumps(ket, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Bật camp
# ---------------------------------------------------------------------------
async def _doc_trang_thai(p, tk, ids, level, nhap=False, them=()):
    lenh = {"ad_account_id": tk, "object_ids": ids, "level": level,
            "fields": ["id", "name", "status", "effective_status", *them]}
    if nhap:
        lenh["object_state"] = "draft"
    d, raw, loi = await p.goi("ads_get_ad_entities", lenh)
    out = {}
    muon = {str(i) for i in ids}
    for _k, _v, o in _tim_het(d, ("effective_status", "status")):
        oid = str(o.get("id") or o.get("ad_object_id") or o.get("object_id") or "")
        if oid in muon:
            out[oid] = {"effective_status": str(o.get("effective_status") or ""),
                        "status": str(o.get("status") or "")}
    return out, loi, d


async def _bat_camp(args, ctx):
    import meta_ads_luat
    tid = _viec_dang_chay()
    f = _tasks()
    if not tid or f is None or not hasattr(f, "job_ads_doc"):
        return ("ERROR: Công cụ này chỉ chạy trong bước 'Bật camp' của một job Đội Ads, sau GATE chủ "
                "đã duyệt. Ngoài job thì chủ tự bật trong Ads Manager.")
    ads = f.job_ads_doc(tid) or {}
    if not ads.get("campaign_id"):
        return ("ERROR: Job này chưa có camp nào được dựng (bước dựng camp chưa lưu mã). Không có gì "
                "để bật. Báo chủ.")
    tk = meta_ads_luat.chuan_tk(ads.get("tai_khoan"))
    camp = str(ads["campaign_id"])
    nhom = [str(x) for x in ads.get("adset_ids") or []]
    qc = [str(x) for x in ads.get("ad_ids") or []]
    tat_ca = [camp] + nhom + qc
    nhap = ads.get("trang_thai") != "TAT"
    job = {"ids": tat_ca, "nhap": nhap}
    lenh_bat = {"ad_account_id": tk, "entity_id": camp, "entity_type": "campaign",
                "object_ids": tat_ca, "publish_as_active": True,
                "campaign_daily_budget": ads.get("ngan_sach_ngay_vnd")}
    ly_do = meta_ads_luat.kiem_lenh("ads_activate_entity", lenh_bat, "full", job=job)
    if ly_do:
        return "ERROR: CHẶN: " + ly_do
    lenh_bat.pop("campaign_daily_budget", None)

    p = _Phien(_ket_noi(), args.get("yeu_cau") or "bật camp đã duyệt")
    if p.conn is None:
        return "ERROR: " + CHUA_NOI

    # Đọc lại ngân sách THẬT trên Meta ngay trước khi bật: camp có thể đã bị sửa tay trong Ads
    # Manager sau lúc dựng. Không đọc được thì KHÔNG bật (fail-closed).
    tran = meta_ads_luat.doc_luat()["tran_ngay_vnd"]
    for level, ids in (("campaign", [camp]), ("adset", nhom)):
        if not ids:
            continue
        st0, loi0, d0 = await _doc_trang_thai(p, tk, ids, level, nhap=nhap,
                                              them=("daily_budget", "lifetime_budget"))
        if loi0 or not st0:
            return ("ERROR: Không đọc lại được ngân sách hiện tại của camp trên Meta"
                    + (f" ({loi0[:200]})" if loi0 else "") + ". Chưa bật, chưa chi tiền. Thử lại sau hoặc "
                    "chủ bật tay trong Ads Manager.")
        for k, v, _o in _tim_het(d0, {"daily_budget", "lifetime_budget", "campaign_daily_budget",
                                      "campaign_lifetime_budget"}):
            n = meta_ads_luat._so(v)
            if n is None:
                continue
            if "lifetime" in k and n > 0:
                return (f"ERROR: CHẶN: camp trên Meta đang có ngân sách trọn đời ({k}={v}). Có người đã "
                        f"sửa camp sau lúc dựng. Không bật, báo chủ.")
            if level == "adset" and n > 0:
                return (f"ERROR: CHẶN: nhóm quảng cáo đang có ngân sách riêng ({k}={v}), trần không tính "
                        f"đúng cho cả camp. Không bật, báo chủ.")
            if n > tran:
                return (f"ERROR: CHẶN: ngân sách hiện tại trên Meta ({k}={v}) vượt trần {tran}. Có người "
                        f"đã sửa camp sau lúc dựng. Không bật, báo chủ.")

    buoc = []
    if nhap:
        d, raw, loi = await p.goi("ads_activate_entity", lenh_bat)
        buoc.append(("đăng bản nháp + bật chiến dịch", loi or str(_tim(d, ("status", "publish_status")) or "ok")))
        if loi:
            return f"ERROR: Meta từ chối đăng camp: {loi}. Camp vẫn ở nháp, chưa chi tiền."
    else:
        lenh_tat = {"ad_account_id": tk, "entity_id": camp, "entity_type": "campaign"}
        ly_do = meta_ads_luat.kiem_lenh("ads_activate_entity", lenh_tat, "full", job=job)
        if ly_do:
            return "ERROR: CHẶN: " + ly_do
        d, raw, loi = await p.goi("ads_activate_entity", lenh_tat)
        buoc.append(("bật chiến dịch", loi or "ok"))
        if loi:
            return f"ERROR: Meta từ chối bật chiến dịch: {loi}. Chưa chi tiền."

    # Nhóm và quảng cáo: Meta chỉ bật đúng đối tượng đích; con nào còn TẮT thì bật từng cái
    # (trên xuống dưới), vì thiếu một cấp là camp không phân phối.
    for level, loai, ids in (("adset", "ad_set", nhom), ("ad", "ad", qc)):
        if not ids:
            continue
        st, _l, _d = await _doc_trang_thai(p, tk, ids, level)
        for oid in ids:
            if (st.get(oid) or {}).get("status", "").upper() == "ACTIVE":
                continue
            lenh = {"ad_account_id": tk, "entity_id": oid, "entity_type": loai}
            ly_do = meta_ads_luat.kiem_lenh("ads_activate_entity", lenh, "full", job=job)
            if ly_do:
                buoc.append((f"bật {loai} {oid}", "CHẶN: " + ly_do))
                continue
            _d2, _r2, loi2 = await p.goi("ads_activate_entity", lenh)
            buoc.append((f"bật {loai} {oid}", loi2 or "ok"))

    trang_thai = {}
    for level, ids in (("campaign", [camp]), ("adset", nhom), ("ad", qc)):
        if ids:
            st, _l, _d = await _doc_trang_thai(p, tk, ids, level)
            trang_thai.update(st)
    dang_chay = [i for i in tat_ca if (trang_thai.get(i) or {}).get("effective_status", "").upper() == "ACTIVE"]
    if len(dang_chay) == len(tat_ca):
        ket_luan = "Đã bật: chiến dịch, nhóm và quảng cáo đều ACTIVE khi đọc lại từ Meta."
    elif not trang_thai:
        ket_luan = ("Đã gửi lệnh bật nhưng CHƯA đọc lại được trạng thái từ Meta (có thể đang PUBLISHING). "
                    "Chưa được báo là đang chạy; chủ kiểm tra trong Ads Manager.")
    else:
        ket_luan = ("Đã gửi lệnh bật nhưng chưa phải mọi cấp đều ACTIVE (có thể đang chờ duyệt hoặc "
                    "PUBLISHING). Không báo là đang chạy cho tới khi Meta xác nhận.")
    return json.dumps({"ok": len(dang_chay) == len(tat_ca), "tai_khoan": "act_" + tk, "ten": ads.get("ten"),
                       "ngan_sach_ngay_vnd": ads.get("ngan_sach_ngay_vnd"), "cac_buoc": buoc,
                       "trang_thai_doc_lai": trang_thai, "ket_luan": ket_luan}, ensure_ascii=False)


def register(ctx):
    ctx.register_tool(
        "meta_ads_dung_camp",
        "Đội Ads: dựng MỘT camp Facebook ở trạng thái TẮT/NHÁP (chưa chi tiền) qua MCP Meta Ads chính "
        "chủ, theo luật của chủ: tên 'CÔNG TY TNHH MTV HALIMI - TÊN PAGE - MÃ SP', nữ 23-54 Việt Nam, "
        "bắt đầu 23:59 hôm nay, ngân sách ngày mặc định 300.000đ và không vượt trần, chỉ tài khoản chủ "
        "cho phép. Có landing_page hợp lệ (+ pixel_id) -> camp chuyển đổi website; không có -> camp mua "
        "hàng qua tin nhắn từ bai_viet_id có sẵn; landing lỗi -> dừng. Dùng tool này thay cho các lệnh "
        "ads_create_* thô. Không bao giờ bật camp.",
        _dung_camp,
        schema={"type": "object", "properties": {
            "page_id": {"type": "string", "description": "ID page Facebook"},
            "page_ten": {"type": "string", "description": "Tên page, để đặt tên camp"},
            "ma_sp": {"type": "string", "description": "Mã sản phẩm thật, ví dụ P720"},
            "bai_viet_id": {"type": "string", "description": "Bài viết/video có sẵn: 'pageID_postID' hoặc postID"},
            "landing_page": {"type": "string", "description": "Ladipage/Webcake (để trống nếu chưa có)"},
            "pixel_id": {"type": "string", "description": "Pixel cho camp website"},
            "noi_dung": {"type": "string", "description": "Chữ quảng cáo khi camp website không dùng bài có sẵn"},
            "image_hash": {"type": "string", "description": "Ảnh đã tải lên tài khoản, khi không dùng bài có sẵn"},
            "ngan_sach_ngay_vnd": {"type": "integer", "description": "Đồng/ngày, mặc định 300000"},
            "tai_khoan": {"type": "string", "description": "Mặc định tài khoản đầu danh sách cho phép"},
            "yeu_cau": {"type": "string", "description": "Lời yêu cầu của chủ, nguyên văn"},
        }, "required": ["page_id", "page_ten", "ma_sp"]},
        min_mode="safe", check_fn=_check, ton_phi=True,
    )
    ctx.register_tool(
        "meta_ads_bat_camp",
        "Đội Ads: BẬT camp đã dựng của job hiện tại, chỉ dùng ở bước 'Bật camp' sau GATE chủ đã duyệt. "
        "Không nhận mã camp: tự đọc đúng các mã bước dựng camp đã lưu trong job, kiểm luật lần nữa, bật, "
        "rồi đọc lại trạng thái thật từ Meta. Báo đúng kết luận tool trả về, không báo 'đang chạy' khi "
        "Meta chưa xác nhận ACTIVE.",
        _bat_camp,
        schema={"type": "object", "properties": {
            "yeu_cau": {"type": "string", "description": "Lời yêu cầu của chủ, nguyên văn"}}},
        min_mode="full", check_fn=_check,
    )
