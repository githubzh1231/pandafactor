import os
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

app = FastAPI(title="PandaAI Web Interface")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the absolute path to the static directory
DIST_DIR = os.path.join(os.path.dirname(__file__), "static")

# Mount the Vue dist directory at /factor path
app.mount("/factor", StaticFiles(directory=DIST_DIR, html=True), name="static")

# Redirect root to /factor
@app.get("/")
async def redirect_to_factor():
    return RedirectResponse(url="/factor")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True  # Enable auto-reload during development
    ) 