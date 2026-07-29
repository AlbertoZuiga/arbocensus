import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import LegacySelectionMap from "./LegacySelectionMap.jsx";
import {
  fetchLegacyTreeObservations,
  fetchTreeObservations,
} from "@/api/datasets.js";

let mapHandlers = {};
let dragTarget = { lat: 0, lng: 0 };

const containerPoint = (latlng) => ({
  x: latlng.lng * 1000,
  y: latlng.lat * 1000,
  distanceTo(other) {
    return Math.hypot(this.x - other.x, this.y - other.y);
  },
});

const mapContainer = document.createElement("div");

const fakeMap = {
  dragging: { disable: vi.fn(), enable: vi.fn() },
  doubleClickZoom: { disable: vi.fn(), enable: vi.fn() },
  getContainer: () => mapContainer,
  latLngToContainerPoint: containerPoint,
};

vi.mock("@/api/datasets.js", () => ({
  fetchTreeObservations: vi.fn().mockResolvedValue([]),
  fetchLegacyTreeObservations: vi.fn().mockResolvedValue([]),
}));

vi.mock("react-leaflet", () => ({
  CircleMarker: ({ center, interactive, eventHandlers }) => (
    <button
      data-testid="circle-marker"
      data-center={JSON.stringify(center)}
      disabled={interactive === false}
      onClick={() => eventHandlers?.click?.()}
    />
  ),
  Marker: ({ position, draggable, eventHandlers }) => (
    <button
      data-testid={draggable ? "shape-vertex" : "shape-midpoint"}
      data-position={JSON.stringify(position)}
      onClick={() => eventHandlers.click?.()}
      onContextMenu={() => eventHandlers.contextmenu?.()}
      onMouseUp={() =>
        eventHandlers.dragend?.({ target: { getLatLng: () => dragTarget } })
      }
    />
  ),
  Polygon: ({ positions, eventHandlers, children }) => (
    <div
      data-testid="polygon"
      data-positions={JSON.stringify(positions)}
      data-clickable={eventHandlers?.click ? "yes" : "no"}
      onClick={() => eventHandlers?.click?.()}
    >
      {children}
    </div>
  ),
  Polyline: ({ positions }) => (
    <div data-testid="polyline" data-count={positions.length} />
  ),
  Popup: ({ position, children }) => (
    <div data-testid="popup" data-position={JSON.stringify(position)}>
      {children}
    </div>
  ),
  Rectangle: () => <div data-testid="rectangle" />,
  Tooltip: ({ children }) => <span>{children}</span>,
  useMapEvents: (handlers) => {
    mapHandlers = { ...mapHandlers, ...handlers };
    return fakeMap;
  },
}));

vi.mock("./BaseMap.jsx", () => ({
  default: ({ children }) => <div>{children}</div>,
}));

const SQUARE = [
  [-33.5, -70.7],
  [-33.5, -70.6],
  [-33.4, -70.6],
  [-33.4, -70.7],
];

const TRIANGLE = [
  [-33.5, -70.7],
  [-33.5, -70.6],
  [-33.4, -70.6],
];

const TREES = [
  {
    source: "legacy_api",
    external_id: 776,
    lat: -33.45,
    lon: -70.65,
    already_imported: true,
    tree_id: "t1",
  },
  {
    source: "legacy_app",
    external_id: 96905,
    lat: -33.41,
    lon: -70.53,
    already_imported: false,
    tree_id: null,
  },
];

function mapElement(props) {
  return (
    <LegacySelectionMap
      trees={[]}
      areas={[]}
      selectedKeys={new Set()}
      shapes={[]}
      selectionMode="polygon"
      onToggleTree={() => {}}
      onToggleArea={() => {}}
      onShapeCreate={() => {}}
      onShapeChange={() => {}}
      {...props}
    />
  );
}

function renderMap(props) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const wrap = (element) => (
    <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>
  );
  const view = render(wrap(mapElement(props)));
  return { ...view, rerender: (next) => view.rerender(wrap(mapElement(next))) };
}

const click = (lat, lng) =>
  act(() => {
    mapHandlers.click({ latlng: { lat, lng } });
  });

beforeEach(() => {
  mapHandlers = {};
  dragTarget = { lat: 0, lng: 0 };
  vi.clearAllMocks();
  mapContainer.style.cursor = "";
});

