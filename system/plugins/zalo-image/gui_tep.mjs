// Gửi FILE/VIDEO qua Zalo bằng đúng thư viện của zalo-agent-cli, nhưng BẬT listener trước.
// Vì sao: zca-js tải file lên rồi chờ Zalo báo lại qua websocket (uploadCallbacks, do
// listener phát). Lệnh `msg send-file` của CLI không mở listener nên treo tới khi hết giờ.
// Chạy qua: npx -y -p zalo-agent-cli@X node gui_tep.mjs <threadId> <type> <caption> <file...>
import { realpathSync } from "node:fs";
import { delimiter, dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

function goiCli() {
    const ten = process.platform === "win32" ? ["zalo-agent.cmd", "zalo-agent"] : ["zalo-agent"];
    for (const d of (process.env.PATH || "").split(delimiter)) {
        for (const t of ten) {
            try {
                const real = realpathSync(join(d, t));
                if (real.endsWith("index.js")) return dirname(dirname(real));
            } catch { /* thử thư mục kế */ }
        }
    }
    throw new Error("không tìm thấy zalo-agent-cli trong PATH");
}

const [threadId, loai, caption, ...tep] = process.argv.slice(2);
const xong = (obj, code) => { console.log(JSON.stringify(obj)); process.exit(code); };

try {
    const goc = goiCli();
    const zc = await import(pathToFileURL(join(goc, "src", "core", "zalo-client.js")).href);
    process.env.ZALO_JSON_MODE = "1";
    await zc.autoLogin(true);
    const api = zc.getApi();

    await new Promise((ok, loi) => {
        const t = setTimeout(() => loi(new Error("listener không kết nối được sau 20 giây")), 20000);
        api.listener.on("connected", () => { clearTimeout(t); ok(); });
        api.listener.on("error", (e) => { clearTimeout(t); loi(e instanceof Error ? e : new Error(String(e))); });
        api.listener.start();
    });

    const kq = await api.sendMessage(
        { msg: caption || "", attachments: tep.map((p) => resolve(p)) },
        threadId, Number(loai) || 0);
    try { api.listener.stop(); } catch { /* bỏ qua */ }
    xong({ ok: true, result: kq }, 0);
} catch (e) {
    xong({ ok: false, error: String(e && e.message || e) }, 1);
}
