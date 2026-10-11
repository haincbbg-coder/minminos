"""Plugin bundled: quản lý Trang/Fanpage Facebook qua Graph API.

Gọi THẲNG graph.facebook.com bằng user access token của kết nối "facebook-pages" (BYO app -
user tự tạo Facebook App, OAuth do oauth_mcp lo, token tự gia hạn ~60 ngày). Đọc danh sách Trang
qua /me/accounts, mỗi Trang có access_token RIÊNG - mọi thao tác trên một Trang (đăng bài, đọc/
trả lời bình luận) đều dùng token của chính Trang đó, KHÔNG dùng token cá nhân.

Tool đọc (fb_pages_list/fb_page_posts/fb_page_comments) = readonly. Tool ghi công khai
(fb_page_post/fb_page_photo/fb_page_album/fb_page_video/fb_page_edit/fb_page_reply) =
min_mode full → không bao giờ tự chạy ở chế độ suggest/auto, phải mức Toàn quyền + kết nối
đã ở mức đó.
Ảnh/video nhận URL http(s) hoặc file TRONG vault (sandbox như tool file); video upload đi
host graph-video riêng của Meta, Meta xử lý nền vài phút mới hiện bài.
"""
from __future__ import annotations

import json

GRAPH = "https://graph.facebook.com/v25.0"
# Upload video phải đi host riêng của Meta (graph thường từ chối file video)
GRAPH_VIDEO = "https://graph-video.facebook.com/v25.0"
CONNECTOR_ID = "facebook-pages"


def _conns():
    """MỌI kết nối facebook-pages ĐÃ đăng nhập: [{id, label, is_default}], tài khoản mặc định lên đầu.
    Import lười để load không phụ thuộc."""
    try:
        import mcp_store
        import oauth_mcp
    except Exception:
        return []
    out = []
    for c in mcp_store.list_connections():
        if c.get("connector_id") == CONNECTOR_ID and oauth_mcp.status(c["id"]).get("connected"):
            out.append({"id": c["id"], "label": c.get("label") or c.get("name") or c["id"],
                        "is_default": bool(c.get("is_default"))})
    out.sort(key=lambda x: not x["is_default"])     # sort ổn định: mặc định trước, còn lại giữ thứ tự thêm
    return out


def _connected_id():
    """id kết nối facebook-pages ĐÃ đăng nhập (ưu tiên tài khoản mặc định; None nếu chưa)."""
    cs = _conns()
    return cs[0]["id"] if cs else None


def _check():
    if not _connected_id():
        return ("Chưa kết nối Facebook Trang. Vào trang Kết nối, chọn 'Facebook Trang (tự tạo app - "
                "Graph API)', làm theo hướng dẫn tạo Facebook App rồi đăng nhập (nhớ tick chọn Trang). "
                "Sau đó gọi lại tool này.")
    return None


async def _token_of(cid):
    import oauth_mcp
    hdr = await oauth_mcp.auth_headers(cid)      # tự refresh token ~60 ngày khi sắp hết hạn
    return (hdr.get("Authorization", "") or "").replace("Bearer ", "").strip() or None


async def _token():
    """Token người dùng của tài khoản mặc định (dùng để kiểm 'đã kết nối chưa')."""
    cid = _connected_id()
    return await _token_of(cid) if cid else None


async def _acct_tokens(tai_khoan=""):
    """[(nhãn tài khoản, user token)] theo thứ tự ưu tiên (mặc định trước). `tai_khoan` (id hoặc tên)
    thu hẹp về đúng tài khoản đó. Trả (list, err)."""
    cs = _conns()
    if not cs:                                    # chưa có danh sách kết nối: dùng đường 1 token cũ
        t = await _token()
        return ([("", t)] if t else []), None
    ref = str(tai_khoan or "").strip().lower()
    if ref:
        sel = [c for c in cs if ref in (c["id"].lower(), c["label"].lower())] or \
              [c for c in cs if ref in c["label"].lower()]
        if not sel:
            return [], ("ERROR: Không có tài khoản Facebook '" + str(tai_khoan) + "'. Đang nối: " +
                        ", ".join(c["label"] for c in cs))
        cs = sel
    out = []
    for c in cs:
        t = await _token_of(c["id"])
        if t:
            out.append((c["label"], t))
    return out, None


