import os
import requests
from dotenv import load_dotenv

load_dotenv()  # loads variables from .env in project root

API_KEY = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"


def get_forecast(lat, lon, days=30):
    """
    Fetch weather forecast for given coordinates.
    Note: OpenWeatherMap's free tier only provides a 5-day/3-hour forecast,
    not a full 30-day forecast. We'll aggregate what's available and note the limitation.
    """
    if not API_KEY:
        raise ValueError("OPENWEATHER_API_KEY not found. Check your .env file.")

    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "metric"
    }

    response = requests.get(BASE_URL, params=params)
    response.raise_for_status()
    data = response.json()

    total_rainfall = 0.0
    temps = []
    freeze_thaw_cycles = 0

    for entry in data["list"]:
        rain_mm = entry.get("rain", {}).get("3h", 0)
        total_rainfall += rain_mm

        temp = entry["main"]["temp"]
        temps.append(temp)

        if -2 <= temp <= 2:
            freeze_thaw_cycles += 1

    avg_temp = sum(temps) / len(temps) if temps else None

    return {
        "location": {"lat": lat, "lon": lon},
        "forecast_period_days": 5,
        "requested_days": days,
        "rainfall_mm_total": round(total_rainfall, 2),
        "avg_temp": round(avg_temp, 2) if avg_temp else None,
        "freeze_thaw_cycles": freeze_thaw_cycles
    }


if __name__ == "__main__":
    result = get_forecast(17.38, 78.47, days=30)
    print(result)