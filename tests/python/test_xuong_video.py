"""Xưởng video: kho, khoá, nhà cung cấp (giả lập HTTP), kịch bản, ghép thật bằng ffmpeg, đăng, dây chuyền, API.
python tests/run.py xuong_video"""
import asyncio, base64, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "server"))
os.environ["JAVIS_STATE_DIR"] = tempfile.mkdtemp()
import _paths  # noqa
import httpx

ok = True
def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)

from xuong_video import chay, dang, ghep, kho, khoa, kich_ban, ncc

def chay_async(c):
    return asyncio.new_event_loop().run_until_complete(c)

# ---- kho
pid = kho.tao({"ten": "T1", "y_tuong": "con mèo đi phượt", "nen_tang": ["youtube", "bậy", "facebook_reel"],
               "ti_le": "4:3", "thoi_luong_giay": 9999, "che_do_dang": "linh tinh"})
p = kho.doc(pid)
check("tạo dự án: lọc nền tảng lạ, ép tỉ lệ và thời lượng, mặc định chế độ duyệt",
      p["nen_tang"] == ["youtube", "facebook_reel"] and p["ti_le"] == "9:16" and p["thoi_luong_giay"] == 180
      and p["che_do_dang"] == "duyet")
rel, loi = kho.them_tai_lieu(pid, "../x/anh mau.PNG", b"\x89PNG....")
check("lưu tài liệu, chống đường dẫn lạ", rel == "tai-lieu/anh_mau.PNG" and not loi, (rel, loi))
check("đuôi lạ bị từ chối", kho.them_tai_lieu(pid, "a.exe", b"x")[1] != "")
check("không đọc được file ngoài thư mục dự án", kho.duong_dan_file(pid, "../../khoa.json") is None and kho.duong_dan_file(pid, rel))
check("id lạ không tạo thư mục ngoài", kho.doc("../..") is None)

# ---- khoá
khoa.dat("gemini", {"api_key": "AIzaSECRET1234"})
tt = khoa.tinh_trang()
check("khoá không lộ ra giao diện, chỉ 4 ký tự cuối", "SECRET" not in json.dumps(tt) and tt["gemini"]["api_key"].endswith("1234"))
raw = (Path(os.environ["JAVIS_STATE_DIR"]) / "xuong-video" / "khoa.json").read_text()
check("khoá lưu trên đĩa đã mã hoá", "SECRET" not in raw)
check("cài đặt có mặc định và kẹp giá trị", khoa.luu_cai_dat({"toi_da_video_moi_ngay": 99999})["toi_da_video_moi_ngay"] == 500)
khoa.luu_cai_dat({"toi_da_video_moi_ngay": 20})

# ---- kịch bản
check("đọc JSON trong khối code", kich_ban.doc_json('xin chào ```json\n{"a":1}\n``` hết') == {"a": 1})
try:
    kich_ban.doc_json("không có json"); loi_json = False
except ValueError:
    loi_json = True
check("không có JSON thì báo lỗi", loi_json)
kb_json = {"tieu_de": "Mèo phượt", "mo_ta": "m", "hashtags": ["#meo", "phuot"], "nhan_vat": [{"ten": "Miu", "mo_ta": "mèo tam thể"}],
           "canh": [{"loi_thoai": "Xin chào " + "chữ " * 40, "mo_ta_hinh": "mèo trên xe máy", "giay": 5, "nhan_vat": ["Miu"]},
                    {"loi_thoai": "Tạm biệt", "mo_ta_hinh": "mèo vẫy tay", "giay": 5}]}
goi = {"n": 0}
async def ask_gia(yc, brain, files):
    goi["n"] += 1
    return "đây\n```json\n" + json.dumps(kb_json) + "\n```" if goi["n"] > 1 else "xin lỗi không có JSON"
copied = []
def chep_gia(brain, files):
    copied.extend(files); return [f"attachments/{Path(f).name}" for f in files]
