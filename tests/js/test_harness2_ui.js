/* Màn "Cải tiến có đối chứng" (dashboard/harness2.js, Trụ 2, 26.10.217).

       node tests/js/test_harness2_ui.js

   Phần thuần chạy dưới node; phần nối (nút ở trang Cộng sự, thẻ script, endpoint) soi mã nguồn.
   Không dùng ký tự em dash. */
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..", "..");
const vi = JSON.parse(fs.readFileSync(path.join(root, "dashboard/i18n/vi.json"), "utf8"));
const en = JSON.parse(fs.readFileSync(path.join(root, "dashboard/i18n/en.json"), "utf8"));

global.window = { t: (k, v) => (vi[k] || k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? v[x] : m)), ic: () => "" };
require(path.join(root, "dashboard", "harness2.js"));
const H = window.JavisHarness2;

const fails = [];
function check(name, cond, them) { console.log((cond ? "ok   " : "FAIL ") + name + (cond || !them ? "" : "  [" + them + "]")); if (!cond) fails.push(name); }

check("phơi JavisHarness2.mo", typeof H.mo === "function" && typeof H.dong === "function");
check("nhãn trạng thái đủ 7 loại", ["dang_chay", "xong", "loi", "dung", "da_ap_dung", "da_bo", "da_hoan_tac"]
  .every((s) => H.nhanTrangThai(s) && H.nhanTrangThai(s) !== s && !H.nhanTrangThai(s).startsWith("h2.")));
const u = H.tomTatUoc({ luot_agent: 12, phien_cai_tien: 3, phien_ngoai: 1, usd: 1.234 });
check("ước lượng k=1 x 3 đề nói rõ 12 lượt + 3 phiên + tiền", u.includes("12") && u.includes("3") && u.includes("1.23"), u);
const dd = H.dongDiem({ h2_diem_luat: { goc_tb: 0.5, ban_chon: 1 }, phu: { base1: { giao_duoc: 3, so_luot: 3, tool_loi: 1, so_khong_nguon: 0 } } });
check("dòng điểm: luật + phụ", dd.length === 2 && dd[0].includes("50") && dd[0].includes("100") && dd[1].includes("base1"), dd.join(" | "));
check("không có điểm thì không bịa dòng nào", H.dongDiem({}).length === 0);

const src = fs.readFileSync(path.join(root, "dashboard/harness2.js"), "utf8");
const ws = fs.readFileSync(path.join(root, "dashboard/workspace.js"), "utf8");
const html = fs.readFileSync(path.join(root, "dashboard/index.html"), "utf8");
const css = fs.readFileSync(path.join(root, "dashboard/console.css"), "utf8");
const routes = JSON.parse(fs.readFileSync(path.join(root, "tests/python/route_table.json"), "utf8")).map((r) => r.path);

check("harness2.js không em dash", !src.includes("—"));
check("trang Cộng sự có nút Cải tiến có đối chứng cho trợ lý", /id="wsH2"/.test(ws) && /JavisHarness2\.mo\(item/.test(ws));
const iH2 = html.indexOf("/static/harness2.js"), iWs = html.indexOf("/static/workspace.js");
check("index.html nạp harness2.js trước workspace.js", iH2 > 0 && iH2 < iWs);
const dung = [...src.matchAll(/"(\/harness\/[a-z\-]+)/g)].map((m) => m[1]);
check("mọi endpoint giao diện gọi đều có thật trên máy chủ", dung.length >= 7 && dung.every((p) => routes.includes(p)),
  dung.filter((p) => !routes.includes(p)).join(","));
check("hộp chiếm trọn màn hình ở điện thoại", /@media \(max-width: 700px\)[\s\S]*\.h2-modal \{[^}]*100dvh/.test(css));
const khoa = [...src.matchAll(/t\("(h2\.[a-z0-9_]+)"/g)].map((m) => m[1]).concat([...ws.matchAll(/t\("(h2\.[a-z0-9_]+)"/g)].map((m) => m[1]));
check("mọi khoá h2.* có trong vi.json và en.json", khoa.length > 30 && khoa.every((k) => k in vi && k in en),
  khoa.filter((k) => !(k in vi) || !(k in en)).join(","));
check("chữ tiếng Anh thật sự được dịch", Object.keys(en).filter((k) => k.startsWith("h2.")).every((k) => en[k] !== vi[k] || !/[ăđơư]/i.test(vi[k])));
check("Áp dụng và Hoàn tác đều hỏi xác nhận", /confirm\(t\("h2\.confirm_apply"\)\)/.test(src) && /confirm\(t\("h2\.confirm_undo"\)\)/.test(src));

console.log(fails.length ? "\nFAIL: " + fails.join(", ") : "\nALL OK");
process.exit(fails.length ? 1 : 0);
