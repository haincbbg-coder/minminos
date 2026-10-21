/* Fanpage (API) - Cảnh báo lỗi - #/fp-canh-bao (tab Đang có · Lịch sử) */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic, FP = DS.fp;
  var NHOM = [
    ["chan", "Chặn đứng", "Đang làm Trang không đăng được. Sửa trước tiên."],
    ["nang", "Nặng", "Có bài lỗi hoặc sắp hỏng, nên sửa trong hôm nay."],
    ["nhac", "Nhắc", "Chưa hỏng gì, nhưng nên xem qua."]
  ];
  // chỉ cho đường dẫn trong app (#/...) hoặc trang khác của MinMin (/...), không cho link ngoài
  function toiAnToan(t) { t = String(t || ""); return /^#\//.test(t) || /^\/(?!\/)/.test(t) ? t : ""; }

  function mucCb(x) {
    var toi = toiAnToan(x.toi);
    return '<div class="fp-cb ' + esc(x.muc || "nhac") + '"><div class="fp-cb-h"><span class="fp-cb-ic">' + ic(x.muc === "nhac" ? "info" : "alert") + '</span><div class="grow" style="min-width:0"><b>' + esc(x.tieu_de || x.ma || "") + "</b>" +
      (x.doi_tuong ? '<div class="tiny muted">' + esc(x.doi_tuong) + "</div>" : "") + "</div>" + (x.luc ? '<span class="tiny muted nw" title="' + esc(DS.gioDu(x.luc)) + '">' + esc(DS.tuongDoi(x.luc)) + "</span>" : "") + "</div>" +
      (x.chi_tiet ? '<div class="small" style="margin-top:6px">' + esc(x.chi_tiet) + "</div>" : "") +
      (x.cach_sua ? '<div class="fp-cb-sua"><b>Cách sửa:</b> ' + esc(x.cach_sua) + "</div>" : "") +
      (toi ? '<div class="row" style="justify-content:flex-end;margin-top:8px"><a class="btn btn-sm" href="' + esc(toi) + '">' + ic("chevr") + "Tới chỗ sửa</a></div>" : "") + "</div>";
  }

  function tabHienTai(el, ctx) {
    var body = el.querySelector("#cb-body");
    body.innerHTML = DS.skel(5, 3);
    function nap() {
      return FP.api("GET", "/canh-bao").then(function (d) {
        if (!ctx.alive) return;
        if (d.ok === false) { body.innerHTML = DS.loiThe(d.error, true); return; }
        var ds = DS.list(d), dem = d.dem || {};
        if (!d.dem) ds.forEach(function (x) { dem[x.muc] = (dem[x.muc] || 0) + 1; });
        var h = '<div class="grid g3">' + NHOM.map(function (n) {
          return '<div class="stat fp-cb-so ' + n[0] + '"><div class="k"><span class="ico">' + ic(n[0] === "nhac" ? "info" : "alert") + "</span>" + esc(n[1]) + '</div><div class="v">' + FP.so(dem[n[0]]) + '</div><div class="s">' + esc(n[2]) + "</div></div>";
        }).join("") + "</div>";
        h += '<div class="small muted mt">' + (d.kiem_luc ? "Kiểm lần cuối " + esc(DS.tuongDoi(d.kiem_luc)) + ". " : "") + "MinMin tự kiểm 10 phút một lần.</div>";
        if (!ds.length) h += '<div class="card mt">' + DS.rong("Mọi thứ đang ổn", "Không có lỗi hay cảnh báo nào cho Fanpage.", "done") + "</div>";
        else NHOM.forEach(function (n) {
          var l = ds.filter(function (x) { return (x.muc || "nhac") === n[0]; });
          if (!l.length) return;
          h += '<div class="grp-t">' + esc(n[1]) + " (" + l.length + ')</div><div class="fp-cb-ds">' + l.map(mucCb).join("") + "</div>";
        });
        body.innerHTML = h;
        DS.capNhatHuyHieu();
      });
    }
    DS.bind(el, {
      "tai-lai": nap,
      "kiem": function (b) {
        b.disabled = true;
        FP.api("POST", "/canh-bao/kiem", {}).then(function (d) { b.disabled = false; if (d.ok !== false) { DS.toast("Đã kiểm tra lại", "ok"); nap(); } });
      }
    });
    ctx.every(nap, 60000);
    return nap();
  }

  function tabLichSu(el, ctx) {
    var body = el.querySelector("#cb-body");
    body.innerHTML = DS.skel(6);
    DS.bind(el, { "tai-lai": function () { nap(); }, "kiem": function () { DS.go("fp-canh-bao"); } });
    function nap() {
      return FP.api("GET", "/canh-bao/lich-su").then(function (d) {
        if (!ctx.alive) return;
        if (d.ok === false) { body.innerHTML = DS.loiThe(d.error, true); return; }
        var ds = DS.list(d);
        if (!ds.length) { body.innerHTML = '<div class="card">' + DS.rong("Chưa có lịch sử", "Cảnh báo nào từng xuất hiện rồi hết sẽ được ghi ở đây.", "list") + "</div>"; return; }
        body.innerHTML = '<div class="card card-x"><div class="tw" style="border-top:0"><table class="tbl tbl-in"><thead><tr><th>Mức</th><th>Cảnh báo</th><th>Xuất hiện</th><th>Hết lúc</th><th>Chi tiết</th></tr></thead><tbody>' +
          ds.map(function (x) {
            return "<tr><td>" + DS.bdMap(FP.MUC_CB, x.muc) + "</td><td><b>" + esc(x.tieu_de || x.ma || "") + '</b><div class="sub">' + esc(x.doi_tuong || "") + '</div></td><td class="small nw">' + esc(DS.gio(x.luc)) +
              '</td><td class="small nw">' + (x.het_luc ? esc(DS.gio(x.het_luc)) : DS.bd("Còn", "warn")) + '</td><td class="small" style="min-width:240px">' + esc(x.chi_tiet || "") + "</td></tr>";
          }).join("") + "</tbody></table></div></div>";
      });
    }
    return nap();
  }

  DS.view("fp-canh-bao", {
    title: "Cảnh báo Fanpage",
    render: function (el, ctx) {
      var tab = ctx.q.tab === "lich-su" ? "lich-su" : "hien-tai";
      el.innerHTML = DS.ph("Cảnh báo lỗi", "MinMin tự soát token, quyền, bài lỗi, kho trống, kênh nguồn. Mỗi mục có cách sửa và nút tới đúng chỗ.",
        '<a class="btn" href="' + FP.GOC + '/canh-bao/xuat" target="_blank" rel="noopener" title="Bản chẩn đoán dạng chữ để gửi người hỗ trợ, không có token">' + ic("download") + "Xuất chẩn đoán</a>" +
        '<button class="btn btn-pri" data-act="kiem">' + ic("refresh") + "Kiểm tra ngay</button>") +
        DS.tabs([{ id: "hien-tai", ten: "Đang có" }, { id: "lich-su", ten: "Lịch sử" }], tab, "#/fp-canh-bao?tab=") + '<div id="cb-body" class="stack"></div>';
      return tab === "lich-su" ? tabLichSu(el, ctx) : tabHienTai(el, ctx);
    }
  });
})();
