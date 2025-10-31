import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import requests


@dataclass
class FlowCreateRequest:
    """创建配置条目流程的请求模型"""
    handler: str = "mcp_server"
    show_advanced_options: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FlowStepResponse:
    """流程步骤响应模型"""
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
    def from_dict(cls, data: Dict[str, Any]) -> 'FlowStepResponse':
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
class FlowSubmitRequest:
    """提交流程配置的请求模型"""
    llm_hass_api: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CreateEntryResponse:
    """创建条目响应模型"""
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
    def from_dict(cls, data: Dict[str, Any]) -> 'CreateEntryResponse':
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


@dataclass
class MCPIntegrationConfig:
    """MCP集成配置模型"""
    host: str
    authorization: str
    user_agent: Optional[str] = None
    
    def get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': self.authorization
        }
        
        if self.user_agent:
            headers['User-Agent'] = self.user_agent
        else:
            headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
        
        return headers


class MCPIntegrationClient:
    """MCP服务器集成客户端"""
    
    def __init__(self, config: MCPIntegrationConfig):
        self.config = config
        self.session = requests.Session()
    
    def create_flow(self) -> FlowStepResponse:
        """创建配置条目流程"""
        url = f"{self.config.host}/api/config/config_entries/flow"
        request_data = FlowCreateRequest()
        
        response = self.session.post(
            url,
            headers=self.config.get_headers(),
            data=json.dumps(request_data.to_dict())
        )
        response.raise_for_status()
        
        data = response.json()
        return FlowStepResponse.from_dict(data)
    
    def submit_flow(self, flow_id: str, llm_hass_api: List[str] = None) -> CreateEntryResponse:
        """提交流程配置"""
        if llm_hass_api is None:
            llm_hass_api = ["assist"]
            
        url = f"{self.config.host}/api/config/config_entries/flow/{flow_id}"
        request_data = FlowSubmitRequest(llm_hass_api=llm_hass_api)
        
        response = self.session.post(
            url,
            headers=self.config.get_headers(),
            data=json.dumps(request_data.to_dict())
        )
        response.raise_for_status()
        
        data = response.json()
        return CreateEntryResponse.from_dict(data)
    
    def setup_mcp_integration(self, llm_hass_api: List[str] = None) -> CreateEntryResponse:
        """完整的MCP集成设置流程"""
        # 第一步：创建流程
        flow_response = self.create_flow()
        print(f"流程创建成功，flow_id: {flow_response.flow_id}")
        
        # 第二步：提交配置
        if llm_hass_api is None:
            # 从数据模式中提取可用的选项
            if flow_response.data_schema:
                schema = flow_response.data_schema[0]
                selector = schema.get('selector', {}).get('select', {})
                options = selector.get('options', [])
                if options:
                    llm_hass_api = [option['value'] for option in options if 'value' in option]
                else:
                    llm_hass_api = ["assist"]
            else:
                llm_hass_api = ["assist"]
        
        entry_response = self.submit_flow(flow_response.flow_id, llm_hass_api)
        print(f"MCP集成设置成功，条目ID: {entry_response.result.get('entry_id')}")
        
        return entry_response


# 使用示例
if __name__ == "__main__":
    # 配置参数
    config = MCPIntegrationConfig(
        host="http://127.0.0.1:18123",
        authorization="Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJiZDg2Y2RlMWYwN2U0NjYwYjQ2MzVlYTBiOGRlODJkNCIsImlhdCI6MTc2MTgxODAwMCwiZXhwIjoyMDc3MTc4MDAwfQ.kSjuj9yQn3ut-imYcocuWj782HTemc9mi3NAqVP-PEo"
    )
    
    client = MCPIntegrationClient(config)
    
    try:
        # 设置MCP集成
        result = client.setup_mcp_integration()
        print(f"集成创建成功: {result.title}")
        print(f"条目ID: {result.result.get('entry_id')}")
        
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
    except Exception as e:
        print(f"集成设置失败: {e}")