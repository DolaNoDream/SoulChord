"""Provider 账号状态数据模型。

NeteaseProvider / QQProvider 的登录状态统一表示为 ProviderAccount。
供 ProviderAccountService 刷新缓存 + SourceSelector 动态优先级决策。
"""

from dataclasses import dataclass


@dataclass
class ProviderAccount:
    """Provider 账号状态。

    provider_account_service 每 300s 刷新一次此数据，
    SourceSelector._resolve_priority() 据此调整播放源优先级。
    """

    provider: str
    login_status: bool
    nickname: str = ""
    avatar_url: str | None = None
