/* mang-ben.js - đọc dữ liệu bền hơn trên mạng chập chờn (26.10.313).
 *
 * MinMin chạy trên VPS, mở từ hai máy tính và một điện thoại, rất hay qua 4G. Hai chuyện file này lo:
 *
 * 1. GOM ĐỌC TRÙNG. Lúc mở app, nhiều phần giao diện cùng hỏi một địa chỉ: đo ngày 30/10, /settings
 *    bị hỏi 7 lần, /auth/status 3 lần, /skills /agents /workflows mỗi cái 2 lần. Một yêu cầu GET y hệt
 *    đang bay thì yêu cầu sau dùng chung kết quả của nó (mỗi bên nhận một bản sao). Trong 20 giây đầu
 *    còn dùng lại kết quả vừa về trong 3 giây. Bất kỳ lệnh GHI nào (POST/PUT/DELETE...) xoá ngay phần
 *    nhớ ngắn đó, nên đọc sau khi lưu luôn là dữ liệu mới.
 *
 * 2. THỬ LẠI KHI MÁY CHỦ ĐANG KHỞI ĐỘNG LẠI. Cập nhật xong, máy chủ mất vài giây mới lên; đọc đúng lúc
 *    đó là lỗi mạng hoặc 502/503/504, giao diện hiện chữ mã (`nav.group...`) hay ô báo lỗi khó hiểu.
 *    Nay việc ĐỌC (GET/HEAD) tự thử lại trong khoảng 10 giây, kèm dòng nhỏ "Đang kết nối lại máy chủ…"
 *    ở đầu trang, nối được là dòng đó tự ẩn. KHÔNG BAO GIỜ thử lại một lệnh ghi: gửi tin, lưu cài đặt
 *    hay tạo đơn mà gửi hai lần là hỏng thật.
 *
 * Không đụng: yêu cầu khác nguồn, yêu cầu có `signal` (bên gọi muốn tự huỷ), luồng stream.
 */
