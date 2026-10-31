"""Engine cho VIỆC NỀN (loop, việc Kanban, nhắc hẹn, tự học, tiêu hoá nguồn).

Trước đây việc nền luôn chạy bằng Claude Code, ô chọn ở trang Model bị khoá cứng vào
danh sách model của provider 'anthropic-cli' - muốn đẩy việc nền sang gói ChatGPT hay
một API rẻ để đỡ hạn mức Claude thì không có đường. Module này mở đường đó.

Cách nối vào (cố ý ít xâm lấn): các nơi chạy nền VẪN dựng engine Claude y như cũ, kèm
đủ allowlist/mode/MCP mà chúng vốn tính toán; xong xuôi mới gọi `swap()`. Nếu người dùng
để mặc định Claude thì `swap()` trả lại đúng engine đó, không đổi gì. Chọn provider khác
thì `swap()` đọc chính các thuộc tính engine Claude đã tính (system_prompt, cwd, vault,
mode, allowlist) và dựng engine tương ứng - nên mọi quyết định an toàn ở đầu kia được
thừa hưởng nguyên vẹn, không phải chép lại.

Ba loại engine, khác nhau ở CÔNG CỤ có được - đây là chỗ phải cẩn thận:
- anthropic-cli: Claude Code. Tool file native + Bash + MCP, chặn theo allowlist per-call.
- openai-oauth: Codex CLI, cũng là agent thật (đọc/ghi file + MCP qua profile javis).
  Sandbox của Codex ánh xạ theo mode: suggest -> read-only, auto -> workspace-write,
  full -> toàn quyền. KHÔNG có allowlist per-call như Claude nên chỉ chặn ở tầng sandbox.
- grok-cli: Grok Build CLI chạy bằng gói SuperGrok / X Premium+. Cũng agent thật (tool file +
  MCP hub qua .grok/config.toml trong brain). Mức quyền xuống thẳng cờ chặn của CLI:
  suggest -> chặn Write/Edit/Bash, auto -> chặn Bash, full -> không chặn ở tầng CLI.
- muse-cli: Meta Muse Code CLI chạy bằng gói thuê bao Muse Code. Cũng agent thật (tool native +
  MCP hub gộp vào ~/.config/muse/settings.json). Mức quyền xuống cờ của `muse exec`:
  suggest -> --disable-write --disable-shell, auto -> --disable-shell, full -> --yolo.
- copilot-cli: GitHub Copilot CLI chạy bằng gói Copilot. Agent thật (tool native + MCP hub qua
  `<brain>/.copilot/mcp-config.json` truyền bằng --additional-mcp-config). Mức quyền xuống cờ:
  suggest -> --deny-tool=shell + write, auto -> --deny-tool=shell, full -> không chặn ở tầng CLI.
- kiro-cli / cursor-cli / vibe-cli (26.10.215): Kiro, Cursor, Mistral Vibe CLI chạy bằng gói của
  từng hãng. Agent thật (tool native + MCP hub ghi vào cấu hình MCP trong brain). Mức quyền
  xuống cờ của từng CLI - xem `_chuan_bi` trong từng module.
- kimi-cli: Kimi Code CLI chạy bằng gói hội viên Kimi. Agent thật (tool native + MCP hub qua
  <brain>/.kimi-code/mcp.json). Mức quyền xuống `disallowedTools` của file agent:
  suggest -> cấm Bash/Write/Edit/Agent, auto -> cấm Bash/Agent, full -> không cấm.
- api (openrouter/openai/gemini/anthropic-api): KHÔNG có tool native. Bù lại hub cấp
  javis_read_file / javis_list_dir / javis_write_file / javis_use_skill + tool MCP, và
  javis_write_file tự chặn khi mode là suggest (mcp_hub._builtin_tools). Không có Bash,
  không có WebFetch - hẹp hơn Claude, nhưng đủ cho việc nền đọc/ghi ghi chú trong vault.

Hợp đồng sự kiện giữ y như ClaudeSDK để nơi gọi không phải sửa: query() sinh dict
{"type": "tool_call"|"final"|"error"|"usage", ...}. Đường API sinh "text" nhiều mảnh nên
ở đây gom lại thành đúng MỘT "final" ở cuối - việc nền đều chỉ đọc sự kiện final.
"""
from __future__ import annotations

import os
import re
import sys
import time
from typing import Optional

import config as cfgmod
import nha_api_rieng

CLAUDE = "anthropic-cli"
CODEX = "openai-oauth"
GROK_CLI = "grok-cli"
MUSE_CLI = "muse-cli"
COPILOT_CLI = "copilot-cli"
KIMI_CLI = "kimi-cli"
ANTIGRAVITY = "antigravity-cli"
# Ba bộ não CLI dựng chung một khuôn (cli_nao_chung.NAO). Giữ tên ở đây thay vì import để module
# này không kéo theo claude_cli lúc nạp.
NAO_CLI_MOI = ("kiro-cli", "cursor-cli", "vibe-cli")
API_PROVIDERS = ("openrouter", "openai", "gemini", "groq", "xai", "meta", "anthropic-api", "ollama",
                 "ollama-local", "openai-compat", *nha_api_rieng.IDS)

# provider -> tên trường chứa API key trong settings["model"]
_KEY_FIELD = {
    "openrouter": "openrouter_key",
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "groq": "groq_api_key",
    "xai": "xai_api_key",
    "meta": "meta_api_key",
    "anthropic-api": "anthropic_api_key",
    "ollama": "ollama_key",
    # Bản chạy MÁY NHÀ. Trường này thường RỖNG - Ollama trần không có xác thực - và điều đó
    # là bình thường chứ không phải "chưa cấu hình": thứ xác định nó dùng được hay không là
    # ĐỊA CHỈ (`ollama_local_endpoint`), còn khoá chỉ cần khi ai đó đặt Ollama sau reverse
    # proxy. Xem `_key_of` bên dưới, chỗ ollama-local được miễn kiểm khoá rỗng.
    "ollama-local": "ollama_local_key",
    # Endpoint OpenAI-compatible tự khai. Như ollama-local: thứ quyết định dùng được là ĐỊA CHỈ
    # (`openai_compat_base`), khoá có thể rỗng khi endpoint không đòi xác thực.
    "openai-compat": "openai_compat_key",
    # DeepSeek / Qwen / GLM / MiniMax: khoá key lấy từ bảng một chỗ.
    **{pid: nha_api_rieng.NHA[pid]["key_field"] for pid in nha_api_rieng.IDS},
}

# mode của Javis -> sandbox của Codex CLI. Bản đồ thật nằm ở `claude_cli.codex_sandbox_cho_mode`
# (nó còn đọc cờ JAVIS_CODEX_SANDBOX); giữ dict này để mã cũ đọc tên mức vẫn chạy.
_CODEX_SANDBOX = {"suggest": "read-only", "auto": "workspace-write", "full": None}

# ── Final "mất đăng nhập" phải bị coi là engine CHẾT, không phải kết quả ──────────────────
# Claude Code chưa đăng nhập KHÔNG trả event error: ResultMessage lỗi vẫn có chữ nên
# claude_sdk_engine map thành một FINAL ngắn "Not logged in · Please run /login".
# _FallbackChain mà tin final đó là thành công thì mắt sau không bao giờ được thử.
# Ca thật 26/08: máy chỉ đăng nhập Gemini, việc nền mặc định Claude → vòng tự học nào
# cũng chết với đúng câu này, nhật ký chỉ ghi "không parse được manifest" khó hiểu.
# Danh sách mẫu đồng bộ TAY với connect_health._ENGINE_AUTH_PATTERNS (không import -
# module này phải test đứng một mình được, xem tests/python/test_aux_fallback.py).
_AUTH_FINAL_PATTERNS = ("please run /login", "not logged in", "invalid api key",
                        "api key not found", "failed to authenticate",
                        "oauth session expired", "oauth token has expired",
                        "could not be refreshed", "refresh token was already used",
                        "log out and sign in again")
