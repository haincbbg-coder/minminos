// MinMin HUD - canh 3D: mot dam may hat co the bien hinh giua "Chan dung" (dau-vai) va "Qua cau".
// Tat ca hinh khoi sinh bang toan hoc ngay trong trinh duyet, khong dung anh hay mo hinh cua ai.
import * as THREE from "three";

const N = 26000;                       // so hat; may yeu tu giam xuong (xem quality)

// ---------- Sinh diem ----------
function rand(a, b) { return a + Math.random() * (b - a); }

// Chan dung: cac lat cat ngang (nhu duong dong muc) qua dau, co, vai.
// Tra ve Float32Array vi tri + Float32Array "vung" (0 = than, 1 = mat/loi nong).
// Ban kinh ngang (rx), sau (rz), lech sau (cz) va do "mat" cua lat cat o do cao y.
function sliceAt(y) {
  let rx, rz, cz = 0, face = 0;
  if (y > 0.42) {
    // dau: elipsoid, dinh 1.62, cam 0.42; ham thu hep o phan duoi
    const hy = (y - 1.02) / 0.6;
    const k = Math.sqrt(Math.max(0, 1 - hy * hy));
    rx = 0.46 * k * (y < 0.78 ? 0.82 + (y - 0.42) * 0.5 : 1);
    rz = 0.56 * k;
    face = Math.max(0, 1 - Math.abs(y - 0.98) / 0.42);
  } else if (y > 0.08) {
    const t = (0.42 - y) / 0.34;            // co
    rx = 0.19 + t * 0.05; rz = 0.2; cz = -0.05;
  } else {
    // vai: loe nhanh ngay duoi co roi doc thoai xuong canh tay
    const t = Math.min(1, (0.08 - y) / 0.42);
    const e = 1 - Math.pow(1 - t, 3);
    rx = 0.26 + e * 1.12 + Math.max(0, -0.34 - y) * 0.06;
    rz = 0.24 + e * 0.24; cz = -0.06;
  }
  return { rx, rz, cz, face };
}

function portraitPoints(n) {
  const pos = new Float32Array(n * 3), zone = new Float32Array(n);
  const slices = 78;                   // so duong dong muc: it lat, moi lat day hat -> thay ro duong
  const top = 1.62, bottom = -1.5;
  for (let i = 0; i < n; i++) {
    // chon lat cat theo chu vi (lat rong nhu vai can nhieu hat hon lat hep nhu co)
    let y, sl;
    for (let tries = 0; tries < 12; tries++) {
      const s = Math.floor(Math.random() * slices);
      y = top - (s / (slices - 1)) * (top - bottom);
      sl = sliceAt(y);
      if (Math.random() < Math.pow((sl.rx + sl.rz) / 1.9, 0.75)) break;
    }
    y += rand(-0.003, 0.003);
    const a = Math.random() * Math.PI * 2;
    let x = Math.cos(a) * sl.rx, z = Math.sin(a) * sl.rz;
    if (y > 0.45 && z > 0) z *= 0.84;                 // mat phang hon gay
    pos[i * 3] = x;
    pos[i * 3 + 1] = y;
    pos[i * 3 + 2] = z + sl.cz;
    zone[i] = sl.face * Math.max(0, z / (sl.rz || 1));
  }
  return { pos, zone };
}

function spherePoints(n) {
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    // mot phan tren vo, mot phan lop loi ben trong
    const shell = Math.random() < 0.72;
    const r = shell ? 1.05 + rand(-0.02, 0.02) : Math.pow(Math.random(), 0.6) * 0.55;
    const u = Math.random() * 2 - 1, th = Math.random() * Math.PI * 2;
    const k = Math.sqrt(1 - u * u);
    pos[i * 3] = r * k * Math.cos(th);
    pos[i * 3 + 1] = r * u + 0.1;
    pos[i * 3 + 2] = r * k * Math.sin(th);
  }
  return pos;
}

function scatterPoints(n) {
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const r = rand(3, 9), a = Math.random() * Math.PI * 2, b = rand(-1, 1);
    pos[i * 3] = Math.cos(a) * r; pos[i * 3 + 1] = b * 5; pos[i * 3 + 2] = Math.sin(a) * r - 2;
  }
  return pos;
}

