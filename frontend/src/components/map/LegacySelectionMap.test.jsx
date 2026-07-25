import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen } from "@testing-library/react";

import LegacySelectionMap from "./LegacySelectionMap.jsx";

let mapHandlers = {};

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

function renderMap(props) {
  return render(
    <LegacySelectionMap
      trees={[]}
      areas={[]}
      selectedKeys={new Set()}
      selectionMode="polygon"
      onToggleTree={() => {}}
      onToggleArea={() => {}}
      onBboxSelect={() => {}}
      onPolygonSelect={() => {}}
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
  vi.clearAllMocks();
  mapContainer.style.cursor = "";
});

describe("LegacySelectionMap polygon drawing", () => {
  it("emits the drawn ring as [lat, lon] when the ring is closed", () => {
    const onPolygonSelect = vi.fn();
    renderMap({ onPolygonSelect });

    click(-33.45, -70.65);
    click(-33.45, -70.6);
    click(-33.4, -70.6);
    click(-33.4501, -70.6501);

    expect(onPolygonSelect).toHaveBeenCalledWith([
      [-33.45, -70.65],
      [-33.45, -70.6],
      [-33.4, -70.6],
    ]);
    expect(screen.getByTestId("polygon")).toBeInTheDocument();
  });

  it("adds a vertex instead of closing while the ring has fewer than three", () => {
    const onPolygonSelect = vi.fn();
    renderMap({ onPolygonSelect });

    click(-33.45, -70.65);
    click(-33.4501, -70.6501);

    expect(onPolygonSelect).not.toHaveBeenCalled();
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
        selectionMode={null}
        onToggleTree={() => {}}
        onToggleArea={() => {}}
        onBboxSelect={() => {}}
        onPolygonSelect={() => {}}
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
