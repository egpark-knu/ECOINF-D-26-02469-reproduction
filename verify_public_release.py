#!/usr/bin/env python3
"""Deterministic, standard-library verification of the public deposit."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
import sys
from pathlib import Path


MANIFEST = "MANIFEST.sha256"
TRANSIENT_PARTS = {".git", "__pycache__", ".pytest_cache", ".venv", "reproduction_output", "output"}
TRANSIENT_NAMES = {".DS_Store"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf"}


def _literal(*parts: str) -> str:
    return "".join(parts)


FORBIDDEN_TEXT = {
    "local_home_path": _literal("/", "Users", "/"),
    "sync_service_identity": _literal("Drop", "box"),
    "personal_account_identity": _literal("eungyu", "park"),
    "private_workspace_identity": _literal("ma", "s2", "-project"),
    "local_dependency_uri": _literal("file:", "///"),
    "patch_placeholder": _literal("@", "@"),
    "unfinished_marker": _literal("TO", "DO"),
    "nonpublic_availability_phrase": _literal("available", " upon request"),
    "chat_runtime_identity": _literal("Tele", "gram"),
    "orchestration_runtime_identity": _literal("MA", "S", "2"),
    "internal_agent_identity": _literal("co", "dex"),
    "internal_worker_field": _literal("worker", "_turn"),
}


_AGENT_FAMILY = _literal("(?:clau", "de|co", "dex|a", "gy)")
INTERNAL_IDENTITY_REGEXES = {
    "internal_agent_name": re.compile(
        _literal(r"\b", _AGENT_FAMILY, r"-[0-9]+\b"), re.IGNORECASE
    ),
    "internal_turn_id": re.compile(
        _literal(r"\bT[0-9]+_", _AGENT_FAMILY, r"[0-9]+_[0-9A-Za-z][0-9A-Za-z_-]*\b"),
        re.IGNORECASE,
    ),
    "internal_completion_field": re.compile(
        _literal(r"(?<!\[)\b(?:phase_report_)?", "worker", r"_(?:done|turn)\b"), re.IGNORECASE
    ),
    "internal_completion_marker": re.compile(
        _literal(
            r"\[(?:", "WORKER", "_DONE|", "HP", "_PASS|", "SENTINEL", "_PASS|",
            "REVIEW", r"_TURN(?::[^]\r\n]+)?|", "APPROVED", r"(?::[^]\r\n]+)?)\]",
        ),
        re.IGNORECASE,
    ),
}


SECRET_REGEXES = {
    "google_style_key": re.compile(_literal("AI", "za", r"[0-9A-Za-z_-]{20,}")),
    "github_style_token": re.compile(_literal("gh", "p_", r"[0-9A-Za-z]{20,}")),
    "openai_style_key": re.compile(_literal("sk", "-", r"[0-9A-Za-z_-]{20,}")),
    "assigned_secret": re.compile(
        _literal(r"(?i)(api[_-]?", "key", "|sec", "ret|to", r"ken)\s*[:=]\s*['\"]?[A-Za-z0-9_./+-]{12,}")
    ),
}


def release_files(root: Path, include_manifest: bool = True) -> list[Path]:
    files = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if not path.is_file() or any(part in TRANSIENT_PARTS for part in relative.parts):
            continue
        if path.name in TRANSIENT_NAMES or path.suffix == ".pyc":
            continue
        if not include_manifest and relative.as_posix() == MANIFEST:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def _read_scannable(path: Path) -> str:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return ""
    payload = path.read_bytes()
    if path.suffix == ".gz":
        try:
            payload = gzip.decompress(payload)
        except (gzip.BadGzipFile, EOFError):
            pass
    return payload.decode("utf-8", errors="ignore")


def scan_paths(paths: list[Path], base: Path) -> list[dict]:
    hits: list[dict] = []
    for path in paths:
        relative = path.relative_to(base).as_posix()
        for name, value in FORBIDDEN_TEXT.items():
            if value.lower() in relative.lower():
                hits.append({"file": relative, "location": "filename", "pattern": name})
        for name, pattern in INTERNAL_IDENTITY_REGEXES.items():
            matches = pattern.findall(relative)
            if matches:
                hits.append({"file": relative, "location": "filename", "pattern": name, "count": len(matches)})
        text = _read_scannable(path)
        lower = text.lower()
        for name, value in FORBIDDEN_TEXT.items():
            count = lower.count(value.lower())
            if count:
                hits.append({"file": relative, "location": "content", "pattern": name, "count": count})
        for name, pattern in INTERNAL_IDENTITY_REGEXES.items():
            matches = pattern.findall(text)
            if matches:
                hits.append({"file": relative, "location": "content", "pattern": name, "count": len(matches)})
        for name, pattern in SECRET_REGEXES.items():
            matches = pattern.findall(text)
            if matches:
                hits.append({"file": relative, "location": "content", "pattern": name, "count": len(matches)})
    return hits


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _close(actual: float, expected: float, tolerance: float = 5e-12) -> bool:
    return math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=tolerance)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_manifest(root: Path) -> tuple[bool, dict]:
    manifest_path = root / MANIFEST
    if not manifest_path.is_file():
        return False, {"error": "missing manifest"}
    entries: dict[str, str] = {}
    malformed: list[str] = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, raw_name = line.split(None, 1)
        except ValueError:
            malformed.append(line)
            continue
        name = raw_name.strip()
        if name.startswith("./"):
            name = name[2:]
        entries[name] = digest
    expected = {path.relative_to(root).as_posix() for path in release_files(root, include_manifest=False)}
    listed = set(entries)
    missing = sorted(expected - listed)
    extra = sorted(listed - expected)
    mismatches = sorted(name for name in expected & listed if _sha256(root / name) != entries[name])
    ok = not malformed and not missing and not extra and not mismatches
    return ok, {
        "entry_count": len(entries),
        "expected_count": len(expected),
        "passed_count": len(expected) - len(missing) - len(mismatches),
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches,
        "malformed": malformed,
    }


def verify_release(root: Path, check_manifest: bool = True) -> dict:
    root = root.resolve()
    gates: list[dict] = []

    def gate(name: str, ok: bool, evidence) -> None:
        gates.append({"name": name, "status": "PASS" if ok else "FAIL", "evidence": evidence})

    files = release_files(root)
    hits = scan_paths(files, root)
    scan_counts = {name: 0 for name in [*FORBIDDEN_TEXT, *INTERNAL_IDENTITY_REGEXES, *SECRET_REGEXES]}
    for hit in hits:
        scan_counts[hit["pattern"]] += int(hit.get("count", 1))
    gate("portable_tree_scan", not hits, {"files_scanned": len(files), "counts": scan_counts, "hits": hits})

    forbidden_runs = [
        "data/P2a_M1/runs/20260815T042748Z_c2ac8933",
        "data/P2d/runs/20260815T045525Z_cf60dc3b",
        "data/P2d/runs/20260815T045855Z_64e34497",
    ]
    present_runs = [name for name in forbidden_runs if (root / name).exists()]
    final_runs = sorted(path.name for path in (root / "data/P2d/runs").iterdir() if path.is_dir())
    gate("final_runs_only", not present_runs and final_runs == ["20260815T051100Z_cf60c3e4"], {
        "forbidden_runs_present": present_runs, "P2d_runs": final_runs,
    })

    p2c_data_dirs = sorted(path.name for path in (root / "data/P2c").iterdir() if path.is_dir())
    gate("P2c_v4_only", p2c_data_dirs == ["v4"], {"result_directories": p2c_data_dirs})

    p2a = _csv(root / "data/P2a_M1/runs/20260815T042826Z_c2ac8933/endpoint_specific_contrasts.csv")
    p2a_by_scope = {row["season_scope"]: row for row in p2a}
    annual = p2a_by_scope["annual_all_samples"]
    bloom = p2a_by_scope["bloom_season_06_10"]
    p2a_ok = (
        _close(annual["delta_endpoint_specific_stacked"], 0.539827967701)
        and _close(annual["wcr_p_holm"], 0.025970458984375)
        and _close(bloom["delta_endpoint_specific_stacked"], 0.297021927909)
        and bloom["inference_status"] == "positive_but_not_holm_supported"
    )
    gate("P2a_submission_values", p2a_ok, {
        "annual_delta": float(annual["delta_endpoint_specific_stacked"]),
        "annual_holm": float(annual["wcr_p_holm"]),
        "bloom_delta": float(bloom["delta_endpoint_specific_stacked"]),
        "bloom_status": bloom["inference_status"],
    })

    panel_path = root / "data/insitu_annual_analysis_panel.csv"
    panel_audit = _json(root / "data/panel_provenance_equality.json")
    differing = panel_audit.get("exact_differing_columns", [])
    equal_columns = panel_audit.get("semantic_equal_columns", [])
    original_columns = panel_audit.get("original_column_hashes", {})
    public_columns = panel_audit.get("public_column_hashes", {})
    normalized_columns = panel_audit.get("normalized_provenance_hashes", {})
    panel_provenance_ok = (
        panel_audit.get("status") == "PASS"
        and panel_audit.get("shape") == [288, 32]
        and differing == ["first_snapshot_x", "first_snapshot_y"]
        and len(equal_columns) == 30
        and panel_audit.get("differing_cell_counts") == {"first_snapshot_x": 288, "first_snapshot_y": 288}
        and panel_audit.get("normalized_provenance_equal") is True
        and panel_audit.get("original_file_sha256") == "83fcf10f4a8b06b2adb0d09370321f1b24bb150fb5be9d0b19e9d487aa1039e7"
        and panel_audit.get("public_file_sha256") == _sha256(panel_path)
        and all(original_columns.get(column) == public_columns.get(column) for column in equal_columns)
        and all(normalized_columns.get(column) == public_columns.get(column) for column in differing)
    )
    gate("analysis_panel_provenance_equality", panel_provenance_ok, {
        "shape": panel_audit.get("shape"), "differing_columns": differing,
        "semantic_equal_column_count": len(equal_columns),
        "original_file_sha256": panel_audit.get("original_file_sha256"),
        "public_file_sha256": panel_audit.get("public_file_sha256"),
    })

    funnel = {row["step"]: int(row["count"]) for row in _csv(root / "data/P2b/m03a_record_funnel.csv")}
    adjusted = _csv(root / "data/P2b/M2_adjusted_estimates.csv")
    slopes = _csv(root / "data/P2b/M2_per_endpoint_slopes.csv")
    basins = _csv(root / "data/P2b/M6_basin_inference.csv")
    adjusted_annual = next(row for row in adjusted if row["spec"] == "P_primary")
    bloom_cyano = next(row for row in slopes if row["spec"] == "S3_adjusted" and row["season_scope"] == "bloom_season_06_10" and row["outcome"] == "cyano")
    basin_p = {row["season_scope"]: float(row["ri_p_right"]) for row in basins if row["fixed_effects"] == "weir + basin-by-year"}
    p2b_ok = (
        funnel["C"] == 6748 and funnel["F"] == 6746
        and _close(adjusted_annual["beta"], 0.723617, tolerance=1e-6)
        and _close(bloom_cyano["cluster_p_two_sided"], 0.0862, tolerance=5e-5)
        and _close(basin_p["annual_all_samples"], 0.3348, tolerance=1e-12)
        and _close(basin_p["bloom_season_06_10"], 0.0262, tolerance=1e-12)
    )
    gate("P2b_submission_values", p2b_ok, {
        "source_count": funnel["C"], "analyzed_count": funnel["F"],
        "adjusted_annual_contrast": float(adjusted_annual["beta"]),
        "adjusted_bloom_cyano_p": float(bloom_cyano["cluster_p_two_sided"]),
        "basin_p": basin_p,
    })

    p2c_root = root / "data/P2c/v4"
    p2c_verification = _json(p2c_root / "verification_v4.json")
    comparison = _json(p2c_root / "clean_rebuild_comparison_v4.json")
    robust = _csv(p2c_root / "endpoint_contrast_robustness_v4.csv")
    primary = next(row for row in robust if row["window"] == "pm1_2017_2025" and row["specification"] == "within_weir_percentile_midrank" and row["aggregation"] == "equal_per_weir_fisher_z")
    p2c_gates = p2c_verification.get("gates", [])
    p2c_ok = (
        p2c_verification.get("status") == "COMPLETE_VERIFIED_V4"
        and p2c_verification.get("named_gate_count") == 17
        and len(p2c_gates) == 17 and all(item.get("status") == "pass" for item in p2c_gates)
        and int(primary["n_rows_chla"]) == 756 and int(primary["n_rows_cyano"]) == 756
        and _close(primary["delta_r"], 0.047288250187)
        and float(primary["delta_ci_low"]) < 0 < float(primary["delta_ci_high"])
        and comparison.get("status") == "pass" and not comparison.get("mismatches")
        and len(comparison.get("matched_sha256", {})) == 17
    )
    gate("P2c_v4_submission_values", p2c_ok, {
        "status": p2c_verification.get("status"), "gate_count": len(p2c_gates),
        "primary_support": int(primary["n_rows_chla"]), "primary_delta": float(primary["delta_r"]),
        "primary_interval": [float(primary["delta_ci_low"]), float(primary["delta_ci_high"])],
        "clean_comparison_status": comparison.get("status"),
        "clean_comparison_matches": len(comparison.get("matched_sha256", {})),
    })

    p2d_root = root / "data/P2d/runs/20260815T051100Z_cf60c3e4"
    p2d = {name: _json(p2d_root / f"{name.lower()}_result.json") for name in ("M5", "M8", "M9")}
    p2d_verification = _json(p2d_root / "verification.json")
    p2d_statuses = {name: result.get("verdict") for name, result in p2d.items()}
    expected_statuses = {"M5": "AXIS_EXHAUSTED", "M8": "WEAKENS_OR_REDIRECTS", "M9": "AXIS_EXHAUSTED"}
    p2d_ok = p2d_statuses == expected_statuses and p2d_verification.get("status") == "PASS" and not p2d_verification.get("failed_gates")
    gate("P2d_adverse_results", p2d_ok, {
        "statuses": p2d_statuses, "verification": p2d_verification.get("status"),
        "verification_gate_count": len(p2d_verification.get("gates", {})),
    })

    p2e = _csv(root / "data/P2e/mask_variant_uncertainty.csv")
    reconciliation = _json(root / "data/P2e/secondary_ci_reconciliation.json")
    p2e_source_root = root / "data/P2e/source_inputs"
    expected_p2e_sources = {
        "Round_2/02_analysis/variant_permutation/assignment_permutation_summary.csv": "92ac9a7a17a095e58ddd0bf1bdbda4cbfe3a94da448944940da18cdb7bd72c82",
        "research_execution/02_sampling_frame_gate/gate_results_site_year.csv": "fb03c168a557536c2af58f186c166effc246def0ef9a5c494aad7b7607e3f30f",
        "research_execution/02_sampling_frame_gate/gate_summary_table.csv": "575cad69b5e9ce29f427a4d01899a3e529d87ffb5cba6d2a2c584bfc94fad7a3",
        "research_execution/02_sampling_frame_gate/mask_variant_registry.csv": "4efbe94aeb0a6d4f820f2d8dff46c3b81a10faf65b9de4b89c34592cd1b04979",
        "research_execution/02_sampling_frame_gate/gee_exports/V04_pair_did.csv": "a85f417bf1a5779f72fee868a6c996a926458772f355bff97af36dfc4654548a",
        "research_execution/02_sampling_frame_gate/gee_exports/V05_pair_did.csv": "95398a3665846676d24d980d6c4d3054318dbc903ff4438af028a46705089e58",
        "research_execution/02_sampling_frame_gate/gee_exports/V06_pair_did.csv": "1a2322330bfbb9f30c8bc91b64ffb4ecb4dfb4bf20ab69eb9b2f4819c39fcc52",
        "research_execution/02_sampling_frame_gate/gee_exports/V07_pair_did.csv": "52ba16e2d6b65b54aebdc5afcbcabb6cfe5f0a7ac687c32083a32aee4dc4ac04",
    }
    actual_p2e_sources = {
        path.relative_to(p2e_source_root).as_posix(): _sha256(path)
        for path in sorted(p2e_source_root.rglob("*.csv"))
    }
    gate("P2e_source_inputs", actual_p2e_sources == expected_p2e_sources, {
        "source_count": len(actual_p2e_sources),
        "hashes_match": actual_p2e_sources == expected_p2e_sources,
    })
    v06 = next(row for row in p2e if row["variant_id"] == "V06")
    p2e_ok = (
        len(p2e) == 8
        and all(row["secondary_ci_includes_zero"] == "True" for row in p2e)
        and float(v06["pooled_effect"]) < 0 and v06["historical_verdict"] == "FAIL_SIGN_REVERSAL"
        and all("Student-t" in row["secondary_inference"] for row in p2e)
        and reconciliation.get("all_variants_confirmed") is True
        and len(reconciliation.get("per_variant", [])) == 8
    )
    gate("P2e_uncertainty_values", p2e_ok, {
        "variant_count": len(p2e), "intervals_include_zero": sum(row["secondary_ci_includes_zero"] == "True" for row in p2e),
        "V06_effect": float(v06["pooled_effect"]), "V06_verdict": v06["historical_verdict"],
        "secondary_method": reconciliation.get("hypothesis"),
    })

    if check_manifest:
        manifest_ok, manifest_evidence = verify_manifest(root)
        gate("manifest", manifest_ok, manifest_evidence)

    failures = [item["name"] for item in gates if item["status"] != "PASS"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "root": ".",
        "package_file_count": len(files),
        "gates": gates,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--no-manifest", action="store_true")
    args = parser.parse_args(argv)
    result = verify_release(args.root, check_manifest=not args.no_manifest)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
