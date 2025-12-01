#!/usr/bin/env python3
"""Load trees for a bbox: try DB queries like bbox_selector, fallback to saved_bbox.json

Usage:
  python load_input.py --bbox saved_bbox.json --out ../01_bbox_input/01_input.json
  python load_input.py --north -33.44 --south -33.45 --east -70.53 --west -70.55 --out out.json

Behaviour:
  - Attempts to read DB connection strings from environment variables
    `ARBOCENSUS_API_DB_URL` and `ARBOCENSUS_DB_URL` (same names used in bbox_selector).
  - If not set, will try `secrets/heatmap_database_url.txt` to populate `ARBOCENSUS_DB_URL`.
  - If no DB is reachable, will write a JSON containing the bbox and any `trees` found in the input bbox file.
"""
import argparse
import json
import os
import sys
import dotenv


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--bbox', help='Path to bbox JSON (default: saved_bbox.json in repo root)')
    p.add_argument('--north', type=float)
    p.add_argument('--south', type=float)
    p.add_argument('--east', type=float)
    p.add_argument('--west', type=float)
    p.add_argument('--max', type=int, default=500)
    p.add_argument('--out', help='Output json path', default='stages/01_bbox_input/01_input.json')
    p.add_argument('--use-secrets', action='store_true', help='Try secrets/heatmap_database_url.txt if env missing')
    return p.parse_args()


def load_bbox_from_file(path):
    if not os.path.isfile(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except Exception:
            return None


def parse_jdbc(jdbc_url):
    if not jdbc_url.startswith('jdbc:postgresql://'):
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
        except ValueError:
            port = None
    else:
        host = hostpart
        port = None
    return {'host': host, 'port': port, 'dbname': dbname}


def get_conn_from_env(name):
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

    parsed = parse_jdbc(val)
    if parsed:
        user = os.getenv(name + '_USER') or os.getenv('PGUSER') or os.getenv('DB_USER')
        password = (
            os.getenv(name + '_PASSWORD') or os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD')
        )
        host = parsed.get('host')
        port = parsed.get('port')
        dbname = parsed.get('dbname')
        try:
            return psycopg2.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password
            )
        except Exception:
            return None
    return None


def try_load_secret_db():
    # Look for secrets/heatmap_database_url.txt relative to repo root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    possible = os.path.join(repo_root, 'secrets', 'heatmap_database_url.txt')
    if os.path.isfile(possible):
        with open(possible, 'r', encoding='utf-8') as f:
            s = f.read().strip()
            if s:
                os.environ.setdefault('ARBOCENSUS_DB_URL', s)
                return True
    return False


def add_point(results, seen, lat, lng, meta=None):
    if lat is None or lng is None:
        return
    key = (round(float(lat), 6), round(float(lng), 6))
    if key in seen:
        return
    seen.add(key)
    results.append({'lat': float(lat), 'lng': float(lng), 'meta': meta})


def query_dbs(north, south, east, west, max_results=500):
    results = []
    seen = set()

    # Try ARBOCENSUS_API_DB_URL
    api_conn = get_conn_from_env('ARBOCENSUS_API_DB_URL')
    if api_conn:
        try:
            cur = api_conn.cursor()
            sql = '''SELECT id, tree_id, tree_latitude AS lat, tree_longitude AS lng
                     FROM arbocensus_api_app_sample
                     WHERE tree_latitude BETWEEN %s AND %s
                       AND tree_longitude BETWEEN %s AND %s
                     LIMIT %s'''
            cur.execute(sql, (south, north, west, east, max_results))
            for row in cur.fetchall():
                add_point(results, seen, row[2], row[3], {'source': 'arbocensus_api', 'id': row[0], 'tree_id': row[1]})
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

    main_conn = get_conn_from_env('ARBOCENSUS_DB_URL')
    if main_conn:
        try:
            cur = main_conn.cursor()
            sql = '''SELECT id, latitude AS lat, longitude AS lng
                     FROM arbocensus_app_sample
                     WHERE latitude BETWEEN %s AND %s
                       AND longitude BETWEEN %s AND %s
                     LIMIT %s'''
            cur.execute(sql, (south, north, west, east, max_results))
            for row in cur.fetchall():
                add_point(results, seen, row[1], row[2], {'source': 'arbocensus', 'id': row[0]})
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


def main():
    # Load .env from repo root so environment variables used by bbox_selector are available
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    dotenv_path = os.path.join(repo_root, '.env')
    dotenv.load_dotenv(dotenv_path)

    args = parse_args()

    # default bbox path: saved_bbox.json in repo root
    if not args.bbox:
        args.bbox = os.path.join(repo_root, 'saved_bbox.json')
    else:
        # if a relative path was given, make it relative to repo root
        if not os.path.isabs(args.bbox):
            args.bbox = os.path.join(repo_root, args.bbox)

    bbox_obj = None
    if args.bbox:
        if os.path.isfile(args.bbox):
            bbox_obj = load_bbox_from_file(args.bbox)
            if bbox_obj is None:
                print(f'Warning: failed to parse bbox JSON at {args.bbox}')
        else:
            print(f'Info: bbox file not found at {args.bbox}')

    # final fallback: try repo_root/saved_bbox.json explicitly if still missing
    if not bbox_obj:
        fb = os.path.join(repo_root, 'saved_bbox.json')
        if os.path.isfile(fb):
            bbox_obj = load_bbox_from_file(fb)
            if bbox_obj:
                print(f'Info: using fallback bbox file {fb}')
            else:
                print(f'Warning: failed to parse fallback bbox JSON at {fb}')

    # allow explicit bbox args to override file
    north = args.north if args.north is not None else (bbox_obj.get('north') if bbox_obj else None)
    south = args.south if args.south is not None else (bbox_obj.get('south') if bbox_obj else None)
    east = args.east if args.east is not None else (bbox_obj.get('east') if bbox_obj else None)
    west = args.west if args.west is not None else (bbox_obj.get('west') if bbox_obj else None)

    if None in (north, south, east, west):
        print('Bounding box incomplete. Provide --bbox file or north/south/east/west args.')
        sys.exit(2)

    # Try to set DB env from secrets if requested
    if args.use_secrets:
        try_load_secret_db()

    trees = []
    try:
        trees = query_dbs(north, south, east, west, args.max)
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

    out_obj = {
        'north': north,
        'south': south,
        'east': east,
        'west': west,
        'trees': trees
    }

    out_path = args.out
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out_obj, f, indent=2)

    print(f'Wrote {len(trees)} trees to {out_path}')


if __name__ == '__main__':
    main()
