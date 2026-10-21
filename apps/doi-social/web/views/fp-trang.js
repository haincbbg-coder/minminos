/* Fanpage (API) - Trang & Nhóm - #/fp-trang (tab Trang · Nhóm · Token) */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic, FP = DS.fp;

  // ================================================================ sửa cấu hình: nhóm, một Trang, nhiều Trang
  function moCauHinh(o) {
    // o: {tieuDe, ch, keThua (Trang: cho chọn Theo nhóm), rieng (đang có cấu hình riêng), them (html đầu form), luu(ch|null, body) -> Promise<bool>}
    return FP.layKho().then(function (dk) {
      var dsKho = DS.list(dk);
      var rieng = o.keThua ? !!o.rieng : true;
      var m = DS.modal({ title: o.tieuDe, wide: true, focus: false,
        body: (o.them || "") + (o.keThua ? '<div class="fld mb"><label>Cấu hình của Trang</label><div class="seg" id="ch-kt"><button type="button" data-v="nhom" class="' + (rieng ? "" : "on") +
          '">Theo nhóm</button><button type="button" data-v="rieng" class="' + (rieng ? "on" : "") + '">Cấu hình riêng</button></div><div class="hint">Theo nhóm: Trang dùng lịch, kho và công tắc của nhóm (hoặc mặc định nếu chưa nhóm).</div></div>' : "") +
          '<div id="ch-form"' + (rieng ? "" : " hidden") + ">" + FP.formCauHinh(o.ch, dsKho) + "</div>",
        foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="ch-luu">Lưu</button>' });
      var f = m.body.querySelector("#ch-form");
      FP.ganCauHinh(f);
      var kt = m.body.querySelector("#ch-kt");
      if (kt) kt.addEventListener("click", function (e) {
        var b = e.target.closest("button"); if (!b) return;
        Array.prototype.forEach.call(kt.children, function (x) { x.classList.toggle("on", x === b); });
        rieng = b.getAttribute("data-v") === "rieng"; f.hidden = !rieng;
      });
      m.foot.querySelector("#ch-luu").onclick = function () {
        var ch = rieng ? FP.docCauHinh(f) : null;
        if (ch && ch.lich.che_do === "gio" && !ch.lich.gio.length) { DS.toast("Nhập ít nhất một khung giờ, ví dụ 09:00", "err"); return; }
        var btn = this; btn.disabled = true;
        Promise.resolve(o.luu(ch, m.body)).then(function (ok) { btn.disabled = false; if (ok) m.close(); });
      };
      return m;
    });
  }

  // ================================================================ tab Trang
  function tabTrang(el, ctx) {
    var body = el.querySelector("#fp-body");
    var F = { nhom: ctx.q.nhom || "", tim: "", sap_xep: "ten" }, chon = {}, ds = [], dsNhom = [], chuaNhom = 0, dsKho = [], cuoi = -1, keo = null, vuaKeo = false;
    body.innerHTML = '<div class="card card-x"><div class="filters" id="tr-loc"></div><div id="tr-bulk"></div><div id="tr-ds"><div class="tw"><table class="tbl tbl-in"><tbody>' + DS.skelDong(6, 7) + "</tbody></table></div></div></div>";

    function loc() {
      var t = F.tim.trim().toLowerCase();
      var l = ds.filter(function (x) {
        if (F.nhom === "_chua" && x.nhom_id != null) return false;
        if (F.nhom && F.nhom !== "_chua" && String(x.nhom_id) !== F.nhom) return false;
        if (t && ((x.ten || "") + " " + x.id + " " + (x.danh_muc || "") + " " + (x.ig_ten || "")).toLowerCase().indexOf(t) < 0) return false;
        return true;
      });
      if (F.sap_xep === "da_dang") l.sort(function (a, b) { return ((b.dem || {}).da_dang || 0) - ((a.dem || {}).da_dang || 0); });
      else if (F.sap_xep === "loi") l.sort(function (a, b) { return ((b.dem || {}).loi || 0) - ((a.dem || {}).loi || 0); });
      else if (F.sap_xep === "theo_doi") l.sort(function (a, b) { return (b.nguoi_theo_doi || 0) - (a.nguoi_theo_doi || 0); });
      else l.sort(function (a, b) { return String(a.ten || "").localeCompare(String(b.ten || ""), "vi"); });
      return l;
    }
    function soChon() { return Object.keys(chon).filter(function (k) { return chon[k]; }); }
    function veLoc() {
      el.querySelector("#tr-loc").innerHTML = '<div class="chips" id="tr-nhom" style="width:100%">' +
        '<button class="chip' + (F.nhom === "" ? " on" : "") + '" data-act="loc-nhom" data-v="">Tất cả <span class="cnt">' + ds.length + "</span></button>" +
        dsNhom.map(function (n) { return '<button class="chip' + (F.nhom === String(n.id) ? " on" : "") + '" data-act="loc-nhom" data-v="' + esc(n.id) + '">' + esc(n.ten) + ' <span class="cnt">' + FP.so(n.so) + "</span></button>"; }).join("") +
        '<button class="chip' + (F.nhom === "_chua" ? " on" : "") + '" data-act="loc-nhom" data-v="_chua">Chưa nhóm <span class="cnt">' + FP.so(chuaNhom) + "</span></button></div>" +
        '<div class="inp-ic" style="min-width:200px;flex:1">' + ic("search") + '<input class="inp" id="tr-tim" placeholder="Tìm tên Trang, ID, danh mục" value="' + esc(F.tim) + '"></div>' +
        '<select class="sel" id="tr-sx" aria-label="Sắp xếp">' + [["ten", "Tên A-Z"], ["da_dang", "Đăng nhiều nhất"], ["loi", "Lỗi nhiều nhất"], ["theo_doi", "Người theo dõi"]].map(function (x) {
          return '<option value="' + x[0] + '"' + (F.sap_xep === x[0] ? " selected" : "") + ">" + x[1] + "</option>";
        }).join("") + "</select>";
    }
    function veBulk() {
      var n = soChon().length;
      el.querySelector("#tr-bulk").innerHTML = n ? '<div class="filters fp-bulk"><b>' + n + ' Trang đã chọn</b><span class="grow"></span><div class="fp-dd"><button class="btn btn-sm btn-pri" data-act="mo-menu">' + ic("bolt") +
        "Hành động" + ic("chev") + '</button><div class="fp-menu" id="tr-menu" hidden>' +
        '<button data-act="hd" data-hd="gan_nhom">' + ic("users") + "Gán nhóm</button>" +
        '<button data-act="hd" data-hd="gan_cau_hinh">' + ic("calendar") + "Gán cấu hình (lịch, kho, công tắc)</button>" +
        '<div class="fp-menu-sep"></div><div class="fp-menu-t">Đổi thông tin Trang (công khai)</div>' +
        '<button data-act="hd" data-hd="doi_tieu_su">' + ic("edit") + "Đổi tiểu sử</button>" +
        '<button data-act="hd" data-hd="doi_anh">' + ic("user") + "Đổi ảnh đại diện</button>" +
        '<button data-act="hd" data-hd="doi_bia">' + ic("image") + "Đổi ảnh bìa</button>" +
        '<div class="fp-menu-sep"></div><button data-act="hd" data-hd="bat">' + ic("play") + "Bật đăng</button>" +
        '<button data-act="hd" data-hd="tat">' + ic("pause") + "Tắt đăng</button></div></div>" +
        '<button class="btn btn-sm btn-ghost" data-act="bo-chon">Bỏ chọn</button></div>' : "";
    }
    function lichO(x) {
      var hl = x.cau_hinh_hieu_luc || {}, l = hl.lich || {}, ng = x.nguon_cau_hinh || "mac_dinh";
      return '<button type="button" class="linkbtn fp-lich" data-act="sua" data-id="' + esc(x.id) + '" title="Sửa cấu hình"><span class="row" style="flex-wrap:nowrap;gap:5px">' + ic("clock") +
        '<span class="clip" style="max-width:190px">' + esc(FP.moTaLich(l)) + '</span></span></button><div class="sub">' + esc(FP.NGUON_CH[ng] || ng) +
        (x.bai_ke ? " · kế " + esc(DS.tuongDoi(x.bai_ke)) : "") + "</div>";
    }
    function veDs() {
      var l = loc(), box = el.querySelector("#tr-ds");
      if (!ds.length) {
        box.innerHTML = DS.rong("Chưa có Trang nào", "Thêm nguồn token ở tab Token (hoặc nối Facebook Trang ở trang Kết nối) rồi bấm Đồng bộ Trang.", "list",
          '<button class="btn btn-pri" data-act="dong-bo">' + ic("refresh") + "Đồng bộ Trang</button>");
        return;
      }
      if (!l.length) { box.innerHTML = DS.rong("Không có Trang khớp bộ lọc", "", "list"); return; }
      var tatCa = l.every(function (x) { return chon[x.id]; });
      box.innerHTML = '<div class="tw"><table class="tbl tbl-in fp-tbl-trang" style="min-width:1120px"><thead><tr><th class="w1"><input type="checkbox" class="cb" id="tr-all"' + (tatCa ? " checked" : "") +
        ' aria-label="Chọn tất cả"></th><th>Trang</th><th>Nhóm</th><th>Lịch đăng</th><th>Kho đang dùng</th><th class="num">Bài</th><th>Công tắc</th><th>Bật</th><th></th></tr></thead><tbody>' +
        l.map(function (x, i) {
          var dm = x.dem || {}, hl = x.cau_hinh_hieu_luc || {}, kho = FP.tenKho(dsKho, hl.kho_noi_dung);
          var mat = (x.quyen || []).length && (x.quyen || []).indexOf("CREATE_CONTENT") < 0;
          return '<tr data-i="' + i + '" data-id="' + esc(x.id) + '" class="' + (chon[x.id] ? "fp-on" : "") + (x.bat === 0 || x.bat === false ? " fp-off" : "") + '"><td class="fp-cbo"><input type="checkbox" class="cb" data-chon="' + esc(x.id) + '"' +
            (chon[x.id] ? " checked" : "") + ' aria-label="Chọn ' + esc(x.ten) + '"></td><td><div class="row" style="flex-wrap:nowrap">' + FP.avTrang(x) + '<div style="min-width:0"><div class="row" style="gap:6px;flex-wrap:nowrap"><b class="clip" style="max-width:220px">' +
            esc(x.ten || x.id) + "</b>" + (x.link ? '<a href="' + esc(x.link) + '" target="_blank" rel="noopener" title="Mở Trang trên Facebook" aria-label="Mở Trang">' + ic("ext") + "</a>" : "") +
            (x.ig_id ? '<span class="bd bd-brand" title="Instagram: ' + esc(x.ig_ten || x.ig_id) + '">IG</span>' : "") + '</div><div class="sub">ID ' + esc(x.id) + (x.danh_muc ? " · " + esc(x.danh_muc) : "") +
            (x.nguoi_theo_doi ? " · " + FP.so(x.nguoi_theo_doi) + " theo dõi" : "") + "</div>" + (mat ? '<div class="tiny" style="color:var(--err)">Mất quyền đăng bài</div>' : "") +
            (x.so_token === 0 ? '<div class="tiny" style="color:var(--err)">Không còn token nào</div>' : "") + "</div></div></td>" +
            '<td class="small nw">' + (x.nhom_ten ? esc(x.nhom_ten) : '<span class="muted">Chưa nhóm</span>') + "</td><td>" + lichO(x) + "</td>" +
            '<td class="small">' + (kho ? '<span class="clip" style="display:block;max-width:160px">' + esc(kho) + "</span>" : '<span class="muted">Không</span>') + "</td>" +
            '<td class="num nw small"><span style="color:var(--ok)" title="Đã đăng">' + FP.so(dm.da_dang) + '</span> · <span title="Đang chờ">' + FP.so(dm.cho) + "</span> · " +
            '<span title="Lỗi" style="' + (dm.loi ? "color:var(--err);font-weight:600" : "") + '">' + FP.so(dm.loi) + "</span></td><td>" + FP.chipCongTac(hl) + "</td>" +
            "<td>" + DS.sw('data-bat="' + esc(x.id) + '" aria-label="Bật đăng cho Trang"', !(x.bat === 0 || x.bat === false)) + '</td><td class="nw"><button class="btn btn-xs" data-act="sua" data-id="' + esc(x.id) + '">' + ic("edit") + "Sửa</button></td></tr>";
        }).join("") + '</tbody></table></div><div class="tfoot"><span>' + l.length + " / " + ds.length + ' Trang</span><span class="tiny">Giữ Shift để chọn một dải, hoặc kéo chuột dọc cột ô chọn.</span></div>';
    }
    function nap(moi) {
      return Promise.all([FP.api("GET", "/trang" + DS.qs({ sap_xep: "ten" }), null, { quiet: true }), FP.layKho(moi)]).then(function (a) {
        if (!ctx.alive) return;
        var d = a[0];
        if (d.ok === false) { el.querySelector("#tr-ds").innerHTML = DS.loiThe(d.error, true); return; }
        DS.cache["fp-trang"] = { t: Date.now(), d: d };
        ds = DS.list(d); dsNhom = d.nhom || []; dsKho = DS.list(a[1]);
        chuaNhom = d.chua_nhom != null ? d.chua_nhom : ds.filter(function (x) { return x.nhom_id == null; }).length;
        var con = {}; ds.forEach(function (x) { if (chon[x.id]) con[x.id] = true; }); chon = con;
        veLoc(); veBulk(); veDs();
      });
    }
    function ids() { return soChon(); }
    function hanhDong(hd, them, viec) {
      var b = Object.assign({ ids: ids(), hanh_dong: hd }, them || {});
      return FP.api("POST", "/trang/hanh-dong", b).then(function (d) {
        if (d.ok === false) return false;
        FP.ketQuaHangLoat(d, viec); FP.boNho(); nap(true); return true;
      });
    }
    function taiAnh(tep) {
      var fd = new FormData(); fd.append("tep", tep, tep.name);
      return FP.api("POST", "/media", fd).then(function (d) { if (d.ok === false) return null; var m = DS.list(d)[0]; return m ? m.tep : null; });
    }
    function moDoiAnh(hd) {
      var bia = hd === "doi_bia", n = ids().length;
      var m = DS.modal({ title: (bia ? "Đổi ảnh bìa" : "Đổi ảnh đại diện") + " cho " + n + " Trang",
        body: '<div class="note note-warn mb">' + ic("alert") + "<span>" + FP.CANH_BAO_CONG_KHAI + " Mọi người theo dõi Trang thấy ảnh mới, Facebook có thể đăng tin cập nhật ảnh.</span></div>" +
          '<label class="drop">' + ic("upload") + ' <span id="da-t">Bấm để chọn một ảnh (JPG, PNG)</span><input type="file" id="da-tep" accept="image/*"></label>' +
          '<div class="hint mt-s">' + (bia ? "Ảnh bìa đẹp nhất ở cỡ 1640 x 624." : "Ảnh vuông, ít nhất 320 x 320.") + " Một ảnh dùng chung cho mọi Trang đã chọn.</div>",
        foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="da-ok">Đổi ảnh ' + n + " Trang</button>" });
      m.body.querySelector("#da-tep").addEventListener("change", function () { var f = this.files[0]; m.body.querySelector("#da-t").textContent = f ? f.name : "Bấm để chọn một ảnh"; });
      m.foot.querySelector("#da-ok").onclick = function () {
        var f = m.body.querySelector("#da-tep").files[0], btn = this;
        if (!f) { DS.toast("Chọn một ảnh", "err"); return; }
        btn.disabled = true; btn.textContent = "Đang tải ảnh lên...";
        taiAnh(f).then(function (tep) {
          if (!tep) { btn.disabled = false; btn.textContent = "Thử lại"; return; }
          return hanhDong(hd, { tep: tep }, bia ? "Đổi ảnh bìa" : "Đổi ảnh đại diện").then(function (ok) { btn.disabled = false; if (ok) m.close(); });
        });
      };
    }
    function moTieuSu() {
      var n = ids().length;
      FP.layKho().then(function (dk) {
        var kho = DS.list(dk).filter(function (k) { return k.loai === "tieu_su"; }), kieu = kho.length ? "kho" : "chu";
        var m = DS.modal({ title: "Đổi tiểu sử cho " + n + " Trang",
          body: '<div class="note note-warn mb">' + ic("alert") + "<span>Tiểu sử mới hiện ngay ở phần Giới thiệu của Trang, ai vào Trang cũng thấy.</span></div>" +
            '<div class="fld"><label>Lấy chữ từ</label><div class="seg" id="ts-k"><button type="button" data-v="kho" class="' + (kieu === "kho" ? "on" : "") + '">Kho tiểu sử</button><button type="button" data-v="chu" class="' +
            (kieu === "chu" ? "on" : "") + '">Gõ tay</button></div></div>' +
            '<div class="fld" id="ts-kho"' + (kieu === "kho" ? "" : " hidden") + '><label for="ts-kho-s">Kho tiểu sử</label><select class="sel" id="ts-kho-s">' + kho.map(function (k) {
              return '<option value="' + esc(k.id) + '">' + esc(k.ten) + " (" + FP.so(k.so) + " mục)</option>"; }).join("") + "</select>" +
            (kho.length ? '<div class="hint">Mỗi Trang lấy một mục theo cách chọn của kho, có spin.</div>' : '<div class="hint">Chưa có kho tiểu sử. <a href="#/fp-kho?tab=tieu_su">Tạo ở Kho nội dung</a></div>') + "</div>" +
            '<div class="fld" id="ts-chu"' + (kieu === "chu" ? "" : " hidden") + '><label for="ts-ta">Tiểu sử</label><textarea class="ta" id="ts-ta" rows="4" maxlength="255" placeholder="{Chuyên|Chuyên trang} {review phim|phim hay} mỗi ngày. Ghé {ten_trang} nhé!"></textarea>' +
            '<div class="hint">Tối đa 255 ký tự. Dùng được spin {a|b} và {ten_trang}.</div></div>',
          foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="ts-ok">Đổi tiểu sử ' + n + " Trang</button>" });
        m.body.querySelector("#ts-k").addEventListener("click", function (e) {
          var b = e.target.closest("button"); if (!b) return;
          kieu = b.getAttribute("data-v");
          Array.prototype.forEach.call(this.children, function (x) { x.classList.toggle("on", x === b); });
          m.body.querySelector("#ts-kho").hidden = kieu !== "kho"; m.body.querySelector("#ts-chu").hidden = kieu !== "chu";
        });
        m.foot.querySelector("#ts-ok").onclick = function () {
          var them;
          if (kieu === "kho") { var v = m.body.querySelector("#ts-kho-s").value; if (!v) { DS.toast("Chọn một kho tiểu sử", "err"); return; } them = { kho_id: isNaN(+v) ? v : +v }; }
          else { var c = m.body.querySelector("#ts-ta").value.trim(); if (!c) { DS.toast("Nhập tiểu sử", "err"); return; } them = { chu: c }; }
          var btn = this; btn.disabled = true;
          hanhDong("doi_tieu_su", them, "Đổi tiểu sử").then(function (ok) { btn.disabled = false; if (ok) m.close(); });
        };
      });
    }
    function moGanNhom() {
      var n = ids().length;
      var m = DS.modal({ title: "Gán nhóm cho " + n + " Trang",
        body: '<div class="fld"><label for="gn-s">Nhóm</label><select class="sel" id="gn-s"><option value="">Không nhóm (dùng cấu hình mặc định)</option>' + dsNhom.map(function (x) {
          return '<option value="' + esc(x.id) + '">' + esc(x.ten) + "</option>"; }).join("") + '<option value="_moi">+ Tạo nhóm mới...</option></select></div>' +
          '<div class="fld" id="gn-moi" hidden><label for="gn-ten">Tên nhóm mới</label><input class="inp" id="gn-ten" placeholder="Ví dụ: Trang phim lẻ"></div>' +
          '<div class="hint mt-s">Trang trong nhóm dùng lịch, kho và công tắc của nhóm (trừ khi Trang có cấu hình riêng).</div>',
        foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="gn-ok">Gán nhóm</button>' });
      var s = m.body.querySelector("#gn-s");
      s.addEventListener("change", function () { m.body.querySelector("#gn-moi").hidden = s.value !== "_moi"; });
      m.foot.querySelector("#gn-ok").onclick = function () {
        var btn = this, v = s.value;
        var lam = function (nid) { return hanhDong("gan_nhom", { nhom_id: nid }, "Gán nhóm").then(function (ok) { btn.disabled = false; if (ok) m.close(); }); };
        btn.disabled = true;
        if (v === "_moi") {
          var ten = m.body.querySelector("#gn-ten").value.trim();
          if (!ten) { btn.disabled = false; DS.toast("Nhập tên nhóm", "err"); return; }
          FP.api("POST", "/nhom", { ten: ten, cau_hinh: {} }).then(function (d) {
            if (d.ok === false) { btn.disabled = false; return; }
            var nid = d.id != null ? d.id : (d.nhom || {}).id;
            lam(nid);
          });
        } else lam(v ? (isNaN(+v) ? v : +v) : null);
      };
    }

    el.addEventListener("input", function (e) { if (e.target.id === "tr-tim") { F.tim = e.target.value; veDs(); } });
    el.addEventListener("change", function (e) {
      var t = e.target;
      if (t.id === "tr-sx") { F.sap_xep = t.value; veDs(); }
      else if (t.id === "tr-all") { loc().forEach(function (x) { chon[x.id] = t.checked; }); veBulk(); veDs(); }
      else if (t.getAttribute("data-chon")) { chon[t.getAttribute("data-chon")] = t.checked; var tr = t.closest("tr"); if (tr) { tr.classList.toggle("fp-on", t.checked); cuoi = +tr.getAttribute("data-i"); } veBulk(); }
      else if (t.getAttribute("data-bat")) {
        var id = t.getAttribute("data-bat"), bat = t.checked;
        FP.api("PATCH", "/trang/" + encodeURIComponent(id), { bat: bat }).then(function (d) {
          if (d.ok === false) { t.checked = !bat; return; }
          ds.forEach(function (x) { if (String(x.id) === id) x.bat = bat ? 1 : 0; });
          var tr2 = t.closest("tr"); if (tr2) tr2.classList.toggle("fp-off", !bat);
          DS.toast(bat ? "Đã bật đăng cho Trang" : "Đã tắt, Trang không đăng gì cho tới khi bật lại", "ok");
        });
      }
    });
    // chọn dải bằng Shift và kéo chọn dọc cột ô chọn
    el.addEventListener("mousedown", function (e) {
      var o = e.target.closest("td.fp-cbo");
      if (!o || e.button !== 0) return;
      var tr = o.closest("tr"), i = +tr.getAttribute("data-i"), l = loc(), x = l[i];
      if (!x) return;
      e.preventDefault();
      vuaKeo = true;
      var val = !chon[x.id];
      if (e.shiftKey && cuoi >= 0) {
        var a = Math.min(cuoi, i), b = Math.max(cuoi, i);
        for (var k = a; k <= b; k++) if (l[k]) chon[l[k].id] = val;
      } else { chon[x.id] = val; keo = { val: val }; }
      cuoi = i;
      dongBoChon(); veBulk();
    });
    el.addEventListener("mouseover", function (e) {
      if (!keo) return;
      var tr = e.target.closest("tbody tr[data-i]");
      if (!tr) return;
      var x = loc()[+tr.getAttribute("data-i")];
      if (x && !!chon[x.id] !== keo.val) { chon[x.id] = keo.val; cuoi = +tr.getAttribute("data-i"); dongBoChon(); veBulk(); }
    });
    function thaKeo() { keo = null; if (!ctx.alive) document.removeEventListener("mouseup", thaKeo); }
    document.addEventListener("mouseup", thaKeo);
    el.addEventListener("click", function (e) {
      if (vuaKeo && e.target.closest("td.fp-cbo")) { e.preventDefault(); }
      vuaKeo = false;
      if (!e.target.closest(".fp-dd")) { var mn = el.querySelector("#tr-menu"); if (mn) mn.hidden = true; }
    }, true);
    function dongBoChon() {
      Array.prototype.forEach.call(el.querySelectorAll("tbody tr[data-id]"), function (tr) {
        var id = tr.getAttribute("data-id"), on = !!chon[id], cb = tr.querySelector("[data-chon]");
        tr.classList.toggle("fp-on", on); if (cb) cb.checked = on;
      });
      var all = el.querySelector("#tr-all"); if (all) all.checked = loc().every(function (x) { return chon[x.id]; });
    }

    DS.bind(el, {
      "tai-lai": function () { FP.boNho(); nap(true); },
      "loc-nhom": function (t) { F.nhom = t.getAttribute("data-v"); veLoc(); veDs(); },
      "bo-chon": function () { chon = {}; veBulk(); veDs(); },
      "mo-menu": function () { var mn = el.querySelector("#tr-menu"); if (mn) mn.hidden = !mn.hidden; },
      "dong-bo": function (b) {
        b.disabled = true;
        FP.api("POST", "/trang/dong-bo", {}).then(function (d) {
          b.disabled = false;
          if (d.ok === false) return;
          var loi = d.loi || [];
          DS.toast("Đã đồng bộ " + FP.so(d.so) + " Trang" + (d.moi ? ", " + d.moi + " Trang mới" : "") + (loi.length ? ", " + loi.length + " nguồn lỗi" : ""), loi.length ? "info" : "ok");
          if (loi.length) DS.modal({ title: "Một số nguồn token lỗi khi đồng bộ", body: '<div class="dd-ds">' + loi.map(function (x) {
            return '<div class="dd-dong"><span class="grow small">' + esc(typeof x === "string" ? x : (x.nhan || x.id || "") + ": " + (x.loi || "")) + "</span></div>"; }).join("") +
            '</div><p class="small muted">Kiểm tra từng token ở tab <a href="#/fp-trang?tab=token">Token</a>.</p>' });
          FP.boNho(); nap(true);
        });
      },
      "sua": function (t) {
        var id = t.getAttribute("data-id"), x = ds.filter(function (y) { return String(y.id) === id; })[0];
        if (!x) return;
        var rieng = x.nguon_cau_hinh === "trang" || Object.keys(x.cau_hinh || {}).length > 0;
        moCauHinh({ tieuDe: "Cấu hình " + (x.ten || x.id), keThua: true, rieng: rieng, ch: rieng ? FP.gop(x.cau_hinh_hieu_luc || {}, x.cau_hinh || {}) : (x.cau_hinh_hieu_luc || {}),
          them: '<div class="fld mb"><label for="sc-nhom">Nhóm</label><select class="sel" id="sc-nhom"><option value="">Chưa nhóm</option>' + dsNhom.map(function (n) {
            return '<option value="' + esc(n.id) + '"' + (String(n.id) === String(x.nhom_id) ? " selected" : "") + ">" + esc(n.ten) + "</option>"; }).join("") + "</select></div>",
          luu: function (ch, mb) {
            var nv = mb.querySelector("#sc-nhom").value;
            return FP.api("PATCH", "/trang/" + encodeURIComponent(id), { nhom_id: nv ? (isNaN(+nv) ? nv : +nv) : null, cau_hinh: ch || {} }).then(function (d) {
              if (d.ok === false) return false;
              DS.toast("Đã lưu cấu hình " + (x.ten || ""), "ok"); FP.boNho(); nap(true); return true;
            });
          } });
      },
      "hd": function (t) {
        var hd = t.getAttribute("data-hd"), n = ids().length, mn = el.querySelector("#tr-menu");
        if (mn) mn.hidden = true;
        if (!n) return;
        if (hd === "gan_nhom") moGanNhom();
        else if (hd === "gan_cau_hinh") moCauHinh({ tieuDe: "Gán cấu hình cho " + n + " Trang", keThua: true, rieng: true, ch: {},
          luu: function (ch) { return hanhDong("gan_cau_hinh", { cau_hinh: ch || {} }, "Gán cấu hình"); } });
        else if (hd === "doi_tieu_su") moTieuSu();
        else if (hd === "doi_anh" || hd === "doi_bia") moDoiAnh(hd);
        else if (hd === "bat") hanhDong("bat", {}, "Bật đăng");
        else if (hd === "tat") DS.xacNhan("Tắt đăng cho " + n + " Trang? Bài chờ đăng của các Trang này sẽ đứng yên cho tới khi bật lại.", "Tắt " + n + " Trang", true).then(function (ok) { if (ok) hanhDong("tat", {}, "Tắt đăng"); });
      }
    });
    return nap(false);
  }

  // ================================================================ tab Nhóm
  function tabNhom(el, ctx) {
    var body = el.querySelector("#fp-body"), ds = [], dsKho = [];
    body.innerHTML = DS.skel(4);
    function nap() {
      return Promise.all([FP.api("GET", "/nhom", null, { quiet: true }), FP.layKho(true)]).then(function (a) {
        if (!ctx.alive) return;
        var d = a[0];
        if (d.ok === false) { body.innerHTML = DS.loiThe(d.error, true); return; }
        ds = DS.list(d); dsKho = DS.list(a[1]);
        var h = '<div class="row-sb mb"><span class="small muted">Nhóm gom các Trang dùng chung một lịch, một bộ kho và công tắc. Trang có cấu hình riêng thì riêng ghi đè nhóm.</span>' +
          '<button class="btn btn-pri" data-act="tao">' + ic("plus") + "Tạo nhóm</button></div>";
        if (!ds.length) { body.innerHTML = h + '<div class="card">' + DS.rong("Chưa có nhóm nào", "Tạo nhóm, rồi ở tab Trang chọn nhiều Trang và bấm Hành động, Gán nhóm.", "box") + "</div>"; return; }
        h += '<div class="mau-grid">' + ds.map(function (n) {
          var ch = FP.gop(FP.MAC_DINH, n.cau_hinh || {}), tr = n.trang || [];
          var kho = FP.tenKho(dsKho, ch.kho_noi_dung);
          return '<div class="mau fp-nhom"><div class="mau-top"><span class="ico fp-nhom-ic">' + ic("users") + '</span><div class="grow" style="min-width:0"><div class="mau-t">' + esc(n.ten) + "</div>" +
            (n.mo_ta ? '<div class="mau-d clamp2">' + esc(n.mo_ta) + "</div>" : "") + '</div><span class="bd bd-brand">' + FP.so(n.so_trang != null ? n.so_trang : tr.length) + " Trang</span></div>" +
            '<div class="stack small"><div class="row" style="gap:6px">' + ic("clock") + esc(FP.moTaLich(ch.lich)) + '</div><div class="row" style="gap:6px">' + ic("box") +
            (kho ? esc(kho) : '<span class="muted">Chưa gắn kho nội dung</span>') + "</div></div>" + FP.chipCongTac(ch) +
            (tr.length ? '<div class="row" style="gap:4px">' + tr.slice(0, 8).map(function (t) { return '<span title="' + esc(t.ten || t.id) + '">' + FP.avTrang(t, "av-s") + "</span>"; }).join("") +
              (tr.length > 8 ? '<span class="tiny muted">+' + (tr.length - 8) + "</span>" : "") + "</div>" : "") +
            '<div class="mau-f"><a class="small" href="#/fp-trang?tab=trang&nhom=' + encodeURIComponent(n.id) + '">Xem Trang</a><span class="row">' +
            '<button class="btn btn-xs btn-dan" data-act="xoa" data-id="' + esc(n.id) + '" aria-label="Xoá nhóm">' + ic("trash") + '</button><button class="btn btn-sm btn-soft" data-act="sua" data-id="' + esc(n.id) + '">' + ic("edit") +
            "Sửa cấu hình</button></span></div></div>";
        }).join("") + "</div>";
        body.innerHTML = h;
      });
    }
    function moSua(n) {
      n = n || {};
      moCauHinh({ tieuDe: n.id ? "Nhóm " + n.ten : "Tạo nhóm", ch: n.cau_hinh || {},
        them: '<div class="fgrid mb"><div class="fld"><label for="nh-ten">Tên nhóm <span class="req">*</span></label><input class="inp" id="nh-ten" value="' + esc(n.ten || "") +
          '" placeholder="Ví dụ: Trang phim lẻ"></div><div class="fld"><label for="nh-mt">Ghi chú</label><input class="inp" id="nh-mt" value="' + esc(n.mo_ta || "") + '" placeholder="Tuỳ chọn"></div></div>',
        luu: function (ch, mb) {
          var ten = mb.querySelector("#nh-ten").value.trim();
          if (!ten) { DS.toast("Nhập tên nhóm", "err"); return false; }
          var b = { ten: ten, mo_ta: mb.querySelector("#nh-mt").value.trim(), cau_hinh: ch };
          return FP.api(n.id ? "PATCH" : "POST", "/nhom" + (n.id ? "/" + encodeURIComponent(n.id) : ""), b).then(function (d) {
            if (d.ok === false) return false;
            DS.toast(n.id ? "Đã lưu nhóm" : "Đã tạo nhóm", "ok"); FP.boNho(); nap(); return true;
          });
        } });
    }
    DS.bind(body, {
      "tai-lai": nap,
      "tao": function () { moSua(null); },
      "sua": function (t) { moSua(ds.filter(function (x) { return String(x.id) === t.getAttribute("data-id"); })[0]); },
      "xoa": function (t) {
        var id = t.getAttribute("data-id"), n = ds.filter(function (x) { return String(x.id) === id; })[0] || {};
        DS.xacNhan("Xoá nhóm " + (n.ten || "") + "? Các Trang trong nhóm chuyển về Chưa nhóm và dùng cấu hình mặc định.", "Xoá nhóm", true).then(function (ok) {
          if (ok) FP.api("DELETE", "/nhom/" + encodeURIComponent(id)).then(function (d) { if (d.ok !== false) { DS.toast("Đã xoá nhóm", "ok"); FP.boNho(); nap(); } });
        });
      }
    });
    return nap();
  }

  // ================================================================ tab Token
  function tabToken(el, ctx) {
    var body = el.querySelector("#fp-body"), ds = [];
    body.innerHTML = '<div class="note mb">' + ic("info") + "<span>Kết nối <b>Facebook Trang (tự tạo app)</b> ở trang Kết nối của MinMin tự hiện ở đây, không cần dán token. Token dán tay lưu trên máy chủ của bạn, " +
      "giao diện chỉ hiện dạng che (6 ký tự đầu, 4 ký tự cuối).</span></div><div class=\"grid g-21\"><div class=\"card card-x\"><div class=\"card-h\"><h3>Nguồn token</h3><button class=\"btn btn-sm\" data-act=\"tai-lai\">" +
      ic("refresh") + 'Làm mới</button></div><div id="tk-ds">' + DS.skel(3) + "</div></div>" +
      '<div class="card"><div class="card-h"><h3>' + ic("plus") + 'Thêm token</h3></div><div class="fld"><label for="tk-nhan">Nhãn</label><input class="inp" id="tk-nhan" placeholder="Ví dụ: BM phim, nick A"></div>' +
      '<div class="fld"><label for="tk-tok">Token <span class="req">*</span></label><textarea class="ta" id="tk-tok" rows="4" autocomplete="off" spellcheck="false" placeholder="EAAB..."></textarea>' +
      '<div class="hint">User token (quản lý nhiều Trang) hoặc page token (một Trang). Cần quyền pages_manage_posts, pages_read_engagement; muốn quản bình luận thêm pages_manage_engagement.</div></div>' +
      '<div class="row-sb mt"><span class="tiny muted">Lưu xong MinMin tự kiểm tra token.</span><button class="btn btn-pri" data-act="them">' + ic("plus") + "Thêm token</button></div></div></div>";
    function nap() {
      return FP.api("GET", "/token").then(function (d) {
        if (!ctx.alive) return;
        var box = body.querySelector("#tk-ds");
        if (d.ok === false) { box.innerHTML = DS.loiThe(d.error, true); return; }
        ds = DS.list(d);
        if (!ds.length) { box.innerHTML = DS.rong("Chưa có nguồn token nào", "Dán token ở khung bên cạnh, hoặc nối Facebook Trang ở trang Kết nối của MinMin.", "box"); return; }
        box.innerHTML = '<div class="tw" style="border-top:0"><table class="tbl" style="min-width:760px"><thead><tr><th>Nguồn</th><th>Token</th><th>Trạng thái</th><th>Hết hạn</th><th class="num">Trang</th><th class="num">Đã đăng</th><th></th></tr></thead><tbody>' +
          ds.map(function (x) {
            var kn = x.loai === "ket_noi", sap = x.het_han && x.het_han - DS.bayGio() < 7 * 86400;
            return "<tr><td><b>" + esc(x.nhan || (kn ? "Kết nối Facebook Trang" : "Token #" + x.id)) + '</b><div class="sub">' + esc(FP.LOAI_TOKEN[x.loai] || x.loai || "") + "</div></td>" +
              '<td><code class="fp-code">' + esc(x.che || (kn ? "OAuth, MinMin không giữ token" : "")) + "</code></td><td>" + DS.bdMap(FP.TT_TOKEN, x.trang_thai || "chua_kiem") +
              (x.loi ? '<div class="tiny" style="color:var(--err);max-width:220px">' + esc(x.loi) + "</div>" : "") + (x.kiem_luc ? '<div class="sub">kiểm ' + esc(DS.tuongDoi(x.kiem_luc)) + "</div>" : "") + "</td>" +
              '<td class="small nw"' + (sap ? ' style="color:var(--warn);font-weight:600"' : "") + ">" + (x.het_han ? esc(DS.gio(x.het_han)) + '<div class="sub">' + esc(DS.tuongDoi(x.het_han)) + "</div>" : '<span class="muted">Không hết hạn / chưa rõ</span>') + "</td>" +
              '<td class="num">' + FP.so(x.so_trang) + '</td><td class="num">' + FP.so(x.so_bai_dang) + '</td><td class="nw" style="text-align:right"><button class="btn btn-xs" data-act="kiem" data-id="' + esc(x.id) + '">' + ic("ok") +
              "Kiểm tra</button> " + (kn ? '<span class="tiny muted" title="Gỡ ở trang Kết nối của MinMin">Gỡ ở Kết nối</span>' : '<button class="btn btn-xs btn-dan" data-act="xoa" data-id="' + esc(x.id) + '" aria-label="Xoá token">' + ic("trash") + "</button>") + "</td></tr>";
          }).join("") + "</tbody></table></div>";
      });
    }
    DS.bind(body, {
      "tai-lai": nap,
      "them": function (b) {
        var tok = body.querySelector("#tk-tok").value.trim(), nhan = body.querySelector("#tk-nhan").value.trim();
        if (tok.length < 20) { DS.toast("Dán token đầy đủ (thường bắt đầu bằng EAA)", "err"); return; }
        b.disabled = true;
        FP.api("POST", "/token", { nhan: nhan, token: tok }).then(function (d) {
          b.disabled = false;
          if (d.ok === false) return;
          body.querySelector("#tk-tok").value = ""; body.querySelector("#tk-nhan").value = "";
          DS.toast("Đã thêm token. Bấm Đồng bộ Trang ở tab Trang để lấy danh sách Trang.", "ok");
          nap();
        });
      },
      "kiem": function (b) {
        b.disabled = true;
        FP.api("POST", "/token/" + encodeURIComponent(b.getAttribute("data-id")) + "/kiem", {}).then(function (d) {
          b.disabled = false;
          if (d.ok !== false) { var x = d.token || d.muc || d; DS.toast(x.trang_thai === "tot" ? "Token dùng tốt" : "Token: " + ((FP.TT_TOKEN[x.trang_thai] || [x.trang_thai || "đã kiểm"])[0]) + (x.loi ? ", " + x.loi : ""), x.trang_thai === "tot" ? "ok" : "info"); }
          nap();
        });
      },
      "xoa": function (b) {
        var id = b.getAttribute("data-id");
        DS.xacNhan("Xoá token này? Trang chỉ có token này sẽ không đăng được nữa cho tới khi thêm token khác.", "Xoá token", true).then(function (ok) {
          if (ok) FP.api("DELETE", "/token/" + encodeURIComponent(id)).then(function (d) { if (d.ok !== false) { DS.toast("Đã xoá token", "ok"); nap(); } });
        });
      }
    });
    return nap();
  }

  DS.view("fp-trang", {
    title: "Trang & Nhóm",
    render: function (el, ctx) {
      var tab = ["trang", "nhom", "token"].indexOf(ctx.q.tab) >= 0 ? ctx.q.tab : "trang";
      el.innerHTML = DS.ph("Trang & Nhóm", "Fanpage đăng bằng Graph API. Gom Trang vào nhóm để dùng chung lịch, kho và công tắc.",
        (tab === "trang" ? '<button class="btn" data-act="tai-lai">' + ic("refresh") + 'Làm mới</button><button class="btn btn-pri" data-act="dong-bo">' + ic("refresh") + "Đồng bộ Trang</button>" : "")) +
        DS.tabs([{ id: "trang", ten: "Trang" }, { id: "nhom", ten: "Nhóm" }, { id: "token", ten: "Token" }], tab, "#/fp-trang?tab=") + '<div id="fp-body" class="stack"></div>';
      return tab === "nhom" ? tabNhom(el, ctx) : tab === "token" ? tabToken(el, ctx) : tabTrang(el, ctx);
    }
  });
})();
