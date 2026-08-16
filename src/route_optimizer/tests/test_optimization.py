import pandas as pd
import pytest

from route_optimizer.exceptions import RouteImpossibleError
from route_optimizer.services import optimization_service
from route_optimizer.utils.geo_utils import downsample_route

STATION_COLUMNS = [
    "OPIS Truckstop ID",
    "Truckstop Name",
    "Address",
    "City",
    "State",
    "Rack ID",
    "Retail Price",
    "Latitude",
    "Longitude",
]


def make_station(name, marker, price):
    return {"name": name, "lat": 40.0, "lon": -75.0, "mile_marker": marker, "price": price}


def make_dataframe(stations):
    return pd.DataFrame(
        [
            {
                "Truckstop Name": name,
                "Latitude": lat,
                "Longitude": lon,
                "Retail Price": price,
            }
            for name, lat, lon, price in stations
        ],
        columns=STATION_COLUMNS,
    )


class TestGreedyAlgorithm:
    def test_short_trip_returns_no_stops_and_zero_cost(self):
        stops, cost = optimization_service.optimize_fuel_stops([], 200, 50)

        assert stops == []
        assert cost == 0

    def test_short_trip_reachable_without_fueling(self):
        stops, cost = optimization_service.optimize_fuel_stops(
            [make_station("A", 50, 3.0)], 200, 50
        )

        assert stops == []
        assert cost == 0

    def test_picks_cheapest_station_in_window(self):
        stations = [
            make_station("Expensive", 200, 4.0),
            make_station("Cheap", 300, 3.0),
            make_station("Mid", 480, 3.5),
        ]

        stops, cost = optimization_service.optimize_fuel_stops(stations, 900, 50)

        assert [stop["name"] for stop in stops] == ["Cheap", "Mid"]
        assert stops[0]["cost"] == "$90.00"
        assert stops[0]["gallons"] == 30.0
        assert cost == 153

    def test_range_resets_to_full_tank_after_refuel(self):
        stations = [
            make_station("A", 100, 3.0),
            make_station("B", 500, 3.0),
            make_station("C", 900, 3.0),
        ]

        stops, _ = optimization_service.optimize_fuel_stops(stations, 1200, 50)

        assert [stop["name"] for stop in stops] == ["A", "B", "C"]

    def test_ignores_cheaper_station_just_out_of_range(self):
        stations = [
            make_station("Reachable", 480, 4.0),
            make_station("CheaperButFar", 510, 2.0),
        ]

        stops, _ = optimization_service.optimize_fuel_stops(stations, 900, 50)

        assert [stop["name"] for stop in stops] == ["Reachable"]

    def test_six_hundred_mile_gap_raises_impossible(self):
        stations = [make_station("A", 100, 3.0), make_station("B", 800, 3.0)]

        with pytest.raises(RouteImpossibleError) as excinfo:
            optimization_service.optimize_fuel_stops(stations, 1200, 50)

        assert excinfo.value.from_mile == 100
        assert excinfo.value.to_mile == 600
        assert "available geocoded station dataset" in str(excinfo.value)

    def test_no_stations_on_long_trip_raises_impossible(self):
        with pytest.raises(RouteImpossibleError) as excinfo:
            optimization_service.optimize_fuel_stops([], 600, 50)

        assert excinfo.value.from_mile == 0
        assert excinfo.value.to_mile == 500
        assert "available geocoded station dataset" in str(excinfo.value)
        assert "no fuel stations in this area" not in str(excinfo.value).lower()


class TestStationMatching:
    def test_station_snaps_to_nearest_route_point(self):
        route_points = downsample_route(
            [(40.0, -100.0 + i * 0.1) for i in range(200)]
        )

        target = route_points[10]
        df = make_dataframe(
            [("OnRoute", target["lat"], target["lon"], 3.0)]
        )

        matched = optimization_service.match_stations_to_route(df, route_points)

        assert len(matched) == 1
        assert matched[0]["name"] == "OnRoute"
        assert matched[0]["mile_marker"] <= target["mile_marker"]
        assert target["mile_marker"] - matched[0]["mile_marker"] <= 15

    def test_station_off_route_is_dropped(self):
        route_points = downsample_route(
            [(40.0, -100.0 + i * 0.1) for i in range(200)]
        )

        df = make_dataframe([("OffRoute", 45.0, -90.0, 3.0)])

        matched = optimization_service.match_stations_to_route(df, route_points)

        assert matched == []
