const $ = (i) => document.getElementById(i);
const hoi = (m) => new Promise((r) => chrome.runtime.sendMessage(m, r));
async function lam() {
  const s = await hoi({ loai: "trang_thai" });
  $("sv").value = s.server;
  $("ghep").hidden = s.da_ghep; $("da").hidden = !s.da_ghep;
  $("tt").textContent = s.da_ghep ? `Đã ghép. Bảng: ${s.sku} mã, ${s.ad} quảng cáo, ${s.post} bài viết` : "Chưa ghép với MinMin";
}
$("bg").onclick = async () => {
  $("loi").textContent = "";
  const r = await hoi({ loai: "ghep", ma: $("ma").value.trim(), server: $("sv").value.trim() });
  if (!r.ok) $("loi").textContent = r.error; else lam();
};
$("lm").onclick = async () => { const r = await hoi({ loai: "lam_moi" }); if (!r.ok) $("loi").textContent = r.error; lam(); };
$("go").onclick = async () => { await hoi({ loai: "go_ghep" }); lam(); };
lam();
