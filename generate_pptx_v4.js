// Tax Assist — project presentation (v4)
// One project at present status · audience-first (no code assumed) ·
// mirrors the IEEE report's narrative · 19 slides · 13.33x7.5
const pptxgen = require("pptxgenjs");

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "Jayant (12406581)";
p.title = "Tax Assist — Rules-Exact Conversational Tax Advisory";

// ---- Design system -------------------------------------------------------
const W = 13.33, H = 7.5, M = 0.55;
const BG = "F6F8FA";
const DARK = "0E2A44";
const PRIMARY = "1A4A73";
const TINT = "E4EDF5";
const TINT2 = "EFF4F8";
const ACCENT = "E8590C";
const TEXT = "182230";
const MUTED = "5D6C7B";
const LINE = "D8E0E8";
const WHITE = "FFFFFF";
const GREEN = "2E7D4F";
const LIGHTTXT = "D7E3F0";
const F = "Segoe UI";
const MONO = "Consolas";
const KICKER = "TAX ASSIST · RULES-EXACT CONVERSATIONAL TAX ADVISORY";

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
let PAGE = 1;
function pageNo(s, opts = {}) {
  PAGE += 1;
  s.addText(String(PAGE).padStart(2, "0"), {
    x: W - 1.0, y: H - 0.52, w: 0.5, h: 0.3, margin: 0, align: "right",
    fontFace: F, fontSize: 11, color: opts.color || MUTED,
  });
}
function bullets(s, x, y, w, h, items, opts = {}) {
  const runs = items.map((it) => ({
    text: it.t,
    options: { bullet: it.plain ? false : bu(), breakLine: true, bold: !!it.b, color: it.c || (it.b ? PRIMARY : TEXT), fontFace: it.mono ? MONO : F },
  }));
  s.addText(runs, {
    x, y, w, h, margin: 0, valign: "top",
    fontFace: F, fontSize: opts.size || 14, color: TEXT,
    paraSpaceAfter: opts.gap == null ? 9 : opts.gap,
  });
}
function chip(s, x, y, w, text, o = {}) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h: o.h || 0.42, rectRadius: 0.09,
    fill: { color: o.fill || TINT }, line: { color: o.fill || TINT, width: 0 },
  });
  s.addText(text, {
    x: x + 0.02, y, w: w - 0.04, h: o.h || 0.42, margin: 0, align: "center", valign: "middle",
    fontFace: o.mono ? MONO : F, fontSize: o.size || 12.5, bold: !!o.b, color: o.color || PRIMARY,
  });
}
function card(s, x, y, w, h) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.07,
    fill: { color: WHITE }, line: { color: LINE, width: 0.75 },
    shadow: sh(),
  });
}
function stat(s, x, y, w, num, label, numColor = ACCENT, numSize = 40) {
  s.addText(num, {
    x, y, w, h: 0.62, margin: 0, align: "center",
    fontFace: F, fontSize: numSize, bold: true, color: numColor,
  });
  s.addText(label, {
    x, y: y + 0.66, w, h: 0.55, margin: 0, align: "center",
    fontFace: F, fontSize: 12, color: MUTED,
  });
}
function sectionLabel(s, x, y, w, text, color = NAVY_L) {
  s.addText(text, {
    x, y, w, h: 0.3, margin: 0,
    fontFace: F, fontSize: 14.5, bold: true, color,
  });
}
const NAVY_L = "1A4A73";

// ---------------------------------------------------------------------------
// SLIDE 1 — Title (dark)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addText("CSE472 · DEEP LEARNING FOR NATURAL LANGUAGE PROCESSING", {
    x: M + 0.15, y: 1.55, w: 11.5, h: 0.35, margin: 0,
    fontFace: F, fontSize: 14, bold: true, color: ACCENT, charSpacing: 2,
  });
  s.addText("Tax Assist", {
    x: M + 0.15, y: 1.95, w: 11.8, h: 1.15, margin: 0,
    fontFace: F, fontSize: 66, bold: true, color: WHITE,
  });
  s.addText(
    "An AI-powered consultant for Indian income tax — a chat that understands " +
    "plain English & Hinglish, computes both tax regimes exactly, and shows its " +
    "working on every single rupee.",
    {
      x: M + 0.15, y: 3.25, w: 10.6, h: 1.0, margin: 0,
      fontFace: F, fontSize: 17, color: LIGHTTXT, lineSpacingMultiple: 1.15,
    }
  );
  const chips = [
    ["FY 2025-26 rules", 2.3],
    ["Only the engine computes rupees", 3.7],
    ["1,204 tests green", 2.3],
    ["November 2026", 2.1],
  ];
  let cx = M + 0.15;
  for (const [t, w] of chips) {
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x: cx, y: 4.55, w, h: 0.46, rectRadius: 0.1,
      fill: { color: "1C3E63" }, line: { color: "2C5580", width: 0.75 },
    });
    s.addText(t, {
      x: cx, y: 4.55, w, h: 0.46, margin: 0, align: "center", valign: "middle",
      fontFace: F, fontSize: 12.5, color: "C9D8E8",
    });
    cx += w + 0.25;
  }
  s.addText([
    { text: "Presented by Jayant (12406581)", options: { breakLine: true } },
    { text: "Roll No. RK4P24MZA06", options: { breakLine: true } },
    { text: "github.com/Jayant1711/Tax_Assist-system", options: {} },
  ], {
    x: M + 0.15, y: 5.9, w: 6.0, h: 1.1, margin: 0,
    fontFace: F, fontSize: 12.5, color: "9FB2C4", paraSpaceAfter: 4,
  });
}

