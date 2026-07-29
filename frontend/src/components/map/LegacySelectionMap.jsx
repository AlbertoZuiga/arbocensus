import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { divIcon, latLngBounds } from "leaflet";
import {
  CircleMarker,
  Marker,
  Polygon,
  Polyline,
  Popup,
  Rectangle,
  Tooltip,
  useMapEvents,
} from "react-leaflet";

import { areaShapes, treeKey, treeKeys } from "@/lib/legacySelection.js";
import { midpoint, pointInRing, ringFromCorners } from "@/lib/geometry.js";
import BaseMap from "./BaseMap.jsx";
import TreeHistoryPopup from "./TreeHistoryPopup.jsx";

const MARKER_STYLES = {
  imported: {
    color: "#64748b",
    fillColor: "#94a3b8",
    fillOpacity: 0.4,
    weight: 1,
  },
  selected: {
    color: "#1d4ed8",
    fillColor: "#2563eb",
    fillOpacity: 0.9,
    weight: 2,
  },
  available: {
    color: "#15803d",
    fillColor: "#16a34a",
    fillOpacity: 0.6,
    weight: 1,
  },
};

const AREA_STYLE = { color: "#f59e0b", weight: 2, fillOpacity: 0.05 };
const BBOX_STYLE = { color: "#2563eb", weight: 1, fillOpacity: 0.1 };
const DRAWING_STYLE = { color: "#2563eb", weight: 2, fillOpacity: 0.1 };
const SHAPE_STYLE = { color: "#1d4ed8", weight: 2, fillOpacity: 0.08 };
const VERTEX_STYLE = {
  color: "#1d4ed8",
  fillColor: "#fff",
  fillOpacity: 1,
  weight: 2,
};
const CLOSE_TOLERANCE_PX = 12;
const MIN_RING_VERTICES = 3;

const vertexIcon = divIcon({
  className: "",
  html: '<span class="block h-3 w-3 rounded-full border-2 border-blue-700 bg-white shadow"></span>',
  iconSize: [12, 12],
  iconAnchor: [6, 6],
});

const midpointIcon = divIcon({
  className: "",
  html: '<span class="block h-2.5 w-2.5 rounded-full border border-blue-700 bg-white opacity-60"></span>',
  iconSize: [10, 10],
  iconAnchor: [5, 5],
});

const TreeMarker = memo(function TreeMarker({
  tree,
  selected,
  drawing,
  onClick,
}) {
  const style = selected
    ? MARKER_STYLES.selected
    : tree.already_imported
      ? MARKER_STYLES.imported
      : MARKER_STYLES.available;
  const clickable = !drawing;
  return (
    <CircleMarker
      center={[tree.lat, tree.lon]}
      radius={selected ? 6 : 5}
      pathOptions={style}
      interactive={clickable}
      eventHandlers={clickable ? { click: () => onClick(tree) } : undefined}
    />
  );
});

// Leaflet fires popupclose on the map, never on a popup that no layer owns.
function PopupCloseWatcher({ onClose }) {
  useMapEvents({ popupclose: onClose });
  return null;
}

