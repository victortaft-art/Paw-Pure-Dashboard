"""Pull settlement / financial events from SP-API Finances.

Uses /finances/v0/financialEvents to fetch ShipmentEvents, RefundEvents,
ServiceFeeEvents, etc. Aggregates 7d + 30d fee totals per ASIN so the P&L
can use real Amazon fees (referral + FBA + storage + other) instead of
the per-unit estimates in `pl_config.json`.

Also extracts net payout amounts for cash-runway projection.

Rate limits:
    listFinancialEvents: 0.5 req/s, burst 30
"""
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sp_api_client import SPAPIClient  # noqa: E402
from config import PRODUCTS, ASIN_TO_KEY, SKU_TO_KEY, RAW_DUMP_DIR  # noqa: E402


SLEEP = 2.5


def list_financial_events(client, posted_after, posted_before):
    """Paginate through /finances/v0/financialEvents."""
    events = {
        "ShipmentEventList": [],
        "RefundEventList": [],
        "GuaranteeClaimEventList": [],
        "ChargebackEventList": [],
        "ServiceFeeEventList": [],
        "AdjustmentEventList": [],
        "SAFETReimbursementEventList": [],
        "ProductAdsPaymentEventList": [],
    }
    next_token = None
    page = 0
    while True:
        page += 1
        params = {
            "PostedAfter": posted_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "PostedBefore": posted_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "MaxResultsPerPage": 100,
        }
        if next_token:
            params["NextToken"] = next_token
        print(f"  → listFinancialEvents page {page}...", flush=True)
        resp = client.get("/finances/v0/financialEvents", params=params)
        if resp.status_code != 200:
            raise RuntimeError(
                f"listFinancialEvents failed: {resp.status_code} "
                f"{resp.text[:300]}"
            )
        payload = resp.json().get("payload", {})
        fin_events = payload.get("FinancialEvents", {}) or {}
        total = 0
        for k in events:
            batch = fin_events.get(k, []) or []
            events[k].extend(batch)
            total += len(batch)
        print(f"     got {total} events this page", flush=True)
        next_token = payload.get("NextToken")
        if not next_token:
            break
        time.sleep(SLEEP)
    return events


