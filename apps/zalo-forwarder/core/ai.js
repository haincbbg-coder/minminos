// Trich tu Zalo Forwarder v2.10.0 (TrungKienHa), chuyen sang chay tren web trong MinMin OS.
"use strict";
var DEFAULT_MODELS = {
  openai: "gpt-4o-mini",
  claude: "claude-3-5-haiku-latest",
  gemini: "gemini-1.5-flash"
};
var BUILTIN_MODELS = {
  openai: ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini"],
  claude: ["claude-3-5-haiku-latest", "claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest"],
  gemini: ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"]
};
function providerLabel(p) {
  return { openai: "OpenAI (ChatGPT)", claude: "Claude (Anthropic)", gemini: "Gemini (Google)" }[p] || p;
}
function resolveAI(globalAi, tmplAi) {
  globalAi = globalAi || {};
  const keys = globalAi.keys || {};
  const models = globalAi.models || {};
  const provider = tmplAi && tmplAi.provider || globalAi.provider || "openai";
  const apiKey = keys[provider] || (provider === globalAi.provider ? globalAi.apiKey : "") || "";
  const model = tmplAi && tmplAi.model || models[provider] || (provider === globalAi.provider ? globalAi.model : "") || "";
  return { provider, apiKey, model };
}
async function fetchJson(url, opts, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs || 3e4);
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal });
    const raw = await res.text();
    let data = null;
    try {
      data = raw ? JSON.parse(raw) : null;
    } catch (_e) {
      data = null;
    }
    if (!res.ok) {
      const msg = data && (data.error?.message || data.error || data.message) || raw || "HTTP " + res.status;
      throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}
