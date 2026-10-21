// Kiểm trang web Đội Social (apps/doi-social/web): cú pháp, đủ màn hình theo hash route, phá cache,
// không em dash, không tải gì từ mạng ngoài, vài hàm tiện ích. Không cần mạng, không cần trình duyệt.
// Chạy: node tests/js/test_doi_social_web.mjs
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB = path.join(__dirname, "../../apps/doi-social/web");
const fails = [];
const check = (name, cond) => { console.log((cond ? "ok   " : "FAIL ") + name); if (!cond) fails.push(name); };

const html = fs.readFileSync(path.join(WEB, "index.html"), "utf8");
const scripts = [...html.matchAll(/<script src="([^"?]+)\?v=([^"]+)"/g)].map((m) => ({ src: m[1], v: m[2] }));
check("index.html nạp app.js và các màn", scripts.length >= 13 && scripts[0].src === "app.js");
check("mọi script có ?v=26.10.187", scripts.every((s) => s.v === "26.10.187"));
check("stylesheet có ?v=26.10.187", /href="styles\.css\?v=26\.10\.187"/.test(html));
check("không script/link ngoài", !/(src|href)="https?:\/\//.test(html));

const tenHop = /^[a-z0-9][a-z0-9._-]*\.(html|js|css|svg|png|webp|json)$/;
const tatCa = [];
for (const f of fs.readdirSync(WEB)) {
  const p = path.join(WEB, f);
  if (fs.statSync(p).isDirectory()) for (const g of fs.readdirSync(p)) tatCa.push(f + "/" + g);
  else tatCa.push(f);
}
check("tên tệp đúng mẫu máy chủ phục vụ", tatCa.every((f) => f.split("/").every((x, i, a) => (i < a.length - 1 ? /^[a-z0-9][a-z0-9._-]*$/.test(x) : tenHop.test(x)))));
check("mọi script trong index tồn tại", scripts.every((s) => fs.existsSync(path.join(WEB, s.src))));

let emDash = [], ngoai = [];
for (const f of tatCa) {
  const s = fs.readFileSync(path.join(WEB, f), "utf8");
  if (s.includes("—")) emDash.push(f);
  if (/https?:\/\/(cdn|unpkg|fonts\.googleapis|cdnjs)/.test(s)) ngoai.push(f);
}
check("không em dash (U+2014): " + emDash.join(","), !emDash.length);
check("không CDN / font ngoài: " + ngoai.join(","), !ngoai.length);

// ---- nạp mã trong vm với DOM tối thiểu
const el = () => ({ addEventListener() {}, classList: { add() {}, remove() {}, toggle() {} }, setAttribute() {}, removeAttribute() {},
  querySelector: () => null, querySelectorAll: () => [], appendChild() {}, innerHTML: "", textContent: "", hidden: false, style: {} });
const ctx = {
  console, setTimeout, clearTimeout, setInterval, clearInterval, URLSearchParams, Promise, JSON, Math, Date,
  location: { hash: "#/tong-quan", origin: "http://x" }, history: { replaceState() {} },
  localStorage: { getItem: () => null, setItem() {} },
  fetch: () => Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('{"ok":true}') }),
  document: { addEventListener() {}, getElementById: () => el(), querySelector: () => null, querySelectorAll: () => [], documentElement: el(),
    createElement: () => el(), body: el(), hidden: false, title: "" },
  navigator: {},
};
ctx.window = ctx;
vm.createContext(ctx);
let napLoi = "";
for (const s of scripts) {
  try { vm.runInContext(fs.readFileSync(path.join(WEB, s.src), "utf8"), ctx, { filename: s.src }); }
  catch (e) { napLoi += s.src + ": " + e.message + "; "; }
}
check("mọi script chạy được " + napLoi, !napLoi);
const DS = ctx.DS;
const ROUTE = ["tong-quan", "automation", "chay-hang-loat", "nhat-ky", "kho", "nhom-fb", "duyet", "tin-nhan", "tro-ly", "kien-thuc", "tai-khoan", "gioi-han", "may"];
check("đủ 13 màn theo mục 5", ROUTE.every((r) => DS.views[r] && typeof DS.views[r].render === "function"));
// 26.10.202: phần Fanpage dùng chung nằm ở DS.fp, KHÔNG có biến toàn cục FP. Màn ngoài fp-* muốn dùng
// phải tự lấy "var FP = DS.fp" (lỗi thật: Viết bài AI rơi về chế độ nick vì gọi FP không tồn tại).
{
  const ngoaiFp = fs.readdirSync(path.join(WEB, "views")).filter((f) => f.endsWith(".js") && !f.startsWith("fp-"));
  const sai = ngoaiFp.filter((f) => { const s = fs.readFileSync(path.join(WEB, "views", f), "utf8"); return /\bFP\./.test(s) && !/var FP = DS\.fp/.test(s); });
  check("màn ngoài fp-* dùng FP thì lấy từ DS.fp: " + sai.join(","), !sai.length);
  check("không có biến toàn cục FP (đúng là DS.fp)", typeof ctx.FP === "undefined" && !!DS.fp);
}
check("thanh bên trỏ đúng route", ROUTE.filter((r) => r !== "chay-hang-loat").every((r) => html.includes(`href="#/${r}"`)));

