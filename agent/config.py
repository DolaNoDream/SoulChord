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
class DJHostConfig:
    """DJ Host Agent 配置。"""
    enabled: bool = True
    llm_timeout_s: int = 10        # Inline LLM 10s timeout
    cache_ttl_s: int = 300         # Cache TTL 5 min
    speech_interval_s: int = 120   # 2 min cooldown between speeches
    progress_threshold: float = 0.85  # 85% song progress triggers DJ
    persona_name: str = "Soul"
    persona_style: str = "warm"


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
    LLM_TIMEOUT_S: int = 60

    # --- 数据文件路径 ---
    DATA_DIR: str = field(default_factory=lambda: os.environ.get("DATA_DIR", "data"))
    MEMORY_FILE: str = ""
    PROGRAM_STATE_FILE: str = ""
    SETTINGS_FILE: str = ""
    PLAYLISTS_FILE: str = ""
    PLAYER_HISTORY_FILE: str = ""
    PLAYER_MIRROR_FILE: str = ""

    # --- Fish Audio TTS/ASR ---
    FISH_AUDIO_API_KEY: str = ""
    FISH_AUDIO_VOICE_ID: str = "1036a9ebfa2145aa8db0c9eb5a2b000e"
    FISH_AUDIO_BASE_URL: str = "https://api.fish.audio"  # Fish Audio API 基础 URL

    # --- 日志 ---
    LOG_LEVEL: str = "INFO"

    # --- 调度器 ---
    scheduler_config: SchedulerConfig = field(default_factory=SchedulerConfig)

    # --- DJ Host ---
    dj_host: DJHostConfig = field(default_factory=DJHostConfig)

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
    dj_host_enabled = os.environ.get("DJ_HOST_ENABLED", "true").lower() == "true"
    dj_host = DJHostConfig(
        enabled=dj_host_enabled,
        llm_timeout_s=int(os.environ.get("DJ_HOST_LLM_TIMEOUT_S", "10")),
        cache_ttl_s=int(os.environ.get("DJ_HOST_CACHE_TTL_S", "300")),
        speech_interval_s=int(os.environ.get("DJ_HOST_SPEECH_INTERVAL_S", "120")),
        progress_threshold=float(os.environ.get("DJ_HOST_PROGRESS_THRESHOLD", "0.85")),
        persona_name=os.environ.get("DJ_HOST_PERSONA_NAME", "Soul"),
        persona_style=os.environ.get("DJ_HOST_PERSONA_STYLE", "warm"),
    )

    return Settings(
        AGENT_HOST=os.environ.get("AGENT_HOST", "127.0.0.1"),
        AGENT_PORT=int(os.environ.get("AGENT_PORT", "8000")),
        MUSIC_API_BASE_URL=os.environ.get("MUSIC_API_BASE_URL", "http://localhost:8081/api/v1"),
        DEEPSEEK_API_KEY=os.environ.get("DEEPSEEK_API_KEY", ""),
        DEEPSEEK_BASE_URL=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        LLM_MODEL=os.environ.get("LLM_MODEL", "deepseek-chat"),
        DATA_DIR=os.environ.get("DATA_DIR", "data"),
        LOG_LEVEL=os.environ.get("LOG_LEVEL", "INFO"),
        FISH_AUDIO_API_KEY=os.environ.get("FISH_AUDIO_API_KEY", ""),
        FISH_AUDIO_VOICE_ID=os.environ.get("FISH_AUDIO_VOICE_ID", "1036a9ebfa2145aa8db0c9eb5a2b000e"),
        FISH_AUDIO_BASE_URL=os.environ.get("FISH_AUDIO_BASE_URL", "https://api.fish.audio"),
        dj_host=dj_host,
    )


settings = load_settings()
