/* Chợ chia sẻ MinMin (26.10.92): gửi agent/skill/workflow sang MinMin khác và nhận về.
 *
 * Ba thẻ trong một hộp thoại:
 *   Gửi đi   tạo link có hạn, mã ngắn XXXXX-XXXXX@ten-mien, QR, PIN, dùng một lần; chép,
 *            gửi email (mở ứng dụng mail của máy) hoặc chép lời nhắn để dán Zalo.
 *   Nhận về  dán link / mã, hoặc chọn file .zip -> XEM TRƯỚC (ai gửi, đã xác minh chưa, có gì,
 *            cảnh báo) -> chọn mục -> cài. Không có đường cài mù.
 *   Đã nhận  các mục đã nhập từ người khác, đang chạy chế độ an toàn hay đã được tin tưởng.
 *
 * Trang nhận công khai của người gửi chuyển người xem về MinMin của họ kèm `?nhap=<link>`; file
 * này bắt tham số đó lúc mở app và mở thẳng thẻ Nhận về.
 *
 * Mọi chữ hiện ra đi qua window.t (khoá "cs.*" trong i18n). Không có chữ tiếng Việt nhúng cứng.
 */
(function () {
  "use strict";
  function t(k, b) { return window.t ? window.t(k, b) : k; }
  const esc = (x) => String(x == null ? "" : x).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const KINDS = [["workflow", "workflows", "workflows"], ["agent", "agents", "agents"], ["skill", "skills", "skills"]];
  const kindName = (k) => (k === "agent" ? t("cs.kind_agent") : k === "skill" ? t("cs.kind_skill") : t("cs.kind_workflow"));
  // Khoá viết TRỌN tên để test i18n quét thấy (không ghép chuỗi khoá).
  const xmNhan = (st) => ({
    da_xac_minh: t("cs.xm_da_xac_minh"), khoa_doi: t("cs.xm_khoa_doi"), chua_doi_chieu: t("cs.xm_chua_doi_chieu"),
    chi_chu_ky: t("cs.xm_chi_chu_ky"), gia_mao: t("cs.xm_gia_mao"),
  }[st] || t("cs.xm_khong_ky"));

  function css() {
    if (document.getElementById("csStyle")) return;
    const s = document.createElement("style");
    s.id = "csStyle";
    s.textContent = `
.cs-ov{position:fixed;inset:0;z-index:99999;background:var(--mm-scrim,rgba(0,0,0,.55));display:flex;align-items:center;justify-content:center;padding:16px}
.cs-box{background:var(--mm-panel,#181822);color:var(--mm-text,#f3f3fb);font-family:var(--mm-font,inherit);border-radius:20px;box-shadow:var(--mm-out);width:min(620px,100%);max-height:92vh;display:flex;flex-direction:column;overflow:hidden}
.cs-head{display:flex;align-items:center;gap:8px;padding:14px 16px 0}
.cs-head b{flex:1;font-size:16px}
.cs-tabs{display:flex;gap:6px;padding:12px 16px 4px}
.cs-tab{flex:1;border:0;border-radius:12px;padding:9px 6px;font:inherit;font-weight:600;cursor:pointer;color:var(--mm-muted);background:var(--mm-panel);box-shadow:var(--mm-out-xs)}
.cs-tab[aria-selected="true"]{color:var(--mm-text);box-shadow:var(--mm-in-sm)}
.cs-body{padding:12px 16px 16px;overflow:auto;display:flex;flex-direction:column;gap:12px}
.cs-card{border-radius:14px;padding:12px;box-shadow:var(--mm-in-sm);display:flex;flex-direction:column;gap:8px}
.cs-row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.cs-dim{color:var(--mm-dim);font-size:12px}
.cs-in{flex:1;min-width:120px;font:inherit;color:var(--mm-text);background:var(--mm-field);border:0;border-radius:10px;padding:9px 10px;box-shadow:var(--mm-in-sm)}
.cs-btn{border:0;border-radius:10px;padding:8px 12px;font:inherit;font-weight:600;cursor:pointer;color:var(--mm-text);background:var(--mm-panel);box-shadow:var(--mm-out-xs)}
.cs-btn.p{background:var(--mm-primary);color:var(--mm-on-brand);box-shadow:var(--mm-primary-shadow)}
.cs-btn:disabled{opacity:.5;cursor:default}
.cs-list{max-height:220px;overflow:auto;display:flex;flex-direction:column;gap:2px}
.cs-list label{display:flex;gap:8px;align-items:flex-start;padding:4px 2px;cursor:pointer}
.cs-list small{display:block;color:var(--mm-dim)}
.cs-chip{font-size:11px;font-weight:700;border-radius:7px;padding:1px 7px;box-shadow:var(--mm-in-sm);color:var(--mm-link);white-space:nowrap}
.cs-badge{border-radius:12px;padding:10px 12px;font-size:13px;line-height:1.45}
.cs-badge.ok{background:color-mix(in srgb,var(--mm-ok) 14%,transparent);color:var(--mm-ok)}
.cs-badge.warn{background:color-mix(in srgb,var(--mm-warn) 16%,transparent);color:var(--mm-warn)}
.cs-badge.bad{background:color-mix(in srgb,var(--mm-bad) 16%,transparent);color:var(--mm-bad)}
.cs-code{font:600 14px ui-monospace,Menlo,monospace;overflow-wrap:anywhere}
.cs-qr{width:150px;height:150px;border-radius:10px;background:#fff;align-self:center}
.cs-msg{font-size:12px;min-height:1em;color:var(--mm-muted)}
.cs-link{display:flex;flex-direction:column;gap:6px;padding:8px 0;border-top:1px solid var(--mm-line)}
`;
    document.head.appendChild(s);
  }

  async function getJson(url, opt) {
    try { const r = await fetch(url, opt); return await r.json(); } catch (e) { return null; }
  }
  async function post(url, fields, file) {
    const fd = new FormData();
    Object.entries(fields || {}).forEach(([k, v]) => fd.append(k, v));
    if (file) fd.append("goi", file);
    return getJson(url, { method: "POST", body: fd });
  }
  async function chep(txt, msgEl) {
    try { await navigator.clipboard.writeText(txt); if (msgEl) msgEl.textContent = t("cs.copied"); }
    catch (e) { window.prompt("", txt); }
  }

  function mo(opts) {
    opts = opts || {};
    const brain = opts.brain || (window.JavisBrains && window.JavisBrains.current && window.JavisBrains.current()) || "brain";
    css();
    const ov = document.createElement("div");
    ov.className = "cs-ov";
    ov.innerHTML = `<div class="cs-box" role="dialog" aria-modal="true">
      <div class="cs-head"><b>${esc(t("cs.title"))}</b><button class="cs-btn" data-x>${esc(t("cs.close"))}</button></div>
      <div class="cs-tabs" role="tablist">
        <button class="cs-tab" data-tab="gui" role="tab">${esc(t("cs.tab_send"))}</button>
        <button class="cs-tab" data-tab="nhan" role="tab">${esc(t("cs.tab_receive"))}</button>
        <button class="cs-tab" data-tab="da" role="tab">${esc(t("cs.tab_received"))}</button>
      </div>
      <div class="cs-body"></div></div>`;
    document.body.appendChild(ov);
    const body = ov.querySelector(".cs-body");
    const dong = () => { ov.remove(); document.removeEventListener("keydown", phim); };
    const phim = (e) => { if (e.key === "Escape") dong(); };
    document.addEventListener("keydown", phim);
    ov.querySelector("[data-x]").onclick = dong;
    ov.addEventListener("click", (e) => { if (e.target === ov) dong(); });
    const chon = (tab) => {
      ov.querySelectorAll(".cs-tab").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
      body.innerHTML = "";
      if (tab === "gui") theGui(body, brain);
      else if (tab === "nhan") theNhan(body, brain, opts.nguon || "", opts.capNhat || null);
      else theDaNhan(body, brain, (x) => { opts.capNhat = x; chon("nhan"); });
      opts.nguon = ""; opts.capNhat = null;
    };
    ov.querySelectorAll(".cs-tab").forEach((b) => (b.onclick = () => chon(b.dataset.tab)));
    chon(opts.tab || "gui");
  }

  // ───────────── Gửi đi ─────────────
  async function theGui(body, brain) {
    body.innerHTML = `
      <div class="cs-card"><div class="cs-row"><span class="cs-dim">${esc(t("cs.me_label"))}</span>
        <input class="cs-in" id="csTen" maxlength="60" placeholder="${esc(t("cs.me_ph"))}">
        <button class="cs-btn" id="csTenLuu">${esc(t("cs.save"))}</button></div>
        <div class="cs-dim" id="csVanTay"></div></div>
      <div class="cs-card">
        <div class="cs-row" id="csKinds"></div>
        <div class="cs-list" id="csList"></div>
        <label class="cs-row"><input type="checkbox" id="csAll"> ${esc(t("cs.all"))}</label>
      </div>
      <div class="cs-card">
        <div class="cs-row"><span class="cs-dim">${esc(t("cs.valid"))}</span>
          <select class="cs-in" id="csDays" style="flex:0 0 auto"><option value="7">7 ${esc(t("cs.days"))}</option><option value="30">30 ${esc(t("cs.days"))}</option><option value="90">90 ${esc(t("cs.days"))}</option></select>
          <label class="cs-row"><input type="checkbox" id="csOnce"> ${esc(t("cs.once"))}</label></div>
        <div class="cs-row"><input class="cs-in" id="csPin" maxlength="12" autocomplete="off" placeholder="${esc(t("cs.pin_ph"))}">
          <input class="cs-in" id="csNhan" maxlength="120" placeholder="${esc(t("cs.label_ph"))}"></div>
        <button class="cs-btn p" id="csMake">${esc(t("cs.make"))}</button>
        <div class="cs-msg" id="csMsg"></div>
      </div>
      <div id="csNew"></div>
      <div class="cs-card"><b>${esc(t("cs.active"))}</b><div id="csLinks"></div>
        <div class="cs-dim">${esc(t("cs.note"))}</div></div>`;
    const $ = (id) => body.querySelector("#" + id);
    getJson("/danh-tinh").then((j) => {
      if (!j) return;
      $("csTen").value = j.ten || "";
      $("csVanTay").textContent = t("cs.fingerprint", { vt: j.van_tay || "" });
    });
    $("csTenLuu").onclick = async () => {
      const j = await post("/danh-tinh", { ten: $("csTen").value });
      $("csMsg").textContent = j && j.ok ? t("cs.saved") : t("cs.failed");
    };
    let kind = "workflow";
    const daChon = { workflow: new Set(), agent: new Set(), skill: new Set() };
    $("csKinds").innerHTML = KINDS.map((k) => `<button class="cs-tab" data-k="${k[0]}">${esc(kindName(k[0]))}</button>`).join("");
    async function napDs() {
      $("csKinds").querySelectorAll("[data-k]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.k === kind)));
      const k = KINDS.find((x) => x[0] === kind);
      $("csList").textContent = "...";
      const j = await getJson("/" + k[1] + "?brain=" + encodeURIComponent(brain) + (kind === "agent" ? "&prompt=0" : ""));
      const arr = ((j && j[k[2]]) || []).filter((x) => !x.system && !x.is_system);
      $("csList").innerHTML = arr.length ? arr.map((x) => {
        const slug = x.slug || x.id || x.name;
        return `<label><input type="checkbox" value="${esc(slug)}" ${daChon[kind].has(slug) ? "checked" : ""}><span>${esc(x.name || slug)}<small>${esc(x.description || x.role || "")}</small></span></label>`;
      }).join("") : `<i class="cs-dim">${esc(t("cs.empty"))}</i>`;
      $("csList").querySelectorAll("input").forEach((i) => (i.onchange = () => { i.checked ? daChon[kind].add(i.value) : daChon[kind].delete(i.value); }));
    }
    $("csKinds").querySelectorAll("[data-k]").forEach((b) => (b.onclick = () => { kind = b.dataset.k; napDs(); }));
    napDs();

    function loiNhan(x) {
      const trang = location.origin + x.trang;
      return t("cs.invite_text", { link: trang, ma: x.ma + "@" + location.host });
    }
    function theLink(x, moi) {
      const trang = location.origin + x.trang;
      const ma = x.ma + "@" + location.host;
      const el = document.createElement("div");
      el.className = moi ? "cs-card" : "cs-link";
      el.innerHTML = `${moi ? `<b>${esc(t("cs.ready"))}</b>` : ""}
        <div class="cs-row"><span class="cs-code" style="flex:1">${esc(ma)}</span>
          ${x.co_pin ? `<span class="cs-chip">PIN</span>` : ""}
          ${x.toi_da ? `<span class="cs-chip">${esc(t("cs.uses", { n: x.tai || 0, max: x.toi_da }))}</span>` : `<span class="cs-dim">${esc(t("cs.downloads", { n: x.tai || 0 }))}</span>`}</div>
        ${x.nhan ? `<div class="cs-dim">${esc(x.nhan)}</div>` : ""}
        ${moi ? `<img class="cs-qr" alt="QR" src="${esc(x.trang)}/qr.svg">` : ""}
        <div class="cs-row">
          <button class="cs-btn" data-a="link">${esc(t("cs.copy_link"))}</button>
          <button class="cs-btn" data-a="ma">${esc(t("cs.copy_code"))}</button>
          <button class="cs-btn" data-a="mail">${esc(t("cs.email"))}</button>
          <button class="cs-btn" data-a="msg">${esc(t("cs.copy_msg"))}</button>
          ${moi ? "" : `<button class="cs-btn" data-a="qr">QR</button><button class="cs-btn" data-a="del">${esc(t("cs.revoke"))}</button>`}
        </div>
        <div class="cs-dim">${esc(t("cs.expires", { d: new Date(x.het_han * 1000).toLocaleDateString() }))}</div>`;
      el.querySelector('[data-a="link"]').onclick = () => chep(trang, $("csMsg"));
      el.querySelector('[data-a="ma"]').onclick = () => chep(ma, $("csMsg"));
      el.querySelector('[data-a="msg"]').onclick = () => chep(loiNhan(x), $("csMsg"));
      el.querySelector('[data-a="mail"]').onclick = () => {
        location.href = "mailto:?subject=" + encodeURIComponent(t("cs.email_subject")) + "&body=" + encodeURIComponent(loiNhan(x));
      };
      const qr = el.querySelector('[data-a="qr"]');
      if (qr) qr.onclick = () => {
        const cu = el.querySelector(".cs-qr");
        if (cu) { cu.remove(); return; }
        const img = document.createElement("img");
        img.className = "cs-qr"; img.alt = "QR"; img.src = x.trang + "/qr.svg";
        el.insertBefore(img, el.querySelector(".cs-row:last-of-type"));
      };
      const del = el.querySelector('[data-a="del"]');
      if (del) del.onclick = async () => {
        if (!window.confirm(t("cs.revoke_ask"))) return;
        await post("/brains/shares/revoke", { token: x.token });
        napLinks();
      };
      return el;
    }
    async function napLinks() {
      const j = await getJson("/brains/shares?brain=" + encodeURIComponent(brain));
      const box = $("csLinks"); box.innerHTML = "";
      const ds = ((j && j.shares) || []).filter((x) => x.con_han);
      if (!ds.length) box.innerHTML = `<i class="cs-dim">${esc(t("cs.no_links"))}</i>`;
      ds.forEach((x) => box.appendChild(theLink(x, false)));
    }
    $("csMake").onclick = async () => {
      const all = $("csAll").checked;
      const items = {}; let n = 0;
      Object.entries(daChon).forEach(([k, s]) => { if (s.size) { items[k] = [...s]; n += s.size; } });
      if (!all && !n) { $("csMsg").textContent = t("cs.pick"); return; }
      const f = { brain, days: $("csDays").value, nhan: $("csNhan").value, pin: $("csPin").value.trim(),
                  toi_da: $("csOnce").checked ? "1" : "0" };
      if (all) f.tat_ca = "1"; else f.items = JSON.stringify(items);
      $("csMake").disabled = true;
      const r = await post("/brains/share", f);
      $("csMake").disabled = false;
      if (!r || !r.ok) { $("csMsg").textContent = (r && r.error) || t("cs.failed"); return; }
      $("csMsg").textContent = "";
      $("csNew").innerHTML = "";
      $("csNew").appendChild(theLink({ token: r.token, trang: r.trang, ma: r.ma, het_han: r.het_han,
        co_pin: !!f.pin, toi_da: Number(f.toi_da), tai: 0, nhan: f.nhan }, true));
      $("csPin").value = "";
      napLinks();
    };
    napLinks();
  }

  // ───────────── Nhận về ─────────────
  const NHAN_XM = {
    da_xac_minh: "ok", khoa_doi: "warn", chua_doi_chieu: "warn", chi_chu_ky: "warn", khong_ky: "warn", gia_mao: "bad",
  };
  function theNhan(body, brain, nguon, capNhat) {
    body.innerHTML = `
      <div class="cs-card">
        <div class="cs-dim">${esc(t("cs.recv_hint"))}</div>
        <div class="cs-row"><input class="cs-in" id="csNguon" placeholder="${esc(t("cs.recv_ph"))}">
          <button class="cs-btn p" id="csXem">${esc(t("cs.preview"))}</button></div>
        <div class="cs-row" id="csPinRow" hidden><input class="cs-in" id="csPinNhan" maxlength="12" autocomplete="off" placeholder="${esc(t("cs.pin_enter"))}"></div>
        <div class="cs-row"><span class="cs-dim">${esc(t("cs.or_file"))}</span><input type="file" id="csFile" accept=".zip,application/zip"></div>
        <div class="cs-msg" id="csMsg"></div>
      </div>
      <div id="csXemTruoc"></div>`;
    const $ = (id) => body.querySelector("#" + id);
    $("csNguon").value = nguon || "";
    async function xem(file) {
      $("csMsg").textContent = t("cs.loading");
      $("csXem").disabled = true;
      const f = { to_brain: brain };
      if (capNhat) { f.td = capNhat.td; f.host_td = capNhat.host; }
      else if (!file) { f.nguon = $("csNguon").value.trim(); f.pin = $("csPinNhan").value.trim(); }
      const r = await post("/brains/import/xem", f, file);
      $("csXem").disabled = false;
      if (r && r.can_pin) {
        $("csPinRow").hidden = false; $("csPinNhan").focus();
        $("csMsg").textContent = r.error || t("cs.pin_need");
        return;
      }
      if (!r || !r.ok) { $("csMsg").textContent = (r && r.error) || t("cs.failed"); return; }
      $("csMsg").textContent = "";
      veXemTruoc(r);
      soiAi(r);
    }
    $("csXem").onclick = () => { if ($("csNguon").value.trim()) xem(null); };
    $("csNguon").addEventListener("keydown", (e) => { if (e.key === "Enter") $("csXem").click(); });
    $("csPinNhan").addEventListener("keydown", (e) => { if (e.key === "Enter") $("csXem").click(); });
    $("csFile").onchange = () => { const fl = $("csFile").files[0]; if (fl) xem(fl); };

    function veNguyCo(ds) {
      if (!ds.length) return `<div class="cs-badge ok">${esc(t("cs.scan_clean"))}</div>`;
      const cao = ds.filter((c) => c.muc === "cao").length;
      return `<div class="cs-badge ${cao ? "bad" : "warn"}"><b>${esc(cao ? t("cs.scan_high", { n: cao }) : t("cs.scan_mid", { n: ds.length }))}</b>
        ${ds.map((c) => `<div style="margin-top:6px"><b>${esc(c.loai)}</b> <span class="cs-dim">${esc(c.file)}, ${esc(t("cs.line", { n: c.dong }))}</span>
          <div class="cs-code" style="font-weight:400;font-size:12px;opacity:.85">${esc(c.trich)}</div></div>`).join("")}</div>`;
    }
    function veKetNoi(ds) {
      if (!ds.length) return "";
      const thieu = ds.filter((k) => k.trang_thai !== "da_co").length;
      const dong = (k) => {
        const tt = k.trang_thai === "da_co" ? `<span style="color:var(--mm-ok)">${esc(t("cs.conn_have"))}</span>`
          : k.trang_thai === "dang_tat" ? `<span style="color:var(--mm-warn)">${esc(t("cs.conn_off"))}</span>`
          : `<span style="color:var(--mm-bad)">${esc(t("cs.conn_missing"))}</span>`;
        return `<div style="margin-top:4px"><b>${esc(k.ten)}</b> ${tt}
          <span class="cs-dim">${esc(k.khai_bao ? t("cs.conn_declared") : t("cs.conn_guessed"))} · ${esc((k.o || []).join(", "))}</span></div>`;
      };
      return `<div class="cs-badge ${thieu ? "warn" : "ok"}"><b>${esc(thieu ? t("cs.conn_title_missing", { n: thieu }) : t("cs.conn_title_ok"))}</b>
        ${ds.map(dong).join("")}
        ${thieu ? `<div class="cs-dim" style="margin-top:6px">${esc(t("cs.conn_hint"))}</div>` : ""}</div>`;
    }
    async function soiAi(r) {
      const box = $("csXemTruoc").querySelector("#csAi");
      if (!box) return;
      const j = await post("/brains/import/soi-ai", { sha256: r.sha256 });
      if (!box.isConnected) return;
      if (!j || !j.ok) { box.className = "cs-badge warn"; box.textContent = t("cs.ai_failed", { e: (j && j.error) || "" }); return; }
      const a = j.ai || {};
      if (a.loi) { box.className = "cs-badge warn"; box.textContent = t("cs.ai_failed", { e: a.loi }); return; }
      const muc = a.muc_rui_ro === "cao" ? "bad" : a.muc_rui_ro === "thap" ? "ok" : "warn";
      const nhanMuc = a.muc_rui_ro === "cao" ? t("cs.ai_high") : a.muc_rui_ro === "thap" ? t("cs.ai_low") : t("cs.ai_mid");
      box.className = "cs-badge " + muc;
      box.innerHTML = `<b>${esc(nhanMuc)}</b><br>${esc(a.tom_tat || "")}
        ${(a.hanh_dong_ra_ngoai || []).length ? `<div style="margin-top:6px"><b>${esc(t("cs.ai_actions"))}</b>${a.hanh_dong_ra_ngoai.map((x) => `<div>• ${esc(x)}</div>`).join("")}</div>` : ""}
        ${(a.dang_ngo || []).length ? `<div style="margin-top:6px"><b>${esc(t("cs.ai_suspicious"))}</b>${a.dang_ngo.map((x) => `<div>• ${esc(x)}</div>`).join("")}</div>` : ""}
        <div class="cs-dim" style="margin-top:6px">${esc(t("cs.ai_note"))}</div>`;
    }
    function veCapNhat(it, cn) {
      if (!it.da_co) return "";
      if (!cn) return ` <span class="cs-dim">(${esc(t("cs.exists"))})</span>`;
      if (!cn.co_ban_moi) return ` <span class="cs-dim">(${esc(t("cs.upd_same"))})</span>`;
      const them = (cn.khac || []).reduce((a, k) => a + (k.them || 0), 0);
      const bot = (cn.khac || []).reduce((a, k) => a + (k.bot || 0), 0);
      return ` <span class="cs-chip" style="color:var(--mm-ok)">${esc(t("cs.upd_new"))}</span>
        <small>${esc(t("cs.upd_diff", { f: (cn.khac || []).length, them, bot }))}: ${esc((cn.khac || []).slice(0, 4).map((k) => k.file).join(", "))}</small>
        ${cn.sua_tai_cho ? `<small style="color:var(--mm-warn)">${esc(t("cs.upd_local"))}</small>` : ""}`;
    }
    function veXemTruoc(r) {
      const xm = r.xac_minh || {};
      const coBanMoi = Object.values(r.cap_nhat || {}).some((c) => c.co_ban_moi);
      const coCao = (r.nguy_co || []).some((c) => c.muc === "cao");
      const muc = NHAN_XM[xm.xac_minh] || "warn";
      const ai = xm.ten ? `${xm.ten}${xm.host ? " · " + xm.host : ""}` : (xm.host || t("cs.unknown_sender"));
      const box = $("csXemTruoc");
      box.innerHTML = `<div class="cs-card">
        <div class="cs-badge ${muc}"><b>${esc(xmNhan(xm.xac_minh))}</b><br>${esc(t("cs.from", { ai }))}
          ${xm.van_tay ? `<br><span class="cs-code">${esc(xm.van_tay)}</span>` : ""}
          ${xm.lan_dau ? `<br>${esc(t("cs.first_time"))}` : ""}
          ${xm.ly_do ? `<br>${esc(xm.ly_do)}` : ""}</div>
        ${(r.canh_bao || []).map((w) => `<div class="cs-badge warn">${esc(w)}</div>`).join("")}
        ${veNguyCo(r.nguy_co || [])}
        ${veKetNoi(r.ket_noi || [])}
        <div class="cs-badge" id="csAi" style="box-shadow:var(--mm-in-sm)">${esc(t("cs.ai_reading"))}</div>
        <div class="cs-list" id="csMuc">${(r.items || []).map((it) => {
          const cn = (r.cap_nhat || {})[it.type + ":" + it.slug];
          const chonSan = !it.da_co || (cn && cn.co_ban_moi);
          return `
          <label><input type="checkbox" value="${esc(it.type + ":" + it.slug)}" ${chonSan ? "checked" : ""}>
            <span><span class="cs-chip">${esc(kindName(it.type))}</span> ${esc(it.name)}${veCapNhat(it, cn)}
            <small>${esc(it.mo_ta || "")}</small></span></label>`;
        }).join("")}</div>
        <label class="cs-row"><input type="checkbox" id="csGhiDe" ${coBanMoi ? "checked" : ""}> ${esc(t("cs.overwrite"))}</label>
        ${xm.xac_minh === "khoa_doi" ? `<label class="cs-row"><input type="checkbox" id="csChapNhan"> ${esc(t("cs.accept_key"))}</label>` : ""}
        ${coCao ? `<label class="cs-row"><input type="checkbox" id="csRuiRo"> ${esc(t("cs.accept_risk"))}</label>` : ""}
        <button class="cs-btn p" id="csCai" ${xm.xac_minh === "gia_mao" ? "disabled" : ""}>${esc(t("cs.install"))}</button>
        <div class="cs-msg" id="csKq"></div></div>`;
      const q = (id) => box.querySelector("#" + id);
      q("csGhiDe").onchange = () => {
        if (q("csGhiDe").checked) box.querySelectorAll("#csMuc input").forEach((i) => (i.checked = true));
      };
      q("csCai").onclick = async () => {
        const chon = [...box.querySelectorAll("#csMuc input:checked")].map((i) => i.value);
        if (!chon.length) { q("csKq").textContent = t("cs.pick"); return; }
        const ck = q("csChapNhan");
        if (ck && !ck.checked) { q("csKq").textContent = t("cs.accept_key_need"); return; }
        const rr = q("csRuiRo");
        if (rr && !rr.checked) { q("csKq").textContent = t("cs.accept_risk_need"); return; }
        q("csCai").disabled = true;
        const kq = await post("/brains/import/cai", { sha256: r.sha256, to_brain: brain, chon: JSON.stringify(chon),
          overwrite: q("csGhiDe").checked ? "1" : "0", chap_nhan: ck && ck.checked ? "1" : "0",
          chap_nhan_rui_ro: rr && rr.checked ? "1" : "0" });
        if (!kq || !kq.ok) { q("csCai").disabled = false; q("csKq").textContent = (kq && kq.error) || t("cs.failed"); return; }
        q("csKq").textContent = t("cs.installed", { n: (kq.imported || []).length, skip: (kq.skipped || []).length });
        try { window.JavisBrains && window.JavisBrains.reload && window.JavisBrains.reload(); } catch (e) {}
      };
    }
    if (capNhat) { $("csNguon").value = capNhat.host; xem(null); }
    else if (nguon) xem(null);
  }

  // ───────────── Đã nhận ─────────────
  async function theDaNhan(body, brain, moCapNhat) {
    body.innerHTML = `<div class="cs-card"><div class="cs-row"><div class="cs-dim" style="flex:1">${esc(t("cs.received_hint"))}</div>
      <button class="cs-btn" id="csKiemTra">${esc(t("cs.upd_check"))}</button></div><div class="cs-msg" id="csKtMsg"></div><div id="csDa">...</div></div>`;
    const box = body.querySelector("#csDa");
    let banMoi = {};
    async function kiemTra() {
      const m = body.querySelector("#csKtMsg");
      m.textContent = t("cs.upd_checking");
      const j = await getJson("/brains/imported/kiem-tra?brain=" + encodeURIComponent(brain));
      banMoi = {};
      ((j && j.items) || []).forEach((x) => { banMoi[x.type + ":" + x.slug] = x; });
      const n = Object.values(banMoi).filter((x) => x.trang_thai === "co_ban_moi").length;
      m.textContent = j && j.ok ? (n ? t("cs.upd_found", { n }) : t("cs.upd_none")) : t("cs.failed");
      nap();
    }
    body.querySelector("#csKiemTra").onclick = kiemTra;
    async function nap() {
      const j = await getJson("/brains/imported?brain=" + encodeURIComponent(brain));
      const ds = (j && j.items) || [];
      if (!ds.length) { box.innerHTML = `<i class="cs-dim">${esc(t("cs.received_none"))}</i>`; return; }
      box.innerHTML = "";
      ds.forEach((x) => {
        const an_toan = x.muc_quyen === "suggest" || x.muc_quyen === "auto";
        const el = document.createElement("div");
        el.className = "cs-link";
        el.innerHTML = `<div class="cs-row"><span class="cs-chip">${esc(kindName(x.type))}</span>
            <b style="flex:1">${esc(x.slug)}</b>
            ${x.type === "skill" ? "" : `<span class="cs-chip">${esc(an_toan ? t("cs.mode_safe") : t("cs.mode_full"))}</span>`}</div>
          <div class="cs-dim">${esc(t("cs.from", { ai: (x.ten ? x.ten + " · " : "") + (x.host || t("cs.unknown_sender")) }))}${x.van_tay ? " · " + esc(x.van_tay) : ""}</div>
          ${veTrangThaiMoi(banMoi[x.type + ":" + x.slug])}
          <div class="cs-row">${an_toan ? `<button class="cs-btn" data-a="tin">${esc(t("cs.trust"))}</button>` : ""}
            ${(banMoi[x.type + ":" + x.slug] || {}).trang_thai === "co_ban_moi" ? `<button class="cs-btn p" data-a="moi">${esc(t("cs.upd_open"))}</button>` : ""}</div>`;
        const bm = el.querySelector('[data-a="moi"]');
        if (bm) bm.onclick = () => { const k = banMoi[x.type + ":" + x.slug]; moCapNhat({ host: k.host, td: k.td }); };
        const b = el.querySelector('[data-a="tin"]');
        if (b) b.onclick = async () => {
          if (!window.confirm(t("cs.trust_ask", { ten: x.slug }))) return;
          await post("/brains/imported/trust", { brain, type: x.type, slug: x.slug });
          nap();
        };
        box.appendChild(el);
      });
    }
    function veTrangThaiMoi(k) {
      if (!k) return "";
      const nhan = { co_ban_moi: t("cs.upd_st_new"), moi_nhat: t("cs.upd_st_latest"), het: t("cs.upd_st_gone"),
                     bo_khoi_goi: t("cs.upd_st_removed"), loi_mang: t("cs.upd_st_net"), chan: t("cs.upd_st_net") }[k.trang_thai] || "";
      const mau = k.trang_thai === "co_ban_moi" ? "var(--mm-ok)" : k.trang_thai === "moi_nhat" ? "var(--mm-dim)" : "var(--mm-warn)";
      return `<div class="cs-dim" style="color:${mau}">${esc(nhan)}${k.sua_tai_cho ? " · " + esc(t("cs.upd_local_short")) : ""}</div>`;
    }
    nap().then(kiemTra);
  }

  // ───────────── ?nhap=<link> từ trang nhận của người gửi ─────────────
  function batNhapTuUrl() {
    let link = "";
    try {
      const u = new URL(location.href);
      link = u.searchParams.get("nhap") || "";
      if (link) {
        u.searchParams.delete("nhap");
        history.replaceState(null, "", u.pathname + (u.search || "") + u.hash);
        try { sessionStorage.setItem("minmin.nhap_cho", link); } catch (e) {}
      } else {
        link = sessionStorage.getItem("minmin.nhap_cho") || "";
      }
    } catch (e) { return; }
    if (!/^https:\/\//i.test(link)) return;
    let lan = 0;
    (function cho() {
      // Đợi đăng nhập xong và danh sách brain nạp xong rồi mới mở (trang đăng nhập phủ lên app).
      const g = document.getElementById("authOverlay");
      const sanSang = !(g && g.classList.contains("open")) && window.JavisBrains
        && window.JavisBrains.ready && window.JavisBrains.ready();
      if (sanSang) {
        try { sessionStorage.removeItem("minmin.nhap_cho"); } catch (e) {}
        mo({ tab: "nhan", nguon: link });
      } else if (++lan < 120) setTimeout(cho, 500);
    })();
  }

  window.MinMinChoChiaSe = { mo };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", batNhapTuUrl);
  else batNhapTuUrl();
})();
