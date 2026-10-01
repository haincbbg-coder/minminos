"""Download the PDF link explicitly provided in a FAST invoice email."""
from urllib.parse import urlsplit, urljoin
import requests
from . import ProviderError
from . import xmllink


def fetch_pdf(url, log):
    # FAST/J&T email links can be wrapped by the sender's HTTP tracking host.
    # Limit that exception to its click endpoint; all invoice requests use HTTPS.
    with requests.Session() as session:
        session.trust_env = False
        for _ in range(5):
            p = urlsplit(url)
            host = (p.hostname or "").lower()
            tracker = host == "url3815.hq.jtexpress.vn" and p.path == "/ls/click"
            invoice = host == "einvoice.fast.com.vn"
            if not (tracker or invoice) or p.username or p.password or p.port not in (None,80,443) or p.scheme not in ("http","https"):
                raise ProviderError("Link FAST không thuộc cổng hoá đơn hoặc link gửi thư đã hỗ trợ.")
            if invoice and p.scheme == "http":
                url = "https://" + p.netloc + p.path + ("?"+p.query if p.query else "")
            xmllink._public_url("https://" + host + "/")
            with session.get(url, timeout=(10,40), allow_redirects=False, stream=True) as r:
                if r.status_code in (301,302,303,307,308):
                    url = urljoin(url,r.headers.get("Location", ""))
                    continue
                if r.status_code != 200:
                    raise ProviderError("Link FAST trả HTTP " + str(r.status_code))
                chunks=[]; size=0
                for chunk in r.iter_content(65536):
                    size += len(chunk)
                    if size > xmllink.MAX_BYTES:
                        raise ProviderError("PDF FAST vượt giới hạn 25 MB")
                    chunks.append(chunk)
                data=b"".join(chunks)
                if not data.lstrip().startswith(b"%PDF-"):
                    raise ProviderError("Link FAST chưa trả PDF; cần link tải PDF trong email gốc.")
                log("FAST: đã tải PDF gốc từ link gửi trong email.")
                return data
    raise ProviderError("Link FAST chuyển hướng quá nhiều lần.")
