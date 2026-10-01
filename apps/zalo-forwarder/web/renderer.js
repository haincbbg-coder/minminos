"use strict";
/* global window, document */
const bridge = window.api;

const APP = { name: "Zalo Forwarder", version: "2.10.0", author: "Trung Kiên Hà", year: 2026 };
const T = (k) => window.i18n.t(k);

let config = null;
let accounts = [];
const nameCache = {}; // id -> ten (nhom/nguoi) de hien thi dep

// ---------- Tien ich ----------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
};
const esc = (s) => {
  let str = String(s == null ? "" : s);
  try {
    str = str.normalize("NFC"); // gộp dấu tổ hợp (vd "ê") để không bị mất khi hiển thị
  } catch (_e) {
    /* môi trường không hỗ trợ normalize -> bỏ qua */
  }
  return str.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
};

function toast(msg) {
  logLine({ level: "info", msg, ts: Date.now() });
  showToast(msg);
}

function showToast(msg) {
  let host = document.getElementById("toast-host");
  if (!host) {
    host = document.createElement("div");
    host.id = "toast-host";
    document.body.appendChild(host);
  }
  const t = document.createElement("div");
  t.className = "toast";
  const isErr = /lỗi|error|❌/i.test(String(msg));
  if (isErr) t.classList.add("err");
  t.textContent = (isErr ? "" : "✅ ") + String(msg);
  host.appendChild(t);
  setTimeout(() => t.classList.add("hide"), 2400);
  setTimeout(() => t.remove(), 2800);
}

// ---------- Dieu huong ----------
$$(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".nav-item").forEach((b) => b.classList.remove("active"));
    $$(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $("#panel-" + btn.dataset.panel).classList.add("active");
  });
});

// ---------- Khoi tao ----------
function applyAppInfo() {
  const set = (id, txt) => {
    const e = $("#" + id);
    if (e) e.textContent = txt;
  };
  set("app-name", APP.name);
  set("app-version", "v" + APP.version);
  set("app-author", APP.author);
  set("app-year", String(APP.year));
  document.title = `${APP.name} v${APP.version}`;
}

async function init() {
  applyAppInfo();
  config = await bridge.loadConfig();
  if (!config.ruleSets) config.ruleSets = {};
  if (!config.routes) config.routes = [];
  if (!config.sending) config.sending = { minDelayMs: 3000, maxDelayMs: 7000, maxPerHour: 0, maxPerDay: 0 };
  if (!config.accountOverrides) config.accountOverrides = {};
  if (!config.ui) config.ui = { theme: "light", lang: "vi" };
  migrateAIConfig();

  applyTheme(config.ui.theme || "light");
  applyLang(config.ui.lang || "vi", true);

  await refreshAccounts();
  renderRoutesPanel();
  renderRulesPanel();
  renderRunPanel();
  renderAIPanel();
  renderBroadcastPanel();
  renderFriendsPanel();
  bindGlobal();
  bindProControls();
  registerEvents();
  bridge.forwardStatus().then((st) => applyStatus(st));

  // Bản quyền: kiểm tra & hiện màn kích hoạt nếu cần.
  await refreshLicense();
  setInterval(refreshLicense, 60000); // kiểm tra lại mỗi phút (đếm ngược trial, hết hạn...)
}

// ---------- Giao diện Pro: theme, ngôn ngữ, bản quyền ----------
function applyTheme(theme) {
  document.body.setAttribute("data-theme", theme === "dark" ? "dark" : "light");
}
function applyLang(lang, silent) {
  window.i18n.setLang(lang);
  window.i18n.applyStaticI18n();
  const ll = $("#lang-label");
  if (ll) ll.textContent = lang === "vi" ? "EN" : "VI";
  document.documentElement.lang = lang;
  if (!silent) reRenderAll();
}
function reRenderAll() {
  renderAccounts();
  renderRoutesPanel();
  renderRulesPanel();
  renderRunPanel();
  renderBroadcastPanel();
  renderFriendsPanel();
}

function bindProControls() {
  $("#btn-theme").addEventListener("click", async () => {
    config.ui.theme = (config.ui.theme || "light") === "light" ? "dark" : "light";
    applyTheme(config.ui.theme);
    await saveConfig();
  });
  $("#btn-lang").addEventListener("click", async () => {
    config.ui.lang = (config.ui.lang || "vi") === "vi" ? "en" : "vi";
    applyLang(config.ui.lang);
    await saveConfig();
  });

  // Gate (kích hoạt bản quyền)
  $("#btn-copy-machine").addEventListener("click", () => {
    navigator.clipboard.writeText($("#gate-machine").textContent || "");
  });
  $("#btn-save-server").addEventListener("click", async () => {
    const url = $("#gate-server").value.trim();
    const st = await bridge.licenseSetServer(url);
    updateLicenseUI(st);
    $("#gate-msg").textContent = "";
  });
  $("#btn-activate").addEventListener("click", async () => {
    const key = $("#gate-key").value.trim();
    $("#gate-msg").textContent = "…";
    const r = await bridge.licenseActivate(key);
    if (r.ok) {
      await refreshLicense();
      $("#gate-msg").textContent = "✅ OK";
    } else {
      $("#gate-msg").textContent = "❌ " + window.i18n.reason(r.reason);
    }
  });
  // Mở lại màn bản quyền bất cứ lúc nào bằng cách bấm huy hiệu.
  $("#lic-badge").addEventListener("click", openGate);
  $("#gate-close").addEventListener("click", closeGate);
}

let manualGate = false;
async function openGate() {
  manualGate = true;
  $("#gate").classList.add("show");
  $("#gate-msg").textContent = "";
  await refreshLicense();
}
function closeGate() {
  manualGate = false;
  $("#gate").classList.remove("show");
}

function fmtDur(ms) {
  ms = Math.max(0, ms || 0);
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms % 3600000) / 60000);
  if (h >= 24) return Math.floor(h / 24) + "d " + (h % 24) + "h";
  return h + "h " + m + "m";
}

function licenseAllowed(st) {
  return st && (st.status === "licensed" || st.status === "trial");
}

async function refreshLicense() {
  try {
    const st = await bridge.licenseStatus();
    updateLicenseUI(st);
  } catch (_e) {}
}

function updateLicenseUI(st) {
  // Mã máy + server
  $("#gate-machine").textContent = st.machineId || "-";
  if (document.activeElement !== $("#gate-server")) $("#gate-server").value = st.serverUrl || "";
  // Ẩn ô địa chỉ máy chủ khi đã có (khách không cần thấy).
  const sf = $("#gate-server-field");
  if (sf) sf.style.display = st.serverUrl ? "none" : "block";

  // Huy hiệu
  const b = $("#lic-badge");
  if (st.status === "licensed") {
    let ex = st.lifetime ? T("lic.lifetime") : st.expiresAt ? new Date(st.expiresAt).toLocaleDateString() : "";
    b.textContent = "✅ " + T("lic.licensed") + (ex ? " · " + ex : "");
    b.className = "lic-badge ok";
  } else if (st.status === "trial") {
    const remain = st.remainingMs != null ? st.remainingMs : (st.expiresAt || 0) - Date.now();
    b.textContent = "⏳ " + T("lic.trialBanner") + " · " + T("lic.left") + " " + fmtDur(remain);
    b.className = "lic-badge trial";
  } else {
    b.textContent = "🔒 " + (st.reason ? window.i18n.reason(st.reason) : T("gate.title"));
    b.className = "lic-badge locked";
  }

  // Nội dung trạng thái trong màn bản quyền (mọi trạng thái).
  let msg = "";
  if (st.status === "licensed") {
    let ex = st.lifetime ? T("lic.lifetime") : st.expiresAt ? new Date(st.expiresAt).toLocaleString() : "";
    msg = "✅ " + T("lic.licensed") + (ex ? " · " + T("lic.expires") + ": " + ex : "");
  } else if (st.status === "trial") {
    const remain = st.remainingMs != null ? st.remainingMs : (st.expiresAt || 0) - Date.now();
    msg = T("gate.trialOn") + " " + T("gate.trialLeft") + " " + fmtDur(remain);
  } else if (st.status === "no_server") {
    msg = T("gate.needServer");
  } else if (st.status === "locked") {
    msg = T("gate.locked") + (st.reason ? " (" + window.i18n.reason(st.reason) + ")" : "");
  }
  $("#gate-status").textContent = msg;

  // Cổng: chặn khi chưa hợp lệ; nếu hợp lệ thì chỉ hiện khi người dùng tự mở.
  const gate = $("#gate");
  const allowed = licenseAllowed(st);
  $("#gate-close").style.display = allowed ? "block" : "none"; // chỉ cho đóng khi còn hạn
  if (!allowed) {
    gate.classList.add("show");
  } else if (!manualGate) {
    gate.classList.remove("show");
  }
}

