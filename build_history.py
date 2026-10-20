"""Download 2023-2025 daily climate once and save monthly averages to a CSV.

Run locally:  python build_history.py
Then commit data/monthly_climate.csv so the deployed app never has to call
the archive API (which rate-limits shared cloud servers).
"""
import time
from pathlib import Path

import pandas as pd
import requests

from places import PLACES

URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch(lat: float, lon: float) -> pd.DataFrame:
    for attempt in range(5):
        r = requests.get(
            URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": "2023-01-01",
                "end_date": "2025-12-31",
                "daily": "temperature_2m_max,precipitation_sum",
                "timezone": "Asia/Colombo",
            },
            timeout=30,
        )
        if r.status_code != 429:
            r.raise_for_status()
            break
        wait = 15 * (attempt + 1)
        print(f"  rate limited, waiting {wait}s...")
        time.sleep(wait)
    else:
        raise RuntimeError("Still rate limited, try again later.")
    df = pd.DataFrame(r.json()["daily"])
    df.columns = ["date", "tmax", "rain_mm"]
    df["date"] = pd.to_datetime(df["date"])
    df["year"], df["month"] = df["date"].dt.year, df["date"].dt.month
    monthly = df.groupby(["year", "month"], as_index=False).agg(
        rain=("rain_mm", "sum"), tmax=("tmax", "mean")
    )
    return monthly.groupby("month", as_index=False).agg(
        avg_rain_mm=("rain", "mean"), avg_max_temp=("tmax", "mean")
    ).round(1)


frames = []
for name, (lat, lon) in PLACES.items():
    print(f"Fetching {name}...")
    out = fetch(lat, lon)
    out.insert(0, "place", name)
    frames.append(out)
    time.sleep(3)

Path("data").mkdir(exist_ok=True)
pd.concat(frames).to_csv("data/monthly_climate.csv", index=False)
print("Saved data/monthly_climate.csv")
