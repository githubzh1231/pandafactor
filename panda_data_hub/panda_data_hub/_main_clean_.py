from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from panda_data_hub.routes.data_clean import factor_data_clean, stock_market_data_clean
from panda_data_hub.routes.config import config_redefine
from panda_data_hub.routes.query import data_query

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

app.include_router(data_query.router, prefix="/datahub/api/v1", tags=["data_query"])
app.include_router(config_redefine.router, prefix="/datahub/api/v1", tags=["config_redefine"])
app.include_router(factor_data_clean.router, prefix="/datahub/api/v1", tags=["factor_data_clean"])
app.include_router(stock_market_data_clean.router, prefix="/datahub/api/v1", tags=["stock_market_data_clean"])
@app.get("/")
async def home():
    return {"message": "Welcome to the Panda Server!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8222)