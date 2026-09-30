// MinMin HUD - mat nhin (0.64.84): camera may tinh / dien thoai.
//
//  - Theo mat: MinMin quay dau nhin theo khuon mat bo truoc camera.
//  - Cu chi tay (dieu khien khong cham):
//      xoe tay .......... dau nhin theo ngon tro
//      chi 1 ngon ....... VE len man hinh bang ngon tro (net sang)
//      nam tay .......... nam lay va xoay nguoi trai / phai
//      chum 2 ngon ...... (cai + tro) keo len / xuong de phong to / thu nho
//      chu V ............ doi hinh chan dung / qua cau
//  - "Nhin": chup khung hinh (kem net ve) gui MinMin mo ta, doc chu, nhan dien do vat...
//
//  - Toan than (0.64.85): 33 diem khop co the. Canh tay robot bat chuoc tay bo; gio CA HAI
//    TAY len qua dau = goi MinMin nghe (khong can noi tu goi).
//  - Moi truong (0.64.85): nhan ra do vat quanh bo (nguoi, dien thoai, coc, ghe...) - ~80 loai.
//  - Chu nhan (0.64.85): bo dang ky khuon mat mot lan; MinMin nhan ra bo, bao nguoi la.
//    Dac trung khuon mat chi luu trong trinh duyet cua may nay (localStorage), khong gui di dau.
//
// Nhan dien chay HOAN TOAN trong trinh duyet (MediaPipe, ma nguon mo cua Google). Hinh anh
// KHONG roi may, tru khi bo bam "Nhin" / ra lenh "Min Min nhin xem" - luc do MOT anh chup
// duoc gui len MinMin cua chinh bo.

const MP_VER = "1.0.1";
const MP_CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VER}`;
const M_GESTURE = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";
const M_FACE = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";
const M_POSE = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task";
const M_OBJ = "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite";
const FA_VER = "1.7.15";
const FA_CDN = `https://cdn.jsdelivr.net/npm/@vladmandic/face-api@${FA_VER}`;
const KEY_CHU = "minmin.hud.owner";
const NGUONG_CHU = 0.5;             // khoang cach dac trung khuon mat < nguong = cung mot nguoi

// Ten do vat (bo COCO 80 loai) -> tieng Viet cho nhung loai hay gap
export const DO_VAT = {
  person: "người", "cell phone": "điện thoại", remote: "điều khiển", laptop: "laptop", keyboard: "bàn phím",
  mouse: "chuột", tv: "màn hình", cup: "cốc", bottle: "chai", chair: "ghế", couch: "sofa", bed: "giường",
  "dining table": "bàn", book: "sách", clock: "đồng hồ", scissors: "kéo", "potted plant": "chậu cây",
  vase: "bình hoa", handbag: "túi xách", backpack: "ba lô", umbrella: "ô", tie: "cà vạt", suitcase: "vali",
  cat: "mèo", dog: "chó", bird: "chim", car: "ô tô", motorcycle: "xe máy", bicycle: "xe đạp", knife: "dao",
  spoon: "thìa", fork: "nĩa", bowl: "bát", "wine glass": "ly", banana: "chuối", apple: "táo", orange: "cam",
  refrigerator: "tủ lạnh", microwave: "lò vi sóng", sink: "bồn rửa", toothbrush: "bàn chải", "hair drier": "máy sấy",
  "teddy bear": "gấu bông", "sports ball": "quả bóng", toilet: "bồn cầu", oven: "lò nướng", pizza: "pizza", cake: "bánh",
};
export const tenDoVat = (en) => DO_VAT[en] || en;

// Goc canh tay tu diem khop (toa do man hinh, y huong xuong) -> goc quay quanh truc z cua robot.
// Canh tay tha xuong = 0. Tra ve [goc canh tay tren, goc cang tay so voi canh tay tren].
export function gocTay(vai, khuyu, co) {
  // goc chuan cua vector a->b trong he truc y huong LEN (man hinh y huong xuong nen doi dau)
  const ang = (a, b) => Math.atan2(-(b.y - a.y), b.x - a.x);
  const chuan = (x) => Math.atan2(Math.sin(x), Math.cos(x));
  const tren = chuan(ang(vai, khuyu) + Math.PI / 2);         // so voi huong thang xuong
  const cang = chuan(ang(khuyu, co) - ang(vai, khuyu));
  return [tren, cang];
}

