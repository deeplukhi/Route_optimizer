import os
from pathlib import Path

import pandas as pd

def _find_project_root() -> Path:
    marker = "fuel-prices-for-be-assessment.csv"
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).is_file():
            return parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()

DEFAULT_CSV_PATH = PROJECT_ROOT / "fuel_prices_with_coords.csv"

CSV_PATH = Path(os.getenv("FUEL_PRICES_CSV", str(DEFAULT_CSV_PATH)))


def load_fuel_prices(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    """Read the geocoded fuel price CSV into a pandas DataFrame."""
    if not csv_path.is_file():
        return pd.DataFrame(
            columns=[
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
        )
    df = pd.read_csv(csv_path)
    for col in ("Latitude", "Longitude"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Retail Price"] = pd.to_numeric(df["Retail Price"], errors="coerce")
    return df.dropna(subset=["Latitude", "Longitude", "Retail Price"])


FUEL_PRICES = load_fuel_prices()
