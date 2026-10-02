/* Composer-only dictation. No chat transport, tools or automatic submission. */
(function () {
  "use strict";
  function create({ input, button, status, beforeStart, language, onError }) {
    let active = false, writing = false, prefix = "", suffix = "", timer;
    const paint = () => {
      button.classList.toggle("recording", active);
      button.setAttribute("aria-pressed", String(active));
      button.title = window.t(active ? "dictation.stop" : "bar.mic");
      button.setAttribute("aria-label", button.title);
      status.textContent = window.t(active ? "dictation.listening" : "dictation.review");
      status.hidden = false;
    };
    const write = text => {
      if (!active || !text) return;
      writing = true;
      input.value = prefix + text + suffix;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      writing = false;
    };
    let generation = 0, capture = null;
    function makeCapture() {
      const token = ++generation;
      const deliver = text => { if (token === generation) write(text); };
      return new JavisVoice({ inputOnly: true, lang: "vi-VN",
      onInterim: deliver, onTranscript: deliver,
      onEnd: () => { if (active && token === generation) stop(); },
      onError: error => { if (token === generation) { stop(); onError(error); } }
      });
    }
    // Pauses keep the draft open. The browser never submits it to the assistant.
    function stop() {
      if (!active) return;
      active = false; clearTimeout(timer);
      generation++;
      capture.cancelListening(); paint();
    }
    function start() {
      if (active) { stop(); return; }
      capture = makeCapture();
      capture.managedEndpoint = true;
      if (!capture.isSupported()) { onError("not-supported"); return; }
      beforeStart();
      const value = input.value || "";
      const a = input.selectionStart == null ? value.length : input.selectionStart;
      const b = input.selectionEnd == null ? a : input.selectionEnd;
      prefix = value.slice(0, a); suffix = value.slice(b);
      if (prefix && !/\s$/.test(prefix)) prefix += " ";
      if (suffix && !/^\s/.test(suffix)) suffix = " " + suffix;
      capture.lang = language();
      if (capture.recognition) capture.recognition.lang = capture.lang;
      active = true; paint();
      timer = setTimeout(stop, 120000);
      capture.startListening();
    }
    button.addEventListener("click", start);
    // Editing, sending, switching sessions and leaving the page invalidate late recognition.
    input.addEventListener("input", () => { if (!writing) stop(); });
    window.addEventListener("pagehide", stop);
    document.addEventListener("visibilitychange", () => { if (document.hidden) stop(); });
    return { stop, active: () => active };
  }
  window.MinMinDictation = { create };
})();
