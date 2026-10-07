# SpecAuditor benchmark adaptation

This repository preserves the upstream SpecAuditor artifact at
`a7f5248890130eac8ba329428672243f80e430bc`. Original upstream files, history,
license, datasets, scripts and reference outputs are unchanged. This adaptation
adds a small deterministic metadata layer; it does not replace the author README.

## What is included

- `datasets/specauditor/`: normalized cases, full specification portfolio,
  pinned provenance and calculated inventory.
- `tools/normalize_specauditor.py`: standard-library normalizer reading fixed
  Git objects, not mutable upstream files. It never imports author code.
- `tests/test_normalize_specauditor.py`: offline metadata and isolation tests.
- [Data contract](docs/SPECAUDITOR_DATA_CONTRACT.md): fields, input boundaries,
  reference interpretation and the next source-binding step.

The normalized inventory has 48 author-selected bug-instance rows, 18
specifications, 47 unique expected function names, 9 seed patches and one Linux
snapshot. It is a positive-only artifact-evaluation subset, not 48 CVEs, 48
projects or the complete paper experiment. Two rows describe different rules
for the same function. Rules include reference ownership, failure handling,
device state and parameter constraints; this is not an authorization-only set.

## Reproduce the metadata

Run from the repository root with Python 3.9 or newer:

```sh
python3 tools/normalize_specauditor.py --check
python3 -m unittest discover -s tests -p test_normalize_specauditor.py
```

The included outputs already exist. Without `--check`, the normalizer only
creates a new/empty destination and refuses overwrites. To generate an independent
copy, give `--output-dir` a new directory. The pinned upstream commit must be
present in the local Git object database.

## Current status

Metadata is normalized; source-location review is pending. No Linux checkout,
code pool, model call, audit, target execution or runtime confirmation is
performed by this adaptation. Expected source is Linux `v6.17-rc3`, commit
`1b237f190eb3d36f52dffe07a40b5eb210280e00`. Author reference metrics are clearly
separated from our `not_run` status.

The author's localized AE runner can force known buggy functions into its
bounded audit queue. The targeted mode is explicitly given the expected
function. Neither condition may silently be called blind Top-K detection.
The official localization-only probe still calls an LLM to generate queries.
Its reference 48/48 counts presence anywhere in the candidate set, not Recall@K.

Upstream is Apache-2.0; its LICENSE is retained unchanged. Linux and bundled
third-party material retain their own licenses. This adaptation does not
relicense target source code or certify every third-party item's license.