kq = chay_async(kich_ban.lap(pid, ask_gia, chep_gia))
p = kho.doc(pid)
check("lập kịch bản: thử lại một lần khi lần đầu hỏng", goi["n"] == 2 and len(p["canh"]) == 2 and p["trang_thai"] == "kich_ban_xong")
check("làm sạch: thoại bị cắt theo thời lượng, thẻ # được gỡ", len(p["canh"][0]["loi_thoai"].split()) <= 5 * kich_ban.TU_MOI_GIAY + 1
      and p["kich_ban"]["hashtags"] == ["meo", "phuot"], p["canh"][0]["loi_thoai"])
check("ảnh tài liệu được chép vào brain cho engine xem", len(copied) == 1)
try:
    kich_ban.lam_sach({"canh": [{"mo_ta_hinh": ""}]}, p); thieu = False
except ValueError:
    thieu = True
check("cảnh thiếu mô tả hình bị từ chối", thieu)

# ---- nhà cung cấp với HTTP giả
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
nhat = []
def gia_http(handler):
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))

def h_gemini(req):
    nhat.append(req)
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "x"}, {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(PNG).decode()}}]}}]})
ncc._client = gia_http(h_gemini)
b = chay_async(ncc.tao_anh("mèo", "9:16", None, {"ncc": "gemini", "model": "m1"}))
check("ảnh Gemini: giải mã đúng, khoá nằm ở header chứ không ở URL", b == PNG and nhat[0].headers["x-goog-api-key"] == "AIzaSECRET1234" and "AIza" not in str(nhat[0].url))
ncc._client = gia_http(lambda r: httpx.Response(429, json={"error": {"message": "quota"}}))
try:
    chay_async(ncc.tao_anh("mèo", "9:16", None, {"ncc": "gemini", "model": "m1"})); msg = ""
except ncc.LoiNcc as e:
    msg = str(e)
check("lỗi 429 dịch ra tiếng Việt, không lộ khoá", "429" in msg and "hạn mức" in msg and "SECRET" not in msg, msg)
ncc._client = gia_http(lambda r: httpx.Response(200, json={"candidates": []}))
try:
    chay_async(ncc.tao_anh("mèo", "9:16", None, {"ncc": "gemini", "model": "m1"})); msg = ""
except ncc.LoiNcc as e:
    msg = str(e)
check("không có ảnh trả về thì báo rõ", "không trả về ảnh" in msg, msg)

async def khong_ngu(_): return None
ncc._ngu = khong_ngu
khoa.dat("fal", {"api_key": "falkey123456"})
anh_tam = Path(tempfile.mkdtemp()) / "a.png"; anh_tam.write_bytes(PNG)
dem_hoi = {"n": 0}
def h_fal(req):
    u = str(req.url)
    if req.method == "POST":
        return httpx.Response(200, json={"request_id": "r1", "status_url": "https://queue.fal.run/s", "response_url": "https://queue.fal.run/r"})
    if u.endswith("/s"):
        dem_hoi["n"] += 1
        return httpx.Response(200, json={"status": "COMPLETED" if dem_hoi["n"] >= 2 else "IN_PROGRESS"})
    if u.endswith("/r"):
        return httpx.Response(200, json={"video": {"url": "https://cdn.fal/v.mp4"}})
    return httpx.Response(200, content=b"VIDEOBYTES")
ncc._client = gia_http(h_fal)
v = chay_async(ncc.tao_video("mèo chạy", anh_tam, 5, "9:16", {"ncc": "fal", "model": "fal-ai/veo3.1/image-to-video"}))
check("video fal: xếp hàng, hỏi tới khi xong, tải về", v == b"VIDEOBYTES" and dem_hoi["n"] == 2)
try:
    chay_async(ncc.tao_video("x", None, 5, "9:16", {"ncc": "fal", "model": "fal-ai/veo3.1/image-to-video"})); msg = ""
except ncc.LoiNcc as e:
    msg = str(e)
check("model cần ảnh mà cảnh chưa có ảnh thì báo, không gọi tốn tiền", "cần ảnh" in msg, msg)
try:
    chay_async(ncc.tao_video("x", anh_tam, 5, "9:16", {"ncc": "kling", "model": "m"})); msg = ""