async def _get(path, params, token):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{GRAPH}/{str(path).lstrip('/')}",
                            params={**(params or {}), "access_token": token})
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}"}}
    except Exception as e:
        return {"error": {"message": f"{type(e).__name__}: {e}"}}


async def _post(path, data, token):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{GRAPH}/{str(path).lstrip('/')}",
                             data={**(data or {}), "access_token": token})
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}"}}
    except Exception as e:
        return {"error": {"message": f"{type(e).__name__}: {e}"}}


async def _delete(path, token):
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.delete(f"{GRAPH}/{str(path).lstrip('/')}", params={"access_token": token})
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}"}}
    except Exception as e:
        return {"error": {"message": f"{type(e).__name__}: {e}"}}


def _fmt(d):
    if isinstance(d, dict) and d.get("error"):
        e = d["error"]
        return "ERROR: Facebook API: " + (e.get("message") if isinstance(e, dict) else str(e))
    return json.dumps(d, ensure_ascii=False, default=str)


async def _pages(user_token):
    """Danh sách Trang user quản lý, mỗi Trang kèm access_token RIÊNG. Trả (list, err)."""
    d = await _get("me/accounts", {"fields": "id,name,category,access_token,tasks", "limit": 200}, user_token)
    if isinstance(d, dict) and d.get("error"):
        return None, _fmt(d)
    return (d or {}).get("data") or [], None


# id Trang -> nhãn tài khoản Facebook đã được dùng cho lần thao tác gần nhất (để báo lại cho người dùng)
_PAGE_OWNER = {}


def _co_quyen_dang(p):
    t = p.get("tasks")
    return (not t) or any(x in t for x in ("CREATE_CONTENT", "MANAGE"))


async def _all_pages(tai_khoan=""):
    """Gộp Trang của MỌI tài khoản Facebook đã nối. Một Trang cả hai tài khoản cùng quản lý chỉ hiện
    một lần, kèm danh sách `owners`; token Trang lấy từ tài khoản có quyền đăng (mặc định trước).
    Trả (pages, loi_tung_tai_khoan, err)."""
    accts, err = await _acct_tokens(tai_khoan)
    if err:
        return None, [], err
    if not accts:
        return None, [], "ERROR: " + (_check() or "chưa kết nối")
    by_id, order, loi = {}, [], []
    for label, utok in accts:
        pages, e = await _pages(utok)
        if e:
            loi.append(f"{label or 'tài khoản'}: {e}")
            continue
        for p in pages:
            pid = str(p.get("id"))
            if pid not in by_id:
                by_id[pid] = {"id": p.get("id"), "name": p.get("name"), "category": p.get("category"),
                              "owners": [], "_cands": []}
                order.append(pid)
            if label and label not in by_id[pid]["owners"]:
                by_id[pid]["owners"].append(label)
            by_id[pid]["_cands"].append((label, p))
    if not order and loi:
        return None, loi, loi[0]
    out = []
    for pid in order:
        e = by_id[pid]
        cands = sorted(e["_cands"], key=lambda lp: not _co_quyen_dang(lp[1]))   # ổn định: mặc định trước
        label, p = cands[0]
        e["access_token"], e["tasks"], e["dung_tai_khoan"] = p.get("access_token"), p.get("tasks"), label
        del e["_cands"]
        out.append(e)
    return out, loi, None


