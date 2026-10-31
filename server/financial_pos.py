"""Read-only, explicitly selected Pancake POS connection. No arbitrary tool dispatch."""
import asyncio
import hashlib
import json
import math
from datetime import datetime, timezone


def sources():
    import mcp_store
    return [dict(id=c['id'], name=c.get('label') or c.get('name') or 'Pancake POS')
            for c in mcp_store.list_connections() if c.get('enabled') and c.get('connector_id') == 'pancake-pos']


async def selected(connection_id):
    import mcp_store
    import mcp_client
    allowed = {c['id'] for c in sources()}
    if connection_id not in allowed:
        raise ValueError('Chọn kết nối Pancake POS đang bật trong MinMin.')
    conns = [c for c in mcp_store.resolved(enabled_only=True) if c['id'] == connection_id]
    specs, routes = await mcp_client.discover_resolved(conns)
    return specs, routes


def args_for(schema, shop=None, page=1, size=50):
    props = schema.get('properties', {})
    if page > 1 and not any(k in props for k in ('page', 'page_number')):
        raise ValueError('Nguồn này chưa công bố phân trang; không đọc lại trang đầu làm trang sau.')
    args = {}
    if 'action' in props:
        choices = props['action'].get('enum', [])
        if choices and 'list' not in choices:
            raise ValueError('Nguồn POS chưa cung cấp thao tác danh sách tương thích.')
        args['action'] = 'list'
    for key in ('shop_id', 'shopId'):
        if key in props and shop is not None:
            args[key] = int(shop) if props[key].get('type') in ('number', 'integer') else str(shop)
    for key in ('page', 'page_number'):
        if key in props:
            args[key] = page
    for key in ('page_size', 'limit'):
        if key in props:
            args[key] = min(size, props[key].get('maximum', size))
    if any(k not in args and k not in ('action',) for k in schema.get('required', [])):
        raise ValueError('Nguồn POS cần thêm tham số; chưa tự suy đoán dữ liệu.')
    return args


def unpack(value):
    if isinstance(value, str):
        if value.startswith('ERROR:'):
            raise ValueError('POS không trả dữ liệu thành công. Kiểm tra lại kết nối và quyền đọc.')
        try:
            value = json.loads(value)
        except ValueError:
            raise ValueError('POS trả dữ liệu không đúng cấu trúc JSON hỗ trợ.')
    if isinstance(value, dict) and value.get('isError'):
        raise ValueError('POS báo lỗi. Kiểm tra lại kết nối.')
    if isinstance(value, dict) and isinstance(value.get('content'), list):
        texts = [x.get('text', '') for x in value['content'] if x.get('type') == 'text']
        if len(texts) == 1:
            return unpack(texts[0])
    return value


def rows(value, kind):
    value = unpack(value)
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in (kind, 'data', 'items', 'results'):
            if key in value and isinstance(value[key], (dict, list)):
                return rows(value[key], kind)
    raise ValueError('Chưa ánh xạ được danh sách POS; giữ nguyên kế hoạch hiện tại.')


async def read_tool(specs, routes, name, shop=None, page=1):
    import mcp_hub
    import mcp_catalog
    spec = next((s for s in specs if s['name'] == name), None)
    if spec is None:
        raise ValueError('Kết nối này chưa cung cấp danh mục ' + ('cửa hàng.' if name == 'pos_shop' else 'sản phẩm tương thích.'))
    args = args_for(spec['schema'], shop, page)
    raw_entry = routes[spec['fn']]
    entry = dict(raw_entry, conn=dict(raw_entry['conn'], perm='readonly'))
    connector = mcp_catalog.get('pancake-pos')
    if mcp_catalog.classify(connector, name, args) != 'read':
        raise ValueError('Thao tác POS không được xác nhận là chỉ đọc.')
    try:
        result = await asyncio.wait_for(mcp_hub._guard(entry, spec['fn'], 'suggest')(args), timeout=30)
    except Exception:
        raise ValueError('Đọc POS chưa thành công hoặc quá thời gian. Không thay đổi kế hoạch.')
    return unpack(result)


async def shops(connection_id):
    specs, routes = await selected(connection_id)
    items = rows(await read_tool(specs, routes, 'pos_shop'), 'shops')
    return [dict(id=str(s['id']), name=str(s.get('name') or s['id'])[:160]) for s in items if isinstance(s, dict) and s.get('id') is not None]


def numeric(item, keys):
    for key in keys:
        v = item.get(key)
        if v is None or isinstance(v, bool):
            continue
        try:
            v = float(v)
            if math.isfinite(v) and 0 <= v <= 1e15:
                return v
        except (ValueError, TypeError):
            pass
    return None


def normalize_products(items, connection_id, shop_id):
    result, seen, skipped = [], set(), 0
    for product in items:
        if not isinstance(product, dict) or product.get('id') is None:
            skipped += 1
            continue
        variants = product.get('variations') or product.get('variants') or [product]
        if not isinstance(variants, list):
            skipped += 1
            continue
        for variant in variants:
            if not isinstance(variant, dict) or variant.get('id') is None:
                skipped += 1
                continue
            ref = dict(connectionId=connection_id, shopId=str(shop_id), productId=str(product['id']), variationId=str(variant['id']))
            identity = json.dumps(ref, sort_keys=True)
            if identity in seen:
                continue
            seen.add(identity)
            sku = str(variant.get('custom_id') or variant.get('sku') or variant.get('display_id') or product.get('custom_id') or variant['id'])[:160]
            result.append(dict(id='POS-' + hashlib.sha256(identity.encode()).hexdigest()[:24], sku=sku,
                               name=(str(product.get('name') or sku) + (' · ' + str(variant.get('name')) if variant.get('name') and variant is not product else ''))[:160],
                               price=numeric(variant, ('retail_price', 'price')), cost=numeric(variant, ('cost_price', 'purchase_price')),
                               stock=numeric(variant, ('remain_quantity', 'available_quantity', 'quantity')), posRef=ref))
    return result, skipped


async def preview(connection_id, shop_id, page=1):
    if type(page) is not int or not 1 <= page <= 1000:
        raise ValueError('Trang không hợp lệ.')
    available = await shops(connection_id)
    shop = next((s for s in available if s['id'] == str(shop_id)), None)
    if shop is None:
        raise ValueError('Cửa hàng không thuộc kết nối POS đã chọn.')
    specs, routes = await selected(connection_id)
    items = rows(await read_tool(specs, routes, 'pos_product', shop_id, page), 'products')
    products, skipped = normalize_products(items, connection_id, shop_id)
    return dict(products=products, shop=shop, page=page, mayHaveMore=len(items) >= 50, skipped=skipped,
                observedAt=datetime.now(timezone.utc).isoformat(), fields=['sku', 'name', 'price', 'cost', 'stock'],
                note='Giá và tồn là ảnh chụp tại thời điểm đọc. Chưa suy ra doanh thu thuần, lợi nhuận hoặc tồn đầu năm.')
