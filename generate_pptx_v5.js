// Tax Assist — project presentation (v5)
// 11 slides (cut from 19) · live product screenshots embedded ·
// mirrors the IEEE report's narrative · 13.33 x 7.5
const pptxgen = require("pptxgenjs");

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "Jayant (12406581)";
p.title = "Tax Assist — Rules-Exact Conversational Tax Advisory";

// ---- Design system -------------------------------------------------------
const W = 13.33, H = 7.5, M = 0.55;
const BG = "FFFFFF";
const DARK = "0E2A44";
const DARK2 = "1C3E63";
const PRIMARY = "1A4A73";
const TINT = "E4EDF5";
const TINT2 = "EFF4F8";
const ACCENT = "E8590C";
const TEXT = "182230";
const MUTED = "5D6C7B";
const LINE = "D8E0E8";
const WHITE = "FFFFFF";
const GREEN = "2E7D4F";
const GREEN_T = "E7F2EC";
const RED = "B23B3B";
const RED_T = "F7E9E9";
const AMBER = "9A6A0B";
const AMBER_T = "F7F1E1";
const LIGHTTXT = "D7E3F0";
const F = "Segoe UI";
const MONO = "Consolas";
const KICKER = "TAX ASSIST · RULES-EXACT CONVERSATIONAL TAX ADVISORY";

const bu = () => ({ code: "2022", indent: 12 });
const sh = () => ({ type: "outer", color: "8B98A5", blur: 7, offset: 2, angle: 90, opacity: 0.18 });
const A = "deck_assets/";

function header(s, title, sub) {
  s.addText(KICKER, {
    x: M, y: 0.42, w: 9.5, h: 0.3, margin: 0,
    fontFace: F, fontSize: 12, bold: true, color: ACCENT, charSpacing: 2,
  });
  s.addText(title, {
    x: M, y: 0.72, w: W - 2 * M, h: 0.62, margin: 0,
    fontFace: F, fontSize: 31, bold: true, color: TEXT,
  });
  if (sub) {
    s.addText(sub, {
      x: M, y: 1.34, w: W - 2 * M, h: 0.34, margin: 0,
      fontFace: F, fontSize: 13.5, color: MUTED,
    });
  }
  s.addText("Jayant (12406581) · RK4P24MZA06", {
    x: W - 3.6 - M, y: 0.44, w: 3.6, h: 0.28, margin: 0, align: "right",
    fontFace: F, fontSize: 10.5, color: MUTED,
  });
}

function framed(s, path, x, y, w, h, caption) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: x - 0.07, y: y - 0.07, w: w + 0.14, h: h + 0.14, rectRadius: 0.06,
    fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: sh(),
  });
  s.addImage({ path, x, y, w, h, sizing: { type: "cover", w, h } });
  if (caption) {
    s.addText(caption, {
      x, y: y + h + 0.1, w, h: 0.26, margin: 0,
      fontFace: F, fontSize: 12, italic: true, color: MUTED,
    });
  }
}

function stat(s, x, y, w, num, label, color) {
  s.addText(num, {
    x, y, w, h: 0.95, margin: 0, fontFace: F, fontSize: 44, bold: true,
    color: color || PRIMARY,
  });
  s.addText(label, {
    x, y: y + 0.95, w, h: 0.55, margin: 0, fontFace: F, fontSize: 12.5,
    color: MUTED, lineSpacingMultiple: 1.05,
  });
}

function row(s, x, y, w, head, body, headColor) {
  s.addText(head, {
    x, y, w: 3.35, h: 0.62, margin: 0, fontFace: F, fontSize: 13.5,
    bold: true, color: headColor || PRIMARY, valign: "top", lineSpacingMultiple: 1.02,
  });
  s.addText(body, {
    x: x + 3.5, y, w: w - 3.5, h: 0.62, margin: 0, fontFace: F,
    fontSize: 12.5, color: TEXT, valign: "top", lineSpacingMultiple: 1.08,
  });
}

function chip(s, x, y, w, t, dark) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h: 0.44, rectRadius: 0.09,
    fill: { color: dark ? DARK2 : TINT }, line: { color: dark ? "2C5580" : "C6D6E4", width: 0.75 },
  });
  s.addText(t, {
    x, y, w, h: 0.44, margin: 0, align: "center", valign: "middle",
    fontFace: F, fontSize: 12, color: dark ? "C9D8E8" : PRIMARY,
  });
}

