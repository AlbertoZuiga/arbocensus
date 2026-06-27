import { describe, it, expect } from "vitest";
import { haversineMeters, PROXIMITY_THRESHOLD_M } from "./geo.js";

describe("haversineMeters", () => {
  it("is zero for the same point", () => {
    expect(haversineMeters(-33.45, -70.65, -33.45, -70.65)).toBe(0);
  });

  it("matches the length of one degree of latitude", () => {
    const distance = haversineMeters(0, 0, 1, 0);
    expect(distance).toBeGreaterThan(111000);
    expect(distance).toBeLessThan(111400);
  });

  it("is symmetric", () => {
    const a = haversineMeters(-33.45, -70.65, -33.4, -70.6);
    const b = haversineMeters(-33.4, -70.6, -33.45, -70.65);
    expect(a).toBeCloseTo(b, 6);
  });

  it("resolves short urban distances around the proximity threshold", () => {
    const near = haversineMeters(-33.45, -70.65, -33.4498, -70.65);
    const far = haversineMeters(-33.45, -70.65, -33.4495, -70.65);
    expect(near).toBeLessThan(PROXIMITY_THRESHOLD_M);
    expect(far).toBeGreaterThan(PROXIMITY_THRESHOLD_M);
  });
});

describe("PROXIMITY_THRESHOLD_M", () => {
  it("is 30 meters", () => {
    expect(PROXIMITY_THRESHOLD_M).toBe(30);
  });
});
