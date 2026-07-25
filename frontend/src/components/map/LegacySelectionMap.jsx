import { memo, useEffect, useMemo, useState } from "react";
import { latLngBounds } from "leaflet";
import {
  CircleMarker,
  Polygon,
  Polyline,
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
const DRAWING_STYLE = { color: "#2563eb", weight: 2, fillOpacity: 0.1 };
const VERTEX_STYLE = { color: "#1d4ed8", fillColor: "#fff", fillOpacity: 1, weight: 2 };
const CLOSE_TOLERANCE_PX = 12;

const TreeMarker = memo(function TreeMarker({
  tree,
  selected,
  drawing,
  onToggle,
}) {
  const style = tree.already_imported
    ? MARKER_STYLES.imported
    : selected
      ? MARKER_STYLES.selected
      : MARKER_STYLES.available;
  const clickable = !tree.already_imported && !drawing;
  return (
    <CircleMarker
      center={[tree.lat, tree.lon]}
      radius={selected ? 6 : 5}
      pathOptions={style}
      interactive={clickable}
      eventHandlers={clickable ? { click: () => onToggle(tree) } : undefined}
    />
  );
});

function useDrawingInteractions(map, active) {
  useEffect(() => {
    if (!active) return undefined;
    const container = map.getContainer();
    container.style.cursor = "crosshair";
    map.doubleClickZoom.disable();
    return () => {
      container.style.cursor = "";
      map.doubleClickZoom.enable();
    };
  }, [map, active]);
}

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

  useDrawingInteractions(map, active);

  useEffect(() => {
    if (!active) return undefined;
    map.dragging.disable();
    return () => {
      map.dragging.enable();
    };
  }, [map, active]);

  useEffect(() => {
    if (!active) {
      setStart(null);
      setCurrent(null);
    }
  }, [active]);

  if (!start || !current) return null;
  return (
    <Rectangle bounds={latLngBounds(start, current)} pathOptions={BBOX_STYLE} />
  );
}

function PolygonSelector({ active, onSelect }) {
  const [points, setPoints] = useState([]);
  const [closedRing, setClosedRing] = useState(null);

  const map = useMapEvents({
    click(event) {
      if (!active) return;
      const closes =
        points.length >= 3 &&
        map
          .latLngToContainerPoint(event.latlng)
          .distanceTo(map.latLngToContainerPoint(points[0])) <=
          CLOSE_TOLERANCE_PX;
      if (closes) {
        const ring = points.map((point) => [point.lat, point.lng]);
        setPoints([]);
        setClosedRing(ring);
        onSelect(ring);
        return;
      }
      setClosedRing(null);
      setPoints((prev) => [...prev, event.latlng]);
    },
  });

  useDrawingInteractions(map, active);

  useEffect(() => {
    if (!active) {
      setPoints([]);
      setClosedRing(null);
    }
  }, [active]);

  return (
    <>
      {closedRing && (
        <Polygon positions={closedRing} pathOptions={DRAWING_STYLE} />
      )}
      {points.length > 1 && (
        <Polyline positions={points} pathOptions={DRAWING_STYLE} />
      )}
      {points.length > 0 && (
        <CircleMarker
          center={points[0]}
          radius={6}
          pathOptions={VERTEX_STYLE}
          interactive={false}
        />
      )}
    </>
  );
}

function toLeafletRing(polygon) {
  return polygon.coordinates[0].map(([lon, lat]) => [lat, lon]);
}

export default function LegacySelectionMap({
  trees,
  areas,
  selectedKeys,
  selectionMode,
  onToggleTree,
  onToggleArea,
  onBboxSelect,
  onPolygonSelect,
}) {
  const bounds = useMemo(
    () => trees.map((tree) => [tree.lat, tree.lon]),
    [trees],
  );
  const drawing = selectionMode !== null;

  return (
    <BaseMap bounds={bounds} preferCanvas>
      {areas
        .filter((area) => area.polygon)
        .map((area) => (
          <Polygon
            key={area.id}
            positions={toLeafletRing(area.polygon)}
            pathOptions={AREA_STYLE}
            interactive={!drawing}
            eventHandlers={
              drawing ? undefined : { click: () => onToggleArea(area) }
            }
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
          drawing={drawing}
          onToggle={onToggleTree}
        />
      ))}
      <BboxSelector active={selectionMode === "bbox"} onSelect={onBboxSelect} />
      <PolygonSelector
        active={selectionMode === "polygon"}
        onSelect={onPolygonSelect}
      />
    </BaseMap>
  );
}
