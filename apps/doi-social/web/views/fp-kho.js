/* Fanpage (API) - Kho nội dung - #/fp-kho (tab Nội dung · Bình luận · Link · Tiểu sử) */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic, FP = DS.fp;
  var TABS = ["noi_dung", "binh_luan", "link", "tieu_su"];
  var GOI_Y = {
    noi_dung: "Caption cho bài đăng. Bài tạo hàng loạt hoặc từ kênh nguồn lấy chữ từ đây.",
    binh_luan: "Câu Trang tự bình luận dưới bài vừa đăng (bật Bình luận sau khi đăng ở cấu hình nhóm).",
    link: "Link nối vào cuối caption hoặc bình luận. Dựng link tự động từ tên tệp bằng mẫu link.",
    tieu_su: "Tiểu sử dùng khi đổi thông tin hàng loạt ở Trang & Nhóm."
  };
  var MAU_GOI_Y = {
    noi_dung: "{Phim hay|Siêu phẩm} {hôm nay|tối nay} trên {ten_trang}\n---\nTập {ten_tep} đã lên sóng!\n{Xem ngay|Đừng bỏ lỡ} nhé",
    binh_luan: "{Xem full|Link full} ở đây nhé\n{Ai cần link|Link} mình để dưới nha",
    link: "https://example.com/bai-1\nhttps://example.com/bai-2",
    tieu_su: "{Kênh|Trang} {review phim|phim hay} mỗi ngày. Ghé {ten_trang} nhé!"
  };

  function panelSpin() {
    return '<div class="card"><div class="card-h"><h3>' + ic("spark") + 'Cú pháp spin</h3></div><div class="small fp-spin-help">' +
      "<p><code>{a|b|c}</code> chọn ngẫu nhiên một trong các chữ, lồng nhau được: <code>{Chào|{Xin chào|Hello}} bạn</code>.</p>" +
      "<p>Biến: <code>{ten_trang}</code> tên Trang, <code>{ngay}</code> ngày hôm nay, <code>{ten_tep}</code> tên tệp ảnh/video (bỏ đuôi).</p>" +
      "<p>Cần ngoặc nhọn thật thì gõ <code>{{</code> và <code>}}</code>.</p>" +
      "<p>Mỗi dòng là một mục. Mục nhiều dòng: tách các mục bằng một dòng chỉ có <code>---</code>.</p></div>" +
      '<div class="sep"></div><div class="fld"><label for="sp-mau">Thử spin</label><textarea class="ta" id="sp-mau" rows="3" placeholder="{Xem ngay|Đừng bỏ lỡ} tập mới trên {ten_trang}"></textarea></div>' +
      '<div class="fld"><label for="sp-tep">Tên tệp mẫu (cho {ten_tep})</label><input class="inp" id="sp-tep" placeholder="tap-12.mp4"></div>' +
      '<div class="row-sb mt-s"><span class="tiny muted">5 kết quả ngẫu nhiên</span><button class="btn btn-sm btn-soft" data-act="thu-spin">' + ic("spark") + 'Thử</button></div><div id="sp-kq" class="mt-s"></div></div>';
  }

  function moKho(loai, k, dsKho, xong) {
    k = k || {};
    var cu = !!k.id, gan = k.gan || {};
    var lNd = dsKho.filter(function (x) { return x.loai === "noi_dung"; }), lBl = dsKho.filter(function (x) { return x.loai === "binh_luan"; });
    var hop = function (ds, khoa) {
      if (!ds.length) return '<div class="small muted">Chưa có kho ' + (khoa === "noi_dung" ? "nội dung" : "bình luận") + " nào.</div>";
      return ds.map(function (x) {
        var on = (gan[khoa] || []).map(String).indexOf(String(x.id)) >= 0;
        return '<label class="chk" style="margin:0 14px 6px 0"><input type="checkbox" class="cb" data-gan="' + khoa + '" value="' + esc(x.id) + '"' + (on ? " checked" : "") + ">" + esc(x.ten) + "</label>";
      }).join("");
    };
    var m = DS.modal({ title: (cu ? "Sửa kho " : "Tạo kho ") + FP.KHO_LOAI[loai].toLowerCase(), wide: true,
      body: '<div class="fgrid"><div class="fld"><label for="kk-ten">Tên kho <span class="req">*</span></label><input class="inp" id="kk-ten" value="' + esc(k.ten || "") + '" placeholder="Ví dụ: Caption phim lẻ"></div>' +
        '<div class="fld"><label>Cách lấy mục</label><div class="seg" id="kk-cd">' + Object.keys(FP.CHE_DO_KHO).map(function (c) {
          return '<button type="button" data-v="' + c + '" class="' + ((k.che_do || "ngau_nhien") === c ? "on" : "") + '">' + esc(FP.CHE_DO_KHO[c]) + "</button>";
        }).join("") + '</div><div class="hint">Theo số trong tên tệp: tệp <code>12.mp4</code> hay <code>tap-012.mp4</code> lấy mục thứ 12. Tệp không có số thì lấy lần lượt.</div></div></div>' +
        (loai === "link" ? '<div class="sec" style="margin-top:14px"><div class="sec-t">' + ic("link") + 'Mẫu link (tuỳ chọn)</div><div class="fgrid"><div class="fld"><label for="kk-mau">Mẫu</label><input class="inp" id="kk-mau" value="' +
          esc(k.mau_link || "") + '" placeholder="https://phim.sbs/article/{ten_tep}"><div class="hint">{ten_tep} đổi thành tên tệp không dấu, chữ thường, khoảng trắng thành dấu gạch.</div></div>' +
          '<div class="fld"><label for="kk-tep">Thử với tên tệp</label><div class="row" style="flex-wrap:nowrap"><input class="inp" id="kk-tep" placeholder="Tập 12 Phim Hay.mp4"><button class="btn" type="button" id="kk-thu">Thử</button></div>' +
          '<div class="small mt-s" id="kk-thu-kq"></div></div></div>' +
          '<div class="fld mt"><label>Nối link vào caption của kho nội dung</label><div>' + hop(lNd, "noi_dung") + '</div></div><div class="fld"><label>Nối link vào bình luận của kho bình luận</label><div>' + hop(lBl, "binh_luan") +
          '</div><div class="hint">Kho được gắn sẽ thêm một link ở dòng cuối mỗi lần lấy mục.</div></div></div>' : "") +
        '<div class="fld" style="margin-top:14px"><label for="kk-muc">Các mục <span class="tiny muted" id="kk-dem"></span></label><textarea class="ta" id="kk-muc" rows="10" placeholder="' + esc(MAU_GOI_Y[loai]) + '"></textarea><div class="hint">Mỗi dòng một mục; mục nhiều dòng thì tách bằng dòng <code>---</code>. ' + (loai === "link" ? "Có mẫu link thì để trống cũng được." : "Có spin {a|b}.") + "</div></div>",
      foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="kk-luu">' + (cu ? "Lưu" : "Tạo kho") + "</button>" });
    var B = m.body, ta = B.querySelector("#kk-muc");
    function dem() { B.querySelector("#kk-dem").textContent = FP.tachMuc(ta.value).length + " mục"; }
    ta.addEventListener("input", dem);
    if (cu) {
      ta.value = "Đang tải..."; ta.disabled = true;
      FP.api("GET", "/kho/" + encodeURIComponent(k.id)).then(function (d) {
        ta.disabled = false;
        var x = d.kho || d;
        ta.value = d.ok === false ? "" : FP.ghepMuc(x.muc || []);
        dem();
      });
    } else dem();
    B.querySelector("#kk-cd").addEventListener("click", function (e) {
      var b = e.target.closest("button"); if (!b) return;
      Array.prototype.forEach.call(this.children, function (x) { x.classList.toggle("on", x === b); });
    });
    var thu = B.querySelector("#kk-thu");
    if (thu) thu.onclick = function () {
      var mau = B.querySelector("#kk-mau").value.trim(), tep = B.querySelector("#kk-tep").value.trim(), kq = B.querySelector("#kk-thu-kq");
      if (!mau || !tep) { DS.toast("Nhập mẫu link và tên tệp", "err"); return; }
      FP.api("POST", "/thu-link", { mau_link: mau, ten_tep: tep }).then(function (d) {
        kq.innerHTML = d.ok === false ? "" : ic("link") + ' <a href="' + esc(d.link) + '" target="_blank" rel="noopener">' + esc(d.link) + "</a>";
      });
    };
    m.foot.querySelector("#kk-luu").onclick = function () {
      var ten = B.querySelector("#kk-ten").value.trim();
      if (!ten) { DS.toast("Nhập tên kho", "err"); return; }
      if (ta.disabled) return;
      var cd = B.querySelector("#kk-cd button.on");
      var b = { ten: ten, che_do: cd ? cd.getAttribute("data-v") : "ngau_nhien", muc: FP.tachMuc(ta.value) };
      if (!cu) b.loai = loai;
      if (loai === "link") {
        b.mau_link = B.querySelector("#kk-mau").value.trim();
        var g = { noi_dung: [], binh_luan: [] };
        Array.prototype.forEach.call(B.querySelectorAll("[data-gan]:checked"), function (c) { g[c.getAttribute("data-gan")].push(isNaN(+c.value) ? c.value : +c.value); });
        b.gan = g;
      }
      var btn = this; btn.disabled = true;
      FP.api(cu ? "PATCH" : "POST", "/kho" + (cu ? "/" + encodeURIComponent(k.id) : ""), b).then(function (d) {
        btn.disabled = false;
        if (d.ok === false) return;
        DS.toast(cu ? "Đã lưu kho" : "Đã tạo kho " + ten, "ok"); DS.boNho("fp-kho"); m.close(); xong();
      });
    };
  }

  DS.view("fp-kho", {
    title: "Kho nội dung Fanpage",
    render: function (el, ctx) {
      var tab = TABS.indexOf(ctx.q.tab) >= 0 ? ctx.q.tab : "noi_dung", ds = [], tatCa = [];
      el.innerHTML = DS.ph("Kho nội dung", "Caption, bình luận, link và tiểu sử soạn sẵn cho Fanpage. Có spin để mỗi bài một khác.",
        '<button class="btn btn-pri" data-act="tao">' + ic("plus") + "Tạo kho " + esc(FP.KHO_LOAI[tab].toLowerCase()) + "</button>") +
        DS.tabs(TABS.map(function (t) { return { id: t, ten: FP.KHO_LOAI[t] }; }), tab, "#/fp-kho?tab=") +
        '<div class="grid g-21"><div class="card card-x"><div class="card-h"><div><h3>Kho ' + esc(FP.KHO_LOAI[tab].toLowerCase()) + '</h3><div class="small muted" style="margin-top:2px">' + esc(GOI_Y[tab]) + '</div></div></div><div id="kh-ds">' +
        DS.skel(4) + "</div></div>" + panelSpin() + '</div><input type="file" id="kh-nhap" accept=".txt,.csv,text/plain,text/csv" hidden>';
      var nhapId = null;
      function nap() {
        return FP.api("GET", "/kho").then(function (d) {
          if (!ctx.alive) return;
          var box = el.querySelector("#kh-ds");
          if (d.ok === false) { box.innerHTML = DS.loiThe(d.error, true); return; }
          DS.cache["fp-kho"] = { t: Date.now(), d: d };
          tatCa = DS.list(d); ds = tatCa.filter(function (k) { return (k.loai || "noi_dung") === tab; });
          if (!ds.length) { box.innerHTML = DS.rong("Chưa có kho nào", "Tạo kho rồi dán các mục vào, hoặc nhập từ tệp .txt / .csv.", "box", '<button class="btn btn-pri" data-act="tao">' + ic("plus") + "Tạo kho</button>"); return; }
          box.innerHTML = '<div class="tw" style="border-top:1px solid var(--line)"><table class="tbl"><thead><tr><th>Kho</th><th>Cách lấy</th><th class="num">Mục</th>' + (tab === "link" ? "<th>Gắn với</th>" : "") + "<th></th></tr></thead><tbody>" +
            ds.map(function (k) {
              var g = k.gan || {}, ganTen = [];
              (g.noi_dung || []).forEach(function (id) { ganTen.push("Caption: " + FP.tenKho(tatCa, id)); });
              (g.binh_luan || []).forEach(function (id) { ganTen.push("Bình luận: " + FP.tenKho(tatCa, id)); });
              return "<tr><td><b>" + esc(k.ten) + "</b>" + (k.mau_link ? '<div class="sub clip" style="max-width:260px">' + ic("link") + " " + esc(k.mau_link) + "</div>" : "") + '</td><td class="small nw">' + esc(FP.CHE_DO_KHO[k.che_do] || k.che_do || "") +
                '</td><td class="num">' + (k.so ? FP.so(k.so) : '<span class="bd bd-warn">Trống</span>') + "</td>" +
                (tab === "link" ? '<td class="small">' + (ganTen.length ? ganTen.map(esc).join("<br>") : '<span class="muted">Chưa gắn</span>') + "</td>" : "") +
                '<td class="nw" style="text-align:right"><button class="btn btn-xs" data-act="nhap" data-id="' + esc(k.id) + '" title="Nhập thêm từ tệp .txt / .csv">' + ic("upload") + 'Nhập tệp</button> ' +
                '<button class="btn btn-xs" data-act="sua" data-id="' + esc(k.id) + '">' + ic("edit") + 'Sửa</button> <button class="btn btn-xs btn-dan" data-act="xoa" data-id="' + esc(k.id) + '" aria-label="Xoá kho">' + ic("trash") + "</button></td></tr>";
            }).join("") + "</tbody></table></div>";
        });
      }
      function tim(id) { return ds.filter(function (k) { return String(k.id) === String(id); })[0]; }
      el.querySelector("#kh-nhap").addEventListener("change", function () {
        var f = this.files && this.files[0], inp = this;
        if (!f || nhapId == null) return;
        if (f.size > 5 * 1024 * 1024) { DS.toast("Tệp lớn quá (tối đa 5MB)", "err"); inp.value = ""; return; }
        var r = new FileReader();
        r.onload = function () {
          var chu = String(r.result || "").replace(/^﻿/, "");
          inp.value = "";
          if (!chu.trim()) { DS.toast("Tệp trống", "err"); return; }
          FP.api("POST", "/kho/" + encodeURIComponent(nhapId) + "/nhap", { chu: chu }).then(function (d) {
            if (d.ok === false) return;
            DS.toast("Đã nhập " + FP.so(d.so != null ? d.so : FP.tachMuc(chu).length) + " mục", "ok"); DS.boNho("fp-kho"); nap();
          });
        };
        r.onerror = function () { DS.toast("Không đọc được tệp", "err"); };
        r.readAsText(f, "utf-8");
      });
      DS.bind(el, {
        "tai-lai": nap,
        "tao": function () { moKho(tab, null, tatCa, nap); },
        "sua": function (t) { var k = tim(t.getAttribute("data-id")); if (k) moKho(tab, k, tatCa, nap); },
        "nhap": function (t) { nhapId = t.getAttribute("data-id"); el.querySelector("#kh-nhap").click(); },
        "xoa": function (t) {
          var k = tim(t.getAttribute("data-id")) || {};
          DS.xacNhan("Xoá kho " + (k.ten || "") + "? Nhóm hay Trang đang dùng kho này sẽ không còn chữ để lấy.", "Xoá kho", true).then(function (ok) {
            if (ok) FP.api("DELETE", "/kho/" + encodeURIComponent(k.id)).then(function (d) { if (d.ok !== false) { DS.toast("Đã xoá kho", "ok"); DS.boNho("fp-kho"); nap(); } });
          });
        },
        "thu-spin": function (b) {
          var mau = el.querySelector("#sp-mau").value, kq = el.querySelector("#sp-kq");
          if (!mau.trim()) { DS.toast("Nhập một câu có spin để thử", "err"); return; }
          b.disabled = true;
          FP.api("POST", "/thu-spin", { mau: mau, ten_tep: el.querySelector("#sp-tep").value.trim() }).then(function (d) {
            b.disabled = false;
            if (d.ok === false) return;
            var l = d.mau_thu || [];
            kq.innerHTML = l.length ? '<ol class="fp-spin-kq">' + l.map(function (x) { return '<li class="pre">' + esc(x) + "</li>"; }).join("") + "</ol>" : '<span class="small muted">Không có kết quả.</span>';
          });
        }
      });
      return nap();
    }
  });
})();
