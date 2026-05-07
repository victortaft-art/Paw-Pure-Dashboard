"""Pull per-keyword and per-campaign PPC data from Amazon Advertising API v3.

Async report flow (v3):
  1. POST /reporting/reports (Content-Type: application/vnd.createasyncreportrequest.v3+json)
     → get reportId
  2. Poll GET /reporting/reports/{reportId} until status == "COMPLETED"
  3. GET download URL (presigned S3) → decompress gzip → parse JSON rows

Pulls two reports per run:
  - SP Targeting report  (covers manual keywords + auto targets in one report)
  - SP Campaigns report  (campaign-level rollup)

Output structure (returned dict):
  {
    "pulled_at": ...,
    "report_date": "YYYY-MM-DD",
    "profile_id": ...,
    "summary": { total_spend, total_sales_7d, overall_acos, ... },
    "campaigns": [ { campaign, spend, sales, acos, ... }, ... ],
    "keywords": [ { keyword, match_type, spend, sales, acos, ctr, cpc, ... }, ... ],
  }

Required env vars:
  ADS_API_PROFILE_ID      — advertising profile ID (auto-discovered via /v2/profiles if missing)
  ADS_API_CLIENT_ID       — LWA client ID (falls back to SP_API_CLIENT_ID if blank)
  ADS_API_CLIENT_SECRET   — LWA client secret
  ADS_API_REFRESH_TOKEN   — LWA refresh token
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

from ads_api_client import AdsAPIClient  # noqa: E402
from config import RAW_DUMP_DIR  # noqa: E402

POLL_INTERVAL = 10
MAX_POLL_ATTEMPTS = 90  # 15 min max — v3 reports can be slow on fresh accounts

REPORT_CONTENT_TYPE = "application/vnd.createasyncreportrequest.v3+json"


# ---------------------------------------------------------------------------
# Profile discovery
# ---------------------------------------------------------------------------

def _resolve_profile(client):
    if client.profile_id:
        print(f"  profile_id: {client.profile_id} (from env)", flush=True)
        return
    print("  ADS_PROFILE_ID not set — calling /v2/profiles...", flush=True)
    profiles = client.get_profiles()
    for p in profiles:
        info = p.get("accountInfo") or {}
        if p.get("countryCode") == "US" and info.get("type") == "seller":
            client.profile_id = str(p["profileId"])
            print(f"  Found US seller profile: {client.profile_id}", flush=True)
            return
    if profiles:
        client.profile_id = str(profiles[0]["profileId"])
        print(f"  Using first profile: {client.profile_id}", flush=True)
    else:
        raise RuntimeError("No advertising profiles found.")


# ---------------------------------------------------------------------------
# v3 Report lifecycle
# ---------------------------------------------------------------------------

def _post_v3(client, path, payload):
    """POST helper that overrides Content-Type for v3 reports endpoint."""
    headers = {
        "Authorization": f"Bearer {client._get_access_token()}",
        "Amazon-Advertising-API-ClientId": client.client_id,
        "Amazon-Advertising-API-Scope": str(client.profile_id),
        "Content-Type": REPORT_CONTENT_TYPE,
        "Accept": REPORT_CONTENT_TYPE,
    }
    return requests.post(
        f"{client.BASE_URL}{path}",
        headers=headers,
        json=payload,
        timeout=60,
    )


def _request_report(client, report_type_id, group_by, columns, start_date, end_date, name):
    payload = {
        "name": name,
        "startDate": start_date,
        "endDate": end_date,
        "configuration": {
            "adProduct": "SPONSORED_PRODUCTS",
            "groupBy": group_by,
            "columns": columns,
            "reportTypeId": report_type_id,
            "timeUnit": "SUMMARY",
            "format": "GZIP_JSON",
        },
    }
    resp = _post_v3(client, "/reporting/reports", payload)
    if resp.status_code not in (200, 202):
        raise RuntimeError(
            f"Report request failed ({resp.status_code}): {resp.text[:400]}"
        )
    rid = resp.json().get("reportId")
    if not rid:
        raise RuntimeError(f"No reportId in response: {resp.text[:200]}")
    return rid


def _poll_report(client, report_id, label=""):
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        resp = client.get(f"/reporting/reports/{report_id}")
        if resp.status_code != 200:
            raise RuntimeError(
                f"Status check failed ({resp.status_code}): {resp.text[:200]}"
            )
        data = resp.json()
        status = data.get("status", "UNKNOWN")
        print(
            f"  [{label}] attempt {attempt}/{MAX_POLL_ATTEMPTS} — {status}",
            flush=True,
        )
        if status == "COMPLETED":
            url = data.get("url")
            if not url:
                raise RuntimeError("Report COMPLETED but no download url")
            return url
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"Report failed: {data}")
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(
        f"Report {report_id} timed out after {MAX_POLL_ATTEMPTS} attempts"
    )


def _download_report(location_url):
    resp = requests.get(location_url, timeout=120)
    resp.raise_for_status()
    with gzip.open(io.BytesIO(resp.content)) as gz:
        return json.loads(gz.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _f(v, default=0.0):
    try:
        return float(v or default)
    except (TypeError, ValueError):
        return default


def _i(v, default=0):
    try:
        return int(v or default)
    except (TypeError, ValueError):
        return default


def _acos(spend, sales):
    if not sales:
        return None
    return round(spend / sales * 100, 1)


def _rate(num, den):
    if not den:
        return None
    return round(num / den, 4)


def _aggregate_keywords(rows):
    """Roll up v3 SP targeting rows."""
    acc = {}
    for row in rows:
        # v3 field names: keyword (manual) or targeting (auto/expr)
        kw = (
            row.get("keyword")
            or row.get("targeting")
            or row.get("keywordText")
            or "auto-target"
        )
        match = (row.get("matchType") or "auto").lower()
        key = f"{kw} [{match}]"

        if key not in acc:
            acc[key] = {
                "keyword": kw,
                "match_type": match,
                "campaign": row.get("campaignName"),
                "ad_group": row.get("adGroupName"),
                "bid": _f(row.get("keywordBid"), None),
                "impressions": 0,
                "clicks": 0,
                "spend": 0.0,
                "attributed_sales_7d": 0.0,
                "conversions_7d": 0,
            }

        acc[key]["impressions"] += _i(row.get("impressions"))
        acc[key]["clicks"] += _i(row.get("clicks"))
        acc[key]["spend"] = round(acc[key]["spend"] + _f(row.get("cost")), 2)
        acc[key]["attributed_sales_7d"] = round(
            acc[key]["attributed_sales_7d"] + _f(row.get("sales7d")), 2
        )
        acc[key]["conversions_7d"] += _i(row.get("purchases7d"))

    for d in acc.values():
        d["acos"] = _acos(d["spend"], d["attributed_sales_7d"])
        d["ctr"] = _rate(d["clicks"], d["impressions"])
        d["cpc"] = _rate(d["spend"], d["clicks"])

    return sorted(acc.values(), key=lambda x: x["spend"], reverse=True)


def _aggregate_campaigns(rows):
    acc = {}
    for row in rows:
        name = row.get("campaignName") or "unknown"
        if name not in acc:
            acc[name] = {
                "campaign": name,
                "campaign_id": row.get("campaignId"),
                "impressions": 0,
                "clicks": 0,
                "spend": 0.0,
                "attributed_sales_7d": 0.0,
                "conversions_7d": 0,
            }
        acc[name]["impressions"] += _i(row.get("impressions"))
        acc[name]["clicks"] += _i(row.get("clicks"))
        acc[name]["spend"] = round(acc[name]["spend"] + _f(row.get("cost")), 2)
        acc[name]["attributed_sales_7d"] = round(
            acc[name]["attributed_sales_7d"] + _f(row.get("sales7d")), 2
        )
        acc[name]["conversions_7d"] += _i(row.get("purchases7d"))

    for d in acc.values():
        d["acos"] = _acos(d["spend"], d["attributed_sales_7d"])
        d["ctr"] = _rate(d["clicks"], d["impressions"])
        d["cpc"] = _rate(d["spend"], d["clicks"])

    return sorted(acc.values(), key=lambda x: x["spend"], reverse=True)


# ---------------------------------------------------------------------------
# Main pull
# ---------------------------------------------------------------------------

def pull():
    client = AdsAPIClient()
    now = datetime.now(timezone.utc)

    print("→ Amazon Advertising API: resolving profile...", flush=True)
    _resolve_profile(client)

    # v3 uses YYYY-MM-DD. Use yesterday for both start+end (single-day report).
    yesterday = (now - timedelta(days=1)).date().isoformat()
    print(f"→ Report date: {yesterday}", flush=True)

    # SP Targeting report covers BOTH manual keywords and auto targets.
    targeting_columns = [
        "impressions", "clicks", "cost",
        "sales7d", "purchases7d",
        "campaignName", "campaignId",
        "adGroupName", "adGroupId",
        "keyword", "keywordBid", "matchType", "targeting",
        "keywordId", "adKeywordStatus",
    ]

    campaign_columns = [
        "impressions", "clicks", "cost",
        "sales7d", "purchases7d",
        "campaignName", "campaignId", "campaignStatus",
    ]

    print("→ Requesting reports...", flush=True)
    tgt_id = _request_report(
        client, "spTargeting", ["targeting"],
        targeting_columns, yesterday, yesterday,
        f"sp_targeting_{yesterday}",
    )
    time.sleep(1)
    camp_id = _request_report(
        client, "spCampaigns", ["campaign"],
        campaign_columns, yesterday, yesterday,
        f"sp_campaigns_{yesterday}",
    )
    print(f"  targeting report: {tgt_id}", flush=True)
    print(f"  campaign report:  {camp_id}", flush=True)

    print("→ Polling targeting report...", flush=True)
    tgt_url = _poll_report(client, tgt_id, "targeting")

    print("→ Polling campaign report...", flush=True)
    camp_url = _poll_report(client, camp_id, "campaigns")

    print("→ Downloading reports...", flush=True)
    tgt_rows = _download_report(tgt_url)
    camp_rows = _download_report(camp_url)
    print(
        f"  rows: {len(tgt_rows)} targeting, {len(camp_rows)} campaign-rows",
        flush=True,
    )

    kw_list = _aggregate_keywords(tgt_rows)
    camp_list = _aggregate_campaigns(camp_rows)

    total_spend = round(sum(d["spend"] for d in camp_list), 2)
    total_sales = round(sum(d["attributed_sales_7d"] for d in camp_list), 2)
    total_clicks = sum(d["clicks"] for d in camp_list)
    total_impressions = sum(d["impressions"] for d in camp_list)

    result = {
        "pulled_at": now.isoformat().replace("+00:00", "Z"),
        "report_date": yesterday,
        "profile_id": client.profile_id,
        "summary": {
            "total_spend_1d": total_spend,
            "total_attributed_sales_7d": total_sales,
            "total_clicks_1d": total_clicks,
            "total_impressions_1d": total_impressions,
            "overall_acos": _acos(total_spend, total_sales),
            "overall_ctr": _rate(total_clicks, total_impressions),
            "overall_cpc": _rate(total_spend, total_clicks),
        },
        "campaigns": camp_list,
        "keywords": kw_list,
    }

    RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = RAW_DUMP_DIR / f"ads_{now.date().isoformat()}.json"
    with open(dump_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Raw dump: {dump_path}", flush=True)

    print("\n✓ Advertising API summary:", flush=True)
    print(f"  Campaigns:              {len(camp_list)}", flush=True)
    print(f"  Keywords + targets:     {len(kw_list)}", flush=True)
    print(f"  Total spend (1d):       ${total_spend}", flush=True)
    print(f"  Attributed sales (7d):  ${total_sales}", flush=True)
    print(f"  Overall ACoS:           {_acos(total_spend, total_sales)}%", flush=True)

    return result


if __name__ == "__main__":
    pull()
