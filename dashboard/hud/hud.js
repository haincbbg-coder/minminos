// MinMin HUD - dieu phoi: noi canh 3D, chom sao, giong noi va su kien tu may chu.
import { MinMinScene } from "./scene.js";
import { Constellation, DOMAINS, domainForTool } from "./constellation.js";
import { VoiceIO } from "./voice.js";
import { Bridge, fetchAgents, fetchKpi } from "./bridge.js";
import { Vision } from "./vision.js";

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
const DEMO = params.has("demo");
const BRAIN = params.get("brain") || "brain";
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const STATE_TEXT = { standby: "CHỜ LỆNH", listening: "ĐANG NGHE", thinking: "ĐANG XỬ LÝ", speaking: "ĐANG TRẢ LỜI", error: "CÓ LỖI" };
const DOMAIN_INFO = {
  sales:    ["Đơn hàng Pancake POS của HALIMI và MeiMei: đơn mới, đơn hoàn, doanh thu theo mã.", ["Hôm nay có bao nhiêu đơn mới?", "Mã nào bán chạy nhất tuần này?"]],
  stock:    ["Tồn kho ròng, hàng sắp về, cảnh báo mã cần đặt thêm.", ["Mã nào sắp hết hàng cần đặt thêm?"]],
  ads:      ["Tài khoản quảng cáo Meta: camp đang chạy, chi tiêu, chi phí mỗi đơn, bật tắt camp.", ["Chi phí mỗi đơn hôm qua của các camp thế nào?", "Camp nào đang đốt tiền?"]],
  pages:    ["Fanpage: đăng bài, lên lịch, theo dõi tương tác.", ["Bài nào đang tương tác tốt nhất tuần này?"]],
  cskh:     ["Tin nhắn khách hàng và Zalo.", ["Có tin nhắn khách nào chưa trả lời không?"]],
  finance:  ["Hóa đơn điện tử, thuế, lợi nhuận theo mã, lương marketing.", ["Tháng này lãi lỗ thế nào?", "Hóa đơn đầu vào đầu ra tháng này?"]],
  email:    ["Hộp thư Gmail của công ty.", ["Sáng nay có email nào quan trọng?"]],
  memory:   ["Second Brain: ghi chú, wiki, những gì MinMin đã học về công việc của bố.", ["MinMin nhớ gì về kế hoạch tuần này?"]],
  schedule: ["Nhắc việc, việc hẹn giờ, vòng lặp chạy định kỳ.", ["Hôm nay có việc hẹn giờ nào?"]],
  jobs:     ["Hàng việc nền (Kanban), trợ lý và quy trình nhiều bước.", ["Việc nền nào đang chạy?"]],
  research: ["Tìm kiếm web, đọc trang, xem YouTube.", ["Xu hướng thời trang nữ tuần này là gì?"]],
  create:   ["Ảnh, video, landing page, nội dung quảng cáo.", ["Viết 3 caption cho mẫu mới nhất"]],
};

// ---------- phien hoi thoai cua HUD: mot phien moi ngay ----------
function hudSession() {
  const day = new Date().toLocaleDateString("sv-SE");
  let s = null;
  try { s = JSON.parse(localStorage.getItem("minmin.hud.session") || "null"); } catch (e) {}
  if (!s || s.day !== day) {
    s = { day, id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()).replace(/-/g, "") };
    try { localStorage.setItem("minmin.hud.session", JSON.stringify(s)); } catch (e) {}
  }
  return s.id;
}
const HUD_SID = hudSession();

// ---------- dung giao dien ----------
let form = params.get("form") === "orb" ? "orb" : (localStorage.getItem("minmin.hud.form") || "portrait");
const scene = new MinMinScene($("scene"), {
  reducedMotion, form, quality: params.get("quality") || "high",
  onFps: (f) => { $("fps").textContent = f.toFixed(0) + " FPS"; watchFps(f); },
});
$("formText").textContent = form === "orb" ? "QUẢ CẦU" : "CHÂN DUNG";

const web = new Constellation($("web"), { reducedMotion, onSelect: openCard });

const eq = $("eq");
for (let i = 0; i < 28; i++) eq.appendChild(document.createElement("i"));
const bars = [...eq.children];

