"""Up bài từ Google Sheet: đọc cấu trúc Sheet, lịch giờ đăng, vòng xử lý/duyệt/đăng với Sheet giả,
AI giả, Graph API giả (httpx.MockTransport) và video thật làm bằng ffmpeg.
python tests/run.py up_bai"""
import asyncio, json, os, shutil, subprocess, sys, tempfile
from datetime import datetime
from pathlib import Path
os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp())
from _paths import ROOT  # noqa: E402
import httpx  # noqa: E402
import up_bai as ub  # noqa: E402

ok = True


def check(ten, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + ten + ("" if cond else f"  {extra}"))
    ok = ok and bool(cond)


# ---- thuần
check("cột chữ <-> số", ub.cot_chu(0) == "A" and ub.cot_chu(14) == "O" and ub.cot_chu(26) == "AA"
      and ub.chu_cot("AA") == 26 and ub.chu_cot("L") == 11)
lich = ub.doc_lich("Bắt đầu đăng từ 08h sáng, và cứ cách 1 tiếng lại đăng bài")
check("đọc lịch 'từ 08h cách 1 tiếng'", lich[0] == 480 and lich[1] == 540 and lich[-1] == 22 * 60, lich[:3])
check("đọc lịch danh sách mốc", ub.doc_lich("8h, 11h30, 20h") == [480, 690, 1200])
check("đọc lịch cách 90 phút", ub.doc_lich("từ 9h cách 90 phút")[:3] == [540, 630, 720])
check("lịch trống = mặc định 8h cách 60 phút", ub.doc_lich("")[:2] == [480, 540])

CFG = [["CHỈ CẦN CHỌN LOẠI CONTENT..."],
       ["Bật", "Tên Page", "Page ID", "Loại content", "Số bài/ngày", "Giờ đăng", "Trạng thái"],
       ["TRUE", "Liora Belle", "1159115630616690", "GIÁ CAO", "2", "Bắt đầu đăng từ 08h sáng, và cứ cách 1 tiếng lại đăng bài", "ĐÃ CẤU HÌNH"],
       ["FALSE", "Trang Tắt", "999", "GIÁ THẤP", "3", "", ""]]
cfgs = ub.doc_cau_hinh_page(CFG)
check("đọc CẤU HÌNH PAGE", cfgs["1159115630616690"].bai_ngay == 2 and cfgs["1159115630616690"].loai == "GIÁ CAO"
      and cfgs["999"].bat is False)
c = cfgs["1159115630616690"]
luc = datetime(2026, 10, 20, 9, 30, tzinfo=ub.VN)
check("được đăng khi tới mốc và chưa đủ bài", ub.den_gio_dang(c, [], luc) is None)
check("mốc giờ đã có bài thì chờ", "mốc" in (ub.den_gio_dang(c, [luc.replace(minute=5)], luc) or ""))
check("đủ số bài/ngày thì dừng", "đủ" in (ub.den_gio_dang(c, [luc.replace(hour=8), luc.replace(hour=9)], luc) or ""))
check("trước giờ đăng đầu thì chờ", ub.den_gio_dang(c, [], luc.replace(hour=7)) is not None)
check("Trang tắt thì không đăng", "tắt" in ub.den_gio_dang(cfgs["999"], [], luc))
check("lấy id Sheet từ link", ub.id_sheet("https://docs.google.com/spreadsheets/d/1t3aWcs1gBuWh3_49diIBcbhFUQNOaBGHrz6LKDIiu-s/edit?usp=x")
      == "1t3aWcs1gBuWh3_49diIBcbhFUQNOaBGHrz6LKDIiu-s" and ub.id_sheet("bậy") == "")
check("bóc JSON content", ub.boc_json('xin chào {"nhan_dien":"váy","content":"VÁY ĐẸP"} hết')["content"] == "VÁY ĐẸP"
      and ub.boc_json('{"nhan_dien":"x"}') is None)
p = ub.prompt_content(c, "CS002", "470000", ["SALE 30% VÁY SƠ MI"], "")
check("prompt có giá định dạng, mã, mẫu và giọng GIÁ CAO", "470.000đ" in p and "CS002" in p and "SALE 30%" in p and "sang" in p)
check("không có giá thì cấm bịa giá", "Không bịa giá" in ub.prompt_content(c, "", "", []))

# ---- Sheet giả
TIEU = ["Ngày đăng", "Giờ đăng", "Tên Page", "Page ID", "Link video", "Chỉnh sửa video", "Mã hàng", "Giá",
        "Chi tiết AI nhận diện", "Content hoàn chỉnh", "Duyệt", "Trạng thái", "Video ID", "Link bài", "Lỗi"]
