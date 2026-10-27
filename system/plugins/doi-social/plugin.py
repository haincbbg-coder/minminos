"""Plugin bundled: Đội Social - cho mọi engine giao việc đăng bài cho máy ở nhà (26.10.185).

Plugin chạy CÙNG tiến trình với server, nên gọi thẳng kho `doi_social` và hàm dùng chung của
`routes.doi_social` (tạo việc + xin duyệt Telegram + đánh thức worker). Không tự đăng gì: tool
tạo bài chỉ đặt việc vào hàng đợi; bài chỉ lên mạng khi chủ bấm Duyệt (trừ khi chủ dặn rõ là
không cần duyệt), rồi máy nhà mới mở profile GPM và làm.
"""
from __future__ import annotations

import json
import re


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
    if args.get("id") and ds[0].get("trang_thai") == "loi" and ds[0].get("buoc"):
        # Việc lỗi: kèm nhật ký Worker (có chẩn đoán trang) để trả lời được "vì sao lỗi".
        out.append("Nhật ký máy nhà:")
        out += [f"- {b}" for b in ds[0]["buoc"]]
    return "\n".join(out)


async def _up_bai_chay(args, ctx):
    import routes.up_bai as rub
    up = rub.may()
    if not up:
        return "Up bài từ Google Sheet chưa khởi động trên máy chủ này."
    cfg = rub.doc_cau_hinh()
    if not cfg["sheet_id"]:
        return "Chưa đặt Google Sheet UP BÀI. Vào Kết nối ngoài > Đội Social, dán link Sheet ở thẻ Up bài."
    dong = int(args.get("dong") or 0) or None
    kq = await up.chay_mot_vong(chi_dong=dong)
    if not kq.get("ok"):
        return f"Không chạy được: {kq.get('loi')}"
    if kq.get("bo_qua"):
        return "Vòng trước còn đang chạy, kết quả sẽ tự báo về Telegram."
    dong_cho = "\n".join(kq.get("cho") or [])
    return (f"Đã chạy một lượt Sheet UP BÀI: xử lý {kq.get('xu_ly', 0)} dòng mới (AI viết content, gửi Telegram "
            f"để duyệt), đăng {kq.get('dang', 0)} bài." + (f"\nĐang chờ:\n{dong_cho}" if dong_cho else "")
            + "\nKết quả từng bài tự gửi về Telegram và ghi ngược vào Sheet.")


def _up_bai_trang_thai(args, ctx):
    import routes.up_bai as rub
    up = rub.may()
    cfg = rub.doc_cau_hinh()
    nk = "\n".join(list(reversed(up.nhat_ky_vong[-15:]))) if up else ""
    return (f"Sheet: {'đã đặt' if cfg['sheet_id'] else 'CHƯA đặt'} · tự chạy 5 phút/lần: {'BẬT' if cfg['bat'] else 'tắt'}"
            f" · tự duyệt: {'có' if cfg['tu_duyet'] else 'không, duyệt qua Telegram'}\n"
            f"Lượt gần nhất: {json.dumps(up.lan_cuoi, ensure_ascii=False) if up and up.lan_cuoi else 'chưa chạy'}"
            + (f"\nNhật ký:\n{nk}" if nk else ""))


# ------------------------------------------------------------------ bản đầy đủ (26.10.187)

def _check_v2():
    """Tool đọc số / lập kế hoạch không cần máy nhà đang ghép, chỉ cần Đội Social đã mở khoá."""
    try:
        import doi_social_v2  # noqa: F401
        _, rds = _mods()
    except Exception:
        return "Đội Social bản đầy đủ chưa nạp được trên máy chủ này."
    return rds.ly_do_chan()


def _chat_id(args, ctx) -> str:
    cid = str((args or {}).get("chat_id") or "").strip()
    if cid:
        return cid
    try:
        import luot_dang_chay
        return luot_dang_chay.doan_chat_id(ctx.vault_root) or ""
    except Exception:
        return ""


def _la_telegram(chat_id: str) -> bool:
    return bool(re.fullmatch(r"-?\d+", str(chat_id or "").strip()))


