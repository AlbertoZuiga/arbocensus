import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ProgressMap from "./ProgressMap.jsx";
import { STATUS_COLORS } from "@/lib/progress.js";

vi.mock("@/components/map/BaseMap.jsx", () => ({
  default: ({ children, bounds, fitKey }) => (
    <div
      data-testid="map"
      data-bounds={JSON.stringify(bounds)}
      data-fit-key={fitKey}
    >
      {children}
    </div>
  ),
}));

vi.mock("react-leaflet", () => ({
  CircleMarker: ({ center, pathOptions }) => (
    <div
      data-testid="stop-marker"
      data-center={JSON.stringify(center)}
      data-color={pathOptions.fillColor}
    />
  ),
  Polyline: ({ positions }) => (
    <div data-testid="route-line" data-positions={JSON.stringify(positions)} />
  ),
  Popup: ({ children }) => <div>{children}</div>,
}));

const stops = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      id: "stop-1",
      geometry: { type: "Point", coordinates: [-70.65, -33.45] },
      properties: {
        route_number: 1,
        sequence: 0,
        status: "visited",
        surveyor_name: "ana",
      },
    },
    {
      type: "Feature",
      id: "stop-2",
      geometry: { type: "Point", coordinates: [-70.66, -33.46] },
      properties: {
        route_number: 1,
        sequence: 1,
        status: "pending",
        surveyor_name: "ana",
      },
    },
    {
      type: "Feature",
      id: "stop-3",
      geometry: { type: "Point", coordinates: [-70.67, -33.47] },
      properties: {
        route_number: 2,
        sequence: 0,
        status: "pending",
        surveyor_name: null,
      },
    },
  ],
};

const routeLines = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [-70.65, -33.45],
          [-70.66, -33.46],
        ],
      },
      properties: { route_number: 1, stops: [] },
    },
    {
      type: "Feature",
      geometry: {
        type: "LineString",
        coordinates: [
          [-70.67, -33.47],
          [-70.68, -33.48],
        ],
      },
      properties: { route_number: 2, stops: [] },
    },
  ],
};

describe("ProgressMap", () => {
  it("renders stops as [lat, lon] colored by status", () => {
    render(<ProgressMap stops={stops} />);

    const markers = screen.getAllByTestId("stop-marker");
    expect(markers).toHaveLength(3);
    expect(markers[0].dataset.center).toBe(JSON.stringify([-33.45, -70.65]));
    expect(markers[0].dataset.color).toBe(STATUS_COLORS.visited);
    expect(markers[1].dataset.color).toBe(STATUS_COLORS.pending);
  });

  it("hides a status when its legend entry is toggled off", async () => {
    render(<ProgressMap stops={stops} />);

    await userEvent.click(screen.getByRole("button", { name: /Pendientes/ }));

    const markers = screen.getAllByTestId("stop-marker");
    expect(markers).toHaveLength(1);
    expect(markers[0].dataset.color).toBe(STATUS_COLORS.visited);
  });

  it("draws route lines as [lat, lon] only when they are shown", () => {
    const { rerender } = render(
      <ProgressMap stops={stops} routeLines={routeLines} />,
    );

    expect(screen.queryAllByTestId("route-line")).toHaveLength(0);

    rerender(<ProgressMap stops={stops} routeLines={routeLines} showRoutes />);

    const lines = screen.getAllByTestId("route-line");
    expect(lines).toHaveLength(2);
    expect(lines[0].dataset.positions).toBe(
      JSON.stringify([
        [-33.45, -70.65],
        [-33.46, -70.66],
      ]),
    );
  });

  it("keeps only the stops and lines of the visible routes", () => {
    render(
      <ProgressMap
        stops={stops}
        routeLines={routeLines}
        showRoutes
        visibleRouteNumbers={new Set([2])}
      />,
    );

    const markers = screen.getAllByTestId("stop-marker");
    expect(markers).toHaveLength(1);
    expect(markers[0].dataset.center).toBe(JSON.stringify([-33.47, -70.67]));

    const lines = screen.getAllByTestId("route-line");
    expect(lines).toHaveLength(1);
    expect(lines[0].dataset.positions).toBe(
      JSON.stringify([
        [-33.47, -70.67],
        [-33.48, -70.68],
      ]),
    );
  });

  it("bounds the map to the visible routes and keys the fit on the selection", () => {
    render(
      <ProgressMap
        stops={stops}
        visibleRouteNumbers={new Set([2])}
        selectedKey="r2"
      />,
    );

    const map = screen.getByTestId("map");
    expect(map.dataset.bounds).toBe(JSON.stringify([[-33.47, -70.67]]));
    expect(map.dataset.fitKey).toBe("r2");
  });

  it("drops stops without usable coordinates so they cannot break the fit", () => {
    render(
      <ProgressMap
        stops={{
          type: "FeatureCollection",
          features: [
            ...stops.features,
            {
              type: "Feature",
              id: "stop-broken",
              geometry: null,
              properties: { route_number: 1, sequence: 2, status: "pending" },
            },
          ],
        }}
      />,
    );

    expect(screen.getAllByTestId("stop-marker")).toHaveLength(3);
  });
});
