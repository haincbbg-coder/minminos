// HUD 0.64.87: khoa mot tay, dieu khien may tinh bang cu chi, hinh minh hoa, file .bat,
// Noi lien / tu goi qua _xuLy chung cho trinh duyet va Whisper.
const assert = require("assert");
const path = require("path");
const hud = (f) => path.join(__dirname, "..", "..", "dashboard", "hud", f);

// Ban tay gia: ngon nao duoi thi dau ngon xa co tay; ti le co ban tay (0 -> 9) = 0.3
function tay({ tro = false, giua = false, ap = false, ut = false, mo = 0.6, cai = false, x = 0.5, y = 0.5 } = {}) {
  const lm = Array.from({ length: 21 }, () => ({ x, y }));
  lm[0] = { x, y: y + 0.3 }; lm[9] = { x, y };
  const ngon = (dau, giuaIdx, duoi, dx) => {
    lm[giuaIdx] = { x: x + dx, y: y - 0.05 };
    lm[dau] = duoi ? { x: x + dx, y: y - 0.2 } : { x: x + dx, y: y + 0.02 };
  };
  ngon(8, 6, tro, -0.04); ngon(12, 10, giua, 0); ngon(16, 14, ap, 0.03); ngon(20, 18, ut, 0.06);
  lm[5] = { x: x - 0.04, y: y + 0.02 };
  // ngon cai: dat cach dau ngon tro dung "mo" lan co ban tay
  lm[4] = { x: lm[8].x - mo * 0.3, y: lm[8].y };
  if (!cai && mo > 0.5) lm[4] = { x: lm[8].x, y: lm[8].y + mo * 0.3 };
  return lm;
}

