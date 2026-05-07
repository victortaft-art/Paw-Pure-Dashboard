"""Experiment Advisor — programmatic learning loop.

Reads all data the dashboard has (Cerebro, rank history, ads, KW data,
competitor intel, daily KPI history, experiment log) and emits structured
advice in three buckets:

  1. to_deprecate   — experiments whose premise no longer holds
  2. to_update      — experiments whose hypothesis or copy is stale but
                      the underlying lever is still worth pursuing
  3. proposed_new   — patterns in current data that suggest a new
                      experiment we don't have yet

Output: dashboard/public/data/experiment_advisor_<date>.json
        + the latest snapshot at experiment_advisor.json

Usage:
    python -m helium10_pipeline.experiment_advisor
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT.parent / "public" / "data"
KW = ROOT / "kw_data"

DOG_REGEX = re.compile(r"\b(dogs?|puppy|puppies|canine|k9)\b", re.I)


# ---------------------------------------------------------------------------
# Source loaders
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def load_sources() -> dict:
    # Latest cerebro_opportunities and rank_history under kw_data
    def latest_in(folder: Path, prefix: str) -> dict | None:
        if not folder.exists():
            return None
        files = sorted([p for p in folder.glob(f"{prefix}_*.json")])
        return _load_json(files[-1]) if files else None

    return {
        "experiment_log": _load_json(ROOT / "experiment_log.json"),
        "active_tracker": _load_json(DATA / "active_tracker.json"),
        "cerebro_opps": latest_in(KW, "cerebro_opportunities"),
        "rank_history": latest_in(KW, "rank_history"),
        "competitor_intel": _load_json(DATA / "competitor_intel.json"),
        "daily_kpis": _load_json(DATA / "daily_kpis_history.json"),
        "kw_data": latest_in(KW, "KW_Data"),
        "lessons_path_hint": "memory/pawpure_experiment_lessons.md",
    }


# ---------------------------------------------------------------------------
# Validators (each returns list of finding dicts)
# ---------------------------------------------------------------------------

def detect_outdated_premises(sources: dict) -> list[dict]:
    """Cross-check active experiments' hypothesis against current data."""
    findings: list[dict] = []
    log = sources.get("experiment_log") or {}
    rank = sources.get("rank_history") or {}
    rank_index = {k["keyword"].lower(): k for k in rank.get("keywords", [])}

    for e in log.get("active_experiments", []):
        if e.get("status") in ("DONE", "SUPERSEDED", "ALTERNATE"):
            continue
        title = (e.get("element") or e.get("title") or "").lower()
        hyp = (e.get("hypothesis") or "").lower()

        # Pattern: experiment proposes bidding up on a KW, but rank history
        # shows we're losing organic ground there → outdated premise.
        for kw in rank_index.values():
            kw_text = kw["keyword"].lower()
            if kw_text not in title and kw_text not in hyp:
                continue
            history = [h for h in (kw.get("history") or []) if h.get("organic") is not None]
            if len(history) < 3:
                continue
            cutoff = (date.today() - timedelta(days=30)).isoformat()
            prior = next((h for h in history if h["date"] >= cutoff), history[0])
            latest = history[-1]
            delta = (prior["organic"] or 0) - (latest["organic"] or 0)  # +ve = improved
            # If experiment's hypothesis is bullish but rank dropped >50 spots:
            bullish = any(t in (title + hyp) for t in ("launch", "add", "bid up", "raise"))
            if bullish and delta < -50:
                findings.append({
                    "id": e["id"],
                    "kind": "outdated_premise",
                    "reason": f"Bullish on '{kw['keyword']}' but organic rank dropped {-delta:+d} positions in last 30d ({prior['organic']} → {latest['organic']}).",
                    "suggested_action": "Mark SUPERSEDED or rewrite hypothesis to defensive (bid down)."
                })
    return findings


def detect_supersession(sources: dict) -> list[dict]:
    """If an active experiment overlaps a newer one on listing+keyword, flag it."""
    findings: list[dict] = []
    log = sources.get("experiment_log") or {}
    actives = [e for e in log.get("active_experiments", []) if e.get("status") not in ("DONE", "SUPERSEDED", "ALTERNATE")]
    # Sort newest first by id
    actives_sorted = sorted(actives, key=lambda e: e["id"], reverse=True)
    seen_keys = {}
    for e in actives_sorted:
        listing = e.get("listing")
        title = (e.get("element") or e.get("title") or "").lower()
        # crude lever signature: "{listing}|{first 3 nouns of title}"
        words = re.findall(r"[a-z]{4,}", title)[:4]
        key = f"{listing}|{'-'.join(sorted(words))}"
        if key in seen_keys:
            findings.append({
                "id": e["id"],
                "kind": "possible_supersession",
                "reason": f"Overlaps with {seen_keys[key]} on listing={listing}, lever signature '{'-'.join(words)}'.",
                "suggested_action": f"Review for merge or mark superseded_by {seen_keys[key]}."
            })
        else:
            seen_keys[key] = e["id"]
    return findings


