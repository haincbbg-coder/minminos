/* Shared, device-local working copies. No automatic sending, uploading, or original-file writes. */
(function () {
  'use strict';
  const R = window.MinMinFileRules;
  let db, owner = '', items = [], selected = new Set(), launcher, busy = false;
  let pdfLoading;
  let wheel, wheelCenter, wheelHint, fileInput, audioContext, soundButton;
  let drawCurrent, disc, footer, heading, previewBox, editorCleanup;
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
  function report(text) { if(wheelHint)wheelHint.textContent=text; }
  function task(fn) {
    // Preserve rapid additions from different inbox messages; never silently drop a click.
    workQueue=workQueue.then(async()=>{
      busy = true; report('Đang xử lý…'); render();
      try { await auth(); await fn(); }
      catch(e) { report(e.message || 'Không xử lý được file.'); }
      finally { busy = false; if(wheelHint && wheelHint.textContent==='Đang xử lý…') report(''); render(); }
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
  async function picture(blob) {
    const img = await createImageBitmap(blob);
    if(img.width * img.height > 24000000) { img.close(); throw Error('Ảnh quá lớn để chỉnh sửa trên trình duyệt (tối đa 24 triệu điểm ảnh).'); }
    return img;
  }
  function clearPreview() {
    if(editorCleanup) { editorCleanup(); editorCleanup=null; }
    if(previewBox) { previewBox.replaceChildren(); previewBox.hidden=true; }
  }
  async function editImage(item) {
    clearPreview();
    const img=await picture(item.blob), canvas=el('canvas');
    editorCleanup=()=>img.close();previewBox.append(canvas);previewBox.hidden=false;
    let ratio=0, width=Math.min(img.width,1920), format='image/png', turns=0, caption='';
    function paint() {
      const sw=turns%2?img.height:img.width,sh=turns%2?img.width:img.height;
      const c=R.crop(sw,sh,ratio),w=width,h=Math.round(w*c.h/c.w);
      if(w*h>16000000)throw Error('Ảnh đầu ra quá lớn. Chọn chiều rộng nhỏ hơn.');
      canvas.width=w;canvas.height=h;const ctx=canvas.getContext('2d');
      if(format==='image/jpeg'){ctx.fillStyle='#fff';ctx.fillRect(0,0,w,h);}
      ctx.save();ctx.scale(w/c.w,h/c.h);ctx.translate(-c.x,-c.y);ctx.translate(sw/2,sh/2);ctx.rotate(turns*Math.PI/2);ctx.drawImage(img,-img.width/2,-img.height/2);ctx.restore();
      if(caption){const fs=Math.max(16,Math.round(w/32));ctx.fillStyle='rgba(0,0,0,.72)';ctx.fillRect(0,h-fs*2.4,w,fs*2.4);ctx.fillStyle='#fff';ctx.font=`${fs}px sans-serif`;ctx.textAlign='center';ctx.fillText(caption,w/2,h-fs*.85,w-24);}
    }
    function safePaint(){try{paint();}catch(e){report(e.message);}}
    function choices(title,rows,set){setView(()=>drawWheel(title,rows.map(([v,label])=>({label,icon:'edit',run:()=>{set(v);safePaint();menu();}})),menu,'Quay lại'));}
    function menu(){
      setView(()=>drawWheel('SỬA ẢNH',[
        {label:'Cắt tỷ lệ',icon:'edit',run:()=>choices('TỶ LỆ CẮT',[[0,'Nguyên ảnh'],[1,'1 : 1'],[.5625,'9 : 16'],[1.77777778,'16 : 9'],[.75,'3 : 4']],v=>ratio=v)},
        {label:'Xoay 90°',icon:'edit',run:()=>{turns=(turns+1)%4;safePaint();}},
        {label:format.split('/')[1].toUpperCase(),icon:'files',run:()=>choices('ĐỊNH DẠNG', [['image/png','PNG'],['image/jpeg','JPG'],['image/webp','WebP']],v=>format=v)},
        {label:width+' px',icon:'collage',run:()=>choices('CHIỀU RỘNG',[[640,'640 px'],[1080,'1080 px'],[1920,'1920 px'],[2560,'2560 px'],[4096,'4096 px']],v=>width=v)},
        {label:'Chú thích',icon:'edit',run:()=>{menu();const input=el('input');input.placeholder='Chú thích dưới ảnh';input.setAttribute('aria-label','Chú thích dưới ảnh');input.maxLength=100;input.value=caption;input.oninput=()=>{caption=input.value;safePaint();};footer.append(input);input.focus();}},
        {label:'Lưu bản sao',icon:'download',run:()=>task(async()=>{paint();const blob=await new Promise(r=>canvas.toBlob(r,format,.9));if(!blob)throw Error('Không xuất được ảnh.');await add(blob,R.nameCopy(item.name,blob.type.split('/')[1].replace('jpeg','jpg')),item.name);clearPreview();showFiles();report('Đã lưu bản sao. Chọn ảnh rồi bấm Dùng file đã chọn.');})}
      ],()=>{clearPreview();showTools();},'Quay lại'));
      report(item.name+' · bản gốc được giữ nguyên');
    }
    paint();menu();
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
    await add(blob,'Ho-so-gop.pdf',`${chosen.length} file · ${count} trang`);report(`Đã tạo PDF ${count} trang. Chọn file rồi mở Tải / xem để xem hoặc in.`);
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
    if(!launcher)return;
    launcher.setAttribute('aria-label',`Mở vòng công cụ · ${items.length} file`);
    launcher.querySelector('.mm-orbit-badge').textContent=items.length;
    if(drawCurrent && !wheel.hidden)drawCurrent();
  }
  async function open() { await auth(); await store(); clearPreview();showFiles(); }
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
    clearPreview();
    launcher.setAttribute('aria-expanded','false');
    if(focus)launcher.focus();
  }
  function icon(name) {
    const paths={add:'M12 4v16M4 12h16',files:'M3 7h7l2-3h9v16H3z',edit:'M4 20l4-1L20 7l-3-3L5 16zM14 7l3 3',collage:'M3 3h18v18H3zM12 3v18M3 12h18',pdf:'M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h7',download:'M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4',close:'M6 6l12 12M18 6 6 18'};
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');
    const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',paths[name]);svg.append(path);return svg;
  }
  function wedge(index,count=6) {
    const points=[],angle=index*360/count-90,half=180/count-2;
    for(let a=angle-half;a<=angle+half;a+=2)points.push([50+48*Math.cos(a*Math.PI/180),50+48*Math.sin(a*Math.PI/180)]);
    for(let a=angle+half;a>=angle-half;a-=2)points.push([50+20*Math.cos(a*Math.PI/180),50+20*Math.sin(a*Math.PI/180)]);
    return 'polygon('+points.map(p=>p.map(v=>v.toFixed(3)+'%').join(' ')).join(',')+')';
  }
  function setView(draw) {
    drawCurrent=draw;wheel.hidden=false;launcher.setAttribute('aria-expanded','true');draw();wheelCenter.focus();
  }
  function drawWheel(title,entries,back,centerText='Quay lại') {
    const focused=disc.contains(document.activeElement)?document.activeElement.getAttribute('aria-label'):null;
    thumbURLs.forEach(url=>URL.revokeObjectURL(url));thumbURLs=[];
    heading.textContent=title;disc.replaceChildren();footer.replaceChildren();
    entries.forEach((entry,i)=>{
      const b=button('',()=>{tick();Promise.resolve().then(entry.run).catch(e=>report(e.message));},'mm-orbit-sector');
      b.style.clipPath=wedge(i,entries.length);b.style.setProperty('--delay',i*24+'ms');b.setAttribute('aria-label',entry.name||entry.label);b.title=entry.hint||entry.name||entry.label;b.disabled=busy;
      if(entry.checked!==undefined)b.setAttribute('aria-pressed',String(entry.checked));
      const content=el('span',null,'mm-orbit-label'),a=(i*360/entries.length-90)*Math.PI/180;
      content.style.left=(50+34*Math.cos(a))+'%';content.style.top=(50+34*Math.sin(a))+'%';
      if(entry.item?.type==='image'){const im=el('img');im.src=URL.createObjectURL(entry.item.blob);thumbURLs.push(im.src);im.alt='';content.append(im);}else content.append(icon(entry.icon||'files'));
      content.append(el('span',entry.label));b.append(content);b.onpointerenter=b.onfocus=()=>{wheelHint.textContent=entry.hint||entry.name||entry.label;};disc.append(b);
    });
    wheelCenter=button('',()=>{if(busy)return;tick();back();},'mm-orbit-center');wheelCenter.setAttribute('aria-label',centerText);
    wheelCenter.append(icon('close'),el('strong',centerText),el('small',`${selected.size} chọn / ${items.length} file`));disc.append(wheelCenter);
    if(focused)([...disc.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')===focused)||wheelCenter).focus();
  }
  function showTools(){
    clearPreview();setView(()=>drawWheel('CÔNG CỤ CỦA BẠN',[
      {label:'Thêm file',icon:'add',run:()=>fileInput.click()},
      {label:'Chọn file',icon:'files',run:()=>showFiles()},
      {label:'Sửa ảnh',icon:'edit',run:()=>moduleAction('edit')},
      {label:'Ghép ảnh',icon:'collage',run:()=>moduleAction('collage')},
      {label:'Gộp PDF',icon:'pdf',run:()=>moduleAction('pdf')},
      {label:'Tải / xem',icon:'download',run:()=>moduleAction('download')}
    ],()=>closeWheel(),'Thu vòng'));
    report('Chọn công cụ · thả file vào vòng');
  }
  function showFiles(pending='',page=0){
    clearPreview();
    setView(()=>{
      const rows=items.filter(x=>!['edit','collage'].includes(pending)||x.type==='image');
      const pages=Math.max(1,Math.ceil(rows.length/6));page=Math.max(0,Math.min(page,pages-1));
      drawWheel('CHỌN FILE · '+(page+1)+' / '+pages,rows.slice(page*6,page*6+6).map(item=>({
        label:item.name,name:'Chọn '+item.name,item,checked:selected.has(item.id),hint:item.name+' · '+item.source,
        run:()=>{if(selected.has(item.id))selected.delete(item.id);else{if(['edit','download'].includes(pending))selected.clear();selected.add(item.id);}drawCurrent();}
      })),showTools,'Công cụ');
      footer.append(button('‹',()=>showFiles(pending,page-1)),button('Dùng file đã chọn',()=>{tick();if(pending)moduleAction(pending,true);else showTools();},'mm-primary'),button('›',()=>showFiles(pending,page+1)));
      footer.children[0].disabled=page===0||busy;footer.children[2].disabled=page===pages-1||busy;footer.children[1].disabled=busy;
      footer.children[0].setAttribute('aria-label','Trang file trước');footer.children[2].setAttribute('aria-label','Trang file sau');
      if(!rows.length){footer.append(button('Thêm file',()=>fileInput.click()));report('Chưa có file phù hợp. Thả file vào vòng hoặc bấm Thêm file.');}
    });
    if(items.length)report(pending?'Chọn file rồi bấm Dùng file đã chọn.':'Bấm từng múi để chọn hoặc bỏ chọn file.');
  }
  async function moduleAction(kind,confirmed=false){
    const chosen=items.filter(x=>selected.has(x.id));
    const valid=kind==='edit'?chosen.length===1&&chosen[0].type==='image':kind==='download'?chosen.length===1:kind==='collage'?chosen.length>=2&&chosen.length<=9&&chosen.every(x=>x.type==='image'):chosen.length&&chosen.every(x=>['image','pdf'].includes(x.type));
    if(!valid){if(!confirmed)showFiles(kind);report(kind==='edit'?'Chọn đúng một ảnh.':kind==='download'?'Chọn đúng một file.':kind==='collage'?'Chọn từ 2 đến 9 ảnh.':'Chọn ảnh và PDF để gộp.');return;}
    if(kind==='edit')return task(()=>editImage(chosen[0]));
    if(kind==='download')return showFileActions(chosen[0]);
    return task(async()=>{if(kind==='collage')await collage();else await mergePDF();const message=wheelHint.textContent;showFiles();report(message);});
  }
  function showFileActions(item){
    clearPreview();setView(()=>drawWheel(item.name,[
      {label:'Tải về',icon:'download',run:()=>download(item.blob,item.name)},
      {label:item.type==='image'?'Sửa ảnh':'Xem file',icon:'edit',run:()=>{if(item.type==='image')return task(()=>editImage(item));if(item.type==='pdf'){const url=URL.createObjectURL(item.blob);thumbURLs.push(url);const a=el('a');a.href=url;a.target='_blank';a.rel='noopener';a.click();}else download(item.blob,item.name);}},
      {label:'Đưa lên',icon:'files',run:()=>task(()=>store(rows=>R.move(rows,item.id,-1)))},
      {label:'Đưa xuống',icon:'files',run:()=>task(()=>store(rows=>R.move(rows,item.id,1)))},
      {label:'Bỏ khỏi khay',icon:'close',run:()=>task(async()=>{await store(rows=>rows.filter(x=>x.id!==item.id));showFiles();report('Đã bỏ bản sao khỏi khay; file gốc giữ nguyên.');})}
    ],showTools,'Công cụ'));
  }
  function init() {
    if(!R)return;
    launcher=button('',()=>{if(busy)return;tick();if(!wheel.hidden){closeWheel();return;}auth().then(()=>store()).then(showTools).catch(e=>report(e.message));},'mm-shelf-launch');
    launcher.append(icon('collage'),el('span','0','mm-orbit-badge'));launcher.title='Vòng công cụ';launcher.hidden=true;launcher.setAttribute('aria-expanded','false');launcher.setAttribute('aria-controls','mm-file-orbit');
    wheel=el('section',null,'mm-orbit');wheel.id='mm-file-orbit';wheel.hidden=true;wheel.setAttribute('aria-label','Vòng công cụ');
    const head=el('div',null,'mm-orbit-head');heading=el('span','CÔNG CỤ CỦA BẠN');
    soundButton=button('',()=>{soundOn=!soundOn;try{localStorage.setItem('minmin-file-sound',soundOn?'on':'off');}catch(_){}updateSound();tick();},'mm-orbit-sound');
    function updateSound(){soundButton.textContent=soundOn?'Âm thanh: bật':'Âm thanh: tắt';soundButton.setAttribute('aria-pressed',String(soundOn));}
    updateSound();head.append(heading,soundButton);disc=el('div',null,'mm-orbit-disc');footer=el('div',null,'mm-orbit-footer');
    previewBox=el('div',null,'mm-orbit-preview');previewBox.hidden=true;previewBox.setAttribute('aria-label','Ảnh đang sửa');
    wheelHint=el('p','Chọn công cụ','mm-orbit-hint');wheelHint.setAttribute('role','status');
    fileInput=el('input');fileInput.type='file';fileInput.multiple=true;fileInput.hidden=true;fileInput.onchange=()=>{addFiles([...fileInput.files]).catch(e=>report(e.message));fileInput.value='';};
    disc.ondragover=e=>{e.preventDefault();disc.classList.add('drag');};disc.ondragleave=e=>{if(!disc.contains(e.relatedTarget))disc.classList.remove('drag');};disc.ondrop=e=>{e.preventDefault();disc.classList.remove('drag');tick();addFiles([...e.dataTransfer.files]).catch(err=>report(err.message));};
    wheel.append(head,previewBox,disc,footer,wheelHint,fileInput);
    wheel.onkeydown=e=>{
      if(e.target.tagName==='INPUT')return;
      if(e.key==='Escape'&&!busy){e.preventDefault();closeWheel();}
      if(['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(e.key)){
        const buttons=[...disc.querySelectorAll('.mm-orbit-sector')];if(!buttons.length)return;
        e.preventDefault();let i=buttons.indexOf(document.activeElement),n=buttons.length,step=['ArrowLeft','ArrowUp'].includes(e.key)?-1:1;
        i=e.key==='Home'?0:e.key==='End'?n-1:(i+step+n)%n;buttons[i].focus();
      }
    };
    document.addEventListener('pointerdown',e=>{if(!wheel.hidden&&!wheel.contains(e.target)&&!launcher.contains(e.target)&&!busy)closeWheel(false);});
    document.body.append(launcher,wheel);
    if(channel)channel.onmessage=()=>store().catch(()=>{});
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)auth().catch(()=>{});});
    auth().then(()=>store()).catch(()=>{});
    document.addEventListener('click',e=>{const b=e.target.closest('[data-shelf-url]');if(b)addURL(b.dataset.shelfUrl,b.dataset.shelfName,b.dataset.shelfSource).catch(err=>report(err.message));});
  }
  window.MinMinShelf={open,addFiles,addURL};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
