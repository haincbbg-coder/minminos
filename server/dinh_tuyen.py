"""dinh_tuyen.py - ĐỊNH TUYẾN MODEL THEO ĐỘ KHÓ CÂU HỎI (26.10.127).

Ý tưởng của chủ repo (10/10): câu dễ thì để model RẺ trả lời, câu khó/cần phân tích sâu/cần
chính xác thì mới gọi model MẠNH. Một cuộc hội thoại có thể luân phiên nhiều model mà câu trả
lời vẫn đảm bảo - việc này đã chạy được sẵn ở tầng dữ liệu (lịch sử chat là văn bản thuần, mỗi
lượt dựng lại và chọn provider mới), nên định tuyến chỉ là CHỌN provider cho lượt sắp tới.

File này THUẦN (chỉ stdlib), KHÔNG import main/engine, nên test trọn vẹn không cần mạng hay key.
Phần nối vào lượt chat thật nằm ở main.py (đọc cờ bật, gọi `quyet_dinh`, ghi đè provider nếu
phiên CHƯA ghim tay).

Hai chế độ phân loại:
  - "luat" (mặc định): chấm độ khó bằng LUẬT, tất định, không tốn thêm một lượt gọi model nào.
    Đây là lựa chọn rẻ nhất và nhanh nhất.
  - "model": để một model RẺ đọc câu hỏi rồi tự xếp bậc (nhe|vua|nang). Dùng khi muốn đúng ý
    "dùng Claude để chia model" - nhưng tốn thêm một lượt gọi. Module này chỉ lo phần ĐỌC kết
    quả model trả về (`doc_bac_model`); việc gọi model là của main.py.

An toàn: định tuyến chỉ đổi NÃO trả lời, không đổi quyền hạn hay dữ liệu. Bộ chấm điểm não
(danh_gia.py) là lưới an toàn: bật định tuyến xong chạy kiểm tra là biết ngay chất lượng có
tụt không.

Config nằm ở settings.json -> model.auto_router:
    {
      "enabled": false,
      "che_do": "luat",
      "model_phan_loai": {"provider": "groq", "model": "..."},   # cho che_do="model"
      "bac": {
        "nhe":  {"provider": "...", "model": "..."},
        "vua":  {"provider": "...", "model": "..."},
        "nang": {"provider": "...", "model": "..."}
      }
    }
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

BAC = ("nhe", "vua", "nang")   # nhẹ -> vừa -> nặng (rẻ -> đắt)

# Ngưỡng điểm -> bậc. Giữ ở một chỗ để test và chỉnh cùng một nơi.
NGUONG_NANG = 4
NGUONG_VUA = 2

# ─────────────────────────── chuẩn hoá ───────────────────────────


def bo_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt + chữ thường, để so khớp từ khoá không kẹt vì dấu."""
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "d").lower()


# Từ khoá kéo câu hỏi lên bậc NẶNG (phân tích, suy luận, lập trình, chiến lược...).
_TU_NANG = (
    "phan tich", "so sanh", "vi sao", "tai sao", "chien luoc", "danh gia", "toi uu",
    "chung minh", "lap luan", "thiet ke", "kien truc", "thuat toan", "du bao", "mo hinh",
    "giai thich", "chi tiet", "tung buoc", "step by step", "debug", "sua loi", "refactor",
    "analyze", "compare", "strategy", "optimize", "explain why", "design", "architecture",
    "proof", "reasoning", "root cause", "nguyen nhan", "ke hoach", "roadmap", "weigh",
)
# Dấu hiệu TÍNH TOÁN / cần chính xác con số: không được đẩy xuống model rẻ nhất.
_TU_TINH = (
    "tinh", "tong", "trung binh", "phan tram", "chiet khau", "lai suat", "doanh thu",
    "chi phi", "loi nhuan", "cong no", "bao nhieu tien", "calculate", "sum", "average",
    "percent", "revenue", "profit", "margin",
)
# Dấu hiệu cần đọc DỮ LIỆU thật (nhạy cảm với bịa số) -> sàn tối thiểu là VỪA.
_TU_DU_LIEU = ("hoa don", "bao cao", "thong ke", "bao nhieu", "invoice", "report", "how many")
# Sinh NỘI DUNG (viết bài, mô tả, email...): không khó về chính xác nhưng chất lượng câu chữ
# được lợi từ model khá hơn -> nhích nhẹ, đủ dài thì lên VỪA.
_TU_NOI_DUNG = ("viet", "soan", "mo ta", "noi dung", "content", "bai viet", "caption",
                "email", "tin nhan", "bai blog", "kich ban", "quang cao")
# Chào hỏi / câu vặt -> NHẸ.
_TU_NHE = (
    "chao", "cam on", "thanks", "thank you", "hello", "hi ", "oke", "okay", "ok",
    "may gio", "gio roi", "hom nay la thu", "hom nay ngay", "what time", "good morning",
)
# Toán thực thụ: hai cụm chữ số có toán tử ở giữa (vd "250000*3", "2000000 - 15%").
_RE_TOAN = re.compile(r"\d[\d.,]*\s*[-+*/x×%=]\s*\d")


