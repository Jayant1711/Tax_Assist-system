// Tax Assist — NLP Course Project Presentation (v3)
// Full-project story · NLP/ML deep focus · 20 slides · 13.33x7.5
const pptxgen = require("pptxgenjs");

const p = new pptxgen();
p.layout = "LAYOUT_WIDE";
p.author = "Tax Assist Project";
p.title = "Tax Assist — AI-Powered Indian Tax Consultant (NLP Project)";

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
const F = "Segoe UI";
const MONO = "Consolas";
const KICKER = "TAX ASSIST · NLP COURSE PROJECT";

const bu = () => ({ code: "2022", indent: 12 });
const sh = () => ({ type: "outer", color: "8B98A5", blur: 6, offset: 2, angle: 90, opacity: 0.16 });

function header(s, title) {
  s.addText(KICKER, {
    x: M, y: 0.42, w: 8.0, h: 0.3, margin: 0,
    fontFace: F, fontSize: 12, bold: true, color: ACCENT, charSpacing: 2,
  });
  s.addText(title, {
    x: M, y: 0.72, w: W - 2 * M, h: 0.62, margin: 0,
    fontFace: F, fontSize: 30, bold: true, color: TEXT,
  });
}
let PAGE = 1; // auto page counter: first call renders "02"
function pageNo(s, _n, opts = {}) {
  PAGE += 1;
  s.addText(String(PAGE).padStart(2, "0"), {
    x: opts.x == null ? W - 1.0 : opts.x, y: opts.y == null ? H - 0.52 : opts.y,
    w: 0.5, h: 0.3, margin: 0, align: "right",
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
function codePanel(s, x, y, w, h, lines, fs = 13) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, fill: { color: DARK }, rectRadius: 0.08,
    shadow: { type: "outer", color: "1A2733", blur: 7, offset: 3, angle: 45, opacity: 0.25 },
  });
  const runs = lines.map((l) => ({ text: l.t, options: { color: l.c || "D7E3F0", breakLine: true } }));
  s.addText(runs, {
    x: x + 0.28, y: y + 0.18, w: w - 0.56, h: h - 0.36, margin: 0, valign: "top",
    fontFace: MONO, fontSize: fs, paraSpaceAfter: 6,
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

// ---- clickable "show me the code" links (open VS Code at file:line) -------
const REPO = "C:/Users/lenovo/Desktop/Tax_Assist-system-main/Tax_Assist-system-main";
function codeLinks(s, links) {
  // links: [{label, path, line}] — rendered right-aligned at top, in order
  const H = 0.34;
  let totalW = 0;
  const widths = links.map((l) => 0.42 + l.label.length * 0.068);
  widths.forEach((w) => { totalW += w + 0.14; });
  let x = W - M - totalW + 0.14;
  links.forEach((l, i) => {
    const w = widths[i];
    const url = l.line ? `vscode://file/${REPO}/${l.path}:${l.line}` : `vscode://file/${REPO}/${l.path}`;
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x, y: 0.42, w, h: H, rectRadius: 0.09, fill: { color: TINT2 },
      line: { color: "B9CDDC", width: 0.75 },
    });
    s.addText([{
      text: l.label,
      options: {
        hyperlink: { url, tooltip: `Open ${l.path} at line ${l.line} in VS Code` },
        color: ACCENT, bold: true,
      },
    }], {
      x: x + 0.05, y: 0.42, w: w - 0.1, h: H, margin: 0, align: "center", valign: "middle",
      fontFace: MONO, fontSize: 10,
    });
    x += w + 0.14;
  });
}
function card(s, x, y, w, h, fill = WHITE) {
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.07, fill: { color: fill }, line: { color: LINE, width: 0.75 }, shadow: sh(),
  });
}
function arrowH(s, x, y, w, color = PRIMARY) {
  s.addShape(p.shapes.LINE, { x, y, w, h: 0, line: { color, width: 2.25, endArrowType: "triangle" } });
}
function arrowV(s, x, y, h, color = PRIMARY) {
  s.addShape(p.shapes.LINE, { x, y, w: 0, h, line: { color, width: 2.25, endArrowType: "triangle" } });
}

// =========================================================================
// 1 — TITLE
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addText("NATURAL LANGUAGE PROCESSING · COURSE PROJECT", {
    x: 1.0, y: 1.5, w: 11.3, h: 0.35, margin: 0,
    fontFace: F, fontSize: 14, bold: true, color: ACCENT, charSpacing: 3,
  });
  s.addText("Tax Assist", {
    x: 1.0, y: 1.95, w: 11.3, h: 1.15, margin: 0,
    fontFace: F, fontSize: 64, bold: true, color: WHITE,
  });
  s.addText("An AI-powered consultant for Indian income tax — a chat that understands\nplain English & Hinglish, and computes FY 2025-26 liability correctly", {
    x: 1.0, y: 3.2, w: 11.2, h: 0.95, margin: 0,
    fontFace: F, fontSize: 19, color: "B9C8D6",
  });
  const metas = ["FY 2025-26 rules", "SEED 472 · CPU-reproducible", "1,225+ tests green", "November 2026"];
  let mx = 1.0;
  metas.forEach((t) => {
    const w = 0.32 + t.length * 0.105;
    chip(s, mx, 4.7, w, t, { fill: "16395C", color: "D7E3F0", h: 0.5, size: 13 });
    mx += w + 0.25;
  });
  s.addText("Presented by the project team", {
    x: 1.0, y: 6.55, w: 11.0, h: 0.35, margin: 0,
    fontFace: F, fontSize: 13, color: "7E93A6",
  });
}

// =========================================================================
// 2 — INTRODUCTION & MOTIVATION
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Introduction & Motivation");
  pageNo(s, 2);

  card(s, M, 1.75, 5.6, 4.95);
  s.addText("What we built", {
    x: 0.85, y: 2.0, w: 5.0, h: 0.35, margin: 0,
    fontFace: F, fontSize: 16, bold: true, color: PRIMARY,
  });
  s.addText("A conversational tax assistant. The user describes income and investments the way they would to a human CA —", {
    x: 0.85, y: 2.42, w: 5.0, h: 0.85, margin: 0,
    fontFace: F, fontSize: 13.5, color: TEXT,
  });
  codePanel(s, 0.85, 3.32, 5.0, 0.78, [
    { t: '"I earn 18 LPA, invest 1.5 lakhs in PPF,', c: "9FD8B4" },
    { t: ' and pay 12,000 rent monthly"', c: "9FD8B4" },
  ], 12);
  bullets(s, 0.85, 4.28, 5.0, 2.3, [
    { t: "Books every amount to the right tax category" },
    { t: "Computes liability under old & new regimes" },
    { t: "Suggests legal optimizations + efficiency score" },
    { t: "Form-driven e-filing tools force users to already know tax — a conversation doesn't" },
  ], { size: 12.5, gap: 8 });

  const rows = [
    ["1,25,000", "Indian numbering", "A comma between digits is grouping, not grammar. Off-the-shelf tokenizers split it into three false clauses."],
    ["21", "statutory categories", "80C, 80D, 80G, 80U/80DD, 24(b), 80GG… each with its own limits, Hinglish cues and follow-up questions."],
    ["×2", "mixed language", "'40 lakhs', '45k pm', 'vyapar', 'kiraya' — currency shorthand and Hinglish verbs inside English sentences."],
  ];
  rows.forEach((r, i) => {
    const y = 1.75 + i * 1.7;
    card(s, 6.55, y, 6.2, 1.5);
    s.addText(r[0], {
      x: 6.85, y: y + 0.22, w: 1.85, h: 1.05, margin: 0, valign: "middle",
      fontFace: F, fontSize: r[0].length > 4 ? 30 : 40, bold: true, color: ACCENT,
    });
    s.addText(r[1], {
      x: 8.85, y: y + 0.22, w: 3.7, h: 0.35, margin: 0,
      fontFace: F, fontSize: 15, bold: true, color: PRIMARY,
    });
    s.addText(r[2], {
      x: 8.85, y: y + 0.58, w: 3.72, h: 0.85, margin: 0,
      fontFace: F, fontSize: 11.5, color: MUTED,
    });
  });
}