function bindGlobal() {
  $("#btn-add-account").addEventListener("click", openLoginModal);
  const btnExp = $("#btn-export-config");
  if (btnExp)
    btnExp.addEventListener("click", async () => {
      try {
        const r = await bridge.exportConfig();
        if (r && r.ok) toast("Đã sao lưu cấu hình.");
        else if (r && r.error) toast("Lỗi sao lưu: " + r.error);
      } catch (e) {
        toast("Lỗi sao lưu: " + (e.message || e));
      }
    });
  const btnImp = $("#btn-import-config");
  if (btnImp)
    btnImp.addEventListener("click", async () => {
      if (!confirm("Khôi phục cấu hình từ file sẽ GHI ĐÈ cấu hình hiện tại (kịch bản, mẫu, cài đặt AI…). Tiếp tục?")) return;
      try {
        const r = await bridge.importConfig();
        if (r && r.ok && r.config) {
          config = r.config;
          migrateAIConfig();
          if (!config.ruleSets) config.ruleSets = {};
          if (!config.routes) config.routes = [];
          if (!config.ui) config.ui = { theme: "light", lang: "vi" };
          applyTheme(config.ui.theme || "light");
          applyLang(config.ui.lang || "vi", true);
          reRenderAll();
          toast("Đã khôi phục cấu hình.");
        } else if (r && r.error) {
          toast("Lỗi khôi phục: " + r.error);
        }
      } catch (e) {
        toast("Lỗi khôi phục: " + (e.message || e));
      }
    });
  $("#btn-add-route").addEventListener("click", addRoute);
  $("#btn-save-routes").addEventListener("click", saveConfig);
  $("#btn-add-rule").addEventListener("click", addRuleSet);
  $("#btn-save-rules").addEventListener("click", saveConfig);
  $("#btn-clear-log").addEventListener("click", () => { logEntries = []; renderLog(); });
  $("#log-level").addEventListener("change", renderLog);
  $("#log-query").addEventListener("input", renderLog);
  $("#btn-export-log").addEventListener("click", () => {
    const data = window.ForwarderOperations.csv(filteredLogs());
    const url = URL.createObjectURL(new Blob([data], {type: "text/csv;charset=utf-8"}));
    const a = document.createElement("a"); a.href = url;
    a.download = "Zalo-NhatKy-" + new Date().toISOString().slice(0,10) + ".csv";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  $("#btn-start-all").addEventListener("click", startAll);
  $("#btn-stop-all").addEventListener("click", stopAll);
  $("#btn-save-sending").addEventListener("click", saveSending);
  $("#sending-head").addEventListener("click", () => {
    const b = $("#sending-body");
    b.style.display = b.style.display === "none" ? "block" : "none";
  });

  $$("[data-close-modal]").forEach((b) =>
    b.addEventListener("click", () => {
      $("#modal-login").classList.remove("show");
      $("#modal-picker").classList.remove("show");
    })
  );
}

async function saveConfig() {
  await bridge.saveConfig(config);
  toast("Đã lưu cấu hình.");
}

// ================= TÀI KHOẢN =================
async function refreshAccounts() {
  accounts = await bridge.listAccounts();
  renderAccounts();
  renderAccountSelect();
}

function renderAccounts() {
  const wrap = $("#accounts-list");
  wrap.innerHTML = "";
  if (accounts.length === 0) {
    wrap.appendChild(el("div", "empty", T("acc.empty")));
    return;
  }
  for (const a of accounts) {
    const card = el("div", "card");
    card.innerHTML = `
      <div class="card-title"><span class="dot ${a.connected ? "on" : "off"}"></span>${esc(a.name)}</div>
      <div class="card-meta">${a.connected ? T("acc.connected") : T("acc.saved")}${
      a.uid ? " · UID " + esc(a.uid) : ""
    }</div>`;
    const actions = el("div", "card-actions");
    const bConn = el("button", "btn small primary", a.connected ? T("acc.reconnect") : T("acc.connect"));
    bConn.addEventListener("click", async () => {
      bConn.disabled = true;
      bConn.textContent = "…";
      try {
        await bridge.connect(a.name);
        toast(`OK: ${a.name}.`);
      } catch (e) {
        toast("Lỗi kết nối: " + e.message);
      }
      await refreshAccounts();
    });
    const bRelogin = el("button", "btn small", T("acc.relogin"));
    bRelogin.addEventListener("click", () => openLoginModal(a.name));
    const bDel = el("button", "btn small danger", T("acc.delete"));
    bDel.addEventListener("click", async () => {
      if (!confirm(`Xoá tài khoản "${a.name}"?`)) return;
      await bridge.deleteAccount(a.name);
      await refreshAccounts();
    });
    actions.append(bConn, bRelogin, bDel);
    card.appendChild(actions);
    wrap.appendChild(card);
  }
}

function renderAccountSelect() {
  // Dat tai khoan mac dinh neu chua co.
  if (!config.account && accounts[0]) config.account = accounts[0].name;
}

function accountOptions(selected) {
  let html = "";
  if (accounts.length === 0) html += `<option value="">(chưa có tài khoản)</option>`;
  for (const a of accounts) {
    html += `<option value="${esc(a.name)}" ${a.name === selected ? "selected" : ""}>${esc(a.name)}</option>`;
  }
  return html;
}

// ---- Modal đăng nhập ----
let loginName = "";
function openLoginModal(presetName) {
  loginName = typeof presetName === "string" ? presetName : "";
  $("#login-name").value = loginName;
  $("#login-step-name").style.display = "block";
  $("#login-step-qr").style.display = "none";
  $("#qr-img").src = "";
  $("#login-status").textContent = "Đang tạo mã QR…";
  $("#modal-login").classList.add("show");
  $("#btn-start-login").onclick = doLogin;
}

async function doLogin() {
  const name = ($("#login-name").value || "").trim();
  if (!name) {
    alert("Nhập tên gợi nhớ cho tài khoản.");
    return;
  }
  loginName = name;
  $("#login-step-name").style.display = "none";
  $("#login-step-qr").style.display = "block";
  try {
    await bridge.loginQR(name); // resolve khi đăng nhập xong
    $("#login-status").textContent = "✅ Đăng nhập thành công!";
    setTimeout(() => $("#modal-login").classList.remove("show"), 900);
    await refreshAccounts();
  } catch (e) {
    $("#login-status").textContent = "❌ Lỗi: " + e.message;
  }
}

// ================= TUYẾN CHUYỂN TIẾP =================
function addRoute() {
  config.routes.push({
    name: "Kịch bản mới",
    enabled: true,
    account: config.account || (accounts.find((a) => a.connected) || accounts[0] || {}).name || "",
    sources: [],
    destinations: [],
    forward: { text: true, image: true, video: true, file: false },
    ruleSet: Object.keys(config.ruleSets)[0] || "",
    includeKeywords: [],
    excludeKeywords: [],
  });
  renderRoutesPanel();
  renderRunPanel();
  saveConfig();
}

function renderRoutesPanel() {
  renderAccountSelect();
  const wrap = $("#routes-list");
  wrap.innerHTML = "";
  if (config.routes.length === 0) {
    wrap.appendChild(el("div", "empty", T("routes.empty")));
    return;
  }
  config.routes.forEach((route, idx) => wrap.appendChild(renderRouteBlock(route, idx)));
}

function ruleSetOptions(selected) {
  const names = Object.keys(config.ruleSets);
  let html = `<option value="">(không biên tập)</option>`;
  for (const n of names) html += `<option value="${esc(n)}" ${n === selected ? "selected" : ""}>${esc(n)}</option>`;
  return html;
}

function renderRouteBlock(route, idx) {
  const block = el("div", "block");
  const head = el("div", "block-head");
  head.innerHTML = `
    <span class="dot ${route.enabled !== false ? "on" : "off"}"></span>
    <span class="title">${esc(route.name || "Kịch bản")}</span>
    <span class="mini">${(route.sources || []).length} nguồn → ${(route.destinations || []).length} đích</span>
    <span class="mini">▼</span>`;
  const body = el("div", "block-body");
  body.style.display = "none";
  head.addEventListener("click", (e) => {
    if (e.target.tagName === "BUTTON") return;
    body.style.display = body.style.display === "none" ? "block" : "none";
  });

  // Ten + bat/tat + xoa
  const f1 = el("div", "field");
  f1.innerHTML = `<label>Tên kịch bản</label>`;
  const nameInput = el("input");
  nameInput.type = "text";
  nameInput.value = route.name || "";
  nameInput.addEventListener("input", (e) => {
    route.name = e.target.value;
    head.querySelector(".title").textContent = e.target.value || "Kịch bản";
  });
  nameInput.addEventListener("change", () => saveConfig()); // tự lưu khi đổi tên xong (rời ô)
  f1.appendChild(nameInput);

  const rowTop = el("div", "row-inline");
  const chkEnabled = el("label", "check");
  chkEnabled.innerHTML = `<input type="checkbox" ${route.enabled !== false ? "checked" : ""}/> Bật kịch bản này`;
  chkEnabled.querySelector("input").addEventListener("change", (e) => {
    route.enabled = e.target.checked;
    head.querySelector(".dot").className = "dot " + (e.target.checked ? "on" : "off");
    saveConfig();
  });
  const btnCloneRoute = el("button", "btn small ghost", "⧉ Nhân bản");
  btnCloneRoute.addEventListener("click", () => {
    const copy = JSON.parse(JSON.stringify(route));
    copy.name = (route.name || "Kịch bản") + " (bản sao)";
    config.routes.splice(idx + 1, 0, copy);
    renderRoutesPanel();
    renderRunPanel();
    saveConfig();
    toast("Đã nhân bản kịch bản.");
  });
  const btnDelRoute = el("button", "btn small danger", "Xoá kịch bản");
  btnDelRoute.addEventListener("click", () => {
    if (!confirm("Xoá kịch bản này?")) return;
    config.routes.splice(idx, 1);
    renderRoutesPanel();
    renderRunPanel();
    saveConfig();
  });
  rowTop.append(chkEnabled, btnCloneRoute, btnDelRoute);

  // Tài khoản chạy kịch bản này - TỰ SỬA nếu trỏ tới tài khoản không còn (đã đăng xuất/đổi tên)
  const validNames = accounts.map((a) => a.name);
  if (!route.account || !validNames.includes(route.account)) {
    const fixed = (accounts.find((a) => a.connected) || accounts[0] || {}).name || "";
    if (fixed && fixed !== route.account) {
      route.account = fixed;
      saveConfig(); // lưu ngay để lần chạy/chọn nhóm dùng đúng tài khoản đang có
    }
  }
  const fAcc = el("div", "field");
  fAcc.innerHTML = `<label>Tài khoản Zalo chạy kịch bản này</label><select>${accountOptions(
    route.account || config.account
  )}</select>`;
  fAcc.querySelector("select").addEventListener("change", (e) => {
    route.account = e.target.value;
    renderRunPanel();
    saveConfig();
  });

  // Nguồn
  const srcWrap = el("div", "field");
  srcWrap.innerHTML = `<label>Nhóm nguồn (nghe tin mới từ đây)</label>`;
  const srcTags = el("div", "tag-list");
  const renderSrcTags = () => {
    srcTags.innerHTML = "";
    (route.sources || []).forEach((id, i) => {
      const t = el("div", "tag", `${esc(nameCache[id] || id)} <span class="x">✕</span>`);
      t.querySelector(".x").addEventListener("click", () => {
        route.sources.splice(i, 1);
        renderSrcTags();
        head.querySelector(".mini").textContent = `${route.sources.length} nguồn → ${route.destinations.length} đích`;
        saveConfig();
      });
      srcTags.appendChild(t);
    });
  };
  renderSrcTags();
  const btnPickSrc = el("button", "btn small", "＋ Chọn nhóm nguồn");
  btnPickSrc.addEventListener("click", async () => {
    const picked = await openPicker("group", "Chọn nhóm nguồn", route.account);
    if (!picked) return;
    for (const p of picked) if (!route.sources.includes(p.id)) route.sources.push(p.id);
    renderSrcTags();
    head.querySelector(".mini").textContent = `${route.sources.length} nguồn → ${route.destinations.length} đích`;
    saveConfig();
  });
  srcWrap.append(srcTags, btnPickSrc);

  // Đích
  const dstWrap = el("div", "field");
  dstWrap.innerHTML = `<div class="subhead">Đích chuyển tới</div>`;
  const dstRows = el("div");
  const renderDst = () => {
    dstRows.innerHTML = "";
    (route.destinations || []).forEach((d, i) => {
      const row = el("div", "dest-row");
      // Hiện TÊN nhóm/người nếu đã biết (thay vì chỉ dãy ID khó đọc)
      const knownName = nameCache[d.threadId];
      if (knownName) {
        const nameTag = el("span", "dest-name", "📛 " + esc(knownName));
        nameTag.title = d.threadId;
        row.appendChild(nameTag);
      }
      const typeSel = el("select");
      typeSel.innerHTML = `<option value="group" ${d.type === "group" ? "selected" : ""}>Nhóm</option>
        <option value="user" ${d.type === "user" ? "selected" : ""}>Người</option>`;
      typeSel.style.width = "90px";
      typeSel.addEventListener("change", (e) => {
        d.type = e.target.value;
        saveConfig();
      });
      const idInput = el("input");
      idInput.type = "text";
      idInput.placeholder = "ID";
      idInput.value = d.threadId || "";
      idInput.style.flex = "1";
      idInput.addEventListener("input", (e) => (d.threadId = e.target.value.trim()));
      idInput.addEventListener("change", () => saveConfig());
      const rsSel = el("select");
      rsSel.innerHTML = `<option value="">(theo kịch bản)</option>` + ruleSetOptions(d.ruleSet).replace(/^<option value="">.*?<\/option>/, "");
      rsSel.value = d.ruleSet || "";
      rsSel.style.width = "130px";
      rsSel.addEventListener("change", (e) => {
        d.ruleSet = e.target.value || undefined;
        saveConfig();
      });
      const rm = el("button", "btn small danger", "✕");
      rm.addEventListener("click", () => {
        route.destinations.splice(i, 1);
        renderDst();
        saveConfig();
      });
      row.append(typeSel, idInput, rsSel, rm);
      dstRows.appendChild(row);
    });
  };
  renderDst();
  const dstBtns = el("div", "row-inline");
  const bPickG = el("button", "btn small", "＋ Chọn nhóm");
  bPickG.addEventListener("click", async () => {
    const picked = await openPicker("group", "Chọn nhóm đích", route.account);
    if (!picked) return;
    for (const p of picked) route.destinations.push({ threadId: p.id, type: "group" });
    renderDst();
    saveConfig();
  });
  const bPickU = el("button", "btn small", "＋ Chọn người");
  bPickU.addEventListener("click", async () => {
    const picked = await openPicker("friend", "Chọn người nhận", route.account);
    if (!picked) return;
    for (const p of picked) route.destinations.push({ threadId: p.id, type: "user" });
    renderDst();
    saveConfig();
  });
  const bAddManual = el("button", "btn small ghost", "＋ Nhập ID tay");
  bAddManual.addEventListener("click", () => {
    route.destinations.push({ threadId: "", type: "group" });
    renderDst();
  });
  dstBtns.append(bPickG, bPickU, bAddManual);

  // Loại nội dung chuyển
  const fwWrap = el("div", "field");
  fwWrap.innerHTML = `<div class="subhead">Loại nội dung chuyển tiếp</div>`;
  const checks = el("div", "checks");
  const mk = (key, label) => {
    const c = el("label", "check");
    c.innerHTML = `<input type="checkbox" ${route.forward[key] ? "checked" : ""}/> ${label}`;
    c.querySelector("input").addEventListener("change", (e) => (route.forward[key] = e.target.checked));
    return c;
  };
  checks.append(mk("text", "Text"), mk("image", "Ảnh"), mk("video", "Video"), mk("file", "File"));
  fwWrap.appendChild(checks);

  // Bộ biên tập (độ trễ cấu hình ở tab Chạy - áp dụng chung theo tài khoản)
  const grid = el("div", "grid2");
  const fRS = el("div", "field");
  fRS.innerHTML = `<label>Mẫu nội dung áp dụng</label><select>${ruleSetOptions(route.ruleSet)}</select>`;
  fRS.querySelector("select").addEventListener("change", (e) => (route.ruleSet = e.target.value));
  const fNote = el("div", "field");
  fNote.innerHTML = `<label>&nbsp;</label><div class="mini">Độ trễ &amp; giới hạn gửi cài ở tab “Chạy &amp; Nhật ký”.</div>`;
  grid.append(fRS, fNote);

  // Từ khoá lọc
  const kwGrid = el("div", "grid2");
  const fInc = el("div", "field");
  fInc.innerHTML = `<label>Chỉ chuyển nếu chứa từ (phẩy ngăn cách, để trống = không lọc)</label>`;
  const incIn = el("input");
  incIn.type = "text";
  incIn.value = (route.includeKeywords || []).join(", ");
  incIn.addEventListener("input", (e) => (route.includeKeywords = splitCsv(e.target.value)));
  fInc.appendChild(incIn);
  const fExc = el("div", "field");
  fExc.innerHTML = `<label>Bỏ qua nếu chứa từ (phẩy ngăn cách)</label>`;
  const excIn = el("input");
  excIn.type = "text";
  excIn.value = (route.excludeKeywords || []).join(", ");
  excIn.addEventListener("input", (e) => (route.excludeKeywords = splitCsv(e.target.value)));
  fExc.appendChild(excIn);
  kwGrid.append(fInc, fExc);

  body.append(f1, rowTop, fAcc, srcWrap, dstWrap, dstRows, dstBtns, fwWrap, grid, kwGrid);
  block.append(head, body);
  return block;
}

function splitCsv(s) {
  return String(s)
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
}

// ================= BỘ BIÊN TẬP =================
function addRuleSet() {
  let base = "bo_moi";
  let name = base;
  let i = 1;
  while (config.ruleSets[name]) name = base + ++i;
  config.ruleSets[name] = {
    brand: { enabled: false, caseInsensitive: true, map: {} },
    price: { enabled: false, mode: "add_amount", amount: 0, round: 1000, map: {} },
    link: { enabled: false, action: "remove", replaceWith: "" },
    custom: [],
    prependText: "",
    appendText: "",
  };
  renderRulesPanel();
}

function renderRulesPanel() {
  const wrap = $("#rules-list");
  wrap.innerHTML = "";
  const names = Object.keys(config.ruleSets);
  if (names.length === 0) {
    wrap.appendChild(el("div", "empty", T("rules.empty")));
    return;
  }
  for (const name of names) wrap.appendChild(renderRuleBlock(name, config.ruleSets[name]));
}

function renderRuleBlock(name, rs) {
  const block = el("div", "block");
  const head = el("div", "block-head");
  head.innerHTML = `<span class="title">✏️ ${esc(name)}</span><span class="mini">▼</span>`;
  const body = el("div", "block-body");
  body.style.display = "none";
  head.addEventListener("click", (e) => {
    if (e.target.tagName === "BUTTON") return;
    body.style.display = body.style.display === "none" ? "block" : "none";
  });

  // Đổi tên bộ + xoá
  const rowTop = el("div", "row-inline");
  const nameF = el("div", "field");
  nameF.style.flex = "1";
  nameF.innerHTML = `<label>Tên mẫu (gán cho kịch bản)</label>`;
  const nameIn = el("input");
  nameIn.type = "text";
  nameIn.value = name;
  nameIn.addEventListener("change", (e) => {
    const nn = (e.target.value || "").trim();
    if (!nn || nn === name) return;
    if (config.ruleSets[nn]) {
      alert("Tên đã tồn tại.");
      e.target.value = name;
      return;
    }
    config.ruleSets[nn] = config.ruleSets[name];
    delete config.ruleSets[name];
    // Cập nhật tham chiếu trong routes
    for (const r of config.routes) {
      if (r.ruleSet === name) r.ruleSet = nn;
      for (const d of r.destinations || []) if (d.ruleSet === name) d.ruleSet = nn;
    }
    renderRulesPanel();
  });
  nameF.appendChild(nameIn);
  const delBtn = el("button", "btn small danger", "Xoá mẫu");
  delBtn.addEventListener("click", () => {
    if (!confirm(`Xoá mẫu "${name}"?`)) return;
    delete config.ruleSets[name];
    renderRulesPanel();
  });
  rowTop.append(nameF, delBtn);

  // --- Đổi tên thương hiệu ---
  const brandH = el("div", "subhead", "Đổi tên thương hiệu");
  const brandChk = el("label", "check");
  brandChk.innerHTML = `<input type="checkbox" ${rs.brand && rs.brand.enabled ? "checked" : ""}/> Bật đổi tên thương hiệu`;
  if (!rs.brand) rs.brand = { enabled: false, caseInsensitive: true, map: {} };
  if (!rs.brand.map) rs.brand.map = {};
  brandChk.querySelector("input").addEventListener("change", (e) => (rs.brand.enabled = e.target.checked));
  const brandMap = mapEditor(rs.brand.map, "Tên gốc", "Đổi thành");

  // --- Đổi giá ---
  const priceH = el("div", "subhead", "Đổi giá");
  if (!rs.price) rs.price = { enabled: false, mode: "add_amount", amount: 0, round: 1000, map: {} };
  const priceChk = el("label", "check");
  priceChk.innerHTML = `<input type="checkbox" ${rs.price.enabled ? "checked" : ""}/> Bật đổi giá`;
  priceChk.querySelector("input").addEventListener("change", (e) => (rs.price.enabled = e.target.checked));
  const priceBox = el("div");
  const renderPrice = () => {
    priceBox.innerHTML = "";
    const modeF = el("div", "field");
    modeF.innerHTML = `<label>Cách đổi</label>
      <select>
        <option value="add_amount" ${rs.price.mode === "add_amount" ? "selected" : ""}>Cộng số tiền cố định (VND)</option>
        <option value="add_percent" ${rs.price.mode === "add_percent" ? "selected" : ""}>Cộng phần trăm (%)</option>
        <option value="multiply" ${rs.price.mode === "multiply" ? "selected" : ""}>Nhân hệ số</option>
        <option value="replace_map" ${rs.price.mode === "replace_map" ? "selected" : ""}>Thay chính xác (vd 400k→450k)</option>
      </select>`;
    modeF.querySelector("select").addEventListener("change", (e) => {
      rs.price.mode = e.target.value;
      renderPrice();
    });
    priceBox.appendChild(modeF);

    if (rs.price.mode === "add_amount") {
      priceBox.appendChild(numField("Số tiền cộng thêm (VND)", rs.price.amount || 0, (v) => (rs.price.amount = v)));
    } else if (rs.price.mode === "add_percent") {
      priceBox.appendChild(numField("Phần trăm cộng thêm (%)", rs.price.percent || 0, (v) => (rs.price.percent = v)));
    } else if (rs.price.mode === "multiply") {
      priceBox.appendChild(numField("Hệ số nhân (vd 1.15)", rs.price.factor || 1, (v) => (rs.price.factor = v), true));
    } else if (rs.price.mode === "replace_map") {
      if (!rs.price.map) rs.price.map = {};
      priceBox.appendChild(mapEditor(rs.price.map, "Giá gốc (vd 400k)", "Đổi thành (vd 450k)"));
    }
    if (rs.price.mode !== "replace_map") {
      priceBox.appendChild(numField("Làm tròn về bội số (vd 1000)", rs.price.round == null ? 1000 : rs.price.round, (v) => (rs.price.round = v)));

      // Nhận cả số trần (không có "k")
      if (!rs.price.bareNumber) rs.price.bareNumber = { enabled: false, min: 50, max: 2000 };
      const bn = rs.price.bareNumber;
      const bnChk = el("label", "check");
      bnChk.style.marginTop = "6px";
      bnChk.innerHTML = `<input type="checkbox" ${bn.enabled ? "checked" : ""}/> Nhận cả số trần “400” (hiểu là 400k)`;
      const bnBox = el("div");
      const renderBn = () => {
        bnBox.innerHTML = "";
        if (!bn.enabled) return;
        bnBox.appendChild(
          el("div", "mini", "Chỉ đổi số trong khoảng dưới đây (tránh sửa nhầm SĐT/ngày/năm). VD: 400 → " + (bn.min || 50) + "–" + (bn.max || 2000))
        );
        const g = el("div", "grid2");
        g.append(
          numField("Số nhỏ nhất (nghìn)", bn.min == null ? 50 : bn.min, (v) => (bn.min = v)),
          numField("Số lớn nhất (nghìn)", bn.max == null ? 2000 : bn.max, (v) => (bn.max = v))
        );
        bnBox.appendChild(g);
      };
      bnChk.querySelector("input").addEventListener("change", (e) => {
        bn.enabled = e.target.checked;
        renderBn();
      });
      renderBn();
      priceBox.appendChild(bnChk);
      priceBox.appendChild(bnBox);
    }
  };
  renderPrice();

  // --- Link ---
  const linkH = el("div", "subhead", "Xoá / thay link");
  if (!rs.link) rs.link = { enabled: false, action: "remove", replaceWith: "" };
  const linkChk = el("label", "check");
  linkChk.innerHTML = `<input type="checkbox" ${rs.link.enabled ? "checked" : ""}/> Bật xử lý link`;
  linkChk.querySelector("input").addEventListener("change", (e) => (rs.link.enabled = e.target.checked));
  const linkBox = el("div");
  const renderLink = () => {
    linkBox.innerHTML = "";
    const actF = el("div", "field");
    actF.innerHTML = `<label>Hành động</label>
      <select>
        <option value="remove" ${rs.link.action === "remove" ? "selected" : ""}>Xoá link</option>
        <option value="replace" ${rs.link.action === "replace" ? "selected" : ""}>Thay bằng link khác</option>
      </select>`;
    actF.querySelector("select").addEventListener("change", (e) => {
      rs.link.action = e.target.value;
      renderLink();
    });
    linkBox.appendChild(actF);
    if (rs.link.action === "replace") {
      linkBox.appendChild(textField("Link thay thế", rs.link.replaceWith || "", (v) => (rs.link.replaceWith = v)));
    }
  };
  renderLink();

  // --- Custom regex ---
  const customH = el("div", "subhead", "Thay thế nâng cao (regex, tuỳ chọn)");
  if (!Array.isArray(rs.custom)) rs.custom = [];
  const customBox = el("div");
  const renderCustom = () => {
    customBox.innerHTML = "";
    rs.custom.forEach((c, i) => {
      const row = el("div", "custom-row");
      const p = el("input");
      p.type = "text";
      p.placeholder = "mẫu (pattern)";
      p.value = c.pattern || "";
      p.style.flex = "2";
      p.addEventListener("input", (e) => (c.pattern = e.target.value));
      const fl = el("input");
      fl.type = "text";
      fl.placeholder = "cờ (gi)";
      fl.value = c.flags || "gi";
      fl.style.width = "60px";
      fl.addEventListener("input", (e) => (c.flags = e.target.value));
      const rp = el("input");
      rp.type = "text";
      rp.placeholder = "thay bằng";
      rp.value = c.replaceWith || "";
      rp.style.flex = "2";
      rp.addEventListener("input", (e) => (c.replaceWith = e.target.value));
      const rm = el("button", "btn small danger", "✕");
      rm.addEventListener("click", () => {
        rs.custom.splice(i, 1);
        renderCustom();
      });
      row.append(p, fl, rp, rm);
      customBox.appendChild(row);
    });
    const add = el("button", "btn small ghost", "＋ Thêm dòng");
    add.addEventListener("click", () => {
      rs.custom.push({ pattern: "", flags: "gi", replaceWith: "" });
      renderCustom();
    });
    customBox.appendChild(add);
  };
  renderCustom();

  // --- Prepend/Append ---
  const ppH = el("div", "subhead", "Chèn text đầu / cuối");
  const ppGrid = el("div", "grid2");
  ppGrid.append(
    textAreaField("Chèn lên đầu", rs.prependText || "", (v) => (rs.prependText = v)),
    textAreaField("Chèn xuống cuối (vd chữ ký shop)", rs.appendText || "", (v) => (rs.appendText = v))
  );

  // --- Dùng AI biên tập (bật riêng từng mẫu) ---
  if (rs.useAI === undefined) rs.useAI = false;
  if (!rs.ai) rs.ai = { provider: "", model: "" };
  const aiChk = el("label", "check ai-toggle");
  aiChk.innerHTML = `<input type="checkbox" ${rs.useAI ? "checked" : ""}/> 🤖 Dùng AI biên tập thông minh cho mẫu này`;
  const aiNote = el(
    "div",
    "mini ai-note",
    "Khi bật: AI đọc tin rồi áp dụng các thiết lập bên dưới một cách thông minh - tự phân biệt giá / số lượng / size / SĐT. " +
      "Cần nhập API key ở mục 🤖 AI. Nếu AI lỗi sẽ tự dùng quy tắc thường."
  );

  // Chọn nhà cung cấp + model riêng cho mẫu (hiện khi bật AI)
  const aiCfgBox = el("div", "ai-cfg");
  const renderAiCfg = () => {
    aiCfgBox.innerHTML = "";
    aiCfgBox.style.display = rs.useAI ? "grid" : "none";
    if (!rs.useAI) return;
    const eff = rs.ai.provider || (config.ai && config.ai.provider) || "openai";

    const pf = el("div", "field");
    pf.innerHTML = `<label>Nhà cung cấp AI cho mẫu này</label>`;
    const ps = el("select");
    ps.innerHTML =
      `<option value="">Mặc định (theo cài đặt AI)</option>` +
      ["openai", "claude", "gemini"]
        .map((p) => `<option value="${p}" ${rs.ai.provider === p ? "selected" : ""}>${AI_LABEL[p]}</option>`)
        .join("");
    ps.addEventListener("change", (e) => {
      rs.ai.provider = e.target.value;
      rs.ai.model = "";
      renderAiCfg();
    });
    pf.appendChild(ps);

    const dlId = "tmpl-models-" + eff;
    const dl = el("datalist");
    dl.id = dlId;
    dl.innerHTML = aiModelList(eff).map((m) => `<option value="${esc(m)}"></option>`).join("");
    const mf = el("div", "field");
    mf.innerHTML = `<label>Model (gõ hoặc chọn - để trống = mặc định)</label>`;
    const mi = el("input");
    mi.type = "text";
    mi.setAttribute("list", dlId);
    mi.value = rs.ai.model || "";
    mi.placeholder = AI_DEFAULT_MODEL[eff] || "";
    mi.addEventListener("change", (e) => (rs.ai.model = (e.target.value || "").trim()));
    mf.append(mi, dl);

    aiCfgBox.append(pf, mf);
  };
  aiChk.querySelector("input").addEventListener("change", (e) => {
    rs.useAI = e.target.checked;
    renderAiCfg();
  });
  renderAiCfg();

  const grid = el("div", "rule-grid");
  grid.append(
    ruleCard("🏷️ Đổi tên thương hiệu", brandChk, brandMap),
    ruleCard("💰 Đổi giá", priceChk, priceBox),
    ruleCard("🔗 Xoá / thay link", linkChk, linkBox),
    ruleCard("🔧 Thay thế nâng cao (regex)", customBox),
    ruleCard("📝 Chèn text đầu / cuối", ppGrid)
  );

  // --- Xem trước biên tập (dán 1 tin mẫu -> thấy kết quả sau khi áp mẫu) ---
  const pvWrap = el("div", "block");
  pvWrap.style.marginTop = "12px";
  const pvHead = el("div", "block-head static");
  pvHead.innerHTML = `<span class="title">🔎 Xem trước biên tập</span>`;
  const pvBody = el("div", "block-body");
  pvBody.style.display = "block";
  const pvIn = el("textarea");
  pvIn.rows = 3;
  pvIn.placeholder = "Dán một tin mẫu vào đây, vd: Váy LUU LEE 400k, xem http://abc.com";
  const pvBtn = el("button", "btn small primary", "Xem trước (quy tắc thường)");
  pvBtn.style.margin = "8px 0";
  const pvOut = el("div", "preview-out");
  pvOut.textContent = "(kết quả sẽ hiện ở đây)";
  pvBtn.addEventListener("click", async () => {
    const t = pvIn.value || "";
    if (!t.trim()) {
      pvOut.textContent = "(nhập tin mẫu trước)";
      return;
    }
    pvOut.textContent = "Đang xử lý…";
    try {
      const res = await bridge.previewRules(t, rs);
      pvOut.textContent = res || "(rỗng)";
    } catch (e) {
      pvOut.textContent = "Lỗi: " + (e.message || e);
    }
  });
  const pvNote = el("div", "mini", "Xem trước dùng quy tắc thường (không gọi AI để khỏi tốn phí). Nếu bật AI biên tập, kết quả thực tế có thể mượt hơn.");
  pvBody.append(pvIn, pvBtn, pvOut, pvNote);
  pvWrap.append(pvHead, pvBody);

  body.append(rowTop, aiChk, aiNote, aiCfgBox, grid, pvWrap);
  block.append(head, body);
  return block;
}

// Thẻ 1 nhóm thiết lập trong khu biên tập (bố cục cột–hàng).
function ruleCard(title, ...nodes) {
  const c = el("div", "rule-card");
  c.appendChild(el("div", "rule-card-title", esc(title)));
  for (const n of nodes) if (n) c.appendChild(n);
  return c;
}

// ================= AI (cài đặt API + soạn tin) =================
const AI_LABEL = { openai: "OpenAI (ChatGPT)", claude: "Claude (Anthropic)", gemini: "Gemini (Google)" };
const AI_DEFAULT_MODEL = { openai: "gpt-4o-mini", claude: "claude-3-5-haiku-latest", gemini: "gemini-1.5-flash" };
const AI_BUILTIN = {
  openai: ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini"],
  claude: ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest"],
  gemini: ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
};
// Model lấy thêm từ API (dùng chung cho panel AI và mục chọn model ở từng mẫu).
const aiModelsCache = { openai: [], claude: [], gemini: [] };
// Lịch sử khung chat với AI (giữ qua các lần render panel).
let aiChatHistory = [];
function aiModelList(provider) {
  return Array.from(new Set([...(AI_BUILTIN[provider] || []), ...(aiModelsCache[provider] || [])]));
}
// Chuyển config.ai kiểu cũ {provider,apiKey,model} -> {provider, keys:{}, models:{}}.
function migrateAIConfig() {
  if (!config.ai) config.ai = {};
  const a = config.ai;
  if (!a.provider) a.provider = "openai";
  if (!a.keys) a.keys = { openai: "", claude: "", gemini: "" };
  if (!a.models) a.models = { openai: "", claude: "", gemini: "" };
  if (a.apiKey && !a.keys[a.provider]) a.keys[a.provider] = a.apiKey;
  if (a.model && !a.models[a.provider]) a.models[a.provider] = a.model;
  delete a.apiKey;
  delete a.model;
}
// Đối tượng AI đã "chốt" để gọi thử/lấy model theo nhà cung cấp p.
function resolvedFor(p) {
  const a = config.ai;
  return { provider: p, apiKey: (a.keys && a.keys[p]) || "", model: (a.models && a.models[p]) || "" };
}

function renderAIPanel() {
  const wrap = $("#ai-body");
  if (!wrap) return;
  wrap.innerHTML = "";
  if (!config.ai || !config.ai.keys) migrateAIConfig();
  const ai = config.ai;
  const prov = ai.provider;

  // ----- Cài đặt AI -----
  const s = el("div", "block");
  const sh = el("div", "block-head static");
  sh.innerHTML = `<span class="title">🔑 Cài đặt AI (API) - lưu key cả 3 nhà cung cấp, đổi qua lại tuỳ ý</span>`;
  const sb = el("div", "block-body");
  sb.style.display = "block";

  const provF = el("div", "field");
  provF.innerHTML = `<label>Nhà cung cấp AI đang dùng (mặc định)</label>
    <select>
      <option value="openai" ${prov === "openai" ? "selected" : ""}>OpenAI (ChatGPT)</option>
      <option value="claude" ${prov === "claude" ? "selected" : ""}>Claude (Anthropic)</option>
      <option value="gemini" ${prov === "gemini" ? "selected" : ""}>Gemini (Google)</option>
    </select>`;
  provF.querySelector("select").addEventListener("change", async (e) => {
    ai.provider = e.target.value;
    await saveConfig();
    renderAIPanel();
  });

  // Trạng thái key của cả 3 nhà cung cấp
  const status = el("div", "mini");
  status.style.margin = "2px 0 10px";
  status.innerHTML =
    "Đã lưu key: " +
    ["openai", "claude", "gemini"].map((p) => `${AI_LABEL[p].split(" ")[0]} ${ai.keys[p] ? "✅" : "⬜"}`).join(" · ");

  const keyF = el("div", "field");
  keyF.innerHTML = `<label>API key của <b>${esc(AI_LABEL[prov])}</b></label>`;
  const keyIn = el("input");
  keyIn.type = "password";
  keyIn.value = ai.keys[prov] || "";
  keyIn.placeholder = "dán API key vào đây";
  keyIn.addEventListener("change", (e) => {
    ai.keys[prov] = (e.target.value || "").trim();
    saveConfig();
    renderAIPanel();
  });
  keyF.appendChild(keyIn);

  // Model: gõ hoặc chọn (datalist), kèm nút cập nhật danh sách từ tài khoản
  const dlId = "ai-models-" + prov;
  const dl = el("datalist");
  dl.id = dlId;
  dl.innerHTML = aiModelList(prov).map((m) => `<option value="${esc(m)}"></option>`).join("");
  const modelF = el("div", "field");
  modelF.innerHTML = `<label>Model của ${esc(AI_LABEL[prov])} (gõ hoặc chọn - để trống = mặc định ${esc(AI_DEFAULT_MODEL[prov])})</label>`;
  const modelIn = el("input");
  modelIn.type = "text";
  modelIn.setAttribute("list", dlId);
  modelIn.value = ai.models[prov] || "";
  modelIn.placeholder = AI_DEFAULT_MODEL[prov];
  modelIn.addEventListener("change", (e) => {
    ai.models[prov] = (e.target.value || "").trim();
    saveConfig();
  });
  const fetchBtn = el("button", "btn small ghost", "🔄 Cập nhật danh sách model");
  fetchBtn.style.marginTop = "6px";
  const fetchMsg = el("span", "mini");
  fetchMsg.style.marginLeft = "8px";
  fetchBtn.addEventListener("click", async () => {
    if (!ai.keys[prov]) {
      fetchMsg.textContent = "⚠️ Nhập API key trước đã.";
      return;
    }
    fetchMsg.textContent = "Đang tải…";
    try {
      const list = await bridge.aiListModels(resolvedFor(prov));
      aiModelsCache[prov] = list || [];
      fetchMsg.textContent = `✅ Có ${list.length} model`;
      renderAIPanel();
    } catch (e) {
      fetchMsg.textContent = "❌ " + (e.message || String(e));
    }
  });
  modelF.append(modelIn, dl, document.createElement("br"), fetchBtn, fetchMsg);

  const testBtn = el("button", "btn primary", "🔌 Kiểm tra kết nối");
  testBtn.style.marginTop = "10px";
  const testMsg = el("div", "mini");
  testMsg.style.marginTop = "8px";
  testBtn.addEventListener("click", async () => {
    testMsg.textContent = "Đang kiểm tra…";
    try {
      const r = await bridge.aiTest(resolvedFor(prov));
      testMsg.innerHTML = `✅ OK - ${esc(r.provider)} · model <b>${esc(r.model)}</b>`;
    } catch (e) {
      testMsg.innerHTML = `❌ Lỗi: ${esc(e.message || String(e))}`;
    }
  });

  const help = el("div", "mini");
  help.style.marginTop = "10px";
  help.innerHTML =
    "Mẹo: dán key cho cả 3 nhà cung cấp, khi bên nào hết tiền chỉ cần đổi ô “Nhà cung cấp đang dùng”.<br/>" +
    "Lấy key: OpenAI → platform.openai.com/api-keys · Claude → console.anthropic.com · Gemini → aistudio.google.com/apikey.<br/>" +
    "Key lưu trên máy bạn, chỉ gửi tới nhà cung cấp AI bạn chọn, không gửi đi đâu khác.";

  sb.append(provF, status, keyF, modelF, testBtn, testMsg, help);
  s.append(sh, sb);

  // ----- Soạn tin bằng AI -----
  const c = el("div", "block");
  const chh = el("div", "block-head static");
  chh.innerHTML = `<span class="title">✍️ Soạn tin quảng cáo bằng AI</span>`;
  const cb = el("div", "block-body");
  cb.style.display = "block";

  const promptF = el("div", "field");
  promptF.innerHTML = `<label>Yêu cầu (mô tả bài cần viết)</label>`;
  const promptTa = el("textarea");
  promptTa.rows = 3;
  promptTa.placeholder = "vd: Viết bài bán váy dạ hội đỏ, sang trọng, kèm 3 emoji, có kêu gọi inbox chốt đơn";
  promptF.appendChild(promptTa);

  const genBtn = el("button", "btn primary", "🤖 AI viết");
  const resF = el("div", "field");
  resF.style.marginTop = "10px";
  resF.innerHTML = `<label>Kết quả</label>`;
  const resTa = el("textarea");
  resTa.rows = 8;
  resTa.placeholder = "Nội dung AI viết sẽ hiện ở đây…";
  resF.appendChild(resTa);
  const copyBtn = el("button", "btn ghost small", "📋 Sao chép");
  copyBtn.style.marginTop = "6px";
  copyBtn.addEventListener("click", () => navigator.clipboard.writeText(resTa.value || ""));

  genBtn.addEventListener("click", async () => {
    const r = resolvedFor(ai.provider);
    if (!r.apiKey) {
      resTa.value = "⚠️ Chưa nhập API key cho " + AI_LABEL[ai.provider] + " ở mục Cài đặt AI phía trên.";
      return;
    }
    genBtn.disabled = true;
    const old = genBtn.textContent;
    genBtn.textContent = "Đang viết…";
    try {
      resTa.value = await bridge.aiCompose(r, promptTa.value || "");
    } catch (e) {
      resTa.value = "❌ Lỗi: " + (e.message || String(e));
    } finally {
      genBtn.disabled = false;
      genBtn.textContent = old;
    }
  });

  cb.append(promptF, genBtn, resF, copyBtn);
  c.append(chh, cb);

  // ----- Khung chat với AI -----
  const ch = el("div", "block");
  const chHead = el("div", "block-head static");
  chHead.innerHTML = `<span class="title">💬 Chat với AI (hỏi đáp, hướng dẫn, nhờ sửa nội dung)</span>`;
  const chBody = el("div", "block-body");
  chBody.style.display = "block";

  const chatLog = el("div", "chat-log");
  const renderChat = () => {
    chatLog.innerHTML = "";
    if (!aiChatHistory.length) {
      chatLog.appendChild(el("div", "mini", "Gõ tin bên dưới để trò chuyện với AI. Ví dụ: “Sửa giúp tin này cho hay hơn: …”, “Cách đặt quy tắc đổi giá?”, “Viết lại đoạn này ngắn gọn”."));
    }
    for (const m of aiChatHistory) {
      const b = el("div", "chat-msg " + (m.role === "user" ? "me" : "ai"));
      b.textContent = m.content;
      chatLog.appendChild(b);
    }
    chatLog.scrollTop = chatLog.scrollHeight;
  };
  renderChat();

  const chatRow = el("div", "chat-row");
  const chatIn = el("textarea");
  chatIn.rows = 2;
  chatIn.placeholder = "Nhập tin nhắn cho AI… (Enter để gửi, Shift+Enter xuống dòng)";
  const chatSend = el("button", "btn primary", "Gửi");
  const chatClear = el("button", "btn ghost small", "🗑 Xoá hội thoại");
  chatClear.addEventListener("click", () => {
    aiChatHistory = [];
    renderChat();
  });

  const doSend = async () => {
    const text = (chatIn.value || "").trim();
    if (!text) return;
    const r = resolvedFor(ai.provider);
    if (!r.apiKey) {
      aiChatHistory.push({ role: "assistant", content: "⚠️ Chưa nhập API key cho " + AI_LABEL[ai.provider] + " ở mục Cài đặt AI phía trên." });
      renderChat();
      return;
    }
    aiChatHistory.push({ role: "user", content: text });
    chatIn.value = "";
    renderChat();
    chatSend.disabled = true;
    const thinking = { role: "assistant", content: "…" };
    aiChatHistory.push(thinking);
    renderChat();
    try {
      const reply = await bridge.aiChat(r, aiChatHistory.filter((m) => m !== thinking));
      thinking.content = reply || "(không có phản hồi)";
    } catch (e) {
      thinking.content = "❌ Lỗi: " + (e.message || String(e));
    } finally {
      chatSend.disabled = false;
      renderChat();
    }
  };
  chatSend.addEventListener("click", doSend);
  chatIn.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  });
  chatRow.append(chatIn, chatSend);
  chBody.append(chatLog, chatRow, chatClear);
  ch.append(chHead, chBody);

  wrap.append(s, c, ch);
}

