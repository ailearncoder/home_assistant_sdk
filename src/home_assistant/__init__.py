"""
Home Assistant Integration Tools

这个包提供了与Home Assistant交互的工具，包括：
- HTTP API客户端（用户认证、集成配置流程）
- WebSocket客户端（实时事件订阅、服务调用）
- 小米智能家居集成配置
- MCP服务器集成配置
"""

__version__ = "0.1.0"

# 通用模块
from .home_assistant_api import HomeAssistantAuth, HomeAssistantIntegrationFlow
from .home_assistant_client import HAWebSocketClient, HAWebSocketError, HAAuthError, HAConnectionClosed, HARequestError

# 集成专用模块
from .xiaomi_home_flow import XiaomiHomeIntegration, setup_xiaomi_home_integration
from .mcp_server_flow import MCPServerIntegration, setup_mcp_server_integration

__all__ = [
    # 版本
    "__version__",
    
    # HTTP API
    "HomeAssistantAuth",
    "HomeAssistantIntegrationFlow",
    
    # WebSocket Client
    "HAWebSocketClient",
    "HAWebSocketError",
    "HAAuthError",
    "HAConnectionClosed",
    "HARequestError",
    
    # 小米集成
    "XiaomiHomeIntegration",
    "setup_xiaomi_home_integration",
    
    # MCP集成
    "MCPServerIntegration",
    "setup_mcp_server_integration",
]


def main() -> None:
    """主入口函数"""
    print(f"Home Assistant Integration Tools v{__version__}")
    print("\n可用模块：")
    print("  - HomeAssistantAuth: 用户认证和Token管理")
    print("  - HomeAssistantIntegrationFlow: 集成配置流程API")
    print("  - HAWebSocketClient: WebSocket客户端")
    print("  - XiaomiHomeIntegration: 小米智能家居集成")
    print("  - MCPServerIntegration: MCP服务器集成")
    print("\n详细信息请查看文档。")


if __name__ == "__main__":
    main()
