# Summer internship project
"""Convert captured corpus conversations into golden regression fixtures.

The quality loop (Sprint4_AI_Modernization.md §1): run the app →
TAX_CORPUS_CAPTURE=1 records every conversation full-fidelity into
logs/corpus/corpus.jsonl → THIS tool converts verified conversations
into fixtures that backend/tests replay against the engine — so every
real interaction becomes a permanent regression test ("until we become
perfect").

Usage:
    python tests/tools/corpus_to_golden.py ^
        --corpus logs/corpus/corpus.jsonl ^
        --out tests/fixtures/corpus_golden.json ^
        [--session <session_id>]        # one session only
        [--min-turns 2]                 # skip shallow conversations
        [--validate]                    # also re-run each turn against
                                        # the LIVE engine and report drift

Output (JSON):
    {
      "generated_at": ...,
      "source": <corpus path>,
      "sessions": [
        {
          "session_id": ...,
          "turns": [{"user_input", "extracted", "state"}...],
          "final_state": {...},
          "final_tax": {...}            # as computed at capture time
        }...
      ]
    }

Wire the fixture into tests by replaying `turns[].user_input` through
POST /chat (authed_client + POST /sessions) and asserting the captured
`state`/`final_tax` — the same red→green protocol as
tests/test_golden_corpus.py.
"""
import argparse
import json
import sys
from pathlib import Path


def load_records(corpus_path: Path):
    records, corrupt = [], 0
    with open(corpus_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                corrupt += 1  # skip; never fatal (append-only discipline)
                continue
            if isinstance(record, dict):
                records.append(record)
    return records, corrupt


def group_sessions(records, only_session=None, min_turns=1):
    sessions = {}
    for record in records:
        if record.get("event") != "chat_turn":
            continue
        session_id = record.get("session_id")
        if not session_id or (only_session and session_id != only_session):
            continue
        entry = sessions.setdefault(session_id, {"turns": []})
        entry["turns"].append({
            "user_input": record.get("user_input"),
            "extracted": record.get("extracted"),
            "state": record.get("state"),
        })
        if record.get("tax_report"):
            entry["final_tax"] = record["tax_report"]
    return {
        sid: data for sid, data in sessions.items() if len(data["turns"]) >= min_turns
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="logs/corpus/corpus.jsonl")
    parser.add_argument("--out", default="tests/fixtures/corpus_golden.json")
    parser.add_argument("--session", default=None)
    parser.add_argument("--min-turns", type=int, default=1)
    parser.add_argument("--validate", action="store_true",
                        help="Re-run each captured turn against the LIVE "
                             "engine and report drift (needs backend deps)")
    args = parser.parse_args()

    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        print(f"ERROR: corpus not found: {corpus_path}")
        return 1

    records, corrupt = load_records(corpus_path)
    sessions = group_sessions(records, args.session, args.min_turns)

    drift = []
    if args.validate:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from tax_engine import TaxEngine  # noqa: E402

        engine = TaxEngine()
        for session_id, data in sessions.items():
            final_state = data["turns"][-1]["state"]
            if not any(
                isinstance(final_state.get(k), (int, float))
                and final_state.get(k, 0) > 0
                for k in ("salary", "business", "rental", "other_income")
            ):
                continue  # no income -> engine reports zeros; skip
            year = final_state.get("tax_year")
            live = engine.calculate_tax_advanced(final_state, year)
            for regime in ("old_regime", "new_regime"):
                captured = (data.get("final_tax") or {}).get(regime, {})
                live_tax = live[regime].total_tax
                captured_tax = captured.get("total_tax")
                if captured_tax is not None and abs(live_tax - captured_tax) > 0.01:
                    drift.append({
                        "session_id": session_id, "regime": regime,
                        "captured": captured_tax, "live": live_tax,
                    })

    fixture = {
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "source": str(corpus_path),
        "corrupt_lines_skipped": corrupt,
        "sessions": [
            {"session_id": sid, **data} for sid, data in sorted(sessions.items())
        ],
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(fixture, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"sessions: {len(sessions)} | turns: "
          f"{sum(len(d['turns']) for d in sessions.values())} | "
          f"corrupt lines skipped: {corrupt} | drift mismatches: {len(drift)}")
    for item in drift:
        print("  DRIFT:", json.dumps(item))
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
