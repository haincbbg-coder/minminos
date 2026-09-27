"""Đọc câu Việt xen Anh: tách đoạn, mỗi đoạn một giọng hợp tiếng, cắt khoảng lặng chỗ nối.

    python tests/run.py tts_tron_tieng

Vì sao file này tồn tại (0.64.67): Edge đọc cả câu bằng một tiếng, nên giọng Việt đọc
"GitHub Actions" thành "huyết áp Action" và giọng đa ngôn ngữ đọc "merge vào main" thành
"mét vào mên". Module tts_tron_tieng tách đoạn rồi nối mp3. Những chỗ dễ vỡ được khoá ở đây:
  1. Nhận nhầm từ tiếng Việt không dấu ("anh", "to", "in", "so") thành tiếng Anh.
  2. Cắt mp3 làm hỏng luồng: khung Layer III mượn byte của khung trước (bit reservoir).
  3. Hỏng một đoạn thì /tts phải rơi về đọc nguyên câu, không im bặt.
Không chạm mạng: edge_tts bị thay bằng module giả.
"""
from _paths import ROOT, SERVER  # noqa: E402,F401
import asyncio
import os
import sys
import tempfile
import types

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="javis-tts-tron-"))

import tts_tron_tieng as T  # noqa: E402

_fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        _fails.append(name)


# ---- 1. Nhận ra từ tiếng Anh ----
for w in ("GitHub", "VPS", "API", "push", "build", "main", "log", "deploy", "workflow",
          "dashboard", "merge", "check", "test", "chat", "ok", "Javis"):
    check(f"'{w}' là tiếng Anh", T.la_tu_tieng_anh(w))
for w in ("anh", "em", "cho", "sang", "theo", "trong", "xin", "nhanh", "to", "in", "no", "so",
          "do", "pin", "mua", "Anh", "đã", "vào", "Lưu", "quy", "gia", "nghiêng"):
    check(f"'{w}' là tiếng Việt", not T.la_tu_tieng_anh(w))


def ghep(text):
    return "".join(d for _, d in T.tach_doan(text))


def nhan(text):
    return [(n, d.strip()) for n, d in T.tach_doan(text)]


C1 = "Pull request đã merge vào main, anh check lại dashboard giúp em nhé."
check("tách đoạn ghép lại ra NGUYÊN VĂN", ghep(C1) == C1)
check("tách đúng đoạn Việt / Anh", nhan(C1) == [
    ("en", "Pull request"), ("vi", "đã"), ("en", "merge"), ("vi", "vào"), ("en", "main,"),
    ("vi", "anh"), ("en", "check"), ("vi", "lại"), ("en", "dashboard"), ("vi", "giúp em nhé.")])
check("'anh' kẹp giữa hai từ tiếng Anh vẫn là tiếng Việt",
      ("vi", "anh") in nhan("merge vào main anh check"))
check("chuỗi từ nối tiếng Anh kẹp giữa theo tiếng Anh",
      nhan("Anh sign in to GitHub rồi bấm Lưu.") == [
          ("vi", "Anh"), ("en", "sign in to GitHub"), ("vi", "rồi bấm Lưu.")])
check("'The' đầu câu trước từ tiếng Anh theo tiếng Anh",
      nhan("The build passed on GitHub Actions.") == [("en", "The build passed on GitHub Actions.")])
check("'Do' đầu câu (do đó) vẫn là tiếng Việt", nhan("Do GitHub lỗi nên em chạy lại.")[0] == ("vi", "Do"))
check("câu thuần Việt không dấu vẫn một đoạn",
      nhan("Anh cứ nói to lên, em in hoá đơn rồi so sánh nhé.") == [
          ("vi", "Anh cứ nói to lên, em in hoá đơn rồi so sánh nhé.")])
check("chuỗi rỗng", T.tach_doan("") == [])
for s in ("Link https://github.com/x nhé", "Số 12.5 triệu, API trả 200", "  cách  đều  "):
    check(f"ghép lại nguyên văn: {s!r}", ghep(s) == s)

