"""Apr 30 experiment cleanup + EXP-056..060 additions.

CLEANUP
  - EXP-053: fix "Strategy" path → "PPC Strategy" everywhere it appears
  - EXP-027 / EXP-029 / EXP-030 / EXP-036: mark `status: SUPERSEDED` with
    `superseded_by` and a note explaining why (per Apr 30 audit).
  - EXP-031 / EXP-037 / EXP-038: keep EXP-031 as primary, mark EXP-037 and
    EXP-038 as `status: ALTERNATE` with `consolidated_into: "EXP-031"`.
  - EXP-028: add `actual_result` string ("DONE 2026-04-19. KEEP.") so the
    verdict is captured.

ADDS
  - EXP-056 PAT campaign on PETLIBRO competitor ASIN
  - EXP-057 Fountain bullets quality-positioning rewrite (replaces EXP-029)
  - EXP-058 Daily Request-a-Review automation (concrete version of EXP-035)
  - EXP-059 Reports API quota retry / backfill
  - EXP-060 Wave 3 dog bullet copy with concrete copy + date

Updates active_tracker.json + experiment_log.json + dashboard mirror.
"""
from __future__ import annotations

import json
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

TODAY = "2026-04-30"
DECISION_7D = "2026-05-07"
DECISION_14D = "2026-05-14"


# ---------------------------------------------------------------------------
# Cleanup actions
# ---------------------------------------------------------------------------

CLEANUP = {
    "EXP-053": {
        "patch": "rename_path",
        "old": "Strategy > H10 Opportunities",
        "new": "PPC Strategy > H10 Opportunities",
    },
    "EXP-027": {
        "patch": "supersede",
        "superseded_by": ["EXP-046", "EXP-051", "EXP-052"],
        "note": "Generic 'exact match campaign' replaced by data-driven specifics: bid surgery (EXP-046), filter campaign (EXP-051), 3 momentum-validated KWs (EXP-052).",
    },
    "EXP-029": {
        "patch": "supersede",
        "superseded_by": ["EXP-057"],
        "note": "Premise outdated. Original used 5.13% organic / 0% ad CVR baseline that no longer reflects the Apr 28 data state (89.6% ACoS, sparse attribution). Replaced by EXP-057 quality-positioning rewrite.",
    },
    "EXP-030": {
        "patch": "supersede",
        "superseded_by": [],
        "note": "Apr 29 6-month rank history shows we're LOSING ground on 'battery operated cat fountain' (#144 → #263). Lessons file rule: don't bid up where algo is dropping us. DEPRECATED.",
    },
    "EXP-036": {
        "patch": "supersede",
        "superseded_by": ["EXP-040", "EXP-055"],
        "note": "Original plan was to deactivate the bundle. Today's strategy is the opposite — EXP-040 rewrites copy + EXP-055 audits images/A+. DEPRECATED in favor of revival path.",
    },
    "EXP-037": {
        "patch": "consolidate",
        "consolidated_into": "EXP-031",
        "note": "Three Bullet 1 rewrite hypotheses overlap. EXP-031 stays primary. EXP-037 retained as ALTERNATE variant if EXP-031 underperforms.",
    },
    "EXP-038": {
        "patch": "consolidate",
        "consolidated_into": "EXP-031",
        "note": "Bullet 2 cleanability messaging — moved into EXP-031 as a secondary angle. Retained as ALTERNATE.",
    },
    "EXP-028": {
        "patch": "add_result",
        "actual_result": "DONE 2026-04-19. Backend search terms updated with high-SV gap KWs. Sessions improvement was not measurable due to Reports API quota gaps starting Apr 27 — see EXP-059 (quota retry). KEEP, but verdict pending Reports API recovery.",
    },
}


# ---------------------------------------------------------------------------
# New experiments
# ---------------------------------------------------------------------------

