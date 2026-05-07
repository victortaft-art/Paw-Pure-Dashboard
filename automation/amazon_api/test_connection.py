"""First-call smoke test. Proves credentials work end-to-end.

Calls /sellers/v1/marketplaceParticipations — lowest-privilege endpoint,
doesn't require any special role. If this returns 200, LWA refresh
works and your app is correctly authorized.

Run:
    cd amazon_api
    python3 test_connection.py
"""
import json
from sp_api_client import SPAPIClient


def main():
    client = SPAPIClient()

    print("→ Refreshing LWA access token...")
    token = client._get_access_token()
    print(f"  Got access token: {token[:20]}... (truncated)")

    print("\n→ Calling /sellers/v1/marketplaceParticipations ...")
    resp = client.get("/sellers/v1/marketplaceParticipations")

    print(f"  Status: {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        print("\n✓ SUCCESS — you are connected to SP-API.\n")
        print("Marketplaces you are registered in:")
        for p in data.get("payload", []):
            mp = p.get("marketplace", {})
            participation = p.get("participation", {})
            print(
                f"  - {mp.get('name')} "
                f"(id={mp.get('id')}, country={mp.get('countryCode')}, "
                f"hasSuspendedListings={participation.get('hasSuspendedListings')})"
            )
    else:
        print(f"\n✗ FAILED — status {resp.status_code}")
        print("Response body:")
        try:
            print(json.dumps(resp.json(), indent=2))
        except Exception:
            print(resp.text)


if __name__ == "__main__":
    main()
