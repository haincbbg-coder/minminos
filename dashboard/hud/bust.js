// MinMin HUD - tuong ban than bang hat sang (0.64.86), hinh mac dinh.
//
// Dau, co, vai ve bang cac vong dong muc ngang day dac. Moi hat mang PHAP TUYEN be mat de
// shader tinh "sang vien" (rim light): hat o ria hinh nhin tu camera sang ruc, hat quay thang
// ve camera mo di - vien ngoai phat sang ro ret, ben trong trong nhu kinh. Mat phia truoc la
// vung am cam voi duong gon song; co va nguc tren co cac soi than kinh cam toa nhanh; quanh
// hinh co bui sang li ti. Moi thu sinh bang toan hoc, mau theo nhan dien MinMin (tim - cam).
import { makeBuffer } from "./body.js";

const rnd = (a, b) => a + Math.random() * (b - a);
const TAU = Math.PI * 2;
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// Mat cat ngang cua tuong tai do cao y: ban kinh ngang rx, sau rz, lech sau cz.
// Dau: elipsoid tam 1.18; co thon; vai loe rong em ai roi thang xuong.
export const DAU = { y: 1.18, rx: 0.5, ry: 0.66, rz: 0.58 };
export function mat(y) {
  let rxD = 0, rzD = 0;
  const dy = (y - DAU.y) / DAU.ry;
  if (Math.abs(dy) < 1) {
    const k = Math.sqrt(1 - dy * dy);
    // 26.10.79: ham vuong va chac hon (truoc thu rat nhanh nen dau trong "ong"): quai ham rong,
    // cam hoi vuong, chi thu lai o ria duoi cung.
    const ham = dy < -0.2 ? 1 - Math.pow((-0.2 - dy) / 0.8, 1.6) * 0.34 : 1;
    rxD = DAU.rx * k * ham; rzD = DAU.rz * k;
  }
  // 26.10.79: than luc luong kieu Apex. Co day, co thang xuong cap tren (trapezius) doc ra vai,
  // vai tron (deltoid), nguc no, roi thon dan xuong eo thanh hinh chu V.
  const rxCo = 0.31, rzCo = 0.31;
  let rxT, rzT;
  if (y > 0.4) { rxT = rxCo; rzT = rzCo; }
  else if (y > 0.04) {                                  // cap tren: doc loe ra, hoi lom gan co
    const t = (0.4 - y) / 0.36;
    rxT = rxCo + (0.98 - rxCo) * (1 - Math.pow(1 - t, 1.85));
    rzT = rzCo + (0.5 - rzCo) * smooth(0, 1, t);
  } else if (y > -0.2) {                                // vai tron
    const t = (0.04 - y) / 0.24;
    rxT = 0.98 + 0.3 * Math.sin(t * Math.PI / 2);
    rzT = 0.5 + 0.1 * t;
  } else if (y > -0.55) {                               // nguc, hoi thu vao
    const t = (-0.2 - y) / 0.35;
    rxT = 1.28 - 0.06 * t;
    rzT = 0.6 + 0.04 * Math.sin(t * Math.PI);
  } else {                                              // chu V: thon dan xuong eo
    const t = Math.min(1, (-0.55 - y) / 0.75);
    rxT = 1.22 - 0.42 * smooth(0, 1, t);
    rzT = 0.6 - 0.18 * smooth(0, 1, t);
  }
  let rx, rz;
  if (y > 0.62) { rx = Math.max(rxD, y < 0.72 ? rxCo : 0); rz = Math.max(rzD, y < 0.72 ? rzCo : 0); }
  else { rx = rxT; rz = rzT; }
  const t0 = smooth(0.36, -0.5, y);
  return { rx, rz, cz: y < 0.3 ? -0.06 * t0 : 0 };
}

