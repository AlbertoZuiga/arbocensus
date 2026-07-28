export const STATUS_LABELS = {
  alive: "Vivo",
  removed: "Removido",
  not_found: "No encontrado",
  other: "Otro",
  unknown: "Desconocido",
};

export const STATUS_STYLES = {
  alive: "border-green-600/30 bg-green-600/10 text-green-700",
  removed: "border-destructive/30 bg-destructive/10 text-destructive",
  not_found: "border-amber-600/30 bg-amber-600/10 text-amber-700",
  other: "border-muted-foreground/30 bg-muted text-muted-foreground",
  unknown: "border-muted-foreground/30 bg-muted text-muted-foreground",
};

export const dateFormatter = new Intl.DateTimeFormat("es-CL", {
  day: "numeric",
  month: "short",
  year: "numeric",
});
