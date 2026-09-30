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
  // MediaPipe gia dinh anh da lat guong: webcam thuong (flip=false) thi nhan bi nguoc
  assert.strictEqual(tayThat("Left", false), "Right");
  assert.strictEqual(tayThat("Right", false), "Left");
  assert.strictEqual(tayThat("Left", true), "Left");
  assert.strictEqual(tayThat("", false), "");
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
  console.log("ok");
})().catch((e) => { console.error(e); process.exit(1); });