// =========================================================================
// 3 — OBJECTIVES
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Project Objectives");
  pageNo(s, 3);

  const objs = [
    ["Conversational understanding", "Parse plain English + Hinglish with Indian numbering, units and statutory vocabulary", "NLP"],
    ["Correct-by-construction math", "Every rupee computed by a deterministic rule engine — zero hallucinated numbers", "ML→rules"],
    ["Machine-learning depth", "Embeddings, intent classification, NER, seq2seq attention, transformers, neuro-fuzzy ANFIS", "ML"],
    ["Production quality", "Accounts, server-side sessions, audit trail, rate limiting, Docker deployment", "SE"],
    ["Verified behavior", "1,225+ automated tests across backend, frontend and end-to-end flows", "QA"],
    ["Reproducible science", "Every experiment seeded (472) and re-runnable offline on CPU", "ML"],
  ];
  objs.forEach((o, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.25, y = 1.8 + row * 1.68;
    card(s, x, y, 5.95, 1.48);
    chip(s, x + 0.28, y + 0.24, 1.05, o[2], { fill: o[2] === "ML" ? DARK : TINT, color: o[2] === "ML" ? WHITE : PRIMARY, b: true, h: 0.4, size: 11 });
    s.addText(o[0], {
      x: x + 1.5, y: y + 0.18, w: 4.3, h: 0.38, margin: 0,
      fontFace: F, fontSize: 14.5, bold: true, color: TEXT,
    });
    s.addText(o[1], {
      x: x + 0.28, y: y + 0.68, w: 5.4, h: 0.72, margin: 0,
      fontFace: F, fontSize: 11.5, color: MUTED,
    });
  });
}

// =========================================================================
// 4 — TECHNOLOGY STACK
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Technology Stack");
  pageNo(s, 4);

  const stacks = [
    ["Frontend", ["Next.js 16.4 · React 19 · TypeScript", "Chat UI, login & session flows", "Talks to API over REST + cookies"]],
    ["Backend API", ["Python · FastAPI · Pydantic", "14 REST endpoints (/chat, /calculate…)", "Wire-level request validation"]],
    ["NLP Engine (production)", ["NumPy · regex guard layer", "UniversalParser + semantic attention", "Amounts → categories → sessions"]],
    ["ML / research layer", ["PyTorch · TF-IDF + LogReg", "Word2Vec & GloVe from scratch", "ANFIS neuro-fuzzy scorer"]],
    ["Data", ["SQLite · SQLAlchemy ORM", "2,226-record JSONL corpus", "Append-only audit stream"]],
    ["Infrastructure & QA", ["Docker Compose · GitHub Actions CI", "pytest 1,099 · Vitest 22", "Playwright E2E 7"]],
  ];
  stacks.forEach((st, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = M + col * 4.15, y = 1.85 + row * 2.5;
    card(s, x, y, 3.93, 2.28);
    s.addText(st[0], {
      x: x + 0.26, y: y + 0.2, w: 3.4, h: 0.4, margin: 0,
      fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
    });
    bullets(s, x + 0.26, y + 0.68, 3.45, 1.5, st[1].map((t) => ({ t })), { size: 11.5, gap: 7 });
  });
}

// =========================================================================
// 5 — SYSTEM ARCHITECTURE (full-stack layered diagram)
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "System Architecture");
  pageNo(s, 5);
  codeLinks(s, [{ label: "</> main.py · app", path: "backend/main.py", line: 1 }]);

  const layerLbl = (t, y) => s.addText(t.toUpperCase(), {
    x: M, y, w: 4.0, h: 0.24, margin: 0,
    fontFace: F, fontSize: 10.5, bold: true, color: MUTED, charSpacing: 1.5,
  });
  const band = (y, h) => {
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x: M, y, w: W - 2 * M, h, rectRadius: 0.07, fill: { color: WHITE },
      line: { color: LINE, width: 0.75 }, shadow: sh(),
    });
  };

  // L1 client
  layerLbl("Client layer", 1.56);
  band(1.84, 0.92);
  s.addText("Next.js 16 · React 19 · TypeScript", {
    x: 0.85, y: 1.84, w: 5.4, h: 0.92, margin: 0, valign: "middle",
    fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  s.addText("chat UI · login & session flow · regime comparison views", {
    x: 6.4, y: 1.84, w: 6.2, h: 0.92, margin: 0, valign: "middle", align: "right",
    fontFace: F, fontSize: 12, color: MUTED,
  });
  arrowV(s, 6.665, 2.78, 0.26);

  // L2 API
  layerLbl("API layer", 3.06);
  band(3.34, 1.04);
  s.addText("FastAPI + Pydantic — validates every request at the wire", {
    x: 0.85, y: 3.46, w: 7.7, h: 0.34, margin: 0,
    fontFace: F, fontSize: 13.5, bold: true, color: PRIMARY,
  });
  s.addText("/auth/* · /chat · /calculate · /sessions · /history · /health", {
    x: 0.85, y: 3.84, w: 7.6, h: 0.34, margin: 0,
    fontFace: MONO, fontSize: 11.5, color: TEXT,
  });
  s.addText("rate limits · CORS allowlist · 1 MB body cap", {
    x: 8.7, y: 3.46, w: 3.9, h: 0.86, margin: 0, valign: "middle", align: "right",
    fontFace: F, fontSize: 11.5, color: MUTED,
  });
  arrowV(s, 6.665, 4.4, 0.26);

  // L3 intelligence — three engines
  layerLbl("Intelligence layer", 4.68);
  const engines = [
    ["NLP Engine", "regex guards · UniversalParser\nsemantic attention · response\ncomposer — understands the user"],
    ["Tax Engine", "FY 2024-25 & 2025-26 rule\nregistries · slab computation ·\nold vs new regime comparison"],
    ["ANFIS model", "20-input neuro-fuzzy scorer ·\n64 rules · tax-efficiency\nscore 0–100 for the results view"],
  ];
  engines.forEach((e, i) => {
    const x = M + i * 4.15;
    card(s, x, 4.96, 3.93, 1.62);
    s.addText(e[0], {
      x: x + 0.26, y: 5.12, w: 3.4, h: 0.34, margin: 0,
      fontFace: F, fontSize: 14, bold: true, color: i === 0 ? ACCENT : PRIMARY,
    });
    s.addText(e[1], {
      x: x + 0.26, y: 5.48, w: 3.45, h: 1.0, margin: 0,
      fontFace: F, fontSize: 10.5, color: MUTED,
    });
    if (i < 2) arrowH(s, x + 3.95, 5.77, 0.18);
  });
  arrowV(s, 6.665, 6.6, 0.22);

  // L4 data & security
  band(6.86, 0.56);
  const l4 = [
    ["SQLite — users · sessions · tax data", TINT, PRIMARY],
    ["JSONL audit — append-only", TINT, PRIMARY],
    ["scrypt + HttpOnly cookies", TINT, PRIMARY],
    ["2,226-record NLP corpus", TINT, PRIMARY],
  ];
  let lx = 0.85;
  l4.forEach((c) => {
    const w = 0.3 + c[0].length * 0.082;
    chip(s, lx, 6.94, w, c[0], { fill: c[1], color: c[2], h: 0.4, size: 11 });
    lx += w + 0.22;
  });
}

// =========================================================================
// 6 — END-TO-END WORKFLOW (query lifecycle)
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "End-to-End Workflow — One Query's Journey");
  pageNo(s, 6);
  codeLinks(s, [{ label: "</> main.py · /chat :1138", path: "backend/main.py", line: 1138 }]);

  const steps = [
    ["1", "User input", "Typed into the chat UI — plain English or Hinglish, no forms", '"I am a software engineer earning 18 LPA"'],
    ["2", "API gateway", "POST /chat with the session cookie; auth, rate limit (30/min), 1 MB cap", "{ message, session_id }"],
    ["3", "Preprocessing", "Prepass guards mask %/dates; Indian comma groups stay whole", "18 LPA → 1,800,000"],
    ["4", "Understanding", "UniversalParser extracts the amount; semantic attention scores categories", "category = salary"],
    ["5", "Tax computation", "TaxEngine applies FY 2025-26 slabs; computes both regimes", "liability + regime Δ"],
    ["6", "Response", "Summary, savings tips, next discovery question, ANFIS score", "efficiency: 82.1 / 100"],
  ];
  steps.forEach((st, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = M + col * 4.15, y = 1.78 + row * 2.62;
    card(s, x, y, 3.93, 2.38);
    s.addText(st[0], {
      x: x + 0.2, y: y + 0.16, w: 0.7, h: 0.85, margin: 0,
      fontFace: F, fontSize: 40, bold: true, color: i === 5 ? ACCENT : PRIMARY,
    });
    s.addText(st[1], {
      x: x + 1.0, y: y + 0.22, w: 2.85, h: 0.38, margin: 0,
      fontFace: F, fontSize: 14.5, bold: true, color: TEXT,
    });
    s.addText(st[2], {
      x: x + 1.0, y: y + 0.62, w: 2.8, h: 0.95, margin: 0,
      fontFace: F, fontSize: 10.5, color: MUTED,
    });
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x: x + 0.2, y: y + 1.68, w: 3.53, h: 0.52, rectRadius: 0.06, fill: { color: DARK },
    });
    s.addText(st[3], {
      x: x + 0.34, y: y + 1.68, w: 3.3, h: 0.52, margin: 0, valign: "middle",
      fontFace: MONO, fontSize: 10, color: "9FD8B4",
    });
    if (col < 2) arrowH(s, x + 3.95, y + 1.19, 0.18);
  });
}

