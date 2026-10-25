/* Trang Tổng quan (phương án 1 "Bàn làm việc", 26.10.239).

       node tests/js/test_tong_quan.js

   Nạp dashboard/tong-quan.js trong vm với window.t thật (từ vi.json) và gọi hàm dựng HTML
   thuần `window.MinMinTongQuan._html(data)` - không cần DOM.

   Những gì file này khoá lại (hợp đồng ở plans/tong-quan/PLAN.md):
   1. Dữ liệu đủ: có tiêu đề, đủ 4 thẻ số, tiền VND dạng "45.280.000đ", nút Duyệt mang task_id.
   2. Khối "chua_noi" hiện chữ "Chưa nối" + nút đi nối, KHÔNG BAO GIỜ hiện "0đ" thay số thiếu.
   3. Cài đặt đủ thì không có thanh Hoàn tất cài đặt; thiếu thì liệt kê bước thiếu.
   4. Cần xử lý rỗng là câu trấn an, không phải lỗi.
   5. Chuỗi từ máy chủ bị escape; link javascript: bị bỏ.
   6. tong-quan.css chỉ dùng token: không mã màu, không font-size/bo góc px trong khoảng cấm.
*/
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..", "..");
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");
const VI = JSON.parse(read("dashboard/i18n/vi.json"));
const EN = JSON.parse(read("dashboard/i18n/en.json"));
const SRC = read("dashboard/tong-quan.js");
const CSS = read("dashboard/tong-quan.css");

let fails = [];
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (cond || extra === undefined ? "" : "  [" + extra + "]"));
  if (!cond) fails.push(name);
}

function t(k, b) {
  const v = VI[k];
  if (v == null) return k;
  return String(v).replace(/\{(\w+)\}/g, (m, n) => (b && b[n] != null ? String(b[n]) : m));
}
const win = { t };
vm.runInNewContext(SRC, { window: win, document: {}, console, Intl, Date, Math, String, Array, Object, isNaN, isFinite, encodeURIComponent });
const TQ = win.MinMinTongQuan;
check("export window.MinMinTongQuan.render và _html", TQ && typeof TQ.render === "function" && typeof TQ._html === "function");

