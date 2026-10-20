/* Tổng quan - #/tong-quan */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;

  function loiChao() {
    var h = new Date().getHours();
    if (h >= 4 && h < 11) return "Chào buổi sáng";
    if (h >= 11 && h < 13) return "Chào buổi trưa";
    if (h >= 13 && h < 18) return "Chào buổi chiều";
    return "Chào buổi tối";
  }

  function robot() {
    return '<svg class="robot" width="150" height="150" viewBox="0 0 150 150" aria-hidden="true"><defs>' +
      '<linearGradient id="rb-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8b5cf6"/><stop offset="1" stop-color="#6366f1"/></linearGradient>' +
      '<linearGradient id="rb-f" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1e1b4b"/><stop offset="1" stop-color="#312e81"/></linearGradient></defs>' +
      '<circle cx="75" cy="78" r="64" fill="#7c3aed" opacity=".08"/><circle cx="75" cy="78" r="48" fill="#7c3aed" opacity=".08"/>' +
      '<line x1="75" y1="22" x2="75" y2="36" stroke="#8b5cf6" stroke-width="4" stroke-linecap="round"/><circle cx="75" cy="18" r="6" fill="#a78bfa"/>' +
      '<rect x="31" y="36" width="88" height="68" rx="24" fill="url(#rb-g)"/>' +
      '<rect x="22" y="58" width="10" height="24" rx="5" fill="#a78bfa"/><rect x="118" y="58" width="10" height="24" rx="5" fill="#a78bfa"/>' +
      '<rect x="42" y="48" width="66" height="42" rx="16" fill="url(#rb-f)"/>' +
      '<ellipse cx="61" cy="68" rx="6" ry="7" fill="#67e8f9"><animate attributeName="ry" values="7;1;7" dur="4s" keyTimes="0;.05;.1" repeatCount="indefinite"/></ellipse>' +
      '<ellipse cx="89" cy="68" rx="6" ry="7" fill="#67e8f9"><animate attributeName="ry" values="7;1;7" dur="4s" keyTimes="0;.05;.1" repeatCount="indefinite"/></ellipse>' +
      '<path d="M66 80q9 6 18 0" fill="none" stroke="#67e8f9" stroke-width="3" stroke-linecap="round"/>' +
      '<rect x="52" y="106" width="46" height="22" rx="10" fill="#c4b5fd"/><circle cx="75" cy="117" r="5" fill="#7c3aed"/></svg>';
  }

  function minhHoa(nen) {
    var ds = ["telegram", "youtube", "reddit", "facebook", "instagram", "tiktok", "x", "threads"];
    var h = '<div class="orbit"><div class="ring" style="width:250px;height:250px"></div><div class="ring" style="width:170px;height:170px;border-style:solid;opacity:.6"></div>';
    ds.forEach(function (id, i) {
      var g = (i / ds.length) * Math.PI * 2 - Math.PI / 2, r = 125;
      var mo = nen.length && id !== "telegram" && nen.indexOf(id) < 0;
      h += '<div class="pf" style="left:calc(50% + ' + Math.round(Math.cos(g) * r) + "px);top:calc(47% + " + Math.round(Math.sin(g) * r * .58) +
        "px);animation-delay:" + (i * .35).toFixed(2) + "s" + (mo ? ";opacity:.45" : "") + '">' + DS.icNT(id, 34) + "</div>";
    });
    return h + "</div>" + robot() + '<div class="robot-cap"><span class="dotx on pulse"></span>MinMin Agent · Sẵn sàng</div>';
  }

  function bieuDo(ds, W) {
    W = Math.max(280, Math.round(W || 700));
    var H = 220, L = 34, B = 22, T = 8;
    var max = 1;
    ds.forEach(function (d) { max = Math.max(max, (d.thanh_cong || 0) + (d.loi || 0)); });
    var buoc = Math.pow(10, Math.floor(Math.log10(max))), tran = Math.ceil(max / buoc) * buoc;
    if (tran / buoc <= 2) tran = Math.ceil(max / (buoc / 2)) * (buoc / 2);
    var cw = (W - L) / ds.length, bw = Math.max(6, Math.min(30, cw * .58));
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="Biểu đồ lượt chạy 14 ngày">';
    for (var k = 0; k <= 4; k++) {
      var gy = T + (H - B - T) * (1 - k / 4);
      s += '<line class="grid-l" x1="' + L + '" x2="' + W + '" y1="' + gy + '" y2="' + gy + '"/><text x="' + (L - 6) + '" y="' + (gy + 3) + '" text-anchor="end">' + DS.so(Math.round(tran * k / 4)) + "</text>";
    }
    ds.forEach(function (d, i) {
      var ok = d.thanh_cong || 0, loi = d.loi || 0, x = L + i * cw + (cw - bw) / 2, hh = H - B - T;
      var hOk = ok / tran * hh, hLoi = loi / tran * hh, y0 = H - B;
      var p = String(d.ngay || "").split("-"), nhan = p.length === 3 ? p[2] + "/" + p[1] : d.ngay;
      if (hOk > 0) s += '<rect class="bar-ok" x="' + x + '" y="' + (y0 - hOk) + '" width="' + bw + '" height="' + hOk + '" rx="' + Math.min(4, bw / 3) + '"/>';
      if (hLoi > 0) s += '<rect class="bar-err" x="' + x + '" y="' + (y0 - hOk - hLoi - (hOk > 0 ? 2 : 0)) + '" width="' + bw + '" height="' + hLoi + '" rx="' + Math.min(4, bw / 3) + '"/>';
      if (cw >= 34 || i % 2 === (ds.length - 1) % 2) s += '<text x="' + (L + i * cw + cw / 2) + '" y="' + (H - 6) + '" text-anchor="middle" class="xl" data-i="' + i + '">' + esc(nhan) + "</text>";
      s += '<rect class="hit" x="' + (L + i * cw) + '" y="' + T + '" width="' + cw + '" height="' + (H - B - T) + '" data-i="' + i + '"/>';
    });
    return s + "</svg>";
  }

  DS.view("tong-quan", {
    title: "Tổng quan",
    render: function (el, ctx) {
      el.innerHTML = '<div class="sk" style="height:290px;border-radius:20px"></div><div class="grid g4 mt"><div class="sk sk-card"></div><div class="sk sk-card"></div><div class="sk sk-card"></div><div class="sk sk-card"></div></div>';
      function nap() {
        return DS.api("GET", "/doi-social/tong-quan?ngay=14").then(function (d) {
          if (!ctx.alive) return;
          if (d.ok === false) { el.innerHTML = DS.loiThe(d.error, true); return; }
          ve(d);
        });
      }
      function ve(d) {
        var ai = d.ai || {}, so = d.so7 || {}, nen = d.nen_tang_dung || [], may = d.may || [], bd = d.bieu_do || [], cx = d.can_xu_ly || [];
        var mayOn = may.filter(function (m) { return m.online; }).length;
        var tg = d.telegram !== false;
        var h = '<section class="hero"><div class="hero-l">' +
          '<span class="hero-on' + (mayOn ? "" : " off") + '"><span class="dotx ' + (mayOn ? "on pulse" : "warn") + '"></span>' +
          (mayOn ? "Agent đang trực" : "Máy ở nhà đang tắt") + (tg ? " · Telegram" : "") + "</span>" +
          "<h1>" + loiChao() + "</h1><p>Agent đang trông <b>" + DS.so(d.nick_tong || 0) + " tài khoản</b> trên <b>" + nen.length + " nền tảng</b>, viết và làm việc bằng <b>" +
          esc(ai.engine || "bộ não MinMin") + "</b>" + (ai.mo_hinh ? " (" + esc(ai.mo_hinh) + ")" : "") + ".</p>" +
          '<div class="quick"><a class="pri" href="#/kho?tab=viet">' + ic("spark") + "Viết bài AI</a>" +
          '<a href="#/chay-hang-loat">' + ic("play") + "Chạy hàng loạt</a>" +
          '<a href="#/automation?tab=lich">' + ic("calendar") + "Lịch hẹn</a>" +
          '<a href="#/duyet">' + ic("check") + "Duyệt nội dung</a>" +
          '<a href="#/may">' + ic("monitor") + "Máy ở nhà</a></div>" +
          '</div><div class="hero-r">' + minhHoa(nen) + "</div></section>";

        h += '<div class="grid g-12 mt"><div class="card"><div class="card-h"><h3>' + ic("spark") + 'Nguồn AI</h3><a class="small" href="#/tro-ly">Trợ lý AI</a></div>' +
          '<div class="ai-src"><span class="av">' + ic("robot") + '</span><div class="grow"><div class="b">' + esc(ai.engine || "Chưa rõ") +
          '</div><div class="small muted clip">' + esc(ai.mo_hinh || "Mô hình mặc định của MinMin") + "</div></div>" +
          (ai.san_sang === false ? DS.bd("Chưa sẵn sàng", "err", true) : DS.bd("Sẵn sàng", "ok", true)) + "</div>" +
          '<div class="ai-src"><span class="av" style="background:var(--info-soft);color:var(--info)">' + ic("image") + '</span><div class="grow"><div class="b">Đọc ảnh trong bài</div>' +
          '<div class="small muted">' + (ai.nhin_anh ? "Có, AI nhìn được ảnh khi chấm bài" : "Không, AI chỉ đọc chữ") + "</div></div>" +
          (ai.nhin_anh ? DS.bd("Có", "ok") : DS.bd("Không", "mu")) + "</div>" +
          '<p class="tiny muted" style="margin:10px 0 0">Đội Social dùng chính bộ não MinMin, không cần khoá API riêng.</p></div>' +
          '<div class="card"><div class="card-h"><h3>' + ic("users") + 'Đội đang có</h3><a class="small" href="#/tai-khoan">Xem tài khoản</a></div>' +
          '<div class="grid g2"><div><div class="big"><b>' + DS.so(d.nick_tong || 0) + '</b><span class="muted">tài khoản</span></div><div class="small muted">trên ' + nen.length + " nền tảng</div>" +
          '<div class="row mt-s">' + (nen.length ? nen.map(function (n) { return DS.icNT(n, 24); }).join("") : '<span class="small muted">Chưa gắn nhãn nền tảng cho nick nào</span>') + "</div></div>" +
          '<div><div class="big"><b>' + mayOn + "/" + may.length + '</b><span class="muted">máy đang bật</span></div><div class="small muted">máy ở nhà chạy GPM</div>' +
          '<div class="stack mt-s">' + (may.length ? may.slice(0, 3).map(function (m) {
            return '<div class="row small"><span class="dotx ' + (m.online ? "on" : "") + '"></span><span class="clip grow">' + esc(m.ten) + '</span><span class="muted">' + esc(m.phien_ban || "") + "</span></div>";
          }).join("") : '<a class="small" href="#/may">Ghép máy đầu tiên</a>') + "</div></div></div></div></div>";

        var ty = so.ty_le != null ? so.ty_le : (so.luot ? Math.round(so.thanh_cong / so.luot * 100) : 0);
        h += '<div class="grid g4 mt">' +
          the("activity", "", "Lượt chạy · 7 ngày", DS.so(so.luot || 0), "mọi việc của đội") +
          the("ok", "ico-ok", "Thành công", DS.so(so.thanh_cong || 0), ty + "% số lượt") +
          the("play", "ico-info", "Đang chạy", DS.so(so.dang_chay || 0), '<a href="#/nhat-ky">xem trực tiếp</a>') +
          the("alert", "ico-err", "Lỗi", DS.so(so.loi || 0), '<a href="#/nhat-ky?tab=hoat-dong&kq=loi">xem lỗi</a>') + "</div>";

        var tong = 0, tc = 0;
        bd.forEach(function (x) { tong += (x.thanh_cong || 0) + (x.loi || 0); tc += x.thanh_cong || 0; });
        h += '<div class="grid g-21 mt"><div class="card"><div class="card-h"><div><h3>Lượt chạy 14 ngày</h3><div class="small muted" style="margin-top:2px">' + DS.so(tong) + " lượt · " +
          (tong ? Math.round(tc / tong * 100) : 0) + '% thành công</div></div><div class="leg"><span><i style="background:#22c55e"></i>Thành công</span><span><i style="background:#f87171"></i>Lỗi</span>' +
          '<span class="bd bd-brand">Hôm nay ' + DS.so(d.hom_nay || 0) + "</span></div></div>" +
          (bd.length ? '<div class="chart" id="chart"></div>' : DS.rong("Chưa có lượt chạy nào", "Chạy một mẫu để thấy biểu đồ ở đây.", "list")) + "</div>";
        h += '<div class="card"><div class="card-h"><h3>Cần bạn xử lý <span class="cnt bd ' + (cx.length ? "bd-warn" : "") + '">' + cx.length + "</span></h3></div>";
        if (!cx.length) h += DS.rong("Không có gì cần xử lý", "Agent đang tự lo được mọi việc.", "done");
        else h += cx.map(function (x) {
          return '<div class="todo"><span class="ti">' + ic(x.loai === "nick" ? "user" : x.loai === "nhom" ? "users" : x.loai === "ban_nhap" ? "check" : x.loai === "tin_nhan" ? "chat" : "alert") +
            '</span><div class="grow"><div class="b">' + esc(x.tieu_de) + '</div><div class="small muted">' + esc(x.chi_tiet || "") + "</div></div>" +
            (x.den ? '<a class="btn btn-sm" href="' + esc(x.den) + '">' + esc(x.nut || "Xem") + "</a>" : "") + "</div>";
        }).join("");
        h += '<div class="sep"></div><a class="small" href="#/nhat-ky">Mở nhật ký hoạt động</a></div></div>';
        el.innerHTML = h;

        var c = el.querySelector("#chart");
        if (c) {
          c.innerHTML = bieuDo(bd, c.clientWidth);
          var rw = function () { if (!ctx.alive) { window.removeEventListener("resize", rw); return; } if (c.isConnected) c.innerHTML = bieuDo(bd, c.clientWidth); };
          window.addEventListener("resize", rw);
          c.addEventListener("mousemove", function (e) {
            var t = e.target.closest("[data-i]");
            if (!t) { DS.tip(null); return; }
            var x = bd[+t.getAttribute("data-i")] || {};
            DS.tip("<b>" + esc(x.ngay) + "</b><br>Thành công: " + DS.so(x.thanh_cong || 0) + "<br>Lỗi: " + DS.so(x.loi || 0), e.clientX, e.clientY);
          });
          c.addEventListener("mouseleave", function () { DS.tip(null); });
          c.addEventListener("click", function (e) {
            var t = e.target.closest("[data-i]");
            if (!t) return;
            var r = t.getBoundingClientRect(), x = bd[+t.getAttribute("data-i")] || {};
            DS.tip("<b>" + esc(x.ngay) + "</b><br>Thành công: " + DS.so(x.thanh_cong || 0) + "<br>Lỗi: " + DS.so(x.loi || 0), r.left + r.width / 2, r.top + 30);
          });
        }
      }
      function the(i, cls, k, v, s) {
        return '<div class="stat"><div class="k"><span class="ico ' + cls + '">' + ic(i) + "</span>" + esc(k) + '</div><div class="v">' + v + '</div><div class="s">' + s + "</div></div>";
      }
      DS.bind(el, { "tai-lai": nap });
      ctx.every(nap, 60000);
      return nap();
    }
  });
})();
