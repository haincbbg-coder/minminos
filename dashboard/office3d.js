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
  // giao diện văn phòng: mặc định SÁNG (dịu mắt), nút trên thanh chuyển sáng/tối và nhớ lựa chọn
  var themeOv = "light"; try { var tv = localStorage.getItem("mmOfficeTheme"); if (tv === "light" || tv === "dark") themeOv = tv; } catch (e) {}
  function sang() { return themeOv === "light"; }
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
    { id: "brain", ten: "Bộ nhớ Brain", z: -8.5, re: /^(read|write|edit|glob|grep|notebook|vault|memory|javis_(use_skill|task)|ask_javis)/i },
    { id: "mcp", ten: "Dữ liệu ngoài", z: -5.7, re: /^mcp__/i },
    { id: "web", ten: "Mạng và web", z: -2.9, re: /(websearch|webfetch|browser|chrome|fetch|search)/i },
    { id: "lenh", ten: "Máy chạy lệnh", z: 2.9, re: /./ }
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
  // lưới phủ cả văn phòng chính lẫn hai phòng bên (GX = nửa bề ngang của cả biệt thự); cửa đôi ở giữa tường bên, z từ -DOOR đến DOOR
  var GX = 33.6, DOOR = 1.4, RW = 19;
  var CELL = 0.4, GW = Math.ceil(GX * 2 / CELL), GH = Math.ceil(HZ * 2 / CELL), blocked = null;
  function gi(x) { return Math.floor((x + GX) / CELL); }
  function gj(z) { return Math.floor((z + HZ) / CELL); }
  function cx(i) { return -GX + (i + 0.5) * CELL; }
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
    for (var i = 0; i < GW; i++) for (var j = 0; j < GH; j++) {
      var x = cx(i), z = cz(j), ax = Math.abs(x);
      if (ax > GX - 0.7 || Math.abs(z) > HZ - 0.7) blocked[j * GW + i] = 1;
      else if (ax > HX - 0.35 && ax < HX + 0.65 && Math.abs(z) > DOOR + 0.1) blocked[j * GW + i] = 1;       // tường giữa văn phòng và phòng bên, chỉ chừa lối cửa
    }
    chanHinhChuNhat(0, 0, TL, TW, 0, 0.45);                       // bàn họp
  }
  // xếp lại nhân viên hai phòng thì xoá các ô bị bàn ghế phòng chiếm (không đụng văn phòng chính)
  function xoaChanPhong() {
    for (var i = 0; i < GW; i++) for (var j = 0; j < GH; j++) { var x = cx(i); if (Math.abs(x) > HX + 0.65 && Math.abs(x) <= GX - 0.7 && Math.abs(cz(j)) <= HZ - 0.7) blocked[j * GW + i] = 0; }
  }
  var tru_khongNguoi = false;
  function viaCua(sx, sz, gx, gz) {
    var sa = sx < -HX ? -1 : sx > HX ? 1 : 0, sb = gx < -HX ? -1 : gx > HX ? 1 : 0, r = [];
    if (sa !== sb) {
      if (sa) { r.push({ x: sa * (HX + 1.3), z: 0 }); r.push({ x: sa * (HX - 1.3), z: 0 }); }
      if (sb) { r.push({ x: sb * (HX - 1.3), z: 0 }); r.push({ x: sb * (HX + 1.3), z: 0 }); }
    }
    r.push({ x: gx, z: gz }); return r;
  }
  function trongTuong(x, z) { var ax = Math.abs(x); return ax > HX - 0.25 && ax < HX + 0.55 && Math.abs(z) > DOOR - 0.15; }
  function nhoNhat(a, b) { return a.f < b.f; }
  function timDuong(sx, sz, gx, gz, tru) {
    // ô tắc bởi vật tĩnh, hoặc bởi người đang ĐỨNG/NGỒI yên (trừ chính nó); vùng quanh điểm đầu/cuối được mở
    var occ = [];
    if (!tru_khongNguoi) banDo().forEach(function (o) { if (o !== tru && !o.walking && !(Math.abs(Math.abs(o.x) - HX) < 1.7 && Math.abs(o.z) < DOOR + 1.3)) occ.push(o); });
    function ok(i, j) {
      if (i < 0 || j < 0 || i >= GW || j >= GH) return false;
      var x = cx(i), z = cz(j);
      if (Math.hypot(x - sx, z - sz) < 0.62 || Math.hypot(x - gx, z - gz) < 0.62) return !trongTuong(x, z) && Math.abs(x) <= GX - 0.7 && Math.abs(z) <= HZ - 0.7 && !(Math.abs(x) <= TL / 2 + 0.3 && Math.abs(z) <= TW / 2 + 0.3);
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
    while (heap.length && guard++ < 30000) {
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
    if (!found) {
      if (occ.length && !tru_khongNguoi) { tru_khongNguoi = true; try { return timDuong(sx, sz, gx, gz, tru); } finally { tru_khongNguoi = false; } }
      return viaCua(sx, sz, gx, gz);                          // thật sự không có đường: đi qua cửa chứ không xuyên tường
    }
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
    var nhan = spriteTu(veNhan(ten, role, "#" + acc.getHexString(), nenNhan()), 1.55);
    nhan.position.set(0, 3.15 * s, 0); g.add(nhan);
    var noi = spriteTu(veNoi("…", "#" + acc.getHexString()), 2.1); noi.center.set(0.5, 0); noi.position.set(0, 3.55 * s, 0); noi.visible = false; g.add(noi);
    return { mat_mat: mat_mat, g: g, dau: dau_, tT: tT, tP: tP, chanT: chanT, chanP: chanP, than: than, matM: matM, nhan: nhan, noi: noi, acc: acc, s: s, vat: sach, but: but };
  }


  // ---------- người 3D có xương (Higgsfield + Meshy), dựng trong office3d: 10 nhân vật, 6 hoạt ảnh ----------
  var NV = null, NV_CLIPS = ["walk", "idle", "sit", "talk", "listen", "sitans"], nvDem = 0, HS = 1.3;
  var NV_DIR = "/static/office/", NV_V = "4", NV_TOTAL = 36;
  function napNguoi(can) {
    var nc = Math.max(10, Math.min(NV_TOTAL, can || 10));
    return import(NV_DIR + "gltf-addons.js?v=" + NV_V).then(function (m) {
      var L = new m.GLTFLoader();
      function tai(u) { return new Promise(function (ok, ko) { L.load(u + "?v=" + NV_V, ok, null, ko); }); }
      var ps = [], i;
      for (i = 0; i < nc; i++) ps.push(tai(NV_DIR + "c" + i + ".glb"));
      NV_CLIPS.forEach(function (n) { ps.push(tai(NV_DIR + "a_" + n + ".glb")); });
      return Promise.all(ps).then(function (r) {
        var clips = {}; NV_CLIPS.forEach(function (n, k) { clips[n] = r[nc + k].animations[0]; });
        r.slice(0, nc).forEach(function (g) { g.scene.traverse(function (o) { if (o.isMesh && o.material) { var ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach(function (m) { ['map', 'normalMap', 'roughnessMap', 'metalnessMap'].forEach(function (k) { if (m[k]) { m[k].anisotropy = 16; m[k].needsUpdate = true; } }); }); } }); });
        NV = { chars: r.slice(0, nc).map(function (g) { return g.scene; }), clips: clips, SU: m.SkeletonUtils, props: {}, sanGo: null }; return true;
      }).then(function () {
        // đồ dùng tạo bằng Higgsfield (ghế, bàn, cây, đèn, sàn gỗ): thiếu cái nào thì dùng hình dựng bằng code
        return Promise.all(["office_chair", "director_chair", "plant", "lamp", "desk", "bar", "coffee", "tea_tray", "cake", "water", "stand_table", "ac"].map(function (n) {
          return tai(NV_DIR + "props/" + n + ".glb").then(function (g) { g.scene.traverse(function (o) { if (o.isMesh && o.material) { (Array.isArray(o.material) ? o.material : [o.material]).forEach(function (m) { ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap'].forEach(function (k) { if (m[k]) { m[k].anisotropy = 16; m[k].needsUpdate = true; } }); }); } }); NV.props[n] = g.scene; }, function () {});
        })).then(function () {
          return new Promise(function (ok) { new T.TextureLoader().load(NV_DIR + "props/floor_wood.jpg?v=" + NV_V, function (tx) { tx.colorSpace = T.SRGBColorSpace; tx.wrapS = tx.wrapT = T.RepeatWrapping; tx.anisotropy = 16; NV.sanGo = tx; ok(); }, null, function () { ok(); }); });
        });
      }).then(function () { return true; });
    }).catch(function (e) { console.warn("[office] không nạp được người 3D, dùng robot", e); NV = null; return false; });
  }
  // đồ Higgsfield đã chuẩn hoá cao 1 (trục Y từ -0.5 đến 0.5): đặt chân chạm sàn, cao `cao`, quay `yaw`
  var PROP_YAW = { office_chair: Math.PI, director_chair: Math.PI, plant: 0, lamp: 0, desk: Math.PI / 2, bar: 0, coffee: 0, tea_tray: 0, cake: 0, water: 0, stand_table: 0, ac: 0 };
  function vatProp(ten, cao, sx) {
    var src = NV && NV.props && NV.props[ten]; if (!src) return null;
    var w = new T.Group(), c = NV.SU.clone(src); c.scale.setScalar(cao); c.position.y = 0.5 * cao; c.rotation.y = PROP_YAW[ten] || 0; w.add(c);
    c.traverse(function (o) { if (o.isMesh) { o.frustumCulled = false; } }); return w;
  }
  function sanGoMoi(rx, rz) { if (!NV || !NV.sanGo) return null; var t = NV.sanGo.clone(); t.needsUpdate = true; t.repeat.set(rx, rz); return t; }
  // lệch gốc của từng hoạt ảnh (cm, theo hông): clip ngồi giả định ghế nằm sau lưng, kéo về đúng chỗ ghế
  var GHE_LUI = -0.3;
  var NV_OFF = { sit: [-21.3, 67.4], sitans: [13.1, 35.2] };
  var _qi = null, _p0 = null, _p1 = null, _p2 = null, _q0 = null, _q1 = null, _v0 = null, _v1 = null;
  function dungNguoi3D(ten, role, hueV, laLead) {
    var acc = hsl(hueV, 0.75, 0.52), idx = laLead ? 0 : 1 + (nvDem++ % (NV.chars.length - 1));
    var g = new T.Group(), pivot = new T.Group(); g.add(pivot);
    var model = NV.SU.clone(NV.chars[idx]); pivot.add(model);
    model.traverse(function (o) { if (o.isSkinnedMesh) o.frustumCulled = false; });
    var B = {}; ["Hips", "Spine02", "Spine01", "Spine", "neck", "Head", "head_end", "LeftArm", "LeftForeArm", "LeftHand", "RightArm", "RightForeArm", "RightHand"].forEach(function (n) { B[n] = model.getObjectByName(n); });
    var hy = B.Hips.position.y || 100; var S = HS * (100.26 / hy), caoNguoi = 1.72 * S;
    pivot.scale.setScalar(S);
    model.updateMatrixWorld(true);
    var rest = {}, qm = new T.Quaternion(); model.getWorldQuaternion(qm); qm.invert();
    ["Spine02", "Spine01", "Spine", "neck", "Head"].forEach(function (n) { if (B[n]) rest[n] = B[n].getWorldQuaternion(new T.Quaternion()).premultiply(qm); });
    var mixer = new T.AnimationMixer(model), act = {}, wt = {};
    NV_CLIPS.forEach(function (n, k) { var ac = mixer.clipAction(NV.clips[n]); ac.play(); ac.setEffectiveWeight(0); ac.time = (k * 0.7 + Math.random() * 3) % 3; act[n] = ac; wt[n] = 0; });
    act.sit.time = 0; act.sit.paused = true;
    var than = new T.Mesh(new T.BoxGeometry(0.9, caoNguoi, 0.6), new T.MeshBasicMaterial({ visible: false })); than.position.y = caoNguoi / 2; g.add(than);
    var bong = new T.Mesh(new T.CircleGeometry(0.55, 20), new T.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.18, depthWrite: false }));
    bong.rotation.x = -Math.PI / 2; bong.position.y = 0.02; g.add(bong);
    if (laLead) { var vong = new T.Mesh(new T.TorusGeometry(0.6, 0.035, 8, 40), mat(0xffb020, { emissive: 0xffb020, emissiveIntensity: 0.8 })); vong.rotation.x = Math.PI / 2; vong.position.y = 0.05; g.add(vong); }
    // sách / máy tính bảng ở tay trái, bút ở tay phải (chỉ hiện khi đi họp); thang xương là cm nên nhân 100
    var gv = new T.Group(); gv.scale.setScalar(100 / 1); var sach = dungVat(hueV % 2, hsl(hueV, 0.5, 0.35).getHex()); sach.scale.setScalar(0.8);
    // trục tay (mô hình dạng chữ T): ngón = Y, pháp tuyến lòng bàn tay = (X+Z)/√2, ngón cái = (Z-X)/√2. Sách: bề ngang theo ngón cái, bề dày theo lòng bàn tay, chiều dài theo ngón; bàn tay nắm phần dưới cuốn sách
    (function () { var a = Math.SQRT1_2, m = new T.Matrix4().makeBasis(new T.Vector3(-a, 0, a), new T.Vector3(a, 0, a), new T.Vector3(0, 1, 0)); sach.quaternion.setFromRotationMatrix(m); sach.position.set(a * 0.055, 0.09, a * 0.055); })();
    gv.add(sach); gv.visible = false; B.LeftHand.add(gv);
    var datBan = dungVat(hueV % 2, hsl(hueV, 0.5, 0.35).getHex()); datBan.visible = false; g.add(datBan);
    var gb = new T.Group(); gb.scale.setScalar(100); var but = new T.Mesh(new T.CylinderGeometry(0.012, 0.012, 0.18, 6), mat(0x222222)); but.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), new T.Vector3(-Math.SQRT1_2, 0, Math.SQRT1_2)); but.position.set(0.012, 0.045, 0.03); gb.add(but); gb.visible = false; B.RightHand.add(gb);
    var nhan = spriteTu(veNhan(ten, role, "#" + acc.getHexString(), nenNhan()), 1.55); nhan.position.set(0, caoNguoi + 0.42, 0); g.add(nhan);
    var noi = spriteTu(veNoi("…", "#" + acc.getHexString()), 2.1); noi.center.set(0.5, 0); noi.position.set(0, caoNguoi + 0.72, 0); noi.visible = false; g.add(noi);
    return { hum: true, rest: rest, g: g, pivot: pivot, model: model, B: B, mixer: mixer, act: act, wt: wt, S: S, than: than, nhan: nhan, noi: noi, acc: acc, s: 0, vat: gv, but: gb, dat: datBan, ikw: 0, carry: 0, vatGoc: sach, idx: idx };
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
  // đặt xương về đúng hướng của dáng đứng thẳng ban đầu (đối với thân mô hình), cộng độ chúi `pitch` về trước, pha trộn `w`
  var _qa = null, _qb = null, _vx = null;
  function veRest(r, ten, pitch, w) {
    var b = r.B[ten], q0 = r.rest[ten]; if (!b || !q0 || w <= 0.001) return;
    if (!_qa) { _qa = new T.Quaternion(); _qb = new T.Quaternion(); _vx = new T.Vector3(1, 0, 0); }
    b.parent.updateWorldMatrix(true, false);
    r.model.getWorldQuaternion(_qa); _qb.setFromAxisAngle(_vx, pitch); _qa.multiply(_qb).multiply(q0);
    b.parent.getWorldQuaternion(_qb).invert(); _qb.multiply(_qa);
    if (w < 0.999) b.quaternion.slerp(_qb, w); else b.quaternion.copy(_qb);
    b.updateMatrixWorld(true);
  }
  // như nhamXuong nhưng chỉ pha trộn một phần `w` (giữ dáng gốc của hoạt ảnh phần còn lại)
  function nhamMem(bone, child, huong, w) {
    if (!bone || !child || w <= 0.001) return;
    var o = bone.quaternion.clone(); nhamXuong(bone, child, huong);
    if (w < 0.999) { bone.quaternion.copy(o).slerp(bone.quaternion.clone(), w); bone.updateMatrixWorld(true); }
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
    var B_ = r.B;
    if (!_p0) { _p0 = new T.Vector3(); _p1 = new T.Vector3(); _p2 = new T.Vector3(); _qi = new T.Quaternion(); _q0 = new T.Quaternion(); _q1 = new T.Quaternion(); _v0 = new T.Vector3(); _v1 = new T.Vector3(); }
    var ngoi = ngoiK > 0.5, mucTieu = {};
    if (a.walking) mucTieu.walk = 1;
    else if (ngoi) mucTieu.sit = 1;
    else mucTieu[dang === "talk" ? "talk" : (dang === "listen" ? "listen" : "idle")] = 1;
    var tong = 0, n, k = Math.min(1, dt * 7);
    for (n in r.act) { r.wt[n] += ((mucTieu[n] || 0) - r.wt[n]) * k; tong += r.wt[n]; }
    var ox = 0, oz = 0, hạ = 0;
    for (n in r.act) {
      var w = tong > 0 ? r.wt[n] / tong : 0; r.act[n].setEffectiveWeight(w);
      if (NV_OFF[n]) { ox += NV_OFF[n][0] * 0.01 * w; oz += NV_OFF[n][1] * 0.01 * w; }
      if (n === "sit" || n === "sitans") hạ += w;
    }
    r.act.walk.timeScale = 1.9 / (0.72 * r.S);
    r.mixer.update(dt);
    var sr0 = Math.sin(a.rot), cr0 = Math.cos(a.rot);
    r.pivot.position.set(ox * r.S, -hạ * (0.745 * r.S - 0.56 - 0.12 - (a.lead ? 0.08 : 0)), oz * r.S + (r.shz || 0) * (r.ikw || 0));
    r.model.updateMatrixWorld(true);
    var cuTa = dang === "talk", tayDat = ngoi && (dang === "type" || dang === "listen" || dang === "write" || dang === "fold" || cuTa);
    r.ikw += ((tayDat ? 1 : 0) - r.ikw) * Math.min(1, dt * 6);
    if (r.ikw < 0.05) r.shzT = 0;
    // thân giữ im: lưng, cổ, đầu bám đúng dáng đứng thẳng của mô hình (không theo cái ngả lưng của hoạt ảnh ngồi), hơi chồm khi gõ
    if (hạ > 0.02) {
      var wS = Math.min(1, hạ), ln = dang === "type" ? 0.05 : 0.02, thở = Math.sin(t * 1.5 + a.seed) * 0.006;
      veRest(r, "Spine02", ln + thở, wS); veRest(r, "Spine01", ln, wS); veRest(r, "Spine", ln, wS); veRest(r, "neck", 0.0, wS); veRest(r, "Head", 0.03, wS);
    } else { veRest(r, "neck", 0, a.walking ? 0.8 : 0.85); veRest(r, "Head", 0, a.walking ? 0.8 : 0.85); }
    if (r.ikw > 0.01) {
      var sr = Math.sin(a.rot), cr = Math.cos(a.rot), f = [sr, cr], lft = [cr, -sr], gõ = dang === "type", xaRef = gõ ? 0.86 : 0.8;
      var lead = !!a.lead, bien = 0, tocDo = 1, cao = gõ ? 0.895 : 0.9, xa = xaRef, ngang = 0.2;
      if (cuTa) { bien = lead ? 0.12 : 0.16; tocDo = lead ? 1.5 : 2.0; cao = 1.0; xa = 0.62; ngang = 0.3; }
      else if (dang === "listen" && lead) { bien = 0.03; tocDo = 0.9; cao = 0.93; xa = 0.7; }
      var cg = r.g.position, B = r.B, tb = null;
      if (a.kind === "seat" && a.seat) tb = Math.abs(a.seat.z) > 0.5 ? { x: a.seat.x, z: Math.sign(a.seat.z) * (TW / 2 - 0.3) } : { x: Math.sign(a.seat.x) * (TL / 2 - 0.62), z: 0 };
      if (tb && dang === "write") { if (Math.abs(a.seat.z) > 0.5) tb = { x: tb.x, z: tb.z - Math.sign(a.seat.z) * 0.14 }; else tb = { x: tb.x - Math.sign(a.seat.x) * 0.14, z: 0 }; }
      // dịch cả thân về phía bàn một lần lúc vào ghế để khuỷu tay co (không cho tay duỗi thẳng); sau đó khoá, không trườn tới lui nữa
      if (r.ikw > 0.5 && (r.shzT || 0) < 1.0) {
        r.shzT = (r.shzT || 0) + dt;
        var mx = (B.LeftArm.getWorldPosition(_p0).x + B.RightArm.getWorldPosition(_p1).x) / 2, mz = (_p0.z + _p1.z) / 2;
        B.LeftForeArm.getWorldPosition(_p1); B.LeftHand.getWorldPosition(_p2); B.LeftArm.getWorldPosition(_p0);
        var armL = _p0.distanceTo(_p1) + _p1.distanceTo(_p2), dd_ = (cg.x + f[0] * xaRef - mx) * f[0] + (cg.z + f[1] * xaRef - mz) * f[1];
        r.shz = cl((r.shz || 0) + (dd_ - armL * 0.62) * Math.min(1, dt * 5), -0.1, 0.05);
      }
      var bs = 0.5 + 0.5 * Math.sin(t * 17 + a.seed), bs2 = 0.5 + 0.5 * Math.sin(t * 13 + a.seed * 2.3);
      [[1, B.LeftArm, B.LeftForeArm, B.LeftHand, bs], [-1, B.RightArm, B.RightForeArm, B.RightHand, bs2]].forEach(function (h) {
        var sd = h[0], j = gõ ? 0.022 * h[4] : bien * Math.sin(t * tocDo + (sd > 0 ? 0 : 2.4) + a.seed), ngH = ngang, bx = cg.x + f[0] * xa, bz = cg.z + f[1] * xa;
        if (tb) { bx = tb.x; bz = tb.z; ngH = 0.22; if (dang === "write") { ngH = sd > 0 ? 0.3 : 0.1 + 0.05 * Math.sin(t * 6 + a.seed); j = sd < 0 ? 0.012 * Math.sin(t * 9 + a.seed) : 0; } else if (dang === "fold") ngH = sd > 0 ? -0.14 : 0.14; }
        var tg = new T.Vector3(bx + lft[0] * sd * ngH, cao + j, bz + lft[1] * sd * ngH);
        var cuc = new T.Vector3(lft[0] * sd * 0.6, -0.8, lft[1] * sd * 0.6);
        ikTay(h[1], h[2], h[3], tg, cuc, r.ikw);
        if (r.ikw > 0.01) { h[3].rotateY(-sd * 1.3 * r.ikw); h[3].updateMatrixWorld(true); }
      });
    }
    // ---- tư thế đứng: khoanh tay, chỉ tay, đưa tay lên miệng (uống nước, ăn bánh) ----
    var pzDang = (!a.walking && ((!ngoi && ["cross", "drink", "point", "back", "hip", "chin"].indexOf(dang) >= 0) || (ngoi && (dang === "cross" || dang === "chin")))) ? dang : null;
    if (pzDang) r.pzk = pzDang;
    r.pzw = (r.pzw || 0) + ((pzDang ? 1 : 0) - (r.pzw || 0)) * Math.min(1, dt * 5);
    if (r.pzw > 0.02 && r.pzk) {
      var Bq = r.B, sL = Bq.LeftArm.getWorldPosition(new T.Vector3()), sR = Bq.RightArm.getWorldPosition(new T.Vector3());
      Bq.LeftForeArm.getWorldPosition(_p1); Bq.LeftHand.getWorldPosition(_p2);
      var Lr = sL.distanceTo(_p1) + _p1.distanceTo(_p2), WW = r.pzw, UPv = new T.Vector3(0, 1, 0);
      var fw = new T.Vector3(Math.sin(a.rot), 0, Math.cos(a.rot)), lf = new T.Vector3(Math.cos(a.rot), 0, -Math.sin(a.rot));
      var cucL = lf.clone().multiplyScalar(0.6).add(new T.Vector3(0, -0.8, 0)), cucR = lf.clone().multiplyScalar(-0.6).add(new T.Vector3(0, -0.8, 0)), tg;
      if (r.pzk === "cross") {
        tg = sL.clone().addScaledVector(lf, -0.5 * Lr).addScaledVector(fw, 0.38 * Lr).addScaledVector(UPv, -0.5 * Lr); ikTay(Bq.LeftArm, Bq.LeftForeArm, Bq.LeftHand, tg, cucL, WW);
        tg = sR.clone().addScaledVector(lf, 0.5 * Lr).addScaledVector(fw, 0.46 * Lr).addScaledVector(UPv, -0.46 * Lr); ikTay(Bq.RightArm, Bq.RightForeArm, Bq.RightHand, tg, cucR, WW);
      } else if (r.pzk === "back") {
        var hq = Bq.Hips.getWorldPosition(new T.Vector3()), cb = new T.Vector3(0, -0.5, 0).addScaledVector(fw, -0.6);
        tg = hq.clone().addScaledVector(lf, 0.17 * Lr).addScaledVector(fw, -0.14 * Lr).addScaledVector(UPv, 0.06 * Lr); ikTay(Bq.LeftArm, Bq.LeftForeArm, Bq.LeftHand, tg, cb.clone().addScaledVector(lf, 0.5), WW);
        tg = hq.clone().addScaledVector(lf, -0.17 * Lr).addScaledVector(fw, -0.14 * Lr).addScaledVector(UPv, 0.06 * Lr); ikTay(Bq.RightArm, Bq.RightForeArm, Bq.RightHand, tg, cb.clone().addScaledVector(lf, -0.5), WW);
      } else if (r.pzk === "hip") {
        var hq2 = Bq.Hips.getWorldPosition(new T.Vector3()), sw = Math.sin(t * 0.8 + a.seed) * 0.02 * Lr;
        tg = hq2.clone().addScaledVector(lf, 0.4 * Lr).addScaledVector(UPv, 0.14 * Lr + sw); ikTay(Bq.LeftArm, Bq.LeftForeArm, Bq.LeftHand, tg, new T.Vector3(lf.x * 0.9, -0.2, lf.z * 0.9), WW);
        tg = hq2.clone().addScaledVector(lf, -0.4 * Lr).addScaledVector(UPv, 0.14 * Lr - sw); ikTay(Bq.RightArm, Bq.RightForeArm, Bq.RightHand, tg, new T.Vector3(-lf.x * 0.9, -0.2, -lf.z * 0.9), WW);
      } else if (r.pzk === "chin") {
        var hc = Bq.Head.getWorldPosition(new T.Vector3()), nod = Math.sin(t * 0.7 + a.seed) * 0.02 * Lr;
        tg = sL.clone().addScaledVector(lf, -0.5 * Lr).addScaledVector(fw, 0.4 * Lr).addScaledVector(UPv, -0.5 * Lr); ikTay(Bq.LeftArm, Bq.LeftForeArm, Bq.LeftHand, tg, cucL, WW);
        tg = hc.clone().addScaledVector(fw, 0.3 * Lr).addScaledVector(UPv, -0.2 * Lr + nod); ikTay(Bq.RightArm, Bq.RightForeArm, Bq.RightHand, tg, cucR, WW);
      } else if (r.pzk === "drink") {
        var hp = Bq.Head.getWorldPosition(new T.Vector3()), sip = 0.5 + 0.5 * Math.sin(t * 0.9 + a.seed);
        tg = hp.clone().addScaledVector(fw, (0.36 - 0.08 * sip) * Lr).addScaledVector(UPv, (-0.16 + 0.12 * sip) * Lr).addScaledVector(lf, 0.02 * Lr); ikTay(Bq.RightArm, Bq.RightForeArm, Bq.RightHand, tg, cucR, WW);
      } else {
        var dir = a.diemPt ? a.diemPt.clone().sub(sR).normalize() : fw.clone();
        tg = sR.clone().addScaledVector(dir, 0.97 * Lr).addScaledVector(UPv, 0.03 * Math.sin(t * 2.2 + a.seed) * Lr); ikTay(Bq.RightArm, Bq.RightForeArm, Bq.RightHand, tg, cucR, WW);
      }
      if (a.item) {
        if (!r.cup) {
          r.cup = new T.Group(); var cm = new T.Mesh(new T.CylinderGeometry(0.07, 0.055, 0.15, 14), mat(0xffffff, { roughness: 0.4 })); cm.position.y = 0.075; r.cup.add(cm);
          var ct = new T.Mesh(new T.CylinderGeometry(0.063, 0.063, 0.01, 14), mat(0x3a2412)); ct.position.y = 0.148; r.cup.add(ct);
          var bn = new T.Mesh(new T.CylinderGeometry(0.075, 0.075, 0.03, 14), mat(0xd9a45c, { roughness: 0.8 })); bn.position.y = 0.05; bn.visible = false; r.cup.add(bn); r.cup.userData = { c: cm, t: ct, b: bn }; r.g.add(r.cup);
        }
        var ud = r.cup.userData, ban_ = a.item === "banh"; ud.c.visible = !ban_; ud.t.visible = !ban_; ud.b.visible = ban_;
        if (!ban_) { ud.c.material.color.setHex(a.item === "cafe" ? 0xf5ecdf : 0xffffff); ud.t.material.color.setHex(a.item === "cafe" ? 0x2a160a : 0x7fc4ff); }
        var hw = Bq.RightHand.getWorldPosition(new T.Vector3()); r.g.worldToLocal(hw); r.cup.position.copy(hw).add(new T.Vector3(0, -0.03, 0)); r.cup.visible = true;
      } else if (r.cup) r.cup.visible = false;
    } else if (r.cup) r.cup.visible = false;
    // cầm sách: tay trái đỡ sách trên lòng bàn tay ngửa, trước ngực (hoặc đặt trên mặt bàn khi ngồi), không để tay xuyên sách
    // sổ và máy tính bảng chỉ cầm lên tay khi đứng phát biểu; ngồi thì đặt trên mặt bàn, đi bộ thì không mang (hai tay đánh tự nhiên)
    var cam_ = !!a.book && !a.walking && a.dd > 0.6 && dang === "talk";
    r.carry += ((cam_ ? 1 : 0) - r.carry) * Math.min(1, dt * 6);
    r.vat.visible = r.but.visible = r.carry > 0.05;
    if (r.dat) {
      var tbq = a.kind === "seat" && a.seat ? (Math.abs(a.seat.z) > 0.5 ? { x: a.seat.x, z: Math.sign(a.seat.z) * (TW / 2 - 0.3) } : { x: Math.sign(a.seat.x) * (TL / 2 - 0.62), z: 0 }) : null;
      r.dat.visible = !!a.book && !!tbq && !a.walking && ngoiK > 0.5 && r.carry < 0.05;
      if (r.dat.visible) { var ddx = tbq.x - r.g.position.x, ddz = tbq.z - r.g.position.z, cr_ = Math.cos(a.rot), sr_ = Math.sin(a.rot), lat = a.lead ? 0.6 : -0.02; r.dat.position.set(ddx * cr_ - ddz * sr_ + lat, 0.9, ddx * sr_ + ddz * cr_ - 0.02); }
    }
    if (r.carry > 0.01) {
      var sc = Math.sin(a.rot), cc = Math.cos(a.rot), cg2 = r.g.position, hy = r.B.Hips.getWorldPosition(_p0).y;
      var tgc = ngoi ? new T.Vector3(cg2.x + sc * 0.62 + cc * 0.22, 0.95, cg2.z + cc * 0.62 - sc * 0.22) : new T.Vector3(cg2.x + sc * 0.5 + cc * 0.16, hy + 0.32, cg2.z + cc * 0.5 - sc * 0.16);
      ikTay(r.B.LeftArm, r.B.LeftForeArm, r.B.LeftHand, tgc, new T.Vector3(cc * 0.6, -0.8, -sc * 0.6), r.carry);
      r.B.LeftHand.rotateY((Math.PI - 1.3) * r.carry); r.B.LeftHand.updateMatrixWorld(true);
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
  function xuongDong(g, text, x, y, maxW, lh, maxLines) {
    var words = String(text).split(/\s+/), line = "", n = 0;
    for (var i = 0; i < words.length; i++) {
      var t = line ? line + " " + words[i] : words[i];
      if (g.measureText(t).width > maxW && line) { g.fillText(line, x, y + n * lh); n++; line = words[i]; if (n >= maxLines) return n; } else line = t;
    }
    if (line && n < maxLines) { g.fillText(line, x, y + n * lh); n++; }
    return n;
  }
  function veBangDieuHanh() {
    var c = document.createElement("canvas"), W = 1400, H = 560; c.width = W; c.height = H; var g = c.getContext("2d"), light = sang();
    var ink = light ? "#12233f" : "#e8f0ff", mute = light ? "#5a6b86" : "#9fb4d8", card = light ? "#ffffff" : "#13264a", F = "system-ui,Segoe UI,Roboto,sans-serif";
    g.fillStyle = light ? "#f3f7ff" : "#0c1830"; rr(g, 4, 4, W - 8, H - 8, 28); g.fill(); g.strokeStyle = "#2a6bff"; g.lineWidth = 6; rr(g, 4, 4, W - 8, H - 8, 28); g.stroke();
    var d = kpiDuLieu || {}, ten = d.company || brain() || "Công ty";
    g.textBaseline = "middle"; g.textAlign = "left"; g.fillStyle = ink; g.font = "800 46px " + F; g.fillText(cat(ten, 28), 44, 54);
    g.font = "600 22px " + F; g.fillStyle = "#2a6bff"; g.fillText("BẢNG ĐIỀU HÀNH", 44, 96);
    g.font = "500 24px " + F; g.fillStyle = mute; g.textAlign = "right";
    g.fillText(cat(kpiDuLieu ? (d.updated ? "Cập nhật: " + d.updated : "Số liệu thật của brain") : "Đang tải số liệu…", 50), W - 44, 54); g.textAlign = "left";
    var ks = d.kpis || [];
    if (!ks.length) {
      g.fillStyle = mute; g.font = "600 30px " + F; g.fillText(kpiDuLieu ? "Chưa có số liệu thật cho brain này." : "Đang lấy số liệu…", 44, 200);
      g.font = "500 24px " + F; g.fillText("Thêm file 00 - Dashboard/minmin-dashboard.json (kpis, company, plan, targets, proposals).", 44, 250);
      return c;
    }
    var cols = 4, tw = 316, th = 118, gap = 24;
    ks.slice(0, 4).forEach(function (k, i) {
      var x = 44 + i * (tw + gap), y = 120;
      g.fillStyle = card; rr(g, x, y, tw, th, 18); g.fill();
      var tone = k.tone === "up" ? "#1fb86a" : k.tone === "down" ? "#e5484d" : k.tone === "warn" ? "#f5a623" : "#6fa8ff";
      g.fillStyle = tone; g.fillRect(x, y + 16, 6, th - 32);
      g.fillStyle = mute; g.font = "500 22px " + F; g.fillText(cat(k.label, 24), x + 22, y + 28);
      g.fillStyle = ink; g.font = "800 44px " + F; g.fillText(cat(String(k.value) + (k.unit ? " " + k.unit : ""), 13), x + 22, y + 70);
      if (k.delta) { g.fillStyle = tone; g.font = "600 20px " + F; g.fillText(cat(k.delta, 26), x + 22, y + 102); }
    });
    // cột trái: kế hoạch + chỉ tiêu; cột phải: đề xuất + cần chú ý
    var y0 = 266, LX = 44, RX = 724, CW = 632;
    g.fillStyle = card; rr(g, LX, y0, CW, 270, 18); g.fill(); rr(g, RX, y0, CW, 270, 18); g.fill();
    g.fillStyle = "#2a6bff"; g.font = "700 24px " + F; g.fillText("KẾ HOẠCH VÀ CHỈ TIÊU", LX + 22, y0 + 30); g.fillText("ĐỀ XUẤT", RX + 22, y0 + 30);
    var y = y0 + 62, i;
    g.font = "500 22px " + F; g.fillStyle = ink;
    (d.plan || []).slice(0, 2).forEach(function (t) { var n = xuongDong(g, "\u2022 " + t, LX + 22, y, CW - 44, 26, 2); y += n * 26 + 4; });
    var ts = d.targets || [], rowH = ts.length > 2 ? 48 : 56;
    ts.slice(0, 3).forEach(function (t) {
      var ym = Math.max(y, y0 + 62) + 12; y = ym + rowH;
      g.fillStyle = ink; g.font = "600 21px " + F; g.fillText(cat(t.label, 26), LX + 22, ym);
      g.textAlign = "right"; g.fillStyle = mute; g.font = "500 20px " + F; g.fillText(cat(t.current + " / " + t.target, 34), LX + CW - 22, ym); g.textAlign = "left";
      var bw = CW - 44 - 80, p = Math.max(0, Math.min(100, t.pct));
      g.fillStyle = light ? "#e3eaf6" : "#1e3560"; rr(g, LX + 22, ym + 16, bw, 14, 7); g.fill();
      g.fillStyle = t.pct >= 100 ? "#1fb86a" : t.pct >= 60 ? "#2a6bff" : "#f5a623"; if (p > 0) { rr(g, LX + 22, ym + 16, Math.max(14, bw * p / 100), 14, 7); g.fill(); }
      g.fillStyle = ink; g.font = "700 22px " + F; g.textAlign = "right"; g.fillText(t.pct + "%", LX + CW - 22, ym + 24); g.textAlign = "left";
    });
    if (!(d.plan || []).length && !ts.length) { g.fillStyle = mute; g.font = "500 22px " + F; g.fillText("Chưa có kế hoạch và chỉ tiêu.", LX + 22, y0 + 70); g.fillText("Thêm plan và targets vào file dashboard.", LX + 22, y0 + 100); }
    y = y0 + 62; g.fillStyle = ink; g.font = "500 22px " + F;
    var pr = d.proposals || [];
    pr.slice(0, 3).forEach(function (t) { var n = xuongDong(g, "\u2022 " + t, RX + 22, y, CW - 44, 26, 2); y += n * 26 + 8; });
    if (!pr.length) { g.fillStyle = mute; g.fillText("Chưa có đề xuất nào.", RX + 22, y); y += 34; }
    (d.alerts || []).slice(0, 2).forEach(function (a) { if (y > y0 + 238) return; g.fillStyle = a.level === "critical" || a.level === "serious" ? "#e5484d" : a.level === "warning" ? "#f5a623" : "#1fb86a"; g.font = "600 20px " + F; g.fillText("\u25cf " + cat(a.text, 56), RX + 22, y + 6); y += 32; });
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
  function ghe(x, z, rot, laStool, laGD) {
    var g = new T.Group(); g.position.set(x, 0, z); g.rotation.y = rot;
    var vc = vatProp(laGD ? "director_chair" : "office_chair", laGD ? 1.3 : 1.12);
    if (vc) { g.add(vc); scene.add(g); return g; }
    var m = mat(sang() ? 0x93a4bd : 0x3a4c6c);
    var seat = laStool ? new T.Mesh(new T.CylinderGeometry(0.42, 0.42, 0.1, 18), m) : new T.Mesh(new T.BoxGeometry(0.95, 0.1, 0.95), m); seat.position.y = 0.4; g.add(seat);
    if (!laStool) { var lung = new T.Mesh(new T.BoxGeometry(0.95, 0.7, 0.1), m); lung.position.set(0, 0.85, -0.5); g.add(lung); }
    var tru = new T.Mesh(new T.CylinderGeometry(0.07, 0.07, 0.5, 8), mat(0x6f7f98)); tru.position.y = 0.2; g.add(tru);
    var de = new T.Mesh(new T.CylinderGeometry(0.4, 0.4, 0.05, 14), mat(0x6f7f98)); de.position.y = 0.03; g.add(de);
    scene.add(g); return g;
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
  function chaiNuoc(x, y, z) {
    var g = new T.Group(); g.position.set(x, y, z);
    var th = new T.Mesh(new T.CylinderGeometry(0.05, 0.05, 0.24, 14), new T.MeshStandardMaterial({ color: 0x9fd8ff, transparent: true, opacity: 0.55, roughness: 0.1, metalness: 0.1 })); th.position.y = 0.12; g.add(th);
    var nuoc = new T.Mesh(new T.CylinderGeometry(0.044, 0.044, 0.16, 14), new T.MeshStandardMaterial({ color: 0x5fb6ff, transparent: true, opacity: 0.6, roughness: 0.05 })); nuoc.position.y = 0.09; g.add(nuoc);
    var co = new T.Mesh(new T.CylinderGeometry(0.02, 0.03, 0.05, 12), mat(0x2a6bff)); co.position.y = 0.27; g.add(co);
    var nap = new T.Mesh(new T.CylinderGeometry(0.024, 0.024, 0.025, 12), mat(0x1a3fa0)); nap.position.y = 0.31; g.add(nap);
    return g;
  }
  function coc(x, y, z, kieu) {
    var g = new T.Group(); g.position.set(x, y, z);
    var mau = [0xffffff, 0xffe0b8, 0xbfe3ff][kieu % 3];
    var th = new T.Mesh(new T.CylinderGeometry(0.058, 0.045, 0.11, 16), mat(mau, { roughness: 0.4 })); th.position.y = 0.055; g.add(th);
    var tra = new T.Mesh(new T.CylinderGeometry(0.05, 0.05, 0.006, 16), mat(kieu === 1 ? 0x4a2c14 : 0x3a2412)); tra.position.y = 0.1; g.add(tra);
    var tay = new T.Mesh(new T.TorusGeometry(0.03, 0.008, 8, 14, Math.PI), mat(mau, { roughness: 0.4 })); tay.rotation.z = -Math.PI / 2; tay.position.set(0.066, 0.055, 0); g.add(tay);
    return g;
  }
  function dungBan(slot, a, idx) {
    var g = new T.Group(); g.position.set(slot.desk.x, NV ? -0.2 : 0, slot.desk.z); g.rotation.y = slot.desk.rot;
    var bk = vatProp("desk", 1);
    if (bk) { var cb = bk.children[0]; cb.scale.set(2.6, 1.83, 2.6); cb.position.y = 0.29 * 1.83; g.add(bk); }
    else {
      var mt = new T.Mesh(new T.BoxGeometry(2.6, 0.12, 1.3), mat(sang() ? 0xdfe6f2 : 0x2a3a58)); mt.position.set(0, 1.0, 0); g.add(mt);
      [[-1.2, -0.55], [1.2, -0.55], [-1.2, 0.55], [1.2, 0.55]].forEach(function (p) { var ch = new T.Mesh(new T.BoxGeometry(0.1, 1.0, 0.1), mat(0x8fa0b8)); ch.position.set(p[0], 0.5, p[1]); g.add(ch); });
    }
    var vien = new T.Mesh(new T.BoxGeometry(1.2, 0.76, 0.06), mat(0x0f1626)); vien.position.set(0, 1.66, -0.38); g.add(vien);
    var man = new T.Mesh(new T.PlaneGeometry(1.1, 0.66), matManOff); man.position.set(0, 1.66, -0.345); g.add(man); a.screen = man; a.screenIdx = idx % 4;
    var de = new T.Mesh(new T.BoxGeometry(0.1, 0.35, 0.1), mat(0x8fa0b8)); de.position.set(0, 1.22, -0.38); g.add(de);
    var bp = new T.Mesh(new T.BoxGeometry(0.85, 0.03, 0.3), mat(0x2b3550)); bp.position.set(0, 1.075, NV ? 0.45 : 0.15); g.add(bp);       // bàn phím
    for (var r = 0; r < 3; r++) { var hang = new T.Mesh(new T.BoxGeometry(0.78, 0.012, 0.055), mat(0x8fa0b8)); hang.position.set(0, 1.095, (NV ? 0.36 : 0.06) + r * 0.085); g.add(hang); }
    var ch = new T.Mesh(new T.SphereGeometry(0.07, 10, 8), mat(0x2b3550)); ch.scale.set(0.8, 0.5, 1.2); ch.position.set(0.62, 1.085, NV ? 0.45 : 0.15); g.add(ch);   // chuột
    g.add(chaiNuoc(-1.05, 1.06, 0.12)); g.add(coc(-0.8, 1.06, 0.3, idx % 3)); if (idx % 2) g.add(coc(1.08, 1.06, -0.15, 1));
    scene.add(g);
    var gk = NV ? GHE_LUI : 0; ghe(slot.stand.x + Math.sign(slot.desk.x - slot.stand.x) * gk, slot.stand.z + Math.sign(slot.desk.z - slot.stand.z) * gk, slot.rot, false);
    var w = slot.desk.rot;
    chanHinhChuNhat(slot.desk.x, slot.desk.z, w === Math.PI / 2 ? 1.3 : 2.6, w === Math.PI / 2 ? 2.6 : 1.3, 0, 0.45);
    chanTron(slot.stand.x, slot.stand.z, 0.5); chanTron(slot.stand.x + Math.sign(slot.desk.x - slot.stand.x) * gk, slot.stand.z + Math.sign(slot.desk.z - slot.stand.z) * gk, 0.55);
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
    var lap = new T.Group(); lap.position.set(TL / 2 - 0.55, 1.07, 0); lap.rotation.y = Math.PI / 2; g.add(lap);
    var dayL = new T.Mesh(new T.BoxGeometry(0.62, 0.035, 0.42), mat(0x9aa8c0)); dayL.position.y = 0.02; lap.add(dayL);
    var bpL = new T.Mesh(new T.BoxGeometry(0.5, 0.012, 0.2), mat(0x1c2538)); bpL.position.set(0, 0.043, 0.06); lap.add(bpL);
    var banhL = new T.Mesh(new T.BoxGeometry(0.16, 0.008, 0.1), mat(0x6d7b95)); banhL.position.set(0, 0.043, 0.16); lap.add(banhL);
    var le = new T.Group(); le.position.set(0, 0.04, -0.2); le.rotation.x = -0.3; lap.add(le);
    var vo = new T.Mesh(new T.BoxGeometry(0.62, 0.4, 0.025), mat(0x9aa8c0)); vo.position.y = 0.2; le.add(vo);
    var manL = new T.Mesh(new T.PlaneGeometry(0.56, 0.34), matManOn.length ? matManOn[0] : matManOff); manL.position.set(0, 0.2, 0.0135); le.add(manL);
    for (var ci = 0; ci < 7; ci++) { var cxm = -4.7 + ci * 1.35, sg = ci % 2 ? 1 : -1; if (ci % 2 === 0) { var cb = chaiNuoc(cxm, 1.07, sg * 0.3); g.add(cb); } else { var cc = coc(cxm, 1.07, sg * 0.3, ci % 3); g.add(cc); } }
    scene.add(g);
    var tham = new T.Mesh(new T.PlaneGeometry(TL + 3.5, TW + 5), new T.MeshBasicMaterial({ color: sang() ? 0xdbe6f7 : 0x1c2c4a })); tham.rotation.x = -Math.PI / 2; tham.position.y = 0.02; scene.add(tham); canhSan.push(tham);
    // ghế: đầu bàn bên phải là giám đốc; người khác ngồi hai bên, từ gần giám đốc ra xa, cuối cùng ghế cuối bàn
    var gs = [{ x: TL / 2 + 0.55, z: 0, kind: "seat", rot: -Math.PI / 2 }];
    for (var i = 7; i >= 0; i--) { var x = -4.55 + 1.3 * i; gs.push({ x: x, z: -1.8, kind: "seat", rot: 0 }); gs.push({ x: x, z: 1.8, kind: "seat", rot: Math.PI }); }
    gs.push({ x: -TL / 2 - 0.85, z: 0, kind: "seat", rot: Math.PI / 2 });
    gs.forEach(function (s, gi_) { s.chair = ghe(s.x, s.z, s.rot, true, gi_ === 0); chanTron(s.x, s.z, 0.52); s.by = null; s.cp = 0; s.ct = 0; s.ox = -Math.sin(s.rot); s.oz = -Math.cos(s.rot); s.sx = s.x + s.ox * 1.15; s.sz = s.z + s.oz * 1.15; });
    return { ghe: gs, holo: holo };
  }
  var anh = { lamps: [], tran: [], pool: [], hemi: null, dl: null };
  function den(x, z, hex) {
    var g = new T.Group(); g.position.set(x, 0, z);
    var vl = vatProp("lamp", 2.9);
    if (vl) g.add(vl); else {
    var tru = new T.Mesh(new T.CylinderGeometry(0.05, 0.05, 2.6, 8), mat(0x6f7f98)); tru.position.y = 1.3; g.add(tru);
    var de = new T.Mesh(new T.CylinderGeometry(0.3, 0.3, 0.06, 14), mat(0x6f7f98)); de.position.y = 0.03; g.add(de);
    var chup = new T.Mesh(new T.CylinderGeometry(0.28, 0.4, 0.5, 14), new T.MeshBasicMaterial({ color: hex })); chup.position.y = 2.7; g.add(chup); }
    var pl = new T.PointLight(hex, 0.9, 20, 1.6); pl.position.y = 2.6; g.add(pl); anh.lamps.push({ l: pl, b: 0.9 });
    scene.add(g); chanTron(x, z, 0.4);
  }
  // ---------- biệt thự: phòng Sale (trái) và phòng Marketing (phải), nhân viên theo Pancake POS ----------
  var PHONG = [
    { id: "sale", ten: "Phòng Sale", cx: -(14.5 + RW / 2), mau: 0xfff0dc, mauToi: 0x3a2c1c, acc: "#f5a623", vaiTro: "Nhân viên bán hàng" },
    { id: "marketing", ten: "Phòng Marketing", cx: 14.5 + RW / 2, mau: 0xf0e6ff, mauToi: 0x2c1f46, acc: "#9b6bff", vaiTro: "Nhân viên marketing" }
  ];
  var nvPhong = [], vatPhong = [], bangPhong = {}, pancakeDL = null, pancakeSig = "";
  function tien(v) { v = Number(v) || 0; var a = Math.abs(v); function f(x, n) { return x.toFixed(n).replace(".", ",").replace(/,0+$/, "").replace(/(,\d*?)0+$/, "$1"); } if (a >= 1e9) return f(v / 1e9, 2) + " tỷ"; if (a >= 1e6) return f(v / 1e6, 1) + " tr"; if (a >= 1e3) return f(v / 1e3, 0) + "k"; return String(Math.round(v)); }
  function veSanGo(light) {
    var c = document.createElement("canvas"), W = 512; c.width = W; c.height = W; var g = c.getContext("2d");
    var base = light ? [196, 150, 98] : [92, 66, 44], n = 8, h = W / n;
    for (var i = 0; i < n; i++) {
      var k = (Math.sin(i * 12.9898) * 43758.5453) % 1, d = Math.round((k - Math.floor(k) - 0.5) * 36);
      g.fillStyle = "rgb(" + (base[0] + d) + "," + (base[1] + d) + "," + (base[2] + d) + ")"; g.fillRect(0, i * h, W, h - 2);
      g.fillStyle = "rgba(0,0,0,0.18)"; g.fillRect(0, i * h + h - 2, W, 2);
      g.fillStyle = "rgba(0,0,0,0.1)"; g.fillRect(((i * 173) % W), i * h, 2, h - 2);
      for (var j = 0; j < 14; j++) { var kk = (Math.sin((i * 31 + j) * 78.233) * 12345.6789) % 1; kk = kk - Math.floor(kk); g.fillStyle = "rgba(60,30,10," + (0.05 + kk * 0.07) + ")"; g.fillRect(kk * W, i * h + 6 + (j % 4) * 8, 60 + kk * 90, 1.5); }
    }
    var tx = new T.CanvasTexture(c); tx.colorSpace = T.SRGBColorSpace; tx.wrapS = tx.wrapT = T.RepeatWrapping; tx.anisotropy = 4; return tx;
  }
  function caySan(x, z, cao) {
    var g = new T.Group(); g.position.set(x, 0, z);
    var vp = vatProp("plant", 1.35 + cao * 0.35); if (vp) { vp.rotation.y = x * 1.7; g.add(vp); scene.add(g); return g; }
    var chau = new T.Mesh(new T.CylinderGeometry(0.34, 0.26, 0.55, 16), mat(0xe9e4da, { roughness: 0.8 })); chau.position.y = 0.275; g.add(chau);
    var dat = new T.Mesh(new T.CylinderGeometry(0.31, 0.31, 0.04, 16), mat(0x3a2a1c)); dat.position.y = 0.55; g.add(dat);
    var xanh = [0x2f8f4e, 0x3aa65d, 0x277a43];
    for (var i = 0; i < 9; i++) {
      var ang = i * 2.4, rr_ = 0.12 + (i % 3) * 0.08, h = 0.55 + (i % 4) * 0.12 * cao;
      var la = new T.Mesh(new T.SphereGeometry(0.2 + (i % 3) * 0.05, 10, 8), mat(xanh[i % 3], { roughness: 0.7 }));
      la.scale.set(1, 1.5, 0.7); la.position.set(Math.cos(ang) * rr_, 0.55 + h, Math.sin(ang) * rr_); la.rotation.y = ang; la.rotation.z = Math.cos(ang) * 0.35; g.add(la);
    }
    scene.add(g); return g;
  }
  // mỗi phòng có 2 bảng: HÔM QUA (số đã chốt) và HÔM NAY (số tươi). kieu = "qua" | "nay".
  // Marketing xếp theo ĐƠN THÁNG: tổng đơn tính lương của các mã người đó phụ trách (không phải đơn marketing tự chốt)
  function nhin(r, kieu) {
    if (kieu !== "qua") return r;
    var y = r.y || {}; return { name: r.name, dept: r.dept, orders: y.orders || 0, revenue: y.revenue || 0, spend: y.spend || 0, roas: y.roas || 0, packed: y.packed || 0, month_orders: y.month_orders != null ? y.month_orders : r.month_orders };
  }
  function homQua() { var d = new Date(Date.now() - 864e5); return ("0" + d.getDate()).slice(-2) + "/" + ("0" + (d.getMonth() + 1)).slice(-2); }
  function veBangPhong(ph, kieu) {
    var c = document.createElement("canvas"), W = 1120, H = 560; c.width = W; c.height = H; var g = c.getContext("2d"), light = sang(), F = "system-ui,Segoe UI,Roboto,sans-serif", qua = kieu === "qua", mk = ph.id === "marketing";
    var ink = light ? "#12233f" : "#e8f0ff", mute = light ? "#5a6b86" : "#9fb4d8", card = light ? "#ffffff" : "#13264a";
    g.fillStyle = light ? "#f3f7ff" : "#0c1830"; rr(g, 4, 4, W - 8, H - 8, 28); g.fill(); g.strokeStyle = qua ? "#8a97ad" : ph.acc; g.lineWidth = 6; rr(g, 4, 4, W - 8, H - 8, 28); g.stroke();
    g.textBaseline = "middle"; g.textAlign = "left"; g.fillStyle = ink; g.font = "800 40px " + F; g.fillText(ph.ten.toUpperCase(), 40, 48);
    g.fillStyle = qua ? "#8a97ad" : "#1fb86a"; g.font = "800 24px " + F;
    if (!qua) { g.beginPath(); g.arc(48, 92, 8, 0, 6.3); g.fill(); g.fillText("HÔM NAY · TRỰC TIẾP", 66, 92); } else g.fillText("HÔM QUA · " + homQua(), 40, 92);
    var d = pancakeDL; g.textAlign = "right"; g.fillStyle = mute; g.font = "500 20px " + F;
    g.fillText(cat(d ? (d.demo ? "MẪU: chưa nối Pancake" : d.source ? (!qua && d.updated ? "Cập nhật " + d.updated : "Pancake POS") : "") : "Đang tải số liệu…", 34), W - 40, 48); g.textAlign = "left";
    var rows = d ? (mk ? d.marketing : d.sale) : [], kho = d && !mk ? d.kho : [];
    rows = rows.map(function (r) { return nhin(r, kieu); }); kho = kho.map(function (r) { return nhin(r, kieu); });
    var key = function (r) { return mk ? (r.month_orders || 0) * 1e9 + (r.spend || 0) : (r.revenue || 0) * 1e3 + (r.orders || 0); };
    rows.sort(function (a1, b1) { return key(b1) - key(a1); }); kho.sort(function (a1, b1) { return (b1.packed || b1.orders || 0) - (a1.packed || a1.orders || 0); });
    if (!d || !d.source || (!rows.length && !kho.length)) {
      g.fillStyle = mute; g.font = "600 28px " + F; g.fillText(!d ? "Đang lấy số liệu…" : "Chưa có số liệu Pancake cho phòng này.", 40, 220);
      g.font = "500 21px " + F; g.fillText("Ghi nhân viên và số liệu vào 00 - Dashboard/pancake-office.json.", 40, 266);
      return c;
    }
    var hasPanel = (!mk && kho.length) || (mk && d.ads && Object.keys(d.ads).length), colW = hasPanel ? 700 : W - 80, maxV = 1;
    rows.forEach(function (r) { maxV = Math.max(maxV, mk ? (r.month_orders || 0) : (r.revenue || 0)); });
    var rowH = 52, y0 = 150, xr = 40 + colW;
    g.font = "600 18px " + F; g.fillStyle = mute; g.fillText("HẠNG", 40, y0 - 8); g.fillText("NHÂN VIÊN", 104, y0 - 8); g.textAlign = "right";
    if (mk) { g.fillText("ĐƠN THÁNG", xr - 250, y0 - 8); g.fillText(qua ? "ĐƠN QUA" : "ĐƠN NAY", xr - 140, y0 - 8); g.fillText("CHI PHÍ", xr - 60, y0 - 8); g.fillText("ROAS", xr - 8, y0 - 8); }
    else { g.fillText("ĐƠN", xr - 190, y0 - 8); g.fillText("DOANH THU", xr - 10, y0 - 8); }
    g.textAlign = "left";
    rows.slice(0, 7).forEach(function (r, i) {
      var y = y0 + 8 + i * rowH, v = mk ? (r.month_orders || 0) : (r.revenue || 0);
      g.fillStyle = card; rr(g, 40, y, colW, rowH - 6, 12); g.fill();
      if (v) { g.fillStyle = ph.acc; g.globalAlpha = 0.2; rr(g, 40, y, Math.max(24, colW * v / maxV), rowH - 6, 12); g.fill(); g.globalAlpha = 1; }
      var cy = y + rowH / 2 - 3;
      g.fillStyle = i < 3 ? ph.acc : mute; g.font = "800 24px " + F; g.fillText("#" + (i + 1), 52, cy);
      g.fillStyle = ink; g.font = "700 24px " + F; g.fillText(cat(r.name, mk ? 12 : 16), 104, cy);
      g.textAlign = "right"; g.fillStyle = ink;
      if (mk) {
        g.font = "800 26px " + F; g.fillText(r.month_orders != null ? String(r.month_orders) : "-", xr - 250, cy);
        g.font = "600 22px " + F; g.fillText(String(r.orders || 0), xr - 140, cy); g.fillText(tien(r.spend), xr - 60, cy);
        g.fillStyle = r.roas >= 3 ? "#1fb86a" : r.roas > 0 ? "#f5a623" : mute; g.fillText(r.roas ? String(r.roas).replace(".", ",") + "x" : "-", xr - 8, cy);
      } else { g.font = "600 22px " + F; g.fillText(String(r.orders || 0), xr - 190, cy); g.fillText(tien(r.revenue), xr - 10, cy); }
      g.textAlign = "left";
    });
    if (mk) { g.fillStyle = mute; g.font = "500 17px " + F; g.fillText("ĐƠN THÁNG = đơn tính lương của các mã người đó phụ trách trong tháng", 40, H - 22); }
    var kx = 770, kw = W - 40 - kx;
    if (!mk && kho.length) {
      g.fillStyle = card; rr(g, kx, 130, kw, 400, 18); g.fill();
      g.fillStyle = ph.acc; g.font = "700 22px " + F; g.fillText("KHO · ĐÓNG GÓI", kx + 20, 160);
      kho.slice(0, 7).forEach(function (r, i) { var y = 204 + i * 46; g.fillStyle = ink; g.font = "600 22px " + F; g.fillText(cat(r.name, 12), kx + 20, y); g.textAlign = "right"; g.fillStyle = mute; g.fillText((r.packed || r.orders || 0) + " đơn", kx + kw - 20, y); g.textAlign = "left"; });
    } else if (mk && hasPanel) {
      var A = qua ? (d.ads_yesterday || null) : d.ads, T2 = { spend: "Chi phí ads", roas: "ROAS", revenue: "Doanh thu", orders: "Đơn", cpa: "CPA", ctr: "CTR" }, ky = 130; g.fillStyle = card; rr(g, kx, ky, kw, 400, 18); g.fill();
      g.fillStyle = ph.acc; g.font = "700 22px " + F; g.fillText("TỔNG QUẢNG CÁO", kx + 20, ky + 30);
      if (!A) { g.fillStyle = mute; g.font = "500 20px " + F; g.fillText("Chưa có số hôm qua", kx + 20, ky + 90); }
      else Object.keys(A).slice(0, 5).forEach(function (k, i) { var y = ky + 84 + i * 62; g.fillStyle = mute; g.font = "500 20px " + F; g.fillText(T2[k] || k, kx + 20, y - 14); g.fillStyle = ink; g.font = "800 32px " + F; g.fillText(k === "roas" ? String(A[k]).replace(".", ",") + "x" : tien(A[k]), kx + 20, y + 14); });
    }
    return c;
  }
  function dungPhongBan() {
    var light = sang(); nvPhong = []; vatPhong = []; bangPhong = {};
    var dat = new T.Mesh(new T.PlaneGeometry(240, 140), mat(light ? 0xd6e6d8 : 0x0f1b2c, { roughness: 1 })); dat.rotation.x = -Math.PI / 2; dat.position.y = -0.32; scene.add(dat); canhSan.push(dat);
    var go = sanGoMoi(RW / 4, HZ * 2 / 4) || veSanGo(light); if (!tgo_()) go.repeat.set(RW / 3, HZ * 2 / 3);
    PHONG.forEach(function (ph) {
      var san = new T.Mesh(new T.BoxGeometry(RW, 0.3, HZ * 2), new T.MeshStandardMaterial({ map: go, color: tgo_() ? (light ? 0xe6dcd0 : 0x8a8a8a) : 0xffffff, roughness: 0.55, metalness: 0.02 })); san.position.set(ph.cx, -0.15, 0); scene.add(san); canhSan.push(san);
      var tuongM = mat(light ? ph.mau : ph.mauToi), dir = ph.cx < 0 ? -1 : 1, xo = ph.cx + dir * (RW / 2 + 0.15);
      var sau = new T.Mesh(new T.BoxGeometry(RW + 0.6, 5.8, 0.3), tuongM); sau.position.set(ph.cx, 2.9, -HZ - 0.15); scene.add(sau);
      var ngoai = new T.Mesh(new T.BoxGeometry(0.3, 5.8, HZ * 2), tuongM); ngoai.position.set(xo, 2.9, 0); scene.add(ngoai);
      var tt = new T.Mesh(new T.BoxGeometry(RW + 0.6, 0.05, 0.12), mat(parseInt(ph.acc.slice(1), 16), { emissive: parseInt(ph.acc.slice(1), 16), emissiveIntensity: 0.6 })); tt.position.set(ph.cx, 5.8, -HZ - 0.15); scene.add(tt);
      canhTuong.push(sau, ngoai, tt);
      [["qua", -4.45], ["nay", 4.45]].forEach(function (kk) {
        var b = new T.Mesh(new T.PlaneGeometry(8.2, 4.1), new T.MeshBasicMaterial({ map: new T.CanvasTexture(veBangPhong(ph, kk[0])), toneMapped: false })); b.material.map.colorSpace = T.SRGBColorSpace;
        b.position.set(ph.cx + kk[1], 3.5, -HZ + 0.08); scene.add(b); giuBang.push(b); bangPhong[ph.id + "_" + kk[0]] = b; khungTV(8.2, 4.1, ph.cx + kk[1], 3.5, -HZ + 0.0, 0);
      });
      chanTuong(RW + 0.6, light, ph.cx, -HZ + 0.03, 0); chanTuong(HZ * 2, light, xo - dir * 0.15, 0, Math.PI / 2);
      caySan(ph.cx - RW / 2 + 1.2, -HZ + 1.3, 1); caySan(ph.cx + RW / 2 - 1.2, -HZ + 1.3, 1.2); caySan(ph.cx - dir * (RW / 2 - 1.2), HZ - 1.2, 0.9);
      var nh = spriteTu(veNhan(ph.ten, "Phòng ban", ph.acc, nenNhan()), 3.4); nh.position.set(ph.cx, 6.4, -HZ + 0.4); scene.add(nh); canhTuong.push(nh);
      [[-5.5, -4.05], [5.5, -4.05], [-5.5, 5.35], [5.5, 5.35], [0, 0.65]].forEach(function (p) { dungDenTran(ph.cx + p[0], p[1]); });
      dungDieuHoa(ph.cx + dir * (RW / 2 - 0.45), 4.65, -3.5, -dir * Math.PI / 2); dungDieuHoa(ph.cx + dir * (RW / 2 - 0.45), 4.65, 5.5, -dir * Math.PI / 2);
      [-3.5, 4.5].forEach(function (zz) { var pd = new T.PointLight(0xfff0d8, 1.2, 26, 1.3); pd.position.set(ph.cx, 4.8, zz); scene.add(pd); anh.lamps.push({ l: pd, b: 1.2 }); canhTuong.push(pd); });
    });
  }
  function chuHang(r) {
    return (r.dept === "marketing" ? (r.month_orders != null ? r.month_orders + " đơn tháng" : tien(r.spend) + " ads") + (r.roas ? " · ROAS " + String(r.roas).replace(".", ",") + "x" : "") : r.dept === "kho" ? (r.packed || r.orders || 0) + " đơn đóng gói" : (r.orders || 0) + " đơn · " + tien(r.revenue)) + (r.rank ? " · #" + r.rank : "");
  }
  function xepNhanVien() {
    if (!scene || !pancakeDL) return;
    var sig = ["sale", "kho", "marketing"].map(function (k) { return (pancakeDL[k] || []).map(function (r) { return r.name; }).join("|"); }).join("#");
    var capNhatChu = function () {
      nvPhong.forEach(function (a) { var r = a.row; if (!r || a.walking || a.cur || a.q.length) return; trangThai(a, chuHang(r)); });
    };
    if (sig === pancakeSig) { capNhatChu(); return; }
    pancakeSig = sig;
    vatPhong.forEach(function (o) { scene.remove(o); }); vatPhong = []; nvPhong = []; xoaChanPhong();
    var truoc = scene.children.length;
    PHONG.forEach(function (ph) {
      var dsr = ph.id === "sale" ? (pancakeDL.sale || []).concat(pancakeDL.kho || []) : (pancakeDL.marketing || []);
      dsr = dsr.slice(0, 20);
      var cot = 5, sp = 3.4, hang = Math.ceil(dsr.length / cot);
      dsr.forEach(function (r, i) {
        var cI = i % cot, hI = Math.floor(i / cot), n = Math.min(cot, dsr.length - hI * cot);
        var x = ph.cx + (cI - (n - 1) / 2) * sp, zd = -6.4 + hI * 4.7, vt = r.dept === "kho" ? "Nhân viên kho" : ph.vaiTro;
        var slot = { desk: { x: x, z: zd, rot: 0 }, stand: { x: x + 0, z: zd + 0.95 }, rot: Math.PI };
        slot.stand = { x: slot.stand.x, z: slot.stand.z + 0.1 };
        var a = taoAgent(r.name, vt, false, { x: slot.stand.x, z: slot.stand.z, kind: "desk" }, Math.PI);
        a.row = r; dungBan(slot, a, i + 1); a.group = ph.id; nvPhong.push(a);
      });
    });
    for (var k = truoc; k < scene.children.length; k++) vatPhong.push(scene.children[k]);
    apKhongGian(); capNhatChu();
  }
  function napPancake() {
    fetch("/office/pancake?brain=" + encodeURIComponent(brain())).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d || !scene) return;
      if (!d.source) {                      // chưa nối Pancake: phòng vẫn có người ngồi để xem, ghi rõ là mẫu
        var mk = function (ds, ns) { return ns.map(function (n, i) { return { name: n, dept: ds, rank: i + 1, orders: 0, revenue: 0, spend: 0, roas: 0, packed: 0 }; }); };
        d = { demo: true, source: "mẫu", updated: "", error: d.error || "", sale: mk("sale", ["Nhân viên Sale 1", "Nhân viên Sale 2", "Nhân viên Sale 3", "Nhân viên Sale 4", "Nhân viên Sale 5"]),
          kho: mk("kho", ["Nhân viên Kho 1", "Nhân viên Kho 2"]), marketing: mk("marketing", ["Nhân viên MKT 1", "Nhân viên MKT 2", "Nhân viên MKT 3", "Nhân viên MKT 4"]), ads: {} };
      }
      pancakeDL = d;
      PHONG.forEach(function (ph) { ["qua", "nay"].forEach(function (k) { if (bangPhong[ph.id + "_" + k]) capNhatSprite2(bangPhong[ph.id + "_" + k], veBangPhong(ph, k)); }); });
      xepNhanVien();
    }).catch(function () {});
  }
  // tường sơn: màu ấm có vân sơn mịn; chân tường trắng; khung tivi viền mỏng cho các bảng
  function veSon(light) {
    var c = document.createElement("canvas"), W = 256; c.width = W; c.height = W; var g = c.getContext("2d");
    g.fillStyle = light ? "#f1ece4" : "#1d2b45"; g.fillRect(0, 0, W, W);
    for (var i = 0; i < 2600; i++) { var k = (Math.sin(i * 12.9898) * 43758.5453) % 1; k = k - Math.floor(k); var k2 = (Math.sin(i * 78.233) * 12345.6789) % 1; k2 = k2 - Math.floor(k2); g.fillStyle = light ? "rgba(120,100,80," + (0.02 + k * 0.035) + ")" : "rgba(255,255,255," + (0.01 + k * 0.02) + ")"; g.fillRect(k * W, k2 * W, 2 + k * 3, 2); }
    var t = new T.CanvasTexture(c); t.colorSpace = T.SRGBColorSpace; t.wrapS = t.wrapT = T.RepeatWrapping; t.repeat.set(6, 3); t.anisotropy = 4; return t;
  }
  function chanTuong(w, light, cx, z, rot, d) {
    var m = new T.Mesh(new T.BoxGeometry(w, 0.28, 0.06), mat(light ? 0xfdfbf7 : 0x2c3d5e, { roughness: 0.4 })); m.position.set(cx, 0.14, z); m.rotation.y = rot || 0; scene.add(m); canhTuong.push(m);
  }
  function khungTV(w, h, x, y, z, ry, man) {
    var f = new T.Mesh(new T.BoxGeometry(w + 0.34, h + 0.34, 0.12), new T.MeshStandardMaterial({ color: 0x0a0c11, roughness: 0.3, metalness: 0.6 }));
    f.position.set(x, y, z); f.rotation.y = ry; scene.add(f); giuBang.push(f);
    var c = new T.Mesh(new T.BoxGeometry(w * 0.16, 0.06, 0.05), new T.MeshBasicMaterial({ color: 0x3a4152 })); c.position.set(0, -(h / 2 + 0.1), 0.07); f.add(c);
    var led = new T.Mesh(new T.CircleGeometry(0.035, 10), new T.MeshBasicMaterial({ color: 0x2a6bff })); led.position.set(w * 0.46, -(h / 2 + 0.1), 0.07); f.add(led);
    return f;
  }

  // ---------- cửa đôi giữa văn phòng và hai phòng bên: tự mở khi có người tới gần ----------
  var cuaDoi = [];
  function dungCuaPhong(tuong, light) {
    cuaDoi = [];
    [-1, 1].forEach(function (s) {
      var xw = s * (HX + 0.15), hD = 3.1, seg = HZ - DOOR;
      [-1, 1].forEach(function (u) { var w = new T.Mesh(new T.BoxGeometry(0.3, 5.8, seg), tuong); w.position.set(xw, 2.9, u * (DOOR + seg / 2)); scene.add(w); canhTuong.push(w); });
      var lt = new T.Mesh(new T.BoxGeometry(0.3, 5.8 - hD, DOOR * 2), tuong); lt.position.set(xw, hD + (5.8 - hD) / 2, 0); scene.add(lt); canhTuong.push(lt);
      var ng = new T.Mesh(new T.BoxGeometry(0.9, 0.3, DOOR * 2), mat(light ? 0xcfc6b8 : 0x3a4458, { roughness: 0.7 })); ng.position.set(xw, -0.15, 0); scene.add(ng); canhSan.push(ng);
      var kf = mat(light ? 0x8a6a4a : 0x6b5238, { roughness: 0.6 });
      [-1, 1].forEach(function (u) { var tr = new T.Mesh(new T.BoxGeometry(0.4, hD, 0.14), kf); tr.position.set(xw, hD / 2, u * DOOR); scene.add(tr); canhTuong.push(tr); });
      var ln = new T.Mesh(new T.BoxGeometry(0.4, 0.14, DOOR * 2 + 0.14), kf); ln.position.set(xw, hD, 0); scene.add(ln); canhTuong.push(ln);
      var lm = mat(light ? 0xe0c196 : 0x7a5d40, { roughness: 0.55 }), tm = mat(0xc0c8d4, { metalness: 0.7, roughness: 0.3 }), l = [], cw = DOOR - 0.05;
      [-1, 1].forEach(function (u) {
        var piv = new T.Group(); piv.position.set(xw, 0, u * (DOOR - 0.03)); scene.add(piv); canhTuong.push(piv);
        var lf = new T.Mesh(new T.BoxGeometry(0.1, hD - 0.08, cw), lm); lf.position.set(0, (hD - 0.08) / 2, -u * cw / 2); piv.add(lf);
        var tay = new T.Mesh(new T.BoxGeometry(0.2, 0.5, 0.06), tm); tay.position.set(0, 1.5, -u * (cw - 0.14)); piv.add(tay);
        l.push({ p: piv, u: u });
      });
      cuaDoi.push({ s: s, l: l, mo: 0 });
    });
  }
  function capNhatGhe(dt) {
    if (!ban) return;
    ban.ghe.forEach(function (s) { if (!s.chair || s.cp === s.ct) return; s.cp += Math.max(-1, Math.min(1, s.ct - s.cp)) * Math.min(1, dt * 3.2); if (Math.abs(s.ct - s.cp) < 0.01) s.cp = s.ct; s.chair.position.set(s.x + s.ox * 0.62 * s.cp, 0, s.z + s.oz * 0.62 * s.cp); });
  }
  function capNhatCua(dt) {
    var L = banDo();
    cuaDoi.forEach(function (c) {
      var xw = c.s * (HX + 0.15), gan = false;
      for (var i = 0; i < L.length; i++) if (Math.abs(L[i].x - xw) < 2.7 && Math.abs(L[i].z) < 2.6) { gan = true; break; }
      c.mo += ((gan ? 1 : 0) - c.mo) * Math.min(1, dt * 3.5);
      c.l.forEach(function (h) { h.p.rotation.y = -c.s * h.u * (Math.PI / 2) * 0.94 * c.mo; });
    });
  }
  // ---------- đồ Higgsfield đặt vào cảnh (quầy trà, điều hòa...), thiếu file thì dựng hình đơn giản ----------
  function datProp(ten, x, z, cao, yaw, y0) {
    var v = vatProp(ten, cao); if (!v) return null;
    v.position.set(x, y0 || 0, z); v.rotation.y = yaw || 0; v.userData.ten = ten; scene.add(v); return v;
  }
  var QUAY = {
    tra: [{ x: 11.3, z: 6.9, rot: Math.PI / 2 }, { x: 11.3, z: 7.9, rot: Math.PI / 2 }, { x: 11.3, z: 8.9, rot: Math.PI / 2 }],
    dung: [{ x: 7.6, z: 6.4, rot: Math.PI / 2 }, { x: 9.6, z: 6.4, rot: -Math.PI / 2 }, { x: 7.6, z: 8.8, rot: Math.PI / 2 }, { x: 9.6, z: 8.8, rot: -Math.PI / 2 }]
  };
  var CHAT = [{ x: -7, z: 5.6 }, { x: -3, z: 5.6 }, { x: 1, z: 5.6 }, { x: -7, z: -5.6 }, { x: -3, z: -5.6 }, { x: 3, z: -5.6 }];
  function dungQuayTra() {
    var light = sang();
    // quầy trà dựa tường phải: máy cà phê, khay trà, tủ bánh; bình nước đứng cạnh
    if (!datProp("bar", 12.75, 7.9, 1.0, Math.PI / 2)) {
      var q = new T.Mesh(new T.BoxGeometry(1.4, 1.05, 3.5), mat(light ? 0xe8dfd2 : 0x3a4458)); q.position.set(12.75, 0.5, 7.9); scene.add(q);
    }
    datProp("coffee", 12.75, 6.9, 0.62, PROP_YAW.coffee, 1.0);
    datProp("tea_tray", 12.75, 7.9, 0.2, PROP_YAW.tea_tray, 1.0);
    datProp("cake", 12.75, 8.9, 0.42, PROP_YAW.cake, 1.0);
    datProp("water", 13.0, 5.6, 1.45, PROP_YAW.water);
    [[8.6, 6.4, "cake", 0.34], [8.6, 8.8, "tea_tray", 0.2]].forEach(function (p) {
      if (!datProp("stand_table", p[0], p[1], 1.15, 0)) { var tb = new T.Mesh(new T.CylinderGeometry(0.55, 0.55, 0.06, 20), mat(0xe6dcc8)); tb.position.set(p[0], 1.12, p[1]); scene.add(tb); var tr = new T.Mesh(new T.CylinderGeometry(0.06, 0.06, 1.1, 8), mat(0x2a2f3a)); tr.position.set(p[0], 0.55, p[1]); scene.add(tr); }
      datProp(p[2], p[0], p[1], p[3], 0, 1.15);
      chanTron(p[0], p[1], 0.62);
    });
    chanHinhChuNhat(12.75, 7.9, 1.5, 3.7, 0, 0.2); chanTron(13.0, 5.6, 0.4);
    var nh = spriteTu(veNhan("Quầy trà", "Giải lao, cà phê, bánh", "#f5a623", nenNhan()), 2.6); nh.position.set(12.4, 3.2, 7.9); scene.add(nh); canhTuong.push(nh);
  }
  // đèn trần (ẩn cùng tường) và điều hòa treo tường
  function dungDenTran(x, z) {
    var g = new T.Group(); g.position.set(x, 5.45, z);
    var m = new T.MeshStandardMaterial({ color: 0xfff7e6, emissive: 0xfff0cc, emissiveIntensity: 0.2, roughness: 0.4 });
    var p = new T.Mesh(new T.BoxGeometry(1.5, 0.07, 0.5), m); g.add(p);
    var vi = new T.Mesh(new T.BoxGeometry(1.62, 0.04, 0.62), mat(0xdfe5ee)); vi.position.y = 0.05; g.add(vi);
    scene.add(g); canhTuong.push(g); anh.tran.push(p);
    if (!anh.poolTex) {
      var cv_ = document.createElement("canvas"); cv_.width = cv_.height = 128; var cx_ = cv_.getContext("2d"), gr = cx_.createRadialGradient(64, 64, 2, 64, 64, 64);
      gr.addColorStop(0, "rgba(255,226,170,0.9)"); gr.addColorStop(0.5, "rgba(255,214,150,0.35)"); gr.addColorStop(1, "rgba(255,200,130,0)"); cx_.fillStyle = gr; cx_.fillRect(0, 0, 128, 128);
      anh.poolTex = new T.CanvasTexture(cv_);
    }
    var po = new T.Mesh(new T.PlaneGeometry(5.2, 4.2), new T.MeshBasicMaterial({ map: anh.poolTex, transparent: true, opacity: 0, blending: T.AdditiveBlending, depthWrite: false, toneMapped: false }));
    po.rotation.x = -Math.PI / 2; po.position.set(x, 0.06, z); scene.add(po); canhTuong.push(po); anh.pool.push(po);
  }
  function dungDieuHoa(x, y, z, yaw) {
    var v = vatProp("ac", 0.72);
    if (!v) { v = new T.Group(); var b = new T.Mesh(new T.BoxGeometry(2.1, 0.7, 0.6), mat(0xf4f6fa, { roughness: 0.35 })); b.position.y = 0.35; v.add(b); }
    v.position.set(x, y, z); v.rotation.y = yaw; scene.add(v); canhTuong.push(v);
  }
  function dungTranNha() {
    [[-7, -5.8], [0, -5.8], [7, -5.8], [-7, 5.8], [0, 5.8], [7, 5.8]].forEach(function (p) { dungDenTran(p[0], p[1]); });
    [-8, 0, 8].forEach(function (x) { var pl = new T.PointLight(0xfff0d8, 1.3, 24, 1.3); pl.position.set(x, 5.0, 0); scene.add(pl); anh.lamps.push({ l: pl, b: 1.3 }); canhTuong.push(pl); });
    dungDieuHoa(-HX + 0.45, 4.65, -7, Math.PI / 2); dungDieuHoa(-HX + 0.45, 4.65, 7, Math.PI / 2); dungDieuHoa(HX - 0.45, 4.65, 6.4, -Math.PI / 2);
  }
  // ---------- độ sáng theo giờ thật: ban ngày sáng, chiều tối ấm, ban đêm tối và bật đèn ----------
  function smooth(x) { return x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x); }
  function giuAnh() { var d = new Date(); return window.__mmOfficeHour != null ? +window.__mmOfficeHour : d.getHours() + d.getMinutes() / 60; }
  function apAnhSang() {
    if (!scene || !anh.hemi) return;
    var h = giuAnh(), kT = smooth((h - 5.0) / 2.0) * (1 - smooth((h - 17.0) / 2.0)), light = sang();
    var k = light ? kT : Math.min(kT, 0.4), dem = light ? 1 - kT : 1;          // chế độ tối: đèn điện luôn bật, trời tối
    anh.hemi.intensity = (light ? 1.0 : 0.75) * (0.36 + 0.64 * k);
    anh.dl.intensity = (light ? 1.2 : 0.7) * (0.08 + 0.92 * k);
    anh.dl.color.setRGB(1, 0.7 + 0.3 * k, 0.45 + 0.55 * k); anh.dl.position.set(-8 + (h - 12) * 2.4, 18, 10);
    var nen = new T.Color(light ? 0xe9f0fa : 0x0d1524).lerp(new T.Color(0x05080f), dem * 0.9);
    scene.background.copy(nen); if (scene.fog) scene.fog.color.copy(nen);
    anh.lamps.forEach(function (o) { o.l.intensity = o.b * (0.35 + 1.5 * dem); });
    anh.tran.forEach(function (m) { m.material.emissiveIntensity = 0.18 + 1.2 * dem; });
    anh.pool.forEach(function (m) { m.material.opacity = 0.55 * dem; m.visible = dem > 0.05; });
  }
  function tgo_() { return !!(NV && NV.sanGo); }
  function dungCanh() {
    var light = sang(), nen = light ? 0xe9f0fa : 0x0d1524;
    scene = new T.Scene(); scene.background = new T.Color(nen); scene.fog = new T.Fog(nen, 55, 110);
    anh = { lamps: [], tran: [], pool: [], hemi: null, dl: null };
    anh.hemi = new T.HemisphereLight(0xffffff, light ? 0xbfcbe0 : 0x24365a, light ? 1.0 : 0.75); scene.add(anh.hemi);
    var dl = new T.DirectionalLight(0xffffff, light ? 1.2 : 0.7); dl.position.set(-8, 18, 10); scene.add(dl); anh.dl = dl;
    canhTuong = []; canhSan = []; giuBang = []; cuaDoi = [];
    var san = new T.Mesh(new T.BoxGeometry(HX * 2, 0.3, HZ * 2), mat(light ? 0xf7f9fd : 0x16233a, { roughness: 0.9 })); san.position.y = -0.15; scene.add(san); canhSan.push(san);
    var tgo = sanGoMoi(HX * 2 / 4, HZ * 2 / 4); if (tgo) { san.material.map = tgo; san.material.color.set(light ? 0xe6dcd0 : 0x8a8a8a); san.material.roughness = 0.5; san.material.needsUpdate = true; }
    var luoi = new T.GridHelper(HX * 2, Math.round(HX * 2), light ? 0xd5deec : 0x24385a, light ? 0xe4ebf6 : 0x1d2d49); luoi.position.y = 0.01; luoi.scale.z = HZ / HX; if (!tgo_()) { scene.add(luoi); canhSan.push(luoi); }
    var tuong = mat(light ? 0xffffff : 0xffffff, { map: veSon(light), roughness: 0.95 });
    var t1 = new T.Mesh(new T.BoxGeometry(HX * 2, 5.8, 0.3), tuong); t1.position.set(0, 2.9, -HZ - 0.15); scene.add(t1);
    var vien = new T.Mesh(new T.BoxGeometry(HX * 2, 0.05, 0.12), mat(0x2a6bff, { emissive: 0x2a6bff, emissiveIntensity: 0.6 })); vien.position.set(0, 5.8, -HZ - 0.15); scene.add(vien); canhTuong.push(t1, vien);
    dungCuaPhong(tuong, light);
    chanTuong(HX * 2, light, 0, -HZ + 0.03, 0);
    khoiTaoLuoi(); taoManHinh();
    // bảng điều hành (số liệu thật) giữa tường sau; khẩu hiệu hai bên và trên tường trái
    bang = new T.Mesh(new T.PlaneGeometry(9, 3.6), new T.MeshBasicMaterial({ map: new T.CanvasTexture(veBangDieuHanh()), toneMapped: false })); bang.material.map.colorSpace = T.SRGBColorSpace;
    bang.position.set(HX - 0.14, 3.95, -5.7); bang.rotation.y = -Math.PI / 2; scene.add(bang); giuBang.push(bang); khungTV(9, 3.6, HX - 0.06, 3.95, -5.7, -Math.PI / 2);   // sau lưng giám đốc
    function kh(i, x, y, z, ry, w) { var m = new T.Mesh(new T.PlaneGeometry(w, w * 260 / 900), new T.MeshBasicMaterial({ map: new T.CanvasTexture(veKhauHieu(i)), toneMapped: false })); m.material.map.colorSpace = T.SRGBColorSpace; m.position.set(x, y, z); m.rotation.y = ry; scene.add(m); canhTuong.push(m); }
    kh(0, -8.0, 3.5, -HZ + 0.02, 0, 5.0); kh(1, 8.0, 3.5, -HZ + 0.02, 0, 5.0); kh(6, 0, 3.5, -HZ + 0.02, 0, 5.0);
    kh(2, -HX + 0.02, 3.5, -6.2, Math.PI / 2, 5.0); kh(3, -HX + 0.02, 4.6, 0, Math.PI / 2, 5.0); kh(4, -HX + 0.02, 3.5, 6.2, Math.PI / 2, 5.0);
        den(-12.9, -9.2, 0xffd9a0); den(12.9, -9.2, 0xffd9a0); den(-12.9, 9.2, 0xffd9a0); den(12.9, 4.1, 0xffd9a0);
    tram = STATION_DEFS.map(dungTram);
    ban = dungBanHop(); dungQuayTra(); dungTranNha(); dungPhongBan();
    apKhongGian(); apAnhSang();
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
    cam.tx = Math.max(-HX - 30, Math.min(HX + 30, cam.tx)); cam.tz = Math.max(-HZ - 3, Math.min(HZ + 3, cam.tz)); cam.ty = Math.max(0, Math.min(4, cam.ty));
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
    // cột trái chừa lối cửa ở giữa (z quanh 0); hàng trước dừng sớm để nhường góc phải cho quầy trà
    var trai = Math.min(6, Math.ceil(n * 0.3)), con = n - trai, sau = Math.ceil(con / 2), truoc = con - sau, res = [], i;
    function sp(a, b, k, m) { return m <= 1 ? (a + b) / 2 : a + (b - a) * k / (m - 1); }
    for (i = 0; i < sau; i++) { var x = sp(-10, 8, i, sau); res.push({ desk: { x: x, z: -9.5, rot: 0 }, stand: { x: x, z: -8.55 }, rot: Math.PI }); }
    for (i = 0; i < truoc; i++) { var x2 = sp(-10, 4.2, i, truoc); res.push({ desk: { x: x2, z: 9.5, rot: Math.PI }, stand: { x: x2, z: 8.55 }, rot: 0 }); }
    var ZT = [-3.9, 3.9, -6.6, 6.6, -9.0, 8.9];
    for (i = 0; i < trai; i++) { var z = ZT[i]; res.push({ desk: { x: -13.3, z: z, rot: Math.PI / 2 }, stand: { x: -12.35, z: z }, rot: -Math.PI / 2 }); }
    return res;
  }
  function dungNguoi(list) {
    list = list.slice(0, 22);
    var bt = boTri(list.length);
    list.forEach(function (ag, i) {
      var p = bt[i];
      if (NV) { var kx = Math.sign(p.stand.x - p.desk.x), kz = Math.sign(p.stand.z - p.desk.z); p.stand = { x: p.stand.x + kx * 0.1, z: p.stand.z + kz * 0.1 }; }
      var a = taoAgent(ag.name || ag.slug, ag.role, false, { x: p.stand.x, z: p.stand.z, kind: "desk" }, p.rot);
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
  function hienVat(a, on) { a.book = !!on; }

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
  function cham(a) { if (a.cur && a.cur.s && (a.cur.t === "ngoi" || a.cur.t === "rave")) a.cur.s.ct = 0; a.q.length = 0; a.cur = null; a.walking = false; }
  function veBan(a, label) {
    cham(a); hienVat(a, false); di(a, a.home, label || "Về chỗ làm"); a.q.push({ t: "face", huong: a.huong }); a.q.push({ t: "hold", pose: "type", tt: "Đang làm việc" });
  }
  function toiGhe(a, label, tt) {
    var g = a.seat; if (!g) return;
    hienVat(a, true); di(a, g, label); a.q.push({ t: "face", huong: g.rot }); a.q.push({ t: "hold", pose: a.lead ? "listen" : ngauNhien(DANG_NGOI), doi: a.lead ? null : DANG_NGOI, tt: tt || "Đang họp" });
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
    } else if (k === "join") {
      a = timAgent(ev.agent); if (a) vaoPhien(key, a, (phien[key] && phien[key].ten) || "");
    } else if (k === "talk") {
      a = ev.agent === "@lead" ? lead : timAgent(ev.agent); if (a) phatBieu(a, ev.text, ev.ms || 6000, ev.tt || "Đang trình bày");
    } else if (k === "run_end") {
      rutKhoiPhien(key, ev.ok, ev.ok ? "Chốt xong. Cảm ơn cả nhóm." : "Lần chạy có lỗi, cần xem lại.");
    }
  }


  // ---------- ai cũng có đời sống riêng: đi uống nước, ăn bánh, dạo, xem bảng, tán gẫu; giám đốc đi xem bảng các phòng ----------
  var cheDo = null, cheDoHet = 0, lastTuDong = "", luotTiep = 3, luotGD = 80;
  var DANG_NGOI = ["listen", "write", "chin", "fold", "cross", "listen", "write"], DANG_DUNG = ["cross", "chin", "back", "hip", "talk", "listen", "cross", "talk"];
  function ngauNhien(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
  function moiNguoi() { return ds.filter(function (x) { return !x.lead; }).concat(nvPhong); }
  function ranh(a) { return !!a && !a.lead && !a.walking && !a.cur && a.q.length === 0 && a.kind === "desk" && !a.seat && a.holdPose === "type" && !conTrongPhien(a); }
  function choTrong(sp, tru) {
    var L = banDo();
    for (var i = 0; i < L.length; i++) {
      var o = L[i]; if (o === tru) continue;
      if (Math.hypot(o.x - sp.x, o.z - sp.z) < 0.9) return false;
      var qs = (o.cur ? [o.cur] : []).concat(o.q);
      for (var k = 0; k < qs.length; k++) if (qs[k].t === "walk" && Math.hypot(qs[k].to.x - sp.x, qs[k].to.z - sp.z) < 0.6) return false;
    }
    return true;
  }
  function chonCho(arr, a) { var x = xaoTron(arr); for (var i = 0; i < x.length; i++) if (choTrong(x[i], a)) return x[i]; return null; }
  function stay_(a, o) { var c = { t: "stay", ms: 3000, pose: "idle" }; for (var k in o) c[k] = o[k]; a.q.push(c); }
  function chu_(a) { if (a.row) trangThai(a, chuHang(a.row)); else trangThai(a, "Đang làm việc"); }
  function veChoLam(a) { di(a, a.home, "Về chỗ làm"); a.q.push({ t: "face", huong: a.huong }); a.q.push({ t: "hold", pose: "type" }); a.q.push({ t: "call", fn: chu_ }); }
  function ngau(a, b) { return a + Math.random() * (b - a); }
  var DAO = [{ x: -8, z: 5.6 }, { x: -4, z: 5.2 }, { x: 0, z: 5.6 }, { x: 4, z: 5.2 }, { x: -8, z: -5.6 }, { x: -3, z: -5.6 }, { x: 3, z: -5.6 }, { x: 8, z: -5.2 }, { x: 10, z: 3.8 }];
  var CAU_CHAT = ["Hôm nay đơn về nhiều nhỉ?", "Cuối tuần có đi đâu không?", "Quán cà phê mới đầu đường ngon lắm.", "Chiều nay họp có gì mới không?", "Mình vừa chốt được mấy đơn lớn.", "Nghe nói tuần sau có chiến dịch mới.", "Trời nóng quá, uống gì đi."];
  function hdNuoc(a, loai, ms) {
    var sp = chonCho(QUAY.tra, a); if (!sp) return false;
    loai = loai || ["cup", "cafe", "cup"][Math.floor(Math.random() * 3)];
    di(a, { x: sp.x, z: sp.z, kind: "dung" }, loai === "cafe" ? "Đi pha cà phê" : "Đi lấy nước uống");
    a.q.push({ t: "face", huong: sp.rot });
    stay_(a, { ms: 1500, pose: "idle", tt: loai === "cafe" ? "Pha cà phê" : "Rót nước" });
    stay_(a, { ms: ms || ngau(7000, 9500), pose: "drink", item: loai, tt: loai === "cafe" ? "Uống cà phê" : "Uống nước" });
    return true;
  }
  function hdAn(a, ms) {
    var sp = chonCho(QUAY.dung, a); if (!sp) return false;
    di(a, { x: sp.x, z: sp.z, kind: "dung" }, "Đi ăn bánh"); a.q.push({ t: "face", huong: sp.rot });
    stay_(a, { ms: ms || ngau(7500, 10500), pose: "drink", item: "banh", tt: "Ăn bánh" });
    return true;
  }
  function hdDao(a) {
    var n = 1 + Math.floor(Math.random() * 2), i;
    for (i = 0; i < n; i++) { var sp = chonCho(DAO, a); if (!sp) break; di(a, { x: sp.x, z: sp.z, kind: "dung" }, "Đi dạo"); stay_(a, { ms: ngau(2200, 4200), pose: "idle", tt: "Đi dạo cho đỡ mỏi" }); }
    return i > 0;
  }
  function diemBang() {
    var r = [{ x: HX - 3.0, z: -5.7, rot: Math.PI / 2, nhin: { x: HX, z: -5.7 }, ten: "bảng điều hành", diem: new T.Vector3(HX - 0.1, 3.95, -5.7) }];
    PHONG.forEach(function (ph) {
      [["qua", -4.45, "hôm qua"], ["nay", 4.45, "hôm nay"]].forEach(function (k) {
        r.push({ x: ph.cx + k[1], z: -8.4, rot: Math.PI, nhin: { x: ph.cx + k[1], z: -HZ }, ten: "bảng " + ph.ten.toLowerCase() + " " + k[2], diem: new T.Vector3(ph.cx + k[1], 3.5, -HZ + 0.1), ph: ph, kieu: k[0] });
      });
    });
    return r;
  }
  function hdXem(a) {
    var sp = chonCho(diemBang(), a); if (!sp) return false;
    di(a, { x: sp.x, z: sp.z, kind: "dung" }, "Đi xem " + sp.ten); a.q.push({ t: "face", huong: sp.rot });
    stay_(a, { ms: ngau(7000, 10000), pose: "idle", nhin: sp.nhin, tt: "Xem " + sp.ten });
    return true;
  }
  function hdChat(a) {
    var b = xaoTron(moiNguoi().filter(function (o) { return o !== a && ranh(o); }))[0]; if (!b) return false;
    var sp = chonCho(CHAT, a); if (!sp) return false;
    var pa = { x: sp.x - 0.6, z: sp.z, kind: "dung" }, pb = { x: sp.x + 0.6, z: sp.z, kind: "dung" }, c1 = CAU_CHAT[Math.floor(Math.random() * CAU_CHAT.length)], c2 = CAU_CHAT[Math.floor(Math.random() * CAU_CHAT.length)];
    di(a, pa, "Đi nói chuyện với " + cat(b.ten, 12)); stay_(a, { ms: 5200, pose: "talk", nhin: pb, text: c1, tt: "Nói chuyện" }); stay_(a, { ms: 4600, pose: "listen", nhin: pb, tt: "Nói chuyện" }); stay_(a, { ms: 4800, pose: "talk", nhin: pb, text: c2, tt: "Nói chuyện" });
    di(b, pb, "Đi nói chuyện với " + cat(a.ten, 12)); stay_(b, { ms: 5200, pose: "listen", nhin: pa, tt: "Nói chuyện" }); stay_(b, { ms: 4600, pose: "talk", nhin: pa, text: c2, tt: "Nói chuyện" }); stay_(b, { ms: 4800, pose: "listen", nhin: pa, tt: "Nói chuyện" });
    veChoLam(a); veChoLam(b); return true;
  }
  function quayDoi(dt) {
    var d = new Date(), h = d.getHours(), key = d.toDateString() + "-" + h;
    if ((h === 10 || h === 15) && d.getMinutes() < 2 && lastTuDong !== key && !cheDo && ban) { lastTuDong = key; gioGiaiLao(); }
    if (cheDo) { if (now() > cheDoHet) cheDo = null; return; }
    var coPhien = Object.keys(phien).length > 0;
    if (lead && !coPhien) {
      luotGD -= dt;
      if (luotGD <= 0) { luotGD = ngau(110, 170); if (!lead.walking && !lead.cur && lead.q.length === 0 && lead.kind === "seat") giamDocDi(); }
    }
    luotTiep -= dt; if (luotTiep > 0) return; luotTiep = ngau(1.5, 4);
    var L = moiNguoi(), dang = L.filter(function (o) { return o.walking || o.q.length || o.kind !== "desk"; }).length;
    if (dang >= Math.max(2, Math.ceil(L.length * 0.22))) return;
    var cand = L.filter(ranh); if (!cand.length) return;
    var a = cand[Math.floor(Math.random() * cand.length)];
    if (now() - (a.hdCuoi || 0) < 25000) return;
    a.hdCuoi = now();
    var r = Math.random(), ok = false;
    if (r < 0.26) ok = hdNuoc(a); else if (r < 0.4) ok = hdAn(a); else if (r < 0.58) ok = hdDao(a); else if (r < 0.8) ok = hdXem(a); else ok = hdChat(a);
    if (ok) { if (!a.q.length || a.q[a.q.length - 1].t !== "call") veChoLam(a); }
  }
  function tomTatBang(sp) {
    var dl = pancakeDL; if (!dl || !sp.ph) return "Số liệu đang cập nhật, mọi người cố gắng nhé.";
    var ls = sp.ph.id === "sale" ? (dl.sale || []).concat(dl.kho || []) : (dl.marketing || []), tong = 0, dt = 0, ch = 0;
    ls.forEach(function (r) { var v = sp.kieu === "qua" ? nhin(r, "qua") : r; tong += v.orders || 0; dt += v.revenue || 0; ch += v.spend || 0; });
    var ngay = sp.kieu === "qua" ? "Hôm qua" : "Hôm nay";
    return sp.ph.id === "sale" ? ngay + " phòng Sale chốt " + tong + " đơn, doanh thu " + tien(dt) + "." : ngay + " phòng Marketing chi " + tien(ch) + " quảng cáo, mang về " + tong + " đơn.";
  }
  function giamDocDi() {
    var bs = diemBang(), ch = [bs[0]], ph = xaoTron(PHONG)[0];
    bs.forEach(function (b) { if (b.ph === ph) ch.push(b); });
    hienVat(lead, false);
    var fol = xaoTron(moiNguoi().filter(ranh)).slice(0, 2);
    ch.forEach(function (sp, i) {
      di(lead, { x: sp.x, z: sp.z, kind: "dung" }, "Đi xem " + sp.ten); lead.q.push({ t: "face", huong: sp.rot });
      stay_(lead, { ms: 8500, pose: "point", diem: sp.diem, nhin: sp.nhin, text: sp.ph ? tomTatBang(sp) : "Mình xem lại bảng điều hành chung của công ty.", tt: "Xem " + sp.ten });
      fol.forEach(function (f, k) {
        var sg = k ? 1 : -1, ngang = sp.rot === Math.PI;
        di(f, { x: ngang ? sp.x + 1.5 * sg : sp.x - 0.2, z: ngang ? sp.z + 0.2 : sp.z + 1.5 * sg, kind: "dung" }, "Đi cùng giám đốc");
        stay_(f, { ms: 8800, pose: k ? "cross" : "listen", nhin: sp.nhin, tt: "Nghe giám đốc" });
      });
    });
    di(lead, lead.seat || lead.home, "Về chỗ họp"); lead.q.push({ t: "face", huong: (lead.seat || lead.home).rot }); lead.q.push({ t: "hold", pose: "listen", tt: "Điều hành" });
    fol.forEach(function (f) { veChoLam(f); });
  }
  // ---------- họp toàn công ty và giờ giải lao ----------
  function toanBo() { return moiNguoi(); }
  function choDungHop() {
    var r = [], x;
    for (x = -5.5; x <= 5.6; x += 1.2) { r.push({ x: x, z: -4.3 }); r.push({ x: x, z: 4.3 }); }
    for (x = -4.8; x <= 4.9; x += 1.2) { r.push({ x: x, z: -5.5 }); r.push({ x: x, z: 5.5 }); }
    for (var z = -2.4; z <= 2.5; z += 1.2) { r.push({ x: -8.6, z: z }); r.push({ x: 8.6, z: z }); }
    r.sort(function (p, q) { return Math.hypot(p.x, p.z * 1.4) - Math.hypot(q.x, q.z * 1.4); });
    var lx = lead ? lead.x : 6.8, lz = lead ? lead.z : 0;
    r.forEach(function (p) { p.rot = Math.atan2(lx - p.x, lz - p.z); });
    return r;
  }
  function baoCaoHop(a, text) {
    stay_(a, { ms: 6200, pose: "talk", text: text, tt: "Báo cáo trong họp", stand: true, speak: true });
    a.q.push({ t: "hold", pose: ngauNhien(a.hop === "ngoi" ? DANG_NGOI : DANG_DUNG), doi: a.hop === "ngoi" ? DANG_NGOI : DANG_DUNG, tt: "Đang họp" });
  }
  function hopToanCty() {
    var tat = xaoTron(toanBo()); if (tat.length < 2 || !ban || !lead) { toast("Chưa đủ nhân viên để họp toàn công ty."); return; }
    cheDo = "hop"; cheDoHet = now() + 190000; ban.sangDen = now() + 150000; toast("Họp toàn công ty: tất cả nhân viên về phòng họp chính");
    noi_(lead, "Triệu tập họp toàn công ty", 4000); trangThai(lead, "Chủ trì họp");
    var ghe_ = ban.ghe.slice(1).filter(function (g) { return !g.by; }), dungC = choDungHop();
    tat.forEach(function (a, i) {
      cham(a); hienVat(a, true);
      if (i < ghe_.length) { var g = ghe_[i]; g.by = a; a.seat = g; a.hop = "ngoi"; di(a, { x: g.sx, z: g.sz, kind: "dung" }, "Đi họp toàn công ty"); a.q.push({ t: "ngoi", s: g }); a.q.push({ t: "hold", pose: ngauNhien(DANG_NGOI), doi: DANG_NGOI, tt: "Đang họp" }); }
      else { var sp = dungC[(i - ghe_.length) % dungC.length]; a.hop = "dung"; di(a, { x: sp.x, z: sp.z, kind: "dung" }, "Đi họp toàn công ty"); a.q.push({ t: "face", huong: sp.rot }); a.q.push({ t: "hold", pose: ngauNhien(DANG_DUNG), doi: DANG_DUNG, tt: "Đứng nghe họp" }); }
    });
    function sau(ms, f) { setTimeout(function () { if (mo && cheDo === "hop") f(); }, ms); }
    function doiDu(f) { var t0 = now(); (function lap() { if (!mo || cheDo !== "hop") return; if (tat.every(function (a) { return !a.walking && a.q.length === 0; }) || now() - t0 > 70000) f(); else setTimeout(lap, 700); })(); }
    doiDu(function () {
      lead.q.length = 0; phatBieu(lead, "Chào cả công ty. Tôi nói nhanh hướng đi tuần này, rồi nghe từng bộ phận báo cáo.", 7500, "Chủ trì họp"); lead.q.push({ t: "hold", pose: "listen", tt: "Điều hành" });
      var ng = tat.filter(function (a) { return a.hop === "ngoi" && !a.row; }), du = tat.filter(function (a) { return a.hop === "dung"; }), ph = tat.filter(function (a) { return a.row; });
      var ds_ = [ng[0], du[0], ph[0], ph.length > 1 ? ph[ph.length - 1] : ng[1], du[1]].filter(function (x, i, arr) { return x && arr.indexOf(x) === i; });
      ds_.slice(0, 4).forEach(function (a, i) {
        sau(9500 + i * 7200, function () {
          var r = a.row, tx = r ? (r.dept === "marketing" ? "Em " + cat(a.ten, 14) + " báo cáo: tháng này em có " + (r.month_orders != null ? r.month_orders : (r.orders || 0)) + " đơn tính lương, chi " + tien(r.spend) + " quảng cáo." : "Em " + cat(a.ten, 14) + " báo cáo: hôm nay em xử lý " + (r.orders || r.packed || 0) + " đơn" + (r.revenue ? ", doanh thu " + tien(r.revenue) : "") + ".") : ["Bên em đang xử lý ổn, không có việc tồn.", "Em đã xong phần việc hôm qua, đang làm tiếp phần mới.", "Em cần thêm một người hỗ trợ cho đợt cao điểm."][i % 3];
          baoCaoHop(a, tx);
        });
      });
      sau(9500 + 4 * 7200 + 1500, function () { lead.q.length = 0; phatBieu(lead, "Cảm ơn mọi người. Ai về việc nấy, chiều nay báo lại cho tôi.", 5200, "Chốt họp"); lead.q.push({ t: "hold", pose: "listen", tt: "Điều hành" }); });
      sau(9500 + 4 * 7200 + 8500, function () {
        ban.sangDen = 0; cheDo = null;
        tat.forEach(function (a) { var sg = a.seat, daNgoi = sg && a.kind === "seat"; if (a.seat) { a.seat.by = null; a.seat = null; } a.hop = null; hienVat(a, false); cham(a); noi_(a, "Xong họp, về làm việc", 2200); if (daNgoi) a.q.push({ t: "rave", s: sg }); di(a, a.home, "Về chỗ làm"); a.q.push({ t: "face", huong: a.huong }); a.q.push({ t: "hold", pose: "type" }); a.q.push({ t: "call", fn: chu_ }); });
      });
    });
  }
  function gioGiaiLao() {
    var tat = xaoTron(toanBo().filter(function (a) { return !a.seat && !conTrongPhien(a); }));
    if (tat.length < 2 || !ban) { toast("Chưa đủ nhân viên để giải lao."); return; }
    cheDo = "nghi"; cheDoHet = now() + 80000; toast("Giờ giải lao: mọi người ra quầy trà, đứng nói chuyện");
    var gp = tat.slice(0, Math.max(2, Math.ceil(tat.length * 0.55))), tra = QUAY.tra.slice(), dung = QUAY.dung.slice(), chat = xaoTron(CHAT.slice()), con = [];
    gp.forEach(function (a) {
      cham(a); hienVat(a, false);
      if (tra.length) {
        var sp = tra.shift(), loai = ["cup", "cafe", "cup"][Math.floor(Math.random() * 3)];
        di(a, { x: sp.x, z: sp.z, kind: "dung" }, loai === "cafe" ? "Đi pha cà phê" : "Đi lấy nước uống"); a.q.push({ t: "face", huong: sp.rot });
        stay_(a, { ms: 1500, pose: "idle", tt: "Rót nước" }); stay_(a, { ms: 8000, pose: "drink", item: loai, tt: loai === "cafe" ? "Uống cà phê" : "Uống nước" }); stay_(a, { ms: 3500, pose: "idle", text: CAU_CHAT[Math.floor(Math.random() * CAU_CHAT.length)], tt: "Giải lao" }); stay_(a, { ms: 9000, pose: "drink", item: loai, tt: "Giải lao" }); veChoLam(a);
      } else if (dung.length) {
        var s2 = dung.shift(); di(a, { x: s2.x, z: s2.z, kind: "dung" }, "Đi ăn bánh"); a.q.push({ t: "face", huong: s2.rot });
        stay_(a, { ms: 9000, pose: "drink", item: "banh", tt: "Ăn bánh" }); stay_(a, { ms: 4000, pose: "talk", text: CAU_CHAT[Math.floor(Math.random() * CAU_CHAT.length)], tt: "Giải lao" }); stay_(a, { ms: 9000, pose: "drink", item: "banh", tt: "Giải lao" }); veChoLam(a);
      } else con.push(a);
    });
    for (var i = 0; i + 1 < con.length && chat.length; i += 2) {
      var sp3 = chat.shift(), a = con[i], b = con[i + 1], pa = { x: sp3.x - 0.6, z: sp3.z, kind: "dung" }, pb = { x: sp3.x + 0.6, z: sp3.z, kind: "dung" };
      di(a, pa, "Ra nói chuyện giải lao"); di(b, pb, "Ra nói chuyện giải lao");
      for (var k = 0; k < 4; k++) { stay_(a, { ms: 5200, pose: k % 2 ? "listen" : "talk", nhin: pb, text: k % 2 ? "" : CAU_CHAT[Math.floor(Math.random() * CAU_CHAT.length)], tt: "Giải lao" }); stay_(b, { ms: 5200, pose: k % 2 ? "talk" : "listen", nhin: pa, text: k % 2 ? CAU_CHAT[Math.floor(Math.random() * CAU_CHAT.length)] : "", tt: "Giải lao" }); }
      veChoLam(a); veChoLam(b);
    }
    if (con.length % 2 && con.length) { var z1 = con[con.length - 1]; hdDao(z1); veChoLam(z1); }
  }

  // ---------- mô phỏng ----------
  var moPhong = 0;
  var KICH_BAN = [
    { id: "hop", ten: "Họp toàn công ty", mo: "Cả công ty vào phòng họp, lãnh đạo chốt hướng đi" },
    { id: "tet", ten: "Bán hàng dịp Tết", mo: "Kiểm kho, tìm nguồn hàng, xây thông điệp chiến dịch" },
    { id: "ads", ten: "Chạy quảng cáo cuối tuần", mo: "Soát ngân sách ads, đổi mẫu quảng cáo, kiểm chứng" },
    { id: "don", ten: "Xử lý đơn giao trễ", mo: "Kho, vận chuyển và chăm sóc khách phối hợp" },
    { id: "bc", ten: "Báo cáo cuối ngày", mo: "Từng người lấy số liệu rồi báo cáo với giám đốc" },
    { id: "nghi", ten: "Giờ giải lao", mo: "Mọi người ra quầy trà uống nước, ăn bánh, đứng nói chuyện" }
  ];
  function xaoTron(arr) { var r = arr.slice(); for (var i = r.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)), t = r[i]; r[i] = r[j]; r[j] = t; } return r; }
  function kichBan(loai, xs, tat) {
    var ev = [], A = function (i) { return xs[i % xs.length].ten; }, R = function (ms, e) { ev.push([ms, e]); };
    if (loai === "hop") {
      var n = Math.min(tat.length, 14);
      R(0, { k: "run_start", name: "Họp toàn công ty (mô phỏng)" });
      for (var i = 0; i < n; i++) R(600 + i * 800, { k: "join", agent: tat[i].ten });
      var t0 = 600 + n * 800 + 1500;
      R(t0, { k: "talk", agent: "@lead", text: "Chào cả nhà. Hôm nay tôi chốt ba việc ưu tiên của tuần.", ms: 5000, tt: "Chủ trì họp" });
      R(t0 + 6000, { k: "talk", agent: A(0), text: "Doanh số đang tăng, em đề xuất giữ nhịp khuyến mãi tới cuối tuần.", ms: 5500 });
      R(t0 + 12500, { k: "talk", agent: A(1), text: "Tồn kho ổn, hai mã sắp hết em đã báo bộ phận nhập.", ms: 5500 });
      R(t0 + 19000, { k: "talk", agent: A(2), text: "Nội dung tuần này em tập trung video ngắn và bài dạng so sánh.", ms: 5500 });
      R(t0 + 25500, { k: "talk", agent: "@lead", text: "Tốt. Mọi người triển khai, chiều nay báo cáo lại cho tôi.", ms: 5000, tt: "Chốt họp" });
      R(t0 + 32000, { k: "run_end", ok: true });
    } else if (loai === "tet") {
      R(0, { k: "run_start", name: "Bán hàng dịp Tết (mô phỏng)" });
      R(900, { k: "step", agent: A(0), task: "Kiểm tra tồn kho và sức bán" }); R(9000, { k: "tool", agent: A(0), tool: "mcp__pos__orders" });
      R(16000, { k: "step_done", agent: A(0), out: "Tồn kho đủ cho 9 mã bán chạy, 2 mã sắp hết cần nhập thêm." });
      R(17000, { k: "step", agent: A(1), task: "Lập phương án nguồn hàng" }); R(22000, { k: "tool", agent: A(1), tool: "WebSearch" });
      R(29000, { k: "step_done", agent: A(1), out: "Đề xuất nhập thêm 2 mã từ nhà cung cấp gần nhất, về trong 3 ngày." });
      R(30000, { k: "step", agent: A(2), task: "Xây thông điệp chiến dịch" }); R(36000, { k: "verify", agent: A(3), target: A(2) });
      R(43000, { k: "step_done", agent: A(2), out: "Thông điệp chính: Quà Tết đẹp, giao nhanh, đổi trả dễ." }); R(51000, { k: "run_end", ok: true });
    } else if (loai === "ads") {
      R(0, { k: "run_start", name: "Quảng cáo cuối tuần (mô phỏng)" });
      R(900, { k: "step", agent: A(0), task: "Soát ngân sách và ROAS các chiến dịch" }); R(8000, { k: "tool", agent: A(0), tool: "mcp__facebook-ads__insights" });
      R(15000, { k: "step_done", agent: A(0), out: "Hai chiến dịch ROAS trên 5, một chiến dịch đang đốt tiền, nên tạm dừng." });
      R(16000, { k: "step", agent: A(1), task: "Viết ba mẫu quảng cáo mới" }); R(22000, { k: "tool", agent: A(1), tool: "mcp__pos__products" });
      R(29000, { k: "step_done", agent: A(1), out: "Đã có ba mẫu quảng cáo, nhấn vào giao nhanh và quà tặng kèm." });
      R(30000, { k: "verify", agent: A(2), target: A(1) }); R(38000, { k: "run_end", ok: true });
    } else if (loai === "don") {
      R(0, { k: "run_start", name: "Xử lý đơn giao trễ (mô phỏng)" });
      R(900, { k: "step", agent: A(0), task: "Lọc các đơn giao trễ trên hệ thống" }); R(8000, { k: "tool", agent: A(0), tool: "mcp__pos__orders" });
      R(15000, { k: "step_done", agent: A(0), out: "Có 7 đơn trễ quá 2 ngày, 4 đơn thuộc cùng một đơn vị vận chuyển." });
      R(16000, { k: "step", agent: A(1), task: "Làm việc với đơn vị vận chuyển" }); R(22000, { k: "tool", agent: A(1), tool: "WebSearch" });
      R(28000, { k: "step_done", agent: A(1), out: "Đơn vị vận chuyển cam kết giao trong ngày mai, đền phí cho 4 đơn." });
      R(29000, { k: "step", agent: A(2), task: "Nhắn xin lỗi và báo lịch giao mới cho khách" }); R(35000, { k: "tool", agent: A(2), tool: "mcp__zalo__send" });
      R(41000, { k: "step_done", agent: A(2), out: "Đã nhắn cả 7 khách, kèm mã giảm cho lần mua sau." }); R(46000, { k: "run_end", ok: true });
    } else {
      var m = Math.min(tat.length, 6);
      R(0, { k: "run_start", name: "Báo cáo cuối ngày (mô phỏng)" });
      for (var q = 0; q < m; q++) {
        R(1000 + q * 6500, { k: "step", agent: tat[q].ten, task: "Tổng hợp số liệu trong ngày" });
        R(3500 + q * 6500, { k: "tool", agent: tat[q].ten, tool: q % 2 ? "mcp__ads__report" : "mcp__pos__orders" });
      }
      for (var w = 0; w < Math.min(m, 3); w++) R(1000 + m * 6500 + w * 6000, { k: "talk", agent: tat[w].ten, text: ["Doanh thu hôm nay đạt 92% mục tiêu ngày.", "Chi phí quảng cáo thấp hơn hôm qua, đơn mới tăng.", "Còn 3 khiếu nại đang xử lý, dự kiến xong trong ngày."][w], ms: 5000, tt: "Báo cáo kết quả" });
      R(1000 + m * 6500 + 19000, { k: "talk", agent: "@lead", text: "Cảm ơn mọi người. Hẹn sáng mai.", ms: 4000, tt: "Chốt ngày" });
      R(1000 + m * 6500 + 24500, { k: "run_end", ok: true });
    }
    return ev;
  }
  function chayMau(loai) {
    var tat = xaoTron(ds.filter(function (x) { return !x.lead; })), xs = tat.slice(0, 4);
    if (typeof loai !== "string" || loai === "rand") loai = KICH_BAN[Math.floor(Math.random() * KICH_BAN.length)].id;
    if (loai === "hop") { hopToanCty(); return; }
    if (loai === "nghi") { gioGiaiLao(); return; }
    if (xs.length < 2) { toast("Brain này chưa có agent nào để mô phỏng. Hãy tạo vài agent ở trang Cộng sự."); return; }
    var id = "demo" + (++moPhong);
    kichBan(loai, xs, tat).forEach(function (e) { e[1].run = id; setTimeout(function () { if (mo) suKien(e[1]); }, e[0]); });
    var ten = KICH_BAN.filter(function (k) { return k.id === loai; })[0]; if (ten) toast("Đang mô phỏng: " + ten.ten);
  }
  function toast(t) {
    var el = $("mmOfficeToast"); if (!el) return; el.textContent = t; el.hidden = false;
    clearTimeout(toast.h); toast.h = setTimeout(function () { el.hidden = true; }, 5000);
  }

  // ---------- chạy mỗi khung hình ----------
  function viTriDi(x, z, c) {                  // chỗ đứng có hợp lệ không (gần điểm đầu/cuối thì được phép)
    if (Math.abs(x) > GX - 0.6 || Math.abs(z) > HZ - 0.6 || trongTuong(x, z)) return false;
    var f0 = c.from0 || c.from;
    if (Math.hypot(x - c.to.x, z - c.to.z) < 0.75 || Math.hypot(x - f0.x, z - f0.z) < 0.6) return true;
    return !blocked[gj(z) * GW + gi(x)];
  }
  function banDo() { return ds.concat(lead ? [lead] : [], nvPhong); }
  function buoc(a, dt, t) {
    var r = a.r, c = a.cur, speed = r.hum ? 1.9 : 3.3;
    if (!c) {
      c = a.cur = a.q.shift() || null;
      if (c) {
        if (c.t === "stay") { c.het = now() + c.ms; if (c.text) noi_(a, c.text, c.ms); if (c.tt) trangThai(a, c.tt); if (c.speak) nguoiNoi = a; }
        else if (c.t === "walk") {
          c.from = { x: a.x, z: a.z }; c.from0 = c.from; c.path = timDuong(a.x, a.z, c.to.x, c.to.z, a); c.i = 0; a.walking = true; c.moc = now(); c.mx = a.x; c.mz = a.z;
          if (c.label) trangThai(a, c.label);
        } else if (c.t === "ngoi" || c.t === "rave") { c.tm = 0; c.fx = a.x; c.fz = a.z; a.walking = true; c.s.ct = 1; }
        else if (c.t === "say") { noi_(a, c.text, c.ms); a.cur = null; return buoc(a, dt, t); }
        else if (c.t === "call") { a.cur = null; c.fn(a); return buoc(a, dt, t); }
      }
    }
    var dang = a.holdPose, sw = 0, dungDay = 0;
    a.item = (c && c.t === "stay" && c.item) || null; a.diemPt = (c && c.t === "stay" && c.diem) || null;
    if (c) {
      if (c.t === "walk") {
        var p = c.path[c.i];
        if (!p) { a.cur = null; a.walking = false; a.kind = c.kind; }
        else {
          var dx = p.x - a.x, dz = p.z - a.z, d = Math.hypot(dx, dz) || 1, st = speed * dt, vx = dx / d, vz = dz / d, sx = 0, sz = 0, tCua = Math.abs(Math.abs(a.x) - HX) < 1.7 && Math.abs(a.z) < DOOR + 1.3;
          if (!tCua) banDo().forEach(function (o) {            // tránh nhau: đẩy ra khỏi người đang ở gần (qua cửa thì đi thẳng, không đẩy nhau)
            if (o === a) return; var ox = a.x - o.x, oz = a.z - o.z, od = Math.hypot(ox, oz);
            if (od < 1.0 && od > 0.001) { var w = (1.0 - od) / 1.0; sx += ox / od * w; sz += oz / od * w; }
          });
          vx += sx * 1.8; vz += sz * 1.8; var vl = Math.hypot(vx, vz) || 1; vx /= vl; vz /= vl;
          var nx = a.x + vx * st, nz = a.z + vz * st;
          if (!viTriDi(nx, nz, c)) {
            nx = a.x + dx / d * st; nz = a.z + dz / d * st;
            if (!viTriDi(nx, nz, c)) {                  // trượt dọc theo vật cản thay vì đứng im ở góc
              var ex = a.x + Math.sign(dx) * st, ez = a.z + Math.sign(dz) * st;
              if (viTriDi(ex, a.z, c)) { nx = ex; nz = a.z; } else if (viTriDi(a.x, ez, c)) { nx = a.x; nz = ez; } else { nx = a.x; nz = a.z; }
            }
          }
          if (Math.hypot(nx - a.x, nz - a.z) < st * 0.2) { a.ket = (a.ket || 0) + dt; a.ketLau = (a.ketLau || 0) + dt; } else { a.ket = 0; a.ketLau = Math.max(0, (a.ketLau || 0) - dt); }
          if (a.ketLau > 2.2) { a.ketLau = 0; nx = p.x; nz = p.z; }                // kẹt quá lâu (nhất là ở cửa): nhảy tới điểm tiếp theo
          if (a.ket > 0.6) { a.ket = 0; c.from = { x: a.x, z: a.z }; c.path = timDuong(a.x, a.z, c.to.x, c.to.z, a); c.i = 0; if (c.path.length > 1 && Math.hypot(c.path[0].x - a.x, c.path[0].z - a.z) < 0.05) c.i = 1; }
          a.x = nx; a.z = nz; a.huongDich = Math.atan2(vx, vz);
          if (Math.hypot(p.x - a.x, p.z - a.z) < Math.max(0.18, st)) { a.x = p.x; a.z = p.z; c.i++; if (c.i >= c.path.length) { a.cur = null; a.walking = false; a.kind = c.kind; } }
          if (now() - c.moc > 1600) {              // kẹt: chưa nhúc nhích bao nhiêu thì tìm đường lại
            if (Math.hypot(a.x - c.mx, a.z - c.mz) < 0.35) { c.from = { x: a.x, z: a.z }; c.path = timDuong(a.x, a.z, c.to.x, c.to.z, a); c.i = 0; }
            c.moc = now(); c.mx = a.x; c.mz = a.z;
          }
        }
        dang = "walk"; sw = Math.sin(t * 11);
      } else if (c.t === "stay") {
        if (c.nhin) a.huongDich = Math.atan2(c.nhin.x - a.x, c.nhin.z - a.z);
        dang = c.pose; if (c.stand) dungDay = 1; if (now() >= c.het) { a.cur = null; if (c.speak && nguoiNoi === a) nguoiNoi = null; }
      } else if (c.t === "ngoi") {                  // kéo ghế ra, bước vào, kéo ghế vào rồi ngồi
        var sg1 = c.s; c.tm += dt; a.huongDich = sg1.rot; dang = "idle"; a.walking = true;
        if (c.tm > 0.7) { var u1 = Math.min(1, (c.tm - 0.7) / 1.1), e1 = u1 * u1 * (3 - 2 * u1); a.x = lerp(c.fx, sg1.x, e1); a.z = lerp(c.fz, sg1.z, e1); dang = "walk"; sw = Math.sin(t * 8); if (u1 > 0.45) sg1.ct = 0; }
        if (c.tm >= 2.1) { a.x = sg1.x; a.z = sg1.z; sg1.ct = 0; a.walking = false; a.kind = "seat"; a.cur = null; }
      } else if (c.t === "rave") {                  // đứng dậy, kéo ghế ra, bước ra, đẩy ghế vào
        var sg2 = c.s; c.tm += dt; dang = "idle"; a.walking = true; a.huongDich = sg2.rot + Math.PI;
        if (c.tm > 0.5) { var u2 = Math.min(1, (c.tm - 0.5) / 1.0), e2 = u2 * u2 * (3 - 2 * u2); a.x = lerp(sg2.x, sg2.sx, e2); a.z = lerp(sg2.z, sg2.sz, e2); dang = "walk"; sw = Math.sin(t * 8); if (u2 > 0.6) sg2.ct = 0; }
        if (c.tm >= 1.8) { a.x = sg2.sx; a.z = sg2.sz; sg2.ct = 0; a.walking = false; a.kind = "dung"; a.cur = null; }
      } else if (c.t === "face") { a.huongDich = c.huong; a.cur = null; }
      else if (c.t === "hold") {
        if (c.doi) { c.tdoi = (c.tdoi == null ? ngau(1, 8) : c.tdoi) - dt; if (c.tdoi <= 0) { c.pose = c.doi[Math.floor(Math.random() * c.doi.length)]; c.tdoi = ngau(5, 12); } }
        dang = c.pose; a.holdPose = c.pose; if (c.tt) trangThai(a, c.tt); if (a.q.length) a.cur = null;
      }
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
    if (anChu) { r.noi.visible = false; r.nhan.visible = false; } else r.nhan.visible = true;
  }

  var camLuu = null;
  var canhTuong = [], canhSan = [], giuBang = [], khongGian = 0; try { khongGian = Math.max(0, Math.min(2, parseInt(localStorage.getItem("mmOfficeKG") || "0", 10) || 0)); } catch (e) {}
  function apKhongGian() { canhTuong.forEach(function (o) { o.visible = khongGian === 0; }); canhSan.forEach(function (o) { o.visible = khongGian < 2; }); }
  var anChu = false; try { anChu = localStorage.getItem("mmOfficeAnChu") === "1"; } catch (e) {}
  var lastManHinh = 0, lastAnh = 0;
  function khung() {
    rafId = requestAnimationFrame(khung);
    var n = now(), dt = Math.min(0.05, (n - lanCuoi) / 1000) * (window.__mmOfficeSpeed || 1); lanCuoi = n; tNow += dt; var t = tNow; phimCam(dt);
    var vua = host.clientWidth, cao = host.clientHeight;
    if (renderer.domElement.width !== Math.floor(vua * renderer.getPixelRatio()) || renderer.domElement.height !== Math.floor(cao * renderer.getPixelRatio())) {
      renderer.setSize(vua, cao, false); camera.aspect = vua / Math.max(1, cao);
      camera.fov = camera.aspect < 0.8 ? 52 : 38; camera.updateProjectionMatrix();
    }
    if (n - lastManHinh > 200) { lastManHinh = n; veManHinh(t); }
    ds.forEach(function (a) { buoc(a, dt, t); }); if (lead) buoc(lead, dt, t); nvPhong.forEach(function (a) { buoc(a, dt, t); });
    capNhatCua(dt); capNhatGhe(dt); quayDoi(dt); if (n - lastAnh > 8000) { lastAnh = n; apAnhSang(); }
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
    var meshes = []; banDo().forEach(function (a) { meshes.push(a.r.than); });
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
    renderer = scene = camera = null; agents = {}; ds = []; lead = null; tram = []; ban = null; nvPhong = []; vatPhong = []; bangPhong = {}; phien = {}; bang = null; manHinh = []; nguoiNoi = null; cheDo = null; cuaDoi = [];
  }
  function dung(list) {
    xoaCanh();
    cv = document.createElement("canvas"); cv.className = "mm-office-cv"; host.insertBefore(cv, host.firstChild);
    renderer = new T.WebGLRenderer({ canvas: cv, antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 3, Math.max(1, Math.sqrt(9e6 / Math.max(1, host.clientWidth * host.clientHeight)))));
    dungCanh(); dungNguoi(list); nhapTay(); lanCuoi = now(); tNow = 0; khung(); napKpi(); pancakeDL = null; pancakeSig = ""; napPancake();
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
    var dem = fetch("/office/pancake?brain=" + encodeURIComponent(brain())).then(function (r) { return r.json(); }).then(function (d) { return (d && d.staff && d.staff.length) || 11; }).catch(function () { return 11; });
    Promise.all([nap(), mon(), dem]).then(function (r0) {
      return napNguoi(1 + r0[1].length + r0[2]).then(function () { return [r0[0], r0[1]]; });
    }).then(function (r) {
      if (!mo) return;
      if (!r[0]) { toast("Máy này không dựng được cảnh 3D"); dong(); return; }
      try { dung(r[1]); } catch (e) { console.warn("[office]", e); toast("Không dựng được văn phòng 3D"); dong(); return; }
      if (camLuu) { cam.az = camLuu.az; cam.pol = camLuu.pol; cam.dist = camLuu.dist; cam.tx = camLuu.tx; cam.ty = camLuu.ty; cam.tz = camLuu.tz; camLuu = null; }
      seq = 0; hoi(); pollId = setInterval(hoi, 1500); kpiId = setInterval(function () { napKpi(); napPancake(); }, 60000);
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
      '<button type="button" id="mmOfficeSim" aria-haspopup="true">Mô phỏng</button><button type="button" id="mmOfficeKG">Ẩn tường</button><button type="button" data-room="-24">Phòng Sale</button><button type="button" data-room="0">Văn phòng</button><button type="button" data-room="24">Phòng Marketing</button><button type="button" id="mmOfficeTheme">Chế độ tối</button><button type="button" id="mmOfficeRefresh" title="MinMin lấy số mới từ Pancake và Meta Ads rồi ghi vào các bảng">Làm mới bảng</button><button type="button" id="mmOfficeTag" aria-pressed="false">Ẩn chữ</button><button type="button" id="mmOfficeFs">Toàn màn hình</button><button type="button" id="mmOfficeWin">Cửa sổ riêng</button><button type="button" id="mmOfficeX" aria-label="Đóng văn phòng">Đóng</button></div>' +
      '<div class="mm-office-simmenu" id="mmOfficeSimMenu" hidden></div><div class="mm-office-card" id="mmOfficeCard" hidden></div><div class="mm-office-toast" id="mmOfficeToast" hidden></div>';
    root.appendChild(host);
    var nut = document.createElement("button");
    nut.id = "officeToggleBtn"; nut.type = "button"; nut.className = "brain-overlay-toggle mm-office-btn";
    nut.setAttribute("aria-pressed", "false"); nut.title = "Văn phòng AI 3D: xem các agent đang làm việc"; nut.setAttribute("aria-label", "Mở văn phòng AI 3D");
    nut.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="9" width="14" height="9" rx="3"></rect><circle cx="9.5" cy="13.5" r="1"></circle><circle cx="14.5" cy="13.5" r="1"></circle><path d="M12 9V6M10 6h4M3 13v2M21 13v2"></path></svg>';
    root.appendChild(nut);
    nut.addEventListener("click", function () { mo ? dong() : mo_(); });
    $("mmOfficeX").addEventListener("click", dong);
    var menuSim = $("mmOfficeSimMenu");
    KICH_BAN.concat([{ id: "rand", ten: "Ngẫu nhiên", mo: "Máy chọn một kịch bản bất kỳ" }]).forEach(function (k) {
      var b = document.createElement("button"); b.type = "button"; b.innerHTML = "<b></b><span></span>"; b.firstChild.textContent = k.ten; b.lastChild.textContent = k.mo;
      b.addEventListener("click", function () { menuSim.hidden = true; chayMau(k.id); }); menuSim.appendChild(b);
    });
    $("mmOfficeSim").addEventListener("click", function () { menuSim.hidden = !menuSim.hidden; });
    Array.prototype.forEach.call(host.querySelectorAll("[data-room]"), function (b) {
      b.addEventListener("click", function () { var x = parseFloat(b.getAttribute("data-room")); cam.tx = x; cam.tz = x ? 1.5 : 1.0; cam.ty = 0.6; cam.az = x ? (x < 0 ? -0.35 : 0.35) : -0.62; cam.pol = 0.95; cam.dist = (x ? 27 : 37) * Math.max(1, 1.6 / (camera ? camera.aspect : 1.6)); giuCam(); });
    });
    var nutKG = $("mmOfficeKG"), TEN_KG = ["Ẩn tường", "Ẩn cả nhà", "Hiện nhà"];
    function veNutKG() { nutKG.textContent = TEN_KG[khongGian]; nutKG.title = ["Đang hiện đủ nhà. Bấm để ẩn tường và bảng", "Đang ẩn tường. Bấm để ẩn cả sàn, chỉ còn người và đồ", "Đang chỉ hiện người và đồ. Bấm để hiện lại nhà"][khongGian]; }
    veNutKG();
    nutKG.addEventListener("click", function () { khongGian = (khongGian + 1) % 3; try { localStorage.setItem("mmOfficeKG", String(khongGian)); } catch (e) {} apKhongGian(); veNutKG(); });
    // ô giao việc: gõ ngay trong văn phòng (kể cả toàn màn hình, điện thoại) để vừa giao việc vừa xem agent làm
    if (!window.__mmOfficeSolo) {
      var dock = document.createElement("form"); dock.className = "mm-office-dock"; dock.autocomplete = "off";
      dock.innerHTML = '<button type="button" class="mm-dock-t" aria-expanded="false">Giao việc</button><div class="mm-dock-b" hidden><input type="text" id="mmDockIn" placeholder="Giao việc cho MinMin..." enterkeyhint="send" autocomplete="off"><button type="submit">Gửi</button></div>';
      host.appendChild(dock);
      var dt = dock.querySelector(".mm-dock-t"), db = dock.querySelector(".mm-dock-b"), di_ = $("mmDockIn");
      dt.addEventListener("click", function () { var open = db.hidden; db.hidden = !open; dt.setAttribute("aria-expanded", open ? "true" : "false"); dock.classList.toggle("open", open); if (open) setTimeout(function () { di_.focus(); }, 30); });
      dock.addEventListener("submit", function (e) {
        e.preventDefault(); var t = di_.value.trim(); if (!t) return;
        if (typeof window.sendMessage !== "function" && typeof sendMessage !== "function") { toast("Chưa gửi được: khung chat chưa sẵn sàng."); return; }
        di_.value = ""; try { (window.sendMessage || sendMessage)(t); toast("Đã giao việc. Xem nhân viên vào họp và làm việc."); } catch (x) { toast("Không gửi được: " + (x && x.message || "lỗi")); }
      });
    }
    document.addEventListener("click", function (e) { if (!menuSim.hidden && !(e.target.closest && (e.target.closest("#mmOfficeSimMenu") || e.target.closest("#mmOfficeSim")))) menuSim.hidden = true; });
    var nutTheme = $("mmOfficeTheme");
    function veNutTheme() { nutTheme.textContent = sang() ? "Chế độ tối" : "Chế độ sáng"; host.classList.toggle("mm-light", sang()); host.classList.toggle("mm-dark", !sang()); }
    veNutTheme();
    nutTheme.addEventListener("click", function () {
      themeOv = sang() ? "dark" : "light"; try { localStorage.setItem("mmOfficeTheme", themeOv); } catch (e) {} veNutTheme();
      if (mo) { camLuu = { az: cam.az, pol: cam.pol, dist: cam.dist, tx: cam.tx, ty: cam.ty, tz: cam.tz }; dong(); mo_(); }
    });
    // thanh điều hướng cho điện thoại: giữ nút để đi / xoay / phóng
    var pad = document.createElement("div"); pad.className = "mm-office-pad";
    function nutPad(cls, k, nhan, tit) {
      var b = document.createElement("button"); b.type = "button"; b.className = cls; b.title = tit; b.setAttribute("aria-label", tit); b.textContent = nhan;
      function on(e) { e.preventDefault(); phim[k] = true; try { b.setPointerCapture(e.pointerId); } catch (x) {} b.classList.add("on"); }
      function off() { phim[k] = false; b.classList.remove("on"); }
      b.addEventListener("pointerdown", on); b.addEventListener("pointerup", off); b.addEventListener("pointercancel", off); b.addEventListener("pointerleave", off); b.addEventListener("contextmenu", function (e) { e.preventDefault(); });
      return b;
    }
    var dp = document.createElement("div"); dp.className = "mm-pad-dir";
    dp.appendChild(nutPad("u", "arrowup", "\u25B2", "Đi tới")); dp.appendChild(nutPad("l", "arrowleft", "\u25C0", "Sang trái")); dp.appendChild(nutPad("r", "arrowright", "\u25B6", "Sang phải")); dp.appendChild(nutPad("d", "arrowdown", "\u25BC", "Lùi lại"));
    var zp = document.createElement("div"); zp.className = "mm-pad-zoom";
    zp.appendChild(nutPad("", "+", "+", "Phóng to")); zp.appendChild(nutPad("", "-", "\u2212", "Thu nhỏ")); zp.appendChild(nutPad("", "q", "\u21BA", "Xoay trái")); zp.appendChild(nutPad("", "e", "\u21BB", "Xoay phải"));
    pad.appendChild(zp); pad.appendChild(dp); host.appendChild(pad);
    var nutTag = $("mmOfficeTag");
    function veNutTag() { nutTag.textContent = anChu ? "Hiện chữ" : "Ẩn chữ"; nutTag.setAttribute("aria-pressed", anChu ? "true" : "false"); }
    veNutTag();
    nutTag.addEventListener("click", function () { anChu = !anChu; try { localStorage.setItem("mmOfficeAnChu", anChu ? "1" : "0"); } catch (e) {} veNutTag(); });
    // Nút "Làm mới bảng": báo server chạy NGAY việc định kỳ làm mới số liệu, rồi hỏi lại bảng mỗi 12 giây tới khi có số mới.
    var nutLM = $("mmOfficeRefresh");
    function mocBang() { return ((kpiDuLieu && kpiDuLieu.updated) || "") + "|" + ((pancakeDL && pancakeDL.updated) || ""); }
    nutLM.addEventListener("click", function () {
      if (nutLM.disabled) return;
      var moc = mocBang(), t = 0;
      function xong(m) { if (t) clearInterval(t); nutLM.disabled = false; nutLM.textContent = "Làm mới bảng"; if (m) toast(m); }
      nutLM.disabled = true; nutLM.textContent = "Đang gọi MinMin…";
      fetch("/office/lam-moi?brain=" + encodeURIComponent(brain()), { method: "POST" }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d || !d.ok) { xong((d && d.error) || "Không làm mới được."); return; }
        toast(d.dung_viec_dinh_ky ? "MinMin đang lấy số mới, bảng tự đổi khi xong (thường 1 đến 3 phút)." : "MinMin đang lấy số mới. Chưa thấy việc định kỳ nên dùng lệnh mặc định.");
        nutLM.textContent = "Đang lấy số…";
        var lan = 0;
        t = setInterval(function () {
          lan++; napKpi(); napPancake();
          if (lan > 1 && mocBang() !== moc) xong("Bảng đã có số mới.");
          else if (lan >= 20) xong("Chưa thấy số mới sau 4 phút. Xem kết quả ở trang Việc định kỳ.");
        }, 12000);
      }).catch(function () { xong("Không gọi được máy chủ, thử lại sau."); });
    });
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
    nv: function () { return NV; }, ag: function () { return agents; }, chay: function (id) { chayMau(id); }, sc: function () { return scene; }, lead: function () { return lead; }, cam: cam, dsAll: function () { return banDo(); },
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
    demo: chayMau, kg: function (v) { khongGian = v; apKhongGian(); }, kichBan: KICH_BAN, cam: cam
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", khoiTao); else khoiTao();
})();