function pageNo(s, n) {
  s.addText(String(n).padStart(2, "0") + " / 11", {
    x: W - 1.4 - M, y: H - 0.44, w: 1.4, h: 0.28, margin: 0, align: "right",
    fontFace: F, fontSize: 10.5, color: MUTED,
  });
}

// ===========================================================================
// SLIDE 1 — Title (dark)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addText("CSE472 · DEEP LEARNING FOR NATURAL LANGUAGE PROCESSING", {
    x: M + 0.15, y: 1.35, w: 11.5, h: 0.35, margin: 0,
    fontFace: F, fontSize: 14, bold: true, color: ACCENT, charSpacing: 2,
  });
  s.addText("Tax Assist", {
    x: M + 0.15, y: 1.75, w: 11.8, h: 1.15, margin: 0,
    fontFace: F, fontSize: 66, bold: true, color: WHITE,
  });
  s.addText(
    "An AI-powered consultant for Indian income tax — a chat that understands " +
    "plain English & Hinglish, computes both tax regimes exactly, and shows its " +
    "working on every single rupee.",
    {
      x: M + 0.15, y: 3.05, w: 10.6, h: 1.0, margin: 0,
      fontFace: F, fontSize: 17, color: LIGHTTXT, lineSpacingMultiple: 1.15,
    }
  );
  const chips = [
    ["FY 2025-26 rules", 2.3],
    ["Only the engine computes rupees", 3.7],
    ["1,235 tests green", 2.3],
    ["November 2026", 2.1],
  ];
  let cx = M + 0.15;
  for (const [t, w] of chips) {
    chip(s, cx, 4.35, w, t, true);
    cx += w + 0.25;
  }
  // real numbers as the visual element: the three measured scores
  s.addChart(p.charts.BAR, [{
    name: "Measured",
    labels: ["Extraction F1", "Intent (held-out)", "NER (widened)"],
    values: [100.0, 96.19, 99.14],
  }], {
    x: M + 0.15, y: 5.15, w: 7.3, h: 1.9, barDir: "bar",
    chartColors: ["2C5580", "3E6E9E", "E8590C"], varyColors: true,
    chartArea: { fill: { color: DARK } }, plotArea: { fill: { color: DARK } },
    catAxisLabelColor: "9FB2C4", valAxisLabelColor: "5D7A96",
    valAxisMaxVal: 100, valAxisMinVal: 0, valAxisHidden: true,
    valGridLine: { style: "none" }, catGridLine: { style: "none" },
    catAxisLineShow: false, serAxisLineShow: false,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: "C9D8E8",
    dataLabelFontSize: 11, catAxisLabelFontSize: 11,
    dataLabelFormatCode: "0.0",
    showLegend: false, showTitle: false,
  });
  s.addText([
    { text: "Presented by Jayant (12406581)", options: { breakLine: true } },
    { text: "Roll No. RK4P24MZA06", options: { breakLine: true } },
    { text: "github.com/Jayant1711/Tax_Assist-system", options: {} },
  ], {
    x: 8.3, y: 5.35, w: 4.6, h: 1.3, margin: 0,
    fontFace: F, fontSize: 12.5, color: "9FB2C4", paraSpaceAfter: 4, align: "right",
  });
  s.addNotes(
    "Open with the one-liner: a chat that understands plain English and Hinglish, computes both regimes exactly, and shows its working on every rupee. " +
    "The three bars are the deck's spine: measured, not claimed. If asked why NER is orange: it is the research-track model, the newest measurement.");
}

