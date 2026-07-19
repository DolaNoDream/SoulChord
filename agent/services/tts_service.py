"""TTSService — 语音合成服务（讯飞 mock）。

★ MVP mock 输出，不接真实讯飞 API（P2 替换）
★ 定位：Service 层（非 Tool 层），由 ActionExecutor 消费
★ 不放入 adapter.py（adapter = Tool dispatch，非 action execution）
"""

import logging

logger = logging.getLogger(__name__)


class TTSService:
    """语音合成服务。

    当前 MVP 返回 mock 音频信息，P2 接真实讯飞 API。
    P2 工作项：appid/key 配置 / token 刷新 / 音频文件管理 / WS 长连接。
    """

    async def synthesize(self, text: str) -> dict:
        """文本转语音。

        Args:
            text: 要合成的文本

        Returns:
            dict: {
                "audio_url": str,      # 音频文件 URL（mock）
                "duration_ms": int,    # 预估时长
                "provider": str,       # "xunfei_mock"（MVP）
            }
        """
        if not text or not text.strip():
            logger.warning("TTSService.synthesize: empty text")
            return {
                "audio_url": "",
                "duration_ms": 0,
                "provider": "xunfei_mock",
            }

        # MVP mock：按文本长度估算时长（假设每秒 4 个字的语速）
        estimated_ms = max(1000, len(text.strip()) * 250)

        logger.info("TTSService.synthesize: text_len=%d duration_ms=%d",
                     len(text), estimated_ms)

        return {
            "audio_url": f"mock://tts/{hash(text)}.wav",
            "duration_ms": estimated_ms,
            "provider": "xunfei_mock",
        }


# 模块级单例
tts_service = TTSService()
