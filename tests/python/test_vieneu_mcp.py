"""Cầu nối VieNeu (server/vieneu_mcp.py) và plugin vieneu-doc. Không mạng.

    python3 tests/python/test_vieneu_mcp.py

Phủ: danh sách tool, thiếu khoá, lọc giọng, số dư, header Bearer, chia đoạn (đoạn cuối < 50 ký tự dồn lại),
ghép mp3 và wav, trần ký tự, tốc độ ngoài khoảng, lỗi 401/403/429 ra câu dễ hiểu, khoá không lộ ra kết quả,
plugin lưu file vào attachments/ và đặt tên không dấu.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import io
import sys
import tempfile
import wave
from pathlib import Path

from _gia_http import GiaHttp, KiemTra
import vieneu_mcp as v

check = KiemTra()
KHOA = "vn_sk_KHOA-BI-MAT-ABCDEF123456"


def chay(c):
    return asyncio.run(c)


def spec():
    return {"key": "conn-vieneu-1", "secrets": {"api_key": KHOA}}


def wav_byte(n=100, rate=24000):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x01\x00" * n)
    return b.getvalue()


# ---- 1. tool ----
ten = [t["name"] for t in chay(v.list_tools({}))]
check("đủ 2 tool", ten == ["vieneu_danh_sach_giong", "vieneu_so_du"], ten)
ra = chay(v.call("vieneu_so_du", {}, {"secrets": {}}))
check("thiếu api_key -> báo rõ", ra.startswith("ERROR") and "api_key" in ra, ra)
check("tool lạ -> báo lỗi", chay(v.call("khong_co", {}, spec())).startswith("ERROR"))

# ---- 2. giọng ----
DS = {"voices": [
    {"id": "Ngọc Lan", "name": "Ngọc Lan", "gender": "female", "region": "south", "kind": "catalog",
     "description": "Giọng nữ, giọng trầm dịu dàng"},
    {"id": "Nhật Phong", "name": "Nhật Phong", "gender": "male", "region": "north", "kind": "catalog",
     "description": "Giọng nam kể chuyện"},
    {"id": "Bích Ngọc", "name": "Bích Ngọc", "gender": "female", "region": "north", "kind": "catalog",
     "description": "Giọng nữ rõ ràng"}]}
gia = GiaHttp().lap()
gia.tra("/voices", DS)
ra = chay(v.call("vieneu_danh_sach_giong", {}, spec()))
g = gia.goi[-1]
check("giọng: đúng URL và engine v4", g["url"] == "https://api.vieneu.io/api/v1/voices" and g["params"].get("engine") == "v4", g)
check("giọng: header Bearer", g["headers"].get("Authorization") == f"Bearer {KHOA}")
check("giọng: trả cả ba", "Ngọc Lan" in ra and "Nhật Phong" in ra and '"tong_giong": 3' in ra, ra)
ra = chay(v.call("vieneu_danh_sach_giong", {"gioi_tinh": "nu", "mien": "bac"}, spec()))
check("giọng: lọc nữ miền Bắc -> Bích Ngọc", "Bích Ngọc" in ra and "Ngọc Lan" not in ra and "Nhật" not in ra, ra)
ra = chay(v.call("vieneu_danh_sach_giong", {"tu_khoa": "kể chuyện"}, spec()))
check("giọng: tìm từ khoá trong mô tả", "Nhật Phong" in ra and "Bích" not in ra, ra)
ra = chay(v.call("vieneu_danh_sach_giong", {"limit": 1}, spec()))
check("giọng: limit", '"hien": 1' in ra, ra)

# ---- 3. số dư ----
gia.tra("/usage", {"tokensRemaining": 123456})
ra = chay(v.call("vieneu_so_du", {}, spec()))
check("số dư: đúng URL và trả dữ liệu", gia.goi[-1]["url"].endswith("/api/v1/usage") and "123456" in ra, ra)
gia = GiaHttp().lap()
gia.tra("/usage", {"error": {"message": "key sai " + KHOA}}, code=401)
ra = chay(v.call("vieneu_so_du", {}, spec()))
check("số dư: 401 không lộ khoá", ra.startswith("ERROR") and KHOA not in ra, ra)

# ---- 4. chia đoạn ----
check("văn bản ngắn -> 1 đoạn", v.chia_doan("Xin chào các bạn, đây là VieNeu đang đọc thử một câu ngắn.") != [])
cau = "Đây là một câu khá dài để thử chia đoạn cho giọng đọc. " * 60
doan = v.chia_doan(cau, toi_da=500)
check("chia: mỗi đoạn <= 500", all(len(d) <= 500 for d in doan) and len(doan) > 3, [len(d) for d in doan])
check("chia: không mất chữ", " ".join(doan).replace(" ", "") == cau.strip().replace(" ", ""))
cuoi = "A" * 480 + ". Hết."          # đoạn cuối chỉ 6 ký tự
d2 = v.chia_doan(cuoi, toi_da=480 + 1)
check("chia: đoạn cuối < 50 dồn vào đoạn trước", len(d2) == 1 or all(len(d) >= 50 for d in d2), [len(d) for d in d2])
check("chia: rỗng", v.chia_doan("   ") == [])

# ---- 5. đọc ----
VAN = "Xin chào, đây là bản đọc thử của MinMin bằng giọng VieNeu, dài hơn năm mươi ký tự."
gia = GiaHttp().lap()
gia.tra("/audio/speech", b"ID3FAKEMP3")
ok, b, so_doan, so_kt = chay(v.doc_thanh_tieng({"api_key": KHOA}, VAN, voice="Ngọc Lan", speed=1.2))
g = gia.goi[-1]
check("đọc: ok, trả byte", ok and b == b"ID3FAKEMP3" and so_doan == 1 and so_kt == len(VAN), (ok, b))
check("đọc: đúng URL, POST, Bearer", g["url"].endswith("/api/v1/audio/speech") and g["method"] == "POST"
      and g["headers"].get("Authorization") == f"Bearer {KHOA}", g)
check("đọc: body voice, speed, mp3, model", g["json"]["voice"] == "Ngọc Lan" and g["json"]["speed"] == 1.2
      and g["json"]["response_format"] == "mp3" and g["json"]["model"] == "vieneu-v4", g["json"])
ok, ra, _, _ = chay(v.doc_thanh_tieng({"api_key": KHOA}, "ngắn quá"))
check("đọc: dưới 50 ký tự -> nói rõ, chưa gọi mạng", (not ok) and "50" in ra and len(gia.goi) == 1, ra)
ok, ra, _, _ = chay(v.doc_thanh_tieng({"api_key": KHOA}, "x" * 20001))
check("đọc: quá trần -> từ chối", (not ok) and "trần" in ra and len(gia.goi) == 1, ra)
ok, ra, _, _ = chay(v.doc_thanh_tieng({"api_key": KHOA}, VAN, speed=5))
check("đọc: tốc độ ngoài khoảng", (not ok) and "0.5" in ra and len(gia.goi) == 1, ra)
ok, ra, _, _ = chay(v.doc_thanh_tieng({"api_key": KHOA}, VAN, fmt="flac"))
check("đọc: định dạng lạ", (not ok) and "mp3" in ra and len(gia.goi) == 1, ra)
ok, ra, _, _ = chay(v.doc_thanh_tieng({}, VAN))
check("đọc: thiếu khoá", (not ok) and "api_key" in ra)

for code, tu in ((401, "Khoá API sai"), (403, "Gói token"), (429, "giới hạn")):
    g2 = GiaHttp().lap()
    g2.tra("/audio/speech", {"error": {"message": "x " + KHOA}}, code=code)
    ok, ra, _, _ = chay(v.doc_thanh_tieng({"api_key": KHOA}, VAN))
    check(f"đọc: {code} -> câu dễ hiểu, không lộ khoá", (not ok) and tu in ra and KHOA not in ra, ra)

# nhiều đoạn: mp3 nối byte, wav ghép đúng tiêu đề
DAI = ("Đây là một câu khá dài để thử chia đoạn cho giọng đọc của VieNeu. " * 40).strip()
g3 = GiaHttp().lap()
g3.tra("/audio/speech", b"MP3A")
ok, b, so_doan, _ = chay(v.doc_thanh_tieng({"api_key": KHOA}, DAI))
check("nhiều đoạn mp3: nối byte đủ", ok and so_doan == len(g3.goi) and so_doan >= 2 and b == b"MP3A" * so_doan, (so_doan, len(g3.goi)))
g4 = GiaHttp().lap()
g4.tra("/audio/speech", wav_byte(100))
ok, b, so_doan, _ = chay(v.doc_thanh_tieng({"api_key": KHOA}, DAI, fmt="wav"))
with wave.open(io.BytesIO(b), "rb") as r:
    khung = r.getnframes()
check("nhiều đoạn wav: ghép thành MỘT file hợp lệ", ok and khung == 100 * so_doan, (khung, so_doan))
g5 = GiaHttp().lap()
g5.tra("/audio/speech", b"")
ok, ra, _, _ = chay(v.doc_thanh_tieng({"api_key": KHOA}, VAN))
check("file rỗng -> báo lỗi", (not ok) and "rỗng" in ra, ra)

# ---- 6. plugin ----
sys.path.insert(0, str(ROOT / "system" / "plugins" / "vieneu-doc"))
import importlib.util
sp = importlib.util.spec_from_file_location("vieneu_doc_plugin", ROOT / "system" / "plugins" / "vieneu-doc" / "plugin.py")
pl = importlib.util.module_from_spec(sp)
sp.loader.exec_module(pl)


class _Ctx:
    def __init__(self):
        self.tools = {}

    def register_tool(self, name, **kw):
        self.tools[name] = kw


class _CC:
    def __init__(self, vr):
        self.vault_root = vr


ctx = _Ctx()
pl.register(ctx)
tl = ctx.tools["javis_vieneu_speak"]
check("plugin: min_mode safe (trừ token thật)", tl["min_mode"] == "safe")
check("plugin: yêu cầu text", tl["schema"]["required"] == ["text"])

kn = [{"id": "c1", "connector_id": "vieneu", "enabled": True, "label": "VieNeu chính", "is_default": True},
      {"id": "c2", "connector_id": "vieneu", "enabled": True, "label": "VieNeu phụ"},
      {"id": "c3", "connector_id": "sepay", "enabled": True, "label": "SePay"}]
pl.mcp_store.list_connections = lambda: kn
pl.mcp_store.connection_secrets = lambda cid: {"api_key": KHOA if cid == "c1" else "vn_sk_KHAC-ABCDEF123456"}
check("plugin: chọn kết nối mặc định", pl._ket_noi_vieneu()["id"] == "c1")
check("plugin: chọn theo nhãn", pl._ket_noi_vieneu("phụ")["id"] == "c2")
check("plugin: bỏ kết nối tắt", pl._ket_noi_vieneu("sepay") is None)
check("plugin: check_fn trống khi đã nối", tl["check_fn"]() is None)
check("plugin: tên file không dấu", pl._bo_dau_slug("Đọc lời bình Xuân Hè!") == "doc-loi-binh-xuan-he")

vr = tempfile.mkdtemp(prefix="javis-vieneu-")
g6 = GiaHttp().lap()
g6.tra("/audio/speech", b"ID3AUDIO")
ra = chay(tl["handler"]({"text": VAN, "voice": "Ngọc Lan", "ten_file": "Lời bình Tết"}, _CC(vr)))
tep = list((Path(vr) / "attachments").glob("vieneu-*.mp3"))
check("plugin: lưu file vào attachments/", len(tep) == 1 and tep[0].read_bytes() == b"ID3AUDIO", tep)
check("plugin: tên file chứa slug không dấu", tep and "loi-binh-tet" in tep[0].name, tep)
check("plugin: kết quả có đường dẫn tương đối và link", "attachments/" in ra and "](attachments/" in ra, ra)
check("plugin: dùng đúng khoá của kết nối mặc định", g6.goi[-1]["headers"]["Authorization"] == f"Bearer {KHOA}")
check("plugin: không lộ khoá trong kết quả", KHOA not in ra)
ra = chay(tl["handler"]({"text": ""}, _CC(vr)))
check("plugin: thiếu text", ra.startswith("ERROR"))
ra = chay(tl["handler"]({"text": VAN}, _CC("")))
check("plugin: không có brain", ra.startswith("ERROR") and "brain" in ra)
kn.clear()
check("plugin: chưa nối VieNeu -> check_fn chỉ đường", "Chợ MinMin" in (tl["check_fn"]() or ""))

# ---- 7. catalog ----
import json
cat = json.loads((ROOT / "system" / "mcp-catalog.json").read_text(encoding="utf-8"))
vn = next(c for c in cat["connectors"] if c["id"] == "vieneu")
check("catalog: internal vieneu, apikey api_key", vn["transport"] == "internal" and vn["internal"] == "vieneu"
      and vn["auth"]["fields"][0]["key"] == "api_key")
check("catalog: validate dùng vieneu_so_du (cần khoá)", vn["validate"]["tool"] == "vieneu_so_du")
check("catalog: mặc định chỉ đọc", vn["default_perm"] == "readonly")
check("catalog: không có gạch dài", "—" not in json.dumps(vn, ensure_ascii=False))
import mcp_client
check("mcp_client: đăng ký vieneu", mcp_client._INTERNAL.get("vieneu") == "vieneu_mcp")
check("không có gạch dài trong module", "—" not in (SERVER / "vieneu_mcp.py").read_text(encoding="utf-8"))

check.ket_thuc()
