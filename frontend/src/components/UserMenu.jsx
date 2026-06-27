import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useAuthStore } from "../store/authStore.js";
import { useLogout } from "../hooks/useLogout.js";
import { Button } from "@/components/ui/button";

export default function UserMenu() {
  const user = useAuthStore((state) => state.user);
  const handleLogout = useLogout();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onPointerDown = (event) => {
      if (!menuRef.current.contains(event.target)) setMenuOpen(false);
    };
    const onKeyDown = (event) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

  return (
    <div ref={menuRef} className="relative">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        aria-controls="user-menu"
        onClick={() => setMenuOpen((open) => !open)}
        className="text-muted-foreground"
      >
        {user?.username}
        <ChevronDown
          className={`transition ${menuOpen ? "rotate-180" : ""}`}
        />
      </Button>
      {menuOpen && (
        <div
          id="user-menu"
          role="menu"
          className="absolute right-0 z-50 mt-2 w-48 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
        >
          <div className="px-2 py-1.5 text-xs text-muted-foreground">
            {user?.role_display}
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={handleLogout}
            className="relative flex w-full cursor-default select-none items-center rounded-sm px-2 py-1.5 text-left text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground"
          >
            Cerrar sesión
          </button>
        </div>
      )}
    </div>
  );
}
