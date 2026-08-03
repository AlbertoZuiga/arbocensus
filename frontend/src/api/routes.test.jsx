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

  it("follows pagination and concatenates all pages", async () => {
    client.get
      .mockResolvedValueOnce({
        data: { results: [{ id: "r1" }, { id: "r2" }], next: "http://x/routes/?page=2" },
      })
      .mockResolvedValueOnce({
        data: { results: [{ id: "r3" }], next: null },
      });

    const result = await fetchRoutes("s1");

    expect(client.get).toHaveBeenCalledTimes(2);
    expect(client.get).toHaveBeenNthCalledWith(2, "/routes/", {
      params: { solution_id: "s1", page: 2 },
    });
    expect(result).toEqual([{ id: "r1" }, { id: "r2" }, { id: "r3" }]);
  });

  it("returns non-paginated responses as-is", async () => {
    const plain = [{ id: "r1" }];
    client.get.mockResolvedValue({ data: plain });

    const result = await fetchRoutes();

    expect(client.get).toHaveBeenCalledTimes(1);
    expect(result).toBe(plain);
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
