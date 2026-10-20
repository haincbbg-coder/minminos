/* Kiến thức cho Agent - #/kien-thuc và #/kien-thuc/<id>?tab=tai-lieu|hoi-dap|nhom */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;
  var TT = { dang_dung: ["AI đang dùng", "ok"], cho_duyet: ["Chờ duyệt", "warn"] };

  function taoMoi(loai) {
    var m = DS.modal({
      title: loai === "chu_de" ? "Thêm chủ đề" : "Thêm sản phẩm",
      body: '<div class="fld"><label for="km-ten">Tên <span class="req">*</span></label><input class="inp" id="km-ten" placeholder="' + (loai === "chu_de" ? "Ví dụ: Mẹ bỉm sữa, Nuôi dạy con" : "Ví dụ: Váy lụa Halimi") + '"></div>' +
        '<div class="fld"><label for="km-mt">Mô tả ngắn</label><textarea class="ta" id="km-mt" rows="3" placeholder="' + (loai === "chu_de" ? "Chủ đề chỉ để Agent tương tác tự nhiên (thích, bình luận), không bán hàng." : "Sản phẩm là gì, cho ai, điểm khác biệt") + '"></textarea></div>',
      foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="km-ok">Tạo</button>'
    });
    m.foot.querySelector("#km-ok").onclick = function () {
      var ten = m.body.querySelector("#km-ten").value.trim();
      if (!ten) { DS.toast("Nhập tên", "err"); return; }
      DS.api("POST", "/doi-social/kien-thuc", { loai: loai, ten: ten, mo_ta: m.body.querySelector("#km-mt").value.trim(), trang_thai: "dang_dung" }).then(function (d) {
        if (d.ok === false) return;
        DS.boNho("kt"); m.close();
        var id = (d.kien_thuc && d.kien_thuc.id) || d.id;
        DS.toast("Đã tạo, thêm tài liệu và hỏi đáp để AI hiểu rõ hơn", "ok");
        if (id != null) DS.go("kien-thuc/" + id); else DS.veLai();
      });
    };
  }

  function ketQuaBoNao(muc, nut) {
    if (!muc.length) return DS.rong("Không thấy ghi chú nào khớp", "Thử từ khoá khác, ví dụ tên sản phẩm hoặc thương hiệu.", "search");
    return '<div class="stack">' + muc.map(function (x) {
      return '<div class="qa" data-path="' + esc(x.path) + '"><div class="row-sb" style="flex-wrap:nowrap;align-items:flex-start"><div style="min-width:0"><b class="clip">' + esc(x.ten || x.path) +
        '</b><div class="tiny muted clip">' + esc(x.path) + "</div></div>" + nut + '</div><div class="small muted clamp2" style="margin-top:4px">' + esc(x.trich || "") + "</div></div>";
    }).join("") + "</div>";
  }

  function nhapBoNao() {
    var m = DS.modal({
      title: "Nhập từ bộ não MinMin",
      body: '<div class="small muted mb">Tìm một ghi chú trong wiki/bộ não (mô tả sản phẩm, bảng giá, chính sách) để tạo hồ sơ. Ghi chú được gắn luôn vào hồ sơ nên lần sau bạn sửa wiki thì Agent đọc bản mới.</div>' +
        '<div class="row" style="flex-wrap:nowrap"><input class="inp" id="bn-q" placeholder="Ví dụ: váy lụa, bảng giá, chính sách đổi trả"><button class="btn btn-pri" id="bn-tim">' + ic("search") + "Tìm</button></div>" +
        '<div id="bn-kq" class="mt"></div>',
      foot: '<button class="btn" data-x>Đóng</button>'
    });
    var q = m.body.querySelector("#bn-q"), kq = m.body.querySelector("#bn-kq");
    function tim() {
      var t = q.value.trim(); if (!t) return;
      kq.innerHTML = DS.skel(3);
      DS.api("GET", "/doi-social/bo-nao/tim?q=" + encodeURIComponent(t)).then(function (d) {
        if (d.ok === false) { kq.innerHTML = DS.loiThe(d.error); return; }
        if (d.co_bo_nao === false) { kq.innerHTML = DS.rong("Chưa nối được bộ não", "MinMin chưa có brain mặc định trên máy chủ này.", "book"); return; }
        kq.innerHTML = ketQuaBoNao(d.muc || [], '<div class="row" style="flex-wrap:nowrap"><button class="btn btn-xs" data-loai="chu_de">Tạo chủ đề</button><button class="btn btn-xs btn-pri" data-loai="san_pham">Tạo sản phẩm</button></div>');
      });
    }
    m.body.querySelector("#bn-tim").onclick = tim;
    q.addEventListener("keydown", function (e) { if (e.key === "Enter") tim(); });
    kq.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-loai]"); if (!b) return;
      var path = b.closest("[data-path]").getAttribute("data-path");
      b.disabled = true;
      DS.api("POST", "/doi-social/kien-thuc/tu-bo-nao", { path: path, loai: b.getAttribute("data-loai") }).then(function (d) {
        b.disabled = false;
        if (d.ok === false) return;
        DS.boNho("kt"); m.close(); DS.toast("Đã tạo hồ sơ từ ghi chú, kiểm lại giá và từ khoá nhé", "ok");
        DS.go("kien-thuc/" + d.kien_thuc.id);
      });
    });
    setTimeout(function () { q.focus(); }, 50);
  }

  function danhSach(el, ctx) {
    el.innerHTML = DS.ph("Kiến thức cho Agent", "Hồ sơ sản phẩm và chủ đề AI dựa vào để viết bài, bình luận, trả lời khách.",
      '<button class="btn" data-act="nhap-bo-nao">' + ic("spark") + 'Nhập từ bộ não MinMin</button><button class="btn" data-act="them" data-loai="chu_de">' + ic("plus") + 'Thêm chủ đề</button><button class="btn btn-pri" data-act="them" data-loai="san_pham">' + ic("plus") + "Thêm sản phẩm</button>") +
      '<div class="note mb">' + ic("info") + '<span>Agent tự đọc thêm <b>wiki, ghi chú và trí nhớ</b> trong bộ não MinMin khớp với từng sản phẩm và từng bài viết, nên bạn không phải nhập lại thứ đã có trong bộ não.</span></div>' +
      '<div id="kt-ds"><div class="kt-grid">' + '<div class="sk sk-card"></div>'.repeat(4) + "</div></div>";
    DS.bind(el, { "them": function (t) { taoMoi(t.getAttribute("data-loai")); }, "tai-lai": nap, "nhap-bo-nao": nhapBoNao });
    function the(k) {
      var tt = TT[k.trang_thai] || TT.dang_dung;
      return '<a class="kt" href="#/kien-thuc/' + encodeURIComponent(k.id) + '"><div class="row-sb" style="flex-wrap:nowrap;align-items:flex-start"><b style="font-size:14px">' + esc(k.ten) + "</b>" + DS.bd(tt[0], tt[1], true) + "</div>" +
        (k.mo_ta ? '<div class="small muted clamp2">' + esc(k.mo_ta) + "</div>" : "") +
        '<div class="row small muted" style="gap:12px;margin-top:auto">' + "<span>" + ic("file") + " " + (k.so_tai_lieu || 0) + " tài liệu</span><span>" + ic("chat") + " " + (k.so_hoi_dap || 0) +
        " hỏi đáp</span>" + (k.loai !== "chu_de" ? "<span>" + ic("users") + " " + (k.so_nhom || 0) + " nhóm</span>" : "") + "</div>" +
        (k.cho_ban ? '<div class="note note-warn" style="padding:7px 10px">' + ic("alert") + "<span><b>" + k.cho_ban + " câu khách hỏi</b> chờ bạn trả lời</span></div>" : "") + "</a>";
    }
    function nap() {
      return DS.layKienThuc(true).then(function (d) {
        if (!ctx.alive) return;
        var box = el.querySelector("#kt-ds");
        if (d.ok === false) { box.innerHTML = DS.loiThe(d.error, true); return; }
        var ds = DS.list(d, "kien_thuc"), sp = ds.filter(function (k) { return k.loai !== "chu_de"; }), cd = ds.filter(function (k) { return k.loai === "chu_de"; });
        var h = '<div class="grp-t">Sản phẩm (' + sp.length + ")</div>" + (sp.length ? '<div class="kt-grid">' + sp.map(the).join("") + "</div>" :
          '<div class="card">' + DS.rong("Chưa có sản phẩm", "Thêm sản phẩm kèm giá, mô tả, giọng văn. Agent dùng để viết bài, bình luận đúng nhu cầu và trả lời khách.", "book",
            '<button class="btn btn-pri" data-act="them" data-loai="san_pham">' + ic("plus") + "Thêm sản phẩm</button>") + "</div>");
        h += '<div class="grp-t">Chủ đề (chỉ tương tác) (' + cd.length + ")</div>" + (cd.length ? '<div class="kt-grid">' + cd.map(the).join("") + "</div>" :
          '<div class="card">' + DS.rong("Chưa có chủ đề", "Chủ đề giúp nick tương tác tự nhiên trong nhóm (không bán hàng), làm nick trông thật hơn.", "book") + "</div>");
        box.innerHTML = h;
      });
    }
    return nap();
  }

  function chiTiet(el, ctx, id) {
    var tab = ["tai-lieu", "hoi-dap", "nhom", "bo-nao"].indexOf(ctx.q.tab) >= 0 ? ctx.q.tab : "tai-lieu", K = null, suaQA = {}, kqBN = null;
    el.innerHTML = '<a class="back" href="#/kien-thuc">' + ic("back") + "Kiến thức cho Agent</a>" + DS.skel(8);
    function nap() {
      return DS.api("GET", "/doi-social/kien-thuc/" + encodeURIComponent(id)).then(function (d) {
        if (!ctx.alive) return;
        if (d.ok === false) { el.innerHTML = '<a class="back" href="#/kien-thuc">' + ic("back") + "Kiến thức cho Agent</a>" + DS.loiThe(d.error, true); return; }
        K = d.kien_thuc || d;
        ve();
      });
    }
    function ve() {
      var tl = K.tai_lieu || [], qa = K.hoi_dap || [], nh = K.nhom || [], cho = qa.filter(function (q) { return q.trang_thai === "cho_ban"; });
      var laSP = K.loai !== "chu_de";
      var h = '<a class="back" href="#/kien-thuc">' + ic("back") + "Kiến thức cho Agent</a>" + DS.ph(K.ten || "", (laSP ? "Sản phẩm" : "Chủ đề (chỉ tương tác)") + " · " + (TT[K.trang_thai] || TT.dang_dung)[0],
        '<button class="btn btn-dan" data-act="xoa">' + ic("trash") + "Xoá</button>");
      h += '<div class="grid g-12"><div class="card"><div class="card-h"><h3>Hồ sơ</h3></div>' +
        '<div class="fld"><label for="kt-ten">Tên</label><input class="inp" id="kt-ten" value="' + esc(K.ten) + '"></div>' +
        '<div class="fld"><label for="kt-mo_ta">Mô tả</label><textarea class="ta" id="kt-mo_ta" rows="4" placeholder="Sản phẩm là gì, cho ai, điểm nổi bật">' + esc(K.mo_ta || "") + "</textarea></div>" +
        (laSP ? '<div class="fgrid" style="margin-top:14px"><div class="fld"><label for="kt-gia">Giá</label><input class="inp" id="kt-gia" value="' + esc(K.gia || "") + '" placeholder="Ví dụ: 590.000đ, freeship từ 2 món"></div>' +
          '<div class="fld"><label for="kt-link">Link mua</label><input class="inp" id="kt-link" value="' + esc(K.link || "") + '" placeholder="https://..."></div></div>' : "") +
        '<div class="fld"><label for="kt-tu_khoa">Từ khoá</label><input class="inp" id="kt-tu_khoa" value="' + esc(K.tu_khoa || "") + '" placeholder="Cách nhau dấu phẩy; dùng để tìm nhóm và chấm bài đúng nhu cầu"></div>' +
        '<div class="fld"><label for="kt-giong_van">Giọng văn</label><input class="inp" id="kt-giong_van" value="' + esc(K.giong_van || "") + '" placeholder="Ví dụ: thân thiện, xưng em gọi chị, không dùng tiếng lóng"></div>' +
        '<div class="fld"><label for="kt-dan_rieng">Dặn riêng cho AI</label><textarea class="ta" id="kt-dan_rieng" rows="3" placeholder="Ví dụ: không nói giá công khai trong bình luận, mời khách nhắn tin">' + esc(K.dan_rieng || "") + "</textarea></div>" +
        '<div class="fld"><label>Trạng thái</label><div class="seg" id="kt-tt">' + Object.keys(TT).map(function (k) {
          return '<button type="button" data-v="' + k + '" class="' + ((K.trang_thai || "dang_dung") === k ? "on" : "") + '">' + TT[k][0] + "</button>";
        }).join("") + '</div><div class="hint">Chờ duyệt: AI chưa dùng hồ sơ này để viết hay trả lời.</div></div>' +
        '<div class="row mt" style="justify-content:flex-end"><button class="btn btn-pri" data-act="luu">Lưu hồ sơ</button></div></div>';

      h += '<div class="card"><div class="tabs" style="margin-top:-6px">' +
        '<a class="tab' + (tab === "tai-lieu" ? " on" : "") + '" href="#/kien-thuc/' + encodeURIComponent(id) + '?tab=tai-lieu">Tài liệu <span class="cnt">' + tl.length + "</span></a>" +
        '<a class="tab' + (tab === "hoi-dap" ? " on" : "") + '" href="#/kien-thuc/' + encodeURIComponent(id) + '?tab=hoi-dap">Hỏi đáp <span class="cnt"' + (cho.length ? ' style="background:var(--warn-soft);color:var(--warn)"' : "") + ">" + qa.length + "</span></a>" +
        '<a class="tab' + (tab === "bo-nao" ? " on" : "") + '" href="#/kien-thuc/' + encodeURIComponent(id) + '?tab=bo-nao">Bộ não MinMin <span class="cnt">' + (K.nguon_bo_nao || []).length + "</span></a>" +
        (laSP ? '<a class="tab' + (tab === "nhom" ? " on" : "") + '" href="#/kien-thuc/' + encodeURIComponent(id) + '?tab=nhom">Nhóm <span class="cnt">' + nh.length + "</span></a>" : "") + "</div>";
      if (tab === "bo-nao") {
        var gan = K.nguon_bo_nao || [];
        h += '<label class="row-sb" style="flex-wrap:nowrap;gap:12px;padding:4px 0 12px;cursor:pointer"><span><b>Tự tra bộ não theo ngữ cảnh</b><div class="tiny muted">Mỗi lần viết bài, bình luận hay trả lời khách, Agent tìm thêm ghi chú khớp trong wiki và bộ não MinMin.</div></span>' +
          '<span class="sw"><input type="checkbox" id="bn-tu" ' + (K.tu_tra_bo_nao !== false ? "checked" : "") + "><span></span></span></label>" +
          '<div class="sec-t">Ghi chú gắn cố định (' + gan.length + ")</div>" +
          (gan.length ? '<div class="stack">' + gan.map(function (p) {
            return '<div class="row-sb" data-path="' + esc(p) + '" style="flex-wrap:nowrap;padding:8px 0;border-bottom:1px solid var(--line2)"><div class="row" style="flex-wrap:nowrap;min-width:0">' + ic("file") + '<span class="clip">' + esc(p) + "</span></div>" +
              '<div class="row" style="flex-wrap:nowrap"><button class="btn btn-xs btn-ghost" data-act="xem-bn">' + ic("eye") + 'Xem</button><button class="btn btn-xs btn-ghost btn-dan" data-act="bo-bn" aria-label="Bỏ gắn">' + ic("x") + "</button></div></div>";
          }).join("") + "</div>" : '<div class="small muted">Chưa gắn ghi chú nào. Agent luôn đọc trọn ghi chú gắn cố định, hợp với bảng giá, chính sách.</div>') +
          '<div class="sep"></div><div class="sec-t">Tìm trong bộ não</div><div class="row" style="flex-wrap:nowrap"><input class="inp" id="bn-q2" value="' + esc(K.ten || "") + '"><button class="btn btn-soft" data-act="tim-bn">' + ic("search") + "Tìm</button></div>" +
          '<div id="bn-kq2" class="mt">' + (kqBN ? ketQuaBoNao(kqBN, '<div class="row" style="flex-wrap:nowrap"><button class="btn btn-xs btn-ghost" data-act="xem-bn">Xem</button><button class="btn btn-xs btn-pri" data-act="gan-bn">Gắn</button></div>') : "") + "</div>";
      } else if (tab === "hoi-dap") {
        var sx = cho.concat(qa.filter(function (q) { return q.trang_thai !== "cho_ban"; }));
        h += (cho.length ? '<div class="note note-warn mb">' + ic("alert") + "<span><b>" + cho.length + " câu khách hỏi</b> mà AI chưa có thông tin. Trả lời một lần, lần sau AI tự trả lời được.</span></div>" : "") +
          (sx.length ? sx.map(function (q) {
            var dangSua = q.trang_thai === "cho_ban" || suaQA[q.id];
            return '<div class="qa' + (q.trang_thai === "cho_ban" ? " wait" : "") + '" data-qa="' + q.id + '"><div class="row-sb" style="flex-wrap:nowrap;align-items:flex-start"><div class="q">' + esc(q.hoi) + "</div>" +
              '<button class="btn btn-xs btn-ghost btn-dan" data-act="xoa-qa" aria-label="Xoá">' + ic("trash") + "</button></div>" +
              (q.nguon || q.luc ? '<div class="tiny muted">' + esc(q.nguon ? ({ chu: "Bạn thêm", ai: "AI ghi lại khi khách hỏi" }[q.nguon] || "Từ " + q.nguon) : "") + (q.luc ? (q.nguon ? " · " : "") + DS.gio(q.luc) : "") + "</div>" : "") +
              (dangSua ? '<textarea class="ta" style="margin-top:8px" rows="2" placeholder="Câu trả lời của bạn">' + esc(q.dap || "") + '</textarea><div class="row mt-s" style="justify-content:flex-end">' +
                (suaQA[q.id] ? '<button class="btn btn-sm btn-ghost" data-act="huy-qa">Thôi</button>' : "") + '<button class="btn btn-sm btn-pri" data-act="tra-loi">Lưu trả lời</button></div>' :
                '<div class="a">' + esc(q.dap) + '</div><button class="linkbtn small" data-act="sua-qa">Sửa</button>') + "</div>";
          }).join("") : DS.rong("Chưa có hỏi đáp", "Thêm các câu khách hay hỏi (giá, size, giao hàng, đổi trả). AI trả lời đúng theo đây.", "chat")) +
          '<div class="sep"></div><div class="sec-t">Thêm câu hỏi</div><div class="fld"><input class="inp" id="qa-hoi" placeholder="Câu hỏi, ví dụ: Có ship COD không?"></div>' +
          '<div class="fld"><textarea class="ta" id="qa-dap" rows="2" placeholder="Câu trả lời"></textarea></div><div class="row mt-s" style="justify-content:flex-end"><button class="btn btn-soft" data-act="them-qa">' + ic("plus") + "Thêm hỏi đáp</button></div>";
      } else if (tab === "nhom" && laSP) {
        h += (nh.length ? '<div class="stack">' + nh.slice(0, 20).map(function (g) {
          return '<div class="row-sb" style="padding:8px 0;border-bottom:1px solid var(--line2)"><div class="grow" style="min-width:0"><div class="b clip">' + esc(g.ten || g.link) + '</div><div class="tiny muted clip">' + esc(g.link || "") + "</div></div>" +
            DS.bdMap({ cho_duyet: ["Chờ duyệt", "warn"], da_duyet: ["Đã duyệt", "ok"], den: ["Danh sách đen", "err"] }, g.trang_thai) + "</div>";
        }).join("") + "</div>" : DS.rong("Chưa có nhóm", "Nhóm Facebook của sản phẩm quản lý ở Kho group FB.", "list")) +
          '<div class="row mt" style="justify-content:flex-end"><a class="btn btn-soft" href="#/nhom-fb?sp=' + encodeURIComponent(id) + '">' + ic("users") + "Mở Kho group FB</a></div>";
      } else {
        h += (tl.length ? tl.map(function (t) {
          return '<div class="qa" data-tl="' + t.id + '"><div class="row-sb" style="flex-wrap:nowrap;align-items:flex-start"><div class="row" style="flex-wrap:nowrap;min-width:0">' + ic("file") + '<b class="clip">' + esc(t.ten || "Tài liệu") +
            '</b></div><button class="btn btn-xs btn-ghost btn-dan" data-act="xoa-tl" aria-label="Xoá">' + ic("trash") + '</button></div><div class="small muted clamp2" style="margin-top:4px">' + esc(t.noi_dung || "") + "</div></div>";
        }).join("") : DS.rong("Chưa có tài liệu", "Dán bảng giá, chính sách đổi trả, thông số, bài mẫu hay. AI đọc tất cả trước khi viết.", "box")) +
          '<div class="sep"></div><div class="sec-t">Thêm tài liệu</div><div class="fld"><input class="inp" id="tl-ten" placeholder="Tên tài liệu, ví dụ: Bảng size"></div>' +
          '<div class="fld"><textarea class="ta" id="tl-nd" rows="4" placeholder="Dán nội dung chữ ở đây"></textarea></div>' +
          '<div class="row-sb mt-s"><label class="btn btn-sm btn-ghost" style="cursor:pointer">' + ic("upload") + 'Tải tệp .txt / .md<input type="file" id="tl-tep" accept=".txt,.md,.markdown,text/plain,text/markdown" hidden></label>' +
          '<button class="btn btn-soft" data-act="them-tl">' + ic("plus") + "Thêm tài liệu</button></div>";
      }
      el.innerHTML = h + "</div></div>";
    }
    function luuHoSo() {
      var b = { ten: val("ten"), mo_ta: val("mo_ta"), tu_khoa: val("tu_khoa"), giong_van: val("giong_van"), dan_rieng: val("dan_rieng") };
      if (el.querySelector("#kt-gia")) { b.gia = val("gia"); b.link = val("link"); }
      var on = el.querySelector("#kt-tt .on"); if (on) b.trang_thai = on.getAttribute("data-v");
      if (!b.ten) { DS.toast("Tên không được trống", "err"); return; }
      DS.api("PUT", "/doi-social/kien-thuc/" + encodeURIComponent(id), b).then(function (d) {
        if (d.ok === false) return;
        DS.boNho("kt"); Object.assign(K, b); DS.toast("Đã lưu hồ sơ", "ok");
        el.querySelector(".ph h1").textContent = b.ten;
      });
    }
    function val(k) { var e = el.querySelector("#kt-" + k); return e ? e.value.trim() : ""; }
    function qaOf(t) { var c = t.closest("[data-qa]"); var qid = c && c.getAttribute("data-qa"); return (K.hoi_dap || []).filter(function (q) { return String(q.id) === String(qid); })[0]; }
    el.addEventListener("click", function (e) {
      var b = e.target.closest("#kt-tt button"); if (!b) return;
      Array.prototype.forEach.call(b.parentNode.children, function (x) { x.classList.toggle("on", x === b); });
    });
    el.addEventListener("change", function (e) {
      if (e.target.id !== "tl-tep") return;
      var f = e.target.files && e.target.files[0]; if (!f) return;
      var fd = new FormData(); fd.append("tep", f, f.name); fd.append("ten", f.name);
      DS.api("POST", "/doi-social/kien-thuc/" + encodeURIComponent(id) + "/tai-lieu", fd).then(function (d) { if (d.ok !== false) { DS.toast("Đã thêm " + f.name, "ok"); DS.boNho("kt"); nap(); } });
    });
    function luuBoNao(b, loi) {
      return DS.api("PUT", "/doi-social/kien-thuc/" + encodeURIComponent(id), b).then(function (d) {
        if (d.ok === false) return;
        K = Object.assign(K, (d.kien_thuc || {})); if (b.nguon_bo_nao) K.nguon_bo_nao = b.nguon_bo_nao;
        DS.boNho("kt"); DS.toast(loi, "ok"); ve();
      });
    }
    function timBN() {
      var q = (el.querySelector("#bn-q2") || {}).value || K.ten || "";
      var box = el.querySelector("#bn-kq2"); if (box) box.innerHTML = DS.skel(3);
      DS.api("GET", "/doi-social/bo-nao/tim?q=" + encodeURIComponent(q.trim())).then(function (d) {
        if (d.ok === false) return;
        kqBN = (d.muc || []).filter(function (x) { return (K.nguon_bo_nao || []).indexOf(x.path) < 0; });
        ve();
      });
    }
    el.addEventListener("change", function (e) {
      if (e.target.id !== "bn-tu") return;
      luuBoNao({ tu_tra_bo_nao: e.target.checked }, e.target.checked ? "Agent sẽ tự tra bộ não" : "Đã tắt tự tra bộ não");
    });
    el.addEventListener("keydown", function (e) { if (e.target.id === "bn-q2" && e.key === "Enter") timBN(); });
    DS.bind(el, {
      "tim-bn": timBN,
      "gan-bn": function (t) {
        var p = t.closest("[data-path]").getAttribute("data-path");
        kqBN = (kqBN || []).filter(function (x) { return x.path !== p; });
        luuBoNao({ nguon_bo_nao: (K.nguon_bo_nao || []).concat([p]) }, "Đã gắn ghi chú vào hồ sơ");
      },
      "bo-bn": function (t) {
        var p = t.closest("[data-path]").getAttribute("data-path");
        luuBoNao({ nguon_bo_nao: (K.nguon_bo_nao || []).filter(function (x) { return x !== p; }) }, "Đã bỏ gắn");
      },
      "xem-bn": function (t) {
        var p = t.closest("[data-path]").getAttribute("data-path");
        DS.api("GET", "/doi-social/bo-nao/tep?path=" + encodeURIComponent(p)).then(function (d) {
          if (d.ok === false) return;
          DS.modal({ title: d.tep.ten, body: '<div class="tiny muted mb">' + esc(d.tep.path) + '</div><pre style="white-space:pre-wrap;max-height:60vh;overflow:auto;font:inherit;font-size:13px">' + esc(d.tep.noi_dung) + "</pre>",
            foot: '<button class="btn" data-x>Đóng</button>' });
        });
      },
      "tai-lai": nap,
      "luu": luuHoSo,
      "xoa": function () {
        DS.xacNhan('Xoá "' + K.ten + '" cùng tài liệu và hỏi đáp? Mẫu đang dùng mục này sẽ không còn hồ sơ để viết.', "Xoá", true).then(function (ok) {
          if (ok) DS.api("DELETE", "/doi-social/kien-thuc/" + encodeURIComponent(id)).then(function (d) { if (d.ok !== false) { DS.boNho("kt"); DS.toast("Đã xoá", "ok"); DS.go("kien-thuc"); } });
        });
      },
      "them-tl": function () {
        var ten = el.querySelector("#tl-ten").value.trim(), nd = el.querySelector("#tl-nd").value.trim();
        if (!nd) { DS.toast("Dán nội dung tài liệu", "err"); return; }
        DS.api("POST", "/doi-social/kien-thuc/" + encodeURIComponent(id) + "/tai-lieu", { ten: ten || nd.slice(0, 40), noi_dung: nd }).then(function (d) { if (d.ok !== false) { DS.toast("Đã thêm tài liệu", "ok"); DS.boNho("kt"); nap(); } });
      },
      "xoa-tl": function (t) {
        var tid = t.closest("[data-tl]").getAttribute("data-tl");
        DS.xacNhan("Xoá tài liệu này?", "Xoá", true).then(function (ok) { if (ok) DS.api("DELETE", "/doi-social/tai-lieu/" + tid).then(function (d) { if (d.ok !== false) { DS.boNho("kt"); nap(); } }); });
      },
      "them-qa": function () {
        var hoi = el.querySelector("#qa-hoi").value.trim(), dap = el.querySelector("#qa-dap").value.trim();
        if (!hoi) { DS.toast("Nhập câu hỏi", "err"); return; }
        DS.api("POST", "/doi-social/kien-thuc/" + encodeURIComponent(id) + "/hoi-dap", { hoi: hoi, dap: dap }).then(function (d) { if (d.ok !== false) { DS.toast("Đã thêm hỏi đáp", "ok"); DS.boNho("kt"); nap(); } });
      },
      "tra-loi": function (t) {
        var q = qaOf(t), dap = t.closest("[data-qa]").querySelector("textarea").value.trim();
        if (!dap) { DS.toast("Nhập câu trả lời", "err"); return; }
        DS.api("PUT", "/doi-social/hoi-dap/" + q.id, { dap: dap }).then(function (d) { if (d.ok !== false) { delete suaQA[q.id]; DS.toast("Đã lưu, AI sẽ dùng câu này", "ok"); DS.boNho("kt"); nap(); } });
      },
      "sua-qa": function (t) { suaQA[qaOf(t).id] = 1; ve(); },
      "huy-qa": function (t) { delete suaQA[qaOf(t).id]; ve(); },
      "xoa-qa": function (t) {
        var q = qaOf(t);
        DS.xacNhan("Xoá câu hỏi này?", "Xoá", true).then(function (ok) { if (ok) DS.api("DELETE", "/doi-social/hoi-dap/" + q.id).then(function (d) { if (d.ok !== false) { DS.boNho("kt"); nap(); } }); });
      }
    });
    return nap();
  }

  DS.view("kien-thuc", {
    title: "Kiến thức cho Agent",
    render: function (el, ctx) { return ctx.arg ? chiTiet(el, ctx, ctx.arg) : danhSach(el, ctx); }
  });
})();
