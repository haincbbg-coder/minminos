"""Plugin bundled: Concat - MinMin điều khiển trình dựng video Concat trên máy ở nhà (26.10.196).

Concat có MCP server sẵn trong app. Cầu nối `apps/concat/cau` ở máy nhà giữ một phiên
`concat --mcp`, nhận việc từ MinMin (long-poll) và gửi kết quả lên. Plugin này đưa toàn bộ công cụ
của Concat tới MỌI engine qua năm tool:

    concat_trang_thai  readonly  máy nhà có online không, Concat bản nào, thư mục làm việc
    concat_cong_cu     readonly  danh sách công cụ Concat, hoặc mô tả + schema của một công cụ
    concat_goi         safe      gọi một công cụ Concat (tạo dự án, nhập, cắt, chữ, hiệu ứng, xuất...)
    concat_ket_qua     readonly  lấy kết quả một việc đã gửi (việc dài như xuất video)
    concat_lay_tep     safe      kéo một tệp trên máy nhà (video vừa xuất) về bộ não

Handler đều là `async`: hub gọi thẳng trên event loop, nên mọi chỗ chờ đều qua asyncio.to_thread.
Mỗi lượt chờ tối đa CHO_TOI_DA giây (các đường gọi tool có hạn 30 giây); việc lâu hơn trả mã việc
để gọi concat_ket_qua sau.
"""
from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import concat_cau

CHO_TOI_DA = 25.0
CHU_TOI_DA = 12000


def _ly_do_khoa():
    try:
        import routes.concat as rc
        return rc.ly_do_chan()
    except Exception:
        return None


def _check():
    ly = _ly_do_khoa()
    if ly:
        return ly
    try:
        tt = concat_cau.trang_thai()
    except Exception:
        return "Concat chưa sẵn sàng trên máy chủ này."
    if not tt["da_ghep"]:
        return ("Chưa ghép máy có Concat. Mở Kết nối ngoài > Concat trên dashboard để tạo mã ghép và "
                "tải bộ cầu nối cho máy tính ở nhà.")
    return None


def _goc(ctx) -> Path:
    return Path(ctx.vault_root) if getattr(ctx, "vault_root", None) else None


def _giai_duong(ctx):
    goc = _goc(ctx)

    def giai(rel: str) -> str:
        p = Path(rel)
        if p.is_absolute() or goc is None:
            return str(p)
        return str(goc / rel)
    return giai


def _luu_anh(ctx, vid: int, so: int, du_lieu_b64: str, mime: str) -> str:
    goc = _goc(ctx)
    if goc is None:
        return ""
    duoi = ".png" if "png" in (mime or "") else ".jpg"
    dich = goc / "attachments" / "concat" / f"khung-{vid}-{so}{duoi}"
    try:
        dich.parent.mkdir(parents=True, exist_ok=True)
        dich.write_bytes(base64.b64decode(du_lieu_b64))
    except Exception:
        return ""
    return str(dich.relative_to(goc)).replace("\\", "/")


def _trinh_bay(ctx, v: dict) -> str:
    vid = v.get("id")
    tt = v.get("trang_thai")
    if tt in ("cho", "dang"):
        return (f"Việc #{vid} ({v.get('cong_cu') or v.get('loai')}) đang "
                f"{'chờ máy nhà nhận' if tt == 'cho' else 'chạy trên máy nhà'}. "
                f"Gọi concat_ket_qua với viec_id={vid} để lấy kết quả.")
    if tt == "loi":
        return f"ERROR: việc #{vid} lỗi: {v.get('loi') or 'không rõ'}"
    kq = v.get("ket_qua") or {}
    if v.get("loai") == "lay_tep":
        duong = kq.get("tep") or ""
        if not duong:
            return f"Việc #{vid} xong nhưng không có đường dẫn tệp."
        anh = duong.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
        return (f"Đã lưu {kq.get('ten') or 'tệp'} vào bộ não: {duong}\n"
                + (f"![{kq.get('ten')}]({duong})" if anh else f"[{kq.get('ten')}]({duong})"))
    phan = []
    for i, c in enumerate(kq.get("content") or []):
        if c.get("type") == "text":
            phan.append(str(c.get("text") or ""))
        elif c.get("type") == "image" and c.get("data"):
            rel = _luu_anh(ctx, vid, i, c["data"], c.get("mimeType") or "")
            phan.append(f"![khung hình]({rel})" if rel else "(có ảnh nhưng chưa lưu được vào bộ não)")
    if kq.get("structuredContent") is not None and not any(p.strip() for p in phan):
        phan.append(json.dumps(kq["structuredContent"], ensure_ascii=False))
    chu = "\n".join(p for p in phan if p).strip() or "(Concat không trả nội dung)"
    if len(chu) > CHU_TOI_DA:
        chu = chu[:CHU_TOI_DA] + f"\n... (cắt bớt, tổng {len(chu)} ký tự)"
    return chu


