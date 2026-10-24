// Chạy trong trang Pancake (world MAIN): nghe phản hồi JSON của chính Pancake, không gọi thêm máy chủ nào.
// Chỉ chuyển cho content.js những phản hồi có dạng danh sách hội thoại hoặc tin nhắn.
(function () {
  if (window.__mmGyHook) return;
  window.__mmGyHook = true;
  const KHOP = /\/(conversations|messages)(\/|\?|$)|\/conversations\b/;
  function gui(url, text) {
    try {
      if (!text || text.length > 8e6 || text[0] !== "{") return;
      window.postMessage({ nguon: "mm-gy", url: String(url).replace(/access_token=[^&]+/, "access_token=*"), body: text }, "*");
    } catch (e) {}
  }
  const of = window.fetch;
  window.fetch = async function (...a) {
    const r = await of.apply(this, a);
    try {
      const u = String((a[0] && a[0].url) || a[0] || "");
      if (KHOP.test(u)) r.clone().text().then((t) => gui(u, t)).catch(() => {});
    } catch (e) {}
    return r;
  };
  const oo = XMLHttpRequest.prototype.open, os = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) { this.__mmU = String(u); return oo.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function () {
    this.addEventListener("load", () => {
      try { if (KHOP.test(this.__mmU) && (this.responseType === "" || this.responseType === "text")) gui(this.__mmU, this.responseText); } catch (e) {}
    });
    return os.apply(this, arguments);
  };
})();
