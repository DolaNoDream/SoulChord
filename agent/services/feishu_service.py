"""FeishuService — 飞书日历服务骨架。

★ MVP mock 输出，不接真实飞书 API（P2 OAuth + 日程读取）
★ 1 DJ_TOOL（query_calendar）+ 2 INTERNAL（get_calendar_current / get_calendar_today）
★ 定位：Service 层，由 adapter.dispatch() 消费
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FeishuService:
    """飞书日历服务。

    当前 MVP 返回 mock 日程数据。
    P2 工作项：OAuth 桌面 loopback / 5 分钟轮询 / 真实日历读取 / 聚合标签。
    """

    async def get_calendar_current(self) -> dict:
        """获取当前正在进行中的日程。

        Returns:
            dict: {
                "has_event": bool,
                "title": str,           # 日程标题（空字符串表示无日程）
                "location": str,        # 地点
                "participants": list,   # 参与人列表
                "start_time": str,      # ISO 格式开始时间
                "end_time": str,        # ISO 格式结束时间
                "source": str,          # "feishu_mock"（MVP）
            }
        """
        # MVP mock：返回一个示例日程
        logger.info("FeishuService.get_calendar_current: returning mock")
        return {
            "has_event": True,
            "title": "团队周会",
            "location": "3楼会议室",
            "participants": ["张三", "李四"],
            "start_time": "2026-07-17T14:00:00+08:00",
            "end_time": "2026-07-17T15:00:00+08:00",
            "source": "feishu_mock",
        }

    async def get_calendar_today(self) -> dict:
        """获取今日日程摘要。

        日历数据（标题/地点/参与人）不发给 LLM 也不写 Memory（仅用聚合标签）。

        Returns:
            dict: {
                "date": str,            # 日期 YYYY-MM-DD
                "event_count": int,     # 今日日程数
                "tags": list[str],      # 聚合标签（如 ["会议", "截止日"]）
                "is_busy": bool,        # 是否忙碌
                "source": str,          # "feishu_mock"（MVP）
            }
        """
        logger.info("FeishuService.get_calendar_today: returning mock")
        return {
            "date": "2026-07-17",
            "event_count": 3,
            "tags": ["会议", "截止日"],
            "is_busy": True,
            "source": "feishu_mock",
        }


# 模块级单例
feishu_service = FeishuService()
