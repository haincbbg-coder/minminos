// Nói chuyện với MinMin: ghép máy, tải ba bảng tra, chốt mã. Token nằm trong chrome.storage.local.
const MAC_DINH = "https://minmin.elaria.cloud";
const lay = (k) => chrome.storage.local.get(k).then((o) => o);

async function cauHinh() {
  const o = await lay(["server", "token"]);
  return { server: (o.server || MAC_DINH).replace(/\/+$/, ""), token: o.token || "" };
}
async function goi(duong, opt = {}) {
  const { server, token } = await cauHinh();
  const r = await fetch(server + "/goi-y-ma/may/" + duong, {
    method: opt.body ? "POST" : "GET",
    headers: Object.assign({ "content-type": "application/json" }, token ? { "x-minmin-may": token } : {}),
    body: opt.body ? JSON.stringify(opt.body) : undefined,
  });
  let j = {}; try { j = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(j.error || j.goi_y_ma || ("HTTP " + r.status));
  return j;
}
async function taiBang() {
  const j = await goi("bang");
  await chrome.storage.local.set({ bang: j, bang_luc: Date.now() });
  return j;
}

chrome.runtime.onMessage.addListener((m, _s, tra) => {
  (async () => {
    try {
      if (m.loai === "ghep") {
        const o = await lay(["server"]);
        if (m.server) await chrome.storage.local.set({ server: m.server.replace(/\/+$/, "") });
        const j = await goi("ghep", { body: { ma: m.ma, ten: m.ten || "Cốc Cốc", phien_ban: chrome.runtime.getManifest().version } });
        await chrome.storage.local.set({ token: j.token, may_id: j.may_id });
        await taiBang();
        return tra({ ok: true });
      }
      if (m.loai === "bang") {
        const o = await lay(["bang", "bang_luc", "token"]);
        if (!o.token) return tra({ ok: false, error: "chưa ghép máy" });
        if (!o.bang || Date.now() - (o.bang_luc || 0) > 10 * 60 * 1000) { try { return tra({ ok: true, bang: await taiBang() }); } catch (e) { if (!o.bang) throw e; } }
        return tra({ ok: true, bang: o.bang });
      }
      if (m.loai === "lam_moi") return tra({ ok: true, bang: await taiBang() });
      if (m.loai === "xac_nhan") { await goi("xac-nhan", { body: m.du_lieu }); return tra({ ok: true }); }
      if (m.loai === "trang_thai") {
        const o = await lay(["server", "token", "bang", "bang_luc"]);
        return tra({ ok: true, server: o.server || MAC_DINH, da_ghep: !!o.token,
          sku: o.bang ? Object.keys(o.bang.sku || {}).length : 0, ad: o.bang ? Object.keys(o.bang.ad || {}).length : 0,
          post: o.bang ? Object.keys(o.bang.post || {}).length : 0, bang_luc: o.bang_luc || 0 });
      }
      if (m.loai === "go_ghep") { await chrome.storage.local.remove(["token", "may_id", "bang", "bang_luc"]); return tra({ ok: true }); }
      tra({ ok: false, error: "loại lệnh lạ" });
    } catch (e) { tra({ ok: false, error: String(e.message || e) }); }
  })();
  return true;
});
