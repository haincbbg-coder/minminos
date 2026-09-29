// ============================================================================
// MinMin OS - "Thiên hà thần kinh" cho khoang não (lớp phủ lên graph.js).
//
// KHÔNG sửa graph.js: file này nạp SAU graph.js, vá JavisGraph.prototype để
//   - gom note cùng thư mục thành từng CỤM sáng xếp vòng quanh một LÕI trắng rực,
//   - vẽ bụi sao, vỏ cầu hạt, vòng quỹ đạo, tia sao chổi bắn ra từ lõi (kiểu ODIN),
//   - giữ nguyên mọi tương tác cũ: rê chuột rọi sáng, bấm mở note, timelapse.
// Chế độ: localStorage "mm.galaxy" = "3d" (mặc định, xem minmin-galaxy3d.js) | "2d" | "off".
// Nút tròn góc khoang não chuyển vòng 3D -> 2D -> tắt -> 3D.
// ============================================================================
(function () {
  "use strict";
  if (typeof window === "undefined" || !window.JavisGraph) return;

  var KEY = "mm.galaxy";
  var CHE_DO = ["3d", "2d", "off"];
  var TEN = { "3d": "Thiên hà 3D", "2d": "Thiên hà 2D", off: "Đồ thị gốc" };
  function cheDo() {
    var v = "3d";
    try { v = localStorage.getItem(KEY) || "3d"; } catch (e) {}
    return CHE_DO.indexOf(v) >= 0 ? v : "3d";
  }
  // Nút chuyển chế độ: luôn có, kể cả khi đang ở đồ thị gốc, để quay lại được.
  function nutCheDo() {
    var c = document.querySelector(".hud-center");
    if (!c || c.querySelector(".mm-galaxy-off")) return;
    var hien = cheDo(), sau = CHE_DO[(CHE_DO.indexOf(hien) + 1) % CHE_DO.length];
    var nut = document.createElement("button");
    nut.className = "brain-overlay-toggle mm-galaxy-off";
    nut.type = "button";
    nut.title = "Đang xem: " + TEN[hien] + ". Bấm để chuyển sang " + TEN[sau];
    nut.innerHTML = window.ic ? window.ic(hien === "off" ? "sparkles" : (hien === "3d" ? "layers" : "sparkle")) : "";
    nut.addEventListener("click", function () {
      try { localStorage.setItem(KEY, sau); } catch (e) {}
      location.reload();
    });
    c.appendChild(nut);
  }
  if (cheDo() === "off") {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", nutCheDo);
    else nutCheDo();
    return;
  }

  var giamChuyenDong = false;
  try { giamChuyenDong = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}

  document.documentElement.classList.add("mm-galaxy");

  // Bảng màu cụm lấy cảm hứng từ ảnh ODIN: cam hồng, vàng kim, oải hương, ngọc lam,
  // tím, đào, bạc, hồng - rực trên nền đen, cộng dồn (lighter) thành quầng.
  var MAU = ["#ff8a5c", "#ffc93c", "#a99bff", "#2fe0b8", "#c77dff",
    "#ff9e7a", "#dfe6ff", "#ff6fa8", "#7fc8ff", "#b6f06a", "#ffd59e", "#9aa7c7"];
  window.MinMinGalaxyColors = MAU;

  var TAU = Math.PI * 2;
  function now() { return (typeof performance !== "undefined" ? performance.now() : Date.now()); }
  function rgba(hex, a) {
    var m = String(hex).replace("#", "");
    return "rgba(" + parseInt(m.substr(0, 2), 16) + "," + parseInt(m.substr(2, 2), 16) + "," +
      parseInt(m.substr(4, 2), 16) + "," + a + ")";
  }
  // Số giả ngẫu nhiên có hạt giống: cùng brain thì bụi sao đứng cùng chỗ mỗi lần mở.
  function rng(seed) {
    var s = seed >>> 0 || 1;
    return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  }
  function gauss(r) { return Math.sqrt(-2 * Math.log(r() || 1e-9)) * Math.cos(TAU * r()); }

  var _spr = {};
  function sprite(color) {
    if (_spr[color]) return _spr[color];
    var s = 64, cv = document.createElement("canvas"); cv.width = cv.height = s;
    var c = cv.getContext("2d");
    var g = c.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.18, rgba(color, 0.95));
    g.addColorStop(0.45, rgba(color, 0.28));
    g.addColorStop(1, rgba(color, 0));
    c.fillStyle = g; c.fillRect(0, 0, s, s);
    return (_spr[color] = cv);
  }

  var P = window.JavisGraph.prototype;
  var goc = { load: P.load, _drawNode: P._drawNode, _nhipVe: P._nhipVe, _recolor: P._recolor };

  // ---------- Lực gom cụm: mỗi thư mục một "neo" trên vòng tròn quanh lõi ----------
  function lucCum(self) {
    var nodes = [];
    function f(alpha) {
      var neo = self.__mmNeo || {};
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i], a = neo[n.__cat];
        if (!a) continue;
        n.vx += (a.x - n.x) * 0.09 * alpha;
        n.vy += (a.y - n.y) * 0.09 * alpha;
      }
    }
    f.initialize = function (ns) { nodes = ns; };
    return f;
  }

  function dungNeo(self, nodes) {
    var cats = [], dem = {};
    nodes.forEach(function (n) {
      if (!(n.__cat in dem)) { dem[n.__cat] = 0; cats.push(n.__cat); }
      dem[n.__cat]++;
    });
    var R = 70 + 14 * Math.sqrt(nodes.length);
    var neo = {};
    cats.forEach(function (c, i) {
      var ang = -Math.PI / 2 + (i / Math.max(1, cats.length)) * TAU;
      // Cụm to đẩy ra xa hơn một chút cho khỏi chồng lên lõi.
      var rr = R * (0.8 + 0.25 * Math.min(1, dem[c] / 20));
      neo[c] = { x: Math.cos(ang) * rr, y: Math.sin(ang) * rr, n: dem[c], i: i };
    });
    self.__mmNeo = neo;
    self.__mmR = R;
    dungBui(self, cats, dem, nodes.length);
  }

  // ---------- Bụi sao: mây hạt quanh mỗi cụm + vỏ cầu hạt + tia sao chổi ----------
  function dungBui(self, cats, dem, tong) {
    var r = rng(tong * 7919 + cats.length * 104729);
    var R = self.__mmR;
    var bui = [];
    cats.forEach(function (c) {
      // Brain ít note vẫn phải ra "tinh vân": số hạt và độ loang có sàn theo bán kính vòng.
      var k = Math.max(tong < 40 ? 150 : 70, Math.min(260, 60 + dem[c] * 14));
      var tr = Math.max(R * 0.13, 14 + Math.sqrt(dem[c]) * 7);
      for (var i = 0; i < k; i++) {
        bui.push({ cat: c, dx: gauss(r) * tr, dy: gauss(r) * tr * 0.8,
          s: 0.5 + r() * 1.3, a: 0.25 + r() * 0.6, ph: r() * TAU });
      }
    });
    // Vỏ cầu: hạt phân bố trên mặt cầu, chiếu xuống 2D, quay chậm quanh trục đứng.
    var vo = [];
    var nv = giamChuyenDong ? 420 : 900;
    for (var j = 0; j < nv; j++) {
      var u = r() * 2 - 1, th = r() * TAU;
      vo.push({ u: u, th: th, rr: R * (1.55 + r() * 0.35), s: 0.4 + r() * 1.1,
        a: 0.12 + r() * 0.45, c: MAU[(r() * MAU.length) | 0], w: r() < 0.55 });
    }
    var tia = [];
    for (var t = 0; t < 22; t++) {
      tia.push({ ang: r() * TAU, len: R * (2.2 + r() * 3.5), sp: 0.05 + r() * 0.12,
        off: r(), w: 0.4 + r() * 0.9 });
    }
    self.__mmBui = bui; self.__mmVo = vo; self.__mmTia = tia;
  }

  function tamCum(self) {
    var d = self.graph.graphData(), t = {};
    d.nodes.forEach(function (n) {
      if (n.x == null) return;
      var o = t[n.__cat] || (t[n.__cat] = { x: 0, y: 0, n: 0 });
      o.x += n.x; o.y += n.y; o.n++;
    });
    Object.keys(t).forEach(function (k) { t[k].x /= t[k].n; t[k].y /= t[k].n; });
    return t;
  }

  // ---------- Lớp nền: vẽ TRƯỚC node, trong toạ độ đồ thị ----------
  function veNen(self, ctx, k) {
    if (!self.__mmBui) return;
    var t = now() / 1000;
    var R = self.__mmR || 120;
    var nghi = self._thinking ? 1 : 0;
    var am = self.level || 0;
    var px = 1 / k;                                     // 1 pixel màn hình theo toạ độ đồ thị

    ctx.save();
    ctx.globalCompositeOperation = "lighter";

    // Tinh vân mờ sau lõi
    var neb = ctx.createRadialGradient(0, 0, 0, 0, 0, R * 2.1);
    neb.addColorStop(0, "rgba(190,160,255,0.16)");
    neb.addColorStop(0.35, "rgba(110,80,200,0.07)");
    neb.addColorStop(1, "rgba(20,10,40,0)");
    ctx.fillStyle = neb;
    ctx.beginPath(); ctx.arc(0, 0, R * 2.1, 0, TAU); ctx.fill();

    // Vỏ cầu hạt quay chậm
    var rot = giamChuyenDong ? 0 : t * 0.045;
    var vo = self.__mmVo;
    for (var i = 0; i < vo.length; i++) {
      var p = vo[i], sq = Math.sqrt(1 - p.u * p.u), th = p.th + rot;
      var x = Math.cos(th) * sq * p.rr, z = Math.sin(th) * sq, y = p.u * p.rr * 0.92;
      var sau = (z + 1) / 2;                           // 0 = phía sau, 1 = phía trước
      ctx.globalAlpha = p.a * (0.35 + 0.65 * sau);
      ctx.fillStyle = p.w ? "#e9e4ff" : p.c;
      var s = p.s * px * (0.7 + 0.6 * sau);
      ctx.fillRect(x - s, y - s, s * 2, s * 2);
    }

    // Mây hạt quanh từng cụm (bám theo tâm cụm thật)
    var tam = tamCum(self), bui = self.__mmBui, idx = window.__javisCatIdx || {};
    for (var b = 0; b < bui.length; b++) {
      var q = bui[b], c = tam[q.cat];
      if (!c) continue;
      var mau = MAU[(idx[q.cat] || 0) % MAU.length];
      var nh = giamChuyenDong ? 1 : (0.7 + 0.3 * Math.sin(t * 1.3 + q.ph));
      var loc = self._catFilter && self._catFilter !== q.cat ? 0.15 : 1;
      ctx.globalAlpha = q.a * nh * loc;
      ctx.fillStyle = mau;
      var ss = q.s * px;
      ctx.fillRect(c.x + q.dx - ss, c.y + q.dy - ss, ss * 2, ss * 2);
    }
    // Quầng cụm
    Object.keys(tam).forEach(function (cat) {
      var c = tam[cat], mau = MAU[(idx[cat] || 0) % MAU.length];
      var rr = 26 + Math.sqrt(c.n) * 9;
      var g = ctx.createRadialGradient(c.x, c.y, 0, c.x, c.y, rr);
      g.addColorStop(0, rgba(mau, self._catFilter && self._catFilter !== cat ? 0.04 : 0.22));
      g.addColorStop(1, rgba(mau, 0));
      ctx.globalAlpha = 1; ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(c.x, c.y, rr, 0, TAU); ctx.fill();
    });

    // Tia sao chổi từ lõi bắn ra
    var tia = self.__mmTia, tocDo = 1 + nghi * 2.2 + am * 2;
    ctx.lineCap = "round";
    for (var j = 0; j < tia.length; j++) {
      var r0 = tia[j], ca = Math.cos(r0.ang), sa = Math.sin(r0.ang);
      var ph = giamChuyenDong ? r0.off : ((t * r0.sp * tocDo + r0.off) % 1);
      var dai = r0.len;
      // thân tia: vạch mảnh mờ dần
      var gr = ctx.createLinearGradient(0, 0, ca * dai, sa * dai);
      gr.addColorStop(0, "rgba(255,255,255,0.0)");
      gr.addColorStop(0.15, "rgba(235,230,255,0.22)");
      gr.addColorStop(1, "rgba(235,230,255,0)");
      ctx.globalAlpha = 0.7;
      ctx.strokeStyle = gr; ctx.lineWidth = r0.w * px;
      ctx.beginPath(); ctx.moveTo(ca * R * 0.15, sa * R * 0.15); ctx.lineTo(ca * dai, sa * dai); ctx.stroke();
      // đầu sao chổi chạy dọc tia
      var hx = ca * dai * ph, hy = sa * dai * ph, duoi = 26 * px + dai * 0.06;
      var gh = ctx.createLinearGradient(hx - ca * duoi, hy - sa * duoi, hx, hy);
      gh.addColorStop(0, "rgba(255,255,255,0)");
      gh.addColorStop(1, "rgba(255,255,255,0.95)");
      ctx.globalAlpha = Math.sin(ph * Math.PI);
      ctx.strokeStyle = gh; ctx.lineWidth = (1.2 + r0.w) * px;
      ctx.beginPath(); ctx.moveTo(hx - ca * duoi, hy - sa * duoi); ctx.lineTo(hx, hy); ctx.stroke();
    }

    // Vòng quỹ đạo nghiêng quanh lõi
    ctx.globalAlpha = 0.35 + 0.25 * nghi;
    ctx.strokeStyle = "rgba(230,225,255,0.6)";
    ctx.lineWidth = 0.8 * px;
    for (var v = 0; v < 2; v++) {
      ctx.save();
      ctx.rotate((giamChuyenDong ? 0 : t * (v ? -0.12 : 0.08)) + v * 0.9);
      ctx.beginPath(); ctx.ellipse(0, 0, R * (0.28 + v * 0.1), R * (0.13 + v * 0.06), 0, 0, TAU); ctx.stroke();
      ctx.restore();
    }
    ctx.restore();
  }

  // ---------- Lớp trên: lõi trắng rực + lens flare (vẽ SAU node) ----------
  function veLoi(self, ctx, k) {
    if (!self.__mmBui) return;
    var t = now() / 1000, R = self.__mmR || 120, px = 1 / k;
    var nghi = self._thinking ? 1 : 0, am = self.level || 0;
    var dap = giamChuyenDong ? 1 : (1 + 0.06 * Math.sin(t * 1.6) + 0.25 * am + 0.12 * nghi * Math.sin(t * 5));
    var rl = R * 0.34 * dap;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    var g = ctx.createRadialGradient(0, 0, 0, 0, 0, rl);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.12, "rgba(255,245,255,0.9)");
    g.addColorStop(0.35, "rgba(220,190,255,0.35)");
    g.addColorStop(1, "rgba(160,120,255,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, rl, 0, TAU); ctx.fill();
    // lens flare ngang + dọc mảnh
    var fl = R * 0.9 * dap;
    [[1, 0, 1], [0, 1, 0.45]].forEach(function (d) {
      var gl = ctx.createLinearGradient(-fl * d[0], -fl * d[1], fl * d[0], fl * d[1]);
      gl.addColorStop(0, "rgba(255,255,255,0)");
      gl.addColorStop(0.5, "rgba(255,255,255," + (0.55 * d[2]) + ")");
      gl.addColorStop(1, "rgba(255,255,255,0)");
      ctx.strokeStyle = gl; ctx.lineWidth = 1.4 * px;
      ctx.beginPath(); ctx.moveTo(-fl * d[0], -fl * d[1]); ctx.lineTo(fl * d[0], fl * d[1]); ctx.stroke();
    });
    ctx.restore();
  }

  // ---------- Vá các phương thức ----------
  P.load = async function () {
    var data = await goc.load.apply(this, arguments);
    var self = this;
    if (this.graph && !this.__mmHook) {
      this.__mmHook = true;
      try { this.graph.d3Force("cluster", lucCum(self)); } catch (e) {}
      try { this.graph.d3Force("charge").strength(-38); } catch (e) {}
      try { var lf = this.graph.d3Force("link"); if (lf) lf.distance(18).strength(0.05); } catch (e) {}
      this.graph
        .onRenderFramePre(function (ctx, k) { try { veNen(self, ctx, k); } catch (e) {} })
        .onRenderFramePost(function (ctx, k) { try { veLoi(self, ctx, k); } catch (e) {} })
        .linkColor(function (l) {
          if (self._hoverId != null) {
            var s = (l.source && l.source.id) || l.source, tg = (l.target && l.target.id) || l.target;
            return (s === self._hoverId || tg === self._hoverId) ? "rgba(255,255,255,0.55)" : "rgba(200,190,255,0.02)";
          }
          return "rgba(200,190,255,0.06)";
        });
    }
    if (this.graph) {
      dungNeo(this, this.graph.graphData().nodes);
      try { this.graph.d3ReheatSimulation(); } catch (e) {}
    }
    this._nhipVe();
    return data;
  };

  P._drawNode = function (n, ctx, scale) {
    if (n.x == null || n.y == null) return;
    var t = now();
    var ent = this._t0 ? Math.min(1, (t - this._t0) / 900) : 1;
    var hov = this._hoverId != null, isH = n.id === this._hoverId, isN = hov && this._nbrs.has(n.id);
    var dim = (hov && !isH && !isN) || (this._catFilter && n.__cat !== this._catFilter && !isH && !isN);
    var mau = MAU[(n.__catIdx || 0) % MAU.length];
    var tho = giamChuyenDong ? 1 : 1 + 0.18 * Math.sin(t / 480 + (n.__ph || 0));   // nhấp nháy như sao
    var born = 1;
    if (n.__born) { var age = (t - n.__born) / 500; born = age < 1 ? age : 1; if (age >= 1) n.__born = 0; }
    var r = (1.6 + Math.sqrt(Math.min(55, n.links || 0)) * 1.1) * (isH ? 1.8 : 1) * tho * (0.4 + 0.6 * born);
    ctx.save();
    ctx.globalCompositeOperation = "lighter";
    ctx.globalAlpha = (dim ? 0.12 : 1) * ent;
    var gs = r * 5.5;
    ctx.drawImage(sprite(isH ? "#ffffff" : mau), n.x - gs / 2, n.y - gs / 2, gs, gs);
    ctx.restore();
    if (isH && n.label) {
      var fs = Math.max(9, 12 / scale);
      ctx.font = fs + "px 'JetBrains Mono', ui-monospace, Menlo, monospace";
      ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.lineWidth = 3 / scale; ctx.strokeStyle = "rgba(3,3,10,0.9)";
      ctx.strokeText(n.label, n.x, n.y + r + 4);
      ctx.fillStyle = "#f2efff"; ctx.fillText(n.label, n.x, n.y + r + 4);
    }
  };

  // Hiệu ứng thiên hà cần vẽ liên tục; vẫn dừng khi tab ẩn hoặc người dùng xin giảm chuyển động.
  P._nhipVe = function () {
    if (giamChuyenDong) return goc._nhipVe.apply(this, arguments);
    var can = !document.hidden;
    if (can === this._veLienTuc) return;
    this._veLienTuc = can;
    if (this.graph) { try { this.graph.autoPauseRedraw(!can); } catch (e) {} }
  };
  document.addEventListener("visibilitychange", function () {
    var g = window.__javisGraph; if (g) g._nhipVe();
  });

  P._recolor = function () {
    goc._recolor && goc._recolor.apply(this, arguments);
    try { this.graph && this.graph.linkColor(this.graph.linkColor()); } catch (e) {}
  };

  // Nhãn thư mục (app.js) tô theo bảng màu thiên hà cho khớp cụm.
  window.JavisCatColorAt = function (i) { return MAU[(i || 0) % MAU.length]; };

  // ---------- HUD chữ kiểu ODIN ở góc khoang não ----------
  function dungHud() {
    var c = document.querySelector(".hud-center");
    if (!c || c.querySelector(".mm-hud")) return;
    var h = document.createElement("div");
    h.className = "mm-hud";
    h.innerHTML =
      '<div class="mm-hud-l1">MINMIN OS · MẠNG TRÍ TUỆ VẬN HÀNH · LOCAL</div>' +
      '<div class="mm-hud-l2">STATE <b id="mmHudState">IDLE DRIFT</b></div>' +
      '<div class="mm-hud-l3">DESIGNATION CONFIRMED</div>';
    c.appendChild(h);
    var f = document.createElement("div");
    f.className = "mm-hud-foot";
    f.innerHTML = 'REFLEX online · <span id="mmHudNodes">-</span> nodes · <span id="mmHudCats">-</span> cụm';
    c.appendChild(f);
    nutCheDo();

    var orb = document.getElementById("orbState");
    function capNhat() {
      var g = window.__javisGraph, st = document.getElementById("mmHudState");
      if (st) {
        var txt = orb ? (orb.textContent || "").trim() : "";
        st.textContent = g && g._thinking ? "THINKING" : (g && g.level > 0.05 ? "SPEAKING" : (txt && txt !== "SẴN SÀNG" ? txt.toUpperCase() : "IDLE DRIFT"));
      }
      if (g && g.graph) {
        var d = g.graph.graphData();
        var en = document.getElementById("mmHudNodes"), ec = document.getElementById("mmHudCats");
        if (en) en.textContent = d.nodes.length;
        if (ec) ec.textContent = Object.keys(g.__mmNeo || {}).length;
      }
    }
    setInterval(capNhat, 800);
    capNhat();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", dungHud);
  else dungHud();

  window.MinMinGalaxy = {
    on: true,
    cheDo: cheDo,
    dat: function (v) { try { localStorage.setItem(KEY, v); } catch (e) {} location.reload(); },
  };
})();
