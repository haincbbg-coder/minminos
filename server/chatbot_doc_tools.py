"""Mức quyền "Đọc tài liệu" của bot (26.10.68): ba công cụ ĐỌC, không có gì khác.

Bot ở mức Chỉ đọc chỉ nhận một khối tài liệu tra sẵn nhét vào prompt. Mức này cho nó tự liệt kê,
tìm và mở thêm tài liệu khi khối kia chưa đủ, mà vẫn không ghi được gì, không gọi được nguồn dữ
liệu nào, không thấy brain khác.

Phạm vi đọc là ĐÚNG tập tài liệu mà bộ tra cứu của bot được phép dùng (`chatbot_grounding._duyet`):
cùng danh sách thư mục bị loại (inbox khách gửi lên, memory, skills, ...) và cùng danh sách file
quy ước bị loại (CLAUDE.md, MEMORY.md, ...). Cố ý KHÔNG dùng `javis_read_file` của hub: tool đó
đọc được cả ghi chú riêng của chủ trong cùng brain, mà người ngoài thì không được thấy chúng.
Tool trả đúng định dạng của hub nên mọi engine API chạy được.
"""
from pathlib import Path

import chatbot_grounding

TOI_DA_LIET_KE = 80
TOI_DA_KY_TU = 20_000


def _cho_phep(root: Path) -> dict:
    """{đường dẫn tương đối (posix, chữ thường) -> Path} của các tài liệu được phép đọc."""
    ra = {}
    for p in chatbot_grounding._duyet(root):
        try:
            ra[p.relative_to(root).as_posix().lower()] = p
        except ValueError:
            continue
    return ra


def tao(root):
    """(tools, route) cho một lượt của bot. `root` là brain CỦA CHÍNH BOT."""
    root = Path(root).resolve()
    tools, route = [], {}

    def add(name, mo_ta, props, required, goi):
        tools.append({"fn": name, "server": "javis", "name": name, "description": mo_ta,
                      "schema": {"type": "object", "properties": props, "required": required}})
        route[name] = {"call": goi, "source_type": "builtin", "source_id": "bot-doc-tai-lieu",
                       "effect": "read", "required_mode": "readonly", "health": "healthy"}

    async def _liet_ke(args):
        ds = sorted(_cho_phep(root))
        if not ds:
            return "Chưa có tài liệu nào."
        dong = ds[:TOI_DA_LIET_KE]
        them = f"\n(còn {len(ds) - len(dong)} tài liệu nữa, dùng tai_lieu_tim để tìm)" if len(ds) > len(dong) else ""
        return "\n".join(dong) + them

    async def _tim(args):
        q = str((args or {}).get("query") or "").strip()
        if not q:
            return "ERROR: thiếu query"
        hit = chatbot_grounding.tim(root, q, 5)
        if not hit:
            return "Không thấy tài liệu nào khớp."
        return "\n\n".join(f"[{h['path']}] {h['ten']}\n{h['text'][:chatbot_grounding.CHUNK_MAX]}" for h in hit)

    async def _mo(args):
        pa = str((args or {}).get("path") or "").strip().replace("\\", "/").lstrip("/")
        p = _cho_phep(root).get(pa.lower())
        if p is None:
            return "ERROR: không có tài liệu này trong phạm vi bot được đọc."
        try:
            return p.read_text(encoding="utf-8", errors="replace")[:TOI_DA_KY_TU]
        except OSError as e:
            return f"ERROR: không đọc được: {type(e).__name__}"

    add("tai_lieu_liet_ke", "Liệt kê các tài liệu bạn được phép đọc (đường dẫn tương đối).", {}, [], _liet_ke)
    add("tai_lieu_tim", "Tìm trong tài liệu theo nội dung câu hỏi, trả về các đoạn khớp nhất kèm đường dẫn file.",
        {"query": {"type": "string"}}, ["query"], _tim)
    add("tai_lieu_mo", "Mở đọc một tài liệu theo đường dẫn lấy từ tai_lieu_liet_ke hoặc tai_lieu_tim.",
        {"path": {"type": "string"}}, ["path"], _mo)
    return tools, route