// ===========================================================================
// SLIDE 2 — The problem & the product (live screenshot)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Tax filing is a trust problem", "Every consultant promises savings; few show the arithmetic. Tax Assist is built to show it.");
  const items = [
    ["The jargon wall", "Sections, regimes, rebates — the law is written for practitioners, not for the person paying."],
    ["The regime guesswork", "Old vs New changes slab-by-slab every year; guessing wrong costs real money."],
    ["The black box", "\u201cTrust me, invest here\u201d — advice without the arithmetic behind it is how mistakes happen."],
  ];
  let y = 1.95;
  for (const [h, b] of items) {
    s.addText(h, {
      x: M, y, w: 5.6, h: 0.3, margin: 0, fontFace: F, fontSize: 14.5,
      bold: true, color: PRIMARY,
    });
    s.addText(b, {
      x: M, y: y + 0.32, w: 5.6, h: 0.62, margin: 0, fontFace: F,
      fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.1,
    });
    y += 1.0;
  }
  s.addText(
    "Tax Assist answers all three with one design rule: the engine is the only " +
    "thing allowed to compute a rupee — the chat understands you, the engine " +
    "computes, and the report shows every figure's working.",
    {
      x: M, y: 5.15, w: 5.6, h: 1.3, margin: 0, fontFace: F, fontSize: 13,
      color: TEXT, lineSpacingMultiple: 1.18, fill: { color: TINT2 },
    }
  );
  framed(s, A + "crop_app_full.png", 6.6, 1.95, 6.1, 3.19,
    "The actual product, live: guided dialogue (left) and the real-time audit (right)");
  s.addText(
    "Screen capture from the running app · November 2026",
    { x: 6.6, y: 5.6, w: 6.1, h: 0.3, margin: 0, fontFace: F, fontSize: 11.5, color: MUTED }
  );
  s.addNotes(
    "The three pains are the audience's pains — most people in the room have faced one. " +
    "Point at the screenshot: everything visible is computed live while the user types.");
  pageNo(s, 2);
}

// ===========================================================================
// SLIDE 3 — Architecture: one invariant (native diagram)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Architecture: one rule guards the whole system",
    "ADR-001 — the TaxEngine is the only component allowed to compute a rupee. Everything else understands, ranks, or shows.");
  const boxes = [
    ["Utterance", "\u201cI earn 24L and put 1.5L in PPF\u201d", TINT2, TEXT],
    ["NLP layer", "understands: profile, amounts,\ncorrections, negation", TINT, PRIMARY],
    ["TaxEngine", "computes: both regimes,\nsurcharge, marginal relief", "1A4A73", WHITE],
    ["Intelligence", "ranks: opportunities, plans,\nconfidence — engine-priced", TINT, PRIMARY],
    ["Report & cards", "shows: statement, evidence,\nfired rules, impact", TINT2, TEXT],
  ];
  const bw = 2.18, gap = 0.32, x0 = M + 0.05, yb = 2.15, bh = 1.5;
  for (let i = 0; i < boxes.length; i++) {
    const [h, b, fill, tc] = boxes[i];
    const bx = x0 + i * (bw + gap);
    const isEngine = fill === "1A4A73";
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x: bx, y: yb, w: bw, h: bh, rectRadius: 0.07,
      fill: { color: fill }, line: { color: isEngine ? "1A4A73" : "C6D6E4", width: 1 },
      shadow: isEngine ? sh() : undefined,
    });
    s.addText(h, {
      x: bx + 0.12, y: yb + 0.12, w: bw - 0.24, h: 0.34, margin: 0,
      fontFace: F, fontSize: 14.5, bold: true, color: tc,
    });
    s.addText(b, {
      x: bx + 0.12, y: yb + 0.5, w: bw - 0.24, h: 0.92, margin: 0,
      fontFace: F, fontSize: 10.5, color: isEngine ? "C9D8E8" : TEXT,
      lineSpacingMultiple: 1.1,
    });
    if (i < boxes.length - 1) {
      s.addShape(p.shapes.LINE, {
        x: bx + bw, y: yb + bh / 2, w: gap, h: 0,
        line: { color: MUTED, width: 1.75, endArrowType: "triangle" },
      });
    }
  }
  s.addText(
    "THE INVARIANT, ENFORCED",
    { x: M, y: 4.15, w: 6, h: 0.3, margin: 0, fontFace: F, fontSize: 12.5, bold: true, color: ACCENT, charSpacing: 1.5 }
  );
  const guards = [
    ["Corrections REPLACE, never add", "\u201coops, salary is actually 7L\u201d re-books the named head and undoes the old value — tested as a 3-turn chain."],
    ["Every figure is engine-priced", "savings, impacts, plan deltas: each one is a TaxEngine recomputation, never arithmetic in the NLP or UI layer."],
    ["Gold labels come from the engine", "the research layer trains against the engine's own two-pass output, so ML and law can never disagree."],
  ];
  y = 4.5;
  for (const [h, b] of guards) {
    row(s, M, y, W - 2 * M, h, b, PRIMARY);
    y += 0.78;
  }
  s.addText(
    "Audited by six specialist review waves (backend, security, tax law, QA, frontend, ML evaluation) — architect verdict: APPROVE.",
    { x: M, y: 6.9, w: W - 2 * M, h: 0.3, margin: 0, fontFace: F, fontSize: 11.5, italic: true, color: MUTED }
  );
  s.addNotes(
    "Walk the pipeline left to right, then land on the dark box: it is the only calculator. " +
    "The three guardrails are the ones the audit waves proved matter most.");
  pageNo(s, 3);
}

