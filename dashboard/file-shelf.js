/* Shared, device-local working copies. No automatic sending, uploading, or original-file writes. */
(function () {
  'use strict';
  const R = window.MinMinFileRules;
  let db, owner = '', items = [], selected = new Set(), panel, launcher, list, status, busy = false;
  let pdfLoading;
  let wheel, wheelCenter, wheelHint, fileInput, audioContext, soundButton;
  let soundOn = true;
  try { soundOn = localStorage.getItem('minmin-file-sound') !== 'off'; } catch (_) {}
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
      if (wheel) wheel.hidden = true;
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
        count+=await R.appendPDF(PDFDocument,output,await item.blob.arrayBuffer(),item.name,200-count);
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
    launcher.setAttribute('aria-label',`Mở vòng công cụ · ${items.length} file`);
    launcher.querySelector('.mm-orbit-badge').textContent=items.length;
    if(wheelCenter) wheelCenter.querySelector('small').textContent=`${selected.size} chọn / ${items.length} file`;
    if(wheel) wheel.querySelectorAll('.mm-orbit-sector').forEach(b=>{b.disabled=busy;});
    list.replaceChildren();
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
  async function open() { await auth(); closeWheel(false); panel.hidden=false; await store(); }
  // Short tactile noise, synthesized locally; no media downloads or autoplay.
  function tick() {
    if(!soundOn) return;
    try {
      const AC=window.AudioContext||window.webkitAudioContext;
      if(!AC)return;
      audioContext ||= new AC();
      const play=()=>{
        const buffer=audioContext.createBuffer(1,Math.ceil(audioContext.sampleRate*.018),audioContext.sampleRate);
        const data=buffer.getChannelData(0);
        for(let i=0;i<data.length;i++) data[i]=(Math.random()*2-1)*Math.exp(-i/(data.length*.13))*.18;
        const source=audioContext.createBufferSource();source.buffer=buffer;source.connect(audioContext.destination);source.start();
      };
      if(audioContext.state==='suspended')audioContext.resume().then(play).catch(()=>{});else play();
    }catch(_){} // Sound is optional and must never block a file action.
  }
  function closeWheel(focus=true) {
    if(wheel)wheel.hidden=true;
    launcher.setAttribute('aria-expanded','false');
    if(focus)launcher.focus();
  }
  function icon(name) {
    const paths={add:'M12 4v16M4 12h16',files:'M3 7h7l2-3h9v16H3z',edit:'M4 20l4-1L20 7l-3-3L5 16zM14 7l3 3',collage:'M3 3h18v18H3zM12 3v18M3 12h18',pdf:'M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h7',download:'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',close:'M6 6l12 12M18 6 6 18'};
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');
    const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',paths[name]);svg.append(path);return svg;
  }
  function wedge(index) {
    const points=[],angle=index*60-90;
    for(let a=angle-28;a<=angle+28;a+=2)points.push([50+48*Math.cos(a*Math.PI/180),50+48*Math.sin(a*Math.PI/180)]);
    for(let a=angle+28;a>=angle-28;a-=2)points.push([50+20*Math.cos(a*Math.PI/180),50+20*Math.sin(a*Math.PI/180)]);
    return 'polygon('+points.map(p=>p.map(v=>v.toFixed(3)+'%').join(' ')).join(',')+')';
  }
  async function moduleAction(kind) {
    const chosen=items.filter(x=>selected.has(x.id));
    if(kind==='add'){fileInput.click();return;}
    await open();
    if(kind==='files'){report('Chọn file trong khay, rồi mở vòng công cụ để xử lý.');return;}
    if(kind==='edit'){
      if(chosen.length===1&&chosen[0].type==='image')return task(()=>preview(chosen[0]));
      report('Chọn một ảnh rồi bấm Sửa ảnh, hoặc bấm Xem / sửa ngay trên ảnh.');return;
    }
    if(kind==='collage')return task(collage);
    if(kind==='pdf')return task(mergePDF);
    if(kind==='download'){
      if(chosen.length!==1){report('Chọn một file để tải. Với nhiều ảnh/PDF, chọn Gộp PDF để tải cùng một file.');return;}
      download(chosen[0].blob,chosen[0].name);report('Đã yêu cầu tải '+chosen[0].name);
    }
  }
  function initWheel() {
    launcher=button('',()=>{
      tick();
      if(!wheel.hidden){closeWheel();return;}
      auth().then(()=>store()).then(()=>{
        panel.hidden=true;wheel.hidden=false;launcher.setAttribute('aria-expanded','true');wheelCenter.focus();
      }).catch(e=>report(e.message));
    },'mm-shelf-launch');
    launcher.append(icon('collage'),el('span','0','mm-orbit-badge'));
    launcher.title='Vòng công cụ';launcher.hidden=true;launcher.setAttribute('aria-expanded','false');launcher.setAttribute('aria-controls','mm-file-orbit');
    wheel=el('section',null,'mm-orbit');wheel.id='mm-file-orbit';wheel.hidden=true;wheel.setAttribute('aria-label','Vòng công cụ');
    const head=el('div',null,'mm-orbit-head');head.append(el('span','CÔNG CỤ CỦA BẠN'));
    soundButton=button('',()=>{soundOn=!soundOn;try{localStorage.setItem('minmin-file-sound',soundOn?'on':'off');}catch(_){}updateSound();tick();},'mm-orbit-sound');
    function updateSound(){soundButton.textContent=soundOn?'Âm thanh: bật':'Âm thanh: tắt';soundButton.setAttribute('aria-pressed',String(soundOn));}
    updateSound();head.append(soundButton);
    const disc=el('div',null,'mm-orbit-disc');
    const modules=[['add','Thêm file','Thả file vào tâm hoặc chọn từ máy'],['files','Khay file','Xem và chọn các file đã lưu'],['edit','Sửa ảnh','Cắt · xoay · PNG / JPG / WebP'],['collage','Ghép ảnh','Ghép từ 2 đến 9 ảnh đã chọn'],['pdf','Gộp PDF','Gộp ảnh và PDF theo thứ tự khay'],['download','Tải file','Tải file đang chọn về máy']];
    const buttons=[];
    modules.forEach(([kind,label,hint],i)=>{
      const b=button('',()=>{tick();moduleAction(kind).catch(e=>report(e.message));},'mm-orbit-sector');
      b.style.clipPath=wedge(i);b.style.setProperty('--delay',i*24+'ms');b.setAttribute('aria-label',label);b.title=hint;
      const content=el('span',null,'mm-orbit-label'),a=(i*60-90)*Math.PI/180;
      content.style.left=(50+34*Math.cos(a))+'%';content.style.top=(50+34*Math.sin(a))+'%';content.append(icon(kind),el('span',label));b.append(content);
      b.onpointerenter=b.onfocus=()=>{wheelHint.textContent=hint;};
      buttons.push(b);disc.append(b);
    });
    wheelCenter=button('',()=>{tick();closeWheel();},'mm-orbit-center');wheelCenter.setAttribute('aria-label','Thu vòng công cụ');
    wheelCenter.append(icon('close'),el('strong','MINMIN'),el('small','0 file'));disc.append(wheelCenter);
    wheelHint=el('p','Chọn công cụ · thả file vào tâm','mm-orbit-hint');wheelHint.setAttribute('aria-live','polite');
    disc.ondragover=e=>{e.preventDefault();disc.classList.add('drag');wheelHint.textContent='Thả để thêm vào khay';};
    disc.ondragleave=e=>{if(!disc.contains(e.relatedTarget))disc.classList.remove('drag');};
    disc.ondrop=e=>{e.preventDefault();disc.classList.remove('drag');tick();addFiles([...e.dataTransfer.files]).catch(err=>report(err.message));};
    wheel.append(head,disc,wheelHint);
    wheel.onkeydown=e=>{
      if(e.key==='Escape'){e.preventDefault();closeWheel();}
      if(['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(e.key)){
        e.preventDefault();let i=buttons.indexOf(document.activeElement);const step=['ArrowLeft','ArrowUp'].includes(e.key)?-1:1;
        i=e.key==='Home'?0:e.key==='End'?5:(i+step+6)%6;buttons[i].focus();
      }
    };
    document.addEventListener('pointerdown',e=>{if(!wheel.hidden&&!wheel.contains(e.target)&&!launcher.contains(e.target))closeWheel(false);});
  }
  function init() {
    if(!R) return;
    initWheel();
    panel=el('section',null,'mm-shelf');panel.id='mm-file-shelf';panel.hidden=true;panel.setAttribute('aria-label','Khay làm việc');
    const h=el('header');h.append(el('h2','Khay làm việc'),button('Thu gọn',()=>{panel.hidden=true;launcher.setAttribute('aria-expanded','false');launcher.focus();}));
    const input=fileInput=el('input');input.type='file';input.multiple=true;input.hidden=true;input.onchange=()=>{addFiles([...input.files]).catch(e=>report(e.message));input.value='';};
    const drop=el('div',null,'mm-shelf-drop');drop.append(button('Thêm file từ máy',()=>input.click()),el('p','Hoặc kéo ảnh, PDF và tài liệu vào đây.'));
    drop.ondragover=e=>{e.preventDefault();drop.classList.add('drag');};drop.ondragleave=()=>drop.classList.remove('drag');drop.ondrop=e=>{e.preventDefault();drop.classList.remove('drag');addFiles([...e.dataTransfer.files]).catch(err=>report(err.message));};
    const actions=el('div',null,'mm-shelf-actions');actions.append(button('Chọn tất cả',()=>{selected=new Set(items.map(x=>x.id));render();}),button('Bỏ chọn',()=>{selected.clear();render();}),button('Gộp PDF',()=>task(mergePDF),'mm-primary'),button('Ghép ảnh',()=>task(collage)));
    list=el('ol',null,'mm-shelf-list');status=el('div',null,'mm-shelf-status');status.setAttribute('role','status');
    panel.append(h,el('p','Bản sao lưu trên trình duyệt này, dùng chung giữa các màn hình MinMin. File gốc được giữ nguyên. Tối đa 40 file / 100 MB.'),drop,input,el('p','', 'mm-shelf-count'),list,actions,status);
    panel.onkeydown=e=>{if(e.key==='Escape'){panel.hidden=true;launcher.setAttribute('aria-expanded','false');launcher.focus();}};
    document.body.append(launcher,wheel,panel);
    if(channel) channel.onmessage=()=>{store().catch(()=>{});};
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)auth().catch(()=>{});});
    auth().then(()=>store()).catch(()=>{});
    // Deliberate opt-in buttons in inbox and invoices; never intercept normal downloads.
    document.addEventListener('click',e=>{const b=e.target.closest('[data-shelf-url]');if(!b)return;addURL(b.dataset.shelfUrl,b.dataset.shelfName,b.dataset.shelfSource).catch(err=>report(err.message));});
  }
  window.MinMinShelf={open,addFiles,addURL};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
