import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/optimization", () => ({
  createJob: vi.fn(),
  fetchSolution: vi.fn(),
  fetchLatestJob: vi.fn().mockResolvedValue(null),
}));

let mockJob;
vi.mock("@/hooks/useOptimizationJob", () => ({
  useOptimizationJob: (jobId) => ({ data: jobId ? mockJob : undefined }),
}));

import { createJob, fetchSolution, fetchLatestJob } from "@/api/optimization";
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
    mockJob = undefined;
  });

  it("renders the config form and no job card initially", () => {
    renderPanel();
    expect(screen.getByText("Configuración de rutas")).toBeInTheDocument();
    expect(
      screen.queryByText("Trabajo de optimización"),
    ).not.toBeInTheDocument();
  });

  it("restores the dataset's latest job on mount without creating one", async () => {
    fetchLatestJob.mockResolvedValue({ id: "j1", status: "completed" });
    mockJob = { id: "j1", status: "completed", solution_ids: {} };
    renderPanel();

    expect(await screen.findByText("Completado")).toBeInTheDocument();
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
