/* Dictation owns a separate recognizer; never submits a chat turn. */
(function () {
  "use strict";
  function create({ input, button, status, beforeStart, language, onError }) {
    let active = false, writing = false, finishing = false, received = false;
    let recognition = null, epoch = 0, prefix = "", suffix = "", committed = "", heard = "";
    let timer, finalTimer, startTimer, fixTimer;
    // Web Speech không nhận từ điển riêng nên "Javis" về thành "Da Vít". Chữ thô được hỏi server
    // (/voice/sua: từ vựng cá nhân + tên rút từ bộ nhớ/wiki), kết quả nhớ theo chữ thô để lần vẽ
    // sau dùng ngay. Server lỗi hay chậm thì cứ giữ chữ thô, không bao giờ chặn việc gõ.
    const fixCache = new Map();
    const shown = raw => fixCache.get(raw) || raw;
    function write() {
      writing = true;
      input.value = prefix + shown(heard) + suffix;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      writing = false;
    }
    async function askFix(raw, immediate) {
      if (!raw || fixCache.has(raw) || typeof fetch !== "function") return;
      try {
        const fd = new FormData(); fd.append("text", raw);
        const r = await (await fetch("/voice/sua", { method: "POST", body: fd })).json();
        if (!r || typeof r.text !== "string") return;
        fixCache.set(raw, r.text);
        if (fixCache.size > 50) fixCache.delete(fixCache.keys().next().value);
        if (r.text !== raw) {
          if (active && heard === raw) write();
          else if (!active && input.value === prefix + raw + suffix) { writing = true; input.value = prefix + r.text + suffix; input.dispatchEvent(new Event("input", { bubbles: true })); writing = false; }
        }
      } catch (_) {}
    }
    function scheduleFix(raw, final) {
      clearTimeout(fixTimer);
      if (final) { askFix(raw); return; }
      fixTimer = setTimeout(() => askFix(raw), 350);
    }
    const show = key => { status.hidden = false; status.textContent = window.t(key); };
    function paint() {
      button.classList.toggle("recording", active);
      button.setAttribute("aria-pressed", String(active));
      button.title = window.t(active ? "dictation.stop" : "bar.mic");
      button.setAttribute("aria-label", button.title);
    }
    function stop() {
      const wasActive = active;
      if (!active && !recognition) return;
      active = false; finishing = false; epoch++;
      clearTimeout(timer); clearTimeout(finalTimer); clearTimeout(startTimer);
      const old = recognition; recognition = null;
      if (old) { old.onend = old.onresult = old.onerror = old.onstart = null; try { old.abort(); } catch (_) {} }
      paint();
      if (wasActive) show(received ? "dictation.review" : "dictation.empty");
      if (wasActive && heard) askFix(heard);
    }
    function finish() {
      if (!active || finishing) return;
      finishing = true;
      // Some browsers only deliver the final text after stop(), not before it.
      if (!recognition) { stop(); return; }
      try { recognition.stop(); } catch (_) { stop(); return; }
      finalTimer = setTimeout(stop, 1500);
    }
    async function start() {
      if (active) { finish(); return; }
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { show("dictation.unsupported"); onError("not-supported"); return; }
      let released;
      try { released = beforeStart(); } catch (_) {}
      const ticket = ++epoch;
      received = false; active = true; finishing = false; paint(); show("dictation.starting");
      try { await released; } catch (_) {}
      if (epoch !== ticket || !active) return;
      const value = input.value || "", a = input.selectionStart ?? value.length, b = input.selectionEnd ?? a;
      prefix = value.slice(0, a); suffix = value.slice(b);
      if (prefix && !/\s$/.test(prefix)) prefix += " ";
      if (suffix && !/^\s/.test(suffix)) suffix = " " + suffix;
      committed = heard = "";
      const r = recognition = new SR();
      r.lang = language() || "vi-VN"; r.continuous = !(typeof navigator !== "undefined" && /iPhone|iPad|iPod/i.test(navigator.userAgent)); r.interimResults = true; r.maxAlternatives = 1;
      r.onstart = () => { if (ticket !== epoch) return; clearTimeout(startTimer); show("dictation.listening"); };
      r.onresult = ev => {
        if (!active || ticket !== epoch) return;
        let text = "";
        for (let i = 0; i < ev.results.length; i++) {
          const part = String((ev.results[i][0] || {}).transcript || "").trim();
          text = window.JavisVoice.ghepManh(text, part);
        }
        heard = window.JavisVoice.ghepManh(committed, text).trim();
        if (!heard) return;
        received = true;
        write();
        const last = ev.results[ev.results.length - 1];
        scheduleFix(heard, !!(last && last.isFinal));
      };
      r.onerror = ev => {
        if (ticket !== epoch || ev.error === "no-speech") return;
        const error = ev.error;
        stop(); show(error === "network" ? "dictation.network" : "dictation.failed");
        onError(error);
      };
      r.onend = () => {
        if (ticket !== epoch || !active) return;
        if (finishing) { stop(); return; }
        committed = heard;
        try { r.start(); } catch (_) { stop(); show("dictation.failed"); }
      };
      timer = setTimeout(finish, 120000);
      startTimer = setTimeout(() => { if (!received) { stop(); show("dictation.failed"); } }, 10000);
      try { r.start(); } catch (_) { stop(); show("dictation.failed"); }
    }
    button.addEventListener("click", start);
    input.addEventListener("input", () => { if (!writing) stop(); });
    window.addEventListener("pagehide", stop);
    document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
    return { stop, active: () => active };
  }
  window.MinMinDictation = { create };
})();
