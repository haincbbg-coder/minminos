// thu-tu-dung.js - phần "Thứ tự dùng" của trang Bộ não AI (26.10.309).
//
// Một danh sách các nhà ĐÃ đăng nhập / kết nối: thẻ trên cùng là MAIN, sau đó Dự phòng 1, 2...
// Chat, việc nền và Telegram dùng chung thứ tự này. Mỗi thẻ có chip model và chip Effort riêng;
// thẻ API có danh sách key đánh số. Kéo thẻ để đổi thứ tự (điện thoại: giữ nút sáu chấm hoặc
// nhấn giữ thẻ), nút Đảo đổi MAIN với Dự phòng 1.
//
// Dữ liệu do server tính sẵn (`model.thu_tu_view` của GET /settings); trang không tự suy. Lưu đi
// qua POST /settings mục model: {thu_tu}, {the}, {khoa}, {auxiliary.reasoning}.
//
// Bảng chọn: máy tính là popover gắn vào <body> (position: fixed) nên thẻ kế tiếp không che được;
// điện thoại (<= 600px) là bảng trượt từ đáy có tiêu đề và nút đóng. Không bao giờ dùng em dash.
(function () {
  "use strict";

  const T = (k, v) => (window.t ? window.t(k, v) : k);
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  const IC = (n, o) => (window.ic ? window.ic(n, o) : "");
  const EFFORT = [["off", "models.r_off"], ["low", "models.r_low"], ["medium", "models.r_med"],
                  ["high", "models.r_high"], ["xhigh", "models.r_xhigh"], ["ultra", "models.r_ultra"]];
  const effortNhan = (v) => T((EFFORT.find((x) => x[0] === v) || EFFORT[0])[1]);
  const laDienThoai = () => window.matchMedia && window.matchMedia("(max-width: 600px)").matches;
  const gio = (epoch) => {
    if (!epoch) return "";
    const d = new Date(epoch * 1000);
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  };
  const ngan = (m) => (m || "").split("/").pop().replace(/^(claude-|gpt-)/, "") || T("models.tt_model_mac_dinh");

  // ---------------------------------------------------------------- bảng chọn (popover / bảng trượt)
  let _dong = null;
  function dongMenu() { if (_dong) { const f = _dong; _dong = null; f(); } }

  /** Mở bảng chọn gắn với `neo`. items = [{v, nhan, phu}], chon = giá trị đang chọn. */
  function moMenu(neo, tieuDe, items, chon, onPick) {
    dongMenu();
    const hang = items.map((it) => `<button type="button" class="tt-mn-hang ${it.v === chon ? "on" : ""}" data-v="${esc(it.v)}">`
      + `<span class="tt-mn-tick">${it.v === chon ? IC("check") : ""}</span><span class="tt-mn-chu">${esc(it.nhan)}`
      + (it.phu ? `<small>${esc(it.phu)}</small>` : "") + `</span></button>`).join("");
    const nen = document.createElement("div");
    const hop = document.createElement("div");
    if (laDienThoai()) {
      nen.className = "tt-sheet-nen";
      hop.className = "tt-sheet";
      hop.setAttribute("role", "dialog");
      hop.innerHTML = `<div class="tt-sheet-dau"><b>${esc(tieuDe)}</b>`
        + `<button type="button" class="tt-sheet-x" aria-label="${esc(T("models.tt_dong"))}">${IC("x")}</button></div>`
        + `<div class="tt-sheet-ds">${hang}</div>`;
      document.body.appendChild(nen);
      document.body.appendChild(hop);
    } else {
      hop.className = "tt-pop";
      hop.setAttribute("role", "menu");
      hop.innerHTML = hang;
      document.body.appendChild(hop);
      const r = neo.getBoundingClientRect();
      const cao = hop.offsetHeight;
      const duoi = window.innerHeight - r.bottom;
      // Mở lên trên như khung chat; chỉ lật xuống khi phía trên không đủ chỗ.
      const top = (r.top > cao + 12 || r.top > duoi) ? Math.max(8, r.top - cao - 6) : r.bottom + 6;
      hop.style.top = top + "px";
      hop.style.left = Math.max(8, Math.min(r.left, window.innerWidth - hop.offsetWidth - 8)) + "px";
    }
    const ngoai = (e) => { if (!hop.contains(e.target) && e.target !== neo && !neo.contains(e.target)) dongMenu(); };
    const phim = (e) => { if (e.key === "Escape") dongMenu(); };
    _dong = () => {
      hop.remove(); nen.remove();
      document.removeEventListener("pointerdown", ngoai, true);
      document.removeEventListener("keydown", phim);
    };
    setTimeout(() => document.addEventListener("pointerdown", ngoai, true), 0);
    document.addEventListener("keydown", phim);
    nen.onclick = dongMenu;
    const x = hop.querySelector(".tt-sheet-x");
    if (x) x.onclick = dongMenu;
    hop.querySelectorAll(".tt-mn-hang").forEach((b) => b.onclick = () => { const v = b.dataset.v; dongMenu(); onPick(v); });
  }

  function menuEffort(neo, ten, chon, onPick) {
    moMenu(neo, T("models.tt_effort_title", { ten }), EFFORT.map(([v, k]) => ({ v, nhan: T(k) })), chon, onPick);
  }

  // ---------------------------------------------------------------- vẽ
  /**
   * ctx = {providers, view, save(patch) -> Promise, moModel(pid, cur, luu), veLai()}
   */
  function ve(el, ctx) {
    const v = ctx.view || {};
    const ds = v.thu_tu || [];
    const pdef = (id) => (ctx.providers || []).find((p) => p.id === id) || { id, label: id };
    if (!ds.length) { el.innerHTML = `<div class="tt-trong">${esc(T("models.tt_empty"))}</div>`; return; }

    const theHtml = (pid, i) => {
      const p = pdef(pid);
      const the = (v.the || {})[pid] || {};
      const het = (v.het_luot || {})[pid];
      const dangDung = v.dang_dung === pid && i > 0;
      const nhan = i === 0 ? T("models.tt_main") : T("models.tt_dp", { n: i });
      const khoa = (v.khoa || {})[pid];
      return `<div class="tt-the ${i === 0 ? "main" : ""}" data-prov="${esc(pid)}">
        <div class="tt-dau">
          <span class="tt-keo" role="button" tabindex="0" aria-label="${esc(T("models.tt_keo"))}" title="${esc(T("models.tt_keo"))}">⋮⋮</span>
          <span class="tt-ten">${esc(p.label)}</span>
          ${dangDung ? `<span class="tt-tag ok">${esc(T("models.tt_dang_dung"))}</span>` : ""}
          ${het ? `<span class="tt-tag warn">${esc(het > 1 ? T("models.tt_het", { gio: gio(het) }) : T("models.tt_het_khong_gio"))}</span>` : ""}
        </div>
        <div class="tt-chips">
          <span class="tt-nhan ${i === 0 ? "main" : ""}">${esc(nhan)}</span>
          <button type="button" class="tt-chip" data-chip="model"><span class="tt-cham"></span>${esc(ngan(the.model))}${IC("chevron-down")}</button>
          <button type="button" class="tt-chip" data-chip="effort">${esc(T("models.tt_effort"))}: ${esc(effortNhan(the.reasoning))}${IC("chevron-down")}</button>
        </div>
        ${khoa ? khoaHtml(pid, khoa) : ""}
      </div>`;
    };
    const khoaHtml = (pid, ds2) => `<div class="tt-khoa" data-khoa="${esc(pid)}">
        <ol class="tt-khoa-ds">${ds2.map((k, i) => `
          <li class="tt-k ${k.dang_dung ? "on" : ""} ${k.bat ? "" : "tat"}" data-id="${esc(k.id)}">
            <div class="tt-k-dong">
              <span class="tt-k-so">${i + 1}</span>
              <span class="tt-k-ten">${esc(k.ten || T("models.tt_khoa_n", { n: i + 1 }))} <code>${esc(k.duoi)}</code></span>
              <span class="tt-k-tt">${k.dang_dung ? esc(T("models.tt_khoa_dung"))
                : !k.bat ? esc(T("models.tt_khoa_tat"))
                : k.nghi_den ? esc(T("models.tt_khoa_nghi", { gio: gio(k.nghi_den) })) : ""}</span>
              <button type="button" class="tt-k-nut" data-k="len" ${i === 0 ? "disabled" : ""} aria-label="${esc(T("models.tt_len"))}">${IC("chevron-up")}</button>
              <button type="button" class="tt-k-nut" data-k="xuong" ${i === ds2.length - 1 ? "disabled" : ""} aria-label="${esc(T("models.tt_xuong"))}">${IC("chevron-down")}</button>
              <button type="button" class="tt-k-nut" data-k="sua" aria-label="${esc(T("models.tt_sua"))}">${IC("ellipsis")}</button>
            </div>
            <div class="tt-k-sua" hidden>
              <input class="js-input" data-f="ten" maxlength="40" value="${esc(k.ten)}" placeholder="${esc(T("models.tt_ten_ph"))}">
              <input class="js-input" data-f="khoa" type="password" autocomplete="off" placeholder="${esc(T("models.tt_doi_key_ph"))}">
              <div class="tt-k-hang">
                <button type="button" class="gcard-btn" data-k="luu">${esc(T("models.tt_luu"))}</button>
                <button type="button" class="gcard-btn ghost" data-k="bat">${esc(k.bat ? T("models.tt_tat") : T("models.tt_bat"))}</button>
                <button type="button" class="gcard-btn ghost" data-k="go">${esc(T("models.tt_go"))}</button>
              </div>
            </div>
          </li>`).join("")}</ol>
        <button type="button" class="tt-them" data-k="mo-them">+ ${esc(T("models.tt_them_key"))}</button>
        <div class="tt-k-sua tt-k-moi" hidden>
          <input class="js-input" data-f="ten" maxlength="40" placeholder="${esc(T("models.tt_ten_ph"))}">
          <input class="js-input" data-f="khoa" type="password" autocomplete="off" placeholder="${esc(T("models.tt_key_ph"))}">
          <div class="tt-k-hang"><button type="button" class="gcard-btn" data-k="them">${esc(T("models.tt_them"))}</button></div>
        </div>
        <div class="tt-k-note">${esc(T("models.tt_khoa_note"))}</div>
      </div>`;

    let html = "";
    ds.forEach((pid, i) => {
      html += theHtml(pid, i);
      if (i === 0 && ds.length > 1) {
        html += `<button type="button" class="tt-dao" data-dao="0">${IC("arrow-up-down")} ${esc(T("models.tt_dao"))}</button>`;
      }
    });
    el.innerHTML = `<div class="tt-ds">${html}</div><div class="tt-note">${esc(T("models.tt_note"))}</div>`;

    // ---- chip model / Effort ----
    el.querySelectorAll(".tt-the").forEach((card) => {
      const pid = card.dataset.prov;
      const p = pdef(pid);
      const the = (v.the || {})[pid] || {};
      card.querySelector('[data-chip="model"]').onclick = () => ctx.moModel(pid, the.model || "",
        (mod) => ctx.save({ the: { provider: pid, model: mod } }));
      const ce = card.querySelector('[data-chip="effort"]');
      ce.onclick = () => menuEffort(ce, p.label, the.reasoning || "off",
        (r) => ctx.save({ the: { provider: pid, reasoning: r } }));
    });
    const dao = el.querySelector(".tt-dao");
    if (dao) dao.onclick = () => { const o = ds.slice(); [o[0], o[1]] = [o[1], o[0]]; ctx.save({ thu_tu: o }); };

    // ---- danh sách key ----
    el.querySelectorAll(".tt-khoa").forEach((box) => {
      const pid = box.dataset.khoa;
      const goc = ((v.khoa || {})[pid] || []).map((k) => ({ id: k.id, ten: k.ten, bat: k.bat }));
      const luu = (items) => ctx.save({ khoa: { provider: pid, items } });
      box.querySelectorAll("li.tt-k").forEach((li, i) => {
        const id = li.dataset.id;
        const sua = li.querySelector(".tt-k-sua");
        li.querySelectorAll("[data-k]").forEach((b) => b.onclick = () => {
          const k = b.dataset.k;
          const ds2 = goc.map((x) => ({ ...x }));
          if (k === "sua") { sua.hidden = !sua.hidden; return; }
          if (k === "len" && i > 0) { [ds2[i - 1], ds2[i]] = [ds2[i], ds2[i - 1]]; return luu(ds2); }
          if (k === "xuong" && i < ds2.length - 1) { [ds2[i + 1], ds2[i]] = [ds2[i], ds2[i + 1]]; return luu(ds2); }
          if (k === "bat") { ds2[i].bat = !ds2[i].bat; return luu(ds2); }
          if (k === "go") {
            if (!window.confirm(T("models.tt_go_hoi", { ten: pdef(pid).label }))) return;
            return luu(ds2.filter((x) => x.id !== id));
          }
          if (k === "luu") {
            ds2[i].ten = (sua.querySelector('[data-f="ten"]').value || "").trim();
            const moi = (sua.querySelector('[data-f="khoa"]').value || "").trim();
            if (moi) ds2[i].khoa = moi;
            return luu(ds2);
          }
        });
      });
      const moi = box.querySelector(".tt-k-moi");
      box.querySelector('[data-k="mo-them"]').onclick = () => {
        moi.hidden = !moi.hidden;
        if (!moi.hidden) moi.querySelector('[data-f="khoa"]').focus();
      };
      moi.querySelector('[data-k="them"]').onclick = () => {
        const khoa = (moi.querySelector('[data-f="khoa"]').value || "").trim();
        if (!khoa) { moi.querySelector('[data-f="khoa"]').focus(); return; }
        luu(goc.concat([{ id: "", ten: (moi.querySelector('[data-f="ten"]').value || "").trim(), bat: true, khoa }]));
      };
    });

    ganKeoTha(el.querySelector(".tt-ds"), (o) => ctx.save({ thu_tu: o }));
  }

  // ---------------------------------------------------------------- kéo thả
  // Chuột / bút: giữ nút sáu chấm rồi kéo. Cảm ứng: giữ nút sáu chấm, hoặc nhấn giữ đầu thẻ ~350ms
  // (nhấn rồi vuốt ngay thì là cuộn trang, không phải kéo).
  function ganKeoTha(list, onXong) {
    if (!list) return;
    const theCua = (x) => x && x.closest && x.closest(".tt-the");
    let keo = null, hen = null, x0 = 0, y0 = 0;

    const batDau = (card, e) => {
      keo = { card, id: e.pointerId };
      card.classList.add("dang-keo");
      list.classList.add("dang-keo");
      try { card.setPointerCapture(e.pointerId); } catch (err) {}
      if (navigator.vibrate) { try { navigator.vibrate(10); } catch (err) {} }
    };
    const ketThuc = () => {
      clearTimeout(hen); hen = null;
      if (!keo) return;
      const card = keo.card;
      keo = null;
      card.classList.remove("dang-keo");
      list.classList.remove("dang-keo");
      const o = [...list.querySelectorAll(".tt-the")].map((c) => c.dataset.prov);
      if (o.join() !== list.dataset.goc) onXong(o);
    };
    list.dataset.goc = [...list.querySelectorAll(".tt-the")].map((c) => c.dataset.prov).join();

    list.addEventListener("pointerdown", (e) => {
      const card = theCua(e.target);
      if (!card || e.button > 0) return;
      if (e.target.closest(".tt-keo")) { e.preventDefault(); batDau(card, e); return; }
      if (e.pointerType === "touch" && e.target.closest(".tt-dau")) {
        x0 = e.clientX; y0 = e.clientY;
        hen = setTimeout(() => batDau(card, e), 350);
      }
    });
    list.addEventListener("pointermove", (e) => {
      if (hen && (Math.abs(e.clientX - x0) > 8 || Math.abs(e.clientY - y0) > 8)) { clearTimeout(hen); hen = null; }
      if (!keo || e.pointerId !== keo.id) return;
      e.preventDefault();
      const cards = [...list.querySelectorAll(".tt-the")].filter((c) => c !== keo.card);
      const sau = cards.find((c) => { const r = c.getBoundingClientRect(); return e.clientY < r.top + r.height / 2; });
      const dao = list.querySelector(".tt-dao");
      if (dao) dao.remove();          // nút Đảo về đúng chỗ sau khi vẽ lại
      if (sau) list.insertBefore(keo.card, sau); else list.appendChild(keo.card);
    });
    // Đang kéo trên cảm ứng: chặn trang cuộn theo ngón tay.
    list.addEventListener("touchmove", (e) => { if (keo) e.preventDefault(); }, { passive: false });
    list.addEventListener("pointerup", ketThuc);
    list.addEventListener("pointercancel", ketThuc);
    list.querySelectorAll(".tt-keo").forEach((g) => g.addEventListener("keydown", (e) => {
      // Bàn phím: mũi tên lên/xuống đổi chỗ thẻ đang chọn.
      if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
      e.preventDefault();
      const o = list.dataset.goc.split(",");
      const i = o.indexOf(theCua(g).dataset.prov), j = i + (e.key === "ArrowUp" ? -1 : 1);
      if (j < 0 || j >= o.length) return;
      [o[i], o[j]] = [o[j], o[i]];
      onXong(o);
    }));
  }

  window.MinMinThuTu = { ve, moMenu, menuEffort, dongMenu, effortNhan, gio };
})();
