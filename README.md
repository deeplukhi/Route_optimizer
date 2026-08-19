# Spotter Route Optimization API

A Django REST API that calculates optimal, cost-effective fuel stops along a driving route based on real truck stop fuel prices and geospatial data.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Request Flow](#request-flow)
- [Core Algorithms](#core-algorithms)
- [Data Pipeline](#data-pipeline)
- [External Services](#external-services)
- [Configuration](#configuration)
- [Setup Instructions](#setup-instructions)
- [API Reference](#api-reference)
- [Testing](#testing)
- [Limitations & Future Improvements](#limitations--future-improvements)

---

## Overview

The system takes a trip origin and destination, geocodes both endpoints, fetches a driving route (using the HGV profile for heavy trucks), matches nearby fuel stations to the route, and runs a greedy optimization to select the cheapest fuel stops while respecting the vehicle's 500-mile maximum range.

**Key assumptions:**
- Vehicle max range: **500 miles**
- Vehicle efficiency: **10 MPG**
- Tank capacity: **50 gallons** (configurable per request)
- Algorithm: **Greedy Sliding Window** (picks the cheapest reachable station, then refills to full range)

---

## Architecture

```
                        ┌─────────────────────┐
                        │   Client (POST)      │
                        │  /api/optimize-route/│
                        └─────────┬───────────┘
                                  │
                        ┌─────────▼───────────┐
                        │    DRF Serializer     │
                        │  (input validation)  │
                        └─────────┬───────────┘
                                  │
                        ┌─────────▼───────────┐
                        │      View Layer       │
                        │    (views.py)         │
                        └───┬─────────────┬───┘
                            │             │
              ┌─────────────▼──┐   ┌──────▼──────────────┐
              │ Routing Service │   │ Optimization Service │
              │ (geocode + ORS) │   │  (station matching  │
              │                 │   │   + greedy select)  │
              └────────┬───────┘   └──────┬──────────────┘
                       │                  │
            ┌──────────▼──┐    ┌──────────▼──────┐
            │  OpenRoute   │    │  Fuel Price CSV  │
            │  Service API │    │  (pre-geocoded)  │
            │  + Nominatim │    │                  │
            └──────────────┘    └─────────────────┘
```

The application follows a **service-oriented architecture** within a single Django app. Business logic is extracted into dedicated service modules (`routing_service`, `optimization_service`) keeping views thin and focused on request/response handling.

---

## Project Structure

```
django-assessment/
├── .env.example                          # Environment variable template
├── requirements.txt                      # Python dependencies
├── pytest.ini                            # Pytest configuration
├── fuel-prices-for-be-assessment.csv     # Raw fuel price data (input)
├── fuel_prices_with_coords.csv           # Geocoded fuel price data (generated)
├── postman_collection.json               # Postman collection for manual testing
└── src/
    ├── manage.py
    ├── config/                           # Django project configuration
    │   ├── settings.py                   #   Settings (DB, installed apps, API keys)
    │   ├── urls.py                       #   Root URL routing
    │   ├── wsgi.py
    │   └── asgi.py
    └── route_optimizer/                  # Main application
        ├── views.py                      #   API endpoint handlers
        ├── serializers.py                #   DRF request/response serializers
        ├── models.py                     #   (empty - no DB models used)
        ├── urls.py                       #   App-level URL routing
        ├── exceptions.py                 #   Custom exception classes
        ├── fuel_data.py                  #   CSV loading & DataFrame construction
        ├── services/
        │   ├── routing_service.py        #   Geocoding + ORS route fetching
        │   └── optimization_service.py   #   Station matching + greedy optimization
        ├── utils/
        │   └── geo_utils.py             #   Haversine distance + route downsampling
        ├── management/
        │   └── commands/
        │       └── geocode_csv.py        #   One-time CSV geocoding command
        └── tests/
            ├── test_api.py               #   Integration tests (full endpoint)
            └── test_optimization.py      #   Unit tests (algorithm + matching)
```

---

## Request Flow

A single `POST /api/optimize-route/` request follows these steps:

### 1. Validation
The `RouteOptimizationRequestSerializer` validates the input:
- `start` (required, string) -- origin city/name
- `end` (required, string) -- destination city/name
- `starting_fuel_gallons` (optional, float, default `50.0`, min `0.1`)

### 2. Geocoding (Routing Service)
Both `start` and `end` are geocoded to `(lat, lon)` coordinates via **Nominatim** (geopy). Results are cached in-memory for the lifetime of the process.

### 3. Route Fetching (Routing Service)
The geocoded endpoints are sent to **OpenRouteService** using the `driving-hgv` profile. The response provides:
- Total route distance in miles
- Full route geometry as a list of `(lat, lon)` coordinates

### 4. Route Downsampling (Geo Utils)
The raw route polyline (potentially hundreds of points) is downsampled to roughly one point every **10 miles**, each annotated with a cumulative `mile_marker`. This reduces the station-matching computation from O(stations x thousands of points) to O(stations x ~100 points).

### 5. Station Matching (Optimization Service)
All geocoded fuel stations from the CSV are compared against the downsampled route points. A station is **matched** if it falls within **15 miles** (haversine distance) of any route point. Each matched station inherits the `mile_marker` of its nearest route point.

### 6. Greedy Fuel Stop Selection (Optimization Service)
Starting from mile 0 with the configured fuel level:
1. Identify all stations within the current range (current position to current position + range).
2. Select the **cheapest** station in that window.
3. Calculate gallons needed to reach that station and the cost.
4. Refill to full range (500 miles).
5. Repeat until the destination is reachable.

If no station is reachable in any window, a `RouteImpossibleError` is raised (HTTP 400).

### 7. Response
The API returns the route metadata, selected fuel stops (with mile markers, prices, gallons, and per-stop costs), and the total fuel cost.

---

## Core Algorithms

### Greedy Sliding Window (`optimization_service.optimize_fuel_stops`)

```python
while current_mile + range_remaining < total_miles:
    window = [stations within range]
    if not window:
        raise RouteImpossibleError(...)
    winner = cheapest station in window
    buy fuel to reach winner
    current_mile = winner.mile_marker
    range_remaining = MAX_RANGE_MILES  # 500
```

This greedy approach locally optimizes each refueling decision. It does **not** guarantee a globally optimal solution (which would require dynamic programming), but it is fast, simple, and produces good results for typical highway routes.

### Haversine Distance (`geo_utils.haversine_miles`)

Standard great-circle distance formula used for:
- Matching stations to route points
- Downsampling the route polyline at regular mile intervals

### Route Downsampling (`geo_utils.downsample_route`)

Iterates through the full route geometry, accumulating haversine distances, and emits a new point every `interval_miles` (default 10). The start and end points are always included.

---

## Data Pipeline

The fuel price data goes through a two-stage pipeline:

### Stage 1: Geocoding (one-time, manual)
```bash
python src/manage.py geocode_csv
```
- Reads `fuel-prices-for-be-assessment.csv`
- Geocodes each truck stop address via Nominatim
- Writes results to `fuel_prices_with_coords.csv`
- **Resumable**: skips already-geocoded rows
- Rate-limited (1.5s between requests) to respect Nominatim usage policy
- Retries failed geocoding up to 3 times with exponential backoff

### Stage 2: Loading (at import time)
`fuel_data.py` loads `fuel_prices_with_coords.csv` into a pandas DataFrame at module import time. This DataFrame is used by all requests for station matching.

---

## External Services

| Service | Purpose | Auth |
|---------|---------|------|
| [OpenRouteService](https://openrouteservice.org) | Route calculation (HGV profile) | API key (`ORS_API_KEY`) |
| [Nominatim](https://nominatim.org) (via geopy) | Geocoding city names to coordinates | Free (user-agent required) |

---

## Configuration

All configuration is managed via environment variables (loaded from `.env`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ORS_API_KEY` | Yes | `""` | OpenRouteService API key |
| `FUEL_PRICES_CSV` | No | `fuel_prices_with_coords.csv` | Path to geocoded fuel CSV |

**Hardcoded constants** (in `optimization_service.py`):
- `MILES_PER_GALLON = 10`
- `MAX_RANGE_MILES = 500`
- `STATION_RADIUS_MILES = 15.0`

---

## Setup Instructions

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd django-assessment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set `ORS_API_KEY` to a valid key from [OpenRouteService](https://openrouteservice.org/dev/#/signup).

### 4. Geocode the fuel data (one-time)

```bash
python src/manage.py geocode_csv
```

This reads the raw CSV, geocodes each truck stop, and produces `fuel_prices_with_coords.csv`. This may take a while due to rate limiting.

### 5. Run migrations

```bash
python src/manage.py migrate
```

### 6. Start the server

```bash
python src/manage.py runserver
```

---

## API Reference

### `GET /api/health/`

Returns a health check response.

**Response** (200):
```json
{ "status": "ok" }
```

### `POST /api/optimize-route/`

Calculates optimal fuel stops for a route.

**Request body:**
```json
{
  "start": "Boston, MA",
  "end": "Chicago, IL",
  "starting_fuel_gallons": 50.0
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `start` | string | Yes | Origin city/state |
| `end` | string | Yes | Destination city/state |
| `starting_fuel_gallons` | float | No | Default `50.0`, minimum `0.1` |

**Success response** (200):
```json
{
  "route": {
    "origin": "Boston, MA",
    "destination": "Chicago, IL",
    "distance_miles": 983.5,
    "coordinates": [[42.36, -71.06], "..."],
    "route_points": [{"lat": 42.36, "lon": -71.06, "mile_marker": 0.0}, "..."]
  },
  "fuel_stops": [
    {
      "name": "PILOT TRAVEL CENTER #1243",
      "latitude": 40.7,
      "longitude": -74.01,
      "mile_marker": 210.4,
      "retail_price": "$3.90",
      "gallons": 21.04,
      "cost": "$82.06"
    }
  ],
  "total_fuel_cost": "$352.18"
}
```

**Error responses:**

| Status | Error | Cause |
|--------|-------|-------|
| 400 | Validation error | Missing/invalid fields |
| 400 | `no_reachable_fuel_station` | No geocoded station within range on a segment |
| 503 | External service failure | ORS or geocoding service error |

---

## Testing

```bash
pytest
```

Tests are split into two files:

- **`test_optimization.py`** -- Unit tests for the greedy algorithm and station-matching logic
- **`test_api.py`** -- Integration tests for the full endpoint, using mocked ORS responses and geocoding

The test suite uses `pytest-django` and `requests-mock` to avoid external API calls.

---

## Limitations & Future Improvements

**Current limitations:**
- The greedy algorithm is not globally optimal (dynamic programming could improve cost)
- Geocoding coverage depends on Nominatim's data; some stations may not resolve
- Station matching is based on proximity to route (15-mile radius), not actual driving distance to the station
- No authentication or rate limiting on the API
- Fuel prices are loaded at import time (requires restart to pick up CSV changes)

**Potential improvements:**
- Implement dynamic programming for globally optimal fuel stop selection
- Add support for non-US routes
- Cache route results for repeated origin/destination pairs
- Add a database model for fuel stations instead of CSV-based loading
- Implement proper API key authentication
- Add station-level detour cost estimation (actual driving distance vs. route distance)
