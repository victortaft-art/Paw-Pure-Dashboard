"""Append EXP-051..055 to active_tracker.json and experiment_log.json.

Driven by the Apr 29 Cerebro pull + 6-month rank history insights:
  - EXP-051: Filter cross-sell campaign launch (B0FWXJ1GKT) — highest ROI move
  - EXP-052: Add 3 cat KWs to Manual Keywords Campaign (rank-history-validated)
  - EXP-053: Bulk-add 26 Cerebro negatives to Manual Keywords Campaign
  - EXP-054: Filter listing audit + refresh (images, A+, copy)
  - EXP-055: Bundle listing audit + refresh (images, A+, copy)

Also bumps `today`, `_last_updated`, and freshness markers.
"""
from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKER_PATHS = [
    ROOT / "dashboard" / "public" / "data" / "active_tracker.json",
    ROOT / "active_tracker.json",
]
LOG_PATHS = [
    ROOT / "experiment_log.json",
    ROOT / "dashboard" / "public" / "data" / "experiment_log.json",
]

TODAY = date(2026, 4, 29)
DECISION = date(2026, 5, 6)  # 7-day verify
TODAY_S = TODAY.isoformat()
DECISION_S = DECISION.isoformat()


# ---------------------------------------------------------------------------
# New experiments
# ---------------------------------------------------------------------------

