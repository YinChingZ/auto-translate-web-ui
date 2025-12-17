import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import Video, VideoStatus, Subtitle
from ..tasks import process_video_task
from ..utils import generate_srt

router = APIRouter()

# 确保上传目录存在（统一使用 uploads/ 目录）
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/videos/upload", status_code=201)
async def upload_video(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # 1. 生成唯一文件名以避免冲突
    file_extension = Path(file.filename).suffix
    new_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / new_filename

    # 2. 保存文件到本地 uploads 文件夹
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")

    # 3. 创建数据库记录
    new_video = Video(
        filename=file.filename, # 保存原始文件名
        file_path=str(file_path),  # 转换为字符串存储
        status=VideoStatus.UPLOADING # 初始状态
    )
    
    db.add(new_video)
    await db.commit()
    await db.refresh(new_video)

    # 4. 更新状态为 PROCESSING 并触发 Celery 任务
    new_video.status = VideoStatus.PROCESSING
    await db.commit()
    
    # 调用 Celery 异步任务处理视频
    # 传递字符串形式的 UUID 以确保序列化兼容性
    process_video_task.delay(str(new_video.id), file_path)

    return {
        "id": new_video.id,
        "filename": new_video.filename,
        "status": new_video.status,
        "message": "Video uploaded successfully and processing started."
    }

class SubtitleUpdate(BaseModel):
    text_original: Optional[str] = None
    text_translated: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

@router.get("/videos/{video_id}/status")
async def get_video_status(video_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # 从 file_path 提取文件名，构造可访问的 URL
    file_name = Path(video.file_path).name
    video_url = f"/uploads/{file_name}"
    
    return {
        "status": video.status,
        "video_url": video_url,
        "filename": video.filename,
        "duration": video.duration
    }

@router.get("/videos/{video_id}/subtitles")
async def get_video_subtitles(video_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # 检查视频是否存在
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # 查询字幕
    result = await db.execute(
        select(Subtitle)
        .where(Subtitle.video_id == video_id)
        .order_by(Subtitle.start_time)
    )
    subtitles = result.scalars().all()
    return subtitles

@router.put("/subtitles/{sub_id}")
async def update_subtitle(
    sub_id: int, 
    subtitle_update: SubtitleUpdate, 
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Subtitle).where(Subtitle.id == sub_id))
    subtitle = result.scalar_one_or_none()
    
    if not subtitle:
        raise HTTPException(status_code=404, detail="Subtitle not found")
    
    if subtitle_update.text_original is not None:
        subtitle.text_original = subtitle_update.text_original
    if subtitle_update.text_translated is not None:
        subtitle.text_translated = subtitle_update.text_translated
    if subtitle_update.start_time is not None:
        subtitle.start_time = subtitle_update.start_time
    if subtitle_update.end_time is not None:
        subtitle.end_time = subtitle_update.end_time
        
    await db.commit()
    await db.refresh(subtitle)
    return subtitle


@router.get("/videos/{video_id}/export")
async def export_subtitles(
    video_id: uuid.UUID,
    translated: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    导出视频字幕为 SRT 文件。
    
    Args:
        video_id: 视频 UUID
        translated: 是否导出翻译后的字幕，默认为 True
    
    Returns:
        SRT 文件下载响应
    """
    # 检查视频是否存在
    result = await db.execute(select(Video).where(Video.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # 查询字幕并按时间排序
    result = await db.execute(
        select(Subtitle)
        .where(Subtitle.video_id == video_id)
        .order_by(Subtitle.start_time)
    )
    subtitles = result.scalars().all()
    
    if not subtitles:
        raise HTTPException(status_code=404, detail="No subtitles found for this video")
    
    # 生成 SRT 内容
    srt_content = generate_srt(subtitles, use_translated=translated)
    
    # 生成下载文件名（基于原始视频文件名）
    base_filename = os.path.splitext(video.filename)[0]
    suffix = "_translated" if translated else "_original"
    download_filename = f"{base_filename}{suffix}.srt"
    
    return Response(
        content=srt_content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{download_filename}"'
        }
    )

