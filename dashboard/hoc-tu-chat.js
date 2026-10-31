/* hoc-tu-chat.js - khối "Học từ trò chuyện" trên trang Tự học (26.10.308).

   Máy chủ (server/hoc_tu_chat.py) chấm những lượt bố nhắn sửa, học khi cùng một lỗi lặp lại đủ ba lần, so đối
   chứng rồi mới giữ. Khối này cho bố thấy: công tắc Tạm dừng mọi cải tiến, trần mỗi ngày, lỗi đang mở, và từng
   lần học với nút Áp dụng / Bỏ (đề xuất) hoặc Hoàn tác (đã áp dụng).

   Hàm vẽ là hàm thuần (test bằng node); `mount` nối API. Chỉ dùng token --mm-* (docs/design-system.md).
   Không dùng ký tự gạch ngang dài. */
(function () {
  "use strict";

  function tw(key, vars) {
    var s = (typeof window !== "undefined" && window.t) ? window.t(key, vars) : key;
    if (vars) {
      s = String(s).replace(/\{(\w+)\}/g, function (m, name) {
        return Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : m;
      });
    }
    return s;
  }
  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function gio(ts) {
    if (!ts) return "";
    var d = new Date(ts * 1000);
    var p = function (n) { return String(n).padStart(2, "0"); };
    return p(d.getHours()) + ":" + p(d.getMinutes()) + " " + p(d.getDate()) + "/" + p(d.getMonth() + 1);
  }

  /** Tên mục tiêu cho người đọc: "skill bao-gia", "trợ lý ban-hang", "quy trình chot-don, bước 2". */
  function tenMucTieu(r) {
    r = r || {};
    if (r.loai === "agent") return tw("htc.kind_agent", { slug: r.slug });
    if (r.loai === "workflow") return tw("htc.kind_workflow", { slug: r.slug, buoc: (Number(r.buoc) || 0) + 1 });
    return tw("htc.kind_skill", { slug: r.slug });
  }

  /** Trạng thái một lần học. Viết đủ chữ từng khoá để bộ quét i18n thấy. */
  function nhanLan(r) {
    r = r || {};
    if (r.trang_thai === "dang_chay") return tw("htc.st_running");
    if (r.trang_thai === "loi") return tw("htc.st_error");
    if (r.trang_thai === "bo_qua") return tw("htc.st_skipped");
    if (r.hoan_tac_luc) return tw("htc.st_undone");
    if (r.bo_luc) return tw("htc.st_discarded");
    if (r.ap_dung) return tw("htc.st_applied");
    if (r.cho_duyet) return tw("htc.st_waiting");
    if (r.ket_luan === "giu_nguyen") return tw("htc.st_kept");
    if (r.ket_luan === "loi_engine") return tw("htc.st_engine");
    return r.ket_luan || r.trang_thai || "";
  }

  function dongKetQua(r) {
    var tt = (r && r.tom_tat) || {};
    var o = tt.ket_qua;
    if (!o) return "";
    return tw("htc.result", { thang: o.thang || 0, thua: o.thua || 0, hoa: o.hoa || 0, cau: tt.so_cau || 0 });
  }

  function thongKeHtml(tk) {
    tk = tk || {};
    var tran = tk.tran || {};
    var loi = tk.loi_mo || {};
    var ds = Object.keys(loi).sort().map(function (k) {
      return '<span class="htc-chip">' + esc(k) + " · " + esc(loi[k]) + "/" + esc(tran.loi_toi_thieu || 3) + "</span>";
    }).join(" ");
    return '<div class="htc-stat">' + esc(tw("htc.stats", {
      cham: tk.cham_hom_nay || 0, tran_cham: tran.cham || 40, hoc: tk.hoc_hom_nay || 0, tran_hoc: tran.hoc || 1,
      cho: tk.cho_cham || 0 })) + "</div>"
      + (ds ? '<div class="htc-open">' + esc(tw("htc.open_mistakes")) + " " + ds + "</div>" : "");
  }

  function lanHtml(r) {
    var nut = "";
    if (r.cho_duyet) {
      nut = '<button class="s-btn htc-ap" data-ma="' + esc(r.id) + '">' + esc(tw("htc.apply")) + "</button>"
        + ' <button class="s-btn-ghost htc-bo" data-ma="' + esc(r.id) + '">' + esc(tw("htc.discard")) + "</button>";
    } else if (r.ap_dung && !r.hoan_tac_luc) {
      nut = '<button class="s-btn-ghost htc-ht" data-ma="' + esc(r.id) + '">' + esc(tw("htc.undo")) + "</button>";
    }
    var ban = r.cho_duyet && r.ban_moi
      ? '<details class="htc-ban"><summary>' + esc(tw("htc.see_new")) + "</summary><pre>" + esc(r.ban_moi) + "</pre></details>"
      : "";
    var ly = r.ly_do ? '<div class="htc-ly">' + esc(r.ly_do) + "</div>" : "";
    var loi = r.loi ? '<div class="htc-ly">' + esc(r.loi) + "</div>" : "";
    return '<div class="le htc-lan"><b>' + esc(tenMucTieu(r)) + "</b> "
      + '<span class="htc-tag">' + esc(nhanLan(r)) + "</span> "
      + '<span class="htc-dim">' + esc(gio(r.bat_dau)) + "</span>"
      + (dongKetQua(r) ? '<div class="htc-dim">' + esc(dongKetQua(r)) + "</div>" : "")
      + ly + loi + ban + (nut ? '<div class="htc-nut">' + nut + "</div>" : "") + "</div>";
  }

  function khungHtml(tamDung) {
    return '<h3 class="htc-h">' + esc(tw("htc.head")) + "</h3>"
      + '<p class="htc-p">' + esc(tw("htc.desc")) + "</p>"
      + '<div class="htc-row"><button class="si-chip ' + (tamDung ? "sel" : "") + '" id="htcPause">'
      + (tamDung ? "● " + esc(tw("htc.paused_on")) : "○ " + esc(tw("htc.paused_off"))) + "</button>"
      + '<span class="htc-dim">' + esc(tw("htc.pause_note")) + "</span></div>"
      + '<div id="htcStats"></div><div id="htcRuns"></div><div class="htc-dim" id="htcMsg"></div>';
  }

  async function getJ(url) { var r = await fetch(url); return r.json(); }
  async function postJ(url, body) {
    var r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
    return r.json();
  }

  function mount(el, fbrain) {
    if (!el) return;
    var brain = function () { return (typeof fbrain === "function" ? fbrain() : fbrain) || "brain"; };
    async function load() {
      var d = {};
      try { d = await getJ("/hoc-tu-chat/tong-quan?brain=" + encodeURIComponent(brain())); } catch (e) { d = {}; }
      var tk = d.thong_ke || {};
      el.innerHTML = khungHtml(!!tk.tam_dung);
      el.querySelector("#htcStats").innerHTML = thongKeHtml(tk);
      var ls = d.lich_su || [];
      el.querySelector("#htcRuns").innerHTML = ls.length ? ls.map(lanHtml).join("")
        : '<div class="htc-dim">' + esc(tw("htc.empty")) + "</div>";
      el.querySelector("#htcPause").onclick = async function () {
        await postJ("/hoc-tu-chat/tam-dung", { brain: brain(), bat: !tk.tam_dung });
        load();
      };
      el.querySelector("#htcRuns").onclick = async function (ev) {
        var b = ev.target.closest("button[data-ma]");
        if (!b) return;
        var duong = b.classList.contains("htc-ap") ? "ap-dung" : b.classList.contains("htc-bo") ? "bo" : "hoan-tac";
        if (duong === "hoan-tac" && !confirm(tw("htc.undo_confirm"))) return;
        b.disabled = true;
        var r = {};
        try { r = await postJ("/hoc-tu-chat/" + duong, { brain: brain(), ma: b.getAttribute("data-ma") }); } catch (e) { r = { error: e.message }; }
        if (!r.ok) { el.querySelector("#htcMsg").textContent = r.error || "?"; b.disabled = false; return; }
        load();
      };
    }
    load();
  }

  var api_ = { mount: mount, tenMucTieu: tenMucTieu, nhanLan: nhanLan, dongKetQua: dongKetQua,
               thongKeHtml: thongKeHtml, lanHtml: lanHtml, khungHtml: khungHtml };
  if (typeof window !== "undefined") window.MinMinHocTuChat = api_;
  if (typeof module !== "undefined" && module.exports) module.exports = api_;
})();
