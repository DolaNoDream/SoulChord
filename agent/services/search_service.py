"""MusicSearchService — 多 Provider 并行搜索 + 故障隔离。"""

import asyncio
import logging

from typing import Optional

from agent.services.providers.base import MusicProvider, ProviderSearchResult
from agent.services.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class MusicSearchService:
    """多 Provider 并行搜索服务。

    职责：
      1. 并行向所有已注册 Provider 发起搜索
      2. 超时控制 + 异常隔离（一个 Provider 挂了不影响其他）
      3. 将各 Provider 结果统一交 SongResolver.resolve() 合并排重
    """

    def __init__(self, registry: ProviderRegistry, search_timeout: float = 10.0):
        self._registry = registry
        self._search_timeout = search_timeout

    async def search(
        self,
        query: str,
        limit: int = 10,
        provider_names: list[str] | None = None,
    ) -> dict[str, list[ProviderSearchResult]]:
        """并行搜索指定（或全部）Provider。

        Args:
            query: 搜索关键词。
            limit: 每个 Provider 返回数量。
            provider_names: 限定搜索的 Provider 列表，None 表示全部。

        Returns:
            {provider_name: [ProviderSearchResult, ...]}
            搜索失败的 Provider 不包含在返回 dict 中。
        """
        providers = self._get_providers(provider_names)
        if not providers:
            logger.warning("MusicSearchService.search: no providers available")
            return {}

        async def _search_one(name: str, query: str, limit: int) -> tuple[str, list[ProviderSearchResult]]:
            try:
                results = await asyncio.wait_for(
                    providers[name].search(query, limit),
                    timeout=self._search_timeout,
                )
                logger.debug("Provider %s returned %d results for %r", name, len(results), query)
                return name, results
            except asyncio.TimeoutError:
                logger.warning("Provider %s search timed out after %ss", name, self._search_timeout)
                return name, []
            except Exception as e:
                logger.error("Provider %s search error: %s", name, e)
                return name, []

        tasks = [_search_one(name, query, limit) for name in providers]
        gathered = await asyncio.gather(*tasks)

        return {name: results for name, results in gathered if results}

    def _get_providers(self, provider_names: list[str] | None) -> dict[str, MusicProvider]:
        """解析 Provider 列表，返回 {name: provider}。"""
        providers: dict[str, MusicProvider] = {}
        if provider_names:
            for name in provider_names:
                p = self._registry.get(name)
                if p:
                    providers[name] = p
                else:
                    logger.warning("Provider %s not found in registry", name)
        else:
            for p in self._registry.get_all():
                providers[p.name] = p
        return providers
