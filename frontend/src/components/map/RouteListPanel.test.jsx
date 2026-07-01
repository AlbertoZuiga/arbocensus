import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import RouteListPanel from "./RouteListPanel.jsx";

const routes = [
  { routeNumber: 1, totalTrees: 12, travelTimeSec: 5400, color: "#2563eb" },
  { routeNumber: 2, totalTrees: 8, travelTimeSec: 120, color: "#dc2626" },
];

describe("RouteListPanel", () => {
  it("lists each route with tree count and formatted travel time", () => {
    render(
      <RouteListPanel routes={routes} selectedRoute={null} onSelectRoute={vi.fn()} />,
    );
    expect(screen.getByText("Ruta 1")).toBeInTheDocument();
    expect(screen.getByText("12 árboles · 1 h 30 min")).toBeInTheDocument();
    expect(screen.getByText("8 árboles · 2 min")).toBeInTheDocument();
  });

  it("selects a route on hover and clears it on leave", () => {
    const onSelectRoute = vi.fn();
    render(
      <RouteListPanel routes={routes} selectedRoute={null} onSelectRoute={onSelectRoute} />,
    );
    const first = screen.getByText("Ruta 1").closest("button");
    fireEvent.mouseEnter(first);
    expect(onSelectRoute).toHaveBeenCalledWith(1);
    fireEvent.mouseLeave(first);
    expect(onSelectRoute).toHaveBeenCalledWith(null);
  });

  it("toggles the selection off when the active route is clicked", () => {
    const onSelectRoute = vi.fn();
    render(
      <RouteListPanel routes={routes} selectedRoute={1} onSelectRoute={onSelectRoute} />,
    );
    fireEvent.click(screen.getByText("Ruta 1").closest("button"));
    expect(onSelectRoute).toHaveBeenCalledWith(null);
  });
});
