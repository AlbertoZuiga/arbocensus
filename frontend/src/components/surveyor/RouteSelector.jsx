import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { routeOptionLabel } from "../../utils/routes.js";

export default function RouteSelector({ routes, activeRouteId, onSelect }) {
  return (
    <Select value={activeRouteId} onValueChange={onSelect}>
      <SelectTrigger className="min-h-11 w-auto gap-1 border-none bg-transparent px-0 text-lg font-bold text-primary shadow-none focus:ring-0">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {routes.map((route, index) => (
          <SelectItem key={route.id} value={route.id}>
            {routeOptionLabel(route, index)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
