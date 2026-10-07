#!/usr/bin/env python3
"""Normalize a pinned SpecAuditor Git snapshot; never import upstream code.

Only Git object reads and parsing are performed. Target Linux, model endpoints,
author scripts, and reference queries are never executed.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess


UPSTREAM = "a7f5248890130eac8ba329428672243f80e430bc"
ADAPTER = "specauditor-normalized-v1"
TARGET_COMMIT = "1b237f190eb3d36f52dffe07a40b5eb210280e00"
SNAPSHOT_ID = "linux-" + TARGET_COMMIT
DATASET = "artifact/reproduced_bug_detection/datasets/checks.csv"
REF_ROOT = "artifact/reproduced_bug_detection/reference/"
RAW_COLUMNS = ("seed patch", "detected target", "buggy function", "spec_target", "spec_predicate")
SPEC_COLUMNS = ("seed patch", "detected target", "spec_target", "spec_predicate")
OUTPUT_NAMES = ("cases.jsonl", "specs.jsonl", "source.json", "summary.json")
PROVENANCE_PATHS = (
    DATASET, "README.md", "AE.md", "INSTALL.md", "LICENSE",
    "artifact/common.py", "artifact/functional/run.py",
    "artifact/reproduced_generation/run.py",
    "artifact/reproduced_generation/datasets/seed_commits.csv",
    "artifact/reproduced_bug_detection/run.py",
    "artifact/reproduced_bug_detection/run.sh",
    "artifact/reproduced_bug_detection/run_localization_check.sh",
    "scripts/bug_detection_threaded.py", "scripts/utils/CodeSearcher.py",
    "scripts/utils/ASTParser.py", "prompts/bug_audit_prompts.py",
    REF_ROOT + "reference.csv", REF_ROOT + "reference_summary.json",
    REF_ROOT + "reproduced_bug_detection_localization_probe.csv",
    REF_ROOT + "reproduced_bug_detection_localized_all_audited_candidates.csv",
    REF_ROOT + "reproduced_bug_detection_localized_summary.json",
    REF_ROOT + "reproduced_bug_detection_localized_violation_reports.csv",
    REF_ROOT + "reproduced_bug_detection_localized_additional_violation_reports.csv",
)
STATUS = {"source_binding": "pending_local_review", "candidate_pool": "not_built", "evaluation": "not_run"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pretty(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def jsonl(rows):
    return b"".join(canonical(row) + b"\n" for row in rows)


def csv_rows(data):
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""))
    require(reader.fieldnames and len(set(reader.fieldnames)) == len(reader.fieldnames),
            "Missing or duplicate CSV column")
    rows = list(reader)
    require(rows and all(None not in row and all(value is not None for value in row.values())
                         for row in rows), "Empty or malformed CSV")
    return [{key: value.strip() for key, value in row.items()} for row in rows]


def normalize(data):
    rows = csv_rows(data)
    require(tuple(rows[0]) == RAW_COLUMNS, "Unexpected checks.csv columns")
    seen_cases = set()
    cases, specs_by_key = [], {}
    for data_row, row in enumerate(rows, 1):
        require(all(row.values()), "Empty case field")
        require(re.fullmatch(r"[0-9a-f]{12,40}", row["seed patch"]), "Invalid seed patch")
        for field in ("detected target", "buggy function"):
            require(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", row[field]), "Invalid C symbol")
        case_key = tuple(row[field] for field in RAW_COLUMNS[:3])
        require(case_key not in seen_cases, "Duplicate official benchmark key")
        seen_cases.add(case_key)
        row_hash = sha(canonical(row))
        case_id = "specauditor-case-" + row_hash[:20]
        spec_key = tuple(row[field] for field in SPEC_COLUMNS)
        spec_id = "specauditor-spec-" + sha(canonical(list(spec_key)))[:20]
        raw_ref = {"path": DATASET, "data_row": data_row, "row_sha256": row_hash}
        cases.append({"case_id": case_id, "snapshot_id": SNAPSHOT_ID, "status": dict(STATUS),
                      "evaluator_only": {"buggy_symbol": row["buggy function"],
                                         "seed_patch": row["seed patch"], "spec_id": spec_id,
                                         "raw_ref": dict(raw_ref)}})
        if spec_key not in specs_by_key:
            specs_by_key[spec_key] = {
                "spec_id": spec_id,
                "model_input": {"target_entity": row["detected target"],
                                "target_description": row["spec_target"],
                                "predicate": row["spec_predicate"]},
                "evaluator_only": {"seed_patch": row["seed patch"], "case_ids": [], "raw_refs": []}}
        spec = specs_by_key[spec_key]
        spec["evaluator_only"]["case_ids"].append(case_id)
        spec["evaluator_only"]["raw_refs"].append(dict(raw_ref))
    specs = list(specs_by_key.values())
    require(len({row["case_id"] for row in cases}) == len(cases), "Case hash collision")
    require(len({row["spec_id"] for row in specs}) == len(specs), "Specification hash collision")
    return rows, cases, specs


def true(value):
    require(value.lower() in ("true", "false", "1", "0", "yes", "no"), "Invalid reference boolean")
    return value.lower() in ("true", "1", "yes")


def author_references(blobs, rows):
    """Describe the author's shipped files, never our measured performance."""
    probe = csv_rows(blobs[REF_ROOT + "reproduced_bug_detection_localization_probe.csv"])
    targeted = csv_rows(blobs[REF_ROOT + "reference.csv"])
    audited = csv_rows(blobs[REF_ROOT + "reproduced_bug_detection_localized_all_audited_candidates.csv"])
    localized = json.loads(blobs[REF_ROOT + "reproduced_bug_detection_localized_summary.json"])
    require([{key: row[key] for key in RAW_COLUMNS} for row in probe] == rows,
            "Reference probe/checks row mismatch")
    require([{key: row[key] for key in RAW_COLUMNS} for row in targeted] == rows,
            "Reference targeted/checks row mismatch")
    violations = sum(true(row["has_violation"]) for row in audited)
    expected_violations = sum(true(row["has_violation"]) and true(row["is_expected_for_any_bug_row"])
                              for row in audited)
    require(localized["detected_bug_rows"] == expected_violations
            and localized["audited_candidate_rows"] == len(audited)
            and localized["violation_report_rows"] == violations,
            "Reference localized summary mismatch")
    return {
        "provenance": "author_shipped_reference_only_not_our_run",
        "localization_probe": {
            "rows": len(probe), "found_anywhere": sum(true(row["expected_function_found"]) for row in probe),
            "candidate_count_min": min(int(row["candidate_count"]) for row in probe),
            "candidate_count_max": max(int(row["candidate_count"]) for row in probe),
            "distinct_generated_queries": len({row["generated_query"] for row in probe}),
            "metric": "membership_in_entire_unranked_candidate_set_not_recall_at_k"},
        "targeted": {"rows": len(targeted), "detected_rows": sum(true(row["has_violation"]) for row in targeted),
                     "input_condition": "known_buggy_function"},
        "localized": {"detected_bug_rows": expected_violations, "audited_candidate_rows": len(audited),
                      "violation_report_rows": violations,
                      "additional_violation_report_rows": violations - expected_violations,
                      "known_answer_budget_correction_present_in_runner": True,
                      "forced_correction_count": None,
                      "forced_correction_count_reason": "shipped_reference_lacks_original_candidate_order_and_forced_flags"},
        "not_runtime_confirmation": True,
    }


