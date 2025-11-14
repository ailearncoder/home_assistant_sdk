# 使用示例

本文档展示如何使用重构后的模块。

## 1. 基础认证

### 获取访问令牌

```python
import os
from home_assistant import HomeAssistantAuth

# 配置
HA_URL = "http://192.168.66.28:8123"
HA_USERNAME = "admin"
HA_PASSWORD = "admin123"

# 创建认证客户端
auth = HomeAssistantAuth(url=HA_URL, username=HA_USERNAME, password=HA_PASSWORD)

# 获取Token
token_info = auth.get_token()
access_token = token_info.get("access_token")
refresh_token = token_info.get("refresh_token")

print(f"Access Token: {access_token}")
print(f"Refresh Token: {refresh_token}")

# 刷新Token
new_token = auth.refresh_token(
    client_id=f"{HA_URL}/",
    refresh_token=refresh_token
)

# 撤销Token（当不再需要时）
try:
    success = auth.revoke_token(access_token)
    print(f"Token撤销成功: {success}")
except Exception as e:
    print(f"Token撤销失败: {e}")
```

## 2. 小米智能家居集成

### 方式一：使用便捷函数（推荐）

```python
import asyncio
import os
from home_assistant import setup_xiaomi_home_integration

async def main():
    HA_URL = "http://192.168.66.28:8123"
    HA_TOKEN = os.environ.get("HA_TOKEN")
    
    # 一键设置小米集成
    success = await setup_xiaomi_home_integration(
        base_url=HA_URL,
        token=HA_TOKEN,
        verify_ssl=False
    )
    
    if success:
        print("✅ 小米集成设置成功！")
    else:
        print("❌ 小米集成设置失败")

asyncio.run(main())
```

### 方式二：使用类（更多控制）

```python
import asyncio
from home_assistant import (
    HomeAssistantIntegrationFlow,
    HAWebSocketClient,
    XiaomiHomeIntegration
)

async def main():
    HA_URL = "http://192.168.66.28:8123"
    HA_TOKEN = "YOUR_TOKEN"
    
    # 创建HTTP API客户端
    api = HomeAssistantIntegrationFlow(HA_URL, HA_TOKEN, verify_ssl=False)
    
    # 创建WebSocket客户端
    async with HAWebSocketClient("ws://192.168.66.28:8123", HA_TOKEN) as ws:
        # 创建小米集成实例
        xiaomi = XiaomiHomeIntegration(api, ws)
        
        # 启动流程
        flow_id = xiaomi.start_xiaomi_flow()
        print(f"Flow ID: {flow_id}")
        
        # 提交EULA
        xiaomi.submit_eula()
        
        # 获取OAuth URL
        oauth_url = xiaomi.submit_auth_config(
            cloud_server='cn',
            language='zh-Hans'
        )
        print(f"请访问: {oauth_url}")
        
        # 等待OAuth完成
        new_flow_id = await xiaomi.wait_for_oauth_completion(timeout=120)
        
        # 获取可用家庭
        homes = xiaomi.get_available_homes()
        print(f"可用家庭: {homes}")
        
        # 提交家庭选择
        result = xiaomi.submit_home_selection()
        print(f"设置完成: {result}")

asyncio.run(main())
```

### 方式三：自定义流程

```python
import asyncio
from home_assistant import (
    HomeAssistantIntegrationFlow,
    HAWebSocketClient,
    XiaomiHomeIntegration
)

async def custom_xiaomi_setup():
    HA_URL = "http://192.168.66.28:8123"
    HA_TOKEN = "YOUR_TOKEN"
    
    api = HomeAssistantIntegrationFlow(HA_URL, HA_TOKEN, verify_ssl=False)
    
    async with HAWebSocketClient("ws://192.168.66.28:8123", HA_TOKEN) as ws:
        xiaomi = XiaomiHomeIntegration(api, ws)
        
        # 只选择特定的家庭
        xiaomi.start_xiaomi_flow()
        xiaomi.submit_eula()
        oauth_url = xiaomi.submit_auth_config()
        
        print(f"请在浏览器中打开: {oauth_url}")
        
        await xiaomi.wait_for_oauth_completion()
        
        homes = xiaomi.get_available_homes()
        print(f"可用家庭: {homes}")
        
        # 只选择第一个家庭
        selected_home_id = list(homes.keys())[0]
        result = xiaomi.submit_home_selection(home_ids=[selected_home_id])
        
        print(f"已添加家庭: {homes[selected_home_id]}")

asyncio.run(custom_xiaomi_setup())
```

