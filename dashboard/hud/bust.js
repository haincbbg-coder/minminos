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
    // cam va quai ham thu lai o nua duoi dau
    const ham = dy < -0.2 ? 1 - (-0.2 - dy) * 0.28 : 1;
    rxD = DAU.rx * k * ham; rzD = DAU.rz * k;
  }
  const rxCo = 0.25, rzCo = 0.26;
  // vai: loe nhanh ngay duoi co (co thang) roi tron dan thanh bo vai, sau do gan nhu thang dung
  const t = smooth(0.36, -0.5, y);
  const e = 1 - Math.pow(1 - t, 2.4);
  const rxVai = rxCo + (1.5 - rxCo) * e + Math.max(0, -0.5 - y) * 0.04;
  const rzVai = rzCo + (0.52 - rzCo) * e;
  let rx, rz;
  if (y > 0.58) { rx = Math.max(rxD, y < 0.72 ? rxCo : 0); rz = Math.max(rzD, y < 0.72 ? rzCo : 0); }
  else if (y > 0.36) { rx = rxCo; rz = rzCo; }
  else { rx = rxVai; rz = rzVai; }
  return { rx, rz, cz: y < 0.3 ? -0.06 * t : 0 };
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
      if (m.rx > 0.02 && Math.random() < (m.rx + m.rz) / 2.1) break;
    }
    const a = Math.random() * TAU;
    let x = Math.cos(a) * m.rx, z = Math.sin(a) * m.rz + m.cz;
    // phap tuyen: ngang theo elip + thanh phan doc o dau (vom) va vai (doc xuong)
    let ny = 0;
    const dy = (y - DAU.y) / DAU.ry;
    if (y > 0.6) ny = dy * 0.9;
    else if (y < 0.36 && y > -0.7) ny = 1.1 * (1 - smooth(0.3, -0.55, y)) * smooth(0.36, 0.25, y) + 0.6 * smooth(0.3, -0.1, y) * (1 - smooth(-0.2, -0.6, y));
    const nx = Math.cos(a) / m.rx, nz = Math.sin(a) / m.rz;
    // mat truoc: vung am, duong gon song nhe
    let zone = 0.04;
    if (y > 0.72 && z > 0) {
      const fx = x / DAU.rx, fy = (y - (DAU.y - 0.08)) / 0.42;
      const am = Math.exp(-(fx * fx * 1.3 + fy * fy * 0.9)) * Math.pow(Math.max(0, z / (m.rz || 1)), 0.6);
      if (am > 0.06) { y += Math.sin(x * 22 + y * 7) * 0.012 * am; zone = 0.15 + am * 1.1; }
    }
    const fade = y < -0.9 ? Math.max(0, (y - Y_BOT) / (0.65)) : 1;
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
