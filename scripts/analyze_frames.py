"""VLM 逐帧视觉识别"""

import base64
import logging
from pathlib import Path

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
    """调用 VLM 分析帧，返回带 description 的帧列表，支持 OpenAI 和 Anthropic 格式"""
    provider = config.get("provider", "omlx")
    client, model, api_type = get_llm_client(config, provider)

    results = []

    for i, frame in enumerate(frames):
        try:
            b64 = _encode_image(frame["path"])
            if api_type == "anthropic":
                desc = _analyze_anthropic(client, model, b64)
            else:
                desc = _analyze_openai(client, model, b64)
        except Exception as e:
            logger.warning("帧 %d 分析失败: %s", frame["index"], e)
            desc = ""

        results.append({**frame, "description": desc})

    return results


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


def _analyze_anthropic(client, model: str, b64: str) -> str:
    """Anthropic 兼容接口帧分析"""
    import anthropic
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64,
                        },
                    },
                ],
            }
        ],
    )
    return "\n".join(block.text for block in response.content if hasattr(block, "text")).strip()
