"""Financial planning storage: SQLite transactions, revision leases, bounded history.

Shared installation scope like the external-app license; no claim of brain isolation.
"""
from __future__ import annotations
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import giay_phep
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse


def validate(p):
    def num(v, lo=0, hi=1e15, integer=False):
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi or (integer and int(v) != v):
            raise ValueError("Số liệu ngoài phạm vi hợp lệ.")
    if not isinstance(p, dict) or p.get("schema") != 1 or not isinstance(p.get("name"), str) or len(p["name"]) > 160:
        raise ValueError("Hồ sơ kế hoạch không hợp lệ.")
    num(p.get("year"), 2000, 2200, True)
    for k in ("openingCash", "openingAR", "openingAP"):
        num(p.get(k))
    for k in ("collectionLag", "paymentLag"):
        num(p.get(k), 0, 12, True)
    num(p.get("taxRate"), 0, 100)
    products, months = p.get("products"), p.get("months")
    if not isinstance(products, list) or len(products) > 200 or not isinstance(months, list) or len(months) != 12:
        raise ValueError("Cần 12 tháng, tối đa 200 sản phẩm.")
    ids = set()
    for s in products:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not 1 <= len(s["id"]) <= 80 or s["id"] in ids or not isinstance(s.get("name"), str) or len(s["name"]) > 160:
            raise ValueError("Mã sản phẩm trống hoặc trùng.")
        ids.add(s["id"])
        for k in ("price", "cost", "opening", "safety"):
            num(s.get(k))
        for k in ("lot", "moq"):
            num(s.get(k), 1, 1e9, True)
        num(s.get("lead"), 0, 12, True)
        if not isinstance(s.get("units"), list) or len(s["units"]) != 12:
            raise ValueError("Sản lượng phải đủ 12 tháng.")
        for v in s["units"]:
            num(v, 0, 1e9)
    for m in months:
        if not isinstance(m, dict):
            raise ValueError("Dữ liệu tháng không hợp lệ.")
        for k in ("fixed", "depreciation", "interest", "capex", "principal"):
            num(m.get(k))
        num(m.get("financing"), -1e15)
        num(m.get("variableRate"), 0, 100)
        for k in ("actualRevenue", "actualProfit"):
            if k not in m:
                raise ValueError("Thiếu dữ liệu thực tế.")
            if m[k] is not None:
                num(m[k], -1e15 if k == "actualProfit" else 0)
        if not isinstance(m.get("locked"), bool):
            raise ValueError("Trạng thái khóa không hợp lệ.")
    if p.get("status") not in ("draft", "submitted", "approved"):
        raise ValueError("Trạng thái kế hoạch không hợp lệ.")


def protect_locked(old, new):
    """Explicit unlock-only save must precede changing any affected inputs."""
    locked = [i for i, m in enumerate(old["months"]) if m["locked"]]
    if not locked:
        return
    # An unlock transaction may only change lock flags, name, status.
    unlocked = any(not new["months"][i]["locked"] for i in locked)
    a, b = json.loads(json.dumps(old)), json.loads(json.dumps(new))
    for p in (a, b):
        p.pop("name", None)
        p.pop("status", None)
        for m in p["months"]:
            m.pop("locked", None)
    if unlocked:
        if a != b:
            raise ValueError("Lưu mở khóa riêng trước khi sửa số liệu.")
        return
    for k in ("year", "openingCash", "openingAR", "openingAP", "collectionLag", "paymentLag", "taxRate"):
        if old[k] != new[k]:
            raise ValueError("Giả định dùng chung ảnh hưởng kỳ đã khóa.")
    if len(old["products"]) != len(new["products"]):
        raise ValueError("Không đổi danh sách sản phẩm khi có kỳ khóa.")
    last = max(locked)
    for a, b in zip(old["products"], new["products"]):
        if {k: v for k, v in a.items() if k != "units"} != {k: v for k, v in b.items() if k != "units"} or a["units"][:last+1] != b["units"][:last+1]:
            raise ValueError("Sản lượng hoặc sản phẩm ảnh hưởng kỳ khóa.")
    for i in range(last+1):
        a, b = dict(old["months"][i]), dict(new["months"][i])
        for m in (a, b):
            m.pop("locked", None)
            if i not in locked:
                m.pop("actualRevenue", None)
                m.pop("actualProfit", None)
        if a != b:
            raise ValueError("Chi phí hoặc thực tế ảnh hưởng kỳ đã khóa.")


