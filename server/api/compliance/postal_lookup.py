"""Postal-code lookup via Postali (MX/CO/ES) and Zippopotam (everywhere else)."""

from __future__ import annotations

import re

import requests

POSTALI_COUNTRIES = {"MX": "mx", "CO": "co", "ES": "es"}
_TIMEOUT = 8


def normalize_postal_code(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()


def postal_code_is_complete(country: str, code: str) -> bool:
    country = (country or "").upper()
    code = normalize_postal_code(code)
    if country in {"MX", "US", "ES"}:
        return bool(re.fullmatch(r"\d{5}", code))
    if country == "CO":
        return bool(re.fullmatch(r"\d{6}", code))
    if country == "CA":
        return len(code) == 6
    return 4 <= len(code) <= 12


def lookup_postal_code(country: str, postal_code: str) -> dict | None:
    country = (country or "").upper()
    code = normalize_postal_code(postal_code)
    if not postal_code_is_complete(country, code):
        return None
    if country in POSTALI_COUNTRIES:
        return _lookup_postali(POSTALI_COUNTRIES[country], code)
    return _lookup_zippopotam(country, code)


def _lookup_postali(country_slug: str, code: str) -> dict | None:
    url = f"https://postali.app/api/v1/{country_slug}/cp/{code.lower()}"
    response = requests.get(url, timeout=_TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get("error"):
        return None
    settlements = data.get("asentamientos") or []
    if not isinstance(settlements, list):
        settlements = []
    neighborhoods = []
    cities = []
    for item in settlements:
        if not isinstance(item, dict):
            continue
        name = str(item.get("nombre") or "").strip()
        city = str(item.get("ciudad") or "").strip()
        if name and name not in neighborhoods:
            neighborhoods.append(name)
        if city and city not in cities:
            cities.append(city)
    return {
        "state": str(data.get("estado") or "").strip(),
        "municipality": str(data.get("municipio") or "").strip(),
        "city": cities[0] if cities else "",
        "neighborhoods": neighborhoods,
    }


def _lookup_zippopotam(country: str, code: str) -> dict | None:
    url = f"https://api.zippopotam.us/{country.lower()}/{code}"
    response = requests.get(url, timeout=_TIMEOUT)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    places = data.get("places") if isinstance(data, dict) else None
    if not isinstance(places, list) or not places:
        return None
    first = places[0] if isinstance(places[0], dict) else {}
    neighborhoods = []
    for place in places:
        if not isinstance(place, dict):
            continue
        name = str(place.get("place name") or "").strip()
        if name and name not in neighborhoods:
            neighborhoods.append(name)
    return {
        "state": str(first.get("state") or "").strip(),
        "municipality": "",
        "city": str(first.get("place name") or "").strip(),
        "neighborhoods": neighborhoods,
    }