# ---- 2. Khi nào tách, giọng nào đọc ----
HM, NM = "vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"
EM, AN = "en-US-EmmaMultilingualNeural", "en-US-AndrewMultilingualNeural"
check("Hoài My + câu trộn: tách", T.nen_tach(HM, C1))
check("Emma + câu trộn: tách", T.nen_tach(EM, C1))
check("câu thuần Việt: không tách", not T.nen_tach(HM, "Vâng, anh cứ nói tiếp."))
check("Emma + câu thuần Anh: không tách (tự đọc chuẩn)", not T.nen_tach(EM, "The build passed."))
check("Hoài My + câu thuần Anh: tách (để giọng Anh đọc)", T.nen_tach(HM, "The build passed."))
check("giọng tiếng khác: không tách", not T.nen_tach("ja-JP-NanamiNeural", C1))
check("Hoài My: Việt Hoài My, Anh Emma", (T.giong_cho_doan(HM, "vi"), T.giong_cho_doan(HM, "en")) == (HM, EM))
check("Nam Minh: Việt Nam Minh, Anh Andrew", (T.giong_cho_doan(NM, "vi"), T.giong_cho_doan(NM, "en")) == (NM, AN))
# Emma đọc mẩu Việt ngắn ("đã" -> "Da") nên đoạn Việt luôn giao giọng Việt bản địa cùng giới.
check("Emma: đoạn Việt giao Hoài My", T.giong_cho_doan(EM, "vi") == HM and T.giong_cho_doan(EM, "en") == EM)
check("Andrew: đoạn Việt giao Nam Minh", T.giong_cho_doan(AN, "vi") == NM)


# ---- 3. Cắt mp3 (khung MPEG-2 Layer III mono 24 kHz 48 kbps như Edge trả: 144 byte, 24 ms) ----
def khung(muon=0, fill=0xAB):
    hdr = bytes([0xFF, 0xF3, 0x64, 0xC4])          # y hệt header Edge: fff364c4
    si = bytes([muon]) + bytes([0x55] * 8)          # main_data_begin + 8 byte side info khác 0
    return hdr + si + bytes([fill] * (144 - 4 - 9))


def luong(ds_muon):
    return b"".join(khung(m, fill=i % 250) for i, m in enumerate(ds_muon))


def cac(data):
    return T._cac_khung(data)


MUON = [0, 124, 255, 200, 100, 50, 0, 20, 20, 20]   # 10 khung = 240 ms
L = luong(MUON)
check("đọc được đủ 10 khung", cac(L) is not None and len(cac(L)) == 10)
check("đọc ra main_data_begin", [k[5] for k in cac(L)] == MUON)
check("không cắt phía nào: y nguyên", T.cat_mp3(L, None, None) == L)
cd = T.cat_mp3(L, None, 100)          # giữ các khung bắt đầu trước 100 ms: 0,24,48,72,96
check("cắt đuôi giữ đúng 5 khung", cd == L[:5 * 144])
# Cắt đầu ở mốc 60 ms + 20 = 80 ms -> khung 3 (72 ms), khung 3 mượn 200 byte = 2 khung kho.
cc = T.cat_mp3(L, 60, None)
kc = cac(cc)
check("cắt đầu: còn khung 1..9 (lùi 2 khung kho cho khung 3)", kc is not None and len(kc) == 9)
check("khung kho bị xoá side info (im lặng, mdb 0)",
      cc[4:13] == bytes(9) and cc[144 + 4:144 + 13] == bytes(9))
check("khung kho GIỮ nguyên byte dữ liệu cho khung sau mượn", cc[13:144] == L[144 + 13:2 * 144])
check("khung từ chỗ cắt trở đi nguyên vẹn", cc[2 * 144:] == L[3 * 144:])
check("khung đầu mượn quá kho có sẵn: không cắt đầu",
      T.cat_mp3(luong([0, 255, 0, 0]), 10, None) == luong([0, 255, 0, 0]))
check("không phải mp3: trả nguyên vẹn", T.cat_mp3(b"ID3abcdef" * 50, 60, 100) == b"ID3abcdef" * 50)
check("mp3 cụt khung cuối: trả nguyên vẹn", T.cat_mp3(L[:-10], 60, 100) == L[:-10])
check("đoạn kết dấu phẩy chừa đuôi dài hơn",
      T.moc_cat("main, ", (50, 300))[1] > T.moc_cat("main ", (50, 300))[1])


