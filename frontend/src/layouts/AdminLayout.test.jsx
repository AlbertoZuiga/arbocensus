import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AdminLayout from "./AdminLayout.jsx";
import { useAuthStore } from "../store/authStore.js";

const logoutSpy = vi.fn();
vi.mock("../hooks/useLogout.js", () => ({
  useLogout: () => logoutSpy,
}));

function renderLayout() {
  return render(
    <MemoryRouter>
      <AdminLayout />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  logoutSpy.mockClear();
  useAuthStore.setState({
    user: { username: "alice", role: "admin", role_display: "Administrador" },
  });
});

describe("AdminLayout", () => {
  it("renders the nav links and the current username", () => {
    renderLayout();
    expect(screen.getByRole("link", { name: "Datasets" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Censadores" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /alice/ })).toBeInTheDocument();
  });

  it("keeps the user menu closed until the trigger is clicked", () => {
    renderLayout();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("opens the menu and logs out when the menu item is clicked", async () => {
    const user = userEvent.setup();
    renderLayout();

    await user.click(screen.getByRole("button", { name: /alice/ }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    await user.click(screen.getByRole("menuitem", { name: /cerrar sesión/i }));
    expect(logoutSpy).toHaveBeenCalledTimes(1);
  });
});
