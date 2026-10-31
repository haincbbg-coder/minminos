"""Giữ ấm tiến trình Claude Code giữa các tin của một cuộc chat (26.10.313).

Đo được ở đây (không có đăng nhập Claude thật): số lần MỞ tiến trình mới và số lần ĐÓNG qua một
chuỗi lượt chat, với client SDK giả. Lượt thứ hai của cùng cuộc chat phải không mở tiến trình nào.
"""
from _paths import ROOT, SERVER  # noqa: F401
import asyncio
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("JAVIS_STATE_DIR", tempfile.mkdtemp(prefix="minmin-giuam-"))
os.environ["MINMIN_WARM_BUDGET_MB"] = "1200"
import claude_agent_sdk as sdk  # noqa: E402
import giu_am  # noqa: E402
import claude_giu_am  # noqa: E402
from claude_sdk_engine import ClaudeSDK  # noqa: E402

_fails = []


def check(name, cond):
    print(("  ok  " if cond else "  FAIL ") + name)
    if not cond:
        _fails.append(name)


# ---------------------------------------------------------------- hồ (giu_am.Ho)
class TayGia(giu_am.Tay):
    loai = "claude"

    def __init__(self):
        self.song = True
        self.da_dong = 0

    def con_song(self):
        return self.song

    async def dong(self):
        self.song = False
        self.da_dong += 1


async def thu_ho():
    ho = giu_am.Ho()
    check("chưa có gì thì trượt", ho.lay("c1", "claude", "v1") is None)
    t = TayGia()
    cho = ho.nhan("c1", "claude", "v1", t)
    check("lượt lạnh được nhận vào hồ", cho is not None and cho.ban)
    ho.tra(cho)
    check("trả về thì rảnh", not cho.ban)
    cho2 = ho.lay("c1", "claude", "v1")
    check("cùng vân tay thì trúng, đúng tiến trình đó", cho2 is cho and cho.ban)
    ho.tra(cho2)
    check("vân tay khác thì trượt", ho.lay("c1", "claude", "v2") is None)
    await asyncio.sleep(0)
    check("và tiến trình cũ bị đóng", t.da_dong == 1)

    # Đang chạy thì không có tiến trình ấm thứ hai cho cùng cuộc chat
    a = ho.nhan("c2", "claude", "v", TayGia())
    check("cuộc chat đang bận: lượt khác không chen tiến trình thứ hai",
          ho.nhan("c2", "claude", "v", TayGia()) is None)
    ho.tra(a)

    # Hết hạn nghỉ
    t3 = TayGia()
    c3 = ho.nhan("c3", "claude", "v", t3)
    ho.tra(c3)
    so = ho.don(bay_gio=c3.luc_dung + giu_am.thoi_gian_nghi_s() + 1)
    await asyncio.sleep(0)
    check("chỗ nghỉ quá hạn được đóng", so >= 1 and t3.da_dong == 1)

    # Ngân sách: 300 MB/chỗ, trần 600 -> chỗ thứ ba đẩy chỗ rảnh lâu nhất ra
    with patch.dict(os.environ, {"MINMIN_WARM_BUDGET_MB": "600"}):
        ho2 = giu_am.Ho()
        ta, tb, tc = TayGia(), TayGia(), TayGia()
        ca = ho2.nhan("a", "claude", "v", ta)
        ho2.tra(ca)
        cb = ho2.nhan("b", "claude", "v", tb)
        ho2.tra(cb)
        cc = ho2.nhan("c", "claude", "v", tc)
        await asyncio.sleep(0)
        check("hồ đầy: đẩy chỗ rảnh lâu nhất", cc is not None and ta.da_dong == 1 and tb.da_dong == 0)
        # Cả hai chỗ đều bận thì không đẩy ai, lượt mới chạy lạnh
        cb2 = ho2.lay("b", "claude", "v")
        check("chỗ bận không bao giờ bị đẩy", ho2.nhan("d", "claude", "v", TayGia()) is None
              and cb2 is not None and tb.da_dong == 0)
    with patch.dict(os.environ, {"MINMIN_WARM_BUDGET_MB": "0"}):
        check("MINMIN_WARM_BUDGET_MB=0 tắt hẳn", giu_am.Ho().lay("x", "claude", "v") is None
              and not claude_giu_am.du_dieu_kien(ClaudeSDK(tag="chat:x")))

    # Đăng nhập/đăng xuất bỏ mọi chỗ Claude + công thức
    ho3 = giu_am.Ho()
    t4 = TayGia()
    c4 = ho3.nhan("k", "claude", "v", t4, cong_thuc=lambda: None)
    ho3.tra(c4)
    check("bo_loai đóng chỗ Claude", ho3.bo_loai("claude") == 1)
    await asyncio.sleep(0)
    check("... và tiến trình thật sự đóng, công thức bị quên",
          t4.da_dong == 1 and not ho3.hum_nong("k"))

    # Hâm nóng: chỗ đóng vì nghỉ lâu để lại công thức, gõ phím thì mở lại
    ho4 = giu_am.Ho()
    mo = []

    async def cong_thuc():
        t = TayGia()
        mo.append(t)
        return t
    c5 = ho4.nhan("h", "claude", "vh", TayGia(), cong_thuc=cong_thuc)
    ho4.tra(c5)
    ho4.don(bay_gio=c5.luc_dung + giu_am.thoi_gian_nghi_s() + 1)
    check("gõ phím: hẹn mở lại", ho4.hum_nong("h"))
    check("gõ tiếp khi đang mở thì không mở thêm", not ho4.hum_nong("h"))
    for _ in range(5):
        await asyncio.sleep(0)
    c6 = ho4.lay("h", "claude", "vh")
    check("tin tới sau khi hâm nóng: trúng tiến trình vừa mở", len(mo) == 1 and c6 is not None
          and c6.tay is mo[0])
    ho4.tra(c6)

    # Hâm nóng không được đáp xuống sau một lượt thật đã bắt đầu
    ho5 = giu_am.Ho()
    cham = asyncio.Event()

    async def cong_thuc_cham():
        await cham.wait()
        return TayGia()
    c7 = ho5.nhan("g", "claude", "v", TayGia(), cong_thuc=cong_thuc_cham)
    ho5.tra(c7)
    ho5.quen("g")
    ho5.nho_cong_thuc("g", "claude", "v", cong_thuc_cham)
    ho5.hum_nong("g")
    await asyncio.sleep(0)
    ho5.lay("g", "claude", "v")          # lượt thật đi tìm chỗ trong lúc đang hâm
    cham.set()
    for _ in range(5):
        await asyncio.sleep(0)
    check("hâm nóng chậm hơn lượt thật thì tự bỏ", ho5.nhin("g") is None and ho5.dem["tu_choi"] >= 1)


