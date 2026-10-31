"""Read-only, explicitly selected Pancake POS connection. No arbitrary tool dispatch."""
import asyncio
import hashlib
import json
import math
import re
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


def args_for(schema, shop=None, page=1, size=50, action='list'):
    props = schema.get('properties', {})
    if page > 1 and not any(k in props for k in ('page', 'page_number')):
        raise ValueError('Nguồn này chưa công bố phân trang; không đọc lại trang đầu làm trang sau.')
    args = {}
    if 'action' in props:
        choices = props['action'].get('enum', [])
        if choices and action not in choices:
            raise ValueError('Nguồn POS chưa cung cấp thao tác danh sách tương thích.')
        args['action'] = action
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
        # pos_describe returns a Schema JSON block followed by an Example
        # invocation JSON block. Decode one complete root, never concatenate them.
        parsed = False
        decoder = json.JSONDecoder()
        # The guard may prepend its own warning line; it remains in audit logs.
        text = value.split('\n', 1)[-1] if value.startswith('[CẢNH BÁO TIÊM LỆNH') else value
        match = re.search(r'[\[{]', text)
        if match:
            try:
                decoded, _ = decoder.raw_decode(text, match.start())
                if isinstance(decoded, (dict, list)):
                    value, parsed = decoded, True
            except ValueError:
                pass
        if not parsed:
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
        for key in (kind, 'variations', 'products_variations', 'data', 'items', 'results'):
            if key in value and isinstance(value[key], (dict, list)):
                return rows(value[key], kind)
    raise ValueError('Chưa ánh xạ được danh sách POS; giữ nguyên kế hoạch hiện tại.')


async def call_read(specs, routes, name, args):
    import mcp_hub
    import mcp_catalog
    spec = next((s for s in specs if s['name'] == name), None)
    if spec is None:
        raise ValueError('Kết nối này chưa cung cấp danh mục ' + ('cửa hàng.' if name == 'pos_shop' else 'sản phẩm tương thích.'))
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


def action_for(spec, name):
    actions = spec['schema'].get('properties', {}).get('action', {}).get('enum', [])
    if name == 'pos_product' and 'list_products_variations' in actions:
        return 'list_products_variations'
    if 'list' in actions and name == 'pos_product':
        description = spec['schema']['properties']['action'].get('description', '').lower()
        if 'list: product tags' in description:
            raise ValueError('Nguồn đang mô tả nhãn sản phẩm, chưa có danh mục hàng tương thích.')
    return 'list'


def described_schema(value):
    value = unpack(value)
    if isinstance(value, dict):
        if isinstance(value.get('properties'), dict):
            return value
        for key in ('inputSchema', 'input_schema', 'schema', 'parameters', 'data', 'result'):
            if key in value:
                found = described_schema(value[key])
                if found:
                    return found
    return None


async def contract(specs, routes, name):
    spec = next((s for s in specs if s['name'] == name), None)
    if spec is None:
        raise ValueError('Nguồn POS chưa cung cấp danh mục tương thích.')
    action = action_for(spec, name)
    schema = spec['schema']
    if any(s['name'] == 'pos_describe' for s in specs):
        detail = await call_read(specs, routes, 'pos_describe', {'tool': name, 'action': action})
        schema = described_schema(detail)
        if schema is None:
            raise ValueError('Chưa đọc được hợp đồng tham số POS; giữ nguyên kế hoạch.')
    return action, schema


async def read_tool(specs, routes, name, shop=None, page=1):
    action, schema = await contract(specs, routes, name)
    args = args_for(schema, shop, page, action=action)
    # pos_describe may omit the multiplexer's action from its per-action schema.
    args['action'] = action
    return await call_read(specs, routes, name, args)


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
        # Current POS action may return flat variations with the parent product nested.
        if isinstance(product, dict) and (product.get('product_id') is not None or isinstance(product.get('product'), dict)):
            variant = product
            parent = product.get('product') or {}
            parent_id = product.get('product_id') or parent.get('id')
            if parent_id is not None:
                product = dict(parent, id=parent_id, name=parent.get('name') or variant.get('product_name') or variant.get('name'), variations=[variant])
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
