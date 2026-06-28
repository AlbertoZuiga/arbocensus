import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ProximityPanel from "./ProximityPanel.jsx";

const stop = { id: "s1", sequence: 2, lat: -33.45, lon: -70.65, visited: false };

describe("ProximityPanel", () => {
  it("renders the visit button for the next pending stop", () => {
    render(
      <ProximityPanel stop={stop} distance={5} inRange locked={false} onVisit={vi.fn()} />
    );
    expect(
      screen.getByRole("button", { name: "Marcar visitado" })
    ).toBeInTheDocument();
  });

  it("still allows marking the next pending stop while out of range", () => {
    render(
      <ProximityPanel
        stop={stop}
        distance={200}
        inRange={false}
        locked={false}
        onVisit={vi.fn()}
      />
    );
    expect(
      screen.getByRole("button", { name: "Marcar de todos modos" })
    ).toBeInTheDocument();
  });

  it("disables the visit button and shows a warning when the stop is locked out of order", () => {
    const onVisit = vi.fn();
    render(
      <ProximityPanel stop={stop} distance={5} inRange locked onVisit={onVisit} />
    );
    expect(
      screen.getByRole("button", { name: "Marcar visitado" })
    ).toBeDisabled();
    expect(
      screen.getByText("Visita los árboles anteriores primero")
    ).toBeInTheDocument();
  });

  it("keeps showing Visitado for an already visited stop", async () => {
    const onVisit = vi.fn();
    render(
      <ProximityPanel
        stop={{ ...stop, visited: true }}
        distance={5}
        inRange
        locked={false}
        onVisit={onVisit}
      />
    );
    expect(screen.getByText("Visitado")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /marcar/i })
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Navegar" })).not.toBeInTheDocument();
  });
});
