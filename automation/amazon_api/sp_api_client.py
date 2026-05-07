"""Thin SP-API client: handles LWA token refresh + signed requests.

Usage:
    client = SPAPIClient()
    resp = client.get("/sellers/v1/marketplaceParticipations")
    print(resp.json())
"""
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class SPAPIClient:
    LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"

    def __init__(self):
        self.client_id = os.environ["SP_API_CLIENT_ID"]
        self.client_secret = os.environ["SP_API_CLIENT_SECRET"]
        self.refresh_token = os.environ["SP_API_REFRESH_TOKEN"]
        self.endpoint = os.environ.get(
            "SP_API_ENDPOINT", "https://sellingpartnerapi-na.amazon.com"
        )
        self.marketplace_id = os.environ.get(
            "SP_API_MARKETPLACE_ID", "ATVPDKIKX0DER"
        )
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
        # Amazon returns expires_in seconds (usually 3600). Refresh 60s early.
        self._access_token_expiry = time.time() + data["expires_in"] - 60

    def _get_access_token(self):
        if not self._access_token or time.time() >= self._access_token_expiry:
            self._refresh_access_token()
        return self._access_token

    def request(self, method, path, params=None, json=None):
        url = f"{self.endpoint}{path}"
        headers = {
            "x-amz-access-token": self._get_access_token(),
            "Content-Type": "application/json",
        }
        resp = requests.request(
            method, url, headers=headers, params=params, json=json, timeout=60
        )
        return resp

    def get(self, path, params=None):
        return self.request("GET", path, params=params)

    def post(self, path, json=None):
        return self.request("POST", path, json=json)