// =========================================================================
// 7 — NLP ENGINE PIPELINE (production processing chain)
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Inside the NLP Engine — Processing Chain");
  pageNo(s, 7);
  codeLinks(s, [{ label: "</> nlp_engine.py · process_message :599", path: "backend/nlp_engine.py", line: 599 }]);

  const stages = [
    ["Sentence & clause split", "Splits on 'and' / ';' / commas — but a comma between digits is grouping, never a boundary"],
    ["Prepass guards", "Percentages, dates, flat statutory amounts and transfer years are masked or booked as flags before parsing"],
    ["Digit & word parsing", "UniversalParser — digit forms (1,25,000 · 18 LPA · 45k pm), word numbers ('thirty five lakhs'), Hinglish numerals"],
    ["Semantic attention", "Every keyword votes for a category with distance-decayed weight; the amount books to the winner"],
    ["Session state update", "Corrections subtract; profile-default guesses can never overwrite a real booked value"],
    ["Response composition", "Acknowledgement text + next discovery question + savings tips, rendered from engine results"],
  ];
  stages.forEach((st, i) => {
    const y = 1.72 + i * 0.86;
    card(s, M, y, W - 2 * M, 0.74);
    chip(s, 0.75, y + 0.15, 0.5, String(i + 1), { fill: DARK, color: WHITE, b: true, h: 0.44, size: 14 });
    s.addText(st[0], {
      x: 1.45, y: y + 0.08, w: 3.1, h: 0.58, margin: 0, valign: "middle",
      fontFace: F, fontSize: 13, bold: true, color: PRIMARY,
    });
    s.addText(st[1], {
      x: 4.7, y: y + 0.08, w: 7.95, h: 0.58, margin: 0, valign: "middle",
      fontFace: F, fontSize: 11, color: TEXT,
    });
    if (i < 5) arrowV(s, 1.0, y + 0.755, 0.1, ACCENT);
  });
}