export function khoangCach(a, b) {
  let s = 0; for (let i = 0; i < a.length; i++) { const d = a[i] - b[i]; s += d * d; }
  return Math.sqrt(s);
}

// Ten cu chi -> chu hien cho bo
export const CU_CHI = {
  Open_Palm: "Xòe tay · nhìn theo",
  Pointing_Up: "Chỉ tay · đang vẽ",
  Closed_Fist: "Nắm tay · xoay",
  Victory: "Chữ V · đổi hình",
  Pinch: "Chụm ngón · phóng to",
};

const khoang = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

// Chum ngon: dau ngon cai (4) sat dau ngon tro (8), so voi co ban tay (0 -> 9)
export function laChum(lm) {
  if (!lm || lm.length < 21) return false;
  const tay = khoang(lm[0], lm[9]) || 1;
  return khoang(lm[4], lm[8]) / tay < 0.28;
}

export class Vision {
  get ready() { return !!this._g; }

  constructor(opts) {
    this.video = opts.video;          // <video> xem truoc (nho, lat guong)
    this.overlay = opts.overlay;      // <canvas> ve diem ban tay len xem truoc
    this.ink = opts.ink;              // <canvas> toan man hinh de ve
    this.scene = opts.scene;
    this.onGesture = opts.onGesture || (() => {});
    this.onStatus = opts.onStatus || (() => {});
    this.onForm = opts.onForm || (() => {});
    this.onWake = opts.onWake || (() => {});
    this.onScene = opts.onScene || (() => {});     // danh sach do vat nhin thay
    this.onOwner = opts.onOwner || (() => {});     // "owner" | "stranger" | "" (khong co ai)
    this.mimic = true;                              // robot bat chuoc canh tay
    this.objects = []; this.pose = null; this.who = ""; this._frame = 0;
    this.on = false;
    this.facing = "user";             // user = camera truoc, environment = camera sau
    this.stroke = null;
    this.strokes = [];
    this._g = null; this._f = null; this._last = -1;
    this._fist = null; this._pinch = null; this._vAt = 0; this._gesture = "";
    this._inkResize();
    addEventListener("resize", () => this._inkResize());
  }

