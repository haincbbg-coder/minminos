/* Tài khoản - #/tai-khoan : profile GPM (chỉ đọc nguồn), gắn nhãn nền tảng, tuổi nick */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;

  DS.mucNick = function (n) {
    if (n.muc === "lau") return DS.bd("Lâu năm", "ok");
    return DS.bd("Nick mới", "info");
  };

  DS.view("tai-khoan", {
    title: "Tài khoản",
    render: function (el, ctx) {
      var F = { tim: "", thu_muc: "", nhan: "", may: "" }, chon = {}, ds = [];
      el.innerHTML = DS.ph("Tài khoản", "Profile GPM Login trên các máy ở nhà. Gắn nhãn nền tảng để lọc nick khi chạy mẫu.",
        '<button class="btn" data-act="tai-lai">' + ic("refresh") + "Làm mới</button>") +
        '<div class="note mb">' + ic("info") + "<span>Tài khoản lấy từ GPM Login trên máy ở nhà, đã đăng nhập sẵn - không cần thêm tài khoản hay proxy. Muốn thêm nick, tạo profile trong GPM rồi máy ở nhà tự báo lên.</span></div>" +
        '<div class="card card-x"><div class="filters" id="tk-loc"></div><div id="tk-bulk"></div><div id="tk-ds">' + '<div class="tw"><table class="tbl tbl-in"><tbody>' + DS.skelDong(8, 6) + "</tbody></table></div></div></div>";

      function loc() {
        var t = F.tim.trim().toLowerCase();
        return ds.filter(function (n) {
          if (t && (n.ten + " " + (n.nhom || "")).toLowerCase().indexOf(t) < 0) return false;
          if (F.thu_muc && (n.nhom || "") !== F.thu_muc) return false;
          if (F.may && String(n.may_id) !== F.may) return false;
          if (F.nhan === "_chua" && (n.nhan || []).length) return false;
          if (F.nhan && F.nhan !== "_chua" && (n.nhan || []).indexOf(F.nhan) < 0) return false;
          return true;
        });
      }
      function veLoc() {
        var tm = {}, may = {};
        ds.forEach(function (n) { if (n.nhom) tm[n.nhom] = (tm[n.nhom] || 0) + 1; may[n.may_id] = n.may_ten || n.may_id; });
        el.querySelector("#tk-loc").innerHTML = '<div class="inp-ic" style="min-width:200px;flex:1">' + ic("search") + '<input class="inp" id="tk-tim" placeholder="Tìm tên nick hoặc thư mục" value="' + esc(F.tim) + '"></div>' +
          '<select class="sel" id="tk-tm"><option value="">Mọi thư mục</option>' + Object.keys(tm).sort().map(function (k) { return "<option" + (F.thu_muc === k ? " selected" : "") + ' value="' + esc(k) + '">' + esc(k) + " (" + tm[k] + ")</option>"; }).join("") + "</select>" +
          '<select class="sel" id="tk-nhan"><option value="">Mọi nền tảng</option>' + DS.NT_THU_TU.map(function (k) { return '<option value="' + k + '"' + (F.nhan === k ? " selected" : "") + ">" + DS.tenNT(k) + "</option>"; }).join("") +
          '<option value="_chua"' + (F.nhan === "_chua" ? " selected" : "") + ">Chưa gắn nhãn</option></select>" +
          (Object.keys(may).length > 1 ? '<select class="sel" id="tk-may"><option value="">Mọi máy</option>' + Object.keys(may).map(function (k) { return '<option value="' + esc(k) + '"' + (F.may === k ? " selected" : "") + ">" + esc(may[k]) + "</option>"; }).join("") + "</select>" : "");
      }
      function soChon() { return Object.keys(chon).filter(function (k) { return chon[k]; }); }
      function veBulk() {
        var n = soChon().length;
        el.querySelector("#tk-bulk").innerHTML = n ? '<div class="filters" style="background:var(--brand-soft)"><b>' + n + ' nick đã chọn</b><span class="grow"></span><button class="btn btn-sm" data-act="gan-nhan">' + ic("tag") +
          'Gắn nhãn nền tảng</button><button class="btn btn-sm" data-act="tao-tu">' + ic("calendar") + 'Đặt "tạo từ"</button><button class="btn btn-sm btn-ghost" data-act="bo-chon">Bỏ chọn</button></div>' : "";
      }
      function veDs() {
        var l = loc(), box = el.querySelector("#tk-ds");
        if (!ds.length) { box.innerHTML = DS.rong("Chưa có nick nào", 'Ghép máy ở nhà có GPM Login để MinMin đọc danh sách profile. <a href="#/may">Mở Máy ở nhà</a>', "list"); return; }
        if (!l.length) { box.innerHTML = DS.rong("Không có nick khớp bộ lọc", "", "list"); return; }
        var tatCa = l.every(function (n) { return chon[n.id]; });
        box.innerHTML = '<div class="tw"><table class="tbl tbl-in" style="min-width:900px"><thead><tr><th class="w1"><input type="checkbox" class="cb" id="tk-all"' + (tatCa ? " checked" : "") +
          ' aria-label="Chọn tất cả"></th><th>Nick</th><th>Thư mục</th><th>Trạng thái</th><th>Nền tảng</th><th>Cảnh báo</th><th>Chạy lần cuối</th><th>Mức</th></tr></thead><tbody>' +
          l.map(function (n) {
            var cb = n.canh_bao || {}, cbk = Object.keys(cb);
            return '<tr><td><input type="checkbox" class="cb" data-chon="' + esc(n.id) + '"' + (chon[n.id] ? " checked" : "") + '></td><td><div class="row" style="flex-wrap:nowrap">' + DS.av(n.ten) +
              '<div style="min-width:0"><div class="b clip" style="max-width:220px">' + esc(n.ten) + '</div><div class="sub">' + esc(n.may_ten || "") + (n.trinh_duyet ? " · " + esc(n.trinh_duyet) : "") + "</div></div></div></td>" +
              '<td class="small nw">' + (n.nhom ? '<span class="row" style="flex-wrap:nowrap;gap:4px">' + ic("folder") + esc(n.nhom) + "</span>" : '<span class="muted">Không thư mục</span>') + "</td>" +
              '<td class="nw"><span class="row" style="flex-wrap:nowrap;gap:6px"><span class="dotx' + (n.online ? " on" : "") + '"></span>' + (n.online ? "Online" : '<span class="muted">Ngoại tuyến</span>') + "</span></td>" +
              '<td><div class="row" style="gap:4px">' + ((n.nhan || []).length ? n.nhan.map(function (t) { return '<span class="bd bd-out" style="padding-left:3px">' + DS.icNT(t, 16) + esc(DS.tenNT(t)) + "</span>"; }).join("") :
                '<span class="small muted">Chưa gắn</span>') + "</div></td>" +
              "<td>" + (cbk.length ? cbk.map(function (k) { return DS.bd((DS.CANH_BAO[cb[k]] || cb[k]) + " · " + DS.tenNT(k), "err", true); }).join(" ") : '<span class="small muted">Không</span>') + "</td>" +
              '<td class="small nw">' + (n.lan_chay ? DS.tuongDoi(n.lan_chay) : '<span class="muted">Chưa chạy</span>') + "</td>" +
              '<td class="nw">' + DS.mucNick(n) + (n.tao_tu ? '<div class="sub">tạo ' + esc(n.tao_tu.split("-").reverse().join("/")) + "</div>" : "") + "</td></tr>";
          }).join("") + '</tbody></table></div><div class="tfoot"><span>' + l.length + " / " + ds.length + " nick</span><span>" + ds.filter(function (n) { return n.online; }).length + " đang online</span></div>";
      }
      function nap(moi) {
        return DS.layNick(moi !== false).then(function (d) {
          if (!ctx.alive) return;
          if (d.ok === false) { el.querySelector("#tk-ds").innerHTML = DS.rong("Chưa tải được", esc(d.error), "list"); return; }
          ds = DS.list(d, "nick");
          veLoc(); veBulk(); veDs();
        });
      }
      function luuMeta(body, msg) {
        body.ids = soChon();
        return DS.api("POST", "/doi-social/nick/meta", body).then(function (d) {
          if (d.ok === false) return false;
          DS.toast(msg.replace("{n}", body.ids.length), "ok"); DS.boNho("nick"); nap(); return true;
        });
      }
      el.addEventListener("input", function (e) { if (e.target.id === "tk-tim") { F.tim = e.target.value; veDs(); } });
      el.addEventListener("change", function (e) {
        var t = e.target;
        if (t.id === "tk-tm") F.thu_muc = t.value;
        else if (t.id === "tk-nhan") F.nhan = t.value;
        else if (t.id === "tk-may") F.may = t.value;
        else if (t.id === "tk-all") { loc().forEach(function (n) { chon[n.id] = t.checked; }); veBulk(); veDs(); return; }
        else if (t.getAttribute("data-chon")) { chon[t.getAttribute("data-chon")] = t.checked; veBulk(); return; }
        else return;
        veDs();
      });
      DS.bind(el, {
        "tai-lai": function () { nap(true); },
        "bo-chon": function () { chon = {}; veBulk(); veDs(); },
        "gan-nhan": function () {
          var ids = soChon(), co = {};
          ds.forEach(function (n) { if (ids.indexOf(String(n.id)) >= 0) (n.nhan || []).forEach(function (t) { co[t] = (co[t] || 0) + 1; }); });
          var m = DS.modal({ title: "Gắn nhãn nền tảng cho " + ids.length + " nick",
            body: '<p class="small muted" style="margin:0 0 12px">Nhãn cho biết nick này đã đăng nhập nền tảng nào trong profile GPM. Nhãn được thay bằng lựa chọn dưới đây.</p><div class="grid g2" style="gap:8px">' +
              DS.NT_THU_TU.map(function (k) {
                return '<label class="swrow" style="margin:0"><span class="row">' + DS.icNT(k, 22) + esc(DS.tenNT(k)) + (co[k] ? '<span class="tiny muted">' + co[k] + "/" + ids.length + "</span>" : "") +
                  '</span><input type="checkbox" class="cb" value="' + k + '"' + (co[k] === ids.length ? " checked" : "") + "></label>";
              }).join("") + "</div>",
            foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="gn-ok">Lưu nhãn</button>' });
          m.foot.querySelector("#gn-ok").onclick = function () {
            var nhan = Array.prototype.map.call(m.body.querySelectorAll("input:checked"), function (i) { return i.value; });
            luuMeta({ nhan: nhan }, "Đã gắn nhãn cho {n} nick").then(function (ok) { if (ok) m.close(); });
          };
        },
        "tao-tu": function () {
          var d = new Date(), gt = d.getFullYear() + "-" + (d.getMonth() < 9 ? "0" : "") + (d.getMonth() + 1);
          var m = DS.modal({ title: 'Đặt "tạo từ" cho ' + soChon().length + " nick",
            body: '<div class="fld"><label for="tt-thang">Tháng tạo tài khoản</label><input class="inp" type="month" id="tt-thang" value="' + gt + '" max="' + gt + '"><div class="hint">Dùng để tính tuổi nick: nick đủ tuổi dùng giới hạn lâu năm (cao hơn).</div></div>',
            foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="tt-ok">Áp dụng</button>' });
          m.foot.querySelector("#tt-ok").onclick = function () {
            var v = m.body.querySelector("#tt-thang").value;
            if (!/^\d{4}-\d{2}$/.test(v)) { DS.toast("Chọn tháng", "err"); return; }
            luuMeta({ tao_tu: v }, "Đã đặt tháng tạo cho {n} nick").then(function (ok) { if (ok) m.close(); });
          };
        }
      });
      return nap(false);
    }
  });
})();
