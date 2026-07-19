import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import CensusProgress from "./CensusProgress.jsx";
import { fetchCensusProgress, fetchCensusProgressStops } from "@/api/progress.js";
import { fetchRoutesGeojson } from "@/api/routes.js";
import { fetchDataset } from "@/api/datasets.js";

vi.mock("@/api/progress.js", () => ({
  fetchCensusProgress: vi.fn(),
  fetchCensusProgressStops: vi.fn(),
}));

vi.mock("@/api/routes.js", () => ({
  fetchRoutesGeojson: vi.fn(),
}));

vi.mock("@/api/datasets.js", () => ({
  fetchDataset: vi.fn(),
}));

vi.mock("@/components/progress/ProgressMap.jsx", () => ({
  default: ({ stops, routeLines, visibleRouteNumbers, onToggleRoutes }) => (
    <div data-testid="progress-map">
      {stops?.features?.length ?? 0}
      <span data-testid="map-filter">
        {visibleRouteNumbers ? [...visibleRouteNumbers].join(",") : "all"}
      </span>
      <span data-testid="map-lines">{routeLines?.features?.length ?? 0}</span>
      <button type="button" onClick={onToggleRoutes}>
        Trazado de rutas
      </button>
    </div>
  ),
}));

const progress = {
  solution: {
    id: "s1",
    strategy: "spatial_term",
    published_at: "2026-07-10T12:00:00Z",
    total_routes: 2,
  },
  totals: { total: 10, visited: 4, skipped: 1, pending: 5 },
  routes: [
    {
      id: "r1",
      route_number: 1,
      surveyor_id: "u1",
      surveyor_name: "ana",
      total: 5,
      visited: 4,
      skipped: 1,
      pending: 0,
    },
    {
      id: "r2",
      route_number: 2,
      surveyor_id: null,
      surveyor_name: null,
      total: 5,
      visited: 0,
      skipped: 0,
      pending: 5,
    },
  ],
  surveyors: [
    {
      surveyor_id: "u1",
      surveyor_name: "ana",
      route_count: 1,
      total: 5,
      visited: 4,
      skipped: 1,
      pending: 0,
    },
    {
      surveyor_id: null,
      surveyor_name: "Sin asignar",
      route_count: 1,
      total: 5,
      visited: 0,
      skipped: 0,
      pending: 5,
    },
  ],
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/datasets/d1/progress"]}>
        <Routes>
          <Route
            path="/admin/datasets/:id/progress"
            element={<CensusProgress />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CensusProgress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchCensusProgressStops.mockResolvedValue({
      type: "FeatureCollection",
      features: [{ id: "stop-1" }],
    });
  });

  it("shows global progress and the per-route breakdown by default", async () => {
    fetchCensusProgress.mockResolvedValue(progress);

    renderPage();

    expect(await screen.findByText("50%")).toBeInTheDocument();
    expect(screen.getByText("5 de 10 árboles")).toBeInTheDocument();

    expect(screen.getByText("Ruta 1")).toBeInTheDocument();
    expect(screen.getByText("Ruta 2")).toBeInTheDocument();
    expect(screen.getByText("100% avance")).toBeInTheDocument();
    expect(screen.getByText("0% avance")).toBeInTheDocument();

    expect(await screen.findByTestId("progress-map")).toHaveTextContent("1");
  });

  it("switches the breakdown to surveyors and clears the filter", async () => {
    fetchCensusProgress.mockResolvedValue(progress);

    renderPage();

    await userEvent.click(await screen.findByText("Ruta 1"));
    expect(screen.getByTestId("map-filter")).toHaveTextContent("1");

    await userEvent.click(screen.getByRole("button", { name: "Censistas" }));

    expect(screen.queryByText("Ruta 1")).not.toBeInTheDocument();
    expect(screen.getByText("ana")).toBeInTheDocument();
    expect(screen.getByText("Sin asignar")).toBeInTheDocument();
    expect(screen.getByTestId("map-filter")).toHaveTextContent("all");
  });

  it("expands a surveyor to show its routes with per-route counters", async () => {
    fetchCensusProgress.mockResolvedValue(progress);

    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Censistas" }),
    );
    expect(screen.queryByText("Ruta 1")).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Ver rutas de ana" }),
    );

    expect(screen.getByText("R1")).toBeInTheDocument();
    expect(screen.queryByText("R2")).not.toBeInTheDocument();
    expect(
      screen.getAllByText("4 censados · 1 omitidos · 0 pendientes"),
    ).toHaveLength(2);
    expect(screen.getByTestId("map-filter")).toHaveTextContent("all");

    await userEvent.click(
      screen.getByRole("button", { name: "Ocultar rutas de ana" }),
    );

    expect(screen.queryByText("R1")).not.toBeInTheDocument();
  });

  it("filters the map to the routes of the selected surveyor", async () => {
    fetchCensusProgress.mockResolvedValue(progress);

    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Censistas" }),
    );
    await userEvent.click(screen.getByText("Sin asignar"));

    expect(screen.getByTestId("map-filter")).toHaveTextContent("2");

    await userEvent.click(screen.getByRole("button", { name: "Ver todas" }));

    expect(screen.getByTestId("map-filter")).toHaveTextContent("all");
  });

  it("filters the map by a single route of an expanded surveyor", async () => {
    fetchCensusProgress.mockResolvedValue({
      ...progress,
      routes: [
        ...progress.routes,
        {
          id: "r3",
          route_number: 3,
          surveyor_id: "u1",
          surveyor_name: "ana",
          total: 5,
          visited: 0,
          skipped: 0,
          pending: 5,
        },
      ],
      surveyors: [
        { ...progress.surveyors[0], route_count: 2 },
        progress.surveyors[1],
      ],
    });

    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Censistas" }),
    );
    await userEvent.click(screen.getByText("ana"));

    expect(screen.getByTestId("map-filter")).toHaveTextContent("1,3");

    await userEvent.click(
      screen.getByRole("button", { name: "Ver rutas de ana" }),
    );
    await userEvent.click(screen.getByRole("button", { name: /^R3/ }));

    expect(screen.getByTestId("map-filter")).toHaveTextContent("3");
    expect(screen.getByRole("button", { name: /^R3/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("ana").closest("button")).toHaveAttribute(
      "aria-pressed",
      "false",
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Ocultar rutas de ana" }),
    );

    expect(screen.getByText("R3 en el mapa")).toBeInTheDocument();
  });

  it("marks the selected surveyor as the one drawn on the map", async () => {
    fetchCensusProgress.mockResolvedValue(progress);

    renderPage();

    await userEvent.click(
      await screen.findByRole("button", { name: "Censistas" }),
    );

    expect(screen.getAllByText("1 ruta")).toHaveLength(2);
    expect(screen.queryByText("En el mapa")).not.toBeInTheDocument();

    await userEvent.click(screen.getByText("ana"));

    expect(screen.getByText("En el mapa")).toBeInTheDocument();
    expect(screen.getAllByText("1 ruta")).toHaveLength(1);
  });

  it("loads route lines only after the map toggle is turned on", async () => {
    fetchCensusProgress.mockResolvedValue(progress);
    fetchRoutesGeojson.mockResolvedValue({
      type: "FeatureCollection",
      features: [{ id: "line-1" }],
    });

    renderPage();

    expect(await screen.findByTestId("map-lines")).toHaveTextContent("0");
    expect(fetchRoutesGeojson).not.toHaveBeenCalled();

    await userEvent.click(
      screen.getByRole("button", { name: "Trazado de rutas" }),
    );

    expect(await screen.findByTestId("map-lines")).toHaveTextContent("1");
    expect(fetchRoutesGeojson).toHaveBeenCalledWith("s1");
  });

  it("asks to publish a solution when there is none", async () => {
    fetchCensusProgress.mockResolvedValue({
      solution: null,
      totals: { total: 0, visited: 0, skipped: 0, pending: 0 },
      routes: [],
      surveyors: [],
    });

    renderPage();

    expect(
      await screen.findByText(/no tiene una solución publicada/i),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("progress-map")).not.toBeInTheDocument();
    expect(fetchCensusProgressStops).not.toHaveBeenCalled();
  });
});
