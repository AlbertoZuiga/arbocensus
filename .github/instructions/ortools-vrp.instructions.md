---
applyTo: "backend/apps/optimization/**"
---

# OR-Tools VRP Conventions

## Dummy depot pattern (Open VRP)

The problem is open-route (no fixed depot). We model it with a dummy depot at index 0 with zero cost to/from all real nodes.

```python
def _build_open_matrix(self) -> np.ndarray:
    n = self.node_count + 1  # +1 for dummy depot at row/col 0
    m = np.zeros((n, n))
    m[1:, 1:] = self.matrix  # real costs start at index 1
    return m  # row 0 and col 0 stay 0 → free transit to/from depot
```

When extracting the solution, always subtract 1 to convert OR-Tools node index back to tree index:
```python
node = manager.IndexToNode(index) - 1  # -1 removes dummy depot offset
if node >= 0:  # skip dummy depot (node == -1 after subtraction)
    route.append(node)
```

Never use `node` without subtracting 1. An `IndexError` or negative index is always a missed offset.

## RoutingIndexManager and RoutingModel

```python
manager = pywrapcp.RoutingIndexManager(
    n,             # number of nodes including dummy depot
    max_vehicles,  # upper bound of vehicles (solver will minimize active ones)
    0              # depot node index
)
routing = pywrapcp.RoutingModel(manager)
```

## Time dimension

```python
routing.AddDimension(
    time_callback_index,    # registered transit callback
    0,                      # slack (0 = no waiting time)
    self.max_route_time_sec, # hard upper bound (T_max)
    True,                   # fix_start_cumul_to_zero (required for open routes)
    "Time",
)
```

Parameter order matters — `slack` before `capacity` before `fix_start_cumul_to_zero`.

Soft bounds apply to `end_index` (end of each vehicle's route), not start:
```python
time_dimension = routing.GetDimensionOrDie("Time")
for vehicle_id in range(self.max_vehicles):
    end_index = routing.End(vehicle_id)
    time_dimension.SetCumulVarSoftLowerBound(end_index, self.min_route_time_sec, 10_000)
    time_dimension.SetCumulVarSoftUpperBound(end_index, midpoint, 500)
```

## Fleet minimization

Fixed cost per vehicle forces the solver to minimize active routes:
```python
routing.SetFixedCostOfAllVehicles(100_000)
```

This value must be large relative to the average arc cost × number of nodes. Too small = solver ignores it. Too large = solver refuses to split into multiple routes even when necessary.

## Time callback

Service time is added when LEAVING a node (not arriving). Skip service for the dummy depot:
```python
def time_callback(from_index, to_index):
    from_node = manager.IndexToNode(from_index)
    to_node = manager.IndexToNode(to_index)
    travel = extended_matrix[from_node][to_node]
    service = self.service_time_sec if from_node != 0 else 0  # no service at dummy depot
    return int(travel + service)
```

## OSRM matrix conventions

OSRM `/table/v1/foot` expects coordinates as `lon,lat` (not lat,lon):
```python
coords = ";".join(f"{lon},{lat}" for lat, lon in points)
#                    ^^^ lon first ^^^
```

`points` from GeoDjango is `[(lat, lon), ...]` using `.y` and `.x`:
```python
points = [(t.location.y, t.location.x) for t in trees]  # (lat, lon) tuples
```

Handle unreachable nodes (OSRM returns `null`):
```python
matrix = np.nan_to_num(matrix, nan=9_999_999.0)
```

## Cache key

The cache hash must use sorted IDs to be order-independent:
```python
payload = ",".join(sorted(str(tid) for tid in tree_ids))
return hashlib.sha256(payload.encode()).hexdigest()
```

Without `sorted()`, the same tree set produces different hashes depending on queryset order.

## Infeasibility handling

If `solution is None`, provide a diagnostic error message — never silently fail:
```python
if solution is None:
    total_service = len(self.trees) * self.config.service_time_sec
    raise ValueError(
        f"No feasible solution found. "
        f"{len(self.trees)} trees × {self.config.service_time_sec}s = "
        f"{total_service}s total service. "
        f"Minimum T_max needed: {total_service // self.config.max_vehicles}s"
    )
```
