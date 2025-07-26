from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from panda_factor_server.routes import user_factor_pro
from panda_llm.routes import chat_router
import mimetypes
from pathlib import Path
from starlette.staticfiles import StaticFiles

app = FastAPI(
    title="Panda Server",
    description="Server for Panda AI Factor System",
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
app.include_router(chat_router.router, prefix="/llm", tags=["panda_llm"])

# 获取根目录下的panda_web
frontend_folder = Path(__file__).resolve().parent.parent.parent / "panda_web" / "panda_web" / "static"
print(f"前端静态资源文件夹路径:{frontend_folder}")
# 显式设置 .js .css 的 MIME 类型
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")
# Mount the Vue dist directory at /factor path
app.mount("/factor", StaticFiles(directory=frontend_folder, html=True), name="static")

@app.get("/")
async def home():
    return {"message": "Welcome to the Panda Server!"}

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8111)

if __name__ == "__main__":
    main()