// =========================================================================
// 8 — TEXT PREPROCESSING
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Text Preprocessing — Indian Numbering & Units");
  pageNo(s, 8);
  codeLinks(s, [{ label: "</> nlp_engine.py · comma splitter :102", path: "backend/nlp_engine.py", line: 102 }]);

  s.addText("The comma problem — solved with one regex", {
    x: M, y: 1.62, w: 7.0, h: 0.32, margin: 0,
    fontFace: F, fontSize: 13.5, bold: true, color: PRIMARY,
  });
  codePanel(s, M, 1.98, 7.1, 1.28, [
    { t: 'split_naive = re.compile(r"[,;]")', c: "F0A8A0" },
    { t: '"claimed 1,25,000 under 80c"', c: "D7E3F0" },
    { t: "→  ['claimed 1', '25', '000 under 80c']   # broken", c: "F0A8A0" },
  ], 12.5);
  codePanel(s, M, 3.42, 7.1, 1.62, [
    { t: '_SPLIT_RE = re.compile(r"(?<!\\d)[,;](?!\\d)")', c: "7FD1A8" },
    { t: '"claimed 1,25,000 under 80c"', c: "D7E3F0" },
    { t: "→  ['claimed 1,25,000 under 80c']   # whole", c: "7FD8B4" },
  ], 12.5);
  s.addText("A comma is a boundary only when neither neighbor is a digit — lookbehind + lookahead encode the rule.", {
    x: M, y: 5.2, w: 7.1, h: 0.6, margin: 0,
    fontFace: F, fontSize: 12.5, italic: true, color: PRIMARY,
  });

  // right: unit normalization table
  card(s, 8.05, 1.62, 4.7, 5.15);
  s.addText("Canonical unit normalization", {
    x: 8.35, y: 1.84, w: 4.1, h: 0.35, margin: 0,
    fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  const units = [
    ["lakh / lac / lpa", "× 1,00,000"],
    ["crore / cr", "× 1,00,00,000"],
    ["k / thousand", "× 1,000"],
    ["pm / per month", "× 12 (annualized)"],
    ["'thirty five lakhs'", "word-form → 35,00,000"],
    ["'paanch hazaar'", "Hinglish numeral → 5,000"],
  ];
  units.forEach((u, i) => {
    const y = 2.32 + i * 0.62;
    s.addText(u[0], {
      x: 8.35, y, w: 2.3, h: 0.5, margin: 0, valign: "middle",
      fontFace: MONO, fontSize: 11.5, color: TEXT,
    });
    s.addText(u[1], {
      x: 10.7, y, w: 1.95, h: 0.5, margin: 0, valign: "middle", align: "right",
      fontFace: F, fontSize: 11.5, bold: true, color: ACCENT,
    });
    if (i < 5) s.addShape(p.shapes.LINE, { x: 8.35, y: y + 0.56, w: 4.05, h: 0, line: { color: LINE, width: 0.75 } });
  });
  s.addText("All values clamped to ₹0 – ₹100 crore after conversion", {
    x: 8.35, y: 6.12, w: 4.1, h: 0.5, margin: 0,
    fontFace: F, fontSize: 11, color: MUTED,
  });
}

// =========================================================================
// 9 — AMOUNT & ENTITY EXTRACTION
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Amount & Entity Extraction");
  pageNo(s, 9);
  codeLinks(s, [{ label: "</> ai_models.py · digit_pat :49", path: "backend/ai_models.py", line: 49 }]);

  // left: extraction demo
  codePanel(s, M, 1.75, 7.1, 0.75, [
    { t: '"I claimed 1,25,000 under section 80c and 80u_80dd"', c: "9FD8B4" },
  ], 13.5);
  const ents = [
    ["MONEY", "1,25,000"],
    ["TAX_SECTION", "80c · 80u_80dd"],
    ["DEDUCTION_TYPE", "80c · 80u_80dd"],
    ["INCOME_TYPE", "salary · business · rental…"],
    ["DATE", "1 april 2024 · FY 2025-26"],
    ["PERCENTAGE", "30% · 5.5 percent"],
  ];
  ents.forEach((e, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 3.65, y = 2.72 + row * 1.0;
    card(s, x, y, 3.45, 0.84);
    s.addText(e[0], {
      x: x + 0.2, y: y + 0.1, w: 3.05, h: 0.3, margin: 0,
      fontFace: MONO, fontSize: 11, bold: true, color: PRIMARY,
    });
    s.addText(e[1], {
      x: x + 0.2, y: y + 0.42, w: 3.05, h: 0.3, margin: 0,
      fontFace: MONO, fontSize: 10.5, color: MUTED,
    });
  });

  // right: the phantom-8 fix
  card(s, 8.05, 1.75, 4.7, 4.95);
  s.addText("The phantom '8' bug — fixed", {
    x: 8.35, y: 1.97, w: 4.1, h: 0.35, margin: 0,
    fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  s.addText("A single pattern read '80u_80dd' as amount 80 with unit 'u' — the statutory deduction became ₹80 of income.", {
    x: 8.35, y: 2.38, w: 4.1, h: 0.85, margin: 0,
    fontFace: F, fontSize: 11.5, color: TEXT,
  });
  codePanel(s, 8.35, 3.32, 4.1, 1.15, [
    { t: "# two-alternative guard", c: "7E93A6" },
    { t: "(80u_80dd\\b | 80u\\b)", c: "7FD1A8" },
    { t: "# full token matches first", c: "7E93A6" },
  ], 12);
  bullets(s, 8.35, 4.68, 4.1, 1.9, [
    { t: "Longest alternative wins — 80u_80dd never decays into '80'" },
    { t: "Two-pass parser: digit forms first, word forms skip digit spans" },
    { t: "Values below ₹100 discarded (noise floor)" },
  ], { size: 11.5, gap: 8 });
}

// =========================================================================
// 10 — SEMANTIC ATTENTION
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Semantic Attention — Where Amounts Belong");
  pageNo(s, 10);
  codeLinks(s, [{ label: "</> ai_models.py · attention :417", path: "backend/ai_models.py", line: 417 }]);

  s.addText("score(keyword) = 100 · e^(−d² / (2·40²))     d = distance to the amount, in characters", {
    x: M, y: 1.66, w: 12.2, h: 0.35, margin: 0,
    fontFace: MONO, fontSize: 13.5, bold: true, color: PRIMARY,
  });

  // left: proximity demo bars
  card(s, M, 2.2, 6.1, 3.05);
  s.addText('"invested 1.5 lakhs in PPF … pay 2L rent"', {
    x: 0.85, y: 2.38, w: 5.5, h: 0.3, margin: 0,
    fontFace: MONO, fontSize: 11.5, color: TEXT,
  });
  const demo = [
    ["PPF", "d = 6", 0.95, "80C wins the ₹1.5L"],
    ["rent", "d = 34", 0.35, "…and rent wins the ₹2L"],
  ];
  demo.forEach((d, i) => {
    const y = 2.85 + i * 1.05;
    s.addText(d[0], {
      x: 0.85, y, w: 0.85, h: 0.34, margin: 0,
      fontFace: MONO, fontSize: 12, bold: true, color: TEXT,
    });
    s.addText(d[1], {
      x: 0.85, y: y + 0.34, w: 0.85, h: 0.28, margin: 0,
      fontFace: F, fontSize: 10, color: MUTED,
    });
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 1.85, y: y + 0.06, w: 3.4, h: 0.4, rectRadius: 0.06, fill: { color: TINT2 } });
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 1.85, y: y + 0.06, w: 3.4 * d[2], h: 0.4, rectRadius: 0.06, fill: { color: i === 0 ? ACCENT : PRIMARY } });
    s.addText(d[3], {
      x: 1.85, y: y + 0.52, w: 4.0, h: 0.3, margin: 0,
      fontFace: F, fontSize: 10.5, italic: true, color: MUTED,
    });
  });

  // right: scoring rules
  card(s, 7.0, 2.2, 5.75, 3.05);
  s.addText("How a category wins", {
    x: 7.3, y: 2.4, w: 5.1, h: 0.35, margin: 0,
    fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
  });
  bullets(s, 7.3, 2.85, 5.15, 2.3, [
    { t: "Proximity decays Gaussian — nearby keywords dominate" },
    { t: "Content score favors longer, multi-word phrases" },
    { t: "Longer phrases subsume their substrings" },
    { t: "Profile priors: business keywords damped for salaried users (×0.1)" },
    { t: "Negation families ('rent received' ≠ 'rent paid') veto −10×" },
  ], { size: 11.5, gap: 7 });

  // bottom band
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 5.55, w: W - 2 * M, h: 1.3, rectRadius: 0.07, fill: { color: TINT },
  });
  s.addText([
    { text: "Guarded fallback: ", options: { bold: true, color: PRIMARY } },
    { text: "when nothing scores above threshold, the amount falls to a profile default but is flagged as a guess — a guess can never overwrite a value the user actually stated (the C4a overwrite guard).", options: { color: TEXT } },
  ], {
    x: 0.85, y: 5.7, w: 11.6, h: 1.0, margin: 0, valign: "middle",
    fontFace: F, fontSize: 13,
  });
}

// =========================================================================
// 11 — WORD EMBEDDINGS FROM SCRATCH
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Word Embeddings — Built From Scratch");
  pageNo(s, 11);
  codeLinks(s, [{ label: "</> embedding_analysis.py · SGNS :138", path: "nlp_research/embedding_analysis.py", line: 138 }]);

  s.addText([
    { text: "Why from scratch? ", options: { bold: true, color: ACCENT } },
    { text: "no gensim wheels exist for our Python build — so we implemented both algorithms in pure NumPy, fully reproducible at SEED 472.", options: { color: TEXT } },
  ], {
    x: M, y: 1.62, w: W - 2 * M, h: 0.55, margin: 0, fontFace: F, fontSize: 15,
  });

  const models = [
    ["Word2Vec · Skip-gram", "50", [
      "Predicts context from center word (SGNS)",
      "Window 5 · 5 negatives · Adam optimizer",
      "Vocabulary from the 2,226-record corpus",
      "Learns: salary ≈ pay · 80c ≈ 80d families",
    ]],
    ["GloVe · co-occurrence", "100", [
      "Factorizes the global co-occurrence matrix",
      "f(x) = min(1, (x/x_max)^α) weighting",
      "Adagrad weighted least-squares solver",
      "Artifacts: embeddings_sgns / _glove .npy",
    ]],
  ];
  models.forEach((m, i) => {
    const x = M + i * 6.25;
    card(s, x, 2.35, 5.95, 4.35);
    s.addText(m[0], {
      x: x + 0.3, y: 2.58, w: 4.1, h: 0.7, margin: 0,
      fontFace: F, fontSize: 15.5, bold: true, color: PRIMARY,
    });
    s.addText([
      { text: m[1], options: { fontSize: 46, bold: true, color: i ? PRIMARY : ACCENT, breakLine: true } },
      { text: "dimensions", options: { fontSize: 12, color: MUTED } },
    ], { x: x + 4.4, y: 2.42, w: 1.4, h: 1.05, margin: 0, fontFace: F });
    bullets(s, x + 0.3, 3.6, 5.35, 2.9, m[2].map((t) => ({ t })), { size: 12.5, gap: 10 });
  });
}

