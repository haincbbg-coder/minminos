// MinMin HUD - "Chom sao" cac bo phan: moi node la mot mang viec cua cong ty.
// Node sang len khi MinMin goi dung cong cu cua mang do; mot tia sang chay tu loi ra node.

// Mang viec co dinh cua doanh nghiep thoi trang. `match` so voi TEN cong cu MinMin goi.
export const DOMAINS = [
  { key: "sales",    label: "Bán hàng",     tone: "warm", match: /pancake|pos\b|order|don_hang|don-hang|botcake/i },
  { key: "stock",    label: "Kho & đặt hàng", tone: "warm", match: /ton[-_ ]?kho|inventory|dat[-_]hang|stock|restock/i },
  { key: "ads",      label: "Quảng cáo",    tone: "warm", match: /meta[-_]ads|ads[-_]graph|adset|campaign|camp|tiktok[-_]ads|google[-_]ads/i },
  { key: "pages",    label: "Fanpage",      tone: "warm", match: /pages?[-_]graph|fanpage|facebook|post_|publish/i },
  { key: "cskh",     label: "CSKH · Zalo",  tone: "warm", match: /zalo|inbox|messenger|tu[-_]van/i },
  { key: "finance",  label: "Kế toán · Thuế", tone: "cool", match: /hoa[-_]don|invoice|thue|tax|ke[-_]toan|luong|payroll|loi[-_]nhuan|pnl/i },
  { key: "email",    label: "Email",        tone: "cool", match: /gmail|mail/i },
  { key: "memory",   label: "Trí nhớ",      tone: "cool", match: /memory|vault|brain|wiki|read|write|edit|glob|grep|file/i },
  { key: "schedule", label: "Lịch · Nhắc việc", tone: "cool", match: /schedule|reminder|cron|calendar|loop/i },
  { key: "jobs",     label: "Việc nền",     tone: "cool", match: /javis_task|kanban|javis_job|workflow|agent|task/i },
  { key: "research", label: "Nghiên cứu",   tone: "dim",  match: /web|search|fetch|youtube|browse/i },
  { key: "create",   label: "Sáng tạo",     tone: "dim",  match: /image|higgsfield|video|webcake|canva|design/i },
];

const TONES = { warm: "#ffa24a", cool: "#b294ff", dim: "#8c86b8", agent: "#6fe0c8" };

export function domainForTool(name) {
  const s = String(name || "");
  for (const d of DOMAINS) if (d.match.test(s)) return d.key;
  return null;
}

export class Constellation {
  constructor(canvas, opts = {}) {
    this.c = canvas;
    this.ctx = canvas.getContext("2d");
    this.onSelect = opts.onSelect || null;
    this.reduced = !!opts.reducedMotion;
    this.nodes = DOMAINS.map((d, i) => ({ ...d, color: TONES[d.tone], heat: 0, count: 0, i, kind: "domain" }));
    this.sparks = [];
    this.hover = null;
    this.thinking = false;
    this._t0 = performance.now();
    this.resize();
    window.addEventListener("resize", () => this.resize());
    canvas.addEventListener("pointermove", e => this._pick(e, false));
    // keo chuot de xoay nguoi thi khong tinh la bam vao node
    canvas.addEventListener("pointerdown", e => { this._down = [e.clientX, e.clientY]; });
    canvas.addEventListener("click", e => {
      if (this._down && Math.hypot(e.clientX - this._down[0], e.clientY - this._down[1]) > 6) return;
      this._pick(e, true);
    });
    this._loop = this._loop.bind(this);
    requestAnimationFrame(this._loop);
  }

