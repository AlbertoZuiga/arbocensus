import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DatasetDetail from "./DatasetDetail.jsx";
import { fetchDataset, fetchDatasetTrees } from "@/api/datasets.js";

vi.mock("@/api/datasets.js", () => ({
  fetchDataset: vi.fn(),
  fetchDatasetTrees: vi.fn(),
}));

vi.mock("@/components/map/BaseMap.jsx", () => ({
  default: ({ children }) => <div data-testid="map">{children}</div>,
}));

vi.mock("react-leaflet", () => ({
  CircleMarker: ({ center }) => (
    <div data-testid="tree-marker" data-center={JSON.stringify(center)} />
  ),
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

beforeEach(() => {
  fetchDataset.mockReset();
  fetchDatasetTrees.mockReset();
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

  it("shows an error alert when trees fail to load", async () => {
    fetchDataset.mockResolvedValue({ id: "d1", name: "Providencia" });
    fetchDatasetTrees.mockRejectedValue(new Error("nope"));
    renderDetail();

    expect(
      await screen.findByText(/No se pudieron cargar los árboles/),
    ).toBeInTheDocument();
  });
});