// ---------------------------------------------------------------- dữ liệu đầy đủ
const DU = {
  luc: "2026-10-25T23:06:00+07:00",
  cai_dat: { buoc: [{ id: "pos", ten: "Pancake POS", xong: true, trang: "mcp" }], xong: 6, tong: 6 },
  can_xu_ly: { trang_thai: "ok", loi_nguon: [], muc: [
    { id: "kanban:t1", nguon: "kanban", muc_do: "warn", tieu_de: "Camp váy lụa chờ duyệt", mo_ta: "Đội Ads",
      nut: [{ nhan: "Duyệt", loai: "duyet_kanban", task_id: "t1" }, { nhan: "Mở", loai: "trang", trang: "kanban", task_id: "t1" }] },
    { id: "doi_social:1", nguon: "doi_social", muc_do: "bad", tieu_de: "2 nick bị checkpoint", mo_ta: "",
      nut: [{ nhan: "Mở", loai: "link", url: "/apps/doi-social/#/duyet" }] },
  ] },
  tien_vao: { trang_thai: "ok", tong: 18420000, so_gd: 11, gan_nhat: [
    { mo_ta: "CK đơn #A1032", so_tien: 2350000, luc: 1761400000 },
    { mo_ta: "CK đơn #A1029", so_tien: 1180000, luc: 1761400100 },
    { mo_ta: "CK đơn #A1020", so_tien: 500000, luc: 1761400200 },
  ] },
  chi_phi_ai: { trang_thai: "ok", usd_that: 0.42, usd_quy_doi: 3.1, luot: 57 },
  so_chinh: {
    doanh_thu: { trang_thai: "ok", hom_nay: 45280000, hom_qua: 40400000 },
    don_chot: { trang_thai: "ok", hom_nay: 62, hom_qua: 54 },
    chot_hoi_thoai: { trang_thai: "ok", ty_le: 31.0, khach: 200, sdt: 118 },
    chi_ads: { trang_thai: "ok", hom_nay: 9640000 },
  },
  theo_page: { trang_thai: "ok", dong: [{ page: "HALIMI", khach: 124, sdt: 76, don: 41, ty_le: 33.0 },
                                         { page: "MeiMei Design", khach: 76, sdt: 42, don: 21, ty_le: null }] },
};
const h = TQ._html(DU);
check("tiêu đề đếm đúng 2 việc", h.includes(t("tongquan.tieu_de", { n: 2 })));
check("dòng cập nhật có giờ HH:MM", /cập nhật \d\d:\d\d/.test(h));
check("đủ 4 thẻ số", (h.match(/tq-the-so/g) || []).length === 4);
check("doanh thu định dạng 45.280.000đ", h.includes("45.280.000đ"));
check("tiền vào +18.420.000đ", h.includes("+18.420.000đ"));
check("chi ads 9.640.000đ", h.includes("9.640.000đ"));
check("so với hôm qua doanh thu +12,1%", h.includes("+12,1% so với hôm qua"), h.match(/[^>]*so với hôm qua/g));
check("đơn chốt +8 đơn so với hôm qua", h.includes("+8 đơn so với hôm qua"));
check("tỉ lệ chốt 31% kèm 200 khách · 118 SĐT", h.includes(">31%<") && h.includes("200 khách · 118 SĐT"));
check("chi ads kèm % doanh thu", h.includes("21,3% doanh thu"));
check("chi phí AI USD dạng 0,42$ và quy đổi 3,10$", h.includes("0,42$") && h.includes("3,10$"));
check("nút Duyệt mang task_id và là nút chính", /<button type="button" class="tq-nut-chinh" data-tq="duyet" data-task="t1">Duyệt<\/button>/.test(h));
check("nút Mở kanban mang task_id", /data-tq="trang" data-trang="kanban" data-task="t1"/.test(h));
check("link nội bộ /apps/... giữ nguyên", h.includes('data-url="/apps/doi-social/#/duyet"'));
check("chấm màu theo mức độ", h.includes("tq-cham warn") && h.includes("tq-cham bad"));
check("3 giao dịch + '+ 8 giao dịch khác' + Xem hết -> biendong",
  (h.match(/CK đơn #A10/g) || []).length === 3 && h.includes(t("tongquan.so_gd_khac", { n: 8 })) && /data-trang="biendong">Xem hết/.test(h));
check("bảng theo page có HALIMI, tỉ lệ null hiện '-'", h.includes(">HALIMI<") && h.includes("<td>33%</td>") && h.includes("<td>-</td>"));
check("cài đặt đủ thì KHÔNG có thanh cài đặt", !h.includes("tq-cai-dat"));
check("không có chữ Chưa nối khi mọi khối ok", !h.includes(t("tongquan.chua_noi")));
check("tiêu đề không viết cứng 'bố'", !/\bbố\b/.test(h));

// ---------------------------------------------------------------- chưa nối
const CN = JSON.parse(JSON.stringify(DU));
CN.so_chinh.doanh_thu = { trang_thai: "chua_noi" };
CN.so_chinh.don_chot = { trang_thai: "chua_noi" };
CN.so_chinh.chi_ads = { trang_thai: "chua_noi" };
CN.tien_vao = { trang_thai: "chua_noi" };
CN.theo_page = { trang_thai: "chua_noi" };
const hc = TQ._html(CN);
const chuaNoi = (hc.match(new RegExp(t("tongquan.chua_noi"), "g")) || []).length;
check("5 khối chưa nối đều hiện chữ 'Chưa nối'", chuaNoi === 5, chuaNoi);
check("chưa nối KHÔNG hiện '0đ' giả", !/(^|[^\d.])0đ/.test(hc));
check("vẫn đủ 4 thẻ số khi chưa nối", (hc.match(/tq-the-so/g) || []).length === 4);
check("tiền vào chưa nối -> nút đi biendong", /data-trang="biendong">Đi nối/.test(hc));
check("doanh thu chưa nối -> nút đi mcp", /data-trang="mcp">Đi nối/.test(hc));
check("chi ads không tính % khi doanh thu chưa nối", !hc.includes("% doanh thu"));

// Khối lỗi: hiện câu lỗi, không phá trang.
const L = JSON.parse(JSON.stringify(DU));
L.so_chinh.doanh_thu = { trang_thai: "loi", loi: "POS hết hạn token" };
L.theo_page = null;
const hl = TQ._html(L);
check("khối lỗi hiện câu lỗi màu warn", hl.includes('<div class="tq-loi">POS hết hạn token</div>'));
check("khối null coi như lỗi, trang vẫn dựng", hl.includes("tq-page") && hl.includes(t("tongquan.loi_nguon_chung")));
check("ok nhưng thiếu số -> 'Chưa có số', không phải 0", (() => {
  const x = JSON.parse(JSON.stringify(DU)); x.so_chinh.chi_ads = { trang_thai: "ok", hom_nay: null };
  const s = TQ._html(x); return s.includes(t("tongquan.chua_co_so")) && !/(^|[^\d.])0đ/.test(s);
})());

// ---------------------------------------------------------------- cài đặt thiếu
const CD = JSON.parse(JSON.stringify(DU));
CD.cai_dat = { xong: 4, tong: 6, buoc: [
  { id: "pos", ten: "Pancake POS", xong: true, trang: "mcp" },
  { id: "telegram", ten: "Telegram", xong: false, trang: "channels" },
  { id: "biendong", ten: "Techcombank", xong: false, trang: "biendong" },
] };
const hcd = TQ._html(CD);
check("thiếu cài đặt -> có thanh, ghi 4/6", hcd.includes("tq-cai-dat") && hcd.includes("4/6"));
check("liệt kê bước còn thiếu", hcd.includes("Còn: Telegram · Techcombank") && !hcd.includes("Còn: Pancake"));
check("nút Nối tiếp đi tới bước thiếu đầu tiên", /data-trang="channels">Nối tiếp/.test(hcd));

// ---------------------------------------------------------------- rỗng + escape
const R = JSON.parse(JSON.stringify(DU));
R.can_xu_ly = { trang_thai: "ok", muc: [], loi_nguon: [] };
const hr = TQ._html(R);
check("Cần xử lý rỗng -> câu trấn an", hr.includes(t("tongquan.trong")) && hr.includes("tq-trong"));
check("0 việc -> tiêu đề 'chưa có việc nào'", hr.includes(t("tongquan.tieu_de_0")));

const X = JSON.parse(JSON.stringify(DU));
X.can_xu_ly.muc[0].tieu_de = '<script>alert(1)</script>';
X.can_xu_ly.muc[0].nut[0].task_id = 't1"><img src=x onerror=alert(1)>';
X.can_xu_ly.muc[1].nut[0].url = "javascript:alert(1)";
X.theo_page.dong[0].page = "<b>x</b>";
const hx = TQ._html(X);
check("<script> từ máy chủ bị escape", !hx.includes("<script>") && hx.includes("&lt;script&gt;"));
check("task_id độc bị escape trong thuộc tính", !hx.includes('"><img') && hx.includes("&quot;&gt;&lt;img"));
check("link javascript: bị bỏ", !hx.includes("javascript:"));
check("tên page bị escape", hx.includes("&lt;b&gt;x&lt;/b&gt;"));

// ---------------------------------------------------------------- định dạng
check("vnd(0) là '0đ' khi số thật bằng 0 (không trốn số 0 thật)", TQ._fmt.vnd(0) === "0đ");
check("vnd(null) rỗng", TQ._fmt.vnd(null) === "");
check("usd(3.4) = 3,40$", TQ._fmt.usd(3.4) === "3,40$");
check("usd(1234.5) = 1.234,50$", TQ._fmt.usd(1234.5) === "1.234,50$");

// ---------------------------------------------------------------- mã nguồn
check("không em dash trong tong-quan.js/.css", !SRC.includes("\u2014") && !CSS.includes("\u2014"));
check("fetch /tong-quan với credentials same-origin", SRC.includes('"/tong-quan?brain="') && SRC.includes('credentials: "same-origin"'));
check("kiểm el.isConnected sau await", (SRC.match(/if \(!el\.isConnected\) return;/g) || []).length >= 3);
check("Duyệt gửi FormData id/status=done/brain tới /kanban/task/move",
  SRC.includes('"/kanban/task/move"') && SRC.includes('f.append("status", "done")') && SRC.includes('f.append("brain"'));
check("link mở bằng window.open noopener", SRC.includes('window.open(u, "_blank", "noopener")'));
const khoa = [...SRC.matchAll(/\bt\(\s*"([a-z0-9_.]+)"/g)].map((m) => m[1]);
const thieu = khoa.filter((k) => !(k in VI) || !(k in EN));
check("mọi khoá t() dùng trong tong-quan.js có ở vi.json và en.json", khoa.length > 30 && thieu.length === 0, thieu.join(", "));
check("có page.tongquan.label/sub", "page.tongquan.label" in VI && "page.tongquan.sub" in EN);

// ---------------------------------------------------------------- CSS chỉ dùng token
// Cùng luật với tests/python/test_design_tokens.py.
const css = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
check("không mã màu hex", !/#[0-9a-f]{3,8}\b/i.test(css), (css.match(/#[0-9a-f]{3,8}\b/gi) || []).join(","));
check("không rgb()/hsl() tự gõ", !/\b(rgba?|hsla?)\(/i.test(css));
const fsBad = [...css.matchAll(/(?<![\w-])font-size\s*:\s*([^;}]*)/gi)]
  .filter((m) => [...m[1].matchAll(/(?<![\w.#-])(\d*\.?\d+)px\b/g)].some((n) => +n[1] >= 10 && +n[1] < 30));
check("không font-size px trong 10-29", fsBad.length === 0, fsBad.map((m) => m[0]).join(" | "));
const rBad = [...css.matchAll(/(?<![\w-])(border(?:-[a-z]+)*-radius)\s*:\s*([^;}]*)/gi)]
  .filter((m) => [...m[2].matchAll(/(?<![\w.#-])(\d*\.?\d+)px\b/g)].some((n) => +n[1] >= 5));
check("không bo góc px >= 5", rBad.length === 0, rBad.map((m) => m[0]).join(" | "));
const TOK = read("dashboard/surface-tokens.css");
const refs = [...css.matchAll(/var\(\s*(--mm-[A-Za-z0-9_-]+)/g)].map((m) => m[1]);
const lạ = [...new Set(refs.filter((r) => !TOK.includes(r + ":")))];
check("mọi var(--mm-*) là token có thật", refs.length > 30 && lạ.length === 0, lạ.join(", "));
check("tông tối có viền, tông sáng gỡ viền", css.includes("border: 1px solid var(--mm-line)") && css.includes(':root[data-theme="light"] .tq-the { border: 0; }'));
check("dưới 900px lưới 1 cột, 4 thẻ số về 2 cột", /@media \(max-width: 900px\)[\s\S]*\.tq-luoi \{ grid-template-columns: minmax\(0, 1fr\)[\s\S]*\.tq-hang-so \{ grid-template-columns: repeat\(2/.test(css));
check("bảng page cuộn ngang trong hộp", /\.tq-bang-hop \{ overflow-x: auto/.test(css));
check("nút cao tối thiểu 44px trên điện thoại", /@media \(max-width: 900px\)[\s\S]*min-height: 44px/.test(css));

console.log("");
if (fails.length) { console.log("FAIL " + fails.length + " mục"); process.exit(1); }
console.log("Tất cả xanh.");
