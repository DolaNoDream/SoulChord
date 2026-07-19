"""ASRService — 语音识别服务骨架。

★ MVP mock 输出，不接真实讯飞 ASR API（P2 替换）
★ 0 DJ_TOOL + 1 INTERNAL（recognize_speech）
★ 定位：Service 层，由 adapter.dispatch() 消费
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ASRService:
    """语音识别服务。

    当前 MVP 返回 mock 转写结果。
    P2 工作项：讯飞 API 接入 / 音频格式处理 / 流式识别。
    """

    async def recognize(self, audio_url: str) -> dict:
        """语音转文字。

        Args:
            audio_url: 音频文件 URL 或本地路径

        Returns:
            dict: {
                "text": str,            # 转写文本
                "confidence": float,    # 置信度 0.0~1.0
                "duration_ms": int,     # 音频时长（毫秒）
                "source": str,          # "xunfei_mock"（MVP）
            }
        """
        if not audio_url or not audio_url.strip():
            logger.warning("ASRService.recognize: empty audio_url")
            return {
                "text": "",
                "confidence": 0.0,
                "duration_ms": 0,
                "source": "xunfei_mock",
            }

        # MVP mock：按 URL 特征返回模拟结果
        logger.info("ASRService.recognize: url=%s returning mock", audio_url)
        return {
            "text": "这是一段测试语音识别的模拟文本",
            "confidence": 0.95,
            "duration_ms": 3000,
            "source": "xunfei_mock",
        }


# 模块级单例
asr_service = ASRService()
