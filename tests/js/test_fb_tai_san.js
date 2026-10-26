/* Facebook nhiều tài khoản - giao diện (plans/fb-nhieu-tai-khoan Phase 04).

       node tests/js/test_fb_tai_san.js

   Khoá lại:
   1. Hàm thuần của fb-tai-san.js: nhãn vai trò, nguồn, chip token, lọc/tìm, đếm, tiền, chip hỏi Trang.
   2. HTML khối chính và hộp Soi quyền đúng hợp đồng PLAN.md và escape mọi chuỗi máy chủ.
   3. chat-card.js nhận {"type":"duyet_ads","id"} (id [a-z0-9]{8,32}), từ chối id xấu, loại cũ vẫn chạy.
   4. duyet-ads.js vẽ thẻ từ bản ghi máy chủ, đúng nút theo trạng thái, escape.
   5. CSS chỉ dùng token --mm-* (cùng luật test_design_tokens.py), i18n đủ vi/en.
*/
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..", "..");
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");
const VI = JSON.parse(read("dashboard/i18n/vi.json"));
const EN = JSON.parse(read("dashboard/i18n/en.json"));
const FB = require(path.join(root, "dashboard/fb-tai-san.js"));
const DA = require(path.join(root, "dashboard/duyet-ads.js"));
const C = require(path.join(root, "dashboard/chat-card.js"));
const SRC_FB = read("dashboard/fb-tai-san.js");
const SRC_DA = read("dashboard/duyet-ads.js");

let fails = [];
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (cond || extra === undefined ? "" : "  [" + extra + "]"));
  if (!cond) fails.push(name);
}
const XSS = '<img src=x onerror="alert(1)">';

// ---------------------------------------------------------------- 1. hàm thuần
check("vai trò quan_tri -> Quản trị viên", FB.nhanVaiTro("quan_tri") === "Quản trị viên");
check("vai trò bien_tap/kiem_duyet/quang_cao/phan_tich", FB.nhanVaiTro("bien_tap") === "Biên tập viên" &&
  FB.nhanVaiTro("kiem_duyet") === "Kiểm duyệt viên" && FB.nhanVaiTro("quang_cao") === "Quảng cáo" && FB.nhanVaiTro("phan_tich") === "Phân tích");
check("vai trò lạ -> Khác", FB.nhanVaiTro("xyz") === "Khác" && FB.nhanVaiTro(undefined) === "Khác");
check("nguồn cá nhân", FB.nhanNguon({ qua: "ca_nhan" }) === "cá nhân");
check("nguồn qua BM có tên", FB.nhanNguon({ qua: "bm", bm_ten: "HALIMI BM" }) === "qua BM HALIMI BM");

const tk = (o) => Object.assign({ fb_id: "1", ten: "Hải", token: { trang_thai: "tot" }, thieu_quyen: [] }, o);
check("chip token tốt", FB.chipToken(tk()).cls === "ok" && FB.chipToken(tk()).chu === "Token tốt");
check("chip sắp hết hạn = warn", FB.chipToken(tk({ token: { trang_thai: "sap_het" } })).chu === "Sắp hết hạn");
check("chip token lỗi/hết hạn = bad", FB.chipToken(tk({ token: { trang_thai: "loi" } })).cls === "bad" &&
  FB.chipToken(tk({ token: { trang_thai: "het_han" } })).chu === "Token lỗi");
check("thiếu ads_management = warn Thiếu quyền quảng cáo",
  FB.chipToken(tk({ thieu_quyen: [{ ma: "ads_management", ten: "Quản lý quảng cáo" }] })).chu === "Thiếu quyền quảng cáo");
check("token lỗi thắng thiếu quyền", FB.chipToken(tk({ token: { trang_thai: "loi" }, thieu_quyen: [{ ma: "ads_management" }] })).cls === "bad");

const ROWS = [{ id: "111", ten: "HALIMI Đầm Lụa" }, { id: "222", ten: "MeiMei Design" }, { id: "333", ten: "Melya", van_de: "chua_giao" }];
check("lọc theo tên không dấu", FB.locDong(ROWS, "dam lua").length === 1);
check("lọc theo id", FB.locDong(ROWS, "222")[0].ten === "MeiMei Design");
check("lọc rỗng trả hết", FB.locDong(ROWS, "  ").length === 3 && FB.locDong(null, "x").length === 0);
check("canXuLy lấy dòng có van_de", FB.canXuLy(ROWS).length === 1);