ctx.location.hash = "#/kien-thuc/12?tab=hoi-dap";
const r = DS.route();
check("route tách base/arg/q", r.base === "kien-thuc" && r.arg === "12" && r.q.tab === "hoi-dap");
ctx.location.hash = "";
check("route mặc định là tổng quan", DS.route().base === "tong-quan");
check("taoCron hằng ngày", DS.taoCron("ngay", { gio: "08:15" }) === "15 8 * * *");
check("taoCron mỗi N giờ", DS.taoCron("gio", { n: 3 }) === "0 */3 * * *");
check("moTaCron đọc lại", DS.moTaCron("15 8 * * *") === "Hằng ngày lúc 08:15" && DS.moTaCron("0 */2 * * *") === "Mỗi 2 giờ");
check("qs bỏ giá trị rỗng", DS.qs({ a: 1, b: "", c: null, d: "x y" }) === "?a=1&d=x%20y");
check("esc chống chèn HTML", DS.esc('<a "x">') === "&lt;a &quot;x&quot;&gt;");
check("list đọc khoá muc", DS.list({ ok: true, muc: [1, 2] }).length === 2 && DS.list({ _list: [1] }).length === 1);
check("tuongDoi tương lai", /nữa$/.test(DS.tuongDoi(Date.now() / 1000 + 8 * 3600)));
check("việc bỏ vì hết hạn mức hiện Bỏ qua", DS.ttViec({ trang_thai: "bo", ket_qua: { bo_qua: 1 } }).includes("Bỏ qua"));

// điều khiển từng việc: nhãn trạng thái + nút trên dòng
check("tam_dung hiện Tạm dừng", DS.ttViec({ trang_thai: "tam_dung" }).includes("Tạm dừng"));
check("đang chạy + lệnh tạm dừng hiện Đang tạm dừng", DS.ttViec({ trang_thai: "dang_chay", lenh: "tam_dung" }).includes("Đang tạm dừng"));
check("đang chạy + lệnh huỷ hiện Đang huỷ", DS.ttViec({ trang_thai: "dang_chay", lenh: "huy" }).includes("Đang huỷ"));
const nut = (v) => DS.nutViec(v);
check("việc chờ có nút Tạm dừng + Huỷ", /data-hd="tam_dung"/.test(nut({ id: 1, trang_thai: "cho_chay" })) && /data-hd="huy"/.test(nut({ id: 1, trang_thai: "cho_chay" })));
check("việc tạm dừng có nút Tiếp tục + Huỷ", /data-hd="tiep_tuc"/.test(nut({ id: 1, trang_thai: "tam_dung" })) && !/data-hd="tam_dung"/.test(nut({ id: 1, trang_thai: "tam_dung" })));
check("đang chạy bị lệnh tạm dừng có nút Tiếp tục", /data-hd="tiep_tuc"/.test(nut({ id: 1, trang_thai: "dang_chay", lenh: "tam_dung" })));
check("việc đã kết thúc không có nút", ["xong", "loi", "bo"].every((t) => nut({ id: 1, trang_thai: t }) === "") && nut({ id: 1, trang_thai: "dang_chay", lenh: "huy" }) === "");
// nơi đăng đã quét
const nk = { id: "p1", ten: "A", dich_den: [{ nen_tang: "facebook", loai: "trang", ten: "Shop X", link: "https://facebook.com/x", cap_nhat: 100 },
  { nen_tang: "facebook", loai: "ca_nhan", ten: "A", link: "https://facebook.com/a", cap_nhat: 120 }, { nen_tang: "instagram", loai: "tai_khoan", ten: "shopx", link: "https://instagram.com/shopx", cap_nhat: 90 }] };