_AUTH_FINAL_MAX = 400   # câu lỗi đăng nhập luôn ngắn; final dài là nội dung thật, đừng nghi oan


def final_loi_dang_nhap(text: str) -> bool:
    """Final này có phải câu báo mất đăng nhập của engine CLI không."""
    t = (text or "").strip()
    if not t or len(t) > _AUTH_FINAL_MAX:
        return False
    low = t.lower()
    return any(p in low for p in _AUTH_FINAL_PATTERNS)

# ── Trần wall-clock cho fork NỀN (nhắc hẹn/cron, việc Kanban, bước workflow) ──────────────
# Mặc định 3600s (1 giờ). Trước đây mỗi nơi ghim một số cứng (nhắc hẹn 300, workflow 300,
# Kanban 600) và 300s giết chết việc nền THẬT của người dùng: quét 11 phân mục Meta Ads +
# ghi Google Sheet + gửi Telegram bị chặt ngang lúc đang ghi dở, result rỗng (báo 18/08).
# Trần này là LƯỚI ĐỠ chống fork treo vô hạn, không phải công cụ quản chi phí - fork đơ
# thật thì watchdog idle-timeout của engine bắt sớm hơn nhiều, nên đặt trần theo việc nền
# DÀI NHẤT hợp lệ chứ không theo việc trung bình. Chỉnh qua env JAVIS_BG_MAX_WALL_S
# (giây; giá trị rác hoặc <= 0 thì về mặc định).
BG_MAX_WALL_S_DEFAULT = 3600


def bg_max_wall_s() -> int:
    try:
        v = int(os.getenv("JAVIS_BG_MAX_WALL_S", "") or 0)
        if v > 0:
            return v
    except (TypeError, ValueError):
        pass
    return BG_MAX_WALL_S_DEFAULT

# ── Chọn model FREE mạnh nhất trên OpenRouter (mắt xích cuối của router việc nền) ──
# Xếp hạng theo HỌ model (đầu danh sách = mạnh nhất) rồi tới cỡ tham số trong id, rồi context.
# Danh sách model free của OpenRouter đổi liên tục nên chấm điểm động thay vì ghim cứng 1 tên.
_FREE_FAMILY_RANK = ("deepseek-r1", "deepseek", "qwen3", "qwen", "llama-4", "llama-3.3",
                     "llama", "glm", "gemini", "mistral", "kimi")
_OR_FREE_CACHE = {"ts": 0.0, "model": ""}   # cache 6h - khỏi gọi API models mỗi lần fallback
_OR_FREE_TTL = 6 * 3600


def _score_free_model(mid: str, ctx: int = 0) -> tuple:
    low = (mid or "").lower()
    fam = 0
    for i, f in enumerate(_FREE_FAMILY_RANK):
        if f in low:
            fam = len(_FREE_FAMILY_RANK) - i
            break
    sizes = [int(x) for x in re.findall(r"(\d{1,4})b\b", low)]
    return (fam, max(sizes, default=0), ctx)


async def pick_openrouter_free(key: str = "") -> str:
    """Model free mạnh nhất đang có trên OpenRouter. Lỗi mạng → đoán tĩnh một id phổ biến."""
    now = time.time()
    if _OR_FREE_CACHE["model"] and now - _OR_FREE_CACHE["ts"] < _OR_FREE_TTL:
        return _OR_FREE_CACHE["model"]
    data = []
    try:
        import httpx
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        async with httpx.AsyncClient(timeout=20) as cx:
            r = await cx.get("https://openrouter.ai/api/v1/models", headers=headers)
            r.raise_for_status()
            data = (r.json() or {}).get("data") or []
    except Exception as e:
        print(f"[aux router] không tải được danh sách model OpenRouter: {e}", file=sys.stderr)
    best, best_score = "", (-1, -1, -1)
    for m in data:
        mid = m.get("id") or ""
        if not mid.endswith(":free"):
            continue
        score = _score_free_model(mid, int(m.get("context_length") or 0))
        if score > best_score:
            best, best_score = mid, score
    if not best:
        best = "deepseek/deepseek-v4-flash:free"
    _OR_FREE_CACHE.update(ts=now, model=best)
    return best


def read_spec(settings: dict = None) -> dict:
    """{'provider','model'} của model việc nền. Cấu hình cũ chỉ có 'model' (luôn là alias
    Claude) nên thiếu provider = anthropic-cli - giữ nguyên hành vi bản cũ.

    PHANH NGÂN SÁCH: nếu tháng này đã tiêu quá trần tiền người dùng đặt VÀ họ đã bật tự
    phanh, việc nền không được tiêu thêm tiền mặt nữa. Nó không dừng lại - nó chuyển sang
    đường KHÔNG tính tiền theo token: gói thuê bao đang đăng nhập, hoặc model free của
    OpenRouter. Chat của người dùng KHÔNG bị đụng tới; chỉ việc chạy nền bị hạ, vì đó là
    phần tiêu tiền lúc người ta không ngồi nhìn.
    """
    s = settings if settings is not None else cfgmod.read_settings()
    aux = (s.get("model", {}) or {}).get("auxiliary") or {}
    spec = {"provider": (aux.get("provider") or CLAUDE), "model": (aux.get("model") or "")}
    if spec["provider"] not in API_PROVIDERS:
        return spec                      # gói thuê bao: không tính tiền theo token, kệ phanh
    try:
        import usage_saving
        if not usage_saving.dang_phanh().get("bat"):
            return spec
    except Exception:                    # noqa: BLE001 - thiếu module thì cứ chạy như cũ
        return spec
    return _spec_ne_tien(s, spec)


def _spec_ne_tien(s: dict, spec: dict) -> dict:
    """Đường thay thế khi phanh: ưu tiên gói thuê bao đã đăng nhập, cuối cùng là OpenRouter free.

    `availability` trả True VÔ ĐIỀU KIỆN cho anthropic-cli (nó không kiểm binary `claude` có
    trên máy hay không, khác hẳn nhánh Codex/Gemini). Nên nếu chỉ hỏi availability thì vòng
    này luôn dừng ở mắt đầu, và trên máy KHÔNG cài Claude Code việc nền bị đẩy sang một engine
    không chạy được - phanh biến thành cái làm chết việc nền. Phải hỏi thẳng binary.
    """
    for prov in (CLAUDE, CODEX):
        ok, _ly_do = availability({"provider": prov}, s)
        if ok and _co_binary(prov):
            return {"provider": prov, "model": ""}
    if api_key_for("openrouter", s):
        # model "" trên OpenRouter = tự chọn model FREE mạnh nhất lúc chạy (_ApiAuxEngine.query).
        return {"provider": "openrouter", "model": ""}
    return spec                          # không có đường nào rẻ hơn -> giữ nguyên, đừng làm chết việc nền


def _co_binary(prov: str) -> bool:
    """Engine CLI đó có thật trên máy không. Lỗi/thiếu module -> False (đừng đoán là có)."""
    try:
        import claude_cli
        if prov == CLAUDE:
            return bool(claude_cli.find_claude_cli())
        if prov == CODEX:
            return bool(claude_cli.find_codex_cli())
    except Exception:   # noqa: BLE001 - không dò được thì coi như không có, rồi thử mắt sau
        return False
    return False


