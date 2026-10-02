// HUD 0.64.84: nhan ra cu chi chum ngon, va cau hoi "nhin" thi gui kem anh camera.
const assert = require("assert");
const path = require("path");
const { pathToFileURL } = require("url");
const fs = require("fs");
(async () => {
  const { laChum, CU_CHI } = await import(pathToFileURL(path.join(__dirname, "..", "..", "dashboard", "hud", "vision.js")).href);
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
  for (const c of ["con nhìn xem đây là gì", "mô tả cái này", "bố đang cầm gì", "đọc giúp bố tờ này", "cái gì đây", "đây là cái gì", "hãng gì thế", "nút này dùng làm gì"]) assert.ok(re.test(c), c);
  for (const c of ["hôm nay có bao nhiêu đơn", "tắt camp HH214"]) assert.ok(!re.test(c), c);

  // Hinh nguoi va robot co du bo phan, co gan canh tay de bat chuoc
  const { humanPoints } = await import(pathToFileURL(path.join(__dirname, "..", "..", "dashboard", "hud", "body.js")).href);
  const { robotPoints } = await import(pathToFileURL(path.join(__dirname, "..", "..", "dashboard", "hud", "robot.js")).href);
  for (const [ten, b] of [["nguoi", humanPoints(5000)], ["robot", robotPoints(5000)]]) {
    assert.strictEqual(b.pos.length, 15000, ten);
    assert.ok(!Array.from(b.pos).some(Number.isNaN), ten + " NaN");
    let dau = 0, nong = 0, tay = 0;
    for (let i = 0; i < 5000; i++) { if (b.info[i * 3 + 2] > 0.5) dau++; if (b.info[i * 3] > 0.4) nong++; if (b.arm[i * 2]) tay++; }
    assert.ok(dau > 600 && nong > 50 && tay > 400, ten + JSON.stringify({ dau, nong, tay }));
  }

  // Goc canh tay tu diem khop: tha xuong = 0, dang ngang = +-90 do
  const { ngonDuoi } = await import(pathToFileURL(path.join(__dirname, "..", "..", "dashboard", "hud", "vision.js")).href);
  const bt = Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5 })); bt[0] = { x: 0.5, y: 0.9 };
  bt[6] = { x: 0.5, y: 0.6 }; bt[8] = { x: 0.5, y: 0.35 };      // ngon tro duoi
  bt[10] = { x: 0.52, y: 0.62 }; bt[12] = { x: 0.52, y: 0.66 };  // ngon giua co
  assert.strictEqual(ngonDuoi(bt, 8, 6), true);
  assert.strictEqual(ngonDuoi(bt, 12, 10), false);
  // tuong ban than: du hat, co phap tuyen don vi, co vung mat am
  const { bustPoints } = await import(pathToFileURL(path.join(__dirname, "..", "..", "dashboard", "hud", "bust.js")).href);
  const bu = bustPoints(8000);
  let nong = 0, lech = 0;
  for (let i = 0; i < 8000; i++) {
    if (bu.info[i * 3] > 0.4) nong++;
    const L = Math.hypot(bu.nrm[i * 3], bu.nrm[i * 3 + 1], bu.nrm[i * 3 + 2]);
    if (Math.abs(L - 1) > 1e-3) lech++;
  }
  assert.ok(nong > 200 && lech === 0 && !Array.from(bu.pos).some(Number.isNaN), JSON.stringify({ nong, lech }));

  const { gocTay, khoangCach, tenDoVat } = await import(pathToFileURL(path.join(__dirname, "..", "..", "dashboard", "hud", "vision.js")).href);
  const P = (x, y) => ({ x, y });
  const g0 = gocTay(P(.4, .4), P(.4, .6), P(.4, .8));
  assert.ok(Math.abs(g0[0]) < 1e-9 && Math.abs(g0[1]) < 1e-9);
  const g1 = gocTay(P(.4, .4), P(.2, .4), P(.2, .2));
  assert.ok(Math.abs(g1[0] + Math.PI / 2) < 1e-9 && Math.abs(g1[1] + Math.PI / 2) < 1e-9);
  assert.strictEqual(khoangCach([0, 3], [4, 0]), 5);
  assert.strictEqual(tenDoVat("remote"), "điều khiển");
  assert.strictEqual(tenDoVat("zebra"), "zebra");
  console.log("ok");
})().catch(e => { console.error(e); process.exit(1); });
