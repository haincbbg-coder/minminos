"""test_be_khoa.py - bể khoá xoay vòng cho nhà API (26.10.161)."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import ROOT, SERVER  # noqa: E402,F401
import be_khoa as bk  # noqa: E402
import engine  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:200] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


bk.xoa_trang_thai()
mcfg = {"openrouter_key": "sk-A", "be_khoa": {"openrouter": ["sk-B", "sk-A", "", "sk-C"]}}
ks = bk.danh_sach("openrouter", mcfg, "sk-A")
check("danh_sach: khoá chính đứng đầu, bỏ trùng và rỗng", ks == ["sk-A", "sk-B", "sk-C"], ks)
check("danh_sach: nhà không khai thì chỉ khoá chính", bk.danh_sach("gemini", mcfg, "g1") == ["g1"])
check("nhan: 4 ký tự cuối", bk.nhan("sk-ABCD1234") == "…1234")

# xoay vòng đều
bk.xoa_trang_thai()
thu = [bk.chon("openrouter", ks, now=100.0) for _ in range(4)]
check("chon: xoay vòng A B C A", thu == ["sk-A", "sk-B", "sk-C", "sk-A"], thu)

# 429 -> nghỉ, chọn khoá khác
bk.xoa_trang_thai()
nghi = bk.bao_loi("openrouter", "sk-A", 429, cho=10, now=100.0)
check("bao_loi 429: nghỉ ít nhất 60s", nghi == 60)
check("dang_nghi: A nghỉ, B không", bk.dang_nghi("openrouter", "sk-A", now=120.0) and not bk.dang_nghi("openrouter", "sk-B", now=120.0))
check("chon: bỏ qua khoá đang nghỉ", bk.chon("openrouter", ks, now=120.0) != "sk-A")
check("hết nghỉ thì dùng lại", not bk.dang_nghi("openrouter", "sk-A", now=200.0))
check("bao_loi 401: nghỉ 1 giờ", bk.bao_loi("openrouter", "sk-B", 401, now=100.0) == bk.NGHI_SAI_KHOA)
check("bao_loi 500: không thuộc về khoá", bk.bao_loi("openrouter", "sk-C", 500, now=100.0) == 0)
check("lỗi lặp lại thì nghỉ dài dần", bk.bao_loi("openrouter", "sk-A", 429, now=300.0) == 120)
bk.bao_ok("openrouter", "sk-A")
check("bao_ok xoá đếm lỗi", bk.bao_loi("openrouter", "sk-A", 429, now=100000.0) == 60)

# tất cả nghỉ -> khoá hết nghỉ sớm nhất
bk.xoa_trang_thai()
for k, n in (("sk-A", 100), ("sk-B", 50), ("sk-C", 80)):
    bk._tt("openrouter", k)["nghi_den"] = n
check("tất cả nghỉ: lấy khoá hết nghỉ sớm nhất", bk.chon("openrouter", ks, now=0.0) == "sk-B")

# Xoay
bk.xoa_trang_thai()
x = bk.Xoay("openrouter", ks)
k1 = x.khoa()
check("Xoay.loi 429 -> đổi khoá", x.loi({"ma": 429, "content": "rate"}) and x.khoa() != k1)
check("Xoay.loi 500 -> không đổi", not x.loi({"ma": 500}))
k2 = x.khoa()
x.loi({"ma": 429}); k3 = x.khoa()
check("đổi tiếp sang khoá thứ ba", k3 not in (k1, k2))
check("hết khoá thì không đổi nữa", not x.loi({"ma": 429}))
check("một khoá thì Xoay không đổi", not bk.Xoay("openrouter", ["chỉ-một"]).loi({"ma": 429}))

# thu_lai_khi_tam_thoi với xoay: 401 (không tạm thời) vẫn được gọi lại bằng khoá khác
bk.xoa_trang_thai()
goi = []


async def _chay():
    x = bk.Xoay("openrouter", ["k1", "k2", "k3"])

    async def _stream():
        k = x.khoa()
        goi.append(k)
        if k == "k1":
            yield {"type": "error", "content": "OpenRouter 401: bad key", "ma": 401}
            return
        if k == "k2":
            yield {"type": "error", "content": "OpenRouter 429: slow", "ma": 429, "tam_thoi": True, "cho": 30}
            return
        yield {"type": "meta", "model": "m"}
        yield {"type": "text", "content": "xong"}

    ra = []
    async for ev in engine.thu_lai_khi_tam_thoi(lambda: _stream(), so_lan=1, nhan="t", xoay=x):
        ra.append(ev)
    return ra


ra = asyncio.run(_chay())
check("retry+xoay: k1 401 -> k2 429 -> k3 trả lời", goi == ["k1", "k2", "k3"], goi)
check("retry+xoay: người đọc chỉ thấy câu trả lời, không thấy lỗi", [e["type"] for e in ra] == ["meta", "text"], ra)
check("retry+xoay: khoá vấp được ghi nghỉ", bk.dang_nghi("openrouter", "k1") and bk.dang_nghi("openrouter", "k2") and not bk.dang_nghi("openrouter", "k3"))

# ev_loi_http luôn mang `ma`
ev = engine.ev_loi_http("X", 401, "bad")
check("ev_loi_http: 401 có ma, không tam_thoi", ev.get("ma") == 401 and not ev.get("tam_thoi"))

# thong_ke không lộ khoá
tk = bk.thong_ke(mcfg, lambda p: "sk-A" if p == "openrouter" else "")
check("thong_ke: chỉ nhà có bể, nhãn 4 ký tự", list(tk) == ["openrouter"] and all(len(k["nhan"]) <= 5 for k in tk["openrouter"]["khoa"]), tk)
check("thong_ke: không chứa khoá đầy đủ", "sk-ABCD" not in str(tk))

# ---------- 26.10.167: xAI Grok API là nhà có bể khoá, khác hẳn Grok Build ----------
check("xai có bể khoá", "xai" in bk.API_CO_BE and "grok-cli" not in bk.API_CO_BE)
import aux_engine as _ax
check("xai là nhà API của việc nền với trường khoá riêng", "xai" in _ax.API_PROVIDERS and _ax._KEY_FIELD.get("xai") == "xai_api_key")
check("engine có xai_stream và xai_chat_with_mcp", hasattr(engine, "xai_stream") and hasattr(engine, "xai_chat_with_mcp") and engine.XAI_URL.startswith("https://api.x.ai/v1/"))
check("xai: grok-3-mini và grok-4 nhận reasoning, bản non-reasoning thì không",
      engine._xai_is_reasoning("grok-3-mini") and engine._xai_is_reasoning("grok-4") and not engine._xai_is_reasoning("grok-4-fast-non-reasoning"))


# ---------- 26.10.170: Meta Muse API ----------
check("meta có bể khoá và là nhà API của việc nền", "meta" in bk.API_CO_BE and "meta" in _ax.API_PROVIDERS and _ax._KEY_FIELD.get("meta") == "meta_api_key")
check("engine có meta_stream/meta_chat_with_mcp trỏ api.meta.ai", hasattr(engine, "meta_stream") and hasattr(engine, "meta_chat_with_mcp") and engine.META_URL == "https://api.meta.ai/v1/chat/completions")


if fails:
    print("ĐỎ", len(fails), fails)
    sys.exit(1)
print("OK - test_be_khoa: tất cả pass")
