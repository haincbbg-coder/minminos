// MinMin HUD - nguoi hat (26.10.81): tuong nam luc luong dung tu hang chuc nghin cham lay mau tu anh
// (figure.bin, tao bang tools/tao_hinh_hat.py). Moi cham co mau that cua anh, do sau tu khoang cach
// toi vien nen xoay nhe van co khoi. Khi noi: moi/ham chuyen dong theo nhip giong, mat sang len.
const S = 3.45 / 1880;              // 1 pixel anh = bao nhieu don vi the gioi
const TOP = 1.95;
const px2w = (x, y) => [(x - 551.5) * S, TOP - y * S];
// Toa do (pixel trong anh da cat) cua miệng va hai mat
const MOUTH = { x: 555, y: 487, rx: 78, ry: 58 };
const EYES = [{ x: 466, y: 309 }, { x: 642, y: 309 }];
const VERT = /* glsl */`
attribute float aZ, aSz, aSeed;
attribute vec3 aCol;
uniform float uTime, uOpen, uSizeK, uPix, uAssemble, uYaw, uPitch, uState, uGlow, uLight;
uniform vec4 uMouth, uEye;
varying vec3 vCol;
varying float vA, vEdge, vGlow, vMouth;
float hash(float n){ return fract(sin(n)*43758.5453); }
void main(){
  vec3 p = position;
  // ---- mieng: hai moi khep lai khi im, mo ra theo giong; ham duoi ha xuong ----
  vec2 d = (p.xy - uMouth.xy) / uMouth.zw;
  float m = 1.0 - smoothstep(0.55, 1.15, length(d));
  float closeK = mix(0.16, 1.0, uOpen);
  float oy = p.y;
  p.y = uMouth.y + (p.y - uMouth.y) * mix(1.0, closeK, m);
  float jaw = smoothstep(uMouth.y - 0.02, uMouth.y - 0.18, oy) * (1.0 - smoothstep(uMouth.y - 0.36, uMouth.y - 0.55, oy))
            * (1.0 - smoothstep(0.30, 0.62, abs(p.x)));
  p.y -= uOpen * 0.05 * jaw;
  vMouth = m;
  // ---- mat sang ----
  float e1 = exp(-dot(p.xy - uEye.xy, p.xy - uEye.xy) * 3200.0);
  float e2 = exp(-dot(p.xy - uEye.zw, p.xy - uEye.zw) * 3200.0);
  vGlow = max(e1, e2) * (0.75 + 0.25 * sin(uTime * 2.2) + uGlow);
  // ---- xoay nhe theo nguoi nhin: dau xoay nhieu, than it ----
  float head = smoothstep(uMouth.y - 0.45, uMouth.y + 0.1, p.y);
  float ya = uYaw * (0.35 + 0.65 * head), c = cos(ya), s = sin(ya);
  p.xz = vec2(c * p.x - s * p.z, s * p.x + c * p.z);
  p.y += uPitch * 0.06 * head * p.z;
  // ---- tho + long lanh ----
  p.y += sin(uTime * 1.25) * 0.007;
  p.xy += vec2(sin(uTime * (0.7 + hash(aSeed) * 0.8) + aSeed * 40.0), cos(uTime * (0.6 + hash(aSeed * 3.0) * 0.8) + aSeed * 31.0)) * 0.0022;
  // ---- hien len tu bung len dau, mep sang quet len ----
  float cao = clamp((p.y + 1.5) / 3.5, 0.0, 1.0);
  float raw = clamp(uAssemble * 1.7 - (cao * 0.55 + aSeed * 0.14), 0.0, 1.0);
  float ease = smoothstep(0.0, 1.0, raw);
  vEdge = smoothstep(0.0, 0.1, raw) * (1.0 - smoothstep(0.5, 1.0, raw));
  vec3 off = vec3(hash(aSeed * 7.0) - 0.5, hash(aSeed * 13.0) - 0.2, hash(aSeed * 19.0) - 0.5) * 1.6;
  p = mix(p + off, p, ease);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float sz = aSz * (1.0 + vGlow * 0.5 + vEdge * 0.8 + m * uOpen * 0.4);
  gl_PointSize = sz * uPix * (4.2 / -mv.z) * uSizeK * mix(1.15, 1.0, uLight);
  vCol = aCol;
  vA = mix(0.2, 1.0, ease);
}`;
const FRAG = /* glsl */`
uniform float uLight, uOpen, uErr, uState;
varying vec3 vCol;
varying float vA, vEdge, vGlow, vMouth;
void main(){
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  float soft = smoothstep(0.5, 0.15, d);
  vec3 col = vCol;
  if (uLight < 0.5) col = pow(col, vec3(0.85)) * 1.05 + vec3(0.0, 0.02, 0.05);   // tren nen toi: cham sang len
  col += vec3(0.30, 0.62, 1.0) * (vGlow * 0.9 + vMouth * uOpen * 0.55);
  col += vec3(1.0, 0.7, 0.4) * vEdge * 0.5;
  col = mix(col, vec3(1.0, 0.25, 0.3), uErr * 0.5);
  gl_FragColor = vec4(col, soft * vA * (uLight > 0.5 ? 0.96 : 0.5));
}`;

