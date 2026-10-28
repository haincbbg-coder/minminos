"""Bộ chạy nền của hòm sự kiện webhook (26.10.273).

Mỗi sự kiện đã lưu (webhook_su_kien) đi qua: lọc -> từng hành động -> xong / thử lại / chặn.

Hành động của một webhook (`hanh_dong`, mặc định `[{"loai": "ai"}]` như trước bản này):
  - `ai`: MinMin chạy việc chủ giao trên TRỌN sự kiện, theo mức quyền của webhook, rồi báo kết quả.
  - `chuyen_tiep`: gửi nguyên thân sang một địa chỉ https khác (Apps Script, máy khác), KHÔNG gọi AI.
    Kèm header `X-MinMin-Delivery` cố định cho mỗi (sự kiện, hành động) để bên nhận tự bỏ trùng.
    Chặn địa chỉ nội bộ (SSRF), không theo chuyển hướng.

Mỗi hành động nhớ kết quả riêng trong sự kiện: chạy lại chỉ làm phần chưa xong, không gửi hai lần.

Thử lại: lỗi tạm thời (mạng, 5xx, 408, 429, AI hết lượt) hẹn lại theo bậc 30 giây, 2, 10, 30 phút,
2 giờ; 429 có `Retry-After` thì chờ ít nhất ngần ấy. Hết lượt thử hoặc lỗi hẳn (4xx khác) thì sự
kiện bị CHẶN, giữ nguyên thân, chủ xem lý do rồi bấm chạy lại.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional
from urllib.parse import urlparse

import webhook_su_kien as sk

BAC_CHO_S = (30, 120, 600, 1800, 7200)
LAN_THU_TOI_DA = len(BAC_CHO_S)
RETRY_AFTER_TOI_DA = 6 * 3600
NHIP_S = 2.0
SONG_SONG = 2
CHUYEN_TIEP_TIMEOUT = 20
LOAI = ("ai", "chuyen_tiep")


class LoiTam(Exception):
    """Lỗi tạm thời: thử lại sau `cho` giây (0 = theo bậc)."""

    def __init__(self, msg: str, cho: float = 0):
        super().__init__(msg)
        self.cho = cho


class LoiHan(Exception):
    """Lỗi hẳn: không thử lại, chặn chờ chủ."""


@dataclass
class ChayDeps:
    # webhook theo id (bản ĐẦY ĐỦ của kho, có loc/hanh_dong/muc_quyen), hoặc None
    lay_hook: Callable[[str], Optional[dict]]
    # chạy việc AI: (brain, lời nhắc, mức quyền) -> (kết quả, lỗi)
    chay_ai: Optional[Callable[[str, str, str], Awaitable[tuple]]] = None
    # báo chủ một câu (hòm thư + Telegram)
    bao_chu: Optional[Callable[[str, str], Awaitable]] = None
    # gửi HTTP POST: (url, thân, header) -> (mã, header trả về). Test thay bằng bản giả.
    gui_http: Optional[Callable[[str, bytes, dict], Awaitable[tuple]]] = None
    # kiểm địa chỉ công khai (test thay)
    kiem_dia_chi: Optional[Callable[[str], Awaitable[str]]] = None
    clock: Callable[[], float] = field(default=time.time)


def chuan_hanh_dong(ds) -> list:
    if ds in (None, "", []):
        return [{"id": "ai", "loai": "ai"}]
    if not isinstance(ds, list) or len(ds) > 5:
        raise ValueError("hành động là danh sách, tối đa 5")
    out, da = [], set()
    for i, a in enumerate(ds):
        if not isinstance(a, dict):
            raise ValueError("mỗi hành động là một object")
        loai = str(a.get("loai") or "").strip()
        if loai not in LOAI:
            raise ValueError("loại hành động là ai hoặc chuyen_tiep")
        hid = str(a.get("id") or (loai if loai not in da else f"{loai}_{i}"))[:40]
        if hid in da:
            raise ValueError("hai hành động trùng id")
        da.add(hid)
        if loai == "chuyen_tiep":
            url = str(a.get("url") or "").strip()
            p = urlparse(url)
            if p.scheme != "https" or not p.hostname or p.port not in (None, 443) or len(url) > 500:
                raise ValueError("chuyển tiếp chỉ tới địa chỉ https:// cổng 443")
            out.append({"id": hid, "loai": loai, "url": url, "lap_an_toan": a.get("lap_an_toan") is True})
        else:
            out.append({"id": hid, "loai": loai})
    return out


def an_url(url: str) -> str:
    """Địa chỉ chuyển tiếp cho giao diện: chỉ tên máy (đường Apps Script chứa mã riêng)."""
    p = urlparse(str(url or ""))
    return f"https://{p.hostname}/…" if p.hostname else ""


async def kiem_dia_chi_cong_khai(url: str) -> str:
    """'' khi mọi địa chỉ của tên máy đều công khai; ngược lại là câu lỗi (SSRF)."""
    p = urlparse(url)
    try:
        ips = {ai[4][0] for ai in await asyncio.to_thread(
            socket.getaddrinfo, p.hostname, 443, 0, socket.SOCK_STREAM)}
    except Exception:
        return f"không phân giải được {p.hostname}"
    if not ips or any(not ipaddress.ip_address(i.split("%")[0]).is_global for i in ips):
        return "địa chỉ trỏ vào mạng nội bộ, không được phép"
    return ""


async def gui_http_that(url: str, than: bytes, headers: dict) -> tuple:
    import httpx
    async with httpx.AsyncClient(timeout=CHUYEN_TIEP_TIMEOUT, follow_redirects=False) as c:
        r = await c.post(url, content=than, headers=headers)
        return r.status_code, dict(r.headers)


def _retry_after(h: dict) -> float:
    v = str({k.lower(): x for k, x in (h or {}).items()}.get("retry-after") or "").strip()
    if v.isdigit():
        return min(float(v), RETRY_AFTER_TOI_DA)
    if v:
        try:
            from email.utils import parsedate_to_datetime
            return max(0.0, min(parsedate_to_datetime(v).timestamp() - time.time(), RETRY_AFTER_TOI_DA))
        except Exception:
            pass
    return 0.0


_LOI_TAM_AI = ("429", "rate", "hạn mức", "quá tải", "overloaded", "timeout", "hết giờ", "tạm thời",
               "503", "502", "connection", "kết nối")


class BoChay:
    def __init__(self, deps: ChayDeps):
        self.deps = deps
        self._dang: set = set()
        self._danh_thuc = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._dung = False

    # -- vòng nền
    def danh_thuc(self) -> None:
        try:
            self._danh_thuc.set()
        except Exception:
            pass

    def bat_dau(self) -> None:
        n = sk.phuc_hoi_sau_khoi_dong()
        if n:
            print(f"[webhook] {n} sự kiện kẹt lúc tắt máy, đã chuyển sang 'bị chặn' chờ chủ xem",
                  file=sys.stderr)
        self._task = asyncio.get_running_loop().create_task(self._vong())

    async def dung(self) -> None:
        self._dung = True
        self.danh_thuc()
        if self._task:
            self._task.cancel()

    async def _vong(self) -> None:
        don = 0.0
        while not self._dung:
            try:
                await self.mot_nhip()
                if self.deps.clock() - don > 3600:
                    don = self.deps.clock()
                    await asyncio.to_thread(sk.don_dep)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[webhook] vòng chạy lỗi: {type(e).__name__}", file=sys.stderr)
            try:
                await asyncio.wait_for(self._danh_thuc.wait(), NHIP_S)
            except asyncio.TimeoutError:
                pass
            self._danh_thuc.clear()

    async def mot_nhip(self) -> int:
        cho = max(0, SONG_SONG - len(self._dang))
        if not cho:
            return 0
        tam_dung = tuple(h for h in self._hook_tam_dung())
        viec = await asyncio.to_thread(sk.nhan_viec, self.deps.clock(), cho, tam_dung)
        if not viec:
            return 0
        await asyncio.gather(*(self.xu_ly(ev) for ev in viec), return_exceptions=True)
        return len(viec)

    def _hook_tam_dung(self) -> list:
        try:
            import webhooks
            return [w["id"] for w in webhooks._doc() if w.get("tam_dung")]
        except Exception:
            return []

    # -- một sự kiện
    async def xu_ly(self, ev: dict) -> str:
        sid = ev["id"]
        self._dang.add(sid)
        try:
            return await self._xu_ly(ev)
        except Exception as e:
            sk.dat_trang_thai(sid, sk.BI_CHAN, f"lỗi bất ngờ: {type(e).__name__}", buoc="chan",
                              chi_tiet=type(e).__name__)
            return sk.BI_CHAN
        finally:
            self._dang.discard(sid)

    async def _xu_ly(self, ev: dict) -> str:
        sid = ev["id"]
        hook = self.deps.lay_hook(ev["hook_id"])
        if not hook:
            sk.dat_trang_thai(sid, sk.BI_CHAN, "webhook đã bị xoá", buoc="chan")
            return sk.BI_CHAN
        doc, _ = sk.doc_than(ev["than"], ev.get("ctype", ""))
        khop, ly_do = sk.xet_loc(hook.get("loc") or [], doc)
        if not khop:
            sk.dat_trang_thai(sid, sk.BO_QUA, ly_do, buoc="loc", chi_tiet="bỏ qua: " + ly_do)
            return sk.BO_QUA
        if hook.get("loc"):
            sk.ghi_dong_tg(sid, "loc", "khớp bộ lọc")
        giao = dict(ev.get("giao") or {})
        hanh_dong = chuan_hanh_dong(hook.get("hanh_dong"))
        cho_lai, loi_han = 0.0, ""
        for a in hanh_dong:
            cu = giao.get(a["id"]) or {}
            if cu.get("tt") == "xong":
                continue
            lan = int(cu.get("lan") or 0) + 1
            try:
                ket = await self._chay_hanh_dong(a, hook, ev)
                giao[a["id"]] = {"tt": "xong", "lan": lan, "luc": self.deps.clock(), "ket_qua": ket[:200]}
                sk.ghi_dong_tg(sid, "giao_xong", f"{a['id']}: {ket[:160]}")
            except LoiTam as e:
                giao[a["id"]] = {"tt": "loi_tam", "lan": lan, "luc": self.deps.clock(), "loi": str(e)[:200]}
                sk.ghi_dong_tg(sid, "giao_loi", f"{a['id']} lần {lan}: {str(e)[:160]}")
                if lan >= LAN_THU_TOI_DA:
                    loi_han = loi_han or f"{a['id']}: hết {LAN_THU_TOI_DA} lần thử ({str(e)[:120]})"
                else:
                    bac = BAC_CHO_S[min(lan - 1, len(BAC_CHO_S) - 1)]
                    cho_lai = max(cho_lai, max(bac, e.cho))
            except LoiHan as e:
                giao[a["id"]] = {"tt": "loi", "lan": lan, "luc": self.deps.clock(), "loi": str(e)[:200]}
                sk.ghi_dong_tg(sid, "giao_loi", f"{a['id']}: {str(e)[:160]}")
                loi_han = loi_han or f"{a['id']}: {str(e)[:160]}"
        lan_max = max([int(g.get("lan") or 0) for g in giao.values()] or [0])
        if loi_han:
            sk.dat_trang_thai(sid, sk.BI_CHAN, loi_han, giao=giao, lan_thu=lan_max, buoc="chan", chi_tiet=loi_han)
            await self._bao_loi(hook, sid, loi_han)
            return sk.BI_CHAN
        if cho_lai:
            sk.dat_trang_thai(sid, sk.THU_LAI, "lỗi tạm thời, sẽ thử lại", giao=giao, lan_thu=lan_max,
                              chay_luc=self.deps.clock() + cho_lai, buoc="hen_lai",
                              chi_tiet=f"thử lại sau {int(cho_lai)} giây")
            return sk.THU_LAI
        sk.dat_trang_thai(sid, sk.XONG, "", giao=giao, lan_thu=lan_max, buoc="xong")
        return sk.XONG

    async def _chay_hanh_dong(self, a: dict, hook: dict, ev: dict) -> str:
        if a["loai"] == "chuyen_tiep":
            return await self._chuyen_tiep(a, ev)
        return await self._ai(hook, ev)

    async def _ai(self, hook: dict, ev: dict) -> str:
        if not self.deps.chay_ai:
            raise LoiHan("máy chưa nối bộ chạy AI")
        prompt = sk.loi_nhac(hook, ev["id"], ev["than"], ev.get("ctype", ""), float(ev["nhan_luc"]))
        try:
            body, err = await self.deps.chay_ai(hook.get("brain") or "brain", prompt,
                                                hook.get("muc_quyen") or "suggest")
        except Exception as e:
            raise LoiTam(f"AI lỗi: {type(e).__name__}")
        if err and not (body or "").strip():
            low = str(err).lower()
            raise LoiTam("AI: " + str(err)[:160]) if any(x in low for x in _LOI_TAM_AI) \
                else LoiHan("AI: " + str(err)[:160])
        if not (body or "").strip():
            raise LoiTam("AI không trả về nội dung")
        if self.deps.bao_chu:
            try:
                await self.deps.bao_chu(str(hook.get("ten") or ""), body.strip())
            except Exception as e:
                print(f"[webhook] báo kết quả lỗi: {type(e).__name__}", file=sys.stderr)
        return "AI đã chạy: " + body.strip().replace("\n", " ")[:150]

    async def _chuyen_tiep(self, a: dict, ev: dict) -> str:
        kiem = self.deps.kiem_dia_chi or kiem_dia_chi_cong_khai
        loi = await kiem(a["url"])
        if loi:
            raise LoiHan(loi)
        gui = self.deps.gui_http or gui_http_that
        hd = {"Content-Type": ev.get("ctype") or "application/octet-stream",
              "User-Agent": "MinMin-Webhook/1", "X-MinMin-Delivery": f"{ev['id']}.{a['id']}"}
        try:
            ma, h = await gui(a["url"], ev["than"], hd)
        except Exception as e:
            if a.get("lap_an_toan"):
                raise LoiTam(f"không gửi được tới {an_url(a['url'])}: {type(e).__name__}")
            raise LoiHan(f"Chưa rõ bên nhận đã xử lý chưa ({type(e).__name__}); kiểm tra trước khi chạy lại.")
        if 200 <= int(ma) < 300:
            return f"đã chuyển tiếp tới {an_url(a['url'])} (HTTP {ma})"
        if int(ma) == 429:
            raise LoiTam("bên nhận báo gửi quá nhanh (HTTP 429)", _retry_after(h))
        if int(ma) >= 500 or int(ma) == 408:
            if a.get("lap_an_toan"):
                raise LoiTam(f"bên nhận lỗi tạm (HTTP {ma})", _retry_after(h))
            raise LoiHan(f"HTTP {ma}: chưa rõ bên nhận đã xử lý chưa; kiểm tra trước khi chạy lại.")
        if 300 <= int(ma) < 400:
            raise LoiHan(f"bên nhận chuyển hướng (HTTP {ma}), MinMin không theo")
        raise LoiHan(f"bên nhận từ chối (HTTP {ma})")

    async def _bao_loi(self, hook: dict, sid: str, ly_do: str) -> None:
        if not self.deps.bao_chu:
            return
        try:
            await self.deps.bao_chu(str(hook.get("ten") or ""),
                                    f"Webhook \"{hook.get('ten')}\" bị chặn ở sự kiện {sid}: {ly_do}. "
                                    "Mở trang Webhook, phần Sự kiện, để xem và bấm chạy lại.")
        except Exception:
            pass

