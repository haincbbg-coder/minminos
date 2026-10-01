"""Exercise real MinMin auth/CSRF, plugin routing and strict brain selection."""
from _paths import ROOT, SERVER
import os
import tempfile
from pathlib import Path

# The host keeps unrelated SQLite stores open for its process lifetime on Windows.
temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["JAVIS_STATE_DIR"] = str(Path(temp.name) / "state")
os.environ["BRAINS_DIR"] = str(Path(temp.name) / "brains")
os.environ["OBSIDIAN_VAULT_PATH"] = str(Path(temp.name) / "vault")

import config
import main
import plugins_host
from fastapi.testclient import TestClient

settings = config.read_settings()
hashed, salt = config.hash_password("test-password-123")
settings["auth"] = {"username": "admin", "password_hash": hashed, "salt": salt}
config.write_settings(settings)
plugins_host.invalidate()
guest, owner = TestClient(main.app), TestClient(main.app)
base = "/ext/lead-engine/"
assert guest.get(base).status_code == 401
assert guest.get(base + "brains").status_code == 401
assert owner.post("/auth/login", data={"username": "admin", "password": "test-password-123"}).json()["ok"]
assert owner.get(base).status_code == 200
brains = owner.get(base + "brains").json()["brains"]
assert brains
brain = brains[0]["path"]
assert owner.get(base + "api", params={"brain": "missing"}).status_code == 400
assert owner.get(base + "api").status_code == 400
args = dict(business_name="Example", offer="Service", ideal_customer="Businesses", currency="VND")
url = base + "api"
foreign = owner.post(url, params={"brain": brain}, json={"op": "configure", "args": args}, headers={"Origin": "https://foreign.example"})
assert foreign.status_code == 403, foreign.text
headers = {"Origin": "http://testserver"}
r = owner.post(url, params={"brain": brain}, json={"op": "configure", "args": args}, headers=headers)
assert r.status_code == 200, r.text
assert owner.get(url, params={"brain": brain}).json()["profile"]["business_name"] == "Example"
other = Path(os.environ["BRAINS_DIR"]) / "Other"; other.mkdir()
assert owner.get(url, params={"brain": str(other.resolve())}).json()["profile"] is None
r = owner.post(url, params={"brain": brain}, json={"op": "setup_agent"}, headers=headers)
assert r.json()["created"], r.text
assert owner.post(url, params={"brain": brain}, json={"op": "configure", "args": {**args, "tenant_id": "other"}}, headers=headers).status_code == 400
assert owner.post(url, params={"brain": brain}, json=[], headers=headers).status_code == 400
assert owner.post(url, params={"brain": brain}, content=b"x" * 2_000_001, headers=headers).status_code == 413
import sessions
sessions.get_store().close()
temp.cleanup()
print("Lead Engine: authenticated routes, CSRF, brain isolation, schemas and size limit OK")
