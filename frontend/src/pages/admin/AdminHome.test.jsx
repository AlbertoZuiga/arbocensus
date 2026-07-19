import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AdminHome from "./AdminHome.jsx";
import { fetchDatasets } from "@/api/datasets.js";
import { fetchUsers } from "@/api/users.js";
import { fetchCensusProgress } from "@/api/progress.js";
import { fetchJobs } from "@/api/optimization.js";

vi.mock("@/api/datasets.js", () => ({
  fetchDatasets: vi.fn(),
}));

vi.mock("@/api/users.js", () => ({
  fetchUsers: vi.fn(),
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

const olderDataset = {
  id: "d2",
  name: "Ñuñoa",
  total_trees: 80,
  imported_at: "2026-06-01T12:00:00Z",
};

beforeEach(() => {
  fetchDatasets.mockReset();
  fetchUsers.mockReset();
  fetchCensusProgress.mockReset();
  fetchJobs.mockReset();
  fetchUsers.mockResolvedValue([]);
  fetchCensusProgress.mockResolvedValue({ solution: null, totals: null });
  fetchJobs.mockResolvedValue([]);
});

describe("AdminHome", () => {
  it("shows global stats across every dataset", async () => {
    fetchDatasets.mockResolvedValue([dataset, olderDataset]);
    fetchUsers.mockResolvedValue([
      { id: "u1", role: "surveyor", is_active: true },
      { id: "u2", role: "surveyor", is_active: false },
      { id: "u3", role: "admin", is_active: true },
    ]);
    renderPage();

    expect(await screen.findByText("Árboles cargados")).toBeInTheDocument();
    expect(screen.getByText("200")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText("Censadores activos").closest("div"),
      ).toHaveTextContent("1"),
    );
  });

  it("lists datasets with their census progress", async () => {
    fetchDatasets.mockResolvedValue([dataset]);
    fetchCensusProgress.mockResolvedValue({
      solution: { id: "s1", published_at: "2026-07-02T12:00:00Z" },
      totals: { total: 120, visited: 30, skipped: 10, pending: 80 },
      routes: [],
      surveyors: [],
    });
    renderPage();

    expect(await screen.findByText("Providencia")).toBeInTheDocument();
    expect(await screen.findByText("33%")).toBeInTheDocument();
    expect(screen.getByText("Publicado")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver avance" })).toHaveAttribute(
      "href",
      "/admin/datasets/d1/progress",
    );
  });

  it("explains the missing progress when no solution is published", async () => {
    fetchDatasets.mockResolvedValue([dataset]);
    renderPage();

    expect(
      await screen.findByText(/Sin solución publicada/),
    ).toBeInTheDocument();
    expect(screen.getByText("Sin optimizar")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Ver avance" }),
    ).not.toBeInTheDocument();
  });

  it("marks a dataset with a running job as optimizing", async () => {
    fetchDatasets.mockResolvedValue([dataset]);
    fetchJobs.mockResolvedValue([
      {
        id: "j1",
        status: "running",
        created_at: new Date().toISOString(),
        solution_ids: {},
      },
    ]);
    renderPage();

    expect(await screen.findByText("Optimizando")).toBeInTheDocument();
  });

  it("shows only the six most recent datasets and links to the full list", async () => {
    fetchDatasets.mockResolvedValue(
      Array.from({ length: 8 }, (_, index) => ({
        ...dataset,
        id: `d${index}`,
        name: `Comuna ${index}`,
      })),
    );
    renderPage();

    expect(await screen.findByText("Comuna 0")).toBeInTheDocument();
    expect(screen.getByText("Comuna 5")).toBeInTheDocument();
    expect(screen.queryByText("Comuna 6")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Ver todos (8)" }),
    ).toBeInTheDocument();
  });

  it("flags when the surveyor count cannot be loaded", async () => {
    fetchDatasets.mockResolvedValue([dataset]);
    fetchUsers.mockRejectedValue(new Error("boom"));
    renderPage();

    expect(
      await screen.findByText("No se pudieron cargar los usuarios."),
    ).toBeInTheDocument();
  });

  it("shows import actions when there are no datasets", async () => {
    fetchDatasets.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/Aún no hay datasets/)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Importar desde Arbocensus" }),
    ).toBeInTheDocument();
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