SHEET = {
    ub.TAB_CAU_HINH: [r[:] for r in CFG],
    ub.TAB_HANG_DOI: [[""], ["MỖI VIDEO 1 DÒNG..."], TIEU[:],
                      ["", "", "Liora Belle", "1159115630616690", "https://www.tiktok.com/@shop/video/1", "", "CS009", "520000"],
                      ["", "", "Liora Belle", "1159115630616690", "không phải link", "", "", ""],
                      ["12/10", "9h00", "Liora Belle", "1159115630616690", "https://www.facebook.com/reel/9", "", "CS001", "",
                       "váy cũ", "SALE VÁY CŨ MẪU", "ĐÃ DUYỆT", "ĐÃ ĐĂNG", "1", "https://fb/1", ""]],
    ub.TAB_NHAT_KY: [["Thời gian", "Job ID"]],
}


async def doc_sheet(sid, tab):
    return [r[:] for r in SHEET[tab]]


async def ghi_o(sid, tab, ranges):
    for a1, v in ranges.items():
        col = "".join(ch for ch in a1 if ch.isalpha())
        row = int("".join(ch for ch in a1 if ch.isdigit()))
        rows = SHEET[tab]
        while len(rows) < row:
            rows.append([])
        r = rows[row - 1]
        j = ub.chu_cot(col)
        while len(r) <= j:
            r.append("")
        r[j] = v[0][0]


async def them_dong(sid, tab, row):
    SHEET[tab].append([str(x) for x in row])

PROMPTS = []


async def nhin_anh(paths, prompt):
    PROMPTS.append((paths, prompt))
    return json.dumps({"nhan_dien": "váy lụa dáng suông, cổ V", "content": "VÁY LỤA CỔ V SANG TRỌNG\nGiá 520.000đ - Mã CS009"})

BAO = []


async def bao(the, sk):
    BAO.append((the.get("dong"), sk))


async def token_page(pid):
    return "TOKEN-" + pid

GOI = []


def graph(req: httpx.Request):
    GOI.append((req.method, str(req.url)))
    u = str(req.url)
    if "video_reels" in u:
        body = req.content.decode()
        if "upload_phase=start" in body:
            return httpx.Response(200, json={"video_id": "777", "upload_url": "https://rupload.facebook.com/video-upload/v26.0/777"})
        return httpx.Response(200, json={"success": True})
    if "rupload" in u:
        return httpx.Response(200, json={"success": True})
    if u.startswith(ub.GRAPH + "/777"):
        return httpx.Response(200, json={"status": {"video_status": "ready", "publishing_phase": {"status": "complete"}},
                                         "permalink_url": "/reel/777"})
    return httpx.Response(404, json={"error": {"message": "lạ"}})


goc = Path(tempfile.mkdtemp())
mau_video = goc / "mau.mp4"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=25", "-t", "4",
                "-pix_fmt", "yuv420p", str(mau_video)], check=True)


def tai_gia(link, dich):
    dich.mkdir(parents=True, exist_ok=True)
    p = dich / "goc.mp4"
    shutil.copyfile(mau_video, p)
    return p


ub.tai_video = tai_gia
deps = ub.Deps(doc_sheet=doc_sheet, ghi_o=ghi_o, them_dong=them_dong, nhin_anh=nhin_anh, token_page=token_page,
               bao=bao, http=lambda: httpx.AsyncClient(transport=httpx.MockTransport(graph)),
               thu_muc=goc / "brain" / "attachments" / "up-bai")
up = ub.UpBai(deps, "SHEETID")
loop = asyncio.new_event_loop()

kq = loop.run_until_complete(up.chay_mot_vong())
r4 = SHEET[ub.TAB_HANG_DOI][3]
check("dòng mới: tải, chuẩn hoá, AI viết content, chờ duyệt", kq["xu_ly"] == 1 and r4[11] == ub.TT_CHO_DUYET
      and r4[9].startswith("VÁY LỤA") and "váy lụa" in r4[8], (kq, r4))
check("AI được xem đúng 3 khung hình và prompt có giá + mã + bài mẫu",
      len(PROMPTS[0][0]) == 3 and all(Path(x).exists() for x in PROMPTS[0][0])
      and "520.000đ" in PROMPTS[0][1] and "CS009" in PROMPTS[0][1] and "SALE VÁY CŨ MẪU" in PROMPTS[0][1])
check("báo chủ để duyệt", (4, "cho_duyet") in BAO)
check("dòng không phải link và dòng đã đăng không bị đụng",
      len(SHEET[ub.TAB_HANG_DOI][4]) <= 8 and SHEET[ub.TAB_HANG_DOI][5][11] == "ĐÃ ĐĂNG")
vd = up._tim_video(4, "https://www.tiktok.com/@shop/video/1")
tt = ub.thong_tin_video(vd)
check("video chuẩn hoá đọc được và có tiếng (Reels cần audio)", tt["rong"] == 360 and tt["co_tieng"] and tt["giay"] > 3, tt)

