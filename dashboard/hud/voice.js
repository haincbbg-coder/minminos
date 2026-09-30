// MinMin HUD - giong noi: nghe tu goi "Hey Min Min" / "Min Min" / "Min Min oi", doc cau tra loi,
// va do nang luong am thanh de canh 3D rung theo giong.

// Bo dau + ha chu de so tu goi ma khong phu thuoc cach may nghe ra ("Mìn Mìn", "Minh Minh"...).
export function fold(s) {
  return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d").replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
}

// Cac cach may nhan dang tieng Viet hay nghe nham "Min Min".
const WAKE = /(?:^| )(?:hey|hay|he|hi|ê|e|a|oi|ơi)? ?(?:min|minh|mính|mjn|ming|mim|mean|min's)[ -]?(?:min|minh|ming|mim|mean)(?: oi| ơi| a| ha)?(?= |$)/;

export function splitWake(text) {
  const f = fold(text);
  const m = WAKE.exec(f);
  if (!m) return null;
  // phan lenh nam sau tu goi; lay tu ban goc theo so tu de giu nguyen dau tieng Viet
  const wordsBefore = f.slice(0, m.index + m[0].length).trim().split(" ").filter(Boolean).length;
  const rest = String(text).trim().split(/\s+/).slice(wordsBefore).join(" ").trim();
  return { rest };
}

export class VoiceIO {
  constructor(opts = {}) {
    this.lang = opts.lang || "vi-VN";
    // Giong Edge: lay dung giong bo da chon o trang chinh (cung trang web nen chung localStorage).
    // Nha cung cap (Edge / OpenAI / ElevenLabs) thi may chu tu chon theo Cai dat -> Giong noi.
    let daChon = "", tocDo = "";
    try { daChon = localStorage.getItem("javis.voice") || ""; tocDo = localStorage.getItem("javis.rate") || ""; } catch (e) {}
    this.ttsVoice = opts.ttsVoice || (/^vi-/.test(daChon) ? daChon : "vi-VN-HoaiMyNeural");
    const r = parseFloat(tocDo);
    this.ttsRate = isFinite(r) && r > 0 ? `${r >= 1 ? "+" : ""}${Math.round((r - 1) * 100)}%` : "+5%";
    this.onSpeakError = opts.onSpeakError || (() => {});
    let fx = null; try { fx = localStorage.getItem("minmin.hud.robotfx"); } catch (e) {}
    this.robotFx = fx !== "0";          // mac dinh BAT: giong tram khan kieu robot
    this.onWake = opts.onWake || (() => {});
    this.onCommand = opts.onCommand || (() => {});
    this.onInterim = opts.onInterim || (() => {});
    this.onStatus = opts.onStatus || (() => {});
    this.onSpeakStart = opts.onSpeakStart || (() => {});
    this.onSpeakEnd = opts.onSpeakEnd || (() => {});
    this.onHeard = opts.onHeard || (() => {});     // moi cau may nghe duoc (ke ca khi chua goi)
    this.onEngine = opts.onEngine || (() => {});   // doi bo nhan giong: "sr" | "whisper"
    let ls = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
    // Noi lien: moi cau noi deu la lenh, khong can "Min Min oi" (bat tat o bang Tro chuyen)
    this.noiLien = ls("minmin.hud.noilien") === "1";
    // Bo nhan giong: auto = trinh duyet, loi thi tu chuyen Whisper; sr; whisper
    this.cheDoNghe = ["auto", "sr", "whisper"].includes(ls("minmin.hud.nghe")) ? ls("minmin.hud.nghe") : "auto";
    this.engine = "";
    this.loiSR = [];               // thoi diem cac lan nhan giong cua trinh duyet bao loi
    this.awake = false;            // da nghe tu goi, dang cho cau lenh
    this.speaking = false;
    this.enabled = false;
    this._awakeTimer = null;
    this.ctx = null; this.outAnalyser = null; this.inAnalyser = null;
    this._buf = new Uint8Array(256);
    this.queue = []; this._playing = null;
  }

  get supported() { return !!(window.SpeechRecognition || window.webkitSpeechRecognition); }

  _audio() {
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      this.ctx = new AC();
      this.outAnalyser = this.ctx.createAnalyser();
      this.outAnalyser.fftSize = 512;
      this.outAnalyser.connect(this.ctx.destination);
    }
    if (this.ctx.state === "suspended") this.ctx.resume().catch(() => {});
    return this.ctx;
  }

  async start() {
    this._audio();
    // mic rieng: do nang luong, va la nguon ghi am cho Whisper khi trinh duyet khong nghe duoc
    try {
      if (!this.micStream || !this.micStream.active) {
        this.micStream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
        const src = this.ctx.createMediaStreamSource(this.micStream);
        this.inAnalyser = this.ctx.createAnalyser(); this.inAnalyser.fftSize = 512;
        src.connect(this.inAnalyser);
      }
    } catch (e) { this.onStatus("no-mic"); return false; }
    this.enabled = true;
    const whisper = this.cheDoNghe === "whisper" || (!this.supported && this.cheDoNghe !== "sr");
    if (!whisper && !this.supported) { this.onStatus("no-sr"); this.enabled = false; return false; }
    this._dungEngine();
    if (whisper) this._startWhisper(); else { this._setEngine("sr"); this._startRec(); }
    this.onStatus("listening-for-wake");
    return true;
  }

  // Tat mic THAT SU (tra lai micro cho may, den mic tren trinh duyet tat)
  stop() {
    this.enabled = false;
    this._setAwake(false);
    this._dungEngine();
    try { this.micStream && this.micStream.getTracks().forEach(t => t.stop()); } catch (e) {}
    this.micStream = null; this.inAnalyser = null;
    this.onStatus("off");
  }

  setCheDoNghe(m) {
    this.cheDoNghe = ["auto", "sr", "whisper"].includes(m) ? m : "auto";
    try { localStorage.setItem("minmin.hud.nghe", this.cheDoNghe); } catch (e) {}
    if (this.enabled) { this.enabled = false; this._dungEngine(); this.start(); }
  }
  setNoiLien(v) {
    this.noiLien = !!v;
    try { localStorage.setItem("minmin.hud.noilien", v ? "1" : "0"); } catch (e) {}
  }

  _setEngine(e) { if (this.engine !== e) { this.engine = e; this.onEngine(e); } }
  _dungEngine() {
    const r = this.rec; this.rec = null;
    try { r && r.abort(); } catch (e) {}
    clearInterval(this._vad); this._vad = null;
    if (this._recW) this._dungGhi(true);
  }

  _startRec() {
    if (!this.enabled || this.speaking || this.engine !== "sr") return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = this.lang; rec.continuous = true; rec.interimResults = true; rec.maxAlternatives = 3;
    rec.onresult = (e) => this._onResult(e);
    rec.onerror = (e) => {
      if (e.error === "not-allowed") { this.enabled = false; this.onStatus("no-mic"); return; }
      if (e.error === "no-speech" || e.error === "aborted") return;
      // network / service-not-allowed / language-not-supported / audio-capture: trinh duyet
      // (Coc Coc, Brave, Chrome khong co dich vu nghe) khong nghe duoc. Bao ro, va o che do Tu
      // chon thi chuyen sang Whisper tren may chu MinMin.
      this.onStatus("sr-error", e.error);
      const now = performance.now();
      this.loiSR = this.loiSR.filter(t => now - t < 30000).concat(now);
      if (this.cheDoNghe === "auto" && (e.error !== "network" || this.loiSR.length >= 2)) {
        this.rec = null; try { rec.abort(); } catch (x) {}
        this._startWhisper();
      }
    };
    rec.onend = () => { if (this.rec === rec) setTimeout(() => this._startRec(), 250); };
    this.rec = rec;
    try { rec.start(); } catch (e) {}
  }

  // ---------- Whisper (0.64.87): tu ghi am khi co tieng noi, gui /stt cua may chu ----------
  // Dung khi trinh duyet khong co nhan giong (hoac bo chon). Can Groq API key o trang Models.
  _startWhisper() {
    if (typeof MediaRecorder === "undefined" || !this.micStream) { this.onStatus("sr-error", "no-recorder"); return; }
    this._setEngine("whisper");
    this._nen = 0.01;
    clearInterval(this._vad);
    this._vad = setInterval(() => this._vadTick(), 50);
  }

  _vadTick() {
    if (!this.enabled || !this.inAnalyser) return;
    if (this.speaking) { if (this._recW) this._dungGhi(true); return; }
    const lv = rms(this.inAnalyser, this._buf), now = performance.now();
    // nen on cua phong: tang cham, giam nhanh
    this._nen = lv < this._nen ? this._nen * 0.9 + lv * 0.1 : this._nen * 0.995 + lv * 0.005;
    const to = lv > Math.max(0.03, this._nen * 2.6);
    if (!this._recW) { if (to) this._batDauGhi(now); return; }
    if (to) this._lanCuoi = now;
    if (now - this._lanCuoi > 900 || now - this._wT0 > 12000) this._dungGhi(false);
  }

  _batDauGhi(now) {
    const loai = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"].find(t => MediaRecorder.isTypeSupported?.(t)) || "";
    let mr;
    try { mr = new MediaRecorder(this.micStream, loai ? { mimeType: loai } : undefined); } catch (e) { return; }
    const phan = [];
    mr.ondataavailable = (e) => { if (e.data && e.data.size) phan.push(e.data); };
    mr.onstop = () => { if (!mr._huy && now) this._guiWhisper(new Blob(phan, { type: mr.mimeType || "audio/webm" }), performance.now() - this._wT0); };
    this._recW = mr; this._wT0 = now; this._lanCuoi = now;
    mr.start();
    this.onStatus("whisper-rec");
  }

  _dungGhi(huy) {
    const mr = this._recW; this._recW = null;
    if (!mr) return;
    mr._huy = huy;
    try { mr.stop(); } catch (e) {}
    if (!huy) this.onStatus("whisper-stop");
  }

  async _guiWhisper(blob, dai) {
    if (dai < 450 || blob.size < 3000) { this.onStatus("whisper-idle"); return; }   // tieng dong ngan
    this.onStatus("whisper-send");
    try {
      const fd = new FormData();
      fd.append("file", blob, "hud." + (/mp4/.test(blob.type) ? "m4a" : /ogg/.test(blob.type) ? "ogg" : "webm"));
      fd.append("lang", "vi");
      const r = await fetch("/stt", { method: "POST", body: fd, credentials: "same-origin" });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) {
        this.onStatus("whisper-error", j.ly_do || ("HTTP " + r.status));
        return;
      }
      this.onStatus("whisper-idle");
      const text = String(j.text || "").trim();
      if (text) this._xuLy([text], true);
    } catch (e) { this.onStatus("whisper-error", "mang"); }
  }

  // Nhan cau lenh truc tiep (bam loi / phim cach) khong can tu goi.
  wakeManually() { this._setAwake(true); this.onWake(""); }

  _setAwake(v) {
    this.awake = v;
    clearTimeout(this._awakeTimer);
    if (v) this._awakeTimer = setTimeout(() => { this.awake = false; this.onStatus("wake-timeout"); }, 9000);
  }

  _onResult(e) {
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i], alts = [];
      for (let k = 0; k < r.length; k++) alts.push(r[k].transcript);
      this._xuLy(alts, r.isFinal);
    }
  }

  // Mot cau nghe duoc (tu trinh duyet hoac Whisper): tim tu goi, hoac la lenh khi dang thuc /
  // dang o che do Noi lien. `alts`: cac phuong an nghe, phuong an nao co tu goi thi lay.
  _xuLy(alts, final) {
    let text = alts[0] || "", hit = null;
    for (const a of alts) { const h = splitWake(a); if (h) { hit = h; text = a; break; } }
    this.onHeard(text, final, !!hit);
    if (!final) {
      if (hit && !this.awake) { this._setAwake(true); this.onWake(hit.rest); }
      if (this.awake || this.noiLien) this.onInterim(hit ? hit.rest : text);
      return;
    }
    if (hit) {
      if (hit.rest && hit.rest.split(" ").length >= 2) { this._setAwake(false); this.onCommand(hit.rest); }
      else { this._setAwake(true); this.onWake(hit.rest); }
    } else if ((this.awake || this.noiLien) && text.trim() && text.trim().split(/\s+/).length >= 2) {
      this._setAwake(false);
      this.onCommand(text.trim());
    }
  }

  // ---------- Doc ----------
  // Doc tung cau de cau dau phat ra nhanh; chu dai qua thi cat.
  say(text, { ttsUrl = "/tts" } = {}) {
    const clean = speakable(text);
    if (!clean) return;
    splitSentences(clean).forEach(s => this.queue.push({ s, ttsUrl }));
    if (!this._playing) this._next();
  }

  cancelSpeech() {
    this.queue = [];
    try { this._playing && this._playing.stop(); } catch (e) {}
  }

  async _next() {
    const item = this.queue.shift();
    if (!item) { this._playing = null; this._endSpeak(); return; }
    this._beginSpeak();
    try {
      const ctx = this._audio();
      const url = `${item.ttsUrl}?text=${encodeURIComponent(item.s)}&voice=${encodeURIComponent(this.ttsVoice)}&rate=${encodeURIComponent(this.ttsRate)}`;
      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) {
        let why = "";
        try { const j = await res.json(); why = j.detail || ""; } catch (e) {}
        const err = new Error(why || ("Máy chủ đọc giọng báo lỗi " + res.status));
        err.fromServer = true;
        throw err;
      }
      const buf = await ctx.decodeAudioData(await res.arrayBuffer());
      const src = ctx.createBufferSource();
      src.buffer = buf;
      if (this.robotFx) { src.playbackRate.value = 0.9; src.connect(this._fxChain()); }
      else src.connect(this.outAnalyser);
      this._playing = src;
      src.onended = () => this._next();
      src.start();
    } catch (e) {
      // May chu doc loi: bao ro cho bo, KHONG tu doi sang giong trinh duyet. Giong trinh duyet
      // tren Coc Coc/Chrome thuong khong co tieng Viet nen doc thanh giong tay (bo bao 30/09).
      // Chi dung no khi may chu khong co (ban xem truoc) VA trinh duyet co giong tieng Viet.
      if (e && e.fromServer) {
        this.queue = [];
        this.onSpeakError(e.message);
        this._next();
        return;
      }
      if (this._coGiongViet()) await this._browserSay(item.s);
      else if (!this._baoThieuGiong) { this._baoThieuGiong = true; this.onSpeakError("Trình duyệt không có giọng tiếng Việt để đọc thử."); }
      this._next();
    }
  }

  // Hieu ung "giong robot tram khan" (0.64.85): ha giong ~2 cung (phat cham 10%), mot chut
  // meo tieng (waveshaper) cho do khan, day tram, cat bot tieng xi, them tieng vang kim loai
  // rat ngan. Ap len moi nha cung cap giong (Edge, OpenAI, ElevenLabs).
  _fxChain() {
    if (this._fx) return this._fx;
    const c = this.ctx;
    const khan = c.createWaveShaper();
    const n = 1024, cur = new Float32Array(n), k = 6;
    for (let i = 0; i < n; i++) { const x = i * 2 / n - 1; cur[i] = (1 + k) * x / (1 + k * Math.abs(x)); }
    khan.curve = cur; khan.oversample = "4x";
    const tram = c.createBiquadFilter(); tram.type = "lowshelf"; tram.frequency.value = 220; tram.gain.value = 5;
    const giua = c.createBiquadFilter(); giua.type = "peaking"; giua.frequency.value = 1400; giua.Q.value = 0.9; giua.gain.value = 3;
    const xi = c.createBiquadFilter(); xi.type = "highshelf"; xi.frequency.value = 6500; xi.gain.value = -8;
    const vang = c.createDelay(0.05); vang.delayTime.value = 0.018;
    const vangG = c.createGain(); vangG.gain.value = 0.22;
    const nho = c.createGain(); nho.gain.value = 0.8;
    khan.connect(tram); tram.connect(giua); giua.connect(xi);
    xi.connect(nho); nho.connect(this.outAnalyser);
    xi.connect(vang); vang.connect(vangG); vangG.connect(this.outAnalyser);
    this._fx = khan;
    return khan;
  }

  _coGiongViet() {
    try { return !!(window.speechSynthesis && speechSynthesis.getVoices().some(v => /^vi/i.test(v.lang || ""))); } catch (e) { return false; }
  }

  _browserSay(s) {
    return new Promise(res => {
      if (!window.speechSynthesis) return res();
      const u = new SpeechSynthesisUtterance(s); u.lang = this.lang; u.rate = 1.05;
      const v = speechSynthesis.getVoices().find(v => v.lang && /^vi/i.test(v.lang));
      if (!v) return res();
      u.voice = v;
      this._fakeTalk = true;
      u.onend = u.onerror = () => { this._fakeTalk = false; res(); };
      speechSynthesis.speak(u);
      setTimeout(() => { this._fakeTalk = false; res(); }, 20000);
    });
  }

  _beginSpeak() {
    if (this.speaking) return;
    this.speaking = true;
    try { this.rec && this.rec.abort(); } catch (e) {}   // khong tu nghe chinh minh
    this.rec = null;
    this.onSpeakStart();
  }
  _endSpeak() {
    if (!this.speaking) return;
    this.speaking = false;
    this.onSpeakEnd();
    setTimeout(() => this._startRec(), 400);
  }

  // Nang luong 0..1 cho canh 3D
  level() {
    if (this.speaking) {
      if (this._fakeTalk) return 0.35 + Math.abs(Math.sin(performance.now() / 90)) * 0.4;
      return rms(this.outAnalyser, this._buf) * 3.2;
    }
    if (this.awake && this.inAnalyser) return rms(this.inAnalyser, this._buf) * 4;
    return 0;
  }
  // Muc am micro 0..1 luc nao cung do (cho bang Tro chuyen va Luong phan tich)
  micLevel() { return this.inAnalyser ? Math.min(1, rms(this.inAnalyser, this._buf) * 4) : 0; }
}

