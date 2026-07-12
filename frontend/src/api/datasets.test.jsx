import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  createDatasetFromLegacySelection,
  deleteDataset,
  fetchDatasets,
  fetchTreeObservations,
  uploadDataset,
} from "./datasets.js";
import client from "./client.js";

vi.mock("./client.js", () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

beforeEach(() => {
  client.get.mockReset();
  client.post.mockReset();
  client.delete.mockReset();
  client.post.mockResolvedValue({ data: { id: "d1", total_trees: 3 } });
  client.delete.mockResolvedValue({ data: undefined });
});

describe("fetchDatasets", () => {
  it("unwraps the paginated DRF response", async () => {
    client.get.mockResolvedValue({
      data: { count: 1, next: null, results: [{ id: "d1" }] },
    });
    expect(await fetchDatasets()).toEqual([{ id: "d1" }]);
  });

  it("returns a bare array unchanged", async () => {
    client.get.mockResolvedValue({ data: [{ id: "d2" }] });
    expect(await fetchDatasets()).toEqual([{ id: "d2" }]);
  });
});

describe("uploadDataset", () => {
  it("sends the file and a name derived from the filename", async () => {
    const file = new File(["lat,lon\n1,2"], "providencia.csv", {
      type: "text/csv",
    });
    await uploadDataset(file);

    const [url, form] = client.post.mock.calls[0];
    expect(url).toBe("/datasets/");
    expect(form.get("file")).toBe(file);
    expect(form.get("name")).toBe("providencia");
  });
});

describe("createDatasetFromLegacySelection", () => {
  it("posts the name and tree refs as JSON", async () => {
    const trees = [{ source: "legacy_api", external_id: 776 }];
    await createDatasetFromLegacySelection({ name: "Selección", trees });

    const [url, body] = client.post.mock.calls[0];
    expect(url).toBe("/datasets/from-legacy-selection/");
    expect(body).toEqual({ name: "Selección", trees });
  });
});

describe("fetchTreeObservations", () => {
  it("fetches the observation list for a tree", async () => {
    client.get.mockResolvedValue({ data: [{ id: "o1" }] });
    expect(await fetchTreeObservations("t1")).toEqual([{ id: "o1" }]);
    expect(client.get).toHaveBeenCalledWith("/datasets/trees/t1/observations/");
  });
});

describe("deleteDataset", () => {
  it("sends a DELETE request to the dataset detail endpoint", async () => {
    await deleteDataset("d1");
    expect(client.delete).toHaveBeenCalledWith("/datasets/d1/");
  });
});
