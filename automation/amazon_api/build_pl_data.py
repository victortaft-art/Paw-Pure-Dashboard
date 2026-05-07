"""Compose PL_Data_YYYY-MM-DD.json from puller outputs + pl_config.

Takes the in-memory dicts produced by build_sc_data.compose() so we don't
re-hit the API. If called standalone, runs the full pipeline first.

Produces the PL_Data schema: inventory, pl_7day, pl_30day, daily_sales, kpis.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PRODUCTS, PL_DATA_DIR, PROJECT_ROOT  # noqa: E402


PL_CONFIG_PATH = PROJECT_ROOT.parent / "public" / "data" / "pl_data" / "pl_config.json"


def load_pl_config():
    with open(PL_CONFIG_PATH) as f:
        return json.load(f)


def per_product_pl(agg_key, units, revenue, pl_cfg):
    """Compute per-product P&L slice."""
    p = pl_cfg["products"][agg_key]
    fee_per_unit = p["amazon_total_fee"]
    cogs_per_unit = p["cogs"]
    amazon_fee = round(units * fee_per_unit, 2)
    cogs = round(units * cogs_per_unit, 2)
    gross_profit = round(revenue - amazon_fee - cogs, 2)
    margin_pct = round((gross_profit / revenue) * 100, 2) if revenue > 0 else 0.0
    return {
        "units": units,
        "revenue": round(revenue, 2),
        "amazon_fee": amazon_fee,
        "_fee_calc": f"{units} × ${fee_per_unit}",
        "cogs": cogs,
        "_cogs_calc": f"{units} × ${cogs_per_unit}",
        "gross_profit": gross_profit,
        "margin_pct": margin_pct,
    }


def totals_pl(by_product, ad_spend):
    units = sum(p["units"] for p in by_product.values())
    revenue = round(sum(p["revenue"] for p in by_product.values()), 2)
    amazon_fee = round(sum(p["amazon_fee"] for p in by_product.values()), 2)
    cogs = round(sum(p["cogs"] for p in by_product.values()), 2)
    gross_profit = round(revenue - amazon_fee - cogs, 2)
    gross_margin_pct = round((gross_profit / revenue) * 100, 2) if revenue > 0 else 0.0
    true_contrib = round(gross_profit - (ad_spend or 0), 2) if ad_spend is not None else None
    contrib_pct = (
        round((true_contrib / revenue) * 100, 2)
        if (true_contrib is not None and revenue > 0) else None
    )
    return {
        "units": units,
        "revenue": revenue,
        "amazon_fee": amazon_fee,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "gross_margin_pct": gross_margin_pct,
        "ad_spend_est": round(ad_spend, 2) if ad_spend is not None else None,
        "true_contribution_margin_est": true_contrib,
        "contribution_margin_pct_est": contrib_pct,
    }


def build_daily_sales(orders_detail, days=30):
    """Per-day revenue + units + order list (last `days` days)."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)

    # Seed all days so we have rows for zero-sales days
    by_day = {
        (start + timedelta(days=i)).isoformat(): {"revenue": 0.0, "units": 0, "orders": []}
        for i in range(days)
    }

    for o in orders_detail:
        d = o["date"]
        if d not in by_day:
            continue
        by_day[d]["revenue"] += o["item_subtotal"]
        by_day[d]["units"] += o["quantity"]
        # Compact order line for dashboard display
        by_day[d]["orders"].append(
            f"{o['order_id']} {o['product_key']} ${o['item_subtotal']}"
        )

    days_list = []
    for d in sorted(by_day.keys()):
        by_day[d]["revenue"] = round(by_day[d]["revenue"], 2)
        days_list.append({"date": d, **by_day[d]})

    return {
        "_data_source": "sp_api_orders",
        "_source": "Aggregated from /orders/v0/orders response",
        "days": days_list,
    }


def build_inventory_section(fba_inventory, pl_cfg):
    out = {}
    for key in PRODUCTS:
        row = fba_inventory.get(key, {}) or {}
        cfg = pl_cfg["products"].get(key, {})
        fba_available = row.get("fba_available")
        inbound = row.get("inbound") or 0
        total_stock = (fba_available or 0) + (inbound or 0) if fba_available is not None else None

        lead_time = (cfg.get("supply_chain") or {}).get("total_lead_time_days", 90)
        safety = cfg.get("safety_stock_days", 30)
        days_7d = row.get("days_of_supply_est_7day")
        days_30d = row.get("days_of_supply_est_30day")

        status = None
        reorder_needed = None
        if days_30d is not None:
            buffer = lead_time + safety
            if days_30d < 14:
                status = "CRITICAL"
                reorder_needed = True
            elif days_30d < buffer:
                status = "REORDER"
                reorder_needed = True
            elif days_30d > 180:
                status = "OVERSTOCKED"
                reorder_needed = False
            else:
                status = "HEALTHY"
                reorder_needed = False

        out[key] = {
            "asin": row.get("asin") or PRODUCTS[key]["asin"],
            "fba_available": fba_available,
            "fba_inbound": inbound,
            "total_stock": total_stock,
            "daily_velocity_7day": row.get("daily_velocity_7day"),
            "daily_velocity_30day": row.get("daily_velocity_30day"),
            "days_of_cover_7day": days_7d,
            "days_of_cover_30day": days_30d,
            "status": status,
            "reorder_needed": reorder_needed,
            "bsr": row.get("bsr_pet_supplies"),
            "bsr_subcategory": row.get("bsr_subcategory"),
        }
    return out


