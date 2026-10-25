// Chạy trong trang Pancake: nhận phản hồi hội thoại/tin nhắn từ hook.js, tra mã, vẽ khung gợi ý.
(function () {
  const hoi = (m) => new Promise((r) => { try { chrome.runtime.sendMessage(m, r); } catch (e) { r({ ok: false, error: String(e) }); } });
  const convs = {};            // id hội thoại -> {ad_ids, post_id, type}
  let hienTai = null;          // {id, text, ad_ids, post_id, anh:[url]}
  let bang = null;
  let chanDoan = { convs: 0, tinNhan: 0, luc: 0 };
  const anhKq = {};            // url ảnh -> {dang} | {kq} | {loi}, giữ qua các hội thoại
  let anhChon = null;

  function chuoiHtml(s) { const d = document.createElement("div"); d.innerHTML = String(s || ""); return d.textContent || ""; }
  function layAnh(m) {
    const kq = [];
    (m.attachments || []).forEach((a) => {
      const u = a.url || a.preview_url || (a.image_data && (a.image_data.url || a.image_data.preview_url)) || a.src;
      const loai = String(a.type || "").toLowerCase();
      // chỉ ảnh thật: bỏ sticker, nút like, quảng cáo, liên kết, mẫu tin
      if (/sticker|ad_click|link|template|reaction|address|replied|video/.test(loai)) return;
      if (/\/stickers\//.test(String(u))) return;
      if (u && /^https?:/.test(u) && (loai === "photo" || loai === "image" || (!loai && /\.(jpe?g|png|webp)/i.test(u)))) kq.push(u);
    });
    return kq;
  }
  // Pancake ghi mã quảng cáo trong tin nhắn loại ad_click: {ad_id, post_attachments:[{description, url ảnh}]}
  // gom mọi chuỗi chữ trong một đối tượng (tên/tiêu đề/nội dung quảng cáo), bỏ qua đường dẫn ảnh
  function gomChu(o, kq, sau) {
    if (o == null || sau > 4) return;
    if (typeof o === "string") { if (!/^https?:\/\//i.test(o) && o.length < 2000) kq.push(chuoiHtml(o)); return; }
    if (Array.isArray(o)) { o.forEach((x) => gomChu(x, kq, sau + 1)); return; }
    if (typeof o === "object") Object.keys(o).forEach((k) => { if (!/url|image|photo|thumb|id$/i.test(k)) gomChu(o[k], kq, sau + 1); });
  }
  // Mã nằm trong tên/nội dung quảng cáo: "#V1213", hoặc "V1213 - Xưởng May MD" ở đầu dòng. Không cần có trong bảng tồn.
  function maQuangCao(text) {
    const kq = [];
    const dung = (c) => { c = self.mmChuanMa(c); if (c && !kq.includes(c)) kq.push(c); };
    let x;
    const r1 = /#\s*([A-Za-z]{1,4}\d{1,6}[A-Za-z]{0,2})\b/g; while ((x = r1.exec(text))) dung(x[1]);
    const r2 = /(?:^|\n)\s*([A-Za-z]{1,4}\d{2,6}[A-Za-z]{0,2})\s*[-–|:]/g; while ((x = r2.exec(text))) dung(x[1]);
    return kq.slice(0, 3);
  }
  function layQuangCao(ds) {
    const ids = [], text = [], anh = [];
    ds.slice().reverse().forEach((m) => (m.attachments || []).forEach((a) => {
      if (!a || String(a.type).toLowerCase() !== "ad_click") return;
      if (a.ad_id && !ids.includes(String(a.ad_id))) ids.push(String(a.ad_id));
      gomChu(a, text, 0);
      (a.post_attachments || []).forEach((p) => {
        if (p.url && /\.(jpe?g|png|webp)/i.test(p.url)) anh.push(p.url);
      });
      if (a.ad_click_photo_url) anh.push(a.ad_click_photo_url);
    }));
    const t = text.join("\n");
    return { ids, text: t, anh: anh[0] || "", ma: maQuangCao(t) };
  }
  // Tin có ghi rõ "MÃ: T145", "Mã #S26", "BÁO GIÁ MÃ S26" (cả của khách lẫn bot/nhân viên shop): mã này đáng tin
  // hơn mọi suy đoán, và hiện ra kể cả khi mã chưa nằm trong bảng tồn.
  function maRo(ds) {
    const kq = [];
    ds.slice(-40).reverse().forEach((m) => {
      const t = chuoiHtml(m.original_message || m.message || m.text || "").normalize("NFC");
      const re = /(?:^|[^A-Za-zÀ-ỹ])m[ãa]\s*(?:s[ốo]|hàng|sp)?\s*[:#.\-]?\s*#?\s*([A-Za-z]{1,4}\s?-?\d{1,6}[A-Za-z]{0,2})/gi;
      let x; while ((x = re.exec(t))) { const c = self.mmChuanMa(x[1]); if (c && !kq.includes(c)) kq.push(c); }
    });
    return kq.slice(0, 3);
  }
  function docConversations(arr) {
    arr.forEach((c) => {
      if (!c || !c.id) return;
      const ad = [].concat(c.ad_ids || c.ad_id || []).map(String).filter(Boolean);
      convs[c.id] = { ad_ids: ad, post_id: c.post_id ? String(c.post_id) : "", type: c.type || "" };
      chanDoan.convs++;
    });
  }
  function docMessages(url, j) {
    const mc = /\/conversations\/([^/?]+)\/messages/.exec(url);
    const mp = /\/pages\/(\d+)\//.exec(url);
    const id = mc ? decodeURIComponent(mc[1]) : (j.conversation_id || "");
    const pageId = mp ? mp[1] : "";
    const ds = (j.messages || []).filter(Boolean);
    const khach = ds.filter((m) => { const f = m.from && m.from.id; return f && String(f) !== pageId; });
    const gan = khach.slice(-8);
    const text = gan.map((m) => chuoiHtml(m.original_message || m.message || m.text || "")).filter(Boolean).join("\n");
    const anh = [];
    gan.forEach((m) => layAnh(m).forEach((u) => anh.push(u)));
    chanDoan.tinNhan += ds.length;
    const c = convs[id] || {};
    // hội thoại bình luận: tin nhắn có thể mang post_id riêng
    const post = c.post_id || (ds.find((m) => m.post_id) || {}).post_id || "";
    const qc = layQuangCao(ds);
    const adIds = qc.ids.length ? qc.ids : (c.ad_ids || []);
    hienTai = { id, text, ad_ids: adIds, ad_text: qc.text, ma_qc: qc.ma, ad_anh: qc.anh, ma_ro: maRo(ds), post_id: post ? String(post) : "", anh: anh.slice(-6) };
  }
  function nhan(url, body) {
    let j; try { j = JSON.parse(body); } catch (e) { return; }
    chanDoan.luc = Date.now();
    if (Array.isArray(j.conversations)) docConversations(j.conversations);
    if (Array.isArray(j.messages)) docMessages(url, j);
    if (j.conversation && j.conversation.id) docConversations([j.conversation]);
    ve();
  }
  window.addEventListener("message", (e) => {
    if (e.source !== window || !e.data || e.data.nguon !== "mm-gy") return;
    nhan(e.data.url, e.data.body);
  });

  // ---------------- khung gợi ý (Shadow DOM để CSS của Pancake không đụng vào)
  let goc = null, root = null, thu = false;
  function dung() {
    if (goc || !document.body) return;
    goc = document.createElement("div");
    goc.style.cssText = "position:fixed;right:12px;bottom:12px;z-index:2147483647;";
    root = goc.attachShadow({ mode: "open" });
    root.innerHTML = `<style>
      .k{font:13px system-ui,sans-serif;width:290px;background:#fff;color:#222;border:1px solid #d0d5dd;border-radius:10px;box-shadow:0 4px 18px #0003;overflow:hidden}
      .t{background:#0b5fff;color:#fff;padding:6px 10px;display:flex;justify-content:space-between;cursor:pointer;font-weight:600}
      .n{padding:8px 10px;max-height:340px;overflow:auto}.u{border:1px solid #e4e7ec;border-radius:8px;padding:6px 8px;margin-bottom:6px}
      .m{font-weight:700;font-size:15px}.s{color:#555;font-size:12px}.c{height:6px;background:#e4e7ec;border-radius:3px;margin:4px 0}
      .c i{display:block;height:6px;border-radius:3px;background:#12b76a}.b{font-size:12px;color:#444}
      button{border:0;background:#0b5fff;color:#fff;border-radius:6px;padding:3px 8px;margin-top:4px;cursor:pointer}
      input{width:100%;box-sizing:border-box;padding:5px;border:1px solid #ccd;border-radius:6px}.g{color:#888;font-size:11px;margin-top:4px}
      .ton0{color:#b42318;font-weight:600}.anh img{width:46px;height:46px;object-fit:cover;border-radius:6px;margin-right:4px}
    </style><div class="k"><div class="t" id="t"><span>Gợi ý mã hàng</span><span id="x">–</span></div><div class="n" id="n"></div></div>`;
    root.getElementById("t").onclick = () => { thu = !thu; root.getElementById("n").style.display = thu ? "none" : ""; root.getElementById("x").textContent = thu ? "+" : "–"; };
    document.body.appendChild(goc);
  }
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function the(u, hash, ep) {
    const ton = u.ton == null ? "" : ` · tồn <span class="${u.ton <= 0 ? "ton0" : ""}">${u.ton}</span>`;
    const bc = u.bang_chung.map((b) => esc(b.ly_do)).join("; ");
    return `<div class="u"><div class="m">${esc(u.ma)} <span class="s">${esc(u.ten)}${ton}</span></div>
      <div class="c"><i style="width:${Math.round(u.do_chac * 100)}%"></i></div><div class="b">${bc}</div>
      <button data-ma="${esc(u.ma)}" data-nguon="${esc(ep || u.bang_chung[0].nguon)}" data-hash="${esc(hash || "")}">Đúng mã này</button></div>`;
  }
  async function ve() {
    dung(); if (!root) return;
    const n = root.getElementById("n");
    if (!bang) {
      const r = await hoi({ loai: "bang" });
      if (!r.ok) { n.innerHTML = `<div class="s">${esc(r.error || "")}. Bấm biểu tượng tiện ích để ghép với MinMin.</div>`; return; }
      bang = r.bang;
    }
    if (!hienTai) { veThanh([]); n.innerHTML = `<div class="s">Mở một hội thoại để xem gợi ý.</div>${chanDoanHtml()}`; return; }
    const ds = self.mmTra(bang, hienTai);
    let h = ds.length ? ds.slice(0, 4).map((u) => the(u)).join("") : `<div class="s">Chưa tra ra mã từ tin nhắn, quảng cáo hay bài viết của hội thoại này.</div>`;
    const daCoQc = ds.length > 0;
    veThanh(ds.filter((u) => u.bang_chung.some((b) => /^(tin_nhan|ma_ro|ma_qc|noi_dung|quang_cao|bai_viet|bi_danh)$/.test(b.nguon))).slice(0, 3).map((u) => u.ma));
    if (hienTai.ad_anh && !daCoQc) {
      const a0 = hienTai.ad_anh;
      if (!anhKq[a0]) soAnh(a0);
      const ak = anhKq[a0] || {};
      h += `<div class="s" style="margin:6px 0 2px">Quảng cáo này chưa có trong bảng. So ảnh quảng cáo:</div>`;
      if (ak.dang) h += `<div class="g">Đang so ảnh quảng cáo với mẫu...</div>`;
      else if (ak.loi) h += `<div class="g" style="color:#b42318">So ảnh quảng cáo lỗi: ${esc(ak.loi)}</div>`;
      else if (ak.kq) h += ak.kq.ung_vien.length ? ak.kq.ung_vien.map((x) => the(x, ak.kq.hash, "quang_cao")).join("") : `<div class="g">Ảnh quảng cáo chưa giống mẫu nào.</div>`;
    }
    if (hienTai.anh.length) {
      const u0 = chonAnh();
      if (u0 && !anhKq[u0]) soAnh(u0);
      const ak = anhKq[u0] || {};
      h += `<div class="anh">${hienTai.anh.slice(-4).map((u) => `<img data-u="${esc(u)}" style="${u === u0 ? "outline:2px solid #0b5fff" : "cursor:pointer"}" src="${esc(u)}">`).join("")}`;
      if (ak.dang) h += `<div class="g">Đang so ảnh với mẫu...</div>`;
      else if (ak.loi) h += `<div class="g" style="color:#b42318">So ảnh lỗi: ${esc(ak.loi)}</div>`;
      else if (ak.kq) h += ak.kq.ung_vien.length ? `<div class="s" style="margin:4px 0">Theo ảnh${ak.kq.cache ? " (đã so trước đó)" : ""}:</div>` + ak.kq.ung_vien.map((x) => the(x, ak.kq.hash)).join("")
        : `<div class="g">Ảnh này chưa giống mẫu nào. Gõ mã tay bên dưới.</div>`;
      h += `</div>`;
    }
    h += `<div style="margin-top:6px"><input id="q" placeholder="Gõ mã để tra tay, vd V33"></div><div id="kq"></div>${chanDoanHtml()}`;
    n.innerHTML = h;
    n.querySelectorAll("button[data-ma]").forEach((b) => b.onclick = async () => {
      const khoa = b.dataset.nguon === "anh" ? b.dataset.hash : /quang_cao|noi_dung/.test(b.dataset.nguon) ? (hienTai.ad_ids[0] || "") : b.dataset.nguon === "bai_viet" ? hienTai.post_id : hienTai.id;
      await hoi({ loai: "xac_nhan", du_lieu: { ma: b.dataset.ma, nguon: b.dataset.nguon, khoa } });
      b.textContent = "Đã ghi nhận"; b.disabled = true;
    });
    n.querySelectorAll("img[data-u]").forEach((im) => im.onclick = () => { anhChon = im.dataset.u; ve(); });
    const q = n.querySelector("#q");
    q.oninput = () => {
      const m = self.mmChuanMa(q.value); const s = bang.sku[m];
      n.querySelector("#kq").innerHTML = m ? (s ? the({ ma: m, ten: s[0], ton: s[1], do_chac: 1, bang_chung: [{ nguon: "tin_nhan", ly_do: "tra tay" }] }) : `<div class="s">Không có mã ${esc(m)} trong bảng</div>`) : "";
    };
  }

  // ---------------- thanh nút trả lời nhanh: ghim gần ô soạn tin, bấm là điền "/cv1213" vào ô trả lời
  let thanh = null, thanhRoot = null, thanhKhoa = "";
  const MAU_KEY = "mmGyMau";
  function layMau() { try { return localStorage.getItem(MAU_KEY) || "/c{ma}"; } catch (e) { return "/c{ma}"; } }
  function oSoan() {
    const ds = [].slice.call(document.querySelectorAll('textarea,[contenteditable="true"],[contenteditable=""]')).filter((e) => {
      const r = e.getBoundingClientRect(); return r.width > 150 && r.height > 8 && r.bottom > 0 && r.top < innerHeight && !(goc && goc.contains(e));
    });
    return ds.find((e) => /trả lời|nhập tin|reply/i.test((e.getAttribute("placeholder") || "") + (e.getAttribute("data-placeholder") || "") + (e.closest("[class*=reply],[class*=compose],[class*=editor]") ? "trả lời" : ""))) || ds.sort((a, b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top)[0] || null;
  }
  function dien(chu) {
    const o = oSoan(); if (!o) return false;
    o.focus();
    if (o.tagName === "TEXTAREA" || o.tagName === "INPUT") {
      const set = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(o), "value").set;
      set.call(o, chu); o.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      document.execCommand("selectAll", false, null);
      if (!document.execCommand("insertText", false, chu)) { o.textContent = chu; o.dispatchEvent(new Event("input", { bubbles: true })); }
    }
    return true;
  }
  function veThanh(maList) {
    const khoa = maList.join(",") + "|" + layMau();
    if (!maList.length) { if (thanh) thanh.style.display = "none"; return; }
    if (!thanh && document.body) {
      thanh = document.createElement("div");
      thanh.style.cssText = "position:fixed;z-index:2147483646;";
      thanhRoot = thanh.attachShadow({ mode: "open" });
      document.body.appendChild(thanh);
      setInterval(datThanh, 800);
    }
    if (!thanh) return;
    thanh.style.display = "";
    if (khoa !== thanhKhoa) {
      thanhKhoa = khoa;
      thanhRoot.innerHTML = `<style>.t{font:13px system-ui,sans-serif;display:flex;gap:6px;align-items:center;background:#fffbe6;border:1px solid #f0c36d;border-radius:20px;padding:4px 8px;box-shadow:0 2px 8px #0002}
        button{border:0;border-radius:14px;padding:5px 12px;background:#0b5fff;color:#fff;font-weight:700;cursor:pointer;font-size:13px}button.s{background:#e4e7ec;color:#333;padding:3px 7px;font-weight:400}.l{color:#7a5b00;font-size:12px}</style>
        <div class="t"><span class="l">Chào nhanh:</span>${maList.map((m) => `<button data-m="${esc(m)}" title="Điền ${esc(layMau().replace("{ma}", m.toLowerCase()))} vào ô trả lời">${esc(layMau().replace("{ma}", m.toLowerCase()))}</button>`).join("")}<button class="s" id="sua" title="Đổi mẫu lệnh">✎</button></div>`;
      thanhRoot.querySelectorAll("button[data-m]").forEach((b) => b.onclick = () => {
        const ok = dien(layMau().replace("{ma}", b.dataset.m.toLowerCase()));
        if (!ok) b.textContent = "Không thấy ô soạn tin";
      });
      thanhRoot.getElementById("sua").onclick = () => {
        const v = prompt("Mẫu lệnh trả lời nhanh, dùng {ma} thay cho mã (chữ thường). Ví dụ: /c{ma}", layMau());
        if (v && v.includes("{ma}")) { try { localStorage.setItem(MAU_KEY, v.trim()); } catch (e) {} thanhKhoa = ""; ve(); }
      };
    }
    datThanh();
  }
  function datThanh() {
    if (!thanh || thanh.style.display === "none") return;
    const o = oSoan();
    if (o) {
      const r = o.getBoundingClientRect();
      thanh.style.left = Math.round(r.left + 12) + "px";
      thanh.style.top = Math.max(60, Math.round(r.top - 112)) + "px";   // trên dải thẻ màu, dưới tin nhắn
    } else { thanh.style.left = "30%"; thanh.style.top = (innerHeight - 170) + "px"; }
  }
  function chonAnh() {
    if (!hienTai || !hienTai.anh.length) return null;
    return anhChon && hienTai.anh.includes(anhChon) ? anhChon : hienTai.anh[hienTai.anh.length - 1];
  }
  async function soAnh(u) {
    anhKq[u] = { dang: true };
    const r = await Promise.race([hoi({ loai: "anh", url: u }), new Promise((ok) => setTimeout(() => ok({ ok: false, error: "quá 45 giây không có trả lời (server MinMin chậm hoặc ChatGPT chưa sẵn sàng)" }), 45000))]);
    anhKq[u] = r && r.ok ? { kq: r } : { loi: (r && r.error) || "không rõ" };
    ve();
  }
  function chanDoanHtml() {
    const ad = hienTai ? hienTai.ad_ids.length : 0;
    return `<div class="g">đọc ${chanDoan.convs} hội thoại, ${chanDoan.tinNhan} tin${hienTai ? `; ad_ids=${ad}${hienTai.ad_text ? "+nội dung" : ""}, post=${hienTai.post_id ? "có" : "không"}, ảnh=${hienTai.anh.length}` : ""}</div>`;
  }
  window.__mmGyTest = { layAnh, layQuangCao, docMessages, hienTai: () => hienTai };
  document.addEventListener("DOMContentLoaded", () => { dung(); ve(); });
  setInterval(() => { bang = null; }, 10 * 60 * 1000);
})();
