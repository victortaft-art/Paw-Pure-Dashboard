"""Pull Seller-Central Business Reports (sessions, page views, CVR) via Reports API.

Requests `GET_SALES_AND_TRAFFIC_REPORT` (JSON format) for a given date range,
polls until DONE, downloads the report document (possibly gzip-compressed),
parses it, and aggregates per-ASIN sessions/page-views/units/CVR for 7d + 30d.

This is the puller that unblocks StrategyTab ConversionFunnel + EconomicsTab
`totalSessions` — fields that are missing from the manual SC_Data files.

Rate limits:
    createReport: 0.0167 req/s (1/min)
    getReport:    2.0 req/s
    getReportDocument: 0.0167 req/s
"""
import gzip
import io
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sp_api_client import SPAPIClient  # noqa: E402
from config import PRODUCTS, ASIN_TO_KEY, MARKETPLACE_ID, RAW_DUMP_DIR  # noqa: E402


POLL_SLEEP = 15  # seconds between polls — reports take 30–120s typically
POLL_TIMEOUT = 600  # 10 min max wait per report
REPORT_TYPE = "GET_SALES_AND_TRAFFIC_REPORT"


def create_report(client, start_dt, end_dt):
    body = {
        "reportType": REPORT_TYPE,
        "marketplaceIds": [MARKETPLACE_ID],
        "dataStartTime": start_dt.isoformat().replace("+00:00", "Z"),
        "dataEndTime": end_dt.isoformat().replace("+00:00", "Z"),
        "reportOptions": {
            "asinGranularity": "CHILD",
            "dateGranularity": "DAY",
        },
    }
    resp = client.post("/reports/2021-06-30/reports", json=body)
    if resp.status_code not in (200, 202):
        raise RuntimeError(
            f"createReport failed: {resp.status_code} {resp.text[:300]}"
        )
    return resp.json()["reportId"]


def poll_report(client, report_id):
    deadline = time.time() + POLL_TIMEOUT
    while True:
        resp = client.get(f"/reports/2021-06-30/reports/{report_id}")
        if resp.status_code != 200:
            raise RuntimeError(
                f"getReport {report_id} failed: {resp.status_code} "
                f"{resp.text[:300]}"
            )
        info = resp.json()
        status = info.get("processingStatus")
        print(f"  poll: status={status}", flush=True)
        if status == "DONE":
            return info["reportDocumentId"]
        if status in ("CANCELLED", "FATAL"):
            raise RuntimeError(f"Report {report_id} ended with status {status}")
        if time.time() > deadline:
            raise TimeoutError(
                f"Report {report_id} did not finish in {POLL_TIMEOUT}s"
            )
        time.sleep(POLL_SLEEP)


def download_report_document(client, doc_id):
    resp = client.get(f"/reports/2021-06-30/documents/{doc_id}")
    if resp.status_code != 200:
        raise RuntimeError(
            f"getReportDocument {doc_id} failed: {resp.status_code} "
            f"{resp.text[:300]}"
        )
    info = resp.json()
    url = info["url"]
    compression = info.get("compressionAlgorithm")

    r = requests.get(url, timeout=120)
    r.raise_for_status()

    if compression == "GZIP":
        raw = gzip.decompress(r.content)
    else:
        raw = r.content

    return json.loads(raw.decode("utf-8"))


def aggregate_by_asin(report_json, start_date, end_date):
    """Aggregate sessions/page views/units/orders per ASIN over the window."""
    per_asin_totals = {}
    # The report has salesAndTrafficByAsin with childAsin as key dimension
    rows = report_json.get("salesAndTrafficByAsin", []) or []
    for row in rows:
        asin = row.get("childAsin") or row.get("parentAsin")
        if not asin:
            continue
        traffic = row.get("trafficByAsin", {}) or {}
        sales = row.get("salesByAsin", {}) or {}

        existing = per_asin_totals.setdefault(asin, {
            "sessions": 0,
            "sessions_b2b": 0,
            "page_views": 0,
            "page_views_b2b": 0,
            "browser_sessions": 0,
            "mobile_app_sessions": 0,
            "units": 0,
            "ordered_product_sales": 0.0,
            "total_order_items": 0,
            "buy_box_pct_sum": 0.0,
            "buy_box_pct_count": 0,
        })

        existing["sessions"] += traffic.get("sessions", 0) or 0
        existing["sessions_b2b"] += traffic.get("sessionsB2B", 0) or 0
        existing["page_views"] += traffic.get("pageViews", 0) or 0
        existing["page_views_b2b"] += traffic.get("pageViewsB2B", 0) or 0
        existing["browser_sessions"] += traffic.get("browserSessions", 0) or 0
        existing["mobile_app_sessions"] += traffic.get("mobileAppSessions", 0) or 0

        units = sales.get("unitsOrdered", 0) or 0
        existing["units"] += units
        amt = (sales.get("orderedProductSales") or {}).get("amount", 0) or 0
        try:
            existing["ordered_product_sales"] += float(amt)
        except (TypeError, ValueError):
            pass
        existing["total_order_items"] += sales.get("totalOrderItems", 0) or 0

        bb = traffic.get("buyBoxPercentage")
        if bb is not None:
            existing["buy_box_pct_sum"] += float(bb)
            existing["buy_box_pct_count"] += 1

    # Compute CVR + avg buy box
    for asin, t in per_asin_totals.items():
        s = t["sessions"]
        t["cvr_pct"] = round((t["units"] / s * 100), 2) if s else 0.0
        t["buy_box_pct_avg"] = (
            round(t["buy_box_pct_sum"] / t["buy_box_pct_count"], 2)
            if t["buy_box_pct_count"] else None
        )
        del t["buy_box_pct_sum"]
        del t["buy_box_pct_count"]
        t["ordered_product_sales"] = round(t["ordered_product_sales"], 2)

    return per_asin_totals


