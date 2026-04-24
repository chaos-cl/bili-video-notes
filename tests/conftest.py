"""共享测试 fixtures"""

from pathlib import Path

import pytest

import scripts.common as common


@pytest.fixture
def config():
    """返回测试用配置"""
    return {
        "omlx": {
            "base_url": "http://localhost:8000/v1",
            "llm_model": "Qwen3.6-35B-A3B-nvfp4",
            "vlm_model": "Qwen3-VL-8B-Instruct-MLX-4bit",
        },
        "minimax": {
            "base_url": "https://api.minimaxi.com/anthropic",
            "api_key_env": "MINIMAX_API_KEY",
            "model": "MiniMax-M2.7",
        },
        "provider": "omlx",
        "obsidian": {
            "vault_path": "/tmp/test_bilibili_vault",
            "notes_dir": "video-notes",
            "images_dir": "video-notes-images",
        },
        "frames": {
            "scene_threshold": 0.3,
            "min_interval": 30,
            "max_frames": 20,
            "max_width": 1920,
        },
        "whisper": {
            "model": "large-v3-turbo",
            "language": "auto",
            "device": "mlx",
        },
        "logging": {"dir": "logs", "level": "DEBUG"},
    }


@pytest.fixture
def mock_config(monkeypatch, config):
    """monkeypatch common.load_config 返回测试配置"""
    monkeypatch.setattr(common, "load_config", lambda: config)
    return config
