// ============================================================================
// MinMin OS - QUẢ CẦU TRI THỨC 3D cho khoang não (0.64.95).
//
// Chủ repo 30/09: muốn đồ thị là MỘT KHỐI CẦU 3D thật (như ảnh mẫu): ghi chú phủ thành quả cầu,
// dây nối xuyên qua lòng cầu cho thấy kiến thức liên kết chặt, xoay / phóng to được. KHÔNG còn
// kiểu "thiên hà" (lõi cam, vòng quỹ đạo, sao nền, mây cụm). File này giữ tên cũ để không đổi
// index.html; phần dưới là mô tả gốc về cách bọc JavisGraph.
//
// Nạp SAU graph.js và minmin-galaxy.js. Không sửa graph.js: chỉ bọc JavisGraph.prototype.load,
// nếu máy có WebGL và tải được thư viện 3D thì dựng đồ thị bằng ForceGraph3D, không thì trả
// về đúng bản thiên hà 2D như cũ. Mọi hàm công khai khác của JavisGraph (pause, wake, resize,
// refit, addOrUpdate, timelapse, spotlightCategory...) vẫn chạy vì ForceGraph3D có cùng tên API.
//
// Thao tác: kéo chuột trái để XOAY, lăn chuột để PHÓNG TO / THU NHỎ, kéo chuột phải để DỜI,
// nắm một chấm để KÉO THẢ, chỉ chuột vào chấm để xem THẺ GHI CHÚ, bấm chấm để mở note.
// Chế độ: localStorage "mm.galaxy" = "3d" (mặc định) | "2d" | "off", đọc MỖI lần dựng đồ thị
// nên nút chuyển đổi được tại chỗ (xem MinMinGalaxy.dat trong minmin-galaxy.js).
// Tông sáng của app: hạt vẽ chồng thường (cộng sáng trên nền trắng sẽ mất hút), màu đậm hơn.
// ============================================================================
(function () {
  "use strict";
  if (typeof window === "undefined" || !window.JavisGraph || !window.MinMinGalaxyColors) return;

  var KEY = "mm.galaxy";
  // 0.64.95: luôn dựng quả cầu 3D (máy không có WebGL thì tự lùi về đồ thị gốc 2D).
  function cheDo() { return "3d"; }
  function sang() { return window.MinMinGalaxyIsLight ? window.MinMinGalaxyIsLight() : false; }
  // Bảng màu theo ảnh mẫu: phần lớn chấm nâu mực, xen xanh ngọc, đỏ gạch, tím, cam, lục.
  var MAU_SANG = ["#4b3a2f", "#1f6f78", "#b8432f", "#6a4bd6", "#c47a14", "#2f7d4a", "#8c3d8f", "#3d5a99", "#7a5a3a", "#a13c5a"];
  var MAU_TOI = ["#e8dccf", "#5fd3c8", "#ff8a6b", "#b39bff", "#ffc36b", "#7fe0a0", "#e79be8", "#8fb0ff", "#d9b48a", "#ff8fb0"];
  function bang() { return sang() ? MAU_SANG : MAU_TOI; }
  function mauCum(i) { var M = bang(); return M[(i || 0) % M.length]; }
  var VENDOR = typeof window.MinMinVendorBase === "string" ? window.MinMinVendorBase : "/static/vendor/";
  var THU_VIEN = VENDOR + "minmin-3d-bundle-1.80.0.min.js?v=1";
  var TAU = Math.PI * 2;
  var giamChuyenDong = false;
  try { giamChuyenDong = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}

  function now() { return (typeof performance !== "undefined" ? performance.now() : Date.now()); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function rng(seed) {
    var s = seed >>> 0 || 1;
    return function () { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
  }
  function gauss(r) { return Math.sqrt(-2 * Math.log(r() || 1e-9)) * Math.cos(TAU * r()); }
  function idCua(x) { return (x && x.id != null) ? x.id : x; }

  function coWebGL() {
    try {
      var c = document.createElement("canvas");
      return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch (e) { return false; }
  }

  var _nap = null;
  function napThuVien() {
    if (window.ForceGraph3D && window.MinMinTHREE) return Promise.resolve(true);
    if (_nap) return _nap;
    _nap = new Promise(function (ok) {
      var s = document.createElement("script");
      s.src = THU_VIEN;
      s.onload = function () { ok(!!(window.ForceGraph3D && window.MinMinTHREE)); };
      s.onerror = function () { console.warn("[MinMin 3D] không tải được " + THU_VIEN + ", dùng bản 2D"); ok(false); };
      document.head.appendChild(s);
    });
    return _nap;
  }

  // ---------- Hạt sáng: một texture quầng tròn cho mỗi màu ----------
  var _tex = {};
  function texQuang(mau) {
    var L = sang(), key = mau + (L ? "|L" : "|D");
    if (_tex[key]) return _tex[key];
    var T = window.MinMinTHREE, s = 64, cv = document.createElement("canvas");
    cv.width = cv.height = s;
    var c = cv.getContext("2d");
    var g = c.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
    if (L) {
      // Chấm mực đặc, viền mềm (không phải quầng sáng) - giống chấm trên giấy của ảnh mẫu
      g.addColorStop(0, mau);
      g.addColorStop(0.5, mau);
      g.addColorStop(0.72, mau + "70");
    } else {
      g.addColorStop(0, "rgba(255,255,255,1)");
      g.addColorStop(0.16, mau);
      g.addColorStop(0.42, mau + "55");
    }
    g.addColorStop(1, mau + "00");
    c.fillStyle = g; c.fillRect(0, 0, s, s);
    var t = new T.CanvasTexture(cv);
    try { t.colorSpace = T.SRGBColorSpace; } catch (e) {}
    return (_tex[key] = t);
  }
  // Bundle 3D chỉ xuất AdditiveBlending; NormalBlending của three là hằng số 1 cố định.
  function tron() { var T = window.MinMinTHREE; return sang() ? (T.NormalBlending != null ? T.NormalBlending : 1) : T.AdditiveBlending; }
  function vatLieu(mau, doMo) {
    var T = window.MinMinTHREE;
    return new T.SpriteMaterial({ map: texQuang(mau), blending: tron(),
      transparent: true, depthWrite: false, opacity: doMo == null ? 1 : doMo });
  }
  function coHat(n) { return 5 + Math.sqrt(Math.min(60, n.links || 0)) * 1.9; }
  // Băm ổn định theo id -> số 0..1 (để cùng một note luôn nằm cùng chỗ trong cầu)
  function bam(id) { var s = String(id), h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return ((h >>> 0) % 10007) / 10007; }

  // ---------- Neo cụm: mỗi thư mục một điểm trên mặt cầu quanh lõi (Fibonacci) ----------
  function datNeo(self, nodes) {
    var cats = [], dem = {};
    nodes.forEach(function (n) {
      if (!(n.__cat in dem)) { dem[n.__cat] = 0; cats.push(n.__cat); }
      dem[n.__cat]++;
    });
    var R = 60 + 7.5 * Math.sqrt(nodes.length);
    var neo = {}, k = Math.max(1, cats.length), vang = Math.PI * (3 - Math.sqrt(5));
    cats.forEach(function (c, i) {
      var y = k === 1 ? 0 : 1 - (i / (k - 1)) * 2;
      var rr = Math.sqrt(Math.max(0, 1 - y * y)), th = vang * i;
      var xa = R;                                                    // neo nằm TRÊN mặt cầu
      neo[c] = { x: Math.cos(th) * rr * xa, y: y * xa, z: Math.sin(th) * rr * xa, n: dem[c] };
    });
    self.__mmNeo = neo;
    self.__mmR = R;
  }
  function lucCum(self) {
    var nodes = [];
    function f(alpha) {
      var neo = self.__mmNeo || {};
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i], a = neo[n.__cat];
        if (!a) continue;
        n.vx += (a.x - n.x) * 0.012 * alpha;                        // cùng thư mục thì gom về một vùng
        n.vy += (a.y - n.y) * 0.012 * alpha;
        n.vz += (a.z - (n.z || 0)) * 0.012 * alpha;
      }
    }
    f.initialize = function (ns) { nodes = ns; };
    return f;
  }
  // Lực QUẢ CẦU: kéo mỗi note về bán kính riêng của nó. Phần lớn nằm sát vỏ (mặt cầu dày chấm
  // như ảnh mẫu), khoảng 1/4 nằm rải trong lòng cầu; dây nối vắt qua lòng cầu thành mạng.
  function lucCau(self) {
    var nodes = [];
    function f(alpha) {
      var R = self.__mmR || 120;
      for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i], z = n.z || 0;
        var r = Math.sqrt(n.x * n.x + n.y * n.y + z * z) || 1;
        if (n.__rCau == null) { var h = bam(n.id); n.__rCau = h < 0.26 ? 0.25 + h * 2.4 : 0.97 + (h - 0.26) * 0.08; }
        var k = (R * n.__rCau - r) / r * 0.22 * alpha;
        n.vx += n.x * k; n.vy += n.y * k; n.vz += z * k;
      }
    }
    f.initialize = function (ns) { nodes = ns; };
    return f;
  }

  // ---------- Cảnh nền quả cầu: quầng tím nhạt ở tâm + bụi chấm li ti trên vỏ ----------
  function dungCanh(self) {
    var T = window.MinMinTHREE, sc = self.graph.scene();
    if (self.__mmCanh) { sc.remove(self.__mmCanh); }
    var R = self.__mmR, g = new T.Group(), r = rng(Math.round(R * 7919));
    var L = sang();
    // quầng tím mềm ở lòng cầu (giống vệt lavender giữa ảnh mẫu)
    var quang = new T.Sprite(vatLieu(L ? "#8a6cf0" : "#6d4bd8", L ? 0.16 : 0.22));
    quang.scale.set(R * 2.1, R * 2.1, 1);
    g.add(quang);
    // bụi chấm li ti bám mặt cầu: viền quả cầu rõ hơn, nhất là mép dưới như ảnh mẫu
    var so = giamChuyenDong ? 500 : 1400, pos = new Float32Array(so * 3);
    for (var i = 0; i < so; i++) {
      var u = r() * 2 - 1, th = r() * TAU, sn = Math.sqrt(1 - u * u), rr = R * (0.99 + r() * 0.05);
      pos[i * 3] = Math.cos(th) * sn * rr; pos[i * 3 + 1] = u * rr; pos[i * 3 + 2] = Math.sin(th) * sn * rr;
    }
    var geo = new T.BufferGeometry();
    geo.setAttribute("position", new T.Float32BufferAttribute(pos, 3));
    var bui = new T.Points(geo, new T.PointsMaterial({ size: 1.6, color: L ? 0x6b5c55 : 0xcfc4ff, transparent: true,
      opacity: L ? 0.45 : 0.5, depthWrite: false, sizeAttenuation: true, map: texQuang(L ? "#6b5c55" : "#cfc4ff"), blending: tron() }));
    g.add(bui);
    sc.add(g);
    self.__mmCanh = g;
    self.__mmVatThe = { quang: quang, bui: bui };
  }

  // ---------- Độ sáng từng hạt theo hover / lọc cụm ----------
  function capNhatSang(self) {
    if (!self.graph) return;
    var hov = self._hoverId != null;
    self.graph.graphData().nodes.forEach(function (n) {
      var o = n.__mmObj; if (!o) return;
      var laH = n.id === self._hoverId, laN = hov && self._nbrs.has(n.id);
      var mo = (hov && !laH && !laN) || (self._catFilter && n.__cat !== self._catFilter && !laH && !laN);
      var mau = laH ? (sang() ? "#e8622a" : "#ffffff") : mauCum(n.__catIdx);
      var bl = tron();
      if (o.material.map !== texQuang(mau) || o.material.blending !== bl) {
        o.material.map = texQuang(mau); o.material.blending = bl; o.material.needsUpdate = true;
      }
      o.material.opacity = mo ? (sang() ? 0.16 : 0.12) : 1;
      n.__mmTo = laH ? 1.9 : (laN ? 1.25 : 1);
    });
    try { self.graph.linkColor(self.graph.linkColor()); } catch (e) {}
    try { self.graph.linkDirectionalParticles(self.graph.linkDirectionalParticles()); } catch (e) {}
  }

  // ---------- Thẻ ghi chú khi chỉ chuột ----------
  var _trich = {};
  function ngay(t) {
    if (!t || t < 1e9) return "";                                    // 0 = không rõ ngày tạo
    var d = new Date(t * 1000);
    if (isNaN(d.getTime())) return "";
    return ("0" + d.getDate()).slice(-2) + "/" + ("0" + (d.getMonth() + 1)).slice(-2) + "/" + d.getFullYear();
  }
  function lamGon(md) {
    var s = String(md || "").replace(/^\uFEFF/, "");
    s = s.replace(/^---[\s\S]*?\n---\s*\n?/, "");                     // bỏ frontmatter
    s = s.replace(/```[\s\S]*?```/g, " ").replace(/!\[\[[^\]]*\]\]|!\[[^\]]*\]\([^)]*\)/g, " ");
    s = s.replace(/\[\[([^\]|]*\|)?([^\]]*)\]\]/g, "$2").replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
    s = s.replace(/^#+\s*/gm, "").replace(/[*_`>|]/g, "").replace(/^\s*[-+]\s+(\[.\]\s*)?/gm, "");
    s = s.replace(/\s+/g, " ").trim();
    return s.length > 190 ? s.slice(0, 190).replace(/\s\S*$/, "") + "..." : s;
  }
  function duongDan(n) {
    var p = String(n.path || "");
    var i = p.indexOf("/");
    return i >= 0 ? p.slice(i + 1) : p;
  }
  function layTrich(self, n) {
    var id = n.id;
    if (id in _trich) return;
    _trich[id] = null;                                                // đang tải
    var brain = "brain";
    try { if (window.currentBrainPath) brain = window.currentBrainPath() || brain; } catch (e) {}
    fetch("/files/read?brain=" + encodeURIComponent(brain) + "&path=" + encodeURIComponent(duongDan(n)))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        _trich[id] = d && d.content ? lamGon(d.content) : "";
        doVaoThe(self, id, 0);
      })
      .catch(function () { _trich[id] = ""; doVaoThe(self, id, 0); });
  }
  // Note có thể đọc xong TRƯỚC khi thẻ kịp gắn vào trang, nên thử lại vài nhịp ngắn.
  function doVaoThe(self, id, lan) {
    var el = document.querySelector('.mm-ntip[data-id="' + (window.CSS && CSS.escape ? CSS.escape(String(id)) : String(id)) + '"] .mm-ntip-tx');
    if (el) { el.textContent = _trich[id] || "Note trống."; el.classList.remove("cho"); return; }
    if (lan < 12 && self._hoverId === id) setTimeout(function () { doVaoThe(self, id, lan + 1); }, 120);
  }
  function theGhiChu(self, n) {
    var mau = mauCum(n.__catIdx);
    var soNbr = 0;
    self.graph.graphData().links.forEach(function (l) {
      var s = idCua(l.source), t = idCua(l.target);
      if (s === n.id || t === n.id) soNbr++;
    });
    var tx = _trich[n.id];
    if (tx === undefined) layTrich(self, n);
    var coTx = typeof tx === "string";
    return '<div class="mm-ntip" data-id="' + esc(n.id) + '">' +
      '<div class="mm-ntip-h"><i style="background:' + mau + ';box-shadow:0 0 8px ' + mau + '"></i>' + esc(n.label || n.id) + '</div>' +
      '<div class="mm-ntip-m"><span style="color:' + mau + '">' + esc(n.__cat || n.folder || "") + '</span>' +
      ' · ' + soNbr + ' liên kết' + (ngay(n.t) ? " · tạo " + ngay(n.t) : "") + '</div>' +
      '<div class="mm-ntip-tx' + (coTx ? "" : " cho") + '">' + (coTx ? esc(tx || "Note trống.") : "Đang đọc note...") + '</div>' +
      '<div class="mm-ntip-f">Bấm để mở note</div></div>';
  }

  // ---------- Dựng đồ thị 3D ----------
  function taoDoThi(self) {
    var FG = window.ForceGraph3D;
    self._is3d = true;
    document.documentElement.classList.add("mm-3d");
    var g = FG({ controlType: "orbit" })(self.container)
      .backgroundColor("rgba(0,0,0,0)")
      .showNavInfo(false)
      .nodeId("id")
      .nodeRelSize(4)
      .nodeVal(function (n) { var r = coHat(n) * 0.5; return r * r / 16; })
      .nodeThreeObject(function (n) {
        var T = window.MinMinTHREE;
        var sp = new T.Sprite(vatLieu(mauCum(n.__catIdx), 1));
        var s = coHat(n); sp.scale.set(s, s, 1);
        n.__mmObj = sp; n.__mmCo = s; n.__mmTo = 1; n.__mmHien = 1;
        if (!n.__hub) return sp;
        // Note trung tâm (nhiều liên kết nhất): thêm quầng vàng như các điểm sáng trong ảnh mẫu
        var nhom = new T.Group();
        var quang = new T.Sprite(new T.SpriteMaterial({ map: texQuang("#ffb43c"), transparent: true, depthWrite: false,
          blending: sang() ? (T.NormalBlending != null ? T.NormalBlending : 1) : T.AdditiveBlending, opacity: 0.7 }));
        quang.scale.set(s * 3.4, s * 3.4, 1);
        nhom.add(quang); nhom.add(sp);
        return nhom;
      })
      .nodeLabel(function (n) { return theGhiChu(self, n); })
      .linkColor(function (l) {
        var L = sang();
        if (self._hoverId != null) {
          var s = idCua(l.source), t = idCua(l.target);
          if (s === self._hoverId || t === self._hoverId) return L ? "#e8622a" : "#ffffff";
          return L ? "#ece6f2" : "#1a1830";
        }
        return L ? "#7a727e" : "#8f86d8";
      })
      .linkOpacity(sang() ? 0.28 : 0.3)
      .linkWidth(0)
      .linkDirectionalParticles(function (l) {
        if (self._hoverId == null) return 0;
        var s = idCua(l.source), t = idCua(l.target);
        return (s === self._hoverId || t === self._hoverId) ? 3 : 0;
      })
      .linkDirectionalParticleWidth(function () { return self._thinking ? 4 : 2; })
      .linkDirectionalParticleSpeed(function () { return self._thinking ? 0.024 : 0.012; })
      .linkDirectionalParticleColor(function () {
        if (self._thinking) return sang() ? "#e8622a" : "#ffd27a";
        return sang() ? "#e8622a" : "#ffffff";
      })
      .warmupTicks(30)
      .cooldownTime(6000)
      .onNodeHover(function (n) {
        self._hoverId = n ? n.id : null;
        self._nbrs = new Set();
        if (n) {
          self.graph.graphData().links.forEach(function (l) {
            var s = idCua(l.source), t = idCua(l.target);
            if (s === n.id) self._nbrs.add(t); else if (t === n.id) self._nbrs.add(s);
          });
        }
        self.container.style.cursor = n ? "pointer" : "grab";
        capNhatSang(self);
      })
      .onNodeClick(function (n) { if (window.onGraphNodeClick) window.onGraphNodeClick(n); })
      .onNodeDragEnd(function (n) { n.fx = n.fy = n.fz = undefined; })
      .onBackgroundClick(function () { self._catFilter = null; })
      .onEngineStop(function () {
        if (self._fitted) return;
        self._fitted = true;
        self._fit(700);
      });
    self.graph = g;

    try { g.d3Force("charge").strength(-18); } catch (e) {}
    try { var lf = g.d3Force("link"); if (lf) lf.distance(34).strength(0.03); } catch (e) {}
    try { g.d3Force("center", null); } catch (e) {}
    try { g.d3Force("cluster", lucCum(self)); } catch (e) {}
    try { g.d3Force("cau", lucCau(self)); } catch (e) {}

    // Tự xoay chậm như video; người dùng đụng chuột thì dừng, rảnh 8 giây thì quay tiếp.
    var ctl = null;
    try { ctl = g.controls(); } catch (e) {}
    if (ctl) {
      ctl.enableDamping = true;
      ctl.dampingFactor = 0.08;
      ctl.autoRotate = tocDoQuay() > 0;
      ctl.autoRotateSpeed = 0.35 * tocDoQuay();
      var hen = null, the = self.__mmThe;
      ctl.addEventListener("start", function () { ctl.autoRotate = false; clearTimeout(hen); });
      // Thả chấm xong, thư viện phát một cú "pointerup" chạm giả để nhả OrbitControls. Với
      // three r183 cú đó đọc toạ độ/pointer không có -> lỗi đỏ trong console. Chặn cú giả đó
      // và tự nhả bộ điều khiển (bundle khoá cứng phiên bản nên các trường nội bộ ổn định).
      document.addEventListener("pointerup", function chanChamGia(e) {
        if (self.__mmThe !== the) { document.removeEventListener("pointerup", chanChamGia, true); return; }
        if (e.isTrusted || e.pointerType !== "touch" || !Array.isArray(ctl._pointers)) return;
        e.stopImmediatePropagation();
        ctl._pointers.length = 0;
        ctl._pointerPositions = {};
        ctl.state = -1;
        try {
          var d = ctl.domElement.ownerDocument;
          d.removeEventListener("pointermove", ctl._onPointerMove);
          d.removeEventListener("pointerup", ctl._onPointerUp);
        } catch (e2) {}
        try { ctl.dispatchEvent({ type: "end" }); } catch (e3) {}
      }, true);
      ctl.addEventListener("end", function () {
        clearTimeout(hen);
        hen = setTimeout(function () { if (self.__mmThe === the) ctl.autoRotate = tocDoQuay() > 0; }, 8000);
      });
    }

    self.__mmCtl = ctl;
    thanhQuay(self);

    // Hàm riêng cho bản 3D (đè lên prototype chỉ ở đối tượng này).
    // MinMin bắt đầu làm việc (nghĩ, gọi công cụ): các điểm sáng bắn tia cho nhau dọc dây nối.
    var tkGoc = self.setThinking;
    self.setThinking = function (bat) {
      var truoc = !!self._thinking;
      tkGoc.call(self, bat);
      if (!truoc && self._thinking) banLoat(self, 3);
    };
    self.banSang = function (so) { banLoat(self, so || 3); };
    self._nhipVe = function () {};
    self._recolor = function () { capNhatSang(self); };
    self._fit = function (ms) {
      if (!self.graph) return;
      try { self.graph.zoomToFit(ms == null ? 400 : ms, Math.max(10, Math.round(self._fitPad() * 0.6))); } catch (e) {}
    };
    self.pause = function () { self._mmDung = true; try { self.graph.pauseAnimation(); } catch (e) {} };
    self.wake = self.resume = function () { self._mmDung = false; try { self.graph.resumeAnimation(); } catch (e) {} };
    var tlGoc = self.startTimelapse;
    self.startTimelapse = function () {
      if (self.graph) self.graph.graphData().nodes.forEach(function (n) { delete n.z; delete n.vz; n.fz = undefined; });
      return tlGoc.apply(self, arguments);
    };
    batNhip(self);
  }

  // ---------- Bắn sáng: điểm này phóng tia theo dây sang điểm kia ----------
  // Bảng kề dựng lại mỗi lần nạp dữ liệu. Tia đi hết dây thì điểm đích loé sáng và có thể bắn
  // tiếp sang láng giềng của nó, thành chuỗi truyền tin lan qua quả cầu.
  function dungKe(self) {
    var ke = new Map();
    self.graph.graphData().links.forEach(function (l) {
      var s = idCua(l.source), t = idCua(l.target);
      if (!ke.has(s)) ke.set(s, []);
      if (!ke.has(t)) ke.set(t, []);
      ke.get(s).push({ l: l, toi: t, xuoi: true });
      ke.get(t).push({ l: l, toi: s, xuoi: false });
    });
    self.__mmKe = ke;
    self.__mmNutTheoId = new Map(self.graph.graphData().nodes.map(function (n) { return [n.id, n]; }));
  }
  function chonGoc(self) {
    var nodes = self.graph.graphData().nodes;
    if (!nodes.length || !self.__mmKe) return null;
    var hubs = nodes.filter(function (n) { return n.__hub; });
    for (var i = 0; i < 8; i++) {
      var n = (hubs.length && Math.random() < 0.45) ? hubs[(Math.random() * hubs.length) | 0] : nodes[(Math.random() * nodes.length) | 0];
      if ((self.__mmKe.get(n.id) || []).length) return n;
    }
    return null;
  }
  function banTu(self, n, doSau, soTia) {
    if (!self.graph || !n || giamChuyenDong) return;
    var ds = (self.__mmKe && self.__mmKe.get(n.id)) || [];
    if (!ds.length) return;
    n.__flash = now();
    var the = self.__mmThe;
    var chon = ds.slice().sort(function () { return Math.random() - 0.5; }).slice(0, soTia);
    chon.forEach(function (c) {
      // emitParticle luôn chạy từ source sang target: dây ngược chiều thì tia chạy VỀ điểm này.
      try { self.graph.emitParticle(c.l); } catch (e) { return; }
      var toi = c.xuoi ? c.toi : n.id;
      var tu = c.xuoi ? n : self.__mmNutTheoId.get(c.toi);
      if (!c.xuoi && tu) tu.__flash = now();
      var ms = self._thinking ? 700 : 1400;
      setTimeout(function () {
        if (self.__mmThe !== the || !self.graph) return;
        var dich = self.__mmNutTheoId.get(toi);
        if (!dich) return;
        dich.__flash = now();
        if (doSau > 0 && self._thinking && Math.random() < 0.7) banTu(self, dich, doSau - 1, 2);
      }, ms);
    });
  }
  function banLoat(self, so) {
    if (!self.graph || !self.__mmKe) return;
    for (var i = 0; i < so; i++) banTu(self, chonGoc(self), 2, 3);
  }

  // ---------- Thanh chỉnh tốc độ quay quả cầu (nhớ theo máy) ----------
  var KHOA_QUAY = "mm.cau.quay";
  function tocDoQuay() {
    var v = NaN;
    try { v = parseFloat(localStorage.getItem(KHOA_QUAY)); } catch (e) {}
    return isFinite(v) ? Math.max(0, Math.min(6, v)) : (giamChuyenDong ? 0 : 1);
  }
  function thanhQuay(self) {
    var cha = self.container && self.container.parentElement;
    if (!cha) return;
    var old = cha.querySelector(".mm-cau-quay");
    if (old) old.remove();
    var hop = document.createElement("div");
    hop.className = "mm-cau-quay";
    hop.innerHTML = '<span class="mm-cq-ic" aria-hidden="true">⟳</span>' +
      '<input type="range" min="0" max="6" step="0.25" aria-label="Tốc độ quay quả cầu">' +
      '<span class="mm-cq-so"></span>';
    hop.title = "Tốc độ quay quả cầu (kéo về 0 để đứng yên)";
    var o = hop.querySelector("input"), so = hop.querySelector(".mm-cq-so");
    function ghi(v) { so.textContent = v === 0 ? "Dừng" : "x" + (Math.round(v * 100) / 100); }
    o.value = String(tocDoQuay()); ghi(tocDoQuay());
    o.addEventListener("input", function () {
      var v = parseFloat(o.value) || 0;
      try { localStorage.setItem(KHOA_QUAY, String(v)); } catch (e) {}
      ghi(v);
      var ctl = self.__mmCtl;
      if (ctl) { ctl.autoRotateSpeed = 0.35 * v; ctl.autoRotate = v > 0; }
    });
    ["pointerdown", "wheel", "touchstart"].forEach(function (ev) {
      hop.addEventListener(ev, function (e) { e.stopPropagation(); }, { passive: true });
    });
    cha.appendChild(hop);
  }

  // ---------- Nhịp khung hình: lõi đập, vỏ quay, hạt thở và nảy sinh ----------
  function batNhip(self) {
    var loc = null, the = self.__mmThe;
    function khung() {
      if (self.__mmThe !== the) return;                               // đồ thị đã bị gỡ để đổi chế độ
      requestAnimationFrame(khung);
      if (self._mmDung || document.hidden || !self.graph || !self.__mmVatThe) return;
      var t = now() / 1000, vt = self.__mmVatThe, R = self.__mmR || 120;
      var am = self.level || 0, nghi = self._thinking ? 1 : 0;
      if (!giamChuyenDong) {
        // quầng tím thở nhẹ; đang nghĩ / đang nói thì sáng hơn
        var dap = 1 + 0.04 * Math.sin(t * 1.3) + 0.15 * am + 0.08 * nghi * Math.sin(t * 5);
        vt.quang.scale.set(R * 2.1 * dap, R * 2.1 * dap, 1);
      }
      if (self._catFilter !== loc) { loc = self._catFilter; capNhatSang(self); }
      var tNow = now();
      if (!giamChuyenDong) {
        var nhip = self._thinking ? 320 : (am > 0.05 ? 700 : 2600);
        if (tNow - (self.__mmLanBan || 0) > nhip) {
          self.__mmLanBan = tNow;
          banTu(self, chonGoc(self), self._thinking ? 2 : 0, self._thinking ? 3 : 1);
        }
      }
      self.graph.graphData().nodes.forEach(function (n) {
        var o = n.__mmObj; if (!o) return;
        var tho = giamChuyenDong ? 1 : 1 + 0.06 * Math.sin(t * 2.1 + (n.__ph || 0));
        var sinh = 1;
        if (n.__born) { var age = (tNow - n.__born) / 500; sinh = age < 1 ? Math.max(0.05, age) : 1; if (age >= 1) n.__born = 0; }
        var loe = 1;
        if (n.__flash) { var ft = (tNow - n.__flash) / 650; if (ft < 1) loe = 1 + 1.3 * (1 - ft) * (1 - ft); else n.__flash = 0; }
        var s = (n.__mmCo || 8) * (n.__mmTo || 1) * tho * sinh * loe;
        o.scale.set(s, s, 1);
      });
    }
    requestAnimationFrame(khung);
  }

  // ---------- Nạp dữ liệu ----------
  async function load3d(query) {
    var res = await fetch("/graph?" + query + "&orphans=1");
    var data = await res.json();
    if (!res.ok) throw new Error(data.error || ("Không tải được đồ thị (" + res.status + ")"));
    var nodes = Array.isArray(data.nodes) ? data.nodes : [];
    this._catMap = null;
    this._prep(nodes);
    window.__javisCatIdx = this._catMap;
    try { if (typeof _mapFromIdx === "function") window.__javisCatMap = _mapFromIdx(this._catMap); } catch (e) {}
    var links = (data.edges || []).map(function (e) { return { source: e.source, target: e.target }; });
    // 6 note nhiều liên kết nhất = điểm sáng vàng
    nodes.slice().sort(function (a, b) { return (b.links || 0) - (a.links || 0); }).slice(0, 6)
      .forEach(function (n) { if ((n.links || 0) >= 3) n.__hub = true; });
    datNeo(this, nodes);
    if (!this.graph) { this.__mmKieu = "3d"; taoDoThi(this); }
    this._fitted = false;
    this._hoverId = null; this._nbrs = new Set();
    this._t0 = now();
    this.graph.graphData({ nodes: nodes, links: links });
    dungKe(this);
    dungCanh(this);
    this.resize();
    // Canh khung sớm (không đợi mô phỏng nguội hẳn) để lúc mở đã thấy trọn quả cầu.
    var self = this;
    clearTimeout(this.__mmHenFit);
    this.__mmHenFit = setTimeout(function () { if (self.graph) self._fit(900); }, 1800);
    return data;
  }

  var P = window.JavisGraph.prototype;
  var load2d = P.load;
  P.load = async function (query) {
    var q = query || this.__mmTruyVan || "source=all";
    this.__mmTruyVan = q;
    if (this._is3d) return load3d.call(this, q);
    if (!this.graph && cheDo() === "3d" && coWebGL() && await napThuVien() && !this.graph) {
      try { return await load3d.call(this, q); }
      catch (e) {
        if (this._is3d) throw e;                                      // lỗi dữ liệu thì báo như bản gốc
        console.warn("[MinMin 3D] dựng 3D lỗi, dùng bản 2D:", e);
      }
    }
    return load2d.apply(this, arguments);
  };

  // Đổi tông khi đang ở 3D: tô lại hạt, dây và dựng lại cảnh nền, giữ nguyên góc nhìn.
  window.addEventListener("javis-theme-change", function () {
    var g = window.__javisGraph;
    if (!g || !g._is3d || !g.graph) return;
    try { dungCanh(g); capNhatSang(g); } catch (e) { console.warn("[MinMin 3D] đổi tông lỗi:", e); }
  });

  window.MinMinGalaxy3D = { on: true };
})();