// =========================================================================
// 12 — EMBEDDING GEOMETRY (PCA / t-SNE)
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Reading the Embedding Geometry — PCA & t-SNE");
  pageNo(s, 12);
  codeLinks(s, [{ label: "</> embedding_analysis.py · GloVe :222", path: "nlp_research/embedding_analysis.py", line: 222 }]);

  card(s, M, 1.8, 4.4, 5.0, DARK);
  s.addText("78%", {
    x: 0.9, y: 2.25, w: 3.7, h: 1.2, margin: 0,
    fontFace: F, fontSize: 72, bold: true, color: WHITE,
  });
  s.addText("of variance captured by the top 10 PCA dimensions of the SGNS space", {
    x: 0.9, y: 3.55, w: 3.6, h: 1.0, margin: 0,
    fontFace: F, fontSize: 14, color: "C4D3E0",
  });
  s.addText("artifacts: embeddings_{pca,tsne}_{sgns,glove}.png", {
    x: 0.9, y: 5.9, w: 3.6, h: 0.7, margin: 0,
    fontFace: MONO, fontSize: 10.5, color: "7E93A6",
  });

  const rows = [
    ["PCA — the global map", "Linear projection via covariance eigendecomposition. Income and deduction classes separate at macro scale; eigenvalue decay quantifies each axis's signal."],
    ["t-SNE — local neighborhoods", "Nonlinear reduction minimizing KL divergence between pairwise probabilities. Fine clusters emerge: 80c / 80d / 80g / 80u_80dd group tightly."],
    ["Key finding", "Template coverage is essential for OOV anchoring — rare Hinglish tokens only land in the right neighborhood when templates seed them."],
  ];
  rows.forEach((r, i) => {
    const y = 1.8 + i * 1.72;
    card(s, 5.3, y, 7.45, 1.52);
    s.addText(r[0], {
      x: 5.6, y: y + 0.16, w: 6.8, h: 0.35, margin: 0,
      fontFace: F, fontSize: 14.5, bold: true, color: PRIMARY,
    });
    s.addText(r[1], {
      x: 5.6, y: y + 0.54, w: 6.85, h: 0.9, margin: 0,
      fontFace: F, fontSize: 12, color: TEXT,
    });
  });
}

// =========================================================================
// 13 — INTENT CLASSIFICATION (+ native chart)
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Intent Classification");
  pageNo(s, 13);
  codeLinks(s, [{ label: "</> phase_c · TF-IDF :117", path: "nlp_research/phase_c_intent_classification.py", line: 117 }]);

  // left: mapping
  card(s, M, 1.8, 6.1, 2.62);
  s.addText("21 production categories", {
    x: 0.85, y: 2.02, w: 2.5, h: 0.4, margin: 0,
    fontFace: F, fontSize: 13.5, bold: true, color: MUTED,
  });
  s.addText("→", {
    x: 3.35, y: 1.98, w: 0.6, h: 0.5, margin: 0, align: "center",
    fontFace: F, fontSize: 28, bold: true, color: ACCENT,
  });
  s.addText("8 intents", {
    x: 4.05, y: 2.02, w: 2.4, h: 0.4, margin: 0,
    fontFace: F, fontSize: 13.5, bold: true, color: PRIMARY,
  });
  const classes = ["salary", "business", "capital_gains", "property", "deductions", "agriculture", "investment", "other"];
  classes.forEach((c, i) => {
    const col = i % 4, row = Math.floor(i / 4);
    chip(s, 0.85 + col * 1.36, 2.75 + row * 0.62, 1.26, c, { mono: true, size: 10.5, h: 0.48 });
  });
  s.addText("PROD_TO_INTENT table · template-disjoint train/test splits · per-class P/R/F1 + confusion matrix", {
    x: 0.85, y: 3.9, w: 5.5, h: 0.45, margin: 0,
    fontFace: F, fontSize: 10.5, color: MUTED,
  });

  // right: stat
  card(s, 7.0, 1.8, 5.75, 2.62, DARK);
  s.addText([
    { text: "96.41%", options: { fontSize: 46, bold: true, color: WHITE, breakLine: true } },
    { text: "TF-IDF + Logistic Regression — 2,226 samples, CPU-only", options: { fontSize: 12.5, color: "C4D3E0" } },
  ], { x: 7.35, y: 2.1, w: 5.0, h: 1.9, margin: 0, fontFace: F });

  // bottom: chart
  card(s, M, 4.62, W - 2 * M, 2.5);
  s.addText("Per-class F1 — the classical baseline", {
    x: 0.85, y: 4.78, w: 6.0, h: 0.3, margin: 0,
    fontFace: F, fontSize: 13, bold: true, color: PRIMARY,
  });
  s.addChart(p.charts.BAR, [{
    name: "F1",
    labels: ["capital_gains", "agriculture", "business", "salary", "property", "deductions"],
    values: [1.0, 1.0, 1.0, 0.994, 0.982, 0.975],
  }], {
    x: 0.8, y: 5.1, w: 11.6, h: 1.85, barDir: "bar",
    chartColors: ["E8590C", "E8590C", "E8590C", "1A4A73", "1A4A73", "1A4A73"],
    varyColors: true,
    chartArea: { fill: { color: "FFFFFF" } },
    catAxisLabelColor: "5D6C7B", catAxisLabelFontSize: 10, catAxisLabelFontFace: F,
    valAxisLabelColor: "5D6C7B", valAxisLabelFontSize: 9, valAxisLabelFontFace: F,
    valAxisMinVal: 0.9, valAxisMaxVal: 1.0,
    valGridLine: { color: "E2E8F0", size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: "182230", dataLabelFontSize: 9.5, dataLabelFontFace: F,
    showLegend: false, showTitle: false,
  });
}

// =========================================================================
// 14 — NER
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Named Entity Recognition");
  pageNo(s, 14);
  codeLinks(s, [{ label: "</> phase_d · BiLSTM NER :368", path: "nlp_research/phase_d_ner.py", line: 368 }]);

  const ents = [
    ["MONEY", "1,25,000 · 18 LPA · 50 lakhs"],
    ["TAX_SECTION", "80c · 80d · 24b · 80u_80dd"],
    ["INCOME_TYPE", "salary · business · capital_gains"],
    ["DEDUCTION_TYPE", "80c · 80d · 80g · 80u_80dd"],
    ["DATE", "1 april 2024 · FY 2025-26"],
    ["PERCENTAGE", "30% · 5.5 percent"],
  ];
  ents.forEach((e, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = M + col * 6.25, y = 1.8 + row * 1.28;
    card(s, x, y, 5.95, 1.08);
    chip(s, x + 0.25, y + 0.18, 2.3, e[0], { mono: true, fill: DARK, color: WHITE, b: true, h: 0.42, size: 11.5 });
    s.addText(e[1], {
      x: x + 2.75, y: y + 0.18, w: 3.0, h: 0.42, margin: 0, valign: "middle",
      fontFace: MONO, fontSize: 11, color: TEXT,
    });
    s.addText("BIO-tagged sequence labels", {
      x: x + 0.25, y: y + 0.64, w: 3.0, h: 0.3, margin: 0,
      fontFace: F, fontSize: 10, color: MUTED,
    });
  });

  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 5.85, w: W - 2 * M, h: 1.0, rectRadius: 0.07, fill: { color: TINT },
  });
  s.addText([
    { text: "Honest finding, documented: ", options: { bold: true, color: PRIMARY } },
    { text: "our BiLSTM tagger (256-dim hidden) reaches 0.143 accuracy on a 51-sample template corpus — a low-data regime result we report as a finding, not hide. Statutory sections stay template-driven in production.", options: { color: TEXT } },
  ], {
    x: 0.85, y: 6.0, w: 11.6, h: 0.75, margin: 0, valign: "middle",
    fontFace: F, fontSize: 12.5,
  });
}

