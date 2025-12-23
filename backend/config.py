import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用配置类，使用 pydantic-settings 从环境变量加载配置
    """
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./app.db"
    
    # Redis 配置 (Celery broker/backend)
    redis_url: str = "redis://localhost:6379/0"
    
    # OpenAI API 配置
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    
    # Whisper 模型配置
    whisper_model: str = "medium"
    
    # 翻译配置
    target_language: str = "Chinese"
    translation_batch_size: int = 15
    
    # 调试模式
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """
    获取配置单例，使用 lru_cache 缓存配置实例
    """
    return Settings()


# 导出配置实例，方便直接导入使用
settings = get_settings()
