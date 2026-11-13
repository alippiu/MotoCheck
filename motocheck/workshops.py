import math
import re
import threading
import time
from urllib.parse import urlparse

import requests


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
SEARCH_RADIUS_METERS = 5000
QUERY_RADIUS_METERS = SEARCH_RADIUS_METERS + 300
CACHE_SECONDS = 300
REQUEST_TIMEOUT_SECONDS = (3, 8)
REQUEST_ATTEMPTS = 2
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
_cache = {}
_cache_lock = threading.Lock()


class WorkshopSearchError(Exception):
    """Raised when the external workshop data provider cannot be used."""


def _address(tags):
    parts = (
        tags.get("addr:street"),
        tags.get("addr:suburb"),
        tags.get("addr:city"),
        tags.get("addr:postcode"),
    )
    parts = [_tag_text(part, 120) for part in parts]
    return ", ".join(part for part in parts if part) or None


def _tag_text(value, limit):
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value[:limit] or None


def _distance_meters(latitude, longitude, target_latitude, target_longitude):
    latitude = math.radians(latitude)
    target_latitude = math.radians(target_latitude)
    latitude_delta = target_latitude - latitude
    longitude_delta = math.radians(target_longitude - longitude)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(latitude)
        * math.cos(target_latitude)
        * math.sin(longitude_delta / 2) ** 2
    )
    haversine = min(1.0, max(0.0, haversine))
    return 6371000 * 2 * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def _within_search_radius(workshops, latitude, longitude):
    matches = [
        workshop
        for workshop in workshops
        if _distance_meters(
            latitude,
            longitude,
            workshop["latitude"],
            workshop["longitude"],
        ) <= SEARCH_RADIUS_METERS
    ]
    return sorted(
        matches,
        key=lambda workshop: _distance_meters(
            latitude,
            longitude,
            workshop["latitude"],
            workshop["longitude"],
        ),
    )


