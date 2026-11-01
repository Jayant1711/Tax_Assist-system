# Summer internship project
"""Full-fidelity corpus capture for test/verification dataset growth.

Sprint 3 follow-up (Sprint4_AI_Modernization.md §1 — dataset strategy):
every chat turn can be captured COMPLETE — session id, full user input,
full AI response, extraction deltas, plan, tax summary and the full
server-side state — so real interactions become golden regression
fixtures ("until we become perfect": every conversation is a test case).

Design:

- **Separate stream** (``TAX_CORPUS_PATH``, default
  ``logs/corpus/corpus.jsonl``) — the certified audit path
  (audit_logger.py) is deliberately NOT touched: the audit stream keeps
  its PII-minimized schema and the corpus carries the full-fidelity
  records the dataset strategy needs.
- **Opt-in**: ``TAX_CORPUS_CAPTURE=1``. Default OFF — full transcripts
  are PII (DPDP); enable only on deployments whose users consented
  (local dev / testing is the intended use).
- **Best-effort, never fatal**: a capture failure logs a warning and the
  chat turn is unaffected. The caller wraps the call in a background
  task.
- **Append-only**: writes go through ``audit_logger.append_jsonl_line``
  (same process-wide lock + torn-tail discipline as the audit stream).
  The corpus grows unbounded by design — prune/archive it like any
  dataset (see the converter: tests/tools/corpus_to_golden.py).
- **Full fidelity**: raw input + raw response are stored VERBATIM (no
  512-char cap — this stream exists because the capped audit stream is
  not enough for dataset work).
"""
import logging
import os
from typing import Any, Dict, Optional

from audit_logger import append_jsonl_line

logger = logging.getLogger(__name__)

CORPUS_VERSION = 1


def corpus_capture_enabled() -> bool:
    """TAX_CORPUS_CAPTURE opt-in flag (read at write time, default off)."""
    return os.environ.get("TAX_CORPUS_CAPTURE", "").strip() in {
        "1",
        "true",
        "True",
    }


def corpus_path() -> str:
    """Corpus stream location (TAX_CORPUS_PATH, documented default)."""
    return os.environ.get("TAX_CORPUS_PATH", "logs/corpus/corpus.jsonl")


def _json_safe(value: Any) -> Any:
    """Convert engine artifacts to JSON-safe types.

    Handles: numpy scalars (``.item()``), TaxResult dataclass instances
    (``dataclasses.asdict`` — the engine returns regime objects as
    dataclasses, and json.dumps rejects them), and containers of both.
    """
    import dataclasses

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_safe(dataclasses.asdict(value))
    if hasattr(value, "item"):  # numpy scalar -> Python scalar
        return value.item()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def capture_chat_turn(
    session_id: str,
    user_id: Optional[str],
    user_input: str,
    ai_response: str,
    extracted: Any,
    plan: Optional[str],
    state: Dict[str, Any],
    tax_report: Any,
) -> bool:
    """Append one full-fidelity chat-turn record to the corpus stream.

    Best-effort by contract: any failure logs a warning and returns False
    — the chat turn itself is never affected. Returns True when the line
    was captured.

    *session_id* must already be sanitized (``safe_session_id``) — the
    caller passes the server-issued id, which the store validated at
    creation.
    """
    if not corpus_capture_enabled():
        return False
    try:
        entry: Dict[str, Any] = _json_safe({
            "event": "chat_turn",
            "corpus_version": CORPUS_VERSION,
            "timestamp": _utcnow(),
            "session_id": session_id,
            "user_id": user_id,
            "user_input": user_input,
            "ai_response": ai_response,
            "extracted": extracted,
            "plan": plan,
            "state": state,
            "tax_report": tax_report,
        })
        path = corpus_path()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        append_jsonl_line(path, entry, session_id)
        return True
    except Exception as exc:  # best-effort: never break the chat turn
        logger.warning(
            "corpus capture failed (session_id_sha256_16=%.16s): %s",
            session_id,
            exc,
        )
        return False