function rms(an, buf) {
  if (!an) return 0;
  an.getByteTimeDomainData(buf);
  let s = 0;
  for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; s += v * v; }
  return Math.min(1, Math.sqrt(s / buf.length));
}

// Bo markdown, bang, link, khoi code - chi giu cau noi duoc.
export function speakable(md) {
  let s = String(md || "");
  s = s.replace(/<!--[\s\S]*?-->/g, " ").replace(/```[\s\S]*?```/g, " ");
  s = s.split("\n").filter(l => !/^\s*\|/.test(l)).join("\n");
  s = s.replace(/!\[[^\]]*\]\([^)]*\)/g, " ").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  s = s.replace(/[*_#>`~]+/g, " ").replace(/^\s*[-•]\s+/gm, "").replace(/https?:\/\/\S+/g, " ");
  s = s.replace(/\s+/g, " ").trim();
  if (s.length > 700) { const cut = s.slice(0, 700); s = cut.slice(0, Math.max(cut.lastIndexOf(". "), 400)) + "."; }
  return s;
}

function splitSentences(s) {
  const out = []; let cur = "";
  for (const part of s.split(/(?<=[.!?…])\s+/)) {
    if ((cur + " " + part).length > 220 && cur) { out.push(cur); cur = part; } else cur = cur ? cur + " " + part : part;
  }
  if (cur) out.push(cur);
  return out;
}