  // Tro ly (agent) that trong brain: xep vong ngoai.
  setAgents(list) {
    this.nodes = this.nodes.filter(n => n.kind === "domain");
    (list || []).slice(0, 10).forEach((a, i) => {
      this.nodes.push({ key: "agent:" + a.slug, label: a.name || a.slug, color: TONES.agent, heat: 0, count: 0,
        kind: "agent", i, match: null, desc: a.description || "" });
    });
    this._layout();
  }

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.w = this.c.clientWidth || window.innerWidth; this.h = this.c.clientHeight || window.innerHeight;
    this.c.width = this.w * dpr; this.c.height = this.h * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this._layout();
  }

  _layout() {
    const cx = this.w / 2, cy = this.h * 0.44;
    const portraitScreen = this.w / this.h < 1;
    // chua cho hai cot bang (so lieu ben trai, nhat ky ben phai) va dong chu ben duoi
    const rx = portraitScreen ? this.w * 0.3 : Math.max(220, Math.min(this.w / 2 - 430, 560));
    const ry = Math.min(this.h * (portraitScreen ? 0.26 : 0.28), 320);
    // bo phan va tro ly xep chung mot vong, tro ly chen giua cac bo phan
    const dom = this.nodes.filter(n => n.kind === "domain");
    const ag = this.nodes.filter(n => n.kind === "agent");
    const all = [];
    const step = ag.length ? Math.max(1, Math.floor(dom.length / ag.length)) : dom.length + 1;
    let ai = 0;
    dom.forEach((n, i) => { all.push(n); if ((i + 1) % step === 0 && ai < ag.length) all.push(ag[ai++]); });
    while (ai < ag.length) all.push(ag[ai++]);
    all.forEach((n, i) => {
      const a = -Math.PI * 0.92 + (i / all.length) * Math.PI * 2;
      const wob = 1 + ((i * 37) % 7 - 3) * 0.022;
      n.x = cx + Math.cos(a) * rx * wob; n.y = cy + Math.sin(a) * ry * wob;
      n.a = a;
    });
    this.cx = cx; this.cy = cy;
  }

  // Ghi nhan mot lan goi cong cu: node sang + tia sang.
  pulse(key) {
    const n = this.nodes.find(x => x.key === key);
    if (!n) return;
    n.heat = 1; n.count++;
    this.sparks.push({ n, t: 0 });
  }
  setThinking(v) { this.thinking = !!v; }
  setVisible(v) { this.visible = !!v; this.c.style.pointerEvents = v ? "" : "none"; }

  _pick(e, click) {
    const r = this.c.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    let best = null, bd = 28;
    for (const n of this.nodes) { const d = Math.hypot(n.x - x, n.y - y); if (d < bd) { bd = d; best = n; } }
    this.hover = best;
    this.c.style.cursor = best ? "pointer" : "default";
    if (click && best && this.onSelect) this.onSelect(best);
  }

  _loop(now) {
    const t = (now - this._t0) / 1000;
    const g = this.ctx;
    g.clearRect(0, 0, this.w, this.h);
    if (this.visible === false) { requestAnimationFrame(this._loop); return; }
    const core = { x: this.cx, y: this.cy };

    // mach dan tu loi ra node: duong gap khuc kieu mach dien
    for (const n of this.nodes) {
      const heat = n.heat;
      g.strokeStyle = hexA(n.color, 0.10 + heat * 0.55 + (this.thinking ? 0.06 : 0));
      g.lineWidth = 1 + heat * 1.4;
      g.beginPath();
      const mx = core.x + (n.x - core.x) * 0.55, my = n.y;
      g.moveTo(core.x + Math.cos(n.a) * 150, core.y + Math.sin(n.a) * 120);
      g.lineTo(mx, my);
      g.lineTo(n.x, n.y);
      g.stroke();
    }

    // tia sang chay ra
    this.sparks = this.sparks.filter(s => s.t < 1);
    for (const s of this.sparks) {
      s.t += this.reduced ? 0.05 : 0.022;
      const n = s.n;
      const sx = core.x + Math.cos(n.a) * 150, sy = core.y + Math.sin(n.a) * 120;
      const mx = core.x + (n.x - core.x) * 0.55, my = n.y;
      const p = s.t < 0.5 ? lerp2(sx, sy, mx, my, s.t * 2) : lerp2(mx, my, n.x, n.y, (s.t - 0.5) * 2);
      const grd = g.createRadialGradient(p[0], p[1], 0, p[0], p[1], 14);
      grd.addColorStop(0, hexA("#fff2d8", 0.95)); grd.addColorStop(1, hexA(n.color, 0));
      g.fillStyle = grd; g.beginPath(); g.arc(p[0], p[1], 14, 0, Math.PI * 2); g.fill();
    }

    // node
    g.textBaseline = "middle";
    for (const n of this.nodes) {
      n.heat *= 0.985;
      const breathe = this.reduced ? 0 : Math.sin(t * 1.6 + n.i) * 0.15;
      const r = (n.kind === "agent" ? 4 : 5.5) + n.heat * 5 + breathe;
      const halo = g.createRadialGradient(n.x, n.y, 0, n.x, n.y, r * 4.5);
      halo.addColorStop(0, hexA(n.color, 0.45 + n.heat * 0.4)); halo.addColorStop(1, hexA(n.color, 0));
      g.fillStyle = halo; g.beginPath(); g.arc(n.x, n.y, r * 4.5, 0, Math.PI * 2); g.fill();
      g.fillStyle = n.heat > 0.3 ? "#fff4e0" : n.color;
      g.beginPath(); g.arc(n.x, n.y, r, 0, Math.PI * 2); g.fill();
      g.strokeStyle = hexA(n.color, 0.6); g.lineWidth = 1;
      g.beginPath(); g.arc(n.x, n.y, r + 5, 0, Math.PI * 2); g.stroke();

      g.font = `${n === this.hover ? 600 : 500} ${n.kind === "agent" ? 12 : 13}px "Be Vietnam Pro", system-ui, sans-serif`;
      const tw = g.measureText(n.label).width;
      let left = n.x < this.cx;
      if (left && n.x - 16 - tw < 8) left = false;
      if (!left && n.x + 16 + tw > this.w - 8) left = true;
      g.textAlign = left ? "right" : "left";
      g.fillStyle = hexA(n.heat > 0.3 ? "#ffe6c2" : "#e9e2ff", 0.62 + n.heat * 0.38 + (n === this.hover ? 0.3 : 0));
      g.fillText(n.label, n.x + (left ? -16 : 16), n.y);
      if (n.count) {
        g.font = `500 10px "JetBrains Mono", ui-monospace, monospace`;
        g.fillStyle = hexA(n.color, 0.85);
        g.fillText(`×${n.count}`, n.x + (left ? -16 : 16), n.y + 15);
      }
    }
    requestAnimationFrame(this._loop);
  }
}

function lerp2(ax, ay, bx, by, t) { return [ax + (bx - ax) * t, ay + (by - ay) * t]; }
function hexA(hex, a) {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map(c => c + c).join("") : h, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${Math.max(0, Math.min(1, a)).toFixed(3)})`;
}
