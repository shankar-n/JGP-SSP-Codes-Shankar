#!/usr/bin/env python3
"""Regression checks for campaign resumption keys (no solver required)."""
from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def repeated_crama_paths(module):
    by_stem = defaultdict(list)
    for family, path, _time_limit in module.get_instances(module.ALL_SETS):
        if family == "Crama":
            by_stem[Path(path).stem].append((family, path))
    for entries in by_stem.values():
        if len(entries) > 1:
            return entries
    raise AssertionError("test data contain no repeated Crama file name")


def check_runner(module, feature_reader, completed_reader):
    entries = repeated_crama_paths(module)
    identities = {
        module._work_key(family, path, "test-config")
        for family, path in entries
    }
    dimensions = {feature_reader(path)[:3] for _family, path in entries}
    assert len(identities) == len(dimensions) == len(entries), (
        "repeated Crama names at different capacities must have distinct keys"
    )
    assert all(10**6 not in dims for dims in dimensions), "Crama headers must parse"

    first_family, first_path = entries[0]
    first_key = module._work_key(first_family, first_path, "test-config")
    row = {
        "benchmark_set": first_key[0],
        "instance": first_key[1],
        "J": str(first_key[2]),
        "T": f"{first_key[3]}.0",
        "C": first_key[4],
        "config": first_key[5],
        "status": "optimal",
    }
    assert module._row_key(row) == first_key
    assert module._row_key({"instance": first_key[1], "config": first_key[5]}) is None

    columns = ["benchmark_set", "instance", "J", "T", "C", "config", "status"]
    with tempfile.TemporaryDirectory() as directory:
        csv_path = Path(directory) / "results.csv"
        with csv_path.open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            writer.writerow(row)
        completed = completed_reader(csv_path)
    assert first_key in completed
    assert sum(key in completed for key in identities) == 1, (
        "one recorded capacity must not suppress its same-name siblings"
    )


def main():
    bbc_dir = ROOT / "src" / "BBC"
    bnp_dir = ROOT / "src" / "BNP"
    sys.path[:0] = [str(bbc_dir), str(bnp_dir)]
    bbc = load_module("resume_test_bbc_runner", bbc_dir / "benchmark_runner.py")
    bnp = load_module("resume_test_bnp_runner", bnp_dir / "bnp_benchmark_runner.py")

    check_runner(bbc, bbc._instance_features, bbc._load_completed_status)
    check_runner(bnp, bnp._features, bnp._completed)
    print("PASS: BBC and BNP resume keys distinguish every repeated Crama capacity")


if __name__ == "__main__":
    main()
