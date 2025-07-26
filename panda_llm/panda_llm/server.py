from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from panda_common.logger_config import logger


# 创建 FastAPI 应用
app = FastAPI(
    title="Panda LLM API",
    description="基于 FastAPI 和 DeepSeek 的聊天 API 服务",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入路由
from panda_llm.routes import chat_router

# 注册路由
app.include_router(chat_router.router, prefix="/llm", tags=["chat"])

# 启动日志
logger.info("Panda LLM API 服务已启动") 