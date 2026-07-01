import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/optimization", () => ({
  createJob: vi.fn(),
  fetchJobs: vi.fn().mockResolvedValue([]),
}));

import { createJob, fetchJobs } from "@/api/optimization";
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
      <MemoryRouter>
        <OptimizationPanel datasetId="d1" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OptimizationPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchJobs.mockResolvedValue([]);
  });

  it("renders the config form and no job cards initially", () => {
    renderPanel();
    expect(screen.getByText("Configuración de rutas")).toBeInTheDocument();
    expect(screen.queryByText("Última optimización")).not.toBeInTheDocument();
  });

  it("restores the dataset's latest job on mount without creating one", async () => {
    fetchJobs.mockResolvedValue([
      {
        id: "j1",
        status: "completed",
        solution_ids: { global: "s1" },
        started_at: "2026-06-30T10:00:00Z",
      },
    ]);
    renderPanel();

    expect(await screen.findByText("Última optimización")).toBeInTheDocument();
    expect(createJob).not.toHaveBeenCalled();
  });

  it("shows the status badge of the latest job", async () => {
    fetchJobs.mockResolvedValue([
      { id: "j1", status: "running", solution_ids: {}, started_at: null },
    ]);
    renderPanel();

    expect((await screen.findAllByText("Ejecutando")).length).toBeGreaterThan(0);
  });

  it("links the latest job to the job detail page", async () => {
    fetchJobs.mockResolvedValue([
      {
        id: "j2",
        status: "completed",
        solution_ids: { global: "s1" },
        started_at: "2026-06-30T10:00:00Z",
      },
    ]);
    renderPanel();

    const detailLink = await screen.findByRole("link", { name: "Ver detalle" });
    expect(detailLink).toHaveAttribute("href", "/admin/datasets/d1/jobs/j2");
  });

  it("shows the error message when the latest job fails", async () => {
    fetchJobs.mockResolvedValue([
      {
        id: "j1",
        status: "failed",
        solution_ids: {},
        error_message: "OSRM table request timed out",
        started_at: "2026-06-30T10:00:00Z",
      },
    ]);
    renderPanel();

    expect(
      await screen.findByText("OSRM table request timed out"),
    ).toBeInTheDocument();
  });

  it("submits the config form to create a job", async () => {
    createJob.mockResolvedValue({ id: "j1", status: "queued" });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole("button", { name: "Generar rutas" }));

    expect(createJob).toHaveBeenCalledTimes(1);
  });
});
