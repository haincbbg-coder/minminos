// MinMin HUD - robot giap (0.64.85): mu giap co kinh visor sang, mao tren dinh, anten hai
// ben, tam giap mat co khe tan nhiet; co nhieu dot; giap nguc co vien, loi nang luong o nguc;
// bung chia khoang, dai lung; giap vai nhieu lop; canh tay co khop, gang tay giap loe; ban tay
// nam; thanh kiem deo sau lung (chuoi tren vai phai, luoi cheo xuong hong trai).
// Cung he toa do va bo dem voi body.js; moi phan sinh bang toan hoc, khong dung mo hinh ngoai.
import { makeBuffer, fill } from "./body.js";

const rnd = (a, b) => a + Math.random() * (b - a);
const STEP = 0.04;
const q = (v) => Math.round(v / STEP) * STEP;
const TAU = Math.PI * 2;

// Mu: elipsoid hoi vuong
const M = { y: 1.37, rx: 0.42, ry: 0.5, rz: 0.47 };
function muTruoc(x, y) {                     // z mat truoc cua mu tai (x, y)
  const dx = x / M.rx, dy = (y - M.y) / M.ry;
  const k = 1 - dx * dx - dy * dy;
  return k > 0 ? M.rz * Math.sqrt(k) : 0;
}

// Giap than: rong vai, thon eo, loe hong nhe
function rx(y) {
  if (y > 0.5) return 0.3 + (0.62 - y) / 0.12 * 0.35;
  if (y > 0.25) return 0.82;
  if (y > -0.45) return 0.82 - (0.25 - y) / 0.7 * 0.27;
  if (y > -0.8) return 0.55;
  return 0.55 + (-0.8 - y) * 0.12;
}
function rz(y) { return y > 0.5 ? 0.24 : y > -0.45 ? 0.36 : 0.3; }

const PHAN = [
  ["mu", 0.14], ["visor", 0.045], ["mao", 0.02], ["giapMat", 0.035], ["tai", 0.03],
  ["co", 0.03], ["than", 0.2], ["duongGiap", 0.05], ["loi", 0.025], ["dai", 0.02],
  ["vai", 0.1], ["tay", 0.12], ["gang", 0.05], ["nam", 0.04], ["kiem", 0.075],
];

export function robotPoints(n) {
  return fill(makeBuffer(n), PHAN, sinh, "than");
}

