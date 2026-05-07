"""Central config for all Paw Pure API pullers.

Single source of truth for ASINs, SKUs, paths, and marketplace.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# PROJECT_ROOT is dashboard/automation/. Dashboard data lives at
# dashboard/public/data — one level up + public/data.
DASHBOARD_DATA = PROJECT_ROOT.parent / "public" / "data"

# ============================================================
# Products
# ============================================================
PRODUCTS = {
    "fountain": {
        "asin": "B0DJHQVJYF",
        "sku": "8V-EUFB-4UF2",
        "name": "Paw Pure Wireless Pet Water Fountain",
        "price": 49.99,
        "amazon_fee": 15.50,
        "cogs": 17.58,
    },
    "filters": {
        "asin": "B0FWXJ1GKT",
        "sku": "97-VFBK-LUWE",
        "name": "Paw Pure Replacement Filter Pack",
        "price": 20.00,
        "amazon_fee": 6.95,
        "cogs": 3.97,
    },
    "bundle": {
        "asin": "B0GMDM6CG2",
        "sku": None,  # virtual bundle — no standalone FBA SKU
        "name": "Paw Pure Fountain + Filter Bundle",
        "price": 64.99,
        "amazon_fee": 15.25,
        "cogs": 21.55,
    },
}

ASIN_TO_KEY = {p["asin"]: key for key, p in PRODUCTS.items()}
SKU_TO_KEY = {p["sku"]: key for key, p in PRODUCTS.items() if p["sku"]}

# ============================================================
# Marketplace
# ============================================================
MARKETPLACE_ID = "ATVPDKIKX0DER"  # Amazon.com US

# ============================================================
# Output paths (absolute, match existing dashboard folders)
# ============================================================
SC_DATA_DIR = DASHBOARD_DATA / "sc_data"
PL_DATA_DIR = DASHBOARD_DATA / "pl_data"
MANIFEST_FILE = DASHBOARD_DATA / "manifest.json"

# Raw API dumps (gitignored, for debugging)
RAW_DUMP_DIR = PROJECT_ROOT / "amazon_api" / "data" / "raw"
LOG_DIR = PROJECT_ROOT / "amazon_api" / "data" / "logs"

# ============================================================
# Pipeline behavior
# ============================================================
ATOMIC_WRITES = True  # write to .tmp + rename
PRESERVE_ON_FAILURE = True  # don't touch files if any puller fails
