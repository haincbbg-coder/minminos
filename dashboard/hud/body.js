// MinMin HUD - hinh nguoi bang hat (0.64.84): dau co mat, long may, mui, mieng, tai; co,
// than, hai tay va ban tay. Moi phan sinh bang toan hoc tai cho, khong dung mo hinh cua ai.
//
// Moi hat co:
//   pos   vi tri (x, y, z), hinh quay mat ve +z, dinh dau o y ~ 1.87, hong o y ~ -1.5
//   zone  do "nong" 0..1 (mat, mieng, mui sang hon) - shader to mau cam va phong to hat
//   fade  do mo 0..1 (phan hong mo dan xuong duoi)
//   head  1 = thuoc dau (quay theo chuot / theo mat nguoi dung), 0 = than
//
// Duong "dong muc": phan vo (dau, than, tay) lam tron toa do theo tung lat nen hien thanh
// cac vong ke ngang nhu ban do dia hinh - dung chat HUD ma bo thich.

const STEP = 0.042;                       // khoang cach giua cac vong dong muc
const rnd = (a, b) => a + Math.random() * (b - a);
const q = (v) => Math.round(v / STEP) * STEP;     // lam tron theo lat

// Hinh dau: tam, ban kinh
const H = { x: 0, y: 1.35, z: 0, rx: 0.40, ry: 0.52, rz: 0.47 };

// z cua mat truoc dau tai (x, y) - de dat mat, mui, mieng dung tren be mat
function mattruoc(x, y) {
  const dx = x / H.rx, dy = (y - H.y) / H.ry;
  const k = 1 - dx * dx - dy * dy;
  return k > 0 ? H.rz * Math.sqrt(k) * 0.92 : 0;
}

function rxThan(y) {
  if (y > 0.45) { const t = Math.min(1, (0.62 - y) / 0.17); return 0.2 + 0.72 * (1 - Math.pow(1 - t, 2)); }
  if (y > 0.2) return 0.92 - (0.45 - y) / 0.25 * 0.3;
  if (y > -0.8) return 0.62 - (0.2 - y) / 1.0 * 0.1;
  return 0.52 + (-0.8 - y) / 0.7 * 0.08;
}
function rzThan(y) {
  if (y > 0.45) return 0.18 + (0.62 - y) / 0.17 * 0.1;
  if (y > -0.2) return 0.31;
  return 0.29;
}

// Cac phan va ty le so hat
const PHAN = [
  ["dau", 0.20], ["mat", 0.03], ["may", 0.012], ["mui", 0.014], ["mieng", 0.013], ["tai", 0.022],
  ["co", 0.03], ["than", 0.33], ["tay", 0.23], ["bantay", 0.07],
];

// Bo dem chung cho moi hinh: vi tri + info (zone, fade, head) + arm (ben -1/0/1, doan 1 = canh
// tay tren, 2 = cang tay + ban tay). `arm` cho phep canh tay bat chuoc tay bo qua camera.
export function makeBuffer(n) {
  const b = { pos: new Float32Array(n * 3), info: new Float32Array(n * 3), arm: new Float32Array(n * 2), n, i: 0 };
  b.put = (x, y, z, zn = 0, hd = 0, ben = 0, doan = 0, fd = null) => {
    if (b.i >= n) return;
    const i = b.i++;
    b.pos[i * 3] = x; b.pos[i * 3 + 1] = y; b.pos[i * 3 + 2] = z;
    // phan than duoi mo dan; tay (ben != 0) va vu khi (fd = 1) giu sang
    const f = fd != null ? fd : (ben ? 1 : Math.min(1, Math.max(0, (y + 1.55) / 0.75)));
    b.info[i * 3] = zn; b.info[i * 3 + 1] = f; b.info[i * 3 + 2] = hd;
    b.arm[i * 2] = ben; b.arm[i * 2 + 1] = doan;
  };
  return b;
}

export function fill(b, parts, gen, filler) {
  const tong = parts.reduce((a, p) => a + p[1], 0);
  for (const [ten, tl] of parts) {
    const m = Math.round(b.n * tl / tong);
    for (let k = 0; k < m; k++) gen[ten](b.put);
  }
  while (b.i < b.n) gen[filler](b.put);
  return b;
}

export const SHOULDER = [0.9, 0.42], ELBOW = [1.04, -0.42];

export function humanPoints(n) {
  return fill(makeBuffer(n), PHAN, sinh, "than");
}

