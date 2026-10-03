"use strict";
/* Hoá đơn (MinMin OS 26.10.6): giao diện web cho Tải Hoá Đơn TCT và Quét hoá đơn Gmail.
 * Nói chuyện với /apps/tai-hoa-don/api/*. Việc dài (tra cứu, tải, quét) chạy nền phía máy chủ,
 * trang này hỏi tiến độ mỗi giây. Không dùng ký tự em dash. */
(function () {
  var API = "api/";
  var $ = function (s) { return document.querySelector(s); };
  var tt = { tai: false, gmail: false, chungtu: false };
  var dn = null;            // MST đang chọn
  var loai = "purchase";
  var dsHd = [];
  var chon = new Set();
  var dsG = [], gChon = new Set(), hdLoc = [], gmLoc = [];
  var paging = {}, warnings = [];
  function pageRows(id, rows, refresh, table, signature) {
    var state = paging[id] || (paging[id] = {page:1,size:30});
    if (state.signature !== signature) { state.page=1; state.signature=signature; }
    var part = InvoiceUI.paginate(rows,state.page,state.size); state.page=part.page;
    var box = $('#' + id + 'Pager');
    if (!box) { box=document.createElement('nav'); box.id=id+'Pager'; box.className='invoice-pager'; box.setAttribute('aria-label','Phân trang '+id); $(table).closest('.cuon').before(box); }
    box.innerHTML='<label>Số dòng mỗi trang <select aria-label="Số dòng '+id+'">'+[10,30,100,500,1000,0].map(function(n){return '<option value="'+n+'"'+(state.size===n?' selected':'')+'>'+(n||'Tất cả')+'</option>';}).join('')+'</select></label>'+
      '<strong>'+ (rows.length ? part.start+1 : 0)+'–'+(part.start+part.rows.length)+' / '+rows.length+' dòng</strong>'+
      '<button class="nut" data-prev'+(part.page===1?' disabled':'')+'>Trang trước</button><span>Trang '+part.page+' / '+part.pages+'</span><button class="nut" data-next'+(part.page===part.pages?' disabled':'')+'>Trang sau</button>';
    box.querySelector('select').onchange=function(){state.size=Number(this.value);state.page=1;refresh();};
    box.querySelector('[data-prev]').onclick=function(){state.page--;refresh();};
    box.querySelector('[data-next]').onclick=function(){state.page++;refresh();};
    return part;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function ngayVN(s) { var m = String(s || "").match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? m[3] + "/" + m[2] + "/" + m[1] : (s || ""); }
  function tien(n) { return Math.round(Number(n) || 0).toLocaleString("vi-VN"); }
  function bao(s) {
    var b = $("#bao"); b.textContent = s; b.classList.add("hien");
    clearTimeout(bao._h); bao._h = setTimeout(function () { b.classList.remove("hien"); }, 3500);
  }
  async function goi(duong, tuy) {
    tuy = tuy || {};
    if (tuy.json !== undefined) {
      tuy.method = tuy.method || "POST";
      tuy.headers = { "content-type": "application/json" };
      tuy.body = JSON.stringify(tuy.json);
    }
    var r = await fetch(API + duong, { method: tuy.method || "GET", headers: tuy.headers, body: tuy.body, credentials: "same-origin" });
    if (r.status === 401) { location.href = "/"; throw new Error("Cần đăng nhập MinMin"); }
    var d = null;
    try { d = await r.json(); } catch (e) {}
    if (!r.ok || !d || d.ok === false) {
      var loi = new Error((d && (d.error || d.detail)) || ("HTTP " + r.status));
      loi.status = r.status;
      throw loi;
    }
    return d;
  }
  async function taiFile(duong, json) {
    var r = await fetch(API + duong, { method: "POST", credentials: "same-origin",
      headers: { "content-type": "application/json" }, body: JSON.stringify(json || {}) });
    if (!r.ok) {
      var d = null; try { d = await r.json(); } catch (e) {}
      throw new Error((d && d.error) || ("HTTP " + r.status));
    }
    var ten = "tep";
    var cd = r.headers.get("content-disposition") || "";
    var m = cd.match(/filename\*=UTF-8''([^;]+)/);
    if (m) ten = decodeURIComponent(m[1]);
    var blob = await r.blob();
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = ten;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1500);
  }
  function ngayISO(d) { return d.toISOString().slice(0, 10); }
  function datNgayMacDinh(tu, den) {
    var h = new Date(), dau = new Date(h.getFullYear(), h.getMonth() - 1, 1);
    tu.value = ngayISO(new Date(dau.getTime() - dau.getTimezoneOffset() * 60000));
    den.value = ngayISO(new Date(h.getTime() - h.getTimezoneOffset() * 60000));
  }

  // ---------------- việc nền
  function theoDoi(id, o, xong) {
    var tu = 0, lanLoi = 0, phien = {};
    o.phienTheoDoi = phien;
    o.hop.hidden = false; o.log.textContent = ""; o.thanh.value = 0; o.thanh.removeAttribute("value");
    o.dung.onclick = function () { goi("viec/" + id + "/dung", { method: "POST" }).catch(function () {}); };
    async function vong() {
      if (o.phienTheoDoi !== phien) return;
      var v;
      try { v = await goi("viec/" + id + "?tu=" + tu); } catch (e) {
        if (o.phienTheoDoi !== phien) return;
        if ((!e.status || e.status >= 500 || e.status === 429) && ++lanLoi <= 12) {
          o.ten.textContent = "Mất kết nối tạm thời, đang nối lại tiến độ. Không cần bấm quét/tải lại.";
          setTimeout(vong, Math.min(15000, 2000 * lanLoi));
        } else {
          o.ten.textContent = e.message + ". Chưa đọc được tiến độ; tác vụ trên máy chủ có thể vẫn đang chạy.";
        }
        return;
      }
      if (o.phienTheoDoi !== phien) return;
      lanLoi = 0;
      o.ten.textContent = v.mo_ta;
      if (v.nhat_ky.length) {
        o.log.textContent += v.nhat_ky.join("\n") + "\n";
        o.log.scrollTop = o.log.scrollHeight;
      }
      tu = v.so_dong;
      if (v.n) { o.thanh.max = v.n; o.thanh.value = v.i; o.so.textContent = v.i + "/" + v.n; }
      if (v.trang_thai === "dang_chay") { setTimeout(vong, 1000); return; }
      o.dung.hidden = true;
      o.so.textContent = v.trang_thai === "xong" ? "Xong" : v.trang_thai === "huy" ? "Đã dừng" : "Lỗi";
      if (v.trang_thai === "loi") bao(v.loi);
      if (xong) xong(v);
    }
    o.dung.hidden = false;
    vong();
  }
  var viecTai = { hop: $("#hopViec"), ten: $("#viecTen"), so: $("#viecSo"), thanh: $("#viecThanh"), log: $("#viecLog"), dung: $("#nutDung") };
  var viecGmail = { hop: $("#gViec"), ten: $("#gViecTen"), so: $("#gViecSo"), thanh: $("#gThanh"), log: $("#gLog"), dung: $("#gDung") };

  // ---------------- tab
  function setupRecovery() {
    var panel=document.createElement('details'); panel.className='the recovery'; panel.id='recovery';
    panel.innerHTML='<summary>Tìm bản gốc từ XML/PDF</summary><p>Gửi chứng từ hoặc chọn hóa đơn trong kho. MinMin đối chiếu Gmail, mã tra cứu và cổng nhà phát hành; chỉ lưu bản gốc đã khớp thông tin.</p>'+
      '<label class="recovery-drop" id="recoveryDrop">Kéo thả XML, PDF Trống đồng hoặc ZIP vào đây<input id="recoveryFiles" type="file" accept=".xml,.pdf,.zip" multiple><small>Tối đa 20 MB/file, 100 mục/ZIP. PDF đầu vào dùng để tìm kiếm, không tự coi là bản gốc.</small></label>'+
      '<div class="hang"><button class="nut" id="recoveryRefresh">Làm mới kết quả</button><label class="tich"><input type="checkbox" id="recoveryRescan"> Quét Gmail bổ sung theo ngày hóa đơn (±7 ngày)</label><button class="nut chinh" id="recoveryRun">Tìm bản gốc đã chọn</button><span id="recoveryCount" role="status"></span></div>'+
      '<p id="recoveryMessage" role="status"></p><div class="cuon"><table id="recoveryTable"><thead><tr><th><input type="checkbox" id="recoveryAll" aria-label="Chọn toàn bộ chứng từ cần tìm"></th><th>Chứng từ / nhà phát hành</th><th>Kết quả và nguồn đã thử</th><th>Thao tác</th></tr></thead><tbody></tbody></table></div>'+
      '<div class="hang"><button class="nut" id="recoveryPrev">Trang trước</button><span id="recoveryPage"></span><button class="nut" id="recoveryNext">Trang sau</button></div>'+
      '<div id="rViec" class="viec" hidden><strong id="rTen"></strong> <span id="rSo"></span> <button id="rDung" class="nut">Dừng</button><progress id="rThanh"></progress><details><summary>Nhật ký tìm bản gốc</summary><pre id="rLog"></pre></details></div>';
    document.querySelector('main').prepend(panel);
    var rows=[], selected=new Set(), page=1, running=false;
    var task={hop:$('#rViec'),ten:$('#rTen'),so:$('#rSo'),thanh:$('#rThanh'),log:$('#rLog'),dung:$('#rDung')};
    function draw(){
      var pages=Math.max(1,Math.ceil(rows.length/30)); page=Math.min(page,pages);
      $('#recoveryPage').textContent='Trang '+page+' / '+pages;
      $('#recoveryCount').textContent=rows.length+' chứng từ · Đã chọn '+selected.size;
      $('#recoveryPrev').disabled=page===1; $('#recoveryNext').disabled=page===pages;
      $('#recoveryRun').disabled=running || !selected.size;
      $('#recoveryAll').checked=!!rows.length && selected.size===rows.length;
      $('#recoveryAll').indeterminate=selected.size>0 && selected.size<rows.length;
      $('#recoveryTable tbody').innerHTML=rows.slice((page-1)*30,page*30).map(function(r){
        return '<tr><td><input type="checkbox" data-rid="'+esc(r.id)+'" aria-label="Chọn '+esc(r.label||r.name||r.id)+'"'+(selected.has(r.id)?' checked':'')+'></td><td><strong>'+esc(r.label||r.name||r.id)+'</strong><br>'+esc(r.provider||'Chưa nhận diện hãng')+'</td><td><strong>'+esc(r.status==='done'?'Đã có bản gốc':r.status==='ready'?'Sẵn sàng':'Cần bổ sung nguồn')+'</strong><p>'+esc(r.reason)+'</p>'+(r.attempts&&r.attempts.length?'<details><summary>Nguồn đã thử ('+r.attempts.length+')</summary><ol>'+r.attempts.map(function(s){return '<li>'+esc(s)+'</li>';}).join('')+'</ol></details>':'')+'</td><td>'+(r.status==='done'&&r.download?'<a class="nut" href="'+esc(r.download)+'">Tải PDF gốc</a>':'')+'<details><summary>Bổ sung mã/link</summary><label>Mã tra cứu<input data-code="'+esc(r.id)+'" value="'+esc(r.code||'')+'"></label><label>Link tra cứu HTTPS<input type="url" data-url="'+esc(r.id)+'" value="'+esc(r.url||'')+'"></label><button class="nut" data-save="'+esc(r.id)+'">Lưu nguồn</button></details><button class="nut" data-run="'+esc(r.id)+'"'+(running?' disabled':'')+'>Tìm lại</button></td></tr>';
      }).join('') || '<tr><td colspan="4">Chưa có chứng từ. Gửi file hoặc chọn “Tìm lại bản gốc” trong danh sách hóa đơn.</td></tr>';
      panel.querySelectorAll('[data-rid]').forEach(function(el){el.onchange=function(){el.checked?selected.add(el.dataset.rid):selected.delete(el.dataset.rid);draw();};});
      panel.querySelectorAll('[data-run]').forEach(function(el){el.onclick=function(){run([el.dataset.run]);};});
      panel.querySelectorAll('[data-save]').forEach(function(el){el.onclick=async function(){try{var id=el.dataset.save; await goi('tim-ban-goc/nguon',{json:{id:id,code:panel.querySelector('[data-code="'+id+'"]').value,url:panel.querySelector('[data-url="'+id+'"]').value}}); await load(); message('Đã lưu nguồn; bấm Tìm lại để tiếp tục.');}catch(e){message(e.message);}};});
    }
    function message(s){$('#recoveryMessage').textContent=s;}
    async function load(){var d=await goi('tim-ban-goc');rows=d.rows;draw();}
    async function run(ids){
      if(running)return;running=true;draw();
      try{var d=await goi('tim-ban-goc/chay',{json:{ids:ids,rescan:$('#recoveryRescan').checked}});localStorage.setItem('minmin.invoiceRecoveryJob',d.viec);watch(d.viec);}
      catch(e){running=false;draw();message(e.message);}
    }
    function watch(id){theoDoi(id,task,async function(v){running=false;localStorage.removeItem('minmin.invoiceRecoveryJob');await load();if(dn)await taiBang();await taiGmail();message(v.trang_thai==='xong'?'Đã tìm xong. Xem kết quả từng hóa đơn bên trên.':v.loi||'Đã dừng; các file đã tìm được được giữ lại.');});}
    async function upload(files){
      if(!files.length)return; $('#recoveryFiles').disabled=true;panel.open=true;
      try{var list=Array.from(files).sort(function(a,b){return Number(!a.name.toLowerCase().endsWith('.xml'))-Number(!b.name.toLowerCase().endsWith('.xml'));});
        for(var f of list){if(f.size>20*1024*1024)throw new Error(f.name+': vượt 20 MB.');message('Đang đọc '+f.name+'…');var b64=await new Promise(function(resolve,reject){var reader=new FileReader();reader.onload=function(){resolve(reader.result.split(',')[1]);};reader.onerror=reject;reader.readAsDataURL(f);});var d=await goi('tim-ban-goc/nhap',{json:{name:f.name,data:b64}});d.rows.forEach(function(r){selected.add(r.id);});}
        await load();message('Đã đọc chứng từ. Kiểm tra danh sách rồi bấm Tìm bản gốc đã chọn.');
      }catch(e){message(e.message);}finally{$('#recoveryFiles').disabled=false;$('#recoveryFiles').value='';}
    }
    $('#recoveryFiles').onchange=function(){upload(this.files);};
    $('#recoveryDrop').ondragover=function(e){e.preventDefault();};$('#recoveryDrop').ondrop=function(e){e.preventDefault();upload(e.dataTransfer.files);};
    $('#recoveryRun').onclick=function(){run(Array.from(selected));};$('#recoveryRefresh').onclick=function(){load().catch(function(e){message(e.message);});};
    $('#recoveryAll').onchange=function(){selected=this.checked?new Set(rows.map(function(r){return r.id;})):new Set();draw();};
    $('#recoveryPrev').onclick=function(){page--;draw();};$('#recoveryNext').onclick=function(){page++;draw();};
    panel.addEventListener('toggle',function(){if(panel.open)load().catch(function(e){message(e.message);});});
    [['#nutTai','tct'],['#gTai','gmail']].forEach(function(pair){var b=document.createElement('button');b.type='button';b.className='nut';b.textContent='Tìm lại bản gốc';$(pair[0]).after(b);b.onclick=async function(){try{var payload=pair[1]==='tct'?phamViXuat({}):{gmail_ids:gmailScope().ids};var d=await goi('tim-ban-goc/kho',{json:payload});selected=new Set(d.ids);panel.open=true;await load();panel.scrollIntoView({behavior:'smooth',block:'start'});message('Đang tìm lại '+d.ids.length+' hóa đơn.');run(d.ids);}catch(e){bao(e.message);}};});
    var job=localStorage.getItem('minmin.invoiceRecoveryJob');if(job){panel.open=true;running=true;goi('viec/'+job).then(function(){watch(job);}).catch(function(){running=false;localStorage.removeItem('minmin.invoiceRecoveryJob');message('Máy chủ đã khởi động lại. Kết quả đã lưu vẫn còn; chọn các hóa đơn cần tìm và bấm Tìm lại.');load().catch(function(e){message(e.message);});});}
  }
  function moTab(t) {
    if (!tt[t]) t = tt.tai ? "tai" : tt.gmail ? "gmail" : "chungtu";
    document.querySelectorAll(".tab button").forEach(function (b) { b.classList.toggle("on", b.dataset.tab === t); });
    $("#tab-tai").hidden = t !== "tai";
    $("#tab-gmail").hidden = t !== "gmail";
    $("#tab-chungtu").hidden = t !== "chungtu";
    history.replaceState(null, "", t === "gmail" ? "?tab=gmail" : t === "chungtu" ? "?tab=chungtu" : "./");
    if (t === "tai") taiDn(); else if (t === "gmail") taiGmail(); else { if (dn && !dsHd.length) taiBang(); veChungTu(); }
  }

  // ================= TẢI HOÁ ĐƠN =================
  async function taiDn() {
    var d;
    try { d = await goi("doanh-nghiep"); } catch (e) { bao(e.message); return; }
    var ul = $("#dsDn");
    ul.innerHTML = d.ds.map(function (x) {
      return '<li data-mst="' + esc(x.mst) + '" class="' + (x.mst === dn ? "on" : "") + '">' +
        '<span class="mst">' + esc(x.mst) + '</span>' +
        (x.ten ? '<span>' + esc(x.ten) + '</span>' : "") +
        '<span class="phu"><span><i class="cham' + (x.dang_nhap ? " ok" : "") + '"></i>' +
        (x.dang_nhap ? "Đã đăng nhập" : "Chưa đăng nhập") + ' · ' + (x.so_hd.purchase + x.so_hd.sold) + ' HĐ</span>' +
        '<button type="button" class="xoa" data-xoa="' + esc(x.mst) + '">Xoá</button></span></li>';
    }).join("") || '<li class="nho">Chưa có doanh nghiệp nào.</li>';
    ul.querySelectorAll("li[data-mst]").forEach(function (li) {
      li.onclick = function (ev) {
        if (ev.target.dataset.xoa) return;
        chonDn(li.dataset.mst, d.ds.filter(function (x) { return x.mst === li.dataset.mst; })[0]);
      };
    });
    ul.querySelectorAll("[data-xoa]").forEach(function (b) {
      b.onclick = async function () {
        if (!confirm("Xoá doanh nghiệp " + b.dataset.xoa + " khỏi danh sách? Hoá đơn đã tải vẫn giữ.")) return;
        await goi("doanh-nghiep/" + encodeURIComponent(b.dataset.xoa), { method: "DELETE" });
        if (dn === b.dataset.xoa) { dn = null; $("#vungDn").hidden = true; $("#chuaChon").hidden = false; }
        taiDn();
      };
    });
    if (dn) {
      var hien = d.ds.filter(function (x) { return x.mst === dn; })[0];
      if (hien) veDangNhap(hien);
    }
  }

  function veDangNhap(x) {
    $("#dnTen").textContent = x.ten ? "(" + x.ten + ")" : x.mst;
    $("#hopDangNhap").hidden = !!x.dang_nhap;
    $("#oMk").hidden = !!x.co_mk;
    $("#nhoMk").parentNode.hidden = !!x.co_mk;
    $("#nutDangXuat").hidden = !x.dang_nhap;
    if (!x.dang_nhap && !$("#anhCaptcha").dataset.mst) layCaptcha();
  }

  function chonDn(mst, x) {
    dn = mst;
    chon.clear();
    $("#chuaChon").hidden = true;
    $("#vungDn").hidden = false;
    $("#hopCanhBao").hidden = true;
    $("#anhCaptcha").dataset.mst = "";
    document.querySelectorAll("#dsDn li").forEach(function (li) { li.classList.toggle("on", li.dataset.mst === mst); });
    if (x) veDangNhap(x);
    taiBang();
  }

  async function layCaptcha() {
    $("#thongDangNhap").textContent = "Đang lấy ảnh...";
    $("#thongDangNhap").className = "thong";
    try {
      var c = await goi("captcha?mst=" + encodeURIComponent(dn));
      var img = $("#anhCaptcha");
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(c.svg);
      img.dataset.key = c.key; img.dataset.mst = dn;
      $("#oCaptcha").value = ""; $("#oCaptcha").focus();
      $("#thongDangNhap").textContent = "";
    } catch (e) {
      $("#thongDangNhap").textContent = e.message; $("#thongDangNhap").className = "thong loi";
    }
  }

  async function dangNhap() {
    var nut = $("#nutDangNhap"); nut.disabled = true;
    try {
      await goi("dang-nhap", { json: { mst: dn, captcha: $("#oCaptcha").value, ckey: $("#anhCaptcha").dataset.key,
        mat_khau: $("#oMk").hidden ? "" : $("#oMk").value, nho_mk: $("#nhoMk").checked } });
      $("#oMk").value = "";
      bao("Đã đăng nhập cổng thuế.");
      $("#anhCaptcha").dataset.mst = "";
      taiDn();
    } catch (e) {
      $("#thongDangNhap").textContent = e.message; $("#thongDangNhap").className = "thong loi";
      layCaptcha();
    } finally { nut.disabled = false; }
  }

  async function taiBang() {
    if (!dn) return;
    var q = "hoa-don?mst=" + encodeURIComponent(dn) + "&loai=" + loai + "&tu=" + $("#tu").value + "&den=" + $("#den").value;
    var d;
    try { d = await goi(q); } catch (e) { bao(e.message); return; }
    dsHd = d.ds;
    var pub = $("#hdPublisher"), chosen = pub.value;
    pub.innerHTML = '<option value="">Tất cả hãng</option>' + Array.from(new Set(dsHd.map(function(r){return r.nha_cung_cap || "unknown";}))).sort().map(function(v){return '<option value="'+esc(v)+'">'+esc(v === "unknown" ? "Chưa có XML / chưa nhận diện" : v)+'</option>';}).join('');
    pub.value = chosen;
    var t = d.tong;
    $("#tong").innerHTML = "<span><b>" + t.so_hd + "</b> hoá đơn</span><span>Tiền hàng <b>" + tien(t.tien_hang) +
      "</b></span><span>Thuế <b>" + tien(t.thue) + "</b></span><span>Tổng <b>" + tien(t.tong) +
      "</b></span><span>Đã có XML <b>" + t.co_xml + "</b></span><span>Có bản gốc <b>" + t.co_goc + "</b></span>";
    veBang();
  }

  function veBang() {
    updateGroups("hd", dsHd);
    updateFileCounts("hd", dsHd);
    var ds = hdLoc = InvoiceUI.filter(dsHd, readFilter("hd"));
    var valid = new Set(ds.map(function(r) { return r.key; }));
    chon.forEach(function(k) { if (!valid.has(k)) chon.delete(k); });
    var base = "/" + encodeURIComponent(dn) + "/" + loai + "/";
    var part = pageRows('hd',ds,veBang,'#bangHd',JSON.stringify([dn,loai,readFilter('hd')]));
    $("#bangHd").innerHTML = part.rows.map(function (r, index) {
      var k = encodeURIComponent(r.key);
      var file = (r.co_html ? '<a href="' + API + "xem" + base + k + '" target="_blank" rel="noopener">Xem</a>' : "") +
        (r.co_xml ? '<a class="nhan ok" href="' + API + "tep" + base + k + '/xml">XML</a>' : "") +
        (r.co_pdf ? '<a class="nhan ok" href="' + API + "tep" + base + k + '/pdf">Trống đồng</a>' :
          r.pdf_loi ? '<span class="nhan loi" title="' + esc(r.pdf_loi) + '">Trống đồng: lỗi</span>' : "") +
        (r.co_goc ? '<a class="nhan ok" href="' + API + "tep" + base + k + '/goc">Gốc' + (r.goc_nguon === "Gmail" ? " (Gmail)" : "") + '</a>' :
          r.goc_loi ? '<span class="nhan loi" title="' + esc(r.goc_loi) + '">Gốc: chưa tải được</span>' : "") +
        (r.co_zip ? '<a class="nhan" href="' + API + "tep" + base + k + '/zip">ZIP</a>' : "") +
        (!r.co_xml && !r.co_goc ? '<span class="nhan">Chưa tải XML</span>' : '') + '<button class="nut phu" data-lookup="' + esc(r.key) + '">Mã tra cứu / Trang hãng</button>';
      return '<tr><td><input type="checkbox" data-k="' + esc(r.key) + '"' + (chon.has(r.key) ? " checked" : "") + '></td>' +
        '<td class="row-number">' + (part.start+index+1) + '</td><td class="ngay">' + esc(ngayVN(r.ngay)) + '</td><td>' + esc(r.so) + '</td><td>' + esc(r.ky_hieu) + '</td>' +
        '<td class="doi">' + esc(r.doi_tac) + (r.may_tinh_tien ? ' <span class="nhan">MTT</span>' : "") + (r.tu_gmail ? ' <span class="nhan">Từ Gmail</span>' : "") + '</td><td>' + esc(r.mst_doi_tac) + '</td>' +
        '<td class="so">' + tien(r.tien_hang) + '</td><td class="so">' + tien(r.thue) + '</td><td class="so">' + tien(r.tong) + '</td>' +
        '<td>' + esc(r.trang_thai) + '<div class="nho">' + esc(r.nha_cung_cap || '') + '</div></td><td>' + file + '</td></tr>';
    }).join("") || '<tr><td colspan="12" class="nho">Chưa có hoá đơn trong khoảng ngày này. Đăng nhập rồi bấm Tra cứu.</td></tr>';
    $("#bangHd").querySelectorAll("input[data-k]").forEach(function (c) {
      c.onchange = function () { if (c.checked) chon.add(c.dataset.k); else chon.delete(c.dataset.k); demChon(); };
    });
    $("#bangHd").querySelectorAll("[data-lookup]").forEach(function(b) { b.onclick = function() { openLookup("tct", b.dataset.lookup); }; });
    var missing=ds.filter(function(r){return !r.co_goc;});
    var noXml=missing.filter(function(r){return !r.co_xml;}).length;
    var failed=missing.filter(function(r){return r.goc_trang_thai==='failed';}).length;
    var summary=document.querySelector('#missingOriginalSummary');
    if(!summary){summary=document.createElement('p'); summary.id='missingOriginalSummary'; summary.className='nho'; $('#bangHd').closest('.cuon').before(summary);}
    summary.textContent='Trong kết quả đang lọc: '+missing.length+' chưa có bản gốc; '+noXml+' chưa tải XML, '+failed+' đã thử tải gốc nhưng chưa thành công, '+(missing.length-noXml-failed)+' có XML và chưa thử tải gốc.';
    demChon();
  }
  function demChon() {
    var all = $("#chonHet"); all.checked = hdLoc.length > 0 && chon.size === hdLoc.length; all.indeterminate = chon.size > 0 && chon.size < hdLoc.length;
    $("#soChon").textContent = "Đang lọc " + hdLoc.length + "/" + dsHd.length + " · Đã chọn " + chon.size;
    $("#phamViTai").textContent = chon.size ? "Áp dụng cho " + chon.size + " hoá đơn đã chọn (cả nút Xuất)"
      : "Áp dụng cho " + hdLoc.length + " hoá đơn đang lọc";
    veChungTu();
  }
  function phamViXuat(them) {
    var d = { mst: dn, tu: $("#tu").value, den: $("#den").value };
    d.keys = (chon.size ? dsHd : hdLoc).filter(function(r) { return !chon.size || chon.has(r.key); }).map(function(r) { return r.key; }); d.loai = loai;
    for (var k in them) d[k] = them[k];
    return d;
  }



  // ---------------- bộ chứng từ kế toán
  function chungTuRows() {
    if (!dn) return [];
    if (chon.size) return dsHd.filter(function(r){ return chon.has(r.key); });
    return (hdLoc && hdLoc.length ? hdLoc : dsHd).slice();
  }
  function veChungTu() {
    var rows = chungTuRows();
    var hasDn = !!dn;
    if ($("#ctDn")) $("#ctDn").textContent = hasDn ? "MST " + dn + " · " + (loai === "purchase" ? "mua vào" : "bán ra") : "Chưa chọn doanh nghiệp";
    if ($("#ctScope")) $("#ctScope").textContent = hasDn ? (chon.size ? "Đang chọn " + rows.length + " hoá đơn." : "Đang dùng " + rows.length + " hoá đơn trong bộ lọc.") : "Chọn doanh nghiệp ở tab Tải Hoá Đơn TCT để lấy dữ liệu.";
    if (!$("#ctStats")) return;
    var sum = rows.reduce(function(a,r){ a.tien += Number(r.tien_hang||0); a.thue += Number(r.thue||0); a.tong += Number(r.tong||0); if(r.co_xml)a.xml++; if(r.co_goc)a.goc++; return a; }, {tien:0,thue:0,tong:0,xml:0,goc:0});
    $("#ctStats").innerHTML = [
      ["Hoá đơn", rows.length], ["Tiền hàng", tien(sum.tien)], ["Thuế GTGT", tien(sum.thue)], ["Tổng thanh toán", tien(sum.tong)], ["Đã có XML", sum.xml + "/" + rows.length], ["Đã có PDF gốc", sum.goc + "/" + rows.length]
    ].map(function(x){return '<div><small>'+esc(x[0])+'</small><b>'+esc(x[1])+'</b></div>';}).join('');
    var missing = [];
    if (!hasDn) missing.push("Chưa chọn doanh nghiệp/MST.");
    if (!rows.length) missing.push("Chưa có hoá đơn trong phạm vi tạo bộ chứng từ.");
    if (rows.some(function(r){ return !r.co_xml; })) missing.push("Một số hoá đơn chưa có XML nên mẫu chỉ ghi dòng tổng hợp theo số hoá đơn.");
    if (rows.some(function(r){ return !r.co_goc; })) missing.push("Một số hoá đơn chưa có PDF gốc NCC; gói vẫn tạo chứng từ và ghi rõ trạng thái còn thiếu.");
    $("#ctCheck").innerHTML = (missing.length ? missing : ["Dữ liệu đủ để tạo bộ chứng từ in được."]).map(function(m,i){return '<p class="'+(missing.length?'can':'ok')+'">'+(missing.length?'Cần rà soát: ':'Sẵn sàng: ')+esc(m)+'</p>';}).join('');
  }
  var nsCols = ["ho_ten", "ngay_sinh", "cccd", "dia_chi", "chuc_vu", "luong", "ngay_vao", "ma_bhxh"];
  function dongNhanSu(data) {
    data = data || {};
    var tr = document.createElement("tr");
    tr.innerHTML = nsCols.map(function(k){ return '<td><input data-ns="'+k+'" value="'+esc(data[k]||'')+'" /></td>'; }).join("") + '<td><button type="button" class="nut phu" data-xoa-ns>×</button></td>';
    tr.querySelectorAll("input").forEach(function(i){ i.oninput = veNhanSuDem; });
    tr.querySelector("[data-xoa-ns]").onclick = function(){ tr.remove(); veNhanSuDem(); };
    return tr;
  }
  function themNhanSu(data) {
    var body = $("#ctNhanSuBody");
    if (!body) return;
    body.appendChild(dongNhanSu(data));
    veNhanSuDem();
  }
  function docNhanSu() {
    var body = $("#ctNhanSuBody");
    if (!body) return [];
    return Array.prototype.map.call(body.querySelectorAll("tr"), function(tr){
      var row = {};
      nsCols.forEach(function(k){ var el = tr.querySelector('[data-ns="'+k+'"]'); row[k] = el ? el.value.trim() : ""; });
      return row;
    }).filter(function(row){ return Object.keys(row).some(function(k){ return row[k]; }); });
  }
  function veNhanSuDem() { if ($("#ctNhanSuDem")) $("#ctNhanSuDem").textContent = docNhanSu().length + " người lao động"; }
  function veDocTabs(name) {
    document.querySelectorAll("#ctTabs [data-doc-tab]").forEach(function(b){ b.classList.toggle("on", b.dataset.docTab === name); });
    document.querySelectorAll("[data-doc-pane]").forEach(function(p){ p.classList.toggle("on", p.dataset.docPane === name); });
  }
  function phamViChungTu() {
    var d = phamViXuat({ kieu_mau: $("#ctKieu").value, pham_vi_chung_tu: $("#ctPhamVi").value });
    d.nhom = Array.prototype.map.call(document.querySelectorAll("#ctNhomHoaDon input:checked, #ctNhomKiemTra input:checked"), function(c){ return c.value; });
    d.nhan_su = docNhanSu();
    var loai = document.querySelector('input[name="ctLoaiHd"]:checked');
    d.loai_hoat_dong = loai ? loai.value : "thuong_mai";
    if ($("#ctGomBhxh") && $("#ctGomBhxh").checked && d.nhan_su.length && d.nhom.indexOf("thue_bhxh") < 0) d.nhom.push("thue_bhxh");
    if (d.nhan_su.length && d.nhom.indexOf("lao_dong") < 0) d.nhom.push("lao_dong");
    if (!d.nhom.length) throw new Error("Chọn ít nhất một bộ hồ sơ cần tạo.");
    return d;
  }

  // ---------------- cài đặt tải
  var cd = null;
  function veChip(hop, ds, chonDs) {
    hop.innerHTML = ds.map(function (t) {
      var i = chonDs.indexOf(t.id);
      return '<button type="button" data-t="' + t.id + '" class="' + (i >= 0 ? "on" : "") + '">' +
        (i >= 0 ? "<b>" + (i + 1) + "</b>" : "") + esc(t.ten) + "</button>";
    }).join("");
    hop.querySelectorAll("button").forEach(function (b) {
      b.onclick = function () {
        var i = chonDs.indexOf(b.dataset.t);
        if (i >= 0) chonDs.splice(i, 1); else chonDs.push(b.dataset.t);
        luuCaiDat(true);
      };
    });
  }
  function veCaiDat(d) {
    cd = d.cai_dat;
    veChip($("#tokFile"), d.token_ten_file, cd.ten_file.tokens);
    veChip($("#tokExcel"), d.token_ten_excel, cd.ten_excel.tokens);
    $("#vietFile").checked = cd.ten_file.keep_viet;
    $("#vietExcel").checked = cd.ten_excel.keep_viet;
    $("#vdFile").textContent = d.vi_du_ten_file + ".xml / .pdf";
    $("#vdExcel").textContent = d.vi_du_ten_excel + ".xlsx";
    $("#vdThuMuc").textContent = d.vi_du_thu_muc + "/";
    $("#xepThuMuc").innerHTML = d.xep_thu_muc.map(function (x) {
      return '<label class="tich"><input type="radio" name="xepTm" value="' + x.id + '"' + (cd.xep_thu_muc === x.id ? " checked" : "") + "> " + esc(x.ten) + "</label>";
    }).join("");
    $("#xepThuMuc").querySelectorAll("input").forEach(function (r) { r.onchange = function () { cd.xep_thu_muc = r.value; luuCaiDat(true); }; });
    $("#giuZip").checked = cd.giu_zip;
    $("#soLuong").value = cd.luong;
    $("#ghiChuTrinhDuyet").textContent = d.co_trinh_duyet ? "" :
      "Muốn tải PDF Trống đồng: vào Thiết lập > Công cụ của MinMin, cài Trình duyệt một lần (miễn phí).";
  }
  async function moCaiDat() {
    var h = $("#hopCaiDat");
    if (!h.hidden) { h.hidden = true; return; }
    try { veCaiDat(await goi("cai-dat")); h.hidden = false; h.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
    catch (e) { bao(e.message); }
  }
  async function luuCaiDat(im) {
    if (!cd) return;
    cd.ten_file.keep_viet = $("#vietFile").checked;
    cd.ten_excel.keep_viet = $("#vietExcel").checked;
    cd.giu_zip = $("#giuZip").checked;
    cd.luong = Number($("#soLuong").value) || 3;
    try {
      veCaiDat(await goi("cai-dat", { json: cd }));
      if (!im) { $("#thongCaiDat").textContent = "Đã lưu."; $("#thongCaiDat").className = "thong ok"; }
    } catch (e) { bao(e.message); }
  }

  async function traCuu() {
    if (!$("#tu").value || !$("#den").value) { bao("Chọn khoảng ngày trước."); return; }
    try {
      var r = await goi("tra-cuu", { json: { mst: dn, tu: $("#tu").value, den: $("#den").value, loai: loai, he: $("#he").value } });
      theoDoi(r.viec, viecTai, function () { taiBang(); taiDn(); });
    } catch (e) { bao(e.message); }
  }
  async function taiXml() {
    try {
      if (!hdLoc.length && !chon.size) throw new Error("Không có hoá đơn trong bộ lọc.");
      var kieu = Array.prototype.map.call(document.querySelectorAll("[data-tai]:checked"), function (c) { return c.dataset.tai; });
      var r = await goi("tai", { json: { mst: dn, loai: loai, keys: phamViXuat({}).keys,
        tu: $("#tu").value, den: $("#den").value, kieu: kieu } });
      bao("Đang tải " + r.so + " hoá đơn.");
      theoDoi(r.viec, viecTai, function () { taiBang(); });
    } catch (e) { bao(e.message); }
  }
  async function canhBao() {
    if (!$("#hopCanhBao").hidden) { $("#hopCanhBao").hidden=true; return; }
    try {
      var d = await goi("canh-bao?mst=" + encodeURIComponent(dn) + "&tu=" + $("#tu").value + "&den=" + $("#den").value);
      $("#hopCanhBao").hidden = false;
      warnings=d.ds; veCanhBao();
    } catch (e) { bao(e.message); }
  }
  function veCanhBao() {
      var part=pageRows('warnings',warnings,veCanhBao,'#bangCanhBao',JSON.stringify([dn,$('#tu').value,$('#den').value]));
      $("#bangCanhBao").innerHTML = part.rows.map(function (w) {
        return "<tr><td>" + esc(w.muc) + "</td><td>" + esc(w.loai) + "</td><td>" + esc(w.so) + '</td><td class="ngay">' + esc(ngayVN(w.ngay)) +
          "</td><td>" + esc(w.doi_tac) + "</td><td>" + esc(w.noi_dung) + "</td></tr>";
      }).join("") || '<tr><td colspan="6" class="nho">Không có cảnh báo nào.</td></tr>';
  }

  // ================= GMAIL =================
  var dsTk = [];
  function veChiMoi() {
    var tk = dsTk.filter(function (x) { return x.email === $("#gTk").value; })[0];
    $("#gChiMoi").disabled = !(tk && tk.co_moc);
    if ($("#gChiMoi").disabled) $("#gChiMoi").checked = false;
  }
  async function taiGmail() {
    try {
      var c = await goi("gmail/cau-hinh");
      dsTk = c.ds;
      $("#dsGmail").innerHTML = c.ds.map(function (x) {
        return '<li><span>' + esc(x.email) + '</span><span class="nhan' + (x.kieu === "google" ? " ok" : "") + '">' +
          (x.kieu === "google" ? "Google" : "Mật khẩu ứng dụng") + '</span><button type="button" class="xoa" data-xoa-tk="' +
          esc(x.email) + '" title="Gỡ tài khoản">✕</button></li>';
      }).join("") || '<li class="nho">Chưa có tài khoản nào.</li>';
      $("#dsGmail").querySelectorAll("[data-xoa-tk]").forEach(function (b) {
        b.onclick = async function () {
          if (!confirm("Gỡ " + b.dataset.xoaTk + " khỏi MinMin? Hoá đơn đã quét vẫn giữ.")) return;
          try { await goi("gmail/tai-khoan/" + encodeURIComponent(b.dataset.xoaTk), { method: "DELETE" }); } catch (e) { bao(e.message); }
          taiGmail();
        };
      });
      var cu = $("#gTk").value;
      $("#gTk").innerHTML = c.ds.map(function (x) { return '<option value="' + esc(x.email) + '">' + esc(x.email) + '</option>'; }).join("");
      if (cu && c.ds.some(function (x) { return x.email === cu; })) $("#gTk").value = cu;
      $("#gTk").hidden = c.ds.length < 2;
      veChiMoi();
      $("#duongVe").textContent = c.google.duong_ve;
      $("#fClient").client_id.value = c.google.client_id || "";
      $("#fClient").client_secret.placeholder = c.google.co_client ? "Đã lưu (gõ để đổi)" : "Client secret";
      $("#nutGoogle").classList.toggle("tat", !c.google.co_client);
      if (!c.google.co_client) $("#hopClient").open = true;
      var k = await goi("gmail/ket-qua");
      dsG = k.ds;
      var pub = $("#gmPublisher"), chosen = pub.value;
      pub.innerHTML = '<option value="">Tất cả hãng</option>' + Array.from(new Set(dsG.map(function(r){return r.nha_cung_cap || "unknown";}))).sort().map(function(v){return '<option value="'+esc(v)+'">'+esc(v === "unknown" ? "Chưa nhận diện" : v.toUpperCase())+'</option>';}).join('');
      pub.value = chosen; veGmail();
    } catch (e) { bao(e.message); }
  }


  function veGmail() {
    updateGroups("gm", dsG);
    updateFileCounts("gm", dsG);
    gmLoc = InvoiceUI.filter(dsG, readFilter("gm"));
    var valid = new Set(gmLoc.map(function(r) { return r.id; }));
    gChon.forEach(function(k) { if (!valid.has(k)) gChon.delete(k); });
      var part=pageRows('gm',gmLoc,veGmail,'#bangGmail',JSON.stringify(readFilter('gm')));
      $("#bangGmail").innerHTML = part.rows.map(function (r, index) {
        var id = encodeURIComponent(r.id);
        var file = (r.co_xml ? '<a href="' + API + "gmail/xem/" + id + '" target="_blank" rel="noopener">Xem</a><a href="' + API + "gmail/tep/" + id + '/xml">XML</a>' : "") +
          (r.co_pdf ? '<a href="' + API + "gmail/tep/" + id + '/pdf">PDF gốc</a>' : "") +
          (r.co_trong_dong ? '<a href="' + API + "gmail/tep/" + id + '/trong_dong">Trống đồng (TCT)</a>' : "") +
          (r.link ? '<a href="' + esc(r.link) + '" target="_blank" rel="noopener noreferrer">Trang tra cứu</a>' : "") +
          '<button class="nut phu" data-glookup="' + esc(r.id) + '">Mã tra cứu</button>';
        return '<tr><td><input type="checkbox" data-gid="' + esc(r.id) + '"' + (gChon.has(r.id) ? " checked" : "") + '></td><td class="row-number">' + (part.start+index+1) + '</td><td class="ngay">' + esc(ngayVN(InvoiceUI.date(r))) + (!r.ngay_hd ? '<small class="nho"> (email)</small>' : '') + "</td><td>" + esc(r.so) + '</td><td class="doi">' + esc(r.ban_ten || r.tu) +
          "</td><td>" + esc(r.hop_thu || "") + '</td><td class="so">' + (r.tong ? tien(r.tong) : "") + "</td><td>" + esc(r.nha_cung_cap) + "</td><td>" +
          (r.can_tai_tay ? '<span class="nhan loi">Cần tải tay</span>' : "") + esc(r.trang_thai) + "</td><td>" +
          (r.lien_ket ? '<span class="nhan ok" title="MST ' + esc(r.lien_ket.mst) + '">Đã ghép</span>' : "") + "</td><td>" + file + "</td></tr>";
      }).join("") || '<tr><td colspan="11" class="nho">' + (dsG.length ? 'Không có hoá đơn khớp bộ lọc. Đổi kỳ thời gian hoặc đặt lại bộ lọc.' : 'Chưa quét. Thêm tài khoản Gmail, chọn khoảng ngày rồi bấm Quét.') + '</td></tr>';

    $("#bangGmail").querySelectorAll("[data-gid]").forEach(function(c) { c.onchange = function() { if(c.checked) gChon.add(c.dataset.gid); else gChon.delete(c.dataset.gid); demGmail(); }; });
    $("#bangGmail").querySelectorAll("[data-glookup]").forEach(function(b) { b.onclick = function() { openLookup("gmail",b.dataset.glookup); }; });
    demGmail();
  }
  function demGmail() {
    var a = $("#gChonHet"); a.checked = gmLoc.length > 0 && gChon.size === gmLoc.length; a.indeterminate = gChon.size > 0 && gChon.size < gmLoc.length;
    $("#gmCount").textContent = "Đang lọc " + gmLoc.length + "/" + dsG.length + " · Đã chọn " + gChon.size + ". Tải/xuất/in dùng " + (gChon.size || gmLoc.length) + " dòng này.";
  }
  function gmailScope() {
    var ids = gmLoc.filter(function(r) { return !gChon.size || gChon.has(r.id); }).map(function(r) { return r.id; });
    if (!ids.length) throw new Error("Không có hoá đơn trong bộ lọc.");
    return {ids:ids};
  }

  async function gmailExport(type) { try { await taiFile("gmail/" + type,gmailScope()); } catch(e) { bao(e.message); } }
  var invoiceGroups = {hd:"", gm:""};
  function updateGroups(prefix, rows) {
    var box = $("#" + prefix + "Groups"); if (!box) return;
    var f = readFilter(prefix); f.group = "";
    var periodRows = InvoiceUI.filter(rows, {from:f.from,to:f.to});
    box.querySelectorAll("[data-group]").forEach(function(b) {
      var group = b.dataset.group, count = InvoiceUI.filter(periodRows,{group:group}).length;
      b.textContent = (group === "bank" ? "Chứng từ ngân hàng" : group === "business" ? "Hóa đơn kinh doanh" : "Tất cả") + " (" + count + ")";
      b.setAttribute("aria-pressed", String(invoiceGroups[prefix] === group));
      b.classList.toggle("chinh", invoiceGroups[prefix] === group);
    });
    var selected = InvoiceUI.filter(rows, readFilter(prefix));
    var missing = selected.filter(function(r){return !r.co_goc;}).length;
    box.querySelector("p").textContent = invoiceGroups[prefix] === "bank" ?
      "Chứng từ do ngân hàng phát hành: " + selected.length + " dòng đang lọc · Tổng " + tien(selected.reduce(function(sum,r){return sum + Number(r.tong || 0);},0)) + " đ · " + missing + " chưa có bản gốc. Tải, Excel, ZIP và in gộp áp dụng cho mục đang chọn. Nhận diện theo tên/MST người bán." :
      "Chọn mục để kiểm soát riêng chứng từ ngân hàng hoặc hóa đơn kinh doanh.";
  }
  function readFilter(prefix) {
    function value(id) { return $("#" + prefix + id).value; }
    return {group:invoiceGroups[prefix],q:prefix === "hd" ? $("#loc").value : value("Query"),supplier:value("Supplier"),number:value("Number"),
      min:value("Min"),max:value("Max"),file:value("File"),sort:value("Sort"),publisher:value("Publisher"),status:value("Status"),
      from:prefix === "gm" ? $("#gTu").value : "",to:prefix === "gm" ? $("#gDen").value : ""};
  }
  function updateFileCounts(prefix, rows) {
    var f = readFilter(prefix); f.file = "";
    var base = InvoiceUI.filter(rows, f);
    var labels = {xml:"Có XML", "no-xml":"Chưa có XML", tax:"Có Trống đồng", "no-tax":"Chưa có Trống đồng", original:"Có PDF gốc", "no-original":"Chưa có PDF gốc"};
    Array.from($("#" + prefix + "File").options).forEach(function(o) {
      o.textContent = (labels[o.value] || "Tất cả") + " (" + InvoiceUI.filter(base, {file:o.value}).length + ")";
    });
  }
  function buildFilters(prefix, table) {
    var box = document.createElement("div"); box.className = "invoice-filters";
    box.innerHTML = (prefix === "gm" ? '<label>Tìm kiếm<input id="gmQuery" type="search" placeholder="Tên, MST, số, ký hiệu" /></label>' : '') +
      ('<label>Hãng phát hành<select id="' + prefix + 'Publisher"><option value="">Tất cả hãng</option></select></label><label>Trạng thái bản gốc<select id="' + prefix + 'Status"><option value="">Tất cả</option><option value="manual">' + (prefix === 'hd' ? 'Tất cả chưa có bản gốc' : 'Cần tải tay / tải lại') + '</option>' + (prefix === 'hd' ? '<option value="no-xml">Chưa tải XML</option><option value="pending">Có XML, chưa thử bản gốc</option><option value="failed">Đã thử, chưa tải được gốc</option>' : '') + '<option value="done">' + (prefix === 'hd' ? 'Đã có bản gốc' : 'Không cần tải lại') + '</option></select></label>') +
      '<label>Nhà cung cấp / MST<input id="' + prefix + 'Supplier" type="search" placeholder="Tên người bán hoặc MST" /></label>' +
      '<label>Số hoá đơn<input id="' + prefix + 'Number" type="search" /></label>' +
      '<label>Số tiền từ<input id="' + prefix + 'Min" type="number" step="any" /></label>' +
      '<label>Đến số tiền<input id="' + prefix + 'Max" type="number" step="any" /></label>' +
      '<label>Chứng từ<select id="' + prefix + 'File"><option value="">Tất cả</option><option value="xml">Có XML</option><option value="no-xml">Chưa có XML</option><option value="tax">Có Trống đồng</option><option value="no-tax">Chưa có Trống đồng</option><option value="original">Có PDF gốc</option><option value="no-original">Chưa có PDF gốc</option></select></label>' +
      '<label>Sắp xếp<select id="' + prefix + 'Sort">' + [['date-desc','Ngày mới trước'],['date-asc','Ngày cũ trước'],['amount-asc','Số tiền nhỏ → lớn'],['amount-desc','Số tiền lớn → nhỏ'],['name-asc','Tên A → Z'],['name-desc','Tên Z → A'],['number-asc','Số HĐ tăng dần'],['number-desc','Số HĐ giảm dần']].map(function(o){return '<option value="'+o[0]+'">'+o[1]+'</option>';}).join('') + '</select></label>' +
      '<button class="nut" type="button" data-reset>Đặt lại bộ lọc</button>' + (prefix === "gm" ? '<p id="gmCount" class="nho"></p><p class="nho">Trống đồng lấy từ hoá đơn đã ghép trong kho TCT. ZIP gồm các file đã có; in gộp sử dụng PDF gốc.</p>' : '');
    $(table).closest(".cuon").before(box);
    var groups = document.createElement("section"); groups.id = prefix + "Groups"; groups.className = "invoice-groups";
    groups.setAttribute("aria-label", "Nhóm chứng từ");
    groups.innerHTML = '<div class="hang">' + ["","business","bank"].map(function(g){return '<button type="button" class="nut" data-group="'+g+'"></button>';}).join('') + '</div><p class="nho"></p>';
    box.before(groups);
    groups.querySelectorAll("[data-group]").forEach(function(b){b.onclick = function(){invoiceGroups[prefix] = b.dataset.group; (prefix === "gm" ? gChon : chon).clear(); (prefix === "gm" ? veGmail : veBang)();};});
    box.querySelectorAll("input,select").forEach(function(e) { e.oninput = e.onchange = prefix === "gm" ? veGmail : function(){chon.clear(); veBang();}; });
    box.querySelector("[data-reset]").onclick = function() { box.querySelectorAll("input").forEach(function(e){e.value="";}); $("#"+prefix+"File").value=""; $("#"+prefix+"Sort").value="date-desc"; $("#"+prefix+"Publisher").value=""; $("#"+prefix+"Status").value=""; if(prefix === "hd") $("#loc").value=""; (prefix === "gm" ? veGmail : veBang)(); };
  }
  function buildPeriod(prefix, from, to, refresh) {
    var box=document.createElement("div"); box.className="hang period-filter";
    var opts=[['custom','Tuỳ chọn'],['all','Tất cả ngày'],['today','Hôm nay'],['yesterday','Hôm qua'],['last7','7 ngày qua'],['last30','30 ngày qua'],['last90','90 ngày qua'],['lastmonth','Tháng trước'],['week','Đầu tuần đến nay'],['month','Đầu tháng đến nay'],['year','Cả năm'],['h1','6 tháng đầu năm'],['h2','6 tháng cuối năm']];
    for(var m=1;m<=12;m++) opts.push(['m'+m,'Tháng '+m]);
    for(var q=1;q<=4;q++) opts.push(['q'+q,'Quý '+q]);
    box.innerHTML='<label>Kỳ thời gian<select id="'+prefix+'Period">'+opts.map(function(o){return '<option value="'+o[0]+'">'+o[1]+'</option>';}).join('')+'</select></label><label>Năm<input id="'+prefix+'Year" type="number" min="2000" max="2100" value="'+new Date().getFullYear()+'" /></label>';
    $(from).closest(".hang").before(box);
    function change() { var id=$("#"+prefix+"Period").value; if(id==='custom') return; var dates=InvoiceUI.period(id,$("#"+prefix+"Year").value); $(from).value=dates[0]; $(to).value=dates[1]; refresh(); }
    $("#"+prefix+"Period").onchange=$("#"+prefix+"Year").onchange=change;
    [from,to].forEach(function(id){$(id).addEventListener("change",function(){ $("#"+prefix+"Period").value='custom'; if(prefix==='gm') refresh(); });});
  }
  var lookupContext=null;
  function drawLookup(data) {
    $("#lookupCode").value=data.code || "";
    $("#lookupNote").textContent=data.note || (data.code ? "Mã lấy từ XML, Gmail hoặc bạn đã nhập." : "Chưa có mã trong nguồn đã đọc. Đối chiếu Gmail hoặc nhập mã từ email nhà phát hành.");
    $("#lookupCopy").disabled=!data.code;
    $("#lookupXml").hidden=lookupContext.kind!=='tct' || data.has_xml!==false;
    $("#lookupLink").hidden=!data.url;
    if(data.url) $("#lookupLink").href=data.url; else $("#lookupLink").removeAttribute("href");
  }
  async function openLookup(kind,id) {
    try {
      lookupContext={kind:kind,id:id};
      if(kind==='gmail') { var r=dsG.find(function(r){return r.id===id;}); drawLookup({code:r.ma_tra_cuu,url:r.link}); }
      else drawLookup(await goi('tra-cuu-hang',{json:{mst:dn,loai:loai,key:id}}));
      $("#lookupDialog").showModal();
    } catch(e) { bao(e.message); }
  }
  var capConfig={keys:{}};
  function showCap(c) { capConfig=c; $("#capProvider").value=c.provider; $("#capEnabled").checked=c.enabled; capPlaceholder(); }
  function capPlaceholder() { var saved=capConfig.keys[$("#capProvider").value]; $("#capKey").value=""; $("#capKey").placeholder=saved ? "Đã lưu (để trống giữ nguyên)" : "Nhập API key"; $("#capStatus").textContent=saved ? "Đã có key dịch vụ này" : "Chưa có key dịch vụ này"; }
  async function saveCap(remove) {
    try { showCap(await goi('captcha-api',{json:{provider:$("#capProvider").value,api_key:$("#capKey").value,enabled:remove?false:$("#capEnabled").checked,xoa_key:remove}})); bao("Đã lưu cấu hình captcha."); } catch(e) { bao(e.message); }
  }
  function setupTools() {
    $('#collapseWarnings').onclick=function(){$('#hopCanhBao').hidden=true;};
    buildFilters('hd','#bangHd'); buildFilters('gm','#bangGmail');
    buildPeriod('hd','#tu','#den',function(){chon.clear();taiBang();}); buildPeriod('gm','#gTu','#gDen',veGmail);
    goi('captcha-api').then(showCap).catch(function(e){bao(e.message);});
    $("#capProvider").onchange=capPlaceholder;
    $("#capBalance").onclick=async function(){ this.disabled=true; try{ var b=await goi('captcha-api/so-du',{json:{provider:$("#capProvider").value}}); $("#capStatus").textContent="Số dư: "+b.balance+" USD"; }catch(e){bao(e.message);}finally{this.disabled=false;} };
    $("#captchaForm").onsubmit=function(e){e.preventDefault();saveCap(false);}; $("#capDelete").onclick=function(){saveCap(true);};
    $("#lookupClose").onclick=function(){$("#lookupDialog").close();};
    $("#lookupXml").onclick=async function(){
      this.disabled=true;
      try {
        var context=lookupContext;
        var r=await goi('tai',{json:{mst:dn,loai:loai,keys:[context.id],kieu:['xml']}});
        $("#lookupDialog").close();
        theoDoi(r.viec,viecTai,async function(){await taiBang(); await openLookup('tct',context.id);});
      } catch(e){bao(e.message);} finally {this.disabled=false;}
    };
    $("#lookupCode").oninput=function(){ $("#lookupCopy").disabled=!this.value.trim(); $("#lookupLink").hidden=true; $("#lookupNote").textContent="Bấm Lưu mã để cập nhật đường dẫn tra cứu."; };
    $("#lookupCopy").onclick=async function(){ try { if(!$("#lookupCode").value) throw new Error("Chưa có mã để sao chép."); await navigator.clipboard.writeText($("#lookupCode").value); bao("Đã sao chép mã tra cứu."); } catch(e){bao(e.message);} };
    $("#lookupForm").onsubmit=async function(e){
      e.preventDefault(); try {
        var code=$("#lookupCode").value;
        if(lookupContext.kind==='gmail') { await goi('gmail/ma-tra-cuu',{json:{id:lookupContext.id,code:code}}); await taiGmail(); var r=dsG.find(function(r){return r.id===lookupContext.id;}); drawLookup({code:r.ma_tra_cuu,url:r.link}); }
        else drawLookup(await goi('tra-cuu-hang',{json:{mst:dn,loai:loai,key:lookupContext.id,code:code}}));
        bao("Đã lưu mã tra cứu.");
      } catch(e){bao(e.message);}
    };
  }

  // ---------------- gắn sự kiện
  function gan() {
    document.querySelectorAll(".tab button").forEach(function (b) { b.onclick = function () { moTab(b.dataset.tab); }; });
    if ($("#ctLamMoi")) $("#ctLamMoi").onclick = function(){ if (dn) taiBang(); else veChungTu(); };
    if ($("#nutBoChungTu")) $("#nutBoChungTu").onclick = async function(){ this.disabled = true; try { await taiFile("bo-chung-tu", phamViChungTu()); } catch(e) { bao(e.message); } finally { this.disabled = false; } };
    ["#ctKieu", "#ctPhamVi"].forEach(function(id){ if($(id)) $(id).onchange = veChungTu; });
    ["#ctNhomHoaDon", "#ctNhomKiemTra", "#ctLoaiHd"].forEach(function(id){ if($(id)) $(id).querySelectorAll("input").forEach(function(c){ c.onchange = veChungTu; }); });
    if ($("#ctTabs")) $("#ctTabs").querySelectorAll("[data-doc-tab]").forEach(function(b){ b.onclick = function(){ veDocTabs(b.dataset.docTab); }; });
    if ($("#ctThemNhanSu")) $("#ctThemNhanSu").onclick = function(){ themNhanSu({}); };
    if ($("#ctNhanSuMau")) $("#ctNhanSuMau").onclick = function(){ themNhanSu({ ho_ten:"Nguyễn Văn A", ngay_sinh:"01/01/1998", cccd:"001098000001", dia_chi:"Hà Nội", chuc_vu:"Nhân viên kinh doanh", luong:"8.000.000", ngay_vao:"01/08/2026", ma_bhxh:"0123456789" }); };
    if ($("#ctNhanSuBody") && !$("#ctNhanSuBody").children.length) themNhanSu({});
    $("#fDn").onsubmit = async function (ev) {
      ev.preventDefault();
      var f = ev.target;
      try {
        var r = await goi("doanh-nghiep", { json: { mst: f.mst.value, ten: f.ten.value, mat_khau: f.mat_khau.value } });
        f.reset(); f.closest("details").open = false;
        dn = r.mst; await taiDn(); chonDn(r.mst);
      } catch (e) { bao(e.message); }
    };
    $("#doiCaptcha").onclick = layCaptcha;
    $("#nutDangNhap").onclick = dangNhap;
    $("#oCaptcha").onkeydown = function (e) { if (e.key === "Enter") dangNhap(); };
    document.querySelectorAll(".loai button").forEach(function (b) {
      b.onclick = function () {
        loai = b.dataset.loai; chon.clear();
        document.querySelectorAll(".loai button").forEach(function (x) { x.classList.toggle("on", x === b); });
        taiBang();
      };
    });
    $("#tu").onchange = $("#den").onchange = taiBang;
    $("#nutTraCuu").onclick = traCuu;
    $("#nutTai").onclick = taiXml;
    $("#nutCanhBao").onclick = canhBao;
    $("#nutCaiDat").onclick = moCaiDat;
    $("#luuCaiDat").onclick = function () { luuCaiDat(false); };
    ["#vietFile", "#vietExcel", "#giuZip", "#soLuong"].forEach(function (id) { $(id).onchange = function () { luuCaiDat(true); }; });
    $("#nutZip").onclick = async function () {
      var lt = Array.prototype.map.call(document.querySelectorAll("[data-zip]:checked"), function (c) { return c.dataset.zip; });
      if (!lt.length) { bao("Tích ít nhất một loại file."); return; }
      try { await taiFile("xuat", phamViXuat({ kieu: "zip", loai_tep: lt, layout: $('#zipLayout').value })); this.closest("details").open = false; } catch (e) { bao(e.message); }
    };
    $("#nutGopPdf").onclick = async function () {
      var m = (document.querySelector("[name=cheDoIn]:checked") || {}).value || "goc_uu_tien";
      try { await taiFile("xuat", phamViXuat({ kieu: "pdf_gop", che_do: m })); this.closest("details").open = false; } catch (e) { bao(e.message); }
    };
    $("#gGhep").onclick = async function () {
      try { var r = await goi("gmail/ghep-lai", { json: gmailScope() }); bao("Ghép thêm " + r.ghep + " hoá đơn có sẵn, thêm mới " + r.moi + " hoá đơn vào Tải Hoá Đơn."); taiGmail(); }
      catch (e) { bao(e.message); }
    };
    $("#nutDangXuat").onclick = async function () { await goi("dang-xuat/" + encodeURIComponent(dn), { method: "POST" }); taiDn(); };
    $("#loc").oninput = function(){chon.clear(); veBang();};
    $("#chonHet").onchange = function () {
      var bat = this.checked;
      hdLoc.forEach(function(r) { if(bat) chon.add(r.key); else chon.delete(r.key); }); veBang();
    };
    document.querySelectorAll("[data-xuat]").forEach(function (b) {
      b.onclick = async function () {
        b.disabled = true;
        try { await taiFile("xuat", phamViXuat({ kieu: b.dataset.xuat })); }
        catch (e) { bao(e.message); } finally { b.disabled = false; }
      };
    });
    $("#fGmail").onsubmit = async function (ev) {
      ev.preventDefault();
      var f = ev.target;
      try {
        await goi("gmail/cau-hinh", { json: { email: f.email.value, mat_khau: f.mat_khau.value } });
        f.reset();
        $("#thongGmail").textContent = "Đã thêm."; $("#thongGmail").className = "thong ok";
        taiGmail();
      } catch (e) { $("#thongGmail").textContent = e.message; $("#thongGmail").className = "thong loi"; }
    };
    $("#fClient").onsubmit = async function (ev) {
      ev.preventDefault();
      var f = ev.target;
      try {
        await goi("gmail/google/client", { json: { client_id: f.client_id.value, client_secret: f.client_secret.value } });
        f.client_secret.value = "";
        $("#thongGmail").textContent = "Đã lưu. Giờ bấm Đăng nhập bằng Google."; $("#thongGmail").className = "thong ok";
        $("#hopClient").open = false;
        taiGmail();
      } catch (e) { $("#thongGmail").textContent = e.message; $("#thongGmail").className = "thong loi"; }
    };
    $("#chepVe").onclick = function () {
      navigator.clipboard.writeText($("#duongVe").textContent).then(function () { bao("Đã chép."); }, function () {});
    };
    $("#nutGoogle").onclick = function (ev) {
      if (this.classList.contains("tat")) { ev.preventDefault(); $("#hopClient").open = true; bao("Cài đặt Đăng nhập bằng Google trước (làm một lần)."); }
    };
    $("#gTk").onchange = veChiMoi;
    $("#nutQuet").onclick = async function () {
      try {
        var r = await goi("gmail/quet", { json: { email: $("#gTk").value, tu: $("#gTu").value, den: $("#gDen").value, chi_moi: $("#gChiMoi").checked } });
        theoDoi(r.viec, viecGmail, taiGmail);
      } catch (e) { bao(e.message); }
    };
    $("#gXuat").onclick = function () { gmailExport("xuat"); };
    $("#gZip").onclick = function () { gmailExport("zip"); };
    $("#gIn").onclick = function () { gmailExport("pdf-gop"); };
    $("#gChonHet").onchange = function() { var checked = this.checked; gmLoc.forEach(function(r) { if(checked) gChon.add(r.id); else gChon.delete(r.id); }); veGmail(); };
    $("#gTai").onclick = async function() { try { var r = await goi("gmail/tai",{json:gmailScope()}); theoDoi(r.viec,viecGmail,taiGmail); } catch(e) { bao(e.message); } };
  }

  document.addEventListener("click", function (ev) {
    document.querySelectorAll("details.menu[open]").forEach(function (m) { if (!m.contains(ev.target)) m.open = false; });
  });

  async function batDau() {
    datNgayMacDinh($("#tu"), $("#den"));
    datNgayMacDinh($("#gTu"), $("#gDen"));
    setupTools();
    gan();
    setupRecovery();
    var s;
    try { s = await goi("trang-thai"); } catch (e) { bao(e.message); return; }
    tt.tai = s.tai_hoa_don; tt.gmail = s.gmail; tt.chungtu = s.bo_chung_tu || s.tai_hoa_don;
    document.querySelector('.tab [data-tab="tai"]').disabled = !tt.tai;
    document.querySelector('.tab [data-tab="gmail"]').disabled = !tt.gmail;
    document.querySelector('.tab [data-tab="chungtu"]').disabled = !tt.chungtu;
    if (!s.gia_lap_chrome) $("#ghiChuCffi").textContent = "Máy chủ thiếu thư viện curl_cffi nên cổng thuế dễ chặn (lỗi 403). Cập nhật MinMin bản mới.";
    var qs = new URLSearchParams(location.search);
    var muon = qs.get("tab") === "gmail" ? "gmail" : qs.get("tab") === "chungtu" ? "chungtu" : "tai";
    if (qs.get("them")) setTimeout(function () { bao("Đã thêm " + qs.get("them") + " bằng Google."); }, 300);
    moTab(muon);
  }
  batDau();
})();
