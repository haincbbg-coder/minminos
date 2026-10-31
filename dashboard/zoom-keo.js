/* zoom-keo.js - phóng to, thu nhỏ và kéo xem sơ đồ, hình SVG, ảnh (26.10.313).
 *
 * Trước đây sơ đồ rộng (mermaid) và ảnh lớn bị ép vừa khung: trên điện thoại chữ trong sơ đồ bé
 * xíu mà không phóng to được. Nay khung xem nào gắn file này cũng:
 *   - lăn chuột hoặc chụm hai ngón để phóng to/thu nhỏ quanh đúng chỗ đang chỉ;
 *   - giữ chuột hoặc một ngón để kéo;
 *   - chạm đúp / nháy đúp để phóng nhanh (đang phóng thì về vừa khung);
 *   - nút +, -, Vừa khung ở góc.
 *
 * Dùng: window.MinMinZoom.gan(khung, noiDung) - `khung` là ô cố định kích thước, `noiDung` là phần
 * tử bên trong (svg, img, div). Trả về { vua(), dat(ti_le), go() }.
 */
(function () {
  "use strict";
  if (window.MinMinZoom) return;

  var TI_LE_MIN = 0.1, TI_LE_MAX = 8;

  function chen_css() {
    if (document.getElementById("mm-zk-css")) return;
    var st = document.createElement("style");
    st.id = "mm-zk-css";
    st.textContent =
      ".mm-zk{position:relative;overflow:hidden;touch-action:none;cursor:grab;user-select:none;-webkit-user-select:none}" +
      ".mm-zk.mm-zk-keo{cursor:grabbing}" +
      ".mm-zk-nd{position:absolute;left:0;top:0;transform-origin:0 0;will-change:transform;max-width:none!important;max-height:none!important}" +
      ".mm-zk-nut{position:absolute;right:var(--mm-sp-2,8px);bottom:var(--mm-sp-2,8px);display:flex;gap:var(--mm-sp-1,4px);z-index:2}" +
      ".mm-zk-nut button{min-width:36px;height:36px;padding:0 var(--mm-sp-2,8px);border-radius:var(--mm-r-btn,10px);" +
      "border:1px solid var(--mm-line,rgba(127,127,127,.3));background:var(--mm-panel,#1b1f2a);color:var(--mm-text,#e8eaf0);" +
      "font:500 var(--mm-fs-14,14px)/1 var(--mm-font,inherit);cursor:pointer;box-shadow:var(--mm-out-xs,none)}" +
      ".mm-zk-nut button:hover{border-color:var(--mm-brand,currentColor)}";
    document.head.appendChild(st);
  }

  function chu(k, mac) {
    try { var s = window.t && window.t(k); if (s && s !== k) return s; } catch (e) { /* noop */ }
    return mac;
  }

  /* Kích thước tự nhiên của nội dung (trước khi phóng). SVG lấy theo viewBox nếu không có cỡ rõ. */
  function co_tu_nhien(el) {
    if (el.tagName === "IMG") return { w: el.naturalWidth || el.width || 1, h: el.naturalHeight || el.height || 1 };
    if (el.tagName && el.tagName.toLowerCase() === "svg") {
      var vb = el.viewBox && el.viewBox.baseVal;
      if (vb && vb.width && vb.height) return { w: vb.width, h: vb.height };
    }
    return { w: el.scrollWidth || el.offsetWidth || 1, h: el.scrollHeight || el.offsetHeight || 1 };
  }

  function gan(khung, nd) {
    if (!khung || !nd) return null;
    if (khung.__mmZoom) return khung.__mmZoom;
    chen_css();
    khung.classList.add("mm-zk");
    nd.classList.add("mm-zk-nd");
    if (nd.tagName && nd.tagName.toLowerCase() === "svg") {
      // mermaid đặt max-width theo % khung: cố định cỡ thật để phóng to là to thật, không bị ép lại.
      var c0 = co_tu_nhien(nd);
      nd.style.width = c0.w + "px";
      nd.style.height = c0.h + "px";
    }
    var s = 1, x = 0, y = 0, co = null;

    function ap() { nd.style.transform = "translate(" + x + "px," + y + "px) scale(" + s + ")"; }
    function han(v) { return Math.max(TI_LE_MIN, Math.min(TI_LE_MAX, v)); }

    function vua() {
      co = co_tu_nhien(nd);
      var W = khung.clientWidth || 1, H = khung.clientHeight || 1;
      s = han(Math.min(W / co.w, H / co.h, nd.tagName === "IMG" ? 1 : 2) * 0.98);
      x = (W - co.w * s) / 2;
      y = (H - co.h * s) / 2;
      ap();
    }

    /* Phóng quanh một điểm (toạ độ trong khung): điểm đó đứng yên dưới ngón tay/con trỏ. */
    function phong(he_so, px, py) {
      var moi = han(s * he_so);
      var k = moi / s;
      x = px - (px - x) * k;
      y = py - (py - y) * k;
      s = moi;
      ap();
    }
    function trong_khung(e) {
      var r = khung.getBoundingClientRect();
      return { x: e.clientX - r.left, y: e.clientY - r.top };
    }

    khung.addEventListener("wheel", function (e) {
      e.preventDefault();
      var p = trong_khung(e);
      // deltaMode 1 = theo dòng (chuột Windows), 0 = theo pixel (touchpad, có cả chụm hai ngón = ctrlKey)
      var d = e.deltaY * (e.deltaMode === 1 ? 16 : 1);
      phong(Math.exp(-d * (e.ctrlKey ? 0.01 : 0.0015)), p.x, p.y);
    }, { passive: false });

    var tro = {}, khoang = 0, giua = null, cham_truoc = 0;
    khung.addEventListener("pointerdown", function (e) {
      if (e.target.closest && e.target.closest(".mm-zk-nut")) return;
      try { khung.setPointerCapture(e.pointerId); } catch (er) { /* noop */ }
      tro[e.pointerId] = trong_khung(e);
      khung.classList.add("mm-zk-keo");
      khoang = 0; giua = null;
      if (e.pointerType !== "mouse") {
        var bay = Date.now();
        if (bay - cham_truoc < 300 && Object.keys(tro).length === 1) { phong_nhanh(tro[e.pointerId]); cham_truoc = 0; }
        else cham_truoc = bay;
      }
    });
    khung.addEventListener("pointermove", function (e) {
      var cu = tro[e.pointerId];
      if (!cu) return;
      var p = trong_khung(e);
      var ids = Object.keys(tro);
      if (ids.length >= 2) {
        tro[e.pointerId] = p;
        var a = tro[ids[0]], b = tro[ids[1]];
        var d = Math.hypot(a.x - b.x, a.y - b.y), m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        if (khoang && giua) {
          x += m.x - giua.x; y += m.y - giua.y;
          phong(d / khoang, m.x, m.y);
        }
        khoang = d; giua = m;
        return;
      }
      x += p.x - cu.x; y += p.y - cu.y;
      tro[e.pointerId] = p;
      ap();
    });
    function tha(e) {
      delete tro[e.pointerId];
      khoang = 0; giua = null;
      if (!Object.keys(tro).length) khung.classList.remove("mm-zk-keo");
    }
    khung.addEventListener("pointerup", tha);
    khung.addEventListener("pointercancel", tha);
    khung.addEventListener("dblclick", function (e) {
      if (e.target.closest && e.target.closest(".mm-zk-nut")) return;
      phong_nhanh(trong_khung(e));
    });

    /* Chạm đúp: đang ở vừa khung thì phóng gấp 2.5 quanh chỗ chạm, đang phóng thì về vừa khung. */
    function phong_nhanh(p) {
      var W = khung.clientWidth || 1, H = khung.clientHeight || 1;
      co = co || co_tu_nhien(nd);
      var s_vua = han(Math.min(W / co.w, H / co.h, nd.tagName === "IMG" ? 1 : 2) * 0.98);
      if (s > s_vua * 1.2) vua();
      else phong(2.5, p.x, p.y);
    }

    var nut = document.createElement("div");
    nut.className = "mm-zk-nut";
    [["+", chu("zoom.in", "Phóng to"), function () { phong(1.4, khung.clientWidth / 2, khung.clientHeight / 2); }],
     ["−", chu("zoom.out", "Thu nhỏ"), function () { phong(1 / 1.4, khung.clientWidth / 2, khung.clientHeight / 2); }],
     [chu("zoom.fit", "Vừa khung"), chu("zoom.fit", "Vừa khung"), vua]].forEach(function (b) {
      var el = document.createElement("button");
      el.type = "button";
      el.textContent = b[0];
      el.title = b[1];
      el.setAttribute("aria-label", b[1]);
      el.addEventListener("click", function (e) { e.stopPropagation(); b[2](); });
      nut.appendChild(el);
    });
    khung.appendChild(nut);

    if (nd.tagName === "IMG" && !nd.complete) nd.addEventListener("load", vua, { once: true });
    vua();
    var ro = null;
    try { ro = new ResizeObserver(function () { if (khung.isConnected) vua(); }); ro.observe(khung); } catch (e) { /* noop */ }

    var api = {
      vua: vua,
      dat: function (v) { s = han(v); ap(); },
      ti_le: function () { return s; },
      go: function () { if (ro) ro.disconnect(); nut.remove(); khung.classList.remove("mm-zk"); khung.__mmZoom = null; },
    };
    khung.__mmZoom = api;
    return api;
  }

  window.MinMinZoom = { gan: gan };
})();
