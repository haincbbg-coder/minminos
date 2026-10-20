/* Chạy hàng loạt - #/chay-hang-loat?mau=<id> : tạo đợt chạy hoặc lịch hẹn cho nhiều nick */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;

  function truong(f, gt, kt) {
    var k = f.key, v = gt[k] !== undefined ? gt[k] : f.mac_dinh, id = "ts-" + k;
    var nhan = '<label for="' + id + '">' + esc(f.nhan) + (f.bat_buoc ? ' <span class="req">*</span>' : "") + "</label>";
    var goiY = f.goi_y ? '<div class="hint">' + esc(f.goi_y) + "</div>" : "";
    switch (f.kieu) {
      case "so":
        return '<div class="fld">' + nhan + '<input class="inp" type="number" id="' + id + '" data-ts="' + k + '" data-kieu="so"' +
          (f.min != null ? ' min="' + f.min + '"' : "") + (f.max != null ? ' max="' + f.max + '"' : "") + ' value="' + esc(v != null ? v : "") + '">' +
          (f.min != null && f.max != null ? '<div class="hint">Từ ' + f.min + " đến " + f.max + (f.goi_y ? ". " + esc(f.goi_y) : "") + "</div>" : goiY) + "</div>";
      case "chu":
        return '<div class="fld">' + nhan + '<input class="inp" id="' + id + '" data-ts="' + k + '" value="' + esc(v || "") + '" placeholder="' + esc(f.goi_y || "") + '"></div>';
      case "doan":
        return '<div class="fld full">' + nhan + '<textarea class="ta" rows="4" id="' + id + '" data-ts="' + k + '" placeholder="' + esc(f.goi_y || "") + '">' + esc(v || "") + "</textarea>" + "</div>";
      case "ds_link":
        return '<div class="fld full">' + nhan + '<textarea class="ta" rows="4" id="' + id + '" data-ts="' + k + '" data-kieu="ds_link" placeholder="https://...&#10;https://...">' +
          esc(Array.isArray(v) ? v.join("\n") : (v || "")) + '</textarea><div class="hint">Mỗi dòng một link, bắt đầu bằng https://</div></div>';
      case "bat":
        return '<div class="swrow"><label for="' + id + '" style="font-weight:500">' + esc(f.nhan) + "</label>" + DS.sw('id="' + id + '" data-ts="' + k + '" data-kieu="bat"', v !== false && v != null ? !!v : false) + "</div>";
      case "chon":
      case "kho":
        var ds = f.lua_chon || [];
        if (k === "che_do" || f.kieu === "kho" || ds.length <= 3) {
          return '<div class="fld full">' + nhan + '<div class="seg" data-seg="' + k + '">' + ds.map(function (x) {
            return '<button type="button" data-v="' + esc(x[0]) + '" class="' + (String(v) === String(x[0]) ? "on" : "") + '">' + esc(x[1]) + "</button>";
          }).join("") + "</div>" + (k === "che_do" ? '<div class="hint" id="cd-hint"></div>' : "") + "</div>";
        }
        return '<div class="fld">' + nhan + '<select class="sel" id="' + id + '" data-ts="' + k + '">' + ds.map(function (x) {
          return '<option value="' + esc(x[0]) + '"' + (String(v) === String(x[0]) ? " selected" : "") + ">" + esc(x[1]) + "</option>";
        }).join("") + "</select></div>";
      case "san_pham":
        var loai = f.loai || "san_pham";
        var opt = kt.filter(function (x) { return loai === "ca_hai" || (x.loai || "san_pham") === loai; });
        return '<div class="fld">' + nhan + '<select class="sel" id="' + id + '" data-ts="' + k + '"><option value="">' + (f.bat_buoc ? "Chọn một mục" : "Không chọn (AI tự nhận ra)") + "</option>" +
          opt.map(function (x) {
            return '<option value="' + esc(x.id) + '"' + (String(v) === String(x.id) ? " selected" : "") + ">" + esc(x.ten) + (x.loai === "chu_de" ? " (chủ đề)" : "") + "</option>";
          }).join("") + "</select>" + (opt.length ? "" : '<div class="hint">Chưa có mục nào. <a href="#/kien-thuc">Thêm ở Kiến thức cho Agent</a></div>') + "</div>";
    }
    return "";
  }

  var GOI_Y_CHE_DO = {
    chay_thu: "Agent chỉ đọc và viết nháp vào Duyệt nội dung, không đăng hay bấm gì công khai.",
    duyet_truoc: "AI viết nháp, bạn bấm Duyệt thì máy ở nhà mới đăng.",
    dang_luon: "AI viết xong đăng ngay. Bạn tự chịu trách nhiệm nội dung."
  };

  DS.view("chay-hang-loat", {
    title: "Chạy hàng loạt",
    render: function (el, ctx) {
      el.innerHTML = '<a class="back" href="#/automation">' + ic("back") + "Automation</a>" + DS.ph("Chạy hàng loạt", "Giao một mẫu việc cho nhiều nick. Máy ở nhà mở từng profile GPM và làm như người thật.") + DS.skel(8);
      var S = { mau: ctx.q.mau || "", chon: {}, tim: "", locNhan: true, chuaNhan: true, thuMuc: "", ts: {}, ten: "", song_song: 1, chay_an: false,
        che_do: "ngay", lich: { kieu: "ngay", gio: "08:00", n: 2, cron: "0 8 * * *" } };
      var KB, NICK = [], KT = [], MAU = [];

      Promise.all([DS.layKichBan(), DS.layNick(true), DS.layKienThuc()]).then(function (a) {
        if (!ctx.alive) return;
        KB = a[0];
        if (KB.ok === false) { el.innerHTML = DS.loiThe(KB.error); return; }
        MAU = DS.dsMau(KB);
        NICK = DS.list(a[1], "nick");
        KT = DS.list(a[2], "kien_thuc");
        if (!S.mau || !MAU.some(function (m) { return m.id === S.mau; })) S.mau = "";
        veKhung();
      });

      function mau() { for (var i = 0; i < MAU.length; i++) if (MAU[i].id === S.mau) return MAU[i]; return null; }
      function khop() {
        var m = mau(), t = S.tim.trim().toLowerCase();
        return NICK.filter(function (n) {
          if (S.thuMuc && (n.nhom || "") !== S.thuMuc) return false;
          if (t && (n.ten + " " + (n.nhom || "") + " " + (n.may_ten || "")).toLowerCase().indexOf(t) < 0) return false;
          if (m && S.locNhan) {
            var nh = n.nhan || [];
            if (nh.indexOf(m.nen_tang) < 0 && !(S.chuaNhan && !nh.length)) return false;
          }
          return true;
        });
      }
      function soChon() { return Object.keys(S.chon).filter(function (k) { return S.chon[k]; }).length; }

      function veKhung() {
        var nhomNT = {};
        MAU.forEach(function (m) { (nhomNT[m.nen_tang] = nhomNT[m.nen_tang] || []).push(m); });
        var thuMuc = {};
        NICK.forEach(function (n) { if (n.nhom) thuMuc[n.nhom] = 1; });
        var h = '<a class="back" href="#/automation">' + ic("back") + "Automation</a>" + DS.ph("Chạy hàng loạt", "Giao một mẫu việc cho nhiều nick. Máy ở nhà mở từng profile GPM và làm như người thật.") +
          '<div class="card" id="chl"><div class="sec"><div class="sec-t">Thông tin chung</div><div class="fgrid">' +
          '<div class="fld"><label for="chl-ten">Tên đợt</label><input class="inp" id="chl-ten" value="' + esc(S.ten) + '" placeholder="Để trống, MinMin tự đặt theo mẫu và giờ chạy"></div>' +
          '<div class="fld"><label for="chl-mau">Mẫu <span class="req">*</span></label><select class="sel" id="chl-mau"><option value="">Chọn mẫu việc</option>' +
          DS.NT_THU_TU.concat(Object.keys(nhomNT).filter(function (x) { return DS.NT_THU_TU.indexOf(x) < 0; })).map(function (nt) {
            if (!nhomNT[nt]) return "";
            return '<optgroup label="' + esc(DS.tenNT(nt)) + '">' + nhomNT[nt].map(function (m) {
              return '<option value="' + esc(m.id) + '"' + (m.id === S.mau ? " selected" : "") + ">" + esc(m.ten) + (m.san_sang === false ? " (máy chưa hỗ trợ)" : "") + "</option>";
            }).join("") + "</optgroup>";
          }).join("") + "</select></div></div><div id=\"chl-mau-info\"></div></div>" +
          '<div class="sec"><div class="sec-t">Nick chạy <span class="bd bd-brand" id="chl-dem"></span></div><div class="nick-box"><div class="nick-tools">' +
          '<div class="inp-ic grow" style="min-width:180px">' + ic("search") + '<input class="inp inp-sm" id="chl-tim" placeholder="Tìm nick, thư mục, máy" value="' + esc(S.tim) + '"></div>' +
          '<select class="sel sel-sm" id="chl-tm" style="width:auto"><option value="">Mọi thư mục GPM</option>' + Object.keys(thuMuc).sort().map(function (t) {
            return '<option' + (t === S.thuMuc ? " selected" : "") + ">" + esc(t) + "</option>";
          }).join("") + "</select>" +
          '<button class="btn btn-sm" type="button" data-act="chon-het" id="chl-chon-het">Chọn tất cả khớp</button><button class="btn btn-sm btn-ghost" type="button" data-act="bo-chon">Bỏ chọn</button></div>' +
          '<div class="nick-tools" style="padding-top:8px;padding-bottom:8px" id="chl-loc-nhan"></div>' +
          '<div class="nick-list" id="chl-nick"></div></div></div>' +
          '<div class="sec" id="chl-ts-sec"><div class="sec-t">Tham số riêng của mẫu</div><div id="chl-ts"></div></div>' +
          '<div class="sec"><div class="sec-t">Cách chạy</div><div class="fgrid"><div class="fld"><label>Chạy song song mỗi máy</label><div class="seg" data-seg="_song">' +
          [1, 2, 3].map(function (n) { return '<button type="button" data-v="' + n + '" class="' + (S.song_song === n ? "on" : "") + '">' + n + " nick</button>"; }).join("") +
          '</div><div class="hint">Mỗi nick một cửa sổ. Máy yếu nên để 1.</div></div>' +
          '<div class="fld"><label>Tuỳ chọn</label><div class="swrow"><label for="chl-an" style="font-weight:500">Chạy ẩn (không hiện cửa sổ trình duyệt)</label>' + DS.sw('id="chl-an"', S.chay_an) + "</div></div></div>" +
          '<div class="fld" style="margin-top:14px"><label>Chế độ</label><div class="seg" data-seg="_chedo"><button type="button" data-v="ngay" class="' + (S.che_do === "ngay" ? "on" : "") + '">' + ic("play") +
          ' Chạy ngay</button><button type="button" data-v="hen" class="' + (S.che_do === "hen" ? "on" : "") + '">' + ic("calendar") + " Hẹn lịch</button></div></div>" +
          '<div id="chl-lich"></div></div>' +
          '<div class="sticky-act"><a class="btn" href="#/automation">Huỷ</a><button class="btn btn-pri btn-lg" type="button" data-act="bat-dau" id="chl-go"></button></div></div>';
        el.innerHTML = h;
        veMau(); veNick(); veThamSo(); veLich();
      }

      function veMau() {
        var m = mau(), box = el.querySelector("#chl-mau-info");
        if (!m) { box.innerHTML = '<div class="note mt-s">' + ic("info") + '<span>Chọn một mẫu, hoặc <a href="#/automation">xem danh sách mẫu</a> kèm mô tả.</span></div>'; return; }
        var h = '<div class="row mt-s" style="align-items:flex-start;flex-wrap:nowrap;gap:12px;padding:12px;border:1px solid var(--line);border-radius:12px">' + DS.icNT(m.nen_tang, 34) +
          '<div class="grow"><div class="b">' + esc(m.ten) + '</div><div class="small muted">' + esc(m.mo_ta) + "</div>" + (m.chi_tiet ? '<div class="tiny muted" style="margin-top:4px">' + esc(m.chi_tiet) + "</div>" : "") +
          '<div class="row mt-s">' + (m.hanh_dong || []).map(function (k) { return DS.bd(DS.tenHD(KB, k), "out"); }).join("") + "</div></div></div>";
        if (m.san_sang === false) h += '<div class="note note-warn mt-s">' + ic("alert") + "<span><b>Máy ở nhà chưa hỗ trợ mẫu này.</b> Bạn vẫn tạo được đợt, nhưng việc sẽ nằm chờ tới khi Worker trên máy ở nhà được cập nhật có mẫu này.</span></div>";
        if (m.ai) h += '<div class="note note-brand mt-s">' + ic("spark") + "<span><b>Mẫu có AI viết chữ.</b> Mặc định là Chạy thử: Agent chỉ đọc và viết nháp vào Duyệt nội dung, chưa đăng gì. Đổi ở mục Chế độ bên dưới khi bạn đã yên tâm.</span></div>";
        box.innerHTML = h;
      }

      function veNick() {
        var m = mau(), ds = khop(), n = soChon();
        var nt = m ? DS.tenNT(m.nen_tang) : "";
        el.querySelector("#chl-loc-nhan").innerHTML = m ?
          '<label class="chk small"><input type="checkbox" class="cb" id="chl-ln"' + (S.locNhan ? " checked" : "") + "> Chỉ nick có nhãn " + esc(nt) + "</label>" +
          '<label class="chk small"' + (S.locNhan ? "" : ' style="opacity:.5"') + '><input type="checkbox" class="cb" id="chl-cn"' + (S.chuaNhan ? " checked" : "") + (S.locNhan ? "" : " disabled") +
          "> Hiện cả nick chưa gắn nhãn</label>" : '<span class="small muted">Chọn mẫu để lọc nick theo nền tảng.</span>';
        el.querySelector("#chl-dem").textContent = n + "/" + NICK.length + " đã chọn · " + ds.length + " khớp lọc";
        el.querySelector("#chl-chon-het").textContent = "Chọn tất cả khớp (" + ds.length + ")";
        var box = el.querySelector("#chl-nick");
        if (!NICK.length) box.innerHTML = DS.rong("Chưa có nick nào", 'Ghép máy ở nhà để MinMin đọc danh sách profile GPM. <a href="#/may">Mở Máy ở nhà</a>', "list");
        else if (!ds.length) box.innerHTML = DS.rong("Không có nick khớp bộ lọc", "Bỏ bớt bộ lọc, hoặc gắn nhãn nền tảng cho nick ở trang Tài khoản.", "list");
        else box.innerHTML = ds.map(function (x) {
          var on = !!S.chon[x.id], cb = x.canh_bao || {}, cbk = Object.keys(cb);
          var trang = !x.online ? DS.bd("Máy tắt", "mu", true) : cbk.length ? DS.bd((DS.CANH_BAO[cb[cbk[0]]] || cb[cbk[0]]) + " · " + DS.tenNT(cbk[0]), "err", true) : DS.bd("Sẵn sàng", "ok", true);
          return '<label class="nick-row' + (on ? " on" : "") + '"><input type="checkbox" class="cb" data-nick="' + esc(x.id) + '"' + (on ? " checked" : "") + ">" + DS.av(x.ten) +
            '<div class="grow" style="min-width:0"><div class="b clip">' + esc(x.ten) + '</div><div class="tiny muted clip">' + esc(x.nhom || "Không thư mục") + " · " + esc(x.may_ten || "") +
            '</div></div><div class="row" style="flex-wrap:nowrap">' + (x.nhan || []).slice(0, 4).map(function (t) { return DS.icNT(t, 18); }).join("") + "</div>" + trang + "</label>";
        }).join("");
        nut();
      }

      function veThamSo() {
        var m = mau(), box = el.querySelector("#chl-ts"), sec = el.querySelector("#chl-ts-sec");
        if (!m) { sec.hidden = true; return; }
        sec.hidden = false;
        var ds = m.tham_so || [];
        if (!ds.length) { box.innerHTML = '<div class="small muted">Mẫu này không cần tham số.</div>'; return; }
        var thuong = ds.filter(function (f) { return f.kieu !== "bat" && f.kieu !== "doan" && f.kieu !== "ds_link" && !(f.kieu === "chon" && (f.key === "che_do" || (f.lua_chon || []).length <= 3)) && f.kieu !== "kho"; });
        var rong = ds.filter(function (f) { return thuong.indexOf(f) < 0 && f.kieu !== "bat"; });
        var bat = ds.filter(function (f) { return f.kieu === "bat"; });
        var h = "";
        if (thuong.length) h += '<div class="fgrid">' + thuong.map(function (f) { return truong(f, S.ts, KT); }).join("") + "</div>";
        rong.forEach(function (f) { h += '<div style="margin-top:14px">' + truong(f, S.ts, KT) + "</div>"; });
        if (bat.length) h += '<div style="margin-top:14px">' + bat.map(function (f) { return truong(f, S.ts, KT); }).join("") + "</div>";
        box.innerHTML = h;
        goiYCheDo();
      }
      function goiYCheDo() {
        var hEl = el.querySelector("#cd-hint");
        if (!hEl) return;
        var m = mau(), f = (m.tham_so || []).filter(function (x) { return x.key === "che_do"; })[0];
        var v = S.ts.che_do || (f && f.mac_dinh) || "chay_thu";
        hEl.textContent = GOI_Y_CHE_DO[v] || "";
        hEl.style.color = v === "dang_luon" ? "var(--warn)" : "";
      }

      function veLich() {
        var box = el.querySelector("#chl-lich");
        if (S.che_do !== "hen") { box.innerHTML = ""; nut(); return; }
        var L = S.lich;
        box.innerHTML = '<div class="card" style="margin-top:12px;box-shadow:none;background:var(--card2)"><div class="fld"><label>Lặp lại</label><div class="seg" data-seg="_lich">' +
          [["ngay", "Hằng ngày lúc"], ["gio", "Mỗi N giờ"], ["cron", "Cron tuỳ chỉnh"]].map(function (k) {
            return '<button type="button" data-v="' + k[0] + '" class="' + (L.kieu === k[0] ? "on" : "") + '">' + k[1] + "</button>";
          }).join("") + "</div></div>" +
          '<div class="fgrid" style="margin-top:12px">' +
          (L.kieu === "ngay" ? '<div class="fld"><label for="chl-gio">Giờ chạy</label><input class="inp" type="time" id="chl-gio" value="' + esc(L.gio) + '"></div>' : "") +
          (L.kieu === "gio" ? '<div class="fld"><label for="chl-n">Cách nhau (giờ)</label><input class="inp" type="number" min="1" max="23" id="chl-n" value="' + esc(L.n) + '"></div>' : "") +
          '<div class="fld"><label for="chl-cron">Cron</label><input class="inp" id="chl-cron" value="' + esc(L.kieu === "cron" ? L.cron : DS.taoCron(L.kieu, L)) + '"' + (L.kieu === "cron" ? "" : " readonly") +
          ' placeholder="phút giờ ngày tháng thứ"><div class="hint" id="chl-cron-mt">' + esc(DS.moTaCron(L.kieu === "cron" ? L.cron : DS.taoCron(L.kieu, L))) + "</div></div></div>" +
          '<div class="hint" style="margin-top:8px">Giờ theo múi giờ của máy chủ MinMin. Mỗi lần tới giờ, MinMin tạo một đợt chạy mới với đúng các nick và tham số này.</div></div>';
        nut();
      }

      function nut() {
        var b = el.querySelector("#chl-go");
        if (!b) return;
        var n = soChon();
        b.innerHTML = (S.che_do === "hen" ? ic("calendar") + "Lưu lịch hẹn (" : ic("play") + "Bắt đầu (") + n + " nick)";
        b.disabled = !n || !S.mau;
      }

      function docThamSo() {
        var m = mau(), ra = {}, loi = "";
        (m.tham_so || []).forEach(function (f) {
          var v = S.ts[f.key] !== undefined ? S.ts[f.key] : f.mac_dinh;
          if (f.kieu === "so") { v = v === "" || v == null ? f.mac_dinh : +v; if (isNaN(v)) loi = loi || "'" + f.nhan + "' phải là số"; }
          if (f.kieu === "ds_link") {
            v = String(Array.isArray(v) ? v.join("\n") : (v || "")).split(/[\n,]/).map(function (x) { return x.trim(); }).filter(Boolean);
            var sai = v.filter(function (x) { return x.indexOf("https://") !== 0; });
            if (sai.length) loi = loi || "Link phải bắt đầu bằng https:// (" + sai[0].slice(0, 50) + ")";
          }
          if (f.kieu === "bat") v = !!v;
          if (f.bat_buoc && (v === "" || v == null || (Array.isArray(v) && !v.length))) loi = loi || "Thiếu '" + f.nhan + "'";
          ra[f.key] = v;
        });
        return { ts: ra, loi: loi };
      }

      // ---- sự kiện
      el.addEventListener("input", function (e) {
        var t = e.target;
        if (t.id === "chl-ten") S.ten = t.value;
        else if (t.id === "chl-tim") { S.tim = t.value; veNick(); }
        else if (t.dataset && t.dataset.ts && t.type !== "checkbox") S.ts[t.dataset.ts] = t.value;
        else if (t.id === "chl-gio" || t.id === "chl-n" || t.id === "chl-cron") {
          if (t.id === "chl-gio") S.lich.gio = t.value;
          if (t.id === "chl-n") S.lich.n = t.value;
          if (t.id === "chl-cron") S.lich.cron = t.value;
          var cr = S.lich.kieu === "cron" ? S.lich.cron : DS.taoCron(S.lich.kieu, S.lich);
          if (S.lich.kieu !== "cron") el.querySelector("#chl-cron").value = cr;
          el.querySelector("#chl-cron-mt").textContent = DS.moTaCron(cr);
        }
      });
      el.addEventListener("change", function (e) {
        var t = e.target;
        if (t.id === "chl-mau") {
          S.mau = t.value; S.ts = {};
          try { history.replaceState(null, "", "#/chay-hang-loat" + (S.mau ? "?mau=" + encodeURIComponent(S.mau) : "")); } catch (x) {}
          veMau(); veNick(); veThamSo();
        } else if (t.id === "chl-tm") { S.thuMuc = t.value; veNick(); }
        else if (t.id === "chl-ln") { S.locNhan = t.checked; veNick(); }
        else if (t.id === "chl-cn") { S.chuaNhan = t.checked; veNick(); }
        else if (t.id === "chl-an") S.chay_an = t.checked;
        else if (t.dataset.nick) {
          S.chon[t.dataset.nick] = t.checked;
          t.closest(".nick-row").classList.toggle("on", t.checked);
          el.querySelector("#chl-dem").textContent = soChon() + "/" + NICK.length + " đã chọn · " + khop().length + " khớp lọc";
          nut();
        } else if (t.dataset.ts) S.ts[t.dataset.ts] = t.type === "checkbox" ? t.checked : t.value;
      });
      el.addEventListener("click", function (e) {
        var b = e.target.closest("[data-seg] button");
        if (!b) return;
        var seg = b.parentNode, k = seg.getAttribute("data-seg"), v = b.getAttribute("data-v");
        Array.prototype.forEach.call(seg.children, function (x) { x.classList.toggle("on", x === b); });
        if (k === "_song") S.song_song = +v;
        else if (k === "_chedo") { S.che_do = v; veLich(); }
        else if (k === "_lich") { S.lich.kieu = v; veLich(); }
        else { S.ts[k] = v; if (k === "che_do") goiYCheDo(); }
      });
      DS.bind(el, {
        "chon-het": function () { khop().forEach(function (n) { S.chon[n.id] = true; }); veNick(); },
        "bo-chon": function () { S.chon = {}; veNick(); },
        "bat-dau": function (b) {
          var m = mau();
          if (!m) { DS.toast("Chọn mẫu trước", "err"); return; }
          var nick = Object.keys(S.chon).filter(function (k) { return S.chon[k]; });
          if (!nick.length) { DS.toast("Chọn ít nhất một nick", "err"); return; }
          var r = docThamSo();
          if (r.loi) { DS.toast(r.loi, "err"); return; }
          var body = { ten: S.ten.trim(), kich_ban: m.id, nick: nick.map(function (x) { return isNaN(+x) ? x : +x; }), tham_so: r.ts, song_song: S.song_song,
            chay_an: S.chay_an, che_do: S.che_do };
          if (S.che_do === "hen") {
            body.cron = S.lich.kieu === "cron" ? String(S.lich.cron || "").trim() : DS.taoCron(S.lich.kieu, S.lich);
            if (body.cron.split(/\s+/).length !== 5) { DS.toast("Cron cần đúng 5 phần: phút giờ ngày tháng thứ", "err"); return; }
          }
          b.disabled = true;
          DS.api("POST", "/doi-social/dot-chay", body).then(function (d) {
            b.disabled = false;
            if (d.ok === false) return;
            if (S.che_do === "hen") { DS.toast("Đã lưu lịch hẹn " + DS.moTaCron(body.cron).toLowerCase(), "ok"); DS.go("automation", { tab: "lich" }); }
            else { DS.toast("Đã tạo đợt chạy cho " + nick.length + " nick" + (m.san_sang === false ? ", chờ máy ở nhà hỗ trợ mẫu" : ""), "ok"); DS.go("nhat-ky", { tab: "dot" }); }
          });
        }
      });
    }
  });
})();
