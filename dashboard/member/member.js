/* Khu vực thành viên: xem / sửa file trong brain được cấp. Mọi quyền do SERVER kiểm. */
(function () {
  "use strict";
  var $ = function (i) { return document.getElementById(i); };
  var T = function (k) { return typeof window.t === "function" ? window.t(k) : k; };
  var state = { brain: "", role: "view", dir: "", file: "" };
  var DUOI_ANH = /\.(png|jpe?g|gif|webp|svg|pdf)$/i;
  var DUOI_GHI = /\.(md|txt|csv|json|ya?ml|tsv)$/i;

  function applyI18n() {
    document.querySelectorAll("[data-i18n]").forEach(function (e) { e.textContent = T(e.getAttribute("data-i18n")); });
    document.querySelectorAll("[data-i18n-ph]").forEach(function (e) { e.placeholder = T(e.getAttribute("data-i18n-ph")); });
  }
  function jget(u) { return fetch(u).then(function (r) { return r.json().then(function (j) { j._st = r.status; return j; }); }); }
  function jpost(u, o) {
    var fd = new FormData(); Object.keys(o || {}).forEach(function (k) { fd.append(k, o[k]); });
    return fetch(u, { method: "POST", body: fd }).then(function (r) { return r.json().then(function (j) { j._st = r.status; return j; }); });
  }
  function q(o) { return Object.keys(o).map(function (k) { return k + "=" + encodeURIComponent(o[k]); }).join("&"); }
  function msg(t) { $("mpMsg").textContent = t || ""; }

  async function start() {
    applyI18n();
    var me = await jget("/m/me");
    if (me._st === 401 || !me.ok) { location.replace("/"); return; }
    $("mpWho").textContent = me.name || me.email;
    $("mpOut").onclick = async function () { await jpost("/m/logout"); location.replace("/"); };
    if (!me.full) return tfa();
    app();
  }

  async function tfa() {
    $("mpTfa").hidden = false; $("mpApp").hidden = true;
    var s = await jpost("/m/2fa/start");
    if (!s.ok) { $("mpTfaErr").textContent = s.error || T("memp.err"); return; }
    $("mpQr").innerHTML = s.qr_svg;     // SVG do server tự sinh từ mã, không có dữ liệu người dùng
    $("mpSecret").textContent = s.secret;
    $("mpGo").onclick = async function () {
      var r = await jpost("/m/2fa/enable", { code: $("mpCode").value });
      if (!r.ok) { $("mpTfaErr").textContent = r.error || T("memp.err"); return; }
      $("mpTfaErr").textContent = "";
      $("mpRecList").textContent = (r.recovery || []).join("\n");
      $("mpRec").hidden = false; $("mpGo").disabled = true;
      $("mpRecOk").onclick = function () { location.reload(); };
    };
  }

  async function app() {
    $("mpTfa").hidden = true; $("mpApp").hidden = false;
    var b = await jget("/m/brains");
    var sel = $("mpBrain"); sel.innerHTML = "";
    (b.brains || []).forEach(function (x) {
      var o = document.createElement("option"); o.value = x.name; o.textContent = x.name; o.setAttribute("data-role", x.role); sel.appendChild(o);
    });
    if (!(b.brains || []).length) { sel.hidden = true; $("mpHint").textContent = T("memp.no_grants"); return; }
    sel.onchange = function () { $("mpGBrain").value = sel.value; pickBrain(); graphLoad(); };
    pickBrain();
    graphInit(b.brains);
    $("mpUp").onclick = function () { state.dir = state.dir.split("/").slice(0, -1).join("/"); list(); };
    $("mpNew").onclick = newFile;
    $("mpSave").onclick = save;
    var tm; $("mpSearch").oninput = function () { clearTimeout(tm); tm = setTimeout(search, 300); };
  }

  function pickBrain() {
    var o = $("mpBrain").selectedOptions[0];
    state.brain = o.value; state.role = o.getAttribute("data-role"); state.dir = ""; state.file = "";
    $("mpRole").textContent = T(state.role === "edit" ? "memp.can_edit" : "memp.view_only");
    $("mpNew").hidden = state.role !== "edit";
    clearView(); list();
  }
  function clearView() {
    $("mpFile").textContent = ""; $("mpText").hidden = true; $("mpImg").hidden = true; $("mpSave").hidden = true;
    $("mpHint").hidden = false; $("mpHint").textContent = T("memp.pick"); msg("");
  }

  async function list() {
    $("mpPath").textContent = "/" + state.dir;
    var j = await jget("/m/files/list?" + q({ brain: state.brain, path: state.dir }));
    var ul = $("mpList"); ul.innerHTML = "";
    if (!j.ok) { msg(j.error || T("memp.err")); return; }
    j.items.forEach(function (it) {
      var li = document.createElement("li"); li.textContent = (it.dir ? "📁 " : "") + it.name;
      li.onclick = function () {
        var p = (state.dir ? state.dir + "/" : "") + it.name;
        if (it.dir) { state.dir = p; list(); } else openFile(p);
      };
      ul.appendChild(li);
    });
  }

  async function search() {
    var k = $("mpSearch").value.trim();
    if (k.length < 2) return list();
    var j = await jget("/m/search?" + q({ brain: state.brain, q: k }));
    var ul = $("mpList"); ul.innerHTML = "";
    (j.hits || []).forEach(function (h) {
      var li = document.createElement("li"); li.textContent = h.path + (h.line ? " : " + h.line : "");
      li.onclick = function () { openFile(h.path); }; ul.appendChild(li);
    });
  }

  async function openFile(p) {
    state.file = p; msg("");
    $("mpFile").textContent = p; $("mpHint").hidden = true;
    if (DUOI_ANH.test(p)) {
      $("mpText").hidden = true; $("mpSave").hidden = true; $("mpImg").hidden = false;
      $("mpImg").src = "/m/files/raw?" + q({ brain: state.brain, path: p }); return;
    }
    $("mpImg").hidden = true;
    var j = await jget("/m/files/read?" + q({ brain: state.brain, path: p }));
    if (!j.ok) { $("mpText").hidden = true; $("mpSave").hidden = true; $("mpHint").hidden = false; $("mpHint").textContent = T("memp.too_big"); return; }
    var ta = $("mpText"); ta.hidden = false; ta.value = j.text;
    var sua = state.role === "edit" && DUOI_GHI.test(p);
    ta.readOnly = !sua; $("mpSave").hidden = !sua;
  }

  async function save() {
    var r = await jpost("/m/files/write", { brain: state.brain, path: state.file, text: $("mpText").value });
    msg(r.ok ? T("memp.saved") : (r.error || T("memp.err")));
  }

  async function newFile() {
    var n = prompt(T("memp.new_ask")); if (!n) return;
    var p = (state.dir ? state.dir + "/" : "") + n.trim();
    var r = await jpost("/m/files/write", { brain: state.brain, path: p, text: "" });
    if (!r.ok) { msg(r.error || T("memp.err")); return; }
    await list(); openFile(p);
  }

  // ---- Đồ thị não: cùng bộ vẽ với MinMin, dữ liệu lấy từ /m/graph (chỉ brain được cấp) ----
  var G = null;
  function tab(g) {
    $("mpGraph").hidden = !g; $("mpApp").hidden = g;
    $("mpTabG").classList.toggle("on", g); $("mpTabF").classList.toggle("on", !g);
    if (g && G) { G.resize && G.resize(); G.refit && G.refit(0); }
  }
  function graphInit(brains) {
    $("mpTabs").hidden = false;
    var s = $("mpGBrain"); s.innerHTML = "";
    brains.forEach(function (x) { var o = document.createElement("option"); o.value = x.name; o.textContent = x.name; s.appendChild(o); });
    s.hidden = brains.length < 2;
    s.onchange = function () { $("mpBrain").value = s.value; pickBrain(); graphLoad(); };
    $("mpTabG").onclick = function () { tab(true); };
    $("mpTabF").onclick = function () { tab(false); };
    window.JAVIS_GRAPH_URL = function () { return "/m/graph?" + q({ brain: s.value }); };
    window.onGraphNodeClick = function (n) {
      if (!n || !n.path) return;
      tab(false);
      state.dir = n.path.split("/").slice(0, -1).join("/"); list(); openFile(n.path);
    };
    $("mpGHint").textContent = T("memp.graph_hint");
    tab(true); graphLoad();
  }
  async function graphLoad() {
    if (!window.JavisGraph) return;
    if (!G) G = new window.JavisGraph($("graph2d"));
    try { await G.load(); } catch (e) { $("mpGHint").textContent = String(e && e.message || e); }
  }

  function boot() { start(); }
  if (window.JavisI18n && window.JavisI18n.ready()) boot();
  else window.addEventListener("javis:i18n", boot, { once: true });
})();
