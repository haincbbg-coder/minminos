"""share_trang.py - TRANG NHẬN công khai của một link chia sẻ brain (`GET /bs/<token>`, 26.10.92).

Trước bản này, mở link chia sẻ trên điện thoại chỉ ra một khối JSON. Người được chia sẻ thường
nhận link qua Zalo hay quét QR, nên trang đầu tiên họ thấy phải nói được ba điều: cái gì, của ai
(và đã xác minh chưa), và bấm vào đâu để đưa nó về MinMin của mình.

Nút "Nhập vào MinMin của tôi" KHÔNG gửi gì về máy chủ này. Nó chỉ chuyển trình duyệt sang tên
miền MinMin của chính người xem kèm `?nhap=<link này>`; ở đó họ đăng nhập, xem trước và tự bấm
cài. Tên miền của họ được nhớ trong localStorage của trình duyệt họ, không lưu ở đây.

An toàn của trang:
  - mọi chữ lấy từ brain (tên, mô tả, nhãn link) đều escape, không có HTML thô nào lọt qua;
  - CSP chặt: không tải gì từ ngoài, script chỉ chạy khi mang đúng nonce của lượt dựng này;
  - trang có PIN thì không liệt kê nội dung gói (người chưa có PIN chỉ biết "có một gói").
"""
from __future__ import annotations

import html as _html
import json
import secrets
from datetime import datetime

import localefmt

_e = _html.escape


def csp(nonce: str) -> str:
    return ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
            f"script-src 'nonce-{nonce}'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def _ngay(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%d/%m/%Y")
    except Exception:
        return ""


_NHAN_LOAI = {"agent": ("Agent", "Agent"), "skill": ("Skill", "Skill"), "workflow": ("Quy trình", "Workflow")}


