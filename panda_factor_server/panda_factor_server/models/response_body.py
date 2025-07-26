from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Union, List
from panda_factor_server.models.common import Params

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

class UserFactorDetailResponse(BaseModel):
    user_id: str = Field(..., example="2", description="用户id")
    name: Optional[str] = Field(default=None, example="圣杯", description="因子中文名称")
    factor_name: str = Field(..., example="Grail", description="Unique Factor English Name")
    factor_type: str = Field(..., example="macro", description="因子类型，只有两种：future｜stock")
    is_persistent: bool = Field(default=False, example=False, description="是否持久化，线上使用只传 false")
    cron: Optional[str] = Field(default=None, example="0 0 12 * * ?",
                                description="cron表达式，开启持久化时传入，默认为null")
    factor_start_day: Optional[str] = Field(default=None, example="2018-01-01",
                                            description="因子持久化开始时间，开启持久化时传入，默认为null")
    code: str = Field(..., example="json", description="代码")
    code_type: str = Field(..., example="formula", description="因子类型，只有两种：formula｜python")
    tags: Optional[str] = Field(default=None, example="动量因子,质量因子", description="因子标签，多个标签\",\"分隔")
    status: int = Field(..., example=0, description="状态：0:未运行，1:运行中，2:运行成功，3：运行失败")
    describe: str = Field(..., example="该因子表述换手率因子", description="描述")
    params: Optional[Params] = Field(default=None, description="参数")
    last_run_at: Optional[datetime] = Field(default=None, description="最后运行时间")
    result: Optional[dict] = Field(default=None, description="运行结果")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")
    id: Optional[str] = Field(default=None, alias="_id", description="因子ID")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @validator('name', pre=True)
    def validate_name(cls, v):
        if v is None:
            return None
        # 如果是数字类型，转换为字符串
        if isinstance(v, (int, float)):
            return str(v)
        return v

class TaskResult(BaseModel):
    """任务结果实体类"""
    process_status:Optional[int] = Field(default=0, description="因子分析进度")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    result: Optional[Union[dict, str]] = Field(default=None, description="任务结果")
    last_log_message: Optional[str] = Field(default=None, description="最后一条日志消息")
    last_log_time: Optional[datetime] = Field(default=None, description="最后一条日志时间")
    task_id: Optional[str] = Field(default=None, description="任务ID")
    factor_id: Optional[str] = Field(default=None, description="因子ID")
    user_id: Optional[str] = Field(default=None, description="用户ID")
    factor_name: Optional[str] = Field(default=None, description="因子名称")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ChartAxisData(BaseModel):
    """图表轴数据"""
    name: str = Field(..., description="轴的名称")
    data: List[Union[str, float]] = Field(..., description="轴的数据")

class ExcessChartData(BaseModel):
    """超额收益图表数据"""
    title: str = Field(..., description="图表标题")
    x: List[ChartAxisData] = Field(..., description="X轴数据")
    y: List[ChartAxisData] = Field(..., description="Y轴数据")

class FactorExcessChartResponse(BaseModel):
    """因子超额收益图表响应"""
    excess_chart: Optional[ExcessChartData] = Field(default=None, description="超额收益图表数据")
    task_id: str = Field(..., description="任务ID")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class FactorAnalysisIndicator(BaseModel):
    """因子分析指标"""
    指标: str = Field(..., description="指标名称")
    python: str = Field(..., description="指标值")

