/* Kho group FB - #/nhom-fb?sp=<id> */
(function () {
  "use strict";
  var esc = DS.esc, ic = DS.ic;
  var TT = { cho_duyet: ["Chờ duyệt", "warn"], da_duyet: ["Đã duyệt", "ok"], den: ["Danh sách đen", "err"] };
  var VAO = { da_vao: ["Đã vào", "ok"], cho_duyet: ["Chờ duyệt", "warn"], bi_tu_choi: ["Bị từ chối", "err"] };

  DS.view("nhom-fb", {
    title: "Kho group FB",
    render: function (el, ctx) {
      el.innerHTML = DS.ph("Kho group FB", "Nhóm Facebook theo từng sản phẩm: nick nào phụ trách, nick nào tương tác, đã vào nhóm chưa.") + DS.skel(6);
      var KT = [], NICK = [], TAT_CA = [], sp = ctx.q.sp || "", ds = [];

      Promise.all([DS.layKienThuc(true), DS.layNick(), DS.api("GET", "/doi-social/nhom-fb", null, { quiet: true })]).then(function (a) {
        if (!ctx.alive) return;
        KT = DS.list(a[0], "kien_thuc");
        NICK = DS.list(a[1], "nick");
        TAT_CA = a[2].ok === false ? [] : DS.list(a[2], "nhom");
        if (!KT.length) {
          el.innerHTML = DS.ph("Kho group FB", "Nhóm Facebook theo từng sản phẩm.") + '<div class="card">' +
            DS.rong("Chưa có sản phẩm nào", "Nhóm được xếp theo sản phẩm. Thêm sản phẩm ở Kiến thức cho Agent trước.", "book", '<a class="btn btn-pri" href="#/kien-thuc">' + ic("plus") + "Thêm sản phẩm</a>") + "</div>";
          return;
        }
        if (!sp || !KT.some(function (k) { return String(k.id) === String(sp); })) sp = String(KT[0].id);
        khung();
        nap();
      });

      function thongKe(spId, list) {
        var l = list.filter(function (g) { return String(g.san_pham_id) === String(spId); });
        var duyet = l.filter(function (g) { return g.trang_thai === "da_duyet"; }).length;
        var coNick = l.filter(function (g) { var t = g.tinh_trang_vao || {}; return Object.keys(t).some(function (k) { return t[k] === "da_vao"; }); }).length;
        return { duyet: duyet, coNick: coNick, tong: l.length };
      }
      function tenNick(id) { for (var i = 0; i < NICK.length; i++) if (String(NICK[i].id) === String(id)) return NICK[i].ten; return id ? "Nick " + id : ""; }

      function khung() {
        el.innerHTML = DS.ph("Kho group FB", "Nhóm Facebook theo từng sản phẩm: nick nào phụ trách, nick nào tương tác, đã vào nhóm chưa.",
          '<a class="btn" href="#/kien-thuc">' + ic("plus") + 'Thêm sản phẩm mới</a><button class="btn btn-pri" data-act="mo-them">' + ic("plus") + "Thêm nhóm</button>") +
          '<div class="card"><div class="fgrid"><div class="fld"><label for="nf-sp">Sản phẩm</label><select class="sel" id="nf-sp">' + KT.map(function (k) {
            var t = thongKe(k.id, TAT_CA);
            var duyet = k.so_nhom != null ? k.so_nhom : t.duyet, coNick = k.so_nhom_co_nick != null ? k.so_nhom_co_nick : t.coNick;
            return '<option value="' + esc(k.id) + '"' + (String(k.id) === sp ? " selected" : "") + ">" + esc(k.ten) + " - " + duyet + " nhóm đã duyệt · " + coNick + " đã có nick tham gia</option>";
          }).join("") + '</select></div><div class="fld"><label>Tóm tắt</label><div class="mini" id="nf-tk" style="padding-top:4px"></div></div></div>' +
          '<div id="nf-them" hidden class="mt"><div class="fld"><label for="nf-links">Link nhóm (mỗi dòng một nhóm)</label><textarea class="ta" id="nf-links" rows="4" placeholder="https://www.facebook.com/groups/...&#10;https://www.facebook.com/groups/..."></textarea>' +
          '<div class="hint">Nhóm bạn tự dán được tính là Đã duyệt. Nhóm do mẫu "Tham gia nhóm theo sản phẩm" tự tìm sẽ nằm ở Chờ duyệt để bạn xem trước.</div></div>' +
          '<div class="row mt-s" style="justify-content:flex-end"><button class="btn" data-act="dong-them">Thôi</button><button class="btn btn-pri" data-act="them">Thêm vào kho</button></div></div></div>' +
          '<div class="card card-x mt"><div id="nf-ds"></div></div>';
      }

      function nap() {
        var box = el.querySelector("#nf-ds");
        box.innerHTML = '<div class="tw"><table class="tbl tbl-in"><tbody>' + DS.skelDong(5, 6) + "</tbody></table></div>";
        return DS.api("GET", "/doi-social/nhom-fb" + DS.qs({ san_pham: sp })).then(function (d) {
          if (!ctx.alive) return;
          if (d.ok === false) { box.innerHTML = DS.rong("Chưa tải được", esc(d.error), "list"); return; }
          ds = DS.list(d, "nhom");
          TAT_CA = TAT_CA.filter(function (g) { return String(g.san_pham_id) !== sp; }).concat(ds.map(function (g) { return Object.assign({ san_pham_id: sp }, g); }));
          var t = thongKe(sp, TAT_CA);
          el.querySelector("#nf-tk").innerHTML = "<div><b>" + t.tong + "</b><span>nhóm</span></div><div><b style=\"color:var(--ok)\">" + t.duyet + "</b><span>đã duyệt</span></div><div><b>" + t.coNick + "</b><span>có nick đã vào</span></div>";
          if (!ds.length) { box.innerHTML = DS.rong("Sản phẩm này chưa có nhóm nào", "Bấm Thêm nhóm và dán link nhóm, hoặc chạy mẫu Tham gia nhóm theo sản phẩm để Agent tự tìm.", "list"); return; }
          var opt = function (sel) {
            return '<option value="">Chưa gán</option>' + NICK.map(function (n) { return '<option value="' + esc(n.id) + '"' + (String(n.id) === String(sel) ? " selected" : "") + ">" + esc(n.ten) + "</option>"; }).join("");
          };
          box.innerHTML = '<div class="tw" style="border-top:0"><table class="tbl tbl-in" style="min-width:980px"><thead><tr><th>Nhóm</th><th>Trạng thái</th><th>Nick chính</th><th>Nick tương tác</th><th>Vào nhóm theo nick</th><th>Lần quét</th><th></th></tr></thead><tbody>' +
            ds.map(function (g) {
              var tv = g.tinh_trang_vao || {}, tt = g.nick_tuong_tac || [];
              return '<tr data-id="' + g.id + '"><td style="max-width:260px"><div class="b clip">' + esc(g.ten || "Nhóm chưa rõ tên") + '</div><a class="tiny clip" style="display:block" href="' + esc(g.link) + '" target="_blank" rel="noopener">' +
                esc(String(g.link || "").replace(/^https:\/\/(www\.)?/, "")) + "</a></td>" +
                '<td><select class="sel sel-sm" data-f="trang_thai" style="width:140px">' + Object.keys(TT).map(function (k) { return '<option value="' + k + '"' + (g.trang_thai === k ? " selected" : "") + ">" + TT[k][0] + "</option>"; }).join("") +
                '</select></td><td><select class="sel sel-sm" data-f="nick_chinh" style="width:160px">' + opt(g.nick_chinh) + "</select></td>" +
                '<td><div class="row" style="gap:4px">' + (tt.length ? tt.map(function (id) { return '<span class="bd bd-out">' + esc(tenNick(id)) + "</span>"; }).join("") : '<span class="small muted">Chưa có</span>') +
                '<button class="btn btn-xs btn-ghost" data-act="chon-tt" data-id="' + g.id + '">' + ic("edit") + "</button></div></td>" +
                '<td><div class="row" style="gap:4px">' + (Object.keys(tv).length ? Object.keys(tv).map(function (id) {
                  var x = VAO[tv[id]] || [tv[id], "mu"];
                  return '<span class="bd bd-' + x[1] + '" title="' + esc(x[0]) + '">' + esc(tenNick(id)) + " · " + esc(x[0].toLowerCase()) + "</span>";
                }).join("") : '<span class="small muted">Chưa nick nào vào</span>') + "</div></td>" +
                '<td class="small nw">' + (g.lan_quet ? DS.tuongDoi(g.lan_quet) : '<span class="muted">Chưa quét</span>') + (g.quet_lai_gio ? '<div class="sub">quét lại mỗi ' + g.quet_lai_gio + " giờ</div>" : "") + "</td>" +
                '<td><button class="btn btn-xs btn-dan" data-act="xoa" data-id="' + g.id + '" aria-label="Xoá">' + ic("trash") + "</button></td></tr>";
            }).join("") + "</tbody></table></div>";
        });
      }
      function sua(id, body) {
        return DS.api("PUT", "/doi-social/nhom-fb/" + id, body).then(function (d) { if (d.ok !== false) DS.toast("Đã lưu", "ok"); return d; });
      }
      function nhom(id) { return ds.filter(function (g) { return String(g.id) === String(id); })[0] || {}; }

      el.addEventListener("change", function (e) {
        var t = e.target;
        if (t.id === "nf-sp") { sp = t.value; try { history.replaceState(null, "", "#/nhom-fb?sp=" + encodeURIComponent(sp)); } catch (x) {} nap(); return; }
        var f = t.getAttribute("data-f"), tr = t.closest("tr[data-id]");
        if (!f || !tr) return;
        var b = {}; b[f] = t.value;
        sua(tr.getAttribute("data-id"), b).then(function (d) { if (d.ok !== false) nap(); });
      });
      DS.bind(el, {
        "tai-lai": nap,
        "mo-them": function () { var x = el.querySelector("#nf-them"); if (x) { x.hidden = false; x.querySelector("textarea").focus(); } },
        "dong-them": function () { el.querySelector("#nf-them").hidden = true; },
        "them": function (b) {
          var links = el.querySelector("#nf-links").value.split(/\s*\n\s*/).map(function (s) { return s.trim(); }).filter(Boolean);
          if (!links.length) { DS.toast("Dán ít nhất một link nhóm", "err"); return; }
          var sai = links.filter(function (l) { return l.indexOf("https://") !== 0; });
          if (sai.length) { DS.toast("Link phải bắt đầu bằng https:// (" + sai[0].slice(0, 40) + ")", "err"); return; }
          b.disabled = true;
          DS.api("POST", "/doi-social/nhom-fb", { san_pham_id: isNaN(+sp) ? sp : +sp, links: links }).then(function (d) {
            b.disabled = false;
            if (d.ok === false) return;
            DS.toast("Đã thêm " + ((d.them || d.nhom || []).length || links.length) + " nhóm", "ok");
            el.querySelector("#nf-links").value = ""; el.querySelector("#nf-them").hidden = true; nap();
          });
        },
        "xoa": function (t) {
          var g = nhom(t.getAttribute("data-id"));
          DS.xacNhan('Xoá nhóm "' + (g.ten || g.link) + '" khỏi kho của sản phẩm này?', "Xoá", true).then(function (ok) {
            if (ok) DS.api("DELETE", "/doi-social/nhom-fb/" + g.id).then(function (d) { if (d.ok !== false) { DS.toast("Đã xoá nhóm", "ok"); nap(); } });
          });
        },
        "chon-tt": function (t) {
          var g = nhom(t.getAttribute("data-id")), chon = (g.nick_tuong_tac || []).map(String);
          var m = DS.modal({ title: "Nick tương tác · tối đa 3", body: '<p class="small muted" style="margin:0 0 10px">Nick tương tác vào thích và bình luận tự nhiên dưới bài đội đăng trong nhóm này. Không chọn nick chính.</p><div class="nick-box"><div class="nick-list">' +
            NICK.map(function (n) {
              var on = chon.indexOf(String(n.id)) >= 0, chinh = String(n.id) === String(g.nick_chinh);
              return '<label class="nick-row' + (on ? " on" : "") + '"' + (chinh ? ' style="opacity:.5"' : "") + '><input type="checkbox" class="cb" value="' + esc(n.id) + '"' + (on ? " checked" : "") + (chinh ? " disabled" : "") + ">" +
                DS.av(n.ten) + '<span class="grow">' + esc(n.ten) + (chinh ? ' <span class="tiny muted">(nick chính)</span>' : "") + "</span></label>";
            }).join("") + "</div></div>",
            foot: '<span class="small muted grow" id="tt-dem"></span><button class="btn" data-x>Thôi</button><button class="btn btn-pri" id="tt-luu">Lưu</button>' });
          function dem() {
            var c = m.body.querySelectorAll("input:checked");
            m.foot.querySelector("#tt-dem").textContent = c.length + "/3 đã chọn";
            Array.prototype.forEach.call(m.body.querySelectorAll("input"), function (i) { if (!i.checked && String(i.value) !== String(g.nick_chinh)) i.disabled = c.length >= 3; i.closest(".nick-row").classList.toggle("on", i.checked); });
          }
          dem();
          m.body.addEventListener("change", dem);
          m.foot.querySelector("#tt-luu").onclick = function () {
            var ids = Array.prototype.map.call(m.body.querySelectorAll("input:checked"), function (i) { return i.value; });
            sua(g.id, { nick_tuong_tac: ids }).then(function (d) { if (d.ok !== false) { m.close(); nap(); } });
          };
        }
      });
    }
  });
})();
