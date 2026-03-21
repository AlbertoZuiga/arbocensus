"""Simple CLI runner for pipeline stages"""

import argparse
import json
import math
import os

from . import cluster, export
from . import filter as flt
from . import graph
from . import input as inp
from . import io as io_mod
from . import tsp

BBOX_DEFAULT_PATH = "saved_bbox.json"
RUNS_DEFAULT_DIR = "artifacts/runs"
LATEST_DEFAULT_DIR = f"{RUNS_DEFAULT_DIR}/latest"
INPUT_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/bbox_input/input.json"
GRAPH_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/graph/graph.json"
FILTER_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/filter/filtered.json"
CLUSTER_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/cluster/clusters_by_censantes.json"
ROUTES_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/tsp/routes_by_cluster.json"
OUTPUT_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/output"


def resolve_output_path(args, default_path, stage_subdir=None):
    out_path = getattr(args, "out", default_path)
    run_id = getattr(args, "run_id", None)
    outdir = getattr(args, "outdir", None)

    if run_id or outdir:
        run_dir = io_mod.make_run_dir(
            base=outdir if outdir else RUNS_DEFAULT_DIR,
            run_id=run_id,
        )
        target_dir = os.path.join(run_dir, stage_subdir) if stage_subdir else run_dir
        os.makedirs(target_dir, exist_ok=True)
        return os.path.join(target_dir, os.path.basename(out_path))

    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    return out_path

def run_stage_input(args=None):
    bbox_path = getattr(args, "bbox", BBOX_DEFAULT_PATH)
    max_results = getattr(args, "max", None)
    use_secrets = bool(getattr(args, "use_secrets", False))

    try:
        out_obj = inp.load_input(
            bbox_path=bbox_path,
            max_results=max_results,
            use_secrets=use_secrets,
        )
    except (ValueError, OSError, RuntimeError) as e:
        print("Failed to load input:", e)
        return

    out_path = resolve_output_path(args, INPUT_DEFAULT_PATH, stage_subdir="bbox_input")
    io_mod.write_json(out_obj, out_path, params={"bbox": bbox_path})
    print(f'Wrote {len(out_obj.get("trees", []))} trees to {out_path}')


