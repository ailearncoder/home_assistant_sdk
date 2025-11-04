# Home Assistant Integration Tools

[中文](README_en.md) | [**English**]

A Python toolkit for interacting with Home Assistant, providing HTTP API, WebSocket client, and automated configuration features for common integrations.

## Features

### 🔐 Authentication Management
- Username/password login
- Long-lived access token management
- Token refresh and caching

### 🌐 HTTP API Client
- Generic integration configuration flow API
- Support for standard configuration flows of all Home Assistant integrations
- Flow step management (start, submit, query)

### 🔌 WebSocket Client
- Complete asynchronous WebSocket client implementation
- Event subscription and push
- Service calls
- State queries
- Automatic reconnection and heartbeat keep-alive
- Flow progress monitoring

### 🏠 Integration-Specific Modules

#### Xiaomi Smart Home Integration
- Automated EULA acceptance
- OAuth authentication flow handling
- Home list retrieval and selection
- Complete configuration wizard

#### MCP Server Integration
- Flow creation and configuration
- LLM API option management
- One-click integration setup

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd home_assistant

# Install dependencies (using uv or pip)
uv sync
# or
pip install -e .
```

## Quick Start

### 1. Get Access Token

```python
from home_assistant import HomeAssistantAuth

auth = HomeAssistantAuth(
    url="http://192.168.66.28:8123",
    username="admin",
    password="admin123"
)

token_info = auth.get_token()
access_token = token_info.get("access_token")
```

### 2. Set up Xiaomi Smart Home Integration

```python
import asyncio
from home_assistant import setup_xiaomi_home_integration

async def main():
    await setup_xiaomi_home_integration(
        base_url="http://192.168.66.28:8123",
        token=access_token,
        verify_ssl=False
    )

asyncio.run(main())
```

### 3. Set up MCP Server Integration

```python
from home_assistant import setup_mcp_server_integration

result = setup_mcp_server_integration(
    base_url="http://192.168.66.28:8123",
    token=access_token
)
print(f"Entry ID: {result.result.get('entry_id')}")
```

### 4. Use WebSocket Client

```python
import asyncio
from home_assistant import HAWebSocketClient

async def main():
    async with HAWebSocketClient("ws://192.168.66.28:8123", access_token) as ws:
        # Get all states
        states = await ws.get_states()
        print(f"Total entities: {len(states)}")
        
        # Call service
        await ws.call_service(
            domain="light",
            service="turn_on",
            target={"entity_id": "light.living_room"}
        )

asyncio.run(main())
```

## Project Structure

```
src/home_assistant/
├── __init__.py                 # Package exports and initialization
├── home_assistant_api.py       # HTTP API client (generic)
├── home_assistant_client.py    # WebSocket client (generic)
├── xiaomi_home_flow.py         # Xiaomi Smart Home integration specific
├── mcp_server_flow.py          # MCP server integration specific
├── ha_xiaomi_setup.py          # [Deprecated] Old Xiaomi integration code
└── mcp_integration.py          # [Deprecated] Old MCP integration code
```

### Core Module Description

| Module | Function | Type |
|--------|----------|------|
| `home_assistant_api.py` | Generic HTTP request encapsulation | Generic |
| `home_assistant_client.py` | Generic WebSocket connection encapsulation | Generic |
| `xiaomi_home_flow.py` | Xiaomi integration specific flow | Specific |
| `mcp_server_flow.py` | MCP integration specific flow | Specific |

## Documentation

- [Refactoring Summary](./REFACTORING_SUMMARY.md) - Detailed refactoring instructions and architecture design
- [Usage Examples](./USAGE_EXAMPLES.md) - Complete usage examples and best practices

## API Reference

### HomeAssistantAuth

User authentication and token management.

```python
auth = HomeAssistantAuth(url, username, password)
token_info = auth.get_token()
new_token = auth.refresh_token(client_id, refresh_token)
```

### HomeAssistantIntegrationFlow

Generic integration configuration flow HTTP API.

```python
api = HomeAssistantIntegrationFlow(base_url, token, verify_ssl=True)
flow_data = api.start_flow(handler="integration_name")
result = api.submit_flow_step(flow_id, data)
info = api.get_flow_info(flow_id)
```

### HAWebSocketClient

Asynchronous WebSocket client.

```python
async with HAWebSocketClient(ws_url, token) as ws:
    # Subscribe to events
    sub_id = await ws.subscribe_events(callback, event_type="state_changed")
    
    # Call service
    await ws.call_service(domain, service, service_data, target)
    
    # Get states
    states = await ws.get_states()
    config = await ws.get_config()
    services = await ws.get_services()
    
    # Wait for flow progress
    flow_id = await ws.wait_for_flow_progress(handler, timeout)
    
    # Unsubscribe
    await ws.unsubscribe_events(sub_id)
