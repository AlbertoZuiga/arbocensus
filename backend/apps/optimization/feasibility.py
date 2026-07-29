import numpy as np
from apps.datasets.models import Tree
from apps.optimization.bounds import symmetric_mst_edges
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.instance_features import minimum_feasible_fleet
from apps.optimization.solver import (
    DROP_PENALTY,
    FIXED_VEHICLE_COST,
    SOFT_LOWER_PENALTY,
)


def _minutes(seconds):
    value = seconds / 60
    if abs(value - round(value)) < 0.05:
        return f"{round(value)}"
    return f"{value:.1f}".replace(".", ",")


def _msf_by_k(mst_edges):
    # msf(k) = sum of the |E| - (k-1) lightest MST edges; one reversed cumulative sum
    # gives every k at once, instead of re-summing a slice per k.
    ascending = np.cumsum(np.array(sorted(mst_edges), dtype=float))
    total_edges = len(mst_edges)
    return {
        k: float(ascending[total_edges - k]) if k <= total_edges else 0.0
        for k in range(1, total_edges + 2)
    }


def check_config(dataset, min_route_time_sec, max_route_time_sec, service_time_sec):
    blocking = []
    warnings = []
    diagnostics = {}

    trees = list(Tree.objects.filter(dataset=dataset, is_active=True).order_by("id"))
    n = len(trees)
    total_service_sec = n * service_time_sec
    diagnostics["n"] = n
    diagnostics["total_service_sec"] = total_service_sec

    if n < 2:
        blocking.append(
            {
                "code": "too_few_trees",
                "detail": (
                    f"Este dataset tiene {n} "
                    f"{'árbol' if n == 1 else 'árboles'} por visitar. "
                    "Se necesitan al menos 2 para armar rutas."
                ),
            }
        )
        diagnostics["matrix_cached"] = False
        return {"blocking": blocking, "warnings": warnings, "diagnostics": diagnostics}

    if service_time_sec > max_route_time_sec:
        blocking.append(
            {
                "code": "service_exceeds_tmax",
                "detail": (
                    f"Censar un árbol toma {_minutes(service_time_sec)} min, más que "
                    f"el tiempo máximo por ruta ({_minutes(max_route_time_sec)} min). "
                    "Ni un solo árbol alcanza a censarse dentro de una ruta: sube el "
                    "tiempo máximo por ruta o baja el tiempo de censo por árbol."
                ),
            }
        )
        diagnostics["matrix_cached"] = False
        return {"blocking": blocking, "warnings": warnings, "diagnostics": diagnostics}

    matrix = OSRMCostMatrixBuilder().get_cached(trees)
    diagnostics["matrix_cached"] = matrix is not None

    if matrix is None:
        # Without matrix, use service-only proxy; travel could fill the floor so not a block.
        if total_service_sec < min_route_time_sec - 100 * n:
            warnings.append(
                {
                    "code": "drop_all_likely",
                    "detail": (
                        f"Censar los {n} árboles del dataset toma unos "
                        f"{_minutes(total_service_sec)} min en total, muy poco frente "
                        f"al tiempo mínimo por ruta ({_minutes(min_route_time_sec)} "
                        "min). Es probable que no se puedan armar rutas y queden "
                        "árboles sin visitar: baja el tiempo mínimo por ruta."
                    ),
                }
            )
        return {"blocking": blocking, "warnings": warnings, "diagnostics": diagnostics}

    # With matrix: W_max = n*s + 2*MST is a valid upper bound on the work of one open
    # route (duplicating MST then shortcutting gives a Hamiltonian path ≤ 2·MST).
    mst_edges = symmetric_mst_edges(matrix)
    mst_total = float(sum(mst_edges))
    work_ub_sec = total_service_sec + 2 * mst_total
    diagnostics["work_ub_sec"] = work_ub_sec

    # Serving every tree costs at least FIXED + LOWER*(T_min - W_max), which beats
    # n*DROP iff W_max < T_min - (n*DROP - FIXED) / LOWER. Serving a subset could still
    # be cheaper than dropping all, so this is a warning and not a block.
    drop_margin_sec = (n * DROP_PENALTY - FIXED_VEHICLE_COST) / SOFT_LOWER_PENALTY
    drop_threshold = min_route_time_sec - drop_margin_sec
    if work_ub_sec < drop_threshold:
        safe_min_route_sec = work_ub_sec + drop_margin_sec
        warnings.append(
            {
                "code": "drop_all_risk",
                "detail": (
                    f"Con estos tiempos es muy probable que no se pueda armar "
                    f"ninguna ruta. Censar los {n} árboles del dataset, caminata "
                    f"incluida, toma como mucho {_minutes(work_ub_sec)} min, y se "
                    f"exige un mínimo de {_minutes(min_route_time_sec)} min por ruta: "
                    "al sistema le conviene dejar árboles sin visitar antes que abrir "
                    "una ruta más corta que el mínimo. Baja el tiempo mínimo por ruta "
                    f"a {int(safe_min_route_sec // 60)} min o menos, o agrega más "
                    "árboles al dataset."
                ),
            }
        )
        return {"blocking": blocking, "warnings": warnings, "diagnostics": diagnostics}

    # Padding-regime warning: T_min not satisfiable with minimum feasible fleet.
    msf_by_k = _msf_by_k(mst_edges)
    try:
        k_hat = minimum_feasible_fleet(msf_by_k, total_service_sec, max_route_time_sec)
        work_lb_sec = total_service_sec + msf_by_k[k_hat]
        rho_pad = k_hat * min_route_time_sec / work_lb_sec
        saturation_hat = work_lb_sec / (k_hat * max_route_time_sec)
        diagnostics["work_lb_sec"] = work_lb_sec
        diagnostics["k_hat"] = k_hat
        diagnostics["rho_pad"] = rho_pad
        diagnostics["saturation_hat"] = saturation_hat

        if rho_pad > 1:
            warnings.append(
                {
                    "code": "padding_regime",
                    "detail": (
                        f"Este dataset necesita al menos {k_hat} "
                        f"{'ruta' if k_hat == 1 else 'rutas'}, y no hay trabajo "
                        f"suficiente para que cada una llegue a los "
                        f"{_minutes(min_route_time_sec)} min exigidos. Las rutas van "
                        "a incluir caminata de relleno y pueden quedar árboles sin "
                        "visitar: considera bajar el tiempo mínimo por ruta."
                    ),
                }
            )
    except ValueError:
        pass

    return {"blocking": blocking, "warnings": warnings, "diagnostics": diagnostics}
