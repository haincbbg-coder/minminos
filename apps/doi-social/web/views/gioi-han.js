/* Giới hạn nick - #/gioi-han (tab Chung · Theo nền tảng · Tuổi nick) */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;

  function sao(o) { return JSON.parse(JSON.stringify(o || {})); }

  DS.view("gioi-han", {
    title: "Giới hạn nick",
    render: function (el, ctx) {
      var tab = ["chung", "nen-tang", "tuoi"].indexOf(ctx.q.tab) >= 0 ? ctx.q.tab : "chung";
      var nt = DS.NT_THU_TU.indexOf(ctx.q.nt) >= 0 ? ctx.q.nt : "facebook";
      var G = null, MD = null, HD = {}, doi = false;
      el.innerHTML = DS.ph("Giới hạn nick", "Trần việc mỗi ngày cho từng nick, tăng dần theo tuổi nick để tránh bị khoá.") +
        DS.tabs([{ id: "chung", ten: "Chung cho mọi nền tảng" }, { id: "nen-tang", ten: "Theo nền tảng" }, { id: "tuoi", ten: "Tuổi nick" }], tab, "#/gioi-han?tab=") +
        '<div id="gh-body">' + DS.skel(7) + "</div>";

      DS.api("GET", "/doi-social/gioi-han-v2").then(function (d) {
        if (!ctx.alive) return;
        if (d.ok === false) { el.querySelector("#gh-body").innerHTML = DS.loiThe(d.error); return; }
        G = sao(d.gia_tri); MD = d.mac_dinh || sao(d.gia_tri); HD = d.hanh_dong || {};
        G.chung = G.chung || {}; G.nen_tang = G.nen_tang || {};
        if (tab === "tuoi") return tuoi();
        ve();
      });

      function nutLuu() {
        return '<div class="sticky-act"><span class="small muted grow" id="gh-doi" style="align-self:center">' + (doi ? "Có thay đổi chưa lưu" : "") + '</span><button class="btn btn-pri" data-act="luu">Lưu giới hạn</button></div>';
      }
      function so(id, v, min, max, w) {
        return '<input class="inp" type="number" data-k="' + id + '" value="' + esc(v != null ? v : "") + '" min="' + (min || 0) + '"' + (max ? ' max="' + max + '"' : "") + (w ? ' style="width:' + w + 'px"' : "") + ">";
      }
      function ve() {
        var b = el.querySelector("#gh-body"), c = G.chung;
        if (tab === "chung") {
          var np = c.nghi_phut || [8, 25], ng = c.nghi_giay || [6, 25];
          b.innerHTML = '<div class="card"><div class="sec"><div class="sec-t">Tổng việc mỗi ngày của một nick</div><div class="fgrid">' +
            '<div class="fld"><label>Nick mới</label>' + so("chung.viec_ngay_moi", c.viec_ngay_moi, 1, 500) + '<div class="hint">Cộng mọi việc trên mọi nền tảng.</div></div>' +
            '<div class="fld"><label>Nick lâu năm</label>' + so("chung.viec_ngay_lau", c.viec_ngay_lau, 1, 1000) + "</div></div></div>" +
            '<div class="sec"><div class="sec-t">Nhịp làm việc</div><div class="fgrid">' +
            '<div class="fld"><label>Nghỉ giữa 2 việc của một nick (phút)</label><div class="range">' + so("chung.nghi_phut.0", np[0], 0, 1440) + '<span class="muted">đến</span>' + so("chung.nghi_phut.1", np[1], 0, 1440) +
            '</div><div class="hint">Chọn ngẫu nhiên trong khoảng này.</div></div>' +
            '<div class="fld"><label>Nghỉ giữa 2 thao tác (giây)</label><div class="range">' + so("chung.nghi_giay.0", ng[0], 0, 600) + '<span class="muted">đến</span>' + so("chung.nghi_giay.1", ng[1], 0, 600) +
            '</div><div class="hint">Giữa hai lần thích, bình luận... trong cùng một việc.</div></div></div></div>' +
            '<div class="sec"><div class="sec-t">Tuổi nick</div><div class="fgrid">' +
            '<div class="fld"><label>Nick thành "lâu năm" sau (ngày tuổi)</label>' + so("chung.lau_nam_sau_ngay", c.lau_nam_sau_ngay, 1, 3650) + '<div class="hint">Tuổi tính từ tháng "tạo từ" ở trang Tài khoản. Chưa đặt thì coi là nick mới.</div></div>' +
            '<div class="fld"><label>Nick mới tăng trần mỗi tuần (%)</label>' + so("chung.tang_tuan_pt", c.tang_tuan_pt, 0, 200) + '<div class="hint">Trần nick mới tăng dần theo tuần nhưng không vượt trần nick lâu năm.</div></div></div></div>' +
            nutLuu() + "</div>";
        } else {
          var v = G.nen_tang[nt] = G.nen_tang[nt] || {}, md = (MD.nen_tang || {})[nt] || {};
          var keys = {};
          Object.keys(md).concat(Object.keys(v)).forEach(function (k) { keys[k] = 1; });
          var mang = Object.keys(keys).filter(function (k) { return Array.isArray(v[k] != null ? v[k] : md[k]); });
          var don = Object.keys(keys).filter(function (k) { return mang.indexOf(k) < 0; });
          var NHAN_RIENG = { vao_nhom_moi_gio: "Vào nhóm tối đa mỗi giờ" };
          b.innerHTML = '<div class="pills mb">' + DS.NT_THU_TU.map(function (id) {
            return '<a class="pill' + (id === nt ? " on" : "") + '" href="#/gioi-han?tab=nen-tang&nt=' + id + '">' + DS.icNT(id, 20) + esc(DS.tenNT(id)) + "</a>";
          }).join("") + "</div>" +
            '<div class="card card-x"><div class="card-h"><h3>' + DS.icNT(nt, 22) + "Việc mỗi ngày · " + esc(DS.tenNT(nt)) + '</h3><button class="btn btn-sm" data-act="mac-dinh">' + ic("refresh") + "Mặc định cho " + esc(DS.tenNT(nt)) +
            '</button></div><div style="height:12px"></div>' +
            (mang.length ? '<div class="tw"><table class="tbl"><thead><tr><th>Việc</th><th>Nick mới</th><th>Nick lâu năm</th><th class="small">Mặc định</th></tr></thead><tbody>' + mang.map(function (k) {
              var x = v[k] || md[k] || [0, 0], m = md[k] || [];
              return "<tr><td><b style=\"font-weight:500\">" + esc(HD[k] || k) + "</b></td><td>" + so("nt." + k + ".0", x[0], 0, 10000, 96) + "</td><td>" + so("nt." + k + ".1", x[1], 0, 10000, 96) +
                '</td><td class="small muted nw">' + (m.length ? m[0] + " / " + m[1] : "") + "</td></tr>";
            }).join("") + "</tbody></table></div>" : DS.rong("Nền tảng này chưa có giới hạn riêng", "", "list")) +
            (don.length ? '<div style="padding:14px 18px;border-top:1px solid var(--line)"><div class="sec-t">Luật riêng</div><div class="fgrid">' + don.map(function (k) {
              return '<div class="fld"><label>' + esc(NHAN_RIENG[k] || HD[k] || k) + "</label>" + so("nt." + k, v[k] != null ? v[k] : md[k], 0, 1000) + "</div>";
            }).join("") + "</div></div>" : "") +
            '<div style="padding:0 18px 18px">' + nutLuu() + "</div></div>";
        }
      }
      function datGT(k, val) {
        var p = k.split("."), n = val === "" ? null : +val;
        if (p[0] === "chung") {
          if (p.length === 3) { G.chung[p[1]] = (G.chung[p[1]] || [0, 0]).slice(); G.chung[p[1]][+p[2]] = n; } else G.chung[p[1]] = n;
        } else {
          var o = G.nen_tang[nt] = G.nen_tang[nt] || {}, md = ((MD.nen_tang || {})[nt] || {})[p[1]];
          if (p.length === 3) { o[p[1]] = (o[p[1]] || md || [0, 0]).slice(); o[p[1]][+p[2]] = n; } else o[p[1]] = n;
        }
        doi = true;
        var e = el.querySelector("#gh-doi"); if (e) e.textContent = "Có thay đổi chưa lưu";
      }
      function kiem() {
        var c = G.chung, loi = "";
        [["nghi_phut", "Nghỉ giữa 2 việc"], ["nghi_giay", "Nghỉ giữa 2 thao tác"]].forEach(function (x) {
          var r = c[x[0]]; if (r && r[0] != null && r[1] != null && r[0] > r[1]) loi = loi || x[1] + ": số đầu phải nhỏ hơn số sau";
        });
        Object.keys(G.nen_tang).forEach(function (n) {
          var o = G.nen_tang[n];
          Object.keys(o).forEach(function (k) { if (Array.isArray(o[k]) && o[k][0] != null && o[k][1] != null && o[k][0] > o[k][1]) loi = loi || DS.tenNT(n) + " · " + (HD[k] || k) + ": nick mới không nên cao hơn nick lâu năm"; });
        });
        return loi;
      }
      el.addEventListener("input", function (e) { var k = e.target.getAttribute("data-k"); if (k && G) datGT(k, e.target.value); });
      DS.bind(el, {
        "luu": function (b) {
          var loi = kiem();
          if (loi) { DS.toast(loi, "err"); return; }
          b.disabled = true;
          DS.api("POST", "/doi-social/gioi-han-v2", G).then(function (d) {
            b.disabled = false;
            if (d.ok === false) return;
            if (d.gia_tri) G = sao(d.gia_tri);
            doi = false; DS.toast("Đã lưu giới hạn", "ok"); ve();
          });
        },
        "mac-dinh": function () {
          G.nen_tang[nt] = sao(((MD.nen_tang || {})[nt]) || {});
          doi = true; ve(); DS.toast("Đã đặt lại mặc định cho " + DS.tenNT(nt) + ", bấm Lưu để áp dụng", "info");
        }
      });

      // ------------------------------------------------------------ tab Tuổi nick
      function tuoi() {
        var chon = {}, b = el.querySelector("#gh-body"), ngay = (G.chung.lau_nam_sau_ngay || 90);
        b.innerHTML = '<div class="card card-x"><div class="tw"><table class="tbl"><tbody>' + DS.skelDong(6, 5) + "</tbody></table></div></div>";
        function nap() {
          return DS.layNick(true).then(function (d) {
            if (!ctx.alive) return;
            if (d.ok === false) { b.innerHTML = DS.loiThe(d.error); return; }
            var ds = DS.list(d, "nick"), lau = ds.filter(function (n) { return n.muc === "lau"; }).length;
            var nowM = new Date(), gt = nowM.getFullYear() + "-" + (nowM.getMonth() < 9 ? "0" : "") + (nowM.getMonth() + 1);
            if (!ds.length) { b.innerHTML = '<div class="card">' + DS.rong("Chưa có nick", 'Ghép máy ở nhà trước. <a href="#/may">Mở Máy ở nhà</a>', "list") + "</div>"; return; }
            b.innerHTML = '<div class="card card-x"><div class="filters" style="justify-content:space-between"><div><b>' + lau + "/" + ds.length + ' nick</b> <span class="muted">đang dùng giới hạn lâu năm (từ ' + ngay +
              ' ngày tuổi)</span></div><div class="row"><input class="inp" type="month" id="tu-thang" value="' + gt + '" max="' + gt + '"><button class="btn btn-sm btn-pri" data-act="ap-thang" id="tu-ap" disabled>Áp dụng cho nick đã chọn</button></div></div>' +
              '<div class="tw" style="border-top:0"><table class="tbl" style="min-width:640px"><thead><tr><th class="w1"><input type="checkbox" class="cb" id="tu-all" aria-label="Chọn tất cả"></th><th>Nick</th><th>Tạo từ</th><th>Tuổi</th><th>Mức giới hạn</th></tr></thead><tbody>' +
              ds.map(function (n) {
                var t = n.tuoi_ngay, con = t != null ? Math.max(0, ngay - t) : null;
                return '<tr><td><input type="checkbox" class="cb" data-tu="' + esc(n.id) + '"></td><td><div class="row" style="flex-wrap:nowrap">' + DS.av(n.ten) + "<b>" + esc(n.ten) + "</b></div></td>" +
                  "<td>" + (n.tao_tu ? esc(n.tao_tu.split("-").reverse().join("/")) : '<span class="muted">Chưa đặt</span>') + "</td><td>" + (t != null ? DS.so(t) + " ngày" : '<span class="muted">Không rõ</span>') + "</td>" +
                  "<td>" + (n.muc === "lau" ? DS.bd("Lâu năm", "ok") : DS.bd("Nick mới", "info") + (con != null ? ' <span class="small muted">còn ' + con + " ngày lên Lâu năm</span>" : ' <span class="small muted">đặt "tạo từ" để tính</span>')) + "</td></tr>";
              }).join("") + "</tbody></table></div></div>";
          });
        }
        function cap() {
          var n = Object.keys(chon).filter(function (k) { return chon[k]; }).length, a = el.querySelector("#tu-ap");
          if (a) { a.disabled = !n; a.textContent = n ? "Áp dụng cho " + n + " nick đã chọn" : "Áp dụng cho nick đã chọn"; }
        }
        b.addEventListener("change", function (e) {
          var t = e.target;
          if (t.id === "tu-all") { Array.prototype.forEach.call(b.querySelectorAll("[data-tu]"), function (c) { c.checked = t.checked; chon[c.getAttribute("data-tu")] = t.checked; }); cap(); }
          else if (t.getAttribute("data-tu")) { chon[t.getAttribute("data-tu")] = t.checked; cap(); }
        });
        DS.bind(b, {
          "ap-thang": function () {
            var v = b.querySelector("#tu-thang").value, ids = Object.keys(chon).filter(function (k) { return chon[k]; }).map(function (x) { return isNaN(+x) ? x : +x; });
            if (!/^\d{4}-\d{2}$/.test(v)) { DS.toast("Chọn tháng tạo", "err"); return; }
            DS.api("POST", "/doi-social/nick/meta", { ids: ids, tao_tu: v }).then(function (d) {
              if (d.ok === false) return;
              DS.toast("Đã đặt tháng tạo cho " + ids.length + " nick", "ok"); chon = {}; DS.boNho("nick"); nap();
            });
          }
        });
        return nap();
      }
    }
  });
})();
