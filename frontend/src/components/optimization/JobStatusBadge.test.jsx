import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import JobStatusBadge from "./JobStatusBadge.jsx";

describe("JobStatusBadge", () => {
  it.each([
    ["queued", "En cola"],
    ["running", "Ejecutando"],
    ["completed", "Completado"],
    ["failed", "Fallido"],
    ["error", "Error"],
  ])("renders the label for %s", (status, label) => {
    render(<JobStatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("falls back to the raw status for an unknown value", () => {
    render(<JobStatusBadge status="weird" />);
    expect(screen.getByText("weird")).toBeInTheDocument();
  });

  it("renders a placeholder when status is missing", () => {
    render(<JobStatusBadge status={undefined} />);
    expect(screen.getByText("Desconocido")).toBeInTheDocument();
  });
});
