const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const peers = [], sockets = [], timers = new Map();
let nextTimer = 0;
class Peer {
  constructor() { peers.push(this); this.iceGatheringState = 'complete'; }
  addTransceiver(kind, options) { this.direction = options.direction; }
  createDataChannel(name) { this.channel = name; }
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
const context = {window: {addEventListener() {}}, location: {protocol: 'https:', host: 'test'},
  RTCPeerConnection: Peer, WebSocket: Socket,
  Audio: class { pause() {} async play() {} },
  setTimeout(fn, ms) { timers.set(++nextTimer, {fn, ms}); return nextTimer; },
  clearTimeout(id) { timers.delete(id); }, encodeURIComponent, console};
vm.runInNewContext(fs.readFileSync('dashboard/voice-preview.js', 'utf8'), context);
(async () => {
  const status = [];
  await context.window.MinMinVoicePreview.play('maple', value => status.push(value));
  const first = sockets[0];
  assert.equal(peers[0].direction, 'recvonly');
  assert.equal(peers[0].channel, 'oai-events');
  await first.event({type: 'ready'});
  assert.equal(first.sent[0].type, 'webrtc_offer');
  await first.event({type: 'webrtc_answer', sdp: 'answer'});
  assert.equal(first.sent[1].type, 'sample');
  await first.event({type: 'turn_done'});
  [...timers.values()].find(timer => timer.ms === 3000).fn();
  assert.ok(first.closed && peers[0].closed);
  assert.equal(timers.size, 0);
  await context.window.MinMinVoicePreview.play('cove', () => {});
  await context.window.MinMinVoicePreview.play('juniper', () => {});
  assert.ok(sockets[1].closed && peers[1].closed);
  await sockets[2].event({type: 'error'});
  assert.ok(sockets[2].closed && peers[2].closed);
  assert.equal(timers.size, 0);
  console.log('OK: preview is receive-only, selects voice, closes on finish, replacement and errors');
})().catch(error => { console.error(error); process.exitCode = 1; });
