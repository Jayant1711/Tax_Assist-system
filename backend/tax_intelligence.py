# Summer internship project
"""Tax Intelligence Layer — ANFIS v5 (Sprint 4 vNext, Phase 1-3).

Design contract (ANFIS_VNEXT_ARCHITECTURE.md):
- **Two-pass pattern**: the deterministic TaxEngine computes; this module
  ANNOTATES. ANFIS v5 never writes a tax amount (ADR-001): every rupee in
  its output is either an engine-computed figure or an ESTIMATE clearly
  labeled as one, and the report generator re-prices everything.
- **Multi-head least-squares TSK**: one shared Gaussian rule base over
  the schema-v2 feature vector; per-head linear consequents solved in
  CLOSED FORM (ridge LSE) — the ADR-004 fix for the v4 training failure
  (EE-BAT on all 3,904 params never converged; LSE solves consequents
  exactly, leaving only memberships to search).
- **Deterministic**: seeded (472), pure NumPy inference, no external
  services (ADR-003).
- **Explainability** (ANFIS_EXPLAINABILITY_FRAMEWORK.md): every answer
  decomposes into rule firing strengths and per-feature contributions,
  and every recommendation carries evidence lines derived from the
  session (utilization state) — never from the model alone.

Heads:
  efficiency  — schema-v2 20 features -> composite 0..100 (display)
  savings     — [20 features + delta_norm + head_idx] -> INR estimate
  opportunity — same inputs -> P(engine savings > 0)
Deterministic heads (no ML): per-head utilization, regime advisory
(engine recommendation + band position), confidence estimation.

Schema: anfis-feature-schema/2 — see ANFIS_FEATURE_SCHEMA.md and
`tools/generate_anfis_dataset.py::feature_vector` (the single source of
the feature definition; this module consumes, never re-derives).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:  # graceful degradation mirrors the v4 contract
    HAS_NUMPY = False

SEED = 472
N_FEATURES = 20
SAV_EXTRA = 3                    # delta_norm + head_idx + f21
                                 # (baseline old-regime tax ratio)
N_IN_SAV = N_FEATURES + SAV_EXTRA
RULES = 48                       # LSE tractable: 48 x 23 = 1,104 dims/head
RIDGE = 1e-3
HEADS = ["80c", "80d", "80d_parents", "nps", "24b", "80g", "80e",
         "80tta", "80ttb"]
LIMITS = {"80c": 150_000, "80d": 25_000, "80d_parents": 50_000,
          "nps": 50_000, "24b": 200_000, "80g": 100_000, "80e": 500_000,
          "80tta": 10_000, "80ttb": 50_000}
EFF_WEIGHTS = {"80c": 0.40, "80d": 0.12, "80d_parents": 0.08, "nps": 0.15,
               "24b": 0.10, "80g": 0.05, "80e": 0.05, "80tta": 0.025,
               "80ttb": 0.025}
SCHEMA = "anfis-feature-schema/3"  # /3: +f21 old-tax ratio (23-dim sav)

_WEIGHTS_PATH = Path(__file__).resolve().parent / "anfis_v5_weights.json"


# ---------------------------------------------------------------------------
# TSK core — shared by fit and inference
# ---------------------------------------------------------------------------

def _membership(X: "np.ndarray", means: "np.ndarray",
                sigmas: "np.ndarray") -> "np.ndarray":
    """Gaussian memberships -> normalized firing strengths (B, K)."""
    diff = X[:, None, :] - means[None]              # (B, K, n)
    mf = np.exp(-0.5 * (diff / sigmas[None]) ** 2)
    # ADDITIVE rule combination (Jang 1993 lists product vs sum; the
    # product over 20 dims underflowed even after flooring on this
    # sparse, grid-structured feature space — the sum is robust there
    # and keeps every rule reachable).
    w = mf.sum(axis=2)                              # (B, K)
    return w / w.sum(axis=1, keepdims=True)


def _lse(wbar: "np.ndarray", X: "np.ndarray", y: "np.ndarray",
         ridge: float = RIDGE,
         weights: Optional["np.ndarray"] = None) -> "np.ndarray":
    """Closed-form ridge consequents for one head.

    TSK consequent c_r = [coef_r (n), bias_r]; output =
    sum_r wbar_r(x) * (coef_r . x + bias_r). Stacking [x,1]*wbar_r over
    rules makes the output linear in the consequents -> one ridge solve.
    """
    B, n = X.shape
    K = wbar.shape[1]
    # column r*(n+1)+j = wbar_r * x_j; trailing K columns are biases
    cols = [wbar[:, r:r + 1] * X for r in range(K)]
    cols.append(wbar)
    D = np.concatenate(cols, axis=1)                # (B, K*(n+1))
    # weighted normal equations (qa/class-imbalance: the opportunity
    # head has 0.31% positives — unweighted LSE predicts a constant)
    w_row = np.ones(B, dtype=D.dtype) if weights is None \
        else weights.astype(D.dtype)
    A = (D * w_row[:, None]).T @ D \
        + ridge * np.eye(D.shape[1], dtype=D.dtype)
    rhs = D.T @ (w_row * y)
    return np.linalg.solve(A, rhs).reshape(K, n + 1).astype(np.float64)


def _predict_head(wbar: "np.ndarray", consequents: "np.ndarray",
                  X: "np.ndarray") -> "np.ndarray":
    B = X.shape[0]
    K = wbar.shape[1]
    n = X.shape[1]
    out = np.zeros(B, dtype=np.float64)
    for r in range(K):
        out += wbar[:, r] * (X @ consequents[r, :n] + consequents[r, n])
    return out


def _init_memberships(X: "np.ndarray", K: int,
                      rng: "np.random.RandomState") -> Tuple["np.ndarray",
                                                             "np.ndarray"]:
    """Data-driven MF placement: per-feature quantile means, sigma from
    the feature's spread (the v4 random-init placed means blind)."""
    n = X.shape[1]
    qs = (np.arange(K) + 0.5) / K
    means = np.stack(
        [np.quantile(X[:, j], qs) for j in range(n)], axis=1)  # (K, n)
    spans = np.maximum(X.max(axis=0) - X.min(axis=0), 1e-6)
    # span/6: rules must OVERLAP — span/(2K) collapsed every firing to
    # ~0 and the normalized weights degenerated (v4-run diagnosis)
    sigmas = np.maximum(spans[None, :] / 6.0, 1e-3) * np.ones((K, n))
    return means.astype(np.float64), sigmas.astype(np.float64)


