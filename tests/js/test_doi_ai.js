/* Khu "Đội AI" trên Bảng việc (phương án 1 "Dòng việc theo job", plans/doi-ai-gate Phase 04).

       node tests/js/test_doi_ai.js

   Nạp dashboard/doi-ai.js trong vm với window.t thật (từ vi.json) và gọi hàm dựng HTML thuần
   `window.MinMinDoiAi._html(data, state)` - không cần DOM.

   Những gì file này khoá lại (hợp đồng `jobs_view` / `gate_action` ở PLAN.md):
   1. Job cho_duyet có khung "Bạn sắp cho phép" + 3 nút mang đúng job_id và action.
   2. Job ket hiện block_reason của bước kẹt.
   3. Job xong/dung gom vào dòng "Xong hôm nay", không có thẻ riêng.
   4. Lọc đội; rỗng là câu trấn an + nút Giao.
   5. Chuỗi từ máy chủ bị escape.
   6. doi-ai.css chỉ dùng token (cùng luật test_design_tokens.py).
   7. Tự làm mới KHÔNG vẽ lại khi đang gõ trong ô của khu.
*/
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..", "..");
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");
const VI = JSON.parse(read("dashboard/i18n/vi.json"));
const EN = JSON.parse(read("dashboard/i18n/en.json"));
const SRC = read("dashboard/doi-ai.js");
const CSS = read("dashboard/doi-ai.css");

let fails = [];
function check(name, cond, extra) {
  console.log((cond ? "ok   " : "FAIL ") + name + (cond || extra === undefined ? "" : "  [" + extra + "]"));
  if (!cond) fails.push(name);
}

function t(k, b) {
  const v = VI[k];
  if (v == null) return k;
  return String(v).replace(/\{(\w+)\}/g, (m, n) => (b && b[n] != null ? String(b[n]) : m));
}
const win = { t };
vm.runInNewContext(SRC, { window: win, document: {}, console, Intl, Date, Math, String, Array, Object, JSON, isNaN, isFinite, encodeURIComponent });
const DA = win.MinMinDoiAi;
check("export window.MinMinDoiAi.render và _html", DA && typeof DA.render === "function" && typeof DA._html === "function");

const NOW = new Date(2026, 9, 26, 15, 0, 0);
const homNay = (h, m) => new Date(2026, 9, 26, h, m, 0).toISOString();
const S = (o) => Object.assign({ now: NOW }, o || {});
const dem = (s, sub) => s.split(sub).length - 1;

// ---------------------------------------------------------------- dữ liệu mẫu (jobs_view)
const JOB_CHO = {
  id: "job-ads-1", title: "Lên camp Váy lụa 25/10", doi: "ads", status: "cho_duyet",
  created_at: homNay(8, 12), chat_id: "web:abc",
  buoc: [
    { task_id: "t1", title: "Nghiên cứu mẫu + đối thủ", loai: "buoc", status: "done", ket_qua_ngan: "", block_reason: "" },
    { task_id: "t2", title: "Viết 3 mẫu content", loai: "buoc", status: "done", ket_qua_ngan: "", block_reason: "" },
    { task_id: "g1", title: "bạn duyệt", loai: "gate", status: "blocked", ket_qua_ngan: "", block_reason: "" },
    { task_id: "t4", title: "Bật camp, bắt đầu chi tiền", loai: "buoc", status: "todo", ket_qua_ngan: "", block_reason: "" },
  ],
  gate_cho: { task_id: "g1", mo_ta: "Bật 1 chiến dịch, ngân sách 1.500.000đ/ngày", xem_truoc: "Content mẫu 1\nLụa mát, dáng suông", mo_khoa: ["t4"] },
};
const JOB_CHAY = {
  id: "job-ads-2", title: "Tối ưu camp tuần 43", doi: "ads", status: "dang_chay", created_at: homNay(9, 0),
  buoc: [
    { task_id: "a1", title: "Kéo số 7 ngày", loai: "buoc", status: "done" },
    { task_id: "a2", title: "Chấm điểm từng camp", loai: "buoc", status: "running" },
    { task_id: "a3", title: "duyệt đề xuất", loai: "gate", status: "todo" },
    { task_id: "a4", title: "Tắt camp lỗ", loai: "buoc", status: "todo" },
  ],
  gate_cho: null,
};
const JOB_KET = {
  id: "job-social-1", title: "6 bài fanpage HALIMI", doi: "social", status: "ket", created_at: homNay(7, 0),
  buoc: [
    { task_id: "s1", title: "Soạn 6 bài + chọn ảnh", loai: "buoc", status: "blocked", block_reason: "Thiếu ảnh sản phẩm trong thư mục" },
    { task_id: "s2", title: "duyệt mẫu", loai: "gate", status: "todo" },
    { task_id: "s3", title: "Đăng giờ vàng", loai: "buoc", status: "todo" },
  ],
  gate_cho: null,
};
const JOB_XONG = { id: "job-xong-1", title: "Báo cáo ngày 25/10", doi: "ads", status: "xong", created_at: homNay(6, 0), updated_at: homNay(6, 30),
  buoc: [{ task_id: "x1", title: "Báo cáo", loai: "buoc", status: "done" }], gate_cho: null };