function EditableShape({ shape, editable, onChange }) {
  const ring = shape.ring;
  return (
    <>
      <Polygon positions={ring} pathOptions={SHAPE_STYLE} interactive={false} />
      {editable &&
        ring.map((vertex, index) => (
          <Marker
            key={`vertex-${index}`}
            position={vertex}
            icon={vertexIcon}
            draggable
            eventHandlers={{
              // Recomputing on drag would run the point-in-ring test over every
              // legacy tree on each animation frame.
              dragend: (event) => {
                const { lat, lng } = event.target.getLatLng();
                onChange(
                  ring.map((point, i) => (i === index ? [lat, lng] : point)),
                );
              },
              contextmenu: () => {
                if (ring.length > MIN_RING_VERTICES) {
                  onChange(ring.filter((_, i) => i !== index));
                }
              },
            }}
          />
        ))}
      {editable &&
        ring.map((vertex, index) => {
          const inserted = midpoint(vertex, ring[(index + 1) % ring.length]);
          return (
            <Marker
              key={`midpoint-${index}`}
              position={inserted}
              icon={midpointIcon}
              eventHandlers={{
                click: () => {
                  const next = [...ring];
                  next.splice(index + 1, 0, inserted);
                  onChange(next);
                },
              }}
            />
          );
        })}
    </>
  );
}

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
      const dragged = start.lat !== current.lat || start.lng !== current.lng;
      if (dragged) {
        onSelect(
          ringFromCorners([start.lat, start.lng], [current.lat, current.lng]),
        );
      }
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

  const map = useMapEvents({
    click(event) {
      if (!active) return;
      const closes =
        points.length >= MIN_RING_VERTICES &&
        map
          .latLngToContainerPoint(event.latlng)
          .distanceTo(map.latLngToContainerPoint(points[0])) <=
          CLOSE_TOLERANCE_PX;
      if (closes) {
        onSelect(points.map((point) => [point.lat, point.lng]));
        setPoints([]);
        return;
      }
      setPoints((prev) => [...prev, event.latlng]);
    },
  });

  useDrawingInteractions(map, active);

  useEffect(() => {
    if (!active) setPoints([]);
  }, [active]);

  return (
    <>
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

// Memoized: the page re-renders on every dialog keystroke, and re-creating one
// element per legacy tree costs hundreds of ms at full selection.
export default memo(function LegacySelectionMap({
  trees,
  areas,
  selectedKeys,
  shapes,
  selectionMode,
  onToggleTree,
  onToggleArea,
  onShapeCreate,
  onShapeChange,
}) {
  const bounds = useMemo(
    () => trees.map((tree) => [tree.lat, tree.lon]),
    [trees],
  );
  const drawing = selectionMode !== null;
  // The legacy area_id only covers the trees of one source and points at the
  // first containing polygon, never the nested one the click landed on, so the
  // area resolves its trees geometrically like a drawn shape does.
  const areaSelections = useMemo(
    () =>
      areaShapes(areas).map(({ area, ring }) => {
        const inside = trees.filter((tree) =>
          pointInRing([tree.lat, tree.lon], ring),
        );
        return { area, ring, count: inside.length, keys: treeKeys(inside) };
      }),
    [areas, trees],
  );
  const [previewTree, setPreviewTree] = useState(null);

  const handleTreeClick = useCallback(
    (tree) => {
      onToggleTree(tree);
      setPreviewTree(tree);
    },
    [onToggleTree],
  );
  const closePreview = useCallback(() => setPreviewTree(null), []);

  return (
    <BaseMap bounds={bounds} preferCanvas>
      {areaSelections.map(({ area, ring, count, keys }) => (
        <Polygon
          key={area.id}
          positions={ring}
          pathOptions={AREA_STYLE}
          eventHandlers={
            drawing ? undefined : { click: () => onToggleArea(keys) }
          }
        >
          <Tooltip sticky>
            {area.campaign} — {area.name} ({count} árboles)
          </Tooltip>
        </Polygon>
      ))}
      {trees.map((tree) => (
        <TreeMarker
          key={treeKey(tree)}
          tree={tree}
          selected={selectedKeys.has(treeKey(tree))}
          drawing={drawing}
          onClick={handleTreeClick}
        />
      ))}
      <PopupCloseWatcher onClose={closePreview} />
      {previewTree && (
        <Popup
          position={[previewTree.lat, previewTree.lon]}
          minWidth={248}
          maxWidth={280}
          keepInView
        >
          <TreeHistoryPopup
            treeId={previewTree.tree_id}
            legacyTree={previewTree}
          />
        </Popup>
      )}
      {shapes.map((shape) => (
        <EditableShape
          key={shape.id}
          shape={shape}
          editable={!drawing}
          onChange={(ring) => onShapeChange(shape.id, ring)}
        />
      ))}
      <BboxSelector
        active={selectionMode === "bbox"}
        onSelect={onShapeCreate}
      />
      <PolygonSelector
        active={selectionMode === "polygon"}
        onSelect={onShapeCreate}
      />
    </BaseMap>
  );
});
