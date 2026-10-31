/* dashboard/zoom-keo.js (26.10.313): phóng to, thu nhỏ, kéo xem sơ đồ / SVG / ảnh.

       node tests/js/test_zoom_keo.js

   Chạy thật hàm phóng/kéo trên một DOM giả tối thiểu: điểm dưới con trỏ phải đứng yên khi lăn
   chuột, kéo một ngón dời đúng bằng quãng kéo, chụm hai ngón phóng theo tỉ lệ khoảng cách.
*/
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.join(__dirname, "..", "..");
const read = (f) => fs.readFileSync(path.join(ROOT, f), "utf8");
const SRC = read("dashboard/zoom-keo.js");
const fails = [];
const check = (name, cond, extra) => {
  console.log((cond ? "ok   " : "FAIL ") + name + (!cond && extra !== undefined ? "  [" + extra + "]" : ""));
  if (!cond) fails.push(name);
};

function phanTu(tag) {
  const nghe = {};
  const el = {
    tagName: tag.toUpperCase(), style: {}, children: [], isConnected: true, dataset: {},
    classList: { s: new Set(), add(c) { this.s.add(c); }, remove(c) { this.s.delete(c); }, contains(c) { return this.s.has(c); } },
    addEventListener(t, f) { (nghe[t] = nghe[t] || []).push(f); },
    phat(t, e) { (nghe[t] || []).forEach((f) => f(Object.assign({ preventDefault() {}, stopPropagation() {}, target: el }, e))); },
    appendChild(c) { this.children.push(c); c.parent = this; return c; },
    setAttribute() {}, setPointerCapture() {}, remove() {}, closest() { return null; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 400, height: 300 }; },
  };
  return el;
}

const head = phanTu("head");
const doc = { head, getElementById: () => null, createElement: phanTu };
const win = {};
const ctx = { window: win, document: doc, Math, Date, console, Object, String, Array, JSON };
vm.createContext(ctx);
vm.runInContext(SRC, ctx);

const khung = phanTu("div");
khung.clientWidth = 400; khung.clientHeight = 300;
const anh = phanTu("img");
anh.naturalWidth = 1600; anh.naturalHeight = 1200; anh.complete = true;
const z = win.MinMinZoom.gan(khung, anh);

const tf = () => {
  const m = /translate\(([-\d.e]+)px,([-\d.e]+)px\) scale\(([-\d.e]+)\)/.exec(anh.style.transform || "");
  return m ? { x: +m[1], y: +m[2], s: +m[3] } : null;
};
const gan = (a, b) => Math.abs(a - b) < 1e-6;

let t = tf();
check("mở ra: vừa khung (ảnh 1600x1200 trong khung 400x300)", t && gan(t.s, 0.25 * 0.98), JSON.stringify(t));
check("có nút +, -, Vừa khung", khung.children.length === 1 && khung.children[0].children.length === 3);
check("đã chèn CSS một lần", head.children.length === 1);

// Lăn chuột phóng quanh con trỏ: điểm (100, 80) của khung đứng yên
const truoc = tf();
const diemAnh = { x: (100 - truoc.x) / truoc.s, y: (80 - truoc.y) / truoc.s };
khung.phat("wheel", { clientX: 100, clientY: 80, deltaY: -200, deltaMode: 0, ctrlKey: false });
t = tf();
check("lăn lên thì to ra", t.s > truoc.s, t.s);
check("điểm dưới con trỏ đứng yên khi phóng",
  gan(diemAnh.x * t.s + t.x, 100) && gan(diemAnh.y * t.s + t.y, 80));

// Kéo một ngón / giữ chuột
const t0 = tf();
khung.phat("pointerdown", { pointerId: 1, pointerType: "mouse", clientX: 50, clientY: 50 });
khung.phat("pointermove", { pointerId: 1, clientX: 80, clientY: 30 });
khung.phat("pointerup", { pointerId: 1 });
t = tf();
check("kéo dời đúng quãng kéo", gan(t.x - t0.x, 30) && gan(t.y - t0.y, -20) && gan(t.s, t0.s));

// Chụm hai ngón: khoảng cách gấp đôi thì tỉ lệ gấp đôi
const t1 = tf();
khung.phat("pointerdown", { pointerId: 2, pointerType: "touch", clientX: 100, clientY: 100 });
khung.phat("pointerdown", { pointerId: 3, pointerType: "touch", clientX: 200, clientY: 100 });
khung.phat("pointermove", { pointerId: 3, clientX: 200, clientY: 100 });   // mốc đầu
khung.phat("pointermove", { pointerId: 3, clientX: 300, clientY: 100 });   // xa gấp đôi
khung.phat("pointerup", { pointerId: 2 }); khung.phat("pointerup", { pointerId: 3 });
t = tf();
check("chụm hai ngón: xa gấp đôi thì to gấp đôi", gan(t.s / t1.s, 2), t.s / t1.s);

// Trần phóng
for (let i = 0; i < 40; i++) khung.phat("wheel", { clientX: 0, clientY: 0, deltaY: -500, deltaMode: 0 });
check("không phóng quá 8 lần", tf().s <= 8 + 1e-9);
z.vua();
check("Vừa khung đưa về như lúc mở", gan(tf().s, 0.25 * 0.98));

// Đã gắn vào các khung xem
const FE = read("dashboard/file-editor.js"), CR = read("dashboard/chat-render.js"), HTML = read("dashboard/index.html");
check("ảnh trong trình sửa file phóng/kéo được", /MinMinZoom\.gan\(khung, khung\.querySelector\("img"\)\)/.test(FE));
check("sơ đồ mermaid phóng/kéo được", /MinMinZoom\.gan\(host, svg\)/.test(CR));
check("SVG hiện bằng <img> (không chạy script) và phóng/kéo được",
  CR.includes('"data:image/svg+xml;charset=utf-8," + encodeURIComponent(art.code)') && /MinMinZoom\.gan\(hop, anh\)/.test(CR));
check("zoom-keo.js nạp trước chat-render.js", HTML.indexOf("/static/zoom-keo.js") > 0
  && HTML.indexOf("/static/zoom-keo.js") < HTML.indexOf("/static/chat-render.js"));
const VI = JSON.parse(read("dashboard/i18n/vi.json")), EN = JSON.parse(read("dashboard/i18n/en.json"));
check("nhãn nút có cả vi và en", ["zoom.in", "zoom.out", "zoom.fit"].every((k) => VI[k] && EN[k]));
check("không em dash", !SRC.includes("—"));

if (fails.length) { console.log(`\nFAIL - test_zoom_keo: ${fails.length}`); process.exit(1); }
console.log("\nOK - test_zoom_keo");