NEW = [
    {
        "id": "EXP-056",
        "title": "PAT campaign on PETLIBRO B0FDKQGRCK — comparison-shopper interception",
        "scheduled_date": TODAY,
        "decision_date": DECISION_7D,
        "priority": "HIGH",
        "growth_metric": "Sponsored impressions on competitor pages",
        "listing": "fountain",
        "assumption": "PETLIBRO sits BSR #5 in Cat Fountains at $66.36 with 1,813 reviews. Buyers comparison-shopping on their listing are exactly the premium-tier segment we want. PAT bids on their detail page can intercept at 30-50% of broad-keyword CPC.",
        "rationale": "Today's Insights tab shows PETLIBRO with Threat Score 50 — third-highest. Premium positioning means their browsers can afford ours. Their 4.3★ vs our 4.5★ is a real wedge.",
        "expected_change": "5-15 sponsored impressions/day on B0FDKQGRCK detail page, 1-2 clicks/day at <$0.50 CPC, first attributed click within 7 days. Monitor for ACoS — gate at 50% (filters' ACoS gate is 30%; PAT against premium has more headroom because basket size and CVR are higher).",
        "execution_steps": [
            "Seller Central > Create Campaign > Sponsored Products > Manual targeting > Continue",
            "Campaign name: SP_PAT_PETLIBRO_2026-04-30",
            "Daily budget: $3.00",
            "Bidding strategy: Dynamic bids — down only",
            "Placement: Top of search 0%, Product pages +20%",
            "Ad group: PAT_PETLIBRO_Dockstream",
            "Default bid: $0.45",
            "Add product: B0DJHQVJYF",
            "Product targeting > Individual products > Enter list:",
            "  B0FDKQGRCK    bid $0.45    (PETLIBRO Dockstream 2)",
            "Negative product targeting:",
            "  B0DJHQVJYF    (exclude our own)",
            "Launch. Daily check-in for first 3 days. Decision on 2026-05-07."
        ],
        "success_criteria": {
            "metric": "pat_clicks_7d",
            "baseline": 0,
            "target": 5,
            "unit": "clicks",
            "direction": "up",
            "how_to_measure": "Ads API SP Targeting report — filter by campaign SP_PAT_PETLIBRO_2026-04-30"
        }
    },
    {
        "id": "EXP-057",
        "title": "Fountain bullets — quality-positioning rewrite vs APAUK / PawPoll",
        "scheduled_date": "2026-05-01",
        "decision_date": DECISION_14D,
        "priority": "HIGH",
        "growth_metric": "Fountain CVR on premium-intent KWs",
        "listing": "fountain",
        "assumption": "APAUK ($21.99, 4.5★ × 2,502 rev) and PawPoll ($39.99, 4.1★ × 3,668 rev) attack on price. We can't win on price. The lever we DO have: we are 4.5★ — matching APAUK and ABOVE PawPoll. Lead bullets with quality + materials, not feature-list parity.",
        "rationale": "Replaces stale EXP-029 which still assumed CVR investigation was the bottleneck. Apr 28 listing audit + competitor data make the actual answer clear: premium positioning is the only path. Bullets must STOP sounding like every other listing and START sounding like a premium product.",
        "expected_change": "CVR lift 15-25% on premium-intent terms (`stainless steel`, `quiet`, `cordless`). No measurable change on price-shopping terms (`cheap`, `bundle`) — that's intentional, those buyers go to APAUK.",
        "execution_steps": [
            "Open Strategy tab > Listing Touchpoint Map for fountain B0DJHQVJYF",
            "Identify which bullets currently mirror competitor language (genericness check)",
            "Rewrite using framework: <PREMIUM-CLAIM> — <CONCRETE-DIFF-VS-COMPETITOR> — <BUYER-OUTCOME>",
            "Example new Bullet 1: 'WHISPER-QUIET 20dB MOTOR — Most fountains hum at 30-40dB. Paw Pure runs at 20dB, the loudness of a quiet library. Won't startle skittish cats, won't wake light sleepers. The premium pump that justifies the price.'",
            "Example new Bullet 2: 'FOOD-GRADE STAINLESS STEEL TRAY — Other brands hide plastic behind a steel rim. The surface your cat's tongue touches is 304 stainless steel — the same grade used in commercial kitchens. Zero plastic taste, BPA-free.'",
            "Submit via Seller Central > Manage Inventory > B0DJHQVJYF > Edit",
            "Wait 24h for live, then verify changes",
            "Monitor SP-API Business Reports for CVR delta over 14 days vs prior 14-day baseline"
        ],
        "success_criteria": {
            "metric": "premium_kw_cvr_14d",
            "baseline": "TBD from prior 14d",
            "target": "+15%",
            "unit": "%",
            "direction": "up",
            "how_to_measure": "SP-API Business Reports + Ads API attributed CVR for KWs containing 'stainless', 'quiet', 'cordless'"
        }
    },
    {
        "id": "EXP-058",
        "title": "Daily Request-a-Review automation via SP-API Solicitations",
        "scheduled_date": "2026-05-02",
        "decision_date": "2026-06-02",
        "priority": "CRITICAL",
        "growth_metric": "Reviews per week",
        "listing": "brand",
        "assumption": "Reviews are THE bottleneck (we have 21 vs APAUK 2,502). At our current ~0.65 reviews/week pace, we'd need 38 years to match APAUK. Solicitations API can request a review on every delivered order, ~2.5x our current organic ask rate.",
        "rationale": "Generalises stale EXP-035 with concrete tactics. The Solicitations API is ready-but-gated per data_freshness notes. Closing this gap unlocks: (1) Amazon's Choice re-eligibility, (2) organic CVR floor, (3) ladder pricing milestones in pricingLadder.",
        "expected_change": "Review velocity from 0.65/wk → 2/wk within 30 days. Hit 50 reviews by mid-June (currently 21 + 30 days × 2/wk = 30). Subsequent ladder unlocks $42.99 price point at 50 reviews per strategy_pricing.json.",
        "execution_steps": [
            "Verify SP-API Solicitations endpoint is callable (check Auth scope: solicitations.requestReviewSolicitation:create)",
            "If gated: open Seller Central case to request access — usually 24-48h",
            "Build amazon_api/pullers/request_reviews.py: pulls delivered orders from last 4-30 days, filters out already-asked (track in solicitation_log.json), calls POST /solicitations/v1/orders/{orderId}/solicitations/productReviewAndSellerFeedback",
            "Add to daily_pipeline.py to run every morning",
            "Track outcomes in dashboard: new column 'requested' on orders table",
            "Insert thank-you cards in next inventory shipment with QR code → review page (parallel manual lever)"
        ],
        "success_criteria": {
            "metric": "reviews_per_week",
            "baseline": 0.65,
            "target": 2.0,
            "unit": "reviews/week",
            "direction": "up",
            "how_to_measure": "data.voc.current.paw_pure.total_ratings 7-day delta"
        }
    },
    {
        "id": "EXP-059",
        "title": "Reports API quota retry + backfill — no more Sessions/CVR gaps",
        "scheduled_date": "2026-05-01",
        "decision_date": DECISION_7D,
        "priority": "HIGH",
        "growth_metric": "Data completeness",
        "listing": "ops",
        "assumption": "Sessions and CVR have been null since Apr 27 (Reports API quota exceeded). The dashboard now uses last-known-good (Apr 23: 157 sessions, 3.18% CVR) but this hides real movement. A retry-with-exponential-backoff inside pull_business_reports.py would close the gap.",
        "rationale": "Daily KPI history shows we're flying blind on the conversion side of the funnel. Without sessions data, we cannot confirm whether the 89.6% ACoS is being caused by traffic drying up OR PPC inefficiency.",
        "expected_change": "Sessions/CVR populated daily within 7 days. 'as of Apr 23 (Reports API quota)' annotation disappears from PPC Strategy tab. EXP-057 success_criteria becomes measurable.",
        "execution_steps": [
            "Read amazon_api/pullers/pull_business_reports.py — find quota error handling",
            "Wrap report request in retry-with-exponential-backoff: 1s, 5s, 30s, 5min, 30min — give up after 4 hours total",
            "On quota_exceeded: log to amazon_api/data/logs/reports_quota.log with timestamp",
            "Add cron retry: if pipeline ran but business_reports came back null, queue a retry 4h later",
            "Backfill: scan ads_*.json window dates and try to pull historical Reports data for any missing days (if API allows)",
            "Verify: run scripts/build_daily_kpis_history.py after first successful pull — gaps should fill in"
        ],
        "success_criteria": {
            "metric": "days_with_sessions_data_last_7d",
            "baseline": 0,
            "target": 5,
            "unit": "days",
            "direction": "up",
            "how_to_measure": "Count of dates in daily_kpis_history.series where sessions != null in last 7 days"
        }
    },
    {
        "id": "EXP-060",
        "title": "Wave 3 dog bullet copy — ship the concrete bridge for Phase 3",
        "scheduled_date": "2026-05-05",
        "decision_date": DECISION_14D,
        "priority": "HIGH",
        "growth_metric": "Dog KW indexing",
        "listing": "fountain",
        "assumption": "EXP-049 exists but is undated and lacks the actual copy. Phase 3 dog PPC (EXP-050) is gated on this. Today's competitor data (oneisall $175K/mo at 10L) confirms we cannot compete on capacity but CAN on wireless + multi-pet positioning.",
        "rationale": "Concrete version of EXP-049 with real copy. Without this, dog SVs (57K/57K/33K) stay un-bid and Phase 3 cannot start.",
        "expected_change": "Listing indexes for dog/multi-pet KWs within 7 days. Unlocks EXP-050 dog PPC validation.",
        "execution_steps": [
            "Update Bullet 4 of fountain B0DJHQVJYF: replace existing text with",
            "  'WORKS FOR CATS AND SMALL DOGS — 3L/108oz capacity is enough for cats AND small dogs to share. Three flow modes (Gentle Stream, Bubble, Continuous) keep every pet drinking — even hesitant ones. Multi-pet households, one fountain.'",
            "Update A+ Module 3: add a small dog drinking image alongside cat",
            "Update backend search terms: add 'small dog water fountain wireless', 'cordless dog water fountain', 'multi pet water fountain'",
            "Submit via Seller Central > B0DJHQVJYF > Edit",
            "After 7 days: pull KW_Data, verify dog KWs are now indexed (rank ≤ 306)",
            "If indexed: launch EXP-050 (dog PPC validation) on 2026-05-12"
        ],
        "success_criteria": {
            "metric": "dog_kws_indexed_7d",
            "baseline": 0,
            "target": 3,
            "unit": "keywords",
            "direction": "up",
            "how_to_measure": "Count of dog KWs (those matching DOG_REGEX) where rank_history shows organic rank ≤ 306"
        }
    }
]