// ===========================================================================
// SLIDE 4 — The conversation (live screenshot)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The conversation: it books what you meant",
    "Plain English and Hinglish in; structured, disambiguated state out — with every mapping visible.");
  // chat-column crop from the live capture
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M - 0.07, y: 1.85, w: 4.75 + 0.14, h: 4.55 + 0.14, rectRadius: 0.06,
    fill: { color: WHITE }, line: { color: LINE, width: 1 }, shadow: sh(),
  });
  s.addImage({ path: A + "live_cards.png", x: M, y: 1.85, w: 4.75, h: 4.55, sizing: { type: "cover", w: 4.75, h: 4.55 } });
  s.addText("Live session: the dialogue drives the real-time audit panel on the right",
    { x: M, y: 6.5, w: 4.75, h: 0.3, margin: 0, fontFace: F, fontSize: 11.5, italic: true, color: MUTED });
  const rows4 = [
    ["Understands both languages", "English and Hinglish (\u201c50 hazaar kiraya deta hoon\u201d) — one tokenizer, word-boundary keywords, no translation step."],
    ["Maps, then shows the mapping", "every amount books with a visible badge: \u201cRENT PAID: \u20b9300,000 (ANNUALIZED)\u201d — the user can catch a mistake instantly."],
    ["Corrections replace", "re-stating a figure re-books its head; a correction naming another head never steals the amount."],
    ["Negation is a first-class citizen", "\u201cno\u201d closes one discovery slot per turn; \u201cI don\u2019t have 80C but my salary is\u2026\u201d books the salary, not the zero."],
    ["The waterfall asks, never interrogates", "80C \u2192 80D \u2192 NPS \u2192 rent/HRA \u2192 metro \u2192 80G — each \u201cno\u201d advances one slot and the next question."],
  ];
  y = 1.95;
  for (const [h, b] of rows4) {
    row(s, 5.75, y, W - 5.75 - M, h, b);
    y += 0.92;
  }
  s.addNotes(
    "This is the layer most demos skip. The badges are the point: the user SEES what was understood. " +
    "If asked about Hinglish: the keyword tables are bilingual by design, tested in the extraction gate.");
  pageNo(s, 4);
}