class TaxIntelligence:
    """ANFIS v5 — multi-head, LSE-trained, explainable. See module doc."""

    def __init__(self) -> None:
        self.ready = False
        self.metrics: Dict[str, Any] = {}
        if not HAS_NUMPY:
            return

    # -- training -----------------------------------------------------------
    def fit(self, X_eff: "np.ndarray", y_eff: "np.ndarray",
            X_sav: "np.ndarray", y_sav: "np.ndarray",
            y_opp: "np.ndarray",
            sigma_evals: int = 40, iters: int = 6) -> Dict[str, Any]:
        """Train all heads. y_eff in 0..100; y_sav in INR.

        Search space: per-feature sigma scale only (means stay at
        quantiles) — each candidate is scored by a full LSE fit on a
        6k-row subsample, so every evaluation is an exact solve, not a
        stochastic step. Deterministic via SEED.
        """
        rng = np.random.RandomState(SEED)
        out: Dict[str, Any] = {}

        def _fit_head(X, y, sigma_evals, subsample=6000, weights=None):
            means, sigmas = _init_memberships(X, RULES, rng)
            best = (sigmas.copy(), None, 1e18)
            idx = rng.choice(len(X), min(subsample, len(X)), replace=False)
            Xs, ys = X[idx], y[idx]
            ws = weights[idx] if weights is not None else None
            for scale in [1.0] + list(rng.uniform(0.4, 2.5, sigma_evals)):
                sig_try = sigmas * scale
                wb = _membership(Xs, means, sig_try)
                cons = _lse(wb, Xs, ys, weights=ws)
                pred = _predict_head(wb, cons, Xs)
                loss = float(np.mean((pred - ys) ** 2))
                if loss < best[2]:
                    best = (sig_try.copy(), cons, loss)
            # mean-jitter refinement rounds (coordinate-ish, still LSE)
            sig, cons, loss = best
            for it in range(iters):
                j = rng.randint(X.shape[1])
                cand = sig.copy()
                cand[j] *= rng.uniform(0.7, 1.4)
                wb = _membership(Xs, means, cand)
                c2 = _lse(wb, Xs, ys, weights=ws)
                l2 = float(np.mean((_predict_head(wb, c2, Xs) - ys) ** 2))
                if l2 < loss:
                    sig, cons, loss = cand, c2, l2
            wb_full = _membership(X, means, sig)
            cons_full = _lse(wb_full, X, y, weights=weights)
            return {"means": means, "sigmas": sig,
                    "consequents": cons_full}, loss

        eff_pack, eff_loss = _fit_head(X_eff, y_eff.astype(np.float64),
                                       sigma_evals)
        # savings/opp share one rule base over the 22-dim input
        # CASCADE (imbalance fix): the savings head trains on material
        # rows (engine savings >= INR 100 — 0.3% of rows) PLUS a random
        # conditioning sample of non-material rows at low weight —
        # 146 material rows alone are fewer than the 1,104 LSE params
        # (underdetermined solve).
        material = y_sav >= 100.0
        if not material.any():
            # no material opportunities in the training slice: the
            # savings/opportunity heads stay untrained (predict ~0) and
            # the advisor falls back to engine-only pricing.
            self.eff = None
            self.sav = None
            self.opp = None
            self.ready = True
            return {"eff_train_mse": eff_loss, "sav_train_log1p_mse": None,
                    "opp_train_mse": None, "rules": RULES,
                    "schema": SCHEMA, "sav_heads_skipped": True}
        rng_c = np.random.RandomState(SEED + 1)
        zero_idx = np.where(~material)[0]
        cond_take = rng_c.choice(zero_idx,
                                 size=min(len(zero_idx), 2_500),
                                 replace=False)
        sav_rows = np.concatenate([np.where(material)[0], cond_take])
        sav_w = np.where(material[sav_rows], 20.0, 0.05)
        sav_pack, sav_loss = _fit_head(
            X_sav[sav_rows], np.log1p(np.maximum(y_sav[sav_rows], 0.0)),
            sigma_evals, weights=sav_w)
        # BALANCED opportunity training: all positives + a 20:1 negative
        # sample with positive weight 5 (equal-count balancing left fewer
        # rows than LSE params — underdetermined).
        pos_idx = np.where(y_opp > 0)[0]
        neg_idx = np.where(y_opp == 0)[0]
        rng_b = np.random.RandomState(SEED)
        neg_take = rng_b.choice(neg_idx, size=min(len(neg_idx),
                                                  20 * len(pos_idx)),
                                replace=False)
        bal = np.concatenate([pos_idx, neg_take])
        opp_w = np.where(y_opp[bal] > 0, 5.0, 1.0)
        opp_pack, opp_loss = _fit_head(X_sav[bal], y_opp[bal].astype(
            np.float64), sigma_evals, weights=opp_w)

        self.eff = eff_pack
        self.sav = sav_pack
        self.opp = opp_pack
        self.sav_train_logy_loss = sav_loss
        self.opp_train_loss = opp_loss
        self.ready = True
        out = {"eff_train_mse": eff_loss, "sav_train_log1p_mse": sav_loss,
               "opp_train_mse": opp_loss, "rules": RULES,
               "schema": SCHEMA}
        self.metrics = out
        return out

    # -- inference ----------------------------------------------------------
    def _wb(self, pack: Dict[str, "np.ndarray"],
            X: "np.ndarray") -> "np.ndarray":
        return _membership(X, pack["means"], pack["sigmas"])

    def composite_efficiency(self, X: "np.ndarray") -> "np.ndarray":
        """The SERVED efficiency: the documented v1 composite evaluated
        directly from the schema-v2 features (exact by construction —
        ADR-001 discipline: never serve a lossy learned approximation of
        a formula that can be evaluated exactly). Weights per
        ANFIS_FEATURE_SCHEMA.md."""
        w = np.asarray([
            0.0,   # f1 income_norm (no composite term)
            0.40,  # f2 u80c
            0.12,  # f3 u80d
            0.08,  # f4 u80d_parents
            0.15,  # f5 unps
            0.0,   # f6 u_hra (Rule-2A exemption, not a composite input)
            0.10,  # f7 u24b
            0.05,  # f8 u80e
            0.05,  # f9 u80g
            0.025, # f10 u80tta
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0,   # f19 senior flag (80TTB utilization is not a feature)
            0.0])  # f20 80c_headroom
        # features 2,3,4,5 -> 80c/80d/80d_parents/nps utilization;
        # feature 7 -> 24b; 8 -> 80e; 9 -> 80g; 19 -> 80ttb (senior);
        # the composite's own 30-floor + 68.5 span, clamped [30, 98.5]
        raw = 30.0 + 68.5 * (X @ w)
        return np.clip(raw, 30.0, 98.5)

    def predict_efficiency(self, X: "np.ndarray") -> "np.ndarray":
        """Served efficiency = composite (see above). The learned TSK
        head (model_efficiency) is the registry-documented experiment."""
        return self.composite_efficiency(X)

    def model_efficiency(self, X: "np.ndarray") -> "np.ndarray":
        wb = self._wb(self.eff, X)
        return np.clip(_predict_head(wb, self.eff["consequents"], X),
                       0.0, 100.0)

    def predict_savings(self, X: "np.ndarray") -> "np.ndarray":
        """INR estimate (log-space head, exponentiated — always >= 0)."""
        wb = self._wb(self.sav, X)
        logy = _predict_head(wb, self.sav["consequents"], X)
        return np.maximum(np.expm1(np.clip(logy, 0.0, 18.0)), 0.0)

    def predict_opportunity(self, X: "np.ndarray") -> "np.ndarray":
        wb = self._wb(self.opp, X)
        p = _predict_head(wb, self.opp["consequents"], X)
        return np.clip(p, 0.0, 1.0)

    # -- persistence ---------------------------------------------------------
    def save(self, path: Path) -> None:
        payload = {
            "schema": SCHEMA, "rules": RULES,
            "eff": {k: v.tolist() for k, v in self.eff.items()},
            "sav": {k: v.tolist() for k, v in self.sav.items()},
            "opp": {k: v.tolist() for k, v in self.opp.items()},
            "metrics": self.metrics,
        }
        Path(path).write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "TaxIntelligence":
        obj = cls()
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema") != SCHEMA:
            raise ValueError(f"schema mismatch: {payload.get('schema')}")
        obj.eff = {k: np.asarray(v, dtype=np.float64)
                   for k, v in payload["eff"].items()}
        obj.sav = {k: np.asarray(v, dtype=np.float64)
                   for k, v in payload["sav"].items()}
        obj.opp = {k: np.asarray(v, dtype=np.float64)
                   for k, v in payload["opp"].items()}
        obj.metrics = payload.get("metrics", {})
        obj.ready = HAS_NUMPY
        return obj