def main_spec(settings: dict = None) -> dict:
    """{'provider','model'} của MAIN MODEL (bộ não người dùng chọn ở trang Models).

    Bản rút của main._effective_main - chép lại thay vì import main (module này không được
    import main, tránh vòng). Dùng làm MẮT DỰ PHÒNG cho việc nền: người để trống model phụ
    thì aux mặc định Claude, nhưng máy chỉ đăng nhập Gemini/OpenAI... thì Claude chết và
    việc nền chết theo dù bộ não CHÍNH vẫn chạy ngon - chuỗi fallback phải biết tới nó.
    """
    s = settings if settings is not None else cfgmod.read_settings()
    m = s.get("model", {}) or {}
    main = m.get("main") or {}
    if main.get("provider"):
        return {"provider": main["provider"], "model": main.get("model") or ""}
    eng = m.get("engine")
    if eng == "openrouter":
        return {"provider": "openrouter", "model": m.get("openrouter_model") or ""}
    if eng == "anthropic-api":
        return {"provider": "anthropic-api", "model": m.get("claude_model") or ""}
    return {"provider": CLAUDE, "model": m.get("claude_model") or ""}


def is_claude(spec: dict) -> bool:
    return (spec or {}).get("provider", CLAUDE) == CLAUDE


def api_key_for(provider: str, settings: dict = None) -> str:
    field = _KEY_FIELD.get(provider)
    if not field:
        return ""
    s = settings if settings is not None else cfgmod.read_settings()
    m = s.get("model", {}) or {}
    if provider == "openai-compat":
        # Có Base URL là chạy được; khoá rỗng thì gửi "none" (endpoint không đòi xác thực).
        return (m.get(field) or "none") if (m.get("openai_compat_base") or "").strip() else ""
    return m.get(field) or ""


def availability(spec: dict, settings: dict = None) -> tuple:
    """(dùng được?, lý do nếu không). Để trang Model cảnh báo TRƯỚC khi người dùng chọn
    nhầm một provider chưa đăng nhập / chưa có key rồi việc nền chết lặng lẽ."""
    prov = (spec or {}).get("provider", CLAUDE)
    if prov == CLAUDE:
        return True, ""
    if prov == CODEX:
        try:
            from claude_cli import find_codex_cli
            if not find_codex_cli():
                return False, "Chưa cài Codex CLI (cần đăng nhập gói ChatGPT)."
        except Exception:
            return False, "Không kiểm tra được Codex CLI."
        return True, ""
    if prov == GROK_CLI:
        try:
            import grok_cli as _g
            st = _g.auth_status()
            if not st.get("connected"):
                return False, st.get("error") or "Grok Build CLI chưa sẵn sàng."
        except Exception:
            return False, "Không kiểm tra được Grok Build CLI."
        return True, ""
    if prov == MUSE_CLI:
        try:
            import muse_cli as _u
            st = _u.auth_status()
            if not st.get("connected"):
                return False, st.get("error") or "Muse Code CLI chưa sẵn sàng."
        except Exception:
            return False, "Không kiểm tra được Muse Code CLI."
        return True, ""
    if prov == COPILOT_CLI:
        try:
            import copilot_cli as _p
            st = _p.auth_status()
            if not st.get("connected"):
                return False, st.get("error") or "GitHub Copilot CLI chưa sẵn sàng."
        except Exception:
            return False, "Không kiểm tra được GitHub Copilot CLI."
    if prov in NAO_CLI_MOI:
        try:
            import cli_nao_chung
            _m = cli_nao_chung.mo_dun(prov)
            st = _m.auth_status() if _m else {"connected": False}
            # "dang_kiem" = chưa có kết quả hỏi CLI lần nào: cứ cho chạy, lượt thật tự báo lỗi.
            if not st.get("connected") and not st.get("dang_kiem"):
                return False, st.get("error") or f"{prov} chưa sẵn sàng."
        except Exception:
            return False, f"Không kiểm tra được {prov}."
    if prov == KIMI_CLI:
        try:
            import kimi_cli as _k
            st = _k.auth_status()
            if not st.get("connected"):
                return False, st.get("error") or "Kimi Code CLI chưa sẵn sàng."
        except Exception:
            return False, "Không kiểm tra được Kimi Code CLI."
        return True, ""
    if prov == ANTIGRAVITY:
        try:
            import antigravity_cli as _a
            if not _a.find_antigravity_cli():
                return False, "Chưa cài Antigravity CLI (`agy`) trên máy chạy Javis."
            # Bản NỀN (đọc cache, làm mới bằng thread), KHÔNG phải auth_status(): hàm này chạy
            # ngay trong code async (học sau lượt chat, việc Kanban, nhắc hẹn, loop), mà
            # auth_status() hỏi thẳng `agy models` tới 80 giây. Cả app đứng theo: chủ repo đổi
            # trợ lý giữa lúc Gemini đang chạy thì màn hình không đổi (23/09).
            # "dang_kiem" = mới khởi động, chưa có kết quả: cứ cho chạy, lượt thật tự báo lỗi.
            st = _a.auth_status_nen()
            if not st.get("connected") and not st.get("dang_kiem"):
                return False, st.get("error") or "Antigravity CLI chưa đăng nhập Google."
        except Exception:
            return False, "Không kiểm tra được Antigravity CLI."
        return True, ""
    # Ollama máy nhà xét theo ĐỊA CHỈ, không theo khoá: Ollama trần không có xác thực nên
    # khoá rỗng là trạng thái BÌNH THƯỜNG. Để nó rơi vào nhánh kiểm khoá bên dưới thì mọi
    # agent dùng model local đều bị báo "chưa có API key" dù đang chạy ngon.
    if prov == "ollama-local":
        s = settings if settings is not None else cfgmod.read_settings()
        if not (s.get("model", {}) or {}).get("ollama_local_endpoint"):
            return False, "Chưa đặt địa chỉ Ollama - vào trang Models, tab Local Model."
        return True, ""
    if prov == "openai-compat":
        s = settings if settings is not None else cfgmod.read_settings()
        if not (s.get("model", {}) or {}).get("openai_compat_base"):
            return False, "Chưa đặt Base URL cho OpenAI Compatible - vào trang Models."
        return True, ""
    if prov in API_PROVIDERS:
        if not api_key_for(prov, settings):
            return False, f"Chưa có API key cho {prov} - vào trang Model dán key trước."
        return True, ""
    return False, f"Provider lạ: {prov}"


