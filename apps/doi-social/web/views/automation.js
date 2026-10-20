/* Automation - #/automation (tab Chọn mẫu · Lịch hẹn) */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;

  DS.CRON_NHANH = function (cron) {
    var m = /^(\d{1,2}) (\d{1,2}) \* \* \*$/.exec(String(cron || "").trim());
    if (m) return { kieu: "ngay", gio: (m[2].length < 2 ? "0" : "") + m[2] + ":" + (m[1].length < 2 ? "0" : "") + m[1] };
    m = /^(\d{1,2}) \*\/(\d{1,2}) \* \* \*$/.exec(String(cron || "").trim());
    if (m) return { kieu: "gio", n: +m[2], phut: +m[1] };
    return { kieu: "cron" };
  };
  DS.taoCron = function (kieu, gt) {
    if (kieu === "ngay") { var p = String(gt.gio || "08:00").split(":"); return (+p[1] || 0) + " " + (+p[0] || 0) + " * * *"; }
    if (kieu === "gio") { var n = Math.max(1, Math.min(23, +gt.n || 2)); return (gt.phut || 0) + " */" + n + " * * *"; }
    return String(gt.cron || "").trim();
  };
  DS.moTaCron = function (cron) {
    var x = DS.CRON_NHANH(cron);
    if (x.kieu === "ngay") return "Hằng ngày lúc " + x.gio;
    if (x.kieu === "gio") return "Mỗi " + x.n + " giờ";
    return cron || "";
  };

  function tabMau(el, ctx) {
    var host = el.querySelector("#am-body");
    host.innerHTML = '<div class="pills mb">' + '<span class="sk" style="width:110px;height:34px"></span>'.repeat(6) + '</div><div class="mau-grid">' + '<div class="sk sk-card"></div>'.repeat(6) + "</div>";
    return DS.layKichBan(true).then(function (kb) {
      if (!ctx.alive) return;
      if (kb.ok === false) { host.innerHTML = DS.loiThe(kb.error, true); return; }
      var ds = DS.dsMau(kb), nenTang = (kb.nen_tang || []).map(function (x) { return x[0]; });
      if (!nenTang.length) nenTang = DS.NT_THU_TU;
      var nhom = kb.nhom || [["dang_bai", "Đăng bài"], ["tuong_tac", "Tương tác"], ["ket_ban", "Kết bạn & nhắn tin"]];
      var nt = ctx.q.nt && nenTang.indexOf(ctx.q.nt) >= 0 ? ctx.q.nt : nenTang[0];
      var loc = ctx.q.nhom || "";
      var trongNT = ds.filter(function (m) { return m.nen_tang === nt; });
      var h = '<div class="pills">' + nenTang.map(function (id) {
        var n = ds.filter(function (m) { return m.nen_tang === id; }).length;
        return '<a class="pill' + (id === nt ? " on" : "") + '" href="#/automation?tab=mau&nt=' + id + '">' + DS.icNT(id, 20) + esc(DS.tenNT(id)) + '<span class="cnt">' + n + "</span></a>";
      }).join("") + "</div>";
      h += '<div class="chips mt">' + '<a class="chip' + (!loc ? " on" : "") + '" href="#/automation?tab=mau&nt=' + nt + '">Tất cả <span class="cnt">' + trongNT.length + "</span></a>" +
        nhom.map(function (g) {
          var n = trongNT.filter(function (m) { return m.nhom === g[0]; }).length;
          if (!n) return "";
          return '<a class="chip' + (loc === g[0] ? " on" : "") + '" href="#/automation?tab=mau&nt=' + nt + "&nhom=" + g[0] + '">' + esc(g[1]) + ' <span class="cnt">' + n + "</span></a>";
        }).join("") + "</div>";
      nhom.forEach(function (g) {
        if (loc && loc !== g[0]) return;
        var dsg = trongNT.filter(function (m) { return m.nhom === g[0]; });
        if (!dsg.length) return;
        h += '<div class="grp-t">' + esc(g[1]) + " (" + dsg.length + ')</div><div class="mau-grid">' + dsg.map(theMau).join("") + "</div>";
      });
      if (!trongNT.length) h += '<div class="card mt">' + DS.rong("Chưa có mẫu cho nền tảng này", "", "box") + "</div>";
      host.innerHTML = h;
    });
  }

  function theMau(m) {
    var ss = m.san_sang !== false;
    return '<div class="mau' + (ss ? "" : " dim") + '"><div class="mau-top">' + DS.icNT(m.nen_tang, 32) + '<div class="grow"><div class="mau-t">' + esc(m.ten) + "</div>" +
      '<div class="mau-d clamp1" data-act="mo-mau" title="Bấm để xem chi tiết">' + esc(m.mo_ta) + "</div>" +
      '<div class="mau-x" data-act="mo-mau" hidden>' + esc(m.mo_ta) + (m.chi_tiet ? "<br><br>" + esc(m.chi_tiet) : "") + "</div></div></div>" +
      '<div class="mau-f"><div class="row">' + (m.ai ? DS.bd("AI viết", "brand") : "") + (ss ? "" : DS.bd("Máy ở nhà chưa hỗ trợ", "warn")) +
      (m.tinh_nang ? '<span class="tiny muted">' + esc(m.tinh_nang) + "</span>" : "") + "</div>" +
      '<a class="btn btn-sm ' + (ss ? "btn-soft" : "") + '" href="#/chay-hang-loat?mau=' + encodeURIComponent(m.id) + '">' + ic("play") + "Chạy hàng loạt</a></div></div>";
  }

  function tabLich(el, ctx) {
    var host = el.querySelector("#am-body");
    host.innerHTML = '<div class="card card-x"><div class="tw"><table class="tbl tbl-in"><tbody>' + DS.skelDong(4, 7) + "</tbody></table></div></div>";
    return Promise.all([DS.api("GET", "/doi-social/lich-hen"), DS.layKichBan()]).then(function (a) {
      if (!ctx.alive) return;
      var d = a[0], mau = DS.mauTheoId(a[1]);
      if (d.ok === false) { host.innerHTML = DS.loiThe(d.error, true); return; }
      var ds = DS.list(d, "lich_hen");
      ctx.lich = ds;
      var dem = el.querySelector("#n-lich");
      if (dem) dem.textContent = ds.length;
      var h = '<div class="note mb">' + ic("info") + "<span>Lịch chạy trên máy chủ MinMin, kể cả khi bạn tắt trang này. Máy ở nhà cần đang bật để nhận việc; máy tắt thì việc chờ tới khi máy bật lại.</span></div>";
      if (!ds.length) {
        host.innerHTML = h + '<div class="card">' + DS.rong("Chưa có lịch hẹn", "Tạo một đợt chạy hàng loạt và chọn chế độ Hẹn lịch để mẫu tự chạy theo giờ.", "list",
          '<a class="btn btn-pri" href="#/chay-hang-loat">' + ic("plus") + "Chạy hàng loạt</a>") + "</div>";
        return;
      }
      h += '<div class="card card-x"><div class="tw"><table class="tbl tbl-in tbl-gon"><thead><tr><th>Tên</th><th>Mẫu</th><th class="num">Số nick</th><th>Lịch</th><th>Bật</th><th>Lần kế</th><th>Lần trước</th><th class="num">Số lần / lỗi</th><th></th></tr></thead><tbody>';
      h += ds.map(function (l) {
        var m = mau[l.kich_ban] || {};
        var mt = l.mo_ta_lich || DS.moTaCron(l.cron);
        return '<tr><td style="min-width:150px"><b>' + esc(l.ten || l.ten_mau || m.ten || "Lịch #" + l.id) + "</b></td><td><div class=\"row\" style=\"flex-wrap:nowrap\">" + DS.icNT(m.nen_tang, 20) + '<span class="clip" style="max-width:180px">' +
          esc(l.ten_mau || m.ten || l.kich_ban) + '</span></div></td><td class="num">' + (l.so_nick != null ? l.so_nick : (l.nick || []).length) + '</td><td class="nw">' + esc(mt) +
          (mt !== l.cron ? '<div class="sub">' + esc(l.cron || "") + "</div>" : "") + "</td><td>" + DS.sw('data-act="bat-lich" data-id="' + l.id + '" aria-label="Bật lịch"', !!l.bat) + '</td><td class="nw">' +
          (l.bat && l.lan_ke ? esc(DS.tuongDoi(l.lan_ke)) + '<div class="sub">' + DS.gio(l.lan_ke) + "</div>" : '<span class="muted">Đang tắt</span>') + '</td><td class="nw">' +
          (l.lan_truoc ? esc(DS.tuongDoi(l.lan_truoc)) : '<span class="muted">Chưa chạy</span>') + '</td><td class="num">' + DS.so(l.so_lan || 0) + " / " +
          (l.so_loi ? '<span style="color:var(--err)">' + DS.so(l.so_loi) + "</span>" : "0") + '</td><td class="nw"><div class="row" style="flex-wrap:nowrap">' +
          '<button class="btn btn-xs" data-act="chay-lich" data-id="' + l.id + '">' + ic("play") + "Chạy</button>" +
          '<button class="btn btn-xs" data-act="sua-lich" data-id="' + l.id + '" title="Sửa" aria-label="Sửa">' + ic("edit") + "</button>" +
          '<button class="btn btn-xs btn-dan" data-act="xoa-lich" data-id="' + l.id + '" aria-label="Xoá">' + ic("trash") + "</button></div></td></tr>";
      }).join("");
      host.innerHTML = h + "</tbody></table></div></div>";
    });
  }

  function suaLich(ctx, l, xong) {
    var x = DS.CRON_NHANH(l.cron);
    var m = DS.modal({
      title: "Sửa lịch hẹn",
      body: '<div class="fld"><label>Tên</label><input class="inp" id="sl-ten" value="' + esc(l.ten || "") + '"></div>' +
        '<div class="fld"><label>Lặp lại</label><div class="seg" id="sl-kieu">' +
        [["ngay", "Hằng ngày lúc"], ["gio", "Mỗi N giờ"], ["cron", "Cron tuỳ chỉnh"]].map(function (k) {
          return '<button type="button" data-k="' + k[0] + '" class="' + (x.kieu === k[0] ? "on" : "") + '">' + k[1] + "</button>";
        }).join("") + "</div></div>" +
        '<div class="fgrid" style="margin-top:12px"><div class="fld"><label>Giờ (hằng ngày)</label><input class="inp" type="time" id="sl-gio" value="' + esc(x.gio || "08:00") + '"></div>' +
        '<div class="fld"><label>Cách nhau (giờ)</label><input class="inp" type="number" min="1" max="23" id="sl-n" value="' + (x.n || 2) + '"></div></div>' +
        '<div class="fld"><label>Cron</label><input class="inp" id="sl-cron" value="' + esc(l.cron || "") + '" placeholder="phút giờ ngày tháng thứ"><div class="hint">Ví dụ 15 8 * * * là 08:15 mỗi ngày.</div></div>' +
        '<div class="swrow mt"><span>Bật lịch</span>' + DS.sw('id="sl-bat"', !!l.bat) + "</div>",
      foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="sl-luu">Lưu</button>'
    });
    var kieu = x.kieu, b = m.body;
    function cap() {
      b.querySelector("#sl-gio").disabled = kieu !== "ngay";
      b.querySelector("#sl-n").disabled = kieu !== "gio";
      b.querySelector("#sl-cron").readOnly = kieu !== "cron";
      if (kieu !== "cron") b.querySelector("#sl-cron").value = DS.taoCron(kieu, { gio: b.querySelector("#sl-gio").value, n: b.querySelector("#sl-n").value });
    }
    cap();
    b.addEventListener("click", function (e) { var t = e.target.closest("[data-k]"); if (!t) return; kieu = t.getAttribute("data-k");
      Array.prototype.forEach.call(b.querySelectorAll("[data-k]"), function (z) { z.classList.toggle("on", z === t); }); cap(); });
    b.addEventListener("input", cap);
    m.foot.querySelector("#sl-luu").onclick = function () {
      var cron = b.querySelector("#sl-cron").value.trim();
      if (cron.split(/\s+/).length !== 5) { DS.toast("Cron cần đúng 5 phần: phút giờ ngày tháng thứ", "err"); return; }
      DS.api("POST", "/doi-social/lich-hen/" + l.id, { ten: b.querySelector("#sl-ten").value.trim(), cron: cron, bat: b.querySelector("#sl-bat").checked }).then(function (d) {
        if (d.ok === false) return;
        DS.toast("Đã lưu lịch", "ok"); m.close(); xong();
      });
    };
  }

  DS.view("automation", {
    title: "Automation",
    render: function (el, ctx) {
      var tab = ctx.q.tab === "lich" ? "lich" : "mau";
      el.innerHTML = DS.ph("Automation", "Chọn một mẫu việc rồi giao cho nhiều nick chạy cùng lúc, hoặc hẹn lịch để Agent tự làm.",
        '<a class="btn btn-pri" href="#/chay-hang-loat">' + ic("plus") + "Chạy hàng loạt</a>") +
        '<div class="tabs"><a class="tab' + (tab === "mau" ? " on" : "") + '" href="#/automation?tab=mau">Chọn mẫu</a><a class="tab' + (tab === "lich" ? " on" : "") +
        '" href="#/automation?tab=lich">Lịch hẹn <span class="cnt" id="n-lich">·</span></a></div><div id="am-body"></div>';
      function nap() { return tab === "lich" ? tabLich(el, ctx) : tabMau(el, ctx); }
      if (tab === "mau") DS.api("GET", "/doi-social/lich-hen", null, { quiet: true }).then(function (d) {
        var n = el.querySelector("#n-lich"); if (n && d.ok !== false) n.textContent = DS.list(d, "lich_hen").length; });
      function lich(id) { return (ctx.lich || []).filter(function (x) { return String(x.id) === String(id); })[0]; }
      DS.bind(el, {
        "tai-lai": nap,
        "mo-mau": function (t) {
          var c = t.closest(".mau"), d = c.querySelector(".mau-d"), x = c.querySelector(".mau-x");
          var mo = x.hidden;
          x.hidden = !mo; d.hidden = mo;
        },
        "chay-lich": function (t) {
          t.disabled = true;
          DS.api("POST", "/doi-social/lich-hen/" + t.getAttribute("data-id") + "/chay", {}).then(function (d) {
            t.disabled = false;
            if (d.ok !== false) { DS.toast("Đã tạo đợt chạy, xem ở Nhật ký hoạt động", "ok"); nap(); }
          });
        },
        "sua-lich": function (t) { var l = lich(t.getAttribute("data-id")); if (l) suaLich(ctx, l, nap); },
        "xoa-lich": function (t) {
          var l = lich(t.getAttribute("data-id")) || {};
          DS.xacNhan('Xoá lịch "' + (l.ten || "#" + l.id) + '"? Các đợt đã chạy vẫn giữ trong nhật ký.', "Xoá", true).then(function (ok) {
            if (!ok) return;
            DS.api("DELETE", "/doi-social/lich-hen/" + l.id).then(function (d) { if (d.ok !== false) { DS.toast("Đã xoá lịch", "ok"); nap(); } });
          });
        }
      });
      DS.bind(el, {
        "bat-lich": function (t) {
          DS.api("POST", "/doi-social/lich-hen/" + t.getAttribute("data-id"), { bat: t.checked }).then(function (d) {
            if (d.ok === false) { t.checked = !t.checked; return; }
            DS.toast(t.checked ? "Đã bật lịch" : "Đã tắt lịch", "ok"); nap();
          });
        }
      }, "change");
      return nap();
    }
  });
})();
