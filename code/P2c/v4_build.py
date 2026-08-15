"""Single-command fresh P2c v4 builder.

From this directory:
    python v4_build.py --out-dir ../../output/P2c/v4
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from v4_core import (
    aggregate_daily_satellite,
    build_frequency,
    build_matchups,
    combine_endpoints,
    crosswalk_accounting,
    endpoint_panel,
    point_statistics,
    run_bootstrap,
    run_leave_one_out,
    support_accounting,
)
from v4_map import render_map
from v4_reports import render_reports


EXPECTED_HASHES = {
    "v4_task_packet": "46ff6f8f3f8239e6f711b2e93a1d07b916499542dff2eabb4bbd3d6f64b9084f",
    "v3_design_packet": "440a99a55a37fa80551c51fce638499ae180145266ab559497d9188dd2a76434",
    "debate": "9b435d140c6ad826f7746605d751dfa6d490ac8c7ed410fdfef06ea57d2fa2bc",
    "rejected_v3_audit": "f534e74df7d9b386cb43a2245b22f9caba7659657f59e069005085bc14d65e69",
    "reviewer_comments": "0e3c4954457344ad66e14ccdff0c63d67afc0d5f07f8353c41a2397a19279522",
    "comment_ledger": "12a467e7f91346d7184f4015784f1a4d63cc9f5d37bde00383504a5c66bc2fd4",
    "archive_note": "f15940b3db06d69aba27123fdb174265806fd6108ec3ecec55b0671f255d43bf",
    "scene_v2": "0e195ca3648a34b4f55858e5df9864075f4aa75a909d841c28f99d37c74e37cc",
    "scene_code_v2": "06689a7504cf7f80ba310c34eea88954f6bb0620ed553121caea76602b73f7ac",
    "matchup_code_v2": "389aaa1fc04b6b2ac60a23145253a86df3664100703ae473f25e5009632e703d",
    "map_code_v2": "012106602b813143d4bca48dcbd7cb2ff9676f4f9ec083f9609524d106db32ee",
    "cyano_raw": "c958efe78888e8a0866c8cf3ab0c06ee74724c84e049feb8dc95126d3f952e2b",
    "chla_raw": "8a9acfd0828d5f4d441ded7caa1706ccd980e16417467a58c13d8006765f5f49",
    "crosswalk": "e573503ef24115a51e845931f9cb0e2268d98fa2cbe255d5a31dba3d33ad4633",
    "weirs": "fd75caa126fc4921b9ee602791f1c77474e0989e9a4bde751f99d82527683bd4",
    "controls": "a8bf63ec39a6b28dda7bd36a25defca30e3f0ec048b0c1e57fda555f889db64a",
    "hydrorivers": "9e1437f9b45f624ab8a4cb598a081b407ff26481e209da093f94110f2dd95935",
    "natural_earth": "239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255",
    "hydrorivers_documentation": "4afcdb2b54b93793a0196c2795ffe8ba6e7364a2ef31ecc2f783a7dd3b5df573",
    "freeze": "4786e155c9346292f74c6e397f278c1e70b245ed48a44e84752f7e5e920d3a2c",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_paths() -> dict[str, tuple[str, Path]]:
    code = Path(__file__).resolve()
    revision = code.parents[3]
    hab = code.parents[4]
    project = Path.home() / "mas2-project"
    packet = project / "workspace/source-packets/ECOINF_revision1_20260815"
    return {
        "v4_task_packet": ("source_packet/P2c_v4_fresh_implementation_packet.md", packet / "P2c_v4_fresh_implementation_packet.md"),
        "v3_design_packet": ("source_packet/P2c_v3_execution_packet.md", packet / "P2c_v3_execution_packet.md"),
        "debate": ("source_packet/P2c_stuck_debate.json", project / "workspace/execution_ECOINF_revision1_P2c_stuck_debate_20260815.json"),
        "rejected_v3_audit": ("99_admin/reports/P2c_v3_AGY1_REJECTED.md", revision / "99_admin/reports/P2c_v3_AGY1_REJECTED.md"),
        "reviewer_comments": ("00_decision/reviewer_comments_verbatim.md", revision / "00_decision/reviewer_comments_verbatim.md"),
        "comment_ledger": ("01_intake/comment_ledger.csv", revision / "01_intake/comment_ledger.csv"),
        "archive_note": ("source_packet/P2c_official_archive_note.md", packet / "P2c_official_archive_note.md"),
        "scene_v2": ("03_analysis/output/P2c/v2/scene_level_matchups_v2.csv", revision / "03_analysis/output/P2c/v2/scene_level_matchups_v2.csv"),
        "scene_code_v2": ("03_analysis/code/P2c/v2_scene_level_export.py", revision / "03_analysis/code/P2c/v2_scene_level_export.py"),
        "matchup_code_v2": ("03_analysis/code/P2c/v2_matchup_analysis.py", revision / "03_analysis/code/P2c/v2_matchup_analysis.py"),
        "map_code_v2": ("03_analysis/code/P2c/v2_study_map.py", revision / "03_analysis/code/P2c/v2_study_map.py"),
        "cyano_raw": ("source_data/insitu/cyanobacteria_panel.csv", hab / "Round_6/01_data/insitu/cyanobacteria_panel.csv"),
        "chla_raw": ("source_data/insitu/chlorophyll_panel.csv", hab / "Round_6/01_data/insitu/chlorophyll_panel.csv"),
        "crosswalk": ("source_data/station_reach_crosswalk_direct_validation_closure_v6.csv", hab / "research_execution/03_validation/station_reach_crosswalk_direct_validation_closure_v6.csv"),
        "weirs": ("source_data/weir_inventory.json", hab / "weir_inventory.json"),
        "controls": ("source_data/control_reaches.json", hab / "control_reaches.json"),
        "hydrorivers": ("source_data/hydrorivers_korea_mainstems.json", hab / "revision/figures/data/hydrorivers_korea_mainstems_12625_12915_3470_3800.json"),
        "natural_earth": ("source_data/ne_10m_admin_0_countries.geojson", hab / "revision/figures/data/ne_10m_admin_0_countries.geojson"),
        "hydrorivers_documentation": ("source_data/HydroRIVERS_TechDoc_v10.pdf", project / "workspace/external_data/hydrorivers/HydroRIVERS_TechDoc_v10.pdf"),
        "freeze": ("03_analysis/frozen_protocols/P2c_freeze_v4_postresult_fresh.md", revision / "03_analysis/frozen_protocols/P2c_freeze_v4_postresult_fresh.md"),
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def robustness_table(stats: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ndci = stats[stats["index"] == "ndci"]
    for keys, group in ndci.groupby(["window", "specification", "aggregation"], sort=True):
        by_endpoint = group.set_index("endpoint")
        chla = by_endpoint.loc["chlorophyll_a"]
        cyano = by_endpoint.loc["harmful_cyanobacteria"]
        lo, hi = float(chla.delta_ci_low), float(chla.delta_ci_high)
        rows.append(
            {
                "window": keys[0], "specification": keys[1], "aggregation": keys[2],
                "n_rows_chla": int(chla.n_rows), "n_rows_cyano": int(cyano.n_rows),
                "n_weirs_chla": int(chla.n_estimable_weirs), "n_weirs_cyano": int(cyano.n_estimable_weirs),
                "n_common_weirs": int(chla.n_common_weirs),
                "r_chla_full": chla.association, "r_cyano_full": cyano.association,
                "r_chla_common": chla.common_support_association,
                "r_cyano_common": cyano.common_support_association,
                "delta_r": chla.paired_delta_chla_minus_cyano,
                "delta_ci_low": lo, "delta_ci_high": hi,
                "interval_excludes_zero": bool(np.isfinite(lo) and np.isfinite(hi) and (lo > 0 or hi < 0)),
                "positive_delta": bool(chla.paired_delta_chla_minus_cyano > 0),
                "support_status": "estimable" if chla.n_common_weirs >= 2 else "insufficient_common_weirs",
                "p_method": "not_computed_ci_primary",
            }
        )
    result = pd.DataFrame(rows)
    required = result[(result["aggregation"] == "equal_per_weir_fisher_z")]
    robust = bool((required["positive_delta"] & required["interval_excludes_zero"] & (required["support_status"] == "estimable")).all())
    result["global_endpoint_conclusion"] = "robust" if robust else "not_robust"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--bootstrap-draws", type=int, default=3000)
    args = parser.parse_args()
    out = Path(args.out_dir).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"output directory is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    sources = source_paths()
    manifest_sources = []
    for role, (logical, path) in sources.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = sha256(path)
        if actual != EXPECTED_HASHES[role]:
            raise ValueError(f"source hash drift: {role}: {actual} != {EXPECTED_HASHES[role]}")
        stat = path.stat()
        manifest_sources.append(
            {"role": role, "logical_path": logical, "sha256": actual, "size_bytes": stat.st_size, "mtime_epoch": stat.st_mtime}
        )

    scene = pd.read_csv(sources["scene_v2"][1])
    weirs = json.loads(sources["weirs"][1].read_text(encoding="utf-8"))
    site_order = [w["name_en"] for w in weirs]
    mapping = {w["name_kr"]: w["name_en"] for w in weirs}
    daily = aggregate_daily_satellite(scene)
    daily.to_csv(out / "daily_satellite_pixel_weighted_v4.csv", index=False, float_format="%.17g")

    chla, chla_audit = endpoint_panel(
        pd.read_csv(sources["chla_raw"][1], low_memory=False), "chlorophyll_a", "iemChla", "mg/m3", mapping
    )
    cyano, cyano_audit = endpoint_panel(
        pd.read_csv(sources["cyano_raw"][1], low_memory=False),
        "harmful_cyanobacteria_total", "iemBgalageCellCo", "Cells/100mL", mapping,
    )
    endpoint_audit = {"chlorophyll_a": chla_audit, "harmful_cyanobacteria": cyano_audit}
    write_json(out / "endpoint_construction_audit_v4.json", endpoint_audit)
    insitu = combine_endpoints(chla, cyano)
    pairs = build_matchups(daily, insitu)
    pairs.to_csv(out / "matchup_pairs_v4.csv", index=False, float_format="%.17g")

    points = point_statistics(pairs)
    draws, intervals = run_bootstrap(pairs, b=args.bootstrap_draws, seed=20260815)
    stats = points.merge(
        intervals,
        on=["window", "specification", "aggregation", "index", "endpoint"],
        how="left", validate="one_to_one",
    )
    stats.to_csv(out / "matchup_statistics_v4.csv", index=False, float_format="%.17g")
    robustness = robustness_table(stats)
    robustness.to_csv(out / "endpoint_contrast_robustness_v4.csv", index=False, float_format="%.17g")
    draws.to_csv(
        out / "bootstrap_draws_v4.csv.gz", index=False, float_format="%.17g",
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
    )

    loo = run_leave_one_out(pairs, all_sites=site_order)
    loo.to_csv(out / "leave_one_weir_out_v4.csv", index=False, float_format="%.17g")
    support = support_accounting(pairs, site_order)
    support.to_csv(out / "zero_and_support_accounting_v4.csv", index=False, float_format="%.17g")
    frequency = build_frequency(scene, site_order, range(2017, 2026))
    frequency.to_csv(out / "observation_frequency_v4.csv", index=False, float_format="%.17g")

    crosswalk = crosswalk_accounting(pd.read_csv(sources["crosswalk"][1], low_memory=False))
    crosswalk.update({"source_logical_path": sources["crosswalk"][0], "source_sha256": EXPECTED_HASHES["crosswalk"]})
    write_json(out / "crosswalk_accounting_v4.json", crosswalk)

    map_meta = render_map(
        sources["weirs"][1], sources["controls"][1], sources["hydrorivers"][1],
        sources["natural_earth"][1], out / "study_area_map_v4.png",
    )
    map_meta.update(
        {
            "weir_source": {"logical_path": sources["weirs"][0], "sha256": EXPECTED_HASHES["weirs"]},
            "control_source": {"logical_path": sources["controls"][0], "sha256": EXPECTED_HASHES["controls"]},
            "river_source": {"logical_path": sources["hydrorivers"][0], "sha256": EXPECTED_HASHES["hydrorivers"]},
            "locator_source_detail": {"logical_path": sources["natural_earth"][0], "sha256": EXPECTED_HASHES["natural_earth"]},
            "hydrorivers_citation": "Lehner, B. and Grill, G. (2013), Hydrological Processes 27:2171-2186.",
            "hydrorivers_license": "HydroSHEDS data are free for non-commercial and commercial use under the source license.",
            "claim_boundary": "buffers may mix upstream lentic and downstream lotic water; no station-point co-location or directed-network connection is implied",
        }
    )
    write_json(out / "study_area_map_metadata_v4.json", map_meta)
    (out / "study_area_map_sources_v4.md").write_text(
        "# Study-area map sources and claim boundary\n\n"
        "- CRS: EPSG:5179 (Korea 2000 / Unified CS).\n"
        "- Target coordinates: `source_data/weir_inventory.json` (16).\n"
        "- Control coordinates: `source_data/control_reaches.json` (16).\n"
        "- River context: cached HydroRIVERS mainstems; cite Lehner & Grill (2013), Hydrological Processes 27:2171–2186. The source license permits commercial and non-commercial use.\n"
        "- Locator: Natural Earth admin-0 countries. Natural Earth public-domain data.\n"
        "- Buffers are exact 5-km projected circles and can mix upstream lentic and downstream lotic water. They do not imply station-point co-location or confirmed directed-network connection.\n",
        encoding="utf-8",
    )

    manifest = {
        "analysis": "P2c_v4_postresult_fresh",
        "command": "python v4_build.py --out-dir ../../output/P2c/v4",
        "bootstrap_seed": 20260815,
        "bootstrap_draws": args.bootstrap_draws,
        "freeze_sha256": EXPECTED_HASHES["freeze"],
        "runtime": {"python": platform.python_version(), "executable_name": Path(sys.executable).name},
        "packages": {name: importlib.metadata.version(name) for name in ["numpy", "pandas", "scipy", "matplotlib", "Pillow", "pyproj"]},
        "sources": manifest_sources,
    }
    write_json(out / "source_manifest_v4.json", manifest)
    render_reports(out, stats, robustness, frequency, support, endpoint_audit, crosswalk, map_meta)
    print(json.dumps({"status": "BUILT_PENDING_FINAL_VERIFICATION", "output": str(out), "pairs": len(pairs), "draw_rows": len(draws), "loo_rows": len(loo)}, sort_keys=True))


if __name__ == "__main__":
    main()
