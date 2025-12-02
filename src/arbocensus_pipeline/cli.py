"""Simple CLI runner for pipeline stages"""

import argparse
import os

from . import cluster, export
from . import filter as flt
from . import graph
from . import input as inp
from . import io as io_mod
from . import tsp


def run_stage_input(args):
    # Use package helpers to load bbox and write the input JSON (with DB fallback)
    try:
        out_obj = inp.load_input(
            bbox_path=args.bbox,
            max_results=getattr(args, "max", None),
            use_secrets=getattr(args, "use_secrets", False),
        )
    except Exception as e:
        print("Failed to load input:", e)
        return
    out_path = args.out
    if getattr(args, "run_id", None) or getattr(args, "outdir", None):
        run_dir = io_mod.make_run_dir(
            base=args.outdir if getattr(args, "outdir", None) else "artifacts/runs",
            run_id=getattr(args, "run_id", None),
        )
        # preserve stage subdir structure
        stage_sub = os.path.join(run_dir, "bbox_input")
        os.makedirs(stage_sub, exist_ok=True)
        out_path = os.path.join(stage_sub, os.path.basename(args.out))
    io_mod.write_json(out_obj, out_path, params={"bbox": args.bbox})
    print(f'Wrote {len(out_obj.get("trees", []))} trees to {out_path}')


def run_stage_filter(args):
    # Read input JSON, apply in-package filter and write result
    import json

    if not os.path.exists(args.inp):
        print(f"Input file {args.inp} not found")
        return
    with open(args.inp, "r", encoding="utf-8") as f:
        obj = json.load(f)
    res = flt.filter_trees(obj)
    out_path = args.out
    if getattr(args, "run_id", None) or getattr(args, "outdir", None):
        run_dir = io_mod.make_run_dir(
            base=args.outdir if getattr(args, "outdir", None) else "artifacts/runs",
            run_id=getattr(args, "run_id", None),
        )
        out_path = os.path.join(run_dir, os.path.basename(args.out))
    io_mod.write_json(res, out_path, params={"source": args.inp})
    print(f"Wrote filtered output to {out_path}")


def run_stage_graph(args):
    import json

    if not os.path.exists(args.inp):
        print(f"Input file {args.inp} not found")
        return
    with open(args.inp, "r", encoding="utf-8") as f:
        obj = json.load(f)
    trees = obj.get("trees", [])
    nodes = graph.build_nodes(trees)
    mat = graph.compute_matrix(nodes)
    out_obj = {"nodes": nodes, "distances": mat}
    out_path = args.out
    if getattr(args, "run_id", None) or getattr(args, "outdir", None):
        run_dir = io_mod.make_run_dir(
            base=args.outdir if getattr(args, "outdir", None) else "artifacts/runs",
            run_id=getattr(args, "run_id", None),
        )
        out_path = os.path.join(run_dir, os.path.basename(args.out))
    io_mod.write_json(
        out_obj, out_path, params={"source": args.inp, "nodes": len(nodes)}
    )
    print(f"Wrote graph to {out_path} (nodes: {len(nodes)})")


def run_stage_cluster(args):
    import json
    import math

    if not os.path.exists(args.inp):
        print(f"Graph file {args.inp} not found")
        return
    with open(args.inp, "r", encoding="utf-8") as f:
        g = json.load(f)
    nodes = g.get("nodes", [])
    n = len(nodes)
    if n == 0:
        print("No nodes in graph")
        return
    desired_k = max(1, int(args.num))
    max_size = math.ceil(n / desired_k)
    clusters_list = cluster.make_clusters_recursive(nodes, max_size=max_size)
    clusters_out = []
    for cid, members in enumerate(clusters_list):
        clusters_out.append(
            {"cluster_id": cid, "member_node_indices": members, "size": len(members)}
        )
    out_path = args.out
    if getattr(args, "run_id", None) or getattr(args, "outdir", None):
        run_dir = io_mod.make_run_dir(
            base=args.outdir if getattr(args, "outdir", None) else "artifacts/runs",
            run_id=getattr(args, "run_id", None),
        )
        out_path = os.path.join(run_dir, os.path.basename(args.out))
    io_mod.write_json(
        {"clusters": clusters_out}, out_path, params={"k_target": desired_k}
    )
    print(f"Wrote {len(clusters_out)} clusters to {out_path}")


def run_stage_tsp(args):
    import json

    if not os.path.exists(args.graph):
        print(f"Graph file {args.graph} not found")
        return
    if not os.path.exists(args.clusters):
        print(f"Clusters file {args.clusters} not found")
        return
    with open(args.graph, "r", encoding="utf-8") as f:
        g = json.load(f)
    with open(args.clusters, "r", encoding="utf-8") as f:
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
    out_path = args.out
    if getattr(args, "run_id", None) or getattr(args, "outdir", None):
        run_dir = io_mod.make_run_dir(
            base=args.outdir if getattr(args, "outdir", None) else "artifacts/runs",
            run_id=getattr(args, "run_id", None),
        )
        out_path = os.path.join(run_dir, os.path.basename(args.out))
    io_mod.write_json(
        {"routes": routes},
        out_path,
        params={"time_per_tree": time_per_tree, "walking_kmh": walking_kmh},
    )
    print(f"Wrote routes for {len(routes)} clusters to {out_path}")


