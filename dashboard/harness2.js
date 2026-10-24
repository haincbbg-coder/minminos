/* harness2.js - màn "Cải tiến có đối chứng" (Trụ 6, 26.10.217) cho MỘT trợ lý.

   Mở từ trang Cộng sự (workspace.js, cột phải Cài đặt của trợ lý). Bốn màn trong cùng một hộp:
     1. Cài đặt: tick đề (việc gần đây), gõ thêm đề, chọn k, chế độ, bộ não cải tiến; xem ước
        lượng số lượt và tiền TRƯỚC khi bấm Chạy.
     2. Tiến độ: hỏi /harness/trang-thai mỗi 3 giây, có nút Dừng.
     3. Kết quả: khác biệt từng file, lý do, bảng "mỗi thay đổi đã làm gì", hành động trợ lý định
        làm (đã giả lập), điểm, chi phí; nút Áp dụng / Bỏ / Hoàn tác.
     4. Lịch sử các lần cải tiến của trợ lý.

   Hộp chiếm trọn màn hình ở điện thoại (console.css .h2-modal). Phần thuần (nhanTrangThai,
   tomTatUoc, dongDiem) phơi ra để test bằng node. Chữ hiện ra lấy từ window.t; câu do máy chủ
   trả về (lý do, cảnh báo) hiện nguyên văn. KHÔNG dùng ký tự em dash. */
