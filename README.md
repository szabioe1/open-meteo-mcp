# open-meteo-mcp

An [MCP](https://modelcontextprotocol.io) server that gives Claude, ChatGPT, Cursor or any MCP-capable AI agent live weather data from [Open-Meteo](https://open-meteo.com). Free, no API key, works out of the box.

It's a small, complete example of how I build MCP servers for clients: a typed API client, tools designed so the model knows when to use them, input validation, clear error messages, and tests that run without network access.

## Tools

| Tool | What the AI can do with it |
|---|---|
| `search_location` | Turn "Debrecen" or "Lisbon" into coordinates, country and timezone |
| `get_current_weather` | Current temperature, feels-like, humidity, precipitation, wind |
| `get_forecast` | Daily forecast for 1–16 days: conditions, min/max, rain amount and chance |

Example: ask *"Do I need an umbrella in Debrecen tomorrow?"* and Claude calls `search_location` → `get_forecast` and answers from real data.

## Install

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/szabioe1/open-meteo-mcp
cd open-meteo-mcp
uv sync
```

### Claude Code

```bash
claude mcp add open-meteo -- uv --directory /path/to/open-meteo-mcp run open-meteo-mcp
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "open-meteo": {
      "command": "uv",
      "args": ["--directory", "/path/to/open-meteo-mcp", "run", "open-meteo-mcp"]
    }
  }
}
```

### Over HTTP (remote agents)

```bash
uv run open-meteo-mcp --http   # Streamable HTTP on http://localhost:8000/mcp
```

## Design notes

- **API client separate from the MCP layer** (`client.py` vs `server.py`): the client can be tested and reused on its own, and the MCP layer stays thin.
- **Validation in the schema**: latitude, longitude, day count and result count have bounds, so bad input is rejected before any HTTP call and the model sees exactly what's allowed.
- **Errors the model can act on**: API and network failures become MCP tool errors with a readable reason ("No place found matching 'X'. Try a different spelling…") instead of stack traces.
- **Human-readable output**: WMO weather codes are translated to text, and units are attached to values.

## Tests

```bash
uv run pytest
```

The tests start the real server in-process and call it through an MCP client. Open-Meteo is mocked with `httpx.MockTransport`, so they're fast and need no network access.

## Need one for your own tools?

I build custom MCP servers that connect AI agents to your API, database, CRM or internal docs, and I set up Claude Code for teams. [Contact me on Fiverr](https://www.fiverr.com/kszabifvr).

## License

MIT. Weather data © [Open-Meteo](https://open-meteo.com), CC BY 4.0.
