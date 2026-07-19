"""python -m agent 入口：封装 uvicorn + lifespan。

被 Electron spawn：python -m agent --port 8000
"""

import logging
import sys

import uvicorn
from agent.runtime import app


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    # 降低 noisy 库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def main():
    _setup_logging()
    import argparse
    parser = argparse.ArgumentParser(description="SoulChord Agent Runtime")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Hot reload")
    args = parser.parse_args()
    uvicorn.run(
        "agent.runtime:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