// ================= GỬI HÀNG LOẠT (nhóm mình quản trị / bạn bè) =================
const sendState = {
  group: { selected: new Set(), images: [] },
  user: { selected: new Set(), images: [] },
};
let activeSend = null; // { progressId, btnId, sendLabel } của panel đang gửi

function bcProgress(e) {
  const box = activeSend ? document.getElementById(activeSend.progressId) : null;
  if (!box) return;
  const line = el("div", "l");
  const t = new Date().toLocaleTimeString("vi-VN");
  const icon = e.ok ? '<span class="ok">✅</span>' : '<span class="error">❌</span>';
  line.innerHTML = `<span class="t">[${t}]</span> ${icon} ${esc(e.name || e.id)} (${e.index + 1}/${e.total})` + (e.error ? ` - ${esc(e.error)}` : "");
  box.appendChild(line);
  box.scrollTop = box.scrollHeight;
}
function bcDone(e) {
  if (!activeSend) return;
  const box = document.getElementById(activeSend.progressId);
  if (box) {
    const line = el("div", "l");
    line.innerHTML = `<b>🎉 Xong: ${e.sent}/${e.total}.</b>`;
    box.appendChild(line);
    box.scrollTop = box.scrollHeight;
  }
  const btn = document.getElementById(activeSend.btnId);
  if (btn) {
    btn.disabled = false;
    btn.textContent = activeSend.sendLabel;
  }
}

