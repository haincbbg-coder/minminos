// Đọc CSS của dashboard với token design system (26.10.238) đã thay bằng số px thật.
// Test cũ soi số kiểu `font-size: 16px`; sau khi CSS chuyển sang `var(--mm-fs-16)` thì giá trị
// vẫn y nguyên, chỉ cách viết đổi. Hàm này giữ cho các test đó kiểm GIÁ TRỊ chứ không kiểm chữ.
const fs = require("fs");
const path = require("path");

const SURFACE = fs.readFileSync(path.join(__dirname, "../../dashboard/surface-tokens.css"), "utf8");
const TOKEN = {};
for (const m of SURFACE.matchAll(/(--mm-(?:fs|r|sp)-[a-z0-9]+)\s*:\s*([0-9.]+px)/g)) TOKEN[m[1]] = m[2];

function docCss(text) {
  return String(text).replace(/var\((--mm-(?:fs|r|sp)-[a-z0-9]+)\)/g, (all, ten) => TOKEN[ten] || all);
}

module.exports = { docCss, TOKEN };
