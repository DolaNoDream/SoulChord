import json
import os
import requests
import uuid
import logging
import time

NODEJS_API_BASE_URL = os.getenv("NETEASE_API_URL", "http://localhost:3000")
TOKEN_FILE_PATH = "netease_token.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NeteaseAuthManager:
    def __init__(self):
        self.device_id = self._get_or_create_device_id()
        self.cookie_str = ""
        self.load_or_init_anonymous_token()

    def _get_or_create_device_id(self):
        """生成或读取固定的设备 ID，用于后续所有请求"""
        device_file = "device_id.txt"
        if os.path.exists(device_file):
            with open(device_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        else:
            new_id = f"win11-dev-{str(uuid.uuid4())[:8]}"
            with open(device_file, "w", encoding="utf-8") as f:
                f.write(new_id)
            return new_id

    def load_or_init_anonymous_token(self):
        """加载本地缓存的匿名 Token，如果没有则去 Node.js 服务请求"""
        if os.path.exists(TOKEN_FILE_PATH):
            try:
                with open(TOKEN_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.cookie_str = data.get("cookie", "")
                    logger.info("成功加载本地匿名 Token 缓存")
                    return
            except Exception as e:
                logger.error(f"读取 Token 缓存失败: {e}")

        self._login_anonymous()

    def _login_anonymous(self):
        """调用 Node.js 的匿名登录接口[cite: 1]"""
        logger.info("正在执行网易云匿名登录...")
        endpoint = f"{NODEJS_API_BASE_URL}/register/anonimous?timestamp={int(time.time() * 1000)}"

        try:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("code") == 200:
                    self.cookie_str = res_data.get("cookie", "")
                    with open(TOKEN_FILE_PATH, "w", encoding="utf-8") as f:
                        json.dump({"cookie": self.cookie_str}, f)
                    logger.info("匿名登录成功，Token 已缓存。")
                else:
                    logger.error(f"匿名登录返回错误码: {res_data}")
            else:
                logger.error(f"请求 Node.js 接口失败，HTTP 状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"执行匿名登录异常: {e}")

    def get_request_params(self):
        """获取向 Node.js 侧发起其他请求时必须携带的参数"""
        return {
            "cookie": self.cookie_str,
            "realIP": "114.114.114.114"
        }


# 全局单例管理器
auth_manager = NeteaseAuthManager()