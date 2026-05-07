"""Shared PPC Analysis builder.

Used by:
  - amazon_api/build_sc_data.py (daily pipeline) — emits today's PPC_Analysis
  - scripts/backfill_ppc_analysis.py (one-off backfill) — emits historical PPC_Analysis

The dashboard's calculations.js fallback chain looks for:
    ppc?.summary?.overall_acos_7d
This module produces files matching that schema.

Logic notes:
  - Source: amazon_api/data/raw/ads_<date>.json (Amazon Ads API output)
  - Spend is summed across the trailing 7-day window
  - Sales uses LAST-KNOWN-GOOD: latest non-null AND positive
    `total_attributed_sales_7d` value in the window. Amazon's daily 7d-rolling
    sales field can reset to 0 even when a recent day had a real sale; using
    last-known-good keeps the dashboard ACoS meaningful.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Resolve project paths via amazon_api.config (single source of truth)
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))  # ensure project root is importable
from amazon_api.config import RAW_DUMP_DIR, SC_DATA_DIR  # noqa: E402

ADS_FILE_RE = re.compile(r"^ads_(\d{4}-\d{2}-\d{2})\.json$")


def load_ads_files(raw_dir: Path = RAW_DUMP_DIR) -> dict[date, dict]:
    """Return {date: ads_payload} for every ads_*.json under raw_dir."""
    out: dict[date, dict] = {}
    if not raw_dir.exists():
        return out
    for p in sorted(raw_dir.glob("ads_*.json")):
        m = ADS_FILE_RE.match(p.name)
        if not m:
            continue
        try:
            out[date.fromisoformat(m.group(1))] = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"  warn: skipping {p.name}: {e}", file=sys.stderr)
    return out


def aggregate_7d(target_date: date, ads_by_date: dict[date, dict]) -> dict:
    """Sum spend / clicks / impressions across 7 days; sales = last-known-good."""
    spend = 0.0
    clicks = 0
    impressions = 0
    days_with_data = 0
    for offset in range(7):
        d = target_date - timedelta(days=offset)
        ads = ads_by_date.get(d)
        if not ads:
            continue
        days_with_data += 1
        s = ads.get("summary") or {}
        spend += float(s.get("total_spend_1d") or 0)
        clicks += int(s.get("total_clicks_1d") or 0)
        impressions += int(s.get("total_impressions_1d") or 0)

    # Last-known-good sales (skip zeros that look like attribution resets)
    sales_value = None
    sales_as_of = None
    for offset in range(7):
        d = target_date - timedelta(days=offset)
        ads = ads_by_date.get(d)
        if not ads:
            continue
        s = ads.get("summary") or {}
        v = s.get("total_attributed_sales_7d")
        if v is not None and v > 0:
            sales_value = float(v)
            sales_as_of = d.isoformat()
            break

    sales = sales_value if sales_value is not None else 0.0
    acos_7d = round((spend / sales) * 100, 1) if sales > 0 else None
    ctr = round(clicks / impressions, 4) if impressions > 0 else None
    cpc = round(spend / clicks, 2) if clicks > 0 else None

    return {
        "overall_acos_7d": acos_7d,
        "total_spend_7d": round(spend, 2),
        "total_attributed_sales_7d": round(sales, 2),
        "total_clicks_7d": clicks,
        "total_impressions_7d": impressions,
        "overall_ctr": ctr,
        "overall_cpc": cpc,
        "_days_with_data": days_with_data,
        "_sales_as_of": sales_as_of,
    }


def build_ppc_analysis(target_date: date, ads_by_date: dict[date, dict]) -> dict | None:
    """Build a single PPC_Analysis payload for target_date. None if no ads data."""
    ads = ads_by_date.get(target_date)
    if not ads:
        return None
    summary_7d = aggregate_7d(target_date, ads_by_date)
    return {
        "_schema_version": "2.0",
        "_data_source": "ads_api",
        "_generated_at": target_date.isoformat(),
        "report_date": ads.get("report_date") or target_date.isoformat(),
        "pulled_at": ads.get("pulled_at"),
        "profile_id": ads.get("profile_id"),
        "summary": summary_7d,
        "summary_1d": ads.get("summary") or {},
        "campaigns": ads.get("campaigns") or [],
        "keywords": ads.get("keywords") or [],
    }


def write_ppc_analysis(target_date: date, payload: dict, sc_dir: Path = SC_DATA_DIR) -> Path:
    """Atomic write of payload to PPC_Analysis_<date>.json under sc_dir. Returns path."""
    sc_dir.mkdir(parents=True, exist_ok=True)
    out_path = sc_dir / f"PPC_Analysis_{target_date.isoformat()}.json"
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(out_path)
    return out_path
