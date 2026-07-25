import { describe, it, expect } from "vitest";

import { midpoint, pointInRing, ringFromCorners } from "./geometry.js";

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

describe("ringFromCorners", () => {
  it("builds a four vertex ring from opposite corners", () => {
    expect(ringFromCorners([-33.4, -70.6], [-33.5, -70.7])).toEqual(SQUARE);
  });

  it("normalises the corner order", () => {
    expect(ringFromCorners([-33.5, -70.6], [-33.4, -70.7])).toEqual(SQUARE);
  });

  it("covers the same points as the equivalent bounds", () => {
    const ring = ringFromCorners([-33.5, -70.7], [-33.4, -70.6]);
    expect(pointInRing([-33.45, -70.65], ring)).toBe(true);
    expect(pointInRing([-33.45, -70.55], ring)).toBe(false);
  });
});

describe("midpoint", () => {
  it("averages both coordinates", () => {
    const [lat, lon] = midpoint([-33.5, -70.7], [-33.4, -70.6]);
    expect(lat).toBeCloseTo(-33.45, 9);
    expect(lon).toBeCloseTo(-70.65, 9);
  });
});
