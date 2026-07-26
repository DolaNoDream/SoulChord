"""ProviderAccountService — asyncio background loop 定期刷新 Provider 账号状态。

不在 Scheduler 中注册事件，因为账号状态是基础设施健康监测，
而非用户可感知的业务事件。生命周期直接绑定 Runtime lifespan。
"""

import asyncio
import logging

from agent.services.accounts.models import ProviderAccount
from agent.services.providers.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class ProviderAccountService:
    """Provider 账号状态服务。

    start() 在 lifespan 中调用，启动后每 refresh_interval_s 刷新一次账号状态。
    刷新结果缓存在 _accounts dict 中，通过 get_all() 暴露给 SourceSelector。

    仅查询 support_account=True 的 Provider。不阻塞启动 — refresh 失败不影响 runtime。
    """

    def __init__(self, registry: ProviderRegistry, refresh_interval_s: int = 300):
        self._accounts: dict[str, ProviderAccount] = {}
        self._registry = registry
        self._interval = refresh_interval_s
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """首次刷新后启动 background loop。"""
        await self.refresh()
        self._task = asyncio.create_task(self._refresh_loop())
        logger.info("ProviderAccountService started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        """停止 background loop。"""
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("ProviderAccountService stopped")

    async def _refresh_loop(self) -> None:
        """后台定期刷新循环。"""
        try:
            while True:
                await asyncio.sleep(self._interval)
                await self.refresh()
        except asyncio.CancelledError:
            logger.debug("ProviderAccountService refresh loop cancelled")
            raise

    async def refresh(self) -> None:
        """遍历 support_account=True 的 Provider 并刷新状态。"""
        for provider in self._registry.get_all():
            if not getattr(provider, "support_account", False):
                continue
            getter = getattr(provider, "get_account_status", None)
            if getter is None:
                continue
            try:
                account = await getter()
                self._accounts[provider.name] = account
                logger.debug("Account refreshed: %s (login=%s)", provider.name, account.login_status)
            except Exception as e:
                logger.warning("Account refresh failed for %s: %s", provider.name, e)

    def get_all(self) -> dict[str, ProviderAccount]:
        """返回当前缓存的全部账号状态。"""
        return dict(self._accounts)

    def get(self, provider_name: str) -> ProviderAccount | None:
        """按名称获取 Provider 账号状态。"""
        return self._accounts.get(provider_name)


# ── 模块级单例访问（供 lifespan / dispatcher / action_executor 共享） ──

_account_service_instance: ProviderAccountService | None = None


def get_account_service() -> ProviderAccountService | None:
    """获取全局 ProviderAccountService 实例（可能为 None）。"""
    return _account_service_instance


def set_account_service(service: ProviderAccountService) -> None:
    """设置全局 ProviderAccountService 实例（由 lifespan 调用）。"""
    global _account_service_instance
    _account_service_instance = service