async def _resolve_page(args, user_token=None):
    """Chọn Trang thao tác trong TẤT CẢ tài khoản Facebook đã nối. Trả (page_id, page_token, page_name, err).
    - page_id / page (tên) khớp: id chính xác, rồi tên chính xác, rồi tên chứa chuỗi (chỉ khi duy nhất);
    - bỏ trống mà chỉ có 1 Trang → tự lấy; nhiều Trang mà không chỉ rõ → lỗi kèm danh sách;
    - `tai_khoan` (id/tên tài khoản Facebook) thu hẹp phạm vi; không có thì MinMin tự tìm tài khoản
      đang quản lý Trang đó, nên đăng được từ bất kỳ máy/điện thoại nào."""
    args = args or {}
    pages, _loi, err = await _all_pages(args.get("tai_khoan"))
    if err:
        return None, None, None, err
    if not pages:
        return None, None, None, ("ERROR: Không thấy Trang nào bạn quản lý. Kiểm tra: bạn là Admin của Trang, "
                                  "và khi đăng nhập Facebook đã TICK chọn Trang đó cho app.")

    def _chon(p):
        _PAGE_OWNER[str(p.get("id"))] = p.get("dung_tai_khoan") or ""
        return p.get("id"), p.get("access_token"), p.get("name"), None

    avail = ", ".join(f"{p.get('name')} ({p.get('id')})" for p in pages)
    ref = str(args.get("page_id") or args.get("page") or "").strip()
    if ref:
        rl = ref.lower()
        hit = [p for p in pages if str(p.get("id")) == ref]
        hit = hit or [p for p in pages if str(p.get("name", "")).strip().lower() == rl]
        hit = hit or [p for p in pages if rl in str(p.get("name", "")).lower()]
        if len(hit) == 1:
            return _chon(hit[0])
        if len(hit) > 1:
            return None, None, None, ("ERROR: '" + ref + "' khớp nhiều Trang: " +
                                      ", ".join(f"{p.get('name')} ({p.get('id')})" for p in hit) +
                                      ". Chỉ rõ page_id hoặc tên đầy đủ.")
        return None, None, None, f"ERROR: Không khớp Trang '{ref}'. Trang bạn có: {avail}"
    if len(pages) == 1:
        return _chon(pages[0])
    return None, None, None, f"ERROR: Bạn có nhiều Trang, cần chỉ rõ page_id hoặc page (tên). Trang: {avail}"


