"""Apr 30 evening — close out EXP-054/055 + add EXP-062.

Done today:
  - EXP-054 Filter listing audit + quick fixes shipped
  - EXP-055 Bundle listing audit + quick fixes shipped
  - Bonus: Bundle A+ upgraded to A+ Premium (matches main fountain listing)

Add:
  - EXP-062: Upgrade filter listing to A+ Premium (only listing without it now)
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
    "EXP-054": (
        "DONE 2026-04-30. Filter listing quick fixes shipped: (1) Title rewritten with 'PAW PURE' brand prefix + corrected to '4 Filters + 4 Sponges' + 'Multi-Layer Filtration' wording. "
        "(2) Bullet 1 corrected from '2 sponges' → '4 sponges' (was a returnable-claim risk). "
        "(3) Bullet 2 reworded to 'Multi-Layer Filtration Design' for consistency with title and bundle. "
        "(4) Added OEM Paw Pure authenticity bullet to compete with RIZZARI. "
        "Bigger items deferred to next week: hi-res hero image, A+ Premium upgrade (now the only Paw Pure listing without it), full image alt-text rewrite. "
        "Verify 2026-05-13 — measure CVR delta + organic indexing."
    ),
    "EXP-055": (
        "DONE 2026-04-30. Bundle listing quick fixes shipped: (1) Bundle pricing dropped to $62.29 / 11% off (from $4.90 / 7% off) — meaningful psychological discount while preserving margin. "
        "(2) Bundle A+ typo fixed ('fourreplacement' → 'four replacement'). "
        "(3) BONUS: Bundle A+ upgraded to A+ Premium (matches main fountain listing). "
        "Hero image already correct (bundle composition shot). EXP-040 bullets confirmed shipped (5 new bullets including the corrected 20dB+stainless steel bullet 5). "
        "Filter listing is now the ONLY Paw Pure listing without A+ Premium — see EXP-062. "
        "Verify 2026-05-15 — first bundle sale within 14 days."
    ),
}

NEW_EXP_062 = {
    "id": "EXP-062",
    "title": "Upgrade filter listing (B0FWXJ1GKT) to A+ Premium",
    "scheduled_date": "2026-05-04",
    "decision_date": "2026-05-18",
    "priority": "MEDIUM",
    "growth_metric": "Filter CVR + brand consistency",
    "listing": "filters",
    "assumption": "Bundle (B0GMDM6CG2) and main fountain (B0DJHQVJYF) are both on A+ Premium. Filter (B0FWXJ1GKT) is the only Paw Pure listing still on basic A+ Content. A+ Premium adds video modules, 1000-pixel hero rows, hover-zoom, and comparison tables — all of which lift CVR ~5-15% per Amazon's own benchmarks for sub-$30 SKUs.",
    "rationale": "We just shipped EXP-054 quick fixes (title + bullet 1 sponge count + OEM bullet + multi-layer wording). Filter Campaign EXP-051 starts driving paid traffic this week. Every dollar of new PPC traffic on the filter converts at a higher rate when the listing has Premium A+ vs basic. Closing the gap brings filter listing parity with bundle and main listing.",
    "expected_change": "Filter session-to-order CVR lifts 5-15% post-Premium upgrade. Hover-zoom + 1000px hero rows give buyers more detail before clicking away. Comparison module helps frame Paw Pure vs RIZZARI on real attributes (e.g. compatibility specifically with Paw Pure fountain).",
    "execution_steps": [
        "Confirm Brand Registry 2.0 status on Paw Pure brand (required for A+ Premium)",
        "Seller Central > Stores > Manage A+ Content > Create A+ Premium Content",
        "Use the same module library as the bundle/fountain Premium A+ but tailor to filter narrative:",
        "  Module 1: Hero with hover-zoom — 'Multi-Layer Filtration Inside'",
        "  Module 2: Video module — 30s show-and-tell of swapping a filter (already have footage, edit and upload)",
        "  Module 3: 1000px crossover row — three side-by-side panels: (a) cotton mesh, (b) activated carbon, (c) ion-exchange resin — each with a single-line benefit",
        "  Module 4: Comparison table — Paw Pure OEM filter vs generic third-party filters on: dimensions match, pump compatibility, multi-layer construction, food-grade materials",
        "  Module 5: 'When to replace' calendar visual — 4 filters covering 4-6 months",
        "  Module 6: Cross-link CTA — 'Don't have the fountain yet?' with link to B0DJHQVJYF and bundle B0GMDM6CG2",
        "Submit for Amazon review (Premium A+ approval typically 24-72h)",
        "Once approved, monitor filter CVR weekly — expect lift to register by 2026-05-18"
    ],
    "success_criteria": {
        "metric": "filter_session_to_order_cvr",
        "baseline": "TBD (post EXP-059 Reports API recovery)",
        "target": "+10%",
        "unit": "%",
        "direction": "up",
        "how_to_measure": "SP-API Business Reports — sessions_total / units_ordered for B0FWXJ1GKT, weekly delta vs prior 14d baseline."
    }
}

NEW_WEEK_POINTERS = [
    {"id": "EXP-062", "scheduled_date": "2026-05-04", "title": "Upgrade filter to A+ Premium", "status": "QUEUED"},
]


def update_log(path: Path) -> None:
    if not path.exists():
        return
    d = json.loads(path.read_text())
    by_id = {e["id"]: e for e in d.get("active_experiments", [])}

    for eid, note in DONE_NOTES.items():
        e = by_id.get(eid)
        if not e:
            continue
        e["status"] = "DONE"
        e["completed_date"] = TODAY
        e["actual_result"] = note

    existing = {e["id"] for e in d.get("active_experiments", [])} | {
        e["id"] for e in d.get("completed_experiments", [])
    }
    if NEW_EXP_062["id"] not in existing:
        d["active_experiments"].append({
            "id": NEW_EXP_062["id"],
            "element": NEW_EXP_062["title"],
            "status": "QUEUED",
            "start_date": NEW_EXP_062["scheduled_date"],
            "decision_date": NEW_EXP_062["decision_date"],
            "hypothesis": NEW_EXP_062["assumption"],
            "priority": NEW_EXP_062["priority"],
            "rationale": NEW_EXP_062["rationale"],
            "expected_impact": NEW_EXP_062["expected_change"],
            "wave": 1,
            "run_window_days": 14,
            "success_criteria": NEW_EXP_062["success_criteria"],
            "execution": {
                "what_to_do": NEW_EXP_062["execution_steps"][0],
                "steps": NEW_EXP_062["execution_steps"],
            },
            "listing": NEW_EXP_062["listing"],
            "actual_result": None,
        })

    d["_last_updated"] = TODAY
    path.write_text(json.dumps(d, indent=2))


def update_tracker(path: Path) -> None:
    if not path.exists():
        return
    d = json.loads(path.read_text())

    bl_by_id = {b["id"]: b for b in d.get("backlog", [])}
    for eid in DONE_NOTES:
        b = bl_by_id.get(eid)
        if b:
            b["status"] = "DONE"
            b["completed_date"] = TODAY

    if NEW_EXP_062["id"] not in bl_by_id:
        d.setdefault("backlog", []).append(NEW_EXP_062)

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
    print("--- Marking EXP-054 + EXP-055 DONE ---")
    for p in LOG_PATHS:
        update_log(p)
        print(f"  {p.name}: 2 done, +1 new (EXP-062)")
    print("\n--- Updating active_tracker.json ---")
    for p in TRACKER_PATHS:
        update_tracker(p)
        print(f"  {p.name}: synced")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
