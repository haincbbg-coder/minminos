// MinMin HUD - dieu phoi: noi canh 3D, chom sao, giong noi va su kien tu may chu.
import { MinMinScene } from "./scene.js?v=14";
import { Constellation, DOMAINS, domainForTool } from "./constellation.js";
import { VoiceIO } from "./voice.js";
import { Bridge, fetchAgents, fetchKpi } from "./bridge.js";
import { Vision, tenDoVat, CHE_DO } from "./vision.js";
import { DieuKhienMay, TayMay, CU_CHI_MAY, taoBat } from "./dieukhien.js";
import { hinhTay, HINH } from "./hinhtay.js";

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
const TEN_HINH = { figure: "NGƯỜI HẠT", bust: "TƯỢNG HẠT", robot: "ROBOT GIÁP", portrait: "NGƯỜI", orb: "QUẢ CẦU" };
let form = (() => {
  const p = params.get("form");
  if (TEN_HINH[p]) return p;
  try { const f = localStorage.getItem("minmin.hud.form4"); if (TEN_HINH[f]) return f; } catch (e) {}
  return "figure";
})();
// Chat luong hinh (26.10.82): high = sac net, mid = can bang, low = nhe. Khach tu chon, may yeu tu ha.
const CL_TEN = { high: "Sắc nét", mid: "Cân bằng", low: "Nhẹ" };
let clTuChon = false;
const CL0 = (() => {
  const q = params.get("quality");
  if (CL_TEN[q]) { clTuChon = true; return q; }
  try { const c = localStorage.getItem("minmin.hud.cl"); if (CL_TEN[c]) { clTuChon = true; return c; } } catch (e) {}
  return "high";
})();
const scene = new MinMinScene($("scene"), {
  reducedMotion, form, quality: CL0 === "low" ? "low" : "high",
  onFps: (f) => { $("fps").textContent = f.toFixed(0) + " FPS"; watchFps(f); },
});
if (params.get("debug")) window.__mmScene = scene;
function datCL(c, luu) {
  scene.setQuality(c); $("tCLtxt").textContent = CL_TEN[c]; $("tCL").dataset.cl = c;
  if (luu) try { localStorage.setItem("minmin.hud.cl", c); } catch (e) {}
}
$("tCL").onclick = () => { clTuChon = true; datCL({ high: "mid", mid: "low", low: "high" }[$("tCL").dataset.cl || "high"], true); };
datCL(CL0, false);
$("formText").textContent = TEN_HINH[form] || form;

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
  sauTrangThai.forEach(f => f(s));
}
const sauTrangThai = [];      // bang Tro chuyen, Luong phan tich dang ky sau

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
    streamLog("a", "CÔNG CỤ", prettyTool(tool));
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
    if (replyText.trim()) talk.minmin(replyText);
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
  onWake(rest) {
    chime(); setState("listening"); $("you").innerHTML = "<b>ĐANG NGHE</b>" + (rest ? escapeHtml(rest) : "Bố nói đi ạ…");
    talk.goi(); streamLog("v", "GIỌNG", "nghe thấy từ gọi");
  },
  onInterim(text) { if (state === "listening" || voice.noiLien) $("you").innerHTML = "<b>ĐANG NGHE</b>" + escapeHtml(text); },
  onHeard(text, final, goi) { talk.nghe(text, final, goi); if (final && text.trim()) streamLog("v", "NGHE", text); },
  onCommand(text) { talk.lenh(text); ask(text, { tuGiong: true }); },
  onEngine(e) { talk.capNhat(); streamLog("v", "NHẬN GIỌNG", e === "whisper" ? "Whisper trên máy chủ MinMin" : "trình duyệt"); },
  onStatus(s, chiTiet) {
    if (s === "wake-timeout" && state === "listening") setState(running.size ? "thinking" : "standby");
    talk.trangThai(s, chiTiet);
  },
  onSpeakStart() { setState("speaking"); },
  onSpeakError(msg) {
    feedAdd("bad", "Giọng đọc", clip(msg, 90), "LỖI");
    talk.loi("Giọng đọc: " + msg);
    toast("Giọng đọc lỗi: " + msg, true);
  },
  onSpeakEnd() { setState(running.size ? "thinking" : "standby"); },
});

