import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from .utils import haversine_m

Coord = Dict[str, Any]
CacheValue = Dict[str, float | str]
CacheKey = Tuple[float, float, float, float, str]


class RoutingCache:
    def __init__(self) -> None:
        self._cache: Dict[CacheKey, CacheValue] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _to_key(origin: Coord, dest: Coord, mode: str) -> CacheKey:
        origin_lat = round(float(origin["lat"]), 7)
        origin_lng = round(float(origin["lng"]), 7)
        dest_lat = round(float(dest["lat"]), 7)
        dest_lng = round(float(dest["lng"]), 7)
        return (origin_lat, origin_lng, dest_lat, dest_lng, str(mode))

    def get(self, origin: Coord, dest: Coord, mode: str) -> Optional[CacheValue]:
        key = self._to_key(origin, dest, mode)
        with self._lock:
            value = self._cache.get(key)
            return dict(value) if value is not None else None

    def put(
        self, origin: Coord, dest: Coord, mode: str, result: Dict[str, Any]
    ) -> None:
        key = self._to_key(origin, dest, mode)
        cache_value: CacheValue = {
            "distance_m": float(result["distance_m"]),
            "duration_s": float(result["duration_s"]),
            "source": str(result["source"]),
        }
        with self._lock:
            self._cache[key] = cache_value

    def save_to_disk(self, path: str | os.PathLike[str]) -> None:
        target = Path(path)
        with self._lock:
            payload = [
                {
                    "origin_lat": key[0],
                    "origin_lng": key[1],
                    "dest_lat": key[2],
                    "dest_lng": key[3],
                    "mode": key[4],
                    "distance_m": value["distance_m"],
                    "duration_s": value["duration_s"],
                    "source": value["source"],
                }
                for key, value in self._cache.items()
            ]

        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True)

    def load_from_disk(self, path: str | os.PathLike[str]) -> None:
        target = Path(path)
        if not target.exists():
            with self._lock:
                self._cache = {}
            return

        with target.open("r", encoding="utf-8") as f:
            raw_payload = json.load(f)

        loaded: Dict[CacheKey, CacheValue] = {}
        if isinstance(raw_payload, list):
            for entry in raw_payload:
                if not isinstance(entry, dict):
                    continue
                try:
                    key: CacheKey = (
                        round(float(entry["origin_lat"]), 7),
                        round(float(entry["origin_lng"]), 7),
                        round(float(entry["dest_lat"]), 7),
                        round(float(entry["dest_lng"]), 7),
                        str(entry["mode"]),
                    )
                    loaded[key] = {
                        "distance_m": float(entry["distance_m"]),
                        "duration_s": float(entry["duration_s"]),
                        "source": str(entry["source"]),
                    }
                except (KeyError, TypeError, ValueError):
                    continue

        with self._lock:
            self._cache = loaded


def haversine_fallback_route_time(
    origin: Coord,
    dest: Coord,
    cache: RoutingCache,
    walking_speed_kmh: float = 4.5,
    multiplier: float = 1.3,
) -> float:
    mode = "walking"
    cached = cache.get(origin, dest, mode)
    if cached is not None:
        return float(cached["duration_s"])

    distance_m = float(
        haversine_m(
            float(origin["lat"]),
            float(origin["lng"]),
            float(dest["lat"]),
            float(dest["lng"]),
        )
    )
    speed_m_per_s = float(walking_speed_kmh) * 1000.0 / 3600.0
    duration_s = (
        (distance_m * float(multiplier)) / speed_m_per_s if speed_m_per_s > 0 else 0.0
    )

    result = {
        "distance_m": distance_m,
        "duration_s": float(duration_s),
        "source": "haversine_fallback",
    }
    cache.put(origin, dest, mode, result)
    return float(duration_s)


def osm_route_time(origin: Coord, dest: Coord, cache: RoutingCache) -> float:
    mode = "walking"
    cached = cache.get(origin, dest, mode)
    if cached is not None:
        return float(cached["duration_s"])

    try:
        lat1 = float(origin["lat"])
        lng1 = float(origin["lng"])
        lat2 = float(dest["lat"])
        lng2 = float(dest["lng"])
    except (KeyError, TypeError, ValueError):
        print("Warning: OSRM failed, using haversine fallback")
        return float(haversine_fallback_route_time(origin, dest, cache))

    if lat1 == lat2 and lng1 == lng2:
        return float(haversine_fallback_route_time(origin, dest, cache))

    base_url = os.getenv("OSRM_BASE_URL")
    root = (base_url or "http://router.project-osrm.org").rstrip("/")
    url = f"{root}/route/v1/foot/{lng1},{lat1};{lng2},{lat2}?overview=false"

    # Keep the public OSRM API usage polite by spacing requests.
    if base_url is None or "router.project-osrm.org" in root:
        time.sleep(0.1)

    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        route = data["routes"][0]
        duration_s = float(route["duration"])
        distance_m = float(route.get("distance", 0.0))
        cache.put(
            origin,
            dest,
            mode,
            {
                "distance_m": distance_m,
                "duration_s": duration_s,
                "source": "osrm",
            },
        )
        return duration_s
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        print("Warning: OSRM failed, using haversine fallback")
        return float(haversine_fallback_route_time(origin, dest, cache))


def google_route_time(
    origin: Coord,
    dest: Coord,
    cache: RoutingCache,
    api_key: Optional[str] = None,
) -> float:
    mode = "walking"
    cached = cache.get(origin, dest, mode)
    if cached is not None:
        return float(cached["duration_s"])

    key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        return float(haversine_fallback_route_time(origin, dest, cache))

    try:
        lat1 = float(origin["lat"])
        lng1 = float(origin["lng"])
        lat2 = float(dest["lat"])
        lng2 = float(dest["lng"])
    except (KeyError, TypeError, ValueError):
        return float(haversine_fallback_route_time(origin, dest, cache))

    if lat1 == lat2 and lng1 == lng2:
        return float(haversine_fallback_route_time(origin, dest, cache))

    params = {
        "origin": f"{lat1},{lng1}",
        "destination": f"{lat2},{lng2}",
        "mode": "walking",
        "key": key,
    }

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/directions/json",
            params=params,
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        leg = data["routes"][0]["legs"][0]
        duration_s = float(leg["duration"]["value"])
        distance_m = float(leg.get("distance", {}).get("value", 0.0))
        cache.put(
            origin,
            dest,
            mode,
            {
                "distance_m": distance_m,
                "duration_s": duration_s,
                "source": "google",
            },
        )
        return duration_s
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return float(haversine_fallback_route_time(origin, dest, cache))


def compute_route_time(
    route: List[Coord],
    f_route_time: Callable[[Coord, Coord, RoutingCache], float],
    cache: RoutingCache,
    t_per_tree: float,
) -> float:
    if not route:
        return 0.0

    total_travel_time = 0.0
    for i in range(len(route) - 1):
        total_travel_time += float(f_route_time(route[i], route[i + 1], cache))

    total_service_time = float(len(route)) * float(t_per_tree)
    return float(total_travel_time + total_service_time)
