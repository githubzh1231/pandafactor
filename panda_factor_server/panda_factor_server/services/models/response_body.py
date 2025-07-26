from pydantic import BaseModel, Field
from datetime import datetime

class FactorListResponse(BaseModel):
    """
    因子排行榜
    """
    id: str = Field(..., description="因子ID")
    factor_name: str = Field(..., example="百分百胜率空手姐白刃", description="因子名称")
    daily_return: float = Field(..., example=98.7523, description="收益率，单位%")
    sharpe_ratio: float = Field(..., example=98.7523, description="夏普率")
    IC: float = Field(..., example=0.0248, description="IC")
    IR: float = Field(..., example=-1.4803, description="IR")
    updated_at: datetime = Field(..., example="2025-02-30 15:00", description="更新时间")
    created_at: datetime = Field(..., example="2025-02-30 15:00", description="创建时间")

    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S")  # 自定义时间字段的序列化格式
        }