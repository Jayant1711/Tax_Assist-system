# docs/paper/make_local_html.py — generate the CLICKABLE HTML edition of the
# NLP/ML technique reference. Every code location is a vscode:// deep link
# that opens the file at the exact line in VS Code (works from a browser
# page; Edge's PDF viewer silently drops custom-protocol links, which is
# why the PDF edition uses copy-paste paths instead).
import html
import io
import os

BASE = 'C:/Users/lenovo/Desktop/Tax_Assist-system-main/Tax_Assist-system-main'
VS = 'vscode://file/' + BASE + '/'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'ml_nlp_topics_reference_LOCAL.html')

# (topic, what-it-is, [(path, line, label)], facts, measured, real example)
TOPICS = [
 ("Rule-based slot filling (information extraction)",
  "The production language layer: guards, an Indian-numeral parser and a waterfall that books every amount into a validated session. No learned component anywhere in the path.",
  [("backend/ai_models.py", 25, "UniversalParser"),
   ("backend/nlp_engine.py", 112, "guard splitters"),
   ("backend/nlp_engine.py", 676, "process_message")],
  "corpus-v1: 2,226 records (1,537/434/255) \u00b7 params: 0 \u00b7 training: none",
  "macro F1 1.000 over 21 categories \u00b7 abstention 17/17 \u00b7 gate PASS",
  "Real use: \u201cI earn 18 LPA, invest 1.5 lakhs in PPF, and pay 12,000 rent monthly\u201d books salary Rs 18,00,000, 80C Rs 1,50,000 and rent Rs 12,000 monthly (annualized Rs 1,44,000) \u2014 three sub-techniques of the same chain."),

 ("Tokenization guard: commas are grouping, not grammar",
  "The splitter only cuts when neither neighbour of a comma is a digit \u2014 encoded as two zero-width regex assertions.",
  [("backend/nlp_engine.py", 119, "grouping-safe split"),
   ("backend/nlp_engine.py", 112, "clause splitter")],
  "params: 0 \u00b7 training: none",
  "covered by the extraction gate (F1 1.000) and adversarial unit tests",
  "Real use: \u201cclaimed 1,25,000 under 80c\u201d stays whole. A naive split destroys it into 1 / 25 / 000."),

 ("Semantic attention (custom): distance-decayed category binding",
  "Each keyword votes with a Gaussian-decayed weight by character distance; the amount binds to the nearest statutory context. Fallbacks are flagged provisional and never overwrite booked values.",
  [("backend/ai_models.py", 142, "SemanticAttention")],
  "params: 0 (sigma = 40 is a fixed design constant) \u00b7 training: none",
  "covered by the extraction gate + adversarial cross-category tests",
  "Real use: \u201cinvested 1.5 lakhs in PPF \u2026 pay 2L rent\u201d \u2014 80C sits d=6 from the Rs 1.5 lakh and wins it; rent sits d=34 and wins the Rs 2 lakh."),

 ("Intent classification: TF-IDF + logistic regression",
  "21 production categories map to 8 research intents; TF-IDF unigrams+bigrams (min_df 2, sublinear) feed an L2 logistic regression. The vectorizer is fit on the TRAIN split only (the audit wave closed a full-corpus fit that leaked test vocabulary); stratified seeded 1,780/446 split.",
  [("nlp_research/phase_c_intent_classification.py", 73, "build_feature_matrices"),
   ("nlp_research/phase_c_intent_classification.py", 135, "train_tfidf_baseline"),
   ("nlp_research/phase_c_intent_classification.py", 300, "run_intent_classification")],
  "data: 2,226 records (1,780 train / 446 held-out), 8 intents \u00b7 params: 1,333 features x 8 classes = 10,672 weights (measured) \u00b7 training: measured 9.7 s wall (CPU container, feature build included)",
  "held-out 96.19% (train 98.48%) \u00b7 BiLSTM on the same split: 98.21% \u00b7 the pre-audit \u201c97.9% test accuracy\u201d was the FULL-corpus score and is retracted (evaluation-integrity audit)",
  "Real use: \u201cI am a software engineer earning 24 lakhs\u201d classifies as the salary intent at very high margin, routing the conversation into the income branch."),

 ("Sequence labeling with BIO tags (corpus encoding)",
  "Entity spans convert to B-/I- tags aligned with the token regex by character offsets from re.finditer. The pre-fix window arithmetic drifted and produced zero I- tags.",
  [("nlp_research/phase_d_corpus.py", 368, "entities_to_bio"),
   ("nlp_research/phase_d_corpus.py", 116, "generate_ner_corpus"),
   ("nlp_research/phase_d_corpus.py", 396, "prepare_ner_dataset")],
  "data: expanded template grammar + 6 multi-entity families \u00b7 471 unique samples \u00b7 labels: 13 BIO tags",
  "pinned torch-free by tests/test_phase_d_corpus.py (10 tests)",
  "Real use: \u201ci paid 25k as rent on 1 april 2024 as of 30 june 2024\u201d encodes as O O B-MONEY O O O B-DATE I-DATE I-DATE O O B-DATE I-DATE I-DATE \u2014 three entities, two multi-token."),

 ("BiLSTM sequence labeling (NER model)",
  "Embedding (128-d, corpus vocab 118) -> BiLSTM (256 hidden, bidirectional) -> linear over 13 BIO tags. Gradient clipping at 1.0; lr 5e-4.",
  [("nlp_research/phase_d_ner.py", 55, "BiLSTM_NER"),
   ("nlp_research/phase_d_ner.py", 91, "train_ner_model"),
   ("nlp_research/phase_d_ner.py", 152, "gradient clipping"),
   ("nlp_research/phase_d_ner.py", 196, "evaluate_ner")],
  "data: 471 samples \u00b7 params: 282,637 (embedding 15,104 + BiLSTM 264,192 + linear 3,341) \u00b7 training: measured 7.9 s / 20 epochs (CPU container)",
  "real evaluator: 91.36% token accuracy \u00b7 0.756 macro F1 (the reported 0.143 was a fabricated metric \u2014 softmax confidence of a NaN-diverged model)",
  "Real use: research-track only \u2014 production extraction stays deterministic. The corrected pipeline is pinned by a torch-free test suite."),

 ("Word embeddings, built from scratch: SGNS",
  "Skip-gram with negative sampling implemented in pure NumPy (no gensim wheel for the build): 50 dimensions, window 5, 5 negatives, Adam.",
  [("nlp_research/embedding_analysis.py", 138, "SGNS")],
  "data: corpus vocabulary \u00b7 params: 50-d in+out matrices \u00b7 training: CPU, seeded",
  "PCA: 78% of variance in the top 10 dimensions",
  "Real use: the geometry analysis \u2014 income and deduction classes separate at macro scale; template coverage anchors rare Hinglish tokens into the right neighborhood."),

 ("Word embeddings, built from scratch: GloVe",
  "Global co-occurrence factorization with f(x) = min(1, (x/x_max)^alpha) weighting, weighted least squares, Adagrad: 100 dimensions.",
  [("nlp_research/embedding_analysis.py", 222, "train_glove")],
  "data: corpus co-occurrence matrix \u00b7 params: 100-d two-sided embeddings \u00b7 training: CPU, seeded",
  "t-SNE exposes fine clusters (80c / 80d / 24b)",
  "Real use: the viva geometry study \u2014 comparing factorization-based and prediction-based spaces on the same corpus."),

 ("Seq2seq with attention: Bahdanau and Luong",
  "Encoder-decoder LSTM (hidden 128, embeddings 64) with both attention forms implemented and compared on 150 Indian-tax input/target pairs, character-level.",
  [("nlp_research/phase_e_seq2seq.py", 157, "Bahdanau additive"),
   ("nlp_research/phase_e_seq2seq.py", 183, "Luong dot-product"),
   ("nlp_research/phase_e_seq2seq.py", 198, "Seq2SeqAttention")],
  "data: 150 pairs \u00b7 params: documented in ATTENTION_STUDY \u00b7 training: CPU, seeded",
  "mechanically documented study (ATTENTION_STUDY.md)",
  "Real use: the study quantifies when additive vs dot-product attention matters \u2014 on a domain too small for the difference to dominate."),

 ("Transformer studies: BERT, GPT-2, T5",
  "BERT-base (110M) joint intent + section head \u2014 full fine-tune blocked (no GPU); GPT-2 (1.5B) prompted generations; T5-small (220M) summarization runs.",
  [("nlp_research/phase_f_bert_classification.py", 1, "BERT"),
   ("nlp_research/phase_g_generative.py", 1, "GPT-2 / T5")],
  "params: 110M / 1.5B / 220M (pretrained) \u00b7 training: blocked or minimal",
  "findings logged: fluent output, statutory numbers unverifiable",
  "Real use: the conclusion the architecture responds to \u2014 generative models are excellent at language but cannot guarantee a single correct rupee."),

 ("Neuro-fuzzy inference (ANFIS / TSK): the production efficiency scorer",
  "Takagi-Sugeno architecture: 20 normalized session features -> Gaussian memberships -> 64 rules -> defuzzified 0-100 efficiency grade on the results screen. Weights byte-identical to the shipped artifact.",
  [("backend/ai_models.py", 637, "ANFIS"),
   ("backend/anfis_weights.json", 1, "shipped weights"),
   ("backend/anfis_trainer.py", 1, "trainer")],
  "data (RUN-001): legacy slab scenarios 200k-1M rows \u00b7 params: 3,904 = 2,560 memberships (20 x 64 x center+sigma) + 1,344 consequents (64 x 21) \u00b7 training: EE-BAT 500 iterations, seeded",
  "architect-verified r2 0.4976 vs engine truth \u2014 retained as the UI grade, never a rupee",
  "Real use: a 24-lakh salaried profile with minimal deductions shows Efficiency Score 64.7/100 \u2014 a UI signal of deduction utilization, fully decoupled from the tax computation."),

 ("Ridge least-squares consequents (the v5 redesign)",
  "Closed-form consequents + data-driven quantile memberships + sigma-scale search \u2014 converging ~100x faster than the bounded EE-BAT. The served efficiency is the exact composite.",
  [("backend/tools/train_anfis_v5.py", 1, "trainer"),
   ("backend/tools/generate_anfis_dataset.py", 187, "continuous stratum")],
  "data: RUN-003b 76,960 rows / 1,623 positives (also RUN-004 at 377,753 rows) \u00b7 params: 1,104 LSE coefficients (48 rules x 23 features) \u00b7 training: measured 65.5 s wall",
  "served composite MAE 0.136 -> 0.0023 on the 3,138-scenario continuous slice",
  "Real use: the composite efficiency the user sees is exact \u2014 and the same run's learned savings head measured MAPE 795%, which triggered the falsification."),

 ("Controlled falsification experiment design (three data scales)",
  "Identical architecture, monotonically more data: 46,816 -> 76,960 -> 377,753 rows. The learned head failed worse at every scale \u2014 the mechanism is a discontinuous regime-flip min() the additive rule base smooths across.",
  [("backend/tools/forensics/", 1, "forensics harness"),
   ("TRAINING_REGISTRY.md", 1, "RUN-002..004"),
   ("EXPERIMENT_REGISTRY.md", 1, "EXP-011/015/016")],
  "data: three scales (146 / 1,623 / 51,873 positives) \u00b7 params: 1,104 constant \u00b7 training: measured per run",
  "learned savings MAPE 795% -> 1,523,679% \u00b7 opportunity P/R 0 at every scale \u00b7 policy: permanently inadmissible",
  "Real use: the dataset (51,873 positives, 13.73% density) is retained as a deterministic benchmark \u2014 not a growth axis."),

 ("Exact rule heads over the two-pass (the deployed decision layer)",
  "Three questions answered from recomputation, never from a model: recommend?, how much, how confidently. Zero learned parameters.",
  [("backend/tax_intelligence.py", 418, "recommend (two-pass)"),
   ("backend/tax_intelligence.py", 681, "rule_opportunity / rule_savings / rule_confidence")],
  "data: engine two-pass over the session \u00b7 params: 0 \u00b7 training: none",
  "P/R 1.0 \u00b7 savings MAE Rs 0.00 (10,995-row validation)",
  "Real use: the 15-lakh profile's report renders Section 24B est. saves Rs 32,500, 80C Rs 22,100, 80G Rs 1,300 \u2014 all with reasoning, all engine-priced."),

 ("Leave-one-out counterfactual evaluation",
  "Re-price the full session with one head zeroed, in both regimes: impact(i) = T_r(x_-i) - T_r(x). An item is \u201capplied\u201d only when the regime's taxable income actually changes without it.",
  [("backend/tax_engine.py", 520, "deduction_impact")],
  "data: the user's own booked session \u00b7 params: 0 \u00b7 training: none \u2014 exact arithmetic",
  "differential tests pin sign + new-regime semantics; control profile prices 115BAC heads at Rs 0",
  "Real use: the impact table shows 80E entered Rs 5,00,000 -> tax reduced Rs 1,30,000 and 24(b) Rs 2,00,000 -> Rs 41,600, matching a hand-worked slab bridge."),

 ("Calibration: Expected Calibration Error + the known-answer canary",
  "ECE over 10 equal-width bins with the full reliability table, computed on the live acceptance store. The canary's 200 constructed pairs must measure exactly 0.0; the flipped set must flag at 0.85. The gate: no learned confidence until ECE <= 0.05 on 30 resolved events.",
  [("backend/calibration.py", 24, "expected_calibration_error"),
   ("backend/calibration.py", 62, "self_check"),
   ("backend/main.py", 1177, "/analytics/overview")],
  "data: the live ADR-017 acceptance store \u00b7 params: 0 \u00b7 training: none \u2014 measurement",
  "canary 0.0 exact \u00b7 flipped set flags 0.85 \u00b7 live store: 1 resolved event -> honestly unmeasured",
  "Real use: the Adoption Dashboard shows the gate progress (resolved events / 30) beside the Accepted-Rupee metric."),

 ("Dataset engineering: seeded generation + manifest pinning",
  "Seed 472 everywhere, LF-normalized writes, sha256 content-addressed manifests \u2014 datasets rebuild byte-for-byte.",
  [("backend/tools/generate_anfis_dataset.py", 187, "continuous stratum"),
   ("backend/tools/build_labeled_corpus.py", 1, "corpus-v1 builder"),
   ("data/manifest.json", 1, "sha256 manifest")],
  "data produced: anfis-v3 = 21,964 scenarios / 377,753 rows / 51,873 positives (13.73%) \u00b7 params: 0",
  "training: none \u2014 generation \u00b7 evaluation: byte-for-byte rebuild verified",
  "Real use: the falsification's third scale (377,753 rows) was generated by this pipeline and regenerated byte-identically for CI."),

 ("Evaluation harness and release gates",
  "The certified extraction gate (>= 95% F1, measured 1.000), the ANFIS gates G1-G6 (three PASS, three measured FAILs), the calibration canary \u2014 every claim has a gate.",
  [("backend/tools/run_eval.py", 46, "eval CLI"),
   ("TRAINING_REGISTRY.md", 1, "RUN-001..005"),
   ("EXPERIMENT_REGISTRY.md", 1, "EXP-001..020")],
  "data: the pinned corpora \u00b7 params: n/a \u00b7 training: n/a",
  "extraction F1 1.000 \u00b7 ANFIS gates: three PASS, three FAIL \u2014 all recorded",
  "Real use: the CI runs the full suite on every push; two releases shipped through CI-gated PRs with post-merge re-certification."),

 ("The adoption store: online-learning substrate",
  "Shown-events persist on the closing turn; the user's action resolves them; the funnel aggregates per session and per head; one-click Apply books the headroom (clamped to statutory caps) and the engine re-prices.",
  [("backend/db.py", 436, "action finality"),
   ("backend/db.py", 509, "cross-session overview"),
   ("backend/main.py", 1177, "/analytics/overview"),
   ("backend/main.py", 1237, "apply_plan endpoint")],
  "data: the live ADR-017 store \u00b7 params: 0 \u00b7 training: none",
  "live: 24 shown / 1 accepted / rate 4.2% / Accepted-Rupee Rs 32,500 \u00b7 gate 1/30",
  "Real use: clicking Apply on a recommendation booked the 80C headroom and re-priced the report \u2014 net taxable moved from Rs 7,50,000 to Rs 5,50,000."),
]


