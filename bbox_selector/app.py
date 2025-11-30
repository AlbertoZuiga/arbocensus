import os
import json

import dotenv
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

dotenv.load_dotenv()

def find_api_key():
    key = os.getenv('GOOGLE_API_KEY')

    if key:
        return key

    raise RuntimeError('GOOGLE_API_KEY not found in environment.')

@app.route('/')
def index():
    api_key = find_api_key()

    return render_template('index.html', api_key=api_key)


@app.route('/save', methods=['POST'])
def save_bbox():
    data = request.get_json()
    if not data:
        return jsonify({'ok': False, 'error': 'no json'}), 400

    bbox = {
        'north': float(data.get('north')),
        'south': float(data.get('south')),
        'east': float(data.get('east')),
        'west': float(data.get('west')),
    }

    out_path = os.path.join(os.path.dirname(__file__), 'saved_bbox.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(bbox, f, indent=2)

    return jsonify({'ok': True, 'path': out_path})


@app.route('/trees')
def trees():
    try:
        north = float(request.args.get('north'))
        south = float(request.args.get('south'))
        east = float(request.args.get('east'))
        west = float(request.args.get('west'))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': 'invalid bounds'}), 400

    max_results = int(request.args.get('max', 300))

    try:
        import psycopg2
        import psycopg2.extras
    except Exception:
        psycopg2 = None

    results = []
    seen = set()

    def add_point(lat, lng, meta=None):
        if lat is None or lng is None:
            return
        key = (round(float(lat), 6), round(float(lng), 6))
        if key in seen:
            return
        seen.add(key)
        results.append({'lat': float(lat), 'lng': float(lng), 'meta': meta})

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
        val = os.getenv(name)
        if not val:
            return None
        val = val.strip()

        if val.startswith('postgres://') or val.startswith('postgresql://'):
            try:
                return psycopg2.connect(dsn=val)
            except Exception:
                return None

        parsed = parse_jdbc(val)
        if parsed:
            user = os.getenv(name + '_USER') or os.getenv('PGUSER') or os.getenv('DB_USER')
            password = (
                os.getenv(name + '_PASSWORD') or \
                os.getenv('PGPASSWORD') or os.getenv('DB_PASSWORD')
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

    api_conn = get_conn_from_env('ARBOCENSUS_API_DB_URL')
    if api_conn:
        try:
            cur = api_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = '''SELECT id, tree_id, tree_latitude AS lat, tree_longitude AS lng
                     FROM arbocensus_api_app_sample
                     WHERE tree_latitude BETWEEN %s AND %s
                       AND tree_longitude BETWEEN %s AND %s
                     LIMIT %s'''
            cur.execute(sql, (south, north, west, east, max_results))
            for row in cur.fetchall():
                add_point(
                    row.get('lat'),
                    row.get('lng'),
                    {
                        'source': 'arbocensus_api',
                        'id': row.get('id'),
                        'tree_id': row.get('tree_id')
                    }
                )
        except Exception as e:
            # log or ignore; continue to next DB
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
            cur = main_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = '''SELECT id, latitude AS lat, longitude AS lng
                     FROM arbocensus_app_sample
                     WHERE latitude BETWEEN %s AND %s
                       AND longitude BETWEEN %s AND %s
                     LIMIT %s'''
            cur.execute(sql, (south, north, west, east, max_results))
            for row in cur.fetchall():
                add_point(
                    row.get('lat'),
                    row.get('lng'),
                    {
                        'source': 'arbocensus',
                        'id': row.get('id')
                    }
                )
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

    return jsonify({'ok': True, 'trees': results})


if __name__ == '__main__':
    host = os.getenv('HOST', '0.0.0.0')
    debug_env = os.getenv('FLASK_DEBUG', os.getenv('DEBUG', 'False'))
    DEBUG = str(debug_env).lower() in ('1', 'true', 'yes')
    app.run(host=host, port=5000, debug=DEBUG)