// ---------- Shader hat ----------
const VERT = /* glsl */`
uniform float uTime, uEnergy, uMorph, uAssemble, uState, uPixel, uSize;
attribute vec3 aPortrait, aSphere, aScatter;
attribute float aZone, aSeed;
varying float vZone, vGlow, vAlpha;

// nhieu gia re
float hash(float n){ return fract(sin(n)*43758.5453); }
vec3 wobble(vec3 p, float t, float s){
  return vec3(sin(p.y*6.0+t*1.3+s*6.2831), sin(p.x*5.0+t*1.1+s*3.1), cos(p.y*4.0+t*0.9+s*4.7))*0.5;
}

void main(){
  vec3 target = mix(aPortrait, aSphere, uMorph);
  float ease = smoothstep(0.0, 1.0, clamp(uAssemble*1.35 - aSeed*0.35, 0.0, 1.0));
  vec3 p = mix(aScatter, target, ease);

  // tho nhe luc nghi
  p += wobble(target, uTime, aSeed) * (0.006 + uEnergy*0.05);

  // STATE: 0 standby, 1 listening, 2 thinking, 3 speaking, 4 error
  float listening = step(0.5, uState)*step(uState, 1.5);
  float thinking  = step(1.5, uState)*step(uState, 2.5);
  float speaking  = step(2.5, uState)*step(uState, 3.5);

  // nghe: gon song lan ra tu tam
  float r = length(p.xz);
  p.xz *= 1.0 + listening * 0.03 * sin(r*14.0 - uTime*6.0);
  // nghi: vach quet chay len
  float scan = fract(uTime*0.35);
  float band = 1.0 - smoothstep(0.0, 0.09, abs((p.y+1.6)/3.2 - scan));
  // noi: hat vung mat bung ra theo nang luong giong
  p += normalize(p + vec3(0.0001)) * aZone * speaking * uEnergy * 0.12;

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float size = uSize * (0.75 + hash(aSeed*91.0)*0.6 + aZone*0.9*(0.4+uEnergy));
  gl_PointSize = size * uPixel * (3.0 / -mv.z);

  vZone = aZone;
  vGlow = band * thinking + aZone * (0.35 + uEnergy*0.9) + speaking*uEnergy*0.25;
  float lowFade = mix(smoothstep(-1.5, -0.35, aPortrait.y), 1.0, uMorph);
  vAlpha = mix(0.35, 1.0, ease) * lowFade;
}`;

const FRAG = /* glsl */`
uniform vec3 uCool, uWarm, uHot;
uniform float uErr;
varying float vZone, vGlow, vAlpha;
void main(){
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  float soft = smoothstep(0.5, 0.0, d);
  vec3 col = mix(uCool, uWarm, clamp(vZone*1.4, 0.0, 1.0));
  col = mix(col, uHot, clamp(vGlow - 0.35, 0.0, 1.0));
  col = mix(col, vec3(1.0, 0.25, 0.3), uErr);
  gl_FragColor = vec4(col * (0.75 + vGlow*0.9), soft * vAlpha * (0.55 + vGlow*0.45));
}`;

// ---------- Nen plasma tim ----------
const BG_FRAG = /* glsl */`
uniform float uTime, uEnergy;
uniform vec2 uRes;
varying vec2 vUv;
float wave(vec2 p, float f, float s, float ph){ return sin(p.x*f + uTime*s + ph + sin(p.y*1.7+uTime*0.3)*1.5); }
void main(){
  vec2 p = (vUv - 0.5) * vec2(uRes.x/uRes.y, 1.0) * 3.0;
  float w = 0.0;
  for (int i = 0; i < 4; i++){
    float fi = float(i);
    float y = wave(p, 1.2 + fi*0.35, 0.25 + fi*0.07, fi*1.9) * (0.35 + fi*0.12);
    w += 0.008 / abs(p.y - y + fi*0.08) ;
  }
  vec3 base = mix(vec3(0.020,0.012,0.045), vec3(0.055,0.020,0.090), vUv.y);
  vec3 line = mix(vec3(0.42,0.20,0.85), vec3(1.0,0.55,0.18), 0.25 + 0.25*sin(uTime*0.2));
  float vig = smoothstep(1.25, 0.2, length(vUv-0.5)*1.6);
  gl_FragColor = vec4(base + line * min(w, 0.9) * (0.14 + uEnergy*0.22) * vig, 1.0);
}`;