const sinh = {
  mu(put) {
    const u = rnd(-1, 1), a = Math.random() * TAU;
    const y = q(M.y + u * M.ry);
    const dy = (y - M.y) / M.ry, k = Math.sqrt(Math.max(0, 1 - dy * dy));
    // hoi vuong: luy thua sieu elip
    const c = Math.cos(a), s = Math.sin(a);
    const e = 0.7;
    const x = Math.sign(c) * Math.pow(Math.abs(c), e) * M.rx * k;
    const z = Math.sign(s) * Math.pow(Math.abs(s), e) * M.rz * k;
    put(x, y, z, 0.08, 1);
  },
  // Kinh visor: dai sang cong ngang qua mat
  visor(put) {
    const x = rnd(-0.34, 0.34);
    const cong = 1 - Math.pow(Math.abs(x) / 0.34, 2) * 0.35;
    const y = 1.42 + rnd(-0.02, 0.02) * cong - Math.abs(x) * 0.08;
    const vien = Math.random() < 0.35;
    const yy = vien ? 1.42 + (Math.random() < 0.5 ? 0.034 : -0.034) * cong - Math.abs(x) * 0.08 : y;
    put(x, yy, muTruoc(x, yy) + 0.02, vien ? 0.6 : 0.85, 1);
  },
  // Mao / vay tren dinh mu, chay tu tran ra sau
  mao(put) {
    const th = rnd(0.45, 2.6);                              // tu tran (truoc) vong qua dinh ra sau
    const cao = Math.sin((th - 0.45) / 2.15 * Math.PI) * 0.1 * Math.random();
    const r = 1.02 + cao / 0.5;
    put(rnd(-0.01, 0.01), M.y + Math.sin(th) * M.ry * r, Math.cos(th) * M.rz * r, cao > 0.07 ? 0.5 : 0.3, 1);
  },
  // Tam giap mat duoi: ham vuong co khe tan nhiet doc
  giapMat(put) {
    if (Math.random() < 0.55) {
      const x = Math.round(rnd(-0.16, 0.16) / 0.04) * 0.04, y = rnd(1.1, 1.26);
      put(x, y, muTruoc(x, y) + 0.03, 0.3, 1);
    } else {
      const t = Math.random() * TAU;
      const x = Math.cos(t) * 0.24, y = 1.18 + Math.sin(t) * 0.12;
      put(x, y, muTruoc(x * 0.9, y) + 0.02, 0.18, 1);
    }
  },
  // Tai: hop tron hai ben + anten cheo len sau
  tai(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    if (Math.random() < 0.6) {
      const a = Math.random() * TAU, r = Math.random() < 0.6 ? 0.11 : Math.sqrt(Math.random()) * 0.11;
      put(ben * (0.43 + rnd(0, 0.03)), 1.38 + Math.sin(a) * r, Math.cos(a) * r - 0.02, r > 0.1 ? 0.45 : 0.15, 1);
    } else {
      const t = Math.random();
      put(ben * (0.45 + t * 0.06), 1.45 + t * 0.42, -0.08 - t * 0.2, t > 0.85 ? 1 : 0.4, 1);
    }
  },
  // Co: cac dot vong + cap
  co(put) {
    const y = Math.round(rnd(0.62, 0.9) / 0.06) * 0.06 + rnd(-0.004, 0.004), a = Math.random() * TAU;
    const r = 0.14 + ((Math.round(y / 0.06) % 2) ? 0.02 : 0);
    put(Math.cos(a) * r, y, Math.sin(a) * r * 0.95 - 0.03, 0.08, Math.min(1, Math.max(0, (y - 0.62) / 0.28)));
  },
  than(put) {
    let y, a, rxx, rzz;
    for (let t = 0; t < 10; t++) {
      y = q(rnd(-1.5, 0.62)); rxx = rx(y); rzz = rz(y);
      if (Math.random() < (rxx + rzz) / 1.2) break;
    }
    a = Math.random() * TAU;
    const c = Math.cos(a), s = Math.sin(a);
    const x = Math.sign(c) * Math.pow(Math.abs(c), 0.75) * rxx;
    let z = Math.sign(s) * Math.pow(Math.abs(s), 0.75) * rzz;
    if (z > 0 && y < 0.45 && y > -0.1) z *= 1.1;      // nguc giap nho ra
    put(x, y, z - 0.04, 0.07, 0);
  },
  // Duong vien giap: duong ngang (nguc, bung chia khoang), duong doc giua, vien co ao
  duongGiap(put) {
    const k = Math.random();
    let x, y;
    if (k < 0.55) {
      const muc = [0.45, -0.1, -0.3, -0.5, -0.68][Math.floor(Math.random() * 5)];
      y = muc; x = rnd(-rx(y), rx(y)) * 0.92;
    } else if (k < 0.75) {
      y = rnd(-0.75, 0.4); x = (Math.random() < 0.5 ? -1 : 1) * 0.012;
    } else {
      // vien chu V cua giap nguc
      const t = rnd(-1, 1); x = t * 0.6; y = 0.5 - Math.abs(t) * 0.12 - (1 - Math.abs(t)) * 0.18;
    }
    const zz = rz(y) * Math.sqrt(Math.max(0, 1 - Math.pow(Math.abs(x) / (rx(y) + 0.001), 2.6))) * (y < 0.45 && y > -0.1 ? 1.1 : 1);
    put(x, y, zz - 0.02, 0.4, 0);
  },
  // Loi nang luong o nguc: vong + nan hoa
  loi(put) {
    const a = Math.random() * TAU, k = Math.random();
    const r = k < 0.6 ? 0.13 : k < 0.8 ? 0.08 : Math.random() * 0.13;
    put(Math.cos(a) * r, 0.15 + Math.sin(a) * r, 0.42, k < 0.8 ? 0.9 : 0.5, 0);
  },
  // Dai lung + khoa
  dai(put) {
    const a = Math.random() * TAU, y = -0.8 + rnd(-0.05, 0.05);
    const buckle = Math.random() < 0.25;
    if (buckle) put(rnd(-0.08, 0.08), -0.8 + rnd(-0.06, 0.06), rz(-0.8) + 0.02, 0.6, 0);
    else put(Math.cos(a) * (rx(y) + 0.03), y, Math.sin(a) * (rz(y) + 0.03) - 0.04, 0.25, 0);
  },
  // Giap vai: 3 lop vom chong len nhau, vien sang
  vai(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    const lop = Math.floor(Math.random() * 3);
    const cx = ben * (0.92 + lop * 0.04), cy = 0.52 - lop * 0.1, R = 0.3 - lop * 0.03;
    const u = Math.random(), a = Math.random() * TAU;
    const vien = Math.random() < 0.3;
    const phi = vien ? Math.PI / 2 : Math.acos(u);           // nua tren vom
    const x = cx + Math.sin(phi) * Math.cos(a) * R * 1.05;
    const y = cy + Math.cos(phi) * R * 0.75;
    const z = Math.sin(phi) * Math.sin(a) * R * 0.95;
    put(x, y, z, vien ? 0.6 : 0.12, 0, 0, 0);
  },
  tay(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    const S = [ben * 0.9, 0.4, -0.02], E = [ben * 1.04, -0.42, 0.04], W = [ben * 1.02, -1.18, 0.13];
    const khop = Math.random() < 0.12;
    if (khop) {                                               // khop khuyu tay
      const u = rnd(-1, 1), a = Math.random() * TAU, k = Math.sqrt(1 - u * u);
      put(E[0] + k * Math.cos(a) * 0.13, E[1] + u * 0.13, E[2] + k * Math.sin(a) * 0.13, 0.3, 0, ben, 2);
      return;
    }
    const tren = Math.random() < 0.5;
    const A = tren ? S : E, B = tren ? E : W;
    const t = Math.round(Math.random() / 0.06) * 0.06;
    const c = [A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t];
    // cang tay (gang) loe to dan ve co tay
    const r = tren ? 0.13 - t * 0.02 : 0.1 + t * 0.05;
    const a = Math.random() * TAU;
    put(c[0] + Math.cos(a) * r, c[1], c[2] + Math.sin(a) * r, 0.03, 0, ben, tren ? 1 : 2);
  },
  // Vien sang cua gang tay va bap tay
  gang(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    const E = [ben * 1.04, -0.42, 0.04], W = [ben * 1.02, -1.18, 0.13];
    const t = [0.15, 0.55, 0.98][Math.floor(Math.random() * 3)];
    const c = [E[0] + (W[0] - E[0]) * t, E[1] + (W[1] - E[1]) * t, E[2] + (W[2] - E[2]) * t];
    const r = 0.1 + t * 0.05 + 0.012, a = Math.random() * TAU;
    put(c[0] + Math.cos(a) * r, c[1], c[2] + Math.sin(a) * r, 0.5, 0, ben, 2);
  },
  // Ban tay nam
  nam(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    const u = rnd(-1, 1), a = Math.random() * TAU, k = Math.sqrt(1 - u * u);
    const knuckle = Math.random() < 0.3;
    put(ben * 1.02 + k * Math.cos(a) * 0.08, -1.32 + u * 0.1, 0.14 + k * Math.sin(a) * 0.1 + (knuckle ? 0.03 : 0),
      knuckle ? 0.35 : 0.1, 0, ben, 2);
  },
  // Kiem deo sau lung: chuoi + chan kiem tren vai phai, luoi cheo xuong hong trai
  kiem(put) {
    const H0 = [0.62, 1.12, -0.42];                           // dau chuoi (nhin thay tren vai)
    const G = [0.44, 0.78, -0.42];                            // chan kiem
    const T = [-0.95, -1.35, -0.42];                          // mui kiem
    const k = Math.random();
    const lerp = (A, B, t) => [A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t];
    const dir = [T[0] - G[0], T[1] - G[1]]; const L = Math.hypot(dir[0], dir[1]);
    const nx = -dir[1] / L, ny = dir[0] / L;                  // vuong goc luoi
    if (k < 0.12) {                                            // chuoi quan
      const p = lerp(H0, G, Math.random()), a = Math.random() * TAU;
      put(p[0] + Math.cos(a) * 0.025, p[1], p[2] + Math.sin(a) * 0.025, 0.3, 0, 0, 0, 1);
    } else if (k < 0.16) {                                     // num chuoi
      const a = Math.random() * TAU, b = Math.random() * TAU;
      put(H0[0] + Math.cos(a) * Math.cos(b) * 0.045, H0[1] + 0.03 + Math.sin(b) * 0.045, H0[2] + Math.sin(a) * 0.045, 0.7, 0, 0, 0, 1);
    } else if (k < 0.27) {                                     // chan kiem ngang
      const t = rnd(-1, 1);
      put(G[0] + nx * t * 0.2, G[1] + ny * t * 0.2, G[2] + rnd(-0.02, 0.02), 0.6, 0, 0, 0, 1);
    } else {                                                   // luoi: hai canh sac + gan giua
      const t = Math.pow(Math.random(), 0.85);
      const p = lerp(G, T, t), w = 0.055 * (1 - t * 0.85);
      const canh = Math.random();
      const off = canh < 0.4 ? w : canh < 0.8 ? -w : rnd(-0.01, 0.01);
      put(p[0] + nx * off, p[1] + ny * off, p[2], canh < 0.8 ? 0.95 : 0.6, 0, 0, 0, 1);
    }
  },
};
