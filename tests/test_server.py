"""Tests run the real MCP server in-process against a mocked Open-Meteo API.

No network access needed: httpx.MockTransport answers every request.
"""

from __future__ import annotations

import json

import httpx
import pytest
from mcp import Client

from open_meteo_mcp.client import FORECAST_URL, GEOCODING_URL, OpenMeteoClient
from open_meteo_mcp.server import mcp, set_client

GEO = {
    "results": [
        {
            "name": "Debrecen",
            "country": "Hungary",
            "admin1": "Hajdú-Bihar",
            "latitude": 47.53,
            "longitude": 21.63,
            "timezone": "Europe/Budapest",
        }
    ]
}
CURRENT = {
    "timezone": "Europe/Budapest",
    "current_units": {
        "temperature_2m": "°C",
        "apparent_temperature": "°C",
        "precipitation": "mm",
        "wind_speed_10m": "km/h",
    },
    "current": {
        "time": "2026-11-22T19:00",
        "temperature_2m": 3.1,
        "apparent_temperature": -0.4,
        "relative_humidity_2m": 88,
        "precipitation": 0.0,
        "weather_code": 3,
        "wind_speed_10m": 12.5,
    },
}
DAILY = {
    "daily": {
        "time": ["2026-11-23", "2026-11-24"],
        "weather_code": [61, 0],
        "temperature_2m_max": [6.0, 4.2],
        "temperature_2m_min": [1.0, -2.3],
        "precipitation_sum": [4.2, 0.0],
        "precipitation_probability_max": [80, 5],
    }
}


def make_handler(fail: bool = False):
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(400, json={"error": True, "reason": "Latitude must be in range"})
        url = str(request.url).split("?")[0]
        if url == GEOCODING_URL:
            if request.url.params["name"] == "Nowhereville":
                return httpx.Response(200, json={})
            return httpx.Response(200, json=GEO)
        if url == FORECAST_URL:
            return httpx.Response(200, json=DAILY if "daily" in request.url.params else CURRENT)
        return httpx.Response(404)

    return handler


@pytest.fixture
def mocked():
    set_client(OpenMeteoClient(httpx.AsyncClient(transport=httpx.MockTransport(make_handler()))))


@pytest.fixture
def failing():
    set_client(OpenMeteoClient(httpx.AsyncClient(transport=httpx.MockTransport(make_handler(fail=True)))))


def payload(result):
    if result.structured_content is not None:
        sc = result.structured_content
        return sc.get("result", sc)
    return json.loads(result.content[0].text)


async def test_lists_three_tools():
    async with Client(mcp) as client:
        tools = {t.name for t in (await client.list_tools()).tools}
    assert tools == {"search_location", "get_current_weather", "get_forecast"}


async def test_search_location(mocked):
    async with Client(mcp) as client:
        result = await client.call_tool("search_location", {"name": "Debrecen"})
    assert not result.is_error
    assert payload(result)[0]["country"] == "Hungary"


async def test_search_location_not_found(mocked):
    async with Client(mcp) as client:
        result = await client.call_tool("search_location", {"name": "Nowhereville"})
    assert result.is_error
    assert "No place found" in result.content[0].text


async def test_current_weather(mocked):
    async with Client(mcp) as client:
        result = await client.call_tool("get_current_weather", {"latitude": 47.53, "longitude": 21.63})
    data = payload(result)
    assert data["conditions"] == "overcast"
    assert data["temperature"] == "3.1 °C"


async def test_forecast(mocked):
    async with Client(mcp) as client:
        result = await client.call_tool("get_forecast", {"latitude": 47.53, "longitude": 21.63, "days": 2})
    days = payload(result)
    assert [d["conditions"] for d in days] == ["slight rain", "clear sky"]


async def test_invalid_latitude_rejected_before_any_http_call(mocked):
    async with Client(mcp) as client:
        result = await client.call_tool("get_current_weather", {"latitude": 123, "longitude": 0})
    assert result.is_error


async def test_api_error_becomes_tool_error(failing):
    async with Client(mcp) as client:
        result = await client.call_tool("get_forecast", {"latitude": 1, "longitude": 1})
    assert result.is_error
    assert "HTTP 400" in result.content[0].text
