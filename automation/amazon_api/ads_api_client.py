"""Amazon Advertising API client: handles LWA token refresh.

The Advertising API uses the same LWA OAuth flow as SP-API but:
  - Different base URL: https://advertising-api.amazon.com (NA)
  - Authorization: Bearer {token}  (not x-amz-access-token)
  - Extra header: Amazon-Advertising-API-ClientId = client_id
  - Extra header: Amazon-Advertising-API-Scope = profile_id

Regional endpoints:
  NA (US/CA/MX/BR): https://advertising-api.amazon.com
  EU (UK/DE/FR/etc): https://advertising-api-eu.amazon.com
  FE (JP/AU):       https://advertising-api-fe.amazon.com

Credentials: reuses SP_API_* env vars by default, or dedicated ADS_* vars
if present (useful if the Ads app is separate from the SP-API app).

Required env var:
  ADS_API_PROFILE_ID  — advertising profile ID for this seller account.
  If not set, call get_profiles() to discover it.
  ADS_API_CLIENT_ID / ADS_API_CLIENT_SECRET / ADS_API_REFRESH_TOKEN
  Optional: falls back to SP_API_* vars if the same LWA app covers both APIs.
"""
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class AdsAPIClient:
    LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
    BASE_URL = "https://advertising-api.amazon.com"

    def __init__(self):
        # Prefer dedicated ADS_API_ vars; fall back to SP-API LWA credentials
        self.client_id = (
            os.environ.get("ADS_API_CLIENT_ID") or os.environ["SP_API_CLIENT_ID"]
        )
        self.client_secret = (
            os.environ.get("ADS_API_CLIENT_SECRET") or os.environ["SP_API_CLIENT_SECRET"]
        )
        self.refresh_token = (
            os.environ.get("ADS_API_REFRESH_TOKEN") or os.environ["SP_API_REFRESH_TOKEN"]
        )
        self.profile_id = os.environ.get("ADS_API_PROFILE_ID")
        self._access_token = None
        self._access_token_expiry = 0

    def _refresh_access_token(self):
        resp = requests.post(
            self.LWA_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._access_token_expiry = time.time() + data["expires_in"] - 60

    def _get_access_token(self):
        if not self._access_token or time.time() >= self._access_token_expiry:
            self._refresh_access_token()
        return self._access_token

    def _headers(self, include_scope=True):
        h = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Amazon-Advertising-API-ClientId": self.client_id,
            "Content-Type": "application/json",
        }
        if include_scope and self.profile_id:
            h["Amazon-Advertising-API-Scope"] = str(self.profile_id)
        return h

    def get_profiles(self):
        """List all advertising profiles (no scope header needed)."""
        resp = requests.get(
            f"{self.BASE_URL}/v2/profiles",
            headers=self._headers(include_scope=False),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def get(self, path, params=None):
        resp = requests.get(
            f"{self.BASE_URL}{path}",
            headers=self._headers(),
            params=params,
            timeout=60,
        )
        return resp

    def post(self, path, json=None):
        resp = requests.post(
            f"{self.BASE_URL}{path}",
            headers=self._headers(),
            json=json,
            timeout=60,
        )
        return resp