const JOB_DUNG = { id: "job-dung-1", title: "Job bị từ chối", doi: "khac", status: "dung", created_at: homNay(5, 0),
  buoc: [{ task_id: "y1", title: "Bước", loai: "buoc", status: "cancelled" }], gate_cho: null };
const DU = { jobs: [JOB_CHAY, JOB_KET, JOB_CHO, JOB_XONG, JOB_DUNG] };

const h = DA._html(DU, S());
check("tiêu đề khu 'Đội AI' cỡ h2, không có h1 trang", h.includes('<h2 class="da-h2">Đội AI</h2>') && !h.includes("<h1"));
check("dòng phụ đếm 1 job chờ GATE", h.includes("1 job đang dừng ở GATE chờ bạn"));
check("có 3 chip lọc + nút Giao việc", h.includes('data-loc="tat_ca"') && h.includes('data-loc="ads"') && h.includes('data-loc="social"') && h.includes(">+ Giao việc cho đội<"));
check("job chờ duyệt xếp lên đầu", h.indexOf('data-job="job-ads-1"') < h.indexOf('data-job="job-social-1"') && h.indexOf('data-job="job-social-1"') < h.indexOf('data-job="job-ads-2"'));

// 1. cho_duyet
check("job cho_duyet có khung 'Bạn sắp cho phép'", dem(h, "Bạn sắp cho phép") === 1 && h.includes('class="da-cho-phep"'));
check("nhãn 'Chờ bạn duyệt' class warn (cho_duyet)", h.includes('<span class="da-tt cho_duyet">Chờ bạn duyệt</span>'));
for (const a of ["duyet", "sua", "tu_choi"]) {
  check("nút " + a + " mang job_id + action", h.includes('data-da="gate" data-action="' + a + '" data-job="job-ads-1"'));
}
check("mở khoá bước -> chữ 'Duyệt và cho chạy thật'", h.includes(">Duyệt và cho chạy thật<"));
const hKhongMoKhoa = DA._html({ jobs: [Object.assign({}, JOB_CHO, { gate_cho: Object.assign({}, JOB_CHO.gate_cho, { mo_khoa: [] }) })] }, S());
check("không mở khoá -> chữ 'Duyệt'", hKhongMoKhoa.includes('data-action="duyet" data-job="job-ads-1">Duyệt<'));
check("mọi nút là button type=button", !/<button(?![^>]*type="button")/.test(h));
check("ô ghi chú có label thật nối id", /<label class="da-nhan" for="da-ghi-job-ads-1">/.test(h) && h.includes('id="da-ghi-job-ads-1"'));
check("xem trước giữ xuống dòng", h.includes("Content mẫu 1\nLụa mát") && /\.da-xem-truoc \{[^}]*white-space: pre-wrap/.test(CSS));
check("ô GATE đang chờ có icon khoá svg + 'GATE · bạn duyệt'", /da-buoc-gate cho[^>]*><svg class="da-khoa"[^>]*stroke="currentColor"/.test(h) && h.includes("GATE · bạn duyệt"));
check("bước done có class xong, bước chưa tới class chua", h.includes('<li class="da-buoc xong"') && h.includes('<li class="da-buoc chua"'));
check("bước đang chạy class chay", h.includes('<li class="da-buoc chay"'));
check("các bước nối bằng vạch", dem(h, 'class="da-noi"') >= 3);
check("dòng phụ thời gian 'giao lúc 08:12'", h.includes("giao lúc 08:12"));
check("badge đội: Đội Ads / Đội Social", h.includes('<span class="da-doi ads">Đội Ads</span>') && h.includes('<span class="da-doi social">Đội Social</span>'));

