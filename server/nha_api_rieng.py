"""nha_api_rieng.py - BẢNG MỘT CHỖ cho bốn bộ não API key riêng: DeepSeek, Qwen, GLM, MiniMax
(26.10.212).

Vì sao có module này thay vì chép tay như xai/meta: mỗi provider API của MinMin phải có mặt ở
chừng hai chục chỗ đăng ký (PROVIDER_DEFS, chọn engine, AGENT_PROVIDERS, bể khoá, việc nền,
nhãn tên, usage, secret...). Chép tay bốn lần là bốn cơ hội sót một chỗ, và chỗ sót thì hỏng
IM LẶNG (usage_index từng vứt dòng của groq/gemini đúng kiểu đó). Nên bốn hãng này mô tả MỘT
LẦN ở đây, mọi chỗ đăng ký đọc bảng này. Thêm hãng thứ năm cùng khuôn = thêm một mục vào NHA.

Cả bốn hãng nói chuẩn OpenAI Chat Completions (Bearer key, /chat/completions, /models), nên
engine dùng lại nguyên `_openai_compat_stream` và `_cc_tool_loop`; thứ khác nhau giữa các hãng
chỉ là: base URL theo vùng, model mặc định, và cách bật/tắt "suy nghĩ".

Base URL: mỗi hãng có bảng VÙNG (quốc tế / Trung Quốc / gói Coding Plan / trả theo lượng) lấy
từ tài liệu CHÍNH HÃNG (nguồn ghi ở từng mục). Chủ chọn vùng trên thẻ; chỗ nào hãng đổi URL mà
MinMin chưa kịp sửa thì chủ tự dán Base URL vào ô phụ của thẻ (`model.<id>_base`), ô đó thắng
mọi thứ. Không đoán cứng một URL rồi bắt chủ chờ bản cập nhật.

Thuần stdlib, KHÔNG import config/engine (config.py import ngược module này để lấy khoá key và
model mặc định, nên vòng import là chết ngay lúc khởi động).
"""
from __future__ import annotations