export class PhotoFigure {
  constructor(THREE, scene, url) {
    this.THREE = THREE; this.ready = false; this.open = 0; this.glow = 0;
    this.mat = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 }, uSizeK: { value: 1 }, uOpen: { value: 0 }, uPix: { value: 1 }, uAssemble: { value: 0 }, uYaw: { value: 0 },
        uPitch: { value: 0 }, uState: { value: 0 }, uGlow: { value: 0 }, uLight: { value: 0 }, uErr: { value: 0 },
        uMouth: { value: new THREE.Vector4(...px2w(MOUTH.x, MOUTH.y), MOUTH.rx * S, MOUTH.ry * S) },
        uEye: { value: new THREE.Vector4(...px2w(EYES[0].x, EYES[0].y), ...px2w(EYES[1].x, EYES[1].y)) },
      },
    });
    this.points = null; this.scene = scene;
    fetch(url).then(r => r.ok ? r.arrayBuffer() : Promise.reject(r.status)).then(buf => this._build(buf)).catch(() => {});
  }
  _build(buf) {
    const THREE = this.THREE, dv = new DataView(buf);
    if (String.fromCharCode(dv.getUint8(0), dv.getUint8(1), dv.getUint8(2), dv.getUint8(3)) !== "MMF1") return;
    const n = dv.getUint32(4, true);
    let o = 12;
    const X = new Uint16Array(buf.slice(o, o + n * 2)); o += n * 2;
    const Y = new Uint16Array(buf.slice(o, o + n * 2)); o += n * 2;
    const Z = new Uint8Array(buf, o, n); o += n;
    const C = new Uint8Array(buf, o, n * 3); o += n * 3;
    const Sz = new Uint8Array(buf, o, n);
    const pos = new Float32Array(n * 3), col = new Float32Array(n * 3), sz = new Float32Array(n), seed = new Float32Array(n), zz = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const [wx, wy] = px2w(X[i] / 16, Y[i] / 16);
      pos[i * 3] = wx; pos[i * 3 + 1] = wy; pos[i * 3 + 2] = (Z[i] / 255 - 0.4) * 0.7;
      col[i * 3] = C[i * 3] / 255; col[i * 3 + 1] = C[i * 3 + 1] / 255; col[i * 3 + 2] = C[i * 3 + 2] / 255;
      sz[i] = Sz[i] / 120; seed[i] = Math.random(); zz[i] = Z[i] / 255;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("aCol", new THREE.BufferAttribute(col, 3));
    g.setAttribute("aSz", new THREE.BufferAttribute(sz, 1));
    g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    g.setAttribute("aZ", new THREE.BufferAttribute(zz, 1));
    this.points = new THREE.Points(g, this.mat);
    this.points.frustumCulled = false;
    this.points.visible = false;
    this.n = n; this.setQuality(this.level || "high");
    this.scene.add(this.points);
    this.ready = true; this.t0 = performance.now();
  }
  setLight(light) {
    this.mat.uniforms.uLight.value = light ? 1 : 0;
    this.mat.blending = light ? this.THREE.NormalBlending : this.THREE.AdditiveBlending;
    this.mat.needsUpdate = true;
  }
  // 3 muc: Sac net (het 400k cham), Can bang (40%), Nhe (15%). Cham la ngau nhien deu nen cat bo
  // phan duoi van giu nguyen hinh; cham to len mot chut de khong thung lo.
  setQuality(level) {
    this.level = level;
    const K = { high: [1, 1], mid: [0.4, 1.5], low: [0.15, 2.4] }[level] || [1, 1];
    this.mat.uniforms.uSizeK.value = K[1];
    if (this.points) this.points.geometry.setDrawRange(0, Math.floor(this.n * K[0]));
  }
  show(v) { if (this.points) this.points.visible = !!v; }
  // Do mo mieng: theo muc am thanh that; dang noi ma chua co muc thi giu nhip am tiet gia lap
  update(t, { energy, state, yaw, pitch, pixel, reduced }) {
    if (!this.ready) return;
    const u = this.mat.uniforms;
    const noi = state === "speaking";
    let target = Math.min(1, energy * 1.5);
    if (noi) target = Math.max(target, 0.22 + 0.3 * Math.abs(Math.sin(t * 9.3) * Math.sin(t * 3.1 + 0.7)));
    this.open += (target - this.open) * (target > this.open ? 0.45 : 0.22);
    this.glow += (((state === "listening" ? 0.5 : 0) + (noi ? 0.35 : 0) + energy * 0.6) - this.glow) * 0.1;
    u.uTime.value = t; u.uOpen.value = this.open; u.uGlow.value = this.glow; u.uPix.value = pixel;
    u.uYaw.value = yaw; u.uPitch.value = pitch;
    u.uErr.value += ((state === "error" ? 1 : 0) - u.uErr.value) * 0.08;
    const k = reduced ? 1 : Math.min(1, (performance.now() - this.t0) / 4200);
    u.uAssemble.value = k;
  }
}