// xem thêm khi xem trước dài
const dai = "x ".repeat(400);
const hDai = DA._html({ jobs: [Object.assign({}, JOB_CHO, { gate_cho: Object.assign({}, JOB_CHO.gate_cho, { xem_truoc: dai }) })] }, S());
check("xem trước dài bị cắt + nút 'xem thêm'", hDai.includes(">xem thêm<") && !hDai.includes(dai.trim()));
const hDaiMo = DA._html({ jobs: [Object.assign({}, JOB_CHO, { gate_cho: Object.assign({}, JOB_CHO.gate_cho, { xem_truoc: dai }) })] }, S({ moRong: { "job-ads-1": true } }));
check("bấm xem thêm thì hiện đủ + 'thu gọn'", hDaiMo.includes(">thu gọn<") && hDaiMo.includes(dai));

// state: đang gửi khoá nút, lỗi hiện dưới nút, ghi chú giữ lại
const hGui = DA._html(DU, S({ guiGate: { "job-ads-1": "duyet" }, loiGate: {}, ghiChu: { "job-ads-1": "nhớ đổi ảnh" } }));
check("đang gửi: cả 3 nút disabled", dem(hGui, 'data-job="job-ads-1" disabled') === 3);
check("ghi chú đang gõ được điền lại khi vẽ", hGui.includes(">nhớ đổi ảnh</textarea>"));
const hLoi = DA._html(DU, S({ loiGate: { "job-ads-1": "HTTP 500" } }));
check("lỗi gate hiện trong khung nút", /data-action="tu_choi"[\s\S]*?<div class="da-loi" role="alert">HTTP 500<\/div>/.test(hLoi));

// 2. ket
check("job ket hiện nhãn 'Kẹt' + lý do bước kẹt", h.includes('<span class="da-tt ket">Kẹt</span>') && h.includes("Kẹt ở bước Soạn 6 bài + chọn ảnh: Thiếu ảnh sản phẩm trong thư mục"));
check("job ket không có khung cho phép", !/data-job="job-social-1"[^]*?da-cho-phep[^]*?<\/article>/.test(h.slice(h.indexOf('data-job="job-social-1"'), h.indexOf("</article>", h.indexOf('data-job="job-social-1"')) + 10)));
check("job dang_chay nhãn 'Đang chạy'", h.includes('<span class="da-tt dang_chay">Đang chạy</span>'));

// 3. xong/dung gom cuối
check("job xong/dung không có thẻ riêng", !h.includes('<article class="da-the" data-job="job-xong-1"') && !h.includes('<article class="da-the" data-job="job-dung-1"'));
check("dòng 'Xong hôm nay' gom job xong ở cuối", /Xong hôm nay:<\/b> Báo cáo ngày 25\/10/.test(h) && h.lastIndexOf("</article>") < h.indexOf("Xong hôm nay"));
check("có nút 'Xem lịch sử'", h.includes('data-da="lich_su"') && h.includes(">Xem lịch sử<"));
const hLs = DA._html(DU, S({ moLichSu: true }));
check("mở lịch sử liệt kê cả job xong và đã dừng", hLs.includes("da-lich-su") && hLs.includes("Báo cáo ngày 25/10") && hLs.includes("Job bị từ chối") && hLs.includes('<span class="da-tt dung">Đã dừng</span>'));

// 4. lọc + rỗng
const hSocial = DA._html(DU, S({ loc: "social" }));
check("lọc Đội Social: chỉ job social", hSocial.includes('data-job="job-social-1"') && !hSocial.includes('data-job="job-ads-1"') && !hSocial.includes('data-job="job-ads-2"'));
check("chip đang lọc aria-pressed=true", hSocial.includes('data-loc="social" aria-pressed="true"') && hSocial.includes('data-loc="tat_ca" aria-pressed="false"'));
const hAds = DA._html(DU, S({ loc: "ads" }));
check("lọc Đội Ads: không có job social", !hAds.includes('data-job="job-social-1"') && hAds.includes('data-job="job-ads-1"'));
const hRong = DA._html({ jobs: [] }, S());
check("rỗng: câu trấn an + nút Giao", hRong.includes("Chưa có job nào. Giao việc cho một đội để bắt đầu.") && dem(hRong, 'data-da="mo_form"') === 2);
check("dữ liệu hỏng (null) không ném lỗi, ra rỗng", DA._html(null, S()).includes("Chưa có job nào."));

