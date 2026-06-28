import { describe, it, expect, vi, beforeEach } from "vitest";
import { uploadDataset } from "./datasets.js";
import client from "./client.js";

vi.mock("./client.js", () => ({
  default: { post: vi.fn() },
}));

beforeEach(() => {
  client.post.mockReset();
  client.post.mockResolvedValue({ data: { id: "d1", total_trees: 3 } });
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
