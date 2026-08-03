import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DatasetDetail from "./DatasetDetail.jsx";
import { fetchDataset, fetchDatasetTrees, updateDataset } from "@/api/datasets.js";
import { fetchJobs, fetchSolutionsForDataset } from "@/api/optimization";
import { fetchRoutesGeojson } from "@/api/routes.js";

vi.mock("@/api/datasets.js", () => ({
  fetchDataset: vi.fn(),
  fetchDatasetTrees: vi.fn(),
  updateDataset: vi.fn(),
}));

vi.mock("@/api/optimization", () => ({
  createJob: vi.fn(),
  fetchSolution: vi.fn(),
  publishSolution: vi.fn(),
  fetchJobs: vi.fn().mockResolvedValue([]),
  fetchSolutionsForDataset: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/api/routes.js", () => ({
  fetchRoutes: vi.fn().mockResolvedValue([]),
  fetchRoutesGeojson: vi.fn().mockResolvedValue({
    type: "FeatureCollection",
    features: [],
  }),
  fetchWorkload: vi.fn().mockResolvedValue([]),
  suggestAssignment: vi.fn().mockResolvedValue({ assignments: [], balance: {} }),
}));

vi.mock("@/api/surveyors.js", () => ({
  fetchSurveyors: vi.fn().mockResolvedValue([]),
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

const baseSolution = {
  strategy: "global",
  config_preset_label: "Equilibrada",
  total_routes: 2,
  total_travel_time_sec: 900,
  balance_score: 0.8,
  balance_below_gate: false,
  dropped_trees: 0,
  degenerate_routes: 0,
  published_at: null,
  recommended: false,
  travel_margin_pct: null,
  technical_tie: false,
};

// API-ordered best-first: s2 ranks ahead of s1.
const SOLUTIONS = [
  { ...baseSolution, id: "s2", job: "j2", recommended: true },
  { ...baseSolution, id: "s1", job: "j1", strategy: "spatial_term" },
];

beforeEach(() => {
  fetchDataset.mockReset();
  fetchDatasetTrees.mockReset();
  fetchJobs.mockReset();
  fetchJobs.mockResolvedValue([]);
  fetchSolutionsForDataset.mockReset();
  fetchSolutionsForDataset.mockResolvedValue([]);
  fetchRoutesGeojson.mockClear();
  updateDataset.mockReset();
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
    const user = userEvent.setup();
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    renderDetail();

    expect(await screen.findByText("Providencia")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "⚙ Optimización" }));
    expect(
      await screen.findByText("Configuración de rutas"),
    ).toBeInTheDocument();
  });

  it("keeps both panels out of the DOM until their button is clicked", async () => {
    const user = userEvent.setup();
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    fetchSolutionsForDataset.mockResolvedValue(SOLUTIONS);
    renderDetail();

    await screen.findByText("Providencia");
    await waitFor(() => expect(fetchRoutesGeojson).toHaveBeenCalledWith("s2"));
    expect(screen.queryByText("Configuración de rutas")).not.toBeInTheDocument();
    expect(screen.queryByText("Asignación de rutas")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "⚙ Optimización" }));
    expect(await screen.findByText("Configuración de rutas")).toBeInTheDocument();
    expect(screen.queryByText("Asignación de rutas")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "👤 Asignación" }));
    expect(await screen.findByText("Asignación de rutas")).toBeInTheDocument();
  });

  it("shows a sweep switcher when a past sweep exists", async () => {
    const user = userEvent.setup();
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    fetchJobs.mockResolvedValue([
      { id: "j2", config: "c2", status: "completed", solution_ids: { global: "s2" }, created_at: "2026-07-28T12:00:00Z" },
      { id: "j1", config: "c1", status: "completed", solution_ids: { global: "s1" }, created_at: "2026-07-27T12:00:00Z" },
    ]);
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "s2", job: "j2", config: "c2", recommended: true },
      { ...baseSolution, id: "s1", job: "j1", config: "c1" },
    ]);
    renderDetail();

    await user.click(await screen.findByRole("button", { name: "⚙ Optimización" }));
    expect(
      await screen.findByRole("combobox", { name: "Corrida" }),
    ).toBeInTheDocument();
  });

  it("hides the sweep switcher when there is only the current sweep", async () => {
    const user = userEvent.setup();
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    fetchJobs.mockResolvedValue([
      { id: "j1", config: "c1", status: "completed", solution_ids: { global: "s1" } },
    ]);
    renderDetail();

    await user.click(await screen.findByRole("button", { name: "⚙ Optimización" }));
    await screen.findByText("Configuración de rutas");
    expect(
      screen.queryByRole("combobox", { name: "Corrida" }),
    ).not.toBeInTheDocument();
  });

  it("renders the best-ranked solution by default", async () => {
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    fetchSolutionsForDataset.mockResolvedValue(SOLUTIONS);
    renderDetail();

    await waitFor(() => expect(fetchRoutesGeojson).toHaveBeenCalledWith("s2"));
    expect(fetchRoutesGeojson).not.toHaveBeenCalledWith("s1");
    expect(
      (await screen.findAllByText(/Equilibrada · Global/)).length,
    ).toBeGreaterThan(0);
  });

  it("defaults to the recommended solution, not to an older sweep that ranks higher", async () => {
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    fetchSolutionsForDataset.mockResolvedValue([
      { ...baseSolution, id: "old", job: "j1", config: "c1", total_travel_time_sec: 10 },
      { ...baseSolution, id: "new", job: "j2", config: "c2", recommended: true },
    ]);
    renderDetail();

    await waitFor(() => expect(fetchRoutesGeojson).toHaveBeenCalledWith("new"));
    expect(fetchRoutesGeojson).not.toHaveBeenCalledWith("old");
  });

  it("switches the map when picking another candidate from the list", async () => {
    const user = userEvent.setup();
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    fetchSolutionsForDataset.mockResolvedValue(SOLUTIONS);
    renderDetail();

    await user.click(await screen.findByRole("button", { name: "⚙ Optimización" }));
    const viewButtons = await screen.findAllByText("Ver en el mapa");
    await user.click(viewButtons[1]);

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

  it("opens the edit dialog pre-filled with the current name and description", async () => {
    const user = userEvent.setup();
    fetchDataset.mockResolvedValue({
      id: "d1",
      name: "Providencia",
      description: "Censo 2025",
    });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    renderDetail();

    await user.click(await screen.findByRole("button", { name: "Editar" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Nombre")).toHaveValue("Providencia");
    expect(screen.getByLabelText("Descripción")).toHaveValue("Censo 2025");
  });

  it("calls updateDataset and closes dialog on save", async () => {
    const user = userEvent.setup();
    fetchDataset.mockResolvedValue({
      id: "d1",
      name: "Providencia",
      description: "",
    });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    updateDataset.mockResolvedValue({ id: "d1", name: "Providencia editado", description: "desc" });
    renderDetail();

    await user.click(await screen.findByRole("button", { name: "Editar" }));

    const nameInput = screen.getByLabelText("Nombre");
    await user.clear(nameInput);
    await user.type(nameInput, "Providencia editado");

    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() =>
      expect(updateDataset).toHaveBeenCalledWith("d1", {
        name: "Providencia editado",
        description: "",
      }),
    );
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });

  it("disables the save button when name is blank", async () => {
    const user = userEvent.setup();
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia", description: "" });
    fetchDatasetTrees.mockResolvedValue({ type: "FeatureCollection", features: [] });
    renderDetail();

    await user.click(await screen.findByRole("button", { name: "Editar" }));
    const nameInput = screen.getByLabelText("Nombre");
    await user.clear(nameInput);

    expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
  });
});
