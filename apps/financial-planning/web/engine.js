/* Independent management model. Money: VND, prices exclude VAT. No HCW code. */
(function(root){
'use strict';
const copy=x=>JSON.parse(JSON.stringify(x));
const sum=a=>a.reduce((s,x)=>s+x,0);
const ratio=(a,b)=>b===0?null:a/b;
function blank(){return {schema:1,name:'Kế hoạch mới',year:new Date().getFullYear(),openingCash:0,openingAR:0,openingAP:0,collectionLag:0,paymentLag:0,taxRate:0,products:[],months:Array.from({length:12},()=>({fixed:0,variableRate:0,depreciation:0,interest:0,capex:0,principal:0,financing:0,actualRevenue:null,actualProfit:null,locked:false})),status:'draft'};}
function validate(p){
 if(!p||p.schema!==1||typeof p.name!=='string'||p.name.length>160||!Number.isInteger(p.year)||p.year<2000||p.year>2200)throw Error('Hồ sơ kế hoạch không hợp lệ.');
 const n=(v,min=0,max=1e15)=>{if(typeof v!=='number'||!Number.isFinite(v)||v<min||v>max)throw Error('Số liệu ngoài phạm vi hợp lệ.');};
 ['openingCash','openingAR','openingAP'].forEach(k=>n(p[k]));n(p.taxRate,0,100);
 ['collectionLag','paymentLag'].forEach(k=>{n(p[k],0,12);if(!Number.isInteger(p[k]))throw Error('Độ trễ phải là số tháng nguyên.');});
 if(!Array.isArray(p.months)||p.months.length!==12||!Array.isArray(p.products)||p.products.length>200)throw Error('Cần đủ 12 tháng, tối đa 200 sản phẩm.');
 const ids=new Set();p.products.forEach(s=>{if(typeof s.id!=='string'||!s.id||s.id.length>80||ids.has(s.id)||typeof s.name!=='string'||s.name.length>160)throw Error('Mã sản phẩm trống hoặc trùng.');ids.add(s.id);['price','cost','opening','safety'].forEach(k=>n(s[k]));['lot','moq'].forEach(k=>{n(s[k],1,1e9);if(!Number.isInteger(s[k]))throw Error('Lô và MOQ phải nguyên.');});n(s.lead,0,12);if(!Number.isInteger(s.lead))throw Error('Thời gian giao phải nguyên.');if(!Array.isArray(s.units)||s.units.length!==12)throw Error('Sản lượng phải đủ 12 tháng.');s.units.forEach(v=>n(v,0,1e9));});
 p.months.forEach(m=>{['fixed','depreciation','interest','capex','principal'].forEach(k=>n(m[k]));n(m.financing,-1e15);n(m.variableRate,0,100);['actualRevenue','actualProfit'].forEach(k=>{if(m[k]!==null)n(m[k],k==='actualProfit'?-1e15:0);});if(typeof m.locked!=='boolean')throw Error('Trạng thái khóa không hợp lệ.');});
 if(!['draft','submitted','approved'].includes(p.status))throw Error('Trạng thái không hợp lệ.');return p;
}
function calculate(plan,shock={}){
 const p=validate(copy(plan)), inventories=p.products.map(s=>s.opening), rows=[];
 const priceFactor=1+(shock.price||0)/100,volumeFactor=1+(shock.volume||0)/100,costFactor=1+(shock.cost||0)/100;
 if([priceFactor,volumeFactor,costFactor].some(v=>!Number.isFinite(v)||v<0))throw Error('Kịch bản không hợp lệ.');
 let cash=p.openingCash,ar=p.openingAR,ap=p.openingAP,workingCapitalOpening=ar+sum(p.products.map(s=>s.opening*s.cost*costFactor))-ap;
 for(let i=0;i<12;i++){
  let revenue=0,cogs=0,purchases=0;const supply=[];
  p.products.forEach((s,j)=>{const units=s.units[i]*volumeFactor,price=s.price*priceFactor,cost=s.cost*costFactor;
   const need=Math.max(0,units+s.safety-inventories[j]);const buy=need>0?Math.ceil(Math.max(need,s.moq)/s.lot)*s.lot:0;
   inventories[j]+=buy-units;revenue+=units*price;cogs+=units*cost;purchases+=buy*cost;
   supply.push({id:s.id,units,buy,closing:inventories[j],value:inventories[j]*cost,orderMonth:i-s.lead});
  });
  const m=p.months[i],variable=revenue*m.variableRate/100,gross=revenue-cogs,ebitda=gross-variable-m.fixed,ebit=ebitda-m.depreciation,pretax=ebit-m.interest,tax=Math.max(0,pretax)*p.taxRate/100,profit=pretax-tax;
  const receipts=(i>=p.collectionLag?(i===i-p.collectionLag?revenue:rows[i-p.collectionLag].revenue):0)+(i===0?p.openingAR:0);
  const supplierPaid=(i>=p.paymentLag?(p.paymentLag===0?purchases:rows[i-p.paymentLag].purchases):0)+(i===0?p.openingAP:0);
  ar+=revenue-receipts;ap+=purchases-supplierPaid;
  const operatingCash=receipts-supplierPaid-variable-m.fixed-m.interest-tax;
  const cashOpening=cash;cash+=operatingCash-m.capex-m.principal+m.financing;
  const contribution=gross-variable,contributionRate=ratio(contribution,revenue),breakEven=contributionRate>0?(m.fixed+m.depreciation+m.interest)/contributionRate:null;
  const inventory=sum(supply.map(s=>s.value));
  const workingCapital=ar+inventory-ap,deltaWorkingCapital=workingCapital-workingCapitalOpening,investingCash=-m.capex,financingCash=m.financing-m.principal,netCash=cash-cashOpening;
  const cashFromEarnings=profit+m.depreciation-deltaWorkingCapital+investingCash+financingCash;
  rows.push({month:i+1,revenue,cogs,purchases,variable,fixed:m.fixed,depreciation:m.depreciation,interest:m.interest,gross,ebitda,ebit,pretax,tax,profit,receipts,supplierPaid,operatingCash,investingCash,financingCash,netCash,cashFromEarnings,cashBridgeDifference:netCash-cashFromEarnings,deltaWorkingCapital,cashOpening,cash,ar,ap,inventory,workingCapital,contributionRate,breakEven,safetyMargin:breakEven===null?null:ratio(revenue-breakEven,revenue),grossMargin:ratio(gross,revenue),netMargin:ratio(profit,revenue),revenueVariance:m.actualRevenue===null?null:m.actualRevenue-revenue,profitVariance:m.actualProfit===null?null:m.actualProfit-profit,supply});workingCapitalOpening=workingCapital;
 }
 const revenue=sum(rows.map(r=>r.revenue)),profit=sum(rows.map(r=>r.profit));
 return {rows,revenue,profit,gross:sum(rows.map(r=>r.gross)),cash,netMargin:ratio(profit,revenue),minCash:Math.min(...rows.map(r=>r.cash)),fundingNeed:Math.max(0,-Math.min(...rows.map(r=>r.cash))),firstShortage:rows.find(r=>r.cash<0)?.month||null};
}
function forecast(history,periods=12){if(!Array.isArray(history)||!history.length||history.some(n=>!Number.isFinite(n)||n<0))throw Error('Lịch sử bán không hợp lệ.');const mean=sum(history.slice(-3))/Math.min(3,history.length);return Array.from({length:periods},()=>Math.round(mean));}
function accuracy(actual,predicted){if(actual.length!==predicted.length||!actual.length)throw Error('Hai chuỗi phải cùng độ dài.');const denom=sum(actual);return {wape:denom?sum(actual.map((v,i)=>Math.abs(v-predicted[i])))/denom:null};}
const api={blank,validate,calculate,forecast,accuracy,copy};if(typeof module!=='undefined')module.exports=api;root.FinancialPlan=api;
})(typeof globalThis!=='undefined'?globalThis:this);
