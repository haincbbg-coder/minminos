"""26.10.71: chọn nhiều hội thoại chuyển project, gom theo nền tảng AI, đổi nhãn brain, chép
skill/agent giữa các brain."""
from _paths import ROOT, SERVER  # noqa: E402,F401
import config
import brain_labels
import sessions


def _store(tmp_path):
    return sessions.SessionStore(tmp_path / "s.db") if hasattr(sessions, "SessionStore") else None


def test_nen_tang_cua_engine():
    f = sessions.nen_tang_cua_engine
    assert f("cli") == "Claude" and f("codex") == "ChatGPT" and f("grok-cli") == "Grok"
    assert f("antigravity-cli") == "Gemini" and f("voice-live:openai") == "Giọng nói (Live)"
    assert f("") is None and f(None) is None and f("lạ-hoắc") is None


def test_gom_theo_nen_tang_va_khong_dung_vao_cai_da_xep(tmp_path):
    st = _store(tmp_path)
    a = st.create_session(brain="brain", engine="cli")
    b = st.create_session(brain="brain", engine="codex")
    c = st.create_session(brain="brain", engine="cli")
    bot = st.create_session(brain="brain", engine="cli", channel="bot:uyen")
    tay = st.create_project("Việc riêng", brain="brain")
    st.set_project(c, tay)
    r = st.gom_theo_nen_tang("brain")
    assert r == {"Claude": 1, "ChatGPT": 1}
    pa = st.get_session(a)["project_id"]
    assert st.get_project(pa)["name"] == "Claude"
    assert st.get_session(c)["project_id"] == tay            # đã xếp tay thì giữ
    assert not st.get_session(bot)["project_id"]             # kênh bot không đụng
    assert st.gom_theo_nen_tang("brain") == {}               # chạy lại không đổi gì


def test_get_or_create_tu_xep_khi_tao_moi_nhung_khong_xep_lai(tmp_path):
    st = _store(tmp_path)
    sid = st.get_or_create(None, brain="brain", engine="cli", model=None)
    pid = st.get_session(sid)["project_id"]
    assert pid and st.get_project(pid)["name"] == "Claude"
    st.set_project(sid, "")                                   # người dùng gỡ tay
    st.get_or_create(sid, brain="brain", engine="cli", model=None)
    assert not st.get_session(sid)["project_id"]              # lượt sau không xếp lại


def test_set_project_many(tmp_path):
    st = _store(tmp_path)
    ids = [st.create_session(brain="brain", engine="x") for _ in range(5)]
    p = st.create_project("P", brain="brain")
    assert st.set_project_many(ids[:3] + ["khong-co"], p) == 3
    assert [bool(st.get_session(i)["project_id"]) for i in ids] == [True] * 3 + [False] * 2
    assert st.set_project_many(ids[:2], "") == 2
    assert st.set_project_many([], p) == 0


def test_nhan_brain_doi_va_xoa(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "STATE_DIR", tmp_path)
    assert brain_labels.dat("Brain Default", "  Kho   chính ") == "Kho chính"
    assert brain_labels.doc() == {"Brain Default": "Kho chính"}
    assert brain_labels.dat("Brain Default", "") == ""
    assert brain_labels.doc() == {}
    assert brain_labels.dat("X", "X") == ""                   # trùng tên thư mục = không cần nhãn
    assert len(brain_labels.dat("X", "a" * 200)) == brain_labels.MAX_DAI


def test_chep_va_chuyen_skill_agent_giua_brain(monkeypatch, tmp_path):
    import importlib
    import main
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main, "BRAINS_DIR", str(tmp_path))
    for n in ("A", "B"):
        main._ensure_brain_scaffold(tmp_path / n)
    (tmp_path / "A" / "agents").mkdir(exist_ok=True)
    (tmp_path / "A" / "agents" / "viet-mail.md").write_text(
        "---\nname: Viết mail\ngroup: Content\n---\nViết email.", encoding="utf-8")
    sk = tmp_path / "A" / "skills" / "bao-gia"
    sk.mkdir(parents=True)
    (sk / "SKILL.md").write_text("---\nname: bao-gia\ndescription: Báo giá\ngroup: Sales\n---\nthân", encoding="utf-8")
    cl = TestClient(main.app, base_url="http://localhost")
    fa, fb = str(tmp_path / "A"), str(tmp_path / "B")
    r = cl.post("/brains/copy-items", data={"from_brain": fa, "to_brain": fb, "kind": "agent",
                                              "slugs": "viet-mail"}).json()
    assert r["ok"] and "agent:viet-mail" in r["imported"]
    assert (tmp_path / "B" / "agents" / "viet-mail.md").is_file()
    assert (tmp_path / "A" / "agents" / "viet-mail.md").is_file()            # copy giữ nguồn
    r = cl.post("/brains/copy-items", data={"from_brain": fa, "to_brain": fb, "kind": "skill",
                                              "slugs": "bao-gia", "mode": "move"}).json()
    assert r["ok"] and r["da_xoa_o_nguon"] == ["bao-gia"]
    assert (tmp_path / "B" / "skills" / "bao-gia" / "SKILL.md").is_file()
    assert not (tmp_path / "A" / "skills" / "bao-gia").exists()              # move xoá nguồn
    r = cl.post("/brains/copy-items", data={"from_brain": fa, "to_brain": fa, "kind": "agent",
                                              "slugs": "viet-mail"})
    assert r.status_code == 400                                              # cùng brain thì từ chối
    r = cl.post("/brains/copy-items", data={"from_brain": fa, "to_brain": fb, "kind": "agent",
                                              "slugs": "../x"})
    assert r.status_code == 400                                              # slug bẩn
