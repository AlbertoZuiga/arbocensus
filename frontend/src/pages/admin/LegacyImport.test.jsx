import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LegacyImport from "./LegacyImport.jsx";
import { Toaster } from "@/components/ui/toaster";
import {
  createDatasetFromLegacySelection,
  fetchLegacyAreas,
  fetchLegacyTrees,
} from "@/api/datasets.js";

vi.mock("@/api/datasets.js", () => ({
  fetchLegacyAreas: vi.fn(),
  fetchLegacyTrees: vi.fn(),
  createDatasetFromLegacySelection: vi.fn(),
}));

vi.mock("@/components/map/LegacySelectionMap.jsx", () => ({
  default: ({ trees, areas, onToggleTree, onToggleArea }) => (
    <div>
      {areas.map((area) => (
        <button key={area.id} onClick={() => onToggleArea(area)}>
          area-{area.id}
        </button>
      ))}
      {trees.map((tree) => (
        <button
          key={`${tree.source}:${tree.external_id}`}
          onClick={() => onToggleTree(tree)}
        >
          tree-{tree.external_id}
        </button>
      ))}
    </div>
  ),
}));

const TREES = [
  {
    source: "legacy_api",
    external_id: 776,
    lat: -33.45,
    lon: -70.55,
    species: "Quillaja saponaria",
    area_id: 26,
    already_imported: false,
  },
  {
    source: "legacy_api",
    external_id: 777,
    lat: -33.46,
    lon: -70.56,
    species: "",
    area_id: 26,
    already_imported: false,
  },
  {
    source: "legacy_app",
    external_id: 96905,
    lat: -33.41,
    lon: -70.53,
    species: "",
    area_id: null,
    already_imported: false,
  },
];

const AREAS = [
  {
    id: 26,
    name: "Area 1",
    campaign: "Campaña Semiponti",
    tree_count: 2,
    polygon: { type: "Polygon", coordinates: [[]] },
  },
];

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/datasets/legacy-import"]}>
        <Routes>
          <Route
            path="/admin/datasets/legacy-import"
            element={<LegacyImport />}
          />
          <Route path="/admin/datasets/:id" element={<p>detalle dataset</p>} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  fetchLegacyAreas.mockReset().mockResolvedValue(AREAS);
  fetchLegacyTrees.mockReset().mockResolvedValue(TREES);
  createDatasetFromLegacySelection.mockReset();
});

describe("LegacyImport", () => {
  it("selects all trees of an area when the area is clicked", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("area-26"));

    expect(screen.getByText("2 seleccionados")).toBeInTheDocument();
    expect(screen.getByText(/Quillaja saponaria/)).toBeInTheDocument();
  });

  it("deselects an individual tree after selecting its area", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("area-26"));
    await user.click(screen.getByText("tree-776"));

    expect(screen.getByText("1 seleccionados")).toBeInTheDocument();
    expect(screen.queryByText(/Quillaja saponaria/)).not.toBeInTheDocument();
  });

  it("removes a tree from the sidebar list", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("tree-96905"));
    await user.click(screen.getByLabelText("Quitar #96905"));

    expect(screen.getByText("0 seleccionados")).toBeInTheDocument();
  });

  it("submits the selection as [{source, external_id}] and redirects", async () => {
    const user = userEvent.setup();
    createDatasetFromLegacySelection.mockResolvedValue({
      id: "d1",
      name: "Mi selección",
      total_trees: 2,
    });
    renderPage();

    await user.click(await screen.findByText("area-26"));
    await user.click(screen.getByText("tree-96905"));
    await user.click(screen.getByText("tree-777"));
    await user.click(screen.getByRole("button", { name: /Importar \(2\)/ }));
    await user.type(
      screen.getByLabelText("Nombre del dataset"),
      "Mi selección",
    );
    await user.click(screen.getByRole("button", { name: "Crear dataset" }));

    expect(createDatasetFromLegacySelection.mock.calls[0][0]).toEqual({
      name: "Mi selección",
      trees: [
        { source: "legacy_api", external_id: 776 },
        { source: "legacy_app", external_id: 96905 },
      ],
    });
    expect(await screen.findByText("detalle dataset")).toBeInTheDocument();
    expect(screen.getByText(/creado con 2 árboles/)).toBeInTheDocument();
  });

  it("disables the import button when nothing is selected", async () => {
    renderPage();

    const button = await screen.findByRole("button", { name: "Importar" });
    expect(button).toBeDisabled();
  });
});