(async () => {
  const { tayThat, chonTay, CHE_DO } = await import(hud("vision.js"));
  // 0.64.89: nhan cua may chi dao khi bo da "Chinh tay" va may goi nguoc (dao = true)
  assert.strictEqual(tayThat("Left", true), "Right");
  assert.strictEqual(tayThat("Right", true), "Left");
  assert.strictEqual(tayThat("Left", false), "Left");
  assert.strictEqual(tayThat("Right", null), "Right");
  assert.strictEqual(tayThat("", true), "");
  // Nut Doi cam: phuong thuc rieng, khong con trung ten voi cai dat `flip` (bi che mat)
  const { Vision } = await import(hud("vision.js"));
  assert.strictEqual(typeof Vision.prototype.doiCam, "function");
  assert.ok(!("flip" in Vision.prototype), "khong duoc co phuong thuc ten flip");
  assert.deepStrictEqual(Object.keys(CHE_DO), ["cuchi", "batchuoc", "maytinh"]);

  const lmA = tay({ x: 0.3 }), lmB = tay({ x: 0.7 });
  const phai = { lm: lmA, label: "Right", score: 0.97 }, trai = { lm: lmB, label: "Left", score: 0.95 };
  // Chi tay da chon duoc dieu khien, tay kia bo qua
  assert.strictEqual(chonTay([trai, phai], "Right", null), phai);
  assert.strictEqual(chonTay([trai, phai], "Left", null), trai);
  assert.strictEqual(chonTay([trai], "Right", null), null, "chi co tay trai -> khong dieu khien");
  // Nhan khong chac (nhay nhan) nhung dung cho tay cu -> van giu
  const nhay = { lm: lmA, label: "Left", score: 0.55 };
  assert.strictEqual(chonTay([nhay], "Right", { x: 0.3, y: 0.5 }), nhay);
  assert.strictEqual(chonTay([nhay], "Right", { x: 0.7, y: 0.5 }), null);
  // Buoc chinh huong: tay nao cung nhan
  assert.strictEqual(chonTay([trai], "Any", null), trai);
  assert.strictEqual(chonTay([], "Right", null), null);

  // ---- Dieu khien may tinh ----
  const { DieuKhienMay, doMo, baNgonCo, anhXa, taoBat, CU_CHI_MAY } = await import(hud("dieukhien.js"));
  assert.ok(doMo(tay({ tro: true, mo: 0.1 })) < 0.28);
  assert.ok(baNgonCo(tay({ tro: true })));
  assert.ok(!baNgonCo(tay({ tro: true, giua: true, ap: true, ut: true })));
  assert.deepStrictEqual(anhXa(0.2, 0.15), [0, 0]);
  assert.deepStrictEqual(anhXa(0.9, 0.9), [1, 1]);

  const lenh = [], bao = [];
  const m = new DieuKhienMay({ gui: (l) => lenh.push(l), bao: (g) => bao.push(g) });
  let t = 1000;
  // Tro -> di chuot
  assert.strictEqual(m.capNhat(tay({ tro: true, x: 0.5 }), "Pointing_Up", t), "M_Move");
  assert.strictEqual(lenh.pop().t, "move");
  // Chum nhanh roi tha -> bam chuot
  m.capNhat(tay({ tro: true, mo: 0.1 }), "Pinch", t += 50);
  m.capNhat(tay({ tro: true, mo: 0.1 }), "Pinch", t += 150);
  assert.strictEqual(m.capNhat(tay({ tro: true, mo: 0.6 }), "Pointing_Up", t += 50), "M_Click");
  assert.deepStrictEqual(lenh.pop(), { t: "click" });
  // Chum GIU nua giay -> che do phong; mo ra -> phong to
  lenh.length = 0;
  m.capNhat(tay({ tro: true, mo: 0.1 }), "Pinch", t += 100);
  assert.strictEqual(m.capNhat(tay({ tro: true, mo: 0.1 }), "Pinch", t += 500), "M_Zoom");
  assert.strictEqual(m.capNhat(tay({ tro: true, mo: 0.5, cai: true }), "", t += 50), "M_ZoomIn");
  assert.ok(lenh.length >= 2 && lenh.every(l => l.t === "zoom" && l.d === 1), JSON.stringify(lenh));
  assert.ok(!lenh.some(l => l.t === "click"), "chum giu khong duoc bam chuot");
  // chum lai -> thu nho
  lenh.length = 0;
  assert.strictEqual(m.capNhat(tay({ tro: true, mo: 0.1 }), "Pinch", t += 50), "M_ZoomOut");
  assert.ok(lenh.every(l => l.d === -1));
  // xoe het tay -> thoat che do phong
  m.capNhat(tay({ tro: true, giua: true, ap: true, ut: true, mo: 0.9, cai: true }), "Open_Palm", t += 50);
  assert.strictEqual(m.zoom, null);

  // Chu V dua LEN -> cuon xuong (lan chuot am), nhu vuot dien thoai
  lenh.length = 0; m.mat();
  m.capNhat(tay({ tro: true, giua: true, y: 0.6 }), "Victory", t += 50);
  assert.strictEqual(m.capNhat(tay({ tro: true, giua: true, y: 0.5 }), "Victory", t += 50), "M_Scroll");
  assert.ok(lenh.length === 1 && lenh[0].t === "scroll" && lenh[0].n < 0, JSON.stringify(lenh));

  // Xoe tay vuot nhanh sang trai -> phim → (trang tiep)
  lenh.length = 0; m.mat();
  const xoe = (x) => tay({ tro: true, giua: true, ap: true, ut: true, mo: 0.9, cai: true, x });
  m.capNhat(xoe(0.7), "Open_Palm", t += 50);
  m.capNhat(xoe(0.6), "Open_Palm", t += 80);
  assert.strictEqual(m.capNhat(xoe(0.45), "Open_Palm", t += 80), "M_Swipe");
  assert.deepStrictEqual(lenh, [{ t: "key", k: "right" }]);
  // xoe yen thi khong lam gi
  lenh.length = 0;
  m.capNhat(xoe(0.45), "Open_Palm", t += 900); m.capNhat(xoe(0.46), "Open_Palm", t += 100);
  assert.strictEqual(lenh.length, 0);

  // Nam tay giu 1,5 giay -> tam dung: moi cu chi bi bo qua
  m.capNhat(tay(), "Closed_Fist", t += 50);
  m.capNhat(tay(), "Closed_Fist", t += 1600);
  assert.strictEqual(m.dung, true);
  lenh.length = 0;
  assert.strictEqual(m.capNhat(tay({ tro: true }), "Pointing_Up", t += 3000), "");
  assert.strictEqual(lenh.length, 0);
  for (const g of new Set(bao)) assert.ok(CU_CHI_MAY[g], g);

  // File .bat: tai dung dia chi, chi nhan lenh tu trang nay, dong CRLF, khong dau tieng Viet
  const bat = taoBat("https://minmin.example.vn");
  assert.ok(bat.includes('curl -fsSL "https://minmin.example.vn/static/hud/tay/minmin-tay.py"'));
  assert.ok(bat.includes("--nguon https://minmin.example.vn"));
  assert.ok(bat.split("\r\n").length > 8 && !/[^\r]\n/.test(bat));
  assert.ok(/^[\x00-\x7f]*$/.test(bat), "bat phai la ASCII");

  // Hinh minh hoa: du cho moi cu chi trong bang
  const { hinhTay, HINH } = await import(hud("hinhtay.js"));
  const fs = require("fs");
  const html = fs.readFileSync(hud("index.html"), "utf8");
  const ds = [...html.matchAll(/data-g="(\w+)"/g)].map(x => x[1]);
  assert.ok(ds.length >= 14);
  for (const g of ds) { assert.ok(HINH[g], "thieu hinh " + g); assert.ok(hinhTay(HINH[g]).startsWith("<svg"), g); }

  // ---- Giong: Noi lien khong can tu goi; tu goi van chay ----
  global.localStorage = { getItem: () => null, setItem: () => {} };
  global.window = {};
  const { VoiceIO } = await import(hud("voice.js"));
  const cmds = [], wakes = [], nghe = [];
  const v = new VoiceIO({ onCommand: (c) => cmds.push(c), onWake: (r) => wakes.push(r), onHeard: (x, f, g) => nghe.push([x, f, g]) });
  v._xuLy(["hôm nay bao nhiêu đơn"], true);
  assert.strictEqual(cmds.length, 0, "chua goi thi khong phai lenh");
  v._xuLy(["Min Min ơi hôm nay bao nhiêu đơn"], true);
  assert.deepStrictEqual(cmds, ["hôm nay bao nhiêu đơn"]);
  v.noiLien = true;
  v._xuLy(["mã nào bán chạy nhất"], true);
  assert.strictEqual(cmds[1], "mã nào bán chạy nhất");
  v._xuLy(["ừ"], true);
  assert.strictEqual(cmds.length, 2, "mot tu le khong tinh la lenh");
  assert.ok(nghe.some(n => n[2] === true), "bang Tro chuyen thay duoc cau co tu goi");
  clearTimeout(v._awakeTimer);

  // Chinh tay (0.64.89): bo gio tay PHAI that. May goi la "Left" -> nhanDao = true; tay hien
  // ben phai man hinh -> khong doi huong.
  const luu = {}; global.localStorage = { getItem: (k) => luu[k] ?? null, setItem: (k, x) => { luu[k] = x; } };
  const ketQua = [];
  const gia = { facing: "user", flip: false, dangChinh: { t: 0 }, onChinh: (r) => ketQua.push(r) };
  gia._sx = Vision.prototype._sx;
  const motTay = (tho, x) => [{ lm: tay({ x }), tho, label: tho, score: 0.9 }];
  Vision.prototype._buocChinh.call(gia, motTay("Left", 0.3), 1000);   // khung tho: x=0.3 -> man hinh 0.7 (ben phai)
  Vision.prototype._buocChinh.call(gia, motTay("Left", 0.3), 1500);
  assert.strictEqual(ketQua.length, 0, "chua du 1 giay");
  Vision.prototype._buocChinh.call(gia, motTay("Left", 0.3), 2100);
  assert.deepStrictEqual(ketQua[0], { nhanDao: true, doiHuong: false });
  assert.strictEqual(luu["minmin.hud.nhandao"], "1");
  assert.strictEqual(gia.dangChinh, null);
  // Tay hien ben TRAI man hinh -> dao huong di chuyen
  const gia2 = { facing: "user", flip: false, dangChinh: { t: 0 }, onChinh: (r) => ketQua.push(r), _sx: Vision.prototype._sx };
  Vision.prototype._buocChinh.call(gia2, motTay("Right", 0.8), 10);
  Vision.prototype._buocChinh.call(gia2, motTay("Right", 0.8), 1200);
  assert.deepStrictEqual(ketQua[1], { nhanDao: false, doiHuong: true });
  assert.strictEqual(gia2.flip, true);
  // Hai tay cung luc: khong chinh
  const gia3 = { facing: "user", flip: false, dangChinh: { t: 0 }, onChinh: (r) => ketQua.push(r), _sx: Vision.prototype._sx };
  Vision.prototype._buocChinh.call(gia3, [...motTay("Right", 0.3), ...motTay("Left", 0.7)], 10);
  Vision.prototype._buocChinh.call(gia3, [...motTay("Right", 0.3), ...motTay("Left", 0.7)], 2000);
  assert.strictEqual(ketQua.length, 2);
  console.log("ok");
})().catch((e) => { console.error(e); process.exit(1); });
