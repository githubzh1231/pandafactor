from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union, Any
from datetime import datetime


class SeriesItem(BaseModel):
    """单个系列数据项"""
    name: str = Field(..., description="系列名称")
    data: List[Union[float, str]] = Field(..., description="系列数据点")


class ChartData(BaseModel):
    """图表数据基类"""
    title: str = Field(..., description="图表标题")
    x: List[SeriesItem] = Field(..., description="x轴数据")
    y: List[SeriesItem] = Field(..., description="y轴数据")


# class ReturnChartData(BaseModel):
#     """收益率图表数据"""
#     series: List[SeriesItem] = Field(..., description="收益率系列数据")
#     dates: List[str] = Field(..., description="日期列表")


# class ICTimeData(BaseModel):
#     """IC时序图数据"""
#     title: str = Field(..., description="图表标题")
#     x_label: str = Field(..., description="x轴标签")
#     x_data: List[str] = Field(..., description="x轴数据")
#     y: Dict[str, Any] = Field(..., description="y轴数据，包含多个系列")


# class ICHistData(BaseModel):
#     """IC直方图数据"""
#     histogram: Dict[str, List[float]] = Field(..., description="直方图数据")
#     normal_curve: Dict[str, List[float]] = Field(..., description="正态分布曲线")
#     stats: Dict[str, float] = Field(..., description="统计指标")


# class ICDecayData(BaseModel):
#     """IC衰减图数据"""
#     lag: int = Field(..., description="滞后期数")
#     value: float = Field(..., description="IC值")


# class ACFData(BaseModel):
#     """自相关图数据"""
#     lag: int = Field(..., description="滞后期数")
#     acf: float = Field(..., description="自相关系数")
#     lower_bound: float = Field(..., description="下界")
#     upper_bound: float = Field(..., description="上界")


# class FactorStat(BaseModel):
#     """因子统计指标"""
#     group_name: str = Field(..., description="分组名称")
#     年化收益率: Optional[str] = Field(None, description="年化收益率")
#     超额年化: Optional[str] = Field(None, description="超额年化")
#     最大回撤: Optional[str] = Field(None, description="最大回撤")
#     超额最大回撤: Optional[str] = Field(None, description="超额最大回撤")
#     年化波动: Optional[str] = Field(None, description="年化波动")
#     超额年化波动: Optional[str] = Field(None, description="超额年化波动")
#     换手率: Optional[str] = Field(None, description="换手率")
#     月度胜率: Optional[str] = Field(None, description="月度胜率")
#     超额月度胜率: Optional[str] = Field(None, description="超额月度胜率")
#     跟踪误差: Optional[str] = Field(None, description="跟踪误差")
#     夏普比率: Optional[str] = Field(None, description="夏普比率")
#     信息比率: Optional[str] = Field(None, description="信息比率")


# class ICStat(BaseModel):
#     """IC统计指标"""
#     metric: str = Field(..., description="指标名称")
#     value: str = Field(..., description="指标值")


# class TopFactor(BaseModel):
#     """Top因子数据"""
#     symbol: str = Field(..., description="股票代码")
#     name: Optional[str] = Field("", description="股票名称")
#     value: float = Field(..., description="因子值")


# class FactorAnalysisChartData(BaseModel):
#     """完整因子分析图表数据"""
#     return_chart: ReturnChartData
#     excess_return_chart: ReturnChartData
#     ic_time_chart: Optional[ICTimeData] = None
#     ic_hist_chart: Optional[ICHistData] = None
#     ic_decay_data: Optional[List[ICDecayData]] = Field(default_factory=list)
#     acf_data: Optional[List[ACFData]] = Field(default_factory=list)
#     group_stats: Optional[List[FactorStat]] = Field(default_factory=list)
#     ic_stats: Optional[List[ICStat]] = Field(default_factory=list)
#     top_factors: Optional[List[TopFactor]] = Field(default_factory=list)
    
#     class Config:
#         json_encoders = {
#             datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S")
#         }
        
#     def dict(self, *args, **kwargs):
#         """转换为字典，处理None值"""
#         result = super().dict(*args, **kwargs)
#         # 处理可能的None值，确保JSON序列化不会出错
#         return {k: ([] if v is None and isinstance(v, list) else v) for k, v in result.items()}