def dung_trang(*, tieu_de: str, host: str, ten: str, van_tay: str, items: list, co_pin: bool,
               het_han, con_luot, ma_day_du: str, qr_svg: str, link: str, nonce: str,
               ket_noi: list = None) -> str:
    c = localefmt.chu
    nguoi = _e(ten) if ten else _e(host)
    if items:
        dong = "".join(
            '<li><span class="chip c-{t}">{nl}</span><div><b>{n}</b>{m}</div></li>'.format(
                t=_e(it.get("type", "")), nl=_e(c(*_NHAN_LOAI.get(it.get("type"), ("", "")))),
                n=_e(it.get("name") or it.get("slug") or ""),
                m=(f'<small>{_e(it["mo_ta"])}</small>' if it.get("mo_ta") else ""))
            for it in items[:60])
        them = (f'<li class="mo">{_e(c("và {n} mục nữa", "and {n} more", n=len(items) - 60))}</li>'
                if len(items) > 60 else "")
        danh_sach = f'<ul class="ds">{dong}{them}</ul>'
    elif co_pin:
        danh_sach = f'<p class="mo">{_e(c("Gói này có mã PIN. Nội dung hiện ra trong MinMin của bạn sau khi nhập đúng PIN.", "This package is PIN protected. Its contents appear in your MinMin once the PIN is entered."))}</p>'
    else:
        danh_sach = ""
    can = ""
    if ket_noi:
        can = ('<p class="mo" style="margin:12px 0 0;font-size:13px">'
               + _e(c("Cần kết nối: {ds}", "Needs: {ds}", ds=", ".join(k.get("ten", "") for k in ket_noi[:10])))
               + "</p>")
    luot = ""
    if con_luot is not None:
        luot = " · " + _e(c("còn {n} lượt", "{n} uses left", n=con_luot))
    js = json.dumps({"link": link, "ma": ma_day_du}, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{_e(tieu_de)} · MinMin</title>
<style>
:root{{--bg:#efe8de;--card:#f6f0e7;--fg:#2d2438;--mo:#6f6480;--tim:#6b4fa3;--hl:#fff;--sd:#d5cbbd;--ok:#2f7d4f}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1d1726;--card:#251d31;--fg:#efe7fb;--mo:#a99cbd;--tim:#b99cf2;--hl:#2e2540;--sd:#140f1b;--ok:#6fd39a}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;padding:24px 16px}}
.w{{max-width:560px;margin:0 auto;display:flex;flex-direction:column;gap:18px}}
.the{{background:var(--card);border-radius:22px;padding:20px;box-shadow:8px 8px 18px var(--sd),-8px -8px 18px var(--hl)}}
.nho{{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--mo)}}
h1{{font-size:22px;margin:4px 0 8px;line-height:1.25}}
.tu{{color:var(--mo)}}.tu b{{color:var(--fg)}}
.vt{{display:inline-block;margin-top:8px;font:12px ui-monospace,Menlo,monospace;color:var(--ok);border:1px solid currentColor;border-radius:99px;padding:2px 10px}}
.ds{{list-style:none;margin:14px 0 0;padding:0;display:flex;flex-direction:column;gap:10px}}
.ds li{{display:flex;gap:10px;align-items:flex-start}}.ds small{{display:block;color:var(--mo)}}
.chip{{flex:none;min-width:74px;text-align:center;font-size:11px;font-weight:600;border-radius:8px;padding:2px 8px;background:var(--bg);color:var(--tim);box-shadow:inset 2px 2px 4px var(--sd),inset -2px -2px 4px var(--hl)}}
.mo{{color:var(--mo)}}
.ma{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.ma code{{flex:1;min-width:0;overflow-wrap:anywhere;font:600 16px ui-monospace,Menlo,monospace;background:var(--bg);padding:10px 12px;border-radius:12px;box-shadow:inset 3px 3px 6px var(--sd),inset -3px -3px 6px var(--hl)}}
.qr{{display:flex;justify-content:center;padding:6px}}.qr svg{{width:180px;height:180px;background:#fff;border-radius:12px;padding:8px}}
input{{width:100%;font:inherit;color:var(--fg);background:var(--bg);border:0;border-radius:12px;padding:12px;box-shadow:inset 3px 3px 6px var(--sd),inset -3px -3px 6px var(--hl)}}
button{{font:inherit;font-weight:600;border:0;border-radius:12px;padding:11px 16px;cursor:pointer;color:var(--fg);background:var(--card);box-shadow:4px 4px 10px var(--sd),-4px -4px 10px var(--hl)}}
button.chinh{{background:var(--tim);color:#fff;box-shadow:none;width:100%;margin-top:10px}}
.loi{{color:#c0392b;font-size:13px;min-height:1em;margin-top:6px}}
</style></head><body><div class="w">
<div class="the">
 <div class="nho">MinMin · {_e(c("Gói chia sẻ", "Shared package"))}</div>
 <h1>{_e(tieu_de)}</h1>
 <div class="tu">{_e(c("Từ", "From"))} <b>{nguoi}</b>{(" · " + _e(host)) if ten else ""}</div>
 {f'<span class="vt" title="{_e(c("Vân tay khoá của máy chủ chia sẻ", "Sharing server key fingerprint"))}">&#10003; {_e(van_tay)}</span>' if van_tay else ""}
 {danh_sach}
 {can}
 <p class="mo" style="margin:14px 0 0;font-size:13px">{_e(c("Hạn tới", "Valid until"))} {_e(_ngay(het_han))}{luot}</p>
</div>
<div class="the">
 <div class="nho">{_e(c("Nhập vào MinMin của bạn", "Import into your MinMin"))}</div>
 <p class="mo" style="margin:6px 0 10px">{_e(c("Gõ địa chỉ MinMin của bạn. Bạn sẽ được đưa về đó để xem trước rồi mới cài.", "Type your MinMin address. You will be taken there to preview before anything is installed."))}</p>
 <input id="cuaToi" placeholder="minmin.tenmien-cua-ban.com" autocomplete="url" inputmode="url">
 <button class="chinh" id="nhap">{_e(c("Nhập vào MinMin của tôi", "Import into my MinMin"))}</button>
 <div class="loi" id="loi"></div>
</div>
<div class="the">
 <div class="nho">{_e(c("Hoặc dùng mã", "Or use the code"))}</div>
 <div class="ma" style="margin-top:8px"><code id="ma">{_e(ma_day_du)}</code><button id="chep">{_e(c("Chép", "Copy"))}</button></div>
 <div class="qr">{qr_svg}</div>
 <p class="mo" style="font-size:13px;margin:0">{_e(c("Trong MinMin: Chợ chia sẻ → Nhận về, dán mã hoặc link này.", "In MinMin: Share market → Receive, paste this code or link."))}</p>
</div>
</div>
<script nonce="{nonce}">
(function(){{
 var D={js};
 var o=document.getElementById("cuaToi"),loi=document.getElementById("loi");
 try{{o.value=localStorage.getItem("minmin.cua_toi")||"";}}catch(e){{}}
 function chuan(v){{v=(v||"").trim().replace(/^https?:\\/\\//i,"").replace(/\\/.*$/,"");return /^[a-z0-9.-]+(:\\d+)?$/i.test(v)?v:"";}}
 document.getElementById("nhap").onclick=function(){{
  var h=chuan(o.value);
  if(!h){{loi.textContent={json.dumps(c("Địa chỉ chưa đúng, ví dụ minmin.tenmien.com", "That address does not look right, e.g. minmin.example.com"), ensure_ascii=False)};return;}}
  if(h===location.host){{loi.textContent={json.dumps(c("Đây là máy chủ đang chia sẻ, hãy nhập địa chỉ MinMin của bạn.", "This is the sharing server; enter your own MinMin address."), ensure_ascii=False)};return;}}
  try{{localStorage.setItem("minmin.cua_toi",h);}}catch(e){{}}
  location.href="https://"+h+"/?nhap="+encodeURIComponent(D.link);
 }};
 document.getElementById("chep").onclick=function(){{
  var b=this;function xong(){{b.textContent="\\u2713";}}
  if(navigator.clipboard)navigator.clipboard.writeText(D.ma).then(xong,function(){{}});
 }};
}})();
</script></body></html>"""


def nonce_moi() -> str:
    return secrets.token_urlsafe(16)