def _utcnow() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# =========================================================================
# Sprint 4 P0 — labeled dataset layout + loader
# (docs/sprint4-execution.md P0 items 1 + 4)
#
# ADDITIVE to the capture stream above: capture_chat_turn keeps writing
# the full-fidelity runtime stream; this section defines the COMMITTED
# labeled dataset (data/{training,validation,test,corpus}/*.jsonl +
# manifest.json) that the eval framework (nlp_eval.py) measures the
# pipeline against.
#
# Layout (dataset root, resolved by dataset_root()):
#   data/training/*.jsonl    ~70% of labeled utterances
#   data/validation/*.jsonl  ~15% — the eval split (P0 baseline, P1 gate)
#   data/test/*.jsonl        ~15% — holdout (opened at the P3 verdict)
#   data/corpus/*.jsonl      runtime capture stream (organic pool; may be
#                            empty — populated by TAX_CORPUS_CAPTURE=1)
#   data/manifest.json       content-addressed build manifest
#
# NOTE: the dataset root is the REPO-LEVEL data/ directory. backend/data/
# is the gitignored SQLite store (db.py) and must never hold the corpus.
# =========================================================================
import hashlib
import json as _json
import re as _re
from pathlib import Path as _Path
from typing import Counter as _Counter
from typing import Dict as _Dict
from typing import Iterable as _Iterable
from typing import List as _List
from typing import Tuple as _Tuple

from ai_models import SemanticAttention

CORPUS_SCHEMA_VERSION = 1

# The 21-label taxonomy: 20 BOOKABLE SemanticAttention categories + ABSTAIN.
# Generated from the live category table at import — never retyped.
#
# ABSTAIN: "this amount must not be booked anywhere — ask instead of
# guessing" (ages, percentages, non-bookable loans, meta questions). A
# labeled ABSTAIN span is correct only when the pipeline books nothing
# for it.
ABSTAIN = "ABSTAIN"

# 80EEA is NOT bookable: docs/tax-verification.md §6 — the section is
# DISCONTINUED (loans must have been sanctioned before April 2022), the
# engine answers a mention with an advisory and never writes state.
NON_BOOKABLE_CATEGORIES: _Tuple[str, ...] = ("80eea",)

_ALL_CATEGORIES: _Tuple[str, ...] = tuple(SemanticAttention().categories.keys())
BOOKABLE_CATEGORIES: _Tuple[str, ...] = tuple(
    cat for cat in _ALL_CATEGORIES if cat not in NON_BOOKABLE_CATEGORIES
)
TAXONOMY: _Tuple[str, ...] = BOOKABLE_CATEGORIES + (ABSTAIN,)

# category -> the session keys the pipeline books that category into.
# Every bookable category books a numeric session key of the same name;
# capital_gains books a LIST of {type, amount, holding} entries under the
# same key (nlp_engine.py assignment rules). The mapping is asserted
# complete against BOOKABLE_CATEGORIES below.
CATEGORY_SESSION_KEYS: _Dict[str, _Tuple[str, ...]] = {
    cat: (cat,) for cat in BOOKABLE_CATEGORIES
}

# Enum-collection session keys: the flat 80U/80DD deduction is collected
# as a disability CATEGORY (40-79% vs 80%+), not an amount
# (docs/tax-verification.md §6; nlp_engine.py pre-parse guard). The eval
# treats a booked enum as a predicted (80u_80dd, amount=None) span when
# no numeric 80u_80dd value was booked. (80g_category stays out: an 80G
# donation books BOTH the amount and the donee enum, and the amount span
# is the primary prediction — counting the enum too would double-count.)
SESSION_ENUM_KEYS: _Dict[str, str] = {"80u_80dd_category": "80u_80dd"}

SPLIT_NAMES: _Tuple[str, ...] = ("training", "validation", "test", "corpus")
EVAL_SPLIT = "validation"
HOLDOUT_SPLIT = "test"
SOURCES: _Tuple[str, ...] = ("synthetic", "ledger", "organic")
LANGS: _Tuple[str, ...] = ("en", "hinglish")

