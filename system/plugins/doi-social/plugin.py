"""Plugin bundled: Đội Social - cho mọi engine giao việc đăng bài cho máy ở nhà (26.10.185).

Plugin chạy CÙNG tiến trình với server, nên gọi thẳng kho `doi_social` và hàm dùng chung của
`routes.doi_social` (tạo việc + xin duyệt Telegram + đánh thức worker). Không tự đăng gì: tool
tạo bài chỉ đặt việc vào hàng đợi; bài chỉ lên mạng khi chủ bấm Duyệt (trừ khi chủ dặn rõ là
không cần duyệt), rồi máy nhà mới mở profile GPM và làm.
"""
from __future__ import annotations


def _mods():
    import doi_social
    import routes.doi_social as rds
    return doi_social, rds


def _check():
    try:
        doi_social, rds = _mods()
    except Exception:
        return "Đội Social chưa nạp được trên máy chủ này."
    ly = rds.ly_do_chan()
    if ly:
        return ly
    if not doi_social.ds_may():
        return ("Chưa có máy ở nhà nào ghép với MinMin. Mở Kết nối ngoài > Đội Social, tải MinMin "
                "Worker về máy có GPM Login, chạy và nhập mã ghép 6 số.")
    return None


def _nick(args, ctx):
    doi_social, _ = _mods()
    tim = str(args.get("tim") or "").strip()
    may = {m["id"]: m for m in doi_social.ds_may()}
    ds = doi_social.tim_nick(tim) if tim else doi_social.ds_nick()
    if not may:
        return "Chưa có máy ở nhà nào ghép."
    dong = []
    for m in may.values():
        trang = "đang bật" if m["online"] else "NGOẠI TUYẾN (máy tắt hoặc Worker chưa chạy)"
        gpm = "GPM ok" if m.get("driver_ok") else f"GPM chưa sẵn sàng: {m.get('loi_driver') or 'chưa rõ'}"
        dong.append(f"Máy '{m['ten']}': {trang}, {gpm}, {m['so_nick']} nick")
    if not ds:
        dong.append("Không thấy nick nào" + (f" khớp '{tim}'." if tim else "."))
    for n in ds[:80]:
        dong.append(f"- {n['ten']} [{n.get('trinh_duyet') or '?'}]"
                    + (" · có proxy" if n.get("co_proxy") else " · không proxy")
                    + (f" · nhóm {n['nhom']}" if n.get("nhom") else "")
                    + f" · máy {may.get(n['may_id'], {}).get('ten', '?')}")
    if len(ds) > 80:
        dong.append(f"... và {len(ds) - 80} nick nữa, thêm 'tim' để lọc.")
    gh = doi_social.gioi_han()
    dong.append(f"Giới hạn: {gh['bai_moi_ngay']} bài/nick/ngày, nghỉ {gh['nghi_phut']} phút giữa hai lượt.")
    return "\n".join(dong)


def _tao_bai(args, ctx):
    doi_social, rds = _mods()
    tep = args.get("tep") or []
    if isinstance(tep, str):
        tep = [t.strip() for t in tep.split(",") if t.strip()]
    goc = ctx.vault_root
    if goc:
        from pathlib import Path
        tep = [str(Path(goc) / t) if not Path(str(t)).is_absolute() else str(t) for t in tep]
    try:
        v = rds.tao_viec_va_bao(ky_nang="fb_dang_bai", nick=str(args.get("nick") or ""),
                                noi_dung=str(args.get("noi_dung") or ""), tep=tep,
                                noi_dang=str(args.get("noi_dang") or ""),
                                can_duyet=not bool(args.get("khong_can_duyet")),
                                chat_id=str(args.get("chat_id") or ""), nguon="chat", ai_tao=ctx.slug)
    except ValueError as e:
        return f"Chưa tạo được bài: {e}"
    if v["trang_thai"] == "cho_duyet":
        return (f"Đã tạo bài #{v['id']} cho nick '{v['nick_ten']}', đang CHỜ DUYỆT. Bản xem trước đã gửi "
                "qua Telegram kèm nút Duyệt / Bỏ (cũng duyệt được ở trang Đội Social). Bài CHƯA lên mạng; "
                "sau khi duyệt, máy ở nhà sẽ mở profile và đăng, kết quả kèm ảnh chụp tự gửi về.")
    return (f"Đã xếp bài #{v['id']} cho nick '{v['nick_ten']}' (không cần duyệt). Máy ở nhà sẽ mở profile "
            "và đăng ở lượt tới; kết quả kèm ảnh chụp tự gửi về Telegram.")


