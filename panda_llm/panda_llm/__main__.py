import uvicorn
from panda_llm.server import app

if __name__ == "__main__":
    uvicorn.run(
        "panda_llm.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    ) 