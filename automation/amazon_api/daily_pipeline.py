"""End-to-end daily pipeline: pull → compose → derive → write → update manifest.

Entry point for both the local Flask refresh endpoint and the launchd cron job.
Exits non-zero if any step fails so cron + Flask can surface the error
WITHOUT corrupting existing JSON files (the composers write atomically).

Steps (in order):
  1.  amazon_api/build_sc_data → SC_Data_<date>.json + PPC_Analysis_<date>.json
  2.  amazon_api/build_pl_data → PL_Data_<date>.json
  3.  amazon_api/update_manifest → manifest.json
  4.  scripts/backfill_ppc_analysis → backfill any missing PPC_Analysis files
  5.  scripts/build_daily_kpis_history → daily_kpis_history.json
  6.  scripts/build_keyword_history → keyword_history.json
  7.  helium10_pipeline/experiment_advisor → experiment_advisor.json

Steps 4-7 are optional — failures log warnings but don't abort the pipeline.
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Make project root importable so cross-package imports resolve cleanly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_sc_data import compose as compose_sc  # noqa: E402
from build_pl_data import compose as compose_pl  # noqa: E402
from update_manifest import update as update_manifest  # noqa: E402


def _run_optional(label: str, func) -> bool:
    """Run an optional pipeline step. Log warning on failure, never raise."""
    try:
        print(f"\n→ {label}", flush=True)
        func()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ {label} skipped: {e}", flush=True)
        return False


def run():
    started = datetime.now()
    print(f"\n╔══ Pipeline start: {started.isoformat()} ══╗", flush=True)

    try:
        # Step 1: pullers + SC_Data + PPC_Analysis (today's day)
        sc_data, puller_outputs = compose_sc()

        # Step 2: PL_Data from in-memory puller outputs
        pl_data = compose_pl(puller_outputs)

        # Step 3: register any newly-written files in manifest
        update_manifest()

    except Exception as e:  # noqa: BLE001
        print(f"\n✗ Pipeline FAILED at core stage: {e}", flush=True)
        print("-" * 60, flush=True)
        traceback.print_exc()
        print("-" * 60, flush=True)
        print("Existing JSON files were NOT modified (atomic writes).", flush=True)
        sys.exit(1)

    # Steps 4-7: derived data builders. Each is optional — a failure here
    # leaves the dashboard in a slightly stale state but doesn't lose data.
    print(f"\n── Running derived-data builders ──", flush=True)

    # Step 4 — backfill PPC analysis for any historical ads files that
    # don't yet have a corresponding PPC_Analysis file
    def _backfill_ppc():
        from scripts.backfill_ppc_analysis import main as backfill_main
        backfill_main()
    _run_optional("[4/7] Backfill PPC_Analysis", _backfill_ppc)

    # Step 5 — daily KPI timeseries (Spend × Sessions × CVR for the chart)
    def _kpi_history():
        from scripts.build_daily_kpis_history import main as kpi_main
        kpi_main()
    _run_optional("[5/7] Build daily_kpis_history.json", _kpi_history)

    # Step 6 — per-keyword 1d/7d/30d aggregations for the Top Keywords table
    def _keyword_history():
        from scripts.build_keyword_history import main as kw_main
        kw_main()
    _run_optional("[6/7] Build keyword_history.json", _keyword_history)

    # Step 7 — refresh advisor recommendations (reads ALL the above)
    def _advisor():
        from helium10_pipeline.experiment_advisor import main as advisor_main
        advisor_main()
    _run_optional("[7/7] Refresh experiment advisor", _advisor)

    elapsed = (datetime.now() - started).total_seconds()
    print(f"\n╚══ Pipeline OK ({elapsed:.0f}s) ══╝", flush=True)
    return sc_data, pl_data


if __name__ == "__main__":
    run()
