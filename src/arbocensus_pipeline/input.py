"""Input stage: load bbox and trees (DB fallback or file)"""
import json
import os
from typing import Any, Dict, Optional


def load_bbox_file(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_json(obj: Dict[str, Any], path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)


def load_env(repo_root: str = None):
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    dotenv_path = os.path.join(repo_root, '.env')
    try:
        import dotenv
        dotenv.load_dotenv(dotenv_path)
    except Exception:
        # optional dependency - warn but continue
        print('python-dotenv not installed; skipping .env load')


def _parse_jdbc(jdbc_url: str):
    if not isinstance(jdbc_url, str) or not jdbc_url.startswith('jdbc:postgresql://'):
        return None
    s = jdbc_url[len('jdbc:postgresql://'):]
    if '/' in s:
        hostpart, dbname = s.split('/', 1)
    else:
        hostpart, dbname = s, ''
    if ':' in hostpart:
        host, port = hostpart.split(':', 1)
        try:
            port = int(port)
        except Exception:
            port = None
    else:
        host = hostpart
        port = None
    return {'host': host, 'port': port, 'dbname': dbname}


def _get_conn_from_env(name: str):
    try:
        import psycopg2
    except Exception:
        return None

    val = os.getenv(name)
    if not val:
        return None
    val = val.strip()
    # support direct postgres url
    if val.startswith('postgres://') or val.startswith('postgresql://'):
        try:
            return psycopg2.connect(dsn=val)
        except Exception:
            return None

    parsed = _parse_jdbc(val)
    if parsed:
        user = os.getenv(name + '_USER') or os.getenv('PGUSER') or os.getenv('DB_USER')
        password = (os.getenv(name + '_PASSWORD') or os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD'))
        host = parsed.get('host')
        port = parsed.get('port')
        dbname = parsed.get('dbname')
        try:
            return psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        except Exception:
            return None
    return None


def _try_load_secret_db(repo_root: str = None):
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    possible = os.path.join(repo_root, 'secrets', 'heatmap_database_url.txt')
    if os.path.isfile(possible):
        with open(possible, 'r', encoding='utf-8') as f:
            s = f.read().strip()
            if s:
                os.environ.setdefault('ARBOCENSUS_DB_URL', s)
                return True
    return False


def _add_point(results, seen, lat, lng, meta=None):
    if lat is None or lng is None:
        return
    try:
        key = (round(float(lat), 7), round(float(lng), 7))
    except Exception:
        return
    if key in seen:
        return
    seen.add(key)
    results.append({'lat': round(float(lat), 7), 'lng': round(float(lng), 7), 'meta': meta})


def _query_dbs(north: float, south: float, east: float, west: float, max_results: Optional[int] = None):
    results = []
    seen = set()
    # Try ARBOCENSUS_API_DB_URL
    api_conn = _get_conn_from_env('ARBOCENSUS_API_DB_URL')
    if api_conn:
        try:
            cur = api_conn.cursor()
            sql = '''SELECT id, tree_id, tree_latitude AS lat, tree_longitude AS lng
                     FROM arbocensus_api_app_sample
                     WHERE tree_latitude BETWEEN %s AND %s
                       AND tree_longitude BETWEEN %s AND %s
                    ''' + (f'LIMIT %s' if max_results is not None else '')
            cur.execute(sql, (south, north, west, east, max_results) if max_results is not None else (south, north, west, east))
            for row in cur.fetchall():
                _add_point(results, seen, row[2], row[3], {'source': 'arbocensus_api', 'id': row[0], 'tree_id': row[1]})
        except Exception as e:
            print('arbocensus_api query failed:', e)
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                api_conn.close()
            except Exception:
                pass

    main_conn = _get_conn_from_env('ARBOCENSUS_DB_URL')
    if main_conn:
        try:
            cur = main_conn.cursor()
            sql = '''SELECT id, latitude AS lat, longitude AS lng
                     FROM arbocensus_app_sample
                     WHERE latitude BETWEEN %s AND %s
                       AND longitude BETWEEN %s AND %s
                    ''' + (f'LIMIT %s' if max_results is not None else '')
            cur.execute(sql, (south, north, west, east, max_results) if max_results is not None else (south, north, west, east))
            for row in cur.fetchall():
                _add_point(results, seen, row[1], row[2], {'source': 'arbocensus', 'id': row[0]})
        except Exception as e:
            print('arbocensus query failed:', e)
        finally:
            try:
                cur.close()
            except Exception:
                pass
            try:
                main_conn.close()
            except Exception:
                pass

    return results


def load_input(bbox_path: str = None, north: float = None, south: float = None, east: float = None, west: float = None, max_results: Optional[int] = None, use_secrets: bool = False, repo_root: str = None):
    """Load bbox and attempt DB queries; returns a dict with north/south/east/west/trees."""
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    load_env(repo_root)

    # default bbox path: saved_bbox.json in repo root
    if not bbox_path:
        bbox_path = os.path.join(repo_root, 'saved_bbox.json')
    else:
        if not os.path.isabs(bbox_path):
            bbox_path = os.path.join(repo_root, bbox_path)

    bbox_obj = None
    if bbox_path and os.path.isfile(bbox_path):
        try:
            with open(bbox_path, 'r', encoding='utf-8') as f:
                bbox_obj = json.load(f)
        except Exception:
            print(f'Warning: failed to parse bbox JSON at {bbox_path}')
    else:
        # no bbox file found
        pass

    # fallback to repo saved_bbox
    if not bbox_obj:
        fb = os.path.join(repo_root, 'saved_bbox.json')
        if os.path.isfile(fb):
            try:
                with open(fb, 'r', encoding='utf-8') as f:
                    bbox_obj = json.load(f)
                    print(f'Info: using fallback bbox file {fb}')
            except Exception:
                print(f'Warning: failed to parse fallback bbox JSON at {fb}')

    # allow explicit bbox args to override file
    north = north if north is not None else (bbox_obj.get('north') if bbox_obj else None)
    south = south if south is not None else (bbox_obj.get('south') if bbox_obj else None)
    east = east if east is not None else (bbox_obj.get('east') if bbox_obj else None)
    west = west if west is not None else (bbox_obj.get('west') if bbox_obj else None)

    if None in (north, south, east, west):
        raise ValueError('Bounding box incomplete. Provide bbox file or north/south/east/west args.')

    if use_secrets:
        _try_load_secret_db(repo_root)

    trees = []
    try:
        trees = _query_dbs(north, south, east, west, max_results)
    except Exception as e:
        print('DB query stage failed:', e)

    # fallback: if no trees from DB, and bbox_obj contains 'trees', filter those
    if not trees and bbox_obj and isinstance(bbox_obj.get('trees'), list):
        for t in bbox_obj.get('trees'):
            lat = t.get('lat') or t.get('latitude')
            lng = t.get('lng') or t.get('longitude')
            if lat is None or lng is None:
                continue
            if south <= lat <= north and west <= lng <= east:
                trees.append({'lat': float(lat), 'lng': float(lng), 'meta': t})

    out_obj = {'north': north, 'south': south, 'east': east, 'west': west, 'trees': trees}
    return out_obj
