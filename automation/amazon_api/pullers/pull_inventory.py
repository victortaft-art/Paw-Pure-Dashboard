"""Pull FBA inventory summaries from SP-API.

Produces a dict matching the existing `SC_Data.fba_inventory` schema
(per-product: fba_available, inbound, reserved).

Daily velocity / days-of-supply are computed separately in
`build_sc_data.py` by combining this output with the orders puller.

Rate limits:
    /fba/inventory/v1/summaries: 2 req/s, burst 2
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sp_api_client import SPAPIClient  # noqa: E402
from config import PRODUCTS, MARKETPLACE_ID, RAW_DUMP_DIR  # noqa: E402


SLEEP = 1.0  # 1 req/s — well under 2 req/s limit


def get_inventory_summaries(client):
    """Fetch all FBA inventory summaries (paginated)."""
    summaries = []
    next_token = None
    page = 0
    while True:
        page += 1
        params = {
            "granularityType": "Marketplace",
            "granularityId": MARKETPLACE_ID,
            "marketplaceIds": MARKETPLACE_ID,
            "details": "true",
        }
        if next_token:
            params["nextToken"] = next_token
        print(f"  → getInventorySummaries page {page}...", flush=True)
        resp = client.get("/fba/inventory/v1/summaries", params=params)
        if resp.status_code != 200:
            raise RuntimeError(
                f"getInventorySummaries failed: {resp.status_code} "
                f"{resp.text[:300]}"
            )
        payload = resp.json().get("payload", {})
        batch = payload.get("inventorySummaries", [])
        summaries.extend(batch)
        # Pagination token is in payload.nextToken (sometimes in top-level .pagination)
        pag = resp.json().get("pagination", {}) or {}
        next_token = pag.get("nextToken") or payload.get("nextToken")
        print(f"     got {len(batch)} summaries (total {len(summaries)})", flush=True)
        if not next_token:
            break
        time.sleep(SLEEP)
    return summaries


def pull():
    client = SPAPIClient()
    now = datetime.now(timezone.utc)

    print("→ Pulling FBA inventory summaries", flush=True)
    summaries = get_inventory_summaries(client)
    print(f"✓ Fetched {len(summaries)} summaries", flush=True)

    # Index by ASIN for lookup
    by_asin = {}
    for s in summaries:
        asin = s.get("asin")
        if not asin:
            continue
        by_asin[asin] = s

    # Build output matching fba_inventory schema
    inventory = {
        "scraped_at": now.isoformat().replace("+00:00", "Z"),
        "data_source": "sp_api",
        "_source": "/fba/inventory/v1/summaries",
    }

    for key, prod in PRODUCTS.items():
        asin = prod["asin"]
        s = by_asin.get(asin)
        if not s:
            # Bundle is virtual — may not have FBA inventory
            inventory[key] = {
                "asin": asin,
                "sku": prod.get("sku"),
                "fba_available": None,
                "inbound": None,
                "reserved": None,
                "_note": "No inventory summary returned for this ASIN",
            }
            continue

        details = s.get("inventoryDetails", {}) or {}
        fulfillable = details.get("fulfillableQuantity", 0)
        inbound_working = details.get("inboundWorkingQuantity", 0)
        inbound_shipped = details.get("inboundShippedQuantity", 0)
        inbound_receiving = details.get("inboundReceivingQuantity", 0)
        inbound_total = inbound_working + inbound_shipped + inbound_receiving
        reserved = (details.get("reservedQuantity", {}) or {}).get(
            "totalReservedQuantity", 0
        )
        total_supply = s.get("totalSupplyQuantity", 0)

        inventory[key] = {
            "asin": asin,
            "sku": s.get("sellerSku") or prod.get("sku"),
            "fnsku": s.get("fnSku"),
            "product_name": s.get("productName"),
            "condition": s.get("condition"),
            "fba_available": fulfillable,
            "inbound": inbound_total,
            "inbound_working": inbound_working,
            "inbound_shipped": inbound_shipped,
            "inbound_receiving": inbound_receiving,
            "reserved": reserved,
            "total_supply": total_supply,
            "price": prod.get("price"),
            "total_fee_per_unit": prod.get("amazon_fee"),
            "last_updated_time": s.get("lastUpdatedTime"),
        }

    result = {
        "pulled_at": now.isoformat().replace("+00:00", "Z"),
        "by_product": {k: v for k, v in inventory.items() if k in PRODUCTS},
        "fba_inventory": inventory,
    }

    # Raw dump
    RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = RAW_DUMP_DIR / f"inventory_{now.date().isoformat()}.json"
    with open(dump_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Raw dump: {dump_path}", flush=True)

    # Summary
    print("\nInventory summary:")
    for key in PRODUCTS:
        inv = inventory[key]
        print(
            f"  {key:8s}  available={inv['fba_available']}  "
            f"inbound={inv['inbound']}  reserved={inv['reserved']}"
        )

    return result


if __name__ == "__main__":
    pull()
