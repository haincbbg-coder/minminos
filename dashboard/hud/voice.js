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
