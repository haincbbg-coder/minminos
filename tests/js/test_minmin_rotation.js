const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync('dashboard/minmin-galaxy3d.js','utf8');
const controls=source.slice(source.indexOf('  var KHOA_QUAY'),source.indexOf('  // ---------- Nhịp khung hình'));
let stored=null, current=null;
const parent={querySelector:()=>current,appendChild(n){current=n;}};
function node(){const input={addEventListener(k,f){this[k]=f;}}, label={};return {querySelector:s=>s==='input'?input:label,addEventListener(){},remove(){current=null;}};}
const context={giamChuyenDong:true,localStorage:{getItem:()=>stored,setItem:(k,v)=>stored=v},document:{createElement:node}};
vm.createContext(context);vm.runInContext(controls,context);
assert.equal(context.tocDoQuay(),0,'Reduced motion defaults to stationary');
const first={container:{parentElement:parent},__mmCtl:{}};
context.thanhQuay(first);let input=current.querySelector('input'); input.value='6';input.input();
assert.equal(first.__mmCtl.autoRotate,true,'Explicit x6 overrides the reduced motion default');
assert.equal(context.tocDoQuay(),6);
const rebuilt={container:{parentElement:parent},__mmCtl:{}};
context.thanhQuay(rebuilt);input=current.querySelector('input');input.value='0';input.input();
assert.equal(rebuilt.__mmCtl.autoRotate,false,'Rebuilt slider controls the current graph');
assert.equal(first.__mmCtl.autoRotate,true,'Old graph no longer receives slider events');
console.log('OK: explicit rotation and rebuilt controls');