// =========================================================================
// 15 — SEQ2SEQ & ATTENTION
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Seq2Seq & Attention — Encoder–Decoder Study");
  pageNo(s, 15);
  codeLinks(s, [{ label: "</> phase_e · Bahdanau :157", path: "nlp_research/phase_e_seq2seq.py", line: 157 }, { label: "</> Luong :183", path: "nlp_research/phase_e_seq2seq.py", line: 183 }]);

  const attn = [
    ["Bahdanau — additive", "score(s_t, h_i) = vᵃᵀ tanh(Wᵃ s_t + Uᵃ h_i)", "A small feed-forward net scores every encoder state against the decoder state — flexible but heavier."],
    ["Luong — dot-product", "score(s_t, h_i) = s_tᵀ Wᵃ h_i", "A bilinear form — cheaper; the study quantifies when the difference matters."],
  ];
  attn.forEach((a, i) => {
    const x = M + i * 6.25;
    card(s, x, 1.8, 5.95, 2.35);
    s.addText(a[0], {
      x: x + 0.3, y: 2.0, w: 5.3, h: 0.35, margin: 0,
      fontFace: F, fontSize: 15, bold: true, color: PRIMARY,
    });
    codePanel(s, x + 0.3, 2.45, 5.35, 0.62, [{ t: a[1], c: "9FD8B4" }], 12);
    s.addText(a[2], {
      x: x + 0.3, y: 3.2, w: 5.35, h: 0.8, margin: 0,
      fontFace: F, fontSize: 12, color: TEXT,
    });
  });

  card(s, M, 4.5, W - 2 * M, 2.2);
  s.addText("Task setup", {
    x: 0.85, y: 4.7, w: 3.0, h: 0.35, margin: 0,
    fontFace: F, fontSize: 14, bold: true, color: PRIMARY,
  });
  bullets(s, 0.85, 5.12, 5.6, 1.5, [
    { t: "Encoder–decoder LSTM · hidden 128 · embeddings 64" },
    { t: "150 input/target pairs from the Indian tax domain" },
    { t: "Character-level vocabulary — full statutory coverage" },
  ], { size: 12.5, gap: 8 });
  s.addText("Documented simplification", {
    x: 7.0, y: 4.7, w: 4.5, h: 0.35, margin: 0,
    fontFace: F, fontSize: 14, bold: true, color: ACCENT,
  });
  s.addText("Full attention training is complex in a minimal PyTorch environment. ATTENTION_STUDY.md documents the mechanics, formulas and trade-offs — the analysis is the deliverable.", {
    x: 7.0, y: 5.12, w: 5.35, h: 1.4, margin: 0,
    fontFace: F, fontSize: 12, color: TEXT,
  });
}

// =========================================================================
// 16 — TRANSFORMER EXPERIMENTS
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Transformer Experiments — BERT · GPT-2 · T5");
  pageNo(s, 16);

  const models = [
    ["BERT", "bert-base-uncased · 110M", [
      "Joint intent + deduction-section head",
      "Full fine-tune blocked: no GPU in env",
      "TF-IDF fallback closes the gap — 96.41%",
    ]],
    ["GPT-2", "causal LM · 1.5B", [
      "Prompted with tax scenarios, temp 0.7",
      "Fluent completions — but hallucinates",
      "Statutory numbers can't be trusted ungrounded",
    ]],
    ["T5-small", "enc–dec · 220M", [
      "'summarize:' prefix on tax queries",
      "20 prompt/response pairs evaluated",
      "Architecture study documented for discussion",
    ]],
  ];
  models.forEach((m, i) => {
    const x = M + i * 4.15;
    card(s, x, 1.8, 3.93, 3.3);
    s.addText(m[0], {
      x: x + 0.26, y: 2.0, w: 3.4, h: 0.42, margin: 0,
      fontFace: F, fontSize: 19, bold: true, color: PRIMARY,
    });
    s.addText(m[1], {
      x: x + 0.26, y: 2.44, w: 3.4, h: 0.3, margin: 0,
      fontFace: MONO, fontSize: 10.5, color: MUTED,
    });
    bullets(s, x + 0.26, 2.86, 3.42, 2.1, m[2].map((t) => ({ t })), { size: 11, gap: 8 });
  });

  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 5.45, w: W - 2 * M, h: 1.4, rectRadius: 0.07, fill: { color: DARK },
  });
  s.addText([
    { text: "What the experiments taught us → ", options: { bold: true, color: "F0A870" } },
    { text: "generative models are excellent at language but cannot guarantee a single correct rupee. That is exactly why production keeps ALL computation in the deterministic TaxEngine — the NLP layer extracts and composes, never calculates.", options: { color: "D7E3F0" } },
  ], {
    x: 0.85, y: 5.6, w: 11.6, h: 1.1, margin: 0, valign: "middle",
    fontFace: F, fontSize: 13.5,
  });
  codeLinks(s, [
    { label: "</> phase_f · BERT", path: "nlp_research/phase_f_bert_classification.py", line: 117 },
    { label: "</> phase_g · GPT-2/T5", path: "nlp_research/phase_g_generative.py", line: 49 },
  ]);
}

