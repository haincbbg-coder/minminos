"""MinMin Tay (0.64.87): chương trình nhỏ trên máy Windows của người dùng, nhận lệnh cử chỉ từ HUD.

Kiểm: phải có mã ghép nối, chỉ nhận trang được phép, preflight cho Chrome (mạng nội bộ), lệnh
lạ bị từ chối, số liệu bị kẹp trong giới hạn. Chạy chế độ thử (MayThu) nên không bấm gì thật.
"""
from _paths import ROOT, SERVER  # noqa: F401
import importlib.util
import json
import os
import tempfile
import threading
import urllib.request
import urllib.error

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="minmin-tay-")
spec = importlib.util.spec_from_file_location("minmin_tay", os.path.join(ROOT, "dashboard", "hud", "tay", "minmin-tay.py"))
tay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tay)

# Mã ghép nối: sinh một lần, đọc lại giống nhau, tạo mới thì khác
ma = tay.lay_ma()
assert len(ma) >= 16 and tay.lay_ma() == ma
ma2 = tay.lay_ma(tao_moi=True)
assert ma2 != ma
ma = ma2

# Kiểm lệnh
assert tay.kiem_lenh({"t": "move", "x": 1.7, "y": -3}) == {"t": "move", "x": 1.0, "y": 0.0}
assert tay.kiem_lenh({"t": "scroll", "n": 99}) == {"t": "scroll", "n": 10}
assert tay.kiem_lenh({"t": "zoom", "d": -1}) == {"t": "zoom", "d": -1}
assert tay.kiem_lenh({"t": "key", "k": "RIGHT"}) == {"t": "key", "k": "right"}
for xau in ({"t": "type", "text": "rm -rf"}, {"t": "key", "k": "f4"}, [], {"t": "run"}):
    try:
        tay.kiem_lenh(xau)
        raise AssertionError(f"phải từ chối {xau}")
    except ValueError:
        pass

may = tay.MayThu()
NGUON = "https://minmin.example.vn"
sv = tay.tao_may_chu(ma, may, [NGUON], cong=0)
cong = sv.server_address[1]
threading.Thread(target=sv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{cong}"


def goi(duong, method="GET", body=None, headers=None):
    req = urllib.request.Request(URL + duong, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, dict(e.headers), json.loads(raw) if raw else {}


try:
    # Preflight của Chrome: trang https gọi vào localhost
    code, h, _ = goi("/act", "OPTIONS", headers={"Origin": NGUON, "Access-Control-Request-Private-Network": "true"})
    assert code == 204 and h.get("Access-Control-Allow-Private-Network") == "true", h
    assert h.get("Access-Control-Allow-Origin") == NGUON and "x-minmin-token" in h.get("Access-Control-Allow-Headers", "")
    # Trang lạ: bị chặn
    code, _, _ = goi("/ping", headers={"Origin": "https://ke-xau.example", "x-minmin-token": ma})
    assert code == 403
    # Thiếu mã / sai mã
    assert goi("/ping", headers={"Origin": NGUON})[0] == 401
    assert goi("/ping", headers={"Origin": NGUON, "x-minmin-token": "sai"})[0] == 401
    code, _, j = goi("/ping", headers={"Origin": NGUON, "x-minmin-token": ma})
    assert code == 200 and j["ok"] and "thử" in j["man"]
    # Lệnh hợp lệ được làm, lệnh lạ bị từ chối, không có mã thì không làm gì
    ok = {"Origin": NGUON, "x-minmin-token": ma, "Content-Type": "application/json"}
    assert goi("/act", "POST", {"t": "scroll", "n": -2}, ok)[0] == 200
    assert goi("/act", "POST", {"t": "type", "text": "x"}, ok)[0] == 400
    assert goi("/act", "POST", {"t": "click"}, {"Origin": NGUON, "Content-Type": "application/json"})[0] == 401
    assert may.da_lam == [{"t": "scroll", "n": -2}], may.da_lam
    # Chỉ nghe localhost
    assert sv.server_address[0] == "127.0.0.1"
finally:
    sv.shutdown()
    sv.server_close()
print("ok")
