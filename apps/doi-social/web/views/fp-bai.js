/* Fanpage (API) - Bài đăng - #/fp-bai (bộ lọc, bảng, việc hàng loạt, Tạo bài hàng loạt) */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic, FP = DS.fp;
  var CAN_TEP = { anh: 1, album: 1, video: 1, reel: 1, story: 1 };

  function soLieu(s) {
    s = s || {};
    var cx = s.cam_xuc != null ? s.cam_xuc : s.reactions, bl = s.binh_luan != null ? s.binh_luan : s.comments, cs = s.chia_se != null ? s.chia_se : s.shares;
    var tc = s.tiep_can != null ? s.tiep_can : s.post_impressions_unique;
    if (cx == null && bl == null && cs == null && tc == null) return '<span class="muted">-</span>';
    return '<span title="Cảm xúc · bình luận · chia sẻ">' + FP.so(cx) + " · " + FP.so(bl) + " · " + FP.so(cs) + "</span>" + (tc != null ? '<div class="sub">' + FP.so(tc) + " tiếp cận</div>" : "");
  }
  DS.fp.soLieu = soLieu;

  // ================================================================ kiểm tra (chạy thử, không đăng)
  function kiemTra(id) {
    var m = DS.modal({ title: "Kiểm tra bài #" + id, body: '<div class="small muted">Đang kiểm token, quyền, tệp và giờ đăng. Không đăng gì lên Facebook.</div>' + DS.skel(3) });
    FP.api("POST", "/bai/" + encodeURIComponent(id) + "/kiem-tra", {}, { quiet: true }).then(function (d) {
      var buoc = d.buoc || [];
      if (!buoc.length && d.ok === false) { m.body.innerHTML = '<div class="note note-err">' + ic("alert") + "<span>" + esc(d.error || "Chưa kiểm tra được") + "</span></div>"; return; }
      var tot = buoc.every(function (b) { return b.ok; });
      m.body.innerHTML = '<div class="note ' + (tot ? "note-ok" : "note-err") + ' mb">' + ic(tot ? "ok" : "alert") + "<span>" + (tot ? "Mọi bước đều ổn, tới giờ bài sẽ lên được." : "Có bước chưa ổn, sửa trước khi tới giờ đăng.") + "</span></div>" +
        '<ol class="steps fp-buoc">' + buoc.map(function (b) {
          return '<li class="' + (b.ok ? "ok" : "loi") + '"><div class="grow"><div class="row" style="gap:6px">' + ic(b.ok ? "ok" : "alert") + "<b>" + esc(b.ten || "") + "</b></div>" +
            (b.chi_tiet ? '<div class="small muted">' + esc(b.chi_tiet) + "</div>" : "") + "</div></li>";
        }).join("") + "</ol>";
    });
  }

  // ================================================================ sửa một bài
  function suaBai(b, xong) {
    var daDang = ["da_dang", "dang_dang"].indexOf(b.trang_thai) >= 0;
    var m = DS.modal({ title: "Sửa bài #" + b.id + " · " + (b.trang_ten || b.trang_id || ""), wide: true,
      body: (daDang ? '<div class="note note-warn mb">' + ic("alert") + "<span>Bài đã lên Facebook. Sửa ở đây chỉ đổi bản lưu trong MinMin.</span></div>" : "") +
        (b.trang_thai === "da_hen_fb" ? '<div class="note mb">' + ic("info") + "<span>Bài đang hẹn sẵn trên Facebook. Đổi giờ ở đây thì MinMin sẽ hẹn lại.</span></div>" : "") +
        FP.thumbs(b.media, 6) + '<div class="fld mt-s"><label for="sb-nd">Nội dung</label><textarea class="ta" id="sb-nd" rows="7">' + esc(b.noi_dung || "") + "</textarea></div>" +
        '<div class="fgrid mt"><div class="fld"><label for="sb-link">Link kèm</label><input class="inp" id="sb-link" value="' + esc(b.link || "") + '" placeholder="https://..."></div>' +
        '<div class="fld"><label for="sb-hen">Giờ đăng</label><input class="inp" type="datetime-local" id="sb-hen" value="' + esc(FP.dtLocal(b.hen_luc)) + '"><div class="hint">Để trống thì không hẹn, bài chờ bạn bấm Đăng ngay.</div></div></div>' +
        '<div class="fld"><label for="sb-bl">Bình luận sau khi đăng</label><textarea class="ta" id="sb-bl" rows="2" placeholder="Để trống nếu không bình luận">' + esc(b.binh_luan || "") + "</textarea></div>",
      foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="sb-luu">Lưu</button>' });
    m.foot.querySelector("#sb-luu").onclick = function () {
      var btn = this; btn.disabled = true;
      FP.api("PATCH", "/bai/" + encodeURIComponent(b.id), { noi_dung: m.body.querySelector("#sb-nd").value, link: m.body.querySelector("#sb-link").value.trim(),
        binh_luan: m.body.querySelector("#sb-bl").value, hen_luc: FP.tuDt(m.body.querySelector("#sb-hen").value) }).then(function (d) {
        btn.disabled = false;
        if (d.ok === false) return;
        DS.toast("Đã lưu bài", "ok"); m.close(); xong();
      });
    };
  }

  // ================================================================ Tạo bài hàng loạt
  function taoHangLoat(xong, dong) {
    var daTao = false;
    var S = { dich: "trang", loai: "anh", tep: [], nd: "tay", chia: "mot_trang", bl: "khong", hen: "tu_dong", xem: null, dang: 0, album: 4 };
    var m = DS.modal({ title: "Tạo bài hàng loạt", wide: true, focus: false, body: DS.skel(6),
      foot: '<span class="tiny muted grow" id="tb-goi-y" style="align-self:center">Bấm Xem trước để xem bài sẽ tạo. Chưa ghi gì cho tới khi bấm Tạo.</span><button class="btn" data-x>Thôi</button>' +
        '<button class="btn" id="tb-xem">' + ic("eye") + 'Xem trước</button><button class="btn btn-pri" id="tb-tao" disabled>' + ic("plus") + "Tạo bài</button>",
      onClose: function () { if (dong) dong(daTao); } });
    var B = m.body, picker = null, dsTrang = [], dsNhom = [], dsKho = [];
    Promise.all([FP.layTrang(true), FP.layKho(true)]).then(function (a) {
      if (a[0].ok === false) { B.innerHTML = DS.rong("Chưa tải được danh sách Trang", esc(a[0].error), "box"); return; }
      dsTrang = DS.list(a[0]); dsNhom = a[0].nhom || []; dsKho = DS.list(a[1]);
      if (!dsTrang.length) { B.innerHTML = DS.rong("Chưa có Trang nào", 'Đồng bộ Trang ở <a href="#/fp-trang">Trang &amp; Nhóm</a> trước.', "list"); return; }
      ve();
    });
    function seg(id, ds, v) {
      return '<div class="seg" data-tb-seg="' + id + '">' + ds.map(function (x) { return '<button type="button" data-v="' + x[0] + '" class="' + (x[0] === v ? "on" : "") + '">' + esc(x[1]) + "</button>"; }).join("") + "</div>";
    }
    function khoOpt(loai) {
      var l = dsKho.filter(function (k) { return k.loai === loai; });
      return l.length ? l.map(function (k) { return '<option value="' + esc(k.id) + '">' + esc(k.ten) + " (" + FP.so(k.so) + " mục)</option>"; }).join("") : '<option value="">Chưa có kho nào</option>';
    }
    function ve() {
      B.innerHTML = '<div class="sec"><div class="sec-t">1. Đăng lên</div>' + seg("dich", [["trang", "Chọn Trang"], ["nhom", "Cả một nhóm"]], S.dich) +
        '<div id="tb-trang" class="mt-s"></div><div class="fld mt-s" id="tb-nhom-f" hidden><label for="tb-nhom">Nhóm</label><select class="sel" id="tb-nhom">' + (dsNhom.length ? dsNhom.map(function (n) {
          return '<option value="' + esc(n.id) + '">' + esc(n.ten) + " (" + FP.so(n.so) + " Trang)</option>"; }).join("") : '<option value="">Chưa có nhóm nào</option>') + "</select></div></div>" +
        '<div class="sec"><div class="sec-t">2. Loại bài</div>' + seg("loai", FP.LOAI_THU_TU.map(function (k) { return [k, FP.LOAI[k]]; }), S.loai) + "</div>" +
        '<div class="sec" id="tb-tep-sec"><div class="sec-t">3. Ảnh / video <span class="bd bd-brand" id="tb-tep-dem">0 tệp</span></div>' +
        '<label class="drop">' + ic("upload") + ' <span>Bấm để chọn tệp (chọn được nhiều tệp, tải lên ngay)</span><input type="file" id="tb-tep" multiple accept="image/*,video/*"></label>' +
        '<div class="hint mt-s" id="tb-tep-goi-y"></div><div class="fp-up" id="tb-tep-ds"></div>' +
        '<div class="fld mt-s" id="tb-album-f" hidden><label for="tb-album">Mỗi album bao nhiêu ảnh</label><input class="inp" type="number" min="2" max="10" id="tb-album" value="' + S.album + '" style="max-width:120px"></div></div>' +
        '<div class="sec"><div class="sec-t">4. Nội dung (caption)</div>' + seg("nd", [["tay", "Gõ tay"], ["kho", "Lấy từ kho"]], S.nd) +
        '<div class="fld mt-s" id="tb-nd-tay"><textarea class="ta" id="tb-nd" rows="6" placeholder="Mỗi dòng là nội dung một bài.&#10;Bài nhiều dòng: tách các bài bằng một dòng chỉ có ---&#10;Dùng được spin {Xem ngay|Đừng bỏ lỡ} và {ten_trang}, {ten_tep}."></textarea>' +
        '<div class="hint" id="tb-nd-dem">0 nội dung</div></div><div class="fld mt-s" id="tb-nd-kho" hidden><select class="sel" id="tb-kho">' + khoOpt("noi_dung") + '</select><div class="hint">Mỗi bài lấy một mục theo cách chọn của kho (ngẫu nhiên, lần lượt, theo số trong tên tệp).</div></div></div>' +
        '<div class="sec"><div class="sec-t">5. Chia cho các Trang</div>' + seg("chia", [["mot_trang", "Mỗi tệp / nội dung một Trang (xoay vòng)"], ["tat_ca", "Trang nào cũng đăng đủ"]], S.chia) +
        '<div class="hint mt-s">Xoay vòng: 10 video cho 5 Trang thì mỗi Trang 2 bài. Đăng đủ: mỗi Trang nhận cả 10.</div></div>' +
        '<div class="sec"><div class="sec-t">6. Kèm theo</div><div class="fld"><label>Bình luận sau khi đăng</label>' + seg("bl", [["khong", "Không"], ["chu", "Gõ chữ"], ["kho", "Từ kho bình luận"]], S.bl) + "</div>" +
        '<div class="fld mt-s" id="tb-bl-chu" hidden><input class="inp" id="tb-bl" placeholder="Ví dụ: Link xem full ở đây {ten_tep}"></div><div class="fld mt-s" id="tb-bl-kho" hidden><select class="sel" id="tb-blk">' + khoOpt("binh_luan") + "</select></div>" +
        '<div class="swrow mt"><div class="grow"><div style="font-weight:500">Đăng kèm Story</div><div class="hint">Lấy tệp đầu tiên của mỗi bài đăng thêm thành Story.</div></div>' + DS.sw('id="tb-story"', false) + "</div>" +
        '<div class="swrow"><div class="grow"><div style="font-weight:500">Đăng luôn sang Instagram</div><div class="hint">Chỉ với Trang có Instagram doanh nghiệp đi kèm, tính vào hạn 24 giờ.</div></div>' + DS.sw('id="tb-ig"', false) + "</div></div>" +
        '<div class="sec"><div class="sec-t">7. Giờ đăng</div>' + seg("hen", [["tu_dong", "Tự xếp theo lịch của Trang"], ["ngay", "Đăng ngay khi duyệt"], ["gio", "Chọn giờ"]], S.hen) +
        '<div class="fld mt-s" id="tb-gio-f" hidden><input class="inp" type="datetime-local" id="tb-gio" style="max-width:260px"></div>' +
        '<div class="note note-warn mt-s" id="tb-ngay-cb" hidden>' + ic("alert") + "<span>Đăng ngay: bài lên Facebook công khai ngay khi bạn bấm Duyệt (hoặc ngay khi tạo, với Trang đã tắt Duyệt trước).</span></div></div>" +
        '<div class="sec" id="tb-xt" hidden></div>';
      picker = FP.boChonTrang(B.querySelector("#tb-trang"), dsTrang, [], { doi: boXem });
      capNhat();
    }
    function capNhat() {
      B.querySelector("#tb-trang").hidden = S.dich !== "trang";
      B.querySelector("#tb-nhom-f").hidden = S.dich !== "nhom";
      B.querySelector("#tb-tep-sec").hidden = !CAN_TEP[S.loai];
      B.querySelector("#tb-album-f").hidden = S.loai !== "album";
      B.querySelector("#tb-tep-goi-y").textContent = { anh: "Mỗi ảnh là một bài.", album: "Ảnh được gom thành từng album theo số ảnh bên dưới.", video: "Mỗi video là một bài.", reel: "Video dọc 9:16, 3 đến 90 giây.",
        story: "Mỗi ảnh hoặc video là một Story." }[S.loai] || "";
      B.querySelector("#tb-nd-tay").hidden = S.nd !== "tay";
      B.querySelector("#tb-nd-kho").hidden = S.nd !== "kho";
      B.querySelector("#tb-bl-chu").hidden = S.bl !== "chu";
      B.querySelector("#tb-bl-kho").hidden = S.bl !== "kho";
      B.querySelector("#tb-gio-f").hidden = S.hen !== "gio";
      B.querySelector("#tb-ngay-cb").hidden = S.hen !== "ngay";
      B.querySelector("#tb-tep-dem").textContent = S.tep.length + " tệp" + (S.dang ? ", đang tải " + S.dang : "");
      demNd();
      veTep();
    }
    function demNd() {
      var n = FP.tachMuc(B.querySelector("#tb-nd").value).length;
      B.querySelector("#tb-nd-dem").textContent = n + " nội dung" + (CAN_TEP[S.loai] && S.tep.length && n ? ", ghép lần lượt với từng tệp" : "");
    }
    function veTep() {
      B.querySelector("#tb-tep-ds").innerHTML = S.tep.map(function (t, i) {
        return '<div class="fp-up-i" title="' + esc(t.ten || t.tep) + '">' + (t.loai === "video" || FP.laVideo(t) ? '<span class="vid">' + ic("video") + "</span>" : '<img src="' + FP.tepUrl(t) + '" alt="" loading="lazy">') +
          '<span class="tiny clip">' + esc(t.ten || t.tep) + '</span><button type="button" class="fp-up-x" data-tb-xoa="' + i + '" aria-label="Bỏ tệp">' + ic("x") + "</button></div>";
      }).join("");
    }
    function boXem() {
      S.xem = null;
      var t = m.foot.querySelector("#tb-tao"); t.disabled = true; t.innerHTML = ic("plus") + "Tạo bài";
      var x = B.querySelector("#tb-xt"); if (x) x.hidden = true;
    }
    function taiLen(files) {
      if (!files.length) return;
      var fd = new FormData();
      Array.prototype.forEach.call(files, function (f) { fd.append("tep", f, f.name); });
      S.dang += files.length; capNhat();
      FP.api("POST", "/media", fd).then(function (d) {
        S.dang = Math.max(0, S.dang - files.length);
        if (d.ok !== false) { S.tep = S.tep.concat(DS.list(d)); boXem(); }
        capNhat();
      });
    }
    function yeuCau(thu) {
      var b = { loai: S.loai, chia: S.chia, story: B.querySelector("#tb-story").checked, ig: B.querySelector("#tb-ig").checked, chay_thu: !!thu };
      if (S.dich === "trang") { b.trang_ids = picker ? picker.lay() : []; if (!b.trang_ids.length) return "Chọn ít nhất một Trang"; }
      else { var nv = B.querySelector("#tb-nhom").value; if (!nv) return "Chọn một nhóm"; b.nhom_id = isNaN(+nv) ? nv : +nv; }
      if (CAN_TEP[S.loai]) {
        if (S.dang) return "Chờ tải tệp xong đã";
        var ten = S.tep.map(function (t) { return t.tep; });
        if (!ten.length) return "Chọn ít nhất một tệp cho bài " + FP.LOAI[S.loai].toLowerCase();
        if (S.loai === "album") {
          var n = Math.max(2, Math.min(10, +B.querySelector("#tb-album").value || 4)), g = [];
          for (var i = 0; i < ten.length; i += n) g.push(ten.slice(i, i + n));
          b.media = g;
        } else b.media = ten;
      }
      if (S.nd === "tay") {
        b.noi_dung = FP.tachMuc(B.querySelector("#tb-nd").value);
        if (S.loai === "chu" && !b.noi_dung.length) return "Nhập ít nhất một nội dung";
      } else {
        var kv = B.querySelector("#tb-kho").value;
        if (!kv) return "Chọn một kho nội dung";
        b.kho_id = isNaN(+kv) ? kv : +kv;
      }
      if (S.bl === "chu") { var c = B.querySelector("#tb-bl").value.trim(); if (c) b.binh_luan = c; }
      else if (S.bl === "kho") { var bk = B.querySelector("#tb-blk").value; if (!bk) return "Chọn một kho bình luận"; b.kho_binh_luan_id = isNaN(+bk) ? bk : +bk; }
      if (S.hen === "gio") { var t = FP.tuDt(B.querySelector("#tb-gio").value); if (!t) return "Chọn giờ đăng"; if (t < DS.bayGio()) return "Giờ đăng đã qua"; b.hen = t; }
      else b.hen = S.hen;
      return b;
    }
    function veXem(d) {
      var ds = Array.isArray(d.xem_truoc) ? d.xem_truoc : DS.list(d), x = B.querySelector("#tb-xt");
      var so = d.so != null ? d.so : ds.length, thang = ds.filter(function (b) { return b.trang_thai === "cho_dang"; }).length;
      x.hidden = false;
      x.innerHTML = '<div class="sec-t">' + ic("eye") + "Xem trước: " + FP.so(so) + " bài" + (d.bo_trung ? ' <span class="bd bd-warn">Bỏ ' + d.bo_trung + " bài trùng</span>" : "") + "</div>" +
        (thang ? '<div class="note note-warn mb">' + ic("alert") + "<span><b>" + thang + " bài</b> sẽ vào thẳng hàng chờ đăng vì Trang của chúng đang tắt Duyệt trước.</span></div>" : "") +
        (ds.length ? '<div class="tw" style="border:1px solid var(--line);border-radius:12px;max-height:340px;overflow:auto"><table class="tbl"><thead><tr><th>Trang</th><th>Loại</th><th>Nội dung</th><th>Tệp</th><th>Giờ đăng</th></tr></thead><tbody>' +
          ds.slice(0, 200).map(function (b) {
            var t = dsTrang.filter(function (y) { return String(y.id) === String(b.trang_id); })[0] || { ten: b.trang_ten || b.trang_id };
            var md = (b.media || []).reduce(function (a, z) { return a.concat(Array.isArray(z) ? z : [z]); }, []);
            return '<tr><td><div class="row" style="flex-wrap:nowrap">' + FP.avTrang(t, "av-s") + '<span class="clip" style="max-width:160px">' + esc(t.ten || "") + '</span></div></td><td class="nw">' + esc(FP.LOAI[b.loai] || b.loai || "") +
              '</td><td style="min-width:220px"><div class="small clamp2">' + esc(b.noi_dung || "(không chữ)") + "</div>" + (b.binh_luan ? '<div class="tiny muted clip">Bình luận: ' + esc(b.binh_luan) + "</div>" : "") + "</td>" +
              '<td class="small">' + (md.length ? esc(md.map(FP.tepTen).join(", ")).slice(0, 80) : '<span class="muted">-</span>') + '</td><td class="nw small">' +
              (b.hen_luc ? esc(DS.gio(b.hen_luc)) + (b.cach_hen === "fb" ? ' <span class="bd bd-brand">FB</span>' : "") : b.hen === "ngay" || S.hen === "ngay" ? "Ngay khi duyệt" : '<span class="muted">Đăng tay</span>') + "</td></tr>";
          }).join("") + "</tbody></table></div>" + (ds.length > 200 ? '<div class="tiny muted mt-s">Hiện 200 bài đầu.</div>' : "") : DS.rong("Không có bài nào được tạo", "Kiểm tra lại tệp, nội dung hoặc Trang đã chọn.", "list"));
      x.scrollIntoView({ block: "nearest", behavior: "smooth" });
      var t = m.foot.querySelector("#tb-tao");
      t.disabled = !so;
      t.innerHTML = ic("plus") + "Tạo " + FP.so(so) + " bài" + (thang === so && so ? "" : " (chờ duyệt)");
    }
    B.addEventListener("click", function (e) {
      var b = e.target.closest("[data-tb-seg] button");
      if (b) {
        var g = b.parentNode, k = g.getAttribute("data-tb-seg");
        Array.prototype.forEach.call(g.children, function (x) { x.classList.toggle("on", x === b); });
        S[k] = b.getAttribute("data-v"); boXem(); capNhat(); return;
      }
      var x = e.target.closest("[data-tb-xoa]");
      if (x) { S.tep.splice(+x.getAttribute("data-tb-xoa"), 1); boXem(); capNhat(); }
    });
    B.addEventListener("input", function (e) { if (e.target.id === "tb-nd") demNd(); if (e.target.closest(".sec")) boXem(); });
    B.addEventListener("change", function (e) {
      if (e.target.id === "tb-tep") { taiLen(e.target.files || []); e.target.value = ""; return; }
      boXem();
    });
    m.foot.querySelector("#tb-xem").onclick = function () {
      var b = yeuCau(true), btn = this;
      if (typeof b === "string") { DS.toast(b, "err"); return; }
      btn.disabled = true;
      FP.api("POST", "/bai/tao", b).then(function (d) {
        btn.disabled = false;
        if (d.ok === false) return;
        S.xem = b; veXem(d);
      });
    };
    m.foot.querySelector("#tb-tao").onclick = function () {
      var b = yeuCau(false), btn = this;
      if (typeof b === "string") { DS.toast(b, "err"); return; }
      btn.disabled = true; btn.textContent = "Đang tạo...";
      FP.api("POST", "/bai/tao", b).then(function (d) {
        btn.disabled = false;
        if (d.ok === false) { btn.innerHTML = ic("plus") + "Thử lại"; return; }
        var so = d.so != null ? d.so : DS.list(d).length;
        DS.toast("Đã tạo " + FP.so(so) + " bài" + (d.bo_trung ? ", bỏ " + d.bo_trung + " bài trùng" : "") + ". Bài nằm ở Chờ duyệt, bấm Duyệt để cho đăng.", "ok");
        daTao = true; m.close(); if (xong) xong(so);
      });
    };
  }
  DS.fp.taoHangLoat = taoHangLoat;

  // ================================================================ màn chính
  DS.view("fp-bai", {
    title: "Bài đăng Fanpage",
    render: function (el, ctx) {
      var F = { trang_thai: ctx.q.trang_thai || "", trang: ctx.q.trang || "", nhom: ctx.q.nhom || "", loai: "", tu: "", den: "", q: "", sap_xep: "moi", trang_so: 1 };
      var chon = {}, ds = [], dem = {};
      el.innerHTML = DS.ph("Bài đăng Fanpage", "Bài tạo hàng loạt, từ kho, từ kênh nguồn hay AI đều vào Chờ duyệt. Bấm Duyệt thì MinMin mới đăng theo lịch.",
        '<button class="btn" data-act="lam-moi">' + ic("refresh") + 'Làm mới</button><a class="btn" id="fb-csv" href="#">' + ic("download") + 'Xuất CSV</a><button class="btn btn-pri" data-act="tao">' + ic("plus") + "Tạo bài hàng loạt</button>") +
        '<div class="card card-x"><div class="filters" style="padding-bottom:0;border-bottom:0"><div class="chips" id="fb-tt"></div></div><div class="filters" id="fb-loc">' +
        '<div class="inp-ic" style="min-width:180px;flex:1">' + ic("search") + '<input class="inp" id="fb-q" placeholder="Tìm trong nội dung"></div>' +
        '<select class="sel" id="fb-trang" aria-label="Trang"><option value="">Mọi Trang</option></select><select class="sel" id="fb-nhom" aria-label="Nhóm"><option value="">Mọi nhóm</option></select>' +
        '<select class="sel" id="fb-loai" aria-label="Loại"><option value="">Mọi loại</option>' + FP.LOAI_THU_TU.map(function (k) { return '<option value="' + k + '">' + FP.LOAI[k] + "</option>"; }).join("") + "</select>" +
        '<input class="inp" type="date" id="fb-tu" aria-label="Từ ngày"><span class="muted small">đến</span><input class="inp" type="date" id="fb-den" aria-label="Đến ngày">' +
        '<select class="sel" id="fb-sx" aria-label="Sắp xếp"><option value="moi">Mới tạo trước</option><option value="hen">Giờ đăng gần nhất</option><option value="tuong_tac">Tương tác cao</option></select></div>' +
        '<div id="fb-bulk"></div><div id="fb-ds"><div class="tw"><table class="tbl tbl-in"><tbody>' + DS.skelDong(6, 6) + "</tbody></table></div></div></div>";

      FP.layTrang().then(function (d) {
        if (!ctx.alive || d.ok === false) return;
        var s = el.querySelector("#fb-trang"), n = el.querySelector("#fb-nhom");
        s.innerHTML += DS.list(d).map(function (t) { return '<option value="' + esc(t.id) + '"' + (String(t.id) === F.trang ? " selected" : "") + ">" + esc(t.ten || t.id) + "</option>"; }).join("");
        n.innerHTML += (d.nhom || []).map(function (x) { return '<option value="' + esc(x.id) + '"' + (String(x.id) === F.nhom ? " selected" : "") + ">" + esc(x.ten) + "</option>"; }).join("");
      });

      function boLoc() {
        var ngay = function (s, cuoi) { if (!s) return ""; var d = new Date(s + "T00:00:00"); if (cuoi) d.setDate(d.getDate() + 1); return Math.floor(d.getTime() / 1000) - (cuoi ? 1 : 0); };
        return { trang_thai: F.trang_thai, trang: F.trang, nhom: F.nhom, loai: F.loai, tu: ngay(F.tu), den: ngay(F.den, true), q: F.q.trim(), sap_xep: F.sap_xep };
      }
      function soChon() { return Object.keys(chon).filter(function (k) { return chon[k]; }); }
      function veTT() {
        var tong = 0; Object.keys(dem).forEach(function (k) { tong += dem[k] || 0; });
        el.querySelector("#fb-tt").innerHTML = '<button class="chip' + (F.trang_thai === "" ? " on" : "") + '" data-act="tt" data-v="">Tất cả <span class="cnt">' + FP.so(tong) + "</span></button>" +
          FP.TT_BAI_THU_TU.map(function (k) {
            return '<button class="chip' + (F.trang_thai === k ? " on" : "") + '" data-act="tt" data-v="' + k + '">' + esc(FP.TT_BAI[k][0]) + ' <span class="cnt">' + FP.so(dem[k]) + "</span></button>";
          }).join("");
      }
      function veBulk() {
        var n = soChon().length;
        el.querySelector("#fb-bulk").innerHTML = n ? '<div class="filters fp-bulk"><b>' + n + ' bài đã chọn</b><span class="grow"></span>' +
          '<button class="btn btn-sm btn-ok" data-act="hd" data-hd="duyet">' + ic("check") + "Duyệt</button>" +
          '<button class="btn btn-sm" data-act="hd" data-hd="dang_ngay">' + ic("send") + "Đăng ngay</button>" +
          '<button class="btn btn-sm" data-act="hd" data-hd="thu_lai">' + ic("refresh") + "Thử lại</button>" +
          '<button class="btn btn-sm" data-act="hd" data-hd="xep_lai_lich">' + ic("calendar") + "Xếp lại lịch</button>" +
          '<button class="btn btn-sm" data-act="hd" data-hd="bo">' + ic("x") + "Bỏ</button>" +
          '<button class="btn btn-sm btn-dan" data-act="hd" data-hd="xoa">' + ic("trash") + "Xoá</button>" +
          '<button class="btn btn-sm btn-ghost" data-act="bo-chon">Bỏ chọn</button></div>' : "";
      }
      function nap(nen) {
        var bl = boLoc(), box = el.querySelector("#fb-ds");
        el.querySelector("#fb-csv").href = FP.GOC + "/bai/xuat.csv" + DS.qs(bl);
        if (!nen) box.innerHTML = '<div class="tw"><table class="tbl tbl-in"><tbody>' + DS.skelDong(6, 6) + "</tbody></table></div>";
        return FP.api("GET", "/bai" + DS.qs(Object.assign({ trang_so: F.trang_so, moi_trang: 50 }, bl)), null, { quiet: !!nen }).then(function (d) {
          if (!ctx.alive) return;
          if (d.ok === false) { if (!nen) box.innerHTML = DS.loiThe(d.error, true); return; }
          ds = DS.list(d); dem = d.dem || {};
          var con = {}; ds.forEach(function (b) { if (chon[b.id]) con[b.id] = true; }); chon = con;
          veTT(); veBulk();
          var tong = d.tong != null ? d.tong : ds.length;
          if (!ds.length) {
            box.innerHTML = DS.rong(F.trang_thai || F.q || F.trang || F.loai ? "Không có bài khớp bộ lọc" : "Chưa có bài nào", "Bấm Tạo bài hàng loạt để đưa ảnh, video hoặc nội dung lên nhiều Trang một lần.", "list",
              '<button class="btn btn-pri" data-act="tao">' + ic("plus") + "Tạo bài hàng loạt</button>");
            return;
          }
          var tatCa = ds.every(function (b) { return chon[b.id]; });
          box.innerHTML = '<div class="tw"><table class="tbl tbl-in" style="min-width:1060px"><thead><tr><th class="w1"><input type="checkbox" class="cb" id="fb-all"' + (tatCa ? " checked" : "") +
            ' aria-label="Chọn tất cả"></th><th>Trang</th><th>Bài</th><th>Trạng thái</th><th>Giờ đăng</th><th class="num">Số liệu</th><th></th></tr></thead><tbody>' +
            ds.map(function (b) {
              return '<tr class="' + (chon[b.id] ? "fp-on" : "") + '"><td><input type="checkbox" class="cb" data-chon="' + esc(b.id) + '"' + (chon[b.id] ? " checked" : "") + ' aria-label="Chọn bài ' + esc(b.id) + '"></td>' +
                '<td><div class="row" style="flex-wrap:nowrap">' + FP.avTrang({ ten: b.trang_ten || b.trang_id, anh: b.trang_anh }) + '<div style="min-width:0"><b class="clip" style="display:block;max-width:170px">' + esc(b.trang_ten || b.trang_id) +
                '</b><div class="sub">#' + esc(b.id) + " · " + esc(FP.NGUON_BAI[b.nguon] || b.nguon || "") + "</div></div></div></td>" +
                '<td style="min-width:280px;max-width:420px"><div class="row" style="flex-wrap:nowrap;align-items:flex-start">' + FP.thumbs(b.media, 2) + '<div class="grow" style="min-width:0"><div class="row" style="gap:5px">' +
                '<span class="bd bd-out">' + ic(FP.LOAI_IC[b.loai] || "file") + esc(FP.LOAI[b.loai] || b.loai || "") + "</span>" + (b.story ? '<span class="bd bd-out">+Story</span>' : "") + (b.ig ? '<span class="bd bd-out">+IG</span>' : "") + "</div>" +
                '<div class="small clamp2" style="margin-top:3px">' + esc(b.noi_dung || "(không có chữ)") + "</div>" + (b.loi ? '<div class="tiny" style="color:var(--err)">' + esc(b.loi) + "</div>" : "") + "</div></div></td>" +
                "<td>" + FP.ttBai(b) + '</td><td class="nw small">' + (b.dang_luc ? "Đăng " + esc(DS.gio(b.dang_luc)) : b.hen_luc ? esc(DS.gio(b.hen_luc)) + '<div class="sub">' + esc(DS.tuongDoi(b.hen_luc)) +
                (b.cach_hen === "fb" ? " · hẹn trên FB" : "") + "</div>" : '<span class="muted">Chưa hẹn</span>') + '</td><td class="num small nw">' + soLieu(b.so_lieu) + "</td>" +
                '<td class="nw" style="text-align:right">' + (b.url ? '<a class="btn btn-xs" href="' + esc(b.url) + '" target="_blank" rel="noopener">' + ic("ext") + "Mở</a> " : "") +
                '<button class="btn btn-xs" data-act="kiem" data-id="' + esc(b.id) + '" title="Kiểm tra thử, không đăng">' + ic("scan") + 'Kiểm tra</button> <button class="btn btn-xs" data-act="sua" data-id="' + esc(b.id) + '">' + ic("edit") + "Sửa</button></td></tr>";
            }).join("") + "</tbody></table></div>" + DS.phanTrang(tong, d.trang_so || F.trang_so, d.moi_trang || 50);
        });
      }
      function lamViec(hd) {
        var ids = soChon(), n = ids.length;
        var NHAN = { duyet: "Duyệt", bo: "Bỏ", dang_ngay: "Đăng ngay", thu_lai: "Thử lại", xoa: "Xoá", xep_lai_lich: "Xếp lại lịch" };
        var hoi = hd === "dang_ngay" ? DS.xacNhan("Đăng ngay " + n + " bài lên Facebook? " + FP.CANH_BAO_CONG_KHAI, "Đăng ngay " + n + " bài", true) :
          hd === "duyet" ? DS.xacNhan("Duyệt " + n + " bài? Bài vào hàng chờ và MinMin tự đăng công khai khi tới giờ hẹn.", "Duyệt " + n + " bài") :
          hd === "xoa" ? DS.xacNhan("Xoá hẳn " + n + " bài khỏi MinMin? Bài đã lên Facebook vẫn còn trên Facebook.", "Xoá " + n + " bài", true) :
          hd === "xep_lai_lich" ? DS.xacNhan("Xếp lại giờ cho " + n + " bài theo lịch hiện tại của Trang? Bài đã hẹn trên FB sẽ được hẹn lại.", "Xếp lại") : Promise.resolve(true);
        hoi.then(function (ok) {
          if (!ok) return;
          FP.api("POST", "/bai/hanh-dong", { ids: ids.map(function (x) { return isNaN(+x) ? x : +x; }), hanh_dong: hd }).then(function (d) {
            if (d.ok === false) return;
            DS.toast(NHAN[hd] + ": " + FP.so(d.so != null ? d.so : n) + " bài", "ok");
            chon = {}; nap();
          });
        });
      }
      var hen = null;
      el.addEventListener("input", function (e) { if (e.target.id === "fb-q") { F.q = e.target.value; F.trang_so = 1; clearTimeout(hen); hen = setTimeout(function () { nap(); }, 350); } });
      el.addEventListener("change", function (e) {
        var t = e.target, map = { "fb-trang": "trang", "fb-nhom": "nhom", "fb-loai": "loai", "fb-tu": "tu", "fb-den": "den", "fb-sx": "sap_xep" };
        if (map[t.id]) { F[map[t.id]] = t.value; F.trang_so = 1; nap(); }
        else if (t.id === "fb-all") { ds.forEach(function (b) { chon[b.id] = t.checked; }); veBulk(); Array.prototype.forEach.call(el.querySelectorAll("[data-chon]"), function (c) { c.checked = t.checked; c.closest("tr").classList.toggle("fp-on", t.checked); }); }
        else if (t.getAttribute("data-chon")) { chon[t.getAttribute("data-chon")] = t.checked; t.closest("tr").classList.toggle("fp-on", t.checked); veBulk(); }
      });
      function tim(id) { return ds.filter(function (b) { return String(b.id) === String(id); })[0]; }
      DS.bind(el, {
        "lam-moi": function () { nap(); },
        "tao": function () { taoHangLoat(function () { F.trang_thai = "cho_duyet"; F.trang_so = 1; nap(); }); },
        "tt": function (t) { F.trang_thai = t.getAttribute("data-v"); F.trang_so = 1; nap(); },
        "trang": function (t) { F.trang_so = +t.getAttribute("data-trang") || 1; nap(); },
        "bo-chon": function () { chon = {}; nap(true); },
        "hd": function (t) { lamViec(t.getAttribute("data-hd")); },
        "kiem": function (t) { kiemTra(t.getAttribute("data-id")); },
        "sua": function (t) { var b = tim(t.getAttribute("data-id")); if (b) suaBai(b, function () { nap(true); }); }
      });
      ctx.every(function () {
        var a = document.activeElement;
        if (document.querySelector(".modal-bg") || (a && el.contains(a) && a.matches("input:not([type=checkbox]),select"))) return;
        nap(true);
      }, 30000);
      var kq = nap();
      // #/fp-bai?tao=1 (từ Tổng quan Fanpage): mở luôn hộp Tạo bài hàng loạt, đóng thì bỏ ?tao khỏi địa chỉ
      if (ctx.q.tao) taoHangLoat(null, function (daTao) { DS.datQ(daTao ? { tao: "", trang_thai: "cho_duyet" } : { tao: "" }); });
      return kq;
    }
  });
})();
