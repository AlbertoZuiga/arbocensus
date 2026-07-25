import { describe, it, expect } from "vitest";

import { pointInRing } from "./geometry.js";

const SQUARE = [
  [-33.5, -70.7],
  [-33.5, -70.6],
  [-33.4, -70.6],
  [-33.4, -70.7],
];

const L_SHAPE = [
  [-33.5, -70.7],
  [-33.5, -70.6],
  [-33.45, -70.6],
  [-33.45, -70.65],
  [-33.4, -70.65],
  [-33.4, -70.7],
];

describe("pointInRing", () => {
  it("accepts a point inside the ring", () => {
    expect(pointInRing([-33.45, -70.65], SQUARE)).toBe(true);
  });

  it("rejects a point outside the ring", () => {
    expect(pointInRing([-33.45, -70.55], SQUARE)).toBe(false);
    expect(pointInRing([-33.3, -70.65], SQUARE)).toBe(false);
  });

  it("rejects points in the notch of a concave ring", () => {
    expect(pointInRing([-33.42, -70.62], L_SHAPE)).toBe(false);
    expect(pointInRing([-33.42, -70.68], L_SHAPE)).toBe(true);
    expect(pointInRing([-33.48, -70.62], L_SHAPE)).toBe(true);
  });

  it("rejects every point when the ring has no area", () => {
    expect(pointInRing([-33.45, -70.65], [])).toBe(false);
    expect(
      pointInRing([-33.45, -70.65], [
        [-33.5, -70.7],
        [-33.4, -70.6],
      ]),
    ).toBe(false);
  });
});
