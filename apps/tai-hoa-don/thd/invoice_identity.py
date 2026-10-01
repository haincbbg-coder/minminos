"""Conservative identity checks for original PDFs without an accompanying XML."""
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text) if not unicodedata.combining(c)).lower().replace('đ', 'd')


@lru_cache(maxsize=256)
def _read(path, size, mtime):
    from pypdf import PdfReader
    if size > 25 * 1024 * 1024:
        return ''
    try:
        reader = PdfReader(path)
        # Identity must be on the invoice itself, not a later attached statement.
        return normalized(reader.pages[0].extract_text() or '') if reader.pages else ''
    except Exception:
        return ''


def read_pdf(path):
    p = Path(path)
    s = p.stat()
    return _read(str(p), s.st_size, s.st_mtime_ns)


def serial(inv):
    value = str(inv.get('khhdon') or '').strip().upper()
    model = str(inv.get('khmshdon') or '').strip()
    return value if re.match(r'^\d', value) else model + value


def numbers(text):
    # Some BKAV PDFs serialize their visual header after the footer in the text stream.
    header = text
    found = re.findall(r'\bso\s*(?:\((?:invoice\s*)?no\.?\))?\s*:\s*0*(\d+)\b', header)
    found += re.findall(r'\b\d[ck]\d{2}[a-z]{3}\s+0*(\d+)\s+ky hieu\s*\(serial no\.\)', header)
    return {n.lstrip('0') for n in found}


def matches(text, inv, buyer):
    """Require both tax IDs, full serial and a labelled invoice number, never number alone."""
    seller = str(inv.get('nbmst') or '').strip()
    if not text or not seller or not buyer or seller == buyer:
        return False
    # FAST prints tax IDs with spaces between digits. Exclude the software vendor footer.
    clean = '\n'.join(line for line in text.splitlines() if 'don vi cung cap' not in line and 'giai phap hoa don' not in line)
    for tax_id in (seller, buyer):
        pattern = r'(?<!\d)' + r'\s*'.join(re.escape(c) for c in tax_id) + r'(?!\s*\d)'
        if not re.search(pattern, clean):
            return False
    header = clean
    sn = serial(inv).lower()
    if not sn or not re.search(r'(?<![a-z0-9])' + re.escape(sn) + r'(?![a-z0-9])', header):
        return False
    number = str(inv.get('shdon') or '').strip().lstrip('0')
    if not number or not number.isdigit():
        return False
    labelled = re.findall(r'\bso\s*(?:\((?:invoice\s*)?no\.?\))?\s*:\s*0*(\d+)\b', header)
    # FAST places values before the serial/number labels in PDF text extraction.
    fast = re.search(re.escape(sn) + r'\s+0*(\d+)\s+ky hieu\s*\(serial no\.\)', header)
    numbers = {n.lstrip('0') for n in labelled}
    if fast:
        numbers.add(fast.group(1).lstrip('0'))
    return numbers == {number}
