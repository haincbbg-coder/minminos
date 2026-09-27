"""Đọc câu Việt xen Anh cho đúng: tách đoạn tiếng Việt và đoạn tiếng Anh, đọc riêng rồi nối.

Vì sao có module này (0.64.67): Edge TTS đọc cả câu bằng MỘT ngôn ngữ. Giọng Việt (Hoài My)
đọc "GitHub" bằng âm Việt; giọng đa ngôn ngữ (Emma) tự dò ngôn ngữ THEO CẢ CÂU, câu chủ yếu
tiếng Việt thì nó cũng đọc "merge vào main" thành "mét vào mên". Đo bằng cách cho Whisper nghe
lại: cả hai giọng đều ra "Youtube Action", "Daspo" (dashboard). Đã thử chèn thẻ SSML
`<lang xml:lang>` để đổi ngôn ngữ giữa câu: Edge bản miễn phí từ chối, không trả audio.

Nên tách: đoạn Việt đọc bằng giọng Việt bản địa, đoạn Anh bằng giọng đa ngôn ngữ CÙNG GIỚI,
nối mp3 lại. Hai điều đo được khi làm (đừng "đơn giản hoá" ngược lại):
  - Đoạn Việt KHÔNG giao cho giọng đa ngôn ngữ: mẩu ngắn như "đã", "vào" nó đọc thành "Da",
    "Vau" vì không đủ chữ để dò ra tiếng Việt.
  - Mỗi lần gọi Edge kèm ~1,4 giây im lặng ở ĐUÔI ("vào" hết tiếng ở 0,45 giây, file dài
    1,87 giây). Nối nguyên thì câu đứt quãng từng chữ. Nên cắt đuôi theo mốc WordBoundary.
    KHÔNG cắt đầu: khung mp3 mượn byte của khung trước (bit reservoir), cắt đầu là rè.

Nhận ra từ tiếng Anh: câu trả lời viết tiếng Việt CÓ DẤU, nên từ có dấu chắc chắn là tiếng
Việt. Từ không dấu thì xét cấu trúc âm tiết: "anh", "cho", "sang" là âm tiết Việt hợp lệ, còn
"push", "build", "main", "log", "deploy" thì không. Chữ viết tắt toàn hoa (VPS, API) và chữ hoa
giữa từ (GitHub) cũng là tiếng Anh.

Module này không gọi mạng và không đọc settings: nhận một hàm tổng hợp từ chỗ gọi (main.py).
"""
import asyncio
import re