(function () {
  "use strict";
  if (typeof window === "undefined" || typeof window.fetch !== "function" || window.__minminMangBen) return;
  window.__minminMangBen = true;

  var goc = window.fetch.bind(window);
  var CHO_THU_LAI_MS = [400, 800, 1500, 2500, 3500];   // cộng lại ~8,7 giây chờ, ~10 giây cả lượt
  var MA_THU_LAI = { 502: 1, 503: 1, 504: 1 };
  var NHO_NGAN_MS = 3000;
  var KHOI_DONG_MS = 20000;
  var batDau = Date.now();
  var dangBay = {};     // khoá -> Promise<Response>
  var vuaVe = {};       // khoá -> { luc, p }
  var dem = { gop: 0, thu_lai: 0, goi: 0 };

  function urlCua(input) {
    if (typeof input === "string") return input;
    if (input && typeof input.url === "string") return input.url;
    return String(input || "");
  }

  function cungNguon(url) {
    try { return new URL(url, location.href).origin === location.origin; } catch (e) { return false; }
  }

  function phuongThuc(input, init) {
    var m = (init && init.method) || (input && typeof input === "object" && input.method) || "GET";
    return String(m).toUpperCase();
  }

  function khoaTieuDe(init) {
    var h = init && init.headers;
    if (!h) return "";
    try {
      var ds = [];
      if (typeof h.forEach === "function" && !Array.isArray(h)) h.forEach(function (v, k) { ds.push(k + "=" + v); });
      else if (Array.isArray(h)) h.forEach(function (p) { ds.push(p[0] + "=" + p[1]); });
      else Object.keys(h).forEach(function (k) { ds.push(k.toLowerCase() + "=" + h[k]); });
      return ds.sort().join("&");
    } catch (e) { return "?"; }
  }

  function laStream(url, init) {
    if (/\/(stream|events|sse)(\b|\/|\?|$)/.test(url)) return true;
    var h = khoaTieuDe(init);
    return h.indexOf("text/event-stream") >= 0;
  }

  // ── Dòng báo kết nối lại ─────────────────────────────────────────────────────
  var soDangCho = 0;
  function chu() {
    try {
      var s = window.t && window.t("net.reconnecting");
      if (s && s !== "net.reconnecting") return s;
    } catch (e) { /* noop */ }
    return "Đang kết nối lại máy chủ…";
  }
  function hienDai() {
    soDangCho++;
    if (!document.body || document.getElementById("minmin-net-bar")) return;
    var bar = document.createElement("div");
    bar.id = "minmin-net-bar";
    bar.setAttribute("role", "status");
    bar.textContent = chu();
    bar.style.cssText = "position:fixed;top:max(8px,env(safe-area-inset-top));left:50%;transform:translateX(-50%);" +
      "z-index:99998;padding:6px 14px;border-radius:var(--mm-r-pill,999px);" +
      "font:500 var(--mm-fs-14,14px)/1.4 var(--mm-font,system-ui,sans-serif);" +
      "background:var(--mm-panel,#1f2430);color:var(--mm-text,#e8eaf0);" +
      "border:1px solid var(--mm-line,#39405180);box-shadow:var(--mm-out-sm,0 6px 20px rgba(0,0,0,.3));pointer-events:none";
    document.body.appendChild(bar);
  }
  function anDai() {
    soDangCho = Math.max(0, soDangCho - 1);
    if (soDangCho) return;
    var bar = document.getElementById("minmin-net-bar");
    if (bar) bar.remove();
  }

  /* 502/503/504 do PROXY trả (máy chủ MinMin chưa lên) thì thử lại. Lỗi do CHÍNH MinMin trả có thân
   * JSON giải thích (vd "Zalo Forwarder phản hồi quá lâu"): đó là câu trả lời thật, đưa ngay cho giao diện. */
  function laDangKhoiDong(r) {
    if (!MA_THU_LAI[r.status]) return false;
    var kieu = "";
    try { kieu = (r.headers && r.headers.get("content-type")) || ""; } catch (e) { /* noop */ }
    return kieu.indexOf("json") < 0;
  }

  function ngu(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  /* Đọc có thử lại. Trả Response cuối cùng (kể cả 5xx) hoặc ném lỗi mạng cuối cùng, y như fetch gốc. */
  function docBen(input, init) {
    var lan = 0, dangBao = false;
    function xong(kq) { if (dangBao) anDai(); return kq; }
    function thu() {
      return goc(input, init).then(function (r) {
        if (laDangKhoiDong(r) && lan < CHO_THU_LAI_MS.length) return lai();
        return xong(r);
      }, function (e) {
        if (e && e.name === "AbortError") { if (dangBao) anDai(); throw e; }
        if (lan < CHO_THU_LAI_MS.length && !(navigator && navigator.onLine === false && lan >= 2)) return lai(e);
        if (dangBao) anDai();
        throw e;
      });
    }
    function lai() {
      if (!dangBao) { dangBao = true; hienDai(); }
      dem.thu_lai++;
      var cho = CHO_THU_LAI_MS[lan++];
      return ngu(cho).then(thu);
    }
    return thu();
  }

  window.fetch = function (input, init) {
    var url = urlCua(input);
    var m = phuongThuc(input, init);
    if (m !== "GET" && m !== "HEAD") {
      vuaVe = {};                 // vừa ghi gì đó: không phát lại kết quả đọc cũ
      return goc(input, init);
    }
    if (typeof input !== "string" || !cungNguon(url) || (init && init.signal) || laStream(url, init)) {
      return goc(input, init);
    }
    dem.goi++;
    var khongNho = init && (init.cache === "no-store" || init.cache === "reload");
    var khoa = m + " " + url + " " + ((init && init.cache) || "") + " " + khoaTieuDe(init);
    if (dangBay[khoa]) {
      dem.gop++;
      return dangBay[khoa].then(function (r) { return r.clone(); });
    }
    var bayGio = Date.now();
    var nho = vuaVe[khoa];
    if (!khongNho && nho && bayGio - nho.luc < NHO_NGAN_MS && bayGio - batDau < KHOI_DONG_MS) {
      dem.gop++;
      return nho.p.then(function (r) { return r.clone(); });
    }
    var p = docBen(input, init);
    dangBay[khoa] = p;
    p.then(function (r) {
      delete dangBay[khoa];
      if (!khongNho && r.ok && Date.now() - batDau < KHOI_DONG_MS) vuaVe[khoa] = { luc: Date.now(), p: p };
    }, function () { delete dangBay[khoa]; });
    return p.then(function (r) { return r.clone(); });
  };

  /* Đăng ký service worker ở MỌI lần mở (không chỉ khi bật thông báo đẩy) để trang chờ "Đang kết nối
   * lại máy chủ…" có mặt cả khi bố tải lại trang đúng lúc máy chủ đang khởi động lại. Cùng /sw.js và
   * scope với push.js nên vẫn là một đăng ký. Chỉ có ở https/localhost (luật trình duyệt). */
  function dangKyTrangCho() {
    try {
      if (!("serviceWorker" in navigator) || !window.isSecureContext) return;
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () { /* noop */ });
    } catch (e) { /* noop */ }
  }
  if (document.readyState === "complete") setTimeout(dangKyTrangCho, 3000);
  else window.addEventListener && window.addEventListener("load", function () { setTimeout(dangKyTrangCho, 3000); });

  window.MinMinMang = { dem: dem, docBen: docBen };
})();
