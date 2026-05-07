"""Safely check that .env values look right (without leaking secrets)."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def check(key, expected_prefix=None, expected_min_len=10):
    v = os.environ.get(key, "")
    if not v:
        print(f"  ✗ {key}: EMPTY")
        return
    # check for whitespace / quotes
    stripped = v.strip().strip('"').strip("'")
    issues = []
    if v != stripped:
        issues.append("HAS SURROUNDING WHITESPACE OR QUOTES")
    if expected_prefix and not stripped.startswith(expected_prefix):
        issues.append(f"DOES NOT START WITH '{expected_prefix}'")
    if len(stripped) < expected_min_len:
        issues.append(f"TOO SHORT ({len(stripped)} chars)")

    status = "✓" if not issues else "✗"
    mask = stripped[:12] + "..." + stripped[-4:] if len(stripped) > 20 else stripped[:4] + "..."
    print(f"  {status} {key}: len={len(stripped)}, preview={mask}")
    for issue in issues:
        print(f"       ⚠ {issue}")


print("Checking .env values:\n")
check("SP_API_CLIENT_ID", "amzn1.application-oa2-client.", 40)
check("SP_API_CLIENT_SECRET", "amzn1.oa2-cs.v1.", 40)
check("SP_API_REFRESH_TOKEN", "Atzr|", 100)
check("SP_API_SELLER_ID", "A", 13)
check("SP_API_MARKETPLACE_ID", "ATVPDKIKX0DER", 13)