def _so(v, mac=0):
    try:
        return int(v)
    except Exception:
        return mac


def _tong_quan(args, ctx):
    import doi_social_v2
    tq = doi_social_v2.tong_quan(_so(args.get("ngay"), 14) or 14) or {}
    so7 = tq.get("so7") or {}
    ai = tq.get("ai") or {}
    may = tq.get("may") or []
    dong = [f"Đội Social: {tq.get('nick_tong', 0)} nick"
            + (f" trên {', '.join(tq.get('nen_tang_dung') or [])}" if tq.get("nen_tang_dung") else "") + ".",
            "Máy ở nhà: " + (", ".join(f"{m.get('ten')} ({'đang bật' if m.get('online') else 'ngoại tuyến'})" for m in may)
                             if may else "chưa ghép máy nào") + ".",
            f"AI: {ai.get('engine') or '?'} · {ai.get('mo_hinh') or 'mặc định'}"
            + (" · nhìn được ảnh" if ai.get("nhin_anh") else "") + ("" if ai.get("san_sang", True) else " · CHƯA sẵn sàng"),
            f"7 ngày: {so7.get('luot', 0)} lượt, {so7.get('thanh_cong', 0)} thành công"
            + (f" ({so7.get('ty_le')}%)" if so7.get("ty_le") is not None else "")
            + f", {so7.get('loi', 0)} lỗi, {so7.get('dang_chay', 0)} đang chạy.",
            f"Hôm nay: {tq.get('hom_nay', 0)} lượt."]
    bd = tq.get("bieu_do") or []
    if bd:
        dong.append("Theo ngày (gần nhất): " + "; ".join(
            f"{str(b.get('ngay'))[5:]} {b.get('thanh_cong', 0)}/{b.get('loi', 0)} lỗi" for b in bd[-7:]))
    cx = tq.get("can_xu_ly") or []
    if cx:
        dong.append(f"Cần bạn xử lý ({len(cx)}):")
        for c in cx[:10]:
            dong.append(f"- {c.get('tieu_de')}" + (f": {c.get('chi_tiet')}" if c.get("chi_tiet") else ""))
    else:
        dong.append("Không có việc nào cần bạn xử lý.")
    return "\n".join(dong)


async def _ke_hoach(args, ctx):
    _, rds = _mods()
    yeu_cau = str(args.get("yeu_cau") or "").strip()
    if not yeu_cau:
        return "Thiếu yeu_cau: nói rõ muốn Đội Social làm gì."
    chat_id = _chat_id(args, ctx)
    phien = str(args.get("phien") or "").strip() or f"chat:{chat_id or 'minmin'}"
    # Luôn qua Telegram: nút Duyệt/Từ chối nằm ở đó (mục 6 KIEN-TRUC). chat_id không thuộc whitelist
    # Telegram (vd khung chat web) thì máy chủ gửi về chat đầu tiên của chủ.
    kq = await rds.tro_ly_tra_loi(yeu_cau, phien, nguon="telegram", chat_id=chat_id)
    kq = kq or {}
    out = [str(kq.get("tra_loi") or "").strip()]
    kh = kq.get("ke_hoach")
    if isinstance(kh, dict) and kh.get("id"):
        import doi_social_kich_ban as dskb
        for i, b in enumerate(kh.get("buoc") or [], 1):
            m = dskb.THEO_ID.get(str(b.get("kich_ban"))) or {}
            out.append(f"Bước {i}: {m.get('ten') or b.get('kich_ban')} · {len(b.get('nick') or [])} nick")
        out.append(f"Đã gửi kế hoạch #{kh['id']} lên Telegram, bấm Duyệt để chạy (hoặc duyệt ở Đội Social > Trợ lý AI). "
                   "Kế hoạch CHƯA chạy cho tới khi chủ duyệt.")
    else:
        out.append("Chưa có kế hoạch nào được tạo.")
    return "\n".join(x for x in out if x)


def _ds_nick_tu_args(v):
    if isinstance(v, list):
        return [x for x in v if str(x).strip()]
    s = str(v or "").strip()
    if not s:
        return []
    try:
        d = json.loads(s)
        if isinstance(d, list):
            return d
    except Exception:
        pass
    return [x.strip() for x in re.split(r"[,\n;]", s) if x.strip()]


