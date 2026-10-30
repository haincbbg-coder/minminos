/* Duyệt nội dung - #/duyet?tt=cho_duyet */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;
  var TABS = [["cho_duyet", "Chờ duyệt"], ["da_duyet", "Đã duyệt"], ["da_dang", "Đã đăng"], ["da_bo", "Đã bỏ"], ["loi", "Lỗi"], ["het_han", "Hết hạn"]];
  var LOAI = { binh_luan: "Bình luận", bai_dang: "Bài đăng", tra_loi: "Trả lời" };
  var MOI = 20;

  function conLai(t) {
    if (!t) return "";
    var s = t - Date.now() / 1000;
    if (s <= 0) return "đã hết hạn";
    if (s < 3600) return "hết hạn sau " + Math.max(1, Math.round(s / 60)) + " phút";
    return "hết hạn sau " + Math.round(s / 3600) + " giờ";
  }

  DS.view("duyet", {
    title: "Duyệt nội dung",
    render: function (el, ctx) {
      var F = { trang_thai: TABS.some(function (t) { return t[0] === ctx.q.tt; }) ? ctx.q.tt : "cho_duyet", noi_dang: "", san_pham: "", trang: 1 };
      var chon = {}, ds = [], KT = {}, sua = {};
      el.innerHTML = DS.ph("Duyệt nội dung", "Bình luận và bài AI viết nằm đây chờ bạn. Duyệt thì máy chạy (máy ở nhà hoặc Chrome MinMin) mới đăng.",
        '<a class="btn btn-pri" href="#/kho?tab=viet">' + ic("spark") + "Viết bài AI</a>") + '<div id="dy-tabs"></div><div id="dy-loc"></div><div id="dy-ds">' + DS.skel(6) + "</div>";

      DS.layKienThuc().then(function (d) { DS.list(d, "kien_thuc").forEach(function (k) { KT[k.id] = k; }); nap(); });

      function veTabs(dem) {
        dem = dem || {};
        el.querySelector("#dy-tabs").innerHTML = '<div class="tabs">' + TABS.map(function (t) {
          return '<button class="tab' + (t[0] === F.trang_thai ? " on" : "") + '" data-act="tab" data-v="' + t[0] + '">' + t[1] + '<span class="cnt">' + DS.so(dem[t[0]] || 0) + "</span></button>";
        }).join("") + "</div>";
      }
      function veLoc(demNoi) {
        demNoi = demNoi || {};
        var tong = 0;
        Object.keys(demNoi).forEach(function (k) { tong += demNoi[k] || 0; });
        var sp = Object.keys(KT).map(function (k) { return KT[k]; });
        el.querySelector("#dy-loc").innerHTML = '<div class="row-sb mb"><div class="chips"><button class="chip' + (!F.noi_dang ? " on" : "") + '" data-act="noi" data-v="">Mọi nơi đăng <span class="cnt">' + tong + "</span></button>" +
          Object.keys(DS.NOI_DANG).filter(function (k) { return demNoi[k]; }).map(function (k) {
            return '<button class="chip' + (F.noi_dang === k ? " on" : "") + '" data-act="noi" data-v="' + k + '">' + esc(DS.NOI_DANG[k]) + ' <span class="cnt">' + demNoi[k] + "</span></button>";
          }).join("") + '</div><select class="sel sel-sm" id="dy-sp" style="width:auto;min-width:180px"><option value="">Mọi sản phẩm</option>' + sp.map(function (k) {
            return '<option value="' + esc(k.id) + '"' + (String(F.san_pham) === String(k.id) ? " selected" : "") + ">" + esc(k.ten) + "</option>";
          }).join("") + "</select></div>" +
          (F.trang_thai === "cho_duyet" && ds.length ? '<div class="bulk"><label class="chk"><input type="checkbox" class="cb" id="dy-all"> Chọn tất cả</label><span class="small muted" id="dy-n"></span><span class="grow"></span>' +
            '<button class="btn btn-sm btn-ok" data-act="duyet-nhieu" data-v="1">' + ic("check") + 'Duyệt đã chọn</button><button class="btn btn-sm" data-act="duyet-nhieu" data-v="0">' + ic("x") + "Bỏ đã chọn</button></div>" : "");
        demChon();
      }
      function demChon() {
        var n = Object.keys(chon).filter(function (k) { return chon[k]; }).length, e = el.querySelector("#dy-n");
        if (e) e.textContent = n ? n + " bài đã chọn" : "";
        Array.prototype.forEach.call(el.querySelectorAll(".bulk .btn"), function (b) { b.disabled = !n; });
        var a = el.querySelector("#dy-all");
        if (a) { a.checked = n && n === ds.length; a.indeterminate = n > 0 && n < ds.length; }
      }

      function theNhap(b) {
        var sp = KT[b.san_pham_id], dangSua = sua[b.id] != null, cho = b.trang_thai === "cho_duyet";
        return '<div class="dr' + (chon[b.id] ? " sel" : "") + '" data-id="' + b.id + '"><div class="dr-h">' + (cho ? '<input type="checkbox" class="cb" data-chon="' + b.id + '"' + (chon[b.id] ? " checked" : "") + ' style="margin-top:3px" aria-label="Chọn">' : "") +
          DS.icNT(DS.NOI_DANG_NT[b.noi_dang] || "facebook", 26) + '<div class="grow" style="min-width:0"><div class="row"><b>' + esc(LOAI[b.loai] || b.loai) + "</b>" +
          '<span class="muted">|</span><span>' + esc(DS.NOI_DANG[b.noi_dang] || b.noi_dang) + "</span>" + (b.chay_thu ? DS.bd("Chạy thử", "brand") : "") + (cho ? "" : DS.bdMap({ da_duyet: ["Đã duyệt", "info"], da_dang: ["Đã đăng", "ok"],
            da_bo: ["Đã bỏ", "mu"], loi: ["Lỗi", "err"], het_han: ["Hết hạn", "mu"] }, b.trang_thai)) + "</div>" +
          '<div class="dr-meta">' + (b.nick_ten ? "<span>" + ic("user") + esc(b.nick_ten) + "</span>" : "<span>" + ic("user") + "Chưa gán nick</span>") +
          ((b.muc_tieu && b.muc_tieu.dich_ten) || b.nhom ? '<span class="clip" style="max-width:300px" title="' + esc(b.nhom || "") + '">' + ic(b.noi_dang === "fb_trang" ? "flag" : "users") + "Đăng lên: " + esc((b.muc_tieu && b.muc_tieu.dich_ten) || b.nhom) + "</span>" : "") +
          (b.hen_luc ? '<span style="color:var(--brand)">' + ic("calendar") + "Đăng lúc " + esc(DS.gio(b.hen_luc)) + "</span>" : (b.loai === "bai_dang" && cho ? "<span>" + ic("calendar") + "Đăng ngay khi duyệt</span>" : "")) + (sp ? "<span>" + ic("tag") + esc(sp.ten) + "</span>" : "") +
          (cho && b.het_han ? '<span style="color:var(--warn)">' + ic("clock") + esc(conLai(b.het_han)) + "</span>" : "<span>" + ic("clock") + DS.gio(b.tao_luc) + "</span>") +
          (b.link_goc ? '<a href="' + esc(b.link_goc) + '" target="_blank" rel="noopener">' + ic("link") + " Mở bài gốc</a>" : "") + "</div></div></div>" +
          (b.bai_goc ? '<div class="quote"><span class="clamp2" data-act="mo-goc" style="cursor:pointer" title="Bấm để xem đủ"><b>Bài gốc:</b> ' + esc(b.bai_goc) + "</span></div>" : "") +
          (b.ly_do ? '<div class="why"><b>Vì sao AI chọn:</b> ' + esc(b.ly_do) + "</div>" : "") +
          (dangSua ? '<textarea class="ta" style="margin-top:10px" rows="5" data-sua="' + b.id + '">' + esc(sua[b.id]) + "</textarea>" :
            '<div class="body-txt">' + esc(b.noi_dung) + "</div>") +
          (b.ket_qua && (b.trang_thai === "loi" || b.trang_thai === "da_dang") ? '<div class="small ' + (b.trang_thai === "loi" ? "" : "muted") + '" style="margin-top:6px;' + (b.trang_thai === "loi" ? "color:var(--err)" : "") + '">' +
            esc(typeof b.ket_qua === "string" ? b.ket_qua : (b.ket_qua.loi || b.ket_qua.link || "")) + "</div>" : "") +
          '<div class="dr-f"><div class="row">' + (dangSua ? '<button class="btn btn-sm btn-pri" data-act="luu-sua">Lưu sửa</button><button class="btn btn-sm btn-ghost" data-act="huy-sua">Thôi</button>' :
            (cho || b.trang_thai === "da_duyet" ? '<button class="btn btn-sm btn-ghost" data-act="sua">' + ic("edit") + "Sửa</button>" : "")) +
          (cho ? '<button class="btn btn-sm btn-ghost" data-act="viet-lai">' + ic("spark") + "Viết lại (AI)</button>" : "") + "</div>" +
          (cho ? '<div class="row"><button class="btn btn-sm" data-act="bo">' + ic("x") + 'Bỏ</button><button class="btn btn-sm btn-ok" data-act="duyet">' + ic("check") + "Duyệt</button></div>" : "") + "</div></div>";
      }

      function nap() {
        var box = el.querySelector("#dy-ds");
        return DS.api("GET", "/doi-social/ban-nhap" + DS.qs({ trang_thai: F.trang_thai, noi_dang: F.noi_dang, san_pham: F.san_pham, trang: F.trang, moi_trang: MOI })).then(function (d) {
          if (!ctx.alive) return;
          if (d.ok === false) { veTabs({}); box.innerHTML = DS.loiThe(d.error, true); return; }
          ds = DS.list(d, "ban_nhap");
          var tong = d.tong != null ? d.tong : ds.length;
          chon = {};
          veTabs(d.dem); veLoc(d.dem_noi_dang);
          if (!ds.length) {
            box.innerHTML = '<div class="card">' + (F.trang_thai === "cho_duyet" ? DS.rong("Không có gì chờ duyệt", "Khi Agent viết bình luận hay bài mới, chúng sẽ nằm ở đây. Bạn cũng có thể nhờ AI viết bài ngay.", "done",
              '<a class="btn btn-pri" href="#/kho?tab=viet">' + ic("spark") + "Viết bài AI</a>") : DS.rong("Trống", "Không có nháp nào ở mục này.", "list")) + "</div>";
            return;
          }
          box.innerHTML = ds.map(theNhap).join("") + '<div class="card card-x mt">' + DS.phanTrang(tong, d.trang || F.trang, MOI) + "</div>";
          if (F.trang_thai === "cho_duyet" && d.dem) { var n = document.getElementById("n-duyet"); if (n) { n.hidden = !d.dem.cho_duyet; n.textContent = d.dem.cho_duyet; } }
        });
      }
      function nhap(t) { var c = t.closest("[data-id]"); var id = c && c.getAttribute("data-id"); return ds.filter(function (b) { return String(b.id) === String(id); })[0]; }
      function veLaiThe(b) { var c = el.querySelector('.dr[data-id="' + b.id + '"]'); if (c) c.outerHTML = theNhap(b); }
      function hanhDong(b, path, body, msg) {
        return DS.api("POST", "/doi-social/ban-nhap/" + b.id + path, body || {}).then(function (d) {
          if (d.ok === false) return;
          DS.toast(msg, "ok"); nap(); DS.capNhatHuyHieu();
        });
      }

      el.addEventListener("change", function (e) {
        var t = e.target;
        if (t.id === "dy-sp") { F.san_pham = t.value; F.trang = 1; nap(); }
        else if (t.id === "dy-all") { ds.forEach(function (b) { chon[b.id] = t.checked; }); Array.prototype.forEach.call(el.querySelectorAll("[data-chon]"), function (c) { c.checked = t.checked; c.closest(".dr").classList.toggle("sel", t.checked); }); demChon(); }
        else if (t.getAttribute("data-chon")) { chon[t.getAttribute("data-chon")] = t.checked; t.closest(".dr").classList.toggle("sel", t.checked); demChon(); }
      });
      el.addEventListener("input", function (e) { var id = e.target.getAttribute("data-sua"); if (id) sua[id] = e.target.value; });
      DS.bind(el, {
        "tai-lai": nap,
        "tab": function (t) { F.trang_thai = t.getAttribute("data-v"); F.trang = 1; F.noi_dang = ""; try { history.replaceState(null, "", "#/duyet?tt=" + F.trang_thai); } catch (x) {} nap(); },
        "noi": function (t) { F.noi_dang = t.getAttribute("data-v"); F.trang = 1; nap(); },
        "trang": function (t) { F.trang = +t.getAttribute("data-trang") || 1; nap(); window.scrollTo(0, 0); },
        "mo-goc": function (t) { t.classList.toggle("clamp2"); },
        "sua": function (t) { var b = nhap(t); sua[b.id] = b.noi_dung; veLaiThe(b); var a = el.querySelector('[data-sua="' + b.id + '"]'); if (a) a.focus(); },
        "huy-sua": function (t) { var b = nhap(t); delete sua[b.id]; veLaiThe(b); },
        "luu-sua": function (t) {
          var b = nhap(t), nd = String(sua[b.id] || "").trim();
          if (!nd) { DS.toast("Nội dung trống", "err"); return; }
          DS.api("PUT", "/doi-social/ban-nhap/" + b.id, { noi_dung: nd }).then(function (d) {
            if (d.ok === false) return;
            b.noi_dung = (d.ban_nhap && d.ban_nhap.noi_dung) || nd; delete sua[b.id]; veLaiThe(b); DS.toast("Đã lưu nội dung", "ok");
          });
        },
        "duyet": function (t) { hanhDong(nhap(t), "/duyet", {}, "Đã duyệt, máy ở nhà sẽ đăng"); },
        "bo": function (t) { hanhDong(nhap(t), "/bo", {}, "Đã bỏ nháp"); },
        "viet-lai": function (t) {
          var b = nhap(t);
          DS.hoi("Nhờ AI viết lại", "Muốn sửa thế nào? (tuỳ chọn)", "Ví dụ: ngắn hơn, bớt quảng cáo, thêm câu hỏi cho khách").then(function (yc) {
            if (yc === null) return;
            var c = el.querySelector('.dr[data-id="' + b.id + '"] .body-txt');
            if (c) c.innerHTML = '<span class="typing"><span></span><span></span><span></span></span> AI đang viết lại...';
            DS.api("POST", "/doi-social/ban-nhap/" + b.id + "/viet-lai", { yeu_cau: yc.trim() }).then(function (d) {
              if (d.ok === false) { veLaiThe(b); return; }
              b.noi_dung = (d.ban_nhap && d.ban_nhap.noi_dung) || d.noi_dung || b.noi_dung; veLaiThe(b); DS.toast("AI đã viết lại", "ok");
            });
          });
        },
        "duyet-nhieu": function (t) {
          var ids = Object.keys(chon).filter(function (k) { return chon[k]; }).map(function (x) { return isNaN(+x) ? x : +x; });
          if (!ids.length) return;
          var dy = t.getAttribute("data-v") === "1";
          DS.api("POST", "/doi-social/ban-nhap/duyet-nhieu", { ids: ids, dong_y: dy }).then(function (d) {
            if (d.ok === false) return;
            DS.toast((dy ? "Đã duyệt " : "Đã bỏ ") + ids.length + " bài", "ok"); nap(); DS.capNhatHuyHieu();
          });
        }
      });
      ctx.every(function () { if (!Object.keys(sua).length && !Object.keys(chon).some(function (k) { return chon[k]; })) nap(); }, 60000);
    }
  });
})();
