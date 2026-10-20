/* Máy ở nhà - #/may : ghép máy, tải Worker, trạng thái GPM, mẫu máy hỗ trợ, Up bài từ Google Sheet, đăng thử */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;

  function theUpBai(u) {
    var c = (u && u.cau_hinh) || {}, lc = (u && u.lan_cuoi) || {};
    var h = '<div class="card"><div class="card-h"><h3>' + ic("file") + 'Up bài từ Google Sheet</h3><button class="btn btn-sm btn-soft" data-act="ub-chay">' + ic("play") + "Chạy ngay</button></div>" +
      '<p class="small muted" style="margin:0 0 12px">Mỗi dòng ở tab HÀNG ĐỢI UP BÀI: Tên Page, Page ID, Link video (TikTok, Facebook, Instagram...), Giá, Mã. MinMin tự tải video, AI nhận diện đồ và viết nội dung, gửi Telegram để bạn duyệt, rồi đăng Reels đúng giờ theo tab CẤU HÌNH PAGE.</p>' +
      '<div class="fld"><label for="ub-sheet">Link Google Sheet UP BÀI</label><input class="inp" id="ub-sheet" placeholder="https://docs.google.com/spreadsheets/d/..." value="' +
      esc(c.sheet_id ? "https://docs.google.com/spreadsheets/d/" + c.sheet_id + "/edit" : "") + '"></div>' +
      '<div class="grid g2 mt-s" style="gap:8px"><div class="swrow"><label for="ub-bat" style="font-weight:500">Tự chạy 5 phút một lần</label>' + DS.sw('id="ub-bat"', !!c.bat) + "</div>" +
      '<div class="swrow"><label for="ub-tu" style="font-weight:500">Tự duyệt (đăng không cần bấm Duyệt)</label>' + DS.sw('id="ub-tu"', !!c.tu_duyet) + "</div></div>" +
      '<div class="row mt-s" style="justify-content:flex-end"><button class="btn btn-pri btn-sm" data-act="ub-luu">Lưu</button></div>';
    if (lc.luc) h += '<div class="note mt-s">' + ic("info") + "<span>Lượt gần nhất " + esc(lc.luc) + ": xử lý " + (lc.xu_ly || 0) + " dòng, đăng " + (lc.dang || 0) + " bài" +
      ((lc.cho || []).length ? ". Chờ: " + esc(lc.cho.join("; ")) : "") + (lc.loi ? '. <b style="color:var(--err)">Lỗi: ' + esc(lc.loi) + "</b>" : "") + "</span></div>";
    if ((u.nhat_ky || []).length) h += '<details class="mt-s"><summary class="small muted" style="cursor:pointer">Nhật ký Up bài</summary><div class="logbox mt-s">' + u.nhat_ky.map(esc).join("\n") + "</div></details>";
    return h + "</div>";
  }

  DS.view("may", {
    title: "Máy ở nhà",
    render: function (el, ctx) {
      el.innerHTML = DS.ph("Máy ở nhà", "Máy Windows chạy GPM Login và MinMin Worker. Máy nhận việc từ đây, mở profile và làm như người thật.",
        '<a class="btn" href="/doi-social/tai-worker.zip">' + ic("download") + 'Tải MinMin Worker</a><button class="btn btn-pri" data-act="ma">' + ic("link") + "Tạo mã ghép</button>") +
        '<div id="may-ma"></div>' + DS.skel(6);
      var D = {}, KB = null, maGhep = "";

      function nap() {
        return Promise.all([DS.api("GET", "/doi-social/trang-thai"), DS.api("GET", "/up-bai/trang-thai", null, { quiet: true }), DS.layKichBan()]).then(function (a) {
          if (!ctx.alive) return;
          if (a[0].ok === false) { el.innerHTML = DS.ph("Máy ở nhà", "") + DS.loiThe(a[0].error, true); return; }
          D = a[0]; D.up_bai = a[1].ok === false ? null : a[1]; KB = a[2];
          ve();
        });
      }
      function ve() {
        var may = D.may || [], viec = D.viec || [], gh = D.gioi_han || {}, nick = D.nick || [], mau = DS.mauTheoId(KB);
        var foc = document.activeElement && el.contains(document.activeElement) ? document.activeElement.id : "";
        var h = DS.ph("Máy ở nhà", "Máy Windows chạy GPM Login và MinMin Worker. Máy nhận việc từ đây, mở profile và làm như người thật.",
          '<a class="btn" href="/doi-social/tai-worker.zip">' + ic("download") + 'Tải MinMin Worker</a><button class="btn btn-pri" data-act="ma">' + ic("link") + "Tạo mã ghép</button>");
        h += '<div id="may-ma">' + (maGhep || "") + "</div>";
        if (!may.length) h += '<div class="card mb"><div class="card-h"><h3>Bắt đầu trong 3 bước</h3></div><div class="steps-h">' +
          '<div><span class="n">1</span><div><b>Tải Worker</b><div class="small muted">Về máy Windows đang cài GPM Login, giải nén.</div></div></div>' +
          '<div><span class="n">2</span><div><b>Chạy cai-dat.bat</b><div class="small muted">Cài Python và trình duyệt tự động, chỉ làm một lần.</div></div></div>' +
          '<div><span class="n">3</span><div><b>Chạy ghep-may.bat</b><div class="small muted">Nhập mã 6 số từ nút Tạo mã ghép ở trên.</div></div></div></div></div>';

        h += '<div class="card"><div class="card-h"><h3>' + ic("monitor") + "Máy đã ghép <span class=\"sub\">" + may.length + " máy · " + nick.length + " nick</span></h3></div>";
        if (!may.length) h += DS.rong("Chưa có máy nào", "Làm 3 bước ở trên để ghép máy đầu tiên.", "robot");
        h += may.map(function (m) {
          var kb = m.kich_ban || [];
          if (typeof kb === "string") { try { kb = JSON.parse(kb); } catch (e) { kb = []; } }
          return '<div class="machine"><span class="mi">' + ic("monitor") + '</span><div class="grow" style="min-width:0"><div class="row"><b style="font-size:14px">' + esc(m.ten) + "</b>" +
            (m.online ? DS.bd("Đang bật", "ok", true) : DS.bd("Ngoại tuyến", "mu", true)) + (m.driver_ok ? DS.bd("GPM sẵn sàng", "ok") : DS.bd("GPM chưa sẵn sàng", "warn")) + "</div>" +
            '<div class="small muted" style="margin-top:3px">' + (m.so_nick || 0) + " nick · Worker " + esc(m.phien_ban || "?") + (m.song_song ? " · song song " + m.song_song : "") +
            " · nhịp cuối " + (m.nhip_luc ? DS.tuongDoi(m.nhip_luc) : "chưa có") + "</div>" +
            (m.loi_driver ? '<div class="small" style="color:var(--err);margin-top:3px">' + esc(m.loi_driver) + "</div>" : "") +
            '<details style="margin-top:8px"><summary class="small" style="cursor:pointer;color:var(--brand-ink)">Mẫu máy hỗ trợ: ' + kb.length + " mẫu</summary>" +
            (kb.length ? '<div class="row mt-s" style="gap:4px">' + kb.map(function (id) { var x = mau[id]; return '<span class="bd bd-out" style="padding-left:3px">' + DS.icNT(x ? x.nen_tang : "", 16) + esc(x ? x.ten : id) + "</span>"; }).join("") + "</div>" :
              '<div class="small muted mt-s">Worker này chưa báo mẫu nào (bản cũ chỉ làm được Đăng bài Facebook). Cập nhật Worker để dùng các mẫu mới.</div>') + "</details></div>" +
            '<button class="btn btn-sm btn-dan" data-act="go" data-id="' + esc(m.id) + '">' + ic("trash") + "Gỡ máy</button></div>";
        }).join("");
        h += "</div>";

        h += '<div class="grid g2 mt"><div>' + (D.up_bai ? theUpBai(D.up_bai) : '<div class="card"><div class="card-h"><h3>' + ic("file") + "Up bài từ Google Sheet</h3></div>" + '<div class="small muted">Chức năng Up bài chưa bật trên máy chủ này.</div></div>') + "</div>";
        h += '<div><div class="card"><div class="card-h"><h3>' + ic("send") + 'Đăng thử một bài</h3></div><p class="small muted" style="margin:0 0 12px">Thường chỉ cần nhắn Telegram cho MinMin. Form này để thử nhanh một bài Facebook.</p>' +
          '<div class="fld"><label for="f-nick">Nick (tên profile GPM)</label><input class="inp" id="f-nick" list="ds-nick" placeholder="Gõ để chọn"><datalist id="ds-nick">' +
          nick.filter(function (n) { return n.trinh_duyet !== "firefox"; }).map(function (n) { return '<option value="' + esc(n.ten) + '">'; }).join("") + "</datalist></div>" +
          '<div class="fld"><label for="f-noi">Nơi đăng</label><input class="inp" id="f-noi" placeholder="Link Trang hoặc nhóm; để trống là tường của nick"></div>' +
          '<div class="fld"><label for="f-nd">Nội dung</label><textarea class="ta" id="f-nd" rows="4"></textarea></div>' +
          '<div class="row mt-s" style="justify-content:flex-end"><button class="btn btn-pri btn-sm" data-act="dang-thu">Tạo bài (chờ duyệt)</button></div></div>' +
          '<div class="card"><div class="card-h"><h3>' + ic("gauge") + 'Giới hạn đăng thử</h3><a class="small" href="#/gioi-han">Giới hạn nick đầy đủ</a></div><div class="fgrid">' +
          '<div class="fld"><label for="g-bai">Bài tối đa mỗi nick mỗi ngày</label><input class="inp" id="g-bai" type="number" min="1" max="50" value="' + (gh.bai_moi_ngay || 5) + '"></div>' +
          '<div class="fld"><label for="g-nghi">Nghỉ giữa hai lượt (phút)</label><input class="inp" id="g-nghi" type="number" min="0" value="' + (gh.nghi_phut != null ? gh.nghi_phut : 20) + '"></div></div>' +
          '<div class="hint mt-s">Chỉ áp cho việc Đăng thử kiểu cũ. Các mẫu Automation dùng Giới hạn nick.</div><div class="row mt-s" style="justify-content:flex-end"><button class="btn btn-sm" data-act="g-luu">Lưu</button></div></div></div></div>';

        h += '<div class="card card-x mt"><div class="card-h"><h3>Việc gần đây</h3><a class="small" href="#/nhat-ky?tab=lich-su">Lịch sử đầy đủ</a></div><div style="height:12px"></div>';
        if (!viec.length) h += DS.rong("Chưa có việc nào", "", "list");
        else h += '<div class="tw"><table class="tbl tbl-in"><thead><tr><th>#</th><th>Việc</th><th>Nick</th><th>Trạng thái</th><th>Tạo lúc</th><th></th></tr></thead><tbody>' + viec.slice(0, 15).map(function (v) {
          var ts = v.tham_so || {}, m = mau[v.ky_nang] || {};
          return '<tr><td class="small muted">#' + v.id + '</td><td style="max-width:320px"><div class="b" style="font-weight:500">' + esc(v.nhan_ky_nang || m.ten || v.ky_nang) + "</div>" +
            (ts.noi_dung ? '<div class="sub clamp1">' + esc(ts.noi_dung) + "</div>" : "") + (v.thong_diep ? '<div class="sub clamp1">Máy báo: ' + esc(v.thong_diep) + "</div>" : "") + "</td><td>" + esc(v.nick_ten || "") + "</td><td>" +
            DS.ttViec(v) + '</td><td class="small nw">' + DS.gio(v.tao_luc) + '</td><td class="nw">' +
            (v.trang_thai === "cho_duyet" ? '<button class="btn btn-xs btn-ok" data-act="duyet-viec" data-id="' + v.id + '">Duyệt đăng</button> <button class="btn btn-xs" data-act="bo-viec" data-id="' + v.id + '">Bỏ</button>' :
              '<button class="btn btn-xs" data-act="xem-viec" data-id="' + v.id + '">' + ic("eye") + "Xem</button>") + "</td></tr>";
        }).join("") + "</tbody></table></div>";
        h += "</div>";
        el.innerHTML = h;
        if (foc) { var f = el.querySelector("#" + foc); if (f) f.focus(); }
      }
      function viecTheoId(id) { return (D.viec || []).filter(function (v) { return String(v.id) === String(id); })[0]; }
      DS.bind(el, {
        "tai-lai": nap,
        "ma": function (b) {
          b.disabled = true;
          DS.api("POST", "/doi-social/ma-ghep", {}).then(function (d) {
            b.disabled = false;
            if (d.ok === false) return;
            maGhep = '<div class="card mb" style="border-color:#d6c8fb"><div class="row-sb"><div><div class="small muted">Mã ghép, sống ' + esc(d.song_phut || 15) + ' phút</div><div class="code" style="margin-top:6px">' + esc(d.ma) +
              '</div></div><div class="small" style="max-width:420px">Trên máy ở nhà, chạy <b>ghep-may.bat</b>, nhập mã này và địa chỉ MinMin:<div class="row mt-s"><code class="bd bd-out" style="height:auto;padding:4px 8px">' +
              esc(location.origin) + '</code><button class="btn btn-xs" data-act="chep-goc">' + ic("copy") + "Chép</button></div></div></div></div>";
            var box = el.querySelector("#may-ma"); if (box) box.innerHTML = maGhep;
          });
        },
        "chep-goc": function () { DS.chepChu(location.origin).then(function (ok) { DS.toast(ok ? "Đã chép địa chỉ" : location.origin, ok ? "ok" : "info"); }); },
        "go": function (t) {
          DS.xacNhan("Gỡ máy này? Worker trên máy đó sẽ phải ghép lại, nick của máy biến khỏi danh sách.", "Gỡ máy", true).then(function (ok) {
            if (ok) DS.api("DELETE", "/doi-social/may/" + encodeURIComponent(t.getAttribute("data-id"))).then(function (d) { if (d.ok !== false) { DS.toast("Đã gỡ máy", "ok"); DS.boNho("nick"); nap(); } });
          });
        },
        "ub-luu": function () {
          DS.api("POST", "/up-bai/cau-hinh", { sheet: el.querySelector("#ub-sheet").value, bat: el.querySelector("#ub-bat").checked, tu_duyet: el.querySelector("#ub-tu").checked })
            .then(function (d) { if (d.ok !== false) { DS.toast("Đã lưu", "ok"); nap(); } });
        },
        "ub-chay": function (b) {
          b.disabled = true; DS.toast("Đang chạy một lượt Sheet, tải video và AI viết bài có thể mất vài phút...", "info");
          DS.api("POST", "/up-bai/chay", {}).then(function (d) {
            b.disabled = false;
            if (d.ok === false) return;
            var k = d.ket_qua || {};
            DS.toast(k.loi ? k.loi : (k.bo_qua || ("Xử lý " + (k.xu_ly || 0) + " dòng, đăng " + (k.dang || 0) + " bài")), k.loi ? "err" : "ok"); nap();
          });
        },
        "dang-thu": function (b) {
          var nk = el.querySelector("#f-nick").value.trim(), nd = el.querySelector("#f-nd").value.trim();
          if (!nk || !nd) { DS.toast("Cần nick và nội dung", "err"); return; }
          b.disabled = true;
          DS.api("POST", "/doi-social/viec", { nick: nk, noi_dang: el.querySelector("#f-noi").value.trim(), noi_dung: nd }).then(function (d) {
            b.disabled = false;
            if (d.ok === false) return;
            DS.toast("Đã tạo bài #" + ((d.viec && d.viec.id) || "") + ", chờ duyệt ở Việc gần đây", "ok"); nap();
          });
        },
        "duyet-viec": function (t) { duyetViec(t.getAttribute("data-id"), true); },
        "bo-viec": function (t) { duyetViec(t.getAttribute("data-id"), false); },
        "xem-viec": function (t) {
          var v = viecTheoId(t.getAttribute("data-id")); if (!v) return;
          DS.modal({ title: "Việc #" + v.id + " · " + (v.nick_ten || ""), wide: true, body: '<div class="row">' + DS.ttViec(v) + '<span class="small muted">' + DS.gioDu(v.tao_luc) + "</span></div>" +
            ((v.tham_so || {}).noi_dung ? '<div class="body-txt">' + esc(v.tham_so.noi_dung) + "</div>" : "") + (v.thong_diep ? '<div class="note mt-s">' + ic("info") + "<span>" + esc(v.thong_diep) + "</span></div>" : "") +
            ((v.buoc || []).length ? '<div class="logbox mt-s">' + v.buoc.map(esc).join("\n") + "</div>" : "") +
            (v.co_anh ? '<img class="shot" loading="lazy" src="/doi-social/anh/' + encodeURIComponent(v.id) + '.png" alt="Ảnh chụp kết quả">' : "") });
        },
        "g-luu": function () {
          DS.api("POST", "/doi-social/gioi-han", { bai_moi_ngay: +el.querySelector("#g-bai").value, nghi_phut: +el.querySelector("#g-nghi").value })
            .then(function (d) { if (d.ok !== false) { DS.toast("Đã lưu", "ok"); nap(); } });
        }
      });
      DS.bind(el, {}, "change");
      function duyetViec(id, dy) {
        DS.api("POST", "/doi-social/viec/" + id + "/duyet", { dong_y: dy }).then(function (d) { if (d.ok !== false) { DS.toast(dy ? "Đã duyệt, máy ở nhà sẽ đăng" : "Đã bỏ", "ok"); nap(); } });
      }
      ctx.every(function () {
        var a = document.activeElement;
        if (a && el.contains(a) && a.matches("input,textarea,select")) return;
        nap();
      }, 15000);
      return nap();
    }
  });
})();
