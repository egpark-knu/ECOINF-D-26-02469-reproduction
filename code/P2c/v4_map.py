"""Fresh, offline, deterministic P2c v4 study-area map."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon as MplPolygon
from pyproj import Transformer


RIVER_COLORS = {
    "한강(남한강)": "#377eb8",
    "낙동강": "#4daf4a",
    "금강": "#984ea3",
    "영산강": "#ff7f00",
}
RIVER_LABELS = {
    "한강(남한강)": "Han (Namhan)",
    "낙동강": "Nakdong",
    "금강": "Geum",
    "영산강": "Yeongsan",
}

matplotlib.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "axes.titleweight": "bold",
        "axes.labelweight": "bold",
        "axes.labelsize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9,
        "figure.dpi": 150,
        "savefig.dpi": 300,
    }
)


def _iter_rings(geometry: dict):
    if geometry["type"] == "Polygon":
        yield from geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            yield from polygon


def _korea_feature(geojson: dict) -> dict:
    for feature in geojson["features"]:
        props = feature.get("properties", {})
        values = " ".join(str(v) for v in props.values())
        if "South Korea" in values or "Republic of Korea" in values or "대한민국" in values:
            return feature
    raise ValueError("South Korea feature not found in Natural Earth source")


def render_map(
    weir_path: Path,
    control_path: Path,
    rivers_path: Path,
    countries_path: Path,
    output_path: Path,
) -> dict:
    weirs = json.loads(weir_path.read_text(encoding="utf-8"))
    controls = json.loads(control_path.read_text(encoding="utf-8"))
    rivers = json.loads(rivers_path.read_text(encoding="utf-8"))
    countries = json.loads(countries_path.read_text(encoding="utf-8"))
    if len(weirs) != 16 or len(controls) != 16:
        raise ValueError(f"map inventory mismatch: {len(weirs)} weirs, {len(controls)} controls")

    project = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    fig, ax = plt.subplots(figsize=(10.2, 10.8))
    ax.set_facecolor("#f5f3ed")

    plotted_segments = 0
    for record in rivers:
        width = 0.25 + 0.12 * max(0, float(record.get("order", 3)) - 3)
        for segment in record.get("segments", []):
            lon = [p[0] for p in segment]
            lat = [p[1] for p in segment]
            x, y = project.transform(lon, lat)
            ax.plot(x, y, color="#83b9d8", lw=width, alpha=0.44, zorder=1)
            plotted_segments += 1

    control_by_weir = {c["weir_name_kr"]: c for c in controls}
    for w in weirs:
        color = RIVER_COLORS[w["river"]]
        x, y = project.transform(w["lon"], w["lat"])
        ax.add_patch(Circle((x, y), 5000, fill=False, ec=color, lw=0.75, alpha=0.65, zorder=2))
        ax.scatter(x, y, marker="s", s=37, color=color, edgecolor="black", lw=0.45, zorder=4)
        ax.annotate(
            w["name_en"].replace(" Weir", ""), (x, y), xytext=(4, 3),
            textcoords="offset points", fontsize=6.4, color="#202020", zorder=5,
        )
        c = control_by_weir[w["name_kr"]]
        cx, cy = project.transform(c["lon"], c["lat"])
        ax.scatter(cx, cy, marker="^", s=25, facecolor="white", edgecolor=color, lw=0.9, zorder=3)
        ax.plot([x, cx], [y, cy], color=color, lw=0.55, ls=":", alpha=0.8, zorder=2)

    projected = [project.transform(w["lon"], w["lat"]) for w in weirs]
    xs, ys = zip(*projected)
    xmin, xmax = min(xs) - 85000, max(xs) + 80000
    ymin, ymax = min(ys) - 65000, max(ys) + 65000
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect("equal")
    ax.set_xlabel("Easting (m), Korea 2000 / Unified CS", fontweight="bold", labelpad=8)
    ax.set_ylabel("Northing (m), Korea 2000 / Unified CS", fontweight="bold", labelpad=8)
    ax.set_title("Four Rivers study reaches", fontsize=15, fontweight="bold", pad=12)

    # Deterministic 100-km scale bar.
    bar_x, bar_y = xmin + 22000, ymin + 22000
    ax.plot([bar_x, bar_x + 100000], [bar_y, bar_y], color="black", lw=2.2, zorder=6)
    ax.plot([bar_x, bar_x], [bar_y - 2500, bar_y + 2500], color="black", lw=1.2, zorder=6)
    ax.plot([bar_x + 100000, bar_x + 100000], [bar_y - 2500, bar_y + 2500], color="black", lw=1.2, zorder=6)
    ax.text(bar_x + 50000, bar_y + 5000, "100 km", ha="center", va="bottom", fontsize=8)

    # North arrow.
    ax.annotate("N", xy=(xmax - 26000, ymax - 18000), ha="center", fontsize=10, weight="bold")
    ax.annotate("", xy=(xmax - 26000, ymax - 21000), xytext=(xmax - 26000, ymax - 54000),
                arrowprops={"arrowstyle": "-|>", "color": "black", "lw": 1.4})

    handles = [
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#777777", markeredgecolor="black", label="Target weir"),
        Line2D([0], [0], marker="^", color="none", markerfacecolor="white", markeredgecolor="#555555", label="Upstream control"),
        Line2D([0], [0], color="#777777", lw=0.8, label="5-km weir buffer"),
        Line2D([0], [0], color="#83b9d8", lw=1.2, label="HydroRIVERS context"),
    ]
    handles += [Line2D([0], [0], marker="s", color="none", markerfacecolor=color, label=RIVER_LABELS[river]) for river, color in RIVER_COLORS.items()]
    ax.legend(handles=handles, loc="lower right", fontsize=7.2, frameon=True, framealpha=0.96, ncol=2)
    ax.grid(color="white", lw=0.6, alpha=0.8)

    # Locator inset from Natural Earth source.
    # Keep the inset and its title fully inside the data panel. An earlier
    # outside title collided with the main axes' scientific-notation offset.
    inset = ax.inset_axes([0.02, 0.62, 0.24, 0.24])
    korea = _korea_feature(countries)
    for ring in _iter_rings(korea["geometry"]):
        inset.add_patch(MplPolygon(ring, closed=True, facecolor="#d9d9d9", edgecolor="#333333", lw=0.6))
    inset.scatter([w["lon"] for w in weirs], [w["lat"] for w in weirs], s=5, color="#d62728", zorder=2)
    inset.set_xlim(124.3, 130.0)
    inset.set_ylim(33.0, 39.1)
    inset.set_aspect("equal")
    inset.set_xticks([])
    inset.set_yticks([])
    inset.text(
        0.5, 0.975, "Republic of Korea", transform=inset.transAxes,
        ha="center", va="top", fontsize=7, fontweight="bold",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 1.2},
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight", metadata={"Software": "P2c v4 matplotlib"})
    plt.close(fig)
    return {
        "weir_count": len(weirs),
        "control_count": len(controls),
        "buffer_radius_m": 5000,
        "river_context_records": len(rivers),
        "river_context_segments": plotted_segments,
        "crs": "EPSG:5179",
        "locator_source": "Natural Earth admin-0 countries",
    }