# Âm đầu tiếng Việt viết bằng chữ ASCII (đ đã có dấu nên không cần). Dài trước ngắn sau.
_AM_DAU = ("ngh", "ng", "nh", "ch", "gh", "gi", "kh", "ph", "qu", "th", "tr",
           "b", "c", "d", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x", "")
# Vần tiếng Việt viết thuần ASCII (không mũ, không móc, không thanh).
_VAN = frozenset("""
a ac ach ai am an ang anh ao ap at au ay
e ec em en eng eo ep et
i ia ich im in inh ip it iu
o oa oac oach oai oam oan oang oanh oao oap oat oay oc oe oen oeo oet oi om on ong ooc oong op ot
u ua uc ui um un ung up ut uy uya uych uyn uynh uyp uyt
y
""".split())
# Từ tiếng Anh ngắn trùng khuôn âm tiết Việt mà tiếng Việt thật luôn viết có dấu ("chát",
# "tốp", "ít"). KHÔNG đưa vào đây những từ tiếng Việt không dấu: "to" (chữ to), "in" (in hoá
# đơn), "no" (ăn no), "so" (so sánh), "do" (do đó), "pin" (sạc pin).
_ANH_NGAN = frozenset("chat top tip map cap ping bin hi ok up at it by".split())
# Từ nối tiếng Anh: trùng khuôn Việt nên để yên, trừ khi KẸP GIỮA hai từ tiếng Anh ("sign in
# to GitHub", "pull request of the team"). Chỉ những từ này được kéo, không kéo "anh", "em".
_NOI_ANH = frozenset("""
to in on a an the and for with of or no so do my your you me we our is are be can
""".split())
_TU = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*", re.U)


def _la_am_tiet_viet(w: str) -> bool:
    s = w.lower()
    for d in _AM_DAU:
        if s.startswith(d) and s[len(d):] in _VAN:
            return True
    return False


def la_tu_tieng_anh(w: str) -> bool:
    """Một từ (chỉ chữ cái) có phải tiếng Anh không. Có dấu tiếng Việt thì chắc chắn không."""
    if not w or not w.isascii():
        return False
    if len(w) >= 2 and w.isupper():
        return True                          # VPS, API, MCP
    if any(c.isupper() for c in w[1:]):
        return True                          # GitHub, OpenRouter, iPhone
    if w.lower() in _ANH_NGAN:
        return True
    return not _la_am_tiet_viet(w)


def tach_doan(text: str):
    """Chuỗi -> danh sách (ngôn ngữ, đoạn), ngôn ngữ là "vi" hoặc "en". Ghép lại ra nguyên văn.

    Dấu câu, số, khoảng trắng sau một từ đi theo đoạn của từ đó.
    """
    s = str(text or "")
    toks = list(_TU.finditer(s))
    if not toks:
        return [("vi", s)] if s else []
    nhan = [("en" if la_tu_tieng_anh(m.group(0)) else "vi") for m in toks]
    # Chuỗi từ nối tiếng Anh ("in to", "of the") kẹp giữa hai từ tiếng Anh thì theo tiếng Anh.
    # "the" đứng đầu câu trước một từ tiếng Anh ("The build passed") cũng vậy.
    noi = [nhan[i] == "vi" and toks[i].group(0).lower() in _NOI_ANH for i in range(len(toks))]
    i = 0
    while i < len(toks):
        if not noi[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(toks) and noi[j + 1]:
            j += 1
        trai = nhan[i - 1] == "en" if i > 0 else toks[i].group(0).lower() == "the"
        phai = j + 1 < len(toks) and nhan[j + 1] == "en"
        if trai and phai:
            for x in range(i, j + 1):
                nhan[x] = "en"
        i = j + 1
    doan, dau, ngon = [], 0, nhan[0]
    for i in range(1, len(toks)):
        if nhan[i] != ngon:
            cat = toks[i].start()
            doan.append((ngon, s[dau:cat]))
            dau, ngon = cat, nhan[i]
    doan.append((ngon, s[dau:]))
    return [(n, t) for n, t in doan if t]


# Giọng đã chọn -> (giọng đọc đoạn Việt, giọng đọc đoạn Anh). Cùng giới để nghe vẫn gần một
# người. Giọng không có ở đây (giọng tiếng khác) thì không tách.
_EMMA, _ANDREW = "en-US-EmmaMultilingualNeural", "en-US-AndrewMultilingualNeural"
_HOAIMY, _NAMMINH = "vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"
_CAP_GIONG = {
    _HOAIMY: (_HOAIMY, _EMMA),
    _NAMMINH: (_NAMMINH, _ANDREW),
    _EMMA: (_HOAIMY, _EMMA),
    "en-US-AvaMultilingualNeural": (_HOAIMY, "en-US-AvaMultilingualNeural"),
    _ANDREW: (_NAMMINH, _ANDREW),
    "en-US-BrianMultilingualNeural": (_NAMMINH, "en-US-BrianMultilingualNeural"),
    "en-AU-WilliamMultilingualNeural": (_NAMMINH, "en-AU-WilliamMultilingualNeural"),
}


def giong_cho_doan(voice: str, ngon: str) -> str:
    cap = _CAP_GIONG.get(voice)
    if not cap:
        return voice
    return cap[1] if ngon == "en" else cap[0]


def nen_tach(voice: str, text: str) -> bool:
    """Có cần đọc tách đoạn không.

    Cần khi: giọng nằm trong bảng ghép, câu có tiếng Anh, và KHÔNG phải trường hợp giọng đa ngôn
    ngữ gặp câu thuần tiếng Anh (nó tự đọc chuẩn). Câu thuần Việt thì đọc nguyên như cũ.
    """
    if voice not in _CAP_GIONG:
        return False
    ngs = {n for n, _ in tach_doan(text)}
    if "en" not in ngs:
        return False
    return not (ngs == {"en"} and not voice.startswith("vi-VN-"))


# ---- Cắt đuôi im lặng của mp3 ----
_BR_M1 = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
_BR_M2 = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
_SR = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}
# Mốc WordBoundary của Edge SỚM hơn lúc nghe thấy tiếng: đo bằng ffmpeg, "đã" có mốc 121 ms
# nhưng có tiếng ở 182 ms, "merge" 50 ms mà 160 ms (một phần là độ trễ giải mã mp3 ~50 ms).
# Nên cắt đầu ở mốc + `CAT_SAU_MOC_MS`, vẫn còn chừa vài chục ms trước tiếng thật.
CAT_SAU_MOC_MS = 20
DEM_DUOI_MS = 40        # chừa sau tiếng cuối: đủ cho âm tắt dần, ngắn như chỗ nghỉ giữa hai từ
DEM_DAU_CAU_MS = 220    # đoạn kết bằng dấu phẩy/chấm: nghỉ như người đọc gặp dấu câu
# Khung mp3 Layer III mượn tối đa 511 byte (MPEG1) / 255 byte (MPEG2) dữ liệu của các khung
# TRƯỚC nó (bit reservoir). Edge dùng rất nhiều: khung thứ hai đã mượn 124 byte. Nên khi cắt
# đầu, giữ lại đúng số khung ngay trước chỗ cắt mà khung đầu cần mượn, làm "kho", và xoá side
# info của chúng về 0: khung kho giải mã ra im lặng, còn byte dữ liệu vẫn nằm đó cho khung sau
# mượn. Đã soát bằng ffmpeg: giải mã sạch, không báo lỗi.


def _cac_khung(data: bytes):
    """[(vị trí, độ dài, thời lượng ms, vị trí side info, độ dài side info)] hoặc None nếu không
    đọc ra được toàn bộ luồng như mp3 Layer III."""
    ra, pos, n = [], 0, len(data)
    while pos < n:
        if pos + 4 > n:
            return None
        b1, b2, b3 = data[pos + 1], data[pos + 2], data[pos + 3]
        if data[pos] != 0xFF or (b1 & 0xE0) != 0xE0 or ((b1 >> 1) & 3) != 1:
            return None
        ver = (b1 >> 3) & 3
        bri, sri, pad = b2 >> 4, (b2 >> 2) & 3, (b2 >> 1) & 1
        if ver == 1 or sri == 3 or bri in (0, 15):
            return None
        sr = _SR[ver][sri]
        mono = (b3 >> 6) == 3
        if ver == 3:
            dai, mau, si = 144 * _BR_M1[bri] * 1000 // sr + pad, 1152, (17 if mono else 32)
        else:
            dai, mau, si = 72 * _BR_M2[bri] * 1000 // sr + pad, 576, (9 if mono else 17)
        vt_si = pos + 4 + (0 if (b1 & 1) else 2)       # bit bảo vệ = 0 thì có 2 byte CRC
        if vt_si + si > pos + dai:
            return None
        # main_data_begin: số byte khung này mượn của các khung trước (9 bit MPEG1, 8 bit MPEG2).
        muon = ((data[vt_si] << 1) | (data[vt_si + 1] >> 7)) if ver == 3 else data[vt_si]
        ra.append((pos, dai, mau * 1000.0 / sr, vt_si, si, muon, pos + dai - vt_si - si))
        pos += dai
    return ra if pos == n else None


def cat_mp3(data: bytes, dau_ms, giu_ms) -> bytes:
    """Bỏ khoảng lặng trước tiếng đầu (`dau_ms` là mốc WordBoundary) và sau `giu_ms` (ms,
    None = không cắt phía đó).

    Đọc không ra khung thì trả NGUYÊN VẸN: thà dư khoảng lặng còn hơn mất tiếng hay rè.
    """
    if not data:
        return data
    khung = _cac_khung(data)
    if not khung:
        return data
    moc, t = [], 0.0
    for k in khung:
        moc.append(t)
        t += k[2]
    cuoi = len(khung)
    if giu_ms is not None and giu_ms > 0:
        cuoi = next((i for i, m in enumerate(moc) if m >= giu_ms), len(khung))
    dau = k = 0
    if dau_ms is not None and dau_ms + CAT_SAU_MOC_MS > 0:
        k = max((i for i, m in enumerate(moc) if m <= dau_ms + CAT_SAU_MOC_MS), default=0)
        # Lùi đủ số khung kho cho khung k mượn dữ liệu.
        dau, du = k, 0
        while du < khung[k][5] and dau > 0:
            dau -= 1
            du += khung[dau][6]
        if du < khung[k][5]:
            dau = k = 0                             # không đủ kho: để nguyên phần đầu
    if cuoi <= k:
        return data
    out = bytearray(data[khung[dau][0]:khung[cuoi - 1][0] + khung[cuoi - 1][1]])
    goc = khung[dau][0]
    for i in range(dau, k):                         # khung kho: side info về 0 = khung im lặng
        vt_si, si = khung[i][3], khung[i][4]
        out[vt_si - goc:vt_si - goc + si] = bytes(si)
    return bytes(out)


def moc_cat(doan: str, moc) -> tuple:
    """(mốc tiếng đầu, mốc giữ tới) cho một đoạn, từ (tiếng đầu, hết tiếng cuối) của Edge.
    Đoạn kết bằng dấu câu thì chừa đuôi dài hơn, như người đọc ngừng ở dấu phẩy."""
    dau, ket = moc if moc else (None, None)
    if ket is None:
        return dau, None
    dem = DEM_DAU_CAU_MS if re.search(r"[,.;:!?…]\s*$", doan) else DEM_DUOI_MS
    return dau, ket + dem


async def doc_tron(text: str, voice: str, tong_hop, song_song: int = 8) -> bytes:
    """Đọc câu trộn hai tiếng. `tong_hop(doan, giong)` là coroutine trả (bytes mp3, (mốc tiếng
    đầu, mốc hết tiếng cuối) tính bằng ms hoặc None). Các đoạn gọi song song (tối đa
    `song_song`), nối theo thứ tự. Đoạn nào hỏng thì ném lỗi để chỗ gọi rơi về đọc nguyên câu.

    Đoạn đầu giữ nguyên khoảng lặng đầu, đoạn cuối giữ nguyên đuôi: chỉ cắt ở CHỖ NỐI.
    """
    doan = [(n, d) for n, d in tach_doan(text) if re.search(r"[^\W_]", d)]
    sem = asyncio.Semaphore(max(1, song_song))

    async def _mot(i, ngon, d):
        async with sem:
            audio, moc = await tong_hop(d, giong_cho_doan(voice, ngon))
        if not audio:
            raise RuntimeError("Edge không trả audio cho một đoạn.")
        dau, giu = moc_cat(d, moc)
        return cat_mp3(audio, dau if i > 0 else None, giu if i < len(doan) - 1 else None)

    phan = await asyncio.gather(*[_mot(i, n, d) for i, (n, d) in enumerate(doan)])
    return b"".join(phan)
