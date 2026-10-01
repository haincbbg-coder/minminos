"use strict";
/* Zalo Forwarder chay tren web (MinMin OS 26.10.4).
 *
 * Tien trinh Node rieng, CHI nghe 127.0.0.1, moi yeu cau phai mang header x-zf-token dung
 * (MinMin sinh ngau nhien moi lan khoi dong). Trinh duyet KHONG goi thang vao day: MinMin dung
 * truoc, kiem tra dang nhap MinMin + ma kich hoat + dong y dieu khoan Zalo roi moi chuyen tiep.
 *
 *   POST /rpc/<ham>      body {"args":[...]} -> {"ok":true,"result":...} | {"ok":false,"error":"..."}
 *   GET  /events         Server-Sent Events: log, qr, login-status, forwarding-status, ...
 *   POST /upload?ten=..  than = byte cua 1 anh -> {"ok":true,"path":"..."} (de dang nhom hang loat)
 *   GET  /health
 *
 * Bien moi truong: ZF_PORT, ZF_TOKEN, ZF_DATA (thu muc du lieu: sessions, config, tmp, uploads).
 * Khong dung ky tu em dash. */
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { ZaloService } = require("./core/zalo-service");
const { aiTest, aiCompose, aiListModels, aiConverse } = require("./core/ai");
const { applyRules } = require("./core/transform");

const PORT = Number(process.env.ZF_PORT || 0);
const TOKEN = String(process.env.ZF_TOKEN || "");
const DATA = path.resolve(process.env.ZF_DATA || path.join(__dirname, ".data"));
if (!TOKEN || TOKEN.length < 16) {
  console.error("ZF_TOKEN thieu hoac qua ngan");
  process.exit(2);
}

const P = {
  config: path.join(DATA, "config.json"),
  sessions: path.join(DATA, "sessions"),
  tmp: path.join(DATA, "tmp"),
  uploads: path.join(DATA, "uploads"),
  running: path.join(DATA, "dang-chay.json"),
};
for (const d of [DATA, P.sessions, P.tmp, P.uploads]) fs.mkdirSync(d, { recursive: true });
try { fs.chmodSync(P.sessions, 0o700); } catch (_e) {}

const DEFAULT_CONFIG = {
  account: "",
  defaultIntervalMs: 1500,
  sending: { minDelayMs: 3000, maxDelayMs: 7000, maxPerHour: 0, maxPerDay: 0 },
  accountOverrides: {},
  routes: [],
  ruleSets: {
    default: {
      brand: { enabled: false, caseInsensitive: true, map: {} },
      price: { enabled: false, mode: "add_amount", amount: 0, round: 1000, map: {} },
      link: { enabled: false, action: "remove", replaceWith: "" },
      custom: [],
      prependText: "",
      appendText: "",
    },
  },
};

function loadConfig() {
  try {
    if (fs.existsSync(P.config)) return JSON.parse(fs.readFileSync(P.config, "utf8"));
  } catch (_e) {}
  return JSON.parse(JSON.stringify(DEFAULT_CONFIG));
}
function saveConfig(cfg) {
  if (!cfg || typeof cfg !== "object" || Array.isArray(cfg)) throw new Error("Cau hinh khong hop le");
  const tam = P.config + ".tmp";
  fs.writeFileSync(tam, JSON.stringify(cfg, null, 2), { encoding: "utf8", mode: 0o600 });
  fs.renameSync(tam, P.config);
  return true;
}

// Anh dang nhom chi duoc lay tu thu muc uploads: khong cho trinh duyet chi dinh file bat ky
// tren may chu (vd tep bi mat) roi gui no len Zalo.
function anhHopLe(list) {
  const goc = fs.realpathSync(P.uploads) + path.sep;
  return (Array.isArray(list) ? list : []).map((p) => {
    const thuc = fs.realpathSync(path.resolve(P.uploads, path.basename(String(p))));
    if (!thuc.startsWith(goc)) throw new Error("Anh khong hop le");
    return thuc;
  });
}

