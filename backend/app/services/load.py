"""Tricycle load tracking.

Every confirmed pickup adds its load units to the tricycle. The fill level
decides whether the tricycle may take more jobs or must go to a disposal site.
"""
from enum import Enum

NEARLY_FULL_PERCENT = 60
FULL_PERCENT = 90


class LoadStatus(str, Enum):
    EMPTY = "empty"
    PARTLY_LOADED = "partly_loaded"
    NEARLY_FULL = "nearly_full"
    FULL = "full"


def fill_percent(load_units: int, capacity_units: int) -> float:
    if capacity_units <= 0:
        raise ValueError("Capacity must be positive")
    return round(100 * load_units / capacity_units, 1)


def load_status(load_units: int, capacity_units: int,
                nearly_full: int = NEARLY_FULL_PERCENT, full: int = FULL_PERCENT) -> LoadStatus:
    percent = fill_percent(load_units, capacity_units)
    if load_units <= 0:
        return LoadStatus.EMPTY
    if percent >= full:
        return LoadStatus.FULL
    if percent >= nearly_full:
        return LoadStatus.NEARLY_FULL
    return LoadStatus.PARTLY_LOADED


def available_units(capacity_units: int, load_units: int, reserved_units: int = 0) -> int:
    """Space left for new jobs. Reserved units belong to accepted jobs not yet collected."""
    return max(capacity_units - load_units - reserved_units, 0)


def can_accept(job_units: int, capacity_units: int, load_units: int, reserved_units: int = 0,
               full: int = FULL_PERCENT) -> bool:
    """A full tricycle takes no new jobs; otherwise the job must fit in the space left."""
    if load_status(load_units, capacity_units, full=full) == LoadStatus.FULL:
        return False
    return job_units <= available_units(capacity_units, load_units, reserved_units)
