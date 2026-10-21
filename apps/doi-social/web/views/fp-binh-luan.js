/* Fanpage (API) - Bình luận - #/fp-binh-luan (tab Hộp bình luận · Quy tắc) + nút Dừng mọi tự động */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic, FP = DS.fp;
  var HANH_DONG = { tra_loi: "Trả lời theo mẫu", tra_loi_ai: "AI soạn trả lời", an: "Ẩn bình luận", an_va_tra_loi: "Ẩn và trả lời" };
  var daHoiGui = false;

  function hoiCongKhai(cau, nut) {
    if (daHoiGui) return Promise.resolve(true);
    return DS.xacNhan(cau + " Câu trả lời hiện công khai dưới bình luận, ai xem bài cũng thấy.", nut || "Gửi").then(function (ok) { if (ok) daHoiGui = true; return ok; });
  }

  // ================================================================ hộp bình luận
  function tabHop(el, ctx, sauDoi) {
    var F = { chi_khach: true, trang_thai: "", trang: "", q: "", trang_so: 1 }, chon = {}, ds = [], mo = {};
    var body = el.querySelector("#bl-body");
    body.innerHTML = '<div class="grid g4" id="bl-so">' + '<div class="sk sk-card"></div><div class="sk sk-card"></div><div class="sk sk-card"></div><div class="sk sk-card"></div>' + "</div>" +
      '<div class="card card-x mt"><div class="card-h"><h3>Bình luận mới <span class="sub" id="bl-quet"></span></h3><div class="row"><button class="btn btn-sm" data-act="lam-moi">' + ic("refresh") +
      'Làm mới</button><button class="btn btn-sm btn-soft" data-act="quet">' + ic("scan") + 'Quét ngay</button></div></div><div class="filters">' +
      '<label class="chk small"><input type="checkbox" class="cb" id="bl-khach" checked>Chỉ bình luận của khách</label>' +
      '<select class="sel" id="bl-tt" aria-label="Trạng thái"><option value="">Mọi trạng thái</option>' + Object.keys(FP.TT_BL).map(function (k) { return '<option value="' + k + '">' + esc(FP.TT_BL[k][0]) + "</option>"; }).join("") + "</select>" +
      '<select class="sel" id="bl-trang" aria-label="Trang"><option value="">Mọi Trang</option></select>' +
      '<div class="inp-ic" style="min-width:180px;flex:1">' + ic("search") + '<input class="inp" id="bl-q" placeholder="Tìm chữ hoặc tên người bình luận"></div></div><div id="bl-bulk"></div><div id="bl-ds"></div></div>';
    FP.layTrang().then(function (d) {
      if (!ctx.alive || d.ok === false) return;
      el.querySelector("#bl-trang").innerHTML += DS.list(d).map(function (t) { return '<option value="' + esc(t.id) + '">' + esc(t.ten || t.id) + "</option>"; }).join("");
    });
    function soChon() { return Object.keys(chon).filter(function (k) { return chon[k]; }); }
    function veBulk() {
      var n = soChon().length;
      el.querySelector("#bl-bulk").innerHTML = n ? '<div class="filters fp-bulk"><b>' + n + ' bình luận</b><span class="grow"></span>' +
        '<button class="btn btn-sm" data-act="hd" data-hd="ai_soan">' + ic("spark") + "AI soạn</button>" +
        '<button class="btn btn-sm btn-ok" data-act="hd" data-hd="gui">' + ic("send") + "Gửi câu đã soạn</button>" +
        '<button class="btn btn-sm" data-act="hd" data-hd="an">' + ic("eye") + "Ẩn</button>" +
        '<button class="btn btn-sm" data-act="hd" data-hd="hien">Hiện</button>' +
        '<button class="btn btn-sm" data-act="hd" data-hd="bo_qua">Bỏ qua</button><button class="btn btn-sm btn-ghost" data-act="bo-chon">Bỏ chọn</button></div>' : "";
    }
    function veSo(h) {
      h = h || {};
      var o = function (i, cls, k, v, s) { return '<div class="stat"><div class="k"><span class="ico ' + cls + '">' + ic(i) + "</span>" + esc(k) + '</div><div class="v">' + FP.so(v) + '</div><div class="s">' + s + "</div></div>"; };
      el.querySelector("#bl-so").innerHTML = o("ok", "ico-ok", "Đã trả lời hôm nay", h.da_tra_loi, "đã lên Facebook") + o("check", "", "Chờ bạn duyệt", h.cho_duyet, "câu trả lời đã soạn") +
        o("send", "ico-info", "Chờ gửi", h.cho_gui, "MinMin gửi trong ít phút") + o("alert", "ico-err", "Lỗi", h.loi, h.loi ? "xem cột trạng thái" : "không có lỗi");
    }
    function dong(c) {
      var cho = c.trang_thai === "cho_duyet" || c.trang_thai === "cho_gui";
      var h = '<tr class="' + (chon[c.id] ? "fp-on" : "") + (c.an ? " fp-off" : "") + '"><td><input type="checkbox" class="cb" data-chon="' + esc(c.id) + '"' + (chon[c.id] ? " checked" : "") + ' aria-label="Chọn"></td>' +
        '<td class="nw small"><b class="clip" style="display:block;max-width:150px">' + esc(c.trang_ten || c.trang_id || "") + '</b><span class="sub" title="' + esc(DS.gioDu(c.luc)) + '">' + esc(DS.tuongDoi(c.luc)) + "</span></td>" +
        '<td style="min-width:260px;max-width:440px"><div class="row" style="gap:6px;flex-wrap:nowrap">' + DS.av(c.tu_ten, "av-s") + "<b class=\"clip\">" + esc(c.tu_ten || "Ẩn danh") + "</b>" +
        (c.la_cua_trang ? '<span class="bd bd-brand">Trang</span>' : "") + (c.an ? '<span class="bd">Đang ẩn</span>' : "") + (c.cha_id ? '<span class="tiny muted">trả lời trong luồng</span>' : "") + "</div>" +
        '<div class="small pre" style="margin-top:3px">' + esc(c.noi_dung || "") + "</div>" +
        (c.tra_loi ? '<div class="fp-rep' + (cho ? " cho" : "") + '">' + ic("chat") + '<span class="pre">' + esc(c.tra_loi) + "</span></div>" : "") +
        (c.loi ? '<div class="tiny" style="color:var(--err)">' + esc(c.loi) + "</div>" : "") + "</td>" +
        "<td>" + DS.bdMap(FP.TT_BL, c.trang_thai || "moi") + (c.quy_tac_id ? '<div class="sub">theo quy tắc #' + esc(c.quy_tac_id) + "</div>" : "") + "</td>" +
        '<td class="nw" style="text-align:right">' + (cho && c.tra_loi ? '<button class="btn btn-xs btn-ok" data-act="mot" data-hd="gui" data-id="' + esc(c.id) + '">' + ic("send") + "Gửi</button> " : "") +
        '<button class="btn btn-xs" data-act="mo-tl" data-id="' + esc(c.id) + '">' + ic("chat") + "Trả lời</button> " +
        '<button class="btn btn-xs" data-act="mot" data-hd="ai_soan" data-id="' + esc(c.id) + '" title="AI soạn câu trả lời, chờ bạn duyệt">' + ic("spark") + "AI soạn</button> " +
        '<button class="btn btn-xs" data-act="mot" data-hd="' + (c.an ? "hien" : "an") + '" data-id="' + esc(c.id) + '">' + (c.an ? "Hiện" : "Ẩn") + "</button> " +
        (c.trang_thai !== "bo_qua" ? '<button class="btn btn-xs btn-ghost" data-act="mot" data-hd="bo_qua" data-id="' + esc(c.id) + '">Bỏ qua</button>' : "") + "</td></tr>";
      if (mo[c.id]) h += '<tr class="fp-tl-row"><td></td><td colspan="4"><div class="fp-tl"><textarea class="ta" rows="2" data-tl="' + esc(c.id) + '" placeholder="Viết câu trả lời cho ' + esc(c.tu_ten || "khách") + '">' +
        esc(c.tra_loi || "") + '</textarea><div class="row-sb mt-s"><span class="tiny muted">Gửi xong hiện công khai dưới bình luận.</span><span class="row"><button class="btn btn-sm btn-ghost" data-act="dong-tl" data-id="' + esc(c.id) +
        '">Thôi</button><button class="btn btn-sm btn-pri" data-act="gui-tl" data-id="' + esc(c.id) + '">' + ic("send") + "Gửi trả lời</button></span></div></div></td></tr>";
      return h;
    }
    function veDs(tong, trangSo, moiTrang) {
      var box = el.querySelector("#bl-ds");
      if (!ds.length) { box.innerHTML = DS.rong("Không có bình luận nào", F.q || F.trang_thai || F.trang ? "Đổi bộ lọc thử xem." : "Bấm Quét ngay để đọc bình luận mới trên các Trang.", "chat"); return; }
      box.innerHTML = '<div class="tw"><table class="tbl tbl-in" style="min-width:980px"><thead><tr><th class="w1"><input type="checkbox" class="cb" id="bl-all" aria-label="Chọn tất cả"></th><th>Trang</th><th>Bình luận</th><th>Trạng thái</th><th></th></tr></thead><tbody>' +
        ds.map(dong).join("") + "</tbody></table></div>" + DS.phanTrang(tong, trangSo, moiTrang);
    }
    var T = { tong: 0, ts: 1, mt: 50 };
    function nap(nen) {
      var box = el.querySelector("#bl-ds");
      if (!nen) box.innerHTML = '<div class="tw"><table class="tbl tbl-in"><tbody>' + DS.skelDong(6, 5) + "</tbody></table></div>";
      return FP.api("GET", "/binh-luan" + DS.qs({ trang: F.trang, trang_thai: F.trang_thai, chi_khach: F.chi_khach ? 1 : "", q: F.q.trim(), trang_so: F.trang_so }), null, { quiet: !!nen }).then(function (d) {
        if (!ctx.alive) return;
        if (d.ok === false) { if (!nen) box.innerHTML = DS.loiThe(d.error, true); return; }
        ds = DS.list(d); veSo(d.hom_nay);
        el.querySelector("#bl-quet").textContent = d.quet_luc ? "quét " + DS.tuongDoi(d.quet_luc) : "chưa quét lần nào";
        var con = {}; ds.forEach(function (c) { if (chon[c.id]) con[c.id] = true; }); chon = con;
        T = { tong: d.tong != null ? d.tong : ds.length, ts: d.trang_so || F.trang_so, mt: d.moi_trang || 50 };
        veBulk(); veDs(T.tong, T.ts, T.mt);
      });
    }
    function lam(ids, hd, them) {
      var b = Object.assign({ ids: ids, hanh_dong: hd }, them || {});
      var hoi = hd === "gui" ? hoiCongKhai("Gửi " + ids.length + " câu trả lời đã soạn lên Facebook?", "Gửi " + ids.length + " câu") : Promise.resolve(true);
      return hoi.then(function (ok) {
        if (!ok) return false;
        return FP.api("POST", "/binh-luan/hanh-dong", b).then(function (d) {
          if (d.ok === false) return false;
          var nhan = { ai_soan: "AI đang soạn, câu trả lời vào Chờ duyệt", gui: "Đã xếp gửi", an: "Đã ẩn", hien: "Đã hiện lại", bo_qua: "Đã bỏ qua", tra_loi: "Đã xếp gửi câu trả lời" }[hd] || "Xong";
          DS.toast(nhan + (ids.length > 1 ? " (" + ids.length + ")" : ""), "ok");
          nap(true); if (sauDoi) sauDoi(); return true;
        });
      });
    }
    var hen = null;
    el.addEventListener("input", function (e) { if (e.target.id === "bl-q") { F.q = e.target.value; F.trang_so = 1; clearTimeout(hen); hen = setTimeout(function () { nap(); }, 350); } });
    el.addEventListener("change", function (e) {
      var t = e.target;
      if (t.id === "bl-khach") { F.chi_khach = t.checked; F.trang_so = 1; nap(); }
      else if (t.id === "bl-tt") { F.trang_thai = t.value; F.trang_so = 1; nap(); }
      else if (t.id === "bl-trang") { F.trang = t.value; F.trang_so = 1; nap(); }
      else if (t.id === "bl-all") { ds.forEach(function (c) { chon[c.id] = t.checked; }); veBulk(); veDs(T.tong, T.ts, T.mt); }
      else if (t.getAttribute("data-chon")) { chon[t.getAttribute("data-chon")] = t.checked; t.closest("tr").classList.toggle("fp-on", t.checked); veBulk(); }
    });
    DS.bind(el, {
      "lam-moi": function () { nap(); },
      "quet": function (b) {
        b.disabled = true;
        FP.api("POST", "/binh-luan/quet", F.trang ? { trang: F.trang } : {}).then(function (d) {
          b.disabled = false;
          if (d.ok === false) return;
          DS.toast(d.so_moi ? "Có " + d.so_moi + " bình luận mới" : "Không có bình luận mới", d.so_moi ? "ok" : "info"); nap();
        });
      },
      "trang": function (t) { F.trang_so = +t.getAttribute("data-trang") || 1; nap(); },
      "bo-chon": function () { chon = {}; veBulk(); veDs(T.tong, T.ts, T.mt); },
      "hd": function (t) { lam(soChon(), t.getAttribute("data-hd")).then(function (ok) { if (ok) chon = {}; }); },
      "mot": function (t) { lam([t.getAttribute("data-id")], t.getAttribute("data-hd")); },
      "mo-tl": function (t) { var id = t.getAttribute("data-id"); mo[id] = !mo[id]; veDs(T.tong, T.ts, T.mt); var ta = el.querySelector('[data-tl="' + id + '"]'); if (ta) ta.focus(); },
      "dong-tl": function (t) { delete mo[t.getAttribute("data-id")]; veDs(T.tong, T.ts, T.mt); },
      "gui-tl": function (t) {
        var id = t.getAttribute("data-id"), ta = el.querySelector('[data-tl="' + id + '"]'), chu = ta ? ta.value.trim() : "";
        if (!chu) { DS.toast("Viết câu trả lời trước đã", "err"); return; }
        hoiCongKhai("Gửi câu trả lời này lên Facebook?", "Gửi trả lời").then(function (ok) {
          if (!ok) return;
          t.disabled = true;
          FP.api("POST", "/binh-luan/hanh-dong", { ids: [id], hanh_dong: "tra_loi", chu: chu }).then(function (d) {
            t.disabled = false;
            if (d.ok === false) return;
            delete mo[id]; DS.toast("Đã xếp gửi câu trả lời", "ok"); nap(true);
          });
        });
      }
    });
    ctx.every(function () {
      var a = document.activeElement;
      if (Object.keys(mo).length || (a && el.contains(a) && a.matches("input:not([type=checkbox]),select,textarea"))) return;
      nap(true);
    }, 30000);
    return nap();
  }

  // ================================================================ quy tắc
  function moQuyTac(q, xong) {
    q = q || {};
    var cu = !!q.id, pv = q.pham_vi || {};
    Promise.all([FP.layTrang(), FP.layNhom()]).then(function (a) {
      var dsTrang = DS.list(a[0]), dsNhom = DS.list(a[1]);
      if (!dsNhom.length) dsNhom = (a[0] && a[0].nhom) || [];
      var hd = q.hanh_dong || "tra_loi";
      var m = DS.modal({ title: cu ? "Sửa quy tắc" : "Thêm quy tắc", wide: true, focus: false,
        body: '<div class="fgrid"><div class="fld"><label for="qt-ten">Tên quy tắc <span class="req">*</span></label><input class="inp" id="qt-ten" value="' + esc(q.ten || "") + '" placeholder="Ví dụ: Hỏi giá, xin link"></div>' +
          '<div class="fld"><label for="qt-ut">Ưu tiên</label><input class="inp" type="number" id="qt-ut" value="' + esc(q.uu_tien || 0) + '"><div class="hint">Số lớn xét trước. Mỗi bình luận chỉ áp một quy tắc đầu tiên khớp.</div></div></div>' +
          '<div class="fld mt"><label for="qt-tk">Từ khoá</label><textarea class="ta" id="qt-tk" rows="2" placeholder="giá, bao nhiêu, ib, link">' + esc((q.tu_khoa || []).join(", ")) +
          '</textarea><div class="hint">Cách nhau bằng dấu phẩy hoặc xuống dòng. Để trống thì khớp mọi bình luận của khách.</div></div>' +
          '<div class="fld"><label>Làm gì</label><div class="seg" id="qt-hd">' + Object.keys(HANH_DONG).map(function (k) { return '<button type="button" data-v="' + k + '" class="' + (k === hd ? "on" : "") + '">' + esc(HANH_DONG[k]) + "</button>"; }).join("") + "</div></div>" +
          '<div class="fld" id="qt-mau-f"><label for="qt-mau">Mẫu trả lời</label><textarea class="ta" id="qt-mau" rows="4" placeholder="{Dạ|Vâng} {bạn|anh chị} xem link ở bình luận đầu nhé&#10;Mình đã ib {bạn|anh chị} rồi ạ">' + esc((q.mau || []).join("\n")) +
          '</textarea><div class="hint">Mỗi dòng một câu, MinMin chọn ngẫu nhiên và spin {a|b}.</div></div>' +
          '<div class="sec" style="margin-top:14px"><div class="sec-t">Áp cho</div><div class="fld"><label>Nhóm</label><div>' + (dsNhom.length ? dsNhom.map(function (n) {
            var on = (pv.nhom || []).map(String).indexOf(String(n.id)) >= 0;
            return '<label class="chk" style="margin:0 14px 6px 0"><input type="checkbox" class="cb" data-qt-nhom value="' + esc(n.id) + '"' + (on ? " checked" : "") + ">" + esc(n.ten) + "</label>";
          }).join("") : '<span class="small muted">Chưa có nhóm.</span>') + '</div></div><div class="fld"><label>Thêm từng Trang</label><div id="qt-trang"></div><div class="hint">Không chọn nhóm hay Trang nào thì quy tắc áp cho mọi Trang bật Tự trả lời / Tự ẩn.</div></div></div>' +
          '<div class="swrow mt"><div class="grow"><div style="font-weight:500">Tự gửi, không chờ duyệt</div><div class="hint">Tắt (mặc định): câu trả lời vào Chờ duyệt, bạn bấm Gửi.</div>' +
          '<div class="hint fp-warn-hint" id="qt-cb"' + (q.tu_gui ? "" : " hidden") + ">" + ic("alert") + " Đang bật: MinMin tự đăng câu trả lời công khai dưới bình luận của khách, không qua tay bạn.</div></div>" + DS.sw('id="qt-gui"', !!q.tu_gui) + "</div>",
        foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="qt-luu">' + (cu ? "Lưu" : "Thêm quy tắc") + "</button>" });
      var B = m.body, pick = FP.boChonTrang(B.querySelector("#qt-trang"), dsTrang, pv.trang || [], { cao: 200 });
      function capHd() { B.querySelector("#qt-mau-f").hidden = hd === "an" || hd === "tra_loi_ai"; }
      capHd();
      B.querySelector("#qt-hd").addEventListener("click", function (e) {
        var b = e.target.closest("button"); if (!b) return;
        hd = b.getAttribute("data-v");
        Array.prototype.forEach.call(this.children, function (x) { x.classList.toggle("on", x === b); });
        capHd();
      });
      B.querySelector("#qt-gui").addEventListener("change", function () {
        var sw = this;
        if (!sw.checked) { B.querySelector("#qt-cb").hidden = true; return; }
        DS.xacNhan("Bật Tự gửi? MinMin sẽ tự đăng câu trả lời công khai lên Facebook ngay khi bình luận khớp quy tắc, không chờ bạn duyệt.", "Bật Tự gửi", true).then(function (ok) {
          sw.checked = ok; B.querySelector("#qt-cb").hidden = !ok;
        });
      });
      m.foot.querySelector("#qt-luu").onclick = function () {
        var ten = B.querySelector("#qt-ten").value.trim();
        if (!ten) { DS.toast("Đặt tên cho quy tắc", "err"); return; }
        var mau = B.querySelector("#qt-mau").value.split("\n").map(function (x) { return x.trim(); }).filter(Boolean);
        if ((hd === "tra_loi" || hd === "an_va_tra_loi") && !mau.length) { DS.toast("Nhập ít nhất một câu trả lời mẫu", "err"); return; }
        var n = function (v) { return isNaN(+v) ? v : +v; };
        var b = { ten: ten, uu_tien: +B.querySelector("#qt-ut").value || 0, hanh_dong: hd, mau: mau, tu_gui: B.querySelector("#qt-gui").checked,
          tu_khoa: B.querySelector("#qt-tk").value.split(/[,\n]/).map(function (x) { return x.trim(); }).filter(Boolean),
          pham_vi: { nhom: Array.prototype.map.call(B.querySelectorAll("[data-qt-nhom]:checked"), function (c) { return n(c.value); }), trang: pick.lay() } };
        if (!cu) b.bat = true;
        var btn = this; btn.disabled = true;
        FP.api(cu ? "PATCH" : "POST", "/quy-tac" + (cu ? "/" + encodeURIComponent(q.id) : ""), b).then(function (d) {
          btn.disabled = false;
          if (d.ok === false) return;
          DS.toast(cu ? "Đã lưu quy tắc" : "Đã thêm quy tắc", "ok"); m.close(); xong();
        });
      };
    });
  }

  function tabQuyTac(el, ctx) {
    var body = el.querySelector("#bl-body"), ds = [];
    body.innerHTML = '<div class="note mb">' + ic("info") + "<span>Quy tắc chạy khi MinMin quét bình luận (10 phút một lần) trên các Trang bật <b>Tự trả lời</b> hoặc <b>Tự ẩn</b> trong cấu hình nhóm. " +
      "Quy tắc chưa bật Tự gửi chỉ soạn sẵn câu trả lời ở Chờ duyệt.</span></div><div class=\"card card-x\"><div class=\"card-h\"><h3>Quy tắc tự động</h3><button class=\"btn btn-sm btn-pri\" data-act=\"them\">" +
      ic("plus") + 'Thêm quy tắc</button></div><div id="qt-ds">' + DS.skel(3) + "</div></div>";
    function nap() {
      return FP.api("GET", "/quy-tac").then(function (d) {
        if (!ctx.alive) return;
        var box = body.querySelector("#qt-ds");
        if (d.ok === false) { box.innerHTML = DS.loiThe(d.error, true); return; }
        ds = DS.list(d);
        if (!ds.length) { box.innerHTML = DS.rong("Chưa có quy tắc nào", "Ví dụ: bình luận chứa \"giá\" thì trả lời \"Dạ mình ib bạn nhé\"; bình luận có số điện thoại thì ẩn.", "chat"); return; }
        box.innerHTML = '<div class="tw" style="border-top:1px solid var(--line)"><table class="tbl" style="min-width:820px"><thead><tr><th>Quy tắc</th><th>Áp cho</th><th>Từ khoá</th><th>Làm gì</th><th>Gửi</th><th>Bật</th><th></th></tr></thead><tbody>' +
          ds.map(function (q) {
            var pv = q.pham_vi || {}, nN = (pv.nhom || []).length, nT = (pv.trang || []).length, tk = q.tu_khoa || [];
            return "<tr><td><b>" + esc(q.ten) + '</b><div class="sub">ưu tiên ' + esc(q.uu_tien || 0) + '</div></td><td class="small">' + (nN || nT ? (nN ? nN + " nhóm" : "") + (nN && nT ? ", " : "") + (nT ? nT + " Trang" : "") : "Mọi Trang") +
              '</td><td><div class="row" style="gap:4px">' + (tk.length ? tk.slice(0, 5).map(function (x) { return '<span class="bd bd-out">' + esc(x) + "</span>"; }).join("") + (tk.length > 5 ? '<span class="tiny muted">+' + (tk.length - 5) + "</span>" : "") :
                '<span class="small muted">Mọi bình luận</span>') + '</div></td><td class="small nw">' + esc(HANH_DONG[q.hanh_dong] || q.hanh_dong || "") + (q.mau && q.mau.length ? '<div class="sub">' + q.mau.length + " mẫu</div>" : "") + "</td>" +
              "<td>" + (q.tu_gui ? DS.bd("Tự gửi", "err", true) : DS.bd("Chờ duyệt", "warn")) + "</td><td>" + DS.sw('data-bat="' + esc(q.id) + '" aria-label="Bật quy tắc"', !(q.bat === 0 || q.bat === false)) +
              '</td><td class="nw" style="text-align:right"><button class="btn btn-xs" data-act="sua" data-id="' + esc(q.id) + '">' + ic("edit") + 'Sửa</button> <button class="btn btn-xs btn-dan" data-act="xoa" data-id="' + esc(q.id) +
              '" aria-label="Xoá quy tắc">' + ic("trash") + "</button></td></tr>";
          }).join("") + "</tbody></table></div>";
      });
    }
    function tim(id) { return ds.filter(function (q) { return String(q.id) === String(id); })[0]; }
    body.addEventListener("change", function (e) {
      var id = e.target.getAttribute("data-bat");
      if (id == null) return;
      var bat = e.target.checked, t = e.target;
      FP.api("PATCH", "/quy-tac/" + encodeURIComponent(id), { bat: bat }).then(function (d) { if (d.ok === false) t.checked = !bat; else DS.toast(bat ? "Đã bật quy tắc" : "Đã tắt quy tắc", "ok"); });
    });
    DS.bind(body, {
      "tai-lai": nap,
      "them": function () { moQuyTac(null, nap); },
      "sua": function (t) { var q = tim(t.getAttribute("data-id")); if (q) moQuyTac(q, nap); },
      "xoa": function (t) {
        var q = tim(t.getAttribute("data-id")) || {};
        DS.xacNhan("Xoá quy tắc " + (q.ten || "") + "?", "Xoá", true).then(function (ok) {
          if (ok) FP.api("DELETE", "/quy-tac/" + encodeURIComponent(q.id)).then(function (d) { if (d.ok !== false) { DS.toast("Đã xoá quy tắc", "ok"); nap(); } });
        });
      }
    });
    return nap();
  }

  DS.view("fp-binh-luan", {
    title: "Bình luận Fanpage",
    render: function (el, ctx) {
      var tab = ctx.q.tab === "quy-tac" ? "quy-tac" : "hop", dung = false;
      el.innerHTML = DS.ph("Bình luận Fanpage", "Bình luận của khách trên mọi Trang về một chỗ. Trả lời, ẩn, nhờ AI soạn, hoặc đặt quy tắc tự động.", '<span id="bl-dung-nut"></span>') +
        '<div id="bl-dung"></div>' + DS.tabs([{ id: "hop", ten: "Hộp bình luận" }, { id: "quy-tac", ten: "Quy tắc tự động" }], tab, "#/fp-binh-luan?tab=") + '<div id="bl-body" class="stack"></div>';
      function veDung() {
        el.querySelector("#bl-dung").innerHTML = FP.dungBanner(dung);
        el.querySelector("#bl-dung-nut").innerHTML = dung ? "" : '<button class="btn fp-stop" data-act="dung" title="Chặn ngay mọi việc tự động của Fanpage">' + ic("stop") + "Dừng mọi tự động</button>";
      }
      function napDung() {
        return FP.api("GET", "/cai-dat", null, { quiet: true }).then(function (d) {
          if (!ctx.alive || d.ok === false) return;
          dung = !!(d.cai_dat || d).dung_tu_dong; veDung();
        });
      }
      DS.bind(el.querySelector(".ph"), {
        "dung": function () {
          DS.xacNhan("Dừng mọi tự động của Fanpage ngay? MinMin ngừng đăng theo lịch, tự trả lời, tự ẩn, bình luận sau đăng và quét kênh. Bài đã hẹn sẵn trên Facebook vẫn lên (nút này không rút được).", "Dừng ngay", true).then(function (ok) {
            if (ok) FP.datDung(true).then(function (v) { if (v !== null) { dung = true; veDung(); } });
          });
        }
      });
      DS.bind(el.querySelector("#bl-dung"), { "fp-chay-lai": function () { FP.datDung(false).then(function (v) { if (v === false) { dung = false; veDung(); } }); } });
      veDung(); napDung();
      return tab === "quy-tac" ? tabQuyTac(el, ctx) : tabHop(el, ctx);
    }
  });
})();