// ===========================================================================
// SLIDE 5 — Measured understanding (chart-centric)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "\u201cDoes it understand?\u201d — measured, not claimed",
    "One labeled corpus, one evaluator, three gates. The extraction gate BINDS in CI: red is a merge blocker.");
  s.addChart(p.charts.BAR, [{
    name: "Score",
    labels: ["Extraction\n(macro F1, 434 records)", "Intent\n(held-out 446 samples)", "NER\n(held-out 100 samples)"],
    values: [100.0, 96.19, 99.14],
  }], {
    x: M, y: 1.95, w: 7.0, h: 4.35, barDir: "bar",
    chartColors: ["1A4A73", "1A4A73", "E8590C"], varyColors: true,
    chartArea: { fill: { color: BG } },
    catAxisLabelColor: TEXT, valAxisLabelColor: MUTED,
    valAxisMaxVal: 100, valAxisMinVal: 0,
    valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: TEXT,
    dataLabelFontSize: 13, catAxisLabelFontSize: 11.5,
    showLegend: false, showTitle: false,
  });
  s.addText("Source: nlp_eval eval-split + the regenerated artifacts (seed 472); the intent vectorizer is fit on the train split only.",
    { x: M, y: 6.45, w: 7.0, h: 0.5, margin: 0, fontFace: F, fontSize: 11.5, italic: true, color: MUTED, lineSpacingMultiple: 1.1 });
  // right rail: the gate + honest exclusions
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: 8.0, y: 1.95, w: 4.75, h: 1.9, rectRadius: 0.07,
    fill: { color: GREEN_T }, line: { color: "BFDCCB", width: 1 },
  });
  s.addText("The gate that cannot be silently skipped", {
    x: 8.2, y: 2.1, w: 4.4, h: 0.35, margin: 0, fontFace: F, fontSize: 14, bold: true, color: GREEN,
  });
  s.addText(
    "The \u226595% income-head gate used to be advisory — it was red while excluded " +
    "from the default run. It now binds: pytest runs it every push, and a regression " +
    "in understanding is a merge blocker.",
    { x: 8.2, y: 2.5, w: 4.4, h: 1.25, margin: 0, fontFace: F, fontSize: 12, color: TEXT, lineSpacingMultiple: 1.12 }
  );
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: 8.0, y: 4.1, w: 4.75, h: 2.2, rectRadius: 0.07,
    fill: { color: TINT2 }, line: { color: LINE, width: 1 },
  });
  s.addText("Honest exclusions — the point, not a gap", {
    x: 8.2, y: 4.25, w: 4.4, h: 0.35, margin: 0, fontFace: F, fontSize: 14, bold: true, color: PRIMARY,
  });
  s.addText([
    { text: "ANFIS regression heads: denied by measurement (P/R = 0) — exact rules serve instead", options: { bullet: bu(), breakLine: true } },
    { text: "Confidence calibration: unmeasured until 30 real decisions accumulate", options: { bullet: bu(), breakLine: true } },
    { text: "BERT fine-tuning: GPU-blocked; logged, not claimed", options: { bullet: bu() } },
  ], {
    x: 8.2, y: 4.65, w: 4.4, h: 1.55, margin: 0, fontFace: F, fontSize: 12,
    color: TEXT, paraSpaceAfter: 7, lineSpacingMultiple: 1.1,
  });
  s.addNotes(
    "Three numbers, three different measurement protocols — say that explicitly. " +
    "The green card is the process claim: understanding regressions cannot merge silently.");
  pageNo(s, 5);
}

// ===========================================================================
// SLIDE 6 — The pricing core (live screenshot)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The pricing core: both regimes, exactly, every time",
    "The engine replays the Income-tax Act slab-by-slab — and the report shows both regimes side by side.");
  framed(s, A + "crop_regimes.png", M, 1.95, 5.35, 4.4,
    "Live report: Old \u20b94,68,000 vs New \u20b92,92,500 — the engine names the winner and the saving");
  const rows6 = [
    ["Both regimes, statutory depth", "slabs, the \u20b975k standard deduction, 87A rebate with its band cap applied PRE-cess (the department\u2019s own method), surcharge with marginal relief at all four thresholds."],
    ["Occupancy-aware 24(b)", "let-out interest deducts against net rental in full (loss set-off capped \u20b92L); self-occupied capped \u20b92L; the new regime allows only the let-out half."],
    ["Parity is byte-checked", "300 frozen scenarios replay through the engine on every push — the fixture regenerates only via its tool, with citations."],
    ["Impact you can audit", "per-deduction impact = leave-one-out recomputation: what each booked item actually removed, exactly."],
  ];
  y = 2.0;
  for (const [h, b] of rows6) {
    row(s, 6.35, y, W - 6.35 - M, h, b);
    y += 1.12;
  }
  s.addText(
    "The audit wave\u2019s tax-law review re-pinned 19 parity cells with citations — every changed cell traced to a documented ruling.",
    { x: 6.35, y: 6.5, w: W - 6.35 - M, h: 0.55, margin: 0, fontFace: F, fontSize: 11.5, italic: true, color: MUTED, lineSpacingMultiple: 1.1 }
  );
  s.addNotes(
    "The screenshot IS the engine's output — both bars, effective rates, the winner. " +
    "If a tax question comes: 87A cap is pre-cess per the department's TI 12,10,000 example; 24(b) follows occupancy.");
  pageNo(s, 6);
}

