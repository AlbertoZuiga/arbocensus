import { useEffect, useRef, useState } from "react";

function StopRow({ stop, selected, onSelectStop, rowRef }) {
  return (
    <li ref={rowRef}>
      <button
        type="button"
        onClick={() => onSelectStop(stop.id)}
        className={`flex w-full items-center gap-3 px-4 py-3 text-left ${
          selected ? "bg-blue-50" : "bg-white"
        }`}
      >
        <span
          className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${
            stop.visited ? "bg-emerald-600" : selected ? "bg-blue-600" : "bg-slate-500"
          }`}
        >
          {stop.sequence}
        </span>
        <span className="flex-1 text-sm text-slate-700">Árbol {stop.sequence}</span>
        {stop.visited && (
          <span className="text-xs font-semibold text-emerald-600">Visitado</span>
        )}
      </button>
    </li>
  );
}

function SectionHeader({ children, onClick }) {
  const className =
    "sticky top-0 z-10 w-full bg-slate-100 px-4 py-1 text-left text-xs font-semibold text-slate-500";
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={className}>
        {children}
      </button>
    );
  }
  return <div className={className}>{children}</div>;
}

export default function StopList({ stops, selectedStopId, onSelectStop }) {
  const [showVisited, setShowVisited] = useState(false);
  const selectedRef = useRef(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedStopId]);

  const pending = stops.filter((stop) => !stop.visited);
  const visited = stops.filter((stop) => stop.visited);

  const renderRow = (stop) => {
    const selected = stop.id === selectedStopId;
    return (
      <StopRow
        key={stop.id}
        stop={stop}
        selected={selected}
        onSelectStop={onSelectStop}
        rowRef={selected ? selectedRef : null}
      />
    );
  };

  return (
    <div>
      <SectionHeader>Pendientes ({pending.length})</SectionHeader>
      <ul className="divide-y divide-slate-100">{pending.map(renderRow)}</ul>

      {visited.length > 0 && (
        <>
          <SectionHeader onClick={() => setShowVisited((value) => !value)}>
            Visitados ({visited.length}) {showVisited ? "▾" : "▸"}
          </SectionHeader>
          {showVisited && (
            <ul className="divide-y divide-slate-100">{visited.map(renderRow)}</ul>
          )}
        </>
      )}
    </div>
  );
}
