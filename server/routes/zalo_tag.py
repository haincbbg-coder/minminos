"""Tag Zalo (Gia đình, Khách...) của tài khoản Zalo cá nhân cho form bot (26.10.306).

Form bot có ô "Không trả lời các cuộc chat có tag Zalo"; route này gợi ý các tag đang có trong
Zalo để chủ bấm chọn. Chỉ đọc, xác thực đi qua middleware chung của main.py.
"""
from __future__ import annotations

from fastapi import APIRouter


def register(app):
    r = APIRouter()

    @r.get("/zalo-tag")
    async def zalo_tag(account_ids: str = ""):
        """Tên tag của các tài khoản Zalo cá nhân. Đọc nền: lần hỏi đầu có thể rỗng, `dang_doc`
        báo thử lại sau."""
        import channel_accounts
        import zalo_personal_channel as zc
        ao = {a["id"] for a in channel_accounts.tai_khoan_ao()}
        ten, dang_doc = [], False
        for aid in [x.strip() for x in str(account_ids or "").split(",") if x.strip()][:10]:
            if aid not in ao:
                continue
            ds = zc.ten_nhan(aid)
            dang_doc = dang_doc or (not ds and aid in zc._NHAN_DANG_DOC)
            for t in ds:
                if t not in ten:
                    ten.append(t)
        return {"ok": True, "items": ten, "dang_doc": dang_doc}

    app.include_router(r)
