import os
import sys
import time
import logging
import traceback
from datetime import datetime
import pytz
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from panda_factor_server.routes import user_factor_pro
from panda_factor_server.models.result_data import ResultData

# 设置时区
os.environ['TZ'] = 'Asia/Shanghai'
#time.tzset()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('panda.log')
    ]
)
logger = logging.getLogger('panda')

app = FastAPI(
    title="Panda Factor API",
    description="Panda Factor API for factor analysis",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
# app.include_router(user_factor.router, prefix="/api/v1", tags=["user_factors"])
app.include_router(user_factor_pro.router, prefix="/api/v1", tags=["user_factors"])

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now(pytz.timezone('Asia/Shanghai'))
    response = await call_next(request)
    end_time = datetime.now(pytz.timezone('Asia/Shanghai'))
    duration = (end_time - start_time).total_seconds()
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration:.2f}s")
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = f"全局异常: {str(exc)}\n{traceback.format_exc()}"
    logger.error(error_msg)
    return JSONResponse(
        status_code=500,
        content=ResultData.fail("500", error_msg).model_dump()
    )

@app.get("/")
async def root():
    return {"message": "Welcome to Panda Factor API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)