except ncc.LoiNcc as e:
    msg = str(e)
check("video: nhà cung cấp chưa hỗ trợ báo thẳng", "chưa được hỗ trợ" in msg, msg)

khoa.dat("elevenlabs", {"api_key": "elkey123456", "voice_id": "V1"})
ncc._client = gia_http(lambda r: httpx.Response(200, content=b"MP3"))
check("giọng ElevenLabs", chay_async(ncc.tao_giong("xin chào", {"ncc": "elevenlabs", "model": "m"})) == b"MP3")

# ---- ghép thật bằng ffmpeg
if shutil.which("ffmpeg"):
    pg = kho.tao({"ten": "G", "y_tuong": "x", "ti_le": "9:16"})
    base = kho.thu_muc(pg); (base / "canh").mkdir()
    canh = []
    for i in (1, 2):
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=2", "-pix_fmt", "yuv420p", str(base / "canh" / f"{i:02d}.mp4")], capture_output=True, check=True)
        canh.append({"stt": i, "loi_thoai": f"Lời cảnh {i}", "mo_ta_hinh": "h", "giay": 2, "video": f"canh/{i:02d}.mp4", "giong": "", "anh": ""})
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", str(base / "canh" / "01.mp3")], capture_output=True, check=True)
    canh[0]["giong"] = "canh/01.mp3"
    kho.cap_nhat(pg, canh=canh)
    kq = chay_async(ghep.ghep(pg, True))
    dai = chay_async(ghep.do_dai(base / kq["video"]))
    check("ghép thật: ra video dọc 1080x1920, dài đủ cả giọng kéo cảnh", kq["kich_co"] == "1080x1920" and 4.5 < dai < 7, (kq, dai))
    kho.cap_nhat_canh(pg, 2, video="")
    try:
        chay_async(ghep.ghep(pg)); thieu = False
    except ghep.LoiGhep:
        thieu = True
    check("còn cảnh thiếu video thì không ghép", thieu)
else:
    print("SKIP không có ffmpeg")

# ---- đăng
v_tam = Path(tempfile.mkdtemp()) / "v.mp4"; v_tam.write_bytes(b"0" * 100)
khoa.dat("youtube", {"client_id": "cid", "client_secret": "csec", "refresh_token": "rt"})
yt = {"loi_put": False}
def h_yt(req):
    u = str(req.url)
    if "oauth2.googleapis.com" in u:
        return httpx.Response(200, json={"access_token": "AT"})
    if req.method == "POST":
        return httpx.Response(200, headers={"location": "https://up.yt/session1"})
    if yt["loi_put"]:
        raise httpx.ReadTimeout("hết giờ")
    return httpx.Response(200, json={"id": "VID123"})
dang._client = gia_http(h_yt)
pp = kho.doc(pid)
r = chay_async(dang.dang("youtube_short", pp, v_tam))
check("YouTube Shorts: link /shorts/", r["url"].endswith("/shorts/VID123"))
yt["loi_put"] = True
try:
    chay_async(dang.dang("youtube", pp, v_tam)); chua_ro = None
except dang.LoiDang as e:
    chua_ro = e.chua_ro
check("mất mạng giữa lúc tải lên YouTube: đánh dấu CHƯA RÕ (không được tự thử lại)", chua_ro is True)
for nt in ("tiktok", "instagram", "x", "threads", "zalo"):
    try:
        chay_async(dang.dang(nt, pp, v_tam)); lop = False
    except dang.LoiDang as e:
        lop = "chưa" in str(e).lower()
    if not lop: break
check("nền tảng chưa làm thì nói thẳng, không giả vờ đăng", lop)
try:
    chay_async(dang.dang("youtube_short", dict(pp, ti_le="16:9"), v_tam)); loi_tl = False
except dang.LoiDang:
    loi_tl = True
check("Shorts bắt buộc video dọc", loi_tl)

# ---- dây chuyền đầy đủ với nhà cung cấp giả
async def gia_anh(prompt, ti_le, tc, cfg): return PNG
async def gia_video(prompt, anh, giay, ti_le, cfg):
    f = Path(tempfile.mkdtemp()) / "c.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=2", "-pix_fmt", "yuv420p", str(f)], capture_output=True, check=True)
    return f.read_bytes()
