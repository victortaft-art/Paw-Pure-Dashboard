"""Aggregate per-day KPIs across all available pulls into one timeseries file.

Reads:
  - amazon_api/data/raw/ads_<date>.json    (Ads API: spend, clicks, impressions, sales)
  - dashboard/public/data/sc_data/SC_Data_<date>.json  (Business reports: sessions, cvr, revenue)

Writes:
  - dashboard/public/data/daily_kpis_history.json
    {
      "_generated": "...",
      "_window": { "start": "YYYY-MM-DD", "end": "YYYY-MM-DD" },
      "series": [
        { "date": "YYYY-MM-DD",
          "ad_spend": 21.98,
          "ad_sales_7d": 49.99,
          "ctr": 0.0052,
          "cpc": 2.20,
          "clicks": 10,
          "impressions": 1929,
          "sessions": 157,
          "cvr": 3.18,
          "revenue": null,
          "units": null,
          "_sources": { "ads": "ads_2026-04-27.json", "sc": "SC_Data_2026-04-27.json" } },
        ...
      ]
    }

Used by the PPC Strategy tab — for the Daily Trend chart (overlays Spend / Sessions / CVR)
AND for last-known-good Sessions / CVR KPI tiles.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADS_DIR = ROOT / "amazon_api" / "data" / "raw"
SC_DIR = ROOT.parent / "public" / "data" / "sc_data"
OUT_PATH = ROOT.parent / "public" / "data" / "daily_kpis_history.json"
MANIFEST = ROOT.parent / "public" / "data" / "manifest.json"

ADS_RE = re.compile(r"^ads_(\d{4}-\d{2}-\d{2})\.json$")
SC_RE = re.compile(r"^SC_Data_(\d{4}-\d{2}-\d{2})\.json$")


def _load_by_date(directory: Path, regex: re.Pattern) -> dict[date, dict]:
    out: dict[date, dict] = {}
    if not directory.exists():
        return out
    for p in sorted(directory.glob("*.json")):
        m = regex.match(p.name)
        if not m:
            continue
        try:
            out[date.fromisoformat(m.group(1))] = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return out


def _ads_row(d: date, ads: dict) -> dict:
    s = ads.get("summary") or {}
    spend = s.get("total_spend_1d")
    sales = s.get("total_attributed_sales_7d")  # rolling 7d, but useful for trend
    clicks = s.get("total_clicks_1d")
    impressions = s.get("total_impressions_1d")
    ctr = s.get("overall_ctr")
    cpc = s.get("overall_cpc")
    return {
        "ad_spend": float(spend) if spend is not None else None,
        "ad_sales_7d": float(sales) if sales is not None else None,
        "clicks": int(clicks) if clicks is not None else None,
        "impressions": int(impressions) if impressions is not None else None,
        "ctr": float(ctr) if ctr is not None else None,
        "cpc": float(cpc) if cpc is not None else None,
    }


def _sc_row(d: date, sc: dict) -> dict:
    br = sc.get("business_reports") or {}
    return {
        "sessions": br.get("sessions_total"),
        "cvr": br.get("cvr_percent"),
        "revenue": br.get("revenue"),
        "units": br.get("units_sold"),
        "page_views": br.get("page_views_total"),
    }


def main() -> int:
    ads_by_date = _load_by_date(ADS_DIR, ADS_RE)
    sc_by_date = _load_by_date(SC_DIR, SC_RE)

    all_dates = sorted(set(ads_by_date) | set(sc_by_date))
    if not all_dates:
        print("No source data found.", file=sys.stderr)
        return 1

    series = []
    for d in all_dates:
        ads = ads_by_date.get(d)
        sc = sc_by_date.get(d)
        row = {"date": d.isoformat()}
        sources = {}
        if ads:
            row.update(_ads_row(d, ads))
            sources["ads"] = f"ads_{d.isoformat()}.json"
        if sc:
            row.update(_sc_row(d, sc))
            sources["sc"] = f"SC_Data_{d.isoformat()}.json"
        row["_sources"] = sources
        series.append(row)

    payload = {
        "_generated": date.today().isoformat(),
        "_window": {"start": series[0]["date"], "end": series[-1]["date"]},
        "_count": len(series),
        "series": series,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2))

    # Manifest doesn't list root-level files, but log for confirmation
    print(f"Wrote {OUT_PATH.relative_to(ROOT.parent)}")
    print(f"  {len(series)} days · {payload['_window']['start']} → {payload['_window']['end']}")

    # Quick last-known-good summary
    def last_nonnull(field: str) -> tuple[str | None, object]:
        for r in reversed(series):
            v = r.get(field)
            if v is not None:
                return r["date"], v
        return None, None

    for f in ("ad_spend", "ctr", "cpc", "sessions", "cvr", "revenue"):
        d, v = last_nonnull(f)
        if d:
            print(f"  last-known {f}: {v} (as of {d})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
