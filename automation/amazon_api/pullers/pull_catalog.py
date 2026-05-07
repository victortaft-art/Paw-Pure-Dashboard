"""Pull catalog metadata (BSR, category rank, title) from SP-API Catalog.

Uses /catalog/2022-04-01/items/{asin} with includedData=salesRanks,attributes.
Produces per-ASIN: best_seller_rank (overall + category), title.

Feeds `SC_Data.fba_inventory[product].bsr_pet_supplies` + related BSR fields.

Rate limits:
    /catalog/2022-04-01/items/{asin}: 2 req/s, burst 2
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sp_api_client import SPAPIClient  # noqa: E402
from config import PRODUCTS, MARKETPLACE_ID, RAW_DUMP_DIR  # noqa: E402


SLEEP = 1.0


def get_catalog_item(client, asin):
    params = {
        "marketplaceIds": MARKETPLACE_ID,
        "includedData": "salesRanks,attributes,summaries",
    }
    resp = client.get(f"/catalog/2022-04-01/items/{asin}", params=params)
    if resp.status_code != 200:
        raise RuntimeError(
            f"getCatalogItem {asin} failed: {resp.status_code} "
            f"{resp.text[:300]}"
        )
    return resp.json()


def extract_bsr(item, marketplace_id):
    """Parse salesRanks into a flat dict.

    Returns:
        {
            "overall": {"rank": N, "category": "Pet Supplies"},
            "sub": [{"rank": N, "category": "..."} ...]
        }
    """
    sales_ranks = item.get("salesRanks") or []
    mp = None
    for s in sales_ranks:
        if s.get("marketplaceId") == marketplace_id:
            mp = s
            break
    if not mp:
        return {"overall": None, "sub": [], "display_categories": []}

    classification = mp.get("classificationRanks", []) or []
    display = mp.get("displayGroupRanks", []) or []

    overall = None
    sub = []
    # `classificationRanks` typically includes the main category (Pet Supplies)
    # as the first/lowest-numbered entry.
    for r in classification:
        entry = {
            "rank": r.get("rank"),
            "category": r.get("title"),
            "link": r.get("link"),
        }
        if overall is None:
            overall = entry
        else:
            sub.append(entry)

    display_cats = [
        {"rank": d.get("rank"), "category": d.get("title")}
        for d in display
    ]

    return {
        "overall": overall,
        "sub": sub,
        "display_categories": display_cats,
    }


def pull():
    client = SPAPIClient()
    now = datetime.now(timezone.utc)

    print("→ Pulling catalog metadata (BSR)", flush=True)
    catalog_data = {}
    for key, prod in PRODUCTS.items():
        asin = prod["asin"]
        print(f"  [{key}] {asin}...", flush=True)
        try:
            item = get_catalog_item(client, asin)
        except RuntimeError as e:
            print(f"     ⚠ {e}", flush=True)
            catalog_data[key] = {"asin": asin, "error": str(e)[:200]}
            time.sleep(SLEEP)
            continue

        bsr = extract_bsr(item, MARKETPLACE_ID)

        # Title from summaries
        summaries = item.get("summaries") or []
        title = None
        brand = None
        for s in summaries:
            if s.get("marketplaceId") == MARKETPLACE_ID:
                title = s.get("itemName")
                brand = s.get("brand")
                break

        catalog_data[key] = {
            "asin": asin,
            "title": title,
            "brand": brand,
            "bsr_overall": bsr["overall"],
            "bsr_subcategories": bsr["sub"],
            "display_group_ranks": bsr["display_categories"],
        }

        rank = (bsr["overall"] or {}).get("rank")
        cat = (bsr["overall"] or {}).get("category")
        print(f"     BSR: #{rank} in {cat}", flush=True)
        time.sleep(SLEEP)

    result = {
        "pulled_at": now.isoformat().replace("+00:00", "Z"),
        "catalog": catalog_data,
    }

    RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = RAW_DUMP_DIR / f"catalog_{now.date().isoformat()}.json"
    with open(dump_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Raw dump: {dump_path}", flush=True)

    return result


if __name__ == "__main__":
    pull()
