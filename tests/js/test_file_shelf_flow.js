// Exercise the actual view/selection transitions, with a minimal DOM (no browser or network).
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Node {
 constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.style={setProperty(){}};this.classList={add(){},remove(){}};this.textContent='';}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k]||null;}
 contains(n){return this.children.includes(n)||this.children.some(x=>x.contains(n));}
 querySelectorAll(){return this.children.filter(n=>n.tagName==='BUTTON');}
 focus(){doc.activeElement=this;}
}
const doc={readyState:'loading',activeElement:null,addEventListener(){},createElement:t=>new Node(t),createElementNS:(_,t)=>new Node(t)};
const win={MinMinFileRules:{},};
const code=fs.readFileSync(require.resolve('../../dashboard/file-shelf.js'),'utf8').replace('  window.MinMinShelf={open,addFiles,addURL};',`  window.qa={moduleAction,showFiles,showTools,showResult,closeWheel,
 setup(rows,ids){items=rows;selected=new Set(ids);launcher=el('button');wheel=el('section');disc=el('div');footer=el('div');heading=el('span');wheelHint=el('p');previewBox=el('div');fileInput=el('input');},
 state(){return {selected:[...selected],wheel,disc,footer,heading,previewBox,drawCurrent};}
 };`);
vm.runInNewContext(code,{window:win,document:doc,localStorage:{getItem:()=> 'off'},URL:{createObjectURL:()=> 'blob:test',revokeObjectURL(){}},console,setTimeout});
const q=win.qa,rows=[{id:'a',name:'one.png',type:'image',source:'sample',blob:{}},{id:'b',name:'two.png',type:'image',source:'sample',blob:{}},{id:'p',name:'source.pdf',type:'pdf',source:'sample',blob:{}}];
(async()=>{
 for(const kind of ['edit','collage','pdf','download']){
  q.setup(rows,kind==='edit'||kind==='download'?['a']:['a','b']);
  await q.moduleAction(kind);
  assert.match(q.state().heading.textContent,/CHỌN FILE/,'tool must select/confirm even with valid old selection');
  assert.ok(q.state().footer.children.some(n=>/Sửa ảnh đã chọn|Ghép ảnh đã chọn|Gộp PDF đã chọn|Xem \/ tải file đã chọn/.test(n.textContent)));
 }
 q.setup(rows,['a','b']);q.showFiles('collage');
 q.state().footer.children.find(n=>n.textContent==='Bỏ chọn tất cả').onclick();
 assert.equal(q.state().selected.length,0);assert.equal(q.state().footer.children[1].disabled,true);
 q.setup(rows,['a']);q.showFiles();q.closeWheel();
 assert.equal(q.state().selected.length,0);assert.equal(q.state().wheel.hidden,true);assert.equal(q.state().previewBox.hidden,true);assert.equal(q.state().drawCurrent,null);
 q.setup(rows,['a','b']);q.showResult(rows[0]);
 assert.equal(q.state().selected.length,0);assert.equal(q.state().previewBox.hidden,false);
 assert.ok(q.state().footer.children.some(n=>n.textContent==='Tải kết quả'));
 q.state().footer.children.find(n=>n.textContent==='Đóng').onclick();assert.equal(q.state().previewBox.hidden,true);
 q.setup(rows,['a']);q.showResult(rows[2]);assert.ok(q.state().footer.children.some(n=>n.textContent==='Tải kết quả'));
 console.log('OK: explicit tool confirmation, clear selection, close preview, result download for images and PDF');
})().catch(e=>{console.error(e);process.exitCode=1;});
