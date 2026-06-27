import { NavLink, Outlet } from "react-router-dom";
import LogoutButton from "../components/LogoutButton.jsx";
import { useAuthStore } from "../store/authStore.js";

const navLinkClass = ({ isActive }) =>
  `rounded px-3 py-1.5 text-sm font-medium ${
    isActive
      ? "bg-emerald-100 text-emerald-800"
      : "text-slate-600 hover:bg-slate-100"
  }`;

export default function AdminLayout() {
  const user = useAuthStore((state) => state.user);

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="flex items-center gap-6 border-b border-slate-200 bg-white px-6 py-3">
        <span className="text-lg font-bold text-emerald-700">Arbocensus</span>
        <nav className="flex items-center gap-2">
          <NavLink to="/admin/datasets" className={navLinkClass}>
            Datasets
          </NavLink>
          <NavLink to="/admin/censadores" className={navLinkClass}>
            Censadores
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-4">
          <span className="text-sm text-slate-600">
            {user?.username} · {user?.role_display}
          </span>
          <LogoutButton />
        </div>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
