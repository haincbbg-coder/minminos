// HUD 0.64.84: nhan ra cu chi chum ngon, va cau hoi "nhin" thi gui kem anh camera.
const assert = require("assert");
const path = require("path");
const fs = require("fs");
(async () => {
  const { laChum, CU_CHI } = await import(path.join(__dirname, "..", "..", "dashboard", "hud", "vision.js"));
  const tay = (dx) => { const lm = Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5 })); lm[0] = { x: 0.5, y: 0.8 }; lm[9] = { x: 0.5, y: 0.5 }; lm[4] = { x: 0.5, y: 0.4 }; lm[8] = { x: 0.5 + dx, y: 0.4 }; return lm; };
  assert.strictEqual(laChum(tay(0.02)), true);
  assert.strictEqual(laChum(tay(0.2)), false);
  assert.strictEqual(laChum(null), false);
  assert.ok(CU_CHI.Pointing_Up && CU_CHI.Closed_Fist && CU_CHI.Pinch);

  // Bieu thuc HOI_NHIN trong hud.js: cau hoi ve canh truoc mat thi gui kem anh
  const src = fs.readFileSync(path.join(__dirname, "..", "..", "dashboard", "hud", "hud.js"), "utf8");
  const m = src.match(/const HOI_NHIN = (\/.*\/i);/);
  assert.ok(m, "thieu HOI_NHIN");
  const re = eval(m[1]);
  for (const c of ["con nhìn xem đây là gì", "mô tả cái này", "bố đang cầm gì", "đọc giúp bố tờ này", "cái gì đây"]) assert.ok(re.test(c), c);
  for (const c of ["hôm nay có bao nhiêu đơn", "tắt camp HH214"]) assert.ok(!re.test(c), c);

  // Hinh nguoi co du bo phan va dung so hat
  const { humanPoints } = await import(path.join(__dirname, "..", "..", "dashboard", "hud", "body.js"));
  const h = humanPoints(5000);
  assert.strictEqual(h.pos.length, 15000);
  let dau = 0, nong = 0, tay2 = 0;
  for (let i = 0; i < 5000; i++) { if (h.head[i] > 0.5) dau++; if (h.zone[i] > 0.4) nong++; if (Math.abs(h.pos[i * 3]) > 0.85) tay2++; }
  assert.ok(dau > 1000 && nong > 50 && tay2 > 500, JSON.stringify({ dau, nong, tay2 }));
  console.log("ok");
})().catch(e => { console.error(e); process.exit(1); });
