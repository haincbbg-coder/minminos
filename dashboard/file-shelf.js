/* Shared, device-local working copies. No automatic sending, uploading, or original-file writes. */
(function () {
  'use strict';
  const R = window.MinMinFileRules;
  let db, owner = '', items = [], selected = new Set(), panel, launcher, list, status, busy = false;
  let pdfLoading;
  let workQueue=Promise.resolve();
  let thumbURLs=[];
  const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('minmin-file-shelf') : null;
  function el(tag, text, cls) {
    const n = document.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n;
  }
  function button(text, fn, cls) { const b = el('button', text, cls); b.type = 'button'; b.onclick = fn; return b; }
  async function auth() {
    const res = await fetch('/auth/status', {cache:'no-store'}), a = await res.json();
    if (!res.ok || !a.authed) {
      if (panel) panel.hidden = true;
      if (launcher) launcher.hidden = true;
      items = []; selected.clear();
      throw Error('Đăng nhập MinMin để mở khay.');
    }
    const next = a.username || 'local';
    if (owner !== next) { items = []; selected.clear(); }
    owner = next;
    if (launcher) launcher.hidden = false;
  }
  function database() {
    if (db) return Promise.resolve(db);
    return new Promise((resolve,reject) => {
      const req = indexedDB.open('minmin-file-shelf-v1',1);
      req.onupgradeneeded = () => req.result.createObjectStore('shelves');
      req.onerror = () => reject(Error('Trình duyệt không cho lưu khay. Kiểm tra quyền lưu dữ liệu trang web.'));
      req.onsuccess = () => { db = req.result; resolve(db); };
    });
  }
  async function store(change) {
    await auth();
    const d = await database(), key = owner;
    return new Promise((resolve,reject) => {
      const tx = d.transaction('shelves', change ? 'readwrite' : 'readonly'), s = tx.objectStore('shelves');
      let result, error;
      s.get(key).onsuccess = e => {
        try { result = e.target.result || []; if (change) { result = change(result); s.put(result,key); } }
        catch (err) { error = err; tx.abort(); }
      };
      tx.oncomplete = () => { items = result; selected = new Set([...selected].filter(id => items.some(x => x.id === id))); render(); if(change && channel) channel.postMessage('changed'); resolve(result); };
      tx.onabort = tx.onerror = () => reject(error || Error('Không lưu được khay; bộ nhớ trình duyệt có thể đã đầy.'));
    });
  }
  function report(text) { if(status) status.textContent = text; const note=document.querySelector('.mm-file-dialog[open] .mm-note');if(note)note.textContent=text; }
  function task(fn) {
    // Preserve rapid additions from different inbox messages; never silently drop a click.
    workQueue=workQueue.then(async()=>{
      busy = true; report('Đang xử lý…'); render();
      try { await auth(); await fn(); }
      catch(e) { report(e.message || 'Không xử lý được file.'); }
      finally { busy = false; if(status && status.textContent==='Đang xử lý…') report(''); render(); }
    });
    return workQueue;
  }
  async function add(blob, name, source) {
    R.validate([],blob);
    const head=new Uint8Array(await blob.slice(0,12).arrayBuffer());
    const ascii=String.fromCharCode(...head);
    const type=ascii.startsWith('%PDF-')?'application/pdf':head[0]===137&&ascii.slice(1,4)==='PNG'?'image/png':head[0]===255&&head[1]===216?'image/jpeg':ascii.startsWith('RIFF')&&ascii.slice(8,12)==='WEBP'?'image/webp':blob.type;
    if(type!==blob.type)blob=new Blob([blob],{type});
    await store(rows => { R.validate(rows,blob); return rows.concat({id:crypto.randomUUID(), name:String(name || 'tep').slice(0,240), source:String(source || 'Máy này').slice(0,300), blob, type:R.kind(name,blob.type), date:Date.now()}); });
  }
  async function addFiles(files) {
    await open();
    await task(async () => {
      let count = 0;
      for (const f of files) {
        try { await add(f,f.name,'Máy này'); count++; }
        catch(e) { throw Error(`Đã thêm ${count}/${files.length} file. ${e.message}`); }
      }
      report(`Đã thêm ${count} file vào khay.`);
    });
  }
  async function limitedBlob(res) {
    if (!res.ok) {
      let error = ''; try { error = (await res.json()).error || ''; } catch (_) {}
      throw Error(error || `Không tải được file (HTTP ${res.status}).`);
    }
    const reader = res.body.getReader(), parts = []; let size = 0;
    try {
      for (;;) { const {done,value} = await reader.read(); if(done) break; size += value.length; if(size > R.MAX_FILE) throw Error('Mỗi file tối đa 20 MB.'); parts.push(value); }
    } catch(e) { await reader.cancel(); throw e; }
    return new Blob(parts,{type:(res.headers.get('content-type') || '').split(';')[0]});
  }
  async function addURL(raw, name, source) {
    await open();
    await task(async () => {
      const url = R.safeURL(raw,location.href);
      if (!url) throw Error('Địa chỉ file không được hỗ trợ.');
      const u = new URL(url); let res;
      if (u.origin === location.origin) res = await fetch(url,{signal:AbortSignal.timeout(60000)});
      else { const data = new FormData(); data.append('url',url); res = await fetch('/conversations/file-shelf/image',{method:'POST',body:data,signal:AbortSignal.timeout(70000)}); }
      const blob = await limitedBlob(res);
      if (/text\/html/.test(blob.type)) throw Error('Đường dẫn trả về trang web, không phải file.');
      await add(blob,name || decodeURIComponent(u.pathname.split('/').pop()) || 'tep',source);
      report('Đã giữ bản sao trong khay.');
    });
  }
  function download(blob,name) {
    const url = URL.createObjectURL(blob), a = el('a'); a.href=url; a.download=name;
    document.body.append(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(url),60000);
  }
  function dialog(title) {
    const d = el('dialog',null,'mm-file-dialog'), h=el('header');
    h.append(el('h2',title),button('Đóng',()=>d.close())); d.append(h); document.body.append(d);
    d.addEventListener('close',()=>d.remove(),{once:true}); d.showModal(); return d;
  }
  async function picture(blob) {
    const img = await createImageBitmap(blob);
    if(img.width * img.height > 24000000) { img.close(); throw Error('Ảnh quá lớn để chỉnh sửa trên trình duyệt (tối đa 24 triệu điểm ảnh).'); }
    return img;
  }
  function field(parent,label,tag,options) {
    const l = el('label',label), n = el(tag);
    if(tag==='select') options.forEach(([v,t]) => { const o=el('option',t);o.value=v;n.append(o); });
    l.append(n);parent.append(l);return n;
  }
  async function editImage(item) {
    const img=await picture(item.blob), d=dialog('Chỉnh ảnh · '+item.name), canvas=el('canvas');
    const fields=el('div',null,'mm-file-fields'); d.append(canvas,fields);
    const ratio=field(fields,'Cắt giữa ảnh','select',[['0','Giữ nguyên'],['1','Vuông 1:1'],['0.5625','Dọc 9:16'],['1.77777778','Ngang 16:9'],['0.75','Dọc 3:4']]);
    const width=field(fields,'Chiều rộng (px)','input');width.type='number';width.min='64';width.max='4096';width.value=String(Math.min(img.width,1920));
    const format=field(fields,'Định dạng','select',[['image/png','PNG'],['image/jpeg','JPG'],['image/webp','WebP']]);
    const text=field(fields,'Chú thích dưới ảnh','input');text.maxLength=100;
    let turns=0;
    function paint() {
      const sw=turns%2?img.height:img.width, sh=turns%2?img.width:img.height;
      const c=R.crop(sw,sh,Number(ratio.value)), w=Math.max(64,Math.min(4096,Number(width.value)||1920));
      const h=Math.round(w*c.h/c.w);
      if(w*h>16000000) throw Error('Ảnh đầu ra quá lớn. Giảm chiều rộng hoặc chọn tỷ lệ cắt.');
      canvas.width=w;canvas.height=h;
      const ctx=canvas.getContext('2d');
      if(format.value==='image/jpeg') {ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h);}
      ctx.save();ctx.scale(w/c.w,h/c.h);ctx.translate(-c.x,-c.y);ctx.translate(sw/2,sh/2);ctx.rotate(turns*Math.PI/2);ctx.drawImage(img,-img.width/2,-img.height/2);ctx.restore();
      if(text.value) { const fs=Math.max(16,Math.round(w/32));ctx.fillStyle='rgba(0,0,0,.72)';ctx.fillRect(0,h-fs*2.4,w,fs*2.4);ctx.fillStyle='#fff';ctx.font=`${fs}px sans-serif`;ctx.textAlign='center';ctx.fillText(text.value,w/2,h-fs*.85,w-24); }
    }
    function update() {try {paint(); note.textContent='Bản gốc được giữ nguyên. Chú thích được gắn vào bản sao.';} catch(e){note.textContent=e.message;} }
    const note=el('p','', 'mm-note'); d.append(note);
    fields.oninput=update;
    const actions=el('div',null,'mm-shelf-actions');
    actions.append(button('Xoay 90°',()=>{turns=(turns+1)%4;update();}),button('Lưu bản sao vào khay',async()=>{
      await task(async()=>{paint();const blob=await new Promise(resolve=>canvas.toBlob(resolve,format.value,.9));if(!blob)throw Error('Không xuất được ảnh.');await add(blob,R.nameCopy(item.name,blob.type.split('/')[1].replace('jpeg','jpg')),item.name);d.close();report('Đã lưu ảnh mới vào khay.');});
    },'mm-primary'));
    d.append(actions);d.addEventListener('close',()=>img.close(),{once:true});update();
  }
  async function pdf() {
    if(window.PDFLib) return window.PDFLib;
    if(!pdfLoading) pdfLoading=new Promise((resolve,reject)=>{const s=el('script');s.src='/static/vendor/pdf-lib-1.17.1.min.js';s.onload=()=>resolve(window.PDFLib);s.onerror=()=>{pdfLoading=null;s.remove();reject(Error('Không nạp được công cụ PDF. Thử lại.'));};document.head.append(s);});
    return pdfLoading;
  }
  async function mergePDF() {
    const chosen=items.filter(x=>selected.has(x.id));
    if(!chosen.length || chosen.some(x=>!['image','pdf'].includes(x.type))) throw Error('Chỉ chọn ảnh PNG/JPG/WebP và PDF để gộp.');
    const {PDFDocument}=await pdf(), output=await PDFDocument.create();
    let count=0;
    for(const item of chosen) {
      report('Đang ghép: '+item.name);
      if(item.type==='pdf') {
        let source;
        try {source=await PDFDocument.load(await item.blob.arrayBuffer());} catch (_) {throw Error('Không đọc được PDF hoặc file có mật khẩu: '+item.name);}
        count+=source.getPageCount(); if(count>200) throw Error('Mỗi lần gộp tối đa 200 trang.');
        const pages=await output.copyPages(source,source.getPageIndices());pages.forEach(p=>output.addPage(p));
      } else {
        if(++count>200) throw Error('Mỗi lần gộp tối đa 200 trang.');
        const im=await picture(item.blob), c=el('canvas');
        const scale=Math.min(1,2400/Math.max(im.width,im.height));c.width=Math.round(im.width*scale);c.height=Math.round(im.height*scale);c.getContext('2d').drawImage(im,0,0,c.width,c.height);im.close();
        const bytes=await (await new Promise(r=>c.toBlob(r,'image/png'))).arrayBuffer(), embedded=await output.embedPng(bytes);
        const page=output.addPage([595.28,841.89]), dim=embedded.scale(Math.min(555/embedded.width,802/embedded.height));
        page.drawImage(embedded,{x:(595.28-dim.width)/2,y:(841.89-dim.height)/2,width:dim.width,height:dim.height});
      }
    }
    const blob=new Blob([await output.save()],{type:'application/pdf'});
    await add(blob,'Ho-so-gop.pdf',`${chosen.length} file · ${count} trang`);report(`Đã tạo PDF ${count} trang. Chọn Xem / sửa để xem trước khi tải hoặc in.`);
  }
  async function preview(item) {
    if(item.type==='image') return editImage(item);
    if(item.type!=='pdf') {download(item.blob,item.name);return;}
    const d=dialog(item.name), url=URL.createObjectURL(item.blob), frame=el('iframe');frame.title='Xem trước PDF';frame.src=url;
    d.append(frame,button('Tải PDF để in',()=>download(item.blob,item.name),'mm-primary'));
    d.addEventListener('close',()=>URL.revokeObjectURL(url),{once:true});
  }
  async function collage() {
    const chosen=items.filter(x=>selected.has(x.id));
    if(chosen.length<2 || chosen.length>9 || chosen.some(x=>x.type!=='image')) throw Error('Chọn từ 2 đến 9 ảnh để ghép.');
    const cols=Math.ceil(Math.sqrt(chosen.length)), rows=Math.ceil(chosen.length/cols), c=el('canvas');c.width=cols*600;c.height=rows*600;
    const ctx=c.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,c.width,c.height);
    for(let i=0;i<chosen.length;i++){const im=await picture(chosen[i].blob), s=Math.min(576/im.width,576/im.height);ctx.drawImage(im,(i%cols)*600+(600-im.width*s)/2,Math.floor(i/cols)*600+(600-im.height*s)/2,im.width*s,im.height*s);im.close();}
    const blob=await new Promise(r=>c.toBlob(r,'image/png'));await add(blob,'Anh-ghep.png',`${chosen.length} ảnh`);report('Đã thêm ảnh ghép vào khay.');
  }
  function render() {
    if(!list) return;
    launcher.textContent=`Khay làm việc · ${items.length}`;list.replaceChildren();
    thumbURLs.forEach(url=>URL.revokeObjectURL(url));thumbURLs=[];
    items.forEach((item,index)=>{
      const li=el('li',null,'mm-shelf-item'), check=el('input');check.type='checkbox';check.checked=selected.has(item.id);check.setAttribute('aria-label','Chọn '+item.name);
      check.onchange=()=>{if(check.checked) selected.add(item.id);else selected.delete(item.id);render();};
      const body=el('div');
      if(item.type==='image') {const thumb=el('img');thumb.src=URL.createObjectURL(item.blob);thumbURLs.push(thumb.src);thumb.alt='';thumb.loading='lazy';thumb.className='mm-shelf-thumb';body.append(thumb);}
      body.append(el('strong',`${index+1}. ${item.name}`),el('small',`${(item.blob.size/1048576).toFixed(2)} MB · ${item.source}`));
      const tools=el('div',null,'mm-row-tools');
      tools.append(button(item.type==='file'?'Tải file':'Xem / sửa',()=>task(()=>preview(item))),button('Tải',()=>download(item.blob,item.name)),button('↑',()=>task(()=>store(rows=>R.move(rows,item.id,-1)))),button('↓',()=>task(()=>store(rows=>R.move(rows,item.id,1)))),button('Bỏ khỏi khay',()=>task(async()=>{await store(rows=>rows.filter(x=>x.id!==item.id));report('Đã bỏ bản sao khỏi khay. File gốc không thay đổi.');})));
      tools.children[2].setAttribute('aria-label','Đưa lên: '+item.name);tools.children[3].setAttribute('aria-label','Đưa xuống: '+item.name);
      body.append(tools);li.append(check,body);list.append(li);
    });
    panel.querySelector('.mm-shelf-count').textContent=`Đã chọn ${selected.size}/${items.length} · Gộp theo thứ tự trong khay`;
    panel.querySelectorAll('button').forEach(b=>{b.disabled=busy;});
    document.querySelectorAll('.mm-file-dialog .mm-primary').forEach(b=>{b.disabled=busy;});
  }
  async function open() { await auth();panel.hidden=false;launcher.setAttribute('aria-expanded','true');await store(); }
  function init() {
    if(!R) return;
    launcher=button('Khay làm việc',()=>{if(panel.hidden) open().catch(e=>report(e.message));else{panel.hidden=true;launcher.setAttribute('aria-expanded','false');}},'mm-shelf-launch');launcher.hidden=true;launcher.setAttribute('aria-expanded','false');launcher.setAttribute('aria-controls','mm-file-shelf');
    panel=el('section',null,'mm-shelf');panel.id='mm-file-shelf';panel.hidden=true;panel.setAttribute('aria-label','Khay làm việc');
    const h=el('header');h.append(el('h2','Khay làm việc'),button('Thu gọn',()=>{panel.hidden=true;launcher.setAttribute('aria-expanded','false');launcher.focus();}));
    const input=el('input');input.type='file';input.multiple=true;input.hidden=true;input.onchange=()=>{addFiles([...input.files]).catch(e=>report(e.message));input.value='';};
    const drop=el('div',null,'mm-shelf-drop');drop.append(button('Thêm file từ máy',()=>input.click()),el('p','Hoặc kéo ảnh, PDF và tài liệu vào đây.'));
    drop.ondragover=e=>{e.preventDefault();drop.classList.add('drag');};drop.ondragleave=()=>drop.classList.remove('drag');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('drag');addFiles([...e.dataTransfer.files]).catch(err=>report(err.message));};
    const actions=el('div',null,'mm-shelf-actions');actions.append(button('Chọn tất cả',()=>{selected=new Set(items.map(x=>x.id));render();}),button('Bỏ chọn',()=>{selected.clear();render();}),button('Gộp PDF',()=>task(mergePDF),'mm-primary'),button('Ghép ảnh',()=>task(collage)));
    list=el('ol',null,'mm-shelf-list');status=el('div',null,'mm-shelf-status');status.setAttribute('role','status');
    panel.append(h,el('p','Bản sao lưu trên trình duyệt này, dùng chung giữa các màn hình MinMin. File gốc được giữ nguyên. Tối đa 40 file / 100 MB.'),drop,input,el('p','', 'mm-shelf-count'),list,actions,status);
    panel.onkeydown=e=>{if(e.key==='Escape'){panel.hidden=true;launcher.setAttribute('aria-expanded','false');launcher.focus();}};
    document.body.append(launcher,panel);
    if(channel) channel.onmessage=()=>{if(!panel.hidden)store().catch(()=>{});};
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)auth().catch(()=>{});});
    auth().then(()=>store()).catch(()=>{});
    // Deliberate opt-in buttons in inbox and invoices; never intercept normal downloads.
    document.addEventListener('click',e=>{const b=e.target.closest('[data-shelf-url]');if(!b)return;addURL(b.dataset.shelfUrl,b.dataset.shelfName,b.dataset.shelfSource).catch(err=>report(err.message));});
  }
  window.MinMinShelf={open,addFiles,addURL};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
