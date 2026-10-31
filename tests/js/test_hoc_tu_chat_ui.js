/* Khối "Học từ trò chuyện" trên trang Tự học (dashboard/hoc-tu-chat.js, 26.10.308).

       node tests/js/test_hoc_tu_chat_ui.js

   Phần thuần chạy dưới node; phần nối (thẻ script, chỗ gắn ở console.js, token CSS) soi mã nguồn.
   Không dùng ký tự em dash. */
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..", "..");
const vi = JSON.parse(fs.readFileSync(path.join(root, "dashboard/i18n/vi.json"), "utf8"));
const en = JSON.parse(fs.readFileSync(path.join(root, "dashboard/i18n/en.json"), "utf8"));

global.window = { t: (k, v) => (vi[k] || k).replace(/\{(\w+)\}/g, (m, x) => (v && x in v ? v[x] : m)) };
const H = require(path.join(root, "dashboard", "hoc-tu-chat.js"));

const fails = [];
function check(name, cond, them) { console.log((cond ? "ok   " : "FAIL ") + name + (cond || !them ? "" : "  [" + them + "]")); if (!cond) fails.push(name); }

check("phơi MinMinHocTuChat.mount", typeof window.MinMinHocTuChat.mount === "function");
check("tên mục tiêu: quy trình đếm bước từ 1", H.tenMucTieu({ loai: "workflow", slug: "chot-don", buoc: 0 }).includes("bước 1"));
check("tên mục tiêu: trợ lý", H.tenMucTieu({ loai: "agent", slug: "ban-hang" }).startsWith("Trợ lý"));

const cho = H.lanHtml({ id: "hc_1", loai: "skill", slug: "bao-gia", trang_thai: "xong", ket_luan: "da_giup", cho_duyet: true,
  ban_moi: "<script>x</script>", bat_dau: 1, tom_tat: { ket_qua: { thang: 6, thua: 0, hoa: 2 }, so_cau: 14 } });
check("đề xuất có nút Áp dụng và Bỏ", cho.includes("htc-ap") && cho.includes("htc-bo") && !cho.includes("htc-ht"));
check("đề xuất hiện nhãn chờ duyệt", cho.includes(vi["htc.st_waiting"]));
check("bản mới được thoát HTML", !cho.includes("<script>") && cho.includes("&lt;script&gt;"));
check("dòng kết quả nói thắng thua", cho.includes("thắng 6") && cho.includes("14"));

const da = H.lanHtml({ id: "hc_2", loai: "agent", slug: "ban-hang", trang_thai: "xong", ket_luan: "da_giup", ap_dung: true });
check("đã áp dụng thì chỉ có Hoàn tác", da.includes("htc-ht") && !da.includes("htc-ap"));
const ht = H.lanHtml({ id: "hc_3", loai: "skill", slug: "x", trang_thai: "xong", ap_dung: true, hoan_tac_luc: 5 });
check("đã hoàn tác thì không còn nút", !ht.includes("<button"));
check("giữ nguyên có nhãn riêng", H.nhanLan({ trang_thai: "xong", ket_luan: "giu_nguyen" }) === vi["htc.st_kept"]);

const tk = H.thongKeHtml({ cham_hom_nay: 3, hoc_hom_nay: 0, cho_cham: 2, loi_mo: { "skill:bao-gia": 2 },
  tran: { cham: 40, hoc: 1, loi_toi_thieu: 3 } });
check("thống kê nói trần mỗi ngày", tk.includes("3/40") && tk.includes("0/1"));
check("lỗi đang mở hiện n/3", tk.includes("skill:bao-gia") && tk.includes("2/3"));
check("công tắc tạm dừng có hai trạng thái",
  H.khungHtml(true).includes(vi["htc.paused_on"]) && H.khungHtml(false).includes(vi["htc.paused_off"]));

const src = fs.readFileSync(path.join(root, "dashboard/hoc-tu-chat.js"), "utf8");
const con = fs.readFileSync(path.join(root, "dashboard/console.js"), "utf8");
const html = fs.readFileSync(path.join(root, "dashboard/index.html"), "utf8");
const css = fs.readFileSync(path.join(root, "dashboard/console.css"), "utf8");
check("index.html nạp hoc-tu-chat.js", /\/static\/hoc-tu-chat\.js\?v=\d+/.test(html));
check("trang Tự học gắn khối", con.includes('id="lnHocTuChat"') && con.includes("MinMinHocTuChat.mount"));
check("gọi đúng endpoint", ["/hoc-tu-chat/tong-quan", "/hoc-tu-chat/tam-dung", "/hoc-tu-chat/"].every((u) => src.includes(u)));
const khoiCss = css.slice(css.indexOf("Học từ trò chuyện (26.10.308"));
check("CSS của khối chỉ dùng token, không mã màu", khoiCss.length > 0 && !/#[0-9a-fA-F]{3,6}\b|rgba?\(/.test(khoiCss));
check("không em dash", !src.includes("—") && !khoiCss.includes("—"));
const khoa = Object.keys(vi).filter((k) => k.startsWith("htc."));
check("mọi khoá htc.* có bản tiếng Anh", khoa.length >= 20 && khoa.every((k) => k in en), khoa.filter((k) => !(k in en)).join(","));

if (fails.length) { console.log("\nĐỎ: " + fails.length); process.exit(1); }
console.log("\nXanh hết.");
