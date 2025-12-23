import uuid
import enum
from typing import List, Optional, Dict, Any
from sqlalchemy import String, Float, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs

# 定义基础模型类，继承 AsyncAttrs 以支持异步属性访问
class Base(AsyncAttrs, DeclarativeBase):
    pass

# 定义视频状态枚举
class VideoStatus(str, enum.Enum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"

class Video(Base):
    __tablename__ = "videos"

    # 使用 UUID 作为主键
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    # 使用 SQLAlchemy 的 Enum 类型映射 Python 枚举
    status: Mapped[VideoStatus] = mapped_column(
        SAEnum(VideoStatus), 
        default=VideoStatus.UPLOADING, 
        nullable=False
    )
    # 视频时长（秒），上传初期可能未知，设为可空
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # 存储视频特定的配置（如翻译批次大小、上下文窗口等）
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # 建立与 Subtitle 的一对多关系
    subtitles: Mapped[List["Subtitle"]] = relationship(
        back_populates="video", 
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Video(id={self.id}, filename='{self.filename}', status='{self.status}')>"

class Subtitle(Base):
    __tablename__ = "subtitles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 外键关联 Video 表的 UUID
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"), nullable=False)
    
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    
    # 原始内容（Whisper 输出）
    text_original: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # 翻译内容（LLM 输出）
    text_translated: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # 置信度 0.0-1.0
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # 建立与 Video 的多对一关系
    video: Mapped["Video"] = relationship(back_populates="subtitles")

    def __repr__(self) -> str:
        return f"<Subtitle(id={self.id}, video_id={self.video_id}, start={self.start_time}, end={self.end_time})>"
