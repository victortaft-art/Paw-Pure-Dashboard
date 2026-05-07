"""Single, generic manifest-update helper.

Replaces four near-identical copies that previously lived in
helium10_pipeline/cerebro_ingest.py, rank_tracker_ingest.py,
competitor_snapshot.py, and scripts/backfill_ppc_analysis.py.

Per docs/ARCHITECTURE.md §2: any script that writes a new file under
dashboard/public/data/<folder>/ MUST register it via this function so the
dashboard's loader can find it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def update_manifest_bucket(
    manifest_path: Path,
    bucket: str,
    filenames: Iterable[str],
) -> None:
    """Add `filenames` to manifest[bucket], deduplicated and lex-sorted.

    Silent no-op if the manifest file doesn't exist or is unparseable —
    this is intentional so a broken manifest doesn't break the producing
    script. Re-run update_manifest.py to regenerate from disk if needed.

    Args:
        manifest_path: absolute path to manifest.json
        bucket: top-level key (e.g. "sc_data", "kw_data", "competitor_snapshots")
        filenames: filenames (basenames only) to register

    Example:
        update_manifest_bucket(
            Path(".../dashboard/public/data/manifest.json"),
            "kw_data",
            ["cerebro_opportunities_2026-04-30.json"],
        )
    """
    if not manifest_path.exists():
        return
    try:
        m = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError):
        return
    existing = set(m.get(bucket, []) or [])
    existing.update(fn for fn in filenames if fn)
    m[bucket] = sorted(existing)
    manifest_path.write_text(json.dumps(m, indent=2))