class FactorAnalysisDataResponse(BaseModel):
    """因子分析数据响应"""
    task_id: str = Field(..., description="任务ID")
    factor_data_analysis: List = Field(..., description="因子分析数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class GroupReturnAnalysis(BaseModel):
    """分组收益分析指标"""
    分组: str = Field(..., description="分组名称")
    年化收益率: str = Field(..., description="年化收益率")
    超额年化: str = Field(..., description="超额年化")
    最大回撤: str = Field(..., description="最大回撤")
    超额最大回撤: str = Field(..., description="超额最大回撤")
    年化波动: str = Field(..., description="年化波动")
    超额年化波动: str = Field(..., description="超额年化波动")
    换手率: str = Field(..., description="换手率")
    月度胜率: str = Field(..., description="月度胜率")
    超额月度胜率: str = Field(..., description="超额月度胜率")
    跟踪误差: str = Field(..., description="跟踪误差")
    夏普比率: str = Field(..., description="夏普比率")
    信息比率: str = Field(..., description="信息比率")

class GroupReturnAnalysisResponse(BaseModel):
    """分组收益分析数据响应"""
    task_id: str = Field(..., description="任务ID")
    group_return_analysis: List[GroupReturnAnalysis] = Field(..., description="分组收益分析数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ICDecayChartData(BaseModel):
    """IC衰减图表数据"""
    title: str = Field(..., description="图表标题")
    x: List[ChartAxisData] = Field(..., description="X轴数据")
    y: List[ChartAxisData] = Field(..., description="Y轴数据")

class ICDecayChartResponse(BaseModel):
    """IC衰减图表响应"""
    task_id: str = Field(..., description="任务ID")
    ic_decay_chart: Optional[ICDecayChartData] = Field(default=None, description="IC衰减图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ICDensityChartData(BaseModel):
    """IC分布图表数据"""
    title: str = Field(..., description="图表标题")
    x: List[ChartAxisData] = Field(..., description="X轴数据")
    y: List[ChartAxisData] = Field(..., description="Y轴数据")

class ICDensityChartResponse(BaseModel):
    """IC分布图表响应"""
    task_id: str = Field(..., description="任务ID")
    ic_den_chart: Optional[ICDensityChartData] = Field(default=None, description="IC分布图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ICSelfCorrelationChartData(BaseModel):
    """IC自相关图表数据"""
    title: str = Field(..., description="图表标题")
    x: List[ChartAxisData] = Field(..., description="X轴数据")
    y: List[ChartAxisData] = Field(..., description="Y轴数据，包含自相关系数和置信区间")

class ICSelfCorrelationChartResponse(BaseModel):
    """IC自相关图表响应"""
    task_id: str = Field(..., description="任务ID")
    ic_self_correlation_chart: Optional[ICSelfCorrelationChartData] = Field(default=None, description="IC自相关图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ICSequenceChartData(BaseModel):
    """IC序列图表数据"""
    title: str = Field(..., description="图表标题，包含IC和IC_IR值")
    x: List[ChartAxisData] = Field(..., description="X轴数据（日期）")
    y: List[ChartAxisData] = Field(..., description="Y轴数据，包含IC和累计IC")

class ICSequenceChartResponse(BaseModel):
    """IC序列图表响应"""
    task_id: str = Field(..., description="任务ID")
    ic_seq_chart: Optional[ICSequenceChartData] = Field(default=None, description="IC序列图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class LastDateTopFactorData(BaseModel):
    """最新日期的因子值数据"""
    date: str = Field(..., description="日期，格式为YYYYMMDD")
    symbol: str = Field(..., description="股票代码")
    python: str = Field(..., description="因子值")

class LastDateTopFactorResponse(BaseModel):
    """最新日期的因子值响应"""
    task_id: str = Field(..., description="任务ID")
    last_date_top_factor: List = Field(..., description="最新日期的因子值列表")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class OneGroupData(BaseModel):
    """单组数据分析结果"""
    return_ratio: float = Field(..., description="收益率")
    annualized_ratio: str = Field(..., description="年化收益率")
    sharpe_ratio: float = Field(..., description="夏普比率")
    maximum_drawdown: str = Field(..., description="最大回撤")

class OneGroupDataResponse(BaseModel):
    """单组数据分析结果响应"""
    task_id: str = Field(..., description="任务ID")
    one_group_data: dict = Field(default=None, description="单组数据分析结果")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class RankICDecayChartData(BaseModel):
    """Rank IC衰减图表数据"""
    title: str = Field(..., description="图表标题")
    x: List[ChartAxisData] = Field(..., description="X轴数据（滞后期数）")
    y: List[ChartAxisData] = Field(..., description="Y轴数据（IC值）")

class RankICDecayChartResponse(BaseModel):
    """Rank IC衰减图表响应"""
    task_id: str = Field(..., description="任务ID")
    rank_ic_decay_chart: Optional[RankICDecayChartData] = Field(default=None, description="Rank IC衰减图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class RankICDensityChartData(BaseModel):
    """Rank IC分布图表数据"""
    title: str = Field(..., description="图表标题，包含偏度(skew)和峰度(kurt)值")
    x: List[ChartAxisData] = Field(..., description="X轴数据（Rank_IC值）")
    y: List[ChartAxisData] = Field(..., description="Y轴数据（密度值）")

class RankICDensityChartResponse(BaseModel):
    """Rank IC分布图表响应"""
    task_id: str = Field(..., description="任务ID")
    rank_ic_den_chart: Optional[RankICDensityChartData] = Field(default=None, description="Rank IC分布图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class RankICSelfCorrelationChartData(BaseModel):
    """Rank IC自相关图表数据"""
    title: str = Field(..., description="图表标题")
    x: List[ChartAxisData] = Field(..., description="X轴数据（滞后期数）")
    y: List[ChartAxisData] = Field(..., description="Y轴数据，包含自相关系数和置信区间")

class RankICSelfCorrelationChartResponse(BaseModel):
    """Rank IC自相关图表响应"""
    task_id: str = Field(..., description="任务ID")
    rank_ic_self_correlation_chart: Optional[RankICSelfCorrelationChartData] = Field(default=None, description="Rank IC自相关图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class RankICSequenceChartData(BaseModel):
    """Rank IC序列图表数据"""
    title: str = Field(..., description="图表标题，包含Rank_IC和IC_IR值")
    x: List[ChartAxisData] = Field(..., description="X轴数据（日期）")
    y: List[ChartAxisData] = Field(..., description="Y轴数据，包含Rank_IC和累计Rank_IC")

class RankICSequenceChartResponse(BaseModel):
    """Rank IC序列图表响应"""
    task_id: str = Field(..., description="任务ID")
    rank_ic_seq_chart: Optional[RankICSequenceChartData] = Field(default=None, description="Rank IC序列图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class ReturnChartData(BaseModel):
    """收益率图表数据"""
    title: str = Field(..., description="图表标题")
    x: List[ChartAxisData] = Field(..., description="X轴数据（日期）")
    y: List[ChartAxisData] = Field(..., description="Y轴数据，包含各组收益率和多空组合收益率")

class ReturnChartResponse(BaseModel):
    """收益率图表响应"""
    task_id: str = Field(..., description="任务ID")
    return_chart: Optional[ReturnChartData] = Field(default=None, description="收益率图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class SimpleReturnChartData(BaseModel):
    """单组收益率图表数据"""
    title: str = Field(..., description="图表标题")
    x: List[ChartAxisData] = Field(..., description="X轴数据（日期）")
    y: List[ChartAxisData] = Field(..., description="Y轴数据（单组收益率）")

class SimpleReturnChartResponse(BaseModel):
    """单组收益率图表响应"""
    task_id: str = Field(..., description="任务ID")
    simple_return_chart: Optional[SimpleReturnChartData] = Field(default=None, description="单组收益率图表数据")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

class UserFactorListItem(BaseModel):
    """用户因子列表项"""
    name:str = Field(...,deprecated="因子名称CN")
    factor_id: str = Field(..., description="因子ID")
    factor_name: str = Field(..., description="因子名称")
    return_ratio: str = Field(default="0.0",description="收益率")
    sharpe_ratio: float = Field(default=0.0, description="夏普比率")
    maximum_drawdown: str = Field(default="0.0", description="最大回撤")
    annualized_ratio:str =Field( description="年化收益率")
    IC: float = Field(default=0.0, description="IC均值")
    IR: float = Field(default=0.0,description="信息比率")
    updated_at: str = Field(..., description="更新时间")
    created_at: str = Field(..., description="创建时间")

class UserFactorListResponse(BaseModel):
    """用户因子列表响应"""
    data: List[UserFactorListItem] = Field(..., description="因子列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=10, description="每页数量")
    total_pages: int = Field(default=0, description="总页数")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