# ---- 4. doc_tron: song song, nối đúng thứ tự, chỉ cắt ở CHỖ NỐI ----
goi = []


async def tong_hop_gia(doan, giong):
    goi.append((doan, giong))
    await asyncio.sleep(0.01 if "merge" in doan else 0)   # đoạn giữa về muộn: thứ tự vẫn phải đúng
    return L, (60, 150)


out = asyncio.run(T.doc_tron("Em merge vào main.", HM, tong_hop_gia))
check("mỗi đoạn một lần gọi, đúng giọng", sorted(goi) == sorted([
    ("Em ", HM), ("merge ", EM), ("vào ", HM), ("main.", EM)]))
p_dau = T.cat_mp3(L, None, T.moc_cat("Em ", (60, 150))[1])
p_giua = T.cat_mp3(L, 60, T.moc_cat("merge ", (60, 150))[1])
p_cuoi = T.cat_mp3(L, 60, None)
check("đoạn đầu giữ đầu, đoạn cuối giữ đuôi, nối đúng thứ tự",
      out == p_dau + p_giua + T.cat_mp3(L, 60, T.moc_cat("vào ", (60, 150))[1]) + p_cuoi)


async def hong(doan, giong):
    if "main" in doan:
        raise RuntimeError("Edge chết")
    return L, (60, 150)


try:
    asyncio.run(T.doc_tron("Em merge vào main.", HM, hong))
    check("một đoạn hỏng thì ném lỗi", False)
except RuntimeError:
    check("một đoạn hỏng thì ném lỗi", True)


# ---- 5. Nối vào /tts: câu trộn đi đường tách, hỏng thì rơi về đọc nguyên câu ----
class _FakeCommunicate:
    goi = []
    chet = set()

    def __init__(self, text, voice, rate="+0%", boundary=None):
        self.text, self.voice, self.boundary = text, voice, boundary
        _FakeCommunicate.goi.append((text, voice, boundary))

    async def stream(self):
        if self.voice in _FakeCommunicate.chet:
            raise RuntimeError("Edge chết")
        yield {"type": "audio", "data": L}
        yield {"type": "WordBoundary", "offset": 600000, "duration": 900000, "text": "x"}


fake = types.ModuleType("edge_tts")
fake.Communicate = _FakeCommunicate
sys.modules["edge_tts"] = fake

import main  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app, base_url="http://127.0.0.1")
_cfg_goc = main.cfgmod.read_settings
main.cfgmod.read_settings = lambda: {"voice": {"tts_provider": "edge"}, "model": {}}
try:
    _FakeCommunicate.goi = []
    r = client.get("/tts", params={"text": "Em merge vào main.", "voice": HM})
    giong = {v for _, v, _ in _FakeCommunicate.goi}
    check("/tts câu trộn: 200 audio/mpeg", r.status_code == 200 and r.headers["content-type"] == "audio/mpeg")
    check("/tts câu trộn: gọi cả giọng Việt lẫn giọng Anh", giong == {HM, EM})
    check("/tts câu trộn: xin mốc WordBoundary", all(b == "WordBoundary" for _, _, b in _FakeCommunicate.goi))
    check("/tts câu trộn: audio là các đoạn đã cắt nối lại", 0 < len(r.content) < 4 * len(L))

    _FakeCommunicate.goi = []
    r = client.get("/tts", params={"text": "Vâng, em nghe.", "voice": HM})
    check("/tts câu thuần Việt: đọc nguyên câu một lần", r.status_code == 200
          and [(t, v) for t, v, _ in _FakeCommunicate.goi] == [("Vâng, em nghe.", HM)])

    _FakeCommunicate.goi, _FakeCommunicate.chet = [], {EM}
    r = client.get("/tts", params={"text": "Em merge vào main.", "voice": HM})
    check("/tts đoạn Anh hỏng: rơi về đọc nguyên câu bằng giọng đã chọn, vẫn 200",
          r.status_code == 200 and ("Em merge vào main.", HM, None) in _FakeCommunicate.goi)
finally:
    main.cfgmod.read_settings = _cfg_goc
    _FakeCommunicate.chet = set()

if _fails:
    print("\nFAIL:", len(_fails), _fails)
    raise SystemExit(1)
print("\nOK - tts_tron_tieng")
