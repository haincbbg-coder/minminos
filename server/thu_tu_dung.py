"""thu_tu_dung.py - THỨ TỰ DÙNG mô hình (26.10.270): một danh sách cho chat, việc nền và Telegram.

Trang Bộ não AI có một danh sách các nhà ĐÃ ĐĂNG NHẬP / ĐÃ KẾT NỐI. Thẻ trên cùng là MAIN, các thẻ
sau là Dự phòng 1, 2... Mỗi thẻ nhớ model và mức Effort riêng. Module này giữ dữ liệu đó trong mục
`model` của settings (truyền vào dạng dict thường) nên KHÔNG import main, test riêng được.

Dữ liệu (trong settings["model"]):
    thu_tu      ["anthropic-cli", "openai-oauth", ...]    [0] là MAIN
    the         {prov: {"model", "reasoning"}}            model + Effort của từng thẻ
    thu_tu_ver  1                                         đã chuyển đổi một lần

Trường cũ vẫn được giữ khớp để hơn trăm chỗ đang đọc chúng chạy như cũ: `main` = thẻ đầu + model
của nó, `reasoning` = Effort của thẻ đầu. Chỉ `dong_bo_main` ghi hai trường đó.

Hết lượt GÓI THUÊ BAO (Claude Code, ChatGPT, Grok Build...) ghi ở đây trong bộ nhớ tiến trình:
chat đọc để né nhà đang hết lượt, lượt sau tự quay lại khi tới giờ mở. Hết lượt của API KEY thì
nằm ở be_khoa (từng khoá một).

Chỉ đổi đường của MỘT lượt, không bao giờ sửa thứ tự hay model đã lưu khi né hay chạy lại.
"""
from __future__ import annotations

import threading
import time

MUC = ("off", "low", "medium", "high", "xhigh", "ultra")
PHIEN_BAN = 1
# Nhà không có tin nhắn "hết lượt tới mấy giờ" thì nghỉ bao lâu trước khi thử lại.
NGHI_MAC_DINH = 30 * 60


def _muc(x) -> str:
    return x if x in MUC else "off"


def _uniq(ids) -> list:
    ra = []
    for x in ids or []:
        x = str(x or "").strip()
        if x and x not in ra:
            ra.append(x)
    return ra


def _main_cu(m: dict) -> dict:
    """{'provider','model'} theo trường cũ (cùng luật main._effective_main)."""
    mn = (m or {}).get("main") or {}
    if mn.get("provider"):
        return {"provider": mn["provider"], "model": mn.get("model") or ""}
    eng = (m or {}).get("engine")
    if eng == "openrouter":
        return {"provider": "openrouter", "model": m.get("openrouter_model") or ""}
    if eng == "anthropic-api":
        return {"provider": "anthropic-api", "model": m.get("claude_model") or ""}
    return {"provider": "anthropic-cli", "model": (m or {}).get("claude_model") or ""}


# ---------------------------------------------------------------- thứ tự và thẻ

def da_luu(m: dict) -> list:
    return _uniq((m or {}).get("thu_tu"))


def thu_tu(m: dict, ket_noi=None) -> list:
    """Thứ tự dùng. Có `ket_noi` (danh sách nhà đang kết nối) thì chỉ giữ nhà còn kết nối, rồi nối
    thêm nhà mới kết nối mà thứ tự chưa biết vào CUỐI. Chưa lưu thứ tự nào thì MAIN đứng một mình."""
    goc = da_luu(m) or [_main_cu(m)["provider"]]
    if ket_noi is None:
        return goc
    kn = _uniq(ket_noi)
    giu = [p for p in goc if p in kn]
    return giu + [p for p in kn if p not in giu]


def main_cua(m: dict) -> str:
    o = da_luu(m)
    return o[0] if o else _main_cu(m)["provider"]


def the(m: dict, prov: str) -> dict:
    """Model + Effort của một thẻ. Thẻ chưa từng sửa: MAIN theo trường cũ, thẻ khác để model rỗng
    (= mặc định của nhà) với Effort chung hiện tại."""
    t = ((m or {}).get("the") or {}).get(prov)
    if isinstance(t, dict):
        return {"model": str(t.get("model") or ""), "reasoning": _muc(t.get("reasoning"))}
    mc = _main_cu(m)
    if mc["provider"] == prov:
        return {"model": mc["model"], "reasoning": _muc((m or {}).get("reasoning"))}
    return {"model": "", "reasoning": _muc((m or {}).get("reasoning"))}


