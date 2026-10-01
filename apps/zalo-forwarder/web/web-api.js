"use strict";
/* web-api.js - thay preload.js cua ban Electron (MinMin OS 26.10.4).
 *
 * renderer.js goi `window.api.<ham>(...)` y nhu ban desktop. O day moi ham thanh mot lan
 * POST api/rpc/<ham> toi MinMin (MinMin kiem tra dang nhap + ma kich hoat roi chuyen cho tien
 * trinh Zalo Forwarder chay nen). Su kien (log, QR, trang thai...) di qua EventSource api/events.
 * Hop thoai chon file cua Electron doi thanh o chon file / tai xuong cua trinh duyet.
 * Khong dung ky tu em dash. */
(function () {
  var BASE = "api/";
  var nghe = {};       // kenh -> [callback]
  var es = null;

  async function rpc(ten, args) {
    var r;
    try {
      r = await fetch(BASE + "rpc/" + ten, {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ args: args || [] }),
      });
    } catch (e) {
      throw new Error("Mat ket noi toi MinMin");
    }
    var d = null;
    try { d = await r.json(); } catch (e) {}
    if (r.status === 401) { location.href = "/"; throw new Error("Can dang nhap MinMin"); }
    if (!r.ok || !d || d.ok === false) {
      var loi = (d && (d.error || d.detail)) || ("HTTP " + r.status);
      throw new Error(typeof loi === "string" ? loi : JSON.stringify(loi));
    }
    return d.result;
  }
  function goi(ten) { return function () { return rpc(ten, Array.prototype.slice.call(arguments)); }; }
  function on(kenh) { return function (cb) { (nghe[kenh] = nghe[kenh] || []).push(cb); }; }
  function phat(kenh, data) { (nghe[kenh] || []).forEach(function (cb) { try { cb(data); } catch (e) { console.error(e); } }); }

  function moSuKien() {
    if (es) return;
    es = new EventSource(BASE + "events");
    ["log", "qr", "login-status", "forwarding-status", "forwarded", "stats", "broadcast-progress", "broadcast-done"]
      .forEach(function (k) {
        es.addEventListener(k, function (ev) { try { phat(k, JSON.parse(ev.data)); } catch (e) {} });
      });
    es.addEventListener("hello", function (ev) {
      try {
        var d = JSON.parse(ev.data);
        (d.log || []).forEach(function (l) { phat("log", l); });
        if (d.status) phat("forwarding-status", d.status);
      } catch (e) {}
    });
    es.onerror = function () { /* EventSource tu noi lai */ };
  }

  function chonFile(accept, nhieu) {
    return new Promise(function (resolve) {
      var o = document.createElement("input");
      o.type = "file";
      o.accept = accept;
      o.multiple = !!nhieu;
      o.style.display = "none";
      var xong = false;
      o.addEventListener("change", function () { xong = true; resolve(Array.prototype.slice.call(o.files || [])); o.remove(); });
      o.addEventListener("cancel", function () { if (!xong) resolve([]); o.remove(); });
      document.body.appendChild(o);
      o.click();
    });
  }

  async function pickImages() {
    var files = await chonFile("image/jpeg,image/png,image/gif,image/webp", true);
    var out = [];
    for (var i = 0; i < files.length; i++) {
      var r = await fetch(BASE + "upload?ten=" + encodeURIComponent(files[i].name), {
        method: "POST", credentials: "same-origin", body: files[i],
      });
      var d = await r.json().catch(function () { return null; });
      if (!r.ok || !d || !d.ok) throw new Error((d && (d.error || d.detail)) || "Tai anh len that bai");
      out.push(d.path);
    }
    return out;
  }

  async function exportConfig() {
    var cfg = await rpc("loadConfig");
    var blob = new Blob([JSON.stringify(cfg, null, 2)], { type: "application/json" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "zalo-forwarder-backup.json";
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    return { ok: true };
  }

  async function importConfig() {
    var files = await chonFile("application/json,.json", false);
    if (!files.length) return { ok: false };
    try {
      var cfg = JSON.parse(await files[0].text());
      if (!cfg || typeof cfg !== "object" || Array.isArray(cfg)) throw new Error("File khong hop le");
      await rpc("saveConfig", [cfg]);
      return { ok: true, config: cfg };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  function loginQR(name) {
    var o = document.getElementById("login-proxy");
    var proxy = o && o.value.trim() ? o.value.trim() : null; // trong = giu proxy cu
    if (o) o.value = "";
    return rpc("loginQR", [name, proxy]);
  }

  var hopLe = async function () { return { status: "licensed", lifetime: true, machineId: "-", serverUrl: "" }; };

  window.api = {
    // Ban quyen do MinMin kiem (ma kich hoat o trang Ket noi ngoai), app khong tu hoi nua.
    licenseStatus: hopLe,
    licenseMachineId: async function () { return "-"; },
    licenseSetServer: hopLe,
    licenseActivate: async function () { return { ok: true }; },
    licenseClear: async function () { return {}; },

    loadConfig: goi("loadConfig"),
    saveConfig: goi("saveConfig"),
    openUserData: async function () { return false; },

    listAccounts: goi("listAccounts"),
    loginQR: loginQR,
    connect: goi("connect"),
    deleteAccount: goi("deleteAccount"),
    setProxy: goi("setProxy"),

    listGroups: goi("listGroups"),
    listFriends: goi("listFriends"),
    getGroupLink: goi("getGroupLink"),
    sendTest: goi("sendTest"),

    startAll: goi("startAll"),
    startAccount: goi("startAccount"),
    stopAccount: goi("stopAccount"),
    pauseAccount: goi("pauseAccount"),
    resumeAccount: goi("resumeAccount"),
    stopAll: goi("stopAll"),
    forwardStatus: goi("forwardStatus"),

    aiTest: goi("aiTest"),
    aiCompose: goi("aiCompose"),
    aiListModels: goi("aiListModels"),
    aiChat: goi("aiChat"),

    exportConfig: exportConfig,
    importConfig: importConfig,
    previewRules: goi("previewRules"),

    broadcastSend: goi("broadcastSend"),
    pickImages: pickImages,
    onBroadcastProgress: on("broadcast-progress"),
    onBroadcastDone: on("broadcast-done"),

    onLog: on("log"),
    onQR: on("qr"),
    onLoginStatus: on("login-status"),
    onForwardingStatus: on("forwarding-status"),
    onForwarded: on("forwarded"),
    onStats: on("stats"),
  };

  // renderer.js chi gan window.__init; ban web goi no sau khi DOM san sang, roi moi mo luong
  // su kien (de cac ham onLog/onQR... da kip dang ky, khong mat log dau tien).
  async function boot() {
    if (window.__init) await window.__init();
    moSuKien();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else setTimeout(boot, 0);
})();
