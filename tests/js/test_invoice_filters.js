const assert = require('node:assert/strict');
const ui = require('../../apps/tai-hoa-don/web/invoice-ui.js');
assert.deepEqual(ui.period('m2',2024),['2024-02-01','2024-02-29']);
assert.deepEqual(ui.period('h1',2026),['2026-01-01','2026-06-30']);
assert.deepEqual(ui.period('h2',2026),['2026-07-01','2026-12-31']);
assert.deepEqual(ui.period('q4',2026),['2026-10-01','2026-12-31']);
assert.deepEqual(ui.period('last7',2026,new Date(2026,0,3)),['2025-12-28','2026-01-03']);
assert.deepEqual(ui.period('week',2026,new Date(2026,9,4)),['2026-09-28','2026-10-04']);
const rows=[{id:'a',ban_ten:'Đức Trung',so:10,tong:100,ngay_hd:'2026-09-30',co_pdf:true},
 {id:'b',ban_ten:'Ánh',so:2,tong:9,ngay_hd:'2026-09-01'},
 {id:'c',ban_ten:'Bình',so:20,tong:20,ngay_mail:'Tue, 01 Sep 2026 10:00:00 +0700'}];
assert.deepEqual(ui.filter(rows,{sort:'amount-asc'}).map(r=>r.id),['b','c','a']);
assert.deepEqual(ui.filter(rows,{sort:'number-asc'}).map(r=>r.id),['b','a','c']);
assert.equal(ui.filter(rows,{supplier:'duc',min:'50',max:'100'})[0].id,'a');
assert.equal(ui.filter(rows,{from:'2026-09-02',to:'2026-09-30',file:'pdf'}).length,1);
assert.equal(ui.filter(rows,{from:'2027-01-01'}).length,0);
assert.equal(rows[0].id,'a','filter must not reorder source rows');
console.log('invoice date presets, filter intersections, amount/number sort: OK');
{
 const docs = [
  {so:'1',doi_tac:'NGÂN HÀNG TMCP Á CHÂU',tong:100,co_goc:true},
  {so:'2',ban_ten:'Chi nhánh Ngân hàng Vietcombank',tong:200},
  {so:'3',doi_tac:'CÔNG TY MAY ABC',ngan_hang:'ACB',tong:300},
  {so:'4',doi_tac:'ACB',mst_doi_tac:'0301452948-001',tong:400},
  {so:'5',tu:'Techcombank <invoice@techcombank.com.vn>',tong:500},
  {so:'6',doi_tac:'CÔNG TY CỔ PHẦN ACB LOGISTICS',tong:600}
 ];
 assert.deepEqual(ui.filter(docs,{group:'bank',sort:'number-asc'}).map(r=>r.so),['1','2','4','5']);
 assert.deepEqual(ui.filter(docs,{group:'business',sort:'number-asc'}).map(r=>r.so),['3','6']);
 assert.deepEqual(ui.filter(docs,{group:'bank',file:'no-original',max:250}).map(r=>r.so),['2']);
 assert.equal(ui.filter(docs,{}).length,6);
 assert.equal(ui.isBank({}),false);
}
{
 const stages=['no-xml','pending','failed','done'];
 const records=stages.map((stage,i)=>({so:String(i),goc_trang_thai:stage,can_tai_tay:stage!=='done'}));
 for(const status of stages) assert.equal(ui.filter(records,{status})[0].goc_trang_thai,status);
 assert.equal(ui.filter(records,{status:'manual'}).length,3);
 assert.equal(ui.filter(records,{status:'failed',number:'0'}).length,0);
}

// Original PDF must never satisfy the tax-rendering filter (and vice versa).
{
 const docs = [
  {so:'1',co_xml:true,co_pdf:true,co_trong_dong:true,co_goc:false},
  {so:'2',co_xml:false,co_pdf:true,co_trong_dong:false,co_goc:true},
  {so:'3',co_xml:true,co_trong_dong:true,co_goc:true},
  {so:'4'}
 ];
 for (const [file, expected] of Object.entries({xml:['1','3'],'no-xml':['2','4'],tax:['1','3'],'no-tax':['2','4'],original:['2','3'],'no-original':['1','4']})) {
  assert.deepEqual(ui.filter(docs,{file,sort:'number-asc'}).map(r=>r.so),expected,file);
 }
 assert.deepEqual(ui.filter(docs,{file:'no-original',number:'1'}).map(r=>r.so),['1']);
}

// Publisher and manual filters intersect; unknown publishers remain selectable.
{
 const ui = require('../../apps/tai-hoa-don/web/invoice-ui.js');
 const rows = [{so:'1',nha_cung_cap:'bkav',can_tai_tay:true},{so:'2',nha_cung_cap:'bkav',can_tai_tay:false},{so:'3',nha_cung_cap:'easyinvoice',can_tai_tay:true},{so:'4',can_tai_tay:true}];
 require('assert').deepStrictEqual(ui.filter(rows,{publisher:'bkav',status:'manual'}).map(r=>r.so),['1']);
 require('assert').deepStrictEqual(ui.filter(rows,{publisher:'unknown',status:'manual'}).map(r=>r.so),['4']);
}
