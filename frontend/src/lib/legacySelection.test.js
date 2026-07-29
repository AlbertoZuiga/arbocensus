import { describe, it, expect } from "vitest";
import {
  areaShapes,
  deselectKeys,
  keysInRing,
  pruneExclusions,
  resolveSelection,
  selectKeys,
  selectionPayload,
  toggleKeys,
  treeKey,
  treeKeys,
} from "./legacySelection.js";

const tree = (source, externalId, lat = -33.45, lon = -70.65) => ({
  source,
  external_id: externalId,
  lat,
  lon,
  already_imported: false,
});

const importedTree = (source, externalId, lat = -33.45, lon = -70.65) => ({
  ...tree(source, externalId, lat, lon),
  already_imported: true,
});

const AREA_TREES = [
  tree("legacy_api", 776),
  tree("legacy_api", 777),
  importedTree("legacy_api", 778),
];

const SQUARE = [
  [-33.5, -70.7],
  [-33.5, -70.6],
  [-33.4, -70.6],
  [-33.4, -70.7],
];

const EMPTY = { manualKeys: new Set(), excludedKeys: new Set() };

describe("keysInRing", () => {
  it("includes all trees inside the ring regardless of import state", () => {
    const trees = [
      tree("legacy_api", 776),
      tree("legacy_app", 96905, -33.3, -70.65),
      importedTree("legacy_api", 778),
    ];
    expect(keysInRing(trees, SQUARE)).toEqual([
      "legacy_api:776",
      "legacy_api:778",
    ]);
  });
});

describe("resolveSelection", () => {
  it("unions the shape coverage with the manual clicks", () => {
    const selected = resolveSelection({
      coveredKeys: new Set(["legacy_api:776"]),
      manualKeys: new Set(["legacy_app:96905"]),
      excludedKeys: new Set(),
    });
    expect(selected).toEqual(new Set(["legacy_api:776", "legacy_app:96905"]));
  });

  it("drops the manually excluded keys even if a shape covers them", () => {
    const selected = resolveSelection({
      coveredKeys: new Set(["legacy_api:776", "legacy_api:777"]),
      manualKeys: new Set(),
      excludedKeys: new Set(["legacy_api:776"]),
    });
    expect(selected).toEqual(new Set(["legacy_api:777"]));
  });
});

describe("deselectKeys", () => {
  it("excludes a key a shape still covers", () => {
    const state = deselectKeys(
      EMPTY,
      ["legacy_api:776"],
      new Set(["legacy_api:776"]),
    );
    expect(state.excludedKeys).toEqual(new Set(["legacy_api:776"]));
  });

  it("only drops the manual click when no shape covers the key", () => {
    const manual = selectKeys(EMPTY, ["legacy_app:96905"]);
    const state = deselectKeys(manual, ["legacy_app:96905"], new Set());
    expect(state.manualKeys.size).toBe(0);
    expect(state.excludedKeys.size).toBe(0);
  });
});

describe("pruneExclusions", () => {
  it("drops the exclusions no shape covers any more", () => {
    const state = {
      manualKeys: new Set(),
      excludedKeys: new Set(["legacy_api:776", "legacy_api:777"]),
    };
    const pruned = pruneExclusions(state, new Set(["legacy_api:777"]));
    expect(pruned.excludedKeys).toEqual(new Set(["legacy_api:777"]));
  });

  it("returns the same state when every exclusion is still covered", () => {
    const state = {
      manualKeys: new Set(),
      excludedKeys: new Set(["legacy_api:776"]),
    };
    expect(pruneExclusions(state, new Set(["legacy_api:776"]))).toBe(state);
  });
});

describe("selectKeys", () => {
  it("clears a previous exclusion so a covered tree comes back", () => {
    const excluded = deselectKeys(
      EMPTY,
      ["legacy_api:776"],
      new Set(["legacy_api:776"]),
    );
    const state = selectKeys(excluded, ["legacy_api:776"]);
    expect(state.excludedKeys.size).toBe(0);
    expect(state.manualKeys).toEqual(new Set(["legacy_api:776"]));
  });
});