# ---------------------------------------------------------------- lượt chat qua engine
class Dem:
    mo = 0
    dong = 0
    gui = 0


def tra_loi(sid="s1", subtype="success", is_error=False):
    return sdk.ResultMessage(subtype=subtype, duration_ms=10, duration_api_ms=9, is_error=is_error,
                             num_turns=1, session_id=sid, result="ok", total_cost_usd=0.0,
                             usage={"input_tokens": 1, "output_tokens": 1})


class ClientGia:
    loi_query = False
    ket_qua = staticmethod(tra_loi)

    def __init__(self, options=None):
        self.options = options
        self.da_dong = False

    async def connect(self):
        Dem.mo += 1

    async def query(self, prompt):
        if ClientGia.loi_query and Dem.mo > 0 and not getattr(self, "_moi", False):
            raise RuntimeError("pipe đã đóng")
        Dem.gui += 1

    async def interrupt(self):
        pass

    async def disconnect(self):
        if not self.da_dong:
            self.da_dong = True
            Dem.dong += 1

    def receive_response(self):
        async def _g():
            yield ClientGia.ket_qua()
        return _g()


def opts_gia(cli):
    return SimpleNamespace(cwd=cli.cwd, model=cli.model, effort=cli.effort, resume=cli.session_id,
                           include_hook_events=False, stderr=None, env={}, mcp_servers=None)


async def mot_luot(sid_hoi_thoai, effort=None, session="s1"):
    cli = ClaudeSDK(tag=f"chat:{sid_hoi_thoai}:abcd", cwd=tempfile.gettempdir())
    cli.session_id = session
    cli.effort = effort
    evs = []
    async for ev in claude_giu_am.query(cli, "xin chào", sid_hoi_thoai):
        evs.append(ev)
    return evs


