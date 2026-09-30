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

  // Toa do man phu, hoac null. Co han 4 giay: lan dau trinh duyet hien hop hoi quyen, bo
  // chua bam thi dung de cua so HUD dung cho.
  async function manPhu() {
    if (!("getScreenDetails" in window)) return null;
    try {
      if (navigator.permissions) {
        var st = await navigator.permissions.query({ name: "window-management" }).catch(function () { return null; });
        if (st && st.state === "denied") return null;   // da tu choi: dung hoi lai moi lan bam
      }
      var sd = await Promise.race([window.getScreenDetails(),
        new Promise(function (r) { setTimeout(function () { r(null); }, 4000); })]);
      return sd ? chonManPhu(sd) : null;
    } catch (e) { return null; }
  }

  async function moHud() {
    // Dien thoai / may tinh bang (0.64.88): khong co man phu, mo HUD ngay trong tab nay cho
    // khoi lac tab; muon quay lai thi bam Quay lai cua trinh duyet.
    if (window.matchMedia && window.matchMedia("(max-width: 860px), (pointer: coarse) and (max-width: 1100px)").matches) {
      location.href = "/hud";
      return;
    }
    // Mo cua so NGAY trong luot bam (cho doi hop hoi quyen xong moi mo thi trinh duyet chan
    // cua so bat len), roi moi doi no sang man phu.
    var w = null;
    try { w = window.open(HUD_URL, WIN_NAME, "popup,width=1280,height=760"); } catch (e) {}
    if (!w) {
      alert(t("top.hud_blocked", "Trình duyệt chặn cửa sổ HUD. Bấm lại nút HUD, hoặc cho phép cửa sổ bật lên cho trang này."));
      return;
    }
    var s = await manPhu();
    if (s) {
      try { w.moveTo(s.availLeft, s.availTop); w.resizeTo(s.availWidth, s.availHeight); } catch (e) {}
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