// Bộ máy gửi dùng chung cho cả "Đăng nhóm" (kind=group) và "Nhắn bạn bè" (kind=user).
function renderSendPanel(cfg) {
  const wrap = $("#" + cfg.bodyId);
  if (!wrap) return;
  wrap.innerHTML = "";
  if (!accounts.length) {
    wrap.appendChild(el("div", "empty", "Chưa có tài khoản. Vào tab Tài khoản đăng nhập trước đã."));
    return;
  }
  const st = sendState[cfg.kind];
  const P = cfg.idPrefix;
  const W = cfg.itemWord;

  const accF = el("div", "field");
  accF.innerHTML = `<label>Tài khoản gửi</label>`;
  const accSel = el("select");
  accSel.innerHTML = accounts.map((a) => `<option value="${esc(a.name)}">${esc(a.name)}</option>`).join("");
  accF.appendChild(accSel);

  // Danh sách đích (checklist)
  const gWrap = el("div", "block");
  const gHead = el("div", "block-head static");
  gHead.innerHTML = `<span class="title">1) ${esc(cfg.selTitle)}</span>`;
  const gBody = el("div", "block-body");
  gBody.style.display = "block";

  const toolbar = el("div", "picker-toolbar");
  const searchIn = el("input");
  searchIn.type = "text";
  searchIn.placeholder = cfg.searchPh;
  searchIn.style.flex = "1";
  const rescanBtn = el("button", "btn small", "↻ Quét lại");
  toolbar.append(searchIn, rescanBtn);

  const bar = el("div", "picker-bar");
  const selAllWrap = el("label", "check");
  selAllWrap.style.gap = "8px";
  selAllWrap.innerHTML = `<input type="checkbox" id="${P}-selall"/> <span>Chọn tất cả (đang lọc)</span>`;
  const cacheInfo = el("span", "mini");
  bar.append(selAllWrap, cacheInfo);

  const listBox = el("div", "picker-list");
  const countEl = el("div", "mini");
  countEl.style.margin = "6px 0";

  let items = [];
  const filterItems = () => {
    const q = (searchIn.value || "").toLowerCase().trim();
    return items.filter((g) => !q || (g.name || "").toLowerCase().includes(q) || String(g.id).includes(q));
  };
  const updateCount = () => (countEl.textContent = `Đã chọn ${st.selected.size} ${W}`);
  const drawList = () => {
    const filtered = filterItems();
    listBox.innerHTML = "";
    if (!filtered.length) {
      listBox.appendChild(el("div", "mini", `Không có ${W} nào.`));
      return;
    }
    for (const g of filtered) {
      const row = el("label", "picker-item");
      row.style.cursor = "pointer";
      const checked = st.selected.has(g.id) ? "checked" : "";
      const meta = cfg.showMembers ? `<span class="mini">${g.totalMember || 0} tv</span>` : "";
      row.innerHTML = `<input type="checkbox" ${checked}/> <span style="flex:1">${esc(g.name)}</span>${meta}`;
      row.querySelector("input").addEventListener("change", (ev) => {
        if (ev.target.checked) st.selected.add(g.id);
        else st.selected.delete(g.id);
        updateCount();
      });
      listBox.appendChild(row);
    }
  };
  const loadItems = async (refresh) => {
    cacheInfo.textContent = "Đang tải…";
    try {
      const res = await cfg.listFn(accSel.value, !!refresh);
      items = res.items || [];
      cacheInfo.textContent = res.fromCache ? `Dùng danh sách đã lưu (${items.length} ${W})` : `Đã quét ${items.length} ${W}`;
    } catch (e) {
      cacheInfo.textContent = "Lỗi tải: " + (e.message || e);
      items = [];
    }
    drawList();
    updateCount();
  };
  searchIn.addEventListener("input", drawList);
  rescanBtn.addEventListener("click", () => loadItems(true));
  selAllWrap.querySelector("input").addEventListener("change", (ev) => {
    for (const g of filterItems()) {
      if (ev.target.checked) st.selected.add(g.id);
      else st.selected.delete(g.id);
    }
    drawList();
    updateCount();
  });
  accSel.addEventListener("change", () => {
    st.selected = new Set();
    loadItems(false);
  });

  gBody.append(toolbar, bar, listBox, countEl);
  gWrap.append(gHead, gBody);

  // Nội dung
  const cWrap = el("div", "block");
  const cHead = el("div", "block-head static");
  cHead.innerHTML = `<span class="title">2) Nội dung</span>`;
  const cBody = el("div", "block-body");
  cBody.style.display = "block";

  const contentF = el("div", "field");
  contentF.innerHTML = `<label>${esc(cfg.contentLabel)}</label>`;
  const contentTa = el("textarea");
  contentTa.rows = 6;
  contentTa.placeholder = "Nhập nội dung…";
  contentF.appendChild(contentTa);

  // Ảnh
  const imgRow = el("div", "row-inline");
  const pickImgBtn = el("button", "btn small", "🖼 Chọn ảnh");
  const imgInfo = el("span", "mini");
  const clearImgBtn = el("button", "btn small ghost", "Xoá ảnh");
  const refreshImgInfo = () => (imgInfo.textContent = st.images.length ? `${st.images.length} ảnh đã chọn` : "Chưa chọn ảnh (không bắt buộc)");
  refreshImgInfo();
  pickImgBtn.addEventListener("click", async () => {
    const files = await bridge.pickImages();
    if (files && files.length) st.images = files;
    refreshImgInfo();
  });
  clearImgBtn.addEventListener("click", () => {
    st.images = [];
    refreshImgInfo();
  });
  imgRow.append(pickImgBtn, clearImgBtn, imgInfo);

  // AI đổi nhẹ text
  const aiVaryWrap = el("label", "check ai-toggle");
  const useAiDefault = config.ai && config.ai.provider ? AI_LABEL[config.ai.provider] : "AI";
  aiVaryWrap.innerHTML = `<input type="checkbox" id="${P}-aivary"/> 🤖 Dùng AI đổi nhẹ câu chữ cho mỗi ${W} (dùng ${esc(useAiDefault)})`;
  const aiVaryNote = el("div", "mini ai-note", `Giúp tin gửi tới mỗi ${W} không giống hệt nhau - tự nhiên hơn, đỡ bị coi là spam. Giữ nguyên giá/link/emoji.`);

  // Chống spam: độ trễ
  const delayGrid = el("div", "grid2");
  const dMin = numField("Giãn cách tối thiểu (ms)", cfg.kind === "user" ? 6000 : 4000, () => {});
  const dMax = numField("Giãn cách tối đa (ms)", cfg.kind === "user" ? 15000 : 9000, () => {});
  delayGrid.append(dMin, dMax);
  const delayNote = el("div", "mini", `Gửi lần lượt từng ${W}, nghỉ ngẫu nhiên để an toàn` + (cfg.kind === "user" ? " (nhắn người nên để giãn 6000–15000ms cho an toàn)." : " (khuyên 4000–9000ms)."));

  cBody.append(contentF, imgRow, aiVaryWrap, aiVaryNote, delayGrid, delayNote);
  cWrap.append(cHead, cBody);

  // Nút gửi + tiến trình
  const sendBtn = el("button", "btn primary", cfg.sendLabel);
  sendBtn.id = P + "-send";
  sendBtn.style.marginTop = "6px";
  const progWrap = el("div", "block");
  const progHead = el("div", "block-head static");
  progHead.innerHTML = `<span class="title">3) Tiến trình</span>`;
  const progBody = el("div", "block-body");
  progBody.style.display = "block";
  const progBox = el("div", "log");
  progBox.id = P + "-progress";
  progBox.style.height = "220px";
  progBody.appendChild(progBox);
  progWrap.append(progHead, progBody);

  sendBtn.addEventListener("click", async () => {
    const text = (contentTa.value || "").trim();
    if (!text && !st.images.length) {
      alert("Nhập nội dung hoặc chọn ảnh trước đã.");
      return;
    }
    if (st.selected.size === 0) {
      alert(`Chưa chọn ${W} nào.`);
      return;
    }
    const byId = new Map(items.map((g) => [g.id, g.name]));
    const targets = Array.from(st.selected).map((id) => ({ id, name: byId.get(id) || id }));
    const aiVary = document.getElementById(P + "-aivary").checked;
    const opts = {
      kind: cfg.kind,
      targets,
      text,
      images: st.images.slice(),
      aiVary,
      ai: aiVary ? resolvedFor(config.ai.provider) : null,
      minDelayMs: parseInt(dMin.querySelector("input").value, 10) || (cfg.kind === "user" ? 6000 : 4000),
      maxDelayMs: parseInt(dMax.querySelector("input").value, 10) || (cfg.kind === "user" ? 15000 : 9000),
    };
    if (aiVary && (!opts.ai || !opts.ai.apiKey)) {
      alert("Đã bật AI đổi text nhưng chưa có API key cho " + AI_LABEL[config.ai.provider] + ". Vào tab AI nhập key, hoặc tắt tuỳ chọn này.");
      return;
    }
    progBox.innerHTML = "";
    activeSend = { progressId: P + "-progress", btnId: P + "-send", sendLabel: cfg.sendLabel };
    sendBtn.disabled = true;
    sendBtn.textContent = "Đang gửi…";
    try {
      await bridge.broadcastSend(accSel.value, opts);
    } catch (e) {
      bcProgress({ ok: false, name: "LỖI", id: "", index: 0, total: targets.length, error: e.message || String(e) });
      sendBtn.disabled = false;
      sendBtn.textContent = cfg.sendLabel;
    }
  });

  wrap.append(accF, gWrap, cWrap, sendBtn, progWrap);
  loadItems(false);
}

