"""Bot gửi ảnh/video/tài liệu cho khách từ thư viện chủ duyệt.   python tests/run.py bot_gui_tep"""
import asyncio, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
import _paths  # noqa
import chatbot_thu_vien as tv
import zalo_personal_channel as zc

ok = True
def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)

root = Path(tempfile.mkdtemp())
check("thư viện trống thì không thêm gì vào prompt", tv.khoi_prompt(root) == "")
t1, e1 = tv.luu(root, "Bảng giá.pdf", b"%PDF-1.4 abc")
t2, e2 = tv.luu(root, "ao-dai.JPG", b"\xff\xd8\xff")
t3, e3 = tv.luu(root, "../../etc/passwd.pdf", b"x")
check("lưu được và chống đường dẫn lạ", t1 == "Bảng giá.pdf" and t2 and t3 == "passwd.pdf" and not e1, (t1, t3))
check("đuôi nguy hiểm bị từ chối", tv.luu(root, "virus.exe", b"x")[1] and tv.luu(root, "a.html", b"x")[1])
check("file rỗng và quá lớn bị từ chối", tv.luu(root, "a.pdf", b"")[1] and tv.luu(root, "b.pdf", b"x" * (tv.MAX_BYTES + 1))[1])
t4, _ = tv.luu(root, "Bảng giá.pdf", b"v2")
check("trùng tên thì không ghi đè", t4 == "Bảng giá (2).pdf" and (root / "gui-khach" / "Bảng giá.pdf").read_bytes() == b"%PDF-1.4 abc")
kp = tv.khoi_prompt(root)
check("prompt liệt kê file và cách xin gửi", "Bảng giá.pdf" in kp and "GUI_FILE" in kp)

txt, files, loi = tv.tach_lenh("Dạ em gửi anh ạ\n[GUI_FILE: bảng giá.pdf]\n[GUI_FILE: ao-dai.jpg]", root)
check("gỡ dòng lệnh khỏi chữ khách đọc", "GUI_FILE" not in txt and txt == "Dạ em gửi anh ạ", txt)
check("tên khớp không phân biệt hoa thường, file mang cờ thư viện",
      len(files) == 2 and all(f["thu_vien"] for f in files) and files[1]["loai"] == "anh", files)
txt, files, loi = tv.tach_lenh("ok [GUI_FILE: ../../etc/passwd] [GUI_FILE: khong-co.pdf] [GUI_FILE: virus.exe]", root)
check("tên ngoài thư viện không bao giờ thành file", files == [] and len(loi) == 3, (files, loi))
(root / "bi-mat.pdf").write_bytes(b"secret")
check("file nằm ngoài gui-khach không gửi được", tv.tach_lenh("[GUI_FILE: ../bi-mat.pdf]", root)[1] == [])
for i in range(6):
    tv.luu(root, f"a{i}.png", b"\x89PNG")
check("mỗi lượt tối đa 4 file", len(tv.tach_lenh(" ".join(f"[GUI_FILE: a{i}.png]" for i in range(6)), root)[1]) == tv.MAX_MOI_LUOT)
check("xoá được, xoá lạ thì không", tv.xoa(root, "a0.png") and not tv.xoa(root, "../bi-mat.pdf"))

# tiếng vọng file của bot không làm bot tự câm
zc.ghi_tep_da_gui("c1", "t1")
check("tiếng vọng ảnh của bot được nhận ra", zc._la_tieng_vong_tep("c1", "t1", "image"))
check("tiếng vọng chỉ tính một lần", not zc._la_tieng_vong_tep("c1", "t1", "image"))
check("tin chữ không bao giờ là tiếng vọng file", not zc._la_tieng_vong_tep("c1", "t1", "text"))

# Zalo cá nhân: gọi đúng lệnh CLI cho ảnh và cho file
import channels.zalo_personal as zp
goi = []
class P:
    returncode = 0
    async def communicate(self): return b"", b""
async def fake(*argv, **kw):
    goi.append(list(argv)); return P()
zp.asyncio.create_subprocess_exec = fake
zc.ket_noi_theo_id = lambda cid: {"id": cid, "command": "npx", "args": ["-y", "zalo-agent-cli@1.6.2", "mcp", "start"], "env": {}}
asyncio.run(zp.gui_tep("c1", "555", "/x/a.png", "private", "anh"))
asyncio.run(zp.gui_tep("c1", "-777", "/x/b.pdf", "group", "tep"))
check("ảnh đi lệnh send-image, chat riêng", "send-image" in goi[0] and goi[0][goi[0].index("-t") + 1] == "0", goi[0])
check("tài liệu đi lệnh send-file, chat nhóm", "send-file" in goi[1] and goi[1][goi[1].index("-t") + 1] == "1", goi[1])
sys.exit(0 if ok else 1)
