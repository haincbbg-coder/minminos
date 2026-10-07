"""goi_chia_se.py - KÝ, SOI và LÀM AN TOÀN gói chia sẻ giữa các máy chủ MinMin (26.10.92).

Ba việc, theo đúng thứ tự một gói đi từ máy này sang máy khác:

1. KÝ (bên gửi, lúc người nhận bấm tải): thêm file `minmin-chu-ky.json` vào gói. Chữ ký phủ
   lên DANH SÁCH (đường dẫn, sha256) của mọi file còn lại, kể cả manifest, nên đổi một byte
   ở bất kỳ đâu là chữ ký hỏng. File chữ ký nằm NGOÀI agents/ workflows/ skills/, nên MinMin
   bản cũ (26.10.73) nhập gói đã ký vẫn được: share_bundle bỏ qua im lặng mọi file lạ ở gốc.

2. SOI (bên nhận, trước khi cài): mở gói, liệt kê từng mục kèm mô tả, đánh dấu mục đã có sẵn
   (sẽ bỏ qua nếu không ghi đè), và nêu CẢNH BÁO thật chứ không phải chung chung: skill nào
   kèm file chạy được, workflow nào sẽ bị tắt, agent nào sẽ hạ quyền. Kết quả soi có sha256
   của gói; bước cài chỉ nhận lại đúng sha256 đó (cùng ý với pack_install.soi/cai), nên thứ
   người dùng đã đọc trên màn hình chính là thứ được cài.

3. LÀM AN TOÀN (bên nhận, lúc cài), chủ repo chốt 2026-10-07:
   - Agent và workflow nhập từ người khác mang `muc_quyen: suggest`: chạy trong workflow thì
     chỉ đọc (kể cả đọc MCP) và đề xuất, hub chặn mọi hành động ra ngoài. Người nhận tự bật lại
     toàn quyền khi đã tin, bằng nút "Tin tưởng" (xem `mo_khoa_muc`).
   - Workflow nhập về luôn `status: off`.
   - Mỗi mục ghi `nguon:` (tên miền, vân tay, ngày) để sau này biết mục này của ai.

Module chỉ thao tác bytes/zip và file trong thư mục được truyền vào; không import main.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import threading
import time
import zipfile
from pathlib import Path

import yaml

import danh_tinh
import fastyaml

try:
    from config import STATE_DIR
except Exception:
    STATE_DIR = Path(os.environ.get("JAVIS_STATE_DIR") or Path.home() / ".minmin")

FILE_CHU_KY = "minmin-chu-ky.json"
_ALLOWED_TOP = ("agents/", "workflows/", "skills/")
# Đuôi file CHẠY ĐƯỢC trong một skill: không phải lý do từ chối (skill tốt hay kèm script),
# nhưng người nhận phải được biết trước khi cài.
_DUOI_CHAY = (".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".ps1", ".bat", ".cmd",
              ".exe", ".rb", ".pl", ".php", ".jar", ".vbs", ".applescript", ".command")
_MAX_GOI = 25 * 1024 * 1024
_STAGING_TTL = 3600          # gói chờ xác nhận sống 1 giờ
_LOCK = threading.RLock()


# ─────────────────────────── KÝ ───────────────────────────

def _dau_van(z: zipfile.ZipFile) -> bytes:
    """Chuỗi bytes ĐÚNG MỘT CÁCH cho nội dung gói: JSON danh sách [đường dẫn, sha256] đã sắp xếp,
    bỏ qua chính file chữ ký và thư mục. Hai bên tính độc lập phải ra cùng một chuỗi."""
    ds = []
    for i in z.infolist():
        if i.is_dir():
            continue
        ten = i.filename.replace("\\", "/")
        if ten == FILE_CHU_KY:
            continue
        ds.append([ten, hashlib.sha256(z.read(i)).hexdigest()])
    ds.sort()
    return json.dumps(ds, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def ky_goi(data: bytes) -> bytes:
    """Trả gói mới có thêm `minmin-chu-ky.json`. Gói đã có chữ ký cũ thì chữ ký cũ bị thay."""
    src = zipfile.ZipFile(io.BytesIO(data))
    dau = _dau_van(src)
    khoa = danh_tinh.cong_khai()
    chu_ky = {"v": 1, "thuat_toan": "ed25519", "khoa": khoa, "van_tay": danh_tinh.van_tay(khoa),
              "ten": danh_tinh.ten(), "noi_dung_sha256": hashlib.sha256(dau).hexdigest(),
              "chu_ky": danh_tinh.ky(dau), "ky_luc": int(time.time())}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for i in src.infolist():
            if i.is_dir() or i.filename.replace("\\", "/") == FILE_CHU_KY:
                continue
            z.writestr(i.filename, src.read(i))
        z.writestr(FILE_CHU_KY, json.dumps(chu_ky, ensure_ascii=False, indent=1))
    return out.getvalue()


def doc_chu_ky(data: bytes) -> dict:
    """Kiểm chữ ký TRONG gói (chưa hỏi tên miền). Trả {trang_thai, khoa, van_tay, ten}:
      khong_ky   gói không có chữ ký (MinMin cũ, hoặc file .zip tự làm)
      hong       có file chữ ký nhưng không đọc được / sai định dạng
      sai        chữ ký KHÔNG khớp nội dung: gói đã bị sửa sau khi ký
      hop_le     chữ ký đúng với khoá kèm theo
    """
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return {"trang_thai": "hong"}
    if FILE_CHU_KY not in z.namelist():
        return {"trang_thai": "khong_ky"}
    try:
        ck = json.loads(z.read(FILE_CHU_KY)[:64 * 1024].decode("utf-8"))
        khoa, sig = str(ck["khoa"]), str(ck["chu_ky"])
    except Exception:
        return {"trang_thai": "hong"}
    ra = {"khoa": khoa, "van_tay": danh_tinh.van_tay(khoa), "ten": " ".join(str(ck.get("ten") or "").split())[:60]}
    ok = danh_tinh.xac_minh(khoa, _dau_van(z), sig)
    return dict(ra, trang_thai="hop_le" if ok else "sai")


# ─────────────────────────── SOI ───────────────────────────

def _parse(text: str):
    if (text or "").startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = fastyaml.safe_load(parts[1]) or {}
            except Exception:
                meta = {}
            return (meta if isinstance(meta, dict) else {}), parts[2]
    return {}, (text or "")


def _cat(s, n=200) -> str:
    return " ".join(str(s or "").split())[:n]


def soi_goi(data: bytes, *, agents_dir=None, workflows_dir=None, skills_root=None) -> dict:
    """Liệt kê nội dung gói cho màn xem trước. Không ghi gì ra đĩa.

    items: [{type, slug, name, mo_ta, da_co, so_file, script: [..]}]
    canh_bao: [chuỗi] - những điều người nhận PHẢI biết trước khi bấm cài.
    """
    if not data or len(data) > _MAX_GOI:
        return {"ok": False, "error": "Gói rỗng hoặc quá lớn (>25MB)"}
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return {"ok": False, "error": "File tải về không phải gói .zip hợp lệ"}
    items: dict = {}
    for i in z.infolist():
        if i.is_dir():
            continue
        arc = i.filename.replace("\\", "/")
        if arc.startswith("/") or ".." in arc.split("/") or ":" in arc:
            continue
        top = next((t for t in _ALLOWED_TOP if arc.startswith(t)), None)
        if not top:
            continue
        rel = arc[len(top):]
        if top in ("agents/", "workflows/"):
            if "/" in rel or not rel.endswith(".md"):
                continue
            typ, slug = top[:-2], rel[:-3]
        else:
            slug = rel.split("/")[0]
            typ = "skill"
            if not slug or "/" not in rel:
                continue
        key = (typ, slug)
        it = items.setdefault(key, {"type": typ, "slug": slug, "name": slug, "mo_ta": "",
                                    "so_file": 0, "script": []})
        it["so_file"] += 1
        if typ == "skill" and arc.lower().endswith(_DUOI_CHAY):
            it["script"].append(rel.split("/", 1)[1][:120])
        md = (typ != "skill") or rel == f"{slug}/SKILL.md"
        if md and i.file_size <= 512 * 1024:
            meta, _ = _parse(z.read(i).decode("utf-8", "replace"))
            it["name"] = _cat(meta.get("name") or slug, 80)
            it["mo_ta"] = _cat(meta.get("description") or meta.get("role") or "", 200)
            if typ == "workflow":
                it["so_buoc"] = len([s for s in (meta.get("steps") or []) if isinstance(s, dict)])
    goc = ({"agent": Path(agents_dir), "workflow": Path(workflows_dir), "skill": Path(skills_root)}
           if agents_dir is not None else None)   # None = trang giới thiệu công khai, không so máy nào
    canh_bao = []
    for (typ, slug), it in items.items():
        it["da_co"] = bool(goc) and (goc[typ] / (slug if typ == "skill" else f"{slug}.md")).exists()
        if it["script"]:
            canh_bao.append(f"Skill \"{it['name']}\" kèm {len(it['script'])} file chạy được "
                            f"({', '.join(it['script'][:3])}{'...' if len(it['script']) > 3 else ''}). "
                            "Chúng chỉ chạy khi trợ lý có quyền chạy lệnh.")
    if any(t == "agent" for t, _ in items):
        canh_bao.append("Agent nhập về ở chế độ AN TOÀN: chỉ đọc và đề xuất, không tự gửi tin, "
                        "lên đơn hay chạy quảng cáo. Bấm \"Tin tưởng\" khi bạn muốn mở toàn quyền.")
    if any(t == "workflow" for t, _ in items):
        canh_bao.append("Workflow nhập về ở trạng thái TẮT và cũng chạy ở chế độ an toàn.")
    ds = sorted(items.values(), key=lambda x: ({"workflow": 0, "agent": 1, "skill": 2}[x["type"]], x["slug"]))
    return {"ok": bool(ds), "error": "" if ds else "Gói không có agent, skill hay workflow nào",
            "items": ds, "canh_bao": canh_bao, "sha256": hashlib.sha256(data).hexdigest(),
            "kich_thuoc": len(data)}


# ─────────────────────────── LÀM AN TOÀN ───────────────────────────

def _ghi_fm(text: str, sua: dict) -> str:
    """Đặt các khoá trong `sua` vào frontmatter (giữ nguyên thân). File không có frontmatter thì
    tạo mới. Dùng yaml.safe_dump như _write_md của main để Studio đọc lại y như file tự tạo."""
    meta, body = _parse(text)
    meta = dict(meta)
    meta.update(sua)
    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm}\n---\n{body if body.startswith(chr(10)) else chr(10) + body}"


def nhan_nguon(host: str, van_tay: str, ngay: str) -> str:
    s = host or "không rõ"
    if van_tay:
        s += f" · {van_tay}"
    return f"{s} · {ngay}"


def lam_an_toan(data: bytes, *, nguon: str, chon=None) -> bytes:
    """Gói mới đã: lọc theo `chon` (tập 'type:slug', None = tất cả), hạ quyền agent/workflow về
    suggest, tắt workflow, ghi `nguon`. Skill giữ NGUYÊN từng byte (nguồn gốc của skill ghi ở sổ
    nhap_nguon của máy nhận, vì sửa SKILL.md là sửa chính tri thức người ta viết)."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for i in src.infolist():
            if i.is_dir():
                continue
            arc = i.filename.replace("\\", "/")
            if arc in (FILE_CHU_KY,):
                continue
            blob = src.read(i)
            if arc == "javis-bundle.json":
                z.writestr(arc, blob)
                continue
            top = next((t for t in _ALLOWED_TOP if arc.startswith(t)), None)
            if not top:
                continue
            rel = arc[len(top):]
            if top == "skills/":
                key = f"skill:{rel.split('/')[0]}"
            else:
                key = f"{top[:-2]}:{rel[:-3] if rel.endswith('.md') else rel}"
            if chon is not None and key not in chon:
                continue
            if top in ("agents/", "workflows/") and rel.endswith(".md") and "/" not in rel:
                sua = {"muc_quyen": "suggest", "nguon": nguon}
                if top == "workflows/":
                    sua["status"] = "off"
                blob = _ghi_fm(blob.decode("utf-8", "replace"), sua).encode("utf-8")
            z.writestr(arc, blob)
    return out.getvalue()


