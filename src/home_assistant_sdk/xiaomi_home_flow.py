"""
小米智能家居集成的专用流程管理

此模块包含小米智能家居集成特有的配置流程逻辑。
"""

import asyncio
from typing import Dict, Any, Optional, List
from .home_assistant_api import HomeAssistantIntegrationFlow
from .home_assistant_client import HAWebSocketClient


class XiaomiHomeIntegration:
    """小米智能家居集成专用配置类"""
    
    def __init__(self, api_client: HomeAssistantIntegrationFlow, ws_client: Optional[HAWebSocketClient] = None):
        """
        初始化小米集成配置
        
        参数:
            api_client: HTTP API客户端
            ws_client: WebSocket客户端（用于监听OAuth完成事件）
        """
        self.api = api_client
        self.ws = ws_client
        self.initial_flow_id: Optional[str] = None
        self.final_flow_id: Optional[str] = None
    
    def start_xiaomi_flow(self) -> str:
        """启动小米集成流程"""
        data = self.api.start_flow(handler="xiaomi_home", show_advanced_options=False)
        self.initial_flow_id = data.get('flow_id')
        if not self.initial_flow_id:
            raise ValueError("Failed to get flow_id from the initial response.")
        return self.initial_flow_id
    
    def submit_eula(self) -> None:
        """提交用户许可协议"""
        if not self.initial_flow_id:
            raise RuntimeError("Flow has not been started. Call start_xiaomi_flow() first.")
        
        self.api.submit_flow_step(self.initial_flow_id, {"eula": True})
    
    def submit_auth_config(
        self, 
        cloud_server: str = 'cn', 
        language: str = 'zh-Hans', 
        redirect_url: str = 'http://homeassistant.local:8123'
    ) -> str:
        """
        提交认证配置并获取OAuth URL
        
        参数:
            cloud_server: 云服务器区域
            language: 界面语言
            redirect_url: OAuth重定向URL
            
        返回:
            str: OAuth授权URL
        """
        if not self.initial_flow_id:
            raise RuntimeError("Flow has not been started. Call start_xiaomi_flow() first.")
        
        payload = {
            "cloud_server": cloud_server,
            "integration_language": language,
            "oauth_redirect_url": redirect_url,
            "network_detect_config": False
        }
        
        data = self.api.submit_flow_step(self.initial_flow_id, payload)
        placeholders = data.get('description_placeholders', {})
        link_html = placeholders.get('link_left', '')
        
        if 'href="' in link_html:
            oauth_url = link_html.split('href="')[1].split('"')[0].replace('&amp;', '&')
            return oauth_url
        else:
            raise ValueError("Could not find the OAuth URL in the response.")
    
    async def wait_for_oauth_completion(self, timeout: int = 120) -> str:
        """
        等待用户完成OAuth认证
        
        参数:
            timeout: 超时时间（秒）
            
        返回:
            str: 认证完成后的新flow_id
        """
        if not self.ws:
            raise RuntimeError("WebSocket client is required for this operation.")
        
        self.final_flow_id = await self.ws.wait_for_flow_progress(
            handler="xiaomi_home",
            timeout=timeout
        )
        return self.final_flow_id
    
    def get_available_homes(self) -> Dict[str, str]:
        """获取可用的小米家庭列表"""
        if not self.final_flow_id:
            raise RuntimeError("Final flow ID is not set. Cannot get home selection.")
        
        data = self.api.get_flow_info(self.final_flow_id)
        
        # 从数据模式中提取家庭选项
        home_options = {}
        for field in data.get("data_schema", []):
            if field.get("name") == "home_infos":
                home_options = field.get("options", {})
                break
        
        if not home_options:
            raise ValueError("Could not find any homes to select in the response.")
        
        return home_options
    
    def submit_home_selection(
        self, 
        home_ids: Optional[List[str]] = None,
        area_name_rule: str = "room",
        advanced_options: bool = False
    ) -> Dict[str, Any]:
        """
        提交家庭选择以完成配置
        
        参数:
            home_ids: 要选择的家庭ID列表（None表示选择所有）
            area_name_rule: 区域命名规则
            advanced_options: 是否启用高级选项
            
        返回:
            Dict[str, Any]: 创建结果
        """
        if not self.final_flow_id:
            raise RuntimeError("Final flow ID is not set. Cannot submit home selection.")
        
        # 如果未指定home_ids，则获取所有可用的家庭
        if home_ids is None:
            home_options = self.get_available_homes()
            home_ids = list(home_options.keys())
        
        payload = {
            "area_name_rule": area_name_rule,
            "advanced_options": advanced_options,
            "home_infos": home_ids
        }
        
        result = self.api.submit_flow_step(self.final_flow_id, payload)
        
        if result.get("type") != "create_entry":
            raise RuntimeError(f"Final step failed. Response: {result}")
        
        return result
    
    async def run_full_flow(
        self,
        cloud_server: str = 'cn',
        language: str = 'zh-Hans',
        redirect_url: str = 'http://homeassistant.local:8123'
    ) -> bool:
        """
        执行完整的小米集成配置流程
        
        参数:
            cloud_server: 云服务器区域
            language: 界面语言
            redirect_url: OAuth重定向URL
            
        返回:
            bool: 是否成功
        """
        try:
            # 步骤1: 启动流程
            print("Step 1: Starting xiaomi_home integration flow...")
            self.start_xiaomi_flow()
            print(f"   -> Success! Initial Flow ID: {self.initial_flow_id}")
            
            # 步骤2: 提交EULA
            print("Step 2: Accepting EULA...")
            self.submit_eula()
            print("   -> Success! EULA accepted.")
            
            # 步骤3: 获取OAuth URL
            print("Step 3: Submitting server configuration...")
            oauth_url = self.submit_auth_config(cloud_server, language, redirect_url)
            print("   -> Success! OAuth URL retrieved.")
            
            # 显示OAuth URL供用户访问
            print("\n" + "="*60)
            print("ACTION REQUIRED:")
            print("Please open the following URL in your browser to log in and authorize:")
            print(f"\n   {oauth_url}\n")
            print("This script will wait for you to complete the login.")
            print("="*60)
            
            # 步骤4: 等待OAuth完成
            print("\nStep 4: Waiting for OAuth completion...")
            await self.wait_for_oauth_completion()
            print(f"   -> Authentication complete! Got new Flow ID: {self.final_flow_id}")
            
            # 步骤5: 获取并提交家庭选择
            print("\nStep 5: Fetching available Xiaomi homes...")
            home_options = self.get_available_homes()
            print(f"   -> Found homes: {list(home_options.values())}")
            
            print("\nStep 6: Submitting home selection to complete setup...")
            result = self.submit_home_selection()
            print("   -> Success! The Xiaomi Home integration has been set up.")
            
            return True
            
        except Exception as e:
            print(f"\n❌ An error occurred during the flow: {e}")
            return False