def build_schema(per_asin_raw, start_date, end_date, period_days):
    """Build the business_reports schema slice the dashboard expects."""
    # Filter/remap to only our tracked ASINs, but keep others under _all for audit
    per_asin = {}
    for asin, t in per_asin_raw.items():
        if asin in ASIN_TO_KEY:
            per_asin[asin] = t

    total_sessions = sum(t["sessions"] for t in per_asin.values())
    total_units = sum(t["units"] for t in per_asin.values())
    total_page_views = sum(t["page_views"] for t in per_asin.values())
    total_revenue = sum(t["ordered_product_sales"] for t in per_asin.values())
    cvr = round(total_units / total_sessions * 100, 2) if total_sessions else 0.0

    return {
        "date_range": f"{start_date} to {end_date}",
        "period_days": period_days,
        "_data_source": "sp_api_reports",
        "_note": "Pulled via Reports API: GET_SALES_AND_TRAFFIC_REPORT",
        "units_sold": total_units,
        "revenue": round(total_revenue, 2),
        "sessions_total": total_sessions,
        "page_views_total": total_page_views,
        "cvr_percent": cvr,
        "per_asin": per_asin,
        "_all_asins": per_asin_raw,
    }


def request_and_fetch(client, start_dt, end_dt):
    """Create → poll → download → parse one report."""
    print(
        f"  → createReport {start_dt.date()} to {end_dt.date()}...", flush=True
    )
    rid = create_report(client, start_dt, end_dt)
    print(f"     reportId={rid}", flush=True)
    time.sleep(POLL_SLEEP)
    doc_id = poll_report(client, rid)
    print(f"     ✓ report DONE, documentId={doc_id}", flush=True)
    return download_report_document(client, doc_id)


def pull():
    client = SPAPIClient()
    now = datetime.now(timezone.utc)

    # Business reports are finalized per day in Pacific Time.
    # Use yesterday as the last completed day to avoid partial data.
    # Dataset goes up to (exclusive) dataEndTime.
    end_7d = datetime.combine(
        (now - timedelta(days=1)).date(), datetime.min.time(), tzinfo=timezone.utc
    )
    start_7d = end_7d - timedelta(days=7)
    end_30d = end_7d
    start_30d = end_7d - timedelta(days=30)

    print(f"→ 7-day window:  {start_7d.date()} → {end_7d.date()}", flush=True)
    print(f"→ 30-day window: {start_30d.date()} → {end_30d.date()}", flush=True)

    # 7-day pull
    report_7d_json = request_and_fetch(client, start_7d, end_7d)
    per_asin_7d = aggregate_by_asin(
        report_7d_json, start_7d.date(), end_7d.date()
    )
    br_7d = build_schema(
        per_asin_7d, start_7d.date().isoformat(), end_7d.date().isoformat(), 7
    )

    # 30-day pull (separate request; reports are per-window)
    report_30d_json = request_and_fetch(client, start_30d, end_30d)
    per_asin_30d = aggregate_by_asin(
        report_30d_json, start_30d.date(), end_30d.date()
    )
    br_30d = build_schema(
        per_asin_30d, start_30d.date().isoformat(), end_30d.date().isoformat(), 30
    )

    result = {
        "pulled_at": now.isoformat().replace("+00:00", "Z"),
        "business_reports": br_7d,
        "business_reports_30day": br_30d,
    }

    RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = RAW_DUMP_DIR / f"business_reports_{now.date().isoformat()}.json"
    with open(dump_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Raw dump: {dump_path}", flush=True)

    # Summary
    print("\n7-day summary:")
    print(
        f"  sessions={br_7d['sessions_total']}  units={br_7d['units_sold']}  "
        f"CVR={br_7d['cvr_percent']}%  revenue=${br_7d['revenue']}"
    )
    for asin, t in br_7d["per_asin"].items():
        key = ASIN_TO_KEY.get(asin, "?")
        print(
            f"  {key:8s} {asin}  sess={t['sessions']}  units={t['units']}  "
            f"CVR={t['cvr_pct']}%"
        )

    print("\n30-day summary:")
    print(
        f"  sessions={br_30d['sessions_total']}  units={br_30d['units_sold']}  "
        f"CVR={br_30d['cvr_percent']}%  revenue=${br_30d['revenue']}"
    )

    return result


if __name__ == "__main__":
    pull()