# ---------------------------------------------------------------------------
# CA-style advisor (Phase 3) — pure functions over engine output + v5
# ---------------------------------------------------------------------------

def features_v2(session: Dict[str, Any], result: Dict[str, Any],
                profile: Optional[str] = None) -> List[float]:
    """Schema anfis-feature-schema/2 — the ONLY feature definition.

    Consumed by tools/generate_anfis_dataset.py (training rows) and by
    recommend() (inference rows), so train/serve can never diverge.
    Defects fixed vs v4: f6 live Rule-2A leg, f10 statutory 80TTA cap
    (10k), f16 engine regime signal (was a constant 0.3).
    """
    def clip(x: float) -> float:
        return max(0.0, min(1.0, float(x)))

    inc = (float(session.get("salary") or 0)
           + float(session.get("business") or 0)
           + float(session.get("other_income") or 0) + 1e-9)
    gains = session.get("capital_gains") or []
    gains_amt = sum(float(g.get("amount") or 0) for g in gains
                    if isinstance(g, dict)) if isinstance(gains, list) \
        else 0.0
    savings = float(result.get("savings") or 0)
    paid = min(float(result["old_regime"].total_tax),
               float(result["new_regime"].total_tax))
    hra_leg = session.get("hra_received")
    if hra_leg is None:
        hra_leg = session.get("hra") or 0
    return [
        clip(inc / 10_000_000),
        clip(float(session.get("80c") or 0) / 150_000),
        clip(float(session.get("80d") or 0) / 25_000),
        clip(float(session.get("80d_parents") or 0) / 50_000),
        clip(float(session.get("nps") or 0) / 50_000),
        clip(float(hra_leg) / 200_000),
        clip(float(session.get("24b") or 0) / 200_000),
        clip(float(session.get("80e") or 0) / 500_000),
        clip(float(session.get("80g") or 0) / (inc * 0.1 + 1)),
        clip(float(session.get("80tta") or 0) / 10_000),
        clip(float(session.get("80u_80dd") or 0) / 125_000),
        clip(float(session.get("80ddb") or 0) / 100_000),
        clip(float(session.get("80eea") or 0) / 150_000),
        clip(gains_amt / inc),
        clip(float(session.get("business") or 0) / inc),
        1.0 if result.get("recommendation") == "New Regime" else 0.0,
        clip(savings / (inc * 0.1 + 1)),
        clip(paid / (inc * 0.3 + 1)),
        1.0 if int(session.get("age", 30) or 30) >= 60 else 0.0,
        1.0 - clip(float(session.get("80c") or 0) / 150_000),
    ]


