"""26.10.136: ghim TAY vs đóng dấu tự động (pinned_manual) - bộ định tuyến chỉ nhường ghim tay.

    python tests/run.py dinh_tuyen_phien
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import os
import sys
import tempfile

import sessions  # noqa: E402

fails = []


def check(name, cond, them=""):
    print(("ok   " if cond else "FAIL ") + name + (("  [" + str(them)[:200] + "]") if not cond and them else ""))
    if not cond:
        fails.append(name)


st = sessions.SessionStore(os.path.join(tempfile.mkdtemp(), "s.db"))
sid = st.create_session(brain="brain")
check("phiên mới: pinned_manual = 0", int(st.get_session(sid).get("pinned_manual") or 0) == 0)
st.set_pinned_model(sid, "openrouter", "m1", manual=True)
check("ghim tay -> 1", st.get_session(sid)["pinned_manual"] == 1)
st.set_pinned_model(sid, "openrouter", "m2", manual=None)
check("tự chữa model (manual=None) giữ nguyên cờ", st.get_session(sid)["pinned_manual"] == 1
      and st.get_session(sid)["pinned_model"] == "m2")
st.set_pinned_model(sid, "openrouter", "m3", manual=False)
check("đóng dấu tự động -> 0", st.get_session(sid)["pinned_manual"] == 0)
st.set_pinned_model(sid, "", "", manual=True)
r = st.get_session(sid)
check("gỡ ghim -> cờ về 0, provider rỗng", r["pinned_manual"] == 0 and not r["pinned_provider"])

# Luật của bộ chia (hàm thuần trong dinh_tuyen): ghim tay thì không áp dụng - kiểm bằng quyết định
import dinh_tuyen as dt  # noqa: E402
CFG = {"enabled": True, "bac": {"nhe": {"provider": "groq", "model": "x"}}}
check("bộ chia có quyết định khi bật", dt.quyet_dinh("chào em", CFG)["ap_dung"])
check("không dùng gạch dài", "—" not in open(os.path.join(ROOT, "server/sessions.py"), encoding="utf-8").read())

if fails:
    print(f"ĐỎ {len(fails)}"); sys.exit(1)
print("Tất cả xanh.")