function renderBroadcastPanel() {
  renderSendPanel({
    bodyId: "broadcast-body",
    kind: "group",
    idPrefix: "bc",
    itemWord: "nhóm",
    listFn: (a, r) => bridge.listGroups(a, r),
    selTitle: "Chọn nhóm đích (mình là quản trị/thành viên)",
    contentLabel: "Nội dung (đăng cùng nội dung này tới các nhóm đã chọn)",
    searchPh: "🔎 Tìm nhóm theo tên…",
    sendLabel: "📢 Đăng ngay",
    showMembers: true,
  });
}

function renderFriendsPanel() {
  renderSendPanel({
    bodyId: "friends-body",
    kind: "user",
    idPrefix: "fr",
    itemWord: "người",
    listFn: (a, r) => bridge.listFriends(a, r),
    selTitle: "Chọn bạn bè / khách nhận tin",
    contentLabel: "Nội dung tin nhắn (gửi tới từng người đã chọn)",
    searchPh: "🔎 Tìm theo tên…",
    sendLabel: "💬 Gửi ngay",
    showMembers: false,
  });
}

// Field helpers
function numField(label, val, onChange, allowFloat) {
  const f = el("div", "field");
  f.innerHTML = `<label>${esc(label)}</label>`;
  const inp = el("input");
  inp.type = "number";
  if (allowFloat) inp.step = "0.01";
  inp.value = val;
  inp.addEventListener("change", (e) => onChange(allowFloat ? parseFloat(e.target.value) || 0 : parseInt(e.target.value, 10) || 0));
  f.appendChild(inp);
  return f;
}
function textField(label, val, onChange) {
  const f = el("div", "field");
  f.innerHTML = `<label>${esc(label)}</label>`;
  const inp = el("input");
  inp.type = "text";
  inp.value = val;
  inp.addEventListener("input", (e) => onChange(e.target.value));
  f.appendChild(inp);
  return f;
}
function textAreaField(label, val, onChange) {
  const f = el("div", "field");
  f.innerHTML = `<label>${esc(label)}</label>`;
  const ta = el("textarea");
  ta.value = val;
  ta.addEventListener("input", (e) => onChange(e.target.value));
  f.appendChild(ta);
  return f;
}
function mapEditor(mapObj, kLabel, vLabel) {
  const box = el("div");
  const render = () => {
    box.innerHTML = "";
    for (const key of Object.keys(mapObj)) {
      const row = el("div", "kv-row");
      const k = el("input");
      k.type = "text";
      k.placeholder = kLabel;
      k.value = key;
      const v = el("input");
      v.type = "text";
      v.placeholder = vLabel;
      v.value = mapObj[key];
      k.addEventListener("change", (e) => {
        const nk = e.target.value;
        if (nk === key) return;
        const val = mapObj[key];
        delete mapObj[key];
        mapObj[nk] = val;
        render();
      });
      v.addEventListener("input", (e) => (mapObj[key] = e.target.value));
      const rm = el("button", "btn small danger", "✕");
      rm.addEventListener("click", () => {
        delete mapObj[key];
        render();
      });
      row.append(k, v, rm);
      box.appendChild(row);
    }
    const add = el("button", "btn small ghost", "＋ Thêm cặp");
    add.addEventListener("click", () => {
      let base = "";
      let i = 1;
      let nk = "mới " + i;
      while (mapObj[nk]) nk = "mới " + ++i;
      mapObj[nk] = "";
      render();
    });
    box.appendChild(add);
  };
  render();
  return box;
}

