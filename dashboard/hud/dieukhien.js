// MinMin HUD - dieu khien MAY TINH bang tay (0.64.87).
//
// Bo muon luot web, doc Word ma khong cham chuot. HUD nhan dien tay (vision.js), bien cu chi
// thanh lenh chuot / ban phim, gui toi "MinMin Tay" - mot chuong trinh nho chay tren may Windows
// cua bo (dashboard/hud/tay/minmin-tay.py), nghe o http://localhost:47700 va bam that.
//
//   Duoi ngon tro, di tay ........... di chuot
//   Chum nhanh cai + tro roi tha ..... bam chuot trai
//   Chum giu nua giay roi MO RA ...... phong to (Ctrl + lan chuot)
//   Chu L (cai + tro) roi CHUM LAI ... thu nho
//   Chu V dua len / xuong ............ cuon trang (nhu vuot dien thoai: dua len = doc tiep)
//   Xoe tay vuot nhanh sang trai ...... trang / anh / slide TIEP (phim →); sang phai = TRUOC
//   Nam tay giu 1,5 giay .............. tam dung / tiep tuc (de gai dau, uong nuoc khong bam nham)

const khoang = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const duoi = (lm, dau, giua) => khoang(lm[0], lm[dau]) > khoang(lm[0], lm[giua]) * 1.12;

// Do mo giua dau ngon cai va dau ngon tro, tinh theo co ban tay (khong phu thuoc xa gan camera)
export function doMo(lm) { return khoang(lm[4], lm[8]) / (khoang(lm[0], lm[9]) || 1); }
// Ba ngon giua, ap ut, ut deu co lai
export function baNgonCo(lm) { return !duoi(lm, 12, 10) && !duoi(lm, 16, 14) && !duoi(lm, 20, 18); }
// Ngon cai choi ra ngoai (chu L), khong phai gap vao long ban tay
export function caiChoi(lm) { return khoang(lm[4], lm[5]) / (khoang(lm[0], lm[9]) || 1) > 0.6; }

export const CHUM = 0.28;          // do mo duoi nguong = dang chum
export const BUOC_ZOOM = 0.16;     // mo them / chum bot moi buoc = mot nac phong
export const BUOC_CUON = 0.035;    // tay di doc bao nhieu (ti le man hinh) = mot nac cuon

// Ten cu chi may tinh -> chu hien tren camera va bang huong dan
export const CU_CHI_MAY = {
  M_Move: "Trỏ · di chuột",
  M_Click: "Chụm nhanh · bấm chuột",
  M_ZoomIn: "Mở ra · phóng to",
  M_ZoomOut: "Chụm lại · thu nhỏ",
  M_Zoom: "Chụm giữ · sẵn sàng phóng",
  M_Scroll: "Chữ V · cuộn trang",
  M_Swipe: "Vuốt · trang trước / sau",
  M_Pause: "Nắm tay · tạm dừng",
};

// Anh xa vi tri ngon tro trong khung camera -> toa do man hinh 0..1. Chi dung vung giua khung
// (tay khong the voi toi mep camera) de voi toi duoc mep man hinh.
export function anhXa(x, y) {
  const c = (v) => Math.max(0, Math.min(1, v));
  return [c((x - 0.2) / 0.6), c((y - 0.15) / 0.55)];
}

export class DieuKhienMay {
  // gui(lenh): gui toi MinMin Tay; bao(ten): cu chi vua lam (cho bang huong dan + nhat ky)
  constructor({ gui, bao } = {}) {
    this.gui = gui || (() => {});
    this.bao = bao || (() => {});
    this.dung = false;              // dang tam dung
    this._reset();
  }

  _reset() {
    this._chum = null; this.zoom = null; this._v = null; this._vet = []; this._nam = 0; this._zCho = 0;
  }

  // Mat tay: huy moi thao tac dang do
  mat() { this._reset(); }