const STATES = { standby: 0, listening: 1, thinking: 2, speaking: 3, error: 4 };

export class MinMinScene {
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.reduced = !!opts.reducedMotion;
    const lowPower = opts.quality === "low";
    this.count = lowPower ? Math.floor(N * 0.45) : N;

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: "high-performance" });
    this.pixel = Math.min(window.devicePixelRatio || 1, lowPower ? 1 : 1.75);
    this.renderer.setPixelRatio(this.pixel);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    this.camera.position.set(0, 0.95, 6.0);
    this.camera.lookAt(0, 0.05, 0);

    // nen
    this.bgMat = new THREE.ShaderMaterial({
      vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.9999, 1.0); }",
      fragmentShader: BG_FRAG, depthWrite: false, depthTest: false,
      uniforms: { uTime: { value: 0 }, uEnergy: { value: 0 }, uRes: { value: new THREE.Vector2(1, 1) } },
    });
    const bg = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.bgMat);
    bg.frustumCulled = false; bg.renderOrder = -1;
    this.scene.add(bg);

    // hat
    const portrait = portraitPoints(this.count);
    const geo = new THREE.BufferGeometry();
    const seed = new Float32Array(this.count);
    for (let i = 0; i < this.count; i++) seed[i] = Math.random();
    geo.setAttribute("position", new THREE.BufferAttribute(portrait.pos, 3)); // de tinh bounding
    geo.setAttribute("aPortrait", new THREE.BufferAttribute(portrait.pos, 3));
    geo.setAttribute("aSphere", new THREE.BufferAttribute(spherePoints(this.count), 3));
    geo.setAttribute("aScatter", new THREE.BufferAttribute(scatterPoints(this.count), 3));
    geo.setAttribute("aZone", new THREE.BufferAttribute(portrait.zone, 1));
    geo.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
    this.mat = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 }, uEnergy: { value: 0 }, uMorph: { value: opts.form === "orb" ? 1 : 0 },
        uAssemble: { value: this.reduced ? 1 : 0 }, uState: { value: 0 }, uPixel: { value: this.pixel },
        uSize: { value: lowPower ? 3.2 : 2.4 }, uErr: { value: 0 },
        uCool: { value: new THREE.Color("#8f6bff") },
        uWarm: { value: new THREE.Color("#ff9a3c") },
        uHot: { value: new THREE.Color("#ffe2b0") },
      },
    });
    this.points = new THREE.Points(geo, this.mat);
    this.points.frustumCulled = false;
    this.scene.add(this.points);

    // loi sang: vung nong o mat (chan dung) hoac tam qua cau
    const cv = document.createElement("canvas"); cv.width = cv.height = 128;
    const cg = cv.getContext("2d");
    const grd = cg.createRadialGradient(64, 64, 0, 64, 64, 64);
    grd.addColorStop(0, "rgba(255,244,222,1)"); grd.addColorStop(0.18, "rgba(255,190,110,.85)");
    grd.addColorStop(0.45, "rgba(255,120,40,.28)"); grd.addColorStop(1, "rgba(255,90,20,0)");
    cg.fillStyle = grd; cg.fillRect(0, 0, 128, 128);
    this.core = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), transparent: true,
      depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending }));
    this.scene.add(this.core);

    // vong quy dao quanh qua cau / chan dung
    this.rings = new THREE.Group();
    const ringMat = (c, o) => new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: o, blending: THREE.AdditiveBlending });
    [[1.55, "#ff9a3c", 0.35], [1.8, "#8f6bff", 0.22], [2.15, "#8f6bff", 0.12]].forEach(([r, c, o], i) => {
      const pts = [];
      for (let k = 0; k <= 256; k++) { const a = k / 256 * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r)); }
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), ringMat(c, o));
      line.rotation.x = Math.PI / 2 - 0.35 + i * 0.22;
      line.rotation.z = i * 0.6;
      line.userData.spin = (i % 2 ? -1 : 1) * (0.05 + i * 0.03);
      this.rings.add(line);
    });
    this.rings.position.y = 0.1;
    this.scene.add(this.rings);

    this.state = "standby";
    this.energy = 0; this._energyTarget = 0;
    this.morphTarget = this.mat.uniforms.uMorph.value;
    this._t0 = performance.now();
    this._frames = 0; this._fpsT = performance.now(); this.fps = 60;
    this.onFps = opts.onFps || null;
    this.resize();
    window.addEventListener("resize", () => this.resize());
    this._loop = this._loop.bind(this);
    requestAnimationFrame(this._loop);
  }

  resize() {
    const w = this.canvas.clientWidth || window.innerWidth, h = this.canvas.clientHeight || window.innerHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    // man doc: lui camera cho du khung
    this.camera.position.z = w / h < 1 ? 8.2 : 6.0;
    this.camera.lookAt(0, 0.05, 0);
    this.camera.updateProjectionMatrix();
    this.bgMat.uniforms.uRes.value.set(w, h);
  }

  setState(s) {
    if (!(s in STATES)) return;
    this.state = s;
    this.mat.uniforms.uState.value = STATES[s];
  }
  setEnergy(v) { this._energyTarget = Math.max(0, Math.min(1, v)); }
  setForm(form) { this.morphTarget = form === "orb" ? 1 : 0; }
  toggleForm() { this.setForm(this.morphTarget > 0.5 ? "portrait" : "orb"); return this.morphTarget > 0.5 ? "orb" : "portrait"; }

  _loop(now) {
    const t = (now - this._t0) / 1000;
    const u = this.mat.uniforms;
    const speed = this.reduced ? 0.25 : 1;
    u.uTime.value = t * speed;
    this.bgMat.uniforms.uTime.value = t * speed;
    // nang luong: len nhanh, xuong cham
    const k = this._energyTarget > this.energy ? 0.35 : 0.08;
    this.energy += (this._energyTarget - this.energy) * k;
    const base = this.state === "thinking" ? 0.25 : this.state === "listening" ? 0.15 : 0;
    u.uEnergy.value = Math.max(this.energy, base);
    this.bgMat.uniforms.uEnergy.value = u.uEnergy.value;
    u.uMorph.value += (this.morphTarget - u.uMorph.value) * 0.04;
    if (u.uAssemble.value < 1) u.uAssemble.value = Math.min(1, t / 2.6);
    u.uErr.value += ((this.state === "error" ? 0.6 : 0) - u.uErr.value) * 0.08;

    this.points.rotation.y = Math.sin(t * 0.15 * speed) * 0.35 + u.uMorph.value * t * 0.12 * speed;
    const ringSpeed = this.state === "thinking" ? 3 : 1;
    this.rings.children.forEach(r => { r.rotation.z += r.userData.spin * 0.01 * ringSpeed * speed; });
    this.rings.visible = u.uMorph.value > 0.05 || this.state !== "standby";
    this.rings.children.forEach(r => { r.material.opacity = (r.userData.o ??= r.material.opacity) * (0.3 + u.uMorph.value * 0.7); });

    // loi sang di theo hinh: mat -> tam qua cau; phong theo nang luong giong
    const m = u.uMorph.value, e = u.uEnergy.value;
    const pulse = this.state === "thinking" ? 0.12 * Math.sin(t * 5) : 0;
    this.core.position.set(0, 0.98 * (1 - m) + 0.1 * m, 0.42 * (1 - m));
    const sc = (0.55 + m * 0.7) * (1 + e * 1.3 + pulse);
    this.core.scale.set(sc, sc, 1);
    this.core.material.opacity = Math.min(1, 0.5 + e * 0.6 + pulse);
    this.core.material.color.set(this.state === "error" ? "#ff5d73" : this.state === "listening" ? "#bff5e8" : "#ffffff");

    this.renderer.render(this.scene, this.camera);

    this._frames++;
    if (now - this._fpsT > 2000) {
      this.fps = this._frames * 1000 / (now - this._fpsT);
      this._frames = 0; this._fpsT = now;
      if (this.onFps) this.onFps(this.fps);
    }
    requestAnimationFrame(this._loop);
  }
}