class _ApiAuxEngine:
    """Engine việc nền chạy bằng provider API, mang hợp đồng của ClaudeSDK.

    Công cụ lấy từ hub (builtin file vault + MCP). Hub tự chặn ghi khi mode=suggest, nên
    loop chế độ chỉ-đọc vẫn chỉ-đọc dù chạy trên engine này.
    """

    def __init__(self, provider, model, system_prompt=None, vault_root=None,
                 mode="full", tag="aux", reasoning="off"):
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt
        self.vault_root = vault_root
        self.javis_mode = mode
        self.tag = tag
        self.reasoning = reasoning
        self.session_id = None      # engine API không có phiên nối tiếp - giữ cho đủ hợp đồng
        # Trụ 6 (26.10.217), cả hai mặc định TẮT nên mọi chỗ dùng cũ không đổi gì:
        # - tools_override = (tools, route): bộ tool RIÊNG thay cho discover_all của hub. Phiên
        #   cải tiến chỉ được đọc thư mục bằng chứng của nó, không được thấy POS/Zalo/plugin.
        # - phat_ket_qua_tool: phát cả sự kiện tool_result để bộ thu trajectory ghi được kết quả
        #   tool. Việc nền cũ chỉ đọc final nên trước giờ bỏ sự kiện này đi.
        self.tools_override = None
        self.phat_ket_qua_tool = False

    def is_available(self) -> bool:
        return bool(api_key_for(self.provider))

    def reset_session(self):
        self.session_id = None

    async def query(self, prompt: str):
        import engine as eng
        import mcp_hub

        key = api_key_for(self.provider)
        if not key:
            yield {"type": "error", "content": f"Chưa có API key cho {self.provider}."}
            return

        # OpenRouter model trống = "tự chọn free mạnh nhất". User ghi đè bằng
        # settings model.fallback_openrouter_model; lần chọn tự động đầu tiên cũng lưu vào
        # đúng field đó để user thấy đang dùng gì và đổi sau nếu muốn.
        if self.provider == "openrouter" and not self.model:
            try:
                s = cfgmod.read_settings()
                override = ((s.get("model", {}) or {}).get("fallback_openrouter_model") or "").strip()
                self.model = override or await pick_openrouter_free(key)
                # Lượt chạy thử (Trụ 6) không được ghi settings thật của chủ, kể cả để nhớ model.
                import che_do_thu
                if not override and self.model and not che_do_thu.dang_bat():
                    s.setdefault("model", {})["fallback_openrouter_model"] = self.model
                    cfgmod.write_settings(s)
            except Exception as e:
                print(f"[aux router] chọn model free lỗi: {e}", file=sys.stderr)
            if not self.model:
                yield {"type": "error", "content": "Không chọn được model free OpenRouter."}
                return

        tools, route = [], {}
        # `khong_tool` (26.10.97): việc chỉ cần ĐỌC CHỮ được đưa sẵn trong prompt (soi gói chia sẻ
        # của người lạ) thì không cấp tool nào, kể cả tool đọc file của hub.
        if getattr(self, "tools_override", None) is not None:
            tools, route = self.tools_override
        elif not getattr(self, "khong_tool", False):
            try:
                tools, route = await mcp_hub.discover_all(self.javis_mode or "full",
                                                          vault_root=self.vault_root)
            except Exception as e:
                print(f"[aux discover] {e}", file=sys.stderr)

        messages = []
        sysprompt = self.system_prompt or ""
        # Khai THẬT năng lực của engine này. Không có dòng này, model chỉ thấy "gọi tool X
        # không được" rồi tự dựng một lý do nghe hợp lý mà sai - hay gặp nhất là đổ cho quyền
        # ("phiên này bị chặn quyền"), khiến chủ đi sửa mức quyền trong khi mức quyền không hề
        # sai. Nói rõ THIẾU GÌ và VÌ SAO thì câu báo về mới dẫn đúng tới việc cần làm.
        sysprompt += (
            "\n\n[Sự thật hệ thống - năng lực của phiên này] Bạn đang chạy bằng engine API "
            f"'{self.provider}', KHÔNG phải Claude Code. Bạn có: các tool qua MCP Hub của Javis "
            "(gồm tool đọc/ghi file trong vault và mọi MCP người dùng đã đấu vào Javis). "
            "Bạn KHÔNG có: lệnh máy (Bash), tự mở URL (WebFetch/WebSearch), và KHÔNG có các "
            "connector gắn thẳng vào TÀI KHOẢN Claude - Gmail, Google Drive, Google Calendar "
            "gọi bằng tool native `mcp__<tên>__*` chỉ tồn tại trên engine Claude Code. "
            "Nếu việc được giao cần một trong những thứ đó, hãy nói THẲNG là engine hiện tại "
            "không có công cụ ấy và chủ cần đổi model việc nền sang Claude Code. TUYỆT ĐỐI "
            "không mô tả chuyện này là bị chặn quyền hay thiếu quyền: mức quyền không liên "
            "quan, đây là chuyện engine nào có tool nào."
        )
        if sysprompt.strip():
            messages.append({"role": "system", "content": sysprompt})
        messages.append({"role": "user", "content": prompt})

        # Bể khoá (26.10.161): việc nền cũng xoay khoá khi vấp 429/401 nếu chủ khai khoá dự phòng.
        xoay = None
        try:
            import be_khoa
            if self.provider in be_khoa.API_CO_BE:
                _keys = be_khoa.danh_sach(self.provider, cfgmod.read_settings().get("model", {}) or {}, key)
                xoay = be_khoa.Xoay(self.provider, _keys) if len(_keys) > 1 else None
        except Exception:
            xoay = None
        if tools:
            fn = {"openrouter": eng.openrouter_chat_with_mcp,
                  "openai": eng.openai_chat_with_mcp,
                  "gemini": eng.gemini_chat_with_mcp, "groq": eng.groq_chat_with_mcp,
                  "xai": eng.xai_chat_with_mcp, "meta": eng.meta_chat_with_mcp,
                  "anthropic-api": eng.anthropic_chat_with_mcp,
                  "ollama": eng.ollama_chat_with_mcp,
                  "ollama-local": eng.ollama_local_chat_with_mcp,
                  "openai-compat": eng.openai_compat_chat_with_mcp,
                  **{p: eng.nha_rieng_ham(p, True) for p in nha_api_rieng.IDS}}[self.provider]
            stream = eng.thu_lai_khi_tam_thoi(
                lambda: fn(xoay.khoa() if xoay else key, self.model, messages, self.reasoning, tools, route),
                nhan=f"nền {self.provider}+tool", xoay=xoay) if xoay else \
                fn(key, self.model, messages, self.reasoning, tools, route)
        else:
            fn = {"openrouter": eng.openrouter_stream, "openai": eng.openai_stream,
                  "gemini": eng.gemini_stream, "groq": eng.groq_stream,
                  "xai": eng.xai_stream, "meta": eng.meta_stream,
                  "anthropic-api": eng.anthropic_stream,
                  "ollama": eng.ollama_stream,
                  "ollama-local": eng.ollama_local_stream,
                  "openai-compat": eng.openai_compat_stream,
                  **{p: eng.nha_rieng_ham(p) for p in nha_api_rieng.IDS}}[self.provider]
            stream = eng.thu_lai_khi_tam_thoi(
                lambda: fn(xoay.khoa() if xoay else key, self.model, messages, self.reasoning),
                nhan=f"nền {self.provider}", xoay=xoay) if xoay else \
                fn(key, self.model, messages, self.reasoning)

        # Đường API sinh "text" theo mảnh; việc nền chỉ đọc "final" nên gom lại rồi phát MỘT lần.
        buf = []
        async for ev in stream:
            t = ev.get("type")
            if t == "text":
                buf.append(ev.get("content") or "")
            elif t in ("tool_call", "error", "usage") or (t == "tool_result" and self.phat_ket_qua_tool):
                if t == "usage":
                    self._ghi_muc_dung(ev)
                yield ev
                if t == "error":
                    return
        yield {"type": "final", "content": "".join(buf)}

    def _ghi_muc_dung(self, ev: dict) -> None:
        """Cộng lượt việc nền này vào sổ mức dùng.

        Đây là chỗ DUY NHẤT việc nền chạy bằng API key đi qua. Trước đây không có nó: cả 12
        chỗ gọi `usage_store.record` trong repo đều nằm trên đường CHAT, còn loop / việc
        Kanban / nhắc hẹn / tự học đều chạy qua đây và không ghi gì. Hệ quả là trang Mức dùng
        không thấy phần token nền của nhánh API, và tệ hơn: trần tiền tháng cùng cái phanh
        ngân sách không nhìn thấy ĐÚNG khoản chi mà chúng sinh ra để chặn - việc nền tiêu tiền
        lúc không ai ngồi nhìn.

        Best-effort: hỏng thì nuốt, một cái sổ đếm không được phép làm chết việc nền.
        """
        try:
            import usage_store
            usage_store.record(self.provider, self.model,
                               ev.get("input", 0), ev.get("output", 0), ev.get("cost", 0) or 0)
        except Exception as e:  # noqa: BLE001
            print(f"[aux usage] {type(e).__name__}: {e}", file=sys.stderr)


