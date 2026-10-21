/* Fanpage (API) - Tổng quan - #/fp-tong-quan */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic, FP = DS.fp;

  function the(i, cls, k, v, s, spark) {
    return '<div class="stat"><div class="k"><span class="ico ' + cls + '">' + ic(i) + "</span>" + esc(k) + '</div><div class="row-sb" style="align-items:flex-end"><div class="v">' + v + "</div>" +
      (spark || "") + '</div><div class="s">' + s + "</div></div>";
  }

  function moCaiDat() {
    var m = DS.modal({ title: "Cài đặt Fanpage", body: DS.skel(4), foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="cd-luu">Lưu</button>' });
    FP.api("GET", "/cai-dat").then(function (d) {
      if (d.ok === false) { m.body.innerHTML = DS.rong("Chưa tải được cài đặt", esc(d.error), "box"); return; }
      var c = d.cai_dat || d;
      m.body.innerHTML = '<div class="fgrid"><div class="fld"><label for="cd-luong">Số bài đăng mỗi lượt (30 giây)</label><input class="inp" type="number" min="1" max="20" id="cd-luong" value="' + esc(c.luong || 3) +
        '"><div class="hint">Nhiều Trang tới giờ cùng lúc thì đăng dần, mỗi lượt chừng này bài.</div></div>' +
        '<div class="fld"><label for="cd-xoa">Xoá tệp đã đăng sau (ngày)</label><input class="inp" type="number" min="1" max="365" id="cd-xoa" value="' + esc(c.xoa_tep_sau_ngay || 7) + '"></div>' +
        '<div class="fld"><label for="cd-ig">Instagram tối đa mỗi 24 giờ</label><input class="inp" type="number" min="1" max="100" id="cd-ig" value="' + esc(c.ig_toi_da_24h || 50) +
        '"><div class="hint">Instagram giới hạn số bài mỗi tài khoản trong 24 giờ.</div></div></div>' +
        '<div class="swrow mt"><div class="grow"><div style="font-weight:500">Báo mỗi bài đăng xong</div><div class="hint">Gửi tin vào hòm thư MinMin mỗi khi một bài lên Trang. Nhiều Trang thì khá ồn.</div></div>' +
        DS.sw('id="cd-bao"', !!c.bao_moi_bai) + "</div>" +
        '<div class="swrow"><div class="grow"><div style="font-weight:500">Cho tạo bài trùng</div><div class="hint">Mặc định MinMin bỏ bài trùng (cùng Trang, cùng nội dung, cùng tệp). Bật thì vẫn tạo.</div></div>' +
        DS.sw('id="cd-trung"', !!c.cho_dang_trung) + "</div>";
    });
    m.foot.querySelector("#cd-luu").onclick = function () {
      var g = function (id) { var e = m.body.querySelector(id); return e ? e : null; };
      if (!g("#cd-luong")) { m.close(); return; }
      var body = { luong: +g("#cd-luong").value || 3, xoa_tep_sau_ngay: +g("#cd-xoa").value || 7, ig_toi_da_24h: +g("#cd-ig").value || 50,
        bao_moi_bai: g("#cd-bao").checked, cho_dang_trung: g("#cd-trung").checked };
      FP.api("POST", "/cai-dat", body).then(function (d) { if (d.ok !== false) { DS.toast("Đã lưu cài đặt", "ok"); m.close(); } });
    };
  }

  DS.view("fp-tong-quan", {
    title: "Tổng quan Fanpage",
    render: function (el, ctx) {
      el.innerHTML = DS.ph("Tổng quan Fanpage", "Đăng lên Trang bằng Graph API, chạy ngay trên máy chủ MinMin, không cần máy ở nhà.") + DS.skel(6, 4);
      function nap() {
        return FP.api("GET", "/tong-quan").then(function (d) {
          if (!ctx.alive) return;
          if (d.ok === false) { el.innerHTML = DS.ph("Tổng quan Fanpage", "") + DS.loiThe(d.error, true); return; }
          ve(d);
        });
      }
      function ve(d) {
        var tr = d.trang || {}, bai = d.bai || {}, cb = d.canh_bao || {}, ig = d.ig || {}, xh = d.xu_huong || [], top = d.top_trang || [], hd = d.hoat_dong || [];
        var h = DS.ph("Tổng quan Fanpage", "Đăng lên Trang bằng Graph API, chạy ngay trên máy chủ MinMin, không cần máy ở nhà.",
          '<button class="btn" data-act="tai-lai">' + ic("refresh") + 'Làm mới</button><button class="btn" data-act="cai-dat">' + ic("gauge") + 'Cài đặt</button>' +
          '<a class="btn btn-pri" href="#/fp-bai?tao=1">' + ic("plus") + "Tạo bài hàng loạt</a>");
        h += FP.dungBanner(d.dung_tu_dong);
        if (!d.nguon_token) {
          h += '<div class="card mb">' + DS.rong("Chưa có nguồn token nào", "Nối kết nối <b>Facebook Trang (tự tạo app)</b> ở trang Kết nối của MinMin, hoặc dán token ở tab Token. Sau đó bấm Đồng bộ Trang.",
            "robot", '<a class="btn btn-pri" href="#/fp-trang?tab=token">' + ic("plus") + "Thêm token</a>") + "</div>";
        }
        var soCb = (cb.chan || 0) + (cb.nang || 0) + (cb.nhac || 0);
        if (soCb) {
          h += '<a class="fp-cb-strip mb' + (cb.chan ? " chan" : cb.nang ? " nang" : "") + '" href="#/fp-canh-bao">' + ic("alert") + '<span class="grow">' +
            (cb.chan ? "<b>" + cb.chan + " lỗi chặn đứng</b> đang làm Trang không đăng được. " : "") +
            (cb.nang ? cb.nang + " cảnh báo nặng. " : "") + (cb.nhac ? cb.nhac + " lời nhắc." : "") + "</span><span class=\"small\">Xem cách sửa</span>" + ic("chevr") + "</a>";
        }
        h += '<div class="grid g4">' +
          the("users", "", "Trang đang quản lý", FP.so(tr.tong), FP.so(tr.co_lich) + " Trang có lịch" + (tr.loi ? ' · <span style="color:var(--err)">' + FP.so(tr.loi) + " lỗi</span>" : "")) +
          the("ok", "ico-ok", "Bài đã đăng", FP.so(bai.da_dang), FP.so(bai.cho_dang) + " chờ đăng · " + FP.so(bai.da_hen_fb) + " đã hẹn trên FB",
            FP.spark(xh.map(function (x) { return x.da_dang; }))) +
          the("check", "", "Chờ bạn duyệt", FP.so(bai.cho_duyet), bai.cho_duyet ? '<a href="#/fp-bai?trang_thai=cho_duyet">Duyệt ngay</a>' : "Không có bài nào chờ") +
          the("alert", "ico-err", "Bài lỗi", FP.so(bai.loi), bai.loi ? '<a href="#/fp-bai?trang_thai=loi">Xem và thử lại</a>' : "Không có lỗi") + "</div>";
        h += '<div class="grid g4 mt">' +
          the("user", "ico-info", "Người theo dõi", FP.so(d.nguoi_theo_doi), "cộng mọi Trang") +
          the("eye", "ico-info", "Tiếp cận · 7 ngày", FP.so(d.tiep_can_7), "người xem duy nhất", FP.spark(xh.map(function (x) { return x.tiep_can; }))) +
          the("activity", "ico-info", "Tương tác · 7 ngày", FP.so(d.tuong_tac_7), "cảm xúc, bình luận, chia sẻ") +
          the("image", "", "Instagram", FP.so(ig.tai_khoan), FP.so(ig.da_dang_24h) + " bài trong 24 giờ") + "</div>";

        h += '<div class="grid g-21 mt"><div class="card"><div class="card-h"><div><h3>Bài đã đăng mỗi ngày</h3><div class="small muted" style="margin-top:2px">' + xh.length + ' ngày gần nhất</div></div>' +
          '<a class="small" href="#/fp-bao-cao">Báo cáo chi tiết</a></div>' + (xh.length ? '<div class="chart" id="fp-tq-ch"></div>' : DS.rong("Chưa có số liệu", "Đăng bài đầu tiên để thấy biểu đồ ở đây.", "list")) + "</div>";
        h += '<div class="card"><div class="card-h"><h3>Trang nổi bật</h3><a class="small" href="#/fp-trang">Mọi Trang</a></div>';
        h += top.length ? '<div class="dd-ds">' + top.slice(0, 6).map(function (t) {
          return '<div class="dd-dong">' + FP.avTrang(t) + '<span class="grow" style="min-width:0"><b class="clip" style="display:block">' + esc(t.ten) + '</b><span class="tiny muted">' + FP.so(t.da_dang) +
            " bài · " + FP.so(t.tuong_tac) + " tương tác</span></span></div>";
        }).join("") + "</div>" : DS.rong("Chưa có Trang nào", '<a href="#/fp-trang">Đồng bộ Trang</a> để bắt đầu.', "list");
        h += "</div></div>";

        h += '<div class="card card-x mt"><div class="card-h"><h3>Hoạt động gần đây</h3><a class="small" href="#/fp-bai">Bài đăng</a></div>';
        h += hd.length ? '<div class="tw"><table class="tbl"><thead><tr><th>Lúc</th><th>Việc</th><th>Kết quả</th><th>Chi tiết</th></tr></thead><tbody>' + hd.slice(0, 20).map(function (x) {
          var k = x.ket_qua === "ok" || x.ket_qua === "thanh_cong" ? DS.bd("Xong", "ok") : x.ket_qua === "loi" ? DS.bd("Lỗi", "err") : DS.bd(x.ket_qua || "Thông tin", "mu");
          return '<tr><td class="nw small" title="' + esc(DS.gioDu(x.luc)) + '">' + esc(DS.tuongDoi(x.luc)) + '</td><td class="nw">' + esc(x.loai || "") + "</td><td>" + k +
            '</td><td class="small" style="min-width:240px">' + esc(x.chi_tiet || "") + "</td></tr>";
        }).join("") + "</tbody></table></div>" : DS.rong("Chưa có hoạt động", "", "list");
        h += "</div>";
        el.innerHTML = h;

        var c = el.querySelector("#fp-tq-ch");
        if (c) {
          var ve2 = function () { c.innerHTML = FP.cot(xh, "da_dang", { w: c.clientWidth, h: 180, nhan: "Bài đã đăng mỗi ngày" }); };
          ve2();
          FP.ganTip(c, xh, function (x) { return "<b>" + esc(FP.ngayNgan(x.ngay)) + "</b><br>Đã đăng: " + FP.so(x.da_dang) + "<br>Tiếp cận: " + FP.so(x.tiep_can); });
          var rw = function () { if (!ctx.alive) { window.removeEventListener("resize", rw); return; } if (c.isConnected) ve2(); };
          window.addEventListener("resize", rw);
        }
      }
      DS.bind(el, {
        "tai-lai": nap,
        "cai-dat": moCaiDat,
        "fp-chay-lai": function () { FP.datDung(false).then(function (v) { if (v === false) nap(); }); }
      });
      ctx.every(nap, 60000);
      return nap();
    }
  });
})();
