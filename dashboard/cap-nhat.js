/* cap-nhat.js - NÚT CẬP NHẬT ngay trên thanh bên, dưới nhóm Thiết lập (26.10.1).
 *
 * Chủ repo muốn: bấm một nút là cập nhật, app hỏi "đồng ý hay không" trước; và mỗi khi có
 * bản mới thì app TỰ BÁO chứ không phải vào Cài đặt > Cập nhật mới biết.
 *
 * - Hỏi /version lúc mở app và mỗi 30 phút. Có bản mới: nút hiện chấm đỏ + số phiên bản, và
 *   một thẻ báo nổi lên ở góc (mỗi phiên bản báo một lần, bấm "Để sau" là thôi).
 * - Bấm nút: hộp thoại nói đang dùng bản nào, bản mới là gì, và hai nút Đồng ý / Không.
 * - Đồng ý: POST /update rồi theo dõi /version tới khi số phiên bản đổi thì tải lại trang.
 *   Máy không tự cập nhật được (Docker thiếu Watchtower) thì nói rõ lệnh phải chạy.
 * Không dùng ký tự em dash. */
(function () {
  "use strict";
  var NHIP_KIEM = 30 * 60 * 1000;
  var KHOA_DA_BAO = "mm.capnhat.da_bao";
  var _v = null;          // kết quả /version gần nhất
  var _nut = null, _dangCap = false;

  function t(k, b) { return window.t ? window.t(k, b) : k; }
  function ic(n) { return window.ic ? window.ic(n) : ""; }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  async function kiem() {
    try {
      var r = await fetch("/version", { cache: "no-store" });
      if (!r.ok) return null;
      _v = await r.json();
    } catch (e) { return null; }
    veNut();
    if (_v && _v.update_available && _v.latest) baoMot(_v.latest);
    return _v;
  }

  function veNut() {
    if (!_nut) return;
    var co = !!(_v && _v.update_available);
    _nut.classList.toggle("co-moi", co);
    _nut.title = co ? t("capnhat.co_moi", { ban: _v.latest }) : t("capnhat.kiem");
    _nut.querySelector(".cn-chu").textContent = co ? t("capnhat.nut_co", { ban: _v.latest }) : t("capnhat.nut");
  }

  function dungNut() {
    var rail = document.querySelector("nav.rail");
    var truoc = document.getElementById("railLangWrap") || (rail && rail.querySelector(".rail-foot"));
    if (!rail || !truoc || document.getElementById("railCapNhat")) return;
    _nut = document.createElement("button");
    _nut.type = "button";
    _nut.id = "railCapNhat";
    _nut.className = "rail-capnhat";
    _nut.innerHTML = '<span class="cn-ic">' + ic("download") + '<i class="cn-cham"></i></span><span class="cn-chu"></span>';
    _nut.onclick = function () { moHop(); };
    truoc.parentNode.insertBefore(_nut, truoc);
    veNut();
  }

  // ---- thẻ báo có bản mới (một lần mỗi phiên bản) ----
  function baoMot(ban) {
    var da = "";
    try { da = localStorage.getItem(KHOA_DA_BAO) || ""; } catch (e) {}
    if (da === ban || document.getElementById("cnBao")) return;
    var the = document.createElement("div");
    the.id = "cnBao";
    the.className = "cn-bao";
    the.setAttribute("role", "status");
    the.innerHTML = '<div class="cn-bao-ic">' + ic("download") + '</div>' +
      '<div class="cn-bao-nd"><b>' + esc(t("capnhat.bao_tieu_de")) + '</b>' +
      '<span>' + esc(t("capnhat.bao_than", { ban: ban, cu: (_v && _v.current) || "?" })) + '</span>' +
      '<div class="cn-bao-nut"><button class="s-btn" data-cn="cap">' + esc(t("capnhat.cap_ngay")) + '</button>' +
      '<button class="s-btn-ghost" data-cn="sau">' + esc(t("capnhat.de_sau")) + '</button></div></div>';
    document.body.appendChild(the);
    var dong = function () {
      try { localStorage.setItem(KHOA_DA_BAO, ban); } catch (e) {}
      the.remove();
    };
    the.querySelector('[data-cn="sau"]').onclick = dong;
    the.querySelector('[data-cn="cap"]').onclick = function () { dong(); moHop(); };
  }

  // ---- hộp thoại Đồng ý / Không ----
  function hop(noiDung, nut) {
    var cu = document.getElementById("cnHop");
    if (cu) cu.remove();
    var o = document.createElement("div");
    o.id = "cnHop";
    o.className = "cn-hop-nen";
    o.innerHTML = '<div class="cn-hop" role="dialog" aria-modal="true" aria-labelledby="cnHopTieuDe">' +
      '<div class="cn-hop-dau" id="cnHopTieuDe">' + ic("download") + ' ' + esc(t("capnhat.tieu_de")) + '</div>' +
      '<div class="cn-hop-than">' + noiDung + '</div>' +
      '<div class="cn-hop-chan">' + (nut || []).map(function (n, i) {
        return '<button type="button" class="' + (n.chinh ? "s-btn" : "s-btn-ghost") + '" data-i="' + i + '">' + esc(n.chu) + '</button>';
      }).join("") + '</div></div>';
    document.body.appendChild(o);
    o.addEventListener("click", function (e) { if (e.target === o && !_dangCap) o.remove(); });
    (nut || []).forEach(function (n, i) {
      o.querySelector('[data-i="' + i + '"]').onclick = function () { if (n.bam) n.bam(o); else o.remove(); };
    });
    var dau = o.querySelector(".cn-hop-chan button");
    if (dau) dau.focus();
    return o;
  }
  function thanHop(o, html, nut) {
    o.querySelector(".cn-hop-than").innerHTML = html;
    var chan = o.querySelector(".cn-hop-chan");
    chan.innerHTML = (nut || []).map(function (n, i) {
      return '<button type="button" class="' + (n.chinh ? "s-btn" : "s-btn-ghost") + '" data-i="' + i + '">' + esc(n.chu) + '</button>';
    }).join("");
    (nut || []).forEach(function (n, i) {
      chan.querySelector('[data-i="' + i + '"]').onclick = function () { if (n.bam) n.bam(o); else o.remove(); };
    });
  }

  async function moHop() {
    if (_dangCap) return;
    var o = hop('<p>' + ic("loader") + ' ' + esc(t("capnhat.dang_kiem")) + '</p>', []);
    var v = await kiem();
    if (!v) {
      thanHop(o, '<p>' + esc(t("capnhat.loi_kiem")) + '</p>', [{ chu: t("capnhat.dong"), chinh: true }]);
      return;
    }
    if (!v.update_available) {
      thanHop(o, '<p>' + esc(t("capnhat.moi_nhat", { ban: v.current })) + '</p>' +
        (v.error ? '<p class="cn-phu">' + esc(t("capnhat.chua_so")) + '</p>' : ""),
        [{ chu: t("capnhat.dong"), chinh: true }]);
      return;
    }
    var html = '<p>' + t("capnhat.hoi", { moi: "<b>v" + esc(v.latest) + "</b>", cu: "v" + esc(v.current) }) + '</p>' +
      '<p class="cn-phu">' + esc(t("capnhat.luu_y")) + '</p>';
    if (!v.can_self_update) {
      thanHop(o, html + '<p class="cn-canh">' + esc(t("capnhat.tay")) + '</p><code class="cn-lenh">docker compose up -d --pull always</code>',
        [{ chu: t("capnhat.dong"), chinh: true }]);
      return;
    }
    thanHop(o, html, [
      { chu: t("capnhat.dong_y"), chinh: true, bam: function () { chay(o, v); } },
      { chu: t("capnhat.khong") },
    ]);
  }

  async function chay(o, v) {
    _dangCap = true;
    var cu = v.current;
    thanHop(o, '<p>' + ic("loader") + ' ' + esc(t("capnhat.dang_cap", { ban: v.latest })) + '</p>', []);
    var resp = null;
    try { resp = await (await fetch("/update", { method: "POST" })).json(); } catch (e) { resp = { ok: true }; }
    if (resp && resp.ok === false) {
      _dangCap = false;
      thanHop(o, '<p class="cn-canh">' + esc(resp.error || t("capnhat.loi")) + '</p>' +
        (resp.manual ? '<code class="cn-lenh">' + esc(resp.manual) + '</code>' : ""),
        [{ chu: t("capnhat.dong"), chinh: true }]);
      return;
    }
    var lan = 0;
    var hen = setInterval(async function () {
      lan++;
      var moi = null;
      try { moi = await (await fetch("/version", { cache: "no-store" })).json(); } catch (e) {}
      if (moi && moi.current && moi.current !== cu) {
        clearInterval(hen);
        thanHop(o, '<p>' + esc(t("capnhat.xong", { ban: moi.current })) + '</p>', []);
        setTimeout(function () { location.reload(); }, 1500);
        return;
      }
      if (lan >= 60) {
        clearInterval(hen);
        _dangCap = false;
        thanHop(o, '<p class="cn-canh">' + esc(t("capnhat.lau")) + '</p>', [{ chu: t("capnhat.dong"), chinh: true }]);
      }
    }, 3000);
  }

  function init() {
    dungNut();
    kiem();
    setInterval(function () { if (!document.hidden && !_dangCap) kiem(); }, NHIP_KIEM);
    window.addEventListener("javis:i18n", veNut);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();

  window.MinMinCapNhat = { kiem: kiem, mo: moHop };
})();
