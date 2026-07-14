import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import BaseMap from "./BaseMap.jsx";

const map = vi.hoisted(() => ({ fitBounds: vi.fn() }));

vi.mock("leaflet/dist/leaflet.css", () => ({}));
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children, ...props }) => (
    <div data-testid="map" data-zoom={props.zoom}>
      {children}
    </div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  useMap: () => map,
}));

describe("BaseMap", () => {
  it("renders a tile layer and its children", () => {
    render(
      <BaseMap>
        <div>marker</div>
      </BaseMap>,
    );
    expect(screen.getByTestId("tile-layer")).toBeInTheDocument();
    expect(screen.getByText("marker")).toBeInTheDocument();
  });

  it("uses the provided zoom level", () => {
    render(<BaseMap zoom={16} />);
    expect(screen.getByTestId("map")).toHaveAttribute("data-zoom", "16");
  });

  it("refits only when the bounds change", () => {
    map.fitBounds.mockClear();
    const { rerender } = render(<BaseMap bounds={[[-33.45, -70.65]]} />);
    expect(map.fitBounds).toHaveBeenCalledTimes(1);

    rerender(<BaseMap bounds={[[-33.45, -70.65]]} />);
    expect(map.fitBounds).toHaveBeenCalledTimes(1);

    rerender(
      <BaseMap
        bounds={[
          [-33.45, -70.65],
          [-33.46, -70.66],
        ]}
      />,
    );
    expect(map.fitBounds).toHaveBeenCalledTimes(2);
  });
});
