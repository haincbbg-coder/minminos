// Trich tu Zalo Forwarder v2.10.0 (TrungKienHa), chuyen sang chay tren web trong MinMin OS.
"use strict";
var fs8 = require("node:fs");
var path3 = require("node:path");
var { EventEmitter: EventEmitter2 } = require("node:events");
var { imageSize } = require("image-size");
var { applyRules: applyRules2 } = require("./transform");
var { aiEditMessage, aiVaryText, resolveAI } = require("./ai");
var { downloadToTmp, cleanup } = require("./media");
var zcaPromise = null;
function getZca() {
  if (!zcaPromise) zcaPromise = import("zca-js");
  return zcaPromise;
}
function sanitize(name) {
  return String(name).replace(/[\\/:*?"<>|]/g, "_").replace(/[\x00-\x1f]/g, "_").replace(/\s+/g, " ").trim() || "tai_khoan";
}
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}
function safeJsonParse(s) {
  if (typeof s !== "string") return {};
  try {
    return JSON.parse(s);
  } catch (_e) {
    return {};
  }
}
async function imageMetadataGetter(filePath) {
  const data = await fs8.promises.readFile(filePath);
  try {
    const dim = imageSize(new Uint8Array(data));
    return { height: dim.height || 0, width: dim.width || 0, size: data.length };
  } catch (_e) {
    return { height: 0, width: 0, size: data.length };
  }
}
// ---------- Moi truong dang nhap RIENG tung tai khoan (MinMin) ----------
// zca-js mac dinh dung CUNG mot user agent cho moi tai khoan, nen nhieu tai khoan tren mot may
// trong y het nhau. Moi tai khoan duoc gan co dinh mot trinh duyet (chon theo ten, luu vao
// session ngay lan dang nhap dau) va co the co proxy rieng, de moi tai khoan la mot "may" rieng.
var USER_AGENTS = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:143.0) Gecko/20100101 Firefox/143.0",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 OPR/122.0.0.0"
];
function pickUserAgent(name) {
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return USER_AGENTS[h % USER_AGENTS.length];
}
function cleanProxy(p) {
  const v = String(p || "").trim();
  if (!v) return "";
  if (!/^https?:\/\/\S+$/i.test(v)) throw new Error("Proxy khong hop le. Dang: http://user:pass@ip:port");
  return v;
}
async function proxyOptions(proxy) {
  if (!proxy) return {};
  // zca-js can node-fetch khi di qua proxy (fetch san cua Node bo qua agent).
  const { HttpsProxyAgent } = await import("https-proxy-agent");
  const nodeFetch = (await import("node-fetch")).default;
  return { agent: new HttpsProxyAgent(proxy), polyfill: nodeFetch };
}