## 3. MCP服务器集成

### 方式一：使用便捷函数（推荐）

```python
import os
from home_assistant import setup_mcp_server_integration

# 配置
HA_URL = "http://127.0.0.1:18123"
HA_TOKEN = os.environ.get("HA_TOKEN")

# 一键设置MCP集成
result = setup_mcp_server_integration(
    base_url=HA_URL,
    token=HA_TOKEN,
    llm_hass_api=None,  # None表示使用所有可用选项
    verify_ssl=False
)

print(f"✅ MCP集成设置成功！")
print(f"Entry ID: {result.result.get('entry_id')}")
```

### 方式二：使用类（更多控制）

```python
from home_assistant import (
    HomeAssistantIntegrationFlow,
    MCPServerIntegration
)

HA_URL = "http://127.0.0.1:18123"
HA_TOKEN = "YOUR_TOKEN"

# 创建HTTP API客户端
api = HomeAssistantIntegrationFlow(HA_URL, HA_TOKEN, verify_ssl=False)

# 创建MCP集成实例
mcp = MCPServerIntegration(api)

# 创建流程
flow_response = mcp.create_flow()
print(f"Flow ID: {flow_response.flow_id}")

# 提取可用选项
options = mcp.extract_available_options(flow_response)
print(f"可用选项: {options}")

# 只选择特定选项
entry_response = mcp.submit_flow(llm_hass_api=["assist"])
print(f"Entry ID: {entry_response.result.get('entry_id')}")
```

## 4. WebSocket客户端使用

### 订阅事件

```python
import asyncio
from home_assistant import HAWebSocketClient

async def on_state_changed(event):
    entity_id = event.get("data", {}).get("entity_id")
    print(f"状态变化: {entity_id}")

async def main():
    HA_URL = "ws://192.168.66.28:8123"
    HA_TOKEN = "YOUR_TOKEN"
    
    async with HAWebSocketClient(HA_URL, HA_TOKEN) as ws:
        # 订阅状态变化事件
        sub_id = await ws.subscribe_events(
            on_state_changed,
            event_type="state_changed"
        )
        
        # 运行一段时间
        await asyncio.sleep(60)
        
        # 取消订阅
        await ws.unsubscribe_events(sub_id)

asyncio.run(main())
```

### 调用服务

```python
import asyncio
from home_assistant import HAWebSocketClient

async def main():
    HA_URL = "ws://192.168.66.28:8123"
    HA_TOKEN = "YOUR_TOKEN"
    
    async with HAWebSocketClient(HA_URL, HA_TOKEN) as ws:
        # 打开灯
        await ws.call_service(
            domain="light",
            service="turn_on",
            target={"entity_id": "light.living_room"},
            service_data={"brightness_pct": 80}
        )
        
        await asyncio.sleep(5)
        
        # 关闭灯
        await ws.call_service(
            domain="light",
            service="turn_off",
            target={"entity_id": "light.living_room"}
        )

asyncio.run(main())
```

### 获取状态

```python
import asyncio
from home_assistant import HAWebSocketClient

async def main():
    HA_URL = "ws://192.168.66.28:8123"
    HA_TOKEN = "YOUR_TOKEN"
    
    async with HAWebSocketClient(HA_URL, HA_TOKEN) as ws:
        # 获取所有状态
        states = await ws.get_states()
        print(f"总共 {len(states)} 个实体")
        
        # 获取配置
        config = await ws.get_config()
        print(f"Home Assistant版本: {config.get('version')}")
        
        # 获取服务列表
        services = await ws.get_services()
        print(f"可用域: {list(services.keys())}")

asyncio.run(main())
```

