import { pointInRing, ringArea } from "./geometry.js";

export function treeKey(tree) {
  return `${tree.source}:${tree.external_id}`;
}

export function isSelectable(tree) {
  return !tree.already_imported;
}

export function selectableKeys(trees) {
  return trees.filter(isSelectable).map(treeKey);
}

export function keysInRing(trees, ring) {
  return trees
    .filter(isSelectable)
    .filter((tree) => pointInRing([tree.lat, tree.lon], ring))
    .map(treeKey);
}

// Leaflet gives a click to the last drawn shape that contains it, so nested and
// repeated legacy areas need an explicit order: the campaigns store the same
// polygon several times, and only the first copy is the one the backend hands
// the trees to (it assigns area_id by first containing polygon).
export function areaShapes(areas) {
  const seen = new Set();
  const shapes = [];
  for (const area of areas) {
    if (!area.polygon) continue;
    const ring = area.polygon.coordinates[0].map(([lon, lat]) => [lat, lon]);
    const signature = ring.join(";");
    if (seen.has(signature)) continue;
    seen.add(signature);
    shapes.push({ area, ring });
  }
  return shapes.sort((a, b) => ringArea(b.ring) - ringArea(a.ring));
}

export function resolveSelection({ coveredKeys, manualKeys, excludedKeys }) {
  const selected = new Set(coveredKeys);
  for (const key of manualKeys) selected.add(key);
  for (const key of excludedKeys) selected.delete(key);
  return selected;
}

export function selectKeys({ manualKeys, excludedKeys }, keys) {
  const manual = new Set(manualKeys);
  const excluded = new Set(excludedKeys);
  for (const key of keys) {
    manual.add(key);
    excluded.delete(key);
  }
  return { manualKeys: manual, excludedKeys: excluded };
}

export function deselectKeys({ manualKeys, excludedKeys }, keys, coveredKeys) {
  const manual = new Set(manualKeys);
  const excluded = new Set(excludedKeys);
  for (const key of keys) {
    manual.delete(key);
    // Only a tree a shape still covers needs an exclusion; otherwise dropping it
    // from the manual set already deselects it, and a later shape may claim it.
    if (coveredKeys.has(key)) excluded.add(key);
  }
  return { manualKeys: manual, excludedKeys: excluded };
}

// An exclusion only means "unchecked while a shape covered it". Once no shape
// covers the key it must be dropped, or a later shape would silently skip it.
export function pruneExclusions(state, coveredKeys) {
  const excluded = new Set(
    [...state.excludedKeys].filter((key) => coveredKeys.has(key)),
  );
  if (excluded.size === state.excludedKeys.size) return state;
  return { ...state, excludedKeys: excluded };
}

export function toggleKeys(state, keys, selectedKeys, coveredKeys) {
  if (keys.length === 0) return state;
  const allSelected = keys.every((key) => selectedKeys.has(key));
  return allSelected
    ? deselectKeys(state, keys, coveredKeys)
    : selectKeys(state, keys);
}

export function selectionPayload(selected) {
  return [...selected].map((key) => {
    const [source, externalId] = key.split(":");
    return { source, external_id: Number(externalId) };
  });
}
