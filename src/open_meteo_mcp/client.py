"""Thin async client for the Open-Meteo geocoding and forecast APIs.

Kept separate from the MCP layer so it can be tested without a server
and reused by other code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes -> short human-readable text.
WEATHER_CODES: dict[int, str] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


class OpenMeteoError(RuntimeError):
    """Raised when Open-Meteo returns an error or an unexpected payload."""


@dataclass(frozen=True)
class Location:
    name: str
    country: str
    admin1: str | None
    latitude: float
    longitude: float
    timezone: str


def describe(code: int | None) -> str:
    if code is None:
        return "unknown"
    return WEATHER_CODES.get(code, f"unknown (code {code})")


class OpenMeteoClient:
    def __init__(self, http: httpx.AsyncClient | None = None, timeout: float = 10.0) -> None:
        self._http = http or httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = await self._http.get(url, params=params)
        except httpx.HTTPError as exc:
            raise OpenMeteoError(f"Network error calling Open-Meteo: {exc}") from exc
        if resp.status_code != 200:
            reason = ""
            try:
                reason = resp.json().get("reason", "")
            except ValueError:
                pass
            raise OpenMeteoError(f"Open-Meteo returned HTTP {resp.status_code}. {reason}".strip())
        data = resp.json()
        if data.get("error"):
            raise OpenMeteoError(data.get("reason", "Open-Meteo reported an error"))
        return data

    async def search_locations(self, name: str, count: int = 5, language: str = "en") -> list[Location]:
        data = await self._get(
            GEOCODING_URL,
            {"name": name, "count": count, "language": language, "format": "json"},
        )
        return [
            Location(
                name=r["name"],
                country=r.get("country", ""),
                admin1=r.get("admin1"),
                latitude=r["latitude"],
                longitude=r["longitude"],
                timezone=r.get("timezone", "auto"),
            )
            for r in data.get("results", [])
        ]

    async def current(self, latitude: float, longitude: float) -> dict[str, Any]:
        data = await self._get(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "precipitation,weather_code,wind_speed_10m",
                "timezone": "auto",
            },
        )
        cur = data.get("current")
        if not cur:
            raise OpenMeteoError("Open-Meteo response had no 'current' block")
        units = data.get("current_units", {})
        return {
            "time": cur["time"],
            "timezone": data.get("timezone"),
            "conditions": describe(cur.get("weather_code")),
            "temperature": f"{cur['temperature_2m']} {units.get('temperature_2m', '°C')}",
            "feels_like": f"{cur['apparent_temperature']} {units.get('apparent_temperature', '°C')}",
            "humidity": f"{cur['relative_humidity_2m']} %",
            "precipitation": f"{cur['precipitation']} {units.get('precipitation', 'mm')}",
            "wind_speed": f"{cur['wind_speed_10m']} {units.get('wind_speed_10m', 'km/h')}",
        }

    async def daily_forecast(self, latitude: float, longitude: float, days: int) -> list[dict[str, Any]]:
        data = await self._get(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,precipitation_probability_max",
                "forecast_days": days,
                "timezone": "auto",
            },
        )
        daily = data.get("daily")
        if not daily or "time" not in daily:
            raise OpenMeteoError("Open-Meteo response had no 'daily' block")
        out = []
        for i, day in enumerate(daily["time"]):
            out.append(
                {
                    "date": day,
                    "conditions": describe(daily["weather_code"][i]),
                    "min_c": daily["temperature_2m_min"][i],
                    "max_c": daily["temperature_2m_max"][i],
                    "precipitation_mm": daily["precipitation_sum"][i],
                    "precipitation_chance_pct": daily["precipitation_probability_max"][i],
                }
            )
        return out
