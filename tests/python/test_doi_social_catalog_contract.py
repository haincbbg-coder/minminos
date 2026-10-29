"""Every advertised Social template must have an executable Worker handler."""
from _paths import ROOT, SERVER
import sys
sys.path.insert(0, str(ROOT / 'apps' / 'doi-social' / 'worker'))
import doi_social_kich_ban as catalog
import minmin_worker as worker
handlers, errors = worker.nap_ky_nang()
assert not errors, errors
missing = [item['id'] for item in catalog.MAU if not callable(handlers.get(item['id']))]
assert not missing, missing
print(f'PASS {len(catalog.MAU)} advertised Social templates have Worker handlers')