def _money(d):
    if not d:
        return 0.0
    try:
        return float(d.get("CurrencyAmount", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def aggregate(events, cutoff_7d):
    """Aggregate ShipmentEvent fees by ASIN for 7d + 30d."""
    # Each shipment event has ShipmentItemList; each item has ItemChargeList,
    # ItemFeeList, PromotionList, + optional ItemChargeAdjustmentList etc.

    def _new_slot():
        return {
            "principal": 0.0,
            "tax": 0.0,
            "shipping": 0.0,
            "referral_fee": 0.0,
            "fba_fee": 0.0,
            "other_fees": 0.0,
            "promotions": 0.0,
            "units": 0,
            "events": 0,
        }

    per_asin_7d = defaultdict(_new_slot)
    per_asin_30d = defaultdict(_new_slot)
    refunds_30d = 0.0
    refunds_7d = 0.0
    ads_payments_30d = 0.0
    ads_payments_7d = 0.0
    adjustments_30d = 0.0

    for ev in events.get("ShipmentEventList", []):
        posted = ev.get("PostedDate")
        if not posted:
            continue
        posted_dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        in_7d = posted_dt >= cutoff_7d

        for item in ev.get("ShipmentItemList", []) or []:
            sku = item.get("SellerSKU")
            asin = None
            # Amazon returns SKU in shipment events; map to ASIN via config
            key = SKU_TO_KEY.get(sku) if sku else None
            if key:
                asin = PRODUCTS[key]["asin"]
            if asin is None:
                asin = "_unknown"

            slot_30 = per_asin_30d[asin]
            slot_7 = per_asin_7d[asin] if in_7d else None

            qty = int(item.get("QuantityShipped", 0) or 0)
            slot_30["units"] += qty
            slot_30["events"] += 1
            if slot_7 is not None:
                slot_7["units"] += qty
                slot_7["events"] += 1

            for charge in item.get("ItemChargeList", []) or []:
                ctype = charge.get("ChargeType", "")
                amt = _money(charge.get("ChargeAmount"))
                if ctype == "Principal":
                    slot_30["principal"] += amt
                    if slot_7 is not None:
                        slot_7["principal"] += amt
                elif ctype == "Tax":
                    slot_30["tax"] += amt
                    if slot_7 is not None:
                        slot_7["tax"] += amt
                elif "Shipping" in ctype:
                    slot_30["shipping"] += amt
                    if slot_7 is not None:
                        slot_7["shipping"] += amt

            for fee in item.get("ItemFeeList", []) or []:
                ftype = fee.get("FeeType", "")
                amt = _money(fee.get("FeeAmount"))  # usually negative
                if ftype == "Commission":
                    slot_30["referral_fee"] += amt
                    if slot_7 is not None:
                        slot_7["referral_fee"] += amt
                elif ftype in ("FBAPerUnitFulfillmentFee", "FBAPerOrderFulfillmentFee"):
                    slot_30["fba_fee"] += amt
                    if slot_7 is not None:
                        slot_7["fba_fee"] += amt
                else:
                    slot_30["other_fees"] += amt
                    if slot_7 is not None:
                        slot_7["other_fees"] += amt

            for promo in item.get("PromotionList", []) or []:
                amt = _money(promo.get("PromotionAmount"))
                slot_30["promotions"] += amt
                if slot_7 is not None:
                    slot_7["promotions"] += amt

    # Refunds
    for ev in events.get("RefundEventList", []):
        posted = ev.get("PostedDate")
        if not posted:
            continue
        posted_dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        for item in ev.get("ShipmentItemAdjustmentList", []) or []:
            for charge in item.get("ItemChargeAdjustmentList", []) or []:
                amt = _money(charge.get("ChargeAmount"))
                refunds_30d += amt
                if posted_dt >= cutoff_7d:
                    refunds_7d += amt

    # Ads payments (sponsored products etc.)
    for ev in events.get("ProductAdsPaymentEventList", []):
        posted = ev.get("postedDate") or ev.get("PostedDate")
        if not posted:
            continue
        posted_dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        amt = _money(ev.get("TransactionValue") or ev.get("transactionValue"))
        ads_payments_30d += amt
        if posted_dt >= cutoff_7d:
            ads_payments_7d += amt

    # Adjustments (reimbursements etc.)
    for ev in events.get("AdjustmentEventList", []):
        amt = _money(ev.get("AdjustmentAmount"))
        adjustments_30d += amt

    # Round everything
    for asin_map in (per_asin_7d, per_asin_30d):
        for a, slot in asin_map.items():
            for k, v in slot.items():
                if isinstance(v, float):
                    slot[k] = round(v, 2)

    return {
        "per_asin_7d": dict(per_asin_7d),
        "per_asin_30d": dict(per_asin_30d),
        "refunds_7d": round(refunds_7d, 2),
        "refunds_30d": round(refunds_30d, 2),
        "ads_payments_7d": round(ads_payments_7d, 2),
        "ads_payments_30d": round(ads_payments_30d, 2),
        "adjustments_30d": round(adjustments_30d, 2),
    }


def pull():
    client = SPAPIClient()
    now = datetime.now(timezone.utc)
    posted_before = now - timedelta(minutes=5)  # API disallows future / near-now
    posted_after = now - timedelta(days=30)
    cutoff_7d = now - timedelta(days=7)

    print(
        f"→ Pulling financial events {posted_after.date()} → {posted_before.date()}",
        flush=True,
    )
    events = list_financial_events(client, posted_after, posted_before)
    counts = {k: len(v) for k, v in events.items()}
    print(f"✓ Event counts: {counts}", flush=True)

    agg = aggregate(events, cutoff_7d)

    result = {
        "pulled_at": now.isoformat().replace("+00:00", "Z"),
        "window_30d": {
            "start": posted_after.isoformat().replace("+00:00", "Z"),
            "end": posted_before.isoformat().replace("+00:00", "Z"),
        },
        "aggregates": agg,
        "raw_counts": counts,
    }

    RAW_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    dump_path = RAW_DUMP_DIR / f"financials_{now.date().isoformat()}.json"
    with open(dump_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Raw dump: {dump_path}", flush=True)

    print("\nPer-ASIN 30d fees:")
    for asin, slot in agg["per_asin_30d"].items():
        key = ASIN_TO_KEY.get(asin, "?" if asin != "_unknown" else "unknown")
        print(
            f"  {key:8s} {asin}  units={slot['units']}  "
            f"principal=${slot['principal']}  "
            f"referral=${slot['referral_fee']}  fba=${slot['fba_fee']}"
        )
    print(
        f"\n  Refunds 7d/30d: ${agg['refunds_7d']} / ${agg['refunds_30d']}"
    )
    print(
        f"  Ads charges 7d/30d: ${agg['ads_payments_7d']} / ${agg['ads_payments_30d']}"
    )

    return result


if __name__ == "__main__":
    pull()