var ZaloService2 = class extends EventEmitter2 {
  constructor(sessionDir2, tmpDir2) {
    super();
    this.sessionDir = sessionDir2;
    this.tmpDir = tmpDir2;
    fs8.mkdirSync(this.sessionDir, { recursive: true });
    fs8.mkdirSync(this.tmpDir, { recursive: true });
    this.apis = /* @__PURE__ */ new Map();
    this.forwarders = /* @__PURE__ */ new Map();
    this._sendLog = /* @__PURE__ */ new Map();
    this._loginAbort = null;
    this._cacheFile = path3.join(path3.dirname(this.sessionDir), "lists-cache.json");
    this._cache = { groups: {}, friends: {} };
    try {
      if (fs8.existsSync(this._cacheFile)) this._cache = JSON.parse(fs8.readFileSync(this._cacheFile, "utf8"));
    } catch (_e) {
    }
  }
  _saveCache() {
    try {
      fs8.writeFileSync(this._cacheFile, JSON.stringify(this._cache, null, 2), "utf8");
    } catch (_e) {
    }
  }
  // Xoa bo nho dem danh sach nhom/ban be cua 1 tai khoan (khi dang xuat / dang nhap lai)
  // de lan sau quet lai tu dau, tranh dung du lieu cu/rong.
  _clearListCache(name) {
    let changed = false;
    if (this._cache.groups && this._cache.groups[name]) {
      delete this._cache.groups[name];
      changed = true;
    }
    if (this._cache.friends && this._cache.friends[name]) {
      delete this._cache.friends[name];
      changed = true;
    }
    if (changed) this._saveCache();
  }
  log(level, msg) {
    this.emit("log", { level, msg, ts: Date.now() });
  }
  // ---------- Session ----------
  sessionPath(name) {
    return path3.join(this.sessionDir, sanitize(name) + ".json");
  }
  hasSession(name) {
    return fs8.existsSync(this.sessionPath(name));
  }
  readSession(name) {
    const p = this.sessionPath(name);
    if (!fs8.existsSync(p)) return null;
    try {
      return JSON.parse(fs8.readFileSync(p, "utf8"));
    } catch (_e) {
      return null;
    }
  }
  writeSession(s) {
    const p = this.sessionPath(s.name);
    fs8.writeFileSync(p, JSON.stringify(s, null, 2), "utf8");
    try {
      fs8.chmodSync(p, 384);
    } catch (_e) {
    }
  }
  deleteSession(name) {
    const p = this.sessionPath(name);
    if (fs8.existsSync(p)) fs8.unlinkSync(p);
    this.apis.delete(name);
    this._clearListCache(name);
  }
  listAccounts() {
    if (!fs8.existsSync(this.sessionDir)) return [];
    return fs8.readdirSync(this.sessionDir).filter((f) => f.endsWith(".json")).map((f) => {
      const name = f.replace(/\.json$/, "");
      const s = this.readSession(name) || {};
      return {
        name,
        uid: s.uid || null,
        displayName: s.displayName || null,
        savedAt: s.savedAt || null,
        proxy: !!s.proxy,
        connected: this.apis.has(name)
      };
    });
  }
  // ---------- Login ----------
  async _newZalo(proxy) {
    const { Zalo: Zalo2 } = await getZca();
    return new Zalo2({ imageMetadataGetter, ...(await proxyOptions(proxy)) });
  }
  /** Moi truong cua 1 tai khoan: user agent co dinh + proxy (neu co). */
  accountEnv(name, proxyOverride) {
    const s = this.readSession(name) || {};
    const proxy = proxyOverride !== undefined && proxyOverride !== null ? cleanProxy(proxyOverride) : (s.proxy || "");
    return { userAgent: s.userAgent || pickUserAgent(name), proxy };
  }
  setProxy(name, proxy) {
    const s = this.readSession(name);
    if (!s) throw new Error(`Chua co tai khoan "${name}".`);
    s.proxy = cleanProxy(proxy);
    this.writeSession(s);
    this.apis.delete(name);
    return { name, proxy: !!s.proxy };
  }
  /** Dang nhap QR. Phat su kien 'qr' (base64) va 'login-status'. */
  async loginQR(name, proxy) {
    const { LoginQRCallbackEventType: LoginQRCallbackEventType2 } = await getZca();
    const env = this.accountEnv(name, proxy);
    const zalo = await this._newZalo(env.proxy);
    const qrFile = path3.join(this.sessionDir, sanitize(name) + "-qr.png");
    this.log("info", `Dang tao ma QR cho "${name}"...`);
    const api = await zalo.loginQR({ qrPath: qrFile, userAgent: env.userAgent, language: "vi" }, (event) => {
      switch (event.type) {
        case LoginQRCallbackEventType2.QRCodeGenerated: {
          const img = event.data && event.data.image ? event.data.image : null;
          this.emit("qr", { account: name, image: img, file: qrFile });
          this.emit("login-status", { account: name, status: "qr", message: "Quet ma QR bang Zalo" });
          break;
        }
        case LoginQRCallbackEventType2.QRCodeScanned:
          this.emit("login-status", {
            account: name,
            status: "scanned",
            message: `Da quet: ${event.data && event.data.display_name}`,
            displayName: event.data && event.data.display_name
          });
          break;
        case LoginQRCallbackEventType2.QRCodeExpired:
          this.emit("login-status", { account: name, status: "expired", message: "QR het han, dang tao lai" });
          break;
        case LoginQRCallbackEventType2.QRCodeDeclined:
          this.emit("login-status", { account: name, status: "declined", message: "QR bi tu choi" });
          break;
        case LoginQRCallbackEventType2.GotLoginInfo:
          this.writeSession({
            name,
            imei: event.data.imei,
            userAgent: event.data.userAgent || env.userAgent,
            cookie: event.data.cookie,
            proxy: env.proxy,
            savedAt: (/* @__PURE__ */ new Date()).toISOString()
          });
          this.emit("login-status", { account: name, status: "got-info", message: "Da lay thong tin dang nhap" });
          break;
      }
    });
    this.apis.set(name, api);
    this._clearListCache(name);
    try {
      const uid = api.getOwnId();
      const s = this.readSession(name) || { name };
      s.uid = uid;
      this.writeSession(s);
    } catch (_e) {
    }
    try {
      if (fs8.existsSync(qrFile)) fs8.unlinkSync(qrFile);
    } catch (_e) {
    }
    this.emit("login-status", { account: name, status: "logged-in", message: "Dang nhap thanh cong" });
    this.log("ok", `Dang nhap thanh cong: ${name}`);
    return { name, uid: this.readSession(name) && this.readSession(name).uid };
  }
  /** Dang nhap lai tu session. */
  async connect(name) {
    if (this.apis.has(name)) return { name, already: true };
    const s = this.readSession(name);
    if (!s) throw new Error(`Chua co session cho "${name}". Hay dang nhap QR truoc.`);
    const zalo = await this._newZalo(s.proxy || "");
    const api = await zalo.login({ imei: s.imei, userAgent: s.userAgent, cookie: s.cookie, language: "vi" });
    this.apis.set(name, api);
    this.log("ok", `Da ket noi lai: ${name}`);
    return { name };
  }
  async ensureApi(name) {
    if (this.apis.has(name)) return this.apis.get(name);
    await this.connect(name);
    return this.apis.get(name);
  }
  // ---------- Features ----------
  // Danh sach nhom: co bo nho dem. refresh=true -> quet lai tu Zalo.
  async listGroups(name, refresh) {
    const cached = this._cache.groups[name];
    if (!refresh && cached && Array.isArray(cached.items) && cached.items.length) {
      return { items: cached.items, cachedAt: cached.cachedAt, fromCache: true };
    }
    const api = await this.ensureApi(name);
    let myUid = "";
    try {
      myUid = String((typeof api.getOwnId === "function" ? api.getOwnId() : "") || "");
    } catch (_e) {
    }
    let out = [];
    for (let attempt = 0; attempt < 4; attempt++) {
      let ids = [];
      try {
        const all = await api.getAllGroups();
        ids = Object.keys(all && all.gridVerMap || {});
      } catch (e) {
        this.log("warn", `[${name}] getAllGroups loi: ${e && e.message ? e.message : e}`);
      }
      out = [];
      const chunk = 50;
      for (let i = 0; i < ids.length; i += chunk) {
        try {
          const info = await api.getGroupInfo(ids.slice(i, i + chunk));
          for (const [gid, g] of Object.entries(info && info.gridInfoMap || {})) {
            const creatorId = g && g.creatorId ? String(g.creatorId) : "";
            const adminIds = g && Array.isArray(g.adminIds) ? g.adminIds.map(String) : [];
            let role = "member";
            if (myUid && creatorId && creatorId === myUid) role = "owner";
            else if (myUid && adminIds.includes(myUid)) role = "admin";
            out.push({
              id: gid,
              name: g && g.name || "(khong ten)",
              totalMember: g && g.totalMember || 0,
              role
            });
          }
        } catch (e) {
          this.log("warn", `[${name}] getGroupInfo loi 1 phan: ${e && e.message ? e.message : e}`);
        }
      }
      if (out.length) break;
      if (attempt < 3) {
        this.log("info", `[${name}] chua thay nhom, doi Zalo dong bo roi thu lai... (${attempt + 1}/4)`);
        await sleep(2500);
      }
    }
    out.sort((a, b) => a.name.localeCompare(b.name));
    if (out.length) {
      this._cache.groups[name] = { items: out, cachedAt: Date.now() };
      this._saveCache();
      return { items: out, cachedAt: Date.now(), fromCache: false };
    }
    return { items: [], cachedAt: Date.now(), fromCache: false, empty: true };
  }
  async listFriends(name, refresh) {
    const cached = this._cache.friends[name];
    if (!refresh && cached && Array.isArray(cached.items) && cached.items.length) {
      return { items: cached.items, cachedAt: cached.cachedAt, fromCache: true };
    }
    const api = await this.ensureApi(name);
    let out = [];
    for (let attempt = 0; attempt < 4; attempt++) {
      let friends = [];
      try {
        friends = await api.getAllFriends() || [];
      } catch (e) {
        this.log("warn", `[${name}] getAllFriends loi: ${e && e.message ? e.message : e}`);
      }
      out = friends.map((f) => ({ id: f.userId, name: f.displayName || f.zaloName || f.userId })).sort((a, b) => a.name.localeCompare(b.name));
      if (out.length) break;
      if (attempt < 3) {
        this.log("info", `[${name}] chua thay ban be, doi dong bo roi thu lai... (${attempt + 1}/4)`);
        await sleep(2500);
      }
    }
    if (out.length) {
      this._cache.friends[name] = { items: out, cachedAt: Date.now() };
      this._saveCache();
      return { items: out, cachedAt: Date.now(), fromCache: false };
    }
    return { items: [], cachedAt: Date.now(), fromCache: false, empty: true };
  }
  // Lay link moi nhom (theo yeu cau tung nhom, co the cham/khong co).
  async getGroupLink(name, groupId) {
    const api = await this.ensureApi(name);
    try {
      let r;
      if (typeof api.getGroupLinkDetail === "function") r = await api.getGroupLinkDetail(groupId);
      else if (typeof api.getGroupLinkInfo === "function") r = await api.getGroupLinkInfo({ groupId });
      const link = r && (r.link || r.url || r.data && (r.data.link || r.data.url)) || "";
      return { ok: !!link, link: link || "" };
    } catch (e) {
      return { ok: false, reason: e.message };
    }
  }
  // ---------- Dang tin hang loat vao cac nhom minh quan tri ----------
  // opts: { targets:[{id,name}], text, images:[path], aiVary, ai, minDelayMs, maxDelayMs }
  async broadcast(account, opts) {
    const o = opts || {};
    const targets = Array.isArray(o.targets) ? o.targets : [];
    if (!targets.length) throw new Error("Chua chon nhom dich.");
    const api = await this.ensureApi(account);
    const tt = await this._threadType(o.kind === "user" ? "user" : "group");
    const images = Array.isArray(o.images) ? o.images : [];
    const minD = o.minDelayMs != null ? o.minDelayMs : 4e3;
    const maxD = o.maxDelayMs != null ? o.maxDelayMs : 9e3;
    const rand = () => Math.floor(minD + Math.random() * Math.max(0, maxD - minD));
    const results = [];
    this.log("info", `[${account}] bat dau dang toi ${targets.length} nhom...`);
    for (let i = 0; i < targets.length; i++) {
      const t = targets[i] || {};
      const label = t.name || t.id;
      try {
        let msg = o.text || "";
        if (o.aiVary && o.ai && o.ai.provider && o.ai.apiKey && msg.trim()) {
          try {
            msg = await aiVaryText(o.ai, o.text || "");
          } catch (e) {
            this.log("warn", `[${account}] AI doi text loi (${e.message}) -> dung ban goc`);
          }
        }
        const payload = { msg };
        if (images.length) payload.attachments = images.slice();
        await api.sendMessage(payload, t.id, tt);
        this._recordSend(account);
        this.log("ok", `[${account}] da dang -> ${label} (${i + 1}/${targets.length})`);
        this.emit("broadcast-progress", { account, index: i, total: targets.length, id: t.id, name: t.name, ok: true });
        results.push({ id: t.id, ok: true });
      } catch (e) {
        this.log("error", `[${account}] dang loi -> ${label}: ${e.message}`);
        this.emit("broadcast-progress", { account, index: i, total: targets.length, id: t.id, name: t.name, ok: false, error: e.message });
        results.push({ id: t.id, ok: false, error: e.message });
      }
      if (i < targets.length - 1) await sleep(rand());
    }
    const sent = results.filter((r) => r.ok).length;
    this.log("ok", `[${account}] dang xong: ${sent}/${targets.length} nhom.`);
    this.emit("broadcast-done", { account, total: targets.length, sent });
    return results;
  }
  async _threadType(type) {
    const { ThreadType: ThreadType2 } = await getZca();
    return type === "user" ? ThreadType2.User : ThreadType2.Group;
  }
  async sendText(name, threadId, type, text) {
    const api = await this.ensureApi(name);
    return api.sendMessage({ msg: text }, threadId, await this._threadType(type));
  }
  // ---------- Forwarding ----------
  parseMessage(msgType, content) {
    if (typeof content === "string") return { kind: "text", text: content };
    const c = content || {};
    const caption = c.title || c.description || "";
    const href = c.href || "";
    const thumb = c.thumb || "";
    const params = safeJsonParse(c.params);
    const mt = (msgType || "").toLowerCase();
    if (mt.includes("video")) {
      return {
        kind: "video",
        text: caption,
        videoUrl: href,
        thumbUrl: thumb || params.thumb || "",
        duration: Number(params.duration || params.dur || 0) || void 0,
        width: Number(params.width || params.w || 0) || void 0,
        height: Number(params.height || params.h || 0) || void 0
      };
    }
    if (mt.includes("photo") || mt.includes("image") || mt.includes("gif") || mt.includes("pic")) {
      return { kind: "image", text: caption, imageUrl: href };
    }
    if (href) return { kind: "file", text: caption, imageUrl: href };
    return { kind: "other", text: caption };
  }
  _passesKeyword(text, route) {
    const t = (text || "").toLowerCase();
    if (route.includeKeywords && route.includeKeywords.length) {
      if (!route.includeKeywords.some((k) => t.includes(String(k).toLowerCase()))) return false;
    }
    if (route.excludeKeywords && route.excludeKeywords.length) {
      if (route.excludeKeywords.some((k) => t.includes(String(k).toLowerCase()))) return false;
    }
    return true;
  }
  async _sendToDest(account, dest, parsed, editedText) {
    const api = await this.ensureApi(account);
    const tt = await this._threadType(dest.type);
    if (parsed.kind === "text") {
      await api.sendMessage({ msg: editedText }, dest.threadId, tt);
    } else if ((parsed.kind === "image" || parsed.kind === "file") && parsed.imageUrl) {
      const file = await downloadToTmp(parsed.imageUrl, this.tmpDir, ".jpg");
      try {
        await api.sendMessage({ msg: editedText || "", attachments: [file] }, dest.threadId, tt);
      } finally {
        cleanup(file);
      }
    } else if (parsed.kind === "video" && parsed.videoUrl) {
      await api.sendVideo(
        {
          msg: editedText || "",
          videoUrl: parsed.videoUrl,
          thumbnailUrl: parsed.thumbUrl || parsed.videoUrl,
          duration: parsed.duration,
          width: parsed.width,
          height: parsed.height
        },
        dest.threadId,
        tt
      );
    } else {
      return false;
    }
    return true;
  }
  // ---------- Gioi han gui (chong spam) ----------
  getLimits(config, account) {
    const d = config.sending || {};
    const o = config.accountOverrides && config.accountOverrides[account] || {};
    const pick = (a, b, def) => {
      const v = a != null && a !== "" ? a : b;
      const n = Number(v);
      return v == null || v === "" || isNaN(n) ? def : n;
    };
    return {
      minDelayMs: pick(o.minDelayMs, d.minDelayMs, 3e3),
      maxDelayMs: pick(o.maxDelayMs, d.maxDelayMs, 7e3),
      maxPerHour: pick(o.maxPerHour, d.maxPerHour, 0),
      maxPerDay: pick(o.maxPerDay, d.maxPerDay, 0)
    };
  }
  _counts(account) {
    const now = Date.now();
    const arr = (this._sendLog.get(account) || []).filter((t) => now - t < 864e5);
    this._sendLog.set(account, arr);
    return { hour: arr.filter((t) => now - t < 36e5).length, day: arr.length };
  }
  _canSend(account, limits) {
    const { hour, day } = this._counts(account);
    if (limits.maxPerHour > 0 && hour >= limits.maxPerHour)
      return { ok: false, reason: `da dat gioi han ${limits.maxPerHour} tin/gio` };
    if (limits.maxPerDay > 0 && day >= limits.maxPerDay)
      return { ok: false, reason: `da dat gioi han ${limits.maxPerDay} tin/ngay` };
    return { ok: true };
  }
  _recordSend(account) {
    const arr = this._sendLog.get(account) || [];
    arr.push(Date.now());
    this._sendLog.set(account, arr);
    const c = this._counts(account);
    this.emit("stats", { account, hour: c.hour, day: c.day });
  }
  _randDelay(limits) {
    const min = Math.max(0, limits.minDelayMs || 0);
    const max = Math.max(min, limits.maxDelayMs || min);
    return Math.floor(min + Math.random() * (max - min));
  }
  // ---------- Chuyen tiep (da luong theo tung tai khoan) ----------
  async startForwarding(account, config) {
    if (this.forwarders.has(account)) throw new Error(`Tai khoan "${account}" dang chay roi.`);
    const api = await this.ensureApi(account);
    const ruleSets = config.ruleSets || {};
    const limits = this.getLimits(config, account);
    const ALBUM_WINDOW_MS = config.albumWindowMs || 2500;
    const routeAccount = (r) => r.account || config.account;
    const routesForAccount = () => (config.routes || []).filter((r) => r.enabled !== false && routeAccount(r) === account);
    const sources = /* @__PURE__ */ new Set();
    for (const r of routesForAccount()) for (const s of r.sources || []) sources.add(s);
    if (sources.size === 0)
      throw new Error(`Tai khoan "${account}" chua co tuyen nao bat (hoac tuyen thieu nhom nguon).`);
    const matchRoutes = (threadId) => routesForAccount().filter((r) => (r.sources || []).includes(threadId));
    const aiConfig = config.ai || null;
    const editText = async (rs, text) => {
      if (rs && rs.useAI && aiConfig) {
        const resolved = resolveAI(aiConfig, rs.ai);
        if (resolved.provider && resolved.apiKey) {
          try {
            return await aiEditMessage(resolved, rs, text || "");
          } catch (e) {
            this.log("warn", `[${account}] AI bien tap loi (${e.message}) -> dung quy tac thuong`);
          }
        }
      }
      return applyRules2(text || "", rs);
    };
    const deliver = async (dest, label, sendFn) => {
      const st = this.forwarders.get(account);
      if (!st) return;
      if (st.paused) return;
      const can = this._canSend(account, limits);
      if (!can.ok) {
        this.log("warn", `[${account}] bo qua ${dest.type}:${dest.threadId} (${can.reason})`);
        return;
      }
      try {
        await sendFn();
        this._recordSend(account);
        this.log("ok", `  -> ${label}`);
        this.emit("forwarded", { account, dest });
      } catch (err2) {
        this.log("error", `  -> loi gui ${dest.type}:${dest.threadId}: ${err2.message}`);
      }
      await sleep(this._randDelay(limits));
    };
    const albumBuffers = /* @__PURE__ */ new Map();
    let chain = Promise.resolve();
    const enqueue = (fn) => {
      chain = chain.then(fn).catch((e) => this.log("error", `[${account}] xu ly tin loi: ${e && e.message ? e.message : e}`));
      return chain;
    };
    const flushAlbum = async (threadId) => {
      const buf = albumBuffers.get(threadId);
      if (!buf) return;
      albumBuffers.delete(threadId);
      if (buf.timer) clearTimeout(buf.timer);
      if (!buf.items.length) return;
      const files = [];
      for (const it of buf.items) {
        try {
          files.push(await downloadToTmp(it.imageUrl, this.tmpDir, ".jpg"));
        } catch (e) {
          this.log("error", "Tai anh loi: " + e.message);
        }
      }
      if (!files.length) return;
      for (const route of matchRoutes(threadId)) {
        if (!route.forward.image) continue;
        if (!this._passesKeyword(buf.caption, route)) continue;
        this.log(
          "info",
          `[${account}][${route.name}] album ${files.length} anh -> ${route.destinations.length} dich`
        );
        for (const dest of route.destinations) {
          const rs = ruleSets[dest.ruleSet] || ruleSets[route.ruleSet];
          const editedText = await editText(rs, buf.caption || "");
          const tt = await this._threadType(dest.type);
          await deliver(
            dest,
            `album ${files.length} anh -> ${dest.type}:${dest.threadId}`,
            () => api.sendMessage({ msg: editedText || "", attachments: files }, dest.threadId, tt)
          );
        }
      }
      for (const f of files) cleanup(f);
    };
    const processSingle = async (threadId, parsed) => {
      for (const route of matchRoutes(threadId)) {
        const kindOk = parsed.kind === "text" && route.forward.text || parsed.kind === "video" && route.forward.video || parsed.kind === "file" && route.forward.file;
        if (!kindOk) continue;
        if (!this._passesKeyword(parsed.text, route)) continue;
        this.log(
          "info",
          `[${account}][${route.name}] tin moi (${parsed.kind}) -> ${route.destinations.length} dich`
        );
        for (const dest of route.destinations) {
          const rs = ruleSets[dest.ruleSet] || ruleSets[route.ruleSet];
          const editedText = await editText(rs, parsed.text || "");
          const tt = await this._threadType(dest.type);
          if (parsed.kind === "text") {
            await deliver(
              dest,
              `text -> ${dest.type}:${dest.threadId}`,
              () => api.sendMessage({ msg: editedText }, dest.threadId, tt)
            );
          } else if (parsed.kind === "video" && parsed.videoUrl) {
            await deliver(
              dest,
              `video -> ${dest.type}:${dest.threadId}`,
              () => api.sendVideo(
                {
                  msg: editedText || "",
                  videoUrl: parsed.videoUrl,
                  thumbnailUrl: parsed.thumbUrl || parsed.videoUrl,
                  duration: parsed.duration,
                  width: parsed.width,
                  height: parsed.height
                },
                dest.threadId,
                tt
              )
            );
          } else if (parsed.kind === "file" && parsed.imageUrl) {
            await deliver(dest, `file -> ${dest.type}:${dest.threadId}`, async () => {
              const f = await downloadToTmp(parsed.imageUrl, this.tmpDir, ".dat");
              try {
                await api.sendMessage({ msg: editedText || "", attachments: [f] }, dest.threadId, tt);
              } finally {
                cleanup(f);
              }
            });
          }
        }
      }
    };
    const handler = (message) => {
      try {
        if (message.isSelf) return;
        const threadId = message.threadId;
        if (!sources.has(threadId)) return;
        const data = message.data || {};
        const parsed = this.parseMessage(data.msgType || "", data.content);
        if (parsed.kind === "image" && parsed.imageUrl) {
          if (!matchRoutes(threadId).some((r) => r.forward.image)) return;
          let buf = albumBuffers.get(threadId);
          if (!buf) {
            buf = { items: [], caption: "", timer: null };
            albumBuffers.set(threadId, buf);
          }
          buf.items.push(parsed);
          if (!buf.caption && parsed.text) buf.caption = parsed.text;
          if (buf.timer) clearTimeout(buf.timer);
          buf.timer = setTimeout(() => {
            enqueue(() => flushAlbum(threadId));
          }, ALBUM_WINDOW_MS);
          return;
        }
        if (albumBuffers.has(threadId)) {
          const buf = albumBuffers.get(threadId);
          if (buf && buf.timer) clearTimeout(buf.timer);
          enqueue(() => flushAlbum(threadId));
        }
        enqueue(() => processSingle(threadId, parsed));
      } catch (err2) {
        this.log("error", "Loi xu ly tin: " + err2.message);
      }
    };
    api.listener.on("message", handler);
    api.listener.on(
      "error",
      (e) => this.log("error", `[${account}] listener loi: ` + (e && e.message ? e.message : e))
    );
    api.listener.start();
    this.forwarders.set(account, { account, sources, config, handler, albumBuffers, paused: false });
    this.log(
      "ok",
      `[${account}] bat dau nghe ${sources.size} nhom nguon | tre ${limits.minDelayMs}-${limits.maxDelayMs}ms | gioi han ${limits.maxPerHour || "khong"}/gio, ${limits.maxPerDay || "khong"}/ngay`
    );
    this.emit("forwarding-status", this.forwardingStatus());
  }
  async stopForwarding(account) {
    const f = this.forwarders.get(account);
    if (!f) return;
    if (f.albumBuffers) {
      for (const buf of f.albumBuffers.values()) if (buf.timer) clearTimeout(buf.timer);
      f.albumBuffers.clear();
    }
    const api = this.apis.get(account);
    try {
      if (api && api.listener) {
        if (typeof api.listener.stop === "function") api.listener.stop();
        api.listener.removeAllListeners("message");
      }
    } catch (_e) {
    }
    this.forwarders.delete(account);
    this.log("info", `[${account}] da dung chuyen tiep.`);
    this.emit("forwarding-status", this.forwardingStatus());
  }
  pauseForwarding(account) {
    const f = this.forwarders.get(account);
    if (!f) return;
    f.paused = true;
    this.log("info", `[${account}] da TAM DUNG (van ket noi, khong chuyen tin).`);
    this.emit("forwarding-status", this.forwardingStatus());
  }
  resumeForwarding(account) {
    const f = this.forwarders.get(account);
    if (!f) return;
    f.paused = false;
    this.log("ok", `[${account}] da TIEP TUC chuyen tin.`);
    this.emit("forwarding-status", this.forwardingStatus());
  }
  async startAll(config) {
    const accounts = /* @__PURE__ */ new Set();
    for (const r of config.routes || []) {
      if (r.enabled === false) continue;
      accounts.add(r.account || config.account);
    }
    const started = [];
    const errors = [];
    for (const acc of accounts) {
      if (!acc || this.forwarders.has(acc)) continue;
      try {
        await this.startForwarding(acc, config);
        started.push(acc);
      } catch (e) {
        errors.push(`${acc}: ${e.message}`);
        this.log("error", `Khong the chay ${acc}: ${e.message}`);
      }
    }
    if (started.length === 0 && errors.length) throw new Error(errors.join("; "));
    return { started, errors };
  }
  async stopAll() {
    for (const acc of Array.from(this.forwarders.keys())) await this.stopForwarding(acc);
  }
  forwardingStatus() {
    const running = Array.from(this.forwarders.keys());
    const counts = {};
    const paused = {};
    for (const acc of running) {
      counts[acc] = this._counts(acc);
      paused[acc] = !!(this.forwarders.get(acc) && this.forwarders.get(acc).paused);
    }
    return { running, counts, paused };
  }
  isForwarding(account) {
    return account ? this.forwarders.has(account) : this.forwarders.size > 0;
  }
};
module.exports = { ZaloService: ZaloService2, pickUserAgent, cleanProxy };
