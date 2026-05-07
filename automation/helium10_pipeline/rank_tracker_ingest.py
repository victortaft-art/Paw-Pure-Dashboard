"""Helium 10 Keyword Tracker CSV → rank history JSON.

Workflow:
  1. In H10 → Keyword Tracker → select Paw Pure ASIN B0DJHQVJYF.
  2. Export the tracked-keyword history as CSV. Drop into kw_data/rank_tracker/.
  3. Run:  python -m helium10_pipeline.rank_tracker_ingest <csv_path>

Output:
  - kw_data/rank_history_<date>.json    — daily organic + sponsored rank
                                           per keyword, last 30 days
  - dashboard/public/data/kw_data/rank_history_<date>.json (mirrored)

Schema:
  {
    "_schema_version": "1.0",
    "runDate": "YYYY-MM-DD",
    "asin": "B0DJHQVJYF",
    "keywords": [
      { "keyword": "...",
        "search_volume": 6400,
        "current_organic": 28,
        "current_sponsored": 12,
        "organic_delta_7d": -4,        # negative = improved
        "sponsored_delta_7d": null,
        "history": [ { "date": "YYYY-MM-DD", "organic": 28, "sponsored": null }, ... ] }
    ]
  }

The Keyword Tracker CSV format varies, so this is tolerant of column drift.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Make project root importable so `common.manifest_utils` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
KW_DATA_DIR = ROOT / "kw_data"
DASHBOARD_DATA_DIR = ROOT.parent / "public" / "data"
DASHBOARD_KW_DIR = DASHBOARD_DATA_DIR / "kw_data"
MANIFEST_FILE = DASHBOARD_DATA_DIR / "manifest.json"

OUR_ASIN = "B0DJHQVJYF"
HISTORY_DAYS = 180  # H10 backfills up to ~6 months when KWs are added


def _norm(h: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", h.lower())


def _to_int(v: Any) -> int | None:
    if v is None or v == "" or v == "-" or str(v).lower() in {"none", "null", "nr"}:
        return None
    s = str(v).replace(",", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def _parse_date(v: str) -> date | None:
    if not v:
        return None
    s = v.strip()
    # H10 emits "2025-10-29 03:00:00" — strip the time component if present
    if " " in s and len(s) > 10:
        s = s.split(" ", 1)[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_rank(v: Any) -> int | None:
    """Parse an H10 rank cell. Handles '>306' (means worse than 306), '-', and ints."""
    if v is None or v == "" or v == "-" or str(v).lower() in {"none", "null", "nr", "na"}:
        return None
    s = str(v).strip()
    if s.startswith(">"):
        # ">306" means worse than 306 — represent as None (not currently ranking)
        # since we treat numeric ranks as "actual position" elsewhere.
        return None
    try:
        return int(float(s.replace(",", "")))
    except ValueError:
        return None


def parse_keyword_tracker(csv_path: Path) -> dict[str, dict[str, Any]]:
    """Returns: { keyword: {search_volume, history: [{date, organic, sponsored}, ...] } }

    Handles two H10 export shapes:
      A) Long format: rows of (keyword, date, organic_rank, sponsored_rank, sv)
      B) Wide format: keyword + many date columns for organic rank
    """
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    norm_headers = {h: _norm(h) for h in headers}
    # H10 long-format export uses "Date Added" as the per-row date column
    has_date_col = any(n in {"date", "dateadded", "snapshotdate"} for n in norm_headers.values())

    out: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"search_volume": None, "history": []}
    )

    if has_date_col:
        # Long format
        kw_col = next((h for h, n in norm_headers.items() if n in {"keyword", "keywordphrase", "phrase"}), None)
        date_col = next((h for h, n in norm_headers.items() if n in {"date", "dateadded", "snapshotdate"}), None)
        org_col = next((h for h, n in norm_headers.items() if n in {"organicrank", "organic"}), None)
        sp_col = next((h for h, n in norm_headers.items() if n in {"sponsoredrank", "sponsored", "sponsoredposition"}), None)
        sv_col = next((h for h, n in norm_headers.items() if n in {"searchvolume", "sv"}), None)
        if not (kw_col and date_col):
            raise ValueError(f"Long-format export missing keyword/date column. Headers: {headers}")

        for row in rows:
            kw = (row.get(kw_col) or "").strip()
            d = _parse_date(row.get(date_col, ""))
            if not kw or not d:
                continue
            entry = out[kw]
            if sv_col:
                # Track latest SV (rows are typically chronological)
                sv = _to_int(row.get(sv_col))
                if sv is not None:
                    entry["search_volume"] = sv
            entry["history"].append(
                {
                    "date": d.isoformat(),
                    "organic": _parse_rank(row.get(org_col)) if org_col else None,
                    "sponsored": _parse_rank(row.get(sp_col)) if sp_col else None,
                }
            )
    else:
        # Wide format: detect date columns
        kw_col = next((h for h, n in norm_headers.items() if n in {"keyword", "keywordphrase", "phrase"}), None)
        sv_col = next((h for h, n in norm_headers.items() if n in {"searchvolume", "sv"}), None)
        if not kw_col:
            raise ValueError(f"Wide-format export missing keyword column. Headers: {headers}")

        date_cols: list[tuple[str, date]] = []
        for h in headers:
            d = _parse_date(h)
            if d:
                date_cols.append((h, d))
        if not date_cols:
            raise ValueError(f"No date columns detected in wide export. Headers: {headers}")

        for row in rows:
            kw = (row.get(kw_col) or "").strip()
            if not kw:
                continue
            entry = out[kw]
            if sv_col:
                entry["search_volume"] = _to_int(row.get(sv_col))
            for col, d in date_cols:
                entry["history"].append(
                    {"date": d.isoformat(), "organic": _to_int(row.get(col)), "sponsored": None}
                )

    # Sort histories chronologically and clip to HISTORY_DAYS
    today = date.today()
    cutoff = today - timedelta(days=HISTORY_DAYS)
    for kw, entry in out.items():
        entry["history"] = sorted(
            (h for h in entry["history"] if _parse_date(h["date"]) and _parse_date(h["date"]) >= cutoff),
            key=lambda h: h["date"],
        )

    return dict(out)


def build_payload(kw_history: dict[str, dict[str, Any]]) -> dict[str, Any]:
    keywords_out = []
    for kw, entry in kw_history.items():
        history = entry["history"]
        current_org = next((h["organic"] for h in reversed(history) if h["organic"] is not None), None)
        current_sp = next((h["sponsored"] for h in reversed(history) if h["sponsored"] is not None), None)

        # 7-day delta: compare current to first non-null on/after (today-7d)
        seven_ago = (date.today() - timedelta(days=7)).isoformat()
        prior = next((h for h in history if h["date"] <= seven_ago), None)
        if prior is None and history:
            prior = history[0]
        org_delta = None
        sp_delta = None
        if current_org is not None and prior and prior.get("organic") is not None:
            org_delta = current_org - prior["organic"]
        if current_sp is not None and prior and prior.get("sponsored") is not None:
            sp_delta = current_sp - prior["sponsored"]

        keywords_out.append(
            {
                "keyword": kw,
                "search_volume": entry["search_volume"],
                "current_organic": current_org,
                "current_sponsored": current_sp,
                "organic_delta_7d": org_delta,
                "sponsored_delta_7d": sp_delta,
                "history": history,
            }
        )

    keywords_out.sort(
        key=lambda k: k["search_volume"] if k.get("search_volume") is not None else -1,
        reverse=True,
    )

    return {
        "_schema_version": "1.0",
        "_source": "Helium 10 Keyword Tracker CSV",
        "runDate": date.today().isoformat(),
        "asin": OUR_ASIN,
        "history_days": HISTORY_DAYS,
        "keyword_count": len(keywords_out),
        "keywords": keywords_out,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    from common.manifest_utils import update_manifest_bucket
    run_date = payload["runDate"]
    fname = f"rank_history_{run_date}.json"
    out_repo = KW_DATA_DIR / fname
    out_dash = DASHBOARD_KW_DIR / fname
    out_repo.parent.mkdir(parents=True, exist_ok=True)
    out_dash.parent.mkdir(parents=True, exist_ok=True)
    with out_repo.open("w") as f:
        json.dump(payload, f, indent=2)
    shutil.copyfile(out_repo, out_dash)
    update_manifest_bucket(MANIFEST_FILE, "kw_data", [fname])
    return out_repo, out_dash


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest Helium 10 Keyword Tracker CSV.")
    ap.add_argument("csv", type=Path, help="Path to Keyword Tracker export")
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        return 1

    history = parse_keyword_tracker(args.csv)
    payload = build_payload(history)
    out_repo, out_dash = write_outputs(payload)

    print(f"Parsed {payload['keyword_count']} tracked keywords from {args.csv.name}")
    print("\nTop 10 by search volume:")
    for k in payload["keywords"][:10]:
        org = k.get("current_organic")
        delta = k.get("organic_delta_7d")
        delta_str = f"{delta:+d}" if delta is not None else "  -"
        print(
            f"  {k['keyword']:50s} SV={k.get('search_volume') or '-':>6}  "
            f"organic={org if org is not None else '-':>4}  Δ7d={delta_str}"
        )
    print(f"\nWrote: {out_repo}")
    print(f"Wrote: {out_dash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
