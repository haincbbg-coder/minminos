const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
(async () => {
 const timers = new Map(), captures = []; let id=0;
 function el() { return {value:'',listeners:{},attrs:{},classList:{toggle(){}},
 addEventListener(k,f){this.listeners[k]=f;},dispatchEvent(e){this.listeners[e.type]?.(e);},setAttribute(k,v){this.attrs[k]=v;}}; }
 const input=el(),button=el(),status=el(),document=el(),window=el(); window.t=x=>x;
 class Recognition {
  constructor(){captures.push(this);}
  start(){this.onstart?.();}
  stop(){this.stopped=true;}
  abort(){this.aborted=true;}
  result(text,final=false){const row=[{transcript:text}];row.isFinal=final;this.onresult?.({results:[row]});}
 }
 window.SpeechRecognition=Recognition;
 const ctx={window,document,Event:class{constructor(type){this.type=type;}},setTimeout(fn){timers.set(++id,fn);return id;},clearTimeout(i){timers.delete(i);}};
 vm.createContext(ctx); vm.runInContext(fs.readFileSync('dashboard/voice.js','utf8'),ctx);
 vm.runInContext(fs.readFileSync('dashboard/dictation.js','utf8'),ctx);
 let stopped=0;
 const d=window.MinMinDictation.create({input,button,status,beforeStart:()=>{d.stop();stopped++;},language:()=> 'vi-VN',onError:()=>{}});
 input.value='Xin';input.selectionStart=input.selectionEnd=3;
 await button.listeners.click();const r=captures[0];assert.equal(r.lang,'vi-VN');assert.equal(status.textContent,'dictation.listening');
 r.result('chào');assert.equal(input.value,'Xin chào');
 r.result('chào Min Min');assert.equal(input.value,'Xin chào Min Min');
 r.onend();r.result('hôm nay');assert.equal(input.value,'Xin chào Min Min hôm nay');
 await button.listeners.click();assert.ok(r.stopped && d.active());
 r.result('hôm nay thế nào',true);r.onend();assert.equal(input.value,'Xin chào Min Min hôm nay thế nào');assert.ok(!d.active());
 assert.equal(status.textContent,'dictation.review');
 input.value=''; input.selectionStart=input.selectionEnd=0;
 await button.listeners.click();await button.listeners.click();captures[1].onend();assert.equal(status.textContent,'dictation.empty');
 await button.listeners.click();const old=captures[2].onresult;input.value='Sửa tay';input.dispatchEvent({type:'input'});
 old({results:[[{transcript:'late'}]]});assert.equal(input.value,'Sửa tay');
 await button.listeners.click();captures[3].onerror({error:'network'});assert.equal(status.textContent,'dictation.network');assert.ok(!d.active());
 let release; const pendingButton=el();
 const pending=window.MinMinDictation.create({input,button:pendingButton,status,beforeStart:()=>new Promise(r=>release=r),language:()=> 'vi-VN',onError:()=>{}});
 const count=captures.length;
 const opening=pendingButton.listeners.click();
 document.hidden=true;document.listeners.visibilitychange();
 release();await opening;
 assert.ok(!pending.active());assert.equal(captures.length,count,'leaving during microphone handover must not start capture');
 assert.equal(stopped,4);
 console.log('OK native recognition: live text, rollover, stop-final, empty, late results, errors; no chat transport');
})().catch(e=>{console.error(e);process.exitCode=1;});
