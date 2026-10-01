"use strict";
/* Hoá đơn (MinMin OS 26.10.6): giao diện web cho Tải Hoá Đơn TCT và Quét hoá đơn Gmail.
 * Nói chuyện với /apps/tai-hoa-don/api/*. Việc dài (tra cứu, tải, quét) chạy nền phía máy chủ,
 * trang này hỏi tiến độ mỗi giây. Không dùng ký tự em dash. */
(function () {
  var API = "api/";
  var $ = function (s) { return document.querySelector(s); };
  var tt = { tai: false, gmail: false };
  var dn = null;            // MST đang chọn
  var loai = "purchase";
  var dsHd = [];
  var chon = new Set();

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function ngayVN(s) { var m = String(s || "").match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? m[3] + "/" + m[2] + "/" + m[1] : (s || ""); }
  function tien(n) { return Math.round(Number(n) || 0).toLocaleString("vi-VN"); }
  function bao(s) {
    var b = $("#bao"); b.textContent = s; b.classList.add("hien");
    clearTimeout(bao._h); bao._h = setTimeout(function () { b.classList.remove("hien"); }, 3500);
  }
  async function goi(duong, tuy) {
    tuy = tuy || {};
    if (tuy.json !== undefined) {
      tuy.method = tuy.method || "POST";
      tuy.headers = { "content-type": "application/json" };
      tuy.body = JSON.stringify(tuy.json);
    }
    var r = await fetch(API + duong, { method: tuy.method || "GET", headers: tuy.headers, body: tuy.body, credentials: "same-origin" });
    if (r.status === 401) { location.href = "/"; throw new Error("Cần đăng nhập MinMin"); }
    var d = null;
    try { d = await r.json(); } catch (e) {}
    if (!r.ok || !d || d.ok === false) throw new Error((d && (d.error || d.detail)) || ("HTTP " + r.status));
    return d;
  }
  async function taiFile(duong, json) {
    var r = await fetch(API + duong, { method: "POST", credentials: "same-origin",
      headers: { "content-type": "application/json" }, body: JSON.stringify(json || {}) });
    if (!r.ok) {
      var d = null; try { d = await r.json(); } catch (e) {}
      throw new Error((d && d.error) || ("HTTP " + r.status));
    }
    var ten = "tep";
    var cd = r.headers.get("content-disposition") || "";
    var m = cd.match(/filename\*=UTF-8''([^;]+)/);
    if (m) ten = decodeURIComponent(m[1]);
    var blob = await r.blob();
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = ten;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }
  function ngayISO(d) { return d.toISOString().slice(0, 10); }
  function datNgayMacDinh(tu, den) {
    var h = new Date(), dau = new Date(h.getFullYear(), h.getMonth() - 1, 1);
    tu.value = ngayISO(new Date(dau.getTime() - dau.getTimezoneOffset() * 60000));
    den.value = ngayISO(new Date(h.getTime() - h.getTimezoneOffset() * 60000));
  }

  // ---------------- việc nền
  function theoDoi(id, o, xong) {
    var tu = 0;
    o.hop.hidden = false; o.log.textContent = ""; o.thanh.value = 0; o.thanh.removeAttribute("value");
    o.dung.onclick = function () { goi("viec/" + id + "/dung", { method: "POST" }).catch(function () {}); };
    async function vong() {
      var v;
      try { v = await goi("viec/" + id + "?tu=" + tu); } catch (e) { o.ten.textContent = e.message; return; }
      o.ten.textContent = v.mo_ta;
      if (v.nhat_ky.length) {
        o.log.textContent += v.nhat_ky.join("\n") + "\n";
        o.log.scrollTop = o.log.scrollHeight;
      }
      tu = v.so_dong;
      if (v.n) { o.thanh.max = v.n; o.thanh.value = v.i; o.so.textContent = v.i + "/" + v.n; }
      if (v.trang_thai === "dang_chay") { setTimeout(vong, 1000); return; }
      o.dung.hidden = true;
      o.so.textContent = v.trang_thai === "xong" ? "Xong" : v.trang_thai === "huy" ? "Đã dừng" : "Lỗi";
      if (v.trang_thai === "loi") bao(v.loi);
      if (xong) xong(v);
    }
    o.dung.hidden = false;
    vong();
  }
  var viecTai = { hop: $("#hopViec"), ten: $("#viecTen"), so: $("#viecSo"), thanh: $("#viecThanh"), log: $("#viecLog"), dung: $("#nutDung") };
  var viecGmail = { hop: $("#gViec"), ten: $("#gViecTen"), so: $("#gViecSo"), thanh: $("#gThanh"), log: $("#gLog"), dung: $("#gDung") };

  // ---------------- tab
  function moTab(t) {
    if (!tt[t]) t = tt.tai ? "tai" : "gmail";
    document.querySelectorAll(".tab button").forEach(function (b) { b.classList.toggle("on", b.dataset.tab === t); });
    $("#tab-tai").hidden = t !== "tai";
    $("#tab-gmail").hidden = t !== "gmail";
    history.replaceState(null, "", t === "gmail" ? "?tab=gmail" : "./");
    if (t === "tai") taiDn(); else taiGmail();
  }

  // ================= TẢI HOÁ ĐƠN =================
  async function taiDn() {
    var d;
    try { d = await goi("doanh-nghiep"); } catch (e) { bao(e.message); return; }
    var ul = $("#dsDn");
    ul.innerHTML = d.ds.map(function (x) {
      return '<li data-mst="' + esc(x.mst) + '" class="' + (x.mst === dn ? "on" : "") + '">' +
        '<span class="mst">' + esc(x.mst) + '</span>' +
        (x.ten ? '<span>' + esc(x.ten) + '</span>' : "") +
        '<span class="phu"><span><i class="cham' + (x.dang_nhap ? " ok" : "") + '"></i>' +
        (x.dang_nhap ? "Đã đăng nhập" : "Chưa đăng nhập") + ' · ' + (x.so_hd.purchase + x.so_hd.sold) + ' HĐ</span>' +
        '<button type="button" class="xoa" data-xoa="' + esc(x.mst) + '">Xoá</button></span></li>';
    }).join("") || '<li class="nho">Chưa có doanh nghiệp nào.</li>';
    ul.querySelectorAll("li[data-mst]").forEach(function (li) {
      li.onclick = function (ev) {
        if (ev.target.dataset.xoa) return;
        chonDn(li.dataset.mst, d.ds.filter(function (x) { return x.mst === li.dataset.mst; })[0]);
      };
    });
    ul.querySelectorAll("[data-xoa]").forEach(function (b) {
      b.onclick = async function () {
        if (!confirm("Xoá doanh nghiệp " + b.dataset.xoa + " khỏi danh sách? Hoá đơn đã tải vẫn giữ.")) return;
        await goi("doanh-nghiep/" + encodeURIComponent(b.dataset.xoa), { method: "DELETE" });
        if (dn === b.dataset.xoa) { dn = null; $("#vungDn").hidden = true; $("#chuaChon").hidden = false; }
        taiDn();
      };
    });
    if (dn) {
      var hien = d.ds.filter(function (x) { return x.mst === dn; })[0];
      if (hien) veDangNhap(hien);
    }
  }

  function veDangNhap(x) {
    $("#dnTen").textContent = x.ten ? "(" + x.ten + ")" : x.mst;
    $("#hopDangNhap").hidden = !!x.dang_nhap;
    $("#oMk").hidden = !!x.co_mk;
    $("#nhoMk").parentNode.hidden = !!x.co_mk;
    $("#nutDangXuat").hidden = !x.dang_nhap;
    if (!x.dang_nhap && !$("#anhCaptcha").dataset.mst) layCaptcha();
  }

  function chonDn(mst, x) {
    dn = mst;
    chon.clear();
    $("#chuaChon").hidden = true;
    $("#vungDn").hidden = false;
    $("#hopCanhBao").hidden = true;
    $("#anhCaptcha").dataset.mst = "";
    document.querySelectorAll("#dsDn li").forEach(function (li) { li.classList.toggle("on", li.dataset.mst === mst); });
    if (x) veDangNhap(x);
    taiBang();
  }

  async function layCaptcha() {
    $("#thongDangNhap").textContent = "Đang lấy ảnh...";
    $("#thongDangNhap").className = "thong";
    try {
      var c = await goi("captcha?mst=" + encodeURIComponent(dn));
      var img = $("#anhCaptcha");
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(c.svg);
      img.dataset.key = c.key; img.dataset.mst = dn;
      $("#oCaptcha").value = ""; $("#oCaptcha").focus();
      $("#thongDangNhap").textContent = "";
    } catch (e) {
      $("#thongDangNhap").textContent = e.message; $("#thongDangNhap").className = "thong loi";
    }
  }

  async function dangNhap() {
    var nut = $("#nutDangNhap"); nut.disabled = true;
    try {
      await goi("dang-nhap", { json: { mst: dn, captcha: $("#oCaptcha").value, ckey: $("#anhCaptcha").dataset.key,
        mat_khau: $("#oMk").hidden ? "" : $("#oMk").value, nho_mk: $("#nhoMk").checked } });
      $("#oMk").value = "";
      bao("Đã đăng nhập cổng thuế.");
      $("#anhCaptcha").dataset.mst = "";
      taiDn();
    } catch (e) {
      $("#thongDangNhap").textContent = e.message; $("#thongDangNhap").className = "thong loi";
      layCaptcha();
    } finally { nut.disabled = false; }
  }

  async function taiBang() {
    if (!dn) return;
    var q = "hoa-don?mst=" + encodeURIComponent(dn) + "&loai=" + loai + "&tu=" + $("#tu").value + "&den=" + $("#den").value;
    var d;
    try { d = await goi(q); } catch (e) { bao(e.message); return; }
    dsHd = d.ds;
    var t = d.tong;
    $("#tong").innerHTML = "<span><b>" + t.so_hd + "</b> hoá đơn</span><span>Tiền hàng <b>" + tien(t.tien_hang) +
      "</b></span><span>Thuế <b>" + tien(t.thue) + "</b></span><span>Tổng <b>" + tien(t.tong) +
      "</b></span><span>Đã có XML <b>" + t.co_xml + "</b></span><span>Có bản gốc <b>" + t.co_goc + "</b></span>";
    veBang();
  }

  function veBang() {
    var f = $("#loc").value.trim().toLowerCase();
    var ds = !f ? dsHd : dsHd.filter(function (r) {
      return (String(r.doi_tac) + " " + r.mst_doi_tac + " " + r.so + " " + r.ky_hieu).toLowerCase().indexOf(f) >= 0;
    });
    var base = "/" + encodeURIComponent(dn) + "/" + loai + "/";
    $("#bangHd").innerHTML = ds.slice(0, 2000).map(function (r) {
      var k = encodeURIComponent(r.key);
      var file = (r.co_html ? '<a href="' + API + "xem" + base + k + '" target="_blank" rel="noopener">Xem</a>' : "") +
        (r.co_xml ? '<a class="nhan ok" href="' + API + "tep" + base + k + '/xml">XML</a>' : "") +
        (r.co_pdf ? '<a class="nhan ok" href="' + API + "tep" + base + k + '/pdf">Trống đồng</a>' :
          r.pdf_loi ? '<span class="nhan loi" title="' + esc(r.pdf_loi) + '">Trống đồng: lỗi</span>' : "") +
        (r.co_goc ? '<a class="nhan ok" href="' + API + "tep" + base + k + '/goc">Gốc' + (r.goc_nguon === "Gmail" ? " (Gmail)" : "") + '</a>' :
          r.goc_loi ? '<span class="nhan loi" title="' + esc(r.goc_loi) + '">Gốc: chưa tải được</span>' : "") +
        (r.co_zip ? '<a class="nhan" href="' + API + "tep" + base + k + '/zip">ZIP</a>' : "") +
        (r.goc_link ? '<a href="' + esc(r.goc_link) + '" target="_blank" rel="noopener noreferrer">Trang hãng</a>' : "");
      return '<tr><td><input type="checkbox" data-k="' + esc(r.key) + '"' + (chon.has(r.key) ? " checked" : "") + '></td>' +
        '<td class="ngay">' + esc(ngayVN(r.ngay)) + '</td><td>' + esc(r.so) + '</td><td>' + esc(r.ky_hieu) + '</td>' +
        '<td class="doi">' + esc(r.doi_tac) + (r.may_tinh_tien ? ' <span class="nhan">MTT</span>' : "") + (r.tu_gmail ? ' <span class="nhan">Từ Gmail</span>' : "") + '</td><td>' + esc(r.mst_doi_tac) + '</td>' +
        '<td class="so">' + tien(r.tien_hang) + '</td><td class="so">' + tien(r.thue) + '</td><td class="so">' + tien(r.tong) + '</td>' +
        '<td>' + esc(r.trang_thai) + '</td><td>' + file + '</td></tr>';
    }).join("") || '<tr><td colspan="11" class="nho">Chưa có hoá đơn trong khoảng ngày này. Đăng nhập rồi bấm Tra cứu.</td></tr>';
    $("#bangHd").querySelectorAll("input[data-k]").forEach(function (c) {
      c.onchange = function () { if (c.checked) chon.add(c.dataset.k); else chon.delete(c.dataset.k); demChon(); };
    });
    demChon();
  }
  function demChon() {
    $("#soChon").textContent = chon.size ? "Đã chọn " + chon.size + " hoá đơn" : "";
    $("#phamViTai").textContent = chon.size ? "Áp dụng cho " + chon.size + " hoá đơn đã chọn (cả nút Xuất)"
      : "Áp dụng cho mọi hoá đơn " + (loai === "purchase" ? "mua vào" : "bán ra") + " trong khoảng ngày";
  }
  function phamViXuat(them) {
    var d = { mst: dn, tu: $("#tu").value, den: $("#den").value };
    if (chon.size) { d.keys = Array.from(chon); d.loai = loai; }
    for (var k in them) d[k] = them[k];
    return d;
  }

  // ---------------- cài đặt tải
  var cd = null;
  function veChip(hop, ds, chonDs) {
    hop.innerHTML = ds.map(function (t) {
      var i = chonDs.indexOf(t.id);
      return '<button type="button" data-t="' + t.id + '" class="' + (i >= 0 ? "on" : "") + '">' +
        (i >= 0 ? "<b>" + (i + 1) + "</b>" : "") + esc(t.ten) + "</button>";
    }).join("");
    hop.querySelectorAll("button").forEach(function (b) {
      b.onclick = function () {
        var i = chonDs.indexOf(b.dataset.t);
        if (i >= 0) chonDs.splice(i, 1); else chonDs.push(b.dataset.t);
        luuCaiDat(true);
      };
    });
  }
  function veCaiDat(d) {
    cd = d.cai_dat;
    veChip($("#tokFile"), d.token_ten_file, cd.ten_file.tokens);
    veChip($("#tokExcel"), d.token_ten_excel, cd.ten_excel.tokens);
    $("#vietFile").checked = cd.ten_file.keep_viet;
    $("#vietExcel").checked = cd.ten_excel.keep_viet;
    $("#vdFile").textContent = d.vi_du_ten_file + ".xml / .pdf";
    $("#vdExcel").textContent = d.vi_du_ten_excel + ".xlsx";
    $("#vdThuMuc").textContent = d.vi_du_thu_muc + "/";
    $("#xepThuMuc").innerHTML = d.xep_thu_muc.map(function (x) {
      return '<label class="tich"><input type="radio" name="xepTm" value="' + x.id + '"' + (cd.xep_thu_muc === x.id ? " checked" : "") + "> " + esc(x.ten) + "</label>";
    }).join("");
    $("#xepThuMuc").querySelectorAll("input").forEach(function (r) { r.onchange = function () { cd.xep_thu_muc = r.value; luuCaiDat(true); }; });
    $("#giuZip").checked = cd.giu_zip;
    $("#soLuong").value = cd.luong;
    $("#ghiChuTrinhDuyet").textContent = d.co_trinh_duyet ? "" :
      "Muốn tải PDF Trống đồng: vào Thiết lập > Công cụ của MinMin, cài Trình duyệt một lần (miễn phí).";
  }
  async function moCaiDat() {
    var h = $("#hopCaiDat");
    if (!h.hidden) { h.hidden = true; return; }
    try { veCaiDat(await goi("cai-dat")); h.hidden = false; h.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
    catch (e) { bao(e.message); }
  }
  async function luuCaiDat(im) {
    if (!cd) return;
    cd.ten_file.keep_viet = $("#vietFile").checked;
    cd.ten_excel.keep_viet = $("#vietExcel").checked;
    cd.giu_zip = $("#giuZip").checked;
    cd.luong = Number($("#soLuong").value) || 3;
    try {
      veCaiDat(await goi("cai-dat", { json: cd }));
      if (!im) { $("#thongCaiDat").textContent = "Đã lưu."; $("#thongCaiDat").className = "thong ok"; }
    } catch (e) { bao(e.message); }
  }

  async function traCuu() {
    if (!$("#tu").value || !$("#den").value) { bao("Chọn khoảng ngày trước."); return; }
    try {
      var r = await goi("tra-cuu", { json: { mst: dn, tu: $("#tu").value, den: $("#den").value, loai: "ca_hai", he: $("#he").value } });
      theoDoi(r.viec, viecTai, function () { taiBang(); taiDn(); });
    } catch (e) { bao(e.message); }
  }
  async function taiXml() {
    try {
      var kieu = Array.prototype.map.call(document.querySelectorAll("[data-tai]:checked"), function (c) { return c.dataset.tai; });
      var r = await goi("tai", { json: { mst: dn, loai: loai, keys: chon.size ? Array.from(chon) : null,
        tu: $("#tu").value, den: $("#den").value, kieu: kieu } });
      bao("Đang tải " + r.so + " hoá đơn.");
      theoDoi(r.viec, viecTai, function () { chon.clear(); taiBang(); });
    } catch (e) { bao(e.message); }
  }
  async function canhBao() {
    try {
      var d = await goi("canh-bao?mst=" + encodeURIComponent(dn) + "&tu=" + $("#tu").value + "&den=" + $("#den").value);
      $("#hopCanhBao").hidden = false;
      $("#bangCanhBao").innerHTML = d.ds.map(function (w) {
        return "<tr><td>" + esc(w.muc) + "</td><td>" + esc(w.loai) + "</td><td>" + esc(w.so) + '</td><td class="ngay">' + esc(ngayVN(w.ngay)) +
          "</td><td>" + esc(w.doi_tac) + "</td><td>" + esc(w.noi_dung) + "</td></tr>";
      }).join("") || '<tr><td colspan="6" class="nho">Không có cảnh báo nào.</td></tr>';
    } catch (e) { bao(e.message); }
  }

  // ================= GMAIL =================
  var dsTk = [];
  function veChiMoi() {
    var tk = dsTk.filter(function (x) { return x.email === $("#gTk").value; })[0];
    $("#gChiMoi").disabled = !(tk && tk.co_moc);
    if ($("#gChiMoi").disabled) $("#gChiMoi").checked = false;
  }
  async function taiGmail() {
    try {
      var c = await goi("gmail/cau-hinh");
      dsTk = c.ds;
      $("#dsGmail").innerHTML = c.ds.map(function (x) {
        return '<li><span>' + esc(x.email) + '</span><span class="nhan' + (x.kieu === "google" ? " ok" : "") + '">' +
          (x.kieu === "google" ? "Google" : "Mật khẩu ứng dụng") + '</span><button type="button" class="xoa" data-xoa-tk="' +
          esc(x.email) + '" title="Gỡ tài khoản">✕</button></li>';
      }).join("") || '<li class="nho">Chưa có tài khoản nào.</li>';
      $("#dsGmail").querySelectorAll("[data-xoa-tk]").forEach(function (b) {
        b.onclick = async function () {
          if (!confirm("Gỡ " + b.dataset.xoaTk + " khỏi MinMin? Hoá đơn đã quét vẫn giữ.")) return;
          try { await goi("gmail/tai-khoan/" + encodeURIComponent(b.dataset.xoaTk), { method: "DELETE" }); } catch (e) { bao(e.message); }
          taiGmail();
        };
      });
      var cu = $("#gTk").value;
      $("#gTk").innerHTML = c.ds.map(function (x) { return '<option value="' + esc(x.email) + '">' + esc(x.email) + '</option>'; }).join("");
      if (cu && c.ds.some(function (x) { return x.email === cu; })) $("#gTk").value = cu;
      $("#gTk").hidden = c.ds.length < 2;
      veChiMoi();
      $("#duongVe").textContent = c.google.duong_ve;
      $("#fClient").client_id.value = c.google.client_id || "";
      $("#fClient").client_secret.placeholder = c.google.co_client ? "Đã lưu (gõ để đổi)" : "Client secret";
      $("#nutGoogle").classList.toggle("tat", !c.google.co_client);
      if (!c.google.co_client) $("#hopClient").open = true;
      var k = await goi("gmail/ket-qua");
      $("#bangGmail").innerHTML = k.ds.map(function (r) {
        var id = encodeURIComponent(r.id);
        var file = (r.co_xml ? '<a href="' + API + "gmail/xem/" + id + '" target="_blank" rel="noopener">Xem</a><a href="' + API + "gmail/tep/" + id + '/xml">XML</a>' : "") +
          (r.co_pdf ? '<a href="' + API + "gmail/tep/" + id + '/pdf">PDF</a>' : "") +
          (r.link ? '<a href="' + esc(r.link) + '" target="_blank" rel="noopener noreferrer">Trang tra cứu</a>' : "") +
          (r.ma_tra_cuu ? '<span class="nhan">Mã ' + esc(r.ma_tra_cuu) + '</span>' : "");
        return '<tr><td class="ngay">' + esc(ngayVN(r.ngay_hd)) + "</td><td>" + esc(r.so) + '</td><td class="doi">' + esc(r.ban_ten || r.tu) +
          "</td><td>" + esc(r.hop_thu || "") + '</td><td class="so">' + (r.tong ? tien(r.tong) : "") + "</td><td>" + esc(r.nha_cung_cap) + "</td><td>" +
          (r.can_tai_tay ? '<span class="nhan loi">Cần tải tay</span>' : "") + esc(r.trang_thai) + "</td><td>" +
          (r.lien_ket ? '<span class="nhan ok" title="MST ' + esc(r.lien_ket.mst) + '">Đã ghép</span>' : "") + "</td><td>" + file + "</td></tr>";
      }).join("") || '<tr><td colspan="9" class="nho">Chưa quét. Thêm tài khoản Gmail, chọn khoảng ngày rồi bấm Quét.</td></tr>';
    } catch (e) { bao(e.message); }
  }

  // ---------------- gắn sự kiện
  function gan() {
    document.querySelectorAll(".tab button").forEach(function (b) { b.onclick = function () { moTab(b.dataset.tab); }; });
    $("#fDn").onsubmit = async function (ev) {
      ev.preventDefault();
      var f = ev.target;
      try {
        var r = await goi("doanh-nghiep", { json: { mst: f.mst.value, ten: f.ten.value, mat_khau: f.mat_khau.value } });
        f.reset(); f.closest("details").open = false;
        dn = r.mst; await taiDn(); chonDn(r.mst);
      } catch (e) { bao(e.message); }
    };
    $("#doiCaptcha").onclick = layCaptcha;
    $("#nutDangNhap").onclick = dangNhap;
    $("#oCaptcha").onkeydown = function (e) { if (e.key === "Enter") dangNhap(); };
    document.querySelectorAll(".loai button").forEach(function (b) {
      b.onclick = function () {
        loai = b.dataset.loai; chon.clear();
        document.querySelectorAll(".loai button").forEach(function (x) { x.classList.toggle("on", x === b); });
        taiBang();
      };
    });
    $("#tu").onchange = $("#den").onchange = taiBang;
    $("#nutTraCuu").onclick = traCuu;
    $("#nutTai").onclick = taiXml;
    $("#nutCanhBao").onclick = canhBao;
    $("#nutCaiDat").onclick = moCaiDat;
    $("#luuCaiDat").onclick = function () { luuCaiDat(false); };
    ["#vietFile", "#vietExcel", "#giuZip", "#soLuong"].forEach(function (id) { $(id).onchange = function () { luuCaiDat(true); }; });
    $("#nutZip").onclick = async function () {
      var lt = Array.prototype.map.call(document.querySelectorAll("[data-zip]:checked"), function (c) { return c.dataset.zip; });
      if (!lt.length) { bao("Tích ít nhất một loại file."); return; }
      try { await taiFile("xuat", phamViXuat({ kieu: "zip", loai_tep: lt })); this.closest("details").open = false; } catch (e) { bao(e.message); }
    };
    $("#nutGopPdf").onclick = async function () {
      var m = (document.querySelector("[name=cheDoIn]:checked") || {}).value || "goc_uu_tien";
      try { await taiFile("xuat", phamViXuat({ kieu: "pdf_gop", che_do: m })); this.closest("details").open = false; } catch (e) { bao(e.message); }
    };
    $("#gGhep").onclick = async function () {
      try { var r = await goi("gmail/ghep-lai", { method: "POST" }); bao("Ghép thêm " + r.ghep + " hoá đơn có sẵn, thêm mới " + r.moi + " hoá đơn vào Tải Hoá Đơn."); taiGmail(); }
      catch (e) { bao(e.message); }
    };
    $("#nutDangXuat").onclick = async function () { await goi("dang-xuat/" + encodeURIComponent(dn), { method: "POST" }); taiDn(); };
    $("#loc").oninput = veBang;
    $("#chonHet").onchange = function () {
      var bat = this.checked;
      $("#bangHd").querySelectorAll("input[data-k]").forEach(function (c) {
        c.checked = bat; if (bat) chon.add(c.dataset.k); else chon.delete(c.dataset.k);
      });
      demChon();
    };
    document.querySelectorAll("[data-xuat]").forEach(function (b) {
      b.onclick = async function () {
        b.disabled = true;
        try { await taiFile("xuat", phamViXuat({ kieu: b.dataset.xuat })); }
        catch (e) { bao(e.message); } finally { b.disabled = false; }
      };
    });
    $("#fGmail").onsubmit = async function (ev) {
      ev.preventDefault();
      var f = ev.target;
      try {
        await goi("gmail/cau-hinh", { json: { email: f.email.value, mat_khau: f.mat_khau.value } });
        f.reset();
        $("#thongGmail").textContent = "Đã thêm."; $("#thongGmail").className = "thong ok";
        taiGmail();
      } catch (e) { $("#thongGmail").textContent = e.message; $("#thongGmail").className = "thong loi"; }
    };
    $("#fClient").onsubmit = async function (ev) {
      ev.preventDefault();
      var f = ev.target;
      try {
        await goi("gmail/google/client", { json: { client_id: f.client_id.value, client_secret: f.client_secret.value } });
        f.client_secret.value = "";
        $("#thongGmail").textContent = "Đã lưu. Giờ bấm Đăng nhập bằng Google."; $("#thongGmail").className = "thong ok";
        $("#hopClient").open = false;
        taiGmail();
      } catch (e) { $("#thongGmail").textContent = e.message; $("#thongGmail").className = "thong loi"; }
    };
    $("#chepVe").onclick = function () {
      navigator.clipboard.writeText($("#duongVe").textContent).then(function () { bao("Đã chép."); }, function () {});
    };
    $("#nutGoogle").onclick = function (ev) {
      if (this.classList.contains("tat")) { ev.preventDefault(); $("#hopClient").open = true; bao("Cài đặt Đăng nhập bằng Google trước (làm một lần)."); }
    };
    $("#gTk").onchange = veChiMoi;
    $("#nutQuet").onclick = async function () {
      try {
        var r = await goi("gmail/quet", { json: { email: $("#gTk").value, tu: $("#gTu").value, den: $("#gDen").value, chi_moi: $("#gChiMoi").checked } });
        theoDoi(r.viec, viecGmail, taiGmail);
      } catch (e) { bao(e.message); }
    };
    $("#gXuat").onclick = function () { taiFile("gmail/xuat").catch(function (e) { bao(e.message); }); };
    $("#gZip").onclick = function () { taiFile("gmail/zip").catch(function (e) { bao(e.message); }); };
  }

  document.addEventListener("click", function (ev) {
    document.querySelectorAll("details.menu[open]").forEach(function (m) { if (!m.contains(ev.target)) m.open = false; });
  });

  async function batDau() {
    datNgayMacDinh($("#tu"), $("#den"));
    datNgayMacDinh($("#gTu"), $("#gDen"));
    gan();
    var s;
    try { s = await goi("trang-thai"); } catch (e) { bao(e.message); return; }
    tt.tai = s.tai_hoa_don; tt.gmail = s.gmail;
    document.querySelector('.tab [data-tab="tai"]').disabled = !tt.tai;
    document.querySelector('.tab [data-tab="gmail"]').disabled = !tt.gmail;
    if (!s.gia_lap_chrome) $("#ghiChuCffi").textContent = "Máy chủ thiếu thư viện curl_cffi nên cổng thuế dễ chặn (lỗi 403). Cập nhật MinMin bản mới.";
    var qs = new URLSearchParams(location.search);
    var muon = qs.get("tab") === "gmail" ? "gmail" : "tai";
    if (qs.get("them")) setTimeout(function () { bao("Đã thêm " + qs.get("them") + " bằng Google."); }, 300);
    moTab(muon);
  }
  batDau();
})();
