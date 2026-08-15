#!/usr/bin/env python3
"""Render the M1 reconciliation reconciliation report from independently verified artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd


SEASONS = ["annual_all_samples", "bloom_season_06_10"]
LABELS = {
    "annual_all_samples": "Annual",
    "bloom_season_06_10": "Bloom season (Jun–Oct)",
}


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def format_p(value: float) -> str:
    return f"{value:.6f}" if value >= 0.0001 else f"{value:.3e}"


def render(run_root: Path, output: Path) -> None:
    if not (run_root / "COMPLETE.json").is_file():
        raise ValueError("verified COMPLETE.json is required before reporting")
    verification = json.loads((run_root / "verification.json").read_text(encoding="utf-8"))
    if verification.get("status") != "PASS":
        raise ValueError("verification did not pass")
    input_audit = json.loads((run_root / "input_audit.json").read_text(encoding="utf-8"))
    design_audit = json.loads((run_root / "design_audit.json").read_text(encoding="utf-8"))
    defect_audit = json.loads(
        (run_root / "legacy_cluster_se_defect_audit.json").read_text(encoding="utf-8")
    )
    legacy_models = pd.read_csv(run_root / "legacy/standardized_tau_models.csv")
    legacy_interactions = pd.read_csv(run_root / "legacy/specificity_interaction.csv")
    contrasts = pd.read_csv(run_root / "endpoint_specific_contrasts.csv")
    matrix = pd.read_csv(run_root / "specification_matrix.csv")
    bloom_defect = {
        row["outcome"]: row
        for row in defect_audit["records"]
        if row["season_scope"] == "bloom_season_06_10"
    }

    annual = contrasts.loc[contrasts["season_scope"] == "annual_all_samples"].iloc[0]
    d1_trigger = bool(
        float(annual["delta_endpoint_specific_stacked"]) <= 0
        or float(annual["wcr_p_holm"]) > 0.05
    )
    verdict = "WEAKENS_OR_REDIRECTS" if d1_trigger else "SUPPORTS"
    claim_impact = (
        "Direction is preserved, but the prespecified direct annual comparison loses formal support; "
        "the specificity claim's inferential strength changes."
        if d1_trigger
        else "Direction and formal annual support are preserved under the endpoint-specific comparison, while the numeric estimand changes."
    )

    lines = [
        "# M1 Residence-Time Reconciliation — M1 reconciliation",
        "",
        f"- Protocol: `P2a_M1_v1`",
        f"- Verified run: `{run_root.name}`",
        f"- Verification: `{run_root / 'verification.json'}` (`PASS`)",
        f"- Artifact hashes: `{run_root / 'artifact_hashes.sha256'}`",
        "",
        "## Exact reproduction",
        "",
        "The byte-frozen historical code and panel reproduced all prespecified coefficients, intervals, p-values, row counts, and the 4,999-permutation targets within the frozen tolerance.",
        "",
        "| Season | Legacy separate cyano | Legacy separate chlorophyll-a | Arithmetic difference | Submitted δ_common | δ_common minus difference |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for season in SEASONS:
        primary = legacy_models[
            (legacy_models["model_family"] == "z_standardized_log1p_outcome")
            & (legacy_models["season_scope"] == season)
        ]
        cyano = float(primary.loc[primary["outcome"] == "cyano", "beta_log1p_tau"].iloc[0])
        chla = float(primary.loc[primary["outcome"] == "chlorophyll_a", "beta_log1p_tau"].iloc[0])
        difference = cyano - chla
        common = float(legacy_interactions.loc[
            legacy_interactions["season_scope"] == season,
            "interaction_beta_cyano_minus_chla",
        ].iloc[0])
        lines.append(
            f"| {LABELS[season]} | {cyano:.12f} | {chla:.12f} | {difference:.12f} | {common:.12f} | {common - difference:.12f} |"
        )

    lines.extend([
        "",
        "`δ_common` is the interaction in a pooled model that constrains weir and year nuisance effects to be common across endpoints. It is not the arithmetic difference of two separately fitted endpoint-specific TWFE slopes.",
        "",
        "## Estimand and direct-test correction",
        "",
        "Submitted/common-FE model:",
        "",
        "```text",
        "z_ite = α + β_H x_it + γ C_e + δ_common(x_it × C_e) + μ_i + λ_t + ε_ite",
        "```",
        "",
        "Primary endpoint-specific model:",
        "",
        "```text",
        "z_ite = α + γC_e + β_Hx_it + δ_ES(x_it×C_e)",
        "        + weir FE + year FE + endpoint×weir FE + endpoint×year FE + ε_ite",
        "```",
        "",
        "On the identical shared support, `δ_ES = β_C,separate − β_H,separate`. The direct test clusters the entire two-endpoint, nine-year block by weir and therefore retains the cross-endpoint covariance; it does not use the invalid independent-SE subtraction.",
        "",
        "## Endpoint-specific results",
        "",
        "| Season | β cyano | β chlorophyll-a | δ_ES / arithmetic difference | Unified CR1 SE | CR1 95% CI | WCR p (two-sided) | Holm p | Paired-cluster bootstrap 95% CI | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for season in SEASONS:
        row = contrasts.loc[contrasts["season_scope"] == season].iloc[0]
        lines.append(
            f"| {LABELS[season]} | {row['beta_cyano']:.12f} | {row['beta_chlorophyll']:.12f} | "
            f"{row['delta_endpoint_specific_stacked']:.12f} | {row['cr1_se_unified']:.12f} | "
            f"[{row['cr1_ci_low']:.12f}, {row['cr1_ci_high']:.12f}] | {format_p(float(row['wcr_p_two_sided']))} | "
            f"{format_p(float(row['wcr_p_holm']))} | [{row['paired_bootstrap_ci_low']:.12f}, "
            f"{row['paired_bootstrap_ci_high']:.12f}] | `{row['inference_status']}` |"
        )

    lines.extend([
        "",
        "Primary WCR inference used all 65,536 null-imposed Rademacher sign patterns per season. The secondary paired bootstrap retained all 9,999 draws per season. One weir-level resample/sign was shared by both endpoints and all years.",
        "",
        "## Fixed specification matrix",
        "",
        matrix[[
            "season_scope", "model_id", "estimand_id", "estimate", "se", "ci_low", "ci_high",
            "p_raw", "p_holm", "inference_role", "source_artifact", "status",
        ]].to_markdown(index=False, floatfmt=".8f"),
        "",
        "## Candidate explanation decisions",
        "",
        "- **E1 supported.** The common-FE historical interaction reproduces, while endpoint-specific `δ_ES` equals the separate arithmetic difference and is numerically distinct from `δ_common`.",
        "- **E2 falsified.** Both endpoint paths use the same 144 weir-year rows per season and the frozen z-score metadata; support/scaling mismatch does not explain the gap.",
        "- **E3 falsified.** The byte-frozen implementation reproduces the named `0.887440...` and `1.035064...` interaction outputs.",
        "- **E4 split verdict: supported for legacy Bloom uncertainty only, falsified as the coefficient-gap explanation.** The frozen `cluster_se` aligns a fresh RangeIndex Series against caller-retained Bloom labels 144–287, obtains zero groups, and returns zero clustered SEs. Resetting only the frame index restores 16 groups and positive SEs with byte-identical coefficients. Pairing, design rank, coefficient mapping, endpoint-specific algebra, and the corrected joint-inference path all pass.",
        "- **E5 falsified.** Canonical hashes and every legacy numeric regression target passed; historical hashes were unchanged after execution.",
        (
            "- **E6 falsified under the prespecified formal-support rule.** The direction is positive, but the annual two-sided WCR/Holm comparison does not meet α=0.05."
            if d1_trigger and float(annual["delta_endpoint_specific_stacked"]) > 0
            else "- **E6 supported.** The prespecified annual endpoint-specific contrast is positive and supported by the WCR/Holm decision rule."
            if not d1_trigger
            else "- **E6 falsified.** The prespecified annual endpoint-specific contrast is nonpositive."
        ),
        "",
        "## Adverse results and claim impact",
        "",
        (
            "- Historical Bloom separate models reproduce exact `cluster_se=0.0` values because of a confirmed pandas index-alignment defect, not because sampling uncertainty is zero. An index-only diagnostic repair gives SE="
            f"{bloom_defect['cyano']['cluster_se_index_repaired']:.12f} for cyanobacteria and "
            f"SE={bloom_defect['chlorophyll_a']['cluster_se_index_repaired']:.12f} for chlorophyll-a, "
            "while changing neither coefficient. The frozen files remain byte-identical and these legacy SEs are not used for the new direct inference."
        ),
        "- The defensible endpoint-specific coefficient is the arithmetic difference, not the larger common-FE interaction. Both values remain visible because they are different estimands.",
        f"- Claim impact: **{claim_impact}**",
        f"- ASK_USER_FIRST(D1): **{'yes' if d1_trigger else 'no'}**. M1 reconciliation does not make the author-owned manuscript decision.",
        "",
        "## Sample, verification, and source paths",
        "",
        f"- Input contract: {input_audit['shape'][0]} rows × {input_audit['shape'][1]} columns; 16 weirs; 9 years; 144 shared rows per season; no duplicate keys or missing required fields.",
        f"- Design audit: `{run_root / 'design_audit.json'}`",
        f"- Legacy clustered-SE defect audit: `{run_root / 'legacy_cluster_se_defect_audit.json'}`",
        f"- source_artifact — legacy slopes: `{run_root / 'legacy/standardized_tau_models.csv'}`",
        f"- source_artifact — legacy common-FE interaction: `{run_root / 'legacy/specificity_interaction.csv'}`",
        f"- source_artifact — endpoint-specific contrasts: `{run_root / 'endpoint_specific_contrasts.csv'}`",
        f"- source_artifact — WCR patterns: `{run_root / 'wcr_signflip_t.csv.gz'}`",
        f"- source_artifact — paired bootstrap: `{run_root / 'cluster_pairs_bootstrap.csv.gz'}`",
        f"- source_artifact — specification matrix: `{run_root / 'specification_matrix.csv'}`",
        "",
        "## Residual risk",
        "",
        "The original June runtime was not archived. The revision run records the current environment. With 16 weirs, WCR still assumes cluster-level sign symmetry; year FE do not eliminate every possible cross-weir annual dependence, and nine years/four basins are too few for stable primary two-way/basin clustering.",
        "",
        f"VERDICT: {verdict}",
    ])
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_text(output, "\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    values = parse_args()
    render(values.run_root, values.output)
