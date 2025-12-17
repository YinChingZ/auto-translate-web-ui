from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from .database import engine, Base
from .api import routes

# 使用 pathlib 定义上传目录路径，确保跨平台兼容性
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时创建数据库表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭时清理资源（如果需要）

app = FastAPI(
    title="AutoTranslateWebUI API",
    description="API for AI Video Translation System",
    version="0.1.0",
    lifespan=lifespan
)

# 确保上传目录存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 挂载静态文件目录
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# 注册路由
app.include_router(routes.router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to AutoTranslateWebUI API"}
