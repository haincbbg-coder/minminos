/* Công cụ người trực, dùng chung Hộp thư hiện tại. Không có bộ gửi tin thứ hai. */
(function () {
  'use strict';
  function esc(x) { return String(x == null ? '' : x).replace(/[&<>"']/g, function (c) {
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  }); }
  async function api(path, data) {
    var r = await fetch('/conversation-ops/' + path, data === undefined ? {} : {
      method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)
    });
    var d = await r.json();
    if (!r.ok || d.ok === false) throw new Error(d.error || 'Không tải được dữ liệu. Thử lại.');
    return d;
  }
  function duration(s) {
    if (s == null) return 'Chưa có mẫu';
    return s < 60 ? s + ' giây' : Math.round(s / 60) + ' phút';
  }
  function modal(title) {
    var box = document.createElement('div'); box.className = 'ht-modal co-modal';
    box.innerHTML = '<section class="co-dialog" role="dialog" aria-modal="true" aria-label="' + esc(title) + '">' +
      '<header><h3>' + esc(title) + '</h3><button type="button" class="s-btn-ghost co-close">Đóng</button></header>' +
      '<div class="co-content">Đang tải…</div></section>';
    var previous = document.activeElement;
    function close() { box.remove(); if (previous && previous.isConnected) previous.focus(); }
    box.querySelector('.co-close').onclick = close;
    box.onclick = function (e) { if (e.target === box) close(); };
    box.onkeydown = function (e) {
      if (e.key === 'Escape') close();
      if (e.key === 'Tab') {
        var focus = box.querySelectorAll('button:not(:disabled),input,textarea,select,a[href]');
        var first = focus[0], last = focus[focus.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.body.appendChild(box); box.querySelector('.co-close').focus();
    return {box: box, body: box.querySelector('.co-content'), close: close};
  }
  async function profile(cid) {
    var m = modal('Hồ sơ khách & người phụ trách');
    try {
      var c = (await api('profile/' + cid)).profile;
      if (!m.box.isConnected) return;
      m.body.innerHTML = '<p><strong>' + esc(c.customer_name || c.title) + '</strong> · ' + esc(c.account_name) + '</p>' +
        '<label>Người phụ trách<input class="co-owner" maxlength="120" value="' + esc(c.owner) + '"></label>' +
        '<p class="co-muted">Tên để phối hợp công việc. MinMin đang dùng phiên quản trị chung; nhãn này không giới hạn quyền truy cập.</p>' +
        (c.chat_type === 'group' ? '<p class="co-muted">Thẻ và ghi chú thuộc hồ sơ người gửi được liên kết, không đại diện mọi thành viên nhóm.</p>' : '') +
        '<label>Thẻ, ngăn cách bằng dấu phẩy<input class="co-tags" value="' + esc((c.customer_tags || []).join(', ')) + '"></label>' +
        '<label>Ghi chú<textarea class="co-note" rows="4" maxlength="4000">' + esc(c.customer_note || '') + '</textarea></label>' +
        '<div class="co-actions"><button class="s-btn co-save">Lưu hồ sơ</button>' +
        '<button class="s-btn-ghost co-summary"' + (c.bot_id ? '' : ' disabled') + '>AI tóm tắt</button></div>' +
        '<p class="co-status" role="status"></p><div class="co-summary-text"></div>' +
        (c.bot_id ? '<p class="co-muted">AI đọc trích đoạn cuối tối đa 60 tin / 12.000 ký tự. Kiểm tra lại trước khi sử dụng.</p>' : '<p class="co-muted">Gắn Chatbot cho tài khoản để dùng AI tóm tắt và gợi ý trả lời.</p>');
      m.body.querySelector('.co-save').onclick = async function () {
        var b = this; b.disabled = true;
        try {
          var d = await api('profile/' + cid, {revision: c.revision, owner: m.body.querySelector('.co-owner').value,
            tags: m.body.querySelector('.co-tags').value.split(',').map(function (x) { return x.trim(); }).filter(Boolean),
            note: m.body.querySelector('.co-note').value});
          c = d.profile; m.body.querySelector('.co-status').textContent = 'Đã lưu hồ sơ.';
        } catch (e) { m.body.querySelector('.co-status').textContent = e.message; }
        b.disabled = false;
      };
      m.body.querySelector('.co-summary').onclick = async function () {
        var b = this; b.disabled = true; m.body.querySelector('.co-status').textContent = 'AI đang đọc hội thoại…';
        try {
          var r = await fetch('/conversation-ops/summary/' + cid, {method:'POST'}), d = await r.json();
          if (!r.ok) throw new Error(d.error || 'Không tóm tắt được.');
          m.body.querySelector('.co-summary-text').textContent = d.text;
          m.body.querySelector('.co-status').textContent = 'Đã tạo bản tóm tắt để tham khảo.';
        } catch (e) { m.body.querySelector('.co-status').textContent = e.message; }
        b.disabled = false;
      };
    } catch (e) { m.body.textContent = e.message; }
  }
  async function chooseTemplate(textarea, customer) {
    var m = modal('Chèn mẫu trả lời');
    try {
      var items = (await api('templates')).items;
      if (!m.box.isConnected) return;
      m.body.innerHTML = items.length ? items.map(function (x, i) {
        return '<button class="co-template" data-i="' + i + '"><strong>/' + esc(x.code) + '</strong><span>' + esc(x.text) + '</span></button>';
      }).join('') : '<p>Chưa có mẫu. Mở tab Vận hành → Mẫu trả lời để tạo mẫu đầu tiên.</p>';
      m.body.querySelectorAll('.co-template').forEach(function (b) { b.onclick = function () {
        textarea.value = expand(items[Number(b.dataset.i)].text, customer); m.close(); textarea.focus();
      }; });
    } catch (e) { m.body.textContent = e.message; }
  }
  function expand(text, customer) { return text.split('{tenKhach}').join(customer || 'anh/chị'); }
  async function slash(textarea, customer) {
    var match = textarea.value.trim().match(/^\/([a-zA-Z0-9_-]+)$/);
    if (!match) return false;
    var items = (await api('templates')).items;
    var hit = items.filter(function (x) { return x.code === match[1]; })[0];
    if (!hit) throw new Error('Chưa có mẫu /' + match[1] + '. Chọn Mẫu trả lời hoặc sửa nội dung trước khi gửi.');
    textarea.value = expand(hit.text, customer); textarea.focus(); return true;
  }
  function attach(box, c) {
    var head = box.querySelector('.ht-head');
    if (head) {
      var p = document.createElement('button'); p.type = 'button'; p.className = 's-btn-ghost';
      p.textContent = 'Hồ sơ'; p.onclick = function () { profile(c.id); }; head.appendChild(p);
    }
    var compose = box.querySelector('.ht-compose');
    if (compose) {
      var b = document.createElement('button'); b.type = 'button'; b.className = 's-btn-ghost co-pick';
      b.textContent = 'Mẫu trả lời · /lệnh'; b.onclick = function () {
        chooseTemplate(compose.querySelector('textarea'), c.customer_name || c.title);
      }; compose.prepend(b);
    }
  }
  async function render(host) {
    host.innerHTML = '<div class="co-work"><div class="co-heading"><div><h2>Vận hành chăm khách</h2>' +
      '<p>Thời gian chờ, hiệu suất trả lời và kịch bản dùng chung.</p></div>' +
      '<button class="s-btn-ghost co-refresh">Làm mới</button></div>' +
      '<div class="co-toolbar"><label>Kênh<select class="co-channel"><option value="zalo_personal">Zalo cá nhân</option><option value="zalo">Zalo Bot</option><option value="">Tất cả kênh</option></select></label>' +
      '<label>Khoảng thời gian<select class="co-days"><option value="1">24 giờ qua</option><option value="7" selected>7 ngày qua</option><option value="30">30 ngày qua</option></select></label>' +
      '<label>Mục tiêu phản hồi<select class="co-sla"><option value="60">1 phút</option><option value="300" selected>5 phút</option><option value="900">15 phút</option><option value="3600">1 giờ</option></select></label></div>' +
      '<p class="co-updated" role="status"></p><div class="co-report">Đang tải…</div>' +
      '<details class="co-section"><summary>Mẫu trả lời dùng chung</summary><div class="co-template-list"></div>' +
      '<form class="co-template-form"><label>Mã /lệnh<input name="code" required maxlength="40" placeholder="chao"></label>' +
      '<label>Nội dung<textarea name="text" required maxlength="8000" rows="3" placeholder="Chào {tenKhach}, em có thể hỗ trợ gì cho mình ạ?"></textarea></label>' +
      '<button class="s-btn">Lưu mẫu</button><p class="co-template-status" role="status"></p></form></details>' +
      '<details class="co-section"><summary>Nhật ký vận hành</summary><p class="co-muted">Thao tác từ bản này, dưới phiên quản trị chung. Nhật ký không có nút sửa/xóa; quản trị máy chủ vẫn có quyền với cơ sở dữ liệu.</p>' +
      '<a href="/conversation-ops/audit.csv" download>Xuất 500 thao tác gần nhất (CSV)</a><div class="co-audit"></div></details></div>';
    // Giữ đúng cây của lượt render: tab-body được dùng lại khi chuyển sang Hộp thư.
    host = host.querySelector('.co-work');
    var generation = 0;
    async function load() {
      var current = ++generation;
      var p = new URLSearchParams({channel: host.querySelector('.co-channel').value,
        days: host.querySelector('.co-days').value, sla: host.querySelector('.co-sla').value});
      try {
        var d = (await api('report?' + p)).report;
        if (!host.isConnected || current !== generation) return;
        host.querySelector('.co-updated').textContent = 'Cập nhật ' + new Date(d.generated_at*1000).toLocaleString();
        var cards = [['Đang chờ',d.pending_count],['Quá mục tiêu',d.overdue_count],['Khách mới',d.new_customers],
          ['Phản hồi đầu',duration(d.avg_seconds)],['AI đã gửi',d.messages.ai],['Người đã gửi',d.messages.human]];
        host.querySelector('.co-report').innerHTML = '<div class="co-kpis">' + cards.map(function (x) {
          return '<div><small>' + esc(x[0]) + '</small><strong>' + esc(x[1]) + '</strong></div>';
        }).join('') + '</div><p class="co-muted">Đạt mục tiêu: ' + d.sla_met + '/' + d.response_count + ' đợt đã trả lời. ' + esc(d.limitations) + '</p>' +
          '<h3>Tin khách theo giờ</h3><div class="co-hours" aria-label="Số tin khách theo giờ">' + d.hourly.map(function (n,i) {
            var max = Math.max.apply(null,d.hourly.concat([1]));
            return '<div title="' + i + ' giờ: ' + n + ' tin"><i style="height:' + Math.max(2,80*n/max) + 'px"></i><small>' + i + '</small></div>';
          }).join('') + '</div><h3>Khách đang chờ</h3>' + (d.pending.length ? '<div class="co-table"><table><thead><tr><th>Hội thoại</th><th>Phụ trách</th><th>Chờ từ tin đầu</th><th></th></tr></thead><tbody>' +
          d.pending.map(function (c) { return '<tr><td>' + esc(c.title || c.id) + '<small>' + esc(c.account_name) + '</small></td><td>' + esc(c.owner || 'Chưa phân công') +
            '</td><td class="' + (c.overdue?'co-late':'') + '">' + duration(c.waiting_seconds) + '</td><td><button class="s-btn-ghost co-open" data-id="' + c.id + '">Mở</button></td></tr>'; }).join('') + '</tbody></table></div>' : '<p>Chưa có khách đang chờ trên kênh này. Kiểm tra tab Tài khoản bot nếu chưa bật ghi hội thoại.</p>') +
          '<h3>Phản hồi theo tên người gửi</h3><div class="co-table"><table><thead><tr><th>Người gửi</th><th>Số đợt</th><th>Trung bình</th><th>Lâu nhất</th></tr></thead><tbody>' +
          d.responders.map(function (x) { return '<tr><td>' + esc(x.name) + '</td><td>' + x.responses + '</td><td>' + duration(x.avg_seconds) + '</td><td>' + duration(x.max_seconds) + '</td></tr>'; }).join('') + '</tbody></table></div>';
        host.querySelectorAll('.co-open').forEach(function (b) { b.onclick = function () {
          window.JavisConversations.mo({tab:'inbox', conversation_id:Number(b.dataset.id), channel:host.querySelector('.co-channel').value});
        }; });
      } catch (e) { if (host.isConnected && current === generation) host.querySelector('.co-report').textContent = e.message; }
    }
    async function loadTemplates() {
      var items = (await api('templates')).items;
      if (!host.isConnected) return;
      host.querySelector('.co-template-list').innerHTML = items.map(function (x,i) {
        return '<button type="button" class="co-template" data-i="' + i + '"><strong>/' + esc(x.code) + '</strong><span>' + esc(x.text) + '</span></button>';
      }).join('') || '<p>Chưa có mẫu. Tạo mẫu bên dưới; biến {tenKhach} tự điền khi chèn vào hội thoại.</p>';
      host.querySelectorAll('.co-template-list button').forEach(function (b) { b.onclick = function () {
        var f = host.querySelector('form'); f.elements.code.value = items[Number(b.dataset.i)].code;
        f.elements.text.value = items[Number(b.dataset.i)].text;
      }; });
    }
    host.querySelectorAll('select').forEach(function (s) { s.onchange = load; });
    host.querySelector('.co-refresh').onclick = function () { load(); loadTemplates().catch(function (e) { host.querySelector('.co-template-status').textContent = e.message; }); };
    host.querySelector('form').onsubmit = async function (e) {
      e.preventDefault(); var f = this, b = f.querySelector('button'); b.disabled = true;
      try { await api('templates',{code:f.elements.code.value,text:f.elements.text.value}); await loadTemplates();
        host.querySelector('.co-template-status').textContent = 'Đã lưu mẫu.';
      } catch (err) { host.querySelector('.co-template-status').textContent = err.message; }
      b.disabled = false;
    };
    host.querySelectorAll('details')[1].ontoggle = async function () {
      if (!this.open) return;
      try { var items = (await api('audit')).items;
        host.querySelector('.co-audit').innerHTML = items.map(function (x) {
          return '<p><time>' + esc(new Date(x.created_at*1000).toLocaleString()) + '</time> · ' + esc(x.action) + ' · ' + esc(x.target) + '</p>';
        }).join('') || '<p>Chưa có thao tác.</p>';
      } catch (e) { host.querySelector('.co-audit').textContent = e.message; }
    };
    await Promise.all([load(),loadTemplates().catch(function (e) { host.querySelector('.co-template-status').textContent=e.message; })]);
  }
  window.JavisConversationOps = {render:render,attach:attach,slash:slash,expand:expand};
})();