# Pointer-only entries for weekly_strategy[0].experiments
NEW_WEEK_POINTERS = [
    {"id": "EXP-056", "scheduled_date": TODAY, "title": "PAT PETLIBRO comparison-shopper interception", "status": "TODO"},
    {"id": "EXP-057", "scheduled_date": "2026-05-01", "title": "Fountain bullets quality-positioning rewrite", "status": "TODO"},
    {"id": "EXP-058", "scheduled_date": "2026-05-02", "title": "Request-a-Review automation", "status": "TODO"},
    {"id": "EXP-059", "scheduled_date": "2026-05-01", "title": "Reports API quota retry/backfill", "status": "TODO"},
    {"id": "EXP-060", "scheduled_date": "2026-05-05", "title": "Wave 3 dog bullet copy ship", "status": "TODO"},
]


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply_cleanup_to_log(log_path: Path) -> None:
    if not log_path.exists():
        return
    d = json.loads(log_path.read_text())
    by_id = {e["id"]: e for e in d.get("active_experiments", [])}
    for exp_id, action in CLEANUP.items():
        e = by_id.get(exp_id)
        if not e:
            continue
        if action["patch"] == "rename_path":
            for key in ("execution",):
                if isinstance(e.get(key), dict):
                    for k2, v in e[key].items():
                        if isinstance(v, str):
                            e[key][k2] = v.replace(action["old"], action["new"])
                        elif isinstance(v, list):
                            e[key][k2] = [
                                s.replace(action["old"], action["new"]) if isinstance(s, str) else s
                                for s in v
                            ]
        elif action["patch"] == "supersede":
            e["status"] = "SUPERSEDED"
            e["superseded_by"] = action["superseded_by"]
            e["supersede_note"] = action["note"]
        elif action["patch"] == "consolidate":
            e["status"] = "ALTERNATE"
            e["consolidated_into"] = action["consolidated_into"]
            e["consolidate_note"] = action["note"]
        elif action["patch"] == "add_result":
            e["actual_result"] = action["actual_result"]
    d["_last_updated"] = TODAY
    log_path.write_text(json.dumps(d, indent=2))


