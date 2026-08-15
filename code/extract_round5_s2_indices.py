#!/usr/bin/env python3
"""Round_5 Sentinel-2 NDCI/FAI/exceedance extraction.

This is intentionally bounded to the Round_5 pre-commitment:
- Sentinel-2 only, 2017-2025 bloom season.
- Same 16 weir + upstream-control geometry style and JRC persistent-water mask
  used by the standing water-masked HAB extraction.
- Bloom variables only: NDCI primary, FAI secondary, exceedance shares.
- No operation-date collection, no tau rebuild, no identification change.
"""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from pathlib import Path

import ee


import os

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "output" / "ndci_panel"
LOG = BASE / "output" / "log"
WEIR_FILE = BASE / "data" / "weir_inventory.json"
CONTROL_FILE = BASE / "data" / "control_reaches.json"

SERVICE_ACCOUNT = os.environ.get("GEE_SERVICE_ACCOUNT")
KEY_PATH = os.environ.get("GEE_KEY_PATH")
GEE_PROJECT = os.environ.get("GEE_PROJECT")

YEARS = list(range(2017, 2026))
BLOOM_START = "-05-01"
BLOOM_END = "-11-01"
BUFFER_M = 5000
SCALE_S2 = 20
WATER_OCCURRENCE_THRESHOLD = 50
CLOUD_PCT_MAX = 30

# Fixed after the pre-output threshold debate and before any completed panel
# was written. These are descriptive sign-share diagnostics, not outcome
# decision rules.
NDCI_EXCEEDANCE_THRESHOLD = 0.0
FAI_EXCEEDANCE_THRESHOLD = 0.0
THRESHOLD_POLICY = "descriptive_demotion_sign_share"
EXCEEDANCE_DECISIVE = False


def init_gee() -> None:
    if KEY_PATH:
        if not SERVICE_ACCOUNT:
            raise ValueError("GEE_SERVICE_ACCOUNT is required when GEE_KEY_PATH is set")
        if not Path(KEY_PATH).is_file():
            raise FileNotFoundError(KEY_PATH)
        credentials = ee.ServiceAccountCredentials(SERVICE_ACCOUNT, KEY_PATH)
        ee.Initialize(credentials=credentials, project=GEE_PROJECT)
        print(f"[GEE] Initialized with service account project={GEE_PROJECT}.")
        return
    if GEE_PROJECT:
        ee.Initialize(project=GEE_PROJECT)
    else:
        ee.Initialize()
    print(f"[GEE] Initialized with user authentication project={GEE_PROJECT or 'default'}.")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def features() -> ee.FeatureCollection:
    weirs = read_json(WEIR_FILE)
    controls = read_json(CONTROL_FILE)
    controls_by_kr = {c["weir_name_kr"]: c for c in controls}
    feats = []
    for w in weirs:
        c = controls_by_kr[w["name_kr"]]
        feats.append(
            ee.Feature(
                ee.Geometry.Point([w["lon"], w["lat"]]).buffer(BUFFER_M),
                {
                    "site": w["name_en"],
                    "site_type": "weir",
                    "weir_name_kr": w["name_kr"],
                    "weir_name_en": w["name_en"],
                    "control_name": c["control_name"],
                    "river": w.get("river", ""),
                },
            )
        )
        feats.append(
            ee.Feature(
                ee.Geometry.Point([c["lon"], c["lat"]]).buffer(BUFFER_M),
                {
                    "site": c["control_name"],
                    "site_type": "control",
                    "weir_name_kr": c["weir_name_kr"],
                    "weir_name_en": c["weir_name_en"],
                    "control_name": c["control_name"],
                    "river": c.get("river", ""),
                },
            )
        )
    return ee.FeatureCollection(feats)


def water_mask() -> ee.Image:
    occurrence = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence")
    return occurrence.gte(WATER_OCCURRENCE_THRESHOLD)


def mask_s2(img: ee.Image) -> ee.Image:
    qa = img.select("QA60")
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return img.updateMask(mask)


def add_indices(img: ee.Image) -> ee.Image:
    red = img.select("B4").multiply(0.0001)   # 665 nm
    re1 = img.select("B5").multiply(0.0001)   # 705 nm
    nir = img.select("B8A").multiply(0.0001)  # 865 nm
    swir = img.select("B11").multiply(0.0001) # 1610 nm

    ndci = re1.subtract(red).divide(re1.add(red)).rename("ndci")
    baseline = red.add(swir.subtract(red).multiply((865 - 665) / (1610 - 665)))
    fai = nir.subtract(baseline).rename("fai")
    ndci_exc = ndci.gt(NDCI_EXCEEDANCE_THRESHOLD).rename("ndci_exceedance")
    fai_exc = fai.gt(FAI_EXCEEDANCE_THRESHOLD).rename("fai_exceedance")
    return img.addBands([ndci, fai, ndci_exc, fai_exc])


def annual_collection(year: int, mask: ee.Image) -> ee.ImageCollection:
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(f"{year}{BLOOM_START}", f"{year}{BLOOM_END}")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", CLOUD_PCT_MAX))
        .map(mask_s2)
        .map(add_indices)
        .map(lambda img: img.updateMask(mask))
    )
    return col


