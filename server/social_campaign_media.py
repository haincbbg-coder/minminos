"""Guarded existing MCP image tools and validated image ingestion for campaigns."""
import asyncio
import base64
import io
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit, urljoin

import doi_social_fanpage as fp


async def tools():
    import mcp_hub, mcp_store, mcp_client, mcp_catalog
    conns = await asyncio.to_thread(mcp_store.resolved, enabled_only=True)
    specs, raw = await mcp_client.discover_resolved(conns)
    routes = {}
    for spec in specs:
        entry = raw.get(spec['fn'])
        if not entry:
            continue
        conn = entry['conn']
        allowed, _ = mcp_catalog.allowed(mcp_catalog.get(conn.get('connector_id')), conn.get('perm'), 'full', entry['tool'], {})
        if allowed:
            routes[spec['fn']] = {**entry, 'call': mcp_hub._guard(entry, spec['fn'], 'full')}
    result = []
    for spec in specs:
        entry = routes.get(spec['fn'], {})
        conn = entry.get('conn') or {}
        name = str(entry.get('tool') or spec.get('name') or '')
        if not conn:
            continue
        normalized = re.sub('[^a-z0-9]', '', name.lower())
        generate = any(k in normalized for k in ('generateimage', 'generatetheimage', 'texttoimage'))
        poll = any(k in normalized for k in ('jobstatus', 'generationstatus', 'getstatus', 'getjob'))
        if generate and conn.get('perm') != 'full':
            continue
        if not (generate or poll):
            continue
        result.append({'id': spec['fn'], 'connection': conn['id'], 'label': conn.get('label') or name,
                       'name': name, 'kind': 'generate' if generate else 'poll', 'schema': spec.get('schema') or {}})
    return result, routes


def render(value, values):
    if isinstance(value, str):
        for key, replacement in values.items():
            value = value.replace('{{' + key + '}}', str(replacement))
        return value
    if isinstance(value, list):
        return [render(v, values) for v in value]
    if isinstance(value, dict):
        return {k: render(v, values) for k, v in value.items()}
    return value


async def call(tool_id, arguments):
    catalog, routes = await tools()
    if not any(t['id'] == tool_id for t in catalog) or tool_id not in routes:
        raise ValueError('MCP tạo ảnh chưa kết nối hoặc bị giới hạn quyền. Kiểm tra ở Kết nối trước.')
    spec = next(t for t in catalog if t['id'] == tool_id)
    try:
        import jsonschema
        jsonschema.validate(arguments, spec['schema'])
    except ImportError:
        required = spec['schema'].get('required') or []
        if any(k not in arguments for k in required):
            raise ValueError('Tham số MCP thiếu trường bắt buộc; kiểm tra mẫu JSON')
    except Exception:
        raise ValueError('Tham số MCP chưa đúng schema; kiểm tra model và mẫu JSON') from None
    import mcp_client
    value = await asyncio.wait_for(mcp_client.call_route(routes, tool_id, arguments), 180)
    if isinstance(value, str):
        if value.startswith('ERROR:'):
            raise ValueError('MCP tạo ảnh chưa trả kết quả; kiểm tra kết nối và nhật ký công cụ')
        try:
            value = json.loads(value)
        except ValueError:
            blocks = []
            for line in value.splitlines():
                try:
                    block = json.loads(line)
                    blocks.append(block if isinstance(block, dict) and block.get('type') == 'image' else {'type': 'text', 'text': line})
                except ValueError:
                    continue
            if not blocks:
                raise ValueError('MCP không trả dữ liệu ảnh hợp lệ') from None
            value = {'content': blocks}
    if not isinstance(value, dict) or value.get('isError'):
        raise ValueError('MCP tạo ảnh trả lỗi; chưa có ảnh để đăng')
    return value


def payload(reply):
    values = [reply]
    for item in reply.get('content') or []:
        if isinstance(item, dict) and item.get('type') == 'text':
            try:
                values.append(json.loads(item.get('text') or ''))
            except ValueError:
                pass
    if isinstance(reply.get('structuredContent'), dict):
        values.append(reply['structuredContent'])
    return values


def inspect(reply):
    urls, inline, jobs, statuses = [], [], [], []
    def walk(value, key=''):
        if isinstance(value, dict):
            if value.get('type') == 'image' and value.get('data'):
                inline.append(value['data'])
            for k, v in value.items():
                if k.lower() in ('job_id', 'generation_id', 'request_id') and isinstance(v, (str, int)):
                    jobs.append(str(v))
                if k.lower() in ('status', 'state') and isinstance(v, str):
                    statuses.append(v.lower())
                walk(v, k.lower())
        elif isinstance(value, list):
            for v in value:
                walk(v, key)
        elif isinstance(value, str) and value.startswith('https://') and key in ('image_url', 'image_urls', 'images', 'image', 'output_url', 'url', 'download_url'):
            urls.append(value)
    for p in payload(reply):
        walk(p)
    if any(s in ('failed', 'error', 'cancelled', 'canceled') for s in statuses):
        raise ValueError('Tác vụ tạo ảnh thất bại hoặc đã hủy; chưa đăng bài')
    pending = any(s in ('queued', 'pending', 'running', 'processing', 'in_progress', 'starting') for s in statuses)
    return {'urls': [] if pending else list(dict.fromkeys(urls))[:4], 'inline': [] if pending else inline[:4],
            'job_id': jobs[0] if jobs else '', 'pending': pending}


def save_image(raw):
    if not raw or len(raw) > 15 * 1024 * 1024:
        raise ValueError('Ảnh rỗng hoặc lớn hơn 15MB')
    from PIL import Image
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > 40_000_000 or image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValueError()
            image.verify()
            extension = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}[image.format]
    except Exception:
        raise ValueError('MCP chưa trả tệp ảnh JPEG/PNG/WebP hợp lệ') from None
    with tempfile.NamedTemporaryFile(suffix='.' + extension, delete=False) as f:
        f.write(raw)
        temp = Path(f.name)
    try:
        return fp.luu_media('campaign-image.' + extension, temp)['tep']
    finally:
        temp.unlink(missing_ok=True)


async def download_image(url):
    import httpx
    import packs_fetch
    async with httpx.AsyncClient(follow_redirects=False, timeout=40, trust_env=False) as client:
        for _ in range(4):
            u = urlsplit(url)
            if u.username or u.password:
                raise ValueError('Link ảnh không được chứa mật khẩu')
            await asyncio.to_thread(packs_fetch.kiem_dia_chi, url)
            async with client.stream('GET', url) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers.get('location', ''))
                    continue
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 15 * 1024 * 1024:
                        raise ValueError('Ảnh lớn hơn 15MB')
                return save_image(bytes(data))
    raise ValueError('Link ảnh chuyển hướng quá nhiều')


async def ingest(reply):
    parsed = inspect(reply)
    result = []
    for value in parsed['inline']:
        try:
            raw = base64.b64decode(value, validate=True)
        except Exception:
            raise ValueError('Dữ liệu ảnh MCP không hợp lệ') from None
        result.append(await asyncio.to_thread(save_image, raw))
    if not result:
        for url in parsed['urls']:
            result.append(await download_image(url))
    return result, parsed