# Per-category floors (docs/sprint4-execution.md P0 item 2): >=50 records
# per bookable category corpus-wide, >=15 spans per category in the eval
# split. A category that misses its floor even synthetically is listed
# as synthetic-backed in provenance and reported in the health report.
CATEGORY_FLOOR_TOTAL = 50
CATEGORY_FLOOR_EVAL = 15


class CorpusValidationError(ValueError):
    """Base class for named corpus errors (schema / leakage)."""


class CorpusSchemaError(CorpusValidationError):
    """A record or file violates the record schema."""


class CorpusLeakageError(CorpusValidationError):
    """Split leakage: a template id or session hash straddles splits."""


def dataset_root() -> _Path:
    """Resolve the labeled-dataset root.

    TAX_DATASET_DIR env override when set; otherwise ALWAYS the committed
    repo-level ``data/`` directory (backend/corpus.py's parent's parent /
    data). The cwd is deliberately never consulted: pytest and uvicorn run
    from ``backend/`` where ``./data`` is the gitignored SQLite store dir
    (backend/data/) — silently loading that would read the wrong files.
    """
    import os

    override = os.environ.get("TAX_DATASET_DIR", "").strip()
    if override:
        return _Path(override)
    return _Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# Record schema validation — malformed records raise NAMED errors that
# carry the record id (or line position) and the failing field.
# ---------------------------------------------------------------------------

_REQUIRED_TOP_LEVEL = ("id", "text", "source", "lang", "spans", "provenance")


def _fail(context: str, reason: str) -> None:
    raise CorpusSchemaError(f"{context}: {reason}")


def _validate_span(span: object, context: str) -> None:
    if not isinstance(span, dict):
        _fail(context, f"span is not an object: {span!r}")
    assert isinstance(span, dict)
    span_text = span.get("text")
    if not isinstance(span_text, str) or not span_text.strip():
        _fail(context, "span.text must be a non-empty string")
    category = span.get("category")
    if category not in TAXONOMY:
        _fail(
            context,
            f"span.category {category!r} not in the 21-label taxonomy",
        )
    amount = span.get("amount")
    if amount is not None:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            _fail(context, f"span.amount must be a number or null, got {amount!r}")
        if not float(amount) >= 0:
            _fail(context, f"span.amount must be >= 0, got {amount!r}")
    if not isinstance(span.get("annualized"), bool):
        _fail(context, "span.annualized must be a boolean")


def _validate_spans(spans: object, context: str) -> None:
    if not isinstance(spans, list):
        _fail(context, "spans must be a list")
    for span in spans:
        _validate_span(span, context)


