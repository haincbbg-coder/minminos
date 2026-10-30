/* 26.10.312: chuông chỉ hiện tin chưa đọc, có X, Không cần báo, ngăn Đã lọc; trang Công việc
   không xoá câu bố đang gõ, có Nhắn thêm, Kiểm lại, khu MinMin đang tự xử lý.

       node tests/js/test_thong_bao_cong_viec.js
*/
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..", "..");
const D = (f) => fs.readFileSync(path.join(ROOT, "dashboard", f), "utf8");
const NOTI = D("notifications.js");
const JS = D("console.js");
const VI = JSON.parse(D(path.join("i18n", "vi.json")));
const EN = JSON.parse(D(path.join("i18n", "en.json")));

const fails = [];
const check = (name, cond, them) => {
  console.log((cond ? "ok   " : "FAIL ") + name + (!cond && them ? "  [" + them + "]" : ""));
  if (!cond) fails.push(name);
};

// ── chuông ──
check("hòm thư chỉ hiện tin chưa đọc trừ khi bấm xem tin đã đọc",
  /chuaDoc\.concat\(state\.showRead \? daDoc : \[\]\)/.test(NOTI));
check("có link Xem N thông báo đã đọc", /noti\.show_read/.test(NOTI) && VI["noti.show_read"].includes("{count}"));
check("Đọc tất cả là sạch chuông (về danh sách chưa đọc)", /docThu\(\{ all: true \}\)/.test(NOTI) && /state\.showRead = false;\s*docThu/.test(NOTI));
check("X trên từng thư gọi /inbox/delete", /data-thu-act="xoa"/.test(NOTI) && /fetch\("\/inbox\/delete"/.test(NOTI));
check("X trên tin tức ẩn trên máy này", /data-an-tin/.test(NOTI) && /saveHidden\(\)/.test(NOTI));
check("Không cần báo gọi /inbox/react", /not_needed/.test(NOTI) && /fetch\("\/inbox\/react"/.test(NOTI));
check("ngăn Đã lọc riêng", /x\.filtered/.test(NOTI) && /notiShowFiltered/.test(NOTI));
check("chỉnh chế độ từng nhóm và hoàn tác", /\/thong-bao\/muc\/nhom/.test(NOTI) && /\/thong-bao\/muc\/hoan-tac/.test(NOTI));
["reminder", "question", "chatbot", "connection", "incident", "job", "cost", "update", "other"].forEach((g) =>
  check("nhãn nhóm " + g, typeof VI["noti.g_" + g] === "string" && typeof EN["noti.g_" + g] === "string"));
check("tên nhóm Câu hỏi chờ bố", VI["noti.g_question"] === "Câu hỏi chờ bố");

// ── trang Công việc ──
check("fillList bỏ qua danh sách không đổi", /if \(node\._knHtml === html\) return false;/.test(JS));
check("fillList không dựng lại khi bố đang gõ",
  /const typing = \[\.\.\.node\.querySelectorAll\("\.kn-ask-input"\)\]\.some/.test(JS));
check("post() không bao giờ ném", /catch \(e\) \{ return \{ ok: false, error: t\("kanban\.cant_update"\) \}; \}/.test(JS));
check("Nhắn thêm gọi /kanban/task/followup", /post\("\/kanban\/task\/followup"/.test(JS));
check("Kiểm lại gọi /kanban/task/verify", /post\("\/kanban\/task\/verify"/.test(JS));
check("thẻ hiện câu dễ hiểu thay vì lỗi đỏ", /t\.calm \? `<div class="kn-calm">/.test(JS)
  && !/kn-task-result" style="color:var\(--red\)"/.test(JS));
check("chi tiết kỹ thuật thu gọn", /<details class="kn-tech">/.test(JS));
check("gợi ý việc lặp có nút bỏ qua", /\/kanban\/hint\/dismiss/.test(JS));
["kanban.p_handled", "kanban.act_follow", "kanban.act_verify", "kanban.kiem_dat", "kanban.kiem_chua", "kanban.hint_msg"].forEach((k) =>
  check("vi.json có " + k, typeof VI[k] === "string" && VI[k].length > 0));
check("Cần bố xử lý", VI["kanban.kpi_attention"] === "Cần bố xử lý");

const allVi = JSON.stringify(VI);
check("không có gạch dài trong vi.json", allVi.indexOf("—") === -1);

console.log();
if (fails.length) {
  console.log("FAIL " + fails.length + ": " + fails.join("; "));
  process.exit(1);
}
console.log("Tất cả xanh.");
