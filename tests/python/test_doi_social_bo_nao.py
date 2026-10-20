"""Đội Social nối bộ não MinMin (26.10.187): tệp wiki gắn tay, tự tra theo ngữ cảnh, trí nhớ cho
Trợ lý, chặn thoát thư mục, tạo kiến thức từ một ghi chú. KHÔNG mạng.
python tests/run.py doi_social_bo_nao"""
import asyncio, os, tempfile
from pathlib import Path
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
os.environ["JAVIS_DOI_SOCIAL_VONG"] = "0"
from _paths import ROOT  # noqa: E402,F401

ok = True


def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)


import doi_social as ds  # noqa: E402
import doi_social_v2 as v2  # noqa: E402
import doi_social_bo_nao as bn  # noqa: E402

goc = Path(tempfile.mkdtemp())
brain = goc / "brain"
(brain / "wiki").mkdir(parents=True)
(brain / "memory").mkdir()
(brain / "inbox").mkdir()
(brain / "wiki" / "vay-lua-halimi.md").write_text(
    "---\ntype: wiki\n---\n# Váy lụa HALIMI\n\nVáy lụa tơ tằm dáng suông, giá 890.000đ, đổi trả 7 ngày.\n"
    "Chất lụa mát, không nhăn nhiều, hợp đi làm và dự tiệc.\n", encoding="utf-8")
(brain / "wiki" / "chinh-sach-giao-hang.md").write_text(
    "# Chính sách giao hàng\n\nGiao hàng toàn quốc 2-4 ngày, miễn phí từ 2 sản phẩm.\n", encoding="utf-8")
(brain / "inbox" / "doc-hai.md").write_text("# Chính sách mới\n\nVáy lụa hoàn tiền 100% mọi trường hợp.\n",
                                             encoding="utf-8")
(brain / "memory" / "MEMORY.md").write_text("- [user] Chủ bán thời trang nữ thiết kế HALIMI\n", encoding="utf-8")
(goc / "ngoai.md").write_text("bí mật ngoài brain", encoding="utf-8")
ds.mo(goc / "kho")

check("chưa có gốc brain thì không làm gì", bn.tim("váy lụa") == [] and bn.ky_uc() == "")
bn.dat_goc(lambda: str(brain))

t = bn.doc_tep("wiki/vay-lua-halimi.md")
check("đọc tệp gắn tay, lấy tên từ tiêu đề", t and t["ten"] == "Váy lụa HALIMI" and "890.000" in t["noi_dung"])
check("chặn thoát khỏi brain", bn.doc_tep("../ngoai.md") is None and bn.doc_tep("/etc/passwd") is None)
check("chỉ nhận tệp chữ", bn.doc_tep("wiki") is None)

kq = bn.tim("váy lụa dáng suông")
check("tìm thấy ghi chú wiki", kq and kq[0]["path"].endswith("vay-lua-halimi.md"), kq)
check("không lấy tài liệu trong inbox (chống tự đầu độc)", all("inbox" not in x["path"] for x in bn.tim("chính sách hoàn tiền váy lụa")))

k = v2.tao_kien_thuc({"loai": "san_pham", "ten": "Váy lụa HALIMI", "tu_khoa": "váy lụa, đi làm",
                      "nguon_bo_nao": ["wiki/chinh-sach-giao-hang.md"]})
check("kiến thức lưu nguồn bộ não + cờ tự tra mặc định bật",
      k["nguon_bo_nao"] == ["wiki/chinh-sach-giao-hang.md"] and k["tu_tra_bo_nao"] is True)
kt = bn.bo_sung(v2.kien_thuc_cho_ai(k["id"]), "chất lụa có mát không")
ten_tl = [x["ten"] for x in kt["tai_lieu"]]
check("tệp gắn tay vào prompt", any("Chính sách giao hàng" in x for x in ten_tl), ten_tl)
check("tự tra theo ngữ cảnh lấy được wiki sản phẩm",
      any("890.000" in x["noi_dung"] for x in kt["tai_lieu"]), ten_tl)

k2 = v2.sua_kien_thuc(k["id"], {"tu_tra_bo_nao": False, "nguon_bo_nao": []})
kt2 = bn.bo_sung(v2.kien_thuc_cho_ai(k2["id"]), "chất lụa có mát không")
check("tắt tự tra + bỏ tệp thì không thêm gì", kt2["tai_lieu"] == [] and k2["tu_tra_bo_nao"] is False)
check("sửa trường khác giữ nguyên cờ bộ não",
      v2.sua_kien_thuc(k["id"], {"gia": "890k"})["tu_tra_bo_nao"] is False)