check("đếm Trang Facebook bỏ tường cá nhân", DS.trangFB(nk).length === 1 && DS.quetLuc(nk) === 120);
check("chip nơi đăng có số Trang và @tài khoản", /1 Trang/.test(DS.chipDichDen(nk)) && /@shopx/.test(DS.chipDichDen(nk)));
check("nick chưa quét hiện chữ chưa quét", /chưa quét/.test(DS.chipDichDen({ id: "p2", dich_den: [] })) && DS.chipDichDen({ id: "p2" }, true) === "");

// api không ném lỗi khi máy chủ lỗi / mất mạng
const loi = await Promise.all([
  (ctx.fetch = () => Promise.resolve({ ok: false, status: 400, text: () => Promise.resolve('{"ok":false,"error":"sai"}') }), DS.api("GET", "/x", null, { quiet: true })),
]);
check("api trả {ok:false,error} khi 4xx", loi[0].ok === false && loi[0].error === "sai");
ctx.fetch = () => Promise.reject(new Error("mất mạng"));
const mat = await DS.api("GET", "/x", null, { quiet: true });
check("api không ném khi mất mạng", mat.ok === false && mat.status === 0);

// ---- Fanpage (API) 26.10.194: docs/doi-social/FANPAGE.md mục 9
const FP_ROUTE = ["fp-tong-quan", "fp-trang", "fp-bai", "fp-kho", "fp-binh-luan", "fp-kenh", "fp-bao-cao", "fp-canh-bao"];
check("đủ 8 màn Fanpage đăng ký", FP_ROUTE.every((r) => DS.views[r] && typeof DS.views[r].render === "function" && DS.views[r].title));
check("thanh bên có nhóm Fanpage (API) trỏ đúng route", html.includes('data-g="fanpage"') && html.includes("Fanpage (API)") && FP_ROUTE.every((r) => html.includes(`href="#/${r}"`) && html.includes(`data-nav="${r}"`)));
const iChung = scripts.findIndex((s) => s.src === "views/fp-chung.js");
check("fp-chung.js nạp trước mọi màn fp-*", iChung > 0 && scripts.every((s, i) => !/^views\/fp-(?!chung)/.test(s.src) || i > iChung));
check("index nạp đủ tệp fp-*", FP_ROUTE.every((r) => scripts.some((s) => s.src === `views/${r}.js`)));
const FP = DS.fp;
check("DS.fp có sẵn", !!FP && typeof FP.api === "function" && typeof FP.formCauHinh === "function");
check("tachGio chuẩn hoá và sắp xếp", JSON.stringify(FP.tachGio("18h, 9:00 12:30;25:00 9:00")) === JSON.stringify(["09:00", "12:30", "18:00"]));
check("tachMuc: mỗi dòng một mục", FP.tachMuc("a\n\n b \nc").length === 3);
check("tachMuc: dòng --- tách mục nhiều dòng", JSON.stringify(FP.tachMuc("x\ny\n---\nz")) === JSON.stringify(["x\ny", "z"]));
check("ghepMuc rồi tachMuc giữ nguyên", JSON.stringify(FP.tachMuc(FP.ghepMuc(["a\nb", "c"]))) === JSON.stringify(["a\nb", "c"]) && FP.ghepMuc(["a", "b"]) === "a\nb");
check("gop: null ở Trang = theo nhóm", FP.gop({ lich: { che_do: "gio", gio: ["09:00"] }, story: true }, { lich: { cach: "fb" }, story: null }).story === true &&
  FP.gop({ lich: { che_do: "gio" } }, { lich: { cach: "fb" } }).lich.che_do === "gio");
check("moTaLich đọc 3 chế độ", FP.moTaLich({ che_do: "gio", gio: ["09:00", "18:00"] }) === "09:00, 18:00" && /^Mỗi 4h, 08:00-22:00/.test(FP.moTaLich({ che_do: "chu_ky", moi_gio: 4, tu: "08:00", den: "22:00" })) &&
  FP.moTaLich({ che_do: "tat" }) === "Không tự xếp lịch" && /hẹn trên FB/.test(FP.moTaLich({ gio: ["09:00"], cach: "fb" })));