def propose_from_rank_momentum(sources: dict, log_existing_kws: set[str]) -> list[dict]:
    """KWs gaining significant rank but not yet in PPC → propose bid-up exp."""
    findings: list[dict] = []
    rank = sources.get("rank_history") or {}
    cerebro = sources.get("cerebro_opps") or {}
    bidding_kws = set()
    for k in (cerebro.get("new_keywords") or []):
        if k.get("already_bidding"):
            bidding_kws.add(k["keyword"].lower())

    for kw in rank.get("keywords", [])[:30]:
        history = [h for h in (kw.get("history") or []) if h.get("organic") is not None]
        if len(history) < 5:
            continue
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        prior = next((h for h in history if h["date"] >= cutoff), history[0])
        latest = history[-1]
        delta = (prior["organic"] or 0) - (latest["organic"] or 0)  # +ve = improved
        sv = kw.get("search_volume") or 0
        if delta >= 50 and sv >= 1500 and kw["keyword"].lower() not in bidding_kws:
            findings.append({
                "kind": "proposed_new",
                "title": f"Bid up on '{kw['keyword']}' — gained {delta} rank positions in 30d",
                "listing": "fountain" if not DOG_REGEX.search(kw["keyword"]) else "fountain",
                "rationale": f"Organic rank improved from #{prior['organic']} → #{latest['organic']} (Δ {delta:+d}). SV {sv:,}. Algo signal: bid here amplifies a winning trend (per Apr 29 lessons).",
                "suggested_match": "exact" if sv < 5000 else "phrase",
                "suggested_bid": round(min(2.0, max(0.6, sv / 10000)), 2),
                "metric": "attributed_orders_7d",
                "target": 1,
            })
    return findings


def propose_from_wasted_spend(sources: dict) -> list[dict]:
    """Active KWs spending money with zero conversion → propose negation."""
    findings: list[dict] = []
    log = sources.get("experiment_log") or {}
    daily = sources.get("daily_kpis") or {}
    series = daily.get("series", [])
    last_with_spend = next((r for r in reversed(series) if r.get("ad_spend") and r.get("ad_spend") > 0), None)
    if not last_with_spend:
        return []
    # We don't have per-keyword series in the daily file, but we can flag if
    # 7d spend > 0 and 7d sales < threshold.
    last_n = series[-7:]
    spend_7d = sum(r.get("ad_spend") or 0 for r in last_n)
    sales_7d = max((r.get("ad_sales_7d") or 0) for r in last_n) if last_n else 0
    if spend_7d > 30 and sales_7d < spend_7d * 0.4:
        findings.append({
            "kind": "proposed_new",
            "title": f"Audit & negate: 7d spend ${spend_7d:.2f} vs sales ${sales_7d:.2f} — ACoS unsustainable",
            "listing": "fountain",
            "rationale": "Spend-to-sales ratio implies portfolio ACoS > 2.5x breakeven. Pull SP Targeting report, identify zero-converting KWs with >$3 spend, add as negatives.",
            "suggested_match": "n/a",
            "suggested_bid": None,
            "metric": "spend_to_sales_ratio_7d",
            "target": 0.4,
        })
    return findings


def propose_from_competitor_signals(sources: dict) -> list[dict]:
    """Competitor data → opportunity-shaped experiments."""
    findings: list[dict] = []
    intel = sources.get("competitor_intel") or {}
    us = intel.get("us") or {}
    list_c = intel.get("competitors") or []

    # If competitor's price < 70% of ours → suggest premium-positioning audit
    threats = [c for c in list_c if c.get("price") and us.get("price") and c["price"] < us["price"] * 0.7]
    if len(threats) >= 2:
        findings.append({
            "kind": "proposed_new",
            "title": f"Premium-positioning audit — {len(threats)} competitor(s) priced ≤70% of ours",
            "listing": "fountain",
            "rationale": f"Brands undercutting us: {', '.join(c['brand'] for c in threats)}. Without explicit premium signals (claims of materials grade, sound dB, charge cycles), we rank with them on price-shopping intent and lose. Audit current bullets for genericness vs differentiation.",
            "suggested_match": "n/a",
            "suggested_bid": None,
            "metric": "premium_kw_cvr_14d",
            "target": "+15%",
        })

    # If a high-revenue competitor exists but we don't have a PAT campaign on
    # them → propose one
    high_rev = [c for c in list_c if (c.get("monthly_revenue") or 0) >= 50000]
    log = sources.get("experiment_log") or {}
    pat_already = {
        kw.lower()
        for e in log.get("active_experiments", [])
        for kw in [(e.get("element") or "")]
        if "pat" in kw.lower()
    }
    for c in high_rev:
        brand = c.get("brand", "")
        if any(brand.lower() in p for p in pat_already):
            continue
        findings.append({
            "kind": "proposed_new",
            "title": f"PAT campaign on {brand} ({c.get('asin')})",
            "listing": "fountain",
            "rationale": f"{brand} doing ~${(c.get('monthly_revenue') or 0)/1000:.0f}K/mo at ${c.get('price', 'N/A'):.2f}. Comparison-shoppers on their detail page are exactly our premium buyer. PAT bid harvests this audience.",
            "suggested_match": "PAT",
            "suggested_bid": round(min(0.60, (c.get("price") or 50) / 100), 2),
            "metric": "pat_clicks_7d",
            "target": 5,
        })

    return findings