class _FallbackChain:
    """Router việc nền: CHUỖI engine thử lần lượt, mắt trước chết LÚC CHẠY (hết quota, CLI
    lỗi, stream câm không final, không sẵn sàng) thì chạy lại nguyên prompt bằng mắt sau.
    Chuỗi điển hình: engine phụ user chọn → Claude → OpenRouter model free mạnh nhất.
    Triết lý của swap() vốn là "việc nền phải chạy chứ không chết" nhưng trước đây chỉ đỡ
    được lỗi lúc DỰNG (thiếu key/CLI); lỗi lúc chạy thì chết thật - ca thật: Codex "You've
    hit your usage limit" làm nhắc hẹn chỉ báo ⚠ về Telegram rồi thôi.
    Trong suốt với nơi gọi: đọc attr → mắt đầu; GÁN attr (max_wall_s...) → đặt cho MỌI mắt
    để engine dự phòng cũng nhận giới hạn/cấu hình mà caller đặt sau swap()."""

    def __init__(self, engines):
        object.__setattr__(self, "_engines", [e for e in (engines or []) if e is not None])

    def _all(self):
        return object.__getattribute__(self, "_engines")

    def __getattr__(self, name):
        return getattr(self._all()[0], name)

    def __setattr__(self, name, value):
        for e in self._all():
            try:
                setattr(e, name, value)
            except Exception:
                pass

    def is_available(self) -> bool:
        for e in self._all():
            try:
                if e.is_available():
                    return True
            except Exception:
                pass
        return False

    def reset_session(self):
        for e in self._all():
            try:
                e.reset_session()
            except Exception:
                pass

    @staticmethod
    def _name(e) -> str:
        return getattr(e, "provider", None) or type(e).__name__

    async def query(self, prompt: str):
        fail = "chuỗi engine việc nền rỗng"
        dau = ""      # lỗi của mắt xích ĐẦU TIÊN thật sự chạy - thường là lỗi có nghĩa nhất
        for e in self._all():
            try:
                if not e.is_available():
                    fail = f"{self._name(e)} không sẵn sàng"
                    continue
                got_final, got_error = False, None
                da_lam = False     # mắt này đã gọi công cụ chưa (đã "làm" gì đó ra ngoài chưa)
                async for ev in e.query(prompt):
                    t = (ev or {}).get("type")
                    if t == "tool_call":
                        da_lam = True
                    if t == "error":
                        got_error = ev.get("content") or f"{self._name(e)} trả error"
                        break
                    # Engine CLI chưa đăng nhập trả một FINAL ngắn kiểu "Not logged in ·
                    # Please run /login" chứ không phải error - nuốt nó lại và coi là mắt
                    # chết, kẻo chuỗi dự phòng tưởng thành công rồi dừng (xem chú thích
                    # ở _AUTH_FINAL_PATTERNS).
                    # Cuộc đua làm mới token Claude: phiên KHÔNG mất, nhưng lượt này hỏng và
                    # việc nền không tự gửi lại được -> vẫn phải nhảy sang mắt kế tiếp. Đọc CỜ
                    # chứ không khớp chữ: câu người đọc đã được viết lại cho dễ hiểu.
                    if t == "final" and ev.get("dua_token"):
                        got_error = (f"{self._name(e)} trùng lúc làm mới phiên đăng nhập "
                                     "(hai lượt cùng dùng một tài khoản)")
                        break
                    if t == "final" and final_loi_dang_nhap(ev.get("content")):
                        got_error = (f"{self._name(e)} mất đăng nhập: "
                                     + (ev.get("content") or "").strip()[:200])
                        break
                    # Claude Code kết thúc lượt hỏng (hết lượt gói, API 429) bằng một final cắm cờ
                    # `is_error`, chữ là câu báo của nhà cung cấp. Cho qua như thành công thì mắt sau
                    # không bao giờ được chạy và việc bị báo Xong với đúng câu đó (26.10.312).
                    if t == "final" and ev.get("is_error"):
                        got_error = ((ev.get("content") or "").strip()[:300]
                                     or f"{self._name(e)} kết thúc lỗi ({ev.get('subtype') or 'final'})")
                        if da_lam:
                            # Đã gọi công cụ rồi mới hỏng: chạy lại từ đầu ở mắt sau có thể gửi tin,
                            # đăng bài hay tạo đơn lần hai. Dừng ở đây, báo đúng lỗi này.
                            yield {"type": "error", "content": got_error}
                            return
                        break
                    yield ev
                    if t == "final":
                        got_final = True
                if got_final:
                    _ghi_duong_nen(self._all(), e, dau)
                    return                                       # mắt này chạy ngon → xong
                fail = got_error or f"{self._name(e)} kết thúc mà không có final"
                _ghi_het_luot_nen(e, fail)
                if da_lam:
                    # 26.10.309: mắt này ĐÃ gọi công cụ rồi mới gãy. Chạy lại nguyên prompt bằng engine
                    # khác có thể gửi tin, đăng bài lần hai, nên chuỗi dừng ở đây và nói rõ vì sao.
                    # Nhờ luật này việc mức full cũng có dự phòng được.
                    print(f"[aux router] {self._name(e)} hỏng SAU khi đã gọi công cụ - dừng, không chạy "
                          "lại bằng engine khác.", file=sys.stderr)
                    yield {"type": "error", "content": str(fail) + (f" | {dau}" if dau and dau != str(fail) else "")}
                    return
            except Exception as exc:
                fail = f"{self._name(e)}: {type(exc).__name__}: {exc}"
            print(f"[aux router] {self._name(e)} lỗi → thử mắt xích kế tiếp. Lý do: {str(fail)[:300]}",
                  file=sys.stderr)
            dau = dau or str(fail)
        # Hết chuỗi: trả CẢ lỗi đầu lẫn lỗi cuối. Chỉ trả lỗi cuối ("openrouter không sẵn sàng")
        # là câu "hết lượt gói Claude" của mắt đầu bị nuốt, và hàng đợi việc không nhận ra để hoãn
        # tới giờ gói mở lại (tasks._het_luot đọc câu này).
        noi = str(fail) if (not dau or dau == str(fail)) else f"{dau} | {fail}"
        yield {"type": "error", "content": noi}


def _build_api(spec, claude_cli_obj, mode, tag):
    return _ApiAuxEngine(
        provider=spec["provider"],
        model=spec.get("model") or "",
        system_prompt=getattr(claude_cli_obj, "system_prompt", None),
        vault_root=getattr(claude_cli_obj, "javis_vault", None),
        mode=mode or getattr(claude_cli_obj, "javis_mode", None) or "full",
        tag=tag or getattr(claude_cli_obj, "tag", "aux"),
    )


