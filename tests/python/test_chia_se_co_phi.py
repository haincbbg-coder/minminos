"""26.10.104: món CÓ PHÍ trên kệ - mã mua gắn vân tay máy người mua.

    python tests/run.py chia_se_co_phi

Máy bán và máy mua giả lập chung một tiến trình nên dùng chung khoá danh tính: "máy mua đúng" là
chính máy này. "Máy khác" được giả bằng một khoá Ed25519 sinh riêng trong test.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-phi-")
GUI = tempfile.mkdtemp(prefix="javis-phi-gui-")
NHAN = tempfile.mkdtemp(prefix="javis-phi-nhan-")
from fastapi.testclient import TestClient  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
import main  # noqa: E402
import danh_tinh  # noqa: E402
import ma_mua  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:300] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


for b in (GUI, NHAN):
    main._ensure_brain_scaffold(Path(b))
(Path(GUI) / "agents").mkdir(exist_ok=True)
(Path(GUI) / "agents" / "len-camp.md").write_text("---\nname: Lên camp\n---\nLên camp Facebook Ads.", encoding="utf-8")
(Path(GUI) / "agents" / "mien-phi.md").write_text("---\nname: Miễn phí\n---\nx", encoding="utf-8")

c = TestClient(main.app, base_url="http://localhost")
HOST = "minmin.ban-hang.vn"


async def _gia_host(h):
    return "" if h == HOST else "chặn"


async def _gia_tai(url, headers=None, tran=0):
    r = c.get(url[len(f"https://{HOST}"):], headers=dict(headers or {}, accept="application/json"))
    return r.status_code, r.content, ""


main._host_cong_khai, main._tai_https = _gia_host, _gia_tai

c.post("/ke-hang/them", data={"brain": GUI, "items": json.dumps({"agent": ["len-camp", "mien-phi"]})})
c.post("/ke-hang/cai-dat", data={"bat": "1"})
mon = {m["slug"]: m for m in c.get("/ke-hang").json()["mon"]}
mid, free = mon["len-camp"]["id"], mon["mien-phi"]["id"]
c.post("/ke-hang/sua", data={"id": mid, "co_phi": "1", "gia": "500.000đ", "lien_he": "Zalo 0900"})
pub = {m["id"]: m for m in c.get("/bs/ke", headers={"accept": "application/json"}).json()["mon"]}
check("trang kệ ghi có phí + giá + liên hệ", pub[mid]["co_phi"] and pub[mid]["gia"] == "500.000đ" and pub[mid]["lien_he"] == "Zalo 0900", pub[mid])
check("món miễn phí vẫn tải thẳng", c.get(f"/bs/ke/{free}/goi.zip").status_code == 200)
r = c.get(f"/bs/ke/{mid}/goi.zip")
check("món có phí: không mã là 402 can_ma", r.status_code == 402 and r.json()["ly_do"] == "can_ma", r.text)
check("món có phí: kênh cập nhật cũng chặn", c.get(f"/bs/td/{mid}/goi.zip").status_code == 402)
check("món có phí: dấu bản (không nội dung) vẫn hỏi được", c.get(f"/bs/td/{mid}").status_code == 200)

# ---------- máy mua chưa có mã ----------
x = c.post("/brains/import/xem", data={"to_brain": NHAN, "nguon": f"https://{HOST}/bs/ke/{mid}"}).json()
vt = danh_tinh.van_tay()
check("xem trước món có phí: hỏi mã + đưa vân tay máy mình", x.get("can_ma_mua") and x["van_tay_cua_toi"] == vt and x["gia"] == "500.000đ", x)

# ---------- cấp mã ----------
check("cấp mã sai vân tay bị từ chối", c.post("/ke-hang/ma-mua", data={"mon": mid, "mua": "abc"}).status_code == 400)
check("cấp mã cho món không có trên kệ bị từ chối", c.post("/ke-hang/ma-mua", data={"mon": "khongcothat123456789012345", "mua": vt}).status_code == 400)
cap = c.post("/ke-hang/ma-mua", data={"mon": mid, "mua": vt.lower().replace("-", ""), "kh": "Chị Lan"}).json()
ma = cap["ma"]
check("cấp mã được (vân tay viết thường, không gạch vẫn nhận)", cap.get("ok") and ma.startswith("MMB1.") and cap["mua"] == vt, cap)
check("chỉ máy bán đọc được mã của mình", ma_mua.doc_ma(ma)["kh"] == "Chị Lan")
check("sửa một ký tự là mã hỏng", ma_mua.doc_ma(ma[:-3] + ("A" if ma[-3] != "A" else "B") + ma[-2:]) is None)

x = c.post("/brains/import/xem", data={"to_brain": NHAN, "nguon": f"https://{HOST}/bs/ke/{mid}", "ma_mua": ma}).json()
check("dùng mã: xem trước được", x.get("ok") and x["xac_minh"]["xac_minh"] == "da_xac_minh", x)
check("máy mua nhớ mã", ma_mua.ma_cua_toi(HOST, mid) == ma)
check("sổ mã của máy mua quyền 600", (os.stat(ma_mua._so_mua()).st_mode & 0o777) == 0o600 or os.name == "nt")
ci = c.post("/brains/import/cai", data={"sha256": x["sha256"], "to_brain": NHAN}).json()
check("cài món có phí", ci.get("ok") and "agent:len-camp" in ci["imported"], ci)

# ---------- cập nhật tự dùng lại mã ----------
(Path(GUI) / "agents" / "len-camp.md").write_text("---\nname: Lên camp\n---\nLên camp bản 2.", encoding="utf-8")
kt = {i["slug"]: i for i in c.get("/brains/imported/kiem-tra", params={"brain": NHAN}).json()["items"]}
check("món có phí: thấy bản mới", kt["len-camp"]["trang_thai"] == "co_ban_moi", kt)
xu = c.post("/brains/import/xem", data={"to_brain": NHAN, "td": mid, "host_td": HOST}).json()
check("cập nhật món có phí không phải nhập lại mã", xu.get("ok") and xu["cap_nhat"]["agent:len-camp"]["co_ban_moi"], xu)

# ---------- chống dùng chui ----------
duong = f"/bs/ke/{mid}/goi.zip"
k2 = Ed25519PrivateKey.generate()
pub2 = base64.b64encode(k2.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
luc = str(int(time.time()))
hd_khac = {"X-MinMin-Ma-Mua": ma, "X-MinMin-Khoa": pub2, "X-MinMin-Luc": luc,
           "X-MinMin-Ky": base64.b64encode(k2.sign(ma_mua.thong_diep(duong, luc))).decode()}
r = c.get(duong, headers=hd_khac)
check("lộ mã sang máy khác: 402 sai_may", r.status_code == 402 and r.json()["ly_do"] == "sai_may", r.text)
hd = ma_mua.dau_yeu_cau(duong, ma)
check("chữ ký đúng: tải được", c.get(duong, headers=hd).status_code == 200)
check("chữ ký cho đường khác không dùng được ở đây", c.get(duong, headers=ma_mua.dau_yeu_cau(f"/bs/ke/{free}/goi.zip", ma)).json().get("ly_do") == "sai_may")
cu = dict(hd, **{"X-MinMin-Luc": str(int(time.time()) - 3600)})
check("yêu cầu cũ (phát lại) bị từ chối", c.get(duong, headers=cu).json().get("ly_do") in ("sai_gio", "sai_may"))
check("mã chỉ có khoá, không ký: bị từ chối", c.get(duong, headers={"X-MinMin-Ma-Mua": ma, "X-MinMin-Khoa": danh_tinh.cong_khai()}).status_code == 402)

khac_mon = c.post("/ke-hang/ma-mua", data={"mon": free, "mua": vt}).json()["ma"]
check("mã của món khác không mở được món này", c.get(duong, headers=ma_mua.dau_yeu_cau(duong, khac_mon)).json().get("ly_do") == "sai_mon")
het = c.post("/ke-hang/ma-mua", data={"mon": mid, "mua": vt, "het_han": "2020-01-01"}).json()["ma"]
check("mã quá hạn bị từ chối", c.get(duong, headers=ma_mua.dau_yeu_cau(duong, het)).json().get("ly_do") == "het_han")
tat_ca = c.post("/ke-hang/ma-mua", data={"mon": "*", "mua": vt}).json()["ma"]
check("mã mọi món mở được món có phí", c.get(duong, headers=ma_mua.dau_yeu_cau(duong, tat_ca)).status_code == 200)

# ---------- thu hồi ----------
ds = c.get("/ke-hang/ma-mua").json()["ma"]
so = next(x["so"] for x in ds if x["ma"] == ma)
check("người bán chép lại được mã đã cấp", any(x["ma"] == ma and x["kh"] == "Chị Lan" for x in ds))
c.post("/ke-hang/ma-mua/thu-hoi", data={"so": so})
check("thu hồi: mã chết, kể cả cập nhật", c.get(duong, headers=ma_mua.dau_yeu_cau(duong, ma)).json().get("ly_do") == "thu_hoi")
xu2 = c.post("/brains/import/xem", data={"to_brain": NHAN, "td": mid, "host_td": HOST}).json()
check("máy mua bị thu hồi thì được báo hỏi mã lại", xu2.get("can_ma_mua") and xu2.get("ly_do") == "thu_hoi", xu2)

c.post("/ke-hang/sua", data={"id": mid, "co_phi": "0"})
check("tắt có phí: tải thẳng lại được", c.get(duong).status_code == 200)
check("cấp mã KHÔNG công khai", not any("/ke-hang/ma-mua".startswith(p) for p in main._AUTH_PUBLIC_PREFIX))

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
