// chat-goal.js - lệnh /goal và THANH MỤC TIÊU ngay trên ô gõ (26.10.310).
//
// Bố gõ "/goal <điều kiện>": MinMin làm, tự kiểm, chưa đạt thì tự nhắc mình làm tiếp vòng sau, tối đa
// TOI_DA vòng. Mỗi hội thoại giữ một mục tiêu, nhiều hội thoại thì nhiều mục tiêu cùng lúc. Thanh trên ô gõ
// hiện mục tiêu đang theo đuổi, đồng hồ, nút xoá, tạm dừng/chạy tiếp, xem chi tiết; có từ hai mục tiêu thì
// thêm ô số ở đầu, bấm xổ danh sách.
//
// MODEL đề xuất, MÃ quyết định: cuối mỗi câu trả lời model ghi một dòng ẩn <!-- MINMIN_GOAL: {...} -->,
// file này đọc dòng đó rồi quyết định có chạy vòng tiếp không (trần vòng, hai vòng liền không tiến triển
// thì dừng, model hỏi ngược thì dừng). Không có trần thì một mục tiêu không bao giờ đạt là vòng lặp đốt token.
//
// Mục tiêu KHÔNG mất khi: bấm Dừng (tạm dừng), bố gõ chen một câu (tạm dừng), rời sang chat khác (chờ, mở
// lại là chạy tiếp), tải lại trang (tạm dừng, bấm chạy tiếp là đi vòng sau).
//
// Chia đôi như chat-slash.js: phần THUẦN chạy được dưới node (tests/js/test_chat_goal.js), phần DOM ở cuối.
(function () {
  "use strict";

  var KHO_KEY = "minmin.goals.v1";
  var TOI_DA = 5;          // số vòng tối đa của một mục tiêu
  var TOI_DA_KHO = 8;      // giữ tối đa 8 mục tiêu, cái cũ nhất rơi ra
  var MARK = "[MỤC TIÊU:";
  var GOAL_RE = /<!--\s*MINMIN_GOAL:\s*([\s\S]*?)\s*-->/g;

  // Tên hàm là tw vì test i18n quét mặt chữ tw(...) để kiểm khoá có thật trong vi.json.
  function tw(khoa, bien) {
    if (typeof window !== "undefined" && window.t) return window.t(khoa, bien);
    try {
      var v = require("./i18n/vi.json")[khoa];
      if (v == null) return khoa;
      return String(v).replace(/\{(\w+)\}/g, function (m, ten) {
        return (bien && bien[ten] != null) ? String(bien[ten]) : m;
      });
    } catch (e) { return khoa; }
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // ===================== HÀM THUẦN =====================

  // Điều kiện -> MỘT dòng an toàn trong khối ngoặc vuông. Ngoặc vuông đổi sang ngoặc tròn: bong bóng cắt
  // khối ở "]" + hai dấu xuống dòng, một điều kiện chứa "]" sẽ làm lộ nửa khối chỉ dẫn.
  function donDong(s, toiDa) {
    return String(s || "").replace(/\s+/g, " ").trim().replace(/\[/g, "(").replace(/\]/g, ")")
      .replace(/-->/g, "- ->").slice(0, toiDa || 400);
  }

  // Khối chỉ dẫn đi TRƯỚC câu của vòng. app.js (chuNguoiGo) và server bóc nó khỏi bong bóng và tên hội thoại.
  function khoiMucTieu(dk, vong, toiDa, left) {
    vong = +vong || 1; toiDa = +toiDa || TOI_DA;
    return MARK + " " + donDong(dk) + "\n" +
      "Chế độ làm tới khi đạt, vòng " + vong + "/" + toiDa + ". Làm tiếp phần còn thiếu bằng công cụ sẵn có, " +
      "rồi tự kiểm bằng dữ liệu thật xem điều kiện trên đã đúng chưa.\n" +
      (vong >= 2 && left ? "Vòng trước còn: " + donDong(left, 300) + "\n" : "") +
      "Cuối câu trả lời LUÔN thêm đúng MỘT dòng ẩn: " +
      '<!-- MINMIN_GOAL: {"done":true} --> nếu đã đạt và đã kiểm chứng, hoặc ' +
      '<!-- MINMIN_GOAL: {"done":false,"left":"phần còn thiếu, một câu ngắn"} --> nếu chưa, hoặc ' +
      '<!-- MINMIN_GOAL: {"done":false,"blocked":"lý do, một câu ngắn"} --> nếu không thể làm tiếp vì thiếu ' +
      "quyền, công cụ, kết nối hay dữ liệu mà chỉ người dùng gỡ được. Không báo đạt khi chưa kiểm chứng. " +
      "Cần người dùng quyết định thì hỏi rõ rồi dừng.]\n\n";
  }

  // Dòng ẩn CUỐI CÙNG thắng; dòng hỏng (JSON sai, thiếu done kiểu boolean) coi như không có.
  function docDanhDau(text) {
    var s = String(text == null ? "" : text), kq = null, m;
    GOAL_RE.lastIndex = 0;
    while ((m = GOAL_RE.exec(s)) !== null) {
      kq = null;
      try {
        var o = JSON.parse(m[1]);
        if (o && typeof o.done === "boolean") {
          kq = { done: o.done, left: String(o.left || "").trim().slice(0, 300) };
          var bl = String(o.blocked || "").trim().slice(0, 300);
          if (bl && !o.done) kq.blocked = bl;
        }
      } catch (e) { /* hỏng: bỏ */ }
    }
    return kq;
  }

  function chuan(s) { return String(s || "").toLowerCase().replace(/\s+/g, " ").trim(); }

  // Sau một vòng: chạy tiếp hay dừng, dừng vì sao. Lỗi và câu hỏi ngược đứng trước: lúc đó bố cần lên tiếng.
  function quyetDinh(g, ket) {
    ket = ket || {};
    if (ket.loi) return { act: "dung", ly: "loi" };
    if (ket.hoiLai) return { act: "dung", ly: "hoi_lai" };
    var m = ket.marker;
    if (!m) return { act: "dung", ly: "khong_bao" };
    if (m.done) return { act: "dung", ly: "dat" };
    if (m.blocked) return { act: "dung", ly: "ket", why: m.blocked };
    if (g.vong >= g.toiDa) return { act: "dung", ly: "het_vong" };
    if (g.left && m.left && chuan(g.left) === chuan(m.left)) return { act: "dung", ly: "dung_im", left: m.left };
    return { act: "tiep", left: m.left || "" };
  }

  var _dem = 0;
  function taoMucTieu(o, now) {
    o = o || {}; now = +now || Date.now(); _dem += 1;
    return {
      id: "g" + now.toString(36) + _dem, sid: o.sid || null, brain: o.brain || "", dk: String(o.dk || ""),
      vong: 1, toiDa: +o.toiDa || TOI_DA, left: "", state: "running", batDau: now, daChay: 0, chayTu: now,
      // Trạng thái vòng, không lưu xuống kho:
      ket: null,          // kết quả vòng vừa về {marker, hoiLai} | {loi}
      xongLuot: false,    // vòng vừa đóng, chưa quyết định vòng tiếp
      tiepNgay: false,    // vòng sau đi luôn khi được phép (sau tạm dừng, gõ chen, tải lại trang)
      catNgang: false,    // lượt đang chạy bị bấm Dừng: bỏ kết quả dở dang
    };
  }

  function thoiGian(g, now) {
    if (!g) return 0;
    var ms = +g.daChay || 0;
    if (g.state === "running" && g.chayTu) ms += Math.max(0, (+now || Date.now()) - g.chayTu);
    return ms;
  }
  function dinhDangGio(ms) {
    var s = Math.max(0, Math.floor((+ms || 0) / 1000));
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
    if (h) return h + "h " + m + "m " + x + "s";
    return m ? m + "m " + x + "s" : x + "s";
  }
  function tamDung(g, now) {
    if (!g || g.state !== "running") return false;
    g.daChay = thoiGian(g, now); g.chayTu = 0; g.state = "paused";
    return true;
  }
  function chayLai(g, now) {
    if (!g || g.state !== "paused") return false;
    g.state = "running"; g.chayTu = +now || Date.now();
    return true;
  }
  // Để HIỆN: mục tiêu đang chạy mà chat của nó không mở thì nó đang chờ.
  function trangThai(g, sid) {
    if (!g) return "";
    if (g.state === "paused") return "paused";
    return (g.sid && g.sid !== sid) ? "waiting" : "running";
  }
  // Mục tiêu đứng trên thanh: của chat đang mở, không có thì cái mới đặt nhất.
  function chonChinh(ds, sid) {
    ds = ds || [];
    return ds.filter(function (g) { return g.sid === (sid || null); })[0] ||
      ds.slice().sort(function (a, b) { return b.batDau - a.batDau; })[0] || null;
  }

  // Kho -> danh sách. Tải lại trang thì mọi mục tiêu thành TẠM DỪNG, bấm chạy tiếp là đi vòng sau: kết quả
  // vòng cuối đã mất cùng trang, quyết định lại trên đó là đoán.
  function tuKho(raw) {
    var ds;
    try { ds = JSON.parse(raw || "[]"); } catch (e) { return []; }
    if (!Array.isArray(ds)) return [];
    var out = [];
    ds.forEach(function (o) {
      if (!o || typeof o !== "object" || !o.id || !o.sid || !String(o.dk || "").trim()) return;
      var g = taoMucTieu({ sid: o.sid, brain: o.brain, dk: o.dk, toiDa: o.toiDa }, +o.batDau || Date.now());
      g.id = String(o.id); g.vong = Math.max(1, +o.vong || 1); g.left = String(o.left || "");
      g.daChay = Math.max(0, +o.daChay || 0); g.chayTu = 0; g.state = "paused"; g.tiepNgay = true;
      out.push(g);
    });
    return out.slice(-TOI_DA_KHO);
  }
  function veKho(ds, now) {
    return JSON.stringify((ds || []).filter(function (g) { return g && g.sid; }).map(function (g) {
      return { id: g.id, sid: g.sid, brain: g.brain, dk: g.dk, vong: g.vong, toiDa: g.toiDa, left: g.left,
               batDau: g.batDau, daChay: thoiGian(g, now) };
    }));
  }

  // ---- HTML của thanh ----
  var SVG = {
    target: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/></svg>',
    trash: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
    pause: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>',
    play: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.5-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5z"/></svg>',
    chevron: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 15 6-6 6 6"/></svg>',
  };
  function nhan(st) { return tw(st === "paused" ? "gb.paused" : st === "waiting" ? "gb.waiting" : "gb.pursuing"); }
  function nutDung(g) {
    var chay = g.state === "running", t = tw(chay ? "gb.pause" : "gb.resume");
    return '<button type="button" class="gb-btn" data-act="' + (chay ? "pause" : "resume") + '" data-id="' + esc(g.id) +
      '" title="' + esc(t) + '" aria-label="' + esc(t) + '">' + (chay ? SVG.pause : SVG.play) + "</button>";
  }
  function nutXoa(g) {
    return '<button type="button" class="gb-btn gb-del" data-act="del" data-id="' + esc(g.id) + '" title="' +
      esc(tw("gb.del")) + '" aria-label="' + esc(tw("gb.del")) + '">' + SVG.trash + "</button>";
  }

  // ui = {mo: khung chi tiết đang mở, xo: danh sách đang xổ}. Không có mục tiêu thì chuỗi rỗng.
  function barHtml(ds, sid, now, ui) {
    ds = ds || []; ui = ui || {};
    var g = chonChinh(ds, sid);
    if (!g) return "";
    now = +now || Date.now();
    var st = trangThai(g, sid), n = ds.length;
    var h = '<div class="gb-row gb-' + st + '">';
    if (n > 1) {
      h += '<button type="button" class="gb-count" data-act="list" aria-expanded="' + (ui.xo ? "true" : "false") +
        '" title="' + esc(tw("gb.list", { n: n })) + '" aria-label="' + esc(tw("gb.list", { n: n })) + '">' + n + "</button>";
    }
    h += '<span class="gb-ic">' + SVG.target + "</span>" +
      '<button type="button" class="gb-main" data-act="' + (st === "waiting" ? "open" : "expand") + '" data-id="' + esc(g.id) +
      '" aria-expanded="' + (ui.mo ? "true" : "false") + '"><span class="gb-lbl">' + esc(nhan(st)) + '</span>' +
      '<span class="gb-txt">' + esc(g.dk) + "</span></button>" +
      '<span class="gb-time" data-gt="' + esc(g.id) + '">' + dinhDangGio(thoiGian(g, now)) + "</span>" +
      nutXoa(g) + nutDung(g) +
      '<button type="button" class="gb-btn gb-exp" data-act="expand" data-id="' + esc(g.id) + '" aria-expanded="' +
      (ui.mo ? "true" : "false") + '" title="' + esc(tw(ui.mo ? "gb.collapse" : "gb.expand")) + '" aria-label="' +
      esc(tw(ui.mo ? "gb.collapse" : "gb.expand")) + '">' + SVG.chevron + "</button></div>";
    if (ui.mo) {
      h += '<div class="gb-detail"><div class="gb-full">' + esc(g.dk) + "</div>" +
        '<div class="gb-meta">' + esc(nhan(st)) + " · " + esc(tw("gb.round", { v: g.vong, n: g.toiDa })) + "</div>" +
        (g.left ? '<div class="gb-meta">' + esc(tw("gb.left", { left: g.left })) + "</div>" : "") +
        (st === "waiting" ? '<div class="gb-meta">' + esc(tw("gb.waiting_hint")) + '</div><button type="button" class="gb-open" data-act="open" data-id="' +
          esc(g.id) + '">' + esc(tw("gb.open")) + "</button>" : "") + "</div>";
    }
    if (ui.xo && n > 1) {
      h += '<div class="gb-pop" role="dialog" aria-label="' + esc(tw("gb.list_title")) + '"><div class="gb-pop-head">' +
        esc(tw("gb.list_title")) + "</div>";
      ds.slice().sort(function (a, b) { return b.batDau - a.batDau; }).forEach(function (x) {
        var s2 = trangThai(x, sid);
        h += '<div class="gb-item gb-' + s2 + (x.sid === (sid || null) ? " gb-cur" : "") + '"><span class="gb-dot" aria-hidden="true"></span>' +
          '<button type="button" class="gb-item-main" data-act="open" data-id="' + esc(x.id) + '"><span class="gb-item-txt">' +
          esc(x.dk) + '</span><span class="gb-item-meta">' + esc(nhan(s2)) + " · " + esc(tw("gb.round", { v: x.vong, n: x.toiDa })) +
          ' · <span data-gt="' + esc(x.id) + '">' + dinhDangGio(thoiGian(x, now)) + "</span></span></button>" +
          nutDung(x) + nutXoa(x) + "</div>";
      });
      h += "</div>";
    }
    return h;
  }

  // ===================== KHO =====================
  var ds = [], nghe = [];
  function doc() { try { ds = tuKho(localStorage.getItem(KHO_KEY)); } catch (e) { ds = []; } }
  function luu() {
    try { localStorage.setItem(KHO_KEY, veKho(ds)); } catch (e) { /* chế độ riêng tư, node */ }
    nghe.forEach(function (f) { try { f(); } catch (e) { /* một người nghe hỏng không chặn người khác */ } });
  }
  function theoSid(sid) { return ds.filter(function (g) { return g.sid === (sid || null); })[0] || null; }
  function theoId(id) { return ds.filter(function (g) { return g.id === id; })[0] || null; }
  function them(o, now) {
    var g = taoMucTieu(o, now);
    ds = ds.filter(function (x) { return x.sid !== g.sid; }).concat([g]).slice(-TOI_DA_KHO);
    luu();
    return g;
  }
  function xoa(id) { ds = ds.filter(function (g) { return g.id !== id; }); luu(); }

  var api = {
    KHO_KEY: KHO_KEY, TOI_DA: TOI_DA, MARK: MARK,
    khoiMucTieu: khoiMucTieu, docDanhDau: docDanhDau, quyetDinh: quyetDinh, taoMucTieu: taoMucTieu,
    thoiGian: thoiGian, dinhDangGio: dinhDangGio, tamDung: tamDung, chayLai: chayLai, trangThai: trangThai,
    chonChinh: chonChinh, tuKho: tuKho, veKho: veKho, barHtml: barHtml,
    ds: function () { return ds.slice(); }, theoSid: theoSid, theoId: theoId, them: them, xoa: xoa, luu: luu, doc: doc,
    _datLai: function () { ds = []; nghe = []; },
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof window === "undefined" || typeof document === "undefined") return;
  window.MinMinGoals = api;
  doc();

  // ===================== CHẠY VÒNG (trình duyệt) =====================
  // app.js cấp window.MinMinChat: sid(), dangChay(sid), send(text, opts), note(text).
  function chat() { return window.MinMinChat || null; }
  function sidNay() { var c = chat(); return c ? (c.sid() || null) : null; }
  function brainNay() { try { return (window.JavisSessions && window.JavisSessions.brain()) || ""; } catch (e) { return ""; } }
  function ghi(s) { var c = chat(); if (c && s) c.note(s); }
  function cat(s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  // "/goal", "/goal <điều kiện>", "/goal clear|stop|tắt".
  function lenh(arg) {
    var c = chat(), cu = theoSid(sidNay());
    arg = String(arg || "").trim();
    if (/^(clear|stop|off|tắt|tat|xoá|xoa)$/i.test(arg)) {
      if (cu) { xoa(cu.id); return ghi(tw("goal.stopped")); }
      return ghi(tw("goal.none"));
    }
    if (!arg) {
      if (cu) return ghi(tw(cu.state === "paused" ? "goal.status_paused" : "goal.status", { dk: cat(cu.dk, 120), v: cu.vong, n: cu.toiDa }));
      return ghi(tw("goal.need", { n: TOI_DA }));
    }
    if (!c || !c.send(arg, { prefix: khoiMucTieu(arg, 1, TOI_DA), goal: true })) return ghi(tw("goal.err_send"));
    // send() đã cấp id cho chat mới, nên lấy id SAU khi gửi. Mục tiêu mới thay mục tiêu cũ của chat này.
    them({ sid: sidNay(), brain: brainNay(), dk: arg, toiDa: TOI_DA });
    ghi(tw("goal.start", { dk: cat(arg, 120), n: TOI_DA }));
  }

  // Bố gõ một tin thường trong chat có mục tiêu: tin của bố lên trước, mục tiêu tạm dừng, lượt đó không tính.
  function chenNgang(sid) {
    var g = theoSid(sid);
    if (!g) return;
    var dangChay = g.state === "running";
    tamDung(g); g.tiepNgay = true; g.xongLuot = false; g.ket = null;
    luu();
    if (dangChay) ghi(tw("goal.paused_takeover"));
  }
  // Nút Dừng của khung chat: lượt bị cắt, mục tiêu tạm dừng chứ không mất.
  function biDung(sid) {
    var g = theoSid(sid), c = chat();
    if (!g || g.state !== "running") return;
    tamDung(g);
    if (c && c.dangChay(g.sid)) g.catNgang = true; else { g.tiepNgay = true; g.xongLuot = false; }
    luu();
    ghi(tw("goal.paused"));
  }
  // Câu trả lời của một vòng vừa về (lượt chưa đóng): chỉ ghi nhận, hetLuot quyết định.
  function traLoi(sid, text, hoiLai) { var g = theoSid(sid); if (g) g.ket = { marker: docDanhDau(text), hoiLai: !!hoiLai }; }
  function loi(sid) { var g = theoSid(sid); if (g) g.ket = { loi: true }; }

  function tiepVong(g) {
    var c = chat();
    if (!c || theoId(g.id) !== g || g.state !== "running") return;
    if (c.sid() !== g.sid || c.dangChay(g.sid)) { g.tiepNgay = true; return; }
    if (g.vong >= g.toiDa) { xoa(g.id); return ghi(tw("goal.max", { n: g.toiDa })); }
    g.vong += 1;
    if (!c.send(tw("goal.cont"), { prefix: khoiMucTieu(g.dk, g.vong, g.toiDa, g.left), goal: true })) {
      g.vong -= 1; g.tiepNgay = true;
    }
    luu();
  }
  function apDung(g) {
    var qd = quyetDinh(g, g.ket);
    g.ket = null; g.xongLuot = false;
    if (qd.act === "tiep") {
      g.left = qd.left;
      if (g.state === "running") setTimeout(function () { tiepVong(g); }, 300); else g.tiepNgay = true;
      return luu();
    }
    xoa(g.id);
    var b = { v: g.vong, n: g.toiDa, why: qd.why || "", left: qd.left || "" };
    ghi(tw({ dat: "goal.done", ket: "goal.blocked", het_vong: "goal.max", dung_im: "goal.stuck",
             hoi_lai: "goal.ask", loi: "goal.err" }[qd.ly] || "goal.unknown", b));
  }
  // Đi tiếp khi: đang chạy, chat của nó đang mở, không có lượt nào đang chạy.
  function thuTiep(g) {
    var c = chat();
    if (!g || g.state !== "running" || !c || c.sid() !== g.sid || c.dangChay(g.sid)) return;
    if (g.tiepNgay) { g.tiepNgay = false; g.xongLuot = false; g.ket = null; setTimeout(function () { tiepVong(g); }, 300); return; }
    if (g.xongLuot) apDung(g);
  }
  // turn_done của phiên sid (kể cả chat đang chạy nền).
  function hetLuot(sid) {
    var g = theoSid(sid), c = chat();
    if (!g || !c) return;
    if (g.catNgang) { g.catNgang = false; g.ket = null; g.tiepNgay = true; g.xongLuot = false; return luu(); }
    if (g.tiepNgay) { g.ket = null; return; }
    g.xongLuot = true;
    if (c.dangChay(sid)) return;
    // Tạm dừng nhưng chat đang mở: vẫn quyết định ngay để "đã đạt" hay "không làm được" được báo liền.
    if (g.state === "paused" && c.sid() === sid) return apDung(g);
    thuTiep(g);
  }

  // Nút trên thanh.
  function bamNut(act, id) {
    var g = theoId(id), s = window.JavisSessions;
    if (!g) return;
    if (act === "del") { var nay = g.sid === sidNay(); xoa(id); if (nay) ghi(tw("goal.deleted")); return; }
    if (act === "pause") { tamDung(g); return luu(); }
    if (act === "resume") {
      chayLai(g); luu();
      if (g.sid === sidNay()) return thuTiep(g);
    }
    if ((act === "open" || act === "resume") && g.sid !== sidNay() && s && s.open) {
      Promise.resolve(s.open(g.sid)).then(function () { thuTiep(theoId(id)); });
    }
  }

  // ===================== THANH (DOM) =====================
  var ui = { mo: false, xo: false }, hen = null;
  function dsHien() { var b = brainNay(); return ds.filter(function (g) { return !g.brain || !b || g.brain === b; }); }
  function ve() {
    var bar = document.getElementById("goalBar");
    if (!bar) return;
    var list = dsHien();
    if (list.length < 2) ui.xo = false;
    var html = barHtml(list, sidNay(), Date.now(), ui);
    bar.innerHTML = html;
    bar.hidden = !html;
    if (hen) { clearInterval(hen); hen = null; }
    if (list.some(function (g) { return g.state === "running"; })) hen = setInterval(demGio, 1000);
  }
  // Mỗi giây chỉ thay chữ đồng hồ, không dựng lại thanh (dựng lại là mất focus nút đang bấm).
  function demGio() {
    var els = document.querySelectorAll("#goalBar [data-gt]"), now = Date.now();
    for (var i = 0; i < els.length; i++) {
      var g = theoId(els[i].getAttribute("data-gt"));
      if (g) els[i].textContent = dinhDangGio(thoiGian(g, now));
    }
  }
  nghe.push(ve);

  function gan() {
    var bar = document.getElementById("goalBar");
    if (!bar) return;
    bar.addEventListener("click", function (e) {
      var b = e.target.closest("[data-act]");
      if (!b) return;
      var act = b.getAttribute("data-act");
      if (act === "list") { ui.xo = !ui.xo; return ve(); }
      if (act === "expand") { ui.mo = !ui.mo; return ve(); }
      ui.xo = false;
      bamNut(act, b.getAttribute("data-id"));
      ve();
    });
    // Bấm ra ngoài thì danh sách thu lại. Soi đường đi của cú bấm: nút vừa bấm đã rời DOM vì thanh vẽ lại.
    document.addEventListener("click", function (e) {
      var duong = e.composedPath ? e.composedPath() : [e.target];
      if (ui.xo && duong.indexOf(bar) === -1) { ui.xo = false; ve(); }
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && ui.xo) { ui.xo = false; ve(); } });
    // Đổi chat: vẽ lại, và mục tiêu của chat vừa mở (đang chờ) thì chạy tiếp.
    window.addEventListener("javis:sessions-changed", function () { ve(); thuTiep(theoSid(sidNay())); });
    window.addEventListener("javis:i18n", ve);
    ve();
  }
  if (document.getElementById("goalBar")) gan(); else document.addEventListener("DOMContentLoaded", gan);

  api.lenh = lenh; api.chenNgang = chenNgang; api.biDung = biDung; api.traLoi = traLoi; api.loi = loi;
  api.hetLuot = hetLuot; api.bamNut = bamNut; api.ve = ve;
})();
