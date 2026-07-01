import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("./client.js", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

import client from "./client.js";
import { fetchRoutesGeojson, fetchRoutes } from "./routes.js";

describe("routes api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches the geojson feature collection for a solution", async () => {
    const collection = { type: "FeatureCollection", features: [] };
    client.get.mockResolvedValue({ data: collection });

    const result = await fetchRoutesGeojson("s1");

    expect(client.get).toHaveBeenCalledWith("/routes/geojson/", {
      params: { solution_id: "s1" },
    });
    expect(result).toBe(collection);
  });

  it("unwraps the paginated routes list", async () => {
    client.get.mockResolvedValue({
      data: { count: 1, results: [{ id: "r1" }] },
    });

    const result = await fetchRoutes("s1");

    expect(client.get).toHaveBeenCalledWith("/routes/", {
      params: { solution_id: "s1" },
    });
    expect(result).toEqual([{ id: "r1" }]);
  });

  it("returns a bare routes array unchanged", async () => {
    client.get.mockResolvedValue({ data: [{ id: "r2" }] });
    expect(await fetchRoutes("s1")).toEqual([{ id: "r2" }]);
  });
});
