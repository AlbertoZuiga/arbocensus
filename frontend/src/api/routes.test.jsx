import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("./client.js", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}));

import client from "./client.js";
import { assignRoute, fetchRoutes, fetchRoutesGeojson } from "./routes.js";

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

  it("unwraps paginated route results for a solution", async () => {
    client.get.mockResolvedValue({ data: { results: [{ id: "r1" }] } });

    const result = await fetchRoutes("s1");

    expect(client.get).toHaveBeenCalledWith("/routes/", {
      params: { solution_id: "s1" },
    });
    expect(result).toEqual([{ id: "r1" }]);
  });

  it("assigns a surveyor to a route", async () => {
    client.patch.mockResolvedValue({ data: { id: "r1", surveyor: "u1" } });

    await assignRoute("r1", "u1");

    expect(client.patch).toHaveBeenCalledWith("/routes/r1/assign/", {
      surveyor_id: "u1",
    });
  });

  it("sends surveyor_id null to unassign a route", async () => {
    client.patch.mockResolvedValue({ data: { id: "r1", surveyor: null } });

    await assignRoute("r1", null);

    expect(client.patch).toHaveBeenCalledWith("/routes/r1/assign/", {
      surveyor_id: null,
    });
  });
});
