# -*- coding: utf-8 -*-
"""
mock_gdt.py - Máy chủ giả lập cổng hoadondientu.gdt.gov.vn để kiểm thử tool
KHÔNG cần internet/tài khoản thật. Chạy:  python tests/mock_gdt.py  (cổng 8765)
Trong app: đặt biến môi trường  TCT_BASE=http://127.0.0.1:8765/api  rồi chạy app.py
Captcha giả: luôn là "ABC12".
"""
from __future__ import annotations

import datetime as dt
import io
import json
import random
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

random.seed(7)
SELLERS = [("0100111948-061", "NGÂN HÀNG TMCP CÔNG THƯƠNG VIỆT NAM - CHI NHÁNH 12"),
           ("0316219359", "CÔNG TY TNHH TÔN SẮT MINH NGỌC HM"),
           ("0317906019", "CÔNG TY TNHH TM CHÍ CƯỜNG"),
           ("0310977980", "CÔNG TY TNHH THƯƠNG MẠI ĐẦU TƯ QUANG BÌNH")]
ME = ("0312739734", "CÔNG TY TNHH TM DV XÂY DỰNG PHÁT TRIỂN ĐẠI PHÚ")
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="150" height="50">'
       '<rect width="150" height="50" fill="#fff"/><text x="10" y="35" font-size="28" '
       'font-family="Arial" fill="#333">ABC12</text><path d="M0 25 L150 20" stroke="#999"/></svg>')


def gen_invoices(n_days=40):
    out = {"purchase": [], "sold": []}
    d0 = dt.date(2026, 1, 1)
    for i in range(n_days * 2):
        day = d0 + dt.timedelta(days=i % n_days * 2)
        seller = random.choice(SELLERS)
        loai = "purchase" if i % 3 else "sold"
        nb = seller if loai == "purchase" else ME
        nm = ME if loai == "purchase" else seller
        tien = random.choice([3000, 35000, 435000, 1831590, 18181958])
        thue = round(tien * 0.1) if tien != 670000 else 0
        out[loai].append({
            "nbmst": nb[0], "nbten": nb[1], "nmmst": nm[0], "nmten": nm[1],
            "khmshdon": 1, "khhdon": random.choice(["K26TBB", "C26TMN", "C26TQB"]),
            "shdon": 100000 + i, "tdlap": f"{day.isoformat()}T00:00:00.000Z",
            "tgtcthue": tien, "tgtthue": thue, "tgtttbso": tien + thue, "dvtte": "VND",
            "tthai": random.choice([1, 1, 1, 1, 2, 6]), "ttxly": random.choice([5, 5, 6]),
            "mccqt": f"M1-26-{random.randint(10**7, 10**8-1)}",
        })
    return out


DATA = gen_invoices()


def _fake_jwt():
    """Token giả có payload giống JWT (sub, name, exp 24h) để test lưu phiên."""
    import base64, time as _t
    p = base64.urlsafe_b64encode(json.dumps({"sub": ME[0], "name": ME[1], "exp": int(_t.time()) + 86400}).encode()).decode().rstrip("=")
    return f"x.{p}.y"


FAKE_JWT = _fake_jwt()


