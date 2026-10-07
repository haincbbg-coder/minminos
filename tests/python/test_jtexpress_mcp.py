"""Cầu nối J&T Express Việt Nam (server/jtexpress_mcp.py). Không mạng.

    python tests/run.py jtexpress_mcp

Phủ: chữ ký data_digest = base64(md5_hex(logistics_interface + key)) so với tính độc lập, dạng ký
khớp mẫu trong tài liệu J&T (giải base64 ra 32 ký tự hex); form 4 ô đúng tên; đúng đường dẫn
và msg_type; địa chỉ máy chủ do người dùng điền được kiểm (chặn query, @, ..); kiểm tra đầu vào
(sai thì KHÔNG gọi mạng); dạng lỗi success false; không lộ key; thiếu ô; tool lạ.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import base64
import hashlib
import json
import re

import httpx

from _gia_http import GiaHttp, KiemTra
import jtexpress_mcp as j

check = KiemTra()
KEY = "khoa-ky-jt-bi-mat-04fc653c"
ECC = "HALIMI"
BASE = "https://api.jt.vi.du/yuenan-interface-web"


def spec(**them):
    sec = {"dia_chi_api": BASE, "eccompanyid": ECC, "api_key": KEY}
    sec.update(them)
    return {"key": "conn-jt-1", "secrets": sec}


def chay(tool, args=None, sp=None):
    return asyncio.run(j.call(tool, args or {}, sp if sp is not None else spec()))


def ky_doc_lap(li, key):
    return base64.b64encode(hashlib.md5((li + key).encode("utf-8")).hexdigest().encode()).decode()


OK = {"logisticproviderid": "YL", "responseitems": [{"success": "true", "reason": "",
                                                     "tracesList": [{"billcode": "842009356289",
                                                                     "details": [{"scantype": "Picked Up"}]}]}]}

# ---- 0. khai báo ----
ten = [t["name"] for t in asyncio.run(j.list_tools({}))]
check("đủ 2 tool", ten == ["jt_tra_hanh_trinh", "jt_huy_don"], ten)
ra = chay("jt_tra_hanh_trinh", {"billcode": "1"}, {"secrets": {"dia_chi_api": BASE, "eccompanyid": ECC}})
check("thiếu api_key -> báo rõ", ra.startswith("ERROR") and "api_key" in ra, ra)
check("tool lạ -> ERROR", chay("jt_xoa_het").startswith("ERROR"))

# ---- 1. chữ ký ----
mau = base64.b64decode("OTViYjc0MGQwYjVlNzQ1ZjlhNjM4NDZmMjJjZmQ4YjY=").decode()
check("mẫu ký trong tài liệu J&T là base64 của md5 dạng hex", re.fullmatch(r"[0-9a-f]{32}", mau) is not None, mau)
li = '{"billcode":"842009356289","lang":"en"}'
check("ky() khớp tính độc lập", j.ky(li, KEY) == ky_doc_lap(li, KEY))
check("ky() có dấu tiếng Việt vẫn khớp (utf-8)", j.ky('{"x":"Hủy"}', KEY) == ky_doc_lap('{"x":"Hủy"}', KEY))
check("ky() đổi key thì đổi chữ ký", j.ky(li, KEY) != j.ky(li, KEY + "x"))

# ---- 2. tra hành trình ----
gia = GiaHttp().lap()
gia.tra("trackForJson", OK)
ra = chay("jt_tra_hanh_trinh", {"billcode": "842009356289"})
r = gia.goi[-1]
check("hành trình trả mốc quét", "Picked Up" in ra, ra)
check("hành trình POST đúng URL", r["method"] == "POST" and r["url"] == BASE + "/standart/trackAction!trackForJson", r["url"])
check("gửi dạng form", r["headers"].get("Content-Type") == "application/x-www-form-urlencoded" and r["json"] is None)
f = r["data"]
check("form đủ 4 ô", set(f) == {"logistics_interface", "data_digest", "msg_type", "eccompanyid"}, f)
check("msg_type TRACKQUERY, eccompanyid", f["msg_type"] == "TRACKQUERY" and f["eccompanyid"] == ECC)
check("logistics_interface đúng nội dung", json.loads(f["logistics_interface"]) == {"billcode": "842009356289", "lang": "en"})
check("data_digest ký đúng chuỗi đã gửi", f["data_digest"] == ky_doc_lap(f["logistics_interface"], KEY))
check("key không nằm trong form", KEY not in json.dumps(f, ensure_ascii=False))
chay("jt_tra_hanh_trinh", {"billcode": "842009356289", "ngon_ngu": "vn"})
check("ngôn ngữ vn", json.loads(gia.goi[-1]["data"]["logistics_interface"])["lang"] == "vn")
n = len(gia.goi)
for bad in ("", "a/b", "../x", "a?b", "1" * 41):
    check(f"billcode {bad[:12]!r} -> ERROR", chay("jt_tra_hanh_trinh", {"billcode": bad}).startswith("ERROR"))
check("ngôn ngữ lạ -> ERROR", chay("jt_tra_hanh_trinh", {"billcode": "1", "ngon_ngu": "fr"}).startswith("ERROR"))
check("đầu vào sai KHÔNG gọi mạng", len(gia.goi) == n)

# địa chỉ máy chủ
chay("jt_tra_hanh_trinh", {"billcode": "1"}, spec(dia_chi_api="api.jt.vi.du:8080/yuenan-interface-web/"))
check("không ghi giao thức thì dùng https, bỏ / cuối",
      gia.goi[-1]["url"] == "https://api.jt.vi.du:8080/yuenan-interface-web/standart/trackAction!trackForJson",
      gia.goi[-1]["url"])
n = len(gia.goi)
for bad in ("https://a.vn/x?y=1", "https://user:pw@a.vn", "https://a.vn/../b", "ftp://a.vn", "https://a.vn/#x",
            "javascript:alert(1)"):
    check(f"địa chỉ {bad!r} bị chặn", chay("jt_tra_hanh_trinh", {"billcode": "1"}, spec(dia_chi_api=bad)).startswith("ERROR"))
check("địa chỉ sai KHÔNG gọi mạng", len(gia.goi) == n)
gia.go()

# ---- 3. hủy đơn ----
gia = GiaHttp().lap()
gia.tra("orderAction!createOrder", {"logisticproviderid": "JT", "responseitems": [{"success": "true", "txlogisticid": "HL-1"}]})
ra = chay("jt_huy_don", {"txlogisticid": "HL-1", "ly_do": "Khách đổi ý"})
r = gia.goi[-1]
check("hủy đơn thành công", not ra.startswith("ERROR"), ra)
check("hủy đơn POST đúng URL", r["url"] == BASE + "/order/orderAction!createOrder")
f = r["data"]
check("hủy đơn msg_type UPDATE", f["msg_type"] == "UPDATE")
check("hủy đơn nội dung WITHDRAW", json.loads(f["logistics_interface"]) == {
    "eccompanyid": ECC, "logisticproviderid": "JNT",
    "fieldlist": [{"txlogisticid": "HL-1", "fieldname": "status", "fieldvalue": "WITHDRAW", "remark": "Khách đổi ý"}]},
    f["logistics_interface"])
check("hủy đơn ký đúng", f["data_digest"] == ky_doc_lap(f["logistics_interface"], KEY))
n = len(gia.goi)
check("hủy mã ../x -> ERROR", chay("jt_huy_don", {"txlogisticid": "../x"}).startswith("ERROR"))
check("hủy mã a/b -> ERROR", chay("jt_huy_don", {"txlogisticid": "a/b"}).startswith("ERROR"))
check("hủy thiếu mã -> ERROR", chay("jt_huy_don", {}).startswith("ERROR"))
check("hủy lý do quá dài -> ERROR", chay("jt_huy_don", {"txlogisticid": "A", "ly_do": "x" * 201}).startswith("ERROR"))
check("hủy sai KHÔNG gọi mạng", len(gia.goi) == n)
gia.go()

# ---- 4. lỗi, không lộ bí mật ----
gia = GiaHttp().lap()
gia.tra("orderAction!createOrder", {"logisticproviderid": "JT",
                                    "responseitems": [{"success": "false", "reason": "S10 " + KEY}]})
ra = chay("jt_huy_don", {"txlogisticid": "A1"})
check("success false -> ERROR có mã lý do", ra.startswith("ERROR") and "S10" in ra, ra)
check("lỗi nghiệp vụ không lộ key", KEY not in ra, ra)
gia.tra("trackForJson", {"responseitems": []})
check("responseitems rỗng -> ERROR", chay("jt_tra_hanh_trinh", {"billcode": "1"}).startswith("ERROR"))
gia.tra("trackForJson", {"loi": "bad key " + KEY}, code=500)
ra = chay("jt_tra_hanh_trinh", {"billcode": "1"})
check("HTTP 500 -> ERROR không lộ key", ra.startswith("ERROR") and KEY not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("trackForJson", "<html>bad gateway</html>")
check("trả về không phải JSON -> ERROR", chay("jt_tra_hanh_trinh", {"billcode": "1"}).startswith("ERROR"))
gia.nem_loi("trackForJson", httpx.ConnectError("timeout key=" + KEY))
ra = chay("jt_tra_hanh_trinh", {"billcode": "1"})
check("ngoại lệ mạng -> ERROR không lộ key", ra.startswith("ERROR") and KEY not in ra, ra)
gia.tra("trackForJson", {"responseitems": [{"success": "true", "ghi_chu": KEY}]})
ra = chay("jt_tra_hanh_trinh", {"billcode": "1"})
check("kết quả thành công nhại key cũng bị giấu", KEY not in ra, ra)
gia.go()

src = open(SERVER / "jtexpress_mcp.py", encoding="utf-8").read()
check("không có em/en dash", "\u2014" not in src and "\u2013" not in src)

check.ket_thuc()
