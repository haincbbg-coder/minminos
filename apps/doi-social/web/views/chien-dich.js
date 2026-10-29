/* One prompt, persisted per-platform variants and explicit publishing policy. */
(function () {
  "use strict";
  DS.view("chien-dich", {title: "Chiến dịch AI", render: function (el, ctx) {
    var esc = DS.esc, tools = [], key = "cmp-" + Date.now() + "-" + Math.random().toString(36).slice(2);
    var base = "/doi-social/campaigns";
    function api(method, path, body) { return DS.api(method, base + path, body); }
    el.innerHTML = '<div class="page-head"><div><h1>Chiến dịch AI</h1><p class="muted">Một ý tưởng → bài riêng theo từng nền tảng → ảnh → lịch đăng.</p></div></div>' +
      '<div class="card"><div class="fld"><label for="cp-prompt">Ý tưởng và yêu cầu</label><textarea class="ta" id="cp-prompt" rows="6" placeholder="Mỗi thứ hai, tư, sáu lúc 09:00 và 20:00, chia sẻ mẹo chăm sóc da. Facebook kể chuyện, Threads ngắn vui, Instagram giàu cảm xúc. Mỗi lượt một góc mới, ảnh tối giản không có chữ."></textarea></div>' +
      '<h3>Đăng ở đâu, giọng văn nào?</h3><p class="small muted">Chọn đúng tài khoản. Nick qua Worker cần máy online và đã đăng nhập nền tảng tương ứng.</p><div id="cp-targets">Đang tải…</div>' +
      '<div class="grid g2 mt"><div class="fld"><label for="cp-source">Ảnh/video</label><select class="sel" id="cp-source"><option value="none">Chỉ nội dung chữ</option><option value="media">Kho media / tải tệp lên</option><option value="folder">Luân phiên ảnh từ thư mục MinMin</option><option value="mcp">Tạo ảnh qua MCP / Higgsfield</option></select></div><div class="fld"><label for="cp-zone">Múi giờ lịch đăng</label><input class="inp" id="cp-zone" value="Asia/Ho_Chi_Minh"></div></div>' +
      '<div id="cp-media" hidden><label class="drop">Tải ảnh/video<input type="file" id="cp-upload" multiple accept="image/jpeg,image/png,image/webp,video/*"></label><div id="cp-library"></div></div>' +
      '<div id="cp-folder-box" class="fld" hidden><label for="cp-folder">Thư mục ảnh trên máy cài MinMin</label><input class="inp" id="cp-folder" placeholder="/data/anh-san-pham"><p class="small muted">Không phải thư mục trên PC Worker. Mỗi lượt lấy một ảnh, không đọc thư mục con.</p></div>' +
      '<div id="cp-mcp" hidden><p>Dùng kết nối MCP đã cấu hình trong MinMin. Thêm Higgsfield/MCP mới tại <a href="/">Kết nối</a>, sau đó tải lại danh sách.</p><button class="btn" id="cp-load-tools">Tải công cụ MCP</button>' +
      '<div class="fld"><label for="cp-tool">Công cụ tạo ảnh</label><select class="sel" id="cp-tool"></select></div><div class="fld"><label for="cp-args">Tham số JSON theo schema công cụ</label><textarea class="ta" id="cp-args" rows="4">{"prompt":"{{image_prompt}}"}</textarea></div>' +
      '<details><summary>Schema công cụ đã chọn</summary><pre id="cp-schema"></pre></details><div class="fld"><label for="cp-poll">Công cụ kiểm tra tác vụ (nếu tạo ảnh bất đồng bộ)</label><select class="sel" id="cp-poll"></select></div><div class="fld"><label for="cp-poll-args">Tham số kiểm tra JSON</label><textarea class="ta" id="cp-poll-args" rows="2">{"job_id":"{{job_id}}"}</textarea></div><p class="small muted">Biến: {{prompt}}, {{image_prompt}}, {{job_id}}. Tác vụ chưa rõ kết quả sẽ dừng để kiểm tra, không tự gọi tạo ảnh có phí lần nữa.</p></div>' +
      '<div class="grid g3 mt"><div class="fld"><label for="cp-schedule">Lịch</label><select class="sel" id="cp-schedule"><option value="prompt">AI đọc giờ / tần suất từ prompt</option><option value="once">Chỉ một lượt ngay</option></select></div><div class="fld"><label for="cp-cap">Tối đa lượt / ngày</label><input class="inp" type="number" id="cp-cap" min="1" max="24" value="5"></div><div class="fld"><label for="cp-image-cap">Tối đa lượt tạo ảnh / ngày</label><input class="inp" type="number" id="cp-image-cap" min="1" max="24" value="5"></div></div>' +
      '<p><label><input type="checkbox" id="cp-auto"> Cho phép tự duyệt và đăng theo lịch vào các đích đã chọn</label></p><p class="small muted">Để trống: chỉ tạo nháp chờ duyệt. Mỗi lượt có bài riêng cho từng đích. YouTube cần video có sẵn; ảnh không thay thế video.</p><button class="btn btn-pri" id="cp-start">Tạo chiến dịch từ prompt</button><p id="cp-message" role="status"></p></div>' +
      '<h2 class="mt">Chiến dịch của bạn</h2><p class="small muted">Tạm dừng chặn lượt tạo mới. Bài đã duyệt trong hàng đợi cần dừng tại Bài đăng / Duyệt nội dung. “Đã vào hàng đợi” chưa có nghĩa đã đăng thành công.</p><div id="cp-list"></div>';
    function q(id) { return el.querySelector("#cp-" + id); }
    function when(t, zone) {
      try { return new Intl.DateTimeFormat("vi-VN", {timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit"}).format(new Date(t * 1000)); }
      catch (e) { return DS.gioDu(t); }
    }
    function library(items) {
      q("library").innerHTML = items.map(function (m) { return '<label class="row"><input type="checkbox" data-media="' + esc(m.tep) + '">' + esc(m.ten || m.tep) + '</label>'; }).join("") || '<p class="muted">Kho trống; tải tệp lên trước.</p>';
    }
    api("GET", "/catalog").then(function (d) {
      if (!ctx.alive || d.ok === false) return;
      q("targets").innerHTML = d.targets.map(function (t, i) { return '<div class="row mt-s"><label><input type="checkbox" data-target="' + esc(t.id) + '"> ' + esc(t.name) + '</label><select class="sel" data-style="' + esc(t.id) + '" aria-label="Phong cách ' + esc(t.name) + '">' + Object.keys(d.styles).map(function (s) { return '<option value="' + s + '">' + esc(d.styles[s]) + '</option>'; }).join("") + '</select></div>'; }).join("") || '<p>Chưa có đích đăng. Thêm Trang API hoặc profile tại Tài khoản trước.</p>';
      library(d.media || []);
    });
    q("source").onchange = function () { ["media", "mcp"].forEach(function (name) { q(name).hidden = q("source").value !== name; }); q("folder-box").hidden = q("source").value !== "folder"; };
    q("upload").onchange = function () {
      var fd = new FormData(); Array.from(q("upload").files).forEach(function (file) { fd.append("tep", file, file.name); });
      q("start").disabled = true;
      DS.api("POST", "/doi-social/fp/media", fd).then(function (d) { if (d.ok !== false) return api("GET", "/catalog").then(function (c) { if (c.ok !== false && ctx.alive) library(c.media || []); }); }).finally(function () { if (ctx.alive) q("start").disabled = false; });
    };
    q("load-tools").onclick = function () { api("GET", "/mcp").then(function (d) {
      if (d.ok === false || !ctx.alive) return;
      tools = d.tools || [];
      ["tool", "poll"].forEach(function (field) { q(field).innerHTML = '<option value="">Chọn công cụ</option>' + tools.filter(function (t) { return t.kind === (field === "tool" ? "generate" : "poll"); }).map(function (t) { return '<option value="' + esc(t.id) + '">' + esc(t.label + " · " + t.name) + '</option>'; }).join(""); });
      if (!tools.length) DS.toast("Chưa có công cụ tạo ảnh được cấp quyền; kiểm tra Kết nối MCP", "info");
    }); };
    q("tool").onchange = function () { var t = tools.find(function (x) { return x.id === q("tool").value; }); q("schema").textContent = JSON.stringify(t ? t.schema : {}, null, 2); };
    q("start").onclick = function () {
      var targets = Array.from(el.querySelectorAll('[data-target]:checked')).map(function (box) { var style = Array.from(el.querySelectorAll('[data-style]')).find(function (s) { return s.dataset.style === box.dataset.target; }); return {id: box.dataset.target, style: style.value}; });
      var image = {mode: q("source").value, media: Array.from(el.querySelectorAll('[data-media]:checked')).map(function (b) { return b.dataset.media; }), folder: q("folder").value, generate_tool: q("tool").value, args: q("args").value, poll_tool: q("poll").value, poll_args: q("poll-args").value};
      q("start").disabled = true; q("message").textContent = "Đang lưu chiến dịch…";
      api("POST", "", {client_key: key, prompt: q("prompt").value, targets: targets, image: image, timezone: q("zone").value, schedule: q("schedule").value, max_runs_day: Number(q("cap").value), max_images_day: Number(q("image-cap").value), auto_publish: q("auto").checked}).then(function (d) {
        if (!ctx.alive) return;
        q("message").textContent = d.ok === false ? d.error : "Đã lưu. AI đang lập kế hoạch; xem lịch và kết quả bên dưới.";
        if (d.ok !== false) { key = "cmp-" + Date.now() + "-" + Math.random().toString(36).slice(2); refresh(); }
      }).finally(function () { if (ctx.alive) q("start").disabled = false; });
    };
    var states = {planning: "AI đang lập kế hoạch", active: "Đang bật", paused: "Tạm dừng", error: "Cần kiểm tra", queued: "Đã tạo nháp / vào hàng đợi", new: "Chờ tạo", writing: "Đang viết", generating: "Đang tạo ảnh", waiting_media: "Đang chờ ảnh"};
    function refresh() { api("GET", "").then(function (d) {
      if (!ctx.alive || d.ok === false) return;
      q("list").innerHTML = (d.items || []).map(function (c) { return '<article class="card mt"><h3>' + esc(c.title) + '</h3><p>' + esc(states[c.state] || c.state) + ' · ' + (c.settings.auto_publish ? "Tự đăng" : "Chờ duyệt") + '</p><p class="small">' + esc(c.prompt) + '</p><p>Lượt tiếp: ' + esc(c.next_at ? when(c.next_at, c.settings.timezone) + ' (' + c.settings.timezone + ')' : 'Không còn lịch') + '</p><pre>' + esc(c.plan.kind ? JSON.stringify(c.plan.schedule || {loai: c.plan.kind, gio: c.plan.times, thu: c.plan.weekdays, cach_phut: c.plan.minutes}, null, 2) : '') + '</pre><p>' + esc(c.message) + '</p><div class="row">' + (c.state === "active" || c.state === "planning" ? '<button class="btn" data-cmd="pause" data-id="' + c.id + '">Tạm dừng</button>' : (c.state === "paused" || c.state === "error") ? '<button class="btn" data-cmd="resume" data-id="' + c.id + '">Tiếp tục lịch</button>' : '') + (c.state === "active" ? '<button class="btn" data-cmd="run" data-id="' + c.id + '">Tạo thêm một lượt ngay</button>' : '') + '</div>' + c.runs.slice(0, 5).map(function (r) { return '<details class="mt-s"><summary>' + esc(when(r.slot, c.settings.timezone) + ' · ' + (states[r.state] || r.state)) + '</summary><p>' + esc(r.message) + '</p>' + r.outputs.map(function (o) { return '<p><a href="#/' + (o.kind === "api" ? "fp-bai" : "duyet") + '">' + esc(o.name) + '</a>: ' + esc(o.status) + '</p>'; }).join("") + '</details>'; }).join("") + '</article>'; }).join("") || '<p class="muted">Chưa có chiến dịch.</p>';
    }); }
    q("list").onclick = function (e) { var b = e.target.closest('[data-cmd]'); if (b) api("POST", "/" + b.dataset.id + "/" + b.dataset.cmd, {}).then(refresh); };
    refresh(); ctx.every(refresh, 10000);
  }});
})();