def make_zip(inv):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<HDon><DLHDon><TTChung><PBan>2.0.1</PBan><THDon>HÓA ĐƠN GIÁ TRỊ GIA TĂNG</THDon>
<KHMSHDon>{inv['khmshdon']}</KHMSHDon><KHHDon>{inv['khhdon']}</KHHDon><SHDon>{inv['shdon']}</SHDon>
<NLap>{inv['tdlap'][:10]}</NLap><DVTTe>VND</DVTTe><TGia>1</TGia><HTTToan>TM/CK</HTTToan></TTChung>
<NDHDon><NBan><Ten>{inv['nbten']}</Ten><MST>{inv['nbmst']}</MST><DChi>TP.HCM</DChi></NBan>
<NMua><Ten>{inv['nmten']}</Ten><MST>{inv['nmmst']}</MST><DChi>Bắc Giang</DChi></NMua>
<DSHHDVu><HHDVu><TChat>1</TChat><STT>1</STT><THHDVu>Phí dịch vụ &amp; hàng hóa A</THHDVu><DVTinh>Cái</DVTinh>
<SLuong>2</SLuong><DGia>{inv['tgtcthue']/2:.0f}</DGia><ThTien>{inv['tgtcthue']}</ThTien><TSuat>10%</TSuat></HHDVu>
</DSHHDVu><TToan><TgTCThue>{inv['tgtcthue']}</TgTCThue><TgTThue>{inv['tgtthue']}</TgTThue>
<TgTTTBSo>{inv['tgtttbso']}</TgTTTBSo><TgTTTBChu>Một số tiền</TgTTTBChu></TToan></NDHDon></DLHDon>
<MCCQT>{inv['mccqt']}</MCCQT></HDon>"""
    html = f"<html><body><h2>Hóa đơn {inv['khhdon']} số {inv['shdon']}</h2><p>{inv['nbten']}</p></body></html>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{inv['nbmst']}_{inv['shdon']}.xml", xml)
        z.writestr("invoice.html", html)
    return buf.getvalue()


class H(BaseHTTPRequestHandler):
    calls = 0

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):  # im lặng
        pass

    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        H.calls += 1
        if u.path.endswith("/captcha"):
            return self._json({"key": "k123", "content": SVG})
        if self.headers.get("Authorization") != f"Bearer {FAKE_JWT}":
            return self._json({"message": "Unauthorized"}, 401)
        if not self.headers.get("request-id"):  # giống cổng thật: thiếu request-id -> 403
            return self._json({"status": 403, "message": "Hệ thống phát hiện hành vi không hợp lệ."}, 403)
        if H.calls % 17 == 0:  # thỉnh thoảng giả lập 429 để test retry
            self.send_response(429); self.send_header("Retry-After", "1"); self.end_headers(); return
        if "/invoices/purchase" in u.path or "/invoices/sold" in u.path:
            loai = "purchase" if "purchase" in u.path else "sold"
            if "sco-query" in u.path:
                return self._json({"datas": [], "total": 0, "state": None})
            search = q.get("search", [""])[0]
            import re
            d1 = dt.datetime.strptime(re.search(r"tdlap=ge=(\d\d/\d\d/\d{4})", search).group(1), "%d/%m/%Y").date()
            d2 = dt.datetime.strptime(re.search(r"tdlap=le=(\d\d/\d\d/\d{4})", search).group(1), "%d/%m/%Y").date()
            mt = re.search(r"ttxly==(\d+)", search); ttxly = mt.group(1) if mt else None
            ms = re.search(r"shdon==(\d+)", search); shdon = ms.group(1) if ms else None
            rows = [r for r in DATA[loai] if d1 <= dt.date.fromisoformat(r["tdlap"][:10]) <= d2
                    and (ttxly is None or str(r["ttxly"]) == ttxly)
                    and (shdon is None or str(r["shdon"]) == shdon)]
            size = int(q.get("size", ["50"])[0]); state = int(q.get("state", ["0"])[0] or 0)
            page = rows[state:state + size]
            nxt = state + size if state + size < len(rows) else None
            return self._json({"datas": page, "total": len(rows), "state": str(nxt) if nxt else None})
        if u.path.endswith("/invoices/export-xml"):
            for loai in DATA:
                for r in DATA[loai]:
                    if str(r["shdon"]) == q["shdon"][0] and r["khhdon"] == q["khhdon"][0]:
                        b = make_zip(r)
                        self.send_response(200); self.send_header("Content-Type", "application/zip"); self.end_headers(); self.wfile.write(b); return
            return self._json({"message": "not found"}, 200)
        if u.path.endswith("/invoices/detail"):
            return self._json({"hdhhdvu": []})
        self._json({"message": "unknown"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        if self.path.endswith("/security-taxpayer/authenticate"):
            if body.get("cvalue", "").upper() == "ABC12" and body.get("password") == "123456":
                return self._json({"token": FAKE_JWT})
            return self._json({"message": "Sai mật khẩu hoặc captcha"}, 400)
        self._json({"message": "unknown"}, 404)


def serve(port=8765):
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)  # đa luồng để test tải song song
    print(f"Mock GDT chạy tại http://127.0.0.1:{port}/api  (MST bất kỳ, mật khẩu 123456, captcha ABC12)")
    srv.serve_forever()


if __name__ == "__main__":
    serve()
