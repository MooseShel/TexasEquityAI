"""
Geo-Intelligence Service
Adds distance data to equity comps and detects external obsolescence
factors (highways, commercial adjacency, power infrastructure).

Uses Nominatim (free) for comp geocoding with Google Geocoding fallback.
"""

import logging
import math
import os
import time
import requests
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Geocoding ─────────────────────────────────────────────────────────────────

_geocode_cache: Dict[str, Optional[Dict]] = {}


def geocode_geoapify(address: str) -> Optional[Dict[str, float]]:
    """Geocode via free Geoapify API."""
    if not address or len(address) < 5:
        return None
    cache_key = address.strip().lower()
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]
    try:
        geoapify_key = os.environ.get("GEOAPIFY_API_KEY", "b3a32fdeb3e449a08a474fd3cc89bf2d")
        response = requests.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={
                "text": f"{address}, Texas",
                "apiKey": geoapify_key,
                "format": "json"
            },
            timeout=5
        )
        if response.status_code == 200:
            data = response.json().get('results', [])
            if data:
                result = {
                    "lat": float(data[0]["lat"]),
                    "lng": float(data[0]["lon"]) # Geoapify uses 'lon', but our internal standard is 'lng'
                }
                _geocode_cache[cache_key] = result
                return result
    except Exception as e:
        logger.debug(f"Geoapify geocode failed for '{address}': {e}")
    _geocode_cache[cache_key] = None
    return None


def geocode_google(address: str) -> Optional[Dict[str, float]]:
    """Geocode via Google Geocoding API (fallback)."""
    api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key or not address:
        return None
    cache_key = address.strip().lower()
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": api_key},
            timeout=5,
        )
        data = resp.json()
        if data.get("status") == "OK":
            loc = data["results"][0]["geometry"]["location"]
            result = {"lat": loc["lat"], "lng": loc["lng"]}
            _geocode_cache[cache_key] = result
            return result
    except Exception as e:
        logger.debug(f"Google geocode failed for '{address}': {e}")
    return None


def geocode(address: str) -> Optional[Dict[str, float]]:
    """Geocode with Geoapify first, Google fallback."""
    result = geocode_geoapify(address)
    if result:
        return result
    return geocode_google(address)


# ── Distance ──────────────────────────────────────────────────────────────────

def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two lat/lng points in miles."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Comp Distance Enrichment ─────────────────────────────────────────────────

def enrich_comps_with_distance(
    subject_address: str,
    equity_5: List[Dict],
    subject_coords: Optional[Dict] = None,
) -> List[Dict]:
    """
    Geocode each equity comp and add distance_mi from subject.
    Returns the same list with distance_mi and distance_rank added.
    """
    # Get subject coordinates
    if not subject_coords:
        subject_coords = geocode(subject_address)
    if not subject_coords:
        logger.warning("GeoIntel: Could not geocode subject — skipping distance enrichment")
        return equity_5

    subj_lat = subject_coords["lat"]
    subj_lng = subject_coords["lng"]

    for comp in equity_5:
        addr = comp.get("address", "")
        if not addr:
            comp["distance_mi"] = None
            continue

        coords = geocode(addr)
        if coords:
            dist = haversine_miles(subj_lat, subj_lng, coords["lat"], coords["lng"])
            comp["distance_mi"] = round(dist, 2)
            comp["comp_lat"] = coords["lat"]
            comp["comp_lng"] = coords["lng"]
        else:
            comp["distance_mi"] = None

        # Geoapify rate limit: up to 3000/day
        time.sleep(0.1)

    # Add distance rank (1 = closest)
    ranked = sorted(
        [c for c in equity_5 if c.get("distance_mi") is not None],
        key=lambda c: c["distance_mi"],
    )
    for i, c in enumerate(ranked):
        c["distance_rank"] = i + 1

    geocoded_count = sum(1 for c in equity_5 if c.get("distance_mi") is not None)
    logger.info(f"GeoIntel: Geocoded {geocoded_count}/{len(equity_5)} comps with distance")

    return equity_5


# ── External Obsolescence Detection ──────────────────────────────────────────

OBSOLESCENCE_TYPES = {
    "highway": {
        "keywords": ["highway", "freeway", "expressway", "interstate"],
        "google_types": ["route"],
        "radius_ft": 500,
        "impact_pct": 3.0,
        "description": "Major highway within {dist}ft — noise and pollution impact",
    },
    "commercial": {
        "keywords": ["shopping", "mall", "gas_station", "convenience_store"],
        "google_types": ["shopping_mall", "gas_station", "convenience_store"],
        "radius_ft": 300,
        "impact_pct": 2.0,
        "description": "Commercial property within {dist}ft — traffic and noise impact",
    },
    "industrial": {
        "keywords": ["factory", "warehouse", "industrial"],
        "google_types": ["storage", "moving_company"],
        "radius_ft": 1000,
        "impact_pct": 4.0,
        "description": "Industrial facility within {dist}ft — environmental and noise impact",
    },
    "power": {
        "keywords": ["substation", "power plant", "electrical"],
        "google_types": ["electrician"],  # Google Places doesn't have a great type for this
        "radius_ft": 500,
        "impact_pct": 2.5,
        "description": "Power infrastructure within {dist}ft — visual and EMF concerns",
    },
}


def check_external_obsolescence(lat: float, lng: float) -> Dict:
    """
    Check for external obsolescence factors near the property.
    Uses Google Places Nearby Search if API key is available.
    Returns list of detected factors with estimated impact.
    """
    api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY") or os.getenv("GOOGLE_API_KEY")
    result = {
        "factors": [],
        "total_impact_pct": 0.0,
        "checked": False,
    }

    if not api_key:
        logger.debug("GeoIntel: No Google API key — skipping external obsolescence check")
        return result

    result["checked"] = True

    for obs_type, config in OBSOLESCENCE_TYPES.items():
        radius_m = int(config["radius_ft"] * 0.3048)  # Convert ft to meters
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params={
                    "location": f"{lat},{lng}",
                    "radius": radius_m,
                    "type": "|".join(config["google_types"]),
                    "key": api_key,
                },
                timeout=5,
            )
            data = resp.json()
            if data.get("status") == "OK" and data.get("results"):
                # Found something nearby
                nearest = data["results"][0]
                name = nearest.get("name", obs_type)
                place_lat = nearest["geometry"]["location"]["lat"]
                place_lng = nearest["geometry"]["location"]["lng"]
                dist_mi = haversine_miles(lat, lng, place_lat, place_lng)
                dist_ft = int(dist_mi * 5280)

                factor = {
                    "type": obs_type,
                    "name": name,
                    "distance_ft": dist_ft,
                    "impact_pct": config["impact_pct"],
                    "description": config["description"].format(dist=dist_ft),
                }
                result["factors"].append(factor)
                result["total_impact_pct"] += config["impact_pct"]
                logger.info(f"GeoIntel: Found {obs_type} '{name}' at {dist_ft}ft")

            time.sleep(0.1)  # Rate limiting

        except Exception as e:
            logger.debug(f"GeoIntel: Places API check failed for {obs_type}: {e}")

    if result["factors"]:
        result["total_impact_pct"] = min(15.0, result["total_impact_pct"])  # Cap at 15%
        logger.info(f"GeoIntel: {len(result['factors'])} obsolescence factors, total impact: {result['total_impact_pct']:.1f}%")

    return result
