"""Aggregate per-keyword PPC metrics across all ads_*.json files into a
single keyword_history.json the dashboard can render with 7d/30d toggle.

Output: dashboard/public/data/keyword_history.json
{
  "_generated": "YYYY-MM-DD",
  "keywords_7d": [{ keyword, match_type, bid, spend, clicks, impressions, sales, acos, ctr, cpc }, ...],
  "keywords_30d": [...],
  "keywords_1d": [...],   # latest day only, for backwards compatibility with current Top Keywords table
  "windows": { "7d": {start, end, files}, "30d": {start, end, files} }
}

Aggregation rules:
  - spend, clicks, impressions: SUM across the window (each ads file is 1d)
  - attributed_sales_7d: MAX across the window (Amazon's rolling 7d figure
    can drop to 0 from attribution lag; max is more honest)
  - acos: re-derive from spend_window / sales_window
  - ctr / cpc: re-derive from totals
  - bid + match_type: take from latest file (most recent setting)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from amazon_api.config import RAW_DUMP_DIR  # noqa: E402

OUT_PATH = ROOT.parent / "public" / "data" / "keyword_history.json"

ADS_RE = re.compile(r"^ads_(\d{4}-\d{2}-\d{2})\.json$")


def _load_ads() -> dict[date, dict]:
    out: dict[date, dict] = {}
    if not RAW_DUMP_DIR.exists():
        return out
    for p in sorted(RAW_DUMP_DIR.glob("ads_*.json")):
        m = ADS_RE.match(p.name)
        if not m:
            continue
        try:
            out[date.fromisoformat(m.group(1))] = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return out


def aggregate_window(end: date, days: int, ads_by_date: dict[date, dict]) -> tuple[list[dict], dict]:
    """Aggregate per-keyword metrics across [end - days + 1 .. end]."""
    # Map keyword → aggregated dict
    agg: dict[str, dict] = defaultdict(lambda: {
        "spend": 0.0, "clicks": 0, "impressions": 0,
        "attributed_sales_7d": 0.0,  # MAX across window
        "conversions_7d": 0,         # MAX across window
        "bid": None, "match_type": None, "campaign": None,
    })
    files_used = []

    for offset in range(days):
        d = end - timedelta(days=offset)
        ads = ads_by_date.get(d)
        if not ads:
            continue
        files_used.append(f"ads_{d.isoformat()}.json")
        for kw in ads.get("keywords", []):
            key = kw.get("keyword")
            if not key:
                continue
            entry = agg[key]
            entry["spend"] += float(kw.get("spend") or 0)
            entry["clicks"] += int(kw.get("clicks") or 0)
            entry["impressions"] += int(kw.get("impressions") or 0)
            sales = float(kw.get("attributed_sales_7d") or 0)
            entry["attributed_sales_7d"] = max(entry["attributed_sales_7d"], sales)
            convs = int(kw.get("conversions_7d") or 0)
            entry["conversions_7d"] = max(entry["conversions_7d"], convs)
            # latest non-null bid + match_type
            if kw.get("bid") is not None:
                entry["bid"] = kw["bid"]
            if kw.get("match_type"):
                entry["match_type"] = kw["match_type"]
            if kw.get("campaign"):
                entry["campaign"] = kw["campaign"]

    out = []
    for keyword, e in agg.items():
        spend = e["spend"]
        sales = e["attributed_sales_7d"]
        clicks = e["clicks"]
        impressions = e["impressions"]
        out.append({
            "keyword": keyword,
            "match_type": e["match_type"],
            "campaign": e["campaign"],
            "bid": e["bid"],
            "spend": round(spend, 2),
            "clicks": clicks,
            "impressions": impressions,
            "attributed_sales_7d": round(sales, 2),
            "conversions_7d": e["conversions_7d"],
            "ctr": round(clicks / impressions, 4) if impressions > 0 else None,
            "cpc": round(spend / clicks, 2) if clicks > 0 else None,
            "acos": round((spend / sales) * 100, 1) if sales > 0 else None,
        })

    out.sort(key=lambda r: r["spend"], reverse=True)
    return out, {
        "start": (end - timedelta(days=days - 1)).isoformat(),
        "end": end.isoformat(),
        "files": files_used,
    }


def main() -> int:
    ads = _load_ads()
    if not ads:
        print("No ads_*.json files found.", file=sys.stderr)
        return 1
    latest = max(ads.keys())

    kw_1d, _w1d = aggregate_window(latest, 1, ads)
    kw_7d, w7d = aggregate_window(latest, 7, ads)
    kw_30d, w30d = aggregate_window(latest, 30, ads)

    payload = {
        "_generated": date.today().isoformat(),
        "_latest_data": latest.isoformat(),
        "keywords_1d": kw_1d,
        "keywords_7d": kw_7d,
        "keywords_30d": kw_30d,
        "windows": {"1d": {"start": latest.isoformat(), "end": latest.isoformat()}, "7d": w7d, "30d": w30d},
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUT_PATH.relative_to(ROOT.parent)}")
    print(f"  1d: {len(kw_1d)} kws · 7d: {len(kw_7d)} kws ({len(w7d['files'])} files) · 30d: {len(kw_30d)} kws ({len(w30d['files'])} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
