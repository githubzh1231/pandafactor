# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field, validator
from datetime import date

class Params(BaseModel):
    """
    回测参数类
    """
    # 回测区间：1年、3年、5年
    start_date: str = Field(..., example="2023-01-01", description="开始时间")
    end_date: str = Field(..., example="2024-01-01", description="结束时间")

    # 调仓周期：N天
    adjustment_cycle: int = Field(..., example=1, description="调仓周期，单位天")

    # 股票池：沪深300、中证500、全A股
    stock_pool: str = Field(..., example="沪深300", description="股票池")

    # 因子方向：正向、负向
    factor_direction: bool = Field(..., example=False, description="因子方向：False 负向，True 正向")

    # 分组数量：2-20
    group_number: int = Field(..., example=2, ge=2, le=20, description="分组数量：2-20")

    # 是否包含ST
    include_st: bool = Field(...,example=False, description="是否包含ST：False 不包含，True 包含")

    # 极值处理：标准差、中位数
    extreme_value_processing: str = Field(..., example="中位数", description="极值处理方式")

    # 添加验证器，验证日期格式
    @validator('start_date', 'end_date')
    def validate_dates(cls, v):
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError('Invalid date format. Use YYYY-MM-DD')