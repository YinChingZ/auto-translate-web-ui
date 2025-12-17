import asyncio
import uuid
from celery import Celery
from sqlalchemy import select
from .database import AsyncSessionLocal
from .models import Video, Subtitle, VideoStatus
from .services.pipeline import process_video
from .config import settings

# Initialize Celery
# 从配置文件加载 Redis URL
celery_app = Celery(
    "worker",
    broker=settings.redis_url,
    backend=settings.redis_url
)


async def _update_video_status(video_id: uuid.UUID, status: VideoStatus):
    """
    更新视频状态
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Video).where(Video.id == video_id))
        video = result.scalars().first()
        if video:
            video.status = status
            await session.commit()
            print(f"Video {video_id} status updated to {status}")


async def _save_subtitles_and_complete(video_id: uuid.UUID, segments: list):
    """
    批量保存字幕数据并更新视频状态为 READY
    """
    async with AsyncSessionLocal() as session:
        # 验证视频存在
        result = await session.execute(select(Video).where(Video.id == video_id))
        video = result.scalars().first()
        if not video:
            raise ValueError(f"Video {video_id} not found in database")

        # 批量创建 Subtitle 对象
        for seg in segments:
            subtitle = Subtitle(
                video_id=video_id,
                start_time=seg['start'],
                end_time=seg['end'],
                text_original=seg['text_original'],
                text_translated=seg.get('text_translated', ''),  # 添加翻译文本
                confidence=seg.get('confidence', 0.0)
            )
            session.add(subtitle)
        
        # 更新视频状态为 READY
        video.status = VideoStatus.READY
        
        # 提交事务，确保数据落库
        await session.commit()
        print(f"Saved {len(segments)} subtitles for video {video_id}, status set to READY")


@celery_app.task(bind=True, max_retries=3)
def process_video_task(self, video_id_str: str, file_path: str):
    """
    Celery 任务：处理视频文件
    
    Args:
        video_id_str: 视频 ID（字符串形式，确保序列化兼容）
        file_path: 视频文件路径
    """
    video_id = uuid.UUID(video_id_str)
    print(f"Starting video processing task for {video_id}")
    
    try:
        # 1. 调用 pipeline 处理视频（提取音频 -> VAD -> Whisper）
        # 这是 CPU 密集型操作
        print(f"Processing video file: {file_path}")
        segments = process_video(file_path)
        print(f"Pipeline returned {len(segments)} segments")
        
        # 2. 批量保存字幕到数据库，并更新状态为 READY
        asyncio.run(_save_subtitles_and_complete(video_id, segments))
        
        print(f"Video {video_id} processing completed successfully")
        return {"status": "success", "video_id": video_id_str, "segments_count": len(segments)}
        
    except Exception as e:
        print(f"Task failed for video {video_id}: {e}")
        # 更新状态为 ERROR
        asyncio.run(_update_video_status(video_id, VideoStatus.ERROR))
        raise e
