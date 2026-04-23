"""流水线编排：串联所有子模块完成视频笔记生成"""

import argparse
import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.analyze_frames import analyze_frames
from scripts.common import get_vault_paths, get_work_dir, load_config, progress, setup_logging
from scripts.extract_frames import download_video, extract_keyframes
from scripts.fetch_data import fetch_all, resolve_input
from scripts.generate_notes import generate_note
from scripts.transcribe_audio import transcribe

logger = logging.getLogger(__name__)


def process_single(bvid: str, config: dict, work_dir: Path | None = None, provider: str | None = None) -> Path | None:
    """处理单个视频的完整流水线"""
    notes_dir, images_dir = get_vault_paths(config)

    # 检查已有笔记
    existing = list(notes_dir.glob(f"*({bvid}).md"))
    if existing:
        logger.info("笔记已存在，跳过: %s", existing[0])
        return existing[0]

    if work_dir is None:
        work_dir = get_work_dir(bvid)

    frames_dir = images_dir / bvid
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 1. 获取数据
    data = None
    try:
        data = fetch_all(bvid, work_dir)
    except Exception as e:
        logger.warning("获取数据失败 %s: %s", bvid, e)

    video_info = data["video"] if data else {"bvid": bvid, "title": bvid, "author": "", "duration": "", "url": f"https://www.bilibili.com/video/{bvid}", "description": ""}
    subtitle_text = data["subtitle"]["text"] if data and data.get("subtitle", {}).get("available") else ""
    comments = data["comments"] if data else []
    audio_path = data["audio_path"] if data else None

    # 2. 语音转录（无字幕且有音频时）
    transcript_text = ""
    if not subtitle_text and audio_path:
        try:
            result = transcribe(Path(audio_path), config)
            transcript_text = result["text"]
            # 保存转录结果到 work 目录
            (work_dir / "transcript.txt").write_text(result["text"], encoding="utf-8")
            if result.get("srt"):
                (work_dir / "transcript.srt").write_text(result["srt"], encoding="utf-8")
            logger.info("转录结果已保存: %s", work_dir / "transcript.txt")
        except Exception as e:
            logger.warning("转录失败 %s: %s", bvid, e)

    # 3. 关键帧抽取
    frames = []
    try:
        video_path = download_video(bvid, work_dir)
        frame_paths = extract_keyframes(video_path, frames_dir, config)
        from scripts.extract_frames import get_frame_timestamps
        frames = get_frame_timestamps(frame_paths)
    except Exception as e:
        logger.warning("关键帧抽取失败 %s: %s", bvid, e)

    # 4. 帧分析
    if frames:
        try:
            frames = analyze_frames(frames, config)
        except Exception as e:
            logger.warning("帧分析失败 %s: %s", bvid, e)

    # 5. 生成笔记
    try:
        video_info["_images_dir"] = config["obsidian"]["images_dir"]
        note_path = generate_note(
            video_info=video_info,
            subtitle_text=subtitle_text,
            transcript_text=transcript_text,
            frames=frames,
            comments=comments,
            notes_dir=notes_dir,
            config=config,
            provider=provider,
        )
        return note_path
    except Exception as e:
        logger.error("生成笔记失败 %s: %s", bvid, e)
        return None


def run_pipeline(
    raw_input: str,
    mode: str = "auto",
    max_videos: int = 10,
    force: bool = False,
    provider: str | None = None,
) -> list[Path]:
    """运行完整流水线"""
    config = load_config()
    setup_logging("pipeline", config)

    logger.info("解析输入: %s (mode=%s)", raw_input, mode)
    bvids = resolve_input(raw_input, mode=mode, max_videos=max_videos)
    logger.info("共 %d 个视频待处理 (provider=%s)", len(bvids), provider or config.get("provider", "omlx"))

    results: list[Path] = []
    total = len(bvids)
    for i, bvid in enumerate(bvids, 1):
        progress(i, total, desc=bvid)
        if force:
            notes_dir, _ = get_vault_paths(config)
            for existing in notes_dir.glob(f"*({bvid}).md"):
                existing.unlink()
                logger.info("强制删除已有笔记: %s", existing)

        result = process_single(bvid, config, provider=provider)
        if result:
            results.append(result)
            logger.info("[%d/%d] 完成: %s", i, total, result)
        else:
            logger.warning("[%d/%d] 失败: %s", i, total, bvid)

    logger.info("流水线完成: %d/%d 成功", len(results), total)
    return results


def main():
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="Bilibili 视频笔记流水线")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user", help="UP主名称或 UID")
    group.add_argument("--url", help="视频 URL 或 b23.tv 短链")
    group.add_argument("--bv", help="BV 号")

    parser.add_argument("--max", type=int, default=10, help="最大视频数（仅 UP 主模式）")
    parser.add_argument("--force", action="store_true", help="覆盖已有笔记")
    parser.add_argument("--provider", choices=["omlx", "minimax"], default=None, help="LLM 提供者（默认读取配置）")
    parser.add_argument("--vault", help="覆盖 vault 路径")
    parser.add_argument("--config", help="配置文件路径")

    args = parser.parse_args()

    # 覆盖配置路径
    if args.config:
        config = load_config(args.config)
    else:
        config = load_config()

    if args.vault:
        config["obsidian"]["vault_path"] = args.vault

    # 确定输入和模式
    if args.user:
        raw_input, mode = args.user, "user"
    elif args.url:
        raw_input, mode = args.url, "url"
    else:
        raw_input, mode = args.bv, "bv"

    results = run_pipeline(raw_input, mode=mode, max_videos=args.max, force=args.force, provider=args.provider)
    print(f"\n完成: {len(results)} 个笔记已生成")


if __name__ == "__main__":
    main()
