// Hòm thư navbar - HAI tầng dữ liệu, cố ý không trộn:
//
//   "Của tôi"  = /inbox : thư RIÊNG (kết quả việc nền, báo cáo định kỳ). Đã-đọc nằm ở SERVER
//                nên điện thoại và máy tính đếm giống nhau, và bấm vào là quay về ĐÚNG hội
//                thoại đã hỏi - nội dung đầy đủ nằm ở đó, không phải trong cái thẻ này.
//   "Tin tức"  = /notifications : bản phát hành + tin cộng đồng, phát chung cho mọi người.
//                Đã-đọc giữ ở localStorage như cũ (ai đọc trên máy nấy, không cần đồng bộ).
//
// Gộp một danh sách thì một kết quả công việc thật bị chôn dưới mấy dòng changelog.
(function () {
  var READ_KEY = "javis.notifications.read";
  var INIT_KEY = "javis.notifications.initialized";
  var TAB_KEY = "javis.notifications.tab";
  var HIDE_KEY = "minmin.notifications.hidden";
  var MAX_ITEMS = 30;
  var PAGE_SIZE = 5;
  var state = { items: [], read: new Set(), loadedAt: 0, loading: false, visibleCount: PAGE_SIZE,
                thu: [], thuChuaDoc: 0, tab: "mine",
                // 26.10.312: chuông chỉ hiện tin CHƯA ĐỌC. Tin đã đọc hiện lại khi bấm "Xem N thông báo
                // đã đọc" (chỉ cho lần mở này); tin bộ chỉ huy đã lọc nằm trong ngăn "Đã lọc".
                showRead: false, showFiltered: false, learned: "", policy: null, hidden: new Set() };
  // Ngày giờ đi theo NGÔN NGỮ đang chọn, không viết cứng "vi-VN": người đọc bản tiếng Anh
  // mà thấy định dạng ngày kiểu Việt là lạc quẻ. Cả dashboard lấy locale từ đúng chỗ này.
  function LOC() { return (window.JavisI18n && JavisI18n.locale()) || "vi-VN"; }

  function byId(id) { return document.getElementById(id); }
  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function safeUrl(value) {
    var url = String(value || "").trim();
    return /^https?:\/\//i.test(url) ? url : "";
  }
  function loadRead() {
    try {
      var raw = JSON.parse(localStorage.getItem(READ_KEY) || "[]");
      state.read = new Set(Array.isArray(raw) ? raw.map(String) : []);
    } catch (e) { state.read = new Set(); }
  }
  function loadHidden() {
    try {
      var raw = JSON.parse(localStorage.getItem(HIDE_KEY) || "[]");
      state.hidden = new Set(Array.isArray(raw) ? raw.map(String) : []);
    } catch (e) { state.hidden = new Set(); }
  }
  function saveHidden() {
    try { localStorage.setItem(HIDE_KEY, JSON.stringify(Array.from(state.hidden).slice(-300))); } catch (e) {}
  }
  function saveRead() {
    try { localStorage.setItem(READ_KEY, JSON.stringify(Array.from(state.read).slice(-300))); } catch (e) {}
  }
  function firstRun(items) {
    try {
      if (localStorage.getItem(INIT_KEY) === "1") return;
      // Không biến toàn bộ lịch sử phiên bản thành hàng trăm tin chưa đọc ở lần mở đầu.
      // Chỉ giữ unread cho bản đang dùng/bản mới và thông báo cộng đồng ưu tiên cao.
      items.forEach(function (item) {
        var important = item.priority === "high" &&
          (item.kind !== "update" || item.is_current || item.update_available);
        if (!important) state.read.add(String(item.id));
      });
      localStorage.setItem(INIT_KEY, "1");
      saveRead();
    } catch (e) {}
  }
  // Bản ĐÃ CÀI thì không bao giờ tính là chưa đọc.
  //
  // Chủ repo báo (2026-08-12): "ấn đọc tất cả rồi, nâng cấp bản mới vẫn hiện các số như là
  // chưa đọc". Đo lại thì cơ chế đánh dấu không hỏng - nó giữ đúng qua cả lần tải lại trang.
  // Chuyện thật sự xảy ra: giữa lúc bấm "Đọc tất cả" và lúc nâng cấp có thêm vài bản phát
  // hành mới. Chúng chưa từng được đọc nên vào hàng chưa đọc, rồi người dùng CÀI CHÍNH CHÚNG,
  // mà chuông vẫn nhắc.
  //
  // Nhắc một bản đang nằm sẵn trong máy là vô nghĩa: thông báo phát hành chỉ đáng chú ý khi
  // nó là thứ mình CHƯA có. Cài xong là hết việc, khỏi cần bấm đọc thêm lần nữa.
  function chuaDoc(item) {
    if (item.kind === "update" && item.installed) return false;
    return !state.read.has(String(item.id));
  }
  function unreadItems() {
    return state.items.filter(chuaDoc);
  }
  function markRead(id) {
    state.read.add(String(id));
    saveRead();
    render();
  }
  function markAll() {
    if (state.tab === "mine") {
      // Thư riêng: đã-đọc nằm ở SERVER, nên đánh dấu ở đây phải đi qua API chứ không
      // chỉ tô lại màu trên máy này.
      state.thu.forEach(function (t) { t.read = true; });
      state.thuChuaDoc = 0;
      state.showRead = false;
      docThu({ all: true }).then(render);
      render();
      return;
    }
    state.items.forEach(function (item) { state.read.add(String(item.id)); });
    saveRead();
    render();
  }
  function kindLabel(kind) {
    if (kind === "marketing") return window.t("noti.kind_marketing");
    if (kind === "community") return window.t("noti.kind_community");
    if (kind === "security") return window.t("noti.kind_security");
    return window.t("noti.kind_update");
  }
  function openUpdates() {
    closePanel();
    try {
      if (window.Alpine && Alpine.store("nav")) Alpine.store("nav").go("logs");
    } catch (e) {}
  }
  function openItem(item) {
    markRead(item.id);
    var action = item.action || (item.cta && item.cta.action);
    var url = safeUrl(item.cta && item.cta.url);
    if (url) {
      window.open(url, "_blank", "noopener");
      return;
    }
    if (item.kind === "update" || action === "changelog") openUpdates();
  }
  // ---------- Hòm thư "Của tôi" ----------
  function thoiGian(ts) {
    var d = new Date((Number(ts) || 0) * 1000);
    if (!ts || isNaN(d.getTime())) return "";
    var cach = (Date.now() - d.getTime()) / 1000;
    if (cach < 60) return window.t("noti.ago_now");
    if (cach < 3600) return window.t("noti.ago_min", { count: Math.floor(cach / 60) });
    if (cach < 86400) return window.t("noti.ago_hour", { count: Math.floor(cach / 3600) });
    return d.toLocaleDateString(LOC(), { day: "2-digit", month: "2-digit" }) + " " +
           d.toLocaleTimeString(LOC(), { hour: "2-digit", minute: "2-digit" });
  }
  function nhanLoai(kind) {
    if (kind === "report") return window.t("noti.card_report");
    if (kind === "system") return window.t("noti.card_system");
    return window.t("noti.card_answer");
  }
  async function docThu(body) {
    try {
      var r = await fetch("/inbox/read", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      var d = await r.json();
      if (typeof d.unread === "number") state.thuChuaDoc = d.unread;
    } catch (e) {}
  }
  // Kênh của hội thoại đích, dạng "agent:<slug>" / "workflow:<slug>" (server ghi vào mẩu thư).
  // Thư CŨ không có trường này nên trả null và mọi thứ chạy y như trước.
  function congSuCuaThu(item) {
    var m = /^(agent|workflow):(.+)$/.exec(String((item && item.channel) || ""));
    return m ? { loai: m[1], slug: m[2] } : null;
  }
  // Bấm một mẩu thư = quay về ĐÚNG hội thoại đã hỏi. Mở hội thoại MỚI ở đây là sai: toàn bộ
  // ngữ cảnh nằm trong hội thoại cũ, hỏi tiếp ở chỗ khác là phải kể lại từ đầu.
  function moThu(item) {
    item.read = true;
    docThu({ id: item.id }).then(render);
    if (!item.session_id) { render(); return; }
    closePanel();
    // Hội thoại của một TRỢ LÝ / QUY TRÌNH phải mở ở trang Cộng sự, không đổ vào khung chat
    // của bộ não chính. Đổ nhầm thì hai chuyện xảy ra cùng lúc: người dùng nhìn một đoạn chat
    // với trợ lý trên màn Javis mà không hiểu vì sao, và phiên đang mở trở thành phiên của
    // trợ lý - tin gõ tiếp bay thẳng vào đó (đúng lỗi bản 0.59.15 đã chữa cho đường rời
    // trang, hòm thư mở lại nó bằng một cửa khác).
    var cs = congSuCuaThu(item);
    if (cs && window.JavisWorkspace && window.JavisWorkspace.openCommand) {
      try {
        window.JavisWorkspace.openCommand(cs.loai, cs.slug, item.session_id);
        return;
      } catch (e) {}
    }
    try {
      if (window.Alpine && Alpine.store("nav") && Alpine.store("nav").active !== "home"
          && Alpine.store("nav").active !== "chat") Alpine.store("nav").go("home");
    } catch (e) {}
    try { if (window.JavisSessions) window.JavisSessions.open(item.session_id); } catch (e) {}
  }
  // Bảng TÊN KHOÁ đầy đủ (không ghép chuỗi) để test i18n quét ra được mọi khoá.
  var KHOA_NHOM = { reminder: "noti.g_reminder", question: "noti.g_question", chatbot: "noti.g_chatbot",
    connection: "noti.g_connection", incident: "noti.g_incident", job: "noti.g_job", cost: "noti.g_cost",
    update: "noti.g_update", other: "noti.g_other" };
  var KHOA_CHE_DO = { all: "noti.mode_all", important: "noti.mode_important", urgent: "noti.mode_urgent",
    off: "noti.mode_off" };
  function tenNhom(g) { return window.t(KHOA_NHOM[g] || KHOA_NHOM.other); }
  function nhanNhom(item) {
    var g = item.group ? tenNhom(item.group) : nhanLoai(item.kind);
    if (item.level === "urgent") g += " · " + window.t("noti.lv_urgent");
    else if (item.level === "important") g += " · " + window.t("noti.lv_important");
    return g;
  }
  function theThu(item) {
    var chua = !item.read ? " unread" : "";
    var phu = item.session_id ? window.t("noti.reopen_chat") : "";
    var nut = "";
    if (item.filtered) nut = '<button class="noti-mini" type="button" data-thu-act="needed">' + esc(window.t("noti.needed")) + "</button>";
    else if (!item.read) nut = '<button class="noti-mini" type="button" data-thu-act="not_needed">' + esc(window.t("noti.not_needed")) + "</button>";
    return '<article class="noti-card' + chua + (item.level === "urgent" ? " urgent" : "") +
      '" tabindex="0" role="button" data-thu-id="' + esc(item.id) + '">' +
      '<div class="noti-card-top"><span class="noti-kind ' + esc(item.kind || "answer") + '">' +
      esc(nhanNhom(item)) + '</span><span class="noti-time">' + esc(thoiGian(item.ts)) + "</span>" +
      '<button class="noti-x" type="button" data-thu-act="xoa" aria-label="' + esc(window.t("noti.dismiss")) +
      '" title="' + esc(window.t("noti.dismiss")) + '">×</button></div>' +
      "<h4>" + esc(item.title || window.t("noti.msg_title")) + "</h4>" +
      '<p class="noti-card-body">' + esc(item.body || "") + "</p>" +
      (phu || nut ? '<div class="noti-card-foot">' + (phu ? '<span class="noti-cta">' + phu + "</span>" : "<span></span>") + nut + "</div>" : "") +
      "</article>";
  }
  async function xoaThu(id) {
    state.thu = state.thu.filter(function (x) { return String(x.id) !== String(id); });
    render();
    try {
      var r = await fetch("/inbox/delete", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: id }) });
      var d = await r.json();
      if (typeof d.unread === "number") state.thuChuaDoc = d.unread;
    } catch (e) {}
    render();
  }
  // "Không cần báo" / "Nên báo": MinMin nhớ loại tin này cho lần sau, và nói ra một lần đã nhớ gì.
  async function phanHoi(item, axis) {
    item.read = true;
    render();
    try {
      var r = await fetch("/inbox/react", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: item.id, axis: axis }) });
      var d = await r.json();
      if (typeof d.unread === "number") state.thuChuaDoc = d.unread;
      state.learned = d.message || "";
      state.policy = null;
    } catch (e) {}
    taiThu();
  }
  function veHomThu(list) {
    var chuaDoc = state.thu.filter(function (x) { return !x.read; });
    var daDoc = state.thu.filter(function (x) { return x.read && !x.filtered; });
    var daLoc = state.thu.filter(function (x) { return x.filtered; });
    var hien = chuaDoc.concat(state.showRead ? daDoc : []).slice(0, MAX_ITEMS);
    var html = "";
    if (state.learned) html += '<div class="noti-learned">' + esc(state.learned) + "</div>";
    if (hien.length) html += hien.map(theThu).join("");
    else html += '<div class="noti-empty">' + esc(window.t(state.thu.length ? "noti.inbox_clear" : "noti.inbox_empty")) +
      "<br>" + esc(window.t("noti.inbox_empty_sub")) + "</div>";
    if (daDoc.length && !state.showRead) html += '<button class="noti-load-more" type="button" id="notiShowRead">' +
      esc(window.t("noti.show_read", { count: daDoc.length })) + "</button>";
    html += '<button class="noti-load-more" type="button" id="notiShowFiltered">' +
      esc(window.t(state.showFiltered ? "noti.filtered_hide" : "noti.filtered_show", { count: daLoc.length })) + "</button>";
    if (state.showFiltered) {
      html += '<div class="noti-filtered"><p class="noti-filtered-note">' + esc(window.t("noti.filtered_note")) + "</p>" +
        daLoc.slice(0, MAX_ITEMS).map(theThu).join("") + '<div id="notiPolicy"></div></div>';
    }
    list.innerHTML = html;
    var sr = byId("notiShowRead");
    if (sr) sr.addEventListener("click", function () { state.showRead = true; render(); });
    var sf = byId("notiShowFiltered");
    if (sf) sf.addEventListener("click", function () { state.showFiltered = !state.showFiltered; render(); });
    if (state.showFiltered) vePolicy();
    list.querySelectorAll("[data-thu-id]").forEach(function (card) {
      function chay() {
        var it = state.thu.find(function (x) { return String(x.id) === card.dataset.thuId; });
        if (it) moThu(it);
      }
      card.querySelectorAll("[data-thu-act]").forEach(function (b) {
        b.addEventListener("click", function (e) {
          e.stopPropagation();
          var it = state.thu.find(function (x) { return String(x.id) === card.dataset.thuId; });
          if (!it) return;
          if (b.dataset.thuAct === "xoa") xoaThu(it.id);
          else phanHoi(it, b.dataset.thuAct);
        });
      });
      card.addEventListener("click", chay);
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); chay(); }
      });
    });
  }
  async function vePolicy() {
    var hop = byId("notiPolicy");
    if (!hop) return;
    if (!state.policy) {
      try { state.policy = await (await fetch("/thong-bao/muc", { cache: "no-store" })).json(); } catch (e) { return; }
      hop = byId("notiPolicy");
      if (!hop) return;
    }
    var p = state.policy || {};
    var modes = p.modes || [];
    var h = '<h5 class="noti-policy-h">' + esc(window.t("noti.policy_title")) + "</h5>";
    (p.groups || []).forEach(function (g) {
      h += '<label class="noti-policy-row"><span>' + esc(tenNhom(g.group)) + "</span>" +
        '<select data-nhom="' + esc(g.group) + '">' + modes.map(function (m) {
          return '<option value="' + esc(m.id) + '"' + (m.id === g.mode ? " selected" : "") + ">" +
            esc(window.t(KHOA_CHE_DO[m.id] || "noti.mode_urgent")) + "</option>";
        }).join("") + "</select></label>";
    });
    var ch = (p.changes || []).filter(function (c) { return !c.undone; }).slice(0, 5);
    if (ch.length) {
      h += '<h5 class="noti-policy-h">' + esc(window.t("noti.policy_changes")) + "</h5>";
      ch.forEach(function (c) {
        h += '<div class="noti-policy-row"><span>' + esc(c.text || "") + '</span><button class="noti-mini" type="button" data-undo="' +
          esc(c.id) + '">' + esc(window.t("noti.undo")) + "</button></div>";
      });
    }
    hop.innerHTML = h;
    async function gui(url, body) {
      try {
        var r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        var d = await r.json();
        if (d && d.ok) state.policy = d;
      } catch (e) {}
      vePolicy();
    }
    hop.querySelectorAll("select[data-nhom]").forEach(function (sel) {
      sel.addEventListener("change", function () { gui("/thong-bao/muc/nhom", { group: sel.dataset.nhom, mode: sel.value }); });
    });
    hop.querySelectorAll("[data-undo]").forEach(function (b) {
      b.addEventListener("click", function () { gui("/thong-bao/muc/hoan-tac", { id: b.dataset.undo }); });
    });
  }
  function chonTab(tab) {
    state.tab = tab === "news" ? "news" : "mine";
    try { localStorage.setItem(TAB_KEY, state.tab); } catch (e) {}
    state.visibleCount = PAGE_SIZE;
    state.showRead = false;
    render();
  }

  function render() {
    var trigger = byId("notificationTrigger");
    var badge = byId("notificationBadge");
    var list = byId("notificationList");
    var summary = byId("notificationSummary");
    if (!trigger || !badge || !list) return;
    var unread = unreadItems();
    // Chấm đỏ trên chuông đếm CẢ HAI tầng: thư riêng chưa đọc + tin chung chưa đọc. Chỉ đếm
    // một bên thì một kết quả công việc vừa về có thể không làm chuông đổi gì cả.
    var tong = unread.length + state.thuChuaDoc;
    trigger.classList.toggle("has-unread", tong > 0);
    badge.hidden = tong === 0;
    badge.textContent = tong > 99 ? "99+" : String(tong);
    if (summary) summary.textContent = tong
      ? window.t("noti.unread_n", { count: tong })
      : window.t("noti.all_read");

    var tabMine = byId("notiTabMine"), tabNews = byId("notiTabNews");
    if (tabMine && tabNews) {
      tabMine.classList.toggle("active", state.tab === "mine");
      tabNews.classList.toggle("active", state.tab === "news");
      tabMine.setAttribute("aria-selected", state.tab === "mine" ? "true" : "false");
      tabNews.setAttribute("aria-selected", state.tab === "news" ? "true" : "false");
      var cM = byId("notiTabMineCount"), cN = byId("notiTabNewsCount");
      if (cM) { cM.hidden = !state.thuChuaDoc; cM.textContent = String(state.thuChuaDoc); }
      if (cN) { cN.hidden = !unread.length; cN.textContent = String(unread.length); }
    }
    if (state.tab === "mine") { veHomThu(list); return; }

    if (!state.items.length) {
      list.innerHTML = '<div class="noti-empty">' + esc(window.t("noti.news_empty")) + "<br>" +
        esc(window.t("noti.news_empty_sub")) + "</div>";
      return;
    }
    var conLai = state.items.filter(function (x) { return !state.hidden.has(String(x.id)); });
    var tinDaDoc = conLai.filter(function (x) { return !chuaDoc(x); });
    var limited = (state.showRead ? conLai : conLai.filter(chuaDoc)).slice(0, MAX_ITEMS);
    var visible = limited.slice(0, state.visibleCount);
    var cards = visible.map(function (item) {
      var id = String(item.id);
      // Dùng CHUNG một luật với con số trên chuông. Trước đây thẻ tự soi state.read, nên chỉ
      // cần hai chỗ lệch nhau một chút là chuông báo 0 mà thẻ vẫn tô đậm kiểu chưa đọc.
      var unreadClass = chuaDoc(item) ? " unread" : "";
      var kind = item.kind || "update";
      // Release chỉ cần tóm tắt; toàn bộ bullet đã có ở trang Nhật ký cập nhật.
      // Tin cộng đồng/marketing được giữ body nhưng clamp bằng CSS để card vẫn gọn.
      var body = kind !== "update" && item.body
        ? '<p class="noti-card-body">' + esc(item.body) + "</p>"
        : "";
      var ctaLabel = (item.cta && item.cta.label) || (kind === "update" ? window.t("noti.cta_update") : "");
      var cta = ctaLabel ? '<span class="noti-cta">' + esc(ctaLabel) + "</span>" : "";
      return '<article class="noti-card' + unreadClass + '" tabindex="0" role="button" data-noti-id="' + esc(id) + '">' +
        '<div class="noti-card-top"><span class="noti-kind ' + esc(kind) + '">' + esc(kindLabel(kind)) + '</span>' +
        '<span class="noti-time">' + esc(item.published_at || "") + "</span>" +
        '<button class="noti-x" type="button" data-an-tin="' + esc(id) + '" aria-label="' + esc(window.t("noti.dismiss")) +
        '" title="' + esc(window.t("noti.dismiss")) + '">×</button></div>' +
        "<h4>" + esc(item.title || window.t("noti.card_untitled")) + "</h4>" +
        '<p class="noti-card-summary">' + esc(item.summary || "") + "</p>" + body + cta + "</article>";
    }).join("");
    var remaining = limited.length - visible.length;
    var loadMore = remaining > 0
      ? '<button class="noti-load-more" id="notificationLoadMore" type="button">' +
        esc(window.t("noti.load_more", { count: Math.min(PAGE_SIZE, remaining) })) + "</button>"
      : "";
    var xemDaDoc = (!state.showRead && tinDaDoc.length)
      ? '<button class="noti-load-more" type="button" id="notiNewsShowRead">' +
        esc(window.t("noti.show_read", { count: tinDaDoc.length })) + "</button>"
      : "";
    var trong = !visible.length ? '<div class="noti-empty">' + esc(window.t("noti.inbox_clear")) + "</div>" : "";
    list.innerHTML = trong + cards + loadMore + xemDaDoc;
    var nr = byId("notiNewsShowRead");
    if (nr) nr.addEventListener("click", function () { state.showRead = true; render(); });
    list.querySelectorAll("[data-an-tin]").forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        state.hidden.add(String(b.dataset.anTin));
        state.read.add(String(b.dataset.anTin));
        saveHidden(); saveRead(); render();
      });
    });
    list.querySelectorAll("[data-noti-id]").forEach(function (card) {
      function activate() {
        var item = state.items.find(function (x) { return String(x.id) === card.dataset.notiId; });
        if (item) openItem(item);
      }
      card.addEventListener("click", activate);
      card.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); activate(); }
      });
    });
    var moreButton = byId("notificationLoadMore");
    if (moreButton) moreButton.addEventListener("click", function () {
      state.visibleCount = Math.min(state.visibleCount + PAGE_SIZE, MAX_ITEMS);
      render();
    });
  }
  // Hòm thư tải RIÊNG và tải thường xuyên hơn /notifications: thư riêng là thứ vừa xảy ra,
  // còn changelog thì nửa tiếng mới đổi một lần. Nhốt chung một nhịp là hoặc thư về chậm,
  // hoặc hỏi GitHub quá dày.
  async function taiThu() {
    try {
      var d = await (await fetch("/inbox?limit=40", { cache: "no-store" })).json();
      state.thu = Array.isArray(d.items) ? d.items : [];
      state.thuChuaDoc = Number(d.unread) || 0;
      render();
    } catch (e) {}
  }

  async function load(force) {
    taiThu();
    if (state.loading || (!force && Date.now() - state.loadedAt < 300000)) return;
    state.loading = true;
    var list = byId("notificationList");
    if (!state.items.length && list && state.tab === "news") list.innerHTML = '<div class="noti-loading">' + esc(window.t("noti.loading")) + "</div>";
    try {
      var response = await fetch("/notifications", { cache: "no-store" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      var data = await response.json();
      state.items = Array.isArray(data.items) ? data.items : [];
      state.visibleCount = PAGE_SIZE;
      state.loadedAt = Date.now();
      firstRun(state.items);
      render();
    } catch (e) {
      if (list && state.tab === "news") list.innerHTML = '<div class="noti-empty">' +
        esc(window.t("noti.load_fail")) + "<br>" + esc(window.t("noti.load_fail_sub")) + "</div>";
    } finally { state.loading = false; }
  }
  function openPanel() {
    var panel = byId("notificationPanel"), shade = byId("notificationShade"), trigger = byId("notificationTrigger");
    if (!panel || !trigger) return;
    panel.hidden = false; panel.setAttribute("aria-hidden", "false");
    // Mỗi lần mở lại chuông: về danh sách chưa đọc, câu "đã nhớ" chỉ nói một lần.
    state.showRead = false; state.learned = "";
    if (shade) shade.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    load(false);
    veNutPush();
  }
  function closePanel() {
    var panel = byId("notificationPanel"), shade = byId("notificationShade"), trigger = byId("notificationTrigger");
    if (panel) { panel.hidden = true; panel.setAttribute("aria-hidden", "true"); }
    if (shade) shade.hidden = true;
    if (trigger) trigger.setAttribute("aria-expanded", "false");
  }
  // ---------- Công tắc thông báo đẩy ----------
  // `loi`: thông báo vừa hỏng thì GIỮ NGUYÊN lý do trên màn hình. Bản đầu vẽ lại dòng ghi
  // chú mặc định ngay sau khi báo lỗi, nên người dùng bấm "Bật" thấy y hệt như chưa bấm -
  // không rõ là chưa chạy, đang chạy, hay đã hỏng.
  async function veNutPush(loi) {
    var hop = byId("notificationPush"), nut = byId("notificationPushToggle");
    var ghi = byId("notificationPushNote"), thu = byId("notificationPushTest");
    if (!hop || !nut || !window.JavisPush) return;
    hop.hidden = false;
    if (!JavisPush.batDuoc()) {
      // Không bấm được thì nói LÝ DO. Một cái nút bấm mãi không lên còn tệ hơn không có nút.
      nut.hidden = true; if (thu) thu.hidden = true;
      if (ghi) ghi.textContent = loi || JavisPush.lyDo();
      return;
    }
    nut.hidden = false;
    var on = await JavisPush.dangBat();
    nut.textContent = on ? window.t("noti.push_off") : window.t("noti.push_on");
    nut.classList.toggle("primary", !on);
    if (thu) thu.hidden = !on;
    if (ghi) ghi.textContent = loi || (on
      ? window.t("noti.push_on_here")
      : window.t("noti.push_note"));
    if (ghi) ghi.classList.toggle("loi", !!loi);
    if (loi || !on) return;
    // Bật/tắt là việc của TỪNG máy, nên "đang bật ở đây" chưa trả lời được "máy kia có nhận
    // không". Nói luôn số thiết bị máy chủ đang đẩy tới, và nêu đích danh máy nào đang hỏng.
    var tb = await JavisPush.thietBi();
    if (!ghi || !tb.length) return;
    var hong = tb.filter(function (x) { return x.lan_cuoi && !x.ok_lan_cuoi; });
    if (hong.length) {
      ghi.textContent = window.t("noti.push_dev_err", { count: tb.length, dv: hong[0].dich_vu,
        loi: String(hong[0].loi_lan_cuoi || "").slice(0, 80) });
      ghi.classList.add("loi");
    } else {
      ghi.textContent = window.t("noti.push_dev_ok", { count: tb.length });
      ghi.classList.remove("loi");
    }
  }
  function gaNutPush() {
    var nut = byId("notificationPushToggle"), ghi = byId("notificationPushNote");
    var thu = byId("notificationPushTest");
    if (nut) nut.addEventListener("click", async function () {
      if (!window.JavisPush) return;
      nut.disabled = true;
      var dangBat = await JavisPush.dangBat();
      var r = dangBat ? await JavisPush.tat() : await JavisPush.bat();
      nut.disabled = false;
      await veNutPush(r.ok ? "" : (r.error || window.t("noti.push_err")));
    });
    if (thu) thu.addEventListener("click", async function () {
      thu.disabled = true;
      var r = await JavisPush.thu();
      thu.disabled = false;
      if (!ghi) return;
      // Nói rõ ĐỦ MẤY MÁY nhận được, chứ không phải "đã gửi" chung chung: gửi thử trên điện
      // thoại mà chỉ máy tính kêu thì câu "đã gửi" là một câu đúng-nhưng-vô-dụng.
      ghi.textContent = r.ok
        ? window.t("noti.push_test_ok", { count: r.so || 1 })
        : (r.error || window.t("noti.push_test_err"));
      ghi.classList.toggle("loi", !r.ok);
    });
  }

  function init() {
    var trigger = byId("notificationTrigger");
    if (!trigger) return;
    loadRead();
    loadHidden();
    try { state.tab = localStorage.getItem(TAB_KEY) === "news" ? "news" : "mine"; } catch (e) {}
    trigger.addEventListener("click", function () {
      byId("notificationPanel").hidden ? openPanel() : closePanel();
    });
    byId("notificationClose").addEventListener("click", closePanel);
    byId("notificationShade").addEventListener("click", closePanel);
    byId("notificationReadAll").addEventListener("click", markAll);
    byId("notificationRefresh").addEventListener("click", function () { load(true); });
    byId("notificationOpenUpdates").addEventListener("click", openUpdates);
    var tm = byId("notiTabMine"), tn = byId("notiTabNews");
    if (tm) tm.addEventListener("click", function () { chonTab("mine"); });
    if (tn) tn.addEventListener("click", function () { chonTab("news"); });
    gaNutPush();
    veNutPush();
    document.addEventListener("keydown", function (event) { if (event.key === "Escape") closePanel(); });
    document.addEventListener("visibilitychange", function () { if (!document.hidden) load(false); });
    load(true);

    // Deep-link từ thông báo đẩy: /?mo_thu=<id>. Mở panel rồi nhảy thẳng vào mẩu thư đó.
    try {
      var idTu = new URLSearchParams(location.search).get("mo_thu");
      if (idTu) {
        history.replaceState(null, "", location.pathname);   // đừng để tham số dính lại khi F5
        setTimeout(function () { moTheoId(idTu); }, 1200);
      }
    } catch (e) {}
  }

  async function moTheoId(id) {
    await taiThu();
    var it = state.thu.find(function (x) { return String(x.id) === String(id); });
    if (it) moThu(it); else openPanel();
  }

  // API cho phần còn lại của app: app.js gọi refresh() khi WebSocket báo có thư mới, push.js
  // gọi moTu() khi người dùng bấm vào thông báo của hệ điều hành.
  window.JavisInbox = {
    refresh: function () { taiThu(); },
    // Hội thoại đang mở thì thư của nó coi như đã đọc - không thì một kết quả bị đếm hai lần.
    docPhien: function (sid) {
      if (!sid) return;
      docThu({ session_id: sid }).then(function () { taiThu(); });
    },
    moTu: function (url) {
      var id = "";
      try { id = new URL(url, location.origin).searchParams.get("mo_thu") || ""; } catch (e) {}
      if (id && id !== "test") moTheoId(id); else openPanel();
    },
  };

  // Từ điển về BẤT ĐỒNG BỘ (i18n/index.js fetch xong mới bắn "javis:i18n"). Hòm thư có thể
  // đã vẽ xong trước lúc đó và in ra mã khoá; đổi ngôn ngữ giữa chừng cũng không ăn nếu
  // không nghe. Vẽ lại thẻ, và vẽ lại cả ô thông báo đẩy khi ô đó đang hiện.
  window.addEventListener("javis:i18n", function () {
    render();
    var hop = byId("notificationPush");
    if (hop && !hop.hidden) veNutPush();
  });

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