def propose_from_review_gap(sources: dict) -> list[dict]:
    """If review velocity is too low to ladder up → propose review-driver exp."""
    findings: list[dict] = []
    intel = sources.get("competitor_intel") or {}
    us = intel.get("us") or {}
    our_reviews = us.get("reviews") or 0
    if our_reviews >= 50:
        return []
    log = sources.get("experiment_log") or {}
    has_review_exp = any(
        "review" in (e.get("element", "") + e.get("hypothesis", "")).lower()
        and e.get("status") not in ("DONE", "SUPERSEDED")
        for e in log.get("active_experiments", [])
    )
    if has_review_exp:
        return []
    findings.append({
        "kind": "proposed_new",
        "title": "Review-velocity push (we are below 50 reviews)",
        "listing": "brand",
        "rationale": f"Current reviews: {our_reviews}. Pricing ladder unlocks $42.99 at 50 reviews. Without a programmatic review-request loop the gap stays open.",
        "suggested_match": "n/a",
        "suggested_bid": None,
        "metric": "reviews_per_week",
        "target": 2.0,
    })
    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    sources = load_sources()
    if not sources.get("experiment_log"):
        print("ERROR: experiment_log.json not found.")
        return 1

    findings: dict[str, list[dict]] = {
        "to_deprecate": [],
        "to_update": [],
        "proposed_new": [],
    }

    # Outdated premises → to_deprecate
    findings["to_deprecate"].extend(detect_outdated_premises(sources))

    # Supersession candidates → to_update
    findings["to_update"].extend(detect_supersession(sources))

    # Already-bidding KW set, used by rank-momentum proposer
    log_existing_kws: set[str] = set()
    for e in sources["experiment_log"].get("active_experiments", []):
        for k in re.findall(r"[a-z][a-z ]+", (e.get("element") or "").lower()):
            log_existing_kws.add(k.strip())

    # Proposed new
    findings["proposed_new"].extend(propose_from_rank_momentum(sources, log_existing_kws))
    findings["proposed_new"].extend(propose_from_wasted_spend(sources))
    findings["proposed_new"].extend(propose_from_competitor_signals(sources))
    findings["proposed_new"].extend(propose_from_review_gap(sources))

    today = date.today().isoformat()
    payload = {
        "_generated": today,
        "_input_window": {
            "cerebro": (sources.get("cerebro_opps") or {}).get("runDate"),
            "rank_history": (sources.get("rank_history") or {}).get("runDate"),
            "kpi_window": (sources.get("daily_kpis") or {}).get("_window"),
            "competitor_intel_updated": (sources.get("competitor_intel") or {}).get("_last_updated"),
        },
        "summary": {
            "to_deprecate": len(findings["to_deprecate"]),
            "to_update": len(findings["to_update"]),
            "proposed_new": len(findings["proposed_new"]),
        },
        "findings": findings,
    }

    out_dated = DATA / f"experiment_advisor_{today}.json"
    out_latest = DATA / "experiment_advisor.json"
    out_dated.write_text(json.dumps(payload, indent=2))
    out_latest.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {out_dated.relative_to(ROOT.parent)} and experiment_advisor.json")
    print(f"  to_deprecate: {payload['summary']['to_deprecate']}")
    print(f"  to_update:    {payload['summary']['to_update']}")
    print(f"  proposed_new: {payload['summary']['proposed_new']}")
    if payload["summary"]["proposed_new"]:
        print("\nTop 5 proposed:")
        for p in payload["findings"]["proposed_new"][:5]:
            print(f"  • {p['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