def _workshop_from_element(element):
    if not isinstance(element, dict):
        return None
    tags = element.get("tags", {})
    if not isinstance(tags, dict):
        return None
    repair_tag = tags.get("motorcycle:repair")
    if tags.get("shop") != "motorcycle_repair" and not (
        isinstance(repair_tag, str)
        and repair_tag.strip().lower() not in {"", "no", "false"}
    ):
        return None
    coordinates = element.get("center", element)
    if not isinstance(coordinates, dict):
        return None
    try:
        if isinstance(coordinates.get("lat"), bool) or isinstance(coordinates.get("lon"), bool):
            return None
        latitude = float(coordinates["lat"])
        longitude = float(coordinates["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if (
        not math.isfinite(latitude)
        or not math.isfinite(longitude)
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None

    raw_website = tags.get("contact:website") or tags.get("website")
    website = _tag_text(raw_website, 2048)
    if website:
        try:
            parsed_website = urlparse(website)
            hostname = parsed_website.hostname
            port = parsed_website.port
            if (
                not isinstance(raw_website, str)
                or len(raw_website) > 2048
                or parsed_website.scheme.lower() not in {"http", "https"}
                or not hostname
                or any(character.isspace() for character in website)
                or parsed_website.username
                or parsed_website.password
                or (port is not None and not 1 <= port <= 65535)
            ):
                website = None
        except (TypeError, ValueError):
            website = None
    phone = _tag_text(tags.get("contact:phone") or tags.get("phone"), 30)
    if phone:
        digit_count = len(re.sub(r"\D", "", phone))
        if not re.fullmatch(r"[+\d().\-\s]{3,30}", phone) or not 3 <= digit_count <= 20:
            phone = None

    element_type = element.get("type")
    element_id = element.get("id")
    valid_id = (
        isinstance(element_id, int)
        and not isinstance(element_id, bool)
        and element_id > 0
    ) or (
        isinstance(element_id, str)
        and element_id.isdigit()
        and int(element_id) > 0
    )
    if element_type not in {"node", "way", "relation"} or not valid_id:
        return None
    return {
        "id": f"{element_type}/{element_id}",
        "name": _tag_text(tags.get("name"), 200),
        "address": _address(tags),
        "phone": phone,
        "website": website,
        "latitude": latitude,
        "longitude": longitude,
        "osm_url": f"https://www.openstreetmap.org/{element_type}/{element_id}",
    }


def _fetch_workshops(latitude, longitude):
    query = (
        "[out:json][timeout:6];("
        f'node["shop"="motorcycle_repair"](around:{QUERY_RADIUS_METERS},{latitude},{longitude});'
        f'way["shop"="motorcycle_repair"](around:{QUERY_RADIUS_METERS},{latitude},{longitude});'
        f'relation["shop"="motorcycle_repair"](around:{QUERY_RADIUS_METERS},{latitude},{longitude});'
        f'node["motorcycle:repair"]["motorcycle:repair"!="no"](around:{QUERY_RADIUS_METERS},{latitude},{longitude});'
        f'way["motorcycle:repair"]["motorcycle:repair"!="no"](around:{QUERY_RADIUS_METERS},{latitude},{longitude});'
        f'relation["motorcycle:repair"]["motorcycle:repair"!="no"](around:{QUERY_RADIUS_METERS},{latitude},{longitude});'
        ");out center tags;"
    )
    data = None
    for attempt in range(REQUEST_ATTEMPTS):
        try:
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                headers={
                    "User-Agent": "MotoCheck/2.0 (educational motorcycle workshop finder)",
                    "Accept": "application/json",
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
                verify=True,
                allow_redirects=False,
            )
            if 300 <= response.status_code < 400:
                raise WorkshopSearchError(
                    "Penyedia OpenStreetMap mengalihkan permintaan; pengalihan tidak diikuti demi melindungi data lokasi."
                )
            response.raise_for_status()
            data = response.json()
            break
        except requests.exceptions.SSLError as error:
            raise WorkshopSearchError(
                "Sertifikat TLS penyedia OpenStreetMap gagal diverifikasi; pencarian langsung dihentikan demi keamanan."
            ) from error
        except requests.exceptions.HTTPError as error:
            status = error.response.status_code if error.response is not None else None
            if status in RETRYABLE_HTTP_STATUSES and attempt + 1 < REQUEST_ATTEMPTS:
                time.sleep(0.25)
                continue
            raise WorkshopSearchError(
                f"Penyedia OpenStreetMap merespons dengan HTTP {status}."
            ) from error
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as error:
            if attempt + 1 < REQUEST_ATTEMPTS:
                time.sleep(0.25)
                continue
            raise WorkshopSearchError(
                "Penyedia data OpenStreetMap tidak dapat dihubungi saat ini."
            ) from error
        except requests.exceptions.JSONDecodeError as error:
            if attempt + 1 < REQUEST_ATTEMPTS:
                time.sleep(0.25)
                continue
            raise WorkshopSearchError(
                "Penyedia data OpenStreetMap mengirim respons yang tidak dapat dibaca."
            ) from error
        except requests.exceptions.RequestException as error:
            raise WorkshopSearchError(
                "Permintaan ke penyedia data OpenStreetMap gagal."
            ) from error

    if not isinstance(data, dict):
        raise WorkshopSearchError("Penyedia data mengirim respons yang tidak dapat dibaca.")
    elements = data.get("elements")
    if not isinstance(elements, list):
        raise WorkshopSearchError("Penyedia data mengirim respons yang tidak dapat dibaca.")
    workshops = []
    seen = set()
    for element in elements:
        workshop = _workshop_from_element(element)
        if workshop and workshop["id"] not in seen:
            seen.add(workshop["id"])
            workshops.append(workshop)
    return workshops


def find_workshops(latitude, longitude):
    if isinstance(latitude, bool) or isinstance(longitude, bool):
        raise ValueError("Koordinat lokasi tidak valid.")
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError) as error:
        raise ValueError("Koordinat lokasi tidak valid.") from error
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("Koordinat lokasi tidak valid.")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Koordinat lokasi berada di luar rentang yang valid.")

    now = time.monotonic()
    cache_key = (round(latitude, 3), round(longitude, 3))
    with _cache_lock:
        expired_keys = [
            key for key, cached_value in _cache.items()
            if now - cached_value[0] >= CACHE_SECONDS
        ]
        for key in expired_keys:
            _cache.pop(key, None)
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < CACHE_SECONDS:
            return {
                "workshops": _within_search_radius(cached[1], latitude, longitude),
                "cached": True,
            }

    workshops = _fetch_workshops(latitude, longitude)
    with _cache_lock:
        if len(_cache) >= 128:
            _cache.pop(next(iter(_cache)))
        _cache[cache_key] = (now, workshops)
    return {
        "workshops": _within_search_radius(workshops, latitude, longitude),
        "cached": False,
    }


def clear_cache():
    with _cache_lock:
        _cache.clear()