# Mỗi mục:
#   nhan        nhãn thẻ trên trang Models (giữ đuôi "(API)" như các thẻ API khác)
#   ngan        tên ngắn: nút Telegram, nhãn trong thông báo lỗi, usage
#   key_field   trường trong settings["model"] giữ key chính
#   vung        {mã vùng: (base URL tính tới /v1 hoặc tương đương, nhãn hiển thị)}
#   vung_mac_dinh  vùng dùng khi chủ chưa chọn và tiền tố key không nói gì
#   theo_tien_to   [(tiền tố key, mã vùng)] - tự nhận vùng theo key khi chủ để "Tự động"
#   models      lưới cuối cho ô chọn model (bản LIVE nạp từ {base}/models khi hãng có)
#   suy_nghi    kiểu điều khiển suy nghĩ, xem `payload_suy_nghi`
#   goi_plan    True = hãng bán gói "Coding Plan" có điều khoản chỉ dùng trong công cụ lập trình
NHA: dict = {
    # https://api-docs.deepseek.com/quick_start/pricing (model, base URL, tool calls: cả hai có)
    # https://api-docs.deepseek.com/guides/thinking_mode (thinking enabled/disabled,
    #   reasoning_effort low|high|max, và: có `tools` thì PHẢI gửi lại reasoning_content)
    "deepseek": {
        "nhan": "DeepSeek (API)", "ngan": "DeepSeek", "key_field": "deepseek_api_key",
        "vung": {"quoc-te": ("https://api.deepseek.com", "api.deepseek.com")},
        "vung_mac_dinh": "quoc-te", "theo_tien_to": [],
        "models": ["deepseek-v4-pro", "deepseek-flash"],
        "suy_nghi": "deepseek", "goi_plan": False,
    },
    # https://www.alibabacloud.com/help/en/model-studio/coding-plan (key sk-sp-, model, điều khoản)
    # https://help.aliyun.com/zh/model-studio/coding-plan (bản Trung Quốc: coding.dashscope...)
    # https://www.alibabacloud.com/help/en/model-studio/base-url (DashScope trả theo lượng, key sk-)
    "qwen": {
        "nhan": "Qwen (API)", "ngan": "Qwen", "key_field": "qwen_api_key",
        "vung": {
            "coding-intl": ("https://coding-intl.dashscope.aliyuncs.com/v1", "Coding Plan - quốc tế"),
            "coding-cn": ("https://coding.dashscope.aliyuncs.com/v1", "Coding Plan - Trung Quốc"),
            "intl": ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "Trả theo lượng - Singapore"),
            "us": ("https://dashscope-us.aliyuncs.com/compatible-mode/v1", "Trả theo lượng - Mỹ"),
            "cn": ("https://dashscope.aliyuncs.com/compatible-mode/v1", "Trả theo lượng - Bắc Kinh"),
        },
        # Key Coding Plan có dạng sk-sp-xxxx, key Model Studio thường là sk-xxxx. Hai loại key
        # KHÔNG dùng chéo endpoint (tài liệu nói rõ), nên nhận vùng theo tiền tố là đúng việc,
        # tiền tố dài phải xét trước tiền tố ngắn.
        "vung_mac_dinh": "intl", "theo_tien_to": [("sk-sp-", "coding-intl"), ("sk-", "intl")],
        "models": ["qwen3.7-plus", "qwen3.6-plus", "qwen3.5-plus", "kimi-k2.5", "glm-5", "MiniMax-M2.5"],
        "suy_nghi": "", "goi_plan": True,
    },
    # https://docs.z.ai/devpack/tool/others (Coding Plan: https://api.z.ai/api/coding/paas/v4)
    # https://docs.bigmodel.cn/cn/guide/develop/opencode.md (Trung Quốc: open.bigmodel.cn/.../coding/paas/v4)
    # https://docs.z.ai/devpack/overview (GLM-5.3, GLM-5.3-Flash có trong mọi gói)
    # Endpoint trả theo token (/api/paas/v4) KHÁC endpoint gói: dùng nhầm thì gói không trừ quota.
    "glm": {
        "nhan": "GLM (API)", "ngan": "GLM", "key_field": "glm_api_key",
        "vung": {
            "quoc-te": ("https://api.z.ai/api/coding/paas/v4", "Coding Plan - z.ai quốc tế"),
            "trung-quoc": ("https://open.bigmodel.cn/api/coding/paas/v4", "Coding Plan - bigmodel.cn"),
            "quoc-te-api": ("https://api.z.ai/api/paas/v4", "Trả theo lượng - z.ai"),
            "trung-quoc-api": ("https://open.bigmodel.cn/api/paas/v4", "Trả theo lượng - bigmodel.cn"),
        },
        "vung_mac_dinh": "quoc-te", "theo_tien_to": [],
        "models": ["glm-5.3", "glm-5.3-flash"],
        "suy_nghi": "", "goi_plan": True,
    },
    # https://platform.minimax.io/docs/token-plan/other-tools (quốc tế https://api.minimax.io/v1,
    #   key gói sk-cp-, model MiniMax-M3.1-Flash)
    # https://platform.minimax.cn/docs/api-reference/text-chat-openai (Trung Quốc api.minimax.cn,
    #   /v1/chat/completions, tool function có hỗ trợ, reasoning_content, reasoning_effort
    #   low..max; M3.1-Flash KHÔNG tắt được suy nghĩ). platform.minimaxi.com cũ chuyển hướng về đây.
    "minimax": {
        "nhan": "MiniMax (API)", "ngan": "MiniMax", "key_field": "minimax_api_key",
        "vung": {
            "quoc-te": ("https://api.minimax.io/v1", "Quốc tế - minimax.io"),
            "trung-quoc": ("https://api.minimax.cn/v1", "Trung Quốc - minimax.cn"),
        },
        "vung_mac_dinh": "quoc-te", "theo_tien_to": [],
        "models": ["MiniMax-M3.1-Flash", "MiniMax-M3"],
        "suy_nghi": "minimax", "goi_plan": True,
    },
}