def link(path, line, label):
    href = VS + path + ':' + str(line)
    return ('<a class="cl" href="' + html.escape(href, quote=True) + '">'
            + html.escape(label) + ':' + str(line) + '</a>')


cards = []
for (topic, what, locs, facts, ev, ex) in TOPICS:
    links = ' \u00b7 '.join(link(*l) for l in locs)
    cards.append(f'''
<div class="card">
  <h3>{html.escape(topic)}</h3>
  <p class="what">{html.escape(what)}</p>
  <p class="locs"><b>code:</b> {links}</p>
  <p class="facts"><b>Data / params / training:</b> {html.escape(facts)}</p>
  <p class="ev"><b>Measured:</b> {html.escape(ev)}</p>
  <p class="ex">{html.escape(ex)}</p>
</div>''')

summary_rows = '\n'.join(
    f'<tr><td>{html.escape(t)}</td><td>{html.escape(p)}</td><td>{html.escape(pa)}</td>'
    f'<td>{html.escape(tr)}</td><td>{html.escape(ev)}</td><td>{html.escape(st)}</td></tr>'
    for t, p, pa, tr, ev, st in [
      ("Extraction", "rules", "0", "\u2014", "F1 1.000", "PRODUCTION"),
      ("Intent", "TF-IDF + LogReg", "10,672", "9.7 s", "96.19% held-out (BiLSTM 98.21%)", "RESEARCH"),
      ("SGNS / GloVe", "NumPy, from scratch", "50-d / 100-d", "CPU, seeded", "PCA 78% top-10", "RESEARCH"),
      ("BiLSTM NER", "BiLSTM 256", "282,637", "7.9 s / 20 ep", "91.36% / F1 0.756", "RESEARCH"),
      ("ANFIS v4", "TSK 20x64", "3,904", "EE-BAT 500 iters", "r2 0.4976 (UI grade)", "PRODUCTION (UI)"),
      ("ANFIS v5 composite", "LSE composite", "exact", "47-67 s", "MAE 0.136 -> 0.0023", "PRODUCTION"),
      ("ANFIS v5 TSK heads", "LSE regression", "1,104", "65.5 s", "MAPE 1.5M% / P-R 0", "DENIED (policy)"),
      ("Rule heads", "closed-form", "0", "\u2014", "P/R 1.0 \u00b7 MAE Rs 0.00", "PRODUCTION"),
      ("CA layer", "authored fuzzy rules", "0", "\u2014", "rulebook fully decodable", "PRODUCTION"),
      ("Calibration", "ECE instrument", "0", "\u2014", "canary 0.0 exact", "PRODUCTION"),
    ])

