from fastapi import APIRouter, Query

from panda_common.config import config
from panda_data_hub.services.query.stock_statistic_service import StockStatisticQuery

router = APIRouter()

@router.get('/data_query')
async def data_query(tables_name : str ,
                     start_date : str ,
                     end_date : str,
                     page: int = Query(default=1, ge=1, description="页码"),
                     page_size: int = Query(default=10, ge=1, le=100, description="每页数量"),
                     sort_field: str = Query(default="created_at", description="排序字段，支持created_at、return_ratio、sharpe_ratio、maximum_drawdown、IC、IR"),
                     sort_order: str = Query(default="desc", description="排序方式，asc升序，desc降序")
                     ):
    """ 根据表名和起止时间获取统计数据 """
    service = StockStatisticQuery(config)
    result_data = service.get_stock_statistic(tables_name,start_date,end_date,page, page_size,sort_field, sort_order)

    return result_data

@router.get('/get_trading_days')
async def data_query(
        start_date: str ,
        end_date: str ,
):
    service = StockStatisticQuery(config)
    result_data = service.get_trading_days(start_date,end_date)
    return result_data




