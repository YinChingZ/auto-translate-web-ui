from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base
from .config import settings

# 从配置文件加载数据库 URL
DATABASE_URL = settings.database_url

# 根据数据库类型设置连接参数
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False  # SQLite 特定配置

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,  # 调试模式下打印 SQL
    connect_args=connect_args
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 依赖项：获取数据库会话
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
