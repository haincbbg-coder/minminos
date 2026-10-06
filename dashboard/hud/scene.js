// MinMin HUD - canh 3D: dam may hat bien hinh giua "Chan dung" (hinh nguoi day du, xem
// body.js) va "Qua cau". Dau nhin theo chuot (hoac theo mat bo qua camera), keo de xoay,
// con lan de phong to thu nho. Moi hinh khoi sinh bang toan hoc tai cho.
import * as THREE from "three";
import { humanPoints, SHOULDER, ELBOW } from "./body.js";
import { robotPoints } from "./robot.js";
import { bustPoints } from "./bust.js?v=8";

const N = 60000;                       // so hat; may yeu tu giam (quality=low)
const rand = (a, b) => a + Math.random() * (b - a);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

function spherePoints(n) {
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const shell = Math.random() < 0.72;
    const r = shell ? 1.3 + rand(-0.02, 0.02) : Math.pow(Math.random(), 0.6) * 0.7;
    const u = Math.random() * 2 - 1, th = Math.random() * Math.PI * 2;
    const k = Math.sqrt(1 - u * u);
    pos[i * 3] = r * k * Math.cos(th);
    pos[i * 3 + 1] = r * u + 0.2;
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
uniform float uTime, uEnergy, uAssemble, uState, uPixel, uSize, uHeadYaw, uHeadPitch;
uniform vec4 uForm;                 // trong so: robot, nguoi, qua cau, tuong ban than
uniform vec4 uArms;                 // canh tay trai (tren, cang), phai (tren, cang) - radian
attribute vec3 aRobot, aHuman, aBust, aSphere, aScatter, aInfoR, aInfoH, aInfoB, aNrmB;
attribute vec2 aArmR, aArmH;
attribute float aSeed;
varying float vZone, vGlow, vAlpha, vRim, vLit;

float hash(float n){ return fract(sin(n)*43758.5453); }
vec3 wobble(vec3 p, float t, float s){
  return vec3(sin(p.y*6.0+t*1.3+s*6.2831), sin(p.x*5.0+t*1.1+s*3.1), cos(p.y*4.0+t*0.9+s*4.7))*0.5;
}
vec3 quayDau(vec3 p, float w){
  vec3 q = p - vec3(0.0, 0.78, 0.0);
  float y = uHeadYaw * w, x = uHeadPitch * w;
  float cy = cos(y), sy = sin(y);
  q = vec3(cy*q.x + sy*q.z, q.y, -sy*q.x + cy*q.z);
  float cx = cos(x), sx = sin(x);
  q = vec3(q.x, cx*q.y - sx*q.z, sx*q.y + cx*q.z);
  return q + vec3(0.0, 0.78, 0.0);
}
vec3 quayHuong(vec3 d, float w){
  float y = uHeadYaw * w, x = uHeadPitch * w;
  float cy = cos(y), sy = sin(y);
  d = vec3(cy*d.x + sy*d.z, d.y, -sy*d.x + cy*d.z);
  float cx = cos(x), sx = sin(x);
  return vec3(d.x, cx*d.y - sx*d.z, sx*d.y + cx*d.z);
}
vec3 quayZ(vec3 p, vec2 c, float a){
  vec2 d = p.xy - c; float ca = cos(a), sa = sin(a);
  return vec3(c + vec2(ca*d.x - sa*d.y, sa*d.x + ca*d.y), p.z);
}
// canh tay bat chuoc: cang tay quay quanh khuyu, ca canh tay quay quanh vai
vec3 tay(vec3 p, vec2 arm){
  if (arm.x == 0.0) return p;
  float up = arm.x < 0.0 ? uArms.x : uArms.z;
  float fo = arm.x < 0.0 ? uArms.y : uArms.w;
  vec2 S = vec2(arm.x * ${SHOULDER[0].toFixed(3)}, ${SHOULDER[1].toFixed(3)});
  vec2 E = vec2(arm.x * ${ELBOW[0].toFixed(3)}, ${ELBOW[1].toFixed(3)});
  if (arm.y > 1.5) p = quayZ(p, E, fo);
  return quayZ(p, S, up);
}

void main(){
  vec3 ro = quayDau(tay(aRobot, aArmR), aInfoR.z);
  vec3 h = quayDau(tay(aHuman, aArmH), aInfoH.z);
  vec3 bu = quayDau(aBust, aInfoB.z);
  vec3 target = ro * uForm.x + h * uForm.y + aSphere * uForm.z + bu * uForm.w;
  vec3 info = aInfoR * uForm.x + aInfoH * uForm.y + vec3(0.0, 1.0, 0.0) * uForm.z + aInfoB * uForm.w;
  float aZone = info.x;
  float uMorph = uForm.z;
  // 26.10.79: tuong ban than hien len tu BUNG len DAU (kieu Apex): hat thap vao truoc, hat cao vao sau
  float cao = clamp((target.y + 1.6) / 3.5, 0.0, 1.0);
  float tre = mix(aSeed*0.35, cao*0.55 + aSeed*0.12, uForm.w);
  float raw = clamp(uAssemble*1.75 - tre, 0.0, 1.0);
  float ease = smoothstep(0.0, 1.0, raw);
  float mepSang = smoothstep(0.0, 0.12, raw) * (1.0 - smoothstep(0.55, 1.0, raw)) * uForm.w;
  vec3 p = mix(aScatter, target, ease);

  // ---- SONG DONG LIEN TUC (0.64.87): hat khong con dung im ----
  float h1 = hash(aSeed*13.0), h2 = hash(aSeed*7.3), h3 = hash(aSeed*29.1);
  // 1) troi nhe quanh vi tri (tho), manh hon khi co giong
  p += wobble(target, uTime*0.8, aSeed) * (0.009 + uEnergy*0.04);
  // 2) chay doc duong dong muc: hat truot qua lai theo vong ngang cua hinh
  float truot = 0.05 * sin(uTime*(0.35 + h1*0.5) + aSeed*40.0) * (1.0 - uForm.z);
  float ct = cos(truot), st = sin(truot);
  p.xz = vec2(ct*p.x - st*p.z, st*p.x + ct*p.z);
  // 3) song nang luong di tu duoi len tren, hat trong song phong ra ngoai mot chut
  float quet = fract(uTime*0.16);
  float song = 1.0 - smoothstep(0.0, 0.045, abs((p.y+1.6)/3.6 - quet));
  p += normalize(vec3(p.x, 0.0001, p.z)) * song * 0.018;
  // 4) tan lua: 3% so hat bay len roi tat, lap lai
  float tanLua = step(0.97 - 0.045*uForm.w, h2);      // tuong ban than: nhieu bui bay hon (kieu Apex)
  float bay = fract(uTime*(0.05 + h3*0.06) + aSeed*3.0);
  p += vec3(sin(uTime*0.7 + aSeed*9.0)*0.05, bay*(0.55 + 0.6*uForm.w), cos(uTime*0.5 + aSeed*5.0)*0.05) * tanLua * ease;
  // 5) nhap nhay: moi hat co nhip rieng
  float nhay = 0.5 + 0.5*sin(uTime*(1.2 + h1*3.3) + aSeed*62.83);
  // 6) xung than kinh: vai hat loe sang chop nhoang
  float xung = pow(max(0.0, sin(uTime*(0.8 + h3*1.6) + aSeed*97.0)), 40.0) * step(0.9, h1);

  // STATE: 0 cho, 1 nghe, 2 nghi, 3 noi, 4 loi
  float listening = step(0.5, uState)*step(uState, 1.5);
  float thinking  = step(1.5, uState)*step(uState, 2.5);
  float speaking  = step(2.5, uState)*step(uState, 3.5);

  float r = length(p.xz);
  p.xz *= 1.0 + listening * 0.025 * sin(r*14.0 - uTime*6.0);
  float scan = fract(uTime*0.35);
  float band = 1.0 - smoothstep(0.0, 0.07, abs((p.y+1.6)/3.6 - scan));
  // noi: vung mat, mieng phap phong theo giong
  p += normalize(p - vec3(0.0, 1.3, 0.0) + vec3(0.0001)) * aZone * speaking * uEnergy * 0.05 * (1.0 - uMorph);

  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  // sang vien (rim): hat nam o ria hinh nhin tu camera thi sang, quay thang ve camera thi mo
  vec3 nv = normalize(normalMatrix * quayHuong(aNrmB, aInfoB.z));
  float rim = 1.0 - abs(dot(nv, normalize(-mv.xyz)));
  vRim = pow(rim, 1.8) * uForm.w;
  // vien sang lung linh: gon song chay vong quanh dau va vai
  vRim *= 0.72 + 0.28*sin(atan(p.z, p.x)*3.0 - uTime*1.3 + p.y*5.0);
  // anh sang chinh (tu tren-trai-truoc): khoi co bap nao quay ve anh sang thi sang, quay di thi toi
  float lit = max(0.0, dot(nv, normalize(vec3(-0.45, 0.75, 0.8)))) * uForm.w;
  vLit = lit;
  float size = uSize * (0.7 + hash(aSeed*91.0)*0.6 + aZone*1.1*(0.5+uEnergy)) * (1.0 - 0.1*uForm.w + vRim*1.6);
  size *= 0.82 + 0.36*nhay + xung*1.6 + song*0.5;
  gl_PointSize = size * uPixel * (3.2 / -mv.z);

  vZone = aZone;
  vGlow = mepSang * 1.6 + band * thinking + aZone * (0.4 + uEnergy*0.9) + speaking*uEnergy*0.2 + song*0.45 + xung*1.4;
  vAlpha = mix(0.35, 1.0, ease) * info.y * mix(1.0, 0.5 + 0.5*max(max(vRim*1.4, aZone), lit*1.25), uForm.w);
  vAlpha *= 0.62 + 0.38*nhay;
  vAlpha *= mix(1.0, (1.0 - bay) * smoothstep(0.0, 0.15, bay) * 1.6, tanLua);
}`;

const FRAG = /* glsl */`
uniform vec3 uCool, uWarm, uHot, uRim;
uniform float uErr, uBoost;
varying float vZone, vGlow, vAlpha, vRim, vLit;
void main(){
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;
  float soft = smoothstep(0.5, 0.0, d);
  // 26.10.80: ruot toi xanh sam, vien trang-xanh chop, mat sang anh den ve cam: duong net noi han len
  vec3 col = mix(uCool * 0.62, uWarm, clamp(vZone*1.4, 0.0, 1.0));
  col = mix(col, uWarm, clamp(vLit * 0.55, 0.0, 0.5));
  col = mix(col, uHot, clamp(vGlow - 0.35, 0.0, 1.0));
  col = mix(col, uRim, clamp(vRim * 2.4, 0.0, 1.0));
  col = mix(col, vec3(1.0, 0.25, 0.3), uErr);
  gl_FragColor = vec4(col * (0.58 + vGlow*0.9 + vRim*2.3 + vLit*0.75) * uBoost, soft * vAlpha * (0.55 + vGlow*0.45));
}`;

// ---------- Nen (26.10.69, kieu Apex) ----------
// Nen toi: xanh than sau, quang xanh sau lung tuong, hai day nui NANG LUONG o hai ben (duong
// dinh nui sang xanh, tia chop cam chay doc dinh nhu dien). Nen sang giu net cu nhung ve bang
// muc xanh. Tat ca la toan hoc trong shader, khong dung anh nao.
const BG_FRAG = /* glsl */`
uniform float uTime, uEnergy, uLight;
uniform vec3 uBase;
uniform vec2 uRes;
varying vec2 vUv;
float h11(float n){ return fract(sin(n*127.1)*43758.5453); }
float vn(float x){ float i = floor(x), f = fract(x); f = f*f*(3.0-2.0*f); return mix(h11(i), h11(i+1.0), f); }
float fbm(float x){ return vn(x)*0.5 + vn(x*2.1+7.0)*0.25 + vn(x*4.3+13.0)*0.125 + vn(x*8.9+3.0)*0.0625; }
void main(){
  vec2 p = (vUv - 0.5) * vec2(uRes.x/uRes.y, 1.0) * 3.0;
  float ax = abs(p.x);
  // ---- nen toi ----
  vec3 col = mix(vec3(0.004,0.010,0.035), vec3(0.010,0.045,0.130), smoothstep(-1.5, 1.1, p.y));
  float quang = exp(-dot(p - vec2(0.0, 0.55), p - vec2(0.0, 0.55)) * 0.55);
  col += vec3(0.020, 0.150, 0.420) * quang * (0.55 + uEnergy*0.5);
  // ---- hai day nui nang luong ----
  float lightning = 0.0, fill = 0.0;
  for (int i = 0; i < 3; i++){
    float fi = float(i);
    float x = ax * (1.0 + fi*0.22) + fi*3.7;
    float dinh = -0.55 + fi*0.14 + (fbm(x*1.5 + fi*5.0) - 0.35) * (1.25 - fi*0.2);
    dinh += 0.12*smoothstep(0.35, 1.9, ax);              // nui cao dan ra mep
    float d = p.y - dinh;
    float duong = 0.0045 / (abs(d) + 0.0035);               // duong dinh sang
    float mask = smoothstep(0.30 + fi*0.05, 0.80, ax);      // chua trong khoang giua cho nguoi
    float chop = pow(vn(ax*9.0 - uTime*(1.6 + fi*0.5) + fi*11.0), 6.0);   // tia chop chay doc dinh
    lightning += (duong * (0.35 + chop*2.2)) * mask * (1.0 - fi*0.22);
    fill += smoothstep(0.0, -0.9, d) * 0.07 * mask * (1.0 - fi*0.25);
  }
  vec3 xanh = vec3(0.10, 0.52, 1.0), cam = vec3(1.0, 0.55, 0.12);
  float noiCam = pow(vn(ax*5.0 - uTime*0.9), 5.0);
  vec3 dien = mix(xanh, cam, clamp(noiCam*1.3, 0.0, 1.0));
  col += dien * min(lightning, 3.0) * (0.55 + uEnergy*0.35);
  col += xanh * fill * 1.5;
  // ---- vien toi ----
  col *= smoothstep(1.9, 0.35, length(vUv-0.5)*1.9) * 0.85 + 0.15;
  // ---- tong sang: giu net cu, doi sang muc xanh ----
  float wv = 0.0;
  for (int i = 0; i < 4; i++){
    float fi = float(i);
    float y = sin(p.x*(1.2+fi*0.35) + uTime*(0.25+fi*0.07) + fi*1.9 + sin(p.y*1.7+uTime*0.3)*1.5) * (0.35 + fi*0.12);
    wv += 0.008 / abs(p.y - y + fi*0.08);
  }
  vec3 sang = uBase - vec3(0.050,0.030,0.010)*min(wv,0.9);
  gl_FragColor = vec4(mix(col, sang, uLight), 1.0);
}`;

const STATES = { standby: 0, listening: 1, thinking: 2, speaking: 3, error: 4 };
// Ba hinh: robot giap (mac dinh), nguoi, qua cau - trong so tron trong shader
const FORMS = { bust: [0, 0, 0, 1], robot: [1, 0, 0, 0], portrait: [0, 1, 0, 0], orb: [0, 0, 1, 0] };
const THU_TU = ["bust", "robot", "portrait", "orb"];

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

    // nen
    this.bgMat = new THREE.ShaderMaterial({
      vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0.9999, 1.0); }",
      fragmentShader: BG_FRAG, depthWrite: false, depthTest: false,
      uniforms: { uLight: { value: 0 }, uBase: { value: new THREE.Color("#efe9e2") }, uTime: { value: 0 }, uEnergy: { value: 0 }, uRes: { value: new THREE.Vector2(1, 1) } },
    });
    const bg = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.bgMat);
    bg.frustumCulled = false; bg.renderOrder = -1;
    this.scene.add(bg);

    // hat
    const human = humanPoints(this.count), robot = robotPoints(this.count), bust = bustPoints(this.count);
    const geo = new THREE.BufferGeometry();
    const seed = new Float32Array(this.count);
    for (let i = 0; i < this.count; i++) seed[i] = Math.random();
    const A = (arr, k) => new THREE.BufferAttribute(arr, k);
    geo.setAttribute("position", A(robot.pos, 3));
    geo.setAttribute("aRobot", A(robot.pos, 3));
    geo.setAttribute("aHuman", A(human.pos, 3));
    geo.setAttribute("aBust", A(bust.pos, 3));
    geo.setAttribute("aInfoB", A(bust.info, 3));
    geo.setAttribute("aNrmB", A(bust.nrm, 3));
    geo.setAttribute("aSphere", A(spherePoints(this.count), 3));
    geo.setAttribute("aScatter", A(scatterPoints(this.count), 3));
    geo.setAttribute("aInfoR", A(robot.info, 3));
    geo.setAttribute("aInfoH", A(human.info, 3));
    geo.setAttribute("aArmR", A(robot.arm, 2));
    geo.setAttribute("aArmH", A(human.arm, 2));
    geo.setAttribute("aSeed", A(seed, 1));
    this.mat = new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 }, uEnergy: { value: 0 }, uForm: { value: new THREE.Vector4(...FORMS[this._formOf(opts.form)]) },
        uArms: { value: new THREE.Vector4() },
        uAssemble: { value: this.reduced ? 1 : 0 }, uState: { value: 0 }, uPixel: { value: this.pixel },
        uSize: { value: lowPower ? 3.0 : 2.2 }, uErr: { value: 0 }, uBoost: { value: 1 },
        uHeadYaw: { value: 0 }, uHeadPitch: { value: 0 },
        uCool: { value: new THREE.Color("#1c9bff") },
        uWarm: { value: new THREE.Color("#ff8a1e") },
        uHot: { value: new THREE.Color("#ffd9a0") },
        uRim: { value: new THREE.Color("#8fe6ff") },
      },
    });
    this.points = new THREE.Points(geo, this.mat);
    this.points.frustumCulled = false;
    this.body = new THREE.Group();          // xoay ca nguoi (keo chuot) + loi sang di cung
    this.body.add(this.points);
    this.scene.add(this.body);

    // loi sang: o nguc (chan dung) hoac tam qua cau
    const cv = document.createElement("canvas"); cv.width = cv.height = 128;
    const cg = cv.getContext("2d");
    const grd = cg.createRadialGradient(64, 64, 0, 64, 64, 64);
    grd.addColorStop(0, "rgba(255,244,222,1)"); grd.addColorStop(0.18, "rgba(255,190,110,.85)");
    grd.addColorStop(0.45, "rgba(255,120,40,.28)"); grd.addColorStop(1, "rgba(255,90,20,0)");
    cg.fillStyle = grd; cg.fillRect(0, 0, 128, 128);
    this.core = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), transparent: true,
      depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending }));
    this.body.add(this.core);

    // vong quy dao
    this.rings = new THREE.Group();
    const ringMat = (c, o) => new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: o, blending: THREE.AdditiveBlending });
    [[1.85, "#ff8a1e", 0.30], [2.15, "#1c9bff", 0.20], [2.55, "#1c9bff", 0.10]].forEach(([r, c, o], i) => {
      const pts = [];
      for (let k = 0; k <= 256; k++) { const a = k / 256 * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r)); }
      const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), ringMat(c, o));
      line.rotation.x = Math.PI / 2 - 0.35 + i * 0.22;
      line.rotation.z = i * 0.6;
      line.userData.spin = (i % 2 ? -1 : 1) * (0.05 + i * 0.03);
      line.userData.o = o;
      this.rings.add(line);
    });
    this.rings.position.y = 0.2;
    this.scene.add(this.rings);

    const applyTheme = () => {
      const light = document.documentElement.getAttribute("data-theme") === "light";
      const style = getComputedStyle(document.documentElement);
      this.bgMat.uniforms.uLight.value = light ? 1 : 0;
      // Shader outputs display-space color; keep the shared surface's exact sRGB tone.
      this.bgMat.uniforms.uBase.value.set(style.getPropertyValue("--mm-bg").trim() || "#efe9e2").convertLinearToSRGB();
      this.mat.blending = light ? THREE.NormalBlending : THREE.AdditiveBlending;
      // Tong toi = kieu Apex: duong dong muc xanh dien, loi cam, vien xanh nhat. Tong sang giu
      // muc dam de doc duoc tren nen sang, cung hue xanh.
      const colors = light ? ["#1b4fb8","#b4510e","#2a6be0","#2b4a78"] : ["#1c9bff","#ff8a1e","#ffd9a0","#8fe6ff"];
      ["uCool","uWarm","uHot","uRim"].forEach((key,i) => this.mat.uniforms[key].value.set(colors[i]));
      this.mat.uniforms.uBoost.value = light ? 1 : 1.3;
      this.apex = !light;
      this.rings.children.forEach((ring,i) => {
        ring.material.blending = light ? THREE.NormalBlending : THREE.AdditiveBlending;
        ring.material.color.set(light ? (i ? "#2a6be0" : "#b4510e") : (i ? "#1c9bff" : "#ff8a1e"));
      });
    };
    applyTheme();
    window.addEventListener("javis-theme-change", applyTheme);

    // ---- tuong tac ----
    this.look = { x: 0, y: 0 };           // muc tieu nhin (-1..1), tu chuot hoac camera
    this.lookNow = { x: 0, y: 0 };
    this.spin = 0; this.spinNow = 0;      // goc xoay ca nguoi do keo chuot / tay
    this.zoom = 1; this.zoomNow = 1;      // 0.5 .. 2.4
    this._lastInput = 0;
    this.external = null;                 // camera dang dieu khien thi chuot tam nhuong

    this.state = "standby";
    this.energy = 0; this._energyTarget = 0;
    this.setForm(opts.form);
    this._arms = [0, 0, 0, 0];
    this._t0 = performance.now();
    this._frames = 0; this._fpsT = performance.now(); this.fps = 60;
    this.onFps = opts.onFps || null;
    this.resize();
    window.addEventListener("resize", () => this.resize());
    if (opts.interactive !== false) this._ganChuot();
    this._loop = this._loop.bind(this);
    requestAnimationFrame(this._loop);
  }

  // Chuot: di chuot = dau nhin theo; keo = xoay nguoi; con lan = phong to / thu nho.
  // Nghe tren window vi lop chom sao nam tren canvas nay.
  _ganChuot() {
    let keo = null;
    const laUI = (el) => el && el.closest && el.closest("button, input, form, .card, .tools, aside, a");
    addEventListener("pointermove", (e) => {
      this._lastInput = performance.now();
      if (!this.external) {
        this.look.x = clamp((e.clientX / innerWidth) * 2 - 1, -1, 1);
        this.look.y = clamp((e.clientY / innerHeight) * 2 - 1, -1, 1);
      }
      if (keo) { this.spin = keo.spin + (e.clientX - keo.x) * 0.008; }
    }, { passive: true });
    addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || laUI(e.target) || document.body.classList.contains("drawing")) return;
      keo = { x: e.clientX, spin: this.spin };
      document.body.classList.add("drag");
    });
    const tha = () => { keo = null; document.body.classList.remove("drag"); };
    addEventListener("pointerup", tha);
    addEventListener("pointercancel", tha);
    addEventListener("wheel", (e) => {
      if (laUI(e.target)) return;
      e.preventDefault();
      this.zoomBy(Math.exp(-e.deltaY * 0.0012));
    }, { passive: false });
    // hai ngon tren dien thoai: chum / gian de phong to
    let chum = null;
    addEventListener("touchmove", (e) => {
      if (e.touches.length !== 2) { chum = null; return; }
      const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      if (chum) this.zoomBy(d / chum);
      chum = d;
    }, { passive: true });
    addEventListener("touchend", () => { chum = null; });
  }

  zoomBy(f) { this.zoom = clamp(this.zoom * f, 0.5, 2.4); this._lastInput = performance.now(); }
  resetView() { this.zoom = 1; this.spin = 0; this.look.x = this.look.y = 0; }
  // Camera (vision.js) dieu khien: nx, ny trong -1..1
  setLook(nx, ny) { this.look.x = clamp(nx, -1, 1); this.look.y = clamp(ny, -1, 1); this._lastInput = performance.now(); }
  setSpin(rad) { this.spin = rad; }

  resize() {
    const w = this.canvas.clientWidth || window.innerWidth, h = this.canvas.clientHeight || window.innerHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this._baseZ = w / h < 1 ? 9.8 : 6.6;
    this.camera.updateProjectionMatrix();
    this.bgMat.uniforms.uRes.value.set(w, h);
  }

  setState(s) {
    if (!(s in STATES)) return;
    this.state = s;
    this.mat.uniforms.uState.value = STATES[s];
  }
  setEnergy(v) { this._energyTarget = clamp(v, 0, 1); }
  _formOf(f) { return FORMS[f] ? f : "bust"; }
  setForm(form) { this.form = this._formOf(form); this._formTarget = FORMS[this.form]; }
  toggleForm() { this.setForm(THU_TU[(THU_TU.indexOf(this.form) + 1) % THU_TU.length]); return this.form; }
  // Canh tay bat chuoc (radian): trai/phai = phia man hinh; null = tha long
  setArms(l, r) { this._arms = [l ? l[0] : 0, l ? l[1] : 0, r ? r[0] : 0, r ? r[1] : 0]; }

  _loop(now) {
    const t = (now - this._t0) / 1000;
    const u = this.mat.uniforms;
    const speed = this.reduced ? 0.25 : 1;
    u.uTime.value = t * speed;
    this.bgMat.uniforms.uTime.value = t * speed;
    const k = this._energyTarget > this.energy ? 0.35 : 0.08;
    this.energy += (this._energyTarget - this.energy) * k;
    const base = this.state === "thinking" ? 0.25 : this.state === "listening" ? 0.15 : 0;
    u.uEnergy.value = Math.max(this.energy, base);
    this.bgMat.uniforms.uEnergy.value = u.uEnergy.value;
    const fv = u.uForm.value, ft = this._formTarget;
    fv.x += (ft[0] - fv.x) * 0.05; fv.y += (ft[1] - fv.y) * 0.05; fv.z += (ft[2] - fv.z) * 0.05; fv.w += (ft[3] - fv.w) * 0.05;
    // Canh tay: lo xo co giam chan (mem, co da, khong giat) thay cho noi suy thang
    const av = u.uArms.value, at = this._arms, vv = this._armV || (this._armV = [0, 0, 0, 0]);
    ["x", "y", "z", "w"].forEach((k, i) => {
      vv[i] += (at[i] - av[k]) * 0.09; vv[i] *= 0.72; av[k] += vv[i];
    });
    const uMorphV = fv.z;
    if (u.uAssemble.value < 1) u.uAssemble.value = Math.min(1, t / 3.8);
    u.uErr.value += ((this.state === "error" ? 0.6 : 0) - u.uErr.value) * 0.08;

    // Khong ai dong vao 6 giay: dau tu nhin quanh nhe nhang
    const ranh = now - this._lastInput > 6000;
    const lx = ranh ? Math.sin(t * 0.3) * 0.35 : this.look.x;
    const ly = ranh ? Math.sin(t * 0.21) * 0.15 : this.look.y;
    this.lookNow.x += (lx - this.lookNow.x) * 0.08;
    this.lookNow.y += (ly - this.lookNow.y) * 0.08;
    u.uHeadYaw.value = this.lookNow.x * 0.55;
    u.uHeadPitch.value = this.lookNow.y * 0.32;
    this.spinNow += (this.spin - this.spinNow) * 0.12;
    this.body.rotation.y = this.spinNow + this.lookNow.x * 0.16 + uMorphV * t * 0.12 * speed;

    this.zoomNow += (this.zoom - this.zoomNow) * 0.12;
    const vao = this.reduced ? 0 : Math.pow(1 - u.uAssemble.value, 2);       // mo man: camera lui xa roi day vao
    const z = this._baseZ * (1 - 0.1 * u.uForm.value.w) * (1 + 0.28 * vao) / this.zoomNow;
    // phong to thi camera ha dan xuong ngang mat
    const cy = 0.5 + 0.2 * fv.w + (this.zoomNow - 1) * 0.35 * (1 - uMorphV);
    this.camera.position.set(0, cy + 0.35, z);
    this.camera.lookAt(0, cy, 0);

    const ringSpeed = this.state === "thinking" ? 3 : 1;
    this.rings.children.forEach(r => {
      r.rotation.z += r.userData.spin * 0.01 * ringSpeed * speed;
      r.material.opacity = r.userData.o * (0.3 + uMorphV * 0.7);
    });
    this.rings.visible = uMorphV > 0.05 || this.state !== "standby";

    // loi sang: o nguc (chan dung) -> tam qua cau; phong theo giong
    const m = uMorphV, e = u.uEnergy.value;
    const pulse = this.state === "thinking" ? 0.12 * Math.sin(t * 5) : 0;
    // loi sang: nguc (robot/nguoi), tam qua cau, trong mat (tuong)
    this.core.position.set(Math.sin(u.uHeadYaw.value) * 0.2 * fv.w, 0.15 * (fv.x + fv.y) + 0.2 * m + 1.12 * fv.w, 0.44 * fv.x + 0.3 * fv.y + 0.3 * fv.w);
    const sc = (0.5 + m * 0.9 - fv.w * 0.15) * (1 + e * 1.2 + pulse);
    this.core.scale.set(sc, sc, 1);
    this.core.material.opacity = Math.min(1, 0.45 + e * 0.6 + pulse);
    this.core.material.color.set(this.state === "error" ? "#ff5d73" : this.state === "listening" ? "#bff5e8" : "#ffffff");

    // Tho (kieu Apex): ca tuong phong nhe len xuong cung nhip voi do sang cua loi cam.
    const tho = this.reduced ? 0 : Math.sin(t * 1.25);
    const thoK = 1 + 0.010 * tho * (0.4 + fv.w);
    this.body.scale.set(thoK, thoK, thoK);
    if (fv.w > 0.5) {
      const dark = this.apex;
      const sb = (1.45 + 0.12 * tho) * (1 + e * 0.9 + pulse) * fv.w;     // loi cam trong dau
      this.core.scale.set(Math.max(sc, sb), Math.max(sc, sb), 1);
      this.core.material.opacity = Math.min(1, (dark ? 0.62 : 0.0) + 0.1 * tho + e * 0.5 + pulse);
      if (dark && this.state === "standby") this.core.material.color.set("#ff9a40");
    }

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
