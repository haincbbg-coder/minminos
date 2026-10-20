(function () {
  "use strict";
  var main = document.getElementById("main");
  var NHAN = { cho_duyet: ["chờ duyệt", "vang"], cho_chay: ["chờ máy nhà", "chay"], dang_chay: ["đang chạy", "chay"],
               xong: ["xong", "ok"], loi: ["lỗi", "loi"], bo: ["đã bỏ", ""] };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function toast(s) { var t = document.getElementById("toast"); t.textContent = s; t.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(function () { t.hidden = true; }, 3500); }
  function api(path, o) {
    o = o || {};
    if (o.body && typeof o.body !== "string") { o.body = JSON.stringify(o.body); o.headers = { "content-type": "application/json" }; }
    return fetch(path, Object.assign({ credentials: "same-origin" }, o)).then(function (r) {
      return r.json().then(function (d) { if (!r.ok || d.ok === false) throw new Error(d.error || ("lỗi " + r.status)); return d; });
    });
  }
  function gio(t) { return t ? new Date(t * 1000).toLocaleString("vi-VN") : ""; }

  function render(d) {
    var may = d.may || [], nick = d.nick || [], viec = d.viec || [], gh = d.gioi_han || {};
    var h = "";
    h += '<div class="card"><div class="dong"><h2>Máy ở nhà</h2><div>' +
         '<button class="btn phu" id="tai">Tải MinMin Worker</button> <button class="btn" id="ma">Tạo mã ghép</button></div></div>';
    h += '<div id="o-ma"></div>';
    if (!may.length) h += '<p class="nho">Chưa có máy nào. Tải Worker về máy có GPM Login, chạy cai-dat.bat, rồi ghep-may.bat với mã 6 số.</p>';
    may.forEach(function (m) {
      h += '<div class="dong viec"><div><b>' + esc(m.ten) + '</b> <span class="tt ' + (m.online ? "ok" : "loi") + '">' +
           (m.online ? "đang bật" : "ngoại tuyến") + '</span> <span class="tt ' + (m.driver_ok ? "ok" : "vang") + '">' +
           (m.driver_ok ? "GPM ok" : "GPM chưa sẵn sàng") + '</span><div class="nho">' + m.so_nick + ' nick · Worker ' +
           esc(m.phien_ban || "?") + ' · nhịp cuối ' + gio(m.nhip_luc) + (m.loi_driver ? " · " + esc(m.loi_driver) : "") +
           '</div></div><button class="btn phu" data-go="' + esc(m.id) + '">Gỡ máy</button></div>';
    });
    h += '</div>';

    h += '<div class="card"><h2>Đăng thử một bài</h2><p class="nho">Thường bố chỉ cần nhắn Telegram, MinMin tự viết bài. Form này để thử nhanh.</p>' +
         '<label>Nick (tên profile GPM)</label><input id="f-nick" list="ds-nick" placeholder="gõ để chọn">' +
         '<datalist id="ds-nick">' + nick.filter(function (n) { return n.trinh_duyet !== "firefox"; }).map(function (n) {
           return '<option value="' + esc(n.ten) + '">'; }).join("") + '</datalist>' +
         '<label>Nơi đăng (link Trang/nhóm, bỏ trống = tường của nick)</label><input id="f-noi" placeholder="https://www.facebook.com/...">' +
         '<label>Nội dung</label><textarea id="f-nd"></textarea>' +
         '<p><button class="btn" id="f-tao">Tạo bài (chờ duyệt)</button></p></div>';

    h += '<div class="card"><h2>Việc gần đây</h2>';
    if (!viec.length) h += '<p class="nho">Chưa có việc nào.</p>';
    viec.forEach(function (v) {
      var n = NHAN[v.trang_thai] || [v.trang_thai, ""];
      var ts = v.tham_so || {};
      h += '<div class="viec"><div class="dong"><div><b>#' + v.id + '</b> ' + esc(v.nhan_ky_nang) + ' · ' + esc(v.nick_ten) +
           ' <span class="tt ' + n[1] + '">' + n[0] + '</span></div><div class="nho">' + gio(v.tao_luc) + '</div></div>';
      if (ts.noi_dang) h += '<div class="nho">Nơi đăng: ' + esc(ts.noi_dang) + '</div>';
      if ((ts.tep || []).length) h += '<div class="nho">Tệp: ' + ts.tep.map(function (t) { return esc(t.ten); }).join(", ") + '</div>';
      if (ts.noi_dung) h += '<pre>' + esc(ts.noi_dung) + '</pre>';
      if (v.thong_diep) h += '<div class="nho">Máy nhà báo: ' + esc(v.thong_diep) + '</div>';
      if (v.trang_thai === "cho_duyet") h += '<p><button class="btn" data-duyet="' + v.id + '">Duyệt đăng</button> ' +
           '<button class="btn phu" data-bo="' + v.id + '">Bỏ</button></p>';
      if ((v.buoc || []).length) h += '<details><summary class="nho">Các bước</summary><div class="nhat-ky">' +
           v.buoc.map(esc).join("\n") + '</div></details>';
      if (v.co_anh) h += '<img loading="lazy" src="/doi-social/anh/' + v.id + '.png" alt="ảnh chụp kết quả">';
      h += '</div>';
    });
    h += '</div>';

    h += '<div class="card"><h2>Giới hạn chống checkpoint</h2><div class="hang">' +
         '<div><label>Bài tối đa mỗi nick mỗi ngày</label><input id="g-bai" type="number" min="1" max="50" value="' + (gh.bai_moi_ngay || 5) + '"></div>' +
         '<div><label>Nghỉ giữa hai lượt của một nick (phút)</label><input id="g-nghi" type="number" min="0" value="' + (gh.nghi_phut || 20) + '"></div>' +
         '</div><p><button class="btn phu" id="g-luu">Lưu giới hạn</button></p></div>';

    h += '<div class="card"><h2>Nick trên các máy (' + nick.length + ')</h2><div class="bang-nick">' +
         nick.map(function (n) { return '<div>' + esc(n.ten) + ' <span class="nho">· ' + esc(n.trinh_duyet || "?") +
           (n.co_proxy ? " · có proxy" : " · không proxy") + (n.nhom ? " · " + esc(n.nhom) : "") + '</span></div>'; }).join("") +
         '</div>' + (nick.length && !nick.some(function (n) { return n.co_proxy; }) ?
         '<p class="nho">Lưu ý: chưa nick nào có proxy riêng, tất cả dùng chung IP nhà. Chạy nhiều nick cùng IP dễ bị Facebook gom lại; nên gắn proxy riêng cho từng nick trong GPM.</p>' : "") +
         '</div>';
    main.innerHTML = h;
  }

  function nap() { return api("/doi-social/trang-thai").then(render).catch(function (e) {
    main.innerHTML = '<div class="card">' + esc(e.message) + '</div>'; }); }

  main.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    if (b.id === "tai") { location.href = "/doi-social/tai-worker.zip"; return; }
    if (b.id === "ma") {
      api("/doi-social/ma-ghep", { method: "POST" }).then(function (d) {
        document.getElementById("o-ma").innerHTML = '<p>Mã ghép (sống ' + d.song_phut + ' phút): <span class="ma-ghep">' + esc(d.ma) +
          '</span></p><p class="nho">Địa chỉ MinMin: ' + esc(location.origin) + '</p>';
      }).catch(function (x) { toast(x.message); });
      return;
    }
    if (b.dataset.go) { if (!confirm("Gỡ máy này? Worker trên máy đó sẽ phải ghép lại.")) return;
      api("/doi-social/may/" + encodeURIComponent(b.dataset.go), { method: "DELETE" }).then(nap); return; }
    if (b.dataset.duyet || b.dataset.bo) {
      var id = b.dataset.duyet || b.dataset.bo;
      api("/doi-social/viec/" + id + "/duyet", { method: "POST", body: { dong_y: !!b.dataset.duyet } })
        .then(function () { toast(b.dataset.duyet ? "Đã duyệt, máy nhà sẽ đăng" : "Đã bỏ"); nap(); }).catch(function (x) { toast(x.message); });
      return;
    }
    if (b.id === "f-tao") {
      api("/doi-social/viec", { method: "POST", body: { nick: document.getElementById("f-nick").value,
        noi_dang: document.getElementById("f-noi").value, noi_dung: document.getElementById("f-nd").value } })
        .then(function (d) { toast("Đã tạo bài #" + d.viec.id + ", chờ duyệt"); nap(); }).catch(function (x) { toast(x.message); });
      return;
    }
    if (b.id === "g-luu") {
      api("/doi-social/gioi-han", { method: "POST", body: { bai_moi_ngay: +document.getElementById("g-bai").value,
        nghi_phut: +document.getElementById("g-nghi").value } }).then(function () { toast("Đã lưu"); nap(); });
    }
  });
  nap();
  setInterval(function () { if (!document.hidden && !document.activeElement.matches("input,textarea")) nap(); }, 15000);
})();
