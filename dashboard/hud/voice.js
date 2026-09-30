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
    this.ttsVoice = opts.ttsVoice || "vi-VN-HoaiMyNeural";
    this.onWake = opts.onWake || (() => {});
    this.onCommand = opts.onCommand || (() => {});
    this.onInterim = opts.onInterim || (() => {});
    this.onStatus = opts.onStatus || (() => {});
    this.onSpeakStart = opts.onSpeakStart || (() => {});
    this.onSpeakEnd = opts.onSpeakEnd || (() => {});
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
    if (!this.supported) { this.onStatus("no-sr"); return false; }
    // mic rieng de do nang luong khi dang nghe (nhan dang giong cua trinh duyet khong cho do)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const src = this.ctx.createMediaStreamSource(stream);
      this.inAnalyser = this.ctx.createAnalyser(); this.inAnalyser.fftSize = 512;
      src.connect(this.inAnalyser);
    } catch (e) { this.onStatus("no-mic"); return false; }
    this.enabled = true;
    this._startRec();
    this.onStatus("listening-for-wake");
    return true;
  }

  stop() {
    this.enabled = false;
    try { this.rec && this.rec.abort(); } catch (e) {}
    this.onStatus("off");
  }

  _startRec() {
    if (!this.enabled || this.speaking) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = this.lang; rec.continuous = true; rec.interimResults = true; rec.maxAlternatives = 3;
    rec.onresult = (e) => this._onResult(e);
    rec.onerror = (e) => { if (e.error === "not-allowed") { this.enabled = false; this.onStatus("no-mic"); } };
    rec.onend = () => { if (this.rec === rec) setTimeout(() => this._startRec(), 250); };
    this.rec = rec;
    try { rec.start(); } catch (e) {}
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
      const r = e.results[i];
      // thu moi phuong an nghe, phuong an nao co tu goi thi lay
      let text = r[0].transcript, hit = null;
      for (let k = 0; k < r.length && !hit; k++) { const h = splitWake(r[k].transcript); if (h) { hit = h; text = r[k].transcript; } }
      if (!r.isFinal) {
        if (hit && !this.awake) { this._setAwake(true); this.onWake(hit.rest); }
        if (this.awake) this.onInterim(hit ? hit.rest : text);
        continue;
      }
      if (hit) {
        if (hit.rest && hit.rest.split(" ").length >= 2) { this._setAwake(false); this.onCommand(hit.rest); }
        else { this._setAwake(true); this.onWake(hit.rest); }
      } else if (this.awake && text.trim()) {
        this._setAwake(false);
        this.onCommand(text.trim());
      }
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
      const url = `${item.ttsUrl}?text=${encodeURIComponent(item.s)}&voice=${encodeURIComponent(this.ttsVoice)}`;
      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) throw new Error("tts " + res.status);
      const buf = await ctx.decodeAudioData(await res.arrayBuffer());
      const src = ctx.createBufferSource();
      src.buffer = buf; src.connect(this.outAnalyser);
      this._playing = src;
      src.onended = () => this._next();
      src.start();
    } catch (e) {
      // khong co may chu doc (vd ban xem truoc): dung giong cua trinh duyet
      await this._browserSay(item.s);
      this._next();
    }
  }

  _browserSay(s) {
    return new Promise(res => {
      if (!window.speechSynthesis) return res();
      const u = new SpeechSynthesisUtterance(s); u.lang = this.lang; u.rate = 1.05;
      const v = speechSynthesis.getVoices().find(v => v.lang && v.lang.startsWith("vi"));
      if (v) u.voice = v;
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
