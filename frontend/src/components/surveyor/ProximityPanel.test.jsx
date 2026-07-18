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

function renderPanel(props = {}) {
  return render(
    <ProximityPanel
      stop={stop}
      distance={5}
      inRange
      locked={false}
      onVisit={vi.fn()}
      onSkip={vi.fn()}
      {...props}
    />
  );
}

function openSheet() {
  fireEvent.click(screen.getByRole("button", { name: "Registrar" }));
}

describe("ProximityPanel", () => {
  it("renders a single register button for the next pending stop", () => {
    renderPanel();
    expect(screen.getByRole("button", { name: "Registrar" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "No se pudo censar" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Marcar visitado" })
    ).not.toBeInTheDocument();
  });

  it("still allows registering the next pending stop while out of range", () => {
    renderPanel({ distance: 200, inRange: false });
    expect(
      screen.getByRole("button", { name: "Registrar de todos modos" })
    ).toBeInTheDocument();
  });

  it("disables the register button and shows a warning when the stop is locked out of order", () => {
    renderPanel({ locked: true });
    expect(screen.getByRole("button", { name: "Registrar" })).toBeDisabled();
    expect(
      screen.getByText("Visita los árboles anteriores primero")
    ).toBeInTheDocument();
  });

  it("keeps the confirm button disabled until a tree state is selected", () => {
    renderPanel();
    openSheet();
    expect(
      screen.getByRole("button", { name: "Confirmar registro" })
    ).toBeDisabled();
  });

  it("exposes the selected tree state to assistive tech", () => {
    renderPanel();
    openSheet();
    const alive = screen.getByRole("button", { name: "Vivo" });
    expect(alive).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(alive);
    expect(alive).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Otro" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("requires a camera photo for a censused tree, then submits status + photo via visit", () => {
    const onVisit = vi.fn();
    renderPanel({ onVisit });
    openSheet();
    fireEvent.click(screen.getByRole("button", { name: "Removido / talado" }));
    expect(
      screen.getByRole("button", { name: "Confirmar registro" })
    ).toBeDisabled();
    expect(document.querySelector("input[type='file']")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Tomar foto" }));
    fireEvent.click(screen.getByRole("button", { name: "Capturar (mock)" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar registro" }));

    expect(onVisit).toHaveBeenCalledWith("s1", {
      status: "removed",
      photo: expect.any(File),
    });
  });

  it("submits a not-found tree via visit without requiring a photo", () => {
    const onVisit = vi.fn();
    const onSkip = vi.fn();
    renderPanel({ onVisit, onSkip });
    openSheet();
    fireEvent.click(screen.getByRole("button", { name: "No encontrado" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar registro" }));
    expect(onVisit).toHaveBeenCalledWith("s1", {
      status: "not_found",
      photo: null,
    });
    expect(onSkip).not.toHaveBeenCalled();
  });

  it("submits a blocked access via skip with the predefined reason", () => {
    const onVisit = vi.fn();
    const onSkip = vi.fn();
    renderPanel({ onVisit, onSkip });
    openSheet();
    fireEvent.click(screen.getByRole("button", { name: "Acceso bloqueado" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar registro" }));
    expect(onSkip).toHaveBeenCalledWith("s1", {
      reason: "Acceso bloqueado",
      photo: null,
    });
    expect(onVisit).not.toHaveBeenCalled();
  });

  it("requires custom text before confirming an 'Otro' registration, then skips with it", () => {
    const onSkip = vi.fn();
    renderPanel({ onSkip });
    openSheet();
    fireEvent.click(screen.getByRole("button", { name: "Otro" }));
    expect(
      screen.getByRole("button", { name: "Confirmar registro" })
    ).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Describe el motivo"), {
      target: { value: "Zona en obras" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar registro" }));
    expect(onSkip).toHaveBeenCalledWith("s1", {
      reason: "Zona en obras",
      photo: null,
    });
  });

  it("allows retaking the photo before confirming", () => {
    renderPanel();
    openSheet();
    fireEvent.click(screen.getByRole("button", { name: "Vivo" }));
    fireEvent.click(screen.getByRole("button", { name: "Tomar foto" }));
    fireEvent.click(screen.getByRole("button", { name: "Capturar (mock)" }));

    expect(screen.getByAltText("Foto capturada del árbol")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Repetir foto/ })
    ).toBeInTheDocument();
  });

  it("closes an open sheet when the selected stop changes", () => {
    const { rerender } = renderPanel();
    openSheet();
    expect(
      screen.getByRole("button", { name: "Confirmar registro" })
    ).toBeInTheDocument();

    rerender(
      <ProximityPanel
        stop={{ ...stop, id: "s2", sequence: 3 }}
        distance={5}
        inRange
        locked={false}
        onVisit={vi.fn()}
        onSkip={vi.fn()}
      />
    );
    expect(
      screen.queryByRole("button", { name: "Confirmar registro" })
    ).not.toBeInTheDocument();
  });

  it("shows an explicit error banner when the visit request fails", () => {
    renderPanel({ visitError: { response: null } });
    expect(
      screen.getByText(/Sin conexión\. No se guardó el registro/)
    ).toBeInTheDocument();
  });

  it("shows the Omitido badge for a skipped stop", () => {
    renderPanel({ stop: { ...stop, status: "skipped", skip_reason: "Acceso bloqueado" } });
    expect(screen.getByText("Omitido")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Registrar" })
    ).not.toBeInTheDocument();
  });

  it("keeps showing Visitado for an already visited stop", () => {
    renderPanel({ stop: { ...stop, visited: true } });
    expect(screen.getByText("Visitado")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /registrar/i })
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Navegar" })).not.toBeInTheDocument();
  });
});
