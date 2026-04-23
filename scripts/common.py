"""共享工具：配置加载、日志初始化、oMLX API 客户端、重试装饰器"""

import functools
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from openai import OpenAI

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_config(config_path: str | None = None) -> dict:
    """加载 config.yaml"""
    path = Path(config_path) if config_path else _PROJECT_ROOT / "config.yaml"
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path) as f:
        config = yaml.safe_load(f)
    if env_url := os.getenv("OMLX_BASE_URL"):
        config.setdefault("omlx", {})["base_url"] = env_url
    vault = config.get("obsidian", {}).get("vault_path", "")
    if vault.startswith("~"):
        config["obsidian"]["vault_path"] = os.path.expanduser(vault)
    return config


def setup_logging(script_name: str, config: dict | None = None) -> logging.Logger:
    """初始化日志，配置根 logger 使子模块日志也能写入文件"""
    cfg = config or {}
    log_cfg = cfg.get("logging", {})
    log_dir = _PROJECT_ROOT / log_cfg.get("dir", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, log_cfg.get("level", "INFO").upper())

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"{script_name}_{timestamp}.log"

    # 配置根 logger，这样 scripts.* 下所有模块都能输出
    root = logging.getLogger()
    root.setLevel(level)

    # 避免重复添加 handler
    has_file = any(isinstance(h, logging.FileHandler) for h in root.handlers)
    if not has_file:
        fmt = logging.Formatter("%(asctime)s [%(name)s %(levelname)s] %(message)s")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        root.addHandler(ch)

    return logging.getLogger(script_name)


def get_omlx_client(config: dict) -> OpenAI:
    """获取 oMLX OpenAI 兼容客户端"""
    return OpenAI(
        base_url=config["omlx"]["base_url"],
        api_key=config["omlx"].get("api_key", ""),
    )


def get_llm_client(config: dict, provider: str | None = None):
    """根据 provider 返回对应的 LLM 客户端和模型名

    Returns: (client, model_name)
    """
    provider = provider or config.get("provider", "omlx")

    if provider == "minimax":
        if Anthropic is None:
            raise ImportError("需要安装 anthropic: uv add anthropic")
        mm = config["minimax"]
        api_key = os.getenv(mm["api_key_env"], "")
        if not api_key:
            raise ValueError(f"环境变量 {mm['api_key_env']} 未设置")
        client = Anthropic(base_url=mm["base_url"], api_key=api_key)
        return client, mm["model"], "anthropic"
    else:
        client = OpenAI(
            base_url=config["omlx"]["base_url"],
            api_key=config["omlx"].get("api_key", ""),
        )
        return client, config["omlx"]["llm_model"], "openai"


def retry(max_retries: int = 3, delays: tuple[float, ...] = (1, 2, 4)):
    """重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt, delay in enumerate(delays[:max_retries], 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_retries:
                        time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator


def get_work_dir(bvid: str) -> Path:
    """获取单个 BV 号的临时工作目录"""
    work = _PROJECT_ROOT / "work" / bvid
    work.mkdir(parents=True, exist_ok=True)
    return work


def get_vault_paths(config: dict) -> tuple[Path, Path]:
    """返回 (notes_dir, images_dir)"""
    obs = config["obsidian"]
    vault = Path(obs["vault_path"])
    return vault / obs["notes_dir"], vault / obs["images_dir"]


def progress(current: int, total: int, desc: str = ""):
    """控制台进度显示"""
    pct = current / total * 100 if total else 0
    filled = int(40 * current / total) if total else 0
    bar = "█" * filled + "░" * (40 - filled)
    msg = f"\r进度: [{bar}] {pct:.1f}% ({current}/{total})"
    if desc:
        msg += f" | {desc}"
    sys.stdout.write(msg)
    sys.stdout.flush()
    if current == total:
        sys.stdout.write("\n")
