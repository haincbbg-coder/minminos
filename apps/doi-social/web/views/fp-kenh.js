/* Fanpage (API) - Kênh nguồn - #/fp-kenh : theo dõi kênh video, tải video mới, tạo bài chờ duyệt */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic, FP = DS.fp;
  var NEN = { youtube: "YouTube", tiktok: "TikTok", facebook: "Facebook", instagram: "Instagram", khac: "Khác" };
  var TT_KENH = { cho: ["Chờ quét", "info"], dang_quet: ["Đang quét", "brand"], tot: ["Ổn", "ok"], ok: ["Ổn", "ok"], loi: ["Lỗi", "err"], tat: ["Tạm dừng", "mu"] };
  var LOAI_BAI = { reel: "Reels", video: "Video", story: "Story" };

  function doanNen(link) {
    var l = String(link || "").toLowerCase();
    if (/youtu\.?be/.test(l)) return "youtube";
    if (/tiktok\.com/.test(l)) return "tiktok";
    if (/instagram\.com/.test(l)) return "instagram";
    if (/facebook\.com|fb\.watch/.test(l)) return "facebook";
    return "";
  }

  function moKenh(k, xong) {
    k = k || {};
    var cu = !!k.id;
    FP.layTrang().then(function (dt) {
      var dsTrang = DS.list(dt), dsNhom = dt.nhom || [], nhan = k.nhom_id != null ? "nhom" : "trang";
      var seg = function (id, ds, v) { return '<div class="seg" data-kn-seg="' + id + '">' + ds.map(function (x) { return '<button type="button" data-v="' + x[0] + '" class="' + (x[0] === v ? "on" : "") + '">' + esc(x[1]) + "</button>"; }).join("") + "</div>"; };
      var m = DS.modal({ title: cu ? "Sửa kênh nguồn" : "Thêm kênh nguồn", wide: true, focus: false,
        body: '<div class="note note-warn mb">' + ic("alert") + "<span>Chỉ dùng kênh của bạn hoặc kênh bạn có quyền đăng lại. Video đăng lại không có quyền dễ bị Facebook gỡ và phạt Trang.</span></div>" +
          '<div class="fgrid"><div class="fld"><label for="kn-link">Link kênh <span class="req">*</span></label><input class="inp" id="kn-link" value="' + esc(k.link || "") + '" placeholder="https://www.youtube.com/@kenh/shorts"></div>' +
          '<div class="fld"><label for="kn-nen">Nền tảng</label><select class="sel" id="kn-nen">' + Object.keys(NEN).map(function (x) { return '<option value="' + x + '"' + ((k.nen_tang || "youtube") === x ? " selected" : "") + ">" + NEN[x] + "</option>"; }).join("") + "</select></div>" +
          '<div class="fld"><label for="kn-ten">Tên gợi nhớ</label><input class="inp" id="kn-ten" value="' + esc(k.ten || "") + '" placeholder="Tuỳ chọn"></div>' +
          '<div class="fld"><label>Loại bài tạo ra</label>' + seg("loai_bai", Object.keys(LOAI_BAI).map(function (x) { return [x, LOAI_BAI[x]]; }), k.loai_bai || "reel") + "</div></div>" +
          '<div class="sec" style="margin-top:14px"><div class="sec-t">Trang nhận video</div>' + seg("nhan", [["trang", "Chọn Trang"], ["nhom", "Cả một nhóm"]], nhan) +
          '<div id="kn-trang" class="mt-s"></div><div class="fld mt-s" id="kn-nhom-f"><select class="sel" id="kn-nhom">' + (dsNhom.length ? dsNhom.map(function (n) {
            return '<option value="' + esc(n.id) + '"' + (String(n.id) === String(k.nhom_id) ? " selected" : "") + ">" + esc(n.ten) + "</option>"; }).join("") : '<option value="">Chưa có nhóm nào</option>') + "</select></div>" +
          '<div class="fld mt"><label>Chia video</label>' + seg("chia", [["xoay", "Xoay vòng, mỗi video một Trang"], ["tat_ca", "Trang nào cũng đăng"]], k.chia || "xoay") + "</div></div>" +
          '<div class="fgrid" style="margin-top:14px"><div class="fld"><label for="kn-ck">Quét mỗi (giờ)</label><input class="inp" type="number" min="1" max="168" id="kn-ck" value="' + esc(k.chu_ky_gio || 6) + '"></div>' +
          '<div class="fld"><label for="kn-max">Tối đa video mới mỗi lần quét</label><input class="inp" type="number" min="1" max="50" id="kn-max" value="' + esc(k.toi_da_moi_lan || 5) + '"></div></div>' +
          '<div class="hint mt-s">Video mới tải về máy chủ, tạo bài ở Chờ duyệt (trừ Trang đã tắt Duyệt trước) và xếp giờ theo lịch của Trang. Caption lấy từ tiêu đề video, spin qua kho nội dung của nhóm nếu có.</div>',
        foot: '<button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="kn-luu">' + (cu ? "Lưu" : "Thêm kênh") + "</button>" });
      var B = m.body, pick = FP.boChonTrang(B.querySelector("#kn-trang"), dsTrang, k.trang_ids || [], { cao: 220 });
      var S = { loai_bai: k.loai_bai || "reel", nhan: nhan, chia: k.chia || "xoay" };
      function cap() { B.querySelector("#kn-trang").hidden = S.nhan !== "trang"; B.querySelector("#kn-nhom-f").hidden = S.nhan !== "nhom"; }
      cap();
      B.addEventListener("click", function (e) {
        var b = e.target.closest("[data-kn-seg] button"); if (!b) return;
        var g = b.parentNode; S[g.getAttribute("data-kn-seg")] = b.getAttribute("data-v");
        Array.prototype.forEach.call(g.children, function (x) { x.classList.toggle("on", x === b); });
        cap();
      });
      B.querySelector("#kn-link").addEventListener("change", function () { var n = doanNen(this.value); if (n) B.querySelector("#kn-nen").value = n; });
      m.foot.querySelector("#kn-luu").onclick = function () {
        var link = B.querySelector("#kn-link").value.trim();
        if (!/^https?:\/\//i.test(link)) { DS.toast("Dán link kênh bắt đầu bằng https://", "err"); return; }
        var b = { link: link, nen_tang: B.querySelector("#kn-nen").value, ten: B.querySelector("#kn-ten").value.trim(), loai_bai: S.loai_bai, chia: S.chia,
          chu_ky_gio: Math.max(1, +B.querySelector("#kn-ck").value || 6), toi_da_moi_lan: Math.max(1, +B.querySelector("#kn-max").value || 5) };
        if (S.nhan === "trang") { b.trang_ids = pick.lay(); b.nhom_id = null; if (!b.trang_ids.length) { DS.toast("Chọn ít nhất một Trang nhận video", "err"); return; } }
        else { var nv = B.querySelector("#kn-nhom").value; if (!nv) { DS.toast("Chọn một nhóm", "err"); return; } b.nhom_id = isNaN(+nv) ? nv : +nv; b.trang_ids = []; }
        var btn = this; btn.disabled = true;
        FP.api(cu ? "PATCH" : "POST", "/kenh" + (cu ? "/" + encodeURIComponent(k.id) : ""), b).then(function (d) {
          btn.disabled = false;
          if (d.ok === false) return;
          DS.toast(cu ? "Đã lưu kênh" : "Đã thêm kênh. Bấm Quét ngay để lấy video đầu tiên.", "ok"); m.close(); xong();
        });
      };
    });
  }

  DS.view("fp-kenh", {
    title: "Kênh nguồn",
    render: function (el, ctx) {
      var ds = [];
      el.innerHTML = DS.ph("Kênh nguồn", "Theo dõi kênh video của bạn. Có video mới thì MinMin tải về, tạo bài chờ duyệt cho các Trang đã chọn.",
        '<button class="btn" data-act="tai-lai">' + ic("refresh") + 'Làm mới</button><button class="btn btn-pri" data-act="them">' + ic("plus") + "Thêm kênh</button>") +
        '<div id="kn-yt"></div><div class="card card-x"><div id="kn-ds">' + DS.skel(4) + "</div></div>";
      function nap() {
        return FP.api("GET", "/kenh").then(function (d) {
          if (!ctx.alive) return;
          var box = el.querySelector("#kn-ds");
          if (d.ok === false) { box.innerHTML = DS.loiThe(d.error, true); return; }
          ds = DS.list(d);
          var coYt = d.co_yt_dlp != null ? d.co_yt_dlp : !ds.some(function (k) { return k.co_yt_dlp === false; });
          el.querySelector("#kn-yt").innerHTML = coYt === false ? '<div class="note note-warn mb">' + ic("alert") + "<span>Máy chủ chưa có <b>yt-dlp</b> nên chưa tải được video từ kênh. Cài yt-dlp trên máy chủ MinMin (pip install yt-dlp) rồi bấm Quét ngay.</span></div>" : "";
          if (!ds.length) { box.innerHTML = DS.rong("Chưa theo dõi kênh nào", "Thêm link kênh YouTube, TikTok... của bạn, chọn Trang nhận video và chu kỳ quét.", "list", '<button class="btn btn-pri" data-act="them">' + ic("plus") + "Thêm kênh</button>"); return; }
          box.innerHTML = '<div class="tw" style="border-top:0"><table class="tbl tbl-in" style="min-width:1000px"><thead><tr><th>Kênh</th><th>Trang nhận</th><th>Cách đăng</th><th>Lần quét</th><th class="num">Video</th><th>Trạng thái</th><th>Theo dõi</th><th></th></tr></thead><tbody>' +
            ds.map(function (k) {
              var nt = k.nen_tang || doanNen(k.link), tt = Array.isArray(k.trang_ten) ? k.trang_ten : (k.trang_ten ? [String(k.trang_ten)] : []), nhan = k.nhom_id != null ? "Nhóm " + (k.nhom_ten || "#" + k.nhom_id) : (tt.length ? tt.slice(0, 2).join(", ") + (tt.length > 2 ? " +" + (tt.length - 2) : "") : FP.so((k.trang_ids || []).length) + " Trang");
              return '<tr><td><div class="row" style="flex-wrap:nowrap">' + DS.icNT(nt, 26) + '<div style="min-width:0"><b class="clip" style="display:block;max-width:220px">' + esc(k.ten || k.link) + '</b><a class="sub clip" style="display:block;max-width:240px" href="' +
                esc(k.link) + '" target="_blank" rel="noopener">' + esc(String(k.link || "").replace(/^https?:\/\/(www\.)?/, "")) + "</a></div></div></td>" +
                '<td class="small"><span class="clip" style="display:block;max-width:200px">' + esc(nhan) + "</span></td>" +
                '<td class="small nw">' + esc(LOAI_BAI[k.loai_bai] || k.loai_bai || "") + " · " + (k.chia === "tat_ca" ? "mọi Trang" : "xoay vòng") + '<div class="sub">mỗi ' + esc(k.chu_ky_gio || 6) + "h, tối đa " + esc(k.toi_da_moi_lan || 5) + " video</div></td>" +
                '<td class="small nw">' + (k.lan_quet ? esc(DS.tuongDoi(k.lan_quet)) : '<span class="muted">Chưa quét</span>') + '</td><td class="num">' + FP.so(k.so_video) + "</td>" +
                "<td>" + DS.bdMap(TT_KENH, k.trang_thai || "cho") + (k.loi ? '<div class="tiny" style="color:var(--err);max-width:220px">' + esc(k.loi) + "</div>" : "") + "</td>" +
                "<td>" + DS.sw('data-theo="' + esc(k.id) + '" aria-label="Theo dõi kênh"', !(k.theo_doi === 0 || k.theo_doi === false)) + "</td>" +
                '<td class="nw" style="text-align:right"><button class="btn btn-xs btn-soft" data-act="quet" data-id="' + esc(k.id) + '">' + ic("scan") + 'Quét ngay</button> <button class="btn btn-xs" data-act="sua" data-id="' + esc(k.id) + '">' + ic("edit") +
                'Sửa</button> <button class="btn btn-xs btn-dan" data-act="xoa" data-id="' + esc(k.id) + '" aria-label="Xoá kênh">' + ic("trash") + "</button></td></tr>";
            }).join("") + "</tbody></table></div>";
        });
      }
      function tim(id) { return ds.filter(function (k) { return String(k.id) === String(id); })[0]; }
      el.addEventListener("change", function (e) {
        var id = e.target.getAttribute("data-theo"); if (id == null) return;
        var t = e.target, on = t.checked;
        FP.api("PATCH", "/kenh/" + encodeURIComponent(id), { theo_doi: on }).then(function (d) { if (d.ok === false) t.checked = !on; else DS.toast(on ? "Đang theo dõi kênh" : "Đã ngừng theo dõi kênh", "ok"); });
      });
      DS.bind(el, {
        "tai-lai": nap,
        "them": function () { moKenh(null, nap); },
        "sua": function (t) { var k = tim(t.getAttribute("data-id")); if (k) moKenh(k, nap); },
        "quet": function (b) {
          b.disabled = true;
          FP.api("POST", "/kenh/" + encodeURIComponent(b.getAttribute("data-id")) + "/quet", {}).then(function (d) {
            b.disabled = false;
            if (d.ok === false) return;
            var so = d.so != null ? d.so : d.so_moi;
            DS.toast(so != null ? (so ? "Có " + so + " video mới, bài đã vào Chờ duyệt" : "Không có video mới") : "Đã giao quét kênh, video mới tự hiện ở Bài đăng", so ? "ok" : "info");
            nap();
          });
        },
        "xoa": function (t) {
          var k = tim(t.getAttribute("data-id")) || {};
          DS.xacNhan("Ngừng và xoá kênh " + (k.ten || k.link || "") + "? Bài đã tạo từ kênh vẫn giữ nguyên.", "Xoá kênh", true).then(function (ok) {
            if (ok) FP.api("DELETE", "/kenh/" + encodeURIComponent(k.id)).then(function (d) { if (d.ok !== false) { DS.toast("Đã xoá kênh", "ok"); nap(); } });
          });
        }
      });
      ctx.every(function () { if (ds.some(function (k) { return k.trang_thai === "dang_quet"; })) nap(); }, 15000);
      return nap();
    }
  });
})();
