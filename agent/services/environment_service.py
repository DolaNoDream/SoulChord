"""EnvironmentService — 环境信息（天气/时间/位置/活动）。

MVP 返回 mock 数据，P1 接真实 API。
"""

import logging
import datetime

logger = logging.getLogger(__name__)


class EnvironmentService:
    """环境上下文服务。"""

    async def get_current_weather(self) -> dict:
        """获取当前天气（MVP mock）。"""
        return {
            "temperature": 22,
            "condition": "clear",
            "humidity": 60,
            "description": "晴朗",
        }

    async def get_current_time(self) -> dict:
        """获取当前时间。"""
        now = datetime.datetime.now()
        return {
            "hour": now.hour,
            "minute": now.minute,
            "day_period": self._compute_day_period(now.hour),
            "weekday": now.weekday(),
            "iso": now.isoformat(),
        }

    async def get_current_location(self) -> dict:
        """获取当前位置（MVP mock）。"""
        return {
            "city": "未设置",
            "district": "",
        }

    async def get_current_activity(self) -> dict:
        """获取当前活动状态（MVP mock）。"""
        hour = datetime.datetime.now().hour
        if 6 <= hour < 9:
            return {"activity": "morning_routine", "label": "早晨"}
        elif 9 <= hour < 12:
            return {"activity": "working", "label": "工作"}
        elif 12 <= hour < 14:
            return {"activity": "lunch_break", "label": "午休"}
        elif 14 <= hour < 18:
            return {"activity": "working", "label": "工作"}
        elif 18 <= hour < 22:
            return {"activity": "leisure", "label": "休闲"}
        else:
            return {"activity": "sleeping", "label": "休息"}

    @staticmethod
    def _compute_day_period(hour: int) -> str:
        if 5 <= hour < 9:
            return "morning"
        elif 9 <= hour < 12:
            return "before_noon"
        elif 12 <= hour < 14:
            return "noon"
        elif 14 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"
