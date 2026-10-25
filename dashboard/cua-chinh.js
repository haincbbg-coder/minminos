/* cua-chinh.js - "Cửa chính" gọn + tín hiệu dùng (26.10.69).
 *
 * 1) Chế độ GỌN (mặc định bật, nhớ lựa chọn trên máy này): màn chính chỉ còn khung chat, quả cầu
 *    và ô gõ; thanh điều hướng và cột tổng quan được GIẤU (không xoá), gọi ra bằng nút Menu.
 *    Phần dàn trang nằm trong cua-chinh.css, file này chỉ giữ công tắc và vài việc nhỏ.
 * 2) Báo TÍN HIỆU DÙNG lên /tin-hieu (trang nào được mở, có gửi chat) để ngăn kéo đưa vài trang
 *    hay dùng lên đầu. Không gửi nội dung chat. Lỗi mạng thì bỏ qua, không ảnh hưởng gì.
 *
 * Ghi chú: KHÔNG dùng ký tự em dash ở bất kỳ đâu.
 */
(function () {
  "use strict";

  var KEY = "minmin.cuachinh";

  function docCheDo() {
    try { var v = localStorage.getItem(KEY); return v === null ? true : v === "1"; }
    catch (e) { return true; }
  }
  function luuCheDo(b) { try { localStorage.setItem(KEY, b ? "1" : "0"); } catch (e) {} }

  function tw(khoa, mac) {
    try { if (window.t) { var v = window.t(khoa); if (v && v !== khoa) return v; } } catch (e) {}
    return mac;
  }
  function nav() {
    try { return (window.Alpine && window.Alpine.store && window.Alpine.store("nav")) || null; }
    catch (e) { return null; }
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ---- Tín hiệu: bắn rồi quên ----
  function bao(loai, doiTuong) {
    try {
      fetch("/tin-hieu", {
        method: "POST", credentials: "same-origin", keepalive: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ loai: loai, doi_tuong: doiTuong || "" }),
      }).catch(function () {});
    } catch (e) {}
  }

  function dongMenu() {
    document.body.classList.remove("nav-open");
    var bd = document.getElementById("navBackdrop");
    if (bd) bd.hidden = true;
  }

  // ---- Công tắc Gọn / Đầy đủ ----
  var nutDoi = null;
  function veNutDoi() {
    if (!nutDoi) return;
    var gon = document.body.classList.contains("cua-chinh");
    nutDoi.innerHTML = '<span><b>' + esc(gon ? tw("cc.hien_day_du", "Hiện đầy đủ")
      : tw("cc.che_do_gon", "Chế độ gọn")) + '</b><span class="cc-sub">' +
      esc(gon ? tw("cc.hien_day_du_sub", "Luôn hiện thanh bên và bảng tổng quan")
        : tw("cc.che_do_gon_sub", "Chỉ một ô để nói, còn lại ẩn đến khi cần")) + "</span></span>";
  }
  function apDung(gon, tuNguoiDung) {
    document.body.classList.toggle("cua-chinh", !!gon);
    if (!gon) dongMenu();
    veNutDoi();
    if (tuNguoiDung) { luuCheDo(gon); bao("doi_che_do", gon ? "gon" : "day_du"); }
  }
  function dungNutDoi() {
    var rail = document.querySelector(".rail");
    if (!rail || nutDoi) return;
    nutDoi = document.createElement("button");
    nutDoi.type = "button";
    nutDoi.className = "cc-switch";
    nutDoi.addEventListener("click", function () {
      apDung(!document.body.classList.contains("cua-chinh"), true);
    });
    var chan = rail.querySelector(".rail-foot");
    rail.insertBefore(nutDoi, chan || null);
    veNutDoi();
  }

  // ---- "Hay dùng": vài trang người dùng hay mở nhất, lên đầu ngăn kéo ----
  function tatCaMuc() {
    var s = nav(), out = {};
    try {
      (s.groups || []).forEach(function (g) {
        (g.items || []).forEach(function (it) { out[it.id] = it; });
      });
    } catch (e) {}
    return out;
  }
  function veHayDung() {
    var rail = document.querySelector(".rail-nav");
    if (!rail) return;
    fetch("/tin-hieu/tom-tat?ngay=30", { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        var host = document.getElementById("ccHayDung");
        var muc = tatCaMuc();
        var ds = ((d && d.hay_dung) || []).filter(function (x) {
          // Tổng quan là trang mở đầu nên luôn đứng top, không cần chip "Hay dùng" (26.10.242).
          return x.so_lan >= 2 && x.id !== "home" && x.id !== "tongquan" && muc[x.id];
        }).slice(0, 4);
        if (!ds.length) { if (host) host.remove(); return; }
        if (!host) {
          host = document.createElement("div");
          host.id = "ccHayDung";
          host.className = "cc-hay-dung";
          rail.insertBefore(host, rail.firstChild);
        }
        host.innerHTML = '<div class="cc-hd-lbl">' + esc(tw("cc.hay_dung", "Hay dùng")) + "</div>" +
          ds.map(function (x) {
            return '<button type="button" class="cc-hd-chip" data-id="' + esc(x.id) + '">' +
              esc(muc[x.id].label || x.id) + "</button>";
          }).join("");
      }).catch(function () {});
  }

  function ganSuKien() {
    // Chọn một mục trong ngăn kéo (kể cả chip Hay dùng) thì đóng ngăn kéo ở chế độ gọn.
    document.addEventListener("click", function (e) {
      var chip = e.target.closest && e.target.closest(".cc-hd-chip");
      if (chip) {
        var s = nav();
        if (s && s.go) s.go(chip.getAttribute("data-id"));
      }
      if (document.body.classList.contains("cua-chinh") &&
          e.target.closest && e.target.closest(".rail-item, .cc-hd-chip")) dongMenu();
    });
    var mo = document.getElementById("navToggle");
    if (mo) mo.addEventListener("click", function () {
      if (document.body.classList.contains("nav-open")) { bao("mo_menu"); veHayDung(); }
    });
    // Gửi chat: chỉ đếm, không lấy nội dung.
    var o = document.getElementById("chatInput");
    var gui = document.getElementById("sendBtn");
    if (gui) gui.addEventListener("click", function () {
      if (o && o.value && o.value.trim()) bao("gui_chat");
    });
    if (o) o.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing && o.value && o.value.trim()) bao("gui_chat");
    });
  }

  function theoDoiTrang() {
    var thu = 0;
    var h = setInterval(function () {
      var s = nav();
      if (!s || !window.Alpine || !window.Alpine.effect) { if (++thu > 60) clearInterval(h); return; }
      clearInterval(h);
      var truoc = null;
      window.Alpine.effect(function () {
        var a = s.active;
        if (truoc !== null && a && a !== truoc) bao("mo_trang", String(a).toLowerCase().replace(/[^a-z0-9_.\-]/g, "").slice(0, 48));
        truoc = a;
      });
      dungNutDoi();
      veHayDung();
    }, 250);
  }

  function khoiDong() {
    apDung(docCheDo(), false);
    ganSuKien();
    theoDoiTrang();
    document.addEventListener("javis:i18n", veNutDoi);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", khoiDong);
  else khoiDong();
})();