const DATA = {
  ok: true, kiem_luc: "2026-10-26T08:12:00", loi: [],
  tai_khoan: [
    { fb_id: "10", ten: "Hải", mac_dinh: true, ket_noi: [{ id: "c1", connector_id: "facebook-pages", label: "FB Hải" }],
      token: { trang_thai: "tot", con_ngay: 50, loi: "" }, so_trang: 16, so_tkqc: 9, can_xu_ly: 2, thieu_quyen: [] },
    { fb_id: "20", ten: "Mai " + XSS, mac_dinh: false, ket_noi: [], token: { trang_thai: "sap_het", con_ngay: 3, loi: "" },
      so_trang: 2, so_tkqc: 1, can_xu_ly: 0, thieu_quyen: [{ ma: "ads_management", ten: "Quản lý quảng cáo" }] },
  ],
  trang: [
    { id: "p1", ten: "HALIMI", nguon: { "10": { vai_tro: "quan_tri", qua: "ca_nhan", bm_ten: "", giao: true },
      "20": { vai_tro: "bien_tap", qua: "bm", bm_ten: "BM Halimi", giao: true } }, dang_bang: "10", van_de: "" },
    { id: "p2", ten: "Trang " + XSS, nguon: { "20": { vai_tro: "quan_tri", qua: "bm", bm_ten: "BM <b>", giao: false } },
      dang_bang: "", van_de: "chua_giao" },
  ],
  tkqc: [
    { id: "act1", ten: "TKQC 1", nguon: { "10": { qua: "bm", bm_ten: "BM Halimi", giao: true } }, dung: "10", van_de: "" },
    { id: "act2", ten: "TKQC 2", nguon: { "20": { qua: "ca_nhan", bm_ten: "", giao: true } }, dung: "20", van_de: "thieu_quyen_ghi" },
  ],
};
const dem = FB.demSo(DATA);
check("đếm Trang/TKQC/cần xử lý", dem.trang === 2 && dem.tkqc === 2 && dem.can === 2);
check("tkCanSoi chọn tài khoản chưa giao", FB.tkCanSoi(DATA.trang[1], DATA) === "20");

check("tiền vi-VN", FB.tien(1250000) === "1.250.000 đ" && FB.tien("980000") === "980.000 đ" && FB.tien(0) === "0 đ");
check("tiền rỗng/không số -> chuỗi rỗng", FB.tien(null) === "" && FB.tien("") === "" && FB.tien("abc") === "");
check("duyet-ads dùng cùng định dạng tiền", DA.tien(1250000) === "1.250.000 đ");

const KQ = { giao: "ok", giao_khong_dang: "warn", chua_giao_bm: "warn", khong_thay_quyen: "warn", khong_tim_thay: "bad",
  thieu_quyen: "bad", loi_token: "bad", can_id: "warn" };
check("chip hỏi Trang đúng màu cho 8 kết quả", Object.keys(KQ).every((k) => FB.chipHoiTrang(k).cls === KQ[k]));
check("chip hỏi Trang: chữ theo thiết kế", FB.chipHoiTrang("giao").chu === "Đã giao, đăng được" &&
  FB.chipHoiTrang("giao_khong_dang").chu === "Đã giao, không có quyền đăng" && FB.chipHoiTrang("can_id").chu === "Cần ID hoặc link");
check("nút chưa giao", FB.nhanNut("dang_nhap_lai") === "Đăng nhập lại và tick" && FB.nhanNut("cap_quyen") === "Cấp quyền" &&
  FB.nhanNut("huong_dan") === "Xem hướng dẫn");

