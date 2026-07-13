"""Render route-audit GeoJSON + CSV pairs as print-ready map figures for the thesis.

Offline and deterministic: no basemap tiles, no network, no Django, no database, no
Docker. The inputs are the versioned route-audit artifacts (docs/experiments/
route-audit-20260713-*). Every number printed on a figure is read from the CSV;
nothing is recomputed except the polyline self-crossings, which are re-derived with
the same geometry as backend/apps/optimization/route_audit.py and asserted against
the CSV column, so a figure can never show a number the audit did not measure.

Install once, then see docs/thesis/media/README.md for the exact command behind each
versioned figure:

    python -m venv .venv-figures
    .venv-figures/bin/pip install -r scripts/requirements-figures.txt
"""

import argparse
import csv
import json
import math
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

EARTH_RADIUS_M = 6371000
SUMMARY_LABEL = "summary"

# Okabe-Ito subset: distinct hues AND distinct grayscale luminance, paired with a
# linestyle/marker cycle so identity survives a black-and-white print.
COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#56B4E9", "#E69F00"]
LINESTYLES = ["-", "--", "-.", ":"]
MARKERS = ["o", "s", "^", "D", "v"]

CONTEXT_COLOR = "#b8b8b8"
SCALE_STEPS_M = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000]


def route_style(slot):
    return {
        "color": COLORS[slot % len(COLORS)],
        "linestyle": LINESTYLES[(slot // len(COLORS)) % len(LINESTYLES)],
        "marker": MARKERS[slot % len(MARKERS)],
    }


def load_geojson(path):
    """Return {route_number: [(lon, lat), ...]} in stop order, from the LineStrings."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    routes = {}
    props = {}
    for feature in data["features"]:
        if feature["geometry"]["type"] != "LineString":
            continue
        number = feature["properties"]["route"]
        routes[number] = [(lon, lat) for lon, lat in feature["geometry"]["coordinates"]]
        props[number] = feature["properties"]
    return routes, props


def load_csv(path):
    """Return ({route_number: row}, summary_row) with numeric fields parsed."""
    rows = {}
    summary = None
    with Path(path).open(encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row = {
                "n_trees": int(raw["n_trees"]),
                "duration_sec": int(raw["duration_sec"]),
                "service_total_sec": int(raw["service_total_sec"]),
                "travel_sec": int(raw["travel_sec"]),
                "walk_ratio": float(raw["walk_ratio"]),
                "shortfall_sec": int(raw["shortfall_sec"]),
                "saturation": float(raw["saturation"]),
                "self_crossings": int(raw["self_crossings"]),
            }
            if raw["route"] == SUMMARY_LABEL:
                summary = row
            else:
                rows[int(raw["route"])] = row
    return rows, summary


def check_csv_matches_geojson(csv_rows, geojson_props):
    """The two artifacts of a run must agree; a mismatch means mixed-up files."""
    for number, props in geojson_props.items():
        row = csv_rows[number]
        for column, value in row.items():
            if props[column] != value:
                raise ValueError(
                    f"route {number}: CSV {column}={value} but GeoJSON "
                    f"{column}={props[column]} — CSV and GeoJSON are from "
                    f"different runs"
                )


def project(points, lat0_deg):
    """(lon, lat) degrees -> (x, y) metres, equirectangular about lat0.

    Same projection as apps.optimization.strategies.project_equirectangular, with an
    explicit lat0 so every panel of a figure shares one metric scale.
    """
    cos_lat0 = math.cos(math.radians(lat0_deg))
    return [
        (
            math.radians(lon) * cos_lat0 * EARTH_RADIUS_M,
            math.radians(lat) * EARTH_RADIUS_M,
        )
        for lon, lat in points
    ]


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _crossing_point(first, second):
    """Intersection of two properly crossing segments, or None if they only touch.

    Mirrors route_audit._segments_cross: a zero orientation means an endpoint lies on
    the other segment's line (the legacy dataset has trees at identical coordinates),
    and touching is not a backtrack — only strict straddling counts.
    """
    p1, p2 = first
    p3, p4 = second
    d1 = _orientation(p3, p4, p1)
    d2 = _orientation(p3, p4, p2)
    d3 = _orientation(p1, p2, p3)
    d4 = _orientation(p1, p2, p4)
    if 0.0 in (d1, d2, d3, d4):
        return None
    if (d1 > 0) == (d2 > 0) or (d3 > 0) == (d4 > 0):
        return None
    t = d3 / (d3 - d4)
    return (p3[0] + t * (p4[0] - p3[0]), p3[1] + t * (p4[1] - p3[1]))


def self_crossings(projected):
    """Crossing points of non-adjacent segments of a projected stop sequence."""
    if len(projected) < 4:
        return []
    segments = list(zip(projected[:-1], projected[1:], strict=True))
    points = []
    for i, j in combinations(range(len(segments)), 2):
        if j <= i + 1:
            continue
        point = _crossing_point(segments[i], segments[j])
        if point is not None:
            points.append(point)
    return points


def es_int(value):
    return f"{value:,}".replace(",", ".")


def es_pct(ratio):
    return f"{100 * ratio:.1f}".replace(".", ",") + " %"


def es_crossings(count):
    return f"{count} cruce" if count == 1 else f"{count} cruces"


def legend_label(number, row):
    return (
        f"Ruta {number}: {row['n_trees']} árboles · {es_int(row['duration_sec'])} s · "
        f"caminata {es_pct(row['walk_ratio'])} · {es_crossings(row['self_crossings'])}"
    )


def summary_label(summary, n_routes):
    return (
        f"{n_routes} rutas · {es_int(summary['n_trees'])} árboles · "
        f"caminata agregada {es_pct(summary['walk_ratio'])} · "
        f"{es_crossings(summary['self_crossings'])}"
    )


def nice_scale_length(span_m):
    target = span_m / 4
    for step in SCALE_STEPS_M:
        if step >= target:
            return step
    return SCALE_STEPS_M[-1]


def draw_scale_bar(ax):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    length = nice_scale_length(x1 - x0)
    bx = x0 + 0.06 * (x1 - x0)
    by = y0 + 0.05 * (y1 - y0)
    ax.plot(
        [bx, bx + length], [by, by], color="black", linewidth=1.6, solid_capstyle="butt"
    )
    for x in (bx, bx + length):
        ax.plot([x, x], [by, by + 0.012 * (y1 - y0)], color="black", linewidth=1.6)
    text = f"{es_int(length)} m" if length < 1000 else f"{es_int(length // 1000)} km"
    ax.text(
        bx + length / 2,
        by + 0.02 * (y1 - y0),
        text,
        ha="center",
        va="bottom",
        fontsize=7,
    )


def draw_north_arrow(ax):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x1 - 0.06 * (x1 - x0)
    y = y0 + 0.06 * (y1 - y0)
    ax.annotate(
        "N",
        xy=(x, y + 0.10 * (y1 - y0)),
        xytext=(x, y),
        ha="center",
        va="center",
        fontsize=8,
        arrowprops={"arrowstyle": "-|>", "color": "black", "linewidth": 1.0},
    )


def set_square_limits(ax, points, pad_frac):
    """Square, explicit limits: the scale bar and the aspect must not depend on the
    axes box that matplotlib would otherwise negotiate."""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
    half *= 1 + pad_frac
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half, cy + half)


def style_axes(ax, title):
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_linewidth(0.6)
        spine.set_color("#888888")
    if title:
        ax.set_title(title, fontsize=9, pad=6)


class Panel:
    """One map: the routes of a run, some of them highlighted."""

    def __init__(self, geojson, csv_path, label, highlight):
        self.routes, props = load_geojson(geojson)
        self.rows, self.summary = load_csv(csv_path)
        check_csv_matches_geojson(self.rows, props)
        self.label = label
        self.highlight = highlight or sorted(self.routes)

    def lat0(self):
        lats = [lat for coords in self.routes.values() for _, lat in coords]
        return sum(lats) / len(lats)

    def crossings(self, number, lat0):
        """Crossing points of one route, cross-checked against the CSV count."""
        points = self_crossings(project(self.routes[number], lat0))
        expected = self.rows[number]["self_crossings"]
        if len(points) != expected:
            raise ValueError(
                f"route {number}: recomputed {len(points)} self-crossings but the "
                f"CSV reports {expected}"
            )
        return points

    def draw(
        self,
        ax,
        lat0,
        *,
        legend_max=6,
        legend_loc="upper left",
        focus=None,
        pad_frac=0.05,
    ):
        handles = []
        framed = focus or sorted(self.routes)
        for number in sorted(self.routes):
            if number in self.highlight:
                continue
            xs, ys = zip(*project(self.routes[number], lat0), strict=True)
            ax.plot(xs, ys, color=CONTEXT_COLOR, linewidth=0.5, zorder=1)
            ax.plot(xs, ys, ".", color=CONTEXT_COLOR, markersize=1.0, zorder=1)

        for slot, number in enumerate(sorted(self.highlight)):
            style = route_style(slot)
            xs, ys = zip(*project(self.routes[number], lat0), strict=True)
            ax.plot(
                xs,
                ys,
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=1.3,
                zorder=3,
            )
            ax.plot(
                xs,
                ys,
                linestyle="none",
                marker=style["marker"],
                markersize=2.6,
                markerfacecolor=style["color"],
                markeredgecolor="white",
                markeredgewidth=0.3,
                color=style["color"],
                zorder=4,
            )
            handles.append(
                Line2D(
                    [],
                    [],
                    color=style["color"],
                    linestyle=style["linestyle"],
                    marker=style["marker"],
                    markersize=4,
                    linewidth=1.3,
                    label=legend_label(number, self.rows[number]),
                )
            )

        frame_points = [
            point for number in framed for point in project(self.routes[number], lat0)
        ]
        set_square_limits(ax, frame_points, pad_frac)
        style_axes(ax, self.label)
        draw_scale_bar(ax)
        draw_north_arrow(ax)

        if len(handles) > legend_max:
            handles = [
                Line2D(
                    [],
                    [],
                    color=COLORS[0],
                    linestyle="-",
                    linewidth=1.3,
                    label=summary_label(self.summary, len(self.rows)),
                )
            ]
        ax.legend(
            handles=handles,
            loc=legend_loc,
            fontsize=6.5,
            framealpha=0.9,
            borderpad=0.5,
            handlelength=2.4,
        )

    def draw_zoom(self, ax, number, lat0):
        """One route alone, with its crossings marked — the 'why it looks bad' panel."""
        row = self.rows[number]
        points = project(self.routes[number], lat0)
        xs, ys = zip(*points, strict=True)
        ax.plot(xs, ys, color=COLORS[0], linewidth=1.2, zorder=3)
        ax.plot(
            xs,
            ys,
            linestyle="none",
            marker="o",
            markersize=2.8,
            markerfacecolor="white",
            markeredgecolor=COLORS[0],
            markeredgewidth=0.7,
            zorder=4,
        )
        ax.plot(
            xs[0],
            ys[0],
            marker="^",
            markersize=7,
            color="black",
            linestyle="none",
            zorder=6,
        )
        ax.plot(
            xs[-1],
            ys[-1],
            marker="s",
            markersize=6,
            color="black",
            linestyle="none",
            zorder=6,
        )

        crossings = self.crossings(number, lat0)
        if crossings:
            cx, cy = zip(*crossings, strict=True)
            ax.plot(
                cx,
                cy,
                linestyle="none",
                marker="x",
                markersize=7,
                markeredgewidth=1.4,
                color=COLORS[1],
                zorder=5,
            )

        set_square_limits(ax, points, 0.08)
        style_axes(ax, f"Ruta {number} aislada: secuencia de visita")
        draw_scale_bar(ax)
        draw_north_arrow(ax)
        handles = [
            Line2D(
                [],
                [],
                color=COLORS[0],
                linewidth=1.2,
                marker="o",
                markersize=4,
                markerfacecolor="white",
                label=legend_label(number, self.rows[number]),
            ),
            Line2D(
                [],
                [],
                color=COLORS[1],
                linestyle="none",
                marker="x",
                markeredgewidth=1.4,
                markersize=6,
                label=f"{row['self_crossings']} cruces de la propia secuencia",
            ),
            Line2D(
                [],
                [],
                color="black",
                linestyle="none",
                marker="^",
                markersize=6,
                label="Inicio",
            ),
            Line2D(
                [],
                [],
                color="black",
                linestyle="none",
                marker="s",
                markersize=5,
                label="Fin",
            ),
        ]
        ax.legend(
            handles=handles,
            loc="upper left",
            fontsize=6.5,
            framealpha=0.9,
            borderpad=0.5,
            handlelength=2.4,
        )


def save(fig, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf = out.with_suffix(".pdf")
    png = out.with_suffix(".png")
    # CreationDate=None keeps the PDF byte-identical across renders (no git churn).
    fig.savefig(pdf, format="pdf", bbox_inches="tight", metadata={"CreationDate": None})
    fig.savefig(png, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    return pdf, png


def setup_style():
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["DejaVu Serif"],
            "font.size": 9,
            "figure.dpi": 120,
            "savefig.transparent": False,
            "pdf.fonttype": 42,
        }
    )


def render_single(args):
    panel = Panel(args.geojson, args.csv, args.label, args.highlight)
    lat0 = panel.lat0()
    focus = args.highlight if args.crop_to_highlight else None
    pad = args.context_pad if args.crop_to_highlight else 0.05
    if args.zoom_route:
        fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.6))
        panel.draw(axes[0], lat0, legend_max=args.legend_max, focus=focus, pad_frac=pad)
        panel.draw_zoom(axes[1], args.zoom_route, lat0)
    else:
        fig, ax = plt.subplots(figsize=(6.0, 5.2))
        panel.draw(ax, lat0, legend_max=args.legend_max, focus=focus, pad_frac=pad)
    if args.title:
        fig.suptitle(args.title, fontsize=10)
    fig.tight_layout()
    return save(fig, args.out)


def render_compare(args):
    left = Panel(args.left_geojson, args.left_csv, args.left_label, args.left_highlight)
    right = Panel(
        args.right_geojson, args.right_csv, args.right_label, args.right_highlight
    )
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.8))
    # Each panel keeps its own lat0: the two runs cover different extents, and a
    # shared origin would squash one of them.
    left.draw(
        axes[0],
        left.lat0(),
        legend_max=args.legend_max,
        focus=args.left_focus,
        pad_frac=args.left_pad,
    )
    right.draw(
        axes[1],
        right.lat0(),
        legend_max=args.legend_max,
        focus=args.right_focus,
        pad_frac=args.right_pad,
    )
    if args.title:
        fig.suptitle(args.title, fontsize=10)
    fig.tight_layout()
    return save(fig, args.out)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Render route-audit GeoJSON + CSV pairs as thesis map figures"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    single = sub.add_parser("single", help="One run: all routes, some highlighted")
    single.add_argument("--geojson", required=True)
    single.add_argument("--csv", required=True)
    single.add_argument("--highlight", type=int, nargs="*", default=None)
    single.add_argument(
        "--zoom-route",
        type=int,
        default=None,
        help="Add a second panel with this route alone and its crossings marked",
    )
    single.add_argument("--label", default=None, help="Panel title")
    single.add_argument("--title", default=None, help="Figure title")
    single.add_argument("--legend-max", type=int, default=6)
    single.add_argument(
        "--crop-to-highlight",
        action="store_true",
        help="Frame the map on the highlighted routes instead of the whole run",
    )
    single.add_argument(
        "--context-pad",
        type=float,
        default=1.0,
        help="Extra margin around the highlighted routes, as a fraction of their span",
    )
    single.add_argument("--out", required=True, help="Output path without extension")
    single.set_defaults(func=render_single)

    compare = sub.add_parser("compare", help="Two runs side by side")
    for side in ("left", "right"):
        compare.add_argument(f"--{side}-geojson", required=True)
        compare.add_argument(f"--{side}-csv", required=True)
        compare.add_argument(f"--{side}-label", default=None)
        compare.add_argument(f"--{side}-highlight", type=int, nargs="*", default=None)
        compare.add_argument(
            f"--{side}-focus",
            type=int,
            nargs="*",
            default=None,
            help="Frame the panel on these routes; the others are still drawn, clipped",
        )
        compare.add_argument(f"--{side}-pad", type=float, default=0.05)
    compare.add_argument("--title", default=None)
    compare.add_argument("--legend-max", type=int, default=6)
    compare.add_argument("--out", required=True, help="Output path without extension")
    compare.set_defaults(func=render_compare)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    setup_style()
    pdf, png = args.func(args)
    print(f"{pdf}\n{png}")


if __name__ == "__main__":
    main()
