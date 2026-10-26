/* doi-ai.js - khu "Đội AI" ở đầu trang Bảng việc, phương án 1 "Dòng việc theo job" (Phase 04
 * của plans/doi-ai-gate/PLAN.md).
 *
 * Đọc GET /kanban/jobs?brain=<brain> (hình dạng `jobs_view` trong hợp đồng) và vẽ:
 *   - tiêu đề khu "Đội AI" + dòng phụ "N job đang dừng ở GATE chờ bạn";
 *   - chip lọc đội (lọc phía client theo `doi`) + nút chính "Giao việc cho đội" mở form gọn;
 *   - mỗi job đang mở một thẻ: badge đội, tên, thời gian, nhãn trạng thái, hàng bước;
 *   - job có `gate_cho` mở sẵn khung "Bạn sắp cho phép" + ghi chú + 3 nút (POST /kanban/job/gate);
 *   - job xong / đã dừng gom vào một dòng "Xong hôm nay" + "Xem lịch sử".
 *   - GATE của Đội Ads có `gate_cho.ads` (26.10.248): thẻ "Camp sẽ bật" (tài khoản, tên camp,
 *     ngân sách/ngày) để chủ thấy đúng thứ mình cho phép tiêu tiền;
 *   - ô gập "Giới hạn Đội Ads" (GET/POST /meta-ads/luat): tài khoản được ghi + trần/camp/ngày.
 *
 * Luật của khu:
 *   - Khối tự chứa: người khác chèn nó vào đầu renderKanban, nên không vẽ tiêu đề trang lớn.
 *   - Tự làm mới mỗi 5 giây khi el còn trong DOM. KHÔNG vẽ lại khi người dùng đang gõ trong
 *     ô nhập của khu (giữ chữ và tiêu điểm) - lỗi cũ của Bảng việc, đừng lặp lại. Thêm một lớp
 *     an toàn: chữ đang gõ (ghi chú, form giao việc) được giữ trong state và điền lại mỗi lần vẽ.
 *   - Mọi chuỗi từ máy chủ đi qua esc(). Mọi chữ hiển thị đi qua t("doiai.*").
 *
 * Phần dựng HTML là hàm THUẦN (_html(data, st)) để test node chạy không cần DOM.
 * Không dùng ký tự em dash. */
