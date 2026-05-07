"""One-time helper: paste refresh_token, saves to .env."""
import re
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
token = input("Paste refresh_token value (just the Atzr|... string, no quotes): ").strip()

if not token.startswith("Atzr|"):
    raise SystemExit("ERROR: refresh tokens start with 'Atzr|'. Aborting.")

content = env_path.read_text()
if "ADS_API_REFRESH_TOKEN=" in content:
    new_content = re.sub(
        r"ADS_API_REFRESH_TOKEN=.*",
        f"ADS_API_REFRESH_TOKEN={token}",
        content,
    )
else:
    new_content = content.rstrip() + f"\nADS_API_REFRESH_TOKEN={token}\n"

env_path.write_text(new_content)
print(f"Saved. Token length: {len(token)} chars.")
