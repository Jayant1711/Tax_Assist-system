# Summer internship project
"""ANFIS vNext dataset generator — Sprint 4 Phase 7.

Ground truth comes EXCLUSIVELY from the deterministic TaxEngine
(ADR-001): every tax figure, every savings delta, every recommendation
ranking in the emitted datasets is computed by
``TaxEngine.calculate_tax_advanced`` before/after a hypothetical booking.
Nothing here invents a label; the only defined quantity is the
**efficiency composite**, a documented display formula over
engine-validated session values (identical to the engine's own
numpy-absent fallback path, widened to all deduction heads).

Outputs (under ``data/anfis_v1/``, created on demand):
  utilization.jsonl    per scenario × deduction head: booked, statutory
                       limit, utilization ratio, remaining headroom
  optimization.jsonl   per scenario × opportunity: baseline engine taxes,
                       hypothetical booking, re-computed taxes, engine
                       savings delta, recommended regime, rank order
  recommendation.jsonl per scenario: opportunities ranked by the
                       ENGINE-computed savings (the ranking ground truth)
  features.npz         X (float32, exactly the 20 production features in
                       score_efficiency order), y_eff (ground-truth
                       efficiency), y_savings_top (engine delta for the
                       top-ranked opportunity), scenario_id — the drop-in
                       training matrix for the existing 20-input ANFIS.

Deterministic: fixed seed, closed value grids, no RNG anywhere.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tax_engine import TaxEngine  # noqa: E402
from tax_intelligence import features_v2  # noqa: E402 — single source

OUT_DIR = Path(__file__).resolve().parents[2] / "data" / "anfis_v1"

# --- statutory limits (display/schema constants; docs/tax-verification.md)
LIMITS: Dict[str, float] = {
    "80c": 150_000,        # Section 80C(1)
    "80d": 25_000,         # Section 80D self/family
    "80d_parents": 50_000, # Section 80D parents (senior tier)
    "nps": 50_000,         # Section 80CCD(1B)
    "24b": 200_000,        # Section 24(b) self-occupied
    "80g": 100_000,        # sampled claim; actual deduction is
                           # category/qualifying-limit driven by the engine
    "80e": 500_000,        # Section 80E interest (no statutory cap; sample)
    "80tta": 10_000,       # Section 80TTA
    "80ttb": 50_000,       # Section 80TTB (senior)
}
# v1 efficiency composite weights (documented display metric). 80ttb
# carries NO weight: its utilization has no schema-v2 feature (senior-
# gated), so a labeled term the features cannot express would make the
# label unverifiable from inputs.
EFF_WEIGHTS: Dict[str, float] = {
    "80c": 0.40, "80d": 0.12, "80d_parents": 0.08, "nps": 0.15,
    "24b": 0.10, "80g": 0.05, "80e": 0.05, "80tta": 0.025, "80ttb": 0.0,
}

# Senior Citizen exercises the senior slabs + 80TTB gating (qa finding 7)
PROFILES: List[Optional[str]] = ["Salaried", "Business Owner",
                                 "Senior Citizen", None]
INCOMES = [300_000, 500_000, 800_000, 1_000_000, 1_150_000, 1_250_000,
           1_400_000, 1_500_000, 1_650_000, 1_800_000, 2_000_000,
           2_400_000, 2_700_000, 3_000_000, 3_500_000, 5_000_000,
           8_000_000, 12_000_000, 20_000_000, 50_000_000]
# booked-value grids per head (0 = head unused → the opportunity space)
GRID: Dict[str, List[float]] = {
    "80c": [0, 50_000, 100_000, 150_000],
    "80d": [0, 25_000],
    "80d_parents": [0, 50_000],
    "nps": [0, 25_000, 50_000],
    "24b": [0, 100_000, 200_000],
    "80g": [0, 20_000, 50_000],
    "80e": [0, 200_000],
    "80tta": [0, 10_000],
    "80ttb": [0, 50_000],
}
# opportunity deltas probed per head (hypothetical top-ups the engine prices)
DELTAS: Dict[str, List[float]] = {
    "80c": [25_000, 50_000],
    "80d": [25_000],
    "80d_parents": [25_000, 50_000],
    "nps": [25_000, 50_000],
    "24b": [100_000],
    "80g": [20_000],
    "80e": [100_000],
    "80tta": [10_000],
    "80ttb": [50_000],
}


def base_session(profile: Optional[str], income: float,
                 booked: Dict[str, float]) -> Dict[str, Any]:
    """A session the way the API validator would hand it to the engine."""
    sess: Dict[str, Any] = {"id": "anfis_gen", "age": 35}
    if profile:
        sess["profile"] = profile
    if profile == "Business Owner":
        sess["business"] = income
    else:
        sess["salary"] = income
    for head, amount in booked.items():
        if amount:
            sess[head] = amount
    sess["has_parents"] = bool(booked.get("80d_parents"))
    sess["has_home_loan"] = bool(booked.get("24b"))
    # Phase 5 expansion inputs: Rule-2A legs + capital gains — the old
    # regime interacts with both, and the v1 grid had neither (the
    # measured cause of the 0.31% positive density)
    if booked.get("hra_received"):
        sess["hra_received"] = booked["hra_received"]
        sess["rent_paid"] = booked.get("rent_paid", 0)
        sess["is_metro"] = bool(booked.get("is_metro", True))
    if booked.get("cg_equity_ltcg"):
        sess["capital_gains"] = [{"type": "equity_ltcg",
                                  "amount": booked["cg_equity_ltcg"],
                                  "holding": "unknown"}]
    elif booked.get("cg_stcg"):
        sess["capital_gains"] = [{"type": "equity_stcg",
                                  "amount": booked["cg_stcg"],
                                  "holding": "unknown"}]
    return sess


def engine_call(engine: TaxEngine, sess: Dict[str, Any]) -> Dict[str, Any]:
    return engine.calculate_tax_advanced(dict(sess), tax_year="fy_2025_26")


def efficiency_ground_truth(booked: Dict[str, float],
                            age: int) -> Tuple[float, Dict[str, float]]:
    """The documented v1 composite — engine-validated inputs only.

    Same spirit as the engine's numpy-absent fallback (a deterministic
    display formula), widened to all heads. Utilization = booked/limit
    clipped to [0, 1]; 80TTB counts only for seniors (60+), 80TTA only
    below 60 — the statutory gating the engine itself applies.
    """
    senior = age >= 60
    util: Dict[str, float] = {}
    eff = 0.0
    for head, weight in EFF_WEIGHTS.items():
        if head == "80ttb" and not senior:
            util[head] = 0.0
            continue
        if head == "80tta" and senior:
            util[head] = 0.0
            continue
        limit = LIMITS[head]
        u = max(0.0, min(1.0, float(booked.get(head, 0) or 0) / limit))
        util[head] = round(u, 4)
        eff += weight * u
    return round(min(98.5, max(30.0, 30.0 + 68.5 * eff)), 2), util


def feature_vector(sess: Dict[str, Any], result: Dict[str, Any],
                   profile: Optional[str]) -> List[float]:
    """Delegates to tax_intelligence.features_v2 (schema v2, single
    source of truth — train/serve can never diverge)."""
    return features_v2(sess, result, profile)


def main() -> int:
    engine = TaxEngine()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    util_rows: List[Dict[str, Any]] = []
    opt_rows: List[Dict[str, Any]] = []
    rec_rows: List[Dict[str, Any]] = []
    X: List[List[float]] = []
    y_eff: List[float] = []
    y_top: List[float] = []
    scenario_ids: List[str] = []

    scenario_no = 0
    EXP_INCOMES = [2_400_000, 3_000_000, 5_000_000, 8_000_000,
                   12_000_000, 20_000_000, 50_000_000]
    expansion = [(p, i, c)
                 for p in PROFILES
                 for i in EXP_INCOMES
                 for c in _expansion_bookings()]
    base_grid = [(p, i, c) for p, i, c in
                 itertools.product(PROFILES, INCOMES,
                                   _sampled_bookings())]
    for profile, income, combo in itertools.chain(base_grid, expansion):
        scenario_no += 1
        sid = f"scn_{scenario_no:05d}"
        age = 35 if profile != "Senior Citizen" else 67
        booked = dict(combo)
        if profile == "Senior Citizen":
            booked.pop("80tta", None)  # statutory gating mirrors the engine
        else:
            booked.pop("80ttb", None)
        sess = base_session(profile, income, booked)
        sess["age"] = age
        base = engine_call(engine, sess)

        eff_gt, utils = efficiency_ground_truth(booked, age)
        for head, u in utils.items():
            util_rows.append({
                "scenario_id": sid, "profile": profile or "General",
                "gross_income": income, "head": head,
                "booked": float(booked.get(head, 0) or 0),
                "limit": LIMITS[head], "utilization": u,
                "remaining": round(max(0.0, LIMITS[head]
                                       - float(booked.get(head, 0) or 0)), 2),
            })

        # baseline paid = the engine's own regime choice
        base_paid = min(float(base["old_regime"].total_tax),
                        float(base["new_regime"].total_tax))
        X.append(feature_vector(sess, base, profile))
        y_eff.append(eff_gt)

        opportunities: List[Dict[str, Any]] = []
        for head in LIMITS:
            if profile == "Senior Citizen" and head == "80tta":
                continue
            if profile != "Senior Citizen" and head == "80ttb":
                continue
            headroom = LIMITS[head] - float(booked.get(head, 0) or 0)
            if headroom <= 0:
                continue
            deltas = list(DELTAS[head])
            if headroom not in deltas:
                deltas.append(headroom)  # full-headroom probe: regime flips
            for delta in deltas:
                delta = min(delta, headroom)
                if delta <= 0:
                    continue
                hypothetical = dict(booked)
                hypothetical[head] = float(booked.get(head, 0) or 0) + delta
                sess2 = base_session(profile, income, hypothetical)
                sess2["age"] = age
                res2 = engine_call(engine, sess2)
                paid2 = min(float(res2["old_regime"].total_tax),
                            float(res2["new_regime"].total_tax))
                savings = round(base_paid - paid2, 2)
                if savings <= 0 and head != "80g":
                    # an engine-priced zero-savings probe is still signal
                    pass
                hyp_sess = dict(sess2)
                x_hyp = feature_vector(hyp_sess, res2, profile)
                head_idx = list(LIMITS).index(head)
                opt_rows.append({
                    "scenario_id": sid, "head": head, "delta": delta,
                    "session": {k: v for k, v in sess.items()
                                if k != "id"},
                    "baseline_paid": base_paid,
                    "hypothetical_paid": paid2,
                    "savings_engine": savings,
                    "recommended_regime_base": base["recommendation"],
                    "new_regime_optimal":
                        float(res2["new_regime"].total_tax)
                        <= float(res2["old_regime"].total_tax),
                    "x_hyp": x_hyp,
                    "delta_norm": round(delta / LIMITS[head], 4),
                    "head_idx": head_idx,
                    # f21 (forensics EXP-F2): the BASELINE old-regime tax
                    # ratio — the marginal-rate context the savings/
                    # opportunity heads cannot see otherwise (engine-
                    # computed, min(1, ·) clipped).
                    "f21_old_tax_ratio": round(
                        min(1.0, float(base["old_regime"].total_tax)
                            / (income * 0.3 + 1)), 6),
                })
                opportunities.append({"head": head, "delta": delta,
                                      "savings_engine": savings})

        opportunities.sort(key=lambda o: (-o["savings_engine"],
                                          o["head"], -o["delta"]))
        for rank, opp in enumerate(opportunities, 1):
            rec_rows.append({"scenario_id": sid, "rank": rank, **opp})
        if opportunities:
            y_top.append(opportunities[0]["savings_engine"])
        else:
            y_top.append(0.0)
        scenario_ids.append(sid)

    _write_jsonl("utilization.jsonl", util_rows)
    _write_jsonl("optimization.jsonl", opt_rows)
    _write_jsonl("recommendation.jsonl", rec_rows)
    try:
        import numpy as np
        np.savez_compressed(OUT_DIR / "features.npz",
                            X=np.asarray(X, dtype=np.float32),
                            y_eff=np.asarray(y_eff, dtype=np.float32),
                            y_top=np.asarray(y_top, dtype=np.float32),
                            scenario_id=np.asarray(scenario_ids))
        # per-opportunity savings/opportunity training matrix (schema v2):
        # rows = [x_hyp(20), delta_norm, head_idx/9]; labels = engine
        # savings (INR) and the >0 opportunity flag.
        sav_x, sav_y, opp_y = [], [], []
        for row in opt_rows:
            sav_x.append(list(row["x_hyp"]) + [row["delta_norm"],
                                               row["head_idx"] / 9.0,
                                               row["f21_old_tax_ratio"]])
            sav_y.append(float(row["savings_engine"]))
            opp_y.append(1.0 if row["savings_engine"] > 0 else 0.0)
        np.savez_compressed(OUT_DIR / "savings.npz",
                            X=np.asarray(sav_x, dtype=np.float32),
                            y_sav=np.asarray(sav_y, dtype=np.float32),
                            y_opp=np.asarray(opp_y, dtype=np.float32))
    except ImportError:  # numpy-absent fallback: JSON matrix
        _write_jsonl("features.jsonl",
                     [{"scenario_id": s, "x": x, "y_eff": e, "y_top": t}
                      for s, x, e, t in zip(scenario_ids, X, y_eff, y_top)])

    print(f"scenarios: {scenario_no}")
    print(f"utilization rows: {len(util_rows)}  optimization rows: "
          f"{len(opt_rows)}  recommendation rows: {len(rec_rows)}")
    print(f"feature matrix: {len(X)} x {len(X[0]) if X else 0}")
    print(f"output dir: {OUT_DIR}")
    return 0


def _sampled_bookings() -> List[Dict[str, float]]:
    """Deterministic scenario grid: full single-head sweeps + a seeded
    sample of multi-head combinations (bounded, reproducible)."""
    combos: List[Dict[str, float]] = [{}]
    heads = list(GRID)
    # full sweep: one head at a time
    for head in heads:
        for value in GRID[head][1:]:
            combos.append({head: value})
    # pairs (bounded sweep): every head pair at its mid value
    for i, h1 in enumerate(heads):
        for h2 in heads[i + 1:]:
            combos.append({h1: GRID[h1][1], h2: GRID[h2][1]})
    # seeded multi-head fill (5 of 9 heads) — deterministic stride
    stride = 7
    for step in range(1200):
        combo: Dict[str, float] = {}
        for j, head in enumerate(heads):
            values = GRID[head]
            combo[head] = values[(step * stride + j) % len(values)]
        combos.append(combo)
    # dedupe while preserving order
    seen = set()
    unique = []
    for c in combos:
        key = tuple(sorted(c.items()))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _expansion_bookings() -> List[Dict[str, float]]:
    """Phase 5 expansion strata (DATASET_QUALITY_REPORT_V2): the v1 grid
    under-sampled the OLD-regime-optimal corner — high incomes with heavy
    deductions, HRA legs, capital gains and senior heads. Forensics
    measured the v1 positive concentration: 80.7% of positives are 80e
    full-headroom flips; these strata widen the surface."""
    combos: List[Dict[str, float]] = []
    # S1: heavy-deduction salaried (old-regime-optimal corner)
    for nps in [0, 50_000]:
        for hra in [0, 300_000]:
            combos.append({"80c": 150_000, "80d": 25_000, "nps": nps,
                           "24b": 200_000, "80e": 200_000, "80g": 50_000,
                           "hra_received": hra, "rent_paid": 250_000 if hra
                           else 0, "is_metro": True})
    # S2: CG interactions (equity LTCG around the 1.25L 112A exempt band)
    for cg in [100_000, 125_000, 300_000, 1_200_000]:
        for stcg in [0, 150_000]:
            combos.append({"80c": 150_000, "cg_equity_ltcg": cg,
                           "cg_stcg": stcg})
    # S3: HRA-only salaried (Rule 2A legs, metro vs non-metro)
    for hra in [120_000, 240_000, 360_000]:
        for metro in [True, False]:
            combos.append({"hra_received": hra, "rent_paid": 240_000,
                           "is_metro": metro})
    # S4: senior heads (80TTB is senior-gated in the engine)
    for ttb in [0, 50_000]:
        for tta in [0, 10_000]:
            combos.append({"80ttb": ttb, "80tta": tta, "80c": 100_000})
    # S6: flip-hunter — the near-flip income band (regime choice flips
    # with heavy deductions around 12L-30L; the measured positive
    # concentration zone)
    for income_band in [1_200_000, 1_500_000, 1_800_000, 2_100_000,
                        2_400_000, 2_700_000, 3_000_000, 3_500_000]:
        for step in range(48):
            combo = {"80c": 150_000, "80d": 25_000, "nps": 50_000,
                     "24b": 200_000, "80e": 200_000, "80g": 50_000,
                     "hra_received": 300_000, "rent_paid": 250_000,
                     "is_metro": True}
            knock = list(combo)[(step * 3) % len(combo)]
            combo[knock] = 0
            if step % 4 == 1:
                combo["cg_equity_ltcg"] = 300_000
            combos.append(combo)
    # S5: near-max fills with one head knocked out (near-max, not all-max
    # — all-max priced zero benefit in qa probes)
    for step in range(120):
        combo = {"80c": 150_000, "80d": 25_000, "nps": 50_000,
                 "24b": 200_000, "80e": 200_000, "80g": 50_000,
                 "hra_received": 300_000, "rent_paid": 250_000,
                 "is_metro": True}
        knock = list(combo)[step % len(combo)]
        combo[knock] = 0
        if step % 3 == 0:
            combo["cg_equity_ltcg"] = 300_000
        elif step % 3 == 1:
            combo["cg_stcg"] = 150_000
        combos.append(combo)
    seen, unique = set(), []
    for c in combos:
        key = tuple(sorted((k, v) for k, v in c.items() if v))
        if key and key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _write_jsonl(name: str, rows: List[Dict[str, Any]]) -> None:
    with (OUT_DIR / name).open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
