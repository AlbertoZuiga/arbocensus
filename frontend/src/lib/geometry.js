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