// form giao việc
const MAU = DA._dsMau({ mau: [{ id: "ads-len-camp", ten: "Đội Ads: lên camp", doi: "ads" }] });
check("danh sách mẫu luôn có 'tu-ke-buoc'", MAU.some((m) => m.id === "tu-ke-buoc") && MAU[0].id === "ads-len-camp");
const hForm = DA._html(DU, S({ moForm: true, mau: MAU, form: { mau: "tu-ke-buoc", muc_tieu: "abc", buoc: "", loi: "Lỗi thử", dangGui: false } }));
check("form: select mẫu + textarea mục tiêu có label", hForm.includes('<label class="da-nhan" for="da-mau">') && hForm.includes('<label class="da-nhan" for="da-muc-tieu">Mục tiêu</label>'));
check("mẫu tự kê bước hiện ô 'Các bước'", hForm.includes('id="da-buoc"'));
check("lỗi form hiện ngay trong form", hForm.includes('<div class="da-loi" role="alert">Lỗi thử</div>'));
const hForm2 = DA._html(DU, S({ moForm: true, mau: MAU, form: { mau: "ads-len-camp", muc_tieu: "", buoc: "", loi: "", dangGui: false } }));
check("mẫu thường không có ô 'Các bước'", !hForm2.includes('id="da-buoc"'));
const tb = DA._tachBuoc("Nghiên cứu\nViết content\nGATE: duyệt ngân sách\nBật camp\n");
check("tách bước: GATE: thành bước gate có mô tả", tb.buoc && tb.buoc.length === 4 && tb.buoc[2].gate === true && tb.buoc[2].gate_mo_ta === "duyệt ngân sách" && tb.buoc[3].gate === false);
check("tách bước: GATE ở cuối bị báo lỗi", !!DA._tachBuoc("A\nGATE: x").loi);
check("tách bước: rỗng bị báo lỗi", !!DA._tachBuoc("  \n").loi);

// 5. escape
const XAU = { jobs: [{
  id: 'j"><script>1</script>', title: "<script>alert(1)</script>", doi: "<img>", status: "cho_duyet", created_at: homNay(8, 0),
  buoc: [{ task_id: "z", title: "<b>x</b>", loai: "buoc", status: "blocked", block_reason: "<script>r</script>" },
    { task_id: "zg", title: "<i>g</i>", loai: "gate", status: "blocked" }, { task_id: "z2", title: "s", loai: "buoc", status: "todo" }],
  gate_cho: { task_id: "zg", mo_ta: "<script>m</script>", xem_truoc: "<script>p</script>", mo_khoa: ["z2"] },
}] };
const hX = DA._html(XAU, S());
check("chuỗi <script> từ máy chủ bị escape", !hX.includes("<script>") && hX.includes("&lt;script&gt;alert(1)&lt;/script&gt;") && hX.includes("&lt;script&gt;p&lt;/script&gt;"));
check("job_id độc bị escape trong thuộc tính", !hX.includes('data-job="j"><') && hX.includes('data-job="j&quot;&gt;&lt;script&gt;'));
check("đội lạ quy về 'khac' (Đội AI)", hX.includes('<span class="da-doi khac">Đội AI</span>'));