(function () {
  "use strict";
  function t(k, b) { return window.t ? window.t(k, b) : k; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  async function api(url, opt) {
    var r = await fetch(url, Object.assign({ credentials: "same-origin" }, opt || {}));
    var d = {};
    try { d = await r.json(); } catch (e) {}
    if (!r.ok || d.ok === false) throw new Error(d.loi || d.error || d.detail || ("HTTP " + r.status));
    return d;
  }
  function brainHienTai() {
    try { return (window.currentBrainPath && window.currentBrainPath()) || "brain"; }
    catch (e) { return "brain"; }
  }

  var CHU_KY_MS = 5000;
  var CAT_XEM_TRUOC = 420;          // số ký tự xem trước hiện sẵn, phần sau nằm sau "xem thêm"
  var MAU_TU_KE = "tu-ke-buoc";

  // ================================================================ THỜI GIAN
  function hai(n) { return (n < 10 ? "0" : "") + n; }
  function docLuc(luc) {
    if (luc == null || luc === "") return null;
    var d = typeof luc === "number" ? new Date(luc < 1e12 ? luc * 1000 : luc) : new Date(luc);
    return isNaN(d.getTime()) ? null : d;
  }
  function cungNgay(a, b) {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  }
  // "08:12" nếu hôm nay, "08:12 25/10" nếu ngày khác.
  function gioNgan(d, now) {
    var g = hai(d.getHours()) + ":" + hai(d.getMinutes());
    return cungNgay(d, now) ? g : g + " " + hai(d.getDate()) + "/" + hai(d.getMonth() + 1);
  }

  // ================================================================ DỮ LIỆU
  function dsJob(d) {
    var j = d && Array.isArray(d.jobs) ? d.jobs : [];
    return j.filter(function (x) { return x && typeof x === "object"; });
  }
  function doiCua(job) { return job.doi === "ads" || job.doi === "social" ? job.doi : "khac"; }
  function laDong(job) { return job.status === "xong" || job.status === "dung"; }
  // Khoá viết tường minh (không ghép chuỗi) để test i18n quét được từng khoá.
  function nhanTtJob(tt) {
    return { cho_duyet: t("doiai.tt_cho_duyet"), dang_chay: t("doiai.tt_dang_chay"), ket: t("doiai.tt_ket"),
      xong: t("doiai.tt_xong"), dung: t("doiai.tt_dung") }[tt] || "";
  }
  function nhanTtBuoc(tt) {
    return { xong: t("doiai.b_xong"), chay: t("doiai.b_chay"), gate: t("doiai.b_gate"), loi: t("doiai.b_loi"),
      huy: t("doiai.b_huy"), chua: t("doiai.b_chua") }[tt] || "";
  }
  function nhanDoi(doi) {
    return doi === "ads" ? t("doiai.doi_ads") : doi === "social" ? t("doiai.doi_social") : t("doiai.doi_khac");
  }
  // Trạng thái hiển thị của một bước, gom từ trạng thái task Kanban.
  function ttBuoc(b, job) {
    var s = String((b && b.status) || "");
    var gate = b && b.loai === "gate";
    if (s === "done" || s === "archived") return "xong";
    if (s === "cancelled") return "huy";
    if (s === "running") return "chay";
    if (gate && s === "blocked") return "gate";
    if (s === "blocked" || s === "failed") return "loi";
    return "chua";
  }
  function buocKet(job) {
    var bs = Array.isArray(job.buoc) ? job.buoc : [];
    for (var i = 0; i < bs.length; i++) {
      if (bs[i] && bs[i].loai !== "gate" && (bs[i].status === "blocked" || bs[i].status === "failed" || bs[i].status === "cancelled")) {
        return { so: i + 1, b: bs[i] };
      }
    }
    for (var k = 0; k < bs.length; k++) if (bs[k] && bs[k].block_reason) return { so: k + 1, b: bs[k] };
    return null;
  }
  // Bước GATE mở khoá thao tác thật? Hợp đồng: bước ngay sau GATE luôn là external-write, nên
  // có `mo_khoa` là đủ. Nếu máy chủ gửi kèm capability cho bước thì đọc thẳng.
  function moKhoaThat(job) {
    var g = job.gate_cho || {};
    var mk = Array.isArray(g.mo_khoa) ? g.mo_khoa : [];
    if (!mk.length) return false;
    var bs = Array.isArray(job.buoc) ? job.buoc : [];
    var coCap = false, coGhi = false;
    bs.forEach(function (b) {
      if (b && mk.indexOf(b.task_id) >= 0 && b.capability) {
        coCap = true;
        if (b.capability === "external-write") coGhi = true;
      }
    });
    return coCap ? coGhi : true;
  }
  function dsMau(d) {
    var raw = Array.isArray(d) ? d : (d && (d.mau || d.templates || d.items)) || [];
    var out = raw.filter(function (m) { return m && m.id; }).map(function (m) {
      return { id: String(m.id), ten: m.ten || m.title || m.name || m.id, doi: m.doi || "", mo_ta: m.mo_ta || m.description || "" };
    });
    if (!out.some(function (m) { return m.id === MAU_TU_KE; })) out.push({ id: MAU_TU_KE, ten: t("doiai.mau_tu_ke"), doi: "khac", mo_ta: "" });
    return out;
  }
  // "Các bước" gõ tay -> mảng bước theo hợp đồng create_job. Trả {buoc} hoặc {loi: khoá i18n}.
  function tachBuoc(chu) {
    var dong = String(chu || "").split(/\r?\n/).map(function (s) { return s.trim(); }).filter(Boolean);
    var buoc = dong.map(function (s) {
      var m = /^gate\s*:\s*(.*)$/i.exec(s);
      if (m) {
        var mt = m[1].trim();
        return { title: mt || "GATE", intent: mt, gate: true, gate_mo_ta: mt };
      }
      return { title: s, intent: s, gate: false };
    });
    if (!buoc.some(function (b) { return !b.gate; })) return { loi: t("doiai.loi_buoc_trong") };
    if (buoc[buoc.length - 1].gate) return { loi: t("doiai.loi_gate_cuoi") };
    return { buoc: buoc };
  }

  // ================================================================ STATE
  function stateMoi() {
    return {
      loc: "tat_ca", moForm: false, moLichSu: false,
      form: { mau: "", muc_tieu: "", buoc: "", loi: "", dangGui: false },
      mau: null, mauLoi: "",
      ghiChu: {}, loiGate: {}, guiGate: {}, moRong: {},
      moGioiHan: false,
      gioiHan: { tai: false, loi: "", dangLuu: false, daLuu: false, tai_khoan: "", tran: "" },
    };
  }

  // ================================================================ MẢNH HTML
  var ICON_KHOA = '<svg class="da-khoa" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' +
    '<rect x="4" y="10" width="16" height="10" rx="2"></rect><path d="M8 10V7a4 4 0 0 1 8 0v3"></path></svg>';

  function phanDau(jobs, st) {
    var soCho = jobs.filter(function (j) { return j.status === "cho_duyet"; }).length;
    var chips = [["tat_ca", t("doiai.loc_tat_ca")], ["ads", t("doiai.doi_ads")], ["social", t("doiai.doi_social")]]
      .map(function (c) {
        var on = st.loc === c[0];
        return '<button type="button" class="da-chip' + (on ? " on" : "") + '" data-da="loc" data-loc="' + c[0] +
          '" aria-pressed="' + (on ? "true" : "false") + '">' + esc(c[1]) + '</button>';
      }).join("");
    return '<header class="da-dau"><div class="da-dau-chu">' +
      '<h2 class="da-h2">' + esc(t("doiai.tieu_de")) + '</h2>' +
      '<span class="da-phu">' + esc(soCho > 0 ? t("doiai.dang_cho", { n: soCho }) : t("doiai.dang_cho_0")) + '</span></div>' +
      '<div class="da-dau-nut"><div class="da-loc" role="group" aria-label="' + esc(t("doiai.loc_aria")) + '">' + chips + '</div>' +
      '<button type="button" class="da-nut-chinh" data-da="mo_form" aria-expanded="' + (st.moForm ? "true" : "false") + '">' +
        esc(t("doiai.giao_viec")) + '</button></div></header>';
  }

  function formGiao(st) {
    if (!st.moForm) return "";
    var f = st.form;
    var than;
    if (st.mau == null && !st.mauLoi) than = '<div class="da-phu">' + esc(t("doiai.dang_tai_mau")) + '</div>';
    else {
      var mau = st.mau || dsMau([]);
      var chon = f.mau && mau.some(function (m) { return m.id === f.mau; }) ? f.mau : (mau[0] && mau[0].id) || MAU_TU_KE;
      var mauChon = mau.filter(function (m) { return m.id === chon; })[0];
      var tuKe = chon === MAU_TU_KE;
      than = (st.mauLoi ? '<div class="da-loi" role="alert">' + esc(t("doiai.loi_mau", { loi: st.mauLoi })) + '</div>' : "") +
        '<label class="da-nhan" for="da-mau">' + esc(t("doiai.chon_mau")) + '</label>' +
        '<select id="da-mau" class="da-o" data-da-o="mau">' + mau.map(function (m) {
          return '<option value="' + esc(m.id) + '"' + (m.id === chon ? " selected" : "") + '>' + esc(m.ten) + '</option>';
        }).join("") + '</select>' +
        (mauChon && mauChon.mo_ta ? '<span class="da-phu">' + esc(mauChon.mo_ta) + '</span>' : "") +
        '<label class="da-nhan" for="da-muc-tieu">' + esc(t("doiai.muc_tieu")) + '</label>' +
        '<textarea id="da-muc-tieu" class="da-o" rows="2" data-da-o="muc_tieu" placeholder="' + esc(t("doiai.muc_tieu_ph")) + '">' +
          esc(f.muc_tieu) + '</textarea>' +
        (tuKe ? '<label class="da-nhan" for="da-buoc">' + esc(t("doiai.cac_buoc")) + '</label>' +
          '<textarea id="da-buoc" class="da-o da-o-buoc" rows="5" data-da-o="buoc" aria-describedby="da-buoc-gy">' + esc(f.buoc) + '</textarea>' +
          '<span id="da-buoc-gy" class="da-phu">' + esc(t("doiai.cac_buoc_goi_y")) + '</span>' : "") +
        '<div class="da-form-nut">' +
          '<button type="button" class="da-nut-chinh" data-da="giao"' + (f.dangGui ? " disabled" : "") + '>' +
            esc(f.dangGui ? t("doiai.dang_gui") : t("doiai.giao")) + '</button>' +
          '<button type="button" class="da-nut-phu" data-da="dong_form">' + esc(t("doiai.dong")) + '</button>' +
        '</div>' +
        '<div class="da-loi" role="alert">' + esc(f.loi) + '</div>';
    }
    return '<section class="da-form" aria-label="' + esc(t("doiai.form_aria")) + '">' + than + '</section>';
  }

  function hangBuoc(job) {
    var bs = Array.isArray(job.buoc) ? job.buoc : [];
    if (!bs.length) return "";
    var o = bs.map(function (b, i) {
      b = b || {};
      var tt = ttBuoc(b, job);
      var ten = b.title || "";
      var nhanTt = nhanTtBuoc(tt);
      if (b.loai === "gate") {
        var lopG = tt === "gate" ? "da-buoc da-buoc-gate cho" : tt === "xong" ? "da-buoc da-buoc-gate xong" : "da-buoc da-buoc-gate " + tt;
        return '<li class="' + lopG + '" title="' + esc(nhanTt) + '">' + ICON_KHOA +
          '<span class="da-buoc-ten">' + esc(t("doiai.gate_nhan", { ten: ten })) + '</span>' +
          '<span class="da-an">' + esc(nhanTt) + '</span></li>';
      }
      return '<li class="da-buoc ' + tt + '" title="' + esc(nhanTt) + '">' +
        '<span class="da-vong" aria-hidden="true">' + (i + 1) + '</span>' +
        '<span class="da-buoc-ten">' + esc(ten) + '</span>' +
        '<span class="da-an">' + esc(nhanTt) + '</span></li>';
    });
    return '<ol class="da-hang-buoc" aria-label="' + esc(t("doiai.buoc_aria")) + '">' +
      o.join('<li class="da-noi" aria-hidden="true"></li>') + '</ol>';
  }

  function dongTien(n) {
    var v = Math.round(Number(n) || 0);
    return String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ".") + "đ";
  }

  // Thẻ "Camp sẽ bật": trị số thật bước dựng camp đã lưu vào job, không phải chữ model tự kể.
  function theCamp(ads) {
    if (!ads || typeof ads !== "object" || !ads.campaign_id) return "";
    var nhom = Array.isArray(ads.adset_ids) ? ads.adset_ids.length : 0;
    var qc = Array.isArray(ads.ad_ids) ? ads.ad_ids.length : 0;
    var tt = ads.trang_thai === "NHAP" ? t("doiai.camp_nhap") : t("doiai.camp_tat");
    function dong(nhan, gt, dam) {
      return '<div class="da-camp-dong"><span class="da-nhan">' + esc(nhan) + '</span>' +
        (dam ? '<b>' + esc(gt) + '</b>' : '<span>' + esc(gt) + '</span>') + '</div>';
    }
    return '<div class="da-camp" role="group" aria-label="' + esc(t("doiai.camp_tieu_de")) + '">' +
      '<b class="da-h4">' + esc(t("doiai.camp_tieu_de")) + '</b>' +
      dong(t("doiai.camp_ten"), ads.ten || "") +
      dong(t("doiai.camp_tai_khoan"), "act_" + String(ads.tai_khoan || "")) +
      dong(t("doiai.camp_ngan_sach"), t("doiai.camp_ngan_sach_gt", { tien: dongTien(ads.ngan_sach_ngay_vnd) }), true) +
      dong(t("doiai.camp_cau_truc"), t("doiai.camp_cau_truc_gt", { nhom: nhom, qc: qc })) +
      dong(t("doiai.camp_trang_thai"), tt) +
      '<span class="da-phu">' + esc(t("doiai.camp_ma", { ma: String(ads.campaign_id) })) + '</span>' +
    '</div>';
  }

  function khungChoPhep(job, st) {
    var g = job.gate_cho;
    if (!g || typeof g !== "object") return "";
    var id = String(job.id || "");
    var xt = String(g.xem_truoc || "");
    var moRong = !!st.moRong[id];
    var dai = xt.length > CAT_XEM_TRUOC;
    var hien = dai && !moRong ? xt.slice(0, CAT_XEM_TRUOC).replace(/\s+\S*$/, "") + "..." : xt;
    var dangGui = !!st.guiGate[id];
    var dis = dangGui ? " disabled" : "";
    var idGhi = "da-ghi-" + id.replace(/[^A-Za-z0-9_-]/g, "_");
    var nutDuyet = moKhoaThat(job) ? t("doiai.duyet_that") : t("doiai.duyet");
    return '<div class="da-cho-phep">' +
      '<div class="da-cho-phep-chu">' +
        '<b class="da-h4">' + esc(t("doiai.cho_phep")) + '</b>' +
        (g.mo_ta ? '<p class="da-gate-mo-ta">' + esc(g.mo_ta) + '</p>' : "") +
        theCamp(g.ads) +
        '<span class="da-nhan">' + esc(t("doiai.xem_truoc")) + '</span>' +
        (xt ? '<div class="da-xem-truoc">' + esc(hien) + '</div>' +
          (dai ? '<button type="button" class="da-link" data-da="xem_them" data-job="' + esc(id) + '" aria-expanded="' + (moRong ? "true" : "false") + '">' +
            esc(moRong ? t("doiai.thu_gon") : t("doiai.xem_them")) + '</button>' : "")
          : '<div class="da-phu">' + esc(t("doiai.xem_truoc_trong")) + '</div>') +
        '<label class="da-nhan" for="' + esc(idGhi) + '">' + esc(t("doiai.ghi_chu")) + '</label>' +
        '<textarea id="' + esc(idGhi) + '" class="da-o" rows="2" data-da-ghi="' + esc(id) + '" placeholder="' + esc(t("doiai.ghi_chu_ph")) + '">' +
          esc(st.ghiChu[id] || "") + '</textarea>' +
      '</div>' +
      '<div class="da-cho-phep-nut">' +
        '<button type="button" class="da-nut-chinh" data-da="gate" data-action="duyet" data-job="' + esc(id) + '"' + dis + '>' +
          esc(dangGui === "duyet" ? t("doiai.dang_gui") : nutDuyet) + '</button>' +
        '<button type="button" class="da-nut-phu" data-da="gate" data-action="sua" data-job="' + esc(id) + '"' + dis + '>' +
          esc(dangGui === "sua" ? t("doiai.dang_gui") : t("doiai.sua")) + '</button>' +
        '<button type="button" class="da-nut-bo" data-da="gate" data-action="tu_choi" data-job="' + esc(id) + '"' + dis + '>' +
          esc(dangGui === "tu_choi" ? t("doiai.dang_gui") : t("doiai.tu_choi")) + '</button>' +
        '<div class="da-loi" role="alert">' + esc(st.loiGate[id] || "") + '</div>' +
      '</div></div>';
  }

  function theJob(job, st, now) {
    var doi = doiCua(job);
    var tt = ["cho_duyet", "dang_chay", "ket", "xong", "dung"].indexOf(job.status) >= 0 ? job.status : "dang_chay";
    var luc = docLuc(job.created_at);
    var ket = "";
    if (tt === "ket") {
      var bk = buocKet(job);
      ket = '<div class="da-ket" role="status">' + esc(bk && bk.b.block_reason
        ? t("doiai.ket_ly_do", { buoc: bk.b.title || bk.so, ly_do: bk.b.block_reason })
        : t("doiai.ket_khong_ro")) + '</div>';
    }
    return '<article class="da-the" data-job="' + esc(job.id || "") + '" data-doi="' + doi + '">' +
      '<div class="da-the-dau"><div class="da-the-ten">' +
        '<span class="da-doi ' + doi + '">' + esc(nhanDoi(doi)) + '</span>' +
        '<b class="da-ten">' + esc(job.title || "") + '</b>' +
        (luc ? '<span class="da-phu">' + esc(t("doiai.giao_luc", { gio: gioNgan(luc, now) })) + '</span>' : "") +
      '</div><span class="da-tt ' + tt + '">' + esc(nhanTtJob(tt)) + '</span></div>' +
      ket + hangBuoc(job) + khungChoPhep(job, st) + '</article>';
  }

  function dongXong(jobs, st, now) {
    var dong = jobs.filter(laDong);
    var homNay = dong.filter(function (j) {
      var d = docLuc(j.updated_at || j.created_at);
      return j.status === "xong" && d && cungNgay(d, now);
    });
    var tom = homNay.length
      ? '<span class="da-xong-chu"><b>' + esc(t("doiai.xong_hom_nay")) + '</b> ' + homNay.map(function (j) {
          return esc(j.title || "") + ' <span class="da-mo">(' + esc(nhanDoi(doiCua(j))) + ')</span>';
        }).join(' · ') + '</span>'
      : '<span class="da-xong-chu da-mo">' + esc(t("doiai.xong_hom_nay_0")) + '</span>';
    var lichSu = "";
    if (st.moLichSu) {
      lichSu = dong.length ? '<ul class="da-lich-su">' + dong.map(function (j) {
        var d = docLuc(j.updated_at || j.created_at);
        return '<li><span class="da-doi ' + doiCua(j) + '">' + esc(nhanDoi(doiCua(j))) + '</span>' +
          '<span class="da-lich-su-ten">' + esc(j.title || "") + '</span>' +
          (d ? '<span class="da-phu">' + esc(gioNgan(d, now)) + '</span>' : "") +
          '<span class="da-tt ' + (j.status === "xong" ? "xong" : "dung") + '">' + esc(nhanTtJob(j.status === "xong" ? "xong" : "dung")) + '</span></li>';
      }).join("") + '</ul>' : '<div class="da-phu">' + esc(t("doiai.lich_su_trong")) + '</div>';
    }
    return '<section class="da-xong"><div class="da-xong-hang">' + tom +
      '<button type="button" class="da-link" data-da="lich_su" aria-expanded="' + (st.moLichSu ? "true" : "false") + '">' +
        esc(st.moLichSu ? t("doiai.an_lich_su") : t("doiai.xem_lich_su")) + '</button></div>' + lichSu + '</section>';
  }

  function gioiHan(st) {
    var g = st.gioiHan || {};
    var nut = '<button type="button" class="da-link" data-da="gioi_han" aria-expanded="' + (st.moGioiHan ? "true" : "false") +
      '" aria-controls="da-gioi-han">' + esc(t("doiai.gh_tieu_de")) + '</button>';
    if (!st.moGioiHan) return '<section class="da-gh">' + nut + '</section>';
    var than;
    if (!g.tai && !g.loi) than = '<div class="da-phu">' + esc(t("doiai.dang_tai")) + '</div>';
    else than =
      '<p class="da-phu">' + esc(t("doiai.gh_giai_thich")) + '</p>' +
      '<label class="da-nhan" for="da-gh-tk">' + esc(t("doiai.gh_tai_khoan")) + '</label>' +
      '<textarea id="da-gh-tk" class="da-o" rows="2" data-da-gh="tai_khoan" aria-describedby="da-gh-tk-gy" placeholder="' + esc(t("doiai.gh_tai_khoan_ph")) + '">' +
        esc(g.tai_khoan || "") + '</textarea>' +
      '<span id="da-gh-tk-gy" class="da-phu">' + esc(t("doiai.gh_tai_khoan_gy")) + '</span>' +
      '<label class="da-nhan" for="da-gh-tran">' + esc(t("doiai.gh_tran")) + '</label>' +
      '<input id="da-gh-tran" class="da-o" inputmode="numeric" data-da-gh="tran" value="' + esc(g.tran || "") + '">' +
      '<div class="da-form-nut"><button type="button" class="da-nut-chinh" data-da="luu_gioi_han"' + (g.dangLuu ? " disabled" : "") + '>' +
        esc(g.dangLuu ? t("doiai.dang_gui") : t("doiai.gh_luu")) + '</button>' +
        (g.daLuu ? '<span class="da-phu" role="status">' + esc(t("doiai.gh_da_luu")) + '</span>' : "") + '</div>' +
      '<div class="da-loi" role="alert">' + esc(g.loi || "") + '</div>';
    return '<section class="da-gh">' + nut + '<div id="da-gioi-han" class="da-gh-than">' + than + '</div></section>';
  }

  // Hàm THUẦN: dữ liệu jobs_view + state giao diện -> chuỗi HTML của cả khu.
  // st.now (Date) cho test cố định "hôm nay"; bỏ trống thì lấy giờ máy.
  function html(d, st) {
    st = Object.assign(stateMoi(), st || {});
    var now = st.now instanceof Date ? st.now : new Date();
    var jobs = dsJob(d);
    var loc = jobs.filter(function (j) { return st.loc === "tat_ca" || doiCua(j) === st.loc; });
    var mo = loc.filter(function (j) { return !laDong(j); });
    // Job chờ bạn lên đầu, rồi kẹt, rồi đang chạy; trong nhóm giữ thứ tự máy chủ gửi.
    var hang = { cho_duyet: 0, ket: 1, dang_chay: 2 };
    mo = mo.map(function (j, i) { return [j, i]; }).sort(function (a, b) {
      var ha = hang[a[0].status] != null ? hang[a[0].status] : 2, hb = hang[b[0].status] != null ? hang[b[0].status] : 2;
      return ha - hb || a[1] - b[1];
    }).map(function (x) { return x[0]; });
    var than;
    if (!jobs.length) {
      than = '<div class="da-rong"><span>' + esc(t("doiai.rong")) + '</span>' +
        '<button type="button" class="da-nut-phu" data-da="mo_form">' + esc(t("doiai.giao_viec")) + '</button></div>';
    } else {
      than = (mo.length ? mo.map(function (j) { return theJob(j, st, now); }).join("")
        : '<div class="da-rong"><span>' + esc(t("doiai.rong_loc")) + '</span></div>') + dongXong(loc, st, now);
    }
    return '<div class="da">' + phanDau(jobs, st) + formGiao(st) + than + gioiHan(st) + '</div>';
  }

  // Đang gõ trong khu? (tiêu điểm nằm trong ô nhập/vùng chữ/hộp chọn của el). Khi đúng thì
  // vòng tự làm mới BỎ QUA lượt vẽ để không cướp chữ và tiêu điểm của người dùng.
  function dangGo(el, act) {
    if (!el || !act || act === el || !el.contains || !el.contains(act)) return false;
    var tag = String(act.tagName || "").toUpperCase();
    return tag === "TEXTAREA" || tag === "INPUT" || tag === "SELECT" || !!act.isContentEditable;
  }

  // ================================================================ HÀNH ĐỘNG
  function ve(el) {
    var st = el._daState;
    el.innerHTML = html(st.data, st);
  }

  async function taiVaVe(el, epVe) {
    var st = el._daState;
    if (st.dangTai) return;
    st.dangTai = true;
    try {
      var d = await api("/kanban/jobs?brain=" + encodeURIComponent(brainHienTai()));
      if (!el.isConnected) return;
      var moi = JSON.stringify(d);
      // Không đổi gì thì không đụng DOM (khỏi giật, khỏi mất tiêu điểm nút).
      if (!epVe && moi === st.dataJson && !st.loiTai) return;
      // Vẽ lại chỉ khi người dùng KHÔNG đang gõ; dữ liệu mới sẽ lên ở lượt sau.
      if (!epVe && dangGo(el, document.activeElement)) return;
      st.data = d; st.dataJson = moi; st.loiTai = "";
      ve(el);
    } catch (e) {
      if (!el.isConnected) return;
      st.loiTai = e.message || "";
      if (st.data == null) {
        el.innerHTML = '<div class="da"><div class="da-rong da-loi-tai"><span>' +
          esc(t("doiai.loi_tai", { loi: st.loiTai })) + '</span>' +
          '<button type="button" class="da-nut-phu" data-da="thu_lai">' + esc(t("doiai.thu_lai")) + '</button></div></div>';
      }
    } finally {
      st.dangTai = false;
    }
  }

  function nhanLuat(st, d) {
    var g = st.gioiHan;
    g.tai = true; g.loi = "";
    g.tai_khoan = (Array.isArray(d.tai_khoan) ? d.tai_khoan : []).map(function (x) { return "act_" + x; }).join("\n");
    g.tran = String(d.tran_ngay_vnd || "");
  }

  async function moGioiHan(el) {
    var st = el._daState;
    st.moGioiHan = !st.moGioiHan;
    st.gioiHan.daLuu = false;
    ve(el);
    if (!st.moGioiHan || st.gioiHan.tai) return;
    try {
      nhanLuat(st, await api("/meta-ads/luat"));
    } catch (e) {
      st.gioiHan.loi = t("doiai.gh_loi_tai", { loi: e.message || "" });
    }
    if (el.isConnected) ve(el);
  }

  async function luuGioiHan(el) {
    var st = el._daState, g = st.gioiHan;
    if (g.dangLuu) return;
    g.dangLuu = true; g.loi = ""; g.daLuu = false; ve(el);
    try {
      var d = await api("/meta-ads/luat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tai_khoan: String(g.tai_khoan || ""), tran_ngay_vnd: String(g.tran || "") }),
      });
      nhanLuat(st, d);
      g.daLuu = true;
    } catch (e) {
      g.loi = t("doiai.gh_loi_luu", { loi: e.message || "" });
    }
    g.dangLuu = false;
    if (el.isConnected) ve(el);
  }

  async function moForm(el) {
    var st = el._daState;
    st.moForm = true;
    ve(el);
    if (st.mau != null) return;
    try {
      var d = await api("/kanban/job-templates");
      st.mau = dsMau(d); st.mauLoi = "";
    } catch (e) {
      st.mau = dsMau([]); st.mauLoi = e.message || "";
    }
    if (!el.isConnected) return;
    ve(el);
    var o = el.querySelector("#da-muc-tieu");
    if (o) o.focus();
  }

  async function giao(el) {
    var st = el._daState, f = st.form;
    var mau = st.mau || dsMau([]);
    var chon = f.mau && mau.some(function (m) { return m.id === f.mau; }) ? f.mau : (mau[0] && mau[0].id) || MAU_TU_KE;
    var mt = String(f.muc_tieu || "").trim();
    var fd = new FormData();
    fd.append("brain", brainHienTai());
    if (chon === MAU_TU_KE) {
      var kq = tachBuoc(f.buoc);
      if (!mt) { f.loi = t("doiai.loi_muc_tieu_trong"); ve(el); return; }
      if (kq.loi) { f.loi = kq.loi; ve(el); return; }
      fd.append("title", mt.split(/\r?\n/)[0].slice(0, 160));
      fd.append("doi", "khac");
      fd.append("steps", JSON.stringify(kq.buoc));
      fd.append("muc_tieu", mt);
    } else {
      if (!mt) { f.loi = t("doiai.loi_muc_tieu_trong"); ve(el); return; }
      fd.append("mau", chon);
      fd.append("muc_tieu", mt);
    }
    f.loi = ""; f.dangGui = true; ve(el);
    try {
      await api("/kanban/job", { method: "POST", body: fd });
      if (!el.isConnected) return;
      st.form = { mau: chon, muc_tieu: "", buoc: "", loi: "", dangGui: false };
      st.moForm = false;
      await taiVaVe(el, true);
    } catch (e) {
      if (!el.isConnected) return;
      f.dangGui = false;
      f.loi = t("doiai.loi_giao", { loi: e.message || "" });
      ve(el);
    }
  }

  async function guiGate(el, jobId, action) {
    var st = el._daState;
    if (st.guiGate[jobId]) return;
    var note = String(st.ghiChu[jobId] || "").trim();
    st.loiGate[jobId] = "";
    if (action === "sua" && !note) {
      st.loiGate[jobId] = t("doiai.loi_ghi_chu");
      ve(el);
      var o = el.querySelector('[data-da-ghi="' + (window.CSS && CSS.escape ? CSS.escape(jobId) : jobId) + '"]');
      if (o) o.focus();
      return;
    }
    if (action === "tu_choi") {
      var job = dsJob(st.data).filter(function (j) { return String(j.id) === jobId; })[0];
      if (!window.confirm(t("doiai.tu_choi_hoi", { ten: (job && job.title) || jobId }))) return;
    }
    st.guiGate[jobId] = action;
    ve(el);
    try {
      var fd = new FormData();
      fd.append("brain", brainHienTai());
      fd.append("job_id", jobId);
      fd.append("action", action);
      fd.append("note", note);
      await api("/kanban/job/gate", { method: "POST", body: fd });
      if (!el.isConnected) return;
      delete st.guiGate[jobId];
      delete st.ghiChu[jobId];
      await taiVaVe(el, true);
    } catch (e) {
      if (!el.isConnected) return;
      delete st.guiGate[jobId];
      st.loiGate[jobId] = t("doiai.loi_gui", { loi: e.message || "" });
      ve(el);
    }
  }

  function noiSuKien(el) {
    // Gán bằng thuộc tính (không addEventListener) để render(el) gọi lại nhiều lần không chồng
    // trình nghe.
    el.oninput = function (ev) {
      var o = ev.target, st = el._daState;
      if (!o || !o.dataset) return;
      if (o.dataset.daGhi != null) { st.ghiChu[o.dataset.daGhi] = o.value; return; }
      if (o.dataset.daGh) { st.gioiHan[o.dataset.daGh] = o.value; st.gioiHan.daLuu = false; return; }
      if (o.dataset.daO) st.form[o.dataset.daO] = o.value;
    };
    el.onchange = function (ev) {
      var o = ev.target, st = el._daState;
      if (o && o.dataset && o.dataset.daO === "mau") { st.form.mau = o.value; st.form.loi = ""; ve(el); }
    };
    el.onclick = function (ev) {
      var nut = ev.target && ev.target.closest ? ev.target.closest("[data-da]") : null;
      if (!nut || !el.contains(nut) || nut.disabled) return;
      var st = el._daState, loai = nut.dataset.da;
      if (loai === "loc") { st.loc = nut.dataset.loc || "tat_ca"; ve(el); }
      else if (loai === "mo_form") { if (st.moForm) { st.moForm = false; ve(el); } else moForm(el); }
      else if (loai === "dong_form") { st.moForm = false; st.form.loi = ""; ve(el); }
      else if (loai === "giao") giao(el);
      else if (loai === "gate") guiGate(el, nut.dataset.job || "", nut.dataset.action || "");
      else if (loai === "xem_them") { var j = nut.dataset.job || ""; st.moRong[j] = !st.moRong[j]; ve(el); }
      else if (loai === "lich_su") { st.moLichSu = !st.moLichSu; ve(el); }
      else if (loai === "thu_lai") taiVaVe(el, true);
      else if (loai === "gioi_han") moGioiHan(el);
      else if (loai === "luu_gioi_han") luuGioiHan(el);
    };
  }

  async function render(el) {
    if (!el) return;
    if (!el._daState) el._daState = stateMoi();
    var st = el._daState;
    if (st.data == null) el.innerHTML = '<div class="da"><div class="da-phu">' + esc(t("doiai.dang_tai")) + '</div></div>';
    noiSuKien(el);
    if (el._daTimer) clearInterval(el._daTimer);
    el._daTimer = setInterval(function () {
      if (!el.isConnected) { clearInterval(el._daTimer); el._daTimer = null; return; }
      if (document.hidden) return;
      if (dangGo(el, document.activeElement)) return;
      var s = el._daState;
      if (s.form.dangGui || s.gioiHan.dangLuu || Object.keys(s.guiGate).length) return;
      taiVaVe(el, false);
    }, CHU_KY_MS);
    await taiVaVe(el, true);
  }

  window.MinMinDoiAi = {
    render: render,
    // Cho test node: dựng HTML không cần DOM, và các hàm thuần.
    _html: html,
    _dangGo: dangGo,
    _tachBuoc: tachBuoc,
    _dsMau: dsMau,
    _theCamp: theCamp,
    _dongTien: dongTien,
  };
})();
