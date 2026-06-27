import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import UserMenu from "./UserMenu.jsx";
import { useAuthStore } from "../store/authStore.js";

const logoutSpy = vi.fn();
vi.mock("../hooks/useLogout.js", () => ({
  useLogout: () => logoutSpy,
}));

function renderMenu() {
  return render(
    <MemoryRouter>
      <UserMenu />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  logoutSpy.mockClear();
  useAuthStore.setState({
    user: { username: "alice", role: "surveyor", role_display: "Censador" },
  });
});

describe("UserMenu", () => {
  it("shows the current username on the trigger", () => {
    renderMenu();
    expect(screen.getByRole("button", { name: /alice/ })).toBeInTheDocument();
  });

  it("keeps the menu closed until the trigger is clicked", () => {
    renderMenu();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("opens the menu showing the role and logs out when clicked", async () => {
    const user = userEvent.setup();
    renderMenu();

    await user.click(screen.getByRole("button", { name: /alice/ }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByText("Censador")).toBeInTheDocument();

    await user.click(screen.getByRole("menuitem", { name: /cerrar sesión/i }));
    expect(logoutSpy).toHaveBeenCalledTimes(1);
  });
});
