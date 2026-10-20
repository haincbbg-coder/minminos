/* Đội Social - lõi trang (MinMin 26.10.187). JS thuần, không thư viện, không bước build.
   Mỗi màn hình ở views/<ten>.js đăng ký bằng DS.view(ten, {title, render(el, ctx)}). */
(function () {
  "use strict";
  var DS = window.DS = { views: {}, cache: {} };
  DS.PHIEN_BAN = "26.10.187";

  // ---------------------------------------------------------------- tiện ích chữ
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  DS.esc = esc;
  DS.so = function (n) { n = Number(n) || 0; try { return n.toLocaleString("vi-VN"); } catch (e) { return String(n); } };
  DS.viet_tat = function (s) {
    var w = String(s || "?").trim().split(/[\s_\-.]+/).filter(Boolean);
    if (!w.length) return "?";
    return ((w[0][0] || "") + (w.length > 1 ? w[w.length - 1][0] : (w[0][1] || ""))).toUpperCase();
  };
  var MAU_AV = ["#7c3aed", "#6366f1", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444", "#ec4899", "#8b5cf6", "#22c55e", "#64748b"];
  DS.av = function (ten, cls) {
    var h = 0, s = String(ten || "");
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return '<span class="av ' + (cls || "") + '" style="background:' + MAU_AV[h % MAU_AV.length] + '">' + esc(DS.viet_tat(s)) + "</span>";
  };
  DS.list = function (d, key) {
    if (!d) return [];
    if (Array.isArray(d)) return d;
    if (Array.isArray(d._list)) return d._list;
    if (key && Array.isArray(d[key])) return d[key];
    if (Array.isArray(d.muc)) return d.muc;
    return [];
  };

  // ---------------------------------------------------------------- thời gian (giờ địa phương trình duyệt)
  function ngay(t) { return t ? new Date(t * 1000) : null; }
  function p2(n) { return (n < 10 ? "0" : "") + n; }
  DS.gio = function (t) { var d = ngay(t); return d ? p2(d.getDate()) + "/" + p2(d.getMonth() + 1) + " " + p2(d.getHours()) + ":" + p2(d.getMinutes()) : ""; };
  DS.gioDu = function (t) { var d = ngay(t); return d ? d.toLocaleString("vi-VN") : ""; };
  DS.gioPhut = function (t) { var d = ngay(t); return d ? p2(d.getHours()) + ":" + p2(d.getMinutes()) : ""; };
  DS.tuongDoi = function (t) {
    if (!t) return "";
    var s = Math.round(t - Date.now() / 1000), a = Math.abs(s), x;
    if (a < 45) return s >= 0 ? "sắp tới" : "vừa xong";
    if (a < 3600) x = Math.round(a / 60) + " phút";
    else if (a < 86400) x = Math.round(a / 3600) + " giờ";
    else if (a < 86400 * 30) x = Math.round(a / 86400) + " ngày";
    else return DS.gio(t);
    return s >= 0 ? x + " nữa" : x + " trước";
  };
  DS.bayGio = function () { return Date.now() / 1000; };

  // ---------------------------------------------------------------- biểu tượng (vẽ tay, nét đơn)
  var IC = {
    home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20h14V9.5"/><path d="M10 20v-5h4v5"/>',
    bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    box: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M18.5 14.8c1.6.8 2.7 2.5 3 5.2"/>',
    check: '<path d="M9 11.5 11.5 14 16 9"/><rect x="3" y="3" width="18" height="18" rx="5"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.6A8 8 0 1 1 21 12z"/>',
    spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4"/><path d="m12 7 1.6 3.4L17 12l-3.4 1.6L12 17l-1.6-3.4L7 12l3.4-1.6z"/>',
    book: '<path d="M4 4.5A1.5 1.5 0 0 1 5.5 3H20v15H5.5A1.5 1.5 0 0 0 4 19.5z"/><path d="M4 19.5A1.5 1.5 0 0 0 5.5 21H20"/><path d="M8 7h8"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c.8-4 4-6 8-6s7.2 2 8 6"/>',
    gauge: '<path d="M4.9 18A8.5 8.5 0 1 1 19.1 18"/><path d="m12 13 4-4"/><circle cx="12" cy="13" r="1.3"/>',
    monitor: '<rect x="3" y="4" width="18" height="12" rx="2.5"/><path d="M8 20h8M12 16v4"/>',
    chev: '<path d="m6 9 6 6 6-6"/>',
    chevr: '<path d="m9 6 6 6-6 6"/>',
    list: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4 6.5 6.5 0 0 0 20 14.5z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.5-4.5L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.5 4.5L20 16"/><path d="M20 20v-4h-4"/>',
    download: '<path d="M12 4v11M7 10l5 5 5-5"/><path d="M4 19h16"/>',
    upload: '<path d="M12 16V5M7 10l5-5 5 5"/><path d="M4 19h16"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4-4"/>',
    play: '<path d="M7 4.5v15l12-7.5z"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6"/><path d="M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
    eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    alert: '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4.5M12 17.5v.1"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6v.1"/>',
    ok: '<circle cx="12" cy="12" r="9"/><path d="m8 12.5 2.7 2.7L16 10"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
    send: '<path d="M21 3 10 14"/><path d="M21 3l-6.5 18-4-8-8-4z"/>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    tag: '<path d="M3 12V4h8l9.5 9.5-8 8z"/><circle cx="7.5" cy="8.5" r="1.3"/>',
    file: '<path d="M14 3H6.5A1.5 1.5 0 0 0 5 4.5v15A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V8z"/><path d="M14 3v5h5M9 13h6M9 17h4"/>',
    robot: '<rect x="4" y="8" width="16" height="11" rx="3.5"/><path d="M12 4v4M9 13v1M15 13v1M2 13v2M22 13v2"/><circle cx="12" cy="3.5" r="1"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    phone: '<path d="M6.5 3h3l1.5 4.5-2 1.5a11 11 0 0 0 6 6l1.5-2L21 14.5v3a2 2 0 0 1-2 2A16 16 0 0 1 4.5 5a2 2 0 0 1 2-2z"/>',
    filter: '<path d="M4 5h16l-6 8v6l-4-2v-4z"/>',
    image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><circle cx="9" cy="10" r="1.8"/><path d="m4 18 5-5 4 4 2.5-2.5L20 19"/>',
    video: '<rect x="3" y="6" width="13" height="12" rx="2.5"/><path d="m16 10.5 5-3v9l-5-3z"/>'
  };
  DS.ic = function (ten, cls) {
    return '<svg class="ic ' + (cls || "") + '" viewBox="0 0 24 24" aria-hidden="true">' + (IC[ten] || IC.info) + "</svg>";
  };

  // ---------------------------------------------------------------- nền tảng: chữ cái trên nền màu tròn (không chép logo)
  DS.NT = {
    facebook: { ten: "Facebook", mau: "#1877f2", chu: "f" },
    tiktok: { ten: "TikTok", mau: "#111827", chu: "T" },
    youtube: { ten: "YouTube", mau: "#ef4444", chu: "▶" },
    threads: { ten: "Threads", mau: "#27272a", chu: "@" },
    instagram: { ten: "Instagram", mau: "url(#g-ig)", chu: "I" },
    x: { ten: "X", mau: "#0f0f0f", chu: "X" },
    reddit: { ten: "Reddit", mau: "#ff4500", chu: "R" },
    telegram: { ten: "Telegram", mau: "#229ed9", chu: "➤" }
  };
  DS.NT_THU_TU = ["facebook", "tiktok", "youtube", "threads", "instagram", "x", "reddit"];
  DS.icNT = function (id, size) {
    var n = DS.NT[id] || { ten: id, mau: "#94a3b8", chu: String(id || "?").charAt(0).toUpperCase() };
    size = size || 28;
    var fs = n.chu === "▶" || n.chu === "➤" ? 10 : (n.chu === "f" ? 15 : 12.5);
    var defs = id === "instagram" ? '<defs><linearGradient id="g-ig" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#f59e0b"/><stop offset=".5" stop-color="#ec4899"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs>' : "";
    return '<svg class="nt" width="' + size + '" height="' + size + '" viewBox="0 0 28 28" role="img" aria-label="' + esc(n.ten) + '">' + defs +
      '<circle cx="14" cy="14" r="14" fill="' + n.mau + '"/><text x="14" y="14" dy=".36em" text-anchor="middle" fill="#fff" font-family="Arial,Helvetica,sans-serif" font-weight="700" font-size="' +
      fs + '">' + esc(n.chu) + "</text></svg>";
  };
  DS.tenNT = function (id) { return (DS.NT[id] || {}).ten || id || ""; };

  DS.NOI_DANG = {
    fb_nhom: "Nhóm Facebook", fb_tuong: "Tường Facebook", fb_trang: "Trang Facebook", threads: "Threads",
    instagram: "Instagram", reddit: "Reddit", x: "X", tiktok: "TikTok"
  };
  DS.NOI_DANG_NT = { fb_nhom: "facebook", fb_tuong: "facebook", fb_trang: "facebook", threads: "threads", instagram: "instagram", reddit: "reddit", x: "x", tiktok: "tiktok" };
  DS.KET_QUA = { thanh_cong: ["Thành công", "ok"], bo_qua: ["Bỏ qua", "mu"], loi: ["Lỗi", "err"], thong_tin: ["Thông tin", "info"], het_bai: ["Hết bài", "warn"] };
  DS.TT_VIEC = { cho_duyet: ["Chờ duyệt", "warn"], cho_chay: ["Chờ máy nhận", "info"], dang_chay: ["Đang chạy", "brand"], xong: ["Thành công", "ok"],
    loi: ["Thất bại", "err"], bo: ["Đã huỷ", "mu"], bo_qua: ["Bỏ qua", "mu"] };
  DS.ttViec = function (v) {
    if (v && v.trang_thai === "bo" && (v.ket_qua || {}).bo_qua) return DS.bd("Bỏ qua", "mu");
    return DS.bdMap(DS.TT_VIEC, v && v.trang_thai);
  };
  DS.TT_DOT = { cho: ["Đang chờ", "info"], dang_chay: ["Đang chạy", "brand"], hoan_tat: ["Hoàn tất", "ok"], huy: ["Đã huỷ", "mu"] };
  DS.CANH_BAO = { dang_xuat: "Đăng xuất", checkpoint: "Checkpoint", captcha: "Captcha", qua_nhanh: "Bị chặn vì quá nhanh" };
  DS.bd = function (txt, kieu, dot) {
    return '<span class="bd' + (kieu && kieu !== "mu" ? " bd-" + kieu : "") + '">' + (dot ? '<i class="dot"></i>' : "") + esc(txt) + "</span>";
  };
  DS.bdMap = function (map, k) { var x = map[k] || [k || "?", "mu"]; return DS.bd(x[0], x[1]); };

  // ---------------------------------------------------------------- gọi API (không bao giờ ném lỗi ra ngoài)
  DS.api = function (method, path, body, opt) {
    opt = opt || {};
    var o = { method: method || "GET", credentials: "same-origin", headers: { accept: "application/json" } };
    if (typeof FormData !== "undefined" && body instanceof FormData) o.body = body;
    else if (body !== undefined && body !== null) { o.body = JSON.stringify(body); o.headers["content-type"] = "application/json"; }
    var p;
    try { p = fetch(path, o); } catch (e) { p = Promise.reject(e); }
    return p.then(function (r) {
      return r.text().then(function (t) {
        var d;
        try { d = t ? JSON.parse(t) : {}; } catch (e) { d = { ok: false, error: r.ok ? "Máy chủ trả dữ liệu không đọc được" : "Lỗi máy chủ " + r.status }; }
        if (Array.isArray(d)) d = { ok: r.ok, _list: d };
        if (d === null || typeof d !== "object") d = { ok: r.ok, value: d };
        if (!r.ok || d.ok === false) {
          var msg = d.error || (typeof d.detail === "string" ? d.detail : "") || "";
          if (r.status === 401) msg = "Phiên đăng nhập MinMin đã hết, hãy đăng nhập lại.";
          else if (r.status === 404 && !msg) msg = "Máy chủ chưa có chức năng này (" + path.split("?")[0] + ").";
          else if (!msg) msg = "Lỗi máy chủ " + r.status;
          d = { ok: false, error: msg, status: r.status };
          if (!opt.quiet) DS.toast(msg, "err");
        }
        return d;
      });
    }).catch(function (e) {
      var msg = "Không kết nối được máy chủ MinMin.";
      if (!opt.quiet) DS.toast(msg, "err");
      return { ok: false, error: msg, status: 0 };
    });
  };
  DS.qs = function (o) {
    var a = [];
    Object.keys(o || {}).forEach(function (k) { var v = o[k]; if (v !== undefined && v !== null && v !== "") a.push(encodeURIComponent(k) + "=" + encodeURIComponent(v)); });
    return a.length ? "?" + a.join("&") : "";
  };

  // dữ liệu dùng chung, nhớ tạm 60 giây
  function nho(key, path, ttl) {
    return function (moi) {
      var c = DS.cache[key];
      if (!moi && c && Date.now() - c.t < (ttl || 60000)) return Promise.resolve(c.d);
      return DS.api("GET", path, null, { quiet: true }).then(function (d) {
        if (d.ok !== false) DS.cache[key] = { t: Date.now(), d: d };
        return d;
      });
    };
  }
  DS.layKichBan = nho("kb", "/doi-social/kich-ban", 120000);
  DS.layNick = nho("nick", "/doi-social/nick");
  DS.layKienThuc = nho("kt", "/doi-social/kien-thuc");
  DS.boNho = function (key) { delete DS.cache[key]; };
  DS.dsMau = function (kb) { return DS.list(kb, "mau").length ? DS.list(kb, "mau") : ((kb && kb.danh_muc && kb.danh_muc.mau) || []); };
  DS.mauTheoId = function (kb) { var m = {}; DS.dsMau(kb).forEach(function (x) { m[x.id] = x; }); return m; };
  DS.tenHD = function (kb, k) { var h = (kb && (kb.hanh_dong || (kb.danh_muc && kb.danh_muc.hanh_dong))) || {}; return h[k] || k || ""; };

  // ---------------------------------------------------------------- toast, tooltip
  DS.toast = function (msg, kieu) {
    var box = document.getElementById("toasts");
    if (!box) return;
    var t = document.createElement("div");
    kieu = kieu || "info";
    t.className = "toast " + kieu;
    t.innerHTML = DS.ic(kieu === "err" ? "alert" : kieu === "ok" ? "ok" : "info") + "<span>" + esc(msg) + "</span>";
    box.appendChild(t);
    while (box.children.length > 4) box.removeChild(box.firstChild);
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, kieu === "err" ? 6000 : 3800);
  };
  DS.tip = function (html, x, y) {
    var t = document.getElementById("tip");
    if (!t) return;
    if (!html) { t.hidden = true; return; }
    t.innerHTML = html; t.hidden = false;
    var w = t.offsetWidth, h = t.offsetHeight;
    var L = Math.min(window.innerWidth - w - 8, Math.max(8, x - w / 2)), T = y - h - 12;
    if (T < 8) T = y + 16;
    t.style.left = L + "px"; t.style.top = T + "px";
  };

  // ---------------------------------------------------------------- hộp thoại
  DS.modal = function (o) {
    var bg = document.createElement("div");
    bg.className = "modal-bg";
    bg.innerHTML = '<div class="modal' + (o.wide ? " wide" : "") + '" role="dialog" aria-modal="true"><div class="modal-h"><h3>' + esc(o.title || "") +
      '</h3><button class="icon-btn" type="button" data-x aria-label="Đóng">' + DS.ic("x") + '</button></div><div class="modal-b"></div>' +
      (o.foot !== false ? '<div class="modal-f"></div>' : "") + "</div>";
    var b = bg.querySelector(".modal-b"), f = bg.querySelector(".modal-f");
    b.innerHTML = o.body || "";
    if (f) f.innerHTML = o.foot || '<button class="btn" type="button" data-x>Đóng</button>';
    function dong() { if (bg.parentNode) bg.parentNode.removeChild(bg); document.removeEventListener("keydown", phim); if (o.onClose) o.onClose(); }
    function phim(e) { if (e.key === "Escape") dong(); }
    bg.addEventListener("click", function (e) { if (e.target === bg || e.target.closest("[data-x]")) dong(); });
    document.addEventListener("keydown", phim);
    document.body.appendChild(bg);
    var m = { el: bg.querySelector(".modal"), body: b, foot: f, close: dong };
    var dau = b.querySelector("input:not([type=checkbox]),textarea,select");
    if (dau && o.focus !== false) setTimeout(function () { try { dau.focus(); } catch (e) {} }, 30);
    return m;
  };
  DS.xacNhan = function (cau, nut, nguyHiem) {
    return new Promise(function (ok) {
      var xong = false;
      var m = DS.modal({ title: "Xác nhận", body: '<p style="margin:0">' + esc(cau) + "</p>",
        foot: '<button class="btn" type="button" data-x>Thôi</button><button class="btn ' + (nguyHiem ? "btn-dan" : "btn-pri") + '" type="button" data-ok>' + esc(nut || "Đồng ý") + "</button>",
        onClose: function () { if (!xong) ok(false); } });
      m.foot.querySelector("[data-ok]").onclick = function () { xong = true; m.close(); ok(true); };
    });
  };
  DS.hoi = function (tieuDe, nhan, goiY, giaTri) {
    return new Promise(function (ok) {
      var xong = false;
      var m = DS.modal({ title: tieuDe, body: '<div class="fld"><label>' + esc(nhan) + '</label><textarea class="ta" rows="3" placeholder="' + esc(goiY || "") + '">' + esc(giaTri || "") + "</textarea></div>",
        foot: '<button class="btn" type="button" data-x>Thôi</button><button class="btn btn-pri" type="button" data-ok>Gửi</button>',
        onClose: function () { if (!xong) ok(null); } });
      m.foot.querySelector("[data-ok]").onclick = function () { xong = true; var v = m.body.querySelector("textarea").value; m.close(); ok(v); };
    });
  };

  // ---------------------------------------------------------------- mẩu giao diện
  DS.ph = function (tieuDe, phu, nut) {
    return '<div class="ph"><div><h1>' + esc(tieuDe) + "</h1>" + (phu ? "<p>" + phu + "</p>" : "") + "</div>" + (nut ? '<div class="ph-act">' + nut + "</div>" : "") + "</div>";
  };
  DS.tabs = function (ds, on, base, them) {
    return '<div class="tabs" role="tablist">' + ds.map(function (t) {
      return '<a class="tab' + (t.id === on ? " on" : "") + '" role="tab" href="' + esc(base + t.id) + '">' + esc(t.ten) +
        (t.n != null ? '<span class="cnt">' + DS.so(t.n) + "</span>" : "") + "</a>";
    }).join("") + (them ? '<div class="tabs-end">' + them + "</div>" : "") + "</div>";
  };
  DS.skel = function (dong, the) {
    var h = "";
    if (the) { h += '<div class="grid g4 mb">'; for (var j = 0; j < the; j++) h += '<div class="sk sk-card"></div>'; h += "</div>"; }
    h += '<div class="card">';
    for (var i = 0; i < (dong || 5); i++) h += '<div class="sk sk-line" style="width:' + (92 - (i % 3) * 17) + '%"></div>';
    return h + "</div>";
  };
  DS.skelDong = function (n, cot) {
    var h = "";
    for (var i = 0; i < n; i++) { h += "<tr>"; for (var j = 0; j < cot; j++) h += '<td><div class="sk" style="height:12px;width:' + (40 + ((i + j) % 4) * 15) + '%"></div></td>'; h += "</tr>"; }
    return h;
  };
  var ART = {
    box: '<rect x="30" y="30" width="50" height="38" rx="8" fill="var(--card)" stroke="var(--line)" stroke-width="2"/><path d="M30 44h50" stroke="var(--line)" stroke-width="2"/><rect x="47" y="38" width="16" height="12" rx="3" fill="var(--brand-soft)"/>',
    chat: '<rect x="22" y="22" width="48" height="32" rx="10" fill="var(--card)" stroke="var(--line)" stroke-width="2"/><rect x="44" y="40" width="44" height="28" rx="10" fill="var(--brand-soft)" stroke="var(--brand)" stroke-opacity=".35" stroke-width="2"/><circle cx="58" cy="54" r="2.5" fill="var(--brand)"/><circle cx="66" cy="54" r="2.5" fill="var(--brand)"/><circle cx="74" cy="54" r="2.5" fill="var(--brand)"/>',
    list: '<rect x="26" y="18" width="58" height="52" rx="9" fill="var(--card)" stroke="var(--line)" stroke-width="2"/><rect x="34" y="28" width="10" height="10" rx="3" fill="var(--brand-soft)"/><rect x="48" y="30" width="28" height="6" rx="3" fill="var(--line)"/><rect x="34" y="44" width="10" height="10" rx="3" fill="var(--brand-soft)"/><rect x="48" y="46" width="22" height="6" rx="3" fill="var(--line)"/>',
    done: '<circle cx="55" cy="42" r="24" fill="var(--ok-soft)"/><path d="m45 42 7 7 13-14" fill="none" stroke="var(--ok)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>',
    robot: '<rect x="33" y="26" width="44" height="34" rx="11" fill="var(--brand-soft)" stroke="var(--brand)" stroke-opacity=".4" stroke-width="2"/><circle cx="47" cy="43" r="4" fill="var(--brand)"/><circle cx="63" cy="43" r="4" fill="var(--brand)"/><path d="M55 26v-8" stroke="var(--brand)" stroke-width="2"/><circle cx="55" cy="16" r="3" fill="var(--brand)"/>'
  };
  DS.rong = function (tieuDe, cau, hinh, nut) {
    return '<div class="empty"><svg class="art" viewBox="0 0 110 84" aria-hidden="true"><ellipse cx="55" cy="74" rx="34" ry="5" fill="var(--mu-soft)"/>' +
      (ART[hinh] || ART.list) + "</svg><b>" + esc(tieuDe) + "</b>" + (cau ? "<p>" + cau + "</p>" : "") + (nut || "") + "</div>";
  };
  DS.loiThe = function (msg, thuLai) {
    return '<div class="card">' + DS.rong("Chưa tải được dữ liệu", esc(msg || ""), "box", thuLai ? '<button class="btn" data-act="tai-lai">' + DS.ic("refresh") + "Thử lại</button>" : "") + "</div>";
  };
  DS.phanTrang = function (tong, trang, moi) {
    tong = Number(tong) || 0; trang = Number(trang) || 1; moi = Number(moi) || 50;
    var n = Math.max(1, Math.ceil(tong / moi)), a = tong ? (trang - 1) * moi + 1 : 0, b = Math.min(tong, trang * moi);
    return '<div class="tfoot"><span>' + DS.so(a) + "-" + DS.so(b) + " / " + DS.so(tong) + '</span><div class="pg">' +
      '<button class="btn btn-sm" data-act="trang" data-trang="' + (trang - 1) + '"' + (trang <= 1 ? " disabled" : "") + ">Trước</button>" +
      '<span class="small" style="padding:0 6px">Trang ' + trang + "/" + n + "</span>" +
      '<button class="btn btn-sm" data-act="trang" data-trang="' + (trang + 1) + '"' + (trang >= n ? " disabled" : "") + ">Sau</button></div></div>";
  };
  DS.sw = function (attrs, bat) { return '<label class="sw"><input type="checkbox" ' + (attrs || "") + (bat ? " checked" : "") + "><span></span></label>"; };
  DS.chepChu = function (s) {
    function cu() {
      var t = document.createElement("textarea"); t.value = s; t.style.position = "fixed"; t.style.opacity = "0"; document.body.appendChild(t); t.select();
      var ok = false; try { ok = document.execCommand("copy"); } catch (e) {}
      document.body.removeChild(t); return ok;
    }
    try {
      if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(s).then(function () { return true; }, cu);
    } catch (e) {}
    return Promise.resolve(cu());
  };
  DS.md = function (s) {
    var dong = esc(s || "").split("\n"), h = "", trongDs = false;
    dong.forEach(function (l) {
      l = l.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
      var m = /^\s*[-*•]\s+(.*)$/.exec(l);
      if (m) { if (!trongDs) { h += "<ul>"; trongDs = true; } h += "<li>" + m[1] + "</li>"; return; }
      if (trongDs) { h += "</ul>"; trongDs = false; }
      if (l.trim()) h += "<p>" + l + "</p>";
    });
    if (trongDs) h += "</ul>";
    return h;
  };

  // ---------------------------------------------------------------- uỷ quyền sự kiện cho từng màn
  DS.bind = function (el, acts, loai) {
    el.addEventListener(loai || "click", function (e) {
      var t = e.target.closest("[data-act]");
      if (!t || !el.contains(t)) return;
      var f = acts[t.getAttribute("data-act")];
      if (!f) return;
      if (t.tagName === "A" && (loai || "click") === "click") e.preventDefault();
      try { f(t, e); } catch (x) { console.error(x); DS.toast("Lỗi giao diện: " + x.message, "err"); }
    });
  };

  // ---------------------------------------------------------------- định tuyến hash
  DS.view = function (ten, def) { DS.views[ten] = def; };
  DS.route = function () {
    var h = location.hash.replace(/^#\/?/, ""), i = h.indexOf("?"), p = i < 0 ? h : h.slice(0, i), q = {};
    if (i >= 0) { try { new URLSearchParams(h.slice(i + 1)).forEach(function (v, k) { q[k] = v; }); } catch (e) {} }
    var seg = p.split("/").filter(Boolean);
    return { base: seg[0] || "tong-quan", arg: seg.slice(1).join("/"), q: q };
  };
  DS.go = function (base, q) { location.hash = "#/" + base + DS.qs(q); };
  DS.datQ = function (them, thayHet) {
    var r = DS.route(), q = thayHet ? {} : Object.assign({}, r.q);
    Object.keys(them || {}).forEach(function (k) { if (them[k] === "" || them[k] == null) delete q[k]; else q[k] = them[k]; });
    location.hash = "#/" + r.base + (r.arg ? "/" + r.arg : "") + DS.qs(q);
  };
  var hienTai = null;
  function veMan() {
    var r = DS.route(), v = DS.views[r.base];
    if (!v) { r.base = "tong-quan"; v = DS.views["tong-quan"]; }
    if (hienTai) { hienTai.alive = false; hienTai.timers.forEach(function (x) { clearInterval(x); }); hienTai.timers = []; }
    DS.tip(null);
    var host = document.getElementById("view"), el = document.createElement("div");
    el.className = "view";
    host.innerHTML = "";
    host.appendChild(el);
    var nav = r.base === "chay-hang-loat" ? "automation" : r.base;
    Array.prototype.forEach.call(document.querySelectorAll("[data-nav]"), function (a) { a.classList.toggle("on", a.getAttribute("data-nav") === nav); });
    document.title = (v.title || "Đội Social") + " · Đội Social";
    var tt = document.getElementById("top-title");
    if (tt) tt.textContent = v.title || "Đội Social";
    dongNgan();
    window.scrollTo(0, 0);
    var ctx = hienTai = { el: el, q: r.q, arg: r.arg, alive: true, timers: [] };
    ctx.every = function (fn, ms) { var id = setInterval(function () { if (ctx.alive && !document.hidden) fn(); }, ms); ctx.timers.push(id); return id; };
    try {
      var kq = v.render(el, ctx);
      if (kq && typeof kq.then === "function") kq.then(null, function (e) { console.error(e); if (ctx.alive) el.innerHTML = DS.loiThe(e.message); });
    } catch (e) { console.error(e); el.innerHTML = DS.loiThe(e.message); }
  }
  DS.veLai = veMan;

  // ---------------------------------------------------------------- thanh bên, ngăn kéo, sáng/tối, huy hiệu
  function moNgan() { document.getElementById("side").classList.add("open"); document.getElementById("scrim").hidden = false; }
  function dongNgan() { var s = document.getElementById("side"); if (s) s.classList.remove("open"); var c = document.getElementById("scrim"); if (c) c.hidden = true; }
  function doc(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } }
  function ghi(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  DS.doc = doc; DS.ghi = ghi;
  function apTheme(t) {
    if (t === "dark") document.documentElement.setAttribute("data-theme", "dark");
    else document.documentElement.removeAttribute("data-theme");
    var b = document.getElementById("theme-btn");
    if (b) b.innerHTML = DS.ic(t === "dark" ? "sun" : "moon");
  }
  function huyHieu(id, n) {
    var e = document.getElementById(id);
    if (!e) return;
    n = Number(n) || 0;
    e.hidden = !n;
    e.textContent = n > 99 ? "99+" : String(n);
  }
  DS.capNhatHuyHieu = function () {
    DS.api("GET", "/doi-social/hoi-thoai?tab=can_tay&moi_trang=1", null, { quiet: true }).then(function (d) {
      if (d.ok !== false) huyHieu("n-tin", (d.dem && d.dem.can_tay) != null ? d.dem.can_tay : DS.list(d, "hoi_thoai").length);
    });
    DS.api("GET", "/doi-social/ban-nhap?trang_thai=cho_duyet&moi_trang=1", null, { quiet: true }).then(function (d) {
      if (d.ok !== false) huyHieu("n-duyet", (d.dem && d.dem.cho_duyet) != null ? d.dem.cho_duyet : d.tong);
    });
  };

  DS.khoiDong = function () {
    Array.prototype.forEach.call(document.querySelectorAll("i[data-ic]"), function (i) { i.outerHTML = DS.ic(i.getAttribute("data-ic")); });
    apTheme(doc("doi-social.theme") === "dark" ? "dark" : "light");
    document.getElementById("theme-btn").addEventListener("click", function () {
      var t = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      ghi("doi-social.theme", t); apTheme(t);
    });
    document.getElementById("menu-btn").addEventListener("click", moNgan);
    document.getElementById("scrim").addEventListener("click", dongNgan);
    var thu = {};
    try { thu = JSON.parse(doc("doi-social.nhom-thu") || "{}") || {}; } catch (e) { thu = {}; }
    Array.prototype.forEach.call(document.querySelectorAll("[data-toggle-g]"), function (b) {
      var g = b.getAttribute("data-toggle-g"), box = b.parentNode;
      if (thu[g]) box.classList.add("thu");
      b.setAttribute("aria-expanded", thu[g] ? "false" : "true");
      b.addEventListener("click", function () {
        box.classList.toggle("thu");
        thu[g] = box.classList.contains("thu");
        b.setAttribute("aria-expanded", thu[g] ? "false" : "true");
        ghi("doi-social.nhom-thu", JSON.stringify(thu));
      });
    });
    DS.api("GET", "/version", null, { quiet: true }).then(function (d) {
      var v = d && d.ok !== false && (d.current || d.version);
      if (v) document.getElementById("sf-ver").textContent = "phiên bản " + v;
    });
    window.addEventListener("hashchange", veMan);
    veMan();
    DS.capNhatHuyHieu();
    setInterval(function () { if (!document.hidden) DS.capNhatHuyHieu(); }, 45000);
  };
  document.addEventListener("DOMContentLoaded", function () { if (!DS._daChay) { DS._daChay = true; DS.khoiDong(); } });
})();
