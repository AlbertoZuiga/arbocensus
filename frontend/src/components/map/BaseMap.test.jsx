import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import BaseMap from "./BaseMap.jsx";

vi.mock("leaflet/dist/leaflet.css", () => ({}));
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children, ...props }) => (
    <div data-testid="map" data-zoom={props.zoom}>
      {children}
    </div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  useMap: () => ({ fitBounds: vi.fn() }),
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
});