(function () {
  "use strict";
  var W = (typeof window !== "undefined") ? window : {};
  var t = function (k, v) { return (W.t ? W.t(k, v) : k); };
  var ic = function (n) { return (W.ic ? W.ic(n) : ""); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }
  async function postJ(url, body) {
    var r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
    return r.json();
  }
  async function getJ(url) { var r = await fetch(url); return r.json(); }
  function usd(x) { var n = Number(x || 0); return n < 0.01 ? n.toFixed(4) : n.toFixed(2); }

  // ---------- phần thuần ----------
  /** Nhãn trạng thái. Viết đủ chữ từng khoá để bộ quét i18n thấy (không ghép chuỗi khoá). */
  function nhanTrangThai(st) {
    if (st === "dang_chay") return t("h2.st_running");
    if (st === "xong") return t("h2.st_done");
    if (st === "loi") return t("h2.st_error");
    if (st === "dung") return t("h2.st_stopped");
    if (st === "da_ap_dung") return t("h2.st_applied");
    if (st === "da_bo") return t("h2.st_discarded");
    if (st === "da_hoan_tac") return t("h2.st_undone");
    return st || "";
  }
  function tomTatUoc(u) {
    u = u || {};
    return t("h2.estimate", { a: u.luot_agent || 0, b: u.phien_cai_tien || 0, c: u.phien_ngoai || 0, usd: usd(u.usd) });
  }
  /** Các dòng điểm cho người đọc: điểm luật (nếu có đề đáp án) + điểm phụ tất định. */
  function dongDiem(diem) {
    var ra = [];
    diem = diem || {};
    var l = diem.h2_diem_luat;
    if (l) ra.push(t("h2.score_rule", { a: Math.round((l.goc_tb || 0) * 100), b: Math.round((l.ban_chon || 0) * 100) }));
    var phu = diem.phu || {};
    Object.keys(phu).sort().forEach(function (n) {
      var p = phu[n] || {};
      ra.push(t("h2.score_soft", { nhan: n, g: p.giao_duoc || 0, n: p.so_luot || 0, e: p.tool_loi || 0, s: p.so_khong_nguon || 0 }));
    });
    return ra;
  }

  // ---------- trạng thái của hộp ----------
  var S = { item: null, brain: "brain", lop: null, hen: null, uocHen: null };

  function dong() {
    if (S.hen) { clearTimeout(S.hen); S.hen = null; }
    if (S.lop && S.lop.parentNode) S.lop.parentNode.removeChild(S.lop);
    S.lop = null;
  }
  function than() { return S.lop ? S.lop.querySelector(".h2-body") : null; }
  function loi(msg) { var b = than(); if (b) b.insertAdjacentHTML("afterbegin", '<div class="h2-err">' + esc(t("h2.err", { e: msg })) + "</div>"); }

  function mo(item, opts) {
    if (!item || !item.slug) return;
    dong();
    S.item = item;
    S.brain = (opts && opts.brain) || "brain";
    var lop = document.createElement("div");
    lop.className = "modal-overlay open";
    lop.id = "h2Modal";
    lop.innerHTML = '<div class="h2-modal" role="dialog" aria-modal="true">' +
      '<div class="fm-head"><span>' + ic("sparkles") + " " + esc(t("h2.title", { ten: item.name || item.slug })) + "</span>" +
      '<button type="button" class="fm-close" data-dong aria-label="' + esc(t("common.close")) + '">' + ic("x") + "</button></div>" +
      '<div class="h2-tabs"><button type="button" class="ws-btn" data-tab="cai">' + esc(t("h2.tab_setup")) + "</button>" +
      '<button type="button" class="ws-btn" data-tab="lich">' + ic("history") + " " + esc(t("h2.history")) + "</button></div>" +
      '<div class="h2-body"></div></div>';
    document.body.appendChild(lop);
    S.lop = lop;
    lop.querySelector("[data-dong]").onclick = dong;
    lop.addEventListener("click", function (e) { if (e.target === lop) dong(); });
    lop.querySelector('[data-tab="cai"]').onclick = function () { batDau(); };
    lop.querySelector('[data-tab="lich"]').onclick = function () { veLichSu(); };
    batDau();
  }

  /** Mở hộp: có lượt đang chạy cho trợ lý này thì vào thẳng màn tiến độ, không thì màn cài đặt. */
  async function batDau() {
    var b = than(); if (!b) return;
    b.innerHTML = '<div class="h2-muted">' + esc(t("h2.loading")) + "</div>";
    try {
      var st = await getJ("/harness/trang-thai?slug=" + encodeURIComponent(S.item.slug) + "&brain=" + encodeURIComponent(S.brain));
      if (st && st.dang_chay && st.run_id === st.dang_chay && st.trang_thai === "dang_chay") return veTienDo(st.run_id);
    } catch (e) { /* không hỏi được thì cứ vào màn cài đặt */ }
    veCaiDat();
  }

  function thamSo() {
    var b = than(); if (!b) return {};
    var chon = [].slice.call(b.querySelectorAll(".h2-de input:checked")).map(function (x) { return x.value; });
    var tay = (b.querySelector("#h2DeTay") || {}).value || "";
    var nao = (b.querySelector("#h2Nao") || {}).value || "";
    var cd = b.querySelector('input[name="h2CheDo"]:checked');
    return {
      brain: S.brain, slug: S.item.slug, k: Number((b.querySelector("#h2K") || {}).value || 1),
      che_do: cd ? cd.value : "song_song", de_chon: chon,
      de_tay: tay.split("\n").map(function (x) { return x.trim(); }).filter(Boolean),
      nao_cai_tien: nao ? { provider: nao } : null,
    };
  }

  async function veCaiDat(truoc) {
    var b = than(); if (!b) return;
    var d = truoc;
    if (!d) {
      b.innerHTML = '<div class="h2-muted">' + esc(t("h2.loading")) + "</div>";
      try { d = await postJ("/harness/uoc-luong", { brain: S.brain, slug: S.item.slug, k: 1 }); }
      catch (e) { b.innerHTML = ""; return loi(String(e)); }
    }
    if (!d || !d.ok) { b.innerHTML = ""; return loi((d && d.error) || "?"); }
    var dangChon = {}; (d.de || []).forEach(function (x) { dangChon[x.id] = true; });
    var deHtml = (d.tat_ca_de || []).filter(function (x) { return x.nguon !== "tay"; }).map(function (x) {
      return '<label class="h2-de"><input type="checkbox" value="' + esc(x.id) + '"' + (dangChon[x.id] ? " checked" : "") + ">" +
        '<span><b>' + esc(x.dau_vao.slice(0, 160)) + "</b>" + (x.luc ? '<small class="h2-muted"> ' + esc(x.luc) + "</small>" : "") +
        (x.co_dap_an ? ' <small class="h2-tag">' + esc(t("h2.has_answer")) + "</small>" : "") + "</span></label>";
    }).join("") || '<div class="h2-muted">' + esc(t("h2.no_tasks")) + "</div>";
    var naoHtml = '<option value="">' + esc(t("h2.brain_default")) + " (" + esc((d.spec_cai_tien || {}).provider || "") + ")</option>" +
      (d.lua_chon_nao || []).map(function (x) { return '<option value="' + esc(x.provider) + '">' + esc(x.provider) + "</option>"; }).join("");
    var hoTro = [];
    ["chay", "cai_tien"].forEach(function (k) { var h = (d.ho_tro || {})[k]; if (h && !h.ok) hoTro.push(h.ly_do); });
    b.innerHTML =
      '<p class="h2-intro">' + esc(t("h2.intro")) + "</p>" +
      (d.dang_chay ? '<div class="h2-warn">' + esc(t("h2.busy")) + "</div>" : "") +
      '<div class="h2-sec"><div class="h2-h">' + esc(t("h2.tasks")) + "</div>" + deHtml +
      '<textarea id="h2DeTay" class="h2-ta" rows="2" placeholder="' + esc(t("h2.task_manual")) + '"></textarea></div>' +
      '<div class="h2-sec h2-row">' +
        '<label>' + esc(t("h2.k")) + ' <select id="h2K"><option value="1">1</option><option value="2">2</option><option value="3">3</option></select></label>' +
        '<span class="h2-radio">' + esc(t("h2.mode")) +
          ' <label><input type="radio" name="h2CheDo" value="song_song" checked> ' + esc(t("h2.mode_par")) + "</label>" +
          ' <label><input type="radio" name="h2CheDo" value="noi_tiep"> ' + esc(t("h2.mode_seq")) + "</label></span>" +
        '<label>' + esc(t("h2.brain_improver")) + ' <select id="h2Nao">' + naoHtml + "</select></label>" +
      "</div>" +
      '<div class="h2-muted">' + esc(t("h2.brain_run", { p: (d.spec_chay || {}).provider || "" })) + " · " + esc(d.vo || "") + "</div>" +
      ((d.khong_sua || []).length ? '<div class="h2-muted">' + esc(t("h2.cannot_edit", { ds: d.khong_sua.map(function (x) { return x.skill + " (" + x.ly_do + ")"; }).join(", ") })) + "</div>" : "") +
      '<div class="h2-uoc" id="h2Uoc">' + esc(tomTatUoc(d.uoc)) + "</div>" +
      (d.canh_bao || []).map(function (c) { return '<div class="h2-warn">' + esc(c) + "</div>"; }).join("") +
      hoTro.map(function (c) { return '<div class="h2-err">' + esc(c) + "</div>"; }).join("") +
      '<div class="ws-acts"><button type="button" class="ws-btn primary" id="h2Chay"' + (hoTro.length || d.dang_chay ? " disabled" : "") + ">" +
        ic("play") + " " + esc(t("h2.run")) + "</button></div>";
    var capNhat = function () {
      if (S.uocHen) clearTimeout(S.uocHen);
      S.uocHen = setTimeout(async function () {
        try {
          var u = await postJ("/harness/uoc-luong", thamSo());
          var o = b.querySelector("#h2Uoc"); if (o && u && u.ok) o.textContent = tomTatUoc(u.uoc);
        } catch (e) { /* giữ ước lượng cũ */ }
      }, 400);
    };
    [].slice.call(b.querySelectorAll("input, select, textarea")).forEach(function (x) { x.addEventListener("change", capNhat); });
    b.querySelector("#h2Chay").onclick = async function () {
      var nut = this; nut.disabled = true;
      try {
        var r = await postJ("/harness/chay", thamSo());
        if (!r.ok) { nut.disabled = false; return loi(r.error || "?"); }
        veTienDo(r.run_id, true);
      } catch (e) { nut.disabled = false; loi(String(e)); }
    };
  }

  async function veTienDo(runId, moiBatDau) {
    var b = than(); if (!b) return;
    if (S.hen) { clearTimeout(S.hen); S.hen = null; }
    b.innerHTML = '<div class="h2-sec"><div class="h2-h">' + ic("loader") + " " + esc(t("h2.progress")) + "</div>" +
      (moiBatDau ? '<div class="h2-muted">' + esc(t("h2.started")) + "</div>" : "") +
      '<div id="h2Buoc" class="h2-buoc"></div><div id="h2Goi" class="h2-muted"></div></div>' +
      '<div class="ws-acts"><button type="button" class="ws-btn danger" id="h2Dung">' + ic("circle-stop") + " " + esc(t("h2.stop")) + "</button></div>";
    b.querySelector("#h2Dung").onclick = async function () {
      this.disabled = true;
      try { await postJ("/harness/bo", { run_id: runId }); } catch (e) { /* lượt hỏi kế tiếp sẽ thấy */ }
    };
    var hoi = async function () {
      if (!S.lop || !b.querySelector("#h2Buoc")) return;
      try {
        var st = await getJ("/harness/trang-thai?run_id=" + encodeURIComponent(runId));
        var o = b.querySelector("#h2Buoc"); if (o) o.textContent = st.buoc || "";
        var g = b.querySelector("#h2Goi"); if (g) g.textContent = t("h2.calls", { n: st.so_goi || 0, usd: usd(st.usd) });
        if (st.trang_thai && st.trang_thai !== "dang_chay") return veKetQua(runId, st);
      } catch (e) { /* mạng chập chờn: hỏi lại lượt sau */ }
      S.hen = setTimeout(hoi, 3000);
    };
    hoi();
  }

  function khoi(tieuDe, noiDung, mo) {
    return '<details class="h2-sec"' + (mo ? " open" : "") + "><summary class=\"h2-h\">" + esc(tieuDe) + "</summary>" + noiDung + "</details>";
  }

  async function veKetQua(runId, st) {
    var b = than(); if (!b) return;
    b.innerHTML = '<div class="h2-muted">' + esc(t("h2.loading")) + "</div>";
    var k;
    try { k = await getJ("/harness/ket-qua?run_id=" + encodeURIComponent(runId)); } catch (e) { b.innerHTML = ""; return loi(String(e)); }
    if (!k || !k.ok) {
      // Lượt dừng/lỗi trước khi có kết quả: nói đúng lý do, trợ lý không đổi gì.
      b.innerHTML = '<div class="h2-sec"><div class="h2-h">' + esc(nhanTrangThai((st || {}).trang_thai)) + "</div>" +
        '<div class="h2-muted">' + esc((st || {}).buoc || (k && k.error) || "") + "</div>" +
        '<div class="h2-muted">' + esc(t("h2.unchanged")) + "</div></div>";
      return;
    }
    var diff = k.diff || [];
    var tieuDe = k.giu_nguyen ? t("h2.keep") : t("h2.proposal", { n: diff.length });
    var stg = (k.stage || {})[k.chon] || {};
    var yd = k.y_dinh || {};
    var soYd = 0; Object.keys(yd).forEach(function (n) { soYd += (yd[n] || []).length; });
    var ydHtml = Object.keys(yd).sort().map(function (n) {
      return "<div><b>" + esc(n) + "</b><ul>" + (yd[n] || []).slice(0, 30).map(function (r) {
        return "<li>" + esc(r.de) + ": <code>" + esc(r.tool) + "</code> " + esc(JSON.stringify(r.args || {}).slice(0, 200)) + "</li>";
      }).join("") + "</ul></div>";
    }).join("");
    var kn = k.kinh_nghiem || {};
    b.innerHTML =
      '<div class="h2-sec"><div class="h2-h">' + esc(tieuDe) + ' <small class="h2-tag">' + esc(nhanTrangThai(k.trang_thai)) + "</small></div>" +
        (k.chan_an_toan ? '<div class="h2-warn">' + esc(t("h2.safety")) + ": " + esc(k.chan_an_toan) + "</div>" : "") +
        '<div class="h2-muted">' + esc(t("h2.chosen_label", { nhan: k.chon || "" })) + " · " + esc(t("h2.cost", { usd: usd(k.usd), n: k.so_goi_model || 0 })) + "</div>" +
        '<div class="h2-muted">' + esc(t("h2.why")) + ": " + esc(k.ly_do_chon || "") + "</div>" +
      "</div>" +
      (diff.length ? khoi(t("h2.diff"), diff.map(function (f) {
        return '<div class="h2-file"><b>' + esc(f.file) + "</b><pre class=\"h2-pre\">" + esc(f.diff) + "</pre></div>";
      }).join(""), true) : "") +
      (stg.notes ? khoi(t("h2.notes"), '<pre class="h2-pre">' + esc(stg.notes) + "</pre>") : "") +
      (k.edits ? khoi(t("h2.edits"), '<pre class="h2-pre">' + esc(k.edits) + "</pre>") : "") +
      (kn.lesson ? khoi(t("h2.lesson"), '<div class="h2-muted">' + esc(kn.cue || "") + "</div><div>" + esc(kn.lesson) +
        '</div><div class="h2-muted">' + esc(kn.evidence || "") + " · " + esc(kn.confidence || "") + "</div>") : "") +
      khoi(t("h2.intents", { n: soYd }), ydHtml || '<div class="h2-muted">-</div>') +
      khoi(t("h2.scores"), dongDiem(k.diem).map(function (x) { return "<div>" + esc(x) + "</div>"; }).join("") || "-") +
      '<div class="ws-acts" id="h2Nut"></div>';
    var nut = b.querySelector("#h2Nut");
    if (k.trang_thai === "xong" && !k.giu_nguyen) {
      nut.innerHTML = '<button type="button" class="ws-btn primary" id="h2ApDung">' + ic("check") + " " + esc(t("h2.apply")) + "</button>" +
        '<button type="button" class="ws-btn" id="h2Bo">' + ic("trash-2") + " " + esc(t("h2.discard")) + "</button>";
      nut.querySelector("#h2ApDung").onclick = async function () {
        if (!confirm(t("h2.confirm_apply"))) return;
        this.disabled = true;
        var r = await postJ("/harness/ap-dung", { run_id: runId });
        if (!r.ok) { this.disabled = false; return loi(r.error || "?"); }
        veKetQua(runId);
      };
      nut.querySelector("#h2Bo").onclick = async function () {
        this.disabled = true;
        var r = await postJ("/harness/bo", { run_id: runId });
        if (!r.ok) { this.disabled = false; return loi(r.error || "?"); }
        veKetQua(runId);
      };
    } else if (k.trang_thai === "da_ap_dung") {
      nut.innerHTML = '<button type="button" class="ws-btn" id="h2HoanTac">' + ic("undo-2") + " " + esc(t("h2.undo")) + "</button>";
      nut.querySelector("#h2HoanTac").onclick = async function () {
        if (!confirm(t("h2.confirm_undo"))) return;
        this.disabled = true;
        var r = await postJ("/harness/hoan-tac", { run_id: runId });
        if (!r.ok) { this.disabled = false; return loi(r.error || "?"); }
        veKetQua(runId);
      };
    }
  }

  async function veLichSu() {
    var b = than(); if (!b) return;
    if (S.hen) { clearTimeout(S.hen); S.hen = null; }
    b.innerHTML = '<div class="h2-muted">' + esc(t("h2.loading")) + "</div>";
    var r;
    try { r = await getJ("/harness/lich-su?slug=" + encodeURIComponent(S.item.slug) + "&brain=" + encodeURIComponent(S.brain)); }
    catch (e) { b.innerHTML = ""; return loi(String(e)); }
    var ds = (r && r.lan) || [];
    b.innerHTML = '<div class="h2-sec"><div class="h2-h">' + esc(t("h2.history")) + "</div>" + (ds.length ? ds.map(function (x) {
      return '<button type="button" class="h2-lan" data-run="' + esc(x.run_id) + '"><b>' + esc(x.bat_dau || x.run_id) + "</b> · " +
        esc(nhanTrangThai(x.trang_thai)) + " · k=" + esc(x.k) + " · " + esc(x.so_de) + " " + esc(t("h2.tasks_short")) +
        (x.usd != null ? " · " + esc(usd(x.usd)) + " USD" : "") + "</button>";
    }).join("") : '<div class="h2-muted">' + esc(t("h2.no_history")) + "</div>") + "</div>";
    [].slice.call(b.querySelectorAll("[data-run]")).forEach(function (n) {
      n.onclick = function () {
        var x = ds.find(function (y) { return y.run_id === n.dataset.run; }) || {};
        if (x.trang_thai === "dang_chay") veTienDo(x.run_id); else veKetQua(x.run_id, x);
      };
    });
  }

  W.JavisHarness2 = { mo: mo, dong: dong, nhanTrangThai: nhanTrangThai, tomTatUoc: tomTatUoc, dongDiem: dongDiem };
})();
