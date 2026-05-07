"""Backfill PPC_Analysis_<date>.json files from raw ads_<date>.json pulls.

Thin CLI wrapper around amazon_api.ppc_analysis. Used to retroactively
generate PPC_Analysis files for any historical ads pull on disk.

Usage:
    python3 scripts/backfill_ppc_analysis.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make project root importable so `amazon_api` resolves
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from amazon_api.ppc_analysis import (  # noqa: E402
    build_ppc_analysis,
    load_ads_files,
    write_ppc_analysis,
)
from common.manifest_utils import update_manifest_bucket  # noqa: E402

DASHBOARD_DATA = ROOT.parent / "public" / "data"
MANIFEST = DASHBOARD_DATA / "manifest.json"


def main() -> int:
    ads_by_date = load_ads_files()
    if not ads_by_date:
        print("No ads_*.json files found.", file=sys.stderr)
        return 1

    written = []
    for d in sorted(ads_by_date.keys()):
        payload = build_ppc_analysis(d, ads_by_date)
        if payload is None:
            continue
        out_path = write_ppc_analysis(d, payload)
        s = payload["summary"]
        print(
            f"  wrote {out_path.name} — ACoS_7d={s['overall_acos_7d']}, "
            f"spend_7d=${s['total_spend_7d']}, sales_7d=${s['total_attributed_sales_7d']}, "
            f"days_with_data={s['_days_with_data']}"
        )
        written.append(out_path.name)

    if written:
        update_manifest_bucket(MANIFEST, "sc_data", written)
    print(f"\nDone. {len(written)} files written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
