// Thanh mục tiêu và lệnh /goal (26.10.310): phần thuần của dashboard/chat-goal.js, phần /goal của chat-slash.js,
// và chỗ app.js nối vào. Chạy: node tests/js/test_chat_goal.js
const path = require("path");
const fs = require("fs");
const D = path.join(__dirname, "..", "..", "dashboard");
const G = require(path.join(D, "chat-goal.js"));
const S = require(path.join(D, "chat-slash.js"));

const fails = [];
function check(ten, ok, them) {
  console.log((ok ? "ok   " : "FAIL ") + ten + (!ok && them !== undefined ? "  [" + JSON.stringify(them) + "]" : ""));
  if (!ok) fails.push(ten);
}

// ---- 1. Khối chỉ dẫn và dòng ẩn ----
const k1 = G.khoiMucTieu("đối soát [hết] đơn", 1, 5);
check("khối mở bằng [MỤC TIÊU:", k1.startsWith("[MỤC TIÊU: "));
check("khối kết thúc bằng ]\\n\\n để bong bóng bóc được", k1.endsWith("]\n\n"));
check("ngoặc vuông trong điều kiện đổi sang ngoặc tròn", k1.includes("đối soát (hết) đơn") && k1.indexOf("]") === k1.length - 3);
const k2 = G.khoiMucTieu("x", 2, 5, "còn 3 đơn");
check("vòng 2 mang phần còn thiếu", k2.includes("vòng 2/5") && k2.includes("Vòng trước còn: còn 3 đơn"));
check("không có em dash", !k1.includes("—") && !k2.includes("—"));

check("đọc dòng ẩn done", JSON.stringify(G.docDanhDau('xong <!-- MINMIN_GOAL: {"done":true} -->')) === '{"done":true,"left":""}');
check("dòng CUỐI thắng", G.docDanhDau('<!-- MINMIN_GOAL: {"done":true} --> rồi <!-- MINMIN_GOAL: {"done":false,"left":"a"} -->').done === false);
check("dòng hỏng = không có", G.docDanhDau("<!-- MINMIN_GOAL: {hỏng} -->") === null);
check("thiếu done kiểu boolean = không có", G.docDanhDau('<!-- MINMIN_GOAL: {"done":"yes"} -->') === null);
check("blocked được giữ", G.docDanhDau('<!-- MINMIN_GOAL: {"done":false,"blocked":"thiếu quyền"} -->').blocked === "thiếu quyền");

// ---- 2. Quyết định vòng tiếp ----
const g0 = { vong: 1, toiDa: 5, left: "" };
check("lỗi thì dừng", G.quyetDinh(g0, { loi: true }).ly === "loi");
check("model hỏi ngược thì dừng", G.quyetDinh(g0, { hoiLai: true, marker: { done: false } }).ly === "hoi_lai");
check("không báo thì dừng, không đoán", G.quyetDinh(g0, { marker: null }).ly === "khong_bao");
check("đạt thì dừng", G.quyetDinh(g0, { marker: { done: true } }).ly === "dat");
check("kẹt thì dừng", G.quyetDinh(g0, { marker: { done: false, blocked: "x" } }).ly === "ket");
check("chưa đạt thì chạy tiếp", G.quyetDinh(g0, { marker: { done: false, left: "còn 2" } }).act === "tiep");
check("hết vòng thì dừng", G.quyetDinh({ vong: 5, toiDa: 5 }, { marker: { done: false, left: "a" } }).ly === "het_vong");
check("hai vòng liền y hệt thì dừng", G.quyetDinh({ vong: 2, toiDa: 5, left: "Còn  2 đơn" }, { marker: { done: false, left: "còn 2 đơn" } }).ly === "dung_im");

// ---- 3. Tạm dừng: đồng hồ đứng, chạy lại thì chạy tiếp ----
const g = G.taoMucTieu({ sid: "s1", dk: "a" }, 1000);
check("mới tạo là đang chạy", g.state === "running" && G.thoiGian(g, 4000) === 3000);
check("tạm dừng được", G.tamDung(g, 5000) && g.state === "paused");
check("tạm dừng thì đồng hồ đứng", G.thoiGian(g, 99000) === 4000);
check("chạy lại cộng tiếp", G.chayLai(g, 100000) && G.thoiGian(g, 102000) === 6000);
check("định dạng giờ", G.dinhDangGio(3 * 3600e3 + 39 * 60e3 + 9e3) === "3h 39m 9s" && G.dinhDangGio(45e3) === "45s");
check("trạng thái hiện: chat khác thì chờ", G.trangThai(g, "s2") === "waiting" && G.trangThai(g, "s1") === "running");

// ---- 4. Kho: nhiều mục tiêu, một mục tiêu mỗi chat, tải lại trang thì tạm dừng ----
G._datLai();
const a = G.them({ sid: "s1", dk: "một" }, 1000);
G.them({ sid: "s2", dk: "hai" }, 2000);
check("nhiều chat thì nhiều mục tiêu", G.ds().length === 2);
G.them({ sid: "s1", dk: "một mới" }, 3000);
check("cùng chat thì mục tiêu mới thay cái cũ", G.ds().length === 2 && G.theoSid("s1").dk === "một mới" && !G.theoId(a.id));
const raw = G.veKho(G.ds(), 5000);
const lai = G.tuKho(raw);
check("tải lại: giữ đủ mục tiêu", lai.length === 2);
check("tải lại: tất cả tạm dừng, chạy tiếp là đi vòng sau", lai.every(x => x.state === "paused" && x.tiepNgay));
check("kho hỏng thì rỗng, không nổ", G.tuKho("{hỏng").length === 0 && G.tuKho('{"a":1}').length === 0);
check("mục tiêu thiếu sid bị bỏ", G.tuKho('[{"id":"x","dk":"a"}]').length === 0);

