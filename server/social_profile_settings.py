"""Load stdlib-only profile helpers also shipped in the standalone Worker ZIP."""
from functools import lru_cache
import importlib.util
from pathlib import Path


@lru_cache(maxsize=2)
def module(name):
    p = Path(__file__).resolve().parents[1] / 'apps/doi-social/worker' / (name + '.py')
    spec = importlib.util.spec_from_file_location('_social_' + name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
