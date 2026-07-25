import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import LegacySelectionMap from "./LegacySelectionMap.jsx";

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

vi.mock("react-leaflet", () => ({
  CircleMarker: ({ center }) => (
    <div data-testid="vertex" data-center={JSON.stringify(center)} />
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
  Polygon: ({ positions }) => (
    <div data-testid="polygon" data-positions={JSON.stringify(positions)} />
  ),
  Polyline: ({ positions }) => (
    <div data-testid="polyline" data-count={positions.length} />
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

function renderMap(props) {
  return render(
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
    />,
  );
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

    rerender(
      <LegacySelectionMap
        trees={[]}
        areas={[]}
        selectedKeys={new Set()}
        shapes={[]}
        selectionMode={null}
        onToggleTree={() => {}}
        onToggleArea={() => {}}
        onShapeCreate={() => {}}
        onShapeChange={() => {}}
      />,
    );

    expect(screen.queryByTestId("polyline")).not.toBeInTheDocument();
    expect(screen.queryByTestId("vertex")).not.toBeInTheDocument();
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
