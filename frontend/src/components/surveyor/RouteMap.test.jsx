import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import RouteMap from "./RouteMap.jsx";

const mapMock = {
  fitBounds: vi.fn(),
  setView: vi.fn(),
  panTo: vi.fn(),
  getZoom: vi.fn(() => 15),
  on: vi.fn(),
  off: vi.fn(),
};

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
  useMap: () => mapMock,
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

  describe("follow control", () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });

    it("is disabled without a GPS position", () => {
      render(<RouteMap stops={stops} selectedStopId={null} onSelectStop={vi.fn()} />);
      expect(
        screen.getByRole("button", { name: "Dejar de seguir mi ubicación" })
      ).toBeDisabled();
    });

    it("follows by default and centers on the user position", () => {
      render(
        <RouteMap
          stops={stops}
          selectedStopId={null}
          onSelectStop={vi.fn()}
          userPosition={{ lat: -33.44, lon: -70.64 }}
        />
      );
      expect(mapMock.setView).toHaveBeenCalledWith([-33.44, -70.64], 17);
      expect(
        screen.getByRole("button", { name: "Dejar de seguir mi ubicación" })
      ).toHaveAttribute("aria-pressed", "true");
    });

    it("stops following when tapped, then recenters and resumes on the next tap", () => {
      render(
        <RouteMap
          stops={stops}
          selectedStopId={null}
          onSelectStop={vi.fn()}
          userPosition={{ lat: -33.44, lon: -70.64 }}
        />
      );
      const button = screen.getByRole("button", {
        name: "Dejar de seguir mi ubicación",
      });
      fireEvent.click(button);
      expect(
        screen.getByRole("button", { name: "Centrar en mi ubicación" })
      ).toHaveAttribute("aria-pressed", "false");

      mapMock.setView.mockClear();
      fireEvent.click(screen.getByRole("button", { name: "Centrar en mi ubicación" }));
      expect(mapMock.setView).toHaveBeenCalledWith([-33.44, -70.64], 17);
      expect(
        screen.getByRole("button", { name: "Dejar de seguir mi ubicación" })
      ).toHaveAttribute("aria-pressed", "true");
    });

    it("stops following when the user drags the map", () => {
      render(
        <RouteMap
          stops={stops}
          selectedStopId={null}
          onSelectStop={vi.fn()}
          userPosition={{ lat: -33.44, lon: -70.64 }}
        />
      );
      const dragHandler = mapMock.on.mock.calls.find(
        ([event]) => event === "dragstart"
      )[1];
      act(() => dragHandler());
      expect(
        screen.getByRole("button", { name: "Centrar en mi ubicación" })
      ).toHaveAttribute("aria-pressed", "false");
    });
  });
});