def apply_cleanup_to_tracker(tracker_path: Path) -> None:
    if not tracker_path.exists():
        return
    d = json.loads(tracker_path.read_text())
    # Remove SUPERSEDED ids from backlog (clean view) but keep ALTERNATE visible
    superseded_ids = {
        eid for eid, a in CLEANUP.items() if a["patch"] == "supersede"
    }
    if "backlog" in d:
        d["backlog"] = [b for b in d["backlog"] if b.get("id") not in superseded_ids]

    # Patch path on EXP-053 if present in backlog
    for b in d.get("backlog", []):
        if b.get("id") == "EXP-053":
            for key in ("execution_steps",):
                if isinstance(b.get(key), list):
                    b[key] = [s.replace("Strategy > H10 Opportunities", "PPC Strategy > H10 Opportunities") for s in b[key]]
    d["today"] = TODAY
    d["generated"] = TODAY
    tracker_path.write_text(json.dumps(d, indent=2))


def append_new_to_tracker(tracker_path: Path) -> None:
    if not tracker_path.exists():
        return
    d = json.loads(tracker_path.read_text())
    bl_ids = {b["id"] for b in d.get("backlog", [])}
    for entry in NEW:
        if entry["id"] not in bl_ids:
            d.setdefault("backlog", []).append(entry)
    if d.get("weekly_strategy"):
        wk = d["weekly_strategy"][0]
        existing_ids = {e["id"] for e in wk.get("experiments", [])}
        for ptr in NEW_WEEK_POINTERS:
            if ptr["id"] not in existing_ids:
                wk["experiments"].append(ptr)
    tracker_path.write_text(json.dumps(d, indent=2))


