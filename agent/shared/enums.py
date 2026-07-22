"""SoulChord 枚举定义。

与 dev/agent-design/state_schema.md v0.1.3 对齐。
"""

from enum import Enum


class TriggerType(str, Enum):
    """★ v0.1.2 P1-6：8 个枚举，user_text + voice_text 合并为 conversation。"""
    SYSTEM_INIT = "system_init"
    CONVERSATION = "conversation"
    PLAYER_EVENT = "player_event"
    TIMER_EVENT = "timer_event"
    REPLAN_EVENT = "replan_event"
    SYSTEM = "system"
    USER_CONTROL = "user_control"
    DJ_MONOLOGUE = "dj_monologue"


class EventPriority(int, Enum):
    """★ v0.6 B 项：P0/P1/P3 显式编号（P2 留扩展）。"""
    USER = 0       # P0 — 用户交互（最高优先）
    SYSTEM = 1     # P1 — 系统事件
    TIMER = 3      # P3 — 定时事件（最低）


class EventType(str, Enum):
    """事件类型。"""
    # 用户触发
    CHAT_SEND = "chat_send"
    VOICE_TEXT = "voice_text"
    USER_CONTROL = "user_control"

    # 系统事件
    AGENT_INIT = "agent_init"
    REPLAN_REQUEST = "replan_request"
    SYSTEM = "system"

    # 播放器事件（由 ws/handler 推入）
    PLAYER_SONG_STARTED = "player_song_started"
    PLAYER_SONG_PROGRESS = "player_song_progress"
    PLAYER_SONG_FINISHED = "player_song_finished"
    PLAYER_USER_SKIP = "player_user_skip"
    PLAYER_USER_LIKE = "player_user_like"
    PLAYER_USER_DISLIKE = "player_user_dislike"
    PLAYER_PLAY_END = "player_play_end"

    # DJ 话术
    DJ_MONOLOGUE = "dj_monologue"

    # 定时事件
    TIMER_FEISHU = "timer_feishu"
    TIMER_HEARTBEAT = "timer_heartbeat"
    TIMER_PLAYLIST_HEALTH = "timer_playlist_health"
    TIMER_PROGRAM_TICK = "timer_program_tick"


class InitMode(str, Enum):
    """★ v0.6 J 项：启动重建 3 情况。"""
    FIRST_INIT = "first_init"
    NEW_DAY_INIT = "new_day_init"
    RESUME = "resume"


class ProgramSegment(str, Enum):
    """节目时间段。"""
    INTRO = "intro"
    MUSIC = "music"
    TRANSITION = "transition"
    TALK = "talk"


class ProgramMood(str, Enum):
    """★ v0.6 C 项：DJ 节目风格（原 current_mood → program_mood）。
    ★ v0.1.2 P1-5：transition speech 3 档模板。"""
    ENERGETIC = "energetic"
    WARM = "warm"
    REFLECTIVE = "reflective"
    NEUTRAL = "neutral"


class InteractionLevel(str, Enum):
    """交互强度。"""
    SILENT = "silent"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlayerEventSubtype(str, Enum):
    """★ v0.6：player_event 细化 7 类 subtype。"""
    SONG_STARTED = "song_started"
    SONG_PROGRESS = "song_progress"
    SONG_FINISHED = "song_finished"
    USER_SKIP = "user_skip"
    USER_LIKE = "user_like"
    USER_DISLIKE = "user_dislike"
    PLAY_END = "play_end"


class WsMessageType(str, Enum):
    """前端↔Agent WS 6 type。"""
    CHAT = "chat"
    MUSIC = "music"
    STATUS = "status"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    DJ = "dj"
