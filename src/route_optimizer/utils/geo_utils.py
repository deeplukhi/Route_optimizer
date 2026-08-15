from math import asin, cos, radians, sin, sqrt

from typing import Iterable

EARTH_RADIUS_MILES = 3958.7613

Coord = tuple[float, float]

RoutePoint = dict[str, float]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two coordinates."""
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(a))


def downsample_route(
    coordinates: Iterable[Coord], interval_miles: float = 10.0
) -> list[RoutePoint]:
    """Sample a polyline to roughly one point per interval_miles.

    Each sampled point carries a cumulative ``mile_marker`` measured from
    the start of the route. The route start is always mile 0 and the
    final coordinate is always included.
    """
    coords = list(coordinates)
    if not coords:
        return []

    first_lat, first_lon = coords[0]
    sampled = [{"lat": first_lat, "lon": first_lon, "mile_marker": 0.0}]

    cumulative = 0.0
    since_last = 0.0
    prev_lat, prev_lon = first_lat, first_lon

    for lat, lon in coords[1:]:
        leg = haversine_miles(prev_lat, prev_lon, lat, lon)
        cumulative += leg
        since_last += leg
        if since_last >= interval_miles:
            sampled.append(
                {"lat": lat, "lon": lon, "mile_marker": round(cumulative, 2)}
            )
            since_last = 0.0
        prev_lat, prev_lon = lat, lon

    last_lat, last_lon = coords[-1]
    if sampled[-1]["lat"] != last_lat or sampled[-1]["lon"] != last_lon:
        sampled.append(
            {"lat": last_lat, "lon": last_lon, "mile_marker": round(cumulative, 2)}
        )

    return sampled
