import csv
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError, GeocoderTimedOut

from route_optimizer.fuel_data import PROJECT_ROOT


class Command(BaseCommand):
    help = "Geocode the fuel price CSV and persist coordinates to a new CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            default=str(PROJECT_ROOT / "fuel-prices-for-be-assessment.csv"),
            help="Path to the source fuel price CSV.",
        )
        parser.add_argument(
            "--output",
            default=str(PROJECT_ROOT / "fuel_prices_with_coords.csv"),
            help="Path where the geocoded CSV will be written.",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=1.5,
            help="Seconds to wait between geocoding requests.",
        )

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        output_path = Path(options["output"])
        sleep_seconds = options["sleep"]

        if not input_path.is_file():
            raise CommandError(f"Input CSV not found: {input_path}")

        geocoder = Nominatim(user_agent="fuel-route-optimizer/1.0")

        rows = self._read_rows(input_path)
        done_ids = self._read_existing_ids(output_path)

        pending = [row for row in rows if row["OPIS Truckstop ID"] not in done_ids]
        self.stdout.write(
            f"Loaded {len(rows)} rows, {len(done_ids)} already geocoded, "
            f"{len(pending)} pending."
        )

        geocoded = []
        failed = 0
        for i, row in enumerate(pending, start=1):
            time.sleep(sleep_seconds)
            lat, lon = self._geocode(geocoder, row)
            if lat is None or lon is None:
                failed += 1
                self.stdout.write(f"  [{i}/{len(pending)}] failed: {row['OPIS Truckstop ID']}")
            else:
                geocoded.append({**row, "Latitude": lat, "Longitude": lon})
            if i % 25 == 0:
                self._append_rows(output_path, rows, geocoded, done_ids)
                self.stdout.write(f"  [{i}/{len(pending)}] geocoded {len(geocoded)} rows...")
            self.stdout.flush()

        self._append_rows(output_path, rows, geocoded, done_ids)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {len(geocoded)} rows geocoded, {failed} failed. "
                f"Output written to {output_path}"
            )
        )

    @staticmethod
    def _read_rows(input_path: Path) -> list[dict]:
        with input_path.open(newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))

    @staticmethod
    def _read_existing_ids(output_path: Path) -> set:
        if not output_path.is_file():
            return set()
        with output_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            if "OPIS Truckstop ID" not in (reader.fieldnames or []):
                return set()
            return {row["OPIS Truckstop ID"] for row in reader}

    @staticmethod
    def _geocode(geocoder, row):
        query = {"street": row["Address"], "city": row["City"], "state": row["State"]}
        for attempt in range(3):
            try:
                location = geocoder.geocode(query, country_codes="us", timeout=20)
            except (GeocoderTimedOut, GeocoderServiceError):
                if attempt < 2:
                    time.sleep(2 ** attempt)
                continue
            break
        if location is None:
            return None, None
        return location.latitude, location.longitude

    @staticmethod
    def _append_rows(output_path, rows, new_rows, done_ids):
        combined = [row for row in rows if row["OPIS Truckstop ID"] in done_ids]
        combined.extend(new_rows)
        fieldnames = [*rows[0].keys(), "Latitude", "Longitude"]
        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(combined)