async def _cho(ctx, vid: int, cho: float) -> str:
    v = await asyncio.to_thread(concat_cau.cho_ket_qua, vid, max(0.0, min(CHO_TOI_DA, cho)))
    if not v:
        return f"ERROR: không có việc #{vid}"
    return _trinh_bay(ctx, v)


async def _trang_thai(args, ctx):
    tt = await asyncio.to_thread(concat_cau.trang_thai)
    if not tt["da_ghep"]:
        return "Chưa ghép máy có Concat."
    dong = []
    for m in tt["may"]:
        cc = m.get("concat") or {}
        dong.append(f"- {m['ten']} ({m['id']}): {'online' if m['online'] else 'đang tắt'}, "
                    f"Concat {'sẵn sàng' if m['concat_ok'] else 'chưa chạy'}"
                    f"{' ' + str(cc.get('version')) if cc.get('version') else ''}, "
                    f"{len(m.get('cong_cu') or [])} công cụ, thư mục làm việc: {m.get('thu_muc') or '?'}"
                    + (f", lỗi: {m['loi_concat']}" if m.get("loi_concat") else ""))
    goi_y = ""
    m = concat_cau.may_chinh()
    if m and m.get("cong_cu"):
        goi_y = "\nCông cụ: " + ", ".join(t["name"] for t in m["cong_cu"])
    return "Máy có Concat:\n" + "\n".join(dong) + goi_y


async def _cong_cu(args, ctx):
    m = await asyncio.to_thread(concat_cau.may_chinh)
    if not m:
        ds = await asyncio.to_thread(concat_cau.ds_may)
        m = max(ds, key=lambda x: x.get("nhip_luc") or 0) if ds else None
    if not m or not m.get("cong_cu"):
        return "ERROR: máy nhà chưa báo danh sách công cụ (cầu nối chưa chạy hoặc Concat chưa mở được)."
    ten = str((args or {}).get("ten") or "").strip()
    if ten:
        for t in m["cong_cu"]:
            if t["name"] == ten:
                return json.dumps(t, ensure_ascii=False)
        return f"ERROR: Concat không có công cụ {ten}. Có: " + ", ".join(t["name"] for t in m["cong_cu"])
    return "\n".join(f"- {t['name']}: {t['description'][:220]}" for t in m["cong_cu"])


async def _goi(args, ctx):
    args = args or {}
    cong_cu = str(args.get("cong_cu") or "").strip()
    tham_so = args.get("tham_so") or {}
    if isinstance(tham_so, str):
        try:
            tham_so = json.loads(tham_so or "{}")
        except json.JSONDecodeError:
            return "ERROR: tham_so phải là object JSON"
    if not isinstance(tham_so, dict):
        return "ERROR: tham_so phải là object JSON"
    try:
        cho_viec = float(args.get("cho_giay") or 600)
    except (TypeError, ValueError):
        cho_viec = 600
    goc = _goc(ctx)
    try:
        tham_so, tep = concat_cau.gom_tep(tham_so, _giai_duong(ctx), goc_them=str(goc) if goc else None)
        v = await asyncio.to_thread(concat_cau.tao_viec, loai="goi", cong_cu=cong_cu, tham_so=tham_so,
                                    tep=tep, cho_giay=cho_viec)
    except ValueError as e:
        return f"ERROR: {e}"
    return await _cho(ctx, v["id"], CHO_TOI_DA)


