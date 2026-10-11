"""chung_cu.py - CHỨNG CỨ cho việc nền (Trụ 5, 26.10.141).

Một việc nền (việc Kanban, vòng loop) chạy xong không chỉ báo "xong", mà kèm một dòng chứng cứ
đọc được trên điện thoại: đã ĐỌC dữ liệu từ tool nào, đã LÀM gì ra ngoài đời (lấy từ sổ hành
động, Trụ 4), và số liệu trong kết quả có NEO vào dữ liệu không (Trụ 3). Nhờ đó người chủ
đọc một tin Telegram là biết việc đó đáng tin đến đâu, không cần mở trang Việc.

Thuần: không gọi mạng, không import main. Dùng nguon.neo_so và hanh_dong.doc (cả hai thuần).
"""
from __future__ import annotations

from typing import Iterable

import hanh_dong
import nguon

_TOOL_NOI_BO = ("javis_search_tools", "javis_no_tools", "javis_wait_quota", "javis_read_file",
                "javis_list_files", "javis_write_file", "javis_use_skill", "javis_connections")


def _ten_that(ev: dict) -> str:
    """Tên tool thật của một sự kiện tool_call, xuyên lớp lazy (javis_run_tool(name=...))."""
    n = str(ev.get("name") or ev.get("tool") or "").rsplit("__", 1)[-1]
    if n == "javis_run_tool":
        n = str((ev.get("input") or {}).get("name") or n).rsplit("__", 1)[-1]
    return n


class Gom:
    """Gom sự kiện của MỘT lần chạy: tool đã gọi + kết quả tool. Gọi nap(ev) cho mỗi sự kiện."""

    def __init__(self, ai: str = "", luc_bat_dau: str = ""):
        self.ai = ai
        self.luc_bat_dau = luc_bat_dau
        self.tool_calls: list[str] = []
        self.ket_qua: list[str] = []

    def nap(self, ev: dict) -> None:
        t = (ev or {}).get("type")
        if t == "tool_call":
            n = _ten_that(ev)
            if n and n not in _TOOL_NOI_BO:
                self.tool_calls.append(n)
        elif t == "tool_result":
            self.ket_qua.append(str(ev.get("content") or ""))

    def hanh_dong_ngoai(self) -> list:
        """Dòng trong sổ hành động do ĐÚNG lần chạy này gây ra (cùng ai, từ lúc bắt đầu)."""
        if not self.ai:
            return []
        ra = []
        for r in hanh_dong.doc(300):
            if r.get("ai") != self.ai:
                continue
            if self.luc_bat_dau and str(r.get("ts") or "") < self.luc_bat_dau:
                continue
            ra.append(r)
        return list(reversed(ra))   # cũ -> mới

    def dung(self, ket_qua_text: str, cau_hoi: str = "") -> str:
        return dung(self.tool_calls, self.ket_qua, ket_qua_text, self.hanh_dong_ngoai(), cau_hoi=cau_hoi)


def _dem(ds: Iterable[str]) -> list:
    seen, ra = set(), []
    for x in ds:
        if x not in seen:
            seen.add(x); ra.append(x)
    return ra


def dung(tool_calls: list, ket_qua_tool: list, ket_qua_text: str, hanh_dong_rows: list, *,
         cau_hoi: str = "") -> str:
    """Dòng chứng cứ. Rỗng khi lần chạy không gọi tool, không làm gì ngoài, không có số liệu
    (vd loop "không có việc mới")."""
    doc = _dem(tool_calls or [])
    neo = nguon.neo_so(ket_qua_text or "", cau_hoi or "", ket_qua_tool or [])
    ngoai = list(hanh_dong_rows or [])
    co_so = bool(neo["co_nguon"] or neo["khong_nguon"])
    if not doc and not ngoai and not co_so:
        return ""
    phan = []
    if doc:
        phan.append(f"đọc {len(tool_calls)} lượt tool ({', '.join(doc[:5])}{', ...' if len(doc) > 5 else ''})")
    else:
        phan.append("không đọc dữ liệu nào")
    if ngoai:
        tt = []
        for r in ngoai[:4]:
            dau = "✓" if r.get("ok") else ("chặn" if "CHẶN" in str(r.get("err") or "") else "lỗi")
            tt.append(f"{r.get('tool')} {dau}")
        phan.append(f"{len(ngoai)} hành động ngoài: " + ", ".join(tt) + (", ..." if len(ngoai) > 4 else ""))
    else:
        phan.append("không làm gì ra ngoài")
    if co_so:
        s = f"số liệu: {len(neo['co_nguon'])} có nguồn"
        if neo["khong_nguon"]:
            s += f", {len(neo['khong_nguon'])} chưa rõ ({', '.join(nguon._fmt(n) for n in neo['khong_nguon'][:3])})"
        phan.append(s)
    dong = "Chứng cứ: " + " · ".join(phan)
    if co_so and not doc:
        dong += "\n⚠ Kết quả có số liệu nhưng lần chạy này không đọc dữ liệu nào. Đừng dùng con số này."
    elif neo["khong_nguon"] and doc:
        dong += "\n⚠ Có số không thấy trong dữ liệu tool: kiểm lại trước khi dùng."
    return dong
