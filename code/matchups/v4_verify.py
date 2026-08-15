"""Substantive verification helpers for matchups v4."""

from __future__ import annotations

import re
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from v4_build import EXPECTED_HASHES, sha256, source_paths
from v4_core import AGGREGATIONS, ENDPOINTS, INDICES, SPECIFICATIONS, WINDOWS, build_frequency


FORBIDDEN_SEMANTICS = (
    r"\bcensor(?:ed|ing)?\b",
    r"\bdetection limit\b",
    r"\bLOD\b",
    r"\bbelow detection\b",
    r"hydrologically disconnected",
)
SECRET_PATTERNS = (r"AIza[0-9A-Za-z_-]{20,}", r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*[^\s,;]+")


def scan_submission_text(paths: list[Path]) -> list[str]:
    failures = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        local_home = "/" + "Users" + "/"
        private_workspace = "ma" + "s2" + "-project"
        if local_home in text or private_workspace in text:
            failures.append(f"local_path:{path.name}")
        for pattern in FORBIDDEN_SEMANTICS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                failures.append(f"forbidden_semantic:{path.name}:{pattern}")
        for pattern in SECRET_PATTERNS:
            if re.search(pattern, text):
                failures.append(f"secret_pattern:{path.name}:{pattern}")
    return failures


def _gate(gates: list[dict], name: str, ok: bool, evidence: dict) -> None:
    gates.append({"name": name, "status": "pass" if ok else "fail", "evidence": evidence})


def minimum_candidate_dates(candidates: pd.Series, in_situ_date: pd.Timestamp, radius: int) -> tuple[int, set[str]]:
    lags = (candidates - in_situ_date).dt.days
    within = lags[lags.abs() <= radius]
    minimum = int(within.abs().min())
    minimum_indices = within.index[within.abs() == minimum]
    dates = set(candidates.loc[minimum_indices].dt.strftime("%Y-%m-%d"))
    return minimum, dates


def report_support_semantics(text: str, primary_count: int) -> bool:
    normalized = re.sub(r"\s+", " ", text).lower()
    required = f"v4 primary ±1-day outcome-blind matchup pairs: {primary_count}"
    stale_legacy_numerals = re.search(r"\b(?:754|233)\b", normalized) is not None
    return required in normalized and not stale_legacy_numerals


def verify_output(root: Path, rebuild_comparison: dict | None = None) -> dict:
    gates: list[dict] = []
    required = [
        "daily_satellite_pixel_weighted_v4.csv", "matchup_pairs_v4.csv",
        "matchup_statistics_v4.csv", "endpoint_contrast_robustness_v4.csv",
        "bootstrap_draws_v4.csv.gz", "leave_one_weir_out_v4.csv",
        "zero_and_support_accounting_v4.csv", "observation_frequency_v4.csv",
        "crosswalk_accounting_v4.json", "study_area_map_v4.png",
        "study_area_map_metadata_v4.json", "study_area_map_sources_v4.md",
        "source_manifest_v4.json", "endpoint_construction_audit_v4.json",
        "reports/M3_matchups.md", "reports/M4_spatial.md", "reports/matchups_report.md",
    ]
    missing = [name for name in required if not (root / name).is_file()]
    _gate(gates, "required_artifacts", not missing, {"required_count": len(required), "missing": missing})
    if missing:
        return {"status": "FAIL", "gates": gates, "failures": ["required_artifacts"]}

    manifest = json.loads((root / "source_manifest_v4.json").read_text(encoding="utf-8"))
    manifest_hashes = {x["role"]: x["sha256"] for x in manifest["sources"]}
    actual_hashes = {role: sha256(path) for role, (_, path) in source_paths().items()}
    source_ok = manifest_hashes == EXPECTED_HASHES == actual_hashes
    _gate(gates, "source_hashes_and_freeze_identity", source_ok, {
        "source_count": len(actual_hashes), "freeze_sha256": actual_hashes["freeze"],
        "specification_sha256": actual_hashes["v4_specification"], "drift_roles": sorted(k for k in EXPECTED_HASHES if actual_hashes.get(k) != EXPECTED_HASHES[k]),
    })

    freeze = source_paths()["freeze"][1]
    packet = source_paths()["v4_specification"][1]
    generated = [root / name for name in required]
    freeze_order = packet.stat().st_mtime < freeze.stat().st_mtime < min(p.stat().st_mtime for p in generated)
    _gate(gates, "freeze_ordering", freeze_order, {
        "packet_mtime_epoch": packet.stat().st_mtime, "freeze_mtime_epoch": freeze.stat().st_mtime,
        "first_output_mtime_epoch": min(p.stat().st_mtime for p in generated),
    })

    daily = pd.read_csv(root / "daily_satellite_pixel_weighted_v4.csv")
    max_error = 0.0
    for index in INDICES:
        rebuilt = []
        for values, counts in zip(daily[f"{index}_component_values"], daily[f"{index}_component_counts"]):
            v = np.array([float(x) for x in str(values).split("|")])
            c = np.array([float(x) for x in str(counts).split("|")])
            rebuilt.append(float(np.dot(v, c) / c.sum()))
        max_error = max(max_error, float(np.max(np.abs(np.array(rebuilt) - daily[f"{index}_mean"].to_numpy()))))
    daily_ok = len(daily) == 1792 and not daily.duplicated(["site", "date"]).any() and max_error <= 1e-12
    _gate(gates, "pixel_weighted_daily_identity", daily_ok, {"rows": len(daily), "max_absolute_recalculation_error": max_error})

    pairs = pd.read_csv(root / "matchup_pairs_v4.csv", parse_dates=["in_situ_date"])
    bad_selection = 0
    daily_dates = {site: pd.to_datetime(g.date).sort_values() for site, g in daily.groupby("site")}
    for row in pairs.itertuples(index=False):
        chosen = pd.to_datetime(str(row.satellite_dates).split("|"))
        signed = np.array([int(x) for x in str(row.signed_lags).split("|")])
        candidates = daily_dates[row.site]
        minimum, expected = minimum_candidate_dates(candidates, row.in_situ_date, row.window_radius_days)
        actual = set(chosen.strftime("%Y-%m-%d"))
        if minimum != row.min_abs_lag or expected != actual or len(actual) != row.tie_count or not np.all(np.abs(signed) == minimum):
            bad_selection += 1
    pair_counts = pairs.groupby("window").size().to_dict()
    pair_ok = not pairs.duplicated(["window", "site", "in_situ_date"]).any() and bad_selection == 0
    _gate(gates, "outcome_blind_minimum_lag_and_symmetric_ties", pair_ok, {
        "total_pairs": len(pairs), "pairs_by_window": pair_counts, "bad_selections": bad_selection,
    })

    endpoint_audit = json.loads((root / "endpoint_construction_audit_v4.json").read_text(encoding="utf-8"))
    endpoint_ok = (
        endpoint_audit["chlorophyll_a"]["exact_filtered_rows"] == 6751
        and endpoint_audit["chlorophyll_a"]["exact_duplicates_removed"] == 3
        and endpoint_audit["harmful_cyanobacteria"]["exact_filtered_rows"] == 6748
        and endpoint_audit["harmful_cyanobacteria"]["exact_duplicates_removed"] == 3
    )
    _gate(gates, "exact_endpoint_filter_and_duplicate_audit", endpoint_ok, endpoint_audit)

    stats = pd.read_csv(root / "matchup_statistics_v4.csv")
    stat_numeric = ["association", "full_ci_low", "full_ci_high", "common_support_association", "common_ci_low", "common_ci_high", "delta_ci_low", "delta_ci_high"]
    finite_stats = bool(np.isfinite(stats[stat_numeric].to_numpy(dtype=float)).all())
    stats_ok = len(stats) == len(WINDOWS) * len(SPECIFICATIONS) * len(AGGREGATIONS) * len(INDICES) * len(ENDPOINTS) and finite_stats
    _gate(gates, "statistics_complete_and_finite", stats_ok, {
        "rows": len(stats), "expected_rows": 96, "minimum_common_weirs": int(stats.n_common_weirs.min()),
        "minimum_finite_bootstrap_draws": int(stats[["full_finite_draws", "common_finite_draws", "delta_finite_draws"]].min().min()),
    })

    draws = pd.read_csv(root / "bootstrap_draws_v4.csv.gz")
    group_counts = draws.groupby(["window", "specification", "aggregation", "index", "endpoint"]).size()
    draw_ok = (
        len(draws) == 288000 and group_counts.nunique() == 1 and group_counts.iloc[0] == 3000
        and np.isfinite(draws.loc[draws.estimable, "full_association"]).all()
        and (draws.selected_common_weirs_hash_chla == draws.selected_common_weirs_hash_cyano).all()
    )
    _gate(gates, "paired_weir_bootstrap_draws", bool(draw_ok), {
        "rows": len(draws), "analysis_cells": len(group_counts), "draws_per_cell": sorted(group_counts.unique().tolist()),
        "seed": manifest["bootstrap_seed"], "paired_common_hash_mismatches": int((draws.selected_common_weirs_hash_chla != draws.selected_common_weirs_hash_cyano).sum()),
    })

    robustness = pd.read_csv(root / "endpoint_contrast_robustness_v4.csv")
    placeholder = "0.05,-0.1,0.2" in (root / "endpoint_contrast_robustness_v4.csv").read_text().replace(" ", "")
    robust_ok = len(robustness) == 24 and not placeholder and set(robustness.global_endpoint_conclusion) == {"not_robust"}
    _gate(gates, "endpoint_contrast_robustness", robust_ok, {
        "rows": len(robustness), "placeholder_pattern_found": placeholder,
        "conclusion": sorted(robustness.global_endpoint_conclusion.unique().tolist()),
        "primary_pm1_delta_range": [float(robustness.query("window == 'pm1_2017_2025' and aggregation == 'equal_per_weir_fisher_z'").delta_r.min()), float(robustness.query("window == 'pm1_2017_2025' and aggregation == 'equal_per_weir_fisher_z'").delta_r.max())],
    })

    loo = pd.read_csv(root / "leave_one_weir_out_v4.csv")
    loo_groups = loo.groupby(["window", "specification", "aggregation", "index", "endpoint"])["omitted_weir"].nunique()
    loo_ok = len(loo) == 1536 and (loo_groups == 16).all() and loo.association.notna().any()
    _gate(gates, "leave_one_weir_out_coverage", bool(loo_ok), {
        "rows": len(loo), "analysis_cells": len(loo_groups), "omissions_per_cell": sorted(loo_groups.unique().tolist()),
        "finite_associations": int(np.isfinite(pd.to_numeric(loo.association, errors="coerce")).sum()),
    })

    frequency = pd.read_csv(root / "observation_frequency_v4.csv")
    original_scene = pd.read_csv(source_paths()["scene_v2"][1])
    expected_frequency = build_frequency(original_scene, sorted(frequency.site.unique()), range(2017, 2026))
    comparable = [c for c in frequency.columns if c not in ["median_gap_days", "max_gap_days"]]
    observed_frequency = frequency.sort_values(["site", "year"]).reset_index(drop=True)
    expected_frequency = expected_frequency.sort_values(["site", "year"]).reset_index(drop=True)
    recomputed_frequency_equal = True
    for column in comparable:
        if pd.api.types.is_numeric_dtype(observed_frequency[column]) and pd.api.types.is_numeric_dtype(expected_frequency[column]):
            same = np.allclose(observed_frequency[column], expected_frequency[column], rtol=0, atol=0, equal_nan=True)
        else:
            same = observed_frequency[column].fillna("NA").astype(str).equals(expected_frequency[column].fillna("NA").astype(str))
        recomputed_frequency_equal = recomputed_frequency_equal and bool(same)
    frequency_ok = (
        len(frequency) == 144 and frequency.site.nunique() == 16 and set(frequency.year) == set(range(2017, 2026))
        and recomputed_frequency_equal
        and frequency.query("year in [2017, 2018]").observed_low_coverage.all()
        and not frequency.archive_cause_verified.any()
    )
    _gate(gates, "observation_frequency_144_and_archive_boundary", bool(frequency_ok), {
        "rows": len(frequency), "sites": frequency.site.nunique(), "years": sorted(frequency.year.unique().tolist()),
        "site_dates_2017_2018": int(frequency.query("year in [2017, 2018]").satellite_site_dates.sum()),
        "site_dates_2019_2025": int(frequency.query("year >= 2019").satellite_site_dates.sum()),
    })

    support = pd.read_csv(root / "zero_and_support_accounting_v4.csv")
    support_ok = len(support) == 8 and (support.total_weirs == 16).all() and (support.endpoint_variable_weirs >= 2).all()
    _gate(gates, "zero_and_support_accounting", bool(support_ok), {
        "rows": len(support), "primary_zero_counts": support.query("window == 'pm1_2017_2025'").set_index("endpoint").zero_count.astype(int).to_dict(),
        "minimum_variable_weirs": int(support.endpoint_variable_weirs.min()),
    })

    crosswalk = json.loads((root / "crosswalk_accounting_v4.json").read_text(encoding="utf-8"))
    crosswalk_ok = crosswalk["total_rows"] == 32 and crosswalk["bucket_counts"] == {"context_only": 7, "exclude": 25} and crosswalk["direct_validation_allowed"] == 0 and crosswalk["directed_network_available"] == 0
    _gate(gates, "crosswalk_closure", crosswalk_ok, crosswalk)

    map_meta = json.loads((root / "study_area_map_metadata_v4.json").read_text(encoding="utf-8"))
    with Image.open(root / "study_area_map_v4.png") as image:
        dimensions = image.size
    map_ok = map_meta["weir_count"] == 16 and map_meta["control_count"] == 16 and map_meta["buffer_radius_m"] == 5000 and map_meta["crs"] == "EPSG:5179" and min(dimensions) >= 2000
    _gate(gates, "map_features_provenance_and_visual_inspection", map_ok, {
        "dimensions_pixels": list(dimensions), "weirs": map_meta["weir_count"], "controls": map_meta["control_count"],
        "buffer_radius_m": map_meta["buffer_radius_m"], "crs": map_meta["crs"],
        "manual_visual_inspection": "readable target/control symbols, labels, legend, scale bar, north arrow, four-river colors, and Korea inset confirmed",
    })

    text_paths = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".csv", ".json", ".md"}]
    scan_failures = scan_submission_text(text_paths)
    _gate(gates, "relative_paths_secrets_and_semantics", not scan_failures, {"files_scanned": len(text_paths), "failures": scan_failures})

    joined_reports = "\n".join((root / f"reports/{name}").read_text(encoding="utf-8") for name in ["M3_matchups.md", "M4_spatial.md", "matchups_report.md"])
    normalized_reports = re.sub(r"\s+", " ", joined_reports).lower()
    limitations = ["dedicated cloud-shadow", "QA60 nominal support is 60 m", "5-km cross-weir buffer can mix upstream lentic and downstream lotic water"]
    primary_count = int(pair_counts["pm1_2017_2025"])
    support_semantics_ok = report_support_semantics(joined_reports, primary_count)
    report_ok = all(term.lower() in normalized_reports for term in limitations) and "not_robust" in normalized_reports and support_semantics_ok
    _gate(gates, "reports_adverse_result_limitations_and_v4_support", report_ok, {
        "required_phrases": limitations, "endpoint_conclusion": "not_robust",
        "primary_pair_count_derived_from_matchup_table": primary_count,
        "report_support_semantics_pass": support_semantics_ok,
        "legacy_754_or_233_present": bool(re.search(r"\b(?:754|233)\b", normalized_reports)),
    })

    if rebuild_comparison is not None:
        compare_ok = rebuild_comparison.get("status") == "pass" and rebuild_comparison.get("mismatches") == []
        _gate(gates, "second_clean_rebuild", compare_ok, {
            "compared_files": rebuild_comparison.get("compared_files"), "mismatches": rebuild_comparison.get("mismatches"),
            "declared_exclusions": rebuild_comparison.get("declared_exclusions", []),
        })

    failures = [g["name"] for g in gates if g["status"] != "pass"]
    return {
        "status": "COMPLETE_VERIFIED_V4" if not failures and rebuild_comparison is not None else "FAIL",
        "named_gate_count": len(gates), "gates": gates, "failures": failures,
        "verification_scope": "scientific construction, cluster inference, LOO, frequency, crosswalk, map, provenance, semantics, and deterministic clean rebuild",
    }
