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
let source;
class AudioContext {
  constructor() {this.state = 'running';this.currentTime=0;}
  createBuffer(c,n,r) {return {duration:n/r,getChannelData:()=>new Float32Array(n)};}
  createBufferSource() {return {connect(){},disconnect(){},start(t){this.at=t;},stop(){this.stopped=true;}};}
  async resume() {}
  async close() {}
  createMediaStreamDestination() {return {stream: {getAudioTracks: () => [track], getTracks: () => [track]}};}
  createConstantSource() { source = {offset: {value: 1}, connect() {}, start() {}, stop() {this.stopped = true;}, disconnect() {}}; return source; }
}
const context = {window: {addEventListener() {}, AudioContext}, location: {protocol: 'https:', host: 'test'},
  RTCPeerConnection: Peer, WebSocket: Socket, ArrayBuffer, DataView,
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
  await gemini.onmessage({data:new ArrayBuffer(4800)});
  await gemini.event({type:'turn_done'});
  [...timers.values()].find(timer=>timer.ms===3000).fn();
  assert.ok(gemini.closed);
  assert.equal(timers.size,0);
  console.log('OK: preview sends only synthetic silence, selects voice, closes on finish, replacement and errors');
})().catch(error => { console.error(error); process.exitCode = 1; });