const t0 = Math.floor(new Date(2026, 9, 21, 9, 30).getTime() / 1000);
check("dtLocal <-> tuDt", FP.dtLocal(t0) === "2026-10-21T09:30" && FP.tuDt(FP.dtLocal(t0)) === t0 && FP.tuDt("") === null);
check("ttBai có trạng thái phụ bình luận/story/IG", /Chờ duyệt/.test(FP.ttBai({ trang_thai: "cho_duyet" })) && /Bình luận lỗi/.test(FP.ttBai({ trang_thai: "da_dang", bl_tt: "loi" })) && /IG xong/.test(FP.ttBai({ trang_thai: "da_dang", ig_tt: "xong" })));
const fch = FP.formCauHinh({}, [{ id: 1, ten: "K", loai: "noi_dung", so: 3 }]);
check("form cấu hình đủ mục theo hợp đồng", ["che_do", "gio", "moi_gio", "tu", "den", "lech_phut", "trai_phut", "cach", "kho_noi_dung", "kho_binh_luan", "kho_tieu_su",
  "binh_luan_sau_dang", "story", "ig_dong_bo", "tu_an", "tu_tra_loi", "chia_video", "duyet_truoc"].every((k) => fch.includes(`"${k}"`)) && fch.includes("Xem trước giờ đăng"));
