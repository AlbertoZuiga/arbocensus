import { Link } from "react-router-dom";

export default function AdminHome() {
  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-slate-800">Panel de administración</h1>
      <Link
        to="/admin/datasets"
        className="w-fit rounded bg-emerald-700 px-4 py-2 font-semibold text-white"
      >
        Ir a Datasets
      </Link>
    </section>
  );
}
