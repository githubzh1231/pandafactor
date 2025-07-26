from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Optional
from models.common import Params
class CreateFactorRequest(BaseModel):
    """
    创建因子请求参数
    """
    user_id: str = Field(..., example="2", description="用户id")
    factor_name: str = Field(..., example="圣杯", description="因子名称")
    factor_type: str = Field(..., example="macro", description="因子类型，只有两种：future｜stock")
    is_persistent: bool = Field(default=False, example=False, description="是否持久化，线上使用只传 false")
    cron: Optional[str] = Field(default=None, example="0 0 12 * * ?", description="cron表达式，开启持久化时传入，默认为null")
    factor_start_day: Optional[str] = Field(default=None, example="2018-01-01", description="因子持久化开始时间，开启持久化时传入，默认为null")
    code: str = Field(..., example="json", description="代码")
    code_type: str = Field(..., example="macro", description="因子类型，只有两种：macro｜python")
    status: int = Field(..., example=0, description="状态：0:未运行，1:运行中，2:运行成功，3：运行失败")
    describe: str = Field(..., example="该因子表述换手率因子", description="描述")
    params: Optional[Params] = Field(default=None, description="参数")

    # 添加验证器，将日期字符串转换为 ISO 格式
    @validator('factor_start_day')
    def validate_factor_start_day(cls, v):
        if v is not None:
            try:
                return date.fromisoformat(v).isoformat()
            except ValueError:
                raise ValueError('Invalid date format. Use YYYY-MM-DD')
        return v