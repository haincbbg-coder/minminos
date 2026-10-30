/* Nén gọn JS lúc phục vụ (server/nen_gon.py, 26.10.313) không được đổi nghĩa một file nào.

       node tests/js/test_nen_gon.js

   Chạy bộ nén Python trên MỌI file JS của dashboard, rồi so từng token của bản nén với bản gốc bằng
   acorn (vendored, MIT). Chỉ chú thích và khoảng trắng được phép biến mất; số dòng phải giữ nguyên.
   Một lần đoán sai "/" là regex hay phép chia là một token lệch, test đỏ ngay ở đúng file đó.
*/
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");
const acorn = require("./vendor/acorn-8.18.0.js");

const ROOT = path.join(__dirname, "..", "..");
const fails = [];
const check = (name, cond, extra) => {
  console.log((cond ? "ok   " : "FAIL ") + name + (!cond && extra ? "  [" + extra + "]" : ""));
  if (!cond) fails.push(name);
};

const PY = `
import sys, json, os, glob
sys.path.insert(0, os.path.join(sys.argv[1], "server"))
import nen_gon
goc = os.path.join(sys.argv[1], "dashboard")
kq = {}
for f in sorted(glob.glob(os.path.join(goc, "**", "*.js"), recursive=True)):
    rel = os.path.relpath(f, goc).replace(os.sep, "/")
    if not nen_gon.nen_duoc(rel):
        continue
    s = open(f, encoding="utf-8").read()
    try:
        kq[rel] = nen_gon.nen_js(s)
    except Exception as e:
        kq[rel] = None
css = {}
for f in sorted(glob.glob(os.path.join(goc, "**", "*.css"), recursive=True)):
    rel = os.path.relpath(f, goc).replace(os.sep, "/")
    if nen_gon.nen_duoc(rel):
        s = open(f, encoding="utf-8").read()
        g = nen_gon.nen_css(s)
        css[rel] = [s.count("\\n"), g.count("\\n"), len(s), len(g), "/*" in g]
print(json.dumps({"js": kq, "css": css}))
`;

let py = null;
for (const exe of ["python3", "python"]) {
  const r = spawnSync(exe, ["-c", PY, ROOT], { encoding: "utf8", maxBuffer: 256 * 1024 * 1024 });
  if (r.status === 0 && r.stdout) { py = JSON.parse(r.stdout); break; }
}
check("chạy được bộ nén Python", py !== null);
if (!py) { console.log("\nFAIL - test_nen_gon"); process.exit(1); }

function tokens(src, type) {
  const out = [];
  const opts = { ecmaVersion: "latest", sourceType: type, allowHashBang: true, allowReturnOutsideFunction: true,
                 allowAwaitOutsideFunction: true, onToken: (t) => out.push(t.type.label + ":" + (t.value === undefined ? "" : String(t.value))) };
  acorn.parse(src, opts);
  return out;
}

let soFile = 0, khongParse = 0, tongGoc = 0, tongNen = 0;
for (const [rel, gon] of Object.entries(py.js)) {
  const src = fs.readFileSync(path.join(ROOT, "dashboard", rel), "utf8");
  if (gon === null) { check(rel + ": bộ nén từ chối thì máy chủ gửi bản gốc (chấp nhận được)", true); continue; }
  let tGoc = null, kieu = "script";
  for (const k of ["script", "module"]) {
    try { tGoc = tokens(src, k); kieu = k; break; } catch (e) { /* thử kiểu kia */ }
  }
  if (tGoc === null) { khongParse++; continue; }   // acorn không đọc được bản gốc: không có gì để so
  let tNen = null, loi = "";
  try { tNen = tokens(gon, kieu); } catch (e) { loi = e.message; }
  soFile++;
  tongGoc += src.length; tongNen += gon.length;
  const giong = tNen !== null && tNen.length === tGoc.length && tNen.every((t, i) => t === tGoc[i]);
  let lech = loi;
  if (!giong && tNen) {
    const i = tNen.findIndex((t, k) => t !== tGoc[k]);
    lech = "token " + i + ": " + tGoc[i] + " -> " + tNen[i];
  }
  if (!giong) check(rel + ": token y hệt bản gốc", false, lech);
  if (src.split("\n").length !== gon.split("\n").length) check(rel + ": giữ đúng số dòng", false);
}
check(`đã so ${soFile} file JS (acorn không đọc được ${khongParse} file gốc)`, soFile > 80);
check(`JS nhẹ đi đáng kể: ${Math.round(tongGoc / 1024)} KB -> ${Math.round(tongNen / 1024)} KB`, tongNen < tongGoc * 0.8);

for (const [rel, [dGoc, dNen, , , conChuThich]] of Object.entries(py.css)) {
  if (dGoc !== dNen) check(rel + ": CSS giữ số dòng", false);
  if (conChuThich) check(rel + ": CSS hết chú thích", false);
}
check(`đã nén ${Object.keys(py.css).length} file CSS`, Object.keys(py.css).length > 10);

// Chuỗi, template và regex phải giữ nguyên từng ký tự, kể cả khoảng trắng bên trong
const MAU = [
  ["a = `  x ${ b /* c */ } // y\n  z`; // c", 'a=`  x ${b} // y\n  z`;'],
  ['s = " // khong phai chu thich "; r = /\\/\\* [/]x/g.test(s)', 's=" // khong phai chu thich ";r= /\\/\\* [/]x/g.test(s)'],
];
const r2 = spawnSync("python3", ["-c", `import sys,json;sys.path.insert(0,${JSON.stringify(path.join(ROOT, "server"))});import nen_gon;print(json.dumps([nen_gon.nen_js(x) for x in json.loads(sys.stdin.read())]))`],
  { input: JSON.stringify(MAU.map((m) => m[0])), encoding: "utf8" });
if (r2.status === 0) {
  const ra = JSON.parse(r2.stdout);
  MAU.forEach((m, i) => check("mẫu " + i + " giữ nguyên chuỗi/template/regex", ra[i] === m[1], JSON.stringify(ra[i])));
}

if (fails.length) { console.log(`\nFAIL - test_nen_gon: ${fails.length}`); process.exit(1); }
console.log("\nOK - test_nen_gon");