// ================= DANH SÁCH NHÓM / NGƯỜI (bảng, có lưu) =================
let pickerData = [];
let pickerSelected = new Set();
let pickerKind = "group";
let pickerAccount = ""; // tài khoản dùng để quét trong bảng chọn (theo kịch bản đang mở)

function fmtAgo(ts) {
  if (!ts) return "";
  const m = Math.floor((Date.now() - ts) / 60000);
  if (m < 1) return "vừa quét";
  if (m < 60) return `quét ${m} phút trước`;
  const h = Math.floor(m / 60);
  if (h < 24) return `quét ${h} giờ trước`;
  return `quét ${Math.floor(h / 24)} ngày trước`;
}

async function loadPickerData(refresh) {
  $("#picker-list").innerHTML = `<div class="empty">${
    refresh ? "Đang quét lại từ Zalo…" : "Đang tải…"
  } (lần đầu/quét lại có thể hơi lâu)</div>`;
  $("#picker-cacheinfo").textContent = "";
  try {
    const res =
      pickerKind === "group"
        ? await bridge.listGroups(pickerAccount, refresh)
        : await bridge.listFriends(pickerAccount, refresh);
    pickerData = (res && res.items) || [];
    for (const it of pickerData) nameCache[it.id] = it.name;
    $("#picker-cacheinfo").textContent = `${pickerData.length} mục · ${
      res && res.fromCache ? "từ bộ nhớ (" + fmtAgo(res.cachedAt) + ")" : "vừa quét mới"
    }`;
  } catch (e) {
    pickerData = [];
    $("#picker-list").innerHTML = `<div class="empty">Lỗi tải: ${esc(
      e.message
    )}<br/>Hãy chắc chắn tài khoản đã kết nối (tab Tài khoản).</div>`;
    return;
  }
  renderPicker($("#picker-search").value);
}