def _co(text_bd: str, tu) -> bool:
    return any(k in text_bd for k in tu)


def phan_loai_luat(text: str, *, co_dinh_kem: bool = False, co_lich_su: bool = False) -> dict:
    """Chấm độ khó câu hỏi bằng LUẬT -> {"bac", "diem", "ly_do"}.

    Tất định, không gọi model. `co_dinh_kem` = có file đính kèm (đọc file nặng hơn);
    `co_lich_su` = đã có lịch sử dài (ngữ cảnh nhiều, nhích nhẹ độ khó).
    """
    raw = str(text or "")
    bd = bo_dau(raw)
    tu = [w for w in re.split(r"\s+", bd) if w]
    so_tu = len(tu)
    ly = []
    diem = 0

    # Đếm SỐ từ khoá phân tích khác nhau: một câu nhắc "phân tích", "so sánh", "vì sao" cùng lúc
    # thì rõ là việc nặng, nặng hơn câu chỉ chạm một từ. Mỗi từ +2, trần 6 để một câu dày từ
    # khoá không nuốt hết thang điểm.
    so_nang = sum(1 for k in _TU_NANG if k in bd)
    if so_nang:
        diem += min(so_nang * 2, 6); ly.append(f"phan-tich-x{so_nang}")
    co_tinh = _co(bd, _TU_TINH) or bool(_RE_TOAN.search(raw))
    if co_tinh:
        diem += 2; ly.append("tinh-toan")
    co_du_lieu = _co(bd, _TU_DU_LIEU)
    if co_du_lieu:
        diem += 1; ly.append("doc-du-lieu")
    if _co(bd, _TU_NOI_DUNG):
        diem += 1; ly.append("sinh-noi-dung")
    if so_tu > 60:
        diem += 2; ly.append("cau-rat-dai")
    elif so_tu > 30:
        diem += 1; ly.append("cau-dai")
    if raw.count("?") >= 2:
        diem += 1; ly.append("nhieu-cau-hoi")
    if raw.count("\n") >= 3:
        diem += 1; ly.append("nhieu-dong")
    if co_dinh_kem:
        diem += 2; ly.append("co-dinh-kem")
    if co_lich_su:
        diem += 1; ly.append("ngu-canh-dai")

    # Câu rất ngắn, không dấu hiệu khó nào -> NHẸ thẳng (chào hỏi, câu vặt).
    ngan_va_de = so_tu <= 5 and diem == 0
    if ngan_va_de or (_co(bd, _TU_NHE) and diem == 0):
        return {"bac": "nhe", "diem": diem, "ly_do": ["cau-ngan-de"] if ngan_va_de else ["chao-hoi"]}

    if diem >= NGUONG_NANG:
        bac = "nang"
    elif diem >= NGUONG_VUA:
        bac = "vua"
    else:
        bac = "nhe"

    # SÀN AN TOÀN: tính toán hoặc đọc dữ liệu thì tối thiểu VỪA, không bao giờ dồn xuống model
    # rẻ nhất - sai một con số tiền là hỏng việc, đắt hơn nhiều so với tiền tiết kiệm được.
    if (co_tinh or co_du_lieu) and bac == "nhe":
        bac = "vua"; ly.append("san-chinh-xac")

    return {"bac": bac, "diem": diem, "ly_do": ly or ["mac-dinh"]}


def doc_bac_model(cau_tra_loi: str) -> Optional[str]:
    """Đọc bậc (nhe|vua|nang) từ câu trả lời của model phân loại (chế độ 'model').

    Model được dặn trả về đúng một từ, nhưng thực tế hay kèm chữ thừa nên bắt lỏng: tìm từ
    bậc đầu tiên xuất hiện. Không nhận ra -> None (main.py sẽ lui về chấm bằng luật)."""
    bd = bo_dau(cau_tra_loi)
    vi = {b: bd.find(b) for b in BAC if b in bd}
    if vi:
        return min(vi, key=vi.get)
    # Vài từ đồng nghĩa hay gặp. TRÁNH "de" trần: bỏ dấu thì "dễ" (easy) và "để" (to/let) đều
    # ra "de", bắt nhầm liên miên; nên chỉ nhận cụm rõ nghĩa, còn từ đơn thì khớp theo TOKEN.
    tok = set(re.split(r"\s+", bd))
    if "don gian" in bd or (tok & {"easy", "simple"}):
        return "nhe"
    if "phuc tap" in bd or (tok & {"kho", "hard", "complex"}):
        return "nang"
    return None


def _hop_le(m: Optional[dict]) -> bool:
    return bool(m and (m.get("provider") or "").strip() and (m.get("model") or "").strip())