def _build_codex(spec, claude_cli_obj, mode, tag, codex_profile=None):
    from claude_cli import CodexCLI, codex_sandbox_cho_mode
    cc = CodexCLI(cwd=getattr(claude_cli_obj, "cwd", None),
                  tag=tag or getattr(claude_cli_obj, "tag", "aux"),
                  model=spec.get("model") or None,
                  instructions=getattr(claude_cli_obj, "system_prompt", None))
    # Codex không có allowlist per-call như Claude → chặn ở tầng sandbox của chính nó.
    # `codex_sandbox_cho_mode` còn đọc cờ JAVIS_CODEX_SANDBOX: trong Docker, bubblewrap không
    # chạy nổi nên rào đó không phải "chặt hơn" mà là "chết hẳn", và cờ là đường thoát.
    cc.sandbox = codex_sandbox_cho_mode(mode or getattr(claude_cli_obj, "javis_mode", None) or "full")
    cc.vault_root = getattr(claude_cli_obj, "javis_vault", None)   # ảnh Codex vẽ về đúng brain
    if codex_profile:
        try:
            cc.profile = codex_profile()   # profile javis = thấy MCP của Javis (POS, connector...)
        except Exception as e:
            print(f"[aux codex profile] {e}", file=sys.stderr)
    try:
        import mcp_hub
        mcp_hub.dat_codex_vault(cc.extra_config, getattr(claude_cli_obj, "javis_vault", None))
        # Mode đi theo việc nền (26.10.96): profile chung luôn full, nên phải ghi đè từng tiến trình,
        # không thì loop mức suggest chạy Codex vẫn gọi được tool MCP ra ngoài.
        mcp_hub.dat_codex_mode(cc.extra_config, mode or getattr(claude_cli_obj, "javis_mode", None) or "full")
        mcp_hub.dat_codex_job(cc.extra_config, getattr(claude_cli_obj, "javis_job", "") or "")
    except Exception as e:
        print(f"[aux codex vault] {e}", file=sys.stderr)
    return cc


def _build_grok(spec, claude_cli_obj, mode, tag):
    """Engine việc nền/agent chạy bằng Grok Build CLI (`grok`).

    Mức quyền xuống thẳng cờ `--deny` của CLI chứ không phải một lời hứa trong prompt, và
    `grok_cli.permission_cho_mode` fail-closed (mode lạ về nấc chặt nhất). Cùng vai với sandbox
    của Codex - lớp chặn tool NATIVE, còn rào tiền/đơn/đăng bài vẫn nằm ở MCP Hub.

    Entry MCP dựng bằng `grok_cli.hub_entry()` chứ KHÔNG viết tay: Grok đọc khoá `url`, còn
    `agy` đọc `serverUrl`. Chép nhầm khoá giữa hai engine là không có lấy một tool nào của
    Javis mà không một câu lỗi nào - đúng thứ đã xảy ra với `agy` mấy bản liền.
    """
    import grok_cli as _g
    muc = mode or getattr(claude_cli_obj, "javis_mode", None) or "full"
    gc = _g.GrokCLI(cwd=getattr(claude_cli_obj, "cwd", None),
                    tag=tag or getattr(claude_cli_obj, "tag", "aux"),
                    model=spec.get("model") or None,
                    instructions=getattr(claude_cli_obj, "system_prompt", None))
    gc.mode = muc
    vault = getattr(claude_cli_obj, "javis_vault", None) or getattr(claude_cli_obj, "cwd", None)
    if vault:
        try:
            import mcp_hub
            hub = None
            if bool(cfgmod.read_settings().get("mcp", {}).get("hub", True)):
                hub = _g.hub_entry(mcp_hub.hub_url(),
                                   {"Authorization": f"Bearer {mcp_hub.hub_token()}",
                                    "X-Javis-Mode": muc, "X-Javis-Vault": str(vault),
                                    **_hub_job(claude_cli_obj)})
            _g.ghi_mcp_settings(vault, hub)
        except Exception as e:
            print(f"[aux grok mcp] {e}", file=sys.stderr)
    return gc


def _build_muse(spec, claude_cli_obj, mode, tag):
    """Engine việc nền/agent chạy bằng Meta Muse Code CLI (`muse`). Cùng khuôn `_build_grok`;
    entry MCP dựng bằng `muse_cli.hub_entry()` (transport streamable_http) và GỘP vào cấu hình
    cá nhân `~/.config/muse/settings.json` thay vì file trong brain."""
    import muse_cli as _u
    muc = mode or getattr(claude_cli_obj, "javis_mode", None) or "full"
    uc = _u.MuseCLI(cwd=getattr(claude_cli_obj, "cwd", None),
                    tag=tag or getattr(claude_cli_obj, "tag", "aux"),
                    model=spec.get("model") or None,
                    instructions=getattr(claude_cli_obj, "system_prompt", None))
    uc.mode = muc
    vault = getattr(claude_cli_obj, "javis_vault", None) or getattr(claude_cli_obj, "cwd", None)
    if vault:
        try:
            import mcp_hub
            hub = None
            if bool(cfgmod.read_settings().get("mcp", {}).get("hub", True)):
                hub = _u.hub_entry(mcp_hub.hub_url(),
                                   {"Authorization": f"Bearer {mcp_hub.hub_token()}",
                                    "X-Javis-Mode": muc, "X-Javis-Vault": str(vault),
                                    **_hub_job(claude_cli_obj)})
            _u.ghi_mcp_settings(vault, hub)
        except Exception as e:
            print(f"[aux muse mcp] {e}", file=sys.stderr)
    return uc


def _build_copilot(spec, claude_cli_obj, mode, tag):
    """Engine việc nền/agent chạy bằng GitHub Copilot CLI (`copilot`). Cùng khuôn `_build_grok`;
    entry MCP dựng bằng `copilot_cli.hub_entry()` và ghi vào `<brain>/.copilot/mcp-config.json`,
    engine tự truyền `--additional-mcp-config @<file>` cho riêng lượt đó."""
    import copilot_cli as _p
    muc = mode or getattr(claude_cli_obj, "javis_mode", None) or "full"
    pc = _p.CopilotCLI(cwd=getattr(claude_cli_obj, "cwd", None),
                       tag=tag or getattr(claude_cli_obj, "tag", "aux"),
                       model=spec.get("model") or None,
                       instructions=getattr(claude_cli_obj, "system_prompt", None))
    pc.mode = muc
    vault = getattr(claude_cli_obj, "javis_vault", None) or getattr(claude_cli_obj, "cwd", None)
    if vault:
        try:
            import mcp_hub
            hub = None
            if bool(cfgmod.read_settings().get("mcp", {}).get("hub", True)):
                hub = _p.hub_entry(mcp_hub.hub_url(),
                                   {"Authorization": f"Bearer {mcp_hub.hub_token()}",
                                    "X-Javis-Mode": muc, "X-Javis-Vault": str(vault),
                                    **_hub_job(claude_cli_obj)})
            f = _p.ghi_mcp_settings(vault, hub)
            pc.mcp_file = f if hub else None
        except Exception as e:
            print(f"[aux copilot mcp] {e}", file=sys.stderr)
    return pc


