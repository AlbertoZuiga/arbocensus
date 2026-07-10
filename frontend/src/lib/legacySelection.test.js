import { describe, it, expect } from "vitest";
import {
  addTrees,
  removeKey,
  selectionPayload,
  toggleTree,
  toggleTrees,
  treeKey,
} from "./legacySelection.js";

const tree = (source, externalId, alreadyImported = false) => ({
  source,
  external_id: externalId,
  already_imported: alreadyImported,
});

const AREA_TREES = [
  tree("legacy_api", 776),
  tree("legacy_api", 777),
  tree("legacy_api", 778, true),
];

describe("toggleTrees (area selection)", () => {
  it("selects every selectable tree of the area", () => {
    const next = toggleTrees(new Set(), AREA_TREES);
    expect(next).toEqual(new Set(["legacy_api:776", "legacy_api:777"]));
  });

  it("skips already imported trees", () => {
    const next = toggleTrees(new Set(), AREA_TREES);
    expect(next.has("legacy_api:778")).toBe(false);
  });

  it("deselects the area when all its trees are already selected", () => {
    const selected = new Set(["legacy_api:776", "legacy_api:777", "other:1"]);
    const next = toggleTrees(selected, AREA_TREES);
    expect(next).toEqual(new Set(["other:1"]));
  });

  it("completes a partially selected area instead of clearing it", () => {
    const next = toggleTrees(new Set(["legacy_api:776"]), AREA_TREES);
    expect(next).toEqual(new Set(["legacy_api:776", "legacy_api:777"]));
  });
});

describe("addTrees (bbox selection)", () => {
  it("adds contained trees without duplicating existing keys", () => {
    const selected = new Set(["legacy_api:776"]);
    const next = addTrees(selected, [
      tree("legacy_api", 776),
      tree("legacy_app", 96905),
    ]);
    expect(next).toEqual(new Set(["legacy_api:776", "legacy_app:96905"]));
  });

  it("never adds already imported trees", () => {
    const next = addTrees(new Set(), [tree("legacy_app", 5, true)]);
    expect(next.size).toBe(0);
  });
});

describe("toggleTree", () => {
  it("deselects an individual tree after an area selection", () => {
    const afterArea = toggleTrees(new Set(), AREA_TREES);
    const next = toggleTree(afterArea, tree("legacy_api", 776));
    expect(next).toEqual(new Set(["legacy_api:777"]));
  });

  it("ignores already imported trees", () => {
    const next = toggleTree(new Set(), tree("legacy_api", 778, true));
    expect(next.size).toBe(0);
  });
});

describe("removeKey", () => {
  it("removes a single key without mutating the original set", () => {
    const selected = new Set(["legacy_api:776", "legacy_app:96905"]);
    const next = removeKey(selected, "legacy_api:776");
    expect(next).toEqual(new Set(["legacy_app:96905"]));
    expect(selected.size).toBe(2);
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
