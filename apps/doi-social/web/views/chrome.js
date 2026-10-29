/* Managed host Chromium: native window on desktop, interactive screen on VPS. */
(function () {
  "use strict";
  var esc = DS.esc;
  DS.view("chrome", { title: "Chrome MinMin", render: function (el, ctx) {
    var selected = "", drawing = false, pending = false, down = null, localMachine = "", localInventoryStamp = null;
    el.innerHTML = '<h1>Chrome MinMin</h1><p class="muted">Chọn chạy Chrome trên VPS hoặc trên máy tính đã ghép. Mỗi profile giữ phiên đăng nhập riêng tại máy chạy trình duyệt.</p>' +
      '<div class="fld"><label for="chrome-location">Nơi chạy Chrome</label><select class="sel" id="chrome-location"><option value="host">Trên VPS / máy đang cài MinMin</option><option value="local">Trên máy tính của tôi (qua Worker)</option></select></div>' +
      '<div id="chrome-local" class="card" hidden><h3>Chrome trên máy tính của tôi</h3><p>VPS điều phối, Chrome mở trên máy tính đã ghép. Phiên đăng nhập nằm trên máy đó; không cần GPM Login hay mở cổng router.</p>' +
      '<ol><li>Tải Worker về máy Windows, giải nén và chạy <b>cai-dat.bat</b> một lần.</li><li>Bấm Tạo mã ghép bên dưới. Chạy <b>ghep-chrome.bat</b>, nhập địa chỉ MinMin và mã ghép.</li><li>Chạy <b>chrome-may-tinh.bat</b>: tải Chromium nếu chưa có Chrome, tạo profile rồi mở để đăng nhập Facebook, YouTube, TikTok...</li><li>Đăng nhập xong, nhấn Enter trong cửa sổ quản lý để lưu và đóng Chrome. Chạy <b>chay.bat</b> và giữ máy bật; chọn nick thuộc máy này trong Automation.</li></ol>' +
      '<p class="small muted">Worker mặc định chạy một việc mỗi lúc, tối đa 3 nếu tăng cấu hình. Máy tắt hoặc mất mạng sẽ không nhận việc mới. Máy có GPM vẫn dùng ghep-may.bat như trước.</p>' +
      '<div class="row"><a class="btn" href="/doi-social/tai-worker.zip">Tải MinMin Worker</a><button class="btn" data-act="pair-local">Tạo mã ghép Chrome máy tính</button><a class="btn" href="#/may">Xem máy đã ghép</a></div><p id="chrome-pair" role="status"></p><div id="chrome-local-machines"></div>' +
      '<div class="fld mt"><label for="chrome-local-machine">Máy tính quản lý profile</label><select class="sel" id="chrome-local-machine"></select></div>' +
      '<div class="row"><input class="inp" id="chrome-local-name" placeholder="Tên profile mới"><button class="btn" data-act="local-create">Tạo profile trên máy tính</button><button class="btn" data-act="local-refresh">Quét profile có sẵn</button><button class="btn" data-act="local-install">Tải Chromium trên máy tính</button></div>' +
      '<p class="small muted">Lệnh gửi qua Worker, có trạng thái Chờ / Đang chạy / Hoàn tất bên dưới. Tên nhập cạnh mỗi profile chỉ đổi tên trong MinMin.</p><div id="chrome-local-inventory"></div><div id="chrome-local-commands" role="status"></div>' +
      '<p class="small muted">Dùng phiên đã đăng nhập: Chrome 144+ cần bật chrome://inspect/#remote-debugging và duyệt hộp thoại kết nối tại máy tính. Chỉ dùng profile hiện tại do Chrome chọn; mở đúng profile rồi quét lại. Cốc Cốc chỉ dùng nếu bản đang cài hỗ trợ cơ chế này. Không chép cookie, không đóng trình duyệt cá nhân, không chạy ẩn với phiên có sẵn.</p></div>' +
      '<div id="chrome-host"><div class="card"><div id="chrome-status"></div><div class="row mt-s"><button class="btn" data-act="install">Tải lõi Chromium</button><button class="btn btn-pri" data-act="enable">Bật Worker Chrome</button><button class="btn" data-act="disable">Tắt Worker</button></div>' +
      '<div class="row mt"><input class="inp" id="chrome-name" placeholder="Tên profile, ví dụ HALIMI Facebook"><button class="btn" data-act="create">Tạo profile</button></div><div id="chrome-profiles" class="mt"></div></div>' +
      '<div id="chrome-screen" class="card mt" hidden><div class="row"><b id="chrome-selected"></b><button class="btn btn-sm" data-act="close">Đóng profile</button></div>' +
      '<p class="small muted">Bấm vào ảnh để đặt con trỏ. Nhập chữ vào ô bên dưới rồi bấm Gõ. Mật khẩu chỉ gửi tới trình duyệt của MinMin. Dừng tác vụ trước khi điều khiển tay.</p>' +
      '<div class="row"><select class="sel" id="chrome-tabs" aria-label="Tab trình duyệt"></select><input class="inp" id="chrome-url" placeholder="https://www.facebook.com"><button class="btn" data-act="goto">Mở địa chỉ</button></div>' +
      '<div class="row mt-s"><input class="inp" id="chrome-text" type="password" autocomplete="off" placeholder="Chữ / mật khẩu cần gõ"><button class="btn" data-act="text">Gõ</button>' +
      '<button class="btn" data-act="key" data-key="Enter">Enter</button><button class="btn" data-act="key" data-key="Tab">Tab</button><button class="btn" data-act="key" data-key="Backspace">Xoá</button><button class="btn" data-act="key" data-key="Control+A">Chọn hết</button></div>' +
      '<div class="row mt-s"><button class="btn" data-act="up">Cuộn lên</button><button class="btn" data-act="down">Cuộn xuống</button></div>' +
      '<p id="chrome-error" class="small muted" role="status"></p><img id="chrome-frame" alt="Màn hình Chrome trên máy MinMin" style="width:100%;height:auto;touch-action:none" draggable="false"></div></div>';
    var base = "/doi-social/chrome";
    function refreshLocal() {
      return DS.api("GET", "/doi-social/trang-thai").then(function (r) {
        if (!ctx.alive || r.ok === false) return;
        var machines = (r.may || []).filter(function (m) { return m.driver === "chrome-local"; });
        el.querySelector("#chrome-local-machines").innerHTML = machines.length ? machines.map(function (m) {
          return '<div class="row mt-s"><b>' + esc(m.ten) + '</b><span>' +
            (m.online ? "Đang bật" : "Ngoại tuyến") + " · " + (m.so_nick || 0) + " nick · " +
            (m.driver_ok ? "Chrome sẵn sàng" : "Chrome chưa sẵn sàng") + '</span></div>';
        }).join("") : '<p class="muted">Chưa có máy tính dùng Chrome riêng được ghép.</p>';
        var picker = el.querySelector("#chrome-local-machine");
        if (!machines.some(function (m) { return m.id === localMachine; })) localMachine = machines.length ? machines[0].id : "";
        picker.innerHTML = machines.map(function (m) { return '<option value="' + esc(m.id) + '">' + esc(m.ten) + '</option>'; }).join("");
        picker.value = localMachine;
        if (!localMachine) return;
        var machineId = localMachine;
        return DS.api("GET", "/doi-social/chrome-local/" + encodeURIComponent(machineId)).then(function (d) {
          if (!ctx.alive || machineId !== localMachine || d.ok === false) return;
          if (d.updated !== localInventoryStamp) { localInventoryStamp = d.updated; DS.boNho("nick"); }
          var box = el.querySelector("#chrome-local-inventory");
          if (box.contains(document.activeElement) && document.activeElement.matches("input,textarea,select")) return;
          box.innerHTML = '<h3>Profile dùng trong Automation</h3>' + (d.profiles || []).map(function (p) {
            return '<div class="row mt-s"><span class="grow">' + esc(p.name) + ' · ' + esc(p.browser) + ' · ' + (p.kind === "existing" ? "Phiên có sẵn" : "MinMin quản lý") + (p.open ? ' · Đang mở' : '') + '</span>' +
              '<input class="inp" data-name="' + esc(p.id) + '" aria-label="Tên mới của ' + esc(p.name) + '" placeholder="Tên mới">' +
              '<button class="btn btn-sm" data-act="local-rename" data-id="' + esc(p.id) + '">Đổi tên</button><button class="btn btn-sm" data-act="local-open" data-id="' + esc(p.id) + '">Mở / Đăng nhập</button>' +
              '<button class="btn btn-sm" data-act="local-extensions" data-id="' + esc(p.id) + '">Cài extension</button><button class="btn btn-sm" data-act="local-close" data-id="' + esc(p.id) + '">Đóng profile</button></div>';
          }).join("") + '<h3>Profile Chrome / Cốc Cốc đang có trên máy</h3>' + (d.existing || []).map(function (p) {
            return '<div class="row mt-s"><span class="grow">' + esc(p.browser) + ' · ' + esc(p.name) + ' · ' + (p.active ? 'Profile hiện tại' : 'Mở profile này trên máy trước khi chạy') + '</span>' +
              '<button class="btn btn-sm" data-act="local-use" data-id="' + esc(p.id) + '">Dùng profile này</button></div>';
          }).join("");
          var labels = {pending: "Chờ máy nhận", running: "Đang chạy trên máy tính", done: "Hoàn tất", error: "Chưa thực hiện được"};
          el.querySelector("#chrome-local-commands").textContent = (d.commands || []).slice(0, 3).map(function (c) { return (labels[c.state] || c.state) + (c.message ? ": " + c.message : ""); }).join(" · ");
        });
      });
    }
    el.querySelector("#chrome-local-machine").onchange = function (e) { localMachine = e.target.value; refreshLocal(); };
    function localCommand(action, params) {
      if (!localMachine) return DS.toast("Ghép và chọn máy tính trước", "info");
      return DS.api("POST", "/doi-social/chrome-local/" + encodeURIComponent(localMachine), { action: action, params: params || {} }).then(function (r) {
        if (r.ok !== false) { DS.toast("Đã gửi lệnh tới Worker", "ok"); DS.boNho("nick"); refreshLocal(); }
      });
    }
    el.querySelector("#chrome-location").onchange = function (e) {
      var local = e.target.value === "local";
      el.querySelector("#chrome-local").hidden = !local;
      el.querySelector("#chrome-host").hidden = local;
      if (local) {
        selected = ""; el.querySelector("#chrome-text").value = "";
        el.querySelector("#chrome-frame").removeAttribute("src");
        el.querySelector("#chrome-screen").hidden = true;
        refreshLocal();
      } else refresh();
    };
    function api(path, data) { return DS.api("POST", base + path, data || {}); }
    function action(data) {
      if (!selected || pending) return Promise.resolve();
      pending = true;
      return api("/profile/" + selected + "/action", data).then(function (r) { if (r.ok === false) el.querySelector("#chrome-error").textContent = r.error; })
        .finally(function () { pending = false; frame(); });
    }
    function frame() {
      if (!selected || drawing || !ctx.alive) return;
      drawing = true;
      var profileId = selected;
      fetch(base + "/profile/" + profileId + "/frame", { credentials: "same-origin", cache: "no-store" }).then(function (r) {
        if (!r.ok) throw new Error("Profile đang đóng hoặc chưa mở. Bấm Mở lại để tiếp tục.");
        return r.blob();
      }).then(function (blob) {
        if (!ctx.alive || selected !== profileId) return;
        var img = el.querySelector("#chrome-frame"), url = URL.createObjectURL(blob), old = img.src;
        img.onload = function () { URL.revokeObjectURL(url); };
        img.src = url;
        if (old.indexOf("blob:") === 0) URL.revokeObjectURL(old);
        el.querySelector("#chrome-error").textContent = "";
      }).catch(function (e) { if (ctx.alive) el.querySelector("#chrome-error").textContent = e.message; }).finally(function () { drawing = false; });
    }
    function refresh() {
      if (el.querySelector("#chrome-location").value === "local") return refreshLocal();
      return DS.api("GET", base + "/status").then(function (s) {
        if (!ctx.alive || s.ok === false) return;
        el.querySelector("#chrome-status").textContent = (s.desktop ? "Máy có màn hình" : "Máy chủ / chế độ màn hình web") + " · " +
          (s.installing ? "Đang tải Chromium" : s.installed ? "Đã có Chrome" : "Chưa có Chrome") + " · " + (s.running ? "Worker đang chạy" : "Worker chưa chạy") + (s.install_error ? " · " + s.install_error : "");
        el.querySelector("#chrome-profiles").innerHTML = s.profiles.map(function (p) {
          return '<div class="row mt-s"><b class="grow">' + esc(p.ten) + '</b><span class="small muted">' + (p.busy ? "Đang chạy tác vụ" : p.open ? "Đang mở" : "Đã đóng") +
            '</span><button class="btn btn-sm" data-act="open" data-id="' + p.id + '">Mở / Đăng nhập</button><button class="btn btn-sm" data-act="view" data-id="' + p.id + '">Xem màn hình</button></div>';
        }).join("");
        if (selected) DS.api("GET", base + "/profile/" + selected + "/tabs").then(function (r) {
          if (!ctx.alive || !r.ok) return;
          var sel = el.querySelector("#chrome-tabs"), old = sel.value;
          sel.innerHTML = r.tabs.map(function (t) { return '<option value="' + t.index + '">' + esc(t.title || "Tab " + (t.index + 1)) + '</option>'; }).join("");
          if (old) sel.value = old;
        });
      });
    }
    function select(id) {
      selected = id; el.querySelector("#chrome-frame").removeAttribute("src");
      el.querySelector("#chrome-text").value = ""; el.querySelector("#chrome-screen").hidden = false;
      el.querySelector("#chrome-selected").textContent = "Màn hình Chrome"; frame(); refresh();
    }
    DS.bind(el, {
      "local-create": function () { localCommand("create", { name: el.querySelector("#chrome-local-name").value }); },
      "local-refresh": function () { localCommand("refresh"); },
      "local-install": function () { localCommand("install"); },
      "local-open": function (b) { localCommand("open", { profile: b.getAttribute("data-id") }); },
      "local-close": function (b) { localCommand("close", { profile: b.getAttribute("data-id") }); },
      "local-extensions": function (b) { localCommand("extensions", { profile: b.getAttribute("data-id") }); },
      "local-use": function (b) { localCommand("use-existing", { source: b.getAttribute("data-id") }); },
      "local-rename": function (b) { var id = b.getAttribute("data-id"); localCommand("rename", { profile: id, name: el.querySelector('[data-name="' + id + '"]').value }); },
      "pair-local": function (b) {
        b.disabled = true;
        DS.api("POST", "/doi-social/ma-ghep", {}).then(function (r) {
          if (ctx.alive && r.ok !== false) el.querySelector("#chrome-pair").textContent =
            "Địa chỉ: " + location.origin + " · Mã ghép: " + r.ma + " (" + (r.song_phut || 15) + " phút). Nhập trong ghep-chrome.bat trên máy tính.";
        }).finally(function () { b.disabled = false; });
      },
      install: function () { api("/install").then(refresh); },
      enable: function () { api("/enable", { enabled: true }).then(refresh); },
      disable: function () { api("/enable", { enabled: false }).then(refresh); },
      create: function () { api("/profiles", { name: el.querySelector("#chrome-name").value }).then(function (r) { if (r.ok) { el.querySelector("#chrome-name").value = ""; DS.boNho("nick"); } refresh(); }); },
      open: function (b) { var id = b.getAttribute("data-id"); api("/profile/" + id + "/open").then(function (r) { if (r.ok) select(id); }); },
      view: function (b) { select(b.getAttribute("data-id")); },
      close: function () { api("/profile/" + selected + "/close").then(function (r) { if (r.ok) { selected = ""; el.querySelector("#chrome-screen").hidden = true; refresh(); } }); },
      goto: function () { action({ action: "goto", url: el.querySelector("#chrome-url").value }); },
      text: function () { var input = el.querySelector("#chrome-text"), text = input.value; input.value = ""; action({ action: "text", text: text }); },
      key: function (b) { action({ action: "key", key: b.getAttribute("data-key") }); },
      up: function () { action({ action: "scroll", dy: -600 }); },
      down: function () { action({ action: "scroll", dy: 600 }); }
    });
    el.querySelector("#chrome-tabs").onchange = function (e) { action({ action: "tab", tab: +e.target.value }); };
    var img = el.querySelector("#chrome-frame");
    function point(e) { var r = img.getBoundingClientRect(); return [(e.clientX-r.left)*1280/r.width, (e.clientY-r.top)*800/r.height]; }
    img.onpointerdown = function (e) { e.preventDefault(); down = point(e); img.setPointerCapture(e.pointerId); };
    img.onpointerup = function (e) { if (!down) return; var end = point(e), start = down; down = null;
      if (Math.abs(start[0]-end[0])+Math.abs(start[1]-end[1]) > 8) action({ action: "drag", from: start, to: end });
      else action({ action: "click", x: end[0], y: end[1] }); };
    ctx.every(frame, 1500); ctx.every(refresh, 10000);
    return refresh();
  }});
})();
