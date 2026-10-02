"""Distance and geofence helpers."""
import math

EARTH_RADIUS_M = 6_371_000


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres (haversine formula)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return distance_m(lat1, lng1, lat2, lng2) / 1000


def inside_geofence(lat: float, lng: float, centre_lat: float, centre_lng: float, radius_m: float) -> bool:
    return distance_m(lat, lng, centre_lat, centre_lng) <= radius_m