async def _list(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    pages, loi, err = await _all_pages((args or {}).get("tai_khoan"))
    if err:
        return err
    # KHÔNG lộ access_token của Trang. `tai_khoan` = các tài khoản Facebook đang quản lý Trang đó.
    safe = []
    for p in pages:
        row = {"id": p.get("id"), "name": p.get("name"), "category": p.get("category"), "tasks": p.get("tasks")}
        if p.get("owners"):
            row["tai_khoan"] = p["owners"]
        safe.append(row)
    if loi:
        return json.dumps({"trang": safe, "loi_tai_khoan": loi}, ensure_ascii=False, default=str)
    return json.dumps(safe, ensure_ascii=False, default=str)


async def _posts(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    pid, ptok, pname, err = await _resolve_page(args, token)
    if err:
        return err
    args = args or {}
    try:
        limit = max(1, min(100, int(args.get("limit") or 10)))
    except (TypeError, ValueError):
        limit = 10
    d = await _get(f"{pid}/feed",
                   {"fields": "id,message,story,created_time,permalink_url,comments.summary(true).limit(0)",
                    "limit": limit}, ptok)
    return _fmt(d)


async def _comments(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    obj = str(args.get("post_id") or args.get("object_id") or "").strip()
    if not obj:
        return "ERROR: thiếu 'post_id' (id bài cần đọc bình luận; lấy từ fb_page_posts)."
    # post_id dạng {pageid}_{postid}: tự suy Trang khi user không chỉ rõ.
    if not (args.get("page_id") or args.get("page")) and "_" in obj:
        args = {**args, "page_id": obj.split("_", 1)[0]}
    pid, ptok, pname, err = await _resolve_page(args, token)
    if err:
        return err
    try:
        limit = max(1, min(100, int(args.get("limit") or 25)))
    except (TypeError, ValueError):
        limit = 25
    d = await _get(f"{obj}/comments",
                   {"fields": "id,from,message,created_time,like_count",
                    "order": "reverse_chronological", "limit": limit}, ptok)
    return _fmt(d)


async def _publish(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    msg = str(args.get("message") or "").strip()
    link = str(args.get("link") or "").strip()
    if not msg and not link:
        return "ERROR: cần 'message' (nội dung bài) hoặc 'link'."
    pid, ptok, pname, err = await _resolve_page(args, token)
    if err:
        return err
    data = {}
    if msg:
        data["message"] = msg
    if link:
        data["link"] = link
    d = await _post(f"{pid}/feed", data, ptok)
    if isinstance(d, dict) and d.get("error"):
        return _fmt(d)
    return json.dumps({"ok": True, "page": pname, "tai_khoan": _PAGE_OWNER.get(str(pid)) or None,
                       "post_id": d.get("id") if isinstance(d, dict) else None},
                      ensure_ascii=False, default=str)


def _media_roots(cctx):
    """Các gốc được phép đọc media: (1) vault đang làm việc, (2) vùng nhận file
    STATE_DIR/.staging - nơi ảnh/video user dán vào khung chat dashboard rơi xuống.
    File trong staging là file CHÍNH CHỦ vừa gửi nên đăng được, không phải mở sandbox bừa.
    (File gửi qua Telegram đã rơi sẵn vào <vault>/inbox/telegram nên thuộc gốc 1.)"""
    from pathlib import Path
    roots = []
    root = getattr(cctx, "vault_root", None)
    if root:
        try:
            roots.append(Path(root).resolve())
        except OSError:
            pass
    try:
        from config import STATE_DIR
        roots.append((Path(STATE_DIR) / ".staging").resolve())
    except Exception:
        pass
    return roots


def _resolve_media(ref, cctx):
    """'photo'/'video' nhận URL http(s) HOẶC đường dẫn file trong vault / vùng nhận file
    của chat (tương đối thử lần lượt từng gốc). Trả (url, path, err) - đúng một trong
    url/path có giá trị. File NGOÀI các gốc cho phép thì từ chối - plugin chạy full quyền
    nhưng không vì thế mà cho đăng file tuỳ ý trên máy lên mạng."""
    from pathlib import Path
    ref = str(ref or "").strip()
    if not ref:
        return None, None, "ERROR: thiếu đường dẫn file hoặc URL http(s) của media."
    if ref.startswith("http://") or ref.startswith("https://"):
        return ref, None, None
    roots = _media_roots(cctx)
    if not roots:
        return None, None, "ERROR: không xác định được vault/vùng nhận file để tìm media."
    try:
        if Path(ref).is_absolute():
            rp = Path(ref).resolve()
            if any(str(rp).startswith(str(r)) for r in roots) and rp.is_file():
                return None, rp, None
        else:
            for r in roots:
                cand = (r / ref).resolve()
                if str(cand).startswith(str(r)) and cand.is_file():
                    return None, cand, None
    except OSError as e:
        return None, None, f"ERROR: không đọc được đường dẫn ({type(e).__name__})."
    return None, None, (f"ERROR: không thấy '{ref}' trong vault hay vùng nhận file của chat. "
                        "File phải nằm trong vault, hoặc là file vừa gửi qua khung chat/Telegram.")


async def _post_file(path_in_graph, file_path, data, token, base=GRAPH, timeout=900):
    """POST multipart (upload file thật). Video đi base GRAPH_VIDEO, timeout dài."""
    import mimetypes
    import httpx
    from pathlib import Path
    mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    try:
        with open(file_path, "rb") as f:
            files = {"source": (Path(file_path).name, f, mime)}
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(f"{base}/{str(path_in_graph).lstrip('/')}",
                                 data={**(data or {}), "access_token": token}, files=files)
        try:
            return r.json()
        except Exception:
            return {"error": {"message": f"HTTP {r.status_code}: {r.text[:200]}"}}
    except Exception as e:
        return {"error": {"message": f"{type(e).__name__}: {e}"}}


async def _publish_photo(args, cctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    url, path, err = _resolve_media(args.get("photo") or args.get("image") or "", cctx)
    if err:
        return err
    pid, ptok, pname, perr = await _resolve_page(args, token)
    if perr:
        return perr
    caption = str(args.get("message") or args.get("caption") or "").strip()
    data = {"caption": caption} if caption else {}
    if url:
        d = await _post(f"{pid}/photos", {**data, "url": url}, ptok)
    else:
        d = await _post_file(f"{pid}/photos", path, data, ptok)
    if isinstance(d, dict) and d.get("error"):
        return _fmt(d)
    return json.dumps({"ok": True, "page": pname, "tai_khoan": _PAGE_OWNER.get(str(pid)) or None,
                       "photo_id": d.get("id") if isinstance(d, dict) else None,
                       "post_id": d.get("post_id") if isinstance(d, dict) else None},
                      ensure_ascii=False, default=str)


async def _publish_video(args, cctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    url, path, err = _resolve_media(args.get("video") or "", cctx)
    if err:
        return err
    pid, ptok, pname, perr = await _resolve_page(args, token)
    if perr:
        return perr
    data = {}
    desc = str(args.get("message") or args.get("description") or "").strip()
    title = str(args.get("title") or "").strip()
    if desc:
        data["description"] = desc
    if title:
        data["title"] = title
    if url:
        d = await _post(f"{pid}/videos", {**data, "file_url": url}, ptok)
    else:
        d = await _post_file(f"{pid}/videos", path, data, ptok, base=GRAPH_VIDEO)
    if isinstance(d, dict) and d.get("error"):
        return _fmt(d)
    return json.dumps({"ok": True, "page": pname, "tai_khoan": _PAGE_OWNER.get(str(pid)) or None,
                       "video_id": d.get("id") if isinstance(d, dict) else None,
                       "note": "Video Facebook xử lý nền vài phút rồi mới hiện trên Trang."},
                      ensure_ascii=False, default=str)


async def _publish_album(args, cctx):
    """Đăng NHIỀU ảnh thành một bài (album): up từng ảnh published=false lấy id,
    rồi gom vào MỘT bài /feed qua attached_media. Meta cho tối đa 10 ảnh một bài."""
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    photos = args.get("photos") or []
    if isinstance(photos, str):   # model hay đưa chuỗi cách nhau dấu phẩy
        photos = [p.strip() for p in photos.split(",") if p.strip()]
    if len(photos) < 2:
        return "ERROR: album cần ít nhất 2 ảnh trong 'photos' (1 ảnh thì dùng fb_page_photo)."
    if len(photos) > 10:
        return f"ERROR: Meta cho tối đa 10 ảnh một bài, đang có {len(photos)}. Bớt lại hoặc chia 2 bài."
    pid, ptok, pname, perr = await _resolve_page(args, token)
    if perr:
        return perr
    media_ids = []
    for i, ref in enumerate(photos):
        url, path, err = _resolve_media(ref, cctx)
        if err:
            return f"{err} (ảnh thứ {i + 1}: {str(ref)[:80]})"
        if url:
            d = await _post(f"{pid}/photos", {"url": url, "published": "false"}, ptok)
        else:
            d = await _post_file(f"{pid}/photos", path, {"published": "false"}, ptok)
        if isinstance(d, dict) and d.get("error"):
            return _fmt(d) + f" (ảnh thứ {i + 1})"
        mid = (d or {}).get("id") if isinstance(d, dict) else None
        if not mid:
            return f"ERROR: Facebook không trả id cho ảnh thứ {i + 1}."
        media_ids.append(mid)
    data = {}
    msg = str(args.get("message") or "").strip()
    if msg:
        data["message"] = msg
    for i, mid in enumerate(media_ids):
        data[f"attached_media[{i}]"] = json.dumps({"media_fbid": mid})
    d = await _post(f"{pid}/feed", data, ptok)
    if isinstance(d, dict) and d.get("error"):
        return _fmt(d)
    return json.dumps({"ok": True, "page": pname, "tai_khoan": _PAGE_OWNER.get(str(pid)) or None, "photos": len(media_ids),
                       "post_id": d.get("id") if isinstance(d, dict) else None},
                      ensure_ascii=False, default=str)


async def _edit_post(args, cctx):
    """Sửa NỘI DUNG CHỮ của bài đã đăng. Meta chỉ cho đổi message - không đổi được
    ảnh/video đã đính kèm (muốn đổi media thì xoá đăng lại, Javis không tự xoá)."""
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    post_id = str(args.get("post_id") or "").strip()
    msg = str(args.get("message") or "").strip()
    if not post_id:
        return "ERROR: thiếu 'post_id' (id bài cần sửa, lấy từ fb_page_posts)."
    if not msg:
        return "ERROR: thiếu 'message' (nội dung MỚI thay cho nội dung cũ)."
    # post_id dạng {pageid}_{postid}: tự suy Trang như fb_page_comments
    if not (args.get("page_id") or args.get("page")) and "_" in post_id:
        args = {**args, "page_id": post_id.split("_", 1)[0]}
    pid, ptok, pname, err = await _resolve_page(args, token)
    if err:
        return err
    d = await _post(post_id, {"message": msg}, ptok)
    if isinstance(d, dict) and d.get("error"):
        return _fmt(d)
    ok = bool(isinstance(d, dict) and (d.get("success") is True or d.get("id")))
    return json.dumps({"ok": ok, "page": pname, "tai_khoan": _PAGE_OWNER.get(str(pid)) or None, "post_id": post_id,
                       "note": "" if ok else "Facebook trả về khác thường: " + str(d)[:120]},
                      ensure_ascii=False, default=str)


async def _delete_post(args, cctx):
    """XOÁ HẲN một bài đã đăng trên Trang. Meta không có thùng rác cho bài Trang nên
    KHÔNG khôi phục được. Trước khi xoá có đọc lại bài, vừa để chắc đúng bài vừa giữ
    lại nội dung trả về cho người dùng đối chiếu (và có cái dán lại nếu lỡ tay)."""
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    post_id = str(args.get("post_id") or "").strip()
    if not post_id:
        return "ERROR: thiếu 'post_id' (id bài cần xoá, lấy từ fb_page_posts)."
    # post_id dạng {pageid}_{postid}: tự suy Trang như fb_page_edit
    if not (args.get("page_id") or args.get("page")) and "_" in post_id:
        args = {**args, "page_id": post_id.split("_", 1)[0]}
    pid, ptok, pname, err = await _resolve_page(args, token)
    if err:
        return err
    snap = await _get(post_id, {"fields": "id,message,created_time,permalink_url"}, ptok)
    if isinstance(snap, dict) and snap.get("error"):
        return _fmt(snap)                      # bài không tồn tại / không thuộc Trang này → dừng, chưa xoá gì
    d = await _delete(post_id, ptok)
    if isinstance(d, dict) and d.get("error"):
        return _fmt(d)
    ok = bool(isinstance(d, dict) and d.get("success") is True)
    cu = str((snap or {}).get("message") or "")
    return json.dumps({"ok": ok, "page": pname, "tai_khoan": _PAGE_OWNER.get(str(pid)) or None, "post_id": post_id,
                       "noi_dung_da_xoa": (cu[:300] + "…") if len(cu) > 300 else cu,
                       "created_time": (snap or {}).get("created_time"),
                       "note": "Đã xoá hẳn, KHÔNG khôi phục được." if ok
                               else "Facebook trả về khác thường: " + str(d)[:120]},
                      ensure_ascii=False, default=str)


async def _reply(args, ctx):
    token = await _token()
    if not token:
        return "ERROR: " + (_check() or "chưa kết nối")
    args = args or {}
    target = str(args.get("comment_id") or args.get("object_id") or args.get("post_id") or "").strip()
    msg = str(args.get("message") or "").strip()
    if not target:
        return "ERROR: thiếu 'comment_id' (bình luận cần trả lời) hoặc 'post_id' (để bình luận vào bài)."
    if not msg:
        return "ERROR: thiếu 'message' (nội dung trả lời)."
    pid, ptok, pname, err = await _resolve_page(args, token)
    if err:
        return err
    d = await _post(f"{target}/comments", {"message": msg}, ptok)
    if isinstance(d, dict) and d.get("error"):
        return _fmt(d)
    return json.dumps({"ok": True, "page": pname, "tai_khoan": _PAGE_OWNER.get(str(pid)) or None,
                       "reply_id": d.get("id") if isinstance(d, dict) else None},
                      ensure_ascii=False, default=str)


def register(ctx):
    ctx.register_tool(
        name="fb_pages_list", min_mode="readonly", check_fn=_check, handler=_list,
        description=("Liệt kê Trang/Fanpage Facebook của MỌI tài khoản Facebook đã nối, kèm tài khoản nào đang quản lý Trang nào (id, tên, hạng mục, quyền). Gọi đầu "
                     "tiên để lấy id/tên Trang cho các tool khác. KHÔNG lộ token của Trang."),
        schema={"type": "object", "properties": {
            "tai_khoan": {"type": "string", "description": "Chỉ liệt kê Trang của tài khoản Facebook này (bỏ trống = tất cả)"}}},
    )
    ctx.register_tool(
        name="fb_page_posts", min_mode="readonly", check_fn=_check, handler=_posts,
        description=("Đọc các bài GẦN ĐÂY trên một Trang của bạn (id bài, nội dung, thời gian, link, số bình "
                     "luận). Bỏ trống page nếu chỉ có 1 Trang; nhiều Trang thì truyền page_id hoặc page (tên)."),
        schema={"type": "object", "properties": {
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = MinMin tự tìm tài khoản đang quản lý Trang)"},
            "page_id": {"type": "string", "description": "id Trang (bỏ trống nếu chỉ có 1 Trang)"},
            "page": {"type": "string", "description": "tên Trang (thay cho page_id)"},
            "limit": {"type": "integer", "description": "Số bài tối đa (mặc định 10)"}}},
    )
    ctx.register_tool(
        name="fb_page_comments", min_mode="readonly", check_fn=_check, handler=_comments,
        description=("Đọc bình luận của MỘT bài trên Trang (người bình luận, nội dung, thời gian). Cần post_id "
                     "lấy từ fb_page_posts. Trang tự suy từ post_id; nhiều Trang thì truyền thêm page_id/page nếu cần."),
        schema={"type": "object", "properties": {
            "post_id": {"type": "string", "description": "id bài cần đọc bình luận (từ fb_page_posts)"},
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = MinMin tự tìm tài khoản đang quản lý Trang)"},
            "page_id": {"type": "string", "description": "id Trang (thường không cần, suy từ post_id)"},
            "page": {"type": "string", "description": "tên Trang (tuỳ chọn)"},
            "limit": {"type": "integer", "description": "Số bình luận tối đa (mặc định 25)"}},
            "required": ["post_id"]},
    )
    ctx.register_tool(
        name="fb_page_post", min_mode="full", check_fn=_check, handler=_publish,
        description=("ĐĂNG một bài lên Trang của bạn - hành động THẬT, công khai. Cần message (nội dung) và/hoặc "
                     "link. Bỏ trống page nếu chỉ có 1 Trang; nhiều Trang thì truyền page_id/page."),
        schema={"type": "object", "properties": {
            "message": {"type": "string", "description": "Nội dung bài đăng"},
            "link": {"type": "string", "description": "Link đính kèm (tuỳ chọn)"},
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = MinMin tự tìm tài khoản đang quản lý Trang)"},
            "page_id": {"type": "string", "description": "id Trang (bỏ trống nếu chỉ có 1 Trang)"},
            "page": {"type": "string", "description": "tên Trang (thay cho page_id)"}}},
    )
    ctx.register_tool(
        name="fb_page_photo", min_mode="full", check_fn=_check, handler=_publish_photo,
        description=("ĐĂNG ẢNH lên Trang của bạn - hành động THẬT, công khai. photo = đường dẫn file ảnh "
                     "trong vault (vd attachments/anh.jpg) hoặc URL http(s). message = caption tuỳ chọn. "
                     "Bỏ trống page nếu chỉ có 1 Trang."),
        schema={"type": "object", "properties": {
            "photo": {"type": "string", "description": "Đường dẫn ảnh trong vault hoặc URL http(s)"},
            "message": {"type": "string", "description": "Caption cho ảnh (tuỳ chọn)"},
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = MinMin tự tìm tài khoản đang quản lý Trang)"},
            "page_id": {"type": "string", "description": "id Trang (bỏ trống nếu chỉ có 1 Trang)"},
            "page": {"type": "string", "description": "tên Trang (thay cho page_id)"}},
            "required": ["photo"]},
    )
    ctx.register_tool(
        name="fb_page_album", min_mode="full", check_fn=_check, handler=_publish_album,
        description=("ĐĂNG ALBUM: nhiều ảnh (2-10) gom vào MỘT bài trên Trang - hành động THẬT, công khai. "
                     "photos = danh sách đường dẫn ảnh trong vault hoặc URL http(s). message = caption chung. "
                     "Một ảnh thì dùng fb_page_photo."),
        schema={"type": "object", "properties": {
            "photos": {"type": "array", "items": {"type": "string"},
                       "description": "2-10 ảnh: đường dẫn trong vault hoặc URL http(s)"},
            "message": {"type": "string", "description": "Caption chung của album (tuỳ chọn)"},
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = MinMin tự tìm tài khoản đang quản lý Trang)"},
            "page_id": {"type": "string", "description": "id Trang (bỏ trống nếu chỉ có 1 Trang)"},
            "page": {"type": "string", "description": "tên Trang (thay cho page_id)"}},
            "required": ["photos"]},
    )
    ctx.register_tool(
        name="fb_page_edit", min_mode="full", check_fn=_check, handler=_edit_post,
        description=("SỬA nội dung chữ của một bài ĐÃ ĐĂNG trên Trang - hành động THẬT. Cần post_id (từ "
                     "fb_page_posts) và message MỚI thay toàn bộ nội dung cũ. Meta không cho đổi ảnh/video "
                     "đã đính kèm, chỉ đổi được chữ - muốn đổi ảnh thì đăng bài mới rồi fb_page_delete bài cũ."),
        schema={"type": "object", "properties": {
            "post_id": {"type": "string", "description": "id bài cần sửa (từ fb_page_posts)"},
            "message": {"type": "string", "description": "Nội dung MỚI thay cho nội dung cũ"},
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = MinMin tự tìm tài khoản đang quản lý Trang)"},
            "page_id": {"type": "string", "description": "id Trang (thường tự suy từ post_id)"},
            "page": {"type": "string", "description": "tên Trang (tuỳ chọn)"}},
            "required": ["post_id", "message"]},
    )
    ctx.register_tool(
        name="fb_page_video", min_mode="full", check_fn=_check, handler=_publish_video,
        description=("ĐĂNG VIDEO lên Trang của bạn - hành động THẬT, công khai. video = đường dẫn file "
                     "video trong vault hoặc URL http(s) (tối đa cỡ 1GB). message = mô tả, title = tiêu đề, "
                     "đều tuỳ chọn. Facebook xử lý nền vài phút mới hiện bài. Bỏ trống page nếu chỉ có 1 Trang."),
        schema={"type": "object", "properties": {
            "video": {"type": "string", "description": "Đường dẫn video trong vault hoặc URL http(s)"},
            "message": {"type": "string", "description": "Mô tả video (tuỳ chọn)"},
            "title": {"type": "string", "description": "Tiêu đề video (tuỳ chọn)"},
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = MinMin tự tìm tài khoản đang quản lý Trang)"},
            "page_id": {"type": "string", "description": "id Trang (bỏ trống nếu chỉ có 1 Trang)"},
            "page": {"type": "string", "description": "tên Trang (thay cho page_id)"}},
            "required": ["video"]},
    )
    ctx.register_tool(
        name="fb_page_delete", min_mode="full", check_fn=_check, handler=_delete_post,
        description=("XOÁ HẲN một bài đã đăng trên Trang - hành động THẬT, KHÔNG HOÀN TÁC ĐƯỢC (Trang không "
                     "có thùng rác). Cần post_id từ fb_page_posts. CHỈ gọi khi người dùng nói rõ muốn xoá "
                     "đúng bài đó; đừng tự xoá để 'dọn dẹp'. Xoá xong trả lại đoạn nội dung vừa xoá để đối chiếu."),
        schema={"type": "object", "properties": {
            "post_id": {"type": "string", "description": "id bài cần xoá (từ fb_page_posts)"},
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = MinMin tự tìm tài khoản đang quản lý Trang)"},
            "page_id": {"type": "string", "description": "id Trang (thường tự suy từ post_id)"},
            "page": {"type": "string", "description": "tên Trang (tuỳ chọn)"}},
            "required": ["post_id"]},
    )
    ctx.register_tool(
        name="fb_page_reply", min_mode="full", check_fn=_check, handler=_reply,
        description=("TRẢ LỜI một bình luận, hoặc bình luận vào một bài - hành động THẬT, công khai. Cần message "
                     "và comment_id (trả lời bình luận) HOẶC post_id (bình luận vào bài). Nhiều Trang thì truyền "
                     "page_id/page."),
        schema={"type": "object", "properties": {
            "message": {"type": "string", "description": "Nội dung trả lời"},
            "comment_id": {"type": "string", "description": "id bình luận cần trả lời"},
            "post_id": {"type": "string", "description": "id bài (bình luận thẳng vào bài thay vì trả lời 1 comment)"},
            "tai_khoan": {"type": "string", "description": "Tên/id tài khoản Facebook muốn dùng (bỏ trống = MinMin tự tìm tài khoản đang quản lý Trang)"},
            "page_id": {"type": "string", "description": "id Trang (khi có nhiều Trang)"},
            "page": {"type": "string", "description": "tên Trang (khi có nhiều Trang)"}},
            "required": ["message"]},
    )