def build(blobs):
    require(set(blobs) == set(PROVENANCE_PATHS), "Incomplete pinned source/protocol files")
    rows, cases, specs = normalize(blobs[DATASET])
    counts = {"cases": len(cases), "specifications": len(specs),
              "buggy_symbols": len({row["buggy function"] for row in rows}),
              "seed_patches": len({row["seed patch"] for row in rows}),
              "target_snapshots": len({case["snapshot_id"] for case in cases}),
              "bound_locations": 0}
    # No location binding is created by this metadata-only adapter.
    source = {
        "schema_version": 1, "adapter": ADAPTER,
        "upstream": {"repository": "https://github.com/Yuuoniy/SpecAuditor", "commit": UPSTREAM},
        "target_snapshot": {"snapshot_id": SNAPSHOT_ID, "repository": "https://github.com/torvalds/linux",
                            "tag": "v6.17-rc3", "commit": TARGET_COMMIT},
        "files": {path: {"sha256": sha(blobs[path]), "bytes": len(blobs[path])} for path in PROVENANCE_PATHS},
        "protocol": {
            "scope": "author_selected_positive_artifact_evaluation_subset_not_full_paper",
            "model_input": "whole_specification_portfolio_and_pinned_source_only",
            "evaluator_only": ["buggy_symbol", "seed_patch", "case_to_spec_mapping", "raw_refs", "author_reference_outputs"],
            "official_localized_gold_budget_correction": True,
            "official_targeted_is_oracle_location": True,
            "official_probe_calls_llm_for_queries": True,
            "official_functional_demo_and_live_have_assistance": True,
            "upstream_code_executed": False,
            "target_code_executed": False,
            "api_called": False,
        },
        "license": {"upstream": "Apache-2.0", "license_path": "LICENSE",
                    "third_party_boundary": "Linux and bundled third-party material retain their own licenses; no blanket relicensing."},
    }
    summary = {"schema_version": 1, "adapter": ADAPTER, "counts": counts, "status": dict(STATUS),
               "scope": source["protocol"]["scope"],
               "author_references": author_references(blobs, rows)}
    return {"cases.jsonl": jsonl(cases), "specs.jsonl": jsonl(specs),
            "source.json": pretty(source), "summary.json": pretty(summary)}


def read_pinned(repo):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.PIPE)
    require(git("rev-parse", UPSTREAM + "^{commit}").decode().strip() == UPSTREAM,
            "Pinned upstream commit unavailable")
    return {path: git("show", UPSTREAM + ":" + path) for path in PROVENANCE_PATHS}


def emit(output_dir, outputs, check=False):
    output_dir = Path(output_dir)
    if check:
        require(output_dir.is_dir() and not output_dir.is_symlink(), "Missing or unsafe normalized directory")
        require({path.name for path in output_dir.iterdir()} == set(OUTPUT_NAMES), "Unexpected normalized file set")
        for name in OUTPUT_NAMES:
            path = output_dir / name
            require(path.is_file() and not path.is_symlink() and path.read_bytes() == outputs[name],
                    "Normalized file differs: " + name)
        return
    require(not output_dir.exists() or (output_dir.is_dir() and not output_dir.is_symlink()
                                      and not any(output_dir.iterdir())),
            "Output exists; use --check. Refusing to overwrite.")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_NAMES:
        with (output_dir / name).open("xb") as stream:
            stream.write(outputs[name])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = build(read_pinned(args.repo))
    emit(args.output_dir or args.repo / "datasets/specauditor", outputs, args.check)
    print(json.dumps({"mode": "verified" if args.check else "created",
                      "counts": json.loads(outputs["summary.json"])["counts"],
                      "target_code_executed": False, "api_called": False}, sort_keys=True))


if __name__ == "__main__":
    main()