describe("LegacySelectionMap polygon drawing", () => {
  it("emits the drawn ring as [lat, lon] when the ring is closed", () => {
    const onShapeCreate = vi.fn();
    renderMap({ onShapeCreate });

    click(-33.45, -70.65);
    click(-33.45, -70.6);
    click(-33.4, -70.6);
    click(-33.4501, -70.6501);

    expect(onShapeCreate).toHaveBeenCalledWith([
      [-33.45, -70.65],
      [-33.45, -70.6],
      [-33.4, -70.6],
    ]);
  });

  it("adds a vertex instead of closing while the ring has fewer than three", () => {
    const onShapeCreate = vi.fn();
    renderMap({ onShapeCreate });

    click(-33.45, -70.65);
    click(-33.4501, -70.6501);

    expect(onShapeCreate).not.toHaveBeenCalled();
    expect(screen.getByTestId("polyline")).toHaveAttribute("data-count", "2");
  });

  it("drops the drawing when the polygon mode is turned off", () => {
    const { rerender } = renderMap({});

    click(-33.45, -70.65);
    click(-33.45, -70.6);
    expect(screen.getByTestId("polyline")).toBeInTheDocument();

    rerender({ selectionMode: null });

    expect(screen.queryByTestId("polyline")).not.toBeInTheDocument();
    expect(screen.queryByTestId("circle-marker")).not.toBeInTheDocument();
  });

  it("keeps panning available and suppresses the double click zoom", () => {
    const { unmount } = renderMap({});

    expect(fakeMap.dragging.disable).not.toHaveBeenCalled();
    expect(fakeMap.doubleClickZoom.disable).toHaveBeenCalled();
    expect(mapContainer.style.cursor).toBe("crosshair");

    unmount();

    expect(fakeMap.doubleClickZoom.enable).toHaveBeenCalled();
    expect(mapContainer.style.cursor).toBe("");
  });

  it("locks dragging only while the rectangle brush is active", () => {
    renderMap({ selectionMode: "bbox" });

    expect(fakeMap.dragging.disable).toHaveBeenCalled();
  });
});

describe("LegacySelectionMap rectangle drawing", () => {
  const drag = (from, to) => {
    act(() => {
      mapHandlers.mousedown({ latlng: from, originalEvent: { button: 0 } });
    });
    act(() => {
      mapHandlers.mousemove({ latlng: to });
    });
    act(() => {
      window.dispatchEvent(new MouseEvent("mouseup"));
    });
  };

  it("emits the rectangle as a four vertex ring", () => {
    const onShapeCreate = vi.fn();
    renderMap({ selectionMode: "bbox", onShapeCreate });

    drag({ lat: -33.4, lng: -70.6 }, { lat: -33.5, lng: -70.7 });

    expect(onShapeCreate).toHaveBeenCalledWith(SQUARE);
  });

  it("ignores a click that does not drag", () => {
    const onShapeCreate = vi.fn();
    renderMap({ selectionMode: "bbox", onShapeCreate });

    drag({ lat: -33.4, lng: -70.6 }, { lat: -33.4, lng: -70.6 });

    expect(onShapeCreate).not.toHaveBeenCalled();
  });
});

describe("LegacySelectionMap areas", () => {
  const polygonOf = (ring) => ({
    type: "Polygon",
    coordinates: [ring.map(([lat, lon]) => [lon, lat])],
  });
  const INNER = [
    [-33.49, -70.69],
    [-33.49, -70.68],
    [-33.48, -70.68],
    [-33.48, -70.69],
  ];
  const areas = [
    { id: 7, name: "Area 7", campaign: "C1", tree_count: 0, polygon: polygonOf(INNER) },
    { id: 8, name: "Area 8", campaign: "C2", tree_count: 0, polygon: polygonOf(INNER) },
    { id: 9, name: "Area 9", campaign: "C2", tree_count: 0, polygon: polygonOf(SQUARE) },
  ];
  const areaTrees = [
    { source: "legacy_app", external_id: 1, lat: -33.485, lon: -70.685 },
    {
      source: "legacy_app",
      external_id: 2,
      lat: -33.484,
      lon: -70.684,
      already_imported: true,
    },
    { source: "legacy_api", external_id: 3, lat: -33.45, lon: -70.65 },
  ];

  it("draws the enclosing area first so the smallest one takes the click", () => {
    renderMap({ areas, selectionMode: null });

    const positions = screen
      .getAllByTestId("polygon")
      .map((node) => JSON.parse(node.getAttribute("data-positions")));
    expect(positions).toEqual([SQUARE, INNER]);
  });

  it("toggles all trees inside the area including already imported ones", () => {
    const onToggleArea = vi.fn();
    renderMap({ areas, trees: areaTrees, selectionMode: null, onToggleArea });

    fireEvent.click(screen.getAllByTestId("polygon")[1]);

    expect(onToggleArea).toHaveBeenCalledWith(["legacy_app:1", "legacy_app:2"]);
  });

  it("counts the trees inside the ring instead of the legacy tree_count", () => {
    renderMap({ areas, trees: areaTrees, selectionMode: null });

    expect(screen.getByText("C2 — Area 9 (3 árboles)")).toBeInTheDocument();
    expect(screen.getByText("C1 — Area 7 (2 árboles)")).toBeInTheDocument();
  });

  it("ignores the areas while a drawing mode is active", () => {
    renderMap({ areas, selectionMode: "bbox" });

    for (const node of screen.getAllByTestId("polygon")) {
      expect(node).toHaveAttribute("data-clickable", "no");
    }
  });
});

