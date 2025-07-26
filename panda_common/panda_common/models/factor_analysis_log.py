from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class FactorAnalysisLog(BaseModel):
    """因子分析日志模型"""
    log_id: str = Field(..., description="日志ID")
    task_id: str = Field(..., description="关联的任务ID")
    factor_id: str = Field(..., description="因子ID")
    factor_name: str = Field(..., description="因子名称")
    user_id: str = Field(..., description="用户ID")
    level: str = Field("INFO", description="日志级别：DEBUG, INFO, WARNING, ERROR")
    message: str = Field(..., description="日志消息")
    timestamp: str = Field(..., description="日志时间戳")
    stage: str = Field("default", description="分析阶段")
    details: Optional[Dict[str, Any]] = Field(None, description="额外详情")

    class Config:
        schema_extra = {
            "example": {
                "log_id": "f7f46e9b-0d4a-4f2c-9b5e-3f0e3f8c0d1a",
                "task_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
                "factor_id": "60f1a2b3c4d5e6f7g8h9i0j1",
                "factor_name": "动量因子",
                "user_id": "user123",
                "level": "INFO",
                "message": "开始进行因子数据清洗",
                "timestamp": "2023-07-01T12:34:56.789Z",
                "stage": "data_cleaning",
                "details": {"rows_processed": 1000, "rows_filtered": 50}
            }
        } 