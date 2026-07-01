import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/optimization", () => ({
  createJob: vi.fn(),
  fetchSolution: vi.fn(),
  fetchJobs: vi.fn().mockResolvedValue([]),
}));

let mockJob;
let mockJobs;
vi.mock("@/hooks/useOptimizationJob", () => ({
  useOptimizationJob: (jobId) => ({
    data: jobId ? (mockJobs[jobId] ?? mockJob) : undefined,
  }),
}));

import { createJob, fetchSolution, fetchJobs } from "@/api/optimization";
import OptimizationPanel from "./OptimizationPanel.jsx";

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <OptimizationPanel datasetId="d1" />
    </QueryClientProvider>,
  );
}

describe("OptimizationPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchJobs.mockResolvedValue([]);
    mockJob = undefined;
    mockJobs = {};
  });

  it("renders the config form and no job card initially", () => {
    renderPanel();
    expect(screen.getByText("Configuración de rutas")).toBeInTheDocument();
    expect(
      screen.queryByText("Trabajo de optimización"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Historial de trabajos"),
    ).not.toBeInTheDocument();
  });

  it("restores the dataset's latest job on mount without creating one", async () => {
    fetchJobs.mockResolvedValue([{ id: "j1", status: "completed", solution_ids: {} }]);
    mockJob = { id: "j1", status: "completed", solution_ids: {} };
    renderPanel();

    expect(await screen.findByText("Historial de trabajos")).toBeInTheDocument();
    expect(await screen.findByText("Trabajo de optimización")).toBeInTheDocument();
    expect(createJob).not.toHaveBeenCalled();
  });

  it("shows the job status badge after a job is created", async () => {
    createJob.mockResolvedValue({ id: "j1", status: "queued" });
    mockJob = { id: "j1", status: "running", solution_ids: {} };
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole("button", { name: "Generar rutas" }));

    expect(await screen.findByText("Ejecutando")).toBeInTheDocument();
  });

  it("lists every job in the history and selects an older one to drive the display", async () => {
    fetchJobs.mockResolvedValue([
      {
        id: "j2",
        status: "completed",
        solution_ids: { global: "s1" },
        started_at: "2026-06-30T10:00:00Z",
      },
      {
        id: "j1",
        status: "failed",
        solution_ids: {},
        started_at: "2026-06-29T10:00:00Z",
      },
    ]);
    mockJobs = {
      j2: { id: "j2", status: "completed", solution_ids: { global: "s1" } },
      j1: {
        id: "j1",
        status: "failed",
        solution_ids: {},
        error_message: "boom",
      },
    };
    fetchSolution.mockResolvedValue({
      id: "s1",
      total_routes: 4,
      total_travel_time_sec: 5400,
      balance_score: 0.87,
      sum_max_radius_m: 820,
      interleave_per_route: 0.13,
      worst_pair_iou: 0.02,
    });
    const user = userEvent.setup();
    renderPanel();

    expect(await screen.findByText("Historial de trabajos")).toBeInTheDocument();
    expect(screen.getAllByText("Global").length).toBeGreaterThan(0);

    const olderJob = screen.getByText("Fallido").closest("button");
    await user.click(olderJob);

    expect(await screen.findByText("boom")).toBeInTheDocument();
  });

  it("renders solution summaries for all strategies when the job completes", async () => {
    createJob.mockResolvedValue({ id: "j1", status: "queued" });
    fetchSolution.mockResolvedValue({
      id: "s1",
      total_routes: 4,
      total_travel_time_sec: 5400,
      balance_score: 0.87,
      sum_max_radius_m: 820,
      interleave_total: 5,
      interleave_per_route: 0.13,
      worst_pair_iou: 0.02,
    });
    mockJob = {
      id: "j1",
      status: "completed",
      solution_ids: {
        global: "s1",
        spatial_term: "s2",
        cluster_first: "s3",
      },
    };
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole("button", { name: "Generar rutas" }));

    expect(await screen.findByText("Global")).toBeInTheDocument();
    expect(screen.getByText("Término espacial")).toBeInTheDocument();
    expect(screen.getByText("Clustering primero")).toBeInTheDocument();
    await waitFor(() => expect(fetchSolution).toHaveBeenCalledWith("s1"));
    await waitFor(() => expect(fetchSolution).toHaveBeenCalledWith("s2"));
    await waitFor(() => expect(fetchSolution).toHaveBeenCalledWith("s3"));
  });

  it("shows the error message when the job fails", async () => {
    createJob.mockResolvedValue({ id: "j1", status: "queued" });
    mockJob = {
      id: "j1",
      status: "failed",
      solution_ids: {},
      error_message: "OSRM table request timed out",
    };
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole("button", { name: "Generar rutas" }));

    expect(
      await screen.findByText("OSRM table request timed out"),
    ).toBeInTheDocument();
  });
});
