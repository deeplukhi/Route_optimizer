# Spotter Route Optimization API

A Django REST API that calculates optimal, cost-effective fuel stops along a driving route based on provided truck stop fuel prices.

## Assumptions
- Vehicle max range: 500 miles
- Vehicle efficiency: 10 MPG
- Algorithm: Greedy Sliding Window (prioritizes cheapest reachable station)

## Data Coverage & Limitations

- The assessment CSV (`fuel-prices-for-be-assessment.csv`) is the source of truck-stop and fuel-price data.
- Station coordinates are derived/enriched during preprocessing (`geocode_csv`).
- Some source stations may remain unresolved and are therefore not available to route matching.
- Only stations with successfully resolved/validated coordinates can participate in route matching and optimization.
- A route failure caused by a missing reachable station (HTTP 400 with `error: "no_reachable_fuel_station"`) reflects a gap in the currently geocoded station dataset, not necessarily an absence of real-world stations.
- The API therefore does not claim that no real-world station exists in the affected segment; `from_mile`/`to_mile` identify the affected route segment in the available data.
- A future improvement could increase geocoding coverage or use a more reliable geographic data source to reduce such gaps.

## Setup Instructions

1. **Create & Activate Virtual Environment**
   ```bash
   python -m venv venv
   # Mac/Linux: source venv/bin/activate
   # Windows: venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   ```bash
   cp .env.example .env
   ```
   Set a real value for `ORS_API_KEY` (free key from [OpenRouteService](https://openrouteservice.org/dev/#/signup)).

4. **Prepare Fuel Price Data (one-time)**
   ```bash
   python src/manage.py geocode_csv
   ```
   Geocodes the provided `fuel-prices-for-be-assessment.csv` and writes `fuel_prices_with_coords.csv` (resumable; run it once and let it finish).

5. **Run Migrations**
   ```bash
   python src/manage.py migrate
   ```

6. **Start the Server**
   ```bash
   python src/manage.py runserver
   ```

## API Usage

`POST /api/optimize-route/`

Request body:

```json
{
  "start": "Boston, MA",
  "end": "Chicago, IL",
  "starting_fuel_gallons": 50.0
}
```

`starting_fuel_gallons` is optional (default `50.0`).

Response:

```json
{
  "route": {
    "origin": "Boston, MA",
    "destination": "Chicago, IL",
    "distance_miles": 983.5,
    "coordinates": [[42.36, -71.06], "..."]
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

## Running Tests

```bash
pytest
```
