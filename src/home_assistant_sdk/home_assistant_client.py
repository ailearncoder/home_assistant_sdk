import asyncio
import json
import logging
from collections.abc import Awaitable
from typing import Any, Callable

import websockets
from websockets.asyncio.connection import Connection
from websockets import WebSocketClientProtocol  # pyright: ignore[reportAttributeAccessIssue, reportUnknownVariableType]

logger = logging.getLogger("ha_ws")
logger.setLevel(logging.INFO)

# ============ 自定义异常类型 ============
class HAWebSocketError(Exception):
    """通用 Home Assistant WebSocket 错误。"""

class HAAuthError(HAWebSocketError):
    """鉴权失败。"""

class HAConnectionClosed(HAWebSocketError):
    """连接已关闭。"""

class HARequestError(HAWebSocketError):
    """请求失败（success=false 或返回错误）。"""

# ============ 类型别名 ============
JSONDict = dict[str, Any]
EventCallback = Callable[[JSONDict], Awaitable[None]]

# ============ 客户端实现 ============
class HAWebSocketClient:
    """
    Home Assistant WebSocket API 客户端（异步）。

    主要特性：
    - 支持完整鉴权流程与（可选）特性启用 supported_features（如 coalesce_messages）。
    - 统一的 send_command 接口，自动生成自增 id，结果关联与超时控制。
    - 事件总线订阅 subscribe_events / 触发器订阅 subscribe_trigger，回调基于 asyncio。
    - 常用 API 方法封装：fire_event、call_service、get_states、get_config、get_services、get_panels、validate_config、extract_from_target、unsubscribe_events。
    - 令牌管理：refresh tokens查询、长期访问令牌创建和删除。
    - 自动心跳（ping/pong）与断线重连（指数回退），并自动恢复已建立的订阅。
    - 可作为异步上下文管理器使用：async with HAWebSocketClient(...) as cli: ...
    - 清晰的错误与日志输出。

    依赖：pip install websockets
    """

    def __init__(
        self,
        base_url: str,
        access_token: str,
        *,
        ping_interval: float = 20.0,
        request_timeout: float = 15.0,
        connect_timeout: float = 15.0,
        auto_reconnect: bool = True,
        reconnect_max_delay: float = 60.0,
        enable_coalesce_messages: bool = True,
        on_reconnect: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """
        参数：
        - base_url: 形如 "ws://host:8123" 或 "wss://host:8123"（无需尾部斜杠）。
        - access_token: 长期访问令牌（Profile -> Long-Lived Access Tokens）。
        - ping_interval: 心跳间隔秒数。
        - request_timeout: 单次请求等待 result 的超时秒数。
        - connect_timeout: 连接与鉴权阶段超时秒数。
        - auto_reconnect: 断线后是否自动重连。
        - reconnect_max_delay: 重连回退的最大间隔。
        - enable_coalesce_messages: 是否启用 supported_features.coalesce_messages。
        - on_reconnect: 重连成功后的钩子（在自动恢复订阅之前调用）。
        """
        self._ws_url: str = self._normalize_ws_url(base_url)
        self._token: str = access_token
        self._ping_interval: float = ping_interval
        self._request_timeout: float = request_timeout
        self._connect_timeout: float = connect_timeout
        self._auto_reconnect: bool = auto_reconnect
        self._reconnect_max_delay: float = reconnect_max_delay
        self._enable_coalesce: bool = enable_coalesce_messages
        self._on_reconnect: Callable[[], Awaitable[None]] | None = on_reconnect

        self._ws: WebSocketClientProtocol | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._pinger_task: asyncio.Task[None] | None = None
        self._close_event: asyncio.Event = asyncio.Event()

        self._next_id: int = 1  # 将为 supported_features 预留 id=1
        self._pending: dict[int, asyncio.Future[JSONDict]] = {}
        self._subscriptions: dict[int, EventCallback] = {}
        self._resubscribe_cache: list[JSONDict] = []  # 用于自动重连恢复订阅
        self._lock: asyncio.Lock = asyncio.Lock()  # 保护 send 操作与 id 分配

    # ---------- 公有接口 ----------
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        await self.close()

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._ws.state == websockets.protocol.State.OPEN

    async def connect(self) -> None:
        """
        建立连接并完成鉴权与特性启用流程。
        """
        await self._do_connect(first_connect=True)

    async def close(self) -> None:
        """
        关闭连接并清理资源。
        """
        self._auto_reconnect = False
        self._close_event.set()

        if self._reader_task:
            self._reader_task.cancel()
        if self._pinger_task:
            self._pinger_task.cancel()

        if self._ws and self._ws.state != websockets.protocol.State.CLOSED:
            await self._ws.close()
        self._ws = None

        # 拒绝所有未完成请求
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(HAConnectionClosed("Connection closed"))
        self._pending.clear()

    # === 常用 API 方法封装 ===

    async def subscribe_config_entries(
        self, callback: EventCallback, type_filter: list[str] | None = None
    ) -> int:
        """
        订阅配置条目事件。
        返回 subscription id（即该请求 id），用于取消订阅。
        """
        payload: JSONDict = {"type": "config_entries/subscribe"}
        if type_filter:
            payload["type_filter"] = type_filter
        sub_id = await self._send_and_confirm(payload)
        self._subscriptions[sub_id] = callback
        # 记录以便重连恢复
        self._resubscribe_cache.append({"op": "subscribe_config_entries", "args": {"type_filter": type_filter}})
        return sub_id

    async def subscribe_events(
        self, callback: EventCallback, event_type: str | None = None
    ) -> int:
        """
        订阅事件总线。
        返回 subscription id（即该请求 id），用于取消订阅。
        """
        payload: JSONDict = {"type": "subscribe_events"}
        if event_type:
            payload["event_type"] = event_type
        sub_id = await self._send_and_confirm(payload)
        self._subscriptions[sub_id] = callback
        # 记录以便重连恢复
        self._resubscribe_cache.append({"op": "subscribe_events", "args": {"event_type": event_type}})
        return sub_id

    async def subscribe_trigger(
        self, callback: EventCallback, trigger: JSONDict | list[JSONDict]
    ) -> int:
        """
        订阅自动化触发器（语法同 Home Assistant automation 触发器）。
        """
        payload: JSONDict = {"type": "subscribe_trigger", "trigger": trigger}
        sub_id = await self._send_and_confirm(payload)
        self._subscriptions[sub_id] = callback
        self._resubscribe_cache.append({"op": "subscribe_trigger", "args": {"trigger": trigger}})
        return sub_id

    async def unsubscribe_events(self, subscription_id: int) -> None:
        """
        取消事件/触发器订阅。订阅 id 即最初订阅请求的 id。
        """
        payload = {"type": "unsubscribe_events", "subscription": subscription_id}
        await self._send_and_confirm(payload, bind_id=False)  # 使用新 id 发送取消命令
        self._subscriptions.pop(subscription_id, None)
        # 同步更新重连缓存
        self._resubscribe_cache = [x for x in self._resubscribe_cache if not self._match_sub_restore(x, subscription_id)]

    async def fire_event(self, event_type: str, event_data: JSONDict | None = None) -> JSONDict:
        payload: JSONDict = {"type": "fire_event", "event_type": event_type}
        if event_data:
            payload["event_data"] = event_data
        result = await self._send_and_get_result(payload)
        return result

    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: JSONDict | None = None,
        target: JSONDict | None = None,
        return_response: bool = False,
    ) -> JSONDict:
        payload: JSONDict = {
            "type": "call_service",
            "domain": domain,
            "service": service,
            "return_response": return_response,
        }
        if service_data:
            payload["service_data"] = service_data
        if target:
            payload["target"] = target
        return await self._send_and_get_result(payload)

    async def get_states(self) -> JSONDict:
        return await self._send_and_get_result({"type": "get_states"})

    async def get_config(self) -> JSONDict:
        return await self._send_and_get_result({"type": "get_config"})

    async def get_services(self) -> JSONDict:
        return await self._send_and_get_result({"type": "get_services"})

    async def get_panels(self) -> JSONDict:
        return await self._send_and_get_result({"type": "get_panels"})

    async def ping(self) -> None:
        """
        主动发送一次 ping 并等待服务端 pong。
        """
        req_id = await self._send({"type": "ping"})
        # pong 与 result 不同，是 type=pong，并带同一个 id。
        await self._await_special(req_id, expected_type="pong")

    async def validate_config(
        self,
        trigger: JSONDict | list[JSONDict] | None = None,
        condition: JSONDict | list[JSONDict] | None = None,
        action: JSONDict | list[JSONDict] | None = None,
    ) -> JSONDict:
        payload: JSONDict = {"type": "validate_config"}
        if trigger is not None:
            payload["trigger"] = trigger
        if condition is not None:
            payload["condition"] = condition
        if action is not None:
            payload["action"] = action
        return await self._send_and_get_result(payload)

    async def extract_from_target(
        self,
        target: JSONDict,
        expand_group: bool = False,
    ) -> JSONDict:
        payload: JSONDict = {"type": "extract_from_target", "target": target, "expand_group": expand_group}
        return await self._send_and_get_result(payload)

    async def get_current_user(self) -> JSONDict:
        return await self._send_and_get_result({"type":"auth/current_user"})

    async def get_refresh_tokens(self) -> JSONDict:
        """获取当前用户的所有refresh tokens"""
        return await self._send_and_get_result({"type": "auth/refresh_tokens"})

    async def create_long_lived_token(self, client_name: str, lifespan: int = 3650) -> JSONDict:
        """创建长期访问令牌"""
        payload = {
            "type": "auth/long_lived_access_token",
            "client_name": client_name,
            "lifespan": lifespan
        }
        return await self._send_and_get_result(payload)

    async def delete_refresh_token(self, refresh_token_id: str) -> None:
        """删除指定的refresh token"""
        payload = {
            "type": "auth/delete_refresh_token",
            "refresh_token_id": refresh_token_id
        }
        await self._send_and_get_result(payload)

    async def admin_change_password(self, password: str, user_id: str | None = None) -> None:
        if user_id is None:
            user_id = (await self.get_current_user()).get('id')
        payload: JSONDict = {
            "type": "config/auth_provider/homeassistant/admin_change_password",
            "user_id": user_id,
            "password": password,
        }
        _ = await self._send_and_get_result(payload)

    async def wait_for_flow_progress(
        self, 
        handler: str,
        timeout: int = 120,
        callback: Callable[[str], Awaitable[None]] | None = None
    ) -> str:
        """
        等待指定集成的流程进展事件
        
        参数:
            handler (str): 集成处理器名称 (例如: 'xiaomi_home')
            timeout (int): 超时时间（秒）
            callback (Callable): 可选的回调函数，在接收到事件时调用
            
        返回:
            str: 新的 flow_id
        """
        flow_id_future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        
        async def on_flow_progress(event: JSONDict) -> None:
            event_data = event.get("data", {})
            if event_data.get("handler") == handler:
                new_flow_id = event_data.get("flow_id")
                if new_flow_id and not flow_id_future.done():
                    flow_id_future.set_result(new_flow_id)
                if callback:
                    await callback(new_flow_id)
        
        # 订阅流程进展事件
        sub_id = await self.subscribe_events(
            on_flow_progress, 
            event_type="data_entry_flow_progressed"
        )
        
        try:
            result = await asyncio.wait_for(flow_id_future, timeout=timeout)
            return result
        finally:
            # 取消订阅
            await self.unsubscribe_events(sub_id)

    # ---------- 内部：连接与鉴权 ----------
    @staticmethod
    def _normalize_ws_url(base: str) -> str:
        base = base.rstrip("/")
        if base.startswith("ws://") or base.startswith("wss://"):
            return f"{base}/api/websocket"
        # 自动补齐协议（默认 wss）
        return f"wss://{base}/api/websocket"

    async def _do_connect(self, *, first_connect: bool) -> None:
        backoff = 1.5
        delay = 1.0
        while True:
            try:
                logger.info("Connecting to %s", self._ws_url)
                # 修复类型问题：直接等待连接而不使用 wait_for
                self._ws = await websockets.connect(self._ws_url)
                await self._handshake_and_auth()
                await self._maybe_enable_features()

                # 启动后台任务
                self._close_event.clear()
                self._reader_task = asyncio.create_task(self._reader_loop(), name="ha_ws_reader")
                self._pinger_task = asyncio.create_task(self._pinger_loop(), name="ha_ws_pinger")

                if not first_connect and self._on_reconnect:
                    await self._on_reconnect()

                # 自动恢复订阅
                if not first_connect:
                    await self._restore_subscriptions()

                logger.info("Connected and ready")
                return
            except Exception as e:
                logger.warning("Connect/auth failed: %s", e)
                if not self._auto_reconnect:
                    raise
                # 回退等待
                await asyncio.sleep(delay)
                delay = min(delay * backoff, self._reconnect_max_delay)

    async def _handshake_and_auth(self) -> None:
        """
        完成 auth_required -> 发送 auth -> 等待 auth_ok。
        """
        assert self._ws is not None
        # 接收首条 auth_required
        msg = await self._recv_json()
        if isinstance(msg, dict) and msg.get("type") != "auth_required":
            raise HAAuthError(f"Expected auth_required, got: {msg}")

        # 发送 auth
        await self._send_raw({"type": "auth", "access_token": self._token}, with_id=False)

        # 等待 auth_ok 或 auth_invalid
        msg2 = await self._recv_json()
        if isinstance(msg2, dict) and msg2.get("type") == "auth_ok":
            return
        if isinstance(msg2, dict) and msg2.get("type") == "auth_invalid":
            raise HAAuthError(f"Auth invalid: {msg2.get('message')}")
        raise HAAuthError(f"Unexpected auth response: {msg2}")

    async def _maybe_enable_features(self) -> None:
        """
        特性启用阶段：当前仅支持 coalesce_messages。
        规范建议 features 消息使用 id=1 作为首个命令。
        """
        if not self._enable_coalesce:
            return
        # 将下一个 id 固定为 1
        self._next_id = 1
        payload = {"id": 1, "type": "supported_features", "features": {"coalesce_messages": 1}}
        await self._send_raw(payload, with_id=False)
        # 不会返回 result，仅改变后续推送行为
        # 确保后续 id 从 2 开始
        self._next_id = 2

    # ---------- 内部：发送/接收与结果处理 ----------
    async def _send(self, payload: JSONDict) -> int:
        """
        分配 id 并发送；返回分配的 id。
        """
        async with self._lock:
            req_id = self._next_id
            self._next_id += 1
        payload_copy = dict(payload)  # 复制
        payload_copy["id"] = req_id
        await self._send_raw(payload_copy)
        return req_id

    async def _send_raw(self, payload: JSONDict, *, with_id: bool = True) -> None:
        """
        发送 JSON，不做 id 分配（用于 auth、features 或需自带 id 的场景）。
        """
        if not self.connected:
            raise HAConnectionClosed("WebSocket not connected")
        assert self._ws is not None # self.connected ensures this
        data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        await self._ws.send(data)

    async def _send_and_confirm(self, payload: JSONDict, *, bind_id: bool = True) -> int:
        """
        发送命令并等待 type=result, success=true 的确认，用于订阅/取消订阅等。
        返回该命令分配的 id（订阅 id）。
        """
        if bind_id:
            req_id = await self._send(payload)
        else:
            # 不希望与订阅 id 绑定时，正常分配 id 并等待结果
            req_id = await self._send(payload)
        result = await self._await_result(req_id)
        if not result.get("success", False):
            err = result.get("error") or {}
            raise HARequestError(f"Request failed: {err}")
        return req_id

    async def _send_and_get_result(self, payload: JSONDict) -> JSONDict:
        """
        发送命令并返回 result 字段（success=true），否则抛错。
        """
        req_id = await self._send(payload)
        result = await self._await_result(req_id)
        if not result.get("success", False):
            err = result.get("error") or {}
            raise HARequestError(f"Request failed: {err}")
        return result.get("result", {})

    async def _await_result(self, req_id: int) -> JSONDict:
        """
        等待一条 type=result 的响应。
        """
        fut: asyncio.Future[JSONDict] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        try:
            return await asyncio.wait_for(fut, timeout=self._request_timeout)
        finally:
            self._pending.pop(req_id, None)

    async def _await_special(self, req_id: int, *, expected_type: str) -> None:
        """
        等待一条非 result 的特定类型响应（例如 pong）。
        """
        fut: asyncio.Future[JSONDict] = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        try:
            await asyncio.wait_for(fut, timeout=self._request_timeout)
        finally:
            self._pending.pop(req_id, None)

    async def _recv_json(self) -> JSONDict:
        assert self._ws is not None
        msg = await self._ws.recv()
        if isinstance(msg, (bytes, bytearray)):
            msg = msg.decode("utf-8", errors="replace")
        try:
            data = json.loads(msg)
            return data
        except json.JSONDecodeError:
            # 服务器可能在 coalesce 模式下返回批量数组；也可能是非法数据
            # 此处让上层处理
            return {"raw": msg}  # 返回包含原始消息的字典

    # ---------- 后台循环 ----------
    async def _reader_loop(self) -> None:
        """
        读取并分发所有来自服务器的消息：
        - result: 唤醒等待该 id 的 pending future
        - event: 回调订阅处理
        - pong: 唤醒等待 ping 的 future
        - 批量消息（list）或 coalesced：逐条分发
        """
        try:
            while not self._close_event.is_set():
                data = await self._recv_json()

                # 批量消息（coalesce 或服务器批量推送）
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            await self._dispatch_message(item)
                    continue

                await self._dispatch_message(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Reader loop error: %s", e)
        finally:
            await self._handle_disconnect()

    async def _dispatch_message(self, msg: JSONDict) -> None:
        if not isinstance(msg, dict):
            logger.debug("Skip non-dict message: %r", msg)
            return

        msg_type = msg.get("type")
        msg_id = msg.get("id")

        if msg_type == "result":
            if isinstance(msg_id, int):
                fut = self._pending.get(msg_id)
                if fut and not fut.done():
                    fut.set_result(msg)
            return

        if msg_type == "event":
            # 将事件交给对应订阅回调（基于订阅时的 id）
            if isinstance(msg_id, int):
                cb = self._subscriptions.get(msg_id)
                if cb:
                    try:
                        await cb(msg.get("event") or msg)
                    except Exception as e:
                        logger.exception("Event callback error: %s", e)
            return

        if msg_type == "pong":
            if isinstance(msg_id, int):
                fut = self._pending.get(msg_id)
                if fut and not fut.done():
                    fut.set_result(msg)
            return

        if msg_type in ("auth_required", "auth_ok", "auth_invalid"):
            # 已在握手阶段处理；这里忽略
            return

        # 其他类型（未来扩展）
        logger.debug("Unhandled message: %s", msg)

    async def _pinger_loop(self) -> None:
        try:
            while not self._close_event.is_set():
                await asyncio.sleep(self._ping_interval)
                try:
                    await self.ping()
                except Exception as e:
                    logger.info("Ping failed: %s -> triggering reconnect", e)
                    # 触发重连
                    await self._handle_disconnect()
                    return
        except asyncio.CancelledError:
            pass

    async def _handle_disconnect(self) -> None:
        """
        清理并根据配置尝试重连。
        """
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None

        # 拒绝所有 pending
        for fut in list(self._pending.values()):
            if not fut.done():
                fut.set_exception(HAConnectionClosed("Connection lost"))
        self._pending.clear()

        if self._auto_reconnect and not self._close_event.is_set():
            logger.info("Attempting to reconnect...")
            await self._do_connect(first_connect=False)

    # ---------- 重连恢复 ----------
    async def _restore_subscriptions(self) -> None:
        """
        根据 _resubscribe_cache 重建订阅，并将新订阅 id 重新绑定到旧的回调。
        """
        if not self._resubscribe_cache:
            return

        # 旧 id -> 回调
        old_callbacks = self._subscriptions.copy()
        self._subscriptions.clear()

        new_cache: list[JSONDict] = []
        for entry in old_callbacks.items():
            pass  # 只为类型提示静默

        # 我们需要知道每条缓存记录对应的回调。将 _resubscribe_cache 与旧回调表按顺序配对。
        # 这是可行的：我们在订阅时 append 缓存，顺序与 _subscriptions 的插入顺序一致。
        old_sub_items = list(old_callbacks.items())  # [(old_id, cb), ...]，插入顺序保持
        cb_iter = (cb for _, cb in old_sub_items)

        for restore in self._resubscribe_cache:
            op = restore.get("op")
            args = restore.get("args", {})
            cb = next(cb_iter, None)
            if cb is None:
                continue

            try:
                if op == "subscribe_events":
                    event_type = args.get("event_type")
                    new_id = await self.subscribe_events(cb, event_type=event_type)
                elif op == "subscribe_trigger":
                    trigger = args.get("trigger")
                    new_id = await self.subscribe_trigger(cb, trigger=trigger)
                elif op == "subscribe_config_entries":
                    type_filter = args.get("type_filter")
                    new_id = await self.subscribe_config_entries(cb, type_filter=type_filter)
                else:
                    logger.warning("Unknown restore op: %s", op)
                    continue
                # 将这条恢复过的记录保存回缓存（使用新的参数保持一致）
                new_cache.append(restore)
                logger.info("Resubscribed %s -> new id %s", op, new_id)
            except Exception as e:
                logger.warning("Failed to resubscribe %s: %s", op, e)

        self._resubscribe_cache = new_cache

    @staticmethod
    def _match_sub_restore(entry: JSONDict, subscription_id: int) -> bool:
        # 无法直接从 entry 得到旧 id；本方法仅用于从缓存中移除（保守返回 False）
        return False

# ================= 使用示例 =================
# 注意：以下示例需在异步环境中执行，例如：asyncio.run(main())
async def main():
    import os
    logging.basicConfig(level=logging.INFO)

    async def on_state_changed(event: JSONDict):
        # 仅示例：打印 entity_id
        data = event.get("data", {})
        eid = data.get("entity_id")
        print("[state_changed]", eid, data)

    token = os.getenv("HA_TOKEN")
    if not token:
        print("Error: HA_TOKEN environment variable not set.")
        return

    # 示例：本地默认端口 wss
    async with HAWebSocketClient(
        "ws://192.168.66.28:8123",
        token,
        enable_coalesce_messages=False,
        auto_reconnect=False,
    ) as cli:
        # 订阅状态变化
        sub_id = await cli.subscribe_events(on_state_changed, event_type="state_changed")
        print("Subscribed with id:", sub_id)

        # 获取所有状态
        states = await cli.get_states()
        print("States count:", len(states))

        servers = await cli.get_services()
        print("Services count:", len(servers))
        with open("servers.json", "w") as f:
            json.dump(servers, f, indent=4, ensure_ascii=False)

        # 调用服务（打开厨房灯）
        print('light turn_on')
        await cli.call_service(
            domain="light",
            service="turn_on",
            target={"entity_id": "light.philips_cn_409518076_cbulb_s_2_light"},
            service_data={"brightness_pct": 60},
        )
        await asyncio.sleep(1)
        print('light turn_off')
        await cli.call_service(
            domain="light",
            service="turn_off",
            target={"entity_id": "light.philips_cn_409518076_cbulb_s_2_light"},
        )
        await asyncio.sleep(1)
        print('admin_change_password')
        await cli.admin_change_password(password="admin123456")
        await asyncio.sleep(1)
        async def on_config_changed(event: JSONDict):
            print("[config_changed]", event)
        id = await cli.subscribe_config_entries(on_config_changed, type_filter=["device","hub","service","hardware"])
        print("Subscribed with id:", id)

        # 心跳检查
        await cli.ping()
        print("Ping successful.")

        # 运行一会接收事件
        print("Waiting for events...")
        await asyncio.sleep(10)

        # 取消订阅
        await cli.unsubscribe_events(sub_id)
        print(f"Unsubscribed from id: {sub_id}")

# 若需要直接运行示例：
if __name__ == "__main__":
    # In a real application, handle potential connection errors gracefully.
    try:
        asyncio.run(main())
    except HAWebSocketError as e:
        logger.error("A WebSocket error occurred: %s", e)
    except websockets.exceptions.InvalidURI:
        logger.error("Invalid WebSocket URI. Ensure it starts with ws:// or wss://")
    except Exception as e:
        logger.error("An unexpected error occurred: %s", e)