// ===========================================================================
// SLIDE 7 — The explainable CA layer
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The explainable CA layer: rules you can read",
    "An authored rule base reasons in sentences; the engine prices every suggestion; the card shows both.");
  // the fired-rule band, live
  framed(s, A + "crop_rule.png", M, 1.9, 11.0, 1.51,
    "Live: fired rule R10 (29% confidence) explaining WHY it is silent about 80G — advice includes the courage not to upsell");
  const steps = [
    ["1 · A readable rule fires", "10 authored rules (trapezoid memberships, floors as hard gates) reason over the session and explain themselves in one sentence."],
    ["2 · The rule names a lever", "\u201ctop up 24(b)\u201d, \u201cNPS has headroom\u201d — a lever, never a rupee."],
    ["3 · The engine prices it", "ONE recomputation per lever: the exact saving, regime shift included."],
    ["4 · The card shows both", "the sentence (why) + the figure (how much) + the engine evidence trail."],
  ];
  const sw = 2.85, x0 = M;
  for (let i = 0; i < steps.length; i++) {
    const [h, b] = steps[i];
    const bx = x0 + i * (sw + 0.22);
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x: bx, y: 4.1, w: sw, h: 1.62, rectRadius: 0.07,
      fill: { color: i === 3 ? TINT : TINT2 }, line: { color: LINE, width: 1 },
    });
    s.addText(h, {
      x: bx + 0.14, y: 4.22, w: sw - 0.28, h: 0.35, margin: 0,
      fontFace: F, fontSize: 13, bold: true, color: PRIMARY,
    });
    s.addText(b, {
      x: bx + 0.14, y: 4.6, w: sw - 0.28, h: 1.05, margin: 0,
      fontFace: F, fontSize: 11, color: TEXT, lineSpacingMultiple: 1.12,
    });
    if (i < steps.length - 1) {
      s.addShape(p.shapes.LINE, {
        x: bx + sw, y: 4.9, w: 0.22, h: 0,
        line: { color: MUTED, width: 1.75, endArrowType: "triangle" },
      });
    }
  }
  s.addText([
    { text: "Live-verified: ", options: { bold: true, color: PRIMARY } },
    { text: "the ranked-plan card for a let-out profile priced a Sec 24(b) top-up at ", options: { color: TEXT } },
    { text: "\u20b931,200", options: { bold: true, color: ACCENT } },
    { text: " — applied in one click, the report re-priced, and the adoption funnel recorded it.", options: { color: TEXT } },
  ], {
    x: M, y: 6.1, w: W - 2 * M, h: 0.7, margin: 0, fontFace: F, fontSize: 14,
    lineSpacingMultiple: 1.15, fill: { color: GREEN_T },
  });
  s.addNotes(
    "The R10 band is the demo moment: the system explains why it is NOT recommending something. " +
    "The four-step chain is the answer to 'how do you keep the ML honest' — the ML never touches rupees.");
  pageNo(s, 7);
}

// ===========================================================================
// SLIDE 8 — The adoption loop (live screenshot)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The adoption loop: suggested vs. done",
    "Every shown recommendation, acceptance and rejection is recorded — the feedback the calibration gate will train on.");
  framed(s, A + "crop_dashboard_tiles.png", M, 1.95, 6.2, 3.03,
    "Live: the cross-session funnel — 6 shown, 2 accepted, \u20b931,200 accepted-rupee");
  const rows8 = [
    ["Finality, SQL-enforced", "accepted/rejected are final; the auto-fired \u201cviewed\u201d can never overwrite them (ADR-017)."],
    ["Accepted-Rupee", "the engine-priced sum of what users actually accepted — adoption measured in rupees, not clicks. Per-head, the 24(b) lever converted at \u20b931,200."],
    ["Calibration gate G7", "no learned confidence until ECE \u2264 0.05 on \u2265 30 resolved events — currently 2/30, and the gate says so."],
    ["One-click apply", "\u201cApply\u201d books the lever (clamped to the statutory cap), records it, and re-prices the whole report."],
  ];
  y = 1.95;
  for (const [h, b] of rows8) {
    s.addText(h, {
      x: 7.15, y, w: W - 7.15 - M, h: 0.3, margin: 0, fontFace: F,
      fontSize: 14.5, bold: true, color: PRIMARY,
    });
    s.addText(b, {
      x: 7.15, y: y + 0.32, w: W - 7.15 - M, h: 0.85, margin: 0, fontFace: F,
      fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.1,
    });
    y += 1.25;
  }
  s.addNotes(
    "The dashboard is real data from a live session. The 2/30 gate reading is deliberate honesty: " +
    "the system displays how far it is from being ALLOWED to claim calibrated confidence.");
  pageNo(s, 8);
}