const service = new ZaloService(P.sessions, P.tmp);

// ---------- Su kien -> SSE ----------
const clients = new Set();
const ganDay = []; // 150 log gan nhat, de mo trang la thay ngay
function phat(kenh, data) {
  if (kenh === "log") {
    ganDay.push(data);
    if (ganDay.length > 150) ganDay.shift();
  }
  const goi = `event: ${kenh}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const res of clients) {
    try { res.write(goi); } catch (_e) {}
  }
}
for (const k of ["log", "qr", "login-status", "forwarding-status", "forwarded", "stats", "broadcast-progress", "broadcast-done"]) {
  service.on(k, (d) => phat(k, d));
}
// Nho tai khoan nao dang chuyen tiep, de MinMin khoi dong lai (cap nhat, mat dien) thi chay tiep.
let dangTat = false;
service.on("forwarding-status", (st) => {
  // Luc tat may (cap nhat MinMin) stopAll se bao "khong con gi chay": giu nguyen danh sach cu.
  if (dangTat) return;
  try {
    fs.writeFileSync(P.running, JSON.stringify({ running: (st && st.running) || [], luc: Date.now() }), "utf8");
  } catch (_e) {}
});

const RPC = {
  loadConfig: () => loadConfig(),
  saveConfig: (cfg) => saveConfig(cfg),
  listAccounts: () => service.listAccounts(),
  loginQR: (name, proxy) => service.loginQR(String(name || "").trim(), proxy),
  connect: (name) => service.connect(name),
  deleteAccount: (name) => { service.deleteSession(name); return true; },
  setProxy: (name, proxy) => service.setProxy(name, proxy),
  listGroups: (account, refresh) => service.listGroups(account, !!refresh),
  listFriends: (account, refresh) => service.listFriends(account, !!refresh),
  getGroupLink: (account, groupId) => service.getGroupLink(account, groupId),
  sendTest: (p) => service.sendText(p.account, p.threadId, p.type, p.text),
  startAll: (cfg) => service.startAll(cfg || loadConfig()),
  startAccount: async (cfg, account) => { await service.startForwarding(account, cfg || loadConfig()); return true; },
  stopAccount: async (account) => { await service.stopForwarding(account); return true; },
  pauseAccount: (account) => { service.pauseForwarding(account); return true; },
  resumeAccount: (account) => { service.resumeForwarding(account); return true; },
  stopAll: async () => { await service.stopAll(); return true; },
  forwardStatus: () => service.forwardingStatus(),
  aiTest: (ai) => aiTest(ai),
  aiCompose: (ai, prompt) => aiCompose(ai, prompt),
  aiListModels: (ai) => aiListModels(ai),
  aiChat: (ai, history) => aiConverse(ai, history),
  previewRules: (text, ruleSet) => {
    try { return applyRules(text || "", ruleSet || {}); } catch (e) { return "(loi bien tap: " + e.message + ")"; }
  },
  broadcastSend: (account, opts) => {
    const o = Object.assign({}, opts || {});
    o.images = anhHopLe(o.images);
    return service.broadcast(account, o);
  },
};

function docThan(req, gioiHan) {
  return new Promise((resolve, reject) => {
    const parts = [];
    let n = 0;
    req.on("data", (c) => {
      n += c.length;
      if (n > gioiHan) { reject(new Error("Du lieu qua lon")); req.destroy(); return; }
      parts.push(c);
    });
    req.on("end", () => resolve(Buffer.concat(parts)));
    req.on("error", reject);
  });
}
function json(res, code, obj) {
  const b = Buffer.from(JSON.stringify(obj === undefined ? null : obj));
  res.writeHead(code, { "content-type": "application/json; charset=utf-8", "content-length": b.length });
  res.end(b);
}
function dungToken(req) {
  const a = Buffer.from(String(req.headers["x-zf-token"] || ""));
  const b = Buffer.from(TOKEN);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://127.0.0.1");
  if (url.pathname === "/health") return json(res, 200, { ok: true });
  if (!dungToken(req)) return json(res, 401, { ok: false, error: "unauthorized" });

  if (req.method === "GET" && url.pathname === "/events") {
    res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });
    res.write(`event: hello\ndata: ${JSON.stringify({ status: service.forwardingStatus(), log: ganDay })}\n\n`);
    clients.add(res);
    const nhip = setInterval(() => { try { res.write(": ping\n\n"); } catch (_e) {} }, 20000);
    req.on("close", () => { clearInterval(nhip); clients.delete(res); });
    return;
  }

  if (req.method === "POST" && url.pathname === "/upload") {
    try {
      const buf = await docThan(req, 20 * 1024 * 1024);
      const ext = (path.extname(String(url.searchParams.get("ten") || "")).toLowerCase().match(/^\.(jpe?g|png|gif|webp)$/) || [".jpg"])[0];
      const ten = crypto.randomBytes(10).toString("hex") + ext;
      fs.writeFileSync(path.join(P.uploads, ten), buf);
      return json(res, 200, { ok: true, path: ten });
    } catch (e) {
      return json(res, 400, { ok: false, error: e.message });
    }
  }

  const m = url.pathname.match(/^\/rpc\/([A-Za-z]+)$/);
  if (req.method === "POST" && m) {
    const fn = RPC[m[1]];
    if (!fn) return json(res, 404, { ok: false, error: "khong co ham " + m[1] });
    let args = [];
    try {
      const raw = await docThan(req, 5 * 1024 * 1024);
      const body = raw.length ? JSON.parse(raw.toString("utf8")) : {};
      args = Array.isArray(body.args) ? body.args : [];
    } catch (e) {
      return json(res, 400, { ok: false, error: "than yeu cau sai: " + e.message });
    }
    try {
      const result = await fn(...args);
      return json(res, 200, { ok: true, result: result === undefined ? null : result });
    } catch (e) {
      return json(res, 200, { ok: false, error: (e && e.message) || String(e) });
    }
  }
  return json(res, 404, { ok: false, error: "not found" });
});
// Dang nhap QR doi nguoi dung quet, co the vai phut: khong cat ngang.
server.requestTimeout = 0;
server.headersTimeout = 60000;

function donRac() {
  const han = Date.now() - 7 * 864e5;
  for (const d of [P.uploads, P.tmp]) {
    for (const f of fs.readdirSync(d)) {
      try {
        const p = path.join(d, f);
        if (fs.statSync(p).mtimeMs < han) fs.unlinkSync(p);
      } catch (_e) {}
    }
  }
}

async function chayLai() {
  let ds = [];
  try { ds = (JSON.parse(fs.readFileSync(P.running, "utf8")).running || []).filter(Boolean); } catch (_e) {}
  if (!ds.length) return;
  const cfg = loadConfig();
  for (const acc of ds) {
    try {
      await service.startForwarding(acc, cfg);
    } catch (e) {
      service.log("error", `Khong chay lai duoc ${acc}: ${e.message}`);
    }
  }
}

server.listen(PORT, "127.0.0.1", () => {
  const port = server.address().port;
  // Dong dau tien ra stdout la cong that: MinMin doc dong nay de biet noi goi vao.
  process.stdout.write(`ZF_READY ${port}\n`);
  try { donRac(); } catch (_e) {}
  chayLai();
});

async function tat() {
  if (dangTat) return;
  dangTat = true;
  try { await service.stopAll(); } catch (_e) {}
  process.exit(0);
}
process.on("SIGTERM", tat);
process.on("SIGINT", tat);
// Mat ket noi voi MinMin (MinMin chet) thi tu tat, khong de mo coi.
process.stdin.on("end", tat);
process.stdin.resume();