def _build_nao_cli(spec, claude_cli_obj, mode, tag):
    """Engine việc nền/agent chạy bằng Kiro / Cursor / Mistral Vibe CLI. Cùng khuôn `_build_grok`:
    entry MCP do chính module dựng (`hub_entry`) rồi ghi vào cấu hình MCP trong brain."""
    import cli_nao_chung
    prov = spec.get("provider")
    _m = cli_nao_chung.mo_dun(prov)
    lop = next(getattr(_m, t) for t in ("KiroCLI", "CursorCLI", "VibeCLI") if hasattr(_m, t))
    muc = mode or getattr(claude_cli_obj, "javis_mode", None) or "full"
    nc = lop(cwd=getattr(claude_cli_obj, "cwd", None),
             tag=tag or getattr(claude_cli_obj, "tag", "aux"),
             model=spec.get("model") or None,
             instructions=getattr(claude_cli_obj, "system_prompt", None))
    nc.mode = muc
    nc.provider = prov
    vault = getattr(claude_cli_obj, "javis_vault", None) or getattr(claude_cli_obj, "cwd", None)
    if vault:
        try:
            import mcp_hub
            hub = None
            if bool(cfgmod.read_settings().get("mcp", {}).get("hub", True)):
                hub = _m.hub_entry(mcp_hub.hub_url(),
                                   {"Authorization": f"Bearer {mcp_hub.hub_token()}",
                                    "X-Javis-Mode": muc, "X-Javis-Vault": str(vault),
                                    **_hub_job(claude_cli_obj)})
            _m.ghi_mcp_settings(vault, hub)
        except Exception as e:
            print(f"[aux {prov} mcp] {e}", file=sys.stderr)
    return nc


def _build_kimi(spec, claude_cli_obj, mode, tag):
    """Engine việc nền/agent chạy bằng Kimi Code CLI (`kimi`). Cùng khuôn `_build_grok`; entry
    MCP dựng bằng `kimi_cli.hub_entry()` và ghi vào `<brain>/.kimi-code/mcp.json`."""
    import kimi_cli as _k
    muc = mode or getattr(claude_cli_obj, "javis_mode", None) or "full"
    kc = _k.KimiCLI(cwd=getattr(claude_cli_obj, "cwd", None),
                    tag=tag or getattr(claude_cli_obj, "tag", "aux"),
                    model=spec.get("model") or None,
                    instructions=getattr(claude_cli_obj, "system_prompt", None))
    kc.mode = muc
    vault = getattr(claude_cli_obj, "javis_vault", None) or getattr(claude_cli_obj, "cwd", None)
    if vault:
        try:
            import mcp_hub
            hub = None
            if bool(cfgmod.read_settings().get("mcp", {}).get("hub", True)):
                hub = _k.hub_entry(mcp_hub.hub_url(),
                                   {"Authorization": f"Bearer {mcp_hub.hub_token()}",
                                    "X-Javis-Mode": muc, "X-Javis-Vault": str(vault),
                                    **_hub_job(claude_cli_obj)})
            _k.ghi_mcp_settings(vault, hub)
        except Exception as e:
            print(f"[aux kimi mcp] {e}", file=sys.stderr)
    return kc


def _build_antigravity(spec, claude_cli_obj, mode, tag):
    """Engine việc nền/agent chạy bằng Antigravity CLI (`agy`).

    Khác `_build_grok` ở hai chỗ, và cả hai đều là lý do phải viết riêng thay vì dùng chung:

    - **Mức quyền yếu hơn thật.** `agy` KHÔNG có cờ chặn per-tool như `--deny` của Grok;
      `suggest` ở đây chỉ được siết bằng `--sandbox` cộng lời dặn trong prompt. Xem
      `antigravity_cli.co_quyen_cho_mode` - nó nói thẳng chuyện này, và rào tiền/đơn/đăng bài
      vẫn nằm ở MCP Hub chứ không ở CLI.
    - **Hình dạng entry MCP khác hẳn.** `agy` đọc khoá `serverUrl`, Grok đọc `url`. Chép nhầm
      khoá là engine chạy trơn tru mà không có lấy một tool nào của Javis, không một tiếng
      động - đúng thứ đã xảy ra mấy bản liền. Nên dựng entry bằng `antigravity_cli.hub_entry()`
      chứ không viết tay.
    """
    import antigravity_cli as _a
    muc = mode or getattr(claude_cli_obj, "javis_mode", None) or "full"
    ac = _a.AntigravityCLI(cwd=getattr(claude_cli_obj, "cwd", None),
                           tag=tag or getattr(claude_cli_obj, "tag", "aux"),
                           model=spec.get("model") or None,
                           instructions=getattr(claude_cli_obj, "system_prompt", None))
    ac.mode = muc
    vault = getattr(claude_cli_obj, "javis_vault", None) or getattr(claude_cli_obj, "cwd", None)
    if vault:
        try:
            import mcp_hub
            hub = None
            if bool(cfgmod.read_settings().get("mcp", {}).get("hub", True)):
                hub = _a.hub_entry(mcp_hub.hub_url(),
                                   {"Authorization": f"Bearer {mcp_hub.hub_token()}",
                                    "X-Javis-Mode": muc, "X-Javis-Vault": str(vault),
                                    **_hub_job(claude_cli_obj)})
            _a.ghi_mcp_settings(vault, hub)
        except Exception as e:
            print(f"[aux antigravity mcp] {e}", file=sys.stderr)
    return ac


def dung_rieng(spec: dict, cli, mode: str, tag: str, codex_profile=None, settings: dict = None):
    """Dựng engine cho ĐÚNG MỘT nhà, KHÔNG chuỗi dự phòng (khác `swap`).

    Dành cho bộ chấm điểm não (26.10.128): chấm não nào phải chạy đúng não đó. Đi qua `swap`
    thì não chọn gãy là Claude lặng lẽ tiếp quản, bảng điểm thành điểm của Claude mà ghi tên
    não kia. Nhà chưa sẵn sàng thì ném ValueError với lý do đọc được, không rơi về đâu cả.
    `cli` là engine Claude đã dựng (system prompt, vault, allowed tools) để các nhà khác thừa kế."""
    sp = dict(spec or {})
    prov = sp.get("provider", CLAUDE)
    ok, why = availability(sp, settings)
    if not ok:
        raise ValueError(why or f"Não '{prov}' chưa sẵn sàng.")
    if prov == CLAUDE:
        cli.model = sp.get("model") or None
        return cli
    if prov == CODEX:
        return _build_codex(sp, cli, mode, tag, codex_profile)
    if prov == GROK_CLI:
        return _build_grok(sp, cli, mode, tag)
    if prov == MUSE_CLI:
        return _build_muse(sp, cli, mode, tag)
    if prov == COPILOT_CLI:
        return _build_copilot(sp, cli, mode, tag)
    if prov in NAO_CLI_MOI:
        return _build_nao_cli(sp, cli, mode, tag)
    if prov == KIMI_CLI:
        return _build_kimi(sp, cli, mode, tag)
    if prov == ANTIGRAVITY:
        return _build_antigravity(sp, cli, mode, tag)
    if prov in API_PROVIDERS:
        return _build_api(sp, cli, mode, tag)
    raise ValueError(f"Không dựng được engine cho nhà '{prov}'.")


def _hub_job(claude_cli_obj) -> dict:
    """Header mã việc Kanban cho cấu hình hub của engine CLI không phải Claude (26.10.248).

    `tasks._gan_ma_viec` đặt `javis_job` lên engine Claude trước khi đổi sang engine phụ. Thiếu
    header này thì hub không biết lượt đang là bước job nào: sổ làm-một-lần không bảo vệ, và luật
    Đội Ads "bước bật camp chỉ bật đúng mã đã duyệt" không áp được cho Codex, Grok, Muse..."""
    job = str(getattr(claude_cli_obj, "javis_job", "") or "")
    if not job:
        return {}
    import once_ledger
    return {once_ledger.JOB_HEADER: job}


