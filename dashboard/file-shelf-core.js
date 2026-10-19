/* Pure file rules shared by the shelf and offline regression tests. */
(function (root) {
  'use strict';
  const MAX_FILE = 20 * 1024 * 1024, MAX_TOTAL = 100 * 1024 * 1024, MAX_COUNT = 40;
  function kind(name, type) {
    if (/^image\/(png|jpeg|webp)$/.test(type)) return 'image';
    if (type === 'application/pdf') return 'pdf';
    return 'file';
  }
  function safeURL(raw, base) {
    try {
      const u = new URL(raw, base), origin = new URL(base).origin;
      if (u.username || u.password) return '';
      if (u.origin === origin && /^https?:$/.test(u.protocol)) return u.href;
      if (u.protocol === 'https:' && (!u.port || u.port === '443') && /(^|\.)zdn\.vn$/i.test(u.hostname)) return u.href;
    } catch (_) {}
    return '';
  }
  function validate(items, blob) {
    if (!blob.size) throw Error('File trống.');
    if (blob.size > MAX_FILE) throw Error('Mỗi file tối đa 20 MB.');
    if (items.length >= MAX_COUNT) throw Error('Khay tối đa 40 file. Bỏ bớt file rồi thêm lại.');
    if (items.reduce((n, x) => n + x.blob.size, 0) + blob.size > MAX_TOTAL) throw Error('Khay tối đa 100 MB. Bỏ bớt file rồi thêm lại.');
  }
  function move(items, id, delta) {
    const out = items.slice(), i = out.findIndex(x => x.id === id), j = i + delta;
    if (i >= 0 && j >= 0 && j < out.length) [out[i], out[j]] = [out[j], out[i]];
    return out;
  }
  function crop(w, h, ratio) {
    if (!ratio) return {x:0, y:0, w, h};
    const cw = Math.min(w, h * ratio), ch = cw / ratio;
    return {x:(w-cw)/2, y:(h-ch)/2, w:cw, h:ch};
  }
  function nameCopy(name, ext) { return String(name || 'tep').replace(/\.[^.]+$/, '') + '-ban-sao.' + ext; }
  const api = {MAX_FILE, MAX_TOTAL, MAX_COUNT, kind, safeURL, validate, move, crop, nameCopy};
  root.MinMinFileRules = api;
  if (typeof module !== 'undefined') module.exports = api;
})(typeof window === 'undefined' ? globalThis : window);
