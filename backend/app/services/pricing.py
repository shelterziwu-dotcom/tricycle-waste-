"""Rubber-based pricing.

Each rubber (bag, sack or bin) is converted into load units by its size.
The same load units are used to price the job and to fill the tricycle.

    price = base_fee
          + total_units * rate_per_unit * waste_type_factor
          + distance_charge

The distance charge only applies beyond a free radius.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class PricingConfig:
    base_fee: Decimal
    rate_per_unit: Decimal
    rate_per_km: Decimal
    free_radius_km: Decimal
    waste_type_factors: dict[str, Decimal]


@dataclass(frozen=True)
class Quote:
    total_units: int
    base_fee: Decimal
    units_charge: Decimal
    distance_charge: Decimal
    total: Decimal


def total_units(items: list[tuple[int, int]]) -> int:
    """Sum load units for (units_per_rubber, quantity) pairs."""
    total = 0
    for units, quantity in items:
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        total += units * quantity
    return total


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def calculate_price(units: int, waste_type: str, distance_km: float | Decimal,
                    config: PricingConfig) -> Quote:
    if units <= 0:
        raise ValueError("A pickup must contain at least one rubber")
    if waste_type not in config.waste_type_factors:
        raise ValueError(f"Unknown waste type: {waste_type}")

    factor = config.waste_type_factors[waste_type]
    units_charge = _money(Decimal(units) * config.rate_per_unit * factor)

    extra_km = max(Decimal(str(distance_km)) - config.free_radius_km, Decimal("0"))
    distance_charge = _money(extra_km * config.rate_per_km)

    base_fee = _money(config.base_fee)
    return Quote(
        total_units=units,
        base_fee=base_fee,
        units_charge=units_charge,
        distance_charge=distance_charge,
        total=base_fee + units_charge + distance_charge,
    )