def apply(deps, cli, mode: str = None, tag: str = None):
    """Dùng ở các nơi chạy nền sau khi đã dựng xong engine Claude.

    deps.aux_swap được main tiêm; thiếu nó (unit test dựng deps tối giản) thì rơi về cách
    cũ - chỉ đặt model - nên test cũ không phải sửa và hành vi không đổi.
    """
    fn = getattr(deps, "aux_swap", None)
    if fn:
        return fn(cli, mode=mode, tag=tag)
    getter = getattr(deps, "aux_model", None)
    if getter:
        cli.model = getter() or None
    return cli


def _ghi_duong_nen(chuoi, e, loi_dau) -> None:
    """Việc nền xong bằng mắt nào: mắt đầu thì xoá dòng "chạy tạm", mắt sau thì ghi lại để trang Bộ
    não AI nói "mô hình nền đang hết lượt, việc nền chạy tạm bằng X" (26.10.309)."""
    try:
        import thu_tu_dung
        if chuoi and e is chuoi[0]:
            thu_tu_dung.ghi_nen_tam("")
        else:
            thu_tu_dung.ghi_nen_tam(getattr(e, "provider", "") or ("anthropic-cli" if type(e).__name__ == "ClaudeSDK" else type(e).__name__),
                                    getattr(e, "model", "") or "", loi_dau)
    except Exception:  # noqa: BLE001
        pass


def _ghi_het_luot_nen(e, loi) -> None:
    """Mắt gói thuê bao gãy vì hết lượt: ghi cho Thứ tự dùng để chat cũng né nhà đó tới giờ mở lại."""
    try:
        import limit_learner
        import thu_tu_dung
        prov = getattr(e, "provider", "") if isinstance(getattr(e, "provider", ""), str) else ""
        prov = prov or ("openai-oauth" if type(e).__name__ == "CodexCLI" else "anthropic-cli")
        hint = limit_learner.ENGINE_HINT_BY_PROVIDER.get(prov)
        if not hint:
            return
        lim = limit_learner.parse_subscription_limit(str(loi or ""), engine_hint=hint)
        if lim:
            thu_tu_dung.ghi_het_luot(prov, float(getattr(lim, "reset_epoch", 0) or 0))
    except Exception:  # noqa: BLE001
        pass


# Gói thuê bao: hạn mức tính theo TÀI KHOẢN chứ không theo model, nên mỗi nhà chỉ một bước.
_MOT_LAN = (CLAUDE, CODEX, GROK_CLI, MUSE_CLI, COPILOT_CLI, KIMI_CLI, ANTIGRAVITY, *NAO_CLI_MOI)
# Mức Effort của MinMin -> cờ `--effort` của Claude Code (cùng bảng main._CLI_EFFORT).
_CLI_EFFORT = {"low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh", "ultra": "max"}


def _mat_cho_buoc(buoc: dict, cli, mode, tag, codex_profile, settings, da_dung_claude: list):
    """Engine cho MỘT bước của chuỗi việc nền, hoặc None khi bước đó không chạy được trên máy này."""
    prov = buoc.get("provider") or CLAUDE
    sp = {"provider": prov, "model": buoc.get("model") or ""}
    muc = buoc.get("reasoning") or "off"
    if prov == CLAUDE:
        if da_dung_claude:
            return None
        da_dung_claude.append(cli)
        cli.model = sp["model"] or None
        eff = _CLI_EFFORT.get(muc)
        if eff and buoc.get("buoc") == "nen":
            try:
                import claude_cli
                if claude_cli.co_co("--effort"):
                    cli.effort = eff
            except Exception:  # noqa: BLE001 - CLI cũ không có cờ thì chạy như Off
                pass
        return cli
    ok, why = availability(sp, settings)
    if not ok:
        print(f"[aux] {why} → bỏ bước {prov}.", file=sys.stderr)
        return None
    try:
        if prov == CODEX:
            return _build_codex(sp, cli, mode, tag, codex_profile)
        if prov == GROK_CLI:
            return _build_grok(sp, cli, mode, tag)
        if prov == MUSE_CLI:
            return _build_muse(sp, cli, mode, tag)
        if prov == COPILOT_CLI:
            return _build_copilot(sp, cli, mode, tag)
        if prov in NAO_CLI_MOI:
            return _build_nao_cli(sp, cli, mode, tag)
        if prov == KIMI_CLI:
            return _build_kimi(sp, cli, mode, tag)
        if prov == ANTIGRAVITY:
            return _build_antigravity(sp, cli, mode, tag)
        if prov in API_PROVIDERS:
            e = _build_api(sp, cli, mode, tag)
            e.reasoning = muc
            return e
    except Exception as exc:  # noqa: BLE001 - một bước hỏng không được kéo các bước khác chết theo
        print(f"[aux router] không dựng được bước {prov}: {type(exc).__name__}: {exc}", file=sys.stderr)
    return None


def swap(cli, mode: str = None, tag: str = None, spec: dict = None,
         codex_profile=None, settings: dict = None):
    """Engine Claude đã dựng -> ROUTER việc nền theo Thứ tự dùng (26.10.309).

    Thứ tự: mô hình việc nền (hoặc `spec`, ví dụ model riêng của trợ lý) -> Dự phòng 1, 2... của
    trang Bộ não AI, mỗi bước chạy cấu hình mặc định của nhà đó -> MAIN sau cùng. Gói thuê bao chỉ
    một bước mỗi nhà. Không tự chen Claude hay OpenRouter free vào khi chúng không có trong thứ tự.

    Mọi mức quyền dùng cùng chuỗi: mắt nào ĐÃ gọi công cụ rồi mới gãy thì chuỗi DỪNG (xem
    `_FallbackChain.query`), nên không việc nào bị làm hai lần. Trước bản này mức full không có
    dự phòng vì lý do đó.

    Hỏng cấu hình kiểu gì cũng giữ việc nền sống: không dựng được mắt nào thì trả engine Claude.
    """
    try:
        import thu_tu_dung
        s = settings if settings is not None else cfgmod.read_settings()
        m = s.get("model", {}) or {}
        sp = spec if spec is not None else read_spec(s)
        dau = {"provider": sp.get("provider") or CLAUDE, "model": sp.get("model") or "",
               "reasoning": (sp.get("reasoning") if sp.get("reasoning") in thu_tu_dung.MUC
                             else thu_tu_dung.nen(m)["reasoning"] if spec is None else "off")}
        # Cài đặt chưa có Thứ tự dùng: MAIN + mọi thẻ API đang có khoá (đúng thứ chuyển đổi sẽ lưu).
        ket_noi = None
        if not thu_tu_dung.da_luu(m):
            ket_noi = [main_spec(s)["provider"]] + [p for p in API_PROVIDERS if api_key_for(p, s)]
        cat = m.get("catalog") or {}
        mac_dinh = {}
        for p in thu_tu_dung.thu_tu(m, ket_noi):
            if p in API_PROVIDERS:
                mdl = thu_tu_dung.the(m, p).get("model") or ((cat.get(p) or [""])[0] if p != "openrouter" else "")
                mac_dinh[p] = {"model": mdl}
        chuoi, da_dung_claude = [], []
        for b in thu_tu_dung.chuoi_nen(m, ket_noi, dau=dau, mac_dinh=mac_dinh, mot_lan=_MOT_LAN):
            e = _mat_cho_buoc(b, cli, mode, tag, codex_profile, s, da_dung_claude)
            if e is not None:
                chuoi.append(e)
        if not chuoi:
            return cli
        return chuoi[0] if len(chuoi) == 1 else _FallbackChain(chuoi)
    except Exception as e:
        print(f"[aux swap] {e} → giữ engine Claude.", file=sys.stderr)
    return cli