// ---------------------------------------------------------------- 2. HTML khối chính
const h = FB.htmlKhoi(DATA, { tab: "trang" });
check("tiêu đề + phụ đề có N tài khoản", h.includes("Facebook - Trang và tài khoản quảng cáo") && h.includes("Gộp từ 2 tài khoản Facebook"));
check("nút Quét lại + nút chính Thêm tài khoản", h.includes('data-fbts="quet"') && /class="fbts-nut-chinh" data-fbts="them"/.test(h));
check("thẻ tài khoản: dòng đếm", h.includes("16 Trang · 9 TKQC · 2 cần xử lý"));
check("thẻ tài khoản: avatar chữ đầu", h.includes('<span class="fbts-avatar" aria-hidden="true">H</span>'));
check("thẻ tài khoản: nút Soi quyền mang fb_id", h.includes('data-fbts="soi" data-fb="10"'));
check("tablist + tab đang chọn aria-selected", h.includes('role="tablist"') && /aria-selected="true"[^>]*>Trang \(2\)/.test(h) &&
  h.includes("Tài khoản quảng cáo (2)") && h.includes("Cần xử lý (2)"));
check("ô tìm", h.includes('data-fbts-o="q"') && h.includes('placeholder="Tìm theo tên hoặc ID"'));
check("bảng nằm trong hộp cuộn ngang", h.includes('<div class="fbts-bang-hop"><table class="fbts-bang">'));
check("cột mỗi tài khoản + cột MinMin đăng bằng", h.includes("<th scope=\"col\">Hải</th>") && h.includes("MinMin đăng bằng"));
check("ô: vai trò + nguồn", h.includes("Quản trị viên") && h.includes("cá nhân") && h.includes("qua BM BM Halimi"));
check("ô chưa giao có chip warn", h.includes('fbts-chip warn fbts-chip-o">Facebook chưa giao cho MinMin'));
check("ô không có quyền là -", h.includes('<span class="fbts-mo">-</span>'));
check("dòng van_de nền warn + nút Cách sửa", h.includes('class="fbts-van-de"') && h.includes('data-fb="20">Cách sửa'));
check("cột cuối: chip ok tên tài khoản / bad Chưa đăng được", h.includes('fbts-chip ok">Hải</span>') && h.includes('fbts-chip bad">Chưa đăng được'));
check("ghi chú cuối dùng 'Bạn', không 'Bố'", h.includes("Bạn vẫn ra lệnh được") && !/Bố/.test(h));
check("escape chuỗi máy chủ trong khối", !h.includes(XSS) && h.includes("&lt;img src=x") && h.includes("BM &lt;b&gt;"));

const hq = FB.htmlKhoi(DATA, { tab: "tkqc" });
check("tab TKQC: cột MinMin dùng + chỉ đọc khi thieu_quyen_ghi", hq.includes("MinMin dùng") && hq.includes("(chỉ đọc)") && hq.includes("TKQC 1"));
const hc = FB.htmlKhoi(DATA, { tab: "can" });
check("tab Cần xử lý gộp Trang + TKQC có van_de", hc.includes("Trang (1)") && hc.includes("Tài khoản quảng cáo (1)") && !hc.includes(">HALIMI<"));
check("tìm không khớp -> câu rỗng", FB.htmlKhoi(DATA, { tab: "trang", q: "zzz" }).includes("Không có dòng nào khớp."));
check("chưa có tài khoản -> câu mời thêm", FB.htmlKhoi({ tai_khoan: [], trang: [], tkqc: [] }, {}).includes("Chưa có tài khoản Facebook nào"));

// ---------------------------------------------------------------- 2b. HTML Soi quyền
const SOI = {
  ok: true, kiem_luc: "2026-10-26T08:12:00", ung_dung: "MinMin App " + XSS,
  tai_khoan: DATA.tai_khoan[0],
  quyen: [{ ma: "pages_show_list", ten: "Xem danh sách Trang", co: true, de_lam: "thấy Trang" },
    { ma: "ads_management", ten: "Quản lý quảng cáo", co: false, de_lam: "bật/tắt chiến dịch" }],
  trang_giao: 16, tkqc_giao: 9, trang_chua_giao: 2, tkqc_chua_giao: 0,
  chua_giao: [
    { loai: "trang", id: "p9", ten: "Trang ẩn " + XSS, vai_tro: "quan_tri", qua: "bm", bm_ten: "BM X", ly_do_ma: "chua_giao_bm",
      ly_do: "Chưa tick lúc đăng nhập", cach_sua: "Đăng nhập lại và tick Trang này", nut: "dang_nhap_lai" },
    { loai: "tkqc", id: "act9", ten: "TKQC 9", vai_tro: "", qua: "ca_nhan", bm_ten: "", ly_do_ma: "thieu_quyen",
      ly_do: "Thiếu ads_management", cach_sua: "Cấp quyền", nut: "cap_quyen" },
  ],
};
const s = FB.htmlSoi(SOI, { fb_id: "10" });
check("hộp: tiêu đề + giờ kiểm", s.includes("Soi quyền Facebook - Hải") && s.includes("Kiểm lúc 08:12."));
check("hộp: Soi lại + nút chính Đăng nhập lại + nút đóng", s.includes('data-fbts="soi_lai"') &&
  s.includes('class="fbts-nut-chinh" data-fbts="dang_nhap_lai">Đăng nhập lại Facebook') && s.includes('data-fbts="dong"'));
