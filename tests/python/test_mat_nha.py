# -*- coding: utf-8 -*-
"""MinMin Mắt Nhà (0.64.91): nhận sự kiện camera từ máy ở nhà. Chạy tay:

    python tests/run.py mat_nha

Phần lớn test này là test AN TOÀN, vì POST /mat-nha/su-kien là đường mới được miễn cổng đăng
nhập (cầu nối ở nhà không có cookie):
  1. Chỉ đúng cặp (POST, /mat-nha/su-kien) được miễn. GET cùng đường, /mat-nha/ma, ảnh, trạng
     thái và mọi đường khác vẫn 401 khi chưa đăng nhập.
  2. Không mã / sai mã -> 401 từ CHÍNH endpoint; mã chỉ lưu bản băm trong settings.
Sau đó: lưu, trùng id, lọc, ảnh, hạn lưu trữ, nhịp cầu nối, plugin mat-nha, bộ cài và cầu nối.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import base64
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

_STATE = tempfile.mkdtemp(prefix="javis-matnha-")
os.environ["JAVIS_STATE_DIR"] = _STATE
os.environ.setdefault("BRAINS_DIR", tempfile.mkdtemp(prefix="javis-matnha-brains-"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from fastapi.testclient import TestClient   # noqa: E402
import main                                 # noqa: E402
import mat_nha                              # noqa: E402

_fails = []


def check(name, cond, extra=None):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond or extra is None else f"  [{extra}]"))
    if not cond:
        _fails.append(name)


cl = TestClient(main.app, base_url="http://localhost")
KIT = ROOT / "dashboard" / "mat-nha" / "kit"
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200 + b"\xff\xd9"

# ============ 1. Cổng đăng nhập BẬT: chỉ POST /mat-nha/su-kien lọt qua ============
_gate_goc = main.cfgmod.gate_active
main.cfgmod.gate_active = lambda: True
r = cl.post("/mat-nha/su-kien", json={"id": "a1"})
check("bật cổng, POST không mã -> 401 do CHÍNH endpoint (không phải hàng rào)",
      r.status_code == 401 and r.json().get("mat_nha") and not r.json().get("auth_required"), r.text)
r = cl.post("/mat-nha/su-kien", json={"id": "a1"}, headers={"x-mat-nha-token": "mn_sai"})
check("bật cổng, sai mã -> 401", r.status_code == 401, r.status_code)
for m, d in (("GET", "/mat-nha/su-kien"), ("POST", "/mat-nha/ma"), ("GET", "/mat-nha/trang-thai"),
             ("GET", "/mat-nha/anh/a1.jpg"), ("GET", "/mat-nha"), ("POST", "/mat-nha/su-kien/"),
             ("POST", "/mat-nha/su-kienX"), ("PUT", "/mat-nha/su-kien"), ("GET", "/settings"),
             ("GET", "/agents")):
    rr = cl.request(m, d)
    check(f"bật cổng, {m} {d} vẫn cần đăng nhập (401 của hàng rào)",
          rr.status_code == 401 and rr.json().get("auth_required") is True, (rr.status_code, rr.text[:80]))
check("miễn đăng nhập đúng MỘT cặp (đường, POST)", main._MAT_NHA_CONG_KHAI == ("/mat-nha/su-kien", "POST"))
check("không đưa /mat-nha vào danh sách tiền tố công khai",
      not any(p.startswith("/mat") for p in main._AUTH_PUBLIC_PREFIX + main._AUTH_PUBLIC_EXACT))
main.cfgmod.gate_active = lambda: False

# ============ 2. Mã ghép nối ============
t0 = cl.get("/mat-nha/trang-thai").json()
check("chưa có mã lúc đầu", t0["ma"]["da_co"] is False, t0)
check("chưa có mã thì không nhận sự kiện",
      cl.post("/mat-nha/su-kien", json={"id": "x"}, headers={"x-mat-nha-token": ""}).status_code == 401)
r = cl.post("/mat-nha/ma")
MA = r.json().get("ma", "")
check("tạo được mã, đủ dài", r.status_code == 200 and MA.startswith("mn_") and len(MA) >= 30, r.text)
raw = (Path(_STATE) / "settings.json").read_text(encoding="utf-8")
check("settings.json KHÔNG chứa mã nguyên văn (chỉ bản băm)", MA not in raw and "token_hash" in raw)
check("GET /settings không lộ mã", MA not in cl.get("/settings").text)
check("trạng thái báo đã có mã + 4 ký tự cuối",
      cl.get("/mat-nha/trang-thai").json()["ma"] == {"da_co": True, "tao_luc": json.loads(raw)["mat_nha"]["token_tao_luc"],
                                                      "cuoi": MA[-4:]})
H = {"x-mat-nha-token": MA}

# ============ 3. Lưu sự kiện ============
now = time.time()
ev1 = {"id": "1727600000.1-abc", "camera": "Cổng", "loai": "nguoi", "nhan": "person", "ten": "Bố",
       "la_nguoi_la": True, "bat_dau": now - 60, "ket_thuc": now - 30, "diem": 0.91,
       "anh_b64": base64.b64encode(JPEG).decode()}
r = cl.post("/mat-nha/su-kien", json=ev1, headers=H)
check("lưu sự kiện có ảnh", r.status_code == 200 and r.json().get("ok") and not r.json().get("trung"), r.text)
r = cl.post("/mat-nha/su-kien", json=ev1, headers=H)
check("gửi lại cùng id -> bỏ qua, báo trùng", r.status_code == 200 and r.json().get("trung") is True, r.text)
cl.post("/mat-nha/su-kien", headers=H, json={"id": "e2", "camera": "san", "loai": "nguoi", "nhan": "person",
                                             "la_nguoi_la": True, "bat_dau": now - 50})
cl.post("/mat-nha/su-kien", headers=H, json={"id": "e3", "camera": "san", "loai": "xe", "nhan": "motorcycle",
                                             "bien_so": "29-B1 123.45", "bat_dau": now - 40})
cl.post("/mat-nha/su-kien", headers=H, json={"id": "e4", "camera": "cong", "loai": "giong", "nhan": "speech",
                                             "chu": "Ai đấy ơi " * 300, "bat_dau": now - 20})
cl.post("/mat-nha/su-kien", headers=H, json={"id": "e5", "camera": "cong", "loai": "la-loai",
                                             "bat_dau": now - 10})
check("id bậy -> 400", cl.post("/mat-nha/su-kien", headers=H, json={"id": "../../x"}).status_code == 400)
check("ảnh không phải JPEG -> 400", cl.post("/mat-nha/su-kien", headers=H,
      json={"id": "p1", "anh_b64": base64.b64encode(b"GIF89a....").decode()}).status_code == 400)
check("ảnh quá 300KB -> 400", cl.post("/mat-nha/su-kien", headers=H,
      json={"id": "p2", "anh_b64": base64.b64encode(b"\xff\xd8" + b"0" * 400_000).decode()}).status_code == 400)
check("thân quá lớn -> 413", cl.post("/mat-nha/su-kien", headers=H,
      content=b'{"id":"p3","x":"' + b"a" * 1_600_000 + b'"}').status_code == 413)
check("JSON hỏng -> 400", cl.post("/mat-nha/su-kien", headers=H, content=b"{hong").status_code == 400)

ds = cl.get("/mat-nha/su-kien").json()["su_kien"]
check("đọc lại đủ 5 sự kiện, mới nhất trước", [e["id"] for e in ds] == ["e5", "e4", "e3", "e2", "1727600000.1-abc"],
      [e["id"] for e in ds])
e1 = ds[-1]
check("tên camera chuẩn hoá (không dấu, thường)", e1["camera"] == "c-ng" or e1["camera"].isascii(), e1["camera"])
check("có tên người nhà thì KHÔNG phải người lạ", e1["ten"] == "Bố" and e1["la_nguoi_la"] is False)
check("có đường ảnh", e1.get("anh") == "/mat-nha/anh/1727600000.1-abc.jpg", e1.get("anh"))
check("loại lạ -> 'khac'", ds[0]["loai"] == "khac")
check("lời nói bị cắt còn tối đa 1000 ký tự", len(ds[1]["chu"]) <= 1000)

# ============ 4. Lọc ============
def ids(**q):
    return [e["id"] for e in cl.get("/mat-nha/su-kien", params=q).json()["su_kien"]]


check("lọc người lạ", ids(chi_nguoi_la="true") == ["e2"], ids(chi_nguoi_la="true"))
check("lọc biển số khớp một phần, bỏ dấu", ids(bien_so="29b1") == ["e3"] and ids(bien_so="12345") == ["e3"])
check("lọc camera", set(ids(camera="san")) == {"e2", "e3"})
check("lọc loại", ids(loai="giong") == ["e4"])
check("lọc tên", ids(ten="bố") == ["1727600000.1-abc"])
check("lọc limit", len(ids(limit=2)) == 2)
check("lọc thời gian: từ ngày mai -> rỗng",
      ids(tu=time.strftime("%Y-%m-%d", time.localtime(now + 2 * 86400))) == [])
check("mốc sai -> 400", cl.get("/mat-nha/su-kien", params={"tu": "hôm qua"}).status_code == 400)

# ============ 5. Ảnh ============
a = cl.get("/mat-nha/anh/1727600000.1-abc.jpg")
check("lấy được ảnh JPEG", a.status_code == 200 and a.content == JPEG and a.headers["content-type"] == "image/jpeg")
check("ảnh không có -> 404", cl.get("/mat-nha/anh/e2.jpg").status_code == 404)
check("id ảnh bậy -> 404", cl.get("/mat-nha/anh/..%2Fsettings.jpg").status_code == 404)

# ============ 6. Nhịp cầu nối ============
t = cl.get("/mat-nha/trang-thai").json()
check("chưa có nhịp -> cầu nối chưa sống", t["cau_noi_song"] is False)
r = cl.post("/mat-nha/su-kien", headers=H, json={"loai": "nhip", "cameras": ["cong", "san", "phong_khach"],
                                                 "phien_ban": "1.0.0", "hang_doi": 3})
t = cl.get("/mat-nha/trang-thai").json()
check("nhịp -> cầu nối sống, có danh sách camera",
      r.status_code == 200 and t["cau_noi_song"] and {"cong", "san", "phong_khach"} <= {c["camera"] for c in t["cameras"]}, t)
check("nhịp không thành sự kiện", len(ids()) == 5)

# ============ 7. Hạn lưu trữ ============
goc = mat_nha.thu_muc()
cu = goc / "su-kien" / "2000-01-01.jsonl"
cu.write_text(json.dumps({"id": "cu", "bat_dau": 946684800}) + "\n", encoding="utf-8")
anh_cu = goc / "anh" / "cu.jpg"
anh_cu.write_bytes(JPEG)
os.utime(anh_cu, (now - 40 * 86400, now - 40 * 86400))
kq = mat_nha.don_dep(ep=True)
check("dọn: xoá file sự kiện quá 30 ngày và ảnh quá hạn",
      not cu.exists() and not anh_cu.exists() and kq["xoa_file"] >= 1 and kq["xoa_anh"] >= 1, kq)
check("dọn: giữ file hôm nay", any((goc / "su-kien").glob("*.jsonl")))
_tran = mat_nha.ANH_TONG_TOI_DA
mat_nha.ANH_TONG_TOI_DA = len(JPEG) + 10
for i in range(3):
    f = goc / "anh" / f"tran{i}.jpg"
    f.write_bytes(JPEG)
    os.utime(f, (now - 100 + i, now - 100 + i))
mat_nha.don_dep(ep=True)
con = sorted(p.name for p in (goc / "anh").glob("*.jpg"))
check("dọn: vượt trần dung lượng -> xoá ảnh cũ nhất trước", len(con) == 1, con)
mat_nha.ANH_TONG_TOI_DA = _tran

# ============ 8. Plugin mat-nha ============
import plugins_host  # noqa: E402

plugins_host.invalidate()
desc = {d["slug"]: d for d in plugins_host.describe(None)}
check("plugin mat-nha có mặt, bật sẵn, chỉ đọc",
      "mat-nha" in desc and desc["mat-nha"]["enabled"] and desc["mat-nha"]["loaded"]
      and desc["mat-nha"]["min_mode"] == "readonly", desc.get("mat-nha"))
tools, route = plugins_host.plugin_tools("suggest", None)
check("tool mat_nha_su_kien chạy được ở chế độ suggest", "mat_nha_su_kien" in {t["fn"] for t in tools})
out = asyncio.run(route["mat_nha_su_kien"]["call"]({}))
check("tóm tắt hôm nay: có tên người nhà, người lạ, biển số",
      "Bố" in out and "người lạ" in out and "29-B1 123.45" in out, out[:300])
out = asyncio.run(route["mat_nha_su_kien"]["call"]({"bien_so": "29-B1", "loai": "xe"}))
check("tra biển số -> đúng 1 sự kiện xe", out.startswith("1 sự kiện") or "\n1 sự kiện" in out or "1 sự kiện." in out, out[:200])
out = asyncio.run(route["mat_nha_su_kien"]["call"]({"tu": "sai"}))
check("mốc sai -> ERROR, không nổ", out.startswith("ERROR"), out)

# ============ 9. Chống dò mã ============
for _ in range(20):
    cl.post("/mat-nha/su-kien", headers={"x-mat-nha-token": "mn_do"}, json={"id": "z"})
check("sai mã 20 lần -> 429 (kể cả mã đúng, trong 10 phút)",
      cl.post("/mat-nha/su-kien", headers=H, json={"id": "z"}).status_code == 429)
import routes.mat_nha as rmn  # noqa: E402
rmn._SAI.clear()

# ============ 10. Bộ cài: .bat, .ps1, mẫu compose/config ============
bat = (KIT / "CaiMatNha.bat").read_bytes()
check(".bat chỉ ASCII", all(b < 128 for b in bat))
check(".bat xuống dòng CRLF, không có LF trần", b"\r\n" in bat and b"\n" not in bat.replace(b"\r\n", b""))
check(".bat có chỗ điền địa chỉ MinMin và chạy ps1 với ExecutionPolicy Bypass",
      b"__MINMIN_URL__" in bat and b"-ExecutionPolicy Bypass -File" in bat)
check(".bat không so sánh chuỗi __MINMIN_URL__ (JS thay chỗ đầu tiên, phép so phải bằng tiền tố)",
      bat.count(b"__MINMIN_URL__") == 1)
ps1 = (KIT / "CaiMatNha.ps1").read_bytes()
check(".ps1 có BOM UTF-8 (PowerShell 5.1 mới đọc đúng tiếng Việt)", ps1.startswith(b"\xef\xbb\xbf"))
check(".ps1 xuống dòng CRLF", b"\n" not in ps1.replace(b"\r\n", b""))
ps1t = ps1.decode("utf-8-sig")
for k in ("# >>> CAMERAS", "# <<< CAMERAS", "# >>> DETECTORS", "#__GPU__", "/Streaming/Channels/101",
          "/Streaming/Channels/102", "docker compose up -d", "x-mat-nha-token", "nvidia-smi", "winget", "wsl"):
    check(f".ps1 có '{k}'", k in ps1t)
check("không có dấu gạch dài (U+2014) trong bộ cài và trang",
      not any(chr(0x2014) in p.read_text(encoding="utf-8-sig", errors="ignore")
              for p in (ROOT / "dashboard" / "mat-nha").rglob("*") if p.is_file()))

import yaml  # noqa: E402

comp = yaml.safe_load((KIT / "docker-compose.yml").read_text(encoding="utf-8"))
sv = comp["services"]
check("compose có frigate (tensorrt), mosquitto, minmin-cau",
      {"frigate", "mosquitto", "minmin-cau"} <= set(sv) and sv["frigate"]["image"].endswith("-tensorrt"))
check("compose frigate: shm_size, volumes config/storage, cổng 5000 chỉ localhost",
      sv["frigate"].get("shm_size") and "./config:/config" in sv["frigate"]["volumes"]
      and "127.0.0.1:5000:5000" in sv["frigate"]["ports"])
check("compose: mosquitto KHÔNG mở cổng ra ngoài", "ports" not in sv["mosquitto"])
check("compose: minmin-cau đọc .env, build ./minmin-cau",
      sv["minmin-cau"]["env_file"] == ".env" and sv["minmin-cau"]["build"] == "./minmin-cau")
txt = (KIT / "docker-compose.yml").read_text(encoding="utf-8")
check("compose có chỗ chèn khối GPU, đúng một lần", txt.count("#__GPU__") == 1)
gpu = ("deploy:\n      resources:\n        reservations:\n          devices:\n            - driver: nvidia\n"
       "              count: 1\n              capabilities: [gpu]")
comp2 = yaml.safe_load(txt.replace("#__GPU__", gpu))
check("chèn khối GPU vẫn là YAML hợp lệ, đúng chỗ",
      comp2["services"]["frigate"]["deploy"]["resources"]["reservations"]["devices"][0]["driver"] == "nvidia")

cfg_txt = (KIT / "config.yml").read_text(encoding="utf-8")
cfg = yaml.safe_load(cfg_txt)
check("config: mqtt tới mosquitto", cfg["mqtt"]["host"] == "mosquitto" and cfg["mqtt"]["enabled"])
check("config: detector ONNX cho NVIDIA + model yolo-generic + labelmap coco-80",
      cfg["detectors"]["onnx_0"]["type"] == "onnx" and cfg["model"]["model_type"] == "yolo-generic"
      and cfg["model"]["labelmap_path"] == "/labelmap/coco-80.txt")
check("config: theo dõi người, xe, xe máy, chó mèo",
      {"person", "car", "motorcycle", "bicycle", "truck", "bus", "dog", "cat"} <= set(cfg["objects"]["track"]))
check("config: bật nhận mặt, biển số (model large), âm thanh + chép lời tiếng Việt",
      cfg["face_recognition"]["enabled"] and cfg["lpr"]["enabled"] and cfg["lpr"]["model_size"] == "large"
      and "speech" in cfg["audio"]["listen"] and cfg["audio_transcription"]["language"] == "vi")
check("config: lưu 7 ngày sự kiện, 30 ngày ảnh chụp",
      cfg["record"]["alerts"]["retain"]["days"] == 7 and cfg["snapshots"]["retain"]["default"] == 30)
check("config: luồng phụ (102) để nhận diện, luồng chính (101) để ghi + tiếng",
      "/Streaming/Channels/102" in cfg_txt and cfg["cameras"]["vi_du"]["ffmpeg"]["inputs"][1]["roles"] == ["detect"]
      and "audio" in cfg["cameras"]["vi_du"]["ffmpeg"]["inputs"][0]["roles"])
for k in ("# >>> CAMERAS", "# <<< CAMERAS", "# >>> DETECTORS", "# <<< DETECTORS"):
    # ĐÚNG MỘT lần: ps1 thay bằng regex không tham lam, dấu lặp lại trong chú thích là thay nhầm chỗ.
    check(f"config có dấu '{k}' đúng một lần", cfg_txt.count(k) == 1, cfg_txt.count(k))
import re  # noqa: E402

# Bản CPU mà ps1 sinh ra (máy không có GPU NVIDIA) vẫn phải là YAML hợp lệ và đúng giá trị.
# Mẫu regex dưới đây PHẢI trùng nguyên văn trong ps1 (kiểm ngay bên dưới), .NET và Python hiểu
# giống nhau với các mẫu đơn giản này.
_thay = [(r"(?s)(face_recognition:.*?model_size: )large", r"\1small"),
         (r"(?s)(lpr:.*?device: )GPU", r"\1CPU"),
         (r"(?s)(audio_transcription:\s*enabled: )true", r"\1false")]
for mau_re, _ in _thay:
    check(f"ps1 dùng đúng mẫu '{mau_re}'", f"'{mau_re}'" in ps1t)
cpu = cfg_txt.replace("hwaccel_args: preset-nvidia", "hwaccel_args: auto")
for mau_re, thay in _thay:
    cpu = re.sub(mau_re, thay, cpu, count=1)
cpu = re.sub(r"(?s)# >>> DETECTORS.*?# <<< DETECTORS",
             "# >>> DETECTORS\ndetectors:\n  cpu1:\n    type: cpu\n# <<< DETECTORS", cpu)
cc = yaml.safe_load(cpu)
check("bản CPU: detector cpu, không còn model ONNX, nhận mặt small, biển số CPU, tắt chép lời",
      cc["detectors"] == {"cpu1": {"type": "cpu"}} and "model" not in cc
      and cc["face_recognition"]["model_size"] == "small" and cc["lpr"]["device"] == "CPU"
      and cc["audio_transcription"]["enabled"] is False and cc["ffmpeg"]["hwaccel_args"] == "auto")

fmt = re.compile(cfg["lpr"]["format"])
for bien in ("30A12345", "30A-123.45", "30A-1234", "51LD-123.45", "29-B1 123.45", "29B112345", "59X2 23456"):
    check(f"regex biển số nhận '{bien}'", bool(fmt.match(bien)))
for bien in ("ABC123", "123", "3A-12345"):
    check(f"regex biển số loại '{bien}'", not fmt.match(bien))

# ============ 11. Cầu nối minmin-cau (không cần paho, không cần mạng) ============
spec = importlib.util.spec_from_file_location("cau_mat_nha", KIT / "minmin-cau" / "cau.py")
cau = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cau)
gui, tra_ve = [], {"ma": 0}


def _gui(body):
    gui.append(body)
    return tra_ve["ma"]


c = cau.Cau(thu_muc=tempfile.mkdtemp(prefix="cau-"), gui_ham=_gui, lay_anh_ham=lambda eid: JPEG,
            minmin_url="http://x", token="t")
c.xu_ly("frigate/tracked_object_update", json.dumps({"type": "face", "id": "p1", "name": "Mẹ", "score": 0.95}))
c.xu_ly("frigate/events", json.dumps({"type": "update", "after": {"id": "p1", "label": "person"}}))
ev = c.xu_ly("frigate/events", json.dumps({"type": "end", "after": {
    "id": "p1", "camera": "cong", "label": "person", "sub_label": None, "top_score": 0.88,
    "start_time": 1700000000.5, "end_time": 1700000010.0, "has_snapshot": True}}).encode())
check("cầu: người + mặt đã học -> tên, không phải người lạ, kèm ảnh",
      ev and ev["ten"] == "Mẹ" and ev["la_nguoi_la"] is False and ev["loai"] == "nguoi"
      and base64.b64decode(ev["anh_b64"]) == JPEG, ev)
ev = c.xu_ly("frigate/events", json.dumps({"type": "end", "after": {
    "id": "p2", "camera": "cong", "label": "person", "sub_label": ["Bố", 0.9], "start_time": 1700000100}}))
check("cầu: sub_label dạng [tên, điểm] -> tên", ev and ev["ten"] == "Bố")
ev = c.xu_ly("frigate/events", json.dumps({"type": "end", "after": {
    "id": "p3", "camera": "san", "label": "person", "start_time": 1700000200}}))
check("cầu: người không nhận ra mặt -> người lạ", ev and ev["la_nguoi_la"] is True and ev["ten"] is None)
c.xu_ly("frigate/tracked_object_update", json.dumps({"type": "lpr", "id": "x1", "plate": "29B112345", "name": None}))
ev = c.xu_ly("frigate/events", json.dumps({"type": "end", "after": {
    "id": "x1", "camera": "san", "label": "motorcycle", "start_time": 1700000300}}))
check("cầu: xe máy + biển số từ tracked_object_update", ev and ev["loai"] == "xe" and ev["bien_so"] == "29B112345")
ev = c.xu_ly("frigate/events", json.dumps({"type": "end", "after": {
    "id": "x2", "camera": "san", "label": "car", "recognized_license_plate": "30A12345",
    "sub_label": "Xe của bố", "start_time": 1700000400}}))
check("cầu: biển số từ recognized_license_plate, biển quen -> tên xe",
      ev and ev["bien_so"] == "30A12345" and ev["ten"] == "Xe của bố")
check("cầu: nhãn lạ -> vật, âm thanh -> giọng",
      c.xu_ly("frigate/events", json.dumps({"type": "end", "after": {"id": "o1", "label": "umbrella", "camera": "a"}}))["loai"] == "vat"
      and c.xu_ly("frigate/events", json.dumps({"type": "end", "after": {"id": "o2", "label": "bark", "camera": "a"}}))["loai"] == "giong")
check("cầu: trùng id -> không xếp hàng lần hai",
      c.xu_ly("frigate/events", json.dumps({"type": "end", "after": {"id": "p3", "label": "person", "camera": "san"}})) is None)
check("cầu: tin hỏng không nổ", c.xu_ly("frigate/events", b"{hong") is None)
check("cầu: 7 sự kiện trong hàng đợi", c.so_hang_doi() == 7, c.so_hang_doi())

# lời nói: gom theo camera, gửi khi im 15 giây
check("cầu: lời nói đầu tiên chưa gửi ngay", c.xu_ly("frigate/cong/audio/transcription", "Xin chào", now=1000.0) is None)
c.xu_ly("frigate/cong/audio/transcription", b"co ai o nha khong", now=1005.0)
check("cầu: chưa im đủ lâu thì chưa đóng câu", c.tick(now=1010.0) == [])
xong = c.tick(now=1030.0)
check("cầu: im 15 giây -> một sự kiện giọng nói gộp cả câu",
      len(xong) == 1 and xong[0]["chu"] == "Xin chào co ai o nha khong" and xong[0]["camera"] == "cong"
      and xong[0]["loai"] == "giong", xong)

# mất mạng -> giữ hàng đợi, lùi thời gian chờ; có mạng lại -> gửi hết theo thứ tự
tra_ve["ma"] = 0
check("cầu: mất mạng -> không gửi được gì, giữ hàng đợi", c.gui_het(now=2000.0) == 0 and c.so_hang_doi() == 8)
check("cầu: đang chờ lùi thì không thử lại ngay", c.gui_het(now=2001.0) == 0 and len(gui) == 1)
tra_ve["ma"] = 200
n = c.gui_het(now=2100.0)
check("cầu: có mạng lại -> gửi hết 8, hàng đợi rỗng, đúng thứ tự",
      n == 8 and c.so_hang_doi() == 0 and [b["id"] for b in gui[1:4]] == ["p1", "p2", "p3"], (n, [b.get("id") for b in gui]))
check("cầu: id đã gửi thì không xếp lại (kể cả sau khởi động lại)",
      cau.Cau(thu_muc=c.thu_muc, gui_ham=_gui).xep_hang({"id": "p1"}) is None)
# 400 = dữ liệu hỏng -> bỏ, không kẹt hàng đợi mãi
c.xep_hang({"id": "hong1", "camera": "a", "loai": "vat"})
tra_ve["ma"] = 400
check("cầu: MinMin trả 400 -> bỏ sự kiện đó, không kẹt", c.gui_het(now=3000.0) == 1 and c.so_hang_doi() == 0)
# 401 -> giữ lại, chờ lâu
c.xep_hang({"id": "k1", "camera": "a", "loai": "vat"})
tra_ve["ma"] = 401
c.gui_het(now=4000.0)
check("cầu: sai mã (401) -> giữ sự kiện, chờ 5 phút", c.so_hang_doi() == 1 and c.cho_den >= 4000.0 + 299)
tra_ve["ma"] = 200
c.nhip()
check("cầu: nhịp mang danh sách camera + phiên bản",
      gui[-1]["loai"] == "nhip" and "cong" in gui[-1]["cameras"] and gui[-1]["phien_ban"] == cau.PHIEN_BAN)
check("cầu: file cau.py chỉ ASCII (chạy được trên mọi code page)",
      all(b < 128 for b in (KIT / "minmin-cau" / "cau.py").read_bytes()))

main.cfgmod.gate_active = _gate_goc
print()
if _fails:
    print(f"ĐỎ {len(_fails)} phép thử:")
    for f in _fails:
        print("  - " + f)
    sys.exit(1)
print("Tất cả phép thử Mắt Nhà đều xanh.")
