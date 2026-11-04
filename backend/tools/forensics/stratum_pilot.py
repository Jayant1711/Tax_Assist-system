# STRATUM PILOT — measured positive yields per candidate Phase-5 stratum.
# Replica of the generator's probe mechanics (base session + engine top-up
# pricing) run purely in-memory; validates/refines the parallel Phase-5
# strata design (old-regime-optimal corner, HRA legs, CG ~1.25L, seniors).
import json
from pathlib import Path

import numpy as np

REPO = Path(r"C:\Users\lenovo\Desktop\Tax_Assist-system-main\Tax_Assist-system-main")
OUT = Path(__file__).resolve().parent / "out"

import sys
sys.path.insert(0, str(REPO / "backend"))
from tax_engine import TaxEngine  # noqa: E402

LIMITS = {"80c": 150_000, "80d": 25_000, "80d_parents": 50_000,
          "nps": 50_000, "24b": 200_000, "80g": 100_000, "80e": 500_000,
          "80tta": 10_000, "80ttb": 50_000}
N_SCEN = 300


def make_session(rng, income, profile, booked, age, hra=None, rent=None,
                 metro=None, cg=None):
    s = {"age": age}
    if profile:
        s["profile"] = profile
    if profile == "Business Owner":
        s["business"] = income
    else:
        s["salary"] = income
    for h, v in booked.items():
        if v:
            s[h] = v
    s["has_parents"] = bool(booked.get("80d_parents"))
    s["has_home_loan"] = bool(booked.get("24b"))
    if hra is not None:
        s["hra_received"] = hra
    if rent is not None:
        s["rent_paid"] = rent
    if metro is not None:
        s["is_metro"] = metro
    if cg:
        s["capital_gains"] = cg
    return s


def probes(rng, booked, age, light=False):
    """(head, delta) probes: full headroom + one mid delta per head."""
    out = []
    senior = age >= 60
    for h, lim in LIMITS.items():
        if h == "80tta" and senior:
            continue
        if h == "80ttb" and not senior:
            continue
        headroom = lim - float(booked.get(h, 0) or 0)
        if headroom <= 0:
            continue
        out.append((h, headroom))
        mid = rng.choice([0.25, 0.5]) * headroom
        out.append((h, float(round(mid))))
    return out


def run_stratum(engine, rng, name, n_scen, sess_fn, probe_fn=probes):
    pos = 0
    rows = 0
    pos_savings = []
    scen_with_pos = 0
    by_head = {}
    by_probe = {"full": 0, "mid": 0}
    pos_by_head = {}
    calls = 0
    for _ in range(n_scen):
        sess, booked, age = sess_fn(rng)
        base = engine.calculate_tax_advanced(dict(sess),
                                             tax_year="fy_2025_26")
        calls += 1
        base_paid = min(float(base["old_regime"].total_tax),
                        float(base["new_regime"].total_tax))
        sc_pos = 0
        for h, d in probe_fn(rng, booked, age):
            hyp = dict(sess)
            hyp[h] = float(booked.get(h, 0) or 0) + d
            if h == "80d_parents":
                hyp["has_parents"] = bool(hyp.get("80d_parents"))
            if h == "24b":
                hyp["has_home_loan"] = bool(hyp.get("24b"))
            r2 = engine.calculate_tax_advanced(hyp, tax_year="fy_2025_26")
            calls += 1
            paid2 = min(float(r2["old_regime"].total_tax),
                        float(r2["new_regime"].total_tax))
            sav = round(base_paid - paid2, 2)
            rows += 1
            key = "full" if abs(d - (LIMITS[h] - float(
                booked.get(h, 0) or 0))) < 1e-6 else "mid"
            by_probe[key] = by_probe.get(key, 0) + 1
            by_head[h] = by_head.get(h, 0) + 1
            if sav > 0:
                pos += 1
                sc_pos += 1
                pos_savings.append(sav)
                pos_by_head[h] = pos_by_head.get(h, 0) + 1
        if sc_pos:
            scen_with_pos += 1
    res = {
        "stratum": name, "scenarios": n_scen, "probe_rows": rows,
        "positives": pos,
        "positives_per_scenario": round(pos / n_scen, 3),
        "positive_rate_per_probe": round(pos / rows, 4),
        "scenarios_with_pos_share": round(scen_with_pos / n_scen, 3),
        "mean_pos_savings": round(float(np.mean(pos_savings)), 0)
        if pos_savings else 0,
        "median_pos_savings": round(float(np.median(pos_savings)), 0)
        if pos_savings else 0,
        "positives_by_head": pos_by_head,
        "probes_by_head": by_head, "probes_full_vs_mid": by_probe,
        "engine_calls": calls,
        "scenarios_for_2000_positives": int(np.ceil(2000 * n_scen / pos))
        if pos else None,
    }
    print(json.dumps(res))
    return res


