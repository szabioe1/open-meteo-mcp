"""MCP server exposing Open-Meteo weather data as tools.

Run it with:  uv run open-meteo-mcp            (stdio, for Claude Desktop / Claude Code)
         or:  uv run open-meteo-mcp --http     (Streamable HTTP on :8000/mcp)
"""

from __future__ import annotations

import sys
from typing import Annotated, Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from .client import OpenMeteoClient, OpenMeteoError

mcp = MCPServer(
    "open-meteo",
    instructions=(
        "Weather data from Open-Meteo (free, no API key). "
        "If the user names a place, call search_location first and pass its "
        "latitude/longitude to the weather tools."
    ),
)

_client: OpenMeteoClient | None = None

Latitude = Annotated[float, Field(ge=-90, le=90, description="Latitude in decimal degrees")]
Longitude = Annotated[float, Field(ge=-180, le=180, description="Longitude in decimal degrees")]


def get_client() -> OpenMeteoClient:
    global _client
    if _client is None:
        _client = OpenMeteoClient()
    return _client


def set_client(client: OpenMeteoClient) -> None:
    """Swap the HTTP client (used by tests)."""
    global _client
    _client = client


@mcp.tool()
async def search_location(
    name: Annotated[str, Field(min_length=2, description="City or place name, e.g. 'Debrecen'")],
    count: Annotated[int, Field(ge=1, le=10, description="Max results")] = 5,
) -> list[dict[str, Any]]:
    """Find places by name and return their coordinates, country and timezone."""
    try:
        locations = await get_client().search_locations(name, count)
    except OpenMeteoError as exc:
        raise ToolError(str(exc)) from exc
    if not locations:
        raise ToolError(f"No place found matching '{name}'. Try a different spelling or a larger nearby city.")
    return [loc.__dict__ for loc in locations]


@mcp.tool()
async def get_current_weather(latitude: Latitude, longitude: Longitude) -> dict[str, Any]:
    """Current conditions (temperature, feels-like, humidity, precipitation, wind) at a point."""
    try:
        return await get_client().current(latitude, longitude)
    except OpenMeteoError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
async def get_forecast(
    latitude: Latitude,
    longitude: Longitude,
    days: Annotated[int, Field(ge=1, le=16, description="Number of days, 1-16")] = 7,
) -> list[dict[str, Any]]:
    """Daily forecast: conditions, min/max temperature (°C), precipitation total and chance."""
    try:
        return await get_client().daily_forecast(latitude, longitude, days)
    except OpenMeteoError as exc:
        raise ToolError(str(exc)) from exc


def main() -> None:
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
