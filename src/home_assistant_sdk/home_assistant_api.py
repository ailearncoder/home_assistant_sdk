import requests
import json
import jwt
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin
from .logger import get_logger

# 创建模块logger
logger = get_logger(__name__)


class HomeAssistantIntegrationFlow:
    """Home Assistant 集成配置流程的通用HTTP API封装类"""

    def __init__(self, base_url: str, token: str, verify_ssl: bool = True):
        """
        初始化集成流程客户端

        参数:
            base_url (str): Home Assistant实例的基础URL (例如: 'http://192.168.66.28:8123')
            token (str): 长期访问令牌
            verify_ssl (bool): 是否验证SSL证书
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

    def start_flow(self, handler: str, show_advanced_options: bool = False) -> Dict[str, Any]:
        """启动集成配置流程

        参数:
            handler (str): 集成处理器名称 (例如: 'xiaomi_home', 'mcp_server')
            show_advanced_options (bool): 是否显示高级选项

        返回:
            Dict[str, Any]: 包含 flow_id 等信息的响应数据
        """
        url = urljoin(self.base_url, '/api/config/config_entries/flow')
        payload = {"handler": handler, "show_advanced_options": show_advanced_options}

        response = self.session.post(url, data=json.dumps(payload), verify=self.verify_ssl)
        response.raise_for_status()

        return response.json()

    def submit_flow_step(self, flow_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """提交流程步骤数据

        参数:
            flow_id (str): 流程ID
            data (Dict[str, Any]): 要提交的数据

        返回:
            Dict[str, Any]: 响应数据
        """
        url = urljoin(self.base_url, f'/api/config/config_entries/flow/{flow_id}')

        response = self.session.post(url, data=json.dumps(data), verify=self.verify_ssl)
        response.raise_for_status()

        return response.json()

    def get_flow_info(self, flow_id: str) -> Dict[str, Any]:
        """获取流程信息

        参数:
            flow_id (str): 流程ID

        返回:
            Dict[str, Any]: 流程信息
        """
        url = urljoin(self.base_url, f'/api/config/config_entries/flow/{flow_id}')

        response = self.session.get(url, verify=self.verify_ssl)
        response.raise_for_status()

        return response.json()


class HomeAssistantAuth:
    """
    Home Assistant 认证管理类，支持智能 Token 缓存与自动刷新。

    功能特性:
        - 自动管理 access_token 和 refresh_token 的有效性
        - 支持本地 JSON 文件缓存 Token
        - 使用 JWT 验证 Token 是否过期
        - 自动选择最优认证方式（缓存 Token > refresh_token > 用户名密码登录）

    用法:
        # 基础用法（无缓存）
        auth = HomeAssistantAuth(
            url="http://192.168.66.28:8123",
            username="admin",
            password="admin123"
        )

        # 使用缓存目录
        auth = HomeAssistantAuth(
            url="http://192.168.66.28:8123",
            username="admin",
            password="admin123",
            token_cache_dir="./cache"  # 可选：指定缓存目录
        )

        try:
            token_info = auth.get_token()
            access_token = token_info.get("access_token")
            print(f"成功获取 Access Token: {access_token}")
        except Exception as e:
            print(f"获取 Token 失败: {e}")
    """

    def __init__(self, url: str, username: str, password: str, token_cache_dir: Optional[str] = None):
        """
        初始化 HomeAssistantAuth 类。

        参数:
            url (str): Home Assistant 实例的基础 URL (例如: http://192.168.66.28:8123)
            username (str): Home Assistant 用户名
            password (str): Home Assistant 密码
            token_cache_dir (Optional[str]): Token 缓存目录路径，如果为 None 则不使用缓存
        """
        if url.endswith('/'):
            url = url[:-1]  # 移除末尾的斜杠，以确保 URL 拼接正确
        self.base_url = url
        self.username = username
        self.password = password

        # 配置缓存路径
        self.token_cache_path = None
        if token_cache_dir:
            cache_dir = Path(token_cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            self.token_cache_path = cache_dir / "token_info.json"

        # 内存中的 Token 信息
        self._cached_token_info: Optional[Dict[str, Any]] = None

        # 初始化 HTTP Session
        self.session = requests.Session()
        # 设置通用的请求头
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Connection': 'keep-alive',
            'Origin': self.base_url
        })

    def get_token(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        智能获取有效的 access_token，自动处理缓存、刷新和重新登录逻辑。

        执行策略（按优先级）:
            1. 如果内存中有有效的 access_token，直接返回
            2. 如果缓存文件中有有效的 access_token，加载并返回
            3. 如果 refresh_token 未过期，使用它刷新获取新 token
            4. 如果以上都失败，使用用户名密码重新登录

        参数:
            force_refresh (bool): 是否强制刷新 Token（忽略缓存，但会尝试使用 refresh_token）

        返回:
            Dict[str, Any]: 包含 access_token, refresh_token, token_type, expires_in 等信息的字典

        抛出:
            Exception: 如果所有认证方式都失败
        """
        # 策略1: 检查内存中的 access_token 是否有效
        if not force_refresh and self._cached_token_info:
            if self._is_access_token_valid(self._cached_token_info.get("access_token")):
                logger.info("✓ 使用内存中的有效 access_token")
                return self._cached_token_info

        # 策略2: 检查缓存文件中的 access_token 是否有效
        if not force_refresh and self.token_cache_path and self.token_cache_path.exists():
            cached_token = self._load_token_from_cache()
            if cached_token and self._is_access_token_valid(cached_token.get("access_token")):
                logger.info("✓ 从缓存文件加载有效的 access_token")
                self._cached_token_info = cached_token
                return cached_token

        # 策略3: 尝试使用 refresh_token 刷新
        refresh_token = None
        if self._cached_token_info:
            refresh_token = self._cached_token_info.get("refresh_token")
        elif self.token_cache_path and self.token_cache_path.exists():
            cached_token = self._load_token_from_cache()
            if cached_token:
                refresh_token = cached_token.get("refresh_token")

        if refresh_token and self._is_refresh_token_valid(refresh_token):
            try:
                logger.info("⟳ 使用 refresh_token 刷新 access_token")
                client_id = f"{self.base_url}/"
                token_info = self._refresh_access_token(client_id, refresh_token)
                cached_token = self._load_token_from_cache()
                if cached_token:
                    cached_token.update(token_info)
                else:
                    cached_token = token_info
                self._save_token(cached_token)
                return token_info
            except Exception as e:
                logger.warning(f"⚠ refresh_token 刷新失败: {e}，尝试重新登录")
        else:
            logger.info(f"⟳ refresh_token 无效:{refresh_token}")

        # 策略4: 使用用户名密码重新登录
        logger.info("⟳ 使用用户名密码重新登录")
        token_info = self._login_with_credentials()
        self._save_token(token_info)
        return token_info

    def revoke_token(self, token: str) -> bool:
        """
        撤销指定的令牌

        参数:
            token (str): 要撤销的令牌

        返回:
            bool: 撤销成功返回True，否则抛出异常
        """
        url = urljoin(self.base_url, '/auth/revoke')

        # 移除 Content-Type，让 requests 自动处理 multipart/form-data
        if 'Content-Type' in self.session.headers:
            del self.session.headers['Content-Type']

        # 准备表单数据
        payload = {'token': token}

        response = self.session.post(url, data=payload)
        response.raise_for_status()

        # 成功撤销返回200状态码，且响应体为空
        return response.status_code == 200

    # ========== Token 验证相关方法 ==========

    def _is_access_token_valid(self, access_token: Optional[str]) -> bool:
        """
        验证 access_token 是否有效（未过期）。

        参数:
            access_token (Optional[str]): 待验证的 access_token

        返回:
            bool: Token 有效返回 True，否则返回 False
        """
        if not access_token:
            return False

        try:
            # 解码 JWT（不验证签名，仅检查过期时间）
            decoded = jwt.decode(
                access_token,
                options={"verify_signature": False, "verify_exp": True}
            )
            # JWT 库会在 Token 过期时抛出 ExpiredSignatureError
            return True
        except jwt.ExpiredSignatureError:
            logger.debug("  ✗ access_token 已过期")
            return False
        except jwt.InvalidTokenError as e:
            logger.debug(f"  ✗ access_token 无效: {e}")
            return False

    def _is_refresh_token_valid(self, refresh_token: Optional[str]) -> bool:
        """
        验证 refresh_token 是否有效。

        注意: refresh_token 通常不是 JWT 格式，无法通过解码验证。
        Home Assistant 的 refresh_token 有效期默认为 6 个月，这里只做简单的非空检查。
        实际有效性需要在刷新时由服务器验证。

        参数:
            refresh_token (Optional[str]): 待验证的 refresh_token

        返回:
            bool: Token 非空返回 True，否则返回 False
        """
        return bool(refresh_token)

    # ========== Token 缓存相关方法 ==========

    def _load_token_from_cache(self) -> Optional[Dict[str, Any]]:
        """
        从缓存文件加载 Token 信息。

        返回:
            Optional[Dict[str, Any]]: Token 信息字典，加载失败返回 None
        """
        try:
            if self.token_cache_path and self.token_cache_path.exists():
                with open(self.token_cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠ 加载缓存文件失败: {e}")
        return None

    def _save_token(self, token_info: Dict[str, Any]) -> None:
        """
        保存 Token 信息到内存和缓存文件。

        参数:
            token_info (Dict[str, Any]): Token 信息字典
        """
        # 保存到内存
        self._cached_token_info = token_info

        # 保存到文件
        if self.token_cache_path:
            try:
                with open(self.token_cache_path, 'w', encoding='utf-8') as f:
                    json.dump(token_info, f, indent=4, ensure_ascii=False)
                logger.info(f"✓ Token 已保存到: {self.token_cache_path}")
            except Exception as e:
                logger.warning(f"⚠ 保存 Token 到缓存文件失败: {e}")

    # ========== 认证流程相关方法 ==========

    def _login_with_credentials(self) -> Dict[str, Any]:
        """
        使用用户名密码执行完整的登录流程。

        返回:
            Dict[str, Any]: 包含 access_token, refresh_token 等信息的字典

        抛出:
            Exception: 如果任何步骤失败
        """
        client_id = f"{self.base_url}/"
        redirect_uri = f"{self.base_url}/?auth_callback=1"

        # 步骤 1: 发起登录流程，获取 flow_id
        flow_id = self._initiate_login_flow(client_id, redirect_uri)
        logger.info(f"  步骤 1/3: 成功获取 flow_id -> {flow_id}")

        # 步骤 2: 提交用户名和密码，获取授权码 (code)
        auth_code = self._submit_credentials(flow_id, client_id)
        logger.info(f"  步骤 2/3: 成功获取授权码 -> {auth_code[:20]}...")

        # 步骤 3: 使用授权码获取 access_token
        token_info = self._exchange_code_for_token(auth_code, client_id)
        logger.info("  步骤 3/3: 成功获取 Token！")

        return token_info

    def _refresh_access_token(self, client_id: str, refresh_token: str) -> Dict[str, Any]:
        """
        使用 refresh_token 刷新获取新的 access_token。

        参数:
            client_id (str): 客户端 ID
            refresh_token (str): 刷新令牌

        返回:
            Dict[str, Any]: 新的 Token 信息

        抛出:
            Exception: 如果刷新失败
        """
        url = f"{self.base_url}/auth/token"
        payload = {
            'client_id': client_id,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }

        # 移除 Content-Type，让 requests 自动处理 multipart/form-data
        if 'Content-Type' in self.session.headers:
            del self.session.headers['Content-Type']

        response = self.session.post(url, data=payload)
        response.raise_for_status()

        token_data = response.json()
        if "access_token" not in token_data:
            raise Exception(f"未能从响应中获取 access_token: {token_data}")

        return token_data


    def _initiate_login_flow(self, client_id, redirect_uri):
        """第一步：发起登录流程"""
        url = f"{self.base_url}/auth/login_flow"
        payload = {
            "client_id": client_id,
            "handler": ["homeassistant", None],
            "redirect_uri": redirect_uri
        }
        self.session.headers['Content-Type'] = 'text/plain;charset=UTF-8'

        response = self.session.post(url, data=json.dumps(payload))
        response.raise_for_status()  # 如果状态码不是 2xx，则抛出异常

        data = response.json()
        if "flow_id" not in data:
            raise Exception(f"未能从响应中获取 flow_id: {data}")
        return data["flow_id"]

    def _submit_credentials(self, flow_id, client_id):
        """第二步：提交凭据"""
        url = f"{self.base_url}/auth/login_flow/{flow_id}"
        payload = {
            "username": self.username,
            "password": self.password,
            "client_id": client_id
        }
        self.session.headers['Content-Type'] = 'text/plain;charset=UTF-8'

        response = self.session.post(url, data=json.dumps(payload))
        response.raise_for_status()

        data = response.json()
        if data.get("type") != "create_entry" or "result" not in data:
            raise Exception(f"凭据提交失败或响应格式不正确: {data}")
        return data["result"]

    def _exchange_code_for_token(self, code, client_id):
        """第三步：交换授权码以获取 Token"""
        url = f"{self.base_url}/auth/token"
        payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': client_id,
        }
        # 对于 multipart/form-data，requests 会自动设置 Content-Type
        # 无需手动设置 boundary

        # 移除之前设置的 Content-Type，让 requests 自动处理
        if 'Content-Type' in self.session.headers:
            del self.session.headers['Content-Type']

        response = self.session.post(url, data=payload)
        response.raise_for_status()

        token_data = response.json()
        if "access_token" not in token_data:
            raise Exception(f"未能从最终响应中获取 access_token: {token_data}")
        return token_data

# --- 使用示例 ---
if __name__ == '__main__':
    # 请将以下参数替换为您的 Home Assistant 实例信息
    HA_URL = "http://192.168.66.28:8123"
    HA_USERNAME = "admin"
    HA_PASSWORD = "admin123"

    # 创建认证类的实例（带缓存目录）
    ha_auth = HomeAssistantAuth(
        url=HA_URL,
        username=HA_USERNAME,
        password=HA_PASSWORD,
        token_cache_dir="./cache"  # 指定缓存目录
    )

    try:
        # 获取 Token（首次会登录，后续会自动使用缓存或刷新）
        token_information = ha_auth.get_token()

        # 打印获取到的完整 Token 信息
        print("\n--- 获取到的 Token 信息 ---")
        print(json.dumps(token_information, indent=2, ensure_ascii=False))

        # 单独提取 access_token
        access_token = token_information.get("access_token", "")
        print(f"\nAccess Token: {access_token[:50] if access_token else 'N/A'}...")  # 只显示前50个字符

        # 测试：再次调用 get_token，应该直接使用缓存
        print("\n--- 测试缓存功能 ---")
        token_information_2 = ha_auth.get_token()
        print(f"第二次调用是否返回相同的 token: {token_information == token_information_2}")

        # 测试：强制刷新
        print("\n--- 测试强制刷新 ---")
        token_information_3 = ha_auth.get_token(force_refresh=True)
        refresh_token_str = token_information_3.get('access_token', '')
        print(f"强制刷新后的 Access Token: {refresh_token_str[:50] if refresh_token_str else 'N/A'}...")

    except requests.exceptions.RequestException as e:
        print(f"\n--- 请求失败 ---")
        print(f"错误详情: {e}")
    except Exception as e:
        print(f"\n--- 发生错误 ---")
        print(f"错误详情: {e}")
