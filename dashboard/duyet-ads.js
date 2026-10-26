/* duyet-ads.js - thẻ duyệt bật/tắt chiến dịch trong khung chat (Phase 04 của
 * plans/fb-nhieu-tai-khoan/PLAN.md).
 *
 * chat-card.js biến khối <!-- JAVIS_CARD: {"type":"duyet_ads","id":"..."} --> thành khung chờ
 * <div class="jv-card dads" data-duyet-ads="<id>">. File này tìm mọi khung chờ (quét đầu + một
 * MutationObserver), nạp GET /meta-ads/duyet/<id> rồi vẽ thẻ. Nút Duyệt / Sửa lại / Từ chối /
 * Hoàn tác gọi POST /meta-ads/duyet/<id> (form hanh_dong=duyet|sua|tu_choi|hoan_tac) và vẽ lại
 * từ bản ghi máy chủ trả về.
 *
 * Luật: NỘI DUNG THẺ CHỈ LẤY TỪ MÁY CHỦ, không bao giờ từ chữ model (model chỉ đưa được id, id
 * bị ép theo [a-z0-9]{8,32}). Mọi chuỗi đi qua esc(). Phần dựng HTML là hàm thuần (htmlThe) để
 * test node chạy không cần DOM. Không dùng em dash. */
