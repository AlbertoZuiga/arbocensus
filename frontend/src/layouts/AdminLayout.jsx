import { Link, NavLink, Outlet } from "react-router-dom";
import UserMenu from "../components/UserMenu.jsx";

const navLinkClass = ({ isActive }) =>
  `rounded px-3 py-1.5 text-sm font-medium ${
    isActive
      ? "bg-emerald-100 text-emerald-800"
      : "text-slate-600 hover:bg-slate-100"
  }`;

export default function AdminLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="flex items-center gap-6 border-b border-slate-200 bg-white px-6 py-3">
        <Link to="/admin" className="text-lg font-bold text-emerald-700">
          Arbocensus
        </Link>
        <nav className="flex items-center gap-2">
          <NavLink to="/admin/datasets" className={navLinkClass}>
            Datasets
          </NavLink>
          <NavLink to="/admin/censadores" className={navLinkClass}>
            Censadores
          </NavLink>
        </nav>
        <div className="ml-auto">
          <UserMenu />
        </div>
      </header>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
