import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("./client.js", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

import client from "./client.js";
import {
  createJob,
  fetchJob,
  fetchJobs,
  fetchSolution,
} from "./optimization.js";

describe("optimization api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps camelCase args to a snake_case request body", async () => {
    client.post.mockResolvedValue({ data: { id: "j1" } });

    await createJob({
      dataset: "d1",
      minRouteTimeSec: 7200,
      maxRouteTimeSec: 10800,
      serviceTimeSec: 300,
      strategy: "compare",
    });

    expect(client.post).toHaveBeenCalledWith("/optimization/jobs/", {
      dataset: "d1",
      min_route_time_sec: 7200,
      max_route_time_sec: 10800,
      service_time_sec: 300,
      strategy: "compare",
    });
  });

  it("returns the created job data", async () => {
    client.post.mockResolvedValue({ data: { id: "j1", status: "queued" } });
    const result = await createJob({ dataset: "d1" });
    expect(result).toEqual({ id: "j1", status: "queued" });
  });

  it("fetches a job by id", async () => {
    client.get.mockResolvedValue({ data: { status: "running" } });
    const result = await fetchJob("j1");
    expect(client.get).toHaveBeenCalledWith("/optimization/jobs/j1/");
    expect(result).toEqual({ status: "running" });
  });

  it("fetches all jobs for a dataset as an array", async () => {
    client.get.mockResolvedValue({
      data: { results: [{ id: "j2" }, { id: "j1" }] },
    });
    const result = await fetchJobs("d1");
    expect(client.get).toHaveBeenCalledWith("/optimization/jobs/", {
      params: { dataset: "d1" },
    });
    expect(result).toEqual([{ id: "j2" }, { id: "j1" }]);
  });

  it("returns an empty array when a dataset has no jobs", async () => {
    client.get.mockResolvedValue({ data: {} });
    const result = await fetchJobs("d1");
    expect(result).toEqual([]);
  });

  it("fetches a solution by id", async () => {
    client.get.mockResolvedValue({ data: { balance: 0.9 } });
    const result = await fetchSolution("s1");
    expect(client.get).toHaveBeenCalledWith("/optimization/solutions/s1/");
    expect(result).toEqual({ balance: 0.9 });
  });
});