const sinh = {
  // Vo dau: elipsoid, ham thu hep, mat truoc hoi phang, vong dong muc theo y
  dau(put) {
    const u = rnd(-1, 1), a = Math.random() * Math.PI * 2;
    const y = q(H.y + u * H.ry);
    const dy = (y - H.y) / H.ry;
    const k = Math.sqrt(Math.max(0, 1 - dy * dy));
    let rx = H.rx * k * (dy < -0.25 ? 0.8 + (dy + 1) * 0.27 : 1);
    let x = Math.cos(a) * rx, z = Math.sin(a) * H.rz * k;
    if (z > 0) z *= 0.92;
    const truoc = Math.max(0, z / (H.rz * k || 1));
    put(x, y, z, truoc * 0.22 * Math.max(0, 1 - Math.abs(dy - 0.05) * 1.4), 1);
  },
  // Hai mat: vien mi + con nguoi day, sang nhat
  mat(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    const cx = ben * 0.155, cy = 1.41;
    let x, y, zn;
    if (Math.random() < 0.55) {            // vien mat hinh hanh nhan
      const a = Math.random() * Math.PI * 2;
      x = cx + Math.cos(a) * 0.075; y = cy + Math.sin(a) * 0.034; zn = 0.5;
    } else {                               // con nguoi
      const r = Math.sqrt(Math.random()) * 0.026, a = Math.random() * Math.PI * 2;
      x = cx + Math.cos(a) * r; y = cy + Math.sin(a) * r; zn = 0.85;
    }
    put(x, y, mattruoc(x, y) + 0.012, zn, 1);
  },
  // Long may: cung cong tren mat
  may(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    const t = Math.random();
    const x = ben * (0.07 + t * 0.17), y = 1.505 + Math.sin(t * Math.PI) * 0.025 - t * 0.012;
    put(x, y + rnd(-0.006, 0.006), mattruoc(x, y) + 0.01, 0.3, 1);
  },
  // Mui: song mui nho ra dan, canh mui o chan
  mui(put) {
    let x, y, z;
    if (Math.random() < 0.6) {
      const t = Math.random();
      y = 1.42 - t * 0.19; x = rnd(-0.012, 0.012) * (1 + t * 2);
      z = mattruoc(0, y) + t * 0.07;
    } else {
      const a = rnd(Math.PI * 0.1, Math.PI * 0.9);
      x = Math.cos(a) * 0.055; y = 1.215 - Math.sin(a) * 0.012;
      z = mattruoc(x, y) + 0.05;
    }
    put(x, y, z, 0.35, 1);
  },
  // Mieng: hai moi
  mieng(put) {
    const t = rnd(-1, 1), x = t * 0.105;
    const tren = Math.random() < 0.5;
    const y = 1.115 + (tren ? 0.012 - Math.abs(t) * 0.01 : -0.016 + t * t * 0.012);
    put(x, y, mattruoc(x, y) + 0.012, 0.45, 1);
  },
  // Tai: vong elip hai ben dau
  tai(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    const a = Math.random() * Math.PI * 2, r = Math.random() < 0.7 ? 1 : Math.sqrt(Math.random());
    const y = 1.36 + Math.sin(a) * 0.11 * r, z = -0.02 + Math.cos(a) * 0.06 * r;
    put(ben * (0.405 + (1 - r) * 0.01), y, z, 0.25, 1);
  },
  // Co
  co(put) {
    const y = q(rnd(0.62, 0.9)), a = Math.random() * Math.PI * 2;
    const hd = Math.min(1, Math.max(0, (y - 0.62) / 0.28));
    put(Math.cos(a) * 0.15, y, -0.03 + Math.sin(a) * 0.14, 0, hd);
  },
  // Than: vai, nguc, eo, hong theo vong dong muc
  than(put) {
    let y, rx, rz;
    for (let t = 0; t < 10; t++) {
      y = q(rnd(-1.5, 0.62)); rx = rxThan(y); rz = rzThan(y);
      if (Math.random() < (rx + rz) / 1.25) break;
    }
    const a = Math.random() * Math.PI * 2;
    let z = Math.sin(a) * rz;
    if (z > 0 && y < 0.35 && y > -0.35) z *= 1.08;       // nguc nho ra
    put(Math.cos(a) * rx, y, z - 0.04, 0, 0);
  },
  // Tay: vai -> khuyu -> co tay, ong tron co vong dong muc
  tay(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    const S = [ben * 0.9, 0.42, -0.02], E = [ben * 1.04, -0.42, 0.04], W = [ben * 1.02, -1.2, 0.13];
    const tren = Math.random() < 0.52;
    const A = tren ? S : E, B = tren ? E : W;
    const r0 = tren ? 0.15 : 0.115, r1 = tren ? 0.12 : 0.085;
    const t = Math.round(Math.random() / 0.055) * 0.055;
    const c = [A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t];
    const r = r0 + (r1 - r0) * t, a = Math.random() * Math.PI * 2;
    put(c[0] + Math.cos(a) * r, c[1] + rnd(-0.004, 0.004), c[2] + Math.sin(a) * r * 0.92, 0, 0, ben, tren ? 1 : 2);
  },
  // Ban tay: long ban tay + 4 ngon + ngon cai
  bantay(put) {
    const ben = Math.random() < 0.5 ? -1 : 1;
    const cx = ben * 1.02, cy = -1.34, cz = 0.14;
    const k = Math.random();
    if (k < 0.45) {
      const a = Math.random() * Math.PI * 2, b = rnd(-1, 1);
      const s = Math.sqrt(1 - b * b);
      put(cx + Math.cos(a) * s * 0.035, cy + b * 0.1, cz + Math.sin(a) * s * 0.07, 0.2, 0, ben, 2);
    } else if (k < 0.88) {
      const f = Math.floor(Math.random() * 4), t = Math.random();
      const fz = cz - 0.05 + f * 0.034;
      put(cx + ben * 0.004 * f, cy - 0.1 - t * (0.1 + (f === 1 || f === 2 ? 0.02 : 0)), fz, 0.25, 0, ben, 2);
    } else {
      const t = Math.random();
      put(cx - ben * 0.01, cy - 0.02 - t * 0.09, cz + 0.08 + t * 0.03, 0.25, 0, ben, 2);
    }
  },
};
