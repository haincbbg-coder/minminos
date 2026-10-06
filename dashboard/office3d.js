// ============================================================================
// MinMin OS - VĂN PHÒNG AI 3D (khoang não).
//
// Các agent của brain là robot làm việc trong một văn phòng 3D chạy theo việc thật:
//  - mỗi agent một bàn + một ghế (máy tính, bàn phím, chuột; màn hình sáng khi đang dùng), kê quanh phòng;
//  - giám đốc MinMin ngồi ở đầu bàn họp dài giữa phòng, bao quát tất cả;
//  - workflow chạy tới đâu thì người của bước đó đi vào bàn họp ngồi; xong bước thì đứng dậy trình bày
//    kết quả thật (trích từ đầu ra của bước) trên đầu; cần dữ liệu thì ra trạm dữ liệu;
//  - lượt chat với MinMin: agent có chuyên môn gần câu hỏi vào họp (đoán theo tên/vai trò), MinMin đứng dậy
//    trả lời bằng chính câu trả lời thật;
//  - bảng điều hành trên tường hiện số liệu thật của brain (cùng nguồn với HUD: GET /hud/kpi).
// Robot đi theo đường tự tìm (A*) quanh bàn ghế, tránh nhau, không xuyên vật thể.
// Sự kiện: GET /office/events (server/office_bus.py) mỗi 1,5 giây khi văn phòng mở, cộng thêm khung chat
// (app.js gọi MinMinOffice.onChatStart / onChatTool / onChatEnd). Nút "Mô phỏng" chạy một tình huống mẫu.
// Dùng three.js bản có sẵn của Hub (/static/hud/vendor), nạp khi mở lần đầu. Không có WebGL thì nút tự ẩn.
// ============================================================================
(function () {
  "use strict";
  if (typeof window === "undefined" || window.MinMinOffice) return;

  var THREE_URL = "/static/hud/vendor/three.module.min.js";
  var T = null;
  var host = null, cv = null, renderer = null, scene = null, camera = null;
  var rafId = 0, pollId = 0, kpiId = 0, seq = 0, mo = false, daDung = false, lanCuoi = 0;
  var agents = {}, ds = [], lead = null, tram = [], ban = null, phien = {};
  var cam = { az: -0.62, pol: 0.95, dist: 0, tx: 0.4, ty: 0.6, tz: 1.0 }, camMacDinh = null, phim = {}, kd = null, ku = null;
  function anBat() { return mo; }
  var raycaster = null, bang = null, kpiDuLieu = null, nguoiNoi = null, tNow = 0;
  var manHinh = [], matManOff = null, matManOn = [];

  function brain() { try { var q = new URLSearchParams(location.search).get("brain"); if (window.__mmOfficeSolo && q) return q; } catch (e0) {} try { return (window.currentBrainPath && window.currentBrainPath()) || "brain"; } catch (e) { return "brain"; } }
  function sang() { try { return window.MinMinGalaxyIsLight ? window.MinMinGalaxyIsLight() : false; } catch (e) { return false; } }
  function now() { return performance.now(); }
  function $(id) { return document.getElementById(id); }
  function hue(s) { var h = 0; for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360; return h; }
  function cat(s, n) { s = String(s || "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n - 1) + "…" : s; }
  function cl(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function lerp(a, b, k) { return a + (b - a) * k; }

  // ---------- bố cục ----------
  // Phòng 28,4 x 20,8. Bàn họp dài NẰM NGANG ở giữa; giám đốc ngồi đầu bên phải nhìn dọc cả bàn và cả phòng.
  // Bàn làm việc của agent kê sát tường sau, tường trái và hàng trước. Trạm dữ liệu dựa tường phải.
  var HX = 14.2, HZ = 10.4, TL = 11.4, TW = 2.3;
  var STATION_DEFS = [
    { id: "brain", ten: "Bộ nhớ Brain", z: -6.5, re: /^(read|write|edit|glob|grep|notebook|vault|memory|javis_(use_skill|task)|ask_javis)/i },
    { id: "mcp", ten: "Dữ liệu ngoài", z: -2.2, re: /^mcp__/i },
    { id: "web", ten: "Mạng và web", z: 2.2, re: /(websearch|webfetch|browser|chrome|fetch|search)/i },
    { id: "lenh", ten: "Máy chạy lệnh", z: 6.5, re: /./ }
  ];
  function tramCua(tool) {
    tool = String(tool || "");
    var mcp = /^mcp__([^_]+(?:_[^_]+)*)__/i.exec(tool);
    for (var i = 0; i < STATION_DEFS.length; i++) if (STATION_DEFS[i].re.test(tool)) {
      var t = tram[i]; return { st: t, i: i, nhan: i === 1 && mcp ? mcp[1].replace(/_/g, " ") : t.def.ten };
    }
    return { st: tram[3], i: 3, nhan: tram[3].def.ten };
  }

  // ---------- tìm đường (A*) quanh vật thể ----------
  var CELL = 0.4, GW = Math.ceil(HX * 2 / CELL), GH = Math.ceil(HZ * 2 / CELL), blocked = null;
  function gi(x) { return Math.floor((x + HX) / CELL); }
  function gj(z) { return Math.floor((z + HZ) / CELL); }
  function cx(i) { return -HX + (i + 0.5) * CELL; }
  function cz(j) { return -HZ + (j + 0.5) * CELL; }
  function chanHinhChuNhat(x, z, w, d, rot, pad) {
    var c = Math.cos(rot), s = Math.sin(rot), hw = w / 2 + pad, hd = d / 2 + pad;
    var r = Math.hypot(w, d) / 2 + pad + CELL;
    for (var i = Math.max(0, gi(x - r)); i <= Math.min(GW - 1, gi(x + r)); i++) for (var j = Math.max(0, gj(z - r)); j <= Math.min(GH - 1, gj(z + r)); j++) {
      var dx = cx(i) - x, dz = cz(j) - z, lx = dx * c - dz * s, lz = dx * s + dz * c;
      if (Math.abs(lx) <= hw && Math.abs(lz) <= hd) blocked[j * GW + i] = 1;
    }
  }
  function chanTron(x, z, rad) {
    for (var i = Math.max(0, gi(x - rad - CELL)); i <= Math.min(GW - 1, gi(x + rad + CELL)); i++) for (var j = Math.max(0, gj(z - rad - CELL)); j <= Math.min(GH - 1, gj(z + rad + CELL)); j++)
      if (Math.hypot(cx(i) - x, cz(j) - z) <= rad) blocked[j * GW + i] = 1;
  }
  function khoiTaoLuoi() {
    blocked = new Uint8Array(GW * GH);
    for (var i = 0; i < GW; i++) for (var j = 0; j < GH; j++) if (Math.abs(cx(i)) > HX - 0.7 || Math.abs(cz(j)) > HZ - 0.7) blocked[j * GW + i] = 1;
    chanHinhChuNhat(0, 0, TL, TW, 0, 0.45);                       // bàn họp
  }
  function nhoNhat(a, b) { return a.f < b.f; }
  function timDuong(sx, sz, gx, gz, tru) {
    // ô tắc bởi vật tĩnh, hoặc bởi người đang ĐỨNG/NGỒI yên (trừ chính nó); vùng quanh điểm đầu/cuối được mở
    var occ = [];
    var danh = ds.concat(lead ? [lead] : []);
    danh.forEach(function (o) { if (o !== tru && !o.walking) occ.push(o); });
    function ok(i, j) {
      if (i < 0 || j < 0 || i >= GW || j >= GH) return false;
      var x = cx(i), z = cz(j);
      if (Math.hypot(x - sx, z - sz) < 0.9 || Math.hypot(x - gx, z - gz) < 0.9) return Math.abs(x) <= HX - 0.7 && Math.abs(z) <= HZ - 0.7 && !(Math.abs(x) <= TL / 2 + 0.3 && Math.abs(z) <= TW / 2 + 0.3);
      if (blocked[j * GW + i]) return false;
      for (var k = 0; k < occ.length; k++) if (Math.hypot(x - occ[k].x, z - occ[k].z) < 0.85) return false;
      return true;
    }
    var si = gi(sx), sj = gj(sz), ti = gi(gx), tj = gj(gz);
    if (si === ti && sj === tj) return [{ x: gx, z: gz }];
    var N = GW * GH, g = new Float32Array(N).fill(1e9), par = new Int32Array(N).fill(-1), done = new Uint8Array(N);
    var heap = [], s0 = sj * GW + si; g[s0] = 0; heap.push({ f: 0, n: s0 });
    function up(i) { while (i > 0) { var p = (i - 1) >> 1; if (nhoNhat(heap[i], heap[p])) { var t = heap[i]; heap[i] = heap[p]; heap[p] = t; i = p; } else break; } }
    function down(i) { for (;;) { var l = i * 2 + 1, r = l + 1, m = i; if (l < heap.length && nhoNhat(heap[l], heap[m])) m = l; if (r < heap.length && nhoNhat(heap[r], heap[m])) m = r; if (m === i) break; var t = heap[i]; heap[i] = heap[m]; heap[m] = t; i = m; } }
    var goal = tj * GW + ti, found = false, DIRS = [[1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1], [1, 1, 1.414], [1, -1, 1.414], [-1, 1, 1.414], [-1, -1, 1.414]];
    var guard = 0;
    while (heap.length && guard++ < 9000) {
      var cur = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; down(0); }
      var n = cur.n; if (done[n]) continue; done[n] = 1; if (n === goal) { found = true; break; }
      var ci = n % GW, cj = (n / GW) | 0;
      for (var d = 0; d < 8; d++) {
        var ni = ci + DIRS[d][0], nj = cj + DIRS[d][1]; if (!ok(ni, nj)) continue;
        if (DIRS[d][2] > 1 && (!ok(ci + DIRS[d][0], cj) || !ok(ci, cj + DIRS[d][1]))) continue;      // không cắt góc
        var nn = nj * GW + ni, ng = g[n] + DIRS[d][2]; if (ng >= g[nn]) continue;
        g[nn] = ng; par[nn] = n; var h = Math.hypot(ni - ti, nj - tj); heap.push({ f: ng + h, n: nn }); up(heap.length - 1);
      }
    }
    if (!found) return [{ x: gx, z: gz }];                    // không tìm được đường: đi thẳng (hiếm)
    var cells = []; for (var q = goal; q !== -1; q = par[q]) cells.push({ x: cx(q % GW), z: cz((q / GW) | 0) }); cells.reverse();
    // kéo căng đường: bỏ điểm giữa nếu nối thẳng vẫn đi được
    function thong(a, b) { var L = Math.hypot(b.x - a.x, b.z - a.z), n2 = Math.max(1, Math.ceil(L / 0.2)); for (var k = 1; k < n2; k++) { var x = lerp(a.x, b.x, k / n2), z = lerp(a.z, b.z, k / n2); if (!ok(gi(x), gj(z))) return false; } return true; }
    var out = [], from = { x: sx, z: sz }, idx = 0;
    while (idx < cells.length) {
      var far = idx; for (var m = cells.length - 1; m > idx; m--) if (thong(from, cells[m])) { far = m; break; }
      from = cells[far]; out.push(from); idx = far + 1;
    }
    out[out.length - 1] = { x: gx, z: gz };
    return out;
  }

  // ---------- chữ trên sprite ----------
  function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function nenNhan() { return sang() ? "rgba(255,255,255,0.94)" : "rgba(18,28,46,0.92)"; }
  function veNhan(dong1, dong2, mau, nen) {
    var c = document.createElement("canvas"), W = 360, H = 96; c.width = W; c.height = H;
    var g = c.getContext("2d");
    g.fillStyle = nen; rr(g, 2, 2, W - 4, H - 4, 18); g.fill();
    g.strokeStyle = mau; g.lineWidth = 3; rr(g, 2, 2, W - 4, H - 4, 18); g.stroke();
    g.fillStyle = mau; g.font = "700 30px system-ui,Segoe UI,Roboto,sans-serif"; g.textBaseline = "middle";
    g.fillText(cat(dong1, 20), 18, dong2 ? 33 : 48);
    if (dong2) { g.fillStyle = sang() ? "#4a5a70" : "#b9c7dc"; g.font = "500 24px system-ui,Segoe UI,Roboto,sans-serif"; g.fillText(cat(dong2, 26), 18, 68); }
    return c;
  }
  function veNoi(text, mau) {                // bong bóng lời nói: xuống dòng, tối đa 4 dòng
    var c = document.createElement("canvas"), W = 560, f = "600 30px system-ui,Segoe UI,Roboto,sans-serif", g = c.getContext("2d"), lines = [], cur = "";
    g.font = f; String(text || "").replace(/\s+/g, " ").trim().split(" ").forEach(function (w) {
      var t = cur ? cur + " " + w : w; if (g.measureText(t).width > W - 44 && cur) { lines.push(cur); cur = w; } else cur = t;
    });
    if (cur) lines.push(cur);
    if (lines.length > 4) { lines = lines.slice(0, 4); lines[3] = cat(lines[3], 30) + "…"; }
    var H = 36 + lines.length * 38; c.width = W; c.height = H; g = c.getContext("2d");
    g.fillStyle = sang() ? "rgba(255,255,255,0.97)" : "rgba(18,28,46,0.96)"; rr(g, 2, 2, W - 4, H - 4, 20); g.fill();
    g.strokeStyle = mau; g.lineWidth = 3; rr(g, 2, 2, W - 4, H - 4, 20); g.stroke();
    g.font = f; g.textBaseline = "middle"; g.fillStyle = sang() ? "#1f2d44" : "#e8f0ff";
    lines.forEach(function (l, i) { g.fillText(l, 22, 36 + i * 38); });
    return c;
  }
  function spriteTu(canvas, sx) {
    var tex = new T.CanvasTexture(canvas); tex.colorSpace = T.SRGBColorSpace;
    var sp = new T.Sprite(new T.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false }));
    sp.scale.set(sx, sx * canvas.height / canvas.width, 1); sp.renderOrder = 10; return sp;
  }
  function capNhatSprite(sp, canvas, sx) {
    var old = sp.material.map; sp.material.map = new T.CanvasTexture(canvas); sp.material.map.colorSpace = T.SRGBColorSpace; sp.material.needsUpdate = true; if (old) old.dispose();
    if (sx) sp.scale.set(sx, sx * canvas.height / canvas.width, 1);
  }

  // ---------- robot ----------
  function mat(c, o) { return new T.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.55, metalness: 0.05 }, o || {})); }
  var GEO = {};
  function cap(r, l) { var k = "c" + r + "_" + l; return GEO[k] || (GEO[k] = new T.CapsuleGeometry(r, l, 4, 8)); }
  function hsl(h, s, l) { return new T.Color().setHSL((h % 360) / 360, s, l); }

  function dungTay(g, side, aoMat, trang) {
    var sh = new T.Group(); sh.position.set(side * 0.5, 1.3, 0); g.add(sh);
    var up = new T.Mesh(cap(0.1, 0.26), aoMat); up.position.y = -0.22; sh.add(up);
    var el = new T.Group(); el.position.y = -0.43; sh.add(el);
    var fo = new T.Mesh(cap(0.085, 0.24), trang); fo.position.y = -0.19; el.add(fo);
    var hand = new T.Group(); hand.position.y = -0.38; el.add(hand);
    var palm = new T.Mesh(new T.BoxGeometry(0.15, 0.13, 0.05), trang); palm.position.y = -0.065; hand.add(palm);
    var ngon = [];
    for (var i = 0; i < 4; i++) {
      var p = new T.Group(); p.position.set(-0.055 + i * 0.037, -0.13, 0); hand.add(p);
      var f = new T.Mesh(cap(0.017, 0.07 + (i === 1 || i === 2 ? 0.015 : 0)), trang); f.position.y = -0.05; p.add(f); ngon.push(p);
    }
    var pt = new T.Group(); pt.position.set(-side * 0.075, -0.03, 0.01); pt.rotation.z = side * 0.7; hand.add(pt);
    var thumb = new T.Mesh(cap(0.019, 0.06), trang); thumb.position.y = -0.04; pt.add(thumb); ngon.push(pt);
    return { sh: sh, el: el, hand: hand, ngon: ngon };
  }
  function dungVat(loai, mauV) {               // vật mang đi họp: sách, tablet, bút
    var g = new T.Group();
    if (loai === 0) { var b = new T.Mesh(new T.BoxGeometry(0.24, 0.05, 0.32), mat(mauV)); g.add(b); var gay = new T.Mesh(new T.BoxGeometry(0.02, 0.055, 0.32), mat(0xf4efe6)); gay.position.x = -0.11; g.add(gay); }
    else { var tb = new T.Mesh(new T.BoxGeometry(0.22, 0.015, 0.3), mat(0x20283a)); g.add(tb); var mh = new T.Mesh(new T.BoxGeometry(0.2, 0.004, 0.27), mat(0x9fe8ff, { emissive: 0x4fc8ff, emissiveIntensity: 0.9 })); mh.position.y = 0.01; g.add(mh); }
    return g;
  }
  function dungRobot(ten, role, hueV, laLead) {
    var g = new T.Group(), s = laLead ? 1.18 : 1, light = sang();
    var acc = hsl(hueV, 0.75, light ? 0.5 : 0.62);
    var ao = mat(hsl(hueV, 0.6, light ? 0.5 : 0.5).getHex());                 // áo: mỗi agent một màu riêng
    var quan = mat(hsl(hueV + 35, 0.3, 0.22).getHex());
    var trang = mat(light ? 0xf4f7fb : 0xe3eaf5), toi = mat(0x1a2233, { roughness: 0.3, metalness: 0.2 });
    var than = new T.Mesh(new T.CapsuleGeometry(0.4, 0.45, 6, 14), ao); than.position.y = 0.95; g.add(than);
    var nguc = new T.Mesh(new T.BoxGeometry(0.3, 0.16, 0.05), mat(0xffffff, { emissive: acc.getHex(), emissiveIntensity: 0.7 })); nguc.position.set(0, 1.02, 0.4); g.add(nguc);
    var dau_ = new T.Group(); dau_.position.y = 1.78; g.add(dau_);
    dau_.add(new T.Mesh(new T.SphereGeometry(0.46, 24, 18), trang));
    var kinh = new T.Mesh(new T.SphereGeometry(0.4, 20, 14), toi); kinh.scale.set(1, 0.62, 0.55); kinh.position.set(0, 0.02, 0.28); dau_.add(kinh);
    var matM = mat(0x9ff3ff, { emissive: 0x6fe6ff, emissiveIntensity: 1.2 });
    var mat_mat = []; [-0.14, 0.14].forEach(function (x) { var e = new T.Mesh(new T.SphereGeometry(0.06, 10, 8), matM); e.scale.set(1, 1.3, 0.6); e.position.set(x, 0.03, 0.46); dau_.add(e); mat_mat.push(e); });
    var anten = new T.Mesh(new T.CylinderGeometry(0.02, 0.02, 0.25, 6), toi); anten.position.y = 0.55; dau_.add(anten);
    var bi = new T.Mesh(new T.SphereGeometry(0.06, 10, 8), mat(acc.getHex(), { emissive: acc.getHex(), emissiveIntensity: 0.9 })); bi.position.y = 0.7; dau_.add(bi);
    var tT = dungTay(g, -1, ao, trang), tP = dungTay(g, 1, ao, trang);
    function chan(x) { var p = new T.Group(); p.position.set(x, 0.55, 0); var t = new T.Mesh(cap(0.12, 0.3), quan); t.position.y = -0.28; p.add(t); var giay = new T.Mesh(new T.BoxGeometry(0.2, 0.1, 0.32), toi); giay.position.set(0, -0.56, 0.05); p.add(giay); g.add(p); return p; }
    var chanT = chan(-0.2), chanP = chan(0.2);
    var bong = new T.Mesh(new T.CircleGeometry(0.62, 20), new T.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.16, depthWrite: false }));
    bong.rotation.x = -Math.PI / 2; bong.position.y = 0.02; g.add(bong);
    if (laLead) { var vong = new T.Mesh(new T.TorusGeometry(0.62, 0.035, 8, 40), mat(0xffb020, { emissive: 0xffb020, emissiveIntensity: 0.8 })); vong.rotation.x = Math.PI / 2; vong.position.y = 0.05; g.add(vong); }
    // vật mang đi họp: tablet hoặc sách ở tay trái, bút ở tay phải (chỉ hiện khi đang họp)
    var sach = dungVat(hueV % 2, hsl(hueV, 0.5, 0.35).getHex()); sach.position.set(0, -0.1, 0.1); sach.rotation.x = 0.0; tT.hand.add(sach); sach.visible = false;
    var but = new T.Mesh(new T.CylinderGeometry(0.014, 0.014, 0.2, 6), mat(0x222222)); but.rotation.x = Math.PI / 2; but.position.set(0, -0.1, 0.05); tP.hand.add(but); but.visible = false;
    g.scale.setScalar(s);
    var nhan = spriteTu(veNhan(ten, role, "#" + acc.getHexString(), nenNhan()), 2.5);
    nhan.position.set(0, 3.15 * s, 0); g.add(nhan);
    var noi = spriteTu(veNoi("…", "#" + acc.getHexString()), 3.6); noi.center.set(0.5, 0); noi.position.set(0, 3.55 * s, 0); noi.visible = false; g.add(noi);
    return { mat_mat: mat_mat, g: g, dau: dau_, tT: tT, tP: tP, chanT: chanT, chanP: chanP, than: than, matM: matM, nhan: nhan, noi: noi, acc: acc, s: s, vat: sach, but: but };
  }


  // ---------- người 3D có xương (Higgsfield + Meshy), dựng trong office3d: 10 nhân vật, 6 hoạt ảnh ----------
  var NV = null, NV_CLIPS = ["walk", "idle", "sit", "talk", "listen", "sitans"], nvDem = 0, HS = 1.15;
  var NV_DIR = "/static/office/", NV_V = "1";
  function napNguoi() {
    return import(NV_DIR + "gltf-addons.js?v=" + NV_V).then(function (m) {
      var L = new m.GLTFLoader();
      function tai(u) { return new Promise(function (ok, ko) { L.load(u + "?v=" + NV_V, ok, null, ko); }); }
      var ps = [], i;
      for (i = 0; i < 10; i++) ps.push(tai(NV_DIR + "c" + i + ".glb"));
      NV_CLIPS.forEach(function (n) { ps.push(tai(NV_DIR + "a_" + n + ".glb")); });
      return Promise.all(ps).then(function (r) {
        var clips = {}; NV_CLIPS.forEach(function (n, k) { clips[n] = r[10 + k].animations[0]; });
        NV = { chars: r.slice(0, 10).map(function (g) { return g.scene; }), clips: clips, SU: m.SkeletonUtils }; return true;
      });
    }).catch(function (e) { console.warn("[office] không nạp được người 3D, dùng robot", e); NV = null; return false; });
  }
  // lệch gốc của từng hoạt ảnh (cm, theo hông): clip ngồi giả định ghế nằm sau lưng, kéo về đúng chỗ ghế
  var NV_OFF = { sit: [-21.3, 67.4], sitans: [13.1, 35.2] };
  var _qi = null, _p0 = null, _p1 = null, _p2 = null, _q0 = null, _q1 = null, _v0 = null, _v1 = null;
  function dungNguoi3D(ten, role, hueV, laLead) {
    var acc = hsl(hueV, 0.75, 0.52), idx = laLead ? 0 : 1 + (nvDem++ % 9);
    var g = new T.Group(), pivot = new T.Group(); g.add(pivot);
    var model = NV.SU.clone(NV.chars[idx]); pivot.add(model);
    model.traverse(function (o) { if (o.isSkinnedMesh) o.frustumCulled = false; });
    var B = {}; ["Hips", "Spine", "neck", "Head", "LeftArm", "LeftForeArm", "LeftHand", "RightArm", "RightForeArm", "RightHand"].forEach(function (n) { B[n] = model.getObjectByName(n); });
    var hy = B.Hips.position.y || 100; var S = HS * (100.26 / hy), caoNguoi = 1.72 * S;
    pivot.scale.setScalar(S);
    var mixer = new T.AnimationMixer(model), act = {}, wt = {};
    NV_CLIPS.forEach(function (n, k) { var ac = mixer.clipAction(NV.clips[n]); ac.play(); ac.setEffectiveWeight(0); ac.time = (k * 0.7 + Math.random() * 3) % 3; act[n] = ac; wt[n] = 0; });
    var than = new T.Mesh(new T.BoxGeometry(0.9, caoNguoi, 0.6), new T.MeshBasicMaterial({ visible: false })); than.position.y = caoNguoi / 2; g.add(than);
    var bong = new T.Mesh(new T.CircleGeometry(0.55, 20), new T.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.18, depthWrite: false }));
    bong.rotation.x = -Math.PI / 2; bong.position.y = 0.02; g.add(bong);
    if (laLead) { var vong = new T.Mesh(new T.TorusGeometry(0.6, 0.035, 8, 40), mat(0xffb020, { emissive: 0xffb020, emissiveIntensity: 0.8 })); vong.rotation.x = Math.PI / 2; vong.position.y = 0.05; g.add(vong); }
    // sách / máy tính bảng ở tay trái, bút ở tay phải (chỉ hiện khi đi họp); thang xương là cm nên nhân 100
    var gv = new T.Group(); gv.scale.setScalar(100 / 1); var sach = dungVat(hueV % 2, hsl(hueV, 0.5, 0.35).getHex()); sach.position.set(0, 0.07, 0.0); sach.rotation.set(0, 0, 0); gv.add(sach); gv.visible = false; B.LeftHand.add(gv);
    var gb = new T.Group(); gb.scale.setScalar(100); var but = new T.Mesh(new T.CylinderGeometry(0.012, 0.012, 0.18, 6), mat(0x222222)); but.position.set(0, 0.06, 0); gb.add(but); gb.visible = false; B.RightHand.add(gb);
    var nhan = spriteTu(veNhan(ten, role, "#" + acc.getHexString(), nenNhan()), 2.5); nhan.position.set(0, caoNguoi + 0.55, 0); g.add(nhan);
    var noi = spriteTu(veNoi("…", "#" + acc.getHexString()), 3.6); noi.center.set(0.5, 0); noi.position.set(0, caoNguoi + 0.95, 0); noi.visible = false; g.add(noi);
    return { hum: true, g: g, pivot: pivot, model: model, B: B, mixer: mixer, act: act, wt: wt, S: S, than: than, nhan: nhan, noi: noi, acc: acc, s: 0, vat: gv, but: gb, ikw: 0, vatGoc: sach, idx: idx };
  }
  // quay xương `bone` sao cho trục hướng tới `child` chỉ về `huong` (thế giới)
  function nhamXuong(bone, child, huong) {
    bone.updateWorldMatrix(true, false); child.updateWorldMatrix(true, false);
    bone.getWorldPosition(_p0); child.getWorldPosition(_p1); _v0.copy(_p1).sub(_p0).normalize();
    _q0.setFromUnitVectors(_v0, huong.normalize());
    bone.getWorldQuaternion(_q1); _q1.premultiply(_q0);
    bone.parent.getWorldQuaternion(_q0); _q0.invert(); bone.quaternion.copy(_q0.multiply(_q1));
    bone.updateMatrixWorld(true);
  }
  // IK hai khúc: vai -> khuỷu -> cổ tay chạm điểm `dich` (thế giới), khuỷu nghiêng về phía `cuc`
  function ikTay(up, fo, ha, dich, cuc, w) {
    if (w <= 0.001) return;
    var oU = up.quaternion.clone(), oF = fo.quaternion.clone();
    up.updateWorldMatrix(true, true);
    up.getWorldPosition(_p0); fo.getWorldPosition(_p1); ha.getWorldPosition(_p2);
    var l1 = _p0.distanceTo(_p1), l2 = _p1.distanceTo(_p2);
    var d = dich.clone().sub(_p0), dist = Math.min(Math.max(d.length(), Math.abs(l1 - l2) + 0.02), (l1 + l2) * 0.995); d.normalize();
    var cosA = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist), sinA = Math.sqrt(Math.max(0, 1 - cosA * cosA));
    var perp = cuc.clone().sub(d.clone().multiplyScalar(cuc.dot(d))).normalize();
    var khuyu = _p0.clone().add(d.clone().multiplyScalar(l1 * cosA)).add(perp.multiplyScalar(l1 * sinA));
    nhamXuong(up, fo, khuyu.clone().sub(_p0));
    var cuoi = _p0.clone().add(d.clone().multiplyScalar(dist));
    nhamXuong(fo, ha, cuoi.sub(khuyu));
    ha.quaternion.slerp(_qi, Math.min(1, w * 1.2)); ha.updateMatrixWorld(true);
    if (w < 0.999) { var nU = up.quaternion.clone(), nF = fo.quaternion.clone(); up.quaternion.copy(oU).slerp(nU, w); fo.quaternion.copy(oF).slerp(nF, w); up.updateMatrixWorld(true); }
  }
  function nguoiKhung(a, r, dang, dt, t, ngoiK) {
    if (!_p0) { _p0 = new T.Vector3(); _p1 = new T.Vector3(); _p2 = new T.Vector3(); _qi = new T.Quaternion(); _q0 = new T.Quaternion(); _q1 = new T.Quaternion(); _v0 = new T.Vector3(); _v1 = new T.Vector3(); }
    var ngoi = ngoiK > 0.5, mucTieu = {};
    if (a.walking) mucTieu.walk = 1;
    else if (ngoi) mucTieu[dang === "talk" ? "sitans" : "sit"] = 1;
    else mucTieu[dang === "talk" ? "talk" : (dang === "listen" ? "listen" : "idle")] = 1;
    var tong = 0, n, k = Math.min(1, dt * 7);
    for (n in r.act) { r.wt[n] += ((mucTieu[n] || 0) - r.wt[n]) * k; tong += r.wt[n]; }
    var ox = 0, oz = 0, hạ = 0;
    for (n in r.act) {
      var w = tong > 0 ? r.wt[n] / tong : 0; r.act[n].setEffectiveWeight(w);
      if (NV_OFF[n]) { ox += NV_OFF[n][0] * 0.01 * w; oz += NV_OFF[n][1] * 0.01 * w; }
      if (n === "sit" || n === "sitans") hạ += w;
    }
    r.act.walk.timeScale = 1.3;
    r.mixer.update(dt);
    r.pivot.position.set(ox * r.S, -hạ * (0.745 * r.S - 0.56), oz * r.S);
    r.model.updateMatrixWorld(true);
    var tayDat = ngoi && (dang === "type" || dang === "listen");
    r.ikw += ((tayDat ? 1 : 0) - r.ikw) * Math.min(1, dt * 6);
    if (r.ikw > 0.01) {
      var sr = Math.sin(a.rot), cr = Math.cos(a.rot), f = [sr, cr], lft = [cr, -sr], gõ = dang === "type", cao = gõ ? 0.92 : 0.9, xa = gõ ? 0.86 : 0.8;
      var cg = r.g.position, B = r.B, bs = 0.5 + 0.5 * Math.sin(t * 17 + a.seed), bs2 = 0.5 + 0.5 * Math.sin(t * 13 + a.seed * 2.3);
      [[1, B.LeftArm, B.LeftForeArm, B.LeftHand, bs], [-1, B.RightArm, B.RightForeArm, B.RightHand, bs2]].forEach(function (h) {
        var sd = h[0], j = gõ ? 0.02 * h[4] : 0, tg = new T.Vector3(cg.x + f[0] * (xa - 0.0) + lft[0] * sd * 0.2, cao + j, cg.z + f[1] * xa + lft[1] * sd * 0.2);
        var cuc = new T.Vector3(lft[0] * sd * 0.6, -0.8, lft[1] * sd * 0.6);
        ikTay(h[1], h[2], h[3], tg, cuc, r.ikw);
        if (r.ikw > 0.01) { h[3].rotateY(-sd * 1.3 * r.ikw); h[3].updateMatrixWorld(true); }
      });
    }
    // đầu quay nhìn người đang nói (quanh trục dọc thế giới), gật nhẹ khi nói
    var yaw = 0;
    if (nguoiNoi && nguoiNoi !== a && !a.walking) { var rel = Math.atan2(nguoiNoi.x - a.x, nguoiNoi.z - a.z) - a.rot; while (rel > Math.PI) rel -= Math.PI * 2; while (rel < -Math.PI) rel += Math.PI * 2; yaw = cl(rel, -1.0, 1.0); }
    else if (!a.walking && ngoi) yaw = Math.sin(t * 0.45 + a.seed) * 0.18;
    r.yawC = lerp(r.yawC || 0, yaw, 0.12);
    if (Math.abs(r.yawC) > 0.002) {
      var hd = r.B.Head; hd.updateWorldMatrix(true, false); hd.getWorldQuaternion(_q1); _q0.setFromAxisAngle(_v1.set(0, 1, 0), r.yawC * 0.8); _q1.premultiply(_q0);
      hd.parent.getWorldQuaternion(_q0); _q0.invert(); hd.quaternion.copy(_q0.multiply(_q1));
    }
  }

  // ---------- màn hình máy tính: bốn kiểu nội dung chuyển động, dùng chung ----------
  function taoManHinh() {
    manHinh = [0, 1, 2, 3].map(function (k) {
      var c = document.createElement("canvas"); c.width = 256; c.height = 160;
      var tex = new T.CanvasTexture(c); tex.colorSpace = T.SRGBColorSpace; return { c: c, g: c.getContext("2d"), tex: tex, k: k };
    });
    matManOn = manHinh.map(function (m) { return new T.MeshBasicMaterial({ map: m.tex, toneMapped: false }); });
    matManOff = new T.MeshBasicMaterial({ color: 0x0b1220 });
  }
  function veManHinh(t) {
    manHinh.forEach(function (m) {
      var g = m.g, W = 256, H = 160, o = t * 22;
      g.fillStyle = "#0b1426"; g.fillRect(0, 0, W, H); g.fillStyle = "#1c3f8f"; g.fillRect(0, 0, W, 16);
      g.fillStyle = "#6fa8ff"; g.fillRect(6, 5, 40, 6);
      if (m.k === 0) { for (var i = 0; i < 12; i++) { var y = 24 + ((i * 12 - o) % 140 + 140) % 140; g.fillStyle = i % 3 === 0 ? "#7ee0a0" : "#8fb4ff"; g.fillRect(10 + (i % 4) * 6, y, 40 + ((i * 37) % 120), 5); } }
      else if (m.k === 1) { for (var b = 0; b < 9; b++) { var h = 20 + 50 * (0.5 + 0.5 * Math.sin(t * 1.3 + b * 0.9)); g.fillStyle = b % 2 ? "#4f8bff" : "#39d0c0"; g.fillRect(14 + b * 26, 142 - h, 18, h); } }
      else if (m.k === 2) { for (var r = 0; r < 7; r++) for (var cc = 0; cc < 4; cc++) { g.fillStyle = ((r + Math.floor(o / 18)) % 3 === 0) ? "#233a66" : "#122244"; g.fillRect(8 + cc * 60, 24 + r * 19, 56, 16); g.fillStyle = "#9bb9ff"; g.fillRect(12 + cc * 60, 30 + r * 19, 14 + ((r * 7 + cc * 13) % 30), 4); } }
      else { g.strokeStyle = "#ffb454"; g.lineWidth = 2; g.beginPath(); for (var x = 0; x <= 236; x += 6) { var yy = 100 + Math.sin(x * 0.05 + t * 1.5) * 24 + Math.sin(x * 0.13 - t) * 10; if (x === 0) g.moveTo(10, yy); else g.lineTo(10 + x, yy); } g.stroke(); g.strokeStyle = "#39d0c0"; g.beginPath(); for (var x2 = 0; x2 <= 236; x2 += 6) { var y2 = 60 + Math.cos(x2 * 0.06 + t * 1.1) * 18; if (x2 === 0) g.moveTo(10, y2); else g.lineTo(10 + x2, y2); } g.stroke(); }
      m.tex.needsUpdate = true;
    });
  }

  // ---------- chữ trên tường: khẩu hiệu và bảng điều hành ----------
  var KHAU_HIEU = [
    ["Khách hàng là trung tâm", "Mỗi tin nhắn là một cơ hội phục vụ"],
    ["Số liệu thật, quyết định đúng", "Nhìn con số trước khi nói cảm giác"],
    ["Nhanh hơn một bước mỗi ngày", "Việc hôm nay, đừng để sang mai"],
    ["Mỗi đơn hàng là một lời cảm ơn", "Giao đúng, đẹp, đủ"],
    ["Cùng nhau đi xa hơn", "Giúp đồng đội là giúp chính mình"],
    ["Chất lượng là uy tín thương hiệu", "Làm kỹ một lần, khỏi làm lại"],
    ["Cười lên, bán thêm một đơn", "Năng lượng tốt mở ra doanh số tốt"]
  ];
  function veKhauHieu(i) {
    var c = document.createElement("canvas"), W = 900, H = 260; c.width = W; c.height = H; var g = c.getContext("2d");
    var h = (i * 47 + 200) % 360, grad = g.createLinearGradient(0, 0, W, H);
    grad.addColorStop(0, "hsl(" + h + ",60%,22%)"); grad.addColorStop(1, "hsl(" + (h + 40) + ",60%,32%)");
    g.fillStyle = grad; rr(g, 4, 4, W - 8, H - 8, 24); g.fill(); g.strokeStyle = "rgba(255,255,255,0.35)"; g.lineWidth = 4; rr(g, 4, 4, W - 8, H - 8, 24); g.stroke();
    g.fillStyle = "#fff"; g.textAlign = "center"; g.textBaseline = "middle"; g.font = "800 54px system-ui,Segoe UI,Roboto,sans-serif";
    var t1 = KHAU_HIEU[i % KHAU_HIEU.length][0]; while (g.measureText(t1).width > W - 80 && g.font.indexOf("40px") < 0) g.font = "800 40px system-ui,sans-serif";
    g.fillText(t1, W / 2, 98); g.font = "500 32px system-ui,Segoe UI,Roboto,sans-serif"; g.fillStyle = "rgba(255,255,255,0.85)"; g.fillText(KHAU_HIEU[i % KHAU_HIEU.length][1], W / 2, 175);
    return c;
  }
  function veBangDieuHanh() {
    var c = document.createElement("canvas"), W = 1400, H = 560; c.width = W; c.height = H; var g = c.getContext("2d"), light = sang();
    g.fillStyle = light ? "#f3f7ff" : "#0c1830"; rr(g, 4, 4, W - 8, H - 8, 28); g.fill(); g.strokeStyle = "#2a6bff"; g.lineWidth = 6; rr(g, 4, 4, W - 8, H - 8, 28); g.stroke();
    g.textBaseline = "middle"; g.fillStyle = light ? "#12233f" : "#e8f0ff"; g.font = "800 44px system-ui,Segoe UI,Roboto,sans-serif"; g.textAlign = "left";
    g.fillText("BẢNG ĐIỀU HÀNH", 44, 58);
    g.font = "500 26px system-ui,sans-serif"; g.fillStyle = light ? "#5a6b86" : "#9fb4d8";
    var tt = kpiDuLieu ? (kpiDuLieu.updated ? "Cập nhật: " + kpiDuLieu.updated : "Số liệu thật của brain") : "Đang tải số liệu…";
    g.textAlign = "right"; g.fillText(cat(tt, 50), W - 44, 58); g.textAlign = "left";
    var ks = kpiDuLieu && kpiDuLieu.kpis || [];
    if (!ks.length) {
      g.fillStyle = light ? "#5a6b86" : "#9fb4d8"; g.font = "600 30px system-ui,sans-serif";
      g.fillText(kpiDuLieu ? "Chưa có số liệu thật cho brain này." : "Đang lấy số liệu…", 44, 190);
      g.font = "500 24px system-ui,sans-serif"; g.fillText("Số liệu hiện ở đây khi brain có file 00 - Dashboard/minmin-dashboard.json.", 44, 240);
    }
    var cols = 4, tw = 316, th = 150, gap = 24;
    ks.slice(0, 8).forEach(function (k, i) {
      var x = 44 + (i % cols) * (tw + gap), y = 100 + Math.floor(i / cols) * (th + 18);
      g.fillStyle = light ? "#ffffff" : "#13264a"; rr(g, x, y, tw, th, 18); g.fill();
      var tone = k.tone === "up" ? "#1fb86a" : k.tone === "down" ? "#e5484d" : k.tone === "warn" ? "#f5a623" : "#6fa8ff";
      g.fillStyle = tone; g.fillRect(x, y + 18, 6, th - 36);
      g.fillStyle = light ? "#5a6b86" : "#9fb4d8"; g.font = "500 24px system-ui,sans-serif"; g.fillText(cat(k.label, 24), x + 24, y + 34);
      g.fillStyle = light ? "#12233f" : "#ffffff"; g.font = "800 50px system-ui,sans-serif"; g.fillText(cat(String(k.value) + (k.unit ? " " + k.unit : ""), 13), x + 24, y + 86);
      if (k.delta) { g.fillStyle = tone; g.font = "600 24px system-ui,sans-serif"; g.fillText(cat(k.delta, 22), x + 24, y + 124); }
    });
    var al = kpiDuLieu && kpiDuLieu.alerts || [];
    if (al.length) {
      g.font = "600 24px system-ui,sans-serif"; var y0 = ks.length > 4 ? 440 : 290;
      al.slice(0, 3).forEach(function (a, i) { g.fillStyle = a.level === "critical" || a.level === "serious" ? "#e5484d" : a.level === "warning" ? "#f5a623" : "#1fb86a"; g.fillText("\u25cf " + cat(a.text, 100), 44, y0 + i * 34); });
    }
    return c;
  }
  function capNhatBang() { if (bang) capNhatSprite2(bang, veBangDieuHanh()); }
  function capNhatSprite2(mesh, canvas) { var old = mesh.material.map; mesh.material.map = new T.CanvasTexture(canvas); mesh.material.map.colorSpace = T.SRGBColorSpace; mesh.material.needsUpdate = true; if (old) old.dispose(); }
  function napKpi() {
    fetch("/hud/kpi?brain=" + encodeURIComponent(brain())).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      kpiDuLieu = d || { kpis: [] }; capNhatBang();
    }).catch(function () { kpiDuLieu = { kpis: [] }; capNhatBang(); });
  }

  // ---------- đồ vật ----------
  function ghe(x, z, rot, laStool) {
    var g = new T.Group(); g.position.set(x, 0, z); g.rotation.y = rot;
    var m = mat(sang() ? 0x93a4bd : 0x3a4c6c);
    var seat = laStool ? new T.Mesh(new T.CylinderGeometry(0.42, 0.42, 0.1, 18), m) : new T.Mesh(new T.BoxGeometry(0.95, 0.1, 0.95), m); seat.position.y = 0.4; g.add(seat);
    if (!laStool) { var lung = new T.Mesh(new T.BoxGeometry(0.95, 0.7, 0.1), m); lung.position.set(0, 0.85, -0.5); g.add(lung); }
    var tru = new T.Mesh(new T.CylinderGeometry(0.07, 0.07, 0.5, 8), mat(0x6f7f98)); tru.position.y = 0.2; g.add(tru);
    var de = new T.Mesh(new T.CylinderGeometry(0.4, 0.4, 0.05, 14), mat(0x6f7f98)); de.position.y = 0.03; g.add(de);
    scene.add(g);
  }
  function taoAgent(ten, role, laLead, home, rot) {
    var r = NV ? dungNguoi3D(ten, cat(role, 24), hue(ten), laLead) : dungRobot(ten, cat(role, 24), hue(ten), laLead);
    var a = { ten: ten, role: role || "", r: r, lead: !!laLead, home: home, kind: home.kind || "desk", huong: rot || 0,
              x: home.x, z: home.z, rot: rot || 0, q: [], cur: null, task: "", noiHet: 0, screen: null, trang: "Rảnh",
              seat: null, key: ten.toLowerCase(), walking: false, dd: 0, bam: 0, seed: Math.random() * 100, holdPose: "type", stuck: 0 };
    r.g.position.set(home.x, 0, home.z); r.g.rotation.y = a.rot; r.than.userData.agent = a;
    scene.add(r.g);
    return a;
  }
  function dungBan(slot, a, idx) {
    var g = new T.Group(); g.position.set(slot.desk.x, NV ? -0.2 : 0, slot.desk.z); g.rotation.y = slot.desk.rot;
    var mt = new T.Mesh(new T.BoxGeometry(2.6, 0.12, 1.3), mat(sang() ? 0xdfe6f2 : 0x2a3a58)); mt.position.set(0, 1.0, 0); g.add(mt);
    [[-1.2, -0.55], [1.2, -0.55], [-1.2, 0.55], [1.2, 0.55]].forEach(function (p) { var ch = new T.Mesh(new T.BoxGeometry(0.1, 1.0, 0.1), mat(0x8fa0b8)); ch.position.set(p[0], 0.5, p[1]); g.add(ch); });
    var vien = new T.Mesh(new T.BoxGeometry(1.2, 0.76, 0.06), mat(0x0f1626)); vien.position.set(0, 1.66, -0.38); g.add(vien);
    var man = new T.Mesh(new T.PlaneGeometry(1.1, 0.66), matManOff); man.position.set(0, 1.66, -0.345); g.add(man); a.screen = man; a.screenIdx = idx % 4;
    var de = new T.Mesh(new T.BoxGeometry(0.1, 0.35, 0.1), mat(0x8fa0b8)); de.position.set(0, 1.22, -0.38); g.add(de);
    var bp = new T.Mesh(new T.BoxGeometry(0.85, 0.03, 0.3), mat(0x2b3550)); bp.position.set(0, 1.075, 0.15); g.add(bp);       // bàn phím
    for (var r = 0; r < 3; r++) { var hang = new T.Mesh(new T.BoxGeometry(0.78, 0.012, 0.055), mat(0x8fa0b8)); hang.position.set(0, 1.095, 0.06 + r * 0.085); g.add(hang); }
    var ch = new T.Mesh(new T.SphereGeometry(0.07, 10, 8), mat(0x2b3550)); ch.scale.set(0.8, 0.5, 1.2); ch.position.set(0.62, 1.085, 0.15); g.add(ch);   // chuột
    var cap = new T.Mesh(new T.CylinderGeometry(0.06, 0.05, 0.1, 10), mat(0x6f8fff)); cap.position.set(-0.95, 1.11, -0.2); g.add(cap);                    // cốc
    scene.add(g);
    ghe(slot.stand.x, slot.stand.z, slot.rot, false);
    var w = slot.desk.rot;
    chanHinhChuNhat(slot.desk.x, slot.desk.z, w === Math.PI / 2 ? 1.3 : 2.6, w === Math.PI / 2 ? 2.6 : 1.3, 0, 0.45);
    chanTron(slot.stand.x, slot.stand.z, 0.5);
  }
  function dungTram(def) {
    var g = new T.Group(); g.position.set(12.6, 0, def.z); g.rotation.y = -Math.PI / 2;
    var acc = hsl(hue(def.id), 0.75, 0.52);
    var thung = new T.Mesh(new T.BoxGeometry(1.5, 2.2, 1.0), mat(sang() ? 0xe3e9f4 : 0x23324d)); thung.position.y = 1.1; g.add(thung);
    var den = mat(acc.getHex(), { emissive: acc.getHex(), emissiveIntensity: 0.35 });
    var m = new T.Mesh(new T.BoxGeometry(1.1, 0.7, 0.05), den); m.position.set(0, 1.45, 0.52); g.add(m);
    for (var k = 0; k < 3; k++) { var r = new T.Mesh(new T.BoxGeometry(1.1, 0.12, 0.05), mat(0x8fa0b8)); r.position.set(0, 0.8 - k * 0.22, 0.52); g.add(r); }
    var nh = spriteTu(veNhan(def.ten, "Trạm dữ liệu", "#" + acc.getHexString(), nenNhan()), 2.6);
    nh.position.set(0, 3.0, 0); g.add(nh);
    scene.add(g); chanHinhChuNhat(12.6, def.z, 1.0, 1.5, 0, 0.45);
    return { def: def, den: den, spot: { x: 10.7, z: def.z, kind: "st" }, g: g };
  }
  function dungBanHop() {
    var g = new T.Group(); g.position.y = NV ? -0.2 : 0;
    var mt = new T.Mesh(new T.BoxGeometry(TL, 0.14, TW), mat(sang() ? 0xd5deee : 0x2a3a58)); mt.position.y = 1.0; g.add(mt);
    [-TL / 2 + 0.7, TL / 2 - 0.7].forEach(function (x) { var ch = new T.Mesh(new T.BoxGeometry(0.25, 1.0, 1.5), mat(0x8fa0b8)); ch.position.set(x, 0.5, 0); g.add(ch); });
    var vien = new T.Mesh(new T.BoxGeometry(TL, 0.05, 0.06), mat(0x2a6bff, { emissive: 0x2a6bff, emissiveIntensity: 0.8 })); vien.position.set(0, 1.09, 0); g.add(vien);
    var holo = new T.Mesh(new T.BoxGeometry(TL - 1, 0.02, 1.2), new T.MeshBasicMaterial({ color: 0x3fb2ff, transparent: true, opacity: 0.0, depthWrite: false })); holo.position.y = 1.1; g.add(holo);
    var lap = new T.Group(); lap.position.set(TL / 2 - 0.9, 1.07, 0); lap.rotation.y = Math.PI / 2; g.add(lap);
    var dayL = new T.Mesh(new T.BoxGeometry(0.62, 0.035, 0.42), mat(0x9aa8c0)); dayL.position.y = 0.02; lap.add(dayL);
    var bpL = new T.Mesh(new T.BoxGeometry(0.5, 0.012, 0.2), mat(0x1c2538)); bpL.position.set(0, 0.043, 0.06); lap.add(bpL);
    var banhL = new T.Mesh(new T.BoxGeometry(0.16, 0.008, 0.1), mat(0x6d7b95)); banhL.position.set(0, 0.043, 0.16); lap.add(banhL);
    var le = new T.Group(); le.position.set(0, 0.04, -0.2); le.rotation.x = -0.3; lap.add(le);
    var vo = new T.Mesh(new T.BoxGeometry(0.62, 0.4, 0.025), mat(0x9aa8c0)); vo.position.y = 0.2; le.add(vo);
    var manL = new T.Mesh(new T.PlaneGeometry(0.56, 0.34), matManOn.length ? matManOn[0] : matManOff); manL.position.set(0, 0.2, 0.0135); le.add(manL);
    scene.add(g);
    var tham = new T.Mesh(new T.PlaneGeometry(TL + 3.5, TW + 5), new T.MeshBasicMaterial({ color: sang() ? 0xdbe6f7 : 0x1c2c4a })); tham.rotation.x = -Math.PI / 2; tham.position.y = 0.02; scene.add(tham);
    // ghế: đầu bàn bên phải là giám đốc; người khác ngồi hai bên, từ gần giám đốc ra xa, cuối cùng ghế cuối bàn
    var gs = [{ x: TL / 2 + 1.1, z: 0, kind: "seat", rot: -Math.PI / 2 }];
    for (var i = 7; i >= 0; i--) { var x = -4.55 + 1.3 * i; gs.push({ x: x, z: -2.05, kind: "seat", rot: 0 }); gs.push({ x: x, z: 2.05, kind: "seat", rot: Math.PI }); }
    gs.push({ x: -TL / 2 - 1.1, z: 0, kind: "seat", rot: Math.PI / 2 });
    gs.forEach(function (s) { ghe(s.x, s.z, s.rot, true); s.by = null; });
    return { ghe: gs, holo: holo };
  }
  function den(x, z, hex) {
    var g = new T.Group(); g.position.set(x, 0, z);
    var tru = new T.Mesh(new T.CylinderGeometry(0.05, 0.05, 2.6, 8), mat(0x6f7f98)); tru.position.y = 1.3; g.add(tru);
    var de = new T.Mesh(new T.CylinderGeometry(0.3, 0.3, 0.06, 14), mat(0x6f7f98)); de.position.y = 0.03; g.add(de);
    var chup = new T.Mesh(new T.CylinderGeometry(0.28, 0.4, 0.5, 14), new T.MeshBasicMaterial({ color: hex })); chup.position.y = 2.7; g.add(chup);
    var pl = new T.PointLight(hex, 0.9, 20, 1.6); pl.position.y = 2.6; g.add(pl);
    scene.add(g); chanTron(x, z, 0.4);
  }
  function dungCanh() {
    var light = sang(), nen = light ? 0xe9f0fa : 0x0d1524;
    scene = new T.Scene(); scene.background = new T.Color(nen); scene.fog = new T.Fog(nen, 55, 110);
    scene.add(new T.HemisphereLight(0xffffff, light ? 0xbfcbe0 : 0x24365a, light ? 1.0 : 0.75));
    var dl = new T.DirectionalLight(0xffffff, light ? 1.2 : 0.7); dl.position.set(-8, 18, 10); scene.add(dl);
    var san = new T.Mesh(new T.BoxGeometry(HX * 2, 0.3, HZ * 2), mat(light ? 0xf7f9fd : 0x16233a, { roughness: 0.9 })); san.position.y = -0.15; scene.add(san);
    var luoi = new T.GridHelper(HX * 2, Math.round(HX * 2), light ? 0xd5deec : 0x24385a, light ? 0xe4ebf6 : 0x1d2d49); luoi.position.y = 0.01; luoi.scale.z = HZ / HX; scene.add(luoi);
    var tuong = mat(light ? 0xdde6f4 : 0x1b2a46);
    var t1 = new T.Mesh(new T.BoxGeometry(HX * 2, 5.8, 0.3), tuong); t1.position.set(0, 2.9, -HZ - 0.15); scene.add(t1);
    var t2 = new T.Mesh(new T.BoxGeometry(0.3, 5.8, HZ * 2), tuong); t2.position.set(-HX - 0.15, 2.9, 0); scene.add(t2);
    var t3 = new T.Mesh(new T.BoxGeometry(0.3, 5.8, HZ * 2), tuong); t3.position.set(HX + 0.15, 2.9, 0); scene.add(t3);
    var vien = new T.Mesh(new T.BoxGeometry(HX * 2, 0.05, 0.12), mat(0x2a6bff, { emissive: 0x2a6bff, emissiveIntensity: 0.6 })); vien.position.set(0, 5.8, -HZ - 0.15); scene.add(vien);
    khoiTaoLuoi(); taoManHinh();
    // bảng điều hành (số liệu thật) giữa tường sau; khẩu hiệu hai bên và trên tường trái
    bang = new T.Mesh(new T.PlaneGeometry(9, 3.6), new T.MeshBasicMaterial({ map: new T.CanvasTexture(veBangDieuHanh()), toneMapped: false })); bang.material.map.colorSpace = T.SRGBColorSpace;
    bang.position.set(HX - 0.02, 3.95, 0); bang.rotation.y = -Math.PI / 2; scene.add(bang);   // sau lưng giám đốc
    function kh(i, x, y, z, ry, w) { var m = new T.Mesh(new T.PlaneGeometry(w, w * 260 / 900), new T.MeshBasicMaterial({ map: new T.CanvasTexture(veKhauHieu(i)), toneMapped: false })); m.material.map.colorSpace = T.SRGBColorSpace; m.position.set(x, y, z); m.rotation.y = ry; scene.add(m); }
    kh(0, -8.0, 3.5, -HZ + 0.02, 0, 5.0); kh(1, 8.0, 3.5, -HZ + 0.02, 0, 5.0); kh(6, 0, 3.5, -HZ + 0.02, 0, 5.0);
    kh(2, -HX + 0.02, 3.5, -6.2, Math.PI / 2, 5.0); kh(3, -HX + 0.02, 3.5, 0, Math.PI / 2, 5.0); kh(4, -HX + 0.02, 3.5, 6.2, Math.PI / 2, 5.0);
        den(-12.9, -9.2, 0xffd9a0); den(12.9, -9.2, 0xffd9a0); den(-12.9, 9.2, 0xffd9a0); den(12.9, 9.2, 0xffd9a0);
    tram = STATION_DEFS.map(dungTram);
    ban = dungBanHop();
    camera = new T.PerspectiveCamera(38, 1, 0.1, 250); raycaster = new T.Raycaster();
  }
  function datCamera() {
    if (!cam.dist) { cam.dist = 37 * Math.max(1, 1.6 / camera.aspect); camMacDinh = { az: cam.az, pol: cam.pol, dist: cam.dist, tx: cam.tx, ty: cam.ty, tz: cam.tz }; }
    var cp = Math.cos(cam.pol), sp = Math.sin(cam.pol), d = cam.dist;
    var cy = cam.ty + cp * d;
    if (cy < 0.35) { cy = 0.35; }
    camera.position.set(cam.tx + Math.sin(cam.az) * sp * d, cy, cam.tz + Math.cos(cam.az) * sp * d);
    camera.lookAt(cam.tx, cam.ty, cam.tz);
  }
  function giuCam() {
    if (cam.dist) cam.dist = Math.max(2, Math.min(75, cam.dist)); cam.pol = Math.max(0.05, Math.min(1.62, cam.pol));
    cam.tx = Math.max(-HX - 3, Math.min(HX + 3, cam.tx)); cam.tz = Math.max(-HZ - 3, Math.min(HZ + 3, cam.tz)); cam.ty = Math.max(0, Math.min(4, cam.ty));
  }
  // dịch điểm nhìn trên mặt sàn theo hướng camera (dx sang phải, dz tiến lên)
  function panCam(dx, dz) {
    var fx = -Math.sin(cam.az), fz = -Math.cos(cam.az), rx = Math.cos(cam.az), rz = -Math.sin(cam.az);
    cam.tx += rx * dx + fx * dz; cam.tz += rz * dx + fz * dz; giuCam();
  }
  function veCamMacDinh() { if (camMacDinh) { for (var k in camMacDinh) cam[k] = camMacDinh[k]; } }
  function phimCam(dt) {
    var v = cam.dist * 0.9 * dt, k = phim;
    if (k.arrowleft || k.a) panCam(-v, 0); if (k.arrowright || k.d) panCam(v, 0); if (k.arrowup || k.w) panCam(0, v); if (k.arrowdown || k.s) panCam(0, -v);
    if (k.q) cam.az += 1.4 * dt; if (k.e) cam.az -= 1.4 * dt;
    if (k["+"] || k["="] || k.pageup) cam.dist *= 1 - 1.4 * dt; if (k["-"] || k["_"] || k.pagedown) cam.dist *= 1 + 1.4 * dt;
    giuCam();
  }

  // ---------- đồng bộ danh sách agent: mỗi người một bàn + một ghế sát tường ----------
  function boTri(n) {
    var trai = Math.ceil(n * 0.3), con = n - trai, sau = Math.ceil(con / 2), truoc = con - sau, res = [], i;
    function sp(a, b, k, m) { return m <= 1 ? (a + b) / 2 : a + (b - a) * k / (m - 1); }
    for (i = 0; i < sau; i++) { var x = sp(-10, 8, i, sau); res.push({ desk: { x: x, z: -9.5, rot: 0 }, stand: { x: x, z: -8.55 }, rot: Math.PI }); }
    for (i = 0; i < truoc; i++) { var x2 = sp(-10, 8, i, truoc); res.push({ desk: { x: x2, z: 9.5, rot: Math.PI }, stand: { x: x2, z: 8.55 }, rot: 0 }); }
    for (i = 0; i < trai; i++) { var z = sp(-6.4, 6.4, i, trai); res.push({ desk: { x: -13.3, z: z, rot: Math.PI / 2 }, stand: { x: -12.35, z: z }, rot: -Math.PI / 2 }); }
    return res;
  }
  function dungNguoi(list) {
    list = list.slice(0, 24);
    var bt = boTri(list.length);
    list.forEach(function (ag, i) {
      var p = bt[i], a = taoAgent(ag.name || ag.slug, ag.role, false, { x: p.stand.x, z: p.stand.z, kind: "desk" }, p.rot);
      dungBan(p, a, i);
      agents[(ag.name || ag.slug).toLowerCase()] = a; if (ag.slug) agents[ag.slug.toLowerCase()] = a;
      a.group = ag.group || ""; ds.push(a);
    });
    var gh = ban.ghe[0];
    lead = taoAgent("MinMin", "Giám đốc AI", true, { x: gh.x, z: gh.z, kind: "seat" }, gh.rot);
    lead.seat = gh; gh.by = lead; lead.kind = "seat"; lead.holdPose = "listen"; lead.trang = "Điều hành";
    agents["minmin"] = lead; hienVat(lead, true);
  }
  function khach(ten) {
    var k = ten.toLowerCase(); if (agents[k]) return agents[k];
    var n = ds.length, a = taoAgent(ten, "Khách mời", false, { x: -12.2 + (n % 2) * 1.5, z: 8.6, kind: "desk" }, 0);
    agents[k] = a; ds.push(a); return a;
  }
  function timAgent(ten) {
    ten = String(ten || "").trim(); if (!ten) return null;
    var k = ten.toLowerCase(); if (agents[k]) return agents[k];
    for (var key in agents) if (key.indexOf(k) >= 0 || k.indexOf(key) >= 0) return agents[key];
    return khach(ten);
  }
  function hienVat(a, on) { a.r.vat.visible = !!on; a.r.but.visible = !!on; }

  // ---------- điều khiển hành động ----------
  function noi_(a, text, ms) {
    a.noiHet = now() + (ms || 2400);
    capNhatSprite(a.r.noi, veNoi(text, "#" + a.r.acc.getHexString()), 3.6);
    a.r.noi.visible = true;
  }
  function trangThai(a, t) {
    if (a.trang === t) return; a.trang = t;
    capNhatSprite(a.r.nhan, veNhan(a.ten, cat(t, 26), "#" + a.r.acc.getHexString(), nenNhan()));
  }
  function di(a, to, label) { a.q.push({ t: "walk", to: to, label: label, kind: to.kind || "desk" }); }
  function dung_(a, ms, pose, nhin, text, tt) { a.q.push({ t: "stay", ms: ms, pose: pose, nhin: nhin, text: text, tt: tt }); }
  function phatBieu(a, text, ms, tt) { a.q.push({ t: "stay", ms: ms || 6000, pose: "talk", text: text, tt: tt || "Đang trình bày", stand: true, speak: true }); }
  function cham(a) { a.q.length = 0; a.cur = null; a.walking = false; }
  function veBan(a, label) {
    cham(a); hienVat(a, false); di(a, a.home, label || "Về chỗ làm"); a.q.push({ t: "face", huong: a.huong }); a.q.push({ t: "hold", pose: "type", tt: "Đang làm việc" });
  }
  function toiGhe(a, label, tt) {
    var g = a.seat; if (!g) return;
    hienVat(a, true); di(a, g, label); a.q.push({ t: "face", huong: g.rot }); a.q.push({ t: "hold", pose: "listen", tt: tt || "Đang họp" });
  }

  // ---------- các phiên họp: mỗi lần chạy workflow và mỗi lượt chat là một phiên ----------
  var phien = {};
  function conTrongPhien(a, tru) { for (var k in phien) if (k !== tru && phien[k].set[a.key]) return true; return false; }
  function capGhe(a) {
    if (a.seat) return a.seat;
    for (var i = 1; i < ban.ghe.length; i++) if (!ban.ghe[i].by) { ban.ghe[i].by = a; a.seat = ban.ghe[i]; return a.seat; }
    return null;
  }
  function vaoPhien(key, a, tenHop) {
    var p = phien[key] || (phien[key] = { set: {}, ten: "" }); p.set[a.key] = a;
    if (a.lead) return;
    if (a.seat && a.kind === "seat") return;
    if (!capGhe(a)) return;
    cham(a); toiGhe(a, "Đi họp: " + cat(tenHop || p.ten || "họp nhóm", 18), "Đang họp");
  }
  function rutKhoiPhien(key, ok, loiNoi) {
    var p = phien[key]; if (!p) return; delete phien[key];
    Object.keys(p.set).forEach(function (k) {
      var a = p.set[k]; if (a.lead || conTrongPhien(a)) return;
      if (a.seat) { a.seat.by = null; a.seat = null; }
      cham(a); noi_(a, ok ? "Xong rồi, em về làm tiếp" : "Cần xem lại phần này", 2400); veBan(a, "Về chỗ làm");
    });
    if (lead && loiNoi) { lead.q.length = 0; phatBieu(lead, loiNoi, 4200, "Chốt họp"); }
    if (ban && Object.keys(phien).length === 0) ban.sangDen = 0;
  }
  function lamTram(a, tool) {
    var t = tramCua(tool); if (!a || now() - (a.luotTool || 0) < 2500) return; a.luotTool = now();
    var trongHop = !!a.seat && conTrongPhien(a);
    cham(a); hienVat(a, false);
    di(a, t.st.spot, "Đi lấy dữ liệu: " + cat(t.nhan, 14));
    dung_(a, 2400, "type", null, "Lấy dữ liệu: " + cat(t.nhan, 20), "Lấy dữ liệu"); t.st.sang = now() + 2800;
    if (trongHop || a.lead) { hienVat(a, true); di(a, a.seat || a.home, "Về chỗ họp"); a.q.push({ t: "face", huong: (a.seat || a.home).rot != null ? (a.seat || a.home).rot : a.huong }); a.q.push({ t: "hold", pose: "listen", tt: a.lead ? "Điều hành" : "Đang họp" }); a.q.push({ t: "say", text: "Có dữ liệu từ " + cat(t.nhan, 16), ms: 3000 }); }
    else veBan(a, "Về chỗ làm");
  }

  // ---------- chat: ai liên quan tới câu hỏi thì vào họp ----------
  var NHOM = [
    { q: /doanh thu|kinh doanh|bao cao|so lieu|ket qua|hom nay|tong quan/, t: ["bao cao", "dashboard", "ke toan", "giam sat", "sales", "ban hang", "ads", "quang cao"] },
    { q: /don|hang|kho|ton|giao|van chuyen|dat hang/, t: ["kho", "ban hang", "sales", "dat hang", "don"] },
    { q: /quang cao|ads|camp|ngan sach|facebook|tiktok/, t: ["ads", "quang cao", "marketing", "media", "lead"] },
    { q: /khach|comment|inbox|cskh|tra loi|khieu nai|zalo/, t: ["cskh", "cham soc", "khach", "buyer", "conversation"] },
    { q: /content|bai viet|viet|video|anh|hinh|dang bai|fanpage|kenh/, t: ["content", "video", "media", "anh", "bien tap", "dang bai", "dieu phoi"] },
    { q: /thue|hoa don|luong|ke toan|chi phi|loi nhuan|tai chinh/, t: ["ke toan", "thue", "nhan su", "bang luong", "giam sat"] },
    { q: /nghien cuu|tim hieu|phan tich|doi thu|thi truong/, t: ["research", "lead engine", "phan tich", "kiem chung"] }
  ];
  function bo(s) { return String(s || "").toLowerCase().replace(/đ/g, "d").normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  function lienQuan(text) {
    var q = bo(text), diem = [];
    var tu = q.split(/[^a-z0-9]+/).filter(function (w) { return w.length >= 4; });
    ds.forEach(function (a) {
      var hay = bo(a.ten + " " + a.role + " " + (a.group || "")), d = 0;
      NHOM.forEach(function (n) { if (n.q.test(q)) n.t.forEach(function (k) { if (hay.indexOf(k) >= 0) d += 2; }); });
      tu.forEach(function (w) { if (hay.indexOf(w) >= 0) d += 1; });
      if (d > 0) diem.push({ a: a, d: d });
    });
    diem.sort(function (x, y) { return y.d - x.d; });
    return diem.slice(0, 5).map(function (x) { return x.a; });
  }
  var luotCu = 0;
  function chonNguoiLayDuLieu(i) {
    var p = phien.chat; if (!p) return lead;
    var ds2 = Object.keys(p.set).map(function (k) { return p.set[k]; }).filter(function (a) { return !a.lead && !a.walking && a.q.length === 0; });
    if (!ds2.length) return lead;
    var pref = [["kho", "ban hang", "sales", "ke toan"], ["bao cao", "dashboard", "ke toan"], ["research", "phan tich"], ["media", "content"]][i % 4] || [];
    for (var j = 0; j < ds2.length; j++) { var h = bo(ds2[j].ten + " " + ds2[j].role); if (pref.some(function (k) { return h.indexOf(k) >= 0; })) return ds2[j]; }
    return ds2[(luotCu++) % ds2.length];
  }

  function suKien(ev) {
    var k = ev.k, a, p, key = ev.run || "chat";
    if (k === "run_start") {
      phien[key] = { set: {}, ten: ev.name }; if (ban) ban.sangDen = now() + 3600000;
      if (lead) { noi_(lead, "Triệu tập họp: " + cat(ev.name, 24), 3400); trangThai(lead, "Chủ trì họp"); }
    } else if (k === "step") {
      a = timAgent(ev.agent); if (!a) return;
      vaoPhien(key, a, (phien[key] && phien[key].ten) || "");
      a.task = ev.task || ""; a.q.push({ t: "say", text: "Nhận việc: " + (cat(ev.task, 80) || "bắt đầu làm"), ms: 4200 });
    } else if (k === "tool") {
      a = timAgent(ev.agent) || lead; if (!a) return; lamTram(a, ev.tool);
    } else if (k === "verify") {
      a = timAgent(ev.agent); p = timAgent(ev.target); if (!a || !p) return;
      vaoPhien(key, a, "Kiểm chứng"); phatBieu(a, "Em kiểm chứng kết quả của " + cat(p.ten, 20), 4000, "Kiểm chứng");
    } else if (k === "step_done") {
      a = timAgent(ev.agent); if (!a) return;
      phatBieu(a, ev.out ? "Kết quả: " + cat(ev.out, 170) : "Đã xong bước này", 7000, "Báo cáo kết quả");
    } else if (k === "run_end") {
      rutKhoiPhien(key, ev.ok, ev.ok ? "Chốt xong. Cảm ơn cả nhóm." : "Lần chạy có lỗi, cần xem lại.");
    }
  }

  // ---------- mô phỏng ----------
  var moPhong = 0;
  function chayMau() {
    var xs = ds.filter(function (x) { return !x.lead; }).slice(0, 4);
    if (xs.length < 2) { toast("Brain này chưa có agent nào để mô phỏng. Hãy tạo vài agent ở trang Cộng sự."); return; }
    var id = "demo" + (++moPhong);
    function at(ms, ev) { setTimeout(function () { if (mo) suKien(ev); }, ms); }
    at(0, { k: "run_start", run: id, name: "Bán hàng dịp Tết (mô phỏng)" });
    at(900, { k: "step", run: id, agent: xs[0].ten, task: "Kiểm tra tồn kho và sức bán" });
    at(9000, { k: "tool", run: id, agent: xs[0].ten, tool: "mcp__pos__orders" });
    at(16000, { k: "step_done", run: id, agent: xs[0].ten, out: "Tồn kho đủ cho 9 mã bán chạy, 2 mã sắp hết cần nhập thêm." });
    at(17000, { k: "step", run: id, agent: xs[1].ten, task: "Lập phương án nguồn hàng" });
    at(22000, { k: "tool", run: id, agent: xs[1].ten, tool: "WebSearch" });
    at(29000, { k: "step_done", run: id, agent: xs[1].ten, out: "Đề xuất nhập thêm 2 mã từ nhà cung cấp gần nhất, về trong 3 ngày." });
    var x3 = xs[2] || xs[0], x4 = xs[3] || xs[1];
    at(30000, { k: "step", run: id, agent: x3.ten, task: "Xây thông điệp chiến dịch" });
    at(36000, { k: "verify", run: id, agent: x4.ten, target: x3.ten });
    at(43000, { k: "step_done", run: id, agent: x3.ten, out: "Thông điệp chính: Quà Tết đẹp, giao nhanh, đổi trả dễ." });
    at(51000, { k: "run_end", run: id, ok: true });
  }
  function toast(t) {
    var el = $("mmOfficeToast"); if (!el) return; el.textContent = t; el.hidden = false;
    clearTimeout(toast.h); toast.h = setTimeout(function () { el.hidden = true; }, 5000);
  }

  // ---------- chạy mỗi khung hình ----------
  function viTriDi(x, z, c) {                  // chỗ đứng có hợp lệ không (gần điểm đầu/cuối thì được phép)
    if (Math.abs(x) > HX - 0.6 || Math.abs(z) > HZ - 0.6) return false;
    if (Math.hypot(x - c.to.x, z - c.to.z) < 1.0 || Math.hypot(x - c.from.x, z - c.from.z) < 1.0) return true;
    return !blocked[gj(z) * GW + gi(x)];
  }
  function banDo() { return ds.concat(lead ? [lead] : []); }
  function buoc(a, dt, t) {
    var r = a.r, c = a.cur, speed = r.hum ? 2.5 : 3.3;
    if (!c) {
      c = a.cur = a.q.shift() || null;
      if (c) {
        if (c.t === "stay") { c.het = now() + c.ms; if (c.text) noi_(a, c.text, c.ms); if (c.tt) trangThai(a, c.tt); if (c.speak) nguoiNoi = a; }
        else if (c.t === "walk") {
          c.from = { x: a.x, z: a.z }; c.path = timDuong(a.x, a.z, c.to.x, c.to.z, a); c.i = 0; a.walking = true; c.moc = now(); c.mx = a.x; c.mz = a.z;
          if (c.label) trangThai(a, c.label);
        } else if (c.t === "say") { noi_(a, c.text, c.ms); a.cur = null; return buoc(a, dt, t); }
      }
    }
    var dang = a.holdPose, sw = 0, dungDay = 0;
    if (c) {
      if (c.t === "walk") {
        var p = c.path[c.i];
        if (!p) { a.cur = null; a.walking = false; a.kind = c.kind; }
        else {
          var dx = p.x - a.x, dz = p.z - a.z, d = Math.hypot(dx, dz) || 1, st = speed * dt, vx = dx / d, vz = dz / d, sx = 0, sz = 0;
          banDo().forEach(function (o) {            // tránh nhau: đẩy ra khỏi người đang ở gần
            if (o === a) return; var ox = a.x - o.x, oz = a.z - o.z, od = Math.hypot(ox, oz);
            if (od < 1.0 && od > 0.001) { var w = (1.0 - od) / 1.0; sx += ox / od * w; sz += oz / od * w; }
          });
          vx += sx * 1.8; vz += sz * 1.8; var vl = Math.hypot(vx, vz) || 1; vx /= vl; vz /= vl;
          var nx = a.x + vx * st, nz = a.z + vz * st;
          if (!viTriDi(nx, nz, c)) { nx = a.x + dx / d * st; nz = a.z + dz / d * st; if (!viTriDi(nx, nz, c)) { nx = a.x; nz = a.z; } }
          a.x = nx; a.z = nz; a.huongDich = Math.atan2(vx, vz);
          if (Math.hypot(p.x - a.x, p.z - a.z) < Math.max(0.18, st)) { a.x = p.x; a.z = p.z; c.i++; if (c.i >= c.path.length) { a.cur = null; a.walking = false; a.kind = c.kind; } }
          if (now() - c.moc > 1600) {              // kẹt: chưa nhúc nhích bao nhiêu thì tìm đường lại
            if (Math.hypot(a.x - c.mx, a.z - c.mz) < 0.35) { c.path = timDuong(a.x, a.z, c.to.x, c.to.z, a); c.i = 0; }
            c.moc = now(); c.mx = a.x; c.mz = a.z;
          }
        }
        dang = "walk"; sw = Math.sin(t * 11);
      } else if (c.t === "stay") {
        if (c.nhin) a.huongDich = Math.atan2(c.nhin.x - a.x, c.nhin.z - a.z);
        dang = c.pose; if (c.stand) dungDay = 1; if (now() >= c.het) { a.cur = null; if (c.speak && nguoiNoi === a) nguoiNoi = null; }
      } else if (c.t === "face") { a.huongDich = c.huong; a.cur = null; }
      else if (c.t === "hold") { dang = c.pose; a.holdPose = c.pose; if (c.tt) trangThai(a, c.tt); if (a.q.length) a.cur = null; }
    }
    if (a.huongDich != null) { var dd = a.huongDich - a.rot; while (dd > Math.PI) dd -= Math.PI * 2; while (dd < -Math.PI) dd += Math.PI * 2; a.rot += dd * Math.min(1, dt * 9); }
    a.dd += (dungDay - a.dd) * Math.min(1, dt * 6);
    var chongoi = !a.walking && (a.kind === "desk" || a.kind === "seat"), ngoiK = chongoi ? 1 - a.dd : 0;
    var ox = chongoi ? -Math.sin(a.rot) * 0.6 * a.dd : 0, oz = chongoi ? -Math.cos(a.rot) * 0.6 * a.dd : 0;
    r.g.position.set(a.x + ox, -0.13 * r.s * ngoiK, a.z + oz); r.g.rotation.y = a.rot;
    if (r.hum) nguoiKhung(a, r, dang, dt, t, ngoiK); else {
    var bob = a.walking ? Math.abs(Math.sin(t * 11)) * 0.07 : Math.sin(t * 1.6 + a.seed) * 0.012;
    r.than.position.y = 0.95 + bob; r.dau.position.y = 1.78 + bob;
    var gc = -1.35 * ngoiK;
    r.chanT.rotation.x = lerp(r.chanT.rotation.x, a.walking ? sw * 0.7 : gc, 0.3); r.chanP.rotation.x = lerp(r.chanP.rotation.x, a.walking ? -sw * 0.7 : gc, 0.3);
    // ---- tay và ngón tay ----
    var Lx = 0.05, Lz = 0.04, Le = -0.15, Rx = 0.05, Rz = -0.04, Re = -0.15, ck = [0.25, 0.25], sn = Math.sin;
    if (dang === "walk") { Lx = -sw * 0.6; Rx = sw * 0.6; Le = -0.25; Re = -0.25; }
    else if (dang === "type") { var gm = sn(t * 9 + a.seed) * 0.05, gm2 = sn(t * 7.3 + a.seed + 1.7) * 0.05; Lx = -1.45 + gm; Rx = -1.45 + gm2; Le = -0.12 + gm2; Re = -0.12 + gm; Lz = 0.35; Rz = -0.35; ck = [-1, -1]; }
    else if (dang === "listen") { Lx = -1.4; Le = -0.15; Lz = 0.3; Rx = -1.4; Re = -0.15 + sn(t * 9 + a.seed) * 0.06; Rz = -0.3; ck = [0.55, 0.7]; }
    else if (dang === "talk") { Lx = -0.85; Le = -1.25; Rx = -0.9 + sn(t * 2.6 + a.seed) * 0.35; Rz = -0.5 + sn(t * 1.7) * 0.2; Re = -1.0 + sn(t * 3.3) * 0.55; ck = [0.55, 0.12]; }
    function datTay(h, sx, sz, ex) { h.sh.rotation.x = lerp(h.sh.rotation.x, sx, 0.22); h.sh.rotation.z = lerp(h.sh.rotation.z, sz, 0.22); h.el.rotation.x = lerp(h.el.rotation.x, ex, 0.22); }
    datTay(r.tT, Lx, Lz, Le); datTay(r.tP, Rx, Rz, Re);
    [r.tT, r.tP].forEach(function (h, side) {
      for (var i = 0; i < h.ngon.length; i++) {
        var cu = ck[side] < 0 ? 0.35 + 0.4 * (0.5 + 0.5 * sn(t * (13 + i * 1.9) + a.seed + side * 2)) : ck[side] + (i === 4 ? 0 : 0.1 * sn(t * 2 + i));
        h.ngon[i].rotation.x = lerp(h.ngon[i].rotation.x, -cu, 0.3);
      }
    });
    // ---- chớp mắt: mỗi người một nhịp riêng, khoảng 3 đến 5 giây chớp một lần ----
    var chu = 3.2 + (a.seed % 1.7), ph = (t + a.seed) % chu, ch = ph < 0.16 ? 1 - Math.abs(ph - 0.08) / 0.08 : 0;
    if (ph > 1.1 && ph < 1.22 && a.seed > 50) ch = 1 - Math.abs(ph - 1.16) / 0.06;           // thỉnh thoảng chớp đôi
    for (var ei = 0; ei < r.mat_mat.length; ei++) r.mat_mat[ei].scale.y = 1.3 * (1 - 0.9 * Math.max(0, ch));
    // ---- đầu: nhìn người đang nói / nhìn quanh / gật khi nói ----
    var yaw = 0;
    if (dang === "talk") r.dau.rotation.x = sn(t * 5 + a.seed) * 0.08;
    else r.dau.rotation.x *= 0.85;
    if (nguoiNoi && nguoiNoi !== a && !a.walking) { var rel = Math.atan2(nguoiNoi.x - a.x, nguoiNoi.z - a.z) - a.rot; while (rel > Math.PI) rel -= Math.PI * 2; while (rel < -Math.PI) rel += Math.PI * 2; yaw = cl(rel, -1.1, 1.1); }
    else if (!a.walking) yaw = sn(t * 0.45 + a.seed) * 0.22 * (dang === "type" ? 1 : 0.5);
    r.dau.rotation.y = lerp(r.dau.rotation.y, yaw, 0.12);
    }
    // ---- màn hình sáng khi đang dùng ----
    if (a.screen) { var dungMay = a.kind === "desk" && !a.walking && ngoiK > 0.5, m = dungMay ? matManOn[a.screenIdx] : matManOff; if (a.screen.material !== m) a.screen.material = m; }
    if (r.noi.visible && now() > a.noiHet) r.noi.visible = false;
  }

  var lastManHinh = 0;
  function khung() {
    rafId = requestAnimationFrame(khung);
    var n = now(), dt = Math.min(0.05, (n - lanCuoi) / 1000) * (window.__mmOfficeSpeed || 1); lanCuoi = n; tNow += dt; var t = tNow; phimCam(dt);
    var vua = host.clientWidth, cao = host.clientHeight;
    if (renderer.domElement.width !== Math.floor(vua * renderer.getPixelRatio()) || renderer.domElement.height !== Math.floor(cao * renderer.getPixelRatio())) {
      renderer.setSize(vua, cao, false); camera.aspect = vua / Math.max(1, cao);
      camera.fov = camera.aspect < 0.8 ? 52 : 38; camera.updateProjectionMatrix();
    }
    if (n - lastManHinh > 200) { lastManHinh = n; veManHinh(t); }
    ds.forEach(function (a) { buoc(a, dt, t); }); if (lead) buoc(lead, dt, t);
    tram.forEach(function (s) { s.den.emissiveIntensity = (s.sang && n < s.sang) ? 1.4 : 0.35; });
    if (ban) ban.holo.material.opacity = n < (ban.sangDen || 0) ? 0.22 + Math.sin(t * 4) * 0.06 : 0;
    datCamera(); renderer.render(scene, camera);
  }

  function nhapTay() {
    var el = renderer.domElement, ptr = {}, lastD = 0, lastM = null, moved = 0;
    el.style.touchAction = "none"; el.tabIndex = 0; el.style.outline = "none";
    el.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    el.addEventListener("pointerdown", function (e) { el.setPointerCapture(e.pointerId); el.focus(); ptr[e.pointerId] = { x: e.clientX, y: e.clientY, b: e.button, sh: e.shiftKey || e.ctrlKey }; moved = 0; lastD = 0; lastM = null; });
    el.addEventListener("pointermove", function (e) {
      var p = ptr[e.pointerId]; if (!p) return; var ids = Object.keys(ptr), px = e.clientX - p.x, py = e.clientY - p.y, k = cam.dist * 0.0021;
      if (ids.length >= 2) {
        var o = ptr[ids.filter(function (i) { return +i !== e.pointerId; })[0]]; var d = Math.hypot(e.clientX - o.x, e.clientY - o.y), mx = (e.clientX + o.x) / 2, my = (e.clientY + o.y) / 2;
        if (lastD) cam.dist *= lastD / d; if (lastM) panCam(-(mx - lastM.x) * k, (my - lastM.y) * k); lastD = d; lastM = { x: mx, y: my };
      } else if (p.b === 2 || p.b === 1 || p.sh) {
        panCam(-px * k, py * k);
      } else {
        cam.az -= px * 0.006; cam.pol -= py * 0.005;
      }
      giuCam(); moved += Math.abs(px) + Math.abs(py); p.x = e.clientX; p.y = e.clientY;
    });
    function len(e) {
      delete ptr[e.pointerId]; lastD = 0; lastM = null;
      if (moved < 6 && e.button === 0) chamRobot(e);
    }
    el.addEventListener("pointerup", len); el.addEventListener("pointercancel", function (e) { delete ptr[e.pointerId]; lastD = 0; lastM = null; });
    el.addEventListener("dblclick", veCamMacDinh);
    el.addEventListener("wheel", function (e) {
      e.preventDefault();
      // phóng tới con trỏ: dời điểm nhìn một chút về phía chuột
      var rc = el.getBoundingClientRect(), nx = ((e.clientX - rc.left) / rc.width) * 2 - 1, f = Math.exp(Math.max(-200, Math.min(200, e.deltaY)) * 0.0012), dn = cam.dist * (f - 1);
      if (f < 1) panCam(nx * -dn * 0.35, 0);
      cam.dist *= f; giuCam();
    }, { passive: false });
    kd = function (e) { if (!anBat() || /input|textarea/i.test((e.target && e.target.tagName) || "")) return; var key = (e.key || "").toLowerCase(); if (key === "r" || key === "home") { veCamMacDinh(); return; } phim[key] = true; };
    ku = function (e) { delete phim[(e.key || "").toLowerCase()]; };
    window.addEventListener("keydown", kd); window.addEventListener("keyup", ku);
  }
  function chamRobot(e) {
    var rc = renderer.domElement.getBoundingClientRect();
    raycaster.setFromCamera({ x: ((e.clientX - rc.left) / rc.width) * 2 - 1, y: -((e.clientY - rc.top) / rc.height) * 2 + 1 }, camera);
    var meshes = []; ds.concat(lead ? [lead] : []).forEach(function (a) { meshes.push(a.r.than); });
    var hit = raycaster.intersectObjects(meshes, false)[0];
    var el = $("mmOfficeCard"); if (!el) return;
    if (!hit) { el.hidden = true; return; }
    var a = hit.object.userData.agent;
    el.innerHTML = "<b></b><span></span><i></i>"; el.children[0].textContent = a.ten; el.children[1].textContent = a.role || "";
    el.children[2].textContent = a.task ? "Việc: " + cat(a.task, 80) : "Trạng thái: " + a.trang; el.hidden = false;
  }

  function hoi() {
    if (!mo) return;
    fetch("/office/events?since=" + seq + "&brain=" + encodeURIComponent(brain())).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d || !mo) return;
      if (d.reset) seq = 0;
      d.events.forEach(function (ev) { suKien(ev); });
      seq = d.seq;
    }).catch(function () {});
  }

  // ---------- mở / đóng ----------
  function nap() {
    if (T) return Promise.resolve(true);
    return import(THREE_URL).then(function (m) { T = m; return true; }).catch(function () { return false; });
  }
  function xoaCanh() {
    if (rafId) cancelAnimationFrame(rafId); rafId = 0;
    if (kd) { window.removeEventListener("keydown", kd); window.removeEventListener("keyup", ku); kd = ku = null; } phim = {};
    cam.az = -0.62; cam.pol = 0.95; cam.dist = 0; cam.tx = 0.4; cam.ty = 0.6; cam.tz = 1.0;
    if (renderer) { renderer.dispose(); if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement); }
    renderer = scene = camera = null; agents = {}; ds = []; lead = null; tram = []; ban = null; phien = {}; bang = null; manHinh = []; nguoiNoi = null;
  }
  function dung(list) {
    xoaCanh();
    cv = document.createElement("canvas"); cv.className = "mm-office-cv"; host.insertBefore(cv, host.firstChild);
    renderer = new T.WebGLRenderer({ canvas: cv, antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    dungCanh(); dungNguoi(list); nhapTay(); lanCuoi = now(); tNow = 0; khung(); napKpi();
  }
  function mon() {
    var b = brain();
    return fetch("/agents?brain=" + encodeURIComponent(b) + "&prompt=0").then(function (r) { return r.json(); })
      .then(function (d) { return (d.agents || []).sort(function (a, b2) { return (b2.last_chat_at || 0) - (a.last_chat_at || 0); }); })
      .catch(function () { return []; });
  }
  function mo_() {
    if (mo) return; mo = true;
    host.hidden = false; document.documentElement.classList.add("mm-office-on");
    var nut = $("officeToggleBtn"); if (nut) nut.setAttribute("aria-pressed", "true");
    Promise.all([nap().then(function (ok) { return ok ? napNguoi().then(function () { return ok; }) : ok; }), mon()]).then(function (r) {
      if (!mo) return;
      if (!r[0]) { toast("Máy này không dựng được cảnh 3D"); dong(); return; }
      try { dung(r[1]); } catch (e) { console.warn("[office]", e); toast("Không dựng được văn phòng 3D"); dong(); return; }
      seq = 0; hoi(); pollId = setInterval(hoi, 1500); kpiId = setInterval(napKpi, 60000);
      if (!r[1].length) toast("Brain này chưa có agent nào. Tạo agent ở trang Cộng sự để họ xuất hiện ở đây.");
    });
  }
  function dong() {
    if (!mo) return; mo = false; clearInterval(pollId); clearInterval(kpiId);
    host.hidden = true; document.documentElement.classList.remove("mm-office-on");
    var nut = $("officeToggleBtn"); if (nut) nut.setAttribute("aria-pressed", "false");
    xoaCanh();
  }
  function khoiTao() {
    if (daDung) return; daDung = true;
    var root = document.querySelector(".hud-center"); if (!root) return;
    var testGL = document.createElement("canvas"); var gl = null;
    try { gl = testGL.getContext("webgl2") || testGL.getContext("webgl"); } catch (e) {}
    if (!gl) return;
    host = document.createElement("div"); host.id = "mmOffice"; host.hidden = true;
    host.innerHTML = '<div class="mm-office-bar"><b>Văn phòng AI 3D</b><span>Kéo xoay · kéo phải/WASD đi quanh · cuộn phóng · R về góc đầu</span>' +
      '<button type="button" id="mmOfficeSim">Mô phỏng</button><button type="button" id="mmOfficeFs">Toàn màn hình</button><button type="button" id="mmOfficeWin">Cửa sổ riêng</button><button type="button" id="mmOfficeX" aria-label="Đóng văn phòng">Đóng</button></div>' +
      '<div class="mm-office-card" id="mmOfficeCard" hidden></div><div class="mm-office-toast" id="mmOfficeToast" hidden></div>';
    root.appendChild(host);
    var nut = document.createElement("button");
    nut.id = "officeToggleBtn"; nut.type = "button"; nut.className = "brain-overlay-toggle mm-office-btn";
    nut.setAttribute("aria-pressed", "false"); nut.title = "Văn phòng AI 3D: xem các agent đang làm việc"; nut.setAttribute("aria-label", "Mở văn phòng AI 3D");
    nut.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="9" width="14" height="9" rx="3"></rect><circle cx="9.5" cy="13.5" r="1"></circle><circle cx="14.5" cy="13.5" r="1"></circle><path d="M12 9V6M10 6h4M3 13v2M21 13v2"></path></svg>';
    root.appendChild(nut);
    nut.addEventListener("click", function () { mo ? dong() : mo_(); });
    $("mmOfficeX").addEventListener("click", dong);
    $("mmOfficeSim").addEventListener("click", chayMau);
    $("mmOfficeFs").addEventListener("click", function () {
      try { if (document.fullscreenElement) document.exitFullscreen(); else if (host.requestFullscreen) host.requestFullscreen(); else if (host.webkitRequestFullscreen) host.webkitRequestFullscreen(); } catch (e) {}
    });
    $("mmOfficeWin").addEventListener("click", function () {
      var w = null; try { w = window.open("/office-3d?brain=" + encodeURIComponent(brain()), "mmOfficeWin", "popup=yes,width=1500,height=900"); } catch (e) {}
      if (!w) toast("Trình duyệt chặn cửa sổ mới. Hãy cho phép cửa sổ bật lên cho trang này."); else dong();
    });
    if (window.__mmOfficeSolo) { document.body.classList.add("mm-office-solo"); }
    document.addEventListener("visibilitychange", function () { if (document.hidden && mo) { clearInterval(pollId); } else if (mo) { pollId = setInterval(hoi, 1500); } });
  }

  var chatTimer = 0, kenh = null;
  try { if (window.BroadcastChannel) kenh = new BroadcastChannel("minmin-office"); } catch (e) { kenh = null; }
  function phat(loai, d) { if (kenh && !window.__mmOfficeSolo) { try { kenh.postMessage({ loai: loai, d: d }); } catch (e) {} } }
  if (kenh && window.__mmOfficeSolo) kenh.onmessage = function (ev) { var m = ev.data || {}; var O = window.MinMinOffice; if (!O) return; if (m.loai === "start") O.onChatStart(m.d); else if (m.loai === "tool") O.onChatTool(m.d); else if (m.loai === "end") O.onChatEnd(m.d); };
  window.MinMinOffice = {
    nv: function () { return NV; }, ag: function () { return agents; },
    open: function () { khoiTao(); mo_(); }, close: dong, toggle: function () { mo ? dong() : mo_(); },
    // khung chat (app.js): MinMin nhận câu hỏi -> người liên quan vào họp; gọi công cụ -> cử người đi lấy dữ liệu;
    // trả lời xong -> MinMin đứng dậy trình bày chính câu trả lời thật
    onChatStart: function (text) {
      phat("start", text);
      if (!mo || !lead) return; clearTimeout(chatTimer);
      if (phien.chat) rutKhoiPhien("chat", true, "");
      phien.chat = { set: {}, ten: "Họp với MinMin" }; phien.chat.set.minmin = lead;
      noi_(lead, "Triệu tập họp", 2500); trangThai(lead, "Chủ trì họp");
      lienQuan(text).forEach(function (a, i) { setTimeout(function () { if (mo && phien.chat) { vaoPhien("chat", a, "Họp với MinMin"); } }, 500 + i * 700); });
    },
    onChatTool: function (data) {
      phat("tool", data && { tool: data.tool });
      if (!mo || !lead) return; var tool = data && data.tool; if (!tool || tool === "ask_javis") return;
      var a = phien.chat ? chonNguoiLayDuLieu(tramCua(tool).i) : lead; lamTram(a, tool);
    },
    onChatEnd: function (text) {
      phat("end", String(text || "").slice(0, 600));
      if (!mo || !phien.chat) return; clearTimeout(chatTimer);
      var tom = String(text || "").replace(/[#*`>_\-]+/g, " ").replace(/\s+/g, " ").trim();
      if (tom && lead) phatBieu(lead, cat(tom, 190), 8000, "Trả lời");
      chatTimer = setTimeout(function () { rutKhoiPhien("chat", true, ""); if (lead) trangThai(lead, "Điều hành"); }, tom ? 9500 : 3500);
    },
    demo: chayMau, cam: cam
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", khoiTao); else khoiTao();
})();
