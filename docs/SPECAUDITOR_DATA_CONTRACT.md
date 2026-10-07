# SpecAuditor normalized data contract v1

Adapter: `specauditor-normalized-v1`. All four generated files use UTF-8 and end
in a newline. JSONL records have sorted keys and compact separators; standalone
JSON is sorted with two-space indentation. Source data is read with `git show`
at upstream commit `a7f5248890130eac8ba329428672243f80e430bc`.

## Source and case identity

The original CSV is
`artifact/reproduced_bug_detection/datasets/checks.csv`. Its ordered columns are
`seed patch`, `detected target`, `buggy function`, `spec_target`, `spec_predicate`.
Values are stripped of leading/trailing whitespace, matching the author runner.
`data_row` is the one-based logical CSV data-record index, excluding the header;
it is not a physical line number because CSV records can span lines.

Canonical row bytes are JSON of the five original column/value pairs, with
`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, no trailing
newline. `row_sha256` hashes those bytes. Case ID is `specauditor-case-` followed
by the first 20 hash characters. The entire original CSV also has a separate
byte hash, so normalization never hides raw changes.

Specification identity follows the official four-field grouping: the JSON list
`[seed patch, detected target, spec_target, spec_predicate]` uses the same
canonical encoding. Spec ID is `specauditor-spec-` plus the first 20 hash
characters. Cases preserve CSV order. Specs preserve first-occurrence order;
case IDs and raw references within each spec preserve CSV order. Duplicate
official `(seed patch, detected target, buggy function)` keys and ID collisions
are rejected.

## Generated files

`cases.jsonl` contains:

```json
{
  "case_id": "specauditor-case-<20-hex>",
  "snapshot_id": "linux-1b237f190eb3d36f52dffe07a40b5eb210280e00",
  "status": {
    "source_binding": "pending_local_review",
    "candidate_pool": "not_built",
    "evaluation": "not_run"
  },
  "evaluator_only": {
    "buggy_symbol": "<expected function>",
    "seed_patch": "<author seed patch>",
    "spec_id": "specauditor-spec-<20-hex>",
    "raw_ref": {
      "path": "artifact/reproduced_bug_detection/datasets/checks.csv",
      "data_row": 1,
      "row_sha256": "<64-hex>"
    }
  }
}
```

`specs.jsonl` contains `spec_id`, `model_input` and `evaluator_only`:

- `model_input`: exactly `target_entity` (author's detected target API),
  `target_description` (spec_target) and `predicate` (spec_predicate).
- `evaluator_only`: `seed_patch`, ordered `case_ids`, and ordered `raw_refs`.

`source.json` contains `schema_version=1`, `adapter`, `upstream`,
`target_snapshot`, `files`, `protocol` and `license`. `files` maps each fixed
path to `{sha256, bytes}`. The complete allowlist is `PROVENANCE_PATHS` in the
normalizer: CSV, original AE/install/license material, relevant upstream
entrypoints/localizer/prompt and author reference outputs. No secret-bearing
local environment file is read. The target snapshot pins repository URL, tag,
full commit and the snapshot ID; it does not assert that source was acquired.

`summary.json` contains `schema_version=1`, `adapter`, calculated `counts`,
`status`, `scope` and `author_references`. Counts are `cases`, `specifications`,
`buggy_symbols`, `seed_patches`, `target_snapshots`, `bound_locations`. No source
binding is produced here, so bound locations remain zero. Metadata counts do
not measure training readiness, localization, detection or runtime success.

## Model/answer boundary

The only model-facing inputs are the **whole** specification portfolio and the
pinned Linux code. Each portfolio item may carry its stable `spec_id` together
with its `model_input`; an item cannot reveal which known cases use it.

The gold buggy function, seed patch, raw row, case-to-spec mapping, reference
findings, generated reference queries and correctness labels remain on the
evaluator side. Do not select a particular spec for a case using the known bug.
For a one-snapshot evaluation, run the declared portfolio on that snapshot and
score the resulting findings against all cases. An oracle-guideline or
oracle-location diagnostic must be labeled separately.

Target API names are deliberately public in the author's specification-driven
task. Removing them changes the task; conversely, adding a gold buggy caller
changes it to given-location auditing. No author-provided rule is newly learned
by this normalization.

## Original AE conditions and reference outputs

The reference section describes only author-shipped files. Probe counts are
membership anywhere in an unranked candidate set. Localized and targeted
reference summaries are not our experiments, and no entry is a runtime oracle.

The original `build_group_audit_candidate_set` in
`artifact/reproduced_bug_detection/run.py` replaces ordinary selected functions
with known buggy functions found outside its initial audit budget. Preserve
this fact when discussing localized results. The shipped aggregate/all-audited
references omit original full candidate order and forced-selection flags;
`forced_correction_count` is therefore `null` with an explicit reason, not zero.
Additional violation reports are model outputs, not independently verified bugs.

The targeted mode queries expected buggy functions. The localization probe
still calls a model for weggli query generation. Functional `demo-assisted`
copies reference retrieval and can fill generated specs from reference;
functional `live` can retry retrieval with a packaged original query and uses
the packaged target selection. The reproduced-generation workflow also reuses
reference retrieval. These are AE conveniences, not a claim of unbiased full
paper replication.

## Next static source-binding step

Acquire and verify the pinned Linux tree; then resolve every expected symbol to
file plus exact function span/hash. Keep ambiguous/missing symbols explicit.
Two different rules for one function remain two cases. Generate the candidate
pool without reading gold functions. Existing function-name-only dictionaries
in the original CodeSearcher can overwrite same-named functions and lose paths;
our IDs should include source path and span.

Do not run the original shell-interpolated weggli helper on untrusted model
queries. Any later static query replay should use a validated argument-vector
subprocess, timeout, captured return code, and explicit error status. Reference
query replay is a separate protocol, not a new live localization result.
Do not execute target code, compile the kernel, call APIs, or modify global Git
configuration to perform metadata normalization.

## Scope and licensing

This is an author-selected positive-only AE subset in one Linux project, not
the full paper scale, a random unseen test set, or a general authorization
benchmark. There are no certified safe examples or complete whole-kernel truth
labels. Unmatched findings require review rather than automatic false-positive
classification. Check overlap before any train/test claim.

The upstream Apache-2.0 LICENSE and all original files remain intact. This
contract adds no grant over Linux or bundled third-party materials, which keep
their original terms. No blanket relicensing is implied.
