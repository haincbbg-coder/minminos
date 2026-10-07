// Biến động số dư: tổng hôm nay, danh sách giao dịch Casso đẩy về, cài webhook và nơi nhận tin.
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  // Nhúng trong trang MinMin: bỏ mũi tên "về MinMin" và lấy tông sáng/tối của MinMin.
  if (new URLSearchParams(location.search).get("nhung") === "1") {
    document.documentElement.classList.add("nhung");
    const lui = document.querySelector("a.back"); if (lui) lui.remove();
    try {
      const tong = window.parent.document.documentElement.getAttribute("data-theme");
      document.documentElement.setAttribute("data-theme", tong === "light" ? "light" : "dark");
    } catch (e) { /* khác origin: theo hệ điều hành */ }
  }
  let duongDan = "";

  function tien(n) {
    n = Math.round(Number(n) || 0);
    return Math.abs(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "đ";
  }
  function gio(ts) {
    if (!ts) return "?";
    const d = new Date(ts * 1000);
    const hom = new Date(); hom.setHours(0, 0, 0, 0);
    const hh = d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
    return d >= hom ? hh : hh + " " + d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
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
    const j = await r.json().catch(() => ({}));
    if (!r.ok && !j.error) j.error = "Lỗi " + r.status;
    return j;
  }
  function postJson(url, data) {
    return api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data || {}) });
  }
  function bao(msg, loi) {
    const p = $("kq"); p.textContent = msg || ""; p.style.color = loi ? "var(--bad)" : "";
  }

  async function taiCaiDat() {
    let c;
    try { c = await api("/bien-dong/cai-dat"); } catch (e) { return; }
    duongDan = c.duong_dan || "";
    $("url").textContent = location.origin + duongDan;
    $("khoaTT").textContent = c.da_co_khoa
      ? "Đã lưu Key bảo mật (không hiện lại). Dán key mới rồi bấm Lưu nếu muốn thay."
      : "Chưa có Key bảo mật: MinMin sẽ từ chối mọi giao dịch cho tới khi bạn dán key.";
    const tt = $("tt");
    tt.className = "tt " + (c.da_co_khoa ? "song" : "mat");
    tt.textContent = c.da_co_khoa ? "Đã nối Casso" : "Chưa nối Casso";
    $("optVao").checked = !!c.chi_tien_vao;
    $("nguong").value = String(c.nguong_toi_thieu || 0);
    $("noiNhan").value = (c.noi_nhan_them || []).join("\n");
  }

  async function taiGiaoDich() {
    const q = new URLSearchParams({ limit: "100" });
    if ($("chiVao").checked) q.set("chi_vao", "true");
    const tim = $("tim").value.trim(); if (tim) q.set("tim", tim);
    let d;
    try { d = await api("/bien-dong/giao-dich?" + q.toString()); } catch (e) { return; }
    const h = d.hom_nay || {};
    $("tongVao").textContent = "+" + tien(h.tong_vao);
    $("soVao").textContent = String(h.so_gd_vao || 0);
    $("tongRa").textContent = "-" + tien(h.tong_ra);
    const ds = d.giao_dich || [];
    const ul = $("ds"); ul.textContent = "";
    $("trong").hidden = ds.length > 0;
    ds.forEach((g) => {
      const vao = (g.so_tien || 0) > 0;
      const li = el("li");
      li.appendChild(el("div", "tien " + (vao ? "vao" : "ra"), (vao ? "+" : "-") + tien(g.so_tien)));
      const nd = el("div", "nd");
      const mt = el("div", "mo-ta", g.mo_ta || "(không có nội dung)");
      if (g.thu_nghiem) mt.appendChild(el("span", "the", "thử nghiệm"));
      nd.appendChild(mt);
      const phan = [gio(g.luc)];
      if (g.nguoi_chuyen) phan.push(g.nguoi_chuyen + (g.ngan_hang_chuyen ? " (" + g.ngan_hang_chuyen + ")" : ""));
      const tk = (g.nhan_tk || g.ngan_hang || "TK") + (g.tk4 ? " " + g.tk4 : "");
      phan.push(tk);
      if (g.so_du != null) phan.push("Số dư " + (g.so_du < 0 ? "-" : "") + tien(g.so_du));
      nd.appendChild(el("div", "meta", phan.join(" · ")));
      li.appendChild(nd);
      ul.appendChild(li);
    });
  }

  $("chiVao").onchange = taiGiaoDich;
  let hen = 0;
  $("tim").oninput = () => { clearTimeout(hen); hen = setTimeout(taiGiaoDich, 350); };

  $("chepUrl").onclick = async () => {
    try { await navigator.clipboard.writeText($("url").textContent); $("chepUrl").textContent = "Đã chép"; }
    catch (e) { const s = getSelection(); const rg = document.createRange(); rg.selectNodeContents($("url")); s.removeAllRanges(); s.addRange(rg); }
    setTimeout(() => { $("chepUrl").textContent = "Chép"; }, 2000);
  };
  $("luuKhoa").onclick = async () => {
    const k = $("khoa").value.trim();
    if (!k) { $("khoaTT").textContent = "Chưa dán key."; return; }
    const r = await postJson("/bien-dong/cai-dat", { khoa: k });
    if (r.error) { $("khoaTT").textContent = r.error; return; }
    $("khoa").value = "";
    taiCaiDat();
  };
  $("luuTuyChon").onclick = async () => {
    const r = await postJson("/bien-dong/cai-dat", {
      chi_tien_vao: $("optVao").checked,
      nguong_toi_thieu: Number($("nguong").value || 0),
      noi_nhan_them: $("noiNhan").value.split(/[\n,;]+/).map((s) => s.trim()).filter(Boolean),
    });
    if (r.error) { bao(r.error, true); return; }
    bao("Đã lưu.");
    taiCaiDat();
  };
  $("guiThu").onclick = async () => {
    bao("Đang gửi thử…");
    const r = await postJson("/bien-dong/thu", {});
    if (r.error) { bao(r.error, true); return; }
    bao("Đã gửi tin thử vào chuông MinMin, Telegram của bạn" + (r.noi_nhan_them ? " và " + r.noi_nhan_them + " nơi nhận thêm" : "") + ".");
  };
  $("doiToken").onclick = async () => {
    if (!confirm("Đổi địa chỉ webhook? Địa chỉ cũ hết hiệu lực ngay, bạn phải dán địa chỉ mới vào Casso.")) return;
    const r = await postJson("/bien-dong/doi-token", {});
    if (r.error) { bao(r.error, true); return; }
    bao("Đã đổi địa chỉ. Chép địa chỉ mới ở bước 2 và sửa webhook trong Casso.");
    taiCaiDat();
  };

  taiCaiDat(); taiGiaoDich();
  setInterval(() => { if (!document.hidden) taiGiaoDich(); }, 10000);
})();
