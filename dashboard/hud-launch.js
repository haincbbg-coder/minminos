// MinMin OS - nút "HUD màn phụ" trên thanh trên cùng (0.64.82).
//
// Mở /hud thành một cửa sổ riêng. Trình duyệt có Window Management API (Chrome/Edge trên máy
// tính) thì đặt cửa sổ đó sẵn lên màn KHÔNG phải màn đang xem - thường là màn phụ như Arzopa -
// và HUD tự vào toàn màn hình khi bố bấm "Bật MinMin". Không có API đó (Firefox, Safari, điện
// thoại) thì vẫn mở HUD ở cửa sổ mới, bố kéo sang màn phụ rồi bấm đúp để toàn màn hình.
//
// Lần đầu Chrome hỏi quyền "Quản lý cửa sổ trên mọi màn hình": chọn Cho phép. Hỏi quyền làm
// mất lượt bấm của người dùng nên cửa sổ có thể bị chặn ở lần bấm đầu; lần sau đã có quyền
// thì mở ngay.
(function () {
  "use strict";
  if (typeof window === "undefined") return;
  var HUD_URL = "/hud?fs=1";
  var WIN_NAME = "minmin-hud";

  function t(k, fb) { try { var s = window.t && window.t(k); return s && s !== k ? s : fb; } catch (e) { return fb; } }

  // Chọn màn để đặt HUD: màn khác màn đang xem, ưu tiên màn không phải màn chính.
  function chonManPhu(sd) {
    var cur = sd.currentScreen;
    var khac = sd.screens.filter(function (s) { return s !== cur; });
    return khac.find(function (s) { return !s.isPrimary; }) || khac[0] || null;
  }

  async function vitriManPhu() {
    if (!("getScreenDetails" in window)) return "";
    try {
      // Đã từ chối quyền thì đừng hỏi lại mỗi lần bấm.
      if (navigator.permissions) {
        var st = await navigator.permissions.query({ name: "window-management" }).catch(function () { return null; });
        if (st && st.state === "denied") return "";
      }
      var sd = await window.getScreenDetails();
      var s = chonManPhu(sd);
      if (!s) return "";
      return ",left=" + s.availLeft + ",top=" + s.availTop + ",width=" + s.availWidth + ",height=" + s.availHeight;
    } catch (e) { return ""; }
  }

  async function moHud() {
    var viTri = await vitriManPhu();
    var w = null;
    try { w = window.open(HUD_URL, WIN_NAME, "popup" + viTri); } catch (e) {}
    if (!w) {
      var msg = t("top.hud_blocked", "Trình duyệt chặn cửa sổ HUD. Bấm lại nút HUD, hoặc cho phép cửa sổ bật lên cho trang này.");
      alert(msg);
      return;
    }
    try { w.focus(); } catch (e) {}
  }

  function gan() {
    var b = document.getElementById("hudLaunchBtn");
    if (!b || b.dataset.ganHud) return;
    b.dataset.ganHud = "1";
    b.addEventListener("click", function (e) { e.preventDefault(); moHud(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", gan); else gan();
  window.MinMinMoHud = moHud;
})();
