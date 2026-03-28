"""Simple CLI runner for pipeline stages"""

import argparse
import glob
import json
import os
from functools import partial

from . import export
from . import filter as flt
from . import graph
from . import input as inp
from . import io as io_mod
from . import optimize, routing

BBOX_DEFAULT_DIR = "bbox"
RUNS_DEFAULT_DIR = "artifacts/runs"
LATEST_DEFAULT_DIR = f"{RUNS_DEFAULT_DIR}/latest"
INPUT_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/bbox_input/input.json"
GRAPH_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/graph/graph.json"
FILTER_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/filter/filtered.json"
ROUTE_DEFAULT_PATH = f"{LATEST_DEFAULT_DIR}/route/routes.json"
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
    bbox_arg = getattr(args, "bbox", None)

    if bbox_arg and os.path.isdir(bbox_arg):
        bbox_files = glob.glob(os.path.join(bbox_arg, "*.json"))
        if not bbox_files:
            print(f"No JSON files found in directory {bbox_arg}")
            return
        print("Available bbox files:")
        for i, f in enumerate(bbox_files):
            print(f"[{i}] {os.path.basename(f)}")
        try:
            choice = int(input("Select a bbox file by index: "))
            bbox_path = bbox_files[choice]
        except (ValueError, IndexError):
            print("Invalid selection")
            return
    elif bbox_arg:
        bbox_path = bbox_arg
    else:
        # fallback to default directory
        bbox_files = glob.glob(os.path.join(BBOX_DEFAULT_DIR, "*.json"))
        if not bbox_files:
            print(f"No JSON files found in default directory {BBOX_DEFAULT_DIR}")
            return
        print("Available bbox files:")
        for i, f in enumerate(bbox_files):
            print(f"[{i}] {os.path.basename(f)}")
        try:
            choice = int(input("Select a bbox file by index: "))
            bbox_path = bbox_files[choice]
        except (ValueError, IndexError):
            print("Invalid selection")
            return

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
    """Build sparse graph using KD-tree nearest neighbors."""
    inp_path = getattr(args, "inp", FILTER_DEFAULT_PATH)
    if not os.path.exists(inp_path):
        print(f"Input file {inp_path} not found")
        return

    with open(inp_path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    trees = obj.get("trees", [])
    nodes = graph.build_nodes(trees)
    kd_tree = graph.build_kd_tree(nodes)
    k_neighbors = 12
    adjacency = graph.build_sparse_graph_from_kdtree(
        nodes,
        kd_tree,
        k_neighbors=k_neighbors,
    )

    out_obj = {
        "nodes": nodes,
        "adjacency": adjacency,
        "graph_mode": "sparse_kdtree_v3",
        "k_neighbors": k_neighbors,
    }
    out_path = resolve_output_path(args, GRAPH_DEFAULT_PATH, stage_subdir="graph")
    io_mod.write_json(
        out_obj,
        out_path,
        params={
            "source": inp_path,
            "nodes": len(nodes),
            "graph_mode": "sparse_kdtree_v3",
            "k_neighbors": k_neighbors,
        },
    )

    edge_count = sum(len(nbrs) for nbrs in adjacency.values()) // 2
    print(
        f"Wrote sparse graph to {out_path} "
        f"(nodes: {len(nodes)}, undirected_edges: {edge_count}, k_neighbors: {k_neighbors})"
    )


def _make_cached_routing_callables(cache_dir):
    """Create routing callables and attach cache paths used by optimize.find_routes."""
    osm_callable = partial(routing.osm_route_time)
    google_callable = partial(routing.google_route_time)

    setattr(osm_callable, "cache_path", os.path.join(cache_dir, "osm_cache.json"))
    setattr(
        google_callable,
        "cache_path",
        os.path.join(cache_dir, "google_cache.json"),
    )

    return osm_callable, google_callable


def run_stage_route(args=None):
    """Run routing orchestrator and write export-compatible route output."""
    inp_path = getattr(args, "inp", FILTER_DEFAULT_PATH)
    if not os.path.exists(inp_path):
        print(f"Input file {inp_path} not found")
        return

    with open(inp_path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    trees = obj.get("trees", [])
    nodes = graph.build_nodes(trees)
    if not nodes:
        print("No nodes available for route optimization")
        out_path = resolve_output_path(args, ROUTE_DEFAULT_PATH, stage_subdir="route")
        io_mod.write_json({"routes": []}, out_path, params={"source": inp_path})
        print(f"Wrote empty route output to {out_path}")
        return

    expected_s = float(getattr(args, "expected_duration", 150.0)) * 60.0
    tpt_s = float(getattr(args, "time_per_tree", 2.0)) * 60.0
    hard_max_min = getattr(args, "hard_max_duration", None)
    hard_max_s = float(hard_max_min) * 60.0 if hard_max_min is not None else None

    out_path = resolve_output_path(args, ROUTE_DEFAULT_PATH, stage_subdir="route")
    default_cache_dir = os.path.join(os.path.dirname(out_path), "cache")
    cache_dir = getattr(args, "cache_dir", None) or default_cache_dir
    os.makedirs(cache_dir, exist_ok=True)

    f_osm, f_google = _make_cached_routing_callables(cache_dir)

    validated_routes = optimize.find_routes(
        nodes,
        tpt_s,
        f_google,
        f_osm,
        expected_s,
        lower_factor=float(getattr(args, "lower_factor", 0.90)),
        upper_factor=float(getattr(args, "upper_factor", 1.10)),
        k_neighbors=int(getattr(args, "k_neighbors", 12)),
        max_iterations=int(getattr(args, "max_iter", 14)),
        hysteresis_rounds=int(getattr(args, "hysteresis_rounds", 2)),
        hard_max_duration=hard_max_s,
    )

    route_items = []

    for i, (route_indices, total_seconds) in enumerate(validated_routes):
        route_indices = [
            int(idx)
            for idx in route_indices
            if isinstance(idx, (int, float)) and 0 <= int(idx) < len(nodes)
        ]
        service_seconds = len(route_indices) * tpt_s
        travel_seconds = max(0.0, float(total_seconds) - float(service_seconds))
        route_items.append(
            {
                "route": route_indices,
                "cluster_id": i,
                "size": len(route_indices),
                "total_minutes": float(total_seconds) / 60.0,
                "travel_seconds": float(travel_seconds),
                "service_seconds": float(service_seconds),
                "total_seconds": float(total_seconds),
                "validated_by": "google",
            }
        )

    io_mod.write_json(
        {"routes": route_items},
        out_path,
        params={
            "source": inp_path,
            "expected_duration_minutes": float(
                getattr(args, "expected_duration", 150.0)
            ),
            "time_per_tree_minutes": float(getattr(args, "time_per_tree", 2.0)),
            "lower_factor": float(getattr(args, "lower_factor", 0.90)),
            "upper_factor": float(getattr(args, "upper_factor", 1.10)),
            "k_neighbors": int(getattr(args, "k_neighbors", 12)),
            "max_iter": int(getattr(args, "max_iter", 14)),
            "hysteresis_rounds": int(getattr(args, "hysteresis_rounds", 2)),
            "hard_max_duration_minutes": hard_max_min,
            "osm_url": getattr(args, "osm_url", None),
            "cache_dir": cache_dir,
            "validated_by": "google",
        },
    )
    print(f"Wrote {len(route_items)} optimized routes to {out_path}")


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


def _load_clusters_from_routes(routes_path, node_count):
    """Build clusters_map/clusters_list directly from route assignments (V3 source of truth)."""
    clusters_map = {}
    clusters_list = []
    if not os.path.exists(routes_path):
        return clusters_map, clusters_list

    with open(routes_path, "r", encoding="utf-8") as f:
        robj = json.load(f)

    for idx, route_obj in enumerate(robj.get("routes", [])):
        cluster_id = route_obj.get("cluster_id", idx)
        members = []
        for node_idx in route_obj.get("route", []):
            try:
                node_i = int(node_idx)
            except (TypeError, ValueError):
                continue
            if 0 <= node_i < node_count:
                members.append(node_i)

        clusters_list.append(
            {
                "cluster_id": cluster_id,
                "member_node_indices": members,
                "size": len(members),
            }
        )

        for node_i in members:
            clusters_map[node_i] = cluster_id

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
    graph_path = getattr(args, "graph", None) or GRAPH_DEFAULT_PATH
    input_path = getattr(args, "input", None) or INPUT_DEFAULT_PATH
    filtered_path = getattr(args, "filtered", None) or FILTER_DEFAULT_PATH
    out_dir = getattr(args, "outdir", None) or OUTPUT_DEFAULT_PATH
    routes_path = getattr(args, "routes", None) or ROUTE_DEFAULT_PATH

    return {
        "graph": graph_path,
        "input": input_path,
        "filtered": filtered_path,
        "routes": routes_path,
        "out_dir": out_dir,
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

    # Route assignments are the source of truth for cluster layers.
    clusters_map, clusters_list = _load_clusters_from_routes(
        paths["routes"], len(nodes)
    )
    if not clusters_list:
        print(
            "Warning: no valid route-based clusters found for export; "
            "writing empty cluster layers"
        )

    _export_cluster_data(nodes, clusters_map, clusters_list, paths["out_dir"])

    _export_routes(paths["routes"], nodes, paths["out_dir"])


def run_all(args=None):
    run_stage_input(args)
    run_stage_filter(args)
    run_stage_graph(args)
    run_stage_route(args)
    run_export(args)


def _setup_input_parser(subparsers):
    """Configure input subcommand parser."""
    si = subparsers.add_parser("input")
    si.add_argument(
        "--bbox",
        default=None,
        help="Path to bbox file or directory containing bbox JSON files",
    )
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


def _setup_route_parser(subparsers):
    """Configure route subcommand parser."""
    sr = subparsers.add_parser("route")
    sr.add_argument("--inp", default=FILTER_DEFAULT_PATH)
    sr.add_argument("--out", default=ROUTE_DEFAULT_PATH)
    sr.add_argument("--expected-duration", type=float, default=150.0)
    sr.add_argument("--time-per-tree", type=float, default=2.0)
    sr.add_argument("--lower-factor", type=float, default=0.90)
    sr.add_argument("--upper-factor", type=float, default=1.10)
    sr.add_argument("--k-neighbors", type=int, default=12)
    sr.add_argument("--max-iter", type=int, default=14)
    sr.add_argument("--hysteresis-rounds", type=int, default=2)
    sr.add_argument("--hard-max-duration", type=float, default=None)
    sr.add_argument("--osm-url", default=None)
    sr.add_argument("--use-google", action="store_true")
    sr.add_argument("--cache-dir", default=None)


def _setup_export_parser(subparsers):
    """Configure export subcommand parser."""
    se = subparsers.add_parser("export")
    se.add_argument("--graph", default=GRAPH_DEFAULT_PATH)
    se.add_argument("--input", default=INPUT_DEFAULT_PATH)
    se.add_argument("--filtered", default=FILTER_DEFAULT_PATH)
    se.add_argument("--routes", default=ROUTE_DEFAULT_PATH)
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
    _setup_route_parser(sub)
    _setup_export_parser(sub)

    args = p.parse_args()
    if args.cmd == "input":
        run_stage_input(args)
    elif args.cmd == "filter":
        run_stage_filter(args)
    elif args.cmd == "graph":
        print("Running graph stage with KD-tree sparse graph builder")
        run_stage_graph(args)
    elif args.cmd == "route":
        run_stage_route(args)
    elif args.cmd == "export":
        run_export(args)
    elif args.cmd is None:
        print("No command specified, running all stages sequentially")
        run_all(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
