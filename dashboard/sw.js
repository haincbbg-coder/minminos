/* Service worker của MinMin - nhận thông báo đẩy, và hiện trang chờ khi máy chủ chưa lên.

   Cố ý KHÔNG cache gì cả. Javis là app tự host, người dùng cập nhật bằng cách kéo bản mới
   rồi tải lại trang; một service worker có cache sẽ phục vụ bản cũ và biến mỗi lần nâng cấp
   thành một cuộc đi tìm "sao sửa rồi mà không thấy đổi". Đổi lại, file này chỉ làm đúng hai
   việc: hiện thông báo, và đưa người dùng về đúng chỗ khi họ bấm vào.

   Phục vụ từ GỐC site qua route /sw.js (xem main.service_worker) để phạm vi điều khiển là "/",
   không phải "/static/". */
/* 26.10.313: TRANG CHỜ khi máy chủ đang khởi động lại.
   Bấm tải lại đúng lúc máy chủ chưa lên (vừa cập nhật, VPS khởi động lại, 4G chập chờn) thì trình
   duyệt hiện trang lỗi trắng của nó và bố phải tự bấm lại. Nay service worker bắt riêng việc MỞ
   TRANG (navigate): mạng lỗi hoặc proxy trả 502/503/504 thì đưa một trang nhỏ viết sẵn ngay trong
   file này, tự hỏi /health mỗi 2 giây và tự vào lại khi máy chủ lên.
   Vẫn đúng tinh thần ở trên: KHÔNG cache gì. Trang chờ là chuỗi trong file, không phải bản chụp
   app; app thật lúc nào cũng tải mới từ máy chủ. Chỉ chạy ở https hoặc localhost (luật của
   trình duyệt cho service worker). */
const TRANG_CHO = `<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MinMin</title>
<style>:root{color-scheme:dark light}body{margin:0;min-height:100vh;display:grid;place-items:center;
font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;background:#12151c;color:#e8eaf0}
@media (prefers-color-scheme:light){body{background:#f6f7fb;color:#1b1f2a}}
.hop{padding:24px;max-width:340px;text-align:center}.vong{width:28px;height:28px;margin:0 auto 16px;
border-radius:50%;border:3px solid currentColor;border-right-color:transparent;opacity:.6;
animation:q 1s linear infinite}@keyframes q{to{transform:rotate(360deg)}}p{margin:6px 0}
.phu{font-size:14px;opacity:.7}</style></head><body><div class="hop"><div class="vong"></div>
<p id="c">Đang kết nối lại máy chủ…</p><p class="phu" id="p">MinMin sẽ tự mở lại khi máy chủ sẵn sàng.</p></div>
<script>(function(){if(!/^vi/i.test(navigator.language||"vi")){document.documentElement.lang="en";
document.getElementById("c").textContent="Reconnecting to the server…";
document.getElementById("p").textContent="MinMin will reopen by itself once the server is ready.";}
function thu(){fetch("/health",{cache:"no-store"}).then(function(r){if(r.ok)location.reload();else setTimeout(thu,2000);},
function(){setTimeout(thu,2000);});}setTimeout(thu,1500);})();</script></body></html>`;

function trangCho() {
  return new Response(TRANG_CHO, { status: 503, headers: { "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store", "Retry-After": "2" } });
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.mode !== "navigate" || req.method !== "GET") return;   // mọi thứ khác: đi thẳng mạng như cũ
  if (new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(fetch(req).then((r) => {
    // 502/503/504 của proxy (máy chủ MinMin chưa lên). Trang lỗi do chính MinMin trả thì giữ nguyên.
    if ([502, 503, 504].includes(r.status) && !(r.headers.get("content-type") || "").includes("json")
        && !r.headers.get("server-timing")) return trangCho();
    return r;
  }, () => trangCho()));
});

self.addEventListener("install", (e) => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch (e) { d = { body: (event.data && event.data.text()) || "" }; }
  const title = d.title || "MinMin";
  const opts = {
    body: d.body || "",
    icon: "/static/icon-192.png",
    badge: "/static/icon-192.png",
    // tag: thông báo cùng tag thì cái mới ĐÈ cái cũ thay vì xếp chồng. Server đặt tag theo
    // id mẩu thư nên mỗi kết quả đúng một dòng, gửi lại không nhân đôi.
    tag: d.tag || "javis",
    data: { url: d.url || "/" },
    renotify: true,
  };
  event.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil((async () => {
    const list = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    // Đã mở Javis ở đâu đó thì FOCUS đúng tab đó rồi nhắn cho nó mở mẩu thư, chứ đừng mở
    // thêm một tab thứ hai - người dùng sẽ có hai bản Javis chạy song song, mỗi bản một
    // hội thoại, và không hiểu vì sao.
    for (const c of list) {
      if (c.url && new URL(c.url).origin === self.location.origin) {
        try { c.postMessage({ type: "javis-open-inbox", url: url }); } catch (e) {}
        return c.focus();
      }
    }
    return self.clients.openWindow(url);
  })());
});
