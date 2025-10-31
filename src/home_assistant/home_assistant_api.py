import requests
import json

class HomeAssistantAuth:
    """
    一个用于处理 Home Assistant 登录流程并获取认证 Token 的类。

    用法:
        auth = HomeAssistantAuth(url="http://192.168.66.28:8123", username="admin", password="admin123")
        try:
            token_info = auth.get_token()
            access_token = token_info.get("access_token")
            print(f"成功获取 Access Token: {access_token}")
        except Exception as e:
            print(f"获取 Token 失败: {e}")
    """
    def __init__(self, url, username, password):
        """
        初始化 HomeAssistantAuth 类。

        参数:
            url (str): Home Assistant 实例的基础 URL (例如: http://192.168.66.28:8123)。
            username (str): 您的 Home Assistant 用户名。
            password (str): 您的 Home Assistant 密码。
        """
        if url.endswith('/'):
            url = url[:-1]  # 移除末尾的斜杠，以确保 URL 拼接正确
        self.base_url = url
        self.username = username
        self.password = password
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

    def get_token(self):
        """
        执行完整的认证流程以获取 access token。

        返回:
            dict: 包含 access_token, refresh_token, token_type 等信息的字典。

        抛出:
            Exception: 如果任何步骤失败。
        """
        client_id = f"{self.base_url}/"
        redirect_uri = f"{self.base_url}/?auth_callback=1"

        # 步骤 1: 发起登录流程，获取 flow_id
        flow_id = self._initiate_login_flow(client_id, redirect_uri)
        print(f"步骤 1/3: 成功获取 flow_id -> {flow_id}")

        # 步骤 2: 提交用户名和密码，获取授权码 (code)
        auth_code = self._submit_credentials(flow_id, client_id)
        print(f"步骤 2/3: 成功获取授权码 -> {auth_code}")

        # 步骤 3: 使用授权码获取 access_token
        token_info = self._exchange_code_for_token(auth_code, client_id)
        print("步骤 3/3: 成功获取 Token！")
        
        return token_info

    def refresh_token(self, client_id: str, refresh_token: str):
        url = f"{self.base_url}/auth/token"
        payload = {
            'client_id': client_id,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
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

    # 创建认证类的实例
    ha_auth = HomeAssistantAuth(url=HA_URL, username=HA_USERNAME, password=HA_PASSWORD)

    try:
        # 获取 Token
        token_information = ha_auth.get_token()
        
        # 打印获取到的完整 Token 信息
        print("\n--- 获取到的 Token 信息 ---")
        print(json.dumps(token_information, indent=2))
        
        # 单独提取 access_token
        access_token = token_information.get("access_token")
        print(f"\nAccess Token: {access_token}")

        access_token = ha_auth.refresh_token(client_id="http://192.168.66.28:8123/", refresh_token="379ee0c59fdbcfba7ae01cbfe8ea611047ae5731f9621a20738089a196ae7360b5b2c29e3a7969f6d79e3ce510d1bf8780f4deafde91e730bcacb8967eea48d3")
        print(f"\nAccess Token: {access_token}")

    except requests.exceptions.RequestException as e:
        print(f"\n--- 请求失败 ---")
        print(f"错误详情: {e}")
    except Exception as e:
        print(f"\n--- 发生错误 ---")
        print(f"错误详情: {e}")