  async start() {
    if (this.on) return true;
    if (!navigator.mediaDevices?.getUserMedia) { this.onStatus("Trình duyệt này không cho dùng camera.", true); return false; }
    this.onStatus("Đang mở camera…");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: this.facing, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    } catch (e) {
      const bi = e && (e.name === "NotAllowedError" || e.name === "SecurityError");
      this.onStatus(bi ? "Bố chưa cho phép camera. Bấm biểu tượng ổ khóa cạnh địa chỉ web → Camera → Cho phép." : "Không mở được camera: " + (e.message || e.name), true);
      return false;
    }
    this.video.srcObject = this.stream;
    this.video.classList.toggle("mirror", this.facing === "user");
    await this.video.play().catch(() => {});
    this.on = true;
    this.onStatus("Đang tải bộ nhận diện tay và khuôn mặt…");
    try { await this._loadModels(); } catch (e) {
      this.onStatus("Camera đã bật, nhưng chưa tải được bộ nhận diện (cần mạng). Vẫn dùng được nút Nhìn.", true);
    }
    if (this._g) this.onStatus("");
    this._tick = this._tick.bind(this);
    requestAnimationFrame(this._tick);
    return true;
  }

  stop() {
    this.on = false;
    try { this.stream?.getTracks().forEach(t => t.stop()); } catch (e) {}
    this.video.srcObject = null;
    this.scene.external = null;
    this.scene.setArms(null, null);
    this.objects = []; this.onScene([]); this.who = ""; this.onOwner("");
    const c = this.overlay.getContext("2d"); c.clearRect(0, 0, this.overlay.width, this.overlay.height);
  }

  async flip() {
    this.facing = this.facing === "user" ? "environment" : "user";
    if (this.on) { this.stop(); await this.start(); }
    return this.facing;
  }

  async _loadModels() {
    if (this._g) return;
    const mp = await import(/* webpackIgnore: true */ `${MP_CDN}/vision_bundle.mjs`);
    const files = await mp.FilesetResolver.forVisionTasks(`${MP_CDN}/wasm`);
    const make = async (delegate) => {
      this._g = await mp.GestureRecognizer.createFromOptions(files, {
        baseOptions: { modelAssetPath: M_GESTURE, delegate }, runningMode: "VIDEO", numHands: 1 });
      this._f = await mp.FaceDetector.createFromOptions(files, {
        baseOptions: { modelAssetPath: M_FACE, delegate }, runningMode: "VIDEO" });
      // hai bo sau la phan them: hong thi van chay tay + mat
      this._p = await mp.PoseLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: M_POSE, delegate }, runningMode: "VIDEO", numPoses: 1 }).catch(() => null);
      this._o = await mp.ObjectDetector.createFromOptions(files, {
        baseOptions: { modelAssetPath: M_OBJ, delegate }, runningMode: "VIDEO", scoreThreshold: 0.45, maxResults: 8 }).catch(() => null);
    };
    try { await make("GPU"); } catch (e) { await make("CPU"); }
  }

  _tick(now) {
    if (!this.on) return;
    requestAnimationFrame(this._tick);
    const v = this.video;
    if (!this._g || v.readyState < 2 || v.currentTime === this._last) return;
    this._last = v.currentTime;
    let hand = null, gest = "", face = null;
    try {
      const r = this._g.recognizeForVideo(v, now);
      hand = r.landmarks?.[0] || null;
      gest = r.gestures?.[0]?.[0]?.categoryName || "";
    } catch (e) {}
    this._frame++;
    try { face = this._f.detectForVideo(v, now).detections?.[0]?.boundingBox || null; } catch (e) {}
    if (this._p && this._frame % 2 === 0) {
      try { this.pose = this._p.detectForVideo(v, now).landmarks?.[0] || null; } catch (e) { this.pose = null; }
      this._applyPose(this.pose);
    }
    if (this._o && this._frame % 12 === 0) {
      try {
        const r = this._o.detectForVideo(v, now).detections || [];
        this.objects = r.map(d => ({ name: d.categories?.[0]?.categoryName || "", score: d.categories?.[0]?.score || 0, box: d.boundingBox }))
          .filter(d => d.name);
        this.onScene(this.objects);
      } catch (e) {}
    }
    if (this._fa && now - (this._faAt || 0) > 1500) { this._faAt = now; this._nhanChu(); }
    if (hand && laChum(hand)) gest = "Pinch";
    this._apply(hand, gest, face);
    this._drawPreview(hand, face);
  }

  // ---- Toan than ----
  _applyPose(lm) {
    const s = this.scene;
    if (!lm || !this.mimic) { s.setArms(null, null); this._tayCao = 0; return; }
    const P = (i) => ({ x: this._sx(lm[i].x), y: lm[i].y, v: lm[i].visibility ?? 1 });
    // 11/13/15 = vai/khuyu/co tay trai (cua nguoi), 12/14/16 = phai. Chia theo PHIA MAN HINH.
    const a = [P(11), P(13), P(15)], b = [P(12), P(14), P(16)];
    const [trai, phai] = a[0].x < b[0].x ? [a, b] : [b, a];
    const ok = (t) => t.every(p => p.v > 0.5);
    s.setArms(ok(trai) ? gocTay(...trai) : null, ok(phai) ? gocTay(...phai) : null);
    // gio ca hai tay qua dau (co tay cao hon mui) giu 0.6 giay = goi MinMin
    const mui = lm[0];
    const cao = ok(trai) && ok(phai) && trai[2].y < mui.y && phai[2].y < mui.y;
    if (cao) {
      this._tayCao = this._tayCao || performance.now();
      if (performance.now() - this._tayCao > 600 && performance.now() - (this._wakeAt || 0) > 4000) {
        this._wakeAt = performance.now(); this.onWake();
      }
    } else this._tayCao = 0;
  }

  // ---- Chu nhan ----
  owner() { try { return JSON.parse(localStorage.getItem(KEY_CHU) || "null"); } catch (e) { return null; } }
  forgetOwner() { try { localStorage.removeItem(KEY_CHU); } catch (e) {} this.who = ""; this.onOwner(""); }

  async _loadFaceApi() {
    if (this._fa) return this._fa;
    const fa = await import(/* webpackIgnore: true */ `${FA_CDN}/dist/face-api.esm.js`);
    const url = `${FA_CDN}/model/`;
    await fa.nets.tinyFaceDetector.loadFromUri(url);
    await fa.nets.faceLandmark68TinyNet.loadFromUri(url);
    await fa.nets.faceRecognitionNet.loadFromUri(url);
    this._faOpt = new fa.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 });
    this._fa = fa;
    return fa;
  }

  async _descriptor() {
    const fa = this._fa;
    const r = await fa.detectSingleFace(this.video, this._faOpt).withFaceLandmarks(true).withFaceDescriptor();
    return r ? Array.from(r.descriptor) : null;
  }

  // Dang ky: lay 6 mau khuon mat trong ~4 giay (bo nhin camera, xoay dau nhe)
  async enrollOwner(ten, onTien) {
    if (!this.on) throw new Error("Bật camera trước khi đăng ký chủ nhân.");
    await this._loadFaceApi();
    const mau = [];
    for (let k = 0; k < 20 && mau.length < 6; k++) {
      const d = await this._descriptor().catch(() => null);
      if (d) { mau.push(d); onTien && onTien(mau.length, 6); }
      await new Promise(r => setTimeout(r, 450));
    }
    if (mau.length < 3) throw new Error("Không thấy rõ khuôn mặt. Bố ngồi đủ sáng, nhìn thẳng camera rồi thử lại.");
    try { localStorage.setItem(KEY_CHU, JSON.stringify({ ten: ten || "Bố", mau, luc: Date.now() })); } catch (e) {}
    this.who = ""; this._nhanChu();
    return mau.length;
  }

  async startOwnerWatch() {
    if (!this.owner()) return false;
    try { await this._loadFaceApi(); return true; } catch (e) { return false; }
  }

  async _nhanChu() {
    const chu = this.owner();
    if (!chu || !this.on || this._dangNhan) return;
    this._dangNhan = true;
    try {
      const d = await this._descriptor();
      let who = "";
      if (d) {
        const gan = Math.min(...chu.mau.map(m => khoangCach(m, d)));
        who = gan < NGUONG_CHU ? "owner" : "stranger";
      }
      // nguoi la phai thay 2 lan lien tiep moi bao, tranh bao nham khi quay mat
      if (who === "stranger" && this._nghiLa !== "stranger") { this._nghiLa = "stranger"; return; }
      this._nghiLa = who;
      if (who !== this.who) { this.who = who; this.onOwner(who, chu.ten); }
    } catch (e) {} finally { this._dangNhan = false; }
  }

  // Tom tat nhung gi dang thay, de gui kem cau hoi
  describeScene() {
    const dem = {};
    for (const o of this.objects) { const t = tenDoVat(o.name); dem[t] = (dem[t] || 0) + 1; }
    const ds = Object.entries(dem).map(([t, n]) => (n > 1 ? `${n} ${t}` : t));
    const chu = this.owner();
    const ai = this.who === "owner" ? `người trước camera là chủ nhân (${chu?.ten || "Bố"})` : this.who === "stranger" ? "có người lạ trước camera" : "";
    return [ds.length ? "máy nhìn sơ bộ thấy: " + ds.join(", ") : "", ai].filter(Boolean).join("; ");
  }

  // Toa do cua camera (0..1) -> toa do man hinh; camera truoc thi lat guong cho tu nhien
  _sx(x) { return this.facing === "user" ? 1 - x : x; }

  _apply(hand, gest, face) {
    const s = this.scene;
    if (gest !== this._gesture) { this._gesture = gest; this.onGesture(gest && CU_CHI[gest] ? CU_CHI[gest] : ""); }
    if (gest !== "Pointing_Up" && this.stroke) this.stroke = null;
    if (gest !== "Closed_Fist") this._fist = null;
    if (gest !== "Pinch") this._pinch = null;

    if (hand) {
      s.external = "hand";
      const tip = hand[8], x = this._sx(tip.x), y = tip.y;
      if (gest === "Pointing_Up") {
        if (!this.stroke) { this.stroke = []; this.strokes.push(this.stroke); }
        this.stroke.push([x * innerWidth, y * innerHeight, performance.now()]);
        this._inkDraw();
      } else if (gest === "Closed_Fist") {
        const cx = this._sx(hand[9].x);
        if (!this._fist) this._fist = { x: cx, spin: s.spin };
        s.setSpin(this._fist.spin + (cx - this._fist.x) * 6);
      } else if (gest === "Pinch") {
        const py = (hand[4].y + hand[8].y) / 2;
        if (!this._pinch) this._pinch = { y: py, zoom: s.zoom };
        s.zoom = Math.max(0.5, Math.min(2.4, this._pinch.zoom * Math.exp((this._pinch.y - py) * 3)));
        s._lastInput = performance.now();
      } else if (gest === "Victory" && performance.now() - this._vAt > 1500) {
        this._vAt = performance.now();
        this.onForm(s.toggleForm());
      }
      if (gest !== "Closed_Fist") s.setLook(x * 2 - 1, y * 2 - 1);
    } else if (face) {
      // khong co tay: nhin theo mat bo
      s.external = "face";
      const vw = this.video.videoWidth || 1, vh = this.video.videoHeight || 1;
      const fx = (face.originX + face.width / 2) / vw, fy = (face.originY + face.height / 2) / vh;
      s.setLook(this._sx(fx) * 2 - 1, fy * 2 - 1);
    } else {
      s.external = null;
    }
  }

  _drawPreview(hand, face) {
    const c = this.overlay, g = c.getContext("2d");
    const w = c.width = c.clientWidth * (devicePixelRatio || 1), h = c.height = c.clientHeight * (devicePixelRatio || 1);
    g.clearRect(0, 0, w, h);
    const vw = this.video.videoWidth || 1, vh = this.video.videoHeight || 1;
    if (face) {
      g.strokeStyle = "rgba(111,224,200,.9)"; g.lineWidth = 2 * (devicePixelRatio || 1);
      const x0 = this._sx((face.originX + face.width) / vw), x1 = this._sx(face.originX / vw);
      g.strokeRect(Math.min(x0, x1) * w, face.originY / vh * h, Math.abs(x1 - x0) * w, face.height / vh * h);
    }
    const d = devicePixelRatio || 1;
    if (this.pose) {
      const L = this.pose, noi = [[11,12],[11,13],[13,15],[12,14],[14,16],[11,23],[12,24],[23,24],[23,25],[24,26],[25,27],[26,28]];
      g.strokeStyle = "rgba(143,107,255,.85)"; g.lineWidth = 2 * d;
      for (const [a, b] of noi) {
        if ((L[a].visibility ?? 1) < 0.5 || (L[b].visibility ?? 1) < 0.5) continue;
        g.beginPath(); g.moveTo(this._sx(L[a].x) * w, L[a].y * h); g.lineTo(this._sx(L[b].x) * w, L[b].y * h); g.stroke();
      }
    }
    for (const o of this.objects) {
      if (!o.box || o.name === "person") continue;
      const bx = o.box, x0 = this._sx(bx.originX / vw), x1 = this._sx((bx.originX + bx.width) / vw);
      const X = Math.min(x0, x1) * w, Y = bx.originY / vh * h, W = Math.abs(x1 - x0) * w, Hh = bx.height / vh * h;
      g.strokeStyle = "rgba(255,207,90,.9)"; g.lineWidth = 1.5 * d; g.strokeRect(X, Y, W, Hh);
      g.fillStyle = "rgba(255,207,90,.95)"; g.font = `${11 * d}px system-ui`; g.fillText(tenDoVat(o.name), X + 3 * d, Y + 12 * d);
    }
    if (hand) {
      g.fillStyle = "#ffb066";
      for (const p of hand) { g.beginPath(); g.arc(this._sx(p.x) * w, p.y * h, 2.5 * (devicePixelRatio || 1), 0, 7); g.fill(); }
    }
  }

  // ---- Net ve ----
  _inkResize() {
    const c = this.ink; if (!c) return;
    c.width = innerWidth * (devicePixelRatio || 1); c.height = innerHeight * (devicePixelRatio || 1);
    this._inkDraw();
  }
  clearInk() { this.strokes = []; this.stroke = null; this._inkDraw(); }
  hasInk() { return this.strokes.some(s => s.length > 1); }
  _inkDraw() {
    const c = this.ink; if (!c) return;
    const g = c.getContext("2d"), d = devicePixelRatio || 1;
    g.clearRect(0, 0, c.width, c.height);
    g.lineCap = g.lineJoin = "round";
    for (const s of this.strokes) {
      if (s.length < 2) continue;
      for (const [w, col] of [[14, "rgba(255,154,60,.18)"], [5, "rgba(255,190,120,.85)"], [2, "#fff4e2"]]) {
        g.strokeStyle = col; g.lineWidth = w * d;
        g.beginPath();
        // lam muot: diem giua cua hai diem lien tiep
        g.moveTo(s[0][0] * d, s[0][1] * d);
        for (let i = 1; i < s.length - 1; i++) {
          const mx = (s[i][0] + s[i + 1][0]) / 2, my = (s[i][1] + s[i + 1][1]) / 2;
          g.quadraticCurveTo(s[i][0] * d, s[i][1] * d, mx * d, my * d);
        }
        g.lineTo(s[s.length - 1][0] * d, s[s.length - 1][1] * d);
        g.stroke();
      }
    }
  }

  // Ve bang chuot khi khong co camera: giu Shift + keo
  attachMouseInk() {
    let on = null;
    addEventListener("pointerdown", (e) => {
      if (!this.drawMode || e.button !== 0 || e.target.closest?.("button, input, form, .card, .tools")) return;
      on = []; this.strokes.push(on); on.push([e.clientX, e.clientY, performance.now()]);
    });
    addEventListener("pointermove", (e) => { if (on) { on.push([e.clientX, e.clientY, performance.now()]); this._inkDraw(); } });
    addEventListener("pointerup", () => { on = null; });
  }

  // Chup khung hinh camera (kem net ve) thanh Blob JPEG de gui MinMin
  async snapshot() {
    const v = this.video;
    const W = this.on && v.videoWidth ? v.videoWidth : innerWidth, Hh = this.on && v.videoHeight ? v.videoHeight : innerHeight;
    const c = document.createElement("canvas"); c.width = W; c.height = Hh;
    const g = c.getContext("2d");
    if (this.on && v.videoWidth) {
      if (this.facing === "user") { g.translate(W, 0); g.scale(-1, 1); }
      g.drawImage(v, 0, 0, W, Hh);
      g.setTransform(1, 0, 0, 1, 0, 0);
    } else {
      g.fillStyle = "#07040f"; g.fillRect(0, 0, W, Hh);
    }
    if (this.hasInk()) g.drawImage(this.ink, 0, 0, W, Hh);
    return await new Promise(r => c.toBlob(r, "image/jpeg", 0.86));
  }
}