describe("toggleKeys (area selection)", () => {
  const keys = treeKeys(AREA_TREES);

  it("selects all trees of the area including already imported ones", () => {
    const state = toggleKeys(EMPTY, keys, new Set());
    expect(state.manualKeys).toEqual(
      new Set(["legacy_api:776", "legacy_api:777", "legacy_api:778"]),
    );
  });

  it("deselects the area when all its trees are already selected", () => {
    const selected = new Set([
      "legacy_api:776",
      "legacy_api:777",
      "legacy_api:778",
      "other:1",
    ]);
    const state = toggleKeys(
      { manualKeys: selected, excludedKeys: new Set() },
      keys,
      new Set(),
    );
    expect(state.manualKeys).toEqual(new Set(["other:1"]));
  });

  it("completes a partially selected area instead of clearing it", () => {
    const state = toggleKeys(
      { manualKeys: new Set(["legacy_api:776"]), excludedKeys: new Set() },
      keys,
      new Set(),
    );
    expect(state.manualKeys).toEqual(
      new Set(["legacy_api:776", "legacy_api:777", "legacy_api:778"]),
    );
  });

  it("counts the keys a shape covers as selected", () => {
    const covered = new Set([
      "legacy_api:776",
      "legacy_api:777",
      "legacy_api:778",
    ]);
    const state = toggleKeys(EMPTY, keys, covered);
    expect(resolveSelection({ coveredKeys: covered, ...state })).toEqual(
      new Set(),
    );
  });

  // React re-runs a state updater with the same previous state; a second run
  // that flipped the toggle back would leave the click with no visible effect.
  it("gives the same result when run twice on the same state", () => {
    const first = toggleKeys(EMPTY, keys, new Set());
    expect(toggleKeys(EMPTY, keys, new Set())).toEqual(first);

    const back = toggleKeys(first, keys, new Set());
    expect(toggleKeys(first, keys, new Set())).toEqual(back);
  });
});

describe("areaShapes", () => {
  const polygon = (ring) => ({
    type: "Polygon",
    coordinates: [ring.map(([lat, lon]) => [lon, lat])],
  });
  const BIG = [
    [-33.6, -70.8],
    [-33.6, -70.5],
    [-33.3, -70.5],
    [-33.3, -70.8],
  ];
  const SMALL = [
    [-33.5, -70.7],
    [-33.5, -70.65],
    [-33.45, -70.65],
    [-33.45, -70.7],
  ];

  it("turns the GeoJSON ring into leaflet [lat, lon] pairs", () => {
    const [shape] = areaShapes([{ id: 1, polygon: polygon(SMALL) }]);
    expect(shape.ring).toEqual(SMALL);
  });

  it("skips the areas without a polygon", () => {
    expect(areaShapes([{ id: 1, polygon: null }])).toEqual([]);
  });

  it("keeps only the first area of every repeated polygon", () => {
    const shapes = areaShapes([
      { id: 1, polygon: polygon(SMALL) },
      { id: 2, polygon: polygon(SMALL) },
    ]);
    expect(shapes.map(({ area }) => area.id)).toEqual([1]);
  });

  it("orders the areas from the largest to the smallest", () => {
    const shapes = areaShapes([
      { id: 1, polygon: polygon(SMALL) },
      { id: 2, polygon: polygon(BIG) },
    ]);
    expect(shapes.map(({ area }) => area.id)).toEqual([2, 1]);
  });
});

describe("selectionPayload", () => {
  it("builds [{source, external_id}] with numeric ids", () => {
    const selected = new Set(["legacy_api:776", "legacy_app:96905"]);
    expect(selectionPayload(selected)).toEqual([
      { source: "legacy_api", external_id: 776 },
      { source: "legacy_app", external_id: 96905 },
    ]);
  });
});

describe("treeKey", () => {
  it("joins source and external_id", () => {
    expect(treeKey(tree("legacy_app", 96905))).toBe("legacy_app:96905");
  });
});
