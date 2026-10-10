"""26.10.123: plugin hoa-don-doc cho bộ não đọc kho hoá đơn TCT.

    python tests/run.py hoa_don_doc

Không mạng: dựng STATE_DIR giả với 1 doanh nghiệp + kho hoá đơn, rồi gọi tool.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import json
import os
import sys
import tempfile

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-hddoc-")

import routes.hoa_don as hd  # noqa: E402
import plugins_host  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


MST = "2401063265"
cfg = hd.doc_cau_hinh()
cfg["doanh_nghiep"][MST] = {"ten": "Công ty TNHH MTV HALIMI"}
hd.ghi_cau_hinh(cfg)
hd._ghi_json(hd._kho_path(MST, "purchase"), {
    "a": {"tgtcthue": 19817920, "tgtthue": 1585434, "tgtttbso": 21403354, "tdlap": "2026-10-09T00:00:00",
          "shdon": "770", "khhdon": "C26TNY", "nbmst": "0319457633", "_loai": "purchase"},
    "b": {"tgtcthue": 12300000, "tgtthue": 984000, "tgtttbso": 13284000, "tdlap": "2026-09-15T00:00:00",
          "shdon": "40", "khhdon": "C26TAA", "nbmst": "0319485542", "_loai": "purchase"}})
hd._ghi_json(hd._kho_path(MST, "sold"), {
    "c": {"tgtcthue": 444444, "tgtthue": 35556, "tgtttbso": 480000, "tdlap": "2026-10-10T00:00:00",
          "shdon": "56532", "khhdon": "C26THL", "nmmst": "", "_loai": "sold"}})


async def main():
    # 1) plugin bundled được khám phá + nạp
    desc = {d["slug"]: d for d in plugins_host.describe(None)}
    check("plugin hoa-don-doc được khám phá", "hoa-don-doc" in desc, sorted(desc))
    check("hoa-don-doc bật + nạp mặc định", desc.get("hoa-don-doc", {}).get("loaded"), desc.get("hoa-don-doc"))

    tools, route = plugins_host.plugin_tools("full", None)
    names = {t["fn"] for t in tools}
    check("hai tool xuất hiện", {"hoa_don_tong_hop", "hoa_don_danh_sach"} <= names, sorted(names))
    # readonly: phải chạy được cả ở mức suggest
    _, route_sg = plugins_host.plugin_tools("suggest", None)
    check("tool chỉ-đọc chạy ở mức suggest", "hoa_don_tong_hop" in route_sg)

    th = json.loads(await route["hoa_don_tong_hop"]["call"]({}))
    dn = th["doanh_nghiep"][0]
    check("tổng hợp mua vào: đúng số hoá đơn", dn["mua_vao"]["so_hd"] == 2, dn["mua_vao"])
    check("tổng hợp mua vào: đúng thuế", dn["mua_vao"]["thue"] == 2569434, dn["mua_vao"])
    check("tổng hợp bán ra: đúng số", dn["ban_ra"]["so_hd"] == 1 and dn["ban_ra"]["tong"] == 480000, dn["ban_ra"])

    thl = json.loads(await route["hoa_don_tong_hop"]["call"]({"tu": "2026-10-01", "den": "2026-10-31", "loai": "mua"}))
    check("lọc kỳ tháng 10 chỉ còn 1 hoá đơn mua", thl["doanh_nghiep"][0]["mua_vao"]["so_hd"] == 1, thl)
    check("lọc loai=mua thì không trả bán ra", "ban_ra" not in thl["doanh_nghiep"][0], thl)

    ds = json.loads(await route["hoa_don_danh_sach"]["call"]({"gioi_han": 10}))
    check("danh sách: đủ 3 hoá đơn, mới nhất trước", ds["tong_so_khop"] == 3
          and ds["hoa_don"][0]["ngay"] == "2026-10-10", ds)
    check("danh sách: trần gioi_han chặn trên 200", json.loads(
        await route["hoa_don_danh_sach"]["call"]({"gioi_han": 9999}))["tra_ve"] == 3)

    err = await route["hoa_don_tong_hop"]["call"]({"mst": "0000000000"})
    check("MST chưa đăng nhập: báo lỗi rõ", err.startswith("ERROR"), err)
    err2 = await route["hoa_don_tong_hop"]["call"]({"tu": "10/2026"})
    check("kỳ sai định dạng: báo lỗi", err2.startswith("ERROR"), err2)


asyncio.run(main())

check("không dùng gạch dài", "—" not in open(
    os.path.join(ROOT, "system/plugins/hoa-don-doc/plugin.py"), encoding="utf-8").read())

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
