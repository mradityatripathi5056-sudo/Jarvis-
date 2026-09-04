"""
skills/aqi_skill.py
------------------------------------------------------------
Live Air Quality Index (AQI) - Open-Meteo ke FREE, no-API-key
geocoding + air-quality endpoints use karta hai:
1. Pehle city ka naam -> lat/lon (geocoding API)
2. Fir lat/lon se current AQI + PM2.5/PM10 (air-quality API)

Weather (temperature/rain) ke liye skills/extra_utilities_skill.py
ka get_weather already hai - ye skill sirf AQI/pollution ke liye hai.
"""

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# US AQI scale ke rough category labels (samajhne mein aasani ke liye)
_AQI_LEVELS = [
    (50, "Achhi (Good)"),
    (100, "Theek-thaak (Moderate)"),
    (150, "Sensitive logon ke liye kharab"),
    (200, "Sabke liye kharab (Unhealthy)"),
    (300, "Bahut kharab (Very Unhealthy)"),
    (10_000, "Khatarnak (Hazardous)"),
]


def _aqi_label(aqi: float) -> str:
    for limit, label in _AQI_LEVELS:
        if aqi <= limit:
            return label
    return "Khatarnak (Hazardous)"


def get_air_quality(params: dict) -> str:
    city = params.get("city", "").strip()
    if not city:
        return "Kaunse city ka AQI chahiye, naam batao."
    try:
        geo_resp = requests.get(
            GEOCODE_URL, params={"name": city, "count": 1}, timeout=8
        ).json()
        results = geo_resp.get("results") or []
        if not results:
            return f"'{city}' naam ka location nahi mila."
        lat, lon = results[0]["latitude"], results[0]["longitude"]
        found_name = results[0].get("name", city)

        aqi_resp = requests.get(
            AQI_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "us_aqi,pm2_5,pm10",
            },
            timeout=8,
        ).json()
        current = aqi_resp.get("current", {})
        aqi = current.get("us_aqi")
        pm25 = current.get("pm2_5")
        pm10 = current.get("pm10")
        if aqi is None:
            return f"{found_name} ka AQI data abhi available nahi hai."
        label = _aqi_label(aqi)
        return (
            f"{found_name} ka AQI: {aqi} ({label}). "
            f"PM2.5: {pm25} µg/m³, PM10: {pm10} µg/m³."
        )
    except Exception as e:
        return f"AQI nahi mil saka: {e}"


ACTIONS = {
    "get_air_quality": get_air_quality,
}

DOCS = """
- get_air_quality: {"city": "Delhi"}  (current AQI, PM2.5, PM10 batata hai)

Example:
User: "Delhi ka AQI kitna hai"
-> {"actions": [{"action": "get_air_quality", "params": {"city": "Delhi"}}]}

User: "hawa kaisi hai aaj yaha"
-> {"actions": [{"action": "get_air_quality", "params": {"city": "<jo city context mein pata ho, warna general_chat se poochho>"}}]}
"""
