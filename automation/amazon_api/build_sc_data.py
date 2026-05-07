"""Compose SC_Data_YYYY-MM-DD.json from all SC-side pullers.

Runs: pull_orders, pull_inventory, pull_catalog, pull_business_reports,
pull_financials. Merges their outputs into a single JSON matching the
existing SC_Data schema so no dashboard component changes are required.

Writes atomically (temp file + rename).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (  # noqa: E402
    PRODUCTS,
    ASIN_TO_KEY,
    SC_DATA_DIR,
)
from pullers import pull_orders, pull_inventory, pull_catalog  # noqa: E402
from pullers import pull_business_reports, pull_financials, pull_ads  # noqa: E402


def build_fba_inventory(inv_out, catalog_out, orders_out):
    """Merge inventory + catalog BSR + orders-derived velocity into fba_inventory."""
    agg = orders_out["by_product"]
    inv = inv_out["fba_inventory"]
    cat = catalog_out["catalog"]

    # Pull Pet Supplies rank from display_group_ranks
    def pet_supplies_rank(key):
        c = cat.get(key, {})
        for dr in c.get("display_group_ranks") or []:
            if dr.get("category") == "Pet Supplies":
                return dr.get("rank")
        return None

    def sub_rank(key):
        c = cat.get(key, {})
        overall = c.get("bsr_overall") or {}
        return {"rank": overall.get("rank"), "category": overall.get("category")}

    fba = {
        "scraped_at": inv_out["pulled_at"],
        "data_source": "sp_api",
        "_source": "SP-API: /fba/inventory/v1/summaries + /catalog/2022-04-01/items",
    }

    for key in PRODUCTS:
        inv_row = inv.get(key, {}) or {}
        units_30d = agg[key]["units_30d"]
        units_7d = agg[key]["units_7d"]
        velocity_30d = round(units_30d / 30, 2)
        velocity_7d = round(units_7d / 7, 2)
        avail = inv_row.get("fba_available")

        days_30d = None
        days_7d = None
        if avail is not None and velocity_30d > 0:
            days_30d = int(avail / velocity_30d)
        if avail is not None and velocity_7d > 0:
            days_7d = int(avail / velocity_7d)

        fba[key] = {
            "asin": inv_row.get("asin") or PRODUCTS[key]["asin"],
            "sku": inv_row.get("sku") or PRODUCTS[key].get("sku"),
            "fba_available": avail,
            "inbound": inv_row.get("inbound"),
            "reserved": inv_row.get("reserved"),
            "bsr_pet_supplies": pet_supplies_rank(key),
            "bsr_subcategory": sub_rank(key),
            "_bsr_source": "SP-API Catalog (displayGroupRanks + classificationRanks)",
            "units_sold_7day": units_7d,
            "units_sold_30day": units_30d,
            "revenue_7day": agg[key]["revenue_7d"],
            "revenue_30day": agg[key]["revenue_30d"],
            "price": PRODUCTS[key]["price"],
            "total_fee_per_unit": PRODUCTS[key]["amazon_fee"],
            "daily_velocity_7day": velocity_7d,
            "daily_velocity_30day": velocity_30d,
            "days_of_supply_est_7day": days_7d,
            "days_of_supply_est_30day": days_30d,
        }

    return fba


def build_campaign_manager(financials_out, ads_out=None):
    """Populate campaign_manager from Advertising API (preferred) or Finances fallback."""
    agg = financials_out["aggregates"]
    spend_finances_7d = abs(agg.get("ads_payments_7d", 0))
    spend_finances_30d = abs(agg.get("ads_payments_30d", 0))

    if ads_out:
        summary = ads_out.get("summary", {})
        return {
            "_data_source": "ads_api",
            "_note": "Per-keyword and per-campaign data from Amazon Advertising API v2.",
            "_report_date": ads_out.get("report_date"),
            "ad_spend_1d": summary.get("total_spend_1d"),
            "ad_spend_7day": round(spend_finances_7d, 2) if spend_finances_7d else None,
            "ad_spend_30day": round(spend_finances_30d, 2) if spend_finances_30d else None,
            "_spend_note": (
                "ad_spend_1d = Advertising API (yesterday, 1-day). "
                "ad_spend_7day/30day = Finances API billing events (may include billing lag)."
            ),
            "impressions_1d": summary.get("total_impressions_1d"),
            "clicks_1d": summary.get("total_clicks_1d"),
            "attributed_sales_7d": summary.get("total_attributed_sales_7d"),
            "overall_acos": summary.get("overall_acos"),
            "overall_ctr": summary.get("overall_ctr"),
            "overall_cpc": summary.get("overall_cpc"),
            "campaigns": ads_out.get("campaigns", []),
            "keywords": ads_out.get("keywords", []),
        }

    return {
        "_data_source": "sp_api_finances",
        "_note": (
            "Ad spend from Finances API ProductAdsPaymentEventList. "
            "Per-keyword detail requires Ads API."
        ),
        "ad_spend_7day": round(spend_finances_7d, 2) if spend_finances_7d else None,
        "ad_spend_30day": round(spend_finances_30d, 2) if spend_finances_30d else None,
        "impressions_7day": None,
        "clicks_7day": None,
        "ad_sales_7day": None,
        "acos_7day": None,
        "acos_percent_30day": None,
        "ad_sales_30day": None,
    }


def build_fba_orders_detail(orders_out):
    # Filter to 7-day window only to match existing schema
    orders_7d = [o for o in orders_out["orders_detail"] if o["in_7d_window"]]
    # Rename/reshape to match existing schema
    reshaped = []
    for o in orders_7d:
        reshaped.append({
            "order_id": o["order_id"],
            "date": o["date"],
            "time_utc": o["time_utc"],
            "buyer": None,  # PII — requires RDT, deferred
            "asin": o["asin"],
            "product": o["product"],
            "item_subtotal": o["item_subtotal"],
            "status": o["status"],
            "type": o["type"],
        })
    return {
        "_data_source": "sp_api_orders",
        "_source": "SP-API: /orders/v0/orders + /orders/v0/orders/{id}/orderItems",
        "total_order_lines_7day": len(reshaped),
        "orders": reshaped,
    }


def build_sales_today(orders_out):
    """Today (UTC) aggregates from orders_detail."""
    today = datetime.now(timezone.utc).date().isoformat()
    today_orders = [
        o for o in orders_out["orders_detail"] if o["date"] == today
    ]
    total_items = len(today_orders)
    units = sum(o["quantity"] for o in today_orders)
    revenue = round(sum(o["item_subtotal"] for o in today_orders), 2)

    return {
        "_data_source": "sp_api_orders",
        "total_order_items_today": total_items,
        "units_ordered_today": units,
        "revenue_today": revenue,
        "ad_spend_today_so_far": None,
        "_ad_note": "Today's ad spend: Ads API reports use yesterday's data (today still accumulating).",
    }


def _null_br():
    """Return a null-filled business-reports structure for when the API is unavailable."""
    null_report = {
        "date_range": None,
        "period_days": None,
        "_data_source": "UNAVAILABLE",
        "_note": "Reports API quota exceeded — sessions/CVR not available this run.",
        "units_sold": None,
        "revenue": None,
        "sessions_total": None,
        "page_views_total": None,
        "cvr_percent": None,
        "per_asin": {},
        "_all_asins": {},
    }
    return {
        "pulled_at": None,
        "business_reports": {**null_report, "period_days": 7},
        "business_reports_30day": {**null_report, "period_days": 30},
    }


def build_highlights(orders_out, br_out, fba_inventory):
    """Simple derived narrative highlights."""
    totals = orders_out["totals"]
    br_7d = br_out["business_reports"]
    sessions = br_7d.get("sessions_total")
    cvr = br_7d.get("cvr_percent")
    sessions_str = f"sessions {sessions}, CVR {cvr}%" if sessions is not None else "sessions N/A (quota exceeded)"
    highlights = {
        "revenue_7d": f"7-day revenue ${totals['revenue_7d']} across {totals['orders_7d']} orders ({totals['units_7d']} units).",
        "sessions_7d": f"7-day {sessions_str}.",
    }
    fountain_days = fba_inventory.get("fountain", {}).get("days_of_supply_est_7day")
    filters_days = fba_inventory.get("filters", {}).get("days_of_supply_est_7day")
    if fountain_days:
        highlights["fountain_cover"] = f"Fountain days of cover (7d velocity): {fountain_days}."
    if filters_days:
        highlights["filters_cover"] = f"Filter days of cover (7d velocity): {filters_days}."
    return highlights


def compose():
    """Run all SC-side pullers and compose SC_Data_YYYY-MM-DD.json."""
    print("=" * 60, flush=True)
    print("Building SC_Data — running pullers in sequence", flush=True)
    print("=" * 60, flush=True)

    print("\n[1/6] ORDERS ----------------------------------------------")
    orders_out = pull_orders.pull()
    print("\n[2/6] INVENTORY -------------------------------------------")
    inv_out = pull_inventory.pull()
    print("\n[3/6] CATALOG (BSR) ---------------------------------------")
    cat_out = pull_catalog.pull()
    print("\n[4/6] BUSINESS REPORTS (SESSIONS / CVR) ------------------")
    try:
        br_out = pull_business_reports.pull()
    except Exception as br_err:
        print(f"  ⚠ Business Reports unavailable: {br_err}", flush=True)
        print("  → Continuing with null sessions/CVR data.", flush=True)
        br_out = _null_br()
    print("\n[5/6] FINANCIALS ------------------------------------------")
    fin_out = pull_financials.pull()
    print("\n[6/6] ADVERTISING API ------------------------------------")
    try:
        ads_out = pull_ads.pull()
    except Exception as ads_err:
        print(f"  ⚠ Advertising API unavailable: {ads_err}", flush=True)
        print("  → Continuing with Finances-only ad spend data.", flush=True)
        ads_out = None

    print("\n" + "=" * 60, flush=True)
    print("Composing SC_Data", flush=True)
    print("=" * 60, flush=True)

    now = datetime.now(timezone.utc)
    fba_inventory = build_fba_inventory(inv_out, cat_out, orders_out)

    sc_data = {
        "date": now.date().isoformat(),
        "period": "daily",
        "data_source": "sp_api",
        "source": (
            "SP-API pipeline: Orders + Inventory + Catalog + "
            "Reports (GET_SALES_AND_TRAFFIC_REPORT) + Finances"
        ),
        "status": "Composed automatically by amazon_api/build_sc_data.py",
        "timestamp": now.isoformat().replace("+00:00", "Z"),
        "highlights": build_highlights(orders_out, br_out, fba_inventory),
        "business_reports": br_out["business_reports"],
        "business_reports_30day": br_out["business_reports_30day"],
        "fba_orders_detail": build_fba_orders_detail(orders_out),
        "sales_today": build_sales_today(orders_out),
        "campaign_manager": build_campaign_manager(fin_out, ads_out),
        "reviews": {
            "_data_source": "pending_api",
            "_note": "Review count not yet pulled from API; existing value carried forward manually.",
            "asin": PRODUCTS["fountain"]["asin"],
        },
        "fba_inventory": fba_inventory,
        "amazon_choice": {
            "_data_source": "manual",
            "_note": "Amazon's Choice badge status requires manual verification (no public SP-API field).",
        },
        "pending_data_requests": [
            "Solicitations API: request-review status (ready but gated)",
            "RDT for PII: buyer names in fba_orders_detail",
        ],
        "_financials_summary": {
            "refunds_7d": fin_out["aggregates"]["refunds_7d"],
            "refunds_30d": fin_out["aggregates"]["refunds_30d"],
            "ads_payments_7d": fin_out["aggregates"]["ads_payments_7d"],
            "ads_payments_30d": fin_out["aggregates"]["ads_payments_30d"],
        },
    }

    # Write atomically
    SC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SC_DATA_DIR / f"SC_Data_{now.date().isoformat()}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(sc_data, f, indent=2)
    tmp_path.replace(out_path)
    print(f"\n✓ Wrote {out_path}", flush=True)

    # Also emit a normalized PPC_Analysis_<date>.json so the dashboard's ACoS
    # fallback chain (calculations.js → ppc?.summary?.overall_acos_7d) has the
    # data it expects. See amazon_api/ppc_analysis.py.
    if ads_out:
        try:
            from amazon_api.ppc_analysis import (  # noqa: E402
                build_ppc_analysis, load_ads_files, write_ppc_analysis,
            )
            ads_by_date = load_ads_files()
            payload = build_ppc_analysis(now.date(), ads_by_date)
            if payload:
                ppc_path = write_ppc_analysis(now.date(), payload)
                print(f"✓ Wrote {ppc_path}", flush=True)
        except Exception as e:
            print(f"  ⚠ PPC_Analysis write skipped: {e}", flush=True)

    return sc_data, {
        "orders": orders_out,
        "inventory": inv_out,
        "catalog": cat_out,
        "business_reports": br_out,
        "financials": fin_out,
        "ads": ads_out,
    }


if __name__ == "__main__":
    compose()
