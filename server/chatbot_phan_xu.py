"""Bộ phán xử của bot trong NHÓM: có nên mở miệng ở tin này không.

Chế độ `reply_when = "judge"` (Tự phán đoán). Bot đọc vài tin gần nhất rồi chấm điểm một tin
khách KHÔNG gọi tên bot. Đủ điểm thì nói, không đủ thì im. Mọi quyết định, kể cả im, đều được
ghi lại kèm LÝ DO để chủ xem trên Hộp thư; chủ bấm Đúng/Sai thì ngưỡng của riêng nhóm đó lệch
đi một nấc.

Thiết kế riêng của MinMin, khác cách "hỏi một model nhỏ" ở chỗ: chấm bằng luật, KHÔNG tốn
một lượt gọi model cho mỗi tin trong nhóm đông (nhóm 200 người nhắn cả ngày sẽ đốt token vô
ích, và model chậm làm bot trả lời trễ). Luật đọc được, giải thích được từng điểm, test được.

Điểm cộng/trừ:
  + tin hỏi (dấu ?, từ hỏi, từ mua bán: giá, còn hàng, size, ship...)
  + bot vừa nói trong vài tin gần đây và đây là người bot vừa trả lời (đang nói tiếp)
  - tin xã giao ngắn (ok, dạ, cảm ơn, haha...)
  - nhắc người khác bằng @ (khách đang nói với nhau)
  - bot vừa nói chưa lâu (nguội giọng, tránh dồn dập)
  - hai người khách đang đối đáp qua lại, không có câu hỏi
"""
from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from typing import Any, Dict, List, Tuple

from config import STATE_DIR

THU_MUC = STATE_DIR / "chatbot-phan-xu"
NGUONG_GOC = 3          # đủ từ chừng này điểm trở lên thì nói
LECH_TOI_DA = 3         # chủ chỉnh ngưỡng của một nhóm tối đa +3 (kín hơn)
LECH_TOI_THIEU = -2     # và tối thiểu -2 (xởi lởi hơn)
GIAY_NGUOI_GIONG = 25   # bot vừa nói trong chừng này giây thì nén lại
MAX_NHAT_KY = 300       # trần số quyết định lưu mỗi bot
_LA_BOT = ("ai", "bot")
_lock = threading.Lock()
_NHO: Dict[tuple, tuple] = {}   # (bot, chat, khoá tin) -> (ts, kết quả): precheck và answer dùng chung

_TU_HOI = ("bao nhieu", "gia", "con hang", "con khong", "het hang", "size", "mau", "ship",
           "giao", "phi", "mua", "dat", "doi tra", "bao hanh", "khuyen mai", "giam gia",
           "tu van", "the nao", "sao", "nhu nao", "o dau", "khi nao", "may gio", "co khong",
           "duoc khong", "bao lau", "chuyen khoan", "thanh toan", "dia chi")
_XA_GIAO = {"ok", "oke", "okie", "da", "vang", "uh", "um", "uhm", "haha", "hihi", "hehe", "kkk",
            "cam on", "thanks", "thank", "oki", "dc", "duoc", "roi", "nhe", "nha", "a", "ah",
            "vay ha", "the a", "ua", "uk"}


# Dấu hiệu khách bức xúc / khiếu nại (không dấu, chữ thường). Bot trả lời ở chỗ này là rủi ro
# lớn nhất của chế độ tự phán đoán: một câu máy móc trước mặt cả nhóm khi khách đang giận làm
# mọi thứ tệ hơn, nên bot im và báo CHỦ.
_TU_KHIEU_NAI = ("lua dao", "lua dot", "lua dao", "hoan tien", "tra hang", "hang loi", "hang hu",
                 "hang kem", "khong hai long", "that vong", "buc minh", "buc xuc", "khieu nai",
                 "bao cong an", "to cao", "bom hang", "chua nhan duoc hang", "chua thay hang",
                 "giao sai", "gui sai", "mat tien", "te qua", "te hai", "lam an kieu gi",
                 "coi thuong khach", "khong ai tra loi", "bao gio moi", "toi se review")


def la_khieu_nai(text: str) -> bool:
    k = _bo_dau(text)
    return any(re.search(r"(^|\W)" + re.escape(w) + r"(\W|$)", k) for w in _TU_KHIEU_NAI)