def chon_model(router_cfg: dict, bac: str) -> Optional[dict]:
    """Bậc -> {"provider","model"} theo cấu hình, có LUI BẬC nếu bậc đó chưa cấu hình.

    Lui xuống trước (nặng->vừa->nhẹ) vì model thấp hơn vẫn trả lời được, chỉ kém sắc; nếu
    dưới cũng trống thì thử lên. Không có bậc nào cấu hình -> None (dùng model chính như cũ)."""
    bac_cfg = (router_cfg or {}).get("bac") or {}
    if bac not in BAC:
        bac = "vua"
    i = BAC.index(bac)
    thu_tu = [bac] + [BAC[j] for j in range(i - 1, -1, -1)] + [BAC[j] for j in range(i + 1, len(BAC))]
    for b in thu_tu:
        m = bac_cfg.get(b)
        if _hop_le(m):
            return {"provider": m["provider"].strip(), "model": m["model"].strip(), "bac_thuc": b}
    return None


def quyet_dinh(text: str, router_cfg: dict, *, co_dinh_kem: bool = False,
               co_lich_su: bool = False) -> dict:
    """Quyết định định tuyến cho MỘT lượt (chế độ LUẬT).

    Trả về {"ap_dung": bool, "bac": str|None, "model": {provider,model}|None, "ly_do": str}.
    `ap_dung=False` nghĩa là giữ nguyên model chính (tắt, hoặc không có bậc nào cấu hình).
    Chế độ 'model' do main.py lo phần gọi model rồi đưa bậc qua `chon_model` trực tiếp."""
    if not (router_cfg or {}).get("enabled"):
        return {"ap_dung": False, "bac": None, "model": None, "ly_do": "tat"}
    pl = phan_loai_luat(text, co_dinh_kem=co_dinh_kem, co_lich_su=co_lich_su)
    m = chon_model(router_cfg, pl["bac"])
    if not m:
        return {"ap_dung": False, "bac": pl["bac"], "model": None, "ly_do": "chua-cau-hinh-bac"}
    return {"ap_dung": True, "bac": pl["bac"], "model": m,
            "ly_do": "+".join(pl["ly_do"]), "diem": pl["diem"]}


# ─────────────────────────── xếp bậc MODEL theo tên ───────────────────────────
# Chủ repo 10/10: trong hộp chọn model, mỗi nhà phải xếp từ CAO CẤP xuống THẤP và nói model
# nào hợp việc nào. Đoán bậc từ TÊN model (không có bảng giá nào chung cho 10 nhà), đủ đúng
# cho các dòng phổ biến; model lạ về "vua". Cùng thang nhe/vua/nang với auto-router ở trên.

_DAU_NHE = ("haiku", "nano", "lite", "micro", "tiny", ":free", "-free", "flash-8b",
            "-1b", "-2b", "-3b", "-4b", "-7b", "-8b", "-9b", "-12b", "-14b")
_DAU_NANG = ("opus", "ultra", "-pro", "pro-", "large", "-max", "max-", "thinking", "reason",
             "-405b", "-235b", "-480b", "-671b", "deepseek-r1", "grok-4", "gpt-4.1", "gpt-4.5",
             "gpt-5", "o1", "o3", "o4", "sol",
             # Hàng đầu của bốn nhà API riêng (26.10.212); bản -flash cùng dòng bị loại ở dưới.
             "glm-5", "minimax-m3", "qwen3.7-plus")
# "gpt-5-mini", "o4-mini", "r1-distill" không phải bậc nặng. Khớp theo RANH GIỚI TỪ: "gemini"
# cũng chứa "mini" mà gemini-2.5-pro là bậc nặng thật.
_RE_NANG_TRU = re.compile(r"(^|[-_.:/ ])(mini|nano|distill|lite|flash)([-_.:/ ]|$)")


def bac_cua_model(model_id: str) -> str:
    """nhe | vua | nang theo tên model. Thứ tự xét: nhẹ trước (haiku/nano/lite/:free), rồi
    nặng (opus/pro/ultra/gpt-5/o3...) trừ khi mang dấu mini/nano/distill, còn lại là vừa."""
    s = str(model_id or "").lower().strip()
    ten = s.rsplit("/", 1)[-1]           # "anthropic/claude-opus-4" -> "claude-opus-4"
    if any(k in ten for k in _DAU_NHE):
        return "nhe"
    if any(k in ten for k in _DAU_NANG) and not _RE_NANG_TRU.search(ten):
        return "nang"
    return "vua"


_THU_TU_BAC = {"nang": 0, "vua": 1, "nhe": 2}


def xep_model(ids: list) -> list:
    """Sắp danh sách model: cao cấp lên đầu, nhanh-rẻ xuống cuối; trong cùng bậc giữ thứ tự
    gốc (danh sách mặc định của nhà thường đã xếp mới trước)."""
    return sorted(list(ids or []), key=lambda m: _THU_TU_BAC[bac_cua_model(m)])
