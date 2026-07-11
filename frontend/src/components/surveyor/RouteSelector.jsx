import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function RouteSelector({ routes, activeRouteId, onSelect }) {
  return (
    <Select value={activeRouteId} onValueChange={onSelect}>
      <SelectTrigger className="min-h-11 w-auto gap-1 border-none bg-transparent px-0 text-lg font-bold text-primary shadow-none focus:ring-0">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {routes.map((route, index) => (
          <SelectItem key={route.id} value={route.id}>
            Ruta {index + 1} · {route.total_trees} árboles
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