// ===========================================================================
// SLIDE 9 — The honesty arc (signature slide)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The honesty arc: when the numbers were wrong",
    "Two fabricated metrics found by our own audit — both retracted, both re-measured, both now pinned by tests.");
  const stations = [
    ["RED — the fabrication", "BiLSTM NER reported \u201c0.143 accuracy\u201d. The audit showed it was never an accuracy: labels collapsed to O, the loss diverged to NaN, and the figure was a softmax confidence with per-class metrics synthesized from entity counts.", RED, RED_T],
    ["AMBER — the correction", "Evaluator rebuilt (real token-level scoring), deterministic corpus vocabulary, gradient clipping, expanded grammar: 91.36% / 0.756 macro-F1 — measured, capped by a thin test split.", AMBER, AMBER_T],
    ["GREEN — the widening", "Grammar widened to 14 multi-entity families, dedup-on-append (500 unique), train-only vocabulary, and a schema fix: the old 6-class scheme double-labeled every section token. Result: 99.14% / 0.994, TAX_SECTION support 2 \u2192 42.", GREEN, GREEN_T],
  ];
  const sw = (W - 2 * M - 0.5) / 3;
  for (let i = 0; i < stations.length; i++) {
    const [h, b, c, tint] = stations[i];
    const bx = M + i * (sw + 0.25);
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x: bx, y: 1.95, w: sw, h: 2.75, rectRadius: 0.07,
      fill: { color: tint }, line: { color: c, width: 1.25 },
    });
    s.addText(h, {
      x: bx + 0.16, y: 2.1, w: sw - 0.32, h: 0.35, margin: 0,
      fontFace: F, fontSize: 13.5, bold: true, color: c,
    });
    s.addText(b, {
      x: bx + 0.16, y: 2.5, w: sw - 0.32, h: 2.1, margin: 0,
      fontFace: F, fontSize: 11.5, color: TEXT, lineSpacingMultiple: 1.14,
    });
    if (i < stations.length - 1) {
      s.addShape(p.shapes.LINE, {
        x: bx + sw + 0.02, y: 3.3, w: 0.21, h: 0,
        line: { color: MUTED, width: 1.75, endArrowType: "triangle" },
      });
    }
  }
  // the intent arc, second row
  s.addText("The same discipline caught a second one:", {
    x: M, y: 5.0, w: 5.5, h: 0.3, margin: 0, fontFace: F, fontSize: 13.5, bold: true, color: PRIMARY,
  });
  s.addText([
    { text: "the intent model\u2019s \u201c97.9% test accuracy\u201d was the FULL-corpus score with the vectorizer fit on all records — test vocabulary leaked into training. ", options: { color: TEXT } },
    { text: "Retracted. ", options: { bold: true, color: RED } },
    { text: "Re-measured with the vectorizer fit on the train split only: 96.19% held-out (BiLSTM 98.21% on the same cells).", options: { color: TEXT } },
  ], {
    x: M, y: 5.35, w: W - 2 * M, h: 0.85, margin: 0, fontFace: F, fontSize: 12.5,
    lineSpacingMultiple: 1.15,
  });
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 6.35, w: W - 2 * M, h: 0.72, rectRadius: 0.07,
    fill: { color: TINT }, line: { color: "C6D6E4", width: 1 },
  });
  s.addText(
    "\u201cAn evaluator is code, and code can be quietly wrong in the direction of whatever number everyone already believed.\u201d — IEEE report, §VIII",
    { x: M + 0.2, y: 6.35, w: W - 2 * M - 0.4, h: 0.72, margin: 0, fontFace: F, fontSize: 13.5, italic: true, color: PRIMARY, valign: "middle" }
  );
  s.addNotes(
    "This is the slide the professor remembers. Lead with the 0.143 story, land on the quote. " +
    "The point is not the final numbers — it is that the pipeline CATCHES and CORRECTS its own fabrications, in writing.");
  pageNo(s, 9);
}

