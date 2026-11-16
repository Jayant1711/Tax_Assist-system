// Tax Assist — Technical Evidence Deck (companion to the main presentation)
// Answers the professor's questions per component: where is the code,
// what data, how many parameters, how long did it train, what did it measure.
// 14 slides · 13.33x7.5
const pptxgen = require("pptxgenjs");

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "Jayant (12406581)";
p.title = "Tax Assist — Technical Evidence Deck";

// ---- Design system (same language as the main deck) ----------------------
const W = 13.33, H = 7.5, M = 0.55;
const BG = "F6F8FA";
const DARK = "0E2A44";
const PRIMARY = "1A4A73";
const TINT = "E4EDF5";
const ACCENT = "E8590C";
const TEXT = "182230";
const MUTED = "5D6C7B";
const LINE = "D8E0E8";
const WHITE = "FFFFFF";
const GREEN = "2E7D4F";
const RED = "B23B3B";
const LIGHTTXT = "D7E3F0";
const F = "Segoe UI";
const MONO = "Consolas";
const KICKER = "TAX ASSIST · TECHNICAL EVIDENCE";

const bu = () => ({ code: "2022", indent: 12 });
const sh = () => ({ type: "outer", color: "8B98A5", blur: 6, offset: 2, angle: 90, opacity: 0.16 });