  // lm: 21 diem ban tay (TOA DO MAN HINH, da lat guong); gest: cu chi on dinh; now: ms.
  // Tra ve ten cu chi dang lam (khoa trong CU_CHI_MAY) hoac "".
  capNhat(lm, gest, now) {
    if (!lm) { this.mat(); return ""; }
    // Nam tay giu 1,5 giay: bat / tat tam dung
    if (gest === "Closed_Fist") {
      if (!this._nam) this._nam = now;
      if (now - this._nam > 1500 && now - (this._namAt || 0) > 2500) {
        this._namAt = now; this.dung = !this.dung; this._reset();
        this.bao("M_Pause", this.dung ? "Tạm dừng điều khiển máy" : "Tiếp tục điều khiển máy");
      }
      return "M_Pause";
    }
    this._nam = 0;
    if (this.dung) return "";

    const mo = doMo(lm), co = baNgonCo(lm);

    // ---- Phong to / thu nho ----
    if (this.zoom) {
      if (!co) { this.zoom = null; }            // xoe het tay ra = thoat
      else {
        const s = Math.round((mo - this.zoom.goc) / BUOC_ZOOM);
        let ten = "M_Zoom";
        while (s > this.zoom.buoc) { this.zoom.buoc++; this.gui({ t: "zoom", d: 1 }); ten = "M_ZoomIn"; this.bao(ten); }
        while (s < this.zoom.buoc) { this.zoom.buoc--; this.gui({ t: "zoom", d: -1 }); ten = "M_ZoomOut"; this.bao(ten); }
        return ten;
      }
    }
    const chum = mo < CHUM;
    const laL = co && mo > 0.8 && caiChoi(lm) && duoi(lm, 8, 6);
    if (co && (chum || laL)) {
      if (!this._zCho) this._zCho = now;
      if (now - this._zCho > (chum ? 450 : 300)) {
        this.zoom = { goc: mo, buoc: 0 }; this._chum = null; this._zCho = 0;
        return "M_Zoom";
      }
    } else this._zCho = 0;

    // ---- Bam chuot: chum nhanh roi tha ----
    if (chum) {
      if (!this._chum) this._chum = now;
      return "";                                 // dang chum: giu yen con tro de bam trung
    }
    if (this._chum) {
      const lau = now - this._chum; this._chum = null;
      if (lau < 450) { this.gui({ t: "click" }); this.bao("M_Click"); return "M_Click"; }
    }

    // ---- Cuon: chu V di len / xuong ----
    if (gest === "Victory") {
      const y = (lm[8].y + lm[12].y) / 2;
      if (!this._v) this._v = { y };
      const n = Math.trunc((y - this._v.y) / BUOC_CUON);
      if (n) {
        // dua tay LEN (y giam) = cuon XUONG doc tiep, nhu vuot dien thoai
        // (n am -> lan chuot am = cuon xuong tren Windows)
        this.gui({ t: "scroll", n: Math.max(-6, Math.min(6, n)) }); this._v.y += n * BUOC_CUON;
        this.bao("M_Scroll");
      }
      return "M_Scroll";
    }
    this._v = null;

    // ---- Vuot: xoe tay di nhanh ngang ----
    if (gest === "Open_Palm") {
      const x = lm[9].x;
      this._vet.push([x, now]);
      while (this._vet.length && now - this._vet[0][1] > 350) this._vet.shift();
      const dx = x - this._vet[0][0];
      if (Math.abs(dx) > 0.2 && now - (this._vuotAt || 0) > 800) {
        this._vuotAt = now; this._vet = [];
        // vuot sang TRAI = trang TIEP (nhu lat anh tren dien thoai)
        this.gui({ t: "key", k: dx < 0 ? "right" : "left" });
        this.bao("M_Swipe", dx < 0 ? "Vuốt trái · trang tiếp" : "Vuốt phải · trang trước");
        return "M_Swipe";
      }
      return "";
    }
    this._vet = [];

    // ---- Di chuot: duoi ngon tro ----
    if (gest === "Pointing_Up" || (duoi(lm, 8, 6) && co)) {
      const [x, y] = anhXa(lm[8].x, lm[8].y);
      const cu = this._chuot;
      if (!cu || Math.hypot(x - cu[0], y - cu[1]) > 0.002) {
        if (!cu || now - (this._chuotAt || 0) > 30) {
          this._chuot = [x, y]; this._chuotAt = now;
          this.gui({ t: "move", x: +x.toFixed(4), y: +y.toFixed(4) });
        }
      }
      return "M_Move";
    }
    return "";
  }
}

