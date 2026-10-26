/* fb-tai-san.js - khối "Facebook - Trang và tài khoản quảng cáo" trên trang Kết nối, màn Soi quyền
 * (hộp phủ) và ô "Hỏi Facebook về một Trang". Phase 04 của plans/fb-nhieu-tai-khoan/PLAN.md,
 * phương án A "Bảng gộp theo Trang".
 *
 * Đọc:
 *   GET  /meta/tai-san?lam_moi=0|1      -> tài khoản, Trang, TKQC gộp theo fb_id
 *   GET  /meta/soi-quyen?fb_id=         -> quyền token + danh sách chưa giao
 *   POST /meta/hoi-trang (form fb_id,q) -> trả lời bằng lời thường + nguyên văn Facebook
 *
 * Phát sự kiện (bubbles) trên phần tử mount, console.js nối:
 *   "fbts:them"           bấm "+ Thêm tài khoản Facebook"
 *   "fbts:dang-nhap-lai"  detail {fb_id, ket_noi, ly_do}  (nút Đăng nhập lại / Cấp quyền)
 *   "fbts:huong-dan"      detail {fb_id, muc}             (nút Xem hướng dẫn)
 *
 * Luật: mọi chuỗi từ máy chủ đi qua esc(); mọi chữ hiển thị đi qua t("fbts.*"). Không bao giờ
 * hiện token. Phần dựng HTML là hàm THUẦN để test node chạy không cần DOM. Không dùng em dash. */
