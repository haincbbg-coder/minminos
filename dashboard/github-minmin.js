/* MinMin adapter for the GitHub-in-chat module. Keeps the existing attachment controls. */
(function () {
  'use strict';
  var items = {}, overlay = null, content = null, lastSid = '', lastBrain = '';
  function close() { if (overlay) { overlay.remove(); overlay = null; content = null; } }
  function openItem(id) {
    var it = items[id]; if (!it) return;
    close(); overlay = document.createElement('div'); overlay.className = 'mp-overlay open gh-menu-overlay';
    var box = document.createElement('div'); box.className = 'mp-box gh-menu-box'; box.setAttribute('role','dialog'); box.setAttribute('aria-modal','true');
    var dismiss = document.createElement('button'); dismiss.className = 's-btn-ghost'; dismiss.type = 'button'; dismiss.textContent = '×'; dismiss.setAttribute('aria-label', window.t('common.close')); dismiss.onclick=close;
    content = document.createElement('div'); content.className='gh-menu-content';
    box.append(dismiss,content); overlay.append(box); document.body.append(overlay);
    overlay.onclick = function(e) { if (e.target===overlay) close(); };
    it.panel(content,{close:close,back:function(){openItem(id);}});
    dismiss.focus();
  }
  window.JavisComposerMenu = {register:function(it){items[it.id]=it;},openItem:openItem,close:close};
  window.JavisConnModal = {
    head:function(title){return '<div class="mp-head"><div class="mp-title">'+title+'</div><button type="button" class="mp-x" data-act="close">×</button></div>';},
    close:close,
    open:function(html){
      close();overlay=document.createElement('div');overlay.className='mp-overlay open gh-menu-overlay';
      var box=document.createElement('div');box.className='mp-box gh-menu-box';box.setAttribute('role','dialog');box.setAttribute('aria-modal','true');box.innerHTML=html;overlay.append(box);document.body.append(overlay);
      overlay.onclick=function(e){if(e.target===overlay || e.target.closest('[data-act="close"]'))close();};
      return overlay;
    }
  };
  function init() {
    var attach=document.getElementById('attachBtn');
    if (attach) {
      var b=document.createElement('button'); b.type='button'; b.className='attach-btn gh-compose-btn'; b.textContent='GitHub'; b.setAttribute('aria-label','GitHub repo'); b.onclick=function(){openItem('github');}; attach.after(b);
      var chips=document.createElement('div'); chips.id='cpChips'; chips.className='gh-minmin-chips'; document.getElementById('hudVoice').before(chips);
    }
    document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});
    setInterval(function(){
      if(document.hidden || !window.JavisGithubRepos) return;
      var current=(window.JavisSessions && window.JavisSessions.current()) || '';
      var brain=(window.JavisSessions && window.JavisSessions.brain()) || '';
      if(current!==lastSid || brain!==lastBrain){lastSid=current;lastBrain=brain;window.JavisGithubRepos.refresh();}
    },3000);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