def run_stage_filter(args=None):
    inp_path = getattr(args, "inp", INPUT_DEFAULT_PATH)
    if not os.path.exists(inp_path):
        print(f"Input file {inp_path} not found")
        return
    with open(inp_path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    res = flt.filter_trees(obj)
    out_path = resolve_output_path(args, FILTER_DEFAULT_PATH, stage_subdir="filter")
    io_mod.write_json(res, out_path, params={"source": inp_path})
    print(f"Wrote filtered output to {out_path}")


def run_stage_graph(args=None):
    inp_path = getattr(args, "inp", FILTER_DEFAULT_PATH)
    if not os.path.exists(inp_path):
        print(f"Input file {inp_path} not found")
        return
    with open(inp_path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    trees = obj.get("trees", [])
    nodes = graph.build_nodes(trees)
    mat = graph.compute_matrix(nodes)
    out_obj = {"nodes": nodes, "distances": mat}
    out_path = resolve_output_path(args, GRAPH_DEFAULT_PATH, stage_subdir="graph")
    io_mod.write_json(
        out_obj, out_path, params={"source": inp_path, "nodes": len(nodes)}
    )
    print(f"Wrote graph to {out_path} (nodes: {len(nodes)})")


def run_stage_cluster(args=None):
    inp_path = getattr(args, "inp", GRAPH_DEFAULT_PATH)
    if not os.path.exists(inp_path):
        print(f"Graph file {inp_path} not found")
        return
    with open(inp_path, "r", encoding="utf-8") as f:
        g = json.load(f)
    nodes = g.get("nodes", [])
    n = len(nodes)
    if n == 0:
        print("No nodes in graph")
        return
    desired_k = max(1, int(getattr(args, "num", 8)))
    max_size = math.ceil(n / desired_k)
    clusters_list = cluster.make_clusters_recursive(nodes, max_size=max_size)
    clusters_out = []
    for cid, members in enumerate(clusters_list):
        clusters_out.append(
            {"cluster_id": cid, "member_node_indices": members, "size": len(members)}
        )
    out_path = resolve_output_path(args, CLUSTER_DEFAULT_PATH, stage_subdir="cluster")
    io_mod.write_json(
        {"clusters": clusters_out}, out_path, params={"k_target": desired_k}
    )
    print(f"Wrote {len(clusters_out)} clusters to {out_path}")


def run_stage_tsp(args=None):
    graph_path = getattr(args, "graph", GRAPH_DEFAULT_PATH)
    clusters_path = getattr(args, "clusters", CLUSTER_DEFAULT_PATH)

    if not os.path.exists(graph_path):
        print(f"Graph file {graph_path} not found")
        return
    if not os.path.exists(clusters_path):
        print(f"Clusters file {clusters_path} not found")
        return
    with open(graph_path, "r", encoding="utf-8") as f:
        g = json.load(f)
    with open(clusters_path, "r", encoding="utf-8") as f:
        cobj = json.load(f)
    distances = g.get("distances", [])
    clusters = cobj.get("clusters") or cobj.get("cluster_list") or []
    routes = []
    # sensible defaults
    time_per_tree = getattr(args, "time_per_tree", 1.5)
    walking_kmh = getattr(args, "walking_kmh", 5.0)
    for c in clusters:
        members = c.get("member_node_indices", [])
        if not members:
            continue
        res = tsp.compute_route_for_cluster(
            members,
            distances,
            time_per_tree=time_per_tree,
            walking_speed_kmh=walking_kmh,
        )
        res["cluster_id"] = c.get("cluster_id")
        res["size"] = len(members)
        routes.append(res)
    out_path = resolve_output_path(args, ROUTES_DEFAULT_PATH, stage_subdir="tsp")
    io_mod.write_json(
        {"routes": routes},
        out_path,
        params={"time_per_tree": time_per_tree, "walking_kmh": walking_kmh},
    )
    print(f"Wrote routes for {len(routes)} clusters to {out_path}")


def _export_bbox_and_input_points(bbox_data, out_dir):
    """Export bbox.geojson and input_points.geojson."""
    north = bbox_data.get("north")
    south = bbox_data.get("south")
    east = bbox_data.get("east")
    west = bbox_data.get("west")
    if all(v is not None for v in [north, south, east, west]):
        bbox_geo = export.build_bbox_geojson(north, south, east, west)
        bbox_path = os.path.join(out_dir, "bbox.geojson")
        export.write_geojson(bbox_geo, bbox_path)
        print(f"Wrote {bbox_path}")

    raw_trees = bbox_data.get("trees", [])
    if raw_trees:
        input_geo = export.build_points_geojson_from_trees(raw_trees)
        input_pts_path = os.path.join(out_dir, "input_points.geojson")
        export.write_geojson(input_geo, input_pts_path)
        print(f"Wrote {input_pts_path}")


def _export_filtered_points(filtered_path, out_dir):
    """Export filtered_points.geojson."""
    if not os.path.exists(filtered_path):
        return
    with open(filtered_path, "r", encoding="utf-8") as f:
        filtered_data = json.load(f)
    filtered_trees = filtered_data.get("trees", [])
    if filtered_trees:
        filtered_geo = export.build_points_geojson_from_trees(filtered_trees)
        filtered_pts_path = os.path.join(out_dir, "filtered_points.geojson")
        export.write_geojson(filtered_geo, filtered_pts_path)
        print(f"Wrote {filtered_pts_path}")


def _load_clusters(clusters_path):
    """Load clusters and return clusters_map and clusters_list."""
    clusters_map = {}
    clusters_list = []
    if not os.path.exists(clusters_path):
        return clusters_map, clusters_list
    with open(clusters_path, "r", encoding="utf-8") as f:
        cobj = json.load(f)
    clusters_list = cobj.get("clusters", [])
    for c in clusters_list:
        for i in c.get("member_node_indices", []):
            clusters_map[i] = c.get("cluster_id")
    return clusters_map, clusters_list


def _export_routes(routes_path, nodes, out_dir):
    """Export routes.geojson."""
    if not os.path.exists(routes_path):
        return
    with open(routes_path, "r", encoding="utf-8") as f:
        robj = json.load(f)
    routes = robj.get("routes", [])
    rgeo = export.build_routes_geojson(nodes, routes)
    rpath = os.path.join(out_dir, "routes.geojson")
    export.write_geojson(rgeo, rpath)
    print(f"Wrote {rpath}")


def _get_export_paths(args):
    """Extract all file paths from args for export stage."""
    return {
        "graph": getattr(args, "graph", GRAPH_DEFAULT_PATH),
        "input": getattr(args, "input", INPUT_DEFAULT_PATH),
        "filtered": getattr(args, "filtered", FILTER_DEFAULT_PATH),
        "clusters": getattr(args, "clusters", CLUSTER_DEFAULT_PATH),
        "routes": getattr(args, "routes", ROUTES_DEFAULT_PATH),
        "out_dir": getattr(args, "outdir", OUTPUT_DEFAULT_PATH),
    }


def _export_cluster_data(nodes, clusters_map, clusters_list, out_dir):
    """Export clusters.geojson and cluster_polygons.geojson."""
    pts = export.build_points_geojson_from_nodes(nodes, clusters_map)
    pts_path = os.path.join(out_dir, "clusters.geojson")
    export.write_geojson(pts, pts_path)
    print(f"Wrote {pts_path}")

    if clusters_list:
        cluster_polygons = export.build_cluster_polygons_geojson(nodes, clusters_list)
        polygons_path = os.path.join(out_dir, "cluster_polygons.geojson")
        export.write_geojson(cluster_polygons, polygons_path)
        print(f"Wrote {polygons_path}")


def run_export(args=None):
    paths = _get_export_paths(args)
    os.makedirs(paths["out_dir"], exist_ok=True)

    if not os.path.exists(paths["graph"]):
        print(f"Graph file {paths['graph']} not found")
        return

    with open(paths["graph"], "r", encoding="utf-8") as f:
        nodes = json.load(f).get("nodes", [])

    if os.path.exists(paths["input"]):
        with open(paths["input"], "r", encoding="utf-8") as f:
            _export_bbox_and_input_points(json.load(f), paths["out_dir"])

    _export_filtered_points(paths["filtered"], paths["out_dir"])

    clusters_map, clusters_list = _load_clusters(paths["clusters"])
    _export_cluster_data(nodes, clusters_map, clusters_list, paths["out_dir"])

    _export_routes(paths["routes"], nodes, paths["out_dir"])


def run_all():
    run_stage_input()
    run_stage_filter()
    run_stage_graph()
    run_stage_cluster()
    run_stage_tsp()
    run_export()

def _setup_input_parser(subparsers):
    """Configure input subcommand parser."""
    si = subparsers.add_parser("input")
    si.add_argument("--bbox", default=BBOX_DEFAULT_PATH)
    si.add_argument("--out", default=INPUT_DEFAULT_PATH)


def _setup_filter_parser(subparsers):
    """Configure filter subcommand parser."""
    sf = subparsers.add_parser("filter")
    sf.add_argument("--inp", default=INPUT_DEFAULT_PATH)
    sf.add_argument("--out", default=FILTER_DEFAULT_PATH)


def _setup_graph_parser(subparsers):
    """Configure graph subcommand parser."""
    sg = subparsers.add_parser("graph")
    sg.add_argument("--inp", default=FILTER_DEFAULT_PATH)
    sg.add_argument("--out", default=GRAPH_DEFAULT_PATH)


def _setup_cluster_parser(subparsers):
    """Configure cluster subcommand parser."""
    sc = subparsers.add_parser("cluster")
    sc.add_argument("--inp", default=GRAPH_DEFAULT_PATH)
    sc.add_argument(
        "--out", default=CLUSTER_DEFAULT_PATH
    )
    sc.add_argument("--num", type=int, default=8)
    sc.add_argument("--time", type=float, default=1.5)


def _setup_tsp_parser(subparsers):
    """Configure tsp subcommand parser."""
    st = subparsers.add_parser("tsp")
    st.add_argument("--graph", default=GRAPH_DEFAULT_PATH)
    st.add_argument(
        "--clusters", default=CLUSTER_DEFAULT_PATH
    )
    st.add_argument("--out", default=ROUTES_DEFAULT_PATH)
    st.add_argument("--time-per-tree", type=float, default=1.5)
    st.add_argument("--walking-kmh", type=float, default=5.0)


def _setup_export_parser(subparsers):
    """Configure export subcommand parser."""
    se = subparsers.add_parser("export")
    se.add_argument("--graph", default=GRAPH_DEFAULT_PATH)
    se.add_argument("--input", default=INPUT_DEFAULT_PATH)
    se.add_argument("--filtered", default=FILTER_DEFAULT_PATH)
    se.add_argument(
        "--clusters", default=CLUSTER_DEFAULT_PATH
    )
    se.add_argument(
        "--routes", default=ROUTES_DEFAULT_PATH
    )
    se.add_argument("--outdir", default=OUTPUT_DEFAULT_PATH)


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--outdir",
        default=None,
        help="Base directory for run artifacts (will create artifacts/runs/<id>)",
    )
    p.add_argument(
        "--run-id",
        default=None,
        help="Optional run id; if omitted a timestamped id is created",
    )
    sub = p.add_subparsers(dest="cmd")

    _setup_input_parser(sub)
    _setup_filter_parser(sub)
    _setup_graph_parser(sub)
    _setup_cluster_parser(sub)
    _setup_tsp_parser(sub)
    _setup_export_parser(sub)

    args = p.parse_args()
    if args.cmd == "input":
        run_stage_input(args)
    elif args.cmd == "filter":
        run_stage_filter(args)
    elif args.cmd == "graph":
        run_stage_graph(args)
    elif args.cmd == "cluster":
        run_stage_cluster(args)
    elif args.cmd == "tsp":
        run_stage_tsp(args)
    elif args.cmd == "export":
        run_export(args)
    elif args.cmd is None:
        print("No command specified, running all stages sequentially")
        run_all()
    else:
        p.print_help()


if __name__ == "__main__":
    main()