// =========================================================================
// 17 — MODEL EVALUATION PROTOCOL & RESULTS
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Evaluating the NLP / ML Models");
  pageNo(s, 17);
  codeLinks(s, [
    { label: "</> phase_i · evaluation", path: "nlp_research/phase_i_evaluation.py", line: 382 },
  ]);

  // left: protocol card
  card(s, M, 1.75, 4.55, 4.55);
  s.addText("Evaluation protocol", {
    x: 0.85, y: 1.97, w: 4.0, h: 0.38, margin: 0,
    fontFace: F, fontSize: 15.5, bold: true, color: PRIMARY,
  });
  bullets(s, 0.85, 2.45, 3.95, 3.7, [
    { t: "2,226 labeled records → template-disjoint train / test splits (test utterances never share a template with train)" },
    { t: "Every split, init and shuffle fixed at SEED 472 — re-runnable offline on CPU" },
    { t: "Metrics: accuracy · per-class precision / recall / F1 · confusion matrix (sklearn)" },
    { t: "Weak results reported honestly — e.g. NER under low data" },
    { t: "Generative models evaluated qualitatively on 20 curated prompt/response pairs" },
  ], { size: 11.5, gap: 9 });

  // right: results table
  card(s, 5.3, 1.75, 7.45, 4.55);
  s.addText("Results across the model zoo", {
    x: 5.6, y: 1.97, w: 6.0, h: 0.38, margin: 0,
    fontFace: F, fontSize: 15.5, bold: true, color: PRIMARY,
  });
  const th = { fill: { color: DARK }, color: WHITE, bold: true, fontFace: F, fontSize: 10.5, valign: "middle" };
  const td = { color: TEXT, fontFace: F, fontSize: 10.5, valign: "middle" };
  const tm = { color: MUTED, fontFace: MONO, fontSize: 9.5, valign: "middle" };
  const tr = { color: ACCENT, fontFace: F, fontSize: 10.5, bold: true, align: "center", valign: "middle" };
  s.addTable([
    [{ text: "Model", options: th }, { text: "Task", options: th }, { text: "Metric", options: th }, { text: "Result", options: th }],
    [{ text: "TF-IDF + LogReg", options: td }, { text: "Intent (8-class)", options: td }, { text: "accuracy", options: tm }, { text: "96.41%", options: tr }],
    [{ text: "SGNS / GloVe", options: td }, { text: "Embeddings", options: td }, { text: "geometry", options: tm }, { text: "78% var", options: tr }],
    [{ text: "BiLSTM tagger", options: td }, { text: "NER (51 samples)", options: td }, { text: "accuracy", options: tm }, { text: "0.143", options: tr }],
    [{ text: "GPT-2 · T5", options: td }, { text: "Generative study", options: td }, { text: "20 pairs", options: tm }, { text: "qualitative", options: tr }],
    [{ text: "ANFIS", options: td }, { text: "Efficiency score", options: td }, { text: "regression", options: tm }, { text: "0–100", options: tr }],
  ], {
    x: 5.6, y: 2.45, w: 6.85, colW: [1.7, 2.75, 1.1, 1.3],
    border: { pt: 0.75, color: LINE },
    fill: { color: WHITE },
    rowH: 0.5, margin: 0.06,
  });
  s.addText("Honest finding: BiLSTM NER reflects a 51-sample low-data regime — documented, not hidden.", {
    x: 5.6, y: 5.88, w: 6.9, h: 0.35, margin: 0,
    fontFace: F, fontSize: 11, italic: true, color: MUTED,
  });

  // bottom band: what evaluation drives
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 6.5, w: W - 2 * M, h: 0.62, rectRadius: 0.07, fill: { color: TINT },
  });
  s.addText([
    { text: "Why it matters → ", options: { bold: true, color: PRIMARY } },
    { text: "evaluation gates what ships: only the 96.41% intent baseline made production; everything weaker stayed in the research layer.", options: { color: TEXT } },
  ], {
    x: 0.85, y: 6.5, w: 11.6, h: 0.62, margin: 0, valign: "middle",
    fontFace: F, fontSize: 12.5,
  });
}

// =========================================================================
// 17 — ANFIS NEURO-FUZZY MODEL (diagram)
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "ANFIS — The Neuro-Fuzzy Efficiency Scorer");
  codeLinks(s, [{ label: "</> ai_models.py · ANFIS :595", path: "backend/ai_models.py", line: 595 }, { label: "</> anfis_trainer.py :154", path: "backend/anfis_trainer.py", line: 154 }]);
  pageNo(s, 17);

  // input chips above first stage
  const inChips = ["income/1e7", "80c/150k", "80d/25k", "nps/50k", "…×20"];
  let cx = M;
  inChips.forEach((c) => {
    const w = 0.24 + c.length * 0.085;
    chip(s, cx, 1.62, w, c, { mono: true, fill: TINT, size: 10, h: 0.36 });
    cx += w + 0.14;
  });

  const stages = [
    ["Inputs", "20 session features,\nmin-max scaled to 0–1", "salary · 80c · 80d\nnps · hra · 24b …"],
    ["Gaussian MFs", "μ(x) per input per rule\nbell-shaped membership", "64 rules total"],
    ["Firing strength", "w = Π μᵢ(x)\nproduct across the\nrule's 20 inputs", "Takagi–Sugeno–Kang"],
    ["Normalize + TSK", "w̄ = w / Σw\nf = Σ w̄ · (a·x + b)\nleast-squares consequents", "defuzzified output"],
    ["Score", "single crisp output\nscaled to 0–100", "tax-efficiency grade"],
  ];
  const sw = 2.28, shh = 1.9, sg = 0.22, sx0 = M, sy = 2.14;
  stages.forEach((st, i) => {
    const x = sx0 + i * (sw + sg);
    const last = i === 4;
    s.addShape(p.shapes.ROUNDED_RECTANGLE, {
      x, y: sy, w: sw, h: shh, rectRadius: 0.07,
      fill: { color: last ? DARK : WHITE },
      line: { color: last ? DARK : LINE, width: 0.75 }, shadow: sh(),
    });
    s.addText(st[0], {
      x: x + 0.14, y: sy + 0.14, w: sw - 0.28, h: 0.36, margin: 0,
      fontFace: F, fontSize: 12.5, bold: true, color: last ? "F0A870" : PRIMARY,
    });
    s.addText(st[1], {
      x: x + 0.14, y: sy + 0.54, w: sw - 0.28, h: 0.95, margin: 0,
      fontFace: F, fontSize: 10, color: last ? "C4D3E0" : MUTED,
    });
    s.addText(st[2], {
      x: x + 0.14, y: sy + 1.5, w: sw - 0.28, h: 0.34, margin: 0,
      fontFace: MONO, fontSize: 9.5, color: last ? "9FD8B4" : ACCENT,
    });
    if (i < 4) arrowH(s, x + sw + 0.015, sy + shh / 2, sg - 0.03);
  });

  // bottom: notes
  card(s, M, 4.45, W - 2 * M, 2.3);
  s.addText("Where it lives & how it behaves", {
    x: 0.85, y: 4.65, w: 6.0, h: 0.35, margin: 0,
    fontFace: F, fontSize: 14, bold: true, color: PRIMARY,
  });
  bullets(s, 0.85, 5.08, 11.6, 1.5, [
    { t: "Runs in production: the results screen shows the user their 0–100 tax-efficiency grade (e.g. 82.1)" },
    { t: "Weights trained offline and shipped as anfis_weights.json — inference is pure NumPy matrix math" },
    { t: "Graceful degradation: if NumPy is unavailable, a deterministic heuristic (80C/80D/NPS utilization) substitutes — never a crash" },
  ], { size: 12.5, gap: 9 });
}