async function openPicker(kind, title, account) {
  // Tài khoản để quét: chỉ chấp nhận tài khoản CÒN TỒN TẠI (tránh tên cũ đã đăng xuất).
  const names = accounts.map((a) => a.name);
  let acct = account && names.includes(account) ? account : "";
  if (!acct && config.account && names.includes(config.account)) acct = config.account;
  if (!acct) acct = (accounts.find((a) => a.connected) || accounts[0] || {}).name || "";
  if (!acct) {
    alert("Chưa có tài khoản. Vào tab Tài khoản đăng nhập trước đã.");
    return null;
  }
  pickerAccount = acct;
  pickerKind = kind;
  pickerSelected = new Set();
  $("#picker-title").textContent = title;
  $("#picker-search").value = "";
  $("#picker-selectall").checked = false;
  const roleSel = $("#picker-role");
  if (roleSel) {
    roleSel.value = "all";
    roleSel.style.display = kind === "group" ? "" : "none"; // vai trò chỉ có ở nhóm
  }
  $("#modal-picker").classList.add("show");

  await loadPickerData(false); // dùng bộ nhớ nếu có

  return new Promise((resolve) => {
    const close = (val) => {
      $("#modal-picker").classList.remove("show");
      resolve(val);
    };
    $("#picker-confirm").onclick = () => close(pickerData.filter((d) => pickerSelected.has(d.id)));
    $$("#modal-picker [data-close-modal]").forEach((b) => (b.onclick = () => close(null)));
    $("#picker-rescan").onclick = () => loadPickerData(true);
  });
}

// Lọc theo tìm kiếm + vai trò (trưởng/phó nhóm). Vai trò chỉ áp dụng khi chọn NHÓM.
function pickerFiltered(q) {
  const ql = (q || "").toLowerCase();
  const roleSel = $("#picker-role");
  const role = pickerKind === "group" && roleSel ? roleSel.value : "all";
  return pickerData.filter((d) => {
    if (ql && !(String(d.name).toLowerCase().includes(ql) || String(d.id).includes(ql))) return false;
    if (role === "owner") return d.role === "owner";
    if (role === "admin") return d.role === "admin";
    if (role === "manage") return d.role === "owner" || d.role === "admin";
    return true;
  });
}

$("#picker-search").addEventListener("input", (e) => renderPicker(e.target.value));
if ($("#picker-role")) $("#picker-role").addEventListener("change", () => renderPicker($("#picker-search").value));
$("#picker-selectall").addEventListener("change", (e) => {
  for (const it of pickerFiltered($("#picker-search").value)) {
    if (e.target.checked) pickerSelected.add(it.id);
    else pickerSelected.delete(it.id);
  }
  renderPicker($("#picker-search").value);
});

function updatePickerCount() {
  $("#picker-count").textContent = pickerSelected.size ? `Đã chọn ${pickerSelected.size}` : "";
}

function roleBadge(role) {
  if (role === "owner") return ` <span class="role-badge owner">👑 Trưởng nhóm</span>`;
  if (role === "admin") return ` <span class="role-badge admin">⭐ Phó nhóm</span>`;
  return "";
}

