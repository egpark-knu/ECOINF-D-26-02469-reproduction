"""Fresh matchups v4 data construction and dependence-aware estimators."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


WINDOWS = {
    "pm1_2017_2025": (1, 2017, 2025),
    "pm2_2017_2025": (2, 2017, 2025),
    "pm3_2017_2025": (3, 2017, 2025),
    "pm1_2019_2025": (1, 2019, 2025),
}
SPECIFICATIONS = (
    "raw_within_weir_pearson",
    "within_weir_percentile_midrank",
    "site_by_calendar_month_pearson",
)
AGGREGATIONS = ("equal_per_weir_fisher_z", "equal_per_observation")
INDICES = ("ndci", "fai")
ENDPOINTS = ("chlorophyll_a", "harmful_cyanobacteria")


def _joined(values: Iterable[object]) -> str:
    return "|".join(str(x) for x in values)


def _finite_number(series: pd.Series, name: str) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce")
    invalid = series.notna() & out.isna()
    if invalid.any():
        raise ValueError(f"non-numeric {name}: {int(invalid.sum())}")
    return out


def aggregate_daily_satellite(scene: pd.DataFrame) -> pd.DataFrame:
    required = {
        "site", "date", "scene_id", "PRODUCT_ID", "MGRS_TILE", "utc_timestamp",
        "ndci_mean", "ndci_count", "fai_mean", "fai_count",
    }
    missing = required - set(scene.columns)
    if missing:
        raise ValueError(f"scene schema missing: {sorted(missing)}")
    x = scene.copy()
    x["date"] = pd.to_datetime(x["date"], errors="raise")
    identity = ["site", "date", "scene_id", "PRODUCT_ID", "MGRS_TILE"]
    if x.duplicated(identity).any():
        raise ValueError("duplicate satellite identity")
    for index in INDICES:
        x[f"{index}_mean"] = _finite_number(x[f"{index}_mean"], f"{index}_mean")
        x[f"{index}_count"] = _finite_number(x[f"{index}_count"], f"{index}_count")
        if x[f"{index}_mean"].isna().any() or x[f"{index}_count"].isna().any():
            raise ValueError(f"missing {index} value/count")
        if (x[f"{index}_count"] <= 0).any():
            raise ValueError(f"nonpositive {index} count")

    rows = []
    for (site, date), group in x.groupby(["site", "date"], sort=True):
        row = {
            "site": site,
            "date": date,
            "component_rows": len(group),
            "scene_ids": _joined(group["scene_id"]),
            "product_ids": _joined(group["PRODUCT_ID"]),
            "tiles": _joined(group["MGRS_TILE"]),
            "utc_timestamps": _joined(group["utc_timestamp"]),
        }
        for index in INDICES:
            count = group[f"{index}_count"].astype(float)
            value = group[f"{index}_mean"].astype(float)
            numerator = float((count * value).sum())
            denominator = float(count.sum())
            row[f"{index}_component_values"] = _joined(value.map(lambda v: f"{v:.17g}"))
            row[f"{index}_component_counts"] = _joined(count.map(lambda v: f"{v:.17g}"))
            row[f"{index}_weighted_numerator"] = numerator
            row[f"{index}_valid_pixels"] = denominator
            row[f"{index}_mean"] = numerator / denominator
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.duplicated(["site", "date"]).any():
        raise AssertionError("daily composite not unique")
    return result


def endpoint_panel(
    raw: pd.DataFrame,
    variable: str,
    source_field: str,
    unit: str,
    weir_to_site: dict[str, str],
) -> tuple[pd.DataFrame, dict]:
    required = {
        "station_code", "station_name", "weir_name", "sampling_date", "variable",
        "source_field", "value", "unit", "source_row_locator", "raw_snapshot_sha256",
    }
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"in-situ schema missing: {sorted(missing)}")
    x = raw.loc[
        (raw["variable"] == variable)
        & (raw["source_field"] == source_field)
        & (raw["unit"] == unit)
    ].copy()
    if x.empty:
        raise ValueError(f"no rows for exact endpoint {variable}/{source_field}/{unit}")
    x["sampling_date"] = pd.to_datetime(x["sampling_date"], errors="raise")
    x["value"] = _finite_number(x["value"], variable)
    if (x["value"].dropna() < 0).any():
        raise ValueError(f"negative {variable}")
    duplicate_key = ["station_code", "sampling_date", "variable"]
    dup = x.duplicated(duplicate_key, keep=False)
    for _, group in x.loc[dup].groupby(duplicate_key, dropna=False, sort=False):
        compare = [c for c in x.columns if c != "source_row_locator"]
        if any(group[c].nunique(dropna=False) > 1 for c in compare):
            raise ValueError(f"conflicting duplicate endpoint record: {variable}")
    before = len(x)
    x = x.sort_values(duplicate_key + ["source_row_locator"], kind="mergesort")
    x = x.drop_duplicates(duplicate_key, keep="first")
    removed = before - len(x)
    x["site"] = x["weir_name"].map(weir_to_site)
    if x["site"].isna().any():
        bad = sorted(x.loc[x["site"].isna(), "weir_name"].astype(str).unique())
        raise ValueError(f"endpoint weir not in inventory: {bad}")
    output_name = "harmful_cyanobacteria" if variable == "harmful_cyanobacteria_total" else variable
    rows = []
    for (site, date), group in x.groupby(["site", "sampling_date"], sort=True):
        rows.append(
            {
                "site": site,
                "in_situ_date": date,
                output_name: float(group["value"].mean()) if group["value"].notna().any() else np.nan,
                f"{output_name}_station_count": int(group["station_code"].nunique()),
                f"{output_name}_station_codes": _joined(sorted(group["station_code"].astype(str).unique())),
                f"{output_name}_source_row_locators": _joined(group["source_row_locator"]),
                f"{output_name}_source_snapshot_hashes": _joined(sorted(group["raw_snapshot_sha256"].astype(str).unique())),
            }
        )
    out = pd.DataFrame(rows)
    if out.duplicated(["site", "in_situ_date"]).any():
        raise AssertionError("endpoint aggregation not unique")
    audit = {
        "endpoint": output_name,
        "exact_filtered_rows": before,
        "exact_duplicates_removed": removed,
        "deduplicated_rows": len(x),
        "aggregated_site_dates": len(out),
        "missing_values": int(x["value"].isna().sum()),
        "zero_values": int((x["value"] == 0).sum()),
        "weirs": int(x["site"].nunique()),
    }
    return out, audit


def combine_endpoints(chla: pd.DataFrame, cyano: pd.DataFrame) -> pd.DataFrame:
    out = chla.merge(cyano, on=["site", "in_situ_date"], how="outer", validate="one_to_one")
    return out.sort_values(["site", "in_situ_date"]).reset_index(drop=True)


def build_matchups(
    daily: pd.DataFrame,
    insitu: pd.DataFrame,
    windows: dict[str, tuple[int, int, int]] = WINDOWS,
) -> pd.DataFrame:
    sat = daily.copy()
    sat["date"] = pd.to_datetime(sat["date"], errors="raise")
    obs = insitu.copy()
    obs["in_situ_date"] = pd.to_datetime(obs["in_situ_date"], errors="raise")
    rows = []
    by_site = {site: g.sort_values("date") for site, g in sat.groupby("site")}
    for window, (radius, start, end) in windows.items():
        eligible_obs = obs[obs["in_situ_date"].dt.year.between(start, end)]
        for _, endpoint_row in eligible_obs.iterrows():
            site = endpoint_row["site"]
            candidates = by_site.get(site)
            if candidates is None:
                continue
            lag = (candidates["date"] - endpoint_row["in_situ_date"]).dt.days
            within = candidates.loc[lag.abs() <= radius].copy()
            if within.empty:
                continue
            within["signed_lag"] = (within["date"] - endpoint_row["in_situ_date"]).dt.days
            min_abs = int(within["signed_lag"].abs().min())
            tied = within[within["signed_lag"].abs() == min_abs].sort_values("date")
            row = endpoint_row.to_dict()
            row.update(
                {
                    "window": window,
                    "window_radius_days": radius,
                    "window_start_year": start,
                    "window_end_year": end,
                    "satellite_dates": _joined(tied["date"].dt.strftime("%Y-%m-%d")),
                    "signed_lags": _joined(tied["signed_lag"]),
                    "min_abs_lag": min_abs,
                    "tie_count": len(tied),
                    "satellite_component_rows": int(tied["component_rows"].sum()),
                    "scene_ids": _joined(tied["scene_ids"]),
                    "product_ids": _joined(tied["product_ids"]),
                    "tiles": _joined(tied["tiles"]),
                    "utc_timestamps": _joined(tied["utc_timestamps"]),
                }
            )
            for index in INDICES:
                weights = tied[f"{index}_valid_pixels"].astype(float)
                values = tied[f"{index}_mean"].astype(float)
                row[f"{index}_valid_pixels"] = float(weights.sum())
                row[f"{index}_weighted_numerator"] = float((weights * values).sum())
                row[f"{index}_mean"] = row[f"{index}_weighted_numerator"] / row[f"{index}_valid_pixels"]
            rows.append(row)
    out = pd.DataFrame(rows)
    if not out.empty and out.duplicated(["window", "site", "in_situ_date"]).any():
        raise AssertionError("matchup pairs are not unique")
    return out.sort_values(["window", "site", "in_situ_date"]).reset_index(drop=True)


def percentile_midrank(values: pd.Series) -> pd.Series:
    return values.rank(method="average") / (values.notna().sum() + 1.0)


@dataclass
class PreparedEndpoint:
    data: pd.DataFrame
    eligible_sites: list[str]
    site_correlations: dict[str, float]
    site_moments: dict[str, tuple[float, float, float, float, float, float]]
    cell_diagnostics: dict[str, float]


def prepare_endpoint(
    pairs: pd.DataFrame,
    window: str,
    index: str,
    endpoint: str,
    specification: str,
) -> PreparedEndpoint:
    cols = ["site", "in_situ_date", f"{index}_mean", endpoint]
    x = pairs.loc[pairs["window"] == window, cols].dropna().copy()
    x = x.rename(columns={f"{index}_mean": "predictor", endpoint: "outcome"})
    x["outcome"] = np.log1p(x["outcome"].astype(float))
    x["predictor"] = x["predictor"].astype(float)
    x["calendar_month"] = pd.to_datetime(x["in_situ_date"]).dt.month
    if specification == "raw_within_weir_pearson":
        x["x_t"] = x["predictor"] - x.groupby("site")["predictor"].transform("mean")
        x["y_t"] = x["outcome"] - x.groupby("site")["outcome"].transform("mean")
    elif specification == "within_weir_percentile_midrank":
        x["x_t"] = x.groupby("site", group_keys=False)["predictor"].transform(percentile_midrank)
        x["y_t"] = x.groupby("site", group_keys=False)["outcome"].transform(percentile_midrank)
    elif specification == "site_by_calendar_month_pearson":
        cells = x.groupby(["site", "calendar_month"])
        x["x_t"] = x["predictor"] - cells["predictor"].transform("mean")
        x["y_t"] = x["outcome"] - cells["outcome"].transform("mean")
    else:
        raise ValueError(f"unknown specification: {specification}")

    site_r = {}
    site_moments = {}
    for site, group in x.groupby("site", sort=True):
        if len(group) >= 2 and group["x_t"].nunique() > 1 and group["y_t"].nunique() > 1:
            r = float(group["x_t"].corr(group["y_t"]))
            if np.isfinite(r):
                site_r[str(site)] = r
                xv = group["x_t"].to_numpy(dtype=float)
                yv = group["y_t"].to_numpy(dtype=float)
                site_moments[str(site)] = (
                    float(len(group)), float(xv.sum()), float(yv.sum()),
                    float(np.dot(xv, xv)), float(np.dot(yv, yv)), float(np.dot(xv, yv)),
                )
    cell_sizes = x.groupby(["site", "calendar_month"]).size()
    diagnostics = {
        "n_rows": int(len(x)),
        "n_cells": int(len(cell_sizes)),
        "singleton_cells": int((cell_sizes == 1).sum()),
        "cells_le_2": int((cell_sizes <= 2).sum()),
        "median_cell_size": float(cell_sizes.median()) if len(cell_sizes) else np.nan,
    }
    return PreparedEndpoint(x, sorted(site_r), site_r, site_moments, diagnostics)


def _sequence_hash(sites: Iterable[str]) -> str:
    return hashlib.sha256("\x1f".join(sites).encode("utf-8")).hexdigest()


def _correlation_from_rows(data: pd.DataFrame) -> float:
    if len(data) < 2 or data["x_t"].nunique() < 2 or data["y_t"].nunique() < 2:
        return np.nan
    return float(data["x_t"].corr(data["y_t"]))


def association(prepared: PreparedEndpoint, aggregation: str, selected_sites: list[str] | None = None) -> float:
    sites = prepared.eligible_sites if selected_sites is None else list(selected_sites)
    if not sites:
        return np.nan
    if aggregation == "equal_per_weir_fisher_z":
        r = np.array([prepared.site_correlations[s] for s in sites if s in prepared.site_correlations], dtype=float)
        if not len(r):
            return np.nan
        return float(np.tanh(np.mean(np.arctanh(np.clip(r, -1 + 1e-12, 1 - 1e-12)))))
    if aggregation == "equal_per_observation":
        moments = [prepared.site_moments[site] for site in sites if site in prepared.site_moments]
        if not moments:
            return np.nan
        n, sx, sy, sxx, syy, sxy = np.asarray(moments, dtype=float).sum(axis=0)
        if n < 2:
            return np.nan
        x_ss = sxx - sx * sx / n
        y_ss = syy - sy * sy / n
        denominator = np.sqrt(max(0.0, x_ss) * max(0.0, y_ss))
        if denominator <= 0:
            return np.nan
        return float((sxy - sx * sy / n) / denominator)
    raise ValueError(f"unknown aggregation: {aggregation}")


def _bootstrap_config(
    pairs: pd.DataFrame,
    window: str,
    specification: str,
    aggregation: str,
    index: str,
    b: int,
    rng: np.random.Generator,
) -> list[dict]:
    prepared = {
        endpoint: prepare_endpoint(pairs, window, index, endpoint, specification)
        for endpoint in ENDPOINTS
    }
    common = sorted(set(prepared[ENDPOINTS[0]].eligible_sites) & set(prepared[ENDPOINTS[1]].eligible_sites))
    records = []
    for draw in range(1, b + 1):
        selected_full = {}
        selected_common = list(rng.choice(common, size=len(common), replace=True)) if common else []
        common_values = {
            endpoint: association(prepared[endpoint], aggregation, selected_common)
            for endpoint in ENDPOINTS
        }
        delta = common_values["chlorophyll_a"] - common_values["harmful_cyanobacteria"]
        if not np.isfinite(delta):
            delta = np.nan
        common_hash = _sequence_hash(selected_common)
        for endpoint in ENDPOINTS:
            eligible = prepared[endpoint].eligible_sites
            selected_full[endpoint] = list(rng.choice(eligible, size=len(eligible), replace=True)) if eligible else []
            full = association(prepared[endpoint], aggregation, selected_full[endpoint])
            records.append(
                {
                    "draw": draw,
                    "window": window,
                    "specification": specification,
                    "aggregation": aggregation,
                    "index": index,
                    "endpoint": endpoint,
                    "full_association": full,
                    "common_support_association": common_values[endpoint],
                    "paired_delta": delta,
                    "n_full_support_weirs": len(eligible),
                    "n_common_weirs": len(common),
                    "selected_full_weirs_hash": _sequence_hash(selected_full[endpoint]),
                    "selected_common_weirs_hash_chla": common_hash,
                    "selected_common_weirs_hash_cyano": common_hash,
                    "estimable": bool(np.isfinite(full)),
                }
            )
    return records


def _percentile_ci(values: pd.Series) -> tuple[float, float, int]:
    finite = pd.to_numeric(values, errors="coerce")
    finite = finite[np.isfinite(finite)]
    if finite.empty:
        return np.nan, np.nan, 0
    lo, hi = np.percentile(finite, [2.5, 97.5])
    return float(lo), float(hi), int(len(finite))


def run_bootstrap(
    pairs: pd.DataFrame,
    windows: Iterable[str] | None = None,
    b: int = 3000,
    seed: int = 20260815,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    use_windows = list(WINDOWS if windows is None else windows)
    rng = np.random.default_rng(seed)
    records = []
    for window in use_windows:
        for specification in SPECIFICATIONS:
            for aggregation in AGGREGATIONS:
                for index in INDICES:
                    records.extend(_bootstrap_config(pairs, window, specification, aggregation, index, b, rng))
    draws = pd.DataFrame(records)
    summaries = []
    keys = ["window", "specification", "aggregation", "index", "endpoint"]
    for key, group in draws.groupby(keys, sort=True):
        full_lo, full_hi, full_n = _percentile_ci(group["full_association"])
        common_lo, common_hi, common_n = _percentile_ci(group["common_support_association"])
        delta_lo, delta_hi, delta_n = _percentile_ci(group["paired_delta"])
        summaries.append(
            dict(
                zip(keys, key),
                full_ci_low=full_lo,
                full_ci_high=full_hi,
                full_finite_draws=full_n,
                common_ci_low=common_lo,
                common_ci_high=common_hi,
                common_finite_draws=common_n,
                delta_ci_low=delta_lo,
                delta_ci_high=delta_hi,
                delta_finite_draws=delta_n,
                bootstrap_draws=b,
                bootstrap_seed=seed,
                p_method="not_computed_ci_primary",
            )
        )
    return draws, pd.DataFrame(summaries)


def point_statistics(pairs: pd.DataFrame, windows: Iterable[str] | None = None) -> pd.DataFrame:
    use_windows = list(WINDOWS if windows is None else windows)
    rows = []
    for window in use_windows:
        for specification in SPECIFICATIONS:
            for aggregation in AGGREGATIONS:
                for index in INDICES:
                    prepared = {
                        endpoint: prepare_endpoint(pairs, window, index, endpoint, specification)
                        for endpoint in ENDPOINTS
                    }
                    common = sorted(set(prepared[ENDPOINTS[0]].eligible_sites) & set(prepared[ENDPOINTS[1]].eligible_sites))
                    common_r = {endpoint: association(prepared[endpoint], aggregation, common) for endpoint in ENDPOINTS}
                    delta = common_r["chlorophyll_a"] - common_r["harmful_cyanobacteria"]
                    for endpoint in ENDPOINTS:
                        p = prepared[endpoint]
                        rows.append(
                            {
                                "window": window,
                                "specification": specification,
                                "aggregation": aggregation,
                                "index": index,
                                "endpoint": endpoint,
                                "association": association(p, aggregation),
                                "common_support_association": common_r[endpoint],
                                "paired_delta_chla_minus_cyano": delta,
                                "n_rows": len(p.data),
                                "n_estimable_weirs": len(p.eligible_sites),
                                "n_common_weirs": len(common),
                                **p.cell_diagnostics,
                            }
                        )
    return pd.DataFrame(rows)


def run_leave_one_out(
    pairs: pd.DataFrame,
    windows: Iterable[str] | None = None,
    all_sites: Iterable[str] | None = None,
) -> pd.DataFrame:
    use_windows = list(WINDOWS if windows is None else windows)
    sites = sorted(pairs["site"].unique() if all_sites is None else all_sites)
    rows = []
    for window in use_windows:
        for specification in SPECIFICATIONS:
            for aggregation in AGGREGATIONS:
                for index in INDICES:
                    prepared = {
                        endpoint: prepare_endpoint(pairs, window, index, endpoint, specification)
                        for endpoint in ENDPOINTS
                    }
                    for omitted in sites:
                        eligible_after = {
                            endpoint: [s for s in prepared[endpoint].eligible_sites if s != omitted]
                            for endpoint in ENDPOINTS
                        }
                        common = sorted(set(eligible_after[ENDPOINTS[0]]) & set(eligible_after[ENDPOINTS[1]]))
                        common_r = {endpoint: association(prepared[endpoint], aggregation, common) for endpoint in ENDPOINTS}
                        delta = common_r["chlorophyll_a"] - common_r["harmful_cyanobacteria"]
                        for endpoint in ENDPOINTS:
                            value = association(prepared[endpoint], aggregation, eligible_after[endpoint])
                            rows.append(
                                {
                                    "window": window,
                                    "specification": specification,
                                    "aggregation": aggregation,
                                    "index": index,
                                    "endpoint": endpoint,
                                    "omitted_weir": omitted,
                                    "association": value,
                                    "estimable": bool(np.isfinite(value)),
                                    "n_estimable_weirs": len(eligible_after[endpoint]),
                                    "n_common_weirs": len(common),
                                    "common_support_association": common_r[endpoint],
                                    "paired_delta_chla_minus_cyano": delta if index == "ndci" else np.nan,
                                    "is_endpoint_contrast": bool(index == "ndci"),
                                }
                            )
    return pd.DataFrame(rows)


def build_frequency(scene: pd.DataFrame, sites: Iterable[str], years: Iterable[int]) -> pd.DataFrame:
    x = scene.copy()
    x["date"] = pd.to_datetime(x["date"], errors="raise")
    if "year" not in x:
        x["year"] = x["date"].dt.year
    rows = []
    for site in sites:
        for year in years:
            group = x[(x["site"] == site) & (x["year"] == year)].copy()
            dates = sorted(group["date"].drop_duplicates())
            gaps = np.diff(np.array(dates, dtype="datetime64[D]")).astype(int) if len(dates) > 1 else np.array([])
            rows.append(
                {
                    "site": site,
                    "year": year,
                    "satellite_site_dates": len(dates),
                    "scene_components": len(group),
                    "unique_scenes": int(group["scene_id"].nunique()) if len(group) else 0,
                    "unique_products": int(group["PRODUCT_ID"].nunique()) if len(group) else 0,
                    "unique_tiles": int(group["MGRS_TILE"].nunique()) if len(group) else 0,
                    "ndci_valid_pixel_sum": float(group["ndci_count"].sum()) if len(group) else 0.0,
                    "fai_valid_pixel_sum": float(group["fai_count"].sum()) if len(group) else 0.0,
                    "median_gap_days": float(np.median(gaps)) if len(gaps) else np.nan,
                    "max_gap_days": float(np.max(gaps)) if len(gaps) else np.nan,
                    "observed_low_coverage": bool(year in (2017, 2018)),
                    "archive_cause_verified": False,
                    "accounting_period": "2017_2025" if year < 2019 else "2017_2025_and_2019_2025_sensitivity",
                }
            )
    return pd.DataFrame(rows)


def crosswalk_accounting(crosswalk: pd.DataFrame) -> dict:
    buckets = crosswalk["direct_validation_bucket_v6"].value_counts().sort_index().to_dict()
    truthy = lambda s: s.astype(str).str.lower().isin(["true", "1", "yes"]).sum()
    result = {
        "total_rows": int(len(crosswalk)),
        "bucket_counts": {str(k): int(v) for k, v in buckets.items()},
        "direct_validation_allowed": int(truthy(crosswalk["direct_validation_claim_allowed_v6"])),
        "directed_network_available": int(truthy(crosswalk["directed_network_available_v6"])),
        "interpretation": "negative direct-validation closure; not proof of hydrologic non-connection",
    }
    expected = {
        "total_rows": 32,
        "bucket_counts": {"context_only": 7, "exclude": 25},
        "direct_validation_allowed": 0,
        "directed_network_available": 0,
    }
    for key, value in expected.items():
        if result[key] != value:
            raise ValueError(f"crosswalk closure mismatch for {key}: {result[key]!r} != {value!r}")
    return result


def support_accounting(pairs: pd.DataFrame, all_sites: Iterable[str]) -> pd.DataFrame:
    rows = []
    for window, group in pairs.groupby("window", sort=True):
        for endpoint in ENDPOINTS:
            endpoint_rows = group[group[endpoint].notna()]
            variable_sites = []
            zero_variance = []
            for site, site_group in endpoint_rows.groupby("site"):
                if site_group[endpoint].nunique() > 1:
                    variable_sites.append(site)
                else:
                    zero_variance.append(site)
            rows.append(
                {
                    "window": window,
                    "endpoint": endpoint,
                    "matched_rows": len(group),
                    "complete_case_rows": len(endpoint_rows),
                    "total_weirs": len(list(all_sites)),
                    "endpoint_observed_weirs": endpoint_rows["site"].nunique(),
                    "endpoint_variable_weirs": len(variable_sites),
                    "zero_variance_weirs": _joined(sorted(zero_variance)),
                    "zero_count": int((endpoint_rows[endpoint] == 0).sum()),
                    "zero_fraction": float((endpoint_rows[endpoint] == 0).mean()) if len(endpoint_rows) else np.nan,
                }
            )
    return pd.DataFrame(rows)
