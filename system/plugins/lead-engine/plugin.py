"""MinMin native tools + authenticated dashboard for the lead ledger."""
import asyncio
import json
from pathlib import Path

from lead_engine import LeadStore


S = {"type": "string"}
SCHEMAS = {
    "report": {},
    "detail": {"lead_id": S},
    "configure": {"business_name": S, "offer": S, "ideal_customer": S, "currency": S},
    "capture": {"source": S, "external_id": S, "name": S, "messages": {
        "type": "array", "maxItems": 500, "items": {"type": "object", "properties": {
            "id": S, "role": {"type": "string", "enum": ["customer", "business"]}, "text": S, "at": S},
            "required": ["id", "role", "text", "at"], "additionalProperties": False}}},
    "analyze": {"lead_id": S, "summary": S, "signals": {"type": "array", "maxItems": 3,
        "items": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["purchase_intent", "product_fit", "timing"]},
                  "message_id": S, "quote": S}, "required": ["kind", "message_id", "quote"], "additionalProperties": False}}},
    "stage": {"lead_id": S, "stage": {"type": "string", "enum": ["new", "qualified", "contacted", "won", "lost", "opted_out"]}},
    "outcome": {"lead_id": S, "source": S, "external_id": S,
        "status": {"type": "string", "enum": ["pending", "delivered", "cancelled", "refunded"]},
        "amount_minor": {"type": "integer", "minimum": 0}, "currency": S, "evidence_ref": S, "observed_at": S},
    "spend": {"source": S, "campaign_id": S, "day": S, "amount_minor": {"type": "integer", "minimum": 0},
              "currency": S, "evidence_ref": S, "observed_at": S},
    "draft": {"idempotency_key": S, "kind": {"type": "string", "enum": ["ad", "follow_up"]}, "body": S, "lead_id": S},
}
DESCRIPTIONS = {
    "report": "Bảng tổng hợp lead, bản nháp, đơn giao thành công và chi phí đã đồng bộ của brain hiện tại. Không phải số liệu toàn nguồn.",
    "detail": "Đọc tối đa 500 tin nhắn mới nhất và phân tích của một lead thuộc brain hiện tại.",
    "configure": "Lưu hồ sơ doanh nghiệp, sản phẩm/dịch vụ, khách mục tiêu và mã tiền tệ. Hỏi người dùng nếu chưa biết; không đoán.",
    "capture": "Nhập lead và hội thoại thật từ connector. source phải gồm nhà cung cấp và mã tài khoản; external_id là mã khách/thread ổn định. Mốc giờ ISO có múi giờ.",
    "analyze": "Lưu phân tích AI với trích dẫn nguyên văn từ tin khách đã nhập. Tính điểm ưu tiên heuristic, KHÔNG phải xác suất mua. Tín hiệu cũ hơn 90 ngày không cộng điểm.",
    "stage": "Cập nhật trạng thái theo hoạt động có thật. opted_out ngăn tạo tin chăm sóc mới. won không tự tạo doanh thu.",
    "outcome": "Đối soát đơn từ POS: snapshot theo mã đơn, không cộng lặp. Chỉ delivered tính doanh thu. Số tiền nguyên theo đơn vị nhỏ nhất; VND=đồng, USD=cent. Cần dẫn nguồn và thời điểm quan sát.",
    "spend": "Lưu tổng chi phí tích lũy của MỘT campaign/MỘT ngày, KHÔNG phải phần tăng thêm. Snapshot mới thay snapshot cũ, không cộng lặp; đơn vị nhỏ nhất của tiền tệ hồ sơ.",
    "draft": "Lưu bản NHÁP quảng cáo hoặc tin chăm sóc. Không gửi, không xuất bản, không tiêu tiền. Dùng idempotency_key ổn định để chống trùng.",
}


def schema(op):
    props = SCHEMAS[op]
    optional = {"capture": {"messages"}, "draft": {"lead_id"}}.get(op, set())
    return {"type": "object", "properties": props,
            "required": [k for k in props if k not in optional], "additionalProperties": False}


def call(op, args, ctx):
    import jsonschema
    jsonschema.validate(args, schema(op))
    return getattr(LeadStore(ctx.data_dir, ctx.vault_root), op)(args)


def _brains():
    # Lazy import avoids the main -> hub -> plugin -> main startup cycle.
    import main
    return main._list_brains_sync()["brains"]


def _http_store(request, ctx):
    requested = request.query_params.get("brain", "")
    roots = {str(Path(b["path"]).resolve()): b["path"] for b in _brains()}
    # Unlike main._brain_root, never silently fall back after an invalid selection.
    if requested not in roots:
        raise ValueError("Chọn một brain có trong danh sách")
    return LeadStore(ctx.data_dir, roots[requested])


def _setup_agent(store):
    folder = store.root / "agents"
    legacy = store.root / "Javis" / "agents"
    if not folder.exists() and legacy.is_dir():
        folder = legacy
    if any(p.is_symlink() for p in (folder, folder.parent)) or not folder.resolve().is_relative_to(store.root):
        raise ValueError("Thư mục agents không hợp lệ")
    folder.mkdir(exist_ok=True)
    path = folder / "lead-engine.md"
    try:
        with path.open("x", encoding="utf-8") as f:
            f.write((Path(__file__).parent / "agent.md").read_text(encoding="utf-8"))
    except FileExistsError:
        return {"created": False, "message": "Agent Lead Engine đã tồn tại; giữ nguyên cấu hình hiện có."}
    return {"created": True, "message": "Đã thêm Lead Engine vào Nhân sự AI của brain này."}


def register(ctx):
    for op in SCHEMAS:
        async def handler(args, context, operation=op):
            return await asyncio.to_thread(call, operation, args, context)
        ctx.register_tool("lead_" + op, DESCRIPTIONS[op], handler,
                          schema=schema(op), min_mode="readonly" if op in ("report", "detail") else "safe")

    def page(request, context):
        from starlette.responses import HTMLResponse
        return HTMLResponse((context.dir / "dashboard.html").read_text(encoding="utf-8"),
                            headers={"Cache-Control": "no-store"})

    def brains(request, context):
        return {"brains": [{"name": b["name"], "path": str(Path(b["path"]).resolve())} for b in _brains()]}

    async def api(request, context):
        from starlette.responses import JSONResponse
        import jsonschema
        try:
            store = await asyncio.to_thread(_http_store, request, context)
            if request.method == "GET":
                result = await asyncio.to_thread(store.report)
            else:
                chunks = bytearray()
                async for chunk in request.stream():
                    chunks.extend(chunk)
                    if len(chunks) > 2_000_000:
                        return JSONResponse({"error": "Dữ liệu tối đa 2 MB mỗi lần"}, status_code=413)
                payload = json.loads(chunks)
                if not isinstance(payload, dict):
                    raise ValueError("Yêu cầu phải là object")
                op, args = payload.get("op"), payload.get("args", {})
                if op == "setup_agent":
                    result = await asyncio.to_thread(_setup_agent, store)
                else:
                    if op not in SCHEMAS:
                        raise ValueError("Thao tác không hợp lệ")
                    jsonschema.validate(args, schema(op))
                    result = await asyncio.to_thread(getattr(store, op), args)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except (ValueError, jsonschema.ValidationError) as exc:
            message = exc.message if isinstance(exc, jsonschema.ValidationError) else str(exc)
            return JSONResponse({"error": message[:500]}, status_code=400, headers={"Cache-Control": "no-store"})

    ctx.register_http("", page)
    ctx.register_http("brains", brains)
    ctx.register_http("api", api, methods=("GET", "POST"))