def dong_bo_main(m: dict) -> None:
    """`main` và `reasoning` luôn bằng thẻ đầu. Chỗ DUY NHẤT ghi hai trường đó từ thứ tự."""
    o = da_luu(m)
    if not o:
        return
    t = the(m, o[0])
    m["main"] = {"provider": o[0], "model": t["model"]}
    m["reasoning"] = t["reasoning"]


def _ghim_the(m: dict, ids) -> None:
    """Chốt thẻ hiện tại của từng nhà trước khi MAIN đổi chỗ, để không thẻ nào nhảy model."""
    tt = m.setdefault("the", {})
    for p in ids:
        if not isinstance(tt.get(p), dict):
            tt[p] = the(m, p)


def dat_the(m: dict, prov: str, model=None, reasoning=None) -> None:
    cur = the(m, prov)
    if model is not None:
        cur["model"] = str(model or "")
    if reasoning is not None:
        cur["reasoning"] = _muc(reasoning)
    m.setdefault("the", {})[prov] = cur
    if main_cua(m) == prov:
        dong_bo_main(m)


def dat_thu_tu(m: dict, ids) -> None:
    ids = _uniq(ids)
    if not ids:
        return
    _ghim_the(m, set(ids) | set(da_luu(m)))
    m["thu_tu"] = ids
    dong_bo_main(m)


def len_dau(m: dict, prov: str, model=None) -> None:
    """Đưa một nhà lên làm MAIN (chọn model ở khung chat, hay đổi model chính kiểu cũ). Các thẻ
    khác giữ thứ tự tương đối, MAIN cũ thành Dự phòng 1."""
    o = da_luu(m) or [_main_cu(m)["provider"]]
    _ghim_the(m, set(o) | {prov})
    m["thu_tu"] = [prov] + [p for p in o if p != prov]
    if model is not None:
        m["the"][prov]["model"] = str(model or "")
    dong_bo_main(m)


def doi_cho(m: dict, i: int) -> None:
    """Nút Đảo: đổi chỗ thẻ thứ i với thẻ thứ i+1."""
    o = da_luu(m)
    if 0 <= i < len(o) - 1:
        o[i], o[i + 1] = o[i + 1], o[i]
        dat_thu_tu(m, o)


def them_cuoi(m: dict, prov: str) -> None:
    """Nhà vừa kết nối vào CUỐI thứ tự."""
    o = da_luu(m)
    if prov and o and prov not in o:
        m["thu_tu"] = o + [prov]


def bo_ra(m: dict, prov: str) -> None:
    """Nhà vừa ngắt kết nối rời thứ tự; nó là MAIN thì thẻ kế lên thay."""
    o = da_luu(m)
    if prov in o and len(o) > 1:
        m["thu_tu"] = [p for p in o if p != prov]
        dong_bo_main(m)


def chuyen_doi(m: dict, ket_noi) -> bool:
    """Chuyển cài đặt cũ sang thứ tự dùng, MỘT lần (chạy lại không đổi gì). Thứ tự = MAIN hiện tại
    rồi các nhà đang kết nối khác; mọi thẻ giữ Effort chung hiện tại nên không lượt nào đổi hành vi."""
    if int((m or {}).get("thu_tu_ver") or 0) >= PHIEN_BAN:
        return False
    mc = _main_cu(m)
    o = [mc["provider"]] + [p for p in _uniq(ket_noi) if p != mc["provider"]]
    if not da_luu(m):
        m["thu_tu"] = o
    _ghim_the(m, da_luu(m))
    aux = m.setdefault("auxiliary", {})
    if aux.get("reasoning") not in MUC:
        aux["reasoning"] = "off"
    m["thu_tu_ver"] = PHIEN_BAN
    dong_bo_main(m)
    return True


# ---------------------------------------------------------------- hết lượt gói thuê bao

