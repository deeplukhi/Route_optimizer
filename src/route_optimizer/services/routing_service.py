import openrouteservice
from django.conf import settings
from geopy.geocoders import Nominatim

from route_optimizer.utils.geo_utils import Coord, downsample_route

GEOPY_USER_AGENT = "fuel-route-optimizer/1.0"

METERS_PER_MILE = 1609.344

_geocode_cache: dict[str, Coord] = {}


class GeocodeError(Exception):
    pass


class RoutingError(Exception):
    pass


def geocode_location(location_text: str) -> Coord:
    """Resolve a free-form US location to (latitude, longitude)."""
    key = location_text.strip().lower()
    if key in _geocode_cache:
        return _geocode_cache[key]

    geocoder = Nominatim(user_agent=GEOPY_USER_AGENT)
    location = geocoder.geocode(location_text, country_codes="us")
    if location is None:
        raise GeocodeError(f"Could not geocode location: {location_text}")

    coords = (location.latitude, location.longitude)
    _geocode_cache[key] = coords
    return coords


def get_route_coordinates(
    origin: Coord, destination: Coord
) -> tuple[float, list[Coord]]:
    """Make the single OpenRouteService directions call.

    Returns total route distance in miles and the geometry as
    (lat, lon) coordinate pairs.
    """
    api_key = settings.ORS_API_KEY
    if not api_key:
        raise RoutingError("OpenRouteService API key is not configured")

    client = openrouteservice.Client(key=api_key)
    response = client.directions(
        coordinates=[
            [origin[1], origin[0]],
            [destination[1], destination[0]],
        ],
        profile="driving-hgv",
        format="geojson",
        validate=False,
    )

    feature = response["features"][0]
    distance_miles = feature["properties"]["summary"]["distance"] / METERS_PER_MILE
    geometry = feature["geometry"]["coordinates"]
    coordinates = [(lat, lon) for lon, lat in geometry]
    return distance_miles, coordinates


def build_route(origin_text: str, destination_text: str) -> dict:
    """Geocode endpoints, fetch the route, and downsample it.

    This is the single entry point that consumes exactly one
    OpenRouteService directions call per request.
    """
    origin = geocode_location(origin_text)
    destination = geocode_location(destination_text)
    distance_miles, coordinates = get_route_coordinates(origin, destination)

    return {
        "origin": origin_text,
        "destination": destination_text,
        "distance_miles": round(distance_miles, 2),
        "coordinates": [[lat, lon] for lat, lon in coordinates],
        "route_points": downsample_route(coordinates),
    }
