"""Bounded, session-local reuse of read-only voice answers."""
import re
import time
from collections import OrderedDict
import localefmt

def now():
    return localefmt.now()

MODES = ("fast", "balanced", "thorough")
_CACHE = OrderedDict()

def eligible(request):
    text = str(request).lower().strip()
    if re.search(r"(?:cập nhật|mới nhất|hiện tại|bây giờ|tra lại|kiểm tra lại|gửi|xóa|xoá|tạo|đặt|sửa|mua|chuyển tiền|lưu)", text):
        return False
    return bool(re.search(r"(?:doanh thu|kết quả kinh doanh|báo cáo|chi phí|bao nhiêu|số liệu)", text))

def key(brain, session, request):
    return str(brain), str(session), localefmt.ten_tz(), now().date().isoformat(), " ".join(re.findall(r"[^\W_]+", str(request).lower()))

def get(brain, session, request, mode):
    if mode == "thorough" or not eligible(request):
        return None
    item = _CACHE.get(key(brain, session, request))
    if item and time.monotonic() - item[0] < (900 if mode == "fast" else 120):
        return "Theo kết quả đã lấy lúc " + item[1] + ":\n" + item[2]
    return None

def put(brain, session, request, result):
    if not eligible(request) or not result or re.search(r"lỗi:|không có nội dung|JAVIS_NOOP", result, re.I):
        return
    _CACHE[key(brain, session, request)] = (time.monotonic(), (now().strftime("%H:%M %d/%m") + " " + localefmt.ten_tz()), result)
    while len(_CACHE) > 128:
        _CACHE.popitem(last=False)

def instruction(mode):
    if mode == "fast":
        return ("Trả lời nhanh: dùng đúng số liệu đã có trong ngữ cảnh/báo cáo lưu sẵn nếu khớp ngày và phạm vi; nêu nguồn/thời điểm. "
                "Không quét lại toàn bộ nguồn chỉ để xác nhận lại. Thiếu mục nào mới tra đúng mục đó; không bịa hoặc xem số cũ là số mới. ")
    if mode == "thorough":
        return "Đối chiếu kỹ nguồn và ngày/phạm vi trước khi kết luận; báo rõ phần thiếu hoặc chưa xác minh. "
    return "Ưu tiên kết quả có sẵn đúng ngày/phạm vi; chỉ tra bổ sung phần thiếu hoặc được yêu cầu cập nhật. "
