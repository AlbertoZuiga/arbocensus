export function pointInRing([lat, lon], ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [latI, lonI] = ring[i];
    const [latJ, lonJ] = ring[j];
    const crosses = latI > lat !== latJ > lat;
    if (
      crosses &&
      lon < ((lonJ - lonI) * (lat - latI)) / (latJ - latI) + lonI
    ) {
      inside = !inside;
    }
  }
  return inside;
}

export function ringFromCorners([latA, lonA], [latB, lonB]) {
  const south = Math.min(latA, latB);
  const north = Math.max(latA, latB);
  const west = Math.min(lonA, lonB);
  const east = Math.max(lonA, lonB);
  return [
    [south, west],
    [south, east],
    [north, east],
    [north, west],
  ];
}

export function midpoint([latA, lonA], [latB, lonB]) {
  return [(latA + latB) / 2, (lonA + lonB) / 2];
}