# ─────────────────────────── KHO CHỜ XÁC NHẬN ───────────────────────────

def _staging() -> Path:
    return Path(STATE_DIR) / "share-staging"


def _don_cu() -> None:
    now = time.time()
    d = _staging()
    if not d.is_dir():
        return
    for f in d.iterdir():
        try:
            if now - f.stat().st_mtime > _STAGING_TTL:
                f.unlink()
        except OSError:
            pass


def cat_cho(data: bytes, thong_tin: dict) -> str:
    """Cất gói vào kho chờ, trả sha256. `thong_tin` (nguồn, chữ ký đã đối chiếu) đi kèm để bước
    cài KHÔNG phải tin lại bất cứ gì client gửi lên ngoài cái sha256."""
    sha = hashlib.sha256(data).hexdigest()
    with _LOCK:
        _don_cu()
        d = _staging()
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{sha}.zip").write_bytes(data)
        (d / f"{sha}.json").write_text(json.dumps(thong_tin, ensure_ascii=False), encoding="utf-8")
    return sha


def lay_cho(sha: str):
    """(bytes, thong_tin) của gói đang chờ, hoặc (None, None) khi hết hạn / sha lạ."""
    if not re.fullmatch(r"[0-9a-f]{64}", str(sha or "")):
        return None, None
    with _LOCK:
        _don_cu()
        p = _staging() / f"{sha}.zip"
        if not p.is_file():
            return None, None
        data = p.read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            return None, None
        try:
            tt = json.loads((_staging() / f"{sha}.json").read_text(encoding="utf-8"))
        except Exception:
            tt = {}
        return data, tt


