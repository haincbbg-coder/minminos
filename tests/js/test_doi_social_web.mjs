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

// api không ném lỗi khi máy chủ lỗi / mất mạng
const loi = await Promise.all([
  (ctx.fetch = () => Promise.resolve({ ok: false, status: 400, text: () => Promise.resolve('{"ok":false,"error":"sai"}') }), DS.api("GET", "/x", null, { quiet: true })),
]);
check("api trả {ok:false,error} khi 4xx", loi[0].ok === false && loi[0].error === "sai");
ctx.fetch = () => Promise.reject(new Error("mất mạng"));
const mat = await DS.api("GET", "/x", null, { quiet: true });
check("api không ném khi mất mạng", mat.ok === false && mat.status === 0);

if (fails.length) { console.log("\n" + fails.length + " FAIL"); process.exit(1); }
console.log("\nTất cả đều ok");