NEW_BACKLOG = [
    {
        "id": "EXP-051",
        "title": "Launch Filters_Manual campaign — first-ever PPC on B0FWXJ1GKT",
        "scheduled_date": TODAY_S,
        "decision_date": DECISION_S,
        "priority": "CRITICAL",
        "growth_metric": "Filter unit sales",
        "listing": "filters",
        "assumption": "Filter cross-sell at 45% margin can sustain higher ACoS than fountain (9% margin). Top-SV filter terms (cat water fountain filter SV 28K, cat fountain filter SV 18K) have 0-1 competitors in top 30 organic — uncontested PPC space.",
        "rationale": "Filter B0FWXJ1GKT has had $0 in PPC spend ever. Cerebro Apr 28 reveals 4 high-SV filter KWs with low competitor density. Razor-blade margin economics + uncontested terms = highest expected ROI per dollar in the entire portfolio.",
        "expected_change": "Filter monthly unit sales ~50% lift over current organic-only baseline. Hard ACoS gate at 30% (vs 33.5% breakeven on fountain — filters have headroom).",
        "execution_steps": [
            "Seller Central > Create Campaign > Sponsored Products > Manual targeting > Continue",
            "Campaign name: SP_Filters_Manual_2026-04-29",
            "Daily budget: $5.00",
            "Bidding strategy: Dynamic bids — down only",
            "Placement: Top of search 0%, Product pages 0%",
            "Ad group: Filters_Exact, Default bid: $0.80",
            "Add product: B0FWXJ1GKT",
            "Add keywords (EXACT match):",
            "  cat water fountain filter — $0.80",
            "  cat fountain filter — $0.80",
            "  veken water fountain filters — $0.80",
            "  petlibro water fountain filter — $0.65",
            "Launch campaign. Monitor daily for first 3 days; verify ACoS < 30% by 2026-05-06."
        ],
        "success_criteria": {
            "metric": "filter_acos_7d",
            "baseline": None,
            "target": 30.0,
            "unit": "%",
            "direction": "down",
            "how_to_measure": "Ads API filter campaign report — pull on 2026-05-06"
        }
    },
    {
        "id": "EXP-052",
        "title": "Add 3 momentum-validated cat KWs to Manual Keywords Campaign",
        "scheduled_date": TODAY_S,
        "decision_date": DECISION_S,
        "priority": "HIGH",
        "growth_metric": "Cat fountain CTR + indexing",
        "listing": "fountain",
        "assumption": "6-month rank history (KT export Apr 29) shows we're GAINING organic rank on `cat water fountain stainless steel wireless` (#147 → #86, +61), `rechargeable cat water fountain` (#255 → #166, +89), and `kitty spout` is brand-search arbitrage. Bidding here amplifies a winning algorithmic signal.",
        "rationale": "Per the lessons file (Apr 29): bid HIGHER on KWs we're already gaining organic rank on (algo reinforcement); avoid pouring money into broad terms where we're losing ground. These 3 KWs satisfy that rule. Replaces the original `stainless steel cat water fountain` plan, which the rank history invalidates.",
        "expected_change": "3 new exact-match KWs convert at 2-3x current portfolio CVR because they're niche-specific. Adds ~$3-5/day spend, expected to recover via 1-2 incremental orders/week.",
        "execution_steps": [
            "Seller Central > Sponsored Products > Manual Keywords Campaign > add keywords",
            "Add (EXACT match):",
            "  cat water fountain stainless steel wireless — bid $1.30",
            "  rechargeable cat water fountain — bid $1.00",
            "  kitty spout cat water fountain — bid $1.20",
            "Save. First ACoS read on 2026-05-02; verdict on 2026-05-06."
        ],
        "success_criteria": {
            "metric": "new_kw_orders_7d",
            "baseline": 0,
            "target": 3,
            "unit": "orders",
            "direction": "up",
            "how_to_measure": "Ads API SP Targeting report — count attributed orders for the 3 new KWs"
        }
    },
    {
        "id": "EXP-053",
        "title": "Bulk-negate 26 wasted-spend terms flagged by Cerebro",
        "scheduled_date": TODAY_S,
        "decision_date": DECISION_S,
        "priority": "HIGH",
        "growth_metric": "Wasted spend",
        "listing": "fountain",
        "assumption": "Cerebro Apr 28 flagged 26 KWs containing 'ceramic', 'no filter', 'pumpless', etc — wrong product attribute matches. Adding as negatives saves PPC dollars on clicks that will not convert.",
        "rationale": "We are paying for impressions/clicks on KWs that semantically can't sell our product (e.g. 'ceramic cat water fountain' — we're stainless). Per lessons (Apr 18 / EXP-024): every negative we should have added but didn't is a daily leak.",
        "expected_change": "Daily wasted spend down ~$2-4. ACoS improvement of 3-5pp portfolio-wide.",
        "execution_steps": [
            "Open dashboard > Strategy > H10 Opportunities panel > Negatives filter",
            "Click 'Add as negatives' button — routes to experiments draft flow with all 26 terms",
            "OR direct: Seller Central > Manual Keywords Campaign > Negative Keywords > paste in the 26 terms (full list in cerebro_opportunities_2026-04-28.json under tag=negative)",
            "Save. Effect compounds daily — verify wasted spend reduction on 2026-05-06."
        ],
        "success_criteria": {
            "metric": "wasted_spend_daily",
            "baseline": 4.0,
            "target": 1.0,
            "unit": "$",
            "direction": "down",
            "how_to_measure": "Dashboard Strategy > Wasted Spend (7d) block — should drop"
        }
    },
    {
        "id": "EXP-054",
        "title": "Filter listing audit + refresh (B0FWXJ1GKT) — images, A+, copy",
        "scheduled_date": "2026-04-30",
        "decision_date": "2026-05-13",
        "priority": "HIGH",
        "growth_metric": "Filter CVR",
        "listing": "filters",
        "assumption": "Filter listing currently has weak images and minimal A+ content. With Filters_Manual campaign launching Apr 29, every dollar of new traffic will convert poorly until the listing matches buyer intent (compatibility, freshness, multi-pack value).",
        "rationale": "Filter is 45% margin and razor-blade economics depend on it converting. Driving PPC to a weak listing is throwing money into a sieve. Listing improvements compound with PPC traffic — get them shipping in parallel.",
        "expected_change": "Filter session-to-order CVR from current baseline (TBD — needs SP-API session pull) to +30%. A+ + better images = better organic indexing too.",
        "execution_steps": [
            "Step 1 (Claude): Live scrape of B0FWXJ1GKT via Chrome — capture current state of: hero image, image carousel (count + content), bullets, A+ modules, comparison table",
            "Step 2 (Claude): Audit against top-converting filter listings (Veken filter, FEELNEEDY filter) — identify gaps in visual hierarchy, social proof, compatibility messaging",
            "Step 3 (Victor): Decide on 3-5 image refreshes (ranked by impact)",
            "Step 4 (Victor): Update via Seller Central > Manage Inventory > Edit listing",
            "Step 5: Verify rank impact in next Sunday's KT pull"
        ],
        "success_criteria": {
            "metric": "filter_listing_cvr",
            "baseline": None,
            "target": "+30%",
            "unit": "%",
            "direction": "up",
            "how_to_measure": "SP-API Business Reports — sessions/units conversion for B0FWXJ1GKT"
        }
    },
    {
        "id": "EXP-055",
        "title": "Bundle listing audit + refresh — images, A+, copy",
        "scheduled_date": "2026-05-01",
        "decision_date": "2026-05-15",
        "priority": "MEDIUM",
        "growth_metric": "Bundle attach rate",
        "listing": "bundle",
        "assumption": "Bundle listing has weak images / A+ / copy. Bundle is at 43% margin and was identified as 'unlaunched' in KW_Data Apr 26. PPC won't be effective without first ensuring the listing converts.",
        "rationale": "Same logic as EXP-054 — listing fundamentals must match marketing intent before paid traffic can compound. Bundle has the highest margin among our SKUs; getting its conversion right multiplies every other PPC effort.",
        "expected_change": "Bundle attach rate (% of fountain orders that include bundle) from current baseline to +25%. Bundle SKU sessions/orders ratio improves.",
        "execution_steps": [
            "Step 1 (Claude): Live scrape of bundle ASIN via Chrome — confirm ASIN first, then capture full listing state",
            "Step 2 (Claude): Compare against top-rated bundle competitors in cat fountain category (any competitor selling fountain+filter combo)",
            "Step 3 (Victor): Confirm bundle ASIN and provide listing access",
            "Step 4 (Victor): Update images / A+ / bullets based on audit",
            "Step 5: First impact reading on 2026-05-15"
        ],
        "success_criteria": {
            "metric": "bundle_attach_rate",
            "baseline": None,
            "target": "+25%",
            "unit": "%",
            "direction": "up",
            "how_to_measure": "SP-API Orders — bundle SKU orders / fountain SKU orders"
        }
    }
]

