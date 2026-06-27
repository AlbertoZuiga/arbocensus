import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "../store/authStore.js";
import { useLogout } from "../hooks/useLogout.js";

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
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        aria-controls="user-menu"
        onClick={() => setMenuOpen((open) => !open)}
        className="flex cursor-pointer items-center gap-1 text-sm text-slate-600"
      >
        {user?.username}
        <span className={`text-xs transition ${menuOpen ? "rotate-180" : ""}`}>
          ▾
        </span>
      </button>
      {menuOpen && (
        <div
          id="user-menu"
          role="menu"
          className="absolute right-0 z-10 mt-2 w-48 rounded border border-slate-200 bg-white py-1 shadow-lg"
        >
          <div className="px-3 py-2 text-xs text-slate-400">
            {user?.role_display}
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={handleLogout}
            className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
          >
            Cerrar sesión
          </button>
        </div>
      )}
    </div>
  );
}
