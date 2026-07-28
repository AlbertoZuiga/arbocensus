import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("@/api/optimization", () => ({
  createJob: vi.fn(),
  fetchJobs: vi.fn().mockResolvedValue([]),
  fetchSolutionsForDataset: vi.fn().mockResolvedValue([]),
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

  it("renders the config form and no sweep status initially", () => {
    renderPanel();
    expect(screen.getByText("Configuración de rutas")).toBeInTheDocument();
    expect(screen.queryByText(/Optimizando…/)).not.toBeInTheDocument();
  });

  it("shows how many of the sweep's jobs have finished", async () => {
    fetchJobs.mockResolvedValue([
      { id: "j2", config: "c1", status: "running", solution_ids: {} },
      { id: "j1", config: "c1", status: "completed", solution_ids: {} },
    ]);
    renderPanel();

    expect(
      await screen.findByText("Optimizando… 1 de 2 configuraciones listas."),
    ).toBeInTheDocument();
  });

  it("hides the sweep status once every job in it is completed", async () => {
    fetchJobs.mockResolvedValue([
      { id: "j1", config: "c1", status: "completed", solution_ids: {} },
    ]);
    renderPanel();

    await screen.findByText("Configuración de rutas");
    expect(screen.queryByText(/Optimizando…/)).not.toBeInTheDocument();
  });

  it("flags a failed job in the sweep", async () => {
    fetchJobs.mockResolvedValue([
      {
        id: "j1",
        config: "c1",
        status: "failed",
        error_message: "OSRM table request timed out",
        solution_ids: {},
      },
    ]);
    renderPanel();

    expect(
      await screen.findByText(
        "Una de las configuraciones falló; puede faltar una solución.",
      ),
    ).toBeInTheDocument();
  });

  it("submits the config form to create a job", async () => {
    createJob.mockResolvedValue([{ id: "j1", status: "queued" }]);
    const user = userEvent.setup();
    renderPanel();

    await user.click(
      screen.getByRole("button", { name: "Generar y comparar rutas" }),
    );

    expect(createJob).toHaveBeenCalledTimes(1);
  });
});