check("4 ô số, chưa giao > 0 tô warn", s.includes("Trang đã giao") && s.includes("TKQC chưa giao") &&
  s.includes('fbts-so-gt warn">2</b>') && s.includes('fbts-so-gt">0</b>'));
check("dải quyền: ok/bad + de_lam cho quyền thiếu", s.includes('fbts-chip ok">') && s.includes("Quản lý quảng cáo - bật/tắt chiến dịch"));
check("dòng Ứng dụng", s.includes("Ứng dụng: MinMin App"));
check("chưa giao: nút theo `nut`", s.includes('data-nut="dang_nhap_lai">Đăng nhập lại và tick') && s.includes('data-nut="cap_quyen">Cấp quyền'));
check("chưa giao: dòng phụ Trang · vai trò · nguồn", s.includes("Trang · Quản trị viên · qua BM BM X"));
check("ghi chú trung thực về Trang chưa tick", s.includes("Facebook không cho MinMin biết nó tồn tại"));
check("form Hỏi Facebook có label + placeholder", s.includes('<label class="fbts-nhan" for="fbts-hoi-q">') &&
  s.includes('placeholder="Tên, ID hoặc link Trang"') && s.includes(">Hỏi Facebook</button>"));
check("hộp escape", !s.includes(XSS) && s.includes("Trang ẩn &lt;img"));
check("chưa giao rỗng -> câu rỗng", FB.htmlSoi(Object.assign({}, SOI, { chua_giao: [] }), {}).includes("Không có gì chưa giao."));
check("lỗi soi hiện câu lỗi", FB.htmlSoi(null, { loiTai: "HTTP 500", fb_id: "10" }).includes("Chưa soi được: HTTP 500"));

const kq = FB.htmlHoiKetQua({ ok: true, id: "123", ten: "Trang A", ket_qua: "chua_giao_bm", ly_do: "Lý do " + XSS,
  cach_sua: "Đăng nhập lại", nguyen_van: '{"error":"<x>"}' });
check("kết quả hỏi: chip + lý do + Cách sửa", kq.includes('fbts-chip warn">Chưa giao cho MinMin') && kq.includes("Cách sửa: Đăng nhập lại"));
check("kết quả hỏi: nguyên văn gập trong details/code", kq.includes("<details") && kq.includes("Nguyên văn Facebook trả về") &&
  kq.includes("<code>{&quot;error&quot;:&quot;&lt;x&gt;&quot;}</code>"));
check("kết quả hỏi escape", !kq.includes(XSS));

// ---------------------------------------------------------------- nguồn: hợp đồng HTTP + sự kiện
check("GET /meta/tai-san?lam_moi=", SRC_FB.includes('"/meta/tai-san?lam_moi="'));
check("GET /meta/soi-quyen?fb_id=", SRC_FB.includes('"/meta/soi-quyen?fb_id=" + encodeURIComponent'));
check("POST /meta/hoi-trang form fb_id + q", SRC_FB.includes('"/meta/hoi-trang", { method: "POST"') &&
  SRC_FB.includes('body.append("fb_id"') && SRC_FB.includes('body.append("q"'));