# Pointer-only entries for weekly_strategy[0].experiments
NEW_WEEK_POINTERS = [
    {"id": "EXP-051", "scheduled_date": TODAY_S, "title": "Launch Filters_Manual campaign", "status": "TODO"},
    {"id": "EXP-052", "scheduled_date": TODAY_S, "title": "Add 3 momentum-validated cat KWs", "status": "TODO"},
    {"id": "EXP-053", "scheduled_date": TODAY_S, "title": "Bulk-negate 26 wasted-spend terms", "status": "TODO"},
    {"id": "EXP-054", "scheduled_date": "2026-04-30", "title": "Filter listing audit + refresh", "status": "QUEUED"},
    {"id": "EXP-055", "scheduled_date": "2026-05-01", "title": "Bundle listing audit + refresh", "status": "QUEUED"},
]


# ---------------------------------------------------------------------------
# Active tracker update
# ---------------------------------------------------------------------------

def update_tracker(path: Path) -> None:
    if not path.exists():
        print(f"  skip (missing): {path}")
        return
    with path.open() as f:
        d = json.load(f)

    d["today"] = TODAY_S
    d["generated"] = TODAY_S

    # Append to backlog (de-duped by id)
    bl_ids = {b["id"] for b in d.get("backlog", [])}
    for entry in NEW_BACKLOG:
        if entry["id"] not in bl_ids:
            d.setdefault("backlog", []).append(entry)

    # Append pointers to current week (weekly_strategy[0])
    if d.get("weekly_strategy"):
        wk = d["weekly_strategy"][0]
        existing_ids = {e["id"] for e in wk.get("experiments", [])}
        for ptr in NEW_WEEK_POINTERS:
            if ptr["id"] not in existing_ids:
                wk["experiments"].append(ptr)

    # Update freshness
    d.setdefault("data_freshness", {})
    d["data_freshness"]["cerebro"] = TODAY_S
    d["data_freshness"]["rank_tracker"] = TODAY_S

    with path.open("w") as f:
        json.dump(d, f, indent=2)
    print(f"  updated: {path.name} (+{len(NEW_BACKLOG)} backlog entries)")


# ---------------------------------------------------------------------------
# Experiment log update
# ---------------------------------------------------------------------------

def update_log(path: Path) -> None:
    if not path.exists():
        print(f"  skip (missing): {path}")
        return
    with path.open() as f:
        d = json.load(f)
    d["_last_updated"] = TODAY_S
    d["_last_run_by"] = "Claude (Apr 29 Cerebro + 6mo rank history pass)"

    existing_ids = {e["id"] for e in d.get("active_experiments", [])} | {
        e["id"] for e in d.get("completed_experiments", [])
    }
    for entry in NEW_BACKLOG:
        if entry["id"] in existing_ids:
            continue
        # Build active_experiment shape
        log_entry = {
            "id": entry["id"],
            "element": entry["title"],
            "status": "TODO",
            "start_date": entry["scheduled_date"],
            "decision_date": entry.get("decision_date"),
            "hypothesis": entry["assumption"],
            "priority": entry["priority"],
            "rationale": entry["rationale"],
            "expected_impact": entry["expected_change"],
            "wave": 1,
            "run_window_days": 7,
            "success_criteria": entry["success_criteria"],
            "execution": {
                "what_to_do": entry["execution_steps"][0],
                "steps": entry["execution_steps"],
            },
            "listing": entry["listing"],
            "actual_result": None,
        }
        d["active_experiments"].append(log_entry)
    with path.open("w") as f:
        json.dump(d, f, indent=2)
    print(f"  updated: {path.name}")


# ---------------------------------------------------------------------------

def main() -> int:
    print("--- updating active_tracker.json ---")
    for p in TRACKER_PATHS:
        update_tracker(p)

    # Sync the dashboard mirror
    src, dst = TRACKER_PATHS[0], TRACKER_PATHS[1] if TRACKER_PATHS[1].exists() else None
    if dst is None:
        # If repo root doesn't have it, copy from dashboard to repo root
        try:
            shutil.copyfile(TRACKER_PATHS[0], TRACKER_PATHS[1])
            print(f"  mirrored to {TRACKER_PATHS[1].name}")
        except Exception as e:
            print(f"  mirror failed: {e}")

    print("--- updating experiment_log.json ---")
    for p in LOG_PATHS:
        update_log(p)

    print(f"\nDone. {len(NEW_BACKLOG)} new experiments added (EXP-051..055).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
