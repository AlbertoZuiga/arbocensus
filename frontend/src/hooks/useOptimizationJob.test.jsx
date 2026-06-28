import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../api/optimization.js", () => ({
  fetchJob: vi.fn(),
}));

import { fetchJob } from "../api/optimization.js";
import { useOptimizationJob, pollInterval } from "./useOptimizationJob.js";

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  function Wrapper({ children }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  }
  return Wrapper;
}

describe("useOptimizationJob", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not run while jobId is falsy", () => {
    const { result } = renderHook(() => useOptimizationJob(undefined), {
      wrapper: makeWrapper(),
    });
    expect(fetchJob).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("fetches the job when a jobId is supplied", async () => {
    fetchJob.mockResolvedValue({ status: "completed", solution_id: "s1" });
    const { result } = renderHook(() => useOptimizationJob("j1"), {
      wrapper: makeWrapper(),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchJob).toHaveBeenCalledWith("j1");
    expect(result.current.data).toEqual({
      status: "completed",
      solution_id: "s1",
    });
  });
});

describe("pollInterval", () => {
  it.each([
    ["queued", 3000],
    ["running", 3000],
  ])("keeps polling while %s", (status, expected) => {
    expect(pollInterval(status)).toBe(expected);
  });

  it.each([["completed"], ["failed"], ["error"]])(
    "stops polling once %s (terminal)",
    (status) => {
      expect(pollInterval(status)).toBe(false);
    }
  );

  it("stops polling when status is undefined", () => {
    expect(pollInterval(undefined)).toBe(false);
  });
});
