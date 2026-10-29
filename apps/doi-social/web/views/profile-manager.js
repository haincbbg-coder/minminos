/* Profile table and bulk creation, shared by VPS and PC Worker locations. */
(function () {
  "use strict";
  DS.profileManager = function (el, send, actions) {
    var esc = DS.esc, rows = [], selected = {}, search = "", group = "";
    el.innerHTML = '<details class="card mt"><summary>Tạo profile hàng loạt và nơi lưu</summary>' +
      '<div class="grid g2 mt"><div class="fld"><label>Mẫu tên ({n} là số)</label><input class="inp" data-pm="name" value="Profile {n}"></div><div class="fld"><label>Nhóm</label><input class="inp" data-pm="group" placeholder="Ví dụ: HALIMI / Khách A"></div></div>' +
      '<div class="grid g3"><div class="fld"><label>Số lượng</label><input class="inp" data-pm="count" type="number" min="1" max="100" value="1"></div><div class="fld"><label>Số bắt đầu</label><input class="inp" data-pm="start" type="number" min="0" value="1"></div><div class="fld"><label>Số chữ số</label><input class="inp" data-pm="digits" type="number" min="1" max="6" value="2"></div></div>' +
      '<div class="fld"><label>Hoặc nhập tên riêng, mỗi dòng một tên</label><textarea class="ta" data-pm="names" rows="3"></textarea></div>' +
      '<div class="fld"><label>Proxy: một dòng dùng chung hoặc một dòng cho mỗi profile</label><textarea class="ta" data-pm="proxy_lines" rows="3" autocomplete="off" spellcheck="false" placeholder="http://IP:PORT hoặc IP:PORT:USER:PASS, socks5://..."></textarea></div>' +
      '<div class="fld"><label>Thư mục lưu trên máy chạy Chrome (để trống dùng mặc định)</label><input class="inp" data-pm="storage_root" placeholder="Ví dụ trên Windows: D:\\MinMinProfiles"></div>' +
      '<p class="small muted" data-pm="storage-hint"></p><div class="row"><button class="btn" data-act="pm-create">Tạo cả lô</button><button class="btn" data-act="pm-storage">Đặt nơi lưu cho profile tạo mới</button></div></details>' +
      '<div class="card mt"><div class="row"><input class="inp" data-pm="search" placeholder="Tìm tên, nhóm hoặc ghi chú"><select class="sel" data-pm="filter" aria-label="Lọc nhóm profile"></select></div>' +
      '<div class="row mt-s"><input class="inp" data-pm="newgroup" placeholder="Nhóm cho profile đã chọn"><button class="btn" data-act="pm-group">Gom nhóm đã chọn</button><input class="inp" data-pm="proxy" type="password" autocomplete="off" placeholder="Proxy mới cho profile đã chọn"><button class="btn" data-act="pm-proxy">Lưu proxy</button><button class="btn" data-act="pm-clear-proxy">Bỏ proxy</button></div>' +
      '<p class="small muted">Chọn nhiều profile để gom nhóm hoặc đổi proxy. Đóng profile trước khi sửa cấu hình. Proxy chỉ áp dụng cho profile MinMin quản lý.</p><div class="tw" data-pm="table"></div></div>';
    function field(name) { return el.querySelector('[data-pm="' + name + '"]'); }
    function draw() {
      var groups = Array.from(new Set(rows.map(function (p) { return p.group || "Chưa phân nhóm"; }))).sort();
      field("filter").innerHTML = '<option value="">Mọi nhóm</option>' + groups.map(function (g) { return '<option>' + esc(g) + '</option>'; }).join("");
      field("filter").value = group;
      var visible = rows.filter(function (p) { return (!group || (p.group || "Chưa phân nhóm") === group) && (!search || (p.name + " " + (p.group || "") + " " + (p.note || "")).toLowerCase().indexOf(search) >= 0); });
      field("table").innerHTML = '<table class="tbl"><thead><tr><th>Chọn</th><th>Profile</th><th>Nhóm</th><th>Proxy</th><th>Vị trí lưu</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>' + visible.map(function (p) {
        return '<tr><td><input type="checkbox" data-pick="' + esc(p.id) + '" aria-label="Chọn ' + esc(p.name) + '"' + (selected[p.id] ? ' checked' : '') + '></td><td><b>' + esc(p.name) + '</b><div class="small muted">' + esc(p.kind === "existing" ? "Phiên có sẵn" : "MinMin quản lý") + '</div></td><td>' + esc(p.group || "Chưa phân nhóm") + '</td><td>' + esc(p.proxy_label || "Không dùng") + '</td><td class="small">' + esc(p.data_dir || "Thư mục trình duyệt cá nhân") + '</td><td>' + (p.busy ? "Đang chạy tác vụ" : p.open ? "Đang mở" : "Đã đóng") + '</td><td><div class="row">' + actions(p) + '</div></td></tr>';
      }).join("") + '</tbody></table><p class="small muted">' + visible.length + ' / ' + rows.length + ' profile · đã chọn ' + Object.keys(selected).filter(function (id) { return selected[id]; }).length + '</p>';
    }
    el.addEventListener("change", function (e) {
      if (e.target.hasAttribute("data-pick")) { selected[e.target.getAttribute("data-pick")] = e.target.checked; }
      if (e.target === field("filter")) { group = e.target.value; draw(); }
    });
    field("search").oninput = function (e) { search = e.target.value.toLowerCase().trim(); draw(); };
    function update(data) {
      data.profiles = rows.filter(function (p) { return selected[p.id]; }).map(function (p) { return p.id; });
      if (!data.profiles.length) return DS.toast("Chọn ít nhất một profile", "info");
      send("update-batch", data);
    }
    DS.bind(el, {
      "pm-create": function () {
        var data = {};
        ["name", "group", "count", "start", "digits", "names", "proxy_lines", "storage_root"].forEach(function (k) { data[k] = field(k).value; });
        Promise.resolve(send("create-batch", data)).then(function () { field("proxy_lines").value = ""; });
      },
      "pm-storage": function () { send("storage", {storage_root: field("storage_root").value}); },
      "pm-group": function () { update({group: field("newgroup").value}); },
      "pm-proxy": function () { var value = field("proxy").value; field("proxy").value = ""; if (value) update({proxy: value}); },
      "pm-clear-proxy": function () { update({proxy: ""}); }
    });
    return {update: function (items, storage) {
      if (field("table").contains(document.activeElement) && document.activeElement.matches("input,textarea,select")) return;
      rows = items;
      field("storage-hint").textContent = 'Mặc định: ' + (storage || 'Chưa có máy được chọn') + '. Đổi nơi lưu chỉ áp dụng cho profile mới, không di chuyển dữ liệu cũ.';
      draw();
    }};
  };
})();
