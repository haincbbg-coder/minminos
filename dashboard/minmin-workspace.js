/* Min Min conversation workspace. No timers invent work completion. */
(function (root) {
  "use strict";
  const states = new Map();
  const clean = s => String(s || "").replace(/```[\s\S]*?```/g, " ").replace(/!\[[^\]]*\]\([^)]*\)/g, "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[#*_>`]/g, "").replace(/\s+/g, " ").trim();
  function outline(messages) {
    const requests = (messages || []).filter(m => m.role === "user").slice(-4).map(m => clean(m.text || m.content).slice(0, 220)).filter(Boolean);
    const answers = (messages || []).filter(m => m.role === "assistant" || m.role === "javis");
    const last = answers.length ? clean(answers[answers.length - 1].text || answers[answers.length - 1].content) : "";
    return { requests, last: last.slice(0, 650) };
  }
  function advance(old, ev) {
    let s = { ...(old || { pct: 0, steps: 0, phase: "idle", text: "" }) };
    if (ev.type === "start" || (ev.type === "status" && ["idle", "done", "error", "cancelled"].includes(s.phase))) s = { pct: 8, steps: 0, phase: "working", text: "" };
    if (ev.type === "status") { s.pct = Math.max(s.pct, 18); s.text = clean(ev.content); }
    if (ev.type === "tool_call" || ev.type === "progress") { s.pct = Math.max(s.pct, Math.min(76, 30 + s.steps * 5)); s.phase = "working"; s.text = clean(ev.content || ev.tool); }
    if (ev.type === "tool_result") { s.steps++; s.pct = Math.max(s.pct, Math.min(82, 40 + s.steps * 5)); }
    if (ev.type === "stream" || ev.type === "response") { s.pct = Math.max(s.pct, 90); s.phase = "writing"; }
    if (ev.type === "error" || ev.type === "cancelled") s.phase = ev.type;
    if (ev.type === "turn_done" && !["error", "cancelled"].includes(s.phase)) { s.pct = 100; s.phase = "done"; }
    return s;
  }
  function safeLink(value) { try { const u = new URL(value); return /^(https?:)$/.test(u.protocol) ? u.href : ""; } catch (_) { return ""; } }
  const api = { outline, advance, safeLink };
  if (typeof module === "object" && module.exports) { module.exports = api; return; }
  const t = k => root.t("mmw." + k), esc = s => String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const current = () => root.JavisSessions ? root.JavisSessions.current() || "draft" : "draft";
  const brain = () => root.JavisSessions ? root.JavisSessions.brain() : "";
  const key = sid => brain() + "|" + (sid || "draft");
  let mounted = null, generation = 0, timer;
  function paintProgress() {
    const el = document.getElementById("minminProgress"); if (!el) return;
    const s = states.get(key(current())); el.hidden = !s; if (!s) return;
    el.dataset.phase = s.phase;
    if (!el.firstElementChild) el.innerHTML = '<div class="mm-progress-head"><span class="mm-motion-mark" aria-hidden="true"></span><div><b></b><small></small></div><strong></strong></div><div class="mm-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100"><span></span></div><div class="mm-progress-foot"><span></span><span></span></div>';
    el.querySelector("b").textContent = t(s.phase === "error" ? "work_error" : s.phase);
    el.querySelector(".mm-progress-head div small").textContent = s.phase === "working" ? (s.text || t("receiving")) : t(s.phase + "_hint");
    el.querySelector("strong").textContent = s.pct + "%";
    const track = el.querySelector(".mm-progress-track");
    track.setAttribute("aria-label", t("estimate")); track.setAttribute("aria-valuenow", s.pct);
    track.firstElementChild.style.width = s.pct + "%";
    el.querySelector(".mm-progress-foot span").textContent = t("estimate");
    el.querySelector(".mm-progress-foot span:last-child").textContent = t("steps") + ": " + s.steps;
  }
  api.event = function (sid, ev) {
    if (!["start","status","tool_call","tool_result","progress","stream","response","error","cancelled","turn_done"].includes(ev.type)) return;
    const k = key(sid); states.set(k, advance(states.get(k), ev));
    if (states.size > 100) states.delete(states.keys().next().value);
    paintProgress();
  };
  api.sync = paintProgress;
  api.mount = function (host, page, toggle) {
    if (!host) return;
    ++generation; mounted = { host, page, toggle, tab: "overview", data: { files: [], links: [] }, search: "" };
    host.innerHTML = '<header class="mm-library-head"><div><small>MIN MIN / ' + esc(t("session")) + '</small><h2>' + esc(t("library")) + '</h2></div><button type="button" class="mm-library-close" aria-label="' + esc(t("close")) + '">' + root.ic("x") + '</button></header><div class="mm-library-tabs" role="tablist"></div><div class="mm-library-search"><input type="search" aria-label="' + esc(t("search")) + '" placeholder="' + esc(t("search")) + '"></div><div class="mm-library-content"></div>';
    const setOpen = open => { page.classList.toggle("library-closed", !open); page.classList.toggle("library-open", open); toggle.setAttribute("aria-expanded", String(open)); };
    setOpen(root.matchMedia("(min-width: 1280px)").matches);
    toggle.onclick = () => setOpen(page.classList.contains("library-closed"));
    host.querySelector(".mm-library-close").onclick = () => { setOpen(false); toggle.focus(); };
    host.onkeydown = e => { if (e.key === "Escape") { setOpen(false); toggle.focus(); } };
    host.querySelector("input").oninput = e => { if (mounted?.host === host) { mounted.search = e.target.value; render(); } };
    refresh();
    return () => { if (mounted?.host === host) { mounted = null; generation++; } };
  };
  function render() {
    const m = mounted; if (!m || !m.host.isConnected) return;
    const media = f => f.image || /\.(png|jpe?g|gif|webp|avif|mp4|webm|mov)$/i.test(f.name || f.path);
    const tabs = [["overview", null], ["media", m.data.files.filter(media).length], ["files", m.data.files.filter(f => !media(f)).length], ["links", m.data.links.length]];
    m.host.querySelector(".mm-library-tabs").innerHTML = tabs.map(([name,n]) => '<button type="button" role="tab" aria-selected="' + (m.tab === name) + '" data-tab="' + name + '">' + esc(t(name)) + (n == null ? "" : '<small>' + n + '</small>') + '</button>').join("");
    m.host.querySelectorAll("[data-tab]").forEach((b, index) => {
      b.tabIndex = m.tab === b.dataset.tab ? 0 : -1;
      b.onclick = () => { m.tab = b.dataset.tab; render(); m.host.querySelector('[data-tab="' + m.tab + '"]').focus(); };
      b.onkeydown = e => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(e.key)) return;
        e.preventDefault();
        const next = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (index + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
        m.tab = tabs[next][0]; render(); m.host.querySelector('[data-tab="' + m.tab + '"]').focus();
      };
    });
    const content = m.host.querySelector(".mm-library-content");
    m.host.querySelector(".mm-library-search").hidden = m.tab === "overview";
    if (m.tab === "overview") {
      const info = outline(root.JavisSessions?.messages?.() || []);
      content.innerHTML = '<section class="mm-summary"><span class="mm-section-label">' + esc(t("requests")) + '</span>' + (info.requests.length ? '<ul>' + info.requests.map(x => '<li>' + esc(x) + '</li>').join("") + '</ul>' : '<p class="mm-empty">' + esc(t("empty_summary")) + '</p>') + '</section><section class="mm-summary"><span class="mm-section-label">' + esc(t("latest")) + '</span><p>' + esc(info.last || t("no_answer")) + '</p><small>' + esc(t("summary_hint")) + '</small></section>';
      return;
    }
    if (m.loading) { content.textContent = t("loading"); return; }
    if (m.error) { content.innerHTML = '<p class="mm-empty">' + esc(t("error")) + '</p><button class="mm-retry" type="button">' + esc(t("retry")) + '</button>'; content.querySelector("button").onclick = refresh; return; }
    const q = m.search.toLocaleLowerCase();
    const items = (m.tab === "links" ? m.data.links : m.data.files.filter(f => m.tab === "media" ? media(f) : !media(f))).filter(f => [f.label, f.name, f.path, f.url].filter(Boolean).join(" ").toLocaleLowerCase().includes(q));
    content.innerHTML = items.length ? '<div class="mm-assets ' + (m.tab === "media" ? "mm-media-grid" : "") + '"></div>' : '<p class="mm-empty">' + esc(q ? t("no_matches") : t("empty_assets")) + '</p>';
    const list = content.querySelector(".mm-assets");
    items.forEach(f => {
      const url = m.tab === "links" ? safeLink(f.url) : '/files/raw?brain=' + encodeURIComponent(brain()) + '&path=' + encodeURIComponent(f.path || "");
      if (!url) return;
      const name = f.label || f.name || f.url, available = f.exists !== false;
      const date = f.ts ? new Date(f.ts < 1e12 ? f.ts * 1000 : f.ts).toLocaleDateString(root.JavisI18n?.locale?.() || "vi-VN") : "";
      const row = document.createElement("article"); row.className = "mm-asset";
      const image = m.tab === "media" && !/\.(mp4|webm|mov)$/i.test(f.name || f.path);
      row.innerHTML = (image && available ? '<img loading="lazy" alt="' + esc(name) + '" src="' + esc(url) + '">' : '<div class="mm-file-symbol">' + root.ic(m.tab === "links" ? "link" : "file-text") + '</div>') + '<div class="mm-asset-info"><b>' + esc(name) + '</b><small>' + esc(available ? [date, f.size ? Math.ceil(f.size/1024) + ' KB' : ""].filter(Boolean).join(" · ") : t("missing")) + '</small></div><div class="mm-asset-actions">' + (available ? '<a target="_blank" rel="noopener noreferrer" href="' + esc(url) + '">' + esc(t("open")) + '</a>' + (m.tab !== "links" ? '<a href="' + esc(url + '&dl=1') + '" download>' + esc(t("download")) + '</a>' : "") : "") + '</div>';
      list.appendChild(row);
    });
  }
  async function refresh() {
    paintProgress(); const m = mounted; if (!m) return;
    const ticket = ++generation, sid = current(), b = brain(); m.data = { files: [], links: [] }; m.error = false; m.loading = sid !== "draft"; render();
    if (sid === "draft") return;
    try {
      const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/assets?brain=' + encodeURIComponent(b));
      const data = await r.json();
      if (mounted !== m || ticket !== generation || sid !== current() || b !== brain()) return;
      if (!r.ok || !data.ok) throw new Error("assets");
      m.data = { files: data.files || [], links: data.links || [] };
    } catch (_) { if (mounted === m && ticket === generation) m.error = true; }
    if (mounted === m && ticket === generation) { m.loading = false; render(); }
  }
  root.addEventListener("javis:sessions-changed", () => { paintProgress(); clearTimeout(timer); timer = setTimeout(refresh, 180); });
  root.addEventListener("javis:i18n", () => { paintProgress(); render(); });
  root.MinMinWorkspace = api;
})(typeof window !== "undefined" ? window : globalThis);
