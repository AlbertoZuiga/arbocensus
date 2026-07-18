import { describe, it, expect } from "vitest";
import { myRouteRefetchInterval } from "./useMyRoute.js";

function queryWithData(data) {
  return { state: { data } };
}

describe("myRouteRefetchInterval", () => {
  it("polls every 30 seconds while the route list is empty", () => {
    expect(myRouteRefetchInterval(queryWithData([]))).toBe(30_000);
  });

  it("stops polling once routes are assigned", () => {
    expect(myRouteRefetchInterval(queryWithData([{ id: "r1" }]))).toBe(false);
  });

  it("stops polling when there is no data, including error states", () => {
    expect(myRouteRefetchInterval(queryWithData(undefined))).toBe(false);
  });
});