async def _ket_qua(args, ctx):
    try:
        vid = int((args or {}).get("viec_id"))
    except (TypeError, ValueError):
        return "ERROR: thiếu viec_id"
    try:
        cho = float((args or {}).get("cho_giay") or CHO_TOI_DA)
    except (TypeError, ValueError):
        cho = CHO_TOI_DA
    return await _cho(ctx, vid, cho)


async def _lay_tep(args, ctx):
    duong = str((args or {}).get("duong_dan") or "").strip()
    if not duong:
        return "ERROR: thiếu duong_dan (đường dẫn tệp trên máy nhà, vd video vừa xuất)"
    goc = _goc(ctx)
    try:
        v = await asyncio.to_thread(concat_cau.tao_viec, loai="lay_tep", duong_dan=duong,
                                    tham_so={"_brain": str(goc) if goc else ""}, cho_giay=1800)
    except ValueError as e:
        return f"ERROR: {e}"
    return await _cho(ctx, v["id"], CHO_TOI_DA)


_HUONG_DAN = (
    " Dự án Concat là một THƯ MỤC; mọi công cụ dự án nhận `path` là thư mục đó. Tạo dự án mới trong "
    "thư mục làm việc mà concat_trang_thai báo (Videos\\MinMin Concat trên máy nhà). Tệp trong bộ não "
    "đưa vào Concat bằng chuỗi \"minmin:<đường trong bộ não>\" ở bất kỳ tham số nào (vd media_import "
    "{\"path\": \"...\", \"files\": [\"minmin:attachments/clip.mp4\"]}); cầu nối tự chép xuống máy nhà. "
    "Sửa chỉ nằm trong bộ nhớ tới khi gọi project_save. Xuất: export_start rồi concat_ket_qua / "
    "export_status; xong thì concat_lay_tep để đưa video về bộ não."
)


def register(ctx):
    ctx.register_tool(
        name="concat_trang_thai",
        description="Trình dựng video Concat ở máy nhà: máy có online không, Concat bản nào, thư mục làm việc, tên các công cụ.",
        handler=_trang_thai, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {}},
    )
    ctx.register_tool(
        name="concat_cong_cu",
        description=("Danh sách công cụ của Concat (dự án, nhập media, cắt, chữ, phụ đề, keyframe, hiệu ứng, "
                     "mẫu, xuất, xem khung hình). Truyền `ten` để lấy mô tả và schema tham số đầy đủ của một "
                     "công cụ trước khi gọi concat_goi."),
        handler=_cong_cu, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {
            "ten": {"type": "string", "description": "Tên một công cụ, vd clip_add, title_add, export_start"},
        }},
    )
    ctx.register_tool(
        name="concat_goi",
        description=("Gọi một công cụ của Concat trên máy nhà để dựng video." + _HUONG_DAN
                     + " Đợi tối đa 25 giây; lâu hơn thì trả mã việc."),
        handler=_goi, min_mode="safe", check_fn=_check,
        schema={"type": "object", "required": ["cong_cu"], "properties": {
            "cong_cu": {"type": "string", "description": "Tên công cụ Concat, vd project_create, clip_add"},
            "tham_so": {"type": "object", "description": "Tham số đúng schema của công cụ (xem concat_cong_cu)"},
            "cho_giay": {"type": "number", "description": "Hạn tối đa cho việc trên máy nhà (giây, mặc định 600)"},
        }},
    )
    ctx.register_tool(
        name="concat_ket_qua",
        description="Kết quả một việc Concat đã gửi (theo viec_id mà concat_goi / concat_lay_tep trả). Đợi tối đa 25 giây.",
        handler=_ket_qua, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "required": ["viec_id"], "properties": {
            "viec_id": {"type": "integer"},
            "cho_giay": {"type": "number", "description": "Đợi thêm tối đa bao nhiêu giây (≤25)"},
        }},
    )
    ctx.register_tool(
        name="concat_lay_tep",
        description=("Đưa một tệp trên máy nhà (thường là video vừa xuất từ Concat) về bộ não, vào "
                     "attachments/concat/. Chỉ tệp nằm trong thư mục người dùng của máy nhà."),
        handler=_lay_tep, min_mode="safe", check_fn=_check,
        schema={"type": "object", "required": ["duong_dan"], "properties": {
            "duong_dan": {"type": "string", "description": "Đường dẫn tuyệt đối trên máy nhà"},
        }},
    )
