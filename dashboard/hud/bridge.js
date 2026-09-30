// MinMin HUD - cau noi voi may chu MinMin qua WebSocket /ws san co.
// Kenh /ws phat moi su kien cua moi luot (ke ca luot bo go o trang chinh hoac Telegram), nen HUD
// chi can nghe la thay MinMin dang nghi gi, goi cong cu nao, tra loi gi.

export class Bridge {
  constructor(handlers = {}) {
    this.h = handlers;
    this.ws = null;
    this.up = false;
    this.brain = handlers.brain || "brain";
    this._retry = 1500;
  }

  connect() {
    const proto = location.protocol === "https:" ? "wss://" : "ws://";
    let ws;
    try { ws = new WebSocket(proto + location.host + "/ws"); } catch (e) { this._later(); return; }
    this.ws = ws;
    ws.onopen = () => { this._retry = 1500; };
    ws.onclose = (e) => {
      this.up = false;
      this.h.onConnection && this.h.onConnection(false, e.code === 1008 ? "auth" : "down");
      if (e.code !== 1008) this._later();
    };
    ws.onmessage = (e) => { let d; try { d = JSON.parse(e.data); } catch (x) { return; } this._route(d); };
  }

  _later() { setTimeout(() => this.connect(), this._retry); this._retry = Math.min(this._retry * 1.6, 15000); }

  _route(d) {
    const h = this.h;
    switch (d.type) {
      case "hello":
        this.up = true;
        h.onConnection && h.onConnection(true);
        h.onRunning && h.onRunning((d.running || []).length);
        break;
      case "user_text": h.onUser && h.onUser(d.session_id, d.content || d.text || ""); break;
      case "status": h.onStatus && h.onStatus(d.session_id, d.content || d.text || ""); break;
      case "tool_call": h.onTool && h.onTool(d.session_id, d.tool || d.name || "", d); break;
      case "tool_result": h.onToolResult && h.onToolResult(d.session_id, d); break;
      case "stream": h.onStream && h.onStream(d.session_id, d.content || ""); break;
      case "response": h.onResponse && h.onResponse(d.session_id, d.content || "", d); break;
      case "turn_done": h.onDone && h.onDone(d.session_id, d); break;
      case "error": h.onError && h.onError(d.session_id, d.content || ""); break;
      case "inbox": case "push": h.onNotice && h.onNotice(d); break;
      default: break;
    }
  }

  // Gui mot cau lenh nhu khi bo go o khung chat; `voice: true` de MinMin tra loi ngan gon kieu noi.
  send(text, sessionId) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
    const ctx = "[KÊNH: HUD màn phụ, người dùng nói bằng giọng. Trả lời ngắn gọn như đang nói, không bảng biểu.]";
    this.ws.send(JSON.stringify({ message: `${ctx}\n\n${text}`, brain: this.brain, session_id: sessionId, voice: true, voice_input: true }));
    return true;
  }

  // Gui kem MOT anh (khung hinh camera / net ve): tai len /upload nhu khung chat, roi gui
  // lenh kem duong dan de MinMin doc anh. Tra ve true/false; loi thi ly do trong this.loi.
  async sendWithImage(text, sessionId, blob) {
    this.loi = "";
    try {
      const fd = new FormData();
      const ten = `hud-camera-${new Date().toISOString().replace(/[:.]/g, "-")}.jpg`;
      fd.append("file", blob, ten);
      fd.append("brain", this.brain);
      const r = await fetch("/upload", { method: "POST", body: fd, credentials: "same-origin" });
      const j = await r.json().catch(() => ({}));
      if (!r.ok || !j.ok) { this.loi = j.error || ("Tải ảnh lên lỗi " + r.status); return false; }
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) { this.loi = "Mất kết nối tới MinMin"; return false; }
      const ctx = "[KÊNH: HUD màn phụ, người dùng nói bằng giọng. Trả lời ngắn gọn như đang nói, không bảng biểu.]\n" +
        `[Ảnh chụp từ CAMERA của HUD vừa xong (đường dẫn):\n- ${j.staged}\n` +
        "Đây là cảnh THẬT trước camera của người dùng (có thể kèm nét vẽ tay màu cam). Xem ảnh rồi trả lời đúng câu hỏi. " +
        "Chỉ đọc, KHÔNG tự lưu ảnh đi đâu.]";
      this.ws.send(JSON.stringify({ message: `${ctx}\n\n${text}`, brain: this.brain, session_id: sessionId, voice: true, voice_input: true }));
      return true;
    } catch (e) { this.loi = e.message || String(e); return false; }
  }

  stop(sessionId) {
    try { this.ws && this.ws.send(JSON.stringify({ action: "stop", session_id: sessionId })); } catch (e) {}
  }
}

// ---- Du lieu phu (khong co thi an di, khong bao loi) ----
export async function fetchAgents(brain) {
  try {
    const r = await fetch(`/agents?brain=${encodeURIComponent(brain)}&prompt=0`, { credentials: "same-origin" });
    if (!r.ok) return [];
    const j = await r.json();
    return (j.agents || []).map(a => ({ slug: a.slug || a.id || a.name, name: a.name || a.title || a.slug, description: a.description || "" }));
  } catch (e) { return []; }
}

// So lieu kinh doanh: MinMin da quy uoc file "00 - Dashboard/minmin-dashboard.json" trong brain.
export async function fetchKpi(brain) {
  const paths = [
    `/hud/kpi?brain=${encodeURIComponent(brain)}`,
  ];
  for (const p of paths) {
    try {
      const r = await fetch(p, { credentials: "same-origin" });
      if (r.ok) { const j = await r.json(); if (j && (j.kpis || j.metrics)) return j; }
    } catch (e) {}
  }
  return null;
}