function renderPicker(q) {
  const list = $("#picker-list");
  list.innerHTML = "";
  const items = pickerFiltered(q);
  updatePickerCount();
  if (items.length === 0) {
    list.appendChild(el("div", "empty", "Không có kết quả."));
    return;
  }
  for (const it of items) {
    const row = el("div", "picker-item");
    const cb = el("input");
    cb.type = "checkbox";
    cb.checked = pickerSelected.has(it.id);
    cb.addEventListener("change", () => {
      if (cb.checked) pickerSelected.add(it.id);
      else pickerSelected.delete(it.id);
      updatePickerCount();
    });
    const nm = el("div", "pi-name");
    nm.innerHTML = `<div><b>${esc(it.name)}</b>${pickerKind === "group" ? roleBadge(it.role) : ""}</div><div class="pi-id">ID: ${esc(it.id)}${
      it.totalMember ? " · 👥 " + it.totalMember + " thành viên" : ""
    }</div>`;
    row.append(cb, nm);

    if (pickerKind === "group") {
      const linkBtn = el("button", "btn small ghost", "🔗 Link");
      linkBtn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        linkBtn.disabled = true;
        linkBtn.textContent = "…";
        try {
          const r = await bridge.getGroupLink(pickerAccount || config.account, it.id);
          if (r.ok && r.link) {
            navigator.clipboard.writeText(r.link);
            linkBtn.textContent = "✓ Đã copy link";
          } else {
            linkBtn.textContent = "Không có link";
          }
        } catch (_e) {
          linkBtn.textContent = "Lỗi";
        }
        setTimeout(() => {
          linkBtn.textContent = "🔗 Link";
          linkBtn.disabled = false;
        }, 2500);
      });
      row.append(linkBtn);
    }

    row.addEventListener("click", (ev) => {
      if (ev.target === cb || ev.target.tagName === "BUTTON") return;
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event("change"));
    });
    list.appendChild(row);
  }
}

// ================= CHẠY (đa tài khoản) =================
let runningAccounts = new Set();
let pausedAccounts = new Set();
let statsByAccount = {}; // account -> {hour, day}

function accountsWithRoutes() {
  const map = {}; // account -> [routes]
  config.routes.forEach((r, idx) => {
    const acc = r.account || config.account;
    if (!acc) return;
    (map[acc] = map[acc] || []).push({ r, idx });
  });
  return map;
}

function renderRunPanel() {
  // Cài đặt gửi
  const s = config.sending || {};
  $("#s-mindelay").value = s.minDelayMs != null ? s.minDelayMs : 3000;
  $("#s-maxdelay").value = s.maxDelayMs != null ? s.maxDelayMs : 7000;
  $("#s-perhour").value = s.maxPerHour != null ? s.maxPerHour : 0;
  $("#s-perday").value = s.maxPerDay != null ? s.maxPerDay : 0;

  renderRunAccounts();
}

function renderRunAccounts() {
  const wrap = $("#run-accounts");
  wrap.innerHTML = "";
  const map = accountsWithRoutes();
  const accs = Object.keys(map);
  if (accs.length === 0) {
    wrap.appendChild(el("div", "empty", T("run.noRoutes")));
    return;
  }
  for (const acc of accs) {
    const running = runningAccounts.has(acc);
    const paused = pausedAccounts.has(acc);
    const st = statsByAccount[acc] || { hour: 0, day: 0 };
    const block = el("div", "block");
    const head = el("div", "block-head");
    const stateTxt = !running ? "⚪ " + T("run.stopped") : paused ? "⏸️ Tạm dừng" : "🟢 " + T("run.running");
    head.innerHTML = `
      <span class="dot ${running ? (paused ? "off" : "on") : "off"}"></span>
      <span class="title">👤 ${esc(acc)}</span>
      <span class="mini" data-stats>${stateTxt} · ${T("run.sent")}: ${st.hour}/h, ${st.day}/d</span>`;

    // Nút Tạm dừng / Tiếp tục (chỉ khi đang chạy)
    if (running) {
      const bPause = el("button", "btn small", paused ? "▶ Tiếp tục" : "⏸ Tạm dừng");
      bPause.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        bPause.disabled = true;
        try {
          if (paused) await bridge.resumeAccount(acc);
          else await bridge.pauseAccount(acc);
        } catch (e) {
          toast("Lỗi: " + e.message);
        }
        bPause.disabled = false;
      });
      head.appendChild(bPause);
    }

    const btn = el("button", "btn small " + (running ? "danger" : "success"), running ? T("run.stop") : T("run.start"));
    btn.addEventListener("click", async (ev) => {
      ev.stopPropagation();
      btn.disabled = true;
      try {
        if (running) {
          await bridge.stopAccount(acc);
        } else {
          await saveConfig();
          await bridge.startAccount(config, acc);
        }
      } catch (e) {
        toast("Lỗi: " + e.message);
      }
      btn.disabled = false;
    });
    head.appendChild(btn);

    const body = el("div", "block-body");
    // Danh sách tuyến của tài khoản này, có công tắc bật/tắt
    for (const { r, idx } of map[acc]) {
      const row = el("div", "kv-row");
      const sw = el("label", "check");
      sw.innerHTML = `<input type="checkbox" ${r.enabled !== false ? "checked" : ""}/> <b>${esc(
        r.name || "Kịch bản"
      )}</b>`;
      sw.querySelector("input").addEventListener("change", async (e) => {
        r.enabled = e.target.checked;
        await saveConfig();
        renderRoutesPanel();
        head.querySelector(".mini[data-stats]");
      });
      const info = el("div", "mini");
      info.style.flex = "1";
      info.textContent = `${(r.sources || []).length} nguồn → ${(r.destinations || []).length} đích · bộ: ${
        r.ruleSet || "(không)"
      }`;
      row.append(sw, info);
      body.appendChild(row);
    }

    // Ghi đè giới hạn riêng cho tài khoản (tuỳ chọn)
    const ov = (config.accountOverrides && config.accountOverrides[acc]) || {};
    const ovWrap = el("div");
    ovWrap.innerHTML = `<div class="subhead">Giới hạn riêng cho “${esc(acc)}” (để trống = dùng cài đặt chung)</div>`;
    const g = el("div", "grid2");
    const mkOv = (key, label) => {
      const f = el("div", "field");
      f.innerHTML = `<label>${label}</label>`;
      const inp = el("input");
      inp.type = "number";
      inp.value = ov[key] != null ? ov[key] : "";
      inp.placeholder = "(chung)";
      inp.addEventListener("change", async (e) => {
        if (!config.accountOverrides) config.accountOverrides = {};
        if (!config.accountOverrides[acc]) config.accountOverrides[acc] = {};
        const v = e.target.value.trim();
        if (v === "") delete config.accountOverrides[acc][key];
        else config.accountOverrides[acc][key] = parseInt(v, 10) || 0;
        await saveConfig();
      });
      f.appendChild(inp);
      return f;
    };
    g.append(
      mkOv("minDelayMs", "Trễ tối thiểu (ms)"),
      mkOv("maxDelayMs", "Trễ tối đa (ms)"),
      mkOv("maxPerHour", "Tin / giờ"),
      mkOv("maxPerDay", "Tin / ngày")
    );
    ovWrap.appendChild(g);
    body.appendChild(ovWrap);

    head.addEventListener("click", (e) => {
      if (e.target.tagName === "BUTTON" || e.target.tagName === "INPUT") return;
      body.style.display = body.style.display === "none" ? "block" : "none";
    });
    body.style.display = "none";
    block.append(head, body);
    wrap.appendChild(block);
  }
}

async function saveSending() {
  config.sending = {
    minDelayMs: parseInt($("#s-mindelay").value, 10) || 0,
    maxDelayMs: parseInt($("#s-maxdelay").value, 10) || 0,
    maxPerHour: parseInt($("#s-perhour").value, 10) || 0,
    maxPerDay: parseInt($("#s-perday").value, 10) || 0,
  };
  await saveConfig();
  toast("Đã lưu cài đặt gửi.");
}

async function startAll() {
  const map = accountsWithRoutes();
  if (Object.keys(map).length === 0) {
    alert("Chưa có tuyến nào để chạy.");
    return;
  }
  await saveConfig();
  try {
    const res = await bridge.startAll(config);
    if (res && res.started && res.started.length) toast("Đã chạy: " + res.started.join(", "));
    if (res && res.errors && res.errors.length) toast("Lỗi: " + res.errors.join("; "));
  } catch (e) {
    toast("Lỗi bắt đầu: " + e.message);
  }
}

async function stopAll() {
  await bridge.stopAll();
}

function applyStatus(st) {
  runningAccounts = new Set((st && st.running) || []);
  pausedAccounts = new Set(
    st && st.paused ? Object.keys(st.paused).filter((a) => st.paused[a]) : []
  );
  if (st && st.counts) statsByAccount = Object.assign(statsByAccount, st.counts);
  renderRunAccounts();
}

// ================= SỰ KIỆN TỪ MAIN =================
function registerEvents() {
  bridge.onLog((e) => logLine(e));
  bridge.onQR((e) => {
    if (!e.image) return;
    const src = String(e.image).startsWith("data:") ? e.image : "data:image/png;base64," + e.image;
    $("#qr-img").src = src;
  });
  bridge.onLoginStatus((e) => {
    const map = {
      qr: "📱 Quét mã QR bằng Zalo trên điện thoại…",
      scanned: "✅ Đã quét: " + (e.displayName || ""),
      expired: "⏳ QR hết hạn, đang tạo lại…",
      declined: "❌ Bạn đã từ chối trên điện thoại.",
      "got-info": "🔐 Đang hoàn tất đăng nhập…",
      "logged-in": "✅ Đăng nhập thành công!",
    };
    if ($("#modal-login").classList.contains("show")) $("#login-status").textContent = map[e.status] || e.message;
  });
  bridge.onForwardingStatus((st) => applyStatus(st));
  bridge.onStats((e) => {
    statsByAccount[e.account] = { hour: e.hour, day: e.day };
    renderRunAccounts();
  });
  bridge.onForwarded(() => {});
  bridge.onBroadcastProgress((e) => bcProgress(e));
  bridge.onBroadcastDone((e) => bcDone(e));
}

let logEntries = [];
function filteredLogs() {
  return window.ForwarderOperations.filter(logEntries, $("#log-level").value, $("#log-query").value);
}
function renderLog() {
  const log = $("#log");
  if (!log) return;
  const rows = filteredLogs();
  $("#log-count").textContent = `${rows.length}/${logEntries.length} dòng (tối đa 500 dòng gần đây trên màn hình)`;
  log.innerHTML = "";
  for (const e of rows) {
    const line = el("div", "l");
    const t = new Date(e.ts).toLocaleString("vi-VN");
    line.innerHTML = `<span class="t">[${t}]</span> <span class="${e.level}">${esc(e.msg)}</span>`;
    log.appendChild(line);
  }
}
function logLine(e) {
  if (!$("#log")) return;
  const level = ["info", "ok", "warn", "error"].includes(e.level) ? e.level : "info";
  logEntries.unshift({level, msg: String(e.msg || ""), ts: Number(e.ts) || Date.now()});
  logEntries = logEntries.slice(0, 500);
  renderLog();
}

window.__init = init;
