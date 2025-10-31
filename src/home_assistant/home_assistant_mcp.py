import json
import hashlib
import yaml
from typing import Any, Dict, List, Optional

from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from mcp.types import TextContent

# --- Constants ---
CONTEXT_PREFIX = "Live Context: An overview of the areas and the devices in this smart home:"

class HomeAssistantController:
    """A controller to interact with the Home Assistant MCP server."""

    def __init__(self, config_path: str = "config.json"):
        """
        Initializes the controller by loading config and creating a client.

        Args:
            config_path: Path to the JSON configuration file.
        """
        self.config = self._load_config(config_path)
        self.client = Client(self.config)
        self._context: Optional[List[Dict[str, Any]]] = None
        self._context_hash: Optional[str] = None

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Loads configuration from a JSON file."""
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            raise ToolError(f"Configuration file not found at: {config_path}")
        except json.JSONDecodeError as e:
            raise ToolError(f"Error parsing JSON configuration: {e}")

    async def _get_raw_context(self) -> str:
        """Fetches the raw context string from the Home Assistant server."""
        async with self.client:
            context_response = await self.client.call_tool("GetLiveContext")
            if not context_response.content or not isinstance(context_response.content[0], TextContent):
                raise ToolError("Received an empty or invalid response from GetLiveContext.")

            context_json = json.loads(context_response.content[0].text)
            if not context_json.get("success"):
                raise ToolError(f"API call to GetLiveContext failed: {context_json.get('result')}")

            result_str = context_json.get("result", "")
            return result_str.replace(CONTEXT_PREFIX, "").strip()

    def _process_context(self, context_list: List[Dict[str, Any]]) -> None:
        """Adds a unique MD5 hash ID to each device in the context list."""
        for item in context_list:
            names = item.get("names", "")
            item["id"] = hashlib.md5(names.encode("utf-8")).hexdigest()

    async def get_processed_context(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves and processes the device context from Home Assistant.

        Caches the context to avoid redundant API calls. The cache is
        invalidated if the raw context from the server has changed.

        Args:
            force_refresh: If True, forces a refresh of the context from the server.

        Returns:
            A list of dictionaries, each representing a device with a unique 'id'.
        """
        raw_context_str = await self._get_raw_context()
        new_hash = hashlib.md5(raw_context_str.encode("utf-8")).hexdigest()

        if force_refresh or self._context is None or self._context_hash != new_hash:
            try:
                # The context from Home Assistant is still in YAML format, so we use yaml.safe_load here.
                # If the API also returns JSON, you can change this to json.loads().
                context_list = yaml.safe_load(raw_context_str)
                if not isinstance(context_list, list):
                     raise ToolError("Parsed context from Home Assistant is not a list.")
                self._process_context(context_list)
                self._context = context_list
                self._context_hash = new_hash
            except yaml.YAMLError as e:
                raise ToolError(f"Error parsing YAML from context: {e}")
        
        if self._context is None:
            raise ToolError("Failed to load context.")

        return self._context

    async def _hass_turn(self, names: str, areas: str, on: bool) -> Dict[str, Any]:
        """Helper function to turn a device on or off via MCP tool call."""
        tool_name = "HassTurnOn" if on else "HassTurnOff"
        arguments = {"name": names, "area": areas}
        async with self.client:
            result = await self.client.call_tool(name=tool_name, arguments=arguments)
            return json.loads(result.content[0].text)

    async def control_switch(self, device_ids: List[str], on: bool) -> List[Dict[str, Any]]:
        """
        Finds devices by their IDs and controls their state (on/off).

        Args:
            device_ids: A list of unique IDs of the devices to control.
            on: True to turn on, False to turn off.

        Returns:
            A list of dictionaries, each representing the result of an operation.
        """
        context = await self.get_processed_context()
        results = []
        
        for device_id in device_ids:
            target_device = next((item for item in context if item.get("id") == device_id), None)

            if not target_device:
                results.append({"success": False, "error": f"Device with id '{device_id}' not found."})
                continue

            names = target_device.get("names")
            areas = target_device.get("areas")

            if names is None or areas is None:
                results.append({"success": False, "error": f"Device '{device_id}' is missing 'names' or 'areas' information."})
                continue

            try:
                result = await self._hass_turn(names, areas, on)
                results.append({"success": True, "device_id": device_id, "result": result})
            except Exception as e:
                results.append({"success": False, "device_id": device_id, "error": str(e)})
        
        return results

    async def _hass_light_set(self, names: str, area: str, brightness: Optional[int] = None) -> Dict[str, Any]:
        """Helper function to set light brightness via MCP tool call."""
        arguments = {"name": names, "area": area}
        if brightness is not None:
            arguments["brightness"] = brightness
        
        async with self.client:
            result = await self.client.call_tool(name="HassLightSet", arguments=arguments)
            return json.loads(result.content[0].text)

    async def control_light_brightness(self, device_ids: List[str], brightness: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Finds light devices by their IDs and sets their brightness.

        Args:
            device_ids: A list of unique IDs of the light devices to control.
            brightness: Brightness percentage (0-100), or None to turn off.

        Returns:
            A list of dictionaries, each representing the result of an operation.
        """
        context = await self.get_processed_context()
        results = []
        
        for device_id in device_ids:
            target_device = next((item for item in context if item.get("id") == device_id), None)

            if not target_device:
                results.append({"success": False, "error": f"Device with id '{device_id}' not found."})
                continue

            names = target_device.get("names")
            areas = target_device.get("areas")

            if names is None or areas is None:
                results.append({"success": False, "error": f"Device '{device_id}' is missing 'names' or 'areas' information."})
                continue

            try:
                result = await self._hass_light_set(names, areas, brightness)
                results.append({"success": True, "device_id": device_id, "result": result})
            except Exception as e:
                results.append({"success": False, "device_id": device_id, "error": str(e)})
        
        return results

# --- FastMCP Tool Definition ---

mcp_home_assistant = FastMCP(
    name="HomeAssistant",
    instructions="A tool to control devices in a Home Assistant smart home.",
)

# Instantiate the controller.
try:
    # The default path is now config.json, so no argument is needed if the file is in the same directory.
    controller = HomeAssistantController()
except ToolError as e:
    print(f"FATAL: Failed to initialize HomeAssistantController: {e}")
    controller = None

@mcp_home_assistant.tool
async def get_device_info() -> List[Dict[str, Any]]:
    """
    Get information about all available devices.
    Before using switch_control, you should call this tool to get the device 'id'.
    """
    if not controller:
        raise ToolError("HomeAssistantController is not initialized.")
    try:
        return await controller.get_processed_context(force_refresh=True)
    except Exception as e:
        raise ToolError(f"An error occurred while getting device info: {e}")

@mcp_home_assistant.tool
async def switch_control(id: List[str], on: bool) -> List[Dict[str, Any]]:
    """
    Control switch devices.

    Args:
        id: A list of device 'id's, obtained from get_device_info.
        on: Set to true to turn the devices on, false to turn them off.
    """
    if not controller:
        raise ToolError("HomeAssistantController is not initialized.")
    try:
        return await controller.control_switch(device_ids=id, on=on)
    except Exception as e:
        raise ToolError(f"An error occurred during switch control: {e}")

@mcp_home_assistant.tool
async def light_set(id: List[str], brightness: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Set the brightness percentage of light devices.

    Args:
        id: A list of device 'id's, obtained from get_device_info.
        brightness: Brightness percentage (0-100), or None to turn off.
    """
    if not controller:
        raise ToolError("HomeAssistantController is not initialized.")
    try:
        return await controller.control_light_brightness(device_ids=id, brightness=brightness)
    except Exception as e:
        raise ToolError(f"An error occurred during light brightness control: {e}")

if __name__ == "__main__":
    if controller:
        mcp_home_assistant.run()
