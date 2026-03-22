import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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
