"""Cầu nối VieNeu (transport "internal"): giọng đọc tiếng Việt AI, gọi qua API đám mây của VieNeu.

Mỗi kết nối = MỘT tài khoản VieNeu (một khoá API). VieNeu bán theo ký tự, nên khoá nào thì trừ
token của tài khoản đó.

API (docs.vieneu.io/docs/cloud-api, đọc 2026-10-23):
  base   https://api.vieneu.io/api/v1
  header Authorization: Bearer <vn_sk_...>      (tạo ở vieneu.io > Nhà phát triển)
  GET  /voices?engine=v4       {"voices":[{id,name,description,gender,region,engine,kind}]}; danh bạ công khai
  GET  /usage                  mức dùng và số dư của khoá
  POST /audio/speech           body {input, voice, response_format, speed, model}; trả THẲNG byte âm thanh

Quy tắc của VieNeu đáng nhớ: mỗi lần gọi tối thiểu 50 ký tự; id giọng của engine này không dùng được cho
engine khác (gửi sai là 400); khoá `vn_test_` bị giới hạn 100 từ mỗi lần; gói dùng thử 7 ngày có 30 lần
gọi mỗi ngày. Đọc văn bản dài ta tự chia theo câu rồi ghép lại, vì /audio/speech giữ kết nối suốt lúc sinh.

Module này lo phần nói chuyện với VieNeu. Việc LƯU file vào brain nằm ở plugin `vieneu-doc` (kết nối
internal không biết brain nào đang mở).
"""
import io
import re
import wave

import httpx

import ket_noi_api as k

HOST = "https://api.vieneu.io/api/v1"
TEN = "VieNeu"
ENGINE = "v4"
TOI_THIEU = 50           # VieNeu từ chối đoạn ngắn hơn
DOAN_TOI_DA = 1500       # ký tự mỗi lần gọi khi ta tự chia đoạn
TOI_DA_TONG = 20000      # trần cho một lệnh đọc, tránh vô tình đốt cả gói token
DINH_DANG = ("mp3", "wav")
_GIOI = {"nam": "male", "male": "male", "nu": "female", "nữ": "female", "female": "female"}
_VUNG = {"bac": "north", "bắc": "north", "north": "north", "trung": "central", "central": "central",
         "nam": "south", "south": "south"}

TOOLS = [
    k.tool("vieneu_danh_sach_giong",
           "Danh sách giọng đọc VieNeu (hơn 1.000 giọng ba miền). Lọc theo giới tính, miền hoặc từ khoá "
           "trong tên và mô tả. Trả id giọng: đưa đúng id này cho công cụ đọc (javis_vieneu_speak).",
           {"gioi_tinh": {"type": "string", "description": "nam hoặc nu (bỏ trống = cả hai)"},
            "mien": {"type": "string", "description": "bac, trung hoặc nam (bỏ trống = cả ba miền)"},
            "tu_khoa": {"type": "string", "description": "tìm trong tên và mô tả giọng, ví dụ 'trầm', 'kể chuyện'"},
            "limit": {"type": "integer", "description": "số giọng tối đa, mặc định 30, tối đa 100"}}),
    k.tool("vieneu_so_du",
           "Mức dùng và số dư token của khoá VieNeu đang nối (còn bao nhiêu, hạn gói). Gọi trước khi đọc "
           "một bài dài để biết có đủ không."),
]


async def list_tools(spec):
    return TOOLS


def _loi_vieneu(code, body, sec):
    """Biến lỗi của VieNeu thành câu người đọc làm theo được."""
    msg = ""
    if isinstance(body, dict):
        e = body.get("error")
        msg = (e.get("message") if isinstance(e, dict) else e) or body.get("message") or ""
    msg = str(msg or body)[:300]
    goi_y = {
        401: "Khoá API sai hoặc đã bị thu hồi. Tạo khoá mới ở vieneu.io > Nhà phát triển rồi dán lại ở trang Kết nối.",
        403: "Gói token đã hết hoặc hết hạn (hoặc khoá chưa gắn gói). Gia hạn hoặc mua thêm token ở vieneu.io.",
        429: "Chạm giới hạn của gói (mỗi ngày, mỗi tuần hoặc số luồng). Đợi một lúc rồi thử lại.",
        503: "Máy chủ VieNeu tạm chưa có nơi xử lý định dạng này. Thử lại sau ít phút.",
    }.get(code, "")
    return k.giau(f"ERROR: VieNeu {code}: {msg}" + (f". {goi_y}" if goi_y else ""), sec)


