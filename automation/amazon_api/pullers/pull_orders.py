"""Pull FBA orders from SP-API Orders for the last 30 days.

Produces an aggregation by ASIN:
    {asin: {units_7d, units_30d, revenue_7d, revenue_30d, orders_7d}}

Also produces a flat `orders_detail` list matching the existing
`SC_Data.fba_orders_detail.orders` schema (without buyer names — PII
requires RDT, deferred).

Rate limits:
    getOrders:     0.0167 req/s (1 per minute sustained, 20 burst)
    getOrderItems: 0.5 req/s (30 per minute)

Usage:
    python3 amazon_api/pullers/pull_orders.py
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make parent importable when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sp_api_client import SPAPIClient  # noqa: E402
from config import PRODUCTS, ASIN_TO_KEY, MARKETPLACE_ID, RAW_DUMP_DIR  # noqa: E402


# Pacing — conservative, stays well under official limits
ORDERS_SLEEP = 2.0  # 2s between getOrders pages (30 req/min cap)
ITEMS_SLEEP = 2.5  # 2.5s between getOrderItems (24 req/min — well under 30)


def iso_utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def list_orders(client, created_after, created_before):
    """Paginate through /orders/v0/orders."""
    orders = []
    next_token = None
    page = 0
    while True:
        page += 1
        params = {
            "MarketplaceIds": MARKETPLACE_ID,
            "CreatedAfter": iso_utc(created_after),
            "CreatedBefore": iso_utc(created_before),
            "MaxResultsPerPage": 100,
        }
        if next_token:
            params["NextToken"] = next_token
        print(f"  → getOrders page {page}...", flush=True)
        resp = client.get("/orders/v0/orders", params=params)
        if resp.status_code != 200:
            raise RuntimeError(
                f"getOrders failed: {resp.status_code} {resp.text[:300]}"
            )
        payload = resp.json().get("payload", {})
        batch = payload.get("Orders", [])
        orders.extend(batch)
        next_token = payload.get("NextToken")
        print(f"     got {len(batch)} orders (total {len(orders)})", flush=True)
        if not next_token:
            break
        time.sleep(ORDERS_SLEEP)
    return orders


def get_order_items(client, order_id):
    resp = client.get(f"/orders/v0/orders/{order_id}/orderItems")
    if resp.status_code != 200:
        raise RuntimeError(
            f"getOrderItems {order_id} failed: {resp.status_code} "
            f"{resp.text[:300]}"
        )
    return resp.json().get("payload", {}).get("OrderItems", [])


def _money(d):
    """Parse Amazon money dict {Amount, CurrencyCode} → float."""
    if not d:
        return 0.0
    try:
        return float(d.get("Amount", 0))
    except (TypeError, ValueError):
        return 0.0


def pull():
    client = SPAPIClient()
    now = datetime.now(timezone.utc)
    # Orders API requires CreatedAfter to be at least 2 minutes in the past
    created_before = now - timedelta(minutes=5)
    created_after = now - timedelta(days=30)
    cutoff_7d = now - timedelta(days=7)

    print(
        f"→ Pulling orders created between {iso_utc(created_after)} "
        f"and {iso_utc(created_before)}",
        flush=True,
    )

    orders = list_orders(client, created_after, created_before)
    print(f"✓ Fetched {len(orders)} orders", flush=True)

    # Filter to FBA shipped/shipping — skip Pending (amounts not final until shipped)
    relevant = [
        o for o in orders
        if o.get("OrderStatus") not in ("Canceled", "Pending")
    ]
    print(f"  {len(relevant)} non-cancelled/non-pending", flush=True)

    # Initialize aggregates
    agg = {
        key: {
            "asin": p["asin"],
            "sku": p["sku"],
            "units_7d": 0,
            "units_30d": 0,
            "revenue_7d": 0.0,
            "revenue_30d": 0.0,
            "orders_7d": 0,
            "orders_30d": 0,
        }
        for key, p in PRODUCTS.items()
    }
    orders_detail = []
    seen_order_7d = set()
    seen_order_30d = set()
    # Per-product order-id sets so we don't double-count an order that
    # somehow contains two line items with the same product_key.
    prod_orders_7d = {k: set() for k in PRODUCTS}
    prod_orders_30d = {k: set() for k in PRODUCTS}

    for i, order in enumerate(relevant, 1):
        order_id = order["AmazonOrderId"]
        purchase_dt = datetime.fromisoformat(
            order["PurchaseDate"].replace("Z", "+00:00")
        )
        in_7d = purchase_dt >= cutoff_7d

        print(
            f"  [{i}/{len(relevant)}] {order_id}  "
            f"{order['OrderStatus']}  {order['PurchaseDate']}",
            flush=True,
        )

        items = get_order_items(client, order_id)
        time.sleep(ITEMS_SLEEP)

        for item in items:
            asin = item.get("ASIN")
            key = ASIN_TO_KEY.get(asin)
            if key is None:
                # Not one of our tracked ASINs (shouldn't happen for this account)
                continue

            qty = int(item.get("QuantityOrdered", 0))
            revenue = _money(item.get("ItemPrice"))

            # Classify standalone vs bundle component:
            # If order has >1 item that both map to our products, treat as bundle
            order_is_bundle = (
                len(
                    [it for it in items if ASIN_TO_KEY.get(it.get("ASIN"))]
                )
                > 1
            )
            order_type = "bundle_component" if order_is_bundle else "standalone"

            agg[key]["units_30d"] += qty
            agg[key]["revenue_30d"] += revenue
            if order_id not in prod_orders_30d[key]:
                agg[key]["orders_30d"] += 1
                prod_orders_30d[key].add(order_id)
            if in_7d:
                agg[key]["units_7d"] += qty
                agg[key]["revenue_7d"] += revenue
                if order_id not in prod_orders_7d[key]:
                    agg[key]["orders_7d"] += 1
                    prod_orders_7d[key].add(order_id)

            orders_detail.append({
                "order_id": order_id,
                "date": purchase_dt.date().isoformat(),
                "time_utc": purchase_dt.strftime("%H:%M:%S"),
                "asin": asin,
                "sku": item.get("SellerSKU"),
                "product": PRODUCTS[key]["name"],
                "product_key": key,
                "quantity": qty,
                "item_subtotal": round(revenue, 2),
                "status": order.get("OrderStatus"),
                "type": order_type,
                "in_7d_window": in_7d,
            })

        seen_order_30d.add(order_id)
        if in_7d:
            seen_order_7d.add(order_id)

    # Round revenues for cleanliness
    for key in agg:
        agg[key]["revenue_7d"] = round(agg[key]["revenue_7d"], 2)
        agg[key]["revenue_30d"] = round(agg[key]["revenue_30d"], 2)

    # Totals across all products
    totals = {
        "units_7d": sum(a["units_7d"] for a in agg.values()),
        "units_30d": sum(a["units_30d"] for a in agg.values()),
        "revenue_7d": round(sum(a["revenue_7d"] for a in agg.values()), 2),
        "revenue_30d": round(sum(a["revenue_30d"] for a in agg.values()), 2),
        "orders_7d": len(seen_order_7d),
        "orders_30d": len(seen_order_30d),
    }

    result = {
        "pulled_at": iso_utc(now),
        "date_range_30d": {
            "start": iso_utc(created_after),
            "end": iso_utc(created_before),
        },
        "by_product": agg,
        "totals": totals,
        "orders_detail": orders_detail,
    }

    # Dump raw for debugging
    RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = RAW_DUMP_DIR / f"orders_{now.date().isoformat()}.json"
    with open(dump_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Raw dump: {dump_path}", flush=True)

    # Print summary
    print("\nSummary (last 7 days):")
    for key, a in agg.items():
        print(
            f"  {key:8s}  units={a['units_7d']}  revenue=${a['revenue_7d']}  "
            f"orders={a['orders_7d']}"
        )
    print(
        f"  TOTALS    units={totals['units_7d']}  "
        f"revenue=${totals['revenue_7d']}  orders={totals['orders_7d']}"
    )

    return result


if __name__ == "__main__":
    pull()
