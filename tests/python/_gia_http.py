"""HTTP giả cho test các cầu nối API tự bọc (server/*_mcp.py dùng ket_noi_api.goi).

    from _gia_http import GiaHttp
    gia = GiaHttp()
    gia.tra("/api/v2/shop/get_shop_info", {"shop_name": "A"})   # khớp theo chuỗi con của URL
    gia.lap()                                                     # thay httpx.AsyncClient
    ...
    gia.goi        # danh sách request đã gửi: dict(method, url, params, json, data, headers, content)

Không chạm mạng. Mỗi lần `tra` thêm một câu trả lời vào HÀNG ĐỢI của mẫu URL đó; hết hàng đợi thì
dùng lại câu cuối. Không khớp mẫu nào thì trả 599 để test lộ ra ngay request ngoài dự kiến.
"""
import json

import httpx


class _Resp:
    def __init__(self, code, body):
        self.status_code = code
        self._b = body
        # Thân dạng bytes = âm thanh/file nhị phân (cầu nối VieNeu): không có text, không phải JSON.
        self.content = body if isinstance(body, bytes) else (
            body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8"))
        self.text = "" if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body))
        self.headers = {}

    def json(self):
        if isinstance(self._b, (str, bytes)):
            raise ValueError("không phải JSON")
        return self._b


class GiaHttp:
    def __init__(self):
        self.mau = []        # [(chuỗi con, [(code, body)...])]
        self.goi = []
        self._goc = httpx.AsyncClient

    def tra(self, chuoi, body, code=200):
        for m, q in self.mau:
            if m == chuoi:
                q.append((code, body))
                return self
        self.mau.append((chuoi, [(code, body)]))
        return self

    def nem_loi(self, chuoi, exc):
        return self.tra(chuoi, exc, code=-1)

    def lap(self):
        gia = self

        class _Client:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def request(self, method, url, params=None, json=None, data=None, headers=None,
                              content=None):
                gia.goi.append({"method": method, "url": url, "params": params or {}, "json": json,
                                "data": data, "headers": headers or {}, "content": content})
                for m, q in sorted(gia.mau, key=lambda x: -len(x[0])):
                    if m in url:
                        code, body = q.pop(0) if len(q) > 1 else q[0]
                        if code == -1:
                            raise body
                        return _Resp(code, body)
                return _Resp(599, {"loi": "không có câu trả lời giả cho " + url})

            async def get(self, url, params=None, headers=None):
                return await self.request("GET", url, params=params, headers=headers)

            async def post(self, url, params=None, json=None, data=None, headers=None, content=None):
                return await self.request("POST", url, params=params, json=json, data=data,
                                          headers=headers, content=content)

        httpx.AsyncClient = _Client
        return self

    def go(self):
        httpx.AsyncClient = self._goc


class KiemTra:
    """Bộ đếm check() kiểu repo: in ok/FAIL, cuối file gọi ket_thuc()."""

    def __init__(self):
        self.loi = []

    def __call__(self, ten, dk, them=""):
        print(("ok   " if dk else "FAIL ") + ten + (f"  [{them}]" if them and not dk else ""))
        if not dk:
            self.loi.append(ten)

    def ket_thuc(self):
        import sys
        print(f"\n{'ĐỎ ' + str(len(self.loi)) if self.loi else 'XANH'}")
        sys.exit(1 if self.loi else 0)
