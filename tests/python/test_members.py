"""Thành viên được mời (26.10.77): đăng nhập email + mật khẩu, 2FA bắt buộc, quyền xem/sửa.

    python tests/run.py members
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import tempfile
from pathlib import Path

os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp(prefix="javis-mem-")
BD = tempfile.mkdtemp(prefix="javis-mem-brains-")
os.environ["BRAINS_DIR"] = BD
os.environ["JAVIS_REQUIRE_LOGIN"] = "1"
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402
import members  # noqa: E402
import totp  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them) + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


A = Path(BD) / "Cua-hang"
A.mkdir()
(A / "ghi-chu.md").write_text("xin chào brain", encoding="utf-8")
(A / "sub").mkdir()
(A / "sub" / "b.md").write_text("trong thư mục con", encoding="utf-8")
(A / "memory").mkdir()
(A / "memory" / "MEMORY.md").write_text("RIÊNG TƯ", encoding="utf-8")
(A / ".env").write_text("KEY=bimat", encoding="utf-8")
B = Path(BD) / "Brain-khac"
B.mkdir()
(B / "x.md").write_text("của brain khác", encoding="utf-8")
secret_out = Path(tempfile.mkdtemp()) / "ngoai.md"
secret_out.write_text("NGOÀI GỐC", encoding="utf-8")
try:
    os.symlink(secret_out, A / "link.md")
except OSError:
    pass

adm = TestClient(main.app, base_url="http://localhost")
r = adm.post("/auth/setup", data={"username": "admin", "password": "matkhau-admin-1"})
check("admin setup", r.status_code == 200)

r = adm.post("/members", data={"email": "Lan@Example.com", "password": "abc", "grants": "{}"})
check("mật khẩu ngắn bị từ chối", r.status_code == 400)
r = adm.post("/members", data={"email": "lan@example.com", "name": "Lan", "password": "matkhau-lan-1",
                               "grants": '{"Cua-hang":"view","Brain-khac":"bậy","../x":"edit"}'})
check("tạo thành viên", r.status_code == 200 and r.json()["member"]["grants"] == {"Cua-hang": "view"}, r.text)
r = adm.post("/members", data={"email": "lan@example.com", "password": "matkhau-lan-1"})
check("trùng email bị chặn", r.status_code == 400)
check("hash không lộ trong danh sách", "hash" not in adm.get("/members").text)

m = TestClient(main.app, base_url="http://localhost")
r = m.post("/auth/login", data={"username": "lan@example.com", "password": "sai-het"})
check("sai mật khẩu 401", r.status_code == 401)
r = m.post("/auth/login", data={"username": "lan@example.com", "password": "matkhau-lan-1"})
check("đăng nhập ok nhưng phải cài 2FA", r.status_code == 200 and r.json().get("needs_2fa_setup") is True, r.text)
st = m.get("/auth/status").json()
check("status role member, chưa full", st.get("role") == "member" and st.get("member_full") is False, st)

check("chưa 2FA thì không xem được file", m.get("/m/brains").status_code == 403)
check("admin endpoint bị chặn", m.get("/members").status_code == 403)
check("endpoint admin khác bị chặn", m.get("/sessions").status_code == 403)
check("tạo thành viên bị chặn", m.post("/members", data={"email": "x@y.zz", "password": "12345678"}).status_code == 403)
check("khách chưa đăng nhập bị 401", TestClient(main.app, base_url="http://localhost").get("/m/me").status_code == 401)

s = m.post("/m/2fa/start").json()
check("2FA start trả secret", bool(s.get("secret")) and "<svg" in s.get("qr_svg", ""))
r = m.post("/m/2fa/enable", data={"code": "000000"})
check("mã sai không bật", r.status_code == 400)
code = totp.ma_cua_buoc(s["secret"], totp.buoc_hien_tai())
r = m.post("/m/2fa/enable", data={"code": code})
check("bật 2FA ok + mã khôi phục", r.status_code == 200 and len(r.json()["recovery"]) >= 5, r.text)
rec = r.json()["recovery"][0]
check("giờ xem được brains", m.get("/m/brains").json()["brains"] == [{"name": "Cua-hang", "role": "view"}])

L = lambda p="": m.get("/m/files/list", params={"brain": "Cua-hang", "path": p})
names = [i["name"] for i in L().json()["items"]]
check("thấy file thường", "ghi-chu.md" in names and "sub" in names, names)
check("ẩn memory/.env/symlink ra ngoài", not ({"memory", ".env", "link.md"} & set(names)), names)
rd = lambda p, b="Cua-hang": m.get("/m/files/read", params={"brain": b, "path": p})
check("đọc file", rd("ghi-chu.md").json()["text"] == "xin chào brain")
check("đọc file con", rd("sub/b.md").status_code == 200)
check("không đọc memory", rd("memory/MEMORY.md").status_code == 404)
check("không đọc .env", rd(".env").status_code == 404)
check("không đọc symlink ra ngoài", rd("link.md").status_code == 404)
check("không thoát bằng ..", rd("../Brain-khac/x.md").status_code == 404)
check("không thoát bằng ..%2f", m.get("/m/files/read?brain=Cua-hang&path=sub/../../Brain-khac/x.md").status_code == 404)
check("brain không được cấp", rd("x.md", "Brain-khac").status_code == 403)
check("brain path tuyệt đối bị chặn", rd("x.md", str(B)).status_code == 403)
check("brain traversal bị chặn", rd("x.md", "../Brain-khac").status_code == 403)
w = lambda p, t="mới": m.post("/m/files/write", data={"brain": "Cua-hang", "path": p, "text": t})
check("quyền view không ghi được", w("ghi-chu.md").status_code == 403)
check("tìm kiếm", any(h["path"] == "ghi-chu.md" for h in m.get("/m/search", params={"brain": "Cua-hang", "q": "xin chào"}).json()["hits"]))
check("file gốc nguyên vẹn", (A / "ghi-chu.md").read_text(encoding="utf-8") == "xin chào brain")

adm.post("/members/update", data={"email": "lan@example.com", "grants": '{"Cua-hang":"edit"}'})
check("edit ghi được", w("ghi-chu.md", "đã sửa").status_code == 200 and (A / "ghi-chu.md").read_text(encoding="utf-8") == "đã sửa")
check("edit tạo file mới", w("sub/moi.md").status_code == 200 and (A / "sub" / "moi.md").exists())
check("edit không ghi .py", w("hack.py").status_code == 400)
check("edit không ghi ra ngoài", w("../hack.md").status_code == 400 and not (Path(BD) / "hack.md").exists())
check("edit không ghi .env", w(".env").status_code == 400)
check("edit không ghi memory", w("memory/x.md").status_code == 400)
check("edit không ghi đè symlink ra ngoài", w("link.md").status_code == 400 and secret_out.read_text(encoding="utf-8") == "NGOÀI GỐC")
check("edit brain khác bị chặn", m.post("/m/files/write", data={"brain": "Brain-khac", "path": "x.md", "text": "z"}).status_code == 403)
check("có nhật ký", (Path(os.environ["JAVIS_STATE_DIR"]) / "member_audit.jsonl").exists())

m.post("/m/logout")
check("sau logout hết phiên", m.get("/m/me").status_code == 401)
m2 = TestClient(main.app, base_url="http://localhost")
r = m2.post("/auth/login", data={"username": "lan@example.com", "password": "matkhau-lan-1"})
check("đã bật 2FA thì đòi mã", r.status_code == 401 and r.json().get("needs_2fa"))
r = m2.post("/auth/login", data={"username": "lan@example.com", "password": "matkhau-lan-1", "code": "123456"})
check("mã sai bị từ chối", r.status_code == 401)
r = m2.post("/auth/login", data={"username": "lan@example.com", "password": "matkhau-lan-1", "code": rec})
check("mã khôi phục vào được", r.status_code == 200 and m2.get("/m/me").json()["full"] is True, r.text)
m3 = TestClient(main.app, base_url="http://localhost")
r = m3.post("/auth/login", data={"username": "lan@example.com", "password": "matkhau-lan-1", "code": rec})
check("mã khôi phục chỉ dùng một lần", r.status_code == 401)

check("phiên thành viên không phải phiên admin", not main.cfgmod.valid_session(m2.cookies.get("javis_session", "")))

adm.post("/members/update", data={"email": "lan@example.com", "disabled": "1"})
check("khóa thì phiên cũ mất", m2.get("/m/me").status_code == 401)
r = TestClient(main.app, base_url="http://localhost").post("/auth/login", data={"username": "lan@example.com", "password": "matkhau-lan-1", "code": "1"})
check("khóa thì không đăng nhập được", r.status_code == 401)
adm.post("/members/update", data={"email": "lan@example.com", "disabled": "0", "reset_2fa": "1"})
r = TestClient(main.app, base_url="http://localhost").post("/auth/login", data={"username": "lan@example.com", "password": "matkhau-lan-1"})
check("reset 2FA thì phải cài lại", r.json().get("needs_2fa_setup") is True)
check("xóa thành viên", adm.post("/members/delete", data={"email": "lan@example.com"}).json()["ok"] and not members.lay("lan@example.com"))

print("\n%d lỗi" % len(fails))
raise SystemExit(1 if fails else 0)