BG = "#F6F8FA"
TEXT = "#182230"
PRIMARY = "#1A4A73"
ACCENT = "#E8590C"
MUTED = "#5D6C7B"
LINE = "#D8E0E8"
TINT = "#E4EDF5"

page = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Tax Assist — NLP &amp; ML Techniques (clickable edition)</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background: {BG}; color: {TEXT};
         margin: 0; padding: 2rem 1.4rem; max-width: 1180px; margin-inline: auto; }}
  h1 {{ color: {TEXT}; font-size: 2rem; margin: 0.2rem 0 0.4rem; }}
  h2 {{ color: {TEXT}; margin-top: 1.6rem; }}
  .kicker {{ color: {ACCENT}; font-weight: 700; letter-spacing: 2px; font-size: 0.8rem; }}
  .sub {{ color: {MUTED}; font-size: 0.95rem; }}
  .how {{ background: {TINT}; border-radius: 8px; padding: 0.9rem 1.1rem;
          font-size: 0.9rem; margin: 1.2rem 0; }}
  .how code {{ background: white; padding: 1px 5px; border-radius: 4px; }}
  .card {{ background: white; border: 1px solid {LINE}; border-radius: 10px;
           padding: 1rem 1.2rem; margin: 0.9rem 0;
           box-shadow: 0 1px 3px rgba(20,40,60,.08); }}
  .card h3 {{ margin: 0 0 0.4rem; color: {PRIMARY}; font-size: 1.05rem; }}
  .what {{ margin: 0.2rem 0; font-size: 0.88rem; }}
  .locs {{ margin: 0.3rem 0; font-size: 0.85rem; color: {MUTED}; }}
  .cl {{ font-family: Consolas, monospace; font-size: 0.82rem; color: {PRIMARY};
         background: {TINT}; padding: 1px 6px; border-radius: 4px;
         text-decoration: none; }}
  .cl:hover {{ background: {ACCENT}; color: white; }}
  .facts {{ margin: 0.3rem 0; font-size: 0.85rem; }}
  .ev {{ margin: 0.3rem 0; font-size: 0.85rem; color: {PRIMARY}; }}
  .ex {{ margin: 0.3rem 0 0; font-size: 0.85rem; color: {MUTED}; font-style: italic; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; background: white; }}
  th {{ background: {PRIMARY}; color: white; text-align: left; padding: 7px 10px; }}
  td {{ border: 1px solid {LINE}; padding: 6px 10px; }}
  .foot {{ color: {MUTED}; font-size: 0.8rem; margin-top: 1.4rem; }}
</style></head><body>
<div class="kicker">TAX ASSIST \u00b7 CLICKABLE CODE LINKS</div>
<h1>NLP &amp; ML Techniques \u2014 clickable edition</h1>
<p class="sub">Companion to the printed reference. Every blue chip opens the exact file and
line in VS Code. First click: tick <b>\u201cAlways allow\u201d</b> when the browser asks.</p>
<div class="how"><b>How to open:</b> click any chip \u2192 the browser asks to open Visual
Studio Code \u2192 the file opens at that line. The copy-paste route always works too:
select the path, then <code>Ctrl+P</code> in VS Code, paste, Enter.</div>
{''.join(cards)}
<h2>Every model, one table</h2>
<table><tr><th>Component</th><th>Type</th><th>Params</th><th>Train time</th>
<th>Measured result</th><th>Status</th></tr>
{summary_rows}</table>
<p class="foot">PRODUCTION = serves users under the engine-only invariant.
RESEARCH = measured honestly, never deployed. DENIED = falsified with the
mechanism recorded. Links open this machine's v0.7-sprint7 tree.</p>
</body></html>'''

with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    f.write(page)
print('HTML written:', OUT, '(', len(page), 'chars,', len(TOPICS), 'topics )')
