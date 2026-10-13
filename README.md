# SpecAuditor benchmark data

Versioned author data in the shared `bench-dataset-v1` format.

- `dataset/cases.jsonl`: 48 author detection rows, covering 47 buggy symbols.
- `dataset/manifest.json`: immutable provenance, assets, counts and licenses.
- `dataset/assets/`: 18-spec global portfolio, original tables, author references,
  12 generation-seed patches and license evidence.

The detection subset uses 9 seed patches; the separate generation input has 12.
The target is Linux `v6.17-rc3`. Historical seed repairs are knowledge, not fixes
for the detected target bugs. Author reference outputs are not new method results.

Use [embed](https://github.com/Dilrevx/embed) for methods, the
[dataset lock](https://github.com/Dilrevx/embed/blob/spec-audit-ab/benchmarks/specauditor/dataset-lock.json),
and [shared commands](https://github.com/Dilrevx/embed/blob/spec-audit-ab/docs/method-runner.md).
From an embed checkout:

```sh
PYTHONPATH=src python -m embedbench validate-dataset \
  --benchmark-checkout ../SpecAuditor --lock benchmarks/specauditor/dataset-lock.json
```

Original inputs and normalization remain traceable at
[`dca9c59`](https://github.com/Dilrevx/SpecAuditor/tree/dca9c5991707f695331ef1ec7e9ca5b56232fd8a).
The [upstream method](https://github.com/Yuuoniy/SpecAuditor) and its AE code are
not maintained in this data branch. Apache-2.0 does not relicense the Linux seed
diffs; their original license evidence is retained in the asset inventory.
