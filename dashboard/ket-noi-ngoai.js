/* ket-noi-ngoai.js - trang KẾT NỐI NGOÀI và hộp ĐIỀU KHOẢN SỬ DỤNG (26.10.3).
 *
 * Kết nối ngoài: các app nhà phát hành tự làm (Zalo Forwarder, Tải Hoá Đơn, Quét hoá đơn
 * Gmail). Mỗi app mở bằng MÃ KÍCH HOẠT ký số (server/giay_phep.py). Máy
 * của nhà phát hành (có khoá riêng) thấy thêm khung tạo mã cho khách.
 *
 * Điều khoản: lần đầu mở MinMin (và mỗi khi điều khoản đổi phiên bản) hiện hộp điều khoản che
 * cả màn hình, phải tích "đã đọc" rồi bấm Đồng ý mới dùng tiếp. Phụ lục riêng cho Zalo và Điều
 * khiển máy tính được hỏi thêm lúc mở các app đó (MinMinDieuKhoan.hoi).
 * Không dùng ký tự em dash. */
(function () {
  "use strict";
  function t(k, b) { return window.t ? window.t(k, b) : k; }
  function ic(n) { return window.ic ? window.ic(n) : ""; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  async function api(url, opt) {
    var r = await fetch(url, opt || {});
    var d = {};
    try { d = await r.json(); } catch (e) {}
    if (!r.ok || d.ok === false) throw new Error(d.error || ("HTTP " + r.status));
    return d;
  }
  function fd(o) { var f = new FormData(); Object.keys(o).forEach(function (k) { f.append(k, o[k]); }); return f; }
  function md(s) {
    try { if (window.mdToHtml) return window.mdToHtml(s, ""); } catch (e) {}
    return "<pre style='white-space:pre-wrap'>" + esc(s) + "</pre>";
  }

  // ================================================================ ĐIỀU KHOẢN
  var _vanBan = null;
  async function vanBan() {
    if (_vanBan) return _vanBan;
    var r = await fetch("/dieu-khoan.md", { cache: "no-cache" });
    _vanBan = await r.text();
    return _vanBan;
  }
  // Lấy riêng một phụ lục ("Phụ lục A" Zalo, "Phụ lục B" Điều khiển máy) để hỏi đúng phần đó.
  function catPhuLuc(s, chu) {
    var i = s.indexOf("## Phụ lục " + chu);
    if (i < 0) return s;
    var j = s.indexOf("\n## ", i + 5);
    return s.slice(i, j < 0 ? s.length : j);
  }

  function hopDieuKhoan(phan, noiDung) {
    return new Promise(function (xong) {
      var cu = document.getElementById("dkHop");
      if (cu) cu.remove();
      var o = document.createElement("div");
      o.id = "dkHop";
      o.className = "dk-nen";
      var tieuDe = phan === "zalo" ? t("dk.tieu_de_zalo") : phan === "dieu_khien" ? t("dk.tieu_de_dieu_khien") : t("dk.tieu_de");
      o.innerHTML = '<div class="dk-hop" role="dialog" aria-modal="true" aria-labelledby="dkTieuDe">' +
        '<div class="dk-dau" id="dkTieuDe">' + ic("scroll-text") + ' ' + esc(tieuDe) + '</div>' +
        '<div class="dk-than">' + md(noiDung) + '</div>' +
        '<label class="dk-tich"><input type="checkbox" id="dkTich"> ' + esc(t("dk.da_doc")) + '</label>' +
        '<div class="dk-chan">' +
          (phan === "chung" ? "" : '<button type="button" class="s-btn-ghost" id="dkKhong">' + esc(t("dk.khong")) + '</button>') +
          '<button type="button" class="s-btn" id="dkDongY" disabled>' + esc(t("dk.dong_y")) + '</button>' +
        '</div><div class="dk-loi" id="dkLoi"></div></div>';
      document.body.appendChild(o);
      var tich = o.querySelector("#dkTich"), nut = o.querySelector("#dkDongY");
      tich.onchange = function () { nut.disabled = !tich.checked; };
      var khong = o.querySelector("#dkKhong");
      if (khong) khong.onclick = function () { o.remove(); xong(false); };
      nut.onclick = async function () {
        nut.disabled = true;
        try {
          await api("/dieu-khoan/dong-y", { method: "POST", body: fd({ phan: phan }) });
          o.remove();
          xong(true);
        } catch (e) {
          o.querySelector("#dkLoi").textContent = e.message;
          nut.disabled = false;
        }
      };
    });
  }

  // Hỏi đồng ý một phần điều khoản nếu chưa đồng ý đúng phiên bản hiện hành. Trả true/false.
  async function hoi(phan, trangThai) {
    var tt = trangThai;
    if (!tt) { try { tt = (await api("/ket-noi-ngoai")).dieu_khoan; } catch (e) { return false; } }
    if (tt && tt[phan]) return true;
    var s = await vanBan();
    var noi = phan === "zalo" ? catPhuLuc(s, "A") : phan === "dieu_khien" ? catPhuLuc(s, "B") : s;
    return hopDieuKhoan(phan, noi);
  }
  async function xemDieuKhoan() {
    var s = await vanBan();
    var o = document.createElement("div");
    o.className = "dk-nen";
    o.innerHTML = '<div class="dk-hop"><div class="dk-dau">' + ic("scroll-text") + ' ' + esc(t("dk.tieu_de")) + '</div>' +
      '<div class="dk-than">' + md(s) + '</div><div class="dk-chan"><button type="button" class="s-btn">' + esc(t("dk.dong")) + '</button></div></div>';
    document.body.appendChild(o);
    o.querySelector("button").onclick = function () { o.remove(); };
  }
  window.MinMinDieuKhoan = { hoi: hoi, xem: xemDieuKhoan };

  // Lần mở đầu: chưa đồng ý điều khoản chung thì chặn cả app cho tới khi đồng ý.
  function kiemLucMo() {
    api("/ket-noi-ngoai").then(function (d) {
      if (!d.dieu_khoan || !d.dieu_khoan.chung) hoi("chung", d.dieu_khoan);
    }).catch(function () {});
  }

  // ================================================================ TRANG KẾT NỐI NGOÀI
  var THANG = [1, 3, 6, 12, 0];
  // Khoá dịch của từng app viết NGUYÊN VĂN (bộ quét i18n chỉ nhận khoá viết liền trong lời gọi).
  var KHOA_APP = {
    zalo_forwarder: ["knn.app.zalo_forwarder.ten", "knn.app.zalo_forwarder.mo_ta"],
    tai_hoa_don: ["knn.app.tai_hoa_don.ten", "knn.app.tai_hoa_don.mo_ta"],
    quet_hoa_don_gmail: ["knn.app.quet_hoa_don_gmail.ten", "knn.app.quet_hoa_don_gmail.mo_ta"],
    bo_chung_tu_ke_toan: ["knn.app.bo_chung_tu_ke_toan.ten", "knn.app.bo_chung_tu_ke_toan.mo_ta"],
    xuong_video: ["knn.app.xuong_video.ten", "knn.app.xuong_video.mo_ta"],
    dieu_khien_may: ["knn.app.dieu_khien_may.ten", "knn.app.dieu_khien_may.mo_ta"],
  };
  function tenApp(id) { return KHOA_APP[id] ? t(KHOA_APP[id][0]) : id; }
  function moTaApp(id) { return KHOA_APP[id] ? t(KHOA_APP[id][1]) : ""; }
  function ngayCong(thang) {
    if (!thang) return null;
    var d = new Date(); d.setMonth(d.getMonth() + thang);
    return d.toISOString().slice(0, 10);
  }
  function ngayVN(s) { return s ? s.split("-").reverse().join("/") : ""; }

  async function render(el) {
    el.innerHTML = '<div class="cview-placeholder">' + esc(t("sess.loading")) + '</div>';
    var d;
    try { d = await api("/ket-noi-ngoai"); }
    catch (e) { el.innerHTML = '<div class="cview-placeholder">' + esc(e.message) + '</div>'; return; }
    var uds = (d.ung_dung || []).filter(function (u) { return u.id !== "dieu_khien_may"; });
    el.innerHTML =
      '<div class="cview-section knn">' +
        '<div class="knn-may">' +
          '<div><div class="knn-nho">' + esc(t("knn.ma_may")) + '</div><code id="knnMaMay">' + esc(d.ma_may) + '</code>' +
          ' <button type="button" class="s-btn-ghost knn-chep" data-chep="knnMaMay">' + ic("copy") + ' ' + esc(t("knn.chep")) + '</button></div>' +
          '<div class="knn-nho">' + esc(t("knn.ma_may_giai_thich")) + '</div>' +
        '</div>' +
        '<div class="knn-kh">' +
          '<input type="text" id="knnMa" placeholder="' + esc(t("knn.nhap_ma")) + '" autocomplete="off" spellcheck="false">' +
          '<button type="button" class="s-btn" id="knnKichHoat">' + ic("key") + ' ' + esc(t("knn.kich_hoat")) + '</button>' +
        '</div>' +
        '<div class="knn-thong" id="knnThong"></div>' +
        '<div class="ud-luoi knn-luoi">' + uds.map(function (u) { return the(u, d); }).join("") + '</div>' +
        (d.nha_phat_hanh ? khungTaoMa(uds) : "") +
        '<div class="knn-chan"><a href="#" id="knnDieuKhoan">' + ic("scroll-text") + ' ' + esc(t("knn.xem_dieu_khoan")) + '</a></div>' +
      '</div>';

    el.querySelectorAll("[data-chep]").forEach(function (b) {
      b.onclick = function () {
        var x = document.getElementById(b.dataset.chep);
        if (x && navigator.clipboard) navigator.clipboard.writeText(x.textContent || x.value || "").catch(function () {});
      };
    });
    el.querySelector("#knnDieuKhoan").onclick = function (e) { e.preventDefault(); xemDieuKhoan(); };
    var thong = el.querySelector("#knnThong");
    el.querySelector("#knnKichHoat").onclick = async function () {
      var ma = el.querySelector("#knnMa").value.trim();
      if (!ma) return;
      if (!(await hoi("chung"))) return;
      try {
        var r = await api("/ket-noi-ngoai/kich-hoat", { method: "POST", body: fd({ ma: ma }) });
        thong.className = "knn-thong ok";
        thong.textContent = t("knn.da_kich_hoat", { kh: r.khach || "", han: r.het_han ? ngayVN(r.het_han) : t("knn.vinh_vien") });
        setTimeout(function () { render(el); }, 1200);
      } catch (e) {
        thong.className = "knn-thong loi";
        thong.textContent = e.message;
      }
    };
    el.querySelectorAll("[data-mo]").forEach(function (b) {
      b.onclick = async function () {
        var u = uds.filter(function (x) { return x.id === b.dataset.mo; })[0];
        if (u && u.dieu_khoan_rieng && !(await hoi(u.dieu_khoan_rieng))) return;
        thong.className = "knn-thong";
        thong.textContent = t("knn.dang_chuyen");
        // App chạy trên trang riêng (giao diện đầy đủ của nó): mở tab mới, MinMin vẫn ở tab này.
        if (u && u.duong_dan && !window.open(u.duong_dan, "_blank")) location.href = u.duong_dan;
      };
    });
    if (d.nha_phat_hanh) noiTaoMa(el);
  }

  function the(u, d) {
    var trang = !u.san_sang ? '<span class="ud-tt sap">' + esc(t("knn.sap_ra")) + '</span>'
      : u.mo ? '<span class="ud-tt on">' + esc(t("knn.da_mo")) + '</span>'
      : u.het_han_roi ? '<span class="ud-tt het">' + esc(t("knn.het_han", { ngay: ngayVN(u.het_han) })) + '</span>'
      : '<span class="ud-tt khoa">' + ic("lock") + ' ' + esc(t("knn.chua_mo")) + '</span>';
    if (u.san_sang === false && u.mo) trang += ' <span class="ud-tt on">' + esc(t("knn.da_co_ma")) + '</span>';
    var han = u.mo ? (u.het_han ? t("knn.han_den", { ngay: ngayVN(u.het_han) }) : t("knn.vinh_vien")) : "";
    return '<div class="ud-the knn-the' + (u.mo ? " mo" : "") + '">' +
      '<div class="ud-ic">' + ic(u.icon) + '</div>' +
      '<div class="ud-nd"><b>' + esc(tenApp(u.id)) + '</b>' + trang +
      '<p>' + esc(moTaApp(u.id)) + '</p>' +
      (han ? '<div class="knn-han">' + esc(han) + (u.kh ? " · " + esc(u.kh) : "") + '</div>' : "") +
      '<div class="ud-nut"><button type="button" class="s-btn" data-mo="' + esc(u.id) + '"' +
      (u.mo && u.san_sang ? "" : " disabled") + '>' + esc(t("knn.mo")) + '</button></div></div></div>';
  }

  function khungTaoMa(uds) {
    return '<div class="knn-ph"><h4>' + ic("key") + ' ' + esc(t("knn.ph_tieu_de")) + '</h4>' +
      '<p class="knn-nho">' + esc(t("knn.ph_giai_thich")) + '</p>' +
      '<div class="knn-ph-luoi">' +
        '<label>' + esc(t("knn.ph_khach")) + '<input type="text" id="phKhach"></label>' +
        '<label>' + esc(t("knn.ph_may")) + '<input type="text" id="phMay" placeholder="MM-... (' + esc(t("knn.ph_may_trong")) + ')"></label>' +
        '<label>' + esc(t("knn.ph_han")) + '<select id="phHan">' + THANG.map(function (m) {
          return '<option value="' + m + '">' + esc(m ? t("knn.ph_thang", { n: m }) : t("knn.vinh_vien")) + '</option>';
        }).join("") + '</select></label>' +
        '<label>' + esc(t("knn.ph_ghi_chu")) + '<input type="text" id="phGhiChu"></label>' +
      '</div>' +
      '<div class="knn-ph-app">' + uds.map(function (u) {
        return '<label><input type="checkbox" data-ph-app="' + esc(u.id) + '" checked> ' + esc(tenApp(u.id)) + '</label>';
      }).join("") + '</div>' +
      '<button type="button" class="s-btn" id="phTao">' + esc(t("knn.ph_tao")) + '</button>' +
      '<textarea id="phKetQua" readonly rows="3" hidden></textarea>' +
      '<div class="knn-thong" id="phThong"></div></div>';
  }
  function noiTaoMa(el) {
    el.querySelector("#phTao").onclick = async function () {
      var apps = [].map.call(el.querySelectorAll("[data-ph-app]:checked"), function (x) { return x.dataset.phApp; });
      var tong = el.querySelectorAll("[data-ph-app]").length;
      var thong = el.querySelector("#phThong"), kq = el.querySelector("#phKetQua");
      try {
        var r = await api("/ket-noi-ngoai/tao-ma", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            khach: el.querySelector("#phKhach").value, may: el.querySelector("#phMay").value.trim() || "*",
            ung_dung: apps.length === tong ? ["*"] : apps,
            het_han: ngayCong(Number(el.querySelector("#phHan").value)), ghi_chu: el.querySelector("#phGhiChu").value,
          }),
        });
        kq.hidden = false; kq.value = r.ma; kq.select();
        thong.className = "knn-thong ok"; thong.textContent = t("knn.ph_xong");
      } catch (e) { thong.className = "knn-thong loi"; thong.textContent = e.message; }
    };
  }

  window.MinMinKetNoiNgoai = { render: render };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", kiemLucMo);
  else kiemLucMo();
})();
