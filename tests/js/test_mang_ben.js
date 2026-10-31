/* dashboard/mang-ben.js (26.10.313): gom đọc trùng lúc mở app, thử lại việc ĐỌC khi máy chủ đang
   khởi động lại, KHÔNG BAO GIỜ thử lại việc ghi.

       node tests/js/test_mang_ben.js
*/
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.join(__dirname, "..", "..");
const SRC = fs.readFileSync(path.join(ROOT, "dashboard", "mang-ben.js"), "utf8");
const HTML = fs.readFileSync(path.join(ROOT, "dashboard", "index.html"), "utf8");
const fails = [];
const check = (name, cond, extra) => {
  console.log((cond ? "ok   " : "FAIL ") + name + (!cond && extra !== undefined ? "  [" + extra + "]" : ""));
  if (!cond) fails.push(name);
};

class Resp {
  constructor(status, body, kieu) { this.status = status; this.ok = status >= 200 && status < 300; this.body = body;
    this.headers = { get: (k) => (k === "content-type" ? kieu || "text/html" : null) }; }
  clone() { return new Resp(this.status, this.body, this.headers.get("content-type")); }
  json() { return Promise.resolve(JSON.parse(this.body)); }
}

function moi(kichBan) {
  const goi = [];
  const body = { children: [], appendChild(el) { this.children.push(el); } };
  const doc = {
    body,
    getElementById: (id) => body.children.find((e) => e.id === id) || null,
    createElement: () => ({ setAttribute() {}, style: {}, remove() { body.children = body.children.filter((x) => x !== this); } }),
  };
  const win = {
    fetch: (input, init) => { goi.push([input, (init && init.method) || "GET"]); return kichBan(input, init, goi.length); },
  };
  const ctx = { window: win, document: doc, location: { href: "http://h/", origin: "http://h" }, navigator: { onLine: true },
                URL, Promise, setTimeout: (f) => setTimeout(f, 0), console, String, Object, Array, JSON, Date, Math };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);
  return { win, goi, body };
}

(async () => {
  // 1. Gom đọc trùng đang bay
  {
    const { win, goi } = moi(() => new Promise((r) => setTimeout(() => r(new Resp(200, '{"a":1}', "application/json")), 5)));
    const kq = await Promise.all([win.fetch("/settings"), win.fetch("/settings"), win.fetch("/settings")]);
    const json = await Promise.all(kq.map((r) => r.json()));
    check("3 lần đọc /settings cùng lúc chỉ ra máy chủ 1 lần", goi.length === 1, goi.length);
    check("... và mỗi bên nhận đủ dữ liệu", json.every((j) => j.a === 1));
    await win.fetch("/settings");
    check("ngay sau đó (lúc mở app) dùng lại kết quả vừa về", goi.length === 1, goi.length);
    await win.fetch("/settings", { method: "POST", body: "{}" });
    await win.fetch("/settings");
    check("sau một lệnh GHI thì đọc lại từ máy chủ", goi.length === 3, goi.length);
    await win.fetch("/app-version", { cache: "no-store" });
    await win.fetch("/app-version", { cache: "no-store" });
    check("cache: no-store không dùng kết quả nhớ", goi.length === 5, goi.length);
  }
  // 2. Thử lại việc đọc khi máy chủ chưa lên
  {
    const { win, goi, body } = moi((u, i, n) => (n < 3 ? Promise.reject(new TypeError("Failed to fetch")) : Promise.resolve(new Resp(200, "{}"))));
    const p = win.fetch("/i18n/vi.json");
    await new Promise((r) => setTimeout(r, 1));
    check("đang thử lại thì hiện dòng báo kết nối lại", body.children.some((e) => e.id === "minmin-net-bar"));
    const r = await p;
    check("đọc được sau khi máy chủ lên lại", r.ok && goi.length === 3, goi.length);
    check("nối được thì dòng báo tự ẩn", !body.children.some((e) => e.id === "minmin-net-bar"));
  }
  {
    const { win, goi } = moi((u, i, n) => Promise.resolve(n < 2 ? new Resp(502, "<html>bad gateway</html>") : new Resp(200, "{}")));
    const r = await win.fetch("/sessions");
    check("502 của proxy (máy chủ chưa lên) thì thử lại", r.ok && goi.length === 2, goi.length);
  }
  {
    const { win, goi } = moi(() => Promise.resolve(new Resp(502, '{"error":"Zalo Forwarder phản hồi quá lâu"}', "application/json")));
    const r = await win.fetch("/zalo/x");
    check("502 do chính MinMin trả (có JSON) thì đưa ngay, không thử lại", r.status === 502 && goi.length === 1, goi.length);
  }
  // 3. Không bao giờ thử lại việc ghi
  {
    const { win, goi } = moi(() => Promise.reject(new TypeError("Failed to fetch")));
    let loi = null;
    try { await win.fetch("/chat/send", { method: "POST", body: "x" }); } catch (e) { loi = e; }
    check("lệnh ghi lỗi mạng: báo lỗi ngay, gửi đúng 1 lần", loi && goi.length === 1, goi.length);
  }
  {
    const { win, goi } = moi(() => Promise.resolve(new Resp(200, "{}")));
    await win.fetch("https://khac.example/x");
    await win.fetch("https://khac.example/x");
    check("khác nguồn: không gom", goi.length === 2);
    await win.fetch("/stream/abc");
    await win.fetch("/stream/abc");
    check("luồng stream: không gom", goi.length === 4);
  }
  // 4. Nạp sớm nhất
  const iMang = HTML.indexOf("/static/mang-ben.js");
  check("mang-ben.js nạp trước i18n và freshness", iMang > 0 && iMang < HTML.indexOf("/static/i18n/index.js") && iMang < HTML.indexOf("/static/freshness.js"));
  check("không em dash", !SRC.includes("—"));

  if (fails.length) { console.log(`\nFAIL - test_mang_ben: ${fails.length}`); process.exit(1); }
  console.log("\nOK - test_mang_ben");
})();
