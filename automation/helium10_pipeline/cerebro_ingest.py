"""Cerebro multi-ASIN CSV → KW opportunity list.

Workflow:
  1. In Helium 10 → Cerebro → reverse ASIN on top-5 competitors
     (Veken, Pektaco, Pawira, Hapaw, FEELNEEDY).
  2. Export the multi-ASIN result as CSV. Drop into kw_data/cerebro/.
  3. Run:  python -m helium10_pipeline.cerebro_ingest <csv_path>

Output:
  - kw_data/cerebro_opportunities_<date>.json — flat list of auto-tagged
    keyword opportunities, scored and merged with current target list.
  - dashboard/public/data/kw_data/cerebro_opportunities_<date>.json — copy
    consumed by the H10 Opportunities panel in the Strategy tab.

Auto-tagging rules:
  core         SV >= 5000 AND we already rank in top 60
  opportunity  SV >= 1500 AND we are NOT in top 60 AND >=2 competitors rank
               in top 30
  competitor   Appears for >=3 competitors top 30 AND we are not indexed
  negative     Contains any token in NEGATIVE_TOKENS

The script is intentionally tolerant of column-name variation across H10
exports — it normalizes headers (lowercase, strip non-alphanumerics) and
matches by canonical keys.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

# Make project root importable so `common.manifest_utils` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
KW_DATA_DIR = ROOT / "kw_data"
CEREBRO_DIR = KW_DATA_DIR / "cerebro"
DASHBOARD_DATA_DIR = ROOT.parent / "public" / "data"
DASHBOARD_KW_DIR = DASHBOARD_DATA_DIR / "kw_data"
MANIFEST_FILE = DASHBOARD_DATA_DIR / "manifest.json"

OUR_ASIN = "B0DJHQVJYF"          # Paw Pure fountain
OUR_FILTER_ASIN = "B0FWXJ1GKT"   # Paw Pure filters

# Tokens that disqualify a keyword (wrong product attribute)
NEGATIVE_TOKENS = {
    "ceramic", "no filter", "no-filter", "pumpless",
    "fountain pump replacement", "battery aa", "diy",
}

# Min search volume floor — anything below is noise
MIN_SV = 500

# Rank thresholds
TOP_30 = 30
TOP_60 = 60


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _norm_header(h: str) -> str:
    """Normalize a CSV header: lowercase, strip everything but alphanum."""
    return re.sub(r"[^a-z0-9]+", "", h.lower())


def _to_int(v: Any) -> int | None:
    if v is None or v == "" or v == "-":
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).replace(",", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def _to_float(v: Any) -> float | None:
    if v is None or v == "" or v == "-":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _detect_asin_columns(headers: list[str]) -> dict[str, dict[str, str]]:
    """Find per-ASIN rank columns.

    Two H10 export formats are supported:

    A) Multi-ASIN format — columns named "<ASIN> Organic Rank" / "<ASIN> Sponsored Rank":
         "B0DJHQVJYF Organic Rank"  → norm "b0djhqvjyforganicrank"

    B) Primary + Competitors format — bare ASIN as a column header containing
       that competitor's organic rank (or "-"). The primary ASIN's ranks live
       in dedicated "Position (Rank)" / "Sponsored Rank (avg)" columns.
    """
    found: dict[str, dict[str, str]] = defaultdict(dict)

    # Format A
    norm = {h: _norm_header(h) for h in headers}
    pattern_a = re.compile(r"^(b0[a-z0-9]{8})(organic|sponsored)rank$")
    for orig, n in norm.items():
        m = pattern_a.match(n)
        if m:
            asin, kind = m.group(1).upper(), m.group(2)
            found[asin][kind] = orig

    # Format B — bare ASIN columns (only kick in if format A didn't catch it)
    pattern_b = re.compile(r"^B0[A-Z0-9]{8}$")
    for h in headers:
        if pattern_b.match(h.strip()) and h.strip() not in found:
            found[h.strip()]["organic"] = h

    return dict(found)


def _column_map(headers: list[str]) -> dict[str, str]:
    """Map canonical key → original header. Tolerant of H10 schema drift."""
    norm = {h: _norm_header(h) for h in headers}
    canonical = {
        "keyword": ["keywordphrase", "keyword", "phrase", "searchterm"],
        "search_volume": ["searchvolume", "sv"],
        "title_density": ["titledensity"],
        "competing_products": ["competingproducts"],
        "cpr": ["cpr"],
        "amazon_recommended": ["amazonrecommendedrank", "amazonrecrank", "amazonrecommended"],
        # Primary-ASIN dedicated columns (format B)
        "primary_organic": ["positionrank", "position", "organicrank"],
        "primary_sponsored": ["sponsoredrankavg", "sponsoredavgrank"],
        # Aggregate / signal columns
        "ranking_competitors_count": ["rankingcompetitorscount"],
        "competitor_rank_avg": ["competitorrankavg"],
        "h10_sugg_bid": ["h10ppcsuggbid"],
        "cerebro_iq": ["cerebroiqscore"],
    }
    out: dict[str, str] = {}
    for key, candidates in canonical.items():
        for orig, n in norm.items():
            if n in candidates:
                out[key] = orig
                break
    out["__asin_cols__"] = _detect_asin_columns(headers)  # type: ignore[assignment]
    return out


# ---------------------------------------------------------------------------
# Tagging
# ---------------------------------------------------------------------------

def _is_negative(keyword: str) -> bool:
    kw = keyword.lower()
    return any(tok in kw for tok in NEGATIVE_TOKENS)


def _classify(row: dict[str, Any]) -> str:
    if _is_negative(row["keyword"]):
        return "negative"

    sv = row.get("search_volume") or 0
    our_organic = row.get("our_organic_rank")
    competitor_top30 = row.get("competitor_top30_count", 0)

    if our_organic is not None and our_organic <= TOP_60 and sv >= 5000:
        return "core"
    if (our_organic is None or our_organic > TOP_60) and sv >= 1500 and competitor_top30 >= 2:
        return "opportunity"
    if competitor_top30 >= 3 and (our_organic is None or our_organic > TOP_60):
        return "competitor"
    return "watch"


def _opportunity_score(row: dict[str, Any]) -> float:
    """Heuristic 0-100 score: higher = better target.

    Weights: search volume (40%), competitor top-30 saturation (30%),
    our distance from page 1 (20%), CPR low = better (10%).
    """
    sv = row.get("search_volume") or 0
    sv_score = min(sv / 10000, 1.0) * 40

    comp = row.get("competitor_top30_count", 0)
    comp_score = min(comp / 5, 1.0) * 30

    our_organic = row.get("our_organic_rank")
    if our_organic is None:
        gap_score = 10  # unknown = some upside
    elif our_organic <= 16:
        gap_score = 20
    elif our_organic <= 60:
        gap_score = 15
    else:
        gap_score = 5

    cpr = row.get("cpr")
    if cpr is None:
        cpr_score = 5
    elif cpr <= 50:
        cpr_score = 10
    elif cpr <= 200:
        cpr_score = 7
    else:
        cpr_score = 3

    return round(sv_score + comp_score + gap_score + cpr_score, 1)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def parse_cerebro_csv(csv_path: Path, our_asin: str = OUR_ASIN) -> list[dict[str, Any]]:
    """Parse a Cerebro CSV into a list of keyword opportunity rows.

    Supports both H10 export formats:
      A) Multi-ASIN format — per-ASIN "<ASIN> Organic Rank" columns.
      B) Primary + Competitors format — our ranks in "Position (Rank)" /
         "Sponsored Rank (avg)" columns and competitor ranks in bare-ASIN
         columns (the primary ASIN does NOT have a per-ASIN column).
    """
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        cmap = _column_map(headers)
        if "keyword" not in cmap:
            raise ValueError(
                f"Could not find a keyword column in {csv_path.name}. "
                f"Headers: {headers}"
            )
        asin_cols: dict[str, dict[str, str]] = cmap.pop("__asin_cols__")  # type: ignore[arg-type]
        our_cols = asin_cols.get(our_asin, {})
        # In format B, our ASIN is NOT in per-ASIN columns (it's the primary).
        competitor_asins = [a for a in asin_cols if a != our_asin]
        primary_org_col = cmap.get("primary_organic")
        primary_sp_col = cmap.get("primary_sponsored")

        rows: list[dict[str, Any]] = []
        for raw in reader:
            keyword = (raw.get(cmap["keyword"]) or "").strip()
            if not keyword:
                continue
            sv = _to_int(raw.get(cmap.get("search_volume", ""), ""))
            if sv is not None and sv < MIN_SV:
                continue

            # Our ranks: prefer per-ASIN columns (format A), else the dedicated
            # primary columns (format B). H10 emits 0 to mean "not ranking" in
            # the primary columns — normalize to None.
            our_org = _to_int(raw.get(our_cols.get("organic", ""), ""))
            our_spons = _to_int(raw.get(our_cols.get("sponsored", ""), ""))
            if our_org is None and primary_org_col:
                v = _to_int(raw.get(primary_org_col, ""))
                our_org = None if v in (0, None) else v
            if our_spons is None and primary_sp_col:
                v = _to_int(raw.get(primary_sp_col, ""))
                our_spons = None if v in (0, None) else v

            comp_top30 = 0
            comp_ranks: dict[str, int | None] = {}
            for asin in competitor_asins:
                org_col = asin_cols[asin].get("organic")
                rank = _to_int(raw.get(org_col, "")) if org_col else None
                comp_ranks[asin] = rank
                if rank is not None and rank <= TOP_30:
                    comp_top30 += 1

            row: dict[str, Any] = {
                "keyword": keyword,
                "search_volume": sv,
                "our_organic_rank": our_org,
                "our_sponsored_rank": our_spons,
                "competitor_top30_count": comp_top30,
                "competitor_total_ranking": _to_int(raw.get(cmap.get("ranking_competitors_count", ""), "")),
                "competitor_ranks": comp_ranks,
                "title_density": _to_int(raw.get(cmap.get("title_density", ""), "")),
                "competing_products": _to_int(raw.get(cmap.get("competing_products", ""), "")),
                "cpr": _to_int(raw.get(cmap.get("cpr", ""), "")),
                "amazon_recommended": _to_int(raw.get(cmap.get("amazon_recommended", ""), "")),
                "h10_sugg_bid": _to_float(raw.get(cmap.get("h10_sugg_bid", ""), "")),
                "cerebro_iq": _to_int(raw.get(cmap.get("cerebro_iq", ""), "")),
            }
            row["tag"] = _classify(row)
            row["opportunity_score"] = _opportunity_score(row)
            rows.append(row)

    return rows


def merge_with_existing(
    new_rows: list[dict[str, Any]],
    target_kws_path: Path,
) -> dict[str, Any]:
    """Mark which Cerebro rows are NEW (not already in target_kws / KW_Data)."""
    existing: set[str] = set()
    if target_kws_path.exists():
        with target_kws_path.open() as f:
            data = json.load(f)
        for entry in data.get("target_keywords", []):
            kw = entry.get("keyword")
            if kw:
                existing.add(kw.lower().strip())

    fresh, known = [], []
    for r in new_rows:
        if r["keyword"].lower().strip() in existing:
            r["already_tracked"] = True
            known.append(r)
        else:
            r["already_tracked"] = False
            fresh.append(r)

    fresh.sort(key=lambda r: r["opportunity_score"], reverse=True)
    known.sort(key=lambda r: r["opportunity_score"], reverse=True)

    return {
        "_schema_version": "1.0",
        "_source": "Helium 10 Cerebro multi-ASIN CSV",
        "runDate": date.today().isoformat(),
        "our_asin": OUR_ASIN,
        "summary": {
            "total_keywords": len(new_rows),
            "new_opportunities": sum(1 for r in fresh if r["tag"] == "opportunity"),
            "competitor_gaps": sum(1 for r in fresh if r["tag"] == "competitor"),
            "negatives": sum(1 for r in new_rows if r["tag"] == "negative"),
        },
        "new_keywords": fresh,
        "already_tracked": known,
    }


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    from common.manifest_utils import update_manifest_bucket
    run_date = payload["runDate"]
    fname = f"cerebro_opportunities_{run_date}.json"
    out_repo = KW_DATA_DIR / fname
    out_dash = DASHBOARD_KW_DIR / fname

    out_repo.parent.mkdir(parents=True, exist_ok=True)
    out_dash.parent.mkdir(parents=True, exist_ok=True)

    with out_repo.open("w") as f:
        json.dump(payload, f, indent=2)
    shutil.copyfile(out_repo, out_dash)
    update_manifest_bucket(MANIFEST_FILE, "kw_data", [fname])
    return out_repo, out_dash


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest Helium 10 Cerebro multi-ASIN CSV.")
    ap.add_argument("csv", type=Path, help="Path to Cerebro CSV export")
    ap.add_argument(
        "--target-kws",
        type=Path,
        default=ROOT / "dashboard" / "public" / "data" / "strategy_target_kws.json",
        help="Existing target keywords JSON (used to flag already-tracked KWs)",
    )
    ap.add_argument("--our-asin", default=OUR_ASIN)
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV not found: {args.csv}", file=sys.stderr)
        return 1

    rows = parse_cerebro_csv(args.csv, our_asin=args.our_asin)
    payload = merge_with_existing(rows, args.target_kws)
    out_repo, out_dash = write_outputs(payload)

    s = payload["summary"]
    print(f"Parsed {s['total_keywords']} keywords from {args.csv.name}")
    print(f"  new opportunities : {s['new_opportunities']}")
    print(f"  competitor gaps   : {s['competitor_gaps']}")
    print(f"  negatives flagged : {s['negatives']}")
    print(f"\nTop 10 new opportunities by score:")
    for r in payload["new_keywords"][:10]:
        print(
            f"  [{r['opportunity_score']:5.1f}] {r['keyword']:50s} "
            f"SV={r.get('search_volume') or '-':>6}  "
            f"our_rank={r.get('our_organic_rank') or '-':>4}  "
            f"comp_top30={r['competitor_top30_count']}  tag={r['tag']}"
        )
    print(f"\nWrote: {out_repo}")
    print(f"Wrote: {out_dash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
