/* Fanpage (API) - phần dùng chung cho các màn #/fp-* (26.10.194). Không đăng ký màn nào.
   Hợp đồng: docs/doi-social/FANPAGE.md mục 8 (API) và 9 (giao diện). */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;
  var FP = DS.fp = {};
  FP.GOC = "/doi-social/fp";

  // ---------------------------------------------------------------- bảng chữ
  FP.TT_BAI = { cho_duyet: ["Chờ duyệt", "warn"], cho_dang: ["Chờ đăng", "info"], da_hen_fb: ["Đã hẹn trên FB", "brand"], dang_dang: ["Đang đăng", "brand"],
    da_dang: ["Đã đăng", "ok"], loi: ["Lỗi", "err"], bo: ["Đã bỏ", "mu"] };
  FP.TT_BAI_THU_TU = ["cho_duyet", "cho_dang", "da_hen_fb", "dang_dang", "da_dang", "loi", "bo"];
  FP.TT_PHU = { cho: ["chờ", "info"], xong: ["xong", "ok"], loi: ["lỗi", "err"] };
  FP.LOAI = { chu: "Chữ", anh: "Ảnh", album: "Album", video: "Video", reel: "Reels", story: "Story" };
  FP.LOAI_THU_TU = ["chu", "anh", "album", "video", "reel", "story"];
  FP.LOAI_IC = { chu: "file", anh: "image", album: "image", video: "video", reel: "video", story: "spark" };
  FP.TT_BL = { moi: ["Mới", "info"], cho_duyet: ["Chờ duyệt", "warn"], cho_gui: ["Chờ gửi", "info"], dang_gui: ["Đang gửi", "brand"], da_tra_loi: ["Đã trả lời", "ok"],
    da_an: ["Đã ẩn", "mu"], bo_qua: ["Bỏ qua", "mu"], loi: ["Lỗi", "err"] };
  FP.TT_TOKEN = { tot: ["Tốt", "ok"], loi: ["Lỗi", "err"], het_han: ["Hết hạn", "err"], chua_kiem: ["Chưa kiểm", "mu"] };
  FP.LOAI_TOKEN = { ket_noi: "Kết nối OAuth", nguoi_dung: "Token người dùng", trang: "Token Trang" };
  FP.MUC_CB = { chan: ["Chặn đứng", "err"], nang: ["Nặng", "warn"], nhac: ["Nhắc", "info"] };
  FP.KHO_LOAI = { noi_dung: "Nội dung", binh_luan: "Bình luận", link: "Link", tieu_su: "Tiểu sử" };
  FP.CHE_DO_KHO = { ngau_nhien: "Ngẫu nhiên", lan_luot: "Lần lượt", stt: "Theo số trong tên tệp" };
  FP.NGUON_CH = { trang: "riêng", nhom: "theo nhóm", mac_dinh: "mặc định" };
  FP.NGUON_BAI = { tay: "Tạo tay", kho: "Từ kho", kenh: "Kênh nguồn", ai: "AI", thu_muc: "Thư mục" };
  FP.MAC_DINH = {
    lich: { che_do: "gio", gio: ["09:00", "12:00", "18:00"], moi_gio: 4, tu: "08:00", den: "22:00", lech_phut: 30, trai_phut: 0, cach: "tool" },
    kho_noi_dung: null, kho_binh_luan: null, kho_tieu_su: null,
    binh_luan_sau_dang: false, story: false, ig_dong_bo: false, tu_an: false, tu_tra_loi: false, chia_video: "mot_trang", duyet_truoc: true
  };
  FP.CANH_BAO_CONG_KHAI = "Việc này đăng công khai lên Facebook, khách của Trang thấy ngay và không rút lại tự động được.";

  // ---------------------------------------------------------------- gọi API + nhớ tạm
  FP.api = function (method, duong, body, opt) { return DS.api(method, FP.GOC + duong, body, opt); };
  function nho(key, duong, ttl) {
    return function (moi) {
      var c = DS.cache[key];
      if (!moi && c && Date.now() - c.t < (ttl || 30000)) return Promise.resolve(c.d);
      return FP.api("GET", duong, null, { quiet: true }).then(function (d) {
        if (d.ok !== false) DS.cache[key] = { t: Date.now(), d: d };
        return d;
      });
    };
  }
  FP.layTrang = nho("fp-trang", "/trang");
  FP.layNhom = nho("fp-nhom", "/nhom");
  FP.layKho = nho("fp-kho", "/kho");
  FP.boNho = function () { ["fp-trang", "fp-nhom", "fp-kho"].forEach(DS.boNho); };

  // ---------------------------------------------------------------- tiện ích
  FP.avTrang = function (t, cls) {
    t = t || {};
    if (t.anh) return '<img class="av fp-av ' + (cls || "") + '" src="' + esc(t.anh) + '" alt="" loading="lazy" referrerpolicy="no-referrer">';
    return DS.av(t.ten || t.id, cls);
  };
  FP.tepTen = function (x) { return typeof x === "string" ? x : (x && (x.tep || x.ten)) || ""; };
  FP.tepUrl = function (x) { return FP.GOC + "/media/" + encodeURIComponent(FP.tepTen(x)); };
  FP.laVideo = function (x) {
    if (x && typeof x === "object" && x.loai) return x.loai === "video";
    return /\.(mp4|mov|m4v|webm|mkv|avi)$/i.test(FP.tepTen(x));
  };
  FP.thumbs = function (ds, toiDa) {
    ds = (ds || []).reduce(function (a, x) { return a.concat(Array.isArray(x) ? x : [x]); }, []);
    if (!ds.length) return "";
    toiDa = toiDa || 3;
    return '<div class="thumbs fp-thumbs">' + ds.slice(0, toiDa).map(function (t) {
      var u = FP.tepUrl(t);
      return FP.laVideo(t) ? '<a class="vid" href="' + u + '" target="_blank" rel="noopener" title="' + esc(FP.tepTen(t)) + '">' + ic("video") + "</a>" :
        '<a href="' + u + '" target="_blank" rel="noopener"><img loading="lazy" src="' + u + '" alt="' + esc(FP.tepTen(t)) + '"></a>';
    }).join("") + (ds.length > toiDa ? '<span class="tiny muted">+' + (ds.length - toiDa) + "</span>" : "") + "</div>";
  };
  FP.bdPhu = function (nhan, v) {
    if (!v) return "";
    var x = FP.TT_PHU[v] || [v, "mu"];
    return DS.bd(nhan + " " + x[0], x[1]);
  };
  FP.ttBai = function (b) {
    b = b || {};
    var h = DS.bdMap(FP.TT_BAI, b.trang_thai);
    h += FP.bdPhu("Bình luận", b.bl_tt) + FP.bdPhu("Story", b.story_tt) + FP.bdPhu("IG", b.ig_tt);
    return '<div class="fp-tt">' + h + "</div>";
  };
  FP.so = function (n) { return DS.so(n || 0); };
  FP.p2 = function (n) { return (n < 10 ? "0" : "") + n; };
  // ts (giây) <-> giá trị của <input type="datetime-local"> theo giờ trình duyệt
  FP.dtLocal = function (t) {
    if (!t) return "";
    var d = new Date(t * 1000), p = FP.p2;
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + "T" + p(d.getHours()) + ":" + p(d.getMinutes());
  };
  FP.tuDt = function (s) { if (!s) return null; var t = new Date(s).getTime(); return isNaN(t) ? null : Math.floor(t / 1000); };
  FP.ngayNgan = function (s) { var p = String(s || "").split("-"); return p.length === 3 ? p[2] + "/" + p[1] : String(s || ""); };
  // tách giờ "9:00, 12:30 18h" -> ["09:00","12:30","18:00"]
  FP.tachGio = function (s) {
    var kq = [];
    String(s || "").split(/[\s,;]+/).forEach(function (x) {
      var m = /^(\d{1,2})(?::|h)?(\d{2})?h?$/i.exec(x.trim());
      if (!m) return;
      var h = +m[1], mi = +(m[2] || 0);
      if (h > 23 || mi > 59) return;
      var g = FP.p2(h) + ":" + FP.p2(mi);
      if (kq.indexOf(g) < 0) kq.push(g);
    });
    return kq.sort();
  };
  // mục trong kho: mỗi dòng 1 mục; có dòng '---' thì tách theo dòng đó (nội dung nhiều dòng)
  FP.tachMuc = function (s) {
    s = String(s || "").replace(/\r\n?/g, "\n");
    if (/^\s*---\s*$/m.test(s)) return s.split(/^\s*---\s*$/m).map(function (x) { return x.trim(); }).filter(Boolean);
    return s.split("\n").map(function (x) { return x.trim(); }).filter(Boolean);
  };
  FP.ghepMuc = function (ds) {
    ds = (ds || []).map(function (x) { return typeof x === "string" ? x : (x && (x.chu || x.noi_dung)) || ""; });
    return ds.some(function (x) { return x.indexOf("\n") >= 0; }) ? ds.join("\n---\n") : ds.join("\n");
  };
  FP.gop = function (a, b) {
    var o = {};
    Object.keys(a || {}).forEach(function (k) { o[k] = a[k]; });
    Object.keys(b || {}).forEach(function (k) {
      var v = b[k];
      if (v === null || v === undefined) return;
      o[k] = v && typeof v === "object" && !Array.isArray(v) && o[k] && typeof o[k] === "object" ? FP.gop(o[k], v) : v;
    });
    return o;
  };
  FP.moTaLich = function (l) {
    l = l || {};
    var cd = l.che_do || "gio", h;
    if (cd === "tat") return "Không tự xếp lịch";
    if (cd === "chu_ky") h = "Mỗi " + (l.moi_gio || 4) + "h, " + (l.tu || "08:00") + "-" + (l.den || "22:00");
    else h = (l.gio || []).length ? (l.gio || []).join(", ") : "Chưa có khung giờ";
    return h + (l.cach === "fb" ? " · hẹn trên FB" : "");
  };
  FP.tenKho = function (dsKho, id) {
    if (id == null || id === "") return "";
    for (var i = 0; i < dsKho.length; i++) if (String(dsKho[i].id) === String(id)) return dsKho[i].ten;
    return "Kho #" + id;
  };
  FP.chipCongTac = function (ch) {
    ch = ch || {};
    var ds = [["binh_luan_sau_dang", "Comment"], ["story", "Story"], ["ig_dong_bo", "IG"], ["tu_an", "Tự ẩn"], ["tu_tra_loi", "Tự trả lời"]];
    return '<div class="fp-tog">' + ds.map(function (x) {
      return '<span class="fp-t' + (ch[x[0]] ? " on" : "") + '" title="' + esc(x[1]) + (ch[x[0]] ? ": bật" : ": tắt") + '">' + esc(x[1]) + "</span>";
    }).join("") + (ch.duyet_truoc === false ? '<span class="fp-t warn" title="Bài vào thẳng hàng chờ đăng">Không duyệt</span>' : "") + "</div>";
  };
  FP.ketQuaHangLoat = function (d, viec) {
    var loi = (d && d.loi) || [], so = d && d.so != null ? d.so : 0;
    if (!loi.length) { DS.toast(viec + ": xong " + so + " Trang", "ok"); return; }
    DS.modal({ title: viec + ": " + so + " xong, " + loi.length + " lỗi",
      body: '<div class="dd-ds">' + loi.map(function (x) {
        return '<div class="dd-dong"><span class="grow" style="min-width:0"><b class="clip" style="display:block">' + esc(x.ten || x.id || "") + '</b><span class="tiny" style="color:var(--err)">' +
          esc(x.loi || "") + "</span></span></div>";
      }).join("") + "</div>" });
  };

  // ---------------------------------------------------------------- dải cảnh báo "Dừng mọi tự động"
  FP.dungBanner = function (dung) {
    if (!dung) return "";
    return '<div class="note note-err mb fp-dung-note">' + ic("stop") + '<div class="grow"><b>Đang dừng mọi tự động.</b> Không đăng theo lịch, không tự trả lời, không tự ẩn, không bình luận sau đăng, không quét kênh. ' +
      'Bài đã hẹn sẵn trên Facebook vẫn lên đúng giờ (Facebook giữ, nút này không rút được).</div><button class="btn btn-sm" type="button" data-act="fp-chay-lai">' + ic("play") + "Chạy lại</button></div>";
  };
  FP.datDung = function (dung) {
    var hoi = dung ? Promise.resolve(true) : DS.xacNhan("Cho MinMin chạy lại mọi tự động của Fanpage (đăng theo lịch, tự trả lời, tự ẩn, quét kênh)?", "Chạy lại");
    return hoi.then(function (ok) {
      if (!ok) return null;
      return FP.api("POST", "/tu-dong", { dung: !!dung }).then(function (d) {
        if (d.ok === false) return null;
        DS.toast(dung ? "Đã dừng mọi tự động của Fanpage" : "Đã cho tự động chạy lại", dung ? "info" : "ok");
        return !!dung;
      });
    });
  };

  // ---------------------------------------------------------------- biểu đồ mini (SVG thuần)
  FP.spark = function (vals, opt) {
    opt = opt || {};
    var W = opt.w || 120, H = opt.h || 34, v = (vals || []).map(function (x) { return Number(x) || 0; });
    if (v.length < 2) return '<svg class="fp-spark" viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" aria-hidden="true"></svg>';
    var mn = Math.min.apply(null, v), mx = Math.max.apply(null, v), r = mx - mn || 1;
    var pts = v.map(function (x, i) { return [(i / (v.length - 1)) * (W - 4) + 2, H - 3 - ((x - mn) / r) * (H - 6)]; });
    var d = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join("");
    return '<svg class="fp-spark" viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" aria-hidden="true"><path class="ar" d="' + d + "L" + (W - 2) + " " + H + "L2 " + H + 'Z"/><path class="ln" d="' + d + '"/></svg>';
  };
  // cột theo ngày: ds = [{ngay, gia_tri}], trả svg có data-i để hiện tooltip
  FP.cot = function (ds, khoa, opt) {
    opt = opt || {};
    var W = Math.max(260, Math.round(opt.w || 600)), H = opt.h || 160, L = 34, B = 20, T = 6;
    var mx = 1;
    ds.forEach(function (x) { mx = Math.max(mx, Number(x[khoa]) || 0); });
    var cw = (W - L) / Math.max(1, ds.length), bw = Math.max(4, Math.min(26, cw * .6)), hh = H - B - T;
    var s = '<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H + '" role="img" aria-label="' + esc(opt.nhan || "Biểu đồ") + '">';
    [0, .5, 1].forEach(function (k) {
      var gy = T + hh * (1 - k);
      s += '<line class="grid-l" x1="' + L + '" x2="' + W + '" y1="' + gy + '" y2="' + gy + '"/><text x="' + (L - 6) + '" y="' + (gy + 3) + '" text-anchor="end">' + DS.so(Math.round(mx * k)) + "</text>";
    });
    ds.forEach(function (x, i) {
      var v = Number(x[khoa]) || 0, h = v / mx * hh, xx = L + i * cw + (cw - bw) / 2;
      if (h > 0) s += '<rect class="' + (opt.cls || "bar-ok") + '" x="' + xx.toFixed(1) + '" y="' + (T + hh - h).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + h.toFixed(1) + '" rx="3"/>';
      if (cw >= 30 || i % 2 === (ds.length - 1) % 2) s += '<text x="' + (L + i * cw + cw / 2).toFixed(1) + '" y="' + (H - 5) + '" text-anchor="middle">' + esc(FP.ngayNgan(x.ngay)) + "</text>";
      s += '<rect class="hit" x="' + (L + i * cw).toFixed(1) + '" y="' + T + '" width="' + cw.toFixed(1) + '" height="' + hh + '" data-i="' + i + '"/>';
    });
    return s + "</svg>";
  };
  FP.ganTip = function (box, ds, fn) {
    box.addEventListener("mousemove", function (e) {
      var t = e.target.closest("[data-i]");
      if (!t) { DS.tip(null); return; }
      DS.tip(fn(ds[+t.getAttribute("data-i")] || {}), e.clientX, e.clientY);
    });
    box.addEventListener("mouseleave", function () { DS.tip(null); });
  };

  // ---------------------------------------------------------------- chọn Trang (danh sách tick + tìm + chọn theo nhóm)
  // FP.boChonTrang(host, dsTrang, daChon[]) -> {lay(): [id], dat(ids)}
  FP.boChonTrang = function (host, ds, daChon, opt) {
    opt = opt || {};
    var chon = {}, tim = "";
    (daChon || []).forEach(function (id) { chon[String(id)] = true; });
    var nhom = {};
    ds.forEach(function (t) { if (t.nhom_id != null) { nhom[t.nhom_id] = nhom[t.nhom_id] || { ten: t.nhom_ten || ("Nhóm #" + t.nhom_id), ids: [] }; nhom[t.nhom_id].ids.push(String(t.id)); } });
    host.innerHTML = '<div class="nick-box fp-pick"><div class="nick-tools"><div class="inp-ic grow" style="min-width:160px">' + ic("search") +
      '<input class="inp inp-sm" data-fp-tim placeholder="Tìm Trang"></div><button class="btn btn-sm" type="button" data-fp-het>Chọn tất cả khớp</button>' +
      '<button class="btn btn-sm btn-ghost" type="button" data-fp-bo>Bỏ chọn</button><span class="bd bd-brand" data-fp-dem></span></div>' +
      (Object.keys(nhom).length ? '<div class="nick-tools" style="padding-top:8px;padding-bottom:8px"><span class="tiny muted">Chọn theo nhóm:</span>' + Object.keys(nhom).map(function (k) {
        return '<button class="chip" type="button" data-fp-nhom="' + esc(k) + '">' + esc(nhom[k].ten) + ' <span class="cnt">' + nhom[k].ids.length + "</span></button>";
      }).join("") + "</div>" : "") + '<div class="nick-list" data-fp-ds style="max-height:' + (opt.cao || 260) + 'px"></div></div>';
    function khop() {
      var t = tim.trim().toLowerCase();
      return ds.filter(function (x) { return !t || ((x.ten || "") + " " + x.id + " " + (x.nhom_ten || "")).toLowerCase().indexOf(t) >= 0; });
    }
    function ve() {
      var l = khop(), box = host.querySelector("[data-fp-ds]");
      box.innerHTML = l.length ? l.map(function (x) {
        var on = !!chon[String(x.id)];
        return '<label class="nick-row' + (on ? " on" : "") + '"><input type="checkbox" class="cb" data-fp-id="' + esc(x.id) + '"' + (on ? " checked" : "") + ">" + FP.avTrang(x) +
          '<span class="grow" style="min-width:0"><b class="clip" style="display:block">' + esc(x.ten || x.id) + '</b><span class="tiny muted">' + esc(x.nhom_ten || "Chưa nhóm") +
          (x.bat === 0 || x.bat === false ? " · đang tắt" : "") + "</span></span></label>";
      }).join("") : '<div class="small muted" style="padding:12px">Không có Trang nào khớp.</div>';
      dem();
    }
    function dem() { host.querySelector("[data-fp-dem]").textContent = Object.keys(chon).filter(function (k) { return chon[k]; }).length + " Trang"; }
    host.addEventListener("input", function (e) { if (e.target.hasAttribute("data-fp-tim")) { tim = e.target.value; ve(); } });
    host.addEventListener("change", function (e) {
      var id = e.target.getAttribute("data-fp-id");
      if (id == null) return;
      chon[id] = e.target.checked;
      e.target.closest(".nick-row").classList.toggle("on", e.target.checked);
      dem();
      if (opt.doi) opt.doi();
    });
    host.addEventListener("click", function (e) {
      if (e.target.closest("[data-fp-het]")) { khop().forEach(function (x) { chon[String(x.id)] = true; }); ve(); if (opt.doi) opt.doi(); }
      else if (e.target.closest("[data-fp-bo]")) { chon = {}; ve(); if (opt.doi) opt.doi(); }
      else {
        var n = e.target.closest("[data-fp-nhom]");
        if (n) { nhom[n.getAttribute("data-fp-nhom")].ids.forEach(function (id) { chon[id] = true; }); ve(); if (opt.doi) opt.doi(); }
      }
    });
    ve();
    return {
      lay: function () { return ds.map(function (x) { return String(x.id); }).filter(function (id) { return chon[id]; }); },
      dat: function (ids) { chon = {}; (ids || []).forEach(function (id) { chon[String(id)] = true; }); ve(); }
    };
  };

  // ---------------------------------------------------------------- sửa cấu hình nhóm / Trang
  // FP.formCauHinh(ch, dsKho) -> html; FP.ganCauHinh(root) gắn sự kiện + xem trước; FP.docCauHinh(root) -> cau_hinh
  function seg(ten, ds, v) {
    return '<div class="seg" data-ch-seg="' + ten + '">' + ds.map(function (x) {
      return '<button type="button" data-v="' + esc(x[0]) + '" class="' + (String(v) === String(x[0]) ? "on" : "") + '">' + esc(x[1]) + "</button>";
    }).join("") + "</div>";
  }
  function chonKho(ten, nhan, loai, dsKho, v) {
    var l = dsKho.filter(function (k) { return k.loai === loai; });
    return '<div class="fld"><label for="ch-' + ten + '">' + esc(nhan) + '</label><select class="sel" id="ch-' + ten + '" data-ch="' + ten + '"><option value="">Không dùng kho</option>' +
      l.map(function (k) { return '<option value="' + esc(k.id) + '"' + (String(v) === String(k.id) ? " selected" : "") + ">" + esc(k.ten) + " (" + DS.so(k.so || 0) + " mục)</option>"; }).join("") +
      "</select>" + (l.length ? "" : '<div class="hint">Chưa có kho ' + esc(FP.KHO_LOAI[loai].toLowerCase()) + '. <a href="#/fp-kho?tab=' + loai + '">Tạo ở Kho nội dung</a></div>') + "</div>";
  }
  function congTac(ten, nhan, goiY, v, canhBao) {
    return '<div class="swrow"><div class="grow"><div style="font-weight:500">' + esc(nhan) + '</div><div class="hint">' + goiY + "</div>" +
      (canhBao ? '<div class="hint fp-warn-hint" data-ch-cb="' + ten + '"' + (v ? " hidden" : "") + ">" + canhBao + "</div>" : "") + "</div>" + DS.sw('data-ch="' + ten + '" data-kieu="bat"', !!v) + "</div>";
  }
  FP.formCauHinh = function (ch, dsKho) {
    ch = FP.gop(FP.MAC_DINH, ch || {});
    var l = ch.lich || {};
    dsKho = dsKho || [];
    return '<div class="fp-ch">' +
      '<div class="sec"><div class="sec-t">' + ic("calendar") + 'Lịch đăng</div>' +
      '<div class="fld"><label>Cách xếp lịch</label>' + seg("che_do", [["gio", "Theo khung giờ"], ["chu_ky", "Theo chu kỳ"], ["tat", "Tắt, đăng tay"]], l.che_do) + "</div>" +
      '<div data-ch-khi="gio"' + (l.che_do === "gio" ? "" : " hidden") + '><div class="fld"><label for="ch-gio">Khung giờ trong ngày</label><input class="inp" id="ch-gio" data-ch="gio" value="' +
      esc((l.gio || []).join(", ")) + '" placeholder="09:00, 12:00, 18:00"><div class="hint">Cách nhau bằng dấu phẩy. Mỗi khung một bài mỗi Trang.</div></div></div>' +
      '<div data-ch-khi="chu_ky"' + (l.che_do === "chu_ky" ? "" : " hidden") + '><div class="fld"><label for="ch-moi">Cứ mấy giờ đăng một bài</label><input class="inp" type="number" min="1" max="48" id="ch-moi" data-ch="moi_gio" value="' +
      esc(l.moi_gio || 4) + '"></div></div>' +
      '<div data-ch-khi="gio chu_ky"' + (l.che_do === "tat" ? " hidden" : "") + '><div class="fgrid" style="margin-top:14px"><div class="fld"><label for="ch-tu">Chỉ đăng từ</label><input class="inp" type="time" id="ch-tu" data-ch="tu" value="' + esc(l.tu || "08:00") +
      '"></div><div class="fld"><label for="ch-den">đến</label><input class="inp" type="time" id="ch-den" data-ch="den" value="' + esc(l.den || "22:00") + '"></div>' +
      '<div class="fld"><label for="ch-lech">Lệch ngẫu nhiên ± phút</label><input class="inp" type="number" min="0" max="120" id="ch-lech" data-ch="lech_phut" value="' + esc(l.lech_phut != null ? l.lech_phut : 30) +
      '"><div class="hint">Cho giờ đăng tự nhiên, không đúng phút tròn.</div></div><div class="fld"><label for="ch-trai">Trải các Trang cách nhau (phút)</label><input class="inp" type="number" min="0" max="240" id="ch-trai" data-ch="trai_phut" value="' +
      esc(l.trai_phut || 0) + '"><div class="hint">Trang thứ 2 lùi thêm chừng này phút, Trang thứ 3 lùi gấp đôi...</div></div></div>' +
      '<div class="fld" style="margin-top:14px"><label>Ai giữ lịch</label>' + seg("cach", [["tool", "MinMin tự đăng khi tới giờ"], ["fb", "Hẹn sẵn trên Facebook"]], l.cach || "tool") +
      '<div class="hint">Hẹn trên Facebook: bài nằm sẵn ở Facebook (từ 11 phút tới 29 ngày), máy chủ tắt vẫn lên. Story, Reels, album luôn do MinMin đăng. Bài đã hẹn trên FB thì nút Dừng mọi tự động không rút được.</div></div>' +
      '<div class="fp-xt mt"><div class="row-sb"><b class="small">' + ic("eye") + ' Xem trước giờ đăng</b><button class="btn btn-xs" type="button" data-ch-xt>' + ic("refresh") + 'Tính lại</button></div><div class="fp-gio" data-ch-xt-kq><span class="tiny muted">Đang tính...</span></div></div></div></div>' +
      '<div class="sec"><div class="sec-t">' + ic("box") + 'Kho nội dung</div><div class="fgrid fgrid3">' +
      chonKho("kho_noi_dung", "Kho nội dung (caption)", "noi_dung", dsKho, ch.kho_noi_dung) + chonKho("kho_binh_luan", "Kho bình luận", "binh_luan", dsKho, ch.kho_binh_luan) +
      chonKho("kho_tieu_su", "Kho tiểu sử", "tieu_su", dsKho, ch.kho_tieu_su) + "</div></div>" +
      '<div class="sec"><div class="sec-t">' + ic("bolt") + "Tự động kèm theo</div>" +
      congTac("binh_luan_sau_dang", "Bình luận sau khi đăng", "Trang tự bình luận một câu từ kho bình luận dưới bài vừa đăng (khoảng 1 phút sau).", ch.binh_luan_sau_dang) +
      congTac("story", "Đăng kèm Story", "Lấy ảnh hoặc video đầu tiên của bài đăng thêm thành Story.", ch.story) +
      congTac("ig_dong_bo", "Đồng bộ sang Instagram", "Trang có Instagram doanh nghiệp đi kèm thì đăng luôn bên đó.", ch.ig_dong_bo) +
      congTac("tu_an", "Tự ẩn bình luận theo quy tắc", "Ẩn bình luận khớp quy tắc (ví dụ chứa số điện thoại, link lạ).", ch.tu_an) +
      congTac("tu_tra_loi", "Tự trả lời bình luận theo quy tắc", "Soạn trả lời theo quy tắc ở trang Bình luận. Quy tắc nào chưa bật Tự gửi thì câu trả lời vẫn chờ bạn duyệt.", ch.tu_tra_loi) +
      congTac("duyet_truoc", "Duyệt trước khi đăng", "Bài tạo hàng loạt, từ kênh nguồn, từ AI vào Chờ duyệt, bạn bấm Duyệt mới đăng.", ch.duyet_truoc !== false,
        ic("alert") + " Đang tắt: bài vào thẳng hàng chờ đăng và tự lên Facebook theo lịch, không qua tay bạn.") +
      '<div class="fld" style="margin-top:14px"><label>Một video cho nhiều Trang</label>' + seg("chia_video", [["mot_trang", "Mỗi video một Trang"], ["tat_ca", "Trang nào cũng đăng"]], ch.chia_video || "mot_trang") + "</div></div></div>";
  };
  FP.docLich = function (root) {
    var v = function (k) { var e = root.querySelector('[data-ch="' + k + '"]'); return e ? e.value : ""; };
    var s = function (k) { var b = root.querySelector('[data-ch-seg="' + k + '"] button.on'); return b ? b.getAttribute("data-v") : ""; };
    return { che_do: s("che_do") || "gio", gio: FP.tachGio(v("gio")), moi_gio: Math.max(1, +v("moi_gio") || 4), tu: v("tu") || "08:00", den: v("den") || "22:00",
      lech_phut: Math.max(0, +v("lech_phut") || 0), trai_phut: Math.max(0, +v("trai_phut") || 0), cach: s("cach") || "tool" };
  };
  FP.docCauHinh = function (root) {
    var o = { lich: FP.docLich(root) };
    ["kho_noi_dung", "kho_binh_luan", "kho_tieu_su"].forEach(function (k) { var e = root.querySelector('[data-ch="' + k + '"]'); o[k] = e && e.value ? (isNaN(+e.value) ? e.value : +e.value) : null; });
    ["binh_luan_sau_dang", "story", "ig_dong_bo", "tu_an", "tu_tra_loi", "duyet_truoc"].forEach(function (k) { var e = root.querySelector('[data-ch="' + k + '"]'); o[k] = !!(e && e.checked); });
    var b = root.querySelector('[data-ch-seg="chia_video"] button.on');
    o.chia_video = b ? b.getAttribute("data-v") : "mot_trang";
    return o;
  };
  FP.ganCauHinh = function (root) {
    var hen = null, lan = 0;
    function xemTruoc() {
      var box = root.querySelector("[data-ch-xt-kq]");
      if (!box) return;
      var l = FP.docLich(root), so = ++lan;
      if (l.che_do === "tat") { box.innerHTML = '<span class="tiny muted">Lịch đang tắt: bài không tự xếp giờ, bạn bấm Đăng ngay từng bài.</span>'; return; }
      if (l.che_do === "gio" && !l.gio.length) { box.innerHTML = '<span class="tiny" style="color:var(--err)">Nhập ít nhất một khung giờ, ví dụ 09:00.</span>'; return; }
      box.innerHTML = '<span class="tiny muted">Đang tính...</span>';
      FP.api("POST", "/lich/xem-truoc", { cau_hinh_lich: l, so: 8 }, { quiet: true }).then(function (d) {
        if (so !== lan) return;
        if (d.ok === false) { box.innerHTML = '<span class="tiny muted">Chưa xem trước được: ' + esc(d.error) + "</span>"; return; }
        var g = d.gio || [];
        box.innerHTML = g.length ? g.map(function (t) { return '<span class="bd bd-out" title="' + esc(DS.gioDu(t)) + '">' + esc(DS.gio(t)) + "</span>"; }).join("") +
          '<div class="tiny muted" style="width:100%">8 lượt đăng kế tiếp của một Trang, đã cộng lệch ngẫu nhiên.</div>' : '<span class="tiny muted">Không có giờ nào trong khung đã chọn.</span>';
      });
    }
    function hoan() { clearTimeout(hen); hen = setTimeout(xemTruoc, 450); }
    root.addEventListener("click", function (e) {
      var b = e.target.closest("[data-ch-seg] button");
      if (b) {
        var g = b.parentNode, ten = g.getAttribute("data-ch-seg");
        Array.prototype.forEach.call(g.children, function (x) { x.classList.toggle("on", x === b); });
        if (ten === "che_do") {
          var v = b.getAttribute("data-v");
          Array.prototype.forEach.call(root.querySelectorAll("[data-ch-khi]"), function (k) { k.hidden = k.getAttribute("data-ch-khi").split(" ").indexOf(v) < 0; });
        }
        if (ten === "che_do" || ten === "cach") hoan();
        return;
      }
      if (e.target.closest("[data-ch-xt]")) xemTruoc();
    });
    root.addEventListener("input", function (e) { var k = e.target.getAttribute("data-ch"); if (k && ["gio", "moi_gio", "tu", "den", "lech_phut", "trai_phut"].indexOf(k) >= 0) hoan(); });
    root.addEventListener("change", function (e) {
      var k = e.target.getAttribute("data-ch");
      if (k === "duyet_truoc") { var c = root.querySelector('[data-ch-cb="duyet_truoc"]'); if (c) c.hidden = e.target.checked; }
    });
    xemTruoc();
  };
})();
