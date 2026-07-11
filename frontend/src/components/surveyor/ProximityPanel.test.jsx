import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ProximityPanel from "./ProximityPanel.jsx";

vi.mock("./CameraCapture.jsx", () => ({
  default: ({ onCapture }) => (
    <button
      type="button"
      onClick={() =>
        onCapture(new File(["photo"], "tree.jpg", { type: "image/jpeg" }))
      }
    >
      Capturar (mock)
    </button>
  ),
}));

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

  it("requires a camera photo before confirming a visit, then submits status + photo", () => {
    const onVisit = vi.fn();
    render(
      <ProximityPanel
        stop={stop}
        distance={5}
        inRange
        locked={false}
        onVisit={onVisit}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Marcar visitado" }));
    expect(screen.getByRole("button", { name: "Confirmar visita" })).toBeDisabled();
    expect(document.querySelector("input[type='file']")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Tomar foto" }));
    fireEvent.click(screen.getByRole("button", { name: "Capturar (mock)" }));
    fireEvent.click(screen.getByRole("button", { name: "Removido / talado" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar visita" }));

    expect(onVisit).toHaveBeenCalledWith("s1", {
      status: "removed",
      photo: expect.any(File),
    });
  });

  it("allows retaking the photo before confirming", () => {
    render(
      <ProximityPanel
        stop={stop}
        distance={5}
        inRange
        locked={false}
        onVisit={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Marcar visitado" }));
    fireEvent.click(screen.getByRole("button", { name: "Tomar foto" }));
    fireEvent.click(screen.getByRole("button", { name: "Capturar (mock)" }));

    expect(screen.getByAltText("Foto capturada del árbol")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Repetir foto/ })
    ).toBeInTheDocument();
  });

  it("skips the stop with a predefined reason and optional photo", () => {
    const onSkip = vi.fn();
    render(
      <ProximityPanel
        stop={stop}
        distance={5}
        inRange
        locked={false}
        onVisit={vi.fn()}
        onSkip={onSkip}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "No se pudo censar" }));
    fireEvent.click(screen.getByRole("button", { name: "Árbol inexistente" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar omisión" }));
    expect(onSkip).toHaveBeenCalledWith("s1", {
      reason: "Árbol inexistente",
      photo: null,
    });
  });

  it("requires custom text before confirming an 'Otro' skip", () => {
    const onSkip = vi.fn();
    render(
      <ProximityPanel
        stop={stop}
        distance={5}
        inRange
        locked={false}
        onVisit={vi.fn()}
        onSkip={onSkip}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "No se pudo censar" }));
    fireEvent.click(screen.getByRole("button", { name: "Otro" }));
    expect(
      screen.getByRole("button", { name: "Confirmar omisión" })
    ).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Describe el motivo"), {
      target: { value: "Zona en obras" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar omisión" }));
    expect(onSkip).toHaveBeenCalledWith("s1", {
      reason: "Zona en obras",
      photo: null,
    });
  });

  it("closes an open sheet when the selected stop changes", () => {
    const { rerender } = render(
      <ProximityPanel
        stop={stop}
        distance={5}
        inRange
        locked={false}
        onVisit={vi.fn()}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Marcar visitado" }));
    expect(
      screen.getByRole("button", { name: "Confirmar visita" })
    ).toBeInTheDocument();

    rerender(
      <ProximityPanel
        stop={{ ...stop, id: "s2", sequence: 3 }}
        distance={5}
        inRange
        locked={false}
        onVisit={vi.fn()}
      />
    );
    expect(
      screen.queryByRole("button", { name: "Confirmar visita" })
    ).not.toBeInTheDocument();
  });

  it("shows an explicit error banner when the visit request fails", () => {
    render(
      <ProximityPanel
        stop={stop}
        distance={5}
        inRange
        locked={false}
        onVisit={vi.fn()}
        onSkip={vi.fn()}
        visitError={{ response: null }}
      />
    );
    expect(
      screen.getByText(/Sin conexión\. No se guardó el registro/)
    ).toBeInTheDocument();
  });

  it("shows the Omitido badge for a skipped stop", () => {
    render(
      <ProximityPanel
        stop={{ ...stop, status: "skipped", skip_reason: "Acceso bloqueado" }}
        distance={5}
        inRange
        locked={false}
        onVisit={vi.fn()}
        onSkip={vi.fn()}
      />
    );
    expect(screen.getByText("Omitido")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "No se pudo censar" })
    ).not.toBeInTheDocument();
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
