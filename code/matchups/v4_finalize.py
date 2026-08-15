"""Compare two clean matchups v4 builds, verify, publish reports, and finalize status."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from v4_build import write_json
from v4_reports import append_verification_summary, mark_complete
from v4_verify import verify_output


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def artifact_files(root: Path) -> dict[str, Path]:
    excluded = {"verification_v4.json", "clean_rebuild_comparison_v4.json"}
    return {
        str(p.relative_to(root)): p for p in sorted(root.rglob("*"))
        if p.is_file() and p.name not in excluded
    }


def compare_builds(primary: Path, rebuild: Path) -> dict:
    a, b = artifact_files(primary), artifact_files(rebuild)
    mismatches = []
    matched_hashes = {}
    for relative in sorted(set(a) | set(b)):
        if relative not in a or relative not in b:
            mismatches.append({"path": relative, "reason": "missing_in_one_build"})
            continue
        hash_a, hash_b = sha256(a[relative]), sha256(b[relative])
        if hash_a != hash_b:
            mismatches.append({"path": relative, "reason": "sha256_mismatch", "primary": hash_a, "rebuild": hash_b})
        else:
            matched_hashes[relative] = hash_a
    return {
        "status": "pass" if not mismatches else "fail",
        "compared_files": len(set(a) | set(b)),
        "mismatches": mismatches,
        "matched_sha256": matched_hashes,
        "declared_exclusions": ["verification_v4.json", "clean_rebuild_comparison_v4.json"],
        "comparison_rule": "byte-identical SHA-256 for every built table, canonical gzip, scientific JSON, report payload, map note, and PNG",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", required=True)
    parser.add_argument("--rebuild", required=True)
    args = parser.parse_args()
    primary, rebuild = Path(args.primary).resolve(), Path(args.rebuild).resolve()
    comparison = compare_builds(primary, rebuild)
    if comparison["status"] != "pass":
        write_json(primary / "clean_rebuild_comparison_v4.json", comparison)
        raise SystemExit(f"clean rebuild mismatch: {comparison['mismatches']}")

    verification = verify_output(primary, comparison)
    if verification["status"] != "COMPLETE_VERIFIED_V4":
        write_json(primary / "clean_rebuild_comparison_v4.json", comparison)
        write_json(primary / "verification_v4.json", verification)
        raise SystemExit(f"verification failed: {verification['failures']}")

    report_names = ["M3_matchups.md", "M4_spatial.md", "matchups_report.md"]
    primary_reports = [primary / "reports" / name for name in report_names]
    rebuild_reports = [rebuild / "reports" / name for name in report_names]
    mark_complete(primary_reports)
    mark_complete(rebuild_reports)
    append_verification_summary(primary_reports)
    append_verification_summary(rebuild_reports)
    comparison = compare_builds(primary, rebuild)
    report_hashes_equal = all(sha256(a) == sha256(b) for a, b in zip(primary_reports, rebuild_reports))
    comparison["post_verification_report_hashes_equal"] = report_hashes_equal
    if comparison["status"] != "pass" or not report_hashes_equal:
        raise SystemExit("post-verification report status hashes differ")

    verification = verify_output(primary, comparison)
    if verification["status"] != "COMPLETE_VERIFIED_V4":
        raise SystemExit(f"post-report verification failed: {verification['failures']}")

    write_json(primary / "clean_rebuild_comparison_v4.json", comparison)
    write_json(primary / "verification_v4.json", verification)

    revision = Path(__file__).resolve().parents[3]
    destinations = [
        revision / "03_analysis/reports/M3_matchups.md",
        revision / "03_analysis/reports/M4_spatial.md",
        revision / "99_admin/reports/matchups_report.md",
    ]
    for source, destination in zip(primary_reports, destinations):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    print(json.dumps({"status": verification["status"], "named_gates": verification["named_gate_count"], "compared_files": comparison["compared_files"]}, sort_keys=True))


if __name__ == "__main__":
    main()