check("credentials same-origin", SRC_FB.includes('credentials: "same-origin"') && SRC_DA.includes('credentials: "same-origin"'));
check("sự kiện fbts:them + fbts:dang-nhap-lai {fb_id, ket_noi}", SRC_FB.includes('"fbts:them"') &&
  /"fbts:dang-nhap-lai", \{ fb_id: h\.st\.fb_id, ket_noi:/.test(SRC_FB));
check("hộp: Esc đóng + bẫy Tab + aria-modal", SRC_FB.includes('ev.key === "Escape"') && SRC_FB.includes('ev.key !== "Tab"') &&
  SRC_FB.includes('"aria-modal", "true"'));
check("window.FbTaiSan.mount/moSoiQuyen", typeof FB.mount === "function" && typeof FB.moSoiQuyen === "function");

// ---------------------------------------------------------------- 3. chat-card duyet_ads
const ok = C.parse(JSON.stringify({ type: "duyet_ads", id: "abc12345def" }));
check("chat-card nhận duyet_ads id hợp lệ", ok && ok.type === "duyet_ads" && ok.id === "abc12345def");
check("id quá ngắn bị từ chối", C.parse(JSON.stringify({ type: "duyet_ads", id: "abc" })) === null);
check("id chữ hoa / ký tự lạ bị từ chối", C.parse(JSON.stringify({ type: "duyet_ads", id: "ABCDEFGH1" })) === null &&
  C.parse(JSON.stringify({ type: "duyet_ads", id: 'abcdefgh"><x' })) === null &&
  C.parse(JSON.stringify({ type: "duyet_ads", id: "a".repeat(33) })) === null &&
  C.parse(JSON.stringify({ type: "duyet_ads", id: 12345678 })) === null);
const ch = C.html(ok);
check("html là khung chờ data-duyet-ads", ch === '<div class="jv-card dads" data-duyet-ads="abc12345def">Đang tải đề xuất…</div>');
check("thẻ bỏ qua nội dung model khác (title, muc)", !C.html(C.parse(JSON.stringify({ type: "duyet_ads", id: "abcdefgh", title: "HACK", muc: [1] }))).includes("HACK"));
check("loại cũ vẫn chạy (stats, buttons)", C.parse(JSON.stringify({ type: "stats", items: [{ label: "A", value: "1" }] })).type === "stats" &&
  C.parse(JSON.stringify({ type: "buttons", buttons: [{ label: "x" }] })).type === "buttons");
const ph = [];
const out = C.replaceIn('Đề xuất: <!-- JAVIS_CARD: {"type":"duyet_ads","id":"k3j9x2m1q8"} --> xong', (x) => { ph.push(x); return "@@" + (ph.length - 1) + "@@"; });
check("replaceIn đặt khung chờ", out.includes("@@0@@") && ph[0].includes('data-duyet-ads="k3j9x2m1q8"'));

// ---------------------------------------------------------------- 4. duyet-ads thẻ
const REC = {
  id: "k3j9x2m1q8", trang_thai: "cho", co_the_hoan_tac: false, ly_do: "",
  muc: [
    { id: "c1", cap: "campaign", ten: "Camp Váy " + XSS, tk_id: "act1", tk_ten: "TKQC HALIMI", fb_id: "10", fb_ten: "Hải",
      chi_hom_nay: 1250000, ngan_sach_ngay: 1500000, tu: "ACTIVE", sang: "PAUSED" },
    { id: "c2", cap: "campaign", ten: "Camp Đầm", tk_ten: "TKQC 2", fb_ten: "Mai", tu: "PAUSED", sang: "ACTIVE" },
  ],
};
const d1 = DA.htmlThe(REC, {});
check("tiêu đề: Bạn sắp đổi 2 chiến dịch", d1.includes("Bạn sắp đổi 2 chiến dịch"));
check("chip Chờ duyệt", d1.includes('dads-chip warn">Chờ duyệt'));
check("dòng tài khoản dùng Facebook", d1.includes("TKQC HALIMI · dùng tài khoản Facebook Hải"));
check("tiền hôm nay / ngân sách ngày", d1.includes("1.250.000 đ") && d1.includes("1.500.000 đ"));
check("chip từ -> sang", d1.includes('dads-chip ok">Đang chạy') && d1.includes('dads-chip bad">Tắt') &&
  d1.includes('dads-chip bad">Đang tắt') && d1.includes('dads-chip ok">Bật'));
check("ghi chú chưa đổi gì", d1.includes("MinMin chỉ đổi sau khi bạn bấm Duyệt."));
check("3 nút Duyệt/Sửa lại/Từ chối", d1.includes('class="dads-nut-chinh" data-dads-act="duyet">Duyệt') &&
  d1.includes('data-dads-act="sua">Sửa lại') && d1.includes('data-dads-act="tu_choi">Từ chối') && !d1.includes("hoan_tac"));
check("thẻ escape", !d1.includes(XSS) && d1.includes("&lt;img"));
check("đang gửi -> nút khoá", (DA.htmlThe(REC, { gui: "duyet" }).match(/ disabled/g) || []).length === 3);
check("tiêu đề theo cấp: nhóm / quảng cáo / trộn", DA.tieuDe({ muc: [{ cap: "adset" }] }) === "Bạn sắp đổi 1 nhóm quảng cáo" &&
  DA.tieuDe({ muc: [{ cap: "ad" }, { cap: "ad" }] }) === "Bạn sắp đổi 2 quảng cáo" &&
  DA.tieuDe({ muc: [{ cap: "campaign" }, { cap: "ad" }] }) === "Bạn sắp đổi 2 đối tượng");
const XONG = Object.assign({}, REC, { trang_thai: "xong", co_the_hoan_tac: true,
  ket_qua: [{ id: "c1", ok: true, trang_thai_moi: "PAUSED", loi: "" }, { id: "c2", ok: false, trang_thai_moi: "", loi: "Hết quyền " + XSS }] });
const d2 = DA.htmlThe(XONG, {});
check("xong: Đã đổi 1/2 + chip Xong", d2.includes("Đã đổi 1/2") && d2.includes('dads-chip ok">Xong'));
check("xong: dòng kết quả từng mục", d2.includes("Đã đổi, Facebook báo: Đang tắt") && d2.includes("Chưa đổi được: Hết quyền &lt;img"));
check("xong + co_the_hoan_tac: chỉ nút Hoàn tác", d2.includes('data-dads-act="hoan_tac">Hoàn tác') && !d2.includes('data-dads-act="duyet"'));
check("xong không hoàn tác được: không nút", !DA.htmlThe(Object.assign({}, XONG, { co_the_hoan_tac: false }), {}).includes("data-dads-act"));
check("chip Từ chối/Hết hạn/Lỗi = bad", ["tu_choi", "het_han", "loi"].every((x) => DA.chipTrangThai(x).cls === "bad") &&
  DA.chipTrangThai("het_han").chu === "Hết hạn");
check("chưa có bản ghi: Đang tải / lỗi", DA.htmlThe(null, {}).includes("Đang tải đề xuất") && DA.htmlThe(null, { loi: "404" }).includes("404"));
check("bản ghi bọc {de_xuat} vẫn đọc", DA.laBanGhi({ ok: true, de_xuat: REC }) === REC && DA.laBanGhi({ ok: true }) === null);
check("POST /meta-ads/duyet/<id> form hanh_dong", SRC_DA.includes('"/meta-ads/duyet/" + encodeURIComponent(id), { method: "POST"') &&
  SRC_DA.includes('body.append("hanh_dong", hanh)'));
check("Sửa lại điền chat", SRC_DA.includes('hanh === "sua"') && SRC_DA.includes("JavisSend") && SRC_DA.includes('getElementById("chatInput")'));
check("MutationObserver + quét đầu", SRC_DA.includes("new MutationObserver") && SRC_DA.includes("quet(document.body)"));
check("id kiểm lại phía client", DA.ID_RE.test("k3j9x2m1q8") && !DA.ID_RE.test("K3J9X2M1Q8"));

// ---------------------------------------------------------------- 5. i18n + CSS
for (const [ten, src] of [["fb-tai-san.js", SRC_FB], ["duyet-ads.js", SRC_DA]]) {
  const khoa = [...src.matchAll(/\bt\(\s*"([a-z0-9_.]+)"/g)].map((m) => m[1]);
  const thieu = khoa.filter((k) => !(k in VI) || !(k in EN));
  check("mọi khoá t() trong " + ten + " có ở vi.json và en.json", khoa.length > 20 && thieu.length === 0, thieu.join(", "));
  check("không ghép khoá i18n động trong " + ten, !/\bt\("(fbts|dads)\.[a-z_]*" \+/.test(src) && !/\bt\(k\)/.test(src));
  check("không em dash trong " + ten, !src.includes("—"));
}
const thieuEn = Object.keys(VI).filter((k) => /^(fbts|dads)\./.test(k) && !(k in EN));
check("mọi khoá fbts./dads. của vi có ở en", thieuEn.length === 0, thieuEn.join(", "));
check("không em dash trong chuỗi fbts/dads", Object.keys(VI).filter((k) => /^(fbts|dads)\./.test(k)).every((k) => !(VI[k] + EN[k]).includes("—")));

const TOK = read("dashboard/surface-tokens.css");
const tachPhay = (x) => { const o = []; let d = 0, cur = ""; for (const c of x) { if (c === "(") d++; if (c === ")") d--; if (c === "," && !d) { o.push(cur); cur = ""; } else cur += c; } o.push(cur); return o.map((y) => y.trim()); };
for (const [ten, tien] of [["fb-tai-san.css", /^(\.fbts|:root|:is\(\.fbts)/], ["duyet-ads.css", /^(\.dads|\.jv-card\.dads|:root)/]]) {
  const raw = read("dashboard/" + ten);
  const css = raw.replace(/\/\*[\s\S]*?\*\//g, "");
  check(ten + ": không mã màu hex", !/#[0-9a-f]{3,8}\b/i.test(css), (css.match(/#[0-9a-f]{3,8}\b/gi) || []).join(","));
  check(ten + ": không rgb()/hsl() tự gõ", !/\b(rgba?|hsla?)\(/i.test(css));
  const fsBad = [...css.matchAll(/(?<![\w-])font-size\s*:\s*([^;}]*)/gi)]
    .filter((m) => [...m[1].matchAll(/(?<![\w.#-])(\d*\.?\d+)px\b/g)].some((n) => +n[1] >= 10 && +n[1] < 30));
  check(ten + ": không font-size px trong 10-29", fsBad.length === 0, fsBad.map((m) => m[0]).join(" | "));
  const rBad = [...css.matchAll(/(?<![\w-])(border(?:-[a-z]+)*-radius)\s*:\s*([^;}]*)/gi)]
    .filter((m) => [...m[2].matchAll(/(?<![\w.#-])(\d*\.?\d+)px\b/g)].some((n) => +n[1] >= 5));
  check(ten + ": không bo góc px >= 5", rBad.length === 0, rBad.map((m) => m[0]).join(" | "));
  const refs = [...css.matchAll(/var\(\s*(--mm-[A-Za-z0-9_-]+)/g)].map((m) => m[1]);
  const la = [...new Set(refs.filter((r) => !TOK.includes(r + ":")))];
  check(ten + ": mọi var(--mm-*) là token có thật", refs.length > 30 && la.length === 0, la.join(", "));
  const vars = [...css.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)/g)].map((m) => m[1]).filter((v) => !v.startsWith("--mm-"));
  check(ten + ": chỉ dùng biến --mm-*", vars.length === 0, vars.join(", "));
  const sel = [...css.matchAll(/(^|\})\s*([^{}@]+)\{/g)].flatMap((m) => tachPhay(m[2].trim()));
  const selLa = sel.filter((x) => !tien.test(x));
  check(ten + ": mọi selector có tiền tố riêng", sel.length > 15 && selLa.length === 0, selLa.join(" | "));
  check(ten + ": tông tối viền, tông sáng gỡ viền", css.includes("border: 1px solid var(--mm-line)") && /:root\[data-theme="light"\][^{]*\{ border: 0; \}/.test(css));
  check(ten + ": nút 44px trên điện thoại", /@media \(max-width: 900px\)[\s\S]*min-height: 44px/.test(css));
  check(ten + ": không em dash", !raw.includes("—"));
}
const fcss = read("dashboard/fb-tai-san.css");
check("hộp phủ dùng --mm-scrim", /\.fbts-phu-man \{[^}]*background: var\(--mm-scrim\)/.test(fcss));
check("bảng cuộn ngang trong hộp lõm", /\.fbts-bang-hop \{[^}]*overflow-x: auto[^}]*box-shadow: var\(--mm-in-sm\)/.test(fcss));

console.log("");
if (fails.length) { console.log("FAIL " + fails.length + " mục"); process.exit(1); }
console.log("Tất cả xanh.");
