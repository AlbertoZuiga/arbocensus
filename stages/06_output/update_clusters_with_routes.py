#!/usr/bin/env python3
"""Update clusters_by_censantes.json member_node_indices from routes_by_cluster.json

Behaviour:
 - loads `stages/04_cluster/clusters_by_censantes.json` and `stages/05_tsp/routes_by_cluster.json`
 - for each cluster in clusters file, if a route with same cluster_id exists, it:
   - saves original `member_node_indices` to `original_member_node_indices`
   - sets `ordered_member_node_indices` to the route order
   - replaces `member_node_indices` with the route order (so downstream stages use ordered members)
 - writes back clusters file (overwrites)
"""
import json
import os
from typing import Dict, List


CLUSTERS = 'stages/04_cluster/clusters_by_censantes.json'
ROUTES = 'stages/05_tsp/routes_by_cluster.json'


def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save(path, obj):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main():
    if not os.path.exists(CLUSTERS):
        print('clusters file not found:', CLUSTERS); return
    if not os.path.exists(ROUTES):
        print('routes file not found:', ROUTES); return
    clusters = load(CLUSTERS)
    routes = load(ROUTES)
    # map cluster_id -> route list
    route_map = {r['cluster_id']: r['route'] for r in routes.get('routes', [])}

    changed = False
    for c in clusters.get('clusters', []):
        cid = c.get('cluster_id')
        if cid in route_map:
            route = route_map[cid]
            orig = c.get('member_node_indices')
            if orig != route:
                c['original_member_node_indices'] = orig
                c['ordered_member_node_indices'] = route
                c['member_node_indices'] = route
                changed = True

    if changed:
        save(CLUSTERS, clusters)
        print('Updated', CLUSTERS)
    else:
        print('No changes')


if __name__ == '__main__':
    main()
