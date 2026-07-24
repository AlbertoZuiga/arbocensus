import math

import numpy as np
from apps.optimization.route_metrics import EARTH_RADIUS_M


def project_local(points):
    # Equirectangular projection around the centroid: over a few km the distortion is
    # far below the scale at which any regime threshold here is read.
    coords = np.asarray(points, dtype=float)
    lat0 = float(coords[:, 0].mean())
    lon0 = float(coords[:, 1].mean())
    x = np.radians(coords[:, 1] - lon0) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    y = np.radians(coords[:, 0] - lat0) * EARTH_RADIUS_M
    return np.column_stack([x, y])


def max_pairwise_distance(projected):
    if len(projected) < 2:
        return 0.0
    diffs = projected[:, None, :] - projected[None, :, :]
    return float(np.sqrt((diffs**2).sum(axis=2)).max())


def principal_extents(projected):
    centered = projected - projected.mean(axis=0)
    _, _, components = np.linalg.svd(centered, full_matrices=False)
    scores = centered @ components.T
    spans = scores.max(axis=0) - scores.min(axis=0)
    # The axis of largest variance is not always the axis of largest range, so the
    # extents are ordered by range: "major" has to be the longer side.
    major, minor = sorted(spans, reverse=True)
    return float(major), float(minor)


def geometry_features(points):
    projected = project_local(points)
    width = float(projected[:, 0].max() - projected[:, 0].min())
    height = float(projected[:, 1].max() - projected[:, 1].min())
    area_km2 = (width / 1000) * (height / 1000)
    major, minor = principal_extents(projected)
    return {
        "n": len(points),
        "bbox_area_km2": area_km2,
        "density_per_km2": len(points) / area_km2,
        "diameter_m": max_pairwise_distance(projected),
        "extent_major_m": major,
        "extent_minor_m": minor,
        "elongation": major / minor,
    }


def minimum_feasible_fleet(msf_by_k, service_total_sec, max_route_time_sec):
    # MSF_k lower-bounds the travel of any k open routes covering every node, so the
    # smallest k whose work fits k*T_max is a lower bound on the fleet: no solution
    # without drops can use fewer routes.
    for k in sorted(msf_by_k):
        if service_total_sec + msf_by_k[k] <= k * max_route_time_sec:
            return k
    raise ValueError("no fleet size in the decomposition table satisfies T_max")


def regime_features(
    msf_by_k, service_total_sec, min_route_time_sec, max_route_time_sec
):
    k_hat = minimum_feasible_fleet(msf_by_k, service_total_sec, max_route_time_sec)
    work_lb = service_total_sec + msf_by_k[k_hat]
    return {
        "k_hat": k_hat,
        "work_lb_sec": work_lb,
        "saturation_hat": work_lb / (k_hat * max_route_time_sec),
        "rho_pad": k_hat * min_route_time_sec / work_lb,
    }
