"""VLM 逐帧视觉识别"""

import base64
import json
import logging
import os
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from scripts.common import get_llm_client

logger = logging.getLogger(__name__)

PROMPT = (
    "描述这张视频截图中的内容，包括场景、人物、动作、文字等关键信息。"
    "用中文回答，简洁准确，一两句话即可。"
)


def _encode_image(image_path: Path) -> str:
    """将图片文件编码为 base64 字符串"""
    return base64.b64encode(Path(image_path).read_bytes()).decode()


def analyze_frames(
    frames: list[dict], config: dict,
) -> list[dict]:
    """调用 VLM 分析帧，返回带 description 的帧列表

    支持两种模式：
    - OpenAI 兼容接口（omlx）：通过 chat completions API 发送 base64 图片
    - MiniMax 云端：通过 MiniMax VLM 专用 API (/v1/coding_plan/vlm) 发送 base64 图片
    """
    provider = config.get("provider", "omlx")
    client, model, api_type = get_llm_client(config, provider)

    results = []

    for i, frame in enumerate(frames):
        try:
            b64 = _encode_image(frame["path"])
            if api_type == "anthropic":
                desc = _analyze_minimax_vlm(config, b64)
            else:
                desc = _analyze_openai(client, model, b64)
        except Exception as e:
            logger.warning("帧 %d 分析失败: %s", frame["index"], e)
            desc = ""

        results.append({**frame, "description": desc})

    return results


def _get_minimax_api_host(config: dict) -> str:
    """从配置中提取 MiniMax API 基础地址（scheme + host）"""
    mm = config.get("minimax", {})
    if api_host := mm.get("api_host"):
        return api_host
    base_url = mm.get("base_url", "https://api.minimaxi.com/anthropic")
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _analyze_minimax_vlm(config: dict, b64: str) -> str:
    """MiniMax VLM 专用 API 帧分析 (/v1/coding_plan/vlm)"""
    mm = config.get("minimax", {})
    api_key = os.getenv(mm.get("api_key_env", "MINIMAX_API_KEY"), "")
    if not api_key:
        raise RuntimeError(f"环境变量 {mm.get('api_key_env', 'MINIMAX_API_KEY')} 未设置")

    api_host = _get_minimax_api_host(config)
    payload = json.dumps({
        "prompt": PROMPT,
        "image_url": f"data:image/png;base64,{b64}",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{api_host}/v1/coding_plan/vlm",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    content = data.get("content", "")
    if not content:
        base_resp = data.get("base_resp", {})
        raise RuntimeError(
            f"MiniMax VLM 返回空内容: "
            f"{base_resp.get('status_code')}-{base_resp.get('status_msg')}"
        )

    return content.strip()


def _analyze_openai(client, model: str, b64: str) -> str:
    """OpenAI 兼容接口帧分析"""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64}"
                        },
                    },
                ],
            }
        ],
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()
