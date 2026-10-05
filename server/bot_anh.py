"""Ảnh khách gửi cho bot, đưa THẲNG vào lượt chat của model đang chạy bot (26.10.68).

Trước đây ảnh chỉ tới bot qua một đoạn tả do ChatGPT viết hộ, nên bot chạy bằng Claude, Gemini,
Groq... không tự nhìn được ảnh và phụ thuộc vào việc chủ có đăng nhập ChatGPT hay không. Giờ ảnh
đi kèm tin nhắn theo định dạng OpenAI (`image_url` + data URL) cho các engine hiểu nó, và hai
bộ chuyển đổi nhỏ dưới đây đổi sang định dạng của Anthropic và của Responses API (gói ChatGPT).

Chỉ là hàm thuần, không gọi mạng, để test được mà không cần key thật.
"""
import re

# Engine chấp nhận ảnh trong tin nhắn. Model chữ thuần ở các nhà này sẽ từ chối ảnh (HTTP 4xx):
# chỗ gọi phải rơi về đường chữ chứ không để khách mất câu trả lời. Gói Claude Code, Grok Build và
# Antigravity chạy qua binary riêng không nhận ảnh trong tin nhắn nên KHÔNG nằm ở đây.
ENGINE_NHAN_ANH = frozenset({
    "openai", "openrouter", "gemini", "groq", "ollama", "ollama-local", "openai-compat",
    "anthropic-api", "openai-oauth",
})

# Trần cho ảnh gửi thẳng vào lượt chat (byte của file gốc). Ảnh lớn hơn thì dùng đường tả bằng chữ.
TRAN_BYTE = 4 * 1024 * 1024

_DATA_URL = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)


def noi_dung_co_anh(text: str, data_url: str) -> list:
    """Nội dung một tin user có ảnh, định dạng OpenAI Chat Completions."""
    return [{"type": "text", "text": str(text or "")},
            {"type": "image_url", "image_url": {"url": data_url}}]


def co_anh(content) -> bool:
    return isinstance(content, list) and any(
        isinstance(p, dict) and p.get("type") in ("image_url", "image") for p in content)


def chi_chu(content) -> str:
    """Phần chữ của một nội dung, chuỗi hay danh sách đều được."""
    if isinstance(content, list):
        return "\n".join(str(p.get("text") or "") for p in content
                         if isinstance(p, dict) and p.get("type") in ("text", "input_text", "output_text"))
    return str(content or "")


def sang_anthropic(content):
    """Nội dung kiểu OpenAI -> khối nội dung của Anthropic Messages API. Chuỗi giữ nguyên."""
    if not isinstance(content, list):
        return content
    out = []
    for p in content:
        if not isinstance(p, dict):
            continue
        if p.get("type") == "text":
            out.append({"type": "text", "text": str(p.get("text") or "")})
        elif p.get("type") == "image_url":
            url = (p.get("image_url") or {}).get("url") if isinstance(p.get("image_url"), dict) else p.get("image_url")
            m = _DATA_URL.match(str(url or ""))
            if m:
                out.append({"type": "image", "source": {"type": "base64",
                                                        "media_type": m.group(1), "data": m.group(2)}})
        else:
            out.append(p)
    return out


def sang_responses(content):
    """Nội dung user kiểu OpenAI -> danh sách phần của Responses API (gói ChatGPT)."""
    if not isinstance(content, list):
        return None
    out = []
    for p in content:
        if not isinstance(p, dict):
            continue
        if p.get("type") == "text":
            out.append({"type": "input_text", "text": str(p.get("text") or "")})
        elif p.get("type") == "image_url":
            url = (p.get("image_url") or {}).get("url") if isinstance(p.get("image_url"), dict) else p.get("image_url")
            if url:
                out.append({"type": "input_image", "image_url": str(url)})
    return out