def validate_record(record: object, context: str = "record") -> None:
    """Validate one labeled record against the P0 schema; raises
    CorpusSchemaError naming the record id and failing field."""
    if not isinstance(record, dict):
        _fail(context, f"record is not a JSON object: {type(record).__name__}")
    assert isinstance(record, dict)
    rid = record.get("id")
    ctx = f"{context}[{rid!r}]" if rid else context

    if not isinstance(rid, str) or not rid.strip():
        _fail(ctx, "id must be a non-empty string")
    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        _fail(ctx, "text must be a non-empty string")
    if record.get("source") not in SOURCES:
        _fail(ctx, f"source must be one of {SOURCES}, got {record.get('source')!r}")
    if record.get("lang") not in LANGS:
        _fail(ctx, f"lang must be one of {LANGS}, got {record.get('lang')!r}")

    has_template = isinstance(record.get("template_id"), str) and bool(
        record["template_id"].strip()
    )
    has_session = isinstance(record.get("session_hash"), str) and bool(
        record["session_hash"].strip()
    )
    if record["source"] == "organic":
        if not has_session:
            _fail(ctx, "organic records require a non-empty session_hash")
    elif not has_template:
        _fail(
            ctx,
            f"source={record['source']!r} records require a non-empty template_id",
        )

    if not isinstance(record.get("provenance"), dict):
        _fail(ctx, "provenance must be an object (builder, built_on, ...)")

    spans = record.get("spans")
    _validate_spans(spans, ctx)

    if "turns" in record:
        turns = record["turns"]
        if not isinstance(turns, list) or not turns:
            _fail(ctx, "turns must be a non-empty list when present")
        flattened = []
        for i, turn in enumerate(turns):
            tctx = f"{ctx} turn {i}"
            if not isinstance(turn, dict):
                _fail(tctx, "turn is not an object")
            if not isinstance(turn.get("text"), str) or not turn["text"].strip():
                _fail(tctx, "turn.text must be a non-empty string")
            _validate_spans(turn.get("spans"), tctx)
            flattened.extend(turn.get("spans") or [])
        key = lambda s: (  # noqa: E731 — local sort key only
            s.get("text", ""), s.get("category"), s.get("amount")
        )
        if sorted(flattened, key=key) != sorted(spans or [], key=key):
            _fail(
                ctx,
                "top-level spans must be the flattened union of turn spans",
            )


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _split_dir(root: _Path, split: str) -> _Path:
    if split not in SPLIT_NAMES:
        raise CorpusSchemaError(
            f"unknown split {split!r} — expected one of {SPLIT_NAMES}"
        )
    return root / split


