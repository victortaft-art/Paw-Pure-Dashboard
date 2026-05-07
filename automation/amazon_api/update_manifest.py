"""Update dashboard/public/data/manifest.json with any new data files.

Reads current manifest, scans sc_data/ and pl_data/ for filenames, merges
them into the manifest's file lists, and writes atomically. De-duplicates
and preserves existing ordering.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import SC_DATA_DIR, PL_DATA_DIR, MANIFEST_FILE  # noqa: E402


def load_manifest():
    if not MANIFEST_FILE.exists():
        return {}
    with open(MANIFEST_FILE) as f:
        return json.load(f)


def scan_files(directory, prefix):
    """Return sorted list of files matching `{prefix}_*.json` in directory."""
    if not directory.exists():
        return []
    files = sorted(p.name for p in directory.glob(f"{prefix}_*.json"))
    return files


def find_list_key(manifest, dir_name):
    """Find which manifest key corresponds to a data directory.

    Manifest shapes vary across projects; we look for any list-valued entry
    whose first filename starts with the given prefix or whose key contains
    the dir name.
    """
    if not isinstance(manifest, dict):
        return None
    # Direct key match
    for k in (dir_name, f"{dir_name}_files", f"{dir_name}Files"):
        if k in manifest and isinstance(manifest[k], list):
            return k
    # Heuristic: scan list-valued fields
    for k, v in manifest.items():
        if isinstance(v, list) and v and isinstance(v[0], str):
            if dir_name in k.lower():
                return k
    return None


def merge_into_manifest(manifest, key, new_files):
    """Merge new_files into manifest[key], de-duplicating, preserving order."""
    existing = manifest.get(key, [])
    seen = set(existing)
    for f in new_files:
        if f not in seen:
            existing.append(f)
            seen.add(f)
    manifest[key] = sorted(existing)  # sort keeps date-named files in order
    return manifest


def update():
    manifest = load_manifest()
    sc_files = scan_files(SC_DATA_DIR, "SC_Data")
    pl_files = scan_files(PL_DATA_DIR, "PL_Data")

    sc_key = find_list_key(manifest, "sc_data") or "sc_data"
    pl_key = find_list_key(manifest, "pl_data") or "pl_data"

    manifest = merge_into_manifest(manifest, sc_key, sc_files)
    manifest = merge_into_manifest(manifest, pl_key, pl_files)

    # Atomic write
    tmp = MANIFEST_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2)
    tmp.replace(MANIFEST_FILE)
    print(f"✓ Updated {MANIFEST_FILE}", flush=True)
    print(f"  {sc_key}: {len(manifest[sc_key])} files", flush=True)
    print(f"  {pl_key}: {len(manifest[pl_key])} files", flush=True)


if __name__ == "__main__":
    update()