# 使用示例
async def setup_xiaomi_home_integration(
    base_url: str,
    token: str,
    verify_ssl: bool = False
):
    """
    设置小米智能家居集成的便捷函数
    
    参数:
        base_url: Home Assistant的URL
        token: 长期访问令牌
        verify_ssl: 是否验证SSL证书
    """
    from urllib.parse import urlparse
    
    # 创建HTTP API客户端
    api_client = HomeAssistantIntegrationFlow(base_url, token, verify_ssl)
    
    # 创建WebSocket客户端
    parsed_url = urlparse(base_url)
    scheme = 'wss' if parsed_url.scheme == 'https' else 'ws'
    ws_url = f"{scheme}://{parsed_url.netloc}"
    
    async with HAWebSocketClient(ws_url, token, auto_reconnect=False) as ws_client:
        # 创建小米集成实例
        xiaomi = XiaomiHomeIntegration(api_client, ws_client)
        
        # 运行完整流程
        success = await xiaomi.run_full_flow()
        
        if success:
            print("\n🎉🎉🎉 All steps completed successfully! 🎉🎉🎉")
        else:
            print("\n🛑 The process failed. Please check the error messages above.")
        
        return success


if __name__ == '__main__':
    import os
    
    HA_URL = "http://192.168.66.28:8123"
    HA_TOKEN = os.environ.get("HA_TOKEN", "YOUR_LONG_LIVED_ACCESS_TOKEN")
    
    if HA_TOKEN == "YOUR_LONG_LIVED_ACCESS_TOKEN":
        print("Please set the environment variable 'HA_TOKEN' to your actual value.")
    else:
        try:
            asyncio.run(setup_xiaomi_home_integration(HA_URL, HA_TOKEN, verify_ssl=False))
        except KeyboardInterrupt:
            print("\nProcess interrupted by user.")
