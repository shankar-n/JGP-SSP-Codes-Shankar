# Public repository hygiene

## Published source of record

- `src/BBC/` is the canonical implementation and merged campaign ledger. Its
  compact provenance is retained separately. The final primary-ledger check reports
  **16,920/16,920 canonical identities**.
- `src/BBC/results/provenance/primary_ledger_audit.json` retains a compact hash
  inventory for the local source-shard archive. Raw scheduler stderr and
  higher-resource sensitivity outputs are intentionally not published.
- Canonical PDFs and `report/figdata/` are intentionally not ignored.

## Local-only material

The following are ignored so a normal `git add -A` cannot publish them:

- `src/BBC-server/` — old/duplicate server snapshot (~289 MB).
- `bbc_primary_recovery_40164.tar.gz` and
  `src/BBC/cluster/bbc_recovery_bundle.zip` — transfer bundles.
- `src/BBC/results/sensitivity_32gb/`, detailed recovery snapshots, and raw
  scheduler evidence, together with the one-off recovery scripts.
- Superseded BNP pilot output and the unused local bibliography scratch file.
- `tmp/` and TeX build/render by-products.

`src/BBC-server/` has not been deleted. After confirming the canonical tree
and a separate backup, it is safe to remove locally; no canonical result or
manifest depends on it.

## Before publishing

Run `python verification/analyse_campaign_results.py --check` and inspect
`git status`.
Do not publish third-party reference PDFs unless their redistribution licence
permits it. `.gitignore` does not remove files that were already committed;
use `git rm --cached <path>` for any already-tracked private material.
