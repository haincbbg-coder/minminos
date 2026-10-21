/* Fanpage (API) - Báo cáo - #/fp-bao-cao : số liệu theo Trang, theo bài, chuỗi theo ngày */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic, FP = DS.fp;

  function tang(n) {
    n = Number(n) || 0;
    if (!n) return '<span class="muted">0</span>';
    return '<span style="color:' + (n > 0 ? "var(--ok)" : "var(--err)") + ';font-weight:600">' + (n > 0 ? "+" : "") + DS.so(n) + "</span>";
  }

  DS.view("fp-bao-cao", {
    title: "Báo cáo Fanpage",
    render: function (el, ctx) {
      var F = { trang: ctx.q.trang || "", ngay: +ctx.q.ngay || 7 };
      if ([7, 14, 30].indexOf(F.ngay) < 0) F.ngay = 7;
      el.innerHTML = DS.ph("Báo cáo Fanpage", "Người theo dõi, tiếp cận và tương tác lấy từ Facebook Insights, cập nhật 6 giờ một lần.",
        '<button class="btn btn-pri" data-act="cap-nhat">' + ic("refresh") + "Cập nhật số liệu</button>") +
        '<div class="card card-x mb"><div class="filters" style="border-bottom:0"><select class="sel" id="bc-trang" aria-label="Trang"><option value="">Mọi Trang</option></select>' +
        '<div class="seg" id="bc-ngay">' + [7, 14, 30].map(function (n) { return '<button type="button" data-v="' + n + '" class="' + (n === F.ngay ? "on" : "") + '">' + n + " ngày</button>"; }).join("") + "</div></div></div>" +
        '<div id="bc-body">' + DS.skel(6, 3) + "</div>";
      FP.layTrang().then(function (d) {
        if (!ctx.alive || d.ok === false) return;
        el.querySelector("#bc-trang").innerHTML += DS.list(d).map(function (t) { return '<option value="' + esc(t.id) + '"' + (String(t.id) === F.trang ? " selected" : "") + ">" + esc(t.ten || t.id) + "</option>"; }).join("");
      });
      var charts = [];
      function nap() {
        return FP.api("GET", "/bao-cao" + DS.qs({ trang: F.trang, ngay: F.ngay })).then(function (d) {
          if (!ctx.alive) return;
          var box = el.querySelector("#bc-body");
          if (d.ok === false) { box.innerHTML = DS.loiThe(d.error, true); return; }
          var tr = d.trang || [], bai = d.bai || [], ch = d.chuoi || [];
          var cuoi = ch.length ? ch[ch.length - 1] : {}, dau = ch.length ? ch[0] : {};
          var cong = function (k) { var s = 0; ch.forEach(function (x) { s += Number(x[k]) || 0; }); return s; };
          var h = '<div class="grid g3">' +
            '<div class="stat"><div class="k"><span class="ico ico-info">' + ic("user") + '</span>Người theo dõi</div><div class="row-sb" style="align-items:flex-end"><div class="v">' + FP.so(cuoi.nguoi_theo_doi) + "</div>" +
            FP.spark(ch.map(function (x) { return x.nguoi_theo_doi; })) + '</div><div class="s">' + tang((cuoi.nguoi_theo_doi || 0) - (dau.nguoi_theo_doi || 0)) + " trong " + ch.length + " ngày</div></div>" +
            '<div class="stat"><div class="k"><span class="ico ico-info">' + ic("eye") + '</span>Tiếp cận</div><div class="row-sb" style="align-items:flex-end"><div class="v">' + FP.so(cong("tiep_can")) + "</div>" +
            FP.spark(ch.map(function (x) { return x.tiep_can; })) + '</div><div class="s">cộng ' + ch.length + " ngày</div></div>" +
            '<div class="stat"><div class="k"><span class="ico ico-ok">' + ic("activity") + '</span>Tương tác</div><div class="row-sb" style="align-items:flex-end"><div class="v">' + FP.so(cong("tuong_tac")) + "</div>" +
            FP.spark(ch.map(function (x) { return x.tuong_tac; })) + '</div><div class="s">cảm xúc, bình luận, chia sẻ</div></div></div>';
          h += ch.length ? '<div class="grid g2 mt"><div class="card"><div class="card-h"><h3>Tiếp cận mỗi ngày</h3></div><div class="chart" data-bc="tiep_can"></div></div>' +
            '<div class="card"><div class="card-h"><h3>Tương tác mỗi ngày</h3></div><div class="chart" data-bc="tuong_tac"></div></div></div>' :
            '<div class="card mt">' + DS.rong("Chưa có số liệu theo ngày", "Bấm Cập nhật số liệu. Facebook cần token có quyền read_insights.", "list") + "</div>";
          h += '<div class="card card-x mt"><div class="card-h"><h3>Theo Trang</h3><span class="small muted">' + tr.length + " Trang</span></div>" + (tr.length ? '<div class="tw"><table class="tbl"><thead><tr><th>Trang</th><th class="num">Người theo dõi</th><th class="num">24 giờ qua</th>' +
            '<th class="num">Tiếp cận</th><th class="num">Tương tác</th><th class="num">Lượt xem</th></tr></thead><tbody>' + tr.map(function (t) {
              return '<tr><td><div class="row" style="flex-wrap:nowrap">' + FP.avTrang(t) + '<a class="b clip" style="max-width:240px" href="#/fp-bao-cao?trang=' + encodeURIComponent(t.id) + "&ngay=" + F.ngay + '">' + esc(t.ten || t.id) + "</a></div></td>" +
                '<td class="num">' + FP.so(t.nguoi_theo_doi) + '</td><td class="num">' + tang(t.tang_24h) + '</td><td class="num">' + FP.so(t.tiep_can) + '</td><td class="num">' + FP.so(t.tuong_tac) + '</td><td class="num">' + FP.so(t.luot_xem) + "</td></tr>";
            }).join("") + "</tbody></table></div>" : DS.rong("Chưa có Trang nào", "", "list")) + "</div>";
          h += '<div class="card card-x mt"><div class="card-h"><h3>Theo bài</h3><span class="small muted">Bài đã đăng trong ' + F.ngay + " ngày</span></div>" + (bai.length ? '<div class="tw"><table class="tbl tbl-in"><thead><tr><th>Bài</th><th>Trang</th><th>Đăng lúc</th>' +
            '<th class="num">Cảm xúc · bình luận · chia sẻ</th><th class="num">Click</th><th></th></tr></thead><tbody>' + bai.map(function (b) {
              var s = b.so_lieu || {}, ck = s.click != null ? s.click : s.post_clicks;
              return '<tr><td style="min-width:260px;max-width:420px"><div class="small clamp2">' + esc(b.noi_dung || "(không có chữ)") + '</div></td><td class="small nw">' + esc(b.trang_ten || "") + '</td><td class="small nw">' + esc(DS.gio(b.dang_luc)) +
                '</td><td class="num small nw">' + DS.fp.soLieuNgan(s) + '</td><td class="num small">' + (ck != null ? FP.so(ck) : '<span class="muted">-</span>') + '</td><td class="nw">' + (b.url ? '<a class="btn btn-xs" href="' + esc(b.url) +
                '" target="_blank" rel="noopener">' + ic("ext") + "Mở</a>" : "") + "</td></tr>";
            }).join("") + "</tbody></table></div>" : DS.rong("Chưa có bài nào trong khoảng này", "", "list")) + "</div>";
          box.innerHTML = h;
          charts = Array.prototype.map.call(box.querySelectorAll("[data-bc]"), function (c) {
            var k = c.getAttribute("data-bc");
            var ve = function () { c.innerHTML = FP.cot(ch, k, { w: c.clientWidth, h: 170, cls: k === "tiep_can" ? "bar-info" : "bar-ok", nhan: k }); };
            ve();
            FP.ganTip(c, ch, function (x) { return "<b>" + esc(FP.ngayNgan(x.ngay)) + "</b><br>" + (k === "tiep_can" ? "Tiếp cận: " : "Tương tác: ") + FP.so(x[k]) + "<br>Người theo dõi: " + FP.so(x.nguoi_theo_doi); });
            return ve;
          });
        });
      }
      var rw = function () { if (!ctx.alive) { window.removeEventListener("resize", rw); return; } charts.forEach(function (f) { f(); }); };
      window.addEventListener("resize", rw);
      el.addEventListener("change", function (e) { if (e.target.id === "bc-trang") { F.trang = e.target.value; nap(); } });
      el.querySelector("#bc-ngay").addEventListener("click", function (e) {
        var b = e.target.closest("button"); if (!b) return;
        F.ngay = +b.getAttribute("data-v");
        Array.prototype.forEach.call(this.children, function (x) { x.classList.toggle("on", x === b); });
        nap();
      });
      DS.bind(el, {
        "tai-lai": nap,
        "cap-nhat": function (b) {
          b.disabled = true;
          FP.api("POST", "/bao-cao/cap-nhat", F.trang ? { trang: F.trang } : {}).then(function (d) {
            b.disabled = false;
            if (d.ok === false) return;
            DS.toast("Đã lấy số liệu mới từ Facebook", "ok"); nap();
          });
        }
      });
      return nap();
    }
  });

  DS.fp.soLieuNgan = function (s) {
    s = s || {};
    var g = function (a, b) { return s[a] != null ? s[a] : s[b]; };
    var cx = g("cam_xuc", "reactions"), bl = g("binh_luan", "comments"), cs = g("chia_se", "shares");
    if (cx == null && bl == null && cs == null) return '<span class="muted">-</span>';
    return FP.so(cx) + " · " + FP.so(bl) + " · " + FP.so(cs);
  };
})();
