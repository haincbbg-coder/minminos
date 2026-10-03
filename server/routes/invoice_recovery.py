"""Evidence-based recovery of originals. Uploaded PDFs are clues, never originals."""
import base64
import copy
import hashlib
import io
import re
import time
import zipfile
from pathlib import Path

MAX_FILE = 20 * 1024 * 1024
MAX_TOTAL = 60 * 1024 * 1024


def unpack(name, data):
    """Bound expanded bytes/count, never extract archive-controlled paths."""
    if len(data) > MAX_FILE:
        raise ValueError("Mỗi file tối đa 20 MB.")
    if name.lower().endswith('.zip'):
        result, total = [], 0
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if len(z.infolist()) > 100:
                raise ValueError("ZIP tối đa 100 mục.")
            for info in z.infolist():
                if info.is_dir():
                    continue
                if info.file_size > MAX_FILE or total + info.file_size > MAX_TOTAL:
                    raise ValueError("ZIP vượt giới hạn giải nén 60 MB.")
                total += info.file_size
                if Path(info.filename).suffix.lower() not in ('.xml', '.pdf'):
                    continue
                with z.open(info) as stream:
                    content = stream.read(MAX_FILE + 1)
                if len(content) > MAX_FILE:
                    raise ValueError("File trong ZIP quá lớn.")
                result.append((Path(info.filename.replace('\\', '/')).name, content))
        if not result:
            raise ValueError("ZIP không có XML/PDF; hãy giải nén ZIP lồng rồi gửi lại.")
        return sorted(result, key=lambda x: not x[0].lower().endswith('.xml'))
    if Path(name).suffix.lower() not in ('.xml', '.pdf'):
        raise ValueError("Chỉ nhận XML, PDF hoặc ZIP.")
    return [(Path(name).name, data)]


def hints(text):
    from urllib.parse import urlsplit, parse_qs
    # Retain the case of secret lookup codes, remove accents only for matching labels.
    from routes import hoa_don as hd
    match = re.search(r'(?:m[ãa]\s*tra\s*c[ứu]u|m[ãa]\s*b[ảa]o\s*m[ậa]t)\s*[:：]\s*([a-z0-9_-]{5,100})', text, re.I)
    code = match.group(1) if match else ''
    urls = re.findall(r'https://[^\s<>"\']+', text)
    urls = [u.rstrip('.,);') for u in urls if not re.search(r'/(?:o|pixel|track|open)/', urlsplit(u).path, re.I)]
    url = next((u for u in urls if any(x in u.lower() for x in ('tracuu', 'invoice', 'hoadon'))), '')
    if not code and url:
        query = {k.lower(): v for k, v in parse_qs(urlsplit(url).query).items()}
        for key in ('mtc', 'code', 'matracuu', 'reservationcode', 'securekey', 'vsecurekey', 'invoicecode'):
            if query.get(key):
                code = query[key][0][:200]
                break
    return code, url


def pdf_qr(page):
    """Read embedded image QR only, bounded to one page and small images."""
    import itertools
    import zxingcpp
    results = []
    for item in itertools.islice(page.images, 16):
        try:
            image = item.image
            if image.width * image.height > 12_000_000:
                continue
            results.extend(b.text[:2000] for b in zxingcpp.read_barcodes(image) if b.valid)
        except Exception:
            continue
    return results


