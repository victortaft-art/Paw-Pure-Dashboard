"""Competitor weekly snapshot — scrape each tracked ASIN and diff vs prior.

Workflow:
  1. Read competitor list from dashboard/public/data/competitor_intel.json.
  2. For each ASIN, scrape Amazon listing page (Claude-in-Chrome OR fallback
     to manual-input mode where snapshots are loaded from a JSON the user
     prepares).
  3. Capture: title, price, stars, reviews, BSR (subcategory rank), main
     image filename.
  4. Write `kw_data/competitor_snapshots/snapshot_<YYYY-MM-DD>.json`.
  5. If a prior snapshot exists, write `changes_<YYYY-MM-DD>.json` listing
     every (competitor, field, old, new) diff.
  6. Update competitor_intel.json with the latest scraped values for the
     fields we now have fresher data for.
  7. Update dashboard/public/data/manifest.json (so the loader picks up the
     new files via loadLatestFromFolder('competitor_snapshots', 'changes')).

This script is designed to be invocable two ways:
    A) `python -m helium10_pipeline.competitor_snapshot --scrape` — uses Chrome
       (must be launched separately; this script only writes the request file
       and consumes a JSON-in-stdin response when --scrape is passed alone, the
       script falls back to manual-input mode).
    B) `python -m helium10_pipeline.competitor_snapshot --input <file.json>` —
       loads pre-collected snapshot data from a JSON file (pasted from a
       Claude-in-Chrome session).

For now, mode B is the practical path: Claude-in-Chrome scrapes and writes a
JSON, then this script ingests + diffs.

JSON input shape (mode B):
    {
      "snapshot_date": "2026-04-29",
      "asins": {
        "B0CK1MXC7J": {"title": "...", "price": 49.99, "stars": 4.4,
                       "reviews": 1234, "bsr_subcategory": {"rank": 12, "category": "Cat Fountains"},
                       "hero_image": "https://..."},
        ...
      }
    }
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

# Make project root importable so `common.manifest_utils` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
INTEL_FILE = ROOT.parent / "public" / "data" / "competitor_intel.json"
SNAPSHOT_DIR = ROOT / "kw_data" / "competitor_snapshots"
DASHBOARD_SNAPSHOT_DIR = ROOT.parent / "public" / "data" / "competitor_snapshots"
MANIFEST = ROOT.parent / "public" / "data" / "manifest.json"


# Fields to track for diffs. Each entry: (field_path, label, direction_for_threat)
TRACKED_FIELDS = [
    ("price", "price", "down"),  # competitor lowering price = threat increases
    ("stars", "stars", "up"),    # competitor raising stars = threat increases
    ("reviews", "reviews", "up"),
    ("title", "title", None),
    ("hero_image", "hero_image", None),
    ("bsr_subcategory.rank", "bsr_rank", "down"),  # lower BSR = better for them
]


def _get_path(d: dict, path: str) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _set_path(d: dict, path: str, value: Any) -> None:
    cur = d
    parts = path.split(".")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def load_intel() -> dict:
    return json.loads(INTEL_FILE.read_text())


def latest_snapshot_path() -> Path | None:
    if not SNAPSHOT_DIR.exists():
        return None
    files = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
    return files[-1] if files else None


def write_snapshot(payload: dict, out_path: Path, dash_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dash_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    dash_path.write_text(json.dumps(payload, indent=2))


def diff_snapshots(prior: dict, current: dict, intel: dict) -> dict:
    """Compute per-field changes between two snapshot payloads."""
    p_asins = prior.get("asins", {})
    c_asins = current.get("asins", {})
    asin_to_brand = {c["asin"]: c.get("brand", c["asin"]) for c in intel.get("competitors", [])}
    out_changes = []
    for asin, c_data in c_asins.items():
        p_data = p_asins.get(asin) or {}
        for path, label, direction in TRACKED_FIELDS:
            old = _get_path(p_data, path)
            new = _get_path(c_data, path)
            if old is None or new is None:
                continue
            if old == new:
                continue
            note = None
            if direction == "down" and isinstance(old, (int, float)) and isinstance(new, (int, float)):
                note = "threat ↑" if new < old else "threat ↓"
            elif direction == "up" and isinstance(old, (int, float)) and isinstance(new, (int, float)):
                note = "threat ↑" if new > old else "threat ↓"
            out_changes.append({
                "asin": asin,
                "brand": asin_to_brand.get(asin, asin),
                "field": label,
                "old": old,
                "new": new,
                "direction": "down" if (isinstance(old, (int, float)) and isinstance(new, (int, float)) and new < old) else "up",
                "note": note,
            })
    return {
        "snapshot_date": current.get("snapshot_date"),
        "prior_snapshot_date": prior.get("snapshot_date"),
        "changes": out_changes,
    }


def update_intel_with_snapshot(intel: dict, snapshot: dict) -> dict:
    """Merge fresh scraped values into intel — but never overwrite existing
    populated fields with None or empty strings."""
    asins = snapshot.get("asins", {})
    for c in intel.get("competitors", []):
        scraped = asins.get(c.get("asin"))
        if not scraped:
            continue
        for path, _label, _ in TRACKED_FIELDS:
            v = _get_path(scraped, path)
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == "":
                continue
            if isinstance(v, dict) and not any(vv not in (None, "") for vv in v.values()):
                continue
            _set_path(c, path, v)
    intel["_last_updated"] = snapshot.get("snapshot_date") or date.today().isoformat()
    return intel


def update_manifest(filenames: list[str]) -> None:
    from common.manifest_utils import update_manifest_bucket
    update_manifest_bucket(MANIFEST, "competitor_snapshots", filenames)


def cmd_template(args) -> int:
    """Print a JSON template the user can fill from a Chrome session."""
    intel = load_intel()
    template = {
        "snapshot_date": date.today().isoformat(),
        "asins": {
            c["asin"]: {
                "title": "",
                "price": None,
                "stars": None,
                "reviews": None,
                "bsr_subcategory": {"rank": None, "category": ""},
                "hero_image": "",
            }
            for c in intel.get("competitors", [])
        },
    }
    out = json.dumps(template, indent=2)
    print(out)
    return 0


def cmd_ingest(args) -> int:
    """Ingest a snapshot JSON file → write snapshot + diff + update intel."""
    src = Path(args.input)
    if not src.exists():
        print(f"ERROR: input file not found: {src}", file=sys.stderr)
        return 1
    payload = json.loads(src.read_text())
    snapshot_date = payload.get("snapshot_date") or date.today().isoformat()
    payload["snapshot_date"] = snapshot_date

    snap_name = f"snapshot_{snapshot_date}.json"
    repo_path = SNAPSHOT_DIR / snap_name
    dash_path = DASHBOARD_SNAPSHOT_DIR / snap_name
    write_snapshot(payload, repo_path, dash_path)
    written = [snap_name]

    # Diff against most recent prior snapshot
    prior_path = None
    if SNAPSHOT_DIR.exists():
        prior_files = sorted([p for p in SNAPSHOT_DIR.glob("snapshot_*.json") if p.name != snap_name])
        if prior_files:
            prior_path = prior_files[-1]

    intel = load_intel()
    if prior_path:
        prior = json.loads(prior_path.read_text())
        diff = diff_snapshots(prior, payload, intel)
        diff_name = f"changes_{snapshot_date}.json"
        diff_repo = SNAPSHOT_DIR / diff_name
        diff_dash = DASHBOARD_SNAPSHOT_DIR / diff_name
        diff_repo.write_text(json.dumps(diff, indent=2))
        diff_dash.write_text(json.dumps(diff, indent=2))
        written.append(diff_name)
        print(f"  wrote {diff_name}: {len(diff['changes'])} changes vs {prior_path.name}")
    else:
        print("  (no prior snapshot — baseline captured, no diff written)")

    # Update intel with fresh values
    new_intel = update_intel_with_snapshot(intel, payload)
    INTEL_FILE.write_text(json.dumps(new_intel, indent=2))
    print(f"  updated competitor_intel.json with latest values")

    update_manifest(written)
    print(f"\nDone. Snapshot {snapshot_date} ingested.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Competitor weekly snapshot pipeline.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("template", help="Emit JSON template to stdout.")
    t.set_defaults(func=cmd_template)

    i = sub.add_parser("ingest", help="Ingest a snapshot JSON file.")
    i.add_argument("input", help="Path to snapshot JSON")
    i.set_defaults(func=cmd_ingest)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
