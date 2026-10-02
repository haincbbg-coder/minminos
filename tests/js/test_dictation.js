const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const captures = [], timers = new Map(); let id = 0, callsStopped = 0;
function el() { return { value: '', listeners: {}, attrs: {}, classList: {toggle() {}},
 addEventListener(n, fn) { this.listeners[n] = fn; },
 dispatchEvent(e) { this.listeners[e.type]?.(e); },
 setAttribute(k,v) {this.attrs[k] = v;} }; }
const input = el(), button = el(), status = el(), document = el(), window = el();
window.t = x => x;
class Voice {
 constructor(opts) { this.opts = opts; this.recognition = {}; captures.push(this); }
 isSupported() { return true; }
 startListening() { this.started = true; }
 cancelListening() { this.cancelled = true; this.opts.onInterim(''); }
}
const ctx = { window, document, JavisVoice: Voice, Event: class {constructor(type) {this.type=type;}},
 setTimeout(fn) {timers.set(++id,fn);return id;}, clearTimeout(i) {timers.delete(i);} };
vm.runInNewContext(fs.readFileSync('dashboard/dictation.js','utf8'),ctx);
const d = window.MinMinDictation.create({input,button,status,beforeStart:()=>callsStopped++,language:()=> 'vi-VN',onError:()=>{}});
input.value='Xin'; input.selectionStart=input.selectionEnd=3;
button.listeners.click(); const first=captures[0];
assert.ok(first.opts.inputOnly && first.managedEndpoint && first.started);
first.opts.onInterim('chào'); assert.equal(input.value,'Xin chào');
first.opts.onInterim('chào Min Min'); assert.equal(input.value,'Xin chào Min Min');
assert.ok(d.active()); // no silence callback or automatic assistant call
button.listeners.click(); assert.ok(!d.active() && first.cancelled);
first.opts.onTranscript('late final'); assert.equal(input.value,'Xin chào Min Min');
input.selectionStart=input.selectionEnd=input.value.length;
button.listeners.click(); first.opts.onInterim('old capture');
assert.equal(input.value,'Xin chào Min Min');
captures[1].opts.onInterim('hôm nay'); assert.equal(input.value,'Xin chào Min Min hôm nay');
input.value='Tự sửa'; input.dispatchEvent({type:'input'});
assert.ok(!d.active()); captures[1].opts.onTranscript('late'); assert.equal(input.value,'Tự sửa');
input.selectionStart=input.selectionEnd=input.value.length;
button.listeners.click(); captures[2].opts.onInterim('giữ lại');
document.hidden=true; document.listeners.visibilitychange();
assert.ok(!d.active() && captures[2].cancelled); assert.equal(input.value,'Tự sửa giữ lại');
document.hidden=false; input.selectionStart=input.selectionEnd=input.value.length;
button.listeners.click(); [...timers.values()][0](); assert.ok(!d.active());
assert.equal(timers.size,0); assert.equal(callsStopped,4);
const app=fs.readFileSync('dashboard/app.js','utf8');
assert.match(app,/function sendMessage\(text, opts\) \{\s*dictation.stop\(\)/);
assert.match(app,/callBtn.addEventListener\("click", \(\) => \{\s*dictation.stop\(\)/);
assert.ok(!/voiceBtn.addEventListener/.test(app));
console.log('OK: dictation drafts only; pauses, stop, editing, timeout and late events cannot submit or corrupt drafts');
