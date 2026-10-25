/* tong-quan.js - trang TỔNG QUAN, phương án 1 "Bàn làm việc" (26.10.242).
 *
 * Đọc GET /tong-quan?brain=<brain> (hợp đồng ở plans/tong-quan/PLAN.md) và dựng một màn:
 * lời chào + số việc cần người dùng, thanh Hoàn tất cài đặt (ẩn khi đủ), khối Cần xử lý,
 * Tiền vào hôm nay, Chi phí AI hôm nay, 4 số chính, bảng Theo page.
 *
 * Luật của trang:
 *   - Mỗi khối tự mang trang_thai: "ok" | "chua_noi" | "loi". Khối chưa nối vẫn hiện thẻ, thay
 *     số bằng chữ "Chưa nối" + nút đi nối. KHÔNG BAO GIỜ hiện 0 thay cho số thiếu.
 *   - Một khối lỗi chỉ hỏng ô đó, không hỏng cả trang.
 *   - Mọi chuỗi từ máy chủ đi qua esc(). Mọi chữ hiển thị đi qua t("tongquan.*").
 *
 * Phần dựng HTML là hàm THUẦN (_html(data) trả chuỗi) để test node chạy không cần DOM.
 * Không dùng ký tự em dash. */
(function () {
  "use strict";
  function t(k, b) { return window.t ? window.t(k, b) : k; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  async function api(url, opt) {
    var r = await fetch(url, Object.assign({ credentials: "same-origin" }, opt || {}));
    var d = {};
    try { d = await r.json(); } catch (e) {}
    if (!r.ok || d.ok === false) throw new Error(d.error || d.detail || ("HTTP " + r.status));
    return d;
  }
  function brainHienTai() {
    try { return (window.currentBrainPath && window.currentBrainPath()) || "brain"; }
    catch (e) { return "brain"; }
  }
  function laSo(x) { return typeof x === "number" && isFinite(x); }

  // ================================================================ ĐỊNH DẠNG
  // Viết tay thay vì Intl để số tiền luôn đúng một dạng "45.280.000đ" / "3,40$" bất kể
  // ngôn ngữ giao diện và bản ICU của trình duyệt.
  function nhom(nguyen) {
    return String(nguyen).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }
  function soNguyen(n) {
    if (!laSo(n)) return "";
    var am = n < 0;
    return (am ? "-" : "") + nhom(Math.round(Math.abs(n)));
  }
  function vnd(n) { return laSo(n) ? soNguyen(n) + "đ" : ""; }
  function usd(n) {
    if (!laSo(n)) return "";
    var am = n < 0;
    var s = Math.abs(n).toFixed(2).split(".");
    return (am ? "-" : "") + nhom(s[0]) + "," + s[1] + "$";
  }
  function phanTram(n) {
    if (!laSo(n)) return "-";
    var r = Math.round(n * 10) / 10;
    return String(r).replace(".", ",") + "%";
  }
  function hai(n) { return (n < 10 ? "0" : "") + n; }
  function gioPhut(d) { return hai(d.getHours()) + ":" + hai(d.getMinutes()); }
  function locale() {
    try { return (window.JavisI18n && window.JavisI18n.locale && window.JavisI18n.locale()) || "vi-VN"; }
    catch (e) { return "vi-VN"; }
  }
  // "Chủ nhật, 25/10" theo giờ máy. Trả "" khi luc hỏng.
  function ngayThu(d) {
    var thu = "";
    try { thu = new Intl.DateTimeFormat(locale(), { weekday: "long" }).format(d); } catch (e) {}
    thu = thu ? thu.charAt(0).toUpperCase() + thu.slice(1) + ", " : "";
    return thu + hai(d.getDate()) + "/" + hai(d.getMonth() + 1);
  }
  function docLuc(luc) {
    if (luc == null || luc === "") return null;
    var d = typeof luc === "number" ? new Date(luc < 1e12 ? luc * 1000 : luc) : new Date(luc);
    return isNaN(d.getTime()) ? null : d;
  }
  // Chỉ cho mở link http(s) hoặc đường dẫn nội bộ; chặn javascript:, data:...
  function urlAnToan(u) {
    u = String(u || "").trim();
    if (/^https?:\/\//i.test(u)) return u;
    if (u.charAt(0) === "/" && u.charAt(1) !== "/") return u;
    return "";
  }

  // ================================================================ MẢNH HTML
  function nutTrang(nhan, trang, lop, taskId) {
    return '<button type="button" class="' + (lop || "tq-nut-phu") + '" data-tq="trang" data-trang="' + esc(trang) + '"' +
      (taskId ? ' data-task="' + esc(taskId) + '"' : "") + '>' + esc(nhan) + '</button>';
  }
  function oChuaNoi(trang) {
    return '<div class="tq-chua-noi"><span>' + esc(t("tongquan.chua_noi")) + '</span>' +
      nutTrang(t("tongquan.di_noi"), trang, "tq-nut-phu tq-nut-nho") + '</div>';
  }
  function oLoi(khoi) {
    return '<div class="tq-loi">' + esc((khoi && khoi.loi) || t("tongquan.loi_nguon_chung")) + '</div>';
  }
  function trangThai(khoi) {
    if (!khoi || typeof khoi !== "object") return "loi";
    return khoi.trang_thai === "ok" || khoi.trang_thai === "chua_noi" ? khoi.trang_thai : "loi";
  }

  function phanDau(d, soViec) {
    var luc = docLuc(d.luc);
    var dong = luc ? esc(ngayThu(luc)) + ' · ' + esc(t("tongquan.cap_nhat", { gio: gioPhut(luc) })) : "";
    var tieuDe = soViec == null ? t("tongquan.tieu_de_chung")
      : soViec > 0 ? t("tongquan.tieu_de", { n: soViec }) : t("tongquan.tieu_de_0");
    return '<header class="tq-dau"><div class="tq-dau-chu">' +
      (dong ? '<span class="tq-nho">' + dong + '</span>' : "") +
      '<h1 class="tq-tieu-de">' + esc(tieuDe) + '</h1></div>' +
      '<button type="button" class="tq-nut-phu" data-tq="lam_moi">' + esc(t("tongquan.lam_moi")) + '</button>' +
      '</header>';
  }

  function thanhCaiDat(cd) {
    if (!cd || !laSo(cd.xong) || !laSo(cd.tong) || cd.xong >= cd.tong) return "";
    var buoc = Array.isArray(cd.buoc) ? cd.buoc : [];
    var thieu = buoc.filter(function (b) { return b && !b.xong; });
    var pt = cd.tong > 0 ? Math.max(0, Math.min(100, Math.round(cd.xong / cd.tong * 100))) : 0;
    var dau = thieu[0];
    return '<section class="tq-the tq-cai-dat" aria-label="' + esc(t("tongquan.cai_dat_aria")) + '">' +
      '<b class="tq-cai-dat-ten">' + esc(t("tongquan.cai_dat", { xong: cd.xong, tong: cd.tong })) + '</b>' +
      '<div class="tq-ranh" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + pt + '">' +
        '<div class="tq-ranh-day" style="width:' + pt + '%"></div></div>' +
      (thieu.length ? '<span class="tq-phu">' + esc(t("tongquan.cai_dat_con", {
        ds: thieu.map(function (b) { return b.ten || b.id || ""; }).join(" · ") })) + '</span>' : "") +
      (dau ? nutTrang(t("tongquan.noi_tiep"), dau.trang || "mcp") : "") +
      '</section>';
  }

  function nutMuc(n, muc) {
    if (!n || typeof n !== "object") return "";
    var nhan = n.nhan || t("tongquan.mo");
    if (n.loai === "duyet_kanban" && n.task_id) {
      return '<button type="button" class="tq-nut-chinh" data-tq="duyet" data-task="' + esc(n.task_id) + '">' + esc(nhan) + '</button>';
    }
    if (n.loai === "trang" && n.trang) return nutTrang(nhan, n.trang, "tq-nut-phu", n.task_id);
    if (n.loai === "link") {
      var u = urlAnToan(n.url);
      if (!u) return "";
      return '<button type="button" class="tq-nut-phu" data-tq="link" data-url="' + esc(u) + '">' + esc(nhan) + '</button>';
    }
    return "";
  }

  function khoiCanXuLy(cx) {
    var tt = trangThai(cx);
    var than;
    if (tt === "loi") than = oLoi(cx);
    else {
      var muc = Array.isArray(cx.muc) ? cx.muc : [];
      than = muc.length ? '<ul class="tq-ds">' + muc.map(function (m) {
        var md = m.muc_do === "bad" || m.muc_do === "warn" ? m.muc_do : "info";
        return '<li class="tq-muc" data-muc="' + esc(m.id || "") + '">' +
          '<span class="tq-cham ' + md + '" aria-hidden="true"></span>' +
          '<div class="tq-muc-chu"><b>' + esc(m.tieu_de || "") + '</b>' +
            (m.mo_ta ? '<span class="tq-phu">' + esc(m.mo_ta) + '</span>' : "") +
            '<span class="tq-muc-loi" role="status"></span></div>' +
          '<div class="tq-muc-nut">' + (Array.isArray(m.nut) ? m.nut.map(function (n) { return nutMuc(n, m); }).join("") : "") + '</div>' +
          '</li>';
      }).join("") + '</ul>'
        : '<div class="tq-trong">' + esc(t("tongquan.trong")) + '</div>';
      var ln = Array.isArray(cx.loi_nguon) ? cx.loi_nguon.filter(Boolean) : [];
      if (ln.length) than += '<div class="tq-loi">' + esc(t("tongquan.loi_nguon", { ds: ln.join(", ") })) + '</div>';
    }
    return '<section class="tq-the tq-can">' +
      '<div class="tq-the-dau"><h2 class="tq-h2">' + esc(t("tongquan.can_xu_ly")) + '</h2>' +
      '<span class="tq-phu">' + esc(t("tongquan.can_xu_ly_phu")) + '</span></div>' + than + '</section>';
  }

  function theTienVao(tv) {
    var tt = trangThai(tv);
    var than;
    if (tt === "chua_noi") than = oChuaNoi("biendong");
    else if (tt === "loi") than = oLoi(tv);
    else if (!laSo(tv.tong)) than = '<div class="tq-phu">' + esc(t("tongquan.chua_co_so")) + '</div>';
    else {
      var gn = (Array.isArray(tv.gan_nhat) ? tv.gan_nhat : []).slice(0, 3);
      var soGd = laSo(tv.so_gd) ? tv.so_gd : gn.length;
      than = '<b class="tq-so tq-xanh">' + (tv.tong > 0 ? "+" : "") + esc(vnd(tv.tong)) + '</b>' +
        (gn.length ? '<ul class="tq-gd">' + gn.map(function (g) {
          var l = docLuc(g.luc);
          return '<li><span class="tq-gd-ten">' + esc(g.mo_ta || "") +
            (l ? ' <span class="tq-mo">' + esc(gioPhut(l)) + '</span>' : "") + '</span>' +
            '<b>' + esc(vnd(g.so_tien)) + '</b></li>';
        }).join("") + '</ul>' : (soGd === 0 ? '<div class="tq-phu">' + esc(t("tongquan.chua_co_gd")) + '</div>' : "")) +
        '<div class="tq-the-chan">' +
          (soGd > gn.length ? '<span class="tq-phu">' + esc(t("tongquan.so_gd_khac", { n: soGd - gn.length })) + '</span>' : '<span></span>') +
          '<button type="button" class="tq-link" data-tq="trang" data-trang="biendong">' + esc(t("tongquan.xem_het")) + '</button>' +
        '</div>';
    }
    return '<section class="tq-the tq-tien">' +
      '<h2 class="tq-h3">' + esc(t("tongquan.tien_vao")) + '</h2>' + than + '</section>';
  }

  function theChiPhiAi(ai) {
    var tt = trangThai(ai);
    var than;
    if (tt === "chua_noi") than = oChuaNoi("models");
    else if (tt === "loi") than = oLoi(ai);
    else {
      than = (laSo(ai.usd_that) ? '<b class="tq-so">' + esc(usd(ai.usd_that)) + '</b>' +
          '<span class="tq-phu">' + esc(t("tongquan.ai_that")) + '</span>'
          : '<div class="tq-phu">' + esc(t("tongquan.chua_co_so")) + '</div>') +
        (laSo(ai.usd_quy_doi) ? '<span class="tq-phu">' + esc(t("tongquan.ai_quy_doi", { usd: usd(ai.usd_quy_doi) })) + '</span>' : "") +
        (laSo(ai.luot) ? '<span class="tq-phu">' + esc(t("tongquan.ai_luot", { n: soNguyen(ai.luot) })) + '</span>' : "");
    }
    return '<section class="tq-the tq-ai">' +
      '<h2 class="tq-h3">' + esc(t("tongquan.chi_phi_ai")) + '</h2>' + than + '</section>';
  }

  // So với hôm qua: % khi hôm qua > 0, số chênh khi hôm qua = 0. Trả {chu, lop} hoặc null.
  function soVoiHomQua(nay, qua, laTien) {
    if (!laSo(nay) || !laSo(qua)) return null;
    var chenh = nay - qua;
    if (chenh === 0) return { chu: t("tongquan.bang_hom_qua"), lop: "tq-mo" };
    var lop = chenh > 0 ? "tq-xanh" : "tq-cam";
    var dau = chenh > 0 ? "+" : "";
    if (laTien && qua > 0) return { chu: t("tongquan.so_hom_qua", { chenh: dau + phanTram(chenh / qua * 100) }), lop: lop };
    if (laTien) return { chu: t("tongquan.so_hom_qua", { chenh: dau + vnd(chenh) }), lop: lop };
    return { chu: t("tongquan.don_hom_qua", { chenh: dau + soNguyen(chenh) }), lop: lop };
  }

  function theSo(lop, nhan, khoi, trangNoi, giaTri, phu) {
    var tt = trangThai(khoi);
    var than;
    if (tt === "chua_noi") than = oChuaNoi(trangNoi);
    else if (tt === "loi") than = oLoi(khoi);
    else {
      var gt = giaTri(khoi);
      if (!gt) than = '<div class="tq-phu">' + esc(t("tongquan.chua_co_so")) + '</div>';
      else {
        var p = phu ? phu(khoi) : null;
        than = '<b class="tq-so">' + esc(gt) + '</b>' + (p ? '<span class="tq-nho ' + p.lop + '">' + esc(p.chu) + '</span>' : "");
      }
    }
    return '<div class="tq-the tq-the-so ' + lop + '"><span class="tq-nhan">' + esc(nhan) + '</span>' + than + '</div>';
  }

  function hangSo(sc) {
    sc = sc || {};
    var dt = sc.doanh_thu, dc = sc.don_chot, ch = sc.chot_hoi_thoai, ads = sc.chi_ads;
    return '<div class="tq-hang-so">' +
      theSo("tq-dt", t("tongquan.doanh_thu"), dt, "mcp",
        function (k) { return laSo(k.hom_nay) ? vnd(k.hom_nay) : ""; },
        function (k) { return soVoiHomQua(k.hom_nay, k.hom_qua, true); }) +
      theSo("tq-dc", t("tongquan.don_chot"), dc, "mcp",
        function (k) { return laSo(k.hom_nay) ? soNguyen(k.hom_nay) : ""; },
        function (k) { return soVoiHomQua(k.hom_nay, k.hom_qua, false); }) +
      theSo("tq-ch", t("tongquan.ty_le_chot"), ch, "mcp",
        function (k) { return laSo(k.ty_le) ? phanTram(k.ty_le) : ""; },
        function (k) {
          return laSo(k.khach) && laSo(k.sdt)
            ? { chu: t("tongquan.khach_sdt", { khach: soNguyen(k.khach), sdt: soNguyen(k.sdt) }), lop: "tq-mo" } : null;
        }) +
      theSo("tq-ads", t("tongquan.chi_ads"), ads, "mcp",
        function (k) { return laSo(k.hom_nay) ? vnd(k.hom_nay) : ""; },
        function (k) {
          // % doanh thu chỉ khi CẢ HAI số đều thật và doanh thu > 0.
          if (trangThai(dt) !== "ok" || !laSo(dt.hom_nay) || dt.hom_nay <= 0 || !laSo(k.hom_nay)) return null;
          return { chu: t("tongquan.pct_doanh_thu", { pct: phanTram(k.hom_nay / dt.hom_nay * 100) }), lop: "tq-cam" };
        }) +
      '</div>';
  }

  function bangPage(tp) {
    var tt = trangThai(tp);
    var than;
    if (tt === "chua_noi") than = oChuaNoi("mcp");
    else if (tt === "loi") than = oLoi(tp);
    else {
      var dong = Array.isArray(tp.dong) ? tp.dong : [];
      var o = function (x) { return laSo(x) ? esc(soNguyen(x)) : "-"; };
      than = dong.length ? '<div class="tq-bang-hop"><table class="tq-bang"><thead><tr>' +
        '<th scope="col">' + esc(t("tongquan.cot_page")) + '</th>' +
        '<th scope="col">' + esc(t("tongquan.cot_khach")) + '</th>' +
        '<th scope="col">' + esc(t("tongquan.cot_sdt")) + '</th>' +
        '<th scope="col">' + esc(t("tongquan.cot_don")) + '</th>' +
        '<th scope="col">' + esc(t("tongquan.cot_ty_le")) + '</th></tr></thead><tbody>' +
        dong.map(function (r) {
          return '<tr><th scope="row">' + esc(r.page || "") + '</th><td>' + o(r.khach) + '</td><td>' + o(r.sdt) +
            '</td><td>' + o(r.don) + '</td><td>' + esc(phanTram(r.ty_le)) + '</td></tr>';
        }).join("") + '</tbody></table></div>'
        : '<div class="tq-phu">' + esc(t("tongquan.page_trong")) + '</div>';
    }
    return '<section class="tq-the tq-page"><h2 class="tq-h3">' + esc(t("tongquan.theo_page")) + '</h2>' + than + '</section>';
  }

  // Hàm THUẦN: dữ liệu /tong-quan -> chuỗi HTML của cả trang.
  function html(d) {
    d = d || {};
    var cx = d.can_xu_ly;
    var soViec = trangThai(cx) === "ok" ? (Array.isArray(cx.muc) ? cx.muc.length : 0) : null;
    return '<div class="tq">' +
      phanDau(d, soViec) +
      thanhCaiDat(d.cai_dat) +
      '<div class="tq-luoi">' + khoiCanXuLy(cx) +
        '<div class="tq-cot-phai">' + theTienVao(d.tien_vao) + theChiPhiAi(d.chi_phi_ai) + '</div></div>' +
      hangSo(d.so_chinh) +
      bangPage(d.theo_page) +
      '</div>';
  }

  // ================================================================ HÀNH ĐỘNG
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  async function diTrang(trang, taskId) {
    try { window.Alpine.store("nav").go(trang); } catch (e) { location.hash = "#" + trang; }
    if (!taskId || trang !== "kanban") return;
    // renderKanban là async: đợi nó gắn JavisKanbanShow (tối đa ~3 giây), như ui-actions.js.
    for (var i = 0; i < 30; i++) {
      if (typeof window.JavisKanbanShow === "function") {
        try { await window.JavisKanbanShow(taskId); } catch (e) {}
        return;
      }
      await sleep(100);
    }
  }

  async function duyet(el, nut) {
    var li = nut.closest(".tq-muc");
    var baoLoi = li && li.querySelector(".tq-muc-loi");
    var chuCu = nut.textContent;
    nut.disabled = true;
    nut.textContent = t("tongquan.dang_gui");
    if (baoLoi) baoLoi.textContent = "";
    try {
      // Y hệt nút Duyệt của Bảng việc (console.js: bf() + post): FormData brain, id, status=done.
      var f = new FormData();
      f.append("brain", brainHienTai());
      f.append("id", nut.dataset.task);
      f.append("status", "done");
      var r = await fetch("/kanban/task/move", { method: "POST", body: f, credentials: "same-origin" });
      var kq = {};
      try { kq = await r.json(); } catch (e) {}
      if (!r.ok || !kq || !kq.ok) throw new Error((kq && kq.error) || ("HTTP " + r.status));
      if (!el.isConnected) return;
      render(el);
    } catch (e) {
      if (!el.isConnected) return;
      nut.disabled = false;
      nut.textContent = chuCu;
      if (baoLoi) baoLoi.textContent = t("tongquan.duyet_loi", { loi: e.message || "" });
    }
  }

  function noiSuKien(el) {
    el.onclick = function (ev) {
      var nut = ev.target && ev.target.closest ? ev.target.closest("[data-tq]") : null;
      if (!nut || !el.contains(nut) || nut.disabled) return;
      var loai = nut.dataset.tq;
      if (loai === "lam_moi") render(el);
      else if (loai === "trang") diTrang(nut.dataset.trang, nut.dataset.task);
      else if (loai === "link") { var u = urlAnToan(nut.dataset.url); if (u) window.open(u, "_blank", "noopener"); }
      else if (loai === "duyet") duyet(el, nut);
    };
  }

  async function render(el) {
    if (!el) return;
    el.innerHTML = '<div class="cview-placeholder">' + esc(t("sess.loading")) + '</div>';
    var d;
    try {
      d = await api("/tong-quan?brain=" + encodeURIComponent(brainHienTai()));
    } catch (e) {
      if (!el.isConnected) return;
      el.innerHTML = '<div class="cview-placeholder tq-loi-trang"><span>' +
        esc(t("tongquan.loi_tai", { loi: e.message || "" })) + '</span>' +
        '<button type="button" class="tq-nut-chinh" data-tq="lam_moi">' + esc(t("tongquan.thu_lai")) + '</button></div>';
      noiSuKien(el);
      return;
    }
    if (!el.isConnected) return;
    el.innerHTML = html(d);
    noiSuKien(el);
  }

  window.MinMinTongQuan = {
    render: render,
    // Cho test node: dựng HTML không cần DOM, và các bộ định dạng.
    _html: html,
    _fmt: { vnd: vnd, usd: usd, phanTram: phanTram, urlAnToan: urlAnToan },
  };
})();