def register(app, dashboard_dir, terms_check):
    directory = Path(dashboard_dir).parent / "apps" / "financial-planning" / "web"
    def guard():
        if not giay_phep.da_mo("financial_planning"):
            return JSONResponse({"error": "Kế Hoạch tài chính chưa được mở khóa tại Kết Nối Ngoài."}, status_code=403)
        if not terms_check("chung"):
            return JSONResponse({"error": "Cần đồng ý điều khoản MinMin."}, status_code=403)
    import financial_workspaces as store
    def db():
        return store.connect()
    def missing(conn, key):
        return conn.execute('SELECT 1 FROM workspaces WHERE id=?', (key,)).fetchone() is None
    def snapshot(row):
        return {"revision": row[0], "savedAt": row[1], "plan": json.loads(row[2])} if row else {"revision": 0, "plan": None}

    async def read_json(request):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 2_000_000:
                raise ValueError('Hồ sơ tối đa 2 MB.')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError('Dữ liệu không hợp lệ.')
        return data

    @app.get('/api/financial-planning/workspaces')
    def financial_workspaces_list():
        denied = guard()
        if denied is not None:
            return denied
        conn = db()
        try:
            return {'workspaces': [store.workspace(conn, row[0]) for row in conn.execute('SELECT id FROM workspaces ORDER BY rowid')]}
        finally:
            conn.close()

    @app.post('/api/financial-planning/workspaces')
    async def financial_workspace_create(request: Request):
        denied = guard()
        if denied is not None:
            return denied
        conn = db()
        try:
            data = await read_json(request)
            plan = data.get('plan')
            if data.get('copyFrom'):
                plan = store.latest(conn, data['copyFrom'])['plan']
            if plan is not None:
                plan = json.loads(json.dumps(plan))
                plan['name'] = data.get('name', plan.get('name', ''))
                plan['status'] = 'draft'
                for m in plan.get('months', []):
                    m['locked'] = False
                validate(plan)
            return {'workspace': store.create(conn, data, plan)}
        except (ValueError, TypeError, KeyError):
            return JSONResponse({'error': 'Tên, nguồn hoặc nội dung phương án không hợp lệ.'}, status_code=400)
        finally:
            conn.close()

    @app.put('/api/financial-planning/workspaces/{key}')
    async def financial_workspace_settings(key: str, request: Request):
        denied = guard()
        if denied is not None:
            return denied
        conn = db()
        try:
            data = await read_json(request)
            s = store.settings(data)
            conn.execute('BEGIN IMMEDIATE')
            old = store.workspace(conn, key)
            if data.get('configRevision') != old['configRevision']:
                return JSONResponse({'error': 'Cấu hình đã đổi ở cửa sổ khác. Hãy tải lại.'}, status_code=409)
            conn.execute('UPDATE workspaces SET settings=?, config_revision=config_revision+1 WHERE id=?', (json.dumps(s, ensure_ascii=False), key))
            conn.commit()
            return {'workspace': store.workspace(conn, key)}
        except (ValueError, TypeError, KeyError):
            return JSONResponse({'error': 'Phương án hoặc cấu hình không hợp lệ.'}, status_code=400)
        finally:
            conn.close()

    @app.get('/api/financial-planning/pos/sources')
    def financial_pos_sources():
        denied = guard()
        if denied is not None:
            return denied
        import financial_pos
        return {'sources': financial_pos.sources()}

    @app.get('/api/financial-planning/pos/capabilities')
    async def financial_pos_capabilities(connection: str):
        denied = guard()
        if denied is not None:
            return denied
        import financial_pos
        try:
            specs, _ = await financial_pos.selected(connection)
            return {'tools': [{'name': s['name'], 'schema': s['schema']} for s in specs if s['name'].startswith('pos_')]}
        except ValueError as e:
            return JSONResponse({'error': str(e)}, status_code=400)

    @app.get('/api/financial-planning/pos/shops')
    async def financial_pos_shops(connection: str):
        denied = guard()
        if denied is not None:
            return denied
        import financial_pos
        try:
            return {'shops': await financial_pos.shops(connection)}
        except ValueError as e:
            return JSONResponse({'error': str(e)}, status_code=400)

    @app.post('/api/financial-planning/pos/preview')
    async def financial_pos_preview(request: Request, workspace: str = 'default'):
        denied = guard()
        if denied is not None:
            return denied
        import financial_pos
        conn = db()
        try:
            data = await read_json(request)
            w = store.workspace(conn, workspace)
            if w['mode'] != 'pos' or not w['connectionId'] or not w['shopId']:
                raise ValueError('Lưu cấu hình phương án POS với đúng kết nối và cửa hàng trước.')
            result = await financial_pos.preview(w['connectionId'], w['shopId'], data.get('page', 1))
            return dict(result, workspace=workspace, configRevision=w['configRevision'])
        except (ValueError, KeyError) as e:
            return JSONResponse({'error': str(e)}, status_code=400)
        finally:
            conn.close()

    @app.get("/apps/financial-planning")
    def financial_planning_redirect():
        return RedirectResponse("/apps/financial-planning/", status_code=307)

    @app.get("/apps/financial-planning/")
    def financial_planning_index():
        return serve_asset("index.html")

    @app.get("/apps/financial-planning/{name}")
    def financial_planning_asset(name: str):
        return serve_asset(name)

    def serve_asset(name: str):
        denied = guard()
        if denied is not None:
            return denied
        if name not in {"index.html", "style.css", "engine.js", "app.js", "simulator.js", "workspaces.js", "planning-extra.css"} or not (directory / name).is_file():
            return JSONResponse({"error": "Không có tệp này."}, status_code=404)
        return FileResponse(directory / name, headers={"Cache-Control": "no-cache"})

    @app.get("/api/financial-planning")
    def financial_planning_get(workspace: str = "default"):
        denied = guard()
        if denied is not None:
            return denied
        conn = db()
        try:
            if missing(conn, workspace):
                return JSONResponse({"error": "Không có phương án này."}, status_code=404)
            return store.latest(conn, workspace)
        finally:
            conn.close()

    @app.put("/api/financial-planning")
    async def financial_planning_put(request: Request, workspace: str = "default"):
        denied = guard()
        if denied is not None:
            return denied
        raw = bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw) > 2_000_000:
                return JSONResponse({"error": "Hồ sơ tối đa 2 MB."}, status_code=413)
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or type(data.get("revision")) is not int:
                raise ValueError("Thiếu phiên bản dữ liệu.")
            plan = data.get("plan")
            validate(plan)
        except (ValueError, TypeError, KeyError) as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        conn = db()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if missing(conn, workspace):
                return JSONResponse({"error": "Không có phương án này."}, status_code=404)
            old = store.latest(conn, workspace)
            if 'workspaceRevision' in data and data['workspaceRevision'] != store.workspace(conn, workspace)['configRevision']:
                return JSONResponse({'error': 'Cấu hình nguồn đã đổi. Tải lại phương án trước khi lưu.'}, status_code=409)
            if old["revision"] != data["revision"]:
                return JSONResponse({"error": "Có phiên bản mới trên máy chủ. Xuất bản sao thay đổi trước khi tải lại trang."}, status_code=409)
            if old["plan"]:
                protect_locked(old["plan"], plan)
            if plan["status"] == "approved" and (not old["plan"] or old["plan"]["status"] not in ("submitted", "approved")):
                raise ValueError("Cần trình duyệt trước khi duyệt.")
            revision = old["revision"] + 1
            saved = datetime.now(timezone.utc).isoformat()
            conn.execute("INSERT INTO workspace_versions VALUES (?,?,?,?)", (workspace, revision, saved, json.dumps(plan, ensure_ascii=False, allow_nan=False)))
            conn.execute("DELETE FROM workspace_versions WHERE workspace=? AND revision <= ?", (workspace, revision - 30))
            conn.commit()
            return {"revision": revision, "savedAt": saved}
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        finally:
            conn.close()

    @app.get("/api/financial-planning/history")
    def financial_planning_history(workspace: str = "default"):
        denied = guard()
        if denied is not None:
            return denied
        conn = db()
        try:
            if missing(conn, workspace):
                return JSONResponse({"error": "Không có phương án này."}, status_code=404)
            return {"versions": [{"revision": r[0], "savedAt": r[1]} for r in conn.execute("SELECT revision,saved_at FROM workspace_versions WHERE workspace=? ORDER BY revision DESC", (workspace,))]}
        finally:
            conn.close()

    @app.get("/api/financial-planning/history/{revision}")
    def financial_planning_version(revision: int, workspace: str = "default"):
        denied = guard()
        if denied is not None:
            return denied
        conn = db()
        try:
            row = conn.execute("SELECT revision,saved_at,plan FROM workspace_versions WHERE workspace=? AND revision=?", (workspace,revision)).fetchone()
            return snapshot(row) if row else JSONResponse({"error": "Không còn phiên bản này."}, status_code=404)
        finally:
            conn.close()
