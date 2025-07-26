from typing import Dict

from fastapi import APIRouter, BackgroundTasks

from panda_common.config import config

from panda_data_hub.services.rq_stock_market_clean_service import StockMarketCleanRQServicePRO
from panda_data_hub.services.ts_stock_market_clean_service import StockMarketCleanTSServicePRO
# from panda_data_hub.services.xt_download_service import XTDownloadService

# from panda_data_hub.services.xt_stock_market_clean_service import StockMarketCleanXTServicePRO

router = APIRouter()

@router.get('/upsert_stockmarket_final')
async def upsert_stockmarket(start_date: str, end_date: str, background_tasks: BackgroundTasks):
    global current_progress
    current_progress = 0  # 重置进度

    data_source = config['DATAHUBSOURCE']

    def progress_callback(progress: int):
        global current_progress
        current_progress = progress

    if data_source  == 'ricequant':
        rice_quant_service = StockMarketCleanRQServicePRO(config)
        rice_quant_service.set_progress_callback(progress_callback)
        # 在后台运行数据清洗任务
        background_tasks.add_task(
            rice_quant_service.stock_market_clean_by_time,
            start_date,
            end_date
        )
    elif data_source == 'tushare':
        tushare_service = StockMarketCleanTSServicePRO(config)
        tushare_service.set_progress_callback(progress_callback)
        background_tasks.add_task(
            tushare_service.stock_market_history_clean,
            start_date,
            end_date
        )
    # elif data_source == 'xuntou':
    #     xt_quant_service = StockMarketCleanXTServicePRO(config)
    #     xt_quant_service.set_progress_callback(progress_callback)
    #     background_tasks.add_task(
    #         xt_quant_service.stock_market_history_clean,
    #         start_date,
    #         end_date
    #     )
    return {"message": "Stock market data cleaning started by {data_source}"}


@router.get('/get_progress_stock_final')
async def get_progress() -> Dict[str, int]:
    """获取当前数据清洗进度"""
    return {"progress": current_progress}


# @router.get("/download_xt_data")
# async def download_xt_data(start_date: str, end_date: str,background_tasks: BackgroundTasks):
#
#     def progress_callback(progress: int):
#         global current_progress
#         current_progress = progress
#
#     service = XTDownloadService(config)
#     service.set_progress_callback(progress_callback)
#     background_tasks.add_task(
#         service.xt_price_data_download,
#         start_date,
#         end_date
#     )
#     return {"message": "XTData data downloading started"}
