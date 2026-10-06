"""Khu vực THÀNH VIÊN: quản lý thành viên (chỉ admin) và API /m/* (chỉ thành viên).

Quy tắc an toàn (deny-by-default):
- Admin endpoint đòi PHIÊN THẬT của admin (không nhận API token, không nhận phiên thành viên).
- /m/* đòi phiên thành viên; trừ /m/me và /m/2fa/* thì phải đã qua 2FA (`full`).
- Mọi đường dẫn bị khoá trong GỐC của brain được cấp: resolve() sau đó relative_to(gốc), nên
  symlink trỏ ra ngoài cũng bị chặn. Thư mục/tệp bắt đầu bằng "." và vài thư mục nhạy cảm bị ẩn.
"""
import json
import mimetypes
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Form, Request
from fastapi.responses import FileResponse, JSONResponse

import config as cfgmod
import members

COOKIE = "javis_session"
DOC_TOI_DA = 2 * 1024 * 1024
GHI_TOI_DA = 1024 * 1024
DUOI_TEXT = {".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".html", ".htm", ".log", ".tsv"}
DUOI_GHI = {".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".tsv"}
DUOI_ANH = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"}
AN_TOP = {"plugins", "node_modules", "memory", "__pycache__"}
AN_TEN = {".env", "settings.json"}


@dataclass
class MemberDeps:
    brains_dir: Callable[[], str]
    ten_workspace: Callable[[], str]


_DEPS: MemberDeps = None


def _loi(msg, code=400):
    return JSONResponse({"ok": False, "error": msg}, status_code=code)


def _admin(request: Request):
    """None nếu là admin phiên thật; ngược lại trả response lỗi."""
    if not cfgmod.valid_session(request.cookies.get(COOKIE, "")):
        return _loi("Chỉ admin đăng nhập bằng trình duyệt mới quản lý thành viên.", 403)
    return None


def _thanh_vien(request: Request, can_full=True):
    p = members.phien(request.cookies.get(COOKIE, ""))
    if not p:
        return None, _loi("Chưa đăng nhập", 401)
    if can_full and not p["full"]:
        return None, JSONResponse({"ok": False, "needs_2fa_setup": True,
                                   "error": "Phải bật xác thực 2 lớp trước."}, status_code=403)
    return p, None


def _an(rel_parts) -> bool:
    for i, part in enumerate(rel_parts):
        if part.startswith(".") or part in AN_TEN:
            return True
        if i == 0 and part in AN_TOP:
            return True
    return False


def _goc(p, brain: str):
    """(gốc_đã_resolve, quyền) hoặc (None, None) nếu không được cấp / không tồn tại."""
    brain = str(brain or "").strip()
    quyen = (p["user"].get("grants") or {}).get(brain)
    if quyen not in members.ROLES or "/" in brain or "\\" in brain or brain.startswith("."):
        return None, None
    base = Path(_DEPS.brains_dir()).resolve()
    goc = (base / brain).resolve()
    if goc.parent != base or not goc.is_dir():
        return None, None
    return goc, quyen


def _duong_dan(goc: Path, rel: str):
    """Đường dẫn tuyệt đối đã kiểm; None nếu thoát khỏi gốc hoặc nằm trong vùng ẩn."""
    rel = str(rel or "").replace("\\", "/").strip("/")
    parts = [x for x in rel.split("/") if x not in ("", ".")]
    if ".." in parts or _an(parts):
        return None
    t = (goc / "/".join(parts)).resolve() if parts else goc
    try:
        t.relative_to(goc)
    except ValueError:
        return None
    return t


def _make_router():
    r = APIRouter()

    # ---------- Admin ----------
    @r.get("/members")
    async def ds(request: Request):
        e = _admin(request)
        if e:
            return e
        return {"ok": True, "members": members.danh_sach()}

    @r.post("/members")
    async def tao(request: Request, email: str = Form(...), password: str = Form(...),
                  name: str = Form(""), grants: str = Form("{}")):
        e = _admin(request)
        if e:
            return e
        try:
            g = json.loads(grants or "{}")
        except Exception:
            return _loi("grants không phải JSON")
        try:
            return {"ok": True, "member": members.tao(email, name, password, g)}
        except ValueError as ex:
            return _loi(str(ex))

    @r.post("/members/update")
    async def capnhat(request: Request, email: str = Form(...), name: str = Form(None),
                      grants: str = Form(None), disabled: str = Form(None),
                      password: str = Form(None), reset_2fa: str = Form("")):
        e = _admin(request)
        if e:
            return e
        try:
            g = json.loads(grants) if grants is not None else None
            dis = None if disabled is None else disabled.strip().lower() in ("1", "true", "yes")
            return {"ok": True, "member": members.sua(
                email, name=name, grants=g, disabled=dis, password=password or None,
                reset_2fa=reset_2fa.strip().lower() in ("1", "true", "yes"))}
        except KeyError as ex:
            return _loi(str(ex.args[0]), 404)
        except (ValueError, TypeError) as ex:
            return _loi(str(ex))

    @r.post("/members/delete")
    async def xoa(request: Request, email: str = Form(...)):
        e = _admin(request)
        if e:
            return e
        return {"ok": members.xoa(email)}

    # ---------- Thành viên ----------
    @r.get("/m/me")
    async def me(request: Request):
        p, e = _thanh_vien(request, can_full=False)
        if e:
            return e
        u = p["user"]
        return {"ok": True, "email": p["email"], "name": u.get("name", ""),
                "full": p["full"], "tfa": bool(u.get("tfa_enabled")),
                "grants": u.get("grants", {})}

    @r.post("/m/logout")
    async def thoat(request: Request):
        tok = request.cookies.get(COOKIE, "")
        members.dong_phien(token=tok)
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @r.post("/m/2fa/start")
    async def tfa_start(request: Request):
        p, e = _thanh_vien(request, can_full=False)
        if e:
            return e
        if p["user"].get("tfa_enabled"):
            return _loi("2FA đã bật rồi")
        return {"ok": True, **members.tfa_bat_dau(p["email"], _DEPS.ten_workspace())}

    @r.post("/m/2fa/enable")
    async def tfa_enable(request: Request, code: str = Form(...)):
        p, e = _thanh_vien(request, can_full=False)
        if e:
            return e
        ma = members.tfa_bat(p["email"], code)
        if ma is None:
            return _loi("Mã không đúng hoặc đã hết hạn, bấm bắt đầu lại.")
        members.nang_phien(request.cookies.get(COOKIE, ""))
        return {"ok": True, "recovery": ma}

    @r.get("/m/brains")
    async def brains(request: Request):
        p, e = _thanh_vien(request)
        if e:
            return e
        out = []
        for ten, q in (p["user"].get("grants") or {}).items():
            goc, quyen = _goc(p, ten)
            if goc:
                out.append({"name": ten, "role": quyen})
        return {"ok": True, "brains": out}

    @r.get("/m/files/list")
    async def ls(request: Request, brain: str, path: str = ""):
        p, e = _thanh_vien(request)
        if e:
            return e
        goc, q = _goc(p, brain)
        if not goc:
            return _loi("Không có quyền với brain này", 403)
        t = _duong_dan(goc, path)
        if not t or not t.is_dir():
            return _loi("Không có thư mục", 404)
        items = []
        for c in sorted(t.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            rel = c.relative_to(goc).parts if not c.is_symlink() else None
            if rel is None:
                try:
                    rel = c.resolve().relative_to(goc).parts
                except ValueError:
                    continue
            if _an(rel):
                continue
            try:
                st = c.stat()
            except OSError:
                continue
            items.append({"name": c.name, "dir": c.is_dir(), "size": 0 if c.is_dir() else st.st_size,
                          "mtime": st.st_mtime})
        return {"ok": True, "role": q, "items": items}

    @r.get("/m/files/read")
    async def doc(request: Request, brain: str, path: str):
        p, e = _thanh_vien(request)
        if e:
            return e
        goc, q = _goc(p, brain)
        if not goc:
            return _loi("Không có quyền với brain này", 403)
        t = _duong_dan(goc, path)
        if not t or not t.is_file() or t.suffix.lower() not in DUOI_TEXT:
            return _loi("Không đọc được tệp này", 404)
        if t.stat().st_size > DOC_TOI_DA:
            return _loi("Tệp quá lớn để xem", 413)
        return {"ok": True, "role": q, "text": t.read_text(encoding="utf-8", errors="replace"),
                "mtime": t.stat().st_mtime}

    @r.get("/m/files/raw")
    async def raw(request: Request, brain: str, path: str):
        p, e = _thanh_vien(request)
        if e:
            return e
        goc, q = _goc(p, brain)
        if not goc:
            return _loi("Không có quyền với brain này", 403)
        t = _duong_dan(goc, path)
        if not t or not t.is_file() or t.suffix.lower() not in DUOI_ANH:
            return _loi("Không có tệp", 404)
        mt = mimetypes.guess_type(t.name)[0] or "application/octet-stream"
        if t.suffix.lower() == ".svg":
            mt = "text/plain"          # SVG có thể chứa script: không cho chạy như trang
        return FileResponse(str(t), media_type=mt, headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self' data:"})

    @r.post("/m/files/write")
    async def ghi(request: Request, brain: str = Form(...), path: str = Form(...),
                  text: str = Form(...)):
        p, e = _thanh_vien(request)
        if e:
            return e
        goc, q = _goc(p, brain)
        if not goc:
            return _loi("Không có quyền với brain này", 403)
        if q != "edit":
            return _loi("Bạn chỉ có quyền xem brain này", 403)
        t = _duong_dan(goc, path)
        if not t or t == goc or t.suffix.lower() not in DUOI_GHI:
            return _loi("Chỉ sửa được tệp văn bản (md, txt, csv, json, yaml)", 400)
        if t.exists() and not t.is_file():
            return _loi("Đây không phải tệp", 400)
        data = text.encode("utf-8")
        if len(data) > GHI_TOI_DA:
            return _loi("Nội dung quá lớn (tối đa 1MB)", 413)
        t.parent.mkdir(parents=True, exist_ok=True)
        tmp = t.with_name(t.name + ".mm-tmp")
        tmp.write_bytes(data)
        os.replace(tmp, t)
        try:
            with open(Path(cfgmod.STATE_DIR) / "member_audit.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), "email": p["email"], "brain": brain,
                                    "path": str(t.relative_to(goc)), "bytes": len(data)},
                                   ensure_ascii=False) + "\n")
        except Exception:
            pass
        return {"ok": True, "size": len(data)}

    @r.get("/m/search")
    async def tim(request: Request, brain: str, q: str):
        p, e = _thanh_vien(request)
        if e:
            return e
        goc, _ = _goc(p, brain)
        if not goc:
            return _loi("Không có quyền với brain này", 403)
        k = (q or "").strip().lower()
        if len(k) < 2:
            return {"ok": True, "hits": []}
        hits = []
        for dp, dn, fn in os.walk(goc):
            rel_d = Path(dp).relative_to(goc).parts
            dn[:] = [d for d in dn if not _an(rel_d + (d,)) and not os.path.islink(os.path.join(dp, d))]
            for f in fn:
                fp = Path(dp) / f
                if _an(rel_d + (f,)) or fp.suffix.lower() not in DUOI_TEXT or fp.is_symlink():
                    continue
                rel = "/".join(rel_d + (f,))
                if k in f.lower():
                    hits.append({"path": rel, "line": ""})
                else:
                    try:
                        if fp.stat().st_size > DOC_TOI_DA:
                            continue
                        for ln in fp.read_text(encoding="utf-8", errors="ignore").splitlines():
                            if k in ln.lower():
                                hits.append({"path": rel, "line": ln.strip()[:200]})
                                break
                    except OSError:
                        pass
                if len(hits) >= 50:
                    return {"ok": True, "hits": hits}
        return {"ok": True, "hits": hits}

    return r


def register(app, deps: MemberDeps):
    global _DEPS
    _DEPS = deps
    router = _make_router()
    app.include_router(router)
    return router
