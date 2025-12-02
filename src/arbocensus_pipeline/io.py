"""I/O helpers for arbocensus pipeline.

Provides read/write helpers for JSON/GeoJSON with metadata injection and
utilities to create run directories.
"""
import hashlib
import json
import os
import subprocess
import uuid
from datetime import datetime
from typing import Any, Dict, Optional


def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def read_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(obj: Dict[str, Any], path: str, params: Optional[Dict[str, Any]] = None):
    """Write JSON and inject `__meta__` with timestamp and pipeline info.

    `params` will be stored under `__meta__['params']`.
    """
    _ensure_dir(path)
    meta = obj.get('__meta__', {}) if isinstance(obj, dict) else {}
    meta.setdefault('created_at', datetime.utcnow().isoformat() + 'Z')
    # try to get git commit sha if available
    try:
        sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
        meta.setdefault('pipeline_version', sha)
    except Exception:
        meta.setdefault('pipeline_version', None)
    if params:
        meta.setdefault('params', params)
    if isinstance(obj, dict):
        obj['__meta__'] = meta
    else:
        # wrap non-dict objects
        obj = {'data': obj, '__meta__': meta}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_geojson(obj: Dict[str, Any], path: str):
    _ensure_dir(path)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)


def read_geojson(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def make_run_dir(base: str = 'artifacts/runs', run_id: Optional[str] = None) -> str:
    """Create a run directory and return its path.

    If `run_id` is None, creates one based on timestamp and uuid.
    """
    if run_id is None:
        now = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        run_id = f"{now}-{uuid.uuid4().hex[:8]}"
    path = os.path.join(base, run_id)
    os.makedirs(path, exist_ok=True)
    # optional symlink to latest
    latest = os.path.join(base, 'latest')
    try:
        if os.path.islink(latest) or os.path.exists(latest):
            try:
                os.remove(latest)
            except Exception:
                pass
        os.symlink(os.path.abspath(path), latest)
    except Exception:
        # symlink may fail on some systems; ignore
        pass
    return path


def sha256_of_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()