// Dap noi be mat (26.10.79): khuon mat va co bap, tinh bang toan hoc theo (x, y) cua mat cat.
// Tra ve do nhô them theo +z (am = lom). Hat nam tren cac vong dong muc nen moi cho nho len/lom
// xuong bi lech vong va doi huong phap tuyen, shader vien sang tu do ve ra duong nhan co.
const g2 = (dx, dy, sx, sy) => Math.exp(-((dx / sx) ** 2 + (dy / sy) ** 2));
export function relief(x, y) {
  const ax = Math.abs(x);
  let dz = 0;
  // --- Mat (dau cao 0.52..1.84) ---
  if (y > 0.5 && y < 1.9) {
    dz += 0.055 * g2(ax, y - 1.30, 0.42, 0.05);                       // gờ long may
    dz -= 0.05 * g2(ax - 0.2, y - 1.2, 0.1, 0.07);                    // hoc mat
    dz += 0.1 * g2(x, 0, 0.055, 1) * smooth(0.78, 0.98, y) * (1 - smooth(1.2, 1.3, y));   // song mui
    dz += 0.05 * g2(x, y - 0.8, 0.1, 0.05);                           // dau mui
    dz += 0.045 * g2(ax - 0.33, y - 0.98, 0.11, 0.11);                // go ma
    dz -= 0.035 * g2(x, y - 0.68, 0.17, 0.018);                       // duong mieng
    dz += 0.05 * g2(x, y - 0.56, 0.16, 0.08);                         // cam
  }
  // --- Co: gan nhau tu tai xuong xuong don (sternocleidomastoid) ---
  if (y > 0.05 && y < 0.62) dz += 0.05 * g2(ax - (0.05 + (0.62 - y) * 0.5), 0, 0.05, 1);
  // --- Nguc, vai, bung ---
  if (y < 0.2 && y > -1.6) {
    for (const s of [-1, 1]) dz += 0.13 * g2(x - s * 0.4, y + 0.3, 0.34, 0.22);     // co nguc
    dz += 0.05 * g2(ax - 0.98, y + 0.1, 0.2, 0.3);                              // vai (deltoid)
    dz -= 0.05 * g2(ax - 0.76, y + 0.2, 0.05, 0.3);                               // khe vai/nguc
    dz -= 0.05 * g2(x, 0, 0.045, 1) * smooth(0.0, -0.1, y) * (1 - smooth(-0.8, -0.55, y));   // ranh giua nguc
    dz += 0.04 * g2(ax, y - (0.1 - 0.13 * Math.min(ax, 1)), 0.75, 0.022);          // xuong don
    dz -= 0.045 * g2(ax, y + 0.55, 0.5, 0.025);                                   // mep duoi nguc
    for (let k = 0; k < 3; k++) {                                                 // cơ bụng 6 mui
      const yk = -0.78 - k * 0.2;
      dz += 0.05 * g2(ax - 0.2, y - yk, 0.13, 0.085) * smooth(-0.62, -0.7, y);
      dz -= 0.03 * g2(ax, y - (yk - 0.1), 0.45, 0.014);
    }
    dz -= 0.035 * g2(x, 0, 0.03, 1) * smooth(-0.62, -0.7, y);                     // duong giua bung
  }
  return dz;
}

const Y_TOP = DAU.y + DAU.ry - 0.005, Y_BOT = -1.55;
const STEP = 0.026;                                   // khoang cach giua cac duong dong muc

