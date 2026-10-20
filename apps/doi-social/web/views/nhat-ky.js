/* Nhật ký hoạt động - #/nhat-ky (tab Hoạt động · Đợt chạy hàng loạt · Lịch sử chạy) */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;

  function kq(e) {
    if (e.ma === "het_bai" || /^hết bài/i.test(e.chi_tiet || "")) return DS.bdMap(DS.KET_QUA, "het_bai");
    return DS.bdMap(DS.KET_QUA, e.ket_qua);
  }
  function tienTrinh(t) {
    t = t || {};
    var tong = t.tong || 0, xong = t.xong || 0, loi = t.loi || 0, dang = t.dang || 0, ok = Math.max(0, xong - loi);
    if (t.thanh_cong != null) ok = t.thanh_cong;
    var pc = function (n) { return tong ? (n / tong * 100).toFixed(1) + "%" : "0"; };
    return '<div class="prog"><div class="bar"><i class="p-ok" style="width:' + pc(ok) + '"></i><i class="p-err" style="width:' + pc(loi) + '"></i><i class="p-run" style="width:' + pc(dang) +
      '"></i></div><span>' + xong + "/" + tong + " · ✓" + ok + " ✗" + loi + "</span></div>";
  }
  DS.tienTrinh = tienTrinh;

  // ================================================================ tab Hoạt động
  function tabHoatDong(el, ctx, KB) {
    var mauId = DS.mauTheoId(KB);
    var tn = {};
    DS.dsMau(KB).forEach(function (m) { if (m.tinh_nang) tn[m.tinh_nang] = 1; });
    var F = { tg: "hom_nay", nick: "", tinh_nang: "", ket_qua: ctx.q.kq || "", tu: "", den: "", trang: 1 };
    var body = el.querySelector("#nk-body");
    body.innerHTML = '<div class="card"><div class="card-h"><h3><span class="dotx on pulse"></span>Đang chạy</h3><span class="tiny muted">Tự làm mới mỗi 5 giây</span></div><div id="nk-dang"><div class="sk sk-line"></div></div></div>' +
      '<div class="card card-x"><div class="card-h"><h3>Hôm nay theo nick</h3></div><div style="height:12px"></div><div class="tw" id="nk-nick"><table class="tbl"><tbody>' + DS.skelDong(3, 5) + "</tbody></table></div></div>" +
      '<div class="card card-x"><div class="card-h"><h3>Dòng thời gian <span class="sub" id="nk-tong"></span></h3><div class="row"><button class="btn btn-sm" data-act="lam-moi">' + ic("refresh") +
      'Làm mới</button><a class="btn btn-sm" id="nk-csv" href="#">' + ic("download") + 'Xuất CSV</a></div></div><div style="height:12px"></div><div class="filters">' +
      '<select class="sel" id="f-tg"><option value="hom_nay">Hôm nay</option><option value="24h">24 giờ qua</option><option value="7d">7 ngày</option><option value="30d">30 ngày</option><option value="tuy">Tuỳ chọn</option></select>' +
      '<span id="f-tuy" hidden class="row"><input class="inp" type="datetime-local" id="f-tu"><span class="muted">đến</span><input class="inp" type="datetime-local" id="f-den"></span>' +
      '<select class="sel" id="f-nick"><option value="">Mọi nick</option></select>' +
      '<select class="sel" id="f-tn"><option value="">Mọi tính năng</option>' + Object.keys(tn).sort().map(function (x) { return "<option>" + esc(x) + "</option>"; }).join("") + "</select>" +
      '<select class="sel" id="f-kq"><option value="">Mọi kết quả</option><option value="thanh_cong">Thành công</option><option value="bo_qua">Bỏ qua</option><option value="loi">Lỗi</option><option value="thong_tin">Thông tin</option></select>' +
      '</div><div id="nk-tl"></div></div>';
    body.querySelector("#f-kq").value = F.ket_qua;

    DS.layNick().then(function (d) {
      var s = body.querySelector("#f-nick");
      if (!s) return;
      s.innerHTML += DS.list(d, "nick").map(function (n) { return '<option value="' + esc(n.id) + '">' + esc(n.ten) + "</option>"; }).join("");
    });

    function khoang() {
      var now = Date.now() / 1000, tu = "", den = "";
      if (F.tg === "hom_nay") { var d = new Date(); d.setHours(0, 0, 0, 0); tu = d.getTime() / 1000; }
      else if (F.tg === "24h") tu = now - 86400;
      else if (F.tg === "7d") tu = now - 7 * 86400;
      else if (F.tg === "30d") tu = now - 30 * 86400;
      else { tu = F.tu ? new Date(F.tu).getTime() / 1000 : ""; den = F.den ? new Date(F.den).getTime() / 1000 : ""; }
      return { tu: tu ? Math.floor(tu) : "", den: den ? Math.floor(den) : "" };
    }
    function boLoc(trang) {
      var k = khoang();
      return { tu: k.tu, den: k.den, nick: F.nick, tinh_nang: F.tinh_nang, ket_qua: F.ket_qua, trang: trang };
    }
    function napDang() {
      return DS.api("GET", "/doi-social/dang-chay", null, { quiet: true }).then(function (d) {
        var box = body.querySelector("#nk-dang");
        if (!box || !ctx.alive) return;
        if (d.ok === false) { box.innerHTML = '<div class="small muted">' + esc(d.error) + "</div>"; return; }
        var ds = DS.list(d, "viec");
        if (!ds.length) { box.innerHTML = '<div class="row small muted" style="padding:6px 0">' + ic("clock") + "Không có nick nào đang chạy.</div>"; return; }
        box.innerHTML = ds.map(function (v) {
          var m = mauId[v.kich_ban || v.ky_nang] || {};
          var buoc = v.buoc || v.nhat_ky || [];
          var cuoi = v.dong || (buoc.length ? buoc[buoc.length - 1] : "");
          return '<div class="run">' + DS.av(v.nick_ten) + '<div class="grow" style="min-width:0"><div class="row"><b>' + esc(v.nick_ten) + "</b>" + DS.icNT(m.nen_tang, 18) +
            '<span class="small">' + esc(m.ten || v.nhan_ky_nang || v.ky_nang || "") + '</span><span class="tiny muted">· bắt đầu ' + esc(DS.tuongDoi(v.bat_dau || v.nhan_luc || v.tao_luc)) + "</span></div>" +
            (cuoi ? '<div class="small muted clip" style="margin-top:3px">' + ic("activity") + " " + esc(cuoi) + "</div>" : "") + "</div>" + DS.bd("Đang chạy", "brand", true) + "</div>";
        }).join("");
      });
    }
    function napNick() {
      return DS.api("GET", "/doi-social/hom-nay-theo-nick", null, { quiet: true }).then(function (d) {
        var box = body.querySelector("#nk-nick");
        if (!box || !ctx.alive) return;
        var ds = DS.list(d, "nick");
        if (d.ok === false || !ds.length) { box.innerHTML = DS.rong("Hôm nay chưa có nick nào chạy", "", "list"); return; }
        box.innerHTML = '<table class="tbl"><thead><tr><th>Nick</th><th class="num">Thành công</th><th class="num">Bỏ qua</th><th class="num">Lỗi</th><th>Chi tiết</th></tr></thead><tbody>' +
          ds.map(function (r) {
            return '<tr><td><div class="row" style="flex-wrap:nowrap">' + DS.av(r.nick_ten) + "<b>" + esc(r.nick_ten) + '</b></div></td><td class="num" style="color:var(--ok);font-weight:600">' + DS.so(r.thanh_cong) +
              '</td><td class="num muted">' + DS.so(r.bo_qua) + '</td><td class="num" style="' + (r.loi ? "color:var(--err);font-weight:600" : "") + '">' + DS.so(r.loi) + '</td><td class="small muted">' + esc(r.chi_tiet || "") + "</td></tr>";
          }).join("") + "</tbody></table>";
      });
    }
    function napTL() {
      var box = body.querySelector("#nk-tl");
      var bl = boLoc(F.trang);
      body.querySelector("#nk-csv").href = "/doi-social/su-kien.csv" + DS.qs({ tu: bl.tu, den: bl.den, nick: bl.nick, tinh_nang: bl.tinh_nang, ket_qua: bl.ket_qua });
      box.innerHTML = '<div class="tw"><table class="tbl tbl-in"><tbody>' + DS.skelDong(6, 6) + "</tbody></table></div>";
      return DS.api("GET", "/doi-social/su-kien" + DS.qs(bl)).then(function (d) {
        if (!ctx.alive) return;
        if (d.ok === false) { box.innerHTML = DS.rong("Chưa tải được dòng thời gian", esc(d.error), "list"); return; }
        var ds = DS.list(d, "su_kien"), tong = d.tong != null ? d.tong : ds.length;
        body.querySelector("#nk-tong").textContent = DS.so(tong) + " sự kiện";
        if (!ds.length) { box.innerHTML = DS.rong("Không có sự kiện nào", "Đổi khoảng thời gian hoặc bỏ bớt bộ lọc.", "list"); return; }
        box.innerHTML = '<div class="tw" style="border-top:0"><table class="tbl tbl-in"><thead><tr><th>Thời gian</th><th>Nick</th><th>Việc</th><th>Nhóm</th><th>Kết quả</th><th>Chi tiết</th></tr></thead><tbody>' +
          ds.map(function (e) {
            var m = mauId[e.kich_ban] || {};
            return '<tr><td class="nw"><b>' + DS.gioPhut(e.luc) + '</b><div class="sub">' + esc(DS.gio(e.luc).slice(0, 5)) + '</div></td><td class="nw"><div class="row" style="flex-wrap:nowrap">' +
              DS.icNT(e.nen_tang || m.nen_tang, 18) + esc(e.nick_ten || "") + "</div></td><td><div class=\"b\" style=\"font-weight:500\">" + esc(DS.tenHD(KB, e.hanh_dong) || m.ten || "") +
              '</div><div class="sub">' + esc(e.tinh_nang || m.tinh_nang || "") + '</div></td><td style="max-width:220px"><div class="clip">' + esc(e.nhom || "") + '</div><div class="sub clip">' +
              esc(e.san_pham || "") + "</div></td><td>" + kq(e) + '</td><td style="min-width:220px;max-width:380px"><div class="small">' + esc(e.chi_tiet || "") + "</div>" +
              (e.link ? '<a class="tiny" href="' + esc(e.link) + '" target="_blank" rel="noopener">' + ic("link") + " Mở bài</a>" : "") + "</td></tr>";
          }).join("") + "</tbody></table></div>" + DS.phanTrang(tong, d.trang || F.trang, d.moi_trang || 50);
      });
    }
    function tatCa() { napDang(); napNick(); return napTL(); }

    body.addEventListener("change", function (e) {
      var t = e.target;
      if (t.id === "f-tg") { F.tg = t.value; body.querySelector("#f-tuy").hidden = F.tg !== "tuy"; if (F.tg === "tuy") return; }
      else if (t.id === "f-tu") F.tu = t.value;
      else if (t.id === "f-den") F.den = t.value;
      else if (t.id === "f-nick") F.nick = t.value;
      else if (t.id === "f-tn") F.tinh_nang = t.value;
      else if (t.id === "f-kq") F.ket_qua = t.value;
      else return;
      F.trang = 1; napTL();
    });
    DS.bind(body, {
      "lam-moi": function () { tatCa(); },
      "trang": function (t) { F.trang = +t.getAttribute("data-trang") || 1; napTL(); }
    });
    ctx.every(napDang, 5000);
    ctx.every(napNick, 30000);
    return tatCa();
  }

  // ================================================================ tab Đợt chạy hàng loạt
  function tabDot(el, ctx, KB) {
    var mauId = DS.mauTheoId(KB), loc = "";
    var body = el.querySelector("#nk-body");
    body.innerHTML = '<div class="card card-x"><div class="card-h"><h3>Đợt chạy hàng loạt <span class="sub" id="dt-tong"></span></h3><a class="btn btn-sm btn-soft" href="#/chay-hang-loat">' +
      ic("plus") + 'Chạy hàng loạt</a></div><div style="height:12px"></div><div class="filters"><div class="chips" id="dt-loc">' +
      [["", "Tất cả"], ["dang_chay", "Đang chạy"], ["cho", "Đang chờ"], ["hoan_tat", "Hoàn tất"], ["huy", "Đã huỷ"]].map(function (x) {
        return '<button class="chip' + (x[0] === loc ? " on" : "") + '" data-act="loc" data-v="' + x[0] + '">' + x[1] + "</button>";
      }).join("") + '</div></div><div id="dt-ds"></div></div>';
    function nap() {
      var box = body.querySelector("#dt-ds");
      return DS.api("GET", "/doi-social/dot-chay" + DS.qs({ trang_thai: loc })).then(function (d) {
        if (!ctx.alive) return;
        if (d.ok === false) { box.innerHTML = DS.rong("Chưa tải được", esc(d.error), "list"); return; }
        var ds = DS.list(d, "dot");
        body.querySelector("#dt-tong").textContent = DS.so(d.tong != null ? d.tong : ds.length) + " đợt";
        if (!ds.length) { box.innerHTML = DS.rong("Chưa có đợt chạy nào", "Tạo đợt đầu tiên từ một mẫu ở Automation.", "list", '<a class="btn btn-pri" href="#/chay-hang-loat">' + ic("play") + "Chạy hàng loạt</a>"); return; }
        box.innerHTML = '<div class="tw" style="border-top:0"><table class="tbl tbl-in"><thead><tr><th>Tên</th><th>Mẫu</th><th>Trạng thái</th><th>Tiến trình</th><th class="num">Song song</th><th>Nguồn</th><th>Tạo lúc</th></tr></thead><tbody>' +
          ds.map(function (x) {
            var m = mauId[x.kich_ban] || {};
            return '<tr class="click" data-act="mo-dot" data-id="' + x.id + '"><td><b>' + esc(x.ten || "Đợt #" + x.id) + '</b><div class="sub">' + (x.nick || []).length + ' nick</div></td><td><div class="row" style="flex-wrap:nowrap">' +
              DS.icNT(m.nen_tang, 18) + '<span class="clip" style="max-width:200px">' + esc(m.ten || x.kich_ban) + "</span></div>" + (x.chay_thu ? DS.bd("Chạy thử", "brand") : "") + "</td><td>" +
              DS.bdMap(DS.TT_DOT, x.trang_thai) + "</td><td>" + tienTrinh(x.tien_trinh) + '</td><td class="num">' + (x.song_song || 1) + '</td><td class="small muted">' +
              esc({ web: "Trang web", lich: "Lịch hẹn", tro_ly: "Trợ lý AI", telegram: "Telegram" }[x.nguon] || x.nguon || "") + '</td><td class="nw small">' + DS.gio(x.tao_luc) + "</td></tr>";
          }).join("") + "</tbody></table></div>";
      });
    }
    function moDot(id) {
      var m = DS.modal({ title: "Đợt #" + id, wide: true, body: DS.skel(5) });
      function ve() {
        DS.api("GET", "/doi-social/dot-chay/" + id).then(function (d) {
          if (d.ok === false) { m.body.innerHTML = DS.rong("Chưa tải được", esc(d.error), "list"); return; }
          var dot = d.dot || d, viec = d.viec || [], sk = d.su_kien || [], mau = mauId[dot.kich_ban] || {};
          m.el.querySelector(".modal-h h3").textContent = dot.ten || "Đợt #" + id;
          var h = '<div class="row-sb"><div class="row">' + DS.icNT(mau.nen_tang, 26) + "<b>" + esc(mau.ten || dot.kich_ban) + "</b>" + DS.bdMap(DS.TT_DOT, dot.trang_thai) + (dot.chay_thu ? DS.bd("Chạy thử", "brand") : "") +
            '</div><div style="min-width:220px">' + tienTrinh(dot.tien_trinh) + "</div></div>" +
            '<div class="small muted mt-s">Tạo ' + DS.gioDu(dot.tao_luc) + (dot.xong_luc ? " · xong " + DS.gioDu(dot.xong_luc) : "") + " · song song " + (dot.song_song || 1) + (dot.chay_an ? " · chạy ẩn" : "") + "</div>";
          var ts = dot.tham_so || {};
          if (Object.keys(ts).length) h += '<div class="logbox mt-s" style="max-height:120px">' + esc(Object.keys(ts).map(function (k) { return k + ": " + (Array.isArray(ts[k]) ? ts[k].join(", ") : ts[k]); }).join("\n")) + "</div>";
          h += '<div class="sec-t" style="margin-top:16px">Việc theo nick (' + viec.length + ')</div><div class="tw" style="border:1px solid var(--line);border-radius:12px"><table class="tbl"><thead><tr><th>Nick</th><th>Trạng thái</th><th>Kết quả</th><th>Máy báo</th></tr></thead><tbody>' +
            (viec.length ? viec.map(function (v) {
              var dm = v.ket_qua || v.dem || {};
              return "<tr><td><b>" + esc(v.nick_ten) + "</b></td><td>" + DS.bdMap(DS.TT_VIEC, v.trang_thai) + '</td><td class="small nw">✓' + (dm.thanh_cong || 0) + " · bỏ qua " + (dm.bo_qua || 0) + " · ✗" + (dm.loi || 0) +
                '</td><td class="small muted">' + esc(v.thong_diep || "") + "</td></tr>";
            }).join("") : '<tr><td colspan="4" class="muted">Chưa có việc.</td></tr>') + "</tbody></table></div>";
          if (sk.length) h += '<div class="sec-t" style="margin-top:16px">Sự kiện gần nhất</div><div class="logbox">' + sk.map(function (e) {
            return esc(DS.gioPhut(e.luc) + "  " + (e.nick_ten || "") + "  [" + ((DS.KET_QUA[e.ket_qua] || [e.ket_qua])[0]) + "]  " + (e.chi_tiet || ""));
          }).join("\n") + "</div>";
          m.body.innerHTML = h;
          var dang = dot.trang_thai === "cho" || dot.trang_thai === "dang_chay";
          m.foot.innerHTML = (dang ? '<button class="btn btn-dan" data-huy>' + ic("stop") + "Huỷ đợt</button>" : "") + '<button class="btn" data-x>Đóng</button>';
          var b = m.foot.querySelector("[data-huy]");
          if (b) b.onclick = function () {
            DS.xacNhan("Huỷ đợt này? Việc chưa chạy sẽ bị bỏ, việc đang chạy được báo dừng.", "Huỷ đợt", true).then(function (ok) {
              if (!ok) return;
              DS.api("POST", "/doi-social/dot-chay/" + id + "/huy", {}).then(function (r) { if (r.ok !== false) { DS.toast("Đã huỷ đợt", "ok"); ve(); nap(); } });
            });
          };
        });
      }
      ve();
    }
    DS.bind(body, {
      "loc": function (t) {
        loc = t.getAttribute("data-v");
        Array.prototype.forEach.call(body.querySelectorAll("#dt-loc .chip"), function (c) { c.classList.toggle("on", c === t); });
        nap();
      },
      "mo-dot": function (t) { moDot(t.getAttribute("data-id")); }
    });
    ctx.every(nap, 10000);
    return nap();
  }

  // ================================================================ tab Lịch sử chạy
  function tabLichSu(el, ctx, KB) {
    var mauId = DS.mauTheoId(KB), F = { trang_thai: "", kich_ban: "", trang: 1 }, cache = {};
    var body = el.querySelector("#nk-body");
    body.innerHTML = '<div class="card card-x"><div class="card-h"><h3>Lịch sử chạy <span class="sub" id="ls-tong"></span></h3></div><div style="height:12px"></div><div class="filters">' +
      '<select class="sel" id="ls-tt"><option value="">Mọi trạng thái</option><option value="cho_chay">Chờ máy nhận</option><option value="dang_chay">Đang chạy</option><option value="xong">Thành công</option><option value="loi">Thất bại</option><option value="bo">Đã huỷ</option></select>' +
      '<select class="sel" id="ls-mau"><option value="">Mọi mẫu</option>' + DS.dsMau(KB).map(function (m) { return '<option value="' + esc(m.id) + '">' + esc(DS.tenNT(m.nen_tang) + " · " + m.ten) + "</option>"; }).join("") +
      '</select></div><div id="ls-ds"></div></div>';
    function nap() {
      var box = body.querySelector("#ls-ds");
      box.innerHTML = '<div class="tw" style="border-top:0"><table class="tbl tbl-in"><tbody>' + DS.skelDong(6, 6) + "</tbody></table></div>";
      return DS.api("GET", "/doi-social/lich-su" + DS.qs(F)).then(function (d) {
        if (!ctx.alive) return;
        if (d.ok === false) { box.innerHTML = DS.rong("Chưa tải được", esc(d.error), "list"); return; }
        var ds = DS.list(d, "viec"), tong = d.tong != null ? d.tong : ds.length;
        body.querySelector("#ls-tong").textContent = DS.so(tong) + " kết quả";
        if (!ds.length) { box.innerHTML = DS.rong("Chưa có lượt chạy nào", "", "list"); return; }
        ds.forEach(function (v) { cache[v.id] = v; });
        box.innerHTML = '<div class="tw" style="border-top:0"><table class="tbl tbl-in"><thead><tr><th>#</th><th>Đợt</th><th>Mẫu</th><th>Nick</th><th>Trạng thái</th><th>Bắt đầu</th><th></th></tr></thead><tbody>' +
          ds.map(function (v) {
            var m = mauId[v.kich_ban || v.ky_nang] || {};
            return '<tr><td class="muted small">#' + v.id + '</td><td class="small">' + esc(v.dot_ten || (v.dot_id ? "Đợt #" + v.dot_id : "Việc lẻ")) + '</td><td><div class="row" style="flex-wrap:nowrap">' + DS.icNT(m.nen_tang, 18) +
              '<span class="clip" style="max-width:220px">' + esc(v.mau_ten || m.ten || v.nhan_ky_nang || v.ky_nang || "") + "</span></div></td><td><b>" + esc(v.nick_ten || "") + "</b></td><td>" + DS.bdMap(DS.TT_VIEC, v.trang_thai) +
              (v.chay_thu ? " " + DS.bd("Chạy thử", "brand") : "") + '</td><td class="nw small">' + DS.gio(v.bat_dau || v.nhan_luc || v.tao_luc) + '</td><td><button class="btn btn-xs" data-act="xem" data-id="' + v.id + '">' + ic("eye") + "Xem</button></td></tr>";
          }).join("") + "</tbody></table></div>" + DS.phanTrang(tong, d.trang || F.trang, d.moi_trang || 50);
      });
    }
    function xem(v) {
      var m = mauId[v.kich_ban || v.ky_nang] || {}, buoc = v.buoc || [];
      DS.modal({ title: "Lượt #" + v.id + " · " + (v.nick_ten || ""), wide: true,
        body: '<div class="row">' + DS.icNT(m.nen_tang, 24) + "<b>" + esc(m.ten || v.nhan_ky_nang || v.ky_nang || "") + "</b>" + DS.bdMap(DS.TT_VIEC, v.trang_thai) + "</div>" +
          '<div class="small muted mt-s">Tạo ' + DS.gioDu(v.tao_luc) + (v.xong_luc ? " · xong " + DS.gioDu(v.xong_luc) : "") + "</div>" +
          (v.thong_diep ? '<div class="note mt-s ' + (v.trang_thai === "loi" ? "note-err" : "") + '">' + ic(v.trang_thai === "loi" ? "alert" : "info") + "<span>" + esc(v.thong_diep) + "</span></div>" : "") +
          '<div class="sec-t" style="margin-top:16px">Các bước máy ở nhà ghi lại</div>' + (buoc.length ? '<div class="logbox">' + buoc.map(esc).join("\n") + "</div>" : '<div class="small muted">Không có bước nào.</div>') +
          (v.co_anh ? '<div class="sec-t" style="margin-top:16px">Ảnh chụp màn hình</div><img class="shot" loading="lazy" src="/doi-social/anh/' + encodeURIComponent(v.id) + '.png" alt="Ảnh chụp kết quả lượt ' + v.id + '">' : "") });
    }
    body.addEventListener("change", function (e) {
      if (e.target.id === "ls-tt") F.trang_thai = e.target.value;
      else if (e.target.id === "ls-mau") F.kich_ban = e.target.value;
      else return;
      F.trang = 1; nap();
    });
    DS.bind(body, {
      "trang": function (t) { F.trang = +t.getAttribute("data-trang") || 1; nap(); },
      "xem": function (t) { var v = cache[t.getAttribute("data-id")]; if (v) xem(v); }
    });
    return nap();
  }

  DS.view("nhat-ky", {
    title: "Nhật ký hoạt động",
    render: function (el, ctx) {
      var tab = ["hoat-dong", "dot", "lich-su"].indexOf(ctx.q.tab) >= 0 ? ctx.q.tab : "hoat-dong";
      el.innerHTML = DS.ph("Nhật ký hoạt động", "Mọi thao tác máy ở nhà đã làm, theo từng nick, từng đợt.") +
        DS.tabs([{ id: "hoat-dong", ten: "Hoạt động" }, { id: "dot", ten: "Đợt chạy hàng loạt" }, { id: "lich-su", ten: "Lịch sử chạy" }], tab, "#/nhat-ky?tab=") +
        '<div id="nk-body" class="stack">' + DS.skel(6) + "</div>";
      return DS.layKichBan().then(function (kb) {
        if (!ctx.alive) return;
        if (tab === "dot") return tabDot(el, ctx, kb);
        if (tab === "lich-su") return tabLichSu(el, ctx, kb);
        return tabHoatDong(el, ctx, kb);
      });
    }
  });
})();
