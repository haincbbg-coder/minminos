const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const src = fs.readFileSync(path.resolve(__dirname, '../../dashboard/conversations.js'), 'utf8');
const ctx = { URL, window: { t: k => k }, Date };
vm.runInNewContext(src.replace('window.JavisConversations =', 'window.testImages = { anhTin, veTin }; window.JavisConversations ='), ctx);
const { anhTin, veTin } = ctx.window.testImages;
const url = 'https://photo-stal-17.zdn.vn/gr/jpg/test/image.jpg';
const old = { message_type: 'image', sender_type: 'customer', text: url, sender_name: '<script>x</script>' };
assert.equal(anhTin(old), url);
assert.equal(anhTin({ ...old, text: 'Caption', metadata: { image_url: url } }), url);
assert.equal(anhTin({ ...old, metadata: { image_url: 'javascript:alert(1)' } }), url);
for (const bad of ['http://photo-stal-17.zdn.vn/a.jpg', 'https://zdn.vn.evil.test/a.jpg', 'https://evil.test/a.jpg', 'https://user:pass@zdn.vn/a.jpg', 'https://zdn.vn:444/a.jpg', 'data:image/png;base64,abc']) {
  assert.equal(anhTin({ ...old, text: bad }), '');
}
assert.equal(anhTin({ ...old, message_type: 'text' }), '');
const html = veTin(old);
assert(html.includes('<img src="'+url+'"'));
assert(html.includes('loading="lazy"'));
assert(html.includes('referrerpolicy="no-referrer"'));
assert(!html.includes('<script>'));
assert(!html.includes('ht-photo-caption'));
const caption = veTin({ ...old, text: '<img src=x onerror=alert(1)>', metadata: { image_url: url } });
assert(caption.includes('&lt;img src=x onerror=alert(1)&gt;'));
assert(!caption.includes('<img src=x'));
assert(veTin({ ...old, message_type: 'text', text: '<b>Hello</b>' }).includes('&lt;b&gt;Hello&lt;/b&gt;'));
console.log('OK: legacy images, metadata, captions and untrusted URL/HTML handling');