async def gia_giong(text, cfg): return b"\xff\xfb\x90"  # không phải mp3 thật; ghép bỏ qua nếu đọc độ dài lỗi
ncc.tao_anh, ncc.tao_video, ncc.tao_giong = gia_anh, gia_video, gia_giong
thong = []
def tb(t, n=""): thong.append(t)
if shutil.which("ffmpeg"):
    khoa.xoa("elevenlabs")    # không giọng: đường phổ biến nhất khi mới dùng
    pc = kho.tao({"ten": "Chạy thử", "y_tuong": "mèo", "nen_tang": ["youtube", "facebook_reel"], "che_do_dang": "tu_dong"})
    goi["n"] = 5
    chay_async(chay.san_xuat(pc, ask_gia, chep_gia, tb))
    p = kho.doc(pc)
    check("dây chuyền: kịch bản -> ảnh -> video -> ghép -> sẵn sàng, tự hẹn giờ đăng",
          p["trang_thai"] == "san_sang" and p["ket_qua"].get("video") and p["dang_luc"] > 0 and p["so_video_da_tao"] == 2, (p["trang_thai"], p["loi"], p["nhat_ky"][-3:]))
    check("đã báo chuông khi xong", any("tự đăng" in t for t in thong), thong)

    lan = {"n": 0}
    async def dang_gia(nt, pr, v):
        lan["n"] += 1
        if nt == "facebook_reel":
            raise dang.LoiDang("Mất kết nối ở bước chốt.", chua_ro=True)
        return {"id": "Y1", "url": "https://yt/Y1"}
    dang.dang = dang_gia
    r = chay_async(chay.dang_du_an(pc, tb))
    p = kho.doc(pc)
    check("đăng: YouTube xong, Facebook chưa rõ", p["dang"]["youtube"]["trang_thai"] == "da_dang" and p["dang"]["facebook_reel"]["trang_thai"] == "chua_ro", p["dang"])
    n0 = lan["n"]
    chay_async(chay.dang_du_an(pc, tb)); chay_async(chay.dang_du_an(pc, tb, ep=True))
    check("không bao giờ tự đăng lại thứ đã đăng hoặc 'chưa rõ' (kể cả bấm tay)", lan["n"] == n0, (lan["n"], n0))
    check("hoàn tất khi mọi nền tảng đã có kết quả", kho.doc(pc)["trang_thai"] == "da_dang")

    # lỗi thường thì tự thử lại có giãn cách, tối đa hai lần
    pl = kho.tao({"ten": "L", "y_tuong": "x", "nen_tang": ["youtube"], "che_do_dang": "tu_dong"})
    shutil.copytree(kho.thu_muc(pc) / "ket-qua", kho.thu_muc(pl) / "ket-qua")
    kho.cap_nhat(pl, ket_qua=kho.doc(pc)["ket_qua"], trang_thai="san_sang")
    async def dang_loi(nt, pr, v): raise dang.LoiDang("Hết hạn token")
    dang.dang = dang_loi
    chay_async(chay.dang_du_an(pl, tb))
    s = kho.doc(pl)["dang"]["youtube"]
    check("lỗi thường: ghi lại, hẹn thử lại sau", s["trang_thai"] == "loi" and s["thu_lai_luc"] > s["luc"] + 500 and s["lan"] == 1, s)
    n1 = lan["n"]
    chay_async(chay.dang_du_an(pl, tb))
    check("chưa tới giờ thử lại thì không đăng", kho.doc(pl)["dang"]["youtube"]["lan"] == 1)

    # hạn mức
    khoa.luu_cai_dat({"toi_da_video_moi_ngay": 1})
    pm = kho.tao({"ten": "M", "y_tuong": "x"}); kho.cap_nhat(pm, canh=[{"stt": 1, "loi_thoai": "", "mo_ta_hinh": "h", "giay": 5, "anh": "", "video": "", "giong": "", "trang_thai": "cho", "loi": "", "nhan_vat": []}])
    chay_async(chay.san_xuat(pm, ask_gia, chep_gia, tb))
    check("chạm hạn mức video thì dừng, báo rõ, không tốn thêm tiền", kho.doc(pm)["trang_thai"] == "loi" and "hạn mức" in kho.doc(pm)["loi"], kho.doc(pm)["loi"])

