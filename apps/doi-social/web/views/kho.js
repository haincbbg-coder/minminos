/* Kho nội dung - #/kho (tab Kho bài · Viết bài AI) */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;
  var TT_KHO = { cho: ["Chờ đăng", "info"], dang_giu: ["Đang đăng", "brand"], da_dang: ["Đã đăng", "ok"], loi: ["Lỗi", "err"] };
  var CO_TIEU_DE = { youtube: 1, reddit: 1 };

  function tachBai(s) {
    return String(s || "").split(/\n\s*===\s*\n|^\s*===\s*$/m).map(function (x) { return x.trim(); }).filter(Boolean);
  }

  function themBai(nt, nickId, nickTen, xong) {
    var m = DS.modal({
      title: "Thêm bài vào kho " + DS.tenNT(nt),
      body: '<div class="row mb">' + DS.icNT(nt, 24) + '<span class="small">Vào: <b>' + esc(nickId ? "kho riêng của " + nickTen : "kho dùng chung") + "</b></span></div>" +
        (CO_TIEU_DE[nt] ? '<div class="fld"><label for="kb-td">Tiêu đề' + (nt === "youtube" ? " (tối đa 100 ký tự)" : " (tối đa 300 ký tự)") + '</label><input class="inp" id="kb-td" maxlength="' + (nt === "youtube" ? 100 : 300) + '"></div>' : "") +
        '<div class="fld"><label for="kb-nd">Nội dung</label><textarea class="ta" id="kb-nd" rows="7" placeholder="Viết hoặc dán nội dung bài.&#10;&#10;Dán nhiều bài một lần: tách các bài bằng một dòng chỉ có ===' +
        (nt === "threads" ? "&#10;Threads: dòng --- tách một bài thành chuỗi." : "") + '"></textarea><div class="hint" id="kb-dem">1 bài</div></div>' +
        '<div class="fld"><label>Ảnh / video</label><label class="drop">' + ic("upload") + ' <span id="kb-tep-t">Bấm để chọn ảnh hoặc video (chọn được nhiều tệp)</span><input type="file" id="kb-tep" multiple accept="image/*,video/*"></label>' +
        '<div class="hint">Khi dán nhiều bài, tệp đính kèm đi theo bài đầu tiên.' + (nt === "instagram" ? " Instagram không nhận ảnh webp." : "") + "</div></div>",
      foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="kb-luu">' + ic("plus") + "Thêm vào kho</button>"
    });
    var b = m.body;
    b.querySelector("#kb-nd").addEventListener("input", function () {
      var n = tachBai(this.value).length;
      b.querySelector("#kb-dem").textContent = (n || 1) + " bài" + (n > 1 ? ", tách theo dòng ===" : "");
    });
    b.querySelector("#kb-tep").addEventListener("change", function () {
      var f = this.files || [];
      b.querySelector("#kb-tep-t").textContent = f.length ? f.length + " tệp: " + Array.prototype.map.call(f, function (x) { return x.name; }).slice(0, 3).join(", ") + (f.length > 3 ? "..." : "") : "Bấm để chọn ảnh hoặc video";
    });
    m.foot.querySelector("#kb-luu").onclick = function () {
      var nd = b.querySelector("#kb-nd").value, tep = b.querySelector("#kb-tep").files || [];
      if (!nd.trim() && !tep.length) { DS.toast("Nhập nội dung hoặc chọn tệp", "err"); return; }
      var fd = new FormData();
      fd.append("nen_tang", nt);
      fd.append("nick", nickId || "");
      fd.append("tieu_de", b.querySelector("#kb-td") ? b.querySelector("#kb-td").value : "");
      fd.append("noi_dung", nd);
      Array.prototype.forEach.call(tep, function (f) { fd.append("tep", f, f.name); });
      var btn = this;
      btn.disabled = true; btn.textContent = "Đang tải lên...";
      DS.api("POST", "/doi-social/kho", fd).then(function (d) {
        btn.disabled = false; btn.textContent = "Thêm vào kho";
        if (d.ok === false) return;
        var n = d.so || (d.ids || []).length || tachBai(nd).length || 1;
        DS.toast("Đã thêm " + n + " bài vào kho", "ok"); m.close(); xong();
      });
    };
  }

  function xemMuc(nt, nickId, nickTen, sauDoi) {
    var F = { trang_thai: "", trang: 1 };
    var m = DS.modal({ title: "Bài trong kho " + DS.tenNT(nt) + (nickId ? " · " + nickTen : " · dùng chung"), wide: true, body: "" });
    m.body.innerHTML = '<div class="chips mb" id="km-loc">' + [["", "Tất cả"], ["cho", "Chờ đăng"], ["da_dang", "Đã đăng"], ["loi", "Lỗi"], ["dang_giu", "Đang đăng"]].map(function (x) {
      return '<button class="chip' + (x[0] === "" ? " on" : "") + '" data-v="' + x[0] + '">' + x[1] + "</button>";
    }).join("") + '</div><div id="km-ds"></div>';
    function nap() {
      var box = m.body.querySelector("#km-ds");
      box.innerHTML = DS.skel(4);
      DS.api("GET", "/doi-social/kho/muc" + DS.qs({ nen_tang: nt, nick: nickId || "", trang_thai: F.trang_thai, trang: F.trang, moi_trang: 20 })).then(function (d) {
        if (d.ok === false) { box.innerHTML = DS.rong("Chưa tải được", esc(d.error), "box"); return; }
        var ds = DS.list(d, "bai"), tong = d.tong != null ? d.tong : ds.length;
        if (!ds.length) { box.innerHTML = DS.rong("Không có bài nào", "Bấm Thêm bài để đưa bài vào kho.", "box"); return; }
        box.innerHTML = '<div class="tw" style="border:1px solid var(--line);border-radius:12px"><table class="tbl"><thead><tr><th>Bài</th><th>Trạng thái</th><th>Thời gian</th><th></th></tr></thead><tbody>' +
          ds.map(function (x) {
            var tep = x.tep || [];
            return '<tr><td style="min-width:260px"><div class="row" style="flex-wrap:nowrap;align-items:flex-start">' + (tep.length ? '<div class="thumbs">' + tep.slice(0, 2).map(function (t) {
              var url = "/doi-social/kho/tep/" + encodeURIComponent(x.id) + "/" + encodeURIComponent(t.luu);
              return /\.(mp4|mov|m4v|webm)$/i.test(t.ten || t.luu) ? '<a class="vid" href="' + url + '" target="_blank" rel="noopener">' + ic("video") + "</a>" :
                '<a href="' + url + '" target="_blank" rel="noopener"><img loading="lazy" src="' + url + '" alt="' + esc(t.ten) + '"></a>';
            }).join("") + "</div>" : "") + '<div class="grow" style="min-width:0">' + (x.tieu_de ? '<div class="b clip">' + esc(x.tieu_de) + "</div>" : "") +
              '<div class="small clamp2">' + esc(x.noi_dung || "(chỉ có tệp)") + "</div>" + (tep.length > 2 ? '<div class="tiny muted">+' + (tep.length - 2) + " tệp</div>" : "") +
              (x.loi ? '<div class="tiny" style="color:var(--err)">' + esc(x.loi) + "</div>" : "") + "</div></div></td><td>" + DS.bdMap(TT_KHO, x.trang_thai) + '</td><td class="small nw">' +
              (x.luc_dang ? "Đăng " + DS.gio(x.luc_dang) : "Thêm " + DS.gio(x.luc_tao)) + (x.link ? '<div><a href="' + esc(x.link) + '" target="_blank" rel="noopener">Mở bài</a></div>' : "") +
              '</td><td class="nw">' + (x.trang_thai === "loi" || x.trang_thai === "dang_giu" ? '<button class="btn btn-xs" data-tra="' + x.id + '">' + ic("refresh") + "Trả lại hàng chờ</button> " : "") +
              '<button class="btn btn-xs btn-dan" data-xoa="' + x.id + '" aria-label="Xoá">' + ic("trash") + "</button></td></tr>";
          }).join("") + "</tbody></table></div>" + DS.phanTrang(tong, d.trang || F.trang, d.moi_trang || 20);
      });
    }
    m.body.addEventListener("click", function (e) {
      var c = e.target.closest("#km-loc .chip");
      if (c) { F.trang_thai = c.getAttribute("data-v"); F.trang = 1; Array.prototype.forEach.call(m.body.querySelectorAll("#km-loc .chip"), function (z) { z.classList.toggle("on", z === c); }); nap(); return; }
      var p = e.target.closest("[data-act=trang]");
      if (p) { F.trang = +p.getAttribute("data-trang") || 1; nap(); return; }
      var x = e.target.closest("[data-xoa]");
      if (x) {
        DS.xacNhan("Xoá bài này khỏi kho? Tệp đính kèm cũng bị xoá.", "Xoá", true).then(function (ok) {
          if (ok) DS.api("DELETE", "/doi-social/kho/" + x.getAttribute("data-xoa")).then(function (d) { if (d.ok !== false) { DS.toast("Đã xoá", "ok"); nap(); sauDoi(); } });
        });
        return;
      }
      var t = e.target.closest("[data-tra]");
      if (t) DS.api("POST", "/doi-social/kho/" + t.getAttribute("data-tra") + "/tra-lai", {}).then(function (d) { if (d.ok !== false) { DS.toast("Đã trả bài về hàng chờ", "ok"); nap(); sauDoi(); } });
    });
    nap();
  }

  function tabKho(el, ctx) {
    var nt = DS.NT_THU_TU.indexOf(ctx.q.nt) >= 0 ? ctx.q.nt : "facebook";
    var body = el.querySelector("#kho-body");
    body.innerHTML = '<div class="pills mb">' + DS.NT_THU_TU.map(function (id) {
      return '<a class="pill' + (id === nt ? " on" : "") + '" href="#/kho?tab=kho&nt=' + id + '">' + DS.icNT(id, 20) + esc(DS.tenNT(id)) + "</a>";
    }).join("") + '</div><div id="kho-nd">' + DS.skel(5) + "</div>";
    var tenNick = {};
    function nap() {
      return DS.api("GET", "/doi-social/kho" + DS.qs({ nen_tang: nt })).then(function (d) {
        if (!ctx.alive) return;
        var box = body.querySelector("#kho-nd");
        if (d.ok === false) { box.innerHTML = DS.loiThe(d.error, true); return; }
        var c = d.chung || {}, ds = d.theo_nick || [];
        ds.forEach(function (r) { tenNick[r.nick_id] = r.nick_ten; });
        var h = '<div class="card"><div class="row-sb"><div class="row" style="gap:12px">' + DS.icNT(nt, 40) + '<div><div class="b" style="font-size:15px">Kho dùng chung · ' + esc(DS.tenNT(nt)) +
          '</div><div class="small muted">Mỗi bài chỉ đăng một lần, nick nào rảnh lấy bài kế tiếp. Lưu trên máy chủ MinMin, tải lên được từ điện thoại.</div></div></div>' +
          '<div class="row"><button class="btn btn-sm" data-act="xem" data-nick="">' + ic("eye") + 'Xem bài</button><button class="btn btn-sm btn-pri" data-act="them" data-nick="">' + ic("plus") + "Thêm bài</button></div></div>" +
          '<div class="mini mt"><div><b>' + DS.so(c.con || 0) + '</b><span>Còn chờ đăng</span></div><div><b style="color:var(--ok)">' + DS.so(c.da_dang || 0) + '</b><span>Đã đăng</span></div><div><b style="color:' +
          (c.loi ? "var(--err)" : "inherit") + '">' + DS.so(c.loi || 0) + "</b><span>Lỗi</span></div></div>" +
          (!c.con ? '<div class="note note-warn mt">' + ic("alert") + "<span>Kho dùng chung đang hết bài. Mẫu đăng từ kho sẽ báo <b>Hết bài</b> (vàng) cho tới khi bạn thêm bài.</span></div>" : "") + "</div>";
        h += '<div class="card card-x"><div class="card-h"><h3>Kho riêng theo nick</h3><span class="small muted">Dùng khi mẫu chọn "Kho riêng của từng nick"</span></div>';
        if (!ds.length) h += DS.rong("Chưa có kho riêng", "Thêm bài cho một nick cụ thể bằng nút bên dưới.", "box", '<button class="btn btn-sm" data-act="chon-nick">' + ic("plus") + "Thêm bài cho một nick</button>");
        else h += '<div class="tw"><table class="tbl"><thead><tr><th>Nick</th><th class="num">Còn</th><th class="num">Đã đăng</th><th class="num">Lỗi</th><th></th></tr></thead><tbody>' + ds.map(function (r) {
          return '<tr><td><div class="row" style="flex-wrap:nowrap">' + DS.av(r.nick_ten) + "<b>" + esc(r.nick_ten) + '</b></div></td><td class="num">' + (r.con ? DS.so(r.con) : '<span class="bd bd-warn">Hết bài</span>') +
            '</td><td class="num">' + DS.so(r.da_dang || 0) + '</td><td class="num" style="' + (r.loi ? "color:var(--err)" : "") + '">' + DS.so(r.loi || 0) +
            '</td><td class="nw" style="text-align:right"><button class="btn btn-xs" data-act="xem" data-nick="' + esc(r.nick_id) + '">' + ic("eye") + 'Xem</button> <button class="btn btn-xs btn-soft" data-act="them" data-nick="' +
            esc(r.nick_id) + '">' + ic("plus") + "Thêm bài</button></td></tr>";
        }).join("") + '</tbody></table></div><div class="tfoot"><span></span><button class="btn btn-sm" data-act="chon-nick">' + ic("plus") + "Thêm bài cho nick khác</button></div>";
        box.innerHTML = h + "</div>";
      });
    }
    DS.bind(body, {
      "tai-lai": nap,
      "them": function (t) { var id = t.getAttribute("data-nick"); themBai(nt, id, tenNick[id], nap); },
      "xem": function (t) { var id = t.getAttribute("data-nick"); xemMuc(nt, id, tenNick[id], nap); },
      "chon-nick": function () {
        DS.layNick().then(function (d) {
          var ds = DS.list(d, "nick");
          var m = DS.modal({ title: "Chọn nick", body: '<div class="fld"><label>Nick</label><select class="sel" id="cn-s">' + ds.map(function (n) {
            return '<option value="' + esc(n.id) + '">' + esc(n.ten) + ((n.nhan || []).indexOf(nt) >= 0 ? " · " + DS.tenNT(nt) : "") + "</option>"; }).join("") + "</select></div>",
            foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="cn-ok">Tiếp</button>' });
          m.foot.querySelector("#cn-ok").onclick = function () {
            var s = m.body.querySelector("#cn-s"), id = s.value, ten = s.options[s.selectedIndex] ? s.options[s.selectedIndex].text.split(" · ")[0] : "";
            m.close(); if (id) themBai(nt, id, ten, nap);
          };
        });
      }
    });
    return nap();
  }

  function tabViet(el, ctx) {
    var body = el.querySelector("#kho-body");
    body.innerHTML = DS.skel(6);
    return Promise.all([DS.layKienThuc(true), DS.layNick()]).then(function (a) {
      if (!ctx.alive) return;
      var kt = DS.list(a[0], "kien_thuc").filter(function (x) { return (x.loai || "san_pham") === "san_pham"; }), nick = DS.list(a[1], "nick");
      if (!kt.length) {
        body.innerHTML = '<div class="card">' + DS.rong("Chưa có sản phẩm nào", "AI viết bài dựa trên hồ sơ sản phẩm (mô tả, giá, giọng văn). Thêm một sản phẩm trước.", "book",
          '<a class="btn btn-pri" href="#/kien-thuc">' + ic("plus") + "Thêm sản phẩm</a>") + "</div>";
        return;
      }
      var spDau = ctx.q.sp || kt[0].id;
      body.innerHTML = '<div class="grid g-21"><div class="card"><div class="card-h"><h3>' + ic("spark") + 'Viết bài bằng AI</h3></div>' +
        '<div class="fgrid"><div class="fld"><label for="vb-sp">Sản phẩm <span class="req">*</span></label><select class="sel" id="vb-sp">' + kt.map(function (x) {
          return '<option value="' + esc(x.id) + '"' + (String(x.id) === String(spDau) ? " selected" : "") + ">" + esc(x.ten) + (x.trang_thai === "cho_duyet" ? " (chờ duyệt)" : "") + "</option>";
        }).join("") + '</select></div><div class="fld"><label for="vb-noi">Nơi đăng <span class="req">*</span></label><select class="sel" id="vb-noi">' + Object.keys(DS.NOI_DANG).map(function (k) {
          return '<option value="' + k + '">' + esc(DS.NOI_DANG[k]) + "</option>";
        }).join("") + "</select></div>" +
        '<div class="fld"><label for="vb-nick">Nick đăng (tuỳ chọn)</label><select class="sel" id="vb-nick"><option value="">Chưa gán, nick nào rảnh thì đăng</option>' + nick.map(function (n) {
          return '<option value="' + esc(n.id) + '">' + esc(n.ten) + "</option>";
        }).join("") + '</select></div><div class="fld"><label for="vb-so">Số bản</label><div class="seg" id="vb-so">' + [1, 2, 3, 4, 5].map(function (n) {
          return '<button type="button" data-v="' + n + '" class="' + (n === 3 ? "on" : "") + '">' + n + "</button>";
        }).join("") + "</div></div></div>" +
        '<div class="fld" id="vb-nhom-f"><label for="vb-nhom">Nhóm Facebook (tuỳ chọn)</label><input class="inp" id="vb-nhom" placeholder="Link hoặc tên nhóm; để trống thì đăng vào nhóm của sản phẩm trong Kho group FB"></div>' +
        '<div class="fld"><label for="vb-yc">Yêu cầu thêm cho AI</label><textarea class="ta" id="vb-yc" rows="4" placeholder="Ví dụ: giọng kể chuyện, nhắc ưu đãi cuối tuần, không quá 120 chữ, có câu hỏi cuối bài"></textarea></div>' +
        '<div class="row-sb mt"><span class="small muted">Bài AI viết đi vào Duyệt nội dung, chưa đăng gì cho tới khi bạn duyệt.</span><button class="btn btn-pri btn-lg" data-act="viet">' + ic("spark") +
        'Viết bài</button></div><div id="vb-kq"></div></div>' +
        '<div class="card"><div class="card-h"><h3>Cách hoạt động</h3></div><ol class="steps" style="margin:0">' +
        "<li><div><b>AI đọc hồ sơ sản phẩm</b><div class=\"small muted\">Mô tả, giá, tài liệu, hỏi đáp, giọng văn và lời dặn riêng ở Kiến thức cho Agent.</div></div></li>" +
        "<li><div><b>Viết nhiều bản khác nhau</b><div class=\"small muted\">Mỗi bản một góc kể, hợp với nơi đăng (độ dài, cách dùng hashtag).</div></div></li>" +
        "<li><div><b>Bạn duyệt</b><div class=\"small muted\">Sửa tại chỗ, bỏ bản không ưng, hoặc nhờ AI viết lại.</div></div></li>" +
        "<li><div><b>Máy ở nhà đăng</b><div class=\"small muted\">Bài đã duyệt được mẫu \"Đăng bài AI đã duyệt\" lấy ra đăng đúng nick, đúng nhóm.</div></div></li></ol></div></div>";
      var so = 3;
      function capNhom() { body.querySelector("#vb-nhom-f").hidden = body.querySelector("#vb-noi").value !== "fb_nhom"; }
      capNhom();
      body.querySelector("#vb-noi").addEventListener("change", capNhom);
      body.querySelector("#vb-so").addEventListener("click", function (e) {
        var b = e.target.closest("button"); if (!b) return; so = +b.getAttribute("data-v");
        Array.prototype.forEach.call(this.children, function (x) { x.classList.toggle("on", x === b); });
      });
      DS.bind(body, {
        "viet": function (b) {
          var noi = body.querySelector("#vb-noi").value;
          var req = { san_pham_id: body.querySelector("#vb-sp").value, noi_dang: noi, so_ban: so, yeu_cau: body.querySelector("#vb-yc").value.trim() };
          var nk = body.querySelector("#vb-nick").value; if (nk) req.nick_id = nk;
          var nh = body.querySelector("#vb-nhom").value.trim(); if (nh && noi === "fb_nhom") req.nhom = nh;
          b.disabled = true; b.innerHTML = '<span class="typing"><span></span><span></span><span></span></span> AI đang viết...';
          body.querySelector("#vb-kq").innerHTML = "";
          DS.api("POST", "/doi-social/viet-bai", req).then(function (d) {
            b.disabled = false; b.innerHTML = ic("spark") + "Viết bài";
            if (d.ok === false) return;
            var n = (d.muc || []).length || so;
            body.querySelector("#vb-kq").innerHTML = '<div class="note note-ok mt">' + ic("ok") + '<div class="grow">Đã gửi <b>' + n + " bản nháp</b> sang Duyệt nội dung." +
              '</div><a class="btn btn-sm btn-ok" href="#/duyet">Đi tới Duyệt nội dung</a></div>';
            DS.capNhatHuyHieu();
          });
        }
      });
    });
  }

  DS.view("kho", {
    title: "Kho nội dung",
    render: function (el, ctx) {
      var tab = ctx.q.tab === "viet" ? "viet" : "kho";
      el.innerHTML = DS.ph("Kho nội dung", "Bài soạn sẵn để máy ở nhà đăng dần, và bài AI viết từ hồ sơ sản phẩm.") +
        DS.tabs([{ id: "kho", ten: "Kho bài" }, { id: "viet", ten: "Viết bài AI" }], tab, "#/kho?tab=") + '<div id="kho-body" class="stack"></div>';
      return tab === "viet" ? tabViet(el, ctx) : tabKho(el, ctx);
    }
  });
})();
