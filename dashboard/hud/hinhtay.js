// MinMin HUD - hinh minh hoa cu chi tay (0.64.87). Ve bang SVG tai cho, khong tai anh ngoai.
//
// Moi hinh: ban tay nhin tu phia long ban tay, cac ngon duoi / co theo cu chi, them mui ten
// chuyen dong (ngang, doc, mo ra, chum lai) va vong giu (giu yen mot luc).

const NGON = [            // [goc x, goc y, dai khi duoi, huong x khi duoi]
  [23, 31, 19, -2],       // tro
  [29.5, 30, 21, 0],      // giua
  [36, 31, 19, 1.5],      // ap ut
  [42, 33, 14, 3],        // ut
];

function ngon([x, y, dai, dx], duoi) {
  const L = duoi ? dai : 5;
  return `<line x1="${x}" y1="${y}" x2="${x + (duoi ? dx : 0)}" y2="${y - L}"/>`;
}

// kieu: { ngon: [cai, tro, giua, ap, ut] (true = duoi), chum, chuL, mui: "ngang"|"doc"|"mo"|"chum"|"vuot",
//         giu: true (vong giu), hai: true (hai tay), bam: true (tia bam) }
export function hinhTay(k = {}) {
  if (k.hai) {
    return `<svg viewBox="0 0 64 64" class="pic" aria-hidden="true"><g transform="translate(-6,6) scale(.62)">${than(k)}</g><g transform="translate(70,6) scale(-.62,.62)">${than(k)}</g>` +
      `<path class="mui" d="M22 6v-4M42 6v-4M20 4l2-3 2 3M40 4l2-3 2 3"/></svg>`;
  }
  return `<svg viewBox="0 0 64 64" class="pic" aria-hidden="true">${than(k)}${mui(k)}</svg>`;
}

function than(k) {
  const n = k.ngon || [false, false, false, false, false];
  let s = `<g class="tay"><rect x="19" y="30" width="26" height="24" rx="8"/>`;
  if (k.chum) {
    s += `<line x1="23" y1="31" x2="17" y2="19"/><line x1="20" y1="47" x2="15.5" y2="21"/>`;
  } else {
    s += ngon(NGON[0], n[1]);
    if (n[0] || k.chuL) s += `<line x1="20" y1="47" x2="${k.chuL ? 5 : 9}" y2="${k.chuL ? 43 : 35}"/>`;
    else s += `<line x1="20" y1="47" x2="27" y2="41"/>`;
  }
  for (let i = 1; i < 4; i++) s += ngon(NGON[i], n[i + 1]);
  s += `</g>`;
  if (k.chum) s += `<circle class="sang" cx="16.3" cy="20" r="3.2"/>`;
  return s;
}

function mui(k) {
  let s = "";
  const m = k.mui;
  if (m === "ngang") s += `<path class="mui" d="M4 60h56M9 56l-5 4 5 4M55 56l5 4-5 4"/>`;
  if (m === "vuot") s += `<path class="mui" d="M58 14H38M43 9l-5 5 5 5"/><path class="mui mo" d="M6 14h14M15 9l5 5-5 5"/>`;
  if (m === "doc") s += `<path class="mui" d="M56 8v40M52 13l4-5 4 5M52 43l4 5 4-5"/>`;
  if (m === "mo") s += `<path class="mui" d="M13 15 5 7M5 12V7h5M22 8l5-6M22 3h5v5"/>`;
  if (m === "chum") s += `<path class="mui" d="M4 6l7 8M11 9v5H6M28 2l-5 7M23 4v5h5"/>`;
  if (m === "tro") s += `<path class="mui" d="M34 10h22M50 5l6 5-6 5M56 20l-10 8"/>`;
  if (k.giu) s += `<circle class="giu" cx="54" cy="52" r="7"/><path class="giu" d="M54 48v4l3 2"/>`;
  if (k.bam) s += `<path class="mui" d="M8 12l-4-3M16 6l1-5M6 21l-5 1"/>`;
  return s;
}

// Tat ca cu chi co hinh: HUD va may tinh
export const HINH = {
  Open_Palm: { ngon: [true, true, true, true, true] },
  Pointing_Up: { ngon: [false, true, false, false, false], mui: "tro" },
  Closed_Fist: { mui: "ngang" },
  Pinch: { chum: true, mui: "doc" },
  Victory: { ngon: [false, true, true, false, false], giu: true },
  Thumb_Up: { ngon: [true, false, false, false, false], giu: true },
  TwoHands: { ngon: [true, true, true, true, true], hai: true },
  M_Move: { ngon: [false, true, false, false, false], mui: "tro" },
  M_Click: { chum: true, bam: true },
  M_ZoomIn: { chuL: true, ngon: [true, true, false, false, false], mui: "mo" },
  M_ZoomOut: { chum: true, mui: "chum" },
  M_Scroll: { ngon: [false, true, true, false, false], mui: "doc" },
  M_Swipe: { ngon: [true, true, true, true, true], mui: "vuot" },
  M_Pause: { giu: true },
};
