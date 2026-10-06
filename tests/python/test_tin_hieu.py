"""Tín hiệu dùng (26.10.69): ghi cách dùng MinMin, không nội dung, không đổi hành vi agent."""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json

import config
import tin_hieu


def _dung(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DIR", tmp_path)


def test_ghi_va_tom_tat_trang_hay_dung(monkeypatch, tmp_path):
    _dung(tmp_path, monkeypatch)
    for _ in range(3):
        assert tin_hieu.ghi("mo_trang", "chat")
    assert tin_hieu.ghi("mo_trang", "agents")
    assert tin_hieu.ghi("gui_chat")
    t = tin_hieu.tom_tat()
    assert t["hay_dung"][0] == {"id": "chat", "so_lan": 3}
    assert t["hay_dung"][1]["id"] == "agents"
    assert t["so_tin_chat"] == 1


def test_loai_la_va_doi_tuong_ban_bi_tu_choi(monkeypatch, tmp_path):
    _dung(tmp_path, monkeypatch)
    assert not tin_hieu.ghi("loai_la", "x")
    assert not tin_hieu.ghi("mo_trang", "Xin chào, nội dung tin nhắn dài")
    assert not tin_hieu.ghi("mo_trang", "../../etc/passwd")
    assert not (tmp_path / "tin-hieu.jsonl").exists()


def test_khong_ghi_noi_dung_chi_ghi_gio_loai_doi_tuong(monkeypatch, tmp_path):
    _dung(tmp_path, monkeypatch)
    tin_hieu.ghi("gui_chat")
    dong = json.loads((tmp_path / "tin-hieu.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert set(dong) == {"t", "loai", "dt"}


def test_tin_hieu_cu_hon_cua_so_bi_bo(monkeypatch, tmp_path):
    _dung(tmp_path, monkeypatch)
    p = tmp_path / "tin-hieu.jsonl"
    p.write_text(json.dumps({"t": 1, "loai": "mo_trang", "dt": "cu"}) + "\nrac khong phai json\n",
                 encoding="utf-8")
    tin_hieu.ghi("mo_trang", "moi")
    ids = [x["id"] for x in tin_hieu.tom_tat()["hay_dung"]]
    assert ids == ["moi"]


def test_file_tu_cat_khi_qua_dai(monkeypatch, tmp_path):
    _dung(tmp_path, monkeypatch)
    monkeypatch.setattr(tin_hieu, "MAX_DONG", 10)
    for i in range(60):
        tin_hieu.ghi("mo_trang", "p%d" % i)
    assert len((tmp_path / "tin-hieu.jsonl").read_text(encoding="utf-8").splitlines()) <= 60
    assert len((tmp_path / "tin-hieu.jsonl").read_text(encoding="utf-8").splitlines()) < 60


def test_route_ghi_va_tom_tat(monkeypatch, tmp_path):
    _dung(tmp_path, monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import routes.tin_hieu as r
    app = FastAPI()
    r.register(app)
    c = TestClient(app)
    assert c.post("/tin-hieu", json={"loai": "mo_trang", "doi_tuong": "chat"}).json()["ok"] is True
    assert c.post("/tin-hieu", json={"loai": "bay"}).status_code == 400
    assert c.post("/tin-hieu", content="khong json").status_code == 400
    assert c.get("/tin-hieu/tom-tat").json()["hay_dung"][0]["id"] == "chat"