// =========================================================================
// 18 — TAX ENGINE & RESPONSE BRIDGE
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Tax Engine & the Response Bridge");
  pageNo(s, 18);
  codeLinks(s, [{ label: "</> tax_engine.py :238", path: "backend/tax_engine.py", line: 238 }, { label: "</> fy_2025_26.py :1", path: "backend/tax_rules/fy_2025_26.py", line: 1 }]);

  // left: engine
  card(s, M, 1.8, 5.95, 3.7);
  s.addText("Deterministic Tax Engine", {
    x: 0.85, y: 2.02, w: 5.3, h: 0.38, margin: 0,
    fontFace: F, fontSize: 15.5, bold: true, color: PRIMARY,
  });
  bullets(s, 0.85, 2.5, 5.35, 2.9, [
    { t: "FY 2024-25 and FY 2025-26 rule registries" },
    { t: "Slab computation + surcharge + 4% health cess" },
    { t: "Old vs new regime compared, best picked for the user" },
    { t: "Every rupee traceable to a rule — auditable by design" },
    { t: "1,099 backend tests pin the numbers down" },
  ], { size: 12.5, gap: 10 });

  // right: bridge mini-flow
  card(s, 6.85, 1.8, 5.9, 3.7);
  s.addText("Response composer bridge", {
    x: 7.15, y: 2.02, w: 5.3, h: 0.38, margin: 0,
    fontFace: F, fontSize: 15.5, bold: true, color: PRIMARY,
  });
  codePanel(s, 7.15, 2.5, 5.3, 2.75, [
    { t: "intent   = classify_intent(text)", c: "9FD8B4" },
    { t: "entities = extract_entities(text)", c: "9FD8B4" },
    { t: "query    = compose_tax_engine_query(", c: "D7E3F0" },
    { t: "              intent, entities)", c: "D7E3F0" },
    { t: "result   = TaxEngine.execute(query)", c: "9FD8B4" },
    { t: "response = human_summary(result)", c: "9FD8B4" },
  ], 11.5);

  // bottom band
  s.addShape(p.shapes.ROUNDED_RECTANGLE, {
    x: M, y: 5.8, w: W - 2 * M, h: 1.05, rectRadius: 0.07, fill: { color: TINT },
  });
  s.addText([
    { text: "Zero-hallucination architecture: ", options: { bold: true, color: PRIMARY } },
    { text: "language models propose, the rule engine disposes. NLP can misunderstand and recover — it can never invent a wrong tax number.", options: { color: TEXT } },
  ], {
    x: 0.85, y: 5.92, w: 11.6, h: 0.8, margin: 0, valign: "middle",
    fontFace: F, fontSize: 13,
  });
}

// =========================================================================
// 19 — RESULTS & TESTING
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: BG };
  header(s, "Results & System Verification");
  pageNo(s, 19);
  codeLinks(s, [{ label: "</> backend/tests/ · 1,099 tests", path: "backend/tests" }]);

  const stats = [
    ["1,099", "pytest cases", "backend modules, all green"],
    ["97", "legacy tests", "pre-sprint suites preserved"],
    ["22", "Vitest units", "frontend logic"],
    ["7", "Playwright E2E", "browser flows, localhost"],
  ];
  stats.forEach((st, i) => {
    const x = M + i * 3.12;
    card(s, x, 1.85, 2.9, 2.35);
    s.addText(st[0], {
      x: x + 0.25, y: 2.1, w: 2.4, h: 0.95, margin: 0,
      fontFace: F, fontSize: 44, bold: true, color: i === 0 ? ACCENT : PRIMARY,
    });
    s.addText(st[1], {
      x: x + 0.25, y: 3.08, w: 2.4, h: 0.35, margin: 0,
      fontFace: F, fontSize: 14, bold: true, color: TEXT,
    });
    s.addText(st[2], {
      x: x + 0.25, y: 3.45, w: 2.45, h: 0.55, margin: 0,
      fontFace: F, fontSize: 11, color: MUTED,
    });
  });

  card(s, M, 4.55, 6.1, 2.2, DARK);
  s.addText([
    { text: "1,225+", options: { fontSize: 46, bold: true, color: WHITE, breakLine: true } },
    { text: "tests green across the full stack — 6 pre-existing environment/test-debt failures triaged separately, zero regressions", options: { fontSize: 12, color: "C4D3E0" } },
  ], { x: 0.9, y: 4.82, w: 5.3, h: 1.65, margin: 0, fontFace: F });

  card(s, 7.0, 4.55, 5.75, 2.2);
  s.addText("Quality audit scores", {
    x: 7.3, y: 4.75, w: 4.0, h: 0.35, margin: 0,
    fontFace: F, fontSize: 13.5, bold: true, color: PRIMARY,
  });
  const scores = [["Architecture", "86"], ["Security", "88"], ["Testing", "91"], ["Production readiness", "90"]];
  scores.forEach((sc, i) => {
    const y = 5.18 + i * 0.38;
    s.addText(sc[0], {
      x: 7.3, y, w: 2.2, h: 0.3, margin: 0, valign: "middle",
      fontFace: F, fontSize: 11.5, color: TEXT,
    });
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 9.75, y: y + 0.045, w: 1.9, h: 0.22, rectRadius: 0.05, fill: { color: TINT2 } });
    s.addShape(p.shapes.ROUNDED_RECTANGLE, { x: 9.75, y: y + 0.045, w: 1.9 * (sc[1] / 100), h: 0.22, rectRadius: 0.05, fill: { color: PRIMARY } });
    s.addText(sc[1], {
      x: 11.75, y, w: 0.5, h: 0.3, margin: 0, valign: "middle",
      fontFace: F, fontSize: 11.5, bold: true, color: PRIMARY,
    });
  });
}

// =========================================================================
// 20 — CONCLUSION & FUTURE WORK (dark)
// =========================================================================
{
  const s = p.addSlide();
  s.background = { color: DARK };
  s.addText("CONCLUSION", {
    x: 1.0, y: 0.8, w: 11.0, h: 0.35, margin: 0,
    fontFace: F, fontSize: 13, bold: true, color: ACCENT, charSpacing: 3,
  });
  s.addText("A complete system — with language at its core.", {
    x: 1.0, y: 1.2, w: 11.4, h: 0.9, margin: 0,
    fontFace: F, fontSize: 36, bold: true, color: WHITE,
  });

  const sums = [
    ["1,225+", "tests green — production\nstability proven"],
    ["96.41%", "intent accuracy from a\nclassical baseline"],
    ["2,226", "labeled corpus records\ndriving every model"],
    ["₹0", "hallucinated tax numbers —\ndeterministic engine only"],
  ];
  sums.forEach((sm, i) => {
    const x = 1.0 + i * 2.95;
    s.addText(sm[0], {
      x, y: 2.5, w: 2.75, h: 0.75, margin: 0,
      fontFace: F, fontSize: 34, bold: true, color: i === 3 ? "F0A870" : WHITE,
    });
    s.addText(sm[1], {
      x, y: 3.28, w: 2.75, h: 0.75, margin: 0,
      fontFace: F, fontSize: 11.5, color: "AFC2D1",
    });
  });

  s.addShape(p.shapes.LINE, { x: 1.0, y: 4.35, w: 11.3, h: 0, line: { color: "27455F", width: 1 } });

  s.addText("What comes next", {
    x: 1.0, y: 4.55, w: 5.0, h: 0.35, margin: 0,
    fontFace: F, fontSize: 13, bold: true, color: "D7E3F0",
  });
  const fut = [
    ["Fine-tune BERT on annotated Indian tax documents"],
    ["Multilingual queries — Hindi & regional languages"],
    ["LoRA adapters for GPT-2/T5 domain tuning"],
    ["Integration with the ITD e-filing portal"],
  ];
  fut.forEach((t, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    s.addText("▸  " + t, {
      x: 1.0 + col * 5.8, y: 5.0 + row * 0.5, w: 5.6, h: 0.4, margin: 0,
      fontFace: F, fontSize: 12, color: "9FB4C6",
    });
  });

  s.addText("Thank you — questions welcome", {
    x: 1.0, y: 6.35, w: 11.0, h: 0.5, margin: 0,
    fontFace: F, fontSize: 20, bold: true, color: WHITE,
  });
  s.addText("Tax Assist · NLP course project · SEED 472 · November 2026", {
    x: 1.0, y: 6.95, w: 11.0, h: 0.35, margin: 0,
    fontFace: F, fontSize: 11.5, color: "7E93A6",
  });
}

// ---- write ---------------------------------------------------------------
p.writeFile({ fileName: "TaxAssist_NLP_Final_Presentation_v3.pptx" })
  .then(() => console.log("DECK WRITTEN (v3, project-focused)"))
  .catch((e) => { console.error(e); process.exit(1); });
