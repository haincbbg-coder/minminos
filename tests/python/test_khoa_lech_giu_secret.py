"""Khoá mã hoá lệch (dựng lại volume, mất .secret_key) không được làm mất secret đã lưu.

Trước đây read_settings giải mã ra "" khi khoá lệch, rồi MỘT lần lưu cài đặt bất kỳ ghi "" đè lên
bản mã cũ nên key API và token mất vĩnh viễn. Giờ write_settings giữ nguyên bản mã cũ.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import json

import config
import secrets_store
from cryptography.fernet import Fernet


def _dung(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")
    monkeypatch.setattr(secrets_store, "_fernet", Fernet(Fernet.generate_key()))
    return tmp_path / "settings.json"


def test_cannot_decrypt_phan_biet_dung_sai(monkeypatch, tmp_path):
    _dung(tmp_path, monkeypatch)
    tot = secrets_store.encrypt("abc")
    assert tot.startswith("enc:")
    assert secrets_store.cannot_decrypt(tot) is False
    monkeypatch.setattr(secrets_store, "_fernet", Fernet(Fernet.generate_key()))
    assert secrets_store.cannot_decrypt(tot) is True
    assert secrets_store.cannot_decrypt("") is False
    assert secrets_store.cannot_decrypt("plain:x") is False


def test_khoa_lech_luu_cai_dat_khac_van_giu_ban_ma(monkeypatch, tmp_path):
    p = _dung(tmp_path, monkeypatch)
    config.write_settings({"model": {"openai_api_key": "sk-that"}})
    cu = json.loads(p.read_text(encoding="utf-8"))["model"]["openai_api_key"]
    assert cu.startswith("enc:")
    # khoá bị đổi: đọc ra rỗng
    monkeypatch.setattr(secrets_store, "_fernet", Fernet(Fernet.generate_key()))
    cfg = config.read_settings()
    assert not cfg.get("model", {}).get("openai_api_key")
    cfg.setdefault("model", {})["ten_khac"] = "x"
    config.write_settings(cfg)
    moi = json.loads(p.read_text(encoding="utf-8"))["model"]["openai_api_key"]
    assert moi == cu, "bản mã cũ phải được giữ nguyên"


def test_khoa_dung_xoa_key_van_xoa_that(monkeypatch, tmp_path):
    p = _dung(tmp_path, monkeypatch)
    config.write_settings({"model": {"openai_api_key": "sk-that"}})
    cfg = config.read_settings()
    cfg["model"]["openai_api_key"] = ""
    config.write_settings(cfg)
    assert not json.loads(p.read_text(encoding="utf-8"))["model"].get("openai_api_key")


def test_khoa_lech_key_moi_go_van_duoc_luu(monkeypatch, tmp_path):
    p = _dung(tmp_path, monkeypatch)
    config.write_settings({"model": {"openai_api_key": "sk-cu"}})
    monkeypatch.setattr(secrets_store, "_fernet", Fernet(Fernet.generate_key()))
    cfg = config.read_settings()
    cfg["model"]["openai_api_key"] = "sk-moi"
    config.write_settings(cfg)
    luu = json.loads(p.read_text(encoding="utf-8"))["model"]["openai_api_key"]
    assert luu.startswith("enc:") and secrets_store.decrypt(luu) == "sk-moi"
