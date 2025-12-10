import json
import os

import dotenv
from flask import Flask, jsonify, render_template, request

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

app = Flask(__name__)

dotenv.load_dotenv()


def find_api_key():
    key = os.getenv("GOOGLE_API_KEY")

    if key:
        return key

    raise RuntimeError("GOOGLE_API_KEY not found in environment.")


@app.route("/")
def index():
    api_key = find_api_key()

    return render_template("index.html", api_key=api_key)


@app.route("/save", methods=["POST"])
def save_bbox():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "no json"}), 400

    bbox = {
        "north": round(float(data.get("north")), 7),
        "south": round(float(data.get("south")), 7),
        "east": round(float(data.get("east")), 7),
        "west": round(float(data.get("west")), 7),
    }

    out_path = os.path.join(os.path.dirname(__file__), "saved_bbox.json")

    # optional trees payload: expect a list of {lat,lng,meta}
    trees = data.get("trees")
    if trees is not None and not isinstance(trees, list):
        return jsonify({"ok": False, "error": "trees must be a list"}), 400

    out_obj = dict(bbox)
    if trees is not None:
        out_obj["trees"] = trees

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, indent=2)

    return jsonify({"ok": True, "path": out_path})


@app.route("/trees")
def get_trees():
    try:
        north = float(request.args.get("north"))
        south = float(request.args.get("south"))
        east = float(request.args.get("east"))
        west = float(request.args.get("west"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "invalid bounds"}), 400

    max_results = int(request.args.get("max", 300))

    results = []
    seen = set()

    def add_point(lat, lng, meta=None):
        if lat is None or lng is None:
            return
        key = (round(float(lat), 7), round(float(lng), 7))
        if key in seen:
            return
        seen.add(key)
        results.append(
            {"lat": round(float(lat), 7), "lng": round(float(lng), 7), "meta": meta}
        )

    def parse_jdbc(jdbc_url):
        if not jdbc_url.startswith("jdbc:postgresql://"):
            return None
        s = jdbc_url[len("jdbc:postgresql://") :]

        if "/" in s:
            hostpart, dbname = s.split("/", 1)
        else:
            hostpart, dbname = s, ""
        if ":" in hostpart:
            db_host, port = hostpart.split(":", 1)
            try:
                port = int(port)
            except ValueError:
                port = None
        else:
            db_host = hostpart
            port = None
        return {"host": db_host, "port": port, "dbname": dbname}

    def get_conn_from_env(name):
        val = os.getenv(name)
        if not val:
            return None
        val = val.strip()

        if val.startswith("postgres://") or val.startswith("postgresql://"):
            try:
                return psycopg2.connect(dsn=val)
            except (psycopg2.Error, OSError):
                return None

        parsed = parse_jdbc(val)
        if parsed:
            user = (
                os.getenv(name + "_USER") or os.getenv("PGUSER") or os.getenv("DB_USER")
            )
            password = (
                os.getenv(name + "_PASSWORD")
                or os.getenv("PGPASSWORD")
                or os.getenv("DB_PASSWORD")
            )
            db_host = parsed.get("host")
            db_port = parsed.get("port")
            db_name = parsed.get("dbname")
            try:
                return psycopg2.connect(
                    host=db_host, port=db_port, dbname=db_name, user=user, password=password
                )
            except (psycopg2.Error, OSError):
                return None
        return None

    api_conn = get_conn_from_env("ARBOCENSUS_API_DB_URL")
    if api_conn:
        try:
            cur = api_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = """SELECT id, tree_id, tree_latitude AS lat, tree_longitude AS lng
                     FROM arbocensus_api_app_sample
                     WHERE tree_latitude BETWEEN %s AND %s
                       AND tree_longitude BETWEEN %s AND %s
                     LIMIT %s"""
            cur.execute(sql, (south, north, west, east, max_results))
            for row in cur.fetchall():
                add_point(
                    row.get("lat"),
                    row.get("lng"),
                    {
                        "source": "arbocensus_api",
                        "id": row.get("id"),
                        "tree_id": row.get("tree_id"),
                    },
                )
        except (psycopg2.Error, OSError) as e:
            # log or ignore; continue to next DB
            print("arbocensus_api query failed:", e)
        finally:
            try:
                cur.close()
            except (psycopg2.Error, AttributeError):
                pass
            try:
                api_conn.close()
            except (psycopg2.Error, AttributeError):
                pass

    main_conn = get_conn_from_env("ARBOCENSUS_DB_URL")
    if main_conn:
        try:
            cur = main_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = """SELECT id, latitude AS lat, longitude AS lng
                     FROM arbocensus_app_sample
                     WHERE latitude BETWEEN %s AND %s
                       AND longitude BETWEEN %s AND %s
                     LIMIT %s"""
            cur.execute(sql, (south, north, west, east, max_results))
            for row in cur.fetchall():
                add_point(
                    row.get("lat"),
                    row.get("lng"),
                    {"source": "arbocensus", "id": row.get("id")},
                )
        except (psycopg2.Error, OSError) as e:
            print("arbocensus query failed:", e)

        finally:
            try:
                cur.close()
            except (psycopg2.Error, AttributeError):
                pass
            try:
                main_conn.close()
            except (psycopg2.Error, AttributeError):
                pass

    return jsonify({"ok": True, "trees": results})


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    debug_env = os.getenv("FLASK_DEBUG", os.getenv("DEBUG", "False"))
    DEBUG = str(debug_env).lower() in ("1", "true", "yes")
    app.run(host=host, port=5000, debug=DEBUG)