(function () {
  "use strict";
  var W = typeof window !== "undefined" ? window : null;
  var VI_NODE = null;
  function t(k, b) {
    if (W && W.t) return W.t(k, b);
    var s = null;
    try { VI_NODE = VI_NODE || require("./i18n/vi.json"); s = VI_NODE[k]; } catch (e) {}
    if (s == null) return k;
    return String(s).replace(/\{(\w+)\}/g, function (m, n) { return b && b[n] != null ? String(b[n]) : m; });
  }
  function ic(ten) { return W && W.ic ? W.ic(ten) : ""; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  async function api(url, opt) {
    var r = await fetch(url, Object.assign({ credentials: "same-origin" }, opt || {}));
    var d = {};
    try { d = await r.json(); } catch (e) {}
    if (!r.ok || d.ok === false) {
      var l = d.loi;
      if (Array.isArray(l)) l = l.join("; ");
      throw new Error(l || d.error || d.detail || ("HTTP " + r.status));
    }
    return d;
  }

  // ================================================================ HÀM THUẦN
  // Khoá viết tường minh (không ghép chuỗi) để test i18n quét được từng khoá.
  function nhanVaiTro(vt) {
    if (!vt) return t("fbts.vt_chua_co");   // thấy Trang trong BM nhưng chưa được gán vai trò / chưa giao
    return { quan_tri: t("fbts.vt_quan_tri"), bien_tap: t("fbts.vt_bien_tap"), kiem_duyet: t("fbts.vt_kiem_duyet"),
      quang_cao: t("fbts.vt_quang_cao"), phan_tich: t("fbts.vt_phan_tich") }[vt] || t("fbts.vt_khac");
  }
  function tenBm(b) {
    var s = String(b || "").trim();
    return /^(BM|Business)\b/i.test(s) ? s : "BM " + s;
  }
  function nhanNguon(n) {
    if (!n) return "";
    // Tên BM thường đã có chữ "BM" ở đầu ("BM Halimi") - đừng thành "qua BM BM Halimi".
    if (n.qua === "bm") return n.bm_ten ? t("fbts.qua_bm", { bm: tenBm(n.bm_ten) }) : t("fbts.qua_bm_trong");
    return t("fbts.ca_nhan");
  }
  function thieuAds(tk) {
    var q = tk && Array.isArray(tk.thieu_quyen) ? tk.thieu_quyen : [];
    return q.some(function (x) { return x && (x.ma === "ads_management" || x === "ads_management"); });
  }
  // Chip trạng thái của một tài khoản: token hỏng thắng thiếu quyền, thiếu quyền thắng sắp hết hạn.
  function chipToken(tk) {
    var tt = tk && tk.token ? tk.token.trang_thai : "";
    if (tt === "loi" || tt === "het_han") return { cls: "bad", chu: t("fbts.tk_loi") };
    if (thieuAds(tk)) return { cls: "warn", chu: t("fbts.tk_thieu_ads") };
    if (tt === "sap_het") return { cls: "warn", chu: t("fbts.tk_sap_het") };
    return { cls: "ok", chu: t("fbts.tk_tot") };
  }
  function boDau(s) {
    return String(s == null ? "" : s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/đ/g, "d").trim();
  }
  // Lọc theo tên hoặc id, không phân biệt hoa thường và dấu.
  function locDong(rows, q) {
    var arr = Array.isArray(rows) ? rows.filter(function (r) { return r && typeof r === "object"; }) : [];
    var k = boDau(q);
    if (!k) return arr;
    return arr.filter(function (r) { return boDau(r.ten).indexOf(k) >= 0 || boDau(r.id).indexOf(k) >= 0; });
  }
  function canXuLy(rows) { return (Array.isArray(rows) ? rows : []).filter(function (r) { return r && r.van_de; }); }
  function demSo(d) {
    var tr = d && Array.isArray(d.trang) ? d.trang : [], qc = d && Array.isArray(d.tkqc) ? d.tkqc : [];
    return { trang: tr.length, tkqc: qc.length, can: canXuLy(tr).length + canXuLy(qc).length };
  }
  // 1250000 -> "1.250.000 đ". Rỗng/không phải số -> "". Tự nhóm để kết quả giống nhau mọi máy.
  function tien(v) {
    if (v == null || v === "") return "";
    var n = typeof v === "number" ? v : parseFloat(String(v).replace(/[^\d.\-]/g, ""));
    if (!isFinite(n)) return "";
    var am = n < 0, s = String(Math.round(Math.abs(n)));
    s = s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    return (am ? "-" : "") + s + " đ";
  }
  function chipHoiTrang(kq) {
    return {
      giao: { cls: "ok", chu: t("fbts.kq_giao") },
      giao_khong_dang: { cls: "warn", chu: t("fbts.kq_giao_khong_dang") },
      chua_giao_bm: { cls: "warn", chu: t("fbts.kq_chua_giao_bm") },
      khong_thay_quyen: { cls: "warn", chu: t("fbts.kq_khong_thay_quyen") },
      khong_tim_thay: { cls: "bad", chu: t("fbts.kq_khong_tim_thay") },
      thieu_quyen: { cls: "bad", chu: t("fbts.kq_thieu_quyen") },
      loi_token: { cls: "bad", chu: t("fbts.kq_loi_token") },
      can_id: { cls: "warn", chu: t("fbts.kq_can_id") },
    }[kq] || { cls: "warn", chu: t("fbts.kq_khac") };
  }
  function chipLyDo(ma) {
    return {
      chua_giao_bm: { cls: "warn", chu: t("fbts.ld_chua_giao") },
      khong_dang: { cls: "warn", chu: t("fbts.ld_khong_dang") },
      thieu_quyen: { cls: "bad", chu: t("fbts.ld_thieu_quyen") },
    }[ma] || { cls: "warn", chu: t("fbts.ld_khac") };
  }
  function nhanNut(nut) {
    return { dang_nhap_lai: t("fbts.nut_dang_nhap_lai"), cap_quyen: t("fbts.nut_cap_quyen"),
      huong_dan: t("fbts.nut_huong_dan") }[nut] || t("fbts.nut_huong_dan");
  }
  function hai(n) { return (n < 10 ? "0" : "") + n; }
  function gioPhut(luc) {
    if (!luc) return "";
    var d = new Date(luc);
    return isNaN(d.getTime()) ? "" : hai(d.getHours()) + ":" + hai(d.getMinutes());
  }
  function dsTk(d) {
    return d && Array.isArray(d.tai_khoan) ? d.tai_khoan.filter(function (x) { return x && x.fb_id; }) : [];
  }
  function tenTk(tk) { return (tk && (tk.ten || tk.ten_fb || tk.fb_id)) || ""; }
  function bangTen(d) {
    var m = {};
    dsTk(d).forEach(function (tk) { m[tk.fb_id] = tenTk(tk); });
    return m;
  }
  // Tài khoản nên soi khi bấm "Cách sửa" trên một dòng: tài khoản thấy mà chưa giao, rồi tài
  // khoản đầu tiên có nguồn, rồi tài khoản đầu danh sách.
  function tkCanSoi(row, d) {
    var nguon = (row && row.nguon) || {};
    var ids = Object.keys(nguon);
    var chua = ids.filter(function (k) { return nguon[k] && nguon[k].giao === false; });
    if (chua.length) return chua[0];
    if (ids.length) return ids[0];
    var tk = dsTk(d)[0];
    return tk ? tk.fb_id : "";
  }
  function chip(c, extra) {
    return '<span class="fbts-chip ' + esc(c.cls) + (extra ? " " + extra : "") + '">' + esc(c.chu) + '</span>';
  }
  function stateMoi() { return { tab: "trang", q: "", dangTai: false, loiTai: "" }; }

  // ================================================================ MẢNH HTML: KHỐI CHÍNH
  function htmlDau(d, st) {
    var n = dsTk(d).length;
    return '<header class="fbts-dau"><div class="fbts-dau-chu">' +
      '<h3 class="fbts-h3">' + esc(t("fbts.tieu_de")) + '</h3>' +
      '<span class="fbts-phu">' + esc(t("fbts.phu", { n: n })) + '</span></div>' +
      '<div class="fbts-dau-nut">' +
        '<button type="button" class="fbts-nut-phu" data-fbts="quet"' + (st.dangTai ? " disabled" : "") + '>' +
          esc(st.dangTai ? t("fbts.dang_quet") : t("fbts.quet_lai")) + '</button>' +
        '<button type="button" class="fbts-nut-chinh" data-fbts="them">' + esc(t("fbts.them_tk")) + '</button>' +
      '</div></header>';
  }
  function htmlTheTk(tk) {
    var c = chipToken(tk);
    var ten = tenTk(tk);
    var chuDau = String(ten).trim().charAt(0).toUpperCase() || "?";
    return '<li class="fbts-tk">' +
      '<span class="fbts-avatar" aria-hidden="true">' + esc(chuDau) + '</span>' +
      '<div class="fbts-tk-chu">' +
        '<div class="fbts-tk-dong"><b class="fbts-tk-ten">' + esc(ten) + '</b>' + chip(c) + '</div>' +
        '<span class="fbts-phu">' + esc(t("fbts.tk_dem", { trang: +tk.so_trang || 0, tkqc: +tk.so_tkqc || 0, can: +tk.can_xu_ly || 0 })) + '</span>' +
      '</div>' +
      '<button type="button" class="fbts-nut-phu fbts-nut-nho" data-fbts="soi" data-fb="' + esc(tk.fb_id) + '">' +
        esc(t("fbts.soi_quyen")) + '</button></li>';
  }
  function htmlTab(d, st) {
    var s = demSo(d);
    var tabs = [["trang", t("fbts.tab_trang", { n: s.trang })], ["tkqc", t("fbts.tab_tkqc", { n: s.tkqc })],
      ["can", t("fbts.tab_can", { n: s.can })]];
    return '<div class="fbts-tabs" role="tablist" aria-label="' + esc(t("fbts.tab_aria")) + '">' + tabs.map(function (x) {
      var on = st.tab === x[0];
      return '<button type="button" role="tab" class="fbts-tab' + (on ? " on" : "") + '" data-fbts="tab" data-tab="' + x[0] +
        '" aria-selected="' + (on ? "true" : "false") + '" aria-pressed="' + (on ? "true" : "false") + '">' + esc(x[1]) + '</button>';
    }).join("") + '</div>';
  }
  function oTrang(n) {
    if (!n) return '<span class="fbts-mo">-</span>';
    return '<span class="fbts-o-1">' + esc(nhanVaiTro(n.vai_tro)) + '</span>' +
      '<span class="fbts-o-2">' + esc(nhanNguon(n)) + '</span>' +
      (n.giao === false ? chip({ cls: "warn", chu: t("fbts.chua_giao_minmin") }, "fbts-chip-o") : "");
  }
  function oTkqc(n) {
    if (!n) return '<span class="fbts-mo">-</span>';
    return '<span class="fbts-o-1">' + esc(t("fbts.co_quyen")) + '</span>' +
      '<span class="fbts-o-2">' + esc(nhanNguon(n)) + '</span>' +
      (n.giao === false ? chip({ cls: "warn", chu: t("fbts.chua_giao_minmin") }, "fbts-chip-o") : "");
  }
  // loai = "trang" | "tkqc". Bảng: cột đầu tên, mỗi tài khoản Facebook một cột, cột MinMin, cột nút.
  function htmlBang(rows, loai, d) {
    var tks = dsTk(d), ten = bangTen(d);
    var dau = '<tr><th scope="col">' + esc(loai === "trang" ? t("fbts.cot_trang") : t("fbts.cot_tkqc")) + '</th>' +
      tks.map(function (tk) { return '<th scope="col">' + esc(tenTk(tk)) + '</th>'; }).join("") +
      '<th scope="col">' + esc(loai === "trang" ? t("fbts.cot_dang_bang") : t("fbts.cot_dung")) + '</th>' +
      '<th scope="col"><span class="fbts-an">' + esc(t("fbts.cot_nut")) + '</span></th></tr>';
    var than = rows.map(function (r) {
      var nguon = r.nguon || {};
      var cuoi;
      if (loai === "trang") {
        cuoi = r.dang_bang ? chip({ cls: "ok", chu: ten[r.dang_bang] || r.dang_bang }) : chip({ cls: "bad", chu: t("fbts.chua_dang_duoc") });
      } else if (r.dung && r.van_de === "thieu_quyen_ghi") {
        cuoi = chip({ cls: "warn", chu: t("fbts.chi_doc", { ten: ten[r.dung] || r.dung }) });
      } else {
        cuoi = r.dung ? chip({ cls: "ok", chu: ten[r.dung] || r.dung }) : chip({ cls: "bad", chu: t("fbts.chua_dung_duoc") });
      }
      var nut = r.van_de ? '<button type="button" class="fbts-nut-phu fbts-nut-nho" data-fbts="soi" data-fb="' +
        esc(tkCanSoi(r, d)) + '">' + esc(t("fbts.cach_sua")) + '</button>' : "";
      return '<tr class="' + (r.van_de ? "fbts-van-de" : "") + '">' +
        '<th scope="row"><span class="fbts-o-1">' + esc(r.ten || r.id) + '</span><span class="fbts-o-2">' + esc(r.id) + '</span></th>' +
        tks.map(function (tk) {
          return '<td>' + (loai === "trang" ? oTrang(nguon[tk.fb_id]) : oTkqc(nguon[tk.fb_id])) + '</td>';
        }).join("") +
        '<td>' + cuoi + '</td><td class="fbts-o-nut">' + nut + '</td></tr>';
    }).join("");
    return '<div class="fbts-bang-hop"><table class="fbts-bang"><thead>' + dau + '</thead><tbody>' + than + '</tbody></table></div>';
  }
  function htmlVung(d, st) {
    var tr = locDong(d && d.trang, st.q), qc = locDong(d && d.tkqc, st.q);
    var rong = function (chu) { return '<div class="fbts-rong">' + esc(st.q ? t("fbts.khong_khop") : chu) + '</div>'; };
    if (st.tab === "tkqc") return qc.length ? htmlBang(qc, "tkqc", d) : rong(t("fbts.rong_tkqc"));
    if (st.tab === "can") {
      var a = canXuLy(tr), b = canXuLy(qc);
      if (!a.length && !b.length) return rong(t("fbts.rong_can"));
      return (a.length ? '<h4 class="fbts-h4">' + esc(t("fbts.nhom_trang", { n: a.length })) + '</h4>' + htmlBang(a, "trang", d) : "") +
        (b.length ? '<h4 class="fbts-h4">' + esc(t("fbts.nhom_tkqc", { n: b.length })) + '</h4>' + htmlBang(b, "tkqc", d) : "");
    }
    return tr.length ? htmlBang(tr, "trang", d) : rong(t("fbts.rong_trang"));
  }
  // Hàm THUẦN: dữ liệu tai_san + state -> HTML cả khối.
  function htmlKhoi(d, st) {
    st = Object.assign(stateMoi(), st || {});
    var tks = dsTk(d);
    var loi = d && Array.isArray(d.loi) && d.loi.length
      ? '<div class="fbts-canh" role="status">' + esc(t("fbts.canh_quet", { loi: d.loi.join("; ") })) + '</div>' : "";
    var loiTai = st.loiTai ? '<div class="fbts-canh" role="alert">' + esc(t("fbts.loi_tai", { loi: st.loiTai })) + '</div>' : "";
    if (!tks.length) {
      return '<section class="fbts">' + htmlDau(d, st) + loiTai + loi +
        '<div class="fbts-rong">' + esc(t("fbts.chua_co_tk")) + '</div></section>';
    }
    return '<section class="fbts">' + htmlDau(d, st) + loiTai + loi +
      '<ul class="fbts-tks">' + tks.map(htmlTheTk).join("") + '</ul>' +
      '<div class="fbts-thanh">' + htmlTab(d, st) +
        '<input type="search" class="fbts-o fbts-tim" data-fbts-o="q" value="' + esc(st.q) + '" placeholder="' +
          esc(t("fbts.tim_ph")) + '" aria-label="' + esc(t("fbts.tim_aria")) + '">' +
      '</div>' +
      '<div class="fbts-vung" role="tabpanel">' + htmlVung(d, st) + '</div>' +
      '<p class="fbts-chu-thich">' + esc(t("fbts.chu_thich")) + '</p></section>';
  }

  // ================================================================ MẢNH HTML: SOI QUYỀN
  function htmlHoiKetQua(r) {
    if (!r) return "";
    if (r.dangHoi) return '<div class="fbts-phu">' + esc(t("fbts.dang_hoi")) + '</div>';
    if (r.loiGui) return '<div class="fbts-canh" role="alert">' + esc(t("fbts.loi_hoi", { loi: r.loiGui })) + '</div>';
    var c = chipHoiTrang(r.ket_qua);
    var nv = r.nguyen_van == null ? "" : (typeof r.nguyen_van === "string" ? r.nguyen_van : JSON.stringify(r.nguyen_van, null, 2));
    return '<div class="fbts-hoi-kq" role="status">' +
      '<div class="fbts-tk-dong"><b class="fbts-tk-ten">' + esc(r.ten || r.id || t("fbts.khong_ten")) + '</b>' + chip(c) +
        (r.id ? '<span class="fbts-phu">' + esc(r.id) + '</span>' : "") + '</div>' +
      (r.ly_do ? '<p class="fbts-p">' + esc(r.ly_do) + '</p>' : "") +
      (r.cach_sua ? '<p class="fbts-p">' + esc(t("fbts.cach_sua_la", { cach: r.cach_sua })) + '</p>' : "") +
      (nv ? '<details class="fbts-nv"><summary>' + esc(t("fbts.nguyen_van")) + '</summary><pre><code>' + esc(nv) + '</code></pre></details>' : "") +
      '</div>';
  }
  function oSo(nhan, so, canh) {
    return '<div class="fbts-so"><span class="fbts-so-nhan">' + esc(nhan) + '</span>' +
      '<b class="fbts-so-gt' + (canh && so > 0 ? " warn" : "") + '">' + esc(so) + '</b></div>';
  }
  // Hàm THUẦN: dữ liệu soi_quyen + state hộp -> HTML trong hộp (không gồm khung phủ).
  function htmlSoi(d, st) {
    st = st || {};
    var tk = (d && d.tai_khoan) || {};
    var ten = tenTk(tk) || st.fb_id || "";
    var dau = '<header class="fbts-hop-dau"><div class="fbts-dau-chu">' +
      '<h3 class="fbts-h3" id="fbts-soi-tieu-de">' + esc(t("fbts.soi_tieu_de", { ten: ten })) + '</h3>' +
      '<span class="fbts-phu">' + esc(d && d.kiem_luc ? t("fbts.soi_phu", { gio: gioPhut(d.kiem_luc) }) : t("fbts.soi_phu_0")) + '</span></div>' +
      '<div class="fbts-dau-nut">' +
        '<button type="button" class="fbts-nut-phu" data-fbts="soi_lai"' + (st.dangTai ? " disabled" : "") + '>' +
          esc(st.dangTai ? t("fbts.dang_soi") : t("fbts.soi_lai")) + '</button>' +
        '<button type="button" class="fbts-nut-chinh" data-fbts="dang_nhap_lai">' + esc(t("fbts.dang_nhap_lai")) + '</button>' +
        '<button type="button" class="fbts-dong" data-fbts="dong" aria-label="' + esc(t("fbts.dong")) + '">' + (ic("x") || "x") + '</button>' +
      '</div></header>';
    if (st.loiTai) {
      return dau + '<div class="fbts-canh" role="alert">' + esc(t("fbts.loi_soi", { loi: st.loiTai })) + '</div>';
    }
    if (!d) return dau + '<div class="fbts-phu">' + esc(t("fbts.dang_soi")) + '</div>';
    var chua = Array.isArray(d.chua_giao) ? d.chua_giao.filter(function (x) { return x && typeof x === "object"; }) : [];
    var demChua = function (loai) { return chua.filter(function (x) { return x.loai === loai && x.ly_do_ma === "chua_giao_bm"; }).length; };
    var trChua = d.trang_chua_giao != null ? +d.trang_chua_giao || 0 : demChua("trang");
    var qcChua = d.tkqc_chua_giao != null ? +d.tkqc_chua_giao || 0 : demChua("tkqc");
    var so = '<div class="fbts-so-hang">' + oSo(t("fbts.so_trang_giao"), +d.trang_giao || 0, false) +
      oSo(t("fbts.so_trang_chua"), trChua, true) + oSo(t("fbts.so_tkqc_giao"), +d.tkqc_giao || 0, false) +
      oSo(t("fbts.so_tkqc_chua"), qcChua, true) + '</div>';
    var quyen = (Array.isArray(d.quyen) ? d.quyen : []).filter(function (q) { return q && q.ma; }).map(function (q) {
      if (q.co === true) return '<span class="fbts-chip ok">' + ic("check") + esc(q.ten || q.ma) + '</span>';
      if (q.co === false) return '<span class="fbts-chip bad">' + ic("x") + esc((q.ten || q.ma) + (q.de_lam ? " - " + q.de_lam : "")) + '</span>';
      return '<span class="fbts-chip mo">' + esc(t("fbts.quyen_chua_ro", { ten: q.ten || q.ma })) + '</span>';
    }).join("");
    var khuQuyen = '<section class="fbts-khu"><h4 class="fbts-h4">' + esc(t("fbts.quyen_dang_co")) + '</h4>' +
      '<div class="fbts-chips">' + (quyen || '<span class="fbts-phu">' + esc(t("fbts.quyen_trong")) + '</span>') + '</div>' +
      (d.ung_dung ? '<span class="fbts-phu">' + esc(t("fbts.ung_dung", { ten: d.ung_dung })) + '</span>' : "") + '</section>';
    var dong = chua.map(function (x, i) {
      var c = chipLyDo(x.ly_do_ma);
      var phu = [x.loai === "tkqc" ? t("fbts.loai_tkqc") : t("fbts.loai_trang")];
      if (x.vai_tro && x.loai !== "tkqc") phu.push(nhanVaiTro(x.vai_tro));
      if (x.qua) phu.push(nhanNguon(x));
      return '<li class="fbts-chua">' +
        '<div class="fbts-chua-ten"><b>' + esc(x.ten || x.id) + '</b><span class="fbts-phu">' + esc(phu.join(" · ")) + '</span></div>' +
        '<div class="fbts-chua-ly-do">' + chip(c) +
          (x.ly_do ? '<span class="fbts-p">' + esc(x.ly_do) + '</span>' : "") +
          (x.cach_sua ? '<span class="fbts-phu">' + esc(x.cach_sua) + '</span>' : "") + '</div>' +
        '<div class="fbts-chua-nut"><button type="button" class="fbts-nut-phu fbts-nut-nho" data-fbts="nut_chua" data-i="' + i +
          '" data-nut="' + esc(x.nut || "huong_dan") + '">' + esc(nhanNut(x.nut)) + '</button></div></li>';
    }).join("");
    var khuChua = '<section class="fbts-khu"><h4 class="fbts-h4">' + esc(t("fbts.chua_giao_tieu_de")) + '</h4>' +
      (dong ? '<ul class="fbts-ds-chua">' + dong + '</ul>' : '<div class="fbts-rong">' + esc(t("fbts.chua_giao_rong")) + '</div>') +
      '<p class="fbts-chu-thich">' + esc(t("fbts.ghi_chu_that")) + '</p></section>';
    var khuHoi = '<section class="fbts-khu"><h4 class="fbts-h4">' + esc(t("fbts.hoi_tieu_de")) + '</h4>' +
      '<form class="fbts-hoi" data-fbts-form="hoi">' +
        '<label class="fbts-nhan" for="fbts-hoi-q">' + esc(t("fbts.hoi_nhan")) + '</label>' +
        '<div class="fbts-hoi-hang"><input id="fbts-hoi-q" class="fbts-o" name="q" autocomplete="off" value="' + esc(st.q || "") +
          '" placeholder="' + esc(t("fbts.hoi_ph")) + '">' +
        '<button type="submit" class="fbts-nut-phu"' + (st.hoi && st.hoi.dangHoi ? " disabled" : "") + '>' + esc(t("fbts.hoi_nut")) + '</button></div>' +
      '</form><div class="fbts-hoi-vung">' + htmlHoiKetQua(st.hoi) + '</div></section>';
    var loi = Array.isArray(d.loi) && d.loi.length ? '<div class="fbts-canh" role="status">' + esc(t("fbts.canh_quet", { loi: d.loi.join("; ") })) + '</div>' : "";
    return dau + loi + so + khuQuyen + khuChua + khuHoi;
  }

  // ================================================================ DOM: KHỐI CHÍNH
  var _mount = null;
  function phat(ten, detail) {
    var noi = (_mount && _mount.isConnected) ? _mount : document;
    try { noi.dispatchEvent(new CustomEvent(ten, { bubbles: true, detail: detail || {} })); } catch (e) {}
  }
  function ve(el) { var st = el._fbts; el.innerHTML = htmlKhoi(st.data, st); }
  function veVung(el) {
    var st = el._fbts, v = el.querySelector(".fbts-vung");
    if (v) v.innerHTML = htmlVung(st.data, st); else ve(el);
  }
  async function tai(el, lamMoi) {
    var st = el._fbts;
    if (st.dangTai) return;
    st.dangTai = true;
    if (st.data) ve(el);
    try {
      var d = await api("/meta/tai-san?lam_moi=" + (lamMoi ? "1" : "0"));
      if (!el.isConnected) return;
      st.data = d; st.loiTai = "";
    } catch (e) {
      if (!el.isConnected) return;
      st.loiTai = e.message || "";
    } finally {
      st.dangTai = false;
    }
    ve(el);
  }
  function noiKhoi(el) {
    el.onclick = function (ev) {
      var nut = ev.target && ev.target.closest ? ev.target.closest("[data-fbts]") : null;
      if (!nut || !el.contains(nut) || nut.disabled) return;
      var st = el._fbts, loai = nut.dataset.fbts;
      if (loai === "quet") tai(el, true);
      else if (loai === "them") phat("fbts:them", {});
      else if (loai === "tab") { st.tab = nut.dataset.tab || "trang"; ve(el); var b = el.querySelector('.fbts-tab.on'); if (b) b.focus(); }
      else if (loai === "soi") moSoiQuyen(nut.dataset.fb || "");
    };
    el.oninput = function (ev) {
      var o = ev.target;
      if (o && o.dataset && o.dataset.fbtsO === "q") { el._fbts.q = o.value; veVung(el); }
    };
    // Mũi tên trái/phải giữa các tab (mẫu tablist).
    el.onkeydown = function (ev) {
      var tab = ev.target && ev.target.closest ? ev.target.closest(".fbts-tab") : null;
      if (!tab || (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft")) return;
      var ds = Array.prototype.slice.call(el.querySelectorAll(".fbts-tab"));
      var i = ds.indexOf(tab) + (ev.key === "ArrowRight" ? 1 : -1);
      var dich = ds[(i + ds.length) % ds.length];
      if (dich) { ev.preventDefault(); dich.click(); }
    };
  }
  function mount(el) {
    if (!el) return;
    _mount = el;
    if (!el._fbts) el._fbts = stateMoi();
    if (!el._fbts.data) el.innerHTML = '<section class="fbts">' + htmlDau(null, el._fbts) +
      '<div class="fbts-phu">' + esc(t("fbts.dang_tai")) + '</div></section>';
    noiKhoi(el);
    return tai(el, false);
  }

  // ================================================================ DOM: HỘP SOI QUYỀN
  var _hop = null;   // {phu, hop, st, truoc}
  function veHop() {
    if (!_hop) return;
    _hop.hop.innerHTML = htmlSoi(_hop.st.data, _hop.st);
  }
  function veHoi() {
    if (!_hop) return;
    var v = _hop.hop.querySelector(".fbts-hoi-vung");
    if (v) v.innerHTML = htmlHoiKetQua(_hop.st.hoi);
    var b = _hop.hop.querySelector('.fbts-hoi button[type="submit"]');
    if (b) b.disabled = !!(_hop.st.hoi && _hop.st.hoi.dangHoi);
  }
  async function taiSoi() {
    var h = _hop;
    if (!h || h.st.dangTai) return;
    h.st.dangTai = true; h.st.loiTai = "";
    veHop();
    try {
      var d = await api("/meta/soi-quyen?fb_id=" + encodeURIComponent(h.st.fb_id));
      if (_hop !== h) return;
      h.st.data = d;
    } catch (e) {
      if (_hop !== h) return;
      h.st.loiTai = e.message || "";
    } finally {
      h.st.dangTai = false;
    }
    veHop();
  }
  async function hoi(q) {
    var h = _hop;
    if (!h) return;
    h.st.q = q;
    if (!String(q || "").trim()) { h.st.hoi = { ket_qua: "can_id", ly_do: t("fbts.hoi_trong") }; veHoi(); return; }
    h.st.hoi = { dangHoi: true };
    veHoi();
    try {
      var body = new URLSearchParams();
      body.append("fb_id", h.st.fb_id);
      body.append("q", String(q).trim());
      var r = await api("/meta/hoi-trang", { method: "POST", body: body });
      if (_hop !== h) return;
      h.st.hoi = r;
    } catch (e) {
      if (_hop !== h) return;
      h.st.hoi = { loiGui: e.message || "" };
    }
    veHoi();
  }
  function ketNoiCua(h) {
    var tk = (h.st.data && h.st.data.tai_khoan) || {};
    if (!tk.fb_id && _mount && _mount._fbts && _mount._fbts.data) {
      tk = dsTk(_mount._fbts.data).filter(function (x) { return x.fb_id === h.st.fb_id; })[0] || {};
    }
    return Array.isArray(tk.ket_noi) ? tk.ket_noi : [];
  }
  function dongSoi() {
    if (!_hop) return;
    var h = _hop;
    _hop = null;
    document.removeEventListener("keydown", h.phim, true);
    if (h.phu.parentNode) h.phu.parentNode.removeChild(h.phu);
    try { if (h.truoc && h.truoc.focus && h.truoc.isConnected) h.truoc.focus(); } catch (e) {}
  }
  var CHON_FOCUS = 'button:not([disabled]), [href], input:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
  function moSoiQuyen(fb_id) {
    if (typeof document === "undefined") return;
    if (_hop) dongSoi();
    var phu = document.createElement("div");
    phu.className = "fbts-phu-man";
    var hop = document.createElement("div");
    hop.className = "fbts-hop";
    hop.setAttribute("role", "dialog");
    hop.setAttribute("aria-modal", "true");
    hop.setAttribute("aria-labelledby", "fbts-soi-tieu-de");
    hop.tabIndex = -1;
    phu.appendChild(hop);
    var h = { phu: phu, hop: hop, truoc: document.activeElement, st: { fb_id: String(fb_id || ""), data: null, q: "", hoi: null } };
    h.phim = function (ev) {
      if (_hop !== h) return;
      if (ev.key === "Escape") { ev.preventDefault(); dongSoi(); return; }
      if (ev.key !== "Tab") return;
      var ds = Array.prototype.slice.call(hop.querySelectorAll(CHON_FOCUS)).filter(function (x) { return x.offsetParent !== null || x === document.activeElement; });
      if (!ds.length) { ev.preventDefault(); hop.focus(); return; }
      var dau = ds[0], cuoi = ds[ds.length - 1];
      if (!hop.contains(document.activeElement)) { ev.preventDefault(); dau.focus(); }
      else if (ev.shiftKey && document.activeElement === dau) { ev.preventDefault(); cuoi.focus(); }
      else if (!ev.shiftKey && document.activeElement === cuoi) { ev.preventDefault(); dau.focus(); }
    };
    phu.addEventListener("mousedown", function (ev) { if (ev.target === phu) dongSoi(); });
    hop.addEventListener("click", function (ev) {
      var nut = ev.target && ev.target.closest ? ev.target.closest("[data-fbts]") : null;
      if (!nut || nut.disabled) return;
      var loai = nut.dataset.fbts;
      if (loai === "dong") dongSoi();
      else if (loai === "soi_lai") taiSoi();
      else if (loai === "dang_nhap_lai") phat("fbts:dang-nhap-lai", { fb_id: h.st.fb_id, ket_noi: ketNoiCua(h), ly_do: "" });
      else if (loai === "nut_chua") {
        var ds = (h.st.data && Array.isArray(h.st.data.chua_giao)) ? h.st.data.chua_giao.filter(function (x) { return x && typeof x === "object"; }) : [];
        var muc = ds[+nut.dataset.i] || {};
        if (nut.dataset.nut === "huong_dan") phat("fbts:huong-dan", { fb_id: h.st.fb_id, muc: muc });
        else phat("fbts:dang-nhap-lai", { fb_id: h.st.fb_id, ket_noi: ketNoiCua(h), ly_do: muc.ly_do_ma || nut.dataset.nut });
      }
    });
    hop.addEventListener("input", function (ev) { if (ev.target && ev.target.id === "fbts-hoi-q") h.st.q = ev.target.value; });
    hop.addEventListener("submit", function (ev) {
      if (!ev.target || ev.target.getAttribute("data-fbts-form") !== "hoi") return;
      ev.preventDefault();
      var o = hop.querySelector("#fbts-hoi-q");
      hoi(o ? o.value : "");
    });
    document.addEventListener("keydown", h.phim, true);
    _hop = h;
    veHop();
    document.body.appendChild(phu);
    var dau = hop.querySelector('[data-fbts="dong"]');
    try { (dau || hop).focus(); } catch (e) {}
    return taiSoi();
  }

  var API = {
    mount: mount, moSoiQuyen: moSoiQuyen, dongSoiQuyen: dongSoi,
    // hàm thuần cho test node
    nhanVaiTro: nhanVaiTro, nhanNguon: nhanNguon, chipToken: chipToken, locDong: locDong, demSo: demSo,
    canXuLy: canXuLy, tien: tien, chipHoiTrang: chipHoiTrang, chipLyDo: chipLyDo, nhanNut: nhanNut,
    gioPhut: gioPhut, tkCanSoi: tkCanSoi, htmlKhoi: htmlKhoi, htmlSoi: htmlSoi, htmlHoiKetQua: htmlHoiKetQua,
    _esc: esc,
  };
  if (W) W.FbTaiSan = API;
  if (typeof module !== "undefined" && module.exports) module.exports = API;
})();