describe("LegacySelectionMap shape editing", () => {
  const shapes = [{ id: 1, ring: SQUARE }];

  it("draws the stored shapes with their handles when no mode is active", () => {
    renderMap({ shapes, selectionMode: null });

    expect(screen.getByTestId("polygon")).toHaveAttribute(
      "data-positions",
      JSON.stringify(SQUARE),
    );
    expect(screen.getAllByTestId("shape-vertex")).toHaveLength(4);
    expect(screen.getAllByTestId("shape-midpoint")).toHaveLength(4);
  });

  it("hides the handles while a drawing mode is active", () => {
    renderMap({ shapes });

    expect(screen.getByTestId("polygon")).toBeInTheDocument();
    expect(screen.queryByTestId("shape-vertex")).not.toBeInTheDocument();
  });

  it("emits the moved vertex only when the drag ends", () => {
    const onShapeChange = vi.fn();
    renderMap({ shapes, selectionMode: null, onShapeChange });

    dragTarget = { lat: -33.55, lng: -70.75 };
    fireEvent.mouseUp(screen.getAllByTestId("shape-vertex")[0]);

    expect(onShapeChange).toHaveBeenCalledWith(1, [
      [-33.55, -70.75],
      [-33.5, -70.6],
      [-33.4, -70.6],
      [-33.4, -70.7],
    ]);
  });

  it("inserts a vertex when a midpoint handle is clicked", () => {
    const onShapeChange = vi.fn();
    renderMap({ shapes, selectionMode: null, onShapeChange });

    fireEvent.click(screen.getAllByTestId("shape-midpoint")[0]);

    const [id, ring] = onShapeChange.mock.calls[0];
    expect(id).toBe(1);
    expect(ring).toHaveLength(5);
    expect(ring[1][0]).toBeCloseTo(-33.5, 9);
    expect(ring[1][1]).toBeCloseTo(-70.65, 9);
    expect(ring[2]).toEqual([-33.5, -70.6]);
  });

  it("removes a vertex on right click", () => {
    const onShapeChange = vi.fn();
    renderMap({ shapes, selectionMode: null, onShapeChange });

    fireEvent.contextMenu(screen.getAllByTestId("shape-vertex")[0]);

    expect(onShapeChange).toHaveBeenCalledWith(1, [
      [-33.5, -70.6],
      [-33.4, -70.6],
      [-33.4, -70.7],
    ]);
  });

  it("keeps at least three vertices", () => {
    const onShapeChange = vi.fn();
    renderMap({
      shapes: [{ id: 2, ring: TRIANGLE }],
      selectionMode: null,
      onShapeChange,
    });

    fireEvent.contextMenu(screen.getAllByTestId("shape-vertex")[0]);

    expect(onShapeChange).not.toHaveBeenCalled();
  });
});

describe("LegacySelectionMap tree history", () => {
  it("opens the history of an already imported tree and notifies the parent", async () => {
    const onToggleTree = vi.fn();
    renderMap({ trees: TREES, selectionMode: null, onToggleTree });

    expect(screen.queryByTestId("popup")).not.toBeInTheDocument();
    expect(fetchTreeObservations).not.toHaveBeenCalled();

    await userEvent.click(screen.getAllByTestId("circle-marker")[0]);

    expect(fetchTreeObservations).toHaveBeenCalledExactlyOnceWith("t1");
    expect(screen.getByTestId("popup")).toHaveAttribute(
      "data-position",
      JSON.stringify([-33.45, -70.65]),
    );
    expect(onToggleTree).toHaveBeenCalledWith(TREES[0]);
  });

  it("opens the legacy history of a tree that was never imported", async () => {
    const onToggleTree = vi.fn();
    renderMap({ trees: TREES, selectionMode: null, onToggleTree });

    await userEvent.click(screen.getAllByTestId("circle-marker")[1]);

    expect(onToggleTree).toHaveBeenCalledWith(TREES[1]);
    expect(fetchTreeObservations).not.toHaveBeenCalled();
    expect(fetchLegacyTreeObservations).toHaveBeenCalledExactlyOnceWith(
      "legacy_app",
      96905,
    );
    expect(screen.getByTestId("popup")).toHaveAttribute(
      "data-position",
      JSON.stringify([-33.41, -70.53]),
    );
  });

  it("reopens the history of the same tree after the popup is closed", async () => {
    renderMap({ trees: TREES, selectionMode: null });

    await userEvent.click(screen.getAllByTestId("circle-marker")[0]);
    expect(screen.getByTestId("popup")).toBeInTheDocument();

    act(() => {
      mapHandlers.popupclose();
    });
    expect(screen.queryByTestId("popup")).not.toBeInTheDocument();

    await userEvent.click(screen.getAllByTestId("circle-marker")[0]);
    expect(screen.getByTestId("popup")).toBeInTheDocument();
  });

  it("keeps the markers inert while a shape is being drawn", () => {
    renderMap({ trees: TREES });

    for (const marker of screen.getAllByTestId("circle-marker")) {
      expect(marker).toBeDisabled();
    }
  });
});
