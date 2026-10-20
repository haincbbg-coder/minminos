/* Tin nhắn khách - #/tin-nhan?tab=can_tay|tat_ca|tiem_nang */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;
  var TT = { bot_dang_lo: ["Bot đang trả lời", "brand"], can_tra_loi_tay: ["Chờ trả lời tay", "warn"], da_xu_ly: ["Đã xử lý", "ok"], spam: ["Spam", "mu"] };
  var TU = { khach: "Khách", bot: "Bot", chu: "Bạn" };

  DS.view("tin-nhan", {
    title: "Tin nhắn",
    render: function (el, ctx) {
      var tab = ["can_tay", "tat_ca", "tiem_nang"].indexOf(ctx.q.tab) >= 0 ? ctx.q.tab : "can_tay";
      var KT = {}, ds = [];
      el.innerHTML = DS.ph("Tin nhắn khách", "Bot trả lời Messenger theo hồ sơ sản phẩm. Câu khó, đặt hàng, khiếu nại thì chuyển sang bạn.",
        '<button class="btn" data-act="tai-lai">' + ic("refresh") + "Làm mới</button>") + '<div id="tn-tabs"></div><div id="tn-ds">' + DS.skel(5) + "</div>";
      DS.layKienThuc().then(function (d) { DS.list(d, "kien_thuc").forEach(function (k) { KT[k.id] = k; }); });

      function veTabs(dem) {
        dem = dem || {};
        el.querySelector("#tn-tabs").innerHTML = DS.tabs([{ id: "can_tay", ten: "Cần trả lời tay", n: dem.can_tay || 0 }, { id: "tat_ca", ten: "Tất cả hội thoại", n: dem.tat_ca || 0 },
          { id: "tiem_nang", ten: "Khách tiềm năng", n: dem.tiem_nang || 0 }], tab, "#/tin-nhan?tab=");
      }
      function the(h) {
        var sp = KT[h.san_pham_id], cuoi = h.tin_cuoi || h.tin_moi || "";
        if (cuoi && typeof cuoi === "object") cuoi = (TU[cuoi.tu] ? TU[cuoi.tu] + ": " : "") + (cuoi.noi_dung || "");
        return '<div class="dr" data-id="' + h.id + '"><div class="dr-h">' + DS.av(h.khach_ten) + '<div class="grow" style="min-width:0"><div class="row"><b>' + esc(h.khach_ten || "Khách") + "</b>" +
          DS.bdMap(TT, h.trang_thai) + (h.tiem_nang ? DS.bd("Khách tiềm năng", "ok") : "") + (h.sdt ? '<span class="bd bd-out">' + ic("phone") + esc(h.sdt) + "</span>" : "") + "</div>" +
          '<div class="dr-meta"><span>' + ic("user") + "Nick: " + esc(h.nick_ten || "") + "</span>" + (sp || h.san_pham_ten ? "<span>" + ic("tag") + "Sản phẩm: " + esc(sp ? sp.ten : h.san_pham_ten) + "</span>" : "") +
          "<span>" + ic("clock") + DS.gio(h.cap_nhat) + "</span>" + (h.nhuong_den && h.nhuong_den > Date.now() / 1000 ? '<span style="color:var(--info)">Bot nhường tới ' + DS.gioPhut(h.nhuong_den) + "</span>" : "") + "</div>" +
          (cuoi ? '<div class="small clamp2" style="margin-top:8px;color:var(--ink2)">' + esc(cuoi) + "</div>" : "") + "</div></div>" +
          '<div class="dr-f"><div class="row">' + (h.trang_thai !== "bot_dang_lo" ? '<button class="btn btn-sm btn-soft" data-act="ai">' + ic("robot") + "Cho AI trả lời tiếp</button>" : "") +
          (h.trang_thai !== "spam" ? '<button class="btn btn-sm btn-ghost" data-act="spam">Đánh dấu spam</button>' : "") +
          (h.trang_thai === "can_tra_loi_tay" ? '<button class="btn btn-sm btn-ghost" data-act="xong">' + ic("check") + "Đã xử lý</button>" : "") +
          '<button class="btn btn-sm btn-ghost" data-act="chep">' + ic("copy") + "Chép link</button></div>" +
          '<button class="btn btn-sm btn-pri" data-act="xem">' + ic("chat") + "Xem tin</button></div></div>";
      }
      function nap() {
        return DS.api("GET", "/doi-social/hoi-thoai?tab=" + tab).then(function (d) {
          if (!ctx.alive) return;
          var box = el.querySelector("#tn-ds");
          if (d.ok === false) { veTabs({}); box.innerHTML = DS.loiThe(d.error, true); return; }
          ds = DS.list(d, "hoi_thoai");
          veTabs(d.dem);
          if (d.dem) { var n = document.getElementById("n-tin"); if (n) { n.hidden = !d.dem.can_tay; n.textContent = d.dem.can_tay; } }
          if (!ds.length) {
            box.innerHTML = '<div class="card">' + DS.rong(tab === "can_tay" ? "Không có khách nào chờ bạn" : tab === "tiem_nang" ? "Chưa có khách tiềm năng" : "Chưa có hội thoại",
              tab === "can_tay" ? "Bot đang tự trả lời được. Khi có câu khó, đặt hàng hoặc khiếu nại, khách sẽ hiện ở đây." : "Chạy mẫu \"Tự trả lời tin nhắn Messenger\" để bot đọc hộp thư của nick.", "chat") + "</div>";
            return;
          }
          box.innerHTML = ds.map(the).join("");
        });
      }
      function hoi(t) { var id = t.closest("[data-id]").getAttribute("data-id"); return ds.filter(function (x) { return String(x.id) === String(id); })[0]; }
      function doi(h, hd, msg) {
        DS.api("POST", "/doi-social/hoi-thoai/" + h.id, { hanh_dong: hd }).then(function (d) { if (d.ok !== false) { DS.toast(msg, "ok"); nap(); DS.capNhatHuyHieu(); } });
      }
      function xem(h) {
        var m = DS.modal({ title: h.khach_ten || "Hội thoại", wide: true, body: DS.skel(4), foot: false });
        function ve() {
          DS.api("GET", "/doi-social/hoi-thoai/" + h.id).then(function (d) {
            if (d.ok === false) { m.body.innerHTML = DS.rong("Chưa tải được", esc(d.error), "chat"); return; }
            var hh = d.hoi_thoai || d, tin = d.tin || hh.tin || [];
            m.body.innerHTML = '<div class="row-sb mb"><div class="dr-meta" style="margin:0"><span>' + ic("user") + "Nick: " + esc(hh.nick_ten || h.nick_ten || "") + "</span>" +
              (hh.khach_link ? '<a href="' + esc(hh.khach_link) + '" target="_blank" rel="noopener">' + ic("link") + " Trang khách</a>" : "") + "</div>" + DS.bdMap(TT, hh.trang_thai || h.trang_thai) + "</div>" +
              '<div class="msgs" id="tn-msgs">' + (tin.length ? tin.map(function (x) {
                return '<div class="bub ' + (x.tu === "khach" ? "bub-k" : x.tu === "chu" ? "bub-c" : "bub-b") + '"><small>' + esc(TU[x.tu] || x.tu) + " · " + DS.gio(x.luc) + "</small>" + esc(x.noi_dung) + "</div>";
              }).join("") : '<div class="small muted">Chưa có tin nào.</div>') + "</div>" +
              '<div class="sep"></div><div class="fld"><label for="tn-tl">Bạn trả lời</label><textarea class="ta" id="tn-tl" rows="3" placeholder="Gõ câu trả lời. Máy ở nhà gửi qua Messenger của nick, bot nhường hội thoại này 12 giờ."></textarea></div>' +
              '<div class="row mt-s" style="justify-content:flex-end"><button class="btn" data-x>Đóng</button><button class="btn btn-pri" id="tn-gui">' + ic("send") + "Gửi</button></div>";
            var ms = m.body.querySelector("#tn-msgs"); ms.scrollTop = ms.scrollHeight;
            m.body.querySelector("#tn-gui").onclick = function () {
              var nd = m.body.querySelector("#tn-tl").value.trim();
              if (!nd) { DS.toast("Nhập câu trả lời", "err"); return; }
              this.disabled = true;
              DS.api("POST", "/doi-social/hoi-thoai/" + h.id + "/tra-loi", { noi_dung: nd }).then(function (r) {
                if (r.ok === false) { m.body.querySelector("#tn-gui").disabled = false; return; }
                DS.toast("Đã giao máy ở nhà gửi tin", "ok"); ve(); nap(); DS.capNhatHuyHieu();
              });
            };
          });
        }
        ve();
      }
      DS.bind(el, {
        "tai-lai": nap,
        "ai": function (t) { doi(hoi(t), "cho_ai_tiep", "Bot sẽ trả lời tiếp hội thoại này"); },
        "spam": function (t) { doi(hoi(t), "spam", "Đã đánh dấu spam"); },
        "xong": function (t) { doi(hoi(t), "da_xu_ly", "Đã đánh dấu xử lý xong"); },
        "chep": function (t) {
          var h = hoi(t);
          if (!h.khach_link) { DS.toast("Hội thoại này chưa có link", "err"); return; }
          DS.chepChu(h.khach_link).then(function (ok) { DS.toast(ok ? "Đã chép link hội thoại" : "Không chép được, link: " + h.khach_link, ok ? "ok" : "info"); });
        },
        "xem": function (t) { xem(hoi(t)); }
      });
      ctx.every(nap, 30000);
      return nap();
    }
  });
})();