def main() -> None:
    engine = TaxEngine()
    rng = np.random.RandomState(472)
    results = []

    # S1 old-regime-optimal heavy-deduction corner, income 24L-2Cr
    def s1(rng):
        inc = float(np.exp(rng.uniform(np.log(2_400_000),
                                       np.log(20_000_000))))
        booked = {"80c": float(rng.choice([50_000, 100_000, 150_000])),
                  "80d": 25_000.0, "80d_parents": 25_000.0,
                  "nps": float(rng.choice([0, 25_000, 50_000])),
                  "24b": float(rng.choice([0, 100_000, 200_000])),
                  "80e": float(rng.choice([0, 200_000]))}
        age = 35
        sess = make_session(rng, inc, "Salaried", booked, age,
                            hra=float(rng.uniform(0, 0.3 * inc)),
                            rent=float(rng.uniform(0.3, 0.6) * inc),
                            metro=bool(rng.randint(2)))
        return sess, booked, age

    # S2 HRA-leg stratum, income 8L-40L, light other bookings
    def s2(rng):
        inc = float(np.exp(rng.uniform(np.log(800_000),
                                       np.log(4_000_000))))
        hra = float(rng.uniform(0.1, 0.3) * inc)
        booked = {"80c": float(rng.choice([0, 50_000])),
                  "nps": float(rng.choice([0, 25_000]))}
        sess = make_session(rng, inc, "Salaried", booked, 35,
                            hra=hra, rent=hra + float(rng.uniform(
                                0.1, 0.5)) * inc + 20_000,
                            metro=bool(rng.randint(2)))
        return sess, booked, 35

    # S3 CG around the 1.25L 112A exemption, salary 10L-40L
    def s3(rng):
        inc = float(np.exp(rng.uniform(np.log(1_000_000),
                                       np.log(4_000_000))))
        cg_amt = float(rng.uniform(50_000, 250_000))
        booked = {"80c": float(rng.choice([0, 50_000, 100_000]))}
        sess = make_session(rng, inc, "Salaried", booked, 35,
                            cg=[{"type": "equity_ltcg",
                                 "amount": cg_amt}])
        return sess, booked, 35

    # S4 seniors 60-89, 80TTB/80D-senior heavy, income 8L-50L
    def s4(rng):
        inc = float(np.exp(rng.uniform(np.log(800_000),
                                       np.log(5_000_000))))
        age = int(rng.choice([61, 67, 72, 81]))
        booked = {"80c": float(rng.choice([0, 50_000, 150_000])),
                  "80d": float(rng.choice([0, 25_000])),
                  "80d_parents": float(rng.choice([0, 25_000])),
                  "80ttb": float(rng.choice([0, 25_000]))}
        sess = make_session(rng, inc, "Senior Citizen", booked, age,
                            hra=float(rng.uniform(0, 0.2) * inc)
                            if rng.rand() < 0.4 else None,
                            rent=float(rng.uniform(100_000, 400_000))
                            if rng.rand() < 0.4 else None,
                            metro=bool(rng.randint(2)))
        return sess, booked, age

    # S5 control: light-booked regime-flip band 10L-30L (current mechanism)
    def s5(rng):
        inc = float(np.exp(rng.uniform(np.log(1_000_000),
                                       np.log(3_000_000))))
        booked = {"80c": float(rng.choice([0, 50_000])),
                  "nps": float(rng.choice([0, 25_000]))}
        sess = make_session(rng, inc, "Salaried", booked, 35)
        return sess, booked, 35

    # S6 disability/medical legs (dead-feature revival probe)
    def s6(rng):
        inc = float(np.exp(rng.uniform(np.log(800_000),
                                       np.log(3_000_000))))
        booked = {"80c": float(rng.choice([0, 50_000]))}
        sess = make_session(rng, inc, "Salaried", booked, 35)
        sess["80u_80dd_category"] = rng.choice(["40_79", "80_plus"])
        sess["80ddb_expenditure"] = float(rng.choice([40_000, 100_000]))
        return sess, booked, 35

    for name, fn in (("S1_old_regime_heavy_24L_2Cr", s1),
                     ("S2_hra_legs_8L_40L", s2),
                     ("S3_cg_112A_1.25L", s3),
                     ("S4_seniors_8L_50L", s4),
                     ("S5_control_light_flip_10L_30L", s5),
                     ("S6_80u_80ddb_legs", s6)):
        results.append(run_stratum(engine, rng, name, N_SCEN, fn))

    # blended sizing for >= 2000 positives
    blend = {}
    for r in results:
        if r["positives_per_scenario"] > 0:
            blend[r["stratum"]] = r["scenarios_for_2000_positives"]
    total = {
        "strata": results,
        "scenarios_for_2000_singles": blend,
        "note": "sizing = ceil(2000 / (positives per scenario)); strata "
                "are not mutually exclusive in production sampling",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stratum_pilot.json").write_text(json.dumps(total, indent=2),
                                            encoding="utf-8")
    print("PILOT DONE")


if __name__ == "__main__":
    main()
