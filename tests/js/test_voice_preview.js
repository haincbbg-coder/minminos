const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const peers = [], sockets = [], timers = new Map();
let nextTimer = 0;
class Peer {
  constructor() { peers.push(this); this.iceGatheringState = 'complete'; }
  addTrack(track) { this.track = track; }
  createDataChannel(name) { this.channel = {name}; return this.channel; }
  async createOffer() { return {sdp: 'offer'}; }
  async setLocalDescription(value) { this.localDescription = value; }
  async setRemoteDescription(value) { this.remoteDescription = value; }
  close() { this.closed = true; }
}
class Socket {
  constructor(url) { this.url = url; this.sent = []; sockets.push(this); }
  send(data) { this.sent.push(JSON.parse(data)); }
  close() { this.closed = true; if (this.onclose) this.onclose(); }
  async event(data) { await this.onmessage({data: JSON.stringify(data)}); }
}
const track = {stop() {this.stopped = true;}};
let source, suspended = false;
const played=[];
class AudioContext {
  constructor() {this.state = suspended ? 'suspended' : 'running';this.currentTime=0;}
  createBuffer(c,n,r) {const values=new Float32Array(n);return {duration:n/r,getChannelData:()=>values};}
  createBufferSource() {return {connect(){},disconnect(){},start(t){this.at=t;played.push(this);},stop(){this.stopped=true;}};}
  async resume() {if (!suspended) this.state='running';}
  async close() {}
  createMediaStreamDestination() {return {stream: {getAudioTracks: () => [track], getTracks: () => [track]}};}
  createConstantSource() { source = {offset: {value: 1}, connect() {}, start() {}, stop() {this.stopped = true;}, disconnect() {}}; return source; }
}
const context = {window: {addEventListener() {}, AudioContext}, location: {protocol: 'https:', host: 'test'},
  navigator: {}, RTCPeerConnection: Peer, WebSocket: Socket, ArrayBuffer, DataView,
  Audio: class { pause() {} async play() {} },
  setTimeout(fn, ms) { timers.set(++nextTimer, {fn, ms}); return nextTimer; },
  clearTimeout(id) { timers.delete(id); }, encodeURIComponent, console};
vm.runInNewContext(fs.readFileSync('dashboard/voice-preview.js', 'utf8'), context);
(async () => {
  const status = [];
  await context.window.MinMinVoicePreview.play('maple', value => status.push(value));
  const first = sockets[0];
  assert.equal(source.offset.value, 0);
  assert.equal(peers[0].track, track);
  assert.equal(peers[0].channel.name, 'oai-events');
  await first.event({type: 'ready'});
  assert.equal(first.sent[0].type, 'webrtc_offer');
  await first.event({type: 'webrtc_answer', sdp: 'answer'});
  assert.equal(first.sent.length, 1); // No speech before transport is ready.
  peers[0].channel.onopen();
  assert.equal(first.sent[1].type, 'sample');
  await first.event({type: 'turn_done'});
  [...timers.values()].find(timer => timer.ms === 3000).fn();
  assert.ok(first.closed && peers[0].closed && track.stopped && source.stopped);
  assert.equal(timers.size, 0);
  await context.window.MinMinVoicePreview.play('cove', () => {});
  await context.window.MinMinVoicePreview.play('juniper', () => {});
  assert.ok(sockets[1].closed && peers[1].closed);
  await sockets[2].event({type: 'error'});
  assert.ok(sockets[2].closed && peers[2].closed);
  assert.equal(timers.size, 0);
  const peerCount=peers.length;
  await context.window.MinMinVoicePreview.play('Kore', () => {}, 'gemini');
  const gemini=sockets.at(-1);
  assert.ok(gemini.url.includes('provider=gemini'));
  assert.equal(peers.length,peerCount, 'Gemini preview never opens WebRTC or microphone');
  await gemini.event({type:'ready',transport:'pcm'});
  assert.equal(gemini.sent[0].type,'sample');
  await gemini.onmessage({data:new Uint8Array([0]).buffer});
  await gemini.onmessage({data:new Uint8Array([64,0,192]).buffer});
  assert.equal(played.length,0,'Do not play incomplete preview packets');
  await gemini.event({type:'turn_done'});
  assert.equal(played.length,1,'One continuous buffer per preview');
  assert.deepEqual(Array.from(played[0].buffer.getChannelData(0)),[0.5,-0.5]);
  gemini.onclose();
  assert.ok(!gemini.closed, 'Transport close must not cut buffered playback');
  played[0].onended();
  assert.ok(gemini.closed);
  assert.equal(timers.size,0);
  suspended = true;
  const retries = [];
  await context.window.MinMinVoicePreview.play('Kore', s => retries.push(s), 'gemini');
  const blocked = sockets.at(-1), total = sockets.length;
  await blocked.onmessage({data:new Uint8Array([0,64]).buffer});
  await blocked.event({type:'turn_done'});
  blocked.onclose();
  assert.ok(retries.at(-1).includes('Bấm Nghe thử lần nữa'));
  suspended = false;
  await context.window.MinMinVoicePreview.play('Kore', s => retries.push(s), 'gemini');
  assert.equal(sockets.length, total, 'A new gesture reuses the prepared preview');
  assert.equal(played.length,2);
  played[1].onended();
  assert.equal(timers.size,0);
  console.log('OK: preview sends only synthetic silence, selects voice, closes on finish, replacement and errors');
})().catch(error => { console.error(error); process.exitCode = 1; });