def bo_cho(sha: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", str(sha or "")):
        return
    with _LOCK:
        for duoi in (".zip", ".json"):
            try:
                (_staging() / f"{sha}{duoi}").unlink()
            except OSError:
                pass


# ─────────────────────────── SỔ NGUỒN GỐC ───────────────────────────

def _so() -> Path:
    return Path(STATE_DIR) / "nhap-nguon.json"


def _doc_so() -> dict:
    try:
        d = json.loads(_so().read_text(encoding="utf-8"))
    except Exception:
        return {}
    return d if isinstance(d, dict) else {}


def ghi_so(brain_root: str, keys, thong_tin: dict, phien_ban: dict = None, hash_cai: dict = None) -> None:
    """Ghi nguồn gốc các mục vừa nhập: {brain_root: {'type:slug': {...}}}.

    Theo dõi bản mới (26.10.102): `td` (kênh theo dõi của người gửi), `phien_ban` (dấu nội dung
    người gửi lúc cài) và `hash_cai` (dấu file trên đĩa ngay sau khi cài, để biết về sau người
    nhận có tự sửa mục đó không). Cài lại bản mới thì `tin_tuong` về False: nội dung mới phải được
    tin lại từ đầu."""
    phien_ban, hash_cai = phien_ban or {}, hash_cai or {}
    with _LOCK:
        d = _doc_so()
        b = d.setdefault(str(brain_root), {})
        for k in keys:
            k = str(k)
            b[k] = {"host": thong_tin.get("host", ""), "van_tay": thong_tin.get("van_tay", ""),
                    "ten": thong_tin.get("ten", ""), "xac_minh": thong_tin.get("xac_minh", ""),
                    "luc": int(time.time()), "tin_tuong": False,
                    "td": thong_tin.get("td", "") if re.fullmatch(r"[A-Za-z0-9_-]{16,80}", str(thong_tin.get("td") or "")) else "",
                    "phien_ban": phien_ban.get(k, ""), "hash_cai": hash_cai.get(k, "")}
        p = _so()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, p)


