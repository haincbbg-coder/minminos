/* Trợ lý AI - #/tro-ly : chat lên kế hoạch, kế hoạch chờ duyệt */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;
  var TT_KH = { cho_duyet: ["Chờ bạn duyệt", "warn"], dang_chay: ["Đang chạy", "brand"], hoan_tat: ["Hoàn tất", "ok"], tu_choi: ["Đã từ chối", "mu"] };
  var TT_BUOC = { cho: ["Chờ", "mu"], chuan_bi: ["Chuẩn bị", "info"], dang_chay: ["Đang chạy", "brand"], xong: ["Xong", "ok"], hoan_tat: ["Xong", "ok"], loi: ["Lỗi", "err"], bo: ["Bỏ", "mu"], huy: ["Đã huỷ", "mu"] };

  DS.view("tro-ly", {
    title: "Trợ lý AI",
    render: function (el, ctx) {
      var KB = null, mauId = {}, NICK = {}, KH = [], phien = DS.doc("doi-social.phien") || "", dangGui = false, SP = [];
      el.innerHTML = DS.ph("Trợ lý AI", "Nói việc bằng lời, trợ lý lên kế hoạch thành các đợt chạy. Kế hoạch chỉ chạy khi bạn bấm Duyệt.") +
        '<div class="card mb" id="ty-tt"><div class="sk sk-line" style="width:40%"></div></div>' +
        '<div class="grid g-21"><div class="card chat"><div class="chat-h"><div class="row"><span class="botav">' + ic("spark") + '</span><div><b>Trợ lý Đội Social</b><div class="tiny muted" id="ty-phien">Hội thoại mới</div></div></div>' +
        '<div class="row"><button class="btn btn-sm btn-ghost" data-act="lich-su">' + ic("clock") + 'Lịch sử</button><button class="btn btn-sm" data-act="moi">' + ic("plus") + "Hội thoại mới</button></div></div>" +
        '<div class="chat-b" id="ty-msgs"></div><div class="chat-f"><textarea class="ta" id="ty-in" rows="1" placeholder="Nhắn cho trợ lý, ví dụ: đăng một bài thu hút lên Trang..."></textarea>' +
        '<button class="btn btn-pri" style="height:40px" data-act="gui" aria-label="Gửi">' + ic("send") + "</button></div></div>" +
        '<div class="card" id="ty-kh-card"><div class="card-h"><h3>' + ic("list") + 'Kế hoạch AI</h3><button class="btn btn-xs btn-ghost" data-act="nap-kh">' + ic("refresh") + '</button></div><div id="ty-kh">' +
        '<div class="sk sk-card"></div></div></div></div>';

      Promise.all([DS.layKichBan(), DS.layNick(), DS.layKienThuc(), DS.api("GET", "/doi-social/tong-quan?ngay=7", null, { quiet: true })]).then(function (a) {
        if (!ctx.alive) return;
        KB = a[0]; mauId = DS.mauTheoId(KB);
        DS.list(a[1], "nick").forEach(function (n) { NICK[n.id] = n.ten; });
        SP = DS.list(a[2], "kien_thuc");
        var ai = (a[3] && a[3].ai) || {};
        el.querySelector("#ty-tt").innerHTML = '<div class="row-sb"><div class="row" style="gap:12px"><span class="botav" style="width:38px;height:38px">' + ic("robot") + '</span><div><div class="b">' +
          (ai.san_sang === false ? "Trợ lý AI chưa sẵn sàng" : "Trợ lý AI đã sẵn sàng") + '</div><div class="small muted">Đang dùng bộ não MinMin: <b>' + esc(ai.engine || "chưa rõ") + "</b>" +
          (ai.mo_hinh ? " · " + esc(ai.mo_hinh) : "") + (ai.nhin_anh ? " · nhìn được ảnh" : "") + "</div></div></div>" +
          (ai.san_sang === false ? DS.bd("Chưa có nguồn AI", "err", true) : DS.bd("Đang chạy", "ok", true)) + "</div>";
        napKH().then(napChat);
      });

      // ---------------------------------------------------------- kế hoạch
      function theKH(k, gon) {
        var buoc = k.buoc || [], cho = k.trang_thai === "cho_duyet";
        var tt = TT_KH[k.trang_thai] || [k.trang_thai, "mu"];
        return '<div class="plan' + (cho ? " wait" : "") + '" data-kh="' + k.id + '"><div class="row-sb"><div class="row"><b class="muted">#' + k.id + "</b>" + DS.bd(tt[0] + " · " + buoc.length + " bước", tt[1]) +
          "</div>" + (gon ? "" : '<span class="tiny muted">' + DS.gio(k.tao_luc) + "</span>") + '</div><div style="margin-top:6px;font-weight:500">' + esc(k.mo_ta || "") + "</div>" +
          '<ol class="steps">' + buoc.map(function (b) {
            var m = mauId[b.kich_ban] || {}, nk = (b.nick || []).map(function (id) { return NICK[id] || id; });
            var tb = b.trang_thai ? (TT_BUOC[b.trang_thai] || [b.trang_thai, "mu"]) : (cho ? null : k.trang_thai === "hoan_tat" ? TT_BUOC.xong : k.trang_thai === "dang_chay" ? TT_BUOC.dang_chay : null);
            return '<li><div class="grow" style="min-width:0"><div class="row">' + DS.icNT(m.nen_tang, 18) + '<span class="b" style="font-weight:600">' + esc(m.ten || b.kich_ban) + "</span>" + (tb ? DS.bd(tb[0], tb[1]) : "") + "</div>" +
              '<div class="tiny muted" style="margin-top:2px">' + (nk.length ? nk.length + " nick: " + esc(nk.slice(0, 3).join(", ")) + (nk.length > 3 ? "..." : "") : "Chưa chọn nick") + "</div>" +
              (b.ghi_chu ? '<div class="small" style="margin-top:2px">' + esc(b.ghi_chu) + "</div>" : "") + "</div></li>";
          }).join("") + "</ol>" +
          (cho ? '<div class="row mt-s" style="justify-content:flex-end"><button class="btn btn-sm" data-act="tu-choi" data-id="' + k.id + '">Từ chối</button><button class="btn btn-sm btn-ok" data-act="duyet-kh" data-id="' + k.id + '">' +
            ic("check") + "Duyệt và chạy</button></div>" : "") +
          ((k.dot_ids || []).length ? '<div class="tiny mt-s"><a href="#/nhat-ky?tab=dot">Xem ' + k.dot_ids.length + " đợt chạy trong nhật ký</a></div>" : "") + "</div>";
      }
      function napKH() {
        return DS.api("GET", "/doi-social/ke-hoach", null, { quiet: true }).then(function (d) {
          if (!ctx.alive) return;
          var box = el.querySelector("#ty-kh");
          if (d.ok === false) { box.innerHTML = '<div class="small muted">' + esc(d.error) + "</div>"; return; }
          KH = DS.list(d, "ke_hoach");
          var cho = KH.filter(function (k) { return k.trang_thai === "cho_duyet"; }), cu = KH.filter(function (k) { return k.trang_thai !== "cho_duyet"; });
          if (!KH.length) { box.innerHTML = DS.rong("Chưa có kế hoạch", "Nhờ trợ lý làm một việc, ví dụ bình luận nhóm cho một sản phẩm. Kế hoạch sẽ hiện ở đây chờ bạn duyệt.", "robot"); return; }
          box.innerHTML = (cho.length ? cho.map(function (k) { return theKH(k); }).join("") : '<div class="small muted mb">Không có kế hoạch nào chờ duyệt.</div>') +
            (cu.length ? '<div class="sec-t" style="margin:16px 0 8px">Kế hoạch cũ</div>' + cu.slice(0, 8).map(function (k) { return theKH(k); }).join("") : "");
        });
      }
      function khTheoId(id) { return KH.filter(function (k) { return String(k.id) === String(id); })[0]; }

      // ---------------------------------------------------------- chat
      function goiY() {
        var sp = SP.filter(function (x) { return (x.loai || "san_pham") === "san_pham"; })[0];
        var ds = ["Hôm nay các nick chạy thế nào?", "Lên kế hoạch bình luận nhóm cho sản phẩm " + (sp ? sp.ten : "của mình"), "Đăng một bài thu hút lên Trang Facebook", "Nick nào đang bị đăng xuất?"];
        return '<div class="sugg"><span class="botav" style="width:46px;height:46px;border-radius:14px">' + ic("spark") + '</span><b style="font-size:15px">Hôm nay bạn muốn đội làm gì?</b>' +
          '<div class="small muted">Trợ lý xem số liệu, chọn mẫu và nick phù hợp, rồi đưa kế hoạch để bạn duyệt.</div><div class="chips mt-s">' +
          ds.map(function (s) { return '<button class="chip" data-act="goi-y">' + esc(s) + "</button>"; }).join("") + "</div></div>";
      }
      function tinAI(noiDung, khId) {
        var k = khId != null ? khTheoId(khId) : null;
        return '<div class="cm cm-a"><span class="botav">' + ic("spark") + '</span><div class="grow" style="min-width:0"><div class="txt">' + DS.md(noiDung) + "</div>" + (k ? '<div class="mt-s">' + theKH(k, true) + "</div>" : "") + "</div></div>";
      }
      function veTin(ds) {
        var box = el.querySelector("#ty-msgs");
        if (!ds.length) { box.innerHTML = goiY(); return; }
        box.innerHTML = ds.map(function (x) {
          return x.vai === "nguoi" ? '<div class="cm cm-u">' + esc(x.noi_dung) + "</div>" : tinAI(x.noi_dung, x.ke_hoach_id);
        }).join("");
        box.scrollTop = box.scrollHeight;
      }
      function napChat() {
        el.querySelector("#ty-phien").textContent = phien ? "Phiên " + phien.slice(0, 12) : "Hội thoại mới";
        if (!phien) { veTin([]); return; }
        DS.api("GET", "/doi-social/tro-ly/lich-su?phien=" + encodeURIComponent(phien), null, { quiet: true }).then(function (d) {
          if (!ctx.alive) return;
          veTin(d.ok === false ? [] : DS.list(d, "tin"));
        });
      }
      function gui(tin) {
        tin = String(tin || "").trim();
        if (!tin || dangGui) return;
        dangGui = true;
        var box = el.querySelector("#ty-msgs"), inp = el.querySelector("#ty-in");
        if (box.querySelector(".sugg")) box.innerHTML = "";
        box.insertAdjacentHTML("beforeend", '<div class="cm cm-u">' + esc(tin) + '</div><div class="cm cm-a" id="ty-go"><span class="botav">' + ic("spark") + '</span><div class="txt typing"><span></span><span></span><span></span></div></div>');
        box.scrollTop = box.scrollHeight;
        inp.value = ""; inp.style.height = "";
        DS.api("POST", "/doi-social/tro-ly", { tin: tin, phien: phien || undefined }).then(function (d) {
          dangGui = false;
          var go = el.querySelector("#ty-go");
          if (!go) return;
          if (d.ok === false) { go.outerHTML = tinAI("Mình chưa trả lời được: " + d.error); return; }
          if (d.phien) { phien = String(d.phien); DS.ghi("doi-social.phien", phien); el.querySelector("#ty-phien").textContent = "Phiên " + phien.slice(0, 12); }
          var k = d.ke_hoach;
          if (k && k.id != null && !khTheoId(k.id)) KH.unshift(k);
          go.outerHTML = tinAI(d.tra_loi || "", k && k.id);
          box.scrollTop = box.scrollHeight;
          if (k) napKH();
        });
      }
      function duyetKH(id, dongY) {
        DS.api("POST", "/doi-social/ke-hoach/" + id + (dongY ? "/duyet" : "/tu-choi"), {}).then(function (d) {
          if (d.ok === false) return;
          DS.toast(dongY ? "Đã duyệt kế hoạch #" + id + ", các đợt đã được tạo" : "Đã từ chối kế hoạch #" + id, "ok");
          var moi = d.ke_hoach || d;
          KH = KH.map(function (k) { return String(k.id) === String(id) ? Object.assign({}, k, moi.id != null ? moi : { trang_thai: dongY ? "dang_chay" : "tu_choi" }) : k; });
          Array.prototype.forEach.call(el.querySelectorAll('[data-kh="' + id + '"]'), function (c) { c.outerHTML = theKH(khTheoId(id), !!c.closest(".chat")); });
          napKH();
        });
      }

      var inp = el.querySelector("#ty-in");
      inp.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); gui(inp.value); } });
      inp.addEventListener("input", function () { inp.style.height = "40px"; inp.style.height = Math.min(140, inp.scrollHeight + 2) + "px"; });
      DS.bind(el, {
        "gui": function () { gui(inp.value); },
        "goi-y": function (t) { gui(t.textContent); },
        "moi": function () { phien = ""; DS.ghi("doi-social.phien", ""); napChat(); inp.focus(); },
        "nap-kh": napKH,
        "duyet-kh": function (t) { duyetKH(t.getAttribute("data-id"), true); },
        "tu-choi": function (t) { duyetKH(t.getAttribute("data-id"), false); },
        "lich-su": function () {
          var m = DS.modal({ title: "Lịch sử hội thoại", body: DS.skel(4) });
          DS.api("GET", "/doi-social/tro-ly/phien").then(function (d) {
            var ds = DS.list(d, "phien");
            if (d.ok === false || !ds.length) { m.body.innerHTML = DS.rong("Chưa có hội thoại cũ", "", "chat"); return; }
            m.body.innerHTML = ds.map(function (p) {
              var id = p.phien || p.id;
              return '<button class="nick-row" style="width:100%;border:1px solid var(--line);border-radius:10px;margin-bottom:6px;background:var(--card);text-align:left" data-phien="' + esc(id) + '">' +
                '<span class="botav">' + ic("chat") + '</span><span class="grow" style="min-width:0"><span class="b clip" style="display:block">' + esc(p.tieu_de || p.tin_dau || "Phiên " + id) + '</span><span class="tiny muted">' +
                DS.gio(p.luc || p.cap_nhat) + (p.so_tin ? " · " + p.so_tin + " tin" : "") + "</span></span></button>";
            }).join("");
            m.body.addEventListener("click", function (e) {
              var b = e.target.closest("[data-phien]"); if (!b) return;
              phien = b.getAttribute("data-phien"); DS.ghi("doi-social.phien", phien); m.close(); napChat();
            });
          });
        }
      });
      ctx.every(napKH, 20000);
    }
  });
})();