def _giai_nick(ds):
    """Tên hoặc id -> id nick. Trả (ids, lỗi). Một tên khớp nhiều nick thì báo để hỏi lại, không đoán."""
    doi_social, _ = _mods()
    tat_ca = doi_social.ds_nick()
    theo_id = {str(n["id"]): n["id"] for n in tat_ca}
    ids, loi = [], []
    for x in ds:
        k = str(x).strip()
        if k in theo_id:
            v = theo_id[k]
        else:
            khop = [n for n in tat_ca if str(n.get("ten") or "").strip().lower() == k.lower()]
            if not khop:
                khop = doi_social.tim_nick(k) or []
            if len(khop) == 1:
                v = khop[0]["id"]
            elif not khop:
                loi.append(f"không thấy nick '{k}'")
                continue
            else:
                loi.append(f"'{k}' khớp {len(khop)} nick: " + ", ".join(f"{n['ten']} (id {n['id']})" for n in khop[:6]))
                continue
        if v not in ids:
            ids.append(v)
    return ids, loi


async def _chay_mau(args, ctx):
    import inspect
    import doi_social_kich_ban as dskb
    _, rds = _mods()
    mid = str(args.get("kich_ban") or "").strip()
    m = dskb.THEO_ID.get(mid)
    if not m:
        return f"Không có mẫu '{mid}'. Gọi social_tong_quan hoặc xem Đội Social > Automation để biết id mẫu."
    ids, loi = _giai_nick(_ds_nick_tu_args(args.get("nick")))
    if loi:
        return "Chưa chạy, cần hỏi lại chủ: " + "; ".join(loi) + "."
    if not ids:
        return "Thiếu nick: truyền tên hoặc id nick (gọi social_nick để xem danh sách)."
    ts = args.get("tham_so") or {}
    if isinstance(ts, str):
        try:
            ts = json.loads(ts) if ts.strip() else {}
        except Exception:
            return "tham_so phải là JSON object, vd {\"links\": [\"https://...\"]}."
    if not isinstance(ts, dict):
        return "tham_so phải là JSON object."
    keys = {f["key"] for f in m["tham_so"]}
    if "che_do" in keys and not ts.get("che_do"):
        ts["che_do"] = "chay_thu"      # mẫu AI: mặc định chạy thử, chỉ viết nháp
    try:
        ts = dskb.kiem_tham_so(mid, ts)
    except ValueError as e:
        return f"Chưa chạy được: {e}"
    chat_id = _chat_id(args, ctx)
    try:
        dot = rds.tao_dot_va_chay(kich_ban=mid, nick=ids, tham_so=ts, ten=str(args.get("ten") or ""),
                                  song_song=max(1, min(3, _so(args.get("song_song"), 1) or 1)),
                                  nguon="telegram" if _la_telegram(chat_id) else "web")
        if inspect.isawaitable(dot):
            dot = await dot
    except ValueError as e:
        return f"Chưa chạy được: {e}"
    dot = dot or {}
    dot = dot.get("dot") if isinstance(dot.get("dot"), dict) else dot
    che_do = ts.get("che_do")
    return (f"Đã tạo đợt chạy #{dot.get('id', '?')} '{dot.get('ten') or m['ten']}' cho {len(ids)} nick"
            + (f", chế độ {'chạy thử (chỉ viết nháp, không đăng)' if che_do == 'chay_thu' else che_do}" if che_do else "")
            + ". Máy ở nhà nhận việc ở lượt tới; tiến trình xem ở Đội Social > Nhật ký hoạt động."
            + (" Nháp AI viết sẽ nằm ở Duyệt nội dung." if che_do in ("chay_thu", "duyet_truoc") else ""))