function header(s, title) {
  s.addText(KICKER, {
    x: M, y: 0.42, w: 9.5, h: 0.3, margin: 0,
    fontFace: F, fontSize: 12, bold: true, color: ACCENT, charSpacing: 2,
  });
  s.addText(title, {
    x: M, y: 0.72, w: W - 2 * M, h: 0.62, margin: 0,
    fontFace: F, fontSize: 30, bold: true, color: TEXT,
  });
}
function pageNo(s) {
  PAGE += 1;
  s.addText(String(PAGE).padStart(2, "0"), {
    x: W - 1.0, y: H - 0.52, w: 0.5, h: 0.3, margin: 0, align: "right",
    fontFace: F, fontSize: 11, color: MUTED,
  });
}
let PAGE = 1;
function codeChip(s, x, y, w, text, o = {}) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h: o.h || 0.34, rectRadius: 0.06,
    fill: { color: o.fill || DARK },
  });
  s.addText(text, {
    x: x + 0.14, y, w: w - 0.28, h: o.h || 0.34, margin: 0, valign: "middle",
    fontFace: MONO, fontSize: o.size || 10.5, color: o.color || "9FD8B4",
  });
}
function card(s, x, y, w, h) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.07,
    fill: { color: WHITE }, line: { color: LINE, width: 0.75 }, shadow: sh(),
  });
}
function sectionLabel(s, x, y, w, text, color = PRIMARY) {
  s.addText(text, {
    x, y, w, h: 0.3, margin: 0, fontFace: F, fontSize: 14.5, bold: true, color,
  });
}
function bullets(s, x, y, w, h, items, opts = {}) {
  const runs = items.map((it) => ({
    text: it.t,
    options: { bullet: bu(), breakLine: true, bold: !!it.b, color: it.c || (it.b ? PRIMARY : TEXT), fontFace: it.mono ? MONO : F },
  }));
  s.addText(runs, {
    x, y, w, h, margin: 0, valign: "top",
    fontFace: F, fontSize: opts.size || 13, color: TEXT,
    paraSpaceAfter: opts.gap == null ? 7 : opts.gap,
  });
}
// facts table for one model: DATA / PARAMS / TRAINING / EVALUATION
function factsTable(s, x, y, w, rows, rowH = 0.4) {
  const tbl = [[
    { text: "Data", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
    { text: "Parameters", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
    { text: "Training", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
    { text: "Evaluation", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
  ]].concat(rows.map((r) => r.map((cell) => ({ text: cell, options: { color: TEXT, fill: { color: WHITE } } }))));
  s.addTable(tbl, {
    x, y, w, colW: [w * 0.30, w * 0.20, w * 0.22, w * 0.28],
    border: { pt: 0.75, color: LINE }, fontFace: F, fontSize: 11.5,
    valign: "middle", rowH,
  });
}

// ---------------------------------------------------------------------------
// SLIDE 1 — Title (dark)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addText("COMPANION TO THE MAIN PRESENTATION", {
    x: M + 0.15, y: 1.5, w: 11, h: 0.35, margin: 0,
    fontFace: F, fontSize: 13, bold: true, color: ACCENT, charSpacing: 2,
  });
  s.addText("Technical Evidence Deck", {
    x: M + 0.15, y: 1.9, w: 12, h: 1.0, margin: 0,
    fontFace: F, fontSize: 54, bold: true, color: WHITE,
  });
  s.addText(
    "For every claim in the main deck: where the code lives, what data was used, " +
    "how many parameters, how long it trained, and what it measured.",
    { x: M + 0.15, y: 3.1, w: 11.6, h: 0.8, margin: 0,
      fontFace: F, fontSize: 16, color: LIGHTTXT, lineSpacingMultiple: 1.15 }
  );
  s.addText([
    { text: "Jayant (12406581) · Roll No. RK4P24MZA06", options: { breakLine: true } },
    { text: "CSE472 · Deep Learning for Natural Language Processing · November 2026", options: { breakLine: true } },
    { text: "github.com/Jayant1711/Tax_Assist-system", options: {} },
  ], {
    x: M + 0.15, y: 5.4, w: 9.5, h: 1.1, margin: 0,
    fontFace: F, fontSize: 12.5, color: "9FB2C4", paraSpaceAfter: 4,
  });
}

// ---------------------------------------------------------------------------
// SLIDE 2 — The code map
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Where everything lives");
  const rows = [
    ["backend/tax_engine.py", "THE calculator — FY rule registries, leave-one-out impact", ":238, :520"],
    ["backend/tax_intelligence.py", "composite efficiency, exact rule heads, ranked review", ":250, :418, :681"],
    ["backend/nlp_engine.py", "conversation chain, guards, closing intelligence", ":119, :647, :676"],
    ["backend/ai_models.py", "UniversalParser, SemanticAttention, ANFIS v4", ":25, :142, :637"],
    ["backend/fuzzy_ca.py", "explainable CA rule base (authored, readable)", ":158, :301, :333"],
    ["backend/ca_plans.py", "engine-priced savings plans", ":49, :86"],
    ["backend/calibration.py", "ECE instrument + known-answer canary", ":24, :62"],
    ["backend/db.py · main.py", "adoption store, funnel, apply endpoints", "db:509 · main:1177-1237"],
    ["nlp_research/", "research models: intent, NER, embeddings, seq2seq, BERT/GPT-2/T5", "phase_a-i"],
    ["backend/tools/", "dataset generator, ANFIS trainers, eval CLI, forensics", "train_anfis_v5.py et al."],
  ];
  let y = 1.6;
  for (const [path, role, anchor] of rows) {
    codeChip(s, M, y + 0.03, 3.6, path);
    s.addText(role, { x: M + 3.8, y: y + 0.02, w: 6.3, h: 0.4, margin: 0, valign: "middle", fontFace: F, fontSize: 11.5, color: TEXT });
    s.addText(anchor, { x: W - 2.6, y: y + 0.02, w: 2.05, h: 0.4, margin: 0, valign: "middle", align: "right", fontFace: MONO, fontSize: 9.5, color: MUTED });
    y += 0.5;
  }
  s.addText(
    "Line anchors are from the released v0.7-sprint7 tree. One-way dependency: " +
    "nlp_research never imports production; production never imports nlp_research.",
    { x: M, y: y + 0.1, w: W - 2 * M, h: 0.55, margin: 0, fontFace: F, fontSize: 12, italic: true, color: MUTED }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 3 — The data
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The data: five datasets, one discipline");
  const ds = [
    ["corpus-v1", "2,226 labeled utterances · 197 template families · splits 1,537 / 434 / 255", "sha256 content-addressed manifest; EOL-normalized byte-reproducible writes"],
    ["anfis-v1", "5,964 engine-priced scenarios · 76,960 opportunity rows · 1,623 positives (2.11%)", "grid generator, SATURATED — superseded by the sampler"],
    ["anfis-v3", "21,964 continuous scenarios · 377,753 rows · 51,873 positives (13.73%)", "continuous sampler v3, seed 472 — the benchmark dataset; row-scaling stopped"],
    ["acceptance events", "live ADR-017 store: shown → accepted/rejected/ignored/viewed/dismissed", "young by design; feeds the funnel and the calibration gate"],
    ["organic capture", "opt-in TAX_CORPUS_CAPTURE — real conversations, minimized", "the ADR-015 re-open trigger"],
  ];
  let y = 1.6;
  for (const [n, shape, note] of ds) {
    card(s, M, y, W - 2 * M, 0.86);
    s.addText(n, { x: M + 0.28, y: y + 0.08, w: 2.6, h: 0.7, margin: 0, valign: "middle", fontFace: F, fontSize: 14, bold: true, color: PRIMARY });
    s.addText(shape, { x: M + 3.0, y: y + 0.08, w: 5.6, h: 0.7, margin: 0, valign: "middle", fontFace: F, fontSize: 11.5, color: TEXT, lineSpacingMultiple: 1.08 });
    s.addText(note, { x: M + 8.75, y: y + 0.08, w: W - 2 * M - 9.0, h: 0.7, margin: 0, valign: "middle", fontFace: F, fontSize: 10.5, italic: true, color: MUTED, lineSpacingMultiple: 1.08 });
    y += 1.0;
  }
  s.addText(
    "Determinism policy: seeded generators (seed 472), LF-normalized writes, " +
    "sha256 manifests — a dataset can be rebuilt byte-for-byte if anyone doubts it.",
    { x: M, y: y + 0.08, w: W - 2 * M, h: 0.5, margin: 0, fontFace: F, fontSize: 12.5, italic: true, color: PRIMARY }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 4 — Deterministic extraction (production language layer)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Deterministic extraction — the production language layer");
  codeChip(s, M, 1.5, 7.2, "backend/nlp_engine.py:112,119,676 · backend/ai_models.py:25,142 · backend/tools/run_eval.py");
  bullets(s, M, 2.05, W - 2 * M, 1.75, [
    { t: "UniversalParser + SemanticAttention + waterfall guards — no learned component anywhere in the path" },
    { t: "Trained on nothing: it is rules. \u201CTraining time\u201D is zero by design; the cost is in authoring and testing the rules" },
    { t: "Corpus: corpus-v1 (2,226 records), evaluation on the 434-record template-disjoint split, 21 categories + a trained abstention class" },
  ], { size: 13, gap: 7 });
  factsTable(s, M, 4.0, W - 2 * M, [
    ["corpus-v1, 434 eval records", "0 learned parameters", "no training — deterministic", "macro F1 1.000 · abstention 17/17 (gate PASS)"],
  ]);
  s.addText(
    "Why rules and not a model? The certified gate demanded \u226595% F1; the rules " +
    "measure 100%, run offline, and cannot drift. A learned extractor would need " +
    "labeled data the project does not have (ADR-015 re-opens only if organic " +
    "capture ever justifies it).",
    { x: M, y: 5.3, w: W - 2 * M, h: 1.0, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 5 — Intent classifier (research layer)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Intent classifier — TF-IDF + logistic regression");
  codeChip(s, M, 1.5, 7.2, "nlp_research/phase_c_intent_classification.py:73,135,300");
  bullets(s, M, 2.05, W - 2 * M, 1.3, [
    { t: "21 production categories map to 8 research intents; TF-IDF unigrams+bigrams (min_df 2, sublinear), L2 logistic regression, stratified seeded split 1,780/446 (seed 472)" },
    { t: "Evaluation integrity: the TF-IDF vectorizer is fit on the TRAIN split only — the pre-audit 97.9% \u201ctest accuracy\u201d was the full-corpus score with test vocabulary leaking into training features, and it is retracted" },
  ], { size: 13, gap: 7 });
  factsTable(s, M, 3.4, W - 2 * M, [
    ["2,226 records \u2192 1,780 train / 446 held-out", "1,333 TF-IDF features \u00D7 8 classes = 10,672 weights (measured)", "measured 9.7 s wall (CPU, container, feature build included)", "held-out 96.19% · train 98.48% · BiLSTM same split 98.21%"],
  ]);
  s.addText("How the 10,672 decompose", {
    x: M, y: 4.7, w: 6, h: 0.3, margin: 0, fontFace: F, fontSize: 13.5, bold: true, color: PRIMARY,
  });
  s.addText(
    "One sparse weight vector per class: 1,333 features × 8 classes = 10,664 " +
    "coefficients + 8 intercepts. Every feature is a unigram or bigram of the " +
    "TRAIN vocabulary — inspectable, and the top weights per class read like " +
    "a keyword list a CA would recognize.",
    { x: M, y: 5.05, w: W - 2 * M, h: 0.9, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  s.addText(
    "Runs anywhere: the numbers above are from a clean CPU-container rerun; " +
    "the research deps are pinned in nlp_research/requirements-research.txt, " +
    "so the split, the vocabulary and the metrics regenerate identically.",
    { x: M, y: 6.1, w: W - 2 * M, h: 0.5, margin: 0, fontFace: F, fontSize: 12, italic: true, color: MUTED }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 6 — BiLSTM NER (the corrected story)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "BiLSTM NER — a fabricated metric, corrected, then widened");
  codeChip(s, M, 1.5, 7.2, "nlp_research/phase_d_ner.py:55,91,196 · phase_d_corpus.py:132,394,422");
  bullets(s, M, 2.05, W - 2 * M, 1.55, [
    { t: "Architecture: embedding (128-d, train-only vocab 161) → BiLSTM (256 hidden, bidirectional) → linear over 11 BIO tags" },
    { t: "Data: widened template grammar — 14 multi-entity sentence families with explicit slot\u2192pool sequences (500 unique samples, dedup-on-append; 64% carry 2+ entities)" },
    { t: "Two audit fixes: the reported 0.143 was a softmax confidence of a NaN-diverged model (fabricated per-class metrics), and the old 6-class schema double-labeled every section token as both TAX_SECTION and DEDUCTION_TYPE — merged to 5 classes with clean gold" },
  ], { size: 12.5, gap: 7 });
  factsTable(s, M, 3.75, W - 2 * M, [
    ["500 samples (widened)", "287,627 (embedding 20,608 + BiLSTM 264,192 + linear 2,827)", "measured 20 epochs (CPU container)", "real evaluator: 99.14% acc · 0.994 macro F1"],
    ["(original) 51 samples", "same architecture", "diverged: loss NaN at epoch 7", "reported \u201C0.143\u201D — never an accuracy"],
  ]);
  s.addText(
    "Every fix is pinned by a torch-free test suite (tests/test_phase_d_corpus.py): " +
    "BIO span alignment (the old window math produced ZERO I- tags), corpus " +
    "determinism, vocabulary stability, seeded-split balance. Training runs in a " +
    "CPU-torch container — Windows Application Control blocks the DLLs natively.",
    { x: M, y: 5.55, w: W - 2 * M, h: 1.1, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 7 — Embeddings from scratch
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Word embeddings — built from scratch in NumPy");
  codeChip(s, M, 1.5, 7.2, "nlp_research/embedding_analysis.py (SGNS :138, GloVe :222)");
  bullets(s, M, 2.05, W - 2 * M, 1.5, [
    { t: "Why from scratch: no gensim wheels for the Python build — so SGNS and GloVe were implemented in pure NumPy against the corpus vocabulary" },
    { t: "SGNS: Skip-gram with negative sampling, 50 dimensions, window 5, 5 negatives, Adam optimizer" },
    { t: "GloVe: global co-occurrence factorization, 100 dimensions, f(x) = min(1, (x/x_max)^α) weighting, Adagrad" },
  ], { size: 13, gap: 7 });
  factsTable(s, M, 3.7, W - 2 * M, [
    ["2,226-record corpus vocabulary", "SGNS 50-d · GloVe 100-d (NumPy, from scratch)", "CPU training, seeded", "PCA: 78% variance in the top 10 SGNS dimensions"],
  ]);
  s.addText(
    "Purpose: geometry analysis for the viva — PCA shows income and deduction " +
    "classes separating at macro scale; t-SNE reveals fine clusters (80c / 80d / " +
    "24b). Key documented finding: template coverage is essential for OOV " +
    "anchoring — rare Hinglish tokens only land in the right neighborhood when " +
    "the templates include them.",
    { x: M, y: 5.15, w: W - 2 * M, h: 1.3, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 8 — ANFIS v4 (production scorer)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "ANFIS v4 — the neuro-fuzzy efficiency scorer");
  codeChip(s, M, 1.5, 7.2, "backend/ai_models.py:637 · anfis_weights.json · anfis_trainer.py");
  bullets(s, M, 2.05, W - 2 * M, 1.3, [
    { t: "Takagi-Sugeno architecture: 20 normalized session features → Gaussian membership functions → 64 rules → defuzzified 0-100 efficiency grade shown on the results screen" },
    { t: "Weights are byte-identical to the shipped anfis_weights.json — the trained artifact is versioned, not re-fit silently" },
  ], { size: 13, gap: 7 });
  factsTable(s, M, 3.4, W - 2 * M, [
    ["200k-1M legacy slab scenarios (RUN-001 — pre-dates the ADR-004 fix)", "3,904 = 2,560 membership (20 inputs × 64 rules × center+σ) + 1,344 consequents (64 × 21)", "EE-BAT evolutionary search, 500 iterations, seeded", "architect-verified r² 0.4976 vs engine truth — retained as a UI grade, never a rupee"],
  ]);
  s.addText(
    "Honest framing: v4's original training target pre-dated the engine-truth " +
    "correction, so its r² against the true engine is modest. That is exactly why " +
    "v5 was retrained against the live engine — and why the served efficiency is " +
    "now the exact composite (next slide), with v4's grade demoted to a UI signal.",
    { x: M, y: 5.35, w: W - 2 * M, h: 1.1, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 9 — ANFIS v5 composite + exact rule heads
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "ANFIS v5 — LSE consequents, measured gates");
  codeChip(s, M, 1.5, 7.2, "backend/tools/train_anfis_v5.py · tools/retrain_anfis.py · tools/generate_anfis_dataset.py");
  bullets(s, M, 2.05, W - 2 * M, 1.3, [
    { t: "Design: ridge least-squares consequents (closed form) + data-driven quantile memberships + sigma-scale search — no evolutionary search, converging ~100\u00D7 faster than the bounded EE-BAT" },
    { t: "The served efficiency is the exact composite (weight-shift fix, EXP-005): MAE 0.136 on the v5 validation, 0.0023 on the 3,138-scenario continuous slice" },
  ], { size: 13, gap: 7 });
  factsTable(s, M, 3.5, W - 2 * M, [
    ["RUN-003: anfis-v1 v2 (46,816 rows / 146 positives)", "1,104 LSE coefficients (48 rules × 23 features)", "measured 47-67 s wall per full fit", "G1 0.053 · G2 −0.013 · G3 100% PASS; learned savings G4 FAIL"],
    ["RUN-003b: expansion (76,960 rows / 1,623 positives)", "same 1,104", "measured 65.5 s wall", "G1 0.136 PASS · G6 95.72% PASS → exact rule heads DEPLOYED"],
    ["RUN-004: anfis-v3 (377,753 rows / 51,873 positives)", "same 1,104", "105× the training rows", "composite 0.0023 PASS; learned heads FAIL worse"],
  ], 0.5);
  s.addText(
    "The LSE parameter count matters: 146 positives once sat below 1,104 parameters " +
    "(underdetermined); 51,873 positives sat far above it (divergent). Both directions " +
    "of failure were measured — the parameter/data ratio was never the real problem.",
    { x: M, y: 6.15, w: W - 2 * M, h: 0.75, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.12 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 10 — The falsification runs
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The falsification: three scales, one mechanism");
  const rows = [
    [{ text: "Run", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Optimizer / config", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Learned-head result", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Verdict", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }],
    ["RUN-002 (1,512 scenarios)", "EE-BAT, 300 iters", "MAE 11.09, loss still descending", "budget exhausted"],
    ["RUN-003 (46,816 rows)", "ridge-LSE, 48 rules", "G4 MAPE 92-108% · G5 P/R 0", "data-limited (146 positives)"],
    ["RUN-003b (76,960 rows)", "ridge-LSE, expanded strata", "G4 MAPE 795% · G5 P/R 0", "scarcity hypothesis falsified"],
    ["RUN-004 (377,753 rows)", "ridge-LSE, 105\u00D7 rows", "G4 MAPE 1,523,679% · G6 65.26%", "promotion DENIED — structural"],
  ];
  s.addTable(rows, {
    x: M, y: 1.6, w: W - 2 * M, colW: [3.1, 3.0, 3.9, 2.83],
    border: { pt: 0.75, color: LINE }, fontFace: F, fontSize: 11.5,
    color: TEXT, align: "center", valign: "middle", rowH: 0.42,
  });
  bullets(s, M, 4.35, W - 2 * M, 2.2, [
    { t: "The savings label is EXACTLY linear in two ratios the calculator produces (validation MAPE 1.6e-14 when handed those ratios) — the target is a formula" },
    { t: "The regime choice inside the ratios is a discontinuous min(); the additive rule base interpolates across the flip instead of pinning it (ranking 65.26% vs 100% exact)" },
    { t: "The opportunity label is the predicate \u201Cthe current regime ignores this head\u201D — zero exceptions in 377,753 rows; a rule was asked to behave like a distribution" },
    { t: "Policy (EXP-011/015/016): learned regression on closed-form targets is inadmissible at any scale; the dataset is retained as a deterministic benchmark" },
  ], { size: 12.5, gap: 7 });
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 11 — Exact rule heads + explainable CA layer
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "What actually ships: exact rules + a readable CA layer");
  codeChip(s, M, 1.5, 7.2, "backend/tax_intelligence.py:418,681-692 · fuzzy_ca.py:158,301,333 · ca_plans.py:49,86");
  bullets(s, M, 2.05, W - 2 * M, 1.3, [
    { t: "Rule heads: opportunity / savings / confidence evaluated from the engine two-pass — zero learned parameters, exact by construction" },
    { t: "Explainable CA layer: an authored readable rule base (10 rules, trapezoid memberships with explicit breakpoints) that fires plain-language reasoning into the report" },
    { t: "Whole plans: combinations of levers priced by ONE engine recomputation each — levers are partitioned into contributions (investable at will) and actuals (only when the underlying fact is booked)" },
  ], { size: 12.5, gap: 7 });
  factsTable(s, M, 3.5, W - 2 * M, [
    ["engine two-pass over the session", "0 learned parameters (rules evaluate closed forms)", "no training — recomputation", "P/R 1.0 · savings MAE Rs 0.00 · 10,995-row validation"],
    ["CA layer: authored rules", "0 learned parameters (authored memberships)", "no training — authored + validated", "rulebook fully decodable; practitioner-proxy validation report"],
  ]);
  s.addText(
    "Code tour, ranked: tax_engine.py:238 (the calculator) → tax_intelligence.py:418 " +
    "(the ranked review) → fuzzy_ca.py:158 (the rule base) → calibration.py:24 (the " +
    "instrument) → main.py:1177-1237 (the adoption endpoints).",
    { x: M, y: 6.0, w: W - 2 * M, h: 0.75, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.12 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 12 — Calibration instrument
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Calibration — the instrument and its gate");
  codeChip(s, M, 1.5, 6.0, "backend/calibration.py:24,62 · main.py:/analytics/overview");
  bullets(s, M, 2.05, W - 2 * M, 1.5, [
    { t: "Expected Calibration Error over 10 equal-width bins with the full reliability table (Guo et al. 2017 formulation)" },
    { t: "Known-answer canary: 200 constructed pairs must measure exactly 0.0; the flipped set must flag at 0.85 — banker's rounding is excluded by construction (20 items/bin)" },
    { t: "Data source: the live ADR-017 acceptance store — resolved events only" },
  ], { size: 13, gap: 7 });
  factsTable(s, M, 3.7, W - 2 * M, [
    ["resolved acceptance events (live store)", "0 learned parameters", "no training — measurement", "canary 0.0 exact; flipped set flags 0.85; live store: 1 resolved event \u2192 honestly \u201Cunmeasured\u201D"],
  ]);
  s.addText(
    "The gate: no learned confidence replaces the 0.85/0.30 anchor until a candidate " +
    "measures ECE \u2264 0.05 on at least 30 resolved events without hurting the " +
    "acceptance rate. The gate converts a data-availability problem into a blocking " +
    "condition instead of a temptation.",
    { x: M, y: 5.3, w: W - 2 * M, h: 1.0, margin: 0, fontFace: F, fontSize: 13, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 13 — Verification & reproducibility
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Verification & reproducibility — how to re-run everything");
  const tiles = [
    ["1,209", "backend tests"], ["44", "frontend tests"], ["7", "browser E2E flows"], ["3", "CI jobs per push"],
  ];
  let tx = M;
  for (const [n, l] of tiles) {
    card(s, tx, 1.6, 3.0, 1.1);
    s.addText(n, { x: tx, y: 1.68, w: 3.0, h: 0.55, margin: 0, align: "center", fontFace: F, fontSize: 30, bold: true, color: ACCENT });
    s.addText(l, { x: tx, y: 2.22, w: 3.0, h: 0.35, margin: 0, align: "center", fontFace: F, fontSize: 11.5, color: MUTED });
    tx += 3.11;
  }
  sectionLabel(s, M, 3.0, 11, "Re-run commands (all seeded, all offline)");
  codeChip(s, M, 3.4, 12.23, "cd backend && python -m pytest tests/ -q                     # 1,209 tests");
  codeChip(s, M, 3.85, 12.23, "cd frontend && npx vitest run && npx tsc --noEmit           # 31+ tests, types");
  codeChip(s, M, 4.3, 12.23, "cd backend && python tools/run_eval.py                      # extraction gate: macro F1 1.000");
  codeChip(s, M, 4.75, 12.23, "cd backend && python tools/train_anfis_v5.py                # LSE fit: ~65 s wall");
  codeChip(s, M, 5.2, 12.23, "docker run --rm -v <repo>:/repo ner-train python nlp_research/phase_d_ner.py   # NER");
  bullets(s, M, 5.85, W - 2 * M, 1.2, [
    { t: "Determinism: seed 472 everywhere, LF-normalized writes, sha256 manifests — datasets rebuild byte-for-byte" },
    { t: "The research stack trains inside a CPU-torch container (the host's Application Control blocks torch DLLs — documented)" },
  ], { size: 12, gap: 6 });
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 14 — Research summary table
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Every model, one table");
  const rows = [
    [{ text: "Component", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Type", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Params", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Train time", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Measured result", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Status", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }],
    ["Extraction", "rules", "0", "—", "F1 1.000", "PRODUCTION"],
    ["Intent", "TF-IDF + LogReg", "10,672", "9.7 s", "96.19% held-out (BiLSTM 98.21%)", "RESEARCH"],
    ["SGNS / GloVe", "NumPy, from scratch", "50-d / 100-d", "CPU, seeded", "PCA 78% top-10", "RESEARCH"],
    ["BiLSTM NER (5-class)", "BiLSTM 256", "287,627", "20 ep (CPU)", "99.14% / F1 0.994", "RESEARCH"],
    ["ANFIS v4", "TSK 20\u00D764", "3,904", "EE-BAT 500 iters", "r\u00B2 0.4976 (UI grade)", "PRODUCTION (UI)"],
    ["ANFIS v5 composite", "LSE composite", "exact", "47-67 s", "MAE 0.136 \u2192 0.0023", "PRODUCTION"],
    ["ANFIS v5 TSK heads", "LSE regression", "1,104", "65.5 s", "MAPE 1.5M% \u00B7 P/R 0", "DENIED (policy)"],
    ["Rule heads", "closed-form", "0", "—", "P/R 1.0 \u00B7 MAE Rs 0.00", "PRODUCTION"],
    ["CA layer", "authored fuzzy rules", "0", "—", "rulebook fully decodable", "PRODUCTION"],
    ["Calibration", "ECE instrument", "0", "—", "canary 0.0 exact", "PRODUCTION"],
  ];
  s.addTable(rows, {
    x: M, y: 1.6, w: W - 2 * M, colW: [2.5, 2.3, 1.3, 1.9, 2.83, 1.94],
    border: { pt: 0.75, color: LINE }, fontFace: F, fontSize: 10.5,
    color: TEXT, align: "center", valign: "middle", rowH: 0.4,
  });
  s.addText(
    "PRODUCTION = serves users under the ADR-001 invariant. RESEARCH = measured " +
    "honestly, never deployed. DENIED = falsified with the mechanism recorded. " +
    "Every row traces to a registry entry (EXPERIMENT_REGISTRY.md EXP-001…020, " +
    "TRAINING_REGISTRY.md RUN-001…005).",
    { x: M, y: 6.3, w: W - 2 * M, h: 0.8, margin: 0, fontFace: F, fontSize: 11.5, color: MUTED, lineSpacingMultiple: 1.12 }
  );
  pageNo(s);
}

p.writeFile({ fileName: "TaxAssist_Technical_Evidence_Deck.pptx" })
  .then(() => console.log("tech deck written"));
