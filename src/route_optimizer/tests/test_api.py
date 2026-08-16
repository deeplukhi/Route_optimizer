import re
from unittest import mock

import pandas as pd
import pytest

from django.test import Client

from route_optimizer.services import routing_service
from route_optimizer.tests.test_optimization import make_dataframe
from route_optimizer.utils.geo_utils import haversine_miles

ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"


def ors_response(distance_meters, coordinates):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {"summary": {"distance": distance_meters, "duration": 3600}},
            }
        ],
    }


def straight_line_geometry(num_points=200):
    return [[-100.0 + i * 0.1, 40.0] for i in range(num_points)]


def geometry_distance_miles(coordinates):
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(coordinates, coordinates[1:]):
        total += haversine_miles(lat1, lon1, lat2, lon2)
    return total


def build_station_dataframe(route_miles):
    stations = []
    for marker in range(100, 900, 100):
        fraction = marker / route_miles
        lon = -100.0 + fraction * 19.9
        stations.append((f"Stop{marker}", 40.0, lon, 3.0))
    return make_dataframe(stations)


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def post_route(api_client):
    def _post(payload):
        return api_client.post(
            "/api/optimize-route/",
            data=payload,
            content_type="application/json",
        )

    return _post


class TestOptimizeRouteEndpoint:
    def test_short_trip_returns_empty_stops(self, post_route, requests_mock):
        requests_mock.post(
            ORS_URL,
            json=ors_response(321868.8, straight_line_geometry(num_points=5)),
        )

        with mock.patch.object(
            routing_service,
            "geocode_location",
            side_effect=lambda text: (40.0, -100.0),
        ):
            response = post_route(
                {"start": "Boston, MA", "end": "New York, NY"}
            )

        assert response.status_code == 200
        body = response.json()
        assert body["fuel_stops"] == []
        assert body["total_fuel_cost"] == "$0.00"
        assert body["route"]["distance_miles"] == 200.0
        assert "coordinates" in body["route"]
        assert "route_points" in body["route"]

    def test_long_trip_returns_stops_and_cost(self, post_route, requests_mock):
        geometry = straight_line_geometry()
        distance_miles = geometry_distance_miles(geometry)
        requests_mock.post(
            ORS_URL,
            json=ors_response(distance_miles * 1609.344, geometry),
        )
        stations = build_station_dataframe(distance_miles)

        with (
            mock.patch.object(
                routing_service,
                "geocode_location",
                side_effect=lambda text: (40.0, -100.0),
            ),
            mock.patch("route_optimizer.views.FUEL_PRICES", stations),
        ):
            response = post_route(
                {"start": "A", "end": "B", "starting_fuel_gallons": 50}
            )

        assert response.status_code == 200
        body = response.json()
        assert body["fuel_stops"]
        assert re.fullmatch(r"\$\d+\.\d{2}", body["total_fuel_cost"])

        stop_keys = {
            "name",
            "latitude",
            "longitude",
            "mile_marker",
            "retail_price",
            "gallons",
            "cost",
        }
        assert all(set(stop) == stop_keys for stop in body["fuel_stops"])
        markers = [stop["mile_marker"] for stop in body["fuel_stops"]]
        assert markers == sorted(markers)

    def test_makes_single_ors_call(self, post_route, requests_mock):
        requests_mock.post(
            ORS_URL,
            json=ors_response(321868.8, straight_line_geometry(num_points=5)),
        )

        with mock.patch.object(
            routing_service,
            "geocode_location",
            side_effect=lambda text: (40.0, -100.0),
        ):
            post_route({"start": "A", "end": "B"})

        assert len(requests_mock.request_history) == 1

    def test_impossible_route_returns_400(self, post_route, requests_mock):
        geometry = straight_line_geometry()
        distance_miles = geometry_distance_miles(geometry)
        requests_mock.post(
            ORS_URL,
            json=ors_response(distance_miles * 1609.344, geometry),
        )
        empty = pd.DataFrame(columns=make_dataframe([]).columns)

        with (
            mock.patch.object(
                routing_service,
                "geocode_location",
                side_effect=lambda text: (40.0, -100.0),
            ),
            mock.patch("route_optimizer.views.FUEL_PRICES", empty),
        ):
            response = post_route({"start": "A", "end": "B"})

        assert response.status_code == 400
        assert "error" in response.json()

    def test_missing_fields_return_400(self, post_route):
        response = post_route({"start": "Boston, MA"})

        assert response.status_code == 400

    def test_invalid_gallons_return_400(self, post_route):
        response = post_route(
            {"start": "A", "end": "B", "starting_fuel_gallons": 0}
        )

        assert response.status_code == 400