async def _get(sec, path, params=None):
    ok, d = await k.goi(TEN, "GET", f"{HOST}{path}", secrets=sec, params=params,
                        headers={"Authorization": f"Bearer {sec['api_key']}"})
    return ok, d


def chia_doan(text, toi_da=DOAN_TOI_DA, toi_thieu=TOI_THIEU):
    """Chia văn bản theo câu thành các đoạn <= toi_da ký tự. Đoạn cuối quá ngắn (< toi_thieu) dồn vào
    đoạn trước, vì VieNeu từ chối đoạn dưới 50 ký tự."""
    t = re.sub(r"[ \t]+", " ", str(text or "")).strip()
    if len(t) <= toi_da:
        return [t] if t else []
    cau = re.split(r"(?<=[.!?…])\s+|\n+", t)
    doan, hien = [], ""
    for c in cau:
        c = c.strip()
        if not c:
            continue
        while len(c) > toi_da:                       # câu dài bất thường: cắt cứng ở khoảng trắng gần nhất
            cat = c.rfind(" ", 0, toi_da)
            cat = cat if cat > toi_da // 2 else toi_da
            if hien:
                doan.append(hien)
                hien = ""
            doan.append(c[:cat].strip())
            c = c[cat:].strip()
        if hien and len(hien) + 1 + len(c) > toi_da:
            doan.append(hien)
            hien = c
        else:
            hien = (hien + " " + c).strip()
    if hien:
        doan.append(hien)
    if len(doan) > 1 and len(doan[-1]) < toi_thieu:
        doan[-2] = doan[-2] + " " + doan[-1]
        doan.pop()
    return doan


def ghep_wav(phan):
    """Ghép nhiều file WAV hoàn chỉnh thành một (nối byte thô sẽ hỏng tiêu đề giữa file)."""
    out = io.BytesIO()
    w = None
    for b in phan:
        with wave.open(io.BytesIO(b), "rb") as r:
            if w is None:
                w = wave.open(out, "wb")
                w.setparams(r.getparams())
            w.writeframes(r.readframes(r.getnframes()))
    if w is not None:
        w.close()
    return out.getvalue()


async def _doc_mot_doan(sec, doan, voice, speed, fmt):
    body = {"model": "vieneu-v4", "input": doan, "response_format": fmt}
    if voice:
        body["voice"] = voice
    if speed:
        body["speed"] = speed
    try:
        async with httpx.AsyncClient(timeout=180) as c:
            r = await c.request("POST", f"{HOST}/audio/speech", json=body,
                                headers={"Authorization": f"Bearer {sec['api_key']}"})
    except Exception as e:
        return False, k.giau(f"ERROR: VieNeu không phản hồi: {type(e).__name__}: {e}", sec)
    if r.status_code >= 400:
        try:
            tra = r.json()
        except ValueError:
            tra = r.text or ""
        return False, _loi_vieneu(r.status_code, tra, sec)
    if not r.content:
        return False, "ERROR: VieNeu trả về file âm thanh rỗng"
    return True, r.content


