import { memo, useEffect, useMemo, useState } from "react";
import { latLngBounds } from "leaflet";
import {
  CircleMarker,
  Polygon,
  Rectangle,
  Tooltip,
  useMapEvents,
} from "react-leaflet";

import { treeKey } from "@/lib/legacySelection.js";
import BaseMap from "./BaseMap.jsx";

const MARKER_STYLES = {
  imported: { color: "#64748b", fillColor: "#94a3b8", fillOpacity: 0.4, weight: 1 },
  selected: { color: "#1d4ed8", fillColor: "#2563eb", fillOpacity: 0.9, weight: 2 },
  available: { color: "#15803d", fillColor: "#16a34a", fillOpacity: 0.6, weight: 1 },
};

const AREA_STYLE = { color: "#f59e0b", weight: 2, fillOpacity: 0.05 };
const BBOX_STYLE = { color: "#2563eb", weight: 1, fillOpacity: 0.1 };

const TreeMarker = memo(function TreeMarker({ tree, selected, onToggle }) {
  const style = tree.already_imported
    ? MARKER_STYLES.imported
    : selected
      ? MARKER_STYLES.selected
      : MARKER_STYLES.available;
  return (
    <CircleMarker
      center={[tree.lat, tree.lon]}
      radius={selected ? 6 : 5}
      pathOptions={style}
      interactive={!tree.already_imported}
      eventHandlers={
        tree.already_imported ? undefined : { click: () => onToggle(tree) }
      }
    />
  );
});

function BboxSelector({ active, onSelect }) {
  const [start, setStart] = useState(null);
  const [current, setCurrent] = useState(null);

  const map = useMapEvents({
    mousedown(event) {
      if (!active || event.originalEvent.button !== 0) return;
      setStart(event.latlng);
      setCurrent(event.latlng);
    },
    mousemove(event) {
      if (start) setCurrent(event.latlng);
    },
  });

  useEffect(() => {
    if (!start) return undefined;
    const finish = () => {
      onSelect(latLngBounds(start, current));
      setStart(null);
      setCurrent(null);
    };
    window.addEventListener("mouseup", finish);
    return () => window.removeEventListener("mouseup", finish);
  }, [start, current, onSelect]);

  useEffect(() => {
    if (!active) {
      setStart(null);
      setCurrent(null);
      return undefined;
    }
    map.dragging.disable();
    const container = map.getContainer();
    container.style.cursor = "crosshair";
    return () => {
      map.dragging.enable();
      container.style.cursor = "";
    };
  }, [active, map]);

  if (!start || !current) return null;
  return (
    <Rectangle bounds={latLngBounds(start, current)} pathOptions={BBOX_STYLE} />
  );
}

function toLeafletRing(polygon) {
  return polygon.coordinates[0].map(([lon, lat]) => [lat, lon]);
}

export default function LegacySelectionMap({
  trees,
  areas,
  selectedKeys,
  bboxMode,
  onToggleTree,
  onToggleArea,
  onBboxSelect,
}) {
  const bounds = useMemo(
    () => trees.map((tree) => [tree.lat, tree.lon]),
    [trees],
  );

  return (
    <BaseMap bounds={bounds} preferCanvas>
      {areas
        .filter((area) => area.polygon)
        .map((area) => (
          <Polygon
            key={area.id}
            positions={toLeafletRing(area.polygon)}
            pathOptions={AREA_STYLE}
            eventHandlers={{ click: () => onToggleArea(area) }}
          >
            <Tooltip sticky>
              {area.campaign} — {area.name} ({area.tree_count} árboles)
            </Tooltip>
          </Polygon>
        ))}
      {trees.map((tree) => (
        <TreeMarker
          key={treeKey(tree)}
          tree={tree}
          selected={selectedKeys.has(treeKey(tree))}
          onToggle={onToggleTree}
        />
      ))}
      <BboxSelector active={bboxMode} onSelect={onBboxSelect} />
    </BaseMap>
  );
}
