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
// Nhan dien chay HOAN TOAN trong trinh duyet (MediaPipe, ma nguon mo cua Google). Hinh anh
// KHONG roi may, tru khi bo bam "Nhin" / ra lenh "Min Min nhin xem" - luc do MOT anh chup
// duoc gui len MinMin cua chinh bo.

const MP_VER = "1.0.1";
const MP_CDN = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${MP_VER}`;
const M_GESTURE = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";
const M_FACE = "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";

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
    try { face = this._f.detectForVideo(v, now).detections?.[0]?.boundingBox || null; } catch (e) {}
    if (hand && laChum(hand)) gest = "Pinch";
    this._apply(hand, gest, face);
    this._drawPreview(hand, face);
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