check("tắt duyệt trước có lời giải thích vào thẳng hàng chờ", /vào thẳng hàng chờ đăng/.test(fch));
check("spark vẽ đường SVG", /<path class="ln" d="M/.test(FP.spark([1, 3, 2])) && /<svg/.test(FP.spark([])));
check("thumbs dẫn tới /doi-social/fp/media/", FP.thumbs(["a b.jpg", { tep: "c.mp4", loai: "video" }]).includes("/doi-social/fp/media/a%20b.jpg") && FP.laVideo({ loai: "video" }));
const src = (f) => fs.readFileSync(path.join(WEB, "views", f), "utf8");
check("đăng ngay phải xác nhận + cảnh báo công khai", /xacNhan\("Đăng ngay/.test(src("fp-bai.js")) && /CANH_BAO_CONG_KHAI/.test(src("fp-bai.js")));
check("Tạo bài hàng loạt có Xem trước (chay_thu) và nhãn chờ duyệt", /chay_thu/.test(src("fp-bai.js")) && /\(chờ duyệt\)/.test(src("fp-bai.js")));
check("quy tắc Tự gửi mặc định tắt và hỏi lại khi bật", /DS\.sw\('id="qt-gui"', !!q\.tu_gui\)/.test(src("fp-binh-luan.js")) && /Bật Tự gửi\?/.test(src("fp-binh-luan.js")));
check("nút Dừng mọi tự động gọi /tu-dong và ghi rõ bài hẹn FB không rút được", /"\/tu-dong"/.test(src("fp-chung.js")) && /không rút được/.test(src("fp-chung.js")));
check("đổi thông tin Trang có cảnh báo công khai", (src("fp-trang.js").match(/note-warn/g) || []).length >= 2);
check("Tới chỗ sửa chỉ nhận đường dẫn trong app", /toiAnToan/.test(src("fp-canh-bao.js")));

// chạy thử render từng màn Fanpage với DOM giả + dữ liệu đúng hình hợp đồng mục 8
const fake = () => {
  const o = { innerHTML: "", textContent: "", value: "", checked: false, hidden: false, disabled: false, files: [], style: {}, children: [], clientWidth: 640, isConnected: true,
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false }, addEventListener() {}, removeEventListener() {}, setAttribute() {}, removeAttribute() {},
    getAttribute: () => null, hasAttribute: () => false, appendChild() {}, removeChild() {}, closest: () => null, contains: () => false, matches: () => false, focus() {}, click() {}, scrollIntoView() {} };
  const con = {};
  o.querySelector = (sel) => con[sel] || (con[sel] = fake()); o.querySelectorAll = () => []; o.parentNode = o; o._con = con;
  return o;
};
const gom = (o) => o.innerHTML + Object.values(o._con || {}).map(gom).join("");
const T = 1761000000;
const trang = { id: "111", ten: "Trang A", anh: "", link: "https://facebook.com/111", nhom_id: 1, nhom_ten: "N1", cau_hinh: {}, cau_hinh_hieu_luc: { lich: { che_do: "gio", gio: ["09:00"] }, kho_noi_dung: 5, story: true },
  nguon_cau_hinh: "nhom", so_token: 1, quyen: ["CREATE_CONTENT"], nguoi_theo_doi: 10, bat: 1, dem: { da_dang: 2, cho: 1, loi: 0 }, bai_ke: T, ig_id: "9" };
const bai = { id: 7, trang_id: "111", trang_ten: "Trang A", loai: "anh", noi_dung: "x", media: ["1.jpg"], trang_thai: "cho_duyet", hen_luc: T, cach_hen: "fb", bl_tt: "cho", so_lieu: { reactions: 1 }, tao_luc: T };
const MAU = [
  [/\/fp\/tong-quan/, { trang: { tong: 1, co_lich: 1, loi: 0 }, bai: { tong: 3, da_dang: 2, cho_duyet: 1, cho_dang: 0, da_hen_fb: 0, loi: 0 }, nguoi_theo_doi: 10, tiep_can_7: 5, tuong_tac_7: 2,
    xu_huong: [{ ngay: "2026-10-20", da_dang: 1, tiep_can: 3 }, { ngay: "2026-10-21", da_dang: 2, tiep_can: 4 }], top_trang: [trang], hoat_dong: [{ luc: T, loai: "dang", ket_qua: "ok", chi_tiet: "đã đăng" }],
    canh_bao: { chan: 1, nang: 0, nhac: 2 }, ig: { tai_khoan: 1, da_dang_24h: 0 }, nguon_token: 1, dung_tu_dong: true }],
  [/\/fp\/trang/, { muc: [trang], nhom: [{ id: 1, ten: "N1", so: 1 }], chua_nhom: 0 }],
  [/\/fp\/nhom/, { muc: [{ id: 1, ten: "N1", mo_ta: "", cau_hinh: {}, so_trang: 1, trang: [trang] }] }],
  [/\/fp\/token/, { muc: [{ id: "kn:abc", nhan: "Kết nối", loai: "ket_noi", che: "", trang_thai: "tot", het_han: null }, { id: 2, nhan: "Tay", loai: "nguoi_dung", che: "EAABxx…9z", trang_thai: "loi", loi: "190", het_han: T }] }],
  [/\/fp\/kho/, { muc: [{ id: 5, ten: "Caption", loai: "noi_dung", che_do: "ngau_nhien", so: 4, gan: {} }, { id: 6, ten: "Link", loai: "link", che_do: "stt", so: 0, gan: { noi_dung: [5] }, mau_link: "https://x/{ten_tep}" }] }],
  [/\/fp\/bai/, { muc: [bai], tong: 1, dem: { cho_duyet: 1 } }],
  [/\/fp\/binh-luan/, { muc: [{ id: "c1", trang_id: "111", trang_ten: "Trang A", tu_ten: "Khách", noi_dung: "giá?", luc: T, trang_thai: "cho_duyet", tra_loi: "Dạ" }], tong: 1, hom_nay: { da_tra_loi: 1 }, quet_luc: T }],
  [/\/fp\/quy-tac/, { muc: [{ id: 1, ten: "Hỏi giá", pham_vi: { nhom: [1] }, tu_khoa: ["giá"], hanh_dong: "tra_loi", mau: ["Dạ"], tu_gui: 0, bat: 1 }] }],
  [/\/fp\/cai-dat/, { dung_tu_dong: false, luong: 3 }],
  [/\/fp\/kenh/, { muc: [{ id: 1, nen_tang: "youtube", link: "https://youtube.com/@a", trang_ids: ["111"], trang_ten: ["Trang A"], chia: "xoay", loai_bai: "reel", theo_doi: 1, trang_thai: "loi", loi: "x", co_yt_dlp: false }] }],
  [/\/fp\/bao-cao/, { trang: [Object.assign({ tang_24h: -2 }, trang)], bai: [Object.assign({ url: "https://facebook.com/p" }, bai)], chuoi: [{ ngay: "2026-10-20", nguoi_theo_doi: 9, tiep_can: 3, tuong_tac: 1 }, { ngay: "2026-10-21", nguoi_theo_doi: 10, tiep_can: 4, tuong_tac: 2 }] }],
  [/\/fp\/canh-bao\/lich-su/, { muc: [{ luc: T, muc: "nang", tieu_de: "Bài lỗi", het_luc: T }] }],
  [/\/fp\/canh-bao/, { muc: [{ muc: "chan", ma: "khong_token", tieu_de: "Chưa có token", cach_sua: "Thêm token", toi: "#/fp-trang?tab=token" }, { muc: "nhac", tieu_de: "x", toi: "https://evil.example" }], dem: { chan: 1, nang: 0, nhac: 1 }, kiem_luc: T }],
];
const goi = [];
ctx.fetch = (p) => { goi.push(p); const m = MAU.find((x) => x[0].test(p)); return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve(JSON.stringify(Object.assign({ ok: true }, m ? m[1] : {}))) }); };
ctx.document.createElement = () => fake();
ctx.addEventListener = ctx.removeEventListener = () => {}; ctx.innerWidth = 1280; ctx.scrollTo = () => {};
ctx.document.querySelector = () => null;
const CHAY = [["fp-tong-quan", {}], ["fp-trang", {}], ["fp-trang", { tab: "nhom" }], ["fp-trang", { tab: "token" }], ["fp-bai", {}], ["fp-kho", {}], ["fp-kho", { tab: "link" }],
  ["fp-binh-luan", {}], ["fp-binh-luan", { tab: "quy-tac" }], ["fp-kenh", {}], ["fp-bao-cao", {}], ["fp-canh-bao", {}], ["fp-canh-bao", { tab: "lich-su" }]];
