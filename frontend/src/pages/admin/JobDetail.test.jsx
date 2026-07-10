import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/optimization", () => ({
  fetchSolution: vi.fn(),
}));

let mockJob;
vi.mock("@/hooks/useOptimizationJob", () => ({
  useOptimizationJob: () => ({ data: mockJob, isLoading: false, error: null }),
}));

import { fetchSolution } from "@/api/optimization";
import JobDetail from "./JobDetail.jsx";

const SOLUTIONS = {
  s1: {
    id: "s1",
    total_routes: 2,
    total_travel_time_sec: 11160,
    total_service_time_sec: 1200,
    total_time_sec: 12360,
    balance_score: 0.96,
    sum_max_radius_m: 3675,
    interleave_per_route: 0.0,
    worst_pair_iou: 0.0,
  },
  s2: {
    id: "s2",
    total_routes: 2,
    total_travel_time_sec: 11160,
    total_service_time_sec: 1200,
    total_time_sec: 12360,
    balance_score: 0.96,
    sum_max_radius_m: 3675,
    interleave_per_route: 0.0,
    worst_pair_iou: 0.0,
  },
  s3: {
    id: "s3",
    total_routes: 5,
    total_travel_time_sec: 11700,
    total_service_time_sec: 3000,
    total_time_sec: 14700,
    balance_score: 0.14,
    sum_max_radius_m: 3590,
    interleave_per_route: 0.0,
    worst_pair_iou: 0.0,
  },
};

function renderJobDetail() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/admin/datasets/d1/jobs/j1"]}>
        <Routes>
          <Route
            path="/admin/datasets/:id/jobs/:jobId"
            element={<JobDetail />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("JobDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchSolution.mockImplementation((id) => Promise.resolve(SOLUTIONS[id]));
    mockJob = {
      id: "j1",
      status: "completed",
      started_at: "2026-06-30T10:00:00Z",
      solution_ids: { global: "s1", spatial_term: "s2", cluster_first: "s3" },
    };
  });

  it("renders one column per strategy", async () => {
    renderJobDetail();
    expect(await screen.findByText("Global")).toBeInTheDocument();
    expect(screen.getByText("Término espacial")).toBeInTheDocument();
    expect(screen.getByText("Clustering primero")).toBeInTheDocument();
  });

  it("highlights the best value per metric", async () => {
    renderJobDetail();
    await screen.findByText("3590 m");

    const bestBalance = screen.getAllByText("0.96");
    expect(bestBalance).toHaveLength(2);
    bestBalance.forEach((cell) =>
      expect(cell.className).toContain("text-primary"),
    );

    const worstBalance = screen.getByText("0.14");
    expect(worstBalance.className).not.toContain("text-primary");

    const bestRadius = screen.getByText("3590 m");
    expect(bestRadius.className).toContain("text-primary");
  });

  it("warns when trees were dropped as unreachable", async () => {
    mockJob = {
      ...mockJob,
      metrics: { dropped_trees: ["t1", "t2", "t3"] },
    };
    renderJobDetail();
    expect(
      await screen.findByText(/3 árboles quedaron fuera de las rutas/),
    ).toBeInTheDocument();
  });

  it("does not warn when no trees were dropped", async () => {
    mockJob = { ...mockJob, metrics: { dropped_trees: [] } };
    renderJobDetail();
    await screen.findByText("Global");
    expect(
      screen.queryByText(/quedaron fuera de las rutas/),
    ).not.toBeInTheDocument();
  });

  it("does not highlight when all strategies tie", async () => {
    renderJobDetail();
    await screen.findByText("3590 m");

    const iouCells = screen.getAllByText("0.00");
    expect(iouCells.length).toBeGreaterThan(0);
    iouCells.forEach((cell) =>
      expect(cell.className).not.toContain("text-primary"),
    );
  });
});