IDS: tuple = tuple(NHA)
KEY_FIELDS: tuple = tuple(NHA[p]["key_field"] for p in IDS)


def co(pid: str) -> bool:
    return pid in NHA


def truong_vung(pid: str) -> str:
    """Trường settings["model"] giữ vùng chủ chọn. "" = Tự động."""
    return f"{pid}_vung"


def truong_base(pid: str) -> str:
    """Trường settings["model"] giữ Base URL chủ tự dán. "" = theo vùng."""
    return f"{pid}_base"


def mac_dinh_settings() -> dict:
    """Các trường mặc định cho config._DEFAULT["model"]."""
    out = {}
    for pid in IDS:
        out[NHA[pid]["key_field"]] = ""
        out[truong_vung(pid)] = ""
        out[truong_base(pid)] = ""
    return out


def chuan_base(url: str) -> str:
    """Base URL sạch: bỏ khoảng trắng, gạch chéo cuối, và đuôi /chat/completions nếu chủ dán
    nguyên URL chat (cùng cách `engine.openai_compat_base` đã xử lý)."""
    u = str(url or "").strip().rstrip("/")
    if u.endswith("/chat/completions"):
        u = u[: -len("/chat/completions")].rstrip("/")
    return u


def base_hop_le(url: str) -> bool:
    u = chuan_base(url)
    return u.startswith(("https://", "http://")) and len(u) > 10 and " " not in u


def vung_tu_dong(pid: str, key: str = "") -> str:
    """Vùng khi chủ để "Tự động": theo tiền tố key, không khớp thì vùng mặc định."""
    d = NHA[pid]
    k = str(key or "").strip()
    for tien_to, vung in d.get("theo_tien_to") or []:
        if k.startswith(tien_to):
            return vung
    return d["vung_mac_dinh"]


def vung_hieu_luc(pid: str, mcfg: dict | None = None, key: str | None = None) -> str:
    d = NHA[pid]
    m = mcfg or {}
    v = str(m.get(truong_vung(pid)) or "").strip()
    if v in d["vung"]:
        return v
    return vung_tu_dong(pid, m.get(d["key_field"]) if key is None else key)


def base_url(pid: str, mcfg: dict | None = None, key: str | None = None) -> str:
    """Base URL hiệu lực: ô Base URL chủ dán > vùng chủ chọn > vùng theo tiền tố key > mặc định.

    `key` truyền riêng khi đang xoay bể khoá: key dự phòng có thể khác loại key chính (một key
    sk-sp- nằm cạnh một key sk-), mà mỗi loại chỉ chạy được ở endpoint của nó."""
    m = mcfg or {}
    tay = chuan_base(m.get(truong_base(pid)) or "")
    if tay and base_hop_le(tay):
        return tay
    return NHA[pid]["vung"][vung_hieu_luc(pid, m, key)][0]


def chat_url(pid: str, mcfg: dict | None = None, key: str | None = None) -> str:
    return base_url(pid, mcfg, key) + "/chat/completions"


def models_url(pid: str, mcfg: dict | None = None, key: str | None = None) -> str:
    return base_url(pid, mcfg, key) + "/models"


def model_mac_dinh(pid: str) -> str:
    return NHA[pid]["models"][0]


def nhan(pid: str) -> str:
    return NHA[pid]["nhan"] if pid in NHA else pid


def ten_ngan(pid: str) -> str:
    return NHA[pid]["ngan"] if pid in NHA else pid


def provider_defs() -> list:
    """Mục cho main.PROVIDER_DEFS, cùng khuôn các thẻ API khác."""
    return [{"id": pid, "label": NHA[pid]["nhan"], "kind": "api", "key_field": NHA[pid]["key_field"],
             "catalog_key": pid, "default_models": list(NHA[pid]["models"])} for pid in IDS]


