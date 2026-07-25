import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DatasetDetail from "./DatasetDetail.jsx";
import { fetchDataset, fetchDatasetTrees } from "@/api/datasets.js";
import { fetchJobs } from "@/api/optimization";
import { fetchRoutesGeojson } from "@/api/routes.js";

vi.mock("@/api/datasets.js", () => ({
  fetchDataset: vi.fn(),
  fetchDatasetTrees: vi.fn(),
}));

vi.mock("@/api/optimization", () => ({
  createJob: vi.fn(),
  fetchSolution: vi.fn(),
  publishSolution: vi.fn(),
  fetchJobs: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/api/routes.js", () => ({
  fetchRoutes: vi.fn().mockResolvedValue([]),
  fetchRoutesGeojson: vi.fn().mockResolvedValue({
    type: "FeatureCollection",
    features: [],
  }),
}));

vi.mock("@/api/surveyors.js", () => ({
  fetchSurveyors: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/hooks/useOptimizationJob", () => ({
  useOptimizationJob: (jobId) => ({
    data: jobId ? { id: jobId, status: "completed", solution_ids: {} } : undefined,
  }),
}));

vi.mock("@/components/map/BaseMap.jsx", () => ({
  default: ({ children }) => <div data-testid="map">{children}</div>,
}));

vi.mock("react-leaflet", () => ({
  CircleMarker: ({ center }) => (
    <div data-testid="tree-marker" data-center={JSON.stringify(center)} />
  ),
  Popup: ({ children }) => <div>{children}</div>,
  Tooltip: ({ children }) => <span>{children}</span>,
}));

function renderDetail() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/datasets/d1"]}>
        <Routes>
          <Route path="/admin/datasets/:id" element={<DatasetDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const JOBS = [
  {
    id: "j2",
    status: "completed",
    started_at: "2026-07-20T14:00:00Z",
    solution_ids: { global: "s2" },
  },
  {
    id: "j1",
    status: "completed",
    started_at: "2026-07-18T09:00:00Z",
    solution_ids: { global: "s1" },
  },
];

beforeEach(() => {
  fetchDataset.mockReset();
  fetchDatasetTrees.mockReset();
  fetchJobs.mockReset();
  fetchJobs.mockResolvedValue([]);
  fetchRoutesGeojson.mockClear();
});

describe("DatasetDetail", () => {
  it("inverts GeoJSON [lon, lat] to Leaflet [lat, lon] for each tree", async () => {
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({
      type: "FeatureCollection",
      features: [
        {
          id: "t1",
          geometry: { type: "Point", coordinates: [-70.65, -33.45] },
          properties: { species: "Quillay" },
        },
      ],
    });
    renderDetail();

    const marker = await screen.findByTestId("tree-marker");
    expect(marker).toHaveAttribute("data-center", JSON.stringify([-33.45, -70.65]));
  });

  it("renders the dataset name and the optimization config form", async () => {
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    renderDetail();

    expect(await screen.findByText("Providencia")).toBeInTheDocument();
    expect(
      screen.getByText("Configuración de rutas"),
    ).toBeInTheDocument();
  });

  it("renders the optimization job history for the dataset", async () => {
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    fetchJobs.mockResolvedValue([
      { id: "j1", status: "completed", solution_ids: { global: "s1" } },
    ]);
    renderDetail();

    expect(
      await screen.findByText("Historial de trabajos"),
    ).toBeInTheDocument();
  });

  it("renders the most recent optimization by default", async () => {
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    fetchJobs.mockResolvedValue(JOBS);
    renderDetail();

    await waitFor(() => expect(fetchRoutesGeojson).toHaveBeenCalledWith("s2"));
    expect(fetchRoutesGeojson).not.toHaveBeenCalledWith("s1");
  });

  it("switches the map to the solution of an older optimization", async () => {
    const user = userEvent.setup();
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    fetchJobs.mockResolvedValue(JOBS);
    renderDetail();

    await user.click(await screen.findByRole("combobox", { name: "Optimización" }));
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    await user.click(options[1]);

    await waitFor(() => expect(fetchRoutesGeojson).toHaveBeenCalledWith("s1"));
  });

  it("shows an error alert when trees fail to load", async () => {
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockRejectedValue(new Error("nope"));
    renderDetail();

    expect(
      await screen.findByText(/No se pudieron cargar los árboles/),
    ).toBeInTheDocument();
  });
});