def run_export(args):
    import json

    # read graph, clusters, routes from archive paths by default
    graph_path = (
        args.graph
        if hasattr(args, "graph")
        else "artifacts/runs/latest/graph/graph.json"
    )
    input_path = getattr(args, "input", "artifacts/runs/latest/bbox_input/input.json")
    filtered_path = getattr(
        args, "filtered", "artifacts/runs/latest/filter/filtered.json"
    )
    clusters_path = (
        args.clusters
        if hasattr(args, "clusters")
        else "artifacts/runs/latest/cluster/clusters_by_censantes.json"
    )
    routes_path = (
        args.routes
        if hasattr(args, "routes")
        else "artifacts/runs/latest/tsp/routes_by_cluster.json"
    )
    out_dir = getattr(args, "outdir", "artifacts/runs/latest/output")
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(graph_path):
        print(f"Graph file {graph_path} not found")
        return

    with open(graph_path, "r", encoding="utf-8") as f:
        g = json.load(f)
    nodes = g.get("nodes", [])

    # Load input for bbox
    bbox_data = None
    if os.path.exists(input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            bbox_data = json.load(f)

        # Generate bbox.geojson
        north = bbox_data.get("north")
        south = bbox_data.get("south")
        east = bbox_data.get("east")
        west = bbox_data.get("west")
        if all(v is not None for v in [north, south, east, west]):
            bbox_geo = export.build_bbox_geojson(north, south, east, west)
            bbox_path = os.path.join(out_dir, "bbox.geojson")
            export.write_geojson(bbox_geo, bbox_path)
            print(f"Wrote {bbox_path}")

        # Generate input_points.geojson (raw trees)
        raw_trees = bbox_data.get("trees", [])
        if raw_trees:
            input_geo = export.build_points_geojson_from_trees(raw_trees)
            input_pts_path = os.path.join(out_dir, "input_points.geojson")
            export.write_geojson(input_geo, input_pts_path)
            print(f"Wrote {input_pts_path}")

    # Generate filtered_points.geojson
    if os.path.exists(filtered_path):
        with open(filtered_path, "r", encoding="utf-8") as f:
            filtered_data = json.load(f)
        filtered_trees = filtered_data.get("trees", [])
        if filtered_trees:
            filtered_geo = export.build_points_geojson_from_trees(filtered_trees)
            filtered_pts_path = os.path.join(out_dir, "filtered_points.geojson")
            export.write_geojson(filtered_geo, filtered_pts_path)
            print(f"Wrote {filtered_pts_path}")

    # Load clusters
    clusters_map = {}
    clusters_list = []
    if os.path.exists(clusters_path):
        with open(clusters_path, "r", encoding="utf-8") as f:
            cobj = json.load(f)
        clusters_list = cobj.get("clusters", [])
        for c in clusters_list:
            for i in c.get("member_node_indices", []):
                clusters_map[i] = c.get("cluster_id")

    # Build clusters.geojson (nodes colored by cluster)
    pts = export.build_points_geojson_from_nodes(nodes, clusters_map)
    pts_path = os.path.join(out_dir, "clusters.geojson")
    export.write_geojson(pts, pts_path)
    print(f"Wrote {pts_path}")

    # Build cluster_polygons.geojson
    if clusters_list:
        cluster_polygons = export.build_cluster_polygons_geojson(nodes, clusters_list)
        polygons_path = os.path.join(out_dir, "cluster_polygons.geojson")
        export.write_geojson(cluster_polygons, polygons_path)
        print(f"Wrote {polygons_path}")

    # routes
    if os.path.exists(routes_path):
        with open(routes_path, "r", encoding="utf-8") as f:
            robj = json.load(f)
        routes = robj.get("routes", [])
        rgeo = export.build_routes_geojson(nodes, routes)
        rpath = os.path.join(out_dir, "routes.geojson")
        export.write_geojson(rgeo, rpath)
        print(f"Wrote {rpath}")


def main():
    p = argparse.ArgumentParser()
    # global options controlling output/run directories
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

    si = sub.add_parser("input")
    si.add_argument("--bbox", default="saved_bbox.json")
    si.add_argument("--out", default="artifacts/runs/latest/bbox_input/input.json")

    sf = sub.add_parser("filter")
    sf.add_argument("--inp", default="artifacts/runs/latest/bbox_input/input.json")
    sf.add_argument("--out", default="artifacts/runs/latest/filter/filtered.json")

    sg = sub.add_parser("graph")
    sg.add_argument("--inp", default="artifacts/runs/latest/filter/filtered.json")
    sg.add_argument("--out", default="artifacts/runs/latest/graph/graph.json")

    sc = sub.add_parser("cluster")
    sc.add_argument("--inp", default="artifacts/runs/latest/graph/graph.json")
    sc.add_argument(
        "--out", default="artifacts/runs/latest/cluster/clusters_by_censantes.json"
    )
    sc.add_argument("--num", type=int, default=8)
    sc.add_argument("--time", type=float, default=1.5)

    st = sub.add_parser("tsp")
    st.add_argument("--graph", default="artifacts/runs/latest/graph/graph.json")
    st.add_argument(
        "--clusters", default="artifacts/runs/latest/cluster/clusters_by_censantes.json"
    )
    st.add_argument("--out", default="artifacts/runs/latest/tsp/routes_by_cluster.json")
    st.add_argument("--time-per-tree", type=float, default=1.5)
    st.add_argument("--walking-kmh", type=float, default=5.0)

    se = sub.add_parser("export")
    se.add_argument("--graph", default="artifacts/runs/latest/graph/graph.json")
    se.add_argument("--input", default="artifacts/runs/latest/bbox_input/input.json")
    se.add_argument("--filtered", default="artifacts/runs/latest/filter/filtered.json")
    se.add_argument(
        "--clusters", default="artifacts/runs/latest/cluster/clusters_by_censantes.json"
    )
    se.add_argument(
        "--routes", default="artifacts/runs/latest/tsp/routes_by_cluster.json"
    )
    se.add_argument("--outdir", default="artifacts/runs/latest/output")

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
    else:
        p.print_help()


if __name__ == "__main__":
    main()
