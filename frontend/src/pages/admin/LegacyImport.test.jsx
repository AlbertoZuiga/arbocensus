import { StrictMode } from "react";
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
  partitionLegacySelection,
} from "@/api/datasets.js";

vi.mock("@/api/datasets.js", () => ({
  fetchLegacyAreas: vi.fn(),
  fetchLegacyTrees: vi.fn(),
  createDatasetFromLegacySelection: vi.fn(),
  partitionLegacySelection: vi.fn(),
}));

const POLYGON_RING = [
  [-33.47, -70.58],
  [-33.47, -70.54],
  [-33.44, -70.54],
  [-33.44, -70.58],
];

const OVERLAPPING_RING = [
  [-33.455, -70.555],
  [-33.455, -70.52],
  [-33.4, -70.52],
  [-33.4, -70.555],
];

const SHRUNK_RING = [
  [-33.455, -70.58],
  [-33.455, -70.54],
  [-33.44, -70.54],
  [-33.44, -70.58],
];

// The map resolves the area geometrically and hands over the keys it covers.
const AREA_KEYS = { 26: ["legacy_api:776", "legacy_api:777"] };

vi.mock("@/components/map/LegacySelectionMap.jsx", () => ({
  default: ({
    trees,
    areas,
    shapes,
    selectionMode,
    onToggleTree,
    onToggleArea,
    onShapeCreate,
    onShapeChange,
  }) => (
    <div>
      <span>mode-{selectionMode ?? "none"}</span>
      <button onClick={() => onShapeCreate(POLYGON_RING)}>
        cerrar-poligono
      </button>
      <button onClick={() => onShapeCreate(OVERLAPPING_RING)}>
        cerrar-poligono-2
      </button>
      <button onClick={() => onShapeChange(shapes[0].id, SHRUNK_RING)}>
        mover-vertice
      </button>
      {areas.map((area) => (
        <button key={area.id} onClick={() => onToggleArea(AREA_KEYS[area.id])}>
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

function renderPage({ strict = false } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const tree = (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/admin/datasets/legacy-import"]}>
        <Routes>
          <Route
            path="/admin/datasets/legacy-import"
            element={<LegacyImport />}
          />
          <Route path="/admin/datasets" element={<p>lista datasets</p>} />
          <Route path="/admin/datasets/:id" element={<p>detalle dataset</p>} />
        </Routes>
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
}

beforeEach(() => {
  fetchLegacyAreas.mockReset().mockResolvedValue(AREAS);
  fetchLegacyTrees.mockReset().mockResolvedValue(TREES);
  createDatasetFromLegacySelection.mockReset();
  partitionLegacySelection.mockReset();
});

async function openImportDialog(user) {
  await user.click(await screen.findByText("area-26"));
  await user.click(screen.getByText("tree-96905"));
  await user.click(screen.getByRole("button", { name: /Importar \(3\)/ }));
  await user.type(screen.getByLabelText("Nombre del dataset"), "Mi selección");
}

// A dataset must hold at least one shift of work, so k is only offered on a
// selection big enough to be split into groups of MIN_TREES_PER_DATASET.
const MANY_TREES = Array.from({ length: 100 }, (_, index) => ({
  source: "legacy_api",
  external_id: 1000 + index,
  lat: -33.45,
  lon: -70.57 + index * 0.0001,
  species: "",
  area_id: null,
  already_imported: false,
}));

async function openPartitionDialog(user) {
  fetchLegacyTrees.mockResolvedValue(MANY_TREES);
  renderPage();

  await user.click(await screen.findByText("cerrar-poligono"));
  await user.click(screen.getByRole("button", { name: /Importar \(100\)/ }));
  await user.type(screen.getByLabelText("Nombre del dataset"), "Mi selección");
  await user.click(screen.getByLabelText("Dividir en k grupos por cercanía"));
}

describe("LegacyImport", () => {
  it("selects all trees of an area when the area is clicked", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("area-26"));

    expect(screen.getByText("2 seleccionados")).toBeInTheDocument();
    expect(screen.getByText(/Quillaja saponaria/)).toBeInTheDocument();
  });

  // StrictMode runs the state updater twice; a toggle that read the selection
  // from outside the updater flipped its decision on the second run and the
  // click ended up doing nothing.
  it("selects the area again after deselecting it", async () => {
    const user = userEvent.setup();
    renderPage({ strict: true });

    await user.click(await screen.findByText("area-26"));
    await user.click(screen.getByText("area-26"));
    expect(screen.getByText("0 seleccionados")).toBeInTheDocument();

    await user.click(screen.getByText("area-26"));

    expect(screen.getByText("2 seleccionados")).toBeInTheDocument();
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

  it("selects the trees inside a free-drawn polygon", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      await screen.findByRole("button", { name: /Selección por polígono/ }),
    );
    await user.click(screen.getByText("cerrar-poligono"));

    expect(screen.getByText("2 seleccionados")).toBeInTheDocument();
    expect(screen.getByText(/Quillaja saponaria/)).toBeInTheDocument();
    expect(screen.getByText(/#777/)).toBeInTheDocument();
    expect(screen.queryByText(/#96905/)).not.toBeInTheDocument();
  });

  it("keeps one drawing mode active at a time", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      await screen.findByRole("button", { name: /Selección por polígono/ }),
    );
    expect(screen.getByText("mode-polygon")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /Selección por rectángulo/ }),
    );
    expect(screen.getByText("mode-bbox")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: /Selección por rectángulo/ }),
    );
    expect(screen.getByText("mode-none")).toBeInTheDocument();
  });

  it("leaves the drawing mode once the shape is closed", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      await screen.findByRole("button", { name: /Selección por polígono/ }),
    );
    await user.click(screen.getByText("cerrar-poligono"));

    expect(screen.getByText("mode-none")).toBeInTheDocument();
  });

  it("ignores clicks on individual trees while drawing a polygon", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(
      await screen.findByRole("button", { name: /Selección por polígono/ }),
    );
    await user.click(screen.getByText("tree-96905"));

    expect(screen.getByText("0 seleccionados")).toBeInTheDocument();
  });

  it("lists the drawn shape with its tree count", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("cerrar-poligono"));

    expect(screen.getByText("Polígono 1 — 2 árboles")).toBeInTheDocument();
  });

  it("deselects the trees of a shape when the shape is deleted", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("cerrar-poligono"));
    await user.click(screen.getByLabelText("Borrar polígono 1"));

    expect(screen.getByText("0 seleccionados")).toBeInTheDocument();
    expect(screen.queryByText(/Quillaja saponaria/)).not.toBeInTheDocument();
  });

  it("keeps a tree another shape still covers after deleting one", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("cerrar-poligono"));
    await user.click(screen.getByText("cerrar-poligono-2"));
    expect(screen.getByText("3 seleccionados")).toBeInTheDocument();

    await user.click(screen.getByLabelText("Borrar polígono 1"));

    expect(screen.getByText("2 seleccionados")).toBeInTheDocument();
    expect(screen.getByText(/Quillaja saponaria/)).toBeInTheDocument();
    expect(screen.getByText(/#96905/)).toBeInTheDocument();
    expect(screen.queryByText(/#777/)).not.toBeInTheDocument();
  });

  it("recomputes the selection when a vertex moves", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("cerrar-poligono"));
    await user.click(screen.getByText("mover-vertice"));

    expect(screen.getByText("1 seleccionados")).toBeInTheDocument();
    expect(screen.getByText("Polígono 1 — 1 árboles")).toBeInTheDocument();
    expect(screen.queryByText(/#777/)).not.toBeInTheDocument();
  });

  it("keeps a manually deselected tree out of the shape selection", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("cerrar-poligono"));
    await user.click(screen.getByText("tree-776"));
    expect(screen.getByText("1 seleccionados")).toBeInTheDocument();

    await user.click(screen.getByText("cerrar-poligono-2"));

    expect(screen.getByText("2 seleccionados")).toBeInTheDocument();
    expect(screen.queryByText(/Quillaja saponaria/)).not.toBeInTheDocument();
  });

  it("forgets a deselection once no shape covers the tree", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("cerrar-poligono"));
    await user.click(screen.getByText("tree-776"));
    await user.click(screen.getByLabelText("Borrar polígono 1"));
    await user.click(screen.getByText("cerrar-poligono"));

    expect(screen.getByText("2 seleccionados")).toBeInTheDocument();
    expect(screen.getByText(/Quillaja saponaria/)).toBeInTheDocument();
  });

  it("clears the shapes, the selection and the drawing mode", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByText("cerrar-poligono"));
    await user.click(
      screen.getByRole("button", { name: /Selección por polígono/ }),
    );
    await user.click(screen.getByRole("button", { name: "Limpiar" }));

    expect(screen.getByText("0 seleccionados")).toBeInTheDocument();
    expect(screen.queryByText(/Polígono 1/)).not.toBeInTheDocument();
    expect(screen.getByText("mode-none")).toBeInTheDocument();
  });

  it("partitions the selection into k datasets", async () => {
    const user = userEvent.setup();
    partitionLegacySelection.mockResolvedValue([
      { id: "d1", name: "Mi selección — 1", total_trees: 60 },
      { id: "d2", name: "Mi selección — 2", total_trees: 40 },
    ]);

    await openPartitionDialog(user);
    await user.clear(screen.getByLabelText("Cantidad de grupos (k)"));
    await user.type(screen.getByLabelText("Cantidad de grupos (k)"), "2");
    await user.click(screen.getByRole("button", { name: "Crear datasets" }));

    expect(partitionLegacySelection.mock.calls[0][0]).toEqual({
      name: "Mi selección",
      k: 2,
      trees: MANY_TREES.map(({ source, external_id }) => ({
        source,
        external_id,
      })),
    });
    expect(await screen.findByText("lista datasets")).toBeInTheDocument();
    expect(
      screen.getByText("2 datasets creados con 100 árboles en total"),
    ).toBeInTheDocument();
  });

  it("shows the resulting group size", async () => {
    const user = userEvent.setup();

    await openPartitionDialog(user);

    expect(screen.getByText("≈ 50 árboles por grupo.")).toBeInTheDocument();
  });

  it("blocks a k that leaves the datasets below one shift of work", async () => {
    const user = userEvent.setup();

    await openPartitionDialog(user);
    await user.clear(screen.getByLabelText("Cantidad de grupos (k)"));
    await user.type(screen.getByLabelText("Cantidad de grupos (k)"), "3");

    expect(
      screen.getByRole("button", { name: "Crear datasets" }),
    ).toBeDisabled();
    expect(partitionLegacySelection).not.toHaveBeenCalled();
  });

  it("offers no split when the selection is smaller than two datasets", async () => {
    const user = userEvent.setup();
    renderPage();

    await openImportDialog(user);

    expect(
      screen.getByLabelText("Dividir en k grupos por cercanía"),
    ).toBeDisabled();
    expect(screen.getByText(/al menos 80 árboles/)).toBeInTheDocument();
  });

  it("reopens the dialog on a single dataset after the split was chosen", async () => {
    const user = userEvent.setup();

    await openPartitionDialog(user);
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    await user.click(screen.getByRole("button", { name: /Importar \(100\)/ }));

    expect(screen.getByLabelText("Un solo dataset")).toBeChecked();
    expect(screen.queryByLabelText("Cantidad de grupos (k)")).toBeNull();
  });

  it("disables the import button when nothing is selected", async () => {
    renderPage();

    const button = await screen.findByRole("button", { name: "Importar" });
    expect(button).toBeDisabled();
  });
});