_LOCK = threading.Lock()
_HET_LUOT: dict = {}       # prov -> epoch mở lại
_NEN_TAM: dict = {}        # {"provider","model","luc","vi_sao"} khi việc nền đang chạy bằng mắt sau


def ghi_het_luot(prov: str, den: float = 0.0, giay: float = 0.0, now: float = None) -> float:
    now = time.time() if now is None else now
    until = float(den or 0) if float(den or 0) > now else now + (giay or NGHI_MAC_DINH)
    with _LOCK:
        _HET_LUOT[str(prov or "")] = until
    return until


def het_luot_den(prov: str, now: float = None) -> float:
    """Epoch nhà này mở lại hạn mức, 0 khi đang dùng được."""
    now = time.time() if now is None else now
    with _LOCK:
        u = float(_HET_LUOT.get(str(prov or ""), 0) or 0)
    return u if u > now else 0.0


def xoa_het_luot(prov: str = "") -> None:
    with _LOCK:
        if prov:
            _HET_LUOT.pop(prov, None)
        else:
            _HET_LUOT.clear()


def duong_ke(m: dict, ket_noi, san_sang, da_thu=()) -> str:
    """Nhà kế tiếp theo thứ tự còn chạy được (`san_sang(prov)` True), bỏ nhà đã thử trong lượt.
    "" khi không còn nhà nào."""
    da_thu = set(da_thu or ())
    for p in thu_tu(m, ket_noi):
        if p in da_thu:
            continue
        try:
            if san_sang(p):
                return p
        except Exception:  # noqa: BLE001 - một nhà kiểm hỏng không được chặn cả thứ tự
            continue
    return ""


# ---------------------------------------------------------------- việc nền

def nen(m: dict) -> dict:
    """Mô hình việc nền: {'provider','model','reasoning'}. Chưa đặt = Claude Code (luật cũ)."""
    a = (m or {}).get("auxiliary") or {}
    return {"provider": a.get("provider") or "anthropic-cli", "model": a.get("model") or "",
            "reasoning": _muc(a.get("reasoning"))}


def chuoi_nen(m: dict, ket_noi=None, dau: dict = None, mac_dinh: dict = None, mot_lan=()) -> list:
    """Các bước việc nền: mô hình nền (hoặc `dau`, ví dụ model riêng của trợ lý) -> Dự phòng 1, 2...
    -> MAIN sau cùng. Mỗi bước sau bước đầu chạy CẤU HÌNH MẶC ĐỊNH của nhà đó (`mac_dinh[prov]`,
    thiếu thì model rỗng = mặc định của nhà), không phải model bố chọn cho chat: chat có thể đang
    để model đắt nhất. Cùng nhà + cùng model chỉ một lần; nhà trong `mot_lan` (gói thuê bao, hạn
    mức tính theo tài khoản chứ không theo model) chỉ xuất hiện một lần."""
    o = thu_tu(m, ket_noi)
    buoc = [dict(dau or nen(m), buoc="nen")]
    for p in o[1:] + o[:1]:
        d = (mac_dinh or {}).get(p) or {}
        buoc.append({"provider": p, "model": str(d.get("model") or ""), "reasoning": "off",
                     "buoc": "main" if p == o[0] else "du_phong"})
    ra, thay = [], set()
    for b in buoc:
        k = (b["provider"], "" if b["provider"] in mot_lan else b["model"])
        if k not in thay:
            thay.add(k)
            ra.append(b)
    return ra


def ghi_nen_tam(prov: str = "", model: str = "", vi_sao: str = "") -> None:
    """Việc nền vừa chạy xong bằng một mắt SAU mắt đầu (mô hình nền hết lượt). Rỗng = xoá."""
    with _LOCK:
        _NEN_TAM.clear()
        if prov:
            _NEN_TAM.update(provider=prov, model=model or "", luc=time.time(), vi_sao=(vi_sao or "")[:160])


def doc_nen_tam(max_tuoi: float = 6 * 3600) -> dict:
    with _LOCK:
        d = dict(_NEN_TAM)
    if d and time.time() - float(d.get("luc") or 0) > max_tuoi:
        return {}
    return d
