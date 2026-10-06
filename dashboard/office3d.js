// ============================================================================
// MinMin OS - VĂN PHÒNG AI 3D (khoang não, 26.10.85).
//
// Các agent của brain là robot đứng trong một văn phòng 3D chạy trực tiếp theo việc thật:
//  - workflow chạy tới bước nào, robot của agent đó tới bàn người làm bước trước để HỎI LẤY kết quả;
//  - agent gọi công cụ (đọc brain, MCP, web, lệnh) thì đi tới TRẠM DỮ LIỆU tương ứng;
//  - người kiểm chứng đi tới bàn người vừa làm xong;
//  - lần chạy kết thúc có từ 2 agent trở lên thì cả nhóm vào BÀN HỌP chốt kết quả.
// Sự kiện lấy từ GET /office/events (server/office_bus.py), mỗi 1,5 giây khi văn phòng đang mở,
// cộng thêm công cụ MinMin gọi trong khung chat (app.js gọi MinMinOffice.onChatTool).
// Nút "Mô phỏng" chạy một tình huống mẫu để xem khi chưa có việc thật.
// Dùng three.js bản có sẵn của Hub (/static/hud/vendor), nạp khi mở lần đầu. Không có WebGL thì
// nút tự ẩn. Kéo để xoay, cuộn / chụm để phóng, chạm robot để xem việc nó đang làm.
// ============================================================================
(function () {
  "use strict";
  if (typeof window === "undefined" || window.MinMinOffice) return;

  var THREE_URL = "/static/hud/vendor/three.module.min.js";
  var T = null;                       // module three, có sau khi nạp
  var host = null, cv = null, renderer = null, scene = null, camera = null;
  var rafId = 0, pollId = 0, seq = 0, mo = false, daDung = false, lanCuoi = 0;
  var agents = {};                    // khoá = tên viết thường -> robot
  var ds = [];                        // danh sách robot theo thứ tự bàn
  var lead = null;                    // MinMin (tổng chỉ huy)
  var runs = {};                      // run -> { agents: {tên:1} }
  var tram = [];                      // các trạm dữ liệu
  var ban = null;                     // bàn họp
  var cam = { az: 0.0, pol: 0.95, zoom: 1, tx: 0.9, tz: 0.6 };
  var pick = null, raycaster = null, chon = null;
  var giamCD = false;
  try { giamCD = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}

  function brain() { try { return (window.currentBrainPath && window.currentBrainPath()) || "brain"; } catch (e) { return "brain"; } }
  function sang() { try { return window.MinMinGalaxyIsLight ? window.MinMinGalaxyIsLight() : true; } catch (e) { return true; } }
  function now() { return performance.now(); }
  function $(id) { return document.getElementById(id); }
  function hue(s) { var h = 0; for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360; return h; }
  function cat(s, n) { s = String(s || "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  // ---------- bố cục ----------
  var AISLE = 3.5, DESK_Z = 6.3, STAND_Z = 4.8, CORR_X = -9.8;
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
      var t = tram[i];
      return { st: t, nhan: i === 1 && mcp ? mcp[1].replace(/_/g, " ") : t.def.ten };
    }
    return { st: tram[3], nhan: tram[3].def.ten };
  }

  // ---------- đường đi: theo hành lang để không xuyên bàn ----------
  function dau(z) { return z >= 0 ? 1 : -1; }
  function route(from, to) {
    var aF = dau(from.z) * AISLE, aT = dau(to.z) * AISLE, p = [];
    p.push({ x: from.x, z: aF });
    if (aF !== aT) { p.push({ x: CORR_X, z: aF }); p.push({ x: CORR_X, z: aT }); }
    p.push({ x: to.x, z: aT }); p.push({ x: to.x, z: to.z });
    return p;
  }

  // ---------- chữ trên sprite ----------
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
  function rr(g, x, y, w, h, r) { g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r); g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath(); }
  function spriteTu(canvas, sx) {
    var tex = new T.CanvasTexture(canvas); tex.colorSpace = T.SRGBColorSpace;
    var sp = new T.Sprite(new T.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, depthTest: false }));
    sp.scale.set(sx, sx * canvas.height / canvas.width, 1); sp.renderOrder = 10; return sp;
  }
  function capNhatSprite(sp, canvas) { sp.material.map.image = canvas; sp.material.map.needsUpdate = true; }

  // ---------- robot ----------
  function mat(c, o) { return new T.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.55, metalness: 0.05 }, o || {})); }
  function dungRobot(ten, role, mauHue, laLead) {
    var g = new T.Group(), s = laLead ? 1.18 : 1;
    var acc = new T.Color().setHSL(mauHue / 360, 0.75, sang() ? 0.5 : 0.62);
    var trang = mat(sang() ? 0xf4f7fb : 0xdfe7f3), toi = mat(0x1a2233, { roughness: 0.3, metalness: 0.2 });
    var than = new T.Mesh(new T.CapsuleGeometry(0.4, 0.45, 6, 14), trang); than.position.y = 0.95; g.add(than);
    var nguc = new T.Mesh(new T.BoxGeometry(0.34, 0.2, 0.06), mat(acc.getHex(), { emissive: acc.getHex(), emissiveIntensity: 0.55 })); nguc.position.set(0, 1.0, 0.4); g.add(nguc);
    var dau_ = new T.Group(); dau_.position.y = 1.78; g.add(dau_);
    var cau = new T.Mesh(new T.SphereGeometry(0.46, 24, 18), trang); dau_.add(cau);
    var kinh = new T.Mesh(new T.SphereGeometry(0.4, 20, 14), toi); kinh.scale.set(1, 0.62, 0.55); kinh.position.set(0, 0.02, 0.28); dau_.add(kinh);
    var matM = mat(0x9ff3ff, { emissive: 0x6fe6ff, emissiveIntensity: 1.2 });
    [-0.14, 0.14].forEach(function (x) { var e = new T.Mesh(new T.SphereGeometry(0.06, 10, 8), matM); e.scale.set(1, 1.3, 0.6); e.position.set(x, 0.03, 0.46); dau_.add(e); });
    var anten = new T.Mesh(new T.CylinderGeometry(0.02, 0.02, 0.25, 6), toi); anten.position.y = 0.55; dau_.add(anten);
    var bi = new T.Mesh(new T.SphereGeometry(0.06, 10, 8), mat(acc.getHex(), { emissive: acc.getHex(), emissiveIntensity: 0.9 })); bi.position.y = 0.7; dau_.add(bi);
    function tay(x) { var p = new T.Group(); p.position.set(x, 1.3, 0); var t = new T.Mesh(new T.CapsuleGeometry(0.1, 0.42, 4, 8), trang); t.position.y = -0.28; p.add(t); g.add(p); return p; }
    var tayT = tay(-0.52), tayP = tay(0.52);
    function chan(x) { var p = new T.Group(); p.position.set(x, 0.55, 0); var t = new T.Mesh(new T.CapsuleGeometry(0.12, 0.3, 4, 8), toi); t.position.y = -0.28; p.add(t); g.add(p); return p; }
    var chanT = chan(-0.2), chanP = chan(0.2);
    var bong = new T.Mesh(new T.CircleGeometry(0.62, 20), new T.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.16, depthWrite: false }));
    bong.rotation.x = -Math.PI / 2; bong.position.y = 0.02; g.add(bong);
    if (laLead) { var vong = new T.Mesh(new T.TorusGeometry(0.62, 0.035, 8, 40), mat(0xffb020, { emissive: 0xffb020, emissiveIntensity: 0.8 })); vong.rotation.x = Math.PI / 2; vong.position.y = 0.05; g.add(vong); }
    g.scale.setScalar(s);
    var nhan = spriteTu(veNhan(ten, role, "#" + acc.getHexString(), sang() ? "rgba(255,255,255,0.94)" : "rgba(18,28,46,0.92)"), 2.5);
    nhan.position.set(0, 3.15 * s, 0); g.add(nhan);
    var noi = spriteTu(veNhan("", "", "#" + acc.getHexString(), "rgba(255,255,255,0)"), 3.4); noi.position.set(0, 4.0 * s, 0); noi.visible = false; g.add(noi);
    g.userData.robot = true;
    return { g: g, dau: dau_, tayT: tayT, tayP: tayP, chanT: chanT, chanP: chanP, than: than, matM: matM, nhan: nhan, noi: noi, acc: acc, s: s };
  }

  function taoAgent(ten, role, laLead, homeX, homeZ, huong) {
    var r = dungRobot(ten, cat(role, 24), hue(ten), laLead);
    var a = { ten: ten, role: role || "", r: r, lead: !!laLead, home: { x: homeX, z: homeZ }, huong: huong || 0,
              x: homeX, z: homeZ, rot: huong || 0, q: [], cur: null, pose: "idle", task: "", noiHet: 0, man: null, trang: "Rảnh" };
    r.g.position.set(homeX, 0, homeZ); r.g.rotation.y = a.rot; r.than.userData.agent = a;
    scene.add(r.g);
    return a;
  }

  function dungBan(x, z, huong, a) {
    var g = new T.Group(); g.position.set(x, 0, z); g.rotation.y = huong;
    var go = mat(sang() ? 0xdfe6f2 : 0x2a3a58);
    var mat_ = new T.Mesh(new T.BoxGeometry(2.6, 0.12, 1.3), go); mat_.position.set(0, 1.0, 0); g.add(mat_);
    [[-1.2, -0.55], [1.2, -0.55], [-1.2, 0.55], [1.2, 0.55]].forEach(function (p) { var ch = new T.Mesh(new T.BoxGeometry(0.1, 1.0, 0.1), mat(0x8fa0b8)); ch.position.set(p[0], 0.5, p[1]); g.add(ch); });
    var mh = mat(0x0f1626, { emissive: 0x1a4fff, emissiveIntensity: 0.15 });
    var mon = new T.Mesh(new T.BoxGeometry(1.1, 0.7, 0.06), mh); mon.position.set(0, 1.62, -0.35); g.add(mon);
    var ch2 = new T.Mesh(new T.BoxGeometry(0.1, 0.35, 0.1), mat(0x8fa0b8)); ch2.position.set(0, 1.2, -0.35); g.add(ch2);
    a.man = mh;
    scene.add(g);
  }

  function dungTram(def, i) {
    var g = new T.Group(), x = 11.2; g.position.set(x, 0, def.z); g.rotation.y = -Math.PI / 2;
    var acc = new T.Color().setHSL(hue(def.id) / 360, 0.75, 0.52);
    var thung = new T.Mesh(new T.BoxGeometry(1.5, 2.2, 1.0), mat(sang() ? 0xe3e9f4 : 0x23324d)); thung.position.y = 1.1; g.add(thung);
    var den = mat(acc.getHex(), { emissive: acc.getHex(), emissiveIntensity: 0.35 });
    var m = new T.Mesh(new T.BoxGeometry(1.1, 0.7, 0.05), den); m.position.set(0, 1.45, 0.52); g.add(m);
    for (var k = 0; k < 3; k++) { var r = new T.Mesh(new T.BoxGeometry(1.1, 0.12, 0.05), mat(0x8fa0b8)); r.position.set(0, 0.8 - k * 0.22, 0.52); g.add(r); }
    var nh = spriteTu(veNhan(def.ten, "Trạm dữ liệu", "#" + acc.getHexString(), sang() ? "rgba(255,255,255,0.94)" : "rgba(18,28,46,0.92)"), 2.6);
    nh.position.set(0, 3.0, 0); g.add(nh);
    scene.add(g);
    return { def: def, den: den, spot: { x: 9.1, z: def.z }, g: g };
  }

  function dungBanHop() {
    var g = new T.Group();
    var mt = new T.Mesh(new T.CylinderGeometry(2.2, 2.2, 0.14, 40), mat(sang() ? 0xdfe6f2 : 0x2a3a58)); mt.position.y = 1.0; g.add(mt);
    var ch = new T.Mesh(new T.CylinderGeometry(0.4, 0.55, 1.0, 16), mat(0x8fa0b8)); ch.position.y = 0.5; g.add(ch);
    var vong = new T.Mesh(new T.TorusGeometry(2.2, 0.03, 8, 60), mat(0x2a6bff, { emissive: 0x2a6bff, emissiveIntensity: 0.8 })); vong.rotation.x = Math.PI / 2; vong.position.y = 1.08; g.add(vong);
    var holo = new T.Mesh(new T.CylinderGeometry(0.9, 0.9, 0.02, 30), new T.MeshBasicMaterial({ color: 0x3fb2ff, transparent: true, opacity: 0.0 })); holo.position.y = 1.12; g.add(holo);
    scene.add(g);
    var ghe = [];
    for (var i = 0; i < 8; i++) { var an = i / 8 * Math.PI * 2 + 0.3; ghe.push({ x: Math.cos(an) * 3.15, z: Math.sin(an) * 3.15, huong: Math.atan2(-Math.cos(an), -Math.sin(an)) }); }
    return { ghe: ghe, holo: holo };
  }

  // ---------- dựng cảnh ----------
  function dungCanh() {
    var light = sang();
    scene = new T.Scene();
    scene.background = new T.Color(light ? 0xe9f0fa : 0x0d1524);
    scene.fog = new T.Fog(light ? 0xe9f0fa : 0x0d1524, 40, 80);
    scene.add(new T.HemisphereLight(0xffffff, light ? 0xbfcbe0 : 0x1b2740, light ? 1.15 : 0.9));
    var dl = new T.DirectionalLight(0xffffff, light ? 1.4 : 1.0); dl.position.set(-8, 18, 10); scene.add(dl);
    var san = new T.Mesh(new T.BoxGeometry(25, 0.3, 17), mat(light ? 0xf7f9fd : 0x16233a, { roughness: 0.9 })); san.position.y = -0.15; scene.add(san);
    var luoi = new T.GridHelper(25, 25, light ? 0xd5deec : 0x24385a, light ? 0xe4ebf6 : 0x1d2d49); luoi.position.y = 0.01; luoi.scale.z = 17 / 25; scene.add(luoi);
    // viền tường thấp phía sau và bên phải cho có chiều sâu
    var tuong = mat(light ? 0xdde6f4 : 0x1e2d49);
    var t1 = new T.Mesh(new T.BoxGeometry(25, 1.6, 0.3), tuong); t1.position.set(0, 0.8, -8.6); scene.add(t1);
    var t2 = new T.Mesh(new T.BoxGeometry(0.3, 1.6, 17), tuong); t2.position.set(-12.6, 0.8, 0); scene.add(t2);
    var vien = new T.Mesh(new T.BoxGeometry(25, 0.04, 0.12), mat(0x2a6bff, { emissive: 0x2a6bff, emissiveIntensity: 0.6 })); vien.position.set(0, 1.62, -8.6); scene.add(vien);
    tram = STATION_DEFS.map(dungTram);
    ban = dungBanHop();
    camera = new T.PerspectiveCamera(38, 1, 0.1, 200);
    raycaster = new T.Raycaster();
  }

  function datCamera() {
    var cp = Math.cos(cam.pol), sp = Math.sin(cam.pol), dist = 26 * Math.max(1, 1.75 / camera.aspect) * cam.zoom;
    camera.position.set(cam.tx + Math.sin(cam.az) * sp * dist, cp * dist, cam.tz + Math.cos(cam.az) * sp * dist);
    camera.lookAt(cam.tx, 0.6, cam.tz);
  }

  // ---------- đồng bộ danh sách agent ----------
  function boTri(n) {
    // n robot: hai hàng bàn, nửa trên z=-DESK_Z, nửa dưới z=+DESK_Z
    var tren = Math.ceil(n / 2), res = [];
    for (var i = 0; i < n; i++) {
      var hang = i < tren ? -1 : 1, so = hang < 0 ? tren : n - tren, k = hang < 0 ? i : i - tren;
      var x = (k - (so - 1) / 2) * 3.8;
      res.push({ x: x, deskZ: hang * DESK_Z, standZ: hang * STAND_Z, huong: hang < 0 ? 0 : Math.PI });
    }
    return res;
  }
  function dungNguoi(list) {
    list = list.slice(0, 12);
    var bt = boTri(list.length);
    list.forEach(function (ag, i) {
      var p = bt[i], a = taoAgent(ag.name || ag.slug, ag.role, false, p.x, p.standZ, p.huong + Math.PI);   // robot quay mặt về bàn
      dungBan(p.x, p.deskZ, p.huong, a);
      agents[(ag.name || ag.slug).toLowerCase()] = a; if (ag.slug) agents[ag.slug.toLowerCase()] = a;
      ds.push(a);
    });
    lead = taoAgent("MinMin", "Tổng chỉ huy AI", true, 6.2, 0.2, -Math.PI / 2);
    agents["minmin"] = lead;
  }
  function khach(ten) {
    // agent chưa có trong danh sách (mới tạo, hoặc tên khác): thêm vào khu nghỉ bên trái
    var k = ten.toLowerCase(); if (agents[k]) return agents[k];
    var n = Object.keys(agents).length, a = taoAgent(ten, "Khách mời", false, -9.0 + (n % 3) * 1.4, -0.2 + ((n / 3) | 0) * 1.4, Math.PI / 2);
    a.man = null; agents[k] = a; ds.push(a); return a;
  }
  function timAgent(ten) {
    ten = String(ten || "").trim(); if (!ten) return null;
    var k = ten.toLowerCase(); if (agents[k]) return agents[k];
    for (var key in agents) if (key.indexOf(k) >= 0 || k.indexOf(key) >= 0) return agents[key];
    return khach(ten);
  }

  // ---------- điều khiển hành động ----------
  function noi_(a, text, ms) {
    a.noiHet = now() + (ms || 2200);
    capNhatSprite(a.r.noi, veNhan(cat(text, 30), "", "#" + a.r.acc.getHexString(), sang() ? "rgba(255,255,255,0.97)" : "rgba(18,28,46,0.95)"));
    a.r.noi.visible = true;
  }
  function trangThai(a, t) {
    if (a.trang === t) return; a.trang = t;
    capNhatSprite(a.r.nhan, veNhan(a.ten, cat(t, 26), "#" + a.r.acc.getHexString(), sang() ? "rgba(255,255,255,0.94)" : "rgba(18,28,46,0.92)"));
  }
  function di(a, to) { a.q.push({ t: "walk", path: route({ x: a.x, z: a.z }, to) }); }
  function dung_(a, ms, pose, nhin, text, tt) { a.q.push({ t: "stay", ms: ms, pose: pose, nhin: nhin, text: text, tt: tt }); }
  function ve(a, pose, tt) {
    di(a, a.home); a.q.push({ t: "face", huong: a.huong });
    a.q.push({ t: "hold", pose: pose || "idle", tt: tt || (pose === "work" ? "Đang làm" : "Rảnh") });
  }
  function cham(a) { a.q.length = 0; a.cur = null; }
  function canh(a) { return { x: a.home.x + 1.5, z: a.home.z + (a.home.z < 0 ? 0.2 : -0.2) }; }
  function lead_di_toi(a, text) {
    if (!lead) return;
    lead.q.length = 0; lead.cur = null;
    di(lead, canh(a)); dung_(lead, 1600, "talk", a, text, "Giao việc"); ve(lead, "idle", "Điều phối");
  }

  function suKien(ev) {
    var k = ev.k, a, p;
    if (k === "run_start") {
      runs[ev.run] = { agents: {}, ten: ev.name };
      if (lead) { noi_(lead, "Nhận việc: " + cat(ev.name, 18), 3000); trangThai(lead, "Điều phối"); }
    } else if (k === "step") {
      a = timAgent(ev.agent); if (!a) return; var r = runs[ev.run]; if (r) r.agents[a.ten.toLowerCase()] = a;
      p = ev.prev ? timAgent(ev.prev) : null; cham(a);
      if (p && p !== a) {
        di(a, canh(p)); dung_(a, 2000, "talk", p, "Cho em xin kết quả của " + cat(p.ten, 14), "Hỏi " + cat(p.ten, 12));
        p.q.length = 0; p.cur = null; dung_(p, 2000, "talk", a, "Dạ, đây ạ", "Trả lời " + cat(a.ten, 12)); ve(p, "idle", "Rảnh");
      } else if (!p) lead_di_toi(a, "Giao việc: " + cat(ev.task, 18));
      ve(a, "work", cat(ev.task, 26) || "Đang làm");
      a.q.push({ t: "say", text: cat(ev.task, 28) || "Bắt đầu làm", ms: 3200 });
      a.task = ev.task || "";
    } else if (k === "tool") {
      a = timAgent(ev.agent) || lead; if (!a || now() - (a.luotTool || 0) < 2500) return; a.luotTool = now();
      var t = tramCua(ev.tool); a.q.length = 0; a.cur = null;
      di(a, t.st.spot); dung_(a, 2300, "work", null, "Lấy dữ liệu: " + cat(t.nhan, 16), "Lấy dữ liệu " + cat(t.nhan, 10)); t.st.sang = now() + 2600;
      ve(a, a === lead ? "idle" : "work", a === lead ? "Điều phối" : "Đang làm");
    } else if (k === "verify") {
      a = timAgent(ev.agent); p = timAgent(ev.target); if (!a || !p || a === p) return;
      a.q.length = 0; a.cur = null; di(a, canh(p)); dung_(a, 2200, "talk", p, "Kiểm chứng kết quả", "Kiểm chứng " + cat(p.ten, 10));
      p.q.length = 0; p.cur = null; dung_(p, 2200, "talk", a, "Dạ, anh xem giúp", "Trình bày"); ve(p, "work", "Chờ kiểm chứng"); ve(a, "idle", "Rảnh");
    } else if (k === "step_done") {
      a = timAgent(ev.agent); if (!a) return; noi_(a, "Xong bước này", 2000); trangThai(a, "Vừa xong");
    } else if (k === "run_end") {
      var run = runs[ev.run]; delete runs[ev.run]; if (!run) return;
      var ds2 = Object.keys(run.agents).map(function (x) { return run.agents[x]; });
      if (ds2.length < 2) { ds2.forEach(function (x) { cham(x); ve(x, "idle", "Rảnh"); }); if (lead) noi_(lead, ev.ok ? "Xong việc" : "Có lỗi, cần xem lại", 3000); return; }
      hopNhom(ds2, ev.ok, run.ten);
    }
  }
  function hopNhom(list, ok, ten) {
    var seats = ban.ghe, all = list.slice(0, 7); if (lead) all.push(lead);
    all.forEach(function (x, i) {
      var g = seats[i % seats.length]; cham(x);
      di(x, { x: g.x, z: g.z }); x.q.push({ t: "face", huong: g.huong });
      dung_(x, 4200, "talk", null, x === lead ? (ok ? "Chốt kết quả" : "Có lỗi, họp xử lý") : (ok ? "Báo cáo xong" : "Cần xem lại"), "Họp: " + cat(ten, 14));
      ve(x, x === lead ? "idle" : "idle", x === lead ? "Điều phối" : "Rảnh");
    });
    ban.sangDen = now() + 7000;
  }

  // ---------- mô phỏng ----------
  var moPhong = 0;
  function chayMau() {
    var xs = ds.filter(function (x) { return !x.lead; }).slice(0, 4);
    if (xs.length < 2) { toast("Brain này chưa có agent nào để mô phỏng. Hãy tạo vài agent ở trang Cộng sự."); return; }
    var id = "demo" + (++moPhong), tg = 0;
    function at(ms, ev) { setTimeout(function () { if (mo) suKien(ev); }, ms); }
    at(0, { k: "run_start", run: id, name: "Bán hàng dịp Tết" });
    at(900, { k: "step", run: id, agent: xs[0].ten, prev: "", task: "Kiểm tra tồn kho và sức bán" });
    at(3500, { k: "tool", run: id, agent: xs[0].ten, tool: "mcp__pos__orders" });
    at(7500, { k: "step_done", run: id, agent: xs[0].ten });
    at(8000, { k: "step", run: id, agent: xs[1].ten, prev: xs[0].ten, task: "Lập phương án nguồn hàng" });
    at(13000, { k: "tool", run: id, agent: xs[1].ten, tool: "WebSearch" });
    at(17500, { k: "step_done", run: id, agent: xs[1].ten });
    var x3 = xs[2] || xs[0], x4 = xs[3] || xs[1];
    at(18000, { k: "step", run: id, agent: x3.ten, prev: xs[1].ten, task: "Xây thông điệp chiến dịch" });
    at(22000, { k: "verify", run: id, agent: x4.ten, target: x3.ten });
    at(26500, { k: "step_done", run: id, agent: x3.ten });
    at(27500, { k: "run_end", run: id, ok: true });
  }
  function toast(t) {
    var el = $("mmOfficeToast"); if (!el) return; el.textContent = t; el.hidden = false;
    clearTimeout(toast.h); toast.h = setTimeout(function () { el.hidden = true; }, 5000);
  }

  // ---------- chạy mỗi khung hình ----------
  function buoc(a, dt, t) {
    var r = a.r, c = a.cur, speed = 3.4;
    if (!c) {
      c = a.cur = a.q.shift() || null;
      if (c && c.t === "stay") { c.het = now() + c.ms; if (c.text) noi_(a, c.text, c.ms); if (c.tt) trangThai(a, c.tt); }
      if (c && c.t === "walk") { c.i = 0; trangThai(a, "Đang đi"); }
      if (c && c.t === "say") { noi_(a, c.text, c.ms); a.cur = null; return buoc(a, 0, t); }
    }
    var dang = "idle";
    if (c) {
      if (c.t === "walk") {
        var p = c.path[c.i];
        if (!p) { a.cur = null; }
        else {
          var dx = p.x - a.x, dz = p.z - a.z, d = Math.hypot(dx, dz), st = speed * dt;
          if (d <= st) { a.x = p.x; a.z = p.z; c.i++; if (c.i >= c.path.length) a.cur = null; }
          else { a.x += dx / d * st; a.z += dz / d * st; a.huongDich = Math.atan2(dx, dz); }
          dang = "walk";
        }
      } else if (c.t === "stay") {
        if (c.nhin) a.huongDich = Math.atan2(c.nhin.x - a.x, c.nhin.z - a.z);
        dang = c.pose; if (now() >= c.het) a.cur = null;
      } else if (c.t === "face") { a.huongDich = c.huong; a.cur = null; }
      else if (c.t === "hold") { dang = c.pose; a.pose = c.pose; if (c.tt) trangThai(a, c.tt); a.holdPose = c.pose; if (a.q.length) a.cur = null; }
    } else dang = a.holdPose || "idle";
    if (a.huongDich != null) { var dd = a.huongDich - a.rot; while (dd > Math.PI) dd -= Math.PI * 2; while (dd < -Math.PI) dd += Math.PI * 2; a.rot += dd * Math.min(1, dt * 9); }
    r.g.position.set(a.x, 0, a.z); r.g.rotation.y = a.rot;
    // dáng
    var sw = dang === "walk" ? Math.sin(t * 11) : 0, bob = dang === "walk" ? Math.abs(Math.sin(t * 11)) * 0.07 : Math.sin(t * 1.6 + a.x) * 0.012;
    r.than.position.y = 0.95 + bob; r.dau.position.y = 1.78 + bob;
    r.chanT.rotation.x = sw * 0.7; r.chanP.rotation.x = -sw * 0.7;
    var ty = 0, tp = 0;
    if (dang === "walk") { ty = -sw * 0.6; tp = sw * 0.6; }
    else if (dang === "work") { ty = -0.9 + Math.sin(t * 14) * 0.18; tp = -0.9 + Math.sin(t * 14 + 2) * 0.18; }
    else if (dang === "talk") { ty = -0.2; tp = -1.3 + Math.sin(t * 6) * 0.35; r.dau.rotation.x = Math.sin(t * 5) * 0.08; }
    r.tayT.rotation.x += (ty - r.tayT.rotation.x) * 0.25; r.tayP.rotation.x += (tp - r.tayP.rotation.x) * 0.25;
    if (dang !== "talk") r.dau.rotation.x *= 0.85;
    if (a.man) a.man.emissiveIntensity = dang === "work" ? 0.9 + Math.sin(t * 7) * 0.2 : 0.12;
    if (r.noi.visible && now() > a.noiHet) r.noi.visible = false;
  }

  function khung() {
    rafId = requestAnimationFrame(khung);
    var n = now(), dt = Math.min(0.05, (n - lanCuoi) / 1000); lanCuoi = n; var t = n / 1000;
    var vua = host.clientWidth, cao = host.clientHeight;
    if (renderer.domElement.width !== Math.floor(vua * renderer.getPixelRatio()) || renderer.domElement.height !== Math.floor(cao * renderer.getPixelRatio())) {
      renderer.setSize(vua, cao, false); camera.aspect = vua / Math.max(1, cao);
      camera.fov = camera.aspect < 0.8 ? 52 : 38; camera.updateProjectionMatrix();
    }
    ds.forEach(function (a) { buoc(a, dt, t); }); if (lead) buoc(lead, dt, t);
    tram.forEach(function (s) { s.den.emissiveIntensity = (s.sang && n < s.sang) ? 1.4 : 0.35; });
    if (ban) ban.holo.material.opacity = n < (ban.sangDen || 0) ? 0.28 + Math.sin(t * 5) * 0.08 : 0;
    datCamera(); renderer.render(scene, camera);
  }

  // ---------- chuột / chạm ----------
  function nhapTay() {
    var el = renderer.domElement, ptr = {}, lastD = 0, moved = 0;
    el.style.touchAction = "none";
    el.addEventListener("pointerdown", function (e) { el.setPointerCapture(e.pointerId); ptr[e.pointerId] = { x: e.clientX, y: e.clientY }; moved = 0; });
    el.addEventListener("pointermove", function (e) {
      var p = ptr[e.pointerId]; if (!p) return; var ids = Object.keys(ptr);
      if (ids.length === 2) {
        var o = ptr[ids.filter(function (i) { return +i !== e.pointerId; })[0]]; var d = Math.hypot(e.clientX - o.x, e.clientY - o.y);
        if (lastD) cam.zoom = Math.max(0.35, Math.min(1.7, cam.zoom * lastD / d)); lastD = d;
      } else {
        cam.az -= (e.clientX - p.x) * 0.006; cam.pol = Math.max(0.35, Math.min(1.35, cam.pol - (e.clientY - p.y) * 0.005));
      }
      moved += Math.abs(e.clientX - p.x) + Math.abs(e.clientY - p.y); p.x = e.clientX; p.y = e.clientY;
    });
    function len(e) {
      delete ptr[e.pointerId]; lastD = 0;
      if (moved < 6) chamRobot(e);
    }
    el.addEventListener("pointerup", len); el.addEventListener("pointercancel", function (e) { delete ptr[e.pointerId]; lastD = 0; });
    el.addEventListener("wheel", function (e) { e.preventDefault(); cam.zoom = Math.max(0.35, Math.min(1.7, cam.zoom * (1 + e.deltaY * 0.001))); }, { passive: false });
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

  // ---------- thăm dò sự kiện ----------
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
    if (renderer) { renderer.dispose(); if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement); }
    renderer = scene = camera = null; agents = {}; ds = []; lead = null; tram = []; ban = null; runs = {};
  }
  function dung(list) {
    xoaCanh();
    cv = document.createElement("canvas"); cv.className = "mm-office-cv"; host.insertBefore(cv, host.firstChild);
    renderer = new T.WebGLRenderer({ canvas: cv, antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    dungCanh(); dungNguoi(list); nhapTay(); lanCuoi = now(); khung();
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
    Promise.all([nap(), mon()]).then(function (r) {
      if (!mo) return;
      if (!r[0]) { toast("Máy này không dựng được cảnh 3D"); dong(); return; }
      try { dung(r[1]); } catch (e) { console.warn("[office]", e); toast("Không dựng được văn phòng 3D"); dong(); return; }
      seq = 0; hoi(); pollId = setInterval(hoi, 1500);
      if (!r[1].length) toast("Brain này chưa có agent nào. Tạo agent ở trang Cộng sự để họ xuất hiện ở đây.");
    });
  }
  function dong() {
    if (!mo) return; mo = false; clearInterval(pollId);
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
    host.innerHTML = '<div class="mm-office-bar"><b>Văn phòng AI 3D</b><span>Kéo để xoay · cuộn để phóng · chạm robot để xem việc</span>' +
      '<button type="button" id="mmOfficeSim">Mô phỏng</button><button type="button" id="mmOfficeX" aria-label="Đóng văn phòng">Đóng</button></div>' +
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
    document.addEventListener("visibilitychange", function () { if (document.hidden && mo) { clearInterval(pollId); } else if (mo) { pollId = setInterval(hoi, 1500); } });
  }

  window.MinMinOffice = {
    open: function () { khoiTao(); mo_(); }, close: dong, toggle: function () { mo ? dong() : mo_(); },
    // công cụ MinMin gọi trong khung chat (app.js): chỉ có tác dụng khi văn phòng đang mở
    onChatTool: function (data) {
      if (!mo || !lead) return; var tool = data && data.tool; if (!tool || tool === "ask_javis") return;
      suKien({ k: "tool", agent: "MinMin", tool: tool });
    },
    demo: chayMau
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", khoiTao); else khoiTao();
})();
