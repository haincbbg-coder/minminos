// ============================================================
// Javis - Trang Chatbot: quản lý các Bot chuyên trách (mỗi bot một Agent, một brain,
// một token Telegram riêng). console.js gọi window.JavisChatbots.render(el).
//
// UX dựng theo hướng NHIỀU BOT ngay từ đầu dù lần đầu chỉ chạy một con: lưới thẻ, ô tìm,
// thêm/sửa/xoá, bật/tắt tại chỗ. Thêm bot thứ hai không phải sửa lại giao diện.
//
// Xem docs/dev/2026-08-bot-chuyen-trach-spec.md
// ============================================================
(function () {
  "use strict";

  // Locale để định dạng số/ngày. Lấy từ i18n chứ KHÔNG khoá "vi-VN": người dùng đổi
  // ngôn ngữ giao diện thì ngày giờ phải đổi theo, nếu không thì nửa màn hình tiếng Anh
  // mà ngày vẫn dd/mm/yyyy kiểu Việt.
  const LOC = () => (window.JavisI18n && JavisI18n.locale()) || "vi-VN";
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function el(html) { var d = document.createElement("div"); d.innerHTML = html.trim(); return d.firstChild; }
  function brain() { try { return (window.currentBrainPath && window.currentBrainPath()) || "brain"; } catch (e) { return "brain"; } }

  async function api(url, opts) {
    var r = await fetch(url, opts || {});
    var d = null;
    try { d = await r.json(); } catch (e) { d = {}; }
    if (!r.ok || d.ok === false) throw new Error((d && d.error) || window.t("cb.loi_ma", { ma: r.status }));
    return d;
  }
  function fd(obj) {
    var f = new FormData();
    Object.keys(obj || {}).forEach(function (k) { if (obj[k] != null) f.append(k, obj[k]); });
    return f;
  }

  // Bốn trạng thái THẬT, không phải hai. "Bot chết âm thầm" là thứ chủ chỉ phát hiện khi
  // có người phàn nàn, nên lỗi phải là một ô màu nhìn thấy được chứ không phải sự vắng mặt.
  var TRANG_THAI = {
    running:  { nhan: "cb.tt_dang_chay", mau: "ok" },
    starting: { nhan: "cb.tt_khoi_dong", mau: "wait" },
    error:    { nhan: "cb.tt_loi", mau: "err" },
    off:      { nhan: "cb.tt_tat", mau: "off" },
  };

  // Nhãn + cảnh báo của từng mức quyền do SERVER cấp (kèm trong GET /chatbots). Không chép
  // cứng ở đây: chép rồi thì một hôm server siết thêm rào mà ô cảnh báo vẫn hứa như cũ, và
  // chủ bấm đồng ý dựa trên một câu đã sai.
  var _bots = [], _q = "", _host = null, _mucDS = [], _timer = null, _dauVet = "";
  // Danh sách kênh do SERVER cấp (kèm chỗ lấy token và kênh đó KHÔNG làm được gì). Không chép
  // cứng ở đây: hôm nào Zalo mở API gửi tài liệu thì server đổi một chỗ, giao diện theo ngay.
  var _kenhDS = [], _kenhLoc = "";
  // Tài khoản kênh chưa bot nào trực (server cấp kèm GET /chatbots). Form tạo bot cho CHỌN
  // trong danh sách này thay vì bắt dán token; dán token mới cũng được, và token đó thành một
  // tài khoản ở tab Tài khoản bot.
  var _tkRanh = [];

  // Kênh KHÔNG đoán theo id: mọi thứ (nhãn, logo, năng lực) lấy từ danh sách server cấp. Kênh
  // lạ (server mới có kênh mà giao diện cũ) thì hiện tên trần, không vẽ nhầm logo kênh khác.
  function kenhCua(id) {
    for (var i = 0; i < _kenhDS.length; i++) if (_kenhDS[i].id === id) return _kenhDS[i];
    return { id: id || "", nhan: id || "", logo: "", lay_token: "", co_nhom: false, gui_tai_lieu: false,
             tien_to_ten: "", tom_tat: "", nang_luc: {} };
  }
  function logoKenh(id, size) {
    var k = kenhCua(id);
    return k.logo ? Icons.kenh(k.logo, { size: size || "13px" }) : "";
  }

  // Nhãn kênh: LOGO + tên. Đây là thứ phân biệt hai con bot trong cùng một lưới thẻ, nên nó
  // phải bắt mắt trước khi người ta kịp đọc chữ - xem khối chú thích ở Icons.kenh.
  function chipKenh(id, cls) {
    return '<span class="cb-kenh-chip ' + (cls || "") + '">' + logoKenh(id) +
           " " + esc(kenhCua(id).nhan) + "</span>";
  }
  // Chip MỘT tài khoản kênh trên thẻ bot: logo kênh + tên tài khoản phía nền tảng.
  function chipTK(a) {
    var k = kenhCua(a.channel);
    return '<span class="cb-kenh-chip" title="' + esc(k.nhan) + '">' + logoKenh(a.channel) + " " +
           esc(a.external_id ? (k.tien_to_ten || "") + a.external_id : (a.label || k.nhan)) + "</span>";
  }
  // Bot có tài khoản nào đứng được trong nhóm không (quyết định khối cấu hình nhóm).
  function coNhom(b) {
    return (b.accounts || []).some(function (a) { return kenhCua(a.channel).co_nhom; });
  }

  // Trạng thái bot là thứ ĐỔI MÀ KHÔNG AI BẤM: bấm Bật xong server trả về "đang khởi động"
  // (poller mới tạo, chưa kịp hỏi Telegram), rồi vài giây sau nó thành "đang chạy" - nhưng
  // trang chỉ nạp lại khi người dùng bấm cái gì đó, nên thẻ đứng nguyên ở "Đang khởi động" cho
  // tới lúc rời trang rồi quay lại. Chủ repo dính đúng ca này: bot chạy thật, trả lời thật, mà
  // thẻ vẫn báo đang khởi động. Poller cũng là chỗ duy nhất thấy được bot vừa CHẾT.
  var NHIP = 5000;

  function mucCua(id) {
    for (var i = 0; i < _mucDS.length; i++) if (_mucDS[i].id === id) return _mucDS[i];
    return { id: id || "suggest", nhan: window.t("cb.muc_chi_doc"), canh_bao: [], can_xac_nhan: false };
  }

  // Nhịp tự làm mới. Dừng khi node của trang đã bị tháo khỏi DOM (console.js thay hẳn
  // #cviewBody mỗi lần đổi trang) và khi tab bị ẩn - không thì mỗi trang từng mở để lại một
  // vòng lặp gọi mạng mãi mãi.
  function nhipTuLamMoi() {
    if (_timer) { clearInterval(_timer); _timer = null; }
    _timer = setInterval(function () {
      if (!_host || !document.body.contains(_host)) { clearInterval(_timer); _timer = null; return; }
      if (document.hidden) return;
      if (document.querySelector(".cb-modal")) return;   // đang mở form: đừng vẽ lại dưới chân
      tai(true);
    }, NHIP);
  }

  function render(host) {
    _host = host;
    host.innerHTML =
      '<div class="cview-section cb-wrap">' +
        '<div class="cb-bar">' +
          '<input class="cb-search" placeholder="' + esc(window.t("cb.tim_ph")) + '">' +
          '<button class="s-btn cb-new" type="button">' + ic("plus") + ' ' +
            esc(window.t("cb.bot_moi")) + '</button>' +
        '</div>' +
        '<div class="cb-loc"></div>' +
        '<p class="cb-intro">' + esc(window.t("cb.intro_1")) + ' <b>' + esc(brain()) + '</b>' +
        esc(window.t("cb.intro_2")) + ' <b>Agent</b> ' + esc(window.t("cb.intro_3")) +
        esc(window.t("cb.intro_4")) + ' <b>' + esc(window.t("cb.intro_chi_doc")) + '</b>' +
        esc(window.t("cb.intro_5")) + ' <b>' + esc(window.t("cb.intro_lam_that")) + '</b> ' +
        esc(window.t("cb.intro_6")) + '<br>' +
        esc(window.t("cb.intro_7")) + '<br>' +
        esc(window.t("cb.intro_8")) + '</p>' +
        '<div class="cb-grid"></div>' +
      '</div>';
    host.querySelector(".cb-new").onclick = function () { moForm(null); };
    var s = host.querySelector(".cb-search");
    s.oninput = function () { _q = s.value.trim().toLowerCase(); ve(); };
    tai();
    nhipTuLamMoi();
  }

  // `im` = lần nạp của nhịp tự động: KHÔNG được xoá lưới đang hiện để thay bằng "Đang tải…",
  // và mạng hỏng một nhịp thì giữ nguyên màn hình cũ chứ đừng thay bằng câu báo lỗi. Nhấp nháy
  // mỗi năm giây còn khó chịu hơn con số cũ vài giây.
  async function tai(im) {
    var box = _host && _host.querySelector(".cb-grid");
    if (!box) return;
    if (!im) box.innerHTML = '<div class="cb-empty">' + esc(window.t("common.loading")) + '</div>';
    try {
      // Lọc theo brain đang mở: trang này thuộc về một brain, y như trang Agents và Skills.
      // console.js tự gọi lại renderPage khi đổi brain nên không cần lắng nghe gì thêm.
      var d = await api("/chatbots?brain=" + encodeURIComponent(brain()));
      _bots = d.bots || [];
      _mucDS = d.muc_quyen || [];
      _langDS = d.lang_list || [];
      _kenhDS = d.kenh || [];
      _tkRanh = d.tai_khoan || [];
      var vet = JSON.stringify(_bots);
      // Nhịp ngầm mà không có gì đổi thì ĐỪNG dựng lại DOM. Không phải để tiết kiệm: dựng lại
      // mỗi 5 giây nghĩa là cứ 5 giây một lần có một khoảnh khắc nút vừa bị thay khỏi cây, và
      // cú bấm rơi đúng lúc đó thì mất.
      if (im && vet === _dauVet) return;
      _dauVet = vet;
    } catch (e) {
      if (!im) box.innerHTML = '<div class="cb-empty">' + esc(window.t("cb.loi_tai_ds")) + ' ' +
                               esc(e.message) + '</div>';
      return;
    }
    ve();
  }

  // Bộ lọc kênh chỉ hiện khi thật sự có từ HAI kênh trở lên. Người mới chỉ có bot Telegram mà
  // đã phải nhìn một hàng nút lọc thì đó là câu trả lời cho một câu hỏi họ chưa từng hỏi.
  function veLoc() {
    var hop = _host && _host.querySelector(".cb-loc");
    if (!hop) return;
    var dem = {};
    _bots.forEach(function (b) {
      var k = b.channel || "telegram";
      dem[k] = (dem[k] || 0) + 1;
    });
    var ks = Object.keys(dem);
    if (ks.length < 2) { hop.innerHTML = ""; _kenhLoc = ""; return; }
    hop.innerHTML =
      '<button class="cb-loc-o' + (_kenhLoc ? "" : " on") + '" data-k="" type="button">' +
        esc(window.t("studio.all")) + ' <span class="cb-loc-n">' + _bots.length + '</span></button>' +
      ks.map(function (k) {
        return '<button class="cb-loc-o' + (_kenhLoc === k ? " on" : "") + '" data-k="' + esc(k) +
          '" type="button">' + logoKenh(k, "14px") + " " + esc(kenhCua(k).nhan) +
          ' <span class="cb-loc-n">' + dem[k] + '</span></button>';
      }).join("");
    hop.querySelectorAll(".cb-loc-o").forEach(function (n) {
      n.onclick = function () { _kenhLoc = n.dataset.k || ""; ve(); };
    });
  }

  function ve() {
    var box = _host && _host.querySelector(".cb-grid");
    if (!box) return;
    veLoc();
    var ds = _bots.filter(function (b) {
      if (_kenhLoc && (b.channel || "telegram") !== _kenhLoc) return false;
      return !_q || String(b.name || "").toLowerCase().indexOf(_q) !== -1;
    });
    if (!_bots.length) {
      box.innerHTML =
        '<div class="cb-empty"><div class="cb-empty-ico">' + ic("bot", { cls: "ic-xl" }) + '</div>' +
        '<b>' + esc(window.t("cb.rong_tieu_de")) + '</b>' +
        '<div>' + esc(window.t("cb.rong_1")) + ' <b>' + esc(window.t("cb.rong_tat")) + '</b>' +
        esc(window.t("cb.rong_2")) + '</div></div>';
      return;
    }
    if (!ds.length) { box.innerHTML = '<div class="cb-empty">' + esc(window.t("cb.khong_khop")) + '</div>'; return; }
    box.innerHTML = "";
    ds.forEach(function (b) { box.appendChild(the(b)); });
  }

  function the(b) {
    var st = b.status || {};
    var tt = TRANG_THAI[st.state] || TRANG_THAI.off;
    var loi = st.last_error ? '<div class="cb-err">' + esc(String(st.last_error).slice(0, 160)) + '</div>' : "";
    // Agent bị xoá hay đổi slug: bot vẫn chạy nhưng trả lời bằng vai trò rỗng. Phải báo,
    // không được để im - đó đúng kiểu hỏng mà cả tính năng này đang cố tránh.
    var mat = b.agent_missing
      ? '<div class="cb-err">' + ic("triangle-alert") + ' ' +
        esc(window.t("cb.agent_mat", {
          // Bot thiếu hẳn object agent (hoặc agent không có slug) thì chỗ điền nhận undefined,
          // mà t() chỉ thay khi giá trị khác null - để nguyên là người dùng đọc thấy "{slug}".
          slug: (b.agent || {}).slug || window.t("cb.agent_khong_ro"),
        })) + '</div>' : "";
    // Poller sống KHÔNG có nghĩa là bot trả lời được: model gọi hỏng thì chấm vẫn xanh trong
    // khi người hỏi nhận toàn câu xin lỗi. Lỗi lượt gần nhất phải nằm ngay trên thẻ, không bắt chủ
    // mở Nhật ký mới thấy - vì chủ chỉ mở Nhật ký khi đã NGỜ là có chuyện.
    var lluot = b.loi_luot
      ? '<div class="cb-err">' + ic("triangle-alert") + ' ' + esc(window.t("cb.luot_loi")) + ' ' +
        esc(String(b.loi_luot).slice(0, 200)) + '</div>' : "";
    // Lượt CHẠY ĐƯỢC nhưng không đúng mức đã đặt (engine không gọi nổi công cụ, hoặc chưa đấu
    // nguồn nào). Màu vàng chứ không đỏ: bot vẫn trả lời tử tế, chỉ là chạy thiếu quyền. Để im
    // thì chủ tưởng bot đang làm việc thật - đúng kiểu hỏng lặng lẽ mà cả trang này chống.
    var cbao = b.canh_bao_luot
      ? '<div class="cb-quyen ghi">' + ic("triangle-alert") + ' ' +
        esc(String(b.canh_bao_luot).slice(0, 300)) + '</div>' : "";
    // Mức quyền phải nhìn thấy TỪ NGOÀI THẺ, không phải mở form Sửa mới biết. Một con bot toàn
    // quyền lẫn giữa mấy con chỉ đọc mà nhìn giống hệt nhau là đúng kiểu hỏng im lặng: chủ nhớ
    // nhầm con nào là con nào rồi thả nhầm vào chỗ ai cũng nhắn được.
    //
    // Hiện CẢ mức chỉ đọc, dù nó là mặc định và không có rủi ro gì để cảnh báo. Bản trước bỏ
    // trống ô này cho mức đó, và "không có nhãn" đọc ra được hai nghĩa trái ngược nhau: bot
    // đang chỉ đọc, hay trang này không nói cho biết? Chủ repo hỏi đúng câu ấy. Một nhãn xám
    // rẻ hơn nhiều so với một lần đoán sai theo hướng ngược lại.
    var mq = b.muc_quyen || "suggest";
    var mqLoi = {
      suggest: " - " + window.t("cb.mq_suggest"),
      auto: " - " + window.t("cb.mq_auto"),
      full: " - " + window.t("cb.mq_full"),
    };
    var quyen =
      '<div class="cb-quyen ' + (mq === "full" ? "full" : mq === "auto" ? "ghi" : "doc") + '">' +
        // "shield-alert" không có trong bộ icon đã vendor nên bản trước vẽ ra một ô trống ở
        // đúng chỗ đáng chú ý nhất. Test icon không bắt được vì nó chỉ dò tên viết thẳng trong
        // lời gọi, không dò lời gọi có biểu thức ở trong.
        ic(mq === "full" ? "shield" : mq === "auto" ? "pencil" : "eye") +
        ' ' + esc(window.t("cb.muc_nhan")) + ' <b>' + esc(mucCua(mq).nhan) + '</b>' +
        esc(mqLoi[mq] || "") +
      '</div>';
    // Nhóm có người gọi bot mà chủ chưa cho phép. Đây là chỗ sửa cho lỗi "thả bot vào nhóm,
    // tag tên nó, không thấy gì": hành vi từ chối vẫn đúng, nhưng nay nó nổi lên đây kèm đúng
    // một nút bấm, thay vì bắt chủ đoán rằng mình phải đi khai id nhóm ở đáy form Sửa.
    var cho = (b.nhom_cho || []).map(function (g) {
      return '<div class="cb-nhomcho" data-cid="' + esc(g.chat_id) + '">' +
        '<div class="cb-nhomcho-t">' + ic("message-circle") + ' <b>' +
          esc(g.ten || (window.t("cb.nhom") + " " + g.chat_id)) +
          '</b> <span class="cb-nhomcho-id">' + esc(g.chat_id) + '</span></div>' +
        '<div class="cb-nhomcho-d">' + esc(g.lan
          ? window.t("cb.nhomcho_goi", { count: g.lan })
          : window.t("cb.nhomcho_chua_bat")) + '</div>' +
        '<div class="cb-nhomcho-a">' +
          '<button class="s-btn cb-ok-nhom" type="button">' + ic("check") + ' ' +
            esc(window.t("cb.cho_phep_nhom")) + '</button>' +
          '<button class="s-btn-ghost cb-bo-nhom" type="button">' +
            esc(window.t("cb.bo_qua")) + '</button>' +
        '</div></div>';
    }).join("");
    // getMe hỏng: bot vẫn trả lời tin nhắn riêng hoàn hảo nhưng ĐIẾC trong mọi nhóm, vì không
    // biết @username của chính mình thì không nhận ra ai đang gọi tên. Chấm vẫn xanh, lượt vẫn
    // chạy, không có gì đỏ - nên nếu không có dòng này thì không ai đoán ra được.
    var loiTen = st.loi_danh_tinh
      ? '<div class="cb-err">' + ic("triangle-alert") + ' ' + esc(st.loi_danh_tinh) + '</div>' : "";
    // Cùng loại hỏng-âm-thầm: menu lệnh "/" đặt hụt thì khách gõ "/" không thấy gì để bấm,
    // trong khi thẻ vẫn xanh và bot vẫn trả lời bình thường.
    if (st.loi_menu_lenh)
      loiTen += '<div class="cb-err">' + ic("triangle-alert") + ' ' + esc(st.loi_menu_lenh) + '</div>';
    // Chế độ riêng tư của Telegram chặn Ở PHÍA TELEGRAM, trước khi Javis nhìn thấy tin nào.
    // Hiện cho MỌI bot có dùng nhóm, không riêng bot đặt "trả lời mọi tin": nó là nguyên nhân
    // số một của "nhắn riêng thì được, trong nhóm tag tên thì im re", và người dùng không có
    // cách nào đoán ra vì mọi dấu hiệu trên trang này đều xanh.
    var kenh = b.channel || "";
    var duNhom = (b.groups || []).length || (b.nhom_cho || []).length;
    // Cảnh báo chế độ riêng tư là chuyện RIÊNG của Telegram. Hiện nó trên một thẻ Zalo là dạy
    // người dùng đi mở @BotFather tìm một cài đặt không tồn tại cho con bot đó.
    var coTelegram = (b.accounts || []).some(function (a) { return a.channel === "telegram"; });
    var riengTu = (coTelegram && duNhom && st.da_hoi_telegram && !st.doc_moi_tin_nhom)
      ? '<div class="cb-quyen ghi">' + ic("triangle-alert") + ' ' + esc(window.t("cb.rt_1")) +
        ' <b>' + esc(window.t("cb.rt_che_do")) + '</b> ' + esc(window.t("cb.rt_2")) +
        ' <b>' + esc(window.t("cb.rt_lenh")) + '</b> ' + esc(window.t("cb.rt_va")) +
        ' <b>' + esc(window.t("cb.rt_tra_thang")) + '</b>' +
        esc(b.reply_when === "always" ? window.t("cb.rt_always") : window.t("cb.rt_mention")) + '.<br>' +
        esc(window.t("cb.rt_fix_1")) + ' <b>@BotFather</b> ' + esc(window.t("cb.rt_go")) +
        ' <b>/setprivacy</b>' + esc(window.t("cb.rt_fix_2")) + ' <b>Disable</b>' +
        esc(window.t("cb.rt_fix_3")) + ' <b>' + esc(window.t("cb.rt_quan_tri")) + '</b>. ' +
        esc(window.t("cb.rt_fix_4")) + '</div>' : "";
    var c = el(
      '<div class="cb-card">' +
        '<div class="cb-head">' +
          '<span class="cb-ico">' + ic(b.icon || "headset") +
            ((b.accounts || []).length === 1
              ? '<span class="cb-ico-kenh" title="' + esc(kenhCua(kenh).nhan) + '">' + logoKenh(kenh, "14px") + '</span>'
              : "") + '</span>' +
          '<span class="cb-name">' + esc(b.name) + '</span>' +
          '<span class="cb-dot ' + tt.mau + '" title="' + esc(st.last_error || window.t(tt.nhan)) + '"></span>' +
          '<span class="cb-state">' + esc(window.t(tt.nhan)) + '</span>' +
        '</div>' +
        // Không hiện brain trên thẻ nữa: mọi bot ở đây đều thuộc brain đang mở, nên nhắc lại
        // trên từng thẻ chỉ là nhiễu. Brain nói một lần ở đầu trang là đủ.
        // Tài khoản kênh bot đang trực (0.61.0: một bot trực được nhiều tài khoản). Chưa có
        // tài khoản nào thì nói thẳng, vì đó là lý do bot không bật được.
        '<div class="cb-meta">' +
          ((b.accounts || []).length
            ? (b.accounts || []).map(chipTK).join("")
            : '<span class="cb-warn">' + ic("triangle-alert") + ' ' + esc(window.t("cb.chua_token")) + '</span>') +
          '<span>' + ic("bot") + ' ' + esc(b.agent_name || (b.agent || {}).slug || "?") + '</span>' +
          // Model bot chạy ra ngoài. Nó là model của trợ lý (0.62.3), nên phải hiện ở đây -
          // nếu không thì chọn model cho trợ lý xong vẫn không biết bot đã theo hay chưa.
          '<span title="' + esc(window.t("cb.model_title")) + '">' + ic("cpu") + ' ' +
            esc(b.agent_model || window.t("cb.model_chinh")) + '</span>' +
        '</div>' +
        '<div class="cb-meta">' +
          '<span>' + esc(!coNhom(b) ? window.t("cb.chi_rieng") : (b.groups || []).length
            ? (window.t("cb.n_nhom", { count: b.groups.length }) + ", " +
               (b.reply_when === "always" ? window.t("cb.tl_moi_tin") : b.reply_when === "judge" ? window.t("cb.tl_judge") : window.t("cb.tl_goi_ten")))
            : window.t("cb.chi_rieng")) + '</span>' +
          '<span>' + esc(b.nguon_tra_loi === "tai_lieu" ? window.t("cb.nguon_tl_ngan")
                                                        : window.t("cb.nguon_ag_ngan")) + '</span>' +
          '<span>' + esc(window.t("cb.n_luot_tra_loi", { count: st.answered || 0 })) + '</span>' +
          (b.handoff_to ? '<span>' + ic("user") + ' ' + esc(window.t("cb.co_chuyen_nguoi")) + '</span>'
                        : '<span class="cb-warn">' + esc(window.t("cb.chua_nguoi_nhan")) + '</span>') +
        '</div>' +
        // Hộp thư hội thoại: số cuộc chat khách hôm nay và số chưa đọc, ngay trên thẻ. Bấm nút
        // Hội thoại ở dưới là sang trang Hội thoại đã lọc sẵn theo bot này.
        (b.hoi_thoai && (b.hoi_thoai.tong || 0) > 0
          ? '<div class="cb-meta"><span>' + ic("messages-square") + ' ' +
            esc(window.t("cb.hoi_thoai_tom", { hom_nay: b.hoi_thoai.hom_nay || 0,
                                               chua_doc: b.hoi_thoai.chua_doc || 0 })) + '</span></div>'
          : "") +
        cho + quyen + loiTen + riengTu + mat + lluot + cbao + loi +
        '<div class="cb-acts">' +
          '<button class="s-btn-ghost cb-toggle" type="button">' +
            (b.enabled ? ic("circle-stop") + " " + esc(window.t("cb.tat"))
                       : ic("play") + " " + esc(window.t("cb.bat"))) + '</button>' +
          '<button class="s-btn-ghost cb-log" type="button">' + ic("history") + ' ' +
            esc(window.t("cb.nhat_ky")) + '</button>' +
          '<button class="s-btn-ghost cb-hoi-thoai" type="button">' + ic("messages-square") + ' ' +
            esc(window.t("cb.xem_hoi_thoai")) + '</button>' +
          '<button class="s-btn-ghost cb-edit" type="button">' + esc(window.t("common.edit")) + '</button>' +
          '<button class="s-btn-ghost cb-del" type="button">' + esc(window.t("common.delete")) + '</button>' +
        '</div>' +
      '</div>');
    c.querySelector(".cb-toggle").onclick = function () { bat(b, !b.enabled); };
    c.querySelector(".cb-log").onclick = function () { moNhatKy(b); };
    c.querySelector(".cb-hoi-thoai").onclick = function () {
      if (window.JavisConversations) window.JavisConversations.mo({ bot_id: b.id });
    };
    c.querySelector(".cb-edit").onclick = function () { moForm(b); };
    c.querySelector(".cb-del").onclick = function () { xoa(b); };
    c.querySelectorAll(".cb-nhomcho").forEach(function (n) {
      var cid = n.dataset.cid;
      n.querySelector(".cb-ok-nhom").onclick = function () { choNhom(b, cid, true); };
      n.querySelector(".cb-bo-nhom").onclick = function () { choNhom(b, cid, false); };
    });
    return c;
  }

  // Một cú bấm thay cho: gõ /id trong nhóm, chép id, mở Sửa, kéo xuống đáy form, dán, Lưu.
  async function choNhom(b, cid, on) {
    try {
      await api("/chatbots/" + encodeURIComponent(b.id) + "/groups",
                { method: "POST", body: fd({ chat_id: cid, on: on ? "1" : "0" }) });
    } catch (e) {
      alert(window.t("cb.loi_cap_nhat_nhom") + " " + e.message);
    }
    tai();
  }

  // ---------------------------------------------------------------- nhật ký + lỗ hổng
  // Mở tab "Bot bí" TRƯỚC, không phải tab hội thoại. Hội thoại chỉ để soi lại khi nghi ngờ,
  // còn danh sách câu bot trả lời không nổi mới là thứ chủ cần LÀM GÌ ĐÓ với nó: mỗi dòng ở
  // đó là một chỗ tài liệu đang thiếu, viết bổ sung vào brain là lần sau bot trả lời được.
  async function moNhatKy(b) {
    var box = el('<div class="cb-modal"><div class="cb-form cb-log-form">' +
      '<h3>' + esc(window.t("cb.nhat_ky")) + ' - ' + esc(b.name) + '</h3>' +
      '<div class="cb-tabs">' +
        '<button class="cb-tab on" data-t="gaps" type="button">' + esc(window.t("cb.tab_bi")) + '</button>' +
        '<button class="cb-tab" data-t="turns" type="button">' + esc(window.t("cb.tab_hoi_thoai")) + '</button>' +
      '</div>' +
      '<div class="cb-log-body">' + esc(window.t("common.loading")) + '</div>' +
      '<div class="cb-form-acts"><button class="s-btn" id="cbLogClose" type="button">' +
        esc(window.t("common.close")) + '</button></div>' +
      '</div></div>');
    document.body.appendChild(box);
    var dong = function () { if (box.parentNode) box.parentNode.removeChild(box); };
    box.onmousedown = function (e) { if (e.target === box) dong(); };
    box.querySelector("#cbLogClose").onclick = dong;

    var than = box.querySelector(".cb-log-body"), d = null;
    try { d = await api("/chatbots/" + encodeURIComponent(b.id) + "/log?limit=60"); }
    catch (e) { than.textContent = window.t("cb.loi_tai_nhat_ky") + " " + e.message; return; }

    function ve(tab) {
      if (tab === "turns") { than.innerHTML = veLuot(d.turns || []); return; }
      than.innerHTML = veLoHong(d.gaps || [], d.tom_tat || {});
    }
    box.querySelectorAll(".cb-tab").forEach(function (t) {
      t.onclick = function () {
        box.querySelectorAll(".cb-tab").forEach(function (x) { x.classList.remove("on"); });
        t.classList.add("on");
        ve(t.dataset.t);
      };
    });
    ve("gaps");
  }

  function gio(ts) {
    if (!ts) return "";
    try { return new Date(ts * 1000).toLocaleString(LOC()); } catch (e) { return ""; }
  }

  function veLoHong(gaps, tt) {
    if (!gaps.length) {
      return '<div class="cb-empty">' + (tt.luot
        ? '<b>' + esc(window.t("cb.bi_rong")) + '</b><div>' +
          esc(window.t("cb.bi_rong_luot", { count: tt.luot })) + '</div>'
        : '<b>' + esc(window.t("cb.chua_luot")) + '</b><div>' +
          esc(window.t("cb.chua_luot_goi_y")) + '</div>') + '</div>';
    }
    return '<div class="cb-sum">' + esc(window.t("cb.tom_tat",
        { luot: tt.luot, bi: tt.bi, ty_le: tt.ty_le_bi })) + '</div>' +
      '<table class="cb-tbl"><thead><tr><th>' + esc(window.t("cb.th_hoi")) + '</th><th>' +
      esc(window.t("cb.th_so_lan")) + '</th><th>' + esc(window.t("cb.th_gan_nhat")) +
      '</th></tr></thead><tbody>' +
      gaps.map(function (g) {
        return '<tr><td>' + esc(g.hoi) + '</td><td class="cb-num">' + g.lan + '</td><td>' +
               esc(gio(g.lan_cuoi)) + '</td></tr>';
      }).join("") + '</tbody></table>';
  }

  function veLuot(turns) {
    if (!turns.length) return '<div class="cb-empty">' + esc(window.t("cb.chua_luot")) + '</div>';
    return turns.map(function (t) {
      // Nguồn hiện ra để chủ kiểm được bot lấy câu trả lời TỪ ĐÂU. Không có dòng này thì
      // "bot trả lời đúng chưa" là câu hỏi không kiểm chứng được, chỉ đoán.
      var ng = (t.nguon || []).length
        ? '<div class="cb-src">' + ic("file-text") + " " + esc(t.nguon.join(", ")) + '</div>'
        : '<div class="cb-src cb-warn">' + esc(window.t("cb.khong_tai_lieu")) + '</div>';
      // Lượt GÃY: người hỏi chỉ nhận một câu xin lỗi chung, nên đây là chỗ DUY NHẤT chủ đọc được
      // lý do thật. Thiếu nó thì "bot trả lời sai" và "bot đang hỏng" nhìn giống hệt nhau.
      if (t.loi) {
        return '<div class="cb-turn loi">' +
          '<div class="cb-turn-h">' + esc(t.user_name || t.chat_id) + ' · ' + esc(gio(t.ts)) + '</div>' +
          '<div class="cb-q">' + esc(t.hoi) + '</div>' +
          '<div class="cb-err">' + ic("triangle-alert") + ' ' + esc(window.t("cb.luot_nay_loi")) + ' ' +
          esc(t.loi) + '</div></div>';
      }
      return '<div class="cb-turn' + (t.bi ? " bi" : "") + '">' +
        '<div class="cb-turn-h">' + esc(t.user_name || t.chat_id) + ' · ' + esc(gio(t.ts)) +
        (t.chuyen_nguoi ? ' · <b>' + esc(window.t("cb.da_bao_nguoi_truc")) + '</b>' : "") + '</div>' +
        '<div class="cb-q">' + esc(t.hoi) + '</div>' +
        '<div class="cb-a">' + esc(t.dap) + '</div>' + ng + '</div>';
    }).join("");
  }

  async function bat(b, on) {
    // Bật là lúc bot bắt đầu nói chuyện với người thật. Với bot có quyền thao tác, nhắc lại
    // đúng ở đây - lúc tạo có thể là mấy hôm trước, và tay bấm Bật chưa chắc nhớ mình đã đặt
    // mức nào cho con này.
    var mq = b.muc_quyen || "suggest";
    if (on && mucCua(mq).can_xac_nhan &&
        !confirm(window.t("cb.xn_bat", { ten: b.name, muc: mucCua(mq).nhan }) + "\n\n" +
                 (mq === "full" ? window.t("cb.xn_bat_full") : window.t("cb.xn_bat_auto")))) return;
    try {
      await api("/chatbots/" + encodeURIComponent(b.id) + "/enable",
                { method: "POST", body: fd({ on: on ? "1" : "0" }) });
    } catch (e) {
      alert((on ? window.t("cb.loi_bat") : window.t("cb.loi_tat")) + " " + e.message);
    }
    tai();
  }

  async function xoa(b) {
    // Nói rõ cái gì MẤT và cái gì CÒN. Người dùng không đoán được hậu quả thì đừng bắt họ gánh.
    if (!confirm(window.t("cb.xn_xoa", { ten: b.name }) + "\n\n" +
                 window.t("cb.xn_xoa_giu"))) return;
    try { await api("/chatbots/" + encodeURIComponent(b.id) + "/delete", { method: "POST" }); }
    catch (e) { alert(window.t("cb.loi_xoa") + " " + e.message); }
    tai();
  }

  // ---------------------------------------------------------------- form tạo / sửa
  // Bot KHÔNG có brain riêng để chọn. Nó thuộc về brain đang mở, cùng chỗ với Agent nó dùng và
  // tài liệu nó đọc. Bản trước bắt chọn brain trong form, và chọn xong lại phải nhớ Agent nằm
  // ở brain nào - hai lớp phải khớp nhau mà không có gì bắt chúng khớp. Bỏ hẳn ô đó thì phạm
  // vi của trang chính là câu trả lời, và không còn gì để lệch.
  async function nạpAgent(br) {
    try {
      // Bản NHẸ: ô chọn chỉ hiện tên + vai trò, không đụng tới system prompt.
      var ad = await api("/agents?brain=" + encodeURIComponent(br || "brain") + "&prompt=0");
      return ad.agents || [];
    } catch (e) { return []; }
  }

  // Vai trò dài thì <option> tràn ngang khỏi hộp và không xuống dòng được (giới hạn của thẻ
  // select gốc). Cắt ngắn là cách duy nhất chắc chắn; tên Agent luôn giữ đủ.
  function optAgent(a, slugDangChon) {
    var vai = String(a.role || "").trim();
    if (vai.length > 34) vai = vai.slice(0, 34).trim() + "…";
    return '<option value="' + esc(a.slug) + '"' + (a.slug === slugDangChon ? " selected" : "") +
           '>' + esc(a.name) + (vai ? " - " + esc(vai) : "") + '</option>';
  }

  function htmlAgent(ds, slugDangChon) {
    return ds.length ? ds.map(function (a) { return optAgent(a, slugDangChon); }).join("")
                     : '<option value="">' + esc(window.t("cb.khong_agent")) + '</option>';
  }

  // ---- NHÓM KHÁCH (26.10.60) -------------------------------------------------------------
  // Mỗi nhóm: tên, thành viên (chọn từ danh bạ), bật/tắt, Agent riêng và phạm vi riêng. Người lạ
  // là một thẻ cố định cuối danh sách. Trạng thái nằm trong DOM, đọc ra bằng docNhom().
  var _nkSeq = 0;
  function optAgentRieng(ds, cur) {
    return '<option value="">' + esc(window.t("cb.nk_agent_bot")) + '</option>' +
      ds.map(function (a) { return '<option value="' + esc(a.slug) + '"' + (a.slug === cur ? " selected" : "") + '>' + esc(a.name) + '</option>'; }).join("");
  }
  function htmlPhamVi(p, ds) {
    p = p || {};
    return '<label>' + esc(window.t("cb.nk_agent")) + '</label><select class="nk-agent">' + optAgentRieng(ds, p.agent_slug || "") + '</select>' +
      '<label>' + esc(window.t("cb.nk_nguon")) + '</label><select class="nk-nguon">' +
        '<option value=""' + (!p.nguon_tra_loi ? " selected" : "") + '>' + esc(window.t("cb.nk_nguon_bot")) + '</option>' +
        '<option value="agent"' + (p.nguon_tra_loi === "agent" ? " selected" : "") + '>' + esc(window.t("cb.nk_nguon_agent")) + '</option>' +
        '<option value="tai_lieu"' + (p.nguon_tra_loi === "tai_lieu" ? " selected" : "") + '>' + esc(window.t("cb.nk_nguon_tl")) + '</option></select>' +
      '<label>' + esc(window.t("cb.lb_noi_duoc")) + '</label><textarea class="nk-duoc" rows="2" placeholder="' + esc(window.t("cb.ph_noi_duoc")) + '">' + esc(p.noi_duoc || "") + '</textarea>' +
      '<label>' + esc(window.t("cb.lb_noi_cam")) + '</label><textarea class="nk-cam" rows="2" placeholder="' + esc(window.t("cb.ph_noi_cam")) + '">' + esc(p.noi_cam || "") + '</textarea>' +
      '<label>' + esc(window.t("cb.lb_tu_khoa")) + '</label><input class="nk-tukhoa" value="' + esc((p.cam_tu_khoa || []).join(", ")) + '" placeholder="' + esc(window.t("cb.ph_tu_khoa")) + '">' +
      '<label>' + esc(window.t("cb.lb_ngoai_pv")) + '</label><select class="nk-ngoai">' +
        '<option value="tu_choi"' + (p.ngoai_pham_vi !== "im" ? " selected" : "") + '>' + esc(window.t("cb.npv_tu_choi")) + '</option>' +
        '<option value="im"' + (p.ngoai_pham_vi === "im" ? " selected" : "") + '>' + esc(window.t("cb.npv_im")) + '</option></select>';
  }
  function htmlNhomThe(n, ds) {
    var id = "nkTv" + (++_nkSeq);
    return '<div class="cb-nk" data-id="' + esc(n.id || "") + '">' +
      '<div class="cb-nk-dau"><input class="nk-ten" value="' + esc(n.ten || "") + '" placeholder="' + esc(window.t("cb.nk_ten_ph")) + '">' +
        '<label class="cb-chk"><input type="checkbox" class="nk-bat"' + (n.bat === false ? "" : " checked") + '> ' + esc(window.t("cb.nk_bat")) + '</label>' +
        '<button type="button" class="s-btn-ghost nk-xoa">' + esc(window.t("cb.nk_xoa")) + '</button></div>' +
      '<label>' + esc(window.t("cb.nk_thanh_vien")) + '</label>' +
      '<textarea id="' + id + '" class="nk-tv" rows="2" placeholder="' + esc(window.t("cb.ph_rieng_cho")) + '">' + esc((n.thanh_vien || []).join("\n")) + '</textarea>' +
      '<div class="cb-db" data-loai="" data-ta="' + id + '"></div>' +
      htmlPhamVi(n, ds) + '</div>';
  }
  function htmlNguoiLa(nl, ds) {
    nl = nl || {};
    return '<div class="cb-nk cb-nk-la">' +
      '<div class="cb-nk-dau"><b>' + esc(window.t("cb.nl_ten")) + '</b>' +
        '<select class="nl-bat">' +
          '<option value=""' + (nl.bat === null || nl.bat === undefined ? " selected" : "") + '>' + esc(window.t("cb.nl_mac_dinh")) + '</option>' +
          '<option value="1"' + (nl.bat === true ? " selected" : "") + '>' + esc(window.t("cb.nl_tra_loi")) + '</option>' +
          '<option value="0"' + (nl.bat === false ? " selected" : "") + '>' + esc(window.t("cb.nl_im")) + '</option></select></div>' +
      '<div class="cb-hint">' + esc(window.t("cb.nl_hint")) + '</div>' + htmlPhamVi(nl, ds) + '</div>';
  }
  function docPhamVi(el) {
    var q = function (c) { return (el.querySelector(c) || {}).value || ""; };
    return { agent_slug: q(".nk-agent"), nguon_tra_loi: q(".nk-nguon"), noi_duoc: q(".nk-duoc"),
             noi_cam: q(".nk-cam"), cam_tu_khoa: q(".nk-tukhoa"), ngoai_pham_vi: q(".nk-ngoai") || "tu_choi" };
  }

  // Agent PHỤ: ô tick, tối đa 5. Agent chính không hiện ở đây (đã chọn ở ô trên).
  function htmlAgentPhu(ds, dangChon, chinh) {
    var ra = ds.filter(function (a) { return a.slug !== chinh; }).map(function (a) {
      var on = (dangChon || []).indexOf(a.slug) >= 0;
      return '<label class="cb-chk"><input type="checkbox" class="cbAgentPhuCk" value="' + esc(a.slug) + '"' +
             (on ? " checked" : "") + '> ' + esc(a.name) + '</label>';
    });
    return ra.length ? ra.join("") : '<span class="cb-hint">' + esc(window.t("cb.khong_agent")) + '</span>';
  }

  // Mô tả một dòng cho mỗi mức, hiện ngay trong ô chọn. Cảnh báo ĐẦY ĐỦ nằm ở khối dưới và do
  // server cấp; ba dòng này chỉ để chọn cho đúng ngay từ đầu.
  var MUC_TOM = {
    suggest: "cb.muctom_suggest",
    auto: "cb.muctom_auto",
    full: "cb.muctom_full",
  };

  // Danh sách ngôn ngữ lấy từ /settings (sổ đăng ký phía server), KHÔNG khai lại ở đây.

  // Khai hai nơi thì thêm ngôn ngữ mới phải nhớ sửa cả hai chỗ.

  var _langDS = [];

  function htmlNgonNgu(cur) {

    var ra = '<option value="auto"' + (cur === "auto" || !cur ? " selected" : "") +

             '>' + esc(window.t("cb.lang_auto")) + '</option>';

    _langDS.forEach(function (l) {

      ra += '<option value="' + esc(l.ma) + '"' + (l.ma === cur ? " selected" : "") +

            '>' + esc(l.ten) + '</option>';

    });

    return ra;

  }


  function htmlMuc(dangChon) {
    var ds = _mucDS.length ? _mucDS : [{ id: "suggest", nhan: window.t("cb.muc_chi_doc") }];
    return ds.map(function (m) {
      return '<option value="' + esc(m.id) + '"' + (m.id === dangChon ? " selected" : "") + '>' +
             esc(MUC_TOM[m.id] ? window.t(MUC_TOM[m.id]) : m.nhan) + '</option>';
    }).join("");
  }

  // Khối cảnh báo dựng từ danh sách câu SERVER trả về. Mức chỉ đọc không có câu nào, và đúng
  // như vậy: nó không lấy đi thứ gì để mà cảnh báo.
  function veCanhBao(id) {
    var m = mucCua(id);
    if (!(m.canh_bao || []).length) {
      return '<div class="cb-hint">' + esc(window.t("cb.canhbao_chi_doc")) + '</div>';
    }
    return '<div class="cb-canhbao ' + (id === "full" ? "full" : "ghi") + '">' +
      '<div class="cb-canhbao-h">' + ic("triangle-alert") + ' ' + esc(window.t("cb.canhbao_h1")) +
      ' <b>' + esc(m.nhan) + '</b> ' + esc(window.t("cb.canhbao_h2")) + '</div><ul>' +
      m.canh_bao.map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("") +
      '</ul><label class="cb-ack"><input type="checkbox" id="cbAck"> ' +
      esc(window.t("cb.ack")) + '</label></div>';
  }

  // Danh sách tài khoản kênh để TÍCH CHỌN: tài khoản bot này đang trực (khi sửa) + tài khoản
  // chưa bot nào trực. Tài khoản đang do bot khác trực không hiện: mỗi token một poller.
  // `chinhXac`: khi vẽ LẠI giữa chừng (vừa nối thêm một kênh), `chonSan` là toàn bộ sự thật về
  // những gì đang được tích. Không có cờ này thì `b.accounts` luôn được tích lại, nên một tài
  // khoản vừa bị bỏ tích sẽ lặng lẽ quay về.
  function veChonTK(b, chonSan, chinhXac) {
    var ds = [];
    var da = {};
    ((b && b.accounts) || []).forEach(function (a) { ds.push(a); da[a.id] = true; });
    _tkRanh.forEach(function (a) { if (!da[a.id]) ds.push(a); });
    if (!ds.length) return '<div class="cb-trong-tk">' + esc(window.t("cb.tk_chua_co")) + '</div>';
    var chon = {};
    if (!chinhXac) ((b && b.accounts) || []).forEach(function (a) { chon[a.id] = true; });
    (chonSan || []).forEach(function (id) { chon[id] = true; });
    return '<div class="cb-tk-list">' + ds.map(function (a) {
      var k = kenhCua(a.channel);
      var ten = a.label || k.nhan;
      return '<label class="cb-tk"><input type="checkbox" class="cb-tk-o" value="' + esc(a.id) + '"' +
        (chon[a.id] ? " checked" : "") + ' data-k="' + esc(a.channel) + '" data-ten="' + esc(ten) + '">' +
        '<span class="cb-tk-logo">' + logoKenh(a.channel, "18px") + '</span>' +
        '<span class="cb-tk-text"><b>' + esc(ten) + '</b><small>' + esc(k.nhan) +
        (a.external_id ? ' · ' + esc((k.tien_to_ten || "") + a.external_id) : "") + '</small>' +
        // Kênh kiểu "account" (Zalo cá nhân) là nick của CHÍNH chủ: bot trả lời dưới tên chủ nên
        // nói thẳng ngay lúc chọn. Đọc theo `kind` do server khai, không đoán theo id kênh.
        (k.kind === "account" ? '<small class="cb-tk-luu-y">' + esc(window.t("cb.tk_ca_nhan_luu_y")) + '</small>' : "") +
        '</span></label>';
    }).join("") + '</div>';
  }

  // Mở modal "Thêm tài khoản" của tab Tài khoản bot (chatbots.js KHÔNG tự dựng lại form dán token: xem
  // chú thích ở `moThemTK` trong conversations.js). Xong thì nạp lại danh sách tài khoản rảnh
  // và tích sẵn con vừa nối - đường đi tự nhiên là nối kênh xong dùng luôn, không phải tự tìm
  // lại nó trong danh sách.
  function noiKenhMoi(xong) {
    var fn = window.JavisConversations && window.JavisConversations.themTaiKhoan;
    if (!fn) return alert(window.t("cb.chua_mo_duoc_kenh"));
    fn({ onXong: async function (tk) {
      try {
        var d = await api("/chatbots?brain=" + encodeURIComponent(brain()));
        _kenhDS = d.kenh || _kenhDS;
        _tkRanh = d.tai_khoan || [];
      } catch (e) {}
      // Ghép tay tài khoản vừa nối vào danh sách nếu lần nạp lại chưa thấy nó (mạng hỏng, hoặc
      // server trả về trước khi kho kịp thấy bản ghi mới). Không có bước này thì id vừa tích
      // rơi lặng lẽ: người dùng nối xong một kênh mà nó không hiện ra ở đâu cả.
      if (tk && tk.id && !_tkRanh.some(function (a) { return a.id === tk.id; })) _tkRanh.push(tk);
      xong(tk && tk.id ? tk.id : "");
    } });
  }

  // `truoc` (tuỳ chọn): { account_id } - tài khoản tích sẵn khi mở từ tab Tài khoản bot ("Tạo bot trực").
  //
  // Form đi theo HAI BƯỚC, và đó là cả điểm của nó. Bước 1 hỏi đúng một câu - bot trả lời ở
  // đâu - bước 2 mới là cài đặt. Trước 0.61.1 cả hai nằm chung một màn, kèm luôn một form dán
  // token với hướng dẫn riêng của từng kênh (lấy token ở đâu, kênh nào không vào được nhóm);
  // trên điện thoại người dùng phải cuộn qua một trang chú thích trước khi thấy ô Tên bot. Nó
  // cũng không mở rộng được: mỗi kênh thêm vào là màn hình dài thêm một khối chú thích nữa.
  // Nay hướng dẫn của một kênh chỉ hiện khi người dùng thật sự chọn kênh đó, trong modal Thêm
  // tài khoản của tab Tài khoản bot - một chỗ duy nhất cho mọi kênh.
  //
  // Sửa bot thì vào thẳng bước 2: tài khoản đã chọn rồi, bắt đi lại từ đầu chỉ để sửa một dòng
  // chữ là phiền. Dòng tóm tắt ở đầu bước 2 vẫn dẫn ngược về bước 1 khi cần đổi.
  async function moForm(b, truoc) {
    var sua = !!b;
    var br = brain();                 // brain đang mở = brain của bot, không hỏi lại
    var agents = await nạpAgent(br);
    var chonSan = (truoc && truoc.account_id) ? [truoc.account_id] : [];
    var buoc = sua ? 2 : 1;
    var box = el(
      '<div class="cb-modal"><div class="cb-form cb-wizard">' +
        '<div class="cb-form-h">' +
          '<h3>' + esc(sua ? window.t("cb.sua_bot") : window.t("cb.bot_moi")) + '</h3>' +
          (sua ? "" : '<span class="cb-buoc" id="cbBuoc"></span>') +
        '</div>' +

        // ---------------------------------------------------------------- BƯỚC 1: trả lời ở đâu
        '<div class="cb-b" id="cbB1">' +
          '<label>' + esc(window.t("cb.lb_tai_khoan")) + '</label>' +
          '<div id="cbTkBox">' + veChonTK(b, chonSan) + '</div>' +
          '<div class="cb-hint">' + esc(window.t("cb.hint_tai_khoan")) + '</div>' +
          '<button class="s-btn-ghost cb-noi-kenh" type="button">' + ic("plus") + ' ' +
            esc(window.t("cb.noi_kenh_moi")) + '</button>' +
        '</div>' +

        // ---------------------------------------------------------------- BƯỚC 2: cài đặt bot
        '<div class="cb-b" id="cbB2">' +
          '<div class="cb-tom" id="cbTom"></div>' +

          '<label>' + esc(window.t("cb.lb_ten")) + '</label>' +
          '<input id="cbName" value="' + esc(b ? b.name : "") + '" placeholder="' +
            esc(window.t("cb.ph_ten")) + '">' +

          '<label>' + esc(window.t("cb.lb_agent")) + '</label>' +
          '<div class="cb-row">' +
            '<select id="cbAgent">' + htmlAgent(agents, (b && (b.agent || {}).slug) || "") + '</select>' +
            '<button class="s-btn-ghost" id="cbNewAgent" type="button">' + ic("plus") + ' ' +
              esc(window.t("cb.tao_agent")) + '</button>' +
          '</div>' +
          '<div class="cb-hint">' + esc(window.t("cb.hint_agent_1")) + ' <b>' + esc(br) + '</b>' +
          esc(window.t("cb.hint_agent_2")) + ' <b>' + esc(window.t("cb.tao_agent")) + '</b> ' +
          esc(window.t("cb.hint_agent_3")) + '</div>' +

          '<label>' + esc(window.t("cb.lb_agent_phu")) + '</label>' +
          '<div class="cb-agent-phu" id="cbAgentPhu">' + htmlAgentPhu(agents, (b && b.agents_phu) || [],
            (b && (b.agent || {}).slug) || "") + '</div>' +
          '<div class="cb-hint">' + esc(window.t("cb.hint_agent_phu")) + '</div>' +

          '<label>' + esc(window.t("cb.lb_rieng")) + '</label>' +
          '<select id="cbRiengPhamVi">' +
            '<option value=""' + (!b || !b.rieng_pham_vi ? " selected" : "") + '>' + esc(window.t("cb.rieng_mac_dinh")) + '</option>' +
            '<option value="tat_ca"' + (b && b.rieng_pham_vi === "tat_ca" ? " selected" : "") + '>' + esc(window.t("cb.rieng_tat_ca")) + '</option>' +
            '<option value="chon"' + (b && b.rieng_pham_vi === "chon" ? " selected" : "") + '>' + esc(window.t("cb.rieng_chon")) + '</option>' +
          '</select>' +
          '<textarea id="cbRiengCho" rows="2" placeholder="' + esc(window.t("cb.ph_rieng_cho")) + '">' +
            esc(((b && b.rieng_cho_phep) || []).join("\n")) + '</textarea>' +
          '<div class="cb-db" id="cbDbRieng" data-loai="private" data-ta="cbRiengCho"></div>' +
          '<div class="cb-hint">' + esc(window.t("cb.hint_rieng")) + '</div>' +

          '<div class="cb-nk-khoi"><div class="cb-nk-tieude">' + esc(window.t("cb.nk_tieu_de")) + '</div>' +
            '<div class="cb-hint">' + esc(window.t("cb.nk_hint")) + '</div>' +
            '<div id="cbNhomKhach">' + ((b && b.nhom_khach) || []).map(function (n) { return htmlNhomThe(n, agents); }).join("") + '</div>' +
            '<button type="button" class="s-btn-ghost" id="cbThemNhom">' + ic("plus") + ' ' + esc(window.t("cb.nk_them")) + '</button>' +
            '<div id="cbNguoiLa">' + htmlNguoiLa(b && b.nguoi_la, agents) + '</div></div>' +

          '<div class="cb-nk-tieude">' + esc(window.t("cb.tv_tieu_de")) + '</div>' +
          '<div class="cb-hint">' + esc(window.t("cb.tv_hint")) + '</div>' +
          (sua ? '<div id="cbThuVien" class="cb-tv"></div>' +
                 '<label class="s-btn-ghost cb-tv-up">' + ic("plus") + ' ' + esc(window.t("cb.tv_tai_len")) +
                 '<input type="file" id="cbTvFile" multiple style="display:none" accept="image/*,video/mp4,video/quicktime,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.txt,.csv"></label>'
               : '<div class="cb-hint"><b>' + esc(window.t("cb.tv_luu_truoc")) + '</b></div>') +

          '<div class="cb-nk-tieude">' + esc(window.t("cb.nk_mac_dinh")) + '</div>' +
          '<label>' + esc(window.t("cb.lb_noi_duoc")) + '</label>' +
          '<textarea id="cbNoiDuoc" rows="3" placeholder="' + esc(window.t("cb.ph_noi_duoc")) + '">' +
            esc((b && b.noi_duoc) || "") + '</textarea>' +
          '<label>' + esc(window.t("cb.lb_noi_cam")) + '</label>' +
          '<textarea id="cbNoiCam" rows="3" placeholder="' + esc(window.t("cb.ph_noi_cam")) + '">' +
            esc((b && b.noi_cam) || "") + '</textarea>' +
          '<label>' + esc(window.t("cb.lb_tu_khoa")) + '</label>' +
          '<input id="cbTuKhoa" value="' + esc(((b && b.cam_tu_khoa) || []).join(", ")) + '" placeholder="' +
            esc(window.t("cb.ph_tu_khoa")) + '">' +
          '<label>' + esc(window.t("cb.lb_ngoai_pv")) + '</label>' +
          '<select id="cbNgoaiPV">' +
            '<option value="tu_choi"' + (!b || b.ngoai_pham_vi !== "im" ? " selected" : "") + '>' + esc(window.t("cb.npv_tu_choi")) + '</option>' +
            '<option value="im"' + (b && b.ngoai_pham_vi === "im" ? " selected" : "") + '>' + esc(window.t("cb.npv_im")) + '</option>' +
          '</select>' +
          '<div class="cb-hint">' + esc(window.t("cb.hint_pham_vi")) + '</div>' +

          // Lựa chọn này quyết định bot "ăn nhập với Agent" hay không, nên đặt ngay dưới Agent
          // chứ không giấu trong khối Cài đặt thêm: nó là thứ người dùng cần hiểu TRƯỚC khi
          // bấm tạo.
          '<label>' + esc(window.t("cb.lb_nguon")) + '</label>' +
          '<select id="cbNguon">' +
            '<option value="agent"' + (!b || b.nguon_tra_loi !== "tai_lieu" ? " selected" : "") + '>' +
              esc(window.t("cb.nguon_agent")) + '</option>' +
            '<option value="tai_lieu"' + (b && b.nguon_tra_loi === "tai_lieu" ? " selected" : "") + '>' +
              esc(window.t("cb.nguon_tai_lieu")) + '</option>' +
          '</select>' +
          '<div class="cb-hint"><b>' + esc(window.t("cb.nguon_agent_b")) + '</b>' +
          esc(window.t("cb.hint_nguon_1")) + '<br>' +
          '<b>' + esc(window.t("cb.nguon_tl_b")) + '</b>' + esc(window.t("cb.hint_nguon_2")) + '</div>' +

          // Mức quyền KHÔNG bao giờ nằm trong khối gấp lại: đây là quyết định nặng nhất trong
          // cả form, phải đọc trước khi bấm tạo chứ không phải một ô phải bấm mới thấy.
          '<label>' + esc(window.t("cb.lb_muc")) + '</label>' +
          '<select id="cbMuc">' + htmlMuc((b && b.muc_quyen) || "suggest") + '</select>' +
          '<div class="cb-muc-note">' + veCanhBao((b && b.muc_quyen) || "suggest") + '</div>' +

          // Ba thứ còn lại gấp vào đây vì đều có mặc định dùng được ngay: ngôn ngữ tự nhận,
          // không chuyển người thật, chưa khai nhóm nào. Ai cần mới mở.
          '<details class="cb-nangcao">' +
            '<summary>' + ic("settings") + ' ' + esc(window.t("cb.nang_cao")) + '</summary>' +

            // Ngôn ngữ của bot ĐỘC LẬP với ngôn ngữ của chủ, và đó là cả lý do ô này tồn tại:
            // bot nói chuyện với NGƯỜI NGOÀI, không phải với chủ. Chủ dùng Javis bằng tiếng
            // Việt mà người nhắn cho bot lại nói tiếng khác là chuyện bình thường, nên lấy
            // ngôn ngữ của chủ suy ra ngôn ngữ của bot là suy sai.
            '<label>' + esc(window.t("cb.lb_ngon_ngu")) + '</label>' +
            '<select id="cbNgonNgu">' + htmlNgonNgu((b && b.ngon_ngu) || "auto") + '</select>' +
            '<div class="cb-muc-note">' + esc(window.t("cb.hint_ngon_ngu")) + '</div>' +

            '<label>' + esc(window.t("cb.lb_handoff")) + '</label>' +
            '<input id="cbHandoff" value="' + esc(b ? (b.handoff_to || "") : "") + '" placeholder="' +
              esc(window.t("cb.ph_handoff")) + '">' +
            '<div class="cb-hint">' + esc(window.t("cb.hint_ho_1")) + ' <b>' +
            esc(window.t("cb.hint_ho_hai_cau")) + '</b> ' + esc(window.t("cb.hint_ho_2")) + '<br>' +
            esc(window.t("cb.hint_ho_3")) + ' <b>' + esc(window.t("cb.hint_ho_binh_thuong")) + '</b> ' +
            esc(window.t("cb.hint_ho_4")) + ' <b>' + esc(window.t("cb.nguon_tl_b")) + '</b> ' +
            esc(window.t("cb.hint_ho_5")) + '</div>' +

            // Khai được NGAY LÚC TẠO, không chỉ ở form Sửa. Đường đi tự nhiên nhất là tạo bot
            // rồi thả thẳng vào nhóm; bắt quay lại bấm Sửa mới khai được nhóm là bảo đảm lần
            // thử đầu tiên của mọi người dùng đều gặp một con bot im lặng.
            // Cả khối nhóm ẩn đi với kênh không vào được nhóm. Hiện ra rồi để nó không có tác
            // dụng là hứa suông: người dùng ngồi khai id nhóm xong chờ mãi một con bot không
            // bao giờ vào được nhóm nào, và không có gì nói cho họ biết.
            '<div id="cbNhomBox">' +
              '<label>' + esc(window.t("cb.lb_nhom")) + '</label>' +
              '<textarea id="cbGroups" rows="2" placeholder="' + esc(window.t("cb.ph_nhom")) + '">' +
                esc(((b && b.groups) || []).join("\n")) + '</textarea>' +
              '<div class="cb-db" id="cbDbNhom" data-loai="group" data-ta="cbGroups"></div>' +
              '<div class="cb-hint">' + esc(window.t("cb.hint_ho_3")) + ' <b>' +
              esc(window.t("cb.hint_nhom_rieng")) + '</b>' + esc(window.t("cb.hint_nhom_1")) +
              ' <b>' + esc(window.t("cb.cho_phep")) + '</b>' + esc(window.t("cb.hint_nhom_2")) +
              ' <b>/id</b> ' + esc(window.t("cb.hint_nhom_3")) + '</div>' +

              '<label>' + esc(window.t("cb.lb_reply_when")) + '</label>' +
              '<select id="cbReplyWhen">' +
                '<option value="mention"' + (!b || b.reply_when !== "always" ? " selected" : "") + '>' +
                  esc(window.t("cb.rw_mention")) + '</option>' +
                '<option value="always"' + (b && b.reply_when === "always" ? " selected" : "") + '>' +
                  esc(window.t("cb.rw_always")) + '</option>' +
                '<option value="judge"' + (b && b.reply_when === "judge" ? " selected" : "") + '>' +
                  esc(window.t("cb.rw_judge")) + '</option>' +
              '</select>' +
              '<div class="cb-hint"><b>' + esc(window.t("cb.rw_moi_tin")) + '</b> ' +
              esc(window.t("cb.hint_rw_1")) + '<b>/setprivacy</b> ' +
              esc(window.t("cb.hint_rw_2")) + '</div>' +
            '</div>' +
            '<div class="cb-hint cb-khong-nhom" id="cbKhongNhom" style="display:none">' +
              esc(window.t("cb.khong_nhom_1")) + ' <b>' + esc(window.t("cb.hint_nhom_rieng")) + '</b>' +
              esc(window.t("cb.khong_nhom_2")) + '</div>' +
          '</details>' +
        '</div>' +

        '<div class="cb-form-acts">' +
          '<button class="s-btn-ghost" id="cbLui" type="button"></button>' +
          '<button class="s-btn" id="cbTien" type="button"></button>' +
        '</div>' +
        (sua ? "" : '<div class="cb-hint" id="cbTaoXong">' + esc(window.t("cb.tao_xong_1")) + ' <b>' +
                    esc(window.t("cb.tao_xong_tat")) + '</b>' +
                    esc(window.t("cb.tao_xong_2")) + '</div>') +
      '</div></div>');

    document.body.appendChild(box);
    var dong = function () { if (box.parentNode) box.parentNode.removeChild(box); };
    box.onmousedown = function (e) { if (e.target === box) dong(); };

    // Sang thẳng trang Cộng sự. Đóng form trước để quay lại không bị hai lớp modal chồng nhau.
    box.querySelector("#cbNewAgent").onclick = function () {
      dong();
      try { window.JavisNav.go("workspace"); } catch (e) {}
    };

    // Đổi mức là vẽ lại cảnh báo NGAY, và ô đồng ý luôn bắt đầu ở trạng thái chưa tick. Giữ
    // lại tick cũ khi đổi từ "Được ghi" sang "Toàn quyền" là để chủ đồng ý với một danh sách
    // rủi ro mà họ chưa đọc.
    var oMuc = box.querySelector("#cbMuc");
    var oNote = box.querySelector(".cb-muc-note");
    oMuc.onchange = function () { oNote.innerHTML = veCanhBao(oMuc.value); };

    // Khối nhóm chỉ hiện khi CÓ tài khoản đứng được trong nhóm. Hiện ra rồi để nó không có tác
    // dụng là hứa suông: người dùng ngồi khai id nhóm xong chờ mãi một con bot không bao giờ
    // vào được nhóm nào.
    function tkDangChon() {
      return Array.prototype.slice.call(box.querySelectorAll(".cb-tk-o:checked")).map(function (n) {
        return { id: n.value, channel: n.dataset.k, ten: n.dataset.ten || "" };
      });
    }
    function coNhomForm() {
      return tkDangChon().some(function (a) { return kenhCua(a.channel).co_nhom; });
    }
    function apNhom() {
      var co = coNhomForm();
      var nhomBox = box.querySelector("#cbNhomBox");
      var khong = box.querySelector("#cbKhongNhom");
      if (nhomBox) nhomBox.style.display = co ? "" : "none";
      if (khong) khong.style.display = co ? "none" : "";
    }

    // Chọn người/nhóm từ DANH BẠ Zalo (tìm theo tên, tích chọn) thay vì chép id tay. Ô chữ id vẫn là
    // nguồn dữ liệu thật; bảng này chỉ thêm/bớt dòng trong đó.
    var _tenDb = {};
    function zaloDangChon() {
      var a = tkDangChon().filter(function (x) { return x.channel === "zalo_personal"; })[0];
      return a ? a.id : "";
    }
    function veDanhBa(host) {
      var ta = box.querySelector("#" + host.getAttribute("data-ta"));
      var loai = host.getAttribute("data-loai");
      var aid = zaloDangChon();
      if (!aid) { host.style.display = "none"; host.innerHTML = ""; return; }
      host.style.display = "";
      if (host.getAttribute("data-aid") === aid && host.firstChild) return;
      host.setAttribute("data-aid", aid);
      host.innerHTML =
        '<button type="button" class="s-btn-ghost cb-db-mo">' + esc(window.t(loai === "group" ? "cb.db_chon_nhom" : "cb.db_chon_nguoi")) + '</button>' +
        '<div class="cb-db-panel" style="display:none">' +
          '<input class="cb-db-q" placeholder="' + esc(window.t("cb.db_tim")) + '">' +
          '<div class="cb-db-ds"></div></div>';
      var panel = host.querySelector(".cb-db-panel"), ds = host.querySelector(".cb-db-ds");
      var q = host.querySelector(".cb-db-q"), hen = null, seq = 0;
      function idsHienCo() {
        return ta.value.split(/[\s,;]+/).filter(Boolean);
      }
      function datIds(arr) { ta.value = arr.join("\n"); }
      function ve(items) {
        var co = idsHienCo();
        var thieu = co.filter(function (i) { return !items.some(function (x) { return x.id === i; }); })
          .map(function (i) { return { id: i, name: _tenDb[i] || "", type: loai }; });
        var all = thieu.concat(items);
        ds.innerHTML = all.length ? all.map(function (x) {
          _tenDb[x.id] = x.name || _tenDb[x.id] || "";
          return '<label class="cb-chk cb-db-dong"><input type="checkbox" value="' + esc(x.id) + '"' +
            (co.indexOf(x.id) >= 0 ? " checked" : "") + '> <span>' + esc(x.name || x.id) + '</span> ' +
            (loai ? "" : '<em>' + esc(window.t(x.type === "group" ? "cb.db_nhom" : "cb.db_ca_nhan")) + '</em>') + '</label>';
        }).join("") : '<div class="cb-hint">' + esc(window.t("cb.db_trong")) + '</div>';
        Array.prototype.forEach.call(ds.querySelectorAll("input"), function (o) {
          o.onchange = function () {
            var cur = idsHienCo().filter(function (i) { return i !== o.value; });
            if (o.checked) cur.push(o.value);
            datIds(cur);
          };
        });
      }
      async function tai() {
        var my = ++seq;
        ds.innerHTML = '<div class="cb-hint">' + esc(window.t("cb.db_dang_tai")) + '</div>';
        try {
          var d = await api("/chatbots/danh-ba?account_id=" + encodeURIComponent(aid) + "&loai=" + loai +
                            "&q=" + encodeURIComponent(q.value || ""));
          if (my === seq) ve(d.items || []);
        } catch (e) {
          if (my === seq) ds.innerHTML = '<div class="cb-warn">' + esc(e.message) + '</div>';
        }
      }
      host.querySelector(".cb-db-mo").onclick = function () {
        var mo = panel.style.display === "none";
        panel.style.display = mo ? "" : "none";
        if (mo) tai();
      };
      q.oninput = function () { clearTimeout(hen); hen = setTimeout(tai, 350); };
    }
    function noiNhom() {
      Array.prototype.forEach.call(box.querySelectorAll(".nk-xoa"), function (n) {
        n.onclick = function () { var the = n.closest(".cb-nk"); if (the) the.remove(); };
      });
      veMoiDanhBa();
    }
    // Thư viện file gửi khách: chỉ khi SỬA bot (bot mới chưa có id để gắn file).
    async function taiThuVien() {
      var ds = box.querySelector("#cbThuVien");
      if (!ds || !b) return;
      try {
        var d = await api("/chatbots/" + encodeURIComponent(b.id) + "/thu-vien");
        ds.innerHTML = (d.items || []).length ? d.items.map(function (x) {
          return '<div class="cb-tv-dong"><span>' + esc(x.name) + ' <em>' + Math.max(1, Math.round(x.size / 1024)) + ' KB</em></span>' +
            '<button type="button" class="s-btn-ghost cb-tv-xoa" data-n="' + esc(x.name) + '">' + esc(window.t("cb.nk_xoa")) + '</button></div>';
        }).join("") : '<div class="cb-hint">' + esc(window.t("cb.tv_trong")) + '</div>';
        Array.prototype.forEach.call(ds.querySelectorAll(".cb-tv-xoa"), function (n) {
          n.onclick = async function () {
            if (!confirm(window.t("cb.tv_xac_nhan_xoa"))) return;
            try { await api("/chatbots/" + encodeURIComponent(b.id) + "/thu-vien/xoa", { method: "POST", body: fd({ ten: n.getAttribute("data-n") }) }); } catch (e) { alert(e.message); }
            taiThuVien();
          };
        });
      } catch (e) { ds.innerHTML = '<div class="cb-warn">' + esc(e.message) + '</div>'; }
    }
    var fTv = box.querySelector("#cbTvFile");
    if (fTv) fTv.onchange = async function () {
      for (var i = 0; i < fTv.files.length; i++) {
        var f = new FormData(); f.append("file", fTv.files[i]);
        try { await api("/chatbots/" + encodeURIComponent(b.id) + "/thu-vien", { method: "POST", body: f }); }
        catch (e) { alert(fTv.files[i].name + ": " + e.message); }
      }
      fTv.value = "";
      taiThuVien();
    };
    taiThuVien();
    var nutThem = box.querySelector("#cbThemNhom");
    if (nutThem) nutThem.onclick = function () {
      var ds = box.querySelectorAll("#cbNhomKhach .cb-nk");
      if (ds.length >= 12) return alert(window.t("cb.nk_toi_da"));
      var d = document.createElement("div");
      d.innerHTML = htmlNhomThe({ ten: "", bat: true }, agents);
      box.querySelector("#cbNhomKhach").appendChild(d.firstChild);
      noiNhom();
    };
    function docNhom() {
      return Array.prototype.map.call(box.querySelectorAll("#cbNhomKhach .cb-nk"), function (el) {
        var o = docPhamVi(el);
        o.id = el.getAttribute("data-id") || "";
        o.ten = (el.querySelector(".nk-ten") || {}).value || "";
        o.bat = !!(el.querySelector(".nk-bat") || {}).checked;
        o.thanh_vien = (el.querySelector(".nk-tv") || {}).value || "";
        return o;
      });
    }
    function docNguoiLa() {
      var el = box.querySelector("#cbNguoiLa .cb-nk");
      if (!el) return {};
      var o = docPhamVi(el);
      var v = (el.querySelector(".nl-bat") || {}).value;
      o.bat = v === "" ? null : v === "1";
      return o;
    }
    function veMoiDanhBa() {
      Array.prototype.forEach.call(box.querySelectorAll(".cb-db"), veDanhBa);
    }

    // Dòng tóm tắt ở đầu bước 2: bot này sẽ trả lời ở đâu, và lối quay lại đổi. Không có nó thì
    // sang bước 2 là mất dấu lựa chọn vừa làm.
    function veTom() {
      var t = box.querySelector("#cbTom");
      if (!t) return;
      var ds = tkDangChon();
      t.innerHTML = '<span class="cb-tom-l">' + esc(window.t("cb.tra_loi_o")) + '</span> ' +
        (ds.length ? ds.map(function (a) {
          return '<span class="cb-kenh-chip">' + logoKenh(a.channel) + " " + esc(a.ten) + "</span>";
        }).join(" ") : '<span class="cb-warn">' + esc(window.t("cb.chua_chon_tk")) + '</span>') +
        ' <button type="button" class="cb-doi-tk">' + esc(window.t("cb.doi")) + '</button>';
      var nut = t.querySelector(".cb-doi-tk");
      if (nut) nut.onclick = function () { veBuoc(1); };
    }

    // Nối lại sự kiện cho danh sách tài khoản: nó được vẽ lại sau mỗi lần nối kênh mới.
    function noiTK() {
      box.querySelectorAll(".cb-tk-o").forEach(function (n) {
        n.onchange = function () { apNhom(); veTom(); veMoiDanhBa(); };
      });
      apNhom();
      veTom();
      veMoiDanhBa();
      noiNhom();
    }
    noiTK();

    box.querySelector(".cb-noi-kenh").onclick = function () {
      noiKenhMoi(function (aid) {
        var giu = tkDangChon().map(function (a) { return a.id; });
        if (aid) giu.push(aid);
        box.querySelector("#cbTkBox").innerHTML = veChonTK(b, giu, true);
        noiTK();
      });
    };

    // Hai nút ở chân form đổi vai theo bước. Một cặp nút cố định đọc dễ hơn hai hàng nút hiện
    // ra rồi biến đi, và trên điện thoại nó luôn nằm đúng một chỗ.
    function veBuoc(n) {
      buoc = n;
      box.querySelector("#cbB1").style.display = n === 1 ? "" : "none";
      box.querySelector("#cbB2").style.display = n === 2 ? "" : "none";
      var nhan = box.querySelector("#cbBuoc");
      if (nhan) nhan.textContent = window.t("cb.buoc_may", { n: n });
      // Form TẠO mở ở bước 1, form SỬA mở thẳng bước 2, nên nút trái đóng form ở bước khởi
      // đầu và lùi một bước ở bước kia. Không phân biệt thì ở form Sửa, bấm nút trái sau khi
      // ghé bước 1 qua "Đổi" là vứt hết những gì vừa sửa ở bước 2.
      var luiLaDong = sua ? n === 2 : n === 1;
      box.querySelector("#cbLui").textContent = luiLaDong ? window.t("common.cancel")
                                                          : window.t("cb.quay_lai");
      box.querySelector("#cbLui").onclick = luiLaDong ? dong : function () { veBuoc(sua ? 2 : 1); };
      box.querySelector("#cbTien").textContent = n === 1 ? window.t("cb.tiep_tuc")
                                                         : (sua ? window.t("common.save") : window.t("cb.tao_bot"));
      var xong = box.querySelector("#cbTaoXong");
      if (xong) xong.style.display = n === 2 ? "" : "none";
      if (n === 2) veTom();
      box.querySelector(".cb-form").scrollTop = 0;
    }
    box.querySelector("#cbTien").onclick = function () { if (buoc === 1) sangBuoc2(); else luu(); };
    veBuoc(buoc);

    // Không có tài khoản nào thì bước 2 vô nghĩa: bot tạo ra không có chỗ nào để trả lời.
    function sangBuoc2() {
      if (!tkDangChon().length) return alert(window.t("cb.chon_tai_khoan"));
      var ten = box.querySelector("#cbName");
      // Gợi tên từ tài khoản vừa chọn: gõ lại đúng cái tên vừa đọc ở bước trước là việc thừa.
      if (!ten.value.trim()) ten.value = (tkDangChon()[0] || {}).ten || "";
      veBuoc(2);
    }

    async function luu() {
      var ten = box.querySelector("#cbName").value.trim();
      var ag = box.querySelector("#cbAgent").value;
      var ho = box.querySelector("#cbHandoff").value.trim();
      var ngu = box.querySelector("#cbNguon").value;
      var muc = oMuc.value;
      var ack = box.querySelector("#cbAck");
      var ids = tkDangChon().map(function (a) { return a.id; });
      if (!ids.length) { veBuoc(1); return alert(window.t("cb.chon_tai_khoan")); }
      if (!ten) return alert(window.t("cb.nhap_ten"));
      if (!ag) return alert(window.t("cb.chon_agent"));
      // Hai lớp, cố ý: ô tick ở đây để chủ ĐỌC, và server vẫn tự chặn lần nữa (can_force) nên
      // gỡ ô này bằng devtools cũng không nâng được quyền.
      if (mucCua(muc).can_xac_nhan && !(ack && ack.checked)) {
        return alert(window.t("cb.can_ack", { muc: mucCua(muc).nhan }));
      }
      if (muc === "full" && !confirm(window.t("cb.xn_full", { ten: ten }))) return;
      // Không tài khoản nào đứng được trong nhóm thì gửi rỗng, đừng gửi thứ người dùng gõ
      // lúc còn tích tài khoản khác: bản ghi mang một danh sách nhóm không bao giờ dùng tới
      // là một lời hứa suông nằm lại trong dữ liệu.
      var coNhomLuu = coNhomForm();
      var gr = coNhomLuu ? box.querySelector("#cbGroups").value : "";
      var rw = coNhomLuu ? box.querySelector("#cbReplyWhen").value : "mention";
      var chung = { name: ten, agent_slug: ag, agent_brain: br, brain: br,
                    handoff_to: ho, nguon_tra_loi: ngu, muc_quyen: muc, xac_nhan_rui_ro: "1",
                    ngon_ngu: (document.getElementById("cbNgonNgu") || {}).value || "auto",
                    groups: gr, reply_when: rw, account_ids: ids.join(","),
                    agents_phu: Array.prototype.map.call(box.querySelectorAll(".cbAgentPhuCk:checked"),
                      function (x) { return x.value; }).filter(function (x) { return x !== ag; }).join(","),
                    rieng_pham_vi: (box.querySelector("#cbRiengPhamVi") || {}).value || "",
                    rieng_cho_phep: ((box.querySelector("#cbRiengCho") || {}).value || ""),
                    nhom_khach: JSON.stringify(docNhom()), nguoi_la: JSON.stringify(docNguoiLa()),
                    noi_duoc: (box.querySelector("#cbNoiDuoc") || {}).value || "",
                    noi_cam: (box.querySelector("#cbNoiCam") || {}).value || "",
                    cam_tu_khoa: (box.querySelector("#cbTuKhoa") || {}).value || "",
                    ngoai_pham_vi: (box.querySelector("#cbNgoaiPV") || {}).value || "tu_choi" };
      try {
        if (sua) {
          await api("/chatbots/" + encodeURIComponent(b.id) + "/update", { method: "POST", body: fd(chung) });
        } else {
          await api("/chatbots", { method: "POST", body: fd(chung) });
        }
      } catch (e) { return alert(window.t("cb.loi_luu") + " " + e.message); }
      dong();
      tai();
    }
  }

  // Tab Kênh bấm "Tạo bot trực" trên một tài khoản: mở form với tài khoản đó tích sẵn. Đợi
  // trang nạp xong danh sách kênh (tai) rồi mới mở, để ô chọn có đủ dữ liệu.
  document.addEventListener("javis:chatbot-new", function (e) {
    var aid = (e.detail || {}).account_id;
    doiNap(function () { moForm(null, { account_id: aid }); });
  });

  // (0.62.2 đã bỏ tay bắt "javis:chatbot-edit" ở đây. Tab Kênh từng bấm Xoá là nhảy sang đây
  // mở form Sửa của con bot đang giữ tài khoản, nhưng trang này chỉ nạp bot của BRAIN ĐANG MỞ
  // còn tài khoản kênh thì toàn cục - nên với con bot ở brain khác, đường đó luôn kết thúc
  // bằng câu "đổi brain rồi thử lại" mà không nói đổi sang brain nào. Nay tab Tài khoản bot tự gỡ tài
  // khoản khỏi bot rồi xoá trong một lần hỏi, không phải đi vòng qua trang này nữa.)

  // Đợi trang nạp xong (kênh + danh sách bot) rồi mới mở form, để ô chọn có đủ dữ liệu. Bỏ cuộc
  // sau 3 giây: mở một form thiếu dữ liệu vẫn hơn là không mở gì và không nói gì.
  function doiNap(xong) {
    var cho = 0;
    (function thu() {
      if ((_kenhDS.length && _bots) || cho++ > 20) return xong();
      setTimeout(thu, 150);
    })();
  }

  window.JavisChatbots = { render: render };
})();
