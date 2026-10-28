"""Pancake Page API, using the existing multi-page connection.

API contract adapted from blogminhquy/javis-store pancake-chat-mcp 1.1.0 (MIT).
All mutations are gated by mcp_hub before this module runs. No automatic retry.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

import httpx
import ket_noi_api as k

HOST = 'https://pages.fm/api/public_api'
READ = ('pancake_conversations_list', 'pancake_messages_get', 'pancake_tags_list',
        'pancake_staff_list', 'pancake_posts_list')
WRITE = ('pancake_conversation_tag', 'pancake_conversation_mark_read',
         'pancake_conversation_assign', 'pancake_customer_add_note',
         'pancake_send_message', 'pancake_send_image')
PAGE = {'page': {'type': 'string', 'description': 'Page ID chính xác; bắt buộc khi kết nối có nhiều page.'}}
CID = {'conversation_id': {'type': 'string'}}
TXT = {'message': {'type': 'string', 'minLength': 1, 'maxLength': 4000}}
TOOLS = [
    k.tool(READ[0], 'Đọc hội thoại inbox/bình luận. Phân trang bằng last_conversation_id; unread_first chỉ ưu tiên chưa đọc, không có nghĩa chưa trả lời.',
           {**PAGE, 'type': {'type': 'string', 'enum': ['INBOX','COMMENT']},
            'tags': {'type':'string'}, 'unread_first': {'type':'boolean'},
            'last_conversation_id': {'type':'string'}, **k.NGAY_PROPS}),
    k.tool(READ[1], 'Đọc 30 tin nhắn của hội thoại; current_count để lấy tiếp tin cũ.',
           {**PAGE, **CID, 'current_count': {'type':'integer','minimum':0}}, ['conversation_id']),
    k.tool(READ[2], 'Thẻ của page, kèm ID dùng gắn thẻ.', PAGE),
    k.tool(READ[3], 'Nhân viên của page, kèm ID dùng phân công.', PAGE),
    k.tool(READ[4], 'Bài đăng của page trong kỳ, có phân trang.',
           {**PAGE, **k.NGAY_PROPS, 'page_number': {'type':'integer','minimum':1}}),
    k.tool(WRITE[0], 'Đề nghị gắn/gỡ thẻ hội thoại. Chỉ làm sau khi chủ bấm duyệt.',
           {**PAGE, **CID, 'tag_id': {'type':'string'}, 'action': {'type':'string','enum':['add','remove']}},
           ['conversation_id','tag_id','action']),
    k.tool(WRITE[1], 'Đề nghị đánh dấu đã đọc/chưa đọc; chờ duyệt.',
           {**PAGE, **CID, 'read': {'type':'boolean'}}, ['conversation_id','read']),
    k.tool(WRITE[2], 'Đề nghị phân công cho nhân viên; assignee_ids rỗng là bỏ phân công. Chờ duyệt.',
           {**PAGE, **CID, 'assignee_ids': {'type':'array','items':{'type':'string'},'maxItems':20}},
           ['conversation_id','assignee_ids']),
    k.tool(WRITE[3], 'Đề nghị thêm ghi chú hồ sơ khách, chờ duyệt.',
           {**PAGE, **TXT, 'page_customer_id': {'type':'string'}}, ['page_customer_id','message']),
    k.tool(WRITE[4], 'Soạn câu trả lời cho khách; gửi thật CHỈ SAU nút duyệt, không tự thử lại nếu lỗi.',
           {**PAGE, **CID, **TXT, 'reply_to_comment_id': {'type':'string'}}, ['conversation_id','message']),
    k.tool(WRITE[5], 'Gửi ảnh local jpg/png/gif/webp sau duyệt. Một lần 1-10 ảnh, tối đa 10MB mỗi ảnh. Không tự thử lại.',
           {**PAGE, **CID, 'paths': {'type':'array','items':{'type':'string'},'minItems':1,'maxItems':10}},
           ['conversation_id','paths']),
]


def ident(v):
    s = str(v or '').strip()
    if not s or len(s) > 200 or not re.fullmatch(r'[A-Za-z0-9_.:-]+', s):
        raise ValueError('Mã hội thoại/khách/thẻ không hợp lệ.')
    return quote(s, safe='')


def plan(tool, a):
    """Allowlisted paths and bodies only. Never accept an arbitrary endpoint from the model."""
    if tool == READ[0]:
        q = {kk:a[kk] for kk in ('type','tags','unread_first','last_conversation_id') if kk in a}
        q['order_by'] = 'updated_at'
        if a.get('type') not in (None,'INBOX','COMMENT'): raise ValueError('type phải là INBOX hoặc COMMENT.')
        for key, source in [('since','tu_ngay'),('until','den_ngay')]:
            if a.get(source):
                q[key] = k.ngay_sang_ts(a[source], cuoi_ngay=key=='until')
                if q[key] is None: raise ValueError('Ngày phải theo YYYY-MM-DD.')
        return 'GET','v2','/conversations',q,None
    if tool == READ[1]:
        return 'GET','v1',f'/conversations/{ident(a.get("conversation_id"))}/messages',{'current_count':k.so(a.get('current_count'),0,0,100000)},None
    if tool in READ[2:4]: return 'GET','v1',('/tags' if tool==READ[2] else '/users'),{},None
    if tool == READ[4]:
        since,until=k.khoang(a,30)
        return 'GET','v1','/posts',{'since':since,'until':until,'page_number':k.so(a.get('page_number'),1,1,100000),'page_size':30},None
    if tool == WRITE[3]:
        return 'POST','v1',f'/page_customers/{ident(a.get("page_customer_id"))}/notes',{}, {'message':text(a)}
    cid=ident(a.get('conversation_id'))
    p=f'/conversations/{cid}'
    if tool == WRITE[0]:
        if a.get('action') not in ('add','remove'): raise ValueError('action phải là add hoặc remove.')
        return 'POST','v1',p+'/tags',{}, {'action':a['action'],'tag_id':ident(a.get('tag_id'))}
    if tool == WRITE[1]:
        if not isinstance(a.get('read'),bool): raise ValueError('Thiếu read true/false.')
        return 'POST','v1',p+('/read' if a['read'] else '/unread'),{},{}
    if tool == WRITE[2]:
        ids=a.get('assignee_ids')
        if not isinstance(ids,list) or len(ids)>20: raise ValueError('assignee_ids phải là danh sách tối đa 20 ID.')
        return 'POST','v1',p+'/assign',{}, {'assignee_ids':[ident(x) for x in ids]}
    if tool == WRITE[4]:
        body={'action':'reply_inbox','message':text(a)}
        if a.get('reply_to_comment_id'): body.update(action='reply_comment',message_id=ident(a['reply_to_comment_id']))
        return 'POST','v1',p+'/messages',{},body
    raise ValueError('Công cụ không được hỗ trợ.')


def text(a):
    v=a.get('message')
    if not isinstance(v,str) or not v.strip() or len(v)>4000: raise ValueError('Nội dung phải có 1-4000 ký tự.')
    return v


def image(path):
    f=Path(str(path))
    if not f.is_absolute() or not f.is_file() or f.stat().st_size>10*1024*1024:
        raise ValueError('Ảnh cần đường dẫn tuyệt đối, là file thật và không quá 10MB.')
    with f.open('rb') as h: b=h.read(10*1024*1024+1)
    if len(b)>10*1024*1024: raise ValueError('Ảnh quá 10MB.')
    mime=('image/png' if b.startswith(b'\x89PNG\r\n\x1a\n') else
          'image/jpeg' if b.startswith(b'\xff\xd8\xff') else
          'image/gif' if b[:6] in (b'GIF87a',b'GIF89a') else
          'image/webp' if b[:4]==b'RIFF' and b[8:12]==b'WEBP' else '')
    if not mime: raise ValueError('File không có định dạng ảnh jpg/png/gif/webp.')
    return f.name,b,mime


async def request(page, method, version, path, params=None, body=None, file=None):
    # httpx does not follow redirects: the page token must only reach pages.fm.
    url=f'{HOST}/{version}/pages/{ident(page["id"])}{path}'
    q={**(params or {}),'page_access_token':page['token']}
    async with httpx.AsyncClient(timeout=30,follow_redirects=False) as c:
        r=await c.request(method,url,params=q,json=body,files={'file':file} if file else None)
    if r.status_code>=300: raise RuntimeError(f'Pancake HTTP {r.status_code}; chưa tự gửi lại.')
    try: data=r.json()
    except ValueError: raise RuntimeError('Pancake không trả JSON hợp lệ.')
    if isinstance(data,dict) and data.get('success') is False:
        raise RuntimeError(str(data.get('message') or data.get('error') or 'Pancake từ chối yêu cầu.')[:400])
    return data


async def call(tool, args, spec):
    import pancake_chat_mcp as stats
    pages=stats.doc_pages(k.bi_mat(spec).get('pages'))
    secrets={str(i):p['token'] for i,p in enumerate(pages)}
    sent=0
    try:
        a=dict(args or {})
        chosen=[p for p in pages if p['id']==str(a.get('page') or '')] if a.get('page') else pages
        if len(chosen)!=1: raise ValueError('Chọn đúng một Page ID từ pancake_tk_ds_page trước khi đọc hoặc thao tác hội thoại.')
        p=chosen[0]
        if tool==WRITE[5]:
            paths=a.get('paths')
            if not isinstance(paths,list) or not 1<=len(paths)<=10: raise ValueError('Cần 1-10 ảnh.')
            cid=ident(a.get('conversation_id'))
            images=[image(x) for x in paths]  # validate every file before the first upload
            for img in images:
                d=await request(p,'POST','v1','/upload_contents',file=img)
                content_id=(d.get('id') if isinstance(d,dict) else None)
                if not content_id: raise RuntimeError('Pancake không trả mã ảnh đã tải; chưa gửi ảnh này.')
                await request(p,'POST','v1',f'/conversations/{cid}/messages',body={'action':'reply_inbox','content_ids':[content_id]})
                sent+=1
            result={'sent_images':sent,'page_id':p['id']}
        else:
            method,ver,path,q,body=plan(tool,a)
            result=await request(p,method,ver,path,q,body)
        return k.giau(k.json_ra(result,24000),secrets)
    except Exception as e:
        suffix=f' Đã gửi {sent} ảnh trước lỗi.' if sent else ''
        return k.giau(f'ERROR: {type(e).__name__}: {e}.{suffix} Nếu đây là lệnh ghi, kiểm tra Pancake trước khi thử lại.',secrets)
