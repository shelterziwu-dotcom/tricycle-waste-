"""Capacity-aware job matching.

Only collectors who are close enough AND have space for the job are
considered. Candidates are ranked by:

    score = w1 * (1 - distance / radius)
          + w2 * (rating / 5)
          + w3 * (waiting_time / max_waiting_time)

The waiting-time term spreads jobs fairly between collectors.
"""
from dataclasses import dataclass

from app.services import geo, load

DEFAULT_RADIUS_KM = 3.0
MAX_WAIT_MINUTES = 60.0
WEIGHTS = (0.5, 0.3, 0.2)  # distance, rating, waiting time


@dataclass(frozen=True)
class Candidate:
    collector_id: int
    lat: float
    lng: float
    rating: float
    minutes_waiting: float
    capacity_units: int
    load_units: int
    reserved_units: int


@dataclass(frozen=True)
class RankedCandidate:
    collector_id: int
    distance_km: float
    score: float


def score(distance_km: float, rating: float, minutes_waiting: float,
          radius_km: float = DEFAULT_RADIUS_KM, weights: tuple[float, float, float] = WEIGHTS) -> float:
    w1, w2, w3 = weights
    closeness = max(0.0, 1 - distance_km / radius_km)
    quality = min(max(rating, 0.0), 5.0) / 5
    fairness = min(max(minutes_waiting, 0.0), MAX_WAIT_MINUTES) / MAX_WAIT_MINUTES
    return round(w1 * closeness + w2 * quality + w3 * fairness, 4)


def rank(job_lat: float, job_lng: float, job_units: int, candidates: list[Candidate],
         radius_km: float = DEFAULT_RADIUS_KM, weights: tuple[float, float, float] = WEIGHTS) -> list[RankedCandidate]:
    """Return eligible candidates, best first."""
    ranked = []
    for c in candidates:
        if not load.can_accept(job_units, c.capacity_units, c.load_units, c.reserved_units):
            continue
        d = geo.distance_km(job_lat, job_lng, c.lat, c.lng)
        if d > radius_km:
            continue
        ranked.append(RankedCandidate(c.collector_id, round(d, 3),
                                      score(d, c.rating, c.minutes_waiting, radius_km, weights)))
    ranked.sort(key=lambda r: (-r.score, r.distance_km, r.collector_id))
    return ranked


def rank_nearest_only(job_lat: float, job_lng: float, candidates: list[Candidate],
                      radius_km: float = DEFAULT_RADIUS_KM) -> list[RankedCandidate]:
    """Baseline for evaluation: nearest collector, ignoring capacity and rating."""
    ranked = []
    for c in candidates:
        d = geo.distance_km(job_lat, job_lng, c.lat, c.lng)
        if d <= radius_km:
            ranked.append(RankedCandidate(c.collector_id, round(d, 3), -d))
    ranked.sort(key=lambda r: (r.distance_km, r.collector_id))
    return ranked
