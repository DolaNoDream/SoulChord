"""ProviderRegistry — 注册 + 获取 + 健康检查。"""

import asyncio
import logging

from agent.services.providers.base import MusicProvider

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Provider 注册中心。

    管理所有 MusicProvider 实例的注册、获取、健康检查。
    """

    def __init__(self):
        self._providers: dict[str, MusicProvider] = {}

    def register(self, provider: MusicProvider) -> None:
        """注册一个 Provider，以 provider.name 为 key。"""
        self._providers[provider.name] = provider
        logger.info("Provider registered: %s", provider.name)

    def get(self, name: str) -> MusicProvider | None:
        """按名称获取 Provider，不存在返回 None。"""
        return self._providers.get(name)

    def get_all(self) -> list[MusicProvider]:
        """获取所有已注册 Provider。"""
        return list(self._providers.values())

    def list_names(self) -> list[str]:
        """列出所有已注册 Provider 名称。"""
        return list(self._providers.keys())

    async def health_check_all(self, timeout: float = 2.0) -> dict[str, bool]:
        """并行对所有 Provider 做健康检查。

        Args:
            timeout: 每个 Provider 的超时时间（秒）。

        Returns:
            {provider_name: is_healthy, ...}
        """
        results: dict[str, bool] = {}

        async def _check(name: str, provider: MusicProvider) -> tuple[str, bool]:
            try:
                ok = await asyncio.wait_for(provider.health_check(), timeout=timeout)
                return name, ok
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("Provider %s health check failed: %s", name, e)
                return name, False

        tasks = [_check(name, p) for name, p in self._providers.items()]
        for name, ok in await asyncio.gather(*tasks):
            results[name] = ok
            if ok:
                logger.info("✓ Provider %s ready", name)
            else:
                logger.warning("⚠ Provider %s unavailable (skip)", name)

        return results


def create_providers() -> ProviderRegistry:
    """工厂函数：创建所有 Provider 并注册。

    不阻塞启动 — health_check_all 在 Runtime 初始化时异步调用。
    """
    from agent.config import settings
    from agent.services.providers.netease_provider import NeteaseProvider
    from agent.services.providers.qq_provider import QQProvider

    registry = ProviderRegistry()
    registry.register(NeteaseProvider(base_url=settings.MUSIC_API_BASE_URL))
    registry.register(QQProvider(base_url=settings.QQ_API_BASE_URL))
    return registry
