// MinMin Mắt Nhà: trạng thái camera, danh sách sự kiện, mã ghép nối, tải bộ cài.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  // Nhúng trong trang MinMin (0.64.98): bỏ mũi tên "về MinMin" (đã đứng trong MinMin rồi).
  if (new URLSearchParams(location.search).get("nhung") === "1") {
    document.documentElement.classList.add("nhung");
    const lui = document.querySelector("a.back"); if (lui) lui.remove();
  }
  const TEN_LOAI = { nguoi: "Người", xe: "Xe", con_vat: "Con vật", vat: "Đồ vật", giong: "Giọng nói", khac: "Khác" };
  const ICON = { nguoi: "👤", xe: "🚗", con_vat: "🐾", vat: "📦", giong: "🔊", khac: "•" };
  // Canh rào (0.64.98): mức cảnh báo cầu nối suy ra từ vùng vẽ trong Frigate (rao_..., trong_...).
  const TEN_CANH_BAO = { tien_sat: "Tiến sát hàng rào", lang_vang: "Lảng vảng sát rào", vao_khu: "Vào khu cấm", vuot_rao: "VƯỢT RÀO" };
  let loc = "hom-nay";
  let camChon = "";

  function gio(ts) {
    if (!ts) return "?";
    const d = new Date(ts * 1000);
    const hom = new Date(); hom.setHours(0, 0, 0, 0);
    const hh = d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
    return d >= hom ? hh : hh + " " + d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
  }
  function truoc(ts) {
    if (!ts) return "chưa có";
    const s = Date.now() / 1000 - ts;
    if (s < 90) return "vừa xong";
    if (s < 3600) return Math.round(s / 60) + " phút trước";
    if (s < 86400) return Math.round(s / 3600) + " giờ trước";
    return Math.round(s / 86400) + " ngày trước";
  }
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  async function api(url, opt) {
    const r = await fetch(url, Object.assign({ credentials: "same-origin" }, opt || {}));
    if (r.status === 401) { location.href = "/"; throw new Error("chưa đăng nhập"); }
    return r.json();
  }
  function dauHomNay() { const d = new Date(); d.setHours(0, 0, 0, 0); return d.getTime() / 1000; }

  async function taiTrangThai() {
    let t;
    try { t = await api("/mat-nha/trang-thai"); } catch (e) { return; }
    const c = $("cau");
    c.className = "cau " + (t.cau_noi_song ? "song" : "mat");
    c.textContent = t.cau_noi_song ? "Máy ở nhà: đang nối" : (t.nhip_cuoi ? "Máy ở nhà: mất nối " + truoc(t.nhip_cuoi) : "Máy ở nhà: chưa cài");
    const box = $("cams"); box.textContent = "";
    (t.cameras || []).forEach((cam) => {
      const b = el("button", "cam"); b.type = "button";
      b.setAttribute("aria-pressed", String(camChon === cam.camera));
      b.appendChild(el("b", "", cam.camera));
      b.appendChild(el("span", "", (cam.nhan_cuoi ? cam.nhan_cuoi + " · " : "") + truoc(cam.su_kien_cuoi)));
      b.onclick = () => { camChon = camChon === cam.camera ? "" : cam.camera; taiTrangThai(); taiSuKien(); };
      box.appendChild(b);
    });
    const ma = t.ma || {};
    $("maTT").textContent = ma.da_co
      ? "Đã có mã (đuôi …" + ma.cuoi + ", tạo " + truoc(ma.tao_luc) + "). Bấm tạo mã mới nếu lỡ làm lộ mã."
      : "Chưa có mã. Tạo mã rồi dán vào bộ cài trên máy ở nhà.";
  }

  async function taiSuKien() {
    const q = new URLSearchParams({ limit: "200" });
    if (loc !== "tat-ca") q.set("tu", String(dauHomNay()));
    if (loc === "tat-ca") q.set("tu", String(dauHomNay() - 6 * 86400));
    if (loc === "nguoi-la") { q.set("chi_nguoi_la", "true"); q.set("tu", String(dauHomNay() - 6 * 86400)); }
    if (loc === "canh-bao") { q.set("chi_canh_bao", "true"); q.set("tu", String(dauHomNay() - 6 * 86400)); }
    if (loc === "xe" || loc === "bien-so") q.set("loai", "xe");
    if (loc === "giong") q.set("loai", "giong");
    if (camChon) q.set("camera", camChon);
    const bs = $("timBien").value.trim(); if (bs) { q.set("bien_so", bs); q.set("tu", String(dauHomNay() - 29 * 86400)); }
    const ten = $("timTen").value.trim(); if (ten) { q.set("ten", ten); q.set("tu", String(dauHomNay() - 29 * 86400)); }
    let d;
    try { d = await api("/mat-nha/su-kien?" + q.toString()); } catch (e) { return; }
    let ds = d.su_kien || [];
    if (loc === "bien-so") ds = ds.filter((e) => e.bien_so);
    const ul = $("ds"); ul.textContent = "";
    $("trong").hidden = ds.length > 0;
    ds.forEach((e) => {
      const li = el("li", e.canh_bao ? "cb cb-" + e.canh_bao : "");
      if (e.anh) {
        const img = el("img"); img.loading = "lazy"; img.alt = TEN_LOAI[e.loai] || ""; img.src = e.anh;
        img.onclick = () => { $("xemAnh").src = e.anh; $("xem").hidden = false; };
        li.appendChild(img);
      } else {
        li.appendChild(el("div", "noimg", ICON[e.loai] || "•"));
      }
      const nd = el("div", "nd");
      const dong = el("div");
      if (e.loai === "nguoi") {
        dong.appendChild(el("span", "ai" + (e.la_nguoi_la ? " la" : ""), e.ten || (e.la_nguoi_la ? "Người lạ" : "Người")));
      } else {
        dong.appendChild(el("span", "ai", e.ten || TEN_LOAI[e.loai] || e.loai));
        if (e.nhan && e.loai !== "giong") dong.appendChild(document.createTextNode(" (" + e.nhan + ")"));
      }
      if (e.bien_so) { dong.appendChild(document.createTextNode(" ")); dong.appendChild(el("span", "bien", e.bien_so)); }
      nd.appendChild(dong);
      if (e.canh_bao) nd.appendChild(el("div", "canh", "⚠ " + (TEN_CANH_BAO[e.canh_bao] || e.canh_bao) + (e.vung && e.vung.length ? " · " + e.vung.join(" → ") : "")));
      nd.appendChild(el("div", "meta", gio(e.bat_dau) + " · " + e.camera + (e.diem ? " · " + Math.round(e.diem * 100) + "%" : "")));
      if (e.chu) nd.appendChild(el("div", "chu", "“" + e.chu + "”"));
      li.appendChild(nd);
      ul.appendChild(li);
    });
  }

  document.querySelectorAll(".loc button").forEach((b) => {
    b.onclick = () => {
      loc = b.dataset.loc;
      document.querySelectorAll(".loc button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      taiSuKien();
    };
  });
  let hen = 0;
  ["timBien", "timTen"].forEach((id) => { $(id).oninput = () => { clearTimeout(hen); hen = setTimeout(taiSuKien, 350); }; });
  $("xem").onclick = () => { $("xem").hidden = true; };

  $("taoMa").onclick = async () => {
    if (!confirm("Tạo mã ghép nối mới? Mã cũ (nếu có) sẽ hết hiệu lực.")) return;
    const r = await api("/mat-nha/ma", { method: "POST" });
    if (!r.ma) { alert(r.error || "Không tạo được mã"); return; }
    $("ma").textContent = r.ma; $("maHop").hidden = false;
    taiTrangThai();
  };
  $("chepMa").onclick = async () => {
    try { await navigator.clipboard.writeText($("ma").textContent); $("chepMa").textContent = "Đã chép"; }
    catch (e) { const s = getSelection(); const rg = document.createRange(); rg.selectNodeContents($("ma")); s.removeAllRanges(); s.addRange(rg); }
  };

  // Tải CaiMatNha.bat đã điền sẵn địa chỉ MinMin này (thay chỗ __MINMIN_URL__ đầu tiên).
  $("taiBat").onclick = async () => {
    const r = await fetch("/static/mat-nha/kit/CaiMatNha.bat", { cache: "no-cache" });
    let t = await r.text();
    t = t.replace("__MINMIN_URL__", location.origin);
    if (t.indexOf("\r\n") < 0) t = t.replace(/\n/g, "\r\n");
    const url = URL.createObjectURL(new Blob([t], { type: "application/octet-stream" }));
    const a = document.createElement("a"); a.href = url; a.download = "CaiMatNha.bat";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  };

  taiTrangThai(); taiSuKien();
  setInterval(() => { if (!document.hidden) { taiTrangThai(); taiSuKien(); } }, 30000);
})();