# ---- API và cổng giấy phép
from fastapi import FastAPI
from fastapi.testclient import TestClient
import giay_phep
import routes.ket_noi_ngoai as knn
import routes.xuong_video as rx
app = FastAPI()
rx.register(app, ask_gia, chep_gia)
with TestClient(app) as tc:
    giay_phep.da_mo = lambda app_id: False
    check("chưa mở khoá thì API 403 và trang bị khoá", tc.get("/apps/xuong-video/api/trang-thai").status_code == 403
          and tc.get("/apps/xuong-video/").status_code == 403 and tc.get("/apps/xuong-video/app.js").status_code == 403)
    giay_phep.da_mo = lambda app_id: app_id == "xuong_video"
    knn.da_dong_y = lambda phan="chung": True
    d = tc.get("/apps/xuong-video/api/trang-thai").json()
    check("mở khoá: trạng thái không lộ khoá", d["ok"] and "SECRET" not in json.dumps(d) and "falkey" not in json.dumps(d))
    check("trang chính và tệp tĩnh phục vụ được, tệp lạ thì 404", tc.get("/apps/xuong-video/").status_code == 200
          and tc.get("/apps/xuong-video/app.js").status_code == 200 and tc.get("/apps/xuong-video/..%2fmain.py").status_code == 404)
    r = tc.post("/apps/xuong-video/api/du-an", json={"y_tuong": ""})
    check("thiếu ý tưởng bị từ chối", r.status_code == 400)
    nid = tc.post("/apps/xuong-video/api/du-an", json={"y_tuong": "abc", "ten": "API"}).json()["id"]
    r = tc.post(f"/apps/xuong-video/api/du-an/{nid}/tai-lieu?ten=a.png", content=PNG)
    check("tải tài liệu lên (thân thô)", r.json().get("ok"))
    r = tc.get(f"/apps/xuong-video/api/du-an/{nid}/tep", params={"rel": "../../khoa.json"})
    check("không đọc được tệp ngoài dự án", r.status_code == 404)
    r = tc.patch(f"/apps/xuong-video/api/du-an/{nid}", json={"nen_tang": ["youtube", "hack"], "ti_le": "9:99", "id": "evil", "trang_thai": "da_dang"})
    p = kho.doc(nid)
    check("sửa dự án: chỉ trường cho phép, giá trị lạ bị lọc", p["nen_tang"] == ["youtube"] and p["ti_le"] == "9:16" and p["id"] == nid and p["trang_thai"] == "nhap")
    check("duyệt khi chưa có video thì 400", tc.post(f"/apps/xuong-video/api/du-an/{nid}/duyet", json={}).status_code == 400)
    check("đăng ngay khi chưa có video thì 400", tc.post(f"/apps/xuong-video/api/du-an/{nid}/dang-ngay").status_code == 400)
    r = tc.post("/apps/xuong-video/api/lo", json={"y_tuong": "", "chung": {}})
    check("lô rỗng bị từ chối", r.status_code == 400)
    r = tc.post("/apps/xuong-video/api/khoa/gemini", json={"api_key": "KEYDAI-9999", "linh_tinh": "x"})
    check("đặt khoá qua API, trả về đã che", r.json()["ok"] and r.json()["khoa"]["gemini"]["api_key"].endswith("9999") and "KEYDAI-9999" != r.json()["khoa"]["gemini"]["api_key"])
    check("dịch vụ lạ bị từ chối", tc.post("/apps/xuong-video/api/khoa/evil", json={}).status_code == 400)
    check("xoá dự án", tc.delete(f"/apps/xuong-video/api/du-an/{nid}").json()["ok"] and kho.doc(nid) is None)

sys.exit(0 if ok else 1)
