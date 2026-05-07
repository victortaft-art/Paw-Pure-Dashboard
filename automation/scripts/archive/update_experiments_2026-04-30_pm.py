"""Apr 30 PM update — close the loop on today's shipped work.

Actions:
  1. Mark EXP-051 / EXP-052 / EXP-053 as DONE with completed_date 2026-04-30
     and a brief actual_result note (Victor confirmed shipped).
  2. Bump EXP-059 priority HIGH → CRITICAL (Reports API retry is a blocker
     for measuring all listing experiments).
  3. Add EXP-061: kill SP_Test_Expansion + merge `cat drinking fountain`
     into Manual Keywords Campaign at $0.80 exact. Single keyword campaigns
     with low bids produce zero data — fold and consolidate.

Touches both experiment_log.json paths and active_tracker.json paths.
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

DONE_NOTES = {
    "EXP-051": "DONE 2026-04-30. Filters_Manual campaign launched on B0FWXJ1GKT with 4 exact-match KWs at $0.65-$0.80. First ACoS pull on 2026-05-07 — gate at 30%.",
    "EXP-052": "DONE 2026-04-30. 3 momentum-validated cat KWs added to Manual Keywords Campaign (cat water fountain stainless steel wireless $1.30, rechargeable cat water fountain $1.00, kitty spout cat water fountain $1.20). First ACoS pull 2026-05-02.",
    "EXP-053": "DONE 2026-04-30. 26 wasted-spend negatives added to Manual Keywords Campaign (ceramic / no filter / pumpless families). Effect compounds daily — verify wasted-spend reduction on 2026-05-06.",
}

NEW_EXP_061 = {
    "id": "EXP-061",
    "title": "Kill SP_Test_Expansion + fold `cat drinking fountain` into Manual Keywords Campaign",
    "scheduled_date": TODAY,
    "decision_date": "2026-05-07",
    "priority": "MEDIUM",
    "growth_metric": "Campaign hygiene + impressions on 'cat drinking fountain'",
    "listing": "fountain",
    "assumption": "SP_Test_Expansion_2026-04-19 has produced 1 impression in 8 days because its single keyword (`cat drinking fountain` exact) is bid too low to win the auction. Per Apr 30 lesson: single-KW low-bid test campaigns are silent failures. Folding the KW into the active Manual Keywords Campaign at competitive bid will capture impressions immediately.",
    "rationale": "Cerebro Apr 28 + KT rank history confirm `cat drinking fountain` (SV 5,519) gained 104 organic positions in the last 30 days (#280 → #176). The Apr 29 lesson says: bid up where the algo is favoring us. Test campaign has zero discoverability; main campaign already wins impressions on similar terms.",
    "expected_change": "Campaign accounting cleaner. `cat drinking fountain` exact gets 5-15 impressions/day inside Manual Keywords Campaign at $0.80 bid. First attributed click within 7 days.",
    "execution_steps": [
        "Seller Central > Sponsored Products > Campaigns > select SP_Test_Expansion_2026-04-19",
        "Campaign settings > Pause campaign (do NOT delete — keep history for reference)",
        "Open Manual Keywords Campaign > add keyword:",
        "  cat drinking fountain — match: exact — bid: $0.80",
        "Save. Daily monitor for first 3 days; verify impressions > 0 by 2026-05-03.",
        "Add to lessons file: 'Single-KW test campaigns produce zero data unless bid is competitive.'",
    ],
    "success_criteria": {
        "metric": "cat_drinking_fountain_impressions_7d",
        "baseline": 1,
        "target": 35,
        "unit": "impressions",
        "direction": "up",
        "how_to_measure": "Ads API SP Targeting report — filter keyword 'cat drinking fountain'."
    },
}

NEW_WEEK_POINTERS = [
    {"id": "EXP-061", "scheduled_date": TODAY, "title": "Kill SP_Test_Expansion + fold KW into Manual", "status": "TODO"},
]


def update_log(path: Path) -> None:
    if not path.exists():
        return
    d = json.loads(path.read_text())
    by_id = {e["id"]: e for e in d.get("active_experiments", [])}

    # 1. Mark done
    for eid, note in DONE_NOTES.items():
        e = by_id.get(eid)
        if not e:
            continue
        e["status"] = "DONE"
        e["completed_date"] = TODAY
        e["actual_result"] = note

    # 2. Priority bump
    if "EXP-059" in by_id:
        by_id["EXP-059"]["priority"] = "CRITICAL"
        by_id["EXP-059"].setdefault("priority_history", []).append({
            "date": TODAY,
            "from": "HIGH",
            "to": "CRITICAL",
            "reason": "Reports API quota gap blocks verdicts on every conversion-related experiment. Apr 30 audit upgrade.",
        })

    # 3. Add EXP-061
    existing = {e["id"] for e in d.get("active_experiments", [])} | {
        e["id"] for e in d.get("completed_experiments", [])
    }
    if NEW_EXP_061["id"] not in existing:
        d["active_experiments"].append({
            "id": NEW_EXP_061["id"],
            "element": NEW_EXP_061["title"],
            "status": "TODO",
            "start_date": NEW_EXP_061["scheduled_date"],
            "decision_date": NEW_EXP_061["decision_date"],
            "hypothesis": NEW_EXP_061["assumption"],
            "priority": NEW_EXP_061["priority"],
            "rationale": NEW_EXP_061["rationale"],
            "expected_impact": NEW_EXP_061["expected_change"],
            "wave": 1,
            "run_window_days": 7,
            "success_criteria": NEW_EXP_061["success_criteria"],
            "execution": {
                "what_to_do": NEW_EXP_061["execution_steps"][0],
                "steps": NEW_EXP_061["execution_steps"],
            },
            "listing": NEW_EXP_061["listing"],
            "actual_result": None,
        })

    d["_last_updated"] = TODAY
    path.write_text(json.dumps(d, indent=2))


def update_tracker(path: Path) -> None:
    if not path.exists():
        return
    d = json.loads(path.read_text())

    # Tracker uses backlog[].status separately
    bl_by_id = {b["id"]: b for b in d.get("backlog", [])}
    for eid in DONE_NOTES:
        b = bl_by_id.get(eid)
        if b:
            b["status"] = "DONE"
            b["completed_date"] = TODAY

    # EXP-059 priority bump in backlog
    if "EXP-059" in bl_by_id:
        bl_by_id["EXP-059"]["priority"] = "CRITICAL"

    # Append EXP-061 to backlog
    if NEW_EXP_061["id"] not in bl_by_id:
        d.setdefault("backlog", []).append(NEW_EXP_061)

    # Update weekly_strategy[0].experiments — mark DONE + add 061
    if d.get("weekly_strategy"):
        wk = d["weekly_strategy"][0]
        wk_existing = {e["id"]: e for e in wk.get("experiments", [])}
        for eid in DONE_NOTES:
            if eid in wk_existing:
                wk_existing[eid]["status"] = "DONE"
                wk_existing[eid]["completed_date"] = TODAY
        for ptr in NEW_WEEK_POINTERS:
            if ptr["id"] not in wk_existing:
                wk["experiments"].append(ptr)

    d["today"] = TODAY
    d["generated"] = TODAY
    path.write_text(json.dumps(d, indent=2))


def main() -> int:
    print("--- updating experiment_log.json ---")
    for p in LOG_PATHS:
        update_log(p)
        print(f"  {p.name}: marked 3 done, bumped EXP-059 → CRITICAL, added EXP-061")
    print("\n--- updating active_tracker.json ---")
    for p in TRACKER_PATHS:
        update_tracker(p)
        print(f"  {p.name}: backlog + weekly_strategy synced")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
