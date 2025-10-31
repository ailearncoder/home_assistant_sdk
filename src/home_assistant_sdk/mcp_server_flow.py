"""
MCP服务器集成的专用流程管理

此模块包含MCP服务器集成特有的配置流程逻辑。
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from .home_assistant_api import HomeAssistantIntegrationFlow


@dataclass
class MCPFlowStepResponse:
    """MCP流程步骤响应模型"""
    type: str
    flow_id: str
    handler: str
    data_schema: List[Dict[str, Any]]
    errors: Dict[str, Any]
    description_placeholders: Dict[str, Any]
    last_step: Optional[bool]
    preview: Optional[Any]
    step_id: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPFlowStepResponse':
        return cls(
            type=data.get('type', ''),
            flow_id=data.get('flow_id', ''),
            handler=data.get('handler', ''),
            data_schema=data.get('data_schema', []),
            errors=data.get('errors', {}),
            description_placeholders=data.get('description_placeholders', {}),
            last_step=data.get('last_step'),
            preview=data.get('preview'),
            step_id=data.get('step_id', '')
        )


@dataclass
class MCPCreateEntryResponse:
    """MCP创建条目响应模型"""
    type: str
    flow_id: str
    handler: str
    description: Optional[str]
    description_placeholders: Optional[Dict[str, Any]]
    title: str
    minor_version: int
    options: Dict[str, Any]
    subentries: List[Any]
    version: int
    result: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MCPCreateEntryResponse':
        return cls(
            type=data.get('type', ''),
            flow_id=data.get('flow_id', ''),
            handler=data.get('handler', ''),
            description=data.get('description'),
            description_placeholders=data.get('description_placeholders'),
            title=data.get('title', ''),
            minor_version=data.get('minor_version', 1),
            options=data.get('options', {}),
            subentries=data.get('subentries', []),
            version=data.get('version', 1),
            result=data.get('result', {})
        )


class MCPServerIntegration:
    """MCP服务器集成专用配置类"""
    
    def __init__(self, api_client: HomeAssistantIntegrationFlow):
        """
        初始化MCP服务器集成配置
        
        参数:
            api_client: HTTP API客户端
        """
        self.api = api_client
        self.flow_id: Optional[str] = None
    
    def create_flow(self) -> MCPFlowStepResponse:
        """
        创建MCP配置条目流程
        
        返回:
            MCPFlowStepResponse: 流程响应
        """
        data = self.api.start_flow(handler="mcp_server", show_advanced_options=False)
        self.flow_id = data.get('flow_id')
        return MCPFlowStepResponse.from_dict(data)
    
    def submit_flow(self, llm_hass_api: Optional[List[str]] = None) -> MCPCreateEntryResponse:
        """
        提交流程配置
        
        参数:
            llm_hass_api: LLM API选项列表（默认为["assist"]）
            
        返回:
            MCPCreateEntryResponse: 创建响应
        """
        if not self.flow_id:
            raise RuntimeError("Flow has not been created. Call create_flow() first.")
        
        if llm_hass_api is None:
            llm_hass_api = ["assist"]
        
        payload = {"llm_hass_api": llm_hass_api}
        data = self.api.submit_flow_step(self.flow_id, payload)
        return MCPCreateEntryResponse.from_dict(data)
    
    def extract_available_options(self, flow_response: MCPFlowStepResponse) -> List[str]:
        """
        从流程响应中提取可用的LLM API选项
        
        参数:
            flow_response: 流程响应数据
            
        返回:
            List[str]: 可用选项列表
        """
        if flow_response.data_schema:
            schema = flow_response.data_schema[0]
            selector = schema.get('selector', {}).get('select', {})
            options = selector.get('options', [])
            if options:
                return [option['value'] for option in options if 'value' in option]
        
        return ["assist"]
    
    def setup_integration(self, llm_hass_api: Optional[List[str]] = None) -> MCPCreateEntryResponse:
        """
        完整的MCP集成设置流程
        
        参数:
            llm_hass_api: LLM API选项列表（None表示使用所有可用选项）
            
        返回:
            MCPCreateEntryResponse: 创建结果
        """
        # 第一步：创建流程
        print("Step 1: Creating MCP integration flow...")
        flow_response = self.create_flow()
        print(f"   -> Success! Flow ID: {flow_response.flow_id}")
        
        # 第二步：提取可用选项（如果未指定）
        if llm_hass_api is None:
            llm_hass_api = self.extract_available_options(flow_response)
            print(f"   -> Available options: {llm_hass_api}")
        
        # 第三步：提交配置
        print("Step 2: Submitting MCP configuration...")
        entry_response = self.submit_flow(llm_hass_api)
        print(f"   -> Success! Entry ID: {entry_response.result.get('entry_id')}")
        
        return entry_response


def setup_mcp_server_integration(
    base_url: str,
    token: str,
    llm_hass_api: Optional[List[str]] = None,
    verify_ssl: bool = False
) -> MCPCreateEntryResponse:
    """
    设置MCP服务器集成的便捷函数
    
    参数:
        base_url: Home Assistant的URL
        token: 长期访问令牌
        llm_hass_api: LLM API选项列表（None表示使用所有可用选项）
        verify_ssl: 是否验证SSL证书
        
    返回:
        MCPCreateEntryResponse: 创建结果
    """
    # 创建HTTP API客户端
    api_client = HomeAssistantIntegrationFlow(base_url, token, verify_ssl)
    
    # 创建MCP集成实例
    mcp = MCPServerIntegration(api_client)
    
    # 运行完整流程
    result = mcp.setup_integration(llm_hass_api)
    
    print(f"\n🎉 MCP集成设置成功: {result.title}")
    print(f"   Entry ID: {result.result.get('entry_id')}")
    
    return result


if __name__ == "__main__":
    import os
    
    # 配置参数
    HA_URL = "http://127.0.0.1:18123"
    HA_TOKEN = os.environ.get("HA_TOKEN", "YOUR_LONG_LIVED_ACCESS_TOKEN")
    
    if HA_TOKEN == "YOUR_LONG_LIVED_ACCESS_TOKEN":
        print("Please set the environment variable 'HA_TOKEN' to your actual value.")
    else:
        try:
            result = setup_mcp_server_integration(HA_URL, HA_TOKEN)
            print(f"\n✅ Integration successfully created!")
        except Exception as e:
            print(f"\n❌ Integration setup failed: {e}")
