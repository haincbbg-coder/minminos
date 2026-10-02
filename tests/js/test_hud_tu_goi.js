// Tu goi "Min Min" nghe dung ca khi may nhan dang viet sai dau hoac viet dinh lien.
const assert = require("assert");
const path = require("path");
const { pathToFileURL } = require("url");
(async () => {
  const { splitWake, speakable } = await import(pathToFileURL(path.join(__dirname, "..", "..", "dashboard", "hud", "voice.js")).href);
  const rest = (t) => { const r = splitWake(t); return r ? r.rest : null; };
  assert.strictEqual(rest("Hey Min Min hôm nay có bao nhiêu đơn"), "hôm nay có bao nhiêu đơn");
  assert.strictEqual(rest("min min ơi"), "");
  assert.strictEqual(rest("Mìn Mìn ơi kiểm tra camp"), "kiểm tra camp");
  assert.strictEqual(rest("Minh Minh ơi tắt camp HH214"), "tắt camp HH214");
  assert.strictEqual(rest("hey minmin"), "");
  assert.strictEqual(rest("hôm nay trời đẹp"), null);
  assert.strictEqual(rest("minh ơi"), null);
  // doc to: bo bang, markdown, link
  const s = speakable("**Doanh thu** 86 tr.\n| a | b |\n|---|---|\n- mục 1\n[xem](https://x.y)");
  assert.ok(!/[|*#]/.test(s) && !/https/.test(s), s);
  console.log("ok");
})().catch(e => { console.error(e); process.exit(1); });