def register(ctx):
    ctx.register_tool(
        name="social_tong_quan",
        description=("Đội Social: số liệu tổng quan (nick, máy ở nhà, AI, lượt chạy 7 ngày, thành công/lỗi, hôm nay, "
                     "việc cần chủ xử lý). Dùng để trả lời 'hôm nay các nick chạy thế nào'."),
        handler=_tong_quan, min_mode="readonly", check_fn=_check_v2,
        schema={"type": "object", "properties": {
            "ngay": {"type": "integer", "description": "Số ngày cho biểu đồ, mặc định 14"},
        }},
    )
    ctx.register_tool(
        name="social_ke_hoach",
        description=("Đội Social: giao việc bằng lời (vd 'đăng một bài thu hút lên fanpage đời sống', 'cho 3 nick bình "
                     "luận nhóm mẹ bỉm'). Trợ lý Đội Social lập KẾ HOẠCH (các đợt chạy mẫu cho nick), gửi Telegram kèm "
                     "nút Duyệt/Từ chối. KHÔNG tự chạy: chỉ chạy khi chủ bấm Duyệt."),
        handler=_ke_hoach, min_mode="full", check_fn=_check_v2,
        schema={"type": "object", "required": ["yeu_cau"], "properties": {
            "yeu_cau": {"type": "string", "description": "Yêu cầu nguyên văn của chủ"},
            "phien": {"type": "string", "description": "Mã phiên trợ lý để nối tiếp (bỏ trống = theo khung chat)"},
            "chat_id": {"type": "string", "description": "Chat Telegram nhận kế hoạch (bỏ trống = chủ)"},
        }},
    )
    ctx.register_tool(
        name="social_chay_mau",
        description=("Đội Social: tạo một đợt chạy MẪU tự động (id mẫu, vd fb_nuoi_nick, fb_binh_luan_nhom_sp) cho một "
                     "hoặc nhiều nick (tên hoặc id). Mẫu AI mặc định chế độ chạy thử (chỉ viết nháp). Chỉ gọi khi chủ "
                     "đã nói rõ mẫu và nick; việc mơ hồ thì dùng social_ke_hoach."),
        handler=_chay_mau, min_mode="full", check_fn=_check,
        schema={"type": "object", "required": ["kich_ban", "nick"], "properties": {
            "kich_ban": {"type": "string", "description": "Id mẫu, vd fb_nuoi_nick"},
            "nick": {"type": "array", "items": {"type": "string"},
                     "description": "Tên hoặc id nick (đúng như social_nick trả về)"},
            "tham_so": {"type": "object", "description": "Tham số của mẫu, vd {\"phut\": 10} hoặc {\"links\": [\"https://...\"]}"},
            "ten": {"type": "string", "description": "Tên đợt (tuỳ chọn)"},
            "song_song": {"type": "integer", "description": "Số nick chạy cùng lúc mỗi máy, 1-3"},
            "chat_id": {"type": "string"},
        }},
    )
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
        description="Đội Social: xem trạng thái các lượt đăng (chờ duyệt, đang chạy, xong, lỗi) hoặc một việc theo id; việc lỗi kèm nhật ký và chẩn đoán trang.",
        handler=_viec, min_mode="readonly", check_fn=_check,
        schema={"type": "object", "properties": {
            "id": {"type": "integer"},
            "trang_thai": {"type": "string", "enum": ["cho_duyet", "cho_chay", "dang_chay", "xong", "loi", "bo"]},
            "limit": {"type": "integer", "description": "Mặc định 10"},
        }},
    )
    ctx.register_tool(
        name="up_bai_chay",
        description=("Up bài từ Google Sheet UP BÀI ngay: tải video ở các dòng mới, AI nhận diện đồ và viết content "
                     "theo giá/mã, gửi Telegram để duyệt, đăng Reels các dòng đã duyệt đến giờ. 'dong' = chỉ chạy một dòng "
                     "(bỏ qua lịch giờ đăng)."),
        handler=_up_bai_chay, min_mode="full",
        schema={"type": "object", "properties": {"dong": {"type": "integer", "description": "Số dòng trong Sheet"}}},
    )
    ctx.register_tool(
        name="up_bai_trang_thai",
        description="Trạng thái Up bài từ Google Sheet: Sheet đã đặt chưa, có tự chạy không, lượt chạy gần nhất và nhật ký.",
        handler=_up_bai_trang_thai, min_mode="readonly",
        schema={"type": "object", "properties": {}},
    )