// ---------------------------------------------------------------------------
// SLIDE 2 — The problem
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The problem: advice you cannot check");
  s.addText(
    "Ask a chatbot about Section 80C and you get a confident, well-formatted " +
    "paragraph — sometimes even with the right numbers. The difficulty is telling " +
    "when it didn't.",
    { x: M, y: 1.55, w: 7.4, h: 1.15, margin: 0, fontFace: F, fontSize: 15.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  card(s, M, 2.85, 7.4, 1.7);
  s.addText([
    { text: "The moment that shaped the project", options: { bold: true, color: PRIMARY, breakLine: true, fontSize: 13.5 } },
    { text: "A test profile earning Rs 46 lakh produced a report where every deduction saved exactly nothing. I spent a day convinced the tax engine was broken. It wasn't — the new regime genuinely disallows those deductions, and my interface simply failed to say so.", options: { fontSize: 13, breakLine: true } },
    { text: "The fix was never \u201Ctrust the model less.\u201D It was \u201Cshow the working, from the calculator, every time.\u201D", options: { italic: true, color: PRIMARY, fontSize: 13 } },
  ], {
    x: M + 0.3, y: 3.0, w: 6.8, h: 1.45, margin: 0, valign: "top",
    fontFace: F, paraSpaceAfter: 6,
  });
  s.addText(
    "Indian income tax is an unforgiving place for invented numbers: liability " +
    "comes out of two parallel regimes interacting with twenty-plus deduction " +
    "sections, surcharge with marginal relief, and a rebate clause — and the person " +
    "reading the answer generally has no way to verify any of it.",
    { x: M, y: 4.8, w: 7.4, h: 1.5, margin: 0, fontFace: F, fontSize: 14, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  // right rail: the three pressures
  const rx = 8.35, rw = 4.43;
  sectionLabel(s, rx, 1.55, rw, "Why this is hard");
  const pressures = [
    ["2 regimes", "Old vs New (Sec 115BAC) — the cheaper one wins, and the winner flips with income"],
    ["20+ sections", "80C, 80D, 80E, 24(b), NPS… each with caps, conditions and regime rules"],
    ["0 ways to check", "A plausible wrong number is indistinguishable from the right one"],
  ];
  let py = 1.95;
  for (const [n, d] of pressures) {
    card(s, rx, py, rw, 1.28);
    s.addText(n, { x: rx + 0.25, y: py + 0.14, w: rw - 0.5, h: 0.4, margin: 0, fontFace: F, fontSize: 17, bold: true, color: ACCENT });
    s.addText(d, { x: rx + 0.25, y: py + 0.55, w: rw - 0.5, h: 0.62, margin: 0, fontFace: F, fontSize: 11.5, color: TEXT, lineSpacingMultiple: 1.08 });
    py += 1.48;
  }
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 3 — What Tax Assist does (capabilities)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "What Tax Assist does");
  s.addText(
    "One conversation, end to end — no forms, no section numbers required.",
    { x: M, y: 1.5, w: 11, h: 0.4, margin: 0, fontFace: F, fontSize: 15, color: MUTED }
  );
  const caps = [
    ["Understands you", "Describe income and investments the way you would to a human CA — plain English or Hinglish. Ambiguous input gets a follow-up question, not a guess."],
    ["Computes exactly", "Both tax regimes calculated side by side from versioned statutory rules — slabs, surcharge, rebate, cess — with every figure recomputable."],
    ["Explains every rupee", "A leave-one-out recomputation prices what each of your deductions actually saved you, in both regimes. No estimates."],
    ["Suggests with evidence", "Ranked opportunities show confidence, savings, the reasoning, and the evidence trail — with one-click Apply."],
    ["Learns what works", "Every recommendation shown is recorded; what you accept or reject feeds an adoption funnel and a calibration gate."],
  ];
  let cy = 2.0;
  for (const [h, d] of caps) {
    card(s, M, cy, W - 2 * M, 0.92);
    s.addText(h, { x: M + 0.3, y: cy + 0.12, w: 3.1, h: 0.68, margin: 0, valign: "middle", fontFace: F, fontSize: 15.5, bold: true, color: PRIMARY });
    s.addText(d, { x: M + 3.5, y: cy + 0.1, w: W - 2 * M - 3.9, h: 0.74, margin: 0, valign: "middle", fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.1 });
    cy += 1.02;
  }
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 4 — The invariant (dark emphasis)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addText("THE ARCHITECTURAL INVARIANT", {
    x: M + 0.15, y: 1.7, w: 11, h: 0.35, margin: 0,
    fontFace: F, fontSize: 13, bold: true, color: ACCENT, charSpacing: 2,
  });
  s.addText("\u201CNo component of the system can invent a rupee.\u201D", {
    x: M + 0.15, y: 2.15, w: 12.0, h: 1.5, margin: 0,
    fontFace: F, fontSize: 40, bold: true, color: WHITE,
  });
  s.addText(
    "One rules engine is the only calculator. The language layer decides what " +
    "you probably meant. The intelligence layer decides what to show — and prices " +
    "it by asking the engine. Every claim ships with its evidence, and an " +
    "append-only audit trail remembers everything.",
    { x: M + 0.15, y: 3.85, w: 11.8, h: 1.3, margin: 0,
      fontFace: F, fontSize: 16, color: LIGHTTXT, lineSpacingMultiple: 1.2 }
  );
  const supports = [
    ["Enforced", "in one place — the engine is the sole calculator"],
    ["Verified", "by construction — advice is priced by re-running the engine"],
    ["Audited", "continuously — append-only logs and an adoption store"],
  ];
  let sx = M + 0.15;
  for (const [a, b] of supports) {
    s.addText([
      { text: a + "  ", options: { bold: true, color: ACCENT } },
      { text: b, options: { color: LIGHTTXT } },
    ], {
      x: sx, y: 5.45, w: 3.9, h: 1.0, margin: 0, valign: "top",
      fontFace: F, fontSize: 13.5, lineSpacingMultiple: 1.15,
    });
    sx += 4.0;
  }
}

// ---------------------------------------------------------------------------
// SLIDE 5 — The tax domain, briefly
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The tax domain, briefly");
  s.addText(
    "Three facts a reader needs — the third one breaks machine-learning models, " +
    "which is a plot point later in this deck.",
    { x: M, y: 1.5, w: 11.5, h: 0.5, margin: 0, fontFace: F, fontSize: 14.5, color: MUTED }
  );
  const facts = [
    ["1 · Two regimes", "The OLD regime allows deductions under numbered sections (80C investments up to Rs 1.5 lakh, 80D health insurance, 80E education-loan interest, 24(b) home-loan interest) but taxes income at higher slab rates. The NEW regime (Sec 115BAC) has lower slab rates and a bigger standard deduction — but discards almost all of those deductions."],
    ["2 · Caps create headroom", "Each section has a statutory cap, so every deduction has a remaining \u201Cheadroom\u201D a recommendation can fill. 80C caps at Rs 1.5 lakh; NPS adds a separate Rs 50,000 slot on top of it."],
    ["3 · The winner flips", "Near certain income levels, topping up one deduction FLIPS which regime is cheaper — the saving from a top-up is discontinuous in the input. Hold onto this fact."],
  ];
  let fy = 2.15;
  for (const [h, d] of facts) {
    card(s, M, fy, W - 2 * M, 1.42);
    s.addText(h, { x: M + 0.3, y: fy + 0.14, w: 3.2, h: 1.1, margin: 0, fontFace: F, fontSize: 16, bold: true, color: PRIMARY, valign: "top" });
    s.addText(d, { x: M + 3.7, y: fy + 0.12, w: W - 2 * M - 4.1, h: 1.2, margin: 0, valign: "top", fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.12 });
    fy += 1.58;
  }
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 6 — Architecture
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Architecture: three tiers, one rule");
  // tier boxes
  const tiers = [
    ["CLIENT", "Next.js · React · TypeScript", "Chat workspace · final advisory report · adoption dashboard", 0.55],
    ["API", "FastAPI · Pydantic", "17 endpoints · auth (scrypt, HttpOnly cookies) · rate limits · origin allow-list", 4.7],
    ["DATA", "SQLite (WAL) · append-only audit", "Users · server-side sessions · recommendation events · JSONL audit stream", 8.85],
  ];
  for (const [t, tech, d, x] of tiers) {
    card(s, x, 1.65, 3.95, 1.55);
    s.addText(t, { x: x + 0.25, y: 1.78, w: 3.45, h: 0.3, margin: 0, fontFace: F, fontSize: 12.5, bold: true, color: ACCENT, charSpacing: 1.5 });
    s.addText(tech, { x: x + 0.25, y: 2.1, w: 3.45, h: 0.3, margin: 0, fontFace: F, fontSize: 12.5, bold: true, color: TEXT });
    s.addText(d, { x: x + 0.25, y: 2.42, w: 3.45, h: 0.72, margin: 0, fontFace: F, fontSize: 11, color: MUTED, lineSpacingMultiple: 1.1 });
  }
  // the four fixed decisions
  s.addText("Four decisions fixed early, never revisited", {
    x: M, y: 3.5, w: 11, h: 0.35, margin: 0, fontFace: F, fontSize: 15, bold: true, color: PRIMARY,
  });
  const decisions = [
    ["The engine is the only calculator", "anything that needs a number asks it"],
    ["Offline and deterministic", "same session, same numbers, on any machine"],
    ["Extraction stays rule-based", "the evaluation numbers support it (F1 1.000)"],
    ["Every recommendation is an event", "shown, then resolved by the user's action"],
  ];
  let dy = 3.95;
  for (const [a, b] of decisions) {
    s.addText([
      { text: a + " — ", options: { bold: true, color: PRIMARY } },
      { text: b, options: { color: TEXT } },
    ], {
      x: M, y: dy, w: W - 2 * M, h: 0.52, margin: 0, valign: "top",
      fontFace: F, fontSize: 13.5, lineSpacingMultiple: 1.1,
    });
    dy += 0.62;
  }
  s.addText(
    "Everything the user sees runs from the middle tier; the research models live " +
    "in a separate sandbox with a one-way dependency and never touch production.",
    { x: M, y: 6.5, w: W - 2 * M, h: 0.6, margin: 0, fontFace: F, fontSize: 12.5, italic: true, color: MUTED }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 7 — One query's journey
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "One query's journey");
  const steps = [
    ["You type", "\u201CI am a software engineer earning 15 LPA. I pay 5 lakhs education-loan interest.\u201D — plain language, no forms."],
    ["The gateway validates", "Authentication, per-route rate limits, and an origin allow-list run before any application logic."],
    ["Guards run first", "Percentages, dates and flat statutory amounts are masked or booked before parsing ever starts."],
    ["Indian numbers parse", "\u201C15 LPA\u201D and \u201C5 lakhs\u201D become exact amounts; a comma inside 1,25,000 is grouping, not grammar."],
    ["Attention assigns", "Each amount binds to its nearest statutory context — the loan interest lands on Section 80E."],
    ["The engine prices", "Both regimes computed from versioned FY rules; the report shows the working, not just the answer."],
  ];
  let sy = 1.6;
  for (let i = 0; i < steps.length; i++) {
    const [h, d] = steps[i];
    s.addShape(p.shapes.OVAL, { x: M, y: sy + 0.06, w: 0.52, h: 0.52, fill: { color: PRIMARY }, line: { color: PRIMARY, width: 0 } });
    s.addText(String(i + 1), { x: M, y: sy + 0.06, w: 0.52, h: 0.52, margin: 0, align: "center", valign: "middle", fontFace: F, fontSize: 16, bold: true, color: WHITE });
    if (i < steps.length - 1) {
      s.addShape(p.shapes.LINE, { x: M + 0.26, y: sy + 0.62, w: 0, h: 0.38, line: { color: LINE, width: 1.5 } });
    }
    s.addText(h, { x: M + 0.75, y: sy + 0.02, w: 11.5, h: 0.32, margin: 0, fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY });
    s.addText(d, { x: M + 0.75, y: sy + 0.34, w: 11.5, h: 0.38, margin: 0, fontFace: F, fontSize: 12, color: TEXT });
    sy += 0.86;
  }
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 8 — Where amounts belong (semantic attention)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Where amounts belong: attention by distance");
  // formula band
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 1.6, w: W - 2 * M, h: 0.85, rectRadius: 0.08,
    fill: { color: DARK },
  });
  s.addText([
    { text: "score(keyword) = 100 · e^(−d² / 2σ²)      σ = 40 characters", options: { color: "9FD8B4" } },
  ], {
    x: M + 0.4, y: 1.6, w: W - 2 * M - 0.8, h: 0.85, margin: 0, valign: "middle",
    fontFace: MONO, fontSize: 16,
  });
  // the worked example
  card(s, M, 2.75, 7.4, 2.9);
  s.addText("A worked example", { x: M + 0.3, y: 2.95, w: 6.8, h: 0.3, margin: 0, fontFace: F, fontSize: 13.5, bold: true, color: PRIMARY });
  s.addText("\u201Cinvested 1.5 lakhs in PPF \u2026 pay 2L rent\u201D", {
    x: M + 0.3, y: 3.3, w: 6.8, h: 0.35, margin: 0, fontFace: MONO, fontSize: 13, color: TEXT,
  });
  bullets(s, M + 0.3, 3.75, 6.8, 1.7, [
    { t: "Section 80C sits 6 characters from \u201C1.5 lakhs\u201D — it wins that amount" },
    { t: "The rent keyword sits 34 characters from \u201C2L\u201D — it wins that one" },
    { t: "Each amount goes to its own category; nothing is double-booked" },
  ], { size: 12.5, gap: 6 });
  // right rail: fallback honesty
  card(s, 8.35, 2.75, 4.43, 2.9);
  s.addText("When nothing matches", { x: 8.6, y: 2.95, w: 3.9, h: 0.3, margin: 0, fontFace: F, fontSize: 13.5, bold: true, color: PRIMARY });
  s.addText(
    "If no keyword scores above threshold, the amount falls back to a profile " +
    "default — flagged as provisional, and never able to overwrite a value the " +
    "user actually booked.",
    { x: 8.6, y: 3.3, w: 3.9, h: 1.3, margin: 0, fontFace: F, fontSize: 12, color: TEXT, lineSpacingMultiple: 1.12 }
  );
  s.addText(
    "Ask-backs beat guesses: ambiguity triggers a follow-up question.",
    { x: 8.6, y: 4.75, w: 3.9, h: 0.6, margin: 0, fontFace: F, fontSize: 12, italic: true, color: MUTED }
  );
  s.addText(
    "One regex encodes a subtle rule: a comma inside 1,25,000 is grouping, not " +
    "grammar — the splitter only cuts when neither neighbour is a digit.",
    { x: M, y: 6.0, w: W - 2 * M, h: 0.6, margin: 0, fontFace: F, fontSize: 13, italic: true, color: MUTED }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 9 — Does it understand? (evaluation)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Does it understand? Measured, not claimed");
  s.addText(
    "Template-disjoint evaluation: test sentences never share a template with " +
    "training data, so the numbers measure generalization, not memorization.",
    { x: M, y: 1.5, w: 11.5, h: 0.55, margin: 0, fontFace: F, fontSize: 14, color: MUTED }
  );
  // native bar chart
  s.addChart(p.charts.BAR, [{
    name: "Score",
    labels: ["Extraction (macro F1)", "Intent accuracy", "NER token accuracy (fixed)", "NER before the fix"],
    values: [100.0, 96.41, 91.36, 14.3],
  }], {
    x: M, y: 2.15, w: 7.6, h: 3.9, barDir: "bar",
    chartColors: ["1A4A73", "1A4A73", "2E7D4F", "B23B3B"],
    varyColors: true,
    chartArea: { fill: { color: BG } },
    catAxisLabelColor: TEXT, valAxisLabelColor: MUTED,
    valAxisMaxVal: 100, valAxisMinVal: 0,
    valGridLine: { color: LINE, size: 0.5 }, catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: TEXT,
    dataLabelFormatCode: "0.0\"%\"",
    showLegend: false, showTitle: false,
    catAxisLabelFontSize: 11, valAxisLabelFontSize: 10,
  });
  // right rail
  s.addText("The NER story — told honestly", {
    x: 8.5, y: 2.15, w: 4.3, h: 0.35, margin: 0, fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  s.addText(
    "The original NER evaluation was audited and found broken: the reported " +
    "\u201C0.143 accuracy\u201D was a confidence value from a diverged model, and " +
    "per-class metrics were derived from entity counts rather than predictions.",
    { x: 8.5, y: 2.55, w: 4.3, h: 1.4, margin: 0, fontFace: F, fontSize: 12, color: TEXT, lineSpacingMultiple: 1.12 }
  );
  s.addText(
    "After correcting the label encoding, vocabulary and evaluator — and " +
    "expanding the templates — the same architecture measures 91.36% token " +
    "accuracy / 0.756 macro F1. Still research-track: production extraction " +
    "stays rule-based, where it measures a perfect 1.000.",
    { x: 8.5, y: 4.0, w: 4.3, h: 1.9, margin: 0, fontFace: F, fontSize: 12, color: TEXT, lineSpacingMultiple: 1.12 }
  );
  s.addText(
    "Every number on this slide is reproducible from a fixed seed on an ordinary CPU.",
    { x: M, y: 6.35, w: W - 2 * M, h: 0.45, margin: 0, fontFace: F, fontSize: 12.5, italic: true, color: MUTED }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 10 — The pricing core
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The pricing core: two passes, no estimates");
  // two-pass
  sectionLabel(s, M, 1.55, 11, "Pricing a recommendation — pass one, pass two");
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 1.95, w: W - 2 * M, h: 0.8, rectRadius: 0.08, fill: { color: DARK },
  });
  s.addText([
    { text: "savings(i) = tax(cheaper regime, as booked) − tax(cheaper regime, head i topped up)", options: { color: "9FD8B4" } },
  ], {
    x: M + 0.4, y: 1.95, w: W - 2 * M - 0.8, h: 0.8, margin: 0, valign: "middle",
    fontFace: MONO, fontSize: 14.5,
  });
  s.addText(
    "Both passes ARE the authoritative calculator. The savings figure is not a " +
    "guess about what the engine would say — it is the engine saying it twice. " +
    "The probe fills the entire remaining statutory headroom, because partial " +
    "probes miss the regime-flip cases where the real saving lives.",
    { x: M, y: 2.95, w: W - 2 * M, h: 0.95, margin: 0, fontFace: F, fontSize: 13.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  // leave-one-out
  sectionLabel(s, M, 4.05, 11, "What each of YOUR deductions actually did — leave-one-out");
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 4.45, w: W - 2 * M, h: 0.8, rectRadius: 0.08, fill: { color: DARK },
  });
  s.addText([
    { text: "impact(i) = tax(recommended regime, item i removed) − tax(recommended regime, as booked)", options: { color: "9FD8B4" } },
  ], {
    x: M + 0.4, y: 4.45, w: W - 2 * M - 0.8, h: 0.8, margin: 0, valign: "middle",
    fontFace: MONO, fontSize: 13.5,
  });
  bullets(s, M, 5.45, W - 2 * M, 1.5, [
    { t: "Live check: a profile with Rs 5 lakh education-loan interest and Rs 2 lakh home-loan interest shows Rs 1,30,000 and Rs 41,600 of real relief — matching a hand-worked slab calculation" },
    { t: "An item is labeled \u201Capplied\u201D only when the regime's taxable income actually changes without it — let-out home-loan interest survives the new regime; self-occupied does not" },
    { t: "A control profile where the new regime wins shows Rs 0 for 80C with the statutory reason printed — honesty over flattery" },
  ], { size: 13, gap: 7 });
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 11 — Deciding what to show
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Deciding what to show — exact by construction");
  const qs = [
    ["Should this head be recommended?", "yes, when filling its statutory headroom actually reduces the cheaper regime's tax"],
    ["How much would it save?", "the recomputed difference itself — never a model's guess"],
    ["How confidently should we say so?", "0.85 when the engine verified the number; 0.30 for priced-no-benefit"],
  ];
  let qy = 1.6;
  for (const [q, a] of qs) {
    card(s, M, qy, W - 2 * M, 1.0);
    s.addText(q, { x: M + 0.3, y: qy + 0.1, w: 5.6, h: 0.8, margin: 0, valign: "middle", fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY });
    s.addText(a, { x: M + 6.1, y: qy + 0.1, w: W - 2 * M - 6.5, h: 0.8, margin: 0, valign: "middle", fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.1 });
    qy += 1.12;
  }
  s.addText(
    "On a 10,995-row validation set these rules measure precision 1.0, recall 1.0, " +
    "and a savings error of Rs 0.00. That is not a lucky split — the rules evaluate " +
    "the same closed-form expressions the calculator uses, so they cannot be wrong " +
    "unless the calculator itself is wrong. And zero-benefit heads are labeled " +
    "\u201Cno benefit\u201D in the interface, never hidden.",
    { x: M, y: 5.05, w: W - 2 * M, h: 1.4, margin: 0, fontFace: F, fontSize: 13.5, color: TEXT, lineSpacingMultiple: 1.18 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 12 — The falsification
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The falsification: a learned model made it worse");
  s.addText(
    "The obvious research step — train a neuro-fuzzy network to imitate the " +
    "engine's decisions — was tried three times with sharply more data each time. " +
    "It failed in every configuration, getting reliably worse as data grew.",
    { x: M, y: 1.5, w: W - 2 * M, h: 0.75, margin: 0, fontFace: F, fontSize: 14, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  // table
  const rows = [
    [{ text: "Data scale", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Positive rows", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Savings error", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } },
     { text: "Opportunity P/R", options: { bold: true, color: WHITE, fill: { color: PRIMARY } } }],
    ["3.5k rows", "146", "fail", "0.0 / 0.0"],
    ["77k rows", "1,623", "MAPE 795%", "0.0 / 0.0"],
    ["378k rows", "51,873", "MAPE 1,523,679%", "0.0 / 0.0"],
    [{ text: "The exact rules", options: { bold: true, color: PRIMARY, fill: { color: TINT } } },
     { text: "—", options: { fill: { color: TINT } } },
     { text: "Rs 0.00 (exact)", options: { bold: true, color: GREEN, fill: { color: TINT } } },
     { text: "1.0 / 1.0", options: { bold: true, color: GREEN, fill: { color: TINT } } }],
  ];
  s.addTable(rows, {
    x: M, y: 2.4, w: W - 2 * M, colW: [3.4, 2.6, 3.4, 2.83],
    border: { pt: 0.75, color: LINE }, fontFace: F, fontSize: 13,
    color: TEXT, align: "center", valign: "middle", rowH: 0.42,
  });
  s.addText("Why more data made it worse", {
    x: M, y: 4.75, w: 6.2, h: 0.35, margin: 0, fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  s.addText(
    "The savings label is a formula of two ratios the calculator produces — hand " +
    "those to the model and the error drops to 10⁻¹⁴. But the regime choice inside " +
    "those ratios is a discontinuous flip (a min() the rule base smooths across " +
    "instead of pinning), and the opportunity label is a simple predicate with " +
    "zero exceptions in all 377,753 rows. A rule was being asked to behave like a " +
    "distribution.",
    { x: M, y: 5.15, w: 6.2, h: 1.7, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  s.addText("The policy it produced", {
    x: 7.1, y: 4.75, w: 5.6, h: 0.35, margin: 0, fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  s.addText(
    "Learned regression on closed-form targets is permanently inadmissible, at " +
    "any data scale. The dataset (51,873 positives, 13.73% density) is kept as a " +
    "deterministic benchmark, not a growth axis. Intelligence effort moves to " +
    "ranking, explanation and adoption — never to re-pricing what the engine " +
    "already prices.",
    { x: 7.1, y: 5.15, w: 5.6, h: 1.7, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 13 — The feedback loop
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The feedback loop: the system learns what you accept");
  const steps = [
    ["Shown", "every ranked recommendation is recorded with its exact savings and confidence"],
    ["Resolved", "you accept, reject or ignore it — from the report card itself"],
    ["Aggregated", "a per-session and per-head funnel makes adoption measurable"],
    ["Applied", "one click books the headroom into your session; the engine re-prices the whole report"],
  ];
  let sy = 1.6;
  for (let i = 0; i < steps.length; i++) {
    const [h, d] = steps[i];
    s.addShape(p.shapes.OVAL, { x: M, y: sy + 0.05, w: 0.5, h: 0.5, fill: { color: ACCENT }, line: { color: ACCENT, width: 0 } });
    s.addText(String(i + 1), { x: M, y: sy + 0.05, w: 0.5, h: 0.5, margin: 0, align: "center", valign: "middle", fontFace: F, fontSize: 15, bold: true, color: WHITE });
    if (i < steps.length - 1) {
      s.addShape(p.shapes.LINE, { x: M + 0.25, y: sy + 0.58, w: 0, h: 0.34, line: { color: LINE, width: 1.5 } });
    }
    s.addText(h, { x: M + 0.72, y: sy, w: 3.0, h: 0.6, margin: 0, valign: "middle", fontFace: F, fontSize: 15, bold: true, color: PRIMARY });
    s.addText(d, { x: M + 3.6, y: sy, w: 9.0, h: 0.6, margin: 0, valign: "middle", fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.1 });
    sy += 0.92;
  }
  // live funnel numbers
  sectionLabel(s, M, 5.45, 11, "The live funnel (real data from the running system)");
  const stats = [
    ["24", "shown"], ["1", "accepted"], ["4.2%", "acceptance rate"], ["Rs 32,500", "Accepted-Rupee"],
  ];
  let sx = M;
  for (const [n, l] of stats) {
    stat(s, sx, 5.9, 3.0, n, l, n === "Rs 32,500" ? GREEN : ACCENT, 30);
    sx += 3.1;
  }
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 14 — Calibration & the gate
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Confidence, calibrated — and gated");
  s.addText(
    "The confidence the system serves today is a constant: 0.85 when the engine " +
    "verified the number, 0.30 for priced-no-benefit. A constant is defensible " +
    "because its meaning can be stated in one line. Whether a LEARNED confidence " +
    "may replace it is instrumented, not assumed.",
    { x: M, y: 1.55, w: W - 2 * M, h: 1.05, margin: 0, fontFace: F, fontSize: 14, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  // ECE band
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 2.75, w: W - 2 * M, h: 0.85, rectRadius: 0.08, fill: { color: DARK },
  });
  s.addText([
    { text: "ECE = Σ (|B_b| / N) · |accuracy(B_b) − confidence(B_b)|      over 10 equal-width bins", options: { color: "9FD8B4" } },
  ], {
    x: M + 0.4, y: 2.75, w: W - 2 * M - 0.8, h: 0.85, margin: 0, valign: "middle",
    fontFace: MONO, fontSize: 14,
  });
  bullets(s, M, 3.85, 7.3, 2.2, [
    { t: "The instrument is validated by a known-answer canary: 200 constructed pairs whose acceptance equals each bin's average confidence must measure exactly 0.0 — and they do" },
    { t: "The flipped outcome set must flag as miscalibrated — it does, at 0.85" },
    { t: "The first canary failed: with ten items per bin, banker's rounding turned a perfect construction into a fake 0.05 — twenty items per bin makes every count exact" },
  ], { size: 12.5, gap: 7 });
  // gate card
  card(s, 8.35, 3.85, 4.43, 2.2);
  s.addText("The standing gate", { x: 8.6, y: 4.0, w: 3.9, h: 0.3, margin: 0, fontFace: F, fontSize: 13.5, bold: true, color: PRIMARY });
  s.addText(
    "No learned confidence ships until it measures ECE \u2264 0.05 on at least 30 " +
    "resolved acceptance events without hurting the acceptance rate.",
    { x: 8.6, y: 4.35, w: 3.9, h: 1.0, margin: 0, fontFace: F, fontSize: 12, color: TEXT, lineSpacingMultiple: 1.12 }
  );
  s.addText(
    "The store currently holds one resolved event — so the honest measurement is " +
    "\u201Cunmeasured,\u201D and the anchor stays.",
    { x: 8.6, y: 5.4, w: 3.9, h: 0.6, margin: 0, fontFace: F, fontSize: 12, italic: true, color: MUTED, lineSpacingMultiple: 1.1 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 15 — The explainable CA layer
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "The explainable CA layer: rules you can argue with");
  s.addText(
    "A neuro-fuzzy system is, structurally, a set of readable rules — and that is " +
    "exactly the shape of how a chartered accountant reasons: graded, conditional " +
    "judgments combined into a plan. The failed regression experiment above was " +
    "the wrong use of that shape; this is the right one.",
    { x: M, y: 1.5, w: W - 2 * M, h: 0.95, margin: 0, fontFace: F, fontSize: 13.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  // the fired rule example
  card(s, M, 2.6, W - 2 * M, 1.35);
  s.addText("A rule, decoded — as it fires for a real session", {
    x: M + 0.3, y: 2.75, w: 11.5, h: 0.3, margin: 0, fontFace: F, fontSize: 13, bold: true, color: PRIMARY,
  });
  s.addText([
    { text: "IF income is mid AND 80C headroom is large AND the taxpayer is young, ", options: { color: PRIMARY, bold: true } },
    { text: "THEN an NPS top-up is a strong opportunity — the separate Rs 50,000 slot over and above the 80C ceiling (old regime only).", options: { color: TEXT } },
  ], {
    x: M + 0.3, y: 3.1, w: 11.6, h: 0.7, margin: 0, valign: "top",
    fontFace: F, fontSize: 13, lineSpacingMultiple: 1.12,
  });
  bullets(s, M, 4.2, W - 2 * M, 1.9, [
    { t: "Every rule that fires for your session is shown in the report — \u201CHow the CA Layer Thinks\u201D — with its strength, next to the exact numbers" },
    { t: "Plans, not just single tips: combinations like \u201Cadd NPS + claim pending 80D\u201D, each priced by the engine" },
    { t: "The whole rule book can be decoded into sentences a person can argue with — nothing opaque, nothing learned" },
  ], { size: 13, gap: 7 });
  s.addText(
    "The division of labor: the engine prices; the fuzzy layer reasons, in readable " +
    "form; and nothing either of them says is trusted until the engine confirms the rupees.",
    { x: M, y: 6.3, w: W - 2 * M, h: 0.55, margin: 0, fontFace: F, fontSize: 13, italic: true, color: PRIMARY }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 16 — Verification
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Verification — and why clicking counts as testing");
  const tiles = [
    ["1,166", "backend tests"], ["31", "frontend tests"], ["7", "browser end-to-end flows"], ["3", "CI jobs per push"],
  ];
  let tx = M;
  for (const [n, l] of tiles) {
    stat(s, tx, 1.6, 3.0, n, l, ACCENT, 38);
    tx += 3.1;
  }
  s.addText("What the tests cover", {
    x: M, y: 3.05, w: 6.3, h: 0.35, margin: 0, fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  bullets(s, M, 3.45, 6.3, 2.9, [
    { t: "The engine against hand-computed statutory cases" },
    { t: "The language chain, including adversarial numbering and Hinglish" },
    { t: "Session ownership, rate limits and the adoption store" },
    { t: "The impact calculation's sign and new-regime behavior" },
    { t: "The calibration instrument against its known-answer canary" },
  ], { size: 12.5, gap: 6 });
  s.addText("The habit that paid for itself", {
    x: 7.2, y: 3.05, w: 5.6, h: 0.35, margin: 0, fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  s.addText(
    "Five real defects this project shipped through code review and full test " +
    "suites — a sign-inverted benefit, a skipped capture path, orphaned " +
    "identifiers — were caught only by clicking through the running product. " +
    "Manual end-to-end sessions are therefore a first-class release gate here, " +
    "not a courtesy.",
    { x: 7.2, y: 3.45, w: 5.6, h: 2.0, margin: 0, fontFace: F, fontSize: 12.5, color: TEXT, lineSpacingMultiple: 1.15 }
  );
  s.addText(
    "Two tagged releases shipped through CI-gated pull requests; the full suite " +
    "was re-run on the merged result both times.",
    { x: M, y: 6.5, w: W - 2 * M, h: 0.45, margin: 0, fontFace: F, fontSize: 12.5, italic: true, color: MUTED }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 17 — Limitations
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Limitations, stated plainly");
  const lims = [
    ["Salaried profiles are deepest", "business and capital-gains flows exist but are thinner — I would not trust the business paths for anything real yet"],
    ["One certified year", "FY 2025-26 is the certified year; a new fiscal year means adding a rules registry and re-certifying (designed for, not yet exercised)"],
    ["Confidence is unmeasured", "the instrument is proven but the store holds one resolved event — a sample of one measures nothing"],
    ["The explainable CA layer is new", "the rules are authored and reviewed, but real-practitioner sign-off is still pending"],
    ["It advises; it does not file", "nothing here submits anything to the tax authority"],
  ];
  let ly = 1.65;
  for (const [h, d] of lims) {
    s.addText([
      { text: h + " — ", options: { bold: true, color: PRIMARY } },
      { text: d, options: { color: TEXT } },
    ], {
      x: M, y: ly, w: W - 2 * M, h: 0.85, margin: 0, valign: "top",
      fontFace: F, fontSize: 13.5, lineSpacingMultiple: 1.15,
    });
    ly += 1.02;
  }
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 18 — Conclusion & future work
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Conclusion");
  s.addText(
    "A tax advisor can be exact — and exactness is an architectural property, " +
    "not a model quality. One deterministic calculator, everything else " +
    "subordinate, costs almost nothing in capability and converts a trust problem " +
    "into an engineering one.",
    { x: M, y: 1.6, w: W - 2 * M, h: 1.05, margin: 0, fontFace: F, fontSize: 15.5, color: TEXT, lineSpacingMultiple: 1.18 }
  );
  s.addText("What comes next follows the evidence", {
    x: M, y: 2.9, w: 11, h: 0.35, margin: 0, fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  bullets(s, M, 3.3, W - 2 * M, 1.9, [
    { t: "Widen the evidence-based adoption instruments: the dashboard, the funnel, the Accepted-Rupee metric" },
    { t: "Explainable CA reasoning validated against a practicing professional's judgment" },
    { t: "Personalization and calibrated confidence — only when the adoption store crosses its gates" },
    { t: "A FY 2026-27 rules drop: the first real test of the registry's forward compatibility" },
  ], { size: 13.5, gap: 8 });
  s.addText(
    "If the project keeps one machine-learning artifact, it is a negative result " +
    "with the mechanism written down. If it keeps one gate, it is the one that " +
    "keeps a model out until the data exists to judge it.",
    { x: M, y: 5.35, w: W - 2 * M, h: 1.0, margin: 0, fontFace: F, fontSize: 14, italic: true, color: PRIMARY, lineSpacingMultiple: 1.18 }
  );
  pageNo(s);
}

// ---------------------------------------------------------------------------
// SLIDE 19 — Thank you (dark)
// ---------------------------------------------------------------------------
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addText("THANK YOU", {
    x: M + 0.15, y: 2.0, w: 11, h: 0.4, margin: 0,
    fontFace: F, fontSize: 14, bold: true, color: ACCENT, charSpacing: 3,
  });
  s.addText("Questions welcome.", {
    x: M + 0.15, y: 2.45, w: 11.5, h: 1.0, margin: 0,
    fontFace: F, fontSize: 44, bold: true, color: WHITE,
  });
  s.addText(
    "Every number in this deck is recomputable from the linked repository — " +
    "seeded, scripted, and certified.",
    { x: M + 0.15, y: 3.6, w: 10.5, h: 0.6, margin: 0, fontFace: F, fontSize: 14, color: LIGHTTXT }
  );
  s.addText([
    { text: "Jayant (12406581) · Roll No. RK4P24MZA06", options: { breakLine: true } },
    { text: "CSE472 · Deep Learning for Natural Language Processing · November 2026", options: { breakLine: true } },
    { text: "github.com/Jayant1711/Tax_Assist-system", options: {} },
  ], {
    x: M + 0.15, y: 5.2, w: 9.0, h: 1.2, margin: 0,
    fontFace: F, fontSize: 12.5, color: "9FB2C4", paraSpaceAfter: 4,
  });
}

p.writeFile({ fileName: "TaxAssist_NLP_Final_Presentation.pptx" })
  .then(() => console.log("v4 deck written"));
