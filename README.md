# Home Assistant Integration Tools

一个用于与Home Assistant交互的Python工具包，提供HTTP API、WebSocket客户端以及常用集成的自动化配置功能。

## 功能特性

### 🔐 认证管理
- 用户名密码登录
- 长期访问令牌（Long-Lived Access Token）管理
- Token刷新

### 🌐 HTTP API客户端
- 通用的集成配置流程API
- 支持所有Home Assistant集成的标准配置流程
- 流程步骤管理（启动、提交、查询）

### 🔌 WebSocket客户端
- 完整的异步WebSocket客户端实现
- 事件订阅与推送
- 服务调用
- 状态查询
- 自动重连与心跳保活
- 流程进展监听

### 🏠 集成专用模块

#### 小米智能家居集成
- 自动化EULA接受
- OAuth认证流程处理
- 家庭列表获取与选择
- 完整的配置向导

#### MCP服务器集成
- 流程创建与配置
- LLM API选项管理
- 一键式集成设置

## 安装

```bash
# 克隆仓库
git clone <repository-url>
cd home_assistant

# 安装依赖（使用uv或pip）
uv sync
# 或
pip install -e .
```

## 快速开始

### 1. 获取访问令牌

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

### 2. 设置小米智能家居集成

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

### 3. 设置MCP服务器集成

```python
from home_assistant import setup_mcp_server_integration

result = setup_mcp_server_integration(
    base_url="http://192.168.66.28:8123",
    token=access_token
)
print(f"Entry ID: {result.result.get('entry_id')}")
```

### 4. 使用WebSocket客户端

```python
import asyncio
from home_assistant import HAWebSocketClient

async def main():
    async with HAWebSocketClient("ws://192.168.66.28:8123", access_token) as ws:
        # 获取所有状态
        states = await ws.get_states()
        print(f"Total entities: {len(states)}")
        
        # 调用服务
        await ws.call_service(
            domain="light",
            service="turn_on",
            target={"entity_id": "light.living_room"}
        )

asyncio.run(main())
```

## 项目结构

```
src/home_assistant/
├── __init__.py                 # 包导出和初始化
├── home_assistant_api.py       # HTTP API客户端（通用）
├── home_assistant_client.py    # WebSocket客户端（通用）
├── xiaomi_home_flow.py         # 小米智能家居集成专用
├── mcp_server_flow.py          # MCP服务器集成专用
├── ha_xiaomi_setup.py          # [废弃] 旧版小米集成代码
└── mcp_integration.py          # [废弃] 旧版MCP集成代码
```

### 核心模块说明

| 模块 | 功能 | 类型 |
|------|------|------|
| `home_assistant_api.py` | HTTP请求的通用封装 | 通用 |
| `home_assistant_client.py` | WebSocket连接的通用封装 | 通用 |
| `xiaomi_home_flow.py` | 小米集成的特定流程 | 专用 |
| `mcp_server_flow.py` | MCP集成的特定流程 | 专用 |

## 文档

- [重构总结](./REFACTORING_SUMMARY.md) - 详细的重构说明和架构设计
- [使用示例](./USAGE_EXAMPLES.md) - 完整的使用示例和最佳实践

## API参考

### HomeAssistantAuth

用户认证和Token管理。

```python
auth = HomeAssistantAuth(url, username, password)
token_info = auth.get_token()
new_token = auth.refresh_token(client_id, refresh_token)
```

### HomeAssistantIntegrationFlow

通用的集成配置流程HTTP API。

```python
api = HomeAssistantIntegrationFlow(base_url, token, verify_ssl=True)
flow_data = api.start_flow(handler="integration_name")
result = api.submit_flow_step(flow_id, data)
info = api.get_flow_info(flow_id)
```

### HAWebSocketClient

异步WebSocket客户端。

```python
async with HAWebSocketClient(ws_url, token) as ws:
    # 订阅事件
    sub_id = await ws.subscribe_events(callback, event_type="state_changed")
    
    # 调用服务
    await ws.call_service(domain, service, service_data, target)
    
    # 获取状态
    states = await ws.get_states()
    config = await ws.get_config()
    services = await ws.get_services()
    
    # 等待流程进展
    flow_id = await ws.wait_for_flow_progress(handler, timeout)
    
    # 取消订阅
    await ws.unsubscribe_events(sub_id)
```

### XiaomiHomeIntegration

小米智能家居集成专用类。

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

MCP服务器集成专用类。

```python
mcp = MCPServerIntegration(api_client)
flow_response = mcp.create_flow()
options = mcp.extract_available_options(flow_response)
entry_response = mcp.submit_flow(llm_hass_api)
```

## 便捷函数

### setup_xiaomi_home_integration

一键设置小米智能家居集成。

```python
await setup_xiaomi_home_integration(
    base_url="http://192.168.66.28:8123",
    token="YOUR_TOKEN",
    verify_ssl=False
)
```

### setup_mcp_server_integration

一键设置MCP服务器集成。

```python
result = setup_mcp_server_integration(
    base_url="http://192.168.66.28:8123",
    token="YOUR_TOKEN",
    llm_hass_api=None,  # None表示使用所有可用选项
    verify_ssl=False
)
```

## 环境变量

建议使用环境变量存储敏感信息：

```bash
export HA_URL="http://192.168.66.28:8123"
export HA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

在代码中使用：

```python
import os

HA_URL = os.environ.get("HA_URL")
HA_TOKEN = os.environ.get("HA_TOKEN")
```

## 错误处理

模块提供了多种异常类型：

```python
from home_assistant import (
    HAWebSocketError,    # 通用WebSocket错误
    HAAuthError,         # 认证失败
    HAConnectionClosed,  # 连接已关闭
    HARequestError       # 请求失败
)

try:
    async with HAWebSocketClient(url, token) as ws:
        await ws.call_service(...)
except HAAuthError as e:
    print(f"认证失败: {e}")
except HAConnectionClosed as e:
    print(f"连接关闭: {e}")
except HAWebSocketError as e:
    print(f"WebSocket错误: {e}")
```

## 依赖项

- `requests` - HTTP请求
- `websockets` - WebSocket连接
- Python 3.10+

## 开发

### 运行示例

```bash
# 设置环境变量
export HA_TOKEN="your_token_here"

# 运行小米集成示例
python -m home_assistant.xiaomi_home_flow

# 运行MCP集成示例
python -m home_assistant.mcp_server_flow

# 运行WebSocket客户端示例
python -m home_assistant.home_assistant_client
```

### 扩展新集成

如果需要添加新的集成，可以参考 `xiaomi_home_flow.py` 或 `mcp_server_flow.py` 的实现：

1. 创建新的Python文件（如 `your_integration_flow.py`）
2. 导入通用基础设施：
   ```python
   from .home_assistant_api import HomeAssistantIntegrationFlow
   from .home_assistant_client import HAWebSocketClient
   ```
3. 实现集成专用类和便捷函数
4. 在 `__init__.py` 中导出

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License

## 相关链接

- [Home Assistant官方文档](https://www.home-assistant.io/)
- [Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket/)
- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/)
