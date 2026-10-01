const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const vm = require('node:vm');
const {createRequire} = require('node:module');
const {EventEmitter} = require('node:events');
const ops = require('../../apps/zalo-forwarder/web/operations');
const rows = [{ts:1,level:'error',msg:'[Shop A] Lỗi gửi'}, {ts:2,level:'ok',msg:'[Shop B] Thành công'}];
assert.equal(ops.filter(rows,'error','shop a').length,1);
assert.equal(ops.filter(rows,'ok','shop a').length,0);
assert.ok(ops.csv([{ts:1,level:'info',msg:'=1+2'}]).includes('"\'=1+2"'));
assert.ok(ops.csv([{ts:1,level:'info',msg:'a,"b"\nc'}]).includes('"a,""b""\nc"'));

// Exercise the real service with a fake network API; no Zalo account or npm install.
const filename = path.resolve(__dirname,'../../apps/zalo-forwarder/core/zalo-service.js');
const actualRequire = createRequire(filename);
const moduleBox = {exports:{}};
vm.runInNewContext(fs.readFileSync(filename,'utf8'), {
 module:moduleBox, require:name => name==='image-size' ? {imageSize:()=>({})} : actualRequire(name),
 setTimeout, clearTimeout, console, Buffer
}, {filename});
const {ZaloService} = moduleBox.exports;
const tick = () => new Promise(r=>setTimeout(r,10));
async function main() {
 const tmp = fs.mkdtempSync(path.join(os.tmpdir(),'zf-ops-'));
 const service = new ZaloService(path.join(tmp,'sessions'),path.join(tmp,'tmp'));
 const listener = new EventEmitter(); listener.start=()=>{}; listener.stop=()=>{};
 const sent=[]; const api={listener,sendMessage:async(payload,dest)=>{sent.push({payload,dest});}};
 service.apis.set('a',api); service.ensureApi=async()=>api; service._threadType=async()=>1;
 service._randDelay=()=>0;
 const logs=[]; service.on('log',r=>logs.push(r));
 const cfg={account:'a',routes:[{name:'test',sources:['source'],destinations:[{threadId:'dest',type:'group'}],forward:{text:true}}]};
 const emit=(id,text='hello')=>listener.emit('message',{threadId:'source',data:{msgId:id,msgType:'webchat',content:text}});
 try {
  await service.startForwarding('a',cfg);
  emit('1');emit('1');await tick();
  assert.equal(sent.length,1,'replayed message ID must not send twice');
  service.pauseForwarding('a'); emit('paused'); await tick();
  service.resumeForwarding('a'); await tick();
  assert.equal(sent.length,1,'paused messages must not silently replay');
  emit('2'); await tick(); assert.equal(sent.length,2,'different ID with identical content is legitimate');
  let release;
  const held = new Promise(r=>release=r);
  service._threadType=()=>held;
  emit('old-1');emit('old-2'); await tick();
  await service.stopForwarding('a');
  assert.equal(listener.listenerCount('error'),0,'stop must remove owned error handler');
  await service.startForwarding('a',cfg);
  release(1);await tick();await tick();
  assert.equal(sent.length,2,'old queued work must not leak into restarted session');
  service._threadType=async()=>1;
  emit('new');await tick();assert.equal(sent.length,3);
  await service.stopForwarding('a');
  // Concurrent starts may only install one listener.
  const starts=await Promise.allSettled([service.startForwarding('a',cfg),service.startForwarding('a',cfg)]);
  assert.equal(starts.filter(r=>r.status==='fulfilled').length,1);
  assert.equal(listener.listenerCount('message'),1);
  let releaseQueue;const stalled=new Promise(r=>releaseQueue=r);
  service._threadType=()=>stalled;
  for(let i=0;i<505;i++)emit('burst-'+i);
  await tick();
  assert.equal(service.forwarders.get('a').pending,500,'queue must be bounded');
  assert.equal(service.forwarders.get('a').dropped,5);
  await service.stopForwarding('a');releaseQueue(1);await tick();
  assert.equal(sent.length,3,'stopped burst must not send');
  console.log('Zalo: duplicate replay, pause, restart, concurrent start, bounded queue, log filter/CSV: OK');
 } finally { await service.stopAll();fs.rmSync(tmp,{recursive:true,force:true}); }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