// ---- 5. HTML của thanh ----
G._datLai();
G.them({ sid: "s1", dk: "đối soát <b>đơn</b>" }, 1000);
let h = G.barHtml(G.ds(), "s1", 2000, {});
check("một mục tiêu: không có ô số", !h.includes("gb-count"));
check("có nút xoá, tạm dừng, chi tiết", h.includes('data-act="del"') && h.includes('data-act="pause"') && h.includes('data-act="expand"'));
check("chữ mục tiêu được escape", h.includes("&lt;b&gt;") && !h.includes("<b>"));
G.them({ sid: "s2", dk: "hai" }, 2000);
h = G.barHtml(G.ds(), "s1", 3000, { xo: true });
check("hai mục tiêu: có ô số 2", /class="gb-count"[^>]*>2</.test(h));
check("đứng trên thanh là mục tiêu của chat đang mở", h.indexOf("đối soát") < h.indexOf("gb-pop"));
check("danh sách xổ ra có cả hai", (h.match(/class="gb-item /g) || []).length === 2);
G.tamDung(G.theoSid("s1"), 4000);
h = G.barHtml(G.ds(), "s1", 5000, {});
check("tạm dừng thì nút thành chạy tiếp", h.includes('data-act="resume"') && h.includes("gb-paused"));
check("không có mục tiêu thì rỗng", G.barHtml([], "s1") === "");

// ---- 6. /goal trong chat-slash.js ----
check("/goal là lệnh hệ thống", S.classify("goal") === "system");
const r = S.route("/goal mọi đơn đã đối soát");
check("route /goal ra type goal kèm điều kiện", r.type === "goal" && r.arg === "mọi đơn đã đối soát", r);
check("/goal giữa câu không phải lệnh", S.route("làm /goal đi").type === "passthrough");
check("menu có /goal", S.buildMenu([]).some(i => i.cmd === "goal" && i.kind === "system"));
check("tô màu /goal ở đầu tin", JSON.stringify(S.vungLenh("/goal abc")) === '{"start":0,"end":5}');
check("đang gõ dở /go thì chưa tô", S.vungLenh("/go") === null);
check("lệnh phiên cũng tô", JSON.stringify(S.vungLenh("/new")) === '{"start":0,"end":4}');
check("đường dẫn không bị tô", S.vungLenh("xem /home/user/a") === null);
S.setKnownSkills(["viet-email"]);
check("skill giữa câu được tô", JSON.stringify(S.vungLenh("nhờ em /viet-email nhé")) === '{"start":7,"end":18}');
check("cột lệnh có sàn và trần", S.cotLenh([{ cmd: "new" }]) === 7 && S.cotLenh([{ cmd: "a".repeat(40) }]) === 18);
check("nhóm: lệnh phiên và hệ thống chung nhóm Lệnh", S.nhomCua({ kind: "session" }) === "cmd" && S.nhomCua({ kind: "system" }) === "cmd");

// ---- 7. app.js nối vào ----
const APP = fs.readFileSync(path.join(D, "app.js"), "utf8");
check("chuNguoiGo bóc khối [MỤC TIÊU:", APP.includes('"[MỤC TIÊU:"'));
check("Dừng thì tạm dừng mục tiêu, không xoá", /MinMinGoals\.biDung\(sid\)/.test(APP));
check("tin thường gõ chen thì mục tiêu tạm dừng", /MinMinGoals\.chenNgang\(sid\)/.test(APP));
check("turn_done của MỌI chat báo cho mục tiêu", /MinMinGoals\.hetLuot\(sid\)/.test(APP));
check("/goal không đi thẳng lên server", /_slash\.type === "goal"[\s\S]{0,400}MinMinGoals\.lenh\(_slash\.arg\)/.test(APP));
const HTML = fs.readFileSync(path.join(D, "index.html"), "utf8");
check("thanh mục tiêu nằm trên ô gõ", HTML.indexOf('id="goalBar"') > 0 && HTML.indexOf('id="goalBar"') < HTML.indexOf('id="chatInput"'));
check("chat-goal.js nạp trước app.js", HTML.indexOf("chat-goal.js") > 0 && HTML.indexOf("chat-goal.js") < HTML.indexOf("/static/app.js"));
const CON = fs.readFileSync(path.join(D, "console.js"), "utf8");
check("thanh đi theo khung chat sang trang Trò chuyện", /CHAT_NODE_IDS = \[[^\]]*"goalBar"/.test(CON));
const SRC = fs.readFileSync(path.join(D, "chat-goal.js"), "utf8");
check("chat-goal.js không có em dash", !SRC.includes("—"));

console.log(fails.length ? "\nFAIL - test_chat_goal: " + fails.length + " lỗi" : "\nOK - test_chat_goal: tất cả pass");
process.exit(fails.length ? 1 : 0);
