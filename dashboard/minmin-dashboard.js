// ============================================================================
// MinMin OS - Bảng điều hành ở cột trái màn chính (thay chỗ panel VAULT).
//
// Hai tab: "Điều hành" (mặc định) và "Vault" (cây thư mục cũ, giữ nguyên chức năng).
// Nguồn số liệu - KHÔNG bịa, thiếu thì nói thiếu:
//   1. Số kinh doanh + dự án: file JSON trong brain `00 - Dashboard/minmin-dashboard.json`
//      (MinMin/loop tự ghi từ POS, Ads... - mẫu ở minmin-dashboard.example.json).
//   2. Việc nền đang chạy: GET /kanban và GET /loops của chính MinMin (số sống).
// Dự báo cuối tháng tính ngay trên trình duyệt từ chuỗi doanh thu ngày, trừ khi file
// JSON đã ghi sẵn khối "forecast".
// ============================================================================
(function () {
  "use strict";
  if (typeof window === "undefined") return;

  var DATA_PATH = "00 - Dashboard/minmin-dashboard.json";
  var KEY_TAB = "mm.leftTab";
  var C = { actual: "#3987e5", good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" };

  function brain() { try { return (window.currentBrainPath && window.currentBrainPath()) || "brain"; } catch (e) { return "brain"; } }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function $(id) { return document.getElementById(id); }

  // 12500000 -> "12,5 tr" ; 1250000000 -> "1,25 tỷ"
  function tien(v, unit) {
    if (v == null || isNaN(v)) return "-";
    var a = Math.abs(v), s;
    if (a >= 1e9) s = (v / 1e9).toLocaleString("vi-VN", { maximumFractionDigits: 2 }) + " tỷ";
    else if (a >= 1e6) s = (v / 1e6).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + " tr";
    else if (a >= 1e3) s = (v / 1e3).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + "k";
    else s = Number(v).toLocaleString("vi-VN");
    return unit === "đ" || unit == null ? s : (s + (unit ? " " + unit : ""));
  }
  function so(v, unit) {
    if (v == null || isNaN(v)) return "-";
    if (unit === "đ" || unit === "VND") return tien(v);
    if (unit === "%") return Number(v).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + "%";
    if (unit === "x") return Number(v).toLocaleString("vi-VN", { maximumFractionDigits: 2 }) + "x";
    return Number(v).toLocaleString("vi-VN") + (unit ? " " + unit : "");
  }
  function tuongDoi(ts) {
    if (!ts) return "";
    var t = typeof ts === "number" ? (ts < 1e12 ? ts * 1000 : ts) : Date.parse(ts);
    if (isNaN(t)) return String(ts);
    var p = Math.round((Date.now() - t) / 60000);
    if (p < 1) return "vừa xong";
    if (p < 60) return p + " phút trước";
    if (p < 1440) return Math.round(p / 60) + " giờ trước";
    return Math.round(p / 1440) + " ngày trước";
  }

  // ---------- Dự báo cuối tháng ----------
  // Doanh thu đã có từ đầu tháng + (trung bình 7 ngày gần nhất × số ngày còn lại).
  // Biên dao động = độ lệch chuẩn 14 ngày × căn(số ngày còn lại) - đủ để thấy độ bất định,
  // không giả vờ chính xác.
  function duBao(series, override) {
    if (override && override.month_end != null) return override;
    if (!series || series.length < 3) return null;
    var last = new Date(series[series.length - 1].date + "T00:00:00");
    if (isNaN(last)) return null;
    var y = last.getFullYear(), m = last.getMonth();
    var soNgay = new Date(y, m + 1, 0).getDate();
    var trongThang = series.filter(function (d) { var x = new Date(d.date + "T00:00:00"); return x.getFullYear() === y && x.getMonth() === m; });
    var mtd = trongThang.reduce(function (s, d) { return s + (+d.value || 0); }, 0);
    var v7 = series.slice(-7).map(function (d) { return +d.value || 0; });
    var tb = v7.reduce(function (a, b) { return a + b; }, 0) / v7.length;
    var v14 = series.slice(-14).map(function (d) { return +d.value || 0; });
    var tb14 = v14.reduce(function (a, b) { return a + b; }, 0) / v14.length;
    var sd = Math.sqrt(v14.reduce(function (a, b) { return a + (b - tb14) * (b - tb14); }, 0) / Math.max(1, v14.length - 1));
    var con = soNgay - last.getDate();
    var band = sd * Math.sqrt(Math.max(0, con));
    return { month_end: mtd + tb * con, low: Math.max(mtd, mtd + tb * con - band), high: mtd + tb * con + band,
      mtd: mtd, per_day: tb, days_left: con, days_in_month: soNgay, y: y, m: m, note: "Ước tính theo nhịp 7 ngày gần nhất" };
  }

  // ---------- Biểu đồ doanh thu tháng + nhánh dự báo (SVG, có tooltip) ----------
  function veBieuDo(el, series, fc) {
    if (!series || !series.length) { el.innerHTML = '<div class="mm-empty">Chưa có chuỗi doanh thu theo ngày.</div>'; return; }
    var W = 228, H = 96, pl = 2, pr = 2, pt = 8, pb = 16;
    var diem = series.slice(-31).map(function (d) { return { date: d.date, v: +d.value || 0, du: false }; });
    var chieu = diem.slice();
    if (fc && fc.days_left > 0 && fc.per_day != null) {
      var l = new Date(diem[diem.length - 1].date + "T00:00:00");
      for (var i = 1; i <= fc.days_left; i++) {
        var d = new Date(l); d.setDate(l.getDate() + i);
        chieu.push({ date: d.toISOString().slice(0, 10), v: fc.per_day, du: true });
      }
    }
    var max = Math.max.apply(null, chieu.map(function (p) { return p.v; })) || 1;
    var n = chieu.length, bx = (W - pl - pr) / Math.max(1, n - 1);
    function X(i) { return pl + i * bx; }
    function Y(v) { return pt + (H - pt - pb) * (1 - v / max); }
    var thucte = diem.map(function (p, i) { return X(i).toFixed(1) + "," + Y(p.v).toFixed(1); });
    var vung = "M" + X(0) + "," + (H - pb) + " L" + thucte.join(" L") + " L" + X(diem.length - 1) + "," + (H - pb) + " Z";
    var duong = "M" + thucte.join(" L");
    var du = "";
    if (chieu.length > diem.length) {
      du = "M" + X(diem.length - 1) + "," + Y(diem[diem.length - 1].v);
      for (var j = diem.length; j < n; j++) du += " L" + X(j).toFixed(1) + "," + Y(chieu[j].v).toFixed(1);
    }
    var nhanDau = diem[0].date.slice(8, 10) + "/" + diem[0].date.slice(5, 7);
    var nhanCuoi = chieu[n - 1].date.slice(8, 10) + "/" + chieu[n - 1].date.slice(5, 7);
    el.innerHTML =
      '<svg class="mm-chart" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Doanh thu theo ngày và dự báo đến cuối tháng">' +
      '<defs><linearGradient id="mmArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + C.actual + '" stop-opacity=".35"/><stop offset="1" stop-color="' + C.actual + '" stop-opacity="0"/></linearGradient></defs>' +
      '<line x1="0" x2="' + W + '" y1="' + (H - pb) + '" y2="' + (H - pb) + '" class="mm-axis"/>' +
      '<path d="' + vung + '" fill="url(#mmArea)"/>' +
      '<path d="' + duong + '" fill="none" stroke="' + C.actual + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>' +
      (du ? '<path d="' + du + '" fill="none" stroke="' + C.actual + '" stroke-width="2" stroke-dasharray="3 3" opacity=".7"/>' : "") +
      '<text x="0" y="' + (H - 3) + '" class="mm-tick">' + nhanDau + '</text>' +
      '<text x="' + W + '" y="' + (H - 3) + '" class="mm-tick" text-anchor="end">' + nhanCuoi + '</text>' +
      '<line class="mm-cross" x1="0" x2="0" y1="' + pt + '" y2="' + (H - pb) + '" style="display:none"/>' +
      '<circle class="mm-dot" r="4" style="display:none" fill="' + C.actual + '"/>' +
      '<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="transparent" class="mm-hit"/>' +
      '</svg><div class="mm-tip" hidden></div>' +
      '<div class="mm-legend"><span><i class="mm-sw" style="background:' + C.actual + '"></i>Thực tế</span>' +
      (du ? '<span><i class="mm-sw mm-sw-dash" style="border-color:' + C.actual + '"></i>Dự báo</span>' : "") + '</div>';
    var svg = el.querySelector("svg"), tip = el.querySelector(".mm-tip"), cr = el.querySelector(".mm-cross"), dot = el.querySelector(".mm-dot");
    function an() { tip.hidden = true; cr.style.display = "none"; dot.style.display = "none"; }
    el.querySelector(".mm-hit").addEventListener("pointermove", function (e) {
      var r = svg.getBoundingClientRect();
      var i = Math.round(((e.clientX - r.left) / r.width * W - pl) / bx);
      i = Math.max(0, Math.min(n - 1, i));
      var p = chieu[i];
      cr.setAttribute("x1", X(i)); cr.setAttribute("x2", X(i)); cr.style.display = "";
      dot.setAttribute("cx", X(i)); dot.setAttribute("cy", Y(p.v)); dot.style.display = "";
      dot.setAttribute("fill-opacity", p.du ? 0.5 : 1);
      tip.hidden = false;
      tip.innerHTML = "<b>" + p.date.slice(8, 10) + "/" + p.date.slice(5, 7) + "</b> · " + tien(p.v) + (p.du ? " <em>(dự báo)</em>" : "");
      var left = (X(i) / W) * r.width;
      tip.style.left = Math.max(0, Math.min(r.width - 120, left - 60)) + "px";
    });
    el.querySelector(".mm-hit").addEventListener("pointerleave", an);
  }

  // Icon Lucide của repo (không dùng emoji: test_icons chặn). Thiếu window.ic thì để trống.
  function icon(ten) { return window.ic ? window.ic(ten) : ""; }
  var ICON = { good: "circle-check", warning: "triangle-alert", serious: "triangle-alert", critical: "circle-x", info: "info" };
  var TRANG_THAI = {
    running: ["Đang chạy", "good"], done: ["Xong", "good"], blocked: ["Kẹt", "critical"],
    review: ["Chờ duyệt", "warning"], planned: ["Kế hoạch", "info"], paused: ["Tạm dừng", "serious"],
  };

  function khoiKpi(k) {
    var d = k.delta_pct;
    var cls = d == null ? "" : (d >= 0 ? (k.lower_is_better ? "down" : "up") : (k.lower_is_better ? "up" : "down"));
    return '<div class="mm-kpi"><div class="mm-kpi-l">' + esc(k.label) + '</div>' +
      '<div class="mm-kpi-v">' + esc(so(k.value, k.unit)) + '</div>' +
      (d == null ? "" : '<div class="mm-kpi-d ' + cls + '">' + icon(d >= 0 ? "trending-up" : "trending-down") + " " + Math.abs(d).toLocaleString("vi-VN", { maximumFractionDigits: 1 }) + "% " + '<span>' + esc(k.compare || "") + '</span></div>') +
      '</div>';
  }

  function veKinhDoanh(d) {
    var box = $("mmBiz");
    if (!box) return;
    if (!d) {
      box.innerHTML = '<div class="mm-empty"><b>Chưa có số liệu kinh doanh.</b><br>MinMin đọc từ file <code>' + esc(DATA_PATH) +
        '</code> trong brain. Nhắn MinMin: <em>"lập file số liệu dashboard từ POS và Ads, cập nhật mỗi giờ"</em>.</div>';
      return;
    }
    var fc = duBao(d.revenue_daily, d.forecast);
    var h = "";
    if (d.demo) h += '<div class="mm-demo">DỮ LIỆU MẪU - chưa phải số thật</div>';
    h += '<div class="mm-kpis">' + (d.kpis || []).slice(0, 4).map(khoiKpi).join("") + '</div>';
    h += '<div class="mm-sec-t">Doanh thu ' + esc(d.period_label || "tháng này") + '</div><div id="mmChart" class="mm-chart-box"></div>';
    if (fc) {
      var tt = d.target_month ? Math.round(fc.month_end / d.target_month * 100) : null;
      var mucTT = tt == null ? "" : (tt >= 100 ? "good" : tt >= 85 ? "warning" : "critical");
      h += '<div class="mm-fc"><div class="mm-fc-l">Dự báo cuối tháng</div>' +
        '<div class="mm-fc-v">' + tien(fc.month_end) + '</div>' +
        '<div class="mm-fc-s">khoảng ' + tien(fc.low) + ' - ' + tien(fc.high) + '</div>' +
        (tt == null ? "" : '<div class="mm-bar"><i style="width:' + Math.min(100, tt) + '%;background:' + C[mucTT] + '"></i></div>' +
          '<div class="mm-fc-s"><span class="mm-st mm-st-' + mucTT + '">' + icon(ICON[mucTT]) + '</span> ' + tt + '% mục tiêu ' + tien(d.target_month) + '</div>') +
        '<div class="mm-fc-n">' + esc(fc.note || "") + '</div></div>';
    }
    if ((d.alerts || []).length) {
      h += '<div class="mm-sec-t">Cần chú ý</div><ul class="mm-alerts">' + d.alerts.slice(0, 5).map(function (a) {
        var lv = ICON[a.level] ? a.level : "info";
        return '<li><span class="mm-st mm-st-' + lv + '">' + icon(ICON[lv]) + '</span><span>' + esc(a.text) + '</span></li>';
      }).join("") + '</ul>';
    }
    box.innerHTML = h;
    veBieuDo($("mmChart"), d.revenue_daily, fc);
  }

  function veDuAn(d) {
    var box = $("mmProj");
    if (!box) return;
    var ds = (d && d.projects) || [];
    if (!ds.length) { box.innerHTML = '<div class="mm-empty">Chưa khai báo dự án trong file số liệu.</div>'; return; }
    box.innerHTML = ds.slice(0, 6).map(function (p) {
      var st = TRANG_THAI[p.status] || [p.status || "-", "info"];
      var pc = Math.max(0, Math.min(100, +p.progress || 0));
      return '<div class="mm-proj"><div class="mm-proj-h"><span class="mm-proj-n">' + esc(p.name) + '</span>' +
        "<span class=\"mm-pill mm-pill-" + st[1] + "\">" + icon(p.status === "running" ? "play" : ICON[st[1]]) + " " + esc(st[0]) + '</span></div>' +
        '<div class="mm-bar"><i style="width:' + pc + '%"></i></div>' +
        '<div class="mm-proj-m"><span>' + pc + '%</span>' + (p.due ? '<span>hạn ' + esc(p.due) + '</span>' : "") + '</div>' +
        (p.next ? '<div class="mm-proj-x">→ ' + esc(p.next) + '</div>' : "") + '</div>';
    }).join("");
  }

  function veVan(kb, lp) {
    var box = $("mmOps");
    if (!box) return;
    if (!kb && !lp) { box.innerHTML = '<div class="mm-empty">Chưa đọc được trạng thái việc nền.</div>'; return; }
    var c = (kb && kb.counts) || {};
    var hang = (c.triage || 0) + (c.todo || 0) + (c.ready || 0);
    var loops = (lp && lp.loops) || [];
    var bat = loops.filter(function (l) { return l.enabled; }).length;
    var loi = loops.filter(function (l) { return l.fail_streak > 0 || l.auto_paused_reason; }).length;
    var h = '<div class="mm-ops">' +
      '<div><b>' + (c.running || 0) + '</b><span>đang chạy</span></div>' +
      '<div><b>' + hang + '</b><span>chờ</span></div>' +
      '<div><b>' + ((c.review || 0) + (c.blocked || 0)) + '</b><span>cần xem</span></div>' +
      '<div><b>' + ((kb && kb.completed_24h) || 0) + '</b><span>xong 24h</span></div></div>';
    if (kb && kb.orchestration === "off") h += '<div class="mm-note"><span class="mm-st mm-st-warning">!</span> Điều phối đang TẮT - việc chỉ xếp hàng, bật "AI tự vận hành" ở trang Việc.</div>';
    var chay = ((kb && kb.operations && kb.operations.active) || []).concat((kb && kb.operations && kb.operations.attention) || []).slice(0, 4);
    if (chay.length) h += '<ul class="mm-tasks">' + chay.map(function (t) {
      var st = TRANG_THAI[t.status] || [t.status, "info"];
      return '<li><span class="mm-st mm-st-' + st[1] + '">' + icon(t.status === "running" ? "play" : ICON[st[1]]) + '</span><span class="mm-t">' + esc(t.title || t.intent || t.id) + '</span></li>';
    }).join("") + '</ul>';
    h += '<div class="mm-loops">Loop: <b>' + bat + '</b>/' + loops.length + ' bật' + (loi ? ' · <span class="mm-bad">' + loi + ' lỗi/tạm dừng</span>' : "") + '</div>';
    box.innerHTML = h;
  }

  // ---------- Nạp dữ liệu ----------
  var _dang = false;
  async function napJson(url) {
    var r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }
  async function napTatCa() {
    if (_dang || document.hidden) return;
    var panel = document.querySelector(".hud-body > .hud-left.mm-dash-on");
    if (!panel) return;
    _dang = true;
    var b = encodeURIComponent(brain());
    var d = null, kb = null, lp = null;
    try {
      var f = await napJson("/files/read?brain=" + b + "&path=" + encodeURIComponent(DATA_PATH));
      d = JSON.parse(f.content);
    } catch (e) { d = null; }
    try { kb = await napJson("/kanban?brain=" + b); } catch (e) {}
    try { lp = await napJson("/loops?brain=" + b); } catch (e) {}
    veKinhDoanh(d); veDuAn(d); veVan(kb, lp);
    var up = $("mmUpd");
    if (up) up.textContent = d && d.updated_at ? ("Số liệu " + tuongDoi(d.updated_at) + (d.source ? " · " + d.source : "")) : "Chưa có file số liệu";
    _dang = false;
  }

  // ---------- Dựng khung panel ----------
  function dung() {
    var left = document.querySelector(".hud-body > .hud-left");
    if (!left || left.querySelector(".mm-tabs")) return;
    var tabs = document.createElement("div");
    tabs.className = "mm-tabs";
    tabs.innerHTML = '<button data-t="dash">Điều hành</button><button data-t="vault">Vault</button>';
    var dash = document.createElement("div");
    dash.className = "mm-dash";
    dash.innerHTML =
      '<div class="mm-head"><span class="mm-title">BẢNG ĐIỀU HÀNH</span><button class="mini-btn" id="mmRefresh" title="Làm mới số liệu">⟳</button></div>' +
      '<div class="mm-upd" id="mmUpd">Đang tải…</div>' +
      '<section><div id="mmBiz"></div></section>' +
      '<section><div class="mm-sec-t">Dự án MinMin đang làm</div><div id="mmProj"></div></section>' +
      '<section><div class="mm-sec-t">Việc nền (sống)</div><div id="mmOps"></div></section>' +
      '<div class="mm-foot"><button class="mm-link" id="mmOpenData">Mở file số liệu</button>' +
      '<button class="mm-link" id="mmGalaxyToggle"></button></div>';
    left.insertBefore(dash, left.firstChild);
    left.insertBefore(tabs, left.firstChild);

    function chon(t) {
      left.classList.toggle("mm-dash-on", t === "dash");
      tabs.querySelectorAll("button").forEach(function (b) { b.classList.toggle("active", b.getAttribute("data-t") === t); });
      try { localStorage.setItem(KEY_TAB, t); } catch (e) {}
      if (t === "dash") napTatCa();
    }
    tabs.addEventListener("click", function (e) { var b = e.target.closest("button"); if (b) chon(b.getAttribute("data-t")); });
    $("mmRefresh").addEventListener("click", function () { napTatCa(); });
    $("mmOpenData").addEventListener("click", function () {
      if (window.JavisOpenVaultPath) { try { window.JavisOpenVaultPath(DATA_PATH); return; } catch (e) {} }
      window.open("/files/raw?brain=" + encodeURIComponent(brain()) + "&path=" + encodeURIComponent(DATA_PATH), "_blank");
    });
    var gt = $("mmGalaxyToggle");
    // 0.64.90: một bản đồ thị 3D duy nhất, ẩn nút chuyển; phần dưới giữ để không vỡ khi thiếu nút
    if (gt) { gt.hidden = true; gt.style.display = "none"; }
    // Vòng chế độ đồ thị: 3D -> 2D -> đồ thị gốc -> 3D (cùng khoá với minmin-galaxy.js).
    // Đổi tại chỗ qua MinMinGalaxy.dat, không tải lại trang.
    var CD = ["3d", "2d", "off"], TEN_CD = { "3d": "Xem 3D", "2d": "Xem 2D", off: "Đồ thị gốc" };
    function cdHien() {
      var v = "3d"; try { v = localStorage.getItem("mm.galaxy") || "3d"; } catch (e) {}
      return CD.indexOf(v) < 0 ? "3d" : v;
    }
    function cdSau() { return CD[(CD.indexOf(cdHien()) + 1) % CD.length]; }
    function veNut() { gt.textContent = "Chuyển: " + TEN_CD[cdSau()]; }
    veNut();
    window.addEventListener("mm-galaxy-mode", veNut);
    gt.addEventListener("click", function () {
      if (window.MinMinGalaxy && window.MinMinGalaxy.dat) { window.MinMinGalaxy.dat(cdSau()); return; }
      try { localStorage.setItem("mm.galaxy", cdSau()); } catch (e) {}
      location.reload();                                             // chỉ khi thiếu minmin-galaxy.js
    });
    var t0 = "dash"; try { t0 = localStorage.getItem(KEY_TAB) || "dash"; } catch (e) {}
    chon(t0);
    setInterval(napTatCa, 60000);
    document.addEventListener("visibilitychange", function () { if (!document.hidden) napTatCa(); });
    // Đổi brain ở navbar -> nạp lại số của brain mới.
    var sel = $("graphSource");
    if (sel) sel.addEventListener("change", function () { setTimeout(napTatCa, 400); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", dung);
  else dung();

  window.MinMinDashboard = { reload: napTatCa, forecast: duBao, DATA_PATH: DATA_PATH };
})();