def register(app, hd):
    from fastapi import Request
    A = hd.GOC + '/api/tim-ban-goc'

    def records():
        return hd._doc_json(hd.goc_du_lieu() / 'tim-ban-goc.json', {})

    def save(row):
        row['updated'] = time.time()
        with hd._KHOA_GHI:
            rows = records()
            rows[row['id']] = row
            hd._ghi_json(hd.goc_du_lieu() / 'tim-ban-goc.json', rows)

    def allowed():
        return hd._chan(hd.APP_TAI)

    def public(row):
        return {k: v for k, v in row.items() if not k.startswith('_')}

    def bind(row, path):
        invs = {m: hd.doc_kho(m, 'purchase') for m in hd.doc_cau_hinh()['doanh_nghiep']}
        identity = hd.thd('invoice_identity')
        if path.suffix == '.xml':
            data = path.read_bytes()
            if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
                raise ValueError('XML chứa khai báo ngoài không được hỗ trợ.')
            det = hd.thd('invoice_xml').parse_invoice(data)
            if not all(det.get(k) for k in ('ban_mst', 'mua_mst', 'shdon', 'khhdon')):
                raise ValueError('XML thiếu MST hai bên, số hoặc ký hiệu hóa đơn.')
            ban = {'xml': hd._tuong_doi(str(path))}
            hit = hd.tim_hd_gmail(det, ban, invs)
            if not hit:
                # Reuse the existing conservative XML import, without passing any PDF.
                hd.lien_ket_gmail(ban, det)
                link = ban.get('lien_ket') or {}
                hit = (link.get('mst'), link.get('key')) if link else None
            elif not hd.tuyet_doi(invs[hit[0]][hit[1]].get('_xml_path')):
                with hd._KHOA_GHI:
                    kho = hd.doc_kho(hit[0], 'purchase')
                    kho[hit[1]]['_xml_path'] = hd._chep_vao(kho[hit[1]], hit[0], path, '.xml')
                    kho[hit[1]]['_detail'] = det
                    hd.ghi_kho(hit[0], 'purchase', kho)
            row['label'] = f"{det['ban_ten']} · {det['shdon']} · {identity.serial(det)}"
        else:
            text = identity.read_pdf(path)
            matches = [(m, k) for m, kho in invs.items() for k, inv in kho.items() if identity.matches(text, inv, m)]
            hit = matches[0] if len(matches) == 1 else None
            if not matches:
                # A PDF may arrive before its invoice was queried on the tax portal.
                # Import only a uniquely matching XML from mail, never the input PDF.
                candidates = {}
                for ban in hd._doc_json(hd._gmail_kho_path(), {}).values():
                    xp = hd.tuyet_doi(ban.get('xml'))
                    if not xp:
                        continue
                    try:
                        det = hd.thd('invoice_xml').parse_invoice(xp.read_bytes())
                        inv = {'nbmst': det.get('ban_mst'), 'shdon': det.get('shdon'),
                               'khhdon': det.get('khhdon'), 'khmshdon': det.get('khmshdon')}
                        buyer = det.get('mua_mst')
                        if buyer in invs and identity.matches(text, inv, buyer):
                            candidates[(buyer, hd.khoa_hd(inv))] = (ban, det)
                    except Exception:
                        continue
                if len(candidates) == 1:
                    ban, det = next(iter(candidates.values()))
                    safe_ban = {'xml': ban['xml']}
                    hd.lien_ket_gmail(safe_ban, det)
                    link = safe_ban.get('lien_ket') or {}
                    if link:
                        hit = (link['mst'], link['key'])
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            raw = reader.pages[0].extract_text() if reader.pages else ''
            if reader.pages:
                try:
                    qr = pdf_qr(reader.pages[0])
                    raw = (raw or '') + '\n' + '\n'.join(qr)
                    row['qr_found'] = len(qr)
                except Exception:
                    row['qr_found'] = 0
                for annotation in (reader.pages[0].get('/Annots') or [])[:50]:
                    action = annotation.get_object().get('/A')
                    if action:
                        action = action.get_object()
                        raw = (raw or '') + '\n' + str(action.get('/URI') or '')
            row['code'], row['url'] = hints(raw or '')
            row['label'] = path.name
        if hit:
            row.update(mst=hit[0], key=hit[1], loai='purchase', status='ready', reason='Đã đối chiếu chứng từ; sẵn sàng tìm bản gốc.')
            inv = hd.doc_kho(hit[0], 'purchase')[hit[1]]
            info = hd.ma_tra_cuu_hd(inv)
            row['label'] = f"{inv.get('nbten', '')} · {inv.get('shdon')} · {identity.serial(inv)}"
            row['code'] = row.get('code') or info['code']
            row['url'] = row.get('url') or info['url']
            row['provider'] = hd.thd('providers').issuer_name(inv) or info['provider']
        else:
            row.update(status='need-source', reason='Chưa khớp duy nhất trong kho. Gửi XML có MST người mua thuộc doanh nghiệp đang quản lý, rồi bấm Tìm lại. PDF ảnh cần bổ sung XML hoặc PDF có lớp chữ.')

    def run(v, ids, rescan):
        v.n = len(ids)
        rows = records()
        # One bounded scan per batch, independent of an active tax session.
        if rescan:
            dates = []
            for rid in ids:
                r = rows[rid]
                inv = hd.doc_kho(r['mst'], r.get('loai', 'purchase')).get(r.get('key'), {}) if r.get('mst') else {}
                day = hd.ngay_hd(inv)
                if day:
                    dates.append(hd._ngay(day))
            if dates:
                import datetime as dt
                start, end = min(dates) - dt.timedelta(days=7), max(dates) + dt.timedelta(days=7)
                if (end-start).days > 380:
                    raise ValueError('Quét Gmail bổ sung tối đa 380 ngày mỗi lượt; chia nhỏ các hóa đơn.')
                scan = hd.Viec('recovery-mail', 'Quét Gmail bổ sung')
                scan.log, scan.huy = v.log, v.huy
                try:
                    hd.quet_gmail(scan, start, end, False)
                except Exception as e:
                    v.log('Gmail chưa quét được: ' + str(e)[:250])
        done = 0
        for rid in ids:
            if v.huy.is_set():
                break
            row = records()[rid]
            row['attempts'] = []
            def log(message):
                message = str(message)[:500]
                row['attempts'].append(message)
                row['attempts'] = row['attempts'][-40:]
                v.log(f"{row.get('label', rid)}: {message}")
            try:
                if not row.get('key') and row.get('_evidence'):
                    bind(row, hd.tuyet_doi(row['_evidence']))
                if not row.get('key'):
                    raise ValueError(row['reason'])
                mst, key, loai = row['mst'], row['key'], row.get('loai', 'purchase')
                inv = copy.deepcopy(hd.doc_kho(mst, loai)[key])
                if row.get('code'):
                    inv.update(_ma_tra_cuu=row['code'], _code=row['code'], _bkav_mtc=row['code'])
                identity = hd.thd('invoice_identity')
                def verified(data):
                    from pypdf import PdfReader
                    if not data.lstrip().startswith(b'%PDF-'):
                        return False
                    reader = PdfReader(io.BytesIO(data))
                    text = identity.normalized(reader.pages[0].extract_text() or '') if reader.pages else ''
                    buyer = mst if loai == 'purchase' else inv.get('nmmst')
                    return identity.matches(text, inv, buyer)
                pdf, source = None, ''
                old = hd.tuyet_doi(inv.get('_goc_path'))
                if old and verified(old.read_bytes()):
                    pdf, source = old.read_bytes(), inv.get('_goc_nguon') or 'Kho hiện có'
                    log('Bản gốc trong kho đã khớp thông tin.')
                if not pdf and loai == 'purchase':
                    log('Đối chiếu Gmail đã quét: MST hai bên, ký hiệu và số hóa đơn.')
                    inventories = {m: hd.doc_kho(m, 'purchase') for m in hd.doc_cau_hinh()['doanh_nghiep']}
                    for ban in hd._doc_json(hd._gmail_kho_path(), {}).values():
                        if hd.tim_hd_gmail(None, ban, inventories) != (mst, key):
                            continue
                        fp = hd.tuyet_doi(ban.get('pdf'))
                        if fp and verified(fp.read_bytes()):
                            pdf, source = fp.read_bytes(), 'Gmail'
                            log('Đã tìm thấy PDF đính kèm khớp hóa đơn.')
                            break
                        # Copy only lookup evidence; a PDF is saved below after verification.
                        safe_ban = dict(ban); safe_ban.pop('pdf', None)
                        hd.ghep_chung_tu_gmail(inv, mst, safe_ban)
                xp = hd.tuyet_doi(inv.get('_xml_path'))
                if not pdf and not xp:
                    log('Thử bổ sung XML từ phiên TCT hiện có.')
                    try:
                        hd.tai_mot(hd._can_dang_nhap(mst), mst, inv, ['xml'], log)
                        xp = hd.tuyet_doi(inv.get('_xml_path'))
                    except Exception as e:
                        log('Chưa lấy được XML: ' + str(e)[:200])
                if not pdf and xp:
                    log('Thử hãng phát hành và đường dẫn trong XML; dùng CAPTCHA API đã cấu hình khi hãng hỗ trợ.')
                    try:
                        source, candidate = hd.thd('providers').fetch_original_pdf(xp.read_bytes(), inv, log=log, solver=hd.tao_solver(log))
                        if verified(candidate):
                            pdf = candidate
                        else:
                            log('PDF nhận được chưa đối chiếu đủ danh tính; không ghi nhận là bản gốc.')
                    except Exception as e:
                        log(str(e))
                if not pdf:
                    url = row.get('url') or (inv.get('_gmail_lookup') or {}).get('link') or hd.ma_tra_cuu_hd(inv)['url']
                    if url:
                        log('Thử đường dẫn tra cứu bổ sung.')
                        try:
                            source, candidate = hd.thd('providers').fetch_original_pdf(url.encode(), inv, log=log, solver=hd.tao_solver(log))
                            if verified(candidate):
                                pdf = candidate
                            else:
                                log('File từ link chưa khớp danh tính hóa đơn.')
                        except Exception as e:
                            log(str(e))
                if pdf:
                    folder = hd.goc_du_lieu() / 'tim-ban-goc' / 'verified'
                    folder.mkdir(parents=True, exist_ok=True)
                    dest = folder / (hashlib.sha256(pdf).hexdigest() + '.pdf')
                    dest.write_bytes(pdf)
                    inv.update(_goc_path=hd._tuong_doi(str(dest)), _goc_nguon=source)
                    inv.pop('_goc_loi', None)
                    row.update(status='done', reason='Đã tải và đối chiếu đúng bản gốc.', source=source,
                               download=f"api/tep/{mst}/{loai}/{key}/goc")
                    done += 1
                else:
                    info = hd.ma_tra_cuu_hd(inv)
                    row['code'], row['url'] = row.get('code') or info['code'], row.get('url') or info['url']
                    row.update(status='need-source', reason='Chưa có PDF gốc đã xác minh. ' + (info['note'] or 'Xem các nguồn đã thử; bổ sung mã/link hoặc quét Gmail rồi tìm lại.'))
                    inv['_goc_loi'] = row['reason']
                row['provider'] = hd.thd('providers').issuer_name(inv)
                with hd._KHOA_GHI:
                    kho = hd.doc_kho(mst, loai)
                    # Merge only recovery-owned fields; do not overwrite simultaneous edits.
                    for field in ('_xml_path', '_detail', '_goc_path', '_goc_nguon', '_goc_loi', '_gmail_lookup', '_ma_tra_cuu', '_code', '_bkav_mtc'):
                        if field in inv:
                            kho[key][field] = inv[field]
                    if pdf:
                        kho[key].pop('_goc_loi', None)
                    hd.ghi_kho(mst, loai, kho)
            except Exception as e:
                row.update(status='need-source', reason=str(e)[:500])
                log(row['reason'])
            save(row)
            v.i += 1
        return {'done': done, 'processed': v.i, 'remaining': len(ids)-done}

    @app.get(A)
    def listing():
        if (c := allowed()): return c
        return {'ok': True, 'rows': [public(r) for r in sorted(records().values(), key=lambda r: r.get('updated', 0), reverse=True)]}

    @app.post(A + '/nhap')
    async def intake(request: Request):
        if (c := allowed()): return c
        try:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 29 * 1024 * 1024:
                    raise ValueError('Yêu cầu vượt 29 MB.')
            import json
            d = json.loads(body)
            data = base64.b64decode(d['data'], validate=True)
            result = []
            for name, content in unpack(d['name'], data):
                rid = hashlib.sha256(content).hexdigest()[:24]
                row = records().get(rid) or {'id': rid, 'name': name, 'attempts': []}
                suffix = '.pdf' if content.lstrip().startswith(b'%PDF-') else '.xml'
                folder = hd.goc_du_lieu() / 'tim-ban-goc' / 'evidence'
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / (rid + suffix)
                path.write_bytes(content)
                row['_evidence'] = hd._tuong_doi(str(path))
                try:
                    bind(row, path)
                except Exception as e:
                    row.update(status='need-source', reason=str(e)[:300])
                save(row); result.append(public(row))
            return {'ok': True, 'rows': result}
        except Exception as e:
            return hd._loi(e)

    @app.post(A + '/kho')
    async def from_store(request: Request):
        if (c := allowed()): return c
        try:
            d = await hd._than(request)
            if d.get('gmail_ids') is not None:
                refs = []
                for ban in hd.chon_gmail({'ids': d['gmail_ids']}):
                    hit = hd.tim_hd_gmail(None, ban)
                    if hit:
                        refs.append((hit[0], 'purchase', hit[1]))
                        continue
                    safe_ban = dict(ban)
                    safe_ban.pop('pdf', None)
                    hd.lien_ket_gmail(safe_ban)
                    link = safe_ban.get('lien_ket') or {}
                    if link: refs.append((link['mst'], 'purchase', link['key']))
                if not refs: raise ValueError('Chưa khớp hóa đơn Gmail vào doanh nghiệp. Gửi XML để đối chiếu trước.')
            else:
                mst = hd.chuan_mst(d.get('mst'))
                if mst not in hd.doc_cau_hinh()['doanh_nghiep'] or d.get('loai') not in hd.LOAI:
                    raise ValueError('Doanh nghiệp/loại hóa đơn không hợp lệ.')
                keys = d.get('keys')
                if not isinstance(keys, list) or not keys or len(keys) > 5000:
                    raise ValueError('Chọn từ 1 đến 5000 hóa đơn.')
                kho = hd.doc_kho(mst, d['loai'])
                if any(k not in kho for k in keys): raise ValueError('Có hóa đơn không còn trong kho.')
                refs = [(mst, d['loai'], k) for k in dict.fromkeys(keys)]
            ids = []
            for mst, loai, key in refs:
                inv = hd.doc_kho(mst, loai)[key]
                rid = hashlib.sha256(f'{mst}/{loai}/{key}'.encode()).hexdigest()[:24]
                info = hd.ma_tra_cuu_hd(inv)
                row = records().get(rid) or {'id': rid, 'attempts': []}
                row.update(mst=mst, loai=loai, key=key, label=f"{inv.get('nbten')} · {inv.get('shdon')}",
                           code=info['code'], url=info['url'], provider=info['provider'], status='ready', reason='Sẵn sàng tìm lại.')
                save(row); ids.append(rid)
            return {'ok': True, 'ids': ids}
        except Exception as e: return hd._loi(e)

    @app.post(A + '/chay')
    async def start(request: Request):
        if (c := allowed()): return c
        try:
            d = await hd._than(request)
            ids, rows = d.get('ids'), records()
            if not isinstance(ids, list) or not ids or len(ids) > 5000 or any(not isinstance(i, str) or i not in rows for i in ids):
                raise ValueError('Chọn các chứng từ hợp lệ để tìm bản gốc.')
            ids = list(dict.fromkeys(ids))
            v = hd.chay_viec('tim-ban-goc', f'Tìm bản gốc {len(ids)} hóa đơn', lambda v: run(v, ids, bool(d.get('rescan'))))
            return {'ok': True, 'viec': v.id}
        except Exception as e: return hd._loi(e)

    @app.post(A + '/nguon')
    async def update(request: Request):
        if (c := allowed()): return c
        try:
            d = await hd._than(request)
            row = records()[d['id']]
            code, url = str(d.get('code') or '').strip(), str(d.get('url') or '').strip()
            if len(code) > 200 or len(url) > 2000: raise ValueError('Mã/link quá dài.')
            if url:
                hd.thd('providers.xmllink')._public_url(url)
            row.update(code=code, url=url)
            save(row)
            return {'ok': True}
        except Exception as e: return hd._loi(e)