// 7. không vẽ lại khi đang gõ
const el = { contains: (x) => x === ta || x === btn, };
const ta = { tagName: "TEXTAREA" }, btn = { tagName: "BUTTON" }, ngoai = { tagName: "TEXTAREA" };
check("_dangGo: textarea trong khu = đang gõ", DA._dangGo(el, ta) === true);
check("_dangGo: nút trong khu không tính", DA._dangGo(el, btn) === false);
check("_dangGo: ô ngoài khu không tính", DA._dangGo(el, ngoai) === false);
check("vòng 5 giây kiểm isConnected + dangGo trước khi tải", /setInterval\(function \(\) \{\s*if \(!el\.isConnected\) \{ clearInterval[\s\S]*?if \(dangGo\(el, document\.activeElement\)\) return;[\s\S]*?\}, CHU_KY_MS\)/.test(SRC) && /CHU_KY_MS = 5000/.test(SRC));
check("taiVaVe không vẽ đè khi đang gõ (lượt không ép)", SRC.includes("if (!epVe && dangGo(el, document.activeElement)) return;"));
check("chữ đang gõ được giữ trong state qua oninput", SRC.includes("st.ghiChu[o.dataset.daGhi] = o.value") && SRC.includes("st.form[o.dataset.daO] = o.value"));

// ---------------------------------------------------------------- mã nguồn / hợp đồng HTTP
check("không em dash trong doi-ai.js/.css", !SRC.includes("\u2014") && !CSS.includes("\u2014"));
check("GET /kanban/jobs?brain= với credentials same-origin", SRC.includes('"/kanban/jobs?brain="') && SRC.includes('credentials: "same-origin"'));
check("GET /kanban/job-templates", SRC.includes('"/kanban/job-templates"'));
check("POST /kanban/job gửi brain/mau/muc_tieu hoặc steps/title/doi=khac", SRC.includes('"/kanban/job", { method: "POST"') &&
  ['fd.append("mau"', 'fd.append("muc_tieu"', 'fd.append("steps", JSON.stringify', 'fd.append("doi", "khac")', 'fd.append("title"'].every((x) => SRC.includes(x)));
check("POST /kanban/job/gate gửi brain/job_id/action/note", SRC.includes('"/kanban/job/gate"') &&
  ['fd.append("brain"', 'fd.append("job_id"', 'fd.append("action"', 'fd.append("note"'].every((x) => SRC.includes(x)));
check("Từ chối hỏi confirm()", SRC.includes("window.confirm(t(\"doiai.tu_choi_hoi\""));
check("Sửa lại cần ghi chú", SRC.includes('action === "sua" && !note'));
check("kiểm el.isConnected sau await", (SRC.match(/if \(!el\.isConnected\) return;/g) || []).length >= 4);
const khoa = [...SRC.matchAll(/\bt\(\s*"([a-z0-9_.]+)"/g)].map((m) => m[1]);
const thieu = khoa.filter((k) => !(k in VI) || !(k in EN));
check("mọi khoá t() trong doi-ai.js có ở vi.json và en.json", khoa.length > 50 && thieu.length === 0, thieu.join(", "));
check("không ghép khoá i18n động", !/t\("doiai\.[a-z_]*" \+/.test(SRC));

// ---------------------------------------------------------------- CSS chỉ dùng token
// Cùng luật với tests/python/test_design_tokens.py.
const css = CSS.replace(/\/\*[\s\S]*?\*\//g, "");
check("không mã màu hex", !/#[0-9a-f]{3,8}\b/i.test(css), (css.match(/#[0-9a-f]{3,8}\b/gi) || []).join(","));
check("không rgb()/hsl() tự gõ", !/\b(rgba?|hsla?)\(/i.test(css));
const fsBad = [...css.matchAll(/(?<![\w-])font-size\s*:\s*([^;}]*)/gi)]
  .filter((m) => [...m[1].matchAll(/(?<![\w.#-])(\d*\.?\d+)px\b/g)].some((n) => +n[1] >= 10 && +n[1] < 30));
check("không font-size px trong 10-29", fsBad.length === 0, fsBad.map((m) => m[0]).join(" | "));
const rBad = [...css.matchAll(/(?<![\w-])(border(?:-[a-z]+)*-radius)\s*:\s*([^;}]*)/gi)]
  .filter((m) => [...m[2].matchAll(/(?<![\w.#-])(\d*\.?\d+)px\b/g)].some((n) => +n[1] >= 5));
check("không bo góc px >= 5", rBad.length === 0, rBad.map((m) => m[0]).join(" | "));
const TOK = read("dashboard/surface-tokens.css");
const refs = [...css.matchAll(/var\(\s*(--mm-[A-Za-z0-9_-]+)/g)].map((m) => m[1]);
const la = [...new Set(refs.filter((r) => !TOK.includes(r + ":")))];
check("mọi var(--mm-*) là token có thật", refs.length > 50 && la.length === 0, la.join(", "));
// Tách dấu phẩy CẤP NGOÀI (bỏ qua dấu phẩy trong :is(...)).
const tachPhay = (s) => { const out = []; let d = 0, cur = ""; for (const c of s) { if (c === "(") d++; if (c === ")") d--; if (c === "," && !d) { out.push(cur); cur = ""; } else cur += c; } out.push(cur); return out.map((x) => x.trim()); };
const sel = [...css.matchAll(/(^|\})\s*([^{}@]+)\{/g)].flatMap((m) => tachPhay(m[2].trim()));
const selLa = sel.filter((x) => !/^(\.da\b|:root|textarea\.da-o)/.test(x));
check("mọi selector có tiền tố .da / :root", sel.length > 40 && selLa.length === 0, selLa.join(" | "));
check("tông tối có viền, tông sáng gỡ viền", css.includes("border: 1px solid var(--mm-line)") && /:root\[data-theme="light"\] :is\(\.da-form, \.da-the, \.da-xong\) \{ border: 0; \}/.test(css));
check("dưới 900px hàng bước dọc + khung cho phép 1 cột", /@media \(max-width: 900px\)[\s\S]*\.da-hang-buoc \{ flex-direction: column[\s\S]*\.da-cho-phep \{ grid-template-columns: minmax\(0, 1fr\)/.test(css));
check("nút cao tối thiểu 44px trên điện thoại", /@media \(max-width: 900px\)[\s\S]*min-height: 44px/.test(css));
check("Từ chối chữ màu bad", /\.da-nut-bo \{[^}]*color: var\(--mm-bad\)/.test(css));
check("bước done nền ok, đang chạy nền tím (brand)", /\.da-buoc\.xong \.da-vong \{[^}]*background: var\(--mm-ok\)/.test(css) && /\.da-buoc\.chay \.da-vong \{[^}]*background: var\(--mm-brand\)/.test(css));

// ---------------------------------------------------------------- Đội Ads: thẻ camp + giới hạn (26.10.248)
const CAMP = { tai_khoan: "1372588536646337", campaign_id: "120001", adset_ids: ["s1"], ad_ids: ["a1", "a2"],
  ten: "CÔNG TY TNHH MTV HALIMI - <b>HALIMI 07</b> - P720", ngan_sach_ngay_vnd: 300000, trang_thai: "NHAP" };
const JOB_CAMP = Object.assign({}, JOB_CHO, { id: "job-ads-2", gate_cho: Object.assign({}, JOB_CHO.gate_cho, { ads: CAMP }) });
const hCamp = DA._html({ jobs: [JOB_CAMP] }, S());
check("GATE có ads: thẻ Camp sẽ bật", hCamp.includes(VI["doiai.camp_tieu_de"]) && hCamp.includes("da-camp"));
check("thẻ camp: tài khoản act_ + ngân sách đồng/ngày", hCamp.includes("act_1372588536646337") && hCamp.includes("300.000đ/ngày"));
check("thẻ camp: đếm nhóm và quảng cáo", hCamp.includes("1 nhóm quảng cáo, 2 quảng cáo"));
check("thẻ camp: trạng thái nháp chưa chi tiền", hCamp.includes(VI["doiai.camp_nhap"]));
check("thẻ camp: tên camp bị escape", hCamp.includes("&lt;b&gt;HALIMI 07&lt;/b&gt;") && !hCamp.includes("<b>HALIMI 07</b>"));
check("GATE không có ads: không có thẻ camp", !DA._html({ jobs: [JOB_CHO] }, S()).includes("da-camp\""));
check("định dạng tiền", DA._dongTien(700000) === "700.000đ" && DA._dongTien(0) === "0đ");
const hGh = DA._html({ jobs: [] }, S());
check("nút Giới hạn Đội Ads luôn có, mặc định gập", hGh.includes(VI["doiai.gh_tieu_de"]) && hGh.includes('data-da="gioi_han" aria-expanded="false"') && !hGh.includes("da-gh-tk"));
const hGh2 = DA._html({ jobs: [] }, S({ moGioiHan: true, gioiHan: { tai: true, tai_khoan: "act_1\nact_2", tran: "700000", loi: "", dangLuu: false, daLuu: true } }));
check("mở Giới hạn: ô tài khoản, ô trần, nút Lưu", hGh2.includes('id="da-gh-tk"') && hGh2.includes('value="700000"') && hGh2.includes('data-da="luu_gioi_han"'));
check("mở Giới hạn: nhãn gắn đúng ô", hGh2.includes('for="da-gh-tk"') && hGh2.includes('for="da-gh-tran"'));
check("mở Giới hạn: báo đã lưu", hGh2.includes(VI["doiai.gh_da_luu"]));
check("mở Giới hạn: giải thích VND", hGh2.includes("VND"));
check("JS gọi đúng /meta-ads/luat", SRC.includes('"/meta-ads/luat"'));

console.log("");
if (fails.length) { console.log("FAIL " + fails.length + " mục"); process.exit(1); }
console.log("Tất cả xanh.");