// ---- Ket noi toi MinMin Tay tren may bo ----
const KEY_MA = "minmin.hud.taytoken";
export class TayMay {
  constructor(url = "http://localhost:47700") {
    this.url = url;
    try { this.ma = localStorage.getItem(KEY_MA) || ""; } catch (e) { this.ma = ""; }
    this.ok = false; this._dang = false; this._cho = null; this.loi = "";
    this.onGui = () => {};          // (lenh, ok) - cho Luong phan tich
  }
  // Moi lan goi co han: MinMin Tay tat giua chung (hoac trinh duyet dang treo hop hoi quyen)
  // thi fetch khong duoc treo mai. Truoc 0.64.89 mot fetch treo la khoa cung hang doi: bat lai
  // MinMin Tay cung khong dieu khien duoc nua (bo bao 30/09).
  _fetch(duong, init = {}, ms = 2000) {
    const ac = typeof AbortController !== "undefined" ? new AbortController() : null;
    const t = ac ? setTimeout(() => ac.abort(), ms) : null;
    return fetch(this.url + duong, { ...init, cache: "no-store", signal: ac ? ac.signal : undefined }).finally(() => clearTimeout(t));
  }
  datMa(ma) { this.ma = String(ma || "").trim(); try { localStorage.setItem(KEY_MA, this.ma); } catch (e) {} }

  // Kiem tra: tra { ok, ly_do } - ly_do: "khong_chay" | "sai_ma" | ""
  async ping() {
    try {
      const r = await this._fetch("/ping", { headers: { "x-minmin-token": this.ma } }, 3000);
      if (r.status === 401) { this.ok = false; return { ok: false, ly_do: "sai_ma" }; }
      const j = await r.json().catch(() => ({}));
      this.ok = !!j.ok;
      return { ok: this.ok, ly_do: this.ok ? "" : "khong_chay", may: j.may || "", man: j.man || "" };
    } catch (e) { this.ok = false; return { ok: false, ly_do: "khong_chay" }; }
  }

  // Gui lenh. Lenh "move" gui lien tuc: dang co mot lenh chua xong thi chi giu lenh MOI NHAT.
  gui(lenh) {
    if (!this.ok) return;
    if (this._dang) { if (lenh.t === "move") this._cho = lenh; else (this._hang ||= []).push(lenh); return; }
    this._dang = true;
    this._fetch("/act", { method: "POST", headers: { "content-type": "application/json", "x-minmin-token": this.ma }, body: JSON.stringify(lenh) })
      .then(r => { if (r.status === 401) { this.ok = false; this.loi = "sai_ma"; } this.onGui(lenh, r.ok); })
      .catch(() => { this.ok = false; this.loi = "khong_chay"; this.onGui(lenh, false); this._hang = []; this._cho = null; })
      .finally(() => {
        this._dang = false;
        const tiep = (this._hang && this._hang.shift()) || this._cho;
        if (tiep === this._cho) this._cho = null;
        if (tiep) this.gui(tiep);
      });
  }
}

// Tep .bat tao ngay trong trinh duyet, gan san dia chi MinMin nay: tai ban moi nhat cua
// minmin-tay.py, tu cai Python neu may chua co, chi nhan lenh tu dung trang nay (--nguon).
export function taoBat(origin) {
  const py = `"%D%\\minmin-tay.py"`;
  const L = [
    "@echo off", "chcp 65001 >nul", "title MinMin Tay",
    'set "D=%LOCALAPPDATA%\\MinMinTay"', 'if not exist "%D%" mkdir "%D%"',
    "echo Dang tai MinMin Tay tu " + origin + " ...",
    `curl -fsSL "${origin}/static/hud/tay/minmin-tay.py" -o "%D%\\moi.py" && move /y "%D%\\moi.py" ${py} >nul`,
    `if not exist ${py} (echo Khong tai duoc MinMin Tay. Kiem tra mang roi thu lai. & pause & exit /b 1)`,
    `where py >nul 2>nul && (py -3 ${py} --nguon ${origin} & pause & exit /b)`,
    `for /f "delims=" %%P in ('where python 2^>nul ^| findstr /v /i WindowsApps') do ("%%P" ${py} --nguon ${origin} & pause & exit /b)`,
    "echo May chua co Python. Dang cai Python 3.12, mat 1-2 phut...",
    "winget install -e --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements",
    "echo.", "echo Cai xong. Dong cua so nay roi bam dup MinMin-Tay.bat lan nua.", "pause",
  ];
  return L.join("\r\n") + "\r\n";
}