def doc_so(brain_root: str) -> dict:
    v = _doc_so().get(str(brain_root))
    return v if isinstance(v, dict) else {}


def mo_khoa_muc(brain_root: str, typ: str, slug: str, *, agents_dir, workflows_dir) -> bool:
    """Người nhận bấm "Tin tưởng": bỏ `muc_quyen: suggest` của agent/workflow đã nhập để nó chạy
    lại bình thường (toàn quyền như mọi agent tự tạo). Chỉ làm với mục CÓ trong sổ nguồn gốc,
    tức đúng là thứ đã nhập từ người khác."""
    key = f"{typ}:{slug}"
    with _LOCK:
        d = _doc_so()
        b = d.get(str(brain_root)) or {}
        if key not in b:
            return False
        if typ in ("agent", "workflow"):
            p = Path(agents_dir if typ == "agent" else workflows_dir) / f"{slug}.md"
            if p.is_file():
                text = p.read_text(encoding="utf-8")
                meta, body = _parse(text)
                if "muc_quyen" in meta:
                    meta.pop("muc_quyen", None)
                    fm = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
                    tmp = p.with_suffix(".md.tmp")
                    tmp.write_text(f"---\n{fm}\n---\n{body}", encoding="utf-8")
                    os.replace(tmp, p)
        b[key]["tin_tuong"] = True
        # Gỡ dòng muc_quyen là sửa file, nhưng không phải "người nhận tự sửa nội dung": dời mốc
        # hash_cai theo để lần kiểm tra bản mới sau không báo nhầm "bạn đã sửa mục này".
        if typ in ("agent", "workflow") and b[key].get("hash_cai"):
            b[key]["hash_cai"] = bam_tren_dia(typ, slug, agents_dir=agents_dir, workflows_dir=workflows_dir,
                                              skills_root=None)
        tmp = _so().with_suffix(".json.tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, _so())
        return True


# ─────────────────────────── THEO DÕI BẢN MỚI (26.10.102) ───────────────────────────
#
# Người gửi: lúc tải gói, máy gửi nhét `minmin-theo-doi.json` {td} vào gói TRƯỚC khi ký. `td` là
# một token bền (365 ngày) gắn với chính link chia sẻ: link hết hạn hay hết lượt thì người ĐÃ
# nhận vẫn hỏi được bản mới, còn thu hồi link là cắt luôn kênh theo dõi.
# Người nhận: ghi td + dấu nội dung từng mục vào sổ nguồn gốc; về sau hỏi /bs/td/<td> để so.

FILE_THEO_DOI = "minmin-theo-doi.json"


def _key_cua(arc: str):
    """'skills/bao-gia/x.md' -> 'skill:bao-gia'; 'agents/a.md' -> 'agent:a'; ngoài ba nhóm -> None."""
    if arc.startswith("skills/"):
        rel = arc[len("skills/"):]
        return f"skill:{rel.split('/')[0]}" if "/" in rel else None
    for top, typ in (("agents/", "agent"), ("workflows/", "workflow")):
        if arc.startswith(top):
            rel = arc[len(top):]
            return f"{typ}:{rel[:-3]}" if rel.endswith(".md") and "/" not in rel else None
    return None


def _dau(ds) -> str:
    ds = sorted(ds)
    return hashlib.sha256(json.dumps(ds, separators=(",", ":")).encode("utf-8")).hexdigest()[:32]


def bam_muc(data: bytes) -> dict:
    """{'type:slug': dấu nội dung} cho từng mục trong gói (bỏ file chữ ký, theo dõi, manifest)."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return {}
    nhom: dict = {}
    for i in z.infolist():
        arc = i.filename.replace("\\", "/")
        if i.is_dir() or ".." in arc.split("/"):
            continue
        k = _key_cua(arc)
        if k:
            nhom.setdefault(k, []).append([arc, hashlib.sha256(z.read(i)).hexdigest()])
    return {k: _dau(v) for k, v in nhom.items()}


def bam_tren_dia(typ: str, slug: str, *, agents_dir, workflows_dir, skills_root) -> str:
    """Dấu các file của một mục ĐANG nằm trên đĩa (cùng cách tính với bam_muc). '' nếu không có."""
    ds = []
    if typ in ("agent", "workflow"):
        p = Path(agents_dir if typ == "agent" else workflows_dir) / f"{slug}.md"
        if p.is_file():
            ds.append([f"{typ}s/{slug}.md", hashlib.sha256(p.read_bytes()).hexdigest()])
    elif skills_root is not None:
        goc = Path(skills_root) / slug
        if goc.is_dir():
            for f in sorted(goc.rglob("*")):
                if f.is_file() and not f.is_symlink():
                    ds.append([f"skills/{slug}/{f.relative_to(goc).as_posix()}", hashlib.sha256(f.read_bytes()).hexdigest()])
    return _dau(ds) if ds else ""


def gan_theo_doi(data: bytes, td: str) -> bytes:
    """Gói mới có `minmin-theo-doi.json` (thay bản cũ nếu có). Gọi TRƯỚC ky_goi để chữ ký phủ nó."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for i in src.infolist():
            if i.is_dir() or i.filename in (FILE_THEO_DOI, FILE_CHU_KY):
                continue
            z.writestr(i.filename, src.read(i))
        z.writestr(FILE_THEO_DOI, json.dumps({"v": 1, "td": td}))
    return out.getvalue()


def doc_theo_doi(data: bytes) -> str:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        td = str(json.loads(z.read(FILE_THEO_DOI)[:4096]).get("td") or "")
    except Exception:
        return ""
    return td if re.fullmatch(r"[A-Za-z0-9_-]{16,80}", td) else ""


# Khoá frontmatter do CHÍNH máy nhận ghi khi cài (muc_quyen, nguon, status) bị bỏ qua khi so.
def _dong_so_sanh(text: str) -> list:
    """Dòng để so khác biệt. File có frontmatter thì so theo NGHĨA chứ không theo chữ: máy nhận
    ghi lại frontmatter bằng yaml.safe_dump (đổi `skills: [a]` thành dạng danh sách xuống dòng),
    nên so chữ là lần cập nhật nào cũng báo "đã sửa" dù người gửi không đụng tới."""
    meta, body = _parse(text)
    if text.startswith("---") and meta:
        meta = {k: v for k, v in meta.items() if k not in ("muc_quyen", "nguon", "status")}
        dau = json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=0, default=str).splitlines()
        return dau + body.strip("\n").splitlines()
    return text.splitlines()


