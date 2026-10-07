"""Offline tests: pinned metadata reads only, never run the author pipeline."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("normalize_specauditor", ROOT / "tools/normalize_specauditor.py")
normalizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(normalizer)


def as_csv(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=normalizer.RAW_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


class NormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blobs = normalizer.read_pinned(ROOT)
        cls.outputs = normalizer.build(cls.blobs)
        cls.rows, cls.cases, cls.specs = normalizer.normalize(cls.blobs[normalizer.DATASET])

    def test_inventory_and_reference_separation(self):
        summary = json.loads(self.outputs["summary.json"])
        self.assertEqual(summary["counts"], dict(cases=48, specifications=18, buggy_symbols=47,
                                                seed_patches=9, target_snapshots=1, bound_locations=0))
        self.assertEqual(summary["status"]["evaluation"], "not_run")
        refs = summary["author_references"]
        self.assertEqual(refs["provenance"], "author_shipped_reference_only_not_our_run")
        self.assertEqual(refs["localization_probe"]["found_anywhere"], 48)
        self.assertEqual(refs["targeted"]["detected_rows"], 39)
        self.assertEqual(refs["localized"]["detected_bug_rows"], 41)
        self.assertIsNone(refs["localized"]["forced_correction_count"])

    def test_deterministic_build_and_pinned_objects(self):
        self.assertEqual(self.outputs, normalizer.build(normalizer.read_pinned(ROOT)))
        source = json.loads(self.outputs["source.json"])
        self.assertEqual(set(source["files"]), set(normalizer.PROVENANCE_PATHS))
        for path, value in source["files"].items():
            self.assertEqual(value, {"sha256": normalizer.sha(self.blobs[path]), "bytes": len(self.blobs[path])})

    def test_raw_refs_and_stable_ids(self):
        for index, (raw, case) in enumerate(zip(self.rows, self.cases), 1):
            digest = normalizer.sha(normalizer.canonical(raw))
            self.assertEqual(case["case_id"], "specauditor-case-" + digest[:20])
            self.assertEqual(case["evaluator_only"]["raw_ref"],
                             {"path": normalizer.DATASET, "data_row": index, "row_sha256": digest})
        spaced = [{key: " " + value + " " for key, value in row.items()} for row in self.rows]
        self.assertEqual(normalizer.normalize(as_csv(spaced))[1:], (self.cases, self.specs))

    def test_model_projection_has_no_answer_mapping(self):
        for spec in self.specs:
            self.assertEqual(set(spec["model_input"]), {"target_entity", "target_description", "predicate"})
            self.assertNotIn("buggy_symbol", spec["model_input"])
            self.assertNotIn("seed_patch", spec["model_input"])
        for case in self.cases:
            self.assertEqual(set(case), {"case_id", "snapshot_id", "status", "evaluator_only"})
        referenced = [case_id for spec in self.specs for case_id in spec["evaluator_only"]["case_ids"]]
        self.assertCountEqual(referenced, [case["case_id"] for case in self.cases])

    def test_same_function_different_specs_preserved(self):
        cases = [case for case in self.cases if case["evaluator_only"]["buggy_symbol"] == "tegra210_xusb_padctl_probe"]
        self.assertEqual(len(cases), 2)
        self.assertEqual(len({case["evaluator_only"]["spec_id"] for case in cases}), 2)

    def test_reject_duplicate_rows_and_malformed_fields(self):
        with self.assertRaisesRegex(ValueError, "Duplicate official"):
            normalizer.normalize(as_csv(self.rows + [self.rows[0]]))
        for field, value in (("buggy function", "bad;command"), ("seed patch", "main"), ("spec_predicate", "")):
            altered = [dict(row) for row in self.rows]
            altered[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                normalizer.normalize(as_csv(altered))

    def test_reject_reference_mismatch(self):
        blobs = dict(self.blobs)
        path = normalizer.REF_ROOT + "reproduced_bug_detection_localized_summary.json"
        value = json.loads(blobs[path])
        value["detected_bug_rows"] = 1000
        blobs[path] = normalizer.pretty(value)
        with self.assertRaisesRegex(ValueError, "Reference localized"):
            normalizer.build(blobs)

    def test_create_check_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "normalized"
            normalizer.emit(output, self.outputs)
            before = {path.name: path.stat().st_mtime_ns for path in output.iterdir()}
            normalizer.emit(output, self.outputs, check=True)
            self.assertEqual(before, {path.name: path.stat().st_mtime_ns for path in output.iterdir()})
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                normalizer.emit(output, self.outputs)
            (output / "summary.json").write_bytes(b"{}\n")
            with self.assertRaisesRegex(ValueError, "differs"):
                normalizer.emit(output, self.outputs, check=True)

    def test_check_rejects_extra_files_or_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "normalized"
            normalizer.emit(output, self.outputs)
            (output / "unexpected.json").write_bytes(b"{}\n")
            with self.assertRaisesRegex(ValueError, "file set"):
                normalizer.emit(output, self.outputs, check=True)
            alias = Path(temp) / "alias"
            alias.symlink_to(output, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                normalizer.emit(alias, self.outputs, check=True)


if __name__ == "__main__":
    unittest.main()
