import { describe, it, expect } from "vitest";
import {
  deselectKeys,
  keysInRing,
  pruneExclusions,
  resolveSelection,
  selectKeys,
  selectableKeys,
  selectionPayload,
  toggleKeys,
  treeKey,
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
  it("keeps only the selectable trees inside the ring", () => {
    const trees = [
      tree("legacy_api", 776),
      tree("legacy_app", 96905, -33.3, -70.65),
      importedTree("legacy_api", 778),
    ];
    expect(keysInRing(trees, SQUARE)).toEqual(["legacy_api:776"]);
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
    const state = deselectKeys(EMPTY, ["legacy_api:776"], new Set(["legacy_api:776"]));
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
  const keys = selectableKeys(AREA_TREES);

  it("selects every selectable tree of the area", () => {
    const state = toggleKeys(EMPTY, keys, new Set(), new Set());
    expect(state.manualKeys).toEqual(
      new Set(["legacy_api:776", "legacy_api:777"]),
    );
  });

  it("skips already imported trees", () => {
    expect(keys).not.toContain("legacy_api:778");
  });

  it("deselects the area when all its trees are already selected", () => {
    const selected = new Set(["legacy_api:776", "legacy_api:777", "other:1"]);
    const state = toggleKeys(
      { manualKeys: selected, excludedKeys: new Set() },
      keys,
      selected,
      new Set(),
    );
    expect(state.manualKeys).toEqual(new Set(["other:1"]));
  });

  it("completes a partially selected area instead of clearing it", () => {
    const selected = new Set(["legacy_api:776"]);
    const state = toggleKeys(
      { manualKeys: selected, excludedKeys: new Set() },
      keys,
      selected,
      new Set(),
    );
    expect(state.manualKeys).toEqual(
      new Set(["legacy_api:776", "legacy_api:777"]),
    );
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
