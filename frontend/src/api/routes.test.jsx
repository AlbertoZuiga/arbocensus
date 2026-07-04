import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("./client.js", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

import client from "./client.js";
import { fetchRoutesGeojson } from "./routes.js";

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
});
