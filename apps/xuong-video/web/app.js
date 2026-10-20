/* Xưởng video: giao diện. Mọi chữ đưa vào trang đều đi qua textContent (nội dung do AI viết, không tin). */
(function () {
  "use strict";
  var API = "/apps/xuong-video/api";
  var NEN_TANG = [
    ["youtube", "YouTube"], ["youtube_short", "YouTube Shorts"], ["facebook_reel", "Facebook Reels"],
    ["tiktok", "TikTok"], ["instagram", "Instagram"], ["x", "X"], ["threads", "Threads"], ["zalo", "Zalo"]];
  var TT = {
    nhap: ["Mới tạo", ""], dang_lap_kich_ban: ["Đang viết kịch bản", "chay"], kich_ban_xong: ["Có kịch bản", ""],
    dang_tao_anh: ["Đang tạo ảnh", "chay"], dang_tao_video: ["Đang tạo video", "chay"],
    dang_tao_giong: ["Đang tạo giọng", "chay"], dang_ghep: ["Đang ghép", "chay"],
    san_sang: ["Video sẵn sàng", "vang"], dang_dang: ["Đang đăng", "chay"], da_dang: ["Đã đăng", "ok"],
    loi: ["Lỗi", "loi"], da_huy: ["Đã huỷ", ""]};
  var main = document.getElementById("main");
  var state = { tab: "du-an", tt: null, xem: "", timer: null };

  function h(tag, attrs) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") e.className = attrs[k];
      else if (k.slice(0, 2) === "on") e[k] = attrs[k];
      else if (k === "value") e.value = attrs[k];
      else if (attrs[k] !== false && attrs[k] != null) e.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    });
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null || c === false) continue;
      if (Array.isArray(c)) c.forEach(function (x) { if (x) e.appendChild(typeof x === "string" ? document.createTextNode(x) : x); });
      else e.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return e;
  }
  function api(path, opt) {
    opt = opt || {};
    var o = { method: opt.method || "GET", headers: {} };
    if (opt.body !== undefined) {
      if (opt.raw) { o.body = opt.body; } else { o.body = JSON.stringify(opt.body); o.headers["Content-Type"] = "application/json"; }
    }
    return fetch(API + path, o).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: "Máy chủ trả dữ liệu lạ." }; })
        .then(function (d) { if (!r.ok && !d.error) d.error = "Lỗi " + r.status; return d; });
    });
  }
  function toast(msg) {
    var t = document.getElementById("toast");
    t.textContent = msg; t.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(function () { t.hidden = true; }, 4500);
  }
  function chip(tt) { var d = TT[tt] || [tt, ""]; return h("span", { class: "tt " + d[1] }, d[0]); }
  function ngay(ts) { return ts ? new Date(ts * 1000).toLocaleString("vi-VN") : ""; }
  function tenNT(id) { for (var i = 0; i < NEN_TANG.length; i++) if (NEN_TANG[i][0] === id) return NEN_TANG[i][1]; return id; }

  function napTrangThai() {
    return api("/trang-thai").then(function (d) {
      if (!d.ok) { main.textContent = d.error || "Không mở được."; return false; }
      state.tt = d;
      var cb = document.getElementById("canh-bao");
      cb.hidden = d.ffmpeg; cb.textContent = d.ffmpeg ? "" : "Máy chủ chưa cài ffmpeg, chưa ghép được video. Cài ffmpeg rồi tải lại trang.";
      document.getElementById("hom-nay").textContent =
        "Hôm nay: " + d.hom_nay.video + "/" + (d.cai_dat.toi_da_video_moi_ngay || "không giới hạn") + " cảnh video, " +
        d.hom_nay.dang + "/" + (d.cai_dat.toi_da_bai_dang_moi_ngay || "không giới hạn") + " bài đăng";
      return true;
    });
  }

  // ------------------------------------------------------------ danh sách
  function veDanhSach() {
    var ds = h("div", {}, h("p", { class: "nho" }, "Đang tải..."));
    main.replaceChildren(ds);
    api("/du-an").then(function (d) {
      if (!d.ok) { ds.textContent = d.error; return; }
      if (!d.du_an.length) { ds.replaceChildren(h("div", { class: "card" }, "Chưa có dự án nào. Bấm Tạo mới hoặc Làm hàng loạt.")); return; }
      ds.replaceChildren.apply(ds, d.du_an.map(function (p) {
        return h("div", { class: "card" }, h("div", { class: "dong" },
          h("div", {}, h("b", {}, p.ten || "(chưa đặt tên)"), " ", chip(p.trang_thai),
            p.loi ? h("div", { class: "nho" }, p.loi) : null,
            h("div", { class: "nho" }, p.so_canh ? p.canh_xong + "/" + p.so_canh + " cảnh có video. " : "",
              p.nen_tang.map(tenNT).join(", ") || "Chưa chọn nền tảng", ". Tạo " + ngay(p.tao_luc))),
          h("button", { class: "btn phu", onclick: function () { state.xem = p.id; veChiTiet(); } }, "Mở")));
      }));
    });
  }

  // ------------------------------------------------------------ biểu mẫu chung
  function chonNenTang(chon) {
    var ds = h("div", { class: "chips" });
    NEN_TANG.forEach(function (n) {
      var ok = state.tt.ho_tro[n[0]];
      var cb = h("input", { type: "checkbox", value: n[0], disabled: !ok });
      if (ok && (chon || []).indexOf(n[0]) >= 0) cb.checked = true;
      var l = h("label", { title: ok ? "" : (state.tt.ly_do_chua[n[0]] || "Chưa hỗ trợ") }, cb, n[1] + (ok ? "" : " (sắp có)"));
      ds.appendChild(l);
    });
    ds.lay = function () { return Array.prototype.filter.call(ds.querySelectorAll("input:checked"), function () { return true; }).map(function (i) { return i.value; }); };
    return ds;
  }
  function truongChung() {
    var f = {
      nen: chonNenTang(["youtube_short", "facebook_reel"]),
      ti_le: h("select", {}, h("option", { value: "9:16" }, "9:16 dọc (Shorts, Reels)"), h("option", { value: "16:9" }, "16:9 ngang (YouTube)"), h("option", { value: "1:1" }, "1:1 vuông")),
      giay: h("input", { type: "number", min: 8, max: 180, value: 30 }),
      phong_cach: h("input", { placeholder: "vd: hoạt hình 3D dễ thương, ấm áp" }),
      ngon_ngu: h("select", {}, h("option", { value: "vi" }, "Tiếng Việt"), h("option", { value: "en" }, "English")),
      che_do: h("select", {}, h("option", { value: "duyet" }, "Chờ tôi duyệt rồi mới đăng (an toàn)"), h("option", { value: "tu_dong" }, "Tự đăng khi xong, chỉ báo kết quả"))
    };
    f.node = h("div", {},
      h("label", {}, "Đăng lên"), f.nen,
      h("div", { class: "hang" },
        h("div", {}, h("label", {}, "Tỉ lệ"), f.ti_le),
        h("div", {}, h("label", {}, "Thời lượng (giây)"), f.giay),
        h("div", {}, h("label", {}, "Ngôn ngữ"), f.ngon_ngu)),
      h("label", {}, "Phong cách hình"), f.phong_cach,
      h("label", {}, "Cách đăng"), f.che_do);
    f.doc = function () {
      return { nen_tang: f.nen.lay(), ti_le: f.ti_le.value, thoi_luong_giay: +f.giay.value || 30,
        phong_cach: f.phong_cach.value, ngon_ngu: f.ngon_ngu.value, che_do_dang: f.che_do.value };
    };
    return f;
  }

  function veMoi() {
    var ten = h("input", { placeholder: "Tên dự án (tuỳ chọn)" });
    var y = h("textarea", { placeholder: "Viết ý tưởng, câu chuyện, hoặc dán lời kể. Có thể đính kèm ảnh/video mẫu bên dưới để AI xem và làm lại thành bản mới." });
    var tep = h("input", { type: "file", multiple: true, accept: "image/*,video/*" });
    var ch = truongChung();
    var nut = h("button", { class: "btn" }, "Tạo và chạy ngay");
    var nutNhap = h("button", { class: "btn phu" }, "Chỉ tạo, chưa chạy");
    function lam(chay) {
      if (!y.value.trim()) { toast("Cần nhập ý tưởng."); return; }
      nut.disabled = nutNhap.disabled = true;
      var body = Object.assign({ ten: ten.value, y_tuong: y.value }, ch.doc());
      api("/du-an", { method: "POST", body: body }).then(function (d) {
        if (!d.ok) throw new Error(d.error);
        var up = Array.prototype.map.call(tep.files, function (f) {
          return api("/du-an/" + d.id + "/tai-lieu?ten=" + encodeURIComponent(f.name), { method: "POST", body: f, raw: true })
            .then(function (r) { if (!r.ok) toast(f.name + ": " + r.error); });
        });
        return Promise.all(up).then(function () { return d.id; });
      }).then(function (id) {
        if (!chay) return id;
        return api("/du-an/" + id + "/chay", { method: "POST" }).then(function (r) { if (!r.ok) toast(r.error); return id; });
      }).then(function (id) { state.xem = id; veChiTiet(); })
        .catch(function (e) { toast(e.message); nut.disabled = nutNhap.disabled = false; });
    }
    nut.onclick = function () { lam(true); }; nutNhap.onclick = function () { lam(false); };
    main.replaceChildren(h("div", { class: "card" }, h("h2", {}, "Dự án video mới"),
      h("label", {}, "Tên"), ten, h("label", {}, "Ý tưởng"), y, h("label", {}, "Ảnh hoặc video mẫu (tuỳ chọn)"), tep,
      ch.node, h("p", {}, nut, " ", nutNhap)));
  }

  async function taiTuLieu(id, files) {
    // Giữ đúng thứ tự chọn file; lỗi upload phải dừng trước khi dựng.
    for (var f of Array.from(files)) {
      var r = await api("/du-an/" + id + "/tai-lieu?ten=" + encodeURIComponent(f.name),
        { method: "POST", body: f, raw: true });
      if (!r.ok) throw new Error(f.name + ": " + r.error);
    }
  }

  function veTuLieu() {
    var ten = h("input", { "aria-label": "Tên video", placeholder: "Ví dụ: Bộ sưu tập thu đông" });
    var files = h("input", { type: "file", multiple: true, accept: "image/png,image/jpeg,image/webp,video/mp4,video/quicktime,video/webm", "aria-label": "Ảnh và clip của tôi" });
    var ratio = h("select", { "aria-label": "Tỉ lệ video" }, h("option", { value: "9:16" }, "9:16 dọc"),
      h("option", { value: "16:9" }, "16:9 ngang"), h("option", { value: "1:1" }, "1:1 vuông"));
    var message = h("p", { class: "nho", role: "status" });
    var create = h("button", { class: "btn", onclick: async function () {
      if (!files.files.length) { message.textContent = "Chọn ít nhất một ảnh hoặc clip."; return; }
      if (files.files.length > 30) { message.textContent = "Mỗi bản dựng tối đa 30 ảnh/clip."; return; }
      create.disabled = true;
      var id = "";
      try {
        var r = await api("/du-an", { method: "POST", body: { ten: ten.value || "Video từ tư liệu",
          y_tuong: ten.value || "Dựng từ ảnh và clip của tôi", nguon: "tu_lieu", ti_le: ratio.value, nen_tang: [], che_do_dang: "duyet" } });
        if (!r.ok) throw new Error(r.error);
        id = r.id;
        message.textContent = "Đang tải tư liệu…";
        await taiTuLieu(id, files.files);
        state.xem = id; veChiTiet();
      } catch (e) {
        message.textContent = e.message + (id ? " Dự án đã lưu trong mục Dự án; mở để thêm lại file còn thiếu." : "");
        create.disabled = false;
      }
    } }, "Tải lên và sắp cảnh");
    main.replaceChildren(h("section", { class: "card" }, h("h2", {}, "Dựng video từ ảnh và clip thật"),
      h("p", { class: "nho" }, "Dùng tư liệu của bạn, không tạo lại sản phẩm bằng AI. Sắp cảnh, thêm lời đọc và nhạc trước khi dựng. Video chỉ được đăng khi bạn chọn đăng."),
      h("label", {}, "Tên video", ten), h("label", {}, "Ảnh và clip (tối đa 30 file)", files),
      h("label", {}, "Khung hình", ratio), h("p", {}, create), message));
  }

  function bienTapTuLieu(p) {
    var b = p.ban_dung || {}, assets = p.tai_lieu || [];
    var rows = (b.canh || assets.filter(function (x) { return x.loai !== "audio"; }).map(function (x) {
      return { rel: x.rel, giay: 5, chu: "" };
    })).map(function (x) { return Object.assign({}, x); });
    var list = h("div", { class: "material-scenes" });
    var feedback = h("p", { class: "nho", role: "status" });
    function select(items, value, name) {
      var e = h("select", { "aria-label": name }, items.map(function (x) { return h("option", { value: x[0] }, x[1]); }));
      if (value != null) e.value = String(value);
      return e;
    }
    var audios = [["", "Không chọn"]].concat(assets.filter(function (a) { return a.loai === "audio"; }).map(function (a) { return [a.rel, a.ten]; }));
    var controls = {
      giong: select([["khong", "Không lời đọc"], ["edge", "Edge TTS"], ["elevenlabs", "ElevenLabs đã kết nối"], ["tep", "File lời đọc của tôi"]], b.giong || "khong", "Nguồn lời đọc"),
      voice: select([["vi-VN-HoaiMyNeural", "Hoài My · nữ · tiếng Việt"], ["vi-VN-NamMinhNeural", "Nam Minh · nam · tiếng Việt"],
        ["en-US-JennyNeural", "Jenny · English"], ["en-US-GuyNeural", "Guy · English"]], b.voice, "Giọng Edge"),
      toc_do: h("input", { type: "number", min: .75, max: 1.25, step: .05, value: b.toc_do || 1, "aria-label": "Tốc độ lời đọc" }),
      nhac: select(audios, b.nhac, "Nhạc nền"),
      loi_doc: select(audios, b.loi_doc, "File lời đọc"),
      am_nhac: h("input", { type: "number", min: 0, max: 1, step: .05, value: b.am_nhac == null ? .15 : b.am_nhac, "aria-label": "Âm lượng nhạc" }),
      am_giong: h("input", { type: "number", min: 0, max: 2, step: .1, value: b.am_giong == null ? 1 : b.am_giong, "aria-label": "Âm lượng lời đọc" }),
      phu_de: h("input", { type: "checkbox", "aria-label": "Hiện phụ đề" }),
      co_chu: h("input", { type: "number", min: 10, max: 32, value: b.co_chu || 18, "aria-label": "Cỡ phụ đề" }),
      mau: h("input", { type: "color", value: b.mau || "#ffffff", "aria-label": "Màu phụ đề" }),
      vi_tri: select([["duoi", "Dưới"], ["tren", "Trên"]], b.vi_tri, "Vị trí phụ đề"),
      khung: select([["fit", "Giữ trọn hình, thêm nền"], ["crop", "Lấp đầy, cắt phần thừa"]], b.khung, "Cách đặt ảnh")
    };
    controls.phu_de.checked = b.phu_de !== false;
    function read() {
      var d = { canh: rows };
      Object.keys(controls).forEach(function (k) { d[k] = k === "phu_de" ? controls[k].checked : controls[k].value; });
      return d;
    }
    function draw() {
      list.replaceChildren();
      rows.forEach(function (c, i) {
        var a = assets.find(function (a) { return a.rel === c.rel; });
        if (!a) return;
        var sec = h("input", { type: "number", min: 1, max: 30, step: .5, value: c.giay, "aria-label": "Giây cảnh " + (i+1),
          oninput: function () { c.giay = +sec.value; } });
        var text = h("textarea", { "aria-label": "Lời cảnh " + (i+1), maxlength: 600, placeholder: "Lời đọc / chữ phụ đề của cảnh này",
          oninput: function () { c.chu = text.value; } }); text.value = c.chu;
        var url = API + "/du-an/" + p.id + "/tep?rel=" + encodeURIComponent(c.rel);
        list.appendChild(h("div", { class: "canh" },
          a.loai === "anh" ? h("img", { src: url, alt: a.ten }) : h("video", { src: url, controls: true, preload: "metadata" }),
          h("b", {}, "Cảnh " + (i+1) + " · " + a.ten),
          h("label", {}, "Thời lượng tối thiểu (giây)", sec), h("label", {}, "Lời cảnh", text),
          h("div", { class: "scene-actions" },
            h("button", { type: "button", class: "btn phu", disabled: i === 0, onclick: function () { [rows[i-1], rows[i]] = [rows[i], rows[i-1]]; draw(); } }, "Lên"),
            h("button", { type: "button", class: "btn phu", disabled: i === rows.length-1, onclick: function () { [rows[i+1], rows[i]] = [rows[i], rows[i+1]]; draw(); } }, "Xuống"),
            h("button", { type: "button", class: "btn phu", onclick: function () { rows.splice(i, 1); draw(); } }, "Bỏ khỏi bản dựng"))));
      });
    }
    draw();
    var addAsset = select([["", "Chọn tư liệu đã tải"]].concat(assets.filter(function (a) { return a.loai !== "audio"; }).map(function (a) { return [a.rel, a.ten]; })), "", "Thêm cảnh từ khay");
    var upload = h("input", { type: "file", multiple: true, accept: "image/*,video/*,audio/*", "aria-label": "Thêm ảnh clip hoặc âm thanh" });
    async function save() {
      var r = await api("/du-an/" + p.id + "/ban-dung", { method: "PUT", body: read() });
      if (!r.ok) throw new Error(r.error);
    }
    var saveBtn = h("button", { class: "btn phu" }, "Lưu bản dựng");
    var runBtn = h("button", { class: "btn" }, "Lưu và dựng video");
    async function commit(run) {
      saveBtn.disabled = runBtn.disabled = true;
      try {
        await save();
        if (run) {
          var r = await api("/du-an/" + p.id + "/chay", { method: "POST" });
          if (!r.ok) throw new Error(r.error);
        }
        veChiTiet();
      } catch (e) { feedback.textContent = e.message; saveBtn.disabled = runBtn.disabled = false; }
    }
    saveBtn.onclick = function () { commit(false); }; runBtn.onclick = function () { commit(true); };
    var fieldset = h("fieldset", { disabled: p.dang_chay, class: "material-editor" },
      h("legend", {}, "Bản dựng từ tư liệu"),
      h("p", { class: "nho" }, "Thứ tự cảnh cũng là thứ tự xuất video. Clip ngắn được lặp đến đủ thời lượng; âm thanh gốc của clip được tắt."),
      list, h("div", { class: "hang" }, addAsset, h("button", { class: "btn phu", onclick: function () {
        if (addAsset.value && rows.length < 30) { rows.push({ rel: addAsset.value, giay: 5, chu: "" }); draw(); }
      } }, "Thêm cảnh")),
      h("label", {}, "Thêm tư liệu / nhạc / bản thu", upload),
      h("button", { class: "btn phu", onclick: async function () {
        if (!upload.files.length) { feedback.textContent = "Chọn file trước khi tải lên."; return; }
        fieldset.disabled = true;
        try { await save(); await taiTuLieu(p.id, upload.files); veChiTiet(); }
        catch (e) { feedback.textContent = e.message; fieldset.disabled = false; }
      } }, "Tải thêm file"),
      h("h3", {}, "Âm thanh"),
      h("div", { class: "hang" }, h("label", {}, "Nguồn lời đọc", controls.giong), h("label", {}, "Giọng Edge", controls.voice),
        h("label", {}, "Tốc độ (0,75–1,25)", controls.toc_do)),
      h("p", { class: "nho" }, "Edge gửi lời cảnh tới dịch vụ đọc Microsoft. ElevenLabs dùng khoá đã kết nối. File lời đọc phát từ đầu video, không tự căn theo từng từ."),
      h("div", { class: "hang" }, h("label", {}, "File lời đọc", controls.loi_doc), h("label", {}, "Âm lượng lời", controls.am_giong)),
      h("div", { class: "hang" }, h("label", {}, "Nhạc nền", controls.nhac), h("label", {}, "Âm lượng nhạc (0–1)", controls.am_nhac)),
      h("h3", {}, "Hình và phụ đề"),
      h("label", { class: "check-label" }, controls.phu_de, "Hiện phụ đề"),
      h("div", { class: "hang" }, h("label", {}, "Cỡ chữ", controls.co_chu), h("label", {}, "Màu chữ", controls.mau),
        h("label", {}, "Vị trí", controls.vi_tri), h("label", {}, "Khung ảnh", controls.khung)),
      h("p", { class: "nho" }, "Edge dùng mốc lời đọc khi dịch vụ cung cấp; các chế độ khác hiển thị phụ đề theo cảnh. Lời đọc dài sẽ kéo dài cảnh."),
      h("p", { class: "scene-actions" }, saveBtn, runBtn), feedback);
    return h("section", { class: "card" }, fieldset);
  }

  function veLo() {
    var y = h("textarea", { style: "min-height:220px", placeholder: "Mỗi ý tưởng một đoạn, cách nhau bằng MỘT DÒNG TRỐNG. Tối đa 30 ý tưởng một lô." });
    var ten = h("input", { placeholder: "Tên lô (vd: Truyện cổ tích tuần 1)" });
    var gian = h("input", { type: "number", min: 0, value: 120 });
    var ch = truongChung();
    var nut = h("button", { class: "btn" }, "Tạo lô và chạy lần lượt");
    nut.onclick = function () {
      if (!y.value.trim()) { toast("Cần nhập ít nhất một ý tưởng."); return; }
      nut.disabled = true;
      var chung = ch.doc(); chung.ten = ten.value;
      api("/lo", { method: "POST", body: { y_tuong: y.value, chung: chung, cach_nhau_phut: +gian.value || 0 } }).then(function (d) {
        if (!d.ok) { toast(d.error); nut.disabled = false; return; }
        toast("Đã tạo " + d.ids.length + " dự án, đang chạy lần lượt.");
        state.tab = "du-an"; chonTab();
      });
    };
    main.replaceChildren(h("div", { class: "card" }, h("h2", {}, "Làm hàng loạt"),
      h("p", { class: "nho" }, "Mỗi ý tưởng thành một video. Các video chạy lần lượt để kiểm soát chi phí và tôn trọng hạn mức mỗi ngày."),
      h("label", {}, "Tên lô"), ten, h("label", {}, "Các ý tưởng"), y, ch.node,
      h("label", {}, "Giãn giờ đăng giữa hai video (phút, chỉ áp dụng khi chọn tự đăng)"), gian, h("p", {}, nut)));
  }

  // ------------------------------------------------------------ chi tiết
  function veChiTiet() {
    clearInterval(state.timer);
    var id = state.xem;
    if (!id) { state.tab = "du-an"; chonTab(); return; }
    var goc = h("div", {});
    main.replaceChildren(goc);
    function ve() {
      api("/du-an/" + id).then(function (d) {
        if (!d.ok) { goc.textContent = d.error; clearInterval(state.timer); return; }
        var p = d.du_an;
        // Đang gõ sửa thì không vẽ lại, kẻo mất chữ.
        if (goc.contains(document.activeElement) && /^(TEXTAREA|INPUT|SELECT)$/.test(document.activeElement.tagName)) return;
        goc.replaceChildren(khungChiTiet(p));
        if (!p.dang_chay && !/^dang_/.test(p.trang_thai)) clearInterval(state.timer);
      });
    }
    ve();
    state.timer = setInterval(ve, 4000);
  }

  function khungChiTiet(p) {
    var kb = p.kich_ban || {};
    var ra = [];
    ra.push(h("div", { class: "card" },
      h("div", { class: "dong" }, h("div", {}, h("h2", {}, p.ten), chip(p.trang_thai), " ", p.dang_chay ? h("span", { class: "tt chay" }, "đang chạy") : null),
        h("div", {},
          h("button", { class: "btn phu", onclick: function () { state.tab = "du-an"; chonTab(); } }, "Quay lại"), " ",
          h("button", { class: "btn", disabled: p.dang_chay || p.nguon === "tu_lieu", onclick: function () { api("/du-an/" + p.id + "/chay", { method: "POST" }).then(function (r) { if (!r.ok) toast(r.error); veChiTiet(); }); } },
            p.canh && p.canh.length ? "Chạy tiếp / làm lại phần thiếu" : "Chạy"), " ",
          h("button", { class: "btn nguy", disabled: p.dang_chay, onclick: function () { if (confirm("Xoá dự án này cùng mọi tệp của nó?")) api("/du-an/" + p.id, { method: "DELETE" }).then(function () { state.tab = "du-an"; chonTab(); }); } }, "Xoá"))),
      p.loi ? h("p", { class: "nho", style: "color:var(--loi)" }, p.loi) : null,
      h("p", {}, p.y_tuong)));

    if (p.nguon === "tu_lieu") ra.push(bienTapTuLieu(p));

    if (p.ket_qua && p.ket_qua.video) {
      var v = h("video", { controls: true, src: API + "/du-an/" + p.id + "/tep?rel=" + encodeURIComponent(p.ket_qua.video) });
      var dangCard = h("div", { class: "card" }, h("h3", {}, "Video hoàn chỉnh (" + p.ket_qua.giay + " giây, " + p.ket_qua.kich_co + ")"), v);
      dangCard.appendChild(h("p", {}, h("a", { class: "btn tai-file", href: API + "/du-an/" + p.id + "/tep?tai=true&rel=" + encodeURIComponent(p.ket_qua.video), download: "video.mp4" }, "Tải video MP4"), " ",
        p.ket_qua.srt ? h("a", { class: "btn tai-file", href: API + "/du-an/" + p.id + "/tep?tai=true&rel=" + encodeURIComponent(p.ket_qua.srt), download: "subtitles.srt" }, "Tải phụ đề SRT") : null));
      var tt = h("div", {});
      (p.nen_tang || []).forEach(function (nt) {
        var s = (p.dang || {})[nt] || {};
        var nhan = s.trang_thai === "da_dang" ? "Đã đăng" : s.trang_thai === "loi" ? "Lỗi" : s.trang_thai === "chua_ro" ? "Chưa rõ, cần kiểm tra" : "Chưa đăng";
        tt.appendChild(h("div", { class: "nho" }, tenNT(nt) + ": " + nhan + " ", s.url ? h("a", { href: s.url, target: "_blank", rel: "noopener" }, "mở bài") : null, s.loi ? " (" + s.loi + ")" : ""));
      });
      dangCard.appendChild(tt);
      var ok = !p.dang_chay && (p.trang_thai === "san_sang" || p.trang_thai === "da_dang" || p.trang_thai === "loi");
      dangCard.appendChild(h("p", {},
        h("button", { class: "btn", disabled: !ok || !(p.nen_tang || []).length, onclick: function () {
          if (!confirm("Đăng video này lên: " + p.nen_tang.map(tenNT).join(", ") + "? Bài đã đăng không rút lại được từ đây.")) return;
          api("/du-an/" + p.id + "/dang-ngay", { method: "POST" }).then(function (r) { toast(r.ok ? "Đang đăng, kết quả sẽ báo ở chuông." : r.error); veChiTiet(); });
        } }, "Đăng ngay"), " ",
        p.che_do_dang !== "tu_dong" ? h("button", { class: "btn phu", disabled: !ok, onclick: function () {
          api("/du-an/" + p.id + "/duyet", { method: "POST", body: {} }).then(function (r) { toast(r.ok ? "Đã duyệt, hệ thống sẽ đăng trong ít phút." : r.error); veChiTiet(); });
        } }, "Duyệt, để hệ thống đăng") : h("span", { class: "nho" }, "Chế độ tự đăng" + (p.dang_luc ? ", hẹn " + ngay(p.dang_luc) : ""))));
      ra.push(dangCard);
    }

    if (kb.tieu_de) ra.push(h("div", { class: "card" }, h("h3", {}, "Kịch bản: " + kb.tieu_de), h("p", {}, kb.mo_ta || ""),
      h("p", { class: "nho" }, (kb.hashtags || []).map(function (t) { return "#" + t; }).join(" "))));

    if ((p.canh || []).length) {
      var luoi = h("div", { class: "luoi" });
      p.canh.forEach(function (c) {
        var thoai = h("textarea", { "aria-label": "Lời thoại" }, c.loi_thoai || ""); thoai.value = c.loi_thoai || "";
        var hinh = h("textarea", { "aria-label": "Mô tả hình" }, ""); hinh.value = c.mo_ta_hinh || "";
        var luu = h("button", { class: "btn phu", onclick: function () {
          api("/du-an/" + p.id, { method: "PATCH", body: { canh: [{ stt: c.stt, loi_thoai: thoai.value, mo_ta_hinh: hinh.value, tao_lai: true }] } })
            .then(function (r) { toast(r.ok ? "Đã lưu, bấm Chạy tiếp để tạo lại cảnh này." : r.error); });
        } }, "Lưu và tạo lại");
        luoi.appendChild(h("div", { class: "canh" },
          c.anh ? h("img", { src: API + "/du-an/" + p.id + "/tep?rel=" + encodeURIComponent(c.anh), alt: "Cảnh " + c.stt }) : null,
          h("b", {}, "Cảnh " + c.stt + " "), h("span", { class: "tt " + (c.trang_thai === "loi" ? "loi" : c.video ? "ok" : "") }, c.video ? "có video" : c.trang_thai === "loi" ? "lỗi" : "chờ"),
          c.loi ? h("div", { class: "nho", style: "color:var(--loi)" }, c.loi) : null,
          h("label", {}, "Lời thoại"), thoai, h("label", {}, "Hình"), hinh, h("p", {}, luu)));
      });
      ra.push(h("div", { class: "card" }, h("h3", {}, "Các cảnh"), luoi));
    }

    var nk = h("div", { class: "nhat-ky" });
    (p.nhat_ky || []).slice(-40).reverse().forEach(function (l) { nk.appendChild(h("div", { class: l.k === "loi" ? "loi" : "" }, new Date(l.t * 1000).toLocaleTimeString("vi-VN") + "  " + l.m)); });
    ra.push(h("div", { class: "card" }, h("h3", {}, "Nhật ký"), nk));
    return h("div", {}, ra);
  }

  // ------------------------------------------------------------ khoá, kết nối, cài đặt
  var NHAN = {
    fal: ["fal.ai (tạo video: Veo, Kling, Seedance...)", { api_key: "API key" }],
    gemini: ["Google Gemini (Nano Banana, tạo ảnh)", { api_key: "API key" }],
    openai: ["OpenAI (ChatGPT Image, tạo ảnh)", { api_key: "API key" }],
    elevenlabs: ["ElevenLabs (giọng đọc)", { api_key: "API key", voice_id: "Voice ID" }],
    youtube: ["YouTube (Google Cloud OAuth)", { client_id: "Client ID", client_secret: "Client Secret" }],
    tiktok: ["TikTok (Content Posting API)", { client_key: "Client key", client_secret: "Client secret", rieng_tu: "Chế độ hiển thị (SELF_ONLY, FOLLOWER_OF_CREATOR, MUTUAL_FOLLOW_FRIENDS, PUBLIC_TO_EVERYONE)", ten_kenh: "Tên kênh (@...) để tạo link bài" }],
    facebook: ["Facebook Page (đăng Reels)", { page_id: "Page ID", page_token: "Page access token", ten_trang: "Tên Trang (để nhớ)" }]
  };
  function veKetNoi() {
    napTrangThai().then(function (ok) {
      if (!ok) return;
      var cd = state.tt.cai_dat, ra = [];
      Object.keys(NHAN).forEach(function (dv) {
        var cur = state.tt.khoa[dv] || {}, inputs = {};
        var rows = Object.keys(NHAN[dv][1]).map(function (k) {
          inputs[k] = h("input", { type: /key|secret|token/.test(k) ? "password" : "text", autocomplete: "off",
            placeholder: cur[k] ? "Đã đặt: " + cur[k] + " (bỏ trống để giữ)" : "" });
          if (!/key|secret|token/.test(k) && cur[k]) inputs[k].value = cur[k];
          return h("div", {}, h("label", {}, NHAN[dv][1][k]), inputs[k]);
        });
        var nut = h("button", { class: "btn", onclick: function () {
          var body = {}; Object.keys(inputs).forEach(function (k) { if (inputs[k].value.trim()) body[k] = inputs[k].value.trim(); });
          api("/khoa/" + dv, { method: "POST", body: body }).then(function (r) { toast(r.ok ? "Đã lưu." : r.error); veKetNoi(); });
        } }, "Lưu");
        var xoa = h("button", { class: "btn phu", onclick: function () { if (confirm("Xoá khoá này?")) api("/khoa/" + dv, { method: "DELETE" }).then(veKetNoi); } }, "Xoá");
        var them = null;
        if (dv === "youtube" || dv === "tiktok") {
          them = h("button", { class: "btn phu", onclick: function () {
            api(dv === "tiktok" ? "/tiktok/ket-noi" : "/youtube/ket-noi").then(function (r) {
              if (!r.ok) { toast(r.error); return; }
              toast("Thêm đường dẫn này vào danh sách redirect URI đã đăng ký: " + r.redirect_uri);
              window.open(r.url, "_blank", "noopener");
            });
          } }, cur.refresh_token ? "Kết nối lại" : "Kết nối tài khoản");
        }
        ra.push(h("div", { class: "card" }, h("div", { class: "dong" }, h("h3", {}, NHAN[dv][0]),
          cur.da_dat ? h("span", { class: "tt ok" }, (dv === "youtube" || dv === "tiktok") && !cur.refresh_token ? "chưa cấp quyền" : "đã cài") : h("span", { class: "tt" }, "chưa cài")),
          h("div", { class: "hang" }, rows), h("p", {}, nut, " ", them, " ", cur.da_dat ? xoa : null)));
      });
      var s = {
        anh: h("input", { value: cd.anh.ncc + "|" + cd.anh.model, "aria-label": "ảnh" }),
        video: h("input", { value: cd.video.ncc + "|" + cd.video.model }),
        giong: h("input", { value: cd.giong.ncc + "|" + cd.giong.model }),
        v: h("input", { type: "number", min: 0, value: cd.toi_da_video_moi_ngay }),
        d: h("input", { type: "number", min: 0, value: cd.toi_da_bai_dang_moi_ngay })
      };
      var luu = h("button", { class: "btn", onclick: function () {
        function t(x) { var a = x.value.split("|"); return { ncc: (a[0] || "").trim(), model: (a[1] || "").trim() }; }
        api("/cai-dat", { method: "POST", body: { anh: t(s.anh), video: t(s.video), giong: t(s.giong), toi_da_video_moi_ngay: +s.v.value, toi_da_bai_dang_moi_ngay: +s.d.value } })
          .then(function (r) { toast(r.ok ? "Đã lưu cài đặt." : r.error); napTrangThai(); });
      } }, "Lưu cài đặt");
      ra.push(h("div", { class: "card" }, h("h3", {}, "Nhà cung cấp và hạn mức"),
        h("p", { class: "nho" }, "Dạng: nhà cung cấp|tên model. Ảnh: gemini hoặc openai. Video: fal (tên model fal, vd fal-ai/veo3.1/image-to-video). Giọng: elevenlabs. Tên model đổi theo từng nhà cung cấp, kiểm tra tài liệu của họ. 0 là không giới hạn."),
        h("label", {}, "Ảnh"), s.anh, h("label", {}, "Video"), s.video, h("label", {}, "Giọng"), s.giong,
        h("div", { class: "hang" }, h("div", {}, h("label", {}, "Tối đa cảnh video mỗi ngày (mỗi cảnh tốn tiền)"), s.v),
          h("div", {}, h("label", {}, "Tối đa bài đăng mỗi ngày"), s.d)), h("p", {}, luu)));
      main.replaceChildren.apply(main, ra);
    });
  }

  function chonTab() {
    clearInterval(state.timer);
    Array.prototype.forEach.call(document.querySelectorAll("#tabs button"), function (b) { b.classList.toggle("on", b.dataset.tab === state.tab); });
    napTrangThai().then(function (ok) {
      if (!ok) return;
      if (state.tab === "moi") veMoi();
      else if (state.tab === "tu-lieu") veTuLieu();
      else if (state.tab === "lo") veLo();
      else if (state.tab === "ket-noi") veKetNoi();
      else veDanhSach();
    });
  }
  document.getElementById("tabs").addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    state.tab = b.dataset.tab; chonTab();
  });
  chonTab();
})();
