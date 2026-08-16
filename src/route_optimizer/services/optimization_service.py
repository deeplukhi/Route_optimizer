from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from route_optimizer.exceptions import RouteImpossibleError
from route_optimizer.utils.geo_utils import haversine_miles

MILES_PER_GALLON = 10
MAX_RANGE_MILES = 500
STATION_RADIUS_MILES = 15.0

Station = dict


def format_currency(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def match_stations_to_route(
    stations: pd.DataFrame,
    route_points: list[dict],
    max_distance_miles: float = STATION_RADIUS_MILES,
) -> list[Station]:
    """Snap each station to the nearest downsampled route point.

    Only stations within ``max_distance_miles`` of a route point are kept;
    each kept station inherits that point's ``mile_marker``. The inner loop
    breaks on the first route point within range.
    """
    matched: list[Station] = []
    for station in stations.to_dict("records"):
        for point in route_points:
            if (
                haversine_miles(
                    station["Latitude"],
                    station["Longitude"],
                    point["lat"],
                    point["lon"],
                )
                <= max_distance_miles
            ):
                matched.append(
                    {
                        "name": station["Truckstop Name"],
                        "lat": station["Latitude"],
                        "lon": station["Longitude"],
                        "mile_marker": point["mile_marker"],
                        "price": float(station["Retail Price"]),
                    }
                )
                break
    return matched


def optimize_fuel_stops(
    stations: list[Station],
    total_miles: float,
    starting_fuel_gallons: float,
) -> tuple[list[dict], Decimal]:
    """Greedy sliding-window fuel stop selection.

    Repeatedly draws the window of stations reachable on the current tank,
    buys at the cheapest one, and refills to the full 500-mile range.
    """
    current_mile = 0.0
    range_remaining = starting_fuel_gallons * MILES_PER_GALLON
    stops: list[dict] = []
    total_cost = Decimal("0")

    while current_mile + range_remaining < total_miles:
        window = [
            station
            for station in stations
            if current_mile < station["mile_marker"] <= current_mile + range_remaining
        ]
        if not window:
            raise RouteImpossibleError(
                f"No reachable fuel station between mile {current_mile:.0f} "
                f"and mile {current_mile + range_remaining:.0f}"
            )

        winner = min(window, key=lambda station: station["price"])
        gallons = (winner["mile_marker"] - current_mile) / MILES_PER_GALLON
        stop_cost = Decimal(str(gallons)) * Decimal(str(winner["price"]))
        total_cost += stop_cost

        stops.append(
            {
                "name": winner["name"],
                "latitude": winner["lat"],
                "longitude": winner["lon"],
                "mile_marker": winner["mile_marker"],
                "retail_price": format_currency(Decimal(str(winner["price"]))),
                "gallons": round(gallons, 2),
                "cost": format_currency(stop_cost),
            }
        )

        current_mile = winner["mile_marker"]
        range_remaining = MAX_RANGE_MILES

    return stops, total_cost


def optimize_route(
    stations: pd.DataFrame,
    route: dict,
    starting_fuel_gallons: float,
) -> tuple[list[dict], Decimal]:
    total_miles = route["distance_miles"]

    if starting_fuel_gallons * MILES_PER_GALLON >= total_miles:
        return [], Decimal("0")

    matched = match_stations_to_route(stations, route["route_points"])
    return optimize_fuel_stops(matched, total_miles, starting_fuel_gallons)
