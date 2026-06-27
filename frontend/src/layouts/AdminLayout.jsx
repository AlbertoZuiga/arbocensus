import { Link, NavLink, Outlet } from "react-router-dom";
import UserMenu from "../components/UserMenu.jsx";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";

const navLinkClass = ({ isActive }) =>
  cn(
    buttonVariants({ variant: isActive ? "secondary" : "ghost", size: "sm" }),
    !isActive && "text-muted-foreground",
  );

export default function AdminLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="flex items-center gap-6 border-b bg-white px-6 py-3">
        <Link to="/admin" className="text-lg font-bold text-primary">
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
