export function treeKey(tree) {
  return `${tree.source}:${tree.external_id}`;
}

export function isSelectable(tree) {
  return !tree.already_imported;
}

export function toggleTree(selected, tree) {
  if (!isSelectable(tree)) return selected;
  const next = new Set(selected);
  const key = treeKey(tree);
  if (next.has(key)) {
    next.delete(key);
  } else {
    next.add(key);
  }
  return next;
}

export function toggleTrees(selected, trees) {
  const keys = trees.filter(isSelectable).map(treeKey);
  if (keys.length === 0) return selected;
  const next = new Set(selected);
  const allSelected = keys.every((key) => next.has(key));
  for (const key of keys) {
    if (allSelected) {
      next.delete(key);
    } else {
      next.add(key);
    }
  }
  return next;
}

export function addTrees(selected, trees) {
  const next = new Set(selected);
  for (const tree of trees) {
    if (isSelectable(tree)) next.add(treeKey(tree));
  }
  return next;
}

export function removeKey(selected, key) {
  const next = new Set(selected);
  next.delete(key);
  return next;
}

export function selectionPayload(selected) {
  return [...selected].map((key) => {
    const [source, externalId] = key.split(":");
    return { source, external_id: Number(externalId) };
  });
}
