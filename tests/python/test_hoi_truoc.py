"""test_hoi_truoc.py - cổng HỎI TRƯỚC cho hành động ra ngoài (26.10.165)."""
import asyncio
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import ROOT, SERVER  # noqa: E402,F401
import hanh_dong as hd  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:200] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# chính sách
check("hoi_truoc là giá trị hợp lệ", hd.chuan_hoa_chinh_sach({"tien": "hoi_truoc", "xoa": "chan"}) == {"tien": "hoi_truoc", "xoa": "chan"})
check("can_hoi đúng loại", hd.can_hoi({"tien": "hoi_truoc"}, "tien") and not hd.can_hoi({"tien": "hoi_truoc"}, "xoa") and not hd.can_hoi({}, "tien"))
check("cho_phep vẫn cho qua loại hỏi trước (cổng hỏi nằm riêng)", hd.cho_phep({"tien": "hoi_truoc"}, "tien")[0])


# máy trạng thái
async def _kich_ban():
    bao = []

    async def _tb(yc):
        bao.append(yc)

    hd.dat_thong_bao(_tb)
    yc = hd.tao_yeu_cau(ai="web:abc", tool="meta_ads_update", connector="meta-ads", label="Ads",
                        loai="tien", args={"budget": 500000, "access_token": "EAAB123"})
    check("yêu cầu đang chờ, có trong danh sách", yc["trang_thai"] == "cho" and any(x["id"] == yc["id"] for x in hd.danh_sach_cho()))
    check("danh sách không chứa event, args che token", "event" not in hd.danh_sach_cho()[0] and "EAAB" not in hd.danh_sach_cho()[0]["args"])

    async def _gat_sau(giay):
        await asyncio.sleep(giay)
        return hd.quyet(yc["id"], True, ai="telegram:1")

    t = asyncio.ensure_future(_gat_sau(0.2))
    kq = await hd.cho_quyet(yc, timeout=5)
    ok, _ = await t
    check("chủ gật -> dong_y, có người quyết", kq == "dong_y" and ok and yc["nguoi_quyet"] == "telegram:1")
    check("đã báo chủ một lần", len(bao) == 1 and bao[0]["id"] == yc["id"] and "event" not in bao[0])
    check("quyết hai lần thì từ chối", not hd.quyet(yc["id"], False)[0])
    check("hết chờ thì khỏi danh sách chờ", all(x["id"] != yc["id"] for x in hd.danh_sach_cho()))

    yc2 = hd.tao_yeu_cau(ai="web:abc", tool="zalo_send_message", connector="zalo", label="Zalo", loai="nhan_tin", args={})
    asyncio.ensure_future(_lac(yc2["id"]))
    kq2 = await hd.cho_quyet(yc2, timeout=5)
    check("chủ lắc -> tu_choi", kq2 == "tu_choi")

    yc3 = hd.tao_yeu_cau(ai="loop:x", tool="pos_order_create", connector="pancake", label="POS", loai="don_hang", args={})
    kq3 = await hd.cho_quyet(yc3, timeout=5)   # timeout kẹp tối thiểu 5s
    check("không ai quyết -> het_gio", kq3 == "het_gio")
    check("yêu cầu lạ -> không quyết được", not hd.quyet("khong-co", True)[0])
    hd.dat_thong_bao(None)


async def _lac(ma):
    await asyncio.sleep(0.1)
    hd.quyet(ma, False, ai="dashboard")


asyncio.run(_kich_ban())


# tích hợp với hub: tool ghi loại "tien" ở mức hỏi trước -> không chạy khi từ chối, chạy khi đồng ý
import mcp_hub  # noqa: E402

hd._DUONG = Path(tempfile.mkdtemp()) / "so.jsonl"
goi = []


async def _kich_ban_hub():
    import mcp_client

    async def _fake_call(route, fn, args):
        goi.append((fn, args))
        return '{"ok":true}'

    mcp_client.call_route = _fake_call
    mcp_hub._chinh_sach_loai_viec = lambda: {"tien": "hoi_truoc"}
    mcp_hub._hoi_truoc_giay = lambda: 5.0
    mcp_hub._rate_ok = lambda *a, **k: True
    ent = {"conn": {"id": "c1", "connector_id": "meta-ads", "label": "Ads", "perm": "full"},
           "tool": "ads_update_budget", "spec": {}}
    g = mcp_hub._guard(ent, "mcp__javis__meta__ads_update_budget", "full")

    async def _tu_choi_sau():
        await asyncio.sleep(0.2)
        for y in hd.danh_sach_cho():
            hd.quyet(y["id"], False, ai="dashboard")

    asyncio.ensure_future(_tu_choi_sau())
    r = await g({"budget": 1})
    check("hub: từ chối -> tool KHÔNG chạy, trả ERROR nói CHƯA LÀM", not goi and str(r).startswith("ERROR:") and "CHƯA LÀM" in str(r), r)

    async def _dong_y_sau():
        await asyncio.sleep(0.2)
        for y in hd.danh_sach_cho():
            hd.quyet(y["id"], True, ai="dashboard")

    asyncio.ensure_future(_dong_y_sau())
    r2 = await g({"budget": 2})
    check("hub: đồng ý -> tool chạy thật", len(goi) == 1 and goi[0][1] == {"budget": 2} and "ok" in str(r2), (goi, r2))
    so = hd.doc(10)
    check("sổ: có dòng ĐÃ DUYỆT và dòng CHẶN (hỏi trước)", any("ĐÃ DUYỆT" in d.get("err", "") for d in so) and any("hỏi trước" in d.get("err", "") for d in so), so)
    # đọc thì không hỏi
    ent_doc = {"conn": {"id": "c1", "connector_id": "meta-ads", "label": "Ads", "perm": "full"},
               "tool": "ads_get_insights", "spec": {}}
    g2 = mcp_hub._guard(ent_doc, "mcp__javis__meta__ads_get_insights", "full")
    r3 = await g2({})
    check("hub: tool đọc không qua cổng hỏi", len(goi) == 2 and not str(r3).startswith("ERROR:"), r3)


asyncio.run(_kich_ban_hub())

if fails:
    print("ĐỎ", len(fails), fails)
    sys.exit(1)
print("OK - test_hoi_truoc: tất cả pass")
