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

  // ================================================================ Viết bài AI (26.10.200)
  // Rõ ba câu hỏi: đăng ở đâu (Fanpage qua API, hay nick ở máy nhà + đúng Trang/nhóm/tài khoản),
  // bao nhiêu bài, khi nào đăng. Bên phải là kế hoạch đăng xem trước, cập nhật theo từng lựa chọn.
  var CACH_PHUT = [[0, "cùng lúc"], [15, "15 phút"], [30, "30 phút"], [60, "1 giờ"], [120, "2 giờ"], [180, "3 giờ"], [360, "6 giờ"], [720, "12 giờ"], [1440, "1 ngày"]];
  var NOI_NICK = ["fb_trang", "fb_nhom", "fb_tuong", "tiktok", "youtube", "instagram", "threads", "x", "reddit"];
  var NT_TK = { instagram: "instagram", tiktok: "tiktok", threads: "threads", youtube: "youtube" };

  function tabViet(el, ctx) {
    var body = el.querySelector("#kho-body");
    body.innerHTML = DS.skel(6);
    var FP = DS.fp;              // phần dùng chung của Fanpage (views/fp-chung.js)
    var layTrangFp = (FP && FP.layTrang) ? FP.layTrang().catch(function () { return {}; }) : Promise.resolve({});
    return Promise.all([DS.layKienThuc(true), DS.layNick(), layTrangFp]).then(function (a) {
      if (!ctx.alive) return;
      var kt = DS.list(a[0], "kien_thuc").filter(function (x) { return (x.loai || "san_pham") === "san_pham"; }), nick = DS.list(a[1], "nick");
      var trangFp = DS.list(a[2]).filter(function (t) { return t.bat !== 0 && t.bat !== false; });
      if (!kt.length) {
        body.innerHTML = '<div class="card">' + DS.rong("Chưa có sản phẩm nào", "AI viết bài dựa trên hồ sơ sản phẩm (mô tả, giá, giọng văn). Thêm một sản phẩm trước.", "book",
          '<a class="btn btn-pri" href="#/kien-thuc">' + ic("plus") + "Thêm sản phẩm</a>") + "</div>";
        return;
      }
      var S = {
        sp: String(ctx.q.sp || kt[0].id),
        che_do: ctx.q.che_do === "nick" || ctx.q.che_do === "api" ? ctx.q.che_do : (trangFp.length ? "api" : "nick"),
        noi: NOI_NICK.indexOf(ctx.q.noi) >= 0 ? ctx.q.noi : "fb_trang", nick: "", dich: "", dich_ten: "",
        so: 1, lich: "duyet", bat_dau: null, cach: 60, anh: [], kieu_anh: "mot_anh", nhomFb: null
      };
      var boChon = null, henXem = null, lanXem = 0;

      function seg(id, ds, v) {
        return '<div class="seg" id="' + id + '">' + ds.map(function (x) {
          return '<button type="button" data-v="' + esc(x[0]) + '" class="' + (String(x[0]) === String(v) ? "on" : "") + '">' + esc(x[1]) + "</button>";
        }).join("") + "</div>";
      }
      function buoc(so, tieuDe, noi) {
        return '<div class="vb-buoc"><div class="vb-so">' + so + '</div><div class="grow" style="min-width:0"><div class="vb-td">' + tieuDe + "</div>" + noi + "</div></div>";
      }

      body.innerHTML = '<div class="grid g-21 vb"><div class="card"><div class="card-h"><h3>' + ic("spark") + 'Viết bài bằng AI</h3></div>' +
        buoc(1, "Viết về sản phẩm nào", '<div class="row" style="flex-wrap:nowrap"><select class="sel grow" id="vb-sp">' + kt.map(function (x) {
          return '<option value="' + esc(x.id) + '"' + (String(x.id) === S.sp ? " selected" : "") + ">" + esc(x.ten) + (x.trang_thai === "cho_duyet" ? " (chờ duyệt)" : "") + "</option>";
        }).join("") + '</select><a class="btn btn-ghost btn-sm" href="#/kien-thuc">Sửa hồ sơ</a></div><div class="hint">AI đọc mô tả, giá, tài liệu, giọng văn và lời dặn của sản phẩm này ở Kiến thức cho Agent.</div>') +
        buoc(2, "Đăng ở đâu", seg("vb-cd", [["api", "Fanpage (máy chủ đăng)"], ["nick", "Nick ở máy nhà"]], S.che_do) +
          '<div class="hint" id="vb-cd-g"></div><div id="vb-dich" class="mt-s"></div>') +
        buoc(3, '<span id="vb-so-td">Số bài</span>', seg("vb-so", [[1, "1"], [2, "2"], [3, "3"], [4, "4"], [5, "5"]], S.so) + '<div class="hint" id="vb-so-g"></div>') +
        buoc(4, "Ảnh / video kèm <span class=\"muted\" style=\"font-weight:400\" id=\"vb-anh-bb\">(tuỳ chọn)</span>", '<div class="row"><label class="btn btn-sm">' + ic("upload") +
          'Chọn ảnh / video<input type="file" id="vb-anh" accept="image/*,video/*" multiple hidden></label><span class="small muted" id="vb-anh-tt">Không kèm ảnh thì đăng bài chữ.</span></div>' +
          '<div id="vb-anh-ds" class="mt-s"></div><div id="vb-anh-kieu" class="mt-s" hidden>' + seg("vb-ka", [["mot_anh", "Mỗi bài 1 ảnh (xoay vòng)"], ["album", "Mỗi bài cả bộ ảnh"]], S.kieu_anh) + "</div>") +
        buoc(5, "Khi nào đăng", '<div id="vb-lich-seg"></div><div class="hint" id="vb-lich-g"></div>' +
          '<div class="fgrid mt-s" id="vb-gio" hidden><div class="fld"><label for="vb-bd">Bài đầu tiên lúc</label><input class="inp" type="datetime-local" id="vb-bd"></div>' +
          '<div class="fld"><label for="vb-cach">Các bài cách nhau</label><select class="sel" id="vb-cach">' + CACH_PHUT.map(function (x) {
            return '<option value="' + x[0] + '"' + (x[0] === S.cach ? " selected" : "") + ">" + x[1] + "</option>";
          }).join("") + "</select></div></div>") +
        buoc(6, "Dặn thêm AI <span class=\"muted\" style=\"font-weight:400\">(tuỳ chọn)</span>", '<textarea class="ta" id="vb-yc" rows="3" placeholder="Ví dụ: giọng kể chuyện, nhắc ưu đãi cuối tuần, không quá 120 chữ, có câu hỏi cuối bài"></textarea>') +
        '<div class="vb-chot"><div class="grow small" id="vb-tom"></div><button class="btn btn-pri btn-lg" data-act="viet">' + ic("spark") + '<span id="vb-nut">Viết bài</span></button></div><div id="vb-kq"></div></div>' +
        '<div class="card vb-kh"><div class="card-h"><h3>' + ic("calendar") + 'Kế hoạch đăng</h3><span class="small muted" id="vb-kh-n"></span></div><div id="vb-kh"></div>' +
        '<div class="note mt"><span class="small">Mọi bài AI viết đều <b>chờ bạn duyệt</b>. Chưa duyệt thì chưa có gì lên mạng, kể cả khi đã tới giờ hẹn.</span></div></div></div>';
      var q = function (s) { return body.querySelector(s); };

      // ---------------------------------------------------------------- đăng ở đâu
      function nickCua(id) { return nick.filter(function (n) { return String(n.id) === String(id); })[0]; }
      function veDich() {
        var h = "", box = q("#vb-dich");
        q("#vb-cd-g").innerHTML = S.che_do === "api"
          ? "Máy chủ MinMin đăng thẳng lên Fanpage bằng kết nối Facebook Trang, không cần máy ở nhà bật. Chọn một hay nhiều Trang."
          : "Máy ở nhà mở nick trong GPM rồi đăng như người thật. Dùng cho nhóm, tường cá nhân, Instagram, TikTok, Threads, hoặc Trang của một nick.";
        if (S.che_do === "api") {
          if (!trangFp.length) {
            box.innerHTML = '<div class="note note-warn">' + ic("alert") + '<div class="grow">Chưa có Fanpage nào. Nối "Facebook Trang" ở trang Kết nối rồi vào <b>Trang &amp; Nhóm</b> bấm <b>Đồng bộ Trang</b>.</div><a class="btn btn-sm" href="#/fp-trang">Mở Trang &amp; Nhóm</a></div>';
            boChon = null;
          } else {
            box.innerHTML = '<div id="vb-fp"></div>';
            boChon = FP.boChonTrang(q("#vb-fp"), trangFp, S.trangChon || [], { cao: 240, doi: function () { S.trangChon = boChon.lay(); capNhat(); } });
          }
          return capNhat();
        }
        boChon = null;
        var nk = nickCua(S.nick);
        h += '<div class="fgrid"><div class="fld"><label for="vb-noi">Đăng vào</label><select class="sel" id="vb-noi">' + NOI_NICK.map(function (k) {
          return '<option value="' + k + '"' + (k === S.noi ? " selected" : "") + ">" + esc(DS.NOI_DANG[k]) + "</option>";
        }).join("") + '</select></div><div class="fld"><label for="vb-nick">Nick đăng</label><select class="sel" id="vb-nick"><option value="">' +
          (S.noi === "fb_nhom" || S.noi === "fb_tuong" ? "Nick nào rảnh thì đăng" : "Chọn nick") + "</option>" + nick.map(function (n) {
            var tr = DS.trangFB(n).length, tk = NT_TK[S.noi] ? DS.dichDen(n, NT_TK[S.noi])[0] : null;
            var phu = S.noi === "fb_trang" ? (tr ? " · " + tr + " Trang" : " · chưa có Trang") : (tk ? " · " + DS.tenTk(tk) : "");
            return '<option value="' + esc(n.id) + '"' + (String(n.id) === String(S.nick) ? " selected" : "") + ">" + esc(n.ten) + esc(phu) + "</option>";
          }).join("") + "</select></div></div>";
        if (S.noi === "fb_trang") {
          if (!nk) h += '<div class="hint">Chọn nick quản lý Trang. Số bên cạnh tên nick là số Trang máy đã quét được.</div>';
          else {
            var tr = DS.trangFB(nk);
            if (!tr.length) {
              h += '<div class="note note-warn mt-s">' + ic("alert") + '<div class="grow">' + (DS.choQuet(nk) ? "Máy ở nhà đang quét Trang của nick này, khoảng 1 phút. Bấm Làm mới sau đó." :
                "Chưa thấy Trang nào của nick này. Bấm Quét Trang để máy ở nhà đọc danh sách Trang nick đang quản lý.") + '</div><button class="btn btn-sm" type="button" data-act="quet">' + ic("refresh") + (DS.choQuet(nk) ? "Làm mới" : "Quét Trang") + "</button></div>";
            } else {
              if (!tr.some(function (d) { return d.link === S.dich; })) { S.dich = tr[0].link; S.dich_ten = tr[0].ten; }
              h += '<div class="fld mt-s"><label>Trang sẽ đăng <span class="req">*</span></label><div class="vb-trang">' + tr.map(function (d) {
                var on = d.link === S.dich;
                return '<label class="nick-row' + (on ? " on" : "") + '"><input type="radio" name="vb-tr" value="' + esc(d.link) + '"' + (on ? " checked" : "") + ">" +
                  (d.anh ? '<img class="av" src="' + esc(d.anh) + '" alt="" loading="lazy">' : DS.av(d.ten)) + '<span class="grow clip"><b>' + esc(d.ten) + '</b></span><a class="tiny" href="' + esc(d.link) + '" target="_blank" rel="noopener">Mở</a></label>';
              }).join("") + '</div><div class="hint">Danh sách quét ' + esc(DS.tuongDoi(DS.quetLuc(nk)) || "") + '. Thiếu Trang? <a href="#" data-act="quet">Quét lại</a>.</div></div>';
            }
          }
        } else if (S.noi === "fb_nhom") {
          var nh = S.nhomFb || [];
          h += '<div class="fld mt-s"><label for="vb-nhom">Nhóm</label><select class="sel" id="vb-nhom"><option value="">Để máy chọn nhóm nick đã tham gia (trong Kho group FB của sản phẩm)</option>' + nh.map(function (g) {
            return '<option value="' + esc(g.link) + '"' + (g.link === S.dich ? " selected" : "") + ">" + esc(g.ten || g.link) + "</option>";
          }).join("") + '<option value="__khac"' + (S.dich && !nh.some(function (g) { return g.link === S.dich; }) ? " selected" : "") + '>Nhóm khác, dán link...</option></select>' +
            '<input class="inp mt-s" id="vb-nhom-link" placeholder="https://www.facebook.com/groups/..." value="' + esc(S.dich && !nh.some(function (g) { return g.link === S.dich; }) ? S.dich : "") + '"' +
            (S.dich && !nh.some(function (g) { return g.link === S.dich; }) ? "" : " hidden") + '><div class="hint">' + (nh.length ? nh.length + " nhóm của sản phẩm này trong Kho group FB." : 'Sản phẩm chưa có nhóm nào trong <a href="#/nhom-fb">Kho group FB</a>.') + "</div></div>";
        } else if (S.noi === "fb_tuong") {
          h += '<div class="hint">Đăng lên trang cá nhân (tường) của ' + (nk ? "<b>" + esc(nk.ten) + "</b>" : "nick được chọn") + ".</div>";
        } else if (NT_TK[S.noi]) {
          if (nk) {
            var tk = DS.dichDen(nk, NT_TK[S.noi])[0];
            h += tk ? '<div class="hint">Đăng lên tài khoản <b>' + esc(DS.tenTk(tk)) + "</b> mà nick này đang đăng nhập.</div>"
              : '<div class="note note-warn mt-s">' + ic("alert") + '<div class="grow">Chưa thấy tài khoản ' + esc(DS.NOI_DANG[S.noi]) + ' của nick này, có thể profile chưa đăng nhập. Máy sẽ báo lỗi lúc đăng nếu chưa đăng nhập.</div><button class="btn btn-sm" type="button" data-act="quet">Quét lại</button></div>';
          }
        } else h += '<div class="hint">Đăng bằng tài khoản ' + esc(DS.NOI_DANG[S.noi]) + " mà profile của nick đang đăng nhập.</div>";
        box.innerHTML = h;
        if (S.noi !== "fb_trang" && S.noi !== "fb_nhom") { S.dich = ""; S.dich_ten = ""; }
        veAnh();
      }
      function napNhomFb() {
        S.nhomFb = null;
        return DS.api("GET", "/doi-social/nhom-fb" + DS.qs({ san_pham: S.sp }), null, { quiet: true }).then(function (d) {
          S.nhomFb = DS.list(d).filter(function (g) { return g.trang_thai !== "den"; });
          if (S.che_do === "nick" && S.noi === "fb_nhom") veDich();
        });
      }

      // ---------------------------------------------------------------- số bài, lịch
      function soTrang() { return S.che_do === "api" ? (S.trangChon || []).length : 1; }
      function tongBai() { return S.che_do === "api" ? soTrang() * S.so : S.so; }
      function veSo() {
        q("#vb-so-td").textContent = S.che_do === "api" ? "Mỗi Trang mấy bài" : "Số bài";
        var n = soTrang(), t = tongBai();
        q("#vb-so-g").innerHTML = S.che_do === "api"
          ? (n ? n + " Trang x " + S.so + " bài = <b>" + t + " bài</b>. AI viết riêng từng bài, không Trang nào trùng chữ với Trang nào." : "Chọn Trang ở bước 2.") + (t > 20 ? ' <span style="color:var(--err)">Tối đa 20 bài mỗi lần.</span>' : "")
          : "AI viết <b>" + S.so + " bài khác nhau</b> (khác góc kể, khác câu mở). Mỗi bài là một lần đăng riêng" + (S.so > 1 ? ", nên đặt giờ cách nhau ở bước 5" : "") + ". Khi duyệt, bạn bỏ được bài không ưng.";
      }
      function veLich() {
        var ds = [["duyet", "Ngay khi duyệt"]];
        if (S.che_do === "api") ds.push(["nhom", "Theo lịch nhóm Trang"]);
        ds.push(["gio", "Chọn giờ"]);
        if (S.lich === "nhom" && S.che_do !== "api") S.lich = "duyet";
        q("#vb-lich-seg").innerHTML = seg("vb-lich", ds, S.lich);
        q("#vb-gio").hidden = S.lich !== "gio";
        q("#vb-lich-g").innerHTML = {
          duyet: S.che_do === "api" ? "Bạn bấm Duyệt bài nào thì máy chủ đăng bài đó trong khoảng 1 phút." : "Bạn bấm Duyệt thì máy ở nhà nhận việc và đăng ngay khi rảnh (máy cần đang bật).",
          nhom: "Mỗi Trang đăng vào khung giờ trống kế tiếp trong lịch của nhóm Trang (hoặc lịch riêng của Trang), có lệch ngẫu nhiên. Đặt lịch ở Trang &amp; Nhóm.",
          gio: "Bài 1 đăng lúc giờ bạn chọn, các bài sau cách nhau đều. Duyệt trước giờ đó; duyệt trễ thì bài đăng ngay lúc duyệt."
        }[S.lich];
        if (S.lich === "gio" && !q("#vb-bd").value) {
          var t = new Date(Date.now() + 30 * 60000); t.setMinutes(Math.ceil(t.getMinutes() / 15) * 15, 0, 0);
          q("#vb-bd").value = FP.dtLocal(t.getTime() / 1000);
        }
      }
      function req(xemTruoc) {
        var r = { san_pham_id: S.sp, che_do: S.che_do, so_ban: S.so, lich: S.lich, xem_truoc: !!xemTruoc, yeu_cau: q("#vb-yc").value.trim() };
        if (S.lich === "gio") { r.bat_dau = FP.tuDt(q("#vb-bd").value); r.cach_phut = +q("#vb-cach").value; }
        if (S.anh.length) { r.media = S.anh.map(function (x) { return x.tep; }); r.kieu_anh = S.kieu_anh; }
        if (S.che_do === "api") r.trang_ids = S.trangChon || [];
        else { r.noi_dang = S.noi; if (S.nick) r.nick_id = S.nick; if (S.dich) { r.dich = S.dich; r.dich_ten = S.dich_ten; } }
        return r;
      }
      function thieu() {
        if (S.che_do === "api" && !soTrang()) return "Chọn ít nhất một Fanpage ở bước 2.";
        if (S.che_do === "api" && tongBai() > 20) return "Tối đa 20 bài mỗi lần, bớt Trang hoặc bớt số bài mỗi Trang.";
        if (S.che_do === "nick" && S.noi === "fb_trang" && !S.nick) return "Chọn nick quản lý Trang ở bước 2.";
        if (S.che_do === "nick" && S.noi === "fb_trang" && !S.dich) return "Chọn Trang sẽ đăng ở bước 2.";
        if (S.che_do === "nick" && NOI_NICK.indexOf(S.noi) >= 3 && !S.nick) return "Chọn nick sẽ đăng ở bước 2.";
        if (S.lich === "gio" && !q("#vb-bd").value) return "Chọn giờ đăng bài đầu tiên ở bước 5.";
        var coVd = S.anh.some(function (x) { return x.loai === "video"; });
        if (S.che_do === "api" && coVd) return "Fanpage qua API ở đây chỉ kèm ảnh. Bỏ video, hoặc dùng Tạo bài hàng loạt ở Bài đăng Fanpage.";
        if (S.che_do === "nick" && S.noi === "youtube" && !coVd) return "YouTube cần một video ở bước 4.";
        if (S.che_do === "nick" && S.noi === "tiktok" && !S.anh.length) return "TikTok cần một video (hoặc ảnh để đăng dạng slide) ở bước 4.";
        return "";
      }
      function capNhat() {
        veSo();
        var t = tongBai(), loi = thieu();
        q("#vb-nut").textContent = "Viết " + (t || "") + " bài";
        q("#vb-tom").innerHTML = loi ? '<span style="color:var(--warn)">' + ic("alert") + esc(loi) + "</span>" :
          "AI viết <b>" + t + " bài</b>, tất cả vào <b>chờ duyệt</b>" + (S.che_do === "api" ? " ở Bài đăng Fanpage." : " ở Duyệt nội dung.");
        q("[data-act=viet]").disabled = !!loi;
        clearTimeout(henXem);
        if (loi) { q("#vb-kh").innerHTML = '<div class="small muted" style="padding:8px 0">' + esc(loi) + "</div>"; q("#vb-kh-n").textContent = ""; return; }
        henXem = setTimeout(xemTruoc, 350);
      }
      function xemTruoc() {
        var lan = ++lanXem;
        DS.api("POST", "/doi-social/viet-bai", req(true), { quiet: true }).then(function (d) {
          if (lan !== lanXem || !ctx.alive) return;
          if (d.ok === false) { q("#vb-kh").innerHTML = '<div class="note note-err">' + ic("alert") + "<span>" + esc(d.error || "Chưa xem trước được") + "</span></div>"; return; }
          veKeHoach(d.ke_hoach || []);
        });
      }
      function moTaGio(x) {
        if (!x.hen_luc) return '<span class="muted">Khi bạn duyệt</span>';
        var s = DS.gio(x.hen_luc) + ' <span class="tiny muted">(' + esc(DS.tuongDoi(x.hen_luc)) + ")</span>";
        if (x.cach_hen === "fb") s += ' <span class="bd bd-out" title="Duyệt xong MinMin gửi bài sang Facebook hẹn sẵn">FB tự đăng</span>';
        return s;
      }
      function veKeHoach(kh) {
        q("#vb-kh-n").textContent = kh.length + " bài";
        q("#vb-kh").innerHTML = kh.length ? '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>#</th><th>Đăng lên</th><th>Lúc đăng</th></tr></thead><tbody>' + kh.map(function (x, i) {
          var dich = x.kenh === "api" ? (FP.avTrang({ ten: x.dich_ten, anh: x.dich_anh }) + "<b>" + esc(x.dich_ten || x.dich_id) + '</b><div class="tiny muted">Fanpage · máy chủ đăng</div>')
            : (DS.icNT(DS.NOI_DANG_NT[x.noi_dang] || "facebook", 18) + "<b>" + esc(x.dich_ten || "") + '</b><div class="tiny muted">' + esc(DS.NOI_DANG[x.noi_dang] || "") + " · nick " + esc(x.nick_ten || "") + "</div>");
          return "<tr><td>" + (i + 1) + '</td><td><div class="row" style="flex-wrap:nowrap;gap:8px"><div class="grow" style="min-width:0">' + dich + "</div></div></td><td>" + moTaGio(x) +
            (x.media && x.media.length ? '<div class="tiny muted">' + ic("image") + (Array.isArray(x.media[0]) ? x.media[0].length : x.media.length) + " ảnh</div>" : "") + "</td></tr>";
        }).join("") + "</tbody></table></div>" : '<div class="small muted">Chưa có bài nào trong kế hoạch.</div>';
      }

      // ---------------------------------------------------------------- ảnh
      function veAnh() {
        q("#vb-anh-ds").innerHTML = S.anh.length ? '<div class="row">' + S.anh.map(function (x, i) {
          return '<span class="vb-anh">' + (x.loai === "video" ? '<video src="' + esc(FP.tepUrl(x.tep)) + '" muted preload="metadata"></video>' : '<img src="' + esc(FP.tepUrl(x.tep)) + '" alt="">') + '<button type="button" class="vb-anh-x" data-act="bo-anh" data-i="' + i + '" aria-label="Bỏ ảnh">' + ic("x") + "</button></span>";
        }).join("") + "</div>" : "";
        var laVd = S.anh.some(function (x) { return x.loai === "video"; });
        q("#vb-anh-tt").textContent = laVd ? "1 video" : S.anh.length ? S.anh.length + " ảnh" : (S.che_do === "nick" && (S.noi === "tiktok" || S.noi === "youtube") ? "Cần một video cho " + DS.NOI_DANG[S.noi] + "." : "Không kèm ảnh thì đăng bài chữ.");
        q("#vb-anh-kieu").hidden = S.anh.length < 2 || laVd;
        capNhat();
      }
      q("#vb-anh").addEventListener("change", function () {
        var f = this.files; if (!f || !f.length) return;
        var fd = new FormData(); Array.prototype.forEach.call(f, function (x) { fd.append("tep", x); });
        q("#vb-anh-tt").textContent = "Đang tải ảnh lên...";
        DS.api("POST", "/doi-social/fp/media", fd).then(function (d) {
          if (d.ok !== false) {
            var moi = DS.list(d).filter(function (x) { return x.loai === "anh" || x.loai === "video"; });
            // một video thì thay hết (mỗi bài một video, không trộn ảnh); ảnh thì cộng dồn tối đa 10
            var vd = moi.filter(function (x) { return x.loai === "video"; });
            S.anh = vd.length ? [vd[vd.length - 1]] : S.anh.filter(function (x) { return x.loai !== "video"; }).concat(moi).slice(0, 10);
          }
          veAnh();
        });
        this.value = "";
      });

      // ---------------------------------------------------------------- sự kiện
      body.addEventListener("click", function (e) {
        var b = e.target.closest(".seg button"); if (!b) return;
        var sg = b.parentNode.id, v = b.getAttribute("data-v");
        Array.prototype.forEach.call(b.parentNode.children, function (x) { x.classList.toggle("on", x === b); });
        if (sg === "vb-cd") { S.che_do = v; veLich(); veDich(); }
        else if (sg === "vb-so") { S.so = +v; capNhat(); }
        else if (sg === "vb-lich") { S.lich = v; veLich(); capNhat(); }
        else if (sg === "vb-ka") { S.kieu_anh = v; capNhat(); }
      });
      body.addEventListener("change", function (e) {
        var t = e.target;
        if (t.id === "vb-sp") { S.sp = t.value; napNhomFb(); capNhat(); }
        else if (t.id === "vb-noi") { S.noi = t.value; S.dich = ""; S.dich_ten = ""; veDich(); }
        else if (t.id === "vb-nick") { S.nick = t.value; S.dich = ""; veDich(); }
        else if (t.name === "vb-tr") {
          S.dich = t.value; var nk = nickCua(S.nick), d = DS.trangFB(nk).filter(function (x) { return x.link === t.value; })[0];
          S.dich_ten = d ? d.ten : ""; Array.prototype.forEach.call(body.querySelectorAll(".vb-trang .nick-row"), function (r) { r.classList.toggle("on", r.querySelector("input").checked); });
          capNhat();
        } else if (t.id === "vb-nhom") {
          var khac = t.value === "__khac"; q("#vb-nhom-link").hidden = !khac;
          S.dich = khac ? q("#vb-nhom-link").value.trim() : t.value; S.dich_ten = khac ? S.dich : (t.options[t.selectedIndex].text || ""); capNhat();
        } else if (t.id === "vb-bd" || t.id === "vb-cach") capNhat();
      });
      body.addEventListener("input", function (e) { if (e.target.id === "vb-nhom-link") { S.dich = e.target.value.trim(); S.dich_ten = S.dich; capNhat(); } });

      DS.bind(body, {
        "bo-anh": function (b) { S.anh.splice(+b.getAttribute("data-i"), 1); veAnh(); },
        "quet": function () {
          var nk = nickCua(S.nick); if (!nk) return;
          if (DS.choQuet(nk)) { DS.boNho("nick"); return DS.layNick().then(function (d) { nick = DS.list(d, "nick"); veDich(); }); }
          DS.quetTaiKhoan([nk.id]).then(function () { veDich(); });
        },
        "viet": function (b) {
          var loi = thieu(); if (loi) return DS.toast(loi, "warn");
          b.disabled = true; b.innerHTML = '<span class="typing"><span></span><span></span><span></span></span> AI đang viết ' + tongBai() + " bài...";
          q("#vb-kq").innerHTML = tongBai() > 5 ? '<div class="small muted mt">Nhiều bài nên AI viết thành từng lượt 5 bài, mất khoảng ' + Math.ceil(tongBai() / 5) * 30 + " giây.</div>" : "";
          DS.api("POST", "/doi-social/viet-bai", req(false)).then(function (d) {
            b.disabled = false; b.innerHTML = ic("spark") + '<span id="vb-nut">Viết ' + tongBai() + " bài</span>";
            if (d.ok === false) { q("#vb-kq").innerHTML = ""; return; }
            veKetQua(d);
            DS.capNhatHuyHieu();
          });
        }
      });

      function veKetQua(d) {
        var api = d.che_do === "api", muc = d.muc || [], ids = muc.map(function (x) { return x.id; });
        q("#vb-kq").innerHTML = '<div class="card vb-ra mt"><div class="row-sb"><div><b>Đã viết ' + muc.length + " bài, đang chờ bạn duyệt</b>" +
          (d.bo_trung ? '<div class="tiny muted">Bỏ ' + d.bo_trung + " bài trùng với bài đã có.</div>" : "") + '</div><div class="row">' +
          '<a class="btn btn-sm" href="' + (api ? "#/fp-bai?trang_thai=cho_duyet" : "#/duyet") + '">' + (api ? "Mở Bài đăng Fanpage" : "Mở Duyệt nội dung") + "</a>" +
          '<button class="btn btn-sm btn-ok" data-act="duyet-het">' + ic("check") + "Duyệt cả " + muc.length + " bài</button></div></div>" +
          '<div class="vb-ra-ds">' + muc.map(function (x) {
            var noi = api ? (x.trang_ten || x.trang_id) : ((x.muc_tieu && x.muc_tieu.dich_ten) || DS.NOI_DANG[x.noi_dang] || "");
            return '<div class="vb-ra-dong"><div class="tiny muted">' + ic(api ? "flag" : "user") + esc(noi) + " · " + (x.hen_luc ? "đăng " + esc(DS.gio(x.hen_luc)) : "đăng khi duyệt") + '</div><div class="clamp3 small">' + esc(x.noi_dung || "") + "</div></div>";
          }).join("") + "</div></div>";
        DS.bind(q("#vb-kq"), {
          "duyet-het": function (b) {
            DS.xacNhan("Duyệt " + ids.length + " bài? Bài sẽ lên " + (api ? "Fanpage" : "mạng") + " công khai đúng giờ trong kế hoạch.", "Duyệt và đăng").then(function (ok) {
              if (!ok) return;
              b.disabled = true;
              var p = api ? DS.api("POST", "/doi-social/fp/bai/hanh-dong", { ids: ids, hanh_dong: "duyet" }) : DS.api("POST", "/doi-social/ban-nhap/duyet-nhieu", { ids: ids, dong_y: true });
              p.then(function (r) {
                if (r.ok === false) { b.disabled = false; return; }
                var so = api ? (r.so || 0) : (r.xong || []).length;
                DS.toast("Đã duyệt " + so + " bài.", "ok"); b.innerHTML = ic("check") + "Đã duyệt"; DS.capNhatHuyHieu();
              });
            });
          }
        });
      }

      veLich(); veDich(); napNhomFb();
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