(function () {
  "use strict";
  var W = typeof window !== "undefined" ? window : null;
  var VI_NODE = null;
  function t(k, b) {
    if (W && W.t) return W.t(k, b);
    var s = null;
    try { VI_NODE = VI_NODE || require("./i18n/vi.json"); s = VI_NODE[k]; } catch (e) {}
    if (s == null) return k;
    return String(s).replace(/\{(\w+)\}/g, function (m, n) { return b && b[n] != null ? String(b[n]) : m; });
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  var ID_RE = /^[a-z0-9]{8,32}$/;

  // ================================================================ HÀM THUẦN
  function tien(v) {
    if (v == null || v === "") return "";
    var n = typeof v === "number" ? v : parseFloat(String(v).replace(/[^\d.\-]/g, ""));
    if (!isFinite(n)) return "";
    var am = n < 0, s = String(Math.round(Math.abs(n)));
    return (am ? "-" : "") + s.replace(/\B(?=(\d{3})+(?!\d))/g, ".") + " đ";
  }
  // Bản ghi có thể tới trần hoặc bọc trong {de_xuat|ban_ghi|record}.
  function laBanGhi(d) {
    if (!d || typeof d !== "object") return null;
    var r = d.de_xuat || d.ban_ghi || d.record || d;
    return r && typeof r === "object" && (r.id || Array.isArray(r.muc)) ? r : null;
  }
  function loaiCap(cap) {
    var c = String(cap || "").toLowerCase();
    if (c === "campaign" || c === "chien_dich") return "chien_dich";
    if (c === "adset" || c === "nhom" || c === "nhom_qc" || c === "ad_set") return "nhom";
    if (c === "ad" || c === "quang_cao") return "quang_cao";
    return "";
  }
  function tieuDe(rec) {
    var muc = Array.isArray(rec && rec.muc) ? rec.muc : [];
    var kq = Array.isArray(rec && rec.ket_qua) ? rec.ket_qua : null;
    if (kq && kq.length) {
      var ok = kq.filter(function (x) { return x && x.ok; }).length;
      return t("dads.da_doi", { x: ok, y: kq.length });
    }
    var caps = {};
    muc.forEach(function (m) { caps[loaiCap(m && m.cap)] = 1; });
    var ks = Object.keys(caps), n = muc.length;
    var k = ks.length === 1 ? ks[0] : "";
    if (k === "chien_dich") return t("dads.sap_doi_cd", { n: n });
    if (k === "nhom") return t("dads.sap_doi_nhom", { n: n });
    if (k === "quang_cao") return t("dads.sap_doi_qc", { n: n });
    return t("dads.sap_doi_dt", { n: n });
  }
  function chipTrangThai(tt) {
    return {
      cho: { cls: "warn", chu: t("dads.tt_cho") },
      dang_chay: { cls: "warn", chu: t("dads.tt_dang_chay") },
      sua: { cls: "warn", chu: t("dads.tt_sua") },
      xong: { cls: "ok", chu: t("dads.tt_xong") },
      hoan_tac: { cls: "ok", chu: t("dads.tt_hoan_tac") },
      tu_choi: { cls: "bad", chu: t("dads.tt_tu_choi") },
      het_han: { cls: "bad", chu: t("dads.tt_het_han") },
      loi: { cls: "bad", chu: t("dads.tt_loi") },
    }[tt] || { cls: "warn", chu: t("dads.tt_khac") };
  }
  function bat(v) {
    var s = String(v || "").toUpperCase();
    if (s === "ACTIVE" || s === "BAT") return true;
    if (s === "PAUSED" || s === "TAT" || s === "ARCHIVED" || s === "DELETED") return false;
    return null;
  }
  // phia "tu" = hiện tại ("Đang chạy"/"Đang tắt"), "sang" = sẽ thành ("Bật"/"Tắt").
  function chipBatTat(v, phia) {
    var b = bat(v);
    if (b === true) return { cls: "ok", chu: phia === "tu" ? t("dads.dang_chay") : t("dads.bat") };
    if (b === false) return { cls: "bad", chu: phia === "tu" ? t("dads.dang_tat") : t("dads.tat") };
    return { cls: "mo", chu: String(v || "-") };
  }
  function chip(c) { return '<span class="dads-chip ' + esc(c.cls) + '">' + esc(c.chu) + '</span>'; }

  function dongMuc(m, kq) {
    var chi = tien(m.chi_hom_nay), ns = tien(m.ngan_sach_ngay);
    var so = [];
    if (chi) so.push(t("dads.chi_hom_nay", { tien: chi }));
    if (ns) so.push(t("dads.ngan_sach_ngay", { tien: ns }));
    var ketQua = "";
    if (kq) {
      ketQua = kq.ok
        ? '<span class="dads-kq ok">' + esc(t("dads.kq_ok", { tt: chipBatTat(kq.trang_thai_moi, "tu").chu })) + '</span>'
        : '<span class="dads-kq bad">' + esc(t("dads.kq_loi", { loi: kq.loi || "" })) + '</span>';
    }
    return '<li class="dads-muc">' +
      '<div class="dads-muc-chu"><b class="dads-ten">' + esc(m.ten || m.id) + '</b>' +
        '<span class="dads-phu">' + esc(t("dads.dong_tk", { tk: m.tk_ten || m.tk_id || "", fb: m.fb_ten || m.fb_id || "" })) + '</span>' +
        (so.length ? '<span class="dads-phu">' + esc(so.join(" · ")) + '</span>' : "") + ketQua + '</div>' +
      '<div class="dads-muc-tt">' + chip(chipBatTat(m.tu, "tu")) +
        '<span class="dads-mui" aria-label="' + esc(t("dads.thanh")) + '">-&gt;</span>' + chip(chipBatTat(m.sang, "sang")) + '</div></li>';
  }
  // Hàm THUẦN: bản ghi đề xuất + state -> HTML bên trong thẻ.
  function htmlThe(rec, st) {
    st = st || {};
    if (!rec) {
      if (st.loi) return '<div class="dads-loi" role="alert">' + esc(t("dads.loi_tai", { loi: st.loi })) + '</div>';
      return '<div class="dads-phu">' + esc(t("dads.dang_tai")) + '</div>';
    }
    var muc = (Array.isArray(rec.muc) ? rec.muc : []).filter(function (m) { return m && typeof m === "object"; });
    var kq = {};
    (Array.isArray(rec.ket_qua) ? rec.ket_qua : []).forEach(function (x) { if (x && x.id != null) kq[String(x.id)] = x; });
    var tt = String(rec.trang_thai || "");
    var gui = st.gui || "";
    var dis = gui ? " disabled" : "";
    var nut = "";
    if (tt === "cho") {
      nut = '<button type="button" class="dads-nut-chinh" data-dads-act="duyet"' + dis + '>' + esc(gui === "duyet" ? t("dads.dang_gui") : t("dads.duyet")) + '</button>' +
        '<button type="button" class="dads-nut-phu" data-dads-act="sua"' + dis + '>' + esc(gui === "sua" ? t("dads.dang_gui") : t("dads.sua")) + '</button>' +
        '<button type="button" class="dads-nut-bo" data-dads-act="tu_choi"' + dis + '>' + esc(gui === "tu_choi" ? t("dads.dang_gui") : t("dads.tu_choi")) + '</button>';
    } else if (rec.co_the_hoan_tac === true) {
      nut = '<button type="button" class="dads-nut-phu" data-dads-act="hoan_tac"' + dis + '>' + esc(gui === "hoan_tac" ? t("dads.dang_gui") : t("dads.hoan_tac")) + '</button>';
    }
    var ghiChu = tt === "cho" ? '<p class="dads-ghi-chu">' + esc(t("dads.ghi_chu")) + '</p>' : "";
    return '<div class="dads-dau"><b class="dads-tieu-de">' + esc(tieuDe(rec)) + '</b>' + chip(chipTrangThai(tt)) + '</div>' +
      (rec.ly_do ? '<p class="dads-ly-do">' + esc(t("dads.ly_do_minmin", { ly_do: rec.ly_do })) + '</p>' : "") +
      '<ul class="dads-ds">' + (muc.length ? muc.map(function (m) { return dongMuc(m, kq[String(m.id)]); }).join("")
        : '<li class="dads-muc dads-phu">' + esc(t("dads.rong")) + '</li>') + '</ul>' +
      ghiChu +
      (rec.thong_bao && tt !== "cho" ? '<p class="dads-ghi-chu" role="status">' + esc(rec.thong_bao) + '</p>' : "") +
      (nut ? '<div class="dads-nut">' + nut + '</div>' : "") +
      '<div class="dads-loi" role="alert">' + esc(st.loi || "") + '</div>';
  }

  // ================================================================ DOM
  var KHO = {};      // id -> bản ghi mới nhất
  var DANG = {};     // id -> Promise đang nạp
  var ST = {};       // id -> {gui, loi}

  function veTatCa(id) {
    if (typeof document === "undefined") return;
    var ds = document.querySelectorAll('[data-duyet-ads="' + id + '"]');
    Array.prototype.forEach.call(ds, function (el) {
      el.setAttribute("data-dads-nap", "1");
      el.setAttribute("aria-busy", ST[id] && ST[id].gui ? "true" : "false");
      el.innerHTML = htmlThe(KHO[id] || null, ST[id] || {});
    });
  }
  async function goi(url, opt) {
    var r = await fetch(url, Object.assign({ credentials: "same-origin" }, opt || {}));
    var d = {};
    try { d = await r.json(); } catch (e) {}
    if (!r.ok || d.ok === false) throw new Error(d.loi || d.error || d.detail || (r.status === 404 ? t("dads.khong_co") : "HTTP " + r.status));
    return d;
  }
  function nap(id) {
    if (DANG[id]) return DANG[id];
    DANG[id] = (async function () {
      try {
        var rec = laBanGhi(await goi("/meta-ads/duyet/" + encodeURIComponent(id)));
        if (!rec) throw new Error(t("dads.khong_co"));
        KHO[id] = rec;
        ST[id] = Object.assign({}, ST[id], { loi: "" });
      } catch (e) {
        ST[id] = Object.assign({}, ST[id], { loi: e.message || "" });
      } finally {
        delete DANG[id];
        veTatCa(id);
      }
    })();
    return DANG[id];
  }
  function moChoSua(id) {
    var chu = t("dads.sua_mau", { id: id });
    var o = document.getElementById("chatInput");
    if (o) {
      o.value = chu;
      try { o.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) {}
      try { o.focus(); o.setSelectionRange(chu.length, chu.length); } catch (e) {}
      return;
    }
    if (W && typeof W.JavisSend === "function") W.JavisSend(chu);
  }
  async function quyet(id, hanh) {
    var s = ST[id] = Object.assign({}, ST[id]);
    if (s.gui) return;
    s.gui = hanh; s.loi = "";
    veTatCa(id);
    try {
      var body = new URLSearchParams();
      body.append("hanh_dong", hanh);
      var rec = laBanGhi(await goi("/meta-ads/duyet/" + encodeURIComponent(id), { method: "POST", body: body }));
      if (rec) KHO[id] = rec;
      ST[id] = { gui: "", loi: "" };
      if (hanh === "sua") moChoSua(id);
    } catch (e) {
      ST[id] = { gui: "", loi: t("dads.loi_gui", { loi: e.message || "" }) };
    }
    veTatCa(id);
  }
  function quet(goc) {
    if (!goc || !goc.querySelectorAll) return;
    var ds = goc.querySelectorAll("[data-duyet-ads]:not([data-dads-nap])");
    if (goc.matches && goc.matches("[data-duyet-ads]:not([data-dads-nap])")) ds = [goc].concat(Array.prototype.slice.call(ds));
    Array.prototype.forEach.call(ds, function (el) {
      var id = el.getAttribute("data-duyet-ads") || "";
      el.setAttribute("data-dads-nap", "1");
      if (!ID_RE.test(id)) { el.innerHTML = '<div class="dads-loi">' + esc(t("dads.khong_co")) + '</div>'; return; }
      // Khung chat vẽ lại tin nhắn nhiều lần khi đang stream: có bản ghi rồi thì vẽ ngay, khỏi gọi lại.
      el.innerHTML = htmlThe(KHO[id] || null, ST[id] || {});
      if (!KHO[id]) nap(id);
    });
  }
  if (typeof document !== "undefined" && typeof MutationObserver !== "undefined") {
    document.addEventListener("click", function (ev) {
      var nut = ev.target && ev.target.closest ? ev.target.closest("[data-dads-act]") : null;
      if (!nut || nut.disabled) return;
      var the = nut.closest("[data-duyet-ads]");
      var id = the ? the.getAttribute("data-duyet-ads") : "";
      if (!ID_RE.test(id)) return;
      ev.preventDefault();
      quyet(id, nut.getAttribute("data-dads-act"));
    });
    var batDau = function () {
      quet(document.body);
      new MutationObserver(function (ds) {
        ds.forEach(function (m) {
          Array.prototype.forEach.call(m.addedNodes || [], function (n) { if (n.nodeType === 1) quet(n); });
        });
      }).observe(document.body, { childList: true, subtree: true });
    };
    if (document.body) batDau(); else document.addEventListener("DOMContentLoaded", batDau);
  }

  var API = { htmlThe: htmlThe, tieuDe: tieuDe, chipTrangThai: chipTrangThai, chipBatTat: chipBatTat, tien: tien,
    laBanGhi: laBanGhi, loaiCap: loaiCap, ID_RE: ID_RE, quet: quet, nap: nap };
  if (W) W.DuyetAds = API;
  if (typeof module !== "undefined" && module.exports) module.exports = API;
})();