// ---------- bang TRO CHUYEN (0.64.87): bat tat mic, dang nghe hay im lang, chu nghe duoc ----------
const LOI_NGHE = {
  "network": "Trình duyệt không nối được dịch vụ nhận giọng (Cốc Cốc, Brave hay gặp).",
  "service-not-allowed": "Trình duyệt này không cho nhận giọng. Dùng Chrome / Edge hoặc chọn Nghe: Whisper.",
  "language-not-supported": "Trình duyệt không nghe được tiếng Việt. Chọn Nghe: Whisper.",
  "audio-capture": "Không lấy được micro (ứng dụng khác đang giữ micro?).",
  "no-recorder": "Trình duyệt không ghi âm được cho Whisper.",
  "thieu_key": "Whisper cần Groq API key: vào trang Models dán Groq key (lấy miễn phí ở console.groq.com).",
  "lech_ban_nhap": "",
};
const talk = {
  _cur: null, _last: null, _loi: "", _loiAt: 0, _ghi: "",
  _li(cls, nhan, text) {
    const ol = $("talkLog"); ol.querySelector(".dim")?.remove();
    const li = document.createElement("li"); li.className = cls;
    const b = document.createElement("b"); b.textContent = nhan;
    li.append(b, document.createTextNode(text));
    ol.prepend(li);
    while (ol.children.length > 9) ol.lastChild.remove();
    return li;
  },
  _dat(li, nhan, text) { li.firstChild.textContent = nhan; li.lastChild.textContent = text; },
  nghe(text, final, goi) {
    if (!text.trim()) return;
    if (!this._cur) this._cur = this._li("nghe", "NGHE", "");
    this._cur.classList.toggle("goi", !!goi);
    this._dat(this._cur, goi ? "GỌI" : "NGHE", clip(text, 140));
    if (final) { this._last = this._cur; this._cur = null; }
  },
  goi() { this.capNhat(); },
  lenh(text) {
    const li = this._last && this._last.isConnected ? this._last : this._li("bo", "BỐ", "");
    li.className = "bo"; this._dat(li, "BỐ", clip(text, 160)); this._last = null;
  },
  bo(text) { this._li("bo", "BỐ", clip(text, 160)); },
  minmin(text) { if (text.trim()) this._li("mm", "MINMIN", clip(plain(text), 180)); },
  loi(msg) { this._loi = msg; this._loiAt = performance.now(); this.capNhat(); },
  trangThai(s, ct) {
    if (s === "no-mic") this.loi("Chưa cho phép micro: bấm ổ khóa cạnh địa chỉ web → Micro → Cho phép, rồi bật lại.");
    else if (s === "no-sr") this.loi("Trình duyệt không có nhận giọng. Chọn Nghe: Whisper.");
    else if (s === "sr-error") this.loi(LOI_NGHE[ct] || ("Nhận giọng lỗi: " + ct));
    else if (s === "whisper-error") { if (LOI_NGHE[ct] !== "") this.loi(LOI_NGHE[ct] || ("Whisper lỗi: " + ct)); }
    else if (s === "whisper-rec") this._ghi = "rec";
    else if (s === "whisper-stop" || s === "whisper-send") this._ghi = "send";
    else if (s === "whisper-idle") this._ghi = "";
    if (s === "sr-error" || s === "whisper-error" || s === "no-mic" || s === "no-sr") streamLog("a", "GIỌNG LỖI", ct || s);
    this.capNhat();
  },
  // Mot dong trang thai duy nhat, uu tien: loi moi > dang noi > dang xu ly > dang nghe > cho goi
  capNhat() {
    const bat = voice.enabled;
    const sw = $("micSw"); sw.setAttribute("aria-checked", bat ? "true" : "false");
    $("micSwText").textContent = bat ? "MIC BẬT" : "MIC TẮT";
    let k = "wake", t;
    const eng = voice.engine === "whisper" ? " · Whisper" : "";
    if (this._loi && performance.now() - this._loiAt < 12000) { k = "err"; t = this._loi; }
    else if (!bat) { k = "off"; t = voiceOn ? "Micro tắt · MinMin không nghe (vẫn đọc trả lời)" : "Micro tắt · MinMin im lặng"; }
    else if (state === "speaking") { k = "speak"; t = "MinMin đang nói…"; }
    else if (this._ghi === "send") { k = "think"; t = "Đang chuyển giọng thành chữ…"; }
    else if (state === "thinking") { k = "think"; t = "MinMin đang xử lý…"; }
    else if (voice.awake || state === "listening") { k = "listen"; t = "Đang nghe bố nói…" + eng; }
    else if (this._ghi === "rec") { k = "listen"; t = "Đang ghi âm…" + eng; }
    else if (voice.noiLien) { k = "listen"; t = "Nghe liên tục: cứ nói lệnh" + eng; }
    else t = "Đang chờ bố gọi “Min Min ơi”" + eng;
    const st = $("talkSt");
    if (st.dataset.k !== k || $("talkStText").textContent !== t) { st.dataset.k = k; $("talkStText").textContent = t; }
  },
};
async function batMic() {
  voice.cancelSpeech();
  voiceOn = true;
  const ok = await voice.start();
  talk.capNhat();
  return ok;
}
function tatMic() { voice.stop(); talk._ghi = ""; talk.capNhat(); }
sauTrangThai.push(() => talk.capNhat(), (s) => streamLog("", "TRẠNG THÁI", STATE_TEXT[s] || s));
$("micSw").onclick = () => (voice.enabled ? tatMic() : batMic());
$("noiLien").checked = voice.noiLien;
$("noiLien").onchange = () => { voice.setNoiLien($("noiLien").checked); talk.capNhat(); };
$("ngheSel").value = voice.cheDoNghe;
$("ngheSel").onchange = () => { voice.setCheDoNghe($("ngheSel").value); talk._loi = ""; talk.capNhat(); };
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
const HOI_NHIN = /(nh[iì]n|xem|th[aấ]y|camera|m[oô] t[aả]|tr[uư][oớ]c m[aặ]t|c[aá]i n[aà]y|c[aá]i g[iì]|l[aà] g[iì]|g[iì] [dđ][aâ]y|[dđ][aâ]y l[aà]|[dđ]ang c[aầ]m|c[aầ]m tr[eê]n tay|[dđ][oọ]c gi[uú]p|[dđ][oọ]c (ch[uữ]|tem|nh[aã]n)|n[eé]t v[eẽ]|h[iì]nh v[eẽ]|t[oô]i v[eẽ]|h[aã]ng (g[iì]|n[aà]o)|m[aà]u g[iì]|n[uú]t (n[aà]y|b[aấ]m)|d[uù]ng (th[eế] n[aà]o|l[aà]m g[iì])|c[aá]ch d[uù]ng|ai (đ|d)[aâ]y|ai (đ|d)ang)/i;
// Cau ngan co tu hoi ma camera dang thay do vat / ban tay -> cung gui kem anh
const HOI_NGAN = /(g[iì]|n[aà]o|sao|bao nhi[eê]u|h[aã]ng|m[aà]u|lo[aạ]i)/i;
function nenGuiAnh(text) {
  if (!vision) return false;
  if (vision.hasInk() && HOI_NHIN.test(text)) return true;
  if (!vision.on) return false;
  if (HOI_NHIN.test(text)) return true;
  const coVat = vision.objects.some(o => o.name !== "person") || vision._gesture;
  return coVat && text.split(/\s+/).length <= 10 && HOI_NGAN.test(text);
}