def catalog_mac_dinh() -> dict:
    return {pid: list(NHA[pid]["models"]) for pid in IDS}


# Nấc suy nghĩ của MinMin (off|low|medium|high|xhigh|ultra) -> tham số của từng hãng.
_DEEPSEEK_EFFORT = {"low": "low", "medium": "high", "high": "high", "xhigh": "max", "ultra": "max"}
_MINIMAX_EFFORT = {"low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh", "ultra": "max"}


def payload_suy_nghi(pid: str, model: str, reasoning: str) -> dict:
    """Phần payload điều khiển suy nghĩ, gắn vào MỌI request của hãng (stream lẫn vòng tool).

    - DeepSeek: suy nghĩ BẬT sẵn ở mức high. Nấc "off" của MinMin nghĩa là "trả lời nhanh như
      cũ" nên tắt hẳn (`thinking: disabled`) - vừa rẻ vừa tránh luật "có tools thì phải gửi lại
      reasoning_content" với những tin cũ trong lịch sử không còn giữ phần đó. Nấc khác thì bật
      và đặt `reasoning_effort` (low|high|max, theo bảng quy đổi của chính DeepSeek).
    - MiniMax: M3.1-Flash KHÔNG tắt được suy nghĩ (gửi `disabled` là 400) và mặc định ở mức
      max - chậm. "off" quy về `low`, mức thấp nhất hãng nhận; model khác bỏ qua trường này.
    - Qwen, GLM: không gửi gì, để mặc định của hãng. CHƯA ĐO trên key thật: tham số bật/tắt
      suy nghĩ của hai hãng khác nhau theo từng model trong gói (gói Qwen chở cả GLM, Kimi,
      MiniMax), gửi sai một trường là 400 cho cả lượt - thà để mặc định còn hơn.
    """
    kieu = NHA.get(pid, {}).get("suy_nghi")
    r = reasoning or "off"
    if kieu == "deepseek":
        if r == "off":
            return {"thinking": {"type": "disabled"}}
        return {"thinking": {"type": "enabled"}, "reasoning_effort": _DEEPSEEK_EFFORT.get(r, "high")}
    if kieu == "minimax":
        return {"reasoning_effort": _MINIMAX_EFFORT.get(r, "low")}
    return {}


def lui_khi_400(pid: str) -> dict:
    """Payload thay thế để thử lại MỘT lần khi hãng trả 400 vì reasoning_content.

    DeepSeek bản suy nghĩ đòi mọi tin assistant trước đó gửi lại reasoning_content khi request
    có `tools`. Tin trong cùng lượt thì `_tin_goi_tool` đã giữ; tin của các lượt TRƯỚC thì MinMin
    chỉ lưu phần chữ. Gặp 400 đó thì tắt suy nghĩ cho phần còn lại của lượt: trả lời được vẫn
    hơn chết lượt. Hãng khác không có luật này nên trả {}."""
    if NHA.get(pid, {}).get("suy_nghi") == "deepseek":
        return {"thinking": {"type": "disabled"}, "reasoning_effort": None}
    return {}


def cho_giao_dien(pid: str, mcfg: dict | None = None) -> dict:
    """Phần riêng của thẻ trên trang Models: vùng, Base URL hiệu lực, cờ gói Coding Plan."""
    d = NHA[pid]
    m = mcfg or {}
    return {
        "vung": [{"id": v, "nhan": n, "url": u} for v, (u, n) in d["vung"].items()],
        "vung_chon": str(m.get(truong_vung(pid)) or "") if str(m.get(truong_vung(pid)) or "") in d["vung"] else "",
        "vung_tu_dong": vung_tu_dong(pid, m.get(d["key_field"]) or ""),
        "base_tay": chuan_base(m.get(truong_base(pid)) or ""),
        "base_hieu_luc": base_url(pid, m),
        "goi_plan": bool(d.get("goi_plan")),
        "key_field": d["key_field"],
    }
