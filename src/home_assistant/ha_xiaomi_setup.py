import requests
import json
import asyncio
import websockets
from urllib.parse import urljoin, urlparse

class HomeAssistantXiaomiFlow:
    """
    A class to automate the setup flow for the Xiaomi Home integration in Home Assistant.

    This class encapsulates the series of API calls and the WebSocket communication
    required to add the integration, from starting the flow to the final configuration.
    """

    def __init__(self, base_url: str, token: str, verify_ssl: bool = True):
        """
        Initializes the Xiaomi Home integration flow helper.

        Args:
            base_url (str): The base URL of your Home Assistant instance 
                            (e.g., 'http://192.168.66.28:8123').
            token (str): A Long-Lived Access Token for your Home Assistant user.
            verify_ssl (bool): Whether to verify the SSL certificate. Set to False
                               if you use a self-signed certificate.
        """
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.verify_ssl = verify_ssl
        
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json;charset=UTF-8',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'Accept': '*/*',
        })
        
        self.initial_flow_id = None
        self.final_flow_id = None

    def _start_flow(self) -> str:
        """Initiates the integration configuration flow."""
        url = urljoin(self.base_url, '/api/config/config_entries/flow')
        payload = {"handler": "xiaomi_home", "show_advanced_options": False}
        
        print("Step 1: Starting integration flow...")
        response = self.session.post(url, data=json.dumps(payload), verify=self.verify_ssl)
        response.raise_for_status()
        
        data = response.json()
        self.initial_flow_id = data.get('flow_id')
        if not self.initial_flow_id:
            raise ValueError("Failed to get flow_id from the initial response.")
        
        print(f"   -> Success! Initial Flow ID: {self.initial_flow_id}")
        return self.initial_flow_id

    def _submit_eula(self):
        """Submits the End User License Agreement."""
        if not self.initial_flow_id:
            raise RuntimeError("Flow has not been started. Call _start_flow() first.")
            
        url = urljoin(self.base_url, f'/api/config/config_entries/flow/{self.initial_flow_id}')
        payload = {"eula": True}
        
        print("Step 2: Accepting EULA...")
        response = self.session.post(url, data=json.dumps(payload), verify=self.verify_ssl)
        response.raise_for_status()
        print("   -> Success! EULA accepted.")

    def _submit_auth_config(self, cloud_server: str, language: str, redirect_url: str) -> str:
        """Submits the authentication and server configuration to get the OAuth URL."""
        if not self.initial_flow_id:
            raise RuntimeError("Flow has not been started. Call _start_flow() first.")

        url = urljoin(self.base_url, f'/api/config/config_entries/flow/{self.initial_flow_id}')
        payload = {
            "cloud_server": cloud_server,
            "integration_language": language,
            "oauth_redirect_url": redirect_url,
            "network_detect_config": False
        }
        
        print("Step 3: Submitting server configuration...")
        response = self.session.post(url, data=json.dumps(payload), verify=self.verify_ssl)
        response.raise_for_status()
        
        data = response.json()
        placeholders = data.get('description_placeholders', {})
        link_html = placeholders.get('link_left', '')
        
        if 'href="' in link_html:
            oauth_url = link_html.split('href="')[1].split('"')[0].replace('&amp;', '&')
            print("   -> Success! OAuth URL retrieved.")
            return oauth_url
        else:
            raise ValueError("Could not find the OAuth URL in the response.")

    async def _listen_for_auth_completion(self, timeout: int = 120) -> str:
        """Connects to WebSocket and waits for the authentication to complete."""
        parsed_url = urlparse(self.base_url)
        scheme = 'wss' if parsed_url.scheme == 'https' else 'ws'
        ws_url = f"{scheme}://{parsed_url.netloc}/api/websocket"
        
        print("\nStep 4: Waiting for you to complete authentication in the browser...")
        print(f"   -> Connecting to WebSocket at {ws_url}")
        print(f"   -> Will time out in {timeout} seconds.")

        try:
            async with websockets.connect(ws_url) as websocket:
                auth_response = json.loads(await websocket.recv())
                if auth_response.get("type") != "auth_required":
                    raise ConnectionAbortedError(f"Unexpected WebSocket response: {auth_response}")
                # 1. Authenticate
                await websocket.send(json.dumps({"type": "auth", "access_token": self.token}))
                auth_response = json.loads(await websocket.recv())
                if auth_response.get("type") != "auth_ok":
                    raise ConnectionAbortedError(f"WebSocket authentication failed: {auth_response.get('message')}")
                print("   -> WebSocket authenticated successfully.")

                # 2. Subscribe to flow progress events
                subscription_id = 1
                await websocket.send(json.dumps({
                    "id": subscription_id,
                    "type": "subscribe_events",
                    "event_type": "data_entry_flow_progressed"
                }))
                subscribe_response = json.loads(await websocket.recv())
                if not subscribe_response.get("success"):
                     raise RuntimeError(f"Failed to subscribe to events: {subscribe_response}")
                print("   -> Subscribed to 'data_entry_flow_progressed' events.")

                # 3. Listen for the specific event
                async for message in websocket:
                    data = json.loads(message)
                    if (data.get("type") == "event" and 
                        data["event"]["event_type"] == "data_entry_flow_progressed" and
                        data["event"]["data"]["handler"] == "xiaomi_home"):
                        
                        self.final_flow_id = data["event"]["data"]["flow_id"]
                        print(f"\n   -> Authentication complete! Got new Flow ID: {self.final_flow_id}")
                        return self.final_flow_id
        except asyncio.TimeoutError:
            raise TimeoutError("Timed out waiting for authentication to complete.")
        except Exception as e:
            raise RuntimeError(f"An error occurred with the WebSocket connection: {e}")

    def _get_and_submit_home_selection(self):
        """Fetches available homes and submits the selection to complete the setup."""
        if not self.final_flow_id:
            raise RuntimeError("Final flow ID is not set. Cannot get home selection.")

        # Step 5: Get the list of available homes
        print("\nStep 5: Fetching available Xiaomi homes...")
        url = urljoin(self.base_url, f'/api/config/config_entries/flow/{self.final_flow_id}')
        response = self.session.get(url, verify=self.verify_ssl)
        response.raise_for_status()
        data = response.json()

        # Extract home IDs from the schema
        home_options = {}
        for field in data.get("data_schema", []):
            if field.get("name") == "home_infos":
                home_options = field.get("options", {})
                break
        
        if not home_options:
            raise ValueError("Could not find any homes to select in the response.")

        home_ids = list(home_options.keys())
        print(f"   -> Found homes: {list(home_options.values())}")

        # Step 6: Submit the selected homes
        print("\nStep 6: Submitting home selection to complete setup...")
        payload = {
            "area_name_rule": "room",
            "advanced_options": False,
            "home_infos": home_ids # Automatically select all found homes
        }
        response = self.session.post(url, data=json.dumps(payload), verify=self.verify_ssl)
        response.raise_for_status()
        
        final_response = response.json()
        if final_response.get("type") == "create_entry":
            print("   -> Success! The Xiaomi Home integration has been set up.")
        else:
            raise RuntimeError(f"Final step failed. Response: {final_response}")

    async def run(self, cloud_server: str = 'cn', language: str = 'zh-Hans', redirect_url: str = 'http://homeassistant.local:8123'):
        """
        Executes the complete flow to add the Xiaomi Home integration.
        """
        try:
            self._start_flow()
            self._submit_eula()
            oauth_url = self._submit_auth_config(cloud_server, language, redirect_url)
            
            print("\n" + "="*60)
            print("ACTION REQUIRED:")
            print("Please open the following URL in your browser to log in and authorize:")
            print(f"\n   {oauth_url}\n")
            print("This script will wait for you to complete the login.")
            print("="*60)

            await self._listen_for_auth_completion()
            self._get_and_submit_home_selection()

            return True

        except Exception as e:
            print(f"\n❌ An error occurred during the flow: {e}")
            if isinstance(e, requests.exceptions.RequestException) and e.response is not None:
                print(f"Response body: {e.response.text}")
            return False

if __name__ == '__main__':
    import os
    # --- Configuration ---
    # PLEASE REPLACE THESE VALUES WITH YOUR OWN
    HA_URL = "http://192.168.66.28:8123" 
    HA_TOKEN = os.environ.get("HA_TOKEN", "YOUR_LONG_LIVED_ACCESS_TOKEN")

    # --- Execution ---
    if HA_TOKEN == "YOUR_LONG_LIVED_ACCESS_TOKEN":
        print("Please set the environment variable 'HA_TOKEN' to your actual value.")
    else:
        xiaomi_flow = HomeAssistantXiaomiFlow(base_url=HA_URL, token=HA_TOKEN, verify_ssl=False)
        
        try:
            # The run method is now async, so we use asyncio.run()
            success = asyncio.run(xiaomi_flow.run())
            if success:
                print("\n🎉🎉🎉 All steps completed successfully! 🎉🎉🎉")
            else:
                print("\n🛑 The process failed. Please check the error messages above.")
        except KeyboardInterrupt:
            print("\nProcess interrupted by user.")
