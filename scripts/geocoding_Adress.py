"""
Geocoding of the Start and Destination address.

Provides a small helper around the OpenStreetMap Nominatim API.
Includes an optional offline stub for a few Bern locations via env var OFFLINE_GEOCODE_STUB.

Usage:
    geocoder = Geocoder(user_agent="WPR2_Project_Group_05/0.1 (contact: your-email@example.com)")
    res = geocoder.geocode("Bern Bahnhof")

    start, dest = geocode_pair(geocoder, "Zytglogge, Bern", "Bern, Bahnhof")
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
import os
import time
import requests

NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")

@dataclass
class GeocodeResult:
    query: str
    lat: float
    lon: float
    display_name: str
    raw: Dict[str, Any]

class Geocoder:
    def __init__(self, user_agent: str, email: Optional[str] = None, throttle_seconds: float = 1.0):
        if not user_agent:
            raise ValueError("user_agent is required for Nominatim usage policy")
        self.user_agent = user_agent
        self.email = email
        self.throttle_seconds = throttle_seconds
        self._last_call_ts = 0.0

    def _throttle(self):
        # Basic polite rate limiting: ensure at most ~1 request/sec
        now = time.time()
        delta = now - self._last_call_ts
        if delta < self.throttle_seconds:
            time.sleep(self.throttle_seconds - delta)
        self._last_call_ts = time.time()

    def geocode(self, address: str, *, country_codes: str = "ch", limit: int = 1, city_hint: Optional[str] = None, timeout: int = 8) -> Optional[GeocodeResult]:
        if not address or not address.strip():
            raise ValueError("address must be a non-empty string")

        # Optional offline stub for a few common points in Bern (useful in dev/no-internet environments)
        if os.getenv("OFFLINE_GEOCODE_STUB", "").lower() in {"1", "true", "yes"}:
            stub = _offline_stub(address)
            if stub:
                return stub

        q = address.strip()
        if city_hint and city_hint.lower() not in q.lower():
            q = f"{q}, {city_hint}"

        params = {
            "q": q,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": str(limit),
            "countrycodes": country_codes,
        }
        headers = {"User-Agent": self.user_agent}
        if self.email:
            headers["From"] = self.email  # per Nominatim's recommended contact header

        self._throttle()
        try:
            resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            # Network error, timeout, or HTTP error
            raise Exception(f"Failed to contact geocoding service: {str(e)}")
        except ValueError as e:
            # JSON parsing error
            raise Exception(f"Invalid response from geocoding service: {str(e)}")

        if not data:
            return None
        top = data[0]
        try:
            lat = float(top["lat"])  # type: ignore[index]
            lon = float(top["lon"])  # type: ignore[index]
        except (KeyError, ValueError, TypeError):
            return None
        return GeocodeResult(query=address, lat=lat, lon=lon, display_name=top.get("display_name", address), raw=top)

def geocode_pair(geocoder: Geocoder, start_address: str, dest_address: str, *, city_hint: Optional[str] = "Bern") -> Tuple[Optional[GeocodeResult], Optional[GeocodeResult]]:
    start = geocoder.geocode(start_address, city_hint=city_hint)
    dest = geocoder.geocode(dest_address, city_hint=city_hint)
    return start, dest


def _offline_stub(address: str) -> Optional[GeocodeResult]:
    # Very small mapping for Bern landmarks to avoid network calls in offline mode.
    mapping = {
        "bern bahnhof": (46.9489, 7.4391, "Bern, Bahnhof"),
        "bahnhof bern": (46.9489, 7.4391, "Bern, Bahnhof"),
        "zytglogge": (46.9479, 7.4474, "Zytglogge, Bern"),
        "bundesplatz": (46.9470, 7.4441, "Bundesplatz, Bern"),
        "universität bern": (46.9480, 7.4386, "Universität Bern"),
    }
    key = address.strip().lower()
    # also try without trailing ", bern"
    key = key.replace(", bern", "").strip()
    if key in mapping:
        lat, lon, name = mapping[key]
        return GeocodeResult(query=address, lat=lat, lon=lon, display_name=name, raw={"source": "offline_stub"})
    return None
