/* Concat: trang ghép máy và theo dõi việc. Mọi chữ đưa vào trang đi qua textContent. */
(function () {
  "use strict";
  var API = "/apps/concat/api";
  var main = document.getElementById("main");
  var TT = { cho: ["Chờ máy nhận", "vang"], dang: ["Đang chạy", "chay"], xong: ["Xong", "ok"], loi: ["Lỗi", "loi"] };

  function h(tag, attrs) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "class") e.className = attrs[k];
      else if (k.slice(0, 2) === "on") e[k] = attrs[k];
      else if (attrs[k] !== false && attrs[k] != null) e.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    });
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null || c === false) continue;
      if (Array.isArray(c)) c.forEach(function (x) { if (x) e.appendChild(typeof x === "string" ? document.createTextNode(x) : x); });
      else e.appendChild(typeof c === "string" ? document.createTextNode(String(c)) : c);
    }
    return e;
  }
  function api(path, method) {
    return fetch(API + path, { method: method || "GET" }).then(function (r) {
      return r.json().catch(function () { return { ok: false, error: "Máy chủ trả dữ liệu lạ." }; });
    });
  }
  function toast(s) {
    var t = document.getElementById("toast");
    t.textContent = s; t.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(function () { t.hidden = true; }, 3500);
  }
  function luc(ts) {
    if (!ts) return "";
    var d = new Date(ts * 1000);
    return d.toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit" });
  }

  function theMay(m) {
    var cc = m.concat || {};
    return h("div", { class: "canh" },
      h("div", { class: "dong" },
        h("strong", null, m.ten),
        h("span", { class: "tt " + (m.online ? (m.concat_ok ? "ok" : "vang") : "loi") },
          m.online ? (m.concat_ok ? "Concat sẵn sàng" : "Cầu nối chạy, Concat chưa mở được") : "Máy đang tắt")),
      h("div", { class: "nho" },
        "Cầu nối " + (m.phien_ban || "?") + (cc.version ? " · Concat " + cc.version : "") +
        " · " + (m.so_cong_cu || 0) + " công cụ · nhịp cuối " + luc(m.nhip_luc)),
      m.thu_muc ? h("div", { class: "nho" }, "Thư mục làm việc: " + m.thu_muc) : null,
      m.loi_concat ? h("div", { class: "nho", style: "color:var(--loi)" }, m.loi_concat) : null,
      h("div", { style: "margin-top:8px" },
        h("button", { class: "btn phu", onclick: function () {
          if (!confirm("Gỡ máy " + m.ten + "? Cầu nối trên máy đó sẽ phải ghép lại.")) return;
          api("/may/" + encodeURIComponent(m.id), "DELETE").then(function (d) { toast(d.ok ? "Đã gỡ máy." : (d.error || "Lỗi")); tai(); });
        } }, "Gỡ máy")));
  }

  var maDangHien = null;   // giữ mã qua các lần làm mới trang (15 giây/lần)
  function veMaGhep(o) {
    var hop = h("div", null);
    function hien(m) {
      hop.textContent = "";
      hop.appendChild(h("div", { class: "nho" }, "Mã ghép (dùng một lần, sống " + m.song_phut + " phút):"));
      hop.appendChild(h("div", { class: "ma-ghep" }, m.ma));
      hop.appendChild(h("div", { class: "nho" }, "Địa chỉ MinMin: " + location.origin));
    }
    if (maDangHien && Date.now() < maDangHien.het) { hien(maDangHien); o.appendChild(hop); return; }
    hop.appendChild(h("button", { class: "btn", onclick: function () {
      api("/ma-ghep", "POST").then(function (d) {
        if (!d.ok) { toast(d.error || "Lỗi"); return; }
        maDangHien = { ma: d.ma, song_phut: d.song_phut, het: Date.now() + d.song_phut * 60000 };
        hien(maDangHien);
      });
    } }, "Tạo mã ghép"));
    o.appendChild(hop);
  }

  function ve(d) {
    main.textContent = "";
    var on = d.may.filter(function (m) { return m.online; }).length;
    document.getElementById("tom-tat").textContent = d.da_ghep ? (on ? on + " máy online" : "Máy nhà đang tắt") : "Chưa ghép máy";

    var c1 = h("section", { class: "card" }, h("h2", null, "Máy có Concat"));
    if (d.may.length) {
      var luoi = h("div", { class: "luoi", style: "grid-template-columns:repeat(auto-fill,minmax(280px,1fr))" });
      d.may.forEach(function (m) { luoi.appendChild(theMay(m)); });
      c1.appendChild(luoi);
    } else {
      c1.appendChild(h("p", { class: "nho" }, "Chưa có máy nào. Làm theo các bước bên dưới để ghép máy tính ở nhà."));
    }
    main.appendChild(c1);

    var c2 = h("section", { class: "card" }, h("h2", null, d.da_ghep ? "Ghép thêm máy" : "Ghép máy ở nhà"),
      h("ol", { class: "buoc" },
        h("li", null, "Cài Concat 0.2.8 trở lên và Python 3.8+ trên máy Windows ở nhà."),
        h("li", null, "Mở Concat > Cài đặt > Tự động hoá > bật \"Script và ứng dụng\" (nên làm, để MinMin không đụng dự án bạn đang sửa)."),
        h("li", null, h("a", { href: API + "/bo-cai.zip" }, "Tải bộ cầu nối"), ", giải nén, bấm đúp ghep-may.bat và nhập mã bên dưới."),
        h("li", null, "Bấm đúp chay.bat và để cửa sổ đó mở.")));
    veMaGhep(c2);
    main.appendChild(c2);

    var c3 = h("section", { class: "card" }, h("h2", null, "Việc gần đây"),
      h("p", { class: "nho" }, "Nhắn MinMin kiểu \"dựng video 15 giây từ 3 clip này, chèn chữ giảm giá rồi xuất dọc\". Mỗi lời gọi công cụ Concat hiện ở đây."));
    if (d.viec.length) {
      var tb = h("table", null, h("tr", null, h("th", null, "#"), h("th", null, "Công cụ"), h("th", null, "Trạng thái"), h("th", null, "Lúc")));
      d.viec.forEach(function (v) {
        var tt = TT[v.trang_thai] || [v.trang_thai, ""];
        tb.appendChild(h("tr", null, h("td", null, String(v.id)),
          h("td", null, v.loai === "lay_tep" ? "Lấy tệp về bộ não" : v.cong_cu,
            v.loi ? h("div", { class: "nho", style: "color:var(--loi)" }, v.loi) : null),
          h("td", null, h("span", { class: "tt " + tt[1] }, tt[0])),
          h("td", { class: "nho" }, luc(v.tao_luc))));
      });
      c3.appendChild(tb);
    } else {
      c3.appendChild(h("p", { class: "nho" }, "Chưa có việc nào."));
    }
    main.appendChild(c3);
  }

  function tai() {
    api("/trang-thai").then(function (d) {
      if (!d.ok) { main.textContent = d.error || "Không tải được."; return; }
      ve(d);
    });
  }
  tai();
  setInterval(function () { if (!document.hidden) tai(); }, 15000);
})();