def _fmt(amount: float) -> str:
    s = str(int(round(abs(amount))))
    sign = "-" if amount < 0 else ""
    if len(s) <= 3:
        return sign + s
    head, tail = s[:-3], s[-3:]
    groups: List[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return sign + ",".join(groups + [tail])


def utilization(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deterministic per-head utilization (no ML) — the evidence base."""
    age = int(session.get("age", 30) or 30)
    rows = []
    for head, limit in LIMITS.items():
        if head == "80ttb" and age < 60:
            continue
        if head == "80tta" and age >= 60:
            continue
        booked = float(session.get(head, 0) or 0)
        rows.append({"head": head, "booked": booked, "limit": limit,
                     "utilization": round(min(1.0, booked / limit), 4),
                     "headroom": max(0.0, limit - booked)})
    return rows


def recommend(session: Dict[str, Any], engine: Any,
              ti: Optional["TaxIntelligence"],
              top_n: int = 3) -> Dict[str, Any]:
    """CA-style review of the CURRENT session (ADR-001 two-pass).

    Pass 1: TaxEngine prices the session as-booked.
    Pass 2: per-head top-ups are priced by the ENGINE — every rupee in
    the output is engine-computed. The learned heads (when deployed and
    gate-passing) only decorate; with ``ti=None`` the review degrades to
    ENGINE-ONLY intelligence and stays fully available.
    """
    payload = {k: v for k, v in session.items()
               if not str(k).startswith("_") and k not in ("history",)}
    profile = session.get("profile")
    base = engine.calculate_tax_advanced(dict(payload), tax_year="fy_2025_26")
    base_paid = min(float(base["old_regime"].total_tax),
                    float(base["new_regime"].total_tax))

    cands: List[Dict[str, Any]] = []
    for u in utilization(session):
        head, headroom = u["head"], u["headroom"]
        if headroom <= 0:
            continue
        # probe the FULL remaining headroom — partial probes miss the
        # regime-flip cases where the real saving lives (the dataset's
        # positive rows are full-headroom flips, e.g. 80E @ 5L on a 15L
        # salary saves ₹1,300 by flipping the optimal regime)
        delta = headroom
        hyp = dict(payload)
        hyp[head] = float(session.get(head, 0) or 0) + delta
        res2 = engine.calculate_tax_advanced(hyp, tax_year="fy_2025_26")
        paid2 = min(float(res2["old_regime"].total_tax),
                    float(res2["new_regime"].total_tax))
        savings_engine = round(base_paid - paid2, 2)
        # model fields are OPTIONAL: engine pricing is authoritative and
        # always present (ADR-001); the learned heads only decorate when
        # their weights are deployed and gate-passing.
        cands.append({
            "head": head, "delta": delta, "headroom": headroom,
            "savings_engine": savings_engine,
            "savings_estimate": savings_engine,
            "opportunity_probability": None,
            "utilization": u["utilization"],
        })
    # rank: engine-priced savings (authoritative), then head/delta order
    cands.sort(key=lambda c: (-c["savings_engine"],
                              -c["savings_estimate"], c["head"]))
    ranked = cands[:top_n]
    for c in ranked:
        c["reason"] = (
            f"Section {c['head'].upper()} has ₹{_fmt(c['headroom'])} unused "
            f"(currently {_fmt(c['headroom'] and c['utilization'] * 100 or 0)}"
            f"% utilized)")
        c["evidence"] = [
            f"{c['head']} booked: ₹{_fmt(float(session.get(c['head'], 0) or 0))}"
            f" of ₹{_fmt(LIMITS[c['head']])}",
            "engine-priced: a top-up of ₹"
            f"{_fmt(c['delta'])} saves ₹{_fmt(c['savings_engine'])}"
            " (authoritative)",
        ]
        if c["savings_engine"] > 0:
            # confidence is anchored on the ENGINE price (authoritative);
            # the learned opportunity head is an experiment and does not
            # touch served output until its gates pass.
            c["confidence"] = 0.85
            c["estimated_savings"] = c["savings_engine"]
            c["verdict"] = "RECOMMEND"
        else:
            c["confidence"] = 0.30
            c["estimated_savings"] = 0
            c["verdict"] = "NO BENEFIT (current regime ignores this head)"
    gross = sum(float(session.get(k) or 0)
                for k in ("salary", "business", "rental", "other_income",
                          "agriculture"))
    return {
        "available": True,
        "recommendation": base["recommendation"],
        "regime_advisory": {
            "engine_verdict": base["recommendation"],
            "savings_if_switched": round(float(base["savings"]), 2),
        },
        "band_position": (
            "exactly at the ₹12,00,000 87A band" if gross == 1_200_000
            else f"{_fmt(abs(gross - 1_200_000))} "
                 f"{'below' if gross < 1_200_000 else 'above'} the ₹12,00,000 "
                 "Section 87A band (new regime)"
        ) if gross and abs(gross - 1_200_000) <= 50_000 else None,
        "recommendations": ranked,
        "utilization": utilization(session),
    }


#: Module singleton — weights load lazily (v5 candidate or fallback None).
_singleton: Optional[TaxIntelligence] = None


def get_intelligence() -> Optional[TaxIntelligence]:
    """Load the v5 weights if present; None means 'layer offline' and the
    engine/composer degrade gracefully (the v4 path remains active)."""
    global _singleton
    if _singleton is not None:
        return _singleton if _singleton.ready else None
    if not HAS_NUMPY or not _WEIGHTS_PATH.exists():
        return None
    try:
        _singleton = TaxIntelligence.load(_WEIGHTS_PATH)
        return _singleton if _singleton.ready else None
    except Exception:  # noqa: BLE001 — a bad artifact must never 500
        return None


# ---------------------------------------------------------------------------
# Phase 2 — Explainability Engine
# ---------------------------------------------------------------------------

FEATURE_NAMES = [
    "income_norm", "u80c", "u80d", "u80d_parents", "unps", "u_hra",
    "u24b", "u80e", "u80g", "u80tta", "u80u", "u80ddb", "u80eea",
    "cg_ratio", "business_share", "regime_signal", "savings_ratio",
    "tax_ratio", "senior", "80c_headroom",
]

_SAV_FEATURE_NAMES = FEATURE_NAMES + ["delta_norm", "head_idx"]


def explain_efficiency(ti: Optional["TaxIntelligence"],
                       x: List[float]) -> Dict[str, Any]:
    """Decompose the SERVED composite efficiency for one feature vector:
    each contributing head is its statutory weight × its utilization —
    exact, human-readable, and independent of any model (the learned TSK
    decomposition remains available via explain_model_efficiency)."""
    names = ["income_norm", "u80c", "u80d", "u80d_parents", "unps",
             "u_hra", "u24b", "u80e", "u80g", "u80tta", "u80u", "u80ddb",
             "u80eea", "cg_ratio", "business_share", "regime_signal",
             "savings_ratio", "tax_ratio", "senior", "80c_headroom"]
    weights = {"u80c": 0.40, "u80d": 0.12, "u80d_parents": 0.08,
               "unps": 0.15, "u24b": 0.10, "u80e": 0.05, "u80g": 0.05,
               "u80tta": 0.025}
    raw = 30.0 + 68.5 * sum(weights[n] * x[i]
                            for i, n in enumerate(names) if n in weights)
    pred = float(np.clip(raw, 30.0, 98.5)) if HAS_NUMPY else raw
    contrib = [{"feature": n,
                "value": round(float(x[i]), 4),
                "weight": weights[n],
                "contribution_share": round(weights[n] / 0.975, 4)}
               for i, n in enumerate(names) if n in weights]
    contrib.sort(key=lambda c: -c["contribution_share"])
    return {
        "available": True,
        "prediction": round(pred, 1),
        "served_by": "deterministic composite (anfis-feature-schema/2)",
        "top_features": contrib[:4],
        "model_experiment": explain_model_efficiency(ti, x),
    }


def explain_model_efficiency(ti: Optional["TaxIntelligence"],
                             x: List[float]) -> Dict[str, Any]:
    """The LEARNED TSK head's decomposition (experiment, not served):
    mu -> wbar -> consequent contributions -> per-feature attribution."""
    if not (HAS_NUMPY and ti is not None and ti.ready):
        return {"available": False}
    x_arr = np.asarray([x], dtype=np.float64)
    wbar = ti._wb(ti.eff, x_arr)[0]
    cons = ti.eff["consequents"]
    pred = float(ti.model_efficiency(x_arr)[0])
    coef = cons[:, :len(x)]
    contrib = (wbar[:, None] * coef * np.asarray([x])).sum(axis=0)
    total_pos = float(np.abs(contrib).sum()) + 1e-9
    shares = contrib / total_pos
    top = sorted(range(len(x)), key=lambda i: -abs(shares[i]))[:4]
    top_rules = sorted(range(wbar.shape[0]), key=lambda r: -wbar[r])[:3]
    return {
        "available": True,
        "prediction": round(pred, 1),
        "top_features": [
            {"feature": ti_mod_feature_names()[i],
             "value": round(float(x[i]), 4),
             "contribution_share": round(float(shares[i]), 4)}
            for i in top
        ],
        "top_rules": [{"rule": r, "firing": round(float(wbar[r]), 4)}
                      for r in top_rules],
        "effective_rules": round(float(1.0 / np.sum(wbar ** 2)), 1),
    }


def ti_mod_feature_names() -> List[str]:
    return ["income_norm", "u80c", "u80d", "u80d_parents", "unps",
            "u_hra", "u24b", "u80e", "u80g", "u80tta", "u80u", "u80ddb",
            "u80eea", "cg_ratio", "business_share", "regime_signal",
            "savings_ratio", "tax_ratio", "senior", "80c_headroom"]


def advisor_block(session: Dict[str, Any], engine: Any,
                  ti: Optional[TaxIntelligence]) -> Optional[str]:
    """Phase 5 — the composer-facing intelligence block (top-1 only).

    Format: recommendation + reason + confidence + estimated savings +
    next best action. Returns None when the model finds nothing material
    or the engine prices zero benefit — the reply then stays exactly as
    the composer built it (ADR-001: no invented value enters the reply).
    Engine-only mode (ti=None) still recommends: every rupee cited is
    engine-priced.
    """
    try:
        review = recommend(session, engine, ti, top_n=1)
    except Exception:  # noqa: BLE001 — intelligence must never break a turn
        return None
    if not review.get("available") or not review.get("recommendations"):
        return None
    rec = review["recommendations"][0]
    if rec["verdict"] != "RECOMMEND" or rec["estimated_savings"] <= 0:
        return None
    head = rec["head"].upper()
    return (f"\n🧠 **Best opportunity**: top up Section {head} by "
            f"₹{_fmt(rec['delta'])} → est. savings "
            f"₹{_fmt(rec['estimated_savings'])} "
            f"(confidence {int(rec['confidence'] * 100)}%; engine-verified "
            "in your report). "
            f"Why: {rec['reason'].rstrip('.')}.")




# ---------------------------------------------------------------------------
# Phase 6 — EXACT RULE HEADS (forensics-derived, engine-priced)
# ---------------------------------------------------------------------------
# ANFIS_ROOT_CAUSE_REPORT.md measured: (a) y_opp ⟺ regime_signal == 0 with
# zero exceptions on all 76,960 rows; (b) the savings label is exactly
# linear in the base/hypothetical min-paid ratios (val MAPE 1.6e-14);
# (c) the additive TSK rule base dilutes separable signal as rule count
# grows (AUC 1.0 → 0.30). The v5 deployment answer is therefore NOT a
# bigger neural fit — it is EXACT RULE HEADS over the engine two-pass:
# the "prediction" IS the engine computation, so P/R/MAPE are correct by
# construction and every rupee stays ADR-001-authoritative. The learned
# TSK heads remain registry-documented experiments.


def rule_opportunity(savings_engine: float) -> float:
    """Exact opportunity rule: 1.0 iff the engine prices a strictly
    positive saving for the top-up (the label definition, engine-priced)."""
    return 1.0 if savings_engine > 0 else 0.0


def rule_savings(savings_engine: float) -> float:
    """Exact savings rule: the engine-priced delta, unmodified."""
    return round(max(0.0, savings_engine), 2)


def rule_confidence(savings_engine: float) -> float:
    """Confidence for an exact-rule recommendation: 0.85 when the engine
    prices a real benefit (authoritative two-pass), 0.30 otherwise."""
    return 0.85 if savings_engine > 0 else 0.30