async def doc_thanh_tieng(sec, text, voice="", speed=None, fmt="mp3"):
    """Văn bản -> (True, byte âm thanh, so_doan, so_ky_tu) hoặc (False, câu lỗi, 0, 0).
    `sec` là map bí mật của kết nối (cần api_key). Dùng bởi plugin vieneu-doc."""
    sec = dict(sec or {})
    if k.thieu(sec, "api_key"):
        return False, "ERROR: kết nối VieNeu thiếu api_key - sửa lại ở trang Kết nối", 0, 0
    sec["api_key"] = str(sec["api_key"]).strip()
    fmt = (fmt or "mp3").lower()
    if fmt not in DINH_DANG:
        return False, f"ERROR: định dạng '{fmt}' chưa hỗ trợ, chọn mp3 hoặc wav", 0, 0
    t = str(text or "").strip()
    if not t:
        return False, "ERROR: thiếu văn bản cần đọc", 0, 0
    if len(t) < TOI_THIEU:
        return False, (f"ERROR: VieNeu chỉ nhận đoạn từ {TOI_THIEU} ký tự trở lên (đang {len(t)}). "
                       "Thêm chữ vào câu cho đủ rồi đọc lại."), 0, 0
    if len(t) > TOI_DA_TONG:
        return False, (f"ERROR: văn bản {len(t):,} ký tự, quá trần {TOI_DA_TONG:,} cho một lệnh đọc "
                       "(để khỏi đốt cả gói token). Chia thành nhiều phần rồi đọc từng phần."), 0, 0
    try:
        sp = float(speed) if speed not in (None, "") else None
    except (TypeError, ValueError):
        return False, "ERROR: tốc độ phải là số từ 0.5 đến 2.0", 0, 0
    if sp is not None:
        if sp != sp or not 0.5 <= sp <= 2.0:
            return False, "ERROR: tốc độ phải nằm trong 0.5 đến 2.0", 0, 0
    phan = []
    doan = chia_doan(t)
    for d in doan:
        ok, b = await _doc_mot_doan(sec, d, str(voice or "").strip(), sp, fmt)
        if not ok:
            hau_qua = f" (đã đọc xong {len(phan)}/{len(doan)} đoạn, phần đã đọc bị bỏ)" if phan else ""
            return False, b + hau_qua, 0, 0
        phan.append(b)
    if len(phan) == 1:
        return True, phan[0], 1, len(t)
    try:
        out = b"".join(phan) if fmt == "mp3" else ghep_wav(phan)
    except Exception as e:
        return False, f"ERROR: không ghép được các đoạn âm thanh: {type(e).__name__}: {e}", 0, 0
    return True, out, len(phan), len(t)


def _loc_giong(ds, a):
    gt = _GIOI.get(str(a.get("gioi_tinh") or "").strip().lower())
    mien = _VUNG.get(str(a.get("mien") or "").strip().lower())
    tk = str(a.get("tu_khoa") or "").strip().lower()
    kq = []
    for v in ds or []:
        if not isinstance(v, dict):
            continue
        if gt and str(v.get("gender") or "").lower() != gt:
            continue
        if mien and str(v.get("region") or "").lower() != mien:
            continue
        if tk and tk not in (str(v.get("name") or "") + " " + str(v.get("description") or "")).lower():
            continue
        kq.append({"id": v.get("id"), "gioi_tinh": v.get("gender"), "mien": v.get("region"),
                   "loai": v.get("kind"), "mo_ta": str(v.get("description") or "")[:100]})
    return kq


async def call(tool, arguments, spec):
    sec = k.bi_mat(spec)
    t = k.thieu(sec, "api_key")
    if t:
        return "ERROR: kết nối VieNeu thiếu " + ", ".join(t) + " - sửa lại ở trang Kết nối"
    sec["api_key"] = str(sec["api_key"]).strip()
    a = arguments or {}
    if tool == "vieneu_danh_sach_giong":
        ok, d = await _get(sec, "/voices", {"engine": ENGINE})
        if not ok:
            return d
        ds = d.get("voices") if isinstance(d, dict) else None
        if not isinstance(ds, list):
            return k.giau(f"ERROR: VieNeu trả danh sách giọng không đúng dạng: {str(d)[:300]}", sec)
        kq = _loc_giong(ds, a)
        gioi_han = k.so(a.get("limit"), 30, 1, 100)
        return k.json_ra({"tong_giong": len(ds), "khop": len(kq), "hien": min(len(kq), gioi_han),
                          "giong": kq[:gioi_han]})
    if tool == "vieneu_so_du":
        ok, d = await _get(sec, "/usage")
        return k.json_ra(d) if ok else d
    return f"ERROR: tool '{tool}' không có trong cầu nối VieNeu"
