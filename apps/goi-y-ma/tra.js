// Tra mã ngay trên máy: cùng luật với server/goi_y_ma.py (đổi một bên thì đổi cả hai bên).
(function (g) {
  function chuanMa(s) {
    return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D")
      .replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  }
  const TRONG_SO = { tin_nhan: 1, quang_cao: 0.95, chien_dich: 0.9, noi_dung: 0.85, ma_ro: 0.95, bai_viet: 0.8, bi_danh: 0.7 };
  function maTrongChu(bang, text) {
    const thay = new Set(), kq = [];
    (String(text || "").normalize("NFC").match(/[A-Za-zĐđ]{0,4}[\s-]?\d{1,6}[A-Za-z]{0,2}/g) || []).forEach((t) => {
      const m = chuanMa(t); if (m) thay.add(m);
    });
    thay.forEach((m) => {
      if (bang.sku[m]) kq.push([m, "tin_nhan", "khách nhắn mã " + m]);
      else if (bang.bi_danh && bang.bi_danh[m]) kq.push([bang.bi_danh[m], "bi_danh", m + " là tên gọi khác của " + bang.bi_danh[m]]);
    });
    return kq;
  }
  function theoKhoa(map, id) {
    if (!id) return null;
    id = String(id);
    return map[id] || map[id.split("_").pop()] || null;
  }
  // ctx: {text, ad_ids:[], post_id}
  g.mmTra = function (bang, ctx) {
    const gom = {};
    const them = (ma, nguon, ly) => {
      const d = gom[ma] || (gom[ma] = { ma, bang_chung: [], diem: [] });
      d.bang_chung.push({ nguon, ly_do: ly }); d.diem.push(TRONG_SO[nguon] || 0.5);
    };
    if (!bang || !bang.sku) return [];
    maTrongChu(bang, ctx.text).forEach(([m, n, l]) => them(m, n, l));
    (ctx.ma_ro || []).forEach((m, i) => {
      m = chuanMa(m); if (!m) return;
      const ma = bang.sku[m] ? m : (bang.bi_danh && bang.bi_danh[m]) || m;
      them(ma, "ma_ro", "tin nhắn ghi rõ mã " + ma + (bang.sku[ma] ? "" : " (chưa có trong bảng tồn)"));
      gom[ma].diem[gom[ma].diem.length - 1] -= 0.01 * i;
    });
    if (ctx.ad_text) maTrongChu(bang, ctx.ad_text).forEach(([m]) => them(m, "noi_dung", "nội dung quảng cáo nhắc mã " + m));
    (ctx.ad_ids || []).forEach((a) => { const m = theoKhoa(bang.ad || {}, a); if (m) them(m, "quang_cao", "quảng cáo " + a); });
    const p = theoKhoa(bang.post || {}, ctx.post_id); if (p) them(p, "bai_viet", "bài viết " + ctx.post_id);
    return Object.values(gom).map((d) => {
      d.diem.sort((a, b) => b - a);
      const s = bang.sku[d.ma] || null;
      return { ma: d.ma, ten: s ? s[0] : "", ton: s ? s[1] : null, co_trong_sku: !!s, bang_chung: d.bang_chung,
        do_chac: Math.min(0.99, d.diem[0] + 0.05 * (d.diem[1] || 0)) };
    }).sort((a, b) => b.do_chac - a.do_chac || (a.ma < b.ma ? -1 : 1));
  };
  g.mmChuanMa = chuanMa;
})(typeof self !== "undefined" ? self : globalThis);
