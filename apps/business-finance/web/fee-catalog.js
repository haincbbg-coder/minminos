/* Vietnam marketplace fee snapshots. Values are suggestions, never account-level guarantees. */
(function(root){
'use strict';
const checked='2026-10-28',version='vn-2026-10-28';
const sources={
 shopee:{url:'https://banhang.shopee.vn/edu/article/2139',mall:'https://banhang.shopee.vn/edu/article/28220',transaction:'https://help.shopee.vn/portal/4/article/77243',program:'https://banhang.shopee.vn/edu/article/21087',processing:'https://banhang.shopee.vn/edu/article/25223'},
 tiktok:{url:'https://seller-vn.tiktok.com/university/essay?knowledge_id=3396736626312961',transaction:'https://seller-vn.tiktok.com/university/essay?knowledge_id=753295858337537',processing:'https://seller-vn.tiktok.com/university/essay?knowledge_id=2968734088120080'},
 lazada:{url:'https://sellercenter.lazada.vn/helpcenter/s/faq/knowledge?categoryId=1000028699&m_station=faq&questionId=1000155629',mall:'https://sellercenter.lazada.vn/helpcenter/s/faq/knowledge?categoryId=1000028702&m_station=faq&questionId=1000149707',transaction:'https://sellercenter.lazada.vn/helpcenter/s/faq/knowledge?categoryId=1000028699&m_station=faq&questionId=1000149699'}
};
const names={shopee:'Shopee',tiktok:'TikTok Shop',lazada:'Lazada'};
const normalize=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').replace(/Đ/g,'D').toLowerCase().replace(/my pham|sac dep|lam dep/g,'beauty');
const vn={'Fashion':'Thời trang','Electronics':'Điện tử','FMCG':'Tiêu dùng nhanh','Lifestyle':'Nhà cửa & đời sống','Health & Beauty':'Sức khỏe & làm đẹp','Home & Living':'Nhà cửa & đời sống','Womenswear & Underwear':'Thời trang nữ & đồ lót','Menswear & Underwear':'Thời trang nam & đồ lót','Beauty & Personal Care':'Mỹ phẩm & chăm sóc cá nhân','Household Appliances':'Thiết bị gia dụng','Kitchenware':'Đồ dùng nhà bếp','Home Supplies':'Đồ dùng gia đình','Computers & Office Equipment':'Máy tính & thiết bị văn phòng','Phones & Electronics':'Điện thoại & điện tử','Food & Beverages':'Thực phẩm & đồ uống','Baby & Maternity':'Mẹ & bé','Health':'Sức khỏe','Pet Supplies':'Thú cưng','Books, Magazines & Audio':'Sách & tạp chí','Furniture':'Nội thất','Shoes':'Giày dép','Luggage & Bags':'Túi xách & hành lý','Fashion Accessories':'Phụ kiện thời trang','Sports & Outdoor':'Thể thao & ngoài trời','Textiles & Soft Furnishings':'Dệt may & nội thất mềm','Womens Tops':'Áo nữ',"Women's Tops":'Áo nữ','Blouses & Shirts':'Áo sơ mi','Casual Dresses':'Đầm thường ngày','Jeans':'Quần jean','Pants':'Quần dài','Skirts':'Chân váy','Jackets & Coats':'Áo khoác',"Women's T-shirts":'Áo thun nữ','Skin Care':'Chăm sóc da','Facial Cleansers':'Sữa rửa mặt','Face Creams & Lotions':'Kem dưỡng da','Sunscreens':'Chống nắng','Lipsticks':'Son môi'};
const translate=s=>vn[s]||s;
function rows(market,shop='standard'){const key=shop==='mall'&&market!=='tiktok'?market+'_mall':market;return (root.MinminFeeData?.[key]||[]).map(a=>{const path=a[1].map(v=>typeof v==='number'?root.MinminFeeTerms[v]:v);return {id:a[0],path,rate:a[2],mall:a[3],page:a[4],mallPage:a[5],bookUpdated:!!a[6],label:path.map(translate).join(' › ')};});}
function rule(id,name,value,opts={}){return {id,name,enabled:true,kind:'percent',value,base:'net',scope:'success',unit:'item',min:0,max:0,tax:0,coverage:100,returnedChargeShare:0,baseDeduction:0,baseAddition:0,...opts};}
function build({market,shop='standard',categoryId,manualRate,buyerShippingExtra=0,extras=[]}){
 if(!Object.hasOwn(names,market)||!['standard','mall'].includes(shop))throw Error('Chọn sàn và loại shop hợp lệ.');
 const row=rows(market,shop).find(r=>r.id===categoryId),manual=categoryId==='manual';
 let rate=manual?manualRate:shop==='mall'?row?.mall:row?.rate;
 if(!Number.isFinite(rate)||rate<0||rate>100)throw Error('Chọn ngành hàng hoặc nhập tỷ lệ hoa hồng 0–100%.');
 if(!Number.isFinite(buyerShippingExtra)||buyerShippingExtra<0)throw Error('Cước khách trả sàn phải là số không âm.');
 const src=sources[market],rules=[],isMall=shop==='mall';
 const commissionSource=isMall&&(market!=='tiktok')?src.mall:src.url;
 let effective=market==='shopee'?(isMall?'2026-10-04':'2026-05-23'):market==='lazada'?'2026-06-04':isMall?'2026-10-20':'2026-07-03';
 if(market==='lazada'&&isMall&&row?.bookUpdated)effective='2026-10-04';
 const c=rule('commission','Hoa hồng / phí cố định theo ngành',rate,{source:commissionSource,effective,officialValue:manual?null:rate,note:manual?'Mức do khách nhập, không xác minh từ danh mục.':'Đã gồm thuế theo bảng công bố. Chọn đúng ngành cấp nhỏ của sản phẩm.'});
 rules.push(c);
 rules.push(rule('transaction',market==='lazada'?'Phí xử lý đơn hàng':'Phí xử lý giao dịch',6,{unit:'order',base:'netShipping',baseAddition:buyerShippingExtra,source:src.transaction,effective:market==='lazada'?'2026-05-26':market==='tiktok'?'2026-05-09':isMall?'2026-05-08':'2026-05-01',officialValue:6,note:market==='shopee'?'Cần trừ thêm phần khuyến mãi ngân hàng nếu shop có. Điền tại “Giảm cơ sở tính phí” của dòng này.':'Tiền hàng sau giảm shop cộng cước khách trả. Không trừ ưu đãi do sàn tự tài trợ.'}));
 rules.push(rule('processing',market==='tiktok'?'Phí xử lý đơn hàng':'Phí hạ tầng',3000,{kind:'fixed',unit:'order',source:market==='lazada'?src.transaction:src.processing,effective:market==='tiktok'?'2025-10-27':market==='shopee'?'2025-07-01':'2026-05-26',officialValue:3000,note:'Đã gồm thuế. Nhập tỷ lệ đơn hoàn vẫn bị thu phí nếu đã giao thành công trước khi hoàn.'}));
 for(const x of extras){
  if(x.id==='voucher'&&market==='shopee')rules.push(rule('voucher','Voucher Xtra',5.5,{max:50000,source:src.program,effective:'2026-05-23',officialValue:5.5,note:'Chỉ bật khi shop thực sự tham gia. Trần 50.000đ / sản phẩm.'}));
  else if(['affiliate','service','shipping','fulfillment','other','content','freemax','coins','sfp'].includes(x.id)){
   if(!Number.isFinite(x.value)||x.value<0||(x.kind!=='fixed'&&x.value>100))throw Error('Nhập mức phí bổ sung hợp lệ.');
   if(!Number.isFinite(x.coverage)||x.coverage<0||x.coverage>100)throw Error('Tỷ lệ đơn/doanh thu chịu phí phải từ 0–100%.');
   rules.push(rule(x.id,{content:'Content Xtra',freemax:'Freeship Max',coins:'LazCoins / đồng tài trợ',sfp:'SFP / chương trình vận chuyển',affiliate:'Hoa hồng affiliate / đối tác',service:'Chương trình dịch vụ shop tham gia',shipping:'Cước / trợ giá vận chuyển shop chịu',fulfillment:'Kho, đóng gói và hoàn tất đơn',other:'Chi phí sàn khác'}[x.id],x.value,{kind:x.kind||'percent',unit:x.kind==='fixed'?'order':'item',coverage:x.coverage,officialValue:null,source:'Người dùng nhập theo hợp đồng / quyết toán',note:'Chỉ nhập phần chưa kê ở chi phí quảng cáo, giao hàng hoặc đóng gói để tránh tính hai lần.'}));
  }
 }
 const warning=['Cước khách trả thẳng sàn được cộng vào cơ sở phí giao dịch, không cộng vào doanh thu shop. Chỉ nhập phần chưa nằm trong cước shop thực thu.','Đây là bản gợi ý đã tra cứu ngày 28/10/2026, không phải kết nối trực tiếp tài khoản sàn. Kiểm tra thông báo shop trước khi áp dụng.','Các mức công bố đã gồm thuế: mặc định không cộng VAT lần nữa. Hồ sơ doanh nghiệp, ưu đãi, miễn/giảm riêng cần chỉnh theo quyết toán.','Đơn hoàn: mặc định chỉ tính phí trên phần đơn thành công còn lại. Hãy chỉnh “% đơn hoàn vẫn bị thu phí” theo loại phí và thực tế shop.','Một sản phẩm/nhóm trong bảng tính dùng giá và giá vốn bình quân; đơn đa ngành cần lập kế hoạch riêng hoặc tự quy đổi phí bình quân.'];
 if(market==='shopee')warning.push('Đã kê phí hạ tầng 3.000đ/đơn; ưu đãi riêng hoặc phí dịch vụ ngoài các dòng đã kê cần bổ sung. Đối chiếu trang Phân loại phí và quyết toán của shop. Phần khuyến mãi ngân hàng cần nhập tại “Giảm cơ sở tính phí” của dòng phí giao dịch.');
 if(market==='tiktok')warning.push('Ưu đãi phí giao dịch GMV Max chỉ áp khi Seller Center xác nhận đủ điều kiện; sửa phí giao dịch thực hưởng, không tự suy từ số tiền quảng cáo dự toán.');
 if(market==='lazada')warning.push('Phí xử lý đơn hàng có thể không hoàn lại sau đổi trả; miễn phí cố định cho shop mới chỉ áp khi shop đủ điều kiện, hãy sửa dòng hoa hồng theo thời hạn ưu đãi.');
 return {name:names[market]+' · '+(isMall?'Mall':'Shop thường')+' · '+(row?row.path.at(-1):'Tự nhập'),category:row?row.label:'Ngành tự nhập',shop:isMall?'Mall':'Shop thường',program:extras.length?'Có chương trình / phí bổ sung':'Chưa bật chương trình bổ sung',effective,source:commissionSource,status:manual?'Người dùng tự cấu hình':extras.some(x=>x.id!=='voucher')?'Gợi ý + phí shop tự nhập':'Gợi ý từ nguồn chính thức',updated:checked,catalogVersion:version,market,categoryId,categoryPage:row?.page||null,rules,warning};
}
root.MinminFeeCatalog={checked,version,sources,names,rows,build,normalize,translate};
})(typeof window==='undefined'?globalThis:window);