async def thu_luot():
    giu_am.HO = giu_am.Ho()
    with patch.object(sdk, "ClaudeSDKClient", ClientGia), \
         patch.object(ClaudeSDK, "is_available", return_value=True), \
         patch.object(ClaudeSDK, "_options", lambda self: opts_gia(self)), \
         patch("claude_token_gate.xep_hang", return_value=""):
        Dem.mo = Dem.dong = Dem.gui = 0
        await mot_luot("hoi-thoai-1")
        check("lượt đầu mở 1 tiến trình và GIỮ lại (không đóng)", Dem.mo == 1 and Dem.dong == 0)
        await mot_luot("hoi-thoai-1")
        await mot_luot("hoi-thoai-1")
        check("lượt 2 và 3 của cùng cuộc chat không mở tiến trình mới", Dem.mo == 1 and Dem.gui == 3)
        check("hồ ghi 2 lần trúng", giu_am.HO.dem["trung"] == 2)

        await mot_luot("hoi-thoai-2")
        check("cuộc chat khác có tiến trình riêng", Dem.mo == 2)

        await mot_luot("hoi-thoai-1", effort="high")
        await asyncio.sleep(0)
        check("đổi độ sâu suy nghĩ: mở tiến trình mới, đóng cái cũ", Dem.mo == 3 and Dem.dong == 1)

        # Lượt kết thúc không sạch (lỗi) thì không giữ
        ClientGia.ket_qua = staticmethod(lambda: tra_loi(subtype="error_during_execution", is_error=True))
        await mot_luot("hoi-thoai-1", effort="high")
        await asyncio.sleep(0)
        check("lượt lỗi: tiến trình ấm bị đóng chứ không giữ lại",
              giu_am.HO.nhin("hoi-thoai-1") is None and Dem.dong == 2)
        ClientGia.ket_qua = staticmethod(tra_loi)

        # Chưa có mạch (phiên mới) thì chạy lạnh rồi mới giữ
        mo_truoc = Dem.mo
        await mot_luot("hoi-thoai-3", session=None)
        check("phiên mới: mở tiến trình như cũ", Dem.mo == mo_truoc + 1)

        # Tiến trình ấm từ chối tin -> chạy lại lạnh, người dùng không thấy lỗi
        await mot_luot("hoi-thoai-4")
        mo_truoc = Dem.mo
        ClientGia.loi_query = True
        orig_init = ClientGia.__init__

        def init_moi(self, options=None):
            orig_init(self, options)
            self._moi = True
        with patch.object(ClientGia, "__init__", init_moi):
            evs = await mot_luot("hoi-thoai-4")
        ClientGia.loi_query = False
        check("tiến trình ấm hỏng: tự chạy lạnh lại, không báo lỗi",
              Dem.mo == mo_truoc + 1 and not any(e["type"] == "error" for e in evs)
              and any(e["type"] == "final" for e in evs))

        # Việc nền / bot không bao giờ dùng hồ
        cli = ClaudeSDK(tag="loop:x", cwd=tempfile.gettempdir())
        check("việc nền không đủ điều kiện", not claude_giu_am.du_dieu_kien(cli))
        cli2 = ClaudeSDK(tag="chat:x", cwd=tempfile.gettempdir(), allowed_tools=["Read"])
        check("phiên có allowlist không đủ điều kiện", not claude_giu_am.du_dieu_kien(cli2))
        await giu_am.HO.dong_het()


def thu_van_tay():
    d = tempfile.mkdtemp(prefix="vt-")
    cli = ClaudeSDK(tag="chat:a", cwd=d)
    o = SimpleNamespace(cwd=d, env={}, resume="s1")
    v1 = claude_giu_am._bam(claude_giu_am.cac_phan_van_tay(cli, o))
    # Claude Code tự ghi lại file đăng nhập sau mỗi lượt: không được đổi vân tay
    home = tempfile.mkdtemp(prefix="home-")
    with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": home}):
        a = claude_giu_am._bam(claude_giu_am.cac_phan_van_tay(cli, o))
        with open(os.path.join(home, ".credentials.json"), "w") as f:
            f.write("{}")
        b = claude_giu_am._bam(claude_giu_am.cac_phan_van_tay(cli, o))
    check("file đăng nhập bị ghi lại không đổi vân tay", a == b)
    os.makedirs(os.path.join(d, ".claude", "skills", "viet-email"))
    with open(os.path.join(d, ".claude", "skills", "viet-email", "SKILL.md"), "w") as f:
        f.write("x")
    v2 = claude_giu_am._bam(claude_giu_am.cac_phan_van_tay(cli, o))
    check("thêm skill thì đổi vân tay (Claude Code chỉ nạp lúc khởi động)", v1 != v2)
    p1 = claude_giu_am.cac_phan_van_tay(cli, o)
    o2 = SimpleNamespace(cwd=d, env={}, resume="s2")
    check("log nêu đúng phần đổi", claude_giu_am.phan_doi(p1, claude_giu_am.cac_phan_van_tay(cli, o2)) == ["resume"])


def thu_noi_day():
    main_src = (SERVER / "main.py").read_text(encoding="utf-8")
    check("chat dashboard chạy qua claude_giu_am", "claude_giu_am.query(cli, prompt, conv_sid)" in main_src)
    check("đăng nhập/đăng xuất bỏ tiến trình ấm", main_src.count('giu_am.HO.bo_loai("claude")') >= 3)
    check("xoá hội thoại quên tiến trình ấm", "giu_am.HO.quen(session_id)" in main_src)
    check("tắt server đóng hết", "await giu_am.HO.dong_het()" in main_src)
    check("có route hâm nóng", '@app.post("/chat/hum-nong")' in main_src)
    eng = (SERVER / "claude_sdk_engine.py").read_text(encoding="utf-8")
    check("engine vẫn disconnect khi không có lớp giữ ấm",
          "if not (am is not None and am.xong(self, client, sach)):" in eng)
    for f in ("giu_am.py", "claude_giu_am.py"):
        check(f"{f} không có em dash", "—" not in (SERVER / f).read_text(encoding="utf-8"))


asyncio.run(thu_ho())
asyncio.run(thu_luot())
thu_van_tay()
thu_noi_day()

if _fails:
    print(f"\nFAIL - test_giu_am: {len(_fails)} lỗi: {_fails}")
    sys.exit(1)
print("\nOK - test_giu_am")