def khac_biet(data: bytes, key: str, *, agents_dir, workflows_dir, skills_root) -> list:
    """[{file, trang_thai: moi|sua|xoa, them, bot}] giữa bản MỚI trong gói và bản trên đĩa của
    một mục. Chỉ đếm dòng, không gửi nội dung đầy đủ ra giao diện (màn xem trước đã có tóm tắt)."""
    import difflib
    typ, _, slug = key.partition(":")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return []
    moi = {}
    for i in z.infolist():
        arc = i.filename.replace("\\", "/")
        if not i.is_dir() and _key_cua(arc) == key and i.file_size <= 2 * 1024 * 1024:
            moi[arc] = z.read(i)
    cu = {}
    if typ in ("agent", "workflow"):
        p = Path(agents_dir if typ == "agent" else workflows_dir) / f"{slug}.md"
        if p.is_file():
            cu[f"{typ}s/{slug}.md"] = p.read_bytes()
    else:
        goc = Path(skills_root) / slug
        if goc.is_dir():
            for f in goc.rglob("*"):
                if f.is_file() and not f.is_symlink() and f.stat().st_size <= 2 * 1024 * 1024:
                    cu[f"skills/{slug}/{f.relative_to(goc).as_posix()}"] = f.read_bytes()
    ra = []
    for arc in sorted(set(moi) | set(cu)):
        a, b = cu.get(arc), moi.get(arc)
        if a == b:
            continue
        la = _dong_so_sanh(a.decode("utf-8", "replace")) if a is not None else []
        lb = _dong_so_sanh(b.decode("utf-8", "replace")) if b is not None else []
        if a is not None and b is not None and la == lb:
            continue   # chỉ khác ở mấy dòng máy nhận tự ghi
        them = bot = 0
        for d in difflib.ndiff(la, lb):
            if d.startswith("+ "):
                them += 1
            elif d.startswith("- "):
                bot += 1
        ra.append({"file": arc.split("/", 1)[1], "trang_thai": "moi" if a is None else "xoa" if b is None else "sua",
                   "them": them, "bot": bot})
    return ra[:80]


def don_file_thua(data: bytes, key: str, *, skills_root) -> int:
    """Cập nhật một SKILL: xoá file trên đĩa mà bản mới không còn (import_bundle chỉ ghi đè, không
    xoá). Chỉ trong đúng thư mục skill đó, không theo symlink. Trả số file đã xoá."""
    typ, _, slug = key.partition(":")
    if typ != "skill" or skills_root is None or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", slug):
        return 0
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return 0
    giu = {i.filename.replace("\\", "/")[len(f"skills/{slug}/"):] for i in z.infolist()
           if i.filename.replace("\\", "/").startswith(f"skills/{slug}/")}
    goc = (Path(skills_root) / slug).resolve()
    n = 0
    if not goc.is_dir():
        return 0
    for f in list(goc.rglob("*")):
        if f.is_file() and not f.is_symlink() and f.resolve().is_relative_to(goc):
            if f.relative_to(goc).as_posix() not in giu:
                try:
                    f.unlink()
                    n += 1
                except OSError:
                    pass
    return n
