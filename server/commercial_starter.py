"""Install the commercial starter into each brain without importing business data.

Called inside system_sync's lock, before its native skill mirror. Own manifest:
modified files stay local, deleted files stay deleted, disabled skills stay disabled.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parent.parent / "system" / "commercial-starter"
MANIFEST = Path(".javis") / "commercial-starter.json"
BUNDLE_ID = "minmin-sales-basic"
BUNDLE_VERSION = 1


def _hash(text):
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _safe(root, path):
    # Do not follow links/junctions outside the selected brain, even for a manifest.
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError("starter destination leaves brain")
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError("starter destination contains a symlink")
    return path


def _write(root, path, text, *, exclusive=False):
    _safe(root, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x", encoding="utf-8", newline="\n") as out:
            out.write(text)
        return
    fd, tmp = tempfile.mkstemp(prefix=".starter-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        _safe(root, path)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def sync_brain(brain_root, bundle_root=None):
    root = Path(brain_root)
    source = Path(bundle_root) if bundle_root is not None else BUNDLE_ROOT
    result = {"ok": True, "installed": [], "updated": [], "kept_user": [], "errors": []}
    if not source.is_dir():
        return result
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = _safe(root, root / MANIFEST)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        records = manifest.setdefault("files", {})
        if not isinstance(records, dict):
            raise ValueError("invalid commercial starter manifest")
    except (ValueError, OSError) as exc:
        result.update(ok=False, errors=[str(exc)])
        return result

    # Match main._brain_sub: prefer flat agents/, otherwise existing Javis/agents/.
    agents = root / "agents"
    if not agents.is_dir() and (root / "Javis" / "agents").is_dir():
        agents = root / "Javis" / "agents"

    changed = False
    for src in sorted(source.rglob("*.md")):
        rel = src.relative_to(source)
        if src.is_symlink() or any(p.startswith(".") for p in rel.parts):
            continue
        key = rel.as_posix()
        if rel.parts[0] not in {"agents", "skills", "commercial"}:
            continue
        try:
            dst = root / rel
            if rel.parts[0] == "agents":
                dst = agents / rel.name
            elif rel.parts[0] == "skills":
                disabled = root / "skills" / ".disabled" / Path(*rel.parts[1:])
                if not dst.exists() and disabled.exists():
                    dst = disabled
            _safe(root, dst)
            text = src.read_text(encoding="utf-8")
            new_hash = _hash(text)
            prior = records.get(key)
            if not dst.exists():
                if prior is not None:
                    # User deletion is intentional. Never resurrect on restart/update.
                    continue
                _write(root, dst, text, exclusive=True)
                records[key] = {"hash": new_hash}
                result["installed"].append(key)
                changed = True
            else:
                current_hash = _hash(dst.read_text(encoding="utf-8"))
                if prior is None:
                    # A customer's file wins even if it happens to match the template.
                    records[key] = {"user_owned": True}
                    result["kept_user"].append(key)
                    changed = True
                elif prior.get("user_owned"):
                    result["kept_user"].append(key)
                elif current_hash != prior.get("hash"):
                    records[key] = {"user_owned": True}
                    result["kept_user"].append(key)
                    changed = True
                elif current_hash != new_hash:
                    _write(root, dst, text)
                    records[key] = {"hash": new_hash}
                    result["updated"].append(key)
                    changed = True
        except (OSError, ValueError) as exc:
            result["ok"] = False
            result["errors"].append(key + ": " + str(exc))
    if changed:
        manifest.update(bundle=BUNDLE_ID, version=BUNDLE_VERSION)
        try:
            _write(root, manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        except (OSError, ValueError) as exc:
            result["ok"] = False
            result["errors"].append(str(exc))
    return result
