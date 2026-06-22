import os

from flask import Flask, render_template, request

import requests

app = Flask(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# SSL verification toggle. Set WEATHER_VERIFY_SSL=0 to disable (TEST ONLY).
VERIFY_SSL = os.environ.get("WEATHER_VERIFY_SSL", "1").lower() not in ("0", "false", "no")
if not VERIFY_SSL:
    # Silence the InsecureRequestWarning spam when verification is disabled.
    from urllib3.exceptions import InsecureRequestWarning

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Map WMO weather codes -> (label, icon key)
WMO_CODES = {
    0: ("Ciel dégagé", "sun"),
    1: ("Principalement dégagé", "sun"),
    2: ("Partiellement nuageux", "partly"),
    3: ("Couvert", "cloud"),
    45: ("Brouillard", "fog"),
    48: ("Brouillard givrant", "fog"),
    51: ("Bruine légère", "rain"),
    53: ("Bruine modérée", "rain"),
    55: ("Bruine dense", "rain"),
    56: ("Bruine verglaçante", "rain"),
    57: ("Bruine verglaçante dense", "rain"),
    61: ("Pluie faible", "rain"),
    63: ("Pluie modérée", "rain"),
    65: ("Pluie forte", "rain"),
    66: ("Pluie verglaçante", "rain"),
    67: ("Pluie verglaçante forte", "rain"),
    71: ("Neige faible", "snow"),
    73: ("Neige modérée", "snow"),
    75: ("Neige forte", "snow"),
    77: ("Grains de neige", "snow"),
    80: ("Averses de pluie faibles", "rain"),
    81: ("Averses de pluie modérées", "rain"),
    82: ("Averses de pluie violentes", "rain"),
    85: ("Averses de neige faibles", "snow"),
    86: ("Averses de neige fortes", "snow"),
    95: ("Orage", "storm"),
    96: ("Orage avec grêle", "storm"),
    99: ("Orage avec forte grêle", "storm"),
}


def describe_code(code):
    return WMO_CODES.get(code, ("Inconnu", "cloud"))


def geocode_city(city):
    resp = requests.get(
        GEOCODE_URL,
        params={"name": city, "count": 1, "language": "fr", "format": "json"},
        timeout=10,
        verify=VERIFY_SSL,
    )
    resp.raise_for_status()
    results = resp.json().get("results")
    if not results:
        return None
    return results[0]


def fetch_weather(lat, lon):
    resp = requests.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "forecast_days": 3,
        },
        timeout=10,
        verify=VERIFY_SSL,
    )
    resp.raise_for_status()
    return resp.json()


def build_weather(city):
    place = geocode_city(city)
    if place is None:
        return None, f"Ville introuvable : « {city} »."

    data = fetch_weather(place["latitude"], place["longitude"])
    current = data.get("current", {})
    daily = data.get("daily", {})

    code = current.get("weather_code", 0)
    label, icon = describe_code(code)

    location_parts = [place.get("name")]
    if place.get("admin1"):
        location_parts.append(place["admin1"])
    if place.get("country"):
        location_parts.append(place["country"])
    location = ", ".join(p for p in location_parts if p)

    forecast = []
    times = daily.get("time", [])
    for i, day in enumerate(times):
        d_label, d_icon = describe_code(daily.get("weather_code", [])[i])
        forecast.append(
            {
                "date": day,
                "label": d_label,
                "icon": d_icon,
                "max": round(daily.get("temperature_2m_max", [])[i]),
                "min": round(daily.get("temperature_2m_min", [])[i]),
            }
        )

    weather = {
        "location": location,
        "temperature": round(current.get("temperature_2m", 0)),
        "humidity": current.get("relative_humidity_2m"),
        "wind": current.get("wind_speed_10m"),
        "condition": label,
        "icon": icon,
        "forecast": forecast,
    }
    return weather, None


@app.route("/", methods=["GET", "POST"])
def index():
    weather = None
    error = None
    city = ""
    if request.method == "POST":
        city = (request.form.get("city") or "").strip()
        if not city:
            error = "Veuillez entrer un nom de ville."
        else:
            try:
                weather, error = build_weather(city)
            except requests.RequestException:
                error = "Le service météo est indisponible. Veuillez réessayer."
    return render_template("index.html", weather=weather, error=error, city=city)


if __name__ == "__main__":
    app.run(debug=True)
