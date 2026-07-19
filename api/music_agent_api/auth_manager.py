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

    # ──────────────── 真实用户登录 ────────────────

    def login_phone(self, phone: str, password: str) -> dict:
        """手机号+密码登录，成功后替换匿名 cookie 为真实用户 cookie"""
        try:
            payload = {
                "phone": phone, "password": password,
                "timestamp": int(time.time() * 1000),
                "realIP": "114.114.114.114",
            }
            res = requests.get(f"{NODEJS_API_BASE_URL}/login/cellphone", params=payload, timeout=10)
            data = res.json()
            if data.get("code") == 200:
                cookie_str = data.get("cookie", "")
                if cookie_str:
                    self.cookie_str = cookie_str
                    self._save_token(cookie_str)
                profile = data.get("profile", {})
                return {"success": True, "nickname": profile.get("nickname", ""), "avatar_url": profile.get("avatarUrl", "")}
            return {"success": False, "msg": data.get("msg", "登录失败")}
        except Exception as e:
            logger.error("手机号登录异常: %s", e)
            return {"success": False, "msg": str(e)}

    def login_qr_key(self) -> dict:
        """获取 QR 登录临时 key"""
        try:
            res = requests.get(f"{NODEJS_API_BASE_URL}/login/qr/key?timestamp={int(time.time() * 1000)}", timeout=10)
            data = res.json()
            if data.get("code") == 200:
                return {"success": True, "key": data.get("data", {}).get("unikey", "")}
            return {"success": False, "msg": "获取 QR key 失败"}
        except Exception as e:
            logger.error("获取 QR key 异常: %s", e)
            return {"success": False, "msg": str(e)}

    def login_qr_create(self, key: str) -> dict:
        """根据 key 生成 QR 码 base64 图片"""
        try:
            res = requests.get(
                f"{NODEJS_API_BASE_URL}/login/qr/create?key={key}&qrimg=true&timestamp={int(time.time() * 1000)}",
                timeout=10,
            )
            data = res.json()
            if data.get("code") == 200:
                raw_qr = data.get("data", {}).get("qrimg", "")
                # Node.js 返回的 qrimg 已带 data:image/png;base64, 前缀，去掉只留纯 base64
                if raw_qr.startswith("data:image"):
                    raw_qr = raw_qr.split(",", 1)[-1]
                return {"success": True, "qr_img": raw_qr}
            return {"success": False, "msg": "生成 QR 码失败"}
        except Exception as e:
            logger.error("生成 QR 码异常: %s", e)
            return {"success": False, "msg": str(e)}

    def login_qr_check(self, key: str) -> dict:
        """轮询检查 QR 码扫描状态
        800=过期, 801=等待扫码, 802=已扫码待确认, 803=授权成功
        """
        try:
            res = requests.get(
                f"{NODEJS_API_BASE_URL}/login/qr/check?key={key}&timestamp={int(time.time() * 1000)}",
                timeout=10,
            )
            data = res.json()
            code = data.get("code")
            if code == 803:
                cookie_str = data.get("cookie", "")
                if cookie_str:
                    self.cookie_str = cookie_str
                    self._save_token(cookie_str)
                return {"success": True, "status": "confirmed"}
            status_map = {800: "expired", 801: "waiting", 802: "scanning"}
            return {"success": True, "status": status_map.get(code, "unknown"), "code": code}
        except Exception as e:
            logger.error("QR 码检查异常: %s", e)
            return {"success": False, "msg": str(e)}

    def login_status(self) -> dict:
        """查询当前登录状态（真实用户信息）"""
        try:
            payload = self.get_request_params()
            res = requests.get(f"{NODEJS_API_BASE_URL}/login/status", params=payload, timeout=10)
            data = res.json()
            profile = data.get("data", {}).get("profile")
            if profile:
                return {
                    "logged_in": True,
                    "nickname": profile.get("nickname", ""),
                    "avatar_url": profile.get("avatarUrl", ""),
                    "user_id": profile.get("userId", 0),
                }
            return {"logged_in": False}
        except Exception as e:
            logger.error("查询登录状态异常: %s", e)
            return {"logged_in": False}

    def is_logged_in(self) -> bool:
        """快速判断当前 cookie 是否为真实用户（非匿名）"""
        return "MUSIC_A=" in self.cookie_str

    def logout(self):
        """登出，重置为匿名 token"""
        logger.info("登出，重置为匿名 token...")
        self._login_anonymous()

    def _save_token(self, cookie_str: str):
        """持久化 cookie 到文件"""
        try:
            with open(TOKEN_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump({"cookie": cookie_str}, f)
            logger.info("Token 已保存")
        except Exception as e:
            logger.error("保存 Token 失败: %s", e)


# 全局单例管理器
auth_manager = NeteaseAuthManager()