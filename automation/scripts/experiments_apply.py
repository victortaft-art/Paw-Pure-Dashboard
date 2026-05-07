"""experiments_apply — single CLI for adding/updating experiments.

Replaces the date-stamped one-off scripts (now archived under scripts/archive/).

Per docs/ARCHITECTURE.md §3 (process): when more than one ad-hoc
update_experiments_<date>.py exists, fold them into this CLI.

Subcommands:
  add        Add a new experiment from a JSON spec file.
             Touches BOTH active_tracker.json and experiment_log.json.

  done       Mark an experiment as DONE with an actual_result note.
             Touches BOTH files in lockstep.

  supersede  Mark an experiment SUPERSEDED with a `superseded_by` list and a note.

  priority   Update an experiment's priority + log the change in priority_history.

Usage:
    python3 scripts/experiments_apply.py done EXP-051 --note "filter campaign launched..."
    python3 scripts/experiments_apply.py priority EXP-059 --to CRITICAL --reason "..."
    python3 scripts/experiments_apply.py supersede EXP-029 --by EXP-057 --reason "..."
    python3 scripts/experiments_apply.py add path/to/exp_spec.json

JSON spec for `add`:
    {
      "id": "EXP-XXX",
      "title": "...",
      "scheduled_date": "YYYY-MM-DD",
      "decision_date": "YYYY-MM-DD",
      "priority": "CRITICAL|HIGH|MEDIUM|LOW",
      "growth_metric": "...",
      "listing": "fountain|filters|bundle|ppc|ops|brand",
      "assumption": "...",
      "rationale": "...",
      "expected_change": "...",
      "execution_steps": ["...", "..."],
      "success_criteria": { "metric": "...", "baseline": ..., "target": ..., "unit": "%", "direction": "up|down", "how_to_measure": "..." }
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKER_PATHS = [
    ROOT.parent / "public" / "data" / "active_tracker.json",
    ROOT / "active_tracker.json",
]
LOG_PATHS = [
    ROOT / "experiment_log.json",
    ROOT.parent / "public" / "data" / "experiment_log.json",
]


def _load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"  warn: failed to parse {path}: {e}", file=sys.stderr)
        return None


def _save(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2))


# ---------------------------------------------------------------------------
# Subcommand: done
# ---------------------------------------------------------------------------

def cmd_done(args) -> int:
    today = date.today().isoformat()
    note = args.note or f"DONE {today}."
    found_anywhere = False

    for path in LOG_PATHS:
        d = _load(path)
        if d is None:
            continue
        for e in d.get("active_experiments", []):
            if e.get("id") == args.id:
                e["status"] = "DONE"
                e["completed_date"] = today
                e["actual_result"] = note
                found_anywhere = True
        d["_last_updated"] = today
        _save(path, d)

    for path in TRACKER_PATHS:
        d = _load(path)
        if d is None:
            continue
        for b in d.get("backlog", []):
            if b.get("id") == args.id:
                b["status"] = "DONE"
                b["completed_date"] = today
                found_anywhere = True
        for wk in d.get("weekly_strategy", []) or []:
            for e in wk.get("experiments", []) or []:
                if e.get("id") == args.id:
                    e["status"] = "DONE"
                    e["completed_date"] = today
                    found_anywhere = True
        for t in d.get("tracking", []) or []:
            if t.get("id") == args.id:
                t["status"] = "DONE"
                t["completed_date"] = today
                if args.note:
                    t["outcome_note"] = args.note
                found_anywhere = True
        d["today"] = today
        _save(path, d)

    if not found_anywhere:
        print(f"ERROR: {args.id} not found in any tracker or log file.", file=sys.stderr)
        return 1
    print(f"✓ {args.id} marked DONE on {today}.")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: priority
# ---------------------------------------------------------------------------

def cmd_priority(args) -> int:
    today = date.today().isoformat()
    found = False

    for path in LOG_PATHS:
        d = _load(path)
        if d is None:
            continue
        for e in d.get("active_experiments", []):
            if e.get("id") == args.id:
                old = e.get("priority")
                e["priority"] = args.to
                e.setdefault("priority_history", []).append({
                    "date": today,
                    "from": old,
                    "to": args.to,
                    "reason": args.reason or "",
                })
                found = True
        _save(path, d)

    for path in TRACKER_PATHS:
        d = _load(path)
        if d is None:
            continue
        for b in d.get("backlog", []):
            if b.get("id") == args.id:
                b["priority"] = args.to
                found = True
        _save(path, d)

    if not found:
        print(f"ERROR: {args.id} not found.", file=sys.stderr)
        return 1
    print(f"✓ {args.id} priority → {args.to}.")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: supersede
# ---------------------------------------------------------------------------

def cmd_supersede(args) -> int:
    today = date.today().isoformat()
    superseded_by = args.by or []
    found = False

    for path in LOG_PATHS:
        d = _load(path)
        if d is None:
            continue
        for e in d.get("active_experiments", []):
            if e.get("id") == args.id:
                e["status"] = "SUPERSEDED"
                e["superseded_by"] = superseded_by
                e["supersede_note"] = args.reason
                e["completed_date"] = today
                found = True
        _save(path, d)

    # Remove from backlog (keep visible only via advisor's to_deprecate)
    for path in TRACKER_PATHS:
        d = _load(path)
        if d is None:
            continue
        d["backlog"] = [b for b in d.get("backlog", []) if b.get("id") != args.id]
        _save(path, d)

    if not found:
        print(f"ERROR: {args.id} not found.", file=sys.stderr)
        return 1
    print(f"✓ {args.id} superseded by {superseded_by or '<none>'}.")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: add
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["id", "title", "scheduled_date", "priority", "listing", "assumption", "rationale", "expected_change", "execution_steps"]


def cmd_add(args) -> int:
    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        return 1
    spec = json.loads(spec_path.read_text())
    missing = [f for f in REQUIRED_FIELDS if not spec.get(f)]
    if missing:
        print(f"ERROR: spec missing required fields: {missing}", file=sys.stderr)
        return 1

    log_entry = {
        "id": spec["id"],
        "element": spec["title"],
        "status": spec.get("status", "TODO"),
        "start_date": spec["scheduled_date"],
        "decision_date": spec.get("decision_date"),
        "hypothesis": spec["assumption"],
        "priority": spec["priority"],
        "rationale": spec["rationale"],
        "expected_impact": spec["expected_change"],
        "wave": spec.get("wave", 1),
        "run_window_days": spec.get("run_window_days", 7),
        "success_criteria": spec.get("success_criteria"),
        "execution": {
            "what_to_do": spec["execution_steps"][0],
            "steps": spec["execution_steps"],
            **{k: spec[k] for k in ("new_title", "copy_paste_bullets", "new_description", "new_a_plus", "new_search_terms", "image_changes", "seller_central_url", "seller_central_path") if k in spec},
        },
        "listing": spec["listing"],
        "actual_result": None,
    }

    backlog_entry = spec.copy()  # full spec is the backlog shape

    for path in LOG_PATHS:
        d = _load(path)
        if d is None:
            continue
        if any(e.get("id") == spec["id"] for e in d.get("active_experiments", [])):
            print(f"  skip {path.name} — {spec['id']} already exists", file=sys.stderr)
            continue
        d["active_experiments"].append(log_entry)
        d["_last_updated"] = date.today().isoformat()
        _save(path, d)

    for path in TRACKER_PATHS:
        d = _load(path)
        if d is None:
            continue
        if any(b.get("id") == spec["id"] for b in d.get("backlog", [])):
            continue
        d.setdefault("backlog", []).append(backlog_entry)
        _save(path, d)

    print(f"✓ Added {spec['id']}: {spec['title']}.")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Apply experiment status changes from CLI.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_done = sub.add_parser("done", help="Mark an experiment DONE.")
    p_done.add_argument("id", help="Experiment ID, e.g. EXP-051")
    p_done.add_argument("--note", help="actual_result note", default=None)
    p_done.set_defaults(func=cmd_done)

    p_pri = sub.add_parser("priority", help="Update an experiment's priority.")
    p_pri.add_argument("id")
    p_pri.add_argument("--to", required=True, choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"])
    p_pri.add_argument("--reason", default="")
    p_pri.set_defaults(func=cmd_priority)

    p_sup = sub.add_parser("supersede", help="Mark an experiment SUPERSEDED.")
    p_sup.add_argument("id")
    p_sup.add_argument("--by", nargs="*", default=[], help="Successor EXP IDs")
    p_sup.add_argument("--reason", required=True)
    p_sup.set_defaults(func=cmd_supersede)

    p_add = sub.add_parser("add", help="Add a new experiment from a JSON spec.")
    p_add.add_argument("spec", help="Path to JSON spec file")
    p_add.set_defaults(func=cmd_add)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
