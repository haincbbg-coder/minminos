const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../../dashboard/theme.js'),'utf8');
function page(saved={}, blocked=false, hour=12) {
  const store=new Map(Object.entries(saved)), attrs={}, events={}, ready={}, clicks={};
  const root={setAttribute:(k,v)=>attrs[k]=v,removeAttribute:k=>delete attrs[k],getAttribute:k=>attrs[k]??null};
  const button={setAttribute(){},addEventListener:(k,fn)=>clicks[k]=fn};
  const meta={setAttribute(){}};
  const document={documentElement:root,readyState:'loading',head:{appendChild(){}},querySelector:()=>meta,createElement:()=>meta,
    getElementById:()=>button,addEventListener:(k,fn)=>ready[k]=fn};
  const window={addEventListener:(k,fn)=>(events[k]??=[]).push(fn),dispatchEvent:e=>(events[e.type]||[]).forEach(fn=>fn(e))};
  const localStorage={getItem:k=>{if(blocked)throw Error('blocked');return store.get(k)??null;},setItem:(k,v)=>{if(blocked)throw Error('blocked');store.set(k,v);}};
  vm.runInNewContext(source,{document,window,localStorage,setInterval(){},Date:class extends Date{constructor(...args){super(...(args.length?args:[2026,9,5,hour,0,0]));}},CustomEvent:class{constructor(type,o){this.type=type;this.detail=o.detail;}}});
  return {window,attrs,store,boot:()=>ready.DOMContentLoaded(),click:()=>clicks.click(),storage:(v)=>{if(v===null)store.delete('javis.theme');else store.set('javis.theme',v);window.dispatchEvent({type:'storage',key:'javis.theme',newValue:v});}};
}
const light=page();
assert.equal(light.attrs['data-theme'],'light','theme applied before DOMContentLoaded');
light.boot();light.click();assert.equal(light.window.javisTheme.isLight(),false);assert.equal(light.store.get('javis.theme'),'dark');
const hud=page(Object.fromEntries(light.store));hud.boot();assert.equal(hud.window.javisTheme.isLight(),false,'new page follows persisted theme');
light.click();hud.storage(light.store.get('javis.theme'));assert.equal(hud.window.javisTheme.isLight(),true,'open HUD follows another tab');
hud.storage(null);assert.equal(hud.window.javisTheme.isLight(),true,'clearing preference restores scheduled daylight default');
const denied=page({},true);denied.boot();denied.click();assert.equal(denied.window.javisTheme.isLight(),false,'theme usable with storage disabled');
console.log('PASS shared theme: first paint, toggle, persistence, cross-tab sync, storage disabled');

const night=page({},false,23);night.boot();assert.equal(night.window.javisTheme.isLight(),false,"new device follows automatic nighttime theme");
