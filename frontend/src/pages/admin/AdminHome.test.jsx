import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AdminHome from "./AdminHome.jsx";
import { fetchDatasets } from "@/api/datasets.js";
import { fetchCensusProgress } from "@/api/progress.js";
import { fetchJobs } from "@/api/optimization.js";

vi.mock("@/api/datasets.js", () => ({
  fetchDatasets: vi.fn(),
}));

vi.mock("@/api/progress.js", () => ({
  fetchCensusProgress: vi.fn(),
  fetchCensusProgressStops: vi.fn(),
}));

vi.mock("@/api/optimization.js", () => ({
  fetchJobs: vi.fn(),
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AdminHome />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const dataset = {
  id: "d1",
  name: "Providencia",
  total_trees: 120,
  imported_at: "2026-07-01T12:00:00Z",
};

beforeEach(() => {
  fetchDatasets.mockReset();
  fetchCensusProgress.mockReset();
  fetchJobs.mockReset();
});

describe("AdminHome", () => {
  it("shows stats and progress for the most recent dataset", async () => {
    fetchDatasets.mockResolvedValue([dataset]);
    fetchCensusProgress.mockResolvedValue({
      solution: { id: "s1", published_at: "2026-07-02T12:00:00Z" },
      totals: { total: 120, visited: 30, skipped: 10, pending: 80 },
      routes: [],
      surveyors: [],
    });
    fetchJobs.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText("Providencia")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(await screen.findByText("33%")).toBeInTheDocument();
    expect(
      screen.getByText("Este dataset no tiene trabajos de optimización."),
    ).toBeInTheDocument();
  });

  it("shows recent jobs with their status", async () => {
    fetchDatasets.mockResolvedValue([dataset]);
    fetchCensusProgress.mockResolvedValue({ solution: null, totals: null });
    fetchJobs.mockResolvedValue([
      {
        id: "j1",
        status: "completed",
        started_at: "2026-07-03T10:00:00Z",
        created_at: "2026-07-03T09:59:00Z",
        solution_ids: { spatial_term: "s1" },
      },
      {
        id: "j2",
        status: "failed",
        started_at: "2026-07-02T10:00:00Z",
        created_at: "2026-07-02T09:59:00Z",
        solution_ids: {},
      },
    ]);
    renderPage();

    expect(await screen.findByText("Completado")).toBeInTheDocument();
    expect(screen.getByText("Fallido")).toBeInTheDocument();
  });

  it("shows an alert when the dataset has no published solution", async () => {
    fetchDatasets.mockResolvedValue([dataset]);
    fetchCensusProgress.mockResolvedValue({ solution: null, totals: null });
    fetchJobs.mockResolvedValue([]);
    renderPage();

    expect(
      await screen.findByText(/no tiene una solución publicada/),
    ).toBeInTheDocument();
  });

  it("shows an empty message when there are no datasets", async () => {
    fetchDatasets.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/Aún no hay datasets/)).toBeInTheDocument();
  });

  it("shows an error alert when datasets fail to load", async () => {
    fetchDatasets.mockRejectedValue(new Error("boom"));
    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/No se pudieron cargar los datasets/),
      ).toBeInTheDocument(),
    );
  });
});
