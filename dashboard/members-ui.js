/* Quản lý thành viên được mời (admin). Nút nằm cạnh các nút brain; cửa sổ nổi. */
(function () {
  "use strict";
  var T = function (k) { return typeof window.t === "function" ? window.t(k) : k; };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var CSS = "background:var(--panel,#10192b);color:var(--fg,#e8eefc);border:1px solid rgba(120,160,255,.3);border-radius:14px;width:min(680px,100%);max-height:90vh;overflow:auto;padding:16px;display:flex;flex-direction:column;gap:10px";

  async function api(url, fd, method) {
    try {
      var r = await fetch(url, fd ? { method: method || "POST", body: fd } : undefined);
      var j = await r.json();
      return j;
    } catch (e) { return { ok: false, error: T("mem.net_err") }; }
  }

  function genPass() {
    var a = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789", out = "", b = new Uint32Array(14);
    crypto.getRandomValues(b);
    for (var i = 0; i < b.length; i++) out += a[b[i] % a.length];
    return out;
  }

  async function brainNames() {
    try {
      var d = await (await fetch("/brains")).json();
      return (d.brains || []).map(function (b) { return String(b.path || b.name || "").split(/[\\/]/).filter(Boolean).pop(); })
        .filter(Boolean);
    } catch (e) { return []; }
  }

  function roleSelect(cur) {
    return '<select>' + [["", "mem.none"], ["view", "mem.view"], ["edit", "mem.edit"]].map(function (o) {
      return '<option value="' + o[0] + '"' + (o[0] === (cur || "") ? " selected" : "") + ">" + esc(T(o[1])) + "</option>"; }).join("") + "</select>";
  }


  async function tenantPanel(box, m, msg, refresh) {
    if (box.style.display === "flex") { box.style.display = "none"; return; }
    box.style.display = "flex"; box.innerHTML = "...";
    var info = await api("/members/tenant/info?email=" + encodeURIComponent(m.email));
    if (!info || !info.ok) { box.textContent = (info && info.error) || T("mem.err"); return; }
    var h = '<div style="opacity:.8">' + esc(T("mem.tenant_explain")) + "</div>";
    if (m.tenant) h += "<div>" + esc(T("mem.tenant_status")) + ": " + esc(info.status) + " · " + esc(m.tenant) + '</div><button data-t="rm" type="button">' + esc(T("mem.tenant_remove")) + "</button>";
    else if (info.docker) h += '<button data-t="mk" type="button">' + esc(T("mem.tenant_create")) + "</button>";
    else h += "<div>" + esc(T("mem.tenant_nodocker")) + '</div><textarea readonly rows="4" style="width:100%;font-family:monospace;font-size:11px">' + esc(info.command) + '</textarea><input data-t="url" placeholder="' + esc(T("mem.tenant_url")) + '"><input data-t="pw" placeholder="' + esc(T("mem.tenant_pass")) + '"><button data-t="sv" type="button">' + esc(T("mem.tenant_save")) + "</button>";
    box.innerHTML = h;
    box.onclick = async function (e) {
      var k = e.target.getAttribute && e.target.getAttribute("data-t"); if (!k) return;
      var fd = new FormData(); fd.append("email", m.email); var r;
      if (k === "mk") { msg(T("mem.tenant_creating")); e.target.disabled = true; r = await api("/members/tenant/create", fd); if (r && r.ok) { msg(T(r.ready ? "mem.tenant_ready" : "mem.tenant_notready")); refresh(); return; } }
      else if (k === "sv") { fd.append("url", box.querySelector('[data-t="url"]').value.trim()); fd.append("password", box.querySelector('[data-t="pw"]').value); r = await api("/members/tenant/set", fd); }
      else if (k === "rm") { fd.append("delete_data", confirm(T("mem.tenant_remove_ask")) ? "1" : ""); r = await api("/members/tenant/remove", fd); }
      msg(r && r.ok ? T("mem.done") : ((r && r.error) || T("mem.err")));
      if (r && r.ok) refresh();
    };
  }

  async function open() {
    var ov = document.createElement("div");
    ov.style.cssText = "position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;padding:16px";
    ov.innerHTML = '<div style="' + CSS + '"><b>' + esc(T("mem.title")) + '</b>' +
      '<div style="font-size:12px;opacity:.75">' + esc(T("mem.note")) + '</div>' +
      '<div id="mmList" style="display:flex;flex-direction:column;gap:8px"></div>' +
      '<hr style="border:0;border-top:1px solid rgba(120,160,255,.2);width:100%">' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
      '<input id="mmEmail" type="email" autocomplete="off" style="flex:1;min-width:180px" placeholder="' + esc(T("mem.email")) + '">' +
      '<input id="mmName" autocomplete="off" style="flex:1;min-width:120px" placeholder="' + esc(T("mem.name")) + '"></div>' +
      '<div style="display:flex;gap:8px"><input id="mmPass" autocomplete="new-password" style="flex:1" placeholder="' + esc(T("mem.pass")) + '"><button id="mmGen" type="button">' + esc(T("mem.gen")) + '</button></div>' +
      '<div id="mmGrants" style="display:flex;flex-direction:column;gap:4px"></div>' +
      '<div id="mmMsg" style="font-size:12px;min-height:16px"></div>' +
      '<div style="display:flex;gap:8px;justify-content:flex-end"><button id="mmClose" type="button">' + esc(T("mem.close")) + '</button><button id="mmCreate" type="button">' + esc(T("mem.create")) + '</button></div></div>';
    document.body.appendChild(ov);
    var $ = function (i) { return ov.querySelector("#" + i); };
    var names = await brainNames();
    var msg = function (t) { $("mmMsg").textContent = t; };
    $("mmClose").addEventListener("click", function () { ov.remove(); });
    ov.addEventListener("click", function (e) { if (e.target === ov) ov.remove(); });
    $("mmGen").addEventListener("click", function () { var p = genPass(); $("mmPass").value = p; $("mmPass").type = "text"; });

    function grantRows(host, cur) {
      host.innerHTML = names.length ? names.map(function (n) {
        return '<label style="display:flex;gap:8px;align-items:center;justify-content:space-between" data-brain="' + esc(n) + '"><span>' + esc(n) + "</span>" + roleSelect(cur && cur[n]) + "</label>";
      }).join("") : "<i>" + esc(T("mem.no_brain")) + "</i>";
    }
    function readGrants(host) {
      var g = {};
      host.querySelectorAll("label[data-brain]").forEach(function (l) {
        var v = l.querySelector("select").value; if (v) g[l.getAttribute("data-brain")] = v; });
      return g;
    }
    grantRows($("mmGrants"), {});

    async function refresh() {
      var j = await api("/members");
      var host = $("mmList");
      var arr = (j && j.members) || [];
      if (!arr.length) { host.innerHTML = "<i>" + esc(T("mem.empty")) + "</i>"; return; }
      host.innerHTML = "";
      arr.forEach(function (m) {
        var card = document.createElement("div");
        card.style.cssText = "border:1px solid rgba(120,160,255,.2);border-radius:10px;padding:8px;display:flex;flex-direction:column;gap:6px";
        card.innerHTML = '<div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><b>' + esc(m.name || m.email) + '</b><span style="font-size:12px;opacity:.8">' + esc(m.email) + " · " + esc(T(m.tfa ? "mem.tfa_on" : "mem.tfa_off")) + (m.disabled ? " · " + esc(T("mem.disabled")) : "") + '</span></div>' +
          '<div class="g" style="display:flex;flex-direction:column;gap:4px"></div>' +
          '<div class="tn" style="display:none;flex-direction:column;gap:6px;font-size:12px"></div><div style="display:flex;gap:6px;flex-wrap:wrap"><button data-a="save" type="button">' + esc(T("mem.save")) + '</button><button data-a="lock" type="button">' + esc(T(m.disabled ? "mem.unlock" : "mem.lock")) + '</button><button data-a="pw" type="button">' + esc(T("mem.newpass")) + '</button><button data-a="tenant" type="button">' + esc(T(m.tenant ? "mem.tenant_on" : "mem.tenant")) + '</button><button data-a="r2" type="button">' + esc(T("mem.reset2fa")) + '</button><button data-a="del" type="button">' + esc(T("mem.delete")) + "</button></div>";
        grantRows(card.querySelector(".g"), m.grants);
        card.addEventListener("click", async function (e) {
          var a = e.target.getAttribute && e.target.getAttribute("data-a"); if (!a) return;
          var fd = new FormData(); fd.append("email", m.email); var r;
          if (a === "tenant") { return tenantPanel(card.querySelector(".tn"), m, msg, refresh); }
          if (a === "save") { fd.append("grants", JSON.stringify(readGrants(card.querySelector(".g")))); r = await api("/members/update", fd); }
          else if (a === "lock") { fd.append("disabled", m.disabled ? "0" : "1"); r = await api("/members/update", fd); }
          else if (a === "pw") { var p = prompt(T("mem.newpass_ask")); if (!p) return; fd.append("password", p); r = await api("/members/update", fd); }
          else if (a === "r2") { if (!confirm(T("mem.confirm_reset"))) return; fd.append("reset_2fa", "1"); r = await api("/members/update", fd); }
          else if (a === "del") { if (!confirm(T("mem.confirm_delete"))) return; r = await api("/members/delete", fd); }
          msg(r && r.ok ? T("mem.done") : ((r && r.error) || T("mem.err")));
          if (r && r.ok) refresh();
        });
        host.appendChild(card);
      });
    }
    $("mmCreate").addEventListener("click", async function () {
      var pass = $("mmPass").value;
      var fd = new FormData();
      fd.append("email", $("mmEmail").value.trim()); fd.append("name", $("mmName").value.trim());
      fd.append("password", pass); fd.append("grants", JSON.stringify(readGrants($("mmGrants"))));
      var r = await api("/members", fd);
      if (r && r.ok) {
        msg(T("mem.created") + " " + $("mmEmail").value.trim() + " / " + pass);
        $("mmEmail").value = ""; $("mmName").value = ""; $("mmPass").value = "";
        grantRows($("mmGrants"), {}); refresh();
      } else msg((r && r.error) || T("mem.err"));
    });
    refresh();
  }

  function addButton() {
    try {
      var anchor = document.getElementById("delBrainBtn");
      if (!anchor || document.getElementById("memBtn")) return !!document.getElementById("memBtn");
      var b = document.createElement("button");
      b.className = "graph-folder-btn"; b.id = "memBtn"; b.type = "button"; b.title = T("mem.btn");
      b.innerHTML = '<i data-ic="users"></i>';
      b.addEventListener("click", open);
      anchor.parentNode.insertBefore(b, anchor);
      try { window.JavisIcons && window.JavisIcons.refresh && window.JavisIcons.refresh(); } catch (e) {}
      return true;
    } catch (e) { return false; }
  }
  var n = 0, iv = setInterval(function () { if (addButton() || ++n > 20) clearInterval(iv); }, 500);
})();