def _bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower().replace("đ", "d"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _la_xa_giao(t: str) -> bool:
    k = re.sub(r"[^a-z0-9 ]", "", _bo_dau(t)).strip()
    if not k:
        return True
    if len(k) <= 3 and "?" not in t:
        return True
    return all(w in _XA_GIAO for w in k.split()) and len(k.split()) <= 4


def cham_diem(text: str, ngu_canh: List[dict], *, bay_gio: float = 0.0,
              lech: int = 0) -> Tuple[bool, int, List[str]]:
    """(nên nói?, điểm, các lý do). `ngu_canh` cũ trước mới sau, KHÔNG gồm tin đang xét.
    Hàm thuần: không đụng đĩa, không đụng mạng."""
    t = str(text or "").strip()
    k = _bo_dau(t)
    diem, ly = 0, []
    if "?" in t or "？" in t:
        diem += 2
        ly.append("có dấu hỏi (+2)")
    elif any(re.search(r"(^|\W)" + re.escape(w) + r"(\W|$)", k) for w in _TU_HOI):
        diem += 2
        ly.append("có từ hỏi/mua bán (+2)")
    if len(t) >= 25:
        diem += 1
        ly.append("câu đủ dài để là một câu hỏi thật (+1)")
    if _la_xa_giao(t):
        diem -= 3
        ly.append("tin xã giao ngắn (-3)")
    if re.search(r"@\S+", t):
        diem -= 2
        ly.append("đang nhắc người khác bằng @ (-2)")
    cuoi = [m for m in (ngu_canh or [])][-6:]
    bot_gan = [m for m in cuoi if m.get("sender_type") in _LA_BOT]
    if bot_gan:
        ts = float(bot_gan[-1].get("created_at") or bot_gan[-1].get("ts") or 0)
        if bay_gio and ts and bay_gio - ts < GIAY_NGUOI_GIONG:
            diem -= 2
            ly.append("bot vừa nói xong, nén giọng (-2)")
        elif cuoi and cuoi[-1].get("sender_type") in _LA_BOT or (
                len(cuoi) >= 2 and cuoi[-2].get("sender_type") in _LA_BOT):
            diem += 2
            ly.append("đang nói tiếp ngay sau câu của bot (+2)")
    khach = [str(m.get("sender_id") or m.get("sender_name") or "")
             for m in cuoi if m.get("sender_type") == "customer"]
    if len(khach) >= 3 and len(set(khach[-3:])) >= 2 and "?" not in t and not bot_gan:
        diem -= 1
        ly.append("khách đang đối đáp với nhau (-1)")
    nguong = NGUONG_GOC + int(lech or 0)
    return diem >= nguong, diem, ly


def _file(bot_id: str):
    an = re.sub(r"[^A-Za-z0-9_-]", "", str(bot_id or ""))[:64] or "khong-ten"
    return THU_MUC / f"{an}.json"


def _doc(bot_id: str) -> dict:
    try:
        d = json.loads(_file(bot_id).read_text("utf-8"))
        if isinstance(d, dict):
            d.setdefault("lech", {})
            d.setdefault("nhat_ky", [])
            return d
    except Exception:
        pass
    return {"lech": {}, "nhat_ky": []}


def _luu(bot_id: str, d: dict) -> None:
    try:
        THU_MUC.mkdir(parents=True, exist_ok=True)
        d["nhat_ky"] = d["nhat_ky"][-MAX_NHAT_KY:]
        tmp = _file(bot_id).with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False), "utf-8")
        tmp.replace(_file(bot_id))
    except Exception:
        pass    # nhật ký hỏng không được làm gãy câu trả lời


def quyet_dinh(bot_id: str, chat_id: str, text: str, ngu_canh: List[dict],
               khoa_tin: str = "", ten_nhom: str = "") -> dict:
    """Quyết định + ghi nhật ký. Cùng một tin hỏi hai lần (precheck rồi answer) chỉ ghi một."""
    bay_gio = time.time()
    khoa = (str(bot_id), str(chat_id), str(khoa_tin or text)[:200])
    with _lock:
        c = _NHO.get(khoa)
        if c and bay_gio - c[0] < 60:
            return c[1]
        if len(_NHO) > 500:
            _NHO.clear()
        d = _doc(bot_id)
        lech = int(d["lech"].get(str(chat_id), 0))
        noi, diem, ly = cham_diem(text, ngu_canh, bay_gio=bay_gio, lech=lech)
        khieu_nai = la_khieu_nai(text)
        if khieu_nai:
            noi = False
            ly.append("khách có dấu hiệu bức xúc/khiếu nại: bot im, để chủ xử lý")
        if lech:
            ly.append(f"ngưỡng nhóm này đã chỉnh {lech:+d} theo phản hồi của chủ")
        kq = {"noi": noi, "diem": diem, "ly_do": ly, "id": int(bay_gio * 1000), "khieu_nai": khieu_nai}
        d["nhat_ky"].append({"id": kq["id"], "ts": bay_gio, "chat_id": str(chat_id),
                             "nhom": str(ten_nhom or "")[:80], "tin": str(text or "")[:300],
                             "noi": noi, "diem": diem, "ly_do": ly, "phan_hoi": "", "khieu_nai": khieu_nai})
        _luu(bot_id, d)
        _NHO[khoa] = (bay_gio, kq)
        return kq


def nhat_ky(bot_id: str, n: int = 50) -> List[dict]:
    with _lock:
        return list(reversed(_doc(bot_id)["nhat_ky"][-max(1, min(int(n or 50), MAX_NHAT_KY)):]))


def phan_hoi(bot_id: str, quyet_dinh_id: int, dung: bool) -> dict:
    """Chủ bấm Đúng/Sai. Sai khi bot nói -> nhóm đó kín hơn; sai khi bot im -> xởi lởi hơn.
    Mỗi quyết định chỉ chấm một lần để bấm nhầm hai lần không đẩy ngưỡng đi xa."""
    with _lock:
        d = _doc(bot_id)
        for r in d["nhat_ky"]:
            if r.get("id") == int(quyet_dinh_id):
                if r.get("phan_hoi"):
                    return {"ok": False, "ly_do": "da_cham"}
                r["phan_hoi"] = "dung" if dung else "sai"
                if not dung:
                    cid = str(r.get("chat_id") or "")
                    cu = int(d["lech"].get(cid, 0))
                    moi = cu + (1 if r.get("noi") else -1)
                    d["lech"][cid] = max(LECH_TOI_THIEU, min(LECH_TOI_DA, moi))
                _luu(bot_id, d)
                return {"ok": True, "lech": d["lech"].get(str(r.get("chat_id")), 0)}
    return {"ok": False, "ly_do": "khong_thay"}


def quen_het(bot_id: str, chat_id: str = "") -> None:
    """Xoá ngưỡng đã học (một nhóm, hoặc tất cả)."""
    with _lock:
        d = _doc(bot_id)
        if chat_id:
            d["lech"].pop(str(chat_id), None)
        else:
            d["lech"] = {}
        _luu(bot_id, d)
