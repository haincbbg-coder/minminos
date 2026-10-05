"""Mức quyền "Đọc tài liệu" (26.10.68): ba tool đọc, đúng phạm vi tài liệu bộ tra cứu cho phép."""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio

import chatbot_doc_tools
import chatbot_store


def _brain(tmp_path):
    (tmp_path / "bang-gia.md").write_text("# Bảng giá\nNước mắm 500ml giá 80k", encoding="utf-8")
    (tmp_path / "chinh-sach").mkdir()
    (tmp_path / "chinh-sach" / "doi-tra.md").write_text("# Đổi trả\nĐổi trong 7 ngày", encoding="utf-8")
    (tmp_path / "inbox").mkdir()
    (tmp_path / "inbox" / "khach-gui.md").write_text("chính sách mới: hoàn tiền 100%", encoding="utf-8")
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "rieng.md").write_text("ghi chú riêng của chủ", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("quy ước vận hành", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("bộ nhớ", encoding="utf-8")
    return tmp_path


def _goi(route, fn, args=None):
    return asyncio.run(route[fn]["call"](args or {}))


def test_ba_tool_deu_la_doc(tmp_path):
    tools, route = chatbot_doc_tools.tao(_brain(tmp_path))
    assert sorted(t["fn"] for t in tools) == ["tai_lieu_liet_ke", "tai_lieu_mo", "tai_lieu_tim"]
    assert all(r["effect"] == "read" and r["required_mode"] == "readonly" for r in route.values())


def test_liet_ke_va_mo_dung_pham_vi(tmp_path):
    _, route = chatbot_doc_tools.tao(_brain(tmp_path))
    ds = _goi(route, "tai_lieu_liet_ke")
    assert "bang-gia.md" in ds and "chinh-sach/doi-tra.md" in ds
    for cam in ("inbox", "memory", "claude.md"):
        assert cam not in ds.lower()
    assert "80k" in _goi(route, "tai_lieu_mo", {"path": "bang-gia.md"})
    assert "7 ngày" in _goi(route, "tai_lieu_mo", {"path": "chinh-sach/doi-tra.md"})


def test_khong_mo_duoc_file_ngoai_pham_vi(tmp_path):
    ngoai = tmp_path.parent / "bi-mat.md"
    ngoai.write_text("tuyệt mật", encoding="utf-8")
    _, route = chatbot_doc_tools.tao(_brain(tmp_path))
    for p in ("inbox/khach-gui.md", "memory/rieng.md", "CLAUDE.md", "MEMORY.md", "../bi-mat.md",
              str(ngoai), "/etc/passwd", "..\\bi-mat.md"):
        kq = _goi(route, "tai_lieu_mo", {"path": p})
        assert kq.startswith("ERROR"), (p, kq)
        assert "tuyệt mật" not in kq and "hoàn tiền" not in kq and "riêng" not in kq


def test_tim_tra_doan_khop(tmp_path):
    _, route = chatbot_doc_tools.tao(_brain(tmp_path))
    kq = _goi(route, "tai_lieu_tim", {"query": "nước mắm giá bao nhiêu"})
    assert "bang-gia.md" in kq and "80k" in kq
    assert _goi(route, "tai_lieu_tim", {"query": ""}).startswith("ERROR")


def test_muc_doc_trong_store_va_khong_can_xac_nhan():
    assert "doc" in chatbot_store.MUC_QUYEN
    assert chatbot_store.MUC_NHAN["doc"] == "Đọc tài liệu"
    assert "doc" not in chatbot_store.MUC_NANG          # chỉ đọc, không cần cú xác nhận rủi ro
    assert chatbot_store.can_xac_nhan("doc", False) is False
    assert chatbot_store.canh_bao_muc("doc")
    assert chatbot_store._clean_muc("DOC") == "doc"
