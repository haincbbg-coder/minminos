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