## 5. 通用集成流程API

如果你需要添加其他集成，可以直接使用通用API：

```python
from home_assistant import HomeAssistantIntegrationFlow

api = HomeAssistantIntegrationFlow(
    base_url="http://192.168.66.28:8123",
    token="YOUR_TOKEN"
)

# 启动任意集成
data = api.start_flow(handler="your_integration_name")
flow_id = data.get("flow_id")

# 提交数据
result = api.submit_flow_step(flow_id, {"key": "value"})

# 获取流程信息
info = api.get_flow_info(flow_id)
```

## 6. 监听流程进展（通用）

```python
import asyncio
from home_assistant import HAWebSocketClient

async def main():
    async with HAWebSocketClient("ws://192.168.66.28:8123", "YOUR_TOKEN") as ws:
        # 等待任意集成的流程进展
        new_flow_id = await ws.wait_for_flow_progress(
            handler="your_integration_name",
            timeout=120
        )
        print(f"流程已进展到新阶段: {new_flow_id}")

asyncio.run(main())
```

## 环境变量配置

建议使用环境变量存储敏感信息：

```bash
# .env 文件
export HA_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
export HA_URL="http://192.168.66.28:8123"
```

在代码中使用：

```python
import os

HA_URL = os.environ.get("HA_URL", "http://localhost:8123")
HA_TOKEN = os.environ.get("HA_TOKEN")

if not HA_TOKEN:
    raise ValueError("请设置 HA_TOKEN 环境变量")
```

## 错误处理

```python
import asyncio
from home_assistant import (
    setup_xiaomi_home_integration,
    HAWebSocketError,
    HAAuthError,
    HAConnectionClosed
)

async def main():
    try:
        await setup_xiaomi_home_integration(
            base_url="http://192.168.66.28:8123",
            token="YOUR_TOKEN"
        )
    except HAAuthError as e:
        print(f"❌ 认证失败: {e}")
    except HAConnectionClosed as e:
        print(f"❌ 连接已关闭: {e}")
    except HAWebSocketError as e:
        print(f"❌ WebSocket错误: {e}")
    except Exception as e:
        print(f"❌ 未知错误: {e}")

asyncio.run(main())
```

## 完整示例：从认证到集成

```python
import asyncio
import os
from home_assistant import (
    HomeAssistantAuth,
    setup_xiaomi_home_integration,
    setup_mcp_server_integration
)

async def setup_all():
    # 配置
    HA_URL = "http://192.168.66.28:8123"
    HA_USERNAME = "admin"
    HA_PASSWORD = "admin123"
    
    # 步骤1: 获取Token
    print("步骤1: 获取访问令牌...")
    auth = HomeAssistantAuth(HA_URL, HA_USERNAME, HA_PASSWORD)
    token_info = auth.get_token()
    access_token = token_info.get("access_token")
    print(f"✅ 获取到Token: {access_token[:20]}...")
    
    # 步骤2: 设置小米集成
    print("\n步骤2: 设置小米智能家居集成...")
    success = await setup_xiaomi_home_integration(HA_URL, access_token)
    if success:
        print("✅ 小米集成设置成功")
    
    # 步骤3: 设置MCP集成
    print("\n步骤3: 设置MCP服务器集成...")
    result = setup_mcp_server_integration(HA_URL, access_token)
    print(f"✅ MCP集成设置成功，Entry ID: {result.result.get('entry_id')}")
    
    print("\n🎉 所有集成设置完成！")

if __name__ == "__main__":
    asyncio.run(setup_all())
```

## 注意事项

1. **SSL验证**: 如果使用自签名证书，需要设置 `verify_ssl=False`
2. **超时时间**: OAuth等待时间默认120秒，可根据需要调整
3. **Token安全**: 不要将Token硬编码在代码中，使用环境变量
4. **错误处理**: 生产环境中务必添加适当的错误处理
5. **WebSocket连接**: 使用 `async with` 确保连接正确关闭