let state = "standby";
function setState(s) {
  if (state === s) return;
  state = s;
  document.body.dataset.state = s;
  $("stateText").textContent = STATE_TEXT[s] || s;
  scene.setState(s);
  web.setThinking(s === "thinking");
}

// ---------- dong ho ----------
function tick() {
  const d = new Date();
  $("clock").textContent = d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", hour12: false });
  const s = d.toLocaleDateString("vi-VN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  $("date").textContent = s.charAt(0).toUpperCase() + s.slice(1);
}
tick(); setInterval(tick, 5000);

// ---------- ket noi ----------
function setConn(up, why) {
  const c = $("conn");
  c.className = "conn " + (up ? "up" : "down");
  c.querySelector("span").textContent = up ? "Đã nối MinMin" : why === "auth" ? "Chưa đăng nhập" : "Mất kết nối · đang nối lại";
  if (why === "auth") {
    $("gate").hidden = false;
    $("gateMsg").innerHTML = "HUD cần đăng nhập MinMin trên trình duyệt này. Bố mở trang chính, đăng nhập một lần rồi quay lại đây.";
    $("gateBtn").textContent = "Mở trang đăng nhập";
    $("gateBtn").onclick = () => { location.href = "/"; };
    $("gateQuiet").hidden = true;
  }
}

// ---------- luot dang chay ----------
const running = new Set();
let focusSid = null;
let replyText = "";
let toolCount = 0;
let lastRunLi = {};         // session -> <li> dang chay gan nhat
let idleTimer = null;
let spokenFor = new Set();

function updRunning() { $("running").textContent = String(running.size); }

function showYou(text) {
  const t = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  $("you").innerHTML = "";
  const b = document.createElement("b"); b.textContent = `BỐ · ${t}`;
  $("you").append(b, document.createTextNode(clip(stripCtx(text), 140)));
}
function showReply(text, streaming) {
  const el = $("reply");
  el.textContent = tail(plain(text), 260);
  if (streaming) { const c = document.createElement("span"); c.className = "cur"; el.appendChild(c); }
}
function stripCtx(t) { return String(t || "").replace(/^\[[^\]]*\]\s*/g, "").replace(/^\[[\s\S]*?\]\n\n/, "").trim(); }
function clip(s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; }
function tail(s, n) { s = String(s || ""); if (s.length <= n) return s; const cut = s.slice(-n); const i = cut.indexOf(" "); return "…" + cut.slice(i + 1); }
function plain(md) {
  return String(md || "").replace(/<!--[\s\S]*?-->/g, "").replace(/```[\s\S]*?```/g, " ").replace(/\|/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[*_#>`]+/g, "").replace(/\s+/g, " ").trim();
}

function feedAdd(cls, what, detail, status) {
  const ol = $("feed");
  const empty = ol.querySelector(".empty"); if (empty) empty.remove();
  const li = document.createElement("li"); li.className = cls;
  const t = document.createElement("span"); t.className = "t";
  t.textContent = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  const w = document.createElement("span"); w.className = "w"; w.textContent = what;
  if (detail) { const sm = document.createElement("small"); sm.textContent = detail; w.appendChild(sm); }
  const s = document.createElement("span"); s.className = "s"; s.textContent = status;
  li.append(t, w, s);
  ol.prepend(li);
  while (ol.children.length > 14) ol.lastChild.remove();
  return li;
}

function labelFor(key) { const d = DOMAINS.find(x => x.key === key); return d ? d.label : "Công cụ"; }
function prettyTool(name) {
  return String(name || "").replace(/^mcp__/, "").replace(/__/g, " · ").replace(/[_-]+/g, " ").slice(0, 48);
}

const H = {
  brain: BRAIN,
  onConnection: setConn,
  onRunning: (n) => { if (n) setState("thinking"); $("running").textContent = String(n); },
  onUser(sid, text) {
    focusSid = sid; running.add(sid); updRunning();
    showYou(text); replyText = ""; showReply("", true);
    clearTimeout(idleTimer);
    if (state !== "speaking") setState("thinking");
  },
  onStatus(sid) { if (sid) { running.add(sid); updRunning(); } if (state === "standby") setState("thinking"); },
  onTool(sid, tool) {
    running.add(sid); updRunning();
    toolCount++; $("toolCount").textContent = String(toolCount);
    const key = domainForTool(tool);
    if (key) web.pulse(key);
    lastRunLi[sid] = feedAdd("run", key ? labelFor(key) : "Công cụ", prettyTool(tool), "…");
    if (state === "standby") setState("thinking");
  },
  onToolResult(sid, d) {
    const li = lastRunLi[sid]; if (!li) return;
    const bad = d && (d.is_error || d.error || d.ok === false);
    li.className = bad ? "bad" : "ok";
    li.querySelector(".s").textContent = bad ? "LỖI" : "XONG";
    lastRunLi[sid] = null;
  },
  onStream(sid, chunk) {
    if (!focusSid) focusSid = sid;
    if (sid !== focusSid) return;
    replyText += chunk; showReply(replyText, true);
  },
  onResponse(sid, content) {
    if (sid !== focusSid && focusSid) return;
    if (content && content.trim()) replyText = content;
    showReply(replyText, false);
  },
  onDone(sid) {
    running.delete(sid); updRunning();
    const li = lastRunLi[sid]; if (li) { li.className = "ok"; li.querySelector(".s").textContent = "XONG"; lastRunLi[sid] = null; }
    if (sid !== focusSid) { if (!running.size && state === "thinking") setState("standby"); return; }
    showReply(replyText, false);
    // chi doc to nhung luot bo hoi qua HUD (tranh doc trung voi trang chinh)
    if ((sid === HUD_SID || DEMO) && voiceOn && replyText.trim() && !spokenFor.has(sid + replyText.length)) {
      spokenFor.add(sid + replyText.length);
      voice.say(replyText);
    } else {
      setState(running.size ? "thinking" : "standby");
    }
  },
  onError(sid, msg) {
    feedAdd("bad", "Lỗi", clip(plain(msg), 60), "LỖI");
    setState("error");
    running.delete(sid); updRunning();
    setTimeout(() => setState(running.size ? "thinking" : "standby"), 2600);
  },
};

// ---------- giong noi ----------
let voiceOn = false;
const voice = new VoiceIO({
  ttsVoice: params.get("voice") || undefined,
  onWake(rest) { chime(); setState("listening"); $("you").innerHTML = "<b>ĐANG NGHE</b>" + (rest ? escapeHtml(rest) : "Bố nói đi ạ…"); },
  onInterim(text) { if (state === "listening") $("you").innerHTML = "<b>ĐANG NGHE</b>" + escapeHtml(text); },
  onCommand(text) { ask(text); },
  onStatus(s) {
    if (s === "wake-timeout" && state === "listening") setState("standby");
    if (s === "no-mic") { $("hint").textContent = "Không mở được micro. Bố cho phép micro cho trang này rồi tải lại."; }
    if (s === "no-sr") { $("hint").innerHTML = "Trình duyệt này không nhận giọng nói. Dùng Chrome hoặc Edge, hoặc nhấn <kbd>/</kbd> để gõ."; }
  },
  onSpeakStart() { setState("speaking"); },
  onSpeakError(msg) {
    feedAdd("bad", "Giọng đọc", clip(msg, 70) + " · kiểm tra Cài đặt → Giọng nói", "LỖI");
  },
  onSpeakEnd() { setState(running.size ? "thinking" : "standby"); },
});
function escapeHtml(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

function chime() {
  try {
    const ctx = voice._audio(), o = ctx.createOscillator(), g = ctx.createGain();
    o.type = "sine"; o.frequency.setValueAtTime(660, ctx.currentTime); o.frequency.exponentialRampToValueAtTime(990, ctx.currentTime + 0.12);
    g.gain.setValueAtTime(0.0001, ctx.currentTime); g.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.35);
    o.connect(g).connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.4);
  } catch (e) {}
}

// ---------- gui lenh ----------
// Cau hoi ve nhung gi truoc mat -> tu chup camera gui kem
const HOI_NHIN = /(nh[iì]n|xem|th[aấ]y|camera|m[oô] t[aả]|tr[uư][oớ]c m[aặ]t|c[aá]i n[aà]y|c[aá]i g[iì] [dđ][aâ]y|[dđ][aâ]y l[aà] g[iì]|[dđ]ang c[aầ]m|[dđ][oọ]c gi[uú]p|n[eé]t v[eẽ]|h[iì]nh v[eẽ]|t[oô]i v[eẽ])/i;

async function ask(text, opts = {}) {
  text = String(text || "").trim();
  if (!text) return;
  voice.cancelSpeech();
  focusSid = HUD_SID;
  const kemAnh = opts.image || (vision && (vision.on || vision.hasInk()) && HOI_NHIN.test(text));
  if (kemAnh && !DEMO) {
    showYou(text); replyText = ""; showReply("", true); setState("thinking");
    flash();
    const blob = await vision.snapshot();
    feedAdd("run", "Mắt nhìn", vision.on ? "Chụp camera gửi MinMin" : "Gửi nét vẽ cho MinMin", "…");
    const ok = await bridge.sendWithImage(text, HUD_SID, blob);
    const li = $("feed").firstChild;
    if (li) { li.className = ok ? "ok" : "bad"; li.querySelector(".s").textContent = ok ? "ĐÃ GỬI" : "LỖI"; }
    if (!ok) { toast(bridge.loi || "Không gửi được ảnh", true); setState("error"); setTimeout(() => setState("standby"), 2000); return; }
    running.add(HUD_SID); updRunning();
    return;
  }
  if (DEMO) { demoAnswer(text); return; }
  if (!bridge.send(text, HUD_SID)) { feedAdd("bad", "Chưa gửi được", "Mất kết nối tới MinMin", "LỖI"); setState("error"); setTimeout(() => setState("standby"), 2000); return; }
  running.add(HUD_SID); updRunning();
  showYou(text); replyText = ""; showReply("", true); setState("thinking");
}

// ---------- the chi tiet node ----------
function openCard(n) {
  const card = $("card");
  const info = DOMAIN_INFO[n.key];
  $("cardKind").textContent = n.kind === "agent" ? "TRỢ LÝ" : "BỘ PHẬN";
  $("cardTitle").textContent = n.label;
  $("cardBody").textContent = n.kind === "agent" ? (n.desc || "Trợ lý chuyên trách trong brain của MinMin.") : (info ? info[0] : "");
  const asks = $("cardAsks"); asks.innerHTML = "";
  const qs = n.kind === "agent" ? [`${n.label} đang theo dõi việc gì?`] : (info ? info[1] : []);
  qs.forEach(q => { const b = document.createElement("button"); b.textContent = q; b.onclick = () => { card.hidden = true; ask(q); }; asks.appendChild(b); });
  const w = innerWidth, h = innerHeight;
  card.style.left = Math.min(Math.max(16, n.x + (n.x < w / 2 ? 24 : -344)), w - 336) + "px";
  card.style.top = Math.min(Math.max(16, n.y - 40), h - 240) + "px";
  card.hidden = false;
}
$("cardX").onclick = () => { $("card").hidden = true; };

// ---------- ban phim ----------
addEventListener("keydown", (e) => {
  const typing = document.activeElement === $("askInput");
  if (e.key === "Escape") {
    $("card").hidden = true;
    if (typing || !$("ask").hidden) { $("ask").hidden = true; $("askInput").blur(); return; }
    if (voice.speaking) { voice.cancelSpeech(); return; }
    if (running.has(HUD_SID)) { bridge.stop(HUD_SID); feedAdd("bad", "Đã dừng", "Bố dừng lượt này", "DỪNG"); }
    return;
  }
  if (typing) return;
  if (e.key === "/") { e.preventDefault(); $("ask").hidden = false; $("askInput").focus(); }
  else if (e.code === "Space") { e.preventDefault(); if (voiceOn) voice.wakeManually(); else { $("ask").hidden = false; $("askInput").focus(); } }
  else if (e.key === "f" || e.key === "F") doiHinh();
  else if (e.key === "h" || e.key === "H") $("tChu").click();
  else if (e.key === "b" || e.key === "B") $("tBoPhan").click();
  else if (e.key === "o" || e.key === "O") $("tChiNguoi").click();
  else if (e.key === "c" || e.key === "C") $("tCam").click();
  else if (e.key === "d" || e.key === "D") $("tVe").click();
  else if (e.key === "x" || e.key === "X") $("tXoa").click();
  else if (e.key === "v" || e.key === "V") $("tNhin").click();
  else if (e.key === "r" || e.key === "R") $("tGoc").click();
  else if (e.key === "Enter" && e.altKey) { document.documentElement.requestFullscreen?.(); }
});
$("ask").addEventListener("submit", (e) => { e.preventDefault(); const v = $("askInput").value; $("askInput").value = ""; $("ask").hidden = true; ask(v); });
$("scene").addEventListener("dblclick", () => document.documentElement.requestFullscreen?.());

// ---------- thanh cong cu, che do an, camera ----------
function doiHinh(f) {
  form = f || scene.toggleForm();
  if (f) scene.setForm(f);
  try { localStorage.setItem("minmin.hud.form", form); } catch (e) {}
  $("formText").textContent = form === "orb" ? "QUẢ CẦU" : "CHÂN DUNG";
}
function nhoLai(k, v) { try { localStorage.setItem("minmin.hud." + k, v ? "1" : "0"); } catch (e) {} }
function daNho(k) { try { return localStorage.getItem("minmin.hud." + k) === "1"; } catch (e) { return false; } }
function batTat(id, cls, on, luu) {
  $(id).setAttribute("aria-pressed", on ? "true" : "false");
  if (cls) document.body.classList.toggle(cls, on);
  if (luu) nhoLai(luu, on);
}
let _toastT = null;
function toast(msg, bad) {
  const t = $("toast");
  if (!msg) { t.hidden = true; return; }
  t.textContent = msg; t.className = "toast" + (bad ? " bad" : ""); t.hidden = false;
  clearTimeout(_toastT); _toastT = setTimeout(() => { t.hidden = true; }, bad ? 7000 : 3500);
}
function flash() {
  const f = document.createElement("div");
  f.style.cssText = "position:fixed;inset:0;z-index:6;background:#fff;opacity:.35;pointer-events:none;transition:opacity .35s";
  document.body.appendChild(f); requestAnimationFrame(() => { f.style.opacity = "0"; }); setTimeout(() => f.remove(), 400);
}

const vision = new Vision({
  video: $("camVideo"), overlay: $("camDots"), ink: $("ink"), scene,
  onGesture: (g) => { $("camGesture").textContent = g; },
  onStatus: (m, bad) => toast(m, bad),
  onForm: (f) => doiHinh(f),
});
vision.attachMouseInk();

$("tChu").onclick = () => batTat("tChu", "no-text", $("tChu").getAttribute("aria-pressed") !== "true", "notext");
$("tBoPhan").onclick = () => {
  const an = $("tBoPhan").getAttribute("aria-pressed") !== "true";
  batTat("tBoPhan", null, an, "noweb"); web.setVisible(!an);
};
$("tChiNguoi").onclick = () => {
  const on = $("tChiNguoi").getAttribute("aria-pressed") !== "true";
  batTat("tChiNguoi", "solo", on, "solo"); web.setVisible(!on && $("tBoPhan").getAttribute("aria-pressed") !== "true");
};
$("tHinh").onclick = () => doiHinh();
$("tGoc").onclick = () => scene.resetView();
$("tFull").onclick = () => { if (document.fullscreenElement) document.exitFullscreen?.(); else document.documentElement.requestFullscreen?.().catch(() => {}); };
$("tVe").onclick = () => {
  vision.drawMode = $("tVe").getAttribute("aria-pressed") !== "true";
  batTat("tVe", "drawing", vision.drawMode);
  if (vision.drawMode) toast("Vẽ bằng chuột, hoặc giơ 1 ngón tay trước camera. Vẽ xong nói “Min Min ơi, đây là gì” hoặc bấm Nhìn.");
};
$("tXoa").onclick = () => vision.clearInk();
$("tCam").onclick = async () => {
  if (vision.on) { vision.stop(); $("cam").hidden = true; $("tFlip").hidden = true; batTat("tCam", null, false); return; }
  $("cam").hidden = false;
  const ok = await vision.start();
  if (!ok) { $("cam").hidden = true; return; }
  batTat("tCam", null, true);
  // dien thoai / may co nhieu camera: cho doi camera truoc - sau
  try { const ds = await navigator.mediaDevices.enumerateDevices(); $("tFlip").hidden = ds.filter(d => d.kind === "videoinput").length < 2; } catch (e) {}
  if (vision.ready) toast("Camera đã bật. Xòe tay: MinMin nhìn theo · chỉ 1 ngón: vẽ · nắm tay: xoay · chụm ngón: phóng to · chữ V: đổi hình.");
};
$("tFlip").onclick = async () => { const f = await vision.flip(); toast(f === "user" ? "Camera trước" : "Camera sau: đưa camera vào vật cần MinMin xem"); };
$("tNhin").onclick = () => {
  const cau = vision.on ? "Bố đang cho con xem qua camera. Con nhìn thấy gì? Mô tả ngắn gọn, đọc chữ nếu có, và nói điều đáng chú ý."
    : "Bố vừa vẽ trên màn hình. Con xem hình vẽ này là gì và mô tả ngắn gọn.";
  if (!vision.on && !vision.hasInk()) { toast("Bật Camera hoặc vẽ gì đó trước rồi bấm Nhìn."); return; }
  ask(cau, { image: true });
};
if (daNho("notext")) batTat("tChu", "no-text", true);
if (daNho("noweb")) { batTat("tBoPhan", null, true); web.setVisible(false); }
if (daNho("solo")) { batTat("tChiNguoi", "solo", true); web.setVisible(false); }

// thanh cong cu mo di khi khong dong chuot 4 giay
let _idleT = null;
addEventListener("pointermove", () => { document.body.classList.remove("idle"); clearTimeout(_idleT); _idleT = setTimeout(() => document.body.classList.add("idle"), 4000); }, { passive: true });

// ---------- vong nang luong -> canh 3D + thanh song ----------
function energyLoop() {
  let lv = voice.level();
  if (state === "thinking") lv = Math.max(lv, 0.08 + Math.abs(Math.sin(performance.now() / 600)) * 0.1);
  scene.setEnergy(lv);
  const now = performance.now() / 1000;
  for (let i = 0; i < bars.length; i++) {
    const mid = 1 - Math.abs(i - bars.length / 2) / (bars.length / 2);
    const idle = 2 + Math.sin(now * 2 + i * 0.6) * 1.5;
    const h = idle + lv * 22 * (0.35 + mid * 0.65) * (0.7 + 0.3 * Math.sin(now * 14 + i * 1.7));
    bars[i].style.height = Math.max(3, Math.min(26, h)).toFixed(1) + "px";
  }
  requestAnimationFrame(energyLoop);
}
requestAnimationFrame(energyLoop);

// ---------- may yeu: giam chat luong ----------
let slow = 0;
function watchFps(f) { if (f < 26) slow++; else slow = 0; if (slow === 3 && !params.has("quality")) { const u = new URL(location.href); u.searchParams.set("quality", "low"); location.replace(u); } }

// ---------- khoi dong ----------
const bridge = new Bridge(H);

async function boot() {
  if (DEMO) { setConn(true); $("conn").querySelector("span").textContent = "Bản xem trước (dữ liệu mẫu)"; demoData(); }
  else {
    bridge.connect();
    fetchAgents(BRAIN).then(a => web.setAgents(a));
    loadKpi(); setInterval(loadKpi, 60000);
  }
}
async function loadKpi() {
  const j = await fetchKpi(BRAIN);
  const list = (j && (j.kpis || [])) || [];
  renderKpi(list, j && j.updated);
  // khoi "Can chu y" cua bang dieu hanh -> nhat ky, moi canh bao chi hien mot lan
  ((j && j.alerts) || []).forEach(a => {
    if (seenAlerts.has(a.text)) return;
    seenAlerts.add(a.text);
    const bad = a.level === "critical" || a.level === "serious";
    feedAdd(bad ? "bad" : a.level === "good" ? "ok" : "run", "Cần chú ý", a.text, bad ? "GẤP" : "LƯU Ý");
  });
}
const seenAlerts = new Set();
function renderKpi(list, updated) {
  $("kpiBox").hidden = !list.length;
  const box = $("kpiTiles"); box.innerHTML = "";
  list.forEach(k => {
    const d = document.createElement("div"); d.className = "tile " + (k.tone || "");
    d.innerHTML = `<div class="l"></div><div class="v"></div><div class="d"></div>`;
    d.querySelector(".l").textContent = k.label;
    d.querySelector(".v").textContent = k.value; if (k.unit) { const s = document.createElement("small"); s.textContent = k.unit; d.querySelector(".v").appendChild(s); }
    d.querySelector(".d").textContent = k.delta || "";
    box.appendChild(d);
  });
  if (updated) { const t = new Date(updated); $("kpiUpd").textContent = isNaN(t) ? "" : "· " + t.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }); }
}

