import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import StopList from "./StopList.jsx";

const stops = [
  { id: "s1", sequence: 1, visited: true, visited_at: "2026-07-01T10:00:00Z" },
  { id: "s2", sequence: 2, visited: false, status: "skipped", skip_reason: "Sin acceso" },
  { id: "s3", sequence: 3, visited: false, status: "pending", tree_id: "abcdef12" },
  { id: "s4", sequence: 4, visited: false, status: "pending", tree_id: "12abcdef" },
];

describe("StopList", () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders every stop by default", () => {
    render(
      <StopList
        stops={stops}
        selectedStopId={null}
        nextPendingStopId="s3"
        onSelectStop={vi.fn()}
      />
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });

  it("shows only unresolved stops when the pending filter is active", () => {
    render(
      <StopList
        stops={stops}
        selectedStopId={null}
        nextPendingStopId="s3"
        onSelectStop={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /Pendientes \(2\)/ }));
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(screen.getByLabelText("Árbol 3")).toBeInTheDocument();
    expect(screen.getByLabelText("Árbol 4")).toBeInTheDocument();
  });

  it("selects and scrolls to the next pending stop", () => {
    const onSelectStop = vi.fn();
    render(
      <StopList
        stops={stops}
        selectedStopId={null}
        nextPendingStopId="s3"
        onSelectStop={onSelectStop}
      />
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Ir al siguiente pendiente" })
    );
    expect(onSelectStop).toHaveBeenCalledWith("s3");
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "center",
    });
  });

  it("disables the next-pending button and shows an empty state when everything is resolved", () => {
    const resolved = stops.map((stop) => ({ ...stop, visited: true }));
    render(
      <StopList
        stops={resolved}
        selectedStopId={null}
        nextPendingStopId={null}
        onSelectStop={vi.fn()}
      />
    );
    expect(
      screen.getByRole("button", { name: "Ir al siguiente pendiente" })
    ).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /Pendientes \(0\)/ }));
    expect(screen.getByText("No quedan árboles pendientes.")).toBeInTheDocument();
  });
});