kq = loop.run_until_complete(up.chay_mot_vong())
check("chưa duyệt thì không đăng", kq["dang"] == 0 and not GOI)
check("không duyệt được dòng không ở trạng thái chờ duyệt",
      "không duyệt" in loop.run_until_complete(up.duyet(6, True)))
msg = loop.run_until_complete(up.duyet(4, True))
check("duyệt qua Telegram ghi ĐÃ DUYỆT + CHỜ ĐĂNG", SHEET[ub.TAB_HANG_DOI][3][10] == "ĐÃ DUYỆT"
      and SHEET[ub.TAB_HANG_DOI][3][11] == ub.TT_CHO_DANG, msg)

ub.bay_gio = lambda: datetime(2026, 10, 20, 10, 15, tzinfo=ub.VN)
kq = loop.run_until_complete(up.chay_mot_vong())
r4 = SHEET[ub.TAB_HANG_DOI][3]
check("tới giờ: đăng Reels 3 pha + hậu kiểm, ghi ĐÃ ĐĂNG, video id, link, giờ", kq["dang"] == 1 and r4[11] == ub.TT_DA_DANG
      and r4[12] == "777" and r4[13] == "https://www.facebook.com/reel/777" and r4[0] == "20/10" and r4[1] == "10h15", (kq, r4))
check("upload dùng token của Trang và file thật", any("rupload" in u for _, u in GOI))
check("ghi một dòng NHẬT KÝ thành công", SHEET[ub.TAB_NHAT_KY][-1][5] == "Đăng Reels" and "THÀNH CÔNG" in SHEET[ub.TAB_NHAT_KY][-1][6])
check("báo chủ đã đăng và dọn video tạm", (4, "da_dang") in BAO and up._tim_video(4, "https://www.tiktok.com/@shop/video/1") is None)

# ---- đăng lỗi sau khi đã đẩy video: không đăng lại, ghi cần kiểm tra
SHEET[ub.TAB_HANG_DOI].append(["", "", "Liora Belle", "1159115630616690", "https://www.tiktok.com/@shop/video/2", "", "", "",
                               "", "VÁY B", "ĐÃ DUYỆT", "CHỜ ĐĂNG"])


def graph_loi(req):
    u = str(req.url)
    if "video_reels" in u and "upload_phase=start" in req.content.decode():
        return httpx.Response(200, json={"video_id": "888", "upload_url": "https://rupload.facebook.com/x/888"})
    if "rupload" in u or "video_reels" in u:
        return httpx.Response(200, json={"success": True})
    return httpx.Response(200, json={"status": {"video_status": "error"}})


deps.http = lambda: httpx.AsyncClient(transport=httpx.MockTransport(graph_loi))
ub.bay_gio = lambda: datetime(2026, 10, 20, 11, 5, tzinfo=ub.VN)
kq = loop.run_until_complete(up.chay_mot_vong())
r7 = SHEET[ub.TAB_HANG_DOI][-1]
check("Meta báo lỗi sau khi nhận video: LỖI - CẦN KIỂM TRA TRANG, giữ video id, không tự đăng lại",
      r7[11] == "LỖI - CẦN KIỂM TRA TRANG" and r7[12].startswith("888") and "lỗi" in r7[14].lower(), r7)
kq = loop.run_until_complete(up.chay_mot_vong())
check("dòng lỗi không bị chạy lại", kq["dang"] == 0 and kq["xu_ly"] == 0)

# ---- tự duyệt
SHEET[ub.TAB_HANG_DOI].append(["", "", "Liora Belle", "1159115630616690", "https://www.tiktok.com/@shop/video/3", "", "", ""])
up.tu_duyet = True
kq = loop.run_until_complete(up.chay_mot_vong())
r8 = SHEET[ub.TAB_HANG_DOI][-1]
check("chế độ tự duyệt: viết xong là CHỜ ĐĂNG + ĐÃ DUYỆT", r8[11] == ub.TT_CHO_DANG and r8[10] == "ĐÃ DUYỆT", r8)

# ---- AI trả bậy thì báo lỗi, không đăng
async def ai_bay(paths, prompt):
    return "xin lỗi tôi không xem được"
deps.nhin_anh = ai_bay
SHEET[ub.TAB_HANG_DOI].append(["", "", "Liora Belle", "1159115630616690", "https://www.tiktok.com/@shop/video/4"])
loop.run_until_complete(up.chay_mot_vong())
r9 = SHEET[ub.TAB_HANG_DOI][-1]
check("AI không trả content: LỖI - CHƯA ĐĂNG kèm lý do", r9[11] == "LỖI - CHƯA ĐĂNG" and "AI" in r9[14], r9)

print("ALL PASS" if ok else "SOME FAILED")
sys.exit(0 if ok else 1)
