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
    var tong = t.tong || 0, ok = t.xong || 0, loi = t.loi || 0, dang = t.dang || 0, bo = t.bo || 0, tam = t.tam || 0, xong = ok + loi + bo;
    var pc = function (n) { return tong ? (n / tong * 100).toFixed(1) + "%" : "0"; };
    return '<div class="prog"><div class="bar"><i class="p-ok" style="width:' + pc(ok) + '"></i><i class="p-err" style="width:' + pc(loi) + '"></i><i class="p-run" style="width:' + pc(dang) +
      '"></i><i class="p-tam" style="width:' + pc(tam) + '"></i></div><span>' + xong + "/" + tong + " · ✓" + ok + " ✗" + loi +
      (tam ? ' · <b style="color:var(--warn);font-weight:600">' + tam + " tạm dừng</b>" : "") + "</span></div>";
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
      '<div class="card card-x"><div class="card-h"><h3>Hôm nay theo nick</h3></div><div class="tw" id="nk-nick"><table class="tbl"><tbody>' + DS.skelDong(3, 5) + "</tbody></table></div></div>" +
      '<div class="card card-x"><div class="card-h"><h3>Dòng thời gian <span class="sub" id="nk-tong"></span></h3><div class="row"><button class="btn btn-sm" data-act="lam-moi">' + ic("refresh") +
      'Làm mới</button><a class="btn btn-sm" id="nk-csv" href="#">' + ic("download") + 'Xuất CSV</a></div></div><div class="filters">' +
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
        dangDs = DS.list(d, "viec");
        veDang();
      });
    }
    var dangDs = [];
    function veDang() {
      var box = body.querySelector("#nk-dang");
      if (!box) return;
      if (!dangDs.length) { box.innerHTML = '<div class="row small muted" style="padding:6px 0">' + ic("clock") + "Không có nick nào đang chạy.</div>"; return; }
      box.innerHTML = dangDs.map(function (v) {
        var m = mauId[v.ky_nang] || {};
        var nk = v.nhat_ky || [], cuoi = v.buoc_cuoi || (nk.length ? (nk[nk.length - 1].dong || nk[nk.length - 1]) : "");
        return '<div class="run' + (DS.viecTam(v) ? " tam" : "") + '" data-vid="' + esc(v.id) + '">' + DS.av(v.nick_ten) + '<div class="grow" style="min-width:0"><div class="row"><b>' + esc(v.nick_ten) + "</b>" + DS.icNT(m.nen_tang, 18) +
          '<span class="small">' + esc(v.ten_mau || m.ten || v.ky_nang || "") + '</span><span class="tiny muted">· bắt đầu ' + esc(DS.tuongDoi(v.bat_dau || v.nhan_luc || v.tao_luc)) + "</span>" +
          (v.dot_id ? '<a class="tiny" href="#/nhat-ky?tab=dot&dot=' + encodeURIComponent(v.dot_id) + '">Đợt #' + esc(v.dot_id) + "</a>" : "") + DS.ttViec(v) + "</div>" +
          (cuoi ? '<div class="vr-buoc">' + ic("activity") + "<span>" + esc(cuoi) + "</span></div>" : "") + "</div>" + DS.nutViec(v) + "</div>";
      }).join("");
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
              DS.icNT(e.nen_tang || m.nen_tang, 18) + esc(e.nick_ten || "") + "</div></td><td><div class=\"b\" style=\"font-weight:500\">" + esc(e.nhan_hanh_dong || DS.tenHD(KB, e.hanh_dong) || m.ten || "") +
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
      "dk-viec": function (t) {
        var id = t.getAttribute("data-id"), v = dangDs.filter(function (x) { return String(x.id) === id; })[0] || {};
        DS.dieuKhienViec(id, t.getAttribute("data-hd"), v.nick_ten, t).then(function (moi) {
          if (!moi || !ctx.alive) return;
          dangDs = dangDs.map(function (x) { return String(x.id) === id ? Object.assign({}, x, moi, { nhat_ky: x.nhat_ky, buoc_cuoi: x.buoc_cuoi }) : x; }).filter(function (x) { return x.trang_thai === "dang_chay"; });
          veDang();
        });
      },
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
      ic("plus") + 'Chạy hàng loạt</a></div><div class="filters"><div class="chips" id="dt-loc">' +
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
              DS.icNT(m.nen_tang, 18) + '<span class="clip" style="max-width:200px">' + esc(x.ten_mau || m.ten || x.kich_ban) + "</span></div>" + (x.chay_thu ? DS.bd("Chạy thử", "brand") : "") + "</td><td>" +
              DS.bdMap(DS.TT_DOT, x.trang_thai) + "</td><td>" + tienTrinh(x.tien_trinh) + '</td><td class="num">' + (x.song_song || 1) + '</td><td class="small muted nw">' +
              esc({ web: "Trang web", lich: "Lịch hẹn", tro_ly: "Trợ lý AI", telegram: "Telegram" }[x.nguon] || x.nguon || "") + '</td><td class="nw small">' + DS.gio(x.tao_luc) + "</td></tr>";
          }).join("") + "</tbody></table></div>";
      });
    }
    DS.bind(body, {
      "loc": function (t) {
        loc = t.getAttribute("data-v");
        Array.prototype.forEach.call(body.querySelectorAll("#dt-loc .chip"), function (c) { c.classList.toggle("on", c === t); });
        nap();
      },
      "mo-dot": function (t) { DS.datQ({ dot: t.getAttribute("data-id") }); }
    });
    ctx.every(nap, 10000);
    return nap();
  }

  // ================================================================ chi tiết một đợt: #/nhat-ky?tab=dot&dot=<id>
  function xemViec(v, mauId) {
    var m = mauId[v.kich_ban || v.ky_nang] || {}, buoc = v.buoc || [];
    DS.modal({ title: "Lượt #" + v.id + " · " + (v.nick_ten || ""), wide: true,
      body: '<div class="row">' + DS.icNT(m.nen_tang, 24) + "<b>" + esc(v.ten_mau || m.ten || v.nhan_ky_nang || v.ky_nang || "") + "</b>" + DS.ttViec(v) + "</div>" +
        '<div class="small muted mt-s">Tạo ' + DS.gioDu(v.tao_luc) + (v.xong_luc ? " · xong " + DS.gioDu(v.xong_luc) : "") + "</div>" +
        (v.thong_diep ? '<div class="note mt-s ' + (v.trang_thai === "loi" ? "note-err" : "") + '">' + ic(v.trang_thai === "loi" ? "alert" : "info") + "<span>" + esc(v.thong_diep) + "</span></div>" : "") +
        '<div class="sec-t" style="margin-top:16px">Các bước máy ở nhà ghi lại</div>' + (buoc.length ? '<div class="logbox">' + buoc.map(function (b) { return esc(typeof b === "string" ? b : (b.dong || JSON.stringify(b))); }).join("\n") + "</div>" : '<div class="small muted">Không có bước nào.</div>') +
        (v.co_anh ? '<div class="sec-t" style="margin-top:16px">Ảnh chụp màn hình</div><img class="shot" loading="lazy" src="/doi-social/anh/' + encodeURIComponent(v.id) + '.png" alt="Ảnh chụp kết quả lượt ' + v.id + '">' : "") });
  }
  DS.xemViec = xemViec;

  function tabChiTietDot(el, ctx, KB, id) {
    var mauId = DS.mauTheoId(KB), dot = null, viec = [], buoc = {}, nickTen = {}, linkTen = {};
    var body = el.querySelector("#nk-body");
    body.innerHTML = '<a class="back" href="#/nhat-ky?tab=dot">' + ic("back") + "Tất cả đợt chạy</a>" + DS.skel(6);
    var napNick = DS.layNick().then(function (d) {
      DS.list(d, "nick").forEach(function (n) { nickTen[n.id] = n.ten; (n.dich_den || []).forEach(function (x) { linkTen[x.link] = x.ten; }); });
    });
    function conChay() { return dot && (dot.trang_thai === "cho" || dot.trang_thai === "dang_chay"); }
    function veThamSo(ts) {
      return Object.keys(ts).map(function (k) {
        var v = ts[k];
        if (v && typeof v === "object" && !Array.isArray(v)) v = Object.keys(v).map(function (nid) { return (nickTen[nid] || nid) + " → " + (v[nid] ? (linkTen[v[nid]] || v[nid]) : "tường / tài khoản chính"); }).join("; ");
        return k + ": " + (Array.isArray(v) ? v.join(", ") : v);
      }).join("\n");
    }
    function noiDang(v) {
      var ts = ((v.tham_so || {}).tham_so) || {}, m = mauId[dot.kich_ban] || {}, k = (m.tham_so || []).filter(function (f) { return f.kieu === "dich_den"; })[0];
      if (!k) return "";
      var l = ts[k.key];
      return '<span class="tiny muted clip" style="max-width:240px" title="' + esc(l || "") + '">' + ic("chevr") + esc(l ? (linkTen[l] || "Trang đã chọn") : (k.nen_tang === "facebook" || !k.nen_tang ? "Tường cá nhân" : "Tài khoản chính")) + "</span>";
    }
    function dongViec(v) {
      var dm = v.ket_qua || v.dem || {}, cuoi = v.trang_thai === "dang_chay" ? buoc[v.id] : "";
      var phu = cuoi ? '<div class="vr-buoc">' + ic("activity") + "<span>" + esc(cuoi) + "</span></div>" : v.thong_diep ? '<div class="vr-buoc"><span>' + esc(v.thong_diep) + "</span></div>" : "";
      return '<div class="vr' + (DS.viecTam(v) ? " tam" : "") + '" data-vid="' + esc(v.id) + '">' + DS.av(v.nick_ten) + '<div class="vr-main"><div class="vr-t"><b class="clip" style="max-width:260px">' + esc(v.nick_ten) + "</b>" + DS.ttViec(v) +
        noiDang(v) + "</div>" + phu + "</div>" +
        (DS.viecXong(v) || (dm.thanh_cong || dm.loi || dm.bo_qua) ? '<span class="vr-kq">✓' + (dm.thanh_cong || 0) + " · bỏ qua " + (dm.bo_qua || 0) + " · ✗" + (dm.loi || 0) + "</span>" : "") +
        '<span class="vr-act">' + DS.nutViec(v) + '<button class="btn btn-xs btn-ghost" type="button" data-act="xem" data-id="' + esc(v.id) + '" title="Xem nhật ký và ảnh">' + ic("eye") + "Xem</button></span></div>";
    }
    function veDs() {
      var box = body.querySelector("#dc-viec");
      if (!box) return;
      body.querySelector("#dc-so").textContent = "(" + viec.length + ")";
      box.innerHTML = viec.length ? viec.map(dongViec).join("") : '<div class="small muted" style="padding:14px">Chưa có việc.</div>';
    }
    function veDau() {
      var mau = mauId[dot.kich_ban] || {}, tam = viec.some(DS.viecTam), chayDuoc = viec.some(function (v) { return !DS.viecXong(v) && !DS.viecTam(v) && v.lenh !== "huy"; });
      var h = '<div class="row-sb"><div class="row" style="min-width:0">' + DS.icNT(mau.nen_tang, 30) + '<div style="min-width:0"><h3 style="margin:0;font-size:16px">' + esc(dot.ten || "Đợt #" + dot.id) + '</h3><div class="row small muted" style="gap:6px;margin-top:2px">' +
        esc(dot.ten_mau || mau.ten || dot.kich_ban) + DS.bdMap(DS.TT_DOT, dot.trang_thai) + (dot.chay_thu ? DS.bd("Chạy thử", "brand") : "") + "</div></div></div>" +
        (conChay() ? '<div class="dot-act">' + (chayDuoc ? '<button class="btn btn-sm" data-act="dot-dk" data-hd="tam_dung">' + ic("pause") + "Tạm dừng tất cả</button>" : "") +
          (tam ? '<button class="btn btn-sm btn-soft" data-act="dot-dk" data-hd="tiep_tuc">' + ic("play") + "Tiếp tục tất cả</button>" : "") +
          '<button class="btn btn-sm btn-dan" data-act="dot-huy">' + ic("stop") + "Huỷ đợt</button></div>" : "") + "</div>" +
        '<div class="mt-s" style="max-width:520px">' + tienTrinh(dot.tien_trinh) + "</div>" +
        '<div class="small muted mt-s">Tạo ' + DS.gioDu(dot.tao_luc) + (dot.xong_luc ? " · xong " + DS.gioDu(dot.xong_luc) : "") + " · song song " + (dot.song_song || 1) + (dot.chay_an ? " · chạy ẩn" : "") +
        (conChay() ? ' · <span class="row" style="display:inline-flex;gap:4px"><span class="dotx on pulse"></span>tự làm mới mỗi 5 giây</span>' : "") + "</div>";
      body.querySelector("#dc-dau").innerHTML = h;
    }
    function veKhung() {
      var ts = dot.tham_so || {}, sk = dot.su_kien || [];
      body.innerHTML = '<a class="back" href="#/nhat-ky?tab=dot">' + ic("back") + "Tất cả đợt chạy</a>" +
        '<div class="card" id="dc-dau"></div>' +
        '<div class="card card-x"><div class="card-h"><h3>Việc theo nick <span class="sub" id="dc-so"></span></h3><span class="tiny muted an-dt">Bấm nút trên dòng để tạm dừng hoặc huỷ riêng một nick</span></div><div id="dc-viec"></div></div>' +
        (Object.keys(ts).length ? '<div class="card"><div class="card-h"><h3>Tham số</h3></div><div class="logbox" style="max-height:160px">' + esc(veThamSo(ts)) + "</div></div>" : "") +
        '<div class="card" id="dc-sk"' + (sk.length ? "" : " hidden") + '><div class="card-h"><h3>Sự kiện gần nhất</h3></div><div class="logbox" id="dc-sk-b"></div></div>';
      veDau(); veDs(); veSk();
    }
    function veSk() {
      var sk = dot.su_kien || [], b = body.querySelector("#dc-sk-b");
      if (!b) return;
      body.querySelector("#dc-sk").hidden = !sk.length;
      b.textContent = sk.map(function (e) { return DS.gioPhut(e.luc) + "  " + (e.nick_ten || "") + "  [" + ((DS.KET_QUA[e.ket_qua] || [e.ket_qua])[0]) + "]  " + (e.chi_tiet || ""); }).join("\n");
    }
    function nap(lan) {
      return Promise.all([DS.api("GET", "/doi-social/dot-chay/" + encodeURIComponent(id), null, { quiet: !!lan }), DS.api("GET", "/doi-social/dang-chay", null, { quiet: true }), napNick]).then(function (a) {
        if (!ctx.alive) return;
        var d = a[0];
        if (d.ok === false) { if (!lan) body.innerHTML = '<a class="back" href="#/nhat-ky?tab=dot">' + ic("back") + "Tất cả đợt chạy</a>" + DS.loiThe(d.error); return; }
        var dauTien = !dot;
        dot = d.dot || {}; viec = dot.viec || [];
        buoc = {};
        DS.list(a[1], "viec").forEach(function (v) {
          var nk = v.nhat_ky || [];
          buoc[v.id] = v.buoc_cuoi || (nk.length ? (nk[nk.length - 1].dong || nk[nk.length - 1]) : "");
          viec.forEach(function (x) { if (String(x.id) === String(v.id) && v.lenh != null && x.lenh == null) x.lenh = v.lenh; });
        });
        if (dauTien) veKhung(); else { veDau(); veDs(); veSk(); }
      });
    }
    function capNhat(moi) {
      viec = viec.map(function (x) { return String(x.id) === String(moi.id) ? Object.assign({}, x, moi) : x; });
      veDs(); veDau();
      nap(true);
    }
    DS.bind(body, {
      "dk-viec": function (t) {
        var vid = t.getAttribute("data-id"), v = viec.filter(function (x) { return String(x.id) === vid; })[0] || {};
        DS.dieuKhienViec(vid, t.getAttribute("data-hd"), v.nick_ten, t).then(function (moi) { if (moi && ctx.alive) capNhat(moi); });
      },
      "xem": function (t) { var v = viec.filter(function (x) { return String(x.id) === t.getAttribute("data-id"); })[0]; if (v) xemViec(v, mauId); },
      "dot-dk": function (t) {
        var hd = t.getAttribute("data-hd");
        t.disabled = true;
        DS.api("POST", "/doi-social/dot-chay/" + encodeURIComponent(id) + "/dieu-khien", { hanh_dong: hd }).then(function (r) {
          t.disabled = false;
          if (r.ok === false) return;
          DS.toast(hd === "tam_dung" ? "Đã tạm dừng cả đợt, nick đang chạy dừng ở thao tác kế tiếp" : "Đã cho cả đợt chạy tiếp", "ok");
          nap(true);
        });
      },
      "dot-huy": function () {
        DS.xacNhan("Huỷ cả đợt? Việc chưa chạy sẽ bị bỏ, việc đang chạy được báo dừng.", "Huỷ đợt", true).then(function (ok) {
          if (!ok) return;
          DS.api("POST", "/doi-social/dot-chay/" + encodeURIComponent(id) + "/huy", {}).then(function (r) { if (r.ok !== false) { DS.toast("Đã huỷ đợt", "ok"); nap(true); } });
        });
      }
    });
    ctx.every(function () { if (conChay() && !document.querySelector(".modal-bg")) nap(true); }, 5000);
    return nap(0);
  }

  // ================================================================ tab Lịch sử chạy
  function tabLichSu(el, ctx, KB) {
    var mauId = DS.mauTheoId(KB), F = { trang_thai: ctx.q.tt || "", kich_ban: "", trang: 1 }, cache = {};
    var body = el.querySelector("#nk-body");
    body.innerHTML = '<div class="card card-x"><div class="card-h"><h3>Lịch sử chạy <span class="sub" id="ls-tong"></span></h3></div><div class="filters">' +
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
            return '<tr><td class="muted small">#' + v.id + '</td><td class="small">' + esc(v.ten_dot || (v.dot_id ? "Đợt #" + v.dot_id : "Việc lẻ")) + '</td><td><div class="row" style="flex-wrap:nowrap">' + DS.icNT(m.nen_tang, 18) +
              '<span class="clip" style="max-width:220px">' + esc(v.ten_mau || m.ten || v.nhan_ky_nang || v.ky_nang || "") + "</span></div></td><td><b>" + esc(v.nick_ten || "") + "</b></td><td>" + DS.ttViec(v) +
              (v.chay_thu ? " " + DS.bd("Chạy thử", "brand") : "") + '</td><td class="nw small">' + DS.gio(v.bat_dau || v.nhan_luc || v.tao_luc) + '</td><td><button class="btn btn-xs" data-act="xem" data-id="' + v.id + '">' + ic("eye") + "Xem</button></td></tr>";
          }).join("") + "</tbody></table></div>" + DS.phanTrang(tong, d.trang || F.trang, d.moi_trang || 50);
      });
    }
    function xem(v) { xemViec(v, mauId); }
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
        if (tab === "dot" && ctx.q.dot) return tabChiTietDot(el, ctx, kb, ctx.q.dot);
        if (tab === "dot") return tabDot(el, ctx, kb);
        if (tab === "lich-su") return tabLichSu(el, ctx, kb);
        return tabHoatDong(el, ctx, kb);
      });
    }
  });
})();