let renderLoi = "";
const html1 = {};
for (const [v, q] of CHAY) {
  const e = fake(), c = { el: e, q, arg: "", alive: true, timers: [], every() {} };
  try { await DS.views[v].render(e, c); await new Promise((r) => setTimeout(r, 0)); html1[v + (q.tab || "")] = gom(e); }
  catch (x) { renderLoi += v + (q.tab ? "?tab=" + q.tab : "") + ": " + x.message + "; "; }
}
check("mọi màn Fanpage render được với dữ liệu mẫu " + renderLoi, !renderLoi);
// (huy hiệu thanh bên của app cũng gọi hoi-thoai / ban-nhap, không tính)
check("màn Fanpage chỉ gọi /doi-social/fp/...", goi.length > 10 && goi.filter((p) => !/^\/doi-social\/(hoi-thoai|ban-nhap)\?/.test(p)).every((p) => p.startsWith("/doi-social/fp/")));
const CO = { "fp-tong-quan": "Trang A", "fp-trang": "Trang A", "fp-trangnhom": "N1", "fp-trangtoken": "EAABxx", "fp-bai": "Kiểm tra", "fp-kho": "Caption", "fp-kholink": "https://x/{ten_tep}",
  "fp-binh-luan": "giá?", "fp-binh-luanquy-tac": "Hỏi giá", "fp-kenh": "yt-dlp", "fp-bao-cao": "Theo bài", "fp-canh-bao": "Thêm token", "fp-canh-baolich-su": "Bài lỗi" };
const thieu = Object.keys(CO).filter((k) => !(html1[k] || "").includes(CO[k]));
check("mỗi màn Fanpage vẽ ra dòng dữ liệu mẫu " + thieu.join(","), !thieu.length);
check("Tổng quan Fanpage hiện dải Dừng tự động khi dung_tu_dong", /Đang dừng mọi tự động/.test(html1["fp-tong-quan"] || ""));
check("Cảnh báo bỏ link Tới chỗ sửa ra ngoài app", (html1["fp-canh-bao"] || "").includes('href="#/fp-trang?tab=token"') && !(html1["fp-canh-bao"] || "").includes("evil.example"));
// thẻ Fanpage trên Tổng quan Đội Social: im lặng khi máy chủ chưa có endpoint
const fpBox = fake(); fpBox.innerHTML = "cũ";
ctx.fetch = () => Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve('{"detail":"Not Found"}') });
let tqLoi = "";
try {
  const e = fake(); e.querySelector = (s) => (s === "#tq-fp" ? fpBox : s === "#chart" ? null : fake());
  ctx.fetch = (p) => /fp\/tong-quan/.test(p) ? Promise.resolve({ ok: false, status: 404, text: () => Promise.resolve('{"detail":"Not Found"}') })
    : Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('{"ok":true,"so7":{},"may":[],"bieu_do":[],"can_xu_ly":[]}') });
  await DS.views["tong-quan"].render(e, { el: e, q: {}, alive: true, timers: [], every() {} });
  await new Promise((r) => setTimeout(r, 0));
} catch (x) { tqLoi = x.message; }
check("thẻ Fanpage ở Tổng quan im lặng khi endpoint lỗi " + tqLoi, !tqLoi && fpBox.innerHTML === "");

if (fails.length) { console.log("\n" + fails.length + " FAIL"); process.exit(1); }
console.log("\nTất cả đều ok");