def load_split(split: str, root: _Path | None = None) -> _List[dict]:
    """Load + validate every *.jsonl record of one split (sorted by file
    name, then line order). A missing split directory is an empty split."""
    root = root if root is not None else dataset_root()
    directory = _split_dir(root, split)
    records: _List[dict] = []
    if not directory.is_dir():
        return records
    for path in sorted(directory.glob("*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                location = f"{path.name} line {line_no}"
                try:
                    parsed = _json.loads(line)
                except _json.JSONDecodeError as exc:
                    raise CorpusSchemaError(
                        f"{location}: invalid JSON ({exc.msg})"
                    ) from exc
                validate_record(parsed, context=location)
                records.append(parsed)
    return records


def load_manifest(root: _Path | None = None) -> dict:
    root = root if root is not None else dataset_root()
    path = root / "manifest.json"
    if not path.exists():
        raise CorpusSchemaError(f"manifest.json not found under {root}")
    try:
        manifest = _json.loads(path.read_text(encoding="utf-8"))
    except _json.JSONDecodeError as exc:
        raise CorpusSchemaError(f"manifest.json: invalid JSON ({exc.msg})") from exc
    if not isinstance(manifest, dict):
        raise CorpusSchemaError("manifest.json: not a JSON object")
    return manifest


def load_all(root: _Path | None = None,
             enforce_manifest: bool = True) -> _Dict[str, _List[dict]]:
    """Load all four splits; validate; enforce cross-split id uniqueness
    and (when a manifest is present) template/session disjointness."""
    root = root if root is not None else dataset_root()
    loaded = {split: load_split(split, root) for split in SPLIT_NAMES}
    seen: dict = {}
    for split, records in loaded.items():
        for record in records:
            rid = record["id"]
            if rid in seen:
                raise CorpusSchemaError(
                    f"duplicate record id {rid!r} in {seen[rid]} and {split}"
                )
            seen[rid] = split
    manifest_path = root / "manifest.json"
    if enforce_manifest and manifest_path.exists():
        assert_splits_disjoint(load_manifest(root))
    return loaded


# ---------------------------------------------------------------------------
# Manifest assertions — template-disjoint + session-disjoint splits
# ---------------------------------------------------------------------------


def assert_splits_disjoint(manifest: dict) -> None:
    """Raise CorpusLeakageError when a template id or a session hash
    appears in more than one build split (training/validation/test)."""
    for index_name in ("template_index", "session_index"):
        index = manifest.get(index_name)
        if not isinstance(index, dict):
            raise CorpusSchemaError(f"manifest.{index_name} missing or invalid")
        owner: dict = {}
        for split, items in index.items():
            if not isinstance(items, list):
                raise CorpusSchemaError(
                    f"manifest.{index_name}.{split} must be a list"
                )
            for item in items:
                if item in owner and owner[item] != split:
                    raise CorpusLeakageError(
                        f"leakage: {index_name} entry {item!r} appears in "
                        f"both {owner[item]} and {split}"
                    )
                owner[item] = split


# ---------------------------------------------------------------------------
# Coverage counts + near-duplicate detection + quality metrics
# ---------------------------------------------------------------------------


def normalized_text(text: str) -> str:
    """Near-duplicate normalization: lowercase, collapse whitespace, drop
    punctuation — including the digit-grouping comma, so "50,000" and
    "50000" collapse together (same utterance) while "50000" and "60000"
    stay distinct (different amounts = different utterances)."""
    lowered = text.lower()
    cleaned = _re.sub(r"[^0-9a-z\s]", "", lowered)
    return _re.sub(r"\s+", " ", cleaned).strip()


def _hash_text(text: str) -> str:
    return hashlib.sha256(normalized_text(text).encode("utf-8")).hexdigest()[:16]


def find_cross_split_duplicates(
    records_by_split: _Dict[str, _List[dict]],
) -> _List[dict]:
    """Exact-after-normalization duplicates ACROSS splits (near-duplicate
    leakage candidates). Same-split duplicates are style, not leakage."""
    seen: _Dict[str, _Tuple[str, str]] = {}
    duplicates: _List[dict] = []
    for split in SPLIT_NAMES:
        for record in records_by_split.get(split, []):
            digest = _hash_text(record["text"])
            first = seen.get(digest)
            if first is not None and first[0] != split:
                duplicates.append({
                    "id_a": first[1],
                    "split_a": first[0],
                    "id_b": record["id"],
                    "split_b": split,
                    "normalized": normalized_text(record["text"]),
                })
            elif first is None:
                seen[digest] = (split, record["id"])
    return duplicates


def coverage_counts(records: _Iterable[dict]) -> _Counter:
    """Per-category span counts (ABSTAIN included) over one split."""
    counts: _Counter = _Counter()
    for record in records:
        for span in record.get("spans") or []:
            counts[span["category"]] += 1
    return counts


def corpus_quality(records_by_split: _Dict[str, _List[dict]]) -> dict:
    """P0 item 4 — corpus quality metrics: per-category counts, source
    distribution, language distribution, template diversity, split sizes."""
    build_splits = ("training", "validation", "test")
    all_records = [r for split in SPLIT_NAMES
                   for r in records_by_split.get(split, [])]
    source_counts: _Counter = _Counter(r["source"] for r in all_records)
    lang_counts: _Counter = _Counter(r["lang"] for r in all_records)
    templates = {
        r["template_id"] for r in all_records if "template_id" in r
    }
    per_category = {
        split: dict(coverage_counts(records_by_split.get(split, [])))
        for split in SPLIT_NAMES
    }
    renders_per_template: _Counter = _Counter(
        r["template_id"] for r in all_records if "template_id" in r
    )
    return {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "total_records": len(all_records),
        "total_spans": sum(len(r.get("spans") or []) for r in all_records),
        "splits": {s: len(records_by_split.get(s, []))
                   for s in SPLIT_NAMES},
        "source_distribution": {s: source_counts.get(s, 0)
                                for s in SOURCES},
        "lang_distribution": {lang: lang_counts.get(lang, 0)
                              for lang in LANGS},
        "template_diversity": {
            "unique_templates": len(templates),
            "max_renders_per_template": max(renders_per_template.values(),
                                            default=0),
            "mean_renders_per_template": (
                sum(renders_per_template.values()) / len(renders_per_template)
                if renders_per_template else 0.0
            ),
        },
        "per_category_counts": per_category,
        "build_splits": build_splits,
    }
