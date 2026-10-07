"""Cầu nối payOS (server/payos_mcp.py). Không mạng.

    python tests/run.py payos_mcp

Phủ: header x-client-id / x-api-key, chữ ký yêu cầu tạo link so với HMAC tính độc lập, chữ ký
phản hồi đúng thì nhận và bị sửa thì từ chối, kiểm tra số tiền / nội dung / URL / orderCode
trước khi gọi mạng, id xem/huỷ chỉ nhận chữ và số, dạng lỗi code != "00", không lộ bí mật.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import hashlib
import hmac
import json
import time

from _gia_http import GiaHttp, KiemTra
import payos_mcp as p

check = KiemTra()
CID = "client-id-payos-0001"
AKEY = "api-key-payos-bi-mat-7777"
CKEY = "checksum-key-payos-bi-mat-8888"


def spec(**them):
    sec = {"client_id": CID, "api_key": AKEY, "checksum_key": CKEY,
           "return_url": "https://halimi.vn/cam-on", "cancel_url": "https://halimi.vn/huy"}
    sec.update(them)
    return {"key": "conn-payos-1", "secrets": sec}


def chay(x):
    return asyncio.run(x)


def hm(s):
    return hmac.new(CKEY.encode(), s.encode(), hashlib.sha256).hexdigest()


# Dữ liệu phản hồi mẫu và chuỗi ký viết TAY (không dùng hàm của module) để đối chiếu độc lập.
DATA = {"bin": "970422", "accountNumber": "113366668888", "accountName": "CONG TY HALIMI",
        "amount": 250000, "description": "DH1234", "orderCode": 1234, "currency": "VND",
        "paymentLinkId": "124c33293c934a85be5b7f8761a27a07", "status": "PENDING", "expiredAt": None,
        "checkoutUrl": "https://pay.payos.vn/web/124c33293c934a85be5b7f8761a27a07",
        "qrCode": "00020101021238570010A000000727"}
CHUOI_TAY = ("accountName=CONG TY HALIMI&accountNumber=113366668888&amount=250000&bin=970422"
             "&checkoutUrl=https://pay.payos.vn/web/124c33293c934a85be5b7f8761a27a07&currency=VND"
             "&description=DH1234&expiredAt=&orderCode=1234&paymentLinkId=124c33293c934a85be5b7f8761a27a07"
             "&qrCode=00020101021238570010A000000727&status=PENDING")
SIG = hm(CHUOI_TAY)

ten = [t["name"] for t in chay(p.list_tools({}))]
check("đủ 3 tool", ten == ["payos_tao_link", "payos_xem_link", "payos_huy_link"], ten)

# ---- 1. hàm ký ----
check("chuỗi dữ liệu phản hồi khớp chuỗi viết tay", p.chuoi_du_lieu(DATA) == CHUOI_TAY, p.chuoi_du_lieu(DATA))
check("chữ ký phản hồi khớp HMAC độc lập", p.ky_du_lieu(CKEY, DATA) == SIG)
check("chữ ký đúng -> nhận", p.chu_ky_dung(CKEY, DATA, SIG))
check("chữ ký IN HOA vẫn nhận", p.chu_ky_dung(CKEY, DATA, SIG.upper()))
check("sửa checkoutUrl -> từ chối", not p.chu_ky_dung(CKEY, {**DATA, "checkoutUrl": "https://evil.example/pay"}, SIG))
check("sửa số tiền -> từ chối", not p.chu_ky_dung(CKEY, {**DATA, "amount": 1}, SIG))
check("sai checksum key -> từ chối", not p.chu_ky_dung("khoa-khac", DATA, SIG))
check("thiếu chữ ký -> từ chối", not p.chu_ky_dung(CKEY, DATA, None) and not p.chu_ky_dung(CKEY, DATA, ""))
long = {"b": [{"z": 1, "a": "x"}], "a": {"y": None, "x": True}, "c": False}
check("list/object JSON gọn, khoá xếp theo tên, bool true/false",
      p.chuoi_du_lieu(long) == 'a={"x":true,"y":null}&b=[{"a":"x","z":1}]&c=false', p.chuoi_du_lieu(long))
check("chữ ký yêu cầu khớp HMAC độc lập",
      p.ky_tao_link(CKEY, 2000, "https://a.vn/c", "DH9", 77, "https://a.vn/r")
      == hm("amount=2000&cancelUrl=https://a.vn/c&description=DH9&orderCode=77&returnUrl=https://a.vn/r"))

# ---- 2. tạo link: request đúng, phản hồi có chữ ký đúng ----
gia = GiaHttp().lap()
gia.tra("/v2/payment-requests", {"code": "00", "desc": "success", "data": DATA, "signature": SIG})
ra = chay(p.call("payos_tao_link", {"amount": 250000, "description": "DH1234", "orderCode": 1234,
                                    "items": [{"name": "Váy lụa", "quantity": 1, "price": 250000}],
                                    "buyerName": "Chị Lan", "buyerPhone": "0900000000"}, spec()))
g = gia.goi[-1]
b = g["json"]
check("tạo link: POST đúng URL", g["method"] == "POST" and g["url"] == "https://api-merchant.payos.vn/v2/payment-requests", g["url"])
check("tạo link: header x-client-id/x-api-key", g["headers"].get("x-client-id") == CID and g["headers"].get("x-api-key") == AKEY, g["headers"])
check("tạo link: KHÔNG gửi checksum key đi", CKEY not in json.dumps(g["headers"]) + json.dumps(b, ensure_ascii=False))
check("tạo link: URL mặc định từ kết nối", b["returnUrl"] == "https://halimi.vn/cam-on" and b["cancelUrl"] == "https://halimi.vn/huy", b)
check("tạo link: chữ ký yêu cầu đúng công thức",
      b["signature"] == hm("amount=250000&cancelUrl=https://halimi.vn/huy&description=DH1234&orderCode=1234"
                           "&returnUrl=https://halimi.vn/cam-on"), b)
check("tạo link: items + người mua", b["items"] == [{"name": "Váy lụa", "quantity": 1, "price": 250000}]
      and b["buyerName"] == "Chị Lan", b)
check("tạo link: chữ ký đúng -> trả checkoutUrl", "checkoutUrl" in ra and "pay.payos.vn" in ra, ra)
check("tạo link: không lộ bí mật", all(x not in ra for x in (AKEY, CKEY)))

# orderCode tự sinh
chay(p.call("payos_tao_link", {"amount": 10000, "description": "Test",
                               "returnUrl": "http://localhost:8000/ok", "cancelUrl": "http://localhost/huy"}, spec()))
b = gia.goi[-1]["json"]
check("orderCode tự sinh là số nguyên dương trong giới hạn", isinstance(b["orderCode"], int)
      and 1 <= b["orderCode"] <= p.MA_DON_TOI_DA, b["orderCode"])
check("cho phép http://localhost khi thử", b["returnUrl"] == "http://localhost:8000/ok")
check("orderCode tự sinh được ký theo đúng giá trị gửi đi",
      b["signature"] == hm(f"amount=10000&cancelUrl=http://localhost/huy&description=Test&orderCode={b['orderCode']}"
                           "&returnUrl=http://localhost:8000/ok"))
gia.go()

# ---- 3. phản hồi bị sửa -> từ chối ----
gia = GiaHttp().lap()
gia.tra("/v2/payment-requests", {"code": "00", "desc": "success",
                                 "data": {**DATA, "checkoutUrl": "https://evil.example/pay"}, "signature": SIG})
ra = chay(p.call("payos_tao_link", {"amount": 250000, "description": "DH1234", "orderCode": 1234}, spec()))
check("phản hồi bị sửa -> ERROR chữ ký không khớp", ra.startswith("ERROR") and "chữ ký phản hồi không khớp" in ra, ra)
check("phản hồi bị sửa -> không đưa link giả ra", "evil.example" not in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/v2/payment-requests", {"code": "00", "desc": "success", "data": DATA})
ra = chay(p.call("payos_tao_link", {"amount": 250000, "description": "DH1234", "orderCode": 1234}, spec()))
check("phản hồi thiếu chữ ký -> ERROR", ra.startswith("ERROR") and "chữ ký" in ra, ra)
gia.go()

# ---- 4. kiểm tra đầu vào, không gọi mạng ----
gia = GiaHttp().lap()
for args, mo_ta in [
    ({"amount": 999, "description": "x"}, "dưới 1.000đ"),
    ({"amount": 500_000_001, "description": "x"}, "trên 500 triệu"),
    ({"amount": "abc", "description": "x"}, "amount chữ"),
    ({"amount": 1500.5, "description": "x"}, "amount lẻ"),
    ({"amount": True, "description": "x"}, "amount bool"),
    ({"description": "x"}, "thiếu amount"),
    ({"amount": 10000}, "thiếu description"),
    ({"amount": 10000, "description": "x" * 26}, "description 26 ký tự"),
    ({"amount": 10000, "description": "x", "orderCode": 0}, "orderCode 0"),
    ({"amount": 10000, "description": "x", "orderCode": -5}, "orderCode âm"),
    ({"amount": 10000, "description": "x", "orderCode": p.MA_DON_TOI_DA + 1}, "orderCode vượt giới hạn"),
    ({"amount": 10000, "description": "x", "returnUrl": "http://halimi.vn/ok"}, "returnUrl http"),
    ({"amount": 10000, "description": "x", "cancelUrl": "javascript:alert(1)"}, "cancelUrl javascript"),
    ({"amount": 10000, "description": "x", "returnUrl": "http://localhost.evil.com/x"}, "localhost giả"),
    ({"amount": 10000, "description": "x", "items": "váy"}, "items không phải list"),
    ({"amount": 10000, "description": "x", "items": [{"name": "A", "quantity": 0, "price": 1}]}, "quantity 0"),
    ({"amount": 10000, "description": "x", "expiredAt": int(time.time()) - 10}, "expiredAt quá khứ"),
]:
    ra = chay(p.call("payos_tao_link", args, spec()))
    check(f"chặn {mo_ta}", ra.startswith("ERROR"), ra)
ra = chay(p.call("payos_tao_link", {"amount": 10000, "description": "x"}, spec(return_url="", cancel_url="")))
check("chặn khi thiếu URL mặc định lẫn truyền vào", ra.startswith("ERROR") and "returnUrl" in ra, ra)
for tool in ("payos_xem_link", "payos_huy_link"):
    for v in ("../v2/payment-requests", "", "a b", "x" * 65, "1;DROP"):
        ra = chay(p.call(tool, {"id": v}, spec()))
        check(f"{tool}: chặn id {v[:20]!r}", ra.startswith("ERROR"), ra)
check("không request nào đi ra khi đầu vào xấu", gia.goi == [], gia.goi)
gia.go()

# ---- 5. xem / huỷ ----
gia = GiaHttp().lap()
gia.tra("/v2/payment-requests/", {"code": "00", "desc": "success",
                                  "data": {"orderCode": 1234, "status": "PAID", "amountPaid": 250000}, "signature": "x"})
ra = chay(p.call("payos_xem_link", {"id": "1234"}, spec()))
g = gia.goi[-1]
check("xem: GET đúng URL", g["method"] == "GET" and g["url"] == "https://api-merchant.payos.vn/v2/payment-requests/1234", g["url"])
check("xem: header đủ", g["headers"].get("x-client-id") == CID and g["headers"].get("x-api-key") == AKEY)
check("xem: trả trạng thái", "PAID" in ra, ra)
chay(p.call("payos_xem_link", {"id": "124c33293c934a85be5b7f8761a27a07"}, spec()))
check("xem: nhận paymentLinkId", gia.goi[-1]["url"].endswith("/v2/payment-requests/124c33293c934a85be5b7f8761a27a07"))
gia.tra("/v2/payment-requests/1234/cancel", {"code": "00", "desc": "success", "data": {"orderCode": 1234, "status": "CANCELLED"}})
ra = chay(p.call("payos_huy_link", {"id": "1234", "cancellationReason": "Khách đổi ý"}, spec()))
g = gia.goi[-1]
check("huỷ: POST đúng URL", g["method"] == "POST" and g["url"] == "https://api-merchant.payos.vn/v2/payment-requests/1234/cancel", g["url"])
check("huỷ: gửi lý do", g["json"] == {"cancellationReason": "Khách đổi ý"}, g["json"])
check("huỷ: trả CANCELLED", "CANCELLED" in ra, ra)
chay(p.call("payos_huy_link", {"id": "1234"}, spec()))
check("huỷ: không lý do thì body rỗng", gia.goi[-1]["json"] == {}, gia.goi[-1]["json"])
gia.go()

# ---- 6. lỗi + bí mật ----
gia = GiaHttp().lap()
gia.tra("/v2/payment-requests/", {"code": "101", "desc": "Không tìm thấy đơn thanh toán", "data": None})
ra = chay(p.call("payos_xem_link", {"id": "999"}, spec()))
check("code != 00 -> ERROR kèm desc", ra.startswith("ERROR") and "101" in ra and "Không tìm thấy" in ra, ra)
gia.go()
gia = GiaHttp().lap()
gia.tra("/v2/payment-requests", {"code": "20", "desc": f"x-api-key {AKEY} sai, checksum {CKEY}"}, code=401)
ra = chay(p.call("payos_tao_link", {"amount": 10000, "description": "x"}, spec()))
check("HTTP 401 vọng lại khoá -> ERROR, KHÔNG lộ", ra.startswith("ERROR") and AKEY not in ra and CKEY not in ra, ra)
gia.tra("/v2/payment-requests/", {"code": "214", "desc": f"client {CID} api {AKEY}"})
ra = chay(p.call("payos_xem_link", {"id": "1"}, spec()))
check("lỗi body vọng lại khoá -> KHÔNG lộ", ra.startswith("ERROR") and AKEY not in ra and CID not in ra, ra)
gia.nem_loi("/v2/payment-requests/1/cancel", ConnectionError(f"proxy chặn header x-api-key={AKEY}"))
ra = chay(p.call("payos_huy_link", {"id": "1"}, spec()))
check("lỗi mạng -> ERROR, KHÔNG lộ api key", ra.startswith("ERROR") and AKEY not in ra, ra)
gia.go()

ra = chay(p.call("payos_xem_link", {"id": "1"}, {"secrets": {"client_id": CID, "api_key": AKEY}}))
check("thiếu checksum_key -> báo rõ", ra.startswith("ERROR") and "checksum_key" in ra, ra)
check("tool lạ -> lỗi", chay(p.call("payos_rut_tien", {}, spec())).startswith("ERROR"))
check.ket_thuc()
