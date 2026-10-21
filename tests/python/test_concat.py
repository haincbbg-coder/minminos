# -*- coding: utf-8 -*-
"""Concat (26.10.196): MinMin điều khiển trình dựng video Concat ở máy nhà qua cầu nối. Chạy tay:

    python tests/run.py concat

Phần đầu là test AN TOÀN, vì /concat/may/ là tiền tố mới được miễn cổng đăng nhập (cầu nối ở nhà
không có cookie): chỉ GET/POST dưới tiền tố đó lọt hàng rào, mỗi endpoint tự kiểm token, sai nhiều
lần bị khoá, tệp chỉ gửi xuống từ trong bộ não. Sau đó: vòng đời việc, plugin, bộ cầu nối, và một
lượt CHẠY THẬT cầu nối (apps/concat/cau/concat_cau.py) với một Concat MCP giả qua HTTP thật.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import base64
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import time
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-concat-")
os.environ["JAVIS_STATE_DIR"] = _STATE
_BRAINS = tempfile.mkdtemp(prefix="javis-concat-brains-")
os.environ.setdefault("BRAINS_DIR", _BRAINS)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastapi.testclient import TestClient   # noqa: E402
import main                                 # noqa: E402
import concat_cau                           # noqa: E402
import giay_phep                            # noqa: E402
import routes.concat as rc                  # noqa: E402
import routes.ket_noi_ngoai as knn          # noqa: E402

_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        _fails.append(name)


cl = TestClient(main.app, base_url="http://localhost")
_da_mo_goc, _dong_y_goc = giay_phep.da_mo, knn.da_dong_y
giay_phep.da_mo = lambda app_id: True
knn.da_dong_y = lambda phan: True

# ============ 1. Cổng đăng nhập BẬT: chỉ GET/POST dưới /concat/may/ lọt ============
main.cfgmod.gate_active = lambda: True
r = cl.post("/concat/may/nhip", json={})
check("bật cổng, POST /concat/may/nhip không token -> 401 của CHÍNH endpoint",
      r.status_code == 401 and r.json().get("concat") and not r.json().get("auth_required"), r.text)
r = cl.get("/concat/may/viec?cho=0", headers={"x-minmin-may": "mmc_sai"})
check("bật cổng, token sai -> 401", r.status_code == 401, r.status_code)
for m, d in (("GET", "/apps/concat/"), ("GET", "/apps/concat/api/trang-thai"), ("POST", "/apps/concat/api/ma-ghep"),
             ("DELETE", "/apps/concat/api/may/c12345678"), ("DELETE", "/concat/may/c12345678"),
             ("PUT", "/concat/may/nhip"), ("GET", "/concat/mayX"), ("GET", "/agents")):
    rr = cl.request(m, d)
    check(f"bật cổng, {m} {d} vẫn cần đăng nhập (401 của hàng rào)",
          rr.status_code == 401 and rr.json().get("auth_required") is True, (rr.status_code, rr.text[:80]))
src = (ROOT / "server" / "main.py").read_text(encoding="utf-8")
check("main.py miễn đăng nhập chỉ GET/POST của tiền tố cầu nối",
      '_CONCAT_MAY = ("/concat/may/", ("GET", "POST"))' in src
      and "path.startswith(_CONCAT_MAY[0]) and request.method in _CONCAT_MAY[1]" in src)
main.cfgmod.gate_active = lambda: False

# ============ 2. Ghép máy ============
r = cl.post("/concat/may/ghep", json={"ma": "000000", "ten": "x"})
check("mã sai -> 400", r.status_code == 400)
rc._SAI.clear()
ma = cl.post("/apps/concat/api/ma-ghep").json()["ma"]
check("mã ghép 6 số", len(ma) == 6 and ma.isdigit())
g = cl.post("/concat/may/ghep", json={"ma": ma, "ten": "PC nhà", "phien_ban": "26.10.199"}).json()
TOKEN = g.get("token", "")
H = {"x-minmin-may": TOKEN}
check("ghép xong nhận token mmc_", g.get("ok") and TOKEN.startswith("mmc_"), g)
check("mã dùng một lần", cl.post("/concat/may/ghep", json={"ma": ma}).status_code == 400)
rc._SAI.clear()
with concat_cau._db() as c:
    bam = c.execute("SELECT token_bam FROM may").fetchone()[0]
check("token chỉ lưu dạng băm", TOKEN not in bam and len(bam) == 64)

# ============ 3. Nhịp + trạng thái ============
r = cl.post("/concat/may/nhip", headers=H, json={
    "concat_ok": True, "concat": {"name": "concat", "version": "0.2.8"},
    "cong_cu": [{"name": "clip_add", "description": "Thêm clip", "inputSchema": {"type": "object"}}],
    "thu_muc_lam_viec": r"C:\Users\x\Videos\MinMin Concat"})
check("nhịp OK", r.status_code == 200, r.text)
st = cl.get("/apps/concat/api/trang-thai").json()
check("trạng thái: máy online, Concat sẵn sàng, đếm công cụ, không lộ token",
      st["online"] and st["concat_ok"] and st["may"][0]["so_cong_cu"] == 1
      and "token_bam" not in json.dumps(st), st)

# ============ 4. Vòng đời việc qua HTTP ============
v = concat_cau.tao_viec(cong_cu="clip_add", tham_so={"path": "/p"}, cho_giay=60)
j = cl.get("/concat/may/viec?cho=0", headers=H).json()["viec"]
check("cầu nối nhận việc", j and j["id"] == v["id"] and j["cong_cu"] == "clip_add" and j["tham_so"] == {"path": "/p"}, j)
check("không còn việc thứ hai", cl.get("/concat/may/viec?cho=0", headers=H).json()["viec"] is None)
r = cl.post(f"/concat/may/ket-qua/{v['id']}", headers=H,
            json={"ok": True, "ket_qua": {"content": [{"type": "text", "text": "đã thêm"}]}})
check("gửi kết quả", r.status_code == 200, r.text)
check("việc xong", concat_cau.lay_viec(v["id"])["trang_thai"] == "xong")
check("gửi lại kết quả cùng việc -> 403",
      cl.post(f"/concat/may/ket-qua/{v['id']}", headers=H, json={"ok": True}).status_code == 403)

# long-poll được đánh thức khi có việc mới
t0 = time.time()
threading.Timer(0.6, lambda: concat_cau.tao_viec(cong_cu="concat_version")).start()
j = cl.get("/concat/may/viec?cho=5", headers=H).json()["viec"]
check("long-poll trả việc mới ngay khi có (không đợi hết 5 giây)",
      j and j["cong_cu"] == "concat_version" and time.time() - t0 < 4, time.time() - t0)
cl.post(f"/concat/may/ket-qua/{j['id']}", headers=H, json={"ok": False, "loi": "thử lỗi"})
check("việc lỗi giữ lời báo lỗi", concat_cau.lay_viec(j["id"])["loi"] == "thử lỗi")

# việc treo
v2 = concat_cau.tao_viec(cong_cu="export_wait", cho_giay=10)
cl.get("/concat/may/viec?cho=0", headers=H)
with concat_cau._db() as c:
    c.execute("UPDATE viec SET nhan_luc=? WHERE id=?", (time.time() - 1000, v2["id"]))
    concat_cau._don_viec_treo(c)
check("việc chạy quá hạn -> lỗi 'cầu nối im lặng'", "im lặng" in concat_cau.lay_viec(v2["id"])["loi"])

# ============ 5. Tệp: chỉ trong bộ não ============
brain = Path(_BRAINS) / "Brain Default"
(brain / "attachments").mkdir(parents=True, exist_ok=True)
(brain / "attachments" / "clip.mp4").write_bytes(b"VIDEO" * 100)
ngoai = Path(tempfile.mkdtemp()) / "bi-mat.txt"
ngoai.write_text("x")
ts, tep = concat_cau.gom_tep({"files": ["minmin:attachments/clip.mp4", "minmin:attachments/clip.mp4"]},
                             lambda rel: str(brain / rel))
check("gom tệp bộ não thành minmin-tep:<số>, trùng thì một số",
      ts == {"files": ["minmin-tep:0", "minmin-tep:0"]} and len(tep) == 1 and tep[0]["ten"] == "clip.mp4", (ts, tep))
try:
    concat_cau.gom_tep({"f": "minmin:" + str(ngoai)})
    check("tệp ngoài bộ não bị từ chối", False)
except ValueError:
    check("tệp ngoài bộ não bị từ chối", True)
try:
    concat_cau.gom_tep({"f": "minmin:../../etc/passwd"}, lambda rel: str(brain / rel))
    check("đường thoát ra ngoài bộ não bị từ chối", False)
except ValueError:
    check("đường thoát ra ngoài bộ não bị từ chối", True)
v3 = concat_cau.tao_viec(cong_cu="media_import", tham_so=ts, tep=tep)
j = cl.get("/concat/may/viec?cho=0", headers=H).json()["viec"]
check("việc gửi cầu nối không lộ đường dẫn trên VPS", j["tep"] == [{"ten": "clip.mp4", "co": 500}], j["tep"])
r = cl.get(f"/concat/may/tep/{v3['id']}/0", headers=H)
check("cầu nối tải được tệp của việc", r.status_code == 200 and r.content == b"VIDEO" * 100)
check("số tệp ngoài danh sách -> 404", cl.get(f"/concat/may/tep/{v3['id']}/5", headers=H).status_code == 404)
cl.post(f"/concat/may/ket-qua/{v3['id']}", headers=H, json={"ok": True, "ket_qua": {}})

# tải lên (lay_tep)
v4 = concat_cau.tao_viec(loai="lay_tep", duong_dan=r"C:\Users\x\Videos\out.mp4", tham_so={"_brain": str(brain)})
j = cl.get("/concat/may/viec?cho=0", headers=H).json()["viec"]
r = cl.post(f"/concat/may/tai-len/{v4['id']}?ten=..%2F..%2Fout.mp4",
            headers={**H, "content-type": "application/octet-stream"}, content=b"MP4DATA")
check("tải lên lưu vào attachments/concat của bộ não, tên tệp bị làm sạch",
      r.status_code == 200 and r.json()["duong_dan"] == "attachments/concat/out.mp4"
      and (brain / "attachments" / "concat" / "out.mp4").read_bytes() == b"MP4DATA", r.text)
check("tải lên cho việc không chờ tệp -> 403",
      cl.post(f"/concat/may/tai-len/{v3['id']}?ten=a.mp4", headers=H, content=b"x").status_code == 403)
cl.post(f"/concat/may/ket-qua/{v4['id']}", headers=H, json={"ok": True, "ket_qua": {"tep": "attachments/concat/out.mp4"}})

# ============ 6. Chống dò + khoá app ============
for _ in range(20):
    cl.get("/concat/may/viec?cho=0", headers={"x-minmin-may": "mmc_do"})
check("sai token 20 lần -> 429", cl.get("/concat/may/viec?cho=0", headers=H).status_code == 429)
rc._SAI.clear()
giay_phep.da_mo = lambda app_id: False
check("app chưa mở khoá thì cầu nối bị chặn 403", cl.get("/concat/may/viec?cho=0", headers=H).status_code == 403)
check("app chưa mở khoá thì trang hiện lời khoá", cl.get("/apps/concat/").status_code == 403)
giay_phep.da_mo = lambda app_id: True
check("Concat có trong Kết nối ngoài", any(u["id"] == "concat" and u["duong_dan"] == "/apps/concat/"
                                           for u in giay_phep.UNG_DUNG))
z = cl.get("/apps/concat/api/bo-cai.zip")
check("tải bộ cầu nối (có concat_cau.py, bat; không có cau-noi.json)",
      z.status_code == 200 and b"concat_cau.py" in z.content and b"chay.bat" in z.content
      and b"cau-noi.json" not in z.content)
check("trang quản lý mở được", cl.get("/apps/concat/").status_code == 200
      and cl.get("/apps/concat/app.js").status_code == 200)

# ============ 7. Plugin ============
import plugins_host  # noqa: E402
tools, route = plugins_host.plugin_tools("full", str(brain))
ten = {t["name"] for t in tools}
check("plugin concat đưa đủ 5 tool", {"concat_trang_thai", "concat_cong_cu", "concat_goi", "concat_ket_qua",
                                      "concat_lay_tep"} <= ten, sorted(x for x in ten if "concat" in x))
_, route_s = plugins_host.plugin_tools("suggest", str(brain))
check("mức quyền: tool đọc readonly, tool sửa/lấy tệp cần safe",
      route["concat_trang_thai"]["required_mode"] == "readonly" and route["concat_ket_qua"]["required_mode"] == "readonly"
      and route["concat_goi"]["required_mode"] == "safe" and route["concat_lay_tep"]["required_mode"] == "safe")
out = asyncio.run(route_s["concat_goi"]["call"]({"cong_cu": "concat_version"}))
check("chế độ suggest chặn concat_goi", out.startswith("ERROR") and "mức quyền" in out, out)


def goi_tool(ten_tool, args):
    return asyncio.run(route[ten_tool]["call"](args))


# ============ 8. CHẠY THẬT cầu nối với Concat MCP giả qua HTTP thật ============
import uvicorn  # noqa: E402

s = socket.socket()
s.bind(("127.0.0.1", 0))
PORT = s.getsockname()[1]
s.close()
srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=PORT, log_level="warning"))
th = threading.Thread(target=srv.run, daemon=True)
th.start()
for _ in range(100):
    if srv.started:
        break
    time.sleep(0.1)

import importlib.util  # noqa: E402   cùng tên tệp với kho server, nên nạp theo đường riêng
spec = importlib.util.spec_from_file_location("concat_cau_nha", ROOT / "apps" / "concat" / "cau" / "concat_cau.py")
cau_nha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cau_nha)
td = Path(tempfile.mkdtemp(prefix="concat-cau-"))
cau_nha.CAU_HINH = td / "cau-noi.json"
cau_nha.NHAT_KY = td / "cau-noi.log"
gia = td / "concat"
gia.write_text(f"#!/bin/sh\nexec {sys.executable} {ROOT / 'tests' / 'python' / '_gia_concat_mcp.py'}\n")
gia.chmod(gia.stat().st_mode | stat.S_IEXEC)
nha = td / "home"
nha.mkdir()
cau_nha.thu_muc_nha = lambda: nha
check("cầu nối và VERSION cùng số phiên bản",
      cau_nha.PHIEN_BAN == (ROOT / "VERSION").read_text().strip(), cau_nha.PHIEN_BAN)

ma2 = cl.post("/apps/concat/api/ma-ghep").json()["ma"]
check("cầu nối ghép qua HTTP thật", cau_nha.ghep(f"http://127.0.0.1:{PORT}", ma2) == 0)
cfg = cau_nha.doc_cau_hinh()
cfg["concat_exe"] = str(gia)
cau_nha.ghi_cau_hinh(cfg)
cau_th = threading.Thread(target=cau_nha.chay, daemon=True)
cau_th.start()
for _ in range(100):
    m = concat_cau.lay_may(cfg["may_id"])
    if m and m["concat_ok"] and m["cong_cu"]:
        break
    time.sleep(0.1)
check("cầu nối báo nhịp: Concat sẵn sàng, đủ 4 công cụ giả",
      m and m["concat_ok"] and len(m["cong_cu"]) == 4 and m["concat"].get("version") == "0.2.8-gia", m)
with concat_cau._db() as c:   # máy ghép ở mục 2 không chạy thật: đẩy nó ra khỏi vai máy chính
    c.execute("DELETE FROM may WHERE id != ?", (cfg["may_id"],))

out = goi_tool("concat_trang_thai", {})
check("tool concat_trang_thai thấy máy online và tên công cụ", "online" in out and "media_import" in out, out)
out = goi_tool("concat_cong_cu", {"ten": "media_import"})
check("tool concat_cong_cu trả schema", '"inputSchema"' in out and "files" in out, out)
out = goi_tool("concat_goi", {"cong_cu": "concat_version"})
check("tool concat_goi -> Concat trả lời qua cầu nối", "0.2.8-gia" in out, out)
out = goi_tool("concat_goi", {"cong_cu": "media_import",
                              "tham_so": {"path": "/du-an", "files": ["minmin:attachments/clip.mp4"]}})
d = json.loads(out)
check("tệp bộ não được tải xuống máy nhà và thay bằng đường thật",
      d["tep_co_that"] and d["nhan"]["files"][0].startswith(str(nha)) and d["nhan"]["files"][0].endswith("clip.mp4"), out)
out = goi_tool("concat_goi", {"cong_cu": "preview_frame", "tham_so": {"path": "/du-an", "time": 1}})
anh = list((brain / "attachments" / "concat").glob("khung-*.png"))
check("ảnh khung hình lưu vào bộ não và nhúng markdown",
      "![khung hình](attachments/concat/khung-" in out and anh and anh[0].read_bytes().startswith(b"\x89PNG"), out)
out = goi_tool("concat_goi", {"cong_cu": "loi_thu"})
check("Concat báo lỗi -> tool trả ERROR", out.startswith("ERROR") and "hỏng" in out, out)
(nha / "Videos").mkdir(exist_ok=True)
(nha / "Videos" / "xuat.mp4").write_bytes(b"MP4" * 50)
out = goi_tool("concat_lay_tep", {"duong_dan": str(nha / "Videos" / "xuat.mp4")})
check("concat_lay_tep đưa video về bộ não", "attachments/concat/xuat.mp4" in out
      and (brain / "attachments" / "concat" / "xuat.mp4").read_bytes() == b"MP4" * 50, out)
out = goi_tool("concat_lay_tep", {"duong_dan": "/etc/hostname"})
check("concat_lay_tep từ chối tệp ngoài thư mục người dùng máy nhà",
      out.startswith("ERROR") and "thư mục người dùng" in out, out)
out = goi_tool("concat_goi", {"cong_cu": "media_import", "tham_so": {"files": ["minmin:" + str(ngoai)]}})
check("concat_goi từ chối tệp ngoài bộ não", out.startswith("ERROR"), out)

srv.should_exit = True

# ============ 9. Bộ cầu nối: .bat ASCII + CRLF, không gạch dài ============
CAU = ROOT / "apps" / "concat" / "cau"
for b in ("chay.bat", "ghep-may.bat"):
    raw = (CAU / b).read_bytes()
    check(f"{b} chỉ ASCII", all(x < 128 for x in raw))
    check(f"{b} xuống dòng CRLF", b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""))
check("không có dấu gạch dài (U+2014) trong mã Concat",
      not any(chr(0x2014) in p.read_text(encoding="utf-8", errors="ignore")
              for p in [*(ROOT / "apps" / "concat").rglob("*"), ROOT / "server" / "concat_cau.py",
                        ROOT / "server" / "routes" / "concat.py", *(ROOT / "system" / "plugins" / "concat").rglob("*")]
              if p.is_file()))

giay_phep.da_mo, knn.da_dong_y = _da_mo_goc, _dong_y_goc
print()
if _fails:
    print(f"{len(_fails)} FAIL")
    sys.exit(1)
print("Tất cả OK")
os._exit(0)