async function ask(text, opts = {}) {
  text = String(text || "").trim();
  if (!text) return;
  voice.cancelSpeech();
  if (!opts.tuGiong) talk.bo(text);
  focusSid = HUD_SID;
  const kemAnh = opts.image || nenGuiAnh(text);
  if (kemAnh && !DEMO) {
    showYou(text); replyText = ""; showReply("", true); setState("thinking");
    flash();
    const blob = await vision.snapshot();
    feedAdd("run", "Mắt nhìn", vision.on ? "Chụp camera gửi MinMin" : "Gửi nét vẽ cho MinMin", "…");
    const ok = await bridge.sendWithImage(text, HUD_SID, blob, vision.describeScene());
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
  else if (e.key === "m" || e.key === "M") $("tBatChuoc").click();
  else if (e.key === "g" || e.key === "G") $("tGiong").click();
  else if (e.key === "k" || e.key === "K") $("tCuChi").click();
  else if (e.key === "p" || e.key === "P") $("tMay").click();
  else if (e.key === "t" || e.key === "T") $("micSw").click();
  else if (e.key === "Enter" && e.altKey) { document.documentElement.requestFullscreen?.(); }
});
$("ask").addEventListener("submit", (e) => { e.preventDefault(); const v = $("askInput").value; $("askInput").value = ""; $("ask").hidden = true; ask(v); });
$("scene").addEventListener("dblclick", () => document.documentElement.requestFullscreen?.());

