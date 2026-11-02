"""Shared utilities for the CSE472 NLP research layer.

Design rules (see NLP_SYLLABUS_GAP_ANALYSIS.md §5):
- ONE-WAY dependency: nlp_research may read data/*.jsonl and import pure
  backend modules for analysis; backend/ NEVER imports nlp_research.
- Deterministic: every experiment is seeded; results are CPU-reproducible
  so the viva demo can be re-run offline.
- No production code is modified by anything in this package except the
  sanctioned Phase H response_composer.py.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
PLOTS_DIR = Path(__file__).resolve().parent / "plots"

# The 8-class academic intent taxonomy (validated against the production
# 21-category scheme; mapping table in NLP_SYLLABUS_GAP_ANALYSIS.md §4).
INTENT_CLASSES: list[str] = [
    "salary",
    "business",
    "capital_gains",
    "property",
    "deductions",
    "agriculture",
    "investment",
    "other",
]

# Production-category -> academic-intent mapping (see tax-expert review).
PROD_TO_INTENT: dict[str, str] = {
    "salary": "salary",
    "business": "business",
    "capital_gains": "capital_gains",
    "rental": "property",
    "24b": "property",
    "hra_received": "property",
    "rent_paid": "property",
    "80gg": "deductions",
    "80c": "investment",
    "nps": "investment",
    "80d": "deductions",
    "80d_parents": "deductions",
    "80e": "deductions",
    "80g": "deductions",
    "80tta": "deductions",
    "80ttb": "deductions",
    "80u_80dd": "deductions",
    "80ddb": "deductions",
    "80eea": "deductions",
    "agriculture": "agriculture",
    "other_income": "other",
}


SEED: int = 472

def set_seed(seed: int = 472) -> None:
    """Seed every RNG used by the research layer (numpy/random/torch)."""
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:  # torch optional for the pure-numpy phases
        pass


def ensure_dirs() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_jsonl(paths: list[Path]) -> list[dict]:
    """Read JSONL files, skipping malformed lines (Sprint 4 P0 convention)."""
    records: list[dict] = []
    for p in paths:
        if not p.exists():
            continue
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(rec, dict):
                    records.append(rec)
    return records


def corpus_records() -> list[dict]:
    """All labeled utterance records from the Sprint 4 P0 corpus layout."""
    subdirs = ["corpus", "training", "validation", "test"]
    paths = [DATA_DIR / d / "*.jsonl" for d in subdirs]
    files: list[Path] = []
    for pattern in paths:
        files.extend(sorted(DATA_DIR.glob(str(pattern.relative_to(DATA_DIR)))))
    return load_jsonl(files)


def utterance_and_category(rec: dict) -> tuple[str, str | None] | None:
    """Extract (text, production_category) from a corpus record.

    The P0 schema stores spans as [{text, category, amount, ...}]; the
    utterance-level category is the FIRST span's category (records are
    single-intent by construction of the template builder).
    """
    text = rec.get("text") or rec.get("utterance") or rec.get("user_input")
    if not text:
        return None
    spans = rec.get("spans") or []
    cat = spans[0].get("category") if spans else rec.get("category")
    return text, cat


def seed_vocabulary() -> dict[str, list[str]]:
    """Domain seed vocabulary for embedding evaluation (Phase B).

    Each entry is a probe concept with the surface forms the corpus uses,
    including the Hinglish families already present in production tests.

    CRITICAL: concept class names themselves (investment, insurance, etc.)
    MUST appear as tokens in the vocabulary for analogies to resolve —
    the offset b - a + c only lands on a word that exists in vocab.
    """
    return {
        "investment": ["ppf", "elss", "nsc", "sukanya", "epf", "vpf", "ulip",
                       "investment", "investing", "invest"],
        "insurance": ["mediclaim", "lic", "premium", "health", "swasthya", "bima",
                      "insurance", "insure", "policy"],
        "salary": ["salary", "ctc", "paycheck", "naukri", "kamata", "wages",
                   "income", "earnings", "salary_earner"],
        "deduction": ["deduction", "exemption", "rebate", "80c", "80d", "80g",
                      "deduct", "exempt"],
        "tax": ["tax", "slab", "surcharge", "cess", "regime", "liability",
                "taxpayer", "taxes"],
        "income": ["income", "earnings", "revenue", "turnover", "vyapar", "kamai",
                   "salary", "business_income"],
        "housing": ["rent", "kiraya", "home", "loan", "makan", "ghar", "hra",
                    "housing", "house", "rental"],
        "donation": ["donation", "daan", "charity", "mandir", "trust", "ngo",
                     "donate", "donated"],
        "medical": ["treatment", "ilaaj", "bimari", "hospital", "illness",
                    "medical", "medicine", "healthcare"],
        "savings_interest": ["interest", "byaaj", "fd", "savings", "deposit",
                             "bank_interest", "interest_income"],
        # These words appear in analogies but need extra template coverage
        # to meet min_count and build analogical geometry
        "extra_investment": ["investment"],
        "extra_insurance": ["insurance"],
        "extra_income": ["income"],
        "extra_rent": ["rent"],
        "extra_housing": ["housing"],
        "extra_donation": ["donation"],
        "extra_byaaj": ["byaaj"],
        "extra_savings_interest": ["savings_interest"],
        "extra_makan": ["makan"],
        "extra_bimari": ["bimari"],
        "extra_medical": ["medical"],
        "extra_deduction": ["deduction"],
        "extra_lic": ["lic"],
    }
