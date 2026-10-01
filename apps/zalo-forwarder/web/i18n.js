"use strict";
/* Đa ngôn ngữ Việt / Anh. */
const I18N = {
  vi: {
    "nav.accounts": "Tài khoản",
    "nav.routes": "Kịch bản",
    "nav.rules": "Mẫu nội dung",
    "nav.ai": "AI & Soạn tin",
    "nav.broadcast": "Đăng nhóm",
    "nav.friends": "Nhắn bạn bè",
    "nav.run": "Chạy & Nhật ký",
    "ai.title": "AI & Soạn tin",
    "ai.sub": "Kết nối ChatGPT / Claude / Gemini để biên tập tin thông minh và soạn nội dung.",
    "bc.title": "Đăng nhóm",
    "bc.sub": "Đăng cùng một nội dung tới nhiều nhóm mình quản trị. Có thể để AI đổi nhẹ câu chữ cho tự nhiên.",
    "fr.title": "Nhắn bạn bè",
    "fr.sub": "Gửi tin tới bạn bè / khách đã kết bạn với shop. Có thể để AI đổi nhẹ câu chữ cho tự nhiên.",
    "brand.sub": "Chuyển tiếp Zalo tự động",
    "foot.warn": "⚠️ Nên dùng tài khoản phụ",
    "foot.copyright": "Bản quyền phần mềm",
    "theme.toggle": "Sáng / Tối",
    "lang.toggle": "EN / VI",

    "acc.title": "Tài khoản",
    "acc.sub": "Đăng nhập Zalo bằng mã QR. Mỗi tài khoản lưu sẵn, lần sau không cần quét lại.",
    "acc.add": "＋ Thêm tài khoản",
    "acc.empty": "Chưa có tài khoản. Bấm “＋ Thêm tài khoản” để đăng nhập.",
    "acc.connected": "Đã kết nối",
    "acc.saved": "Đã lưu (chưa kết nối)",
    "acc.connect": "Kết nối",
    "acc.reconnect": "Kết nối lại",
    "acc.relogin": "Đăng nhập lại (QR)",
    "acc.delete": "Xoá",

    "routes.title": "Kịch bản chuyển tiếp",
    "routes.sub": "Mỗi tuyến: chọn tài khoản, nhóm nguồn để nghe, và nơi nhận. Có tin mới là tự biên tập rồi gửi đi.",
    "routes.add": "＋ Tạo kịch bản",
    "routes.empty": "Chưa có kịch bản nào. Bấm “＋ Tạo kịch bản”.",

    "rules.title": "Mẫu nội dung",
    "rules.sub": "Cách sửa nội dung trước khi gửi: đổi giá, xoá/thay link, đổi tên thương hiệu.",
    "rules.add": "＋ Tạo mẫu",
    "rules.empty": "Chưa có mẫu nào. Bấm “＋ Tạo mẫu”.",

    "run.title": "Chạy & Nhật ký",
    "run.sub": "Bật/tắt từng tuyến, chạy nhiều tài khoản song song, theo dõi hoạt động.",
    "run.startAll": "▶ Bật tất cả",
    "run.stopAll": "■ Dừng tất cả",
    "run.sending": "⚙️ Cài đặt gửi & chống spam",
    "run.log": "📜 Nhật ký hoạt động",
    "run.clearLog": "Xoá nhật ký",
    "run.noRoutes": "Chưa có tuyến nào. Vào tab “Tuyến chuyển tiếp” để tạo.",
    "run.running": "đang chạy",
    "run.stopped": "dừng",
    "run.sent": "gửi",
    "run.start": "▶ Chạy",
    "run.stop": "■ Dừng",

    "common.save": "💾 Lưu",

    "lic.trialBanner": "Bản dùng thử",
    "lic.left": "còn",
    "lic.licensed": "Đã kích hoạt",
    "lic.expires": "Hết hạn",
    "lic.lifetime": "Vĩnh viễn",
    "gate.title": "Kích hoạt bản quyền",
    "gate.trialOn": "Bạn đang dùng thử miễn phí.",
    "gate.trialLeft": "Thời gian dùng thử còn lại:",
    "gate.locked": "Đã hết hạn dùng thử / bản quyền. Vui lòng nhập key để tiếp tục.",
    "gate.machine": "Mã máy của bạn (gửi cho người bán để lấy key):",
    "gate.copy": "Sao chép",
    "gate.server": "Địa chỉ máy chủ bản quyền",
    "gate.serverSave": "Lưu máy chủ",
    "gate.key": "Nhập key kích hoạt",
    "gate.activate": "Kích hoạt",
    "gate.continueTrial": "Tiếp tục dùng thử",
    "gate.close": "Đóng",
    "gate.viewHint": "Bấm vào huy hiệu bản quyền (góc dưới) để mở lại màn hình này.",
    "gate.buy": "Liên hệ người bán để mua key: 1 / 3 / 6 / 12 tháng hoặc vĩnh viễn.",
    "gate.needServer": "Chưa cấu hình máy chủ. Hãy dán địa chỉ máy chủ bản quyền rồi lưu.",
    "gate.reasons": {
      key_not_found: "Key không tồn tại.",
      key_revoked: "Key đã bị thu hồi.",
      key_bound_other_machine: "Key đã dùng cho máy khác.",
      key_expired: "Key đã hết hạn.",
      trial_ended: "Đã hết thời gian dùng thử.",
      server_unreachable: "Không kết nối được máy chủ.",
      no_server: "Chưa cấu hình máy chủ.",
      empty_key: "Vui lòng nhập key.",
    },
  },
  en: {
    "nav.accounts": "Accounts",
    "nav.routes": "Scenarios",
    "nav.rules": "Content templates",
    "nav.ai": "AI & Compose",
    "nav.broadcast": "Broadcast",
    "nav.friends": "Message friends",
    "nav.run": "Run & Logs",
    "ai.title": "AI & Compose",
    "ai.sub": "Connect ChatGPT / Claude / Gemini for smart editing and message composing.",
    "bc.title": "Broadcast",
    "bc.sub": "Post the same content to many groups you manage. AI can lightly vary the wording.",
    "fr.title": "Message friends",
    "fr.sub": "Send messages to friends / customers connected with your shop. AI can lightly vary the wording.",
    "brand.sub": "Auto Zalo forwarding",
    "foot.warn": "⚠️ Use a secondary account",
    "foot.copyright": "Software copyright",
    "theme.toggle": "Light / Dark",
    "lang.toggle": "VI / EN",

    "acc.title": "Accounts",
    "acc.sub": "Log in to Zalo via QR code. Each account is saved so you won't need to scan again.",
    "acc.add": "＋ Add account",
    "acc.empty": "No accounts yet. Click “＋ Add account” to log in.",
    "acc.connected": "Connected",
    "acc.saved": "Saved (not connected)",
    "acc.connect": "Connect",
    "acc.reconnect": "Reconnect",
    "acc.relogin": "Re-login (QR)",
    "acc.delete": "Delete",

    "routes.title": "Forwarding scenarios",
    "routes.sub": "Each route: pick an account, source groups to listen, and destinations. New messages are auto-edited then sent.",
    "routes.add": "＋ New scenario",
    "routes.empty": "No scenarios yet. Click “＋ New scenario”.",

    "rules.title": "Content templates",
    "rules.sub": "How to edit content before sending: change price, remove/replace links, rename brands.",
    "rules.add": "＋ New template",
    "rules.empty": "No templates yet. Click “＋ New template”.",

    "run.title": "Run & Logs",
    "run.sub": "Toggle each route, run multiple accounts in parallel, watch activity.",
    "run.startAll": "▶ Start all",
    "run.stopAll": "■ Stop all",
    "run.sending": "⚙️ Sending & anti-spam settings",
    "run.log": "📜 Activity log",
    "run.clearLog": "Clear log",
    "run.noRoutes": "No routes yet. Go to “Forward routes” to create one.",
    "run.running": "running",
    "run.stopped": "stopped",
    "run.sent": "sent",
    "run.start": "▶ Start",
    "run.stop": "■ Stop",

    "common.save": "💾 Save",

    "lic.trialBanner": "Trial",
    "lic.left": "left",
    "lic.licensed": "Activated",
    "lic.expires": "Expires",
    "lic.lifetime": "Lifetime",
    "gate.title": "Activate license",
    "gate.trialOn": "You are on a free trial.",
    "gate.trialLeft": "Trial time remaining:",
    "gate.locked": "Trial / license expired. Please enter a key to continue.",
    "gate.machine": "Your Machine ID (send it to the seller to get a key):",
    "gate.copy": "Copy",
    "gate.server": "License server address",
    "gate.serverSave": "Save server",
    "gate.key": "Enter activation key",
    "gate.activate": "Activate",
    "gate.continueTrial": "Continue trial",
    "gate.close": "Close",
    "gate.viewHint": "Click the license badge (bottom-left) to reopen this screen.",
    "gate.buy": "Contact the seller to buy a key: 1 / 3 / 6 / 12 months or lifetime.",
    "gate.needServer": "Server not configured. Paste the license server address and save.",
    "gate.reasons": {
      key_not_found: "Key not found.",
      key_revoked: "Key has been revoked.",
      key_bound_other_machine: "Key is already used on another machine.",
      key_expired: "Key has expired.",
      trial_ended: "Trial period has ended.",
      server_unreachable: "Cannot reach the server.",
      no_server: "Server not configured.",
      empty_key: "Please enter a key.",
    },
  },
};

let LANG = "vi";
function setLang(l) {
  LANG = I18N[l] ? l : "vi";
}
function getLang() {
  return LANG;
}
function t(key) {
  const d = I18N[LANG] || I18N.vi;
  return d[key] != null ? d[key] : key;
}
function reason(code) {
  const d = (I18N[LANG] || I18N.vi)["gate.reasons"];
  return (d && d[code]) || code || "";
}
function applyStaticI18n(root) {
  (root || document).querySelectorAll("[data-i18n]").forEach((e) => {
    e.textContent = t(e.getAttribute("data-i18n"));
  });
  (root || document).querySelectorAll("[data-i18n-ph]").forEach((e) => {
    e.setAttribute("placeholder", t(e.getAttribute("data-i18n-ph")));
  });
}

window.i18n = { setLang, getLang, t, reason, applyStaticI18n, LANGS: ["vi", "en"] };