async function aiChat(ai, systemPrompt, userText) {
  if (!ai || !ai.provider) throw new Error("Chua chon nha cung cap AI.");
  if (!ai.apiKey) throw new Error("Chua nhap API key.");
  const model = ai.model && ai.model.trim() || DEFAULT_MODELS[ai.provider];
  if (ai.provider === "openai") {
    const data = await fetchJson("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + ai.apiKey },
      body: JSON.stringify({
        model,
        temperature: 0.3,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userText }
        ]
      })
    });
    return (data?.choices?.[0]?.message?.content || "").trim();
  }
  if (ai.provider === "claude") {
    const data = await fetchJson("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": ai.apiKey,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model,
        max_tokens: 1500,
        temperature: 0.3,
        system: systemPrompt,
        messages: [{ role: "user", content: userText }]
      })
    });
    const parts = data?.content || [];
    return parts.map((p) => p.text || "").join("").trim();
  }
  if (ai.provider === "gemini") {
    const url = "https://generativelanguage.googleapis.com/v1beta/models/" + encodeURIComponent(model) + ":generateContent?key=" + encodeURIComponent(ai.apiKey);
    const data = await fetchJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        system_instruction: { parts: [{ text: systemPrompt }] },
        contents: [{ parts: [{ text: userText }] }],
        generationConfig: { temperature: 0.3 }
      })
    });
    const cand = data?.candidates?.[0];
    return (cand?.content?.parts || []).map((p) => p.text || "").join("").trim();
  }
  throw new Error("Nha cung cap khong ho tro: " + ai.provider);
}
async function aiListModels2(ai) {
  if (!ai || !ai.provider) throw new Error("Chua chon nha cung cap AI.");
  if (!ai.apiKey) throw new Error("Chua nhap API key.");
  if (ai.provider === "openai") {
    const d = await fetchJson("https://api.openai.com/v1/models", { headers: { Authorization: "Bearer " + ai.apiKey } });
    return (d?.data || []).map((m) => m.id).filter((id) => /^(gpt|o[0-9]|chatgpt)/i.test(id)).sort();
  }
  if (ai.provider === "claude") {
    const d = await fetchJson("https://api.anthropic.com/v1/models", {
      headers: { "x-api-key": ai.apiKey, "anthropic-version": "2023-06-01" }
    });
    return (d?.data || []).map((m) => m.id).sort();
  }
  if (ai.provider === "gemini") {
    const d = await fetchJson(
      "https://generativelanguage.googleapis.com/v1beta/models?key=" + encodeURIComponent(ai.apiKey),
      {}
    );
    return (d?.models || []).filter((m) => (m.supportedGenerationMethods || []).includes("generateContent")).map((m) => String(m.name || "").replace(/^models\//, "")).filter(Boolean).sort();
  }
  throw new Error("Nha cung cap khong ho tro: " + ai.provider);
}
async function aiTest2(ai) {
  const out = await aiChat(ai, "Ban la tro ly. Tra loi ngan gon.", "Tra loi dung 2 tu: OK R\u1ED2I");
  return { ok: true, provider: providerLabel(ai.provider), model: ai.model && ai.model.trim() || DEFAULT_MODELS[ai.provider], sample: out };
}
function buildEditInstruction(rs) {
  const lines = [];
  if (rs.brand && rs.brand.enabled && rs.brand.map) {
    const pairs = Object.entries(rs.brand.map).filter(([k]) => k);
    if (pairs.length) lines.push("- Doi ten thuong hieu: " + pairs.map(([k, v]) => `"${k}" -> "${v}"`).join(", ") + ".");
  }
  if (rs.price && rs.price.enabled) {
    const p = rs.price;
    let how = "";
    if (p.mode === "add_amount") how = `cong them ${p.amount || 0} VND vao MOI GIA san pham`;
    else if (p.mode === "add_percent") how = `tang MOI GIA them ${p.percent || 0}%`;
    else if (p.mode === "multiply") how = `nhan MOI GIA voi he so ${p.factor || 1}`;
    else if (p.mode === "replace_map") {
      const pairs = Object.entries(p.map || {}).filter(([k]) => k);
      how = "thay gia chinh xac: " + pairs.map(([k, v]) => `"${k}" -> "${v}"`).join(", ");
    }
    const round = p.round == null ? 1e3 : p.round;
    lines.push(
      `- Doi gia: ${how}. Sau khi doi, lam tron ve boi so ${round}. Luu y so viet tat: "400" hoac "400k" deu la 400.000 VND (400 nghin). TUYET DOI khong doi cac so KHONG phai gia nhu: so luong ("100 cai", "5 mau"), size ("size 40"), so dien thoai, ngay/thang/nam, phan tram. Giu nguyen dinh dang goc (neu goc ghi "400k" thi tra "450k"; neu goc ghi "400" thi tra "450"; neu "400.000d" thi tra "450.000d").`
    );
  }
  if (rs.link && rs.link.enabled) {
    if (rs.link.action === "replace") lines.push(`- Thay moi duong link bang: "${rs.link.replaceWith || ""}".`);
    else lines.push("- Xoa het duong link (http/https/www).");
  }
  if (rs.prependText) lines.push(`- Chen len DAU tin doan: "${rs.prependText}".`);
  if (rs.appendText) lines.push(`- Chen xuong CUOI tin doan: "${rs.appendText}".`);
  return lines;
}
async function aiEditMessage(ai, rs, text) {
  if (!text || !text.trim()) return text;
  const instr = buildEditInstruction(rs);
  if (!instr.length) return text;
  const system = "Ban la bien tap vien tin ban hang tieng Viet. Nhiem vu: ap dung DUNG cac phep bien tap duoi day len tin nhan, giu nguyen moi thu khac (emoji, xuong dong, dau cach). Chi tra ve NOI DUNG TIN da bien tap, KHONG them loi giai thich, KHONG them dau ngoac kep bao ngoai.\n\nCAC PHEP BIEN TAP:\n" + instr.join("\n");
  const out = await aiChat(ai, system, text);
  return (out || text).trim();
}
async function aiConverse2(ai, history, systemPrompt) {
  if (!ai || !ai.provider) throw new Error("Chua chon nha cung cap AI.");
  if (!ai.apiKey) throw new Error("Chua nhap API key.");
  const msgs = (history || []).filter((m) => m && m.content && (m.role === "user" || m.role === "assistant"));
  if (!msgs.length) throw new Error("Chua co noi dung chat.");
  const system = systemPrompt || "Ban la tro ly AI trong phan mem Zalo Forwarder cua mot shop thoi trang nu. Giup chu shop: soan va sua noi dung tin ban hang, goi y cach bien tap (doi gia, doi ten thuong hieu, xoa/thay link), va huong dan su dung phan mem. Tra loi tieng Viet, ngan gon, thuc dung.";
  const model = ai.model && ai.model.trim() || DEFAULT_MODELS[ai.provider];
  if (ai.provider === "openai") {
    const data = await fetchJson("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: "Bearer " + ai.apiKey },
      body: JSON.stringify({
        model,
        temperature: 0.5,
        messages: [{ role: "system", content: system }, ...msgs.map((m) => ({ role: m.role, content: m.content }))]
      })
    });
    return (data?.choices?.[0]?.message?.content || "").trim();
  }
  if (ai.provider === "claude") {
    const data = await fetchJson("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": ai.apiKey, "anthropic-version": "2023-06-01" },
      body: JSON.stringify({
        model,
        max_tokens: 1500,
        temperature: 0.5,
        system,
        messages: msgs.map((m) => ({ role: m.role, content: m.content }))
      })
    });
    return (data?.content || []).map((p) => p.text || "").join("").trim();
  }
  if (ai.provider === "gemini") {
    const url = "https://generativelanguage.googleapis.com/v1beta/models/" + encodeURIComponent(model) + ":generateContent?key=" + encodeURIComponent(ai.apiKey);
    const data = await fetchJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        system_instruction: { parts: [{ text: system }] },
        contents: msgs.map((m) => ({ role: m.role === "assistant" ? "model" : "user", parts: [{ text: m.content }] })),
        generationConfig: { temperature: 0.5 }
      })
    });
    return (data?.candidates?.[0]?.content?.parts || []).map((p) => p.text || "").join("").trim();
  }
  throw new Error("Nha cung cap khong ho tro: " + ai.provider);
}
async function aiVaryText(ai, text) {
  if (!text || !text.trim()) return text;
  const system = "Viet lai NHE doan tin ban hang sau cho tu nhien, khac di mot chut ve cach dien dat. GIU NGUYEN: y nghia, gia tien, so dien thoai, duong link, ten san pham, emoji. KHONG them thong tin moi. Chi tra ve noi dung tin, khong giai thich.";
  const out = await aiChat(ai, system, text);
  return (out || text).trim();
}
async function aiCompose2(ai, prompt) {
  if (!prompt || !prompt.trim()) throw new Error("Chua nhap yeu cau.");
  const system = "Ban la chuyen gia viet content ban hang thoi trang nu tren Zalo/Facebook, giong tieng Viet tu nhien, thu hut, co emoji hop ly, ngan gon de doc. Chi tra ve noi dung bai dang, khong giai thich them.";
  return await aiChat(ai, system, prompt);
}
module.exports = {
  aiChat,
  aiTest: aiTest2,
  aiListModels: aiListModels2,
  aiEditMessage,
  aiCompose: aiCompose2,
  aiConverse: aiConverse2,
  aiVaryText,
  buildEditInstruction,
  resolveAI,
  DEFAULT_MODELS,
  BUILTIN_MODELS,
  providerLabel
};
