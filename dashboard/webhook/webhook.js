// Trang Webhook (26.10.273): Cấu hình / Sự kiện / Tình trạng. Dòng gọn, bấm mở ngăn phải.
// Mọi chữ do người ngoài gửi tới đều đi qua textContent hoặc esc(), không bao giờ innerHTML thô.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const TT = {
    cho: ["Đang chờ", ""], dang_chay: ["Đang chạy", "warn"], thu_lai: ["Chờ thử lại", "warn"],
    xong: ["Xong", "ok"], bo_qua: ["Bỏ qua", ""], bi_chan: ["Bị chặn", "bad"],
  };
  const BUOC = {
    nhan: "Nhận và lưu", trung: "Gửi trùng, bỏ qua", loc: "Bộ lọc", giao_xong: "Hành động xong",
    giao_loi: "Hành động lỗi", hen_lai: "Hẹn thử lại", chan: "Bị chặn", chay_lai: "Chạy lại", xong: "Xong",
  };
  let hooks = [];

  async function api(url, body) {
    const o = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    try { const r = await fetch(url, o); return await r.json(); } catch (e) { return { ok: false, error: "Không kết nối được máy chủ" }; }
  }
  function gio(ts) {
    if (!ts) return "?";
    const d = new Date(ts * 1000), hom = new Date(); hom.setHours(0, 0, 0, 0);
    const hh = d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    return d >= hom ? hh : hh + " " + d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
  }
  function chip(tt) { const [ten, lop] = TT[tt] || [tt, ""]; return `<span class="chip-tt ${lop}">${esc(ten)}</span>`; }
  function tenHook(id) { const h = hooks.find((x) => x.id === id); return h ? h.ten : id; }

  // ---- ngăn phải
  let ngan = null;
  function dongNgan() {
    if (!ngan) return;
    ngan.box.remove(); ngan.bd.remove(); document.removeEventListener("keydown", ngan.esc); ngan = null;
  }
  function moNgan(tieuDe, thanHtml, nut) {
    dongNgan();
    const bd = document.createElement("div"); bd.className = "ngan-bd";
    const box = document.createElement("aside"); box.className = "ngan";
    box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true");
    box.innerHTML = `<div class="ngan-h"><span class="ngan-t">${esc(tieuDe)}</span><button type="button" class="ngan-x" aria-label="Đóng">&times;</button></div><div class="ngan-b">${thanHtml}</div>`;
    if (nut && nut.length) {
      const f = document.createElement("div"); f.className = "ngan-f";
      nut.forEach((n) => f.appendChild(n)); box.appendChild(f);
    }
    const escFn = (e) => { if (e.key === "Escape") dongNgan(); };
    ngan = { box, bd, esc: escFn };
    bd.onclick = dongNgan; box.querySelector(".ngan-x").onclick = dongNgan;
    document.addEventListener("keydown", escFn);
    document.body.appendChild(bd); document.body.appendChild(box);
    box.querySelector(".ngan-x").focus({ preventScroll: true });
    return box;
  }
  function nut(chu, fn, lop) {
    const b = document.createElement("button"); b.type = "button"; b.className = lop || "nut-phu"; b.textContent = chu;
    b.onclick = async () => { b.disabled = true; try { await fn(b); } finally { b.disabled = false; } };
    return b;
  }

  // ---- tabs
  document.querySelectorAll(".tab").forEach((t) => {
    t.onclick = () => {
      document.querySelectorAll(".tab").forEach((x) => { x.classList.toggle("on", x === t); x.setAttribute("aria-selected", x === t ? "true" : "false"); });
      document.querySelectorAll(".phan").forEach((p) => { p.hidden = p.id !== "p-" + t.dataset.tab; });
      if (t.dataset.tab === "su-kien") taiSuKien();
      if (t.dataset.tab === "tinh-trang") taiTinhTrang();
    };
  });

  // ---- Cấu hình
  async function taiHook() {
    const d = await api("/webhooks");
    hooks = (d && d.webhooks) || [];
    const ul = $("dsHook"); ul.innerHTML = "";
    $("trongHook").hidden = hooks.length > 0;
    hooks.forEach((w) => {
      const li = document.createElement("li");
      const tt = !w.bat ? ["Đang tắt", ""] : w.tam_dung ? ["Tạm dừng xử lý", "warn"] : ["Đang nhận", "ok"];
      const hd = (w.hanh_dong || []).map((a) => (a.loai === "ai" ? "AI" : "chuyển tiếp")).join(" + ");
      li.innerHTML = `<span class="cham ${tt[1]}"></span><div class="giua"><div class="ten"></div><div class="phu"></div></div><span class="chip-tt ${tt[1]}">${esc(tt[0])}</span>`;
      li.querySelector(".ten").textContent = w.ten;
      li.querySelector(".phu").textContent = `${hd} · ${(w.loc || []).length} điều kiện lọc · đã nhận ${w.so_lan} lần`;
      li.appendChild(nut("Chi tiết", () => moCauHinh(w)));
      ul.appendChild(li);
    });
    const sel = $("locHook"), cu = sel.value;
    sel.innerHTML = `<option value="">Mọi webhook</option>` + hooks.map((w) => `<option value="${esc(w.id)}">${esc(w.ten)}</option>`).join("");
    sel.value = cu;
  }

  function moCauHinh(w) {
    const xt = w.xac_thuc || { kieu: "none" };
    const html = `
      <label>Tên <input class="o-nhap" id="cTen" value="${esc(w.ten)}"></label>
      <label>Việc MinMin làm (hành động AI) <textarea class="o-nhap" id="cViec" rows="3">${esc(w.viec)}</textarea></label>
      <label>Mức quyền <select class="o-nhap" id="cMuc">
        <option value="suggest">Chỉ đọc và đề xuất</option><option value="auto">Được ghi file nháp</option><option value="full">Được làm việc thật</option></select></label>
      <label><input type="checkbox" id="cAI"> Chạy AI cho mỗi sự kiện</label>
      <label class="hang-check"><input type="checkbox" id="cAnToan"> Bên nhận tự chống trùng theo mã X-MinMin-Delivery (cho phép tự thử lại khi chưa rõ kết quả)</label>
      <label class="hang-check"><input type="checkbox" id="cTheoDon"> POSCake: chống trùng theo shop_id + id + status. Bỏ chọn nếu cần nhận mọi lần sửa đơn cùng trạng thái.</label>
      <label>Chuyển tiếp nguyên thân tới (https, để trống nếu không cần) <input class="o-nhap" id="cURL" placeholder="https://script.google.com/macros/s/.../exec"></label>
      <h3>Bộ lọc</h3>
      <p class="ghi-chu">Mỗi dòng một điều kiện: <code>đường | phép | giá trị</code>. Phép: bang, khac, trong, chua, co. Ví dụ đơn mới của Pancake: <code>status | bang | 0</code>, sản phẩm: <code>items[*].variation_info.name | chua | Đầm</code>. Thiếu trường thì sự kiện bị bỏ qua, không đoán.</p>
      <textarea class="o-nhap" id="cLoc" rows="3"></textarea>
      <label>Coi là gửi trùng trong (giờ) <input class="o-nhap" id="cTrung" type="number" min="0" max="168" value="${esc(w.trung_gio)}"></label>
      <h3>Xác thực</h3>
      <p class="ghi-chu">Pancake/POSCake không ký webhook: đường bí mật là lớp khoá. Stripe, GitHub, Shopify, Systeme.io hoặc HMAC-SHA256 thì dán khoá ký của họ. Khoá được mã hoá, không bao giờ hiện lại.</p>
      <label>Kiểu <select class="o-nhap" id="cKieu">
        <option value="none">Chỉ đường bí mật (Pancake, form)</option><option value="stripe">Stripe</option><option value="github">GitHub</option>
        <option value="shopify">Shopify</option><option value="systeme_io">Systeme.io (chưa kiểm với lần giao thật)</option><option value="hmac_sha256">HMAC-SHA256 tuỳ chỉnh</option></select></label>
      <div id="cHmac"><label>Header chữ ký <input class="o-nhap" id="cHdr" value="${esc(xt.header || "")}" placeholder="X-Signature"></label>
        <label>Mã hoá <select class="o-nhap" id="cMH"><option value="hex">hex</option><option value="base64">base64</option></select></label>
        <label>Tiền tố <input class="o-nhap" id="cTT" value="${esc(xt.tien_to || "")}" placeholder="sha256="></label></div>
      <label>Khoá ký ${xt.co_khoa ? "(đã có, để trống là giữ nguyên)" : ""} <input class="o-nhap" id="cKhoa" type="password" autocomplete="off"></label>
      <h3>Gửi thử</h3>
      <p class="ghi-chu">Dán một thân mẫu (JSON). Bấm <b>Xem trước</b> để biết nó qua bộ lọc không và sẽ chạy gì, chưa làm gì thật. <b>Gửi thử thật</b> lưu thành sự kiện có nhãn thử rồi chạy y như đơn thật.</p>
      <textarea class="o-nhap" id="cThan" rows="4" placeholder='{"event_type": "create", "id": 739, "status": 0}'></textarea>
      <pre id="cKQ" hidden></pre>`;
    const giu = () => {
      const loc = $("cLoc").value.split("\n").map((d) => d.trim()).filter(Boolean).map((d) => {
        const [duong, phep, ...gt] = d.split("|").map((x) => x.trim());
        let v = gt.join("|"); if (v !== "" && !isNaN(Number(v))) v = Number(v);
        return { duong, phep: phep || "bang", gia_tri: v };
      });
      const hd = [];
      if ($("cAI").checked) hd.push({ id: "ai", loai: "ai" });
      const url = $("cURL").value.trim();
      if (url) hd.push({ id: "chuyen_tiep", loai: "chuyen_tiep", url, lap_an_toan: $("cAnToan").checked });
      const kieu = $("cKieu").value;
      const xtMoi = { kieu };
      if (kieu === "hmac_sha256") Object.assign(xtMoi, { header: $("cHdr").value.trim(), ma_hoa: $("cMH").value, tien_to: $("cTT").value });
      return { id: w.id, ten: $("cTen").value, viec: $("cViec").value, muc_quyen: $("cMuc").value, loc, hanh_dong: hd,
        trung_theo_don: $("cTheoDon").checked, trung_gio: Number($("cTrung").value || 24), xac_thuc: xtMoi, khoa: $("cKhoa").value };
    };
    const hienKQ = (o) => { const p = $("cKQ"); p.hidden = false; p.textContent = o; };
    const moTa = (r) => r.se_chay ? "Sẽ chạy:\n" + (r.hanh_dong || []).map((a) => "- " + a.mo_ta).join("\n") : "Bỏ qua: " + (r.ly_do || "");
    const box = moNgan(w.ten, html, [
      nut("Lưu", async () => {
        const p = giu();
        if (!p.hanh_dong.length) { alert("Cần ít nhất một hành động (AI hoặc chuyển tiếp)."); return; }
        const r = await api("/webhooks/cap-nhat", p);
        if (!r.ok) { alert("Chưa lưu được: " + (r.error || "")); return; }
        dongNgan(); taiHook();
      }, "nut-chinh"),
      nut("Xem trước", async () => { const r = await api("/webhooks/xem-truoc", { id: w.id, than: $("cThan").value }); hienKQ(r.ok ? moTa(r) : r.error); }),
      nut("Gửi thử thật", async () => { const r = await api("/webhooks/thu", { id: w.id, than: $("cThan").value }); hienKQ(r.ok ? `Đã lưu sự kiện ${r.su_kien}. ${moTa(r)}` : r.error); }),
      nut(w.tam_dung ? "Tiếp tục xử lý" : "Tạm dừng xử lý", async () => { await api("/webhooks/cap-nhat", { id: w.id, tam_dung: !w.tam_dung }); dongNgan(); taiHook(); }),
      nut(w.bat ? "Tắt nhận" : "Bật nhận", async () => { await api("/webhooks/cap-nhat", { id: w.id, bat: !w.bat }); dongNgan(); taiHook(); }),
      nut("Đổi mã", async () => {
        if (!confirm("Đổi mã? Đường cũ ngừng nhận ngay, phải dán đường mới vào Pancake.")) return;
        const r = await api("/webhooks/doi-token", { id: w.id }); dongNgan(); hienMa(r.url); taiHook();
      }),
      nut("Xoá", async () => {
        if (!confirm("Xoá webhook này cùng mọi sự kiện của nó?")) return;
        await api("/webhooks/xoa", { id: w.id }); dongNgan(); taiHook();
      }, "nut-phu nut-nguy"),
    ]);
    box.querySelector("#cMuc").value = w.muc_quyen;
    box.querySelector("#cAI").checked = (w.hanh_dong || []).some((a) => a.loai === "ai");
    const ct = (w.hanh_dong || []).find((a) => a.loai === "chuyen_tiep");
    box.querySelector("#cURL").value = ct ? ct.url : "";
    box.querySelector("#cAnToan").checked = !!(ct && ct.lap_an_toan);
    box.querySelector("#cTheoDon").checked = !!w.trung_theo_don;
    box.querySelector("#cLoc").value = (w.loc || []).map((d) => `${d.duong} | ${d.phep} | ${Array.isArray(d.gia_tri) ? d.gia_tri.join(",") : (d.gia_tri == null ? "" : d.gia_tri)}`).join("\n");
    box.querySelector("#cKieu").value = xt.kieu || "none";
    box.querySelector("#cMH").value = xt.ma_hoa || "hex";
    const hm = () => { box.querySelector("#cHmac").hidden = box.querySelector("#cKieu").value !== "hmac_sha256"; };
    box.querySelector("#cKieu").onchange = hm; hm();
  }

  function hienMa(url) {
    const b = $("baoMa");
    if (!url) { b.hidden = true; return; }
    b.hidden = false;
    b.innerHTML = `<b>Đường bí mật, chỉ hiện lần này. Chép ngay:</b><code></code><p class="ghi-chu">Trong Pancake POS: Cấu hình, Webhook, dán đường này vào ô URL rồi chọn sự kiện đơn hàng. Ai có đường này là gửi được vào MinMin, đừng chia sẻ.</p>`;
    b.querySelector("code").textContent = url;
  }

  $("themMoi").onclick = () => { $("formMoi").hidden = !$("formMoi").hidden; };
  $("mHuy").onclick = () => { $("formMoi").hidden = true; };
  $("mTao").onclick = async () => {
    const r = await api("/webhooks", { ten: $("mTen").value, viec: $("mViec").value, muc_quyen: $("mMuc").value });
    if (!r.ok) { alert("Chưa tạo được: " + (r.error || "")); return; }
    $("formMoi").hidden = true; $("mTen").value = ""; $("mViec").value = "";
    hienMa(r.url); taiHook();
  };

  // ---- Sự kiện
  async function taiSuKien() {
    const q = new URLSearchParams({ id: $("locHook").value, trang_thai: $("locTT").value, gioi_han: "200" });
    const d = await api("/webhooks/su-kien?" + q);
    const ds = (d && d.su_kien) || [];
    const ul = $("dsSK"); ul.innerHTML = "";
    $("trongSK").hidden = ds.length > 0;
    ds.forEach((ev) => {
      const li = document.createElement("li");
      const lop = (TT[ev.trang_thai] || ["", ""])[1];
      li.innerHTML = `<span class="cham ${lop}"></span><div class="giua"><div class="ten"></div><div class="phu"></div></div>${chip(ev.trang_thai)}`;
      li.querySelector(".ten").textContent = `${tenHook(ev.hook_id)}${ev.thu ? " (thử)" : ""}`;
      li.querySelector(".phu").textContent = `${gio(ev.nhan_luc)} · ${ev.id}${ev.ly_do ? " · " + ev.ly_do : ""}`;
      li.appendChild(nut("Xem", () => moSuKien(ev.id)));
      ul.appendChild(li);
    });
  }
  async function moSuKien(sid) {
    const d = await api("/webhooks/su-kien/chi-tiet?sk=" + encodeURIComponent(sid));
    if (!d.ok) { alert(d.error || "Không mở được"); return; }
    const ev = d.su_kien;
    const giao = Object.entries(ev.giao || {}).map(([k, g]) => `<dt>${esc(k)}</dt><dd>${esc(g.tt)} · lần ${esc(g.lan)}${g.loi ? " · " + esc(g.loi) : ""}${g.ket_qua ? " · " + esc(g.ket_qua) : ""}</dd>`).join("");
    const html = `<dl><dt>Webhook</dt><dd>${esc(tenHook(ev.hook_id))}</dd><dt>Trạng thái</dt><dd>${chip(ev.trang_thai)} ${esc(ev.ly_do || "")}</dd>
      <dt>Nhận lúc</dt><dd>${esc(gio(ev.nhan_luc))}</dd><dt>Số lần thử</dt><dd>${esc(ev.lan_thu)}</dd><dt>Dung lượng</dt><dd>${esc(ev.dai)} byte</dd>${giao}</dl>
      <h3>Dòng thời gian</h3><ul class="tg">${(ev.dong_thoi_gian || []).map((t) => `<li><span class="gio">${esc(gio(t.luc))}</span>${esc(BUOC[t.buoc] || t.buoc)}${t.chi_tiet ? ": " + esc(t.chi_tiet) : ""}</li>`).join("")}</ul>
      <h3>Dữ liệu (đã che khách, nhân viên, link)</h3><pre></pre>`;
    const nutDs = [];
    if (ev.trang_thai !== "dang_chay") {
      nutDs.push(nut("Chạy lại với cấu hình hiện tại", async () => {
        const r = await api("/webhooks/su-kien/chay-lai", { sk: sid });
        if (!r.ok) { alert(r.error); return; }
        dongNgan(); taiSuKien();
      }, "nut-chinh"));
    }
    const box = moNgan("Sự kiện " + sid, html, nutDs);
    box.querySelector("pre").textContent = ev.than_che || "";
  }
  $("locHook").onchange = taiSuKien;
  $("locTT").onchange = taiSuKien;
  $("chayLaiHet").onclick = async () => {
    if (!confirm("Chạy lại mọi sự kiện đang bị chặn bằng cấu hình hiện tại?")) return;
    const r = await api("/webhooks/su-kien/chay-lai-bi-chan", { id: $("locHook").value });
    alert(`Đã đưa ${r.so || 0} sự kiện về hàng chờ.`); taiSuKien();
  };

  // ---- Tình trạng
  async function taiTinhTrang() {
    const d = await api("/webhooks/tinh-trang");
    if (!d.ok) return;
    let chan = 0, xong = 0;
    Object.values(d.hook || {}).forEach((h) => { chan += h.bi_chan; xong += h.dem_24h.xong || 0; });
    $("tongTT").innerHTML = `<div class="o"><span>Hàng đợi</span><b>${esc(d.hang_doi)}</b></div><div class="o"><span>Xong trong 24 giờ</span><b>${esc(xong)}</b></div><div class="o"><span>Đang bị chặn</span><b>${esc(chan)}</b></div>`;
    const ul = $("dsTT"); ul.innerHTML = "";
    hooks.forEach((w) => {
      const h = (d.hook || {})[w.id]; if (!h) return;
      const li = document.createElement("li");
      const lop = h.bi_chan ? "bad" : (h.dem_24h.thu_lai ? "warn" : "ok");
      li.innerHTML = `<span class="cham ${lop}"></span><div class="giua"><div class="ten"></div><div class="phu"></div></div>`;
      li.querySelector(".ten").textContent = w.ten;
      const c = h.dem_24h;
      li.querySelector(".phu").textContent = `24 giờ: ${c.xong} xong, ${c.bo_qua} bỏ qua, ${c.thu_lai} chờ thử lại, ${c.bi_chan} bị chặn · cuối: ${gio(h.cuoi_luc)}${h.loi_cuoi ? " · lỗi cuối: " + h.loi_cuoi.ly_do : ""}`;
      ul.appendChild(li);
    });
    const tt = $("ttChay");
    tt.textContent = d.dang_chay ? "Bộ xử lý đang chạy" : "Bộ xử lý chưa chạy";
    tt.className = "chip-tt " + (d.dang_chay ? "ok" : "bad");
  }

  taiHook().then(taiTinhTrang);
  setInterval(() => {
    if (document.hidden || ngan) return;
    if (!$("p-su-kien").hidden) taiSuKien();
    if (!$("p-tinh-trang").hidden) taiTinhTrang();
  }, 10000);
})();

