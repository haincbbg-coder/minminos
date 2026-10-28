const assert=require('node:assert/strict');
const web='../../apps/business-finance/web/';
require(web+'fee-data.js');require(web+'fee-catalog.js');require(web+'profit.js');
const C=MinminFeeCatalog;
assert.equal(C.normalize('mỹ phẩm'),C.normalize('sắc đẹp'));
assert.equal(C.normalize('sắc đẹp'),C.normalize('làm đẹp'));
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);
assert.equal(C.rows('shopee').length,1656);
assert.equal(C.rows('shopee','mall').length,1439);
assert.equal(C.rows('tiktok').length,2040);
assert.equal(C.rows('lazada').length,2829);
for(const market of ['shopee','tiktok','lazada'])for(const shop of ['standard','mall']){
 const rows=C.rows(market,shop);assert.equal(new Set(rows.map(r=>r.id)).size,rows.length);
 for(const r of rows){assert.ok(r.path.length&&r.label);assert.ok(Number.isFinite(r.rate)&&r.rate>=0&&r.rate<=100);assert.ok(Number.isFinite(r.mall)&&r.mall>=0&&r.mall<=100);}
}
const blouse=C.rows('shopee').find(r=>r.path.join(' > ')==='Thời Trang Nữ > Áo > Áo sơ mi');assert.ok(blouse);near(blouse.rate,16.5);
const tk=C.rows('tiktok').find(r=>r.path[1]==='Womenswear & Underwear'&&r.path[3]==='Blouses & Shirts');assert.ok(tk);near(tk.rate,15);near(tk.mall,17.1);
assert.equal(C.build({market:'tiktok',shop:'mall',categoryId:tk.id}).effective,'2026-10-20');
const book=C.rows('lazada','mall').find(r=>r.id==='8577');near(book.mall,13);assert.equal(C.build({market:'lazada',shop:'mall',categoryId:'8577'}).effective,'2026-10-04');
assert.throws(()=>C.build({market:'shopee',categoryId:'not-a-category'}));
assert.throws(()=>C.build({market:'shopee',categoryId:'manual',manualRate:NaN}));
assert.equal(C.build({market:'shopee',categoryId:'manual',manualRate:0}).status,'Người dùng tự cấu hình');
const base={q:100,price:200000,discount:10000,returns:10,cost:0,restock:100,pack:0,ads:0,returnCost:0,fixed:0,shipping:30000,items:1,basketMode:'average',freeMode:'none'};
let p=C.build({market:'lazada',categoryId:'11424'}),r=MinminProfit(base,p);
near(r.fees,3168000);assert.equal(p.rules.length,3);assert.ok(p.rules.every(r=>r.tax===0));
p=C.build({market:'lazada',categoryId:'11424',extras:[{id:'affiliate',kind:'percent',value:10,coverage:20}]});r=MinminProfit(base,p);near(r.feeLines.find(r=>r.name.includes('affiliate')).amount,342000);
// A 3,000 VND fee applies to 90 retained orders plus half of the 10 returned orders.
r=MinminProfit(base,{rules:[{enabled:true,name:'processing',kind:'fixed',value:3000,scope:'success',unit:'order',returnedChargeShare:50,coverage:100}]});near(r.fees,285000);
r=MinminProfit(base,{rules:[{enabled:true,name:'processing',kind:'fixed',value:3000,scope:'success',unit:'order',returnedChargeShare:50,coverage:20}]});near(r.fees,57000);
// Bank discount reduces only the transaction fee basis, not seller revenue.
r=MinminProfit(base,{rules:[{enabled:true,name:'bank',kind:'percent',value:6,base:'netShipping',scope:'success',unit:'order',baseDeduction:10000}]});near(r.fees,1134000);near(r.revenue,19800000);
p=C.build({market:'shopee',categoryId:blouse.id,extras:[{id:'voucher'}]});r=MinminProfit({...base,q:1,returns:0,price:2000000,discount:0,items:2},p);near(r.feeLines.find(r=>r.name==='Voucher Xtra').amount,100000);
// Buyer shipping collected by the platform changes fee basis, never shop revenue.
p=C.build({market:'lazada',categoryId:'11424',buyerShippingExtra:30000});r=MinminProfit({...base,shipping:0},p);near(r.revenue,17100000);near(r.feeLines.find(r=>r.name==='Phí xử lý đơn hàng').amount,1188000);
assert.throws(()=>C.build({market:'lazada',categoryId:'11424',buyerShippingExtra:-1}));
const fresh=C.build({market:'shopee',categoryId:blouse.id});p.rules[0].value=1;assert.equal(fresh.rules[0].value,16.5);assert.equal(fresh.rules.find(r=>r.id==='processing').value,3000);assert.equal(fresh.rules.find(r=>r.id==='processing').effective,'2025-07-01');
console.log('OK: official category coverage, shop separation, dated book overrides, fee basis, optional programs, caps and post-delivery returns');
