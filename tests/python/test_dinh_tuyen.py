"""26.10.127: định tuyến model theo độ khó (dinh_tuyen.py). THUẦN, không mạng, không model thật.

    python tests/run.py dinh_tuyen
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys

import dinh_tuyen as dt  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:200] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


# ---------- chuẩn hoá ----------
check("bỏ dấu + thường hoá", dt.bo_dau("Phân Tích ĐÃ") == "phan tich da", dt.bo_dau("Phân Tích ĐÃ"))

# ---------- phân loại bằng luật ----------
check("chào hỏi -> nhẹ", dt.phan_loai_luat("chào em")["bac"] == "nhe", dt.phan_loai_luat("chào em"))
check("hỏi giờ -> nhẹ", dt.phan_loai_luat("mấy giờ rồi?")["bac"] == "nhe")
check("câu ngắn vu vơ -> nhẹ", dt.phan_loai_luat("ok em")["bac"] == "nhe")

check("yêu cầu phân tích sâu -> nặng",
      dt.phan_loai_luat("Phân tích chiến lược giá và so sánh với đối thủ, vì sao nên giảm?")["bac"] == "nang",
      dt.phan_loai_luat("Phân tích chiến lược giá và so sánh với đối thủ, vì sao nên giảm?"))
check("debug code -> nặng", dt.phan_loai_luat("Giúp tôi debug lỗi này trong thuật toán sắp xếp")["bac"] == "nang")

# tính toán / đọc dữ liệu: KHÔNG được rơi xuống nhẹ
r_tinh = dt.phan_loai_luat("tính 250000*3 giúp em")
check("toán -> không nhẹ (sàn chính xác)", r_tinh["bac"] in ("vua", "nang"), r_tinh)
r_hd = dt.phan_loai_luat("tháng này mua vào bao nhiêu hoá đơn?")
check("đọc dữ liệu hoá đơn -> không nhẹ", r_hd["bac"] in ("vua", "nang"), r_hd)

# câu trung bình -> vừa (sinh nội dung + câu dài, nhưng không có phân tích sâu)
r_vua = dt.phan_loai_luat("Viết giúp tôi một bài blog giới thiệu shop nước mắm truyền thống, "
                          "giọng thân thiện, có mở bài thân bài kết bài, nhấn vào chất lượng cá cơm "
                          "và quy trình ủ chượp sáu tháng cho khách miền Bắc nhé bạn")
check("câu sinh nội dung dài -> vừa", r_vua["bac"] == "vua", r_vua)

# đính kèm làm nặng thêm
base = dt.phan_loai_luat("xem file này")["diem"]
kem = dt.phan_loai_luat("xem file này", co_dinh_kem=True)["diem"]
check("đính kèm làm tăng điểm", kem > base, (base, kem))

# ---------- đọc bậc từ model phân loại ----------
check("đọc bậc 'nang'", dt.doc_bac_model("Câu này khó, xếp: nang") == "nang")
check("đọc bậc 'nhe' kèm chữ thừa", dt.doc_bac_model("  NHE  ") == "nhe")
check("đồng nghĩa 'đơn giản' -> nhẹ", dt.doc_bac_model("câu này đơn giản thôi") == "nhe")
check("không rõ -> None", dt.doc_bac_model("ừm để xem") is None)

# ---------- chọn model theo bậc + lui bậc ----------
CFG = {"enabled": True, "bac": {
    "nhe": {"provider": "groq", "model": "llama-fast"},
    "vua": {"provider": "openai-oauth", "model": "gpt-mid"},
    "nang": {"provider": "anthropic-cli", "model": "claude-top"}}}
check("bậc nặng -> model top", dt.chon_model(CFG, "nang")["model"] == "claude-top")
check("bậc nhẹ -> model rẻ", dt.chon_model(CFG, "nhe")["provider"] == "groq")

# thiếu bậc nặng -> lui xuống vừa
CFG2 = {"enabled": True, "bac": {"vua": {"provider": "openai-oauth", "model": "gpt-mid"}}}
lui = dt.chon_model(CFG2, "nang")
check("thiếu bậc nặng -> lui về vừa", lui and lui["bac_thuc"] == "vua", lui)
check("không bậc nào cấu hình -> None", dt.chon_model({"bac": {}}, "vua") is None)
check("bậc trống rỗng (thiếu model) bị bỏ qua", dt.chon_model({"bac": {"vua": {"provider": "x"}}}, "vua") is None)

# ---------- quyết định đầu-cuối ----------
check("tắt -> không áp dụng", dt.quyet_dinh("gì cũng được", {"enabled": False})["ap_dung"] is False)
qd = dt.quyet_dinh("Phân tích vì sao doanh thu giảm và đề xuất chiến lược", CFG)
check("bật + câu khó -> áp dụng model nặng", qd["ap_dung"] and qd["model"]["model"] == "claude-top", qd)
qd2 = dt.quyet_dinh("chào em", CFG)
check("bật + câu dễ -> model nhẹ", qd2["ap_dung"] and qd2["model"]["provider"] == "groq", qd2)
check("bật nhưng chưa cấu hình bậc -> không áp dụng (giữ model chính)",
      dt.quyet_dinh("chào", {"enabled": True, "bac": {}})["ap_dung"] is False)


# ---------- 26.10.135: xếp bậc model theo tên ----------
for m, b in {"anthropic/claude-opus-4.1": "nang", "claude-sonnet-4.5": "vua", "claude-haiku-4": "nhe",
             "gpt-5": "nang", "gpt-5-mini": "vua", "gpt-5-nano": "nhe", "o4-mini": "vua",
             "gemini-2.5-pro": "nang", "gemini-2.5-flash": "vua", "gemini-2.5-flash-lite": "nhe",
             "deepseek-r1-distill-llama-8b": "nhe", "qwen/qwen3-235b-a22b": "nang",
             "meta-llama/llama-3.1-8b-instruct:free": "nhe", "aion-labs/aion-3.0": "vua"}.items():
    check(f"bậc {m} = {b}", dt.bac_cua_model(m) == b, dt.bac_cua_model(m))
check("xếp cao cấp lên đầu, nhanh rẻ xuống cuối",
      dt.xep_model(["claude-haiku-4", "claude-sonnet-4.5", "claude-opus-4.1"]) == ["claude-opus-4.1", "claude-sonnet-4.5", "claude-haiku-4"])
check("cùng bậc giữ thứ tự gốc", dt.xep_model(["b-sonnet", "a-sonnet"]) == ["b-sonnet", "a-sonnet"])

check("không dùng gạch dài", "—" not in open(os.path.join(ROOT, "server/dinh_tuyen.py"), encoding="utf-8").read())

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