export function bustPoints(n) {
  const b = makeBuffer(n);
  const nrm = new Float32Array(n * 3);
  const put = (x, y, z, nx, ny, nz, zone, fade, head) => {
    const i = b.i;
    if (i >= n) return;
    b.put(x, y, z, zone, head, 0, 0, fade);
    const L = Math.hypot(nx, ny, nz) || 1;
    nrm[i * 3] = nx / L; nrm[i * 3 + 1] = ny / L; nrm[i * 3 + 2] = nz / L;
  };
  const nVo = Math.floor(n * 0.77), nThan = Math.floor(n * 0.05), nBui = n - nVo - nThan;   // 26.10.69: nhieu bui quanh dau hon (kieu Apex)

  // 1) Vo: vong dong muc. Chon lat cat theo chu vi de mat do deu.
  for (let k = 0; k < nVo; k++) {
    let y, m;
    for (let t = 0; t < 12; t++) {
      y = Y_BOT + Math.random() * (Y_TOP - Y_BOT);
      y = Math.round(y / STEP) * STEP;
      m = mat(y);
      if (m.rx > 0.02 && Math.random() < (m.rx + m.rz) / 1.9) break;
    }
    const a = Math.random() * TAU;
    let x = Math.cos(a) * m.rx, z = Math.sin(a) * m.rz + m.cz;
    // dap noi: chi mat truoc (sin a > 0), mem dan ve hai ben
    const truoc = smooth(0.0, 0.55, Math.sin(a));
    const rl = relief(x, y);
    z += rl * truoc;
    // phap tuyen: ngang theo elip + thanh phan doc o dau (vom) va vai (doc xuong)
    let ny = 0;
    const dy = (y - DAU.y) / DAU.ry;
    if (y > 0.6) ny = dy * 0.9;
    else if (y < 0.36 && y > -0.7) ny = 1.1 * (1 - smooth(0.3, -0.55, y)) * smooth(0.36, 0.25, y) + 0.6 * smooth(0.3, -0.1, y) * (1 - smooth(-0.2, -0.6, y));
    let nx = Math.cos(a) / m.rx, nz = Math.sin(a) / m.rz;
    // phap tuyen theo do doc cua dap noi: nho len thi huong ra, doc xuong thi huong xuong
    const e = 0.012;
    const gx = (relief(x + e, y) - relief(x - e, y)) / (2 * e), gy = (relief(x, y + e) - relief(x, y - e)) / (2 * e);
    nx -= gx * 1.6 * truoc; ny -= gy * 1.6 * truoc;
    // mat truoc: vung am, duong gon song nhe
    let zone = 0.04;
    if (y > 0.72 && z > 0) {
      const fx = x / DAU.rx, fy = (y - (DAU.y - 0.08)) / 0.42;
      const am = Math.exp(-(fx * fx * 1.3 + fy * fy * 0.9)) * Math.pow(Math.max(0, z / (m.rz || 1)), 0.6);
      if (am > 0.06) { y += Math.sin(x * 22 + y * 7) * 0.012 * am; zone = 0.15 + am * 1.1; }
    }
    const fade = y < -1.15 ? Math.max(0, (y - Y_BOT) / (0.4)) : 1;
    const head = y > 0.55 ? 1 : y > 0.3 ? (y - 0.3) / 0.25 : 0;
    put(x, y, z, nx, ny, nz, zone, fade, head);
  }

  // 2) Soi than kinh cam: di ngau nhien tu hom uc len co va toa theo xuong don
  let gieo = 0;
  while (b.i < nVo + nThan) {
    gieo++;
    let x = rnd(-0.12, 0.12), y = rnd(-0.45, -0.05), dx = rnd(-0.35, 0.35), dyv = 1;
    const len = 20 + Math.floor(Math.random() * 45);
    const ngang = gieo % 4 === 0;                    // mot phan chay ngang theo xuong don
    if (ngang) { y = rnd(0.12, 0.26); x = rnd(-0.15, 0.15); dx = Math.random() < 0.5 ? -1 : 1; dyv = rnd(-0.35, -0.1); }
    for (let s = 0; s < len && b.i < nVo + nThan; s++) {
      x += dx * 0.01 + rnd(-0.006, 0.006); y += dyv * 0.01 + rnd(-0.003, 0.003);
      if (!ngang && Math.random() < 0.08) dx = rnd(-0.7, 0.7);   // re nhanh
      if (y > 0.62 || Math.abs(x) > 0.9) break;
      const m = mat(y);
      if (Math.abs(x) > m.rx * 0.95) break;
      const z = m.rz * Math.sqrt(Math.max(0, 1 - (x / m.rx) ** 2)) + m.cz + 0.01;
      const sang = 0.35 + Math.random() * 0.35;
      put(x, y, z, 0, 0, 1, sang, 1, y > 0.3 ? (y - 0.3) / 0.3 : 0);
    }
  }

  // 3) Bui sang quanh vien hinh
  for (let k = 0; k < nBui && b.i < n; k++) {
    const xa = 1.03 + Math.pow(Math.random(), 2.2) * 0.3;
    if (Math.random() < 0.55) {                      // quanh dau: vo cau
      const u = rnd(-1, 1), a = Math.random() * TAU, k = Math.sqrt(1 - u * u);
      const nx = k * Math.cos(a), ny = u, nz = k * Math.sin(a);
      put(nx * DAU.rx * xa, DAU.y + ny * DAU.ry * xa, nz * DAU.rz * xa, nx, ny, nz, 0.02, 0.6, 1);
    } else {
      const y = rnd(-1.2, 0.5), m = mat(y), a = Math.random() * TAU;
      put(Math.cos(a) * m.rx * xa, y, Math.sin(a) * m.rz * xa, Math.cos(a), 0, Math.sin(a), 0.02, 0.5 * (y < -0.9 ? 0.4 : 1), 0);
    }
  }
  while (b.i < n) put(0, DAU.y, 0, 0, 0, 1, 0, 0, 1);
  b.nrm = nrm;
  return b;
}
