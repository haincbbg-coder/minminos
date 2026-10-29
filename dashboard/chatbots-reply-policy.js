/* Read-only bridge to MinMin's existing conversation judge. */
(function () {
  'use strict';
  var CODE_LB = {below_threshold: 'rp.code_below_threshold'};
  function tt(k) { return window.t ? window.t(k) : k; }
  function codeLabel(code) { return CODE_LB[code] ? tt(CODE_LB[code]) : String(code || ''); }
  async function openPanel(bot) {
    var overlay = document.createElement('div'); overlay.className = 'mp-overlay open';
    var box = document.createElement('section'); box.className = 'mp-box'; box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    var head = document.createElement('div'); head.className = 'mp-head';
    var title = document.createElement('strong'); title.textContent = tt('mm.inbox.judge') + ': ' + (bot.name || '');
    var close = document.createElement('button'); close.type = 'button'; close.className = 's-btn-ghost'; close.textContent = tt('common.close');
    var body = document.createElement('div'); body.className = 'mp-body'; body.textContent = tt('common.loading');
    var previous = document.activeElement;
    function dismiss() { overlay.remove(); if (previous && previous.isConnected) previous.focus(); }
    close.onclick = dismiss; overlay.onclick = function (e) { if (e.target === overlay) dismiss(); };
    overlay.onkeydown = function (e) { if (e.key === 'Escape') dismiss(); };
    head.append(title, close); box.append(head, body); overlay.append(box); document.body.append(overlay); close.focus();
    try {
      var res = await fetch('/chatbots/' + encodeURIComponent(bot.id) + '/phan-xu');
      var data = await res.json(); if (!res.ok || data.ok === false) throw new Error(data.error || tt('mm.inbox.load_error'));
      body.textContent = '';
      if (!(data.items || []).length) body.textContent = tt('mm.inbox.no_judgments');
      (data.items || []).forEach(function (r) {
        var row = document.createElement('p'); row.textContent = (r.noi ? tt('mm.inbox.did_reply') : tt('mm.inbox.did_wait')) + ': ' + (r.ly_do || '') + ' (' + (r.chat_id || '') + ')'; body.append(row);
      });
    } catch (e) { body.textContent = e.message; }
  }
  window.JavisReplyPolicy = {codeLabel: codeLabel, openPanel: openPanel};
})();
