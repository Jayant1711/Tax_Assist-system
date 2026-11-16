"""Dataset integrity pin (ML-review P2 closure): the "51,873 positives
(13.73%)" count transcribed into DATASET_REGISTRY.md / the registries /
the paper was a one-time measurement with NO committed assertion — any
generator or engine edit silently orphaned every transcribed count while
the docs claimed reproducibility.

The dataset itself is gitignored (>100 MB), so this test SKIPS when the
dataset is absent; when it IS present locally it enforces the pinned
counts (deterministic under seed 472 for a given tax-math baseline —
re-pin deliberately, with a registry citation, when the engine changes,
exactly like the parity fixture). An operator may additionally export
TAX_DATASET_SHA256 (hash of features.npz + savings.npz) to enforce byte
identity on a machine where BLAS/kernel drift makes bytes unstable.
"""
import hashlib
import json
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = REPO_ROOT / "data" / "anfis_v3"

# The registry pin (DATASET_REGISTRY.md, anfis-v3 row): deterministic
# under the seeded sampler for the CURRENT tax-math baseline.
PINNED_SCENARIOS = 21_964
PINNED_OPPORTUNITY_ROWS = 377_753
PINNED_POSITIVES = 51_873


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.mark.skipif(not (DATASET_DIR / "optimization.jsonl").exists(),
                    reason="anfis_v3 dataset not present on this machine "
                           "(gitignored >100MB) — nothing to verify")
class TestAnfisV3DatasetPin:
    def test_row_counts_match_the_registry(self) -> None:
        scenarios = rows = positives = 0
        seen_ids = set()
        with open(DATASET_DIR / "optimization.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                rows += 1
                seen_ids.add(row.get("scenario_id"))
                if float(row.get("savings_engine") or 0) > 0:
                    positives += 1
        scenarios = len(seen_ids)
        assert scenarios == PINNED_SCENARIOS, (
            f"scenarios {scenarios} != pinned {PINNED_SCENARIOS} — the "
            "sampler or engine changed; re-pin the registries WITH a "
            "citation, like the parity fixture")
        assert rows == PINNED_OPPORTUNITY_ROWS, (
            f"opportunity rows {rows} != pinned {PINNED_OPPORTUNITY_ROWS}")
        assert positives == PINNED_POSITIVES, (
            f"positives {positives} != pinned {PINNED_POSITIVES} — every "
            "transcribed '51,873 positives (13.73%)' is now stale")

    def test_optional_byte_pin(self) -> None:
        expected = os.environ.get("TAX_DATASET_SHA256")
        if not expected:
            pytest.skip("TAX_DATASET_SHA256 not exported — byte pin "
                        "optional (kernel drift makes bytes machine-"
                        "sensitive; the COUNT pins above are the real gate)")
        digest = hashlib.sha256()
        for name in ("features.npz", "savings.npz"):
            digest.update(_sha256(DATASET_DIR / name).encode())
        assert digest.hexdigest() == expected, (
            "dataset bytes drifted from the exported pin — regenerate or "
            "re-export")