def build_kpis(pl_7d, pl_30d, inventory_section, br_7d, financials_agg):
    pl7t = pl_7d["totals"]
    pl30t = pl_30d["totals"]
    filter_units_30 = pl_30d.get("filters", {}).get("units", 0)
    fountain_units_30 = pl_30d.get("fountain", {}).get("units", 0)
    razor_ratio = round(filter_units_30 / fountain_units_30, 2) if fountain_units_30 else None

    return {
        "revenue_7d": pl7t["revenue"],
        "revenue_30d": pl30t["revenue"],
        "units_7d": pl7t["units"],
        "units_30d": pl30t["units"],
        "gross_margin_7d_pct": pl7t["gross_margin_pct"],
        "gross_margin_30d_pct": pl30t["gross_margin_pct"],
        "contribution_margin_7d_est": pl7t["true_contribution_margin_est"],
        "contribution_margin_pct_est": pl7t["contribution_margin_pct_est"],
        "sessions_7d": br_7d.get("sessions_total"),
        "sessions_per_day_7d": round(br_7d.get("sessions_total", 0) / 7, 1) if br_7d.get("sessions_total") else None,
        "cvr_7d_pct": br_7d.get("cvr_percent"),
        "days_of_cover_fountain_30d": inventory_section.get("fountain", {}).get("days_of_cover_30day"),
        "days_of_cover_fountain_7d": inventory_section.get("fountain", {}).get("days_of_cover_7day"),
        "days_of_cover_filters": inventory_section.get("filters", {}).get("days_of_cover_30day"),
        "razor_blade_ratio_30d": razor_ratio,
        "ppc_spend_7d": pl7t["ad_spend_est"],
        "ppc_spend_30d": pl30t["ad_spend_est"],
        "refunds_7d": financials_agg.get("refunds_7d"),
        "refunds_30d": financials_agg.get("refunds_30d"),
    }


def compose(puller_outputs):
    """Compose PL_Data from in-memory puller outputs (from build_sc_data.compose)."""
    now = datetime.now(timezone.utc)
    pl_cfg = load_pl_config()

    orders = puller_outputs["orders"]
    business_reports = puller_outputs["business_reports"]
    financials = puller_outputs["financials"]

    agg = orders["by_product"]

    # Ad spend from Finances API (absolute value — charges are negative)
    ads_7d = abs(financials["aggregates"].get("ads_payments_7d", 0)) or None
    ads_30d = abs(financials["aggregates"].get("ads_payments_30d", 0)) or None

    # Per-product 7d and 30d
    pl_7d = {k: per_product_pl(k, agg[k]["units_7d"], agg[k]["revenue_7d"], pl_cfg) for k in PRODUCTS}
    pl_30d = {k: per_product_pl(k, agg[k]["units_30d"], agg[k]["revenue_30d"], pl_cfg) for k in PRODUCTS}

    pl_7d["totals"] = totals_pl(pl_7d, ads_7d)
    pl_30d["totals"] = totals_pl(pl_30d, ads_30d)

    # SC_Data's fba_inventory is in the composed sc_data dict; get it back
    # by re-running build_fba_inventory here — but cleaner: build once here.
    from build_sc_data import build_fba_inventory
    fba_inventory = build_fba_inventory(
        puller_outputs["inventory"],
        puller_outputs["catalog"],
        orders,
    )
    inventory_section = build_inventory_section(fba_inventory, pl_cfg)

    daily_sales = build_daily_sales(orders["orders_detail"], days=31)

    pl_data = {
        "date": now.date().isoformat(),
        "period": "daily",
        "data_source": "sp_api",
        "config_last_updated": pl_cfg.get("_last_updated"),
        "_fee_note": "Fees are computed from pl_config.json per-unit schedule. Real settlement fees available in Finances dump (amazon_api/data/raw/).",
        "sc_data_source": "sp_api_composite",
        "inventory": inventory_section,
        "pl_7day": pl_7d,
        "pl_30day": pl_30d,
        "daily_sales": daily_sales,
        "kpis": build_kpis(
            pl_7d, pl_30d, inventory_section,
            business_reports["business_reports"], financials["aggregates"]
        ),
    }

    PL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PL_DATA_DIR / f"PL_Data_{now.date().isoformat()}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    with open(tmp_path, "w") as f:
        json.dump(pl_data, f, indent=2)
    tmp_path.replace(out_path)
    print(f"\n✓ Wrote {out_path}", flush=True)

    return pl_data


if __name__ == "__main__":
    # Standalone: run the full pipeline first
    from build_sc_data import compose as compose_sc
    _, puller_outputs = compose_sc()
    compose(puller_outputs)