def extract() -> list[dict]:
    fc = features()
    wm = water_mask()
    rows: list[dict] = []
    reducer = (
        ee.Reducer.mean()
        .combine(ee.Reducer.median(), sharedInputs=True)
        .combine(ee.Reducer.stdDev(), sharedInputs=True)
        .combine(ee.Reducer.count(), sharedInputs=True)
    )
    for year in YEARS:
        t0 = time.time()
        col = annual_collection(year, wm)
        image_count = col.size().getInfo()
        img = col.select(["ndci", "fai", "ndci_exceedance", "fai_exceedance"]).reduce(reducer)
        reduced = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=SCALE_S2).getInfo()
        for feat in reduced["features"]:
            props = feat["properties"]
            rows.append(
                {
                    "year": year,
                    "site": props.get("site"),
                    "site_type": props.get("site_type"),
                    "weir_name_kr": props.get("weir_name_kr"),
                    "weir_name_en": props.get("weir_name_en"),
                    "control_name": props.get("control_name"),
                    "river": props.get("river"),
                    "s2_image_count_year": image_count,
                    "ndci_mean": props.get("ndci_mean"),
                    "ndci_median": props.get("ndci_median"),
                    "ndci_std": props.get("ndci_stdDev"),
                    "ndci_valid_pixel_observations": props.get("ndci_count"),
                    "ndci_exceedance_share_gt_0p00_descriptive": props.get("ndci_exceedance_mean"),
                    "fai_mean": props.get("fai_mean"),
                    "fai_median": props.get("fai_median"),
                    "fai_std": props.get("fai_stdDev"),
                    "fai_valid_pixel_observations": props.get("fai_count"),
                    "fai_exceedance_share_gt_0p00_descriptive": props.get("fai_exceedance_mean"),
                    "water_mask": f"JRC occurrence >= {WATER_OCCURRENCE_THRESHOLD}",
                    "months": "May-Oct",
                }
            )
        print(f"{year}: images={image_count}, features={len(reduced['features'])}, elapsed={time.time()-t0:.1f}s", flush=True)
    return rows


def write_outputs(rows: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LOG.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / "round5_s2_ndci_fai_exceedance_panel_2017_2025.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    meta = {
        "created_at": datetime.now().astimezone().isoformat(),
        "csv": str(csv_path),
        "rows": len(rows),
        "years": YEARS,
        "sites_expected": 32,
        "dataset": "COPERNICUS/S2_SR_HARMONIZED",
        "water_mask": "JRC/GSW1_4/GlobalSurfaceWater occurrence >= 50",
        "cloud_filter": f"CLOUDY_PIXEL_PERCENTAGE < {CLOUD_PCT_MAX}",
        "ndci_formula": "(B5 - B4) / (B5 + B4)",
        "fai_formula": "B8A - (B4 + (B11 - B4) * (865 - 665) / (1610 - 665))",
        "ndci_exceedance_threshold": NDCI_EXCEEDANCE_THRESHOLD,
        "fai_exceedance_threshold": FAI_EXCEEDANCE_THRESHOLD,
        "threshold_policy": THRESHOLD_POLICY,
        "exceedance_decisive": EXCEEDANCE_DECISIVE,
        "threshold_debate": str(LOG / "threshold_debate_packet_20260630_0726.md"),
        "exceedance_interpretation": "descriptive sign-share only; not used in terminal R/N/A label",
        "guardrails": [
            "no operation-date collection",
            "no tau rebuild",
            "no identification change",
            "no third index",
        ],
    }
    (OUT / "round5_s2_ndci_fai_exceedance_metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = LOG / "round5_panel_verification.md"
    nonblank_ndci = sum(r["ndci_mean"] is not None for r in rows)
    nonblank_fai = sum(r["fai_mean"] is not None for r in rows)
    md.write_text(
        "\n".join(
            [
                "# Round_5 Panel Verification",
                "",
                f"Created: {meta['created_at']}",
                "",
                f"- CSV: `{csv_path}`",
                f"- Rows: {len(rows)}",
                f"- Nonblank NDCI mean rows: {nonblank_ndci}",
                f"- Nonblank FAI mean rows: {nonblank_fai}",
                "- Expected shape: 32 sites (16 weirs + 16 controls) x 9 years = 288 rows.",
                f"- NDCI descriptive sign-share threshold: > {NDCI_EXCEEDANCE_THRESHOLD}",
                f"- FAI descriptive sign-share threshold: > {FAI_EXCEEDANCE_THRESHOLD}",
                f"- Threshold policy: {THRESHOLD_POLICY}",
                f"- Exceedance decisive for R/N/A label: {EXCEEDANCE_DECISIVE}",
                "- Guardrail: this extraction changed only bloom variables.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(csv_path)
    print(md)


def main() -> None:
    init_gee()
    rows = extract()
    if not rows:
        raise SystemExit("no rows extracted")
    write_outputs(rows)


if __name__ == "__main__":
    main()