// Mo tu nut "HUD man phu" (?fs=1): cu bam dau tien tren man bat dau dua HUD vao toan man hinh
function toanManHinh() {
  if (!params.has("fs") || document.fullscreenElement) return;
  try { document.documentElement.requestFullscreen?.().catch(() => {}); } catch (e) {}
}
$("gateBtn").onclick = async () => {
  toanManHinh();
  $("gate").hidden = true;
  voiceOn = await voice.start();
  if (!voiceOn && voice.supported === false) voiceOn = true; // van doc duoc, chi khong nghe
  if (DEMO && !voiceOn) voiceOn = true;
};
$("gateQuiet").onclick = () => { toanManHinh(); $("gate").hidden = true; voice._audio(); };
// Che do kiosk: ?autostart=1 bo qua man bat dau (can co --autoplay-policy khi mo trinh duyet)
if (params.get("autostart") === "1") { $("gate").hidden = true; voice.start().then(ok => { voiceOn = ok; }); }

boot();

// ================= BAN XEM TRUOC (?demo=1) =================
function demoData() {
  web.setAgents([
    { slug: "nhan-vien-dat-hang", name: "Nhân viên đặt hàng" },
    { slug: "tro-ly-ads", name: "Trợ lý quảng cáo" },
    { slug: "ke-toan", name: "Kế toán thuế" },
  ]);
  renderKpi([
    { label: "Đơn mới hôm nay", value: "414", delta: "+12% so với hôm qua", tone: "up" },
    { label: "Doanh thu hôm nay", value: "86,4", unit: "tr", delta: "+8%", tone: "up" },
    { label: "Chi quảng cáo", value: "18,4", unit: "tr", delta: "56 tài khoản" },
    { label: "Chi phí mỗi đơn", value: "44.500", unit: "đ", delta: "vượt ngưỡng 40k", tone: "warn" },
    { label: "Tỷ lệ hoàn 7 ngày", value: "9,8", unit: "%", delta: "-1,2 điểm", tone: "up" },
    { label: "Mã sắp hết hàng", value: "6", delta: "cần đặt thêm", tone: "warn" },
  ], new Date().toISOString());
  const sid = "demo-bg";
  setTimeout(() => { H.onUser(sid, "Kiểm tra camp nào đang đốt tiền"); }, 1500);
  setTimeout(() => H.onTool(sid, "mcp__meta-ads-graph__insights"), 2600);
  setTimeout(() => H.onToolResult(sid, {}), 3600);
  setTimeout(() => H.onTool(sid, "pancake_pos_orders"), 4000);
  setTimeout(() => H.onToolResult(sid, {}), 5000);
  const txt = "Có 3 camp đang có chi phí mỗi đơn trên 60 nghìn: HH214, HH187 và HH233. Con đề xuất giảm ngân sách HH214 và tạm dừng HH233, bố duyệt thì con làm.";
  let i = 0;
  setTimeout(function feed() { if (i < txt.length) { H.onStream(sid, txt.slice(i, i + 6)); i += 6; setTimeout(feed, 40); } else { H.onResponse(sid, txt); H.onDone(sid); } }, 5400);
}
function demoAnswer(q) {
  const sid = HUD_SID;
  H.onUser(sid, q);
  const f = q.toLowerCase();
  const tool = /đơn|bán|doanh/.test(f) ? "pancake_pos_orders" : /camp|quảng|ads/.test(f) ? "mcp__meta-ads-graph__insights"
    : /hết|kho|đặt/.test(f) ? "ton_kho_dat_hang" : /email|mail/.test(f) ? "gmail_search" : "vault_read";
  setTimeout(() => H.onTool(sid, tool), 700);
  setTimeout(() => H.onToolResult(sid, {}), 1600);
  const txt = "Đây là bản xem trước nên con dùng số liệu mẫu. Khi chạy thật trên MinMin, con sẽ lấy số liệu trực tiếp và trả lời bố ngay tại đây.";
  let i = 0;
  setTimeout(function feed() { if (i < txt.length) { H.onStream(sid, txt.slice(i, i + 6)); i += 6; setTimeout(feed, 35); } else { H.onResponse(sid, txt); H.onDone(sid); } }, 1900);
}

// Cua de kiem tra tu bang dieu khien trinh duyet (F12): MinMinHUD.setState("speaking") ...
window.MinMinHUD = { scene, web, vision, setState, ask, pulse: (k) => web.pulse(k) };