def _viec(args, ctx):
    doi_social, _ = _mods()
    if args.get("id"):
        v = doi_social.lay_viec(int(args["id"]))
        if not v:
            return f"Không có việc #{args['id']}."
        ds = [v]
    else:
        ds = doi_social.ds_viec(int(args.get("limit") or 10), str(args.get("trang_thai") or ""))
    if not ds:
        return "Chưa có việc nào."
    nhan = {"cho_duyet": "chờ duyệt", "cho_chay": "chờ máy nhà", "dang_chay": "đang chạy",
            "xong": "xong", "loi": "lỗi", "bo": "đã bỏ"}
    out = []
    for v in ds:
        out.append(f"#{v['id']} {v['nhan_ky_nang']} · {v['nick_ten']} · {nhan.get(v['trang_thai'], v['trang_thai'])}"
                   + (f" · {v['thong_diep']}" if v.get("thong_diep") else ""))
    return "\n".join(out)


def register(ctx):
    ctx.register_tool(
        name="social_nick",
        description=("Đội Social: liệt kê máy ở nhà và nick (profile GPM Login) dùng được để đăng bài, "
                     "kèm trạng thái máy, proxy và giới hạn bài/ngày. 'tim' lọc theo tên (không dấu)."),
        handler=_nick, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {
            "tim": {"type": "string", "description": "Lọc nick theo tên, vd 'mai anh'"},
        }},
    )
    ctx.register_tool(
        name="social_tao_bai_fb",
        description=("Đội Social: tạo một bài đăng Facebook để máy ở nhà mở profile GPM và đăng NHƯ NGƯỜI "
                     "THẬT (gõ từng chữ, tải ảnh/video). Mặc định CHỜ CHỦ DUYỆT qua Telegram trước khi đăng. "
                     "Tự viết noi_dung hoàn chỉnh trước khi gọi. Trùng nhiều nick thì gọi social_nick để hỏi lại."),
        handler=_tao_bai, min_mode="full", check_fn=_check,
        schema={"type": "object", "required": ["nick"], "properties": {
            "nick": {"type": "string", "description": "Tên profile GPM (đúng như social_nick trả về)"},
            "noi_dung": {"type": "string", "description": "Nội dung bài, chữ thuần, xuống dòng bình thường"},
            "tep": {"type": "array", "items": {"type": "string"},
                    "description": "Ảnh/video đính kèm: đường dẫn trong brain (vd inbox/telegram/a.jpg), tối đa 10"},
            "noi_dang": {"type": "string",
                         "description": "Link Trang/nhóm Facebook để đăng. Bỏ trống = tường cá nhân của nick"},
            "khong_can_duyet": {"type": "boolean",
                                "description": "CHỈ true khi chủ dặn rõ là đăng luôn không cần duyệt"},
            "chat_id": {"type": "string", "description": "Chat Telegram nhận xin duyệt/kết quả (bỏ trống = chủ)"},
        }},
    )
    ctx.register_tool(
        name="social_viec",
        description="Đội Social: xem trạng thái các lượt đăng (chờ duyệt, đang chạy, xong, lỗi) hoặc một việc theo id.",
        handler=_viec, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {
            "id": {"type": "integer"},
            "trang_thai": {"type": "string", "enum": ["cho_duyet", "cho_chay", "dang_chay", "xong", "loi", "bo"]},
            "limit": {"type": "integer", "description": "Mặc định 10"},
        }},
    )