// ---------- thanh cong cu, che do an, camera ----------
function doiHinh(f) {
  form = f || scene.toggleForm();
  if (f) scene.setForm(f);
  try { localStorage.setItem("minmin.hud.form4", form); } catch (e) {}
  $("formText").textContent = TEN_HINH[form] || form;
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

// ---------- huong dan + luyen cu chi ----------
const BUOC = [
  { g: "Calib", hoi: "Giơ tay PHẢI của bố lên (tay phải thật), đưa sang phía tay phải, giữ yên 1 giây", giu: 1 },
  { g: "Open_Palm", hoi: "Xòe bàn tay về phía camera", giu: 700 },
  { g: "Pointing_Up", hoi: "Duỗi riêng ngón trỏ", giu: 700 },
  { g: "Closed_Fist", hoi: "Nắm tay lại", giu: 700 },
  { g: "Pinch", hoi: "Chụm đầu ngón cái vào đầu ngón trỏ", giu: 700 },
  { g: "Victory", hoi: "Giơ chữ V", giu: 700 },
  { g: "Thumb_Up", hoi: "Giơ ngón cái", giu: 700 },
  { g: "TwoHands", hoi: "Giơ cả hai tay qua đầu", giu: 600 },
];
// Luyen dieu khien may tinh: chay "thu", KHONG gui lenh that sang may
const BUOC_MAY = [
  { g: "M_Move", hoi: "Duỗi ngón trỏ, di tay qua lại", giu: 900 },
  { g: "M_Click", hoi: "Chụm nhanh ngón cái vào ngón trỏ rồi thả (bấm chuột)", giu: 1 },
  { g: "M_ZoomIn", hoi: "Chụm giữ nửa giây rồi từ từ mở ra (phóng to)", giu: 1 },
  { g: "M_ZoomOut", hoi: "Mở chữ L (cái + trỏ) giữ một chút rồi chụm lại (thu nhỏ)", giu: 1 },
  { g: "M_Scroll", hoi: "Giơ chữ V rồi đưa lên / xuống (cuộn trang)", giu: 1 },
  { g: "M_Swipe", hoi: "Xòe tay, vuốt nhanh sang trái (trang tiếp)", giu: 1 },
  { g: "M_Pause", hoi: "Nắm tay giữ 1,5 giây (tạm dừng)", giu: 1500 },
];
let tabCuChi = "hud";
function chonTab(t) {
  tabCuChi = t;
  document.querySelectorAll(".g-tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === t ? "true" : "false"));
  document.querySelectorAll("#gList li").forEach(li => { li.hidden = li.dataset.tab !== t; });
  $("guideLead").textContent = t === "may"
    ? "Bật Máy tính để dùng tay điều khiển màn hình chính: lướt web, đọc Word, xem PDF không cần chuột."
    : "Giơ tay trước camera: cử chỉ nào MinMin nhận ra sẽ sáng lên.";
  if (guide.on) guide.dung(false);
}
document.querySelectorAll("#gList li").forEach(li => {
  const k = HINH[li.dataset.g];
  if (k) li.insertAdjacentHTML("afterbegin", hinhTay(k));
});
document.querySelectorAll(".g-tabs button").forEach(b => { b.onclick = () => chonTab(b.dataset.tab); });
const guide = {
  on: false, buoc: -1, t0: 0, lastG: "", lastAt: 0, ds: BUOC,
  thay(g) {
    this.lastG = g; this.lastAt = performance.now();
    const li = document.querySelector(`#gList li[data-g="${g}"]`);
    if (li) { li.classList.add("live"); clearTimeout(li._t); li._t = setTimeout(() => li.classList.remove("live"), 350); }
  },
  batDau() {
    if (!vision.on) { toast("Bật Camera trước rồi luyện cử chỉ.", true); return; }
    // luyen cu chi thi tam tat hanh dong that (khong doi hinh, khong goi MinMin, khong bam may)
    this.on = true; this.buoc = -1; vision.practice = true;
    this.ds = tabCuChi === "may" ? BUOC_MAY : BUOC;
    if (tabCuChi === "may") { this._cheDoCu = vision.mode; may.thu = true; may.dung = false; vision.setMode("maytinh"); }
    document.querySelectorAll("#gList li").forEach(li => li.classList.remove("done", "now"));
    $("gTrain").hidden = false; $("gStart").textContent = "Dừng luyện";
    this.tiep();
  },
  dung(xong) {
    this.on = false; vision.practice = false; vision.anyHand = false;
    if (this._cheDoCu) { vision.setMode(this._cheDoCu); this._cheDoCu = null; may.thu = false; may.dung = false; capNhatCheDo(); }
    $("gTrain").hidden = !xong; $("gStart").textContent = "Luyện lại";
    if (xong) { $("gStep").textContent = "HOÀN THÀNH"; $("gAsk").textContent = this.ds === BUOC_MAY ? "Bố đã nắm hết cử chỉ điều khiển máy. Bấm Bật điều khiển máy là dùng thật." : "Bố đã nắm hết cử chỉ. Đóng bảng này là dùng được ngay."; $("gBar").style.width = "100%"; }
    document.querySelectorAll("#gList li").forEach(li => li.classList.remove("now"));
  },
  tiep() {
    this.buoc++;
    const ds = this.ds;
    if (this.buoc >= ds.length) { this.dung(true); feedAdd("ok", "Luyện cử chỉ", `Hoàn thành ${ds.length} bước`, "XONG"); return; }
    const b = ds[this.buoc];
    vision.anyHand = b.g === "Calib";        // buoc chinh tay: tay nao cung nhan
    if (b.g === "Calib") { this._chinhXong = false; vision.chinhTay(); }
    $("gStep").textContent = `BƯỚC ${this.buoc + 1}/${ds.length}`;
    $("gAsk").textContent = b.hoi; $("gBar").style.width = "0%";
    document.querySelectorAll("#gList li").forEach(li => li.classList.toggle("now", li.dataset.g === b.g));
    this.giuTu = 0;
  },
  // goi moi khung hinh
  tick(now) {
    if (!this.on) return;
    const b = this.ds[this.buoc];
    let dung = false;
    if (b.g === "Calib") dung = !!this._chinhXong;    // vision.js bao qua onChinh
    else dung = this.lastG === b.g && now - this.lastAt < 250;
    if (!dung) { this.giuTu = 0; $("gBar").style.width = "0%"; return; }
    if (!this.giuTu) this.giuTu = now;
    const tl = Math.min(1, (now - this.giuTu) / b.giu);
    $("gBar").style.width = Math.round(tl * 100) + "%";
    if (tl >= 1) {
      const li = document.querySelector(`#gList li[data-g="${b.g}"]`); if (li) li.classList.add("done");
      chime();
      this.tiep();
    }
  },
};
function guideLoop(now) { guide.tick(now); requestAnimationFrame(guideLoop); }
requestAnimationFrame(guideLoop);

// ---------- dieu khien may tinh (MinMin Tay tren may bo) ----------
const tayMay = new TayMay();
const may = new DieuKhienMay({
  gui: (l) => { if (!may.thu) tayMay.gui(l); },
  bao: (g, chu) => {
    streamLog("g", "MÁY TÍNH", chu || CU_CHI_MAY[g] || g);
    if (g === "M_Pause" && chu) { toast(chu); capNhatCheDo(); }
  },
});

const vision = new Vision({
  video: $("camVideo"), overlay: $("camDots"), ink: $("ink"), scene, may,
  onGesture: (g) => { $("camGesture").textContent = g; if (g) streamLog("g", "CỬ CHỈ", g); },
  onControl: (t) => {
    $("rowCtl").hidden = !t; $("ctlText").textContent = t || "-";
    if (t) streamLog("a", "ĐIỀU KHIỂN", t);
  },
  onStatus: (m, bad) => toast(m, bad),
  onForm: (f) => { doiHinh(f); feedAdd("ok", "Cử chỉ", "Chữ V · đổi sang " + (TEN_HINH[f] || f).toLowerCase(), "XONG"); },
  onLook: () => { feedAdd("run", "Cử chỉ", "Ngón cái · MinMin nhìn", "…"); $("tNhin").click(); },
  onDetect: (g) => { guide.thay(g); dem.cuChi++; },
  // Chinh tay xong: tu nay "tay phai" la dung tay phai that cua bo
  onChinh: ({ doiHuong }) => {
    guide._chinhXong = true;
    $("gFlip").checked = vision.flip;
    chime();
    const chu = vision.handPref === "Any" ? "tay nào cũng điều khiển được" : `chỉ ${vision.handPref === "Left" ? "tay TRÁI" : "tay PHẢI"} điều khiển, tay kia bỏ qua`;
    toast(`Đã nhận tay phải của bố${doiHuong ? ", đã sửa luôn hướng di chuyển" : ""}. Từ giờ ${chu}.`);
    feedAdd("ok", "Chỉnh tay", "Đã nhận đúng tay phải", "XONG");
    streamLog("a", "CHỈNH TAY", "xong" + (doiHuong ? " · đảo hướng" : ""));
  },
  onBoQua: (nhan) => {
    const ben = nhan === "Left" ? "TRÁI" : "PHẢI", can = vision.handPref === "Left" ? "TRÁI" : "PHẢI";
    toast(`MinMin đang thấy tay ${ben}, chỉ nghe tay ${can}. Giơ tay ${can}, hoặc đổi ở bảng Cử chỉ → Tay điều khiển. Sai tay thì bấm Chỉnh tay.`);
  },
  // gio ca hai tay len = goi MinMin nghe
  onWake: () => {
    feedAdd("run", "Cử chỉ", "Giơ hai tay · MinMin nghe", "…");
    if (voiceOn) voice.wakeManually(); else { $("ask").hidden = false; $("askInput").focus(); }
  },
  onScene: (objs) => {
    const dem = {};
    objs.filter(o => o.name !== "person").forEach(o => { const t = tenDoVat(o.name); dem[t] = (dem[t] || 0) + 1; });
    const nguoi = objs.filter(o => o.name === "person").length;
    const ds = Object.entries(dem).map(([t, n]) => (n > 1 ? `${n} ${t}` : t));
    if (nguoi) ds.unshift(`${nguoi} người`);
    $("rowEnv").hidden = !vision.on;
    $("envText").textContent = ds.length ? ds.slice(0, 6).join(", ") : "—";
    if (ds.length) streamLog("", "MÔI TRƯỜNG", ds.slice(0, 6).join(", "));
  },
  onOwner: (who, ten) => {
    $("rowChu").hidden = !vision.on || !vision.owner();
    const el = $("chuText");
    el.className = who;
    el.textContent = who === "owner" ? `CHỦ NHÂN · ${String(ten || "BỐ").toUpperCase()}` : who === "stranger" ? "NGƯỜI LẠ" : "—";
    if (who === "owner" && !chaoRoi) {
      chaoRoi = true;
      feedAdd("ok", "Chủ nhân", `Nhận ra ${ten || "bố"}`, "XIN CHÀO");
      if (voiceOn) voice.say(`Chào ${ten || "bố"}, con đây ạ.`);
    }
    if (who === "stranger") feedAdd("bad", "Trước camera", "Có người lạ, không phải chủ nhân", "LƯU Ý");
  },
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
$("tFull").onclick = () => { if (document.fullscreenElement) document.exitFullscreen?.(); else document.documentElement.requestFullscreen?.().then(khoaDoc).catch(() => {}); };
// Ve thuc te: bat che do ve la tu mo camera, hien camera mo phia sau net ve (thay chinh minh
// dang ve tren khong). Duoi ngon tro = ha but, co ngon lai = nhac but. Tat thi het ve.
$("tVe").onclick = async () => {
  const bat = $("tVe").getAttribute("aria-pressed") !== "true";
  vision.drawMode = bat;
  batTat("tVe", "drawing", bat);
  if (!bat) { document.body.classList.remove("ar"); vision.cursor = null; vision.stroke = null; vision._inkDraw(); return; }
  if (!vision.on) await $("tCam").onclick();
  if (vision.on) {
    document.body.classList.add("ar");
    toast("Vẽ thực tế: duỗi ngón trỏ để vẽ, co ngón trỏ lại (hoặc nắm tay) để nhấc bút. Vẽ xong nói “Min Min ơi, đây là gì”. Bấm Vẽ lần nữa để thoát.");
  } else toast("Không có camera: vẽ bằng chuột. Bấm Vẽ lần nữa để thoát.");
};
$("tXoa").onclick = () => vision.clearInk();
$("tCuChi").onclick = () => {
  const mo = $("guide").hidden;
  $("guide").hidden = !mo;
  if (mo) $("may").hidden = true;
  batTat("tCuChi", null, mo);
  if (mo && !vision.on) $("guideLead").textContent = "Bật Camera để MinMin thấy tay bố. Cử chỉ nào nhận ra sẽ sáng lên.";
  if (!mo && guide.on) guide.dung(false);
};
$("guideX").onclick = () => $("tCuChi").click();
$("gStart").onclick = () => (guide.on ? guide.dung(false) : guide.batDau());
$("gFlip").checked = vision.flip;
$("gFlip").onchange = () => { vision.flip = $("gFlip").checked; try { localStorage.setItem("minmin.hud.flip", vision.flip ? "1" : "0"); } catch (e) {} };
$("tCam").onclick = async () => {
  if (vision.on) { vision.stop(); tatMay(); document.body.classList.remove("ar", "cam-on"); $("cam").hidden = true; $("tFlip").hidden = true; $("rowEnv").hidden = true; $("rowChu").hidden = true; batTat("tCam", null, false); return; }
  $("cam").hidden = false;
  const ok = await vision.start();
  if (!ok) { $("cam").hidden = true; return; }
  batTat("tCam", null, true);
  document.body.classList.add("cam-on");
  $("rowEnv").hidden = false;
  if (vision.owner()) { $("rowChu").hidden = false; vision.startOwnerWatch(); }
  // dien thoai / may co nhieu camera: cho doi camera truoc - sau
  // dien thoai luon co nut Doi cam (iOS co luc chi liet ke 1 camera truoc khi doi lan dau)
  try { const ds = await navigator.mediaDevices.enumerateDevices(); $("tFlip").hidden = !vision.nhe && ds.filter(d => d.kind === "videoinput").length < 2; } catch (e) { $("tFlip").hidden = !vision.nhe; }
  // chua chinh tay: nhac mot lan (khong chinh van dung duoc, tay nao cung dieu khien)
  if (!vision.daChinh && vision.ready) setTimeout(() => toast("Mẹo: mở bảng Cử chỉ, bấm Chỉnh tay để MinMin nhận đúng tay phải của bố."), 6000);
  if (vision.ready) toast(`Camera đã bật. Chỉ ${vision.handPref === "Left" ? "tay TRÁI" : "tay PHẢI"} điều khiển (đổi ở bảng Cử chỉ). Giơ đồ vật lên và hỏi “Min Min ơi, đây là gì”.`);
};
let chaoRoi = false;
$("tChuNhan").onclick = async () => {
  if (!vision.on) { toast("Bật Camera trước, ngồi đủ sáng và nhìn thẳng vào camera rồi bấm Chủ nhân.", true); return; }
  const cu = vision.owner();
  if (cu && !$("tChuNhan").dataset.xacNhan) {
    $("tChuNhan").dataset.xacNhan = "1";
    toast(`Đã có chủ nhân "${cu.ten}". Bấm Chủ nhân lần nữa trong 5 giây để đăng ký lại khuôn mặt.`);
    setTimeout(() => { delete $("tChuNhan").dataset.xacNhan; }, 5000);
    return;
  }
  delete $("tChuNhan").dataset.xacNhan;
  toast("Đang tải bộ nhận diện khuôn mặt… Bố nhìn thẳng camera, xoay đầu nhẹ sang hai bên.");
  try {
    const n = await vision.enrollOwner("Bố", (k, tong) => toast(`Đang ghi nhớ khuôn mặt bố: ${k}/${tong}`));
    chaoRoi = false;
    batTat("tChuNhan", null, true);
    toast(`Xong. MinMin đã ghi nhớ khuôn mặt bố (${n} mẫu). Dữ liệu chỉ nằm trong trình duyệt máy này.`);
    feedAdd("ok", "Chủ nhân", "Đã đăng ký khuôn mặt", "XONG");
  } catch (e) {
    const m = String(e && e.message || "");
    toast(/fetch|import|network|load/i.test(m) ? "Không tải được bộ nhận diện khuôn mặt (cần mạng tới cdn.jsdelivr.net). Kiểm tra mạng rồi thử lại."
      : (m || "Không đăng ký được. Kiểm tra mạng và ánh sáng rồi thử lại."), true);
  }
};
// ---------- che do dieu khien: Cu chi (mac dinh) / Bat chuoc / May tinh - chi mot nguon ----------
function capNhatCheDo() {
  batTat("tBatChuoc", null, vision.mode === "batchuoc");
  batTat("tMay", null, vision.mode === "maytinh");
  $("gMay").textContent = vision.mode === "maytinh" ? "Tắt điều khiển máy" : "Bật điều khiển máy";
}
$("tBatChuoc").onclick = async () => {
  const bat = vision.mode !== "batchuoc";
  if (bat && vision.mode === "maytinh") tatMay();
  vision.setMode(bat ? "batchuoc" : "cuchi");
  capNhatCheDo();
  if (bat && !vision.on) await $("tCam").onclick();
  toast(bat ? "Chế độ Bắt chước: robot làm theo cánh tay bố, cử chỉ tay tạm tắt." : "Về chế độ Cử chỉ: tay điều khiển MinMin, không có tay thì nhìn theo mặt.");
};
let _kiemMay = null;
function tatMay(baoLoi) {
  clearInterval(_kiemMay); _kiemMay = null;
  if (vision.mode === "maytinh") vision.setMode("cuchi");
  capNhatCheDo(); trangMay("");
  if (baoLoi) { toast(baoLoi, true); feedAdd("bad", "Máy tính", baoLoi, "TẮT"); }
}
// Dong MÁY TÍNH o goc phai: da noi / dang cho MinMin Tay
function trangMay(k) {
  $("rowMay").hidden = !k;
  const b = $("mayText"); b.className = k === "ok" ? "ok" : k ? "cho" : "";
  b.textContent = k === "ok" ? "ĐÃ NỐI" : k === "cho" ? "CHỜ MINMIN TAY…" : "-";
}
// Dang o che do May tinh ma MinMin Tay tat: KHONG tat che do, cu thu noi lai moi 3 giay.
// Bo bat lai cua so MinMin Tay la tu dieu khien duoc tiep (truoc 0.64.89 phai bam lai tu dau).
function kiemMayDinhKy() {
  clearInterval(_kiemMay);
  let mat = false;
  _kiemMay = setInterval(async () => {
    if (vision.mode !== "maytinh") { clearInterval(_kiemMay); _kiemMay = null; return; }
    const k = await tayMay.ping();
    if (k.ok && mat) {
      mat = false; trangMay("ok");
      toast("Đã nối lại MinMin Tay, điều khiển máy tiếp tục.");
      feedAdd("ok", "Máy tính", "Nối lại MinMin Tay", "NỐI LẠI");
    } else if (!k.ok && !mat) {
      mat = true; trangMay("cho");
      toast(k.ly_do === "sai_ma" ? "MinMin Tay báo sai mã (có thể đã tạo mã mới). Bấm Máy tính, dán mã mới." : "Mất kết nối MinMin Tay (cửa sổ đen đã tắt?). Bật lại MinMin-Tay.bat, HUD tự nối lại.", true);
      feedAdd("bad", "Máy tính", "Mất kết nối MinMin Tay, đang chờ", "CHỜ");
    }
  }, 3000);
}
const LY_DO_MAY = {
  khong_chay: "Chưa thấy MinMin Tay chạy trên máy này. Làm bước 1 (tải và bấm đúp MinMin-Tay.bat). Trình duyệt hỏi “cho phép truy cập thiết bị trong mạng” thì bấm Cho phép.",
  sai_ma: "Mã ghép nối chưa đúng. Chép lại mã trong cửa sổ đen MinMin Tay rồi dán vào đây.",
};
function moMay(lyDo) {
  $("may").hidden = false; $("guide").hidden = true; batTat("tCuChi", null, false);
  $("mayMa").value = tayMay.ma;
  const st = $("maySt"); st.className = "may-st" + (lyDo ? " bad" : ""); st.textContent = lyDo ? LY_DO_MAY[lyDo] || lyDo : "";
}
async function batMay() {
  const r = await tayMay.ping();
  if (!r.ok) { moMay(r.ly_do); return false; }
  if (!vision.on) await $("tCam").onclick();
  if (!vision.on) return false;
  if (guide.on) guide.dung(false);
  may.dung = false;
  vision.setMode("maytinh"); capNhatCheDo();
  feedAdd("ok", "Máy tính", "Đã nối MinMin Tay · " + (r.man || "màn chính"), "BẬT");
  streamLog("a", "MÁY TÍNH", "đã nối MinMin Tay · " + (r.man || ""));
  toast("Điều khiển máy: BẬT. Trỏ = di chuột · chụm nhanh = bấm · chụm giữ rồi mở = phóng to · chữ L chụm lại = thu nhỏ · chữ V lên xuống = cuộn · xòe vuốt = trang tiếp · nắm giữ = tạm dừng.");
  trangMay("ok");
  kiemMayDinhKy();
  if (!vision.daChinh) { vision.chinhTay(); toast("Lần đầu: giơ tay PHẢI của bố lên, đưa sang phía tay phải, giữ 1 giây để MinMin nhận đúng tay.", false); }
  return true;
}
$("tMay").onclick = async () => { if (vision.mode === "maytinh") { tatMay(); toast("Điều khiển máy: TẮT."); } else await batMay(); };
$("gMay").onclick = () => $("tMay").click();
$("mayX").onclick = () => { $("may").hidden = true; };
$("mayNoi").onclick = async () => {
  tayMay.datMa($("mayMa").value);
  const st = $("maySt"); st.className = "may-st"; st.textContent = "Đang kết nối…";
  if (await batMay()) { st.className = "may-st ok"; st.textContent = "Đã kết nối. Giơ tay trước camera để điều khiển màn hình chính."; setTimeout(() => { $("may").hidden = true; }, 1500); }
};
$("mayMa").addEventListener("keydown", (e) => { if (e.key === "Enter") $("mayNoi").click(); e.stopPropagation(); });
$("mayTai").onclick = () => {
  const url = URL.createObjectURL(new Blob([taoBat(location.origin)], { type: "application/octet-stream" }));
  const a = document.createElement("a"); a.href = url; a.download = "MinMin-Tay.bat";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
  $("maySt").className = "may-st"; $("maySt").textContent = "Đã tải. Mở thư mục Tải xuống, bấm đúp MinMin-Tay.bat, rồi dán mã vào ô trên.";
};
$("gHand").value = vision.handPref;
$("gHand").onchange = () => {
  vision.setHand($("gHand").value);
  const h = $("gHand").value;
  toast(h === "Any" ? "Tay nào cũng điều khiển được (hai tay cùng giơ thì theo tay giơ trước)."
    : `Chỉ ${h === "Left" ? "tay TRÁI" : "tay PHẢI"} điều khiển, tay kia MinMin bỏ qua.` + (vision.daChinh ? "" : " Bấm Chỉnh tay một lần để MinMin nhận đúng tay."));
};
$("gChinh").onclick = () => {
  if (!vision.on) { toast("Bật Camera trước rồi bấm Chỉnh tay.", true); return; }
  vision.chinhTay();
  toast("Giơ tay PHẢI của bố lên (một tay thôi), đưa sang phía tay phải, giữ yên 1 giây…");
};
// Thu di chuot: ve mot vong tron nho quanh giua man chinh - thay chuot chay la da noi dung
$("mayThu").onclick = async () => {
  const r = await tayMay.ping();
  const st = $("maySt");
  if (!r.ok) { st.className = "may-st bad"; st.textContent = LY_DO_MAY[r.ly_do] || "Chưa nối được MinMin Tay."; return; }
  st.className = "may-st ok"; st.textContent = "Nhìn màn hình chính: chuột đang chạy một vòng tròn.";
  for (let i = 0; i <= 36; i++) {
    const a = i / 36 * Math.PI * 2;
    tayMay.gui({ t: "move", x: +(0.5 + Math.cos(a) * 0.12).toFixed(4), y: +(0.5 + Math.sin(a) * 0.18).toFixed(4) });
    await new Promise(res => setTimeout(res, 35));
  }
};
tayMay.onGui = (l, ok) => { if (l.t !== "move" || !ok) streamLog(ok ? "g" : "a", "GỬI MÁY", `${l.t}${l.n != null ? " " + l.n : l.d != null ? " " + l.d : l.k ? " " + l.k : ""} ${ok ? "✓" : "lỗi"}`); };
$("tGiong").onclick = () => {
  voice.robotFx = $("tGiong").getAttribute("aria-pressed") !== "true";
  batTat("tGiong", null, voice.robotFx);
  try { localStorage.setItem("minmin.hud.robotfx", voice.robotFx ? "1" : "0"); } catch (e) {}
  toast(voice.robotFx ? "Giọng robot trầm khàn: BẬT" : "Giọng robot: TẮT (giọng gốc)");
};
batTat("tGiong", null, voice.robotFx);
if (vision.owner()) batTat("tChuNhan", null, true);
capNhatCheDo();

$("tFlip").onclick = async () => { const f = await vision.doiCam(); toast(f === "user" ? "Camera trước" : "Camera sau: đưa camera vào vật cần MinMin xem"); };
$("tNhin").onclick = () => {
  const cau = vision.on ? "Bố đang cho con xem qua camera. Con nhìn thấy gì? Nếu bố đang cầm hay giơ một đồ vật thì cho bố biết đó là gì, hãng gì, màu gì, các nút và công dụng. Đọc chữ nếu có."
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

// ---------- LUONG PHAN TICH (0.64.87): so do lien tuc + dong su kien chay ----------
const dem = { cuChi: 0 };
const SP = [
  ["fps", "KHUNG HÌNH", (v) => v.toFixed(0), 70],
  ["mic", "MIC", (v, x) => x, 1],
  ["loa", "GIỌNG RA", (v) => (v * 100).toFixed(0) + "%", 1],
  ["tay", "TỐC ĐỘ TAY", (v) => vision.on ? v.toFixed(2) + "/s" : "-", 2],
  ["tin", "TIN CẬY TAY", (v) => vision.on && vision.stats.tay ? (v * 100).toFixed(0) + "%" : "-", 1],
  ["tre", "TRỄ NHẬN DIỆN", (v) => vision.on ? v.toFixed(0) + " ms" : "-", 60],
];
const spHang = {};
for (const [k, nhan, , tran] of SP) {
  const sp = document.createElement("span"); sp.textContent = nhan;
  const b = document.createElement("b"); b.textContent = "-";
  const c = document.createElement("canvas"); c.width = 172; c.height = 32;
  $("spRows").append(sp, b, c);
  spHang[k] = { b, c, ds: new Array(60).fill(0), tran };
}
function veSong(h, mau) {
  const g = h.c.getContext("2d"), W = h.c.width, Hh = h.c.height;
  g.clearRect(0, 0, W, Hh);
  const tran = Math.max(h.tran, ...h.ds) || 1;
  g.beginPath();
  h.ds.forEach((v, i) => { const x = i / (h.ds.length - 1) * W, y = Hh - 2 - (v / tran) * (Hh - 4); i ? g.lineTo(x, y) : g.moveTo(x, y); });
  g.strokeStyle = mau; g.lineWidth = 2; g.stroke();
  g.lineTo(W, Hh); g.lineTo(0, Hh); g.closePath();
  g.fillStyle = mau.replace("1)", ".14)"); g.fill();
}
const MAU_SP = { fps: "rgba(143,107,255,1)", mic: "rgba(111,224,200,1)", loa: "rgba(255,154,60,1)", tay: "rgba(255,215,160,1)", tin: "rgba(111,224,200,1)", tre: "rgba(201,184,255,1)" };
let _lanLog = 0, _dongCuoi = "";
function streamLog(cls, nhan, text) {
  const dong = nhan + " " + text;
  if (dong === _dongCuoi) return;
  _dongCuoi = dong; _lanLog = performance.now();
  const ol = $("slog"); if (!ol) return;
  const li = document.createElement("li"); li.className = cls || "";
  const t = document.createElement("i");
  t.textContent = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  li.append(t, document.createTextNode(nhan + " · " + clip(String(text), 70)));
  ol.prepend(li);
  while (ol.children.length > 12) ol.lastChild.remove();
}
function doSong() {
  const micRms = voice.micLevel() / 4;
  const db = micRms > 0.0005 ? Math.round(20 * Math.log10(micRms)) : -99;
  const gt = {
    fps: scene.fps || 0,
    mic: voice.enabled ? voice.micLevel() : 0,
    loa: voice.speaking ? Math.min(1, voice.level()) : 0,
    tay: vision.on ? vision.stats.toc : 0,
    tin: vision.on ? vision.stats.conf : 0,
    tre: vision.on ? vision.stats.ms : 0,
  };
  for (const [k, , dang] of SP) {
    const h = spHang[k];
    h.ds.push(gt[k]); h.ds.shift();
    h.b.textContent = k === "mic" ? (voice.enabled ? db + " dB" : "tắt") : dang(gt[k]);
    veSong(h, MAU_SP[k]);
  }
  $("talkLv").style.width = Math.min(100, voice.micLevel() * 140).toFixed(0) + "%";
  talk.capNhat();
  // khong co su kien moi 2,5 giay thi ghi mot nhip do de luong luon chay
  if (performance.now() - _lanLog > 2500) {
    const phan = [`fps ${(scene.fps || 0).toFixed(0)}`, voice.enabled ? `mic ${db}dB` : "mic tắt"];
    if (vision.on) phan.push(`tay ${vision.stats.tay}`, `mặt ${vision.stats.mat}`, `vật ${vision.stats.vat}`, `${vision.stats.ms.toFixed(0)}ms`);
    phan.push(`việc ${running.size}`);
    _dongCuoi = ""; streamLog("", "NHỊP", phan.join(" · "));
  }
}
setInterval(doSong, 200);

// ---------- may yeu: giam chat luong ----------
let slow = 0;
function watchFps(f) {
  if (f < 26) slow++; else slow = 0;
  if (slow === 3 && !clTuChon) {        // may yeu va khach chua tu chon: ha mot bac, doi do tiep
    const c = $("tCL").dataset.cl || "high", n = { high: "mid", mid: "low" }[c];
    slow = 0;
    if (n) { datCL(n, false); feedAdd("ok", "Hình", "Máy hơi chậm, tự giảm sang " + CL_TEN[n].toLowerCase(), "XONG"); }
  }
}

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
  try { document.documentElement.requestFullscreen?.().then(khoaDoc).catch(() => {}); } catch (e) {}
}
// Dien thoai: giu man DOC khi toan man hinh (Android Chrome cho khoa; iOS bo qua im lang)
function khoaDoc() { if (vision.nhe && innerHeight >= innerWidth) screen.orientation?.lock?.("portrait").catch(() => {}); }
$("gateBtn").onclick = async () => {
  toanManHinh();
  $("gate").hidden = true;
  await batMic();          // van doc duoc tra loi ke ca khi khong nghe duoc (loi hien o bang Tro chuyen)
};
$("gateQuiet").onclick = () => { toanManHinh(); $("gate").hidden = true; voice._audio(); talk.capNhat(); };
// Che do kiosk: ?autostart=1 bo qua man bat dau (can co --autoplay-policy khi mo trinh duyet)
if (params.get("autostart") === "1") { $("gate").hidden = true; batMic(); }

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
