"""LLM Service — 封装 DeepSeek/OpenAI API 调用。

职责边界：
  - 只做 prompt → structured dict 的调用
  - 不感知业务 schema（不传 schema 参数）
  - JSON 解析失败后自动重试一次（retry_prompt 可由调用方定制）
  - 结构化错误码返回（不 raise 穿透 Runtime）

错误码：
  LLM_API_ERROR          API 调用异常（网络/鉴权）
  LLM_TIMEOUT            请求超时
  LLM_JSON_PARSE_FAILED  JSON 解析失败（重试后仍失败）
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_RETRY_PROMPT = (
    "\n\nYour previous output was invalid JSON. "
    "Return JSON only, no markdown code blocks."
)


class LLMService:
    """LLM 调用服务。

    Usage:
        svc = LLMService()
        svc.configure(api_key="sk-...", base_url="https://...", model="deepseek-chat")
        result = await svc.call_json(prompt)

    Returns:
        {"ok": True,  "data": {...}}
        {"ok": False, "error": {"code": "...", "message": "..."}}
    """

    def __init__(self):
        self._api_key: str = ""
        self._base_url: str = ""
        self._model: str = ""
        self._timeout_s: int = 30
        self._client: Optional["AsyncOpenAI"] = None  # type: ignore
        self._configured: bool = False

    def configure(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        timeout_s: int = 30,
    ) -> None:
        """配置 LLM 服务连接信息（在 lifespan 启动时调用）。"""
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._timeout_s = timeout_s
        self._configured = True

    def _ensure_client(self):
        """延迟初始化 AsyncOpenAI client。"""
        if self._client is not None:
            return
        if not self._configured:
            raise RuntimeError(
                "LLMService not configured. Call configure() first."
            )
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=self._timeout_s,
        )

    async def call_json(
        self,
        prompt: str,
        temperature: float = 0.7,
        retry_prompt: Optional[str] = None,
    ) -> dict:
        """调用 LLM 并解析 JSON 响应。

        Args:
            prompt: 完整 system prompt（含 schema 定义）
            temperature: 生成温度
            retry_prompt: JSON 解析失败时的重试 prompt 后缀。
                          默认提示 LLM 只输出 JSON。

        Returns:
            {"ok": True,  "data": dict}  — 成功
            {"ok": False, "error": {...}} — 失败，不会 raise
        """
        self._ensure_client()
        retry_suffix = retry_prompt if retry_prompt is not None else _DEFAULT_RETRY_PROMPT

        # ── 第一次调用 ──
        api_result = await self._call_api(prompt, temperature)
        if not api_result["ok"]:
            return {
                "ok": False,
                "error": {"code": "LLM_API_ERROR", "message": api_result["error"]},
            }

        content = api_result["content"]
        result = self._parse_json(content)
        if result["ok"]:
            return result  # {"ok": True, "data": ...}

        # ── 第一次 JSON 解析失败 → 重试 ──
        logger.warning("LLM JSON parse failed on first attempt, retrying: %s", result["error"]["message"])
        retry_api = await self._call_api(prompt + retry_suffix, temperature)
        if not retry_api["ok"]:
            return {
                "ok": False,
                "error": {"code": "LLM_API_ERROR", "message": retry_api["error"]},
            }

        retry_result = self._parse_json(retry_api["content"])
        if retry_result["ok"]:
            return retry_result

        return {
            "ok": False,
            "error": {
                "code": "LLM_JSON_PARSE_FAILED",
                "message": f"JSON parse failed after retry: {retry_result['error']['message']}",
            },
        }

    # ── 内部方法 ──

    async def _call_api(self, prompt: str, temperature: float) -> dict:
        """调用 DeepSeek/OpenAI API。

        Returns:
            {"ok": True,  "content": "..."}  — 成功
            {"ok": False, "error": "..."}     — 失败（含异常类型 + 信息）
        """
        try:
            response = await self._client.chat.completions.create(  # type: ignore
                model=self._model,
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=temperature,
            )
            content = response.choices[0].message.content or ""
            return {"ok": True, "content": content}
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            logger.error("LLM API call failed: %s", err_msg)
            return {"ok": False, "error": err_msg}

    @staticmethod
    def _parse_json(content: str) -> dict:
        """解析 JSON 字符串。

        Args:
            content: LLM 返回的原始字符串

        Returns:
            {"ok": True,  "data": dict}   — 解析成功
            {"ok": False, "error": {...}}  — 解析失败
        """
        if not content or not content.strip():
            return {"ok": False, "error": {"code": "LLM_JSON_PARSE_FAILED", "message": "Empty response"}}
        try:
            data = json.loads(content)
            if not isinstance(data, dict):
                return {"ok": False, "error": {"code": "LLM_JSON_PARSE_FAILED", "message": f"Expected dict, got {type(data).__name__}"}}
            return {"ok": True, "data": data}
        except json.JSONDecodeError as e:
            return {"ok": False, "error": {"code": "LLM_JSON_PARSE_FAILED", "message": str(e)}}