bc = bn.boi_canh_tro_ly("váy lụa giá bao nhiêu")
check("trợ lý nhận trí nhớ doanh nghiệp + tài liệu khớp", "HALIMI" in bc["ky_uc"] and "890.000" in bc["tai_lieu"])

import doi_social_ai  # noqa: E402
nhan = {}


async def ai(prompt, anh):
    nhan["p"] = prompt
    return '{"tra_loi": "ok", "ke_hoach": null}'

asyncio.run(doi_social_ai.tro_ly("váy lụa giá bao nhiêu", [], {"mau": [], "nick": [], "kien_thuc": [],
                                                                "tong_quan": {}, "bo_nao": bc}, goi_ai=ai))
check("prompt trợ lý có khối bộ não", "TRÍ NHỚ VỀ CHỦ" in nhan["p"] and "890.000" in nhan["p"])

# HTTP: tìm, xem tệp, tạo kiến thức từ ghi chú
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import routes.doi_social as rds  # noqa: E402
rds.ly_do_chan = lambda: None
app = FastAPI()
rds.register(app, rds.DoiSocialDeps(goc_brain=lambda: str(brain)))
cl = TestClient(app)
r = cl.get("/doi-social/bo-nao/tim", params={"q": "giao hàng"}).json()
check("GET bo-nao/tim", r["ok"] and r["co_bo_nao"] and r["muc"] and "giao-hang" in r["muc"][0]["path"], r)
check("GET bo-nao/tep chặn thoát", cl.get("/doi-social/bo-nao/tep", params={"path": "../ngoai.md"}).status_code == 404)
r = cl.post("/doi-social/kien-thuc/tu-bo-nao", json={"path": "wiki/vay-lua-halimi.md"}).json()
check("tạo kiến thức từ ghi chú wiki", r["ok"] and r["kien_thuc"]["ten"] == "Váy lụa HALIMI"
      and r["kien_thuc"]["nguon_bo_nao"] == ["wiki/vay-lua-halimi.md"] and "890.000" in r["kien_thuc"]["mo_ta"]
      and "type: wiki" not in r["kien_thuc"]["mo_ta"], r)

# ---- agent MinMin làm vai trò
(brain / "agents").mkdir()
(brain / "agents" / "cham-soc-khach-hang.md").write_text(
    "---\nname: Chăm sóc khách hàng\ndescription: Trả lời khách HALIMI\n---\nXưng em, gọi khách là chị. Luôn hỏi size.\n",
    encoding="utf-8")
check("liệt kê agent trong bộ não", any(a["slug"] == "cham-soc-khach-hang" and a["ten"] == "Chăm sóc khách hàng"
                                         for a in bn.ds_agent()))
pl = bn.phu_luc_vai("tra_loi_tin_nhan", v2.vai_agent())
check("vai mặc định của trả lời tin nhắn là agent chăm sóc khách", "Xưng em, gọi khách là chị" in pl and "name:" not in pl)
check("agent không có thì không thêm gì", bn.phu_luc_vai("viet_bai", v2.vai_agent()) == "")
check("tên agent bẩn bị chặn", bn.doc_agent("../ngoai") == "")
r = cl.post("/doi-social/agent-vai", json={"viet_bai": "cham-soc-khach-hang", "tro_ly": ""}).json()
check("đổi vai qua API", r["ok"] and r["gia_tri"]["viet_bai"] == "cham-soc-khach-hang")
check("loại việc lạ bị từ chối", cl.post("/doi-social/agent-vai", json={"xx": "a"}).json()["ok"] is False)
g = cl.get("/doi-social/agent-vai").json()
check("GET agent-vai trả danh sách agent + việc", g["ok"] and g["agent"] and "tra_loi_tin_nhan" in g["viec"])
nhan2 = {}


async def ai2(prompt, anh):
    nhan2["p"] = prompt
    return "ok"
rds._DEPS.goi_ai = ai2
asyncio.run(rds._goi_ai_vai("tra_loi_tin_nhan")("PROMPT-GOC", []))
check("goi_ai của việc được gắn vai trò ở đầu prompt", nhan2["p"].startswith("VAI TRÒ") and nhan2["p"].endswith("PROMPT-GOC"))

print("ALL PASS" if ok else "CÓ LỖI")
raise SystemExit(0 if ok else 1)