// ===========================================================================
// SLIDE 10 — Engineering rigor (stats row)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The discipline underneath",
    "Numbers first: the suite, the gates, and what runs on every single push.");
  const stats = [
    ["1,235", "backend tests, 0 failed — extraction gate BINDS in CI"],
    ["44", "frontend tests (vitest, containerized; tsc clean)"],
    ["300", "parity scenarios byte-checked on every push"],
    ["5 \u2192 0", "P0 defects found by the audit waves \u2192 all fixed, regression-pinned"],
  ];
  const sw = (W - 2 * M - 3 * 0.3) / 4;
  for (let i = 0; i < stats.length; i++) {
    const [n, l] = stats[i];
    stat(s, M + i * (sw + 0.3), 1.95, sw, n, l, i === 3 ? ACCENT : PRIMARY);
  }
  const rows10 = [
    ["Security posture", "rate limiting on GETs too, chunked bodies rejected 411 with the full header set, non-dict bodies 422, registration KDF ordering, and a .dockerignore that keeps the credentials database out of image layers."],
    ["Reproducibility", "research dependencies pinned (torch 2.15.0+cpu / sklearn 1.9.1); the NER CLI matches its pinned artifact; the anfis-v3 dataset counts (21,964 / 377,753 / 51,873) verified by a committed integrity pin."],
    ["End-to-end, live", "the full product loop — register \u2192 discover \u2192 report \u2192 apply \u2192 reprice \u2192 analytics — verified against the production containers, then re-verified after every fix."],
    ["Two honest limitations", "mixed-property 24(b) needs per-property inputs; real-CA sign-off is pending — a practicing chartered accountant must validate the rule base before any production claim."],
  ];
  y = 3.85;
  for (const [h, b] of rows10) {
    row(s, M, y, W - 2 * M, h, b);
    y += 0.82;
  }
  s.addNotes(
    "The 5→0 stat is the audit story in one figure: five P0s (two of them money-math, one a metric fabrication) found, fixed, and pinned. " +
    "The limitations row is pre-emptive honesty — name them before anyone asks.");
  pageNo(s, 10);
}

// ===========================================================================
// SLIDE 11 — Conclusion (dark)
// ===========================================================================
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addText("WHAT THIS PROJECT PROVES", {
    x: M + 0.15, y: 0.75, w: 11.5, h: 0.35, margin: 0,
    fontFace: F, fontSize: 13.5, bold: true, color: ACCENT, charSpacing: 2,
  });
  s.addText("An AI tax advisor can be exact, explainable — and honest about itself.", {
    x: M + 0.15, y: 1.15, w: 11.9, h: 1.35, margin: 0,
    fontFace: F, fontSize: 34, bold: true, color: WHITE, lineSpacingMultiple: 1.05,
  });
  const proofs = [
    ["Exact", "one engine computes every rupee; 300-scenario parity byte-checked; the tax-law corrections are cited and hand-verified."],
    ["Explainable", "readable rules reason, the engine prices, the card shows both — and it can explain why it is NOT advising."],
    ["Honest", "two fabricated metrics retracted in writing; the gate that catches regressions now binds in CI; the exclusions are stated, not hidden."],
  ];
  let y = 2.85;
  for (const [h, b] of proofs) {
    s.addText(h, {
      x: M + 0.15, y, w: 1.7, h: 0.75, margin: 0, fontFace: F, fontSize: 16,
      bold: true, color: ACCENT, valign: "top",
    });
    s.addText(b, {
      x: M + 2.0, y, w: 9.9, h: 0.75, margin: 0, fontFace: F, fontSize: 13.5,
      color: LIGHTTXT, valign: "top", lineSpacingMultiple: 1.12,
    });
    y += 0.88;
  }
  s.addText("NEXT", {
    x: M + 0.15, y: 5.6, w: 2, h: 0.3, margin: 0,
    fontFace: F, fontSize: 12.5, bold: true, color: "7FA3C8", charSpacing: 2,
  });
  s.addText(
    "Rule validation with a practicing CA · cohort benchmarks (privacy-first) · " +
    "per-property 24(b) · learned confidence once 30 real decisions accumulate.",
    {
      x: M + 0.15, y: 5.9, w: 11.5, h: 0.7, margin: 0,
      fontFace: F, fontSize: 13, color: LIGHTTXT, lineSpacingMultiple: 1.15,
    }
  );
  s.addText([
    { text: "Thank you. ", options: { bold: true, color: WHITE } },
    { text: "Jayant (12406581) · Roll No. RK4P24MZA06 · github.com/Jayant1711/Tax_Assist-system", options: { color: "9FB2C4" } },
  ], {
    x: M + 0.15, y: 6.8, w: 11.9, h: 0.4, margin: 0, fontFace: F, fontSize: 13,
  });
  s.addNotes(
    "Close on the three-word thesis: exact, explainable, honest. " +
    "Then the next steps — each one is scoped and named, not hand-waved.");
}

p.writeFile({ fileName: "TaxAssist_NLP_Final_Presentation_v5.pptx" })
  .then(() => console.log("v5 deck written: 11 slides"));