def append_new_to_log(log_path: Path) -> None:
    if not log_path.exists():
        return
    d = json.loads(log_path.read_text())
    existing = {e["id"] for e in d.get("active_experiments", [])} | {
        e["id"] for e in d.get("completed_experiments", [])
    }
    for entry in NEW:
        if entry["id"] in existing:
            continue
        d["active_experiments"].append({
            "id": entry["id"],
            "element": entry["title"],
            "status": "TODO",
            "start_date": entry["scheduled_date"],
            "decision_date": entry["decision_date"],
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
        })
    log_path.write_text(json.dumps(d, indent=2))


def main() -> int:
    print("--- Cleanup ---")
    for p in LOG_PATHS:
        apply_cleanup_to_log(p)
        print(f"  cleanup applied to {p.name}")
    for p in TRACKER_PATHS:
        apply_cleanup_to_tracker(p)
        print(f"  cleanup applied to {p.name}")
    print("\n--- Adding EXP-056..060 ---")
    for p in TRACKER_PATHS:
        append_new_to_tracker(p)
        print(f"  appended to {p.name}")
    for p in LOG_PATHS:
        append_new_to_log(p)
        print(f"  appended to {p.name}")
    print(f"\nDone. {len(CLEANUP)} cleanups + {len(NEW)} new experiments.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
