"""Unit tests for the pure business rules."""
from decimal import Decimal

import pytest

from app.services import geo, load, matching, pricing

CONFIG = pricing.PricingConfig(
    base_fee=Decimal("5"), rate_per_unit=Decimal("3"), rate_per_km=Decimal("1"),
    free_radius_km=Decimal("2"),
    waste_type_factors={"general": Decimal("1.0"), "recyclable": Decimal("0.7"), "bulky": Decimal("1.5")},
)


# ---------- pricing ----------
def test_proposal_worked_example():
    units = pricing.total_units([(1, 2), (4, 1)])  # 2 small + 1 large
    quote = pricing.calculate_price(units, "general", 1.5, CONFIG)
    assert units == 6
    assert quote.total == Decimal("23.00")


def test_distance_charged_only_beyond_free_radius():
    quote = pricing.calculate_price(2, "general", 3.5, CONFIG)
    assert quote.distance_charge == Decimal("1.50")
    assert quote.total == Decimal("12.50")


def test_recyclables_are_discounted():
    general = pricing.calculate_price(10, "general", 0, CONFIG)
    recyclable = pricing.calculate_price(10, "recyclable", 0, CONFIG)
    assert recyclable.units_charge == Decimal("21.00")
    assert recyclable.total < general.total


@pytest.mark.parametrize("units, waste_type", [(0, "general"), (3, "hazardous")])
def test_invalid_pricing_input(units, waste_type):
    with pytest.raises(ValueError):
        pricing.calculate_price(units, waste_type, 0, CONFIG)


# ---------- load ----------
@pytest.mark.parametrize("load_units, expected", [
    (0, load.LoadStatus.EMPTY), (1, load.LoadStatus.PARTLY_LOADED), (23, load.LoadStatus.PARTLY_LOADED),
    (24, load.LoadStatus.NEARLY_FULL), (35, load.LoadStatus.NEARLY_FULL), (36, load.LoadStatus.FULL),
    (40, load.LoadStatus.FULL),
])
def test_load_status_thresholds(load_units, expected):
    assert load.load_status(load_units, 40) == expected


def test_job_must_fit_remaining_space_including_reservations():
    assert load.can_accept(4, capacity_units=40, load_units=30, reserved_units=6)
    assert not load.can_accept(5, capacity_units=40, load_units=30, reserved_units=6)


def test_full_tricycle_takes_no_jobs_even_if_space_left():
    assert not load.can_accept(1, capacity_units=40, load_units=36)


# ---------- geo ----------
def test_geofence():
    assert geo.inside_geofence(5.6037, -0.1870, 5.6037, -0.1870, 50)
    assert geo.distance_m(5.6037, -0.1870, 5.6046, -0.1870) == pytest.approx(100, abs=2)
    assert not geo.inside_geofence(5.6046, -0.1870, 5.6037, -0.1870, 50)


# ---------- matching ----------
def cand(cid, lat=5.6180, lng=-0.2030, rating=4.0, waiting=0, load_units=0, capacity=40, reserved=0):
    return matching.Candidate(cid, lat, lng, rating, waiting, capacity, load_units, reserved)


def test_matching_skips_tricycles_without_space_and_too_far():
    ranked = matching.rank(5.6145, -0.2057, 6, [
        cand(1, load_units=36),           # full
        cand(2, load_units=30, reserved=5),  # only 5 units left
        cand(3, lat=5.7, lng=-0.1),       # too far
        cand(4),
    ])
    assert [r.collector_id for r in ranked] == [4]


def test_matching_prefers_closer_then_fairness():
    near, farther = cand(1), cand(2, lat=5.6300, lng=-0.2057)
    assert matching.rank(5.6145, -0.2057, 2, [farther, near])[0].collector_id == 1
    rested = cand(3, waiting=60)
    assert matching.rank(5.6145, -0.2057, 2, [near, rested])[0].collector_id == 3


def test_nearest_only_baseline_ignores_capacity():
    ranked = matching.rank_nearest_only(5.6145, -0.2057, [cand(1, load_units=40)])
    assert [r.collector_id for r in ranked] == [1]
