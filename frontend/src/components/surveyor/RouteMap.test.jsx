import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import RouteMap from "./RouteMap.jsx";

vi.mock("leaflet/dist/leaflet.css", () => ({}));
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  TileLayer: () => <div data-testid="tile-layer" />,
  Polyline: (props) => (
    <div data-testid="polyline" data-positions={JSON.stringify(props.positions)} />
  ),
  Marker: (props) => (
    <div
      data-testid="marker"
      data-position={JSON.stringify(props.position)}
      onClick={props.eventHandlers?.click}
    />
  ),
  useMap: () => ({ fitBounds: vi.fn(), setView: vi.fn(), panTo: vi.fn() }),
}));

const stops = [
  { id: "s1", sequence: 1, lat: -33.45, lon: -70.65, visited: true },
  { id: "s2", sequence: 2, lat: -33.46, lon: -70.66, visited: false },
];

describe("RouteMap", () => {
  it("falls back to a straight line between stops when no geometry is available", () => {
    render(<RouteMap stops={stops} selectedStopId={null} onSelectStop={vi.fn()} />);
    const polyline = screen.getByTestId("polyline");
    expect(JSON.parse(polyline.dataset.positions)).toEqual([
      [-33.45, -70.65],
      [-33.46, -70.66],
    ]);
  });

  it("renders the walkable OSRM geometry when provided, inverting [lon, lat] to [lat, lon]", () => {
    const geometry = {
      type: "LineString",
      coordinates: [
        [-70.65, -33.45],
        [-70.655, -33.455],
        [-70.66, -33.46],
      ],
    };
    render(
      <RouteMap
        stops={stops}
        selectedStopId={null}
        onSelectStop={vi.fn()}
        geometry={geometry}
      />
    );
    const polyline = screen.getByTestId("polyline");
    expect(JSON.parse(polyline.dataset.positions)).toEqual([
      [-33.45, -70.65],
      [-33.455, -70.655],
      [-33.46, -70.66],
    ]);
  });

  it("renders a marker per stop", () => {
    render(<RouteMap stops={stops} selectedStopId={null} onSelectStop={vi.fn()} />);
    expect(screen.getAllByTestId("marker")).toHaveLength(2);
  });
});
