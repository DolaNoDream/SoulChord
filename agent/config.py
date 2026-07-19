"""SoulChord Agent Runtime 配置。

所有配置项从环境变量读取，提供默认值。
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SchedulerConfig:
    feishu_interval_s: int = 300        # 飞书日程轮询间隔（5 分钟）
    heartbeat_interval_s: int = 30      # 心跳检测间隔
    playlist_health_interval_s: int = 600  # 歌单健康检查（10 分钟）
    program_tick_interval_s: int = 1800  # 节目时段切换（30 分钟）


@dataclass
class Settings:
    # --- 网络 ---
    AGENT_HOST: str = "127.0.0.1"
    AGENT_PORT: int = 8000
    MUSIC_API_BASE_URL: str = "http://localhost:8081/api/v1"

    # --- LLM ---
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT_S: int = 30

    # --- 数据文件路径 ---
    DATA_DIR: str = field(default_factory=lambda: os.environ.get("DATA_DIR", "data"))
    MEMORY_FILE: str = ""
    PROGRAM_STATE_FILE: str = ""
    SETTINGS_FILE: str = ""
    PLAYLISTS_FILE: str = ""
    PLAYER_HISTORY_FILE: str = ""
    PLAYER_MIRROR_FILE: str = ""

    # --- 日志 ---
    LOG_LEVEL: str = "INFO"

    # --- 调度器 ---
    scheduler_config: SchedulerConfig = field(default_factory=SchedulerConfig)

    def __post_init__(self):
        """初始化依赖路径。"""
        base = self.DATA_DIR
        self.MEMORY_FILE = self.MEMORY_FILE or os.path.join(base, "memory.json")
        self.PROGRAM_STATE_FILE = self.PROGRAM_STATE_FILE or os.path.join(base, "program_state.json")
        self.SETTINGS_FILE = self.SETTINGS_FILE or os.path.join(base, "settings.json")
        self.PLAYLISTS_FILE = self.PLAYLISTS_FILE or os.path.join(base, "playlists.json")
        self.PLAYER_HISTORY_FILE = self.PLAYER_HISTORY_FILE or os.path.join(base, "player_history.json")
        self.PLAYER_MIRROR_FILE = self.PLAYER_MIRROR_FILE or os.path.join(base, "player_mirror.json")


def _load_dotenv():
    """手动解析 .env 文件（不依赖 python-dotenv）。"""
    import os as _os
    env_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), ".env")
    if not _os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _key, _, _val = _line.partition("=")
            _key, _val = _key.strip(), _val.strip().strip("\"'")
            if _key and _key not in _os.environ:
                _os.environ[_key] = _val


def load_settings() -> Settings:
    """从环境变量加载设置（自动读取 .env 文件）。"""
    _load_dotenv()
    return Settings(
        AGENT_HOST=os.environ.get("AGENT_HOST", "127.0.0.1"),
        AGENT_PORT=int(os.environ.get("AGENT_PORT", "8000")),
        MUSIC_API_BASE_URL=os.environ.get("MUSIC_API_BASE_URL", "http://localhost:8081/api/v1"),
        DEEPSEEK_API_KEY=os.environ.get("DEEPSEEK_API_KEY", ""),
        DEEPSEEK_BASE_URL=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        LLM_MODEL=os.environ.get("LLM_MODEL", "deepseek-chat"),
        DATA_DIR=os.environ.get("DATA_DIR", "data"),
        LOG_LEVEL=os.environ.get("LOG_LEVEL", "INFO"),
    )


settings = load_settings()
