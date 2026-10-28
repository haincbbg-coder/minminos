/* Localized numeric entry: fractional quantities accept 1,46 and 1.46. */
(function(root){
function parse(value,decimal=false){let s=String(value).trim().replace(/\s+/g,'');if(!s)return NaN;if(!/^[+-]?[\d.,]+$/.test(s))return NaN;if(s.includes(',')){if((s.match(/,/g)||[]).length!==1)return NaN;const parts=s.split(',');if(parts[0].includes('.')&&!/^[+-]?\d{1,3}(\.\d{3})+$/.test(parts[0]))return NaN;s=parts[0].replace(/\./g,'')+'.'+parts[1];}else if(s.includes('.')){if(!decimal&&/^[+-]?\d{1,3}(\.\d{3})+$/.test(s))s=s.replace(/\./g,'');else if((s.match(/\./g)||[]).length!==1)return NaN;}return Number(s);}
function format(value,decimal=false){return new Intl.NumberFormat('vi-VN',{useGrouping:!decimal,maximumFractionDigits:6}).format(value)}
root.MinminNumbers={parse,format};
})(typeof window==='undefined'?globalThis:window);
