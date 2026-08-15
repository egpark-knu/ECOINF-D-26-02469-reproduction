"""Fail-closed chronology eligibility and bounded late-post comparator helpers."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd


def _treated_mask(values: pd.Series) -> pd.Series:
    return values.astype(str).isin({"treated", "documented_opened_examples"})


def chronology_eligibility(
    events: pd.DataFrame,
    coverage: pd.DataFrame,
    gaps: pd.DataFrame,
    panel: pd.DataFrame,
) -> dict:
    """Apply the frozen exact-sequence and within-basin eligibility rule."""
    weirs = sorted(panel["weir_name"].astype(str).dropna().unique().tolist())
    event_by_weir = {key: value.copy() for key, value in events.groupby("weir_name")}
    coverage_by_weir = coverage.set_index("weir_name", drop=False)
    gap_by_weir = {key: value.copy() for key, value in gaps.groupby("weir_name")}
    unresolved: list[str] = []
    detail: list[dict] = []

    for weir in weirs:
        event_rows = event_by_weir.get(weir, pd.DataFrame())
        cov = coverage_by_weir.loc[weir] if weir in coverage_by_weir.index else None
        gap_rows = gap_by_weir.get(weir, pd.DataFrame())
        exact_complete = False
        if not event_rows.empty:
            exact = event_rows["date_precision"].astype(str).str.startswith("exact")
            complete = event_rows["start_date"].astype(str).ne("") & event_rows["end_date"].astype(str).ne("")
            final = event_rows["analysis_usable"].astype(str).eq("final_sequence")
            exact_complete = bool((exact & complete & final).any())
        coverage_final = bool(
            cov is not None
            and str(cov.get("current_best_status", "")) == "final_sequence"
            and str(cov.get("final_timeline_blocker", "")) == ""
        )
        expected_years = set(range(2017, 2026))
        gap_years = set(pd.to_numeric(gap_rows.get("year", pd.Series(dtype=float)), errors="coerce").dropna().astype(int))
        gap_final = bool(
            gap_years == expected_years
            and not gap_rows.empty
            and gap_rows["audit_status"].astype(str).eq("final_daily_sequence").all()
            and gap_rows["analysis_use"].astype(str).eq("event_time_ready").all()
        )
        resolved = exact_complete and coverage_final and gap_final
        if not resolved:
            unresolved.append(weir)
        detail.append(
            {
                "weir_name": weir,
                "exact_complete_event": exact_complete,
                "coverage_final": coverage_final,
                "gap_2017_2025_final": gap_final,
                "resolved": resolved,
            }
        )

    unit = panel[["weir_name", "river", "gate0_group"]].drop_duplicates("weir_name")
    unit = unit.assign(treated=_treated_mask(unit["gate0_group"]))
    basin_counts = (
        unit.groupby(["river", "treated"]).size().unstack(fill_value=0).rename(columns={False: "control", True: "treated"})
    )
    within_basin = bool(
        not basin_counts.empty
        and "control" in basin_counts.columns
        and "treated" in basin_counts.columns
        and ((basin_counts["control"] > 0) & (basin_counts["treated"] > 0)).any()
    )
    reasons: list[str] = []
    if unresolved:
        reasons.append("incomplete_exact_2017_2025_treatment_sequences")
    if not within_basin:
        reasons.append("no_within_basin_treated_control_variation")
    return {
        "eligible": not reasons,
        "failure_reasons": reasons,
        "unresolved_weirs": unresolved,
        "n_weirs": len(weirs),
        "n_resolved": len(weirs) - len(unresolved),
        "within_basin_variation": within_basin,
        "basin_counts": basin_counts.reset_index().to_dict("records"),
        "weir_detail": detail,
    }


def legacy_late_post_comparator(panel: pd.DataFrame) -> pd.DataFrame:
    """Recompute only the frozen 2017/2018/2019-25 legacy comparator point estimates."""
    outcomes = [
        "log1p_harmful_cyanobacteria_total_mean",
        "log1p_chlorophyll_a_mean",
    ]
    rows: list[dict] = []
    for season, frame in panel.groupby("season_scope", sort=True):
        frame = frame.copy()
        frame["treated"] = _treated_mask(frame["gate0_group"]).astype(int)
        for outcome in outcomes:
            base = frame.loc[frame["year"] == 2017].groupby("treated")[outcome].mean()
            immediate = frame.loc[frame["year"] == 2018].groupby("treated")[outcome].mean()
            late = frame.loc[frame["year"] >= 2019].groupby("treated")[outcome].mean()
            if set(base.index) != {0, 1} or set(immediate.index) != {0, 1} or set(late.index) != {0, 1}:
                raise ValueError("legacy comparator lacks both groups")
            rows.append(
                {
                    "season_scope": season,
                    "outcome": outcome,
                    "n_treated_weirs": int(frame.loc[frame["treated"] == 1, "weir_name"].nunique()),
                    "n_comparison_or_unresolved_weirs": int(frame.loc[frame["treated"] == 0, "weir_name"].nunique()),
                    "did_2018_vs_2017": float((immediate[1] - base[1]) - (immediate[0] - base[0])),
                    "did_late_2019_2025_vs_2017": float((late[1] - base[1]) - (late[0] - base[0])),
                    "role": "legacy_cross_basin_comparator_not_event_study",
                }
            )
    return pd.DataFrame(rows)