```

### XiaomiHomeIntegration

Xiaomi Smart Home integration specific class.

```python
xiaomi = XiaomiHomeIntegration(api_client, ws_client)
flow_id = xiaomi.start_xiaomi_flow()
xiaomi.submit_eula()
oauth_url = xiaomi.submit_auth_config(cloud_server, language, redirect_url)
await xiaomi.wait_for_oauth_completion(timeout)
homes = xiaomi.get_available_homes()
result = xiaomi.submit_home_selection(home_ids)
```

### MCPServerIntegration

MCP server integration specific class.

```python
mcp = MCPServerIntegration(api_client)
flow_response = mcp.create_flow()
options = mcp.extract_available_options(flow_response)
entry_response = mcp.submit_flow(llm_hass_api)
```

## Convenience Functions

### setup_xiaomi_home_integration

One-click setup for Xiaomi Smart Home integration.

```python
await setup_xiaomi_home_integration(
    base_url="http://192.168.66.28:8123",
    token="YOUR_TOKEN",
    verify_ssl=False
)
```

### setup_mcp_server_integration

One-click setup for MCP server integration.

```python
result = setup_mcp_server_integration(
    base_url="http://192.168.66.28:8123",
    token="YOUR_TOKEN",
    llm_hass_api=None,  # None means use all available options
    verify_ssl=False
)
```

## Environment Variables

It's recommended to store sensitive information using environment variables:

```bash
export HA_URL="http://192.168.66.28:8123"
export HA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

Use in code:

```python
import os

HA_URL = os.environ.get("HA_URL")
HA_TOKEN = os.environ.get("HA_TOKEN")
```

## Error Handling

The module provides several exception types:

```python
from home_assistant import (
    HAWebSocketError,    # Generic WebSocket error
    HAAuthError,         # Authentication failed
    HAConnectionClosed,  # Connection closed
    HARequestError       # Request failed
)

try:
    async with HAWebSocketClient(url, token) as ws:
        await ws.call_service(...)
except HAAuthError as e:
    print(f"Authentication failed: {e}")
except HAConnectionClosed as e:
    print(f"Connection closed: {e}")
except HAWebSocketError as e:
    print(f"WebSocket error: {e}")
```

## Dependencies

- `requests` - HTTP requests
- `websockets` - WebSocket connections
- Python 3.10+

## Development

### Run Examples

```bash
# Set environment variables
export HA_TOKEN="your_token_here"

# Run Xiaomi integration example
python -m home_assistant.xiaomi_home_flow

# Run MCP integration example
python -m home_assistant.mcp_server_flow

# Run WebSocket client example
python -m home_assistant.home_assistant_client
```

### Extending with New Integrations

To add new integrations, you can refer to the implementation in `xiaomi_home_flow.py` or `mcp_server_flow.py`:

1. Create a new Python file (e.g., `your_integration_flow.py`)
2. Import the generic infrastructure:
   ```python
   from .home_assistant_api import HomeAssistantIntegrationFlow
   from .home_assistant_client import HAWebSocketClient
   ```
3. Implement integration-specific classes and convenience functions
4. Export in `__init__.py`

## Contributing

Issues and Pull Requests are welcome!

## License

MIT License

## Related Links

- [Home Assistant Official Documentation](https://www.home-assistant.io/)
- [Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket/)
- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/)