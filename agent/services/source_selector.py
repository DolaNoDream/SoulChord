"""SourceSelector — 播放源选择器。

只决策：从 Song.sources[] 中按 provider_priority 排序，返回有序 SongSource 列表。
不执行：不调 API，不获取 URL。

P3 无状态：每次 rank() 独立计算优先级，不修改实例状态。
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from agent.services.providers.base import SongSource
from agent.services.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)

# 默认优先级（无登录状态时使用）
PROVIDER_PRIORITY_DEFAULT = ["netease", "qqmusic"]


@dataclass
class ProviderSelectionContext:
    """播放源选择上下文。

    P3 含 accounts（登录状态），预留 network/quality 扩展。
    P4+: network: str | None = None
    P4+: preferred_quality: str | None = None
    """

    accounts: Optional[dict] = None  # {provider_name: ProviderAccount}


class SourceSelector:
    """播放源选择器。

    职责：
      - 接收 Song dict（含 sources[]）
      - 按 provider_priority + play_available 排序
      - 返回有序 SongSource 列表

    P3 无状态：_resolve_priority() 每次返回新列表，rank() 不修改实例状态。
    连续两次 rank() 结果独立，互不影响。
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        provider_priority: list[str] | None = None,
    ):
        self._registry = registry
        self._default_priority = provider_priority or PROVIDER_PRIORITY_DEFAULT

    def _resolve_priority(self, accounts: dict | None = None) -> list[str]:
        """根据登录状态决定优先级顺序。每次返回新列表，无副作用。

        Args:
            accounts: ProviderAccount dict（由 ProviderAccountService 刷新）。

        Returns:
            新的优先级列表。QQ 登录后 qqmusic 排 netease 前。
        """
        if not accounts:
            return list(self._default_priority)

        qq = accounts.get("qqmusic")
        if qq and getattr(qq, "login_status", False):
            return ["qqmusic", "netease"]

        return list(self._default_priority)

    def rank(self, song: dict, context: ProviderSelectionContext | None = None) -> list[SongSource]:
        """按 priority 排序所有 play_available 的 source。

        无状态：每次调用独立计算优先级，不修改 self._default_priority。

        Args:
            song: Song dict，须含 sources[] 字段。
            context: ProviderSelectionContext（含 accounts 等选择上下文）。

        Returns:
            按优先级排序的 SongSource 列表（不含 play_available=False）。
            无可用 source 时返回空列表。
        """
        raw_sources = song.get("sources", [])
        if not raw_sources:
            return []

        # 转为 SongSource 并过滤不可用
        sources: list[SongSource] = []
        for s in raw_sources:
            source = SongSource.from_dict(s) if isinstance(s, dict) else s
            if not source.play_available:
                continue
            sources.append(source)

        if not sources:
            return []

        # 每次独立计算优先级
        accounts = context.accounts if context else None
        priority = self._resolve_priority(accounts)

        # 按 priority 排序
        def _sort_key(source: SongSource) -> int:
            try:
                return priority.index(source.provider)
            except ValueError:
                return len(priority)  # 不在优先级列表中的排最后

        sources.sort(key=_sort_key)
        return